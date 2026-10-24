# ParallelRunner - Professional Architecture Guide

## Project Overview

**ParallelRunner** is a scalable, reusable Robot Framework library for parallel test execution with thread-safe logging. Designed for production use and easy adaptation to other projects.

## Project Structure

```
ParallelRunner/
├── src/
│   ├── ParallelRunner/        # Core library (the installable package) -> `Library    ParallelRunner`
│   │   ├── __init__.py        # Exposes ParallelRunner, ParallelTaskError, __version__
│   │   ├── parallel_library.py   # ParallelRunner implementation (+ ParallelLibrary alias)
│   │   └── version.py         # Reads the version from the installed package metadata
│   └── parallelrunner.py      # Deprecated shim for the old `parallelrunner.parallel_library` path
│
├── examples/                  # Example "business logic" libraries, not part of the package
│   ├── api_client/
│   │   ├── __init__.py
│   │   └── api_client.py      # Example API client with logging
│   │
│   ├── custom_logger/         # Custom logging adapter examples
│   │   ├── __init__.py
│   │   ├── custom_logger.py                # Custom severity-based logger
│   │   ├── custom_logging_mapper.py        # Mapper for custom logger format
│   │   ├── custom_logger_api_client.py     # Example using custom logger
│   │   └── README.md          # Documentation on custom loggers
│   │
│   ├── db_seed/                # Parallel test-data seeding example (stdlib sqlite3, no network)
│   │   ├── __init__.py
│   │   └── db_seed_client.py  # Flagship `repeat` + `return_values_only` use case
│   │
│   ├── order_check/           # Failure handling example: some orders fail on purpose (offline)
│   │   ├── __init__.py
│   │   └── order_check_client.py
│   │
│   ├── log_levels/            # Every log level and a [Timeout] demo (offline)
│   │   ├── shipment_check_client.py
│   │   ├── log_levels.robot   # Example suite: --loglevel vs thread_log_level, timeout
│   │   └── README.md
│   │
│   ├── pabot_demo/            # Offline timing demo: robot vs pabot, with/without ParallelRunner
│   │   ├── demo_client.py     # Simulated I/O (1 s sleep per item), no network
│   │   ├── demo.resource      # Shared keyword; MODE=sequential|parallel
│   │   ├── suites/            # 4 identical suites (run by `invoke demo-pabot`, not by CI)
│   │   └── README.md          # How to run it and measured results
│   │
│   └── playwright_ui/         # OPTIONAL: UI automation example (not installed by default, not in CI)
│       ├── ui_client.py       # Playwright sync_api, one browser per call (thread-safe)
│       ├── test_playwright_ui.robot   # Lives here, not under atest/, on purpose
│       └── README.md          # Opt-in install/run instructions
│
├── atest/                              # Robot Framework acceptance suites
│   ├── test_api.robot                  # Happy path tests (sequential & parallel)
│   ├── test_api_negative.robot         # Tests with warnings/errors
│   ├── test_repeat.robot               # `repeat` usage: data setup, fixed-endpoint calls
│   ├── test_return_values.robot        # Result ordering guarantees, `return_values_only`, `Get Result Values`
│   ├── test_custom_logger.robot        # Tests with an explicit custom logger adapter
│   ├── test_custom_logger_with_env.robot  # Same, via ROBOT_LOGGER_MAPPER env var
│   ├── test_logger_mapper.robot        # Which logger is really used (mapper vs default), offline
│   ├── test_failures.robot             # Failed calls fail the keyword; `fail_on_error=False`, offline
│   ├── test_log_levels.robot           # Every level in the real log, vs --loglevel and thread_log_level, offline
│   ├── test_timeouts.robot             # Robot [Timeout] interrupts the batch, partial logs, offline
│   ├── _fixtures/                      # Suites run in a separate robot process by the two above
│   │                                   # (skipped by `robot atest`: the name starts with "_")
│   └── resources/
│       ├── MapperProbe.py              # Test helper: recording mapper + logging keyword
│       └── FixtureRunner.py            # Test helper: runs a fixture suite, reads its output.xml
│
├── utest/                     # pytest unit tests (no Robot execution context needed)
├── docs/                      # User docs + generated keyword docs (ParallelRunner.html, GitHub Pages)
├── .github/workflows/         # tests.yml (CI), publish.yml (PyPI release via Trusted Publishing)
├── pyproject.toml             # Poetry project / packaging metadata
├── poetry.lock                # Locked dev environment
├── tasks.py                   # invoke tasks: utest, atest, tests, coverage, libdoc, demo-pabot, build
└── README.md                  # Project documentation (also the PyPI project page)
```

