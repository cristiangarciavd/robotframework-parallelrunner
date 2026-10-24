*** Settings ***
Documentation     What happens when some parallel calls fail. Offline (no network).
...
...               By default `Run Parallel Scenarios` fails as soon as one call
...               failed - after every call has finished and all logs have been
...               replayed - with a `ParallelTaskError` listing each failed item.
...               `fail_on_error=False` returns the per-call results instead and
...               leaves the checks to the test.
...
...               Regression suite: before 0.3.0 a failed call was only logged
...               at ERROR level and the keyword (and test) passed.
Library           ParallelRunner
Library           examples.order_check.order_check_client.OrderCheckClient
Test Setup        Reset Checked Orders


*** Variables ***
${LIB}            examples.order_check.order_check_client.OrderCheckClient
@{GOOD}           A-1    A-2    A-3-late    A-4
@{MIXED}          A-1    A-2-missing    A-3    A-4-missing    A-5
${MIXED_ERROR}    ParallelTaskError: 2 of 5 parallel task(s) failed:
...               item='A-2-missing': Order A-2-missing not found;
...               item='A-4-missing': Order A-4-missing not found


*** Test Cases ***
All Calls Pass So The Keyword Passes
    ${results}=    Run Parallel Scenarios    keyword=Check Order    library=${LIB}
    ...    for_loop_iterable=${GOOD}
    Length Should Be    ${results}    4
    FOR    ${entry}    IN    @{results}
        Should Be Equal    ${entry}[status]    PASS
    END
    Should Be Equal    ${results}[2][result][state]    late

A Failed Call Fails The Keyword
    [Documentation]    The error lists every failed item, in call order.
    Run Keyword And Expect Error    ${MIXED_ERROR}
    ...    Run Parallel Scenarios    keyword=Check Order    library=${LIB}
    ...    for_loop_iterable=${MIXED}

Every Call Runs Before The Keyword Fails
    [Documentation]    A failed call does not cancel the others.
    Run Keyword And Expect Error    ParallelTaskError: 2 of 5 parallel task(s) failed:*
    ...    Run Parallel Scenarios    keyword=Check Order    library=${LIB}
    ...    for_loop_iterable=${MIXED}
    ${checked}=    Get Checked Orders
    Should Be Equal    ${checked}    ${{ sorted($MIXED) }}

A Single Failure Out Of Many Is Not Hidden
    ${orders}=    Evaluate    [f"B-{i}" for i in range(19)] + ["B-19-missing"]
    Run Keyword And Expect Error    ParallelTaskError: 1 of 20 parallel task(s) failed: item='B-19-missing': *
    ...    Run Parallel Scenarios    keyword=Check Order    library=${LIB}
    ...    for_loop_iterable=${orders}    delay=0

Failure Is Reported With Remove Passing Logs And WARN Level
    Run Keyword And Expect Error    ParallelTaskError: 2 of 5 parallel task(s) failed:*
    ...    Run Parallel Scenarios    keyword=Check Order    library=${LIB}
    ...    for_loop_iterable=${MIXED}    remove_passing_logs=True    thread_log_level=WARN

The Failure Can Be Handled Like Any Other Keyword Failure
    ${status}    ${message}=    Run Keyword And Ignore Error
    ...    Run Parallel Scenarios    keyword=Check Order    library=${LIB}
    ...    for_loop_iterable=${MIXED}
    Should Be Equal    ${status}    FAIL
    Should Be Equal    ${message}    ${MIXED_ERROR}

Fail On Error False Returns A Status Per Item
    [Documentation]    Opt out: get every result back and check them yourself.
    ${results}=    Run Parallel Scenarios    keyword=Check Order    library=${LIB}
    ...    for_loop_iterable=${MIXED}    fail_on_error=False
    Length Should Be    ${results}    5
    Should Be Equal    ${results}[0][status]    PASS
    Should Be Equal    ${results}[1][status]    FAIL
    Should Be Equal    ${results}[1][error]    Order A-2-missing not found
    Should Be Equal    ${results}[2][status]    PASS
    Should Be Equal    ${results}[3][status]    FAIL
    Should Be Equal    ${results}[4][result][order_id]    A-5

Fail On Error False Leaves The Assertion To The Test
    ${results}=    Run Parallel Scenarios    keyword=Check Order    library=${LIB}
    ...    for_loop_iterable=${MIXED}    fail_on_error=False
    Run Keyword And Expect Error    FAIL != PASS
    ...    Should Be Equal    ${results}[1][status]    PASS

Return Values Only Fails Even With Fail On Error False
    [Documentation]    A failed call has no return value to put in the tuple.
    Run Keyword And Expect Error    ${MIXED_ERROR}
    ...    Run Parallel Scenarios    keyword=Check Order    library=${LIB}
    ...    for_loop_iterable=${MIXED}    return_values_only=True    fail_on_error=False

Get Result Values Fails On A List With Failed Calls
    ${results}=    Run Parallel Scenarios    keyword=Check Order    library=${LIB}
    ...    for_loop_iterable=${MIXED}    fail_on_error=False
    Run Keyword And Expect Error    ${MIXED_ERROR}
    ...    Get Result Values    ${results}
