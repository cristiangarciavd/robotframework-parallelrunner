*** Settings ***
Documentation     What the threads' messages look like in the Robot log, at
...               every level, with Robot's --loglevel and with
...               thread_log_level. Offline (no network).
...
...               The log can't be inspected from inside the run that writes
...               it, so atest/_fixtures/log_levels.robot is run in a separate
...               Robot process (once per --loglevel) and its output.xml is
...               read back.
...
...               Regression suite: before 0.3.1 only INFO, WARN and ERROR were
...               replayed; TRACE, DEBUG and HTML messages were lost silently,
...               even with --loglevel TRACE.
Library           Collections
Library           ParallelRunner
Library           examples.log_levels.shipment_check_client.ShipmentCheckClient
Library           atest.resources.FixtureRunner
Suite Setup       Run Fixture With Every Log Level


*** Variables ***
${LIB}            examples.log_levels.shipment_check_client.ShipmentCheckClient
@{S1_ALL}         INFO --- Logs for Item: S-1 ---
...               INFO Checking shipment S-1
...               TRACE GET /shipments/S-1
...               DEBUG Response: id=S-1 state=delivered
...               HTML Shipment <b>S-1</b>: <i>delivered</i>
...               INFO Status: PASS
@{S2_ALL}         INFO --- Logs for Item: S-2-late ---
...               INFO Checking shipment S-2-late
...               TRACE GET /shipments/S-2-late
...               DEBUG Response: id=S-2-late state=late
...               HTML Shipment <b>S-2-late</b>: <i>late</i>
...               WARN Shipment S-2-late is late
...               INFO Status: PASS


*** Test Cases ***
Every Level Is Replayed With Loglevel TRACE
    ${messages}=    Get Thread Messages    ${TRACE_RUN}[output]    Default Thread Log Level
    Lists Should Be Equal    ${messages}    ${{ $S1_ALL + $S2_ALL }}

Loglevel DEBUG Hides Only TRACE
    ${messages}=    Get Thread Messages    ${DEBUG_RUN}[output]    Default Thread Log Level
    Lists Should Be Equal    ${messages}    ${{ [m for m in $S1_ALL + $S2_ALL if not m.startswith("TRACE")] }}

Default Loglevel Hides TRACE And DEBUG
    [Documentation]    Robot's default --loglevel is INFO: TRACE and DEBUG
    ...    thread messages are filtered like any other keyword's.
    ${messages}=    Get Thread Messages    ${INFO_RUN}[output]    Default Thread Log Level
    ${expected}=    Evaluate    [m for m in $S1_ALL + $S2_ALL if not m.startswith(("TRACE", "DEBUG"))]
    Lists Should Be Equal    ${messages}    ${expected}

HTML Messages Are Rendered As HTML
    ${messages}=    Get Thread Messages    ${INFO_RUN}[output]    Default Thread Log Level
    List Should Contain Value    ${messages}    HTML Shipment <b>S-1</b>: <i>delivered</i>

Thread Log Level DEBUG Hides TRACE Even With Loglevel TRACE
    ${messages}=    Get Thread Messages    ${TRACE_RUN}[output]    Thread Log Level DEBUG
    Lists Should Be Equal    ${messages}    ${{ [m for m in $S1_ALL + $S2_ALL if not m.startswith("TRACE")] }}

Thread Log Level WARN Keeps Only Warnings And Errors
    ${messages}=    Get Thread Messages    ${TRACE_RUN}[output]    Thread Log Level WARN
    ${expected}=    Create List
    ...    INFO --- Logs for Item: S-1 ---    INFO Status: PASS
    ...    INFO --- Logs for Item: S-2-late ---    WARN Shipment S-2-late is late    INFO Status: PASS
    Lists Should Be Equal    ${messages}    ${expected}

Failed Call Keeps Every Level Before The Error
    ${messages}=    Get Thread Messages    ${TRACE_RUN}[output]    Failed Call With Every Level
    ${expected}=    Create List
    ...    INFO --- Logs for Item: S-3-lost ---
    ...    INFO Checking shipment S-3-lost
    ...    TRACE GET /shipments/S-3-lost
    ...    DEBUG Response: id=S-3-lost state=lost
    ...    HTML Shipment <b>S-3-lost</b>: <i>lost</i>
    ...    ERROR Shipment S-3-lost was lost
    ...    ERROR Thread failed for item S-3-lost: Shipment S-3-lost lost
    ...    INFO Status: FAIL
    Lists Should Be Equal    ${messages}    ${expected}

Fixture Runs Pass
    [Documentation]    Every fixture test passes at every --loglevel.
    FOR    ${run}    IN    ${TRACE_RUN}    ${DEBUG_RUN}    ${INFO_RUN}
        Should Be Equal As Integers    ${run}[rc]    0
    END

Result Logs Keep Every Level As Given
    [Documentation]    The `logs` of each result are not filtered by any level.
    ${results}=    Run Parallel Scenarios    keyword=Check Shipment    library=${LIB}
    ...    for_loop_iterable=${{["S-7-late"]}}    delay=0    thread_log_level=ERROR
    ${levels}=    Evaluate    [level for level, _ in $results[0]["logs"]]
    Should Be Equal    ${levels}    ${{ ["INFO", "TRACE", "DEBUG", "HTML", "WARN"] }}

Unknown Thread Log Level Does Not Fail The Keyword
    ${values}=    Run Parallel Scenarios    keyword=Check Shipment    library=${LIB}
    ...    for_loop_iterable=${{["S-8"]}}    delay=0    thread_log_level=LOUD    return_values_only=True
    Should Be Equal    ${values}[0][state]    delivered


*** Keywords ***
Run Fixture With Every Log Level
    ${run}=    Run Fixture Suite    log_levels    --loglevel    TRACE
    Set Suite Variable    ${TRACE_RUN}    ${run}
    ${run}=    Run Fixture Suite    log_levels    --loglevel    DEBUG
    Set Suite Variable    ${DEBUG_RUN}    ${run}
    ${run}=    Run Fixture Suite    log_levels
    Set Suite Variable    ${INFO_RUN}    ${run}
