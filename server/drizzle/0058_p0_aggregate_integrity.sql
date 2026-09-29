ALTER TABLE "vh_case" DROP CONSTRAINT "vh_case_intake_state_ck";--> statement-breakpoint
ALTER TABLE "vh_task" DROP CONSTRAINT "vh_task_depends_on_json_ck";--> statement-breakpoint
ALTER TABLE "platform_eval_run" DROP CONSTRAINT "platform_eval_run_outcome_ck";--> statement-breakpoint
ALTER TABLE "vh_case" ADD CONSTRAINT "vh_case_intake_state_ck" CHECK ((jsonb_typeof("vh_case"."intake_state_json") = 'object' AND jsonb_typeof("vh_case"."intake_state_json"->'issueCandidates') = 'array') IS TRUE);--> statement-breakpoint
ALTER TABLE "vh_task" ADD CONSTRAINT "vh_task_depends_on_json_ck" CHECK ((jsonb_typeof("vh_task"."depends_on_json") = 'object' AND jsonb_typeof("vh_task"."depends_on_json"->'taskIds') = 'array') IS TRUE);--> statement-breakpoint
ALTER TABLE "platform_eval_run" ADD CONSTRAINT "platform_eval_run_outcome_ck" CHECK (((status='PASSED' AND result='PASS' AND completed_at IS NOT NULL) OR (status IN ('FAILED','CANCELLED') AND result IN ('REVISE','BLOCK','INCONCLUSIVE') AND completed_at IS NOT NULL) OR (status IN ('PENDING','RUNNING') AND result IS NULL AND completed_at IS NULL)) IS TRUE);
--> statement-breakpoint
-- JSON aggregates replace normalized P0 tables without weakening lifecycle guards.
DROP FUNCTION IF EXISTS platform_freeze_spec() CASCADE;
--> statement-breakpoint
DROP FUNCTION IF EXISTS platform_evaluation_scope() CASCADE;
--> statement-breakpoint
DROP FUNCTION IF EXISTS platform_mcp_version_pinned() CASCADE;
--> statement-breakpoint
DROP FUNCTION IF EXISTS platform_eval_case_pinned() CASCADE;
--> statement-breakpoint
DROP FUNCTION IF EXISTS platform_eval_run_pin_suite() CASCADE;
--> statement-breakpoint
DROP FUNCTION IF EXISTS product_tool_identity() CASCADE;
--> statement-breakpoint
DROP FUNCTION IF EXISTS product_tool_version_source() CASCADE;
--> statement-breakpoint
DROP FUNCTION IF EXISTS workforce_dependency_acyclic() CASCADE;
--> statement-breakpoint
CREATE OR REPLACE FUNCTION platform_version_lifecycle() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE capability_id uuid;
BEGIN
  IF TG_OP='DELETE' THEN
    IF OLD.status NOT IN ('DRAFT','NEEDS_INPUT') THEN RAISE EXCEPTION 'evaluated versions cannot be deleted' USING ERRCODE='23514'; END IF;
    RETURN OLD;
  END IF;
  IF TG_OP='INSERT' THEN
    IF NEW.status<>'DRAFT' THEN RAISE EXCEPTION 'new agent versions start as DRAFT' USING ERRCODE='23514'; END IF;
  ELSE
    IF OLD.status NOT IN ('DRAFT','NEEDS_INPUT') AND
      ((NEW.agent_id,NEW.version_no,NEW.spec_json,NEW.spec_hash,NEW.created_by) IS DISTINCT FROM
       (OLD.agent_id,OLD.version_no,OLD.spec_json,OLD.spec_hash,OLD.created_by) OR NEW.status IN ('DRAFT','NEEDS_INPUT')) THEN
      RAISE EXCEPTION 'evaluated agent revision is immutable' USING ERRCODE='23514';
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
  END IF;
  NEW.spec_hash := encode(sha256(convert_to(NEW.spec_json::text,'UTF8')),'hex');
  IF NEW.status='READY_FOR_EVAL' THEN
    IF (jsonb_typeof(NEW.spec_json->'capabilities')='array' AND
        NEW.spec_json->>'schemaVersion'='1' AND length(NEW.spec_json->>'instructions')>0) IS DISTINCT FROM TRUE THEN
      RAISE EXCEPTION 'AgentSpec requires schemaVersion, instructions and pinned capabilities' USING ERRCODE='23514';
    END IF;
    IF (SELECT count(*)<>count(DISTINCT value) FROM jsonb_array_elements_text(NEW.spec_json->'capabilities')) THEN
      RAISE EXCEPTION 'duplicate capability pin' USING ERRCODE='23514';
    END IF;
    BEGIN
      FOR capability_id IN SELECT value::uuid FROM jsonb_array_elements_text(NEW.spec_json->'capabilities') LOOP
        PERFORM 1 FROM platform_capability WHERE tenant_id=NEW.tenant_id AND id=capability_id AND status='ACTIVE' FOR SHARE;
        IF NOT FOUND THEN RAISE EXCEPTION 'capability must be active in the same tenant' USING ERRCODE='23514'; END IF;
      END LOOP;
    EXCEPTION WHEN invalid_text_representation THEN
      RAISE EXCEPTION 'capability pins must be UUID strings' USING ERRCODE='23514';
    END;
  END IF;
  IF NEW.status='PUBLISHED' AND OLD.status<>'PUBLISHED' THEN
    IF NOT EXISTS (SELECT 1 FROM platform_eval_run r
        WHERE r.tenant_id=NEW.tenant_id AND r.agent_version_id=NEW.id AND r.status='PASSED' AND r.result='PASS'
        AND r.evaluated_by<>NEW.created_by AND jsonb_array_length(r.tests_json)>0 AND jsonb_array_length(r.evidence_json)>0
        AND (SELECT count(DISTINCT g->>'type') FROM jsonb_array_elements(r.results_json) g
             WHERE g->>'type' IN ('CONTRACT','QUALITY','SAFETY','REGRESSION') AND g->>'status'='PASS'
               AND length(g->>'evidenceRef')>0)=4
        AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements(r.results_json) g WHERE g->>'status' IS DISTINCT FROM 'PASS'))
      OR (SELECT count(DISTINCT approval_type) FROM platform_publish_approval
          WHERE tenant_id=NEW.tenant_id AND agent_version_id=NEW.id AND status='APPROVED' AND reviewer_id<>NEW.created_by)<>4 THEN
      RAISE EXCEPTION 'publication requires successful evaluation, four evidence-backed gates and independent approvals' USING ERRCODE='23514';
    END IF;
    NEW.published_at:=coalesce(OLD.published_at,clock_timestamp());
  END IF;
  IF NEW.status='SUSPENDED' AND OLD.status<>'SUSPENDED' THEN NEW.suspended_at:=clock_timestamp(); END IF;
  IF NEW.status='RETIRED' AND OLD.status<>'RETIRED' THEN NEW.retired_at:=clock_timestamp(); END IF;
  RETURN NEW;
