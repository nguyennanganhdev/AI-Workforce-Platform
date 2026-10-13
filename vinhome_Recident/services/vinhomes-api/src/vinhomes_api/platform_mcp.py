"""The tools the platform's coordinator calls, served at /mcp (docs/domain/NOI_WORKFORCE_V1.md section 6).

Streamable HTTP without sessions: the platform opens a new one for every call. Every request must carry
`Authorization: Bearer <VINHOMES_API_PLATFORM_MCP_TOKEN>`. A configured token enables discovery independently of
the outbound platform bridge. A tool is a thin shell: platform_work does the work, in one transaction scoped to the configured tenant.
Results expose structured domain fields and the same JSON as text for compatible clients.
"""

import hmac
import json
import logging
import os
import asyncio
import time
from collections import OrderedDict, deque
from uuid import uuid4
from urllib.parse import urlsplit
from contextlib import asynccontextmanager
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations, CallToolResult, TextContent
from pydantic import Field, BaseModel, ConfigDict
from sqlalchemy import text
from starlette.responses import JSONResponse
from starlette.routing import Route

from . import platform_work as work
from .platform_access import ACCESS,find_grant,authorize

log = logging.getLogger("vinhomes_api.platform_mcp")
READ = ToolAnnotations(readOnlyHint=True)
Ticket = Annotated[str, Field(description="The ticket_id line of the hand-over message, copied exactly.")]
Reference = Annotated[str, Field(min_length=8,max_length=120,description="Filled in by the platform; identifies this call so it is done once.")]
BUSY = "Chưa xác định được kết quả. Đối soát bằng cách gửi lại cùng client_reference và nội dung; không tạo reference mới."


class ToolFailure(BaseModel):
    code: str
    message: str
    retryable: bool


class Confirmation(BaseModel):
    result_published: bool
    waiting_for_resident: bool
    resident_accepted: bool
    ticket_closed: bool


class WorkSnapshot(BaseModel):
    model_config=ConfigDict(extra='allow')
    work_order_id: str
    version: int
    work_status: str
    description: str


class ActionPermission(BaseModel):
    allowed: bool
    blocked_reason: str | None


class TicketPolicy(BaseModel):
    version: str
    requires_plan: bool
    actions: dict[str,ActionPermission]
    resident_approval_required_for: list[str]
    security_dispatch: str


class HistoryPage(BaseModel):
    next_before_seq: int | None
    limit: int


class TicketSla(BaseModel):
    response_due_at: str | None
    resolution_due_at: str | None
    resolution_overdue: bool


class ToolReply(BaseModel):
    model_config=ConfigDict(extra='allow')
    schema_version: str
    correlation_id: str
    status: str | None=None
    ticket_id: str | None=None
    ticket_version: int | None=None
    ticket_status: str | None=None
    confirmation: Confirmation | None=None
    work_orders: list[WorkSnapshot] | None=None
    policy: TicketPolicy | None=None
    sla: TicketSla | None=None
    history_page: HistoryPage | None=None
    error: ToolFailure | None=None


