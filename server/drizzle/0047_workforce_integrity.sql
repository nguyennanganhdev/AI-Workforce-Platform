-- Deliberate hand-written complement to 0046. Drizzle snapshots do not model
-- triggers, exclusion constraints or FORCE RLS. Preserve this migration.
CREATE EXTENSION IF NOT EXISTS btree_gist;
--> statement-breakpoint
CREATE FUNCTION workforce_touch() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF (to_jsonb(NEW)->'id') IS DISTINCT FROM (to_jsonb(OLD)->'id')
    OR (to_jsonb(NEW)->'tenant_id') IS DISTINCT FROM (to_jsonb(OLD)->'tenant_id')
    OR (to_jsonb(NEW)->'project_id') IS DISTINCT FROM (to_jsonb(OLD)->'project_id')
    OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
    RAISE EXCEPTION 'identity and ownership cannot be changed' USING ERRCODE = '23514';
  END IF;
  IF NEW.version NOT IN (OLD.version, OLD.version + 1) THEN
    RAISE EXCEPTION 'invalid optimistic version' USING ERRCODE = '40001';
  END IF;
  NEW.version := OLD.version + 1;
  NEW.updated_at := clock_timestamp();
  RETURN NEW;
END $$;
--> statement-breakpoint
CREATE FUNCTION workforce_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION '% is append-only', TG_TABLE_NAME USING ERRCODE = '23514';
END $$;
--> statement-breakpoint
-- Install version and tenant defenses only on the new model, not the OpenBot shell.
DO $$ DECLARE r record;
BEGIN
  FOR r IN SELECT table_name FROM information_schema.tables
    WHERE table_schema = 'public' AND (table_name LIKE 'platform\_%' ESCAPE '\' OR table_name LIKE 'vh\_%' ESCAPE '\')
  LOOP
    IF r.table_name <> 'platform_domain_package' THEN
      EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', r.table_name);
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name=r.table_name AND column_name='updated_at') THEN
      EXECUTE format('CREATE TRIGGER workforce_touch BEFORE UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION workforce_touch()', r.table_name);
    END IF;
  END LOOP;
END $$;
--> statement-breakpoint
DO $$ DECLARE n text;
BEGIN
  FOREACH n IN ARRAY ARRAY[
    'platform_skill_version','platform_eval_assertion','platform_eval_evidence',
    'platform_publish_gate_result','platform_publish_approval','platform_runtime_artifact',
    'platform_runtime_decision','platform_memory_review','platform_audit_event',
    'vh_resident_confirmation','vh_feedback','vh_evidence_ref','vh_qc_result',
    'vh_qc_result_evidence','vh_message','vh_business_event','vh_rule_evaluation',
    'vh_intercom_event','vh_payment_allocation','vh_loyalty_entry','vh_sensor_reading',
    'platform_memory_revision'
  ] LOOP
    IF n = 'platform_memory_revision' THEN
      EXECUTE format('CREATE TRIGGER workforce_immutable BEFORE DELETE ON %I FOR EACH ROW EXECUTE FUNCTION workforce_append_only()', n);
    ELSE
      EXECUTE format('CREATE TRIGGER workforce_immutable BEFORE UPDATE OR DELETE ON %I FOR EACH ROW EXECUTE FUNCTION workforce_append_only()', n);
    END IF;
    EXECUTE format('CREATE TRIGGER workforce_no_truncate BEFORE TRUNCATE ON %I FOR EACH STATEMENT EXECUTE FUNCTION workforce_append_only()', n);
  END LOOP;
END $$;
--> statement-breakpoint
ALTER TABLE vh_property_membership ADD CONSTRAINT vh_membership_no_overlap
  EXCLUDE USING gist (tenant_id WITH =, user_id WITH =,
    (coalesce(apartment_id, tower_id, project_id)) WITH =, membership_type WITH =,
    tstzrange(valid_from, valid_until, '[)') WITH &&) WHERE (status = 'ACTIVE');
--> statement-breakpoint
-- Shared-capacity resources use one slot with capacity N, not overlapping slots.
ALTER TABLE vh_time_slot ADD CONSTRAINT vh_slot_no_overlap
  EXCLUDE USING gist (tenant_id WITH =, facility_id WITH =,
    tstzrange(starts_at, ends_at, '[)') WITH &&);
--> statement-breakpoint
CREATE FUNCTION workforce_pin_action() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF (to_jsonb(NEW) - ARRAY['status','version','updated_at']) IS DISTINCT FROM
     (to_jsonb(OLD) - ARRAY['status','version','updated_at']) THEN
    RAISE EXCEPTION 'an action payload is immutable; propose a new action' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END $$;
--> statement-breakpoint
CREATE TRIGGER vh_action_pinned BEFORE UPDATE ON vh_action_request
  FOR EACH ROW EXECUTE FUNCTION workforce_pin_action();
