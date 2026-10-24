*** Settings ***
Documentation     A keyword called through `Run Parallel Scenarios` is found and
...               receives its arguments the same way as when the test calls it
...               directly. Offline (no network).
...
...               Regression suite: before 0.4.0 a keyword with a custom name
...               (`@keyword("...")`) was not found, and named arguments were
...               passed as strings instead of being converted by their type
...               hints (`delay=0.5` arrived as "0.5", not 0.5).
Library           ParallelRunner
Library           atest.resources.KeywordProbe


*** Variables ***
${PROBE}          atest.resources.KeywordProbe


*** Test Cases ***
Named Arguments Are Converted Like In A Direct Call
    ${direct}=    Describe Arguments    7    delay=0.5    enabled=yes    tags=['a', 'b']
    ${parallel}=    Run Parallel Scenarios    keyword=Describe Arguments    library=${PROBE}
    ...    for_loop_iterable=${{["7"]}}    delay=0.5    enabled=yes    tags=['a', 'b']
    ...    return_values_only=True
    Should Be Equal    ${parallel}[0]    ${direct}
    Should Be Equal    ${direct}[delay]    ${{[0.5, "float"]}}
    Should Be Equal    ${direct}[tags]    ${{[["a", "b"], "list"]}}

String Items Are Converted, Other Items Are Passed As They Are
    ${results}=    Run Parallel Scenarios    keyword=Describe Arguments    library=${PROBE}
    ...    for_loop_iterable=${{["1", 2]}}
    Should Be Equal    ${results}[0][result][item]    ${{[1, "int"]}}
    Should Be Equal    ${results}[1][result][item]    ${{[2, "int"]}}
    Should Be Equal    ${results}[0][item]    1    # results keep the original item

An Item That Cannot Be Converted Fails Only That Call
    ${results}=    Run Parallel Scenarios    keyword=Describe Arguments    library=${PROBE}
    ...    for_loop_iterable=${{["1", "x"]}}    fail_on_error=False
    Should Be Equal    ${results}[0][status]    PASS
    Should Be Equal    ${results}[1][error]    Argument 'item' got value 'x' that cannot be converted to integer.

A Bad Named Argument Fails Before Running Anything
    Run Keyword And Expect Error    ValueError: Argument 'delay' got value 'slow' that cannot be converted to float.
    ...    Run Parallel Scenarios    keyword=Describe Arguments    library=${PROBE}
    ...    repeat=3    delay=slow

Keyword With A Custom Name Is Found
    ${values}=    Run Parallel Scenarios    keyword=Check Order Status    library=${PROBE}
    ...    for_loop_iterable=${{["A-1", "A-2"]}}    return_values_only=True
    Should Be Equal    ${values}    ${{("status of A-1", "status of A-2")}}

Keyword Names Ignore Case, Spaces And Underscores
    FOR    ${name}    IN    describe arguments    DescribeArguments    describe_arguments
        ${values}=    Run Parallel Scenarios    keyword=${name}    library=${PROBE}
        ...    repeat=1    return_values_only=True
        Should Be Equal    ${values}[0][item]    ${{[0, "int"]}}
    END
