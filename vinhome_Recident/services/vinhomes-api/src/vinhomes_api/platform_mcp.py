"""The tools the platform's coordinator calls, served at /mcp (docs/domain/NOI_WORKFORCE_V1.md section 6).

Streamable HTTP without sessions: the platform opens a new one for every call. Every request must carry
`Authorization: Bearer <VINHOMES_API_PLATFORM_MCP_TOKEN>`. The path exists only while the bridge is on and has a
token. A tool is a thin shell: platform_work does the work, in one transaction scoped to the configured tenant.
An answer is one line of text: JSON, or for a look-up that was refused the reason in plain words.
"""

import hmac
import json
import logging
import os
from contextlib import asynccontextmanager
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from pydantic import Field
from sqlalchemy import text
from starlette.responses import JSONResponse
from starlette.routing import Route

from . import platform_work as work
from .platform import enabled

log = logging.getLogger("vinhomes_api.platform_mcp")
READ = ToolAnnotations(readOnlyHint=True)
Ticket = Annotated[str, Field(description="The ticket_id line of the hand-over message, copied exactly.")]
Reference = Annotated[str, Field(description="Filled in by the platform; identifies this call so it is done once.")]
BUSY = "Hệ thống Vinhomes đang trục trặc, chưa thực hiện được. Không có gì thay đổi."


def build(app) -> FastMCP:
    async def run(action: bool, call, *args) -> str:
        try:
            async with app.state.engine.begin() as db:
                await db.execute(text("select set_config('app.tenant_id',:tenant,true)"), {"tenant": str(app.state.settings.tenant_id)})
                answer = await call(db, *args)
        except work.Refused as no:
            return str(no)
        except Exception:  # noqa: BLE001 - the coordinator gets words, never a stack trace; the transaction was rolled back
            log.exception("Platform tool %s failed", call.__name__)
            return json.dumps({"status": "failed", "reason": BUSY}, ensure_ascii=False) if action else BUSY
        return json.dumps(answer, ensure_ascii=False, default=str)

    # Answers as plain JSON bodies, and no check of the Host header: the token is the protection, and the
    # platform reaches this server under whatever name its network gives it.
    mcp = FastMCP("vinhomes", stateless_http=True, json_response=True, log_level="WARNING",
                  transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False))

    @mcp.tool(annotations=READ)
    async def vh_ticket_get(ticket_id: Ticket) -> str:
        """Where the request stands: ticket_status, how urgent (is_emergency, severity), the work given to staff (who
        holds it, appointment, progress times), a quote waiting for the resident's own answer (items, total), the
        acceptance report (who reported, when, note), photo counts and the milestones so far. Times are Vietnam time."""
        return await run(False, work.ticket_get, ticket_id)

    @mcp.tool(annotations=READ)
    async def vh_resident_context(ticket_id: Ticket) -> str:
        """Who sent the request and for which home: name, relation to the home, unit, building, zone."""
        return await run(False, work.resident_context, ticket_id)

    @mcp.tool(annotations=READ)
    async def vh_knowledge_search(ticket_id: Ticket, query: Annotated[str, Field(description="What to look for, in Vietnamese.")]) -> str:
        """Passages of the documents that apply to the resident's zone and building (rules, fees, opening hours,
        phone numbers), each with the name of its document. Returns passages, not an answer."""
        return await run(False, work.knowledge_search, ticket_id, query)

    @mcp.tool(annotations=READ)
    async def vh_home_rules(ticket_id: Ticket) -> str:
        """The limits of the home's zone: visitors, access cards, amenity payment hold."""
        return await run(False, work.rules, ticket_id)

    @mcp.tool(annotations=READ)
    async def vh_debit_notes(ticket_id: Ticket, view: Annotated[str, Field(
            description="balance (what is owed in total), or the debit notes: open, paid, all.")] = "balance") -> str:
        """What the home owes. Only when the sender is its owner or tenant."""
        return await run(False, work.debts, ticket_id, view)

    @mcp.tool(annotations=READ)
    async def vh_staff_available(ticket_id: Ticket) -> str:
        """Staff with the specialty the request needs who are on shift now and have room for a job."""
        return await run(False, work.staff_available, ticket_id)

    @mcp.tool()
    async def vh_work_order_dispatch(
            ticket_id: Ticket, client_reference: Reference,
            description: Annotated[str, Field(description="What has to be done and where in the home. No phone numbers.")],
            staff_id: Annotated[str | None, Field(description="A staff_id from vh_staff_available, only to choose that person.")] = None,
            appointment_at: Annotated[str | None, Field(
                description="Only when the resident named a time: ISO 8601, e.g. 2026-10-12T09:00:00+07:00.")] = None) -> str:
        """Create the work and offer it to staff. status pending: offered, waiting for someone to accept. queued: nobody
        is free, it is offered automatically later. failed: not dispatched, see reason. Progress follows as events."""
        return await run(True, work.dispatch, ticket_id, description, staff_id, appointment_at, client_reference)

    @mcp.tool()
    async def vh_work_order_reschedule(
            ticket_id: Ticket, client_reference: Reference,
            appointment_at: Annotated[str, Field(description="The new time: ISO 8601, e.g. 2026-10-12T09:00:00+07:00.")],
            reason: Annotated[str, Field(description="Why the time changes.")] = "") -> str:
        """Move the appointment of the work that has not started. failed once the staff member is on the way."""
        return await run(True, work.reschedule, ticket_id, appointment_at, reason, client_reference)

    @mcp.tool()
    async def vh_ticket_cancel(ticket_id: Ticket, client_reference: Reference,
                               reason: Annotated[str, Field(description="Why the resident cancels.")]) -> str:
        """Cancel the request and its unfinished work at the resident's wish. failed once staff arrived or started."""
        return await run(True, work.cancel, ticket_id, reason, client_reference)

    @mcp.tool()
    async def vh_ticket_add_note(ticket_id: Ticket, client_reference: Reference,
                                 note: Annotated[str, Field(description="What the resident added, for the staff to read.")]) -> str:
        """Add to the request something the resident said that the staff should know."""
        return await run(True, work.add_note, ticket_id, note, client_reference)

    return mcp


def mount(app) -> None:
    """Serve the tools at /mcp when the bridge is on and has a token; otherwise the path does not exist."""
    token = os.getenv("VINHOMES_API_PLATFORM_MCP_TOKEN", "").strip()
    if not enabled() or not token:
        return
    if len(token) < 32:
        raise ValueError("VINHOMES_API_PLATFORM_MCP_TOKEN requires at least 32 characters")
    app.state.platform_tools = mcp = build(app)
    mcp.streamable_http_app()  # creates the session manager
    # A route of the API itself, at exactly /mcp: the platform follows no redirect.
    app.router.routes.append(Route("/mcp", Guarded(mcp, b"Bearer " + token.encode())))


class Guarded:
    """The MCP endpoint behind the token: checked on every request, in constant time."""

    def __init__(self, mcp: FastMCP, expected: bytes):
        self.mcp, self.expected = mcp, expected

    async def __call__(self, scope, receive, send):
        given = dict(scope["headers"]).get(b"authorization", b"")
        if not hmac.compare_digest(given, self.expected):
            await JSONResponse({"detail": "Unauthorized"}, 401, {"WWW-Authenticate": "Bearer"})(scope, receive, send)
            return
        await self.mcp.session_manager.handle_request(scope, receive, send)


@asynccontextmanager
async def serving(app):
    """Keeps the tool sessions running for the life of the API."""
    mcp = getattr(app.state, "platform_tools", None)
    if mcp is None:
        yield
        return
    async with mcp.session_manager.run():
        yield
