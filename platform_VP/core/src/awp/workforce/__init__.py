"""Workforce v1: the partner API of the platform (contract 1.3).

`install_workforce` mounts the admin API (/platform/v1/wf) and the partner API
(/workforce/v1) on the app. Slices add their modules under this package.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from fastapi import APIRouter, FastAPI

from ..config import Settings
from ..db import Database
from .admin import build_admin
from .auth import RateLimiter
from .close import build_close
from .commands import build_commands
from .crypto import Sealer
from .decision import build_decision
from .engine import Engine, NullEngine
from .errors import OpenRoute, WorkforceError, WorkforceRoute
from .onboarding import build_onboarding
from .partner_hub import McpHub
from .provider_api import build_provider
from .reads import build_reads
from .stream import Slots, build_stream
from .uploads import build_uploads


@dataclass
class WorkforceContext:
    rt: Any
    settings: Settings
    db: Database
    sealer: Sealer
    limiter: RateLimiter
    slots: Slots
    engine: Engine = field(default_factory=NullEngine)  # what runs the jobs; S3 replaces it
    mcp: McpHub | None = None  # the MCP clients of the routes' partner tools (also rt.mcp)


def build_partner(ctx: WorkforceContext) -> APIRouter:
    r = APIRouter(prefix="/workforce/v1", route_class=WorkforceRoute, tags=["workforce"])
    build_onboarding(r, ctx)
    build_commands(r, ctx)
    build_reads(r, ctx)
    build_stream(r, ctx)
    build_close(r, ctx)
    build_decision(r, ctx)
    build_provider(r, ctx)
    r.include_router(build_uploads(ctx))  # image assets: an extension beyond contract v1 (spec A3)
    return r


def build_fallback() -> APIRouter:
    """Every other path under /workforce answers in the error envelope (SecurityMiddleware lets
    the whole prefix through), so /workforce/v2 or a missing slash cannot leak a different shape."""
    r = APIRouter(prefix="/workforce", route_class=OpenRoute, include_in_schema=False)

    @r.api_route("", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    @r.api_route("/{rest:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    async def unknown(rest: str = ""):
        raise WorkforceError("NOT_FOUND", 404, "No such endpoint.")

    return r


def install_workforce(app: FastAPI, rt: Any) -> WorkforceContext:
    s = rt.settings
    ctx = WorkforceContext(rt=rt, settings=s, db=rt.db,
                           sealer=Sealer(s.secret_key, s.dev_open),
                           limiter=RateLimiter(s.wf_rate_per_minute), slots=Slots(s.wf_max_streams))
    ctx.mcp = rt.mcp = McpHub(rt.db, ctx.sealer, s)
    app.state.wf = ctx
    app.include_router(build_admin(ctx))
    app.include_router(build_partner(ctx))
    app.include_router(build_fallback())
    return ctx