END $$;
--> statement-breakpoint
CREATE FUNCTION platform_capability_pinned() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' THEN
    RAISE EXCEPTION 'capability revisions are retained; retire instead' USING ERRCODE='23514';
  END IF;
  IF TG_OP='UPDATE' AND (to_jsonb(NEW)-ARRAY['status','version','updated_at']) IS DISTINCT FROM
                         (to_jsonb(OLD)-ARRAY['status','version','updated_at']) THEN
    RAISE EXCEPTION 'capability content is immutable; create a new version_no' USING ERRCODE='23514';
  END IF;
  IF NEW.source_type='MCP_SERVER' THEN
    IF NEW.type<>'MCP_TOOL' OR NOT EXISTS(SELECT 1 FROM mcp_servers WHERE tenant_id=NEW.tenant_id AND id=NEW.source_ref)
      OR (jsonb_typeof(NEW.config_json->'toolName')='string' AND length(NEW.config_json->>'toolName')>0
          AND jsonb_typeof(NEW.config_json->'inputSchema')='object' AND jsonb_typeof(NEW.config_json->'outputSchema')='object'
          AND length(NEW.config_json->>'fingerprint')>0) IS DISTINCT FROM TRUE THEN
      RAISE EXCEPTION 'MCP capability requires a tenant server and a pinned tool schema' USING ERRCODE='23514';
    END IF;
  END IF;
  RETURN NEW;
