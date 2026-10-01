"""FastAPI entry point for the canonical V3 PostgreSQL schema."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
import os
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine

from .v3_config import V3Settings
from .v3_routes import router as v3_router
from .v3_operations import router as operations_router
from .v3_mutations import router as mutations_router
from .v3_specialized import router as specialized_router
from .v3_triage import router as triage_router
from .v3_files import router as files_router
from .v3_resident import router as resident_router
from .v3_resident_support import router as resident_support_router
from .v3_rooms import router as rooms_router
from .v3_knowledge import router as knowledge_router
from .v3_memory import router as memory_router
from .v3_reports import router as reports_router
from .v3_water import router as water_router
from .v3_demo import router as demo_router
from .password_auth import router as password_router


def create_app(settings: V3Settings | None = None) -> FastAPI:
    settings = settings or V3Settings.from_env()
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = settings
        app.state.engine = (
            create_async_engine(settings.database_url, pool_pre_ping=True)
            if settings.database_url else None
        )
        try:
            yield
        finally:
            if app.state.engine is not None:
                await app.state.engine.dispose()

    app = FastAPI(
        title="Vinhomes Operations API (database V3)",
        version="0.2.0",
        description=(
            "Operations API for the canonical V3 tickets/work_orders schema. "
            "Business calls require a platform session through VINHOMES_API_AUTH_URL, "
            "or VINHOMES_API_DEV_USER_ID on loopback only. The user must have an "
            "active admin or scoped management/staff grant in V3."
        ),
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def protect_browser_mutations(request, call_next):
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            allowed = {v.strip().rstrip("/") for v in os.getenv("VINHOMES_API_ALLOWED_ORIGINS", "").split(",") if v.strip()}
            if settings.demo_mode or settings.dev_user_id:
                allowed.update({"http://127.0.0.1:3011", "http://localhost:3011", "http://127.0.0.1:3020", "http://localhost:3020"})
            same_origin = origin and urlsplit(origin).netloc == request.headers.get("host")
            if request.headers.get("sec-fetch-site") == "cross-site" or (origin and not same_origin and origin.rstrip("/") not in allowed):
                return JSONResponse({"detail": "Untrusted browser origin"}, status_code=403)
        return await call_next(request)

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "vinhomes-api", "schema": "v3",
                "dataMode": "faker-database" if settings.demo_mode else "database",
                "authMode": "password" if settings.password_auth else "demo" if settings.demo_mode else "development" if settings.dev_user_id else "session" if settings.auth_url else "unconfigured"}

    @app.get("/ready", tags=["health"])
    async def ready() -> dict[str, str]:
        if app.state.engine is None:
            raise HTTPException(503, "VINHOMES_API_DATABASE_URL is not configured")
        try:
            async with app.state.engine.connect() as connection:
                result = await connection.execute(
                    text("""
                        select to_regclass('public.tickets') is not null
                           and to_regclass('public.work_orders') is not null
                           and to_regclass('public.vh_qc_results') is not null
                           and to_regclass('public.vh_qc_redo_orders') is not null
                           and to_regclass('public.vh_cleaning_plans') is not null
                           and to_regclass('public.vh_security_incidents') is not null
                           and to_regclass('public.vh_budget_approvals') is not null
                    """)
                )
                if not result.scalar_one():
                    raise HTTPException(503, "V3 operations migrations are missing")
        except SQLAlchemyError as exc:
            raise HTTPException(503, "V3 database is unavailable") from exc
        return {"status": "ready", "schema": "v3"}

    app.include_router(v3_router)
    app.include_router(password_router)
    app.include_router(operations_router)
    app.include_router(mutations_router)
    app.include_router(specialized_router)
    app.include_router(triage_router)
    app.include_router(files_router)
    app.include_router(resident_router)
    app.include_router(resident_support_router)
    app.include_router(rooms_router)
    app.include_router(knowledge_router)
    app.include_router(memory_router)
    app.include_router(reports_router)
    app.include_router(water_router)
    app.include_router(demo_router)
    if settings.demo_mode:
        demo_ui = Path(__file__).parent / "demo_ui"
        app.mount("/demo/assets", StaticFiles(directory=demo_ui), name="demo-assets")

        @app.get("/demo/ui", include_in_schema=False)
        async def demo_page() -> FileResponse:
            return FileResponse(demo_ui / "business.html", headers={"Cache-Control": "no-store"})
    return app


app = create_app()
