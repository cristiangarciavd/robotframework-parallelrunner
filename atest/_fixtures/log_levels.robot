*** Settings ***
Documentation     Fixture for atest/test_log_levels.robot, run in a separate
...               Robot process with different --loglevel values. Not run on
...               its own: directories starting with "_" are skipped by robot.
Library           ParallelRunner
Library           examples.log_levels.shipment_check_client.ShipmentCheckClient


*** Variables ***
${LIB}            examples.log_levels.shipment_check_client.ShipmentCheckClient
@{SHIPMENTS}      S-1    S-2-late


*** Test Cases ***
Default Thread Log Level
    Run Parallel Scenarios    keyword=Check Shipment    library=${LIB}
    ...    for_loop_iterable=${SHIPMENTS}    delay=0

Thread Log Level DEBUG
    Run Parallel Scenarios    keyword=Check Shipment    library=${LIB}
    ...    for_loop_iterable=${SHIPMENTS}    delay=0    thread_log_level=DEBUG

Thread Log Level WARN
    Run Parallel Scenarios    keyword=Check Shipment    library=${LIB}
    ...    for_loop_iterable=${SHIPMENTS}    delay=0    thread_log_level=WARN

Failed Call With Every Level
    Run Parallel Scenarios    keyword=Check Shipment    library=${LIB}
    ...    for_loop_iterable=${{["S-3-lost"]}}    delay=0    fail_on_error=False
