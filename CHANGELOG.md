# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.0] - 2026-10-24

### Added
- **`call_timeout` parameter on `Run Parallel Scenarios`**: the maximum time
  each call may run, in Robot's time format (`call_timeout=10s`). A call
  still running after it fails on its own - error `Timed out after 10
  seconds`, with its partial logs - while the other calls keep running and
  finish. It is reported like any other failed call (`ParallelTaskError`,
  which unlike a Robot `[Timeout]` can be handled, or a `FAIL` entry with
  `fail_on_error=False`). The timed-out call can't be killed and keeps
  running in the background; a new worker thread takes its place so the
  rest of the batch still runs `ROBOT_THREAD_WORKERS` calls at a time.
- **Cooperative cancellation with `_cancelled`**: a keyword method that
  declares a `_cancelled` parameter receives a `threading.Event`, set when
  its call exceeds `call_timeout` or a Robot `[Timeout]` interrupts the
  batch, so it can stop early instead of running on in the background.
  Methods that don't declare it are called exactly as before.
- `log_to_robot(msg, level="INFO")`, importable from `ParallelRunner`: the
  fallback logger for a parallel-ready keyword called directly. It accepts
  the same levels as the injected `_logger`; the fallback the documentation
  used to recommend (`robot.api.logger.write`) failed with `Invalid log
  level 'IGNORE'` (or `'WARNING'`) when the keyword was called directly.
- Library documentation section "Call timeouts and cancellation";
  `examples/log_levels/` demos for both; `atest/test_call_timeout.robot` and
  `atest/test_keyword_calls.robot` (offline). 44 new unit tests.

### Changed
- **Arguments are converted by the keyword's type hints, like in a direct
  call.** Named arguments given to `Run Parallel Scenarios` used to reach the
  keyword as strings (`delay=0.5` arrived as `"0.5"`); they are now
  converted with Robot's own argument conversion (type hints, then the types
  of default values), exactly as when the test calls the keyword directly.
  Items are converted the same way when they are strings; other items
  (numbers, lists, dictionaries) are passed as they are, and the results
  always report the original item. An item that can't be converted fails
  only that call; a named argument that can't be converted fails the
  keyword before any call runs. A keyword that relied on receiving strings
  despite its type hints may need adjusting.
- A keyword argument named `call_timeout` is no longer forwarded to the
  target keyword.

### Fixed
- A keyword with a custom name (`@keyword("Check Order Status")`) was not
  found by `Run Parallel Scenarios`, although Robot can call it directly.
  Keywords are now found by method name or custom name, ignoring case,
  spaces and underscores like Robot.
- An invalid `ROBOT_THREAD_WORKERS` (e.g. `abc`) made the library import fail
  with a bare `invalid literal for int()`; it is now ignored with a warning
  (default 4 workers), as are values below 1.

## [0.3.1] - 2026-10-24

### Fixed
- **Messages logged at `DEBUG`, `TRACE` or `HTML` from the threads were lost.**
  Only `INFO`, `WARN` and `ERROR` were replayed into the log; any other level
  passed the filter but was never written, without any warning, even with
  `--loglevel TRACE`. Every Robot Framework level is now replayed (`TRACE`,
  `DEBUG`, `INFO`, `HTML`, `CONSOLE`, `WARN`, `ERROR`), and Robot's
  `--loglevel` filters them like any other keyword's messages. Levels are
  case-insensitive and Python `logging` names work too (`WARNING`,
  `CRITICAL`, `FATAL`). A message with an unknown level is no longer dropped:
  it is logged at `INFO` with the level as a prefix (`[VERBOSE] ...`), plus a
  warning naming the level.
- **A Robot `[Timeout]` only failed the test once the whole batch had
  finished, and the batch's logs were lost.** On Windows the timeout could
  not interrupt the keyword while it waited for the calls; on every platform
  the keyword then waited for all running calls anyway. Now a test or keyword
  timeout interrupts `Run Parallel Scenarios` when it expires: it replays the
  logs of the finished calls, the partial logs of the calls still running
  (with an `ERROR` saying they did not finish) and a summary line, and does
  not start the calls that were still waiting. Calls already running can't be
  killed and finish in the background.
