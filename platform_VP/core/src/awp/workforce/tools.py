from agentscope.tool import ParamsBase
from pydantic import Field

from ..guard import check_text
from ..protocol.tools import _CaseTool, _err, _ok


class SayParams(ParamsBase):
    text: str = Field(min_length=1, max_length=12000)
    expects: str = Field(description="reply, confirmation, or none")
    cites: list[str] = Field(default_factory=list)


class CaseSay(_CaseTool):
    name = "CaseSay"
    description = "Send a grounded answer or question to the requester and park this turn. Never approves a tool."
    input_schema = SayParams.model_json_schema()

    async def call(self, text: str, expects: str, cites: list[str] | None = None):
        if (denied := self._leader_only()) or (denied := await self._closed()):
            return denied
        if expects not in ("reply", "confirmation", "none"):
            return _err("expects must be reply, confirmation or none")
        view = await self._view()
        sources, trusted, bad = self._sources(view, cites or [])
        problems = bad or check_text(text, sources, await self.rt.case_rules(self.b.case_id), trusted)
        if problems:
            return _err("Unsupported answer: " + "; ".join(problems))
        if expects != "reply":
            pending = await self._pending_team(view)
            pending.extend(c.ref for c in view.open_challenges())
            if pending:
                return _err("Wait for teammate answers/reports before presenting a result: " + ", ".join(pending))
        wf = await self.rt.workforce.workflow_of_case(self.b.case_id)
        from .lifecycle import complete
        accepted = await complete(self.rt.workforce, wf["id"], text, expects, fence=self.b.fence)
        return _ok("Message persisted. End your turn and wait.") if accepted else _err("Workflow is closed")
