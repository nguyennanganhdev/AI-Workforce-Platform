-- Domain Vinhomes database. Generated once from the running schema, then kept by hand.
-- Every table has tenant_id and row level security that is forced; the API runs as a role that cannot bypass it.

CREATE OR REPLACE FUNCTION public.app_agent_version_scope()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
 IF NOT EXISTS(SELECT 1 FROM agent_versions WHERE id=NEW.version_id AND tenant_id=NEW.tenant_id AND agent_id=NEW.agent_id) THEN RAISE EXCEPTION 'Agent version belongs to another agent'; END IF; RETURN NEW;
END $function$
;

CREATE OR REPLACE FUNCTION public.app_append_only()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN RAISE EXCEPTION '% is append-only (% refused)', TG_TABLE_NAME,TG_OP USING ERRCODE='23514'; END $function$
;

CREATE OR REPLACE FUNCTION public.app_assignment_capacity()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
DECLARE capacity integer; used integer;
BEGIN
 IF NEW.status NOT IN ('offered','accepted') THEN RETURN NEW; END IF;
 SELECT max_concurrent_jobs INTO STRICT capacity FROM staff_profiles
 WHERE id=NEW.staff_id AND tenant_id=NEW.tenant_id FOR UPDATE;
 SELECT count(*) INTO used FROM work_assignments a
 JOIN work_orders w ON w.id=a.work_order_id AND w.tenant_id=a.tenant_id
 WHERE a.tenant_id=NEW.tenant_id AND a.staff_id=NEW.staff_id AND a.id<>NEW.id
 AND w.status NOT IN ('completed','cancelled','rejected')
 AND (a.status='accepted' OR (a.status='offered' AND a.offer_expires_at>now()));
 IF used>=capacity THEN RAISE EXCEPTION 'Staff capacity exhausted' USING ERRCODE='23514'; END IF;
 IF NEW.status='offered' AND (NEW.offer_expires_at IS NULL OR NEW.offer_expires_at<=now()) THEN RAISE EXCEPTION 'Offer must have a future expiry'; END IF;
 IF NEW.status='accepted' AND (NEW.accepted_at IS NULL OR NEW.eta_at IS NULL) THEN RAISE EXCEPTION 'Accepted assignment requires acknowledgment and ETA'; END IF;
 RETURN NEW;
END $function$
;

CREATE OR REPLACE FUNCTION public.app_check_applied_decision()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
 IF NEW.outcome='applied' AND NOT EXISTS (
  SELECT 1 FROM tickets WHERE id=NEW.ticket_id AND current_triage_decision_id=NEW.id
   AND version>=NEW.applied_ticket_version AND reopen_count=NEW.ticket_generation
 ) THEN RAISE EXCEPTION 'Applied decision and ticket projection must commit together'; END IF;
 RETURN NULL;
END $function$
;

CREATE OR REPLACE FUNCTION public.app_check_ticket_projection()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
DECLARE d ticket_triage_decisions; current_ticket tickets;
BEGIN
 -- Read final row at deferred time, rather than a stale NEW image from an earlier update.
 SELECT * INTO current_ticket FROM tickets WHERE id=NEW.id;
 IF current_ticket.current_triage_decision_id IS NOT NULL THEN
  SELECT * INTO STRICT d FROM ticket_triage_decisions WHERE id=current_ticket.current_triage_decision_id;
  IF d.ticket_id<>current_ticket.id OR d.ticket_generation<>current_ticket.reopen_count OR d.outcome<>'applied' OR (d.priority,d.severity,d.is_emergency) IS DISTINCT FROM (current_ticket.priority,current_ticket.severity,current_ticket.is_emergency) THEN RAISE EXCEPTION 'Ticket projection differs from applied decision'; END IF;
 END IF;
 RETURN NULL;
END $function$
;

CREATE OR REPLACE FUNCTION public.app_policy_immutable()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
DECLARE version_id uuid; state text;
BEGIN
 IF TG_TABLE_NAME='triage_policy_versions' THEN
  IF OLD.status<>'draft' AND (to_jsonb(NEW)-'status'-'updated_at') IS DISTINCT FROM (to_jsonb(OLD)-'status'-'updated_at') THEN RAISE EXCEPTION 'Published policy content is immutable'; END IF;
  IF OLD.status<>'draft' AND NEW.status='draft' THEN RAISE EXCEPTION 'Published policy cannot return to draft'; END IF;
  RETURN NEW;
 END IF;
 IF TG_OP='UPDATE' THEN
  SELECT status INTO STRICT state FROM triage_policy_versions WHERE id=OLD.policy_version_id FOR UPDATE;
  IF state<>'draft' THEN RAISE EXCEPTION 'Published rules are immutable'; END IF;
 END IF;
 IF TG_OP='DELETE' THEN version_id=OLD.policy_version_id; ELSE version_id=NEW.policy_version_id; END IF;
 SELECT status INTO STRICT state FROM triage_policy_versions WHERE id=version_id FOR UPDATE;
 IF state<>'draft' THEN RAISE EXCEPTION 'Published rules are immutable'; END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
