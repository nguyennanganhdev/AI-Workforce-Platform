"""Add the cleaning and landscape service ("Vệ sinh & cảnh quan") to an existing deployment's data.

    DATABASE_URL=<database owner> VINHOMES_API_TENANT_ID=<tenant> python scripts/add_cleaning_service.py

The platform routes a resident request by its service category: Reception picks one of the enabled
categories, the request goes to the management unit covering that category for the building, the
Supervisor invites the published specialists that serve it, and the work is offered to staff with
that specialty. A deployment that only knows `technical` and `security` can do none of this for a
complaint about rubbish or the gardens. This adds the data, no tables:

- the category `cleaning`, the code Team Hoàng's cleaning tools look for;
- coverage of it wherever a management unit covers `technical` today, on the same scopes;
- one cleaning staff account of the Sapphire unit, with the specialty and an open shift.

Safe to run again: rows that exist are left alone, and a password is generated only for an account
this run creates. It is appended to `.local-connected/accounts.txt` (ignored by git), never printed.
"""

import asyncio
import os
import secrets
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import asyncpg
from vinhomes_api.password_auth import PROVIDER, password_hash

ACCOUNTS_FILE = Path(__file__).resolve().parents[1] / ".local-connected" / "accounts.txt"
UNIT = "bql-sapphire"
STAFF = ("vesinh.sapphire@oceanpark.local", "Nhân viên vệ sinh Sapphire", "VS-SAPPHIRE-01")


async def main() -> None:
    url, tenant = os.environ.get("DATABASE_URL", ""), os.environ.get("VINHOMES_API_TENANT_ID", "")
    if not url or not tenant:
        raise SystemExit("DATABASE_URL (the database owner) and VINHOMES_API_TENANT_ID are required")
    t = UUID(tenant)

    def key(name: str) -> UUID:
        """Stable ids, so running again finds the same rows."""
        return uuid5(NAMESPACE_URL, f"connected:{tenant}:{name}")

    db = await asyncpg.connect(url.replace("postgresql+asyncpg://", "postgresql://"))
    password = None
    try:
        async with db.transaction():
            await db.execute("select set_config('app.tenant_id',$1,true)", tenant)
            await db.execute("insert into service_categories(id,tenant_id,code,name) values($1,$2,'cleaning','Vệ sinh & cảnh quan') "
                             "on conflict do nothing", key("category:cleaning"), t)
            category = await db.fetchval("select id from service_categories where tenant_id=$1 and code='cleaning'", t)
            covered = await db.execute("""
                insert into management_coverage(tenant_id,management_unit_id,scope_id,service_category_id,priority,valid_from)
                select mc.tenant_id,mc.management_unit_id,mc.scope_id,$2,mc.priority,now() from management_coverage mc
                join service_categories c on c.id=mc.service_category_id and c.tenant_id=mc.tenant_id and c.code='technical'
                where mc.tenant_id=$1 and mc.valid_from<=now() and (mc.valid_to is null or mc.valid_to>now())
                  and not exists (select 1 from management_coverage x where x.tenant_id=mc.tenant_id
                    and x.management_unit_id=mc.management_unit_id and x.scope_id=mc.scope_id and x.service_category_id=$2
                    and (x.valid_to is null or x.valid_to>now()))""", t, category)

            unit = await db.fetchval("select id from management_units where tenant_id=$1 and code=$2 and status='active'", t, UNIT)
            if unit is None:
                raise SystemExit(f"No active management unit {UNIT}")
            email, name, code = STAFF
            user = await db.fetchval("select id from users where lower(email)=$1", email)
            if user is None:
                user, password = str(uuid4()), secrets.token_urlsafe(12)
                await db.execute("insert into users(id,email,name,status) values($1,$2,$3,'active')", user, email, name)
                await db.execute("insert into accounts(id,account_id,provider_id,user_id,password) values($1,$2,$3,$2,$4)",
                                 str(uuid4()), user, PROVIDER, await asyncio.to_thread(password_hash, password))
            await db.execute("insert into tenant_memberships(id,tenant_id,user_id,status,joined_at) values($1,$2,$3,'active',now()) "
                             "on conflict do nothing", key("membership:cleaning-staff"), t, user)
            membership = await db.fetchval("select id from tenant_memberships where tenant_id=$1 and user_id=$2", t, user)
            # Staff on site work across the site, as the technician does.
            site_scope = await db.fetchval("""select s.id from access_scopes s join sites site on site.id=s.site_id and site.tenant_id=s.tenant_id
                where s.tenant_id=$1 and s.kind='site' and site.code='ocean-park-1'""", t)
            admin = await db.fetchval("select user_id from platform_admins order by user_id limit 1")
            await db.execute("insert into scoped_user_roles(id,tenant_id,membership_id,scope_id,role_code,granted_by,valid_from) "
                             "values($1,$2,$3,$4,'staff',$5,now()) on conflict do nothing",
                             key("role:cleaning-staff:site"), t, membership, site_scope, admin)
            staff = key("staff:cleaning")
            await db.execute("insert into staff_profiles(id,tenant_id,user_id,management_unit_id,employee_code,availability) "
                             "values($1,$2,$3,$4,$5,'available') on conflict do nothing", staff, t, user, unit, code)
            await db.execute("insert into staff_specialties(tenant_id,staff_id,category_id,proficiency) values($1,$2,$3,'standard') "
                             "on conflict do nothing", t, staff, category)
            await db.execute("insert into staff_shifts(id,tenant_id,staff_id,starts_at,ends_at,status) "
                             "values($1,$2,$3,now(),now()+interval '5 years','available') on conflict do nothing",
                             key("shift:cleaning"), t, staff)
    finally:
        await db.close()
    if password:
        ACCOUNTS_FILE.parent.mkdir(exist_ok=True)
        with ACCOUNTS_FILE.open("a", encoding="utf-8") as out:
            out.write(f"cleaning: {STAFF[0]} / {password}\n")
    print(f"Cleaning service ready. Coverage rows added: {covered.split()[-1]}. "
          + (f"Staff account created; password in {ACCOUNTS_FILE.name}." if password else "Staff account already existed."))


if __name__ == "__main__":
    asyncio.run(main())
