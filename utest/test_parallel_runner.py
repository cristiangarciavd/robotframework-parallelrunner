"""Unit tests for ParallelRunner, run without a Robot Framework execution context.

`BuiltIn().get_library_instance` only works while Robot is running, so the
library lookup is patched to return a plain Python object. Everything else
(thread pool, ordering, failure capture, log replay filtering) is the real code.
"""

import ctypes
import importlib
import random
import sys
import threading
import time
import types
import warnings

import pytest

import ParallelRunner as package
from ParallelRunner import ParallelLibrary, ParallelRunner, ParallelTaskError
from ParallelRunner import parallel_library
from ParallelRunner.parallel_library import TimeoutExceeded


class FakeLibrary:
    def echo_item(self, item, _logger=None, **kwargs):
        # Random sleeps make threads finish out of order, so ordering is really tested.
        time.sleep(random.uniform(0, 0.02))
        _logger(f"processing {item}")
        return {"item": item, **kwargs}

    def fail_on_two(self, item, _logger=None):
        if item == 2:
            raise ValueError("boom")
        return item

    def log_levels(self, item, _logger=None):
        _logger("info msg", "INFO")
        _logger("warn msg", "WARN")
        _logger("error msg", "ERROR")
        _logger("ignored msg", "IGNORE")

    def every_level(self, item, _logger=None):
        for level in ("TRACE", "DEBUG", "INFO", "HTML", "CONSOLE", "WARN", "ERROR"):
            _logger(f"{level.lower()} msg", level)

    def log_with(self, levels, _logger=None):
        for level in levels:
            _logger(f"msg at {level}", level)

    def default_level(self, item, _logger=None):
        _logger("no level given")

    def raise_system_exit(self, item, _logger=None):
        raise SystemExit("bye")

    def __init__(self):
        self.release = threading.Event()
        self.started = []
        self._lock = threading.Lock()
        self._running = 0
        self.max_running = 0

    def wait_seconds(self, seconds, _logger=None):
        """Runs for `seconds`, or until `release` is set (so tests never leave
        threads running for long). Tracks how many calls run at once."""
        with self._lock:
            self.started.append(seconds)
            self._running += 1
            self.max_running = max(self.max_running, self._running)
        _logger(f"start {seconds}")
        self.release.wait(float(seconds))
        _logger(f"end {seconds}")
        with self._lock:
            self._running -= 1
        return seconds


class RecordingLogger:
    def __init__(self):
        self.messages = []

    def info(self, msg):
        self.messages.append(("INFO", msg))

    def warn(self, msg):
        self.messages.append(("WARN", msg))

    def error(self, msg):
        self.messages.append(("ERROR", msg))

    def write(self, msg, level, html=False):
        # Like robot.api.logger.write: an invalid level is an error, not a no-op.
        assert level in parallel_library.LOG_LEVELS, f"invalid level {level!r} passed to logger.write"
        self.messages.append((level, msg))


@pytest.fixture
def fake_library():
    library = FakeLibrary()
    yield library
    # Let calls a test left running in the background finish right away.
    library.release.set()


@pytest.fixture
def runner(monkeypatch, fake_library):
    lib = ParallelRunner()
    monkeypatch.setattr(lib, "_get_library_instance_owning_keyword", lambda keyword, library: fake_library)
    return lib


@pytest.fixture
def robot_logger(monkeypatch):
    recorder = RecordingLogger()
    monkeypatch.setattr(parallel_library, "logger", recorder)
    return recorder


def test_results_are_in_call_order_not_completion_order(runner, robot_logger):
    items = list(range(20))
    results = runner.run_parallel_scenarios("Echo Item", "Fake", for_loop_iterable=items)
    assert [r["item"] for r in results] == items
    assert all(r["status"] == "PASS" for r in results)


def test_kwargs_are_forwarded_to_every_call(runner, robot_logger):
    values = runner.run_parallel_scenarios("Echo Item", "Fake", repeat=3, return_values_only=True, prefix="x")
    assert values == ({"item": 0, "prefix": "x"}, {"item": 1, "prefix": "x"}, {"item": 2, "prefix": "x"})


