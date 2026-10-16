"""Helpers for the partner-tool tests (slice T1): configure a route's MCP server and tools through the admin
API, a standard set of tools over the fake partner, and leader scripts that call them."""
from __future__ import annotations

from conftest import ADM
from enginekit import evidence_of
from fake_llm import Call
from partnerkit import SECRET, Partner
from scripts import say

SERVER = "p"


def lookup(name="partner_lookup", mcp_tool="lookup_ticket", **kw) -> dict:
    return {"name": name, "server": SERVER, "mcp_tool": mcp_tool, "kind": "lookup", "read_only": True, **kw}


WAIVER = "test fixture: this action is not about consent"


def waived(tool: dict) -> dict:
    """An action asks the resident's consent unless a recorded waiver says why not (M5). The fixtures that are not
    about consent declare that waiver here, in one place; a tool with `requires_consent=True` is left as it is."""
    if tool.get("kind") == "action" and not tool.get("requires_consent") and "consent_waiver" not in tool:
        return {**tool, "requires_consent": False, "consent_waiver": WAIVER}
    return tool


def action(name: str, mcp_tool: str, **kw) -> dict:
    return waived({"name": name, "server": SERVER, "mcp_tool": mcp_tool, "kind": "action", "tracking": "events",
                   "client_reference_arg": "client_reference", **kw})


STANDARD = [
    lookup(),
    action("partner_repair", "book_repair"),
    action("partner_hotel", "book_hotel", tracking="none"),
    action("partner_slow", "slow_action", tracking="none", call_timeout=1.5),
    action("partner_reject", "rejecting_action", tracking="none"),
    action("partner_broken", "broken_action", tracking="none"),
    action("partner_structured", "structured_only", tracking="none"),
    action("partner_nostatus", "no_status_action", tracking="none"),
    action("partner_repair_consent", "book_repair", requires_consent=True, consent_summary="Book a repair visit for {slot}"),
    action("partner_repair_q", "book_repair", tracking="status_query", status_tool="repair_status"),
    action("partner_hotel_keyed", "book_hotel_keyed", tracking="none", client_reference_arg=None,
           idempotency_arg="request_key"),
    action("partner_repair_keyed", "book_repair", idempotency_arg="client_reference"),
]
NAMES = [x["name"] for x in STANDARD]


def configure(w, partner: Partner, tools: list[dict] | None = None, route_id: str | None = None,
              headers: dict | None = None) -> str:
    """Point the world's route at the fake partner and declare its tools (all of STANDARD by default)."""
    rid = route_id or w.flow.route["route_id"]
    http = w.env.http
    r = http.put(f"/platform/v1/wf/routes/{rid}/mcp", headers=ADM, json={"servers": [
        {"name": SERVER, "url": partner.url, "headers": headers if headers is not None else {"Authorization": f"Bearer {SECRET}"}}]})
    assert r.status_code == 200, r.text
    r = http.put(f"/platform/v1/wf/routes/{rid}/tools", headers=ADM, json={"tools": STANDARD if tools is None else tools})
    assert r.status_code == 200, r.text
    return rid


TOOLS = dict(leader_tools=NAMES, worker_tools=NAMES)
SETTINGS = dict(mcp_allow_private=True)


def act(tool: str, args: dict, text: str, expects: str = "none", cite: bool = True):
    """The leader calls `tool` once, then says `text`."""
    def script(c: Call):
        turn = c.after_user()
        if turn.called(tool) == 0:
            return [(tool, args)]
        if turn.called("CaseSay") == 0:
            ev = evidence_of(" ".join(turn.results(tool)))
            return say(text, expects, ev[:1] if cite else [])
        return "Said."
    return script


def tool_texts() -> list[str]:
    """Every tool result the scripted model was shown, in the longest request it received (its whole context)."""
    from fake_llm import CALLS
    best = max((c.get("shape", []) for c in CALLS), key=len, default=[])
    return [text for role, text, _ in best if role == "tool"]


def wait_for(w, query: str, args=(), timeout: float = 20.0, what: str = "rows"):
    return w.wait(lambda: w.sql(query, args), timeout, what)


def ops(w, workflow_id: str | None = None) -> list[dict]:
    q = ("select id, workflow_id, tool_name, status, normalized_status, client_reference, external_job_id, args_hash "
         "from wf_operations" + (" where workflow_id=?" if workflow_id else "") + " order by created_at")
    keys = ("id", "workflow_id", "tool", "status", "partner_status", "reference", "job", "args_hash")
    return [dict(zip(keys, r)) for r in w.sql(q, (workflow_id,) if workflow_id else ())]


def event_types(w, conv: str) -> list[str]:
    return [e["event_type"] for e in w.flow.history(conv, limit=500).json()["items"]]




def quiet_leader(c: Call):
    """Says one thing and rests: for tests that drive the tools by hand."""
    return say("Noted.", "reply") if c.after_user().called("CaseSay") == 0 else "Said."


def workflow_row(w) -> dict:
    """The workflow of a world that has one (as a dict, like the agent side reads it)."""
    from awp.workforce.lookup import workflow_of_case
    case = w.sql("select case_id from wf_workflows")[0][0]
    return w.run(lambda: workflow_of_case(w.rt.db, case))


def tools_of(w, patterns=("*",)) -> dict:
    """The PartnerTools a fresh agent of the workflow would be given, by name. Built on the app's loop."""
    from awp.workforce.partner_tools import partner_tools
    wf = workflow_row(w)
    return {t.name: t for t in w.run(lambda: partner_tools(w.rt, wf, list(patterns)))}


class Crash(BaseException):
    """The process dies here: not an Exception, so no handler of the tool body may catch it."""


def crash_at(monkeypatch, module, name: str, after: bool = False):
    """Replace `module.name` so that it raises Crash (after=True: after doing its work)."""
    real = getattr(module, name)

    async def dies(*a, **k):
        if after:
            await real(*a, **k)
        raise Crash(name)

    monkeypatch.setattr(module, name, dies)
    return real
