"""Create an empty, migrated local deployment and its initial administrator.

Uses the existing local PostgreSQL engine only. Never copies demo business rows.
Credentials are written to ignored local files, never printed.
"""
import asyncio
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
from urllib.parse import urlsplit, urlunsplit, quote
from uuid import uuid4
import asyncpg
from vinhomes_api.password_auth import password_hash, PROVIDER

SERVICE = Path(__file__).resolve().parents[1]
ROOT = SERVICE.parents[1]
LOCAL = SERVICE / ".local-connected"


def envfile(path):
    return dict(line.split("=",1) for line in path.read_text(encoding="utf-8").splitlines() if "=" in line and not line.startswith("#"))


async def main():
    config = SERVICE / ".env.connected"
    if config.exists():
        raise RuntimeError("Connected configuration exists; refusing to replace credentials or initialize again.")
    source = envfile(SERVICE / ".local-v3-faker/migration.env")["DATABASE_URL"]
    parsed = urlsplit(source)
    if parsed.hostname != "127.0.0.1" or parsed.port != 5544:
        raise RuntimeError("Only the existing local PostgreSQL server on 5544 is supported by this bootstrap.")
    db = await asyncpg.connect(source)
    if await db.fetchval("select 1 from pg_database where datname='vinhomes_connected'"):
        raise RuntimeError("Database already exists; inspect it before retrying setup.")
    await db.execute('CREATE DATABASE vinhomes_connected')
    await db.close()
    owner_url = urlunsplit(parsed._replace(path="/vinhomes_connected"))
    LOCAL.mkdir(exist_ok=True)
    (LOCAL / "migration.env").write_text("DATABASE_URL="+owner_url+"\n",encoding="utf-8")
    environment = {**os.environ,"DATABASE_URL":owner_url}
    bun = shutil.which("bun.cmd") or shutil.which("bun")
    subprocess.run([bun,"server/scripts/migrate.ts"],cwd=ROOT,env=environment,check=True)
    tenant, user = str(uuid4()), str(uuid4())
    admin_email = sys.argv[1] if len(sys.argv)>1 else "admin@resident.local"
    password, runtime_password = secrets.token_urlsafe(20), secrets.token_hex(24)
    db = await asyncpg.connect(owner_url)
    try:
        async with db.transaction():
            await db.execute("select set_config('app.tenant_id',$1,true),set_config('app.user_id',$2,true)",tenant,user)
            await db.execute("insert into tenants(id,code,name,status) values($1,'resident-local','Resident local','active')",__import__('uuid').UUID(tenant))
            await db.execute("insert into users(id,email,name,status) values($1,$2,'Quản trị viên','active')",user,admin_email.lower())
            await db.execute("insert into tenant_memberships(tenant_id,user_id,status,joined_at) values($1,$2,'active',now())",__import__('uuid').UUID(tenant),user)
            await db.execute("insert into platform_admins(user_id) values($1)",user)
            await db.execute("insert into accounts(id,account_id,provider_id,user_id,password) values($1,$2,$3,$2,$4)",str(uuid4()),user,PROVIDER,password_hash(password))
        if await db.fetchval("select 1 from pg_roles where rolname='vinhomes_connected_api'"):
            raise RuntimeError("Runtime role already exists; refusing to overwrite it.")
        await db.execute("CREATE ROLE vinhomes_connected_api LOGIN PASSWORD '"+runtime_password+"' NOSUPERUSER NOBYPASSRLS")
        grants = (SERVICE / "scripts/grant_v3_api_role.sql").read_text().replace("vinhomes_v3_api","vinhomes_connected_api").replace("DATABASE vinhomes_v3","DATABASE vinhomes_connected")
        await db.execute(grants)
        await db.execute("GRANT INSERT, UPDATE, DELETE ON sessions TO vinhomes_connected_api")
        await db.execute("GRANT INSERT, UPDATE ON accounts, users, tenant_memberships, scoped_user_roles, access_scopes TO vinhomes_connected_api")
    finally:
        await db.close()
    config.write_text(
        "VINHOMES_API_HOST=127.0.0.1\nVINHOMES_API_PORT=8000\nVINHOMES_API_PASSWORD_AUTH=1\n"
        "VINHOMES_API_DEMO_MODE=0\nVINHOMES_API_DEV_USER_ID=\nVINHOMES_API_AUTH_URL=\n"
        f"VINHOMES_API_TENANT_ID={tenant}\n"
        f"VINHOMES_API_DATABASE_URL=postgresql+asyncpg://vinhomes_connected_api:{quote(runtime_password)}@127.0.0.1:5544/vinhomes_connected\n"
        "VINHOMES_API_ALLOWED_ORIGINS=http://127.0.0.1:3011,http://127.0.0.1:3020,http://localhost:3011,http://localhost:3020\n",encoding="utf-8")
    (LOCAL / "initial-admin.txt").write_text(f"Login: {admin_email}\nPassword: {password}\nURL: http://127.0.0.1:3020/operations/login\nChange this password after first sign-in.\n",encoding="utf-8")
    print("Created empty connected database and administrator. Credentials: services/vinhomes-api/.local-connected/initial-admin.txt")


if __name__ == "__main__":
    asyncio.run(main())
