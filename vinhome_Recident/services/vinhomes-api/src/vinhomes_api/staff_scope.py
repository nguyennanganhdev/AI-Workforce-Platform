"""Dispatch eligibility must match the scope the worker's UI can actually read.

SQL callers supply aliases sp (staff profile) and t (ticket). Assignment ownership
is deliberately excluded: this predicate runs before an assignment exists.
"""

STAFF_TICKET_SCOPE = """
exists (
    select 1 from scoped_user_roles r
    join tenant_memberships m on m.id=r.membership_id and m.tenant_id=r.tenant_id
    join access_scopes s on s.id=r.scope_id and s.tenant_id=r.tenant_id
    where m.user_id=sp.user_id and m.status='active' and r.tenant_id=t.tenant_id
      and r.role_code in ('staff','management')
      and r.valid_from<=now() and (r.valid_to is null or r.valid_to>now())
      and (s.kind='tenant'
        or (s.kind='management' and s.management_unit_id=t.management_unit_id)
        or (s.kind='site' and s.site_id=t.site_id)
        or (s.kind='zone' and s.zone_id=t.zone_id)
        or (s.kind='building' and s.building_id=t.building_id))
)
"""
