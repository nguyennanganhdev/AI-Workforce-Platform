-- Local-only redesign: refuse destructive consolidation when old aggregates contain data.
DO $$ DECLARE n text; occupied boolean;
BEGIN
  FOREACH n IN ARRAY ARRAY['vh_transit_route','vh_transit_route_stop','vh_transit_stop','vh_action_request','vh_checklist','vh_checklist_version','vh_rule_evaluation','vh_work_order','vh_handover','platform_agent_change_request','platform_agent_spec','platform_agent_version','platform_agent_capability_binding','platform_agent_knowledge_binding','platform_agent_model_binding','platform_agent_policy_binding','platform_agent_skill_binding','platform_agent_tool_binding','platform_capability','platform_mcp_server_version','platform_model_profile','platform_skill_version','platform_tool','platform_tool_version','platform_domain_installation','platform_domain_package','platform_eval_assertion','platform_eval_case','platform_eval_evidence','platform_eval_run','platform_eval_suite','platform_publish_approval','platform_publish_gate','platform_publish_gate_result','platform_regression_baseline','platform_knowledge_base','platform_knowledge_revision','platform_knowledge_source','platform_policy','platform_policy_version','platform_agent_run','platform_run_step','platform_run_step_dependency','platform_tool_call','platform_workflow_session','platform_session_wait'] LOOP
    EXECUTE format('SELECT EXISTS(SELECT 1 FROM %I)',n) INTO occupied;
    IF occupied THEN RAISE EXCEPTION '0057 requires empty legacy aggregate %: export/map data before retry',n; END IF;
  END LOOP;
