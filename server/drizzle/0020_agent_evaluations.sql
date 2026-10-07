-- Agent evaluation V1 (docs/teams/dong/eval_agent.md). The worker registers the environment and its
-- catalog (fixtures, documents, tools) so a hand-written suite is checked without calling the sandbox.
-- Source side: suites of exactly four cases, runs, per-case results and progress events, owned by the
-- source tenant. Sandbox side: a marker, synthetic fixture profiles and full tool-call traces. Those three
-- are only ever written in the evaluation sandbox database; production has no marker, so its gateway
-- never stores tool arguments or results.
CREATE TABLE vh_agent_eval_environments (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 tenant_id uuid NOT NULL DEFAULT nullif(current_setting('app.tenant_id',true),'')::uuid REFERENCES tenants(id),
 name text NOT NULL DEFAULT 'default', status text NOT NULL CHECK(status IN ('ready','disabled')),
 execution_tenant_id uuid NOT NULL, fixture_version text NOT NULL CHECK(length(fixture_version) BETWEEN 1 AND 120),
 runtime_profile jsonb NOT NULL, catalog jsonb NOT NULL DEFAULT '{}'::jsonb, catalog_updated_at timestamptz,
 created_by text REFERENCES users(id),
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(tenant_id,id), UNIQUE(tenant_id,name), CHECK(execution_tenant_id <> tenant_id)
);
--> statement-breakpoint
CREATE TABLE vh_agent_eval_suites (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 tenant_id uuid NOT NULL DEFAULT nullif(current_setting('app.tenant_id',true),'')::uuid REFERENCES tenants(id),
 room_id text NOT NULL, agent_id text NOT NULL, revision integer NOT NULL CHECK(revision > 0),
 configuration_hash text NOT NULL CHECK(configuration_hash ~ '^[a-f0-9]{64}$'),
 status text NOT NULL CHECK(status IN ('draft','approved','archived')),
 generation_context jsonb, generator_profile jsonb, problems jsonb NOT NULL DEFAULT '[]'::jsonb,
 suite_hash text CHECK(suite_hash ~ '^[a-f0-9]{64}$'), version bigint NOT NULL DEFAULT 0,
 created_by text NOT NULL REFERENCES users(id), approved_by text REFERENCES users(id), approved_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(tenant_id,id), UNIQUE(tenant_id,agent_id,revision),
 FOREIGN KEY(tenant_id,agent_id) REFERENCES agents(tenant_id,id), FOREIGN KEY(tenant_id,room_id) REFERENCES channels(tenant_id,id),
 CHECK(status <> 'approved' OR (approved_by IS NOT NULL AND approved_at IS NOT NULL AND suite_hash IS NOT NULL AND problems = '[]'::jsonb))
);
--> statement-breakpoint
CREATE TABLE vh_agent_eval_cases (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 tenant_id uuid NOT NULL DEFAULT nullif(current_setting('app.tenant_id',true),'')::uuid REFERENCES tenants(id),
 suite_id uuid NOT NULL, ordinal smallint NOT NULL CHECK(ordinal BETWEEN 1 AND 4),
 name text NOT NULL CHECK(length(name) BETWEEN 1 AND 120),
 kind text NOT NULL CHECK(kind IN ('in_scope','out_of_scope','collaboration','boundary')),
 source text NOT NULL CHECK(source IN ('generated','manual')),
 input jsonb NOT NULL, expectations jsonb NOT NULL, rubric jsonb NOT NULL, metric_policy jsonb NOT NULL DEFAULT '{}'::jsonb,
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(tenant_id,id), UNIQUE(tenant_id,suite_id,ordinal), UNIQUE(tenant_id,suite_id,name),
 FOREIGN KEY(tenant_id,suite_id) REFERENCES vh_agent_eval_suites(tenant_id,id)
);
--> statement-breakpoint
-- An approved suite is immutable: changing a case means a new revision that is approved again.
CREATE FUNCTION vh_agent_eval_cases_frozen() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF EXISTS(SELECT 1 FROM vh_agent_eval_suites s WHERE s.id = coalesce(NEW.suite_id, OLD.suite_id) AND s.status <> 'draft') THEN
  RAISE EXCEPTION 'cases of an approved suite are immutable' USING ERRCODE = 'check_violation';
 END IF;
 RETURN coalesce(NEW, OLD);
