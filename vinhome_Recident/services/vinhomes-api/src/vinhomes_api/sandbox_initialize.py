"""Initialize/restart the isolated Docker sandbox. Reads secrets only from environment/files."""

import asyncio
import json
import os
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import asyncpg

from . import database
from .bootstrap import bootstrap
from .owner_bundle import validate
from .owner_sandbox import MARKER, guard, materialize
from .owner_sandbox_bundle import prepare
from .owner_sandbox_business import extend
from .travel_seed import load as travel


async def initialize(url, folder, runtime_password):
    guard(url)
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    os.chmod(folder, 0o700)
    bundle = folder / "bundle"
    credentials_path = folder / "accounts.secret.json"
    if not bundle.exists():
        prepare(bundle)
    report = validate(bundle)
    if not credentials_path.exists() and not report["valid"]:
        raise ValueError(
            "Sandbox bundle expired or invalid; provision a new isolated sandbox"
        )
    parsed = urlsplit(url)
    name = parsed.path.lstrip("/")
    base = urlunsplit(parsed._replace(path="/postgres"))
    conn = await asyncpg.connect(base)
    try:
        exists = await conn.fetchval("select 1 from pg_database where datname=$1", name)
    finally:
        await conn.close()
    if not exists:
        await database.create(base, name)
        conn = await asyncpg.connect(url)
        try:
            await conn.execute(f"COMMENT ON DATABASE \"{name}\" IS '{MARKER}'")
        finally:
            await conn.close()
    conn = await asyncpg.connect(url)
    try:
        if (
            await conn.fetchval(
                "select shobj_description(oid,'pg_database') from pg_database where datname=current_database()"
            )
            != MARKER
        ):
            raise ValueError("Existing database is not a marked synthetic sandbox")
    finally:
        await conn.close()
    await database.migrate(url)
    await bootstrap(url)
    await database.role(url, "sandbox_runtime", runtime_password)
    if credentials_path.exists():
        # A restart is not a fresh operational import: elapsed shifts stay elapsed.
        # Require the original, already-validated snapshot instead of revalidating its clock.
        conn = await asyncpg.connect(url)
        try:
            snapshot = await conn.fetchval("select snapshot_sha256 from owner_operational_batches where bundle_code='op1-technical-simulation'")
            if snapshot != report['snapshot_sha256']:
                raise ValueError('Existing sandbox source changed; provision a new version explicitly')
        finally:
            await conn.close()
        credentials = json.loads(credentials_path.read_text(encoding="utf-8"))
    else:
        result = await materialize(url, bundle)
        credentials = result["credentials"]
        credentials_path.write_text(
            json.dumps(credentials, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        os.chmod(credentials_path, 0o600)
    business = await extend(url)
    if business["credentials"]:
        credentials.extend(business["credentials"])
        credentials_path.write_text(
            json.dumps(credentials, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        os.chmod(credentials_path, 0o600)
    await travel(url, enable_mock=True)
    result = {
        "data_mode": "synthetic_test",
        "accounts": len(credentials),
        "business_profile": business["profile"],
        "production_changed": False,
        "agent_calls": 0,
    }
    (folder / "data-report.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    return result


if __name__ == "__main__":
    print(
        json.dumps(
            asyncio.run(
                initialize(
                    os.environ["DATABASE_URL"],
                    os.getenv("SANDBOX_PRIVATE_DIR", "/sandbox"),
                    os.environ["SANDBOX_RUNTIME_PASSWORD"],
                )
            )
        )
    )
