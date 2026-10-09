"""Clients, delegations and the tool catalog (docs/domain/HOP_DONG_TICH_HOP.md sections 2 to 4)."""

import re
from contextlib import contextmanager
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from test_resident_contract import TENANT, sql
from test_resident_contract import database as database  # noqa: F401 -- pytest fixture export

from vinhomes_api.integration import TOOLS, new_secret, digest
from vinhomes_api.main import create_app
from vinhomes_api.v3_config import V3Settings

CLIENT = "demo-platform"
RESIDENT = "local-v3-resident"
MANAGER = "local-v3-management"
HEADERS = {"Idempotency-Key": "x"}


@contextmanager
def person(database, user):
    """A signed-in person (the local development identity)."""
    settings = V3Settings("127.0.0.1", 8000, database["runtime"], TENANT, user, resident_allowed_origins=("http://testserver",))
    with TestClient(create_app(settings), client=("127.0.0.1", 50000)) as c:
        yield c


@contextmanager
def outsider(database):
    """A caller with no sign-in of its own: only a client secret or a delegation can get it in."""
    settings = V3Settings("127.0.0.1", 8000, database["runtime"], TENANT, None)
    with TestClient(create_app(settings), client=("203.0.113.9", 50000)) as c:
        yield c


def mint(database, user=RESIDENT, purpose="resident_assistant", **extra):
    with person(database, user) as c:
        response = c.post("/integration/v1/delegations/self", headers={"Idempotency-Key": str(uuid4())},
                          json={"client_id": CLIENT, "purpose": purpose, **extra})
    assert response.status_code == 201, response.text
    return response.json()


def bearer(token):
    return {"Authorization": "Bearer " + token}


@pytest.fixture()
def secret(database):
    value = new_secret()
    sql(database, "update integration_clients set secret_hash=$1,status='active' where id=$2 returning id", digest(value), CLIENT)
    yield value
    sql(database, "update integration_clients set secret_hash=null,secret_hash_next=null,status='active' where id=$1 returning id", CLIENT)


def test_a_signed_in_person_lets_a_client_act_for_them_with_limited_scopes(database):
    token = mint(database)
    assert token["token"].startswith("dg1_") and token["persona"] == "resident"
    assert token["scopes"] == ["read", "draft", "act_small"]
    row = sql(database, "select client_id,user_id,status,persona,token_hash from delegations where id=$1", UUID(token["delegation_id"]))[0]
    assert row["client_id"] == CLIENT and row["user_id"] == RESIDENT and row["status"] == "active"
    assert row["token_hash"] == digest(token["token"]) and token["token"] not in str(row)


def test_the_token_acts_as_that_person_and_only_for_catalog_operations(database):
    token = mint(database)["token"]
    with outsider(database) as c:
        me = c.get("/resident/me", headers=bearer(token))
        assert me.status_code == 200, me.text
        assert c.get("/resident/tickets", headers=bearer(token)).status_code == 200
        # Not in the catalog: it looks like it does not exist.
        assert c.get("/admin/accounts", headers=bearer(token)).status_code == 404
        assert c.post("/resident/plans/" + str(uuid4()) + "/decision", headers={**bearer(token), **HEADERS},
                      json={"decision": "approve", "version": 0, "note": "ok"}).status_code == 404
        # The catalog names the persona: a resident delegation is not staff.
        assert c.get("/tickets", headers=bearer(token)).status_code == 403
        # Without a token the same caller is nobody.
        assert c.get("/resident/me").status_code in (401, 503)


def test_staff_delegation_reaches_staff_operations_with_the_persons_own_rights(database):
    token = mint(database, MANAGER, "staff_assistant")
    assert token["scopes"] == ["read", "draft", "propose"] and token["persona"] == "staff"
    with outsider(database) as c:
        assert c.get("/operations/me", headers=bearer(token["token"])).status_code == 200
        assert c.get("/tickets", headers=bearer(token["token"])).status_code == 200
        assert c.get("/resident/tickets", headers=bearer(token["token"])).status_code == 403


def test_a_resident_cannot_get_a_staff_delegation(database):
    with person(database, RESIDENT) as c:
        response = c.post("/integration/v1/delegations/self", headers={"Idempotency-Key": str(uuid4())},
                          json={"client_id": CLIENT, "purpose": "staff_assistant"})
        assert response.status_code == 403
        assert c.post("/integration/v1/delegations/self", headers={"Idempotency-Key": str(uuid4())},
                      json={"client_id": "no-such-client", "purpose": "resident_assistant"}).status_code == 404


def test_a_delegation_cannot_create_another_and_a_key_is_used_once(database):
    token = mint(database)["token"]
    with outsider(database) as c:
        again = c.post("/integration/v1/delegations/self", headers={**bearer(token), **HEADERS},
                       json={"client_id": CLIENT, "purpose": "resident_assistant"})
        assert again.status_code in (403, 404)
    with person(database, RESIDENT) as c:
        key = {"Idempotency-Key": str(uuid4())}
        body = {"client_id": CLIENT, "purpose": "resident_assistant"}
        assert c.post("/integration/v1/delegations/self", headers=key, json=body).status_code == 201
        assert c.post("/integration/v1/delegations/self", headers=key, json=body).status_code == 409


