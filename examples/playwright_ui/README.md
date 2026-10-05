# Playwright UI Automation Example (Optional)

Demonstrates that ParallelRunner's thread-based parallelism also works for
browser/UI automation, not just plain HTTP calls - using Playwright's
**official** Python package (https://playwright.dev/python/), not a
third-party wrapper.

## Why this lives outside the normal install/test path

- It pulls in a heavy dependency: the `playwright` pip package plus a
  downloaded Chromium binary (`playwright install chromium`, ~150 MB+).
- It is **not** included in `poetry install`, and it is **not**
  run by `.github/workflows/tests.yml` or the documented
  `robot --pythonpath . atest/` command - this suite lives at
  `examples/playwright_ui/test_playwright_ui.robot`, outside `atest/`,
  precisely so it is never swept up by the default test run.
- You opt in deliberately, on your own machine, when you actually want to
  try it.

## Thread-safety note

Playwright's sync API is **not** safe to share a single `Browser`/`Page`
instance across threads. `UiClient.check_page_title` (in `ui_client.py`)
avoids this by launching and closing its own Chromium instance on every
call - each parallel task is fully self-contained. That makes it safe to
run from ParallelRunner's thread pool, but also much heavier per task than
an HTTP request (every call starts a real browser). If you adapt this
pattern, keep `ROBOT_THREAD_WORKERS` low (2-4) rather than the higher
values that make sense for API calls.

## Install

```bash
poetry install --extras playwright-example
# or, with plain pip: pip install -e ".[playwright-example]"
playwright install chromium
```

## Run

```bash
robot --pythonpath . examples/playwright_ui/test_playwright_ui.robot
```

This opens `https://example.com`, `https://example.net`, and
`https://example.org` (IANA-reserved example domains - stable, static,
safe for automated tests) concurrently and asserts each page's title.
