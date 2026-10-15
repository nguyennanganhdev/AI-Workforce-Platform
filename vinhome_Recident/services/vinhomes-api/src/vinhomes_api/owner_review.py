"""Import the project-approved proposal snapshot without inventing operational master facts or identities."""

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

import asyncpg

from .database import TENANT, _url


async def load(url, folder, approval_path):
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    if approval.get("approval_kind") != "project_scope" or not approval.get(
        "user_statement"
    ):
        raise ValueError("Explicit project approval record required")
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    raw = (folder / "proposals.jsonl").read_bytes()
    if approval.get("proposal_snapshot_sha256") != hashlib.sha256(raw).hexdigest():
        raise ValueError("Approval is not bound to this proposal snapshot")
    for name, expected in manifest["files"].items():
        file = (folder / name).resolve()
        if (
            not file.is_relative_to(folder.resolve())
            or hashlib.sha256(file.read_bytes()).hexdigest() != expected
        ):
            raise ValueError("Proposal file integrity check failed")
    if hashlib.sha256(raw).hexdigest() != manifest["files"]["proposals.jsonl"]:
        raise ValueError("Proposal snapshot hash does not match manifest")
    records = [json.loads(line) for line in raw.decode().splitlines()]
    if len(records) != manifest["total_proposals"] or len(
        {row["proposal_id"] for row in records}
    ) != len(records):
        raise ValueError("Proposal count/identifiers invalid")
    tenant = UUID(TENANT)
    conn = await asyncpg.connect(_url(url))
    try:
        async with conn.transaction():
            await conn.execute("select set_config('app.tenant_id',$1,true)", TENANT)
            sites = {
                row["code"]: row["id"]
                for row in await conn.fetch(
                    "select code,id from sites where tenant_id=$1", tenant
                )
            }
            if any(row["site_code"] not in sites for row in records):
                raise ValueError("All proposal sites must already exist")
            for row in records:
                content = json.dumps(row, ensure_ascii=False, sort_keys=True)
                digest = hashlib.sha256(content.encode()).hexdigest()
                old = await conn.fetchval(
                    "select source_hash from owner_data_records where id=$1",
                    UUID(row["proposal_id"]),
                )
                if old is not None and old != digest:
                    raise ValueError(
                        "Existing proposal has different content; use a new reviewed version"
                    )
                await conn.execute(
                    """insert into owner_data_records(id,tenant_id,site_id,dataset,proposal_code,title,source_hash,proposal,project_approval)
                    values($1,$2,$3,$4,$5,$6,$7,$8::jsonb,$9::jsonb) on conflict(id) do nothing""",
                    UUID(row["proposal_id"]),
                    tenant,
                    sites[row["site_code"]],
                    row["dataset"],
                    row["proposal_code"],
                    row["title"],
                    digest,
                    content,
                    json.dumps(approval, ensure_ascii=False),
                )
                if row["dataset"] == "services":
                    await conn.execute(
                        """insert into domain_service_catalog(id,tenant_id,site_id,title,category_code,policy)
                        values($1,$2,$3,$4,$5,$6::jsonb) on conflict(id) do nothing""",
                        UUID(row["proposal_id"]),
                        tenant,
                        sites[row["site_code"]],
                        row["title"],
                        row["data"]["category_code"],
                        json.dumps(row["data"], ensure_ascii=False),
                    )
                if row["basis"].startswith("public_"):
                    await conn.execute(
                        """update vh_knowledge_documents set metadata=metadata || $3::jsonb
                        where tenant_id=$1 and code=$2""",
                        tenant,
                        "public/" + row["site_code"] + "/" + row["proposal_code"],
                        json.dumps({"project_approval": approval}, ensure_ascii=False),
                    )
            zones = {}
            for row in records:
                if (
                    row["dataset"] != "geography"
                    or row["data"]["kind"] != "subdivision"
                ):
                    continue
                identifier = uuid5(
                    NAMESPACE_URL, "vinhomes-owner-master/" + row["proposal_id"]
                )
                code = "ref-" + row["proposal_code"].split("/", 1)[1]
                metadata = {
                    "code_kind": "internal_reference",
                    "sources": row["sources"],
                    "project_approval": approval,
                    "operational_confirmation": "pending",
                    "proposal_id": row["proposal_id"],
                }
                await conn.execute(
                    """insert into zones(id,tenant_id,site_id,code,name,status,metadata)
                    values($1,$2,$3,$4,$5,'inactive',$6::jsonb) on conflict(id) do nothing""",
                    identifier,
                    tenant,
                    sites[row["site_code"]],
                    code,
                    row["title"],
                    json.dumps(metadata, ensure_ascii=False),
                )
                zones[(row["site_code"], row["title"])] = identifier
            for row in records:
                if row["dataset"] != "geography" or row["data"]["kind"] != "building":
                    continue
                zone = zones.get((row["site_code"], row["data"]["public_parent_name"]))
                if zone is None or not row["data"]["official_code"]:
                    raise ValueError(
                        "Building needs a sourced parent and explicit public building code"
                    )
                metadata = {
                    "code_kind": "public_source",
                    "sources": row["sources"],
                    "project_approval": approval,
                    "operational_confirmation": "pending",
                    "proposal_id": row["proposal_id"],
                }
                await conn.execute(
                    """insert into buildings(id,tenant_id,site_id,zone_id,code,name,status,metadata)
                    values($1,$2,$3,$4,$5,$6,'inactive',$7::jsonb) on conflict(id) do nothing""",
                    uuid5(NAMESPACE_URL, "vinhomes-owner-master/" + row["proposal_id"]),
                    tenant,
                    sites[row["site_code"]],
                    zone,
                    row["data"]["official_code"],
                    row["title"],
                    json.dumps(metadata, ensure_ascii=False),
                )
        return {
            "project_approved_records": len(records),
            "geography_zones": len(zones),
            "geography_buildings": sum(
                row["dataset"] == "geography" and row["data"]["kind"] == "building"
                for row in records
            ),
            "operational_activation": False,
            "users_created": 0,
            "staff_created": 0,
        }
    finally:
        await conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folder", type=Path, required=True)
    parser.add_argument("--approval", type=Path, required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            asyncio.run(load(os.environ["DATABASE_URL"], args.folder, args.approval))
        )
    )
