"""Private CustomerService receipts remain subject to the Leader evidence gate."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from agentscope.app._shared_context import SharedContextService
from agentscope.app.middleware import LeaderEvidenceMiddleware
from agentscope.event import ReplyEndEvent, TextBlockDeltaEvent, TextBlockEndEvent, TextBlockStartEvent
from agentscope.message import TextBlock, ToolCallBlock, ToolResultBlock, ToolResultState
from agentscope.state import AgentState


def setup_receipt(*, team_id=None):
    storage = SimpleNamespace(
        get_session=AsyncMock(return_value=SimpleNamespace(team_id=team_id)),
        get_team_shared_context=AsyncMock(return_value=None),
    )
    shared = SharedContextService(storage, None)
    middleware = LeaderEvidenceMiddleware(storage, shared, 'alice', 'leader', 'session', max_nudges=0, max_repairs=0)
    state = AgentState(session_id='session')
    state.reply_id = 'reply-current'
    receipt = dict(user_id='alice', agent_id='leader', session_id='session', operation='create',
        cases=[dict(id='case-private', code='CASE-123456', sync_status='applied', service_status='received')])
    result = ToolResultBlock(id='call', name='CustomerService', output='server result', state=ToolResultState.SUCCESS,
        metadata={'customer_service_receipt': receipt})
    state.append_context('Leader', [ToolCallBlock(id='call', name='CustomerService', input='{"operation":"create"}'), result])
    agent = SimpleNamespace(name='Leader', state=state)
    return middleware, agent, result, receipt


@pytest.mark.asyncio
async def test_current_server_receipt_supports_private_case_and_keeps_unknown_claims_blocked():
    middleware, agent, _, _ = setup_receipt()
    assert not (await middleware._claim_validation('Yêu cầu CASE-123456 đã được ghi nhận.', agent)).unsupported
    assert (await middleware._claim_validation('Yêu cầu CASE-999999 đã được ghi nhận.', agent)).unsupported
    assert 'state:ticket_closed' in (await middleware._claim_validation('Ticket is closed.', agent)).unsupported
    assert 'state:resident_accepted' in (await middleware._claim_validation('Resident has accepted.', agent)).unsupported


@pytest.mark.parametrize('alter', ['user', 'agent', 'session', 'old-reply', 'failed', 'other-tool', 'missing-metadata', 'wrong-operation'])
@pytest.mark.asyncio
async def test_untrusted_or_stale_receipt_cannot_back_a_claim(alter):
    middleware, agent, result, receipt = setup_receipt()
    if alter in {'user', 'agent', 'session'}:
        receipt[alter + '_id'] = 'someone-else'
    elif alter == 'old-reply':
        agent.state.reply_id = 'next-reply'
    elif alter == 'failed':
        result.state = ToolResultState.ERROR
    elif alter == 'other-tool':
        result.name = 'mcp__untrusted'
    elif alter == 'missing-metadata':
        result.metadata.clear()
    elif alter == 'wrong-operation':
        receipt['operation'] = 'context'
    assert (await middleware._claim_validation('Yêu cầu CASE-123456 đã được ghi nhận.', agent)).unsupported


@pytest.mark.asyncio
async def test_scoped_receipts_combine_with_shared_context_without_changing_team_status():
    middleware, agent, _, _ = setup_receipt(team_id='team')
    assert not (await middleware._claim_validation('Yêu cầu CASE-123456 đã được ghi nhận.', agent)).unsupported
    assert (await middleware._claim_validation('Yêu cầu CASE-999999 đã được ghi nhận.', agent)).unsupported


@pytest.mark.asyncio
async def test_latest_progress_receipt_replaces_previous_case_facts():
    middleware, agent, _, receipt = setup_receipt()
    updated = {**receipt, 'operation': 'progress', 'cases': [{**receipt['cases'][0], 'code': 'CASE-654321'}]}
    agent.state.append_context('Leader', [ToolCallBlock(id='refresh', name='CustomerService', input='{"operation":"progress"}'),
        ToolResultBlock(id='refresh', name='CustomerService', output='', state=ToolResultState.SUCCESS,
            metadata={'customer_service_receipt': updated})])
    assert (await middleware._claim_validation('CASE-123456', agent)).unsupported
    assert not (await middleware._claim_validation('CASE-654321', agent)).unsupported


@pytest.mark.asyncio
async def test_reply_preserves_verified_request_instead_of_team_incomplete_fallback():
    middleware, agent, _, _ = setup_receipt()
    text = 'Yêu cầu CASE-123456 đã được ghi nhận.'
    agent.state.append_context('Leader', [TextBlock(text=text)])
    async def reply(**kwargs):
        yield TextBlockStartEvent(reply_id=agent.state.reply_id, block_id='text')
        yield TextBlockDeltaEvent(reply_id=agent.state.reply_id, block_id='text', delta=text)
        yield TextBlockEndEvent(reply_id=agent.state.reply_id, block_id='text', text=text)
        yield ReplyEndEvent(session_id='session', reply_id=agent.state.reply_id)
    output = [event async for event in middleware.on_reply(agent, {}, reply)]
    assert ''.join(event.delta for event in output if isinstance(event, TextBlockDeltaEvent)) == text


def test_model_text_and_call_arguments_never_become_a_receipt():
    middleware, agent, result, receipt = setup_receipt()
    result.metadata.clear()
    result.output = json.dumps({'customer_service_receipt': receipt})
    assert middleware._customer_sources(agent) == []
