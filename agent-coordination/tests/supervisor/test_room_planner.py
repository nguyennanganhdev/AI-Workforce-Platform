from copy import deepcopy

import pytest
from groupchat.models import AgentOutput, TurnPolicy
from support.harness import mention
from supervisor.models import DECISION, SupervisorError
from supervisor.planner import validate_decision
from supervisor.service import prepare_decision

OPEN = {'kind': 'open', 'agent_version_ids': ['A-v1', 'B-v1']}
TASKS = {'kind': 'tasks', 'tasks': [
    {'task_id': 'analysis-v1', 'description': 'Inspect leak', 'assignee_agent_version_id': 'A-v1', 'dependencies': []},
    {'task_id': 'review-v1', 'description': 'Review', 'assignee_agent_version_id': 'B-v1', 'dependencies': ['analysis-v1']}]}
RUN = {'kind': 'run', 'task_id': 'analysis-v1', 'agent_version_id': 'A-v1', 'instruction': 'Analyze leak'}


async def opened(rig):
    await rig.start()
    rig.model.outputs = [OPEN, TASKS, RUN, {'kind': 'pause', 'reason': 'inspect terminal'}]
    return await rig.resume()


async def test_real_room_tasks_terminal_followups_no_reenqueue(rig):
    s = await opened(rig)
    assert len(rig.h.agents.calls) == 1
    terminal = list(s.terminal_results.values())[0]
    assert terminal.turn_status == 'success' and terminal.source_run_id
    assert terminal.task_id == 'analysis-v1' and terminal.turn_id
    assert s.room.turns_used == 1
    assert s.room.tasks[0].status == 'in_progress'  # agent success is not work completion
    assert s.room.tasks[0].reader_agent_version_ids == ['A-v1', 'B-v1']
    assert rig.h.agents.calls[0].ticket_context[0].content == 'Pipe leak'
    room = rig.h.state.records[rig.ctx.scope()].snapshot
    follow = [m for m in room.transcript if m.content == 'B hãy kiểm tra thêm.']
    assert len(follow) == 1
    assert any(m.message.message_id == follow[0].message_id for m in room.mailbox)
    commands = [a.wire for a in s.journal if a.channel == 'room']
    assert all(c['contract_version'] == '1' and c['payload']['version'] == 2 for c in commands)
    run = next(c for c in commands if c['payload']['operation'] == 'run_turn')
    assert run['payload']['expected_room_version'] == 4


@pytest.mark.parametrize('outputs,reason', [
    (['not json', '{}'], 'invalid_model_output'),
    ([{'kind': 'open', 'agent_version_ids': ['unpublished']}]*2, 'invalid_model_output'),
    ([{'kind': 'plan', 'plan': {'approved': True}}]*2, 'invalid_model_output'),
])
async def test_bounded_invalid_model(rig, outputs, reason):
    await rig.start()
    rig.model.outputs = deepcopy(outputs)
    s = await rig.resume()
    assert s.pause_reason == reason and rig.model.calls == 2
    assert not rig.h.agents.calls and not rig.transport.calls


@pytest.mark.parametrize('change,code', [
    ('cycle', 'dependency_cycle'), ('unknown', 'missing_dependency'), ('acl', 'task_acl_denied'),
])
async def test_task_graph_and_acl(rig, change, code):
    await rig.start()
    _, response = await rig.h.open()
    s = await rig.state()
    s.room = response.data
    view = await rig.authority.inspect(s)
    tasks = deepcopy(TASKS)
    if change == 'cycle':
        tasks['tasks'][0]['dependencies'] = ['review-v1']
    elif change == 'unknown':
        tasks['tasks'][0]['dependencies'] = ['missing']
    else:
        view.catalog['A-v1'].task_readers = ['B-v1']
    with pytest.raises(SupervisorError, match=code):
        validate_decision(DECISION.validate_python(tasks), s, view)


async def test_dependency_not_complete_and_unproven_result(rig):
    s = await opened(rig)
    s.phase = 'planning'
    view = await rig.authority.inspect(s)
    d = DECISION.validate_python({**RUN, 'task_id': 'review-v1', 'agent_version_id': 'B-v1'})
    with pytest.raises(SupervisorError, match='dependency_incomplete'):
        validate_decision(d, s, view)
    d = DECISION.validate_python({'kind': 'complete_task', 'task_id': 'analysis-v1',
                                  'result_refs': ['invented'], 'assessment': 'Looks done'})
    with pytest.raises(SupervisorError, match='unproven_result'):
        validate_decision(d, s, view)
    terminal = next(iter(s.terminal_results.values()))
    ref = next(m.message_id for m in terminal.messages if m.task_id == 'analysis-v1' and m.content.startswith('A-v1:'))
    d.result_refs = [ref]
    prepare_decision(s, d, view, rig.service.clock())
    receipt = await rig.room.dispatch(s.action)
    assert receipt['data']['tasks'][0]['status'] == 'completed'