END $function$
;

CREATE OR REPLACE FUNCTION public.app_touch_updated_at()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN NEW.updated_at=clock_timestamp(); RETURN NEW; END $function$
;

CREATE OR REPLACE FUNCTION public.app_validate_evidence()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
DECLARE f files; w work_orders; a work_assignments;
BEGIN
 SELECT * INTO STRICT f FROM files WHERE id=NEW.file_id AND tenant_id=NEW.tenant_id;
 IF f.ticket_id IS DISTINCT FROM NEW.ticket_id OR f.scope_kind<>'ticket' OR f.status<>'ready' THEN RAISE EXCEPTION 'Evidence file is not ready or belongs to another ticket'; END IF;
 IF NEW.purpose IN ('before','after') AND (NEW.work_order_id IS NULL OR NEW.assignment_id IS NULL) THEN RAISE EXCEPTION 'Before/after evidence requires assignment'; END IF;
 IF NEW.work_order_id IS NOT NULL THEN
  SELECT * INTO STRICT w FROM work_orders WHERE id=NEW.work_order_id AND ticket_id=NEW.ticket_id;
 END IF;
 IF NEW.assignment_id IS NOT NULL THEN
  SELECT * INTO STRICT a FROM work_assignments WHERE id=NEW.assignment_id AND work_order_id=NEW.work_order_id;
 END IF;
 IF TG_OP='UPDATE' AND (NEW.ticket_id,NEW.work_order_id,NEW.assignment_id,NEW.file_id,NEW.purpose,NEW.uploaded_by) IS DISTINCT FROM (OLD.ticket_id,OLD.work_order_id,OLD.assignment_id,OLD.file_id,OLD.purpose,OLD.uploaded_by) THEN RAISE EXCEPTION 'Evidence provenance is immutable'; END IF;
 RETURN NEW;
END $function$
;

CREATE OR REPLACE FUNCTION public.app_validate_file()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
DECLARE obj file_objects;
BEGIN
 IF NEW.accepted_object_id IS NOT NULL THEN
  SELECT * INTO STRICT obj FROM file_objects WHERE id=NEW.accepted_object_id AND tenant_id=NEW.tenant_id;
  IF obj.file_id<>NEW.id OR obj.variant<>'original' THEN RAISE EXCEPTION 'Accepted original object belongs to a different file'; END IF;
  IF NEW.status='ready' AND (obj.status<>'ready' OR obj.scan_status<>'clean' OR obj.verified_at IS NULL) THEN RAISE EXCEPTION 'File is not verified'; END IF;
 END IF;
 IF TG_OP='UPDATE' AND OLD.accepted_object_id IS NOT NULL AND NEW.accepted_object_id IS DISTINCT FROM OLD.accepted_object_id THEN RAISE EXCEPTION 'Accepted bytes are immutable'; END IF;
 IF TG_OP='UPDATE' AND (NEW.tenant_id,NEW.owner_principal_id,NEW.scope_kind,NEW.ticket_id,NEW.channel_id,NEW.unit_id) IS DISTINCT FROM (OLD.tenant_id,OLD.owner_principal_id,OLD.scope_kind,OLD.ticket_id,OLD.channel_id,OLD.unit_id) THEN RAISE EXCEPTION 'File security scope is immutable'; END IF;
 RETURN NEW;
END $function$
;

