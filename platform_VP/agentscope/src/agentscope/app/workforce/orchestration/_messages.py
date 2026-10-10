"""Persist manager messages and pending delivery before runtime dispatch."""

from hashlib import sha256
import json

from ._mentions import resolve_recipient
from ._models import detached, new_id, require, scope_key


class MessageService:
    def __init__(self, repository, identity, deliver_message):
        self.repository, self.identity = repository, identity
        self.deliver = deliver_message

    async def send_message(self, scope, conversation_id, *, client_message_id, content,
                           target_agent_id=None, reply_to_message_id=None):
        require(isinstance(content, str) and 0 < len(content.strip()) <= 32_000, "MESSAGE_INVALID")
        require(isinstance(client_message_id, str) and 0 < len(client_message_id) <= 128, "MESSAGE_ID_INVALID")
        fingerprint = sha256(json.dumps([content, target_agent_id, reply_to_message_id],
                                        ensure_ascii=False).encode()).hexdigest()
        async with self.repository.transaction() as uow:
            await self.identity.check_scope_active(scope, uow)
            conversation = await self.repository.get("conversation", scope_key(scope), conversation_id, uow)
            require(conversation is not None, "RESOURCE_NOT_FOUND")
            existing = next((m for m in conversation.messages if m.get("client_message_id") == client_message_id), None)
            if existing is not None:
                require(existing["payload_hash"] == fingerprint, "MESSAGE_ID_CONFLICT")
                message = existing
                if message["delivery_status"] == "delivered":
                    return detached(message)
                require(bool(message.get("run_id")) and bool(message.get("group_id")), "MESSAGE_BINDING_REQUIRED")
                run = await self.repository.get("run", scope_key(scope), message["run_id"], uow)
                require(run is not None and run.status == "running", "RUN_UNAVAILABLE")
                require(conversation.active_run_id == run.run_id and run.group_id == message["group_id"],
                        "RUN_BINDING_MISMATCH")
                require(message["target_session_id"] in {run.leader_session_id} |
                        {member["session_id"] for member in run.members}, "MEMBER_NOT_FOUND")
            else:
                require(conversation.active_run_id is not None, "RUN_REQUIRED")
                run = await self.repository.get("run", scope_key(scope), conversation.active_run_id, uow)
                require(run is not None and run.status == "running", "RUN_UNAVAILABLE")
                if conversation.mode == "direct":
                    require(target_agent_id in (None, conversation.direct_agent_id), "DIRECT_TARGET_INVALID")
                    target_agent_id = conversation.direct_agent_id
                target = resolve_recipient(run, conversation, target_agent_id=target_agent_id,
                                           reply_to_message_id=reply_to_message_id)
                message = {"message_id": new_id(), "client_message_id": client_message_id,
                           "run_id": run.run_id, "group_id": run.group_id,
                           "conversation_id": conversation_id, "sender": "user", "content": content,
                           "target_agent_id": target_agent_id, "target_session_id": target,
                           "reply_to_message_id": reply_to_message_id, "payload_hash": fingerprint,
                           "delivery_status": "pending"}
                conversation.messages.append(message)
                await self.repository.save("conversation", conversation, conversation.state_revision, uow)
        await self.identity.check_scope_active(scope)
        await self.deliver(scope, detached(message), idempotency_key=message["message_id"])
        async with self.repository.transaction() as uow:
            await self.identity.check_scope_active(scope, uow)
            current = await self.repository.get("conversation", scope_key(scope), conversation_id, uow)
            stored = next(m for m in current.messages if m["message_id"] == message["message_id"])
            stored["delivery_status"] = "delivered"
            await self.repository.save("conversation", current, current.state_revision, uow)
            return detached(stored)


def shared_context(conversation, *, selected_fact_keys):
    """User-selected facts only, never private message history or credentials."""
    require(set(selected_fact_keys) <= set(conversation.facts), "CONTEXT_FIELD_INVALID")
    return {key: detached(conversation.facts[key]) for key in selected_fact_keys}
