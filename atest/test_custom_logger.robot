*** Settings ***
Library    ParallelRunner
Library    examples.custom_logger.custom_logger_api_client.CustomLoggerApiClient

*** Variables ***
${custom_logger_lib}    examples.custom_logger.custom_logger_api_client.CustomLoggerApiClient

*** Test Cases ***
Custom Logger - Parallel With Standard Mapper
    [Documentation]    Tests ParallelRunner with custom logger adapter.
    ...                Shows how to adapt custom logging formats to work with ParallelRunner.
    ${agents}=    Create List    1    2    3    4    5
    Run Parallel Scenarios    keyword=Validate With Custom Logger    for_loop_iterable=${agents}    library=${custom_logger_lib}    logger_mapper=examples.custom_logger.custom_logging_mapper.custom_logger_adapter

Custom Logger - Parallel With Warnings And Mapper
    [Documentation]    Tests custom logger with warnings and mapper.
    ${agents}=    Create List    1    2    3    4    5
    Run Parallel Scenarios    keyword=Validate With Custom Warnings    for_loop_iterable=${agents}    library=${custom_logger_lib}    logger_mapper=examples.custom_logger.custom_logging_mapper.custom_logger_adapter

Custom Logger - Parallel With Errors And Mapper
    [Documentation]    Tests custom logger with errors and mapper.
    ${agents}=    Create List    1    2    3    4    5
    Run Parallel Scenarios    keyword=Validate With Custom Errors    for_loop_iterable=${agents}    library=${custom_logger_lib}    logger_mapper=examples.custom_logger.custom_logging_mapper.custom_logger_adapter

Custom Logger - With Remove Passing Logs
    [Documentation]    Tests custom logger with remove_passing_logs to reduce noise.
    ${agents}=    Create List    1    2    3    4    5
    Run Parallel Scenarios    keyword=Validate With Custom Warnings    for_loop_iterable=${agents}    library=${custom_logger_lib}    logger_mapper=examples.custom_logger.custom_logging_mapper.custom_logger_adapter    remove_passing_logs=True

Custom Logger - With Log Level Filter
    [Documentation]    Tests custom logger with thread_log_level to filter logs.
    ${agents}=    Create List    1    2    3    4    5
    Run Parallel Scenarios    keyword=Validate With Custom Warnings    for_loop_iterable=${agents}    library=${custom_logger_lib}    logger_mapper=examples.custom_logger.custom_logging_mapper.custom_logger_adapter    thread_log_level=WARN