def test_an_expired_revoked_or_over_used_delegation_stops_working(database):
    expired = mint(database)
    sql(database, "update delegations set expires_at=now()-interval '1 minute' where id=$1 returning id", UUID(expired["delegation_id"]))
    with outsider(database) as c:
        assert c.get("/resident/me", headers=bearer(expired["token"])).status_code == 401
    assert sql(database, "select status,error_code from delegations where id=$1", UUID(expired["delegation_id"]))[0] == {"status": "failed", "error_code": "expired"}

    used = mint(database)
    sql(database, "update delegations set calls=120 where id=$1 returning id", UUID(used["delegation_id"]))
    with outsider(database) as c:
        limited = c.get("/resident/me", headers=bearer(used["token"]))
        assert limited.status_code == 429 and limited.headers["Retry-After"]

    revoked = mint(database)
    sql(database, "update integration_clients set status='disabled' where id=$1 returning id", CLIENT)
    try:
        with outsider(database) as c:
            assert c.get("/resident/me", headers=bearer(revoked["token"])).status_code == 403
    finally:
        sql(database, "update integration_clients set status='active' where id=$1 returning id", CLIENT)
    assert sql(database, "select status from delegations where id=$1", UUID(revoked["delegation_id"]))[0]["status"] == "revoked"


def test_losing_the_persons_membership_revokes_the_delegation_at_once(database):
    token = mint(database)
    sql(database, "update tenant_memberships set status='suspended' where user_id=$1 returning id", RESIDENT)
    try:
        with outsider(database) as c:
            assert c.get("/resident/me", headers=bearer(token["token"])).status_code == 403
    finally:
        sql(database, "update tenant_memberships set status='active' where user_id=$1 returning id", RESIDENT)


def test_a_client_with_its_secret_sees_only_the_tools_it_may_use(database, secret):
    with outsider(database) as c:
        assert c.get("/integration/v1/tools").status_code == 401
        assert c.get("/integration/v1/tools", headers={"X-Client-Id": CLIENT, **bearer("ics_wrong")}).status_code == 401
        listed = c.get("/integration/v1/tools", headers={"X-Client-Id": CLIENT, **bearer(secret)})
        assert listed.status_code == 200, listed.text
        names = [t["name"] for t in listed.json()["tools"]]
        assert len(names) == len(set(names))
        # The seeded client may read, draft and act small for residents, and read, draft and propose for staff.
        allowed = {t.name for t in TOOLS if t.persona == "resident" and t.level in {"read", "draft", "act_small"}
                   or t.persona == "staff" and t.level in {"read", "draft", "propose"}}
        assert set(names) == allowed
        sql(database, "update integration_clients set levels='{\"resident\":[\"read\"]}'::jsonb where id=$1 returning id", CLIENT)
        try:
            narrow = c.get("/integration/v1/tools", headers={"X-Client-Id": CLIENT, **bearer(secret)}).json()["tools"]
            assert narrow and all(t["persona"] == "resident" and t["level"] == "read" for t in narrow)
        finally:
            sql(database, "update integration_clients set levels='{\"resident\":[\"read\",\"draft\",\"act_small\"],\"staff\":[\"read\",\"draft\",\"propose\"]}'::jsonb where id=$1 returning id", CLIENT)
        sql(database, "update integration_clients set status='disabled' where id=$1 returning id", CLIENT)
        try:
            assert c.get("/integration/v1/tools", headers={"X-Client-Id": CLIENT, **bearer(secret)}).status_code == 403
        finally:
            sql(database, "update integration_clients set status='active' where id=$1 returning id", CLIENT)


def test_every_tool_is_a_real_operation_and_none_decides_for_a_person(database, secret):
    forbidden = re.compile(r"(decision|approve|confirm|issue|payment|refund|/qc|redo|roles|accounts|memberships|close|status|assignments|reopen|budget)")
    with outsider(database) as c:
        tools = c.get("/integration/v1/tools", headers={"X-Client-Id": CLIENT, **bearer(secret)}).json()["tools"]
    assert len(tools) == len([t for t in TOOLS if t.level in {"read", "draft", "act_small", "propose"}]), "a tool names a route that does not exist"
    for tool in TOOLS:
        assert not forbidden.search(tool.path), f"{tool.name} reaches a decision that belongs to a person"
    # Only the staff catalog proposes; residents never propose.
    assert all(t.persona == "staff" for t in TOOLS if t.level == "propose")


def test_only_the_client_ends_a_delegation(database, secret):
    token = mint(database)
    with outsider(database) as c:
        wrong = c.post(f"/integration/v1/delegations/{token['delegation_id']}/finish", headers=bearer(token["token"]), json={})
        assert wrong.status_code == 403
        done = c.post(f"/integration/v1/delegations/{token['delegation_id']}/finish", headers={"X-Client-Id": CLIENT, **bearer(secret)},
                      json={"status": "finished", "usage": {"input_tokens": 10, "output_tokens": 2}})
        assert done.status_code == 200, done.text
        assert c.get("/resident/me", headers=bearer(token["token"])).status_code == 401
    row = sql(database, "select status,input_tokens,output_tokens from delegations where id=$1", UUID(token["delegation_id"]))[0]
    assert row == {"status": "finished", "input_tokens": 10, "output_tokens": 2}


def test_integration_errors_have_the_documented_shape(database):
    with outsider(database) as c:
        refused = c.get("/integration/v1/tools", headers={"X-Correlation-Id": "trace-1"})
        assert refused.status_code == 401
        body = refused.json()["error"]
        assert body["code"] == "UNAUTHENTICATED" and body["retryable"] is False and body["correlation_id"] == "trace-1"
        assert refused.headers["X-Correlation-Id"] == "trace-1"
    with person(database, RESIDENT) as c:
        bad = c.post("/integration/v1/delegations/self", headers={"Idempotency-Key": "x"}, json={"client_id": CLIENT, "purpose": "nonsense"})
        assert bad.status_code == 422 and bad.json()["error"]["code"] == "VALIDATION_FAILED" and bad.json()["error"]["details"]
