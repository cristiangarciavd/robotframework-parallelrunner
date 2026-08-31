"""
Custom logger with severity-based logging (sv=0,1,2,3).
Useful for adapting existing projects with custom logging formats.

Severity levels:
- sv=0: No log (ignored)
- sv=1: INFO (default)
- sv=2: WARN
- sv=3: ERROR
"""

def log_custom_message(msg, sv=1):
    """
    Custom logging function using severity numeric codes.
    
    Args:
        msg (str): The message to log.
        sv (int): Severity level (0=ignored, 1=info, 2=warn, 3=error). Default 1.
    
    Example:
        log_custom_message("Processing started", sv=1)  # INFO
        log_custom_message("Missing field", sv=2)  # WARN
        log_custom_message("Critical failure", sv=3)  # ERROR
        log_custom_message("Debug info", sv=0)  # Ignored
    """
    severity_names = {0: "IGNORE", 1: "INFO", 2: "WARN", 3: "ERROR"}
    severity_name = severity_names.get(sv, "INFO")
    
    if sv == 0:
        return  # Ignore this log
    
    # In a real project, this could write to a file, database, etc.
    print(f"[{severity_name}] {msg}")
