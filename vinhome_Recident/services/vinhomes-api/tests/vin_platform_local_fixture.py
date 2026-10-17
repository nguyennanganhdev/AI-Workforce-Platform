"""Disposable Docker E2E fixture only. Never import into an application deployment."""

import asyncio
import hashlib
import json
import os
import sys
import time
import socket
from uuid import UUID, uuid4

TENANT = "11111111-1111-5111-a111-111111111111"
PASSWORD = "Offline-e2e-password-2026!"
SECRET = "offline-e2e-domain-client-secret-only"


def loopback_only():
    original = socket.socket.connect
    lookup = socket.getaddrinfo
    def check(address):
        if isinstance(address, tuple) and address[0] not in {"localhost", "127.0.0.1", "::1"}:
            raise RuntimeError("Disposable E2E blocks non-loopback network")
    def connect(sock, address):
        check(address)
        return original(sock, address)
    def getaddrinfo(host, port, *args, **kwargs):
        check((host, port))
        return lookup(host, port, *args, **kwargs)
    socket.socket.connect = connect
    socket.getaddrinfo = getaddrinfo


async def seed_domain():
    import asyncpg
    from vinhomes_api import database
    from vinhomes_api.password_auth import password_hash
    owner = os.environ["FIXTURE_DOMAIN_OWNER_URL"]
    await database.migrate(owner)
    await database.seed(owner)
    await database.role(owner, "vin_runtime", "offline-runtime-only")
    db = await asyncpg.connect(owner)
    try:
        for actor in ("resident", "admin", "technical"):
            user = "local-v3-" + actor
            await db.execute("""INSERT INTO accounts (id,account_id,provider_id,user_id,password)
                VALUES($1,$2,'vinhomes-password-v1',$2,$3) ON CONFLICT DO NOTHING""", str(uuid4()), user, password_hash(PASSWORD))
        await db.execute("UPDATE users SET phone_e164='+84901234567' WHERE id='local-v3-resident'")
        await db.execute("""INSERT INTO platform_customer_clients(tenant_id,client_id,secret_hash,redirect_uri,issuer,active)
            VALUES($1,'local-e2e',$2,$3,'http://127.0.0.1:18101',true)""", UUID(TENANT), hashlib.sha256(SECRET.encode()).hexdigest(),
            "http://127.0.0.1:18104/connections/callback/vinhomes")
        users = await db.fetch("SELECT id,email FROM users WHERE id=ANY($1::text[])", ["local-v3-" + a for a in ("resident", "admin", "technical")])
        return {row["id"]: row["email"] for row in users}
    finally:
        await db.close()


async def seed_platform():
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import text
    cfg = Config("/workspace/platform_VP/agentscope/src/agentscope/app/storage/_sql/_alembic/alembic.ini")
    cfg.set_main_option("sqlalchemy.url", os.environ["AGENTSCOPE_SQL_URL"])
    await asyncio.to_thread(command.upgrade, cfg, "head")
    async with platform_auth() as auth:
        admin = await auth.register_personal(email="admin@fixture.invalid", username="fixtureadmin", password=PASSWORD)
        async with auth._require_engine().begin() as db:
            await db.execute(text("UPDATE auth_users SET role='PLATFORM_ADMIN' WHERE id=:id"), {"id": admin.id})
    return {"admin": admin.id}


def platform_auth():
    from agentscope.app.auth import AuthService
    return AuthService(database_url=os.environ["AGENTSCOPE_SQL_URL"], jwt_secret="offline-e2e-jwt-material-" * 3,
        refresh_pepper="offline-e2e-refresh-material-" * 3, default_tenant_id="default", cookie_secure=False)


def platform_app():
    from agentscope.app import create_app
    from agentscope.app.storage import RedisStorage, AsyncSQLAlchemyStorage
    from agentscope.app.message_bus import RedisMessageBus
    from agentscope.app.workspace_manager import LocalWorkspaceManager
    return create_app(storage=RedisStorage(host="127.0.0.1", port=18106),
        shared_context_storage=AsyncSQLAlchemyStorage(os.environ["AGENTSCOPE_SQL_URL"], create_tables=False),
        message_bus=RedisMessageBus(host="127.0.0.1", port=18106),
        workspace_manager=LocalWorkspaceManager(basedir="/tmp/vin-e2e-workspaces", default_mcps=[]),
        auth_service=platform_auth(), enable_index_worker=False, enable_channel_worker=False, enable_scheduler=False)


