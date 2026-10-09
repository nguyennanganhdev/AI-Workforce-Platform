"""The limits that differ from one zone to another (migration 0012, table zone_settings).

What a home may hold or announce is read where it is judged, from the zone the home is in; a zone that sets
nothing gets the tenant's value, and a tenant that sets nothing gets the value app_zone_rules carries.
"""

from sqlalchemy import text

TENANT = "nullif(current_setting('app.tenant_id',true),'')::uuid"


async def unit_rules(db, unit_id) -> dict:
    """The rules that apply to a home, from its building's zone."""
    row = (await db.execute(text(f"""
        select r.* from units u join buildings b on b.id=u.building_id and b.tenant_id=u.tenant_id
        cross join lateral app_zone_rules(u.tenant_id, b.zone_id) r
        where u.tenant_id={TENANT} and u.id=:unit
    """), {"unit": unit_id})).mappings().one()
    return dict(row)
