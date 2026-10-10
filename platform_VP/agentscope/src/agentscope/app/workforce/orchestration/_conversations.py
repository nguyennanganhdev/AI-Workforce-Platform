"""Manager conversation storage. Partner ingress has separate audience guards."""

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ._models import StoredConversation, detached, new_id, require, scope_key


class ConversationService:
    def __init__(self, repository, identity):
        self.repository = repository
        self.identity = identity

    async def create(self, scope, mode="group", timezone="UTC", direct_agent_id=None):
        require(mode in ("group", "direct"), "CONVERSATION_MODE_INVALID")
        require((mode == "direct") == bool(direct_agent_id), "DIRECT_AGENT_REQUIRED")
        try:
            ZoneInfo(timezone)
        except (ZoneInfoNotFoundError, ValueError, TypeError):
            require(False, "TIMEZONE_INVALID")
        record = StoredConversation(new_id(), scope_key(scope), mode, timezone,
                                    direct_agent_id=direct_agent_id)
        async with self.repository.transaction() as uow:
            await self.identity.check_scope_active(scope, uow)
            await self.repository.insert("conversation", record, uow)
        return detached(record)

    async def read_state(self, scope, conversation_id):
        async with self.repository.transaction() as uow:
            await self.identity.check_scope_active(scope, uow)
            record = await self.repository.get("conversation", scope_key(scope), conversation_id, uow)
            require(record is not None, "RESOURCE_NOT_FOUND")
            return detached(record)