def model_app():
    from fastapi import FastAPI, Request
    from fastapi.responses import StreamingResponse
    app = FastAPI()
    calls = []

    @app.get("/evidence")
    async def evidence():
        return {"calls": calls, "paid_model_calls": 0, "provider": "local-scripted"}

    @app.get("/v1/models")
    async def models():
        return {"object": "list", "data": [{"id": "scripted-vin", "object": "model", "owned_by": "fixture"}]}

    @app.post("/v1/chat/completions")
    async def complete(request: Request):
        payload = await request.json()
        tools = {tool["function"]["name"] for tool in payload.get("tools", [])}
        operation, arguments = None, None
        if "CustomerService" in tools:
            results = []
            for message in payload.get("messages", []):
                if message.get("role") == "tool":
                    try:
                        results.append(json.loads(message["content"]))
                    except (TypeError, ValueError):
                        pass
            profiles = [item for result in results if isinstance(result, dict) for item in result.get("items", [])
                        if isinstance(item, dict) and item.get("apartments")]
            created = any(isinstance(result, dict) and result.get("id") and "service_status" in result for result in results)
            if not results:
                operation, arguments = "context", {"operation": "context"}
            elif profiles and not created:
                profile = profiles[-1]
                category = next(item["id"] for item in profile["service_categories"] if item["code"] == "technical")
                operation, arguments = "create", {"operation": "create", "link_id": profile["link_id"],
                    "apartment_id": profile["apartments"][0]["id"], "category_id": category,
                    "description": "Vòi nước bếp rò rỉ, tôi yêu cầu nhân viên kỹ thuật kiểm tra.", "location": "Dưới bồn rửa bếp"}
        calls.append({"model": payload["model"], "operation": operation, "tools": sorted(tools),
            "tool_results": [message.get("content") for message in payload.get("messages", []) if message.get("role") == "tool"]})
        if len(calls) > 20:
            from fastapi import HTTPException
            raise HTTPException(429, "Scripted fixture call bound exceeded")
        ident = "chatcmpl-" + uuid4().hex
        delta = {"role": "assistant", "content": "Yêu cầu đã được ghi nhận. Theo dõi trạng thái xác minh trong thẻ yêu cầu."}
        finish = "stop"
        if arguments:
            delta = {"role": "assistant", "tool_calls": [{"index": 0, "id": "call_" + uuid4().hex, "type": "function",
                "function": {"name": "CustomerService", "arguments": json.dumps(arguments, ensure_ascii=False)}}]}
            finish = "tool_calls"
        common = {"id": ident, "object": "chat.completion.chunk", "created": int(time.time()), "model": "scripted-vin"}
        usage = {"prompt_tokens": 100, "completion_tokens": 40, "total_tokens": 140}
        if payload.get("stream"):
            chunks = [{**common, "choices": [{"index": 0, "delta": delta, "finish_reason": None}]},
                      {**common, "choices": [{"index": 0, "delta": {}, "finish_reason": finish}], "usage": usage}]
            return StreamingResponse(iter([*("data: " + json.dumps(chunk, ensure_ascii=False) + "\n\n" for chunk in chunks), "data: [DONE]\n\n"]),
                media_type="text/event-stream", headers={"x-request-id": ident})
        return {**common, "object": "chat.completion", "choices": [{"index": 0, "message": delta, "finish_reason": finish}], "usage": usage}
    return app


if __name__ == "__main__":
    loopback_only()
    mode = sys.argv[1]
    if mode.startswith("seed-"):
        result = asyncio.run(seed_domain() if mode == "seed-domain" else seed_platform())
        print(json.dumps(result))
    else:
        import uvicorn
        if mode == "domain":
            from vinhomes_api.main import create_app
            app, port = create_app(), 18101
        elif mode == "platform":
            app, port = platform_app(), 18102
        else:
            app, port = model_app(), 18103
        uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
