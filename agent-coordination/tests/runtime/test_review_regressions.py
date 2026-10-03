"""Regression coverage for step-budget scheduling and room/release wiring."""
import json
from types import SimpleNamespace

import httpx
import pytest

from agents.releases import ReleaseConsumer
from adapters.openbot import OpenbotAdapter
from adapters.agentscope_remote import AgentScopeRemoteAdapter
from groupchat.models import ParticipantSpec
from groupchat.room import RoomService
from persistence.budget import Budget
from persistence.sqlite import DevelopmentStore
from runtime.composition import build
from runtime.reporting import ReportArtifacts
from support.fakes import FakeResolver
from support.harness import Harness, mention
from tests.runtime.test_releases_remote import release
from tests.runtime.test_workflows import bindings, REPO
from tests.supervisor.conftest import Rig, NOW


async def test_worker_resumes_unsent_approval_after_step_limit_and_restart(tmp_path):
    now = [100.]
    b, store, _, _ = await bindings(tmp_path, now=now)
    rig = Rig()
    delivery = rig.delivery('ticket.submitted', {
        'report': 'Pipe leak', 'facts': {}, 'attachment_ids': []})
    await rig.service.handle_delivery(delivery, 'verified-worker', acknowledge=False)
    rig.model.outputs = [{'kind': 'open', 'agent_version_ids': ['A-v1', 'B-v1']},
                         {'kind': 'pause', 'reason': 'fixture setup'}]
    state = await rig.resume()
    state.phase, state.pause_reason, state.resume_phase = 'planning', None, None
    state.version = 0
    await store.commit(state, None)
    # Keep the real Supervisor, room, planner and backend adapters; use durable
    # file checkpoints/inbox and the explicit producer doubles from the rig.
    store.in_commit = False
    rig.authority.store = rig.model.store = rig.transport.store = store
    b.authority, b.event_verifier = rig.authority, rig.verifier
    b.groupchat_version_id = 'test-group-v1'
    b.event_types = rig.service.event_types
    b.contribution_producer = None
    async def authentication(reference):
        assert reference == 'durable-reference'
        return 'verified-worker'
    b.worker_authentication = SimpleNamespace(from_reference=authentication)
    await store.accept('ticket', {
        'kind': 'event', 'authentication_ref': 'durable-reference',
        'delivery': delivery.__dict__})
    rig.model.outputs = [{'kind': 'plan', 'plan': {
        'summary': 'Replace pipe', 'steps': ['Inspect', 'Replace'],
        'performer_role': 'Plumber', 'expected_duration': '45 minutes',
        'conditions': 'Resident available', 'cost': None,
        'result_refs': [], 'attachment_ids': []}}]

    def composed():
        c = build(b)
        c.supervisor.room = rig.room
        c.supervisor.backend = rig.backend
        c.supervisor.planner = rig.service.planner
        c.supervisor.clock = lambda: NOW
        c.supervisor.max_steps = 1  # force every prepare/dispatch budget boundary
        return c

    c = composed()
    assert await c.worker.once()
    state = await store.load(rig.ctx)
    assert state.action is not None, (state.phase, state.pause_reason, state.feedback,
                                     state.plan_draft, state.context_drafts, rig.model.outputs)
    assert state.action.status == 'pending' and state.action.operation == 'approval.requested'
    assert rig.transport.calls == []
    with store.connection() as db:
        assert db.execute('SELECT status FROM inbox').fetchone() == ('pending',)
        assert db.execute('SELECT count(*) FROM acknowledgements').fetchone() == (0,)
    now[0] += 6
    await c.close()
    c = composed()  # recreate worker/composition while the input is deferred
    c.supervisor.max_steps = 16
    assert await c.worker.once()
    assert rig.transport.calls[0]['type'] == 'approval.requested'
    assert len(rig.transport.calls) == 1
    await c.close()


class RoomBindingResolver(FakeResolver):
    def __init__(self):
        super().__init__()
        self.binding_rooms = {}

    async def resolve(self, context, groupchat_version_id, spec, room):
        participant = await super().resolve(context, groupchat_version_id, spec, room)
        self.binding_rooms[participant.binding_id] = room.room_id
        return participant

    async def invocation_run(self, context, room, participant, operation_id):
        assert self.binding_rooms[participant.binding_id] == room.room_id
        return await super().invocation_run(context, room, participant, operation_id)


