"""Boundary fakes only. Actual RoomService and DEV-3 adapters are used below."""
import asyncio
import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest
from adapters.backend.client import BackendClient, HttpResponse
from adapters.backend.approval_client import ApprovalClient
from adapters.backend.events import PendingDelivery, ResolvedEvent
from adapters.backend.messages import fingerprint
from adapters.reception.reception_gateway import ReceptionGateway
from adapters.tools.tool_client import ToolClient
from groupchat.models import ContextItem, ParticipantSpec
from support.harness import Harness
from supervisor.backend_bridge import BackendBridge
from supervisor.models import AuthorityView, CatalogEntry, Reconciliation, SupervisorError
from supervisor.planner import Planner
from supervisor.room_bridge import RoomBridge
from supervisor.service import SupervisorService

NOW = datetime(2026, 9, 30, tzinfo=timezone.utc)
KINDS = ('ticket.submitted', 'resident.message', 'approval.responded', 'assignment.offered',
         'assignment.responded', 'work.completed', 'completion.responded')


class Store:
    def __init__(self):
        self.states, self.acks = {}, set()
        self.lock = asyncio.Lock()
        self.in_commit = False

    async def load(self, context):
        value = self.states.get(context.scope())
        return value.model_copy(deep=True) if value else None

    async def commit(self, state, expected_version, *, delivery_id=None):
        async with self.lock:
            self.in_commit = True
            try:
                old = self.states.get(state.context.scope())
                if (old.version if old else None) != expected_version:
                    return False
                assert state.version == (expected_version + 1 if old else 0)
                # JSON roundtrip simulates checkpoint recovery, not process durability.
                self.states[state.context.scope()] = type(state).model_validate_json(state.model_dump_json())
                if delivery_id:
                    self.acks.add((state.context.tenant_id, delivery_id))
                return True
            finally:
                self.in_commit = False


class Authority:
    def __init__(self, store, context):
        self.store, self.context = store, context
        self.allowed = True
        self.execution = True
        self.publication = None
        self.closed = False
        self.reconciled = False
        self.resolution = Reconciliation(outcome='unknown')
        self.reconcile_calls = 0
        self.expiry = NOW + timedelta(days=1)
        self.ticket_readers = ['A-v1', 'B-v1']
        self.withhold_ticket_context = False

    async def inspect(self, state):
        assert not self.store.in_commit
        if not self.allowed or state.context != self.context:
            raise SupervisorError('forbidden')
        return AuthorityView(context=self.context, state_version=state.version,
            catalog={a: CatalogEntry(participant=ParticipantSpec(agent_version_id=a, role='advisor'),
                                     task_readers=([a] if a == 'C-v1' else ['A-v1', 'B-v1'])) for a in ('A-v1', 'B-v1', 'C-v1')},
            ticket_context=[ContextItem(item_id='trusted-ticket-report',
                content='\n'.join(f.get('report', f.get('text', '')) for f in state.facts),
                reader_agent_version_ids=self.ticket_readers)]
                if state.facts and not self.withhold_ticket_context else [],
            plan_id='plan-1', management_recipient='manager', resident_recipient='resident',
            approval_expires_at=self.expiry, assignment_id=f'assignment-{state.revision}',
            execution_allowed=self.execution, publication=self.publication,
            closure_confirmed=self.closed, revision_reconciled=self.reconciled)

    async def authorize_action(self, state, action):
        assert not self.store.in_commit
        if not self.allowed:
            raise SupervisorError('forbidden')
        if action.operation == 'assignment.offered' and not self.execution:
            raise SupervisorError('execution_not_authorized')

    async def reconcile(self, state, action):
        assert not self.store.in_commit
        self.reconcile_calls += 1
        return self.resolution


class Verifier:
    def __init__(self, context):
        self.context, self.allowed = context, True

    async def resolve(self, event, authentication):
        if not self.allowed or authentication != 'verified-worker':
            raise SupervisorError('event_not_authorized')
        return ResolvedEvent(self.context.model_dump(exclude_none=True))


