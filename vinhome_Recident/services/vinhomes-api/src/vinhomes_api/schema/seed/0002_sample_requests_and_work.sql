-- Synthetic local fixtures in canonical V3 tables. Re-running does not reset workflow states.
BEGIN;
SELECT set_config('app.tenant_id','11111111-1111-5111-a111-111111111111',true);
SELECT set_config('app.user_id','local-v3-admin',true);

INSERT INTO users (id,email,name,status)
VALUES ('local-v3-resident','resident@example.invalid','Cu dan demo 001','active'),
       ('local-v3-management','management@example.invalid','Ban quan ly demo','active'),
       ('local-v3-technical','technical@example.invalid','Ky thuat demo','active'),
       ('local-v3-security','security@example.invalid','Bao ve demo','active')
ON CONFLICT(id) DO NOTHING;

INSERT INTO users(id,email,name,status)
SELECT 'faker-resident-'||n, 'resident-'||n||'@example.invalid', 'Cu dan demo '||n,'active'
FROM generate_series(2,20) n ON CONFLICT(id) DO NOTHING;

INSERT INTO tenant_memberships(id,tenant_id,user_id,status,joined_at)
SELECT md5('membership:'||id)::uuid,'11111111-1111-5111-a111-111111111111',id,'active',now()
FROM users WHERE id LIKE 'local-v3-%' OR id LIKE 'faker-resident-%'
ON CONFLICT(id) DO NOTHING;

INSERT INTO scoped_user_roles(id,tenant_id,membership_id,scope_id,role_code,granted_by,valid_from)
SELECT md5('role:'||user_id)::uuid,tenant_id,id,'99999999-9999-5999-a999-999999999999',
 CASE WHEN user_id='local-v3-management' THEN 'management'
      WHEN user_id IN ('local-v3-technical','local-v3-security') THEN 'staff' ELSE 'customer' END,
 'local-v3-admin','2026-01-01T00:00:00Z'
FROM tenant_memberships WHERE tenant_id='11111111-1111-5111-a111-111111111111'
ON CONFLICT(id) DO NOTHING;

INSERT INTO service_categories(id,tenant_id,code,name)
VALUES ('33333333-3333-5333-a333-333333333334','11111111-1111-5111-a111-111111111111','security','An ninh demo')
ON CONFLICT(id) DO NOTHING;

INSERT INTO access_scopes(id,tenant_id,kind,management_unit_id)
VALUES ('99999999-9999-5999-a999-999999999998','11111111-1111-5111-a111-111111111111',
 'management','88888888-8888-5888-a888-888888888888') ON CONFLICT(id) DO NOTHING;
INSERT INTO scoped_user_roles(id,tenant_id,membership_id,scope_id,role_code,granted_by,valid_from)
VALUES (md5('management-unit-role')::uuid,'11111111-1111-5111-a111-111111111111',
 md5('membership:local-v3-management')::uuid,'99999999-9999-5999-a999-999999999998',
 'management','local-v3-admin','2026-01-01T00:00:00Z') ON CONFLICT(id) DO NOTHING;

INSERT INTO management_coverage(id,tenant_id,management_unit_id,scope_id,service_category_id,valid_from)
VALUES ('aaaaaaaa-aaaa-5aaa-aaaa-aaaaaaaaaaab','11111111-1111-5111-a111-111111111111',
 '88888888-8888-5888-a888-888888888888','99999999-9999-5999-a999-999999999999',
 '33333333-3333-5333-a333-333333333334','2026-01-01T00:00:00Z') ON CONFLICT(id) DO NOTHING;

INSERT INTO staff_profiles(id,tenant_id,user_id,management_unit_id,employee_code,availability)
VALUES ('eeeeeeee-eeee-5eee-aeee-eeeeeeeeeee1','11111111-1111-5111-a111-111111111111',
 'local-v3-technical','88888888-8888-5888-a888-888888888888','DEMO-TECH','available'),
 ('eeeeeeee-eeee-5eee-aeee-eeeeeeeeeee2','11111111-1111-5111-a111-111111111111',
 'local-v3-security','88888888-8888-5888-a888-888888888888','DEMO-SEC','available')
ON CONFLICT(id) DO NOTHING;

