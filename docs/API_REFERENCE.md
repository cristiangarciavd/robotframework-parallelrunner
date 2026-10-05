# API Reference

This page documents the public Robot Framework keyword exposed by
`ParallelRunner`, pulled directly from the
implementation in `src/ParallelRunner/parallel_library.py`.

## `ParallelRunner`

```python
from ParallelRunner import ParallelRunner
```

- `ROBOT_LIBRARY_SCOPE = 'GLOBAL'`
- Constructor takes no arguments. It reads the `ROBOT_THREAD_WORKERS`
  environment variable (default `4`) to size its internal
  `ThreadPoolExecutor`.

As a Robot Framework library:

```robot
*** Settings ***
Library    ParallelRunner
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
    return_values_only: bool = False,
    **kwargs: Any,
) -> Union[List[Dict[str, Any]], Tuple[Any, ...]]
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
| `repeat` | `int` or `None` | No | `None` | If `for_loop_iterable` is not given, run the keyword this many times instead (`range(repeat)`); the loop index is passed as the first positional argument. An explicit `repeat=0` runs zero times (an empty result list), same as passing `for_loop_iterable=${EMPTY_LIST}` — it is not treated as "not given". If `repeat` itself is not given (`None`) and neither is `for_loop_iterable`, the keyword runs exactly once (`range(1)`). Use this when there's no pre-existing list of items — e.g. creating N independent test records in parallel, or firing N concurrent calls at one fixed endpoint — see `atest/test_repeat.robot` for worked examples of both. |
| `remove_passing_logs` | `bool` | No | `False` | When `True`, only the log block for tasks with `status == "FAIL"` is replayed; passing tasks are skipped entirely (their result is still returned). |
| `thread_log_level` | `str` | No | `"INFO"` | Minimum level to replay: one of `"INFO"`, `"WARN"`, `"ERROR"`. Uses the ordering `INFO(1) < WARN(2) < ERROR(3)`; messages below the threshold are dropped. `"IGNORE"`-level messages are always dropped regardless of this setting. |
| `logger_mapper` | callable, `str`, or `None` | No | `None` | Custom logger adapter with signature `mapper(msg: str, level: str) -> None`. May be passed as a callable, or as a string module path (`"package.module.function"`) which is imported dynamically. Bare names without a module path (e.g. `"custom_logger_adapter"`) are not supported. A value that can't be resolved (bare name, module that can't be imported, missing or non-callable attribute) is ignored with a warning in the log, and the library then falls back to the `ROBOT_LOGGER_MAPPER` environment variable (see below). If neither resolves, logs are captured internally and replayed through `robot.api.logger`. A mapper's messages are not buffered or replayed, so `thread_log_level` and `remove_passing_logs` don't apply to them; it is called from several threads at once and must be thread-safe. |
| `return_values_only` | `bool` | No | `False` | When `True`, return a plain `tuple` of each call's return value - in call order - instead of the list of result dictionaries. Raises `ParallelTaskError` if any task failed (there is no meaningful value to put in its slot). This is the natural pairing with `repeat`: since there's no input list to zip results against, unpacking directly into N variables is often more convenient than indexing into a list of dicts - e.g. `${id1}    ${id2}    ${id3}=    Run Parallel Scenarios    ...    repeat=3    return_values_only=True`. Equivalent to calling `Get Result Values` on the default (dict-list) return value. |
| `**kwargs` | `Any` | No | - | Any additional keyword arguments are forwarded verbatim to every call of `keyword`. |

### Return value

**Default (`return_values_only=False`):** a `list` of per-task result
dictionaries, **in call order** - `results[i]` corresponds to
`for_loop_iterable[i]`, or to repeat index `i`. All tasks still run
concurrently; only the order results are *collected* in is affected, so this
holds regardless of which thread happens to finish first.

> Prior to `return_values_only` being added, this list was collected in
> `concurrent.futures.as_completed` (completion) order instead of call order.
> That was a real ordering gap for direct indexing - see `CHANGELOG.md`.

- On success: `{"status": "PASS", "item": <item>, "logs": [(level, msg), ...], "result": <return value of keyword>}`
- On failure (the method raised): `{"status": "FAIL", "item": <item>, "logs": [(level, msg), ...], "error": "<exception message>"}`

`item` is either the element from `for_loop_iterable` or the integer index
from `range(repeat)`.

**With `return_values_only=True`:** a plain `tuple` of each task's `result`
value, in the same call order described above. Raises `ParallelTaskError`
(see below) instead of returning anything if any task failed.

### Environment variables

| Variable | Effect |
|---|---|
| `ROBOT_THREAD_WORKERS` | Number of worker threads used by the internal `ThreadPoolExecutor`. Default: `4`. Read once, at `ParallelRunner.__init__`. |
| `ROBOT_LOGGER_MAPPER` | Global default for `logger_mapper` when the parameter is not passed explicitly. Must be a dotted `module.function` path (e.g. `examples.custom_logger.custom_logging_mapper.custom_logger_adapter`); a bare name is ignored with a warning. It must be a real environment variable (shell, or `Set Environment Variable` in a Suite Setup): a Robot variable given with `--variable` is not read. A resolvable `logger_mapper` argument always takes precedence over this variable. |

### Method contract for `keyword`

Any method targeted by `run_parallel_scenarios` should accept:

```python
def method_name(self, item, _logger: Optional[Callable] = None, **kwargs):
    log = _logger if _logger else default_log
    log("message", "INFO")   # or "WARN" / "ERROR" / "IGNORE"
    return result
