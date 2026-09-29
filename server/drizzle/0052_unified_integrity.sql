-- Integrity for the canonical OpenBot registries and PostgreSQL transcript.
-- RLS isolates tenants. Request authorization and channel readership still belong to the application.
DO $$ DECLARE n text;
BEGIN
  FOREACH n IN ARRAY ARRAY['agents','channels','channel_memberships','channel_agents','credentials',
    'audit_events','attachments','intelligence_channel_mappings','agent_profiles','agent_preferences',
    'routines','routine_runs','mcp_servers','mcp_tools','skills','skill_tools','plugin_grants',
    'mcp_user_credentials','composio_connections','sandboxed_components','voice_sessions',
    'channel_messages','channel_subjects'] LOOP
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY',n);
  END LOOP;
END $$;
--> statement-breakpoint
CREATE FUNCTION product_identity_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF (to_jsonb(NEW)->'tenant_id') IS DISTINCT FROM (to_jsonb(OLD)->'tenant_id') THEN
    RAISE EXCEPTION 'tenant ownership cannot change' USING ERRCODE='23514';
  END IF;
  IF TG_TABLE_NAME IN ('agents','channels','mcp_servers','skills') THEN
    IF NEW.id IS DISTINCT FROM OLD.id OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
      RAISE EXCEPTION 'canonical identity cannot change' USING ERRCODE='23514';
    END IF;
    IF NEW.revision NOT IN (OLD.revision, OLD.revision+1) THEN
      RAISE EXCEPTION 'invalid optimistic revision' USING ERRCODE='40001';
    END IF;
    NEW.revision := OLD.revision+1;
    NEW.updated_at := clock_timestamp();
  END IF;
  RETURN NEW;
END $$;
--> statement-breakpoint
DO $$ DECLARE n text;
BEGIN
  FOREACH n IN ARRAY ARRAY['agents','channels','channel_memberships','channel_agents','credentials',
    'audit_events','attachments','intelligence_channel_mappings','agent_profiles','agent_preferences',
    'routines','routine_runs','mcp_servers','mcp_tools','skills','skill_tools','plugin_grants',
    'mcp_user_credentials','composio_connections','sandboxed_components','voice_sessions'] LOOP
    EXECUTE format('CREATE TRIGGER product_identity_immutable BEFORE UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION product_identity_immutable()',n);
  END LOOP;
END $$;
--> statement-breakpoint
CREATE FUNCTION product_channel_message() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE last_seq bigint; parent_seq bigint; c channels;
BEGIN
  SELECT * INTO c FROM channels WHERE tenant_id=NEW.tenant_id AND id=NEW.channel_id FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'channel not found in tenant' USING ERRCODE='23503'; END IF;
  IF c.status <> 'ACTIVE' OR c.deleted_at IS NOT NULL THEN
    RAISE EXCEPTION 'channel is not active' USING ERRCODE='23514';
  END IF;
  IF NEW.role='USER' AND NOT EXISTS (
    SELECT 1 FROM channel_memberships cm JOIN platform_tenant_membership tm
      ON tm.tenant_id=cm.tenant_id AND tm.user_id=cm.user_id
    WHERE cm.tenant_id=NEW.tenant_id AND cm.channel_id=NEW.channel_id AND cm.user_id=NEW.author_user_id
      AND tm.status='ACTIVE' AND tm.valid_from<=now() AND (tm.valid_until IS NULL OR tm.valid_until>now())
  ) THEN RAISE EXCEPTION 'message author must be an active channel member' USING ERRCODE='23514'; END IF;
  IF NEW.role='ASSISTANT' AND NOT EXISTS (
    SELECT 1 FROM channel_agents ca JOIN agents a ON a.tenant_id=ca.tenant_id AND a.id=ca.agent_id
    WHERE ca.tenant_id=NEW.tenant_id AND ca.channel_id=NEW.channel_id AND ca.agent_id=NEW.author_agent_id AND a.status='ACTIVE'
  ) THEN RAISE EXCEPTION 'assistant must be active and assigned to channel' USING ERRCODE='23514'; END IF;
  SELECT coalesce(max(sequence_no),0) INTO last_seq FROM channel_messages WHERE tenant_id=NEW.tenant_id AND channel_id=NEW.channel_id;
  IF NEW.sequence_no<>last_seq+1 THEN RAISE EXCEPTION 'append at next channel sequence under parent lock' USING ERRCODE='23514'; END IF;
  IF NEW.reply_to_message_id IS NOT NULL THEN
    SELECT sequence_no INTO parent_seq FROM channel_messages WHERE tenant_id=NEW.tenant_id AND channel_id=NEW.channel_id AND id=NEW.reply_to_message_id;
    IF parent_seq IS NULL OR parent_seq>=NEW.sequence_no THEN
      RAISE EXCEPTION 'reply must address an earlier message in this channel' USING ERRCODE='23514';
    END IF;
  END IF;
  RETURN NEW;
