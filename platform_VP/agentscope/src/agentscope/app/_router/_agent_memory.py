# -*- coding: utf-8 -*-
"""Review an agent's memory: approve, reject, pin, confirm or delete."""
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from .._service._agent_memory import _SENSITIVE, MemoryData, view
from ..deps import get_current_user_id, get_storage
from ..storage import AgentArtifactRecord, StorageBase

agent_memory_router = APIRouter(prefix="/agent/{agent_id}/memories", tags=["agent-memory"])

_ORDER = {"proposed": 0, "approved": 1, "rejected": 2}


class AddMemoryRequest(BaseModel):
    content: str = Field(min_length=1, max_length=300)


class ApproveMemoryRequest(BaseModel):
    content: str | None = Field(default=None, min_length=1, max_length=300, description="Edited wording.")


class UpdateMemoryRequest(BaseModel):
    pinned: bool | None = None
    confirm: bool = Field(default=False, description="Mark it still true, restoring full priority.")


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _clean(content: str) -> str:
    content = " ".join(content.split())
    if _SENSITIVE.search(content):
        raise HTTPException(status_code=422, detail="Không ghi nhớ mật khẩu, mã OTP, số thẻ, số giấy tờ hay khoá bí mật.")
    return content


async def _agent(storage: StorageBase, user_id: str, agent_id: str) -> None:
    if await storage.get_agent(user_id, agent_id) is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy agent.")


async def _memory(storage: StorageBase, user_id: str, agent_id: str, memory_id: str) -> tuple[AgentArtifactRecord, MemoryData]:
    record = await storage.get_agent_artifact(user_id, memory_id)
    if record is None or record.agent_id != agent_id or record.kind != "memory":
        raise HTTPException(status_code=404, detail="Không tìm thấy ghi nhớ.")
    return record, MemoryData.model_validate(record.data)


async def _save(storage: StorageBase, user_id: str, record: AgentArtifactRecord, data: MemoryData) -> dict:
    record.data = data.model_dump()
    await storage.upsert_agent_artifact(user_id, record)
    return view(record)


@agent_memory_router.get("", summary="Proposals waiting for review, then approved memories by priority")
async def list_memories(
    agent_id: str,
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
) -> list[dict]:
    await _agent(storage, user_id, agent_id)
    views = [view(r) for r in await storage.list_agent_artifacts(user_id, agent_id, "memory")]
    views = [item for item in views if item["status"] != "rejected"]
    return sorted(views, key=lambda item: (_ORDER[item["status"]], -item["priority"]))


@agent_memory_router.post("", status_code=status.HTTP_201_CREATED, summary="Add an approved memory by hand")
async def add_memory(
    agent_id: str,
    body: AddMemoryRequest,
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
) -> dict:
    await _agent(storage, user_id, agent_id)
    now = _now()
    data = MemoryData(content=_clean(body.content), status="approved", proposed_at=now, approved_at=now)
    record = AgentArtifactRecord(user_id=user_id, agent_id=agent_id, kind="memory")
    return await _save(storage, user_id, record, data)


@agent_memory_router.post("/{memory_id}/approve", summary="Approve a proposal, optionally reworded")
async def approve_memory(
    agent_id: str,
    memory_id: str,
    body: ApproveMemoryRequest,
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
) -> dict:
    record, data = await _memory(storage, user_id, agent_id, memory_id)
    if body.content is not None:
        data.content = _clean(body.content)
    now = _now()
    data.status, data.approved_at, data.last_confirmed_at = "approved", now, now
    return await _save(storage, user_id, record, data)


@agent_memory_router.post("/{memory_id}/reject", summary="Reject a proposal")
async def reject_memory(
    agent_id: str,
    memory_id: str,
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
) -> dict:
    record, data = await _memory(storage, user_id, agent_id, memory_id)
    data.status = "rejected"
    return await _save(storage, user_id, record, data)


@agent_memory_router.patch("/{memory_id}", summary="Pin, unpin or confirm an approved memory")
async def update_memory(
    agent_id: str,
    memory_id: str,
    body: UpdateMemoryRequest,
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
) -> dict:
    record, data = await _memory(storage, user_id, agent_id, memory_id)
    if data.status != "approved":
        raise HTTPException(status_code=409, detail="Hãy duyệt ghi nhớ trước.")
    if body.pinned is not None:
        data.pinned = body.pinned
    if body.confirm:
        data.confirmations += 1
        data.last_confirmed_at = _now()
    return await _save(storage, user_id, record, data)


@agent_memory_router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(
    agent_id: str,
    memory_id: str,
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
) -> None:
    await _memory(storage, user_id, agent_id, memory_id)
    await storage.delete_agent_artifact(user_id, memory_id)
