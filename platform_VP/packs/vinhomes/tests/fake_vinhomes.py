"""A stand-in for vinhomes-api's `/integration/v1/*`, strict where the real one is strict.

The wire models and the 409/422 rules below are copied from
vinhome_Recident/services/vinhomes-api/src/vinhomes_api/{v3_reception_supervisor,integration_cases}.py
so a body the pack builds is checked against the same contract. It cannot prove the real server
agrees; it keeps the pack honest against the contract as written.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

TENANT = "11111111-1111-1111-1111-111111111111"
WORKSPACE = "22222222-2222-2222-2222-222222222222"
TEAM = "33333333-3333-3333-3333-333333333333"
TICKET = "44444444-4444-4444-4444-444444444444"
CATEGORY = "55555555-5555-5555-5555-555555555555"
NAME, PHONE = "Nguyễn Văn An", "0912345678"


Key = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=160)]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ResultError(Strict):
    code: str = Field(min_length=1, max_length=100)
    retryable: bool
    message: str = Field(min_length=1, max_length=2000)


class ResultData(Strict):
    outcome: Literal["work_completed", "needs_human_review", "unable_to_resolve"]
    summary: str = Field(min_length=1, max_length=5000)
    work_order_ids: list[UUID] = Field(max_length=100)
    evidence_ids: list[UUID] = Field(max_length=200)


class ResultIn(Strict):
    schema_version: Literal["2.0"]
    message_id: str = Field(min_length=1, max_length=200)
    correlation_id: str = Field(min_length=1, max_length=200)
    sent_at: datetime
    message_type: Literal["accepted", "in_progress", "information_requested", "plan_approval_requested",
                          "completed", "failed", "cancelled"]
    message: str = Field(min_length=1, max_length=10000)
    tenant_id: UUID
    workspace_id: UUID
    team_id: UUID
    ticket_id: UUID
    ticket_code: str = Field(min_length=1, max_length=100)
    ticket_generation: int = Field(ge=0)
    ticket_version: str = Field(pattern=r"^[0-9]+$", max_length=30)
    supervisor_run_id: str = Field(min_length=1, max_length=200)
    result: ResultData = Field(default=None)
    error: ResultError = Field(default=None)

    @field_validator("sent_at")
    @classmethod
    def tz(cls, v):
        if v.utcoffset() is None:
            raise ValueError("timestamp must include a timezone")
        return v

    @model_validator(mode="after")
    def matches(self):
        if self.message_type == "completed" and (self.result is None or self.result.outcome != "work_completed"):
            raise ValueError("completed requires a work_completed result")
        if self.message_type == "failed" and self.error is None:
            raise ValueError("failed requires an error object")
        if self.message_type == "cancelled" and self.result is not None:
            raise ValueError("cancelled cannot report work_completed")
        return self


class PlanIn(Strict):
    ticket_version: int = Field(ge=0)
    summary: str = Field(min_length=1, max_length=300)
    steps: list[str] = Field(min_length=1, max_length=4)
    performer_staff_id: UUID | None = None
    appointment_at: datetime | None = None
    estimated_amount: Decimal = Field(default=Decimal("0"), ge=0)
    estimated_duration_min: int | None = Field(default=None, ge=1, le=10080)
    cost_bearer: Literal["management", "resident", "warranty", "contractor"] = "resident"
    requires_outage: bool = False


def submitted(n: int = 1, mtype: str = "ticket_submitted", *, generation: int = 0, version: int = 7,
              title: str = "Vòi bếp rò nước", description: str = "Nước rò dưới bồn rửa từ sáng nay.",
              facts: list | None = None, message: str | None = None, emergency: bool = False,
              ticket: str = TICKET) -> dict:
    """An inbox message exactly as ReceptionToSupervisorMessage serializes."""
    msg = {
        "schema_version": "2.0", "message_id": f"m-{n}", "correlation_id": "corr-1",
        "sent_at": "2026-10-09T08:00:00+00:00", "message_type": mtype,
        "message": message or description, "tenant_id": TENANT, "domain_id": "66666666-6666-6666-6666-666666666666",
        "domain_name": "Vinhomes", "workspace_id": WORKSPACE, "team_id": TEAM, "ticket_id": ticket,
        "ticket_code": "VH-0001", "ticket_generation": generation, "ticket_version": str(version),
        "resident": {"resident_id": "res-42", "resident_name": NAME, "phone_number": PHONE},
        "location": {"location_scope_id": "77777777-7777-7777-7777-777777777777",
                     "unit_id": "88888888-8888-8888-8888-888888888888", "unit_number": "S1.01-1201",
                     "building_id": "99999999-9999-9999-9999-999999999999", "building_code": "S1.01",
                     "building_name": "Tòa S1.01"},
        "request": {"title": title, "description": description, "request_kind": "incident",
                    "category_id": CATEGORY, "priority": "critical" if emergency else "high",
                    "severity": "moderate", "is_emergency": emergency, "triage_decision_id": None,
                    "handoff_reason": "needs_staff"},
        "facts": facts if facts is not None else [
            {"key": "vị trí", "value": "bồn rửa bếp", "source": "customer_report", "source_message_id": "c-1"}],
        "file_ids": [], "created_at": "2026-10-09T07:59:00+00:00",
    }
    if mtype != "ticket_submitted":
        msg["source_message_id"] = "c-2"
    return msg


class State:
    def __init__(self) -> None:
        self.secret = "ics_test"
        self.messages: list[dict] = []
        self.generation = 0
        self.version = 7
        self.status = "open"
        self.category: str | None = CATEGORY
        self.plan: dict | None = None
        self.pending = False          # a resident-facing request is open
        self.work_incomplete = False  # a required work order is not completed
        self.force_409: str | None = None
        self.fail: list[int] = []     # statuses to answer with, one per request
        self.bump_after_get = False   # the ticket changes right after the next read
        self.stored: dict[str, tuple[str, dict]] = {}   # message_id -> (hash, response)
        self.results: list[dict] = []                    # accepted result bodies, in order
        self.result_posts = 0                            # every POST /results, accepted or not
        self.plans: dict[str, tuple[str, dict]] = {}
        self.plan_posts = 0
        self.knowledge_version = "sha256:v1"
        self.knowledge: dict[str, list[dict]] = {"resident": [], "staff": []}
        self.knowledge_calls: list[dict] = []
        self.auth_seen: list[tuple] = []

    def ticket(self) -> dict:
        return {"id": TICKET, "code": "VH-0001", "status": self.status, "version": self.version,
                "priority": "high", "severity": "moderate", "is_emergency": False, "request_kind": "incident",
                "title": "Vòi bếp rò nước", "category_id": self.category, "management_unit_id": None,
                "response_due_at": "2026-10-09T10:00:00+00:00", "resolution_due_at": "2026-10-10T10:00:00+00:00",
                "reopen_count": self.generation, "unit_code": "S1.01-1201"}


def _err(status: int, code: str, message: str, retryable: bool = False) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message, "retryable": retryable,
                                   "correlation_id": "c"}}, status_code=status)


class Refuse(Exception):
    def __init__(self, response: JSONResponse) -> None:
        self.response = response


def make_app(state: State) -> FastAPI:
    app = FastAPI()

    @app.exception_handler(Refuse)
    async def _refuse(_r, exc: Refuse):
        return exc.response

    def conflict(message: str) -> Refuse:
        return Refuse(_err(409, "CONFLICT", message))

    async def gate(request: Request, x_client_id: str = Header(default=""), authorization: str = Header(default="")):
        state.auth_seen.append((x_client_id, authorization))
        if x_client_id != "platform" or authorization != f"Bearer {state.secret}":
            raise Refuse(_err(401, "UNAUTHENTICATED", "bad client credentials"))
        if state.fail:
            code = state.fail.pop(0)
            raise Refuse(_err(code, "UNAVAILABLE", "try later", True))

    @app.get("/integration/v1/cases/inbox", dependencies=[Depends(gate)])
    async def inbox(cursor: str | None = None, limit: int = Query(50, ge=1, le=100)):
        start = int(cursor[1:]) if cursor else 0
        items = state.messages[start:start + limit]
        return {"items": items, "next_cursor": f"c{start + len(items)}" if items else cursor}

    @app.get("/integration/v1/cases/{ticket_id}", dependencies=[Depends(gate)])
    async def get_case(ticket_id: UUID):
        if str(ticket_id) != TICKET:
            raise Refuse(_err(404, "NOT_FOUND", "No such case for this client"))
        body = {"case_id": TEAM, "status": "open", "ticket_generation": state.generation,
                "ticket": state.ticket(), "plan": state.plan}
        if state.bump_after_get:
            state.bump_after_get = False
            state.version += 1
        return body

    @app.post("/integration/v1/cases/{ticket_id}/results", status_code=201, dependencies=[Depends(gate)])
    async def post_result(ticket_id: UUID, body: ResultIn, key: Key):
        state.result_posts += 1
        if str(body.team_id) != TEAM or body.ticket_id != ticket_id:
            raise conflict("The result names a different case")
        payload = body.model_dump(mode="json", exclude_unset=True)
        digest = hashlib.sha256(json.dumps({k: v for k, v in payload.items() if k != "sent_at"},
                                           sort_keys=True).encode()).hexdigest()
        previous = state.stored.get(body.message_id)
        if previous:
            if previous[0] != digest:
                raise conflict("message_id was already used for a different payload")
            return {**previous[1], "replayed": True}
        if state.force_409:
            raise conflict(state.force_409)
        if (body.ticket_generation != state.generation or body.ticket_version != str(state.version)
                or body.ticket_code != "VH-0001" or str(body.tenant_id) != TENANT):
            raise conflict("Supervisor result is stale or targets a different ticket scope")
        final = state.status in {"resolved", "closed", "cancelled"}
        if body.message_type in {"accepted", "in_progress", "information_requested",
                                 "plan_approval_requested"} and final:
            raise conflict("A final ticket cannot receive a new Supervisor request")
        if body.message_type == "completed":
            if state.pending:
                raise conflict("Resolve the pending resident request before finishing this team")
            if state.status not in {"resolved", "closed"}:
                raise conflict("Backend has not accepted ticket completion")
            if state.work_incomplete:
                raise conflict("One or more backend work orders are not complete")
        if body.message_type == "cancelled" and state.status != "cancelled":
            raise conflict("Backend has not confirmed ticket cancellation")
        response = {"result": payload, "replayed": False, "verification": {"ticket_status": state.status}}
        state.stored[body.message_id] = (digest, response)
        state.results.append(payload)
        return response

    @app.post("/integration/v1/cases/{ticket_id}/plans", status_code=201, dependencies=[Depends(gate)])
    async def post_plan(ticket_id: UUID, body: PlanIn, key: Key):
        state.plan_posts += 1
        digest = hashlib.sha256(json.dumps(body.model_dump(mode="json", exclude={"ticket_version"}),
                                           sort_keys=True).encode()).hexdigest()
        old = state.plans.get(key)
        if old:
            if old[0] != digest:
                raise conflict("That Idempotency-Key was used for a different plan")
            return old[1]
        if body.ticket_version != state.version or state.status in {"closed", "cancelled", "resolved"}:
            raise conflict("The request changed or is final")
        if state.category is None:
            return JSONResponse({"detail": "The request must be classified before a plan can be proposed"}, status_code=422)
        if state.plan and state.plan["status"] in ("management_pending", "resident_pending"):
            raise conflict("Decide the plan already waiting first")
        plan = {"id": f"plan-{len(state.plans) + 1}", "status": "management_pending", "version": 1,
                "title": body.summary, "proposed_by_client_id": "platform"}
        state.plans[key] = (digest, plan)
        state.plan = {k: plan[k] for k in ("id", "status", "version", "title")}
        return plan

    @app.get("/integration/v1/knowledge/pack", dependencies=[Depends(gate)])
    async def knowledge(audience: Literal["resident", "staff", "management"] = "resident",
                        since: str | None = None):
        state.knowledge_calls.append({"audience": audience, "since": since})
        base = {"version": state.knowledge_version, "generated_at": "2026-10-09T00:00:00+00:00", "audience": audience}
        if since == state.knowledge_version:
            return {**base, "unchanged": True, "documents": []}
        return {**base, "unchanged": False, "documents": state.knowledge.get(audience, [])}

    @app.exception_handler(RequestValidationError)
    async def _validation(_r, exc: RequestValidationError):
        # FastAPI's own shape, which the real server keeps for validation errors.
        return JSONResponse({"detail": [{"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()]},
                            status_code=422)

    return app


def doc(doc_id: str, title: str, body: str, kind: str = "policy", zones: list[str] | None = None) -> dict:
    return {"id": doc_id, "kind": kind, "title": title, "body_md": body, "language": "vi",
            "scope": {"zone_codes": zones or [], "unit_kinds": []}, "audience": ["resident"],
            "effective_from": "2026-01-01", "effective_to": None, "checksum": "sha256:x", "source": "x"}


@contextlib.asynccontextmanager
async def stack():
    """(state, client): the client talks to the fake in process, on the caller's event loop."""
    from awp_vinhomes.client import VinhomesClient

    state = State()
    client = VinhomesClient("http://vinhomes.test", state.secret, transport=httpx.ASGITransport(app=make_app(state)))
    try:
        yield state, client
    finally:
        await client.aclose()
