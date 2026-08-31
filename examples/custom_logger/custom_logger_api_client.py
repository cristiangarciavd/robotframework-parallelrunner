"""
Example API client demonstrating custom logger integration.
Shows how to adapt existing code with custom loggers to work with ParallelRunner.
"""

import requests
from typing import Callable, Optional
from examples.custom_logger.custom_logging_mapper import _create_local_logger
import time


class CustomLoggerApiClient:
    """API client using custom severity-based logging (sv=0,1,2,3)."""

    def validate_with_custom_logger(self, agent_id: str, _logger: Optional[Callable] = None, **kwargs) -> dict:
        """
        Validates agent data using custom logger with severity codes.
        This demonstrates how to adapt existing code with custom loggers.
        
        Args:
            agent_id: Agent ID to validate.
            _logger: Custom logger function (injected by ParallelRunner).
                    Expected signature: _logger(msg, level) where level is "INFO", "WARN", or "ERROR".
        """
        # Use injected logger (from ParallelRunner) or local wrapper that adapts custom format
        # Both use the same standard level strings ("INFO", "WARN", "ERROR")
        log = _logger if _logger else _create_local_logger()
        
        log(f"Starting validation for Agent ID: {agent_id}", "INFO")
        
        # Example using JSONPlaceholder API
        url = f"https://jsonplaceholder.typicode.com/users/{agent_id}"
        response = requests.get(url, timeout=10)
        
        if response.status_code != 200:
            log(f"Failed to fetch data for {agent_id}", "WARN")
            raise Exception(f"API Error: {response.status_code}")

        data = response.json()
        log(f"Data retrieved: {data['name']}", "INFO")
        
        # Business logic validation
        if not data.get("email"):
            log(f"Agent {agent_id} is missing an email address!", "WARN")
            
        return data

    def validate_with_custom_warnings(self, agent_id: str, _logger: Optional[Callable] = None, **kwargs) -> dict:
        """
        Validates with warnings for specific IDs, using custom logger.
        """
        log = _logger if _logger else _create_local_logger()
        
        log(f"Starting validation with warnings for Agent ID: {agent_id}", "INFO")
        
        # Simulate warning for ID > 3
        if int(agent_id) > 3:
            log(f"Agent {agent_id} has potential issues!", "WARN")
        
        # Example using JSONPlaceholder API
        url = f"https://jsonplaceholder.typicode.com/users/{agent_id}"
        response = requests.get(url, timeout=10)
        
        if response.status_code != 200:
            log(f"Failed to fetch data for {agent_id}", "WARN")
            raise Exception(f"API Error: {response.status_code}")

        data = response.json()
        log(f"Data retrieved: {data['name']}", "INFO")
        
        # Business logic validation
        if not data.get("email"):
            log(f"Agent {agent_id} is missing an email address!", "WARN")
            
        return data

    def validate_with_custom_errors(self, agent_id: str, _logger: Optional[Callable] = None, **kwargs) -> dict:
        """
        Validates with errors for specific IDs, using custom logger.
        """
        log = _logger if _logger else _create_local_logger()
        
        log(f"Starting validation with errors for Agent ID: {agent_id}", "INFO")
        
        # Simulate error for ID > 3
        if int(agent_id) > 3:
            log(f"Critical error for agent {agent_id}!", "ERROR")
            raise Exception(f"Simulated error for agent {agent_id}")
        
        # Example using JSONPlaceholder API
        url = f"https://jsonplaceholder.typicode.com/users/{agent_id}"
        response = requests.get(url, timeout=10)
        
        if response.status_code != 200:
            log(f"Failed to fetch data for {agent_id}", "WARN")
            raise Exception(f"API Error: {response.status_code}")

        data = response.json()
        log(f"Data retrieved: {data['name']}", "INFO")
        
        # Business logic validation
        if not data.get("email"):
            log(f"Agent {agent_id} is missing an email address!", "WARN")
            
        return data
