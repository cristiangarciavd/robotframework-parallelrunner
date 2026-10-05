# Global Logger Mapper Configuration

## The Problem

Passing `logger_mapper` on **every single call** to `Run Parallel Scenarios`
gets repetitive in projects with many tests and suites:

```robot
Run Parallel Scenarios
    ...    keyword=Validate With Custom Logger
    ...    library=examples.custom_logger.custom_logger_api_client.CustomLoggerApiClient
    ...    for_loop_iterable=${agents}
    ...    logger_mapper=examples.custom_logger.custom_logging_mapper.custom_logger_adapter    # <- repeated on every test
```

## Solution: the `ROBOT_LOGGER_MAPPER` Environment Variable

Set a mapper **once** for the whole run, and ParallelRunner uses it whenever
`logger_mapper` is not given.

Two rules:

- **The value must be a full `module.function` path**, e.g.
  `examples.custom_logger.custom_logging_mapper.custom_logger_adapter`.
  Bare names such as `custom_logger_adapter` are not supported: ParallelRunner
  ignores them with a warning in the log and uses its default logger.
- **It must be a real environment variable.** A Robot Framework variable
  passed with `robot --variable ROBOT_LOGGER_MAPPER:...` is *not* read.

### Option 1: Shell Environment Variable

```bash
# Linux/Mac
export ROBOT_LOGGER_MAPPER=examples.custom_logger.custom_logging_mapper.custom_logger_adapter
robot --pythonpath . atest/

# Windows (PowerShell)
$env:ROBOT_LOGGER_MAPPER = "examples.custom_logger.custom_logging_mapper.custom_logger_adapter"
robot --pythonpath . atest/

# Windows (CMD)
set ROBOT_LOGGER_MAPPER=examples.custom_logger.custom_logging_mapper.custom_logger_adapter
robot --pythonpath . atest/
```

### Option 2: In the Suite (Robot Framework)

```robot
*** Settings ***
Library           OperatingSystem
Library           ParallelRunner
Library           examples.custom_logger.custom_logger_api_client.CustomLoggerApiClient
Suite Setup       Set Environment Variable    ROBOT_LOGGER_MAPPER    examples.custom_logger.custom_logging_mapper.custom_logger_adapter
Suite Teardown    Remove Environment Variable    ROBOT_LOGGER_MAPPER

*** Test Cases ***
Validate Users In Parallel
    # No need to pass logger_mapper anymore
    ${agents}=    Create List    1    2    3
    Run Parallel Scenarios
    ...    keyword=Validate With Custom Logger
    ...    library=examples.custom_logger.custom_logger_api_client.CustomLoggerApiClient
    ...    for_loop_iterable=${agents}
```

Environment variables are process-wide: the `Suite Teardown` keeps the mapper
from leaking into suites that run afterwards. `atest/test_custom_logger_with_env.robot`
is a working example.

## Available Mappers

### 1. `custom_logger_adapter`

Ready-made mapper for the severity-based custom logger in this folder
(sv=0,1,2,3). Its full path is:

```
examples.custom_logger.custom_logging_mapper.custom_logger_adapter
```

`IGNORE`-level messages (sv=0) are dropped, which is handy for debug
messages you don't want in production logs.

### 2. Your Own Mapper

A mapper is any function with the signature `mapper(msg, level="INFO")`:

```python
# my_project/loggers.py
def project_logger(msg, level="INFO"):
    """Adapter for my own logging system."""
    if level == "IGNORE":
        return
    my_logging_system.emit(level, msg)
```

Use it by its full path, as long as the module is importable (for example
with `--pythonpath .`):

```bash
export ROBOT_LOGGER_MAPPER=my_project.loggers.project_logger
robot --pythonpath . tests/
```

## Handling `sv=0` (IGNORE)

The special `"IGNORE"` level (sv=0) is dropped:

1. **Direct execution:** `_create_local_logger()` doesn't log it.
2. **Parallel execution, default logger:** IGNORE messages aren't replayed.
3. **Parallel execution, with a mapper:** the mappers in this folder drop it;
   your own mapper should too.

```python
def validate_user(self, user_id: str, _logger=None, **kwargs):
    log = _logger if _logger else _create_local_logger()

    log("Starting validation", "INFO")      # visible
    log(f"Debug info: {user_id}", "IGNORE")  # not visible
    log("Warning!", "WARN")                 # visible
```

## How It Works

1. **No mapper configured:** `Run Parallel Scenarios` uses the default
   logger. Each thread's messages are buffered and replayed in order into
   `log.html`, filtered by `thread_log_level` and `remove_passing_logs`.
2. **`logger_mapper` argument:** used if it resolves (a callable or a
   `module.function` path). It takes priority over the environment variable.
3. **`ROBOT_LOGGER_MAPPER`:** used when the argument is not given, or when the
   argument can't be resolved (ParallelRunner logs a warning and falls back).
4. **Neither resolves:** default logger, with a warning for any value that
   was given but couldn't be resolved.

When a mapper is used, it is injected as `_logger` into every worker thread
and **its messages go straight to your logging system**: they are not
buffered or replayed into `log.html`, so `thread_log_level` and
`remove_passing_logs` don't apply to them. The mapper is called from several
threads at once, so it must be thread-safe.

## Debugging

- **Was my mapper used?** If ParallelRunner can't resolve the value, the log
  shows a warning such as:
  `Ignoring ROBOT_LOGGER_MAPPER 'custom_logger_adapter': expected a 'module.function' path such as 'my_package.my_module.my_mapper'.`
  No warning means the mapper was resolved and used.
- **Check the path from Python:**
  ```bash
  python -c "import examples.custom_logger.custom_logging_mapper as m; print(m.custom_logger_adapter)"
  ```
- **Check the variable is really in the environment** (not a `--variable`):
  `echo $ROBOT_LOGGER_MAPPER` (or `$env:ROBOT_LOGGER_MAPPER` in PowerShell).
