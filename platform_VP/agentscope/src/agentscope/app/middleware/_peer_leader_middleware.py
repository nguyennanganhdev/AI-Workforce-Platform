"""A personal-chat (peer) Leader answers once after it dispatches work."""

from ...message import HintBlock
from ...middleware import MiddlewareBase
from ...tool import ToolChoice
from ._leader_evidence_middleware import LeaderEvidenceMiddleware

PEER_DISPATCHED_HINT = (
    "The specialists you just started are working now and post their results "
    "in this chat themselves. Reply to the customer once, briefly and in their "
    "language: who is handling the request and that the answer will appear "
    "here. Do not message members, ask them for updates, accept their work or "
    "promise to follow up yourself."
)


class PeerLeaderDispatchMiddleware(MiddlewareBase):  # pylint: disable=abstract-method
    """Stop a peer-mode Leader from polling members it just dispatched.

    In personal chat the Leader has no wait gate: members publish their own
    results. Without this, a model kept calling TeamSay to remind a member
    that had not even started, then accepted its unreported work, and the
    member was put to sleep with nothing done.
    """

    async def on_reasoning(self, agent, input_kwargs, next_handler):
        if LeaderEvidenceMiddleware._expected_reports(agent):
            agent.state.append_context(agent.name, [HintBlock(hint=PEER_DISPATCHED_HINT)])
            input_kwargs = {**input_kwargs, "tool_choice": ToolChoice(mode="none")}
        async for event in next_handler(**input_kwargs):
            yield event

    async def get_middleware_key(self) -> str:
        return "peer_leader_dispatch"