--> statement-breakpoint
CREATE FUNCTION vh_check_redo() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE predecessor vh_work_order; last_qc text;
BEGIN
  IF TG_OP = 'UPDATE' THEN
    IF OLD.status IN ('COMPLETED','FAILED','CANCELLED') THEN
      RAISE EXCEPTION 'terminal work order is immutable; create a redo' USING ERRCODE='23514';
    END IF;
    IF (NEW.task_id, NEW.incident_id, NEW.action_request_id, NEW.attempt_no, NEW.redo_of_work_order_id)
      IS DISTINCT FROM (OLD.task_id, OLD.incident_id, OLD.action_request_id, OLD.attempt_no, OLD.redo_of_work_order_id) THEN
      RAISE EXCEPTION 'work order lineage is immutable' USING ERRCODE='23514';
    END IF;
  END IF;
  IF NEW.redo_of_work_order_id IS NOT NULL THEN
    SELECT * INTO predecessor FROM vh_work_order WHERE tenant_id=NEW.tenant_id AND id=NEW.redo_of_work_order_id FOR UPDATE;
    SELECT outcome INTO last_qc FROM vh_qc_result WHERE tenant_id=NEW.tenant_id AND work_order_id=predecessor.id ORDER BY checked_at DESC, created_at DESC, id DESC LIMIT 1;
    IF predecessor.id IS NULL OR predecessor.task_id <> NEW.task_id OR predecessor.attempt_no >= NEW.attempt_no OR last_qc IS DISTINCT FROM 'FAIL' THEN
      RAISE EXCEPTION 'redo requires an earlier attempt of the same task with failed QC' USING ERRCODE='23514';
    END IF;
  ELSIF NEW.attempt_no <> 1 THEN
    RAISE EXCEPTION 'later attempts must reference their predecessor' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END $$;
--> statement-breakpoint
CREATE TRIGGER vh_work_order_lineage BEFORE INSERT OR UPDATE ON vh_work_order
  FOR EACH ROW EXECUTE FUNCTION vh_check_redo();
--> statement-breakpoint
CREATE FUNCTION workforce_dependency_acyclic() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE has_cycle boolean;
BEGIN
  IF TG_OP='UPDATE' THEN
    RAISE EXCEPTION 'replace dependency edges using delete and insert' USING ERRCODE='23514';
  END IF;
  IF TG_TABLE_NAME='vh_task_dependency' THEN
    -- Serialize edits to this graph, including edges inserted by another transaction.
    PERFORM 1 FROM vh_incident WHERE tenant_id=NEW.tenant_id AND id=NEW.incident_id FOR UPDATE;
    WITH RECURSIVE reach(id) AS (
      SELECT NEW.depends_on_task_id
      UNION SELECT d.depends_on_task_id FROM vh_task_dependency d JOIN reach r ON d.task_id=r.id
        WHERE d.tenant_id=NEW.tenant_id AND d.incident_id=NEW.incident_id
    ) SELECT EXISTS(SELECT 1 FROM reach WHERE id=NEW.task_id) INTO has_cycle;
  ELSE
    PERFORM 1 FROM platform_workflow_session WHERE tenant_id=NEW.tenant_id AND id=NEW.workflow_session_id FOR UPDATE;
    WITH RECURSIVE reach(id) AS (
      SELECT NEW.depends_on_run_step_id
      UNION SELECT d.depends_on_run_step_id FROM platform_run_step_dependency d JOIN reach r ON d.run_step_id=r.id
        WHERE d.tenant_id=NEW.tenant_id AND d.workflow_session_id=NEW.workflow_session_id
    ) SELECT EXISTS(SELECT 1 FROM reach WHERE id=NEW.run_step_id) INTO has_cycle;
  END IF;
  IF has_cycle THEN RAISE EXCEPTION 'dependency graph cannot contain a cycle' USING ERRCODE='23514'; END IF;
  RETURN NEW;
END $$;
--> statement-breakpoint
CREATE TRIGGER vh_dependency_graph BEFORE INSERT OR UPDATE ON vh_task_dependency
  FOR EACH ROW EXECUTE FUNCTION workforce_dependency_acyclic();
--> statement-breakpoint
CREATE TRIGGER platform_dependency_graph BEFORE INSERT OR UPDATE ON platform_run_step_dependency
  FOR EACH ROW EXECUTE FUNCTION workforce_dependency_acyclic();
--> statement-breakpoint
CREATE FUNCTION vh_available_attachment() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE f vh_file_object;
BEGIN
  SELECT * INTO f FROM vh_file_object WHERE tenant_id=NEW.tenant_id AND id=NEW.file_id FOR SHARE;
  IF f.upload_status IS DISTINCT FROM 'AVAILABLE' THEN
    RAISE EXCEPTION 'only available files may be attached' USING ERRCODE='23514';
  END IF;
  IF TG_TABLE_NAME='vh_membership_application_file' AND f.visibility <> 'PRIVATE' THEN
    RAISE EXCEPTION 'membership proof must remain private' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END $$;
--> statement-breakpoint
DO $$ DECLARE n text;
BEGIN
  FOREACH n IN ARRAY ARRAY['vh_membership_application_file','vh_request_attachment','vh_report_attachment','vh_pet_document','vh_service_request_file','vh_evidence_ref'] LOOP
    EXECUTE format('CREATE TRIGGER vh_file_available BEFORE INSERT OR UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION vh_available_attachment()', n);
  END LOOP;
