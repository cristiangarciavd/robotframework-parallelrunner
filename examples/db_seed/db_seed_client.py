import os
import sqlite3
import tempfile
from typing import Callable, Optional
from robot.api import logger


def default_log(msg, level="INFO"):
    if level == "INFO":
        logger.info(msg)
    elif level == "WARN":
        logger.warn(msg)
    elif level == "ERROR":
        logger.error(msg)
    else:
        logger.info(msg)


class DbSeedClient:
    """
    Example library for a very common QA automation need: seeding N
    independent fixture rows into a database *before* a test runs (test
    data setup), and needing each row's generated primary key right away -
    e.g. to look the record up again in a later step, or to clean it up in
    a Suite/Test Teardown.

    This is the flagship use case for `run_parallel_scenarios`'s
    `return_values_only` parameter: pass `repeat=N`, and unpack each row's
    generated id straight into its own variable instead of digging through
    a list of result dictionaries.

    Backed by a local SQLite database (stdlib `sqlite3`) so the example has
    no external dependency, no network flakiness, and is fully
    deterministic - only the *pattern* (parallel INSERT + `repeat` +
    `return_values_only`) matters here, not the specific database engine.
    The same approach applies directly to a real Postgres/MySQL connection
    pool, an internal admin/provisioning API, or a cloud SDK call that
    creates a resource and returns its id (an S3 bucket, a feature flag, a
    tenant record, ...).

    `ROBOT_LIBRARY_SCOPE = 'GLOBAL'`: one instance (and therefore one
    `db_path`) is shared for the whole suite, so a `Suite Setup` call to
    `initialize_schema` and the later parallel `seed_fixture_record` calls
    all operate on the same underlying database file.
    """

    ROBOT_LIBRARY_SCOPE = 'GLOBAL'

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or os.path.join(tempfile.gettempdir(), "parallelrunner_example_fixtures.db")

    def _connect(self) -> sqlite3.Connection:
        # `timeout` makes concurrent writers from different threads/connections
        # wait for the database lock instead of immediately raising
        # "database is locked" - SQLite still serializes writes internally,
        # which is fine here: the point of the example is the
        # repeat/return_values_only calling pattern, not raw write throughput.
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.execute("PRAGMA busy_timeout = 30000")
        return conn

    def initialize_schema(self) -> None:
        """
        Create (or reset) the `fixtures` table. Call this once, sequentially
        (e.g. from `Suite Setup`), before seeding rows in parallel.
        """
        conn = self._connect()
        try:
            conn.execute("DROP TABLE IF EXISTS fixtures")
            conn.execute(
                "CREATE TABLE fixtures ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "name TEXT NOT NULL, "
                "created_by_call_index INTEGER NOT NULL"
                ")"
            )
            conn.commit()
        finally:
            conn.close()

    def seed_fixture_record(self, call_index: int, _logger: Optional[Callable] = None, **kwargs) -> int:
        """
        Insert one fixture row and return its generated primary key.

        Meant to be driven by `repeat`, not `for_loop_iterable`: there is no
        pre-existing list of rows to create, only "insert N independent
        fixture rows concurrently" (e.g. seeding N tenant/user/order records
        in a Suite Setup ahead of a data-migration test). `call_index` is
        only used to keep each row's `name` unique across the N parallel
        calls - it is NOT the primary key, the database assigns that. A
        value shared by every call (`name_prefix`) is passed as a kwarg
        instead of being repeated N times in a list.
        """
        log = _logger if _logger else default_log

        name_prefix = kwargs.get("name_prefix", "fixture")
        name = f"{name_prefix}-{call_index}"
        log(f"Inserting fixture row '{name}'")

        conn = self._connect()
        try:
            cursor = conn.execute(
                "INSERT INTO fixtures (name, created_by_call_index) VALUES (?, ?)",
                (name, call_index),
            )
            conn.commit()
            new_id = cursor.lastrowid
            log(f"Row '{name}' inserted with id {new_id}")
            return new_id
        except sqlite3.Error as e:
            log(f"Failed to insert row '{name}': {e}", "ERROR")
            raise
        finally:
            conn.close()

    def count_fixture_rows(self) -> int:
        """Sequential helper for assertions: total rows currently in the table."""
        conn = self._connect()
        try:
            return conn.execute("SELECT COUNT(*) FROM fixtures").fetchone()[0]
        finally:
            conn.close()