END $$;
--> statement-breakpoint
ALTER TABLE "platform_domain_package" DISABLE ROW LEVEL SECURITY;--> statement-breakpoint
DROP POLICY "vh_transit_route_stop_tenant_policy" ON "vh_transit_route_stop" CASCADE;--> statement-breakpoint
DROP TABLE "vh_transit_route_stop" CASCADE;--> statement-breakpoint
DROP POLICY "vh_transit_stop_tenant_policy" ON "vh_transit_stop" CASCADE;--> statement-breakpoint
DROP TABLE "vh_transit_stop" CASCADE;--> statement-breakpoint
DROP POLICY "vh_checklist_tenant_policy" ON "vh_checklist" CASCADE;--> statement-breakpoint
DROP TABLE "vh_checklist" CASCADE;--> statement-breakpoint
DROP POLICY "vh_checklist_version_tenant_policy" ON "vh_checklist_version" CASCADE;--> statement-breakpoint
DROP TABLE "vh_checklist_version" CASCADE;--> statement-breakpoint
DROP POLICY "vh_rule_evaluation_tenant_policy" ON "vh_rule_evaluation" CASCADE;--> statement-breakpoint
DROP TABLE "vh_rule_evaluation" CASCADE;--> statement-breakpoint
DROP POLICY "platform_agent_change_request_tenant_policy" ON "platform_agent_change_request" CASCADE;--> statement-breakpoint
DROP TABLE "platform_agent_change_request" CASCADE;--> statement-breakpoint
DROP POLICY "platform_agent_spec_tenant_policy" ON "platform_agent_spec" CASCADE;--> statement-breakpoint
DROP TABLE "platform_agent_spec" CASCADE;--> statement-breakpoint
DROP POLICY "platform_agent_capability_binding_tenant_policy" ON "platform_agent_capability_binding" CASCADE;--> statement-breakpoint
DROP TABLE "platform_agent_capability_binding" CASCADE;--> statement-breakpoint
DROP POLICY "platform_agent_knowledge_binding_tenant_policy" ON "platform_agent_knowledge_binding" CASCADE;--> statement-breakpoint
DROP TABLE "platform_agent_knowledge_binding" CASCADE;--> statement-breakpoint
DROP POLICY "platform_agent_model_binding_tenant_policy" ON "platform_agent_model_binding" CASCADE;--> statement-breakpoint
DROP TABLE "platform_agent_model_binding" CASCADE;--> statement-breakpoint
DROP POLICY "platform_agent_policy_binding_tenant_policy" ON "platform_agent_policy_binding" CASCADE;--> statement-breakpoint
DROP TABLE "platform_agent_policy_binding" CASCADE;--> statement-breakpoint
DROP POLICY "platform_agent_skill_binding_tenant_policy" ON "platform_agent_skill_binding" CASCADE;--> statement-breakpoint
DROP TABLE "platform_agent_skill_binding" CASCADE;--> statement-breakpoint
DROP POLICY "platform_agent_tool_binding_tenant_policy" ON "platform_agent_tool_binding" CASCADE;--> statement-breakpoint
DROP TABLE "platform_agent_tool_binding" CASCADE;--> statement-breakpoint
DROP POLICY "platform_mcp_server_version_tenant_policy" ON "platform_mcp_server_version" CASCADE;--> statement-breakpoint
DROP TABLE "platform_mcp_server_version" CASCADE;--> statement-breakpoint
DROP POLICY "platform_model_profile_tenant_policy" ON "platform_model_profile" CASCADE;--> statement-breakpoint
DROP TABLE "platform_model_profile" CASCADE;--> statement-breakpoint
DROP POLICY "platform_skill_version_tenant_policy" ON "platform_skill_version" CASCADE;--> statement-breakpoint
DROP TABLE "platform_skill_version" CASCADE;--> statement-breakpoint
DROP POLICY "platform_tool_tenant_policy" ON "platform_tool" CASCADE;--> statement-breakpoint
DROP TABLE "platform_tool" CASCADE;--> statement-breakpoint
DROP POLICY "platform_tool_version_tenant_policy" ON "platform_tool_version" CASCADE;--> statement-breakpoint
DROP TABLE "platform_tool_version" CASCADE;--> statement-breakpoint
DROP TABLE "platform_domain_package" CASCADE;--> statement-breakpoint
DROP POLICY "platform_eval_assertion_tenant_policy" ON "platform_eval_assertion" CASCADE;--> statement-breakpoint
DROP TABLE "platform_eval_assertion" CASCADE;--> statement-breakpoint
DROP POLICY "platform_eval_case_tenant_policy" ON "platform_eval_case" CASCADE;--> statement-breakpoint
DROP TABLE "platform_eval_case" CASCADE;--> statement-breakpoint
DROP POLICY "platform_eval_evidence_tenant_policy" ON "platform_eval_evidence" CASCADE;--> statement-breakpoint
DROP TABLE "platform_eval_evidence" CASCADE;--> statement-breakpoint
DROP POLICY "platform_eval_suite_tenant_policy" ON "platform_eval_suite" CASCADE;--> statement-breakpoint
DROP TABLE "platform_eval_suite" CASCADE;--> statement-breakpoint
DROP POLICY "platform_publish_gate_tenant_policy" ON "platform_publish_gate" CASCADE;--> statement-breakpoint
DROP TABLE "platform_publish_gate" CASCADE;--> statement-breakpoint
DROP POLICY "platform_publish_gate_result_tenant_policy" ON "platform_publish_gate_result" CASCADE;--> statement-breakpoint
DROP TABLE "platform_publish_gate_result" CASCADE;--> statement-breakpoint
DROP POLICY "platform_regression_baseline_tenant_policy" ON "platform_regression_baseline" CASCADE;--> statement-breakpoint
DROP TABLE "platform_regression_baseline" CASCADE;--> statement-breakpoint
DROP POLICY "platform_knowledge_base_tenant_policy" ON "platform_knowledge_base" CASCADE;--> statement-breakpoint
DROP TABLE "platform_knowledge_base" CASCADE;--> statement-breakpoint
DROP POLICY "platform_knowledge_revision_tenant_policy" ON "platform_knowledge_revision" CASCADE;--> statement-breakpoint
DROP TABLE "platform_knowledge_revision" CASCADE;--> statement-breakpoint
DROP POLICY "platform_knowledge_source_tenant_policy" ON "platform_knowledge_source" CASCADE;--> statement-breakpoint
DROP TABLE "platform_knowledge_source" CASCADE;--> statement-breakpoint
DROP POLICY "platform_policy_tenant_policy" ON "platform_policy" CASCADE;--> statement-breakpoint
DROP TABLE "platform_policy" CASCADE;--> statement-breakpoint
DROP POLICY "platform_policy_version_tenant_policy" ON "platform_policy_version" CASCADE;--> statement-breakpoint
DROP TABLE "platform_policy_version" CASCADE;--> statement-breakpoint
DROP POLICY "platform_run_step_tenant_policy" ON "platform_run_step" CASCADE;--> statement-breakpoint
DROP TABLE "platform_run_step" CASCADE;--> statement-breakpoint
DROP POLICY "platform_run_step_dependency_tenant_policy" ON "platform_run_step_dependency" CASCADE;--> statement-breakpoint
DROP TABLE "platform_run_step_dependency" CASCADE;--> statement-breakpoint
ALTER TABLE "platform_capability" DROP CONSTRAINT IF EXISTS "platform_capability_uq_0";--> statement-breakpoint
ALTER TABLE "platform_domain_installation" DROP CONSTRAINT IF EXISTS "platform_domain_installation_uq_0";--> statement-breakpoint
ALTER TABLE "platform_publish_approval" DROP CONSTRAINT IF EXISTS "platform_publish_approval_uq_0";--> statement-breakpoint
ALTER TABLE "vh_work_order" DROP CONSTRAINT IF EXISTS "vh_work_order_fk_6";
--> statement-breakpoint
ALTER TABLE "vh_handover" DROP CONSTRAINT IF EXISTS "vh_handover_fk_4";
--> statement-breakpoint
ALTER TABLE "platform_domain_installation" DROP CONSTRAINT IF EXISTS "platform_domain_installation_fk_1";
--> statement-breakpoint
ALTER TABLE "platform_eval_run" DROP CONSTRAINT IF EXISTS "platform_eval_run_fk_2";
--> statement-breakpoint
ALTER TABLE "platform_publish_approval" DROP CONSTRAINT IF EXISTS "platform_publish_approval_fk_1";
--> statement-breakpoint
ALTER TABLE "platform_agent_run" DROP CONSTRAINT IF EXISTS "platform_agent_run_fk_2";
--> statement-breakpoint
ALTER TABLE "platform_tool_call" DROP CONSTRAINT IF EXISTS "platform_tool_call_fk_2";
--> statement-breakpoint
ALTER TABLE "platform_session_wait" DROP CONSTRAINT IF EXISTS "platform_session_wait_fk_2";
--> statement-breakpoint
DROP INDEX "vh_work_order_ix_0";--> statement-breakpoint
DROP INDEX "vh_handover_ix_0";--> statement-breakpoint
DROP INDEX "platform_eval_run_ix_1";--> statement-breakpoint
DROP INDEX "platform_domain_installation_ix_0";--> statement-breakpoint
DROP INDEX "platform_publish_approval_ix_0";--> statement-breakpoint
DROP INDEX "platform_agent_run_ix_2";--> statement-breakpoint
DROP INDEX "platform_tool_call_ix_1";--> statement-breakpoint
DROP INDEX "platform_session_wait_ix_3";--> statement-breakpoint
ALTER TABLE "vh_transit_route" ADD COLUMN "stops_json" jsonb DEFAULT '[]'::jsonb NOT NULL;--> statement-breakpoint
ALTER TABLE "vh_action_request" ADD COLUMN "rule_decision" text;--> statement-breakpoint
ALTER TABLE "vh_action_request" ADD COLUMN "rule_reason_code" text;--> statement-breakpoint
ALTER TABLE "vh_action_request" ADD COLUMN "rule_version" text;--> statement-breakpoint
ALTER TABLE "vh_action_request" ADD COLUMN "rule_evaluated_at" timestamp with time zone;--> statement-breakpoint
ALTER TABLE "vh_work_order" ADD COLUMN "checklist_id" text;--> statement-breakpoint
ALTER TABLE "vh_work_order" ADD COLUMN "checklist_version" integer;--> statement-breakpoint
ALTER TABLE "vh_work_order" ADD COLUMN "checklist_snapshot_json" jsonb DEFAULT '{}'::jsonb NOT NULL;--> statement-breakpoint
ALTER TABLE "vh_handover" ADD COLUMN "checklist_snapshot_json" jsonb DEFAULT '{}'::jsonb NOT NULL;--> statement-breakpoint
ALTER TABLE "platform_agent_version" ADD COLUMN "spec_json" jsonb DEFAULT '{}'::jsonb NOT NULL;--> statement-breakpoint
ALTER TABLE "platform_capability" ADD COLUMN "version_no" integer NOT NULL;--> statement-breakpoint
ALTER TABLE "platform_capability" ADD COLUMN "source_type" text NOT NULL;--> statement-breakpoint
ALTER TABLE "platform_capability" ADD COLUMN "source_ref" text NOT NULL;--> statement-breakpoint
ALTER TABLE "platform_capability" ADD COLUMN "config_json" jsonb NOT NULL;--> statement-breakpoint
ALTER TABLE "platform_domain_installation" ADD COLUMN "domain_namespace" text NOT NULL;--> statement-breakpoint
ALTER TABLE "platform_domain_installation" ADD COLUMN "domain_version" text NOT NULL;--> statement-breakpoint
ALTER TABLE "platform_eval_run" ADD COLUMN "result" text;--> statement-breakpoint
ALTER TABLE "platform_eval_run" ADD COLUMN "tests_json" jsonb NOT NULL;--> statement-breakpoint
ALTER TABLE "platform_eval_run" ADD COLUMN "results_json" jsonb DEFAULT '[]'::jsonb NOT NULL;--> statement-breakpoint
ALTER TABLE "platform_eval_run" ADD COLUMN "evidence_json" jsonb DEFAULT '[]'::jsonb NOT NULL;--> statement-breakpoint
ALTER TABLE "platform_eval_run" ADD COLUMN "evaluated_by" text NOT NULL;--> statement-breakpoint
ALTER TABLE "platform_publish_approval" ADD COLUMN "agent_version_id" uuid NOT NULL;--> statement-breakpoint
ALTER TABLE "platform_agent_run" ADD COLUMN "step_key" text NOT NULL;--> statement-breakpoint
ALTER TABLE "platform_agent_run" ADD COLUMN "role" text DEFAULT 'SPECIALIST' NOT NULL;--> statement-breakpoint
ALTER TABLE "platform_agent_run" ADD COLUMN "attempt_no" integer DEFAULT 1 NOT NULL;--> statement-breakpoint
ALTER TABLE "platform_agent_run" ADD COLUMN "error_type" text;--> statement-breakpoint
ALTER TABLE "platform_agent_run" ADD COLUMN "error_json" jsonb;--> statement-breakpoint
ALTER TABLE "platform_agent_run" ADD COLUMN "input_json" jsonb NOT NULL;--> statement-breakpoint
ALTER TABLE "platform_agent_run" ADD COLUMN "output_json" jsonb NOT NULL;--> statement-breakpoint
ALTER TABLE "platform_tool_call" ADD COLUMN "capability_id" uuid NOT NULL;--> statement-breakpoint
ALTER TABLE "platform_workflow_session" ADD COLUMN "plan_json" jsonb NOT NULL;--> statement-breakpoint
ALTER TABLE "platform_workflow_session" ADD COLUMN "context_snapshot_json" jsonb DEFAULT '{}'::jsonb NOT NULL;--> statement-breakpoint
ALTER TABLE "platform_session_wait" ADD COLUMN "step_key" text;--> statement-breakpoint
ALTER TABLE "platform_eval_run" ADD CONSTRAINT "platform_eval_run_reviewer_fk" FOREIGN KEY ("evaluated_by") REFERENCES "public"."users"("id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_publish_approval" ADD CONSTRAINT "platform_publish_approval_fk_1" FOREIGN KEY ("tenant_id","agent_version_id") REFERENCES "public"."platform_agent_version"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "platform_tool_call" ADD CONSTRAINT "platform_tool_call_fk_2" FOREIGN KEY ("tenant_id","capability_id") REFERENCES "public"."platform_capability"("tenant_id","id") ON DELETE restrict ON UPDATE no action;--> statement-breakpoint
CREATE INDEX "platform_domain_installation_ix_0" ON "platform_domain_installation" USING btree ("domain_namespace");--> statement-breakpoint
CREATE INDEX "platform_publish_approval_ix_0" ON "platform_publish_approval" USING btree ("tenant_id","agent_version_id");--> statement-breakpoint
CREATE INDEX "platform_agent_run_ix_2" ON "platform_agent_run" USING btree ("tenant_id","workflow_session_id","step_key");--> statement-breakpoint
CREATE INDEX "platform_tool_call_ix_1" ON "platform_tool_call" USING btree ("tenant_id","capability_id");--> statement-breakpoint
CREATE INDEX "platform_session_wait_ix_3" ON "platform_session_wait" USING btree ("tenant_id","workflow_session_id","step_key");--> statement-breakpoint
ALTER TABLE "vh_work_order" DROP COLUMN "checklist_version_id";--> statement-breakpoint
ALTER TABLE "vh_handover" DROP COLUMN "checklist_version_id";--> statement-breakpoint
ALTER TABLE "platform_domain_installation" DROP COLUMN "domain_package_id";--> statement-breakpoint
ALTER TABLE "platform_eval_run" DROP COLUMN "eval_suite_id";--> statement-breakpoint
ALTER TABLE "platform_publish_approval" DROP COLUMN "publish_gate_id";--> statement-breakpoint
ALTER TABLE "platform_agent_run" DROP COLUMN "run_step_id";--> statement-breakpoint
ALTER TABLE "platform_agent_run" DROP COLUMN "input_snapshot";--> statement-breakpoint
ALTER TABLE "platform_agent_run" DROP COLUMN "output_snapshot";--> statement-breakpoint
ALTER TABLE "platform_tool_call" DROP COLUMN "tool_version_id";--> statement-breakpoint
ALTER TABLE "platform_workflow_session" DROP COLUMN "plan_snapshot";--> statement-breakpoint
ALTER TABLE "platform_session_wait" DROP COLUMN "run_step_id";--> statement-breakpoint
ALTER TABLE "platform_capability" ADD CONSTRAINT "platform_capability_uq_0" UNIQUE("tenant_id","type","code","version_no");--> statement-breakpoint
ALTER TABLE "platform_domain_installation" ADD CONSTRAINT "platform_domain_installation_uq_0" UNIQUE("tenant_id","domain_namespace","environment");--> statement-breakpoint
ALTER TABLE "platform_publish_approval" ADD CONSTRAINT "platform_publish_approval_uq_0" UNIQUE("tenant_id","agent_version_id","approval_type");--> statement-breakpoint
ALTER TABLE "platform_agent_run" ADD CONSTRAINT "platform_agent_run_attempt_uq" UNIQUE("tenant_id","workflow_session_id","step_key","agent_id","attempt_no");--> statement-breakpoint
ALTER TABLE "vh_transit_route" ADD CONSTRAINT "vh_transit_route_stops_ck" CHECK (jsonb_typeof(stops_json)='array');--> statement-breakpoint
ALTER TABLE "vh_action_request" ADD CONSTRAINT "vh_action_request_rule_ck" CHECK ("vh_action_request"."rule_decision" in ('ALLOW', 'DENY', 'REQUIRE_APPROVAL'));--> statement-breakpoint
ALTER TABLE "vh_action_request" ADD CONSTRAINT "vh_action_request_rule_complete_ck" CHECK (num_nonnulls(rule_decision,rule_reason_code,rule_version,rule_evaluated_at) IN (0,4));--> statement-breakpoint
ALTER TABLE "vh_work_order" ADD CONSTRAINT "vh_work_order_checklist_ck" CHECK (jsonb_typeof(checklist_snapshot_json)='object' AND ((checklist_id IS NULL AND checklist_version IS NULL AND checklist_snapshot_json='{}'::jsonb) OR (checklist_id IS NOT NULL AND checklist_version > 0 AND jsonb_typeof(checklist_snapshot_json->'criteria')='array')) IS TRUE);--> statement-breakpoint
ALTER TABLE "platform_agent_version" ADD CONSTRAINT "platform_agent_version_spec_ck" CHECK (jsonb_typeof(spec_json) = 'object');--> statement-breakpoint
ALTER TABLE "platform_capability" ADD CONSTRAINT "platform_capability_type_ck" CHECK ("platform_capability"."type" in ('MODEL', 'MCP_TOOL', 'SKILL', 'KNOWLEDGE', 'POLICY', 'CONNECTOR'));--> statement-breakpoint
ALTER TABLE "platform_capability" ADD CONSTRAINT "platform_capability_revision_ck" CHECK (version_no > 0);--> statement-breakpoint
ALTER TABLE "platform_capability" ADD CONSTRAINT "platform_capability_config_ck" CHECK (jsonb_typeof(config_json) = 'object' AND length(source_type) > 0 AND length(source_ref) > 0);--> statement-breakpoint
ALTER TABLE "platform_eval_run" ADD CONSTRAINT "platform_eval_run_result_ck" CHECK ("platform_eval_run"."result" in ('PASS', 'REVISE', 'BLOCK', 'INCONCLUSIVE'));--> statement-breakpoint
ALTER TABLE "platform_eval_run" ADD CONSTRAINT "platform_eval_run_json_ck" CHECK (jsonb_typeof(tests_json)='array' AND jsonb_typeof(results_json)='array' AND jsonb_typeof(evidence_json)='array');--> statement-breakpoint
ALTER TABLE "platform_eval_run" ADD CONSTRAINT "platform_eval_run_outcome_ck" CHECK ((status='PASSED' AND result='PASS' AND completed_at IS NOT NULL) OR (status IN ('FAILED','CANCELLED') AND result IN ('REVISE','BLOCK','INCONCLUSIVE') AND completed_at IS NOT NULL) OR (status IN ('PENDING','RUNNING') AND result IS NULL AND completed_at IS NULL));--> statement-breakpoint
ALTER TABLE "platform_agent_run" ADD CONSTRAINT "platform_agent_run_attempt_ck" CHECK (attempt_no > 0);--> statement-breakpoint
ALTER TABLE "platform_workflow_session" ADD CONSTRAINT "platform_workflow_session_plan_ck" CHECK ((jsonb_typeof(plan_json)='object' AND jsonb_typeof(plan_json->'steps')='array') IS TRUE AND jsonb_typeof(context_snapshot_json)='object');