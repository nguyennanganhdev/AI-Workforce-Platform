-- Completed/cancelled work must no longer consume the staff capacity enforced by
-- app_assignment_capacity(). Keep assignment identity and history intact.
UPDATE work_assignments a
SET status = w.status,
    ended_at = COALESCE(a.ended_at, w.completed_at, w.updated_at),
    updated_at = now()
FROM work_orders w
WHERE w.id = a.work_order_id AND w.tenant_id = a.tenant_id
  AND w.status IN ('completed', 'cancelled')
  AND a.status IN ('accepted', 'offered');
