"""Builds the platform: AgentScope's service plus the core on top of it."""
from __future__ import annotations

import asyncio
import contextlib
import logging
import secrets
from types import SimpleNamespace
from typing import Any, Sequence

from fastapi import FastAPI
from starlette.middleware import Middleware

from agentscope.app import create_app
from agentscope.app.message_bus import InMemoryMessageBus
from agentscope.app.storage import AsyncSQLAlchemyStorage
from agentscope.app.workspace_manager import LocalWorkspaceManager

from .casefile import CaseStore
from .config import Settings
from .cost import CostService
from .db import Database
from .guard import build_judge
from .intake.agentscope_client import AgentScopeClient
from .intake.service import IntakeService
from .middleware import middleware_factory, tool_factory
from .packs import DomainPack, install_pack
from .profiles import ProfileStore
from .providers import ModelCatalog
from .router import build_router
from .runtime import Runtime
from .security import SecurityMiddleware

log = logging.getLogger("awp")


def build_app(
    settings: Settings | None = None,
    *,
    packs: Sequence[DomainPack] = (),
    catalog: ModelCatalog | None = None,
    judge: Any = None,
    storage: Any = None,
    message_bus: Any = None,
    workspace_manager: Any = None,
    deliver_every: float = 2.0,
    **create_app_kwargs: Any,
) -> FastAPI:
    settings = settings or Settings.from_env()
    database = Database(settings.db_url)
    catalog = catalog or ModelCatalog.load(settings.models_file)
    if storage is None:
        # SQLite is for development: wait for the lock instead of failing a reply.
        sqlite = settings.agentscope_db_url.startswith("sqlite")
        storage = AsyncSQLAlchemyStorage(
            settings.agentscope_db_url,
            engine_kwargs={"connect_args": {"timeout": 30}} if sqlite else None)
    bus = message_bus or InMemoryMessageBus()
    workspaces = workspace_manager or LocalWorkspaceManager(basedir=settings.workspace_dir)
    if judge is None:
        judge = build_judge(settings.jev_enabled, settings.jev_model)

    rt = Runtime(
        settings=settings, db=database, cases=CaseStore(database),
        profiles=ProfileStore(database), catalog=catalog,
        cost=CostService(database, catalog), storage=storage, bus=bus, judge=judge)

    secret = secrets.token_urlsafe(24)
    kwargs = dict(
        enable_scheduler=False, title="AI Workforce Platform",
        extra_middlewares=[Middleware(SecurityMiddleware, settings=settings,
                                      internal_secret=secret)],
        extra_agent_middlewares=middleware_factory(rt),
        extra_agent_tools=tool_factory(rt),
        custom_subagent_templates=[],
    )
    kwargs.update(create_app_kwargs)
    app = create_app(storage, bus, workspaces, **kwargs)
    rt.templates = app.state.custom_subagent_templates  # the dict AgentCreate reads
    rt.kb_manager = app.state.knowledge_base_manager

    client = AgentScopeClient(rt, app, secret)
    intake = IntakeService(rt, client)
    app.include_router(build_router(rt, intake))
    app.state.awp = SimpleNamespace(rt=rt, intake=intake, settings=settings)

    inner = app.router.lifespan_context

    @contextlib.asynccontextmanager
    async def lifespan(a: FastAPI):
        await database.create_all()
        await rt.sync_templates()
        stop = asyncio.Event()

        async def sweep() -> None:
            while not stop.is_set():
                try:
                    await intake.expire_stalled()
                    await intake.deliver_pending()
                except Exception:
                    log.exception("result delivery sweep failed")
                with contextlib.suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(stop.wait(), deliver_every)

        task = None
        try:
            async with inner(a):
                # Packs start only once AgentScope is up: a connector may submit at once.
                pairs = {(k.tenant, k.domain) for k in settings.service_keys.values()}
                for pack in packs:
                    for tenant, domain in sorted(pairs):
                        if domain == pack.domain:
                            await install_pack(rt, intake, pack, tenant)
                task = asyncio.create_task(sweep())
                yield
        finally:
            stop.set()
            if task is not None:
                await task
            for pack in packs:
                with contextlib.suppress(Exception):
                    await pack.stop()
            await intake.aclose()
            await database.dispose()

    app.router.lifespan_context = lifespan
    return app
