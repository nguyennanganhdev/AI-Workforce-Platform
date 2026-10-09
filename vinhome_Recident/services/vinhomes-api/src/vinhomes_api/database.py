"""Create, migrate, seed and grant the domain database.

    python -m vinhomes_api.database create  --admin-url URL --name vinhomes
    python -m vinhomes_api.database migrate --url URL
    python -m vinhomes_api.database seed    --url URL
    python -m vinhomes_api.database role    --url URL --role vinhomes_api --password-env API_DB_PASSWORD
    python -m vinhomes_api.database mock    --url URL [--profile test|standard] [--seed 42]
    python -m vinhomes_api.database import  --url URL --dir DIR [--dry-run]
    python -m vinhomes_api.database client  --url URL --id platform --kind platform [--accepts-cases]
    python -m vinhomes_api.database reset   --url URL --confirm DATABASE_NAME

The SQL lives next to this file in `schema/`. Migrations are numbered files, applied once each in
order and recorded in `schema_migrations` with a checksum, so a file edited after it was applied is
refused instead of silently skipped. URLs and passwords are never printed. `--url` may be left out when the environment variable DATABASE_URL holds it,
which keeps the password off the command line (a container's command is visible to whoever can inspect it).

`seed` writes sample rows for several tenants, so it needs a role that is not held to tenant row level
security (a superuser or a BYPASSRLS role). `migrate` and `role` do not.
"""

import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
from pathlib import Path

import asyncpg

SCHEMA = Path(__file__).resolve().parent / "schema"
IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")


def _url(value: str) -> str:
    return value.replace("postgresql+asyncpg:", "postgresql:", 1)


def _identifier(value: str, what: str) -> str:
    if not IDENTIFIER.fullmatch(value):
        raise SystemExit(f"{what} must be lower case letters, digits and underscores (at most 63).")
    return value


def migration_files() -> list[Path]:
    return sorted((SCHEMA / "migrations").glob("*.sql"))


def seed_files() -> list[Path]:
    return sorted((SCHEMA / "seed").glob("*.sql"))


async def create(admin_url: str, name: str) -> bool:
    """Create the database when it does not exist. True when it was created."""
    _identifier(name, "Database name")
    connection = await asyncpg.connect(_url(admin_url))
    try:
        if await connection.fetchval("select 1 from pg_database where datname=$1", name):
            return False
        await connection.execute(f'create database "{name}"')
        return True
    finally:
        await connection.close()


async def migrate(url: str) -> list[str]:
    """Apply the migrations not yet applied, each in its own transaction. Returns the names applied."""
    connection = await asyncpg.connect(_url(url))
    applied: list[str] = []
    try:
        await connection.execute(
            "create table if not exists schema_migrations("
            "name text primary key, checksum text not null, applied_at timestamptz not null default now())"
        )
        done = {row["name"]: row["checksum"] for row in await connection.fetch("select name,checksum from schema_migrations")}
        for path in migration_files():
            sql = path.read_text(encoding="utf-8")
            checksum = hashlib.sha256(sql.encode("utf-8")).hexdigest()
            if path.name in done:
                if done[path.name] != checksum:
                    raise SystemExit(f"{path.name} was changed after it was applied. Add a new migration instead.")
                continue
            async with connection.transaction():
                await connection.execute(sql)
                await connection.execute("insert into schema_migrations(name,checksum) values($1,$2)", path.name, checksum)
            applied.append(path.name)
        return applied
    finally:
        await connection.close()


async def seed(url: str) -> list[str]:
    """Load the sample data. Safe to repeat: the files insert with ON CONFLICT DO NOTHING."""
    connection = await asyncpg.connect(_url(url))
    loaded: list[str] = []
    try:
        for path in seed_files():
            async with connection.transaction():
                await connection.execute(path.read_text(encoding="utf-8"))
            loaded.append(path.name)
        return loaded
    finally:
        await connection.close()


async def role(url: str, name: str, password: str | None) -> None:
    """Create the API's runtime role when missing and give it exactly the rights in roles.sql."""
    _identifier(name, "Role name")
    database = None
    connection = await asyncpg.connect(_url(url))
    try:
        database = await connection.fetchval("select current_database()")
        exists = await connection.fetchval("select 1 from pg_roles where rolname=$1", name)
        if not exists:
            if not password:
                raise SystemExit("The role does not exist: give its password through --password-env.")
            statement = await connection.fetchval("select format('create role %I login nosuperuser nobypassrls password %L', $1::text, $2::text)", name, password)
            await connection.execute(statement)
        elif password:
            statement = await connection.fetchval("select format('alter role %I password %L', $1::text, $2::text)", name, password)
            await connection.execute(statement)
        flags = await connection.fetchrow("select rolsuper, rolbypassrls from pg_roles where rolname=$1", name)
        if flags["rolsuper"] or flags["rolbypassrls"]:
            raise SystemExit(f"Role {name} is a superuser or bypasses row level security: refusing to use it for the API.")
        quoted = '"' + name + '"'
        sql = (SCHEMA / "roles.sql").read_text(encoding="utf-8").replace(":role", quoted)
        await connection.execute(f'grant connect on database "{database}" to {quoted}')
        await connection.execute(sql)
    finally:
        await connection.close()


