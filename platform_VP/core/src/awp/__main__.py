"""Run the platform: `python -m awp` (configuration is read from the AWP_* environment variables).

`python -m awp migrate [--storage] [--check] [--stamp]` brings the database schema to the latest revision (awp/migrate.py).
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

from .config import Settings


def migrate_command(argv: list[str]) -> int:
    from . import migrate

    ap = argparse.ArgumentParser(prog="python -m awp migrate", description="Schema migrations of AWP_DB_URL.")
    ap.add_argument("--check", action="store_true", help="change nothing; exit 1 unless the database is at the latest revision "
                    "and matches the models")
    ap.add_argument("--stamp", action="store_true", help="declare a database that create_all built to be at the latest revision "
                    "(refused when it differs from the models)")
    ap.add_argument("--storage", action="store_true", help="also bring AgentScope's storage database (AWP_AGENTSCOPE_DB_URL) "
                    "to its latest revision, with AgentScope's own scripts")
    args = ap.parse_args(argv)
    s = Settings.from_env()
    if args.check:
        problems = migrate.check(s.db_url)
        if problems:
            print("\n".join(problems), file=sys.stderr)
            raise SystemExit(1)
        print(f"up to date at revision {migrate.head()}")
        return 0
    if args.stamp:
        migrate.stamp(s.db_url)
        print(f"stamped at revision {migrate.head()}")
        return 0
    migrate.upgrade(s.db_url)
    print(f"at revision {asyncio.run(migrate.current(s.db_url))}")
    if args.storage:
        migrate.upgrade_storage(s.agentscope_db_url)
        print("AgentScope storage at its latest revision")
    return 0


def main(argv: list[str] | None = None) -> int | None:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "migrate":
        return migrate_command(argv[1:])
    import uvicorn

    from .app import build_app

    settings = Settings.from_env()
    if not settings.admin_keys and not settings.dev_open:
        raise SystemExit("Set AWP_ADMIN_KEYS (or AWP_DEV_OPEN=1 for local work).")
    if not settings.secret_key and not settings.dev_open:
        raise SystemExit("Set AWP_SECRET_KEY (a Fernet key) or AWP_DEV_OPEN=1 for local work.")
    app = build_app(settings)
    uvicorn.run(app, host=os.environ.get("AWP_HOST", "127.0.0.1"),
                port=int(os.environ.get("AWP_PORT", "8800")))
    return None


if __name__ == "__main__":
    main()
