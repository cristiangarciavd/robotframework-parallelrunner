"""
Custom logging mapper that adapts custom logger format to ParallelRunner's standard format.
This mapper converts severity numeric codes (sv=0,1,2,3) to standard level strings (INFO, WARN, ERROR).

Supports:
1. Local adaptation: _create_local_logger() for use in methods
2. Global mappers: Custom loggers registered and accessible by name
3. sv=0 handling: Logs with sv=0 (IGNORE) are filtered out in parallel execution
4. Environment variables: Set ROBOT_LOGGER_MAPPER to use a mapper globally across all suites
"""

import os
from examples.custom_logger.custom_logger import log_custom_message
from typing import Callable, Optional, Dict

# Global registry of available mappers
_MAPPER_REGISTRY: Dict[str, Callable] = {}


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
    
    Example:
        mapper = create_custom_logging_mapper()
        # Use with ParallelRunner:
        # Run Parallel Scenarios    keyword=...    logger_mapper=${mapper}
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
    Can be passed as logger_mapper to ParallelRunner or set as ROBOT_LOGGER_MAPPER.
    
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


def register_mapper(name: str, mapper: Callable) -> None:
    """
    Register a custom logger mapper by name for global use.
    
    Args:
        name (str): Name to register the mapper under (e.g., "custom_logger_adapter").
        mapper (Callable): Mapper function with signature (msg: str, level: str) -> None
    
    Example:
        from examples.custom_logger.custom_logger import custom_logger_adapter
        register_mapper("my_custom_logger", custom_logger_adapter)
        
        # Then in Robot Framework suite setup:
        # Set Environment Variable    ROBOT_LOGGER_MAPPER    my_custom_logger
    """
    _MAPPER_REGISTRY[name] = mapper


def get_mapper_by_name(name: str) -> Optional[Callable]:
    """
    Retrieve a registered mapper by name.
    
    Args:
        name (str): The name of the registered mapper.
    
    Returns:
        Callable: The mapper function, or None if not found.
    """
    return _MAPPER_REGISTRY.get(name)


def get_global_mapper() -> Optional[Callable]:
    """
    Get the global mapper configured via ROBOT_LOGGER_MAPPER environment variable.
    
    Returns:
        Callable: The mapper function if configured, None otherwise.
    
    Environment variable format:
        - ROBOT_LOGGER_MAPPER=custom_logger_adapter (looks up registered mapper)
        - ROBOT_LOGGER_MAPPER=module.path.function (imports and uses the function)
    
    Example:
        # In robot suite setup or command line:
        robot --variable ROBOT_LOGGER_MAPPER:custom_logger_adapter test.robot
        
        # Or in suite settings:
        *** Settings ***
        Suite Setup    Set Environment Variable    ROBOT_LOGGER_MAPPER    custom_logger_adapter
    """
    mapper_name = os.getenv("ROBOT_LOGGER_MAPPER")
    
    if not mapper_name:
        return None
    
    # First, check if it's a registered mapper
    if mapper_name in _MAPPER_REGISTRY:
        return _MAPPER_REGISTRY[mapper_name]
    
    # Try to import it as a module path
    try:
        parts = mapper_name.rsplit(".", 1)
        if len(parts) == 2:
            module_name, func_name = parts
            module = __import__(module_name, fromlist=[func_name])
            mapper = getattr(module, func_name, None)
            if callable(mapper):
                return mapper
    except (ImportError, AttributeError):
        pass
    
    return None


# Register the built-in mapper on module load
register_mapper("custom_logger_adapter", custom_logger_adapter)
register_mapper("create_custom_logging_mapper", create_custom_logging_mapper())
