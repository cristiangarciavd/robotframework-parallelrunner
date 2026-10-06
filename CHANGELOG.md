# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.1] - 2026-10-06

### Added
- README section "Using It Together With pabot": the combination was tested
  (all 41 acceptance tests pass under pabot, splitting by suite and with
  `--testlevelsplit`), with measured timings and caveats (run pabot from the
  library's virtualenv, concurrency = processes × workers, shared resources
  across processes).
- `examples/pabot_demo/`: offline timing demo (4 suites × 8 items × 1 s of
  simulated I/O) and the `invoke demo-pabot` task, which times robot vs
  pabot, with and without ParallelRunner, and prints a table.
- `robotframework-pabot` as a development dependency (used by the demo only).
- `atest/test_logger_mapper.robot` (offline) and new unit tests that check
  which logger is really used: a resolvable mapper receives the messages, an
  unresolvable one is ignored with a warning and logs stay buffered.
- Library documentation section "Custom logger mappers".

### Changed
- README "Summary of Benefits" and ARCHITECTURE "Performance
  Considerations" now quote measured timings instead of theoretical ones.
- README project structure, ARCHITECTURE, ROADMAP, CONTRIBUTING and
  INSTALLATION updated to the current layout and tooling (`utest/`,
  `tasks.py`, Poetry, release workflow).
- `.gitignore`: pabot artifacts (`.pabotsuitenames`, `pabot_results/`).

### Removed
- `register_mapper`, `get_mapper_by_name` and `get_global_mapper` from
  `examples/custom_logger/custom_logging_mapper.py`. ParallelRunner never
  consulted that registry, so it only taught a pattern that didn't work.
  (Example code only; not part of the installed package.)

### Fixed
- **A logger mapper that can't be resolved is no longer ignored silently.**
  `logger_mapper` and `ROBOT_LOGGER_MAPPER` only accept a callable or a full
  `module.function` path; anything else (for example a bare name such as
  `custom_logger_adapter`, a module that can't be imported, or a missing
  function) used to fall back to the default logger without any message. It
  now logs a warning saying why, e.g. `Ignoring ROBOT_LOGGER_MAPPER
  'custom_logger_adapter': expected a 'module.function' path ...`. Behavior is
  otherwise unchanged: the default buffered logger (or, for an invalid
  argument, `ROBOT_LOGGER_MAPPER`) is still used. `None`, an empty string and
  the text `None` (any case, e.g. `logger_mapper=None` in a `.robot` file) mean
  "not given" and don't warn.
