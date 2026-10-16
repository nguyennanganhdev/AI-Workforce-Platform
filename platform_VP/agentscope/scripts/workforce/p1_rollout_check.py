"""Read-only P1 upgrade inventory, compatible with the pre-0018 schema.

Run inside the target application's environment, without loading .env or
calling a model. This checks existing data, not business acceptance or backups.
Never invent historical contracts/versions to turn this report green.
"""

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path

from sqlalchemy import MetaData, Table, inspect, select, text
from sqlalchemy.ext.asyncio import create_async_engine


def object_value(value):
    return json.loads(value) if isinstance(value, str) else value or {}


async def inventory(url, storage=None):
    engine = create_async_engine(url)
    rows = {}
    columns = {}
    try:
        async with engine.connect() as connection:
            if engine.dialect.name == "postgresql":
                await connection.execute(text("SET TRANSACTION READ ONLY"))
            elif engine.dialect.name == "sqlite":
                await connection.execute(text("PRAGMA query_only=ON"))
            else:
                raise ValueError("P1 inventory supports PostgreSQL and isolated SQLite tests")
            available = await connection.run_sync(lambda conn: set(inspect(conn).get_table_names()))
            for name in ("alembic_version", "wf_workflows", "wf_unified_routes",
                         "wf_unified_operations", "wf_unified_receipts", "wf_unified_approvals"):
                if name not in available:
                    continue
                table = await connection.run_sync(lambda conn, table_name=name: Table(
                    table_name, MetaData(), autoload_with=conn))
                columns[name] = set(table.c.keys())
                rows[name] = [dict(row) for row in (await connection.execute(select(table))).mappings()]
    finally:
        await engine.dispose()

    blockers = []
    required = {"wf_workflows": {"id", "state", "payload"}, "wf_unified_routes": {"route_id"},
                "wf_unified_operations": {"terminal"}, "wf_unified_receipts": {"receipt_id", "ingestion_status"},
                "wf_unified_approvals": {"status"}}
    missing = sorted(required.keys() - rows.keys())
    if missing:
        blockers.append({"code": "SCHEMA_INVENTORY_INCOMPLETE", "tables": missing})
    for table, expected in required.items():
        if table in columns and expected - columns[table]:
            blockers.append({"code": "SCHEMA_INVENTORY_INCOMPLETE", "table": table,
                             "columns": sorted(expected - columns[table])})
            rows[table] = []
    routes = {r["route_id"]: r for r in rows.get("wf_unified_routes", [])}
    pins = set()
    active = []
    for row in rows.get("wf_workflows", []):
        workflow = object_value(row.get("payload")).get("workflow") or {}
        if row.get("state") == "closed" or workflow.get("route_id") not in routes:
            continue
        active.append(row["id"])
        snapshot = workflow.get("contract_snapshot") or {}
        if not snapshot:
            blockers.append({"code": "WORKFLOW_CONTRACT_NOT_PINNED", "workflow_id": row["id"]})
            continue
        canonical = {k: v for k, v in snapshot.items() if k != "sha256"}
        digest = hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
        if snapshot.get("format") != 1 or snapshot.get("sha256") != digest or not snapshot.get("route"):
            blockers.append({"code": "WORKFLOW_CONTRACT_CORRUPT", "workflow_id": row["id"]})
            continue
        route = snapshot["route"]
        for agent_id, binding in ((route.get("config") or {}).get("member_agents") or {}).items():
            version = binding.get("version")
            if not isinstance(version, int) or version < 1:
                blockers.append({"code": "AGENT_VERSION_NOT_PINNED", "workflow_id": row["id"], "agent_id": agent_id})
            else:
                pins.add((route["manager_account_id"], agent_id, version))
    if pins and storage is None:
        blockers.append({"code": "AGENT_STORAGE_NOT_CHECKED", "pins": len(pins)})
    if storage is not None:
        for owner, agent_id, version in sorted(pins):
            record = await storage.get_agent(owner, agent_id)
            if record is None or record.user_id != owner or not any(
                entry.get("version") == version for entry in record.data.versions
            ):
                blockers.append({"code": "PINNED_AGENT_UNAVAILABLE", "agent_id": agent_id, "version": version})
    quarantined = [r for r in rows.get("wf_unified_receipts", []) if r.get("ingestion_status") == "quarantined"]
    for receipt in quarantined:
        if not receipt.get("envelope"):
            blockers.append({"code": "QUARANTINE_ENVELOPE_MISSING", "receipt_id": receipt["receipt_id"]})
    return {
        "check": "p1_upgrade_data_inventory", "read_only": True,
        "schema_heads": [row["version_num"] for row in rows.get("alembic_version", [])],
        "active_unified_workflows": len(active), "agent_version_pins_checked": len(pins) if storage is not None else 0,
        "open_operations": sum(not r.get("terminal") for r in rows.get("wf_unified_operations", [])),
        "pending_approvals": sum(r.get("status") == "pending" for r in rows.get("wf_unified_approvals", [])),
        "quarantined_receipts": len(quarantined), "blockers": blockers,
        "data_preflight_pass": not blockers,
        "production_acceptance": "not_assessed",
        "still_required": ["reviewed_release_source", "verified_backup_and_rollback", "isolated_pair_smoke",
                           "domain_reconcile_reader", "model_and_human_business_acceptance"],
    }


async def run(args):
    from agentscope.app.storage import RedisStorage

    async with RedisStorage(host=os.environ["REDIS_HOST"], port=int(os.getenv("REDIS_PORT", "6379")),
                            db=int(os.getenv("REDIS_DB", "0")), password=os.getenv("REDIS_PASSWORD") or None) as storage:
        result = await inventory(os.environ["AGENTSCOPE_SQL_URL"], storage)
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(result, output, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["data_preflight_pass"] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        return asyncio.run(run(args))
    except Exception as exc:  # noqa: BLE001 - connection details and credentials must not enter the report
        print(f"P1 preflight could not complete: {type(exc).__name__}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
