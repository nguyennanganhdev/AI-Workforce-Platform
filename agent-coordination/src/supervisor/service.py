"""Fenced orchestration: prepare/commit, external I/O, reconcile/commit.

All mutations occur on detached checkpoint copies. Store commits are the only
transaction boundary; model, verifier, authority and adapter calls stay outside.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid5, NAMESPACE_URL

from adapters.backend.errors import AdapterError
from adapters.backend.events import EventVerifier, PendingDelivery, INBOUND_TYPES
from adapters.backend.messages import fingerprint, validate_context, validate_event, validate_payload
from groupchat.models import (AddParticipant, Command, Context, ContextItem, MessageInput, OpenRoom,
                              PutContext, PutTask, RunTurn, TaskItem, TurnPolicy, RoomData)
from .approval_flow import apply_message, execution_gate, propose, invalidate
from .backend_bridge import BackendBridge
from .models import (Action, Approval, AuthorityView, Question, SupervisorError,
                     SupervisorState, TaskMetadata, require)
from .planner import Planner, validate_decision
from .ports import Authority, ReceptionPort, StateStore
from .reception_flow import emit, pending, receive
from groupchat.reception import ReceptionMessage, ReceptionResult, SupervisorMessage
from groupchat.context_builder import reception_context
from .room_bridge import RoomBridge
from .turn_policy import runnable


def stable_id(state: SupervisorState, label: str) -> str:
    return str(uuid5(NAMESPACE_URL, repr((state.context.scope(), state.context.domain_id,
                                        state.context.workspace_id, state.revision, label))))


def pause(state: SupervisorState, reason: str) -> None:
    if state.phase != "paused":
        state.resume_phase = state.phase
    state.phase, state.pause_reason = "paused", reason


def plan_fields(state):
    require(state.plan is not None, "plan_required")
    return {"plan_id": state.plan.plan_id, "plan_version": state.plan.version}


def room_args(state):
    require(state.room is not None, "room_required")
    return {"room_id": state.room.room_id, "expected_room_version": state.room.room_version}


def trusted_ticket_context(view, members, *, new_member=None):
    """Validate the authority's exact ACL before writing DEV-2 ContextItem."""
    require(bool(view.ticket_context), "dependency_unavailable:ticket_context")
    require(len({item.item_id for item in view.ticket_context}) == len(view.ticket_context),
            "duplicate_context_item")
    selected = set(members)
    for item in view.ticket_context:
        require(item.task_id is None and set(item.reader_agent_version_ids) <= selected,
                "ticket_context_acl_denied")
    if new_member is not None:
        require(any(new_member in item.reader_agent_version_ids for item in view.ticket_context),
                "ticket_context_acl_denied")
    return [item.model_copy(deep=True) for item in view.ticket_context]


def action(state, channel, operation, payload):
    require(state.action is None, "action_pending")
    key = stable_id(state, f"action:{len(state.journal)}:{operation}")
    common = dict(request_id=key, trace_id=key, idempotency_key=key,
                  context=state.context.model_dump(mode="json", exclude_none=True))
    wire = (Command(**common, payload=payload).model_dump(mode="json") if channel == "room"
            else dict(contract_version="1", type=operation, **common, payload=payload))
    state.action = Action(action_id=key, channel=channel, operation=operation,
                          wire=wire, plan_version=state.revision,
                          previous_action_id=(state.journal[-1].action_id
                                              if state.journal and state.journal[-1].status == "failed" else None))


