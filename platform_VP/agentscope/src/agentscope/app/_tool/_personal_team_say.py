"""Translate manual-group review vocabulary to the core's bounded TeamSay."""

from ...message import TextBlock, ToolResultState
from ...tool import ToolChunk
from .._shared_context import SharedContextService
from .._team_turn import get_team_turn
from ..storage._utils import _ensure_team_members, _resolve_team_leader
from ._constants import HANDLE_LEN
from ._team_say import TeamSay
from ._team_tool_base import _TeamToolError


class PersonalTeamSay(TeamSay):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        properties = self.input_schema["properties"]
        properties["kind"]["enum"].append("review")
        properties["decision"] = {"type": "string", "enum": ["accept", "challenge", "stop"]}
        properties["report_type"] = {"type": "string", "enum": ["verified", "analysis"], "default": "verified"}
        properties["done_when"] = {"type": "string", "maxLength": 4000}

    async def __call__(self, content, kind="result", decision=None, report_type="verified", done_when="", **kwargs):
        try:
            team = await self._require_team()
        except _TeamToolError as exc:
            return ToolChunk(state=ToolResultState.ERROR, content=[TextBlock(text=str(exc))])
        if team.data.purpose != "platform_group" or report_type not in {"verified", "analysis"}:
            return ToolChunk(state=ToolResultState.ERROR, content=[TextBlock(text="Personal group context required")])
        if kind == "review":
            resolution = {"accept": "complete", "challenge": "verify", "stop": "stop"}.get(decision)
            if resolution is None:
                return ToolChunk(state=ToolResultState.ERROR, content=[TextBlock(text="Choose accept, challenge or stop")])
            kind = "handoff"
            kwargs["resolution"] = resolution
        if done_when:
            content += "\nAcceptance criteria: " + done_when
        if report_type == "analysis" and kind in {"answer", "result"}:
            notice = "[PROPOSAL / UNVERIFIED ANALYSIS - NOT OPERATIONAL FACT]\n"
            if not content.startswith(notice):
                content = notice + content
            kwargs["context_delta"] = None
        else:
            report_type = "verified"
        if kind in {"answer", "result", "error"} and not kwargs.get("to"):
            shared = self._shared_context or SharedContextService(self._storage, self._message_bus)
            record = await shared.storage.get_team_shared_context(self._user_id, team.id)
            task = record.state.tasks.get(record.state.active_task_id) if record else None
            waiting = [(sid, request_id) for sid, branch in (task.collaboration.items() if task else ())
                       if branch.customer_revision == task.latest_customer_revision
                       for request_id, provider in branch.waiting_for.items() if provider == self._session_id]
            if len(waiting) > 1:
                return ToolChunk(state=ToolResultState.ERROR, content=[TextBlock(text="Choose the requesting peer explicitly")])
            turn = await get_team_turn(self._message_bus, team.id, storage=shared.storage, user_id=self._user_id)
            recipient = waiting[0][0] if waiting else (turn.reply_owner_session_id if turn else team.session_id)
            if waiting:
                kwargs.setdefault("in_reply_to", waiting[0][1])
            leader = await _resolve_team_leader(self._storage, self._user_id, team)
            if leader is not None and recipient == leader.session_id:
                kwargs["to"] = leader.name
            else:
                for member in await _ensure_team_members(self._storage, self._user_id, team):
                    if member.session_id == recipient:
                        agent = await self._storage.get_agent(member.owner_id, member.agent_id)
                        if agent:
                            kwargs["to"] = agent.data.name + ("@" + agent.id[:HANDLE_LEN] if member.role == "invited" else "")
                        break
            if not kwargs.get("to"):
                return ToolChunk(state=ToolResultState.ERROR, content=[TextBlock(text="The requesting peer is unavailable")])
        return await super().__call__(content, kind=kind, report_type=report_type, **kwargs)
