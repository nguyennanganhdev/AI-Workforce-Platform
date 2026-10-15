"""Bounded OP2 simulation expansion. Never certifies operator data or overwrites live rows."""

import argparse
import asyncio
from collections import deque
from datetime import UTC, datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
from urllib.parse import urlsplit
from uuid import NAMESPACE_URL, uuid5

import asyncpg

from .bootstrap import site_id
from .database import TENANT, _url
from .password_auth import password_hash

PROFILE = "op2-simulation-v1"
OPERATOR = "SIM-OP2-OPERATOR"
TABLES = """management_units zones buildings access_scopes zone_settings users accounts
tenant_memberships units scoped_user_roles unit_residents staff_profiles staff_specialties
staff_shifts management_coverage sla_policies owner_data_records domain_service_catalog
vehicles access_cards visitor_passes debit_notes debit_note_lines amenities amenity_bookings
construction_policies construction_permits service_requests vh_knowledge_documents vh_knowledge_chunks""".split()
SHARED = set("""management_units zones access_scopes zone_settings management_coverage
sla_policies owner_data_records domain_service_catalog amenities construction_policies
vh_knowledge_documents vh_knowledge_chunks""".split())


def uid(value):
    return str(uuid5(NAMESPACE_URL, PROFILE + "/" + value))