def request_approval(state, view, stage, now):
    require(state.plan is not None, "plan_required")
    recipient = view.management_recipient if stage == "management_plan" else view.resident_recipient
    require(recipient is not None and view.approval_expires_at is not None,
            "dependency_unavailable:approval_routing")
    require(view.approval_expires_at.tzinfo is not None and view.approval_expires_at > now,
            "approval_expired")
    approval_id = stable_id(state, stage)
    p = state.plan.proposal
    payload = dict(approval_id=approval_id, stage=stage, **plan_fields(state),
                   recipient_user_id=recipient,
                   delivery_channel="management_ui" if stage == "management_plan" else "reception",
                   summary=p.summary, steps=p.canonical_steps(),
                   cost=p.cost.model_dump() if p.cost else None,
                   attachment_ids=p.attachment_ids, expires_at=view.approval_expires_at.isoformat())
    if stage == "resident_plan":
        management = state.approvals["management_plan"]
        require(management.decision == "approve" and management.plan_version == state.revision,
                "management_required")
        payload["depends_on_approval_id"] = management.approval_id
    state.approvals[stage] = Approval(approval_id=approval_id, stage=stage,
                                    **plan_fields(state), expires_at=view.approval_expires_at)
    if state.reception is not None and stage == "resident_plan":
        emit(state, "plan_approval_requested", pending(state, view, "plan_approval_requested"), now)
    else:
        action(state, "backend", "approval.requested", payload)
    state.phase = "waiting_management" if stage == "management_plan" else "waiting_resident_plan"


def prepare_decision(state, decision, view, now):
    """Pure, validated intent construction; no model/network/storage calls."""
    validate_decision(decision, state, view)
    kind = decision.kind
    if kind == "open":
        context = trusted_ticket_context(view, decision.agent_version_ids)
        action(state, "room", "open_room", OpenRoom(
            groupchat_version_id=state.groupchat_version_id, turn_policy=state.turn_policy,
            participants=[view.catalog[a].participant for a in decision.agent_version_ids],
            # Ticket details must flow through trusted ACL context, not broadcast.
            initial_message=MessageInput(content="Phòng phân tích ticket đã được xác thực."),
            ticket_context=context))
    elif kind == "add_agent":
        members = {p.agent_version_id for p in state.room.participants}
        trusted_ticket_context(
            view, members | {decision.agent_version_id}, new_member=decision.agent_version_id
        )
        state.context_join_pending = decision.agent_version_id
        action(state, "room", "add_participant", AddParticipant(
            **room_args(state), participant=view.catalog[decision.agent_version_id].participant))
    elif kind == "tasks":
        state.task_drafts = [t.model_copy(deep=True) for t in decision.tasks]
        for t in decision.tasks:
            state.tasks[t.task_id] = TaskMetadata(plan_version=state.revision, dependencies=t.dependencies)
    elif kind == "run":
        task = runnable(state, decision.task_id, decision.agent_version_id).model_copy(deep=True)
        task.status = "in_progress"
        state.run_after_put = decision
        action(state, "room", "put_task", PutTask(**room_args(state), task=task))
    elif kind == "complete_task":
        task = next((t for t in state.room.tasks if t.task_id == decision.task_id), None)
        require(task is not None, "task_missing")
        task = task.model_copy(deep=True)
        task.status, task.result_refs = "completed", decision.result_refs
        action(state, "room", "put_task", PutTask(**room_args(state), task=task))
    elif kind in ("question", "supplement"):
        question_id = stable_id(state, f"question:{len(state.journal)}")
        if state.reception is not None:
            require(state.pending_resident is None, "resident_request_pending")
            state.question_draft = decision.question
            return
        action(state, "backend", "resident.question", {
            "question_id": question_id, "question": decision.question})
        state.question = Question(request_id=state.action.action_id,
                                  question_id=question_id, return_phase=state.phase)
        state.phase = "waiting_information"
    elif kind == "summarize":
        state.publication_draft = dict(summary=decision.summary, evidence_file_ids=decision.evidence_file_ids,
                                       result_id=state.result["result_id"], result_version=state.result["result_version"],
                                       **plan_fields(state))
        state.pause_reason = "waiting_backend_publication"
    elif kind == "plan":
        require(view.plan_id is not None, "dependency_unavailable:plan_identity")
        if state.assignment:
            require(view.revision_reconciled, "dependency_unavailable:live_assignment_reconciliation")
        if state.phase == "waiting_result_validation":
            invalidate(state, "supplemental_scope_or_cost")
        if state.reception is not None:
            require(view.ticket_version is not None and view.ticket_version != state.ticket_version,
                    "new_ticket_version_required")
            state.ticket_version = view.ticket_version
        propose(state, decision.plan, view.plan_id)
        request_approval(state, view, "management_plan", now)
    elif kind == "pause":
        pause(state, "planner:" + decision.reason)


