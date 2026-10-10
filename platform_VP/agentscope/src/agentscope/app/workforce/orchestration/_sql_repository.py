"""SQL persistence without hidden engine creation or schema mutation at startup."""

from contextlib import asynccontextmanager
from dataclasses import asdict

from sqlalchemy import and_, insert, select, update

from ._models import StoredCommand, StoredConversation, StoredRun, StoredWorkflow, require
from ._tables import SCOPE_COLUMNS, conversations, runs, workflows, commands


KINDS = {"conversation": (conversations, StoredConversation, "conversation_id", "state_revision"),
         "run": (runs, StoredRun, "run_id", "revision"),
         "workflow": (workflows, StoredWorkflow, "workflow_id", "revision"),
         "command": (commands, StoredCommand, "request_id", "revision")}


class SQLOrchestrationRepository:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    @asynccontextmanager
    async def transaction(self):
        async with self.session_factory() as session:
            async with session.begin():
                yield session

    def _where(self, kind, scope, record_id):
        table, _, id_name, _ = KINDS[kind]
        return and_(table.c[id_name] == record_id,
                    *(table.c[name] == value for name, value in zip(SCOPE_COLUMNS, scope, strict=True)))

    async def get(self, kind, scope, record_id, uow):
        table, cls, _, _ = KINDS[kind]
        result = await uow.execute(select(table.c.payload).where(self._where(kind, scope, record_id)).with_for_update())
        payload = result.scalar_one_or_none()
        if payload is None:
            return None
        payload = dict(payload)
        payload["scope"] = tuple(payload["scope"])
        if kind == "run":
            payload["requirements"] = tuple(payload["requirements"])
        return cls(**payload)

    async def insert(self, kind, record, uow):
        table, _, id_name, revision_name = KINDS[kind]
        values = {**dict(zip(SCOPE_COLUMNS, record.scope, strict=True)),
                  id_name: getattr(record, id_name), "revision": getattr(record, revision_name),
                  "payload": asdict(record)}
        if kind == "run":
            values.update(conversation_id=record.conversation_id, group_id=record.group_id)
        if kind == "workflow":
            values.update(conversation_id=record.conversation_id, group_id=record.group_id,
                          **{name: record.audience[name] for name in (
                              "partner_client_id", "external_user_id", "external_ticket_id", "external_conversation_id")})
        if kind == "command":
            values.update(partner_client_id=record.partner_client_id, external_request_id=record.external_request_id,
                          workflow_id=record.workflow_id)
        await uow.execute(insert(table).values(**values))

    async def save(self, kind, record, expected_revision, uow):
        table, _, id_name, revision_name = KINDS[kind]
        previous = await self.get(kind, record.scope, getattr(record, id_name), uow)
        require(previous is not None, "RESOURCE_NOT_FOUND")
        immutable = {
            "conversation": ("scope", "mode", "timezone", "direct_agent_id"),
            "run": ("scope", "conversation_id", "group_id", "leader_session_id"),
            "workflow": ("scope", "conversation_id", "group_id", "audience", "route_id", "route_revision"),
            "command": ("scope", "partner_client_id", "external_request_id", "workflow_id", "payload_hash", "accepted_at"),
        }
        require(all(getattr(previous, key) == getattr(record, key) for key in immutable[kind]),
                "IMMUTABLE_BINDING_CHANGED")
        payload = asdict(record)
        payload[revision_name] = expected_revision + 1
        result = await uow.execute(update(table).where(
            self._where(kind, record.scope, getattr(record, id_name)), table.c.revision == expected_revision,
        ).values(revision=expected_revision + 1, payload=payload))
        require(result.rowcount == 1, "REVISION_CONFLICT")
        return await self.get(kind, record.scope, getattr(record, id_name), uow)

    async def find_command(self, tenant_id, partner_client_id, external_request_id, uow):
        result = await uow.execute(select(commands.c.payload).where(
            commands.c.tenant_id == tenant_id, commands.c.partner_client_id == partner_client_id,
            commands.c.external_request_id == external_request_id).with_for_update())
        payload = result.scalar_one_or_none()
        if payload is None:
            return None
        payload = dict(payload)
        payload["scope"] = tuple(payload["scope"])
        return StoredCommand(**payload)

    async def find_binding(self, tenant_id, audience, uow):
        from sqlalchemy import or_
        result = await uow.execute(select(workflows.c.payload).where(
            workflows.c.tenant_id == tenant_id,
            workflows.c.partner_client_id == audience["partner_client_id"],
            workflows.c.external_user_id == audience["external_user_id"],
            or_(workflows.c.external_ticket_id == audience["external_ticket_id"],
                workflows.c.external_conversation_id == audience["external_conversation_id"])).with_for_update())
        payloads = result.scalars().all()
        if not payloads:
            return None
        # A request combining ticket A with chat B is always a conflict.
        require(len(payloads) == 1, "WORKFLOW_BINDING_MISMATCH")
        payload = dict(payloads[0])
        payload["scope"] = tuple(payload["scope"])
        return StoredWorkflow(**payload)
