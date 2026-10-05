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
        _logger is injected by ParallelRunner to capture logs.
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

    def create_test_record(self, index: int, _logger: Optional[Callable] = None, **kwargs) -> dict:
        """
        Creates one new record via POST, meant to be driven by `repeat` rather
        than `for_loop_iterable`: there is no pre-existing list of items here,
        the goal is simply "create N independent records concurrently"
        (e.g. seeding test data in a Suite Setup). `index` is only used to
        keep each record's payload unique across the N parallel calls; any
        value shared by every call (e.g. `title_prefix`) should be passed as
        a kwarg instead, since it's identical for every task.
        """
        log = _logger if _logger else default_log

        title_prefix = kwargs.get("title_prefix", "record")
        payload = {"title": f"{title_prefix}-{index}", "body": "created in parallel", "userId": index + 1}

        log(f"Creating record #{index} with title '{payload['title']}'")

        url = "https://jsonplaceholder.typicode.com/posts"
        response = requests.post(url, json=payload, timeout=10)

        if response.status_code not in (200, 201):
            log(f"Failed to create record #{index}", "ERROR")
            raise Exception(f"API Error: {response.status_code}")

        data = response.json()
        log(f"Record #{index} created with id {data.get('id')}")
        return data

    def check_endpoint_health(self, call_index: int, _logger: Optional[Callable] = None, **kwargs) -> dict:
        """
        Calls a single, fixed endpoint (identified by the `agent_id` kwarg,
        the same for every call) repeatedly. Meant to be driven by `repeat`:
        `call_index` is not used to select what to call, only to label each
        of the N concurrent calls in the logs/results. Useful for a light
        concurrent load check, or to catch failures that only show up when
        the same endpoint is hit by several threads at once.
        """
        log = _logger if _logger else default_log

        agent_id = kwargs.get("agent_id", "1")
        log(f"Health check call #{call_index} against agent {agent_id}")

        url = f"https://jsonplaceholder.typicode.com/users/{agent_id}"
        response = requests.get(url, timeout=10)

        if response.status_code != 200:
            log(f"Call #{call_index} failed with status {response.status_code}", "ERROR")
            raise Exception(f"API Error: {response.status_code}")

        log(f"Call #{call_index} succeeded")
        return {"call_index": call_index, "status_code": response.status_code}

    def smoke_test_endpoint(self, endpoint_path: str, _logger: Optional[Callable] = None, **kwargs) -> int:
        """
        Hits one endpoint path from a list of *different* routes and returns
        its HTTP status code. Meant to be driven by `for_loop_iterable` with a
        list of route paths - the shape of a real post-deployment smoke test
        that fans out across several microservices/routes right after a
        release, to catch a broken deploy before real traffic does.

        Contrast with `check_endpoint_health`, which hits the SAME fixed
        endpoint `repeat` times (a concurrent load check); this hits N
        DIFFERENT endpoints once each (a release verification check). Pairs
        well with `return_values_only=True`: the caller usually only cares
        about "did every route come back 200", not the full response body.
        """
        log = _logger if _logger else default_log

        log(f"Smoke testing endpoint: {endpoint_path}")
        url = f"https://jsonplaceholder.typicode.com/{endpoint_path}"
        response = requests.get(url, timeout=10)

        if response.status_code != 200:
            log(f"Endpoint '{endpoint_path}' returned {response.status_code}", "ERROR")
            raise Exception(f"API Error: {response.status_code}")

        log(f"Endpoint '{endpoint_path}' OK ({response.status_code})")
        return response.status_code

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