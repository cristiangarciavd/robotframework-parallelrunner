# API Reference

This page documents the public Robot Framework keyword exposed by
`parallelrunner.parallel_library.ParallelLibrary`, pulled directly from the
implementation in `src/parallelrunner/parallel_library.py`.

## `ParallelLibrary`

```python
from parallelrunner.parallel_library import ParallelLibrary
```

- `ROBOT_LIBRARY_SCOPE = 'GLOBAL'`
- Constructor takes no arguments. It reads the `ROBOT_THREAD_WORKERS`
  environment variable (default `4`) to size its internal
  `ThreadPoolExecutor`.

As a Robot Framework library:

```robot
*** Settings ***
Library    parallelrunner.parallel_library.ParallelLibrary
```

## `Run Parallel Scenarios`

Python signature:

```python
def run_parallel_scenarios(
    self,
    keyword: str,
    library: str,
    for_loop_iterable: Optional[Iterable[Any]] = None,
    repeat: Optional[int] = None,
    remove_passing_logs: bool = False,
    thread_log_level: str = "INFO",
    logger_mapper: Optional[Any] = None,
    **kwargs: Any,
) -> List[Dict[str, Any]]
```

Runs `keyword` once per item (or `repeat` times) on a thread pool, then replays
all captured logs into the Robot Framework log sequentially, so `log.html`
never gets corrupted by concurrent writes.

### Parameters

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `keyword` | `str` | Yes | - | Name of the method to call, Robot-keyword style (e.g. `Validate Agents Data With Steps`). It is converted internally to a Python method name via `.replace(" ", "_").lower()`, so it must resolve to an actual method on the target library instance. |
| `library` | `str` | Yes | - | Full dotted path to the Robot Framework library instance that owns `keyword`, exactly as it was imported in `*** Settings ***` (e.g. `examples.api_client.api_client.ApiClient`). Resolved via `BuiltIn().get_library_instance(library)`. |
| `for_loop_iterable` | `Iterable[Any]` or `None` | No | `None` | Items to process, one task per item. If provided, this takes precedence and each item is passed as the first positional argument to `keyword`. |
| `repeat` | `int` or `None` | No | `None` | If `for_loop_iterable` is not given, run the keyword this many times instead (`range(repeat or 1)`); the loop index is passed as the first positional argument. If neither `for_loop_iterable` nor `repeat` is given, the keyword runs exactly once (`range(1)`). |
| `remove_passing_logs` | `bool` | No | `False` | When `True`, only the log block for tasks with `status == "FAIL"` is replayed; passing tasks are skipped entirely (their result is still returned). |
| `thread_log_level` | `str` | No | `"INFO"` | Minimum level to replay: one of `"INFO"`, `"WARN"`, `"ERROR"`. Uses the ordering `INFO(1) < WARN(2) < ERROR(3)`; messages below the threshold are dropped. `"IGNORE"`-level messages are always dropped regardless of this setting. |
| `logger_mapper` | callable, `str`, or `None` | No | `None` | Custom logger adapter with signature `mapper(msg: str, level: str) -> None`. May be passed as a callable, or as a string module path (`"package.module.function"`) which is imported dynamically. If omitted, the library falls back to the `ROBOT_LOGGER_MAPPER` environment variable (see below). If neither is set, logs are captured internally and replayed through `robot.api.logger`. |
| `**kwargs` | `Any` | No | - | Any additional keyword arguments are forwarded verbatim to every call of `keyword`. |

### Return value

A `list` of per-task result dictionaries, in completion order (i.e.
`concurrent.futures.as_completed` order, not input order):

- On success: `{"status": "PASS", "item": <item>, "logs": [(level, msg), ...], "result": <return value of keyword>}`
- On failure (the method raised): `{"status": "FAIL", "item": <item>, "logs": [(level, msg), ...], "error": "<exception message>"}`

`item` is either the element from `for_loop_iterable` or the integer index
from `range(repeat)`.

### Environment variables

| Variable | Effect |
|---|---|
| `ROBOT_THREAD_WORKERS` | Number of worker threads used by the internal `ThreadPoolExecutor`. Default: `4`. Read once, at `ParallelLibrary.__init__`. |
| `ROBOT_LOGGER_MAPPER` | Global default for `logger_mapper` when the parameter is not passed explicitly. Accepts either a name registered via a mapper registry (see `examples/custom_logger/custom_logging_mapper.py::register_mapper`) or a dotted `module.function` path. An explicit `logger_mapper` argument always takes precedence over this variable. |

### Method contract for `keyword`

Any method targeted by `run_parallel_scenarios` should accept:

```python
def method_name(self, item, _logger: Optional[Callable] = None, **kwargs):
    log = _logger if _logger else default_log
    log("message", "INFO")   # or "WARN" / "ERROR" / "IGNORE"
    return result
```

- The first positional argument receives the current item (or repeat index).
- `_logger` is injected automatically by `ParallelLibrary` — inside a worker
  thread it is never `None`. Methods should still guard for direct
  (non-parallel) invocation by falling back to a default logger.
- Do **not** call `BuiltIn().run_keyword(...)` from inside the target method —
  it is not thread-safe. Call plain Python methods/functions instead.
- Return values are collected into the `"result"` field of the corresponding
  entry in the returned list.

### Internal helper methods

These are implementation details (prefixed with `_`), not part of the public
API, but documented here for maintainers:

- `_resolve_mapper(mapper)` - normalizes a callable-or-string mapper into a callable, or `None`.
- `_load_mapper_from_environment()` - reads and resolves `ROBOT_LOGGER_MAPPER`.
- `_get_library_instance_owning_keyword(keyword_name, library)` - resolves the Robot Framework library instance and validates that it has the target method.
- `_execute_and_capture(method, item, logger_mapper, **kwargs)` - worker-thread entry point; buffers logs and captures pass/fail results.
- `_replay_logs(results, remove_passing_logs, thread_log_level)` - replays buffered logs sequentially through `robot.api.logger`, applying filtering.

## Example

```robot
*** Settings ***
Library    parallelrunner.parallel_library.ParallelLibrary
Library    examples.api_client.api_client.ApiClient

*** Test Cases ***
Verify Agents In Parallel
    ${agents}=    Create List    1    2    3    4    5
    ${results}=    Run Parallel Scenarios
    ...    keyword=Verify Agent Data
    ...    library=examples.api_client.api_client.ApiClient
    ...    for_loop_iterable=${agents}
    ...    thread_log_level=WARN
    ...    remove_passing_logs=True
```

See `tests/robot/` for further worked examples, including custom logger
adapters and `ROBOT_LOGGER_MAPPER` usage.
