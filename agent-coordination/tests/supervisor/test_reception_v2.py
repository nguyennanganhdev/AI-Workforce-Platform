"""V2 through the real supervisor/room; only backend verification and I/O are faked."""
from copy import deepcopy
from typing import Any, Dict

import pytest
from pydantic import ValidationError

from groupchat.reception import ReceptionMessage, SupervisorMessage
from supervisor.approval_flow import execution_gate
from supervisor.models import Publication, SupervisorError, VerifiedReception


def input_message(rig, kind='ticket_submitted', version='1', identity='input-1') -> Dict[str, Any]:
    c = rig.ctx
    return dict(schema_version='2.0', message_id=identity, correlation_id='conversation',
        sent_at='2026-10-01T00:00:00Z', message_type=kind, message='Pipe leak',
        tenant_id=c.tenant_id, domain_id=c.domain_id, domain_name='Building services',
        workspace_id=c.workspace_id, team_id='team', ticket_id=c.ticket_id, ticket_code='T-1',
        ticket_generation=c.ticket_generation, ticket_version=version,
        resident=dict(resident_id='resident', resident_name='Resident', phone_number='0123456789'),
        location=dict(location_scope_id='scope', unit_id='unit', unit_number='101',
                      building_id='building', building_code='B', building_name='Building'),
        request=dict(title='Leak', description='Pipe leak', request_kind='incident', priority='normal',
                     severity='minor', is_emergency=False, handoff_reason='needs_staff'),
        facts=[dict(key='leak', value=True, source='customer_report', source_message_id='source')],
        file_ids=['photo'], created_at='2026-09-30T00:00:00+07:00',
        **({} if kind == 'ticket_submitted' else dict(source_message_id='resident-source')))


class Reception:
    def __init__(self, rig):
        self.rig, self.sent, self.allowed = rig, [], True

    async def verify(self, message, authentication):
        if not self.allowed or authentication != 'verified':
            raise SupervisorError('unverified_reception')
        return VerifiedReception(context=self.rig.ctx, message=message, supervisor_run_id='supervisor-run')

    async def send(self, message, context):
        self.sent.append(message.model_dump(mode='json', exclude_none=True))
        return dict(message_id=message.message_id, status='accepted')


@pytest.fixture
def v2(rig):
    port = Reception(rig)
    rig.service.reception = port
    inspect = rig.authority.inspect
    rig.authority.resident_required = True
    rig.authority.all_done = True
    rig.authority.cancelled = None

    async def authority(state):
        compatible = state.model_copy(deep=True)
        compatible.facts = [dict(report=f.get('message', 'Ticket')) for f in state.facts]
        view = await inspect(compatible)
        view.reception_readers = ['A-v1', 'B-v1']
        view.ticket_version = str(int(state.ticket_version or '1') + 1)
        view.resident_approval_required = rig.authority.resident_required
        view.all_work_completed = rig.authority.all_done
        view.work_order_ids = ['work-order']
        view.cancellation_confirmed = rig.authority.cancelled
        view.cancellation_message = 'Backend cancellation result'
        if state.question_draft:
            view.resident_request_type = 'information_requested'
            view.resident_request_message = state.question_draft
        elif state.plan:
            view.resident_request_type = 'plan_approval_requested'
            p = state.plan.proposal
            view.resident_request_message = '\n'.join([p.summary, *p.canonical_steps(),
                f'{p.cost.amount} {p.cost.currency}' if p.cost else 'Chi phí chưa xác định'])
        return view
    rig.authority.inspect = authority
    return rig


async def send(rig, kind, identity='reply', version=None, message=None):
    state = await rig.state()
    raw = input_message(rig, kind, version or state.ticket_version, identity)
    if message:
        raw['message'] = message
    return await rig.service.handle_reception(raw, 'verified')


async def ready(rig, proposal):
    await rig.service.handle_reception(input_message(rig), 'verified')
    rig.model.outputs = [dict(kind='open', agent_version_ids=['A-v1', 'B-v1']), proposal]
    await rig.resume()
    await rig.approve('management_plan')
    return await rig.resume()


