*** Settings ***
Library    parallelrunner.parallel_library.ParallelLibrary
Library    examples.api_client.api_client.ApiClient

*** Variables ***
${test_library}  examples.api_client.api_client.ApiClient

*** Test Cases ***
Parallel With Warnings - Default Logs
    ${agents}=    Create List    1    2    3    4    5
    Run Parallel Scenarios    keyword=Validate Agents With Warnings    for_loop_iterable=${agents}    library=${test_library}

Parallel With Warnings - Remove Passing Logs
    ${agents}=    Create List    1    2    3    4    5
    Run Parallel Scenarios    keyword=Validate Agents With Warnings    for_loop_iterable=${agents}    library=${test_library}    remove_passing_logs=True

Parallel With Warnings - Log Level WARN
    ${agents}=    Create List    1    2    3    4    5
    Run Parallel Scenarios    keyword=Validate Agents With Warnings    for_loop_iterable=${agents}    library=${test_library}    thread_log_level=WARN

Parallel With Warnings - Log Level ERROR
    ${agents}=    Create List    1    2    3    4    5
    Run Parallel Scenarios    keyword=Validate Agents With Warnings    for_loop_iterable=${agents}    library=${test_library}    thread_log_level=ERROR

Parallel With Errors - Default Logs
    ${agents}=    Create List    1    2    3    4    5
    Run Parallel Scenarios    keyword=Validate Agents With Errors    for_loop_iterable=${agents}    library=${test_library}

Parallel With Errors - Remove Passing Logs
    ${agents}=    Create List    1    2    3    4    5
    Run Parallel Scenarios    keyword=Validate Agents With Errors    for_loop_iterable=${agents}    library=${test_library}    remove_passing_logs=True

Parallel With Errors - Log Level WARN
    ${agents}=    Create List    1    2    3    4    5
    Run Parallel Scenarios    keyword=Validate Agents With Errors    for_loop_iterable=${agents}    library=${test_library}    thread_log_level=WARN

Parallel With Errors - Log Level ERROR
    ${agents}=    Create List    1    2    3    4    5
    Run Parallel Scenarios    keyword=Validate Agents With Errors    for_loop_iterable=${agents}    library=${test_library}    thread_log_level=ERROR

Sequential With Warnings
    ${agents}=    Create List    1    2    3    4    5
    FOR    ${agent}    IN    @{agents}
        Validate Agents With Warnings    ${agent}
    END

Sequential With Errors
    ${agents}=    Create List    1    2    3    4    5
    FOR    ${agent}    IN    @{agents}
        Run Keyword And Ignore Error    Validate Agents With Errors    ${agent}
    END