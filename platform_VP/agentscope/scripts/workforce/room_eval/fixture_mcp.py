"""Partner MCP that answers the Vinhomes tools from scenario fixtures.

The room evaluation (run_eval.py) runs the real declaration and a real model
against this server instead of the partner's database: each ticket id is
``<scenario id>--<run>`` and the tools return that scenario's fixture data.
Every call is appended to the calls log (JSON lines) for the checks.

    python fixture_mcp.py scenarios.json ../../../.artifacts/room-eval/calls.jsonl 18766
"""

import json
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

SCENARIOS = {s["id"]: s for s in json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))["scenarios"]}
CALLS = Path(sys.argv[2])
CALLS.parent.mkdir(parents=True, exist_ok=True)
server = FastMCP("room-eval-partner")


def _fixture(ticket_id: str) -> dict:
    return SCENARIOS.get(ticket_id.split("--")[0], {}).get("fixtures", {})


def _log(tool: str, ticket_id: str, arguments: dict) -> None:
    with CALLS.open("a", encoding="utf-8") as calls:
        calls.write(json.dumps({"tool": tool, "ticket_id": ticket_id, "arguments": arguments}, ensure_ascii=False) + "\n")


def _answer(tool: str, ticket_id: str, arguments: dict, default: dict) -> str:
    _log(tool, ticket_id, arguments)
    return json.dumps(_fixture(ticket_id).get(tool, default), ensure_ascii=False)


@server.tool(annotations=ToolAnnotations(readOnlyHint=True))
def vh_ticket_get(ticket_id: str) -> str:
    """Where the request stands now: status, urgency, work orders, quote, acceptance report, photos."""
    return _answer("vh_ticket_get", ticket_id, {}, {"ticket_id": ticket_id, "status": "open", "work_orders": []})


@server.tool(annotations=ToolAnnotations(readOnlyHint=True))
def vh_knowledge_search(query: str, ticket_id: str = "") -> str:
    """Search the management board's documents (rules, fees, hours, hotlines) of the ticket's area."""
    return _answer("vh_knowledge_search", ticket_id, {"query": query}, {"results": []})


@server.tool(annotations=ToolAnnotations(readOnlyHint=True))
def vh_staff_available(ticket_id: str = "", skill: str = "") -> str:
    """Staff on duty who can take this ticket's work."""
    return _answer("vh_staff_available", ticket_id, {"skill": skill}, {"staff": []})


@server.tool(annotations=ToolAnnotations(readOnlyHint=False))
def vh_work_order_dispatch(
    ticket_id: str, description: str, client_reference: str, staff_id: str = "", appointment_at: str = "",
    expected_ticket_version: int | None = None,
) -> str:
    """Create the work and offer it to staff."""
    return _answer("vh_work_order_dispatch", ticket_id, {"description": description, "staff_id": staff_id},
                   {"status": "pending", "external_job_id": "WO-" + client_reference[-6:]})


@server.tool(annotations=ToolAnnotations(readOnlyHint=False))
def vh_work_order_reschedule(
    ticket_id: str, appointment_at: str, reason: str, client_reference: str, source_message_id: str = "",
    expected_ticket_version: int | None = None,
) -> str:
    """Move the appointment of the ticket's work order."""
    return _answer("vh_work_order_reschedule", ticket_id, {"appointment_at": appointment_at}, {"status": "rescheduled"})


@server.tool(annotations=ToolAnnotations(readOnlyHint=False))
def vh_ticket_cancel(
    ticket_id: str, reason: str, client_reference: str, source_message_id: str = "",
    expected_ticket_version: int | None = None,
) -> str:
    """Cancel the ticket at the resident's request."""
    return _answer("vh_ticket_cancel", ticket_id, {"reason": reason}, {"status": "cancelled"})


@server.tool(annotations=ToolAnnotations(readOnlyHint=False))
def vh_ticket_add_note(ticket_id: str, note: str, client_reference: str, expected_ticket_version: int | None = None) -> str:
    """Add a note for the staff on the ticket."""
    return _answer("vh_ticket_add_note", ticket_id, {"note": note}, {"status": "noted"})


if __name__ == "__main__":
    server.settings.host = "0.0.0.0"
    server.settings.port = int(sys.argv[3]) if len(sys.argv) > 3 else 18766
    server.settings.transport_security.enable_dns_rebinding_protection = False
    server.run(transport="streamable-http")
