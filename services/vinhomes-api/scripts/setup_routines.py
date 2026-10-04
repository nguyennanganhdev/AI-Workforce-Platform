"""Give the local password-login deployment (.local-connected) the schedule service for management's agents.

    python scripts/setup_routines.py

1. Creates (or re-keys) the database role the schedule service signs in with and applies
   server/scripts/grant_routines_role.sql: the routine tables and the queue, nothing else.
2. Lets the API close a run (the one new grant of grant_v3_api_role.sql), for a database migrated
   before this release.
3. Writes .local-connected/routines.env (ignored by git): ROUTINES_DATABASE_URL, ROUTINES_TENANT_ID,
   ROUTINES_SERVICE_TOKEN and ROUTINES_API_URL. Nothing is printed from it.

Run again any time: every step is repeatable. Then start the service with scripts/start_routines.ps1
and restart the API, which reads the same file.
"""
import asyncio
import secrets
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

import asyncpg

SERVICE = Path(__file__).resolve().parents[1]
ROOT = SERVICE.parents[1]
ROLE = "vinhomes_connected_routines"


def environment(path: Path) -> dict[str, str]:
    return dict(line.split("=", 1) for line in path.read_text(encoding="utf-8").splitlines()
                if line and not line.startswith("#") and "=" in line)


async def main() -> None:
    local = SERVICE / ".local-connected"
    owner_url = environment(local / "migration.env")["DATABASE_URL"]
    api = environment(SERVICE / ".env.connected")
    api_role = urlsplit(api["VINHOMES_API_DATABASE_URL"].replace("postgresql+asyncpg:", "postgresql:")).username
    address = urlsplit(owner_url)
    if address.hostname not in ("localhost", "127.0.0.1"):
        raise RuntimeError("This setup is for a local database")
    path = local / "routines.env"
    existing = environment(path) if path.exists() else {}
    known = existing.get("ROUTINES_DATABASE_URL")
    password = urlsplit(known).password if known else secrets.token_hex(24)
    token = existing.get("ROUTINES_SERVICE_TOKEN") or secrets.token_urlsafe(32)
    grants = (ROOT / "server/scripts/grant_routines_role.sql").read_text(encoding="utf-8")
    db = await asyncpg.connect(owner_url)
    try:
        async with db.transaction():
            literal = "'" + password.replace("'", "''") + "'"
            verb = "ALTER" if await db.fetchval("select 1 from pg_roles where rolname=$1", ROLE) else "CREATE"
            await db.execute(f"{verb} ROLE {ROLE} LOGIN PASSWORD {literal} NOSUPERUSER NOBYPASSRLS")
            await db.execute(f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {ROLE}")
            await db.execute(grants.replace("vinhomes_routines", ROLE))
            await db.execute(f"GRANT UPDATE (status, finished_at, error) ON routine_runs TO {api_role}")
    finally:
        await db.close()
    url = urlunsplit((address.scheme, f"{ROLE}:{quote(password)}@{address.hostname}:{address.port}", address.path, "", ""))
    path.write_text(f"ROUTINES_DATABASE_URL={url}\nROUTINES_TENANT_ID={api['VINHOMES_API_TENANT_ID']}\n"
                    f"ROUTINES_SERVICE_TOKEN={token}\nROUTINES_API_URL=http://127.0.0.1:8000\n", encoding="utf-8")
    print(f"Schedule service ready: role {ROLE}. Settings saved in {path} (keep it out of git).")


if __name__ == "__main__":
    asyncio.run(main())
