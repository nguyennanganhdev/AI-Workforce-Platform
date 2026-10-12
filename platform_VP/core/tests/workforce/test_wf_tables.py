"""Spec section 4: every table exists, with the constraints the spec implies."""
import asyncio
import re

import pytest

import dbtest
from awp.config import Settings
from awp.db import Database
from awp.workforce.tables import new_id

TABLES = {
    "wf_clients", "wf_keys", "wf_signing_keys", "wf_integrations", "wf_routes", "wf_mcp_servers",
    "wf_tools", "wf_residences", "wf_conversations", "wf_workflows", "wf_requests", "wf_messages",
    "wf_events", "wf_event_tombstones", "wf_turns", "wf_jobs", "wf_approvals", "wf_operations",
    "wf_provider_inbox", "wf_assets"}


@pytest.fixture
def con(tmp_path):
    where = dbtest.one(tmp_path, "t.db")
    db = Database(where.url)

    async def make():  # one loop for both: a PostgreSQL connection belongs to the loop that opened it
        await db.create_all()
        await db.dispose()

    asyncio.run(make())
    c = dbtest.connect(where)
    yield c
    c.close()


def test_create_all_makes_every_workforce_table(con):
    have = con.tables()
    assert TABLES <= have
    assert "awp_cases" in have  # the old tables are still there


def test_spec_columns_are_present(con):
    cols = con.columns

    assert {"id", "tenant", "domain", "environment", "name", "status", "capabilities", "created_at"} <= cols("wf_clients")
    assert {"key_id", "client_id", "integration_id", "kind", "secret_hash", "operations", "routes", "status",
            "expires_at", "created_at", "revoked_at"} <= cols("wf_keys")
    assert {"id", "client_id", "external_management_ref", "status", "revision", "leader_profile",
            "config", "created_at"} <= cols("wf_routes")
    assert {"workflow_id", "trigger", "msg_id", "job_id", "status"} <= cols("wf_turns")  # 13.12
    assert {"client_reference", "args_hash", "external_job_id", "last_rank", "provider_version"} <= cols("wf_operations")
    assert {"arguments_hash", "quote_ref", "workflow_revision", "expires_at"} <= cols("wf_approvals")
    assert "secret_enc" in cols("wf_signing_keys") and "secret" not in cols("wf_signing_keys")


def test_new_id_has_prefix_and_uuid():
    a, b = new_id("req"), new_id("req")
    assert a != b and re.fullmatch(r"req_[0-9a-f]{32}", a)


def _ins(con, table, **v):
    con.execute(f"insert into {table} ({','.join(v)}) values ({','.join('?' * len(v))})", list(v.values()))


def test_key_must_belong_to_exactly_one_owner(con):
    base = dict(kind="customer", secret_hash="h", operations="[]", routes="[]", status="active", created_at=1)
    _ins(con, "wf_keys", key_id="k1", client_id="c1", **base)
    with pytest.raises(dbtest.IntegrityError):
        _ins(con, "wf_keys", key_id="k2", **base)  # no owner
    with pytest.raises(dbtest.IntegrityError):
        _ins(con, "wf_keys", key_id="k3", client_id="c1", integration_id="i1", **base)
    with pytest.raises(dbtest.IntegrityError):
        _ins(con, "wf_keys", key_id="k4", client_id="c1", **{**base, "kind": "provider"})


def test_only_one_active_route_per_ref_in_a_client(con):
    r = dict(client_id="c1", external_management_ref="REF", revision=1, leader_profile="x", config="{}", created_at=1)
    _ins(con, "wf_routes", id="r1", status="active", **r)
    _ins(con, "wf_routes", id="r2", status="pending", **r)  # pending and replaced may repeat
    _ins(con, "wf_routes", id="r3", status="replaced", **r)
    with pytest.raises(dbtest.IntegrityError):
        _ins(con, "wf_routes", id="r4", status="active", **r)
    _ins(con, "wf_routes", id="r5", status="active", **{**r, "client_id": "c2"})  # another client is fine


def test_idempotency_and_binding_uniqueness(con):
    req = dict(command_type="start_workflow", fingerprint="f", status="accepted", accepted_at=1)
    _ins(con, "wf_requests", id="a", client_id="c1", external_request_id="x", **req)
    with pytest.raises(dbtest.IntegrityError):
        _ins(con, "wf_requests", id="b", client_id="c1", external_request_id="x", **req)
    _ins(con, "wf_requests", id="c", client_id="c2", external_request_id="x", **req)

    conv = dict(route_id="r", external_user_id="u", last_sequence=0, purged_through=0, created_at=1)
    _ins(con, "wf_conversations", id="v1", client_id="c1", external_conversation_id="chat", **conv)
    with pytest.raises(dbtest.IntegrityError):
        _ins(con, "wf_conversations", id="v2", client_id="c1", external_conversation_id="chat", **conv)

    wf = dict(conversation_id="v1", route_id="r", external_user_id="u", state="accepted", revision=1, created_at=1)
    _ins(con, "wf_workflows", id="w1", client_id="c1", external_ticket_id="T", **wf)
    with pytest.raises(dbtest.IntegrityError):
        _ins(con, "wf_workflows", id="w2", client_id="c1", external_ticket_id="T", **wf)
    _ins(con, "wf_workflows", id="w3", client_id="c1", external_ticket_id=None, **wf)
    _ins(con, "wf_workflows", id="w4", client_id="c1", external_ticket_id=None, **wf)  # unticketed may repeat


