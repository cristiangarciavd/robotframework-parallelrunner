# ParallelRunner - Roadmap

This document tracks the project's maturity: what is already in place, and what
could reasonably be added next. It replaces the old (Spanish-language,
session-scoped) `IMPROVEMENT_PLAN.md`.

## Current Status (as of 0.2.0)

### Done

**Core functionality**
- `ParallelRunner` with `ThreadPoolExecutor`-based execution
- Thread-safe logging via buffer + sequential replay (`_execute_and_capture` / `_replay_logs`)
- Support for `for_loop_iterable` and `repeat`
- Log filtering by level (`thread_log_level`)
- Handling of `sv=0` / `"IGNORE"` level logs
- Results collected in **call order** (`results[i]` matches `for_loop_iterable[i]`
  / repeat index `i`), not `as_completed` completion order
- `return_values_only` parameter and standalone `Get Result Values` keyword,
  for extracting a plain, ordered tuple of each call's return value - the
  natural fit for `repeat`, since there's no input list to zip results
  against (see `ParallelTaskError`, raised if any task failed)

**Custom logger support**
- `_create_local_logger()` for local adaptation inside existing methods
- `ROBOT_LOGGER_MAPPER` environment variable for global configuration
- Named mapper registration (`register_mapper` / `get_global_mapper`)
- Full worked example with `CustomLoggerApiClient`

**Packaging and distribution**
- `src/` layout with the installable package at `src/ParallelRunner/`
- `pyproject.toml` (PEP 621, built with Poetry), published as
  `robotframework-parallelrunner` and imported as `Library    ParallelRunner`
- Keyword documentation generated with libdoc (`invoke libdoc`) and served
  from GitHub Pages
- pytest unit tests (`utest/`) alongside the Robot acceptance suites (`atest/`)
- Release workflow publishing to TestPyPI and PyPI via Trusted Publishing
- `py.typed` marker (PEP 561) so type checkers respect the package's inline
  type hints once installed
- MIT `LICENSE`
- `.gitignore`, `.editorconfig`

**Documentation**
- `README.md` with quickstart and a "How is this different from pabot?" comparison
- `ARCHITECTURE.md` (technical deep dive)
- `docs/INSTALLATION.md`, `docs/QUICKSTART.md`, `docs/API_REFERENCE.md`
- `CHANGELOG.md` (Keep a Changelog format)
- `examples/custom_logger/README.md` and `ENVIRONMENT_SETUP.md`

**Community / governance**
- `CONTRIBUTING.md`
- `CODE_OF_CONDUCT.md` (Contributor Covenant)

**Tests**
- 36 Robot Framework test cases across 6 suites under `atest/`, all passing,
  including a dedicated `test_repeat.robot` covering the `repeat` parameter
  (parallel data setup, repeated calls to a fixed endpoint, precedence vs.
  `for_loop_iterable`, the no-argument default, `return_values_only`, and the
  `repeat=0` regression) and `test_return_values.robot` (call-order
  guarantees, `return_values_only`, `Get Result Values`, and
  `ParallelTaskError` on failure)

**CI**
- `.github/workflows/tests.yml`: installs the package and runs the Robot Framework
  suites on push/PR across a small Python version matrix

### Explicitly out of scope for now

- **PyPI publishing workflow.** There is no PyPI token configured for this
  project yet, so no `publish.yml` / trusted-publishing workflow exists. Once a
  token (or PyPI Trusted Publisher config) is available, add a release workflow
  that builds with `python -m build` and uploads via `twine`/`pypa/gh-action-pypi-publish`.
- **GitHub issue/PR templates.** Not created yet; cheap to add later
  (`.github/ISSUE_TEMPLATE/`, `.github/PULL_REQUEST_TEMPLATE.md`).

## Ideas for Future Work

These are possible directions, not commitments. Contributions welcome — see
`CONTRIBUTING.md`.

- **Retry mechanism** for individual failed tasks within `run_parallel_scenarios`
  (e.g. `retries=N`, `retry_backoff=...`).
- **Per-task timeout** so a single hung item doesn't stall the whole batch.
- **Richer result aggregation**, e.g. a summary object/keyword (`Get Parallel Summary`)
  instead of only the raw list of per-item dicts.
- **Structured (JSON) logging** as an alternative to the current text-based replay,
  for easier machine parsing of `log.html`-adjacent artifacts.
- **Process-based execution mode** for CPU-bound workloads, as an opt-in alternative
  to the current thread-based model (would need its own log-buffering strategy,
  since data can't be shared across processes the same way).
- **Type-checked mapper contracts** (e.g. a `Protocol` for `logger_mapper`) to catch
  malformed adapters earlier.
- **Linting/formatting in CI** (ruff/black) and optionally pre-commit hooks.
- **Code coverage reporting** once there is meaningful Python-level unit test
  coverage (today the test suite is Robot Framework acceptance tests, which is
  appropriate for this project but doesn't produce a coverage number in the
  usual sense).
- **PyPI release** once the maintainer decides to publish (see "out of scope" above).

## Contributing to This Roadmap

If you pick up one of these items, open an issue or PR describing the approach
before investing significant time — see `CONTRIBUTING.md`. Please keep the
public API of `run_parallel_scenarios` stable; if a change requires breaking
it, propose it as a major version bump with a migration note in `CHANGELOG.md`.