END $$;
--> statement-breakpoint
CREATE TRIGGER platform_capability_pinned BEFORE INSERT OR UPDATE OR DELETE ON platform_capability FOR EACH ROW EXECUTE FUNCTION platform_capability_pinned();
--> statement-breakpoint
CREATE TRIGGER platform_capability_no_truncate BEFORE TRUNCATE ON platform_capability FOR EACH STATEMENT EXECUTE FUNCTION workforce_append_only();
--> statement-breakpoint
CREATE FUNCTION platform_eval_json_pinned() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE revision_status text;
BEGIN
  IF TG_OP='DELETE' THEN RAISE EXCEPTION 'evaluation history is retained' USING ERRCODE='23514'; END IF;
  SELECT status INTO revision_status FROM platform_agent_version WHERE tenant_id=NEW.tenant_id AND id=NEW.agent_version_id FOR UPDATE;
  IF revision_status IS DISTINCT FROM 'EVALUATING' THEN
    RAISE EXCEPTION 'evaluation is written only while the revision is EVALUATING' USING ERRCODE='23514';
  END IF;
  IF TG_OP='UPDATE' AND (OLD.status IN ('PASSED','FAILED','CANCELLED') OR
      (NEW.agent_version_id,NEW.tests_json,NEW.environment_snapshot,NEW.model_snapshot,NEW.evaluated_by) IS DISTINCT FROM
      (OLD.agent_version_id,OLD.tests_json,OLD.environment_snapshot,OLD.model_snapshot,OLD.evaluated_by)) THEN
    RAISE EXCEPTION 'evaluation pins tests and provenance; completed results are immutable' USING ERRCODE='23514';
  END IF;
  IF NEW.status='PASSED' AND (jsonb_array_length(NEW.tests_json)=0 OR jsonb_array_length(NEW.results_json)=0 OR jsonb_array_length(NEW.evidence_json)=0) THEN
    RAISE EXCEPTION 'PASS requires tests, results and evidence' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END $$;
--> statement-breakpoint
CREATE TRIGGER platform_eval_json_pinned BEFORE INSERT OR UPDATE OR DELETE ON platform_eval_run FOR EACH ROW EXECUTE FUNCTION platform_eval_json_pinned();
--> statement-breakpoint
CREATE TRIGGER platform_eval_no_truncate BEFORE TRUNCATE ON platform_eval_run FOR EACH STATEMENT EXECUTE FUNCTION workforce_append_only();
--> statement-breakpoint
CREATE FUNCTION platform_approval_revision_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE revision platform_agent_version;
BEGIN
  SELECT * INTO revision FROM platform_agent_version WHERE tenant_id=NEW.tenant_id AND id=NEW.agent_version_id FOR UPDATE;
  IF revision.status NOT IN ('READY_FOR_REVIEW','READY_FOR_PUBLISH') OR revision.created_by=NEW.reviewer_id THEN
    RAISE EXCEPTION 'independent approval requires a revision ready for review' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END $$;