`src/` (the `ParallelRunner` package plus the `parallelrunner.py` shim) is the only thing that ships as the installed package (`pip install robotframework-parallelrunner`). Everything under `examples/`, `atest/` and `utest/` is developer-facing sample code and acceptance tests that consume the installed library.

## Architecture Principles

### 1. **Separation of Concerns**
- **ParallelRunner**: Handles parallelization and thread-safe logging only
- **Business Logic**: Implemented in separate libraries (e.g., TestAPI, CustomLoggerApiClient)
- **Test Suites**: Contain only test cases, not logic

### 2. **Extensibility**
- Methods can be extended by subclassing or creating new libraries
- Custom loggers can be adapted via `logger_mapper` parameter
- No hardcoding of library names or logging formats

### 3. **Reusability**
- `ParallelRunner` is library-agnostic (pass any library name via `library` parameter)
- Custom logging adapters allow integration with any existing logger
- Methods follow standard patterns for easy adaptation

### 4. **Thread Safety**
- Direct method calls instead of `BuiltIn().run_keyword()` (not thread-safe)
- Log buffering with sequential replay to prevent interleaving
- Isolated thread contexts

## Core Features

### `run_parallel_scenarios` API

```python
run_parallel_scenarios(
    keyword: str,              # Method name to execute in parallel
    library: str,              # Library where method is defined
    for_loop_iterable: Optional[Iterable[Any]] = None,  # Items to iterate
    repeat: Optional[int] = None,  # Or repeat N times
    remove_passing_logs: bool = False,  # Hide logs for passing tasks
    thread_log_level: str = "TRACE",    # Min level replayed: TRACE (all), DEBUG, INFO, WARN, ERROR
    logger_mapper: Optional[Callable] = None,  # Adapter for custom loggers
    return_values_only: bool = False,  # Return a plain tuple of return values instead
    fail_on_error: bool = True,        # Fail if any call failed (False: return statuses instead)
    **kwargs: Any              # Extra args passed to method
) -> Union[List[Dict[str, Any]], Tuple[Any, ...]]
```

### Parameters

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `keyword` | str | Method name (snake_case converted) | Required |
| `library` | str | Library full path (e.g., "examples.api_client.api_client.ApiClient") | Required |
| `for_loop_iterable` | Iterable | Items to process in parallel | None |
| `repeat` | int | Or number of times to repeat | None |
| `remove_passing_logs` | bool | Skip logs for passing tasks | False |
| `thread_log_level` | str | Min level replayed: TRACE, DEBUG, INFO, WARN, ERROR. Robot's `--loglevel` still applies | "TRACE" |
| `logger_mapper` | Callable | Custom logger adapter | None |
| `return_values_only` | bool | Return a plain `tuple` of each call's return value (call order), instead of the list of result dicts. Raises `ParallelTaskError` on any failure. | False |
| `fail_on_error` | bool | Raise `ParallelTaskError` if any call failed, after all calls finished and logs were replayed. `False` returns the result list with a `PASS`/`FAIL` status per call instead. | True |
| `**kwargs` | Any | Extra args for method | - |

### Result ordering

`results[i]` (or `return_values_only` tuple index `i`) always corresponds to
`for_loop_iterable[i]`, or to repeat index `i` - **call order**, not
completion order. Every call has a slot in a result list created up front;
the worker that runs call `i` writes its result to slot `i`, and the main
thread waits for the slots in order. Waiting for slot `i` doesn't force calls
to run one at a time: up to `ROBOT_THREAD_WORKERS` run at once, whatever
order they finish in. This makes direct indexing - and tuple-unpacking via
`return_values_only` - safe to rely on.

### Thread pool and timeouts

Each `Run Parallel Scenarios` call starts its own `min(ROBOT_THREAD_WORKERS,
number of calls)` worker threads, which take call indexes from a queue until
it is empty. The library does not use `concurrent.futures.ThreadPoolExecutor`
(it did before 0.3.1), for two reasons that both come from Robot's
`[Timeout]`:

