*** Settings ***
Documentation     Checks which logger ParallelRunner really uses: the mapper given
...               with `logger_mapper` or ROBOT_LOGGER_MAPPER, or the default
...               buffered logger. A used mapper receives the messages and the
...               result entries have no buffered `logs`; an ignored one leaves
...               the messages in `logs`. Offline (no network).
...
...               Regression suite for the bug where a bare mapper name was
...               silently ignored while the other suites still passed.
Library           Collections
Library           OperatingSystem
Library           ParallelRunner
Library           atest.resources.MapperProbe
Suite Setup       Remove Environment Variable    ROBOT_LOGGER_MAPPER
Test Setup        Clear Recorded Logs
Test Teardown     Remove Environment Variable    ROBOT_LOGGER_MAPPER


*** Variables ***
${PROBE}          atest.resources.MapperProbe
${MAPPER}         atest.resources.MapperProbe.record
@{ITEMS}          1    2    3
@{EXPECTED}       info from item 1    info from item 2    info from item 3
...               warning from item 1    warning from item 2    warning from item 3


*** Test Cases ***
Explicit Mapper Path Receives All Messages
    ${results}=    Run Parallel Scenarios    keyword=Emit Logs    library=${PROBE}
    ...    for_loop_iterable=${ITEMS}    logger_mapper=${MAPPER}
    Mapper Should Have Received All Messages
    Results Should Have No Buffered Logs    ${results}

Environment Variable Mapper Path Receives All Messages
    Set Environment Variable    ROBOT_LOGGER_MAPPER    ${MAPPER}
    ${results}=    Run Parallel Scenarios    keyword=Emit Logs    library=${PROBE}
    ...    for_loop_iterable=${ITEMS}
    Mapper Should Have Received All Messages
    Results Should Have No Buffered Logs    ${results}

Bare Mapper Name Is Ignored And Logs Stay Buffered
    [Documentation]    A bare name is not a `module.function` path: ParallelRunner
    ...    logs a warning and keeps its default buffered logger.
    ${results}=    Run Parallel Scenarios    keyword=Emit Logs    library=${PROBE}
    ...    for_loop_iterable=${ITEMS}    logger_mapper=record
    Mapper Should Have Received Nothing
    Results Should Have Buffered Logs    ${results}

Bare Environment Variable Name Is Ignored And Logs Stay Buffered
    Set Environment Variable    ROBOT_LOGGER_MAPPER    record
    ${results}=    Run Parallel Scenarios    keyword=Emit Logs    library=${PROBE}
    ...    for_loop_iterable=${ITEMS}
    Mapper Should Have Received Nothing
    Results Should Have Buffered Logs    ${results}

Unresolvable Explicit Mapper Falls Back To Environment Variable
    Set Environment Variable    ROBOT_LOGGER_MAPPER    ${MAPPER}
    ${results}=    Run Parallel Scenarios    keyword=Emit Logs    library=${PROBE}
    ...    for_loop_iterable=${ITEMS}    logger_mapper=no_such.module.mapper
    Mapper Should Have Received All Messages
    Results Should Have No Buffered Logs    ${results}


*** Keywords ***
Mapper Should Have Received All Messages
    ${received}=    Get Recorded Messages
    Lists Should Be Equal    ${received}    ${EXPECTED}

Mapper Should Have Received Nothing
    ${received}=    Get Recorded Messages
    Should Be Empty    ${received}

Results Should Have No Buffered Logs
    [Arguments]    ${results}
    FOR    ${entry}    IN    @{results}
        Should Be Equal    ${entry}[status]    PASS
        Should Be Empty    ${entry}[logs]
    END

Results Should Have Buffered Logs
    [Arguments]    ${results}
    FOR    ${entry}    IN    @{results}
        Should Be Equal    ${entry}[status]    PASS
        Length Should Be    ${entry}[logs]    2
    END
