"""Loads the data the domain owner supplies: buildings, homes, people, staff, cards, statements and knowledge.

    python -m vinhomes_api.database import --url URL --dir DIR [--dry-run]

One CSV (UTF-8, header row) or JSON (list of objects) file per kind, named as below. Rows refer to each other by code,
never by id. A file may be left out. The whole load is one transaction: any bad row (unknown code, wrong value) is
reported with its file and line and nothing is written; `--dry-run` reports and never writes. Running the same files
again adds nothing. It adds rows; it does not change rows that already exist. See docs/domain/NAP_DU_LIEU.md.
"""

import csv
import json
from datetime import date, datetime, time
from pathlib import Path

import asyncpg

from .mock_data import CAT_SEC, CAT_TECH, DOMAIN, MANAGEMENT, SITE, TENANT, uid

ORDER = ["buildings", "units", "zone_settings", "residents", "staff", "shifts", "vehicles", "cards", "debit_notes", "debit_note_lines",
         "amenities", "handbook", "policies", "announcements"]
# The rules a zone may set (table zone_settings): whole numbers, except the purposes of visits that need no approval.
ZONE_NUMBERS = ["visit_max_waiting", "visit_max_days_ahead", "visit_max_hours", "visit_auto_approve_max_guests", "visit_early_minutes",
                "card_limit_resident", "card_limit_vehicle", "amenity_payment_hold_minutes"]
CATEGORY = {"technical": CAT_TECH, "security": CAT_SEC}
PATHS = {
    "paid": ["issued", "paid"], "partially_paid": ["issued", "partially_paid"], "overdue": ["issued", "overdue"],
    "issued": ["issued"], "draft": [], "cancelled": ["cancelled"],
}
CARD_PATHS = {"active": ["active"], "pending_issue": [], "lost": ["active", "lost"], "suspended": ["active", "suspended"],
              "expired": ["active", "expired"], "revoked": ["active", "revoked"]}


class BadRow(Exception):
    pass


def read(path: Path) -> list[dict]:
    if path.suffix == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return [{k.strip(): (v.strip() if isinstance(v, str) else v) for k, v in row.items()} for row in csv.DictReader(handle)]


def find(folder: Path, kind: str) -> Path | None:
    return next((p for p in (folder / f"{kind}.csv", folder / f"{kind}.json") if p.is_file()), None)


