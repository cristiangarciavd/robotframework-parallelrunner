"""Test helper for suites that check what really ends up in the Robot log.

What `Run Parallel Scenarios` logs (and at which level), how Robot's
`--loglevel` filters it and what a `[Timeout]` does can't be checked from
inside the same run, so these keywords run a fixture suite from
`atest/_fixtures/` in a separate Robot process and read its output.xml.
`atest/_fixtures/` starts with an underscore, so `robot atest` (and pabot)
never run the fixtures directly.
"""

import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

from robot.api import ExecutionResult, ResultVisitor
from robot.libraries.BuiltIn import BuiltIn

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "atest" / "_fixtures"

# Messages Robot itself logs inside a keyword, not the threads.
_ROBOT_MESSAGES = re.compile(r"^(Arguments: |Return: |(Test|Keyword) timeout .* active\.)")


class _MessageCollector(ResultVisitor):
    def __init__(self):
        self.messages = []

    def visit_message(self, msg):
        self.messages.append(msg)


class _ParallelKeywordFinder(ResultVisitor):
    def __init__(self):
        self.keywords = []

    def start_keyword(self, keyword):
        # Robot 7: name is "Run Parallel Scenarios"; Robot 5/6: "ParallelRunner.Run Parallel Scenarios".
        if keyword.name.endswith("Run Parallel Scenarios"):
            self.keywords.append(keyword)


def _all_tests(suite):
    # `TestSuite.all_tests` only exists since Robot Framework 6.1.
    yield from suite.tests
    for child in suite.suites:
        yield from _all_tests(child)


def _elapsed_seconds(item) -> float:
    if hasattr(item, "elapsed_time"):  # Robot 7
        return item.elapsed_time.total_seconds()
    return item.elapsedtime / 1000


def _messages(item) -> List[Any]:
    collector = _MessageCollector()
    item.visit(collector)
    return collector.messages


class FixtureRunner:
    ROBOT_LIBRARY_SCOPE = "GLOBAL"

    def run_fixture_suite(self, name: str, *options: str, **environment: str) -> Dict[str, Any]:
        """Runs `atest/_fixtures/<name>.robot` in a new Robot process.

        `options` are extra robot command line options (e.g. `--loglevel`
        `TRACE`), `environment` extra environment variables. Returns a dict
        with `output` (output.xml path), `rc` and `elapsed` (seconds, the whole
        process, so it includes the time to exit).
        """
        output_dir = Path(BuiltIn().get_variable_value("${OUTPUT DIR}")) / "fixtures"
        label = "_".join([name] + [option.strip("-").lower() for option in options]) or name
        output = output_dir / f"{label}.xml"
        command = [
            sys.executable, "-m", "robot",
            "--pythonpath", str(ROOT),
            "--output", str(output),
            "--log", str(output_dir / f"{label}-log.html"),
            "--report", "NONE",
            "--console", "none",
            *options,
            str(FIXTURES / f"{name}.robot"),
        ]
        env = {**os.environ, **environment}
        start = time.monotonic()
        completed = subprocess.run(command, env=env, cwd=str(ROOT), timeout=300)
        return {"output": str(output), "rc": completed.returncode, "elapsed": time.monotonic() - start}

    def get_fixture_test(self, output: str, name: str) -> Dict[str, Any]:
        """Returns `status`, `message` and `elapsed` (seconds) of one test in
        a fixture's output.xml."""
        result = ExecutionResult(output)
        tests = [test for test in _all_tests(result.suite) if test.name == name]
        if not tests:
            raise AssertionError(f"No test '{name}' in {output}.")
        test = tests[0]
        return {"status": test.status, "message": test.message, "elapsed": _elapsed_seconds(test)}

    def get_thread_messages(self, output: str, name: str) -> List[str]:
        """Returns what `Run Parallel Scenarios` logged in test `name`, as
        `LEVEL message` strings (`HTML` for messages rendered as HTML), in
        order and without Robot's own argument/return/timeout/FAIL messages."""
        result = ExecutionResult(output)
        finder = _ParallelKeywordFinder()
        for test in _all_tests(result.suite):
            if test.name == name:
                test.visit(finder)
        if not finder.keywords:
            raise AssertionError(f"Test '{name}' in {output} has no 'Run Parallel Scenarios' keyword.")
        messages = []
        for keyword in finder.keywords:
            for msg in _messages(keyword):
                if msg.level != "FAIL" and not _ROBOT_MESSAGES.match(msg.message):
                    messages.append(f"{'HTML' if msg.html else msg.level} {msg.message}")
        return messages