END $$;
--> statement-breakpoint
CREATE FUNCTION vh_confirmation_current() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE i vh_incident;
BEGIN
  SELECT * INTO i FROM vh_incident WHERE tenant_id=NEW.tenant_id AND id=NEW.incident_id FOR UPDATE;
  IF i.status IS DISTINCT FROM 'RESOLVED' OR i.resolution_version IS DISTINCT FROM NEW.resolution_version THEN
    RAISE EXCEPTION 'confirmation must refer to the current resolution round' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END $$;
--> statement-breakpoint
CREATE TRIGGER vh_confirmation_round BEFORE INSERT ON vh_resident_confirmation
  FOR EACH ROW EXECUTE FUNCTION vh_confirmation_current();
--> statement-breakpoint
CREATE FUNCTION vh_booking_capacity() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE slot vh_time_slot; occupied bigint;
BEGIN
  IF TG_OP='UPDATE' THEN
    IF (NEW.slot_id,NEW.apartment_id,NEW.booked_by_membership_id,NEW.price_minor,NEW.currency)
      IS DISTINCT FROM (OLD.slot_id,OLD.apartment_id,OLD.booked_by_membership_id,OLD.price_minor,OLD.currency) THEN
      RAISE EXCEPTION 'booking scope and price are immutable' USING ERRCODE='23514';
    END IF;
    IF OLD.status IN ('CANCELLED','EXPIRED','COMPLETED') AND NEW.status<>OLD.status THEN
      RAISE EXCEPTION 'terminal booking cannot be reactivated' USING ERRCODE='23514';
    END IF;
  END IF;
  SELECT * INTO slot FROM vh_time_slot WHERE tenant_id=NEW.tenant_id AND id=NEW.slot_id FOR UPDATE;
  IF NEW.status IN ('HELD','CONFIRMED') THEN
    IF slot.status IS DISTINCT FROM 'OPEN' OR slot.starts_at <= clock_timestamp() THEN
      RAISE EXCEPTION 'slot is not open for booking' USING ERRCODE='23514';
    END IF;
    IF NEW.status='HELD' AND NEW.hold_expires_at <= clock_timestamp() THEN
      RAISE EXCEPTION 'new hold must be unexpired' USING ERRCODE='23514';
    END IF;
    SELECT coalesce(sum(party_size),0) INTO occupied FROM vh_booking
      WHERE tenant_id=NEW.tenant_id AND slot_id=NEW.slot_id AND id<>NEW.id
      AND (status='CONFIRMED' OR (status='HELD' AND hold_expires_at>clock_timestamp()));
    IF occupied + NEW.party_size > slot.capacity THEN
      RAISE EXCEPTION 'slot capacity exceeded' USING ERRCODE='23514';
    END IF;
  END IF;
  RETURN NEW;
END $$;
--> statement-breakpoint
CREATE TRIGGER vh_booking_capacity BEFORE INSERT OR UPDATE ON vh_booking
  FOR EACH ROW EXECUTE FUNCTION vh_booking_capacity();
--> statement-breakpoint
CREATE FUNCTION vh_slot_capacity() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE occupied bigint;
BEGIN
  IF (NEW.facility_id,NEW.starts_at,NEW.ends_at) IS DISTINCT FROM (OLD.facility_id,OLD.starts_at,OLD.ends_at) THEN
    RAISE EXCEPTION 'replace a slot instead of moving existing reservations' USING ERRCODE='23514';
  END IF;
  SELECT coalesce(sum(party_size),0) INTO occupied FROM vh_booking WHERE tenant_id=NEW.tenant_id AND slot_id=NEW.id
    AND (status='CONFIRMED' OR (status='HELD' AND hold_expires_at>clock_timestamp()));
  IF occupied > NEW.capacity THEN RAISE EXCEPTION 'capacity below active reservations' USING ERRCODE='23514'; END IF;
  RETURN NEW;
END $$;
--> statement-breakpoint
CREATE TRIGGER vh_slot_capacity BEFORE UPDATE ON vh_time_slot
  FOR EACH ROW EXECUTE FUNCTION vh_slot_capacity();
--> statement-breakpoint
CREATE FUNCTION vh_event_capacity() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE e vh_community_event; occupied bigint;
BEGIN
  IF TG_OP='UPDATE' AND (NEW.event_id,NEW.membership_id) IS DISTINCT FROM (OLD.event_id,OLD.membership_id) THEN
    RAISE EXCEPTION 'registration scope is immutable' USING ERRCODE='23514';
  END IF;
  SELECT * INTO e FROM vh_community_event WHERE tenant_id=NEW.tenant_id AND id=NEW.event_id FOR UPDATE;
  IF NEW.status='ATTENDED' AND (TG_OP='INSERT' OR OLD.status NOT IN ('REGISTERED','ATTENDED')) THEN
    RAISE EXCEPTION 'attendance requires an existing registration' USING ERRCODE='23514';
  END IF;
  IF NEW.status IN ('REGISTERED','ATTENDED') THEN
    IF NEW.status='REGISTERED' AND (e.status IS DISTINCT FROM 'PUBLISHED' OR e.registration_closes_at <= clock_timestamp()) THEN
      RAISE EXCEPTION 'event registration is closed' USING ERRCODE='23514';
    END IF;
    SELECT coalesce(sum(1+guest_count),0) INTO occupied FROM vh_event_registration
      WHERE tenant_id=NEW.tenant_id AND event_id=NEW.event_id AND id<>NEW.id AND status IN ('REGISTERED','ATTENDED');
    IF occupied + 1 + NEW.guest_count > e.capacity THEN RAISE EXCEPTION 'event capacity exceeded' USING ERRCODE='23514'; END IF;
  END IF;
  RETURN NEW;
