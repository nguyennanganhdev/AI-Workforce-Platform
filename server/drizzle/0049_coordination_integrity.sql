-- Only additions from 0048. Preserve the 0046/0047 baseline and its ledger.
DO $$ DECLARE n text;
BEGIN
  FOREACH n IN ARRAY ARRAY[
    'platform_conversation','platform_conversation_subject','platform_conversation_message',
    'platform_session_participant','platform_session_control','platform_runtime_message',
    'platform_runtime_checkpoint','platform_session_wait','platform_handoff','platform_event_receipt',
    'vh_team','vh_team_member','vh_staff_skill','vh_staff_shift','vh_asset','vh_incident_asset',
    'vh_work_assignment','vh_work_appointment','vh_work_progress','vh_report_update',
    'vh_notification_delivery','vh_provider_event','vh_sla_policy','vh_incident_sla','vh_escalation'
  ] LOOP
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY',n);
    IF EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name=n AND column_name='updated_at') THEN
      EXECUTE format('CREATE TRIGGER workforce_touch BEFORE UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION workforce_touch()',n);
    END IF;
  END LOOP;
  FOREACH n IN ARRAY ARRAY['platform_conversation_subject','platform_conversation_message','platform_runtime_message','platform_runtime_checkpoint','vh_work_progress','vh_report_update'] LOOP
    EXECUTE format('CREATE TRIGGER workforce_immutable BEFORE UPDATE OR DELETE ON %I FOR EACH ROW EXECUTE FUNCTION workforce_append_only()',n);
    EXECUTE format('CREATE TRIGGER workforce_no_truncate BEFORE TRUNCATE ON %I FOR EACH STATEMENT EXECUTE FUNCTION workforce_append_only()',n);
  END LOOP;
