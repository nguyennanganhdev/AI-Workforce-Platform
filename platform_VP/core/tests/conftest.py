"""Run-wide setup: which database the tests use (tests/dbtest.py) and the cleanup of the PostgreSQL databases they made."""
import pytest

import dbtest


def pytest_report_header(config):
    return "database: " + (f"PostgreSQL ({dbtest.PG_URL.rsplit('@', 1)[-1]})" if dbtest.IS_PG else "SQLite files")


@pytest.fixture(autouse=True)
def _drop_the_databases_of_the_test(tmp_path):
    yield  # shared (module) fixtures drop their own, or the end of the session does
    dbtest.drop(str(tmp_path))


def pytest_sessionfinish(session, exitstatus):
    dbtest.drop_all()
