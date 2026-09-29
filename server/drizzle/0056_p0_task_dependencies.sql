DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM vh_task_dependency) THEN
    RAISE EXCEPTION '0056 requires empty legacy task dependencies; map edges to depends_on_json first';
  END IF;
END $$;
--> statement-breakpoint
DROP POLICY "vh_task_dependency_tenant_policy" ON "vh_task_dependency" CASCADE;--> statement-breakpoint
DROP TABLE "vh_task_dependency" CASCADE;--> statement-breakpoint
ALTER TABLE "vh_task" ADD COLUMN "depends_on_json" jsonb DEFAULT '{"taskIds":[]}'::jsonb NOT NULL;--> statement-breakpoint
ALTER TABLE "vh_task" ADD CONSTRAINT "vh_task_depends_on_json_ck" CHECK (jsonb_typeof("vh_task"."depends_on_json") = 'object' AND jsonb_typeof("vh_task"."depends_on_json"->'taskIds') = 'array');
--> statement-breakpoint
CREATE OR REPLACE FUNCTION workforce_dependency_acyclic() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE has_cycle boolean;
BEGIN
  IF TG_OP='UPDATE' THEN
    RAISE EXCEPTION 'replace dependency edges using delete and insert' USING ERRCODE='23514';
  END IF;
  PERFORM 1 FROM platform_workflow_session WHERE tenant_id=NEW.tenant_id AND id=NEW.workflow_session_id FOR UPDATE;
  WITH RECURSIVE reach(id) AS (
    SELECT NEW.depends_on_run_step_id
    UNION SELECT d.depends_on_run_step_id FROM platform_run_step_dependency d JOIN reach r ON d.run_step_id=r.id
      WHERE d.tenant_id=NEW.tenant_id AND d.workflow_session_id=NEW.workflow_session_id
  ) SELECT EXISTS(SELECT 1 FROM reach WHERE id=NEW.run_step_id) INTO has_cycle;
  IF has_cycle THEN RAISE EXCEPTION 'dependency graph cannot contain a cycle' USING ERRCODE='23514'; END IF;
  RETURN NEW;
END $$;
--> statement-breakpoint
CREATE FUNCTION vh_task_json_dependency_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE dep uuid; has_cycle boolean; dep_count integer; distinct_count integer;
BEGIN
  -- Serialize changes to one Incident graph, including concurrent edits on different Task rows.
  PERFORM 1 FROM vh_incident WHERE tenant_id=NEW.tenant_id AND project_id=NEW.project_id AND id=NEW.incident_id FOR UPDATE;
  BEGIN
    SELECT count(*),count(DISTINCT value::uuid) INTO dep_count,distinct_count
      FROM jsonb_array_elements_text(NEW.depends_on_json->'taskIds');
  EXCEPTION WHEN invalid_text_representation THEN
    RAISE EXCEPTION 'Dependency ids must be UUID strings' USING ERRCODE='23514';
  END;
  IF dep_count <> distinct_count THEN
    RAISE EXCEPTION 'Duplicate task dependency' USING ERRCODE='23514';
  END IF;
  FOR dep IN SELECT value::uuid FROM jsonb_array_elements_text(NEW.depends_on_json->'taskIds') LOOP
    IF NOT EXISTS (
      SELECT 1 FROM vh_task WHERE tenant_id=NEW.tenant_id AND project_id=NEW.project_id
       AND incident_id=NEW.incident_id AND id=dep
    ) THEN
      RAISE EXCEPTION 'Task dependency must belong to the same Incident' USING ERRCODE='23514';
    END IF;
  END LOOP;
  WITH RECURSIVE reach(id) AS (
    SELECT value::uuid FROM jsonb_array_elements_text(NEW.depends_on_json->'taskIds')
    UNION
    SELECT value::uuid FROM vh_task t JOIN reach r ON t.id=r.id,
      LATERAL jsonb_array_elements_text(t.depends_on_json->'taskIds') AS value
      WHERE t.tenant_id=NEW.tenant_id AND t.project_id=NEW.project_id AND t.incident_id=NEW.incident_id
  ) SELECT EXISTS(SELECT 1 FROM reach WHERE id=NEW.id) INTO has_cycle;
  IF has_cycle THEN RAISE EXCEPTION 'Task dependency graph cannot contain a cycle' USING ERRCODE='23514'; END IF;
  RETURN NEW;
END $$;
--> statement-breakpoint
CREATE TRIGGER vh_task_json_dependency_guard BEFORE INSERT OR UPDATE OF depends_on_json ON vh_task
  FOR EACH ROW EXECUTE FUNCTION vh_task_json_dependency_guard();
