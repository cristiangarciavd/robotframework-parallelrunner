*** Settings ***
Documentation     Fixture for atest/test_timeouts.robot, run in a separate
...               Robot process with ROBOT_THREAD_WORKERS=2. Its timeout tests
...               fail on purpose. Not run on its own: directories starting
...               with "_" are skipped by robot.
...
...               S-1 finishes right away; the "stuck" shipments hang for
...               60 seconds. With 2 workers, S-1 and S-2-stuck start, then
...               S-3-stuck takes the freed worker and S-4 never starts.
Library           ParallelRunner
Library           examples.log_levels.shipment_check_client.ShipmentCheckClient


*** Variables ***
${LIB}            examples.log_levels.shipment_check_client.ShipmentCheckClient
@{SHIPMENTS}      S-1    S-2-stuck    S-3-stuck    S-4


*** Test Cases ***
Test Timeout Interrupts The Batch
    [Timeout]    1 second
    Run Parallel Scenarios    keyword=Check Shipment    library=${LIB}
    ...    for_loop_iterable=${SHIPMENTS}    delay=0

Keyword Timeout Interrupts The Batch
    Check Shipments With Keyword Timeout

Next Test Runs Normally
    ${values}=    Run Parallel Scenarios    keyword=Check Shipment    library=${LIB}
    ...    for_loop_iterable=${{["S-5", "S-6-late"]}}    delay=0    return_values_only=True
    Should Be Equal    ${values}[1][state]    late


*** Keywords ***
Check Shipments With Keyword Timeout
    [Timeout]    1 second
    Run Parallel Scenarios    keyword=Check Shipment    library=${LIB}
    ...    for_loop_iterable=${SHIPMENTS}    delay=0
