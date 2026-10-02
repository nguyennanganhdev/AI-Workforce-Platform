-- Fake fixtures only. Requires the existing local V3 demo seed and migration 0009.
BEGIN;
SET LOCAL app.tenant_id='11111111-1111-5111-a111-111111111111';
INSERT INTO units
SELECT (jsonb_populate_record(null::units,to_jsonb(u)||jsonb_build_object(
 'id','e5555555-5555-4555-8555-555555555555','code','A2-DEMO'))).*
FROM units u WHERE tenant_id=current_setting('app.tenant_id')::uuid
 AND building_id='77777777-7777-5777-a777-777777777777' LIMIT 1 ON CONFLICT DO NOTHING;
INSERT INTO unit_residents
SELECT (jsonb_populate_record(null::unit_residents,to_jsonb(r)||jsonb_build_object(
 'id','e5555555-5555-4555-8555-555555555556','unit_id','e5555555-5555-4555-8555-555555555555'))).*
FROM unit_residents r WHERE tenant_id=current_setting('app.tenant_id')::uuid LIMIT 1 ON CONFLICT DO NOTHING;
-- Retire the early local fixture whose MD5 UUID does not meet the API UUID format.
UPDATE knowledge_documents SET status='archived',code='SOP-DEMO-DRAIN-OLD'
WHERE tenant_id=current_setting('app.tenant_id')::uuid AND id=md5('technical-demo-sop')::uuid;
INSERT INTO knowledge_categories(id,tenant_id,code,name)
VALUES(md5('technical-demo-category')::uuid,current_setting('app.tenant_id')::uuid,'TECH-DEMO','SOP kỹ thuật demo') ON CONFLICT DO NOTHING;
INSERT INTO knowledge_bases(id,tenant_id,domain_id,code,name,status)
SELECT md5('technical-demo-kb')::uuid,tenant_id,id,'TECH-DEMO','Tri thức kỹ thuật demo','active' FROM domains
WHERE tenant_id=current_setting('app.tenant_id')::uuid LIMIT 1 ON CONFLICT DO NOTHING;
INSERT INTO knowledge_documents(id,tenant_id,knowledge_base_id,category_id,code,title,status,language)
VALUES('e1111111-1111-4111-8111-111111111111'::uuid,current_setting('app.tenant_id')::uuid,md5('technical-demo-kb')::uuid,
 md5('technical-demo-category')::uuid,'SOP-DEMO-DRAIN','SOP thoát nước demo','published','vi') ON CONFLICT DO NOTHING;
INSERT INTO document_scopes(tenant_id,document_id,scope_id,applies_to_descendants)
SELECT tenant_id,'e1111111-1111-4111-8111-111111111111'::uuid,id,true FROM access_scopes
WHERE tenant_id=current_setting('app.tenant_id')::uuid AND building_id='77777777-7777-5777-a777-777777777777'
ON CONFLICT DO NOTHING;
INSERT INTO document_acl(tenant_id,document_id,principal_kind,role_code,effect)
SELECT current_setting('app.tenant_id')::uuid,'e1111111-1111-4111-8111-111111111111'::uuid,'role',r,'allow'
FROM unnest(ARRAY['management','staff']) r
WHERE NOT EXISTS(SELECT 1 FROM document_acl WHERE document_id='e1111111-1111-4111-8111-111111111111'::uuid AND role_code=r);
INSERT INTO document_versions(id,tenant_id,document_id,version_no,file_id,content_hash,effective_from,submitted_by,extraction_config)
SELECT 'e2222222-2222-4222-8222-222222222222'::uuid,tenant_id,'e1111111-1111-4111-8111-111111111111'::uuid,1,id,repeat('0',64),
 '2026-01-01T00:00:00Z','local-v3-management','{}' FROM files
