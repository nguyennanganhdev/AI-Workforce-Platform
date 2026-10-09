-- Removes the eight tables nothing uses (see docs/domain/KIEM_KE_BANG.md, group H) and the four columns that
-- pointed at them. None of them has a row in the seed, the mock world or any test, and no code reads or writes them:
--   SLA cycles / escalations / adjustments   superseded by sla_policies + the app_assign_sla trigger (0007)
--   dispatch_queue / dispatch_attempts       a dispatcher that was never built
--   triage_rules                             decisions are proposed by people; no rule engine exists
--   payment_webhook_receipts                 no payment provider is connected
--   event_inbox                              the domain only publishes events (event_outbox)
-- Tables are dropped without CASCADE so that anything unexpected still depending on them stops the migration.

-- The one function that read triage_rules: the same checks, minus the rule lookup.
CREATE OR REPLACE FUNCTION public.app_validate_triage_decision()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
DECLARE a ticket_assessments; b triage_policy_bindings; t tickets; r ticket_triage_reviews;
BEGIN
 SELECT * INTO STRICT a FROM ticket_assessments WHERE id=NEW.assessment_id AND tenant_id=NEW.tenant_id;
 SELECT * INTO STRICT t FROM tickets WHERE id=NEW.ticket_id AND tenant_id=NEW.tenant_id FOR UPDATE;
 SELECT * INTO STRICT b FROM triage_policy_bindings WHERE id=NEW.policy_binding_id AND tenant_id=NEW.tenant_id;
 IF a.ticket_id<>t.id OR a.ticket_generation<>NEW.ticket_generation OR b.policy_version_id<>NEW.policy_version_id OR b.domain_id<>t.domain_id THEN RAISE EXCEPTION 'Triage decision source mismatch'; END IF;
 IF NEW.outcome='applied' THEN
  IF t.reopen_count<>NEW.ticket_generation OR t.version<>NEW.basis_ticket_version OR t.current_triage_decision_id IS DISTINCT FROM NEW.previous_applied_id THEN RAISE EXCEPTION 'Stale triage decision' USING ERRCODE='40001'; END IF;
  IF NEW.applied_ticket_version<>t.version+1 THEN RAISE EXCEPTION 'Invalid applied version'; END IF;
  IF NEW.review_id IS NOT NULL THEN
   SELECT * INTO STRICT r FROM ticket_triage_reviews WHERE id=NEW.review_id AND ticket_id=t.id AND ticket_generation=NEW.ticket_generation;
  END IF;
  IF NEW.approved_by IS NULL AND ((array_position(ARRAY['low','normal','high','critical'],NEW.priority)<array_position(ARRAY['low','normal','high','critical'],t.priority)) OR (t.is_emergency AND NOT NEW.is_emergency) OR (array_position(ARRAY['unknown','minor','moderate','major','critical'],NEW.severity)<array_position(ARRAY['unknown','minor','moderate','major','critical'],t.severity))) THEN RAISE EXCEPTION 'Downgrade requires authorized human review'; END IF;
 END IF;
 RETURN NEW;
END $function$
;

ALTER TABLE public.tickets DROP COLUMN active_sla_cycle_id;
ALTER TABLE public.work_assignments DROP COLUMN dispatch_attempt_id;
ALTER TABLE public.ticket_triage_decisions DROP COLUMN matched_rule_id;
ALTER TABLE public.payments DROP COLUMN receipt_id;

DROP TABLE public.ticket_escalations;
DROP TABLE public.ticket_sla_adjustments;
DROP TABLE public.ticket_sla_cycles;
DROP TABLE public.dispatch_attempts;
DROP TABLE public.dispatch_queue;
DROP TABLE public.triage_rules;
DROP TABLE public.payment_webhook_receipts;
DROP TABLE public.event_inbox;
