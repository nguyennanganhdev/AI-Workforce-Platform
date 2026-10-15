"""Materialize a synthetic pilot in a new, explicitly marked, loopback sandbox only.

This is not an owner-data production publisher. Real owner handoffs stay staged.
The caller creates/migrates/bootstraps a NEW owner_pilot_test_<uuid> database,
and marks it with `COMMENT ON DATABASE ... IS 'vinhomes-synthetic-sandbox-v1'`.
Credentials are returned to the local caller, never printed by this module.
"""

import hashlib
import json
import re
import secrets
from datetime import datetime
from urllib.parse import urlsplit
from uuid import NAMESPACE_URL, UUID, uuid5

import asyncpg

from .bootstrap import DOMAIN, OP1
from .database import TENANT, _url
from .owner_operational import inspect
from .password_auth import password_hash

MARKER = "vinhomes-synthetic-sandbox-v1"
ADMIN = "sim-sandbox-admin"
CATEGORY = UUID("33333333-3333-5333-a333-333333333333")


def guard(url):
    parsed = urlsplit(_url(url))
    if parsed.hostname not in {"127.0.0.1", "localhost", "::1"} or not re.fullmatch(
        r"owner_pilot_test_[a-f0-9]{32}", parsed.path.lstrip("/")
    ):
        raise ValueError(
            "Synthetic activation requires a loopback owner_pilot_test database"
        )


def uid(kind, code):
    return uuid5(NAMESPACE_URL, f"vinhomes-synthetic-sandbox/{kind}/{code}")


def timestamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


