-- Due times by priority for every management unit and service category (clock runs around the clock).
-- A request takes the policy in force when it is created; requests already in the sample are brought up to date below.
SELECT set_config('app.tenant_id','11111111-1111-5111-a111-111111111111',true);

INSERT INTO sla_policies (tenant_id, management_unit_id, category_id, priority, response_minutes, resolution_minutes,
                          effective_from, domain_id, request_kind, version_no)
SELECT mu.tenant_id, mu.id, c.id, p.priority, p.response_minutes, p.resolution_minutes,
       '2026-01-01T00:00:00+00'::timestamptz, d.id, k.kind, 1
FROM management_units mu
JOIN service_categories c ON c.tenant_id = mu.tenant_id
JOIN domains d ON d.tenant_id = mu.tenant_id
CROSS JOIN (VALUES ('critical', 15, 240), ('high', 60, 1440), ('normal', 240, 4320), ('low', 1440, 10080)) AS p(priority, response_minutes, resolution_minutes)
CROSS JOIN (VALUES ('incident'), ('service_request')) AS k(kind)
WHERE mu.tenant_id = '11111111-1111-5111-a111-111111111111'
ON CONFLICT DO NOTHING;

-- Fires the assignment trigger for sample requests created before the policies existed.
UPDATE tickets SET priority = priority
WHERE tenant_id = '11111111-1111-5111-a111-111111111111' AND sla_policy_id IS NULL AND priority IS NOT NULL;