- A call that hangs no longer keeps the Robot process from exiting at the
  end of the run: the worker threads are now daemon threads.
- A named argument called `method` (forwarded to the target keyword) failed
  with `TypeError: got multiple values for argument 'method'`.
- A call that raised a `BaseException` that is not an `Exception` (e.g.
  `SystemExit`) escaped from the keyword instead of being reported as a
  failed call.
- `atest/test_failures.robot` only passed on Robot Framework 7 (it used the
  RF 7 `separator=` variable syntax). The acceptance tests now pass on Robot
  Framework 5.0, 6.1 and 7.x (checked on Linux with Python 3.9, 3.11 and
  3.13).

### Changed
- `thread_log_level` now defaults to `TRACE` (replay every level and let
  Robot's `--loglevel` filter) instead of `INFO`, and also accepts `TRACE`
  and `DEBUG`. Since only `INFO` and higher used to be replayed anyway, the
  log is the same as before unless the run uses `--loglevel DEBUG` or
  `TRACE`. An unknown `thread_log_level` is now ignored with a warning
  instead of silently meaning `INFO`.
- `Run Parallel Scenarios` runs the calls on its own daemon worker threads
  (at most `ROBOT_THREAD_WORKERS`, never more than the number of calls)
  instead of `concurrent.futures.ThreadPoolExecutor`. `ROBOT_THREAD_WORKERS`
  below 1 fails with a clearer message.

### Added
- Library documentation sections "Log levels" and "Timeouts".
- `examples/log_levels/`: an offline example library that logs at every
  level, and an example suite comparing `--loglevel` and `thread_log_level`,
  with a `[Timeout]` demo.
- `atest/test_log_levels.robot` and `atest/test_timeouts.robot` (offline):
  they run fixture suites from `atest/_fixtures/` in a separate Robot process
  and check its output.xml - what really ends up in the log at each
  `--loglevel`, and how long a timeout takes. 34 new unit tests (log levels,
  interruption, the thread pool).

## [0.3.0] - 2026-10-11

### Changed
- **Breaking: a failed call now fails `Run Parallel Scenarios`.** When any
  call raises, the keyword still waits for every other call and replays all
  logs, then fails with `ParallelTaskError` listing each failed item and its
  error, e.g. `ParallelTaskError: 2 of 5 parallel task(s) failed:
  item='4': Simulated error for agent 4; item='5': Simulated error for agent 5`.
  Before, a failed call was only logged at `ERROR` level and the keyword
  passed, so a test that didn't check every `status` itself passed with
  failed calls. To keep the old behavior, pass `fail_on_error=False` (see
  below). `ParallelTaskError` is now also raised without
  `return_values_only=True`.

### Added
- `fail_on_error` parameter on `Run Parallel Scenarios` (default `True`).
  With `fail_on_error=False` the keyword returns the result list even when
  calls failed: each entry has a `PASS`/`FAIL` status and the test checks
  them itself (e.g. `Should Be Equal    ${results}[1][status]    PASS`).
  `return_values_only=True` and `Get Result Values` still always fail on a
  failed call. Note: a keyword argument named `fail_on_error` is no longer
  forwarded to the target keyword.
- `atest/test_failures.robot` (offline, 10 tests) and
  `examples/order_check/`: every way of handling failed calls - the keyword
  failing, every call still running first, every failed item in the message,
  `fail_on_error=False`, `Run Keyword And Ignore Error`.
- Library documentation section "Failures"; QUICKSTART section "Checking
  failures yourself".

### Fixed
- Tests that ran failing calls (`test_api_negative.robot` "Parallel With
  Errors - ...", the "With Errors" custom logger tests) passed without
  checking anything; they now expect the failure, and new tests cover
  `fail_on_error=False`. The opt-in Playwright example no longer passes when a
  page check fails.

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