async def materialize(url, folder, now=None):
    guard(url)  # Before connecting, even when the source bundle is invalid.
    report, rows, manifest = inspect(folder, now)
    if not report["valid"] or manifest.get("data_mode") != "synthetic_test":
        raise ValueError(
            "Only a complete synthetic_test pilot can be activated in sandbox"
        )
    tenant = UUID(TENANT)
    credentials = []
    conn = await asyncpg.connect(_url(url))
    try:
        async with conn.transaction():
            await conn.execute(
                "select pg_advisory_xact_lock(hashtextextended(current_database(),0))"
            )
            marker = await conn.fetchval(
                "select shobj_description(oid,'pg_database') from pg_database where datname=current_database()"
            )
            if marker != MARKER:
                raise ValueError("Database lacks the explicit synthetic sandbox marker")
            # Fresh-only avoids overlays on a historical test world or resetting passwords on reruns.
            for table in (
                "users",
                "units",
                "buildings",
                "zones",
                "management_units",
                "tickets",
                "staff_profiles",
                "domain_service_catalog",
                "owner_operational_batches",
            ):
                if await conn.fetchval("select count(*) from " + table):
                    raise ValueError(
                        "Sandbox materialization requires an empty operational database"
                    )
            await conn.execute("select set_config('app.tenant_id',$1,true)", TENANT)
            metadata = json.dumps(
                {
                    "data_mode": "synthetic_test",
                    "operational_verified": False,
                    "snapshot_sha256": report["snapshot_sha256"],
                    "manifest": manifest,
                }
            )
            scope = uid("scope", manifest["pilot"]["building_code"])
            zone = uid("zone", manifest["pilot"]["zone_code"])
            building = uid("building", manifest["pilot"]["building_code"])
            operator = uid("operator", rows["operators"][0]["operator_code"])

            async def account(user, email, name, role):
                password = secrets.token_urlsafe(24)
                await conn.execute(
                    "insert into users(id,email,name,status,email_verified) values($1,$2,$3,'active',true)",
                    user,
                    email,
                    name,
                )
                await conn.execute(
                    "insert into tenant_memberships(id,tenant_id,user_id,status,joined_at) values($1,$2,$3,'active',now())",
                    uid("membership", user),
                    tenant,
                    user,
                )
                await conn.execute(
                    "insert into accounts(id,account_id,provider_id,user_id,password) values($1,$2,'vinhomes-password-v1',$2,$3)",
                    str(uid("account", user)),
                    user,
                    password_hash(password),
                )
                credentials.append(
                    {
                        "user_id": user,
                        "email": email,
                        "password": password,
                        "role": role,
                        "data_mode": "synthetic_test",
                    }
                )

            await account(
                ADMIN, "admin@op1-sandbox.test", "[MÔ PHỎNG] Admin sandbox", "admin"
            )
            await conn.execute("insert into platform_admins(user_id) values($1)", ADMIN)
            await conn.execute(
                """insert into storage_locations(id,tenant_id,provider,endpoint_ref,bucket_name,tenant_prefix,
                    credential_secret_ref,versioning_required,encryption_mode,purpose,status)
                    values($1,$2,'local_fs','sandbox-private-disk','vinhomes-files','synthetic/',
                    'sandbox-no-external-credentials',false,'filesystem','evidence','active')""",
                uid("storage", "evidence"),
                tenant,
            )
            row = rows["operators"][0]
            await conn.execute(
                "insert into management_units(id,tenant_id,code,name,status,metadata) values($1,$2,$3,$4,'active',$5::jsonb)",
                operator,
                tenant,
                row["operator_code"],
                row["legal_name"],
                metadata,
            )
            row = rows["zones"][0]
            await conn.execute(
                "insert into zones(id,tenant_id,site_id,code,name,status,metadata) values($1,$2,$3,$4,$5,'active',$6::jsonb)",
                zone,
                tenant,
                OP1,
                row["zone_code"],
                row["name"],
                metadata,
            )
            row = rows["buildings"][0]
            await conn.execute(
                "insert into buildings(id,tenant_id,site_id,zone_id,code,name,status,metadata) values($1,$2,$3,$4,$5,$6,'active',$7::jsonb)",
                building,
                tenant,
                OP1,
                zone,
                row["building_code"],
                row["name"],
                metadata,
            )
            await conn.execute(
                "insert into access_scopes(id,tenant_id,kind,building_id) values($1,$2,'building',$3)",
                scope,
                tenant,
                building,
            )
            row = rows["coverage"][0]
            await conn.execute(
                "insert into management_coverage(id,tenant_id,management_unit_id,scope_id,service_category_id,valid_from,valid_to) values($1,$2,$3,$4,$5,$6,$7)",
                uid("coverage", row["platform_route_id"]),
                tenant,
                operator,
                scope,
                CATEGORY,
                timestamp(row["effective_from"]),
                timestamp(row["effective_until"]),
            )
            for row in rows["units"]:
                await conn.execute(
                    "insert into units(id,tenant_id,site_id,zone_id,building_id,code,unit_kind,status) values($1,$2,$3,$4,$5,$6,$7,'active')",
                    uid("unit", row["unit_code"]),
                    tenant,
                    OP1,
                    zone,
                    building,
                    row["unit_code"],
                    row["asset_type"],
                )
            for index, row in enumerate(rows["residents"], 1):
                user = row["account_code"]
                await account(user, row["email"], row["name"], "customer")
                if index > 99:
                    raise ValueError("Synthetic contact range exhausted")
                # Fictitious NANPA 555-0100..0199, never an invented Vietnamese subscriber.
                # https://www.nanpa.com/numbering/555-line-numbers
                await conn.execute(
                    "update users set phone_e164=$2,phone_verified_at=now() where id=$1",
                    user,
                    f"+1202555{100 + index:04d}",
                )
                await conn.execute(
                    "insert into scoped_user_roles(id,tenant_id,membership_id,scope_id,role_code,granted_by,valid_from,valid_to) values($1,$2,$3,$4,'customer',$5,$6,$7)",
                    uid("role", user),
                    tenant,
                    uid("membership", user),
                    scope,
                    ADMIN,
                    timestamp(row["valid_from"]),
                    timestamp(row["valid_until"]),
                )
                await conn.execute(
                    "insert into unit_residents(id,tenant_id,unit_id,user_id,relation,verification_status,valid_from,valid_to,verified_by,verified_at) values($1,$2,$3,$4,$5,'verified',$6,$7,$8,$6)",
                    uid("residency", user),
                    tenant,
                    uid("unit", row["unit_code"]),
                    user,
                    row["relation"],
                    timestamp(row["valid_from"]),
                    timestamp(row["valid_until"]),
                    ADMIN,
                )
            for row in rows["staff"]:
                user = row["employee_code"].lower()
                await account(user, row["email"], row["name"], "staff")
                staff = uid("staff", row["employee_code"])
                await conn.execute(
                    "insert into staff_profiles(id,tenant_id,user_id,management_unit_id,employee_code,availability,max_concurrent_jobs) values($1,$2,$3,$4,$5,'available',$6)",
                    staff,
                    tenant,
                    user,
                    operator,
                    row["employee_code"],
                    int(row["max_concurrent_jobs"]),
                )
                await conn.execute(
                    "insert into staff_specialties(tenant_id,staff_id,category_id,proficiency) values($1,$2,$3,'standard')",
                    tenant,
                    staff,
                    CATEGORY,
                )
                await conn.execute(
                    "insert into scoped_user_roles(id,tenant_id,membership_id,scope_id,role_code,granted_by,valid_from,valid_to) values($1,$2,$3,$4,'staff',$5,$6,$7)",
                    uid("role", user),
                    tenant,
                    uid("membership", user),
                    scope,
                    ADMIN,
                    timestamp(row["effective_from"]),
                    timestamp(row["effective_until"]),
                )
            for index, row in enumerate(rows["shifts"]):
                await conn.execute(
                    "insert into staff_shifts(id,tenant_id,staff_id,starts_at,ends_at,status) values($1,$2,$3,$4,$5,'available')",
                    uid("shift", str(index)),
                    tenant,
                    uid("staff", row["employee_code"]),
                    timestamp(row["starts_at"]),
                    timestamp(row["ends_at"]),
                )
            for row in rows["services"]:
                identifier = uid("service", row["service_code"])
                await conn.execute(
                    """insert into owner_data_records(id,tenant_id,site_id,dataset,proposal_code,title,source_hash,proposal,project_approval,operational_verified)
                    values($1,$2,$3,'services',$4,$5,$6,$7::jsonb,$8::jsonb,false)""",
                    identifier,
                    tenant,
                    OP1,
                    row["service_code"],
                    row["title"],
                    report["snapshot_sha256"],
                    json.dumps(row),
                    metadata,
                )
                await conn.execute(
                    "insert into domain_service_catalog(id,tenant_id,site_id,title,category_code,policy,operational_enabled) values($1,$2,$3,$4,'technical',$5::jsonb,true)",
                    identifier,
                    tenant,
                    OP1,
                    row["title"],
                    json.dumps({**row, "data_mode": "synthetic_test"}),
                )
            for row in rows["sops"]:
                document = uid("sop", row["sop_code"])
                body = "\n".join(
                    f"{key}: {value}"
                    for key, value in row.items()
                    if not key.startswith("_") and value
                )
                digest = hashlib.sha256(body.encode()).hexdigest()
                await conn.execute(
                    """insert into vh_knowledge_documents(id,tenant_id,code,version_id,title,category,audience,site_id,zone_id,building_ids,unverified,metadata)
                    values($1,$2,$3,$4,$5,'synthetic-sop',$6,$7,$8,$9,true,$10::jsonb)""",
                    document,
                    tenant,
                    row["sop_code"],
                    uuid5(document, digest),
                    row["title"],
                    row["audience"],
                    OP1,
                    zone,
                    [building],
                    metadata,
                )
                await conn.execute(
                    """insert into vh_knowledge_chunks(id,tenant_id,document_id,ordinal,heading_path,text_content,text_hash,token_count,search_tsv)
                    values($1,$2,$3,0,$4,$5,$6,$7,to_tsvector('simple',$5))""",
                    uuid5(document, "body"),
                    tenant,
                    document,
                    row["title"],
                    body,
                    digest,
                    len(body.split()),
                )
            # All three simulated services have the same category SLA. Do not silently pick
            # one if a future bundle supplies conflicting category policies.
            policies = {
                (
                    r["request_kind"],
                    r["priority"],
                    r["response_minutes"],
                    r["resolution_minutes"],
                    r["effective_from"],
                    r["effective_until"],
                )
                for r in rows["sops"]
            }
            seen = set()
            for kind, priority, response, resolution, start, end in policies:
                if (kind, priority) in seen:
                    raise ValueError("Conflicting sandbox category SLA policies")
                seen.add((kind, priority))
                await conn.execute(
                    """insert into sla_policies(id,tenant_id,management_unit_id,category_id,domain_id,request_kind,priority,response_minutes,resolution_minutes,effective_from,effective_to,version_no)
                    values($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,1)""",
                    uid("sla", kind + priority),
                    tenant,
                    operator,
                    CATEGORY,
                    DOMAIN,
                    kind,
                    priority,
                    int(response),
                    int(resolution),
                    timestamp(start),
                    timestamp(end),
                )
            # Store the private source snapshot in the SAME transaction as runtime rows.
            batch = uid("snapshot", report["snapshot_sha256"])
            await conn.execute(
                """insert into owner_operational_batches(id,tenant_id,bundle_code,version,snapshot_sha256,manifest,counts,staged_by)
                values($1,$2,$3,$4,$5,$6::jsonb,$7::jsonb,$8)""",
                batch,
                tenant,
                manifest["bundle_code"],
                manifest["version"],
                report["snapshot_sha256"],
                json.dumps(manifest),
                json.dumps(report["counts"]),
                ADMIN,
            )
            await conn.executemany(
                "insert into owner_operational_records(tenant_id,batch_id,dataset,ordinal,data) values($1,$2,$3,$4,$5::jsonb)",
                [
                    (
                        tenant,
                        batch,
                        table,
                        index,
                        json.dumps({k: v for k, v in row.items() if k != "_label"}),
                    )
                    for table, records in rows.items()
                    for index, row in enumerate(records, 1)
                ],
            )
        return {
            "report": {
                **report,
                "database_written": True,
                "sandbox_runtime_activation": True,
                "operational_activation": False,
                "production_changed": False,
            },
            "credentials": credentials,
        }
    finally:
        await conn.close()