def build(app) -> FastMCP:
    async def run(action: bool, tool: str, call, *args):
        correlation=str(uuid4())
        try:
            async with asyncio.timeout(7):
                async with app.state.engine.begin() as db:
                    await db.execute(text("select set_config('app.tenant_id',:tenant,true)"), {"tenant": str(app.state.settings.tenant_id)})
                    await authorize(db,tool,args[0])
                    answer = await call(db, *args)
        except work.Refused as no:
            answer={'status':'failed','reason':str(no),'code':no.code,'retryable':False}
        except Exception:  # noqa: BLE001 - commit acknowledgement can be lost; never promise no side effect
            log.exception("Platform tool %s failed", call.__name__)
            answer={'status':'failed','reason':BUSY if action else 'Không đọc được dữ liệu. Vui lòng thử lại.',
                    'code':'OUTCOME_UNKNOWN' if action else 'TEMPORARILY_UNAVAILABLE','retryable':True}
        failed=answer.get('status')=='failed'
        if failed:
            answer={**answer,'error':{'code':answer.get('code','BUSINESS_RULE_REFUSED'),'message':answer.get('reason','Không thực hiện được.'),'retryable':answer.get('retryable',False)}}
        answer={**answer,'schema_version':'vinhomes-mcp-v2','correlation_id':correlation}
        encoded=json.dumps(answer,ensure_ascii=False,default=str)
        if len(encoded.encode())>256*1024:
            answer={'schema_version':'vinhomes-mcp-v2','correlation_id':correlation,'status':'failed',
                    'error':{'code':'OUTPUT_LIMIT','message':'Kết quả vượt giới hạn; đọc từng trang lịch sử.','retryable':False}}
            failed=True; encoded=json.dumps(answer,ensure_ascii=False)
        log.info('MCP call tool=%s grant=%s correlation=%s outcome=%s',tool,(ACCESS.get() or {}).get('id'),correlation,'failed' if failed else 'ok')
        return CallToolResult(content=[TextContent(type='text',text=encoded)],structuredContent=json.loads(encoded),isError=failed)

    origins=[v.strip().rstrip('/') for v in os.getenv('VINHOMES_API_ALLOWED_ORIGINS','').split(',') if v.strip()]
    hosts=['127.0.0.1:*','localhost:*']+[urlsplit(v).netloc for v in origins if urlsplit(v).netloc]
    hosts += [v.strip() for v in os.getenv('VINHOMES_API_MCP_ALLOWED_HOSTS','').split(',') if v.strip()]
    mcp = FastMCP("vinhomes", stateless_http=True, json_response=True, log_level="WARNING",
                  transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=True,allowed_hosts=hosts,
                    allowed_origins=origins+['http://127.0.0.1:*','http://localhost:*']))

    @mcp.tool(annotations=READ)
    async def vh_ticket_get(ticket_id: Ticket,history_before_seq: Annotated[int | None,Field(ge=1,description='next_before_seq from history_page, only to read older milestones.')]=None) -> ToolReply:
        """Where the request stands: ticket_status, how urgent (is_emergency, severity), the work given to staff (who
        holds it, appointment, progress times), a quote waiting for the resident's own answer (items, total), the
        acceptance report (who reported, when, note), photo counts and the milestones so far. Times are Vietnam time."""
        return await run(False,'vh_ticket_get',work.ticket_get,ticket_id,history_before_seq)

    @mcp.tool(annotations=READ)
    async def vh_knowledge_search(ticket_id: Ticket, query: Annotated[str, Field(min_length=1,max_length=1000,description="What to look for, in Vietnamese.")]) -> ToolReply:
        """Passages of the documents that apply to the resident's zone and building (rules, fees, opening hours,
        phone numbers), each with the name of its document. Returns passages, not an answer."""
        return await run(False,'vh_knowledge_search',work.knowledge_search,ticket_id,query)

    @mcp.tool(annotations=READ)
    async def vh_staff_available(ticket_id: Ticket,appointment_at: str | None=None) -> ToolReply:
        """Staff with the specialty the request needs who are on shift now and have room for a job."""
        return await run(False,'vh_staff_available',work.staff_available,ticket_id,appointment_at)

    @mcp.tool()
    async def vh_work_order_dispatch(
            ticket_id: Ticket, client_reference: Reference,
            description: Annotated[str, Field(min_length=1,max_length=2000,description="What has to be done and where in the home. No phone numbers.")],
            staff_id: Annotated[str | None, Field(description="A staff_id from vh_staff_available, only to choose that person.")] = None,
            appointment_at: Annotated[str | None, Field(
                description="Only when the resident named a time: ISO 8601, e.g. 2026-10-12T09:00:00+07:00.")] = None,
            expected_ticket_version: Annotated[int | None,Field(ge=0)]=None) -> ToolReply:
        """Create the work and offer it to staff. status pending: offered, waiting for someone to accept. queued: nobody
        is free, it is offered automatically later. failed: not dispatched, see reason. Progress follows as events."""
        return await run(True,'vh_work_order_dispatch',work.dispatch,ticket_id,description,staff_id,appointment_at,client_reference,expected_ticket_version)

    @mcp.tool()
    async def vh_work_order_reschedule(
            ticket_id: Ticket, client_reference: Reference,
            appointment_at: Annotated[str, Field(description="The new time: ISO 8601, e.g. 2026-10-12T09:00:00+07:00.")],
            reason: Annotated[str, Field(max_length=2000,description="Why the time changes.")] = "",
            expected_ticket_version: Annotated[int | None,Field(ge=0)]=None,source_message_id: str | None=None) -> ToolReply:
        """Move the appointment of the work that has not started. failed once the staff member is on the way."""
        return await run(True,'vh_work_order_reschedule',work.reschedule,ticket_id,appointment_at,reason,client_reference,expected_ticket_version,source_message_id)

    @mcp.tool()
    async def vh_ticket_cancel(ticket_id: Ticket, client_reference: Reference,
                               reason: Annotated[str, Field(min_length=1,max_length=2000,description="Why the resident cancels.")],
                               expected_ticket_version: Annotated[int | None,Field(ge=0)]=None,source_message_id: str | None=None) -> ToolReply:
        """Cancel the request and its unfinished work at the resident's wish. failed once staff arrived or started."""
        return await run(True,'vh_ticket_cancel',work.cancel,ticket_id,reason,client_reference,expected_ticket_version,source_message_id)

    @mcp.tool()
    async def vh_ticket_add_note(ticket_id: Ticket, client_reference: Reference,
                                 note: Annotated[str, Field(min_length=1,max_length=2000,description="What the resident added, for the staff to read.")],
                                 expected_ticket_version: Annotated[int | None,Field(ge=0)]=None) -> ToolReply:
        """Add to the request something the resident said that the staff should know."""
        return await run(True,'vh_ticket_add_note',work.add_note,ticket_id,note,client_reference,expected_ticket_version)

    return mcp


