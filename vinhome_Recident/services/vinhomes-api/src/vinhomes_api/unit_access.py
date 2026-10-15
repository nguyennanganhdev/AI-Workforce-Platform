"""Who may touch which home: the resident's link to it, and the staff scope that covers it."""

from fastapi import HTTPException
from sqlalchemy import text

TENANT = "nullif(current_setting('app.tenant_id',true),'')::uuid"
ALL_RELATIONS = ("owner", "tenant", "household")
# Money and renovation are for the people who answer for the home, not for every member of the household.
ANSWERABLE = ("owner", "tenant")

# A unit alias `u` is visible to staff whose valid role has a scope that covers its building, zone, site or the
# management unit that covers it. Parameters: :user_id and :is_admin.
UNIT_VISIBILITY = """
    u.tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid
    and (:is_admin or exists (
        select 1 from scoped_user_roles r
        join tenant_memberships m on m.id=r.membership_id and m.tenant_id=r.tenant_id
        join access_scopes s on s.id=r.scope_id and s.tenant_id=r.tenant_id
        where m.user_id=:user_id and m.status='active' and r.role_code in ('management','staff')
          and r.valid_from<=now() and (r.valid_to is null or r.valid_to>now()) and r.tenant_id=u.tenant_id
          and (s.kind='tenant'
            or (s.kind='site' and s.site_id=u.site_id)
            or (s.kind='zone' and s.zone_id=u.zone_id)
            or (s.kind='building' and s.building_id=u.building_id)
            or (s.kind='management' and exists (
                select 1 from management_coverage mc join access_scopes cs on cs.id=mc.scope_id and cs.tenant_id=mc.tenant_id
                where mc.management_unit_id=s.management_unit_id and mc.tenant_id=u.tenant_id
                  and mc.valid_from<=now() and (mc.valid_to is null or mc.valid_to>now())
                  and (cs.kind='tenant' or (cs.kind='site' and cs.site_id=u.site_id)
                    or (cs.kind='zone' and cs.zone_id=u.zone_id) or (cs.kind='building' and cs.building_id=u.building_id)))))
    ))
"""


async def resident_unit(db, user_id: str, unit_id, relations=ALL_RELATIONS) -> dict:
    """The home, if the person is verified to live there in one of the given roles. Otherwise 403."""
    row = (await db.execute(text(f"""
        select u.id,u.code,u.unit_kind,u.site_id,u.zone_id,u.building_id,ur.relation
        from unit_residents ur join units u on u.id=ur.unit_id and u.tenant_id=ur.tenant_id
        where ur.tenant_id={TENANT} and ur.user_id=:user and ur.unit_id=:unit and ur.verification_status='verified'
          and ur.valid_from<=now() and (ur.valid_to is null or ur.valid_to>now())
        order by (ur.relation='owner') desc limit 1
    """), {"user": user_id, "unit": unit_id})).mappings().first()
    if row is None or row["relation"] not in relations:
        raise HTTPException(403, "You are not linked to this home for that")
    return dict(row)


async def my_units(db, user_id: str) -> list[dict]:
    rows = await db.execute(text(f"""
        select u.id,u.code,ur.relation from unit_residents ur join units u on u.id=ur.unit_id and u.tenant_id=ur.tenant_id
        where ur.tenant_id={TENANT} and ur.user_id=:user and ur.verification_status='verified'
          and ur.valid_from<=now() and (ur.valid_to is null or ur.valid_to>now()) order by u.code
    """), {"user": user_id})
    return [dict(r) for r in rows.mappings()]


async def staff_unit(scope, unit_id) -> dict:
    """A home the staff member is responsible for. Otherwise 404, so staff cannot probe other places."""
    db, user_id, is_admin = scope
    row = (await db.execute(text(f"select u.id,u.code,u.unit_kind,u.site_id,u.zone_id,u.building_id from units u where u.id=:unit and {UNIT_VISIBILITY}"),
                            {"unit": unit_id, "user_id": user_id, "is_admin": is_admin})).mappings().first()
    if row is None:
        raise HTTPException(404, "Home not found")
    return dict(row)


async def require_management(scope) -> None:
    """Management (or the administrator) decides; other staff only prepare."""
    db, user_id, is_admin = scope
    if is_admin:
        return
    allowed = (await db.execute(text(f"""
        select 1 from scoped_user_roles r join tenant_memberships m on m.id=r.membership_id and m.tenant_id=r.tenant_id
        where m.user_id=:user and m.status='active' and r.tenant_id={TENANT} and r.role_code='management'
          and r.valid_from<=now() and (r.valid_to is null or r.valid_to>now()) limit 1
    """), {"user": user_id})).first()
    if allowed is None:
        raise HTTPException(403, "Management role required")


def delegated() -> dict | None:
    """The delegation behind this request, when an agent is acting for the person."""
    from .integration import CURRENT
    return CURRENT.get()


def for_agent(row: dict, *hidden: str) -> dict:
    """Fields an agent never sees (contract section 3.4) are removed when one is acting."""
    if delegated() is None:
        return row
    return {key: value for key, value in row.items() if key not in hidden}
