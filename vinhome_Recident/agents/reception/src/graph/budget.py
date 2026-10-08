"""Bound injected async ports; cancellation does not prove rollback of side effects."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

from .decision import GraphFault

T = TypeVar("T")


class CancellationToken:
    def __init__(self):
        self._event = asyncio.Event()

    @property
    def aborted(self) -> bool:
        return self._event.is_set()

    def abort(self) -> None:
        self._event.set()

    async def wait(self) -> None:
        await self._event.wait()

    def throw_if_aborted(self) -> None:
        if self.aborted:
            raise GraphFault("REQUEST_ABORTED")


async def with_budget(
    timeout_ms: int,
    parent: CancellationToken | None,
    run: Callable[[CancellationToken], Awaitable[T]],
) -> T:
    if parent:
        parent.throw_if_aborted()
    signal = CancellationToken()
    task = asyncio.create_task(run(signal))
    cancelled = asyncio.create_task(parent.wait()) if parent else None
    watched = {task} | ({cancelled} if cancelled else set())
    try:
        done, _ = await asyncio.wait(
            watched, timeout=timeout_ms / 1000, return_when=asyncio.FIRST_COMPLETED
        )
        if cancelled in done:
            raise GraphFault("REQUEST_ABORTED")
        if task in done:
            return task.result()
        raise GraphFault("PORT_TIMEOUT", True)
    finally:
        signal.abort()
        # Do not await a misbehaving coroutine that swallows cancellation forever.
        for pending in watched:
            if not pending.done():
                pending.cancel()
                pending.add_done_callback(
                    lambda future: (
                        future.exception() if not future.cancelled() else None
                    )
                )
