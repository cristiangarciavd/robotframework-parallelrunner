# Quickstart (5 minutes)

This walks through running the example suite that ships with the repository,
then writing your own minimal parallel test case.

## 1. Install

```bash
pip install -e ".[dev]"
```

See [INSTALLATION.md](INSTALLATION.md) for details.

## 2. Run the bundled example

The repository ships a small example API client
(`examples/api_client/api_client.py`) and a matching test suite
(`tests/robot/test_api.robot`) that hits a public test API
(`jsonplaceholder.typicode.com`) for a handful of fake "agent" IDs, both
sequentially and in parallel:

```bash
robot --pythonpath . --outputdir robot_results tests/robot/test_api.robot
```

Open `robot_results/log.html` and compare the `Verify Agents In Parallel`
and `Verify Agents Sequentially` test cases: both produce a clean,
readable log even though the parallel one ran 9 HTTP calls concurrently on a
thread pool.

## 3. Write your own minimal example

Create a tiny library with one method that follows the `_logger` injection
contract:

```python
# my_project/my_client.py
from typing import Callable, Optional

class MyClient:
    def process_item(self, item_id, _logger: Optional[Callable] = None, **kwargs):
        log = _logger if _logger else print
        log(f"Processing {item_id}", "INFO")
        if item_id == "bad":
            log(f"{item_id} failed validation", "ERROR")
            raise ValueError(f"Invalid item: {item_id}")
        return {"id": item_id, "status": "ok"}
```

Then a Robot Framework suite that parallelizes calls to it:

```robot
*** Settings ***
Library    parallelrunner.parallel_library.ParallelLibrary
Library    my_project.my_client.MyClient

*** Test Cases ***
Process Items In Parallel
    ${items}=    Create List    1    2    3    bad    5
    ${results}=    Run Parallel Scenarios
    ...    keyword=Process Item
    ...    library=my_project.my_client.MyClient
    ...    for_loop_iterable=${items}
    ...    remove_passing_logs=True
    Log    ${results}
```

Run it with `my_project` on the Python path:

```bash
robot --pythonpath . my_suite.robot
```

You'll get one `log.html` with a clearly grouped log block per item, plus a
`${results}` list containing a `PASS`/`FAIL` status, the item, captured logs,
and either the return value or the error message for each one — in call
order, so `${results}[0]` is always the first item/repeat call, regardless
of which thread happened to finish first.

## 4. Just want the return values?

If you don't need the status/logs envelope — you only care about what each
call returned — pass `return_values_only=True` to get a plain tuple instead,
in the same call order. This is the natural fit for `repeat`, since there's
no input list to zip results against:

```robot
*** Test Cases ***
Seed Three Fixture Records
    ${record1}    ${record2}    ${record3}=    Run Parallel Scenarios
    ...    keyword=Process Item
    ...    library=my_project.my_client.MyClient
    ...    repeat=3
    ...    return_values_only=True
```

If any of the N calls fails, this raises `ParallelTaskError` instead of
silently putting `None` in that slot — see
[API_REFERENCE.md](API_REFERENCE.md#get-result-values) for the standalone
`Get Result Values` keyword, useful when you want to inspect the full
result list before deciding whether to extract the values.

## Next steps

- [API_REFERENCE.md](API_REFERENCE.md) - full parameter reference for `Run Parallel Scenarios`.
- [../ARCHITECTURE.md](../ARCHITECTURE.md) - how the log buffering/replay mechanism works internally.
- `examples/custom_logger/` - adapting a project that already has its own custom/severity-based logger.
- `tests/robot/` - more worked examples (warnings, errors, log-level filtering, custom loggers).
