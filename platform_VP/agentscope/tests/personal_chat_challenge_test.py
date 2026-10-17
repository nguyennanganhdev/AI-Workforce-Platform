"""Scripted team debate: actual TeamSay/state transitions, no model provider."""
from unittest.mock import AsyncMock

from tests.personal_chat_test import personal_app, make_group
from agentscope.app._shared_context import SharedContextService
from agentscope.app._team_turn import start_team_turn
from agentscope.app._tool import TeamSay


def test_group_challenge_requires_revised_report(personal_app):
    app, client, storage = personal_app
    app.state.chat_service._run_impl = AsyncMock()
    group = make_group(client, 'Offline challenge audit')
    members = {m['agent_id']: m for m in group['members']}
    service = SharedContextService(storage, app.state.message_bus)

    async def exercise():
        event = await service.append_event(user_id='alice', team_id=group['teamId'],
                                           kind='customer_message', content='Prepare a proposed maintenance plan')
        await start_team_turn(app.state.message_bus, group['teamId'],
                              reply_owner_session_id=group['sessionId'], reply_owner_agent_id=group['agentId'],
                              customer_session_id=group['sessionId'], mode='leader', task_id=event.task_id,
                              storage=storage, user_id='alice')

        async def send(agent, **payload):
            tool = TeamSay(storage=storage, message_bus=app.state.message_bus,
                           workspace_manager=app.state.workspace_manager, user_id='alice',
                           agent_id=agent, session_id=members[agent]['session_id'],
                           shared_context_service=service, role='leader' if agent == 'alice-a' else 'worker',
                           management_group=True)
            chunk = await tool(**payload)
            assert chunk.state.value != 'error', chunk

        await send('alice-a', kind='handoff', to='alice-b@alice-b', content='Propose a maintenance plan', done_when='Include resident access requirements')
        await send('alice-b', kind='result', report_type='analysis', content='Proposal: inspect the shared equipment.')
        await send('alice-a', kind='review', to='alice-b@alice-b', decision='challenge', content='Missing access requirements: revise the proposal to include them.')
        record = await storage.get_team_shared_context('alice', group['teamId'])
        assert record.state.tasks[event.task_id].collaboration[members['alice-b']['session_id']].status != 'completed'
        await send('alice-b', kind='result', report_type='analysis', content='Revised proposal: confirm access with BQL, then inspect the shared equipment; staffing is unverified.')
        await send('alice-a', kind='review', to='alice-b@alice-b', decision='accept', content='Accept revised proposal as advice, pending operational confirmation.')
        record = await storage.get_team_shared_context('alice', group['teamId'])
        assert record.state.tasks[event.task_id].collaboration[members['alice-b']['session_id']].status == 'completed'
        assert sum(e.kind == 'result' for e in record.state.events) == 2

    client.portal.call(exercise)