END $$;
--> statement-breakpoint
CREATE TRIGGER vh_event_capacity BEFORE INSERT OR UPDATE ON vh_event_registration
  FOR EACH ROW EXECUTE FUNCTION vh_event_capacity();
--> statement-breakpoint
CREATE FUNCTION vh_pin_payment() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF (NEW.invoice_id, NEW.initiated_by_user_id, NEW.amount_minor, NEW.currency, NEW.provider, NEW.idempotency_key)
    IS DISTINCT FROM (OLD.invoice_id, OLD.initiated_by_user_id, OLD.amount_minor, OLD.currency, OLD.provider, OLD.idempotency_key)
    OR (OLD.provider_payment_ref IS NOT NULL AND NEW.provider_payment_ref IS DISTINCT FROM OLD.provider_payment_ref)
    OR (OLD.status IN ('SUCCEEDED','FAILED','CANCELLED','SIMULATED') AND NEW.status<>OLD.status)
    OR (OLD.confirmed_at IS NOT NULL AND NEW.confirmed_at IS DISTINCT FROM OLD.confirmed_at) THEN
    RAISE EXCEPTION 'submitted payment terms and terminal outcome are immutable' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END $$;
--> statement-breakpoint
CREATE TRIGGER vh_payment_pinned BEFORE UPDATE ON vh_payment_attempt
  FOR EACH ROW EXECUTE FUNCTION vh_pin_payment();
--> statement-breakpoint
CREATE FUNCTION vh_allocate_payment() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE inv vh_invoice; payment vh_payment_attempt; paid bigint; allocated bigint;
BEGIN
  -- All allocation writers take the invoice lock first, then payment, in the same order.
  SELECT * INTO inv FROM vh_invoice WHERE tenant_id=NEW.tenant_id AND id=NEW.invoice_id FOR UPDATE;
  SELECT * INTO payment FROM vh_payment_attempt WHERE tenant_id=NEW.tenant_id AND id=NEW.payment_attempt_id FOR UPDATE;
  IF inv.status NOT IN ('ISSUED','PARTIALLY_PAID') OR payment.status IS DISTINCT FROM 'SUCCEEDED'
    OR payment.invoice_id IS DISTINCT FROM NEW.invoice_id OR payment.currency IS DISTINCT FROM inv.currency THEN
    RAISE EXCEPTION 'allocation requires a verified successful payment of this invoice and currency' USING ERRCODE='23514';
  END IF;
  SELECT coalesce(sum(amount_minor),0) INTO paid FROM vh_payment_allocation WHERE tenant_id=NEW.tenant_id AND invoice_id=NEW.invoice_id;
  SELECT coalesce(sum(amount_minor),0) INTO allocated FROM vh_payment_allocation WHERE tenant_id=NEW.tenant_id AND payment_attempt_id=NEW.payment_attempt_id;
  IF paid+NEW.amount_minor > inv.total_minor OR allocated+NEW.amount_minor > payment.amount_minor THEN
    RAISE EXCEPTION 'payment over-allocation' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END $$;
--> statement-breakpoint
CREATE TRIGGER vh_payment_allocate BEFORE INSERT ON vh_payment_allocation
  FOR EACH ROW EXECUTE FUNCTION vh_allocate_payment();
--> statement-breakpoint
CREATE FUNCTION vh_invoice_integrity() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE inv vh_invoice; line_total numeric; allocated numeric;
BEGIN
  IF TG_TABLE_NAME='vh_invoice_line' THEN
    IF TG_OP='UPDATE' AND NEW.invoice_id<>OLD.invoice_id THEN
      RAISE EXCEPTION 'invoice line cannot move between invoices' USING ERRCODE='23514';
    END IF;
    SELECT * INTO inv FROM vh_invoice WHERE tenant_id=coalesce(NEW.tenant_id,OLD.tenant_id) AND id=coalesce(NEW.invoice_id,OLD.invoice_id) FOR UPDATE;
    IF inv.status IS DISTINCT FROM 'DRAFT' THEN RAISE EXCEPTION 'issued invoice lines are immutable' USING ERRCODE='23514'; END IF;
    IF TG_OP='DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
  END IF;
  IF TG_OP='INSERT' AND NEW.status<>'DRAFT' THEN RAISE EXCEPTION 'create invoice as draft before adding lines' USING ERRCODE='23514'; END IF;
  IF TG_OP='UPDATE' AND OLD.status<>'DRAFT' THEN
    IF NEW.status='DRAFT' OR (NEW.apartment_id,NEW.billed_to_user_id,NEW.invoice_number,NEW.period_start,NEW.period_end,NEW.total_minor,NEW.currency)
      IS DISTINCT FROM (OLD.apartment_id,OLD.billed_to_user_id,OLD.invoice_number,OLD.period_start,OLD.period_end,OLD.total_minor,OLD.currency) THEN
      RAISE EXCEPTION 'issued invoice terms are immutable' USING ERRCODE='23514';
    END IF;
  END IF;
  IF NEW.status<>'DRAFT' THEN
    SELECT coalesce(sum(total_minor),0) INTO line_total FROM vh_invoice_line WHERE tenant_id=NEW.tenant_id AND invoice_id=NEW.id;
    IF line_total<>NEW.total_minor THEN RAISE EXCEPTION 'invoice total differs from rounded line totals' USING ERRCODE='23514'; END IF;
    SELECT coalesce(sum(amount_minor),0) INTO allocated FROM vh_payment_allocation WHERE tenant_id=NEW.tenant_id AND invoice_id=NEW.id;
    IF (NEW.status='PAID' AND allocated<>NEW.total_minor)
      OR (NEW.status='PARTIALLY_PAID' AND NOT (allocated>0 AND allocated<NEW.total_minor))
      OR (NEW.status IN ('ISSUED','VOID') AND allocated<>0) THEN
      RAISE EXCEPTION 'invoice status contradicts payment allocations' USING ERRCODE='23514';
    END IF;
  END IF;
  RETURN NEW;
