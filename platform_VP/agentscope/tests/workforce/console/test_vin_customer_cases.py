"""Real C05/C06/C07 adapters with shared authority and an in-process Domain fixture."""

import hashlib
import hmac
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import insert, select, update

from vin_fixtures import authority as authority  # noqa: F401
from agentscope.app._service import _customer_cases as cases
from agentscope.app._tool._customer_service import CustomerService
from agentscope.app.vin_platform import PlatformError
from agentscope.app.vin_platform import _tables as t
from agentscope.app.vin_platform._contracts import DomainProvider, SourceIntent
from agentscope.app.vin_platform._domain import DomainAdapter


@pytest_asyncio.fixture
async def customer(authority, monkeypatch):
    monkeypatch.setenv("VIN_PLATFORM_ENABLED", "true")
    storage = authority.storage
    storage.vin_platform_service = authority
    storage.get_agent = AsyncMock(side_effect=lambda user, ident: SimpleNamespace(user_id="alice", data=SimpleNamespace(system_role="leader")) if user == "alice" and ident == "leader" else None)
    storage.get_session = AsyncMock(side_effect=lambda user, agent, session: SimpleNamespace(id=session) if user == "alice" and agent == "leader" and session in {"session", "another"} else None)
    admin = await authority.context("admin")
    secret = await authority.secret_put(admin, "offline-client-secret", "domain-client")
    link_secret = await authority.secret_put(admin, "offline-link-token", "domain-link")
    await DomainAdapter(authority).configure(admin, DomainProvider(id="vinhomes", issuer="https://domain.fixture.invalid",
        client_id="fixture-client", authorization_url="https://domain.fixture.invalid/authorize", token_url="https://domain.fixture.invalid/token",
        api_base_url="https://domain.fixture.invalid/customer", redirect_uri="https://platform.fixture.invalid/connections/callback",
        client_secret_ref=secret, active=True))
    link_id, apartment_id, category_id, domain_id, resolution_id = [str(uuid4()) for _ in range(5)]
    async with authority.engine.begin() as db:
        await db.execute(insert(t.links).values(id=link_id, tenant_id="vin", user_id="alice", provider_id="vinhomes",
            issuer="https://domain.fixture.invalid", subject="resident-alice", status="active", secret_ref=link_secret,
            scopes=["self", "requests"], revision=1, data={"domain_link_id": str(uuid4())}))
    state = {"calls": [], "created": 0, "version": 1, "case_id": None, "materialized": {}, "decisions": [], "gap": False}

    def domain(request):
        path = request.url.path.removeprefix("/customer")
        body = json.loads(request.content) if request.content else None
        state["calls"].append((request.method, path, body))
        result = {}
        snapshot = {"id": domain_id, "code": "FIXTURE-01", "title": "Vòi nước rò rỉ", "description": "fixture request",
            "canonical_version": state["version"], "service_status": "waiting_for_customer", "status": "resolved",
            "as_of": "2026-10-18T10:00:00Z", "next_action": "review_current_decision", "projection_hash": "fixture-hash",
            "permissions": {"canConfirm": True, "canRequestRework": True}, "resolutionRevision": resolution_id,
            "resolution": {"summary": "Đã thay vòi", "photos": []}, "pending_decisions": [], "work_orders": []}
        if path == "/grants":
            result = {"access_token": "offline-private-access-token"}
        elif path == "/me":
            result = {"apartments": [{"id": apartment_id, "label": "Fixture A"}], "service_categories": [{"id": category_id, "name": "Nước"}]}
        elif path == "/requests" and request.method == "POST":
            state["created"] += 1
            state["case_id"] = body["platform_case_id"]
            assert body["platform_workflow_id"] == state["case_id"]
            result = snapshot
        elif path.endswith("/events"):
            cursor = int(request.url.params.get("after", 0))
            result = {"items": [{"schema_version": "vin-case-1", "event_id": "fixture-event-1", "case_id": state["case_id"],
                "sequence": 2 if state["gap"] else 1, "canonical_version": state["version"], "event_type": "resident.case.progress",
                "occurred_at": "2026-10-18T10:00:00Z", "audience": "customer", "data": {"label": "Nhân viên đã cập nhật", "note": "Đã thay vòi"}}] if cursor == 0 else [],
                "last_sequence": 1, "has_more": False, "canonical_version": state["version"]}
        elif path.endswith("/tickets"):
            key = request.headers["Idempotency-Key"]
            previous = state["materialized"].setdefault(key, body)
            assert previous == body
            result = {"ticket_id": str(uuid4()), "origin": "platform"}
        elif path.endswith("/projection-acks"):
            assert body["canonical_version"] == state["version"]
            result = {"ingestion_status": "applied"}
        elif path.endswith("/decisions"):
            proof = body["intent_proof"]
            signature = hmac.new(hashlib.sha256(b"offline-client-secret").digest(), json.dumps(proof, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(), hashlib.sha256).hexdigest()
            assert hmac.compare_digest(signature, body["intent_signature"])
            if body["expected_version"] != state["version"]:
                return httpx.Response(409, json={"detail": "stale projection"})
            state["decisions"].append(body)
            result = {"status": "closed"}
            state["version"] += 1
        elif path == "/requests/" + domain_id:
            result = snapshot
        else:
            raise AssertionError((request.method, path))
        return httpx.Response(200, json=result)

    async with httpx.AsyncClient(transport=httpx.MockTransport(domain)) as client:
        authority.http_client = client
        yield SimpleNamespace(storage=storage, authority=authority, state=state,
            args=(storage, "alice", "leader", "session"), command=dict(link_id=link_id, apartment_id=apartment_id,
                description="Vòi nước ở bếp rò rỉ", location="Bếp dưới bồn rửa", category_id=category_id))


@pytest.mark.asyncio
async def test_leader_create_replay_timeline_and_private_session_binding(customer):
    profile = await cases.linked_context(*customer.args)
    assert profile["items"][0]["apartments"][0]["id"] == customer.command["apartment_id"]
    first = await cases.create_request(*customer.args, **customer.command)
    customer.state["version"] = 2  # Staff/manual update between delivery retries.
    second = await cases.create_request(*customer.args, **customer.command)
    assert second["id"] == first["id"] and customer.state["created"] == 1
    assert len(customer.state["materialized"]) == 1
    assert first["sync_status"] == "applied" and first["as_of"] and first["next_action"] == "review_current_decision"
    assert second["events"][0]["label"] == "Nhân viên đã cập nhật"
    assert len((await cases.session_cases(*customer.args))["items"][0]["events"]) == 1
    assert (await cases.session_cases(customer.storage, "alice", "leader", "another"))["items"] == []
    with pytest.raises(PlatformError, match="CUSTOMER_LEADER_NOT_FOUND"):
        await cases.session_cases(customer.storage, "bob", "leader", "session")
    async with customer.authority.engine.connect() as db:
        assert len((await db.execute(select(t.cases))).all()) == 1
    public = json.dumps(second)
    assert all(secret not in public for secret in ("offline-private", "offline-link", "offline-client", "ticket_grant", "intent_proof"))
    assert not any("ticket-grants" in path or "partner" in path or "workflows" in path for _, path, _ in customer.state["calls"])


@pytest.mark.asyncio
async def test_no_model_consent_and_ui_intent_is_versioned_signed_and_idempotent(customer):
    tool = CustomerService(customer.storage, None, None, "alice", "session", "leader")
    await tool(operation="create", **customer.command)
    assert customer.state["decisions"] == []
    assert set(tool.input_schema["properties"]["operation"]["enum"]) == {"context", "create", "progress"}
    card = (await cases.session_cases(*customer.args))["items"][0]
    action = next(a for a in card["actions"] if a["action"] == "confirm")
    command = SourceIntent(case_id=card["id"], action=action["action"], expected_version=action["expected_version"],
        payload=action["payload"], idempotency_key=str(uuid4()))
    context = await customer.authority.context("alice")
    assert await DomainAdapter(customer.authority).decide(context, command) == {"status": "closed"}
    assert await DomainAdapter(customer.authority).decide(context, command) == {"status": "closed"}
    assert len(customer.state["decisions"]) == 1
    with pytest.raises(PlatformError, match="DOMAIN_REQUEST_REJECTED"):
        await DomainAdapter(customer.authority).decide(context, command.model_copy(update={"idempotency_key": str(uuid4())}))


@pytest.mark.asyncio
async def test_revocation_and_event_gap_disable_confirmation(customer):
    card = await cases.create_request(*customer.args, **customer.command)
    async with customer.authority.engine.begin() as db:
        await db.execute(update(t.links).values(status="revoked"))
    unavailable = (await cases.session_cases(*customer.args))["items"][0]
    assert unavailable["sync_status"] == "unavailable" and unavailable["actions"] == []
    with pytest.raises(PlatformError, match="DOMAIN_LINK_REQUIRED"):
        await cases.create_request(*customer.args, **customer.command)
    assert customer.state["created"] == 1
    assert card["actions"]


@pytest.mark.asyncio
async def test_gap_never_shows_current_or_offers_decision(customer):
    customer.state["gap"] = True
    with pytest.raises(PlatformError, match="SYNC_PENDING"):
        await cases.create_request(*customer.args, **customer.command)
    card = (await cases.session_cases(*customer.args))["items"][0]
    assert card["error"] == "SYNC_PENDING" and card["actions"] == []


@pytest.mark.asyncio
async def test_lost_response_retries_same_case_before_binding(customer, monkeypatch):
    original = DomainAdapter.create_case
    async def lost(adapter, *args, **kwargs):
        await original(adapter, *args, **kwargs)
        raise PlatformError("DOMAIN_OUTCOME_UNKNOWN", 503)
    monkeypatch.setattr(DomainAdapter, "create_case", lost)
    with pytest.raises(PlatformError, match="DOMAIN_OUTCOME_UNKNOWN"):
        await cases.create_request(*customer.args, **customer.command)
    assert (await cases.session_cases(*customer.args))["items"][0]["sync_status"] == "outcome_unknown"
    monkeypatch.setattr(DomainAdapter, "create_case", original)
    assert (await cases.create_request(*customer.args, **customer.command))["sync_status"] == "applied"
    assert customer.state["created"] == 1


@pytest.mark.asyncio
async def test_invalid_tool_operation_and_non_customer_cannot_sign_or_dispatch(customer, monkeypatch):
    tool = CustomerService(customer.storage, None, None, "alice", "session", "leader")
    chunk = await tool(operation="confirm", payload={"approved": True})
    assert chunk.content[0].text == "INVALID_REQUEST_DETAILS"
    assert customer.state["decisions"] == []
    with pytest.raises(PlatformError, match="PERSONAL_WORKSPACE_REQUIRED"):
        await cases.session_cases(customer.storage, "admin", "leader", "session")
    monkeypatch.setenv("VIN_PLATFORM_ENABLED", "false")
    with pytest.raises(PlatformError, match="VIN_PLATFORM_DISABLED"):
        await cases.session_cases(*customer.args)
    assert customer.state["created"] == 0


def test_missing_approval_revision_never_uses_case_or_ticket_revision():
    domain = {"canonical_version": 8, "pending_decisions": [{"id": "approval-a", "status": "pending", "ticket_version": 99}]}
    assert cases.decision_actions(domain) == []