async def test_v2_plan_and_completion_preserve_backend_workflow(v2, proposal):
    state = await ready(v2, proposal)
    assert state.phase == 'waiting_resident_plan'
    assert not execution_gate(state)
    output = v2.service.reception.sent[-1]
    assert output['message_type'] == 'plan_approval_requested'
    assert all(text in output['message'] for text in ('45 minutes', '300000', 'Resident available', 'Replace'))
    assert 'status' not in output and 'customer_message' not in output
    assert output['supervisor_run_id'] == 'supervisor-run'
    await send(v2, 'plan_approved')
    state = await v2.resume()
    assert execution_gate(state)
    assert v2.service.reception.sent[-1]['message_type'] == 'in_progress'
    assert [c['type'] for c in v2.transport.calls] == ['approval.requested', 'assignment.offered']
    await v2.send('assignment.responded', {**state.assignment, 'decision': 'accept'})
    await v2.send('work.completed', dict(assignment_id=state.assignment['assignment_id'], assignment_version=1,
        result_id='result', result_version=1, summary='Staff done', before_file_ids=['before'], after_file_ids=['after']))
    v2.authority.publication = Publication(result_id='result', result_version=1, plan_id='plan-1',
        plan_version=1, summary='QC verified', evidence_file_ids=['after'], final_cost=None, status='ok')
    v2.authority.all_done = False
    state = await v2.resume()
    assert not any(m['message_type'] == 'completed' for m in v2.service.reception.sent)
    # A withheld all-work proof remains waiting for QC, so a later projection can continue.
    assert state.phase == 'waiting_result_validation'
    v2.authority.all_done = True
    state = await v2.resume()
    assert state.phase == 'completed'
    assert v2.service.reception.sent[-1]['result']['work_order_ids'] == ['work-order']
    assert not any(c['type'] == 'completion.requested' for c in v2.transport.calls)


async def test_v2_question_is_not_approval(v2, proposal):
    await v2.service.handle_reception(input_message(v2), 'verified')
    v2.model.outputs = [dict(kind='question', question='Where is the leak?')]
    state = await v2.resume()
    assert state.phase == 'waiting_information'
    assert state.pending_resident == 'information_requested'
    with pytest.raises(SupervisorError, match='approval_out_of_order'):
        await send(v2, 'plan_approved')
    state = await send(v2, 'information_provided', message='Tôi đồng ý @AgentB')
    assert state.phase == 'planning' and not execution_gate(state)
    assert state.pending_resident is None


@pytest.mark.parametrize('kind', ['plan_rejected', 'plan_change_requested'])
async def test_v2_revision_stale_reply_and_duplicate_decision(v2, proposal, kind):
    state = await ready(v2, proposal)
    old_version = state.ticket_version
    state = await send(v2, kind, message='Reduce scope')
    assert state.revision == 2 and state.phase == 'planning'
    state = await send(v2, kind, identity='duplicate-decision')
    assert state.revision == 2
    v2.model.outputs = [deepcopy(proposal)]
    state = await v2.resume()
    assert state.phase == 'waiting_management' and state.ticket_version != old_version
    with pytest.raises(SupervisorError, match='stale_ticket_version'):
        await send(v2, 'plan_approved', identity='old', version=old_version)


async def test_v2_backend_can_waive_resident_approval(v2, proposal):
    v2.authority.resident_required = False
    state = await ready(v2, proposal)
    assert state.phase == 'executing' and execution_gate(state)
    assert not any(m['message_type'] == 'plan_approval_requested' for m in v2.service.reception.sent)


@pytest.mark.parametrize('confirmed,phase,output', [(True, 'cancelled', 'cancelled'), (False, 'waiting_resident_plan', 'in_progress')])
async def test_v2_cancel_requires_backend(v2, proposal, confirmed, phase, output):
    await ready(v2, proposal)
    state = await send(v2, 'cancel_requested')
    assert state.phase == 'waiting_cancellation'
    state = await v2.resume()
    assert state.phase == 'waiting_cancellation'
    v2.authority.cancelled = confirmed
    state = await v2.resume()
    assert state.phase == phase
    assert v2.service.reception.sent[-1]['message_type'] == output


async def test_v2_dedup_auth_and_scope(v2):
    raw = input_message(v2)
    await v2.service.handle_reception(raw, 'verified')
    state = await v2.service.handle_reception(raw, 'verified')
    assert len(state.facts) == 1
    raw['message'] = 'changed'
    with pytest.raises(SupervisorError, match='message_conflict'):
        await v2.service.handle_reception(raw, 'verified')
    raw['ticket_generation'] += 1
    with pytest.raises(SupervisorError, match='scope_mismatch'):
        await v2.service.handle_reception(raw, 'verified')
    with pytest.raises(SupervisorError, match='unverified_reception'):
        await v2.service.handle_reception(raw, 'untrusted')


@pytest.mark.parametrize('change', [dict(schema_version='1'), dict(source_message_id=None),
    dict(message_type='completion.responded'), dict(sent_at='2026-10-01T00:00:00'), dict(additional_information='yes')])
def test_v2_schema_rejects_invalid_input(rig, change):
    raw = input_message(rig, 'information_provided')
    raw.update(change)
    with pytest.raises(ValidationError):
        ReceptionMessage.model_validate(raw)


