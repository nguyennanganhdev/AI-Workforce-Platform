# -*- coding: utf-8 -*-
"""Memories an agent proposes and the user approves.

An agent proposes a durable fact with ``MemoryPropose``; nothing reaches its
prompt until the user approves it. Approved memories lose priority over time
(half-life ``HALF_LIFE_DAYS``) unless they are pinned, confirmed again by a
new identical proposal, or marked still true; below ``ACTIVE_MIN`` they stay
listed as fading but are no longer given to the agent.
"""
import re
import unicodedata
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

from ..._logging import logger
from ..storage import AgentArtifactRecord, StorageBase

HALF_LIFE_DAYS = 30.0
ACTIVE_MIN = 0.25  # about 60 days without confirmation
PROMPT_LIMIT = 10
PENDING_LIMIT = 20

# Never stored: secrets, payment data and identifiers.
_SENSITIVE = re.compile(
    r"\b(mật khẩu|password|passcode|otp|cvv|cvc|token|api[ _-]?key|secret|"
    r"số thẻ|card number|cccd|cmnd|passport|hộ chiếu)\b"
    r"|\d[\d \-.]{10,}\d",
    re.IGNORECASE,
)


class MemoryData(BaseModel):
    """``AgentArtifactRecord.data`` of kind ``memory``."""

    content: str = Field(min_length=1, max_length=300)
    reason: str = Field(default="", max_length=300)
    status: Literal["proposed", "approved", "rejected"] = "proposed"
    pinned: bool = False
    confirmations: int = 0
    proposed_at: str
    approved_at: str | None = None
    last_confirmed_at: str | None = None
    source_session_id: str | None = None


class MemoryRejected(ValueError):
    """The proposal is not stored; the message says why."""


def _now() -> datetime:
    return datetime.now(UTC)


def _normalized(text: str) -> str:
    text = unicodedata.normalize("NFC", text).casefold()
    return " ".join(re.sub(r"[^\w\s]", " ", text).split())


def priority(data: MemoryData, now: datetime | None = None) -> float:
    """1.0 when fresh or pinned, halving every ``HALF_LIFE_DAYS``."""
    if data.status != "approved":
        return 0.0
    if data.pinned:
        return 1.0
    anchor = data.last_confirmed_at or data.approved_at or data.proposed_at
    days = max(((now or _now()) - datetime.fromisoformat(anchor)).total_seconds() / 86400, 0.0)
    return 0.5 ** (days / HALF_LIFE_DAYS)


def view(record: AgentArtifactRecord, now: datetime | None = None) -> dict:
    """A memory as the UI shows it, with its current priority."""
    data = MemoryData.model_validate(record.data)
    score = priority(data, now)
    return {
        "id": record.id,
        **data.model_dump(),
        "priority": round(score, 3),
        "active": data.status == "approved" and score >= ACTIVE_MIN,
    }


async def propose(
    storage: StorageBase,
    user_id: str,
    agent_id: str,
    content: str,
    reason: str = "",
    session_id: str | None = None,
) -> tuple[Literal["proposed", "reinforced", "duplicate"], AgentArtifactRecord]:
    """Store a proposal, or confirm an identical approved memory again."""
    content = " ".join(content.split())
    if not content:
        raise MemoryRejected("Nội dung ghi nhớ trống.")
    if len(content) > 300:
        raise MemoryRejected("Ghi nhớ tối đa 300 ký tự; hãy viết ngắn một sự thật.")
    if _SENSITIVE.search(content):
        raise MemoryRejected("Không ghi nhớ mật khẩu, mã OTP, số thẻ, số giấy tờ hay khoá bí mật.")
    key = _normalized(content)
    existing = await storage.list_agent_artifacts(user_id, agent_id, "memory")
    for record in existing:
        data = MemoryData.model_validate(record.data)
        if _normalized(data.content) != key:
            continue
        if data.status == "approved":
            data.confirmations += 1
            data.last_confirmed_at = _now().isoformat()
            record.data = data.model_dump()
            await storage.upsert_agent_artifact(user_id, record)
            return "reinforced", record
        if data.status == "proposed":
            return "duplicate", record
    pending = sum(1 for r in existing if r.data.get("status") == "proposed")
    if pending >= PENDING_LIMIT:
        raise MemoryRejected("Đã có nhiều đề xuất ghi nhớ đang chờ người dùng duyệt.")
    record = AgentArtifactRecord(
        user_id=user_id,
        agent_id=agent_id,
        kind="memory",
        data=MemoryData(
            content=content,
            reason=" ".join(reason.split())[:300],
            proposed_at=_now().isoformat(),
            source_session_id=session_id,
        ).model_dump(),
    )
    await storage.upsert_agent_artifact(user_id, record)
    return "proposed", record


async def memory_prompt(storage: StorageBase, user_id: str, agent_id: str) -> str:
    """The approved, still-active memories as a prompt section ("" if none)."""
    now = _now()
    active = []
    try:
        records = await storage.list_agent_artifacts(user_id, agent_id, "memory")
    except Exception:  # noqa: BLE001 - memory is optional; the reply must still run
        logger.warning("Approved memories of agent %s could not be read", agent_id, exc_info=True)
        return ""
    for record in records:
        data = MemoryData.model_validate(record.data)
        score = priority(data, now)
        if data.status == "approved" and score >= ACTIVE_MIN:
            active.append((score, data.content))
    active.sort(key=lambda item: -item[0])
    lines = "\n".join(f"- {content}" for _, content in active[:PROMPT_LIMIT])
    return (
        "APPROVED MEMORY (facts the user approved for this agent; they may be "
        "outdated, so the customer's latest message wins, and live facts such as "
        f"prices or availability still need tools):\n{lines}"
        if lines
        else ""
    )


MEMORY_POLICY = (
    "MEMORY: when the customer states or confirms a durable fact about "
    "themselves or their preferences (for example a home city or a seating "
    "preference), or a successful tool result establishes a lasting outcome, "
    "you may call MemoryPropose with one short sentence. Never propose live "
    "prices, availability, one-off details of the current request, passwords, "
    "OTP codes, card or document numbers. A proposal is not a memory until the "
    "user approves it, so never tell the customer it is saved."
)
