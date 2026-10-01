-- Relational fixtures for the new V3 endpoints. Existing workflow state is preserved.
BEGIN;
SELECT set_config('app.tenant_id','11111111-1111-5111-a111-111111111111',true);
INSERT INTO security_cameras(id,tenant_id,building_id,code,name,location,status)
SELECT md5('demo-camera:'||n)::uuid,'11111111-1111-5111-a111-111111111111',
 '77777777-7777-5777-a777-777777777777','CAM-DEMO-'||n,'Camera demo '||n,
 CASE WHEN n=1 THEN 'Sanh toa nha' ELSE 'Bai xe' END,
 CASE WHEN n=1 THEN 'online' ELSE 'offline' END
FROM generate_series(1,2) n ON CONFLICT DO NOTHING;

INSERT INTO security_emergency_contacts(id,tenant_id,building_id,user_id,name,role_label,phone,position,ack_timeout_seconds)
VALUES
 (md5('demo-contact:1')::uuid,'11111111-1111-5111-a111-111111111111','77777777-7777-5777-a777-777777777777','local-v3-security','Bao ve demo','Bao ve truc','0000000000',1,60),
 (md5('demo-contact:2')::uuid,'11111111-1111-5111-a111-111111111111','77777777-7777-5777-a777-777777777777','local-v3-management','Ban quan ly demo','Truong ban quan ly','0000000000',2,60)
ON CONFLICT DO NOTHING;

INSERT INTO channels(id,tenant_id,name,description,kind,created_by)
VALUES ('demo-emergency-chat','11111111-1111-5111-a111-111111111111','Trao doi su co an ninh demo','Du lieu gia de demo an ninh','reception','local-v3-resident') ON CONFLICT DO NOTHING;
INSERT INTO channel_memberships(tenant_id,channel_id,user_id)
VALUES ('11111111-1111-5111-a111-111111111111','demo-emergency-chat','local-v3-resident') ON CONFLICT DO NOTHING;
INSERT INTO tickets(id,tenant_id,code,requester_user_id,channel_id,domain_id,site_id,zone_id,building_id,management_unit_id,category_id,title,description,priority,severity,is_emergency,status,contact_name,contact_phone,address_snapshot,request_kind)
SELECT md5('demo-emergency-ticket')::uuid,tenant_id,'DEMO-SEC-EMERGENCY',requester_user_id,'demo-emergency-chat',domain_id,site_id,zone_id,building_id,management_unit_id,
 '33333333-3333-5333-a333-333333333334','Tinh huong an ninh khan cap demo','Du lieu gia: can bao ve kiem tra khu vuc sanh',
 'critical','critical',true,'open','Cu dan demo','0000000000','{}','incident'
FROM tickets WHERE id=md5('faker-ticket:1')::uuid ON CONFLICT DO NOTHING;
INSERT INTO work_orders(id,tenant_id,ticket_id,category_id,description,status,required_specialty_id)
VALUES (md5('demo-security-work')::uuid,'11111111-1111-5111-a111-111111111111',md5('demo-emergency-ticket')::uuid,
 '33333333-3333-5333-a333-333333333334','Kiem tra su co an ninh demo','queued','33333333-3333-5333-a333-333333333334')
ON CONFLICT DO NOTHING;

INSERT INTO vh_security_checkpoints(id,tenant_id,site_id,name,location,sort_order,status)
VALUES (md5('demo-checkpoint')::uuid,'11111111-1111-5111-a111-111111111111','66666666-6666-5666-a666-666666666666','Sanh demo','Tang 1',1,'missed')
ON CONFLICT DO NOTHING;

INSERT INTO agents(id,tenant_id,workspace_id,name,type,configuration,purpose,status)
VALUES ('demo-room-unlinked','11111111-1111-5111-a111-111111111111','ffffffff-ffff-5fff-afff-fffffffffff1','Agent co san demo','built_in','{"demo":true}','specialist','active')
ON CONFLICT DO NOTHING;

INSERT INTO execution_principals(id,tenant_id,kind,workspace_id,status)
VALUES (md5('demo-workspace-principal')::uuid,'11111111-1111-5111-a111-111111111111','workspace_service','ffffffff-ffff-5fff-afff-fffffffffff1','active')
ON CONFLICT DO NOTHING;
INSERT INTO memory_namespaces(id,tenant_id,owner_principal_id,kind,workspace_id,namespace_key,purpose,status)
SELECT md5('demo-memory-namespace')::uuid,tenant_id,id,'workspace',workspace_id,'demo-operations','operations','active'
FROM execution_principals WHERE workspace_id='ffffffff-ffff-5fff-afff-fffffffffff1' AND kind='workspace_service'
ON CONFLICT DO NOTHING;
INSERT INTO memory_candidates(id,tenant_id,source_ticket_id,scope_id,namespace_id,proposed_text,evidence,pii_redacted,status,reason,proposal_hash)
VALUES (md5('demo-memory-pending')::uuid,'11111111-1111-5111-a111-111111111111',md5('demo-emergency-ticket')::uuid,
 '99999999-9999-5999-a999-999999999998',md5('demo-memory-namespace')::uuid,'Quy trinh demo: kiem tra sanh, ghi nhan bang chung va bao BQL.',
 '{"source":"synthetic-demo"}',true,'pending','Du lieu gia de chay luong duyet memory',
 encode(sha256(convert_to('demo-memory-pending','UTF8')),'hex')) ON CONFLICT DO NOTHING;