async def test_admission_real_resolver_denies_unpublished_and_pins_add(rig):
    await rig.start()
    async def extend_trusted_context():
        rig.authority.ticket_readers = ['A-v1', 'B-v1', 'C-v1']
    async def after_open():
        if (await rig.state()).room:
            await extend_trusted_context()
    rig.model.callback = after_open
    rig.model.outputs = [OPEN, {'kind': 'add_agent', 'agent_version_id': 'C-v1'},
                         {'kind': 'pause', 'reason': 'stop'}]
    s = await rig.resume()
    assert [p.agent_version_id for p in s.room.participants] == ['A-v1', 'B-v1', 'C-v1']
    snapshot = rig.h.state.records[rig.ctx.scope()].snapshot
    assert 'C-v1' in snapshot.ticket_context['trusted-ticket-report'].reader_agent_version_ids
    assert all('latest' not in p.agent_version_id for p in s.room.participants)
    from groupchat.models import PutTask, RunTurn, TaskItem
    c_task = await rig.h.service.execute(rig.h.command(PutTask(
        room_id=s.room.room_id, expected_room_version=s.room.room_version,
        task=TaskItem(task_id='c-analysis', description='Verify leak',
                      assignee_agent_version_id='C-v1', reader_agent_version_ids=['C-v1']))))
    c_turn = await rig.h.service.execute(rig.h.command(RunTurn(
        room_id=s.room.room_id, expected_room_version=c_task.data.room_version,
        turn_id='c-first-turn', task_id='c-analysis', correlation_id='c-correlation',
        speaker_agent_version_id='C-v1', instruction='Analyze the ticket')))
    assert c_turn.status == 'completed'
    assert rig.h.agents.calls[-1].ticket_context[0].content == 'Pipe leak'


async def test_stale_model_after_concurrent_event_has_no_side_effect(rig, proposal):
    await rig.start()
    rig.model.outputs = [proposal]
    async def change():
        await rig.send('resident.message', {'text': 'new information'})
    rig.model.callback = change
    with pytest.raises(SupervisorError, match='state_conflict'):
        await rig.resume()
    assert not rig.transport.calls and not (await rig.state()).plans


async def test_max_turns_and_mentions_use_real_dev2_budget(rig):
    rig.service.turn_policy = TurnPolicy(max_turns=1)
    s = await opened(rig)
    assert s.room.turns_remaining == 0
    # User mention remains handled by DEV-2 and doesn't reopen Supervisor execution.
    result = await rig.h.service.execute(mention(rig.h, s.room, agent='B'))
    assert result.status == 'completed' and result.data.turns_used == 1
    assert not s.approvals
    s.phase = 'planning'
    s.room = result.data
    with pytest.raises(SupervisorError, match='max_turns'):
        validate_decision(DECISION.validate_python(RUN), s, await rig.authority.inspect(s))


@pytest.mark.parametrize('mode,status', [('failure', 'failure'), ('timeout', 'timeout'), ('unknown', 'outcome_unknown')])
async def test_agent_terminal_errors_and_unknown_slot(rig, mode, status):
    if mode == 'failure':
        rig.h.agents.fail = True
    else:
        rig.service.turn_policy = TurnPolicy(timeout_seconds=0.001)
        rig.h.agents.delay = 0.1
        rig.h.agents.cancel_confirmed = mode != 'unknown'
    s = await opened(rig)
    assert s.room.turns_used == 1 and s.room.turn_status == status
    assert len(rig.h.agents.calls) == 1
    if mode == 'unknown':
        assert s.action.status == 'unknown'
        await rig.resume()
        assert len(rig.h.agents.calls) == 1 and rig.authority.reconcile_calls == 1
    else:
        assert s.phase == 'paused' and s.action is None


async def test_room_bridge_pages_history(rig):
    _, opened_result = await rig.h.open()
    from groupchat.models import Message
    # Seed only the boundary storage fake; query/pagination is real RoomService.
    snapshot = rig.h.state.records[rig.ctx.scope()].snapshot
    now = rig.service.clock()
    snapshot.transcript = [Message(message_id=f'm-{n}', sequence=n, content=str(n),
                                  sender=rig.ctx.principal_id, timestamp=now)
                           for n in range(1, 503)]
    snapshot.transcript_cursor = 502
    read = await rig.room.read(rig.ctx, opened_result.data.room_id)
    assert len(read.messages) == 502 and read.messages[-1].sequence == read.transcript_cursor