--> statement-breakpoint
CREATE TRIGGER platform_approval_revision_guard BEFORE INSERT ON platform_publish_approval FOR EACH ROW EXECUTE FUNCTION platform_approval_revision_guard();
--> statement-breakpoint
CREATE FUNCTION platform_plan_json_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE step jsonb; keys text[]; dep text; cycle_found boolean;
BEGIN
  IF (jsonb_typeof(NEW.plan_json->'steps')='array') IS DISTINCT FROM TRUE THEN
    RAISE EXCEPTION 'plan.steps must be an array' USING ERRCODE='23514';
  END IF;
  SELECT array_agg(s->>'key') INTO keys FROM jsonb_array_elements(NEW.plan_json->'steps') s;
  IF (SELECT count(*)<>count(DISTINCT s->>'key') FROM jsonb_array_elements(NEW.plan_json->'steps') s) THEN
    RAISE EXCEPTION 'plan step keys must be present and unique' USING ERRCODE='23514';
  END IF;
  FOR step IN SELECT value FROM jsonb_array_elements(NEW.plan_json->'steps') LOOP
    IF (jsonb_typeof(step)='object' AND jsonb_typeof(step->'key')='string' AND length(step->>'key')>0
        AND jsonb_typeof(step->'dependsOn')='array') IS DISTINCT FROM TRUE THEN
      RAISE EXCEPTION 'each plan step requires a key and dependsOn array' USING ERRCODE='23514';
    END IF;
    IF EXISTS(SELECT 1 FROM jsonb_array_elements(step->'dependsOn') d WHERE jsonb_typeof(d)<>'string') OR
       (SELECT count(*)<>count(DISTINCT value) FROM jsonb_array_elements_text(step->'dependsOn')) THEN
      RAISE EXCEPTION 'step dependencies must be distinct strings' USING ERRCODE='23514';
    END IF;
    FOR dep IN SELECT value FROM jsonb_array_elements_text(step->'dependsOn') LOOP
      IF NOT dep=ANY(keys) THEN RAISE EXCEPTION 'dependency step does not exist' USING ERRCODE='23514'; END IF;
    END LOOP;
    WITH RECURSIVE reach(key) AS (
      SELECT value FROM jsonb_array_elements_text(step->'dependsOn')
      UNION SELECT d.value FROM reach r JOIN jsonb_array_elements(NEW.plan_json->'steps') s ON s->>'key'=r.key,
        LATERAL jsonb_array_elements_text(s->'dependsOn') d
    ) SELECT EXISTS(SELECT 1 FROM reach WHERE key=step->>'key') INTO cycle_found;
    IF cycle_found THEN RAISE EXCEPTION 'plan cannot contain dependency cycles' USING ERRCODE='23514'; END IF;
  END LOOP;
  IF TG_OP='UPDATE' AND (
    EXISTS(SELECT 1 FROM platform_agent_run WHERE tenant_id=NEW.tenant_id AND workflow_session_id=NEW.id AND NOT step_key=ANY(coalesce(keys,ARRAY[]::text[]))) OR
    EXISTS(SELECT 1 FROM platform_session_wait WHERE tenant_id=NEW.tenant_id AND workflow_session_id=NEW.id AND step_key IS NOT NULL AND NOT step_key=ANY(coalesce(keys,ARRAY[]::text[])))
  ) THEN RAISE EXCEPTION 'plan cannot remove referenced run or wait steps' USING ERRCODE='23514'; END IF;
  RETURN NEW;
END $$;
--> statement-breakpoint
CREATE TRIGGER platform_plan_json_guard BEFORE INSERT OR UPDATE OF plan_json ON platform_workflow_session FOR EACH ROW EXECUTE FUNCTION platform_plan_json_guard();
--> statement-breakpoint
CREATE OR REPLACE FUNCTION platform_run_eligible() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE workflow platform_workflow_session; version_status text;
BEGIN
  IF TG_OP='UPDATE' AND (NEW.agent_id,NEW.agent_version_id,NEW.workflow_session_id,NEW.step_key,NEW.attempt_no)
    IS DISTINCT FROM (OLD.agent_id,OLD.agent_version_id,OLD.workflow_session_id,OLD.step_key,OLD.attempt_no) THEN
    RAISE EXCEPTION 'run pins its agent version, session, step and attempt' USING ERRCODE='23514';
  END IF;
  SELECT * INTO workflow FROM platform_workflow_session WHERE tenant_id=NEW.tenant_id AND id=NEW.workflow_session_id FOR UPDATE;
  IF NOT EXISTS(SELECT 1 FROM jsonb_array_elements(workflow.plan_json->'steps') s WHERE s->>'key'=NEW.step_key) THEN
    RAISE EXCEPTION 'run step must be defined in session plan' USING ERRCODE='23514';
  END IF;
  IF workflow.environment='PRODUCTION' AND NEW.status IN ('PENDING','RUNNING') THEN
    SELECT status INTO version_status FROM platform_agent_version WHERE tenant_id=NEW.tenant_id AND id=NEW.agent_version_id FOR SHARE;
    IF version_status IS DISTINCT FROM 'PUBLISHED' OR NOT EXISTS(SELECT 1 FROM platform_agent_deployment
        WHERE tenant_id=NEW.tenant_id AND agent_version_id=NEW.agent_version_id AND environment='PRODUCTION' AND status='ACTIVE') THEN
      RAISE EXCEPTION 'production run requires a published version with an active deployment' USING ERRCODE='23514';
    END IF;
  END IF;
  RETURN NEW;