class Loader:
    def __init__(self, conn):
        self.c = conn
        self.cache: dict[tuple, object] = {}
        self.added: dict[str, int] = {}

    def count(self, kind: str):
        self.added[kind] = self.added.get(kind, 0) + 1

    async def one(self, what: str, sql: str, *args):
        key = (what, args)
        if key not in self.cache:
            value = await self.c.fetchval(sql, *args)
            if value is None:
                raise BadRow(f"{what} {args[-1]!r} does not exist")
            self.cache[key] = value
        return self.cache[key]

    def need(self, row: dict, *names: str) -> list[str]:
        missing = [n for n in names if not str(row.get(n) or "").strip()]
        if missing:
            raise BadRow("missing " + ", ".join(missing))
        return [str(row[n]).strip() for n in names]

    def day(self, text_: str | None) -> date | None:
        return date.fromisoformat(text_) if text_ else None

    def stamp(self, text_: str | None) -> datetime | None:
        if not text_:
            return None
        value = datetime.fromisoformat(text_)
        if value.tzinfo is None:
            raise BadRow(f"{text_!r} needs a time zone, for example +07:00")
        return value

    # ---- one method per file ----

    async def buildings(self, row):
        code, name, zone = self.need(row, "code", "name", "zone_code")
        zone_id = await self.one("zone", "select id from zones where site_id=$1 and code=$2", SITE, zone)
        building = uid("import", "building", code)
        await self.c.execute("insert into buildings(id,tenant_id,site_id,zone_id,code,name,status) values($1,$2,$3,$4,$5,$6,'active') on conflict do nothing", building, TENANT, SITE, zone_id, code, name)
        scope = await self.c.fetchval("select id from access_scopes where kind='building' and building_id=(select id from buildings where site_id=$1 and code=$2) and tenant_id=$3 limit 1", SITE, code, TENANT)
        real = await self.c.fetchval("select id from buildings where site_id=$1 and code=$2", SITE, code)
        if scope is None:
            scope = uid("import", "scope", code)
            await self.c.execute("insert into access_scopes(id,tenant_id,kind,building_id) values($1,$2,'building',$3) on conflict do nothing", scope, TENANT, real)
        for category in (CAT_TECH, CAT_SEC):
            if not await self.c.fetchval("select 1 from management_coverage where scope_id=$1 and service_category_id=$2 and valid_to is null", scope, category):
                await self.c.execute("insert into management_coverage(id,tenant_id,management_unit_id,scope_id,service_category_id,valid_from) values($1,$2,$3,$4,$5,now()) on conflict do nothing", uid("import", "coverage", code, category), TENANT, MANAGEMENT, scope, category)
        self.count("buildings")

    async def units(self, row):
        code, building, kind = self.need(row, "code", "building_code", "unit_kind")
        if kind not in ("apartment", "townhouse", "villa", "other"):
            raise BadRow(f"unit_kind {kind!r} must be apartment, townhouse, villa or other")
        b = await self.c.fetchrow("select id,zone_id from buildings where site_id=$1 and code=$2", SITE, building)
        if b is None:
            raise BadRow(f"building {building!r} does not exist")
        await self.c.execute("insert into units(id,tenant_id,site_id,zone_id,building_id,code,unit_kind,floor,status) values($1,$2,$3,$4,$5,$6,$7,$8,'active') on conflict do nothing",
                             uid("import", "unit", code), TENANT, SITE, b["zone_id"], b["id"], code, kind, row.get("floor") or None)
        self.count("units")

    async def person(self, name: str, phone: str | None, email: str | None, user_id: str | None) -> str:
        user = user_id or "imp-" + (phone or email or name).lower().replace(" ", "")
        await self.c.execute("insert into users(id,email,name,status,phone_e164) values($1,$2,$3,'active',$4) on conflict(id) do nothing", user, email or f"{user}@example.invalid", name, ("+84" + phone.lstrip("0")) if phone else None)
        await self.c.execute("insert into tenant_memberships(id,tenant_id,user_id,status,joined_at) values($1,$2,$3,'active',now()) on conflict(id) do nothing", uid("membership", user), TENANT, user)
        return user

    async def residents(self, row):
        name, unit, relation = self.need(row, "name", "unit_code", "relation")
        status = row.get("status") or "verified"
        if relation not in ("owner", "tenant", "household") or status not in ("verified", "pending"):
            raise BadRow("relation must be owner, tenant or household; status verified or pending")
        unit_id = await self.one("unit", "select id from units where tenant_id=$1 and code=$2", TENANT, unit)
        user = await self.person(name, row.get("phone"), row.get("email"), row.get("user_id"))
        await self.c.execute("""insert into unit_residents(id,tenant_id,unit_id,user_id,relation,verification_status,valid_from,verified_by,verified_at)
            values($1,$2,$3,$4,$5,$6,coalesce($7::timestamptz,now()),$8,$9) on conflict(id) do nothing""",
                             uid("import", "link", user, unit, relation), TENANT, unit_id, user, relation, status, self.stamp(row.get("valid_from")),
                             "local-v3-admin" if status == "verified" else None, datetime.now().astimezone() if status == "verified" else None)
        self.count("residents")

    async def staff(self, row):
        code, name, role = self.need(row, "employee_code", "name", "role")
        if role not in ("staff", "management"):
            raise BadRow("role must be staff or management")
        specialties = [s for s in (row.get("specialties") or "").split("|") if s]
        if any(s not in CATEGORY for s in specialties):
            raise BadRow("specialties are technical and/or security, separated by |")
        user = await self.person(name, row.get("phone"), row.get("email"), row.get("user_id"))
        staff_id = uid("import", "staff", code)
        await self.c.execute("insert into staff_profiles(id,tenant_id,user_id,management_unit_id,employee_code,availability,max_concurrent_jobs) values($1,$2,$3,$4,$5,$6,3) on conflict do nothing",
                             staff_id, TENANT, user, MANAGEMENT, code, row.get("availability") or "available")
        for s in specialties:
            await self.c.execute("insert into staff_specialties(tenant_id,staff_id,category_id,proficiency) values($1,$2,$3,'standard') on conflict do nothing", TENANT, staff_id, CATEGORY[s])
        scopes = await self.c.fetch("select id from access_scopes where tenant_id=$1 and kind='building'", TENANT)
        for scope in scopes:
            await self.c.execute("insert into scoped_user_roles(id,tenant_id,membership_id,scope_id,role_code,granted_by,valid_from) values($1,$2,$3,$4,$5,'local-v3-admin',now()) on conflict(id) do nothing",
                                 uid("import", "role", user, scope["id"], role), TENANT, uid("membership", user), scope["id"], role)
        self.count("staff")

    async def shifts(self, row):
        code, start, end = self.need(row, "employee_code", "starts_at", "ends_at")
        staff_id = await self.one("staff", "select id from staff_profiles where tenant_id=$1 and employee_code=$2", TENANT, code)
        await self.c.execute("insert into staff_shifts(id,tenant_id,staff_id,starts_at,ends_at,status) values($1,$2,$3,$4,$5,'available') on conflict(id) do nothing",
                             uid("import", "shift", code, start), TENANT, staff_id, self.stamp(start), self.stamp(end))
        self.count("shifts")

    async def vehicles(self, row):
        unit, kind, plate, owner = self.need(row, "unit_code", "kind", "plate_no", "owner_name")
        if kind not in ("car", "electric_car", "motorbike", "electric_motorbike", "bicycle"):
            raise BadRow(f"kind {kind!r} is not a vehicle kind")
        unit_id = await self.one("unit", "select id from units where tenant_id=$1 and code=$2", TENANT, unit)
        await self.c.execute("insert into vehicles(id,tenant_id,unit_id,owner_name,kind,plate_no,status) values($1,$2,$3,$4,$5,$6,'active') on conflict do nothing", uid("import", "vehicle", plate), TENANT, unit_id, owner, kind, plate)
        self.count("vehicles")

    async def cards(self, row):
        number, kind, unit = self.need(row, "card_no", "kind", "unit_code")
        status = row.get("status") or "active"
        if status not in CARD_PATHS or kind not in ("resident", "vehicle", "temporary", "worker", "staff"):
            raise BadRow("unknown card status or kind")
        unit_id = await self.one("unit", "select id from units where tenant_id=$1 and code=$2", TENANT, unit)
        vehicle = None
        if row.get("plate_no"):
            vehicle = await self.one("vehicle", "select id from vehicles where tenant_id=$1 and plate_no=$2 and status='active'", TENANT, row["plate_no"])
        card = uid("import", "card", number)
        await self.c.execute("insert into access_cards(id,tenant_id,card_no,kind,holder_name,unit_id,vehicle_id,status,valid_from,valid_to,monthly_fee) values($1,$2,$3,$4,$5,$6,$7,'pending_issue',$8,$9,$10) on conflict do nothing",
                             card, TENANT, number, kind, row.get("holder_name") or None, unit_id, vehicle, self.day(row.get("valid_from")), self.day(row.get("valid_to")),
                             int(row["monthly_fee"]) if row.get("monthly_fee") else None)
        previous = "pending_issue"
        for step in CARD_PATHS[status]:
            await self.c.execute("update access_cards set status=$2 where id=$1 and status=$3", card, step, previous)
            previous = step
        self.count("cards")

    async def debit_notes(self, row):
        doc, unit, issue, due = self.need(row, "doc_no", "unit_code", "issue_date", "due_date")
        status = row.get("status") or "issued"
        if status not in PATHS:
            raise BadRow(f"status {status!r} is not a statement status")
        unit_id = await self.one("unit", "select id from units where tenant_id=$1 and code=$2", TENANT, unit)
        subtotal, vat = int(row.get("subtotal") or 0), int(row.get("vat_amount") or 0)
        await self.c.execute("""insert into debit_notes(id,tenant_id,doc_no,unit_id,period_month,kind,issue_date,due_date,subtotal,vat_amount,total_amount,status)
            values($1,$2,$3,$4,$5,'monthly',$6,$7,$8,$9,$10,'draft') on conflict do nothing""",
                             uid("import", "note", doc), TENANT, doc, unit_id, self.day(row.get("period_month")), self.day(issue), self.day(due), subtotal, vat, subtotal + vat)
        self.pending_notes[doc] = (status, int(row.get("paid_amount") or 0))
        self.count("debit_notes")

    async def debit_note_lines(self, row):
        doc, number, kind, description, amount = self.need(row, "doc_no", "line_no", "fee_kind", "description", "amount")
        note = uid("import", "note", doc)
        if not await self.c.fetchval("select 1 from debit_notes where id=$1", note):
            raise BadRow(f"debit note {doc!r} does not exist")
        await self.c.execute("insert into debit_note_lines(id,tenant_id,debit_note_id,line_no,fee_kind,description,quantity,unit_price,amount) values($1,$2,$3,$4,$5,$6,$7,$8,$9) on conflict do nothing",
                             uid("import", "line", doc, number), TENANT, note, int(number), kind, description, row.get("quantity") or 1, int(row.get("unit_price") or amount), int(amount))
        self.count("debit_note_lines")

    async def settle_notes(self):
        """Statements move on once their lines are in: draft to issued, then to what they are."""
        for doc, (status, paid) in self.pending_notes.items():
            note = uid("import", "note", doc)
            previous = "draft"
            for step in PATHS[status]:
                extra = ""
                if step == "paid":
                    extra = ",paid_amount=total_amount"
                elif step == "partially_paid":
                    extra = f",paid_amount={paid or 0}"
                await self.c.execute(f"update debit_notes set status=$2{extra} where id=$1 and status=$3", note, step, previous)
                previous = step

    async def zone_settings(self, row):
        """The row replaces the zone's rules (the whole tenant's when zone_code is empty); an empty cell inherits."""
        zone = await self.one("zone", "select id from zones where site_id=$1 and code=$2", SITE, row["zone_code"]) if row.get("zone_code") else None
        numbers = {name: int(row[name]) if str(row.get(name) or "").strip() else None for name in ZONE_NUMBERS}
        purposes = [p for p in (row.get("visit_auto_approve_purposes") or "").split("|") if p] or None
        values = {**numbers, "visit_auto_approve_purposes": purposes, "note": row.get("note") or None}
        columns = list(values)
        existing = await self.c.fetchval("select id from zone_settings where tenant_id=$1 and zone_id is not distinct from $2::uuid", TENANT, zone)
        if existing is None:
            await self.c.execute(f"insert into zone_settings(tenant_id,zone_id,{','.join(columns)}) values($1,$2,{','.join(f'${i + 3}' for i in range(len(columns)))})",
                                 TENANT, zone, *values.values())
            self.count("zone_settings")
        else:
            changed = await self.c.fetchval(f"""update zone_settings set {','.join(f'{c}=${i + 2}' for i, c in enumerate(columns))}
                where id=$1 and ({' or '.join(f'{c} is distinct from ${i + 2}' for i, c in enumerate(columns))}) returning 1""", existing, *values.values())
            if changed:
                self.count("zone_settings")

    async def amenities(self, row):
        code, name, category, zone = self.need(row, "code", "name", "category_code", "zone_code")
        areas = [a for a in (row.get("areas") or "main").split("|") if a]
        zone_id = await self.one("zone", "select id from zones where site_id=$1 and code=$2", SITE, zone)
        await self.c.execute("""insert into amenities(id,tenant_id,code,zone_id,name,category,areas,price,slot_minutes,open_time,close_time,max_advance_days,cancel_before_hours,weekly_quota_per_unit,max_guests,rules_note)
            values($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16) on conflict do nothing""",
                             uid("import", "amenity", code), TENANT, code, zone_id, name, category, areas, int(row.get("price") or 0), int(row.get("slot_minutes") or 60),
                             time.fromisoformat(row.get("open_time") or "06:00"), time.fromisoformat(row.get("close_time") or "22:00"), int(row.get("max_advance_days") or 7),
                             int(row.get("cancel_before_hours") or 2), int(row["weekly_quota"]) if row.get("weekly_quota") else None, int(row.get("max_guests") or 0), row.get("rules_note") or None)
        self.count("amenities")

    def audience(self, row) -> list[str]:
        values = [a for a in (row.get("audience") or "resident").split("|") if a]
        if not values or any(a not in ("resident", "staff", "management") for a in values):
            raise BadRow("audience is resident, staff and/or management, separated by |")
        return values

    async def handbook(self, row):
        title, body = self.need(row, "title", "body_md")
        zone = await self.one("zone", "select id from zones where site_id=$1 and code=$2", SITE, row["zone_code"]) if row.get("zone_code") else None
        await self.c.execute("insert into handbook_articles(id,tenant_id,zone_id,seq,title,body_md,audience,language) values($1,$2,$3,$4,$5,$6,$7,$8) on conflict do nothing",
                             uid("import", "handbook", title, row.get("zone_code") or ""), TENANT, zone, int(row.get("seq") or 0), title, body, self.audience(row), row.get("language") or "vi")
        self.count("handbook")

    async def policies(self, row):
        code, title, kind, version, effective = self.need(row, "code", "title", "kind", "version", "effective_from")
        if kind not in ("terms_of_use", "privacy_policy", "building_rules", "construction_rules", "amenity_rules", "fee_table", "faq"):
            raise BadRow(f"kind {kind!r} is not a policy kind")
        zone = await self.one("zone", "select id from zones where site_id=$1 and code=$2", SITE, row["zone_code"]) if row.get("zone_code") else None
        await self.c.execute("insert into policy_documents(id,tenant_id,code,title,kind,version,body_md,zone_id,unit_kind,audience,language,effective_from,effective_to) values($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13) on conflict do nothing",
                             uid("import", "policy", code, version), TENANT, code, title, kind, version, row.get("body_md") or "", zone, row.get("unit_kind") or None, self.audience(row),
                             row.get("language") or "vi", self.day(effective), self.day(row.get("effective_to")))
        self.count("policies")

    async def announcements(self, row):
        code, kind, title, body = self.need(row, "code", "kind", "title", "body_md")
        status = row.get("status") or "draft"
        if status not in ("draft", "published"):
            raise BadRow("status is draft or published")
        buildings = []
        for b in [x for x in (row.get("building_codes") or "").split("|") if x]:
            buildings.append(await self.one("building", "select id from buildings where site_id=$1 and code=$2", SITE, b))
        note = uid("import", "announcement", code)
        await self.c.execute("insert into announcements(id,tenant_id,code,kind,title,summary,body_md,status,building_ids,zone_ids) values($1,$2,$3,$4,$5,$6,$7,'draft',$8,'{}') on conflict do nothing",
                             note, TENANT, code, kind, title, row.get("summary") or None, body, buildings)
        if status == "published":
            await self.c.execute("update announcements set status='published',published_at=coalesce($2,now()) where id=$1 and status='draft'", note, self.stamp(row.get("published_at")))
        self.count("announcements")