- On Windows, Robot raises the timeout in the main thread asynchronously
  (`PyThreadState_SetAsyncExc`), and it is only delivered while that thread
  runs Python code. A main thread blocked in `future.result()` (waiting on a
  lock, in C) never received it until the whole batch was done. On POSIX the
  timeout (`SIGALRM`) did interrupt the wait, but leaving the
  `with ThreadPoolExecutor()` block then waited for every thread anyway. The
  main thread now waits in short `time.sleep` steps, reading the result
  slots without any lock (a lock held at the moment the asynchronous
  exception arrives could stay locked forever).
- `ThreadPoolExecutor` threads are not daemon threads: Python waits for them
  at exit, so a call that hangs kept the Robot process alive after the run.
  The workers are now daemon threads.

When the wait is interrupted, the main thread tells the workers to stop
taking new calls, replays the logs collected so far (finished calls as
usual; running calls with their partial logs - the log buffers are created by
the main thread, so it can read them - plus an `ERROR`; calls that never
started are only counted in a summary line) and re-raises, so Robot reports
the timeout. Calls already running can't be killed: they finish in the
background.

### Log levels

The injected `_logger` keeps `(level, message)` as given; levels are checked
when the logs are replayed. Every Robot level (`TRACE`, `DEBUG`, `INFO`,
`HTML`, `CONSOLE`, `WARN`, `ERROR`, any case; `WARNING`/`CRITICAL`/`FATAL`
as aliases) is written with `logger.write`, so Robot's `--loglevel` filters
them like any keyword's messages; `thread_log_level` is an extra minimum on
top. A message with an unknown level is written at `INFO` with the level as a
prefix, plus one warning per unknown level. Before 0.3.1 only `INFO`, `WARN`
and `ERROR` were written and every other level was dropped silently.

### Failure handling

Each worker catches any exception raised by its call and turns it into a
`FAIL` result entry (the error is also added to that call's buffered logs at
`ERROR` level), so one failure never cancels or hides the other calls. Once
every call has finished and the logs have been replayed, the main thread
checks the results: with the default `fail_on_error=True`, any `FAIL` entry
raises `ParallelTaskError`, listing each failed item and its error, which
fails the keyword like any other Robot Framework failure. With
`fail_on_error=False` the full result list is returned and the test decides
what a failed call means. `return_values_only=True` always raises on a
failed call, since there is no return value to put in its slot.

Before 0.3.0 failed calls never failed the keyword: they were only logged at
`ERROR` level, and a test that didn't check each `status` itself passed.

### Method Signature Pattern

All methods compatible with `ParallelRunner` should follow:

```python
def method_name(self, item_id: str, _logger: Optional[Callable] = None, **kwargs):
    # Use injected logger or fallback
    log = _logger if _logger else default_log
    
    # Any Robot level: "TRACE", "DEBUG", "INFO", "HTML", "CONSOLE", "WARN", "ERROR"
    log(f"Request: {item_id}", "DEBUG")
    log("Starting processing", "INFO")
    log("Warning detected", "WARN")
    log("Error occurred", "ERROR")
    
    # Return result
    return result
```

## Usage Examples

### Basic Parallel Execution

```robot
*** Test Cases ***
Parallel Processing
    ${items}=    Create List    1    2    3    4    5
    Run Parallel Scenarios    
    ...    keyword=Verify Agent Data
    ...    library=examples.api_client.api_client.ApiClient
    ...    for_loop_iterable=${items}
```

### With Log Filtering

```robot
*** Test Cases ***
Show Only Warnings And Errors
    ${items}=    Create List    1    2    3    4    5
    Run Parallel Scenarios    
    ...    keyword=Validate Agents With Warnings
    ...    library=examples.api_client.api_client.ApiClient
    ...    for_loop_iterable=${items}
    ...    thread_log_level=WARN
    ...    remove_passing_logs=True
```

### Checking Failures Yourself

```robot
*** Test Cases ***
Report Each Failed Item
    ${items}=    Create List    1    2    3    4    5
    ${results}=    Run Parallel Scenarios
    ...    keyword=Validate Agents With Errors
    ...    library=examples.api_client.api_client.ApiClient
    ...    for_loop_iterable=${items}
    ...    fail_on_error=False
    Should Be Equal    ${results}[3][status]    FAIL
```

