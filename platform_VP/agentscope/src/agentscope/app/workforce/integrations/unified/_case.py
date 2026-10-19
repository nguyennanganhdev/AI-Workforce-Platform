"""The partner case runtime of unified mode.

A partner ticket is a ticket of the platform's Leader (the console
Leader of the route's manager). The Leader talks to the partner's end user
only through ``CaseSay`` / ``CaseFinalize`` and holds no partner tool: the
runtime opens the ticket's room with its session, and the Leader invites
(``AgentInvite``) the partner's coordinator agent (the declaration's leader
profile) and, when needed, its specialists, and waits for their reports within its turn. Members call their
share of the route's tools under their declared names and the ticket's grant
(the platform fills the hidden ``client_reference``); every result and
provider event carries an evidence label ``E<n>`` that the Leader cites.
Everything here is per session and only attached to sessions of partner
workflows (see :class:`CaseRuntime.middlewares`).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import uuid4

import mcp.types
from pydantic import Field
from sqlalchemy import and_, func, insert, select, update
from sqlalchemy.exc import IntegrityError

from ....._logging import logger
from .....event import ReplyEndEvent, ReplyFinishedReason
from .....message import TextBlock, ToolResultBlock, ToolResultState
from .....middleware import MiddlewareBase
from .....model import ChatResponse
from .....permission import PermissionBehavior, PermissionDecision
from .....tool import MCPTool, ParamsBase, ToolBase, ToolChunk
from ...._evidence_claims import ClaimValidation, EvidenceSource, validate_claims
from ...contracts import Scope
from ...orchestration._tables import partner_requests, workflow_inputs, workflows
from ._tables import (
    approvals,
    case_entries,
    case_sessions,
    operations,
    receipts,
    routes,
)

EXPECTS = ("none", "reply", "confirmation")
# The ticket's room lasts as long as the ticket: no TeamDelete (its schema
# would ride along in every Leader call).
# The ticket's room opens with its session (the runner's _case_session): no TeamCreate.
TEAM_TOOLS = ("AgentInvite", "TeamSay")
# Rounds of member reports the leader may wait for within one turn.
MAX_TEAM_ROUNDS = 4
MAX_TEXT = 4000
LABEL = re.compile(r"^E(\d+)$")


def _now() -> datetime:
    return datetime.now(UTC)


def _say_claims(text: str, cited: dict[str, str], trusted: list[str]) -> ClaimValidation:
    return validate_claims(
        text,
        [EvidenceSource(content=value, source_id=label) for label, value in cited.items()]
        + [EvidenceSource(content=value, source_id=f"customer:{index}", authority="customer") for index, value in enumerate(trusted)],
    )


def check_say(
    text: str,
    cites: list[str],
    rules: dict,
    cited: dict[str, str],
    trusted: list[str],
    *,
    claim_validation: ClaimValidation | None = None,
) -> list[str]:
    """Why ``text`` may not reach the end user (empty list: it may).

    * a phrase the route forbids (``rules.phrase_rules``); a rule's
      ``unless`` phrases lift it when a cited source says them;
    * a factual claim that does not match its entity, field, value and unit
      within cited evidence or the end user's messages;
    * a cited label that does not exist.
    """

    problems: list[str] = []
    missing = [label for label in cites if label not in cited]
    if missing:
        problems.append(
            "cites có mã không tồn tại: " + ", ".join(missing)
            + ". Chỉ dùng mã E.. ở đầu kết quả công cụ hoặc sự kiện."
        )
    lowered = " ".join(text.lower().split())
    sources = " ".join(cited.values()).lower()
    for rule in (rules or {}).get("phrase_rules") or []:
        unless = [str(item).lower() for item in rule.get("unless") or []]
        # Match affirmative evidence, not a negated occurrence such as
        # "không miễn phí". A substring alone cannot grant an exception.
        if unless and any(
            any(not re.search(r"(?:không|chưa|not|never)\s+(?:\w+\s+){0,2}$", sources[max(0, match.start()-50):match.start()])
                for match in re.finditer(re.escape(item), sources))
            for item in unless
        ):
            continue
        for phrase in rule.get("phrases") or []:
            matches = re.finditer(re.escape(str(phrase).lower()), lowered)
            if any(not re.search(r"(?:không|chưa|not|never)\s+(?:\w+\s+){0,2}$",
                                 lowered[max(0, match.start()-50):match.start()]) for match in matches):
                problems.append(f'Không được viết "{phrase}": {rule.get("reason", "")}'.strip())
                break
    claims = claim_validation if claim_validation is not None else _say_claims(text, cited, trusted)
    if claims.unsupported:
        problems.append(
            "Các chi tiết sau chưa khớp với bằng chứng đã trích (cites) hay lời của người dùng: "
            + ", ".join(claims.unsupported)
            + ". Kiểm tra đúng đối tượng, trường dữ liệu, giá trị và đơn vị; chỉ sửa phần chưa khớp."
        )
    return problems


class CaseStore:
    """Persistence of one partner case (sessions, log, operations)."""

    def __init__(self, uows: Callable[[], Any], jobs: Any = None) -> None:
        self._uows = uows
        self.jobs = jobs

    async def route(self, route_id: str) -> dict | None:
        async with self._uows() as uow:
            row = (
                await uow.execute(select(routes).where(routes.c.route_id == route_id))
            ).mappings().first()
        return dict(row) if row else None

    async def session(self, session_id: str) -> dict | None:
        async with self._uows() as uow:
            row = (
                await uow.execute(
                    select(case_sessions).where(case_sessions.c.session_id == session_id),
                )
            ).mappings().first()
        return dict(row) if row else None

    async def routes_using(self, manager_account_id: str, agent_id: str) -> list[str]:
        """Routes of this manager whose leader or declared member is the agent."""
        async with self._uows() as uow:
            rows = (
                await uow.execute(
                    select(routes.c.route_id, routes.c.leader_agent_id, routes.c.config).where(
                        routes.c.manager_account_id == manager_account_id,
                    ),
                )
            ).all()
        return [
            route_id for route_id, leader, config in rows
            if leader == agent_id or agent_id in ((config or {}).get("member_agents") or {})
        ]

    async def session_of_workflow(self, workflow_id: str) -> dict | None:
        async with self._uows() as uow:
            row = (
                await uow.execute(
                    select(case_sessions).where(case_sessions.c.workflow_id == workflow_id),
                )
            ).mappings().first()
        return dict(row) if row else None

    async def bind_session(self, values: dict) -> None:
        async with self._uows() as uow:
            try:
                await uow.execute(insert(case_sessions).values(created_at=_now(), **values))
                await uow.commit()
            except IntegrityError:
                return

    async def set_trigger(self, session_id: str, trigger_id: str) -> None:
        async with self._uows() as uow:
            await uow.execute(
                update(case_sessions)
                .where(case_sessions.c.session_id == session_id)
                .values(trigger_id=trigger_id),
            )
            await uow.commit()

    async def append(self, workflow_id: str, kind: str, text: str, uow=None, **fields) -> int:
        """Add one log entry; returns its number (the ``E<n>`` of evidence)."""

        if uow is not None:
            return await self._append(uow, workflow_id, kind, text, fields)
        for _ in range(5):
            try:
                async with self._uows() as owned:
                    seq = await self._append(owned, workflow_id, kind, text, fields)
                    await owned.commit()
                    return seq
            except IntegrityError:
                await asyncio.sleep(0.01)
        raise RuntimeError("case log is busy")

    @staticmethod
    async def _append(uow, workflow_id, kind, text, fields) -> int:
        last = await uow.scalar(
            select(func.max(case_entries.c.seq)).where(case_entries.c.workflow_id == workflow_id),
        )
        seq = int(last or 0) + 1
        await uow.execute(
            insert(case_entries).values(
                id=uuid4().hex,
                workflow_id=workflow_id,
                seq=seq,
                kind=kind,
                text=text,
                trigger_id=fields.get("trigger_id"),
                expects=fields.get("expects"),
                outcome=fields.get("outcome"),
                pending=bool(fields.get("pending", False)),
                created_at=_now(),
            ),
        )
        return seq

    async def entries(self, workflow_id: str, *, kind: str | None = None, trigger_id: str | None = None) -> list[dict]:
        clauses = [case_entries.c.workflow_id == workflow_id]
        if kind is not None:
            clauses.append(case_entries.c.kind == kind)
        if trigger_id is not None:
            clauses.append(case_entries.c.trigger_id == trigger_id)
        async with self._uows() as uow:
            rows = (
                await uow.execute(
                    select(case_entries).where(and_(*clauses)).order_by(case_entries.c.seq),
                )
            ).mappings().all()
        return [dict(row) for row in rows]

    async def labelled(self, workflow_id: str, labels: list[str]) -> dict[str, str]:
        numbers = {int(m.group(1)): label for label in labels if (m := LABEL.match(label))}
        if not numbers:
            return {}
        async with self._uows() as uow:
            rows = (
                await uow.execute(
                    select(case_entries.c.seq, case_entries.c.text).where(
                        case_entries.c.workflow_id == workflow_id,
                        case_entries.c.seq.in_(list(numbers)),
                        case_entries.c.kind.in_(("evidence", "event")),
                    ),
                )
            ).all()
        return {numbers[seq]: text for seq, text in rows}

    async def take_pending(self, workflow_id: str) -> list[dict]:
        """Events the leader has not heard about yet; marks them heard."""

        async with self._uows() as uow:
            rows = (
                await uow.execute(
                    select(case_entries)
                    .where(case_entries.c.workflow_id == workflow_id, case_entries.c.pending.is_(True))
                    .order_by(case_entries.c.seq),
                )
            ).mappings().all()
            if rows:
                await uow.execute(
                    update(case_entries)
                    .where(case_entries.c.id.in_([row["id"] for row in rows]))
                    .values(pending=False),
                )
                await uow.commit()
        return [dict(row) for row in rows]

    async def customer_texts(self, workflow_id: str) -> list[str]:
        async with self._uows() as uow:
            rows = (
                await uow.execute(
                    select(workflow_inputs.c.text).where(workflow_inputs.c.workflow_id == workflow_id),
                )
            ).all()
        return [row[0] for row in rows if row[0]]

    async def grant_context(self, workflow_id: str) -> dict:
        async with self._uows() as uow:
            payload = await uow.scalar(select(partner_requests.c.payload).where(
                partner_requests.c.workflow_id == workflow_id,
            ).order_by(partner_requests.c.accepted_at, partner_requests.c.id).limit(1))
        if not payload or payload.get("workflow_id") != workflow_id:
            raise ValueError("Workflow has no trusted handover")
        return {"ticket_id": payload["audience"]["external_ticket_id"],
                "external_request_id": payload["external_request_id"]}

    async def operation(self, reference: str) -> dict | None:
        async with self._uows() as uow:
            row = (await uow.execute(select(operations).where(
                operations.c.client_reference == reference,
            ))).mappings().first()
        return dict(row) if row else None

    async def progress_operation(self, workflow_id: str, receipt_id: str) -> dict | None:
        async with self._uows() as uow:
            row = (await uow.execute(select(operations).join(receipts,
                receipts.c.operation_id == operations.c.operation_id).where(
                receipts.c.receipt_id == receipt_id, operations.c.workflow_id == workflow_id))).mappings().first()
        return dict(row) if row else None

    async def record_operation(self, values: dict) -> bool:
        async with self._uows() as uow:
            workflow = (await uow.execute(select(workflows).where(
                workflows.c.id == values["workflow_id"],
            ).with_for_update())).mappings().one()
            if workflow["state"] == "closed":
                raise ValueError("closed workflows cannot start partner operations")
            existing = (
                await uow.execute(
                    select(operations.c.operation_id).where(
                        operations.c.client_reference == values["client_reference"],
                    ),
                )
            ).first()
            if existing is None:
                now = _now()
                await uow.execute(
                    insert(operations).values(
                        operation_id=uuid4().hex,
                        rank=0,
                        terminal=False,
                        outcome=None,
                        created_at=now,
                        updated_at=now,
                        **values,
                    ),
                )
                if self.jobs is not None:
                    await self.jobs.enqueue(
                        Scope(**{key: workflow[key] for key in ("tenant_id", "domain_id", "area_id", "manager_account_id")}),
                        "workforce.unified.reconcile", {"client_reference": values["client_reference"], "generation": 0},
                        "unified-reconcile:" + values["client_reference"] + ":0", uow,
                        not_before=now + timedelta(seconds=30),
                    )
                await uow.commit()
                return True
            return False

    async def open_operations(self, workflow_id: str) -> int:
        async with self._uows() as uow:
            return int(
                await uow.scalar(
                    select(func.count()).select_from(operations).where(
                        operations.c.workflow_id == workflow_id,
                        operations.c.terminal.is_(False),
                    ),
                )
                or 0,
            )

    async def completion_ready(self, workflow_id: str) -> bool:
        async with self._uows() as uow:
            work = (await uow.execute(select(operations).where(
                operations.c.workflow_id == workflow_id))).mappings().all()
            pending = await uow.scalar(select(func.count()).select_from(approvals).where(
                approvals.c.workflow_id == workflow_id, approvals.c.status == "pending"))
        return bool(work) and not pending and all(
            row["terminal"] and row["outcome"] == "completed" and row["status"] == "result_published"
            for row in work)

    async def settle_operation(self, reference: str, status: str, external_job_id: str | None = None) -> None:
        async with self._uows() as uow:
            # An event can arrive while the tool call is still returning. Never roll it back.
            values = {"updated_at": _now()}
            if external_job_id:
                values["external_job_id"] = external_job_id
            await uow.execute(update(operations).where(operations.c.client_reference == reference).values(**values))
            await uow.execute(update(operations).where(
                operations.c.client_reference == reference, operations.c.rank == 0,
            ).values(status=status[:64], terminal=status in ("failed", "confirmed", "rejected")))
            await uow.commit()

    async def save_call_result(self, reference: str, result: dict, *, unknown: bool = False) -> None:
        async with self._uows() as uow:
            await uow.execute(update(operations).where(
                operations.c.client_reference == reference,
            ).values(call_result=result, updated_at=_now()))
            if unknown:
                await uow.execute(update(operations).where(
                    operations.c.client_reference == reference, operations.c.rank == 0,
                    operations.c.terminal.is_(False),
                ).values(status="unknown"))
            await uow.commit()


class _Case:
    """What the tools of one session need to know at call time."""

    def __init__(self, store: CaseStore, session: dict, route: dict, on_say: Callable | None = None,
                 context_reader: Callable | None = None) -> None:
        self.store = store
        self.workflow_id = session["workflow_id"]
        self.session_id = session["session_id"]
        self.route = route
        self.rules = (route.get("config") or {}).get("rules") or {}
        # Tells the ticket's room what the end user was sent.
        self.on_say = on_say
        self.context_reader = context_reader
        self.operation_owner = (session.get("agent_id"), session["session_id"])

    async def trigger_id(self) -> str:
        current = await self.store.session(self.session_id)
        return (current or {}).get("trigger_id") or "unknown"

    async def said(self) -> bool:
        """Whether the current turn already sent its one message."""
        return bool(await self.store.entries(self.workflow_id, kind="say", trigger_id=await self.trigger_id()))

    async def client_reference(self, tool: str, arguments: dict) -> str:
        canonical = json.dumps(arguments, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        seed = f"{self.workflow_id}|{await self.trigger_id()}|{tool}|{canonical}"
        return "cr_" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:40]


class _SayParams(ParamsBase):
    text: str = Field(description="Đúng lời gửi người dùng (tiếng Việt có dấu).")
    expects: Literal["none", "reply", "confirmation"] = Field(
        default="none",
        description='"none": chỉ báo tin; "reply": bạn hỏi và chờ trả lời; "confirmation": mời xác nhận hoàn thành.',
    )
    cites: list[str] = Field(
        default_factory=list,
        description='Mã E.. của kết quả công cụ/sự kiện chứa các con số, giờ, tên, số tiền bạn viết, ví dụ ["E7"].',
    )


class _FinalizeParams(ParamsBase):
    answer: str = Field(description="Câu trả lời cuối cho người dùng.")
    outcome: str = Field(default="answered", description='Kết quả, ví dụ "answered" hoặc "needs_human".')
    cites: list[str] = Field(default_factory=list, description="Mã E.. làm bằng chứng.")
    unknowns: list[str] = Field(default_factory=list, description="Điều chưa xác minh được.")


class _CaseTool(ToolBase):
    is_concurrency_safe = False
    is_read_only = True
    is_state_injected = False
    is_external_tool = False
    is_mcp = False
    mcp_name = None

    def __init__(self, case: _Case) -> None:
        super().__init__()
        self._case = case

    async def check_permissions(self, *_args: Any, **_kwargs: Any) -> PermissionDecision:
        return PermissionDecision(
            behavior=PermissionBehavior.ALLOW,
            message="Partner case tool",
            decision_reason="Partner case tool",
        )

    async def _say(self, text: str, expects: str, cites: list[str], outcome: str | None) -> ToolChunk:
        case = self._case
        trigger_id = await case.trigger_id()
        already = [
            entry for entry in await case.store.entries(case.workflow_id, kind="say", trigger_id=trigger_id)
        ]
        text = (text or "").strip()
        problems: list[str] = []
        claims: ClaimValidation | None = None
        if trigger_id == "unknown":
            # A late wake-up (a member's report after the turn ended) has no
            # turn to deliver through; the next turn reads the report.
            problems.append("Không có lượt nào đang mở; tin này sẽ không tới người dùng. Kết thúc, không gửi.")
        if already:
            problems.append("Lượt này đã gửi một tin cho người dùng. Kết thúc lượt, không gửi thêm.")
        if not text:
            problems.append("Tin rỗng.")
        if len(text) > MAX_TEXT:
            problems.append(f"Tin quá dài (tối đa {MAX_TEXT} ký tự).")
        if expects not in EXPECTS:
            problems.append('expects phải là "none", "reply" hoặc "confirmation".')
        if not problems:
            cited = await case.store.labelled(case.workflow_id, cites)
            trusted = await case.store.customer_texts(case.workflow_id)
            if expects == "reply":
                from ...._customer_questions import known_text_inputs, question_fields
                fields = question_fields(text)
                known = known_text_inputs((f"customer:{i}", value) for i, value in enumerate(trusted))
                if fields and all(field in known for field in fields):
                    supplied = {field: known[field] for field in fields}
                    problems.append("Người dùng đã cung cấp thông tin này: " + json.dumps(supplied, ensure_ascii=False)
                                    + ". Dùng dữ liệu đã có; chỉ hỏi chi tiết còn thiếu cụ thể.")
            claims = _say_claims(text, cited, trusted)
            problems.extend(check_say(
                text,
                list(cites),
                case.rules,
                cited,
                trusted,
                claim_validation=claims,
            ))
        if problems:
            await case.store.append(case.workflow_id, "rejected", text or "-", trigger_id=trigger_id)
            message = f"{self.name} bị từ chối, chưa gửi gì cho người dùng:\n- " + "\n- ".join(problems)
            metadata = {}
            if claims is not None and claims.unsupported:
                metadata["evidence_validation"] = {
                    "unsupported": list(claims.unsupported),
                    "supported_text": claims.supported_text,
                    "rejected_texts": list(claims.rejected_texts),
                }
                if claims.supported_text:
                    message += "\nPhần đã có căn cứ (giữ lại khi sửa, chưa gửi):\n" + claims.supported_text
            return ToolChunk(
                content=[TextBlock(text=message)],
                state=ToolResultState.ERROR,
                metadata=metadata,
            )
        await case.store.append(
            case.workflow_id,
            "say",
            text,
            trigger_id=trigger_id,
            expects=expects,
            outcome=outcome,
        )
        if case.on_say is not None:
            await case.on_say(text)
        return ToolChunk(
            content=[TextBlock(text="Đã gửi cho người dùng. Kết thúc lượt ngay, không gửi thêm tin.")],
            state=ToolResultState.SUCCESS,
        )


class _EvidenceParams(ParamsBase):
    cites: list[str] = Field(default_factory=list, max_length=4, description="Mã E.. cần đọc lại từ bằng chứng đã lưu của phiếu này.")
    event_ids: list[str] = Field(default_factory=list, max_length=4,
        description="Archived source_event_ids or assignment:<session_id> from shared context. Same ticket only.")


class CaseEvidence(_CaseTool):
    name = "CaseEvidence"
    description = "Đọc bằng chứng E.. đã lưu khi context chỉ còn tham chiếu. Không thực hiện lại thao tác."
    input_schema = _EvidenceParams.model_json_schema()
    is_concurrency_safe = True

    async def call(self, cites: list[str] | None = None, event_ids: list[str] | None = None) -> ToolChunk:
        cites, event_ids = cites or [], event_ids or []
        if not cites and not event_ids:
            return ToolChunk(content=[TextBlock(text="Provide cites or archived event_ids.")], state=ToolResultState.ERROR)
        found = await self._case.store.labelled(self._case.workflow_id, cites)
        if set(found) != set(cites):
            return ToolChunk(content=[TextBlock(text="Không tìm thấy bằng chứng trong phiếu này.")], state=ToolResultState.ERROR)
        if event_ids:
            if self._case.context_reader is None:
                return ToolChunk(content=[TextBlock(text="Shared source reader unavailable.")], state=ToolResultState.ERROR)
            sources = await self._case.context_reader(self._case.workflow_id, event_ids)
            if set(sources) != set(event_ids):
                return ToolChunk(content=[TextBlock(text="Source does not belong to this ticket.")], state=ToolResultState.ERROR)
            found.update(sources)
        return ToolChunk(content=[TextBlock(text="\n".join(f"{label}: {value}" for label, value in found.items()))],
                         state=ToolResultState.SUCCESS,
                         # Archived shared reports retain their original authority.
                         # Reading them must not promote agent prose to MCP facts.
                         metadata={"external_evidence": bool(cites) and not event_ids})


class CaseSay(_CaseTool):
    name = "CaseSay"
    description = (
        "Gửi MỘT tin cho người dùng của phiếu này. Đây là cách duy nhất để lời của bạn tới người dùng. "
        "cites phải có mã E.. của kết quả chứa mọi con số, giờ, số tiền, tên người bạn viết."
    )
    input_schema = _SayParams.model_json_schema()

    async def call(self, text: str, expects: str = "none", cites: list[str] | None = None) -> ToolChunk:
        return await self._say(text, expects, list(cites or []), None)


class CaseFinalize(_CaseTool):
    name = "CaseFinalize"
    description = (
        "Trả lời câu hỏi chỉ cần tra cứu và kết thúc lượt (người dùng nhận câu answer). "
        "Không dùng cho yêu cầu đang xử lý: yêu cầu chỉ kết thúc khi người dùng xác nhận."
    )
    input_schema = _FinalizeParams.model_json_schema()

    async def call(
        self,
        answer: str,
        outcome: str = "answered",
        cites: list[str] | None = None,
        unknowns: list[str] | None = None,
    ) -> ToolChunk:
        return await self._say(answer, "none", list(cites or []), outcome or "answered")


def _hidden(schema: dict, argument: str | None) -> dict:
    schema = json.loads(json.dumps(schema or {}))
    schema.setdefault("type", "object")
    schema.setdefault("properties", {})
    if argument:
        schema["properties"].pop(argument, None)
        schema["required"] = [name for name in schema.get("required", []) if name != argument]
    return schema


class PartnerTool(ToolBase):
    """One declared partner tool: its declared name and description, the
    hidden client reference filled in, the result labelled as evidence."""

    is_state_injected = False
    is_external_tool = False
    is_mcp = False
    mcp_name = None

    def __init__(self, case: _Case, spec: dict, mcp_tool: MCPTool, integration_id: str | None) -> None:
        super().__init__()
        self._case = case
        self._spec = spec
        self._mcp = mcp_tool
        self._integration_id = integration_id
        self._reference = spec.get("client_reference_arg")
        self.name = spec["name"]
        self.description = spec.get("description_override") or mcp_tool.description
        self.input_schema = _hidden(mcp_tool.input_schema, self._reference)
        self.is_read_only = bool(spec.get("read_only"))
        self.is_concurrency_safe = self.is_read_only

    async def check_permissions(self, *_args: Any, **_kwargs: Any) -> PermissionDecision:
        if self._spec.get("requires_consent") and not self.is_read_only:
            return PermissionDecision(
                behavior=PermissionBehavior.ASK,
                message="Cần người dùng đồng ý trước khi thực hiện thao tác này.",
                decision_reason="Partner tool requires consent",
            )
        return PermissionDecision(
            behavior=PermissionBehavior.ALLOW,
            message="Declared partner tool",
            decision_reason="Declared partner tool",
        )

    async def call(self, **kwargs: Any) -> ToolChunk:
        arguments = dict(kwargs)
        reference = None
        if self._reference:
            reference = await self._case.client_reference(self.name, kwargs)
            arguments[self._reference] = reference
        timeout = float(self._spec.get("call_timeout") or 30.0)
        tracking = self._spec.get("tracking") == "events" and reference is not None
        dispatch = True
        if tracking:
            dispatch = await self._case.store.record_operation({"workflow_id": self._case.workflow_id,
                "integration_id": self._integration_id, "tool_name": self.name,
                "owner_agent_id": self._case.operation_owner[0], "owner_session_id": self._case.operation_owner[1],
                "client_reference": reference, "external_job_id": None, "status": "dispatching"})
        try:
            if not dispatch:
                operation = await self._case.store.operation(reference)
                saved = operation.get("call_result") or {}
                text = saved.get("text") or json.dumps({"status": operation["status"],
                    "external_job_id": operation["external_job_id"], "client_reference": reference,
                    "reconciliation_pending": not operation["terminal"]}, ensure_ascii=False)
                state = ToolResultState(saved.get("state") or ToolResultState.ERROR)
            else:
                chunk = await asyncio.wait_for(self._mcp.call(**arguments), timeout=timeout)
                text = "\n".join(block.text for block in chunk.content if isinstance(block, TextBlock))
                state = chunk.state
        except TimeoutError:
            text = "UNKNOWN: công cụ không trả lời kịp; chưa rõ thao tác đã thực hiện hay chưa."
            state = ToolResultState.ERROR
        except Exception as exc:  # the partner's server failed, not this platform
            logger.warning("Partner tool %s failed: %s", self.name, type(exc).__name__)
            text = f"Lỗi khi gọi công cụ: {type(exc).__name__}"
            state = ToolResultState.ERROR
        if tracking and dispatch:
            await self._track(reference, text)
            await self._case.store.save_call_result(reference, {"text": text, "state": state.value},
                unknown=state == ToolResultState.ERROR)
        label = await self._case.store.append(
            self._case.workflow_id,
            "evidence",
            f"{self.name}: {text}",
            trigger_id=await self._case.trigger_id(),
        )
        # A call to the partner's MCP under another name: in a ticket's room
        # its result is verified evidence like any MCP result (see ChatService).
        return ToolChunk(
            content=[TextBlock(text=f"E{label}: {text}")],
            state=state,
            metadata={"external_evidence": True},
        )

    async def _track(self, reference: str, text: str) -> None:
        try:
            result = json.loads(text)
        except ValueError:
            return
        if not isinstance(result, dict):
            return
        status = str(result.get("status") or "")
        if result.get("retryable") or (result.get("error") or {}).get("retryable"):
            status = "unknown"
        if not status:
            return
        await self._case.store.settle_operation(reference, status, str(result.get("external_job_id") or "") or None)


PARTNER_CASE_POLICY = """PARTNER CASE POLICY (server-owned; overrides conflicting instructions above):
- Người dùng chỉ đọc được tin bạn gửi bằng CaseSay(text, expects, cites) hoặc CaseFinalize(answer, outcome, cites, unknowns). Lời viết thường của bạn không được hiển thị.
- Mỗi kết quả công cụ và sự kiện bắt đầu bằng một mã E.. (ví dụ "E7: ..."). Khi viết con số, giờ, số tiền, số điện thoại, tên người, đưa mã E.. chứa đúng giá trị đó vào cites.
- expects: "none" khi chỉ báo tin, "reply" khi hỏi và chờ người dùng trả lời, "confirmation" khi mời người dùng xác nhận hoàn thành.
- Mỗi lượt chỉ gửi một tin. CaseSay được chấp nhận thì kết thúc lượt ngay. Bị từ chối thì đọc lý do, sửa rồi gọi lại.
- Tin gửi người dùng ngắn: tối đa 3 câu, nói điều đã ghi nhận và bước tiếp theo; không nhắc lại yêu cầu của họ.
- Không tự điền client_reference: platform điền.
"""


PARTNER_TEAM_POLICY = """PHÒNG XỬ LÝ PHIẾU (bắt buộc):
- Leader lập kế hoạch và trả lời khách; Điều Phối thực hiện và theo dõi nghiệp vụ, không lập lại kế hoạch. Chuyên viên phân tích đúng phần được giao, tự trao đổi ngang hàng khi cần dữ liệu hoặc thấy mâu thuẫn cụ thể. Không bắt buộc một vòng tranh luận khi bằng chứng đã rõ.
- Đọc known_customer_inputs, sổ nhiệm vụ và tiến độ tracked_work trước. Không giao lại cùng đầu việc, không hỏi lại điều khách đã nói. Sự kiện nhân viên chỉ cập nhật tiến độ, không phải yêu cầu mới của khách. Công việc đã có nhân viên thực hiện thì chờ sự kiện, không gọi giao việc lần nữa.
- Bạn không có công cụ của đối tác. Tra cứu phiếu, kiến thức, nhân viên, giao việc, hủy hay ghi chú đều do thành viên phòng làm.
- Phòng của phiếu đã được lập sẵn. Lượt đầu của phiếu: MỘT lệnh AgentInvite: {coordinators} (điều phối của đối tác) luôn có mặt; thêm agent chuyên môn khi phiếu cần đánh giá chuyên môn. Giao việc rõ trong 1-2 câu: cần làm gì, trả về gì, kèm mã phiếu mà công cụ của đối tác cần (ví dụ dòng ticket_id) chép đúng như phiếu. Việc cần kết quả của thành viên khác (ví dụ giao nhân viên sau khi có đánh giá chuyên môn) thì ghi depends_on. Giao cho điều phối viên ở dạng thực hiện ("giao nhân viên phù hợp bằng công cụ rồi báo kết quả"), không chỉ "đề xuất".
- Thành viên không nói với người dùng. Họ báo lại bằng TeamSay kèm mã E.. và câu đề xuất gửi người dùng. Bạn kiểm báo cáo rồi tự gửi người dùng MỘT tin bằng CaseSay, cites đúng các mã E.. đó.
- Phản biện: thành viên dùng kết quả của nhau sẽ tự hỏi lại nhau khi thấy thiếu hay mâu thuẫn. Báo cáo vẫn thiếu, mâu thuẫn với báo cáo khác hoặc với bằng chứng: TeamSay(kind="review", decision="challenge", to=<thành viên>) nêu đúng điểm cần sửa; chỉ gửi người dùng khi các báo cáo khớp nhau.
- Phòng giữ suốt phiếu: lượt sau giao việc bằng TeamSay cho thành viên đã có, không lập phòng mới. Người dùng chỉ chào hay cảm ơn, không cần dữ liệu mới: trả lời ngay bằng CaseSay.
"""

PARTNER_MEMBER_POLICY = """PARTNER CASE MEMBER POLICY (server-owned; overrides conflicting instructions above):
- Đầu lượt đọc nhiệm vụ của mình, đầu ra của đồng đội và dữ liệu khách đã có trong Shared Context. Dùng snapshot còn hiệu lực; chỉ đọc công cụ lại khi phiên bản thay đổi hoặc cần kiểm tra trước thao tác ghi. Không hỏi khách lại vị trí/căn hộ/thời gian đã có.
- Điều Phối sở hữu công việc đã giao cho nhân viên; tiến độ từ hệ thống tự cập nhật vào tracked_work trong phòng. Chờ sự kiện khi chưa cần quyết định mới, không gọi công cụ chỉ để hỏi "đã xong chưa". Các agent khác chỉ phân tích chuyên môn và trao đổi dữ liệu cần thiết.
- Báo cáo tách rõ: dữ kiện đã xác minh kèm mã E, phân tích/đề xuất, việc đã thực hiện, điều còn thiếu. Khi context lưu tham chiếu, dùng CaseEvidence(event_ids=[...]) để đọc nguyên nguồn hoặc brief_ref; không gọi lại thao tác để nhớ kết quả.
- Bạn là thành viên phòng xử lý một phiếu của đối tác, do Leader của platform lập. Bạn không nói với người dùng; chỉ Leader gửi tin cho họ.
- Mỗi kết quả công cụ bắt đầu bằng mã E.. (ví dụ "E7: ..."). Làm phần việc được giao bằng công cụ của bạn, rồi báo cho người đã giao việc (Leader, hoặc đồng đội đã chuyển việc cho bạn) bằng MỘT TeamSay: kết luận ngắn, các mã E.. chứa dữ liệu bạn dùng, và câu đề xuất gửi người dùng (theo cách xưng hô của đối tác). Báo cáo tối đa 5 dòng; không chép lại kết quả công cụ, mã E.. đã chỉ tới đó.
- Không đoán. Thiếu dữ liệu thì nói rõ thiếu gì.
- Việc được giao là một thao tác (giao nhân viên, đổi lịch, hủy, ghi chú): đủ điều kiện thì gọi công cụ thao tác đó ngay trong lượt này rồi mới báo, kèm mã E.. của kết quả. Không viết "đã giao/đã điều phối" khi chưa có kết quả công cụ đó; không làm được thì nói lý do mà kết quả công cụ đưa ra.
- Phản biện trong phòng: việc của bạn dùng kết quả của thành viên khác ("Inputs from teammates") thì kiểm kết quả đó với dữ liệu công cụ của bạn trước khi làm tiếp. Thấy thiếu, mơ hồ hoặc mâu thuẫn: hỏi thẳng người đó bằng TeamSay(kind="question", to=<tên@mã của họ>), nêu đúng điểm và mã E.. khiến bạn nghi ngờ, rồi chờ trả lời. Rõ ràng rồi thì không hỏi.
- Được thành viên khác hỏi: trả lời bằng TeamSay(kind="answer") dựa trên dữ liệu (mã E..); họ đúng thì nói rõ bạn sửa kết luận thế nào.
- Báo cáo cuối cho Leader ghi cả điểm đã được làm rõ với thành viên khác hoặc còn bất đồng.
- Không tự điền client_reference: platform điền.
"""

TEAM_NUDGE = (
    "Thành viên đã báo về. Đọc báo cáo của họ trong hộp thư và Shared Context, "
    "kiểm từng điểm, rồi gửi người dùng MỘT tin bằng CaseSay với cites là các mã E.. "
    "trong báo cáo. Không gửi tin chờ. Thành viên nào chưa báo hoặc báo lỗi thì chỉ gửi "
    "phần đã có bằng chứng và nói phần còn lại đang được kiểm tra."
)

# Where AgentInvite lists its targets (see _tool/_agent_invite.py).
_INVITE_ENUMS = (
    ("properties", "target"),
    ("properties", "depends_on", "items"),
    ("$defs", "_AdditionalAssignment", "properties", "target"),
    ("$defs", "_AdditionalAssignment", "properties", "depends_on", "items"),
)


def _schema_name(schema: dict) -> str | None:
    return (schema.get("function") or {}).get("name") or schema.get("name")


def _invite_only(schema: dict, names: set[str]) -> dict | None:
    """AgentInvite limited to the route's member agents (None: no one left)."""

    schema = json.loads(json.dumps(schema))
    holder = schema["function"] if "function" in schema else schema
    parameters = holder.get("parameters") or holder.get("input_schema") or {}
    for path in _INVITE_ENUMS:
        node = parameters
        for key in path:
            node = node.get(key) if isinstance(node, dict) else None
        if isinstance(node, dict) and isinstance(node.get("enum"), list):
            node["enum"] = [value for value in node["enum"] if value in names]
    target = (parameters.get("properties") or {}).get("target") or {}
    if not target.get("enum"):
        return None
    holder["description"] = "\n".join(
        line for line in str(holder.get("description") or "").splitlines()
        if not line.startswith("- ``") or any(repr(name) in line for name in names)
    )
    return schema