END $$;
--> statement-breakpoint
CREATE FUNCTION workforce_coordination_identity() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE old_data jsonb:=to_jsonb(OLD); new_data jsonb:=to_jsonb(NEW); k text;
BEGIN
  -- Late acknowledgement/confirmation fields are explicit exceptions; references
  -- identifying a record cannot be silently moved to another conversation/task.
  FOR k IN SELECT jsonb_object_keys(old_data) LOOP
    IF (k LIKE '%\_id' ESCAPE '\' OR k IN ('idempotency_key','initiation_key','request_hash','payload_hash','sequence_no','provider','provider_event_id','event_id','consumer','producer_namespace'))
      AND k NOT IN ('target_workflow_session_id','coordinator_participant_id','confirmed_by_user_id','acknowledged_by_user_id')
      AND old_data->k IS DISTINCT FROM new_data->k THEN
      RAISE EXCEPTION '% identity field % is immutable',TG_TABLE_NAME,k USING ERRCODE='23514';
    END IF;
  END LOOP;
  RETURN NEW;
END $$;
--> statement-breakpoint
DO $$ DECLARE n text;
BEGIN
  FOREACH n IN ARRAY ARRAY['platform_conversation','platform_session_participant','platform_session_control','platform_session_wait','platform_handoff','platform_event_receipt','vh_team_member','vh_staff_skill','vh_staff_shift','vh_work_assignment','vh_work_appointment','vh_notification_delivery','vh_provider_event','vh_incident_sla','vh_escalation'] LOOP
    EXECUTE format('CREATE TRIGGER coordination_identity BEFORE UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION workforce_coordination_identity()',n);
  END LOOP;
END $$;
--> statement-breakpoint
CREATE FUNCTION platform_coordination_message() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE last_seq bigint; parent_seq bigint; owner_id text; sender platform_session_participant; run_version uuid;
BEGIN
  IF TG_TABLE_NAME='platform_conversation_message' THEN
    SELECT owner_user_id INTO owner_id FROM platform_conversation WHERE tenant_id=NEW.tenant_id AND id=NEW.conversation_id FOR UPDATE;
    SELECT coalesce(max(sequence_no),0) INTO last_seq FROM platform_conversation_message WHERE tenant_id=NEW.tenant_id AND conversation_id=NEW.conversation_id;
    IF NEW.role='USER' AND NEW.author_user_id IS DISTINCT FROM owner_id THEN
      RAISE EXCEPTION 'conversation message author must own the conversation' USING ERRCODE='23514';
    END IF;
    IF NEW.reply_to_message_id IS NOT NULL THEN
      SELECT sequence_no INTO parent_seq FROM platform_conversation_message WHERE tenant_id=NEW.tenant_id AND conversation_id=NEW.conversation_id AND id=NEW.reply_to_message_id;
    END IF;
  ELSE
    PERFORM 1 FROM platform_workflow_session WHERE tenant_id=NEW.tenant_id AND id=NEW.workflow_session_id FOR UPDATE;
    SELECT coalesce(max(sequence_no),0) INTO last_seq FROM platform_runtime_message WHERE tenant_id=NEW.tenant_id AND workflow_session_id=NEW.workflow_session_id;
    IF NEW.sender_participant_id IS NOT NULL THEN
      SELECT * INTO sender FROM platform_session_participant WHERE tenant_id=NEW.tenant_id AND workflow_session_id=NEW.workflow_session_id AND id=NEW.sender_participant_id FOR SHARE;
      IF sender.status IS DISTINCT FROM 'ACTIVE' THEN RAISE EXCEPTION 'sender is not an active session participant' USING ERRCODE='23514'; END IF;
      IF NEW.agent_run_id IS NOT NULL THEN
        SELECT agent_version_id INTO run_version FROM platform_agent_run WHERE tenant_id=NEW.tenant_id AND workflow_session_id=NEW.workflow_session_id AND id=NEW.agent_run_id;
        IF run_version IS DISTINCT FROM sender.agent_version_id THEN RAISE EXCEPTION 'message run must match sender agent version' USING ERRCODE='23514'; END IF;
      END IF;
    END IF;
    IF NEW.reply_to_message_id IS NOT NULL THEN
      SELECT sequence_no INTO parent_seq FROM platform_runtime_message WHERE tenant_id=NEW.tenant_id AND workflow_session_id=NEW.workflow_session_id AND id=NEW.reply_to_message_id;
    END IF;
  END IF;
  IF NEW.sequence_no <> last_seq+1 THEN RAISE EXCEPTION 'append message at the next sequence under its parent lock' USING ERRCODE='23514'; END IF;
  IF NEW.reply_to_message_id IS NOT NULL AND (parent_seq IS NULL OR parent_seq>=NEW.sequence_no) THEN
    RAISE EXCEPTION 'reply must reference an earlier message in the same conversation/session' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END $$;
--> statement-breakpoint
CREATE TRIGGER conversation_message_order BEFORE INSERT ON platform_conversation_message FOR EACH ROW EXECUTE FUNCTION platform_coordination_message();
--> statement-breakpoint
CREATE TRIGGER runtime_message_order BEFORE INSERT ON platform_runtime_message FOR EACH ROW EXECUTE FUNCTION platform_coordination_message();
--> statement-breakpoint
CREATE FUNCTION platform_session_control_integrity() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE cycle boolean; p platform_session_participant;
BEGIN
  -- Lock the tenant's control graph while introducing a parent edge.
  IF TG_OP='INSERT' THEN
    PERFORM 1 FROM platform_tenant WHERE id=NEW.tenant_id FOR UPDATE;
    WITH RECURSIVE ancestors(id) AS (
      SELECT NEW.parent_workflow_session_id
      UNION SELECT c.parent_workflow_session_id FROM platform_session_control c JOIN ancestors a ON c.workflow_session_id=a.id WHERE c.tenant_id=NEW.tenant_id
    ) SELECT EXISTS(SELECT 1 FROM ancestors WHERE id=NEW.workflow_session_id) INTO cycle;
    IF cycle THEN RAISE EXCEPTION 'session parent graph cannot contain a cycle' USING ERRCODE='23514'; END IF;
  ELSE
    IF NEW.purpose<>OLD.purpose OR NEW.fencing_token<OLD.fencing_token
      OR ((NEW.lease_owner IS DISTINCT FROM OLD.lease_owner OR (OLD.lease_expires_at<=clock_timestamp() AND NEW.lease_expires_at>clock_timestamp())) AND NEW.fencing_token<=OLD.fencing_token) THEN
      RAISE EXCEPTION 'session purpose is pinned; lease takeover must advance fencing token' USING ERRCODE='23514';
    END IF;
  END IF;
  IF NEW.coordinator_participant_id IS NOT NULL THEN
    SELECT * INTO p FROM platform_session_participant WHERE tenant_id=NEW.tenant_id AND workflow_session_id=NEW.workflow_session_id AND id=NEW.coordinator_participant_id;
    IF p.role IS DISTINCT FROM 'COORDINATOR' OR p.status NOT IN ('INVITED','ACTIVE') THEN RAISE EXCEPTION 'coordinator must be an eligible participant of this session' USING ERRCODE='23514'; END IF;
  END IF;
  RETURN NEW;
END $$;
--> statement-breakpoint
CREATE TRIGGER session_control_integrity BEFORE INSERT OR UPDATE ON platform_session_control FOR EACH ROW EXECUTE FUNCTION platform_session_control_integrity();
--> statement-breakpoint
CREATE FUNCTION platform_checkpoint_integrity() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE last_no bigint; last_seq bigint; control platform_session_control; provider text;
BEGIN
  SELECT runtime_provider INTO provider FROM platform_workflow_session WHERE tenant_id=NEW.tenant_id AND id=NEW.workflow_session_id FOR UPDATE;
  SELECT * INTO control FROM platform_session_control WHERE tenant_id=NEW.tenant_id AND workflow_session_id=NEW.workflow_session_id FOR SHARE;
  SELECT coalesce(max(checkpoint_no),0) INTO last_no FROM platform_runtime_checkpoint WHERE tenant_id=NEW.tenant_id AND workflow_session_id=NEW.workflow_session_id;
  SELECT coalesce(max(sequence_no),0) INTO last_seq FROM platform_runtime_message WHERE tenant_id=NEW.tenant_id AND workflow_session_id=NEW.workflow_session_id;
  IF control.id IS NULL OR NEW.fencing_token<>control.fencing_token OR control.lease_owner IS NULL OR control.lease_expires_at<=clock_timestamp() THEN
    RAISE EXCEPTION 'checkpoint requires the current live lease fencing token' USING ERRCODE='23514';
  END IF;
  IF NEW.checkpoint_no<>last_no+1 OR NEW.last_message_sequence>last_seq OR NEW.runtime_provider<>provider THEN
    RAISE EXCEPTION 'invalid checkpoint sequence, cursor or provider' USING ERRCODE='23514';
  END IF;
  IF EXISTS(SELECT 1 FROM platform_runtime_checkpoint WHERE tenant_id=NEW.tenant_id AND workflow_session_id=NEW.workflow_session_id AND last_message_sequence>NEW.last_message_sequence) THEN
    RAISE EXCEPTION 'checkpoint cursor cannot regress' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END $$;
--> statement-breakpoint
CREATE TRIGGER checkpoint_integrity BEFORE INSERT ON platform_runtime_checkpoint FOR EACH ROW EXECUTE FUNCTION platform_checkpoint_integrity();
--> statement-breakpoint
CREATE FUNCTION platform_handoff_integrity() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE target platform_workflow_session;
BEGIN
  IF TG_OP='INSERT' AND NEW.status<>'OFFERED' THEN
    RAISE EXCEPTION 'handoff must start as an offered request' USING ERRCODE='23514';
  END IF;
  IF TG_OP='UPDATE' THEN
    IF (NEW.domain_namespace,NEW.subject_type,NEW.subject_ref,NEW.subject_version,NEW.context_json,NEW.expires_at)
      IS DISTINCT FROM (OLD.domain_namespace,OLD.subject_type,OLD.subject_ref,OLD.subject_version,OLD.context_json,OLD.expires_at)
      OR (OLD.target_workflow_session_id IS NOT NULL AND NEW.target_workflow_session_id IS DISTINCT FROM OLD.target_workflow_session_id)
      OR (OLD.status IN ('COMPLETED','FAILED','EXPIRED','CANCELLED') AND NEW.status<>OLD.status) THEN
      RAISE EXCEPTION 'handoff subject, context and acknowledged destination are pinned' USING ERRCODE='23514';
    END IF;
    IF NEW.status<>OLD.status AND NOT ((OLD.status='OFFERED' AND NEW.status IN ('ACCEPTED','FAILED','EXPIRED','CANCELLED')) OR (OLD.status='ACCEPTED' AND NEW.status IN ('COMPLETED','FAILED','CANCELLED'))) THEN
      RAISE EXCEPTION 'invalid handoff transition' USING ERRCODE='23514';
    END IF;
  END IF;
  IF NEW.target_workflow_session_id IS NOT NULL THEN
    SELECT * INTO target FROM platform_workflow_session WHERE tenant_id=NEW.tenant_id AND id=NEW.target_workflow_session_id FOR SHARE;
    IF target.id IS NULL OR (target.domain_namespace,target.subject_type,target.subject_ref) IS DISTINCT FROM (NEW.domain_namespace,NEW.subject_type,NEW.subject_ref) THEN
      RAISE EXCEPTION 'handoff destination must process the same subject' USING ERRCODE='23514';
    END IF;
  END IF;
  IF NEW.status='ACCEPTED' AND (TG_OP='INSERT' OR OLD.status<>'ACCEPTED') THEN
    IF NEW.expires_at<=clock_timestamp() OR NEW.accepted_at>NEW.expires_at OR NOT EXISTS(SELECT 1 FROM platform_session_participant WHERE tenant_id=NEW.tenant_id AND workflow_session_id=NEW.target_workflow_session_id AND agent_version_id=NEW.target_agent_version_id AND status='ACTIVE') THEN
      RAISE EXCEPTION 'handoff acknowledgement requires an unexpired request and active target participant' USING ERRCODE='23514';
    END IF;
  END IF;
  RETURN NEW;
END $$;
--> statement-breakpoint
CREATE TRIGGER handoff_integrity BEFORE INSERT OR UPDATE ON platform_handoff FOR EACH ROW EXECUTE FUNCTION platform_handoff_integrity();
--> statement-breakpoint
ALTER TABLE vh_team_member ADD CONSTRAINT vh_team_member_no_overlap EXCLUDE USING gist
  (tenant_id WITH =, team_id WITH =, property_membership_id WITH =, tstzrange(valid_from,valid_until,'[)') WITH &&) WHERE (status='ACTIVE');
--> statement-breakpoint
ALTER TABLE vh_work_appointment ADD CONSTRAINT vh_work_appointment_no_overlap EXCLUDE USING gist
  (tenant_id WITH =, work_order_id WITH =, tstzrange(starts_at,ends_at,'[)') WITH &&) WHERE (status IN ('PROPOSED','CONFIRMED'));
--> statement-breakpoint
CREATE FUNCTION vh_staff_membership_integrity() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE member vh_property_membership;
BEGIN
  SELECT * INTO member FROM vh_property_membership WHERE tenant_id=NEW.tenant_id AND project_id=NEW.project_id AND id=NEW.property_membership_id FOR SHARE;
  IF member.membership_type NOT IN ('STAFF','CONTRACTOR','MANAGER') OR member.id IS NULL THEN
    RAISE EXCEPTION 'workforce records require staff, contractor or manager membership' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END $$;
--> statement-breakpoint
CREATE TRIGGER staff_membership BEFORE INSERT OR UPDATE ON vh_team_member FOR EACH ROW EXECUTE FUNCTION vh_staff_membership_integrity();
--> statement-breakpoint
CREATE TRIGGER staff_skill_membership BEFORE INSERT OR UPDATE ON vh_staff_skill FOR EACH ROW EXECUTE FUNCTION vh_staff_membership_integrity();
--> statement-breakpoint
CREATE FUNCTION vh_staff_shift_integrity() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE membership uuid; target_user text;
BEGIN
  SELECT property_membership_id INTO membership FROM vh_team_member WHERE tenant_id=NEW.tenant_id AND id=NEW.team_member_id;
  SELECT user_id INTO target_user FROM vh_property_membership WHERE tenant_id=NEW.tenant_id AND id=membership;
  -- Lock the shared identity to serialize shifts across teams/property memberships.
  PERFORM 1 FROM users WHERE id=target_user FOR UPDATE;
  IF NEW.status IN ('PLANNED','CONFIRMED') AND EXISTS(
    SELECT 1 FROM vh_staff_shift s JOIN vh_team_member t ON t.tenant_id=s.tenant_id AND t.id=s.team_member_id
    JOIN vh_property_membership m ON m.tenant_id=t.tenant_id AND m.id=t.property_membership_id
    WHERE s.tenant_id=NEW.tenant_id AND s.id<>NEW.id AND m.user_id=target_user AND s.status IN ('PLANNED','CONFIRMED')
      AND tstzrange(s.starts_at,s.ends_at,'[)') && tstzrange(NEW.starts_at,NEW.ends_at,'[)')
  ) THEN RAISE EXCEPTION 'staff member has an overlapping shift within this tenant' USING ERRCODE='23514'; END IF;
  RETURN NEW;
END $$;
--> statement-breakpoint
CREATE TRIGGER staff_shift_integrity BEFORE INSERT OR UPDATE ON vh_staff_shift FOR EACH ROW EXECUTE FUNCTION vh_staff_shift_integrity();
--> statement-breakpoint
CREATE FUNCTION vh_field_parent_integrity() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE w vh_work_order; team_member vh_team_member;
BEGIN
  SELECT * INTO w FROM vh_work_order WHERE tenant_id=NEW.tenant_id AND id=NEW.work_order_id FOR UPDATE;
  IF TG_TABLE_NAME='vh_work_assignment' THEN
    IF TG_OP='UPDATE' AND OLD.status IN ('REJECTED','RELEASED','COMPLETED') THEN RAISE EXCEPTION 'closed assignment is historical; create another assignment' USING ERRCODE='23514'; END IF;
    IF NEW.status IN ('OFFERED','ACCEPTED') THEN
      IF w.status IN ('COMPLETED','FAILED','CANCELLED') THEN RAISE EXCEPTION 'cannot assign a terminal work order' USING ERRCODE='23514'; END IF;
      IF NOT EXISTS(SELECT 1 FROM vh_team WHERE tenant_id=NEW.tenant_id AND id=NEW.team_id AND status='ACTIVE') THEN RAISE EXCEPTION 'assignment team must be active' USING ERRCODE='23514'; END IF;
      IF NEW.team_member_id IS NOT NULL THEN
        SELECT * INTO team_member FROM vh_team_member WHERE tenant_id=NEW.tenant_id AND id=NEW.team_member_id;
        IF team_member.status IS DISTINCT FROM 'ACTIVE' OR team_member.valid_from>clock_timestamp() OR team_member.valid_until<=clock_timestamp()
          OR NOT EXISTS(SELECT 1 FROM vh_property_membership WHERE tenant_id=NEW.tenant_id AND id=team_member.property_membership_id AND status='ACTIVE' AND valid_from<=clock_timestamp() AND (valid_until IS NULL OR valid_until>clock_timestamp())) THEN
          RAISE EXCEPTION 'assignment member is not currently eligible' USING ERRCODE='23514';
        END IF;
      END IF;
    END IF;
  ELSE
    IF TG_OP='UPDATE' AND (OLD.status IN ('COMPLETED','CANCELLED') OR (NEW.starts_at,NEW.ends_at) IS DISTINCT FROM (OLD.starts_at,OLD.ends_at)) THEN
      RAISE EXCEPTION 'rescheduling creates a new appointment after cancellation' USING ERRCODE='23514';
    END IF;
    IF NEW.resident_report_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM vh_resident_report WHERE tenant_id=NEW.tenant_id AND id=NEW.resident_report_id AND incident_id=NEW.incident_id) THEN
      RAISE EXCEPTION 'appointment report must belong to the work order incident' USING ERRCODE='23514';
    END IF;
  END IF;
  RETURN NEW;
