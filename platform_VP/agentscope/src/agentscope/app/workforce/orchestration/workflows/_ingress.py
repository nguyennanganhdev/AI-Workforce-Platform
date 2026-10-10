"""Ticketed partner ingress, durable command/binding and immutable audience.

The guard validates an authenticated partner actor, current routing grant and
audience in the supplied UOW. Jobs must enqueue in that same UOW, not commit
independently. Non-ticketed routes remain a separate integration requirement.
"""

import hashlib
import json
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .._models import StoredCommand, StoredConversation, StoredWorkflow, detached, new_id, require, scope_key
from ._policy import post_status


class TicketIngress:
    def __init__(self, repository, partner_guard, jobs):
        self.repository, self.guard, self.jobs = repository, partner_guard, jobs

    async def accept(self, partner_actor, envelope):
        require(envelope.get("schema_version") == "1", "SCHEMA_VERSION_INVALID")
        require(envelope.get("command_type") in {"start_workflow", "workflow_reply"}, "COMMAND_INVALID")
        for key in ("external_request_id", "external_management_ref", "external_user_id", "external_conversation_id", "external_ticket_id"):
            require(isinstance(envelope.get(key), str) and 0 < len(envelope[key]) <= 128,
                    "EXTERNAL_TICKET_REQUIRED" if key == "external_ticket_id" else "ENVELOPE_INVALID")
        message = envelope.get("message")
        require(isinstance(message, dict) and message.get("type") == "text" and
                isinstance(message.get("text"), str) and 0 < len(message["text"].strip()) <= 32_000, "MESSAGE_INVALID")
        is_reply = envelope["command_type"] == "workflow_reply"
        require(not is_reply or bool(envelope.get("workflow_id")), "WORKFLOW_REFERENCE_REQUIRED")
        require(is_reply or not envelope.get("workflow_id"), "ENVELOPE_INVALID")
        require(not {"scope", "manager_account_id", "group_id", "session_id", "tenant_id", "domain_id",
                     "area_id", "conversation_id", "ticket_id", "route_id", "agent_id", "tool_id",
                     "credential", "role", "execution_mode"}.intersection(envelope), "AUTHORITY_FIELD_FORBIDDEN")
        payload_hash = hashlib.sha256(json.dumps(envelope, sort_keys=True, ensure_ascii=False,
                                                 separators=(",", ":")).encode()).hexdigest()
        async with self.repository.transaction() as uow:
            route = await self.guard.authorize(partner_actor, envelope, "reply" if is_reply else "submit_request", uow)
            timezone = envelope.get("timezone") or route.get("timezone")
            require(isinstance(timezone, str) and bool(timezone), "TIMEZONE_REQUIRED")
            try:
                ZoneInfo(timezone)
            except (ZoneInfoNotFoundError, ValueError):
                require(False, "TIMEZONE_INVALID")
            key = scope_key(route["scope"])
            audience = detached(route["audience"])
            require(all(audience[name] == envelope[name] for name in (
                "external_user_id", "external_ticket_id", "external_conversation_id")), "WORKFLOW_BINDING_MISMATCH")
            previous = await self.repository.find_command(key[0], audience["partner_client_id"], envelope["external_request_id"], uow)
            if previous:
                require(previous.scope == key, "REQUEST_ROUTE_CHANGED")
                require(previous.payload_hash == payload_hash, "REQUEST_ID_CONFLICT")
                workflow = await self.repository.get("workflow", key, previous.workflow_id, uow)
                require(workflow.audience == audience and workflow.route_id == route["route_id"] and
                        workflow.route_revision == route["route_revision"], "REQUEST_ROUTE_CHANGED")
                return self.receipt(previous, workflow)
            binding = await self.repository.find_binding(key[0], audience, uow)
            if is_reply:
                require(binding is not None and binding.workflow_id == envelope["workflow_id"] and
                        binding.scope == key and binding.audience == audience, "WORKFLOW_BINDING_MISMATCH")
                require(binding.route_id == route["route_id"] and binding.route_revision == route["route_revision"], "REQUEST_ROUTE_CHANGED")
                require(binding.state != "closed", "WORKFLOW_CLOSED")
                workflow = binding
            else:
                if binding:
                    require(binding.audience == audience, "CONVERSATION_ALREADY_BOUND")
                    require(False, "TICKET_ALREADY_BOUND")
                conversation_id, group_id, workflow_id = new_id(), new_id(), new_id()
                workflow = StoredWorkflow(workflow_id, key, conversation_id, group_id,
                                          audience, route["route_id"], route["route_revision"])
                await self.repository.insert("conversation", StoredConversation(conversation_id, key, "group", timezone), uow)
                await self.repository.insert("workflow", workflow, uow)
            command = StoredCommand(new_id(), key, audience["partner_client_id"], envelope["external_request_id"],
                                    workflow.workflow_id, payload_hash,
                                    accepted_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"))
            await self.repository.insert("command", command, uow)
            await self.jobs.enqueue(route["scope"], "workflow_turn", {
                "request_id": command.request_id, "workflow_id": workflow.workflow_id,
                "conversation_id": workflow.conversation_id, "group_id": workflow.group_id,
                "message": detached(envelope["message"]), "cause_kind": "user_reply" if is_reply else "start",
            }, command.request_id, uow=uow)
            return self.receipt(command, workflow)

    @staticmethod
    def receipt(command, workflow):
        return {"http_status": post_status(command.status), "request_id": command.request_id,
                "request_status": command.status, "workflow_id": workflow.workflow_id,
                "conversation_id": workflow.conversation_id,
                "external_ticket_id": workflow.audience["external_ticket_id"],
                "workflow_state": workflow.state, "workflow_revision": workflow.revision,
                "next_action": "watch_request" if post_status(command.status) == 202 else workflow.next_action,
                "result": detached(command.result),
                "error": None, "accepted_at": command.accepted_at, "completed_at": command.completed_at,
                "status_url": f"/workforce/v1/partner/requests/{command.request_id}",
                "conversation_url": f"/workforce/v1/partner/conversations/{workflow.conversation_id}",
                "event_stream_url": f"/workforce/v1/partner/conversations/{workflow.conversation_id}/events"}