async def test_resolved_bindings_use_persisted_room_id_and_replay(harness):
    resolver = RoomBindingResolver()
    harness.service = RoomService(resolver, harness.agents, harness.state)
    command, opened = await harness.open()
    assert set(resolver.binding_rooms.values()) == {opened.data.room_id}
    assert (await harness.service.execute(command)).data.room_id == opened.data.room_id
    result = await harness.service.execute(harness.turn(opened.data))
    assert result.status == 'completed'
    assert harness.agents.calls[0].room_id == opened.data.room_id


@pytest.mark.parametrize('mode', ['turn', 'mention'])
@pytest.mark.parametrize('matching_pin', [True, False])
async def test_room_report_uses_verified_artifacts_through_release_sdk_and_remote(tmp_path, monkeypatch, mode, matching_pin):
    monkeypatch.setenv('TEST_BOT_KEY', 'test-secret')
    artifacts = ReportArtifacts(REPO, development=True)
    h = Harness()
    store = DevelopmentStore(tmp_path/'report.sqlite')
    requests = []
    class Releases:
        async def resolve_released_session(self, invocation):
            return release(invocation) | {
                'groupchat_version_id': 'test-group-v1', 'capabilities': ['report'],
                'report_artifact_hash': artifacts.artifact_hash if matching_pin else 'different-release-artifact',
                'tool_descriptors': []}
    def respond(request):
        wire = json.loads(request.content)
        requests.append(wire)
        common = {'threadId': wire['threadId'], 'runId': wire['runId']}
        events = [{'type': 'RUN_STARTED', **common},
            {'type': 'TEXT_MESSAGE_START', 'messageId': 'reply', 'role': 'assistant'},
            {'type': 'TEXT_MESSAGE_CONTENT', 'messageId': 'reply',
             'delta': '{"content":"Report result","follow_up_requests":[]}'},
            {'type': 'TEXT_MESSAGE_END', 'messageId': 'reply'},
            {'type': 'RUN_FINISHED', **common}]
        return httpx.Response(200, headers={'content-type': 'text/event-stream'},
            content=''.join('data: '+json.dumps(e)+'\n\n' for e in events).encode())
    remote = OpenbotAdapter(ReleaseConsumer(Releases(), store), store, None,
        Budget(store, scope='report', token_limit=20000),
        client=httpx.AsyncClient(transport=httpx.MockTransport(respond)))
    sdk = AgentScopeRemoteAdapter(remote)
    h.service = RoomService(h.resolver, sdk, store, report_artifacts=artifacts)
    opening, _ = await h.open()
    # Use a separate scope so the published participant list is immutable.
    from support.fakes import make_context
    h.ctx = make_context('REPORT')
    opening = h.command(opening.payload.model_copy(update={
        'participants': [ParticipantSpec(agent_version_id='B-v1', role='report')]}))
    opened = await h.service.execute(opening)
    command = h.turn(opened.data, speaker='B-v1') if mode == 'turn' else mention(h, opened.data)
    result = await h.service.execute(command)
    if not matching_pin:
        assert result.status == 'error' and result.error.code == 'DEPENDENCY_UNAVAILABLE'
        assert requests == []  # mismatched release must fail before remote dispatch
        await remote.close()
        return
    assert result.status == 'completed', result
    assert result.data.messages[-1].content == 'Report result'
    assert len(requests) == 1
    # A replay after rebuilding the room service must use the saved receipt.
    h.service = RoomService(h.resolver, sdk, store, report_artifacts=artifacts)
    assert (await h.service.execute(command)).data == result.data
    assert len(requests) == 1
    await remote.close()


async def test_room_report_without_verified_artifacts_never_provisions_child_run(harness):
    opening, _ = await harness.open()
    from support.fakes import make_context
    harness.ctx = make_context('REPORT')
    opened = await harness.service.execute(harness.command(opening.payload.model_copy(update={
        'participants': [ParticipantSpec(agent_version_id='B-v1', role='report')]})))
    result = await harness.service.execute(harness.turn(opened.data, speaker='B-v1'))
    assert result.status == 'error' and result.error.code == 'DEPENDENCY_UNAVAILABLE'
    assert harness.resolver.calls == [] and harness.agents.calls == []
