"""V2 transitions over the existing supervisor state and durable action journal."""
from datetime import datetime
from typing import Optional
from uuid import NAMESPACE_URL, uuid5

from adapters.backend.messages import fingerprint
from groupchat.reception import OutputType, ReceptionError, ReceptionResult, SupervisorMessage
from .approval_flow import approval_response, invalidate
from .models import Action, AuthorityView, SupervisorState, VerifiedReception, require


def emit(state: SupervisorState, kind: OutputType, message: str, now: datetime,
         result: Optional[ReceptionResult] = None,
         error: Optional[ReceptionError] = None) -> None:
    require(state.action is None, 'action_pending')
    source = state.reception
    require(source is not None and state.supervisor_run_id is not None, 'v2_context_required')
    key = str(uuid5(NAMESPACE_URL, repr((state.context.scope(), len(state.journal), kind))))
    wire = SupervisorMessage(
        schema_version='2.0', message_id=key, correlation_id=source.correlation_id,
        sent_at=now.isoformat(), message_type=kind, message=message,
        tenant_id=source.tenant_id, workspace_id=source.workspace_id, team_id=source.team_id,
        ticket_id=source.ticket_id, ticket_code=source.ticket_code,
        ticket_generation=source.ticket_generation, ticket_version=state.ticket_version,
        supervisor_run_id=state.supervisor_run_id, result=result, error=error,
    )
    state.action = Action(action_id=key, channel='reception', operation=kind,
                          wire=wire.model_dump(mode='json', exclude_none=True),
                          plan_version=state.revision)


def receive(state: SupervisorState, verified: VerifiedReception, now: datetime) -> bool:
    message = verified.message
    require(verified.context == state.context, 'scope_mismatch')
    require((message.tenant_id, message.ticket_id, message.ticket_generation,
             message.workspace_id, message.domain_id) ==
            (state.context.tenant_id, state.context.ticket_id, state.context.ticket_generation,
             state.context.workspace_id, state.context.domain_id), 'scope_mismatch')
    digest = fingerprint(message.model_dump(mode='json'))
    prior = state.reception_events.get(message.message_id)
    if prior is not None:
        require(prior == digest, 'message_conflict')
        return False
    require(state.action is None, 'action_pending')
    kind = message.message_type
    if state.reception:
        require(state.supervisor_run_id == verified.supervisor_run_id and
                state.reception.team_id == message.team_id and
                state.reception.ticket_code == message.ticket_code, 'scope_mismatch')
        require(message.ticket_version == state.ticket_version, 'stale_ticket_version')
    if kind == 'ticket_submitted':
        require(state.reception is None and not state.facts, 'ticket_already_started')
    else:
        require(state.reception is not None, 'ticket_required')
        require(state.phase not in ('completed', 'cancelled', 'failed'), 'ticket_processing_finished')
        decision = {'plan_approved': 'approve', 'plan_rejected': 'reject',
                    'plan_change_requested': 'request_changes'}.get(kind)
        if decision:
            prior_decision = state.resident_decisions.get(message.ticket_version)
            if prior_decision is not None:
                require(prior_decision == kind, 'decision_conflict')
                state.reception_events[message.message_id] = digest
                return False
            require(state.pending_resident == 'plan_approval_requested' and
                    state.pending_ticket_version == message.ticket_version, 'approval_out_of_order')
            approval = state.approvals.get('resident_plan')
            require(approval is not None, 'unexpected_approval')
            approval_response(state, dict(approval_id=approval.approval_id, stage=approval.stage,
                plan_id=approval.plan_id, plan_version=approval.plan_version,
                decision=decision, comment=message.message), now)
            state.resident_decisions[message.ticket_version] = kind
            state.pending_resident = state.pending_ticket_version = None
        elif kind == 'information_provided':
            # Unsolicited information stays data; it never approves a pending plan.
            if state.pending_resident == 'information_requested':
                require(state.question is not None and
                        state.pending_ticket_version == message.ticket_version, 'stale_question')
                state.phase = state.question.return_phase
                state.question = None
                state.pending_resident = state.pending_ticket_version = None
                state.needs_clarification = False
                if state.plan:
                    invalidate(state, 'new_resident_information')
            elif state.plan and state.phase in (
                'waiting_management', 'waiting_resident_plan', 'execution_ready',
                'executing', 'waiting_result_validation',
            ):
                invalidate(state, 'new_unassessed_resident_information')
        elif kind == 'cancel_requested':
            if state.phase != 'waiting_cancellation':
                state.cancellation_return_phase = state.phase
                state.phase = 'waiting_cancellation'
    state.reception = message.model_copy(deep=True)
    state.ticket_version = message.ticket_version
    state.supervisor_run_id = verified.supervisor_run_id
    state.facts.append(message.model_dump(mode='json'))
    state.reception_events[message.message_id] = digest
    if kind == 'ticket_submitted':
        emit(state, 'accepted', 'Yêu cầu đã được tiếp nhận.', now)
    return True


def pending(state: SupervisorState, view: AuthorityView, kind: OutputType) -> str:
    require(state.pending_resident is None, 'resident_request_pending')
    require(view.ticket_version is not None and view.resident_request_message is not None
            and view.resident_request_type == kind,
            'dependency_unavailable:resident_request')
    require(view.ticket_version != state.ticket_version, 'new_ticket_version_required')
    state.ticket_version = view.ticket_version
    state.pending_resident = kind
    state.pending_ticket_version = view.ticket_version
    return view.resident_request_message
