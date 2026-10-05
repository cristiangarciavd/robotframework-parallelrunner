*** Settings ***
Library    ParallelRunner
Library    examples.playwright_ui.ui_client.UiClient

*** Variables ***
${test_library}    examples.playwright_ui.ui_client.UiClient

*** Test Cases ***
Check Page Titles In Parallel
    [Documentation]    Demonstrates ParallelRunner driving Playwright browsers concurrently:
    ...    one worker thread per page, each opening and closing its own Chromium instance
    ...    (see the thread-safety note in ui_client.py). Uses the IANA-reserved example
    ...    domains (example.com/.net/.org), which are guaranteed stable, static, and safe
    ...    to hit in an automated test - no real product or third-party site involved.
    ${pages}=    Create List
    ...    https://example.com
    ...    https://example.net
    ...    https://example.org
    ${results}=    Run Parallel Scenarios
    ...    keyword=Check Page Title
    ...    library=${test_library}
    ...    for_loop_iterable=${pages}
    ...    expected_title=Example Domain
    Log    ${results}
    Length Should Be    ${results}    3
