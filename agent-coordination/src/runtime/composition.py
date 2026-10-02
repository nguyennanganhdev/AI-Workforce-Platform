"""Concrete service composition with externally allocated producer bindings.

Platform factory supplies these ports using producer contracts. No built-in fake,
in-memory fallback, invented endpoint or direct shared database connection.
"""
from dataclasses import dataclass
from uuid import uuid4

from adapters.agentscope_remote import AgentScopeRemoteAdapter
from adapters.backend.approval_client import ApprovalClient
from adapters.backend.events import PendingDelivery
from adapters.reception.reception_gateway import ReceptionGateway
from adapters.tools.tool_client import ToolClient
from adapters.openbot import OpenbotAdapter
from agents.releases import ReleaseConsumer
from groupchat.room import RoomService
from supervisor.backend_bridge import BackendBridge
from supervisor.planner import Planner
from supervisor.room_bridge import RoomBridge
from supervisor.service import SupervisorService
from runtime.publication import DraftPublisher
from runtime.ingress import DurableIngress
from evaluation.traces import DecisionTraces
from runtime.service import Components,Worker,REQUIRED
from runtime.workflows import Workflows
from runtime.contributions import Contributions
from runtime.reporting import ReportConsumer


@dataclass
class ProductionBindings:
    backend_client: object
    authority: object
    event_verifier: object
    reception_authentication: object
    resolver: object
    release_producer: object
    tool_boundary: object
    supervisor_store: object
    room_store: object
    inbox: object
    records: object
    supervisor_model: object
    remote_budget: object
    delegation: object
    worker_authentication: object
    readiness: object
    close: object
    groupchat_version_id: str
    event_types: dict
    # Optional C13/C14 consumer proposal bindings. Unbound routes fail closed;
    # they never make ordinary ticket readiness falsely report a live contract.
    workflow_authority: object = None
    contribution_producer: object = None
    report_producer: object = None
    report_artifacts: object = None


def build(bindings: ProductionBindings):
    gateway=ReceptionGateway(bindings.backend_client,authentication=bindings.reception_authentication)
    releases=ReleaseConsumer(bindings.release_producer,bindings.records)
    remote=OpenbotAdapter(releases,bindings.records,bindings.tool_boundary,bindings.remote_budget)
    invocation_port=AgentScopeRemoteAdapter(remote)
    room=RoomService(bindings.resolver,invocation_port,bindings.room_store)
    workflows=Workflows(bindings.workflow_authority,bindings.records,
        contributions=Contributions(bindings.contribution_producer,bindings.records) if bindings.contribution_producer else None,
        reports=ReportConsumer(bindings.report_artifacts,bindings.report_producer,bindings.records)
            if bindings.report_producer and bindings.report_artifacts else None,
        remote=invocation_port)
    service=SupervisorService(store=bindings.supervisor_store,authority=bindings.authority,
        verifier=bindings.event_verifier,event_types=bindings.event_types,planner=Planner(bindings.supervisor_model,trace=DecisionTraces(bindings.records)),
        room=RoomBridge(room),backend=BackendBridge(ApprovalClient(bindings.backend_client),gateway,ToolClient(bindings.backend_client)),
        groupchat_version_id=bindings.groupchat_version_id,reception=gateway,publisher=DraftPublisher(bindings.authority),
        groupchat_resolver=bindings.resolver.supervisor_group)

    async def handle(claim):
        payload=claim.payload
        # Producer allocates a durable delegation reference at authenticated accept.
        # References are reverified on consumption; raw transport bearer is not persisted.
        authentication=await bindings.worker_authentication.from_reference(payload['authentication_ref'])
        if payload['kind'] in ('contribution','report'):
            result=await workflows.execute(payload['kind'],payload['wire'],authentication,fence=claim.fence)
            return 5 if result is None else None
        if payload['kind']=='reception':
            resolution=await gateway.resolve(payload['wire'],authentication)
            if resolution.room_command is not None:
                result = await room.execute(resolution.room_command)
                if result.status == 'error':
                    from adapters.backend.errors import AdapterError
                    raise AdapterError('mention_execution_unconfirmed')
                # Mention is a room interaction; it cannot grant plan approval.
                return
            state=await service.handle_reception(payload['wire'],authentication)
        elif payload['kind']=='event':
            delivery=PendingDelivery(**payload['delivery'])
            state=await service.handle_delivery(delivery,authentication,acknowledge=False)
            if delivery.message_type == 'work.completed' and bindings.contribution_producer is not None:
                # C13 supplies real staff/work-order/message references and a stable
                # command. Never derive an employee or synthetic source from chat.
                await workflows.request_after_work(state,delivery,authentication,ingress)
        else:
            raise ValueError('unsupported durable input')
        state = await service.resume(state.context)
        if state.action and state.action.status in ('sending','unknown','accepted'):
            return 5  # durable bounded reconciliation; never blind mutation retry

    worker=Worker(bindings.inbox,handle,owner=str(uuid4()))

    async def readiness():
        status=await bindings.readiness()
        return {kind:status.get(kind) is True for kind in REQUIRED}

    async def close():
        await remote.close()
        await bindings.supervisor_model.close()
        await bindings.close()

    ingress=DurableIngress(gateway,bindings.event_verifier,bindings.backend_client.validator,
        bindings.inbox,bindings.delegation,bindings.event_types,workflows)
    components=Components(ingress,worker,readiness,close)
    # Expose internal services to trusted integration/bootstrap; never HTTP user flows.
    components.supervisor=service
    components.room=room
    components.workflows=workflows
    return components
