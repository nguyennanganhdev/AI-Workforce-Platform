# -*- coding: utf-8 -*-
"""Replay-first SSE delivery backed by a durable conversation event port."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
import json

from ...contracts import (
    ActorContext,
    ConversationEvent,
    ConversationEventPort,
    OpaqueId,
    PublicEventSignalPort,
    Scope,
)


def _safe_sse_field(value: str, field: str) -> str:
    if "\r" in value or "\n" in value:
        raise ValueError(f"SSE {field} must not contain a newline")
    return value


@dataclass(frozen=True, slots=True)
class SseFrame:
    """One UTF-8 SSE frame, either a semantic event or heartbeat."""

    event_id: str | None = None
    event_type: str | None = None
    data: str | None = None
    comment: str | None = None
    retry_ms: int | None = None

    @classmethod
    def from_event(cls, event: ConversationEvent) -> "SseFrame":
        return cls(
            event_id=event.event_id,
            event_type=event.event_type,
            data=json.dumps(
                event.model_dump(mode="json"),
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        )

    @classmethod
    def heartbeat(cls) -> "SseFrame":
        return cls(comment="heartbeat")

    def encode(self) -> bytes:
        lines: list[str] = []
        if self.comment is not None:
            for line in self.comment.splitlines() or [""]:
                lines.append(f": {line}")
        if self.event_id is not None:
            lines.append(f"id: {_safe_sse_field(self.event_id, 'id')}")
        if self.event_type is not None:
            lines.append(f"event: {_safe_sse_field(self.event_type, 'event')}")
        if self.retry_ms is not None:
            if self.retry_ms < 0:
                raise ValueError("SSE retry must not be negative")
            lines.append(f"retry: {self.retry_ms}")
        if self.data is not None:
            lines.extend(f"data: {line}" for line in self.data.splitlines())
        return ("\n".join(lines) + "\n\n").encode("utf-8")


class ConversationSseService:
    """Streams durable events and treats the signal as an advisory wake-up."""

    def __init__(
        self,
        events: ConversationEventPort,
        signals: PublicEventSignalPort,
        *,
        page_size: int = 100,
        heartbeat_seconds: float = 15.0,
    ) -> None:
        if page_size < 1:
            raise ValueError("page_size must be positive")
        if heartbeat_seconds <= 0:
            raise ValueError("heartbeat_seconds must be positive")
        self._events = events
        self._signals = signals
        self._page_size = page_size
        self._heartbeat_seconds = heartbeat_seconds

    async def frames(
        self,
        actor: ActorContext,
        scope: Scope,
        conversation_id: OpaqueId,
        cursor: OpaqueId | None = None,
    ) -> AsyncIterator[SseFrame]:
        current_cursor = cursor
        while True:
            previous_cursor = current_cursor
            page = await self._events.list_after(
                actor,
                conversation_id,
                current_cursor,
                self._page_size,
            )
            for event in page.items:
                if event.conversation_id != conversation_id:
                    raise RuntimeError(
                        "event port returned a different conversation",
                    )
                current_cursor = event.event_id
                yield SseFrame.from_event(event)

            if page.has_more:
                next_cursor = page.next_cursor or current_cursor
                if next_cursor is None or next_cursor == previous_cursor:
                    raise RuntimeError("event page cursor did not advance")
                current_cursor = next_cursor
                continue

            signal = await self._signals.wait_for_signal(
                scope,
                conversation_id,
                self._heartbeat_seconds,
            )
            if signal is None:
                yield SseFrame.heartbeat()

    async def stream(
        self,
        actor: ActorContext,
        scope: Scope,
        conversation_id: OpaqueId,
        cursor: OpaqueId | None = None,
    ) -> AsyncIterator[bytes]:
        async for frame in self.frames(
            actor,
            scope,
            conversation_id,
            cursor,
        ):
            yield frame.encode()