```

- The first positional argument receives the current item (or repeat index).
- `_logger` is injected automatically by `ParallelRunner` — inside a worker
  thread it is never `None`. Methods should still guard for direct
  (non-parallel) invocation by falling back to a default logger.
- Do **not** call `BuiltIn().run_keyword(...)` from inside the target method —
  it is not thread-safe. Call plain Python methods/functions instead.
- Return values are collected into the `"result"` field of the corresponding
  entry in the returned list.

## `Get Result Values`

Python signature:

```python
def get_result_values(self, results: List[Dict[str, Any]]) -> Tuple[Any, ...]
```

Extracts each task's `"result"` value out of a `run_parallel_scenarios`
result list, preserving call order (`results[i]` → tuple index `i`). This is
exactly what `return_values_only=True` does internally; use this standalone
form when you want to inspect the full dict list first (e.g. assert on
`status` or `logs`) before extracting the plain values, instead of getting
the tuple in one step.

```robot
${results}=    Run Parallel Scenarios    keyword=Seed Fixture Record    library=${lib}    repeat=3
${id1}    ${id2}    ${id3}=    Get Result Values    ${results}
```

Raises `ParallelTaskError` if any entry in `results` has `status == "FAIL"`.

## `ParallelTaskError`

```python
from ParallelRunner import ParallelTaskError
```

Raised by `Get Result Values` and by `Run Parallel Scenarios` (when called
with `return_values_only=True`) if at least one task failed. A failed task
has no return value, so raising loudly here - instead of silently
substituting `None` - is what makes a test relying on `return_values_only`
fail for the right reason instead of continuing with a hole in the data.

- Subclass of `RuntimeError`.
- `.failures`: the subset of result dicts with `status == "FAIL"`, in the
  order they appear in the full result list. Each has the usual `item`,
  `logs`, and `error` keys (see the `FAIL` shape under **Return value**
  above).
- `str(error)`: a human-readable summary, e.g.
  `"2 of 5 parallel task(s) failed: item=4: Simulated error for agent 4; item=5: Simulated error for agent 5"`.

### Internal helper methods

These are implementation details (prefixed with `_`), not part of the public
API, but documented here for maintainers:

- `_resolve_mapper(mapper, source)` - normalizes a callable-or-`module.function` mapper into a callable; returns `None` when nothing was given, and logs a warning (naming `source`) when a given value can't be resolved.
- `_load_mapper_from_environment()` - reads and resolves `ROBOT_LOGGER_MAPPER`.
- `_get_library_instance_owning_keyword(keyword_name, library)` - resolves the Robot Framework library instance and validates that it has the target method.
- `_execute_and_capture(method, item, logger_mapper, **kwargs)` - worker-thread entry point; buffers logs and captures pass/fail results.
- `_replay_logs(results, remove_passing_logs, thread_log_level)` - replays buffered logs sequentially through `robot.api.logger`, applying filtering.

## Examples

```robot
*** Settings ***
Library    ParallelRunner
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

Seeding N independent fixture rows with `repeat`, and getting each row's
generated id back directly via `return_values_only` (see
`examples/db_seed/db_seed_client.py` and `atest/test_return_values.robot`):

```robot
*** Settings ***
Library    ParallelRunner
Library    examples.db_seed.db_seed_client.DbSeedClient
Suite Setup    Initialize Schema

*** Test Cases ***
Seed Fixture Rows In Parallel
    ${id1}    ${id2}    ${id3}=    Run Parallel Scenarios
    ...    keyword=Seed Fixture Record
    ...    library=examples.db_seed.db_seed_client.DbSeedClient
    ...    repeat=3
    ...    name_prefix=order
    ...    return_values_only=True
```

Post-deployment smoke test across several different service routes, using
`return_values_only` to get back a plain tuple of status codes:

```robot
*** Test Cases ***
Smoke Test Routes After Deploy
    @{routes}=    Create List    users/1    posts/1    albums/1
    ${status_codes}=    Run Parallel Scenarios
    ...    keyword=Smoke Test Endpoint
    ...    library=examples.api_client.api_client.ApiClient
    ...    for_loop_iterable=${routes}
    ...    return_values_only=True
    FOR    ${code}    IN    @{status_codes}
        Should Be Equal As Integers    ${code}    200
    END
```

See `atest/` for further worked examples, including custom logger
adapters and `ROBOT_LOGGER_MAPPER` usage.
