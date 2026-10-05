*** Settings ***
Documentation    Shared setup for the pabot + ParallelRunner timing demo.
...              Every suite in this folder validates ${ITEM_COUNT} items, each
...              taking ${DELAY} seconds of simulated I/O wait. ${MODE} decides
...              whether the loop runs sequentially or through ParallelRunner.
Library          Collections
Library          ParallelRunner
Library          examples.pabot_demo.demo_client.DemoClient


*** Variables ***
${MODE}          sequential
${ITEM_COUNT}    8
${DELAY}         1


*** Keywords ***
Validate All Items
    ${items}=    Evaluate    [str(i) for i in range(1, int(${ITEM_COUNT}) + 1)]
    IF    $MODE == 'parallel'
        ${validated}=    Run Parallel Scenarios
        ...    keyword=Validate Item
        ...    library=examples.pabot_demo.demo_client.DemoClient
        ...    for_loop_iterable=${items}
        ...    delay=${DELAY}
        ...    return_values_only=True
    ELSE
        ${validated}=    Create List
        FOR    ${item}    IN    @{items}
            ${value}=    Validate Item    ${item}    delay=${DELAY}
            Append To List    ${validated}    ${value}
        END
    END
    Lists Should Be Equal    ${validated}    ${items}
