-- Local Swagger fixture only. Run on an empty V3 development database.
-- This fixture is isolated from the legacy vh_* PostgreSQL instance.
BEGIN;
SELECT set_config('app.tenant_id', '11111111-1111-5111-a111-111111111111', true);
SELECT set_config('app.user_id', 'local-v3-admin', true);

INSERT INTO tenants (id, code, name, status)
VALUES ('11111111-1111-5111-a111-111111111111', 'vinhomes-local-v3', 'Vinhomes Local V3', 'active')
ON CONFLICT (id) DO NOTHING;

INSERT INTO users (id, email, name, status)
VALUES ('local-v3-admin', 'local-v3-admin@example.invalid', 'Local V3 Admin', 'active')
ON CONFLICT (id) DO NOTHING;

INSERT INTO platform_admins (user_id)
VALUES ('local-v3-admin') ON CONFLICT (user_id) DO NOTHING;

INSERT INTO domains (id, tenant_id, code, name, status)
VALUES ('22222222-2222-5222-a222-222222222222', '11111111-1111-5111-a111-111111111111', 'vinhomes', 'Vinhomes', 'active')
ON CONFLICT (id) DO NOTHING;

INSERT INTO service_categories (id, tenant_id, code, name)
VALUES ('33333333-3333-5333-a333-333333333333', '11111111-1111-5111-a111-111111111111', 'technical', 'Technical')
ON CONFLICT (id) DO NOTHING;

INSERT INTO sites (id, tenant_id, domain_id, code, name, address, status)
VALUES ('66666666-6666-5666-a666-666666666666', '11111111-1111-5111-a111-111111111111',
        '22222222-2222-5222-a222-222222222222', 'local-site', 'Local Site', 'Local demo', 'active')
ON CONFLICT (id) DO NOTHING;

INSERT INTO buildings (id, tenant_id, site_id, code, name, status)
VALUES ('77777777-7777-5777-a777-777777777777', '11111111-1111-5111-a111-111111111111',
        '66666666-6666-5666-a666-666666666666', 'local-building', 'Local Building', 'active')
ON CONFLICT (id) DO NOTHING;

INSERT INTO management_units (id, tenant_id, code, name, status)
VALUES ('88888888-8888-5888-a888-888888888888', '11111111-1111-5111-a111-111111111111',
        'local-management', 'Local Management', 'active')
ON CONFLICT (id) DO NOTHING;

INSERT INTO access_scopes (id, tenant_id, kind, building_id)
VALUES ('99999999-9999-5999-a999-999999999999', '11111111-1111-5111-a111-111111111111',
        'building', '77777777-7777-5777-a777-777777777777')
ON CONFLICT (id) DO NOTHING;

INSERT INTO management_coverage
  (id, tenant_id, management_unit_id, scope_id, service_category_id, valid_from)
VALUES ('aaaaaaaa-aaaa-5aaa-aaaa-aaaaaaaaaaaa', '11111111-1111-5111-a111-111111111111',
        '88888888-8888-5888-a888-888888888888', '99999999-9999-5999-a999-999999999999',
        '33333333-3333-5333-a333-333333333333', now() - interval '1 day')
ON CONFLICT (id) DO NOTHING;

INSERT INTO triage_policy_versions
  (id, tenant_id, domain_id, policy_code, version_no, status,
   engine_version, input_schema_version, input_schema, unknown_priority,
   review_timeout_seconds, max_fact_age_seconds, max_queue_wait_seconds,
   policy_hash, created_by, published_by, published_at)
VALUES ('cccccccc-cccc-5ccc-accc-cccccccccccc',
        '11111111-1111-5111-a111-111111111111',
        '22222222-2222-5222-a222-222222222222',
        'local-triage', 1, 'published', 'local-v3', 'v3', '{}'::jsonb,
        'normal', 3600, 86400, 3600, 'local-demo-policy',
        'local-v3-admin', 'local-v3-admin', now())
ON CONFLICT (id) DO NOTHING;

INSERT INTO triage_policy_bindings
  (id, tenant_id, domain_id, scope_id, category_id, request_kind,
   policy_version_id, valid_from, status, configured_by)
VALUES ('dddddddd-dddd-5ddd-addd-dddddddddddd',
        '11111111-1111-5111-a111-111111111111',
        '22222222-2222-5222-a222-222222222222',
        '99999999-9999-5999-a999-999999999999',
        NULL, 'incident',
        'cccccccc-cccc-5ccc-accc-cccccccccccc',
        now() - interval '1 day', 'active', 'local-v3-admin')
ON CONFLICT (id) DO NOTHING;

INSERT INTO storage_locations
  (id, tenant_id, provider, endpoint_ref, bucket_name, tenant_prefix,
   credential_secret_ref, versioning_required, encryption_mode, purpose, status)
VALUES ('bbbbbbbb-bbbb-5bbb-abbb-bbbbbbbbbbbb',
        '11111111-1111-5111-a111-111111111111',
        'local_fs', 'vinhomes-api-local', 'vinhomes-local-v3', 'evidence/',
        'local-only', false, 'none', 'evidence', 'active')
ON CONFLICT (id) DO NOTHING;

INSERT INTO channels (id, tenant_id, name, description, kind)
VALUES ('local-v3-reception', '11111111-1111-5111-a111-111111111111', 'Local V3 Reception', 'Swagger local fixture', 'reception')
ON CONFLICT (id) DO NOTHING;

INSERT INTO tickets (
  id, tenant_id, code, requester_user_id, channel_id, domain_id,
  title, description, priority, status, contact_name, contact_phone,
  address_snapshot, request_kind
) VALUES (
  '44444444-4444-5444-a444-444444444444',
  '11111111-1111-5111-a111-111111111111',
  'LOCAL-V3-001', 'local-v3-admin', 'local-v3-reception',
  '22222222-2222-5222-a222-222222222222',
  'Demo technical ticket', 'Fixture for Swagger reads', 'normal', 'open',
  'Local Test', '0000000000', '{"label":"Local fixture"}'::jsonb, 'incident'
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO work_orders (
  id, tenant_id, ticket_id, category_id, description, status,
  required_specialty_id
) VALUES (
  '55555555-5555-5555-a555-555555555555',
  '11111111-1111-5111-a111-111111111111',
  '44444444-4444-5444-a444-444444444444',
  '33333333-3333-5333-a333-333333333333',
  'Inspect local demo issue', 'queued',
  '33333333-3333-5333-a333-333333333333'
)
ON CONFLICT (id) DO NOTHING;
COMMIT;
