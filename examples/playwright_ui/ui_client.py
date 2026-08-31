from typing import Callable, Optional
from robot.api import logger
from playwright.sync_api import sync_playwright


def default_log(msg, level="INFO"):
    if level == "INFO":
        logger.info(msg)
    elif level == "WARN":
        logger.warn(msg)
    elif level == "ERROR":
        logger.error(msg)
    else:
        logger.info(msg)


class UiClient:
    """
    UI automation example using Playwright's official `sync_api`
    (https://playwright.dev/python/), demonstrating that ParallelRunner's
    thread-based parallelism also applies to browser automation, not just
    plain HTTP calls.

    Thread-safety: Playwright's sync API is not safe to share a single
    Browser/Page instance across threads. `check_page_title` avoids this by
    launching and closing its own browser on every call, so each parallel
    task is fully self-contained and safe to run concurrently from
    ParallelRunner's thread pool. This is much heavier per task than an HTTP
    request (each call starts a real Chromium instance) - keep
    ROBOT_THREAD_WORKERS low (2-4) when running this rather than the higher
    values that make sense for API calls.
    """

    def check_page_title(self, url: str, _logger: Optional[Callable] = None, **kwargs) -> dict:
        log = _logger if _logger else default_log
        expected_title = kwargs.get("expected_title")

        log(f"Opening {url}")
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                page = browser.new_page()
                page.goto(url, timeout=15000)
                title = page.title()
                log(f"{url} -> title: '{title}'")

                if expected_title is not None and title != expected_title:
                    log(f"Unexpected title for {url}: got '{title}', expected '{expected_title}'", "ERROR")
                    raise AssertionError(
                        f"Unexpected title for {url}: got '{title}', expected '{expected_title}'"
                    )

                return {"url": url, "title": title}
            finally:
                browser.close()
