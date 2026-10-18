"""Validate and privately stage an OP1 technical handoff. Never activates accounts, routing or knowledge.

    DATABASE_URL=<owner connection> python -m vinhomes_api.owner_operational --folder DIR
    DATABASE_URL=<owner connection> python -m vinhomes_api.owner_operational --folder DIR --apply --actor ADMIN_ID

Default is offline validation. Personal rows are owner-only staging data, never MCP context.
"""

import argparse
import asyncio
import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit
from uuid import NAMESPACE_URL, UUID, uuid5

import asyncpg

from .database import TENANT, _url
from .owner_bundle import inspect_bundle


def inspect(folder, now=None):
    report, rows, manifest = inspect_bundle(folder, now)
    if report["schema_version"] != 2:
        report["errors"].append(
            "Operational staging requires pilot schema_version=2 with SOP and evidence"
        )
        report["valid"] = False
    return report, rows, manifest


async def stage(url, folder, actor, now=None):
    report, rows, manifest = inspect(folder, now)
    if not report["valid"]:
        # Field/line errors are safe; never include input values or the SQL exception text.
        raise ValueError("Bundle validation failed: " + "; ".join(report["errors"]))
    if manifest["data_mode"] == "synthetic_test" and not re.fullmatch(
        r"owner_pilot_test_[a-f0-9]{32}", urlsplit(_url(url)).path.lstrip("/")
    ):
        raise ValueError(
            "Synthetic data may only enter an isolated owner_pilot_test database"
        )
    tenant = UUID(TENANT)
    batch = uuid5(
        NAMESPACE_URL,
        f"vinhomes-owner-batch/{TENANT}/{manifest['bundle_code']}/{manifest['version']}",
    )
    conn = await asyncpg.connect(_url(url))
    try:
        async with conn.transaction():
            await conn.execute("select set_config('app.tenant_id',$1,true)", TENANT)
            if not await conn.fetchval(
                """select 1 from platform_admins a join users u on u.id=a.user_id
                join tenant_memberships m on m.user_id=u.id
                where a.user_id=$1 and u.status='active' and m.tenant_id=$2 and m.status='active'""",
                actor,
                tenant,
            ):
                raise ValueError(
                    "An active Domain administrator in this tenant must be the staging actor"
                )
            await conn.execute(
                "select pg_advisory_xact_lock(hashtextextended($1,0))", str(batch)
            )
            old = await conn.fetchval(
                "select snapshot_sha256 from owner_operational_batches where tenant_id=$1 and id=$2",
                tenant,
                batch,
            )
            if old is not None and old != report["snapshot_sha256"]:
                raise ValueError(
                    "Bundle version already exists with different content; submit a new version"
                )
            if old is None:
                await conn.execute(
                    """insert into owner_operational_batches
                    (id,tenant_id,bundle_code,version,snapshot_sha256,manifest,counts,staged_by)
                    values($1,$2,$3,$4,$5,$6::jsonb,$7::jsonb,$8)""",
                    batch,
                    tenant,
                    manifest["bundle_code"],
                    manifest["version"],
                    report["snapshot_sha256"],
                    json.dumps(manifest, ensure_ascii=False),
                    json.dumps(report["counts"]),
                    actor,
                )
                await conn.executemany(
                    """insert into owner_operational_records
                    (tenant_id,batch_id,dataset,ordinal,data) values($1,$2,$3,$4,$5::jsonb)""",
                    [
                        (
                            tenant,
                            batch,
                            dataset,
                            index,
                            json.dumps(
                                {
                                    key: value
                                    for key, value in row.items()
                                    if key != "_label"
                                },
                                ensure_ascii=False,
                            ),
                        )
                        for dataset, records in rows.items()
                        for index, row in enumerate(records, 1)
                    ],
                )
        return {
            **report,
            "database_written": old is None,
            "batch_id": str(batch),
            "status": "staged",
            "idempotent_replay": old is not None,
            "personal_data_exported_to_platform": False,
            "operational_activation": False,
        }
    finally:
        await conn.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folder", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--actor")
    args = parser.parse_args()
    try:
        if args.apply:
            if not os.getenv("DATABASE_URL") or not args.actor:
                raise ValueError("--apply requires DATABASE_URL and --actor")
            report = asyncio.run(
                stage(os.environ["DATABASE_URL"], args.folder, args.actor)
            )
        else:
            report = inspect(args.folder)[0]
    except (OSError, ValueError, TypeError, asyncpg.PostgresError):
        # SQL errors may contain emails/row contents/connection data. Keep console output redacted.
        report = {
            "valid": False,
            "errors": [
                "Staging refused: check validation, active administrator, database privileges and bundle version"
            ],
            "database_written": False,
        }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["valid"] else 1)


if __name__ == "__main__":
    main()
