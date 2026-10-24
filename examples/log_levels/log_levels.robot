*** Settings ***
Documentation     Log levels and timeouts with ParallelRunner. Offline.
...
...               Run it with every level visible:
...               robot --pythonpath . --loglevel TRACE examples/log_levels/log_levels.robot
...
...               and compare log.html with a run at the default --loglevel
...               (INFO), where the TRACE and DEBUG messages are filtered out.
...               The test tagged `fails-on-purpose` shows what a [Timeout]
...               does to a batch with a hanging call; leave it out with
...               --exclude fails-on-purpose.
Library           ParallelRunner
Library           examples.log_levels.shipment_check_client.ShipmentCheckClient


*** Variables ***
${LIB}            examples.log_levels.shipment_check_client.ShipmentCheckClient
@{SHIPMENTS}      S-1    S-2-late    S-3    S-4-late


*** Test Cases ***
Every Level Ends Up In The Log
    [Documentation]    INFO, HTML and WARN always; DEBUG and TRACE only with
    ...    --loglevel DEBUG / TRACE, like any other keyword's messages.
    Run Parallel Scenarios    keyword=Check Shipment    library=${LIB}
    ...    for_loop_iterable=${SHIPMENTS}

Only Warnings And Errors From The Threads
    [Documentation]    thread_log_level filters the threads' messages on top
    ...    of --loglevel: here only the "is late" warnings are replayed.
    Run Parallel Scenarios    keyword=Check Shipment    library=${LIB}
    ...    for_loop_iterable=${SHIPMENTS}    thread_log_level=WARN

Debug Without Trace
    [Documentation]    Even with --loglevel TRACE, the request lines (TRACE)
    ...    are left out and the responses (DEBUG) kept.
    Run Parallel Scenarios    keyword=Check Shipment    library=${LIB}
    ...    for_loop_iterable=${SHIPMENTS}    thread_log_level=DEBUG

Only The Logs Of Failed Calls
    [Documentation]    With remove_passing_logs=True the lost shipment is the
    ...    only one in the log, with every level it logged before failing.
    ${results}=    Run Parallel Scenarios    keyword=Check Shipment    library=${LIB}
    ...    for_loop_iterable=${{ $SHIPMENTS + ["S-5-lost"] }}
    ...    remove_passing_logs=True    fail_on_error=False
    Should Be Equal    ${results}[4][status]    FAIL

A Timeout Stops Waiting For A Hanging Call
    [Documentation]    Fails on purpose after 2 seconds, not after the 60
    ...    seconds S-3-stuck hangs for. The log shows S-1 and S-2-late as
    ...    usual and S-3-stuck's partial logs with an ERROR. S-3-stuck keeps
    ...    running in the background; the run still exits right away.
    [Tags]    fails-on-purpose
    [Timeout]    2 seconds
    Run Parallel Scenarios    keyword=Check Shipment    library=${LIB}
    ...    for_loop_iterable=${{ ["S-1", "S-2-late", "S-3-stuck"] }}
