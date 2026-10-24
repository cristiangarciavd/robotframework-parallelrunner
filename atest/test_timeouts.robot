*** Settings ***
Documentation     What a Robot [Timeout] does to `Run Parallel Scenarios` with
...               calls that hang. Offline (no network).
...
...               A timeout can't be caught inside the test it fails, so
...               atest/_fixtures/timeouts.robot is run in a separate Robot
...               process (with ROBOT_THREAD_WORKERS=2) and its output.xml is
...               read back. Its "stuck" calls hang for 60 seconds.
...
...               Regression suite: before 0.3.1 the timeout only failed the
...               test once the whole batch had finished (60 seconds here), the
...               batch's logs were lost, and hanging worker threads kept the
...               Robot process from exiting.
Library           Collections
Library           atest.resources.FixtureRunner
Suite Setup       Run Timeout Fixture


*** Variables ***
${INTERRUPTED}    INFO Run Parallel Scenarios was interrupted (*): 1 call(s) finished,
...               2 still running (left running in the background), 1 not started.
${MAX_SECONDS}    3


*** Test Cases ***
Test Timeout Fails The Test When It Expires
    ${test}=    Get Fixture Test    ${RUN}[output]    Test Timeout Interrupts The Batch
    Should Be Equal    ${test}[status]    FAIL
    Should Be Equal    ${test}[message]    Test timeout 1 second exceeded.
    Should Be True    ${test}[elapsed] < ${MAX_SECONDS}    Took ${test}[elapsed] s: waited for the stuck calls.

Keyword Timeout Fails The Keyword When It Expires
    ${test}=    Get Fixture Test    ${RUN}[output]    Keyword Timeout Interrupts The Batch
    Should Be Equal    ${test}[status]    FAIL
    Should Be Equal    ${test}[message]    Keyword timeout 1 second exceeded.
    Should Be True    ${test}[elapsed] < ${MAX_SECONDS}    Took ${test}[elapsed] s: waited for the stuck calls.

Logs Collected Before The Timeout Are Replayed
    [Documentation]    Finished calls as usual, running calls with their partial
    ...    logs and an ERROR; calls that never started are only counted.
    FOR    ${name}    IN    Test Timeout Interrupts The Batch    Keyword Timeout Interrupts The Batch
        ${messages}=    Get Thread Messages    ${RUN}[output]    ${name}
        Should Match    ${messages}[0]    ${INTERRUPTED}
        # The reason depends on the platform: Robot raises the timeout without a
        # message on Windows ("Robot timeout exceeded"), with one on POSIX.
        ${messages}=    Evaluate
        ...    [re.sub(r"\\((Test|Keyword) timeout .* exceeded\\.\\)", "(Robot timeout exceeded)", m) for m in $messages]
        ...    modules=re
        ${expected}=    Create List
        ...    INFO --- Logs for Item: S-1 ---
        ...    INFO Checking shipment S-1
        ...    HTML Shipment <b>S-1</b>: <i>delivered</i>
        ...    INFO Status: PASS
        ...    INFO --- Logs for Item: S-2-stuck ---
        ...    INFO Checking shipment S-2-stuck
        ...    ERROR Call for item S-2-stuck did not finish: still running when the keyword was interrupted (Robot timeout exceeded)
        ...    INFO Status: FAIL
        ...    INFO --- Logs for Item: S-3-stuck ---
        ...    INFO Checking shipment S-3-stuck
        ...    ERROR Call for item S-3-stuck did not finish: still running when the keyword was interrupted (Robot timeout exceeded)
        ...    INFO Status: FAIL
        Lists Should Be Equal    ${messages}[1:]    ${expected}
    END

The Next Test Runs Normally
    ${test}=    Get Fixture Test    ${RUN}[output]    Next Test Runs Normally
    Should Be Equal    ${test}[status]    PASS

Hanging Calls Do Not Keep Robot From Exiting
    [Documentation]    The stuck calls hang for 60 seconds, but the worker
    ...    threads are daemon threads: the process exits right away.
    Should Be Equal As Integers    ${RUN}[rc]    2    Expected exactly the 2 timeout tests to fail.
    Should Be True    ${RUN}[elapsed] < 30    The fixture run took ${RUN}[elapsed] s.


*** Keywords ***
Run Timeout Fixture
    ${run}=    Run Fixture Suite    timeouts    ROBOT_THREAD_WORKERS=2
    Set Suite Variable    ${RUN}    ${run}
