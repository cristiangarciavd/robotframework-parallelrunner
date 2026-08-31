# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- Moved `AI_AGENT_CONTEXT.md` out of the repository into a local, gitignored
  `notes/` folder — it's a maintainer-facing working doc (AI-agent onboarding
  for development), not user-facing documentation, so it's no longer shipped.

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
