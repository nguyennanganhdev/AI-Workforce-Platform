"""Builds the platform: AgentScope's service plus the core on top of it."""
from __future__ import annotations

import asyncio
import contextlib
import logging
import secrets
import time
from types import SimpleNamespace
from typing import Any

from fastapi import FastAPI
from starlette.middleware import Middleware

from agentscope.app import create_app
from agentscope.app.storage import AsyncSQLAlchemyStorage
from agentscope.app.workspace_manager import LocalWorkspaceManager

from .casefile import CaseStore
from .config import Settings
from .console import build_console
from .cost import CostService
from .db import Database, engine_options
from .agentscope_client import AgentScopeClient
from .assets import build_store
from .builder import Builder
from .bus import build_bus, new_node
from .evals.runner import EvalRunner
from .evals.sandbox import fixture_tools
from .guard import build_judge
from .middleware import middleware_factory, tool_factory
from .offload import PolicyAgent
from .profiles import ProfileStore
from .providers import ModelCatalog
from .router import build_router
from .runtime import Runtime
from .security import SecurityMiddleware
from .workforce import install_workforce, retention
from .workforce.managers import ManagerKeys
from .workforce.runner import WorkflowEngine
from .workforce.uploads import ensure_store
from .workforce.waker import relay

log = logging.getLogger("awp")


async def require_head(url: str) -> None:
    """With AWP_AUTO_CREATE=0 the tables come from `python -m awp migrate`: start only on a database that is at the latest
    revision (a database one revision behind would fail later, on the first query that needs the new column)."""
    from . import migrate

    try:
        at = await migrate.current(url)
    except Exception as e:
        raise RuntimeError(f"cannot read the schema revision of the database ({type(e).__name__}); "
                           "run `python -m awp migrate`") from e
    if at != migrate.head():
        raise RuntimeError(f"the database is at revision {at}, the code needs {migrate.head()}: run `python -m awp migrate`"
                           " (or set AWP_AUTO_CREATE=1 for a development database)")


