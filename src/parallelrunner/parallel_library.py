import os
import concurrent.futures
from typing import Iterable, Any, List, Dict, Optional
from robot.api import logger
from robot.libraries.BuiltIn import BuiltIn


class ParallelLibrary:
    """
    Library to run Robot Framework keywords/Python functions in parallel
    using ThreadPoolExecutor while preserving log integrity.
    """
    ROBOT_LIBRARY_SCOPE = 'GLOBAL'

    def __init__(self):
        # Workers count from Env Var or default to 4
        self.max_workers = int(os.getenv("ROBOT_THREAD_WORKERS", "4"))

    def run_parallel_scenarios(
        self, 
        keyword: str, 
        library: str,
        for_loop_iterable: Optional[Iterable[Any]] = None, 
        repeat: Optional[int] = None, 
        remove_passing_logs: bool = False,
        thread_log_level: str = "INFO",
        logger_mapper: Optional[Any] = None,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Runs a keyword in parallel.
        - If for_loop_iterable is provided, it acts like a parallel FOR loop.
        - If repeat is provided, it runs the same keyword N times.
        - If remove_passing_logs is True, only logs warnings/errors for failed tasks, skipping successful ones.
        - library: Library name where the keyword is defined. Required.
        - thread_log_level: Minimum log level to replay ("INFO", "WARN", "ERROR"). Default "INFO".
        - logger_mapper: Optional custom logger function to map standard levels to custom logging format. 
          Signature: mapper(msg: str, level: str). 
          Can be a callable or a string path to a module function (e.g., "examples.custom_logger.custom_logging_mapper.custom_logger_adapter").
          If not provided, will attempt to load from ROBOT_LOGGER_MAPPER environment variable.
        
        Environment variables:
        - ROBOT_THREAD_WORKERS: Number of parallel worker threads (default: 4)
        - ROBOT_LOGGER_MAPPER: Global logger mapper name or module path (default: None)
          Example: ROBOT_LOGGER_MAPPER=custom_logger_adapter
        """
        results = []
        tasks = []
        
        # Determine items to process
        items = for_loop_iterable if for_loop_iterable is not None else range(repeat or 1)

        # Resolve mapper: it might be a callable or a string path
        effective_mapper = self._resolve_mapper(logger_mapper)
        
        # If not resolved from parameter, try environment
        if effective_mapper is None:
            effective_mapper = self._load_mapper_from_environment()

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # We map the execution. 
            # Note: We must call the underlying Python method, not BuiltIn().run_keyword
            # because run_keyword is not thread-safe.
            lib_instance = self._get_library_instance_owning_keyword(keyword, library)
            method = getattr(lib_instance, keyword.replace(" ", "_").lower())

            for item in items:
                tasks.append(executor.submit(self._execute_and_capture, method, item, effective_mapper, **kwargs))

            for future in concurrent.futures.as_completed(tasks):
                results.append(future.result())

        # Step: Re-play logs into Robot Framework sequentially
        self._replay_logs(results, remove_passing_logs, thread_log_level)
        return results

    def _resolve_mapper(self, mapper: Optional[Any]) -> Optional[Any]:
        """
        Resolve a mapper which might be a callable or a string path to a module function.
        
        Args:
            mapper: Callable or string path (e.g., "examples.custom_logger.custom_logging_mapper.custom_logger_adapter")
        
        Returns:
            Callable: The mapper function if successfully resolved, None otherwise.
        """
        if mapper is None:
            return None
        
        # If already callable, return it
        if callable(mapper):
            return mapper
        
        # If it's a string, try to import it
        if isinstance(mapper, str):
            try:
                parts = mapper.rsplit(".", 1)
                if len(parts) == 2:
                    module_name, func_name = parts
                    module = __import__(module_name, fromlist=[func_name])
                    resolved = getattr(module, func_name, None)
                    if callable(resolved):
                        return resolved
            except (ImportError, AttributeError):
                pass
        
        return None

    def _load_mapper_from_environment(self) -> Optional[Any]:
        """
        Load custom logger mapper from ROBOT_LOGGER_MAPPER environment variable.
        Supports both registered mapper names and module.function paths.
        
        Returns:
            Callable: The mapper function if found, None otherwise.
        """
        mapper_name = os.getenv("ROBOT_LOGGER_MAPPER")
        if not mapper_name:
            return None
        
        # Use _resolve_mapper to handle the string path
        return self._resolve_mapper(mapper_name)

    def _get_library_instance_owning_keyword(self, keyword_name: str, library: str) -> Any:
        method_name = keyword_name.replace(" ", "_").lower()
        lib_instance = BuiltIn().get_library_instance(library)
        if hasattr(lib_instance, method_name):
            return lib_instance
        raise ValueError(f"Keyword '{keyword_name}' not found in library '{library}'")

    def _execute_and_capture(self, method, item, logger_mapper: Optional[Any] = None, **kwargs) -> Dict[str, Any]:
        """Worker wrapper to capture logs and results."""
        log_buffer = []
        
        # Injection of a custom logger into the thread
        def thread_log(msg, level="INFO"):
            # Filter out IGNORE (sv=0) level logs
            if level != "IGNORE":
                log_buffer.append((level, msg))
        
        # Use mapper if provided, otherwise use thread_log
        effective_logger = logger_mapper if logger_mapper else thread_log

        try:
            # We pass the custom logger as an extra kwarg if the method supports it
            # or rely on the method returning its own logs.
            result = method(item, _logger=effective_logger, **kwargs)
            return {"status": "PASS", "item": item, "logs": log_buffer, "result": result}
        except Exception as e:
            thread_log(f"Thread failed for item {item}: {str(e)}", "ERROR")
            return {"status": "FAIL", "item": item, "logs": log_buffer, "error": str(e)}

    def _replay_logs(self, results: List[Dict[str, Any]], remove_passing_logs: bool = False, thread_log_level: str = "INFO"):
        """Sequential dump to the real RF Logger. Filters out IGNORE level logs."""
        level_order = {"INFO": 1, "WARN": 2, "ERROR": 3}
        min_level = level_order.get(thread_log_level, 1)
        for entry in results:
            if remove_passing_logs and entry['status'] == 'PASS':
                continue
            logger.info(f"--- Logs for Item: {entry['item']} ---")
            for level, msg in entry['logs']:
                # Skip IGNORE level and logs below minimum level
                if level == "IGNORE" or level_order.get(level, 1) < min_level:
                    continue
                if level == "INFO": logger.info(msg)
                elif level == "WARN": logger.warn(msg)
                elif level == "ERROR": logger.error(msg)
            logger.info(f"Status: {entry['status']}")