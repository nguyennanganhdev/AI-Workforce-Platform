"""The sign-in limit: under whose address a try is counted behind our proxies, and that the count is one for
every copy of the API (it lives in PostgreSQL)."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request
from test_resident_contract import TENANT, sql
from test_resident_contract import database as database  # noqa: F401 -- pytest fixture export

from vinhomes_api import password_auth
from vinhomes_api.main import create_app
from vinhomes_api.v3_config import V3Settings

SOCKET = "172.18.0.5"  # whoever holds the connection: a proxy of ours, or the caller itself


def arriving(hops: int, *forwarded: str, real_ip: str | None = None) -> Request:
    headers = [(b"x-forwarded-for", value.encode()) for value in forwarded]
    if real_ip:
        headers.append((b"x-real-ip", real_ip.encode()))
    settings = V3Settings("127.0.0.1", 8000, None, None, None, trusted_proxy_hops=hops)
    return Request({"type": "http", "headers": headers, "client": (SOCKET, 40000),
                    "app": SimpleNamespace(state=SimpleNamespace(settings=settings))})


def test_without_a_proxy_of_ours_the_socket_is_the_caller_whatever_the_headers_say():
    assert password_auth.caller_address(arriving(0)) == SOCKET
    assert password_auth.caller_address(arriving(0, "198.51.100.1", real_ip="198.51.100.2")) == SOCKET


def test_behind_the_gateway_the_caller_is_the_address_the_gateway_added():
    # The gateway appends the address it was called from; what the caller wrote itself stands before it.
    assert password_auth.caller_address(arriving(1, "203.0.113.7")) == "203.0.113.7"
    assert password_auth.caller_address(arriving(1, "198.51.100.1, 203.0.113.7", real_ip="198.51.100.2")) == "203.0.113.7"
    assert password_auth.caller_address(arriving(1, "198.51.100.1", "10.9.9.9 , 203.0.113.7")) == "203.0.113.7"
    # A call that did not come through the gateway carries no entry of ours.
    assert password_auth.caller_address(arriving(1)) == SOCKET
    assert password_auth.caller_address(arriving(1, " , ", real_ip="198.51.100.2")) == SOCKET


def test_behind_caddy_and_the_gateway_the_caller_is_the_address_caddy_added():
    assert password_auth.caller_address(arriving(2, "203.0.113.7, 172.18.0.9")) == "203.0.113.7"
    assert password_auth.caller_address(arriving(2, "198.51.100.1, 203.0.113.7, 172.18.0.9")) == "203.0.113.7"
    # One entry only: the call skipped a proxy (Caddy straight to /mcp), so no entry is the caller's for sure.
    assert password_auth.caller_address(arriving(2, "198.51.100.1")) == SOCKET


def test_the_number_of_proxies_is_checked_at_start(monkeypatch):
    monkeypatch.setenv("VINHOMES_API_TRUSTED_PROXY_HOPS", "2")
    assert V3Settings.from_env().trusted_proxy_hops == 2
    monkeypatch.delenv("VINHOMES_API_TRUSTED_PROXY_HOPS")
    assert V3Settings.from_env().trusted_proxy_hops == 0
    monkeypatch.setenv("VINHOMES_API_TRUSTED_PROXY_HOPS", "3")
    with pytest.raises(ValueError):
        V3Settings.from_env()


@pytest.fixture()
def copies(database, monkeypatch):
    """Two copies of the API behind the gateway, on one database. The password check is skipped: it takes a
    third of a second and these tests only count tries."""
    monkeypatch.setattr(password_auth, "check_password", lambda password, encoded: False)
    settings = V3Settings("127.0.0.1", 8000, database["runtime"], TENANT, None, password_auth=True, trusted_proxy_hops=1)
    with TestClient(create_app(settings), client=(SOCKET, 40000)) as first, \
            TestClient(create_app(settings), client=(SOCKET, 40001)) as second:
        yield first, second


def attempt(api, address: str, name: str | None = None, forged: str = ""):
    return api.post("/auth/login", json={"identifier": name or f"{uuid4().hex}@example.invalid", "password": "wrong"},
                    headers={"X-Forwarded-For": forged + address, "X-Real-IP": "198.51.100.200"})


def test_each_address_has_its_own_budget_shared_by_every_copy_of_the_api(database, copies):
    sql(database, "delete from sign_in_attempts returning 1")
    address, other = "203.0.113.7", "203.0.113.8"
    for number in range(60):
        # Every try names another address in front of the real one: none of them is counted.
        assert attempt(copies[number % 2], address, forged=f"198.51.100.{number}, ").status_code == 401
    for api in copies:
        limited = attempt(api, address, forged="192.0.2.1, ")
        assert limited.status_code == 429 and limited.headers["Retry-After"] == "300"
    assert attempt(copies[0], other).status_code == 401
    # 60 tries under the one real address, one under the other, each with its account: nothing under a forged one.
    counts = sql(database, "select count(*) as tries from sign_in_attempts group by key order by 1 desc")
    assert [row["tries"] for row in counts] == [60] + [1] * 62


def test_an_account_has_one_budget_whatever_the_address_and_the_copy(database, copies):
    name = f"{uuid4().hex}@example.invalid"
    for number in range(10):
        assert attempt(copies[number % 2], f"203.0.113.{100 + number}", name).status_code == 401
    assert attempt(copies[1], "203.0.113.120", name).status_code == 429
    # A copy that starts now finds the same count: a restart hands out no new budget.
    settings = V3Settings("127.0.0.1", 8000, database["runtime"], TENANT, None, password_auth=True, trusted_proxy_hops=1)
    with TestClient(create_app(settings), client=(SOCKET, 40002)) as started:
        assert attempt(started, "203.0.113.121", name).status_code == 429
    # The table holds digests only.
    stored = sql(database, "select key from sign_in_attempts")
    assert stored and all(len(row["key"]) == 64 and "@" not in row["key"] and "." not in row["key"] for row in stored)


def test_tries_older_than_the_window_are_forgotten_and_removed(database, copies):
    name = f"{uuid4().hex}@example.invalid"
    for number in range(10):
        assert attempt(copies[0], "203.0.113.130", name).status_code == 401
    assert attempt(copies[0], "203.0.113.130", name).status_code == 429
    sql(database, "update sign_in_attempts set at=at-interval '6 minutes' returning 1")
    assert attempt(copies[1], "203.0.113.130", name).status_code == 401
    assert sql(database, "select count(*) as kept from sign_in_attempts")[0]["kept"] == 2
