"""Exercise DEV-3 ingress/adapter objects with Supervisor and DEV-2 RoomService.

Only verifier, inbox, authority, HTTP transport, schema validator and model are
faked at the missing production boundaries.
"""
from adapters.backend.events import EventIngress
from supervisor.models import SupervisorError


class Inbox:
    def __init__(self):
        self.pending = {}

    async def enqueue_once(self, delivery):
        key = (delivery.tenant_id, delivery.event_id)
        previous = self.pending.get(key)
        if previous:
            if previous.fingerprint != delivery.fingerprint:
                raise ValueError('conflict')
            return False
        self.pending[key] = delivery
        return True


class Validator:
    def __init__(self):
        self.kinds = []

    def validate(self, kind, value):
        self.kinds.append(kind)


async def test_real_ingress_to_supervisor_to_room_and_approval_adapter(rig, proposal):
    inbox, validator = Inbox(), Validator()
    ingress = EventIngress(verifier=rig.verifier, inbox=inbox, validator=validator,
                           event_types=rig.service.event_types)
    ticket = rig.delivery('ticket.submitted', {
        'report': 'Pipe leak', 'facts': {'location': 'kitchen'}, 'attachment_ids': [],
    })
    queued = await ingress.receive(ticket.event, authentication='verified-worker')
    assert queued.queued and 'event' in validator.kinds
    delivered = inbox.pending[(ticket.tenant_id, ticket.event_id)]
    await rig.service.handle_delivery(delivered, 'verified-worker')
    rig.model.outputs = [{'kind': 'open', 'agent_version_ids': ['A-v1', 'B-v1']}, proposal]
    state = await rig.resume()
    assert state.room and state.phase == 'waiting_management'
    assert rig.transport.calls[0]['type'] == 'approval.requested'
    assert rig.transport.calls[0]['payload']['plan_version'] == 1
    approval = state.approvals['management_plan']
    response = rig.delivery('approval.responded', {
        'approval_id': approval.approval_id,
        'stage': approval.stage,
        'plan_id': approval.plan_id,
        'plan_version': approval.plan_version,
        'decision': 'approve',
        'comment': '',
    }, aggregate=approval.approval_id)
    receipt = await ingress.receive(response.event, authentication='verified-worker')
    assert receipt.queued
    await rig.service.handle_delivery(inbox.pending[(response.tenant_id, response.event_id)],
                                      'verified-worker')
    state = await rig.resume()
    assert state.phase == 'waiting_resident_plan'
    assert [r['payload']['stage'] for r in rig.transport.calls] == [
        'management_plan', 'resident_plan',
    ]
    assert rig.transport.calls[-1]['payload']['depends_on_approval_id'] == approval.approval_id


async def test_mention_routes_to_dev2_not_supervisor(rig):
    inbox = Inbox()
    ingress = EventIngress(verifier=rig.verifier, inbox=inbox, validator=Validator(),
                           event_types=rig.service.event_types)
    mention = rig.delivery('resident.message', {'text': 'Ask agent', 'mentioned_agent_id': 'A'})
    received = await ingress.receive(mention.event, authentication='verified-worker')
    assert received.queued
    delivery = inbox.pending[(mention.tenant_id, mention.event_id)]
    assert delivery.target == 'groupchat'
    try:
        await rig.service.handle_delivery(delivery, 'verified-worker')
    except SupervisorError as exc:
        assert exc.code == 'wrong_target'
    else:
        raise AssertionError('Supervisor consumed a DEV-2 mention')
