"""Development tasks, run with `poetry run invoke <task>` (list them with `invoke --list`)."""

from pathlib import Path

from invoke import task

ROOT = Path(__file__).parent
RESULTS = ROOT / "robot_results"
DOCS = ROOT / "docs"


@task
def utest(c):
    """Run the pytest unit tests in utest/."""
    c.run("python -m pytest utest", pty=False)


@task
def atest(c):
    """Run the Robot Framework acceptance tests in atest/."""
    c.run(f"python -m robot --pythonpath . --outputdir {RESULTS} atest", pty=False)


@task(utest, atest)
def tests(c):
    """Run unit and acceptance tests."""


@task
def coverage(c):
    """Run all tests under coverage and write an HTML report to htmlcov/."""
    c.run("coverage erase")
    c.run("coverage run --source=src -p -m pytest utest")
    c.run(f"coverage run --source=src -p -m robot --pythonpath . --outputdir {RESULTS} atest")
    c.run("coverage combine")
    c.run("coverage report")
    c.run("coverage html")


@task
def libdoc(c):
    """Generate the keyword documentation into docs/ (published via GitHub Pages)."""
    c.run(f"python -m robot.libdoc --pythonpath src ParallelRunner {DOCS / 'ParallelRunner.html'}")


@task
def build(c):
    """Build the sdist and wheel into dist/."""
    c.run("poetry build")