async def load(url: str, folder: str, dry_run: bool) -> tuple[dict[str, int], list[str]]:
    root = Path(folder)
    if not root.is_dir():
        raise SystemExit(f"{folder} is not a folder")
    problems: list[str] = []
    conn = await asyncpg.connect(url.replace("postgresql+asyncpg:", "postgresql:", 1))
    try:
        if not await conn.fetchval("select 1 from tenants where id=$1", TENANT):
            raise SystemExit("Run `database seed` first: the import adds to the base sample.")
        tx = conn.transaction()
        await tx.start()
        await conn.execute("select set_config('app.tenant_id',$1,true)", str(TENANT))
        loader = Loader(conn)
        loader.pending_notes = {}
        for kind in ORDER:
            path = find(root, kind)
            if path is None:
                continue
            for number, row in enumerate(read(path), start=2):
                savepoint = conn.transaction()
                await savepoint.start()
                try:
                    await getattr(loader, kind)(row)
                    await savepoint.commit()
                except BadRow as exc:
                    await savepoint.rollback()
                    problems.append(f"{path.name} line {number}: {exc}")
                except (asyncpg.PostgresError, ValueError, TypeError, KeyError) as exc:
                    await savepoint.rollback()
                    problems.append(f"{path.name} line {number}: {type(exc).__name__}: {exc}")
        if not problems:
            await loader.settle_notes()
        if problems or dry_run:
            await tx.rollback()
        else:
            await tx.commit()
        return loader.added, problems
    finally:
        await conn.close()