def mount(app) -> None:
    """Serve /mcp with a token, including during onboarding before the outbound bridge is configured."""
    token = os.getenv("VINHOMES_API_PLATFORM_MCP_TOKEN", "").strip()
    if not token:
        return
    if len(token) < 32:
        raise ValueError("VINHOMES_API_PLATFORM_MCP_TOKEN requires at least 32 characters")
    app.state.platform_tools = mcp = build(app)
    mcp.streamable_http_app()  # creates the session manager
    # A route of the API itself, at exactly /mcp: the platform follows no redirect.
    app.router.routes.append(Route("/mcp", Guarded(app,mcp, b"Bearer " + token.encode())))


class Guarded:
    """The MCP endpoint behind the token: checked on every request, in constant time."""

    def __init__(self,app,mcp: FastMCP,expected: bytes):
        self.app,self.mcp,self.expected=app,mcp,expected
        self.rate=OrderedDict()

    async def __call__(self, scope, receive, send):
        given = dict(scope["headers"]).get(b"authorization", b"")
        access=None
        if not hmac.compare_digest(given,self.expected):
            if given.startswith(b'Bearer vhm_') and getattr(self.app.state,'engine',None) is not None:
                token=given[7:].decode('utf-8',errors='replace')
                async with self.app.state.engine.begin() as db:
                    await db.execute(text("select set_config('app.tenant_id',:tenant,true)"),{'tenant':str(self.app.state.settings.tenant_id)})
                    access=await find_grant(db,token)
                if access:
                    access={**access,'token':token}
            if access is None:
                await JSONResponse({'detail':'Unauthorized'},401,{'WWW-Authenticate':'Bearer'})(scope,receive,send)
                return
        key=str(access['id']) if access else 'discovery:'+str((scope.get('client') or ('unknown',0))[0])
        now=time.monotonic(); entries=self.rate.setdefault(key,deque())
        while entries and entries[0]<now-60: entries.popleft()
        if len(entries)>=120:
            await JSONResponse({'detail':'Rate limited'},429,{'Retry-After':'60'})(scope,receive,send); return
        entries.append(now); self.rate.move_to_end(key)
        if len(self.rate)>4096:self.rate.popitem(last=False)
        if scope['method']=='POST':
            body=b''
            while True:
                message=await receive()
                if message['type']=='http.disconnect': return
                body+=message.get('body',b'')
                if len(body)>256*1024:
                    await JSONResponse({'detail':'Payload too large'},413)(scope,receive,send); return
                if not message.get('more_body'):break
            consumed=False
            original=receive
            async def bounded_receive():
                nonlocal consumed
                if not consumed:
                    consumed=True; return {'type':'http.request','body':body,'more_body':False}
                return await original()
            receive=bounded_receive
        marker=ACCESS.set(access)
        try:
            await self.mcp.session_manager.handle_request(scope,receive,send)
        finally:
            ACCESS.reset(marker)


@asynccontextmanager
async def serving(app):
    """Keeps the tool sessions running for the life of the API."""
    mcp = getattr(app.state, "platform_tools", None)
    if mcp is None:
        yield
        return
    async with mcp.session_manager.run():
        yield