INSERT INTO staff_specialties(tenant_id,staff_id,category_id,proficiency)
VALUES ('11111111-1111-5111-a111-111111111111','eeeeeeee-eeee-5eee-aeee-eeeeeeeeeee1','33333333-3333-5333-a333-333333333333','demo'),
 ('11111111-1111-5111-a111-111111111111','eeeeeeee-eeee-5eee-aeee-eeeeeeeeeee2','33333333-3333-5333-a333-333333333334','demo')
ON CONFLICT DO NOTHING;

INSERT INTO staff_shifts(id,tenant_id,staff_id,starts_at,ends_at,status)
SELECT md5('shift:'||id)::uuid,tenant_id,id,'2026-01-01T00:00:00Z','2030-01-01T00:00:00Z','available'
FROM staff_profiles WHERE user_id IN ('local-v3-technical','local-v3-security')
ON CONFLICT(id) DO NOTHING;

INSERT INTO units(id,tenant_id,site_id,building_id,code,unit_kind,floor,status)
SELECT md5('demo-unit:'||n)::uuid,'11111111-1111-5111-a111-111111111111',
 '66666666-6666-5666-a666-666666666666','77777777-7777-5777-a777-777777777777',
 '12'||lpad(n::text,2,'0'),'apartment','12','active'
FROM generate_series(1,20) n ON CONFLICT(id) DO NOTHING;

INSERT INTO unit_residents(id,tenant_id,unit_id,user_id,relation,verification_status,valid_from,verified_by,verified_at)
SELECT md5('resident-unit:'||n)::uuid,'11111111-1111-5111-a111-111111111111',md5('demo-unit:'||n)::uuid,
 CASE WHEN n=1 THEN 'local-v3-resident' ELSE 'faker-resident-'||n END,
 'owner','verified','2026-01-01T00:00:00Z','local-v3-admin',now()
FROM generate_series(1,20) n ON CONFLICT(id) DO NOTHING;

INSERT INTO workspaces(id,tenant_id,management_unit_id,code,name,status)
VALUES ('ffffffff-ffff-5fff-afff-fffffffffff1','11111111-1111-5111-a111-111111111111',
 '88888888-8888-5888-a888-888888888888','demo-bql','Phong BQL demo','active')
ON CONFLICT(id) DO NOTHING;

INSERT INTO workspace_members(tenant_id,workspace_id,user_id,status,joined_at)
VALUES ('11111111-1111-5111-a111-111111111111','ffffffff-ffff-5fff-afff-fffffffffff1','local-v3-management','active',now())
ON CONFLICT DO NOTHING;

INSERT INTO channels(id,tenant_id,workspace_id,name,description,kind,created_by,is_dispatch_default)
VALUES ('management-room','11111111-1111-5111-a111-111111111111','ffffffff-ffff-5fff-afff-fffffffffff1',
 'BQL demo','Du lieu gia cho Swagger','management','local-v3-management',true)
ON CONFLICT(id) DO NOTHING;

INSERT INTO channel_memberships(tenant_id,channel_id,user_id)
VALUES ('11111111-1111-5111-a111-111111111111','management-room','local-v3-management')
ON CONFLICT DO NOTHING;

INSERT INTO agents(id,tenant_id,workspace_id,name,type,configuration,purpose,status)
VALUES ('demo-supervisor','11111111-1111-5111-a111-111111111111','ffffffff-ffff-5fff-afff-fffffffffff1',
 'Supervisor demo','built_in','{}','supervisor','active'),
 ('demo-report','11111111-1111-5111-a111-111111111111','ffffffff-ffff-5fff-afff-fffffffffff1',
 'Report demo','built_in','{}','specialist','active') ON CONFLICT(id) DO NOTHING;

INSERT INTO agents(id,tenant_id,name,type,configuration,purpose,status)
VALUES ('demo-reception','11111111-1111-5111-a111-111111111111','Reception demo','built_in','{}','reception','active')
ON CONFLICT(id) DO NOTHING;

INSERT INTO channel_agents(tenant_id,channel_id,agent_id)
VALUES ('11111111-1111-5111-a111-111111111111','management-room','demo-supervisor'),
 ('11111111-1111-5111-a111-111111111111','management-room','demo-report') ON CONFLICT DO NOTHING;

-- The Reception-to-Supervisor demo handoff requires a versioned Supervisor member.
INSERT INTO agent_versions(id,tenant_id,agent_id,version_no,runtime,framework_version,
 instructions,config,config_hash,created_by)
