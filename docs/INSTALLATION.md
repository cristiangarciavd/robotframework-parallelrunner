# Installation

## Requirements

- Python >= 3.8
- [Robot Framework](https://robotframework.org/) >= 5.0 (installed automatically as a dependency)

## Install from source (current recommended method)

This project is not yet published to PyPI, so install it directly from a
local clone in editable mode:

```bash
git clone <this-repository-url>
cd ParallelRunner
pip install -e .
```

Editable installs mean changes to `src/parallelrunner/` take effect
immediately, without reinstalling.

To also install the tools needed to run the test suites and build the
package (`robotframework`, `build`, `requests` used by the example API
client):

```bash
pip install -e ".[dev]"
```

## Verify the install

```bash
python -c "from parallelrunner.parallel_library import ParallelLibrary; print('OK')"
```

## Future: install from PyPI

Once this project is published, it will be installable as:

```bash
pip install robotframework-parallelrunner
```

(This does not work yet — there is no published release. Track progress in
[CHANGELOG.md](../CHANGELOG.md) and [ROADMAP.md](../ROADMAP.md).)

## Building a distribution locally

```bash
pip install build
python -m build
```

This produces a wheel and sdist under `dist/`, which you can install with
`pip install dist/robotframework_parallelrunner-*.whl` to sanity-check
packaging without a registry.

## Running the example test suites

After installing the package, run the bundled acceptance tests (they use
`examples/` as example "business logic" libraries, so it must be on
`--pythonpath`):

```bash
robot --pythonpath . --outputdir robot_results tests/robot/
```

See [QUICKSTART.md](QUICKSTART.md) for a walkthrough.

## Optional: UI automation example (Playwright)

Not installed by `.[dev]` and not run by the test command above. See
[examples/playwright_ui/README.md](../examples/playwright_ui/README.md) if
you want to try it — it requires its own extra plus a browser download.
