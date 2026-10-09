"""Run the platform: `python -m awp` (set AWP_PACKS to load domain packs)."""
from __future__ import annotations

import importlib
import os

import uvicorn

from .app import build_app
from .config import Settings


def load_packs(spec: str | None) -> list:
    """AWP_PACKS="pkg.module:Class,other.module:Class" -> pack instances."""
    packs = []
    for item in filter(None, (spec or "").split(",")):
        module, _, cls = item.strip().partition(":")
        packs.append(getattr(importlib.import_module(module), cls)())
    return packs


def main() -> None:
    settings = Settings.from_env()
    if not settings.service_keys and not settings.admin_keys and not settings.dev_open:
        raise SystemExit("Set AWP_SERVICE_KEYS and AWP_ADMIN_KEYS (or AWP_DEV_OPEN=1 for local work).")
    app = build_app(settings, packs=load_packs(os.environ.get("AWP_PACKS")))
    uvicorn.run(app, host=os.environ.get("AWP_HOST", "127.0.0.1"),
                port=int(os.environ.get("AWP_PORT", "8800")))


if __name__ == "__main__":
    main()
