"""Python LangGraph business workflow. Inject real ports/model/checkpointer explicitly."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from ..prompts.workflow import RESIDENT_TURN_PROMPT
from .budget import with_budget
from .decision import GraphFault, compact_json, json_value
from .intake import run_intake
from .state import PYTHON_CONTRACT_VERSION, GraphState
from .workflow_contracts import WORKFLOW_VERSION, GraphDependencies, WorkflowOptions
from .workflow_validation import (
    boolean,
    build_handoff,
    choice,
    integer,
    parse_ack,
    parse_incident,
    parse_profile,
    parse_route,
    parse_supervisor_event,
    parse_ticket,
    parse_triage,
    parse_turn,
    record,
    strings,
    text,
)

WORKFLOW_NODES = (
    "receive_message",
    "answer_or_escalate",
    "create_ticket_draft",
    "load_resident_context",
    "collect_incident_details",
    "submit_assessment",
    "resolve_management_destination",
    "handoff_to_supervisor",
    "wait_for_supervisor",
    "active_ticket_dialogue",
    "process_supervisor_event",
    "execute_operation",
    "wait_for_operation",
    "wait_for_resident",
    "human_review",
)


class ReceptionWorkflowFactory:
    contract_version = PYTHON_CONTRACT_VERSION
    state_schema_version = 1

    def __init__(self, options: WorkflowOptions):
        if (
            type(options.timeout_ms) is not int
            or options.timeout_ms <= 0
            or type(options.max_question_attempts) is not int
            or options.max_question_attempts <= 0
        ):
            raise GraphFault("INVALID_WORKFLOW_LIMIT")
        self.options = options

    def create(self, dependencies: GraphDependencies):
        return ReceptionWorkflowGraph(self.options, dependencies)


def create_reception_workflow_factory(
    options: WorkflowOptions,
) -> ReceptionWorkflowFactory:
    return ReceptionWorkflowFactory(options)


class ReceptionWorkflowGraph:
    state_schema_version = 1

    def __init__(self, options: WorkflowOptions, dependencies: GraphDependencies):
        self.options, self.dependencies = options, dependencies
        self.now = options.now or (lambda: datetime.now(timezone.utc).isoformat())
        builder = StateGraph(GraphState)
        for node in WORKFLOW_NODES:
            builder.add_node(node, self._handler(getattr(self, "_" + node)))
        builder.add_edge(START, "receive_message")
        for node in WORKFLOW_NODES:
            builder.add_conditional_edges(
                node, lambda state: state["data"]["next"], list(WORKFLOW_NODES) + [END]
            )
        if dependencies.checkpointer is None:
            raise GraphFault("CHECKPOINTER_REQUIRED")
        self.compiled = builder.compile(checkpointer=dependencies.checkpointer)

    @staticmethod
    def _handler(method):
        async def handler(state: GraphState, config: RunnableConfig):
            return {"data": await method(deepcopy(state["data"]), config)}

        return handler

    @staticmethod
    def _context(config):
        return config["configurable"]["context"]

    @staticmethod
    def _signal(config):
        return config["configurable"].get("signal")

    async def _budget(self, config, run):
        return await with_budget(self.options.timeout_ms, self._signal(config), run)

    @staticmethod
    def _next(data, node):
        return {**data, "next": node}

    @staticmethod
    def _ticket_input(data):
        ticket = data.get("ticket")
        if not ticket or data.get("active_ticket_id") != ticket["ticket_id"]:
            raise GraphFault("ACTIVE_TICKET_REQUIRED")
        return {
            key: ticket[key]
            for key in ("ticket_id", "ticket_generation", "ticket_version")
        }

    @staticmethod
    def _review(data, code):
        return {
            **data,
            "phase": "review",
            "next": "human_review",
            "last_error": code,
            "reply": "Yêu cầu cần người có thẩm quyền xem xét; chưa có xác nhận xử lý hoàn tất.",
        }

    def _ask(self, data, questions):
        fresh = [
            q for q in dict.fromkeys(questions) if q not in data["asked_questions"]
        ]
        if not fresh or data["question_attempts"] >= self.options.max_question_attempts:
            return self._review(data, "UNANSWERED_FIELDS_REVIEW")
        return {
            **data,
            "next": "wait_for_resident",
            "wait_kind": "resident",
            "questions": fresh,
            "asked_questions": data["asked_questions"] + fresh,
            "question_attempts": data["question_attempts"] + 1,
            "reply": "\n".join(fresh),
        }

    @staticmethod
    def _accept_resident(data, source):
        if (
            source.get("kind") != "resident"
            or not source.get("residentKey")
            or not source.get("operationId")
        ):
            raise GraphFault("INVALID_RESIDENT_RESUME")
        return {
            **data,
            "message": source["message"],
            "operation_id": source["operationId"],
            "completed_operations": data["completed_operations"]
            + [source["residentKey"]],
            "turn": None,
            "reply": "",
            "wait_registered": False,
            "next": "receive_message",
        }

    def _plan(self, data, operation, value, after):
        if data.get("pending"):
            raise GraphFault("OPERATION_UNRESOLVED")
        suffix = (
            "draft"
            if operation == "create_ticket_draft"
            else [
                data["message"]["id"],
                (data.get("ticket") or {}).get("ticket_version", ""),
                (data.get("route") or {}).get("route_revision", 0),
                data["last_event_version"],
            ]
        )
        key = compact_json(
            [
                data["reception_binding_id"],
                data["reception_session_id"],
                operation,
                suffix,
            ]
        )
        return {
            **data,
            "next": "execute_operation",
            "pending": {
                "operation": operation,
                "input": json_value(value),
                "after": after,
                "idempotencyKey": key,
            },
        }

    async def _extract(self, data, config):
        response = await self._budget(
            config,
            lambda signal: self.dependencies.model.ainvoke(
                [
                    SystemMessage(content=RESIDENT_TURN_PROMPT),
                    HumanMessage(
                        content=compact_json(
                            {
                                "message": data["message"],
                                "active_incident": data.get("incident"),
                                "pending_interaction": data.get("pending_interaction"),
                            }
                        )
                    ),
                ]
            ),
        )
        return parse_turn(response.content, data["message"]["id"])

    async def _receive_message(self, data, config):
        node = (
            "answer_or_escalate"
            if not data.get("active_ticket_id")
            else "load_resident_context"
            if not data.get("verified_profile")
            else "collect_incident_details"
            if not data.get("ack")
            else "active_ticket_dialogue"
        )
        return self._next(data, node)

    async def _answer_or_escalate(self, data, config):
        try:
            intake = await self._budget(
                config,
                lambda signal: run_intake(
                    self.options.intake,
                    {
                        "message": data["message"],
                        "context": self._context(config),
                        "signal": signal,
                    },
                ),
            )
        except Exception:  # noqa: BLE001 - sanitize arbitrary injected port/model errors.
            return self._review(data, "INTAKE_DEPENDENCY_UNAVAILABLE")
        updated = {**data, "intake": intake, "reply": intake["reply"]}
        if intake["kind"] == "answer":
            return self._next(updated, END)
        if intake["kind"] == "clarify":
            return self._ask(updated, [intake["reply"]])
        if intake["kind"] == "review":
            return self._review(updated, "INTAKE_DEPENDENCY_UNAVAILABLE")
        return self._next(
            {
                **updated,
                "phase": "ticket_draft",
                "handoff_reason": "emergency"
                if intake["emergency"]
                else intake.get("handoffReason", "needs_staff"),
            },
            "create_ticket_draft",
        )

    async def _create_ticket_draft(self, data, config):
        if data.get("active_ticket_id"):
            return self._next(data, "load_resident_context")
        return self._plan(
            data,
            "create_ticket_draft",
            {
                "channel_id": data["channel_id"],
                "handoff_reason": data["handoff_reason"],
            },
            "load_resident_context",
        )

    async def _load_resident_context(self, data, config):
        return self._plan(
            {**data, "phase": "collecting_profile"},
            "get_verified_resident_context",
            {**self._ticket_input(data), "resident_response": data["message"]},
            "collect_incident_details",
        )

    async def _collect_incident_details(self, data, config):
        try:
            turn = await self._extract(data, config)
        except Exception as error:  # noqa: BLE001 - sanitize arbitrary injected port/model errors.
            return self._review(
                data,
                error.code
                if isinstance(error, GraphFault)
                else "RESIDENT_EXTRACTION_UNAVAILABLE",
            )
        if turn["intent"] == "new_incident":
            return self._next(
                {
                    **data,
                    "reply": "Cuộc hội thoại đang xử lý ticket hiện tại. Vui lòng hoàn tất ticket hoặc mở cuộc hội thoại mới cho sự cố khác.",
                },
                END,
            )
        if turn["intent"] in ("cancel", "status"):
            return self._next({**data, "turn": turn}, "active_ticket_dialogue")
        prior = data.get("incident") or {
            "title": "",
            "description": "",
            "facts": [],
            "file_ids": [],
        }
        incident = {
            "title": prior["title"] or turn.get("title", ""),
            "description": "\n".join(
                filter(None, [prior["description"], turn.get("description")])
            ),
            "facts": prior["facts"] + turn["facts"],
            "file_ids": list(
                dict.fromkeys(prior["file_ids"] + data["message"].get("fileIds", []))
            ),
        }
        return self._plan(
            {**data, "phase": "collecting_incident", "turn": turn},
            "update_ticket_incident",
            {**self._ticket_input(data), "incident": incident},
            "submit_assessment",
        )

    async def _submit_assessment(self, data, config):
        return self._plan(
            data,
            "submit_ticket_assessment",
            {
                **self._ticket_input(data),
                "facts": (data.get("incident") or {}).get("facts", []),
            },
            "resolve_management_destination",
        )

    async def _resolve_management_destination(self, data, config):
        if (
            not data.get("verified_profile")
            or not data.get("incident", {}).get("title", "").strip()
            or not data.get("incident", {}).get("description", "").strip()
            or not data.get("triage")
        ):
            return self._review(data, "ROUTING_INCOMPLETE")
        return self._plan(
            {**data, "phase": "routing"},
            "resolve_management_destination",
            self._ticket_input(data),
            "handoff_to_supervisor",
        )

    async def _handoff_to_supervisor(self, data, config):
        try:
            message = build_handoff(data, self.now())
        except Exception as error:  # noqa: BLE001 - sanitize arbitrary injected port/model errors.
            return self._review(
                data,
                error.code if isinstance(error, GraphFault) else "HANDOFF_INCOMPLETE",
            )
        return self._plan(
            {**data, "phase": "handoff"},
            "handoff_ticket",
            {
                **self._ticket_input(data),
                "destination_id": data["route"]["destination_id"],
                "route_revision": data["route"]["route_revision"],
                "message": message,
            },
            "wait_for_supervisor",
        )

    async def _wait_for_supervisor(self, data, config):
        if not data.get("ack") or not data.get("route"):
            return self._review(data, "HANDOFF_ACK_REQUIRED")
        if not data["wait_registered"]:
            return self._plan(
                data,
                "register_supervisor_wait",
                {
                    **self._ticket_input(data),
                    "correlation_id": data["ack"]["correlation_id"],
                    **{
                        key: data["route"][key]
                        for key in (
                            "workspace_id",
                            "team_id",
                            "coordination_binding_id",
                        )
                    },
                },
                "wait_for_supervisor",
            )
        source = interrupt(
            {
                "kind": "supervisor",
                "ticket_id": data["active_ticket_id"],
                "correlation_id": data["ack"]["correlation_id"],
            }
        )
        if source["kind"] == "resident":
            return self._accept_resident(data, source)
        if not source.get("verifiedEvent"):
            raise GraphFault("VERIFIED_EVENT_REQUIRED")
        return self._apply_event(data, source["verifiedEvent"])

    async def _active_ticket_dialogue(self, data, config):
        try:
            turn = data.get("turn") or await self._extract(data, config)
        except Exception as error:  # noqa: BLE001 - sanitize arbitrary injected port/model errors.
            return self._review(
                data,
                error.code
                if isinstance(error, GraphFault)
                else "RESIDENT_EXTRACTION_UNAVAILABLE",
            )
        if turn["intent"] == "new_incident":
            return self._next(
                {
                    **data,
                    "turn": turn,
                    "reply": "Ticket hiện tại vẫn được giữ. Vui lòng mở cuộc hội thoại mới cho sự cố khác hoặc hoàn tất ticket này.",
                },
                END,
            )
        after = "wait_for_supervisor" if data.get("ack") else END
        if turn["intent"] == "cancel":
            return self._plan(
                {**data, "turn": turn},
                "request_ticket_cancellation",
                {
                    **self._ticket_input(data),
                    "reason": data["message"]["text"],
                    "source_message_id": data["message"]["id"],
                },
                after,
            )
        if turn["intent"] == "status":
            return self._plan(
                {**data, "turn": turn},
                "get_ticket_status",
                self._ticket_input(data),
                after,
            )
        if data.get("pending_interaction"):
            info = data["pending_interaction"]
            if set(turn["answers"]) - {q["field_id"] for q in info["questions"]}:
                return self._review(data, "UNREQUESTED_ANSWER_FIELD")
            missing = [
                q["question"]
                for q in info["questions"]
                if q["required"] and not turn["answers"].get(q["field_id"])
            ]
            if missing:
                return self._ask({**data, "turn": turn}, missing)
            return self._plan(
                {**data, "turn": turn},
                "respond_supervisor_interaction",
                {
                    **self._ticket_input(data),
                    "interaction_id": info["interaction_id"],
                    "interaction_revision": info["revision"],
                    "source_message_id": data["message"]["id"],
                    "answers": turn["answers"],
                },
                after,
            )
        return self._plan(
            {**data, "turn": turn},
            "append_ticket_information",
            {
                **self._ticket_input(data),
                "source_message_id": data["message"]["id"],
                "message": data["message"]["text"],
                "facts": turn["facts"],
                "file_ids": data["message"].get("fileIds", []),
            },
            after,
        )

    def _apply_event(self, data, event):
        p = event["payload"]
        base = {
            **data,
            "ticket": {
                **data["ticket"],
                "ticket_version": p["ticket_version"],
                "aggregate_version": event["aggregate_version"],
            },
            "phase": "ticket_discussion",
            "processed_event_ids": (data["processed_event_ids"] + [event["event_id"]])[
                -256:
            ],
            "last_event_version": event["aggregate_version"],
            "wait_registered": False,
            "event": None,
            "pending_interaction": None,
            "turn": None,
        }
        if p["status"] == "completed":
            return self._plan(
                {
                    **base,
                    "reply": "Supervisor báo công việc hoàn tất; đang kiểm tra xác nhận từ backend.",
                },
                "get_ticket_status",
                self._ticket_input(base),
                "wait_for_supervisor",
            )
        if p["status"] == "failed":
            return self._review(base, "SUPERVISOR_FAILED")
        if p["status"] == "waiting_for_customer":
            info = p["requested_information"]
            return self._ask(
                {
                    **base,
                    "pending_interaction": {
                        **info,
                        "revision": event["interaction_revision"],
                    },
                },
                [q["question"] for q in info["questions"]],
            )
        return self._next(
            {**base, "reply": p["customer_message"]}, "wait_for_supervisor"
        )

    async def _event_lookup(self, event, context, signal):
        result = await with_budget(
            self.options.timeout_ms,
            signal,
            lambda child: self.dependencies.tools.invoke(
                {
                    "operation": "get_supervisor_event",
                    "input": {"event": event},
                    "context": context,
                    "idempotencyKey": "event:" + event["eventId"],
                    "timeoutMs": self.options.timeout_ms,
                    "signal": child,
                }
            ),
        )
        if result.get("kind") != "success":
            raise GraphFault("EVENT_LOOKUP_UNAVAILABLE")
        return result["value"]

    async def _process_supervisor_event(self, data, config):
        if not data.get("event"):
            raise GraphFault("BUFFERED_EVENT_LOOKUP_REQUIRED")
        value = await self._event_lookup(
            data["event"], self._context(config), self._signal(config)
        )
        return self._apply_event(data, parse_supervisor_event(value, data))

    @staticmethod
    def _clear_scope(data, ticket):
        return {
            **data,
            "ticket": ticket,
            "verified_profile": None,
            "route": None,
            "ack": None,
            "triage": None,
            "wait_registered": False,
            "next": "load_resident_context",
        }

    def _apply_output(self, data, raw):
        pending = data.get("pending")
        if not pending:
            raise GraphFault("PENDING_OPERATION_REQUIRED")
        v = record(raw)
        updated = {
            **data,
            "pending": None,
            "last_error": None,
            "next": pending["after"],
            "completed_operations": data["completed_operations"]
            + [pending["idempotencyKey"]],
        }
        operation = pending["operation"]
        if operation == "create_ticket_draft":
            ticket = parse_ticket(raw)
            if (
                data.get("active_ticket_id")
                and data["active_ticket_id"] != ticket["ticket_id"]
            ):
                raise GraphFault("SECOND_TICKET_FORBIDDEN")
            return {
                **updated,
                "ticket": ticket,
                "active_ticket_id": ticket["ticket_id"],
            }
        if operation == "get_verified_resident_context":
            if v.get("kind") in ("missing", "selection_required"):
                return self._ask(updated, strings(v.get("questions")))
            choice(v.get("kind"), ("verified",))
            profile = parse_profile(v.get("profile"))
            old = data.get("verified_profile")
            if old and any(
                old[key] != profile[key] for key in ("building_id", "domain_id")
            ):
                updated.update(route=None, ack=None, triage=None, wait_registered=False)
            return {**updated, "verified_profile": profile}
        if operation == "update_ticket_incident":
            updated.update(
                ticket=parse_ticket(v.get("ticket"), data.get("ticket")),
                incident=parse_incident(v.get("incident")),
                route=None,
                triage=None,
            )
            missing = [
                field
                for field in strings(v.get("missing_fields"))
                if not (data.get("intake", {}).get("emergency") and field == "file_ids")
            ]
            if missing:
                questions = {
                    "file_ids": "Bạn có thể bổ sung ảnh sự cố không?",
                    "description": "Bạn mô tả rõ vị trí và biểu hiện sự cố nhé.",
                    "title": "Bạn cần hỗ trợ vấn đề gì?",
                }
                return self._ask(
                    updated,
                    [
                        questions.get(field, "Bạn bổ sung thông tin: " + field + ".")
                        for field in missing
                    ],
                )
            if (
                not updated["incident"]["title"].strip()
                or not updated["incident"]["description"].strip()
            ):
                return self._review(updated, "INCIDENT_INCOMPLETE")
            return updated
        if operation == "submit_ticket_assessment":
            if v.get("status") in ("policy_missing", "review_required"):
                return self._review(updated, "ASSESSMENT_REVIEW_REQUIRED")
            return {
                **updated,
                "ticket": parse_ticket(v.get("ticket"), data.get("ticket")),
                "triage": parse_triage(v.get("triage")),
            }
        if operation == "resolve_management_destination":
            if v.get("kind") == "unresolved":
                return self._review({**updated, "route": None}, "ROUTING_UNRESOLVED")
            choice(v.get("kind"), ("resolved",))
            return {**updated, "route": parse_route(v.get("route"), data)}
        if operation == "handoff_ticket":
            return {
                **updated,
                "ack": parse_ack(raw, pending["input"]["message"]["correlation_id"]),
                "reply": "Ticket đã được hệ thống tiếp nhận để chuyển xử lý.",
            }
        if operation == "register_supervisor_wait":
            if v.get("registered") is not True:
                raise GraphFault("WAIT_REGISTRATION_REQUIRED")
            if "buffered_event" in v:
                return {
                    **updated,
                    "wait_registered": True,
                    "event": record(v["buffered_event"]),
                    "next": "process_supervisor_event",
                    "last_error": "BUFFERED_EVENT",
                }
            return {
                **updated,
                "phase": "waiting_supervisor",
                "wait_registered": True,
                "wait_kind": "supervisor",
            }
        if operation == "append_ticket_information":
            ticket = parse_ticket(v.get("ticket"), data.get("ticket"))
            changed, delivered = (
                boolean(v.get("scope_changed")),
                boolean(v.get("delivered")),
            )
            if changed:
                return self._clear_scope(updated, ticket)
            return {
                **updated,
                "ticket": ticket,
                "reply": "Thông tin đã được bổ sung vào ticket hiện tại."
                if delivered
                else "Thông tin đã được lưu; đang chờ chuyển đến bộ phận xử lý.",
            }
        if operation == "respond_supervisor_interaction":
            updated["ticket"] = parse_ticket(v.get("ticket"), data.get("ticket"))
            if (
                choice(v.get("status"), ("accepted", "conflict", "expired"))
                != "accepted"
            ):
                return self._review(updated, "INTERACTION_CONFLICT_OR_EXPIRED")
            return {
                **updated,
                "pending_interaction": None,
                "reply": "Câu trả lời đã được hệ thống tiếp nhận.",
            }
        if operation == "request_ticket_cancellation":
            return {
                **updated,
                "ticket": parse_ticket(v.get("ticket"), data.get("ticket")),
                "reply": "Yêu cầu hủy đã được tiếp nhận; đang chờ xác nhận."
                if choice(v.get("status"), ("accepted", "rejected", "review"))
                == "accepted"
                else "Yêu cầu hủy chưa được chấp thuận; cần người có thẩm quyền xem xét.",
            }
        if operation == "get_ticket_status":
            ticket = parse_ticket(v.get("ticket"), data.get("ticket"))
            status = choice(
                v.get("status"),
                ("draft", "in_progress", "resolved", "closed", "cancelled"),
            )
            confirmed, changed = (
                boolean(v.get("completion_confirmed")),
                boolean(v.get("scope_changed")),
            )
            if changed:
                return self._clear_scope(updated, ticket)
            if confirmed and status in ("resolved", "closed", "cancelled"):
                return {
                    **updated,
                    "ticket": ticket,
                    "phase": "terminal",
                    "next": END,
                    "reply": "Backend xác nhận ticket đã được hủy."
                    if status == "cancelled"
                    else "Backend xác nhận ticket đã hoàn tất xử lý.",
                }
            return {
                **updated,
                "ticket": ticket,
                "reply": "Ticket đang được xử lý; chưa có xác nhận hoàn tất từ backend.",
            }
        raise GraphFault("TOOL_NOT_ALLOWED")

    async def _execute_operation(self, data, config):
        if not data.get("pending"):
            raise GraphFault("PENDING_OPERATION_REQUIRED")
        pending = data["pending"]
        request = {
            "operation": pending["operation"],
            "input": pending["input"],
            "context": self._context(config),
            "idempotencyKey": pending["idempotencyKey"],
            "timeoutMs": self.options.timeout_ms,
        }
        try:
            reconciling = config["configurable"].get("recoverKey") == pending[
                "idempotencyKey"
            ] or config["configurable"].get("reconcile")
            port = (
                self.options.reconcile
                if reconciling
                else self.dependencies.tools.invoke
            )
            if port is None:
                raise GraphFault("RECONCILIATION_UNAVAILABLE")
            result = await self._budget(
                config, lambda signal: port({**request, "signal": signal})
            )
        except Exception as error:
            if (
                isinstance(error, GraphFault)
                and error.code == "RECONCILIATION_UNAVAILABLE"
            ):
                raise
            result = {
                "kind": "failure",
                "code": "TOOL_OUTCOME_UNKNOWN",
                "retryable": False,
                "outcome": "unknown",
            }
        signal = self._signal(config)
        if signal:
            signal.throw_if_aborted()
        if isinstance(result, dict) and result.get("kind") == "success":
            try:
                return self._apply_output(data, result.get("value"))
            except Exception as error:  # noqa: BLE001 - sanitize arbitrary injected port/model errors.
                return {
                    **data,
                    "phase": "waiting_operation",
                    "next": "wait_for_operation",
                    "last_error": error.code
                    if isinstance(error, GraphFault)
                    else "INVALID_WORKFLOW_OUTPUT",
                    "reply": "Chưa xác minh được kết quả; cần đối soát với backend.",
                }
        if (
            isinstance(result, dict)
            and result.get("kind") == "failure"
            and result.get("outcome") == "not_applied"
        ):
            return self._review({**data, "pending": None}, "BACKEND_OPERATION_REJECTED")
        return {
            **data,
            "phase": "waiting_operation",
            "next": "wait_for_operation",
            "wait_kind": "operation",
            "reply": "Đang chờ backend xác nhận kết quả thao tác.",
        }

    async def _wait_for_operation(self, data, config):
        source = interrupt(
            {
                "kind": "operation",
                "idempotency_key": (data.get("pending") or {}).get("idempotencyKey"),
                "dependency": None if self.options.reconcile else "reconcile",
            }
        )
        if self.options.reconcile is None:
            raise GraphFault("RECONCILIATION_UNAVAILABLE")
        if source["kind"] != "backend":
            raise GraphFault("BACKEND_RESUME_REQUIRED")
        return await self._execute_operation(
            {
                **data,
                "processed_event_ids": (
                    data["processed_event_ids"] + [source["event"]["eventId"]]
                )[-256:],
            },
            {**config, "configurable": {**config["configurable"], "reconcile": True}},
        )

    async def _wait_for_resident(self, data, config):
        source = interrupt({"kind": "resident", "questions": data["questions"]})
        if source["kind"] == "backend" and source.get("verifiedEvent"):
            return self._apply_event(data, source["verifiedEvent"])
        return self._accept_resident(data, source)

    async def _human_review(self, data, config):
        source = interrupt({"kind": "review", "code": data.get("last_error")})
        if source["kind"] == "backend" and source.get("verifiedEvent"):
            return self._apply_event(data, source["verifiedEvent"])
        return self._accept_resident(data, source)

    @staticmethod
    def _config(context, signal=None, recover_key=None):
        return {
            "configurable": {
                "thread_id": compact_json(
                    [
                        context["checkpoint"]["namespace"],
                        context["checkpoint"]["threadId"],
                    ]
                ),
                "checkpoint_ns": "",
                "context": context,
                "signal": signal,
                "recoverKey": recover_key,
            },
            "recursion_limit": 80,
        }

    async def _snapshot(self, context):
        snap = await self.compiled.aget_state(self._config(context))
        data = snap.values.get("data")
        if data:
            if (
                data.get("schemaVersion") != 1
                or data.get("workflow_version") != WORKFLOW_VERSION
            ):
                raise GraphFault("WORKFLOW_MIGRATION_REQUIRED")
            if (
                any(
                    not isinstance(data.get(key), list)
                    for key in (
                        "completed_operations",
                        "processed_event_ids",
                        "asked_questions",
                    )
                )
                or not data.get("owner")
                or not data.get("message")
                or not data.get("reception_session_id")
                or not data.get("channel_id")
            ):
                raise GraphFault("WORKFLOW_STATE_INVALID")
            if (
                data["owner"]
                != {
                    key: context[key]
                    for key in ("tenantId", "principalId", "initiatedBy", "bindingId")
                }
                or data["reception_binding_id"] != context["bindingId"]
            ):
                raise GraphFault("CONTEXT_MISMATCH")
            if (
                data.get("ticket")
                and data.get("active_ticket_id") != data["ticket"]["ticket_id"]
            ):
                raise GraphFault("ACTIVE_TICKET_MISMATCH")
        waits = [item for task in snap.tasks for item in task.interrupts]
        return snap, data, waits

    @staticmethod
    def _result(data, waits, blank=False):
        state = deepcopy(data)
        if blank:
            state["reply"] = ""
        if not waits:
            return {"status": "completed", "state": state}
        reason = (
            "backend_event"
            if data.get("pending")
            else "human_review"
            if data["next"] == "human_review"
            else "resident_input"
            if data["next"] == "wait_for_resident"
            else "backend_event"
        )
        return {
            "status": "interrupted",
            "state": state,
            "interrupts": [{"id": wait.id, "reason": reason} for wait in waits],
        }

    async def read(self, context):
        return deepcopy((await self._snapshot(context))[1])

    async def run(self, request):
        return await self._execute(request)

    async def resume(self, request):
        return await self._execute(request)

    async def recover(self, request):
        return await self._execute(request, recovering=True)

    async def stream(self, request):
        result = await self._execute(request)
        if result["status"] in ("completed", "interrupted") and result["state"].get(
            "reply"
        ):
            yield {"type": "text_delta", "text": result["state"]["reply"]}
        yield {"type": "result", "result": result}

    async def _execute(self, request, recovering=False):
        signal, context = request.get("signal"), request["context"]
        try:
            if signal:
                signal.throw_if_aborted()
            snap, data, waits = await self._snapshot(context)
            recover_key = None
            if recovering:
                if not data or not data.get("pending") or not snap.next or waits:
                    raise GraphFault("RECOVERY_NOT_REQUIRED")
                if self.options.reconcile is None:
                    raise GraphFault("RECONCILIATION_UNAVAILABLE")
                recover_key = data["pending"]["idempotencyKey"]
                graph_input = None
            elif "source" in request:
                if (
                    not data
                    or len(waits) != 1
                    or waits[0].id != request.get("interruptId")
                ):
                    raise GraphFault("INTERRUPT_MISMATCH")
                if data.get("pending") and self.options.reconcile is None:
                    raise GraphFault("RECONCILIATION_UNAVAILABLE")
                source = deepcopy(request["source"])
                if source["kind"] == "backend":
                    event = record(source["event"])
                    integer(event.get("aggregateVersion"))
                    integer(event.get("generation"))
                    text(event.get("eventId"))
                    if (
                        event.get("bindingId") != context["bindingId"]
                        or event.get("interruptId") != request["interruptId"]
                    ):
                        raise GraphFault("EVENT_CONTEXT_MISMATCH")
                    if event["eventId"] in data["processed_event_ids"]:
                        raise GraphFault("EVENT_STALE_OR_MISMATCH")
                    ticket = data.get("ticket")
                    if ticket and (
                        event.get("ticketId") != ticket["ticket_id"]
                        or event["generation"] != ticket["ticket_generation"]
                        or event["aggregateVersion"] < ticket["aggregate_version"]
                    ):
                        raise GraphFault("EVENT_STALE_OR_MISMATCH")
                    if not data.get("pending"):
                        raw = await self._event_lookup(event, context, signal)
                        source["verifiedEvent"] = parse_supervisor_event(
                            raw, {**data, "event": event}
                        )
                elif source["kind"] == "resident":
                    if data.get("pending"):
                        raise GraphFault("OPERATION_UNRESOLVED")
                    key = self._resident_key(request["operationId"], source["message"])
                    old = next(
                        (
                            v
                            for v in data["completed_operations"]
                            if v.startswith("resident:" + request["operationId"] + ":")
                        ),
                        None,
                    )
                    if old:
                        if old != key:
                            raise GraphFault("OPERATION_PAYLOAD_CONFLICT")
                        return self._result(data, waits, True)
                    source.update(residentKey=key, operationId=request["operationId"])
                else:
                    raise GraphFault("INVALID_REQUEST")
                graph_input = Command(resume=source)
            elif "message" in request:
                key = self._resident_key(request["operationId"], request["message"])
                if data and data.get("pending") or snap.next and not waits:
                    raise GraphFault("RECOVERY_REQUIRED")
                if waits:
                    raise GraphFault("RESUME_REQUIRED")
                old = (
                    next(
                        (
                            v
                            for v in data["completed_operations"]
                            if v.startswith("resident:" + request["operationId"] + ":")
                        ),
                        None,
                    )
                    if data
                    else None
                )
                if old:
                    if old != key:
                        raise GraphFault("OPERATION_PAYLOAD_CONFLICT")
                    return self._result(data, [], True)
                session = await with_budget(
                    self.options.timeout_ms,
                    signal,
                    lambda child: self.options.resolve_session(context, child),
                )
                text(session.get("channel_id"))
                text(session.get("reception_session_id"))
                if data and any(
                    session[field] != data[field]
                    for field in ("channel_id", "reception_session_id")
                ):
                    raise GraphFault("SESSION_MISMATCH")
                if not data:
                    data = {
                        "schemaVersion": 1,
                        "workflow_version": WORKFLOW_VERSION,
                        "owner": {
                            field: context[field]
                            for field in (
                                "tenantId",
                                "principalId",
                                "initiatedBy",
                                "bindingId",
                            )
                        },
                        "channel_id": session["channel_id"],
                        "reception_session_id": session["reception_session_id"],
                        "reception_binding_id": context["bindingId"],
                        "phase": "knowledge_chat",
                        "handoff_reason": "needs_staff",
                        "wait_registered": False,
                        "questions": [],
                        "asked_questions": [],
                        "question_attempts": 0,
                        "processed_event_ids": [],
                        "last_event_version": -1,
                        "completed_operations": [],
                    }
                data = {
                    **data,
                    "message": deepcopy(request["message"]),
                    "operation_id": request["operationId"],
                    "turn": None,
                    "reply": "",
                    "next": "receive_message",
                    "completed_operations": data["completed_operations"] + [key],
                }
                graph_input = {"data": data}
            else:
                raise GraphFault("INVALID_REQUEST")
            await self.compiled.ainvoke(
                graph_input,
                self._config(context, signal, recover_key),
                durability="sync",
            )
            if signal:
                signal.throw_if_aborted()
            _, final, interrupts = await self._snapshot(context)
            if not final:
                raise GraphFault("STATE_MISSING")
            return self._result(final, interrupts)
        except asyncio.CancelledError:
            return {"status": "cancelled"}
        except Exception as error:  # noqa: BLE001 - sanitize arbitrary injected port/model errors.
            if signal and signal.aborted:
                return {"status": "cancelled"}
            return {
                "status": "failed",
                "code": error.code
                if isinstance(error, GraphFault)
                else "WORKFLOW_EXECUTION_FAILED",
                "retryable": error.retryable
                if isinstance(error, GraphFault)
                else False,
            }

    @staticmethod
    def _resident_key(operation_id, message):
        text(operation_id)
        text(message.get("id"))
        text(message.get("text"))
        strings(message.get("fileIds", []))
        # Canonical ordering avoids dictionary insertion-order affecting replay identity.
        import json

        return (
            "resident:"
            + operation_id
            + ":"
            + json.dumps(
                json_value(message),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        )