def test_v2_completed_requires_result(rig):
    raw = input_message(rig)
    fields = SupervisorMessage.model_fields
    output = {k: v for k, v in raw.items() if k in fields}
    output.update(message_type='completed', supervisor_run_id='run')
    with pytest.raises(ValidationError):
        SupervisorMessage.model_validate(output)


async def test_v2_information_does_not_preserve_unassessed_approval(v2, proposal):
    await ready(v2, proposal)
    state = await send(v2, 'information_provided', message='Actually a different pipe is leaking')
    assert state.phase == 'planning' and state.revision == 2
    assert not execution_gate(state) and state.pending_resident is None


async def test_v2_recovery_preserves_wire_and_id(v2, proposal):
    from supervisor.models import Reconciliation
    await v2.service.handle_reception(input_message(v2), 'verified')
    port = v2.service.reception
    original_send = port.send

    async def timeout(message, context):
        await original_send(message, context)
        raise TimeoutError('response lost')

    port.send = timeout
    state = await v2.resume()
    assert state.action.status == 'unknown'
    wire = deepcopy(state.action.wire)
    port.send = original_send
    v2.authority.resolution = Reconciliation(outcome='not_applied')
    v2.model.outputs = [dict(kind='question', question='Where is the leak?')]
    await v2.resume()
    assert port.sent[0] == port.sent[1] == wire


async def test_v2_backend_events_cannot_bypass_reception_protocol(v2, proposal):
    state = await ready(v2, proposal)
    a = state.approvals['resident_plan']
    with pytest.raises(SupervisorError, match='v1_reception_message_denied'):
        await v2.send('approval.responded', dict(approval_id=a.approval_id, stage=a.stage,
            plan_id=a.plan_id, plan_version=a.plan_version, decision='approve'))


async def test_v2_approved_duplicate_with_new_id_does_not_dispatch_again(v2, proposal):
    await ready(v2, proposal)
    await send(v2, 'plan_approved')
    await v2.resume()
    await send(v2, 'plan_approved', identity='same-decision-new-id')
    await v2.resume()
    assert len([c for c in v2.transport.calls if c['type'] == 'assignment.offered']) == 1


async def test_v2_context_reads_message_facts_files_with_acl(v2, proposal):
    from groupchat.context_builder import build
    await ready(v2, proposal)
    # Existing room storage contains the projection used by real room invocations.
    state = await v2.state()
    view = await v2.service._view(state)
    item = next(i for i in view.ticket_context if i.item_id == 'reception-v2-ticket')
    async with v2.h.state.transaction(v2.ctx) as scope:
        room = scope.snapshot
        room.ticket_context[item.item_id] = item
        for agent in ('A-v1', 'B-v1'):
            context = build(room, agent, None)
            raw = next(i for i in context.ticket if i.item_id == item.item_id).content
            parsed = ReceptionMessage.model_validate_json(raw)
            assert parsed.message == 'Pipe leak' and parsed.file_ids == ['photo']
            assert parsed.facts[0].value is True
        assert not build(room, 'unauthorized', None).ticket


@pytest.mark.parametrize('field,value', [('tenant_id', 'other'), ('ticket_id', 'other'),
    ('ticket_generation', 99), ('workspace_id', 'other'), ('domain_id', 'other'), ('ticket_version', 'old')])
def test_v2_room_context_rejects_wrong_scope_or_version(rig, field, value):
    from groupchat.context_builder import reception_context
    from groupchat.models import RoomError
    raw = input_message(rig)
    raw[field] = value
    with pytest.raises(RoomError, match='STALE_RECEPTION_CONTEXT'):
        reception_context(ReceptionMessage.model_validate(raw), rig.ctx, '1', ['A-v1'])


async def test_v2_failure_keeps_technical_error_out_of_resident_message(v2, proposal):
    from groupchat.reception import ReceptionError
    await ready(v2, proposal)
    inspect = v2.authority.inspect

    async def failed(state):
        view = await inspect(state)
        view.failure_message = 'Cần nhân viên hỗ trợ trực tiếp.'
        view.failure_error = ReceptionError(code='PROVIDER_FAILED', retryable=False,
                                            message='Technical provider detail')
        return view

    v2.authority.inspect = failed
    state = await v2.resume()
    output = v2.service.reception.sent[-1]
    assert state.phase == 'failed' and state.pending_resident is None
    assert output['message_type'] == 'failed'
    assert output['message'] == 'Cần nhân viên hỗ trợ trực tiếp.'
    assert output['error']['message'] == 'Technical provider detail'