END $$;
--> statement-breakpoint
CREATE TRIGGER field_assignment_integrity BEFORE INSERT OR UPDATE ON vh_work_assignment FOR EACH ROW EXECUTE FUNCTION vh_field_parent_integrity();
--> statement-breakpoint
CREATE TRIGGER field_appointment_integrity BEFORE INSERT OR UPDATE ON vh_work_appointment FOR EACH ROW EXECUTE FUNCTION vh_field_parent_integrity();
--> statement-breakpoint
CREATE FUNCTION vh_progress_provenance() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE e vh_business_event; p vh_work_progress; next_seq bigint;
BEGIN
  SELECT * INTO e FROM vh_business_event WHERE tenant_id=NEW.tenant_id AND id=NEW.business_event_id;
  IF e.incident_id IS DISTINCT FROM NEW.incident_id THEN RAISE EXCEPTION 'progress event must belong to the same incident' USING ERRCODE='23514'; END IF;
  IF TG_TABLE_NAME='vh_work_progress' THEN
    IF e.subject_type<>'WORK_ORDER' OR e.subject_id<>NEW.work_order_id OR e.actor_type<>'HUMAN' OR e.actor_id<>NEW.actor_user_id OR e.occurred_at<>NEW.occurred_at THEN
      RAISE EXCEPTION 'field progress requires the work order event and actual human actor' USING ERRCODE='23514';
    END IF;
  ELSE
    IF NEW.source_occurred_at<>e.occurred_at OR NOT EXISTS(SELECT 1 FROM vh_incident WHERE tenant_id=NEW.tenant_id AND id=NEW.incident_id AND version>=NEW.incident_version) THEN
      RAISE EXCEPTION 'resident projection must reference an existing incident version and exact source time' USING ERRCODE='23514';
    END IF;
    PERFORM 1 FROM vh_resident_report WHERE tenant_id=NEW.tenant_id AND id=NEW.report_id FOR UPDATE;
    SELECT coalesce(max(sequence_no),0)+1 INTO next_seq FROM vh_report_update WHERE tenant_id=NEW.tenant_id AND report_id=NEW.report_id;
    IF NEW.sequence_no<>next_seq THEN RAISE EXCEPTION 'report update must append at next sequence' USING ERRCODE='23514'; END IF;
    IF NEW.work_progress_id IS NOT NULL THEN
      SELECT * INTO p FROM vh_work_progress WHERE tenant_id=NEW.tenant_id AND id=NEW.work_progress_id;
      IF p.business_event_id IS DISTINCT FROM NEW.business_event_id OR p.expected_completion_at IS DISTINCT FROM NEW.expected_completion_at THEN
        RAISE EXCEPTION 'resident ETA/provenance must match the confirmed field update' USING ERRCODE='23514';
      END IF;
    ELSIF NEW.expected_completion_at IS NOT NULL THEN
      RAISE EXCEPTION 'resident ETA requires a confirmed field update' USING ERRCODE='23514';
    END IF;
    IF EXISTS(SELECT 1 FROM vh_report_update WHERE tenant_id=NEW.tenant_id AND report_id=NEW.report_id AND (incident_version>NEW.incident_version OR source_occurred_at>NEW.source_occurred_at)) THEN
      RAISE EXCEPTION 'resident progress cannot regress to an older source' USING ERRCODE='23514';
    END IF;
  END IF;
  RETURN NEW;