END $$;
--> statement-breakpoint
CREATE TRIGGER channel_messages_order BEFORE INSERT ON channel_messages FOR EACH ROW EXECUTE FUNCTION product_channel_message();
--> statement-breakpoint
CREATE TRIGGER channel_messages_immutable BEFORE UPDATE OR DELETE ON channel_messages FOR EACH ROW EXECUTE FUNCTION workforce_append_only();
--> statement-breakpoint
CREATE TRIGGER channel_messages_no_truncate BEFORE TRUNCATE ON channel_messages FOR EACH STATEMENT EXECUTE FUNCTION workforce_append_only();
--> statement-breakpoint
-- Commit a canonical message and its delivery intent together. No second transcript owner.
CREATE FUNCTION product_channel_message_outbox() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  INSERT INTO platform_outbox_event(tenant_id,aggregate_type,aggregate_id,event_type,payload_json,status,attempt_count,available_at)
  VALUES(NEW.tenant_id,'CHANNEL',NEW.channel_id,'CHANNEL_MESSAGE_COMMITTED',
    jsonb_build_object('schemaVersion',1,'messageId',NEW.id,'channelId',NEW.channel_id,'sequenceNo',NEW.sequence_no::text),
    'PENDING',0,now());
  RETURN NEW;
END $$;
--> statement-breakpoint
CREATE TRIGGER channel_messages_outbox AFTER INSERT ON channel_messages FOR EACH ROW EXECUTE FUNCTION product_channel_message_outbox();
--> statement-breakpoint
CREATE FUNCTION product_tool_identity() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='UPDATE' AND (NEW.provider_type,NEW.mcp_server_id,NEW.mcp_tool_name,NEW.handler_key)
      IS DISTINCT FROM (OLD.provider_type,OLD.mcp_server_id,OLD.mcp_tool_name,OLD.handler_key) THEN
    RAISE EXCEPTION 'tool execution target is immutable; register a new tool' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END $$;
--> statement-breakpoint
CREATE TRIGGER product_tool_identity BEFORE UPDATE ON platform_tool FOR EACH ROW EXECUTE FUNCTION product_tool_identity();
--> statement-breakpoint
CREATE FUNCTION product_tool_version_source() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE tool platform_tool; server_id text;
BEGIN
  SELECT * INTO tool FROM platform_tool WHERE tenant_id=NEW.tenant_id AND id=NEW.tool_id;
  IF tool.provider_type='MCP' THEN
    SELECT mcp_server_id INTO server_id FROM platform_mcp_server_version WHERE tenant_id=NEW.tenant_id AND id=NEW.mcp_server_version_id;
    IF server_id IS DISTINCT FROM tool.mcp_server_id THEN
      RAISE EXCEPTION 'MCP tool revision must pin its own server revision' USING ERRCODE='23514';
    END IF;
  ELSIF NEW.mcp_server_version_id IS NOT NULL THEN
    RAISE EXCEPTION 'non-MCP tool cannot pin an MCP server' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END $$;
--> statement-breakpoint
CREATE TRIGGER product_tool_version_source BEFORE INSERT OR UPDATE ON platform_tool_version FOR EACH ROW EXECUTE FUNCTION product_tool_version_source();

--> statement-breakpoint
CREATE OR REPLACE FUNCTION platform_coordination_message() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE last_seq bigint; parent_seq bigint; sender platform_session_participant; run_version uuid;
BEGIN
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
  IF NEW.sequence_no <> last_seq+1 THEN RAISE EXCEPTION 'append message at the next sequence under its parent lock' USING ERRCODE='23514'; END IF;
  IF NEW.reply_to_message_id IS NOT NULL AND (parent_seq IS NULL OR parent_seq>=NEW.sequence_no) THEN
    RAISE EXCEPTION 'reply must reference an earlier message in the same conversation/session' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END $$;
