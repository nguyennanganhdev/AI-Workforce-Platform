"""Which agents may run unattended from a channel or a schedule."""

from __future__ import annotations

from fastapi import HTTPException

from ..storage import AgentRecord, StorageBase


def is_runnable(record: AgentRecord) -> bool:
    """The Leader, or a business agent that passed its publish gate."""
    return record.data.system_role == "leader" or record.data.lifecycle_state == "published"


async def ensure_runnable(storage: StorageBase, user_id: str, agent_id: str) -> AgentRecord:
    record = await storage.get_agent(user_id, agent_id)
    if record is None:
        raise HTTPException(404, "Không tìm thấy agent.")
    if not is_runnable(record):
        raise HTTPException(
            400,
            f"Agent “{record.data.name}” chưa phát hành. Chỉ Leader hoặc agent đã phát hành "
            "mới được gắn vào kênh hoặc lịch chạy.",
        )
    return record
