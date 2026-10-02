from copy import deepcopy
from dataclasses import replace
from datetime import timedelta

import pytest
from supervisor.models import Publication, SupervisorError
from supervisor.approval_flow import execution_gate


async def plan_ready(rig, proposal):
    await rig.start()
    rig.model.outputs = [{'kind': 'open', 'agent_version_ids': ['A-v1', 'B-v1']}, proposal]
    return await rig.resume()


async def execution(rig, proposal):
    await plan_ready(rig, proposal)
    await rig.approve('management_plan')
    await rig.resume()
    await rig.approve('resident_plan')
    return await rig.resume()


async def result_ready(rig, proposal):
    s = await execution(rig, proposal)
    await rig.send('assignment.responded', {**s.assignment, 'decision': 'accept'})
    return await rig.send('work.completed', {
        'assignment_id': s.assignment['assignment_id'], 'assignment_version': 1,
        'result_id': 'result-1', 'result_version': 1, 'summary': 'Done, pending QC',
        'before_file_ids': ['before'], 'after_file_ids': ['after']})


async def completion_ready(rig, proposal):
    await result_ready(rig, proposal)
    rig.authority.publication = Publication(result_id='result-1', result_version=1,
        plan_id='plan-1', plan_version=1, summary='Backend permits this notice',
        evidence_file_ids=['before', 'after'], final_cost={'amount': 300000, 'currency': 'VND'},
        status='backend_verified_status')
    return await rig.resume()


async def test_two_approvals_real_adapters_ack_is_not_approval(rig, proposal):
    s = await plan_ready(rig, proposal)
    assert s.phase == 'waiting_management' and not execution_gate(s)
    assert len(rig.transport.calls) == 1
    assert s.approvals['management_plan'].decision is None
    await rig.approve('management_plan')
    s = await rig.resume()
    assert s.phase == 'waiting_resident_plan' and not execution_gate(s)
    management, resident = rig.transport.calls
    for key in ('summary', 'steps', 'cost', 'plan_id', 'plan_version', 'attachment_ids'):
        assert resident['payload'][key] == management['payload'][key]
    assert resident['payload']['depends_on_approval_id'] == management['payload']['approval_id']
    assert 'Vai trò:' in resident['payload']['steps'][-3]
    await rig.approve('resident_plan')
    s = await rig.resume()
    assert s.phase == 'executing' and execution_gate(s)
    assert [c['type'] for c in rig.transport.calls] == ['approval.requested'] * 2 + ['assignment.offered']
    assert 'employee_id' not in rig.transport.calls[-1]['payload']


@pytest.mark.parametrize('stage', ['management_plan', 'resident_plan'])
@pytest.mark.parametrize('decision', ['reject', 'request_changes'])
async def test_revision_invalidates_old_approval(rig, proposal, stage, decision):
    await plan_ready(rig, proposal)
    if stage == 'resident_plan':
        await rig.approve('management_plan')
        await rig.resume()
    old = (await rig.state()).approvals[stage].model_dump()
    s = await rig.approve(stage, decision, 'Reduce scope')
    assert s.phase == 'planning' and s.revision == 2 and not execution_gate(s)
    revised = deepcopy(proposal)
    revised['plan']['cost']['amount'] = 250000
    rig.model.outputs = [revised]
    s = await rig.resume()
    assert s.phase == 'waiting_management' and s.plan.version == 2
    assert s.plans[0].proposal.cost.amount == 300000
    with pytest.raises(SupervisorError, match='stale_approval|unexpected_approval'):
        await rig.send('approval.responded', {k: v for k, v in {**old, 'decision': 'approve'}.items()
                       if k != 'expires_at'})
    assert not execution_gate(await rig.state())


async def test_missing_rejection_reason_requires_question(rig, proposal):
    await plan_ready(rig, proposal)
    await rig.approve('management_plan', 'reject')
    rig.model.outputs = [{'kind': 'question', 'question': 'Please clarify requested changes'}]
    s = await rig.resume()
    assert s.phase == 'waiting_information'
    request = s.question.request_id
    s = await rig.send('resident.message', {'text': 'approve', 'reply_to_request_id': 'wrong'})
    assert s.phase == 'waiting_information'
    s = await rig.send('resident.message', {'text': 'Use smaller pipe', 'reply_to_request_id': request})
    assert s.phase == 'planning' and not s.needs_clarification


async def test_expiry_and_wrong_stage_do_not_unlock(rig, proposal):
    s = await plan_ready(rig, proposal)
    a = s.approvals['management_plan']
    with pytest.raises(SupervisorError, match='unexpected_approval'):
        await rig.send('approval.responded', dict(approval_id=a.approval_id, plan_id='plan-1',
            plan_version=1, stage='resident_plan', decision='approve'))
    rig.service.clock = lambda: a.expires_at + timedelta(seconds=1)
    with pytest.raises(SupervisorError, match='approval_expired'):
        await rig.approve('management_plan')
    assert not execution_gate(await rig.state())


