*** Settings ***
Documentation     Result ordering guarantees, plus the `return_values_only` parameter
...               and the standalone `Get Result Values` keyword for extracting plain
...               return values out of a `repeat` / `for_loop_iterable` run.
Library    Collections
Library    ParallelRunner
Library    examples.api_client.api_client.ApiClient
Library    examples.db_seed.db_seed_client.DbSeedClient
Suite Setup    Initialize Schema

*** Variables ***
${test_library}    examples.api_client.api_client.ApiClient
${db_library}    examples.db_seed.db_seed_client.DbSeedClient

*** Test Cases ***
Results Preserve Call Order For Repeat
    [Documentation]    `results[i]` must correspond to repeat index `i`, regardless
    ...    of which thread happens to finish first - callers can index into the
    ...    returned list directly instead of sorting by `item` themselves.
    ${results}=    Run Parallel Scenarios
    ...    keyword=Check Endpoint Health
    ...    library=${test_library}
    ...    repeat=6
    ...    agent_id=1
    FOR    ${index}    ${entry}    IN ENUMERATE    @{results}
        Should Be Equal As Integers    ${entry}[item]    ${index}
    END

Results Preserve Call Order For For Loop Iterable
    [Documentation]    Same order guarantee for `for_loop_iterable`: `results[i]`
    ...    corresponds to `for_loop_iterable[i]`, not to completion order.
    @{agents}=    Create List    1    2    3    4    5
    ${results}=    Run Parallel Scenarios
    ...    keyword=Verify Agent Data
    ...    library=${test_library}
    ...    for_loop_iterable=${agents}
    FOR    ${index}    ${entry}    IN ENUMERATE    @{results}
        ${expected}=    Get From List    ${agents}    ${index}
        Should Be Equal As Strings    ${entry}[item]    ${expected}
    END

Return Values Only With Repeat Unpacks Each Row Id Directly
    [Documentation]    The flagship `repeat` + `return_values_only` use case: seed
    ...    4 independent fixture rows in parallel via `repeat`, and unpack each
    ...    row's generated primary key straight into its own variable - exactly
    ...    like Robot Framework's native multi-assignment - instead of digging
    ...    through a list of result dictionaries.
    ${id1}    ${id2}    ${id3}    ${id4}=    Run Parallel Scenarios
    ...    keyword=Seed Fixture Record
    ...    library=${db_library}
    ...    repeat=4
    ...    name_prefix=return_values_test
    ...    return_values_only=True
    Should Not Be Equal    ${id1}    ${id2}
    Should Not Be Equal    ${id1}    ${id3}
    Should Not Be Equal    ${id1}    ${id4}
    ${count}=    Count Fixture Rows
    Should Be True    ${count} >= 4

Return Values Only With For Loop Iterable Returns Plain Tuple
    [Documentation]    Realistic post-deployment smoke test: hit several
    ...    different service routes concurrently and assert every one is
    ...    healthy, using `return_values_only` to get back a plain tuple of
    ...    status codes instead of a list of result dictionaries.
    @{endpoints}=    Create List    users/1    posts/1    albums/1
    ${status_codes}=    Run Parallel Scenarios
    ...    keyword=Smoke Test Endpoint
    ...    library=${test_library}
    ...    for_loop_iterable=${endpoints}
    ...    return_values_only=True
    Length Should Be    ${status_codes}    3
    FOR    ${code}    IN    @{status_codes}
        Should Be Equal As Integers    ${code}    200
    END

Return Values Only Raises When A Task Fails
    [Documentation]    A failed task has no meaningful return value - raise
    ...    loudly (`ParallelTaskError`) instead of silently returning `None`
    ...    for it, so the test fails for the right reason instead of passing
    ...    with a hole in the data.
    @{agents}=    Create List    1    2    3    4    5
    ${status}    ${message}=    Run Keyword And Ignore Error
    ...    Run Parallel Scenarios
    ...    keyword=Validate Agents With Errors
    ...    library=${test_library}
    ...    for_loop_iterable=${agents}
    ...    return_values_only=True
    Should Be Equal    ${status}    FAIL
    Should Contain    ${message}    parallel task(s) failed

Get Result Values Extracts A Tuple From An Existing Result List
    [Documentation]    `Get Result Values` is also usable standalone, on a result
    ...    list already collected via the default `return_values_only=False`
    ...    call - e.g. after inspecting `status`/`logs` first - instead of only
    ...    through `return_values_only=True`.
    @{agents}=    Create List    1    2    3
    ${results}=    Run Parallel Scenarios
    ...    keyword=Verify Agent Data
    ...    library=${test_library}
    ...    for_loop_iterable=${agents}
    ${values}=    Get Result Values    ${results}
    Length Should Be    ${values}    3
    FOR    ${index}    ${value}    IN ENUMERATE    @{values}
        Should Be Equal    ${value}[id]    ${results}[${index}][result][id]
    END

Get Result Values Raises When A Task Failed
    [Documentation]    Same failure guard as `return_values_only=True`, but
    ...    invoked standalone against an already-collected result list.
    @{agents}=    Create List    1    2    3    4    5
    ${results}=    Run Parallel Scenarios
    ...    keyword=Validate Agents With Errors
    ...    library=${test_library}
    ...    for_loop_iterable=${agents}
    ${status}    ${message}=    Run Keyword And Ignore Error
    ...    Get Result Values    ${results}
    Should Be Equal    ${status}    FAIL
    Should Contain    ${message}    parallel task(s) failed
