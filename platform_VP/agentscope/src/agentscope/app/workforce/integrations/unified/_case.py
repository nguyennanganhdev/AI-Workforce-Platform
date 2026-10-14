"""The partner case runtime of unified mode.

A route onboarded from a partner declaration has its own leader: an Agent
Studio agent that talks to the partner's end user only through ``CaseSay`` /
``CaseFinalize``, calls the route's tools under their declared names (the
platform fills the hidden ``client_reference``), and cites the evidence
labels ``E<n>`` that every tool result and provider event carries.
Everything here is per session and only attached to sessions of partner
workflows (see :class:`CaseRuntime.middlewares`).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

import mcp.types
from pydantic import Field
from sqlalchemy import and_, func, insert, select, update
from sqlalchemy.exc import IntegrityError

from ....._logging import logger
from .....message import TextBlock, ToolResultState
from .....middleware import MiddlewareBase
from .....permission import PermissionBehavior, PermissionDecision
from .....tool import MCPTool, ParamsBase, ToolBase, ToolChunk
from ...orchestration._tables import partner_requests, workflow_inputs
from ._tables import case_entries, case_sessions, operations, routes

EXPECTS = ("none", "reply", "confirmation")
MAX_TEXT = 4000
EVIDENCE_TEXT = 6000
LABEL = re.compile(r"^E(\d+)$")
# Digits with the separators that make one figure: 09:30, 150.000, 20/10/2026.
FIGURE = re.compile(r"\d+(?:[.,:/]\d+)*")


def _now() -> datetime:
    return datetime.now(UTC)


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value)


def _figures(text: str) -> set[str]:
    return {_digits(match) for match in FIGURE.findall(text)}


def check_say(
    text: str,
    cites: list[str],
    rules: dict,
    cited: dict[str, str],
    trusted: list[str],
) -> list[str]:
    """Why ``text`` may not reach the end user (empty list: it may).

    * a phrase the route forbids (``rules.phrase_rules``); a rule's
      ``unless`` phrases lift it when a cited source says them;
    * a figure (time, amount, count, phone) that no cited evidence and no
      message of the end user contains — single digits are free;
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
        if unless and any(item in sources for item in unless):
            continue
        for phrase in rule.get("phrases") or []:
            if str(phrase).lower() in lowered:
                problems.append(f'Không được viết "{phrase}": {rule.get("reason", "")}'.strip())
                break
    known = _figures(" ".join([*cited.values(), *trusted]))
    unknown = sorted(
        figure for figure in _figures(text)
        if figure and len(figure) > 1 and figure not in known
    )
    if unknown:
        problems.append(
            "Các con số/giờ/số tiền sau không có trong bằng chứng đã trích (cites) "
            "hay lời của người dùng: " + ", ".join(unknown)
            + ". Thêm mã E.. chứa đúng con số đó vào cites, hoặc bỏ con số."
        )
    return problems


class CaseStore:
    """Persistence of one partner case (sessions, log, operations)."""

    def __init__(self, uows: Callable[[], Any]) -> None:
        self._uows = uows

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

    async def record_operation(self, values: dict) -> None:
        async with self._uows() as uow:
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
                await uow.commit()

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


class _Case:
    """What the tools of one session need to know at call time."""

    def __init__(self, store: CaseStore, session: dict, route: dict) -> None:
        self.store = store
        self.workflow_id = session["workflow_id"]
        self.session_id = session["session_id"]
        self.route = route
        self.rules = (route.get("config") or {}).get("rules") or {}

    async def trigger_id(self) -> str:
        current = await self.store.session(self.session_id)
        return (current or {}).get("trigger_id") or "unknown"

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
            problems = check_say(
                text,
                list(cites),
                case.rules,
                cited,
                await case.store.customer_texts(case.workflow_id),
            )
        if problems:
            await case.store.append(case.workflow_id, "rejected", text or "-", trigger_id=trigger_id)
            return ToolChunk(
                content=[TextBlock(text=f"{self.name} bị từ chối, chưa gửi gì cho người dùng:\n- " + "\n- ".join(problems))],
                state=ToolResultState.ERROR,
            )
        await case.store.append(
            case.workflow_id,
            "say",
            text,
            trigger_id=trigger_id,
            expects=expects,
            outcome=outcome,
        )
        return ToolChunk(
            content=[TextBlock(text="Đã gửi cho người dùng. Kết thúc lượt ngay, không gửi thêm tin.")],
            state=ToolResultState.SUCCESS,
        )


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
        if tracking:
            await self._case.store.record_operation({"workflow_id": self._case.workflow_id,
                "integration_id": self._integration_id, "tool_name": self.name,
                "client_reference": reference, "external_job_id": None, "status": "dispatching"})
        try:
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
        if tracking:
            await self._track(reference, text)
        label = await self._case.store.append(
            self._case.workflow_id,
            "evidence",
            f"{self.name}: {text}"[:EVIDENCE_TEXT],
            trigger_id=await self._case.trigger_id(),
        )
        return ToolChunk(content=[TextBlock(text=f"E{label}: {text}")], state=state)

    async def _track(self, reference: str, text: str) -> None:
        try:
            result = json.loads(text)
        except ValueError:
            return
        if not isinstance(result, dict):
            return
        status = str(result.get("status") or "")
        if not status:
            return
        await self._case.store.settle_operation(reference, status, str(result.get("external_job_id") or "") or None)