class Model:
    def __init__(self, store):
        self.store, self.outputs, self.calls = store, [], 0
        self.callback = None

    async def generate(self, prompt):
        assert not self.store.in_commit
        self.calls += 1
        if self.callback:
            await self.callback()
        value = self.outputs.pop(0) if self.outputs else {'kind': 'pause', 'reason': 'test model exhausted'}
        return value if isinstance(value, str) else json.dumps(value)


class Validator:
    def validate(self, kind, value):
        pass  # canonical schema unavailable; DEV-3 local guards still run


class Headers:
    async def headers(self):
        return {'Authorization': 'test-only'}


class Transport:
    def __init__(self, store):
        self.store, self.calls, self.failure = store, [], None

    async def post(self, url, *, headers, body, timeout):
        assert not self.store.in_commit
        self.calls.append(json.loads(body))
        if self.failure:
            raise self.failure
        return HttpResponse(202, json.dumps({'request_id': json.loads(body)['request_id'],
                            'status': 'accepted', 'data': {'operation_id': 'test-op'}}).encode())


class Rig:
    def __init__(self):
        self.h = Harness()
        self.ctx = self.h.ctx
        self.store = Store()
        self.authority, self.verifier = Authority(self.store, self.ctx), Verifier(self.ctx)
        self.model, self.transport = Model(self.store), Transport(self.store)
        client = BackendClient(base_url='https://backend.test',
            routes={k: '/test/' + k for k in ('approval.request', 'completion.request',
                    'assignment.offer', 'reception.question', 'reception.update')},
            transport=self.transport, headers=Headers(), validator=Validator())
        self.room = RoomBridge(self.h.service)
        self.backend = BackendBridge(ApprovalClient(client), ReceptionGateway(client), ToolClient(client))
        self.service = SupervisorService(store=self.store, authority=self.authority, verifier=self.verifier,
            event_types={f'test.{k}': k for k in KINDS}, planner=Planner(self.model),
            room=self.room, backend=self.backend, groupchat_version_id='test-group-v1', clock=lambda: NOW,
            max_steps=64)
        self.serial = 0

    def delivery(self, kind, payload, *, aggregate=None, version=None):
        self.serial += 1
        event = dict(event_id=f'event-{self.serial}', event_type=f'test.{kind}', schema_version='1',
                     tenant_id=self.ctx.tenant_id, aggregate_id=aggregate or kind,
                     aggregate_version=version if version is not None else self.serial,
                     occurred_at=NOW.isoformat(), correlation_id='trace', causation_id='request', payload=deepcopy(payload))
        return PendingDelivery(self.ctx.tenant_id, event['event_id'], fingerprint(event), 'supervisor',
                               kind, self.ctx.model_dump(exclude_none=True), event)

    async def send(self, kind, payload, **kwargs):
        return await self.service.handle_delivery(self.delivery(kind, payload, **kwargs), 'verified-worker')

    async def start(self):
        return await self.send('ticket.submitted', {'report': 'Pipe leak', 'facts': {}, 'attachment_ids': []})

    async def state(self):
        return await self.store.load(self.ctx)

    async def resume(self):
        return await self.service.resume(self.ctx)

    async def approve(self, stage, decision='approve', comment=''):
        s = await self.state()
        a = s.approvals[stage]
        return await self.send('approval.responded', dict(approval_id=a.approval_id, stage=stage,
            plan_id=a.plan_id, plan_version=a.plan_version, decision=decision, comment=comment), aggregate=a.approval_id)


@pytest.fixture
def rig():
    return Rig()


@pytest.fixture
def proposal():
    return {'kind': 'plan', 'plan': {'summary': 'Replace pipe', 'steps': ['Inspect', 'Replace'],
            'performer_role': 'Plumber assigned by backend', 'expected_duration': '45 minutes',
            'conditions': 'Resident available', 'cost': {'amount': 300000, 'currency': 'VND', 'kind': 'estimate'},
            'result_refs': [], 'attachment_ids': []}}
