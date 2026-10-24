*** Settings ***
Documentation     `call_timeout`: a call that runs too long fails on its own,
...               the other calls keep running and finish, and the failure is a
...               normal ParallelTaskError (it can be handled, unlike a Robot
...               [Timeout]). Calls that declare `_cancelled` are told to stop.
...               Offline (no network).
Library           ParallelRunner
Library           examples.log_levels.shipment_check_client.ShipmentCheckClient
Test Setup        Reset Cancelled Shipments


*** Variables ***
${LIB}            examples.log_levels.shipment_check_client.ShipmentCheckClient
@{MIXED}          S-1    S-2-stuck    S-3-late    S-4


*** Test Cases ***
A Hung Call Fails Only Itself
    ${start}=    Evaluate    time.monotonic()    modules=time
    Run Keyword And Expect Error
    ...    ParallelTaskError: 1 of 4 parallel task(s) failed: item='S-2-stuck': Timed out after 500 milliseconds
    ...    Run Parallel Scenarios    keyword=Check Shipment    library=${LIB}
    ...    for_loop_iterable=${MIXED}    delay=0    call_timeout=500ms
    ${elapsed}=    Evaluate    time.monotonic() - ${start}    modules=time
    Should Be True    ${elapsed} < 5    Took ${elapsed} s: waited for the hung call.

The Other Calls Still Return Their Results
    ${results}=    Run Parallel Scenarios    keyword=Check Shipment    library=${LIB}
    ...    for_loop_iterable=${MIXED}    delay=0    call_timeout=0.5    fail_on_error=False
    Should Be Equal    ${results}[0][status]    PASS
    Should Be Equal    ${results}[1][status]    FAIL
    Should Be Equal    ${results}[1][error]    Timed out after 500 milliseconds
    Should Be Equal    ${results}[2][result][state]    late
    Should Be Equal    ${results}[3][result][state]    delivered

The Timed Out Call Keeps Its Partial Logs
    ${results}=    Run Parallel Scenarios    keyword=Check Shipment    library=${LIB}
    ...    for_loop_iterable=${{["S-5-stuck"]}}    call_timeout=0.3    fail_on_error=False
    ${messages}=    Evaluate    [message for level, message in $results[0]["logs"]]
    ${expected}=    Create List
    ...    Checking shipment S-5-stuck
    ...    GET /shipments/S-5-stuck
    ...    Call for item S-5-stuck timed out after 300 milliseconds (call_timeout); it keeps running in the background
    Should Be Equal    ${messages}    ${expected}

A Timed Out Call Can Be Handled Like Any Failure
    ${status}    ${message}=    Run Keyword And Ignore Error
    ...    Run Parallel Scenarios    keyword=Check Shipment    library=${LIB}
    ...    for_loop_iterable=${{["S-6-stuck"]}}    call_timeout=0.3
    Should Be Equal    ${status}    FAIL
    Should End With    ${message}    Timed out after 300 milliseconds

Call Timeout Cancels Calls That Declare _cancelled
    [Documentation]    Track Shipment polls a stuck shipment forever, but it
    ...    declares `_cancelled`: the call timeout sets it and the call stops.
    ${results}=    Run Parallel Scenarios    keyword=Track Shipment    library=${LIB}
    ...    for_loop_iterable=${{["T-1", "T-2-stuck", "T-3-stuck"]}}    poll_interval=0.05
    ...    call_timeout=0.5    fail_on_error=False
    Should Be Equal    ${results}[0][result]    delivered
    Should Be Equal    ${results}[1][status]    FAIL
    ${cancelled}=    Get Cancelled Shipments    expected=2
    Should Be Equal    ${cancelled}    ${{["T-2-stuck", "T-3-stuck"]}}

Calls That Finish In Time Are Not Cancelled
    ${values}=    Run Parallel Scenarios    keyword=Track Shipment    library=${LIB}
    ...    for_loop_iterable=${{["T-4", "T-5"]}}    poll_interval=0.01    call_timeout=10s
    ...    return_values_only=True
    Should Be Equal    ${values}    ${{("delivered", "delivered")}}
    ${cancelled}=    Get Cancelled Shipments
    Should Be Empty    ${cancelled}

Robot Time Format Is Accepted
    FOR    ${timeout}    IN    2s    2 seconds    1 minute    2.5    NONE
        ${values}=    Run Parallel Scenarios    keyword=Check Shipment    library=${LIB}
        ...    for_loop_iterable=${{["S-7"]}}    delay=0    call_timeout=${timeout}    return_values_only=True
        Should Be Equal    ${values}[0][state]    delivered
    END

Invalid Call Timeout Fails Before Running Anything
    Run Keyword And Expect Error    ValueError: Invalid call_timeout 'soon'*
    ...    Run Parallel Scenarios    keyword=Check Shipment    library=${LIB}
    ...    for_loop_iterable=${{["S-8"]}}    call_timeout=soon
    Run Keyword And Expect Error    ValueError: call_timeout must be positive, got '0'.
    ...    Run Parallel Scenarios    keyword=Check Shipment    library=${LIB}
    ...    for_loop_iterable=${{["S-8"]}}    call_timeout=0
