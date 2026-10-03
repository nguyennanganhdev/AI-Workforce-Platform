"""Stateful, local-only demo API. No database, model, camera or messaging calls."""

from datetime import datetime, timezone
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from .v3_reports import _docx

Actor = Annotated[Literal["resident", "management", "technical", "security", "admin"],
                  Header(alias="X-Demo-Actor")]


class ChatInput(BaseModel):
    title: str = Field(min_length=1, max_length=160)


class MessageInput(BaseModel):
    text: str = Field(min_length=1, max_length=10000)
    client_message_id: str = Field(min_length=1, max_length=120)
    mention_agent_id: str | None = None


class TicketInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(min_length=1, max_length=10000)
    category_id: Literal["technical", "security"] = "technical"
    business_severity: Literal["P0", "P1", "P2", "P3"] = "P2"
    building_id: str = "building-s201"
    domain_id: str = "vinhomes"
    unit_id: str = "unit-1201"


class DecisionInput(BaseModel):
    approved: bool
    note: str = Field(min_length=1, max_length=2000)


class AssignmentInput(BaseModel):
    staff_id: Literal["technical", "security"]


class StatusInput(BaseModel):
    status: Literal["in_progress", "completed"]
    evidence: str | None = Field(default=None, max_length=1000)


class AgentInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class AccountInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    role: Literal["resident", "management", "technical", "security"]


class AccessInput(BaseModel):
    status: Literal["active", "suspended", "deleted"]


class MemoryInput(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class EvidenceInput(BaseModel):
    file_name: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=1000)


class DemoState:
    def __init__(self) -> None:
        self.chats: dict[str, dict] = {}
        self.tickets: dict[str, dict] = {}
        self.orders: dict[str, dict] = {}
        self.approvals: dict[str, dict] = {}
        self.alerts: dict[str, dict] = {}
        self.interruptions: dict[str, dict] = {}
        self.notifications: list[dict] = []
        self.memory: dict[str, dict] = {}
        self.invoices: dict[str, dict] = {}
        self.evidence: dict[str, dict] = {}
        self.accounts = {role: {"id": role, "name": f"Demo {role}", "role": role,
                                "status": "active"} for role in
                         ("resident", "management", "technical", "security", "admin")}
        self.agents = {"reception": {"id": "reception", "name": "Reception"},
                       "supervisor": {"id": "supervisor", "name": "Supervisor"},
                       "report": {"id": "report", "name": "Report"}}
        self.rooms = {"management-room": {"id": "management-room", "name": "BQL S2.01",
                                           "messages": [], "agents": list(self.agents)}}

    def notify(self, actor: str, kind: str, resource: str) -> None:
        self.notifications.append({"id": str(uuid4()), "actor": actor,
                                   "payload": {"type": kind, "resourceId": resource},
                                   "read_at": None})

    def event(self, ticket: dict, kind: str, actor: str) -> None:
        ticket["version"] += 1
        ticket["events"].append({"seq": len(ticket["events"]) + 1, "event_type": kind,
                                  "actor": actor, "occurred_at": datetime.now(timezone.utc).isoformat()})
        self.notify("resident", kind, ticket["id"])


def require(actor: str, *roles: str) -> None:
    if actor not in roles:
        raise HTTPException(403, "Role is not allowed for this action")


def item(collection: dict, resource_id: str) -> dict:
    if resource_id not in collection:
        raise HTTPException(404, "Resource not found")
    return collection[resource_id]


