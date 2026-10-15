"""Provision private filesystem storage for the existing local connected database.

No business fixtures are created. Run once or safely repeat after local setup.
"""
import asyncio
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID
import asyncpg

ROOT = Path(__file__).resolve().parents[1]


def envfile(path):
    return dict(line.split("=", 1) for line in path.read_text(encoding="utf-8-sig").splitlines()
                if "=" in line and not line.startswith("#"))


async def main():
    config = ROOT / ".env.connected"
    settings = envfile(config)
    url = envfile(ROOT / ".local-connected/migration.env")["DATABASE_URL"]
    parsed = urlsplit(url)
    if parsed.hostname != "127.0.0.1" or parsed.port != 5544 or parsed.path != "/vinhomes_connected":
        raise RuntimeError("This provisioner only supports the local connected database.")
    if settings["VINHOMES_API_HOST"] not in {"127.0.0.1", "localhost", "::1"}:
        raise RuntimeError("Local storage requires a loopback host.")
    tenant = UUID(settings["VINHOMES_API_TENANT_ID"])
    db = await asyncpg.connect(url)
    try:
        async with db.transaction():
            await db.execute("select set_config('app.tenant_id',$1,true)", str(tenant))
            await db.execute("""
                insert into storage_locations
                (tenant_id,provider,endpoint_ref,bucket_name,tenant_prefix,
                 credential_secret_ref,versioning_required,encryption_mode,purpose,status)
                values($1,'local_fs','connected-private-files','private-evidence',$2,
                       'local-filesystem-acl',false,'none','evidence','active')
                on conflict(endpoint_ref,bucket_name,tenant_prefix) do nothing
            """, tenant, f"{tenant}/")
    finally:
        await db.close()
    lines = config.read_text(encoding="utf-8-sig").splitlines()
    lines = [line for line in lines if not line.startswith("VINHOMES_API_LOCAL_FILE_STORAGE=")]
    config.write_text("\n".join(lines) + "\nVINHOMES_API_LOCAL_FILE_STORAGE=1\n", encoding="utf-8")
    print("Private local evidence storage configured. Restart the connected API to load the setting.")


if __name__ == "__main__":
    asyncio.run(main())