async def reset(url: str, confirm: str) -> None:
    """Drop everything in the schema and build it again, empty. The database name must be repeated to confirm."""
    connection = await asyncpg.connect(_url(url))
    try:
        name = await connection.fetchval("select current_database()")
        if confirm != name:
            raise SystemExit(f"This would erase database {name}. Repeat its name with --confirm to go ahead.")
        await connection.execute("drop schema public cascade; create schema public")
    finally:
        await connection.close()
    await migrate(url)


async def client(url: str, client_id: str, kind: str, accepts_cases: bool, levels: dict, tenant: str) -> str:
    """Register an integration client, or rotate its secret, and return the secret (shown once, never stored)."""
    from .integration import digest, new_secret
    secret = new_secret()
    connection = await asyncpg.connect(_url(url))
    try:
        await connection.execute("select set_config('app.tenant_id',$1,false)", tenant)
        await connection.execute("""
            insert into integration_clients(tenant_id,id,name,kind,status,accepts_cases,levels,secret_hash)
            values($1::uuid,$2,$2,$3,'active',$4,$5::jsonb,$6)
            on conflict (tenant_id,id) do update set secret_hash=excluded.secret_hash,levels=excluded.levels,accepts_cases=excluded.accepts_cases,status='active'
        """, tenant, client_id, kind, accepts_cases, json.dumps(levels), digest(secret))
    finally:
        await connection.close()
    return secret


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m vinhomes_api.database", description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    from_env = os.environ.get("DATABASE_URL")
    c = commands.add_parser("create")
    c.add_argument("--admin-url", default=from_env, required=from_env is None)
    c.add_argument("--name", required=True)
    for name in ("migrate", "seed"):
        commands.add_parser(name).add_argument("--url", default=from_env, required=from_env is None)
    k = commands.add_parser("mock")
    k.add_argument("--url", default=from_env, required=from_env is None)
    k.add_argument("--profile", default="standard", choices=["test", "standard"])
    k.add_argument("--seed", type=int, default=42)
    i = commands.add_parser("import")
    i.add_argument("--url", default=from_env, required=from_env is None)
    i.add_argument("--dir", required=True)
    i.add_argument("--dry-run", action="store_true")
    g = commands.add_parser("client")
    g.add_argument("--url", default=from_env, required=from_env is None)
    g.add_argument("--id", required=True)
    g.add_argument("--kind", choices=["reception", "platform"], default="platform")
    g.add_argument("--accepts-cases", action="store_true")
    g.add_argument("--tenant", default="11111111-1111-5111-a111-111111111111")
    g.add_argument("--resident-levels", default="read,draft,act_small")
    g.add_argument("--staff-levels", default="read,draft,propose")
    z = commands.add_parser("reset")
    z.add_argument("--url", default=from_env, required=from_env is None)
    z.add_argument("--confirm", required=True)
    r = commands.add_parser("role")
    r.add_argument("--url", default=from_env, required=from_env is None)
    r.add_argument("--role", required=True)
    r.add_argument("--password-env", help="name of the environment variable that holds the role's password")
    args = parser.parse_args(argv)

    if args.command == "create":
        print("created" if asyncio.run(create(args.admin_url, args.name)) else "already exists")
    elif args.command == "migrate":
        done = asyncio.run(migrate(args.url))
        print("applied: " + ", ".join(done) if done else "up to date")
    elif args.command == "seed":
        print("loaded: " + ", ".join(asyncio.run(seed(args.url))))
    elif args.command == "mock":
        from .mock_data import build
        print("built: " + ", ".join(f"{k}={v}" for k, v in asyncio.run(build(args.url, args.profile, args.seed)).items()))
    elif args.command == "import":
        from .import_data import load
        added, problems = asyncio.run(load(args.url, args.dir, args.dry_run))
        for line in problems:
            print("ERROR " + line)
        if problems:
            print(f"{len(problems)} problem(s); nothing was written.")
            return 1
        print(("would add: " if args.dry_run else "added: ") + ", ".join(f"{k}={v}" for k, v in added.items()))
    elif args.command == "client":
        levels = {"resident": [x for x in args.resident_levels.split(",") if x], "staff": [x for x in args.staff_levels.split(",") if x]}
        print("client secret (shown once): " + asyncio.run(client(args.url, args.id, args.kind, args.accepts_cases, levels, args.tenant)))
    elif args.command == "reset":
        asyncio.run(reset(args.url, args.confirm))
        print("schema rebuilt empty; run `role` again for the API's rights")
    else:
        password = os.environ.get(args.password_env) if args.password_env else None
        if args.password_env and not password:
            raise SystemExit(f"Environment variable {args.password_env} is empty or missing.")
        asyncio.run(role(args.url, args.role, password))
        print(f"role {args.role} ready")
    return 0


if __name__ == "__main__":
    sys.exit(main())
