"""Unit tests for ParallelRunner, run without a Robot Framework execution context.

`BuiltIn().get_library_instance` only works while Robot is running, so the
library lookup is patched to return a plain Python object. Everything else
(thread pool, ordering, failure capture, log replay filtering) is the real code.
"""

import importlib
import random
import sys
import time
import warnings

import pytest

import ParallelRunner as package
from ParallelRunner import ParallelLibrary, ParallelRunner, ParallelTaskError
from ParallelRunner import parallel_library


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


class RecordingLogger:
    def __init__(self):
        self.messages = []

    def info(self, msg):
        self.messages.append(("INFO", msg))

    def warn(self, msg):
        self.messages.append(("WARN", msg))

    def error(self, msg):
        self.messages.append(("ERROR", msg))


@pytest.fixture
def runner(monkeypatch):
    lib = ParallelRunner()
    monkeypatch.setattr(lib, "_get_library_instance_owning_keyword", lambda keyword, library: FakeLibrary())
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


def test_failed_call_is_captured_not_raised(runner, robot_logger):
    results = runner.run_parallel_scenarios("Fail On Two", "Fake", for_loop_iterable=[1, 2, 3])
    assert [r["status"] for r in results] == ["PASS", "FAIL", "PASS"]
    assert results[1]["error"] == "boom"
    assert "result" not in results[1]


def test_return_values_only_raises_when_any_call_failed(runner, robot_logger):
    with pytest.raises(ParallelTaskError) as error:
        runner.run_parallel_scenarios("Fail On Two", "Fake", for_loop_iterable=[1, 2, 3], return_values_only=True)
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
    runner.run_parallel_scenarios("Fail On Two", "Fake", for_loop_iterable=[1, 2], remove_passing_logs=True)
    replayed = " ".join(msg for _, msg in robot_logger.messages)
    assert "Item: 1" not in replayed
    assert "Item: 2" in replayed


def test_logger_mapper_resolution():
    lib = ParallelRunner()
    assert lib._resolve_mapper(None) is None
    assert lib._resolve_mapper(print) is print
    assert lib._resolve_mapper("os.path.join") is __import__("os").path.join
    assert lib._resolve_mapper("no.such.module.func") is None


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
