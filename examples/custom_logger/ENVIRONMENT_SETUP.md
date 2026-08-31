# Global Logger Mapper Configuration

## The Problem

Previously, you had to pass `logger_mapper` on **every single call** to `Run Parallel Scenarios`:

```robot
Run Parallel Scenarios
    ...    keyword=Validate With Custom Logger
    ...    library=examples.custom_logger.custom_logger_api_client.CustomLoggerApiClient
    ...    for_loop_iterable=${agents}
    ...    logger_mapper=custom_logger_adapter    # <- repeated on every test
```

**Downside:** with many tests and suites, this parameter gets repeated constantly.

## Solution: the `ROBOT_LOGGER_MAPPER` Environment Variable

You can now configure a mapper **globally** for the whole project. The library will pick it up automatically.

### Option 1: System Environment Variable

```bash
# Windows (PowerShell)
$env:ROBOT_LOGGER_MAPPER = "custom_logger_adapter"
robot --pythonpath . .

# Windows (CMD)
set ROBOT_LOGGER_MAPPER=custom_logger_adapter
robot --pythonpath . .

# Linux/Mac
export ROBOT_LOGGER_MAPPER=custom_logger_adapter
robot --pythonpath . .
```

### Option 2: Command-Line Variable

```bash
robot --pythonpath . --variable ROBOT_LOGGER_MAPPER:custom_logger_adapter .
```

### Option 3: In the Suite (Robot Framework)

```robot
*** Settings ***
Suite Setup    Set Environment Variable    ROBOT_LOGGER_MAPPER    custom_logger_adapter

*** Test Cases ***
Validate Users In Parallel
    # No need to pass logger_mapper anymore
    Run Parallel Scenarios
    ...    keyword=Validate With Custom Logger
    ...    library=examples.custom_logger.custom_logger_api_client.CustomLoggerApiClient
    ...    for_loop_iterable=${agents}
```

## Available Mappers

### 1. `custom_logger_adapter`

Built-in mapper for a severity-based custom logger (sv=0,1,2,3).

```python
from examples.custom_logger.custom_logging_mapper import custom_logger_adapter

# Automatically available as a registered mapper
```

**Handling sv=0 (IGNORE):**
- Logs with `"IGNORE"` as their level are excluded from the parallel replay
- Ideal for debug messages you don't want showing up in production logs

### 2. Creating Your Own Mapper

```python
# my_mappers.py
def my_custom_logger(msg, level="INFO"):
    """Adapter for your own custom log format."""
    level_map = {
        "INFO": "log_info",
        "WARN": "log_warn",
        "ERROR": "log_error",
        "IGNORE": "no_op",
    }

    func_name = level_map.get(level, "log_info")
    if func_name == "no_op":
        return  # Ignore IGNORE-level logs

    # Call your own logging system
    my_logging_system.emit(func_name, msg)
```

Then register it:

```python
# __init__.py or setup module
from examples.custom_logger.custom_logging_mapper import register_mapper
from my_mappers import my_custom_logger

register_mapper("my_custom_logger", my_custom_logger)
```

And use it:

```bash
export ROBOT_LOGGER_MAPPER=my_custom_logger
robot --pythonpath . .
```

### 3. Mapper by Full Module Path

```bash
# Use the full module path
robot --variable ROBOT_LOGGER_MAPPER:examples.custom_logger.custom_logging_mapper.custom_logger_adapter .
```

## Handling `sv=0` (IGNORE)

The special `"IGNORE"` level (which corresponds to sv=0) is **automatically filtered out** in:

1. **Direct execution:** if you call `log(msg, "IGNORE")`, it isn't recorded
2. **Parallel execution:** logs with `"IGNORE"` don't appear in the replay

Example:

```python
def validate_user(self, user_id: str, _logger=None, **kwargs):
    log = _logger if _logger else _create_local_logger()

    log(f"Starting validation", "INFO")      # visible
    log(f"Debug info: {user_id}", "IGNORE")  # not visible
    log(f"Warning!", "WARN")                 # visible
```

## How It Works

1. **Without an environment variable:**
   - `Run Parallel Scenarios` without `logger_mapper` uses the standard buffer + replay mechanism.

2. **With the environment variable:**
   - `ParallelLibrary` detects `ROBOT_LOGGER_MAPPER`.
   - It looks up the registered mapper or imports the module.
   - It injects the mapper into every worker thread.
   - Logs are filtered automatically (sv=0 excluded).

3. **With an explicit parameter:**
   - The `logger_mapper=...` parameter takes **priority** over the environment variable.
   - This lets you override the global configuration when needed.

## Full Example

### Project Structure

```
my_project/
├── tests/
│   ├── test_users.robot
│   └── test_agents.robot
├── lib/
│   ├── api_client.py
│   └── loggers/
│       ├── __init__.py
│       └── custom_adapter.py
└── robot.config
```

### Adapter Code

```python
# lib/loggers/custom_adapter.py
from examples.custom_logger.custom_logging_mapper import register_mapper

def project_logger(msg, level="INFO"):
    """Custom adapter for my project."""
    severity_map = {
        "INFO": 1,
        "WARN": 2,
        "ERROR": 3,
        "IGNORE": 0,
    }
    sv = severity_map.get(level, 1)

    if sv == 0:
        return  # Ignore

    # My own logging system
    print(f"[PROJECT-{level}] {msg}")

register_mapper("project_logger", project_logger)
```

### Suite Configuration

```robot
*** Settings ***
Library    parallelrunner.parallel_library.ParallelLibrary
Library    my_project.lib.api_client.ApiClient
Suite Setup    Set Environment Variable    ROBOT_LOGGER_MAPPER    project_logger

*** Test Cases ***
Validate Users Parallel
    [Documentation]    No need to pass logger_mapper
    ${users}=    Create List    1    2    3    4    5
    Run Parallel Scenarios
    ...    keyword=Validate User
    ...    library=my_project.lib.api_client.ApiClient
    ...    for_loop_iterable=${users}
```

### Running It

```bash
# Option 1: auto-detected from Suite Setup
robot --pythonpath . tests/

# Option 2: pass the environment variable
export ROBOT_LOGGER_MAPPER=project_logger
robot --pythonpath . tests/

# Option 3: command line
robot --pythonpath . --variable ROBOT_LOGGER_MAPPER:project_logger tests/
```

## Benefits

- **One mapper per project** - no need to repeat it on every test
- **Zero changes to existing suites** - fully backward compatible
- **Automatic sv=0 filtering** - IGNORE logs never pollute the output
- **Flexible** - an explicit parameter can override the global setting
- **Debuggable** - easy to configure and verify

## Debugging

### See which mapper is active

```python
# In your code
from examples.custom_logger.custom_logging_mapper import get_global_mapper
mapper = get_global_mapper()
print(f"Current mapper: {mapper}")
```

### Check the mapper registry

```python
from examples.custom_logger.custom_logging_mapper import _MAPPER_REGISTRY
print(f"Available mappers: {list(_MAPPER_REGISTRY.keys())}")
```

### No mapper (default value)

If you don't configure `ROBOT_LOGGER_MAPPER`:
- `ParallelLibrary` uses the standard buffer + replay mechanism.
- All logs are included.
- Perfectly valid for projects without a custom logger.
