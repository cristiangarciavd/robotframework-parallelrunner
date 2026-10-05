# Installation

## Requirements

- Python >= 3.9
- [Robot Framework](https://robotframework.org/) >= 5.0 (installed automatically as a dependency)

## Install from PyPI

```bash
pip install robotframework-parallelrunner
```

Upgrade to the latest release:

```bash
pip install --upgrade robotframework-parallelrunner
```

Then import it in a suite:

```robot
*** Settings ***
Library    ParallelRunner
```

Keyword documentation:
<https://cristiangarciavd.github.io/robotframework-parallelrunner/ParallelRunner.html>

## Verify the install

```bash
python -c "import ParallelRunner; print(ParallelRunner.__version__)"
python -m robot.libdoc ParallelRunner list
```

## Upgrading from the pre-release import path

Before 0.2.0 the library was imported as
`parallelrunner.parallel_library.ParallelLibrary`. That path still works but
emits a `DeprecationWarning` and will be removed in a future release. Replace:

```robot
Library    parallelrunner.parallel_library.ParallelLibrary
```

with:

```robot
Library    ParallelRunner
```

In Python, `from ParallelRunner import ParallelRunner` (the old class name
`ParallelLibrary` is kept as an alias).

## Development install (from source)

The project uses [Poetry](https://python-poetry.org/) (2.x) for dependency
management and packaging:

```bash
git clone https://github.com/cristiangarciavd/robotframework-parallelrunner.git
cd robotframework-parallelrunner
poetry install
```

This creates a virtual environment with the library installed in editable
mode, plus the dev tools (`pytest`, `coverage`, `invoke`, and `requests`
for the example API client). Prefix commands with `poetry run`, or activate
the environment with `poetry env activate`.

Without Poetry, plain pip also works for an editable install of the library
itself (the dev tools then need to be installed by hand):

```bash
pip install -e .
pip install pytest coverage invoke requests
```

## Building a distribution locally

```bash
poetry build
```

This produces a wheel and an sdist under `dist/`. Install the wheel into a
fresh virtual environment with `pip install dist/robotframework_parallelrunner-*.whl`
to sanity-check packaging without a registry.

## Running the tests

```bash
poetry run invoke tests    # unit (utest/) + acceptance (atest/) tests
poetry run invoke utest    # pytest only
poetry run invoke atest    # Robot Framework suites only
```

The acceptance suites use `examples/` as "business logic" libraries, so the
repository root must be on `--pythonpath` (the `atest` task does that).

To see how much time ParallelRunner and pabot save, alone and combined, run
the offline timing demo (about a minute; pabot is included in the dev
dependencies):

```bash
poetry run invoke demo-pabot
```

Details and measured results are in
[examples/pabot_demo/README.md](../examples/pabot_demo/README.md). For a
walkthrough of the library itself, see [QUICKSTART.md](QUICKSTART.md).

## Optional: UI automation example (Playwright)

Not installed by default and not run by the commands above. See
[examples/playwright_ui/README.md](../examples/playwright_ui/README.md) if
you want to try it — it requires its own extra plus a browser download.
