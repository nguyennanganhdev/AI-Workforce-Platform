-- now() is constant within a transaction; random UUIDs cannot order a multipart handoff.
-- Preserve the existing timestamp/ID order when backfilling old commands.
ALTER TABLE platform_commands ADD COLUMN enqueue_seq bigint;
WITH ordered AS (
    SELECT id, row_number() OVER (ORDER BY created_at, id) AS position
    FROM platform_commands
)
UPDATE platform_commands c SET enqueue_seq = ordered.position
FROM ordered WHERE c.id = ordered.id;
ALTER TABLE platform_commands ALTER COLUMN enqueue_seq SET NOT NULL;
ALTER TABLE platform_commands ALTER COLUMN enqueue_seq ADD GENERATED ALWAYS AS IDENTITY;
SELECT setval(pg_get_serial_sequence('platform_commands', 'enqueue_seq'),
              coalesce(max(enqueue_seq), 0) + 1, false) FROM platform_commands;
CREATE INDEX platform_commands_pending_order
    ON platform_commands (tenant_id, ticket_id, enqueue_seq) WHERE status = 'pending';
