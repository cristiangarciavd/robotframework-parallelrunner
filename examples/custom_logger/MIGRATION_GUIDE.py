"""
QUICK START: Adapting Existing Projects to ParallelRunner

This guide shows the MINIMAL changes needed to adapt an existing project
with custom logging to work with ParallelRunner.
"""

# ==============================================================================
# SCENARIO: You have an existing project with custom logger
# ==============================================================================

# EXISTING CODE (Before ParallelRunner)
# -----------

from examples.custom_logger.custom_logger import log_custom_message

class MyExistingClient:
    def validate_user(self, user_id):
        """Your existing method with custom logger."""
        log_custom_message(f"Validating user {user_id}", sv=1)
        
        # Your business logic
        result = fetch_user_data(user_id)
        
        if not result.get("email"):
            log_custom_message(f"User {user_id} missing email", sv=2)
        
        log_custom_message(f"Validation complete for {user_id}", sv=1)
        return result


# ==============================================================================
# ADAPTED CODE (For ParallelRunner)
# ==============================================================================

from typing import Callable, Optional
from examples.custom_logger.custom_logger import log_custom_message


def _create_local_logger():
    """
    STEP 1: Create this wrapper once in your project.
    Maps standard level strings to your custom logger format.
    """
    def local_log(msg, level="INFO"):
        severity_map = {"INFO": 1, "WARN": 2, "ERROR": 3}
        sv = severity_map.get(level, 1)
        log_custom_message(msg, sv=sv)
    return local_log


class MyAdaptedClient:
    def validate_user(self, user_id: str, _logger: Optional[Callable] = None, **kwargs):
        """
        STEP 2: Add _logger parameter and one line.
        
        Changes made:
        1. Add _logger parameter: _logger: Optional[Callable] = None
        2. Add **kwargs for ParallelRunner compatibility
        3. Add ONE line: log = _logger if _logger else _create_local_logger()
        
        That's it! The rest of the code can use standard level strings.
        """
        # ← This one line! Everything else stays the same.
        log = _logger if _logger else _create_local_logger()
        
        # Now use standard levels - works in BOTH parallel and direct execution
        log(f"Validating user {user_id}", "INFO")
        
        # Your business logic
        result = fetch_user_data(user_id)
        
        if not result.get("email"):
            log(f"User {user_id} missing email", "WARN")
        
        log(f"Validation complete for {user_id}", "INFO")
        return result


# ==============================================================================
# USAGE
# ==============================================================================

# Direct execution (unchanged, works as before)
# client = MyAdaptedClient()
# result = client.validate_user("user123")

# Parallel execution (new capability)
"""
*** Robot Framework ***
Library    ParallelRunner
Library    your_project.my_client.MyAdaptedClient

*** Test Cases ***
Validate Users In Parallel
    ${users}=    Create List    user1    user2    user3    user4    user5
    Run Parallel Scenarios    
    ...    keyword=Validate User
    ...    library=your_project.my_client.MyAdaptedClient
    ...    for_loop_iterable=${users}
"""


# ==============================================================================
# KEY INSIGHTS
# ==============================================================================

"""
1. MINIMAL CHANGES:
   - Add _logger parameter
   - Add **kwargs
   - Add ONE line in method: log = _logger if _logger else _create_local_logger()

2. NO CONDITIONALS IN METHODS:
   - Before: if _logger: ... else: ...  (repeated everywhere)
   - After:  Just one log setup line at the top

3. STANDARD LEVEL STRINGS:
   - Your code now uses "INFO", "WARN", "ERROR"
   - Internally mapped to sv=1, sv=2, sv=3
   - Clear and consistent throughout

4. WORKS EVERYWHERE:
   - Direct execution: _logger is None, uses local_logger wrapper
   - Parallel execution: _logger is injected by ParallelRunner
   - Same code path, same results

5. MAINTAINABLE:
   - Single log() call throughout
   - No duplicated logic
   - Easy to read and understand
"""