def prepare_next(state, view, now):
    """Prepare deterministic continuations. Return True when a transition occurred."""
    if state.reception is not None and view.failure_message is not None:
        state.pending_resident = state.pending_ticket_version = None
        emit(state, "failed", view.failure_message, now, view.failure_result, view.failure_error)
        return True
    if state.question_draft is not None and state.phase != "waiting_cancellation":
        if view.resident_request_type != "information_requested" or view.resident_request_message is None:
            return False
        require(view.resident_request_message == state.question_draft, "question_not_stored_by_backend")
        canonical = pending(state, view, "information_requested")
        emit(state, "information_requested", canonical, now)
        state.question = Question(request_id=state.action.action_id,
                                  question_id=state.action.action_id, return_phase=state.phase)
        state.question_draft = None
        state.phase = "waiting_information"
        return True
    if state.reception is not None and state.phase == "waiting_cancellation":
        if view.cancellation_confirmed is None:
            return False
        require(view.cancellation_message is not None, "dependency_unavailable:cancellation_message")
        if view.cancellation_confirmed:
            state.pending_resident = state.pending_ticket_version = None
            emit(state, "cancelled", view.cancellation_message, now)
        else:
            require(state.cancellation_return_phase is not None, "cancellation_state_missing")
            state.phase = state.cancellation_return_phase
            state.cancellation_return_phase = None
            emit(state, "in_progress", view.cancellation_message, now)
        return True
    if state.room:
        members = {p.agent_version_id for p in state.room.participants}
        require(not state.context_fingerprints or bool(view.ticket_context),
                "dependency_unavailable:context_revocation")
        current = trusted_ticket_context(view, members, new_member=state.context_join_pending)
        require(set(state.context_fingerprints) <= {item.item_id for item in current},
                "dependency_unavailable:context_revocation")
        state.context_drafts = [item for item in current
                                if state.context_fingerprints.get(item.item_id) != item.model_dump_json()]
        if not state.context_drafts:
            state.context_join_pending = None
    if state.run_after_put:
        d = state.run_after_put
        runnable(state, d.task_id, d.agent_version_id)
        require(d.agent_version_id in view.catalog, "agent_not_allowed")
        action(state, "room", "run_turn", RunTurn(
            **room_args(state), turn_id=stable_id(state, f"turn:{len(state.journal)}"),
            task_id=d.task_id, correlation_id=stable_id(state, f"correlation:{len(state.journal)}"),
            speaker_agent_version_id=d.agent_version_id, instruction=d.instruction))
        state.run_after_put = None
        return True
    if state.context_drafts:
        item = state.context_drafts.pop(0)
        members = {p.agent_version_id for p in state.room.participants}
        require(set(item.reader_agent_version_ids) <= members, "ticket_context_acl_denied")
        action(state, "room", "put_context", PutContext(**room_args(state), item=item))
        return True
    if state.task_drafts:
        t = state.task_drafts.pop(0)
        entry = view.catalog.get(t.assignee_agent_version_id)
        require(entry is not None and t.assignee_agent_version_id in entry.task_readers,
                "task_acl_denied")
        action(state, "room", "put_task", PutTask(**room_args(state), task=TaskItem(
            task_id=t.task_id, description=t.description, assignee_agent_version_id=t.assignee_agent_version_id,
            reader_agent_version_ids=entry.task_readers)))
        return True
    if state.phase == "waiting_management" and state.approvals["management_plan"].decision == "approve":
        if state.reception is not None:
            require(view.resident_approval_required is not None,
                    "dependency_unavailable:resident_approval_policy")
            state.resident_approval_required = view.resident_approval_required
            if not state.resident_approval_required:
                state.phase = "execution_ready"
                return True
        request_approval(state, view, "resident_plan", now)
        return True
    if state.phase == "execution_ready":
        require(execution_gate(state) and view.execution_allowed, "execution_not_authorized")
        require(view.assignment_id is not None, "dependency_unavailable:assignment_identity")
        if state.assignment:
            require(view.revision_reconciled, "dependency_unavailable:live_assignment_reconciliation")
            require(view.assignment_id != state.assignment["assignment_id"] or
                    view.assignment_version > state.assignment["assignment_version"], "stale_assignment_identity")
        if state.assignment:
            state.assignment_history.append(dict(state.assignment))
        if state.result:
            state.result_history.append(dict(state.result))
        state.result, state.completion, state.publication_draft = None, None, None
        state.assignment = dict(assignment_id=view.assignment_id, assignment_version=view.assignment_version,
                                **plan_fields(state))
        action(state, "backend", "assignment.offered", dict(state.assignment))
        state.phase = "executing"
        return True
    if (state.reception is not None and state.phase == "executing" and state.journal
            and state.journal[-1].operation == "assignment.offered"):
        emit(state, "in_progress", "Công việc đang được triển khai theo phương án đã duyệt.", now)
        return True
    if state.phase == "waiting_result_validation" and view.publication:
        pub = view.publication
        require(state.result is not None and state.plan is not None and
                (pub.result_id, pub.result_version) == (state.result["result_id"], state.result["result_version"]) and
                (pub.plan_id, pub.plan_version) == (state.plan.plan_id, state.revision), "stale_publication")
        agreed_cost = state.plan.proposal.cost
        if agreed_cost and pub.final_cost and (
            pub.final_cost.currency != agreed_cost.currency or pub.final_cost.amount > agreed_cost.amount
        ):
            # Withhold publication and let AI propose a revised scope/cost, which
            # still requires live-work reconciliation and two fresh approvals.
            state.revision_reason = "supplemental_approval_required"
            evidence = {"backend_publication_requires_revision": pub.model_dump(mode="json")}
            if evidence not in state.feedback:
                state.feedback.append(evidence)
            return False
        if state.reception is not None:
            room_tasks = {task.task_id: task for task in state.room.tasks} if state.room else {}
            require(view.all_work_completed and all(
                task_id in room_tasks and room_tasks[task_id].status == "completed"
                for task_id, metadata in state.tasks.items() if metadata.plan_version == state.revision
            ), "dependency_unavailable:work_completion")
            emit(state, "completed", pub.summary, now, ReceptionResult(
                outcome="work_completed", summary=pub.summary,
                work_order_ids=view.work_order_ids, evidence_ids=pub.evidence_file_ids))
            return True
        require(view.resident_recipient is not None, "dependency_unavailable:completion_recipient")
        # Trusted projection must withhold publication if supplemental cost/scope approval is needed.
        state.completion = dict(confirmation_id=stable_id(state, f"completion:{pub.result_id}:{pub.result_version}"),
                                result_id=pub.result_id, result_version=pub.result_version,
                                **plan_fields(state), recipient_user_id=view.resident_recipient,
                                summary=pub.summary, evidence_file_ids=pub.evidence_file_ids,
                                final_cost=({"amount": pub.final_cost.amount, "currency": pub.final_cost.currency}
                                            if pub.final_cost else None))
        action(state, "backend", "resident.update", dict(summary=pub.summary,
               attachment_ids=pub.evidence_file_ids, status=pub.status))
        # completion request follows successful update receipt, without a second wrapper.
        return True
    if state.phase == "waiting_backend_closure" and view.closure_confirmed:
        state.phase = "completed"
        return True
    return False


