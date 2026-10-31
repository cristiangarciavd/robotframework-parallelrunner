*** Settings ***
Documentation     `call_retries`, `retry_delay` and `retry_backoff`: a failed (or
...               timed-out) call is tried again before it counts as failed.
...               Offline (no network).
Library           ParallelRunner
Library           atest.resources.FlakyProbe


*** Variables ***
${PROBE}          atest.resources.FlakyProbe


*** Test Cases ***
A Flaky Call Passes After Retries
    ${results}=    Run Parallel Scenarios    keyword=Fail Until Attempt    library=${PROBE}
    ...    for_loop_iterable=${{["A:3", "B:1"]}}    call_retries=2    retry_delay=0
    Should Be Equal    ${results}[0][result]    ${3}
    Should Be Equal    ${results}[0][attempts]    ${3}
    Should Be Equal    ${results}[1][attempts]    ${1}
    Should Be Equal    ${results}[0][logs][1]    ${{("WARN", "Attempt 1 of 3 failed: A not ready; retrying now")}}

A Call That Keeps Failing Fails The Keyword With Its Last Error
    Run Keyword And Expect Error    ParallelTaskError: 1 of 1 parallel task(s) failed: item='C:9': C not ready
    ...    Run Parallel Scenarios    keyword=Fail Until Attempt    library=${PROBE}
    ...    for_loop_iterable=${{["C:9"]}}    call_retries=1    retry_delay=10ms

Waits Between Attempts Grow With The Backoff
    ${start}=    Evaluate    time.monotonic()    modules=time
    ${results}=    Run Parallel Scenarios    keyword=Fail Until Attempt    library=${PROBE}
    ...    for_loop_iterable=${{["D:3"]}}    call_retries=2    retry_delay=100ms    retry_backoff=2
    ${elapsed}=    Evaluate    time.monotonic() - ${start}    modules=time
    Should Be True    ${elapsed} >= 0.3
    Should Be Equal    ${results}[0][logs][3]    ${{("WARN", "Attempt 2 of 3 failed: D not ready; retrying in 200 milliseconds")}}

A Timed-Out Call Is Retried
    ${values}=    Run Parallel Scenarios    keyword=Hang On First Call    library=${PROBE}
    ...    for_loop_iterable=${{["E"]}}    call_timeout=300ms    call_retries=1    retry_delay=0
    ...    return_values_only=True
    Should Be Equal    ${values}    ${{("answered",)}}

Invalid Retry Arguments Fail Before Anything Runs
    Run Keyword And Expect Error    ValueError: Invalid call_retries 'many'*
    ...    Run Parallel Scenarios    keyword=Fail Until Attempt    library=${PROBE}
    ...    for_loop_iterable=${{["F:1"]}}    call_retries=many
    Run Keyword And Expect Error    ValueError: retry_backoff must be at least 1, got '0.5'.
    ...    Run Parallel Scenarios    keyword=Fail Until Attempt    library=${PROBE}
    ...    for_loop_iterable=${{["F:1"]}}    call_retries=1    retry_backoff=0.5