END $$;
--> statement-breakpoint
CREATE TRIGGER field_progress_provenance BEFORE INSERT ON vh_work_progress FOR EACH ROW EXECUTE FUNCTION vh_progress_provenance();
--> statement-breakpoint
CREATE TRIGGER resident_update_provenance BEFORE INSERT ON vh_report_update FOR EACH ROW EXECUTE FUNCTION vh_progress_provenance();
--> statement-breakpoint
CREATE FUNCTION vh_delivery_recipient() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.report_update_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM vh_notification n JOIN vh_report_update u ON u.tenant_id=n.tenant_id AND u.project_id=n.project_id AND u.recipient_user_id=n.recipient_id AND u.business_event_id=n.business_event_id
    WHERE n.tenant_id=NEW.tenant_id AND n.id=NEW.notification_id AND u.id=NEW.report_update_id) THEN
    RAISE EXCEPTION 'delivery must use the report update recipient and source event' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END $$;
--> statement-breakpoint
CREATE TRIGGER notification_delivery_recipient BEFORE INSERT OR UPDATE ON vh_notification_delivery FOR EACH ROW EXECUTE FUNCTION vh_delivery_recipient();
--> statement-breakpoint
CREATE FUNCTION vh_sla_integrity() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE p vh_sla_policy; i vh_incident;
BEGIN
  SELECT * INTO p FROM vh_sla_policy WHERE tenant_id=NEW.tenant_id AND id=NEW.policy_id FOR SHARE;
  SELECT * INTO i FROM vh_incident WHERE tenant_id=NEW.tenant_id AND id=NEW.incident_id FOR UPDATE;
  IF TG_OP='INSERT' THEN
    IF p.status IS DISTINCT FROM 'PUBLISHED' OR p.category<>i.category OR p.severity<>i.severity OR p.effective_from>NEW.started_at OR p.effective_until<=NEW.started_at THEN
      RAISE EXCEPTION 'incident SLA requires an applicable published policy' USING ERRCODE='23514';
    END IF;
  ELSIF (NEW.started_at,NEW.response_due_at,NEW.resolution_due_at) IS DISTINCT FROM (OLD.started_at,OLD.response_due_at,OLD.resolution_due_at) THEN
    RAISE EXCEPTION 'SLA deadlines are pinned at application time' USING ERRCODE='23514';
  END IF;
  IF NEW.response_due_at<>NEW.started_at+make_interval(mins=>p.response_minutes) OR NEW.resolution_due_at<>NEW.started_at+make_interval(mins=>p.resolution_minutes) THEN
    RAISE EXCEPTION 'SLA deadlines must match elapsed-time policy' USING ERRCODE='23514';
  END IF;
  IF i.sla_due_at IS NOT NULL AND i.sla_due_at<>NEW.resolution_due_at THEN
    RAISE EXCEPTION 'legacy incident deadline and SLA deadline disagree' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END $$;
