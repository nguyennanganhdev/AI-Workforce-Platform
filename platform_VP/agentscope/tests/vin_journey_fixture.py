"""Browser -> actual Platform ASGI -> actual Domain ASGI on disposable data.

The browser proxy only translates origins; it never invents API responses.
Model IO is scripted. Domain persistence/auth/business APIs are production code.
"""

import asyncio
import json
import os
from pathlib import Path
import socket
from types import SimpleNamespace
from urllib.parse import urlsplit
from urllib.parse import urlunsplit
from uuid import uuid4

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.staticfiles import StaticFiles
import uvicorn

from vin_fixtures import seed_authority, seed_policy_catalog
from agentscope.app import create_app
from agentscope.app.auth import AuthService
from agentscope.app.channel import DiscordChannel
from agentscope.app.message_bus import InMemoryMessageBus
from agentscope.app.storage import AsyncSQLAlchemyStorage
from agentscope.app.workspace_manager import LocalWorkspaceManager
from agentscope.app.vin_platform._contracts import DomainProvider
from agentscope.app.vin_platform._domain import DomainAdapter

PASSWORD = "Offline-journey-password-20261018"


@pytest.fixture
def journey(database, tmp_path, monkeypatch, request):
    from test_account_administration import door
    from test_platform_customers import register, CLIENT, SECRET

    monkeypatch.setenv("VIN_PLATFORM_ENABLED", "true")
    monkeypatch.setenv("VIN_PLATFORM_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("VINHOMES_CUSTOMER_PLATFORM_ENABLED", "true")
    monkeypatch.setenv("VINHOMES_API_PLATFORM_MCP_TOKEN", "offline-control-plane-token-0123456789")
    register(database)

    async def resident(request):
        return {"id": "local-v3-resident", "name": "Offline Resident"}
    # Only the fixture's Domain identity provider is replaced. Platform uses
    # its real password/JWT/session/capability boundary throughout the browser.
    monkeypatch.setattr("vinhomes_api.password_auth.authenticated_user", resident)
    admin_url = os.environ["RESIDENT_TEST_ADMIN_URL"]
    name = "vin_n2_platform_" + uuid4().hex
    owner_url = urlunsplit(urlsplit(admin_url)._replace(scheme="postgresql+asyncpg", path="/" + name))
    url = urlunsplit(urlsplit(os.environ["RESIDENT_TEST_RUNTIME_URL"])._replace(scheme="postgresql+asyncpg", path="/" + name))
    auth = AuthService(database_url=url, jwt_secret="offline-jwt-signing-material-" * 2,
        refresh_pepper="offline-refresh-material-" * 2, default_tenant_id="vin", cookie_secure=False,
        engine_kwargs={"poolclass": NullPool})

    async def initialize():
        import asyncpg
        from alembic import command
        from alembic.config import Config
        control = await asyncpg.connect(admin_url)
        try:
            await control.execute('CREATE DATABASE "' + name + '"')
        finally:
            await control.close()
        request.addfinalizer(lambda: asyncio.run(cleanup()))
        config = Config(str(Path(__file__).parents[1] / "src/agentscope/app/storage/_sql/_alembic/alembic.ini"))
        config.set_main_option("sqlalchemy.url", owner_url)
        await asyncio.to_thread(command.upgrade, config, "head")
        engine = create_async_engine(owner_url)
        try:
            # Production Alembic has already created the schema. Keep the
            # shared fixture's user/account rows without repeating its DDL.
            with monkeypatch.context() as schema:
                schema.setattr("vin_fixtures.create_authority_schema", lambda connection: None)
                await seed_authority(engine)
            async with engine.begin() as db:
                await db.execute(text("UPDATE auth_users SET password_hash=:password"),
                    {"password": auth._password_hasher.hash(PASSWORD)})
                role = urlsplit(url).username
                assert role.startswith("vin_n2_journey_") and len(role) == 47
                await db.execute(text(f'GRANT USAGE ON SCHEMA public TO "{role}"'))
                await db.execute(text(f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "{role}"'))
                await db.execute(text(f'GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO "{role}"'))
        finally:
            await engine.dispose()

    async def cleanup():
        import asyncpg
        assert name.startswith("vin_n2_platform_") and len(name) == 48
        db = await asyncpg.connect(admin_url)
        try:
            await db.execute('DROP DATABASE "' + name + '" WITH (FORCE)')
        finally:
            await db.close()
    asyncio.run(initialize())
    storage = AsyncSQLAlchemyStorage(url)
    manager = LocalWorkspaceManager(str(tmp_path / "workspace"))
    from agentscope.app.rag.knowledge_base_manager import CollectionPerKbManager
    from agentscope.rag import QdrantStore
    knowledge = CollectionPerKbManager(storage=storage, vector_store=QdrantStore(path=str(tmp_path / 'qdrant')))
    app = create_app(storage=storage, message_bus=InMemoryMessageBus(), workspace_manager=manager,
        knowledge_base_manager=knowledge,
        auth_service=auth, vin_platform_enabled=True, channels=[DiscordChannel],
        enable_scheduler=False, enable_channel_worker=False, enable_index_worker=False)
    state = SimpleNamespace(domain_calls=[], browser_calls=[], decisions=[], forbidden=[], model_calls=[], deliveries=[],
        storage=storage, manager=manager, app=app, database=database, client=None, domain=None)
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    request.addfinalizer(listener.close)
    state.url = "http://127.0.0.1:" + str(listener.getsockname()[1])
    from test_resident_contract import sql, TENANT
    redirect = state.url + '/connections/callback/vinhomes'
    sql(database, 'UPDATE platform_customer_clients SET redirect_uri=$1 WHERE tenant_id=$2 AND client_id=$3', redirect, TENANT, CLIENT)
    with door(database) as domain:
        state.domain = domain

        async def exchange(request):
            state.domain_calls.append((request.method, request.url.path))
            if request.url.path.endswith("/decisions"):
                state.decisions.append(json.loads(request.content))
            response = await asyncio.to_thread(domain.request, request.method, str(request.url),
                headers=dict(request.headers), content=request.content, follow_redirects=False)
            return httpx.Response(response.status_code, headers=dict(response.headers), content=response.content)

        with TestClient(app) as client:
            state.client = client
            authority = app.state.vin_platform_service
            state.authority = authority
            http = httpx.AsyncClient(transport=httpx.MockTransport(exchange))
            authority.http_client = http

            async def configure():
                if 'admin_policy' not in request.node.name:
                    await seed_policy_catalog(authority)
                admin = await authority.context("admin")
                secret = await authority.secret_put(admin, SECRET, "domain-client")
                await DomainAdapter(authority).configure(admin, DomainProvider(id="vinhomes", issuer="https://domain.invalid",
                    client_id=CLIENT, authorization_url="https://domain.invalid/platform/link/authorize",
                    token_url="https://domain.invalid/platform/link/token", api_base_url="https://domain.invalid/platform/customer",
                    redirect_uri=redirect, client_secret_ref=secret, active=True))
            client.portal.call(configure)
            class SpaFiles(StaticFiles):
                async def get_response(self, path, scope):
                    try:
                        return await super().get_response(path, scope)
                    except StarletteHTTPException as exc:
                        if exc.status_code != 404 or Path(path).suffix:
                            raise
                        return await super().get_response("index.html", scope)

            files = SpaFiles(directory=os.environ["VIN_UI_DIST"], html=True)

            async def site(scope, receive, send):
                if scope["type"] in {"http", "websocket"} and scope["path"].startswith("/api/"):
                    # Same prefix stripping as the deployed reverse proxy;
                    # authorization middleware sees its real backend routes.
                    inner = {**scope, "path": scope["path"][4:], "raw_path": scope["raw_path"][4:]}
                    async def proxy_send(message):
                        if message["type"] == "http.response.start":
                            message = {**message, "headers": [(key, value.replace(b"Path=/auth", b"Path=/api/auth")
                                if key.lower() == b"set-cookie" else value) for key, value in message["headers"]]}
                        await send(message)
                    return await app(inner, receive, proxy_send)
                return await files(scope, receive, send)

            server = uvicorn.Server(uvicorn.Config(site, lifespan="off", log_level="error"))
            server_task = client.portal.start_task_soon(server.serve, [listener])

            async def ready():
                for _ in range(100):
                    if server.started:
                        return
                    await asyncio.sleep(0.02)
                raise RuntimeError("Local browser fixture did not start")
            client.portal.call(ready)
            try:
                yield state
            finally:
                server.should_exit = True
                server_task.result(timeout=10)
                listener.close()
                client.portal.call(http.aclose)


def browser_bridge(page, journey):
    """Permit the real loopback site and route only synthetic Domain origins."""
    base_url = journey.url
    origin = urlsplit(base_url)

    def forward(route):
        request = route.request
        parsed = urlsplit(request.url)
        if (parsed.scheme, parsed.netloc) == (origin.scheme, origin.netloc):
            if parsed.path.startswith("/api/"):
                journey.browser_calls.append((request.method, parsed.path.removeprefix("/api")))
                assert "x-user-id" not in request.headers
            route.continue_()
            return
        elif parsed.netloc == "domain.invalid" and parsed.path.startswith("/platform/link/"):
            response = journey.domain.request(request.method, request.url,
                headers={"content-type": request.headers.get("content-type", "")}, content=request.post_data_buffer,
                follow_redirects=False)
        elif parsed.netloc == "platform.invalid" and parsed.path == "/connections/callback/vinhomes":
            route.fulfill(status=302, headers={"location": base_url + parsed.path + "?" + parsed.query})
            return
        elif parsed.netloc == 'www.google.com' and parsed.path == '/s2/favicons':
            # A decorative channel icon is a labelled static asset fixture,
            # never a business/API response or a real internet request.
            route.fulfill(status=200, content_type='image/svg+xml', body='<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24"/>')
            return
        else:
            journey.forbidden.append(request.url)
            route.abort()
            return
        headers = {key: value for key, value in response.headers.items()
            if key.lower() not in {"content-length", "content-encoding", "transfer-encoding", "set-cookie"}}
        route.fulfill(status=response.status_code, headers=headers, body=response.content)

    page.context.route("**/*", forward)


def login(journey, user="alice"):
    response = journey.client.post("/auth/login", json={"tenant_id": "vin", "identity": user, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def evidence(journey, name, page):
    folder = Path(".artifacts/vin-journey")
    folder.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(folder / (name + ".png")), full_page=True)
    assert not journey.forbidden
    # Bearer secrets are never serialized to the evidence file.
    (folder / (name + ".json")).write_text(json.dumps({"browser_requests": journey.browser_calls,
        "domain_requests": journey.domain_calls, "model_mode": "scripted", "paid_model_calls": 0,
        "external_network_attempts": len(journey.forbidden)}, indent=2), encoding="utf-8")


def staff_complete(journey, case_id, ticket_id):
    """Yield for the two real Platform UI consents; never inject workflow SQL."""
    from datetime import datetime, timedelta, timezone
    from test_resident_contract import CATEGORY, client, image

    def ok(response, status=200):
        assert response.status_code == status, response.text
        return response.json()

    with client(journey.database, "management") as staff:
        ticket = ok(staff.get("/tickets/" + ticket_id))["ticket"]
        work = ok(staff.post('/tickets/' + ticket_id + '/work-orders', json={'category_id': CATEGORY,
            'required_specialty_id': CATEGORY, 'description': 'Offline repair leak', 'ticket_version': ticket['version']}), 201)
        worker = next(item for item in ok(staff.get("/catalogs"))["staff"] if item["user_id"] == "local-v3-technical")
        assignment = ok(staff.post("/work-orders/" + work["id"] + "/assignments", json={"staff_id": worker["id"],
            "offer_expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(), "work_order_version": work["version"]}), 201)
        with client(journey.database, "technical") as executor:
            ok(executor.post("/assignments/" + assignment["id"] + "/response", json={"status": "accepted",
                "eta_at": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()}))
        work = ok(staff.get("/work-orders/" + work["id"]))["workOrder"]
        for target in ("en_route", "arrived"):
            with client(journey.database, "technical") as executor:
                work = ok(executor.patch("/work-orders/" + work["id"] + "/status",
                    json={"version": work["version"], "status": target, "note": "Offline workflow step"}))
        with client(journey.database, 'technical') as executor:
            ok(executor.post('/work-orders/' + work['id'] + '/repair-proposal', json={'version': work['version'],
                'note': 'Offline replace faucet seal', 'labor_cost': 0, 'warranty_months': 1,
                'lines': [{'name': 'Fixture seal', 'quantity': '1', 'unit': 'piece', 'unit_price': 0}]}), 201)
        yield 'repair', None
        work = ok(staff.get('/work-orders/' + work['id']))['workOrder']
        with client(journey.database, 'technical') as executor:
            work = ok(executor.patch('/work-orders/' + work['id'] + '/status', json={'version': work['version'], 'status': 'in_progress', 'note': 'Approved repair begins'}))
        for purpose in ("before", "after"):
            photo = ok(staff.post("/tickets/" + ticket_id + "/files", content=image(),
                headers={"Content-Type": "application/octet-stream"},
                params={"filename": purpose + ".png", "mimeType": "image/png", "purpose": purpose}), 201)
            version = ok(staff.get("/tickets/" + ticket_id))["ticket"]["version"]
            ok(staff.post("/tickets/" + ticket_id + "/evidence", json={"file_id": photo["fileId"], "work_order_id": work["id"],
                "assignment_id": assignment["id"], "purpose": purpose, "version": version}), 201)
        with client(journey.database, "technical") as executor:
            ok(executor.patch("/work-orders/" + work["id"] + "/status", json={"version": work["version"], "status": "completed", "note": "Repair complete"}))
        ok(staff.post("/work-orders/" + work["id"] + "/qc", json={"outcome": "pass", "criteria": [{"name": "No leak", "passed": True}]}), 201)
        yield 'completion', photo['fileId']
