import os
import concurrent.futures
import importlib
from typing import Iterable, Any, List, Dict, Optional, Tuple, Union
from robot.api import logger
from robot.libraries.BuiltIn import BuiltIn

from .version import __version__


class ParallelTaskError(RuntimeError):
    """
    Raised when at least one parallel task failed and there is no meaningful
    return value to hand back for it - by ``get_result_values``, and by
    ``run_parallel_scenarios`` when called with ``return_values_only=True``.

    Silently substituting `None` for a failed task's value would let a test
    keep going with bad data instead of failing for the right reason, so
    this is raised instead.

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

    - Each call runs on a worker thread of a ``ThreadPoolExecutor``.
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

    ``_logger(msg, level)`` accepts the levels ``INFO``, ``WARN``, ``ERROR``
    and ``IGNORE`` (dropped). Any extra named argument given to
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

    A failing call does *not* fail the keyword; check ``status`` yourself,
    or use ``return_values_only=True`` / `Get Result Values`, which fail
    if any call failed.

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
        thread_log_level: str = "INFO",
        logger_mapper: Optional[Any] = None,
        return_values_only: bool = False,
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
          ``INFO`` (default), ``WARN`` or ``ERROR``.
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
        - ``**kwargs``: Any other named argument is passed to every call.

        Returns a list of result dictionaries (see `Result format`), in call
        order: entry ``i`` belongs to ``for_loop_iterable[i]`` / repeat
        index ``i``, regardless of which thread finished first.

        Examples:
        | ${agents}=    | Create List            | 1                         | 2                       | 3 |
        | ${results}=   | Run Parallel Scenarios | keyword=Verify Agent Data | library=MyLibrary       | for_loop_iterable=${agents} |
        | ${results}=   | Run Parallel Scenarios | keyword=Check Health      | library=MyLibrary       | repeat=8 | agent_id=1 |
        | ${id1}    ${id2}    ${id3}= | Run Parallel Scenarios | keyword=Seed Record | library=MyLibrary | repeat=3 | return_values_only=True |
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

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # We map the execution.
            # Note: We must call the underlying Python method, not BuiltIn().run_keyword
            # because run_keyword is not thread-safe.
            lib_instance = self._get_library_instance_owning_keyword(keyword, library)
            method = getattr(lib_instance, keyword.replace(" ", "_").lower())

            # Submit every task up front so they all start running concurrently,
            # then collect results in submission order (NOT as_completed order) -
            # tasks[i].result() blocks only until the i-th task finishes, it
            # doesn't force tasks to run one at a time.
            tasks = [
                executor.submit(self._execute_and_capture, method, item, effective_mapper, **kwargs)
                for item in items
            ]
            results = [task.result() for task in tasks]

        # Step: Re-play logs into Robot Framework sequentially
        self._replay_logs(results, remove_passing_logs, thread_log_level)

        if return_values_only:
            return self.get_result_values(results)
        return results

    def get_result_values(self, results: List[Dict[str, Any]]) -> Tuple[Any, ...]:
        """Returns the return value of every call in ``results``, as a tuple in call order.

        ``results`` is the list returned by `Run Parallel Scenarios`.
        ``results[i]`` becomes tuple index ``i``.

        Passing ``return_values_only=True`` to `Run Parallel Scenarios` does
        the same in one step; use this keyword when you want to inspect the
        full results first (e.g. assert on ``status`` or ``logs``).

        Fails with ``ParallelTaskError`` if any entry has status ``FAIL`` -
        a failed call has no return value to put in its slot.

        Example:
        | ${results}=                 | Run Parallel Scenarios | keyword=Seed Record | library=MyLibrary | repeat=3 |
        | ${id1}    ${id2}    ${id3}= | Get Result Values      | ${results}          |
        """
        failures = [entry for entry in results if entry.get("status") == "FAIL"]
        if failures:
            raise ParallelTaskError(failures, len(results))
        return tuple(entry["result"] for entry in results)

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
            mapper: Callable, ``module.function`` string, or None / empty string.
            source: Where the value came from, used in the warning message.
        """
        if mapper is None or (isinstance(mapper, str) and not mapper.strip()):
            return None

        if callable(mapper):
            return mapper

        if isinstance(mapper, str):
            module_name, _, func_name = mapper.strip().rpartition(".")
            if not module_name:
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

    def _execute_and_capture(self, method, item, logger_mapper: Optional[Any] = None, **kwargs) -> Dict[str, Any]:
        """Worker wrapper to capture logs and results."""
        log_buffer = []
        
        # Injection of a custom logger into the thread
        def thread_log(msg, level="INFO"):
            # Filter out IGNORE (sv=0) level logs
            if level != "IGNORE":
                log_buffer.append((level, msg))
        
        # Use mapper if provided, otherwise use thread_log
        effective_logger = logger_mapper if logger_mapper else thread_log

        try:
            # We pass the custom logger as an extra kwarg if the method supports it
            # or rely on the method returning its own logs.
            result = method(item, _logger=effective_logger, **kwargs)
            return {"status": "PASS", "item": item, "logs": log_buffer, "result": result}
        except Exception as e:
            thread_log(f"Thread failed for item {item}: {str(e)}", "ERROR")
            return {"status": "FAIL", "item": item, "logs": log_buffer, "error": str(e)}

    def _replay_logs(self, results: List[Dict[str, Any]], remove_passing_logs: bool = False, thread_log_level: str = "INFO"):
        """Sequential dump to the real RF Logger. Filters out IGNORE level logs."""
        level_order = {"INFO": 1, "WARN": 2, "ERROR": 3}
        min_level = level_order.get(thread_log_level, 1)
        for entry in results:
            if remove_passing_logs and entry['status'] == 'PASS':
                continue
            logger.info(f"--- Logs for Item: {entry['item']} ---")
            for level, msg in entry['logs']:
                # Skip IGNORE level and logs below minimum level
                if level == "IGNORE" or level_order.get(level, 1) < min_level:
                    continue
                if level == "INFO": logger.info(msg)
                elif level == "WARN": logger.warn(msg)
                elif level == "ERROR": logger.error(msg)
            logger.info(f"Status: {entry['status']}")

# Backwards-compatible name: the class was called ParallelLibrary before the
# package was renamed to ParallelRunner (imported as `Library    ParallelRunner`).
ParallelLibrary = ParallelRunner
