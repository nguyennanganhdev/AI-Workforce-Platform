"""WorkerWatch: a specialist of a workflow that stops without reporting must not keep the workflow waiting.

The leader waits for every specialist it created to report (`settling.workers_pending`). A specialist whose
model fails, or that ends its run without TeamSay, never will, and AgentScope only tells the leader about
the first case. So when a run ends, a specialist that has never reported gets a report item saying so
(which ends the wait and shows in the leader's digest), and the leader is woken when it would otherwise not be.
A specialist that is waiting on a teammate (an open question) or that spoke to a peer is not silent.
"""
from __future__ import annotations

import asyncio
import logging

from agentscope.event import ReplyEndEvent, RequireUserConfirmEvent, ToolCallStartEvent
from agentscope.middleware import MiddlewareBase
from agentscope.types import ReplyFinishedReason

from ..casefile import build_view

log = logging.getLogger("awp.workforce")


class WorkerWatch(MiddlewareBase):
    def __init__(self, rt, binding) -> None:
        self.rt, self.b = rt, binding

    async def on_reply(self, agent, input_kwargs, next_handler):
        spoke = parked = failed = False
        try:
            async for item in next_handler(**input_kwargs):
                if isinstance(item, ToolCallStartEvent) and item.tool_call_name == "TeamSay":
                    spoke = True
                elif isinstance(item, RequireUserConfirmEvent):
                    parked = True
                elif isinstance(item, ReplyEndEvent) and item.finished_reason == ReplyFinishedReason.ERROR:
                    failed = True
                yield item
        except (asyncio.CancelledError, GeneratorExit):
            raise
        except BaseException:
            await self._ended(spoke, True)  # the model failed: raised here, not reported as an event
            raise
        if not parked:
            await self._ended(spoke, failed)

    async def _ended(self, spoke: bool, failed: bool) -> None:
        try:
            cases, cid, me = self.rt.cases, self.b.case_id, self.b.agent_name
            case = await cases.get_case(cid)
            if case is None or case["status"] != "open":
                return  # the workflow is over: nobody waits for this specialist any more
            view = build_view(await cases.items(cid))
            if me in view.reports:
                return
            waiting = any(me in (q.author, q.addressee) for q in [*view.open_questions(), *view.open_challenges()])
            if not failed and (spoke or waiting):
                return
            note = "stopped with an error and did not report" if failed else "finished without sending a report"
            await cases.add(cid, "report", me, {"summary": f"({me} {note}.)", "ended": True})
            leader = await self.rt.leader_name(cid)
            if leader and not failed:  # for a failure AgentScope wakes the leader itself
                await self.rt.deliver(cid, leader, f'ref="ended-{me}"', "platform",
                                      f"Team member {me!r} finished without reporting; there is nothing from it "
                                      "to wait for. Decide with what you have, and tell the resident only what is verified.")
        except Exception:
            log.exception("could not close out the run of %s", self.b.agent_name)