--> statement-breakpoint
CREATE TRIGGER sla_policy_pinned BEFORE UPDATE OR DELETE ON vh_sla_policy FOR EACH ROW EXECUTE FUNCTION workforce_published_content();
--> statement-breakpoint
CREATE TRIGGER incident_sla_integrity BEFORE INSERT OR UPDATE ON vh_incident_sla FOR EACH ROW EXECUTE FUNCTION vh_sla_integrity();
--> statement-breakpoint
CREATE FUNCTION vh_incident_sla_deadline_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF EXISTS(SELECT 1 FROM vh_incident_sla WHERE tenant_id=NEW.tenant_id AND incident_id=NEW.id AND NEW.sla_due_at IS DISTINCT FROM resolution_due_at) THEN
    RAISE EXCEPTION 'incident SLA deadline is owned by the pinned SLA record' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END $$;
--> statement-breakpoint
CREATE TRIGGER incident_sla_deadline_guard BEFORE UPDATE OF sla_due_at ON vh_incident FOR EACH ROW EXECUTE FUNCTION vh_incident_sla_deadline_guard();
--> statement-breakpoint
CREATE FUNCTION vh_sla_mirror_deadline() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  UPDATE vh_incident SET sla_due_at=NEW.resolution_due_at WHERE tenant_id=NEW.tenant_id AND id=NEW.incident_id AND sla_due_at IS DISTINCT FROM NEW.resolution_due_at;
  RETURN NEW;