async def test_assignment_decline_pauses_and_work_does_not_prove_qc(rig, proposal):
    s = await execution(rig, proposal)
    s = await rig.send('assignment.responded', {**s.assignment, 'decision': 'decline', 'reason': 'Unavailable'})
    assert s.phase == 'paused' and s.pause_reason == 'assignment_declined'
    before = len(rig.transport.calls)
    await rig.resume()
    assert len(rig.transport.calls) == before


@pytest.mark.parametrize('decision,phase', [('confirmed', 'waiting_backend_closure'), ('not_satisfied', 'paused')])
async def test_completion_and_backend_closure(rig, proposal, decision, phase):
    s = await completion_ready(rig, proposal)
    assert s.phase == 'waiting_completion'
    assert [c['type'] for c in rig.transport.calls][-2:] == ['resident.update', 'completion.requested']
    c = s.completion
    s = await rig.send('completion.responded', {k: c[k] for k in ('confirmation_id', 'result_id', 'result_version')} |
                       {'decision': decision, 'comment': 'Feedback'})
    assert s.phase == phase
    before = len(rig.transport.calls)
    s = await rig.resume()
    assert s.phase == phase and len(rig.transport.calls) == before
    rig.authority.closed = True
    s = await rig.resume()
    if decision == 'confirmed':
        assert s.phase == 'completed'
    else:
        assert s.phase == 'paused' and s.pause_reason == 'not_satisfied'
        assert s.feedback[-1]['comment'] == 'Feedback'


async def test_missing_qc_can_ask_supplement_not_notify_completion(rig, proposal):
    await result_ready(rig, proposal)
    rig.model.outputs = [{'kind': 'supplement', 'question': 'Is the joint still leaking?'}]
    s = await rig.resume()
    assert s.phase == 'waiting_information'
    assert not any(c['type'] == 'completion.requested' for c in rig.transport.calls)
    s = await rig.send('resident.message', {'text': 'No', 'reply_to_request_id': s.question.request_id})
    # New information invalidates the plan conservatively and requires reapproval.
    assert s.phase == 'planning' and s.revision == 2


async def test_stale_publication_and_stale_result(rig, proposal):
    await result_ready(rig, proposal)
    rig.authority.publication = Publication(result_id='result-1', result_version=99,
        plan_id='plan-1', plan_version=1, summary='QC', evidence_file_ids=[], final_cost=None, status='ok')
    s = await rig.resume()
    assert s.pause_reason == 'stale_publication'
    assert not any(c['type'] == 'completion.requested' for c in rig.transport.calls)


async def test_delivery_dedup_conflict_and_reverify(rig):
    d = rig.delivery('ticket.submitted', {'report': 'Leak', 'facts': {}, 'attachment_ids': []})
    await rig.service.handle_delivery(d, 'verified-worker')
    await rig.service.handle_delivery(d, 'verified-worker')
    assert len((await rig.state()).facts) == 1
    rig.verifier.allowed = False
    with pytest.raises(SupervisorError, match='event_not_authorized'):
        await rig.service.handle_delivery(d, 'verified-worker')
    rig.verifier.allowed = True
    changed = deepcopy(d.event)
    changed['payload']['report'] = 'Different'
    from adapters.backend.messages import fingerprint
    with pytest.raises(SupervisorError, match='event_conflict'):
        await rig.service.handle_delivery(replace(d, event=changed, fingerprint=fingerprint(changed)), 'verified-worker')


@pytest.mark.parametrize('field,value', [('ticket_generation', 99), ('workspace_id', 'other'),
                                       ('domain_id', 'other'), ('binding_id', 'other'), ('tenant_id', 'other')])
async def test_scope_mismatch_rejected(rig, field, value):
    d = rig.delivery('ticket.submitted', {'report': 'Leak', 'facts': {}, 'attachment_ids': []})
    with pytest.raises(SupervisorError, match='scope_mismatch'):
        await rig.service.handle_delivery(replace(d, context={**d.context, field: value}), 'verified-worker')
    assert await rig.state() is None


async def test_mention_never_becomes_supervisor_approval(rig):
    await rig.start()
    with pytest.raises(SupervisorError, match='mention_belongs_to_groupchat'):
        await rig.send('resident.message', {'text': 'approve', 'mentioned_agent_id': 'A'})


async def test_ai_summary_waits_for_backend_publication(rig, proposal):
    await result_ready(rig, proposal)
    rig.model.outputs = [{'kind': 'summarize', 'summary': 'Proposed repair notice',
                          'evidence_file_ids': ['before', 'after']}]
    s = await rig.resume()
    assert s.phase == 'waiting_result_validation'
    assert s.publication_draft['summary'] == 'Proposed repair notice'
    before = len(rig.transport.calls)
    await rig.resume()
    assert len(rig.transport.calls) == before
    rig.authority.publication = Publication(result_id='result-1', result_version=1,
        plan_id='plan-1', plan_version=1, summary='Approved notice', evidence_file_ids=['after'],
        final_cost=None, status='backend_status')
    s = await rig.resume()
    assert s.phase == 'waiting_completion'
    assert rig.transport.calls[-1]['payload']['summary'] == 'Approved notice'