END $$;
--> statement-breakpoint
CREATE TRIGGER vh_invoice_terms BEFORE INSERT OR UPDATE ON vh_invoice
  FOR EACH ROW EXECUTE FUNCTION vh_invoice_integrity();
--> statement-breakpoint
CREATE TRIGGER vh_invoice_line_terms BEFORE INSERT OR UPDATE OR DELETE ON vh_invoice_line
  FOR EACH ROW EXECUTE FUNCTION vh_invoice_integrity();
--> statement-breakpoint
CREATE FUNCTION vh_settle_invoice() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  UPDATE vh_invoice SET status = CASE WHEN total_minor=(SELECT sum(amount_minor) FROM vh_payment_allocation WHERE tenant_id=NEW.tenant_id AND invoice_id=NEW.invoice_id) THEN 'PAID' ELSE 'PARTIALLY_PAID' END
    WHERE tenant_id=NEW.tenant_id AND id=NEW.invoice_id;
  RETURN NEW;
END $$;
--> statement-breakpoint
CREATE TRIGGER vh_invoice_settlement AFTER INSERT ON vh_payment_allocation
  FOR EACH ROW EXECUTE FUNCTION vh_settle_invoice();
--> statement-breakpoint
CREATE FUNCTION workforce_published_content() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.status <> 'DRAFT' THEN
    IF TG_OP='DELETE' THEN RAISE EXCEPTION 'published content cannot be deleted' USING ERRCODE='23514'; END IF;
    IF (to_jsonb(NEW)-ARRAY['status','version','updated_at']) IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['status','version','updated_at']) OR NEW.status='DRAFT' THEN
      RAISE EXCEPTION 'published content is immutable; create a new revision' USING ERRCODE='23514';
    END IF;
  END IF;
  IF TG_OP='DELETE' THEN RETURN OLD; END IF;
  RETURN NEW;
END $$;
--> statement-breakpoint
DO $$ DECLARE n text;
BEGIN
  FOREACH n IN ARRAY ARRAY['vh_checklist_version','vh_fee_schedule','platform_policy_version','platform_tool_version','platform_knowledge_revision'] LOOP
    EXECUTE format('CREATE TRIGGER workforce_content_pinned BEFORE UPDATE OR DELETE ON %I FOR EACH ROW EXECUTE FUNCTION workforce_published_content()', n);
  END LOOP;
END $$;
--> statement-breakpoint
CREATE FUNCTION platform_freeze_spec() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v platform_agent_version; version_id uuid; tenant uuid;
BEGIN
  version_id := coalesce(NEW.agent_version_id, OLD.agent_version_id);
  tenant := coalesce(NEW.tenant_id, OLD.tenant_id);
  IF TG_OP='UPDATE' AND (NEW.tenant_id,NEW.agent_version_id) IS DISTINCT FROM (OLD.tenant_id,OLD.agent_version_id) THEN
    RAISE EXCEPTION 'specification/binding cannot move between agent revisions' USING ERRCODE='23514';
  END IF;
  SELECT * INTO v FROM platform_agent_version WHERE tenant_id=tenant AND id=version_id FOR UPDATE;
  IF v.status NOT IN ('DRAFT','NEEDS_INPUT') THEN
    RAISE EXCEPTION 'evaluated agent specification and bindings are frozen' USING ERRCODE='23514';
  END IF;
  IF TG_OP='DELETE' THEN RETURN OLD; END IF;
  RETURN NEW;
END $$;
--> statement-breakpoint
DO $$ DECLARE n text;
BEGIN
  FOREACH n IN ARRAY ARRAY['platform_agent_spec','platform_agent_capability_binding','platform_agent_model_binding','platform_agent_tool_binding','platform_agent_skill_binding','platform_agent_knowledge_binding','platform_agent_policy_binding'] LOOP
    EXECUTE format('CREATE TRIGGER platform_frozen_spec BEFORE INSERT OR UPDATE OR DELETE ON %I FOR EACH ROW EXECUTE FUNCTION platform_freeze_spec()', n);
    EXECUTE format('CREATE TRIGGER platform_no_truncate BEFORE TRUNCATE ON %I FOR EACH STATEMENT EXECUTE FUNCTION workforce_append_only()', n);
  END LOOP;
