"""
Custom logging mapper that adapts a custom logger format to ParallelRunner's standard format.
This mapper converts standard level strings (INFO, WARN, ERROR, IGNORE) to severity
numeric codes (sv=1,2,3,0).

Supports:
1. Local adaptation: _create_local_logger() for use in methods
2. A ready-made mapper for ParallelRunner: custom_logger_adapter
3. sv=0 handling: logs with level IGNORE (sv=0) are dropped

ParallelRunner resolves a mapper given as a callable or as a full
`module.function` path, either with the `logger_mapper` argument or the
ROBOT_LOGGER_MAPPER environment variable, e.g.:

    examples.custom_logger.custom_logging_mapper.custom_logger_adapter

Bare names such as "custom_logger_adapter" are not supported (they are ignored
with a warning).
"""

from examples.custom_logger.custom_logger import log_custom_message
from typing import Callable


def _create_local_logger() -> Callable:
    """
    Creates a wrapper logger for use WITHIN existing project methods.
    
    Use this in your methods to adapt custom logger format to standard level strings.
    This allows identical code in both direct execution and parallel execution.
    
    Returns:
        Callable: A logger function with signature (msg, level="INFO") -> None
    
    Example in your existing code:
        def validate_user(self, user_id: str, _logger: Optional[Callable] = None, **kwargs):
            # This ONE line is all you need to add
            log = _logger if _logger else _create_local_logger()
            
            # Then use it with standard levels everywhere
            log(f"Validating user {user_id}", "INFO")
            log("Warning detected", "WARN")
            log("Critical error", "ERROR")
            
            # Logs with sv=0 (IGNORE) are automatically filtered
    """
    def local_log(msg: str, level: str = "INFO"):
        severity_map = {
            "INFO": 1,
            "WARN": 2,
            "ERROR": 3,
            "IGNORE": 0,  # sv=0 is explicitly ignored
        }
        sv = severity_map.get(level, 1)
        if sv == 0:
            return  # Don't log ignored messages
        log_custom_message(msg, sv=sv)
    return local_log


def create_custom_logging_mapper() -> Callable:
    """
    Factory function that creates a logger mapper for custom severity-based logging.
    
    Returns:
        Callable: A mapper function that converts (msg, level) to custom logger format (sv=n).
        Automatically filters sv=0 (IGNORE) logs.
    
    Example (Python, passing the callable itself):
        mapper = create_custom_logging_mapper()
        ParallelRunner().run_parallel_scenarios(..., logger_mapper=mapper)
    """
    
    def map_to_custom_logger(msg: str, level: str = "INFO"):
        """
        Maps standard level strings to custom severity codes.
        Filters out IGNORE (sv=0) logs.
        
        Args:
            msg (str): The message to log.
            level (str): Standard level ("INFO", "WARN", "ERROR", "IGNORE").
        """
        severity_map = {
            "INFO": 1,
            "WARN": 2,
            "ERROR": 3,
            "IGNORE": 0,
        }
        sv = severity_map.get(level, 1)  # Default to INFO (sv=1)
        
        if sv == 0:
            return  # Don't log ignored messages
            
        log_custom_message(msg, sv=sv)
    
    return map_to_custom_logger


def custom_logger_adapter(msg: str, level: str = "INFO"):
    """
    Directly adapts standard level to custom severity logger.
    Pass it to ParallelRunner by its full path, as logger_mapper or as the
    ROBOT_LOGGER_MAPPER environment variable:
    examples.custom_logger.custom_logging_mapper.custom_logger_adapter
    
    Automatically filters sv=0 (IGNORE) logs from parallel execution.
    
    Args:
        msg (str): The message to log.
        level (str): Standard level ("INFO", "WARN", "ERROR", "IGNORE").
    """
    severity_map = {
        "INFO": 1,
        "WARN": 2,
        "ERROR": 3,
        "IGNORE": 0,
    }
    sv = severity_map.get(level, 1)
    
    if sv == 0:
        return  # Don't log ignored messages
        
    log_custom_message(msg, sv=sv)