def build(template, admin, now=None):
    """Generate fresh credentials privately; the checked-in template contains no hashes/tokens."""
    now = now or datetime.now(UTC)
    if template.get("data_mode") != "synthetic_test" or set(template["tables"]) != set(TABLES):
        raise ValueError("Only the sanitized OP2 simulation template is accepted")
    source = template["tables"]
    op1 = template["source_site"]
    source_admin = template["source_admin"]
    op2 = str(site_id("ocean-park-2"))
    common = {op1: op2, source_admin: admin}
    for table in SHARED:
        for row in source[table]:
            if row.get("id"):
                common[str(row["id"])] = uid(table + "/" + str(row["id"]))
    result = {table: [] for table in TABLES}
    credentials = []
    zone_scope = common[source["access_scopes"][0]["id"]]
    zone = common[source["zones"][0]["id"]]
    buildings = [uid(f"{cohort}/buildings/" + source["buildings"][0]["id"]) for cohort in range(1, 4)]
    anchor = datetime.fromisoformat(template["anchor"])
    delta = now - anchor

    for cohort in range(1, 4):
        mapping = dict(common)
        for table in TABLES:
            for row in source[table]:
                if row.get("id") and str(row["id"]) not in mapping:
                    mapping[str(row["id"])] = uid(f"{cohort}/{table}/" + str(row["id"]))
        for row in source["users"]:
            mapping[row["id"]] = f"sim-op2-{cohort}-" + row["id"].removeprefix("sim-")

        def transform(value):
            if isinstance(value, list):
                return [transform(item) for item in value]
            if isinstance(value, dict):
                return {key: transform(item) for key, item in value.items()}
            if not isinstance(value, str):
                return value
            if value in mapping:
                return mapping[value]
            if value.startswith("SIM-") and " " not in value:
                return value.replace("SIM-", f"SIM-OP2-{cohort}-", 1)
            if value.startswith("sim-") and " " not in value:
                return f"sim-op2-{cohort}-" + value[4:]
            if re.fullmatch(r"[0-9a-f-]{36}", value):
                # Natural FK identifiers shared by the domain (tenant/domain/category) remain unchanged.
                if value in template["shared_ids"]:
                    return value
                return uid(f"{cohort}/reference/" + value)
            if re.match(r"\d{4}-\d\d-\d\dT", value):
                return (datetime.fromisoformat(value.replace("Z", "+00:00")) + delta).isoformat()
            return value.replace("ocean-park-1", "ocean-park-2").replace("OP1", "OP2").replace("op1-sandbox.test", "op2-sandbox.test")

        for table in TABLES:
            if table == "staff_shifts" or (cohort > 1 and table in SHARED):
                continue
            for original in source[table]:
                row = transform(original)
                row["tenant_id"] = TENANT if "tenant_id" in row else row.get("tenant_id")
                if "tenant_id" not in original:
                    row.pop("tenant_id", None)
                if table == "users":
                    stem = original["email"].split("@", 1)[0]
                    row["email"] = f"{stem}.c{cohort}@op2-sandbox.test"
                    row["name"] = f"[MÔ PHỎNG OP2] {stem} ca/nhóm {cohort}"
                    row["phone_e164"] = f"+1202555{120 + (cohort - 1) * 2 + int(stem[-1]):04d}" if stem.startswith("resident") else None
                elif table == "accounts":
                    password = secrets.token_urlsafe(24)
                    row["password"] = password_hash(password)
                    row["account_id"] = row["user_id"]
                    original_user = next(u for u in source["users"] if u["id"] == original["user_id"])
                    stem = original_user["email"].split("@", 1)[0]
                    credentials.append({"user_id": row["user_id"], "email": f"{stem}.c{cohort}@op2-sandbox.test", "password": password,
                                        "role": "customer" if stem.startswith("resident") else "staff", "data_mode": "synthetic_test"})
                elif table == "management_units":
                    row.update(code=OPERATOR, name="[MÔ PHỎNG] Đơn vị OP2", contact_email=None, contact_phone=None)
                elif table == "zones":
                    row.update(code="SIM-OP2-ZONE", name="[MÔ PHỎNG OP2] Khu nghiệm thu")
                elif table == "buildings":
                    row.update(code=f"SIM-OP2-TOWER-{cohort}", name=f"[MÔ PHỎNG OP2] Tòa {cohort}")
                elif table == "access_scopes":
                    row.update(kind="zone", zone_id=zone, building_id=None, site_id=None, management_unit_id=None)
                elif table in {"scoped_user_roles", "management_coverage"}:
                    row["scope_id"] = zone_scope
                    if row.get("role_code") not in {None, "customer", "staff"}:
                        raise ValueError("Simulation must not create elevated roles")
                elif table == "vh_knowledge_documents":
                    row["building_ids"] = buildings
                    row["metadata"] = {**row["metadata"], "data_mode": "synthetic_test", "profile": PROFILE, "operational_verified": False}
                    row["unverified"] = True
                    row["code"] = PROFILE + "/" + original["code"]
                elif table == "vh_knowledge_chunks":
                    row["text_content"] = "MÔ PHỎNG OP2, không phải chính sách Vinhomes đã xác nhận. " + row["text_content"]
                    row["text_hash"] = hashlib.sha256(row["text_content"].encode()).hexdigest()
                    row["search_tsv"] = ""  # Filled with to_tsvector by the importer.
                    row["embedding"] = None
                elif table in {"domain_service_catalog", "owner_data_records"}:
                    key = "policy" if table == "domain_service_catalog" else "proposal"
                    row[key].update(data_mode="synthetic_test", profile=PROFILE, site_code="ocean-park-2", zone_code="SIM-OP2-ZONE",
                                    building_code="", eligibility="Chỉ 6 căn OP2 mô phỏng có cư trú hiệu lực", operating_hours="3 ca mô phỏng, phủ 24 giờ; không phải giờ phục vụ chính thức")
                    row[key]["operator_code"] = OPERATOR
                    row[key]["service_code"] = "OP2-" + original[key]["service_code"]
                    if table == "owner_data_records":
                        row["proposal_code"] = row[key]["service_code"]
                        row["source_hash"] = hashlib.sha256(json.dumps(row[key], sort_keys=True).encode()).hexdigest()
                        row["operational_verified"] = False
                        row["project_approval"] = {"data_mode": "synthetic_test", "operator_approval": False, "profile": PROFILE}
                if table in {"zones", "buildings", "management_units"}:
                    row["metadata"] = {"data_mode": "synthetic_test", "profile": PROFILE, "operator_approval": False}
                if table == "amenity_bookings":
                    for date_key in ("start_at", "end_at"):
                        row[date_key] = (datetime.fromisoformat(row[date_key]) + timedelta(days=2 * (cohort - 1))).isoformat()
                result[table].append(row)

        start_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        for staff in source["staff_profiles"]:
            for day in range(14):
                start = start_day + timedelta(days=day, hours=8 * (cohort - 1))
                result["staff_shifts"].append({"id": uid(f"shift/{cohort}/{staff['id']}/{start.date()}"), "tenant_id": TENANT,
                    "staff_id": mapping[staff["id"]], "starts_at": start.isoformat(), "ends_at": (start + timedelta(hours=8)).isoformat(), "status": "available"})
    return {"data_mode": "synthetic_test", "profile": PROFILE, "site_code": "ocean-park-2", "category_codes": template["category_codes"], "tables": result}, credentials


def transition_path(transitions, entity, target):
    queue = deque([("", [])])
    seen = set()
    while queue:
        previous, path = queue.popleft()
        if previous == target:
            return path
        if previous in seen:
            continue
        seen.add(previous)
        queue.extend((r["to_status"], path + [r["to_status"]]) for r in transitions if r["entity"] == entity and r["from_status"] == previous)
    raise ValueError(f"No legal initial-state path: {entity}/{target}")