def build_app(
    settings: Settings | None = None,
    *,
    catalog: ModelCatalog | None = None,
    judge: Any = None,
    storage: Any = None,
    message_bus: Any = None,
    workspace_manager: Any = None,
    sweep_every: float = 2.0,
    **create_app_kwargs: Any,
) -> FastAPI:
    settings = settings or Settings.from_env()
    pool = dict(pool_size=settings.db_pool_size, max_overflow=settings.db_max_overflow,
                pool_timeout=settings.db_pool_timeout, pool_recycle=settings.db_pool_recycle)
    database = Database(settings.db_url, **pool)
    catalog = catalog or ModelCatalog.load(settings.models_file)
    if storage is None:
        # SQLite is for development: wait for the lock instead of failing a reply.
        sqlite = settings.agentscope_db_url.startswith("sqlite")
        storage = AsyncSQLAlchemyStorage(
            settings.agentscope_db_url, create_tables=settings.auto_create,  # else its own scripts made them: `migrate --storage`
            engine_kwargs={"connect_args": {"timeout": 30}} if sqlite else engine_options(settings.agentscope_db_url, **pool) or None)
    node = new_node()
    # AWP_REDIS_URL: the bus every process of the fleet shares. Without it the bus is this process's memory, and the engine
    # refuses to start next to another process on the same database (workforce/nodes.py). A bus handed in is the caller's
    # word that it is shared.
    bus = message_bus or build_bus(settings.redis_url, node)
    workspaces = workspace_manager or LocalWorkspaceManager(basedir=settings.workspace_dir)
    if judge is None:
        judge = build_judge(settings.jev_enabled, settings.jev_model)

    rt = Runtime(
        settings=settings, db=database, cases=CaseStore(database),
        profiles=ProfileStore(database), catalog=catalog,
        cost=CostService(database, catalog), storage=storage, bus=bus, judge=judge,
        node=node, shared_bus=bool(message_bus is not None or settings.redis_url),
        assets=build_store(settings))  # a setting that cannot work stops the start here, by its name

    secret = secrets.token_urlsafe(24)
    kwargs = dict(
        enable_scheduler=False, title="AI Workforce Platform",
        extra_middlewares=[Middleware(SecurityMiddleware, settings=settings,
                                      internal_secret=secret, managers=ManagerKeys(database))],
        extra_agent_middlewares=middleware_factory(rt),
        extra_agent_tools=tool_factory(rt),
        custom_subagent_templates=[],
        custom_agent_cls=PolicyAgent,
    )
    kwargs.update(create_app_kwargs)
    app = create_app(storage, bus, workspaces, **kwargs)
    rt.templates = app.state.custom_subagent_templates  # the dict AgentCreate reads
    rt.kb_manager = app.state.knowledge_base_manager

    client = AgentScopeClient(rt, app, secret)
    app.include_router(build_router(rt))
    app.include_router(build_console())  # the admin console at /console: static files, every call it makes needs a key
    wf = install_workforce(app, rt)
    engine = WorkflowEngine(wf, client)  # the real engine; a test may put another in wf.engine
    wf.engine = engine
    rt.turn_hook = engine.on_turn
    rt.tool_factories.append(fixture_tools)  # the tools of an evaluation sandbox; nothing for any other case
    rt.evals, rt.builder = EvalRunner(wf), Builder(rt)
    app.state.awp = SimpleNamespace(rt=rt, client=client, settings=settings)

    inner = app.router.lifespan_context

    @contextlib.asynccontextmanager
    async def lifespan(a: FastAPI):
        if settings.auto_create:
            await database.create_all()
        else:
            await require_head(settings.db_url)
        retention.warn_if_short(settings)
        await ensure_store(rt)  # the bucket, made when missing; a store that is down is logged and tried again by an upload
        await rt.sync_templates()
        await rt.evals.store.reap()  # the evaluation runs of a process that is gone
        stop = asyncio.Event()

        async def heard(said: dict) -> None:
            if said.get("sync") == "templates":  # another process published, retired or rolled back an agent
                await rt.sync_templates(announce=False)

        async def sweep() -> None:
            look_at = 0.0  # retention asks the lease at most every half minute (every period when that is shorter)
            templates_at = time.monotonic() + 30.0
            while not stop.is_set():
                try:
                    sweep_engine = getattr(wf.engine, "sweep", None)  # whichever engine is attached
                    if sweep_engine is not None:
                        await sweep_engine()
                except Exception:
                    log.exception("workflow sweep failed")
                try:
                    await rt.evals.sweep()  # dead runs end; a sandbox workflow whose run is over is closed
                except Exception:
                    log.exception("evaluation sweep failed")
                if rt.shared_bus and time.monotonic() >= templates_at:  # the net under the fleet's "templates" news
                    templates_at = time.monotonic() + 30.0
                    try:
                        await rt.sync_templates(announce=False)
                    except Exception:
                        log.exception("could not read the published agents again")
                if time.monotonic() >= look_at:
                    look_at = time.monotonic() + min(30.0, settings.retention_every_seconds)
                    try:
                        await retention.tick(wf)  # every process asks; the lease lets one of them do it
                    except Exception:
                        log.exception("retention failed")
                with contextlib.suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(stop.wait(), sweep_every)

        task = None
        try:
            async with inner(a):
                await wf.slots.attach(bus if rt.shared_bus else None)
                start_engine = getattr(wf.engine, "start", None)
                if start_engine is not None:
                    await start_engine()
                task = asyncio.create_task(sweep())
                try:
                    # a commit here wakes the readers of the other processes; what is published here is theirs at once
                    async with relay(bus, node, rt.shared_bus, heard=heard) as tell:
                        rt.announce = (lambda what: tell({"sync": what})) if rt.shared_bus else None
                        try:
                            yield
                        finally:
                            rt.announce = None
                finally:
                    await rt.evals.stop()  # their sandbox workflows end with them, while the engine still runs
                    stop_engine = getattr(wf.engine, "stop", None)
                    if stop_engine is not None:  # before AgentScope shuts down under its dispatchers
                        await stop_engine()
        finally:
            stop.set()
            if task is not None:
                await task
            await client.aclose()
            if rt.assets is not None:
                await rt.assets.aclose()
            await database.dispose()

    app.router.lifespan_context = lifespan
    return app