VALUES ('dddddddd-dddd-5ddd-addd-ddddddddddd1',
 '11111111-1111-5111-a111-111111111111','demo-supervisor',1,'agentscope',
 'demo-record-only','Supervisor demo record-only version','{}',repeat('0',64),
 'local-v3-management')
ON CONFLICT(id) DO NOTHING;

UPDATE channels SET created_by='local-v3-resident' WHERE id='local-v3-reception';
INSERT INTO channel_memberships(tenant_id,channel_id,user_id)
VALUES ('11111111-1111-5111-a111-111111111111','local-v3-reception','local-v3-resident') ON CONFLICT DO NOTHING;
UPDATE tickets SET requester_user_id='local-v3-resident',
 unit_id=md5('demo-unit:1')::uuid,site_id='66666666-6666-5666-a666-666666666666',
 building_id='77777777-7777-5777-a777-777777777777',management_unit_id='88888888-8888-5888-a888-888888888888',
 category_id='33333333-3333-5333-a333-333333333333'
WHERE id='44444444-4444-5444-a444-444444444444';

INSERT INTO channels(id,tenant_id,name,description,kind,created_by)
SELECT 'faker-chat-'||n,'11111111-1111-5111-a111-111111111111','Chat demo '||n,'Synthetic fixture','reception',
 CASE WHEN n=1 THEN 'local-v3-resident' ELSE 'faker-resident-'||n END
FROM generate_series(1,20) n ON CONFLICT(id) DO NOTHING;
INSERT INTO channel_memberships(tenant_id,channel_id,user_id)
SELECT tenant_id,id,created_by FROM channels WHERE id LIKE 'faker-chat-%' ON CONFLICT DO NOTHING;

INSERT INTO tickets(id,tenant_id,code,requester_user_id,channel_id,unit_id,site_id,building_id,management_unit_id,
 domain_id,category_id,title,description,priority,status,contact_name,contact_phone,address_snapshot,request_kind,created_at)
SELECT md5('faker-ticket:'||n)::uuid,'11111111-1111-5111-a111-111111111111','FAKER-'||lpad(n::text,3,'0'),
 CASE WHEN n=1 THEN 'local-v3-resident' ELSE 'faker-resident-'||n END,'faker-chat-'||n,md5('demo-unit:'||n)::uuid,
 '66666666-6666-5666-a666-666666666666','77777777-7777-5777-a777-777777777777','88888888-8888-5888-a888-888888888888',
 '22222222-2222-5222-a222-222222222222','33333333-3333-5333-a333-333333333333',
 CASE WHEN n%2=0 THEN 'Kiem tra dien demo ' ELSE 'Sua ong nuoc demo ' END||n,
 'Du lieu tong hop, khong phai su co that','normal','open','Cu dan demo '||n,'0000000000','{}','incident',
 now() - (n||' days')::interval
FROM generate_series(1,20) n ON CONFLICT(id) DO NOTHING;

INSERT INTO invoices(id,tenant_id,ticket_id,invoice_no,issued_by_staff_id,bill_to_user_id,status,subtotal,tax_total,grand_total,issued_at)
SELECT md5('faker-invoice:'||n)::uuid,'11111111-1111-5111-a111-111111111111',md5('faker-ticket:'||n)::uuid,
 'DEMO-INV-'||n,'eeeeeeee-eeee-5eee-aeee-eeeeeeeeeee1',
 CASE WHEN n=1 THEN 'local-v3-resident' ELSE 'faker-resident-'||n END,
 'issued',100000+n*10000,0,100000+n*10000,now() - (n||' days')::interval
FROM generate_series(1,20) n ON CONFLICT(id) DO NOTHING;
INSERT INTO invoice_lines(id,tenant_id,invoice_id,line_no,category_id,description,quantity,unit_price,net_amount,tax_amount,total_amount)
SELECT md5('faker-invoice-line:'||n)::uuid,'11111111-1111-5111-a111-111111111111',md5('faker-invoice:'||n)::uuid,
 1,'33333333-3333-5333-a333-333333333333','Dich vu ky thuat gia lap',1,100000+n*10000,100000+n*10000,0,100000+n*10000
FROM generate_series(1,20) n ON CONFLICT(id) DO NOTHING;
COMMIT;