@pytest.mark.parametrize(
    "kwargs, expected_items",
    [
        ({}, [0]),
        ({"repeat": 0}, []),
        ({"repeat": 4}, [0, 1, 2, 3]),
        ({"for_loop_iterable": ["a", "b"], "repeat": 10}, ["a", "b"]),
    ],
)
def test_items_selection(runner, robot_logger, kwargs, expected_items):
    results = runner.run_parallel_scenarios("Echo Item", "Fake", **kwargs)
    assert [r["item"] for r in results] == expected_items


def test_failed_call_fails_the_keyword_by_default(runner, robot_logger):
    with pytest.raises(ParallelTaskError) as error:
        runner.run_parallel_scenarios("Fail On Two", "Fake", for_loop_iterable=[1, 2, 3])
    assert str(error.value) == "1 of 3 parallel task(s) failed: item=2: boom"
    assert [entry["item"] for entry in error.value.failures] == [2]


def test_every_call_finishes_and_is_logged_before_failing(runner, robot_logger):
    with pytest.raises(ParallelTaskError):
        runner.run_parallel_scenarios("Fail On Two", "Fake", for_loop_iterable=[1, 2, 3])
    replayed = [msg for _, msg in robot_logger.messages]
    assert replayed.count("Status: PASS") == 2
    assert replayed.count("Status: FAIL") == 1
    assert ("ERROR", "Thread failed for item 2: boom") in robot_logger.messages


def test_all_failures_are_listed_in_call_order(runner, robot_logger):
    with pytest.raises(ParallelTaskError) as error:
        runner.run_parallel_scenarios("Fail On Two", "Fake", for_loop_iterable=[2, 1, 2])
    assert str(error.value).startswith("2 of 3 parallel task(s) failed")
    assert len(error.value.failures) == 2


def test_fail_on_error_false_returns_failed_calls_as_results(runner, robot_logger):
    results = runner.run_parallel_scenarios("Fail On Two", "Fake", for_loop_iterable=[1, 2, 3], fail_on_error=False)
    assert [r["status"] for r in results] == ["PASS", "FAIL", "PASS"]
    assert results[1]["error"] == "boom"
    assert "result" not in results[1]
    assert ("ERROR", "Thread failed for item 2: boom") in robot_logger.messages


def test_fail_on_error_is_not_forwarded_to_the_keyword(runner, robot_logger):
    values = runner.run_parallel_scenarios("Echo Item", "Fake", repeat=1, fail_on_error=False, return_values_only=True)
    assert values == ({"item": 0},)


@pytest.mark.parametrize("fail_on_error", [True, False])
def test_return_values_only_raises_when_any_call_failed(runner, robot_logger, fail_on_error):
    with pytest.raises(ParallelTaskError) as error:
        runner.run_parallel_scenarios(
            "Fail On Two", "Fake", for_loop_iterable=[1, 2, 3], return_values_only=True, fail_on_error=fail_on_error
        )
    assert len(error.value.failures) == 1
    assert "1 of 3 parallel task(s) failed" in str(error.value)


def test_get_result_values_preserves_order():
    results = [{"status": "PASS", "item": i, "logs": [], "result": i * 10} for i in range(3)]
    assert ParallelRunner().get_result_values(results) == (0, 10, 20)


def test_replay_filters_by_thread_log_level(runner, robot_logger):
    runner.run_parallel_scenarios("Log Levels", "Fake", thread_log_level="WARN")
    levels = [msg for level, msg in robot_logger.messages if not msg.startswith(("---", "Status:"))]
    assert levels == ["warn msg", "error msg"]


def test_remove_passing_logs_skips_passing_calls(runner, robot_logger):
    runner.run_parallel_scenarios(
        "Fail On Two", "Fake", for_loop_iterable=[1, 2], remove_passing_logs=True, fail_on_error=False
    )
    replayed = " ".join(msg for _, msg in robot_logger.messages)
    assert "Item: 1" not in replayed
    assert "Item: 2" in replayed


class RecordingMapper:
    """A logger mapper that just remembers what it was called with (thread-safe enough for list.append)."""

    def __init__(self):
        self.calls = []

    def __call__(self, msg, level="INFO"):
        self.calls.append((level, msg))


@pytest.fixture
def mapper_module(monkeypatch):
    """An importable module `fake_mappers` with a `record` mapper, for module.function paths."""
    module = types.ModuleType("fake_mappers")
    module.record = RecordingMapper()
    module.not_callable = "just a string"
    monkeypatch.setitem(sys.modules, "fake_mappers", module)
    monkeypatch.delenv("ROBOT_LOGGER_MAPPER", raising=False)
    return module


