import os
import importlib
import inspect
import queue
import threading
import time
from typing import Iterable, Any, List, Dict, Optional, Tuple, Union
from robot.api import logger
from robot.errors import DataError
try:
    from robot.errors import TimeoutExceeded
except ImportError:  # Robot Framework < 7.0
    from robot.errors import TimeoutError as TimeoutExceeded
from robot.libraries.BuiltIn import BuiltIn
from robot.running.arguments import PythonArgumentParser
from robot.utils import secs_to_timestr, timestr_to_secs

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


def _normalize_name(name: str) -> str:
    """Keyword name comparison the way Robot does it: ignoring case, spaces and underscores."""
    return name.lower().replace(" ", "").replace("_", "")


def _not_given(value: Any) -> bool:
    """None, an empty string or "None" (any case - Robot's usual spelling of None)."""
    return value is None or (isinstance(value, str) and value.strip().upper() in ("", "NONE"))


# Who owns the result of a call that may time out: the worker that ran it, or
# the main thread that timed it out. See `ParallelRunner._run_in_threads`.
_WORKER, _MAIN = "worker", "main"
_NOT_SET = object()


def log_to_robot(msg: Any, level: str = "INFO") -> None:
    """Logs ``msg`` straight to Robot Framework, accepting the same levels as
    the ``_logger`` that `Run Parallel Scenarios` injects.

    Use it as the fallback when a parallel-ready keyword is called directly
    (without `Run Parallel Scenarios`)::

        from ParallelRunner import log_to_robot

        def verify_agent(self, agent_id, _logger=None):
            log = _logger or log_to_robot
            log("details", "DEBUG")

    Unlike ``robot.api.logger.write``, it accepts ``IGNORE`` (dropped), any
    case and Python ``logging`` names (``WARNING``), and logs a message with an
    unknown level at INFO, prefixed with the level, instead of failing.
    """
    name = _normalize_level(level)
    if name == "IGNORE":
        return
    if name is None:
        name, msg = "INFO", f"[{level}] {msg}"
    logger.write(msg, name)


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

    | from ParallelRunner import log_to_robot
    |
    | class MyLibrary:
    |     def verify_agent(self, agent_id: int, timeout: float = 10, _logger=None, **kwargs):
    |         log = _logger or log_to_robot
    |         log(f"Checking agent {agent_id}")
    |         ...
    |         return result

    ``_logger(msg, level)`` accepts every Robot Framework log level (see
    `Log levels`) plus ``IGNORE`` (dropped). ``log_to_robot`` is the fallback
    for when the keyword is called directly: it accepts the same levels
    (``robot.api.logger.write`` fails on ``IGNORE`` or ``WARNING``).

    Any extra named argument given to `Run Parallel Scenarios` is forwarded
    to every call as ``**kwargs``. Arguments are converted by the method's
    type hints (and default values) exactly as when the keyword is called
    directly: ``timeout=5`` arrives as the number ``5.0`` above. Items that
    are strings are converted the same way; other items (numbers, lists,
    dictionaries from a variable) are passed as they are.

    The keyword is found by its method name (``Verify Agent`` ->
    ``verify_agent``) or by a custom name given with ``@keyword("...")``,
    ignoring case, spaces and underscores, like Robot does.

    To be stoppable when it times out, the method can also declare a
    ``_cancelled`` parameter: see `Call timeouts and cancellation`.

    Logging is made thread-safe for you; your keyword's own side effects are
    not. Protect shared state (files, shared objects) with a lock.

    = Result format =

    `Run Parallel Scenarios` returns a list with one dictionary per call:

    | =Key=    | =Description= |
    | status   | ``PASS`` or ``FAIL``. |
    | item     | The item (or repeat index) the call received. |
    | logs     | List of ``(level, message)`` tuples captured during the call. |
    | result   | The return value of the call (only when ``status`` is ``PASS``). |
    | error    | The error message (only when ``status`` is ``FAIL``), e.g. ``Timed out after 10 seconds`` with ``call_timeout``. |

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
    runs) - unless they cooperate, see `Call timeouts and cancellation`.
    Calls that had not started yet are not started. The worker threads are
    daemon threads, so they never keep the Robot process alive after the run.
    A keyword that may hang (e.g. network I/O) should set its own timeouts
    (e.g. ``requests.get(url, timeout=10)``).

    A Robot timeout fails the whole test and can't be handled with
    `Run Keyword And Ignore Error`. To fail only the call that hangs, use
    ``call_timeout``.

    = Call timeouts and cancellation =

    ``call_timeout`` limits how long *each call* may run, e.g.
    ``call_timeout=10s`` (Robot's time format). A call still running after
    that becomes a failed call - error ``Timed out after 10 seconds``, with its
    partial logs - while the other calls keep running and finish normally. It
    is then reported like any other failed call: `Run Parallel Scenarios`
    fails with ``ParallelTaskError`` (which, unlike a Robot timeout, can be
    handled), or returns it with ``status`` ``FAIL`` when
    ``fail_on_error=False``.

    | ${results}= | Run Parallel Scenarios | keyword=Verify Agent | library=MyLibrary | for_loop_iterable=${agents} | call_timeout=10s | fail_on_error=False |

    The timed-out call can't be killed either: it keeps running in the
    background, and a new worker thread takes its place so the remaining
    calls still run ``ROBOT_THREAD_WORKERS`` at a time.

    A keyword that can stop early declares a ``_cancelled`` parameter.
    `Run Parallel Scenarios` then passes it a ``threading.Event`` that is set
    when that call times out, or when a Robot ``[Timeout]`` interrupts the
    batch. The keyword checks it between steps, or waits on it instead of
    sleeping:

    | def poll_job(self, job_id, _logger=None, _cancelled=None):
    |     while not job_done(job_id):
    |         if _cancelled is not None and _cancelled.wait(1):   # sleeps 1 s, wakes up if cancelled
    |             _logger(f"Stopped waiting for {job_id}", "WARN")
    |             return None

    ``_cancelled`` is only passed to methods that declare it by that name, so
    existing keywords keep working unchanged. It can't interrupt a call that
    is blocked in a single operation (a network request without a timeout).

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
    | ROBOT_THREAD_WORKERS   | Number of worker threads. Read when the library is imported. Default ``4``. An invalid value is ignored with a warning. |
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

    DEFAULT_WORKERS = 4

    def __init__(self):
        self.max_workers = self._workers_from_environment()

    def _workers_from_environment(self) -> int:
        """``ROBOT_THREAD_WORKERS``, or 4. An invalid value is ignored with a
        warning (it used to make the library import fail with a bare
        ``invalid literal for int()``)."""
        value = os.getenv("ROBOT_THREAD_WORKERS")
        if _not_given(value):
            return self.DEFAULT_WORKERS
        try:
            workers = int(value)
        except ValueError:
            workers = 0
        if workers < 1:
            logger.warn(
                f"Ignoring ROBOT_THREAD_WORKERS {value!r}: expected a whole number of at least 1. "
                f"Using {self.DEFAULT_WORKERS} workers."
            )
            return self.DEFAULT_WORKERS
        return workers

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
        call_timeout: Union[str, float, None] = None,
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
        - ``call_timeout``: Maximum time each call may run, in Robot's time
          format (``10s``, ``1 minute 30 seconds``, ``2.5``). A call still
          running after it fails with ``Timed out after ...`` while the other
          calls keep running; calls that declare ``_cancelled`` are told to
          stop. Not given (default): no limit. See
          `Call timeouts and cancellation`.
        - ``**kwargs``: Any other named argument is passed to every call,
          converted by the method's type hints like in a direct call.

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
        | ${results}=   | Run Parallel Scenarios | keyword=Verify Agent Data | library=MyLibrary       | for_loop_iterable=${agents} | call_timeout=30s |
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
        timeout_seconds = self._resolve_call_timeout(call_timeout)

        # Note: We must call the underlying Python method, not BuiltIn().run_keyword
        # because run_keyword is not thread-safe.
        lib_instance = self._get_library_instance_owning_keyword(keyword, library)
        method = self._get_keyword_method(lib_instance, keyword)

        results = self._run_in_threads(
            method, list(items), effective_mapper, remove_passing_logs, min_level, kwargs, timeout_seconds
        )

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
        lib_instance = BuiltIn().get_library_instance(library)
        if self._find_keyword_method(lib_instance, keyword_name) is not None:
            return lib_instance
        raise ValueError(f"Keyword '{keyword_name}' not found in library '{library}'")

    def _get_keyword_method(self, lib_instance: Any, keyword_name: str):
        method = self._find_keyword_method(lib_instance, keyword_name)
        if method is None:
            raise ValueError(f"Keyword '{keyword_name}' not found in library '{type(lib_instance).__name__}'")
        return method

    @staticmethod
    def _find_keyword_method(lib_instance: Any, keyword_name: str):
        """Finds the method implementing ``keyword_name``: by method name
        (``Verify Agent Data`` -> ``verify_agent_data``), or, like Robot
        itself, by a custom name given with ``@keyword("...")``. Names are
        compared ignoring case, spaces and underscores."""
        method = getattr(lib_instance, keyword_name.replace(" ", "_").lower(), None)
        if callable(method):
            return method
        wanted = _normalize_name(keyword_name)
        for attribute in dir(lib_instance):
            # getattr_static: don't run properties just to look at them.
            raw = inspect.getattr_static(lib_instance, attribute, None)
            function = raw.__func__ if isinstance(raw, (staticmethod, classmethod)) else raw
            robot_name = getattr(function, "robot_name", None)
            if robot_name is not None:
                matches = _normalize_name(robot_name) == wanted
            else:
                matches = not attribute.startswith("_") and _normalize_name(attribute) == wanted
            if matches and callable(getattr(lib_instance, attribute, None)):
                return getattr(lib_instance, attribute)
        return None

    def _resolve_thread_log_level(self, thread_log_level: Any) -> int:
        """Returns the numeric minimum level for ``thread_log_level``. Not
        given (None, empty, "None") means every level; an unknown value is
        ignored with a warning instead of silently filtering by INFO."""
        if _not_given(thread_log_level):
            return LOG_LEVELS["TRACE"]
        level = _normalize_level(thread_log_level)
        if level in LOG_LEVELS:
            return LOG_LEVELS[level]
        logger.warn(
            f"Ignoring thread_log_level {thread_log_level!r}: expected TRACE, DEBUG, INFO, WARN or ERROR. "
            "Replaying every level."
        )
        return LOG_LEVELS["TRACE"]

    @staticmethod
    def _resolve_call_timeout(call_timeout: Any) -> Optional[float]:
        """Returns ``call_timeout`` in seconds, or None when not given. Accepts
        Robot's time format (``10s``, ``1 minute 30 seconds``, ``1.5``)."""
        if _not_given(call_timeout):
            return None
        try:
            seconds = timestr_to_secs(call_timeout)
        except (ValueError, DataError) as error:
            raise ValueError(f"Invalid call_timeout {call_timeout!r}: {error}") from None
        if seconds <= 0:
            raise ValueError(f"call_timeout must be positive, got {call_timeout!r}.")
        return seconds

    @staticmethod
    def _converter_for(method):
        """Returns a function converting ``(positional, named)`` arguments by
        the method's type hints and default values, exactly like Robot does
        when the keyword is called directly - or None if Robot can't parse the
        method's signature (then arguments are passed as given)."""
        try:
            spec = PythonArgumentParser().parse(method)
        except Exception:
            return None
        return lambda positional, named: spec.convert(positional, named)

    @staticmethod
    def _accepts_cancel_event(method) -> bool:
        """``_cancelled`` is only passed to keywords that declare it, so that
        keywords with a fixed signature keep working."""
        try:
            return "_cancelled" in inspect.signature(method).parameters
        except (TypeError, ValueError):
            return False

    def _run_in_threads(
        self,
        method,
        items: List[Any],
        logger_mapper: Optional[Any],
        remove_passing_logs: bool,
        min_level: int,
        kwargs: Dict[str, Any],
        call_timeout: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """
        Runs ``method`` once per item on up to ``max_workers`` daemon threads
        and returns the result dicts in call order (NOT completion order).

        With ``call_timeout``, a call still running after that many seconds
        becomes a ``FAIL`` result: its thread is abandoned (it can't be
        killed) and a new worker takes its place, so the other calls keep
        running ``max_workers`` at a time.

        If the wait is interrupted (mostly by a Robot ``[Timeout]``), the
        workers stop starting new calls, the logs collected so far are
        replayed and the exception is re-raised. Calls already running can't
        be stopped: they finish in the background. The threads are daemon
        threads (unlike the ones of ``ThreadPoolExecutor``), so a call that
        never returns can't keep the Robot process alive at exit.
        """
        if self.max_workers < 1:
            raise ValueError(f"ROBOT_THREAD_WORKERS must be at least 1, got {self.max_workers}.")

        count = len(items)
        convert = self._converter_for(method)
        if convert is not None:
            # Once, before any thread starts: a bad named argument fails the
            # keyword instead of every call.
            kwargs = dict(convert([], list(kwargs.items()))[1])
        cancel_events = [threading.Event() for _ in items] if self._accepts_cancel_event(method) else None

        # Created here, not in the workers, so the logs of calls that are still
        # running can be replayed if the keyword is interrupted or times out.
        log_buffers: List[list] = [[] for _ in items]
        # Written by the workers. A worker writes `started_at[i]` when call i
        # starts and `finished[i]` when it has returned - unless the main
        # thread has timed the call out first. `claims` decides which of the
        # two wins: dict.setdefault is atomic, so the first claim sticks.
        started_at: List[Optional[float]] = [None] * count
        finished: List[Optional[Dict[str, Any]]] = [None] * count
        claims: Dict[int, str] = {}
        # Written by the main thread only.
        results: List[Optional[Dict[str, Any]]] = [None] * count

        # What each call receives as its first argument. Only strings are
        # converted (by the type hint, as when Robot calls the keyword with a
        # value from a test file); other objects are passed as they are. The
        # results keep the original item either way.
        arguments = list(items)
        pending = queue.SimpleQueue()
        for index, item in enumerate(items):
            if convert is not None and isinstance(item, str):
                try:
                    (arguments[index],), _ = convert([item], [])
                except Exception as error:
                    # Not worth starting: Robot would fail this call before running it, too.
                    message = str(error)
                    log_buffers[index].append(("ERROR", f"Thread failed for item {item}: {message}"))
                    started_at[index] = time.monotonic()
                    finished[index] = {"status": "FAIL", "item": item, "logs": log_buffers[index], "error": message}
                    continue
            pending.put(index)
        stop = threading.Event()
        workers_started = 0

        def worker():
            while not stop.is_set():
                try:
                    index = pending.get_nowait()
                except queue.Empty:
                    return
                call_kwargs = kwargs if cancel_events is None else {**kwargs, "_cancelled": cancel_events[index]}
                started_at[index] = time.monotonic()
                result = self._execute_and_capture(
                    method, items[index], logger_mapper, log_buffers[index], call_kwargs, arguments[index]
                )
                if claims.setdefault(index, _WORKER) != _WORKER:
                    # The call timed out and a new worker took this thread's
                    # place: stop here, so no more than max_workers calls run.
                    return
                finished[index] = result

        def start_worker():
            nonlocal workers_started
            workers_started += 1
            threading.Thread(target=worker, name=f"ParallelRunner-worker-{workers_started}", daemon=True).start()

        try:
            for _ in range(min(self.max_workers, count)):
                start_worker()
            # Deliberately no lock, Event or Future wait here: a timeout raised
            # asynchronously while such a wait holds an internal lock could
            # leave it locked forever. Short sleeps and plain reads are safe.
            remaining = count
            next_unstarted = 0
            running: List[int] = []
            while remaining:
                # Calls start in index order (FIFO queue), so started calls are
                # picked up by moving a pointer instead of scanning every slot.
                while next_unstarted < count and started_at[next_unstarted] is not None:
                    running.append(next_unstarted)
                    next_unstarted += 1
                now = time.monotonic()
                still_running = []
                for index in running:
                    if finished[index] is not None:
                        results[index] = finished[index]
                        remaining -= 1
                    elif (
                        call_timeout is not None
                        and now - started_at[index] >= call_timeout
                        and claims.setdefault(index, _MAIN) == _MAIN
                    ):
                        results[index] = self._timed_out_result(items[index], log_buffers[index], call_timeout)
                        remaining -= 1
                        if cancel_events is not None:
                            cancel_events[index].set()
                        if not pending.empty():
                            start_worker()
                    else:
                        still_running.append(index)
                running = still_running
                if remaining:
                    time.sleep(_POLL_INTERVAL)
        except BaseException as error:
            stop.set()
            if cancel_events is not None:
                for event in cancel_events:
                    event.set()
            self._replay_interrupted(
                items, results, finished, started_at, log_buffers, error, remove_passing_logs, min_level
            )
            raise
        return results

    @staticmethod
    def _timed_out_result(item, log_buffer: list, call_timeout: float) -> Dict[str, Any]:
        duration = secs_to_timestr(call_timeout)
        logs = list(log_buffer)
        logs.append(("ERROR", f"Call for item {item} timed out after {duration} (call_timeout); "
                              "it keeps running in the background"))
        return {"status": "FAIL", "item": item, "logs": logs, "error": f"Timed out after {duration}"}

    def _replay_interrupted(self, items, results, finished, started_at, log_buffers, error, remove_passing_logs, min_level):
        """Replays what the calls logged before the keyword was interrupted.
        Calls that never started are only counted, not listed one by one."""
        # On Windows Robot raises the timeout as a bare class, without message.
        reason = str(error) or ("Robot timeout exceeded" if isinstance(error, TimeoutExceeded) else type(error).__name__)
        partial = []
        running = not_started = 0
        for index, item in enumerate(items):
            # Read the results before `started_at`: a call that finishes in
            # between is then reported as still running, never as not started.
            result = results[index] or finished[index]
            if result is not None:
                partial.append(result)
            elif started_at[index] is not None:
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
        self, method, item, logger_mapper: Optional[Any], log_buffer: list, kwargs: Dict[str, Any],
        argument: Any = _NOT_SET,
    ) -> Dict[str, Any]:
        """Worker wrapper to capture logs and results.

        ``argument`` is what the call receives as its first argument (``item``
        converted by its type hint), ``item`` what the result reports. ``kwargs``
        is a dict, not ``**kwargs``, so a keyword argument that happens to be
        called ``method``, ``item`` or ``log_buffer`` can't clash with this
        method's own parameters.
        """
        if argument is _NOT_SET:
            argument = item
        # Injection of a custom logger into the thread
        def thread_log(msg, level="INFO"):
            # Filter out IGNORE (sv=0) level logs. Other levels are kept as
            # given and checked when the logs are replayed.
            if _normalize_level(level) != "IGNORE":
                log_buffer.append((level, msg))

        # Use mapper if provided, otherwise use thread_log
        effective_logger = logger_mapper if logger_mapper else thread_log

        try:
            result = method(argument, _logger=effective_logger, **kwargs)
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
