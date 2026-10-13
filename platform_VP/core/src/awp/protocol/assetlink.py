"""CaseAssetLink: a short-lived link to an image the resident sent, for the argument of a partner tool (spec A3).

The leader never sees an image, only its id. When a partner's tool takes a photo (for the people who do the work), the
leader asks for a link here and puts it in that tool's argument. The link is made by the store, for one object and
for AWP_ASSET_URL_TTL seconds, and only for an image that was sent in this workflow's own conversation.

What is kept and what is not: the case file gets an evidence item that says a link was made and to which object,
WITHOUT the signature (the link in the file opens nothing). The link itself is in the tool's answer to the model and
nowhere else of ours; the resident is never shown one (speak.problems refuses a text that holds a link, and a
consent summary shows it unsigned: approvals.summary_of).
"""
from __future__ import annotations

from pydantic import Field

from agentscope.tool import ParamsBase, ToolChunk

from ..assets import StoreError, unsigned
from ..workforce.lookup import workflow_of_case
from ..workforce.uploads import of_workflow
from .tools import _CaseTool, _err, _ok


class _LinkP(ParamsBase):
    asset_id: str = Field(description="The id (ast_...) of an image the resident attached in this workflow.")


class CaseAssetLink(_CaseTool):
    name = "CaseAssetLink"
    description = ("Leader only. Get a short-lived link to an image the resident attached, to put into the argument of "
                   "a partner tool that takes a photo. The link is never for the resident: do not put it in CaseSay.")
    input_schema = _LinkP.model_json_schema()

    async def call(self, asset_id: str = "") -> ToolChunk:
        denied = self._leader_only() or await self._closed()
        if denied:
            return denied
        wf = await workflow_of_case(self.rt.db, self.b.case_id)
        store = getattr(self.rt, "assets", None)
        if wf is None or store is None:
            return _err("Images are not available here.")
        found = await of_workflow(self.rt.db, wf, [asset_id] if isinstance(asset_id, str) else [])
        if not found:
            return _err("No such image in this workflow. Use the asset id given with a message of the resident.")
        asset, ttl = found[0], int(self.rt.settings.asset_url_ttl)
        try:
            url = store.link(asset["object_key"], ttl)
        except StoreError:
            return _err("The link could not be made. You may try once more.")
        item = await self.rt.cases.add(self.b.case_id, "evidence", self.b.agent_name, {
            "tool": self.name, "input": asset["id"], "asset": asset["id"],
            "text": f"a link to image {asset['id']} ({asset['content_type']}, {asset['size']} bytes) was made for a partner "
                    f"tool, valid for {ttl} seconds: {unsigned(url)}"})
        return _ok(f"{url}\nValid for {ttl} seconds, for image {asset['id']}. Put it in the argument of the partner tool "
                   f"that needs the photo. It is not for the resident. [evidence {item.ref}]")