def warnings_logged(robot_logger):
    return [msg for level, msg in robot_logger.messages if level == "WARN"]


def test_logger_mapper_resolution(robot_logger, mapper_module):
    lib = ParallelRunner()
    assert lib._resolve_mapper(print) is print
    assert lib._resolve_mapper("os.path.join") is __import__("os").path.join
    assert lib._resolve_mapper("fake_mappers.record") is mapper_module.record
    assert warnings_logged(robot_logger) == []


@pytest.mark.parametrize("value", [None, "", "   ", "None", "NONE", "none"])
def test_missing_mapper_is_silently_none(robot_logger, value):
    assert ParallelRunner()._resolve_mapper(value) is None
    assert warnings_logged(robot_logger) == []


@pytest.mark.parametrize(
    "value, reason",
    [
        ("custom_logger_adapter", "expected a 'module.function' path"),
        ("os.", "expected a 'module.function' path"),
        (".record", "expected a 'module.function' path"),
        ("no.such.module.func", "cannot import module 'no.such.module'"),
        ("fake_mappers.missing", "module 'fake_mappers' has no callable 'missing'"),
        ("fake_mappers.not_callable", "module 'fake_mappers' has no callable 'not_callable'"),
        (42, "expected a callable or a 'module.function' string, got int"),
    ],
)
def test_unresolvable_mapper_is_ignored_with_a_warning(robot_logger, mapper_module, value, reason):
    assert ParallelRunner()._resolve_mapper(value) is None
    (warning,) = warnings_logged(robot_logger)
    assert f"Ignoring logger_mapper {value!r}" in warning
    assert reason in warning


def test_explicit_mapper_receives_the_logs_instead_of_the_buffer(runner, robot_logger, mapper_module):
    results = runner.run_parallel_scenarios(
        "Echo Item", "Fake", for_loop_iterable=[1, 2, 3], logger_mapper="fake_mappers.record"
    )
    assert sorted(mapper_module.record.calls) == [("INFO", "processing 1"), ("INFO", "processing 2"), ("INFO", "processing 3")]
    assert all(entry["logs"] == [] for entry in results)


def test_environment_mapper_path_is_used(runner, robot_logger, mapper_module, monkeypatch):
    monkeypatch.setenv("ROBOT_LOGGER_MAPPER", "fake_mappers.record")
    results = runner.run_parallel_scenarios("Echo Item", "Fake", repeat=2)
    assert len(mapper_module.record.calls) == 2
    assert all(entry["logs"] == [] for entry in results)
    assert warnings_logged(robot_logger) == []


def test_environment_bare_name_warns_and_falls_back_to_buffered_logs(runner, robot_logger, mapper_module, monkeypatch):
    monkeypatch.setenv("ROBOT_LOGGER_MAPPER", "custom_logger_adapter")
    results = runner.run_parallel_scenarios("Echo Item", "Fake", repeat=2)
    (warning,) = warnings_logged(robot_logger)
    assert "Ignoring ROBOT_LOGGER_MAPPER 'custom_logger_adapter'" in warning
    assert [entry["logs"] for entry in results] == [[("INFO", "processing 0")], [("INFO", "processing 1")]]


def test_explicit_mapper_wins_over_environment(runner, robot_logger, mapper_module, monkeypatch):
    env_mapper = RecordingMapper()
    mapper_module.env_record = env_mapper
    monkeypatch.setenv("ROBOT_LOGGER_MAPPER", "fake_mappers.env_record")
    runner.run_parallel_scenarios("Echo Item", "Fake", repeat=2, logger_mapper=mapper_module.record)
    assert len(mapper_module.record.calls) == 2
    assert env_mapper.calls == []


def test_unresolvable_explicit_mapper_falls_back_to_environment(runner, robot_logger, mapper_module, monkeypatch):
    monkeypatch.setenv("ROBOT_LOGGER_MAPPER", "fake_mappers.record")
    runner.run_parallel_scenarios("Echo Item", "Fake", repeat=2, logger_mapper="typo_name")
    assert len(mapper_module.record.calls) == 2
    (warning,) = warnings_logged(robot_logger)
    assert "Ignoring logger_mapper 'typo_name'" in warning