END $$;
--> statement-breakpoint
CREATE FUNCTION platform_version_lifecycle() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE passed_gate uuid;
BEGIN
  IF TG_OP='INSERT' THEN
    IF NEW.status<>'DRAFT' THEN RAISE EXCEPTION 'new agent versions start as DRAFT' USING ERRCODE='23514'; END IF;
    RETURN NEW;
  END IF;
  IF TG_OP='DELETE' THEN
    IF OLD.status NOT IN ('DRAFT','NEEDS_INPUT') THEN RAISE EXCEPTION 'evaluated versions cannot be deleted' USING ERRCODE='23514'; END IF;
    RETURN OLD;
  END IF;
  IF OLD.status NOT IN ('DRAFT','NEEDS_INPUT') THEN
    IF (NEW.agent_id,NEW.version_no,NEW.spec_hash,NEW.created_by) IS DISTINCT FROM (OLD.agent_id,OLD.version_no,OLD.spec_hash,OLD.created_by)
      OR NEW.status IN ('DRAFT','NEEDS_INPUT') THEN
      RAISE EXCEPTION 'evaluated agent revision is immutable' USING ERRCODE='23514';
    END IF;
  END IF;
  IF NEW.status<>OLD.status AND NOT (
    (OLD.status='DRAFT' AND NEW.status IN ('NEEDS_INPUT','READY_FOR_EVAL')) OR
    (OLD.status='NEEDS_INPUT' AND NEW.status IN ('DRAFT','READY_FOR_EVAL')) OR
    (OLD.status='READY_FOR_EVAL' AND NEW.status IN ('EVALUATING','RETIRED')) OR
    (OLD.status='EVALUATING' AND NEW.status IN ('READY_FOR_REVIEW','RETIRED')) OR
    (OLD.status='READY_FOR_REVIEW' AND NEW.status IN ('READY_FOR_PUBLISH','RETIRED')) OR
    (OLD.status='READY_FOR_PUBLISH' AND NEW.status IN ('PUBLISHED','RETIRED')) OR
    (OLD.status='PUBLISHED' AND NEW.status IN ('SUSPENDED','RETIRED')) OR
    (OLD.status='SUSPENDED' AND NEW.status IN ('PUBLISHED','RETIRED'))
  ) THEN RAISE EXCEPTION 'invalid agent version transition' USING ERRCODE='23514'; END IF;
  IF NEW.status='READY_FOR_EVAL' AND NOT EXISTS(SELECT 1 FROM platform_agent_spec WHERE tenant_id=NEW.tenant_id AND agent_version_id=NEW.id) THEN
    RAISE EXCEPTION 'evaluation requires a specification' USING ERRCODE='23514';
  END IF;
  IF NEW.status='PUBLISHED' AND OLD.status<>'PUBLISHED' THEN
    SELECT g.id INTO passed_gate FROM platform_publish_gate g
      WHERE g.tenant_id=NEW.tenant_id AND g.agent_version_id=NEW.id AND g.status='PASSED'
      AND (SELECT count(*) FROM platform_publish_gate_result r WHERE r.tenant_id=g.tenant_id AND r.publish_gate_id=g.id AND r.status='PASS')=4
      AND (SELECT count(*) FROM platform_publish_approval a WHERE a.tenant_id=g.tenant_id AND a.publish_gate_id=g.id AND a.status='APPROVED' AND a.reviewer_id<>NEW.created_by)=4
      ORDER BY g.created_at DESC LIMIT 1;
    IF passed_gate IS NULL OR NOT EXISTS(SELECT 1 FROM platform_eval_run WHERE tenant_id=NEW.tenant_id AND agent_version_id=NEW.id AND status='PASSED') THEN
      RAISE EXCEPTION 'publication requires successful evaluation, all gates and independent approvals' USING ERRCODE='23514';
    END IF;
    NEW.published_at := coalesce(OLD.published_at,clock_timestamp());
  END IF;
  IF NEW.status='SUSPENDED' AND OLD.status<>'SUSPENDED' THEN NEW.suspended_at:=clock_timestamp(); END IF;
  IF NEW.status='RETIRED' AND OLD.status<>'RETIRED' THEN NEW.retired_at:=clock_timestamp(); END IF;
  RETURN NEW;
END $$;
--> statement-breakpoint
CREATE TRIGGER platform_version_lifecycle BEFORE INSERT OR UPDATE OR DELETE ON platform_agent_version
  FOR EACH ROW EXECUTE FUNCTION platform_version_lifecycle();
--> statement-breakpoint
CREATE FUNCTION platform_deployment_eligible() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE version_status text;
BEGIN
  IF NEW.status='ACTIVE' THEN
    SELECT status INTO version_status FROM platform_agent_version WHERE tenant_id=NEW.tenant_id AND id=NEW.agent_version_id FOR SHARE;
    IF version_status IS DISTINCT FROM 'PUBLISHED' THEN RAISE EXCEPTION 'only published versions can be deployed' USING ERRCODE='23514'; END IF;
    IF NEW.domain_installation_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM platform_domain_installation WHERE tenant_id=NEW.tenant_id AND id=NEW.domain_installation_id AND environment=NEW.environment AND status='ENABLED') THEN
      RAISE EXCEPTION 'deployment requires an enabled installation in the same environment' USING ERRCODE='23514';
    END IF;
  END IF;
  RETURN NEW;
