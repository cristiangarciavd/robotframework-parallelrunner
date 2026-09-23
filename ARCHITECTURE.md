# ParallelRunner - Professional Architecture Guide

## Project Overview

**ParallelRunner** is a scalable, reusable Robot Framework library for parallel test execution with thread-safe logging. Designed for production use and easy adaptation to other projects.

## Project Structure

```
ParallelRunner/
├── src/
│   └── parallelrunner/        # Core parallelization library (the installable package)
│       ├── __init__.py        # Exposes __version__ and ParallelLibrary
│       └── parallel_library.py   # Main ParallelLibrary implementation
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
│   └── playwright_ui/         # OPTIONAL: UI automation example (not in `dev` extras or CI)
│       ├── ui_client.py       # Playwright sync_api, one browser per call (thread-safe)
│       ├── test_playwright_ui.robot   # Lives here, not under tests/robot/, on purpose
│       └── README.md          # Opt-in install/run instructions
│
├── tests/
│   └── robot/                          # Robot Framework acceptance suites
│       ├── test_api.robot              # Happy path tests (sequential & parallel)
│       ├── test_api_negative.robot     # Tests with warnings/errors
│       ├── test_repeat.robot           # `repeat` usage: data setup, fixed-endpoint calls
│       ├── test_return_values.robot    # Result ordering guarantees, `return_values_only`, `Get Result Values`
│       ├── test_custom_logger.robot    # Tests with an explicit custom logger adapter
│       └── test_custom_logger_with_env.robot  # Same, via ROBOT_LOGGER_MAPPER env var
│
├── docs/                      # User-facing documentation
├── pyproject.toml             # Packaging metadata (installable via pip)
└── README.md                  # Project documentation
```

`parallelrunner` is the only directory that ships as the installed package (`pip install robotframework-parallelrunner`). Everything under `examples/` and `tests/` is developer-facing sample code and acceptance tests that consume the installed library.

## Architecture Principles

### 1. **Separation of Concerns**
- **ParallelLibrary**: Handles parallelization and thread-safe logging only
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
    thread_log_level: str = "INFO",     # Filter by level: INFO, WARN, ERROR
    logger_mapper: Optional[Callable] = None,  # Adapter for custom loggers
    return_values_only: bool = False,  # Return a plain tuple of return values instead
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
| `thread_log_level` | str | Min level to show: INFO, WARN, ERROR | "INFO" |
| `logger_mapper` | Callable | Custom logger adapter | None |
| `return_values_only` | bool | Return a plain `tuple` of each call's return value (call order), instead of the list of result dicts. Raises `ParallelTaskError` on any failure. | False |
| `**kwargs` | Any | Extra args for method | - |

### Result ordering

`results[i]` (or `return_values_only` tuple index `i`) always corresponds to
`for_loop_iterable[i]`, or to repeat index `i` - **call order**, not
`concurrent.futures.as_completed` completion order. Tasks are submitted to
the executor up front (so they all start concurrently), and results are then
collected by calling `.result()` on each future *in submission order*;
`.result()` on an earlier future simply blocks until that specific task
finishes, it does not force tasks to run one at a time. This makes direct
indexing - and tuple-unpacking via `return_values_only` - safe to rely on.

### Method Signature Pattern

All methods compatible with `ParallelRunner` should follow:

```python
def method_name(self, item_id: str, _logger: Optional[Callable] = None, **kwargs):
    # Use injected logger or fallback
    log = _logger if _logger else default_log
    
    # Log with standard levels: "INFO", "WARN", "ERROR"
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

### With Custom Logger

```robot
*** Test Cases ***
Custom Logger Integration
    ${items}=    Create List    1    2    3    4    5
    Run Parallel Scenarios    
    ...    keyword=Validate With Custom Logger
    ...    library=examples.custom_logger.custom_logger_api_client.CustomLoggerApiClient
    ...    for_loop_iterable=${items}
    ...    logger_mapper=custom_logger_adapter
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
Library    parallelrunner.parallel_library.ParallelLibrary
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

Then pass it:

```robot
Run Parallel Scenarios    
    ...    keyword=Process Item
    ...    library=my_library.my_client.MyClient
    ...    for_loop_iterable=${items}
    ...    logger_mapper=map_to_my_logger
```

## Performance Considerations

### Thread Pool Configuration

Set number of workers via environment variable:

```bash
# Default 4 workers
export ROBOT_THREAD_WORKERS=8

robot --pythonpath . tests/robot/
```

### Scalability

- **Small datasets (1-10 items)**: Sequential may be faster (overhead of threading)
- **Medium datasets (10-100 items)**: Parallel with 4-8 workers recommended
- **Large datasets (100+ items)**: Adjust workers based on workload type and hardware

### Network/IO Bound

For network requests (API calls), parallelization provides significant speedup. With 5 items at 1s each:
- Sequential: ~5s
- Parallel (4 workers): ~2s
- Parallel (10 workers): ~1s

### CPU Bound

Python's GIL (Global Interpreter Lock) limits CPU-bound parallelization. For heavy computation, consider:
- Optimizing logic
- Using external services
- Alternative execution strategies

## Testing Coverage

Total: **36 test cases** across 6 test suites

| Suite | Cases | Coverage |
|-------|-------|----------|
| test_api.robot | 2 | Happy path (sequential & parallel) |
| test_api_negative.robot | 10 | Warnings, errors, log levels, filtering |
| test_repeat.robot | 6 | `repeat`: parallel data creation, fixed-endpoint calls, precedence vs. `for_loop_iterable`, default (neither given), `return_values_only` unpacking, explicit `repeat=0` runs zero times |
| test_return_values.robot | 7 | Call-order guarantees (`repeat` and `for_loop_iterable`), `return_values_only` (success and `ParallelTaskError` on failure), standalone `Get Result Values` |
| test_custom_logger.robot | 5 | Custom logger adapter integration, passed explicitly |
| test_custom_logger_with_env.robot | 6 | Same, configured via `ROBOT_LOGGER_MAPPER` env var |

Run all tests:

```bash
robot --pythonpath . tests/robot/
```

Run specific suite:

```bash
robot --pythonpath . tests/robot/test_custom_logger.robot
```

## Best Practices

### For Method Implementations

✅ **DO:**
- Accept `_logger` as optional parameter
- Use standard levels: "INFO", "WARN", "ERROR"
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

### Logs not appearing
- Check `thread_log_level` setting (default "INFO")
- Verify `remove_passing_logs` is not set to True
- Ensure methods use `_logger` parameter

## Future Enhancements

See [ROADMAP.md](ROADMAP.md) for the up-to-date list of completed work and future ideas.

## License

MIT. See [LICENSE](LICENSE).

## Support

For questions or issues, refer to:
- `src/parallelrunner/`: Core implementation
- `examples/custom_logger/`: Custom logger integration examples
- `tests/robot/`: Test examples
- `docs/`: User-facing documentation