async def test_accepted_requires_original_operation_terminal_not_idle(rig):
    import asyncio
    from supervisor.service import action
    from groupchat.models import RunTurn
    s = await opened(rig)
    s.phase = 'planning'
    s.pause_reason = None
    s.room = await rig.room.read(rig.ctx, s.room.room_id)
    action(s, 'room', 'run_turn', RunTurn(room_id=s.room.room_id, expected_room_version=s.room.room_version,
        turn_id='second-turn', task_id='analysis-v1', correlation_id='c',
        speaker_agent_version_id='A-v1', instruction='Analyze more'))
    saved_action = s.action.model_copy(deep=True)
    rig.h.agents.delay = 0.08
    running = asyncio.create_task(rig.room.dispatch(saved_action))
    await asyncio.sleep(0.01)
    accepted = await rig.room.dispatch(saved_action)
    assert accepted['status'] == 'accepted'
    await running
    saved_action.status = 'accepted'
    terminal = await rig.room.terminal(saved_action)
    assert terminal['data']['turn_status'] == 'success'
    assert len(rig.h.agents.calls) == 2


async def test_mention_between_put_and_run_is_stale_not_replayed(rig):
    from supervisor.service import action
    from groupchat.models import RunTurn
    s = await opened(rig)
    s.phase, s.pause_reason = 'planning', None
    s.room = await rig.room.read(rig.ctx, s.room.room_id)
    action(s, 'room', 'run_turn', RunTurn(room_id=s.room.room_id, expected_room_version=s.room.room_version,
        turn_id='stale-turn', task_id='analysis-v1', correlation_id='c',
        speaker_agent_version_id='A-v1', instruction='Continue'))
    old_wire = deepcopy(s.action.wire)
    await rig.service._save(s, s.version)
    await rig.h.service.execute(mention(rig.h, s.room, agent='B'))
    s = await rig.resume()
    assert s.phase == 'paused' and s.pause_reason == 'STALE_VERSION'
    assert s.journal[-1].wire == old_wire
    assert len(rig.h.agents.calls) == 2  # original analysis + user mention only


async def test_model_timeout_and_automatic_step_limit(rig):
    import asyncio
    await rig.start()
    async def slow():
        await asyncio.sleep(0.1)
    rig.model.callback = slow
    rig.service.planner.timeout = 0.001
    s = await rig.resume()
    assert s.pause_reason == 'model_timeout' and not rig.h.agents.calls


async def test_revoked_member_denied_by_real_room(rig):
    await rig.start()
    rig.model.outputs = [OPEN]
    rig.h.resolver.revoked = True
    s = await rig.resume()
    assert s.pause_reason == 'FORBIDDEN' and not rig.h.agents.calls


@pytest.mark.parametrize('cost', [{'amount': -1, 'currency': 'VND'}, {'amount': float('inf'), 'currency': 'VND'},
                                 {'amount': 1, 'currency': 'invalid'}])
async def test_invalid_cost_is_not_sent(rig, proposal, cost):
    await rig.start()
    proposal['plan']['cost'] = cost
    rig.model.outputs = [proposal, proposal]
    s = await rig.resume()
    assert s.pause_reason == 'invalid_model_output' and not rig.transport.calls


async def test_old_task_version_and_wrong_assignee_denied(rig):
    s = await opened(rig)
    s.phase = 'planning'
    wrong = DECISION.validate_python({**RUN, 'agent_version_id': 'B-v1'})
    with pytest.raises(SupervisorError, match='task_acl_denied'):
        validate_decision(wrong, s, await rig.authority.inspect(s))
    s.revision = 2
    with pytest.raises(SupervisorError, match='stale_task'):
        validate_decision(DECISION.validate_python(RUN), s, await rig.authority.inspect(s))


async def test_consecutive_limit_does_not_change_policy(rig):
    s = await opened(rig)
    s.phase = 'planning'
    s.room.consecutive_turns = s.turn_policy.max_consecutive_turns
    with pytest.raises(SupervisorError, match='consecutive_limit'):
        validate_decision(DECISION.validate_python(RUN), s, await rig.authority.inspect(s))
    assert not any(a.operation == 'update_turn_policy' for a in s.journal)


async def test_automatic_step_limit_separate_from_agent_budget(rig):
    await rig.start()
    rig.service.max_steps = 1
    rig.model.outputs = [OPEN]
    s = await rig.resume()
    assert s.action and s.action.operation == 'open_room'
    s = await rig.resume()
    assert s.phase == 'paused' and s.pause_reason == 'automatic_step_limit'
    assert s.room.turns_used == 0


async def test_mention_during_model_invalidates_proposal(rig, proposal):
    s = await opened(rig)
    s.phase, s.pause_reason = 'planning', None
    await rig.service._save(s, s.version)
    async def mention_during_model():
        current = await rig.room.read(rig.ctx, s.room.room_id)
        await rig.h.service.execute(mention(rig.h, current, agent='B'))
    rig.model.callback = mention_during_model
    rig.model.outputs = [proposal]
    s = await rig.resume()
    assert s.pause_reason == 'STALE_VERSION' and not rig.transport.calls


