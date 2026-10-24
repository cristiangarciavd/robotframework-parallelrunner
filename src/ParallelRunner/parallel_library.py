import os
import importlib
import queue
import threading
import time
from typing import Iterable, Any, List, Dict, Optional, Tuple, Union
from robot.api import logger
try:
    from robot.errors import TimeoutExceeded
except ImportError:  # Robot Framework < 7.0
    from robot.errors import TimeoutError as TimeoutExceeded
from robot.libraries.BuiltIn import BuiltIn

from .version import __version__


# Robot Framework log levels, in increasing severity. HTML and CONSOLE are
# INFO messages (rendered as HTML / also written to the console).
LOG_LEVELS = {"TRACE": 0, "DEBUG": 1, "INFO": 2, "HTML": 2, "CONSOLE": 2, "WARN": 3, "ERROR": 4}
# Spellings from Python's `logging` module, mapped to the Robot level.
LOG_LEVEL_ALIASES = {"WARNING": "WARN", "CRITICAL": "ERROR", "FATAL": "ERROR"}

# How often the main thread checks whether the calls have finished. Waiting in
# short sleeps (instead of blocking on a lock until the end) is what lets a
# Robot `[Timeout]` interrupt the keyword: on Windows the timeout is raised
# asynchronously and only arrives while Python code runs.
_POLL_INTERVAL = 0.01


def _normalize_level(level: Any) -> Optional[str]:
    """Returns the Robot level name for ``level`` (any case, or a Python
    ``logging`` alias), ``"IGNORE"``, or None if it's not a known level."""
    name = str(level).strip().upper()
    name = LOG_LEVEL_ALIASES.get(name, name)
    return name if name in LOG_LEVELS or name == "IGNORE" else None


class ParallelTaskError(RuntimeError):
    """
    Raised when at least one parallel task failed: by ``run_parallel_scenarios``
    (unless called with ``fail_on_error=False``), and by ``get_result_values``,
    which has no meaningful return value to hand back for a failed task.

    Returning normally after a failed call would let a test keep going (and
    pass) with bad or missing data instead of failing for the right reason,
    so this is raised instead - after every task has finished and all logs
    have been replayed.

    Attributes:
        failures: the subset of result dicts with ``status == "FAIL"``,
            in the same order they appear in the full result list.
    """

    def __init__(self, failures: List[Dict[str, Any]], total: int):
        self.failures = failures
        detail = "; ".join(f"item={entry['item']!r}: {entry['error']}" for entry in failures)
        super().__init__(f"{len(failures)} of {total} parallel task(s) failed: {detail}")