async def apply(url, bundle):
    if bundle.get("profile") != PROFILE or bundle.get("data_mode") != "synthetic_test" or set(bundle["tables"]) != set(TABLES):
        raise ValueError("Invalid OP2 simulation bundle")
    name = urlsplit(_url(url)).path.lstrip("/")
    if not re.fullmatch(r"(?:vinhomes_release_20261015_[a-f0-9]{8}|op2_expansion_test_[a-f0-9]{32})", name):
        raise ValueError("Refusing an unrelated database")
    conn = await asyncpg.connect(_url(url))
    counts = {}
    try:
        async with conn.transaction():
            marker = await conn.fetchval("select shobj_description(oid,'pg_database') from pg_database where datname=current_database()")
            if marker != "vinhomes-synthetic-sandbox-v1":
                raise ValueError("Target is not explicitly marked as simulated")
            await conn.execute("select pg_advisory_xact_lock(hashtextextended($1,0))", PROFILE)
            await conn.execute("select set_config('app.tenant_id',$1,true)", TENANT)
            category_map = {}
            for source_id, code in bundle["category_codes"].items():
                target_id = await conn.fetchval("select id from service_categories where tenant_id=$1::uuid and code=$2", TENANT, code)
                if target_id is None:
                    raise ValueError("Missing target service category: " + code)
                category_map[source_id] = str(target_id)
            transitions = await conn.fetch("select * from state_transitions")
            guarded = {r["name"] for r in await conn.fetch("select tgrelid::regclass::text name from pg_trigger where tgfoid='app_enforce_transition'::regproc and not tgisinternal")}
            pending = []
            for table in TABLES:
                inserted = 0
                allowed_columns = {r["column_name"] for r in await conn.fetch("select column_name from information_schema.columns where table_schema='public' and table_name=$1", table)}
                primary = await conn.fetchval("select array(select attname from pg_attribute where attrelid=conrelid and attnum=any(conkey) order by attnum) from pg_constraint where contype='p' and conrelid=$1::regclass", table)
                conflict = ','.join('"' + column + '"' for column in primary)
                for original in bundle["tables"][table]:
                    row = dict(original)
                    for column in ("category_id", "service_category_id"):
                        if row.get(column) in category_map:
                            row[column] = category_map[row[column]]
                    if not set(row) <= allowed_columns:
                        raise ValueError("Unknown columns in " + table)
                    if row.get("tenant_id", TENANT) != TENANT:
                        raise ValueError("Cross-tenant row")
                    if table == "users" and (not row["id"].startswith("sim-op2-") or not row["email"].endswith("@op2-sandbox.test")):
                        raise ValueError("Non-synthetic identity")
                    if table == "scoped_user_roles" and row["role_code"] not in {"staff", "customer"}:
                        raise ValueError("Elevated simulation role")
                    if row.get("id") and await conn.fetchval(f'select exists(select 1 from "{table}" where id::text=$1)', str(row["id"])):
                        continue
                    path = transition_path(transitions, table, row["status"]) if table in guarded else []
                    if path:
                        row["status"] = path[0]
                    columns = list(row)
                    quoted = ','.join('"' + c + '"' for c in columns)
                    made = await conn.fetchval(f'insert into "{table}" ({quoted}) select {quoted} from json_populate_record(null::"{table}",$1::json) on conflict ({conflict}) do nothing returning 1', json.dumps(row, ensure_ascii=False))
                    if made:
                        inserted += 1
                        if len(path) > 1:
                            pending.append((table, row["id"], path[1:]))
                        if table == "vh_knowledge_chunks":
                            await conn.execute("update vh_knowledge_chunks set search_tsv=to_tsvector('simple',text_content) where id::text=$1", row["id"])
                counts[table] = inserted
            for table, identifier, path in pending:
                for status in path:
                    await conn.execute(f'update "{table}" set status=$1 where id::text=$2', status, identifier)
        return {"profile": PROFILE, "inserted": counts, "total_inserted": sum(counts.values()), "agent_calls": 0}
    finally:
        await conn.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--allow-runtime-simulation", action="store_true")
    args = parser.parse_args()
    if not args.allow_runtime_simulation:
        parser.error("Explicit --allow-runtime-simulation is required")
    print(json.dumps(asyncio.run(apply(os.environ["DATABASE_URL"], json.loads(args.bundle.read_text(encoding="utf-8"))))))


if __name__ == "__main__":
    main()
