*** Settings ***
Library    OperatingSystem
Library    ParallelRunner
Library    examples.custom_logger.custom_logger_api_client.CustomLoggerApiClient
# ROBOT_LOGGER_MAPPER must be a `module.function` path: a bare name such as
# `custom_logger_adapter` is ignored (with a warning) and the default buffered
# logger is used instead. That used to be silent, so this suite passed while
# never using the mapper; test_logger_mapper.robot now checks which logger is used.
Suite Setup       Set Environment Variable    ROBOT_LOGGER_MAPPER    examples.custom_logger.custom_logging_mapper.custom_logger_adapter
Suite Teardown    Remove Environment Variable    ROBOT_LOGGER_MAPPER

*** Variables ***
${custom_logger_lib}    examples.custom_logger.custom_logger_api_client.CustomLoggerApiClient

*** Test Cases ***
Custom Logger - Global Mapper - Parallel With Standard Mapper
    [Documentation]    Tests ParallelRunner using global ROBOT_LOGGER_MAPPER environment variable.
    ...                No logger_mapper parameter needed - uses environment setup automatically.
    ${agents}=    Create List    1    2    3    4    5
    Run Parallel Scenarios
    ...    keyword=Validate With Custom Logger
    ...    library=${custom_logger_lib}
    ...    for_loop_iterable=${agents}

Custom Logger - Global Mapper - Parallel With Warnings
    [Documentation]    Tests custom logger with warnings using global mapper.
    ${agents}=    Create List    1    2    3    4    5
    Run Parallel Scenarios
    ...    keyword=Validate With Custom Warnings
    ...    library=${custom_logger_lib}
    ...    for_loop_iterable=${agents}

Custom Logger - Global Mapper - Parallel With Errors
    [Documentation]    Tests custom logger with errors using global mapper.
    ${agents}=    Create List    1    2    3    4    5
    Run Parallel Scenarios
    ...    keyword=Validate With Custom Errors
    ...    library=${custom_logger_lib}
    ...    for_loop_iterable=${agents}

Custom Logger - Global Mapper - With Remove Passing Logs
    [Documentation]    Tests custom logger with remove_passing_logs to reduce noise.
    ${agents}=    Create List    1    2    3    4    5
    Run Parallel Scenarios
    ...    keyword=Validate With Custom Warnings
    ...    library=${custom_logger_lib}
    ...    for_loop_iterable=${agents}
    ...    remove_passing_logs=True

Custom Logger - Global Mapper - With Log Level Filter
    [Documentation]    Tests custom logger with thread_log_level to filter logs.
    ${agents}=    Create List    1    2    3    4    5
    Run Parallel Scenarios
    ...    keyword=Validate With Custom Warnings
    ...    library=${custom_logger_lib}
    ...    for_loop_iterable=${agents}
    ...    thread_log_level=WARN

Custom Logger - Override Global Mapper
    [Documentation]    Tests ability to override global mapper with explicit parameter.
    ...                Even with Suite Setup, explicit parameter takes precedence.
    ${agents}=    Create List    1    2    3    4
    Run Parallel Scenarios
    ...    keyword=Validate With Custom Logger
    ...    library=${custom_logger_lib}
    ...    for_loop_iterable=${agents}
    ...    logger_mapper=examples.custom_logger.custom_logging_mapper.custom_logger_adapter