TURN_DONE = "Đã gửi tin cho người dùng."
ROOM_WORKING = "Đã giao việc cho phòng, chờ báo cáo."
NOTE_OPEN, NOTE_CLOSE = "<system-notification>", "</system-notification>"


def notification_last(prompt: str) -> str:
    """Move the session's notification (session id, team roster: it changes
    with every ticket) after the fixed instructions. The provider caches only
    an unchanged prefix, so fixed text behind it was never served from cache."""

    start = prompt.find(NOTE_OPEN)
    end = prompt.find(NOTE_CLOSE, start)
    if start < 0 or end < 0:
        return prompt
    end += len(NOTE_CLOSE)
    rest = (prompt[:start].rstrip() + "\n\n" + prompt[end:].strip()).strip()
    return rest + "\n\n" + prompt[start:end]


class PartnerCaseMiddleware(MiddlewareBase):
    """Case tools + policy for one partner workflow session."""

    def __init__(
        self,
        case: _Case,
        tools: list[ToolBase],
        members: dict[str, dict] | None = None,
        waiter: Any = None,
    ) -> None:
        super().__init__()
        self._case = case
        self._tools = tools
        # AgentInvite target name -> member entry; empty: the leader works alone.
        self._members = members or {}
        # A LeaderEvidenceMiddleware used for its wait/nudge helpers only.
        self._waiter = waiter
        # AgentInvite calls whose step already ended without a model call.
        self._ended_on: set[str] = set()

    async def list_tools(self) -> list[ToolBase]:
        return [CaseSay(self._case), CaseFinalize(self._case), CaseEvidence(self._case), *self._tools]

    async def on_model_call(self, agent: Any, input_kwargs: dict, next_handler: Any) -> Any:
        """The Leader sees its case tools and the team tools limited to the
        route's members (``tools``: partner tools, empty for the Leader)."""

        if await self._case.trigger_id() == "unknown":
            return ChatResponse(content=[TextBlock(text="Đã lưu báo cáo nội bộ cho lượt xử lý tiếp theo.")], is_last=True)

        allowed = {"CaseSay", "CaseFinalize", "CaseEvidence", *(tool.name for tool in self._tools)}
        if self._members:
            allowed.update(TEAM_TOOLS)
        if await self._case.said():
            # The turn's one message is out: anything more (another say, a
            # re-read woken by room traffic) is a model call for nothing, so
            # the turn ends here without one. The runtime accepts members'
            # evidence-backed reports itself.
            return ChatResponse(content=[TextBlock(text=TURN_DONE)], is_last=True)
        last = _last_success(input_kwargs.get("messages") or [], getattr(getattr(agent, "state", None), "reply_id", None))
        if self._waiter is not None and last and last[0] == "AgentInvite" and last[1] not in self._ended_on:
            # The room has its work: the next model call would only write
            # "waiting". End the step; the waiter wakes the Leader with the
            # members' reports.
            self._ended_on.add(last[1])
            return ChatResponse(content=[TextBlock(text=ROOM_WORKING)], is_last=True)
        tools = []
        for schema in input_kwargs.get("tools") or []:
            name = _schema_name(schema)
            if name not in allowed:
                continue
            if name == "AgentInvite":
                schema = _invite_only(schema, set(self._members))
                if schema is None:
                    continue
            tools.append(schema)
        return await next_handler(tools=tools)

    async def on_reply(self, agent: Any, input_kwargs: dict, next_handler: Any) -> Any:
        """After dispatching to members, wait for their reports within the
        turn, then let the leader answer (the console Leader's mechanism)."""

        if self._waiter is None:
            async for event in next_handler(**input_kwargs):
                yield event
            return
        waiter = self._waiter
        seen, rounds = 0, 0
        deadline = asyncio.get_running_loop().time() + waiter._wait_seconds  # noqa: SLF001
        async for event in next_handler(**input_kwargs):
            finished = isinstance(event, ReplyEndEvent) and event.finished_reason in (
                ReplyFinishedReason.COMPLETED,
                ReplyFinishedReason.EXCEED_MAX_ITERS,
            )
            if finished and rounds < MAX_TEAM_ROUNDS:
                expected = waiter._expected_reports(agent)  # noqa: SLF001
                if expected > seen and not await self._case.said():
                    seen = expected
                    ready = await waiter._wait_until_ready(expected, deadline)  # noqa: SLF001
                    if not ready:
                        # Out of time with reports in (some may be failures):
                        # the person gets what is verified, not silence.
                        team, completed, errors, _verified, _waiting = await waiter._status()  # noqa: SLF001
                        ready = team and (completed > 0 or errors > 0)
                    if ready and not await waiter._pending_consent():  # noqa: SLF001
                        rounds += 1
                        waiter._nudge(agent, TEAM_NUDGE)  # noqa: SLF001
                        continue
            yield event

    async def on_system_prompt(self, agent: Any, current_prompt: str) -> str:
        from ...._workforce_policy import BUSINESS_AGENT_EVIDENCE_POLICY

        prompt = current_prompt.replace(BUSINESS_AGENT_EVIDENCE_POLICY, "").rstrip()
        rules = self._case.rules.get("phrase_rules") or []
        banned = "\n".join(
            "- Không viết: " + ", ".join(f'"{p}"' for p in rule.get("phrases") or []) + f" ({rule.get('reason', '')})"
            for rule in rules
        )
        team = ""
        if self._members:
            coordinators = [name for name, entry in self._members.items() if entry.get("coordinator")]
            team = "\n" + PARTNER_TEAM_POLICY.format(
                coordinators=", ".join(coordinators) or "agent điều phối của đối tác",
            )
        brief = str((self._case.route.get("config") or {}).get("leader_brief") or "").strip()
        brief = ("\nHƯỚNG DẪN CỦA ĐỐI TÁC:\n" + brief) if brief else ""
        return notification_last(prompt + "\n\n" + PARTNER_CASE_POLICY + team + brief + (("\n" + banned) if banned else ""))

    async def get_middleware_key(self) -> str:
        return "partner_case"