class SupervisorService:
    def __init__(self, *, store: StateStore, authority: Authority, verifier: EventVerifier,
                 event_types: Dict[str, str], planner: Planner, room: RoomBridge,
                 backend: BackendBridge, groupchat_version_id: str,
                 turn_policy: Optional[TurnPolicy] = None,
                 max_steps: int = 16, clock=None,
                 reception: Optional[ReceptionPort] = None):
        require(bool(groupchat_version_id) and type(max_steps) is int and max_steps > 0, "invalid_config")
        require(all(v in INBOUND_TYPES for v in event_types.values()), "unsupported_event_mapping")
        self.reception = reception
        self.store, self.authority, self.verifier = store, authority, verifier
        self.event_types = dict(event_types)
        self.planner, self.room, self.backend = planner, room, backend
        self.groupchat_version_id, self.turn_policy = groupchat_version_id, turn_policy or TurnPolicy()
        self.max_steps, self.clock = max_steps, clock or (lambda: datetime.now(timezone.utc))

    async def _save(self, state, expected, delivery_id=None):
        state.version = 0 if expected is None else expected + 1
        require(await self.store.commit(state, expected, delivery_id=delivery_id), "state_conflict")
        return state

    async def handle_delivery(self, delivery: PendingDelivery, trusted_context: object):
        """trusted_context is transport/worker authentication, NOT a user JSON Context."""
        require(delivery.target == "supervisor", "wrong_target")
        validate_event(delivery.event)
        validate_payload(delivery.message_type, delivery.event["payload"])
        require(self.event_types.get(delivery.event["event_type"]) == delivery.message_type,
                "event_mapping_mismatch")
        require(delivery.fingerprint == fingerprint(delivery.event) and
                delivery.event_id == delivery.event["event_id"] and
                delivery.tenant_id == delivery.event["tenant_id"], "event_identity_mismatch")
        resolved = await self.verifier.resolve(delivery.event, trusted_context)
        validate_context(dict(resolved.context))
        context = Context.model_validate(resolved.context)
        require(context == Context.model_validate(delivery.context) and
                context.tenant_id == delivery.tenant_id, "scope_mismatch")
        old = await self.store.load(context)
        state = old.model_copy(deep=True) if old else SupervisorState(
            context=context, groupchat_version_id=self.groupchat_version_id, turn_policy=self.turn_policy)
        require(state.context == context, "scope_mismatch")
        if not old:
            require(delivery.message_type == "ticket.submitted", "ticket_required")
        prior = state.events.get(delivery.event_id)
        if prior is not None:
            require(prior == delivery.fingerprint, "event_conflict")
            return await self._save(state, old.version, delivery.event_id)
        # Worker retries after action reconciliation; do not lose events while an
        # effect is in flight, or let a reply rewrite the dispatch fence.
        require(state.action is None, "action_pending")
        aggregate = delivery.event["aggregate_id"]
        version = delivery.event["aggregate_version"]
        require(version > state.aggregate_versions.get(aggregate, -1), "stale_event")
        apply_message(state, delivery.message_type, delivery.event["payload"], self.clock())
        state.events[delivery.event_id] = delivery.fingerprint
        state.aggregate_versions[aggregate] = version
        return await self._save(state, old.version if old else None, delivery.event_id)

    async def handle_reception(self, raw: Dict[str, Any], authentication: object) -> SupervisorState:
        require(self.reception is not None, "dependency_unavailable:reception_v2")
        message = ReceptionMessage.model_validate(raw)
        verified = await self.reception.verify(message.model_copy(deep=True), authentication)
        require(verified.message == message, "verified_message_mismatch")
        old = await self.store.load(verified.context)
        state = old.model_copy(deep=True) if old else SupervisorState(
            context=verified.context, groupchat_version_id=self.groupchat_version_id,
            turn_policy=self.turn_policy)
        require(old is None or old.reception is not None, "v1_checkpoint_requires_migration")
        receive(state, verified, self.clock())
        return await self._save(state, old.version if old else None)

    async def _view(self, state):
        view = await self.authority.inspect(state.model_copy(deep=True))
        require(view.context == state.context and view.state_version == state.version, "stale_authority_view")
        if state.reception is not None:
            require(bool(view.reception_readers), "dependency_unavailable:reception_context_acl")
            require(not any(item.item_id == "reception-v2-ticket" for item in view.ticket_context),
                    "duplicate_context_item")
            view.ticket_context.append(reception_context(
                state.reception, state.context, state.reception.ticket_version, view.reception_readers))
        return view

    async def _record(self, state, receipt):
        """Persist receipt with a CAS; stale returns remain recoverable by the journal."""
        a = state.action
        require(a is not None, "action_missing")
        identity = "message_id" if a.channel == "reception" else "request_id"
        require(receipt.get(identity) == a.wire[identity], "receipt_mismatch")
        expected = state.version
        a.receipt = receipt
        if a.channel == "reception":
            require(receipt.get("status") in ("accepted", "completed"), "invalid_receipt")
            a.status = "done"
            if a.operation in ("completed", "cancelled", "failed"):
                state.phase = a.operation
        elif a.channel == "backend":
            require(receipt.get("status") in ("accepted", "completed"), "invalid_receipt")
            a.status = "done"  # Only delivery acknowledged; approvals come through verifier.
            if a.operation == "resident.update" and state.completion:
                # Request is persisted as a separate action in the next resume step.
                state.phase = "waiting_completion"
        else:
            status = receipt.get("status")
            code = receipt.get("error", {}).get("code")
            raw = receipt.get("data") if status != "error" else receipt.get("error", {}).get("details", {}).get("turn_result")
            data = RoomData.model_validate(raw) if raw else None
            if data:
                require(data.ticket_id == state.context.ticket_id and
                        data.ticket_generation == state.context.ticket_generation and
                        (state.room is None or data.room_id == state.room.room_id), "room_receipt_scope")
                state.room = data
            if status == "accepted":
                a.status = "accepted"
            elif code in ("OUTCOME_UNKNOWN", "DEPENDENCY_UNAVAILABLE"):
                a.status = "unknown"
                state.pause_reason = "outcome_unknown"
            elif status == "error":
                a.status = "failed"
                if data and data.turn_status:
                    state.terminal_results[a.action_id] = data
                state.run_after_put = None
                if a.operation == "add_participant":
                    state.context_drafts = []
                    state.context_join_pending = None
                if a.operation == "put_context" and code in ("STALE_VERSION", "ROOM_BUSY", "ROOM_PAUSED"):
                    state.context_drafts = []
                if a.operation == "put_task" and code in ("STALE_VERSION", "ROOM_BUSY", "ROOM_PAUSED"):
                    # Release only metadata for tasks proven not applied. Do not
                    # patch expected_room_version and replay the discarded draft.
                    # The next planner decision validates the whole graph anew.
                    known = {t.task_id for t in state.room.tasks} if state.room else set()
                    discarded = {t.task_id for t in state.task_drafts}
                    discarded.add(a.wire["payload"]["task"]["task_id"])
                    for task_id in discarded - known:
                        state.tasks.pop(task_id, None)
                    state.task_drafts = []
                pause(state, code or "room_error")
            else:
                require(status == "completed" and data is not None, "invalid_room_receipt")
                if a.operation == "open_room":
                    state.context_fingerprints.update({
                        item["item_id"]: ContextItem.model_validate(item).model_dump_json()
                        for item in a.wire["payload"]["ticket_context"]
                    })
                elif a.operation == "put_context":
                    item = ContextItem.model_validate(a.wire["payload"]["item"])
                    state.context_fingerprints[item.item_id] = item.model_dump_json()
                if a.operation == "run_turn":
                    require(data.turn_status in ("success", "failure", "timeout", "cancel"), "terminal_required")
                    require(data.turn_id == a.wire["payload"]["turn_id"] and
                            data.task_id == a.wire["payload"]["task_id"], "turn_receipt_mismatch")
                    state.terminal_results[a.action_id] = data
                    if data.turn_status != "success":
                        pause(state, "turn_" + data.turn_status)
                a.status = "done"
                if a.operation == "run_turn" and data.turns_remaining == 0:
                    pause(state, "max_turns")
        if a.status == "done" and state.pause_reason == "outcome_unknown":
            state.pause_reason = None
        if a.status in ("done", "failed"):
            state.journal.append(a.model_copy(deep=True))
            state.action = None
        return await self._save(state, expected)

    def _check_action(self, state):
        a = state.action
        require(a is not None and a.plan_version == state.revision, "stale_action")
        if a.channel == "reception":
            message = SupervisorMessage.model_validate(a.wire)
            require(message.message_type == a.operation and
                    message.message_id == a.action_id and
                    message.ticket_version == state.ticket_version and
                    message.supervisor_run_id == state.supervisor_run_id and
                    message.workspace_id == state.context.workspace_id and
                    state.reception is not None and message.team_id == state.reception.team_id and
                    message.ticket_code == state.reception.ticket_code and
                    (message.tenant_id, message.ticket_id, message.ticket_generation) == state.context.scope(),
                    "action_identity_mismatch")
            if message.message_type in ("information_requested", "plan_approval_requested"):
                require(state.pending_resident == message.message_type and
                        state.pending_ticket_version == message.ticket_version, "resident_request_not_pending")
            if message.message_type == "completed":
                require(state.phase == "waiting_result_validation", "publication_not_authorized")
            elif message.message_type == "cancelled":
                require(state.phase == "waiting_cancellation", "cancellation_not_pending")
            return
        require(Context.model_validate(a.wire["context"]) == state.context and
                a.wire["idempotency_key"] == a.action_id and
                a.wire["request_id"] == a.action_id, "action_identity_mismatch")
        p = a.wire["payload"]
        if a.channel == "backend":
            if a.operation == "approval.requested":
                approval = state.approvals.get(p["stage"])
                require(approval is not None and approval.approval_id == p["approval_id"] and
                        approval.plan_version == state.revision and
                        self.clock() < approval.expires_at, "approval_expired_or_stale")
                require(state.phase == ("waiting_management" if p["stage"] == "management_plan"
                                        else "waiting_resident_plan"), "approval_phase_denied")
            elif a.operation == "assignment.offered":
                require(execution_gate(state) and state.phase == "executing" and
                        p == state.assignment, "execution_not_authorized")
            elif a.operation == "completion.requested":
                require(state.phase == "waiting_completion" and p == state.completion,
                        "stale_completion_action")
            elif a.operation == "resident.update":
                require(state.phase == "waiting_result_validation" and state.completion is not None,
                        "publication_not_authorized")
            elif a.operation == "resident.question":
                require(state.phase == "waiting_information" and state.question is not None and
                        state.question.request_id == a.action_id, "question_not_pending")
        elif a.operation == "run_turn":
            task = runnable(state, p["task_id"], p["speaker_agent_version_id"])
            require(task.status == "in_progress", "task_not_started")

    async def _dispatch(self, state):
        a = state.action
        require(a is not None, "action_missing")
        if a.status in ("sending", "unknown"):
            resolution = await self.authority.reconcile(state.model_copy(deep=True), a.model_copy(deep=True))
            if resolution.outcome == "unknown":
                return state
            if resolution.outcome == "receipt":
                require(resolution.receipt is not None, "invalid_reconciliation")
                return await self._record(state, resolution.receipt)
            # This proof must also fence any previously running worker. Preserve
            # original wire/key; never regenerate payload from current context.
            a.status = "pending"
            return await self._save(state, state.version)
        if a.status == "accepted":
            return await self._record(state, await self.room.terminal(a))
        require(a.status == "pending", "invalid_action_state")
        self._check_action(state)
        await self.authority.authorize_action(state.model_copy(deep=True), a.model_copy(deep=True))
        a.status = "sending"
        state = await self._save(state, state.version)
        try:
            if a.channel == "reception":
                require(self.reception is not None, "dependency_unavailable:reception_v2")
                receipt = await self.reception.send(SupervisorMessage.model_validate(a.wire), state.context)
            else:
                receipt = await (self.room.dispatch(a) if a.channel == "room" else self.backend.dispatch(a))
        except Exception as exc:
            # Cancellation/BaseException leaves 'sending', also forcing reconciliation.
            old_version = state.version
            if isinstance(exc, AdapterError) and not exc.outcome_unknown:
                a.status = "failed"
                a.receipt = {"error": exc.code}
                state.journal.append(a.model_copy(deep=True))
                state.action = None
                pause(state, exc.code)
            else:
                a.status = "unknown"
                state.pause_reason = "outcome_unknown"
            return await self._save(state, old_version)
        return await self._record(state, receipt)

    async def resume(self, context: Context, trigger: str = "worker") -> SupervisorState:
        # trigger is diagnostic only: no caller string can approve/unpause work.
        for _ in range(self.max_steps):
            original = await self.store.load(context)
            require(original is not None and original.context == context, "scope_missing")
            state = original.model_copy(deep=True)
            try:
                view = await self._view(state)
                if state.action:
                    state = await self._dispatch(state)
                    if state.phase == "paused" or (state.action and state.action.status in ("sending", "accepted", "unknown")):
                        return state
                    continue
                if state.phase == "paused" and state.pause_reason in {
                    "STALE_VERSION", "ROOM_BUSY", "ROOM_PAUSED", "CONSECUTIVE_LIMIT",
                    "AGENT_FAILURE", "AGENT_TIMEOUT", "turn_cancel",
                } and state.resume_phase:
                    # Known failed/not-applied attempt: refresh room, ask planner
                    # again. Never patch/replay a stale command under its old key.
                    state.phase, state.pause_reason = state.resume_phase, None
                    state.resume_phase = None
                    await self._save(state, original.version)
                    continue
                if state.phase in ("paused", "completed", "cancelled", "failed"):
                    return state
                if state.room:
                    state.room = await self.room.read(context, state.room.room_id)
                if state.phase == "waiting_completion" and state.completion and not any(
                    a.operation == "completion.requested" and
                    a.wire["payload"]["confirmation_id"] == state.completion["confirmation_id"]
                    for a in state.journal
                ):
                    action(state, "backend", "completion.requested", dict(state.completion))
                elif prepare_next(state, view, self.clock()):
                    pass
                elif state.question_draft is not None:
                    return state  # Backend must store/version the proposed question.
                elif state.phase == "waiting_result_validation" and state.publication_draft:
                    return state  # Backend must authorize the draft/QC/cost before delivery.
                elif state.phase in ("planning", "waiting_result_validation"):
                    decision = await self.planner.decide(state.model_copy(deep=True), view)
                    # CAS below rejects stale model output. Recheck rights after model I/O.
                    view = await self._view(state)
                    if state.room:
                        current_room = await self.room.read(context, state.room.room_id)
                        require(current_room.room_version == state.room.room_version, "STALE_VERSION")
                    prepare_decision(state, decision, view, self.clock())
                else:
                    return state
                await self._save(state, original.version)
            except SupervisorError as exc:
                if exc.code == "state_conflict":
                    raise  # Another worker won; no hidden spin/re-dispatch.
                # Do not commit half a failed transition. Keep the last durable snapshot.
                current = await self.store.load(context)
                require(current is not None and current.version == original.version, "state_conflict")
                state = current.model_copy(deep=True)
                if state.phase in ("paused", "completed", "cancelled", "failed"):
                    raise
                if state.action:
                    # Pending work remains recoverable; authorization failure doesn't
                    # erase its wire or permit a new key.
                    state.pause_reason = exc.code
                elif (state.phase == "waiting_result_validation" or state.reception is not None) and exc.code.startswith("dependency_unavailable"):
                    state.pause_reason = exc.code
                else:
                    pause(state, exc.code)
                return await self._save(state, state.version)
        # Bounded model/non-agent progression, independent of DEV-2 turn budget.
        state = (await self.store.load(context)).model_copy(deep=True)
        if not state.action:
            pause(state, "automatic_step_limit")
            return await self._save(state, state.version)
        return state
