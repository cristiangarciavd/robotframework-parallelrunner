*** Settings ***
Library    parallelrunner.parallel_library.ParallelLibrary
Library    examples.api_client.api_client.ApiClient

*** Variables ***
${test_library}    examples.api_client.api_client.ApiClient

*** Test Cases ***
Create Records In Parallel
    [Documentation]    `repeat` (not `for_loop_iterable`) is the right tool when there is
    ...    no pre-existing list of items to iterate - only "do this N times", e.g. seeding
    ...    N independent test records in a Suite Setup. The loop index that `repeat`
    ...    generates internally is used by the keyword only to keep each record's payload
    ...    unique; a value shared by every call (`title_prefix`) is passed as a kwarg
    ...    instead of being repeated N times in a list.
    ${results}=    Run Parallel Scenarios
    ...    keyword=Create Test Record
    ...    library=${test_library}
    ...    repeat=5
    ...    title_prefix=fixture
    Log    ${results}
    Length Should Be    ${results}    5

Repeated Health Check Against Fixed Endpoint
    [Documentation]    `repeat` also fits "call this one fixed endpoint N times
    ...    concurrently" - a light concurrent load check, or a way to catch failures
    ...    that only appear when the same endpoint is hit by several threads at once.
    ...    The target (`agent_id`) is identical for every call; only the call index differs.
    ${results}=    Run Parallel Scenarios
    ...    keyword=Check Endpoint Health
    ...    library=${test_library}
    ...    repeat=8
    ...    agent_id=1
    Log    ${results}
    Length Should Be    ${results}    8

For Loop Iterable Takes Precedence Over Repeat
    [Documentation]    Documents/verifies the precedence rule from the API reference:
    ...    if both `for_loop_iterable` and `repeat` are given, `for_loop_iterable` wins
    ...    and `repeat` is ignored entirely - the number of tasks matches the list length,
    ...    not `repeat`.
    ${agents}=    Create List    1    2    3
    ${results}=    Run Parallel Scenarios
    ...    keyword=Check Endpoint Health
    ...    library=${test_library}
    ...    for_loop_iterable=${agents}
    ...    repeat=10
    ...    agent_id=1
    Length Should Be    ${results}    3

Neither For Loop Iterable Nor Repeat Runs Once
    [Documentation]    If neither `for_loop_iterable` nor `repeat` is given, the keyword
    ...    still runs exactly once (`range(repeat or 1)` defaults to `range(1)`) - useful
    ...    for a single one-off call that still benefits from the same buffered-log
    ...    replay and structured result as a parallel run.
    ${results}=    Run Parallel Scenarios
    ...    keyword=Check Endpoint Health
    ...    library=${test_library}
    ...    agent_id=1
    Length Should Be    ${results}    1

Repeat With Return Values Only Unpacks Each Record Directly
    [Documentation]    `return_values_only=True` pairs naturally with `repeat`: since
    ...    there is no input list to zip results against, getting back a plain
    ...    tuple - one entry per repeat call, in call order - lets each record be
    ...    unpacked straight into its own variable instead of digging through a
    ...    list of result dictionaries. Results are guaranteed to be in call order
    ...    (repeat index 0, 1, 2, ...), not completion order, so `record1` here is
    ...    always the index-0 call. See tests/robot/test_return_values.robot for
    ...    the full ordering/failure guarantees and the standalone
    ...    `Get Result Values` keyword.
    ${record1}    ${record2}    ${record3}=    Run Parallel Scenarios
    ...    keyword=Create Test Record
    ...    library=${test_library}
    ...    repeat=3
    ...    title_prefix=fixture
    ...    return_values_only=True
    Should Be Equal    ${record1}[title]    fixture-0
    Should Be Equal    ${record2}[title]    fixture-1
    Should Be Equal    ${record3}[title]    fixture-2
