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
from .workforce.service import Workforce, Fault
from .workforce.router import build_router as workforce_router
from .workforce.boundary import WorkforceBoundary

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
    if message_bus is None and settings.redis_url:
        from agentscope.app.message_bus import RedisMessageBus
        from redis.asyncio import ConnectionPool
        bus = RedisMessageBus(connection_pool=ConnectionPool.from_url(settings.redis_url, decode_responses=True))
    else:
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
        extra_middlewares=[Middleware(WorkforceBoundary), Middleware(SecurityMiddleware, settings=settings,
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
    workforce = Workforce(rt, intake)
    rt.workforce = workforce
    app.state.awp.workforce = workforce
    app.include_router(workforce_router(workforce))
    from .workforce.console import build_console
    app.include_router(build_console(workforce))

    from fastapi.responses import JSONResponse
    from fastapi.exceptions import RequestValidationError
    from fastapi.exception_handlers import request_validation_exception_handler

    @app.exception_handler(Fault)
    async def workforce_fault(request, exc):
        details = {}
        if exc.code == "EVENT_CURSOR_EXPIRED":
            details["snapshot_url"] = request.url.path.rsplit("/", 1)[0]
        headers = {"Retry-After": "5"} if exc.status == 429 else None
        return JSONResponse({"error": {"code": exc.code, "message": exc.message, "details": details,
            "request_id": None, "retryable": exc.status in (429, 503)}}, status_code=exc.status, headers=headers)

    @app.exception_handler(RequestValidationError)
    async def workforce_validation(request, exc):
        if not request.url.path.startswith("/workforce/v1/"):
            return await request_validation_exception_handler(request, exc)
        return await workforce_fault(request, Fault(422, "INVALID_REQUEST", "Request schema validation failed"))

    inner = app.router.lifespan_context

    @contextlib.asynccontextmanager
    async def lifespan(a: FastAPI):
        await database.create_all()
        await rt.sync_templates()
        stop = asyncio.Event()
        from .workforce.worker import loop as worker_loop
        worker_tasks = []

        async def sweep() -> None:
            next_retention = 0
            while not stop.is_set():
                try:
                    await intake.expire_stalled()
                    await intake.deliver_pending()
                    if asyncio.get_running_loop().time() >= next_retention:
                        from .workforce.retention import prune
                        await prune(workforce)
                        next_retention = asyncio.get_running_loop().time() + 300
                except Exception:
                    log.exception("result delivery sweep failed")
                with contextlib.suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(stop.wait(), deliver_every)

        task = None
        try:
            async with contextlib.AsyncExitStack() as sdk_stack:
                # AgentScope creates its own tables. Serialize that first-start DDL
                # across API/worker processes without changing the vendor package.
                if settings.agentscope_db_url.startswith("postgresql"):
                    from sqlalchemy import text
                    from sqlalchemy.ext.asyncio import create_async_engine
                    bootstrap = create_async_engine(settings.agentscope_db_url)
                    try:
                        async with bootstrap.begin() as conn:
                            await conn.execute(text("SELECT pg_advisory_xact_lock(724103820)"))
                            await sdk_stack.enter_async_context(inner(a))
                    finally:
                        await bootstrap.dispose()
                else:
                    await sdk_stack.enter_async_context(inner(a))
                # Packs start only once AgentScope is up: a connector may submit at once.
                pairs = {(k.tenant, k.domain) for k in settings.service_keys.values()}
                for pack in packs:
                    for tenant, domain in sorted(pairs):
                        if domain == pack.domain:
                            await install_pack(rt, intake, pack, tenant)
                task = asyncio.create_task(sweep())
                worker_tasks = [asyncio.create_task(worker_loop(workforce, stop))
                                for _ in range(settings.workforce_workers)]
                yield
        finally:
            stop.set()
            for worker_task in worker_tasks:
                worker_task.cancel()
            await asyncio.gather(*worker_tasks, return_exceptions=True)
            if task is not None:
                await task
            for pack in packs:
                with contextlib.suppress(Exception):
                    await pack.stop()
            await intake.aclose()
            await database.dispose()

    app.router.lifespan_context = lifespan
    return app
