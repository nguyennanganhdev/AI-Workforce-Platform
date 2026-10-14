"""Long-term memory of business agents: recall and consolidation.

Retrieval is lexical (accent-folded, BM25-style) on purpose: an agent's
memory is small (hundreds of short Vietnamese/English sentences), needs no
embedding endpoint to work, and is fully explainable. Consolidation follows
the ADD / UPDATE / NOOP pattern: a model compares each new candidate with the
most similar existing items; an update supersedes the old item instead of
deleting it, so history and provenance stay visible.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from .._logging import logger
from ..message import UserMsg
from ..model import ChatModelBase
from .storage import AgentMemoryRecord, StorageBase

_TOKEN = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "va", "cua", "la", "co", "cho", "khong", "duoc", "mot", "cac", "nhung",
    "voi", "khi", "thi", "nay", "do", "o", "tai", "de", "da", "se", "dang",
    "nhu", "neu", "vao", "ra", "len", "the", "a", "an", "to", "of", "and",
    "is", "are", "for", "in", "on", "with", "be", "it", "that", "this",
}


def fold_tokens(text: str) -> list[str]:
    decomposed = unicodedata.normalize("NFKD", text.casefold()).replace("đ", "d")
    plain = "".join(c for c in decomposed if not unicodedata.combining(c))
    return [token for token in _TOKEN.findall(plain) if token not in _STOPWORDS and len(token) > 1]


def rank(query: str, memories: list[AgentMemoryRecord]) -> list[tuple[float, AgentMemoryRecord]]:
    """BM25-style score of each memory against ``query`` (best first)."""

    query_tokens = set(fold_tokens(query))
    if not query_tokens or not memories:
        return []
    documents = [fold_tokens(memory.content) for memory in memories]
    frequency = Counter(token for document in documents for token in set(document))
    count = len(documents)
    average = sum(len(document) for document in documents) / count or 1.0
    scored = []
    for memory, document in zip(memories, documents):
        if not document:
            continue
        terms = Counter(document)
        score = 0.0
        for token in query_tokens & set(terms):
            idf = math.log(1 + (count - frequency[token] + 0.5) / (frequency[token] + 0.5))
            tf = terms[token]
            score += idf * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * len(document) / average))
        if score > 0:
            scored.append((score * (0.5 + memory.confidence / 2), memory))
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored


class MemoryCandidate(BaseModel):
    kind: Literal["lesson", "fact", "preference"] = "lesson"
    content: str = Field(min_length=1, max_length=2000)
    evidence_event_ids: list[str] = Field(default_factory=list, max_length=20)


class _Decision(BaseModel):
    candidate: int = Field(ge=0, description="Index of the candidate.")
    action: Literal["add", "update", "noop"]
    target_id: str | None = Field(
        default=None,
        description="update: the id of the existing memory it replaces.",
    )
    content: str = Field(
        default="",
        description="add/update: the final wording (merge old and new when updating).",
    )


class _Decisions(BaseModel):
    decisions: list[_Decision] = Field(default_factory=list)


class AgentMemoryService:
    """Store, recall and consolidate one agent's memories."""

    def __init__(self, storage: StorageBase) -> None:
        self._storage = storage

    async def active(self, user_id: str, agent_id: str) -> list[AgentMemoryRecord]:
        try:
            return await self._storage.list_agent_memories(user_id, agent_id, status="active")
        except NotImplementedError:
            return []

    async def recall(
        self,
        user_id: str,
        agent_id: str,
        query: str,
        *,
        limit: int = 5,
        max_chars: int = 2400,
    ) -> list[AgentMemoryRecord]:
        """Best matching active memories within a character budget."""

        selected: list[AgentMemoryRecord] = []
        used = 0
        for _score, memory in rank(query, await self.active(user_id, agent_id)):
            if len(selected) >= limit or used + len(memory.content) > max_chars:
                break
            selected.append(memory)
            used += len(memory.content)
        for memory in selected:
            memory.uses += 1
            try:
                await self._storage.upsert_agent_memory(user_id, memory)
            except Exception:  # noqa: BLE001 - usage count is best effort
                logger.debug("Could not count memory use", exc_info=True)
        return selected

    @staticmethod
    def render(memories: list[AgentMemoryRecord]) -> str:
        if not memories:
            return ""
        lines = "\n".join(f"- [{memory.kind}] {memory.content}" for memory in memories)
        return (
            "\n<agent-memory>\nExperience from your earlier verified tickets. "
            "Use it as guidance only: current tool results and the customer's "
            "words always win, and never quote a remembered fact as current "
            "without checking it.\n"
            f"{lines}\n</agent-memory>"
        )

    async def retire(
        self,
        user_id: str,
        agent_id: str,
        memory_id: str,
        reason: str = "",
    ) -> AgentMemoryRecord | None:
        memory = await self._storage.get_agent_memory(user_id, agent_id, memory_id)
        if memory is None:
            return None
        memory.status = "rejected"
        memory.reason = (reason or "Gỡ bởi người quản lý")[:1000]
        await self._storage.upsert_agent_memory(user_id, memory)
        return memory

    async def consolidate(
        self,
        user_id: str,
        agent_id: str,
        candidates: list[MemoryCandidate],
        *,
        ticket_id: str,
        model: ChatModelBase | None,
    ) -> list[dict]:
        """Apply ADD / UPDATE / NOOP for each candidate; return what changed."""

        if not candidates:
            return []
        existing = await self.active(user_id, agent_id)
        by_id = {memory.id: memory for memory in existing}
        folded_existing = {" ".join(fold_tokens(memory.content)) for memory in existing}
        fresh = [
            candidate
            for candidate in candidates
            if " ".join(fold_tokens(candidate.content)) not in folded_existing
        ]
        if not fresh:
            return []
        neighbours = {
            index: [memory for _s, memory in rank(candidate.content, existing)[:3]]
            for index, candidate in enumerate(fresh)
        }
        decisions: list[_Decision]
        if model is None or not any(neighbours.values()):
            decisions = [
                _Decision(candidate=index, action="add", content=candidate.content)
                for index, candidate in enumerate(fresh)
            ]
        else:
            prompt = (
                "Bạn quản lý bộ nhớ dài hạn của một AI agent. Với mỗi ỨNG VIÊN mới, "
                "so với các ký ức GẦN GIỐNG đang có và chọn: add (thông tin mới), "
                "update (cùng chủ đề nhưng mới hơn/đúng hơn hoặc mâu thuẫn — ghi "
                "target_id của ký ức cũ và nội dung đã hợp nhất), noop (đã có, "
                "không thêm gì). Không bịa nội dung ngoài ứng viên và ký ức cũ.\n\n"
                + "\n\n".join(
                    f"ỨNG VIÊN {index}: {candidate.content}\nGẦN GIỐNG: "
                    + (
                        "; ".join(f"[{m.id}] {m.content}" for m in neighbours[index])
                        or "(không có)"
                    )
                    for index, candidate in enumerate(fresh)
                )
            )
            try:
                response = await model.generate_structured_output(
                    messages=[UserMsg(name="memory_manager", content=prompt)],
                    structured_model=_Decisions,
                )
                decisions = _Decisions.model_validate(response.content).decisions
            except Exception:  # noqa: BLE001 - fall back to plain adds
                logger.exception("Memory consolidation model call failed")
                decisions = [
                    _Decision(candidate=index, action="add", content=candidate.content)
                    for index, candidate in enumerate(fresh)
                ]
        changes: list[dict] = []
        handled: set[int] = set()
        for decision in decisions:
            if decision.candidate >= len(fresh) or decision.candidate in handled:
                continue
            handled.add(decision.candidate)
            candidate = fresh[decision.candidate]
            if decision.action == "noop":
                continue
            record = AgentMemoryRecord(
                user_id=user_id,
                agent_id=agent_id,
                kind=candidate.kind,
                content=(decision.content or candidate.content)[:2000],
                source_ticket=ticket_id,
                source_event_ids=candidate.evidence_event_ids[:20],
                confidence=0.8 if candidate.evidence_event_ids else 0.6,
                reason="Tự duyệt sau ticket đã xác minh",
            )
            old = by_id.get(decision.target_id or "") if decision.action == "update" else None
            if old is not None:
                old.status = "superseded"
                old.reason = f"Thay bằng ký ức mới từ ticket {ticket_id[:8]}"
                old.updated_at = datetime.now()
                await self._storage.upsert_agent_memory(user_id, old)
                record.supersedes = old.id
            await self._storage.upsert_agent_memory(user_id, record)
            changes.append(
                {
                    "action": "update" if old is not None else "add",
                    "memory_id": record.id,
                    "supersedes": record.supersedes,
                    "content": record.content,
                },
            )
        return changes


__all__ = [
    "AgentMemoryService",
    "MemoryCandidate",
    "fold_tokens",
    "rank",
]