class ParallelRunner:
    """
    ParallelRunner runs a keyword many times *inside a single test case*,
    concurrently on a thread pool, and still produces one clean, ordered
    ``log.html``.

    Typical uses: validate 100 API endpoints in one test, or repeat one
    call N times (seed N fixture rows, a light concurrent load check) -
    I/O-bound work where most of the time is spent waiting on the network
    or a database.

    = Table of contents =

    %TOC%

    = How it works =

    - Each call runs on one of a pool of worker threads (see
      ``ROBOT_THREAD_WORKERS``), created for that keyword call.
      ``BuiltIn().run_keyword`` is *not* used inside threads (it is not
      thread-safe); the underlying Python method of the target library is
      called directly instead.
    - Every thread buffers its log messages in memory. When all tasks have
      finished, the logs are replayed sequentially into the real Robot
      Framework logger, grouped per item and in call order - so concurrent
      work never interleaves or corrupts ``log.html``.
    - Results come back in *call order*, not completion order: entry ``i``
      always belongs to the ``i``-th item / repetition.

    = Writing a parallel-ready keyword =

    The target keyword must be a method of a Python library that is already
    imported in the suite. It receives the current item (or the repeat
    index) as its first argument and an injected ``_logger`` callable that
    it should use instead of ``robot.api.logger``:

    | from robot.api import logger
    |
    | class MyLibrary:
    |     def verify_agent(self, agent_id, _logger=None, **kwargs):
    |         log = _logger or (lambda msg, level="INFO": logger.write(msg, level))
    |         log(f"Checking agent {agent_id}")
    |         ...
    |         return result

    ``_logger(msg, level)`` accepts every Robot Framework log level (see
    `Log levels`) plus ``IGNORE`` (dropped). Any extra named argument given to
    `Run Parallel Scenarios` is forwarded to every call as ``**kwargs``.

    Logging is made thread-safe for you; your keyword's own side effects are
    not. Protect shared state (files, shared objects) with a lock.

    = Result format =

    `Run Parallel Scenarios` returns a list with one dictionary per call:

    | =Key=    | =Description= |
    | status   | ``PASS`` or ``FAIL``. |
    | item     | The item (or repeat index) the call received. |
    | logs     | List of ``(level, message)`` tuples captured during the call. |
    | result   | The return value of the call (only when ``status`` is ``PASS``). |
    | error    | The error message (only when ``status`` is ``FAIL``). |

    = Failures =

    If any call raises, `Run Parallel Scenarios` still waits for every other
    call, replays all logs, and then *fails* with a ``ParallelTaskError``
    that lists each failed item and its error, e.g.
    ``2 of 5 parallel task(s) failed: item='4': ...; item='5': ...``.
    One failed call is never hidden behind a passing keyword.

    To inspect failures yourself instead, pass ``fail_on_error=False``: the
    keyword then always returns the result list, failed calls get
    ``status`` ``FAIL`` (their error is also logged at ``ERROR`` level), and
    it is up to you to assert on them:

    | ${results}= | Run Parallel Scenarios | keyword=Verify Agent Data | library=MyLibrary | for_loop_iterable=${agents} | fail_on_error=False |
    | Should Be Equal | ${results}[1][status] | PASS |

    ``return_values_only=True`` and `Get Result Values` always fail if any
    call failed, because a failed call has no return value.

    = Log levels =

    The injected ``_logger`` accepts the same levels as Robot Framework's
    ``logger.write``: ``TRACE``, ``DEBUG``, ``INFO``, ``HTML`` (an ``INFO``
    message rendered as HTML), ``CONSOLE`` (an ``INFO`` message also written
    to the console), ``WARN`` and ``ERROR``. Levels are case-insensitive, and
    Python ``logging`` names are accepted too: ``WARNING`` is ``WARN``,
    ``CRITICAL`` and ``FATAL`` are ``ERROR``. ``IGNORE`` drops the message.

    Replayed messages go through Robot's normal filtering, so ``TRACE`` and
    ``DEBUG`` messages only show up in ``log.html`` when the run uses a low
    enough ``--loglevel`` (e.g. ``--loglevel DEBUG``), exactly as they would
    from a normal keyword. ``thread_log_level`` filters the threads' messages
    on top of that (by default it lets every level through).

    A message with an unknown level is not lost: it is logged at ``INFO``
    with the level as a prefix (``[VERBOSE] message``), and a warning names
    the unknown level once per keyword call.

    = Timeouts =

    A Robot ``[Timeout]`` (test or keyword) interrupts `Run Parallel Scenarios`
    as soon as it expires, not when the whole batch has finished. Before the
    timeout failure is reported, the logs collected so far are replayed:
    finished calls as usual, and every call that did not finish with its
    partial logs and an ``ERROR`` saying it was interrupted.

    Python threads can't be killed, so calls that are already running keep
    running in the background until they return (possibly while the next test
    runs); calls that had not started yet are not started. The worker threads
    are daemon threads, so they never keep the Robot process alive after the
    run. A keyword that may hang (e.g. network I/O) should set its own
    timeouts (e.g. ``requests.get(url, timeout=10)``).

    = Custom logger mappers =

    A logger mapper replaces the default buffering logger: the target keyword
    receives it as ``_logger`` and every message goes straight to your own
    logging system. Use it when a project already has its own log format
    (severity codes, JSON...).

    - Give it as a callable or as a ``module.function`` path, either with the
      ``logger_mapper`` argument or, for a project-wide default, with the
      ``ROBOT_LOGGER_MAPPER`` environment variable. The argument wins.
    - Bare names (without a module path) are not supported. A value that
      can't be resolved is ignored with a warning in the log.
    - Mapper messages are *not* buffered and replayed into ``log.html``, so
      ``thread_log_level`` and ``remove_passing_logs`` don't apply to them.
      The mapper is called from several threads at once, so it must be
      thread-safe.
    - ``ROBOT_LOGGER_MAPPER`` must be a real environment variable (e.g. set
      with ``Set Environment Variable`` or in the shell); a Robot variable
      given with ``--variable`` is not read.

    = Environment variables =

    | =Variable=             | =Description= |
    | ROBOT_THREAD_WORKERS   | Number of worker threads. Read when the library is imported. Default ``4``. |
    | ROBOT_LOGGER_MAPPER    | Default ``logger_mapper`` as a ``module.function`` path, used when the argument is not given. See `Custom logger mappers`. |

    = When not to use it =

    - CPU-bound work: threads share Python's GIL. Use
      [https://github.com/mkorpela/pabot|pabot] or ``multiprocessing``.
    - Running many independent suites/tests faster: that is what pabot is
      for. Both tools compose well together.
    """
    ROBOT_LIBRARY_SCOPE = 'GLOBAL'
    ROBOT_LIBRARY_VERSION = __version__
    ROBOT_LIBRARY_DOC_FORMAT = 'ROBOT'

    def __init__(self):
        # Workers count from Env Var or default to 4
        self.max_workers = int(os.getenv("ROBOT_THREAD_WORKERS", "4"))

    def run_parallel_scenarios(
        self,
        keyword: str,
        library: str,
        for_loop_iterable: Optional[Iterable[Any]] = None,
        repeat: Optional[int] = None,
        remove_passing_logs: bool = False,
        thread_log_level: str = "TRACE",
        logger_mapper: Optional[Any] = None,
        return_values_only: bool = False,
        fail_on_error: bool = True,
        **kwargs
    ) -> Union[List[Dict[str, Any]], Tuple[Any, ...]]:
        """Runs ``keyword`` from ``library`` concurrently, once per item or N times.

        Arguments:
        - ``keyword``: Name of the keyword to run, e.g. ``Verify Agent Data``.
          It must be implemented as a Python method of ``library`` (see
          `Writing a parallel-ready keyword`).
        - ``library``: Name of the library that owns the keyword, exactly as
          it was imported in the suite (e.g. ``my_package.MyLibrary``).
        - ``for_loop_iterable``: Items to iterate over, like a parallel FOR
          loop. Each call receives one item as its first argument. Takes
          precedence over ``repeat``.
        - ``repeat``: Run the keyword this many times; each call receives its
          repeat index (``0`` .. ``N-1``). ``repeat=0`` runs it zero times.
          If neither ``for_loop_iterable`` nor ``repeat`` is given, the
          keyword runs once.
        - ``remove_passing_logs``: If true, logs of passing calls are not
          replayed into ``log.html``; only failed calls are shown.
        - ``thread_log_level``: Minimum level replayed from the threads:
          ``TRACE`` (default, every message), ``DEBUG``, ``INFO``, ``WARN``
          or ``ERROR``. Robot's own ``--loglevel`` still applies on top of it
          (see `Log levels`). An unknown value is ignored with a warning.
        - ``logger_mapper``: Optional callable ``mapper(msg, level)`` - or a
          ``module.function`` path to one, such as
          ``my_package.my_module.my_mapper`` - injected as ``_logger`` instead
          of the default buffering logger, to route logs to a custom logging
          system. Falls back to the ``ROBOT_LOGGER_MAPPER`` environment
          variable. A value that can't be resolved (e.g. a bare name without a
          module) is ignored with a warning. See `Custom logger mappers`.
        - ``return_values_only``: If true, return a plain tuple of each call's
          return value (in call order) instead of the result dictionaries.
          Fails with ``ParallelTaskError`` if any call failed. Same as calling
          `Get Result Values` on the default return value.
        - ``fail_on_error``: If true (default), fail with ``ParallelTaskError``
          when any call failed, after all calls have finished and their logs
          have been replayed. If false, return the results anyway and leave
          checking ``status`` to the caller. See `Failures`.
        - ``**kwargs``: Any other named argument is passed to every call.

        Returns a list of result dictionaries (see `Result format`), in call
        order: entry ``i`` belongs to ``for_loop_iterable[i]`` / repeat
        index ``i``, regardless of which thread finished first. With the
        default ``fail_on_error=True`` it only returns when every call passed.

        Examples:
        | ${agents}=    | Create List            | 1                         | 2                       | 3 |
        | ${results}=   | Run Parallel Scenarios | keyword=Verify Agent Data | library=MyLibrary       | for_loop_iterable=${agents} |
        | ${results}=   | Run Parallel Scenarios | keyword=Check Health      | library=MyLibrary       | repeat=8 | agent_id=1 |
        | ${id1}    ${id2}    ${id3}= | Run Parallel Scenarios | keyword=Seed Record | library=MyLibrary | repeat=3 | return_values_only=True |
        | ${results}=   | Run Parallel Scenarios | keyword=Verify Agent Data | library=MyLibrary       | for_loop_iterable=${agents} | fail_on_error=False |
        """
        # Determine items to process. NOTE: `repeat or 1` would be wrong here -
        # 0 is falsy in Python, so an explicit repeat=0 would silently fall
        # back to running once instead of zero times. Only a missing (None)
        # repeat should default to 1.
        if for_loop_iterable is not None:
            items = for_loop_iterable
        else:
            items = range(1 if repeat is None else repeat)

        # Resolve mapper: it might be a callable or a string path
        effective_mapper = self._resolve_mapper(logger_mapper)

        # If not resolved from parameter, try environment
        if effective_mapper is None:
            effective_mapper = self._load_mapper_from_environment()

        min_level = self._resolve_thread_log_level(thread_log_level)

        # Note: We must call the underlying Python method, not BuiltIn().run_keyword
        # because run_keyword is not thread-safe.
        lib_instance = self._get_library_instance_owning_keyword(keyword, library)
        method = getattr(lib_instance, keyword.replace(" ", "_").lower())

        results = self._run_in_threads(method, list(items), effective_mapper, remove_passing_logs, min_level, kwargs)

        # Step: Re-play logs into Robot Framework sequentially
        self._replay_logs(results, remove_passing_logs, min_level)

        if return_values_only:
            return self.get_result_values(results)
        if fail_on_error:
            self._raise_if_any_failed(results)
        return results

    def get_result_values(self, results: List[Dict[str, Any]]) -> Tuple[Any, ...]:
        """Returns the return value of every call in ``results``, as a tuple in call order.

        ``results`` is the list returned by `Run Parallel Scenarios`.
        ``results[i]`` becomes tuple index ``i``.

        Passing ``return_values_only=True`` to `Run Parallel Scenarios` does
        the same in one step; use this keyword when you want to inspect the
        full results first (e.g. assert on ``status`` or ``logs``). Such a
        result list may only contain failed calls if it came from a run with
        ``fail_on_error=False``.

        Fails with ``ParallelTaskError`` if any entry has status ``FAIL`` -
        a failed call has no return value to put in its slot.

        Example:
        | ${results}=                 | Run Parallel Scenarios | keyword=Seed Record | library=MyLibrary | repeat=3 |
        | ${id1}    ${id2}    ${id3}= | Get Result Values      | ${results}          |
        """
        self._raise_if_any_failed(results)
        return tuple(entry["result"] for entry in results)

    def _raise_if_any_failed(self, results: List[Dict[str, Any]]) -> None:
        failures = [entry for entry in results if entry.get("status") == "FAIL"]
        if failures:
            raise ParallelTaskError(failures, len(results))

    def _resolve_mapper(self, mapper: Optional[Any], source: str = "logger_mapper") -> Optional[Any]:
        """
        Resolve a mapper given as a callable or as a ``module.function`` path
        (e.g. "examples.custom_logger.custom_logging_mapper.custom_logger_adapter").

        Returns the callable, or None when no mapper was given. A mapper that
        was given but can't be resolved (a bare name without a module, a module
        that can't be imported, a missing or non-callable attribute) is ignored
        with a warning in the log - it used to be ignored silently, which hid
        typos and unsupported values such as bare registered names.

        Args:
            mapper: Callable, ``module.function`` string, or "not given": None,
                an empty string, or the string "None" (any case - Robot
                Framework's usual spelling of None, e.g. ``logger_mapper=None``).
            source: Where the value came from, used in the warning message.
        """
        if mapper is None or (isinstance(mapper, str) and mapper.strip().upper() in ("", "NONE")):
            return None

        if callable(mapper):
            return mapper

        if isinstance(mapper, str):
            module_name, _, func_name = mapper.strip().rpartition(".")
            if not module_name or not func_name:
                reason = "expected a 'module.function' path such as 'my_package.my_module.my_mapper'"
            else:
                try:
                    module = importlib.import_module(module_name)
                except ImportError as error:
                    reason = f"cannot import module '{module_name}' ({error})"
                else:
                    resolved = getattr(module, func_name, None)
                    if callable(resolved):
                        return resolved
                    reason = f"module '{module_name}' has no callable '{func_name}'"
        else:
            reason = f"expected a callable or a 'module.function' string, got {type(mapper).__name__}"

        logger.warn(f"Ignoring {source} {mapper!r}: {reason}.")
        return None

    def _load_mapper_from_environment(self) -> Optional[Any]:
        """
        Load the logger mapper named by the ROBOT_LOGGER_MAPPER environment
        variable, which must be a ``module.function`` path (bare names are not
        supported and are ignored with a warning).

        Returns:
            Callable: The mapper function if found, None otherwise.
        """
        return self._resolve_mapper(os.getenv("ROBOT_LOGGER_MAPPER"), source="ROBOT_LOGGER_MAPPER")

    def _get_library_instance_owning_keyword(self, keyword_name: str, library: str) -> Any:
        method_name = keyword_name.replace(" ", "_").lower()
        lib_instance = BuiltIn().get_library_instance(library)
        if hasattr(lib_instance, method_name):
            return lib_instance
        raise ValueError(f"Keyword '{keyword_name}' not found in library '{library}'")

    def _resolve_thread_log_level(self, thread_log_level: Any) -> int:
        """Returns the numeric minimum level for ``thread_log_level``. Not
        given (None, empty, "None") means every level; an unknown value is
        ignored with a warning instead of silently filtering by INFO."""
        if thread_log_level is None or str(thread_log_level).strip().upper() in ("", "NONE"):
            return LOG_LEVELS["TRACE"]
        level = _normalize_level(thread_log_level)
        if level in LOG_LEVELS:
            return LOG_LEVELS[level]
        logger.warn(
            f"Ignoring thread_log_level {thread_log_level!r}: expected TRACE, DEBUG, INFO, WARN or ERROR. "
            "Replaying every level."
        )
        return LOG_LEVELS["TRACE"]

    def _run_in_threads(
        self,
        method,
        items: List[Any],
        logger_mapper: Optional[Any],
        remove_passing_logs: bool,
        min_level: int,
        kwargs: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Runs ``method`` once per item on up to ``max_workers`` daemon threads
        and returns the result dicts in call order (NOT completion order).

        If the wait is interrupted (mostly by a Robot ``[Timeout]``), the
        workers stop starting new calls, the logs collected so far are
        replayed and the exception is re-raised. Calls already running can't
        be stopped: they finish in the background. The threads are daemon
        threads (unlike the ones of ``ThreadPoolExecutor``), so a call that
        never returns can't keep the Robot process alive at exit.
        """
        if self.max_workers < 1:
            raise ValueError(f"ROBOT_THREAD_WORKERS must be at least 1, got {self.max_workers}.")

        # Created here, not in the workers, so the logs of calls that are still
        # running can be replayed if the keyword is interrupted.
        log_buffers: List[list] = [[] for _ in items]
        results: List[Optional[Dict[str, Any]]] = [None] * len(items)
        started = [False] * len(items)
        pending = queue.SimpleQueue()
        for index in range(len(items)):
            pending.put(index)
        stop = threading.Event()

        def worker():
            while not stop.is_set():
                try:
                    index = pending.get_nowait()
                except queue.Empty:
                    return
                started[index] = True
                results[index] = self._execute_and_capture(
                    method, items[index], logger_mapper, log_buffers[index], kwargs
                )

        try:
            for number in range(min(self.max_workers, len(items))):
                threading.Thread(target=worker, name=f"ParallelRunner-worker-{number + 1}", daemon=True).start()
            # Deliberately no lock, Event or Future wait here: a timeout raised
            # asynchronously while such a wait holds an internal lock could
            # leave it locked forever. Short sleeps and plain reads are safe.
            for index in range(len(items)):
                while results[index] is None:
                    time.sleep(_POLL_INTERVAL)
        except BaseException as error:
            stop.set()
            self._replay_interrupted(items, results, started, log_buffers, error, remove_passing_logs, min_level)
            raise
        return results

    def _replay_interrupted(self, items, results, started, log_buffers, error, remove_passing_logs, min_level):
        """Replays what the calls logged before the keyword was interrupted.
        Calls that never started are only counted, not listed one by one."""
        # On Windows Robot raises the timeout as a bare class, without message.
        reason = str(error) or ("Robot timeout exceeded" if isinstance(error, TimeoutExceeded) else type(error).__name__)
        partial = []
        running = not_started = 0
        for index, item in enumerate(items):
            # Read the result before `started`: a call that finishes in between
            # is then reported as still running, never as not started.
            result = results[index]
            if result is not None:
                partial.append(result)
            elif started[index]:
                running += 1
                logs = list(log_buffers[index])
                logs.append(("ERROR", f"Call for item {item} did not finish: still running when the keyword was interrupted ({reason})"))
                partial.append({"status": "FAIL", "item": item, "logs": logs, "error": f"Did not finish: interrupted ({reason})"})
            else:
                not_started += 1
        logger.info(
            f"Run Parallel Scenarios was interrupted ({reason}): {len(partial) - running} call(s) finished, "
            f"{running} still running (left running in the background), {not_started} not started."
        )
        self._replay_logs(partial, remove_passing_logs, min_level)

    def _execute_and_capture(
        self, method, item, logger_mapper: Optional[Any], log_buffer: list, kwargs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Worker wrapper to capture logs and results.

        ``kwargs`` is a dict, not ``**kwargs``, so a keyword argument that
        happens to be called ``method``, ``item`` or ``log_buffer`` can't clash
        with this method's own parameters.
        """
        # Injection of a custom logger into the thread
        def thread_log(msg, level="INFO"):
            # Filter out IGNORE (sv=0) level logs. Other levels are kept as
            # given and checked when the logs are replayed.
            if _normalize_level(level) != "IGNORE":
                log_buffer.append((level, msg))

        # Use mapper if provided, otherwise use thread_log
        effective_logger = logger_mapper if logger_mapper else thread_log

        try:
            result = method(item, _logger=effective_logger, **kwargs)
            return {"status": "PASS", "item": item, "logs": log_buffer, "result": result}
        # BaseException, not Exception: whatever the call raises (even
        # SystemExit), the worker must report a result, or the main thread
        # would wait for this call forever.
        except BaseException as e:
            thread_log(f"Thread failed for item {item}: {str(e)}", "ERROR")
            return {"status": "FAIL", "item": item, "logs": log_buffer, "error": str(e)}

    def _replay_logs(self, results: List[Dict[str, Any]], remove_passing_logs: bool = False, min_level: int = 0):
        """Sequential dump to the real RF Logger, in call order.

        Every Robot level goes through ``logger.write``, so Robot's
        ``--loglevel`` filters it as usual. IGNORE messages and levels below
        ``min_level`` are skipped. A message with an unknown level is kept at
        INFO, prefixed with its level, plus one warning per unknown level.
        (Before 0.3.1 only INFO/WARN/ERROR were written; everything else,
        DEBUG included, was dropped silently.)
        """
        unknown_levels = []
        for entry in results:
            if remove_passing_logs and entry['status'] == 'PASS':
                continue
            logger.info(f"--- Logs for Item: {entry['item']} ---")
            # A copy: after an interruption, a call still running may append to it.
            for level, msg in list(entry['logs']):
                name = _normalize_level(level)
                if name == "IGNORE":
                    continue
                if name is None:
                    if level not in unknown_levels:
                        unknown_levels.append(level)
                    name, msg = "INFO", f"[{level}] {msg}"
                if LOG_LEVELS[name] >= min_level:
                    logger.write(msg, name)
            logger.info(f"Status: {entry['status']}")
        for level in unknown_levels:
            logger.warn(
                f"Unknown log level {level!r} used with _logger: its messages were logged as INFO, "
                "prefixed with the level. Use TRACE, DEBUG, INFO, HTML, CONSOLE, WARN, ERROR or IGNORE."
            )

# Backwards-compatible name: the class was called ParallelLibrary before the
# package was renamed to ParallelRunner (imported as `Library    ParallelRunner`).
ParallelLibrary = ParallelRunner