Without `fail_on_error=False`, this call fails with
`ParallelTaskError: 2 of 5 parallel task(s) failed: ...`.

### With Custom Logger

```robot
*** Test Cases ***
Custom Logger Integration
    ${items}=    Create List    1    2    3    4    5
    Run Parallel Scenarios    
    ...    keyword=Validate With Custom Logger
    ...    library=examples.custom_logger.custom_logger_api_client.CustomLoggerApiClient
    ...    for_loop_iterable=${items}
    ...    logger_mapper=examples.custom_logger.custom_logging_mapper.custom_logger_adapter
```

## Adapting to Other Projects

### Step 1: Create Your Library

```python
# my_library/my_client.py
class MyClient:
    def process_item(self, item_id: str, _logger=None, **kwargs):
        log = _logger if _logger else print
        log("Processing started", "INFO")
        # Your logic here
        return result
```

### Step 2: Use in Robot Framework

```robot
*** Settings ***
Library    ParallelRunner
Library    my_library.my_client.MyClient

*** Test Cases ***
Process In Parallel
    ${items}=    Create List    1    2    3    4    5
    Run Parallel Scenarios    
    ...    keyword=Process Item
    ...    library=my_library.my_client.MyClient
    ...    for_loop_iterable=${items}
```

### Step 3: Optional - Custom Logger Integration

If your project uses a custom logger (e.g., `log_custom(msg, severity=1)`):

```python
# my_library/custom_mapper.py
def map_to_my_logger(msg, level="INFO"):
    severity_map = {"INFO": 1, "WARN": 2, "ERROR": 3}
    log_custom(msg, severity=severity_map.get(level, 1))
```

Then pass it by its full `module.function` path (bare names like
`map_to_my_logger` are ignored with a warning). The mapper's messages go
straight to your logger instead of being buffered and replayed into
`log.html`, and it is called from several threads at once, so keep it
thread-safe:

```robot
Run Parallel Scenarios    
    ...    keyword=Process Item
    ...    library=my_library.my_client.MyClient
    ...    for_loop_iterable=${items}
    ...    logger_mapper=my_library.custom_mapper.map_to_my_logger
```

## Performance Considerations

### Thread Pool Configuration

Set number of workers via environment variable:

```bash
# Default 4 workers
export ROBOT_THREAD_WORKERS=8

poetry run robot --pythonpath . atest/
```

### Scalability

- **Small datasets (1-10 items)**: Sequential may be faster (overhead of threading)
- **Medium datasets (10-100 items)**: Parallel with 4-8 workers recommended
- **Large datasets (100+ items)**: Adjust workers based on workload type and hardware

### Network/IO Bound

For network requests (API calls), parallelization provides significant speedup.
Measured on this repository's examples (2026-10-04):

- `atest/test_api.robot` (9 HTTP calls, each with a 1 s simulated delay):
  13.0 s sequential, 4.7 s with 4 workers, 2.0 s with 9 workers.
- `examples/pabot_demo` (4 suites × 8 items × 1 s, offline): 32.7 s
  sequential, 4.6 s with ParallelRunner (8 workers), 10.6 s with pabot
  (4 processes), 3.5 s with both. See the README section "Using It Together
  With pabot".

### CPU Bound

Python's GIL (Global Interpreter Lock) limits CPU-bound parallelization. For heavy computation, consider:
- Optimizing logic
- Using external services
- Alternative execution strategies

## Testing Coverage

Acceptance tests: **67 test cases** across 10 Robot Framework suites in `atest/`.
Unit tests: **72 pytest tests** in `utest/` (ordering, item selection, failure
handling and `fail_on_error`, every log level and its filtering, interruption
by a timeout, the thread pool, mapper resolution and warnings, deprecated
import path).

