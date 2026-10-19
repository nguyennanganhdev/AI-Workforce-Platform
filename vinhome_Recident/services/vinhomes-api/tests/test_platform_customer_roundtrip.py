"""Platform SQL authority -> Domain HTTP -> canonical progress, without a model.

Opt in by adding Platform src to PYTHONPATH; ordinary Domain CI needs no SDK.
"""

import asyncio
import re
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
from uuid import UUID, uuid4

import pytest

from test_account_administration import door
from test_platform_customers import CLIENT, SECRET, REDIRECT, register
from test_resident_contract import CATEGORY, sql
from test_resident_contract import database as database  # noqa: F401


def test_platform_authority_domain_link_case_progress_intent_and_revoke(database, monkeypatch, tmp_path):
    pytest.importorskip("agentscope.app.vin_platform")
    fixtures = pytest.importorskip("vin_fixtures", reason="Add Platform tests to PYTHONPATH for the shared authority fixture")
    import httpx
    from cryptography.fernet import Fernet
    from sqlalchemy.ext.asyncio import create_async_engine
    from agentscope.app.vin_platform import VinPlatformService, PlatformError
    from agentscope.app.vin_platform._contracts import DomainProvider, ServiceRequest, SourceIntent
    from agentscope.app.vin_platform._domain import DomainAdapter

    monkeypatch.setenv("VINHOMES_CUSTOMER_PLATFORM_ENABLED", "true")
    monkeypatch.setenv("VINHOMES_API_PLATFORM_MCP_TOKEN", "offline-control-plane-token-0123456789")
    register(database)
    async def resident(request):
        return {"id": "local-v3-resident", "name": "Fixture Resident"}
    monkeypatch.setattr("vinhomes_api.password_auth.authenticated_user", resident)

    with door(database) as domain:
        async def exercise():
            engine = create_async_engine("sqlite+aiosqlite:///" + str(tmp_path / "platform.db"))
            async def exchange(request):
                response = await asyncio.to_thread(domain.request, request.method, str(request.url),
                    headers=dict(request.headers), content=request.content, follow_redirects=False)
                return httpx.Response(response.status_code, headers=dict(response.headers), content=response.content)
            async with httpx.AsyncClient(transport=httpx.MockTransport(exchange)) as http:
                authority = VinPlatformService(SimpleNamespace(_require_engine=lambda: engine), SimpleNamespace(),
                    encryption_key=Fernet.generate_key(), http_client=http)
                adapter = DomainAdapter(authority)
                try:
                    await fixtures.seed_authority(engine)
                    admin, alice, bob = [await authority.context(user) for user in ("admin", "alice", "bob")]
                    secret = await authority.secret_put(admin, SECRET, "domain-client")
                    await adapter.configure(admin, DomainProvider(id="vinhomes", issuer="https://domain.invalid", client_id=CLIENT,
                        authorization_url="https://domain.invalid/platform/link/authorize", token_url="https://domain.invalid/platform/link/token",
                        api_base_url="https://domain.invalid/platform/customer", redirect_uri=REDIRECT, client_secret_ref=secret, active=True))
                    started = await adapter.start(alice, "vinhomes")
                    page = domain.get(started["authorization_url"])
                    assert page.status_code == 200, page.text
                    transaction = re.search(r'name="transaction" value="([^"]+)"', page.text)[1]
                    csrf = re.search(r'name="csrf" value="([^"]+)"', page.text)[1]
                    consent = domain.post("https://domain.invalid/platform/link/authorize", data={"transaction": transaction, "csrf": csrf, "decision": "allow"}, follow_redirects=False)
                    assert consent.status_code == 303, consent.text
                    query = parse_qs(urlsplit(consent.headers["location"]).query)
                    linked = await adapter.complete(alice, "vinhomes", started["transaction_id"], query["state"][0], query["code"][0])
                    profile = await adapter.request(alice, linked["id"], "GET", "/me")
                    command = ServiceRequest(link_id=linked["id"], idempotency_key=uuid4().hex, request={
                        "apartmentId": profile["apartments"][0]["id"], "description": "Vòi nước dưới bồn rửa rò liên tục.",
                        "location": {"description": "Bếp dưới bồn rửa"}, "photoIds": []})
                    case = await adapter.create_case(alice, command)
                    assert await adapter.create_case(alice, command) == case
                    with pytest.raises(PlatformError, match="CASE_NOT_FOUND"):
                        await adapter.get_case(bob, case["id"])
                    ticket = await adapter.materialize(alice, case["id"], category_id=CATEGORY,
                        expected_version=case["domain"]["version"], idempotency_key=uuid4().hex)
                    canonical = await adapter.get_case(alice, case["id"], refresh=True)
                    feed = await adapter.sync_events(alice, case["id"])
                    assert not feed["has_more"]
                    replay = await adapter.sync_events(alice, case["id"])
                    assert replay["sync_status"] == "applied"
                    intent = SourceIntent(case_id=case["id"], action="cancel", expected_version=canonical["data"]["domain"]["version"],
                        payload={"reason": "Khách yêu cầu hủy công việc"}, idempotency_key=uuid4().hex)
                    receipt = await adapter.decide(alice, intent)
                    assert await adapter.decide(alice, intent) == receipt
                    commands = await asyncio.to_thread(sql, database, "SELECT count(*) AS n FROM platform_commands WHERE ticket_id=$1", UUID(ticket["ticket_id"]))
                    assert commands[0]["n"] == 0
                    await adapter.revoke(alice, linked["id"])
                    with pytest.raises(PlatformError, match="DOMAIN_LINK_REQUIRED"):
                        await adapter.request(alice, linked["id"], "GET", "/me")
                finally:
                    await engine.dispose()
        asyncio.run(exercise())
