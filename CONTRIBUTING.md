# Contributing to ParallelRunner

Thanks for considering a contribution. This project is small and focused, so
the process is intentionally lightweight.

## Ground rules

- All code, comments, docstrings, and documentation in this repository must be
  written in English.
- Keep the public API of `run_parallel_scenarios` stable. If a change requires
  breaking it, discuss it in an issue first and treat it as a major version
  bump with a migration note in `CHANGELOG.md`.
- Prefer small, focused pull requests over large ones.

## Development setup

```bash
git clone <this-repository-url>
cd ParallelRunner
pip install -e ".[dev]"
```

This installs the package in editable mode plus `robotframework`, `build`,
and `requests` (used by the example API client and test suites).

## Running the tests

The test suite is a set of Robot Framework acceptance suites under
`tests/robot/`, exercising the library against the example libraries in
`examples/`:

```bash
robot --pythonpath . --outputdir robot_results tests/robot/
```

All suites should pass before you open a pull request. Some tests call a
public test API (`jsonplaceholder.typicode.com`) and require network access.

## Project layout

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full structure and design
rationale. In short:

- `src/parallelrunner/` - the installable library. This is the only directory
  that ships to end users.
- `examples/` - example "business logic" libraries used by the test suites
  and documentation. Not part of the installable package.
- `tests/robot/` - Robot Framework acceptance suites.
- `docs/` - user-facing documentation.

## Making changes

1. Fork/branch from `main`.
2. Make your change. If you touch `src/parallelrunner/parallel_library.py`,
   keep `docs/API_REFERENCE.md` in sync with the actual signature/behavior.
3. Add or update a Robot Framework test case under `tests/robot/` covering the
   change.
4. Run the full suite locally (see above) and make sure it passes.
5. Update `CHANGELOG.md` under an `[Unreleased]` section.
6. Open a pull request describing the change and why it's needed.

## Reporting bugs / requesting features

Open a GitHub issue with:
- What you expected to happen vs. what happened.
- A minimal Robot Framework snippet reproducing the issue, if applicable.
- Your Python, Robot Framework, and OS versions.

## Code of Conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md). By
participating, you agree to abide by it.
