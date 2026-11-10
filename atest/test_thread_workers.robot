*** Settings ***
Documentation     `thread_workers` limits how many calls run at once for a single
...               `Run Parallel Scenarios` call, without changing
...               ROBOT_THREAD_WORKERS (default 4 here). Offline (no network).
Library           ParallelRunner
Library           atest.resources.ConcurrencyProbe
Test Setup        Reset Concurrency


*** Variables ***
${PROBE}          atest.resources.ConcurrencyProbe


*** Test Cases ***
Thread Workers Limits The Calls Running At Once
    ${values}=    Run Parallel Scenarios    keyword=Busy Call    library=${PROBE}
    ...    repeat=8    thread_workers=2    return_values_only=True
    ${max}=    Max Concurrency
    Should Be Equal    ${max}    ${2}
    Should Be Equal    ${values}    ${{tuple(str(i) for i in range(8))}}

Thread Workers One Runs The Calls One At A Time
    Run Parallel Scenarios    keyword=Busy Call    library=${PROBE}    repeat=4    thread_workers=1
    ${max}=    Max Concurrency
    Should Be Equal    ${max}    ${1}

Without Thread Workers The Global Value Is Used
    Run Parallel Scenarios    keyword=Busy Call    library=${PROBE}    repeat=8
    ${max}=    Max Concurrency
    Should Be Equal    ${max}    ${4}

Thread Workers Does Not Change The Global Value For Later Calls
    Run Parallel Scenarios    keyword=Busy Call    library=${PROBE}    repeat=4    thread_workers=1
    Reset Concurrency
    Run Parallel Scenarios    keyword=Busy Call    library=${PROBE}    repeat=8
    ${max}=    Max Concurrency
    Should Be Equal    ${max}    ${4}

Other Named Arguments Are Still Forwarded
    ${values}=    Run Parallel Scenarios    keyword=Busy Call    library=${PROBE}
    ...    for_loop_iterable=${{["a", "b"]}}    thread_workers=2    tag=-x    seconds=0.01
    ...    return_values_only=True
    Should Be Equal    ${values}    ${{("a-x", "b-x")}}

Invalid Thread Workers Fails Before Anything Runs
    [Template]    Invalid Thread Workers Should Fail
    0
    -1
    abc
    2.5


*** Keywords ***
Invalid Thread Workers Should Fail
    [Arguments]    ${value}
    Run Keyword And Expect Error
    ...    ValueError: Invalid thread_workers '${value}': expected a whole number of at least 1.
    ...    Run Parallel Scenarios    keyword=Busy Call    library=${PROBE}    repeat=2    thread_workers=${value}
    ${max}=    Max Concurrency
    Should Be Equal    ${max}    ${0}