END $$;
--> statement-breakpoint
CREATE TRIGGER vh_agent_eval_cases_frozen BEFORE INSERT OR UPDATE OR DELETE ON vh_agent_eval_cases
 FOR EACH ROW EXECUTE FUNCTION vh_agent_eval_cases_frozen();
--> statement-breakpoint
CREATE TABLE vh_agent_eval_runs (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 tenant_id uuid NOT NULL DEFAULT nullif(current_setting('app.tenant_id',true),'')::uuid REFERENCES tenants(id),
 suite_id uuid NOT NULL, environment_id uuid NOT NULL, room_id text NOT NULL, agent_id text NOT NULL,
 request_id text NOT NULL CHECK(length(request_id) BETWEEN 1 AND 120), request_hash text NOT NULL,
 configuration_hash text NOT NULL CHECK(configuration_hash ~ '^[a-f0-9]{64}$'),
 suite_hash text NOT NULL, snapshot_hash text NOT NULL, snapshot jsonb NOT NULL,
 status text NOT NULL CHECK(status IN ('queued','running','completed','failed','interrupted','cancelled')),
 passed boolean, summary jsonb NOT NULL DEFAULT '{}'::jsonb, error jsonb,
 lease_owner text, lease_expires_at timestamptz, heartbeat_at timestamptz,
 requested_by text NOT NULL REFERENCES users(id), created_at timestamptz NOT NULL DEFAULT now(),
 started_at timestamptz, finished_at timestamptz, updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(tenant_id,id), UNIQUE(tenant_id,agent_id,request_id),
 FOREIGN KEY(tenant_id,suite_id) REFERENCES vh_agent_eval_suites(tenant_id,id),
 FOREIGN KEY(tenant_id,environment_id) REFERENCES vh_agent_eval_environments(tenant_id,id),
 FOREIGN KEY(tenant_id,agent_id) REFERENCES agents(tenant_id,id),
 -- Only a completed run carries a verdict, and the API computes it; nothing else is a pass.
 CHECK((status = 'completed') = (passed IS NOT NULL))
);
--> statement-breakpoint
CREATE UNIQUE INDEX vh_agent_eval_runs_one_active ON vh_agent_eval_runs(tenant_id,environment_id) WHERE status IN ('queued','running');
--> statement-breakpoint
CREATE INDEX vh_agent_eval_runs_agent ON vh_agent_eval_runs(tenant_id,agent_id,created_at DESC);
--> statement-breakpoint
CREATE TABLE vh_agent_eval_case_results (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 tenant_id uuid NOT NULL DEFAULT nullif(current_setting('app.tenant_id',true),'')::uuid REFERENCES tenants(id),
 run_id uuid NOT NULL, case_id uuid NOT NULL, ordinal smallint NOT NULL CHECK(ordinal BETWEEN 1 AND 4),
 status text NOT NULL CHECK(status IN ('pending','running','passed','failed','error')),
 execution_refs jsonb NOT NULL DEFAULT '{}'::jsonb, trace jsonb, final_response text, terminal_state text,
 checks jsonb, judge jsonb, metrics jsonb NOT NULL DEFAULT '[]'::jsonb, environment jsonb,
 usage jsonb NOT NULL DEFAULT '{}'::jsonb, failure_layers jsonb NOT NULL DEFAULT '[]'::jsonb, error jsonb,
 started_at timestamptz, finished_at timestamptz, latency_ms bigint CHECK(latency_ms >= 0),
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(tenant_id,id), UNIQUE(tenant_id,run_id,case_id), UNIQUE(tenant_id,run_id,ordinal),
 FOREIGN KEY(tenant_id,run_id) REFERENCES vh_agent_eval_runs(tenant_id,id),
 FOREIGN KEY(tenant_id,case_id) REFERENCES vh_agent_eval_cases(tenant_id,id)
);
--> statement-breakpoint
CREATE TABLE vh_agent_eval_events (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 tenant_id uuid NOT NULL DEFAULT nullif(current_setting('app.tenant_id',true),'')::uuid REFERENCES tenants(id),
 run_id uuid NOT NULL, case_id uuid, seq bigint NOT NULL CHECK(seq > 0),
 kind text NOT NULL CHECK(kind IN ('lifecycle','message','routing','tool','retrieval','state','error')),
 actor_ref jsonb, payload jsonb NOT NULL, occurred_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(tenant_id,id), UNIQUE(tenant_id,run_id,seq),
 FOREIGN KEY(tenant_id,run_id) REFERENCES vh_agent_eval_runs(tenant_id,id),
 FOREIGN KEY(tenant_id,case_id) REFERENCES vh_agent_eval_cases(tenant_id,id)
);
--> statement-breakpoint
CREATE INDEX vh_agent_eval_events_case ON vh_agent_eval_events(tenant_id,run_id,case_id,seq);
--> statement-breakpoint
-- A publication made after this release cites the passing run it rests on.
ALTER TABLE vh_agent_reviews ADD COLUMN evaluation_run_id uuid;
--> statement-breakpoint
ALTER TABLE vh_agent_reviews ADD CONSTRAINT vh_agent_reviews_evaluation_run_fkey FOREIGN KEY(tenant_id,evaluation_run_id) REFERENCES vh_agent_eval_runs(tenant_id,id);
--> statement-breakpoint
-- The judge and the case generator run on a model of their own, apart from the agents under test.
ALTER TABLE admin_role_models DROP CONSTRAINT admin_role_models_role_check;
--> statement-breakpoint
ALTER TABLE admin_role_models ADD CONSTRAINT admin_role_models_role_check CHECK(role IN ('reception','supervisor','specialist','factory','embedding','evaluator'));
--> statement-breakpoint
-- Sandbox side. The marker row exists only in the sandbox database's own tenant.
CREATE TABLE vh_agent_eval_sandbox (
 tenant_id uuid PRIMARY KEY REFERENCES tenants(id), source_database text NOT NULL,
 fixture_version text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 CHECK(source_database <> current_database())
);
--> statement-breakpoint
CREATE TABLE vh_agent_eval_fixtures (
 tenant_id uuid NOT NULL DEFAULT nullif(current_setting('app.tenant_id',true),'')::uuid REFERENCES vh_agent_eval_sandbox(tenant_id),
 id text NOT NULL CHECK(id ~ '^[a-z0-9-]{1,60}$'), user_id text NOT NULL REFERENCES users(id),
 unit_id uuid NOT NULL, building_id uuid NOT NULL, description text NOT NULL,
 PRIMARY KEY(tenant_id,id), UNIQUE(tenant_id,user_id),
 FOREIGN KEY(tenant_id,unit_id) REFERENCES units(tenant_id,id), FOREIGN KEY(tenant_id,building_id) REFERENCES buildings(tenant_id,id)
);
--> statement-breakpoint
CREATE TABLE vh_agent_eval_tool_traces (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 tenant_id uuid NOT NULL DEFAULT nullif(current_setting('app.tenant_id',true),'')::uuid REFERENCES vh_agent_eval_sandbox(tenant_id),
 agent_run_id uuid NOT NULL, agent_id text NOT NULL, server_id text, tool text NOT NULL,
 arguments jsonb NOT NULL, status text NOT NULL, result jsonb, created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
--> statement-breakpoint
CREATE INDEX vh_agent_eval_tool_traces_run ON vh_agent_eval_tool_traces(tenant_id,agent_run_id,created_at);
--> statement-breakpoint
DO $$ DECLARE name text; BEGIN
 FOREACH name IN ARRAY ARRAY['vh_agent_eval_environments','vh_agent_eval_suites','vh_agent_eval_cases','vh_agent_eval_runs',
   'vh_agent_eval_case_results','vh_agent_eval_events','vh_agent_eval_sandbox','vh_agent_eval_fixtures','vh_agent_eval_tool_traces'] LOOP
  EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY',name);
  EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY',name);
  EXECUTE format('CREATE POLICY tenant_scope ON %I USING (tenant_id=nullif(current_setting(''app.tenant_id'',true),'''')::uuid) WITH CHECK (tenant_id=nullif(current_setting(''app.tenant_id'',true),'''')::uuid)',name);
 END LOOP;
END $$;
--> statement-breakpoint
DO $$ BEGIN IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='vinhomes_v3_api') THEN
 GRANT SELECT,INSERT,UPDATE ON vh_agent_eval_environments,vh_agent_eval_suites,vh_agent_eval_runs,vh_agent_eval_case_results TO vinhomes_v3_api;
 GRANT SELECT,INSERT,DELETE ON vh_agent_eval_cases TO vinhomes_v3_api;
 GRANT SELECT,INSERT ON vh_agent_eval_events,vh_agent_eval_tool_traces TO vinhomes_v3_api;
 GRANT SELECT ON vh_agent_eval_sandbox,vh_agent_eval_fixtures TO vinhomes_v3_api;
END IF; END $$;