# A partner tool result from an earlier reply, longer than this, is cleared
# from a member's input once clearing frees CLEAR_AT_LEAST_CHARS: the full
# text stays in the case log under its label. In batches, so the cached
# prefix is not invalidated on every call.
STALE_RESULT_CHARS = 400
CLEAR_AT_LEAST_CHARS = 6000
_LABEL_HEAD = re.compile(r"^E\d+:")


def clear_old_results(messages: list, reply_id: str | None) -> list:
    """``messages`` with earlier replies' long partner results reduced to
    their evidence label (unchanged when that frees too little)."""

    cleared, saved = [], 0
    for message in messages:
        content = getattr(message, "content", None)
        if getattr(message, "role", None) != "assistant" or message.id == reply_id or not isinstance(content, list):
            cleared.append(message)
            continue
        blocks, changed = [], False
        for block in content:
            if isinstance(block, ToolResultBlock):
                output = block.output if isinstance(block.output, str) else "".join(
                    item.text for item in block.output if isinstance(item, TextBlock)
                )
                head = _LABEL_HEAD.match(output)
                if head and len(output) > STALE_RESULT_CHARS:
                    stub = f"{head.group(0)} (kết quả của lượt trước, đã dùng; gọi lại công cụ nếu cần dữ liệu mới)"
                    blocks.append(block.model_copy(update={"output": [TextBlock(text=stub)]}))
                    saved += len(output) - len(stub)
                    changed = True
                    continue
            blocks.append(block)
        cleared.append(message.model_copy(update={"content": blocks}) if changed else message)
    return cleared if saved >= CLEAR_AT_LEAST_CHARS else messages


