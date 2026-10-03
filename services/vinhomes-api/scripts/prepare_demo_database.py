"""Prepare an isolated local database configuration and seed canonical V3 tables."""
import asyncio
from pathlib import Path
import secrets
import sys
from urllib.parse import quote

import asyncpg

SERVICE = Path(__file__).resolve().parents[1]
LOCAL = SERVICE / ".local-v3-faker"


def read_env(path: Path) -> dict[str, str]:
    return dict(line.split("=", 1) for line in path.read_text().splitlines() if line and not line.startswith("#"))


def prepare() -> None:
    LOCAL.mkdir(exist_ok=True)
    postgres = LOCAL / "postgres.env"
    if not postgres.exists():
        postgres.write_text("POSTGRES_DB=vinhomes_v3\nPOSTGRES_USER=vinhomes_seed\nPOSTGRES_PASSWORD=" + secrets.token_hex(24) + "\n")
    settings = read_env(postgres)
    migration = f"postgresql://vinhomes_seed:{quote(settings['POSTGRES_PASSWORD'])}@127.0.0.1:5544/vinhomes_v3"
    (LOCAL / "migration.env").write_text(f"DATABASE_URL={migration}\n")
    runtime = LOCAL / "runtime.env"
    if not runtime.exists():
        runtime.write_text("API_PASSWORD=" + secrets.token_hex(24) + "\n")
    password = read_env(runtime)["API_PASSWORD"]
    (LOCAL / "api.env").write_text(
        "VINHOMES_API_DATABASE_URL=postgresql+asyncpg://vinhomes_v3_api:" + quote(password) + "@127.0.0.1:5544/vinhomes_v3\n"
        "VINHOMES_API_TENANT_ID=11111111-1111-5111-a111-111111111111\n"
        "VINHOMES_API_DEMO_MODE=1\nVINHOMES_API_HOST=127.0.0.1\nVINHOMES_API_PORT=8000\n")
    print("Local database configuration prepared; credentials kept in ignored files.")


async def seed() -> None:
    db = await asyncpg.connect(read_env(LOCAL / "migration.env")["DATABASE_URL"])
    try:
        if await db.fetchval("select current_database()") != "vinhomes_v3":
            raise RuntimeError("Refusing to seed a database outside the local demo")
        if await db.fetchval("select count(*) from tenants where id <> '11111111-1111-5111-a111-111111111111'"):
            raise RuntimeError("Refusing to seed a database containing another tenant")
        await db.execute((SERVICE / "scripts/seed_v3_local.sql").read_text(encoding="utf-8"))
        await db.execute((SERVICE / "scripts/seed_v3_faker.sql").read_text(encoding="utf-8"))
        await db.execute((SERVICE / "scripts/seed_v3_demo_ui.sql").read_text(encoding="utf-8"))
        await db.execute((SERVICE / "scripts/seed_v3_remaining.sql").read_text(encoding="utf-8"))
        await db.execute((SERVICE / "scripts/seed_v3_ocean_park.sql").read_text(encoding="utf-8"))
        password = read_env(LOCAL / "runtime.env")["API_PASSWORD"]
        # Password is locally generated; quote as a SQL literal for DDL (no bind parameters).
        literal = "'" + password.replace("'", "''") + "'"
        if not await db.fetchval("select 1 from pg_roles where rolname='vinhomes_v3_api'"):
            await db.execute(f"CREATE ROLE vinhomes_v3_api LOGIN PASSWORD {literal} NOSUPERUSER NOBYPASSRLS")
        else:
            await db.execute(f"ALTER ROLE vinhomes_v3_api PASSWORD {literal} NOSUPERUSER NOBYPASSRLS")
        await db.execute((SERVICE / "scripts/grant_v3_api_role.sql").read_text(encoding="utf-8"))
        print("V3 faker fixtures seeded and runtime role configured.")
    finally:
        await db.close()


async def prepare_ui_scope(upgrade: bool = False) -> None:
    db = await asyncpg.connect(read_env(LOCAL / "migration.env")["DATABASE_URL"])
    try:
        if await db.fetchval("select current_database()") != "vinhomes_v3":
            raise RuntimeError("Refusing UI fixtures outside the local demo")
        if await db.fetchval("select count(*) from tenants where id <> '11111111-1111-5111-a111-111111111111'"):
            raise RuntimeError("Refusing UI fixtures with another tenant")
        await db.execute((SERVICE / "scripts/seed_v3_demo_ui.sql").read_text(encoding="utf-8"))
        if upgrade:
            await db.execute((SERVICE / "scripts/seed_v3_remaining.sql").read_text(encoding="utf-8"))
            await db.execute((SERVICE / "scripts/seed_v3_ocean_park.sql").read_text(encoding="utf-8"))
            await db.execute((SERVICE / "scripts/grant_v3_api_role.sql").read_text(encoding="utf-8"))
        print("Local demo UI site permissions ready; workflow data preserved.")
    finally:
        await db.close()


if __name__ == "__main__":
    if sys.argv[1:] == ["prepare"]:
        prepare()
    elif sys.argv[1:] == ["seed"]:
        asyncio.run(seed())
    elif sys.argv[1:] == ["ui"]:
        asyncio.run(prepare_ui_scope())
    elif sys.argv[1:] == ["upgrade"]:
        asyncio.run(prepare_ui_scope(upgrade=True))
    else:
        raise SystemExit("Usage: prepare_demo_database.py prepare|seed|ui|upgrade")