PARTNER_CASE_POLICY = """PARTNER CASE POLICY (server-owned; overrides conflicting instructions above):
- Người dùng chỉ đọc được tin bạn gửi bằng CaseSay(text, expects, cites) hoặc CaseFinalize(answer, outcome, cites, unknowns). Lời viết thường của bạn không được hiển thị.
- Mỗi kết quả công cụ và sự kiện bắt đầu bằng một mã E.. (ví dụ "E7: ..."). Khi viết con số, giờ, số tiền, số điện thoại, tên người, đưa mã E.. chứa đúng giá trị đó vào cites.
- expects: "none" khi chỉ báo tin, "reply" khi hỏi và chờ người dùng trả lời, "confirmation" khi mời người dùng xác nhận hoàn thành.
- Mỗi lượt chỉ gửi một tin. CaseSay được chấp nhận thì kết thúc lượt ngay. Bị từ chối thì đọc lý do, sửa rồi gọi lại.
- Không tự điền client_reference: platform điền.
"""


class PartnerCaseMiddleware(MiddlewareBase):
    """Case tools + policy for one partner workflow session."""

    def __init__(self, case: _Case, tools: list[ToolBase]) -> None:
        super().__init__()
        self._case = case
        self._tools = tools

    async def list_tools(self) -> list[ToolBase]:
        return [CaseSay(self._case), CaseFinalize(self._case), *self._tools]

    async def on_model_call(self, agent: Any, input_kwargs: dict, next_handler: Any) -> Any:
        """The route leader sees only its case tools and the declared tools.

        The toolkit also offers team tools (TeamCreate, TeamSay, AgentInvite)
        to any session outside a team; a partner leader works alone.
        """

        allowed = {"CaseSay", "CaseFinalize", *(tool.name for tool in self._tools)}

        def name(schema: dict) -> str | None:
            return (schema.get("function") or {}).get("name") or schema.get("name")

        tools = [schema for schema in input_kwargs.get("tools") or [] if name(schema) in allowed]
        return await next_handler(tools=tools)

    async def on_system_prompt(self, agent: Any, current_prompt: str) -> str:
        from ...._workforce_policy import BUSINESS_AGENT_EVIDENCE_POLICY

        prompt = current_prompt.replace(BUSINESS_AGENT_EVIDENCE_POLICY, "").rstrip()
        rules = self._case.rules.get("phrase_rules") or []
        banned = "\n".join(
            "- Không viết: " + ", ".join(f'"{p}"' for p in rule.get("phrases") or []) + f" ({rule.get('reason', '')})"
            for rule in rules
        )
        return prompt + "\n\n" + PARTNER_CASE_POLICY + (("\n" + banned) if banned else "")

    async def get_middleware_key(self) -> str:
        return "partner_case"


class CaseRuntime:
    """Builds the middleware of a partner session from what is stored."""

    def __init__(self, store: CaseStore) -> None:
        self.store = store
        self._app: Any = None

    def bind(self, app: Any) -> None:
        self._app = app

    @property
    def _storage(self) -> Any:
        return getattr(getattr(self._app, "state", None), "storage", None)

    async def middlewares(self, user_id: str, agent_id: str, session_id: str, *_: Any) -> list[MiddlewareBase]:
        session = await self.store.session(session_id)
        if session is None or session["agent_id"] != agent_id or self._storage is None:
            return []
        route = await self.store.route(session["route_id"])
        if route is None:
            return []
        case = _Case(self.store, session, route)
        return [PartnerCaseMiddleware(case, await self._tools(user_id, case, route))]

    async def _tools(self, user_id: str, case: _Case, route: dict) -> list[ToolBase]:
        from .....mcp import MCPClient

        tools: list[ToolBase] = []
        clients: dict[str, Any] = {}
        transports: dict[str, Any] = {}
        for spec in route.get("tools") or []:
            mcp_id = spec.get("mcp_id")
            if not mcp_id:
                continue
            if mcp_id not in clients:
                record = await self._storage.get_mcp(user_id, mcp_id)
                clients[mcp_id] = record
            record = clients[mcp_id]
            if record is None or not record.enabled:
                continue
            raw = next(
                (item for item in record.discovered_tools if item.get("name") == spec.get("mcp_tool")),
                None,
            )
            if raw is None:
                continue
            if mcp_id not in transports:
                grant_config = ((route.get("config") or {}).get("mcp_grants") or {}).get(record.client.name)
                if grant_config:
                    from ._grants import scoped_client
                    allowed = [s.get("mcp_tool") for s in route.get("tools") or [] if s.get("mcp_id") == mcp_id]
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
    "CaseFinalize",
    "CaseRuntime",
    "CaseSay",
    "CaseStore",
    "PartnerCaseMiddleware",
    "PartnerTool",
    "check_say",
]