INSERT INTO users(id,name,email,status)
VALUES ('demo-pending-account','Tai khoan cho duyet demo','pending-demo@example.test','active'),
 ('demo-suspended-account','Tai khoan bi khoa demo','suspended-demo@example.test','active')
ON CONFLICT DO NOTHING;
INSERT INTO tenant_memberships(id,tenant_id,user_id,status)
VALUES (md5('demo-pending-membership')::uuid,'11111111-1111-5111-a111-111111111111','demo-pending-account','pending'),
 (md5('demo-suspended-membership')::uuid,'11111111-1111-5111-a111-111111111111','demo-suspended-account','suspended')
ON CONFLICT DO NOTHING;
INSERT INTO account_reviews(id,tenant_id,user_id,action,to_status,reason,reviewer_user_id,decided_at)
VALUES (md5('demo-account-registration')::uuid,'11111111-1111-5111-a111-111111111111','demo-pending-account','register','pending','Dang ky gia cho demo','local-v3-admin',now())
ON CONFLICT DO NOTHING;
-- Independent historical work orders keep the specialised screens populated.
INSERT INTO work_orders(id,tenant_id,ticket_id,category_id,description,status,required_specialty_id)
SELECT md5('demo-special-work:'||kind)::uuid,t.tenant_id,t.id,t.category_id,
 'Cong viec gia: '||kind,CASE WHEN kind='qc' THEN 'completed' ELSE 'queued' END,t.category_id
FROM tickets t CROSS JOIN unnest(ARRAY['qc','redo','cleaning','contractor','budget']) kind
WHERE t.id=md5('faker-ticket:1')::uuid ON CONFLICT DO NOTHING;
INSERT INTO vh_qc_results(id,tenant_id,work_order_id,outcome,criteria,redo_required,note,checked_by)
VALUES (md5('demo-qc-fail')::uuid,'11111111-1111-5111-a111-111111111111',md5('demo-special-work:qc')::uuid,
 'fail','{"demo":true,"cleanliness":false}',true,'Ket qua gia de demo lam lai','local-v3-management')
ON CONFLICT DO NOTHING;
INSERT INTO vh_qc_redo_orders(id,tenant_id,qc_result_id,source_work_order_id,redo_work_order_id,created_by)
VALUES (md5('demo-redo-link')::uuid,'11111111-1111-5111-a111-111111111111',md5('demo-qc-fail')::uuid,
 md5('demo-special-work:qc')::uuid,md5('demo-special-work:redo')::uuid,'local-v3-management') ON CONFLICT DO NOTHING;
INSERT INTO vh_cleaning_plans(id,tenant_id,work_order_id,plan,status,updated_by)
VALUES (md5('demo-cleaning-plan')::uuid,'11111111-1111-5111-a111-111111111111',md5('demo-special-work:cleaning')::uuid,
 '{"demo":true,"areas":["Sanh demo"],"steps":["Quet san","Lau san"]}','draft','local-v3-management') ON CONFLICT DO NOTHING;
INSERT INTO vh_contractor_updates(id,tenant_id,work_order_id,status,worker_name,materials,note,updated_by)
VALUES (md5('demo-contractor')::uuid,'11111111-1111-5111-a111-111111111111',md5('demo-special-work:contractor')::uuid,
 'pending','Nha thau gia','[{"name":"Vat tu demo","quantity":1}]','Du lieu demo','local-v3-management') ON CONFLICT DO NOTHING;
INSERT INTO vh_budget_approvals(id,tenant_id,work_order_id,requested_by,reviewer_user_id,amount_vnd,purpose,status)
VALUES (md5('demo-budget')::uuid,'11111111-1111-5111-a111-111111111111',md5('demo-special-work:budget')::uuid,
 'local-v3-technical','local-v3-management',250000,'Vat tu gia cho demo','pending') ON CONFLICT DO NOTHING;
INSERT INTO vh_security_incidents(id,tenant_id,site_id,ticket_id,title,location,severity,report,status,reported_by)
VALUES (md5('demo-incident')::uuid,'11111111-1111-5111-a111-111111111111','66666666-6666-5666-a666-666666666666',
 md5('demo-emergency-ticket')::uuid,'Su co gia tai sanh','Sanh demo','p1','{"demo":true}','investigating','local-v3-security') ON CONFLICT DO NOTHING;
INSERT INTO vh_security_handovers(id,tenant_id,site_id,shift_name,shift_date,payload,from_user_id,to_user_id)
VALUES (md5('demo-handover')::uuid,'11111111-1111-5111-a111-111111111111','66666666-6666-5666-a666-666666666666',
 'ca_sang','2026-10-01','{"demo":true,"note":"Kiem tra sanh"}','local-v3-security','local-v3-management') ON CONFLICT DO NOTHING;
INSERT INTO vh_assets(id,tenant_id,building_id,code,name,details,status)
VALUES (md5('demo-asset')::uuid,'11111111-1111-5111-a111-111111111111','77777777-7777-5777-a777-777777777777',
 'ASSET-DEMO-1','May bom demo','{"demo":true,"location":"Phong ky thuat"}','active') ON CONFLICT DO NOTHING;
INSERT INTO vh_sensor_readings(id,tenant_id,asset_id,parameter,value,unit,measured_at,source,recorded_by)
VALUES (md5('demo-sensor')::uuid,'11111111-1111-5111-a111-111111111111',md5('demo-asset')::uuid,
 'pressure',2.5,'bar','2026-10-01T00:00:00Z','synthetic-demo','local-v3-management') ON CONFLICT DO NOTHING;
COMMIT;
