"""The admin console (MVP section 7): one static page served by awp itself at /console.

Three files and an icon, no build step and nothing fetched from anywhere else. The page holds no data: SecurityMiddleware
lets these GETs through without a key, and everything the page then shows comes from the admin API, called with the
Bearer key the operator typed (an admin key or a manager's key), so the API decides what each key sees. There is no
business logic here; the page only calls endpoints that exist.

The headers keep the page to itself: scripts, styles and requests only from this origin (no inline script), no framing,
no referrer, and never cached, so the page an operator sees is the one this version serves.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

HERE = Path(__file__).parent
FILES = {"index.html": "text/html; charset=utf-8", "app.js": "text/javascript; charset=utf-8",
         "app.css": "text/css; charset=utf-8", "favicon.svg": "image/svg+xml"}
HEADERS = {
    "Content-Security-Policy": "default-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "Cache-Control": "no-store",
}


def is_console(method: str, path: str) -> bool:
    """The requests that need no key: reading the static page. Nothing else lives under /console."""
    return method == "GET" and (path == "/console" or path.startswith("/console/"))


def build_console() -> APIRouter:
    r = APIRouter(include_in_schema=False)

    def serve(name: str) -> Response:
        if name not in FILES:  # a fixed list, never a path made from the request
            raise HTTPException(404, "no such file", headers=HEADERS)
        return Response((HERE / name).read_bytes(), media_type=FILES[name], headers=HEADERS)

    @r.get("/console")
    @r.get("/console/")
    async def page():
        return serve("index.html")

    @r.get("/console/{name}")
    async def asset(name: str):
        return serve(name)

    return r
