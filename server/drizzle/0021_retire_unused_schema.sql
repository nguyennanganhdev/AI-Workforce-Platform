-- Retire only the nine empty legacy/reserved tables reviewed on 2026-10-07.
-- Refuse to discard data if another deployment still uses any of them.
SET LOCAL lock_timeout = '10s';
--> statement-breakpoint
-- Idempotent so an explicitly applied maintenance transaction can later be replayed
-- by the ordered migrator without skipping another team's pending migration.
DO $$
DECLARE table_name text;
BEGIN
  FOREACH table_name IN ARRAY ARRAY[
    'user_roles', 'model_profiles', 'agent_build_requests', 'agent_build_answers',
    'reception_sessions', 'reception_waits', 'runtime_session_operations',
    'report_requests', 'report_sources', 'agent_versions', 'files'
  ] LOOP
    IF to_regclass(format('public.%I', table_name)) IS NOT NULL THEN
      EXECUTE format('LOCK TABLE public.%I IN ACCESS EXCLUSIVE MODE', table_name);
    END IF;
  END LOOP;
END $$;
--> statement-breakpoint
DO $$
DECLARE table_name text; occupied boolean;
BEGIN
  FOREACH table_name IN ARRAY ARRAY[
    'user_roles', 'model_profiles', 'agent_build_requests', 'agent_build_answers',
    'reception_sessions', 'reception_waits', 'runtime_session_operations',
    'report_requests', 'report_sources'
  ] LOOP
    IF to_regclass(format('public.%I', table_name)) IS NOT NULL THEN
      EXECUTE format('SELECT EXISTS (SELECT 1 FROM public.%I)', table_name) INTO occupied;
      IF occupied THEN
        RAISE EXCEPTION 'Refusing to retire nonempty table public.%', table_name;
      END IF;
    END IF;
  END LOOP;
  IF EXISTS (SELECT 1 FROM pg_attribute WHERE attrelid='public.agent_versions'::regclass AND attname='model_profile_id' AND NOT attisdropped) THEN
    EXECUTE 'SELECT EXISTS (SELECT 1 FROM public.agent_versions WHERE model_profile_id IS NOT NULL)' INTO occupied;
    IF occupied THEN RAISE EXCEPTION 'Refusing to retire referenced model profiles'; END IF;
  END IF;
  IF EXISTS (SELECT 1 FROM public.files WHERE scope_kind = 'report') THEN
    RAISE EXCEPTION 'Refusing to retire report-scoped files';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_attribute WHERE attrelid='public.files'::regclass AND attname='report_id' AND NOT attisdropped) THEN
    EXECUTE 'SELECT EXISTS (SELECT 1 FROM public.files WHERE report_id IS NOT NULL)' INTO occupied;
    IF occupied THEN RAISE EXCEPTION 'Refusing to retire referenced report requests'; END IF;
  END IF;
END $$;
--> statement-breakpoint
ALTER TABLE public.agent_versions DROP CONSTRAINT IF EXISTS agent_versions_model_profile_id_fk;
--> statement-breakpoint
ALTER TABLE public.agent_versions DROP COLUMN IF EXISTS model_profile_id;
--> statement-breakpoint
ALTER TABLE public.files DROP CONSTRAINT IF EXISTS files_report_id_fk;
--> statement-breakpoint
ALTER TABLE public.files DROP CONSTRAINT files_check_0;
--> statement-breakpoint
ALTER TABLE public.files DROP CONSTRAINT files_check_1;
--> statement-breakpoint
ALTER TABLE public.files DROP CONSTRAINT files_check_3;
--> statement-breakpoint
ALTER TABLE public.files DROP COLUMN IF EXISTS report_id;
--> statement-breakpoint
ALTER TABLE public.files ADD CONSTRAINT files_check_0
  CHECK (num_nonnulls(ticket_id, channel_id, document_id, unit_id) = 1);
--> statement-breakpoint
ALTER TABLE public.files ADD CONSTRAINT files_check_1 CHECK (
  (scope_kind = 'ticket' AND ticket_id IS NOT NULL) OR
  (scope_kind = 'channel' AND channel_id IS NOT NULL) OR
  (scope_kind = 'document' AND document_id IS NOT NULL) OR
  (scope_kind = 'resident' AND unit_id IS NOT NULL)
);
--> statement-breakpoint
ALTER TABLE public.files ADD CONSTRAINT files_check_3
  CHECK (scope_kind IN ('ticket', 'channel', 'document', 'resident'));
--> statement-breakpoint
CREATE OR REPLACE FUNCTION app_validate_file() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE obj file_objects;
BEGIN
 IF NEW.accepted_object_id IS NOT NULL THEN
  SELECT * INTO STRICT obj FROM file_objects WHERE id=NEW.accepted_object_id AND tenant_id=NEW.tenant_id;
  IF obj.file_id<>NEW.id OR obj.variant<>'original' THEN RAISE EXCEPTION 'Accepted original object belongs to a different file'; END IF;
  IF NEW.status='ready' AND (obj.status<>'ready' OR obj.scan_status<>'clean' OR obj.verified_at IS NULL) THEN RAISE EXCEPTION 'File is not verified'; END IF;
 END IF;
 IF TG_OP='UPDATE' AND OLD.accepted_object_id IS NOT NULL AND NEW.accepted_object_id IS DISTINCT FROM OLD.accepted_object_id THEN RAISE EXCEPTION 'Accepted bytes are immutable'; END IF;
 IF TG_OP='UPDATE' AND (NEW.tenant_id,NEW.owner_principal_id,NEW.scope_kind,NEW.ticket_id,NEW.channel_id,NEW.document_id,NEW.unit_id) IS DISTINCT FROM (OLD.tenant_id,OLD.owner_principal_id,OLD.scope_kind,OLD.ticket_id,OLD.channel_id,OLD.document_id,OLD.unit_id) THEN RAISE EXCEPTION 'File security scope is immutable'; END IF;
 RETURN NEW;
END $$;
--> statement-breakpoint
DROP TABLE IF EXISTS public.agent_build_answers;
--> statement-breakpoint
DROP TABLE IF EXISTS public.agent_build_requests;
--> statement-breakpoint
DROP TABLE IF EXISTS public.reception_waits;
--> statement-breakpoint
DROP TABLE IF EXISTS public.reception_sessions;
--> statement-breakpoint
DROP TABLE IF EXISTS public.runtime_session_operations;
--> statement-breakpoint
DROP TABLE IF EXISTS public.report_sources;
--> statement-breakpoint
DROP TABLE IF EXISTS public.report_requests;
--> statement-breakpoint
DROP TABLE IF EXISTS public.model_profiles;
--> statement-breakpoint
DROP TABLE IF EXISTS public.user_roles;