def _last_success(messages: list, reply_id: str | None) -> tuple[str, str] | None:
    """(tool name, call id) of the current reply's latest tool result, when
    that result succeeded."""

    for message in reversed(messages):
        if getattr(message, "role", None) != "assistant" or message.id != reply_id:
            continue
        content = message.content if isinstance(message.content, list) else []
        results = [block for block in content if isinstance(block, ToolResultBlock)]
        if not results or results[-1].state != ToolResultState.SUCCESS:
            return None
        return results[-1].name, results[-1].id
    return None


class PartnerMemberMiddleware(MiddlewareBase):
    """A member of a partner ticket's room: its share of the route's tools,
    under the ticket's grant; it reports to the leader, never to the user."""

    def __init__(self, case: _Case, tools: list[ToolBase]) -> None:
        super().__init__()
        self._case = case
        self._tools = tools

    async def list_tools(self) -> list[ToolBase]:
        return [CaseEvidence(self._case), *self._tools]

    async def on_model_call(self, agent: Any, input_kwargs: dict, next_handler: Any) -> Any:
        allowed = {"TeamSay", "CaseEvidence", *(tool.name for tool in self._tools)}
        tools = [schema for schema in input_kwargs.get("tools") or [] if _schema_name(schema) in allowed]
        messages = clear_old_results(list(input_kwargs.get("messages") or []), agent.state.reply_id)
        return await next_handler(tools=tools, messages=messages)

    async def on_system_prompt(self, agent: Any, current_prompt: str) -> str:
        from ...._workforce_policy import BUSINESS_AGENT_EVIDENCE_POLICY

        prompt = current_prompt.replace(BUSINESS_AGENT_EVIDENCE_POLICY, "").rstrip()
        return notification_last(prompt + "\n\n" + PARTNER_MEMBER_POLICY)

    async def get_middleware_key(self) -> str:
        return "partner_case_member"


