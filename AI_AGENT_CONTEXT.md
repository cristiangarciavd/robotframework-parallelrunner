# For AI Agents: ParallelRunner Context & Instructions

> **Use this file to get up to speed on ParallelRunner in 2 minutes.**

## What is This Project? (TL;DR)

**ParallelRunner** = Robot Framework library for running a keyword/method in
parallel *inside a single test case* (thread pool), with thread-safe logging.
Packaged for installation as `robotframework-parallelrunner`, importable as
`parallelrunner`.

**Problem:** Robot Framework is single-threaded, and multi-threading breaks
`log.html` if you're not careful.
**Solution:** Execute keywords in parallel on a thread pool, buffer logs per
thread, replay sequentially into the real logger.
**Result:** ~Nx speedup for I/O-bound loops, clean `log.html`, no corruption.

This is a different, complementary tool to **pabot** (which parallelizes at
the suite/test-case level using separate processes). See the README's
"How Is This Different From pabot?" section for the full comparison.

## Current Status

| Component | Status | Notes |
|-----------|--------|-------|
| Core library | Complete | `src/parallelrunner/parallel_library.py` — logic unchanged since the pre-restructure version |
| Custom logger support | Complete | Mapper pattern, env variable (`ROBOT_LOGGER_MAPPER`), all working |
| Tests | Complete | 23 Robot Framework test cases, all passing (4 suites, under `tests/robot/`) |
| Documentation | Complete | README, ARCHITECTURE, docs/INSTALLATION, docs/QUICKSTART, docs/API_REFERENCE |
| Packaging | Complete | `pyproject.toml` (PEP 621), `src/` layout, editable install verified |
| CI | Complete | `.github/workflows/tests.yml` runs the Robot suites on push/PR |
| PyPI publish workflow | Not done (intentionally) | No PyPI token/trusted-publisher configured yet — see ROADMAP.md |
| Git repository | Initialized | Single initial commit with the restructured layout |

For a longer-form, forward-looking list of finished vs. potential future
work, see **[ROADMAP.md](ROADMAP.md)** (this replaced the old, session-scoped,
Spanish-language `IMPROVEMENT_PLAN.md`).

## Key Files to Know

### Core Implementation
- **src/parallelrunner/parallel_library.py**
  - `ParallelLibrary.run_parallel_scenarios()` - main API, do not change its
    signature or behavior without a very good reason (see CONTRIBUTING.md).
  - Uses `ThreadPoolExecutor` for parallel execution.
  - Buffers logs per task, replays them sequentially (`_replay_logs`).
  - Supports `ROBOT_THREAD_WORKERS` and `ROBOT_LOGGER_MAPPER` env variables.
- **src/parallelrunner/__init__.py** - exposes `ParallelLibrary` and `__version__`.

### Example Libraries (not part of the installable package)
- **examples/api_client/api_client.py** - simple example hitting a public
  test API (jsonplaceholder.typicode.com).
- **examples/custom_logger/** - demonstrates adapting a project with a
  pre-existing custom/severity-based logger (`sv=0,1,2,3`) to
  ParallelRunner's standard level strings via the `logger_mapper` mechanism.
  - `custom_logging_mapper.py` - `_create_local_logger()`, `custom_logger_adapter()`, `register_mapper()`, `get_global_mapper()`.
  - `custom_logger_api_client.py` - example client using the pattern.
  - `README.md`, `ENVIRONMENT_SETUP.md`, `MIGRATION_GUIDE.py` - narrative docs.

### Tests (Read to Understand Usage)
- **tests/robot/test_api.robot** - basic happy path (sequential vs. parallel).
- **tests/robot/test_api_negative.robot** - edge cases, warnings, errors, log-level filtering.
- **tests/robot/test_custom_logger.robot** - custom logger adapter, passed explicitly.
- **tests/robot/test_custom_logger_with_env.robot** - custom logger via `ROBOT_LOGGER_MAPPER` env var.

### Documentation
- **README.md** - intro, install, quickstart, pabot comparison.
- **ARCHITECTURE.md** - technical deep dive on the log buffer/replay design.
- **docs/INSTALLATION.md**, **docs/QUICKSTART.md**, **docs/API_REFERENCE.md** - user docs.
- **ROADMAP.md** - what's done, what's next.
- **CHANGELOG.md** - version history (Keep a Changelog format).

## Important Things to Remember

### What Works (Don't Break)
- `ThreadPoolExecutor` usage - solid, well-tested.
- Log buffering + replay - core feature, don't bypass it.
- Mapper pattern (`logger_mapper` / `ROBOT_LOGGER_MAPPER`) - flexible, works.
- Environment variables (`ROBOT_THREAD_WORKERS`, `ROBOT_LOGGER_MAPPER`) - clean configuration surface.

### What NOT to Change
- Don't refactor `src/parallelrunner/parallel_library.py`'s core logic unless
  there's an actual bug — it's intentionally minimal.
- Don't remove or restructure tests under `tests/robot/` without replacing
  their coverage.
- Don't change the public signature/behavior of `run_parallel_scenarios()`
  without treating it as a breaking (major-version) change.
- Keep `examples/` content as-is unless explicitly asked — it's teaching material.
- Everything (code, comments, docs) must stay in English.

## Project Layout

```
ParallelRunner/
├── src/
│   └── parallelrunner/         # Core library (the installable package)
│       ├── __init__.py
│       └── parallel_library.py
├── examples/                   # Example business-logic libraries (not installed)
│   ├── api_client/
│   └── custom_logger/
├── tests/
│   └── robot/                  # Robot Framework acceptance suites
├── docs/
│   ├── INSTALLATION.md
│   ├── QUICKSTART.md
│   └── API_REFERENCE.md
├── .github/workflows/tests.yml
├── pyproject.toml
├── LICENSE
├── CHANGELOG.md
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
├── ROADMAP.md                  # forward-looking; supersedes the old IMPROVEMENT_PLAN.md
├── ARCHITECTURE.md
├── AI_AGENT_CONTEXT.md         # this file
└── README.md
```

## Running Tests

```bash
cd ParallelRunner
pip install -e ".[dev]"

# Run all suites
robot --pythonpath . --outputdir robot_results tests/robot/

# Run a specific suite
robot --pythonpath . tests/robot/test_api.robot

# With a custom logger mapper via env var
robot --pythonpath . --variable ROBOT_LOGGER_MAPPER:custom_logger_adapter tests/robot/
```

## Version Info

**Current:** 0.1.0 (first packaged release)
**Python:** >= 3.8
**Dependencies:** `robotframework >= 5.0`

## How to Introduce Me (AI) to a New Agent

Share this file (`AI_AGENT_CONTEXT.md`) plus, for deeper technical context,
`ARCHITECTURE.md`. For forward-looking priorities, share `ROADMAP.md`.
