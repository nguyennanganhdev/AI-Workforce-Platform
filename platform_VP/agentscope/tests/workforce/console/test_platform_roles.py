"""Platform roles: one platform admin, domain admins, one approved BQL per area."""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import tempfile
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from agentscope.app._router._admin import admin_router
from agentscope.app._router._auth import auth_router
from agentscope.app.auth import AuthService

ROOT = Path(__file__).resolve().parents[3]
PASSWORD = "correct-horse-battery"


@pytest.fixture()
def stack():
    temp = tempfile.TemporaryDirectory()
    url = f"sqlite+aiosqlite:///{(Path(temp.name) / 'roles.sqlite3').as_posix()}"
    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(ROOT / "src/agentscope/app/storage/_sql/_alembic/alembic.ini"),
         "upgrade", "head"],
        check=True, cwd=ROOT, env={**os.environ, "AGENTSCOPE_SQL_URL": url}, capture_output=True,
    )

    async def seed():
        engine = create_async_engine(url)
        async with engine.begin() as connection:
            for statement in (
                "INSERT INTO business_domains VALUES ('dom-a','tenant-1','Domain A','active')",
                "INSERT INTO business_domains VALUES ('dom-b','tenant-1','Domain B','active')",
                "INSERT INTO areas VALUES ('area-1','dom-a','Khu 1','active')",
                "INSERT INTO areas VALUES ('area-2','dom-a','Khu 2','active')",
                "INSERT INTO areas VALUES ('area-9','dom-b','Khu 9','active')",
            ):
                await connection.execute(text(statement))
        await engine.dispose()

    asyncio.run(seed())
    yield url
    temp.cleanup()


async def _run(url: str) -> None:
    service = AuthService(
        database_url=url, jwt_secret="j" * 48, refresh_pepper="p" * 48, default_tenant_id="tenant-1",
        access_ttl=timedelta(minutes=5), cookie_secure=False, require_approval=True,
    )
    async with service:
        app = FastAPI()
        app.include_router(auth_router)
        app.include_router(admin_router)
        app.state.auth_service = service
        await service.create_admin(
            tenant_id="tenant-1", email="root@example.com", username="root", password=PASSWORD,
            role="PLATFORM_ADMIN",
        )
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://platform.test") as http:

            async def register(name, area, domain="dom-a"):
                return await http.post("/auth/register", json={
                    "email": f"{name}@example.com", "username": name, "password": PASSWORD,
                    "domain_id": domain, "area_id": area,
                })

            async def login(name):
                return await http.post("/auth/login", json={"tenant_id": "tenant-1", "identity": name, "password": PASSWORD})

            async def as_(name):
                answer = await login(name)
                assert answer.status_code == 200, answer.text
                return {"Authorization": "Bearer " + answer.json()["access_token"]}

            first = await register("bql-one", "area-1")
            assert first.status_code == 201 and first.json()["status"] == "pending"
            assert (await login("bql-one")).json()["detail"] == "pending_approval"
            assert (await register("bql-two", "area-1")).status_code == 409  # one BQL per area
            assert (await register("bql-three", "area-2")).status_code == 201
            assert (await register("bql-nine", "area-9", "dom-b")).status_code == 201

            root = await as_("root")
            listed = await http.get("/admin/accounts", params={"status_filter": "pending"}, headers=root)
            assert listed.status_code == 200, listed.text
            pending = listed.json()
            assert {a["username"] for a in pending} == {"bql-one", "bql-three", "bql-nine"}
            approved = await http.post(f"/admin/accounts/{first.json()['id']}/approve", headers=root)
            assert approved.status_code == 200 and approved.json()["status"] == "active"
            bql = await as_("bql-one")
            assert (await http.get("/admin/accounts", headers=bql)).status_code == 403

            made = await http.post("/admin/domain-admins", headers=root, json={
                "email": "da@example.com", "username": "domain-a", "password": PASSWORD, "domain_id": "dom-a",
            })
            assert made.status_code == 201, made.text
            domain_admin = await as_("domain-a")
            mine = (await http.get("/admin/accounts", headers=domain_admin)).json()
            assert {a["username"] for a in mine} == {"bql-one", "bql-three"}  # not dom-b
            nine = next(a for a in pending if a["username"] == "bql-nine")
            assert (await http.post(f"/admin/accounts/{nine['id']}/approve", headers=domain_admin)).status_code == 403
            three = next(a for a in pending if a["username"] == "bql-three")
            assert (await http.post(f"/admin/accounts/{three['id']}/reject", headers=domain_admin)).json()["status"] == "rejected"
            assert (await login("bql-three")).status_code == 401

            assert (await http.put("/admin/domains/dom-a/areas/area-3", headers=domain_admin, json={"name": "Khu 3"})).status_code == 200
            assert (await http.put("/admin/domains/dom-new", headers=domain_admin, json={"name": "Mới"})).status_code == 403
            assert (await http.put("/admin/domains/dom-new", headers=root, json={"name": "Mới"})).status_code == 200
            directory = (await http.get("/admin/directory", headers=root)).json()
            area1 = next(a for d in directory if d["id"] == "dom-a" for a in d["areas"] if a["id"] == "area-1")
            assert [(m["username"], m["status"]) for m in area1["managers"]] == [("bql-one", "active")]
            assert {d["id"] for d in (await http.get("/admin/directory", headers=domain_admin)).json()} == {"dom-a"}

        engine = create_async_engine(url)
        async with engine.connect() as connection:
            membership = await connection.scalar(text(
                "SELECT status FROM wf_manager_memberships WHERE manager_account_id = :id"), {"id": first.json()["id"]})
        await engine.dispose()
        assert membership == "verified"


def test_roles_registration_approval_and_scopes(stack) -> None:
    asyncio.run(_run(stack))
