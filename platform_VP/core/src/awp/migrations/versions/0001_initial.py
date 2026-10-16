"""Initial schema: a frozen snapshot of every table, index and constraint of awp/db.py and workforce/tables.py.

It deliberately does not call `metadata.create_all`: that would make this revision follow the current models, and a later
change would be applied twice on a new database (once here, once by its own revision). Every later change to the models is a new
revision on top of this one (`tests/workforce/test_wf_migrations.py` fails when the models and the revisions disagree).

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-11 03:43:52
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('awp_agent_map',
    sa.Column('tenant', sa.String(length=80), nullable=False),
    sa.Column('key', sa.String(length=80), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('agent_id', sa.String(length=60), nullable=False),
    sa.PrimaryKeyConstraint('tenant', 'key', 'version')
    )
    op.create_table('awp_case_items',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('case_id', sa.String(length=40), nullable=False),
    sa.Column('ref', sa.String(length=16), nullable=False),
    sa.Column('kind', sa.String(length=16), nullable=False),
    sa.Column('author', sa.String(length=80), nullable=False),
    sa.Column('addressee', sa.String(length=80), nullable=True),
    sa.Column('data', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.Float(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('case_id', 'ref', name='uq_item_ref')
    )
    op.create_index('ix_item_case', 'awp_case_items', ['case_id', 'id'], unique=False)

    op.create_table('awp_case_sessions',
    sa.Column('session_id', sa.String(length=60), nullable=False),
    sa.Column('case_id', sa.String(length=40), nullable=False),
    sa.Column('agent_id', sa.String(length=60), nullable=False),
    sa.Column('agent_name', sa.String(length=80), nullable=False),
    sa.Column('role', sa.String(length=12), nullable=False),
    sa.PrimaryKeyConstraint('session_id')
    )
    op.create_index(op.f('ix_awp_case_sessions_case_id'), 'awp_case_sessions', ['case_id'], unique=False)

    op.create_table('awp_cases',
    sa.Column('id', sa.String(length=40), nullable=False),
    sa.Column('tenant', sa.String(length=80), nullable=False),
    sa.Column('domain', sa.String(length=80), nullable=False),
    sa.Column('external_ref', sa.String(length=200), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('user_id', sa.String(length=200), nullable=False),
    sa.Column('leader_agent_id', sa.String(length=60), nullable=True),
    sa.Column('leader_session_id', sa.String(length=60), nullable=True),
    sa.Column('meta', sa.JSON(), nullable=False),
    sa.Column('result', sa.JSON(), nullable=True),
    sa.Column('budget_usd', sa.Float(), nullable=False),
    sa.Column('budget_tokens', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.Float(), nullable=False),
    sa.Column('updated_at', sa.Float(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tenant', 'domain', 'external_ref', name='uq_case_external')
    )
    op.create_index(op.f('ix_awp_cases_tenant'), 'awp_cases', ['tenant'], unique=False)

    op.create_table('awp_credential_map',
    sa.Column('user_id', sa.String(length=120), nullable=False),
    sa.Column('spec_id', sa.String(length=80), nullable=False),
    sa.Column('credential_id', sa.String(length=60), nullable=False),
    sa.PrimaryKeyConstraint('user_id', 'spec_id')
    )
    op.create_table('awp_cursors',
    sa.Column('case_id', sa.String(length=40), nullable=False),
    sa.Column('agent_key', sa.String(length=120), nullable=False),
    sa.Column('last_item_id', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('case_id', 'agent_key')
    )
    op.create_table('awp_ledger',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant', sa.String(length=80), nullable=False),
    sa.Column('case_id', sa.String(length=40), nullable=True),
    sa.Column('session_id', sa.String(length=60), nullable=True),
    sa.Column('agent_id', sa.String(length=60), nullable=True),
    sa.Column('agent_name', sa.String(length=80), nullable=True),
    sa.Column('model', sa.String(length=120), nullable=False),
    sa.Column('tier', sa.String(length=16), nullable=True),
    sa.Column('input_tokens', sa.Integer(), nullable=False),
    sa.Column('output_tokens', sa.Integer(), nullable=False),
    sa.Column('cache_read_tokens', sa.Integer(), nullable=False),
    sa.Column('cache_write_tokens', sa.Integer(), nullable=False),
    sa.Column('cost_usd', sa.Float(), nullable=False),
    sa.Column('priced', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.Float(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_awp_ledger_case_id'), 'awp_ledger', ['case_id'], unique=False)
    op.create_index(op.f('ix_awp_ledger_tenant'), 'awp_ledger', ['tenant'], unique=False)

    op.create_table('awp_profiles',
    sa.Column('id', sa.String(length=40), nullable=False),
    sa.Column('tenant', sa.String(length=80), nullable=False),
    sa.Column('key', sa.String(length=80), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=12), nullable=False),
    sa.Column('data', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.Float(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tenant', 'key', 'version', name='uq_profile_version')
    )
    op.create_table('wf_approvals',
    sa.Column('id', sa.String(length=48), nullable=False),
    sa.Column('workflow_id', sa.String(length=48), nullable=False),
    sa.Column('conversation_id', sa.String(length=48), nullable=False),
    sa.Column('client_id', sa.String(length=48), nullable=False),
    sa.Column('external_user_id', sa.String(length=200), nullable=False),
    sa.Column('session_id', sa.String(length=60), nullable=False),
    sa.Column('agent_id', sa.String(length=60), nullable=False),
    sa.Column('tool_call_id', sa.String(length=120), nullable=False),
    sa.Column('tool_name', sa.String(length=80), nullable=False),
    sa.Column('arguments', sa.Text(), nullable=False),
    sa.Column('arguments_hash', sa.String(length=80), nullable=False),
    sa.Column('quote_ref', sa.String(length=80), nullable=True),
    sa.Column('summary', sa.JSON(), nullable=False),
    sa.Column('status', sa.String(length=12), nullable=False),
    sa.Column('workflow_revision', sa.Integer(), nullable=False),
    sa.Column('expires_at', sa.Float(), nullable=True),
    sa.Column('decided_at', sa.Float(), nullable=True),
    sa.Column('decision_request_id', sa.String(length=48), nullable=True),
    sa.Column('reply_id', sa.String(length=80), nullable=True),
    sa.Column('resumed_at', sa.Float(), nullable=True),
    sa.Column('used_at', sa.Float(), nullable=True),
    sa.Column('operation_id', sa.String(length=48), nullable=True),
    sa.Column('created_at', sa.Float(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('session_id', 'reply_id', 'tool_call_id', name='uq_approval_call')
    )
    op.create_index(op.f('ix_wf_approvals_workflow_id'), 'wf_approvals', ['workflow_id'], unique=False)

    op.create_table('wf_assets',
    sa.Column('id', sa.String(length=48), nullable=False),
    sa.Column('client_id', sa.String(length=48), nullable=False),
    sa.Column('conversation_id', sa.String(length=48), nullable=True),
    sa.Column('object_key', sa.Text(), nullable=False),
    sa.Column('content_type', sa.String(length=64), nullable=False),
    sa.Column('size', sa.Integer(), nullable=False),
    sa.Column('sha256', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.Float(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('wf_clients',
    sa.Column('id', sa.String(length=48), nullable=False),
    sa.Column('tenant', sa.String(length=80), nullable=False),
    sa.Column('domain', sa.String(length=80), nullable=False),
    sa.Column('environment', sa.String(length=16), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('status', sa.String(length=12), nullable=False),
    sa.Column('capabilities', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.Float(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_wf_clients_tenant'), 'wf_clients', ['tenant'], unique=False)

    op.create_table('wf_conversations',
    sa.Column('id', sa.String(length=48), nullable=False),
    sa.Column('client_id', sa.String(length=48), nullable=False),
    sa.Column('route_id', sa.String(length=48), nullable=False),
    sa.Column('external_user_id', sa.String(length=200), nullable=False),
    sa.Column('external_conversation_id', sa.String(length=200), nullable=False),
    sa.Column('external_ticket_id', sa.String(length=200), nullable=True),
    sa.Column('last_sequence', sa.Integer(), nullable=False),
    sa.Column('purged_through', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.Float(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('client_id', 'external_conversation_id', name='uq_conv_external')
    )
    op.create_table('wf_event_tombstones',
    sa.Column('event_id', sa.String(length=48), nullable=False),
    sa.Column('conversation_id', sa.String(length=48), nullable=False),
    sa.Column('sequence', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('event_id')
    )
    op.create_index(op.f('ix_wf_event_tombstones_conversation_id'), 'wf_event_tombstones', ['conversation_id'], unique=False)

    op.create_table('wf_events',
    sa.Column('event_id', sa.String(length=48), nullable=False),
    sa.Column('conversation_id', sa.String(length=48), nullable=False),
    sa.Column('sequence', sa.Integer(), nullable=False),
    sa.Column('event_type', sa.String(length=48), nullable=False),
    sa.Column('workflow_id', sa.String(length=48), nullable=True),
    sa.Column('ticket_id', sa.String(length=48), nullable=True),
    sa.Column('external_ticket_id', sa.String(length=200), nullable=True),
    sa.Column('payload', sa.JSON(), nullable=False),
    sa.Column('occurred_at', sa.Float(), nullable=False),
    sa.Column('recorded_at', sa.Float(), nullable=False),
    sa.PrimaryKeyConstraint('event_id'),
    sa.UniqueConstraint('conversation_id', 'sequence', name='uq_event_sequence')
    )
    op.create_table('wf_integrations',
    sa.Column('id', sa.String(length=48), nullable=False),
    sa.Column('client_id', sa.String(length=48), nullable=False),
    sa.Column('status', sa.String(length=12), nullable=False),
    sa.Column('event_schema', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.Float(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_wf_integrations_client_id'), 'wf_integrations', ['client_id'], unique=False)

    op.create_table('wf_jobs',
    sa.Column('id', sa.String(length=48), nullable=False),
    sa.Column('workflow_id', sa.String(length=48), nullable=False),
    sa.Column('kind', sa.String(length=24), nullable=False),
    sa.Column('request_id', sa.String(length=48), nullable=True),
    sa.Column('payload', sa.JSON(), nullable=False),
    sa.Column('status', sa.String(length=12), nullable=False),
    sa.Column('lease_owner', sa.String(length=80), nullable=True),
    sa.Column('lease_until', sa.Float(), nullable=True),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.Float(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_job_queue', 'wf_jobs', ['status', 'created_at'], unique=False)
    op.create_index('uq_job_dispatched', 'wf_jobs', ['workflow_id'], unique=True, sqlite_where=sa.text("status = 'dispatched'"), postgresql_where=sa.text("status = 'dispatched'"))

    op.create_table('wf_keys',
    sa.Column('key_id', sa.String(length=64), nullable=False),
    sa.Column('client_id', sa.String(length=48), nullable=True),
    sa.Column('integration_id', sa.String(length=48), nullable=True),
    sa.Column('kind', sa.String(length=12), nullable=False),
    sa.Column('secret_hash', sa.String(length=64), nullable=False),
    sa.Column('operations', sa.JSON(), nullable=False),
    sa.Column('routes', sa.JSON(), nullable=False),
    sa.Column('status', sa.String(length=12), nullable=False),
    sa.Column('expires_at', sa.Float(), nullable=True),
    sa.Column('created_at', sa.Float(), nullable=False),
    sa.Column('revoked_at', sa.Float(), nullable=True),
    sa.CheckConstraint("(kind = 'customer' AND client_id IS NOT NULL AND integration_id IS NULL) OR (kind = 'provider' AND integration_id IS NOT NULL AND client_id IS NULL)", name='ck_key_owner'),
    sa.PrimaryKeyConstraint('key_id')
    )
    op.create_index(op.f('ix_wf_keys_client_id'), 'wf_keys', ['client_id'], unique=False)
    op.create_index(op.f('ix_wf_keys_integration_id'), 'wf_keys', ['integration_id'], unique=False)

    op.create_table('wf_leases',
    sa.Column('name', sa.String(length=80), nullable=False),
    sa.Column('owner', sa.String(length=80), nullable=True),
    sa.Column('lease_until', sa.Float(), nullable=False),
    sa.Column('last_run_at', sa.Float(), nullable=True),
    sa.PrimaryKeyConstraint('name')
    )
    op.create_table('wf_mcp_servers',
    sa.Column('route_id', sa.String(length=48), nullable=False),
    sa.Column('name', sa.String(length=80), nullable=False),
    sa.Column('url', sa.Text(), nullable=False),
    sa.Column('transport', sa.String(length=24), nullable=False),
    sa.Column('headers_enc', sa.Text(), nullable=True),
    sa.Column('timeout', sa.Float(), nullable=False),
    sa.PrimaryKeyConstraint('route_id', 'name')
    )
    op.create_table('wf_messages',
    sa.Column('id', sa.String(length=48), nullable=False),
    sa.Column('conversation_id', sa.String(length=48), nullable=False),
    sa.Column('workflow_id', sa.String(length=48), nullable=False),
    sa.Column('request_id', sa.String(length=48), nullable=True),
    sa.Column('sender', sa.String(length=12), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('asset_ids', sa.JSON(), nullable=False),
    sa.Column('expects', sa.String(length=16), nullable=True),
    sa.Column('outcome', sa.String(length=16), nullable=True),
    sa.Column('source', sa.String(length=12), nullable=True),
    sa.Column('sequence', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.Float(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('conversation_id', 'sequence', name='uq_msg_sequence')
    )
    op.create_index(op.f('ix_wf_messages_request_id'), 'wf_messages', ['request_id'], unique=False)

    op.create_table('wf_operations',
    sa.Column('id', sa.String(length=48), nullable=False),
    sa.Column('workflow_id', sa.String(length=48), nullable=False),
    sa.Column('route_id', sa.String(length=48), nullable=False),
    sa.Column('integration_id', sa.String(length=48), nullable=True),
    sa.Column('tool_name', sa.String(length=80), nullable=False),
    sa.Column('tool_call_id', sa.String(length=120), nullable=True),
    sa.Column('args_hash', sa.String(length=80), nullable=False),
    sa.Column('client_reference', sa.String(length=120), nullable=False),
    sa.Column('external_job_id', sa.String(length=200), nullable=True),
    sa.Column('status', sa.String(length=12), nullable=False),
    sa.Column('normalized_status', sa.String(length=40), nullable=True),
    sa.Column('last_rank', sa.Integer(), nullable=True),
    sa.Column('provider_version', sa.String(length=80), nullable=True),
    sa.Column('result', sa.JSON(), nullable=True),
    sa.Column('arguments', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.Float(), nullable=False),
    sa.Column('updated_at', sa.Float(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('client_reference', name='uq_operation_reference'),
    sa.UniqueConstraint('workflow_id', 'tool_name', 'args_hash', name='uq_operation_dedupe')
    )
    op.create_index('ix_operation_job', 'wf_operations', ['integration_id', 'external_job_id'], unique=False)
    op.create_index(op.f('ix_wf_operations_workflow_id'), 'wf_operations', ['workflow_id'], unique=False)

    op.create_table('wf_provider_inbox',
    sa.Column('receipt_id', sa.String(length=48), nullable=False),
    sa.Column('integration_id', sa.String(length=48), nullable=False),
    sa.Column('external_event_id', sa.String(length=200), nullable=False),
    sa.Column('key_id', sa.String(length=64), nullable=True),
    sa.Column('sig_key_id', sa.String(length=64), nullable=True),
    sa.Column('payload_hash', sa.String(length=80), nullable=False),
    sa.Column('event_type', sa.String(length=64), nullable=False),
    sa.Column('payload', sa.JSON(), nullable=False),
    sa.Column('operation_id', sa.String(length=48), nullable=True),
    sa.Column('workflow_id', sa.String(length=48), nullable=True),
    sa.Column('ingestion_status', sa.String(length=16), nullable=False),
    sa.Column('normalized_status', sa.String(length=40), nullable=True),
    sa.Column('error', sa.JSON(), nullable=True),
    sa.Column('provider_version', sa.String(length=80), nullable=True),
    sa.Column('note', sa.String(length=40), nullable=True),
    sa.Column('received_at', sa.Float(), nullable=False),
    sa.Column('applied_at', sa.Float(), nullable=True),
    sa.Column('checked_at', sa.Float(), nullable=True),
    sa.PrimaryKeyConstraint('receipt_id'),
    sa.UniqueConstraint('integration_id', 'external_event_id', name='uq_inbox_event')
    )
    op.create_index('ix_inbox_pending', 'wf_provider_inbox', ['ingestion_status', 'received_at'], unique=False)
    op.create_index(op.f('ix_wf_provider_inbox_operation_id'), 'wf_provider_inbox', ['operation_id'], unique=False)

    op.create_table('wf_requests',
    sa.Column('id', sa.String(length=48), nullable=False),
    sa.Column('client_id', sa.String(length=48), nullable=False),
    sa.Column('external_request_id', sa.String(length=200), nullable=False),
    sa.Column('command_type', sa.String(length=24), nullable=False),
    sa.Column('fingerprint', sa.String(length=80), nullable=False),
    sa.Column('route_id', sa.String(length=48), nullable=True),
    sa.Column('conversation_id', sa.String(length=48), nullable=True),
    sa.Column('workflow_id', sa.String(length=48), nullable=True),
    sa.Column('status', sa.String(length=12), nullable=False),
    sa.Column('response', sa.JSON(), nullable=True),
    sa.Column('error', sa.JSON(), nullable=True),
    sa.Column('accepted_at', sa.Float(), nullable=False),
    sa.Column('completed_at', sa.Float(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('client_id', 'external_request_id', name='uq_request_external')
    )
    op.create_index(op.f('ix_wf_requests_workflow_id'), 'wf_requests', ['workflow_id'], unique=False)

    op.create_table('wf_residences',
    sa.Column('client_id', sa.String(length=48), nullable=False),
    sa.Column('residence_id', sa.String(length=200), nullable=False),
    sa.Column('external_user_id', sa.String(length=200), nullable=False),
    sa.Column('route_id', sa.String(length=48), nullable=False),
    sa.Column('status', sa.String(length=12), nullable=False),
    sa.Column('revision', sa.Integer(), nullable=False),
    sa.Column('updated_at', sa.Float(), nullable=False),
    sa.PrimaryKeyConstraint('client_id', 'residence_id', 'external_user_id')
    )
    op.create_table('wf_routes',
    sa.Column('id', sa.String(length=48), nullable=False),
    sa.Column('client_id', sa.String(length=48), nullable=False),
    sa.Column('external_management_ref', sa.String(length=128), nullable=False),
    sa.Column('status', sa.String(length=12), nullable=False),
    sa.Column('revision', sa.Integer(), nullable=False),
    sa.Column('leader_profile', sa.String(length=80), nullable=False),
    sa.Column('config', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.Float(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_wf_routes_client_id'), 'wf_routes', ['client_id'], unique=False)
    op.create_index('uq_route_active_ref', 'wf_routes', ['client_id', 'external_management_ref'], unique=True, sqlite_where=sa.text("status = 'active'"), postgresql_where=sa.text("status = 'active'"))

    op.create_table('wf_signing_keys',
    sa.Column('key_id', sa.String(length=64), nullable=False),
    sa.Column('integration_id', sa.String(length=48), nullable=False),
    sa.Column('secret_enc', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=12), nullable=False),
    sa.Column('created_at', sa.Float(), nullable=False),
    sa.PrimaryKeyConstraint('key_id')
    )
    op.create_index(op.f('ix_wf_signing_keys_integration_id'), 'wf_signing_keys', ['integration_id'], unique=False)

    op.create_table('wf_tools',
    sa.Column('route_id', sa.String(length=48), nullable=False),
    sa.Column('name', sa.String(length=80), nullable=False),
    sa.Column('server', sa.String(length=80), nullable=False),
    sa.Column('mcp_tool', sa.String(length=120), nullable=False),
    sa.Column('kind', sa.String(length=12), nullable=False),
    sa.Column('read_only', sa.Boolean(), nullable=False),
    sa.Column('requires_consent', sa.Boolean(), nullable=False),
    sa.Column('tracking', sa.String(length=16), nullable=False),
    sa.Column('client_reference_arg', sa.String(length=80), nullable=True),
    sa.Column('idempotency_arg', sa.String(length=80), nullable=True),
    sa.Column('consent_summary', sa.Text(), nullable=True),
    sa.Column('call_timeout', sa.Float(), nullable=False),
    sa.Column('description_override', sa.Text(), nullable=True),
    sa.Column('status_tool', sa.String(length=120), nullable=True),
    sa.Column('integration_id', sa.String(length=48), nullable=True),
    sa.PrimaryKeyConstraint('route_id', 'name')
    )
    op.create_table('wf_turns',
    sa.Column('id', sa.String(length=48), nullable=False),
    sa.Column('workflow_id', sa.String(length=48), nullable=False),
    sa.Column('job_id', sa.String(length=48), nullable=True),
    sa.Column('trigger', sa.String(length=12), nullable=True),
    sa.Column('msg_id', sa.String(length=80), nullable=True),
    sa.Column('status', sa.String(length=12), nullable=False),
    sa.Column('started_at', sa.Float(), nullable=False),
    sa.Column('ended_at', sa.Float(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_wf_turns_workflow_id'), 'wf_turns', ['workflow_id'], unique=False)

    op.create_table('wf_workflows',
    sa.Column('id', sa.String(length=48), nullable=False),
    sa.Column('conversation_id', sa.String(length=48), nullable=False),
    sa.Column('client_id', sa.String(length=48), nullable=False),
    sa.Column('route_id', sa.String(length=48), nullable=False),
    sa.Column('case_id', sa.String(length=40), nullable=True),
    sa.Column('external_user_id', sa.String(length=200), nullable=False),
    sa.Column('external_ticket_id', sa.String(length=200), nullable=True),
    sa.Column('ticket_id', sa.String(length=48), nullable=True),
    sa.Column('state', sa.String(length=32), nullable=False),
    sa.Column('revision', sa.Integer(), nullable=False),
    sa.Column('expects', sa.String(length=16), nullable=True),
    sa.Column('current_request_id', sa.String(length=48), nullable=True),
    sa.Column('close_reason', sa.String(length=200), nullable=True),
    sa.Column('attention_reason', sa.String(length=40), nullable=True),
    sa.Column('last_activity_at', sa.Float(), nullable=True),
    sa.Column('created_at', sa.Float(), nullable=False),
    sa.Column('closed_at', sa.Float(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('client_id', 'external_ticket_id', name='uq_workflow_ticket')
    )
    op.create_index(op.f('ix_wf_workflows_case_id'), 'wf_workflows', ['case_id'], unique=False)
    op.create_index(op.f('ix_wf_workflows_conversation_id'), 'wf_workflows', ['conversation_id'], unique=False)
    op.create_index(op.f('ix_wf_workflows_state'), 'wf_workflows', ['state'], unique=False)



def downgrade() -> None:
    op.drop_table('wf_workflows')
    op.drop_table('wf_turns')
    op.drop_table('wf_tools')
    op.drop_table('wf_signing_keys')
    op.drop_table('wf_routes')
    op.drop_table('wf_residences')
    op.drop_table('wf_requests')
    op.drop_table('wf_provider_inbox')
    op.drop_table('wf_operations')
    op.drop_table('wf_messages')
    op.drop_table('wf_mcp_servers')
    op.drop_table('wf_leases')
    op.drop_table('wf_keys')
    op.drop_table('wf_jobs')
    op.drop_table('wf_integrations')
    op.drop_table('wf_events')
    op.drop_table('wf_event_tombstones')
    op.drop_table('wf_conversations')
    op.drop_table('wf_clients')
    op.drop_table('wf_assets')
    op.drop_table('wf_approvals')
    op.drop_table('awp_profiles')
    op.drop_table('awp_ledger')
    op.drop_table('awp_cursors')
    op.drop_table('awp_credential_map')
    op.drop_table('awp_cases')
    op.drop_table('awp_case_sessions')
    op.drop_table('awp_case_items')
    op.drop_table('awp_agent_map')
