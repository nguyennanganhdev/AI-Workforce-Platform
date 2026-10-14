# -*- coding: utf-8 -*-
"""Fail-fast checks for the C7/Phase-D test environment."""

from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
import sys

from alembic.config import Config
from alembic.script import ScriptDirectory


REQUIRED_MODULES = (
    "aiosqlite",
    "alembic",
    "fastapi",
    "httpx",
    "pytest",
    "sqlalchemy",
)


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    failures: list[str] = []
    if sys.version_info < (3, 11):
        failures.append("Python 3.11 or newer is required")
    for module in REQUIRED_MODULES:
        try:
            importlib.import_module(module)
        except ImportError:
            failures.append(f"missing Python module: {module}")

    config = Config(
        str(
            root
            / "src/agentscope/app/storage/_sql/_alembic/alembic.ini"
        )
    )
    scripts = ScriptDirectory.from_config(config)
    heads = scripts.get_heads()
    # The gate protects against a forked migration chain; the head name moves
    # with every new migration, so only the single-head invariant is pinned.
    if len(heads) != 1:
        failures.append(f"expected exactly one Alembic head, got {heads!r}")

    postgres = os.getenv("WORKFORCE_TEST_POSTGRES_URL")
    if postgres and not postgres.startswith(
        ("postgresql+asyncpg://", "postgresql://")
    ):
        failures.append(
            "WORKFORCE_TEST_POSTGRES_URL must be a PostgreSQL test DSN"
        )

    report = {
        "python": sys.version.split()[0],
        "alembic_heads": heads,
        "postgres_gate": "configured" if postgres else "not_configured",
        "status": "failed" if failures else "ready",
        "failures": failures,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
