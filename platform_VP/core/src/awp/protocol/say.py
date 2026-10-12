"""CaseSay: the leader's only voice to the resident of a workflow.

The text goes through the same grounding guard as a final answer (figures and codes must come from the
cited items; the route's phrase rules apply), and only then is it written, as a message with the event
that announces it. A refusal leaves nothing behind: the resident never sees an ungrounded figure.
"""
from __future__ import annotations

from pydantic import Field

from agentscope.tool import ParamsBase, ToolChunk

from ..workforce.lookup import workflow_of_case
from ..workforce.speak import EXPECTS, MAX_SAYS, BadText, chain_says, checked, problems, publish
from ..workforce.workflows import IllegalTransition
from .tools import _CaseTool, _err, _ok


class _SayP(ParamsBase):
    text: str = Field(description="What the resident will read. Figures, dates and codes must come from cited items.")
    expects: str = Field(default="none", description='"reply" if you need their answer, "confirmation" if you '
                                                     'ask them to confirm a result, "none" otherwise.')
    cites: list[str] = Field(default_factory=list, description="Evidence/fact ids (E.., F..) the text rests on.")


class CaseSay(_CaseTool):
    name = "CaseSay"
    description = ("Leader only. Say something to the resident; this is the only way they read anything from you. "
                   "Every figure, date and code must appear in the items you cite. Set expects to reply when you "
                   "need their answer, confirmation when you ask them to confirm a result.")
    input_schema = _SayP.model_json_schema()

    async def call(self, text: str, expects: str = "none", cites: list[str] | None = None) -> ToolChunk:
        denied = self._leader_only()
        if denied:
            return denied
        wf = await workflow_of_case(self.rt.db, self.b.case_id)
        if wf is None:
            return _err("CaseSay works only inside a workflow.")
        if expects not in EXPECTS:
            return _err(f"expects must be one of {EXPECTS}.")
        limit = self.rt.settings.wf_text_limit
        try:
            text = checked(text, limit)
        except BadText as e:
            return _err(str(e))
        if (closed := await self._closed()):
            return closed
        said = await chain_says(self.rt.db, wf["id"])
        if len(said) >= MAX_SAYS:
            return _err(f"You have already sent {len(said)} messages for this message of the resident. "
                        "Stop: let them read and answer.")
        if text in said:
            return _err("You already said exactly this to the resident. Say something new or stop.")
        sources, trusted, bad = self._sources(await self._view(), cites or [])
        if bad:
            return _err(f"Cannot cite: {', '.join(bad)}.")
        refused = problems(text, sources, await self._rules(wf), trusted, getattr(self.rt, "assets", None))
        if refused:
            return _err("Not sent, the resident has seen nothing: " + "; ".join(refused)
                        + ". Cite the item that states it, or leave it out.")
        try:
            sent = await publish(self.rt.db, wf["id"], text, expects=expects, limit=limit)
        except IllegalTransition:
            return _err("The workflow is closed or blocked. Stop working on it.")
        except BadText as e:
            return _err(str(e))
        return _ok(f"Sent to the resident as {sent['message_id']}" + (f"; you expect their {expects}." if expects != "none" else "."))
