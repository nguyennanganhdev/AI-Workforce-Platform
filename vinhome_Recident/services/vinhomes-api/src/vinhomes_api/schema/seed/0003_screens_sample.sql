-- Site-scoped actors for the single local demo site; no production grants.
BEGIN;
INSERT INTO access_scopes(id,tenant_id,kind,site_id)
VALUES (md5('demo-ui-site-scope')::uuid,'11111111-1111-5111-a111-111111111111',
 'site','66666666-6666-5666-a666-666666666666')
ON CONFLICT(id) DO NOTHING;
INSERT INTO scoped_user_roles(id,tenant_id,membership_id,scope_id,role_code,granted_by,valid_from)
SELECT md5('demo-ui-site-role:'||user_id)::uuid,tenant_id,id,md5('demo-ui-site-scope')::uuid,
 CASE WHEN user_id='local-v3-management' THEN 'management' ELSE 'staff' END,
 'local-v3-admin','2026-01-01T00:00:00Z'
FROM tenant_memberships
WHERE tenant_id='11111111-1111-5111-a111-111111111111'
 AND user_id IN ('local-v3-management','local-v3-security') AND status='active'
ON CONFLICT(id) DO NOTHING;
COMMIT;
