*** Settings ***
Library    ParallelRunner
Library    examples.api_client.api_client.ApiClient


*** Variables ***
${test_library}  examples.api_client.api_client.ApiClient
@{scenarios}    1    2    3    4    5   6   7   8   9

*** Test Cases ***
Verify Agents In Parallel
    # New Parallel way:
    Run Parallel Scenarios    keyword=Validate Agents Data With Steps    for_loop_iterable=${scenarios}    library=${test_library}

Verify Agents Sequentially
    FOR    ${agent}    IN    @{scenarios}
        Validate Agents Data With Steps    ${agent}
    END