async def test_real_room_cancel_terminal_is_not_task_completion(rig):
    import asyncio
    from groupchat.models import CancelTurn, RunTurn
    from supervisor.service import action
    s = await opened(rig)
    s.phase, s.pause_reason = 'planning', None
    s.room = await rig.room.read(rig.ctx, s.room.room_id)
    action(s, 'room', 'run_turn', RunTurn(room_id=s.room.room_id, expected_room_version=s.room.room_version,
        turn_id='cancel-turn', task_id='analysis-v1', correlation_id='c',
        speaker_agent_version_id='A-v1', instruction='Analyze more'))
    rig.h.agents.delay = 1
    running = asyncio.create_task(rig.room.dispatch(s.action))
    await asyncio.sleep(0.01)
    active = await rig.room.read(rig.ctx, s.room.room_id)
    canceled = await rig.h.service.execute(rig.h.command(CancelTurn(room_id=active.room_id,
        expected_room_version=active.room_version, target_operation_id=active.operation_id)))
    assert canceled.data.turn_status == 'cancel'
    await running
    s.action.status = 'accepted'
    receipt = await rig.room.terminal(s.action)
    assert receipt['data']['turn_status'] == 'cancel'
    await rig.service._save(s, s.version)
    s = await rig.service._record(s, receipt)
    assert s.pause_reason == 'turn_cancel' and s.room.tasks[0].status == 'in_progress'


async def test_new_verified_ticket_facts_reach_next_agent_turn(rig):
    await rig.start()
    rig.model.outputs = [OPEN, {'kind': 'question', 'question': 'Where is the leak?'}]
    waiting = await rig.resume()
    assert waiting.phase == 'waiting_information'
    await rig.send('resident.message', {
        'text': 'Under the kitchen sink',
        'reply_to_request_id': waiting.question.request_id,
    })
    rig.model.outputs = [TASKS, RUN, {'kind': 'pause', 'reason': 'review'}]
    state = await rig.resume()
    assert state.room.tasks[0].status == 'in_progress'
    assert 'Under the kitchen sink' in rig.h.agents.calls[-1].ticket_context[0].content
    assert any(a.operation == 'put_context' for a in state.journal)


async def test_ticket_context_acl_fail_closed_before_open(rig):
    await rig.start()
    rig.model.outputs = [
        {'kind': 'open', 'agent_version_ids': ['A-v1']},
        {'kind': 'open', 'agent_version_ids': ['A-v1']},
    ]
    state = await rig.resume()
    assert state.pause_reason == 'ticket_context_acl_denied'
    assert state.room is None
    assert rig.h.state.records.get(rig.ctx.scope()) is None


async def test_removed_context_pauses_until_dev2_can_revoke_it(rig):
    await rig.start()
    rig.model.outputs = [OPEN, {'kind': 'pause', 'reason': 'stop'}]
    state = await rig.resume()
    assert state.context_fingerprints
    state.phase, state.pause_reason = 'planning', None
    await rig.service._save(state, state.version)
    rig.authority.withhold_ticket_context = True
    state = await rig.resume()
    assert state.pause_reason == 'dependency_unavailable:context_revocation'
    assert state.room is not None


async def test_stale_task_creation_releases_unapplied_drafts_for_replanning(rig):
    from supervisor.service import prepare_next
    await rig.start()
    _, opened_result = await rig.h.open()
    s = await rig.state()
    s.room = opened_result.data
    view = await rig.authority.inspect(s)
    from groupchat.models import PutContext
    item = view.ticket_context[0]
    with_context = await rig.h.service.execute(rig.h.command(PutContext(
        room_id=s.room.room_id, expected_room_version=s.room.room_version, item=item)))
    s.room = with_context.data
    s.context_fingerprints[item.item_id] = item.model_dump_json()
    prepare_decision(s, DECISION.validate_python(TASKS), view, rig.service.clock())
    prepare_next(s, view, rig.service.clock())
    await rig.service._save(s, s.version)
    await rig.h.service.execute(mention(rig.h, s.room, agent='B'))
    s = await rig.resume()
    assert s.pause_reason == 'STALE_VERSION' and not s.tasks and not s.task_drafts
    failed_key = s.journal[-1].action_id
    rig.model.outputs = [TASKS, {'kind': 'pause', 'reason': 'done'}]
    s = await rig.resume()
    assert len(s.room.tasks) == 2
    attempt = next(a for a in s.journal if a.previous_action_id == failed_key)
    assert attempt.action_id != failed_key