def test_event_sequence_and_one_dispatched_job_per_workflow(con):
    ev = dict(event_type="t", payload="{}", occurred_at=1, recorded_at=1)
    _ins(con, "wf_events", event_id="e1", conversation_id="v", sequence=1, **ev)
    with pytest.raises(dbtest.IntegrityError):
        _ins(con, "wf_events", event_id="e2", conversation_id="v", sequence=1, **ev)

    job = dict(kind="resident_message", payload="{}", attempts=0, created_at=1)
    _ins(con, "wf_jobs", id="j1", workflow_id="w", status="dispatched", **job)
    _ins(con, "wf_jobs", id="j2", workflow_id="w", status="queued", **job)
    _ins(con, "wf_jobs", id="j3", workflow_id="w", status="done", **job)
    with pytest.raises(dbtest.IntegrityError):
        _ins(con, "wf_jobs", id="j4", workflow_id="w", status="dispatched", **job)


def test_operation_inbox_and_approval_keys(con):
    op = dict(route_id="r", tool_name="call_worker", status="intent", created_at=1, updated_at=1)
    _ins(con, "wf_operations", id="o1", workflow_id="w", args_hash="h", client_reference="ref1", **op)
    with pytest.raises(dbtest.IntegrityError):
        _ins(con, "wf_operations", id="o2", workflow_id="w", args_hash="h", client_reference="ref2", **op)
    with pytest.raises(dbtest.IntegrityError):
        _ins(con, "wf_operations", id="o3", workflow_id="w", args_hash="h2", client_reference="ref1", **op)

    ib = dict(payload_hash="p", event_type="t", payload="{}", ingestion_status="accepted", received_at=1)
    _ins(con, "wf_provider_inbox", receipt_id="r1", integration_id="i", external_event_id="e", **ib)
    with pytest.raises(dbtest.IntegrityError):
        _ins(con, "wf_provider_inbox", receipt_id="r2", integration_id="i", external_event_id="e", **ib)

    ap = dict(workflow_id="w", conversation_id="v", client_id="c", external_user_id="u", agent_id="a",
              tool_name="t", arguments="{}", arguments_hash="h", summary="{}", status="pending",
              workflow_revision=1, created_at=1)
    _ins(con, "wf_approvals", id="a1", session_id="s", tool_call_id="tc", reply_id="r1", **ap)
    with pytest.raises(dbtest.IntegrityError):  # one approval per (session, reply, call)
        _ins(con, "wf_approvals", id="a2", session_id="s", tool_call_id="tc", reply_id="r1", **ap)
    _ins(con, "wf_approvals", id="a3", session_id="s", tool_call_id="tc", reply_id="r2", **ap)  # a model server may reuse call ids


def test_new_settings_have_defaults_and_read_the_environment():
    s = Settings()
    assert (s.wf_wait_seconds, s.wf_body_limit, s.wf_text_limit) == (25.0, 256 * 1024, 20000)
    assert s.wf_rate_per_minute > 0 and s.secret_key == ""
    assert (s.approval_ttl_seconds, s.event_retention_days, s.inbox_retention_days) == (86400, 90, 180)
    e = Settings.from_env({"AWP_WF_WAIT_SECONDS": "3", "AWP_WF_BODY_LIMIT": "1000", "AWP_WF_TEXT_LIMIT": "50",
                           "AWP_WF_RATE_PER_MINUTE": "7", "AWP_SECRET_KEY": "k", "AWP_APPROVAL_TTL_SECONDS": "60",
                           "AWP_EVENT_RETENTION_DAYS": "1", "AWP_INBOX_RETENTION_DAYS": "2"})
    assert (e.wf_wait_seconds, e.wf_body_limit, e.wf_text_limit, e.wf_rate_per_minute) == (3.0, 1000, 50, 7)
    assert (e.secret_key, e.approval_ttl_seconds, e.event_retention_days, e.inbox_retention_days) == ("k", 60, 1, 2)
    assert Settings.from_env({"AWP_WF_WAIT_SECONDS": ""}).wf_wait_seconds == 25.0
    assert Settings.from_env({}).db_url == Settings().db_url  # old settings untouched