END $$;
--> statement-breakpoint
CREATE TRIGGER platform_deployment_eligible BEFORE INSERT OR UPDATE ON platform_agent_deployment
  FOR EACH ROW EXECUTE FUNCTION platform_deployment_eligible();
--> statement-breakpoint
CREATE FUNCTION platform_memory_vector_approved() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE revision platform_memory_revision; decision text;
BEGIN
  SELECT * INTO revision FROM platform_memory_revision WHERE tenant_id=NEW.tenant_id AND id=NEW.memory_revision_id FOR UPDATE;
  IF NEW.sync_status IN ('PENDING','SYNCED') THEN
    SELECT r.decision INTO decision FROM platform_memory_review r WHERE r.tenant_id=NEW.tenant_id AND r.memory_revision_id=NEW.memory_revision_id ORDER BY reviewed_at DESC,created_at DESC,id DESC LIMIT 1;
    IF revision.redaction_status IS DISTINCT FROM 'CLEAN' OR decision IS DISTINCT FROM 'APPROVED' THEN
      RAISE EXCEPTION 'vector sync requires an approved clean memory revision' USING ERRCODE='23514';
    END IF;
  END IF;
  RETURN NEW;
END $$;
--> statement-breakpoint
CREATE TRIGGER platform_vector_approved BEFORE INSERT OR UPDATE ON platform_memory_vector_ref
  FOR EACH ROW EXECUTE FUNCTION platform_memory_vector_approved();
--> statement-breakpoint
CREATE FUNCTION platform_memory_review_lock() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  PERFORM 1 FROM platform_memory_revision WHERE tenant_id=NEW.tenant_id AND id=NEW.memory_revision_id FOR UPDATE;
  IF EXISTS(SELECT 1 FROM platform_memory_review WHERE tenant_id=NEW.tenant_id AND memory_revision_id=NEW.memory_revision_id AND reviewed_at>=NEW.reviewed_at) THEN
    RAISE EXCEPTION 'memory reviews must advance review time' USING ERRCODE='23514';
  END IF;
  IF NEW.decision<>'APPROVED' THEN
    UPDATE platform_memory_vector_ref SET sync_status='DELETE_PENDING' WHERE tenant_id=NEW.tenant_id AND memory_revision_id=NEW.memory_revision_id AND sync_status NOT IN ('DELETED','DELETE_PENDING');
  END IF;
  RETURN NEW;
END $$;
--> statement-breakpoint
CREATE TRIGGER platform_memory_review_lock BEFORE INSERT ON platform_memory_review
  FOR EACH ROW EXECUTE FUNCTION platform_memory_review_lock();
--> statement-breakpoint
CREATE FUNCTION platform_memory_content_pinned() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF (to_jsonb(NEW)-'redaction_status') IS DISTINCT FROM (to_jsonb(OLD)-'redaction_status') THEN
    RAISE EXCEPTION 'memory revision content is immutable' USING ERRCODE='23514';
  END IF;
  IF NEW.redaction_status<>'CLEAN' THEN
    UPDATE platform_memory_vector_ref SET sync_status='DELETE_PENDING' WHERE tenant_id=NEW.tenant_id AND memory_revision_id=NEW.id AND sync_status NOT IN ('DELETED','DELETE_PENDING');
  END IF;
  RETURN NEW;
END $$;
--> statement-breakpoint
CREATE TRIGGER platform_memory_content_pinned BEFORE UPDATE ON platform_memory_revision
  FOR EACH ROW EXECUTE FUNCTION platform_memory_content_pinned();
--> statement-breakpoint
CREATE FUNCTION vh_receipt_pinned() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.status='COMPLETED' OR (NEW.actor_user_id,NEW.command_type,NEW.idempotency_key,NEW.payload_hash)
    IS DISTINCT FROM (OLD.actor_user_id,OLD.command_type,OLD.idempotency_key,OLD.payload_hash) THEN
    RAISE EXCEPTION 'command identity and completed receipt are immutable' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END $$;
--> statement-breakpoint
CREATE TRIGGER vh_receipt_pinned BEFORE UPDATE ON vh_command_receipt
  FOR EACH ROW EXECUTE FUNCTION vh_receipt_pinned();
--> statement-breakpoint
CREATE FUNCTION platform_run_eligible() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE session_environment text; version_status text;
BEGIN
  IF TG_OP='UPDATE' AND (NEW.agent_id,NEW.agent_version_id,NEW.workflow_session_id,NEW.run_step_id)
    IS DISTINCT FROM (OLD.agent_id,OLD.agent_version_id,OLD.workflow_session_id,OLD.run_step_id) THEN
    RAISE EXCEPTION 'run pins its agent version and session' USING ERRCODE='23514';
  END IF;
  SELECT environment INTO session_environment FROM platform_workflow_session WHERE tenant_id=NEW.tenant_id AND id=NEW.workflow_session_id FOR SHARE;
  IF session_environment='PRODUCTION' AND NEW.status IN ('PENDING','RUNNING') THEN
    SELECT status INTO version_status FROM platform_agent_version WHERE tenant_id=NEW.tenant_id AND id=NEW.agent_version_id FOR SHARE;
    IF version_status IS DISTINCT FROM 'PUBLISHED' OR NOT EXISTS(SELECT 1 FROM platform_agent_deployment WHERE tenant_id=NEW.tenant_id AND agent_version_id=NEW.agent_version_id AND environment='PRODUCTION' AND status='ACTIVE') THEN
      RAISE EXCEPTION 'production run requires a published version with an active deployment' USING ERRCODE='23514';
    END IF;
  END IF;
  RETURN NEW;