WHERE tenant_id=current_setting('app.tenant_id')::uuid AND status='ready' LIMIT 1 ON CONFLICT DO NOTHING;
UPDATE knowledge_documents SET active_version_id='e2222222-2222-4222-8222-222222222222'::uuid
WHERE id='e1111111-1111-4111-8111-111111111111'::uuid AND EXISTS(SELECT 1 FROM document_versions WHERE id='e2222222-2222-4222-8222-222222222222'::uuid);
INSERT INTO agents(id,name,type,configuration,tenant_id,workspace_id,status,purpose)
SELECT 'demo-technical-a2','Technical A2 demo',type,'{}',tenant_id,workspace_id,'active','specialist'
FROM agents WHERE id='demo-supervisor' ON CONFLICT(id) DO NOTHING;
INSERT INTO agent_versions(tenant_id,agent_id,version_no,runtime,framework_version,instructions,config,config_hash,created_by)
SELECT tenant_id,'demo-technical-a2',1,runtime,framework_version,'API demo; no AI execution','{}',repeat('0',64),created_by
FROM agent_versions WHERE agent_id='demo-supervisor' AND version_no=1
ON CONFLICT DO NOTHING;
INSERT INTO vh_technical_agent_grants(tenant_id,agent_id,capability,scope_id)
SELECT r.tenant_id,'demo-technical-a2',c.capability,r.scope_id
FROM scoped_user_roles r JOIN tenant_memberships m ON m.tenant_id=r.tenant_id AND m.id=r.membership_id
CROSS JOIN unnest(ARRAY['interruption:read','sop:read','asset:read','sensor:read','maintenance:read',
 'measurement:write','executor_result:submit','resolution:verify','maintenance:append',
 'utility_isolation:request','area_restriction:request','apartment_entry:request','vendor_dispatch:request']) AS c(capability)
WHERE m.user_id IN ('local-v3-management','local-v3-technical') AND m.tenant_id=current_setting('app.tenant_id')::uuid
ON CONFLICT DO NOTHING;
UPDATE vh_assets SET details=details||jsonb_build_object('type','pump','model','DEMO-PUMP',
 'location','Phòng bơm tầng B1','ownership','building','updatedAt',now())
WHERE tenant_id=current_setting('app.tenant_id')::uuid AND code='ASSET-DEMO-1';
INSERT INTO vh_technical_sensors(tenant_id,sensor_id,building_id,asset_id,metric,unit)
SELECT tenant_id,'SENSOR-DEMO-SUPPLY-PRESSURE',building_id,code,'supply_pressure','bar' FROM vh_assets
WHERE tenant_id=current_setting('app.tenant_id')::uuid AND code='ASSET-DEMO-1' ON CONFLICT DO NOTHING;
INSERT INTO vh_technical_sensor_samples(tenant_id,sensor_id,value,unit,observed_at,quality)
SELECT tenant_id,sensor_id,2.5,'bar',now(),'good' FROM vh_technical_sensors
WHERE tenant_id=current_setting('app.tenant_id')::uuid AND sensor_id='SENSOR-DEMO-SUPPLY-PRESSURE';
INSERT INTO vh_technical_sop_profiles(tenant_id,document_code,version_no,issue_codes,excerpt,acceptance_criteria)
SELECT d.tenant_id,d.code,v.version_no,'["TECH.PLUMB.SEWAGE_BACKFLOW"]',
 'SOP demo: kiểm tra điểm rò nước; ghi số đo và ảnh; đề nghị BQL duyệt nếu cần cô lập nước.',
 '[{"id":"DRAIN_CLEAR","text":"Đường thoát nước thông","check":{"kind":"checklist","itemCode":"DRAIN_CLEAR"}}]'
FROM knowledge_documents d JOIN document_versions v ON v.tenant_id=d.tenant_id AND v.id=d.active_version_id
WHERE d.tenant_id=current_setting('app.tenant_id')::uuid AND d.status='published'
ON CONFLICT DO NOTHING;
INSERT INTO vh_technical_vendors(tenant_id,id,payload)
SELECT tenant_id,'VENDOR-DEMO-WATER',jsonb_build_object('vendorId','VENDOR-DEMO-WATER',
 'tenantId',tenant_id,'displayName','Nhà thầu nước demo','specialtyCodes',jsonb_build_array('plumbing'),
 'siteIds',jsonb_build_array(site_id),'status','active','licenseExpiresAt','2030-01-01T00:00:00Z',
 'insuranceVerified',true,'contactPhone','0000000000','hourlyRate',0)
FROM buildings WHERE id='77777777-7777-5777-a777-777777777777'
ON CONFLICT DO NOTHING;
COMMIT;
