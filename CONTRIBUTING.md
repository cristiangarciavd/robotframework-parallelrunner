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

The project uses [Poetry](https://python-poetry.org/) 2.x:

```bash
git clone https://github.com/cristiangarciavd/robotframework-parallelrunner.git
cd robotframework-parallelrunner
poetry install
```

This installs the library in editable mode plus the dev tools (`pytest`,
`coverage`, `invoke`, and `requests` for the example API client).

## Running the tests

Common tasks are defined in `tasks.py` and run with [invoke](https://www.pyinvoke.org/):

```bash
poetry run invoke --list      # show all tasks
poetry run invoke tests       # unit + acceptance tests
poetry run invoke utest       # pytest unit tests in utest/
poetry run invoke atest       # Robot Framework acceptance suites in atest/
poetry run invoke coverage    # both, under coverage, with an HTML report
```

All tests should pass before you open a pull request. Some acceptance tests
call a public test API (`jsonplaceholder.typicode.com`) and require network
access.

## Project layout

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full structure and design
rationale. In short:

- `src/ParallelRunner/` - the installable library (`Library    ParallelRunner`).
  `src/parallelrunner.py` is a deprecated shim for the old import path.
- `examples/` - example "business logic" libraries used by the test suites
  and documentation. Not part of the installable package.
- `atest/` - Robot Framework acceptance suites.
- `utest/` - pytest unit tests.
- `docs/` - user-facing documentation and the generated keyword
  documentation (`docs/ParallelRunner.html`).

## Making changes

1. Fork/branch from `main`.
2. Make your change. If you touch `src/ParallelRunner/parallel_library.py`,
   keep the keyword docstrings and `docs/API_REFERENCE.md` in sync with the
   actual signature/behavior, and regenerate the keyword documentation with
   `poetry run invoke libdoc`.
3. Add or update tests: a pytest case under `utest/` and/or a Robot
   Framework test case under `atest/`.
4. Run the full suite locally (see above) and make sure it passes.
5. Update `CHANGELOG.md` under the `[Unreleased]` section.
6. Open a pull request describing the change and why it's needed.

## Releasing

Releases are published to PyPI by `.github/workflows/publish.yml` when a
GitHub Release is published, using
[Trusted Publishing](https://docs.pypi.org/trusted-publishers/) - no API
tokens are stored in the repository.

### One-time setup

1. On <https://pypi.org/manage/account/publishing/>, add a *pending
   publisher* (this also reserves the project name before the first upload):
   - PyPI project name: `robotframework-parallelrunner`
   - Owner: `cristiangarciavd`
   - Repository: `robotframework-parallelrunner`
   - Workflow: `publish.yml`
   - Environment: `pypi`
2. Do the same on <https://test.pypi.org/manage/account/publishing/>, with
   environment `testpypi`.
3. In the GitHub repository, *Settings -> Environments*, create the
   environments `testpypi` and `pypi` (optionally require a reviewer on
   `pypi`).
4. *Settings -> Pages*: source "Deploy from a branch", branch `main`,
   folder `/docs`, to serve the keyword documentation.

### Each release

1. Bump the version: `poetry version patch` (or `minor` / `major`).
2. Move the `[Unreleased]` entries in `CHANGELOG.md` to the new version.
3. Regenerate the keyword docs: `poetry run invoke libdoc`.
4. Commit, push, and create a GitHub Release with tag `vX.Y.Z` matching the
   version in `pyproject.toml` (the workflow refuses to publish otherwise).
5. The workflow runs the tests, builds, publishes to TestPyPI, then to PyPI.

To try the pipeline without a release, run the workflow manually
(*Actions -> Publish to PyPI -> Run workflow*): it publishes to TestPyPI only.

## Reporting bugs / requesting features

Open a GitHub issue with:
- What you expected to happen vs. what happened.
- A minimal Robot Framework snippet reproducing the issue, if applicable.
- Your Python, Robot Framework, and OS versions.

## Code of Conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md). By
participating, you agree to abide by it.