END $$;
--> statement-breakpoint
CREATE TRIGGER platform_run_eligible BEFORE INSERT OR UPDATE ON platform_agent_run
  FOR EACH ROW EXECUTE FUNCTION platform_run_eligible();
--> statement-breakpoint
CREATE FUNCTION platform_evaluation_scope() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM platform_eval_run r JOIN platform_eval_case c ON c.tenant_id=r.tenant_id AND c.eval_suite_id=r.eval_suite_id
    WHERE r.tenant_id=NEW.tenant_id AND r.id=NEW.eval_run_id AND c.id=NEW.eval_case_id) THEN
    RAISE EXCEPTION 'assertion case must belong to the evaluated suite' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END $$;
--> statement-breakpoint
CREATE TRIGGER platform_evaluation_scope BEFORE INSERT ON platform_eval_assertion
  FOR EACH ROW EXECUTE FUNCTION platform_evaluation_scope();
--> statement-breakpoint
CREATE FUNCTION platform_mcp_version_pinned() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF (to_jsonb(NEW)-ARRAY['security_status','version','updated_at']) IS DISTINCT FROM
    (to_jsonb(OLD)-ARRAY['security_status','version','updated_at']) THEN
    RAISE EXCEPTION 'MCP schema and fingerprint are immutable; create a revision' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END $$;
--> statement-breakpoint
CREATE TRIGGER platform_mcp_version_pinned BEFORE UPDATE ON platform_mcp_server_version
  FOR EACH ROW EXECUTE FUNCTION platform_mcp_version_pinned();
--> statement-breakpoint
CREATE FUNCTION platform_eval_case_pinned() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE suite_id uuid; tenant uuid;
BEGIN
  suite_id:=coalesce(NEW.eval_suite_id,OLD.eval_suite_id);
  tenant:=coalesce(NEW.tenant_id,OLD.tenant_id);
  IF TG_OP='UPDATE' AND (NEW.eval_suite_id,NEW.tenant_id) IS DISTINCT FROM (OLD.eval_suite_id,OLD.tenant_id) THEN
    RAISE EXCEPTION 'evaluation case cannot change suite' USING ERRCODE='23514';
  END IF;
  PERFORM 1 FROM platform_eval_suite WHERE tenant_id=tenant AND id=suite_id FOR UPDATE;
  IF EXISTS(SELECT 1 FROM platform_eval_run WHERE tenant_id=tenant AND eval_suite_id=suite_id) THEN
    RAISE EXCEPTION 'evaluated suites are frozen; create a new suite revision' USING ERRCODE='23514';
  END IF;
  IF TG_OP='DELETE' THEN RETURN OLD; END IF;
  RETURN NEW;
END $$;
--> statement-breakpoint
CREATE TRIGGER platform_eval_case_pinned BEFORE INSERT OR UPDATE OR DELETE ON platform_eval_case
  FOR EACH ROW EXECUTE FUNCTION platform_eval_case_pinned();
--> statement-breakpoint
CREATE FUNCTION platform_eval_run_pin_suite() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  PERFORM 1 FROM platform_eval_suite WHERE tenant_id=NEW.tenant_id AND id=NEW.eval_suite_id FOR UPDATE;
  IF TG_OP='UPDATE' AND (NEW.eval_suite_id,NEW.agent_version_id,NEW.environment_snapshot,NEW.model_snapshot)
    IS DISTINCT FROM (OLD.eval_suite_id,OLD.agent_version_id,OLD.environment_snapshot,OLD.model_snapshot) THEN
    RAISE EXCEPTION 'evaluation run pins its suite, version and environment' USING ERRCODE='23514';
  END IF;
  IF TG_OP='UPDATE' AND OLD.status IN ('PASSED','FAILED','CANCELLED') THEN
    RAISE EXCEPTION 'completed evaluation is immutable' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END $$;
--> statement-breakpoint
CREATE TRIGGER platform_eval_run_pin_suite BEFORE INSERT OR UPDATE ON platform_eval_run
  FOR EACH ROW EXECUTE FUNCTION platform_eval_run_pin_suite();
--> statement-breakpoint
CREATE FUNCTION vh_event_capacity_floor() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE occupied bigint;
BEGIN
  SELECT coalesce(sum(1+guest_count),0) INTO occupied FROM vh_event_registration WHERE tenant_id=NEW.tenant_id AND event_id=NEW.id AND status IN ('REGISTERED','ATTENDED');
  IF NEW.capacity<occupied THEN RAISE EXCEPTION 'event capacity below registrations' USING ERRCODE='23514'; END IF;
  RETURN NEW;
END $$;
--> statement-breakpoint
CREATE TRIGGER vh_event_capacity_floor BEFORE UPDATE ON vh_community_event
  FOR EACH ROW EXECUTE FUNCTION vh_event_capacity_floor();