def create_demo_app() -> FastAPI:
    app = FastAPI(title="Vinhomes API — mock demo", version="demo-1",
                  description="Mock data in memory. Select X-Demo-Actor in Swagger. Restart resets data.")
    state = DemoState()
    app.state.demo = state
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:5173"], allow_methods=["*"], allow_headers=["Content-Type", "X-Demo-Actor"])

    @app.middleware("http")
    async def mark_demo(request: Request, call_next):
        actor = request.headers.get("X-Demo-Actor")
        if actor in state.accounts and state.accounts[actor]["status"] != "active":
            return JSONResponse({"detail": "Management suspended this demo account"}, status_code=403)
        response = await call_next(request)
        response.headers["X-Vinhomes-Data-Mode"] = "mock"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/health")
    @app.get("/ready")
    async def health():
        return {"status": "ready", "mode": "mock", "databaseRequired": False}

    @app.get("/demo/fixtures")
    async def fixtures():
        return {"actors": list(state.accounts), "domainId": "vinhomes",
                "buildingId": "building-s201", "unitId": "unit-1201",
                "managementUnitId": "management-s201", "roomId": "management-room",
                "categories": ["technical", "security"]}

    @app.get("/catalogs")
    async def catalogs(actor: Actor = "resident"):
        return {"domains": [{"id": "vinhomes", "name": "Vinhomes"}],
                "buildings": [{"id": "building-s201", "name": "S2.01"}],
                "serviceCategories": [{"id": c, "name": c} for c in ("technical", "security")],
                "staff": [state.accounts[c] for c in ("technical", "security")]}

    @app.get("/management-units/resolve")
    async def resolve(buildingId: str, domainId: str, actor: Actor = "resident"):
        if buildingId != "building-s201" or domainId != "vinhomes":
            raise HTTPException(404, "Unknown demo location")
        return {"managementUnitId": "management-s201", "buildingId": buildingId, "domainId": domainId}

    @app.post("/resident/chats", status_code=201)
    async def create_chat(body: ChatInput, actor: Actor = "resident"):
        require(actor, "resident")
        chat = {"id": str(uuid4()), "name": body.title, "messages": [], "ticket_id": None}
        state.chats[chat["id"]] = chat
        return chat

    @app.get("/resident/chats")
    async def chats(actor: Actor = "resident"):
        require(actor, "resident")
        return {"items": list(state.chats.values())}

    @app.get("/resident/chats/{channel_id}/messages")
    async def messages(channel_id: str, actor: Actor = "resident"):
        require(actor, "resident")
        return {"items": item(state.chats, channel_id)["messages"]}

    @app.post("/resident/chats/{channel_id}/messages", status_code=201)
    async def message(channel_id: str, body: MessageInput, actor: Actor = "resident"):
        require(actor, "resident")
        chat = item(state.chats, channel_id)
        previous = next((m for m in chat["messages"] if m.get("client_message_id") == body.client_message_id), None)
        if previous:
            if previous["body"]["text"] != body.text:
                raise HTTPException(409, "Message key already used")
            return previous
        sent = {"id": str(uuid4()), "seq": len(chat["messages"]) + 1,
                "sender_kind": "user", "body": {"text": body.text},
                "client_message_id": body.client_message_id}
        chat["messages"].append(sent)
        chat["messages"].append({"id": str(uuid4()), "seq": len(chat["messages"]) + 1,
                                 "sender_kind": "agent", "body": {"text": "Reception demo đã tiếp nhận. Nếu cần nhân viên, hãy tạo ticket trong chat này."}})
        return sent

    @app.post("/resident/chats/{channel_id}/tickets", status_code=201)
    async def create_ticket(channel_id: str, body: TicketInput, actor: Actor = "resident"):
        require(actor, "resident")
        chat = item(state.chats, channel_id)
        if chat["ticket_id"]:
            raise HTTPException(409, "Chat already has a ticket")
        if (body.building_id, body.domain_id, body.unit_id) != ("building-s201", "vinhomes", "unit-1201"):
            raise HTTPException(422, "Use the demo fixture location")
        ticket = {"id": str(uuid4()), **body.model_dump(), "channel_id": channel_id,
                  "management_unit_id": "management-s201", "status": "open",
                  "severity": {"P0": "p1", "P1": "p2", "P2": "p3", "P3": "p4"}[body.business_severity],
                  "version": 0, "events": []}
        ticket["code"] = "DEMO-" + ticket["id"][:8].upper()
        state.tickets[ticket["id"]] = ticket
        chat["ticket_id"] = ticket["id"]
        state.event(ticket, "ticket.created", actor)
        state.notify("management", "ticket.created", ticket["id"])
        return ticket

    @app.get("/resident/tickets")
    @app.get("/tickets")
    async def tickets(actor: Actor = "resident"):
        return {"items": list(state.tickets.values())}

    @app.get("/resident/tickets/{ticket_id}")
    @app.get("/tickets/{ticket_id}")
    async def ticket(ticket_id: str, actor: Actor = "resident"):
        row = item(state.tickets, ticket_id)
        return {"ticket": row, "events": row["events"],
                "workOrders": [o for o in state.orders.values() if o["ticket_id"] == ticket_id]}

    @app.get("/tickets/{ticket_id}/timeline")
    async def timeline(ticket_id: str, actor: Actor = "resident"):
        return {"items": item(state.tickets, ticket_id)["events"]}

    @app.post("/tickets/{ticket_id}/routing/ack")
    async def ack_ticket(ticket_id: str, actor: Actor = "management"):
        require(actor, "management")
        row = item(state.tickets, ticket_id)
        if row["status"] != "open":
            raise HTTPException(409, "Ticket already accepted")
        row["status"] = "triaging"
        state.event(row, "ticket.routing_accepted", actor)
        return row

    @app.post("/tickets/{ticket_id}/work-orders", status_code=201)
    async def create_order(ticket_id: str, actor: Actor = "management"):
        require(actor, "management")
        row = item(state.tickets, ticket_id)
        if row["status"] != "triaging":
            raise HTTPException(409, "Accept ticket before creating work")
        order = {"id": str(uuid4()), "ticket_id": ticket_id, "status": "queued", "staff_id": None,
                 "category_id": row["category_id"], "evidence": None}
        state.orders[order["id"]] = order
        row["status"] = "assigned"
        state.event(row, "work_order.created", actor)
        return order

    @app.get("/work-orders")
    @app.get("/my-work-orders")
    async def orders(actor: Actor = "management"):
        require(actor, "management", "technical", "security", "admin")
        return {"items": [o for o in state.orders.values() if actor in ("management", "admin") or o["staff_id"] == actor]}

    @app.get("/staff/available")
    async def available(actor: Actor = "management"):
        require(actor, "management")
        busy = {o["staff_id"] for o in state.orders.values() if o["status"] in ("offered", "accepted", "in_progress")}
        return {"items": [state.accounts[a] for a in ("technical", "security") if a not in busy]}

    @app.get("/dispatch-queue")
    async def queue(actor: Actor = "management"):
        require(actor, "management")
        return {"items": [o for o in state.orders.values() if o["status"] == "queued"]}

    @app.post("/work-orders/{order_id}/assignments")
    async def assign(order_id: str, body: AssignmentInput, actor: Actor = "management"):
        require(actor, "management")
        row = item(state.orders, order_id)
        if row["status"] != "queued" or row["category_id"] != body.staff_id:
            raise HTTPException(409, "Assignment does not match queued work")
        if row["category_id"] == "security" and not row.get("dispatch_approved"):
            raise HTTPException(409, "Management must approve security dispatch")
        if any(o["staff_id"] == body.staff_id and o["status"] in ("offered", "accepted", "in_progress") for o in state.orders.values()):
            raise HTTPException(409, "Staff is busy; work stays queued")
        row.update(staff_id=body.staff_id, status="offered")
        state.notify(body.staff_id, "work_order.offered", order_id)
        return row

    @app.post("/assignments/{order_id}/response")
    async def assignment_response(order_id: str, body: DecisionInput, actor: Actor = "technical"):
        row = item(state.orders, order_id)
        require(actor, row["staff_id"])
        if row["status"] != "offered":
            raise HTTPException(409, "Assignment is not offered")
        row["status"] = "accepted" if body.approved else "queued"
        if not body.approved:
            row["staff_id"] = None
        state.event(item(state.tickets, row["ticket_id"]), "work_assignment.responded", actor)
        return row

    @app.patch("/work-orders/{order_id}/status")
    async def progress(order_id: str, body: StatusInput, actor: Actor = "technical"):
        row = item(state.orders, order_id)
        require(actor, row["staff_id"])
        expected = "accepted" if body.status == "in_progress" else "in_progress"
        if row["status"] != expected:
            raise HTTPException(409, "Invalid work transition")
        if body.status == "completed" and not body.evidence:
            raise HTTPException(422, "Completion requires evidence")
        if body.status == "completed" and any(w["order_id"] == order_id and w["status"] not in ("restored", "cancelled") for w in state.interruptions.values()):
            raise HTTPException(409, "Restore water before completion")
        ticket = item(state.tickets, row["ticket_id"])
        if body.status == "completed" and ticket["category_id"] == "security" and ticket["business_severity"] in ("P0", "P1"):
            if not any(a["ticket_id"] == ticket["id"] and a["status"] == "acknowledged" for a in state.alerts.values()):
                raise HTTPException(409, "Emergency alert requires acknowledgement")
        row.update(status=body.status, evidence=body.evidence)
        ticket = item(state.tickets, row["ticket_id"])
        ticket["status"] = "in_progress" if body.status == "in_progress" else "waiting_for_customer"
        if body.status == "completed":
            if row["category_id"] == "technical" and order_id not in state.invoices:
                state.invoices[order_id] = {"id": str(uuid4()), "order_id": order_id, "status": "issued", "amount": 150000, "currency": "VND"}
            approval = {"id": str(uuid4()), "order_id": order_id, "kind": "customer_completion", "status": "pending"}
            state.approvals[approval["id"]] = approval
        state.event(ticket, "work_order.status_changed", actor)
        return row

    @app.post("/work-orders/{order_id}/evidence", status_code=201)
    async def add_evidence(order_id: str, body: EvidenceInput, actor: Actor = "technical"):
        order = item(state.orders, order_id)
        require(actor, order["staff_id"])
        if order["status"] != "in_progress":
            raise HTTPException(409, "Evidence requires work in progress")
        row = {"id": str(uuid4()), "order_id": order_id, **body.model_dump(), "mode": "mock_metadata"}
        state.evidence[row["id"]] = row
        return row

    @app.get("/tickets/{ticket_id}/evidence")
    async def evidence(ticket_id: str, actor: Actor = "resident"):
        item(state.tickets, ticket_id)
        ids = {o["id"] for o in state.orders.values() if o["ticket_id"] == ticket_id}
        return {"items": [e for e in state.evidence.values() if e["order_id"] in ids]}

    @app.get("/resident/approvals")
    @app.get("/approvals")
    async def approvals(actor: Actor = "resident"):
        require(actor, "resident", "management")
        return {"items": [a for a in state.approvals.values() if
                          (a["kind"] == "customer_completion") == (actor == "resident")]}

    @app.post("/resident/approvals/{approval_id}/decision")
    @app.post("/approvals/{approval_id}/decision")
    async def decide(approval_id: str, body: DecisionInput, actor: Actor = "resident"):
        approval = item(state.approvals, approval_id)
        require(actor, "resident" if approval["kind"] == "customer_completion" else "management")
        if approval["status"] != "pending":
            raise HTTPException(409, "Approval already decided")
        approval.update(status="approved" if body.approved else "rejected", note=body.note)
        order = item(state.orders, approval["order_id"])
        ticket = item(state.tickets, order["ticket_id"])
        if approval["kind"] == "customer_completion":
            ticket["status"] = "closed" if body.approved else "in_progress"
            if not body.approved:
                order["status"] = "in_progress"
        elif approval["kind"] == "water":
            item(state.interruptions, approval["resource_id"])["status"] = "approved" if body.approved else "cancelled"
        elif approval["kind"] == "dispatch" and body.approved:
            order["dispatch_approved"] = True
        elif approval["kind"] == "cancel" and body.approved:
            order["status"] = "cancelled"
            ticket["status"] = "cancelled"
        state.event(ticket, "work_approval.decided", actor)
        return approval

    @app.post("/work-orders/{order_id}/water-shutdown-request", status_code=201)
    async def water_request(order_id: str, actor: Actor = "technical"):
        order = item(state.orders, order_id)
        require(actor, order["staff_id"])
        if actor != "technical" or order["status"] != "in_progress":
            raise HTTPException(409, "Technical work must be in progress")
        if any(w["order_id"] == order_id and w["status"] not in ("restored", "cancelled") for w in state.interruptions.values()):
            raise HTTPException(409, "Water request already active")
        water = {"id": str(uuid4()), "order_id": order_id, "status": "proposed"}
        approval = {"id": str(uuid4()), "order_id": order_id, "kind": "water",
                    "resource_id": water["id"], "status": "pending"}
        water["approval_id"] = approval["id"]
        state.interruptions[water["id"]] = water
        state.approvals[approval["id"]] = approval
        state.notify("management", "water.approval_requested", approval["id"])
        return water

    @app.post("/water-interruptions/{interruption_id}/{action}")
    async def water_action(interruption_id: str, action: Literal["notify", "start", "restore"], actor: Actor = "management"):
        water = item(state.interruptions, interruption_id)
        order = item(state.orders, water["order_id"])
        require(actor, "management" if action == "notify" else order["staff_id"])
        previous, target = {"notify": ("approved", "notified"), "start": ("notified", "active"), "restore": ("active", "restored")}[action]
        if water["status"] != previous:
            raise HTTPException(409, "Invalid water transition")
        water["status"] = target
        state.event(item(state.tickets, order["ticket_id"]), f"water.{target}", actor)
        return water

    @app.get("/work-orders/{order_id}/water-interruptions")
    async def water_list(order_id: str, actor: Actor = "management"):
        order = item(state.orders, order_id)
        require(actor, "management", order["staff_id"])
        return {"items": [w for w in state.interruptions.values() if w["order_id"] == order_id]}

    @app.get("/security/cameras")
    async def cameras(actor: Actor = "security"):
        require(actor, "security", "management")
        return {"items": [{"id": "camera-lobby", "location": "Sảnh S2.01", "online": True},
                          {"id": "camera-gate", "location": "Cổng S2.01", "online": False}]}

    @app.get("/security/emergency-contacts")
    async def contacts(actor: Actor = "security"):
        require(actor, "security", "management")
        return {"items": [{"id": "security", "name": "Trưởng ca demo", "order": 1},
                          {"id": "management", "name": "BQL demo", "order": 2}]}

    @app.post("/tickets/{ticket_id}/emergency-alerts", status_code=201)
    async def alert(ticket_id: str, actor: Actor = "security"):
        require(actor, "security", "management")
        ticket = item(state.tickets, ticket_id)
        if ticket["category_id"] != "security" or ticket["business_severity"] not in ("P0", "P1"):
            raise HTTPException(409, "Emergency security ticket required")
        row = {"id": str(uuid4()), "ticket_id": ticket_id, "status": "sent", "recipient": "security", "step": 1}
        state.alerts[row["id"]] = row
        state.notify("security", "emergency.alert", row["id"])
        state.event(ticket, "emergency.alert_sent", actor)
        return row

    @app.post("/security/alerts/{alert_id}/escalate")
    async def escalate(alert_id: str, actor: Actor = "management"):
        require(actor, "management", "security")
        row = item(state.alerts, alert_id)
        if row["status"] != "sent" or row["step"] != 1:
            raise HTTPException(409, "Alert cannot escalate")
        row.update(recipient="management", step=2)
        state.notify("management", "emergency.alert", alert_id)
        return row

    @app.post("/security/alerts/{alert_id}/ack")
    async def ack_alert(alert_id: str, actor: Actor = "security"):
        row = item(state.alerts, alert_id)
        require(actor, row["recipient"])
        if row["status"] != "sent":
            raise HTTPException(409, "Alert already acknowledged")
        row.update(status="acknowledged", acknowledged_by=actor)
        state.event(item(state.tickets, row["ticket_id"]), "emergency.acknowledged", actor)
        return row

    @app.post("/work-orders/{order_id}/security/{action}-request", status_code=201)
    async def security_request(order_id: str, action: Literal["dispatch", "cancel"], actor: Actor = "security"):
        require(actor, "security")
        order = item(state.orders, order_id)
        if order["category_id"] != "security":
            raise HTTPException(422, "Security work required")
        if order["status"] in ("completed", "cancelled") or (action == "dispatch" and order["status"] != "queued"):
            raise HTTPException(409, "Invalid security request transition")
        if any(a["order_id"] == order_id and a["kind"] == action and a["status"] == "pending" for a in state.approvals.values()):
            raise HTTPException(409, "Request already pending")
        approval = {"id": str(uuid4()), "order_id": order_id, "kind": action, "status": "pending"}
        state.approvals[approval["id"]] = approval
        state.notify("management", f"security.{action}_requested", approval["id"])
        return approval

    @app.get("/my/notifications")
    async def notifications(actor: Actor = "resident"):
        return {"items": [n for n in state.notifications if n["actor"] == actor]}

    @app.post("/my/notifications/{notification_id}/read")
    async def read_notification(notification_id: str, actor: Actor = "resident"):
        row = next((n for n in state.notifications if n["id"] == notification_id and n["actor"] == actor), None)
        if row is None:
            raise HTTPException(404, "Notification not found")
        row["read_at"] = datetime.now(timezone.utc).isoformat()
        return row

    @app.get("/knowledge/search")
    async def knowledge(query: str, actor: Actor = "resident"):
        return {"items": [{"title": "Hướng dẫn demo", "text_content": "Sự cố điện/nước: tạo ticket. Khẩn cấp an ninh: báo bảo vệ và BQL.", "query": query}]}

    @app.get("/rooms")
    async def rooms(actor: Actor = "management"):
        require(actor, "management")
        return {"items": list(state.rooms.values())}

    @app.get("/rooms/{room_id}/agents")
    async def room_agents(room_id: str, actor: Actor = "management"):
        require(actor, "management")
        return {"items": [state.agents[a] for a in item(state.rooms, room_id)["agents"]]}

    @app.get("/rooms/{room_id}/mentions/{message_id}")
    async def mention(room_id: str, message_id: str, actor: Actor = "management"):
        require(actor, "management")
        room = item(state.rooms, room_id)
        message = next((m for m in room["messages"] if m["id"] == message_id), None)
        if not message or not message.get("mention_agent_id"):
            raise HTTPException(404, "Mention not found")
        return {"messageId": message_id, "status": "completed", "mode": "mock", "agentId": message["mention_agent_id"]}

    @app.post("/rooms/{room_id}/agents", status_code=201)
    async def create_agent(room_id: str, body: AgentInput, actor: Actor = "management"):
        require(actor, "management")
        room = item(state.rooms, room_id)
        row = {"id": str(uuid4()), "name": body.name}
        state.agents[row["id"]] = row
        room["agents"].append(row["id"])
        return row

    @app.get("/rooms/{room_id}/messages")
    async def room_messages(room_id: str, actor: Actor = "management"):
        require(actor, "management")
        return {"items": item(state.rooms, room_id)["messages"]}

    @app.post("/rooms/{room_id}/messages", status_code=201)
    async def room_message(room_id: str, body: MessageInput, actor: Actor = "management"):
        require(actor, "management")
        room = item(state.rooms, room_id)
        if body.mention_agent_id and body.mention_agent_id not in room["agents"]:
            raise HTTPException(422, "Agent is not in room")
        previous = next((m for m in room["messages"] if m.get("client_message_id") == body.client_message_id), None)
        if previous:
            if previous["body"]["text"] != body.text or previous.get("mention_agent_id") != body.mention_agent_id:
                raise HTTPException(409, "Message key already used")
            return previous
        sent = {"id": str(uuid4()), "body": {"text": body.text}, "sender_kind": "user", "client_message_id": body.client_message_id, "mention_agent_id": body.mention_agent_id}
        room["messages"].append(sent)
        if body.mention_agent_id:
            room["messages"].append({"id": str(uuid4()), "sender_kind": "agent",
                                     "body": {"text": f"Demo đã xử lý yêu cầu từ context room: {len(state.tickets)} ticket."}})
        return sent

    @app.get("/reports/{report_type}")
    async def report(report_type: Literal["incident-frequency", "issued-revenue", "incident-frequency.docx", "issued-revenue.docx"], actor: Actor = "management"):
        require(actor, "management")
        issued = [i for i in state.invoices.values() if i["status"] == "issued"]
        summary = {"incidentCount": len(state.tickets), "closedCount": sum(t["status"] == "closed" for t in state.tickets.values()),
                   "issuedInvoiceCount": len(issued), "billedAmount": sum(i["amount"] for i in issued),
                   "currency": "VND", "basis": "mock_issued_invoices"}
        if report_type.endswith(".docx"):
            return Response(_docx(["Báo cáo demo", *[f"{k}: {v}" for k, v in summary.items()]]),
                            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            headers={"Content-Disposition": f'attachment; filename="{report_type}"'})
        return summary

    @app.post("/memory-candidates", status_code=201)
    async def propose_memory(body: MemoryInput, actor: Actor = "management"):
        require(actor, "management")
        row = {"id": str(uuid4()), "text": body.text, "status": "pending"}
        state.memory[row["id"]] = row
        return row

    @app.get("/admin/memory-candidates")
    async def memories(actor: Actor = "admin"):
        require(actor, "admin")
        return {"items": list(state.memory.values())}

    @app.post("/admin/memory-candidates/{candidate_id}/review")
    async def review(candidate_id: str, body: DecisionInput, actor: Actor = "admin"):
        require(actor, "admin")
        row = item(state.memory, candidate_id)
        if row["status"] != "pending":
            raise HTTPException(409, "Already reviewed")
        row.update(status="approved" if body.approved else "rejected", note=body.note)
        return row

    @app.get("/admin/accounts")
    async def accounts(actor: Actor = "admin"):
        require(actor, "admin")
        return {"items": list(state.accounts.values())}

    @app.post("/admin/accounts", status_code=201)
    async def account(body: AccountInput, actor: Actor = "admin"):
        require(actor, "admin")
        row = {"id": str(uuid4()), **body.model_dump(), "status": "active"}
        state.accounts[row["id"]] = row
        return row

    @app.patch("/admin/accounts/{account_id}/access")
    async def access(account_id: str, body: AccessInput, actor: Actor = "admin"):
        require(actor, "admin")
        row = item(state.accounts, account_id)
        row["status"] = body.status
        return row

    return app
