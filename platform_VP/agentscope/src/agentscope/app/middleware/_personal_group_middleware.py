"""Deliver registered group questions through the core's finalization gate."""

from ...event import ReplyEndEvent
from ...types import ReplyFinishedReason
from ._leader_evidence_middleware import LeaderEvidenceMiddleware


class PersonalGroupEvidenceMiddleware(LeaderEvidenceMiddleware):
    async def on_reply(self, agent, input_kwargs, next_handler):
        async for event in super().on_reply(agent, input_kwargs, next_handler):
            question = (await self._question() if isinstance(event, ReplyEndEvent)
                        and event.finished_reason == ReplyFinishedReason.COMPLETED else None)
            if question:
                for replacement in self._replacement(agent, event, question):
                    yield replacement
            else:
                yield event