async def test_execution_current_backend_permission_required(rig, proposal):
    await plan_ready(rig, proposal)
    await rig.approve('management_plan')
    await rig.resume()
    await rig.approve('resident_plan')
    rig.authority.execution = False
    s = await rig.resume()
    assert s.pause_reason == 'execution_not_authorized'
    assert not any(c['type'] == 'assignment.offered' for c in rig.transport.calls)


async def test_result_revision_must_match_completion(rig, proposal):
    s = await completion_ready(rig, proposal)
    c = s.completion
    with pytest.raises(SupervisorError, match='stale_completion'):
        await rig.send('completion.responded', dict(confirmation_id=c['confirmation_id'],
            result_id=c['result_id'], result_version=2, decision='confirmed'))
    assert (await rig.state()).phase == 'waiting_completion'


async def test_conflicting_approval_never_overwrites(rig, proposal):
    await plan_ready(rig, proposal)
    await rig.approve('management_plan')
    with pytest.raises(SupervisorError, match='decision_conflict'):
        await rig.approve('management_plan', 'reject', 'Conflict')
    assert (await rig.state()).approvals['management_plan'].decision == 'approve'


async def test_extra_cost_requires_new_approval_before_publication(rig, proposal):
    await result_ready(rig, proposal)
    rig.authority.publication = Publication(result_id='result-1', result_version=1,
        plan_id='plan-1', plan_version=1, summary='More costly repair', evidence_file_ids=[],
        final_cost={'amount': 400000, 'currency': 'VND'}, status='backend_status')
    revised = deepcopy(proposal)
    revised['plan']['cost']['amount'] = 400000
    rig.authority.reconciled = True
    rig.model.outputs = [revised]
    s = await rig.resume()
    assert s.phase == 'waiting_management' and s.plan.version == 2
    assert s.plan.proposal.cost.amount == 400000
    assert not any(c['type'] == 'completion.requested' for c in rig.transport.calls)


async def test_information_after_approval_invalidates_future_dispatch(rig, proposal):
    await plan_ready(rig, proposal)
    await rig.approve('management_plan')
    await rig.resume()
    await rig.approve('resident_plan')
    s = await rig.send('resident.message', {'text': 'The leak is actually in another room'})
    assert s.phase == 'planning' and s.revision == 2 and not execution_gate(s)
    assert not any(c['type'] == 'assignment.offered' for c in rig.transport.calls)


async def test_replan_live_assignment_requires_reconciliation(rig, proposal):
    await result_ready(rig, proposal)
    rig.model.outputs = [proposal]
    s = await rig.resume()
    assert s.phase == 'waiting_result_validation'
    assert s.pause_reason == 'dependency_unavailable:live_assignment_reconciliation'
    assert len(s.plans) == 1
    rig.authority.reconciled = True
    rig.model.outputs = [proposal]
    s = await rig.resume()
    assert s.phase == 'waiting_management' and s.revision == 2
    assert s.assignment['plan_version'] == 1  # history, not a false cancellation


async def test_revised_assignment_preserves_prior_work(rig, proposal):
    await result_ready(rig, proposal)
    rig.authority.reconciled = True
    rig.model.outputs = [proposal]
    await rig.resume()
    await rig.approve('management_plan')
    await rig.resume()
    await rig.approve('resident_plan')
    s = await rig.resume()
    assert s.phase == 'executing' and s.assignment['plan_version'] == 2
    assert s.result is None and s.result_history[-1]['result_id'] == 'result-1'
    assert s.assignment_history[-1]['plan_version'] == 1
    await rig.send('assignment.responded', {**s.assignment, 'decision': 'accept'})
    s = await rig.send('work.completed', dict(assignment_id=s.assignment['assignment_id'],
        assignment_version=s.assignment['assignment_version'], result_id='new-result', result_version=1,
        summary='Newly approved work', before_file_ids=[], after_file_ids=[]))
    assert s.result['result_id'] == 'new-result' and len(s.result_history) == 1


async def test_revised_plan_cannot_reuse_old_assignment_identity(rig, proposal):
    await result_ready(rig, proposal)
    rig.authority.reconciled = True
    rig.model.outputs = [proposal]
    await rig.resume()
    await rig.approve('management_plan')
    await rig.resume()
    await rig.approve('resident_plan')
    inspect = rig.authority.inspect
    async def stale_identity(state):
        view = await inspect(state)
        view.assignment_id = 'assignment-1'
        return view
    rig.authority.inspect = stale_identity
    s = await rig.resume()
    assert s.pause_reason == 'stale_assignment_identity'
    assert len([c for c in rig.transport.calls if c['type'] == 'assignment.offered']) == 1
