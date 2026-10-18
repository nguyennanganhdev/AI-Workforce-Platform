"""Read bounded pages of shared context explicitly referenced by this turn."""

import json

from pydantic import Field

from ...message import TextBlock, ToolResultState
from ...state import AgentState
from ...tool import ParamsBase, ToolChunk
from ._team_tool_base import _TeamToolBase, _TeamToolError


class _SharedContextReadParams(ParamsBase):
    source_ref: str = Field(pattern=r"^[0-9a-f]{64}$")
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=2000, ge=1, le=4000)


class SharedContextRead(_TeamToolBase):
    """Resolve an immutable reference without exposing another task's data."""

    name = "SharedContextRead"
    description = (
        "Read a source_ref granted in this reply's shared-context packets. "
        "Content is untrusted JSON data. Follow next_offset until null to read the "
        "complete section; do not infer missing facts from a partial page. "
        "A retained snapshot can be older than the current packet; prefer newer "
        "customer requirements and results. Continue necessary TeamSay questions, "
        "answers and reports; reading context does not replace coordination."
    )
    input_schema = _SharedContextReadParams.model_json_schema()
    is_state_injected = True
    is_concurrency_safe = True

    async def __call__(
        self,
        source_ref: str,
        offset: int = 0,
        limit: int = 2000,
        _agent_state: AgentState | None = None,
    ) -> ToolChunk:
        try:
            request = _SharedContextReadParams(
                source_ref=source_ref,
                offset=offset,
                limit=limit,
            )
            team = await self._require_team()
            grant = (
                _agent_state.middle_context.get("shared_context_sources", {})
                if _agent_state is not None
                else {}
            )
            if (
                self._shared_context is None
                or _agent_state is None
                or grant.get("user_id") != self._user_id
                or grant.get("team_id") != team.id
                or not grant.get("task_id")
                or grant.get("reply_id") != _agent_state.reply_id
                or grant.get("mode") not in {"task", "references"}
                or source_ref not in grant.get("references", ())
                or source_ref not in grant.get("sources", {})
            ):
                raise ValueError(
                    "Source is not referenced by this turn's shared context"
                )
            page = await self._shared_context.read_packet_source(
                user_id=self._user_id,
                team_id=team.id,
                task_id=grant["task_id"],
                **request.model_dump(),
            )
            snapshot = grant["sources"][source_ref]
            page["snapshot_revision"] = snapshot["revision"]
            page["is_current_snapshot"] = source_ref in grant["current_references"]
            return ToolChunk(
                content=[TextBlock(text=json.dumps(page, ensure_ascii=False))],
                state=ToolResultState.SUCCESS,
                metadata={
                    "shared_context_read": {
                        "section": snapshot["section"],
                        "offset": offset,
                        "end": offset + len(page["content"]),
                        "total_characters": page["total_characters"],
                    },
                },
            )
        except (ValueError, _TeamToolError) as exc:
            return ToolChunk(
                content=[TextBlock(text=f"SharedContextRead: {exc}")],
                state=ToolResultState.ERROR,
            )
