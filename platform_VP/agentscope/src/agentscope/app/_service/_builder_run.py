"""Durable checkpoints for one frozen Builder outline, using existing storage."""

import asyncio
import copy
from contextlib import AsyncExitStack, asynccontextmanager
from datetime import UTC, datetime

from fastapi import HTTPException

from ._builder_decisions import digest

RUN_KEY = "builder_run_v1"


@asynccontextmanager
async def builder_run_guard(bus, owner_id, conversation_id):
    """Serialize authoring/retries across workers, with the bus's renewable lease."""
    async with AsyncExitStack() as stack:
        try:
            await asyncio.wait_for(
                stack.enter_async_context(
                    bus.acquire_lock(
                        f"builder-run:{digest([owner_id, conversation_id])}",
                        ttl_secs=600,
                    )
                ),
                timeout=1,
            )
        except TimeoutError as exc:
            raise HTTPException(
                409,
                "Hội thoại Builder đang được xử lý; tải lại kết quả trước khi thử tiếp.",
            ) from exc
        yield


class BuilderRun:
    def __init__(self, storage, owner_id, session, value):
        self.storage, self.owner_id, self.session = storage, owner_id, session
        self.value = copy.deepcopy(value)

    @classmethod
    def load(cls, storage, owner_id, session):
        value = session.state.middle_context.get(RUN_KEY)
        return cls(storage, owner_id, session, value) if value else None

    async def save(self):
        # Progress/memory may have changed other fields since this object loaded.
        current = await self.storage.get_session(
            self.owner_id, self.session.agent_id, self.session.id
        )
        if current is None:
            raise HTTPException(404, "Hội thoại Builder đã bị xóa.")
        self.value["updated_at"] = datetime.now(UTC).isoformat()
        current.state.middle_context[RUN_KEY] = copy.deepcopy(self.value)
        await self.storage.update_session_state(
            self.owner_id, current.agent_id, current.id, current.state
        )

    def cache_key(self, state, questions, model, purpose):
        return digest(
            {
                "contract": 1,
                "snapshot": self.value["snapshot"],
                "model": model,
                "purpose": purpose,
                "state": state,
                "questions": {
                    k: q.model_dump(mode="json") for k, q in questions.items()
                },
            }
        )

    async def remember(self, key, answers):
        self.value.setdefault("batches", {})[key] = answers
        await self.save()

    async def status(self, classifier_status):
        self.value["classifier_status"] = classifier_status.model_dump(mode="json")
        await self.save()