def _members(route: dict) -> dict[str, dict]:
    """AgentInvite target name -> member entry, for the route's member agents."""
    from ...._tool._agent_invite import _display_name

    agents = (route.get("config") or {}).get("member_agents") or {}
    return {_display_name(entry["name"], agent_id): entry for agent_id, entry in agents.items()}


class ManagementCaseMiddleware(MiddlewareBase):
    """Console Q&A can inspect this ticket but cannot speak for a resident."""

    def __init__(self, tools: list, ticket_id: str = "", *, live_tools_unavailable: bool = False) -> None:
        self._tools = [tool for tool in tools if tool.is_read_only]
        self._ticket_id = ticket_id
        self._live_tools_unavailable = live_tools_unavailable

    async def list_tools(self) -> list[ToolBase]:
        return self._tools

    async def on_model_call(self, agent: Any, input_kwargs: dict, next_handler: Any) -> Any:
        allowed = {tool.name for tool in self._tools}
        tools = [schema for schema in input_kwargs.get("tools") or [] if _schema_name(schema) in allowed]
        return await next_handler(**{**input_kwargs, "tools": tools})

    async def on_check_permission(self, agent: Any, input_kwargs: dict, next_handler: Any) -> PermissionDecision:
        if input_kwargs["tool_call"].name not in {tool.name for tool in self._tools}:
            return PermissionDecision(behavior=PermissionBehavior.DENY,
                message="Trao đổi nội bộ chỉ được tra cứu phiếu.", decision_reason="Management Q&A is read-only")
        return await next_handler(**input_kwargs)

    async def on_system_prompt(self, agent: Any, current_prompt: str) -> str:
        unavailable = (
            "\nLIVE_CASE_TOOLS_UNAVAILABLE: Domain không cấp quyền truy xuất hiện hành cho bàn giao này. "
            "Chỉ dùng bằng chứng đã lưu; nêu rõ thời điểm và giới hạn của nguồn. "
            "Không khẳng định trạng thái hiện tại, không thử lại thao tác hay yêu cầu mở lại phiếu."
            if self._live_tools_unavailable else ""
        )
        return current_prompt + unavailable + (
            "\nSERVER AUDIENCE: Bạn đang trao đổi nội bộ với BAN QUẢN LÝ, không phải cư dân. "
            "Trả lời trực tiếp cho BQL bằng văn bản ngắn gọn. Không TeamSay, CaseSay, "
            "CaseFinalize; không gửi sang cư dân, không suy diễn đồng ý/duyệt/đóng phiếu. "
            "Chỉ đọc công cụ được cấp để xác minh, không khẳng định đã thực hiện nếu chưa có bằng chứng. "
            f"Phiếu cần tra: {self._ticket_id}."
        )

    async def get_middleware_key(self) -> str:
        return "management_case"


