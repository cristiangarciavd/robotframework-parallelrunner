# CustomLogger - Adapter Example

This directory demonstrates how to adapt projects with custom logging formats to work with **ParallelRunner** with **minimal code changes**.

## Overview

`ParallelRunner` uses standard log levels ("INFO", "WARN", "ERROR"), but existing projects may use custom logging formats (e.g., severity codes: `sv=1, sv=2, sv=3`).

The key insight: **Create a local wrapper function that converts standard levels to your custom format**. This way, your method code remains identical regardless of whether it's called directly or in parallel.

## Solution Pattern

### 1. Create a Local Logger Wrapper

```python
def _create_local_logger():
    """Adapts custom logger format to standard level strings."""
    def local_log(msg, level="INFO"):
        severity_map = {"INFO": 1, "WARN": 2, "ERROR": 3}
        sv = severity_map.get(level, 1)
        log_custom_message(msg, sv=sv)  # Your custom logger
    return local_log
```

### 2. Use It in Your Methods

```python
def my_method(self, item_id: str, _logger: Optional[Callable] = None, **kwargs):
    # That's it! One line replaces all the conditional logic
    log = _logger if _logger else _create_local_logger()
    
    # Now use standard levels - works in both parallel and direct execution
    log("Processing started", "INFO")
    log("Warning detected", "WARN")
    log("Error occurred", "ERROR")
    
    return result
```

**No conditionals needed!** The same log calls work everywhere.

## Before vs After

### Before (Complex)
```python
def method(self, item_id: str, _logger=None, **kwargs):
    if _logger:
        _logger(f"Processing {item_id}", "INFO")
    else:
        log_custom_message(f"Processing {item_id}", sv=1)
    
    if _logger:
        _logger("Warning", "WARN")
    else:
        log_custom_message("Warning", sv=2)
```

### After (Simple)
```python
def method(self, item_id: str, _logger=None, **kwargs):
    log = _logger if _logger else _create_local_logger()
    
    log(f"Processing {item_id}", "INFO")
    log("Warning", "WARN")
```

## Files

- **custom_logger.py**: Severity-based logging function (sv=0,1,2,3)
- **custom_logging_mapper.py**: Mapper to convert standard levels to custom format (for ParallelRunner)
- **custom_logger_api_client.py**: Example implementation showing the clean pattern

## Usage in Your Project

### Step 1: Create Your Wrapper

In your existing project, add this function:

```python
# my_project/my_logger_wrapper.py

from your_custom_logger import log_custom_message

def _create_local_logger():
    """Adapter from standard levels to your custom logger."""
    def local_log(msg, level="INFO"):
        level_to_severity = {"INFO": 1, "WARN": 2, "ERROR": 3}
        severity = level_to_severity.get(level, 1)
        log_custom_message(msg, sv=severity)
    return local_log
```

### Step 2: Update Your Methods

**Minimal changes**:

```python
# Before
def process(self, item_id):
    log_custom_message("Starting", sv=1)
    ...

# After (add one line)
def process(self, item_id: str, _logger: Optional[Callable] = None, **kwargs):
    log = _logger if _logger else _create_local_logger()  # ← This one line!
    log("Starting", "INFO")  # ← Same call as before
    ...
```

### Step 3: Use with ParallelRunner

```robot
*** Test Cases ***
Process In Parallel
    ${items}=    Create List    1    2    3    4    5
    Run Parallel Scenarios    
    ...    keyword=Process
    ...    library=my_project.my_client.MyClient
    ...    for_loop_iterable=${items}
```

**That's all!** Your methods work in both contexts without extra logic.

## Testing

Run the example tests to see this pattern in action:

```bash
robot --pythonpath . tests/robot/test_custom_logger.robot
```

## Why This Approach

✅ **Minimal invasiveness**: One line per method  
✅ **No conditionals**: Clean, readable code  
✅ **Works everywhere**: Direct execution or parallel  
✅ **Easy migration**: Existing projects adapt quickly  
✅ **Maintainable**: Standard level strings in your code  

## Key Files in Example

- `custom_logger_api_client.py`: See how methods implement the pattern
- Tests demonstrate parallel execution with custom logger