CREATE OR REPLACE FUNCTION public.app_validate_object()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
DECLARE loc storage_locations; parent file_objects;
BEGIN
 SELECT * INTO STRICT loc FROM storage_locations WHERE id=NEW.location_id AND tenant_id=NEW.tenant_id;
 IF left(NEW.object_key,length(loc.tenant_prefix))<>loc.tenant_prefix THEN RAISE EXCEPTION 'Object key escapes tenant prefix'; END IF;
 IF NEW.source_object_id IS NOT NULL THEN
  SELECT * INTO STRICT parent FROM file_objects WHERE id=NEW.source_object_id AND file_id=NEW.file_id AND tenant_id=NEW.tenant_id;
  IF parent.id=NEW.id THEN RAISE EXCEPTION 'Object derivation cycle'; END IF;
 END IF;
 IF TG_OP='UPDATE' AND (NEW.file_id,NEW.location_id,NEW.object_key,NEW.version_id,NEW.sha256,NEW.size_bytes,NEW.mime_type,NEW.source_object_id,NEW.variant,NEW.variant_revision) IS DISTINCT FROM (OLD.file_id,OLD.location_id,OLD.object_key,OLD.version_id,OLD.sha256,OLD.size_bytes,OLD.mime_type,OLD.source_object_id,OLD.variant,OLD.variant_revision) THEN RAISE EXCEPTION 'Object bytes and lineage are immutable'; END IF;
 RETURN NEW;
END $function$
;

CREATE OR REPLACE FUNCTION public.app_validate_runtime_binding()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
DECLARE p execution_principals; ident runtime_identities; a agents; av agent_versions; tm team_members; team agent_teams;
BEGIN
 SELECT * INTO STRICT ident FROM runtime_identities WHERE id=NEW.identity_id AND tenant_id=NEW.tenant_id;
 IF ident.backend_id<>NEW.backend_id THEN RAISE EXCEPTION 'Binding backend mismatch'; END IF;
 SELECT * INTO STRICT p FROM execution_principals WHERE id=ident.principal_id AND tenant_id=NEW.tenant_id;
 SELECT * INTO STRICT a FROM agents WHERE id=NEW.agent_id AND tenant_id=NEW.tenant_id;
 SELECT * INTO STRICT av FROM agent_versions WHERE id=NEW.agent_version_id AND agent_id=a.id AND tenant_id=NEW.tenant_id;
 IF TG_OP='UPDATE' AND (NEW.identity_id,NEW.backend_id,NEW.runtime_session_key,NEW.customer_user_id,NEW.channel_id,NEW.agent_id,NEW.agent_version_id,NEW.team_member_id)
   IS DISTINCT FROM (OLD.identity_id,OLD.backend_id,OLD.runtime_session_key,OLD.customer_user_id,OLD.channel_id,OLD.agent_id,OLD.agent_version_id,OLD.team_member_id)
 THEN RAISE EXCEPTION 'Runtime owner and identity are immutable'; END IF;
 IF NEW.audience_kind='personal' THEN
  IF p.kind<>'user' OR p.user_id IS DISTINCT FROM NEW.customer_user_id THEN RAISE EXCEPTION 'Personal binding owner mismatch'; END IF;
 ELSE
  SELECT * INTO STRICT tm FROM team_members WHERE id=NEW.team_member_id AND tenant_id=NEW.tenant_id;
  SELECT * INTO STRICT team FROM agent_teams WHERE id=tm.team_id AND tenant_id=NEW.tenant_id;
  IF p.kind<>'workspace_service' OR p.workspace_id IS DISTINCT FROM team.workspace_id OR team.channel_id<>NEW.channel_id OR tm.agent_id<>NEW.agent_id OR tm.version_id<>NEW.agent_version_id THEN RAISE EXCEPTION 'Team runtime scope mismatch'; END IF;
 END IF;
 RETURN NEW;
END $function$
;

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
 IF NEW.matched_rule_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM triage_rules WHERE id=NEW.matched_rule_id AND policy_version_id=NEW.policy_version_id) THEN RAISE EXCEPTION 'Rule policy mismatch'; END IF;
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

CREATE OR REPLACE FUNCTION public.prevent_audit_event_mutation()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
DECLARE days integer;
BEGIN
 IF TG_OP IN ('UPDATE','TRUNCATE') THEN RAISE EXCEPTION 'Audit events are append-only'; END IF;
 BEGIN days=nullif(current_setting('vinhomes.audit_retention_days',true),'')::integer; EXCEPTION WHEN others THEN days=NULL; END;
 IF days IS NULL OR days<1 OR OLD.created_at>=now()-make_interval(days=>days) THEN RAISE EXCEPTION 'Audit events are append-only within retention'; END IF;
 RETURN OLD;
END $function$
;

CREATE OR REPLACE FUNCTION public.vh_reception_supervisor_message_immutable()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
  RAISE EXCEPTION 'Reception/Supervisor V2 messages are immutable';
END $function$
;

CREATE OR REPLACE FUNCTION public.vh_resident_immutable()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN RAISE EXCEPTION 'Resident receipt or historical record is immutable'; END $function$
;
