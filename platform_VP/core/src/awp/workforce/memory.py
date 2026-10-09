"""Private per-agent, per-workflow notes. Notes are never verified evidence."""
import json
import time
from typing import ClassVar

from agentscope.message import TextBlock, ToolResultState
from agentscope.permission import PermissionBehavior, PermissionDecision
from agentscope.tool import ToolBase, ToolChunk
from sqlalchemy import insert, select, update

from . import schema as s
from .service import Fault, row


class MemoryRecall(ToolBase):
    name = "memory_recall"
    description = "Recall your private notes in this workflow. Notes are unverified hints; verify against tools before reporting facts."
    is_read_only = True
    input_schema: ClassVar[dict] = {"type": "object", "properties": {}, "additionalProperties": False}

    def __init__(self, service, binding):
        super().__init__()
        self.service, self.binding = service, binding

    async def scope(self, conn):
        wf = await self.binding.fence.check(self.service, conn)
        profile, _ = await self.service.rt.profile_of(self.binding.user_id, self.binding.agent_id, wf["snapshot"]["tenant"])
        if not profile or not profile.memory.enabled:
            raise Fault(403, "MEMORY_NOT_GRANTED")
        return wf, profile

    async def check_permissions(self, *args, **kwargs):
        return PermissionDecision(behavior=PermissionBehavior.ALLOW, message="Private scoped notes")

    async def call(self):
        async with self.service.tx() as conn:
            wf, profile = await self.scope(conn)
            notes = (await conn.execute(select(s.memory.c.key, s.memory.c.text).where(
                s.memory.c.workflow_id == wf["id"], s.memory.c.profile_key == profile.key))).mappings().all()
        return ToolChunk(content=[TextBlock(text=json.dumps({"unverified_notes": [dict(x) for x in notes]}, ensure_ascii=False))],
                         state=ToolResultState.SUCCESS)


class MemoryRemember(MemoryRecall):
    name = "memory_remember"
    description = "Save an unverified private note for this agent and workflow. Maximum 32 notes. Reusable knowledge requires administrator review."
    is_read_only = False
    input_schema: ClassVar[dict] = {"type": "object", "properties": {"key": {"type": "string", "minLength": 1, "maxLength": 80},
                    "text": {"type": "string", "minLength": 1, "maxLength": 8000}},
                    "required": ["key", "text"], "additionalProperties": False}

    async def call(self, key, text):
        if not isinstance(key, str) or not 0 < len(key) <= 80 or not isinstance(text, str) or not 0 < len(text) <= 8000:
            raise Fault(422, "INVALID_MEMORY_NOTE")
        async with self.service.tx() as conn:
            wf, profile = await self.scope(conn)
            await row(conn, s.workflows, s.workflows.c.id == wf["id"], lock=True)
            where = (s.memory.c.workflow_id == wf["id"], s.memory.c.profile_key == profile.key)
            old = await row(conn, s.memory, *where, s.memory.c.key == key)
            if old:
                await conn.execute(update(s.memory).where(*where, s.memory.c.key == key).values(text=text, updated=time.time()))
            else:
                count = len((await conn.execute(select(s.memory.c.key).where(*where))).all())
                if count >= 32:
                    raise Fault(409, "MEMORY_NOTE_LIMIT")
                await conn.execute(insert(s.memory).values(workflow_id=wf["id"], profile_key=profile.key,
                    key=key, text=text, updated=time.time()))
        return ToolChunk(content=[TextBlock(text="Private unverified note saved.")], state=ToolResultState.SUCCESS)
