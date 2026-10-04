-- A plan may be proposed by the Supervisor agent of a ticket's session instead of by a person.
-- It enters the same lifecycle: management decides, then the resident.
ALTER TABLE vh_ticket_plans ALTER COLUMN proposed_by DROP NOT NULL;
--> statement-breakpoint
ALTER TABLE vh_ticket_plans ADD COLUMN proposed_by_agent_id text;
--> statement-breakpoint
ALTER TABLE vh_ticket_plans
  ADD CONSTRAINT vh_ticket_plans_proposed_by_agent_fk
  FOREIGN KEY(tenant_id,proposed_by_agent_id) REFERENCES agents(tenant_id,id) ON DELETE RESTRICT;
--> statement-breakpoint
ALTER TABLE vh_ticket_plans
  ADD CONSTRAINT vh_ticket_plans_author_check
  CHECK(num_nonnulls(proposed_by,proposed_by_agent_id)=1);
--> statement-breakpoint
-- What the Supervisor proposed beyond the steps: who performs it, how long, under which conditions,
-- whether a cost is known, and which specialist replies it relies on. Null for a person's plan.
ALTER TABLE vh_ticket_plans ADD COLUMN proposal jsonb;