def test_workers_come_from_environment(monkeypatch):
    monkeypatch.setenv("ROBOT_THREAD_WORKERS", "7")
    assert ParallelRunner().max_workers == 7


def test_library_metadata():
    assert ParallelRunner.ROBOT_LIBRARY_SCOPE == "GLOBAL"
    assert ParallelRunner.ROBOT_LIBRARY_VERSION == package.__version__
    assert ParallelLibrary is ParallelRunner


def test_deprecated_import_path_still_works():
    sys.modules.pop("parallelrunner", None)
    sys.modules.pop("parallelrunner.parallel_library", None)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        legacy = importlib.import_module("parallelrunner.parallel_library")
    assert legacy.ParallelLibrary is ParallelRunner
    assert any(issubclass(w.category, DeprecationWarning) for w in caught)


# --- Log levels (0.3.1: DEBUG/TRACE/HTML/CONSOLE used to be dropped silently) ---


def replayed(robot_logger):
    """The thread messages that were replayed, without the per-item header and status lines."""
    return [(level, msg) for level, msg in robot_logger.messages if not msg.startswith(("---", "Status:"))]


def test_every_robot_level_is_replayed_by_default(runner, robot_logger):
    runner.run_parallel_scenarios("Every Level", "Fake")
    assert replayed(robot_logger) == [
        ("TRACE", "trace msg"),
        ("DEBUG", "debug msg"),
        ("INFO", "info msg"),
        ("HTML", "html msg"),
        ("CONSOLE", "console msg"),
        ("WARN", "warn msg"),
        ("ERROR", "error msg"),
    ]


@pytest.mark.parametrize(
    "thread_log_level, expected",
    [
        ("TRACE", ["TRACE", "DEBUG", "INFO", "HTML", "CONSOLE", "WARN", "ERROR"]),
        ("DEBUG", ["DEBUG", "INFO", "HTML", "CONSOLE", "WARN", "ERROR"]),
        ("INFO", ["INFO", "HTML", "CONSOLE", "WARN", "ERROR"]),
        ("debug", ["DEBUG", "INFO", "HTML", "CONSOLE", "WARN", "ERROR"]),
        ("WARNING", ["WARN", "ERROR"]),
        ("ERROR", ["ERROR"]),
    ],
)
def test_thread_log_level_is_a_minimum_over_every_level(runner, robot_logger, thread_log_level, expected):
    runner.run_parallel_scenarios("Every Level", "Fake", thread_log_level=thread_log_level)
    assert [level for level, _ in replayed(robot_logger)] == expected


def test_levels_are_case_insensitive_and_accept_python_logging_names(runner, robot_logger):
    levels = ["debug", "Info", "warn", "WARNING", "Critical", "fatal", " error "]
    runner.run_parallel_scenarios("Log With", "Fake", for_loop_iterable=[levels])
    assert [level for level, _ in replayed(robot_logger)] == ["DEBUG", "INFO", "WARN", "WARN", "ERROR", "ERROR", "ERROR"]


def test_default_message_level_is_info(runner, robot_logger):
    runner.run_parallel_scenarios("Default Level", "Fake")
    assert replayed(robot_logger) == [("INFO", "no level given")]


@pytest.mark.parametrize("ignore", ["IGNORE", "ignore", "Ignore"])
def test_ignore_is_dropped_in_any_case(runner, robot_logger, ignore):
    (result,) = runner.run_parallel_scenarios("Log With", "Fake", for_loop_iterable=[[ignore, "INFO"]])
    assert result["logs"] == [("INFO", "msg at INFO")]
    assert replayed(robot_logger) == [("INFO", "msg at INFO")]


def test_unknown_level_is_kept_at_info_with_one_warning_per_level(runner, robot_logger):
    runner.run_parallel_scenarios("Log With", "Fake", for_loop_iterable=[["VERBOSE", "VERBOSE", "sv=2", "INFO"]])
    assert replayed(robot_logger)[:4] == [
        ("INFO", "[VERBOSE] msg at VERBOSE"),
        ("INFO", "[VERBOSE] msg at VERBOSE"),
        ("INFO", "[sv=2] msg at sv=2"),
        ("INFO", "msg at INFO"),
    ]
    warnings = warnings_logged(robot_logger)
    assert len(warnings) == 2
    assert "Unknown log level 'VERBOSE'" in warnings[0]
    assert "Unknown log level 'sv=2'" in warnings[1]