END $$;
--> statement-breakpoint
CREATE FUNCTION platform_wait_plan_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE plan jsonb;
BEGIN
  IF TG_OP='UPDATE' AND NEW.step_key IS DISTINCT FROM OLD.step_key THEN
    RAISE EXCEPTION 'wait step is pinned' USING ERRCODE='23514';
  END IF;
  SELECT plan_json INTO plan FROM platform_workflow_session WHERE tenant_id=NEW.tenant_id AND id=NEW.workflow_session_id FOR UPDATE;
  IF NEW.step_key IS NOT NULL AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements(plan->'steps') s WHERE s->>'key'=NEW.step_key) THEN
    RAISE EXCEPTION 'wait step must be defined in session plan' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END $$;
--> statement-breakpoint
CREATE TRIGGER platform_wait_plan_guard BEFORE INSERT OR UPDATE ON platform_session_wait FOR EACH ROW EXECUTE FUNCTION platform_wait_plan_guard();
--> statement-breakpoint
CREATE FUNCTION platform_tool_call_capability_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NOT EXISTS(SELECT 1 FROM platform_capability WHERE tenant_id=NEW.tenant_id AND id=NEW.capability_id AND type IN ('MCP_TOOL','CONNECTOR')) THEN
    RAISE EXCEPTION 'tool call must pin a tool or connector capability' USING ERRCODE='23514';
  END IF;
  IF TG_OP='UPDATE' AND (NEW.agent_run_id,NEW.capability_id,NEW.request_json) IS DISTINCT FROM (OLD.agent_run_id,OLD.capability_id,OLD.request_json) THEN
    RAISE EXCEPTION 'tool call identity and request are pinned' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END $$;
--> statement-breakpoint
CREATE TRIGGER platform_tool_call_capability_guard BEFORE INSERT OR UPDATE ON platform_tool_call FOR EACH ROW EXECUTE FUNCTION platform_tool_call_capability_guard();
--> statement-breakpoint
CREATE FUNCTION vh_aggregate_snapshot_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_TABLE_NAME='vh_action_request' AND OLD.rule_decision IS NOT NULL AND
     (NEW.rule_decision,NEW.rule_reason_code,NEW.rule_version,NEW.rule_evaluated_at) IS DISTINCT FROM
     (OLD.rule_decision,OLD.rule_reason_code,OLD.rule_version,OLD.rule_evaluated_at) THEN
    RAISE EXCEPTION 'RuleDecision is pinned to the ActionRequest payload' USING ERRCODE='23514';
  ELSIF TG_TABLE_NAME='vh_work_order' AND
     (NEW.checklist_id,NEW.checklist_version,NEW.checklist_snapshot_json) IS DISTINCT FROM
     (OLD.checklist_id,OLD.checklist_version,OLD.checklist_snapshot_json) THEN
    RAISE EXCEPTION 'work order checklist snapshot is immutable; create a new attempt' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END $$;
--> statement-breakpoint
CREATE TRIGGER vh_rule_decision_pinned BEFORE UPDATE ON vh_action_request FOR EACH ROW EXECUTE FUNCTION vh_aggregate_snapshot_guard();
--> statement-breakpoint
CREATE TRIGGER vh_checklist_snapshot_pinned BEFORE UPDATE ON vh_work_order FOR EACH ROW EXECUTE FUNCTION vh_aggregate_snapshot_guard();
--> statement-breakpoint
CREATE FUNCTION vh_task_dependency_target_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  PERFORM 1 FROM vh_incident WHERE tenant_id=OLD.tenant_id AND id=OLD.incident_id FOR UPDATE;
  IF EXISTS(SELECT 1 FROM vh_task WHERE tenant_id=OLD.tenant_id AND incident_id=OLD.incident_id AND depends_on_json->'taskIds' ? OLD.id::text) THEN
    RAISE EXCEPTION 'task is referenced by a dependency' USING ERRCODE='23514';
  END IF;
  RETURN OLD;
END $$;
--> statement-breakpoint
CREATE TRIGGER vh_task_dependency_target_guard BEFORE DELETE ON vh_task FOR EACH ROW EXECUTE FUNCTION vh_task_dependency_target_guard();
--> statement-breakpoint
CREATE TRIGGER workforce_touch BEFORE UPDATE ON vh_loyalty_balance FOR EACH ROW EXECUTE FUNCTION workforce_touch();
