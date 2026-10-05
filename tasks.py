"""Development tasks, run with `poetry run invoke <task>` (list them with `invoke --list`)."""

import sys
import time
from pathlib import Path

from invoke import task

ROOT = Path(__file__).parent
RESULTS = ROOT / "robot_results"
DOCS = ROOT / "docs"
# Always use the interpreter invoke runs under, never whatever `python` is first
# on the PATH: with a plain `invoke` (no `poetry run`), that can be a different
# Python without the library installed.
PYTHON = f'"{sys.executable}"'


@task
def utest(c):
    """Run the pytest unit tests in utest/."""
    c.run(f"{PYTHON} -m pytest utest", pty=False)


@task
def atest(c):
    """Run the Robot Framework acceptance tests in atest/."""
    c.run(f'{PYTHON} -m robot --pythonpath . --outputdir "{RESULTS}" atest', pty=False)


@task(utest, atest)
def tests(c):
    """Run unit and acceptance tests."""


@task
def coverage(c):
    """Run all tests under coverage and write an HTML report to htmlcov/."""
    coverage = f"{PYTHON} -m coverage"
    c.run(f"{coverage} erase")
    c.run(f"{coverage} run --source=src -p -m pytest utest")
    c.run(f'{coverage} run --source=src -p -m robot --pythonpath . --outputdir "{RESULTS}" atest')
    c.run(f"{coverage} combine")
    c.run(f"{coverage} report")
    c.run(f"{coverage} html")


@task
def libdoc(c):
    """Generate the keyword documentation into docs/ (published via GitHub Pages)."""
    c.run(f'{PYTHON} -m robot.libdoc --pythonpath src ParallelRunner "{DOCS / "ParallelRunner.html"}"')


@task(help={"workers": "ROBOT_THREAD_WORKERS for the ParallelRunner runs (default 8).",
            "processes": "pabot --processes (default 4)."})
def demo_pabot(c, workers=8, processes=4):
    """Time examples/pabot_demo with robot vs pabot, with and without ParallelRunner."""
    suites = ROOT / "examples" / "pabot_demo" / "suites"
    out = RESULTS / "pabot_demo"
    # Hand pabot this exact interpreter, so it never picks up another `robot` from the PATH.
    pabot = f"{PYTHON} -m pabot.pabot --processes {processes} --command {PYTHON} -m robot --end-command"
    runs = [
        ("robot, sequential loop", f"{PYTHON} -m robot", "sequential"),
        (f"robot + ParallelRunner ({workers} workers)", f"{PYTHON} -m robot", "parallel"),
        (f"pabot ({processes} processes), sequential loop", pabot, "sequential"),
        (f"pabot ({processes} processes) + ParallelRunner ({workers} workers)", pabot, "parallel"),
    ]
    rows = []
    for index, (label, runner, mode) in enumerate(runs, start=1):
        start = time.perf_counter()
        result = c.run(
            f'{runner} --pythonpath . --variable MODE:{mode} --outputdir "{out / str(index)}" "{suites}"',
            env={"ROBOT_THREAD_WORKERS": str(workers)}, hide=True, warn=True, pty=False,
        )
        elapsed = time.perf_counter() - start
        rows.append((label, elapsed, "PASS" if result.ok else "FAIL"))
        print(f"{label}: {elapsed:.1f} s ({rows[-1][2]})")
    baseline = rows[0][1]
    print("\n| Run | Wall-clock time | Speedup |\n|---|---|---|")
    for label, elapsed, status in rows:
        print(f"| {label} | {elapsed:.1f} s | x{baseline / elapsed:.1f} |" + ("" if status == "PASS" else " FAILED |"))
    if any(status != "PASS" for _, _, status in rows):
        raise SystemExit("Some demo runs failed; see the results under " + str(out))


@task
def build(c):
    """Build the sdist and wheel into dist/."""
    c.run("poetry build")