def test_unknown_level_counts_as_info_for_thread_log_level(runner, robot_logger):
    runner.run_parallel_scenarios("Log With", "Fake", for_loop_iterable=[["VERBOSE", "WARN"]], thread_log_level="WARN")
    (warning,) = [msg for msg in warnings_logged(robot_logger) if msg.startswith("Unknown")]
    assert replayed(robot_logger) == [("WARN", "msg at WARN"), ("WARN", warning)]


def test_invalid_thread_log_level_warns_and_replays_everything(runner, robot_logger):
    runner.run_parallel_scenarios("Every Level", "Fake", thread_log_level="LOUD")
    warning = warnings_logged(robot_logger)[0]
    assert "Ignoring thread_log_level 'LOUD'" in warning
    assert len([m for m in replayed(robot_logger) if m[1] != warning]) == 7


@pytest.mark.parametrize("value", [None, "", "None", "NONE"])
def test_missing_thread_log_level_replays_everything_silently(runner, robot_logger, value):
    runner.run_parallel_scenarios("Every Level", "Fake", thread_log_level=value)
    assert warnings_logged(robot_logger) == ["warn msg"]
    assert len(replayed(robot_logger)) == 7


def test_mapper_receives_levels_untouched(runner, robot_logger):
    mapper = RecordingMapper()
    runner.run_parallel_scenarios(
        "Log With", "Fake", for_loop_iterable=[["debug", "TRACE", "VERBOSE"]], logger_mapper=mapper
    )
    assert mapper.calls == [("debug", "msg at debug"), ("TRACE", "msg at TRACE"), ("VERBOSE", "msg at VERBOSE")]
    assert replayed(robot_logger) == []


# --- Thread pool ---


def test_never_more_calls_at_once_than_workers(runner, robot_logger, fake_library):
    runner.max_workers = 3
    runner.run_parallel_scenarios("Wait Seconds", "Fake", for_loop_iterable=[0.05] * 12)
    assert fake_library.max_running == 3


def started_threads(monkeypatch):
    """Records (name, daemon) of every thread started from now on."""
    seen = []
    original_start = threading.Thread.start

    def recording_start(thread):
        seen.append((thread.name, thread.daemon))
        original_start(thread)

    monkeypatch.setattr(threading.Thread, "start", recording_start)
    return seen


def test_workers_are_named_daemon_threads(runner, robot_logger, monkeypatch):
    seen = started_threads(monkeypatch)
    runner.max_workers = 2
    runner.run_parallel_scenarios("Echo Item", "Fake", repeat=5)
    assert seen == [("ParallelRunner-worker-1", True), ("ParallelRunner-worker-2", True)]


def test_no_more_threads_than_items(runner, robot_logger, monkeypatch):
    seen = started_threads(monkeypatch)
    runner.max_workers = 8
    runner.run_parallel_scenarios("Echo Item", "Fake", repeat=2)
    runner.run_parallel_scenarios("Echo Item", "Fake", repeat=0)
    assert len(seen) == 2


def test_generator_items_are_consumed_once(runner, robot_logger):
    results = runner.run_parallel_scenarios("Echo Item", "Fake", for_loop_iterable=(i * 2 for i in range(5)))
    assert [r["item"] for r in results] == [0, 2, 4, 6, 8]


@pytest.mark.parametrize("workers", [0, -1])
def test_less_than_one_worker_is_an_error(runner, robot_logger, workers):
    runner.max_workers = workers
    with pytest.raises(ValueError, match="ROBOT_THREAD_WORKERS must be at least 1"):
        runner.run_parallel_scenarios("Echo Item", "Fake", repeat=1)


def test_base_exception_in_a_call_is_a_failed_call_not_a_hang(runner, robot_logger):
    with pytest.raises(ParallelTaskError, match="item=0: bye"):
        runner.run_parallel_scenarios("Raise System Exit", "Fake")


def test_kwargs_named_like_internal_parameters_are_forwarded(runner, robot_logger):
    (value,) = runner.run_parallel_scenarios(
        "Echo Item", "Fake", return_values_only=True, method="m", log_buffer="b", kwargs="k"
    )
    assert value == {"item": 0, "method": "m", "log_buffer": "b", "kwargs": "k"}