class CaseRuntime:
    """Builds the middleware of a partner session from what is stored."""

    def __init__(self, store: CaseStore) -> None:
        self.store = store
        self._app: Any = None

    def bind(self, app: Any) -> None:
        self._app = app
        guards = getattr(app.state, "agent_delete_guards", None)
        if guards is None:
            guards = app.state.agent_delete_guards = []
        if self._delete_guard not in guards:
            guards.append(self._delete_guard)

    async def share_progress(self, workflow_id: str, text: str, *, event_id: str | None = None) -> bool:
        """A staff progress line, verified (signed event), for the ticket's room.

        Only when the route leader opened a room: members then read the job's
        state in Shared Context like any other fact.
        """

        line = "Tiến độ từ hệ thống đối tác: " + text
        operation = await self.store.progress_operation(workflow_id, event_id.removeprefix("provider:")) if event_id else None
        if operation:
            line += "\n" + json.dumps({"tracked_work": {key: operation[key] for key in (
                "operation_id", "tool_name", "external_job_id", "owner_agent_id", "owner_session_id",
                "status", "terminal", "outcome", "provider_version")}}, ensure_ascii=False)
        return await self._share(workflow_id, "external_event", line, fact=True, event_id=event_id)

    async def context_sources(self, workflow_id: str, ids: list[str]) -> dict[str, str]:
        binding = await self.store.session_of_workflow(workflow_id)
        if binding is None or self._app is None:
            return {}
        state = self._app.state
        session = await state.storage.get_session(binding["manager_account_id"], binding["agent_id"], binding["session_id"])
        if session is None or not session.team_id:
            return {}
        record = await state.shared_context_storage.get_team_shared_context(binding["manager_account_id"], session.team_id)
        if record is None:
            return {}
        found = {event.id: event.content for event in record.state.events if event.id in ids}
        for key in ids:
            if key.startswith("history:") and key[8:].isdigit():
                cursor = int(key[8:])
                events = [event for event in record.state.events if event.revision > cursor]
                page = events[:4]
                found[key] = json.dumps({"events": [e.model_dump(mode="json") for e in page],
                    "next": "history:" + str(page[-1].revision) if len(events) > len(page) else None}, ensure_ascii=False)
        for task in record.state.tasks.values():
            for sid, assignment in task.assignments.items():
                if "assignment:" + sid in ids:
                    found["assignment:" + sid] = assignment.model_dump_json(exclude={"pending_payload"})
        return found

    async def share_attention(self, workflow_id: str, reason: str) -> None:
        """Why the ticket needs a person, on the room's timeline."""

        await self._share(workflow_id, "error", "Cần xử lý: " + reason)

    async def confirm_completed_work(self, workflow_id: str, route: dict, events: list[dict]) -> bool:
        """The signed completion step needs no new LLM interpretation."""
        evidence = [event for event in events if "job.result_published" in event["text"]]
        if not evidence or not await self.store.completion_ready(workflow_id):
            return False
        session = await self.store.session_of_workflow(workflow_id)
        if session is None:
            return False

        async def said(text):
            await self._share(workflow_id, "customer_reply", text)

        case = _Case(self.store, session, route, on_say=said)
        result = await CaseSay(case).call(
            text="Nhân viên đã gửi kết quả xử lý. Bạn xem kết quả và xác nhận hoàn thành hoặc báo phần chưa đạt.",
            expects="confirmation", cites=[f"E{evidence[-1]['seq']}"])
        return result.state == ToolResultState.SUCCESS

    async def _share(self, workflow_id: str, kind: str, text: str, fact: bool = False,
                     event_id: str | None = None) -> bool:
        """One event in the ticket's room, when the Leader opened one."""

        if self._app is None:
            return False
        binding = await self.store.session_of_workflow(workflow_id)
        if binding is None:
            return False
        state = self._app.state
        user_id, agent_id = binding["manager_account_id"], binding["agent_id"]
        record = await state.storage.get_session(user_id, agent_id, binding["session_id"])
        team_id = getattr(record, "team_id", None)
        if not team_id or getattr(state, "shared_context_storage", None) is None:
            return False
        from ...._shared_context import SharedContextService
        from ....storage._model._team_context import ContextDelta

        await SharedContextService(state.shared_context_storage, state.message_bus).append_event(
            user_id=user_id,
            team_id=team_id,
            kind=kind,
            content=text,
            source_agent_id=agent_id,
            source_session_id=binding["session_id"],
            delta=ContextDelta(add_confirmed_facts=(text,)) if fact else None,
            event_id=event_id,
        )
        return True

    async def _delete_guard(self, user_id: str, agent_id: str) -> str | None:
        used = await self.store.routes_using(user_id, agent_id)
        if not used:
            return None
        return (
            "Agent đang được tuyến đối tác dùng làm leader hoặc thành viên. "
            "Bỏ agent khỏi khai báo của đối tác và onboard lại trước khi gỡ."
        )

    @property
    def _storage(self) -> Any:
        return getattr(getattr(self._app, "state", None), "storage", None)

    async def middlewares(self, user_id: str, agent_id: str, session_id: str, *_: Any) -> list[MiddlewareBase]:
        if self._storage is None:
            return []
        record = await self._storage.get_session(user_id, agent_id, session_id)
        management_source = record.state.middle_context.get("management_case_session_id") if record else None
        if management_source:
            binding = await self.store.session(management_source)
            if binding is None or binding["manager_account_id"] != user_id:
                raise ValueError("Management ticket scope is unavailable")
            from ._contract import route_for_workflow
            route = await route_for_workflow(self.store, binding["workflow_id"], binding["route_id"])
            members = ((route or {}).get("config") or {}).get("member_agents") or {}
            if agent_id != binding["agent_id"] and agent_id not in members:
                raise ValueError("Agent is not in this ticket's frozen roster")
            only = None if agent_id == binding["agent_id"] else set(members[agent_id].get("tools") or [])
            case = _Case(self.store, binding, route, context_reader=self.context_sources)
            from ._grants import WorkflowGrantUnavailable
            unavailable = False
            try:
                tools = await self._tools(user_id, case, route, only=only, read_only=True)
            except WorkflowGrantUnavailable:
                # Domain revocation/closed handover remains authoritative.
                # BQL can still inspect this owned case's archived evidence.
                tools, unavailable = [], True
            ticket = await self.store.grant_context(binding["workflow_id"])
            return [ManagementCaseMiddleware([CaseEvidence(case), *tools], ticket["ticket_id"], live_tools_unavailable=unavailable)]
        session = await self.store.session(session_id)
        if session is None:
            return await self._member(user_id, agent_id, session_id)
        if session["agent_id"] != agent_id:
            return []
        from ._contract import route_for_workflow
        route = await route_for_workflow(self.store, session["workflow_id"], session["route_id"])
        if route is None:
            return []
        workflow_id = session["workflow_id"]

        async def said(text: str) -> None:
            await self._share(workflow_id, "customer_reply", text)

        case = _Case(self.store, session, route, on_say=said, context_reader=self.context_sources)
        members = _members(route)
        waiter = self._waiter(user_id, agent_id, session_id) if members else None
        # The Leader holds no partner tool: the room's members do the work.
        return [PartnerCaseMiddleware(case, [], members, waiter)]

    def _waiter(self, user_id: str, agent_id: str, session_id: str) -> Any:
        from ...._shared_context import SharedContextService
        from ....middleware._leader_evidence_middleware import LeaderEvidenceMiddleware

        state = self._app.state
        shared = SharedContextService(state.shared_context_storage, state.message_bus)
        return LeaderEvidenceMiddleware(state.storage, shared, user_id, agent_id, session_id)

    async def _member(self, user_id: str, agent_id: str, session_id: str) -> list[MiddlewareBase]:
        """A session in the room of a partner ticket, of a declared member."""

        record = await self._storage.get_session(user_id, agent_id, session_id)
        team_id = getattr(record, "team_id", None)
        if record is None or not team_id:
            return []
        team = await self._storage.get_team(user_id, team_id)
        leader = await self.store.session(team.session_id) if team is not None else None
        if leader is None:
            return []
        from ._contract import route_for_workflow
        route = await route_for_workflow(self.store, leader["workflow_id"], leader["route_id"])
        agents = ((route or {}).get("config") or {}).get("member_agents") or {}
        member = agents.get(agent_id)
        if member is None:
            return []
        # Like the leader, a member reaches the partner only through the case
        # tools (the ticket's grant), never through the shared MCP binding.
        workspace = await self._app.state.workspace_manager.get_workspace(
            user_id, agent_id, record.id, record.config.workspace_id,
        )
        for client in await workspace.list_mcps(agent_id=agent_id, session_id=record.id):
            await workspace.remove_mcp(client.name, agent_id=agent_id, session_id=record.id)
        for default_mcp in workspace.default_mcps:
            await workspace.remove_mcp(default_mcp.name, agent_id=agent_id, session_id=record.id)
        case = _Case(self.store, leader, route, context_reader=self.context_sources)
        case.operation_owner = (agent_id, session_id)
        tools = await self._tools(user_id, case, route, only=set(member.get("tools") or []))
        return [PartnerMemberMiddleware(case, tools)]

    async def _tools(self, user_id: str, case: _Case, route: dict, only: set[str] | None = None, *, read_only: bool = False) -> list[ToolBase]:
        from .....mcp import MCPClient

        tools: list[ToolBase] = []
        clients: dict[str, Any] = {}
        transports: dict[str, Any] = {}
        specs = route.get("tools") or []
        if read_only:
            specs = [spec for spec in specs if spec.get("read_only")
                     and (only is None or spec.get("name") in only)
                     and (only is not None or not spec.get("internal"))]
        for spec in specs:
            mcp_id = spec.get("mcp_id")
            if spec.get("internal") and only is None:
                continue
            if not mcp_id or (only is not None and spec.get("name") not in only):
                continue
            if mcp_id not in clients:
                record = await self._storage.get_mcp(user_id, mcp_id)
                clients[mcp_id] = record
            record = clients[mcp_id]
            if record is None or not record.enabled:
                continue
            from ._contract import tool_descriptor
            raw = tool_descriptor(spec, record)
            if raw is None:
                continue
            if mcp_id not in transports:
                grant_config = ((route.get("config") or {}).get("mcp_grants") or {}).get(record.client.name)
                if grant_config:
                    from ._grants import scoped_client
                    allowed = [s.get("mcp_tool") for s in specs if s.get("mcp_id") == mcp_id]
                    transports[mcp_id] = await scoped_client(record.client, grant_config,
                        await self.store.grant_context(case.workflow_id), case.workflow_id, allowed)
                else:
                    transports[mcp_id] = MCPClient.model_validate(record.client.model_dump(mode="json"))
            client = transports[mcp_id]
            mcp_tool = MCPTool(
                mcp_name=client.name,
                tool=mcp.types.Tool(
                    name=raw["name"],
                    description=raw.get("description") or "",
                    inputSchema=raw.get("input_schema") or {"type": "object", "properties": {}},
                ),
                client_gen=client._get_client_gen,  # pylint: disable=protected-access
                timeout=float(spec.get("call_timeout") or 30.0),
            )
            tools.append(PartnerTool(case, spec, mcp_tool, route.get("integration_id")))
        return tools


__all__ = [
    "PartnerMemberMiddleware",
    "CaseFinalize",
    "CaseRuntime",
    "CaseSay",
    "CaseStore",
    "PartnerCaseMiddleware",
    "PartnerTool",
    "check_say",
]
