import os

import httpx
import pytest
from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import async_sessionmaker

from vp import db
from vp.api import app
from vp.config import settings
from vp.db import Login, Membership, Record, Revision, User, now
from vp.schemas import AgentSpec, ModelSpec
from vp.security import Principal, hash_password, token_digest


@pytest.fixture(autouse=True)
async def isolated_database(tmp_path, monkeypatch):
    url = os.environ.get("VP_TEST_DATABASE_URL") or f"sqlite+aiosqlite:///{tmp_path}/test.db"
    if "postgresql" in url and not url.rsplit("/", 1)[-1].endswith("_test"):
        raise RuntimeError("Tests must use a separate database ending in _test")
    engine = db.make_engine(url)
    monkeypatch.setattr(db, "engine", engine)
    monkeypatch.setattr(db, "factory", async_sessionmaker(engine, expire_on_commit=False))
    monkeypatch.setattr(
        settings, "encryption_key", type(settings.encryption_key)(Fernet.generate_key().decode())
    )
    monkeypatch.setattr(settings, "cookie_secure", False)
    monkeypatch.setattr(settings, "redis_url", "")
    monkeypatch.setattr(settings, "bootstrap_email", "")
    monkeypatch.setattr(settings, "allow_private_endpoints", True)
    monkeypatch.setattr(settings, "jev_enabled", False)
    async with engine.begin() as conn:
        await conn.run_sync(db.Base.metadata.drop_all)
        await conn.run_sync(db.Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def principal():
    async with db.transaction() as session:
        user = User(
            id="admin", email="admin@test.local", password=hash_password("Test-password-123!")
        )
        session.add(user)
        session.add(Membership(workspace="default", user_id=user.id, role="admin"))
        session.add(Login(digest=token_digest("test-auth"), user_id=user.id, expires=now() + 3600))
    return Principal("admin", "default", "admin")


@pytest.fixture
async def client(principal):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        cookies={"vp_session": "test-auth"},
    ) as client:
        yield client


@pytest.fixture
async def registry(principal):
    model = ModelSpec(
        name="Fixture model",
        adapter="ollama",
        model="fixture",
        context_tokens=128000,
        rpm=10000,
        tpm=100000000,
        pricing_version="fixture-no-billing",
    ).model_dump()
    async with db.transaction() as session:
        session.add(
            Record(id="model", workspace="default", owner="admin", kind="models", body=model)
        )
        for aid in ("coordinator", "specialist", "reviewer"):
            spec = AgentSpec(
                name=aid,
                purpose="Test isolated platform behavior",
                charter="You verify all claims against sources.",
                model_id="model",
            ).model_dump()
            session.add(
                Record(
                    id=aid,
                    workspace="default",
                    owner="admin",
                    kind="agents",
                    body={"name": aid, "published_revision": aid + "-r1"},
                )
            )
            session.add(
                Revision(
                    id=aid + "-r1",
                    workspace="default",
                    agent_id=aid,
                    number=1,
                    status="published",
                    body=spec,
                )
            )
    return ["coordinator", "specialist"]


@pytest.fixture
async def leased(principal, registry):
    from vp.domain import create_session, submit_chat
    from vp.queue import claim

    async with db.transaction() as session:
        run = await create_session(session, principal, "Test session", registry, 500000)
        await submit_chat(session, principal, run.id, "Verify the source", "request-1234")
        sid = run.id
    return sid, await claim("test-worker")