- Documentation claimed `ROBOT_LOGGER_MAPPER` accepted names registered with
  the example's `register_mapper`, and suggested `robot --variable
  ROBOT_LOGGER_MAPPER:...`; neither ever worked (ParallelRunner only resolves
  `module.function` paths and reads a real environment variable). Fixed in
  the API reference, ARCHITECTURE and `examples/custom_logger/ENVIRONMENT_SETUP.md`.
- `atest/test_custom_logger_with_env.robot` set a bare name, so its 6 tests
  passed without ever using the mapper. It now uses the full path and removes
  the variable in a Suite Teardown so it can't leak into later suites.
- `tasks.py`: every invoke task now runs tools with the interpreter invoke
  itself runs under (`sys.executable`) instead of the first `python` on the
  PATH. A plain `invoke atest` (without `poetry run` or an activated
  virtualenv) could pick up another Python and fail 33 of 36 tests with
  `No module named 'ParallelRunner'`.

## [0.2.0] - 2026-10-04

First release published to PyPI.

### Added
- `return_values_only` parameter on `Run Parallel Scenarios`: when `True`,
  returns a plain `tuple` of each call's return value (in call order)
  instead of the list of result dictionaries, and raises `ParallelTaskError`
  if any task failed. This is the natural pairing with `repeat` — since
  there's no input list to zip results against, unpacking directly into N
  variables (`${id1}    ${id2}    ${id3}=    Run Parallel Scenarios    ...    repeat=3    return_values_only=True`)
  is more convenient than indexing into a list of dicts.
- `Get Result Values` keyword (`ParallelLibrary.get_result_values`): the
  standalone form of the above — extracts the value tuple from an
  already-collected result list, for when you want to inspect `status`/`logs`
  first. Same `ParallelTaskError`-on-failure behavior.
- `ParallelTaskError` exception, exported from `parallelrunner`, raised by
  both of the above on failure. Carries `.failures` (the failed result
  dicts) for programmatic inspection, in addition to a human-readable
  summary message.
- `py.typed` marker (PEP 561) so type checkers (mypy/pyright) pick up this
  package's inline type hints once it's installed.
- `examples/db_seed/`: new example library (stdlib `sqlite3`, no network, no
  extra dependency) demonstrating the flagship `repeat` + `return_values_only`
  use case — seeding N independent fixture rows in parallel and getting each
  row's generated primary key back directly, without digging into a list of
  result dictionaries. Representative of seeding rows via a real DB
  connection pool, an internal admin API, or a cloud SDK call that returns a
  new resource's id.
- `ApiClient.smoke_test_endpoint` in `examples/api_client/api_client.py`: a
  second, realistic `for_loop_iterable` shape — hitting several *different*
  service routes once each (a post-deployment smoke test across
  microservices), contrasted with `check_endpoint_health`'s "hit the same
  fixed endpoint N times" (`repeat`) shape.
- `atest/test_return_values.robot`: 7 new test cases covering result
  ordering guarantees (for both `repeat` and `for_loop_iterable`),
  `return_values_only` (success and `ParallelTaskError` on failure), and the
  standalone `Get Result Values` keyword.
- `atest/test_repeat.robot`: 1 new test case pairing `repeat` with
  `return_values_only`.
- `examples/playwright_ui/`: optional, opt-in example demonstrating UI
  automation with Playwright's official `sync_api`. Not part of the `dev`
  extra or CI — install separately via `pip install -e ".[playwright-example]"`
  plus `playwright install chromium`; see that folder's README. Verified
  working locally (1/1 test passing).
- `atest/test_repeat.robot`: 4 new test cases covering the `repeat`
  parameter, previously undocumented by example — parallel test-data
  creation, repeated calls against a fixed endpoint, precedence of
  `for_loop_iterable` over `repeat` when both are given, and the
  no-argument default (runs once).
- `ApiClient.create_test_record` and `ApiClient.check_endpoint_health` in
  `examples/api_client/api_client.py`, backing the new test suite.

### Added (packaging)
- `utest/`: pytest unit tests covering ordering, `repeat`/`for_loop_iterable`
  selection, failure capture, log replay filtering, mapper resolution and the
  deprecated import path - runnable without a Robot execution context.
- `tasks.py` with invoke tasks: `utest`, `atest`, `tests`, `coverage`,
  `libdoc`, `build`.
- `.github/workflows/publish.yml`: on a published GitHub Release, runs the
  tests, builds, and publishes to TestPyPI and then PyPI using Trusted
  Publishing (no API tokens). Release steps are documented in CONTRIBUTING.md.
- Python 3.13 classifier.

### Changed
- **Import name is now `Library    ParallelRunner`** (Python: `from ParallelRunner
  import ParallelRunner`), following the Robot Framework convention of a
  `robotframework-<name>` distribution exposing a `<Name>` library. The class
  `ParallelLibrary` was renamed `ParallelRunner`. The old
  `parallelrunner.parallel_library.ParallelLibrary` path and the
  `ParallelLibrary` name keep working as deprecated aliases (a
  `DeprecationWarning` is emitted).
- Packaging migrated from setuptools to Poetry (`poetry-core` build backend).
  The version is defined only in `pyproject.toml`; `__version__` and
  `ROBOT_LIBRARY_VERSION` read it from the installed package metadata.
- Keyword and library docstrings rewritten in Robot Framework documentation
  format; keyword documentation is generated with libdoc into
  `docs/ParallelRunner.html` (served via GitHub Pages).
- Acceptance tests moved from `tests/robot/` to `atest/`.
- README links are absolute so they work on the PyPI project page; project
  URLs point to `github.com/cristiangarciavd/robotframework-parallelrunner`.
- CI installs with Poetry, runs unit and acceptance tests on Python 3.9, 3.11
  and 3.13, and checks that the keyword documentation builds.
- `Run Parallel Scenarios` now returns per-task results in **call order**
  (`results[i]` matches `for_loop_iterable[i]`, or repeat index `i`) instead
  of `concurrent.futures.as_completed` completion order. Concurrency is
  unaffected — every task still runs at once — only the order results are
  *collected* in changed. This was previously documented as completion
  order; since that order depended on thread-scheduling timing and was not
  reproducible, no real usage could have depended on a specific ordering, so
  no migration action should be needed. If you were manually sorting
  `results` by `item` to get a deterministic order, that workaround is no
  longer necessary (but remains harmless).
- Moved `AI_AGENT_CONTEXT.md` out of the repository into a local, gitignored
  `notes/` folder — it's a maintainer-facing working doc (AI-agent onboarding
  for development), not user-facing documentation, so it's no longer shipped.

### Fixed
- **Python 3.8 was actually uninstallable, not just untested.** `pyproject.toml`'s
  `license = "MIT"` (PEP 639 SPDX string form) requires setuptools >=77.0.1 to
  parse — but setuptools itself dropped Python 3.8 support at 76.0.0, so no
  setuptools version could satisfy both at once. `pip install` (editable or
  wheel) failed outright on a fresh Python 3.8 environment before any of this
  project's own code ran. Confirmed by reproducing the failure in a clean
  `python:3.8-slim` container (and the fix in a clean `python:3.9-slim` one,
  full test suite passing). Fixed by bumping `requires-python` to `>=3.9`,
  dropping the `Python :: 3.8` classifier, and tightening
  `[build-system] requires` to the real floor, `setuptools>=77.0.1` (was
  `>=68.0`, which only worked by luck on whatever newer setuptools happened
  to get resolved). `docs/INSTALLATION.md` updated to match. No source code
  changes were needed — this was a packaging-metadata/toolchain constraint,
  not a language-compatibility issue.
- **`repeat=0` silently ran the keyword once instead of zero times.**
  `run_parallel_scenarios` computed the item list as `range(repeat or 1)`;
  since `0` is falsy in Python, an explicit `repeat=0` was indistinguishable
  from `repeat` not being given at all, and fell back to `range(1)`. Fixed
  by checking `repeat is None` instead of truthiness, so `repeat=0` now
  correctly produces zero calls and an empty result list — matching what
  `for_loop_iterable=${EMPTY_LIST}` already did. Covered by a new regression
  test, `Explicit Repeat Of Zero Runs Zero Times`, in `test_repeat.robot`.

## [0.1.0] - 2026-08-30

Initial professional release. This version restructures the project from an
ad-hoc script layout into an installable Python package, without changing the
public behavior of `run_parallel_scenarios`.

### Added
- `src/` layout package `parallelrunner` (installable as
  `robotframework-parallelrunner`), exposing `ParallelLibrary` and `__version__`.
- `pyproject.toml` (PEP 621) with an editable local/dev install workflow
  (`pip install -e .`, `python -m build`).
- `examples/` directory containing the demo API client and custom-logger
  adapter libraries, moved out of the installable package.
- `atest/` directory containing the Robot Framework acceptance suites.
- `docs/INSTALLATION.md`, `docs/QUICKSTART.md`, `docs/API_REFERENCE.md`.
- `CONTRIBUTING.md` and `CODE_OF_CONDUCT.md`.
- `ROADMAP.md`, replacing the old ad-hoc, Spanish-language `IMPROVEMENT_PLAN.md`.
- `.github/workflows/tests.yml` GitHub Actions workflow running the Robot
  Framework suites on push/PR across a Python version matrix.
- `.gitignore`, `.editorconfig`, MIT `LICENSE`.
- Git repository initialized for the project.

### Changed
- Moved `ParallelLibrary/parallel_library.py` to `src/parallelrunner/parallel_library.py`
  (logic unchanged).
- Moved `TestAPI/` to `examples/api_client/`.
- Moved `CustomLogger/` to `examples/custom_logger/`.
- Moved `TestExample/*.robot` to `atest/`.
- Updated all `Library` statements in `.robot` files and all documentation to
  reference the new module paths (`parallelrunner.parallel_library.ParallelLibrary`,
  `examples.api_client.api_client.ApiClient`,
  `examples.custom_logger.custom_logger_api_client.CustomLoggerApiClient`).
- Rewrote `README.md` with installation instructions, a quickstart, and a
  dedicated comparison against [pabot](https://github.com/mkorpela/pabot).
- Updated `ARCHITECTURE.md` and `AI_AGENT_CONTEXT.md` to reflect the new layout.
- Translated remaining Spanish-language documentation to English.

### Removed
- Stale generated Robot Framework artifacts from the repository root
  (`output.xml`, `log.html`, `report.html`, `__pycache__/`) — these are now
  gitignored build artifacts, not tracked source.

No changes were made to the public API or runtime behavior of
`run_parallel_scenarios`.
