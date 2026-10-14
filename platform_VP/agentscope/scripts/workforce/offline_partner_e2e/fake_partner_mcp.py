"""A fake partner MCP (two Vinhomes-like tools) for the offline end-to-end check."""

import json
import sys

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

server = FastMCP("fake-partner")
CALLS = []


@server.tool(annotations=ToolAnnotations(readOnlyHint=True))
def vh_ticket_get(ticket_id: str) -> str:
    """Where the request stands."""
    CALLS.append(("vh_ticket_get", {"ticket_id": ticket_id}))
    print(json.dumps(CALLS[-1]), flush=True)
    return json.dumps({"ticket_id": ticket_id, "ticket_status": "open", "work_orders": []})


@server.tool(annotations=ToolAnnotations(readOnlyHint=False))
def vh_work_order_dispatch(ticket_id: str, description: str, client_reference: str) -> str:
    """Create the work and offer it to staff."""
    CALLS.append(("vh_work_order_dispatch", {"ticket_id": ticket_id, "client_reference": client_reference}))
    print(json.dumps(CALLS[-1]), flush=True)
    return json.dumps({"status": "pending", "external_job_id": "WO-" + client_reference[-6:], "offered_to": "Bình"})


if __name__ == "__main__":
    server.settings.host = "0.0.0.0"
    server.settings.port = int(sys.argv[1]) if len(sys.argv) > 1 else 18765
    server.settings.transport_security.enable_dns_rebinding_protection = False
    server.run(transport="streamable-http")