END $$;
--> statement-breakpoint
CREATE TRIGGER incident_sla_mirror AFTER INSERT ON vh_incident_sla FOR EACH ROW EXECUTE FUNCTION vh_sla_mirror_deadline();
--> statement-breakpoint
CREATE FUNCTION vh_asset_location_integrity() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.apartment_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM vh_apartment WHERE tenant_id=NEW.tenant_id AND project_id=NEW.project_id AND tower_id=NEW.tower_id AND id=NEW.apartment_id) THEN
    RAISE EXCEPTION 'asset apartment must belong to its tower and project' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END $$;
--> statement-breakpoint
CREATE TRIGGER asset_location_integrity BEFORE INSERT OR UPDATE ON vh_asset FOR EACH ROW EXECUTE FUNCTION vh_asset_location_integrity();
--> statement-breakpoint
CREATE FUNCTION platform_coordination_scope() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_TABLE_NAME='platform_workflow_session' THEN
    IF (NEW.domain_namespace,NEW.subject_type,NEW.subject_ref,NEW.runtime_provider,NEW.environment) IS DISTINCT FROM
       (OLD.domain_namespace,OLD.subject_type,OLD.subject_ref,OLD.runtime_provider,OLD.environment) THEN
      RAISE EXCEPTION 'workflow session subject, environment and provider are pinned' USING ERRCODE='23514';
    END IF;
  ELSIF NEW.status='ACTIVE' AND EXISTS(SELECT 1 FROM platform_workflow_session WHERE tenant_id=NEW.tenant_id AND id=NEW.workflow_session_id AND environment='PRODUCTION') THEN
    IF NOT EXISTS(SELECT 1 FROM platform_agent_version v JOIN platform_agent_deployment d ON d.tenant_id=v.tenant_id AND d.agent_version_id=v.id
      WHERE v.tenant_id=NEW.tenant_id AND v.id=NEW.agent_version_id AND v.status='PUBLISHED' AND d.environment='PRODUCTION' AND d.status='ACTIVE') THEN
      RAISE EXCEPTION 'production participant requires a published and deployed agent version' USING ERRCODE='23514';
    END IF;
  END IF;
  RETURN NEW;
END $$;
--> statement-breakpoint
CREATE TRIGGER workflow_session_scope BEFORE UPDATE ON platform_workflow_session FOR EACH ROW EXECUTE FUNCTION platform_coordination_scope();
--> statement-breakpoint
CREATE TRIGGER session_participant_eligibility BEFORE INSERT OR UPDATE ON platform_session_participant FOR EACH ROW EXECUTE FUNCTION platform_coordination_scope();