# --- Interruption: Robot [Timeout] (0.3.1: used to wait for the whole batch) ---


def interrupt_main_thread(after, error=TimeoutExceeded):
    """Raises `error` in the calling thread after `after` seconds, the way Robot
    Framework's Windows timeout does: PyThreadState_SetAsyncExc, delivered only
    while the thread runs Python code. Returns the timer, to cancel it."""
    thread_id = threading.get_ident()

    def fire():
        ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_ulong(thread_id), ctypes.py_object(error))

    timer = threading.Timer(after, fire)
    timer.daemon = True
    timer.start()
    return timer


def run_interrupted(runner, error=TimeoutExceeded, **kwargs):
    """Runs `Wait Seconds` and interrupts it after 0.3 s. Returns the elapsed time."""
    timer = interrupt_main_thread(0.3, error)
    start = time.monotonic()
    try:
        with pytest.raises(error):
            runner.run_parallel_scenarios("Wait Seconds", "Fake", **kwargs)
    finally:
        timer.cancel()
    return time.monotonic() - start


UNFINISHED_30 = "Call for item 30 did not finish: still running when the keyword was interrupted (Robot timeout exceeded)"


def test_timeout_interrupts_the_keyword_right_away(runner, robot_logger):
    elapsed = run_interrupted(runner, for_loop_iterable=[0.01, 30, 30])
    assert elapsed < 2, f"took {elapsed:.1f}s: the keyword waited for the calls instead of being interrupted"


def test_timeout_replays_finished_and_partial_logs(runner, robot_logger):
    runner.max_workers = 2
    run_interrupted(runner, for_loop_iterable=[0.01, 30, 30, 30])
    messages = robot_logger.messages
    (summary,) = [msg for _, msg in messages if msg.startswith("Run Parallel Scenarios was interrupted")]
    assert summary == (
        "Run Parallel Scenarios was interrupted (Robot timeout exceeded): "
        "1 call(s) finished, 2 still running (left running in the background), 1 not started."
    )
    replay = [msg for _, msg in messages[messages.index(("INFO", summary)) + 1:]]
    assert replay == [
        "--- Logs for Item: 0.01 ---", "start 0.01", "end 0.01", "Status: PASS",
        "--- Logs for Item: 30 ---", "start 30", UNFINISHED_30, "Status: FAIL",
        "--- Logs for Item: 30 ---", "start 30", UNFINISHED_30, "Status: FAIL",
    ]
    assert messages.count(("ERROR", UNFINISHED_30)) == 2


def test_timeout_stops_starting_new_calls(runner, robot_logger, fake_library):
    runner.max_workers = 2
    run_interrupted(runner, for_loop_iterable=[30] * 10)
    fake_library.release.set()
    time.sleep(0.2)
    assert fake_library.started == [30, 30]


def test_timeout_replay_honours_remove_passing_logs_and_level(runner, robot_logger):
    run_interrupted(runner, for_loop_iterable=[0.01, 30], remove_passing_logs=True, thread_log_level="ERROR")
    replay = [msg for _, msg in robot_logger.messages if not msg.startswith("Run Parallel")]
    assert replay == ["--- Logs for Item: 30 ---", UNFINISHED_30, "Status: FAIL"]


def test_timeout_with_a_mapper_still_reports_the_unfinished_calls(runner, robot_logger):
    """A mapper's messages are not buffered, so there are no partial logs to
    replay - but the unfinished call is still reported."""
    mapper = RecordingMapper()
    run_interrupted(runner, for_loop_iterable=[0.01, 30], logger_mapper=mapper)
    assert ("INFO", "start 30") in mapper.calls
    replay = [msg for _, msg in robot_logger.messages if not msg.startswith("Run Parallel")]
    assert replay == [
        "--- Logs for Item: 0.01 ---", "Status: PASS",
        "--- Logs for Item: 30 ---", UNFINISHED_30, "Status: FAIL",
    ]


def test_other_interruptions_name_the_exception(runner, robot_logger):
    run_interrupted(runner, error=KeyboardInterrupt, for_loop_iterable=[30])
    assert any("was interrupted (KeyboardInterrupt)" in msg for _, msg in robot_logger.messages)
