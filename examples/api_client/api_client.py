import requests
from typing import Callable, Optional
from robot.api import logger
import time

def default_log(msg, level="INFO"):
    if level == "INFO":
        logger.info(msg)
    elif level == "WARN":
        logger.warn(msg)
    elif level == "ERROR":
        logger.error(msg)
    else:
        logger.info(msg)

class ApiClient:
    """Library for API interactions."""

    def verify_agent_data(self, agent_id: str, _logger: Optional[Callable] = None, **kwargs) -> dict:
        """
        Fetches data from a public API and validates it.
        _logger is injected by the ParallelLibrary to capture logs.
        """
        log = _logger if _logger else default_log
        
        log(f"Starting validation for Agent ID: {agent_id}")
        
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

    def validate_agents_data_with_steps(self, agent_id: str, _logger: Optional[Callable] = None, **kwargs) -> dict:
        """
        Validates agent data with additional steps: preparation, sleep, and finish logs.
        """
        log = _logger if _logger else default_log
        
        log(f"Preparing data for agent {agent_id}")
        time.sleep(1)  # Simulate processing delay
        result = self.verify_agent_data(agent_id, _logger=log, **kwargs)
        log(f"Finished processing agent {agent_id}")
        return result

    def validate_agents_with_warnings(self, agent_id: str, _logger: Optional[Callable] = None, **kwargs) -> dict:
        """
        Validates agent data and logs warnings for certain IDs.
        """
        log = _logger if _logger else default_log
        
        log(f"Starting validation with warnings for Agent ID: {agent_id}")
        
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

    def validate_agents_with_errors(self, agent_id: str, _logger: Optional[Callable] = None, **kwargs) -> dict:
        """
        Validates agent data and raises errors for certain IDs.
        """
        log = _logger if _logger else default_log
        
        log(f"Starting validation with errors for Agent ID: {agent_id}")
        
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