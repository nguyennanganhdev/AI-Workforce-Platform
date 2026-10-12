"""TurnRecorder: one `wf_turns` row for every run of the leader's session, whoever started it.

A run starts from a message we sent (its `Msg.id` is the job's id, which is how the engine knows the
message arrived), or from AgentScope itself (a worker's report wakes the leader: no job). The recorder
only writes; settling a workflow waits until the session is idle (the engine does that, not this hook).

How a turn ends (P0 findings): a normal end is a ReplyEndEvent; a turn parked on a permission has a
RequireUserConfirmEvent and no ReplyEndEvent; a failing model is an exception raised inside `on_reply`;
an interrupt is a ReplyEndEvent(interrupted). The recorder never changes the stream and never lets its
own failure reach the reply.
"""
from __future__ import annotations

import asyncio
import logging

from agentscope.event import ReplyEndEvent, RequireExternalExecutionEvent, RequireUserConfirmEvent
from agentscope.message import Msg
from agentscope.middleware import MiddlewareBase
from sqlalchemy import insert, update
from sqlalchemy.exc import IntegrityError

from . import tables as t
from .common import now
from .tables import new_id

log = logging.getLogger("awp.workforce")


def job_of(msg_id: str | None) -> str | None:
    """The job a message belongs to: its id, or `<job id>.<attempt>` for a repeated attempt."""
    if msg_id and msg_id.startswith("job_"):
        return msg_id.split(".", 1)[0]
    return None


def status_of(reason: str | None, parked: bool, left: str) -> str:
    if parked:
        return "parked"
    if left == "error" or reason == "error":
        return "error"
    if left == "interrupted" or reason == "interrupted":
        return "interrupted"
    return "completed"


class TurnRecorder(MiddlewareBase):
    def __init__(self, rt, workflow_id: str) -> None:
        self.rt, self.workflow_id = rt, workflow_id

    async def on_reply(self, agent, input_kwargs, next_handler):
        turn = await self._begin(input_kwargs.get("inputs"))
        reason, parked, left = None, False, "end"
        try:
            async for item in next_handler(**input_kwargs):
                if isinstance(item, (RequireUserConfirmEvent, RequireExternalExecutionEvent)):
                    parked = True
                elif isinstance(item, ReplyEndEvent):
                    reason = str(getattr(item.finished_reason, "value", item.finished_reason))
                yield item
        except asyncio.CancelledError:
            left = "interrupted"
            raise
        except GeneratorExit:
            left = "interrupted"
            raise
        except BaseException:  # a model failure is raised here, not reported as an event
            left = "error"
            raise
        finally:
            await self._end(turn, status_of(reason, parked, left))

    async def _begin(self, inputs) -> str | None:
        """The row that says the turn started. The engine takes this row for the acknowledgement of its message
        and sends the message again without it, so a failed insert is tried again before it is given up."""
        try:
            first = inputs[0] if isinstance(inputs, list) and inputs else inputs
            if isinstance(first, Msg):
                trigger, msg_id = "message", first.id
            elif inputs is None:
                trigger, msg_id = "continue", None
            else:  # a resume event of ours (UserConfirmResultEvent, UserInterruptEvent) carries its own id
                trigger, msg_id = type(inputs).__name__.lower()[:12], getattr(inputs, "id", None)
                msg_id = str(msg_id)[:80] if str(msg_id).startswith(("resume_", "job_")) else None
        except Exception:
            log.exception("could not record a turn of workflow %s", self.workflow_id)
            return None
        turn_id = new_id("turn")
        for attempt in range(3):
            try:
                await self._insert(turn_id, trigger, msg_id)
                return turn_id
            except IntegrityError:
                return turn_id  # an earlier try did commit
            except Exception:
                log.exception("could not record a turn of workflow %s (try %s)", self.workflow_id, attempt + 1)
                await asyncio.sleep(0.05 * (attempt + 1))
        return None

    async def _insert(self, turn_id: str, trigger: str, msg_id: str | None) -> None:
        async with self.rt.db.engine.begin() as conn:
            await conn.execute(insert(t.turns).values(
                id=turn_id, workflow_id=self.workflow_id, job_id=job_of(msg_id), trigger=trigger,
                msg_id=msg_id, status="running", started_at=now()))

    async def _end(self, turn_id: str | None, status: str) -> None:
        """Shielded: the run's own task may be cancelled right here, and the row must still close."""
        async def write() -> None:
            if turn_id is not None:
                async with self.rt.db.engine.begin() as conn:
                    await conn.execute(update(t.turns).where(t.turns.c.id == turn_id).values(
                        status=status, ended_at=now()))
        try:
            await asyncio.shield(write())
        except BaseException as e:  # noqa: BLE001 - the reply goes on whatever happened here
            if isinstance(e, asyncio.CancelledError):
                log.warning("turn %s: closing the record was cancelled", turn_id)
            else:
                log.exception("could not close turn %s", turn_id)
        try:
            if self.rt.turn_hook is not None:
                self.rt.turn_hook(self.workflow_id)
        except Exception:
            log.exception("turn hook failed")