| Suite | Cases | Coverage |
|-------|-------|----------|
| test_api.robot | 2 | Happy path (sequential & parallel) |
| test_api_negative.robot | 11 | Warnings, errors, log levels, filtering; failed calls fail the keyword, or are returned with `fail_on_error=False` |
| test_repeat.robot | 6 | `repeat`: parallel data creation, fixed-endpoint calls, precedence vs. `for_loop_iterable`, default (neither given), `return_values_only` unpacking, explicit `repeat=0` runs zero times |
| test_return_values.robot | 7 | Call-order guarantees (`repeat` and `for_loop_iterable`), `return_values_only` (success and `ParallelTaskError` on failure), standalone `Get Result Values` |
| test_custom_logger.robot | 5 | Custom logger adapter integration, passed explicitly |
| test_custom_logger_with_env.robot | 6 | Same, configured via `ROBOT_LOGGER_MAPPER` env var |
| test_logger_mapper.robot | 5 | Which logger is actually used: explicit/env mapper paths receive the messages; bare or unresolvable names are ignored and logs stay buffered; fallback from an invalid argument to the env var. Offline |
| test_failures.robot | 10 | Failed calls: the keyword fails after every call ran, with every failed item in the message; `fail_on_error=False` returns a status per item; `return_values_only` and `Get Result Values` always fail. Offline |
| test_log_levels.robot | 10 | What really ends up in the log at every level (TRACE to ERROR, HTML) with `--loglevel` TRACE, DEBUG and the default, and with `thread_log_level`; runs `_fixtures/log_levels.robot` in a separate process. Offline |
| test_timeouts.robot | 5 | A test or keyword `[Timeout]` fails right away, not when hung calls end; finished and partial logs replayed; next test unaffected; the process exits despite hung calls. Runs `_fixtures/timeouts.robot` in a separate process. Offline |

Run all tests (after `poetry install`):

```bash
poetry run invoke tests
```

Run a specific suite:

```bash
poetry run robot --pythonpath . atest/test_custom_logger.robot
```

## Best Practices

### For Method Implementations

✅ **DO:**
- Accept `_logger` as optional parameter
- Use Robot levels: "TRACE", "DEBUG", "INFO", "HTML", "WARN", "ERROR" (DEBUG/TRACE for detail that only shows with `--loglevel DEBUG`/`TRACE`)
- Set timeouts on your own I/O (e.g. `requests.get(url, timeout=10)`): a Robot `[Timeout]` can't stop a call that is already running
- Handle both parallel (_logger provided) and direct execution
- Return meaningful results

❌ **DON'T:**
- Use `BuiltIn().run_keyword()` inside methods (not thread-safe)
- Log directly to files in threads (use logger injection)
- Modify shared state across threads
- Block threads with long sleeps

### For Test Suites

✅ **DO:**
- Use meaningful test names that describe the scenario
- Test different combinations of parameters
- Document expected behavior
- Compare sequential vs parallel results

❌ **DON'T:**
- Hard-code library names (use variables)
- Test implementation details (test behavior)
- Skip error cases

## Troubleshooting

### "No library 'X' found"
- Ensure library path includes full class path: `PackageName.module.ClassName`
- Check `--pythonpath .` is included in robot command

### "Keyword 'X' not found in library"
- Verify method name exists and matches (converted to snake_case)
- Check method signature includes `_logger` parameter

### "No keyword with name 'Run Parallel Scenarios' found" under pabot
- pabot starts whichever `robot` is first on the `PATH`. Run pabot from the
  virtual environment where the library is installed (or `poetry run pabot`),
  or pass the interpreter explicitly:
  `pabot --command python -m robot --end-command ...`

### Logs not appearing
- Check `thread_log_level` setting (default "TRACE", every level)
- `TRACE`/`DEBUG` messages need a low enough Robot `--loglevel` (e.g. `--loglevel DEBUG`)
- A message with an unknown level is logged at `INFO` with a `[LEVEL]` prefix and a warning
- Verify `remove_passing_logs` is not set to True
- Ensure methods use `_logger` parameter
- If a logger mapper is configured, its messages go to your own logging
  system, not to `log.html`. If the log shows `Ignoring logger_mapper ...` or
  `Ignoring ROBOT_LOGGER_MAPPER ...`, the value couldn't be resolved: use a
  full `module.function` path, and set `ROBOT_LOGGER_MAPPER` as a real
  environment variable (not with `--variable`)

## Future Enhancements

See [ROADMAP.md](ROADMAP.md) for the up-to-date list of completed work and future ideas.

## License

MIT. See [LICENSE](LICENSE).

## Support

For questions or issues, refer to:
- `src/ParallelRunner/`: Core implementation
- `examples/custom_logger/`: Custom logger integration examples
- `atest/`: Test examples
- `docs/`: User-facing documentation
