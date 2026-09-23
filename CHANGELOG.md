# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
- `tests/robot/test_return_values.robot`: 7 new test cases covering result
  ordering guarantees (for both `repeat` and `for_loop_iterable`),
  `return_values_only` (success and `ParallelTaskError` on failure), and the
  standalone `Get Result Values` keyword.
- `tests/robot/test_repeat.robot`: 1 new test case pairing `repeat` with
  `return_values_only`.
- `examples/playwright_ui/`: optional, opt-in example demonstrating UI
  automation with Playwright's official `sync_api`. Not part of the `dev`
  extra or CI — install separately via `pip install -e ".[playwright-example]"`
  plus `playwright install chromium`; see that folder's README. Verified
  working locally (1/1 test passing).
- `tests/robot/test_repeat.robot`: 4 new test cases covering the `repeat`
  parameter, previously undocumented by example — parallel test-data
  creation, repeated calls against a fixed endpoint, precedence of
  `for_loop_iterable` over `repeat` when both are given, and the
  no-argument default (runs once).
- `ApiClient.create_test_record` and `ApiClient.check_endpoint_health` in
  `examples/api_client/api_client.py`, backing the new test suite.

### Changed
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
- `tests/robot/` directory containing the Robot Framework acceptance suites.
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
- Moved `TestExample/*.robot` to `tests/robot/`.
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
