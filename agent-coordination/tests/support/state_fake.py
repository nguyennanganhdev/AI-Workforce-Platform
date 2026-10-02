"""Test fake dùng rollback transaction và process-local lock; không durable."""

import asyncio
from contextlib import asynccontextmanager

from groupchat.models import Context, ScopeState


class InMemoryState:
    def __init__(self):
        self.records: dict[tuple, ScopeState] = {}
        self.locks: dict[tuple, asyncio.Lock] = {}

    @asynccontextmanager
    async def transaction(self, context: Context):
        key = context.scope()
        async with self.locks.setdefault(key, asyncio.Lock()):
            working = self.records.get(key, ScopeState()).model_copy(deep=True)
            yield working
            self.records[key] = working.model_copy(deep=True)
