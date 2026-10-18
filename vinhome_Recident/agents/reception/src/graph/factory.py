"""Generic PD01 Python LangGraph; all backend bindings must be injected."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from ..prompts.pd01 import PD01_SYSTEM_PROMPT
from .budget import with_budget
from .decision import GraphFault, compact_json, facts, json_value, parse_decision
from .intake import run_intake
from .state import (
    PD01_RUNTIME_VERSION,
    PYTHON_CONTRACT_VERSION,
    GraphState,
    belongs_to,
    initial_state,
)


@dataclass(frozen=True)
class ToolBinding:
    description: str
    input_schema: Any
    parse_input: Callable
    parse_output: Callable
    confirmed_facts: Callable | None = None
    ticket: Callable | None = None
    reconcile: Callable | None = None


@dataclass(frozen=True)
class ReceptionFactoryOptions:
    bindings: dict[str, ToolBinding]
    timeout_ms: int = 10000
    max_steps: int = 8
    max_clarifications: int = 3
    intake: Any = None


class ReceptionGraphFactory:
    contract_version = PYTHON_CONTRACT_VERSION
    state_schema_version = 1

    def __init__(self, options):
        for value, name in (
            (options.timeout_ms, "TIMEOUT"),
            (options.max_steps, "STEP_LIMIT"),
            (options.max_clarifications, "CLARIFICATION_LIMIT"),
        ):
            if type(value) is not int or value <= 0:
                raise GraphFault("INVALID_" + name)
        self.options = options

    def create(self, dependencies):
        return ReceptionGraph(self.options, dependencies)


def create_reception_graph_factory(options):
    return ReceptionGraphFactory(options)


class ReceptionGraph:
    state_schema_version = 1

    def __init__(self, options, dependencies):
        if dependencies.checkpointer is None:
            raise GraphFault("CHECKPOINTER_REQUIRED")
        self.options, self.dependencies = options, dependencies
        builder = StateGraph(GraphState)
        for name in (
            "intake",
            "decide",
            "tool",
            "resident_wait",
            "backend_wait",
            "handoff_wait",
        ):
            handler = getattr(self, "_" + name)

            def bind(handler):
                async def node(state, config):
                    return {"data": await handler(deepcopy(state["data"]), config)}

                return node

            builder.add_node(name, bind(handler))
        builder.add_edge(START, "intake")
        builder.add_conditional_edges(
            "intake",
            lambda s: (
                "decide"
                if not s["data"].get("intake")
                else END
                if s["data"]["phase"] == "completion"
                else "resident_wait"
                if s["data"]["phase"] == "clarify"
                else "handoff_wait"
            ),
        )
        builder.add_conditional_edges(
            "decide",
            lambda s: (
                "tool"
                if s["data"]["phase"] == "awaiting_tool"
                else END
                if s["data"]["phase"] == "completion"
                else "handoff_wait"
                if s["data"]["phase"] == "handoff"
                else "resident_wait"
            ),
        )
        for name in ("tool", "backend_wait"):
            builder.add_conditional_edges(
                name,
                lambda s: (
                    "handoff_wait"
                    if s["data"]["phase"] == "handoff"
                    else "backend_wait"
                    if s["data"]["pendingTool"]
                    else "decide"
                ),
            )
        builder.add_edge("resident_wait", "intake")
        builder.add_edge("handoff_wait", "intake")
        self.compiled = builder.compile(checkpointer=dependencies.checkpointer)

    def _binding(self, operation):
        if operation not in self.options.bindings:
            raise GraphFault("TOOL_NOT_ALLOWED")
        return self.options.bindings[operation]

    async def _budget(self, config, run):
        return await with_budget(
            self.options.timeout_ms, config["configurable"].get("signal"), run
        )

    async def _intake(self, data, config):
        if not self.options.intake or data["ticket"] or data["pendingTool"]:
            return {**data, "intake": None}
        outcome = await self._budget(
            config,
            lambda child: run_intake(
                self.options.intake,
                {
                    "message": data["message"],
                    "context": config["configurable"]["context"],
                    "signal": child,
                },
            ),
        )
        exhausted = (
            outcome["kind"] == "clarify"
            and data["clarifications"] >= self.options.max_clarifications
        )
        phase = (
            "completion"
            if outcome["kind"] == "answer"
            else "clarify"
            if outcome["kind"] == "clarify" and not exhausted
            else "handoff"
        )
        return {
            **data,
            "intake": outcome,
            "phase": phase,
            "decision": None,
            "reply": "Chưa đủ dữ kiện sau các lần làm rõ; yêu cầu cần người xem xét."
            if exhausted
            else outcome["reply"],
            "clarifications": data["clarifications"] + (phase == "clarify"),
        }

    async def _decide(self, data, config):
        if data["steps"] >= self.options.max_steps:
            return {
                **data,
                "phase": "handoff",
                "reply": "Yêu cầu cần người có thẩm quyền xem xét để tiếp tục.",
            }
        prompt = {
            "catalog": [
                {
                    "operation": key,
                    "description": b.description,
                    "inputSchema": b.input_schema,
                }
                for key, b in self.options.bindings.items()
            ],
            **{
                key: data[key]
                for key in (
                    "reported",
                    "confirmed",
                    "inferences",
                    "lastToolResult",
                    "pendingTool",
                )
            },
        }
        response = await self._budget(
            config,
            lambda _: self.dependencies.model.ainvoke(
                [SystemMessage(PD01_SYSTEM_PROMPT), HumanMessage(compact_json(prompt))]
            ),
        )
        decision = parse_decision(response.content)
        updated = {
            **data,
            "decision": decision,
            "steps": data["steps"] + 1,
            "inferences": (data["inferences"] + decision["inferences"])[-64:],
        }
        action = decision["action"]
        if data["pendingTool"] and action in ("tool", "complete"):
            raise GraphFault("TOOL_OUTCOME_UNRESOLVED")
        if action == "tool":
            binding = self._binding(decision["operation"])
            sequence = data["toolSequence"] + 1
            return {
                **updated,
                "phase": "awaiting_tool",
                "toolSequence": sequence,
                "reply": "",
                "pendingTool": {
                    "operation": decision["operation"],
                    "input": json_value(binding.parse_input(decision["input"])),
                    "idempotencyKey": compact_json(
                        [data["owner"]["bindingId"], data["operationId"], sequence]
                    ),
                    "timeoutMs": self.options.timeout_ms,
                },
            }
        if (
            action in ("clarify", "await_resident")
            and data["clarifications"] >= self.options.max_clarifications
        ):
            return {
                **updated,
                "phase": "handoff",
                "reply": "Chưa đủ dữ kiện sau các lần làm rõ; yêu cầu cần người xem xét.",
            }
        return {
            **updated,
            "phase": {
                "complete": "completion",
                "await_resident": "awaiting_resident",
            }.get(action, action),
            "reply": decision["text"],
            "clarifications": data["clarifications"]
            + (action in ("clarify", "await_resident")),
        }

    async def _call(self, data, config, reconcile=False):
        pending = data["pendingTool"]
        if not pending:
            raise GraphFault("STATE_INVALID")
        port = (
            self._binding(pending["operation"]).reconcile
            if reconcile
            else self.dependencies.tools.invoke
        )
        if port is None:
            raise GraphFault("RECONCILIATION_UNAVAILABLE")
        try:
            raw = await self._budget(
                config,
                lambda child: port(
                    {
                        **pending,
                        "context": config["configurable"]["context"],
                        "signal": child,
                    }
                ),
            )
        except Exception:  # noqa: BLE001 - sanitize arbitrary injected port/model errors.
            raw = {
                "kind": "failure",
                "code": "TOOL_RESPONSE_LOST",
                "retryable": False,
                "outcome": "unknown",
            }
        signal = config["configurable"].get("signal")
        if signal:
            signal.throw_if_aborted()
        return self._apply(data, raw)

    async def _tool(self, data, config):
        return await self._call(data, config)

    def _apply(self, data, raw):
        pending = data["pendingTool"]
        if isinstance(raw, dict) and raw.get("kind") == "success":
            binding = self._binding(pending["operation"])
            try:
                output = binding.parse_output(raw.get("value"))
                confirmed = [
                    {
                        **fact,
                        "source": {
                            "operation": pending["operation"],
                            "idempotencyKey": pending["idempotencyKey"],
                        },
                    }
                    for fact in facts(
                        binding.confirmed_facts(output)
                        if binding.confirmed_facts
                        else []
                    )
                ]
                ticket = binding.ticket(output) if binding.ticket else data["ticket"]
                if ticket and (
                    not ticket.get("id")
                    or any(
                        type(ticket.get(k)) is not int or ticket[k] < 0
                        for k in ("generation", "aggregateVersion")
                    )
                ):
                    raise GraphFault("INVALID_TOOL_OUTPUT")
                return {
                    **data,
                    "phase": "intake",
                    "confirmed": (data["confirmed"] + confirmed)[-64:],
                    "ticket": ticket,
                    "pendingTool": None,
                    "lastToolResult": {"kind": "success", "value": json_value(output)},
                }
            except Exception:  # noqa: BLE001 - sanitize arbitrary injected port/model errors.
                raw = {
                    "kind": "failure",
                    "code": "INVALID_TOOL_OUTPUT",
                    "retryable": False,
                    "outcome": "unknown",
                }
        if (
            isinstance(raw, dict)
            and raw.get("kind") == "accepted"
            and isinstance(raw.get("operationId"), str)
            and raw["operationId"]
        ):
            return {
                **data,
                "phase": "awaiting_tool",
                "lastToolResult": raw,
                "reply": "Hệ thống đã tiếp nhận yêu cầu; đang chờ xác nhận kết quả.",
            }
        if (
            not isinstance(raw, dict)
            or raw.get("kind") != "failure"
            or not isinstance(raw.get("code"), str)
            or type(raw.get("retryable")) is not bool
            or raw.get("outcome") not in ("unknown", "not_applied")
        ):
            raw = {
                "kind": "failure",
                "code": "INVALID_TOOL_RESULT",
                "retryable": False,
                "outcome": "unknown",
            }
        unknown = raw["outcome"] == "unknown"
        return {
            **data,
            "phase": "awaiting_tool" if unknown else "handoff",
            "pendingTool": pending if unknown else None,
            "lastToolResult": raw,
            "reply": "Chưa xác định kết quả; cần kiểm tra lại với hệ thống."
            if unknown
            else "Yêu cầu chưa được thực hiện; cần người có thẩm quyền xem xét.",
        }

    async def _resident_wait(self, data, config):
        source = interrupt({"kind": "resident", "message": data["message"]})
        if source.get("kind") != "resident":
            raise GraphFault("RESUME_SOURCE_MISMATCH")
        return {
            **data,
            "phase": "intake",
            "message": source["message"],
            "reported": (data["reported"] + [source["message"]])[-64:],
            "steps": 0,
            "reply": "",
        }

    async def _backend_wait(self, data, config):
        interrupt({"reason": "backend_event"})
        return await self._call(data, config, True)

    async def _handoff_wait(self, data, config):
        interrupt({"reason": "human_review"})
        return {**data, "phase": "intake", "steps": 0, "reply": ""}

    @staticmethod
    def _config(context, signal=None):
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
            },
            "recursion_limit": 100,
        }

    async def _snapshot(self, context):
        snapshot = await self.compiled.aget_state(self._config(context))
        data = snapshot.values.get("data")
        if data:
            if (
                data.get("schemaVersion") != 1
                or data.get("runtime_version") != PD01_RUNTIME_VERSION
            ):
                raise GraphFault("STATE_VERSION_UNSUPPORTED")
            if not belongs_to(data, context):
                raise GraphFault("CONTEXT_MISMATCH")
            if (
                any(
                    not isinstance(data.get(k), list)
                    for k in ("reported", "confirmed", "inferences")
                )
                or not data.get("message")
                or data.get("phase")
                not in (
                    "intake",
                    "clarify",
                    "awaiting_tool",
                    "awaiting_resident",
                    "handoff",
                    "completion",
                )
                or type(data.get("toolSequence")) is not int
                or data["toolSequence"] < 0
            ):
                raise GraphFault("STATE_INVALID")
        return snapshot, data, [i for task in snapshot.tasks for i in task.interrupts]

    async def read(self, context):
        return deepcopy((await self._snapshot(context))[1])

    async def run(self, request):
        return await self._execute(request)

    async def resume(self, request):
        return await self._execute(request)

    async def stream(self, request):
        result = await self._execute(request)
        if (
            result["status"] in ("completed", "interrupted")
            and result["state"]["reply"]
        ):
            yield {"type": "text_delta", "text": result["state"]["reply"]}
        yield {"type": "result", "result": result}

    async def _execute(self, request):
        signal = request.get("signal")
        try:
            if signal:
                signal.throw_if_aborted()
            snapshot, data, waits = await self._snapshot(request["context"])
            if "source" in request:
                if (
                    data is None
                    or len(waits) != 1
                    or waits[0].id != request.get("interruptId")
                ):
                    raise GraphFault("INTERRUPT_MISMATCH")
                source = request["source"]
                resident = data["phase"] in ("clarify", "awaiting_resident")
                if (source.get("kind") == "resident") != resident:
                    raise GraphFault("RESUME_SOURCE_MISMATCH")
                if not resident:
                    event = source.get("event", {})
                    if any(
                        type(event.get(k)) is not int or event[k] < 0
                        for k in ("generation", "aggregateVersion")
                    ):
                        raise GraphFault("EVENT_INVALID")
                    if (
                        event.get("bindingId") != request["context"]["bindingId"]
                        or event.get("interruptId") != request["interruptId"]
                    ):
                        raise GraphFault("EVENT_CONTEXT_MISMATCH")
                    ticket = data["ticket"]
                    if ticket and (
                        event.get("ticketId") != ticket["id"]
                        or event["generation"] != ticket["generation"]
                        or event["aggregateVersion"] <= ticket["aggregateVersion"]
                    ):
                        raise GraphFault("EVENT_STALE_OR_MISMATCH")
                    if (
                        data["pendingTool"]
                        and not self._binding(
                            data["pendingTool"]["operation"]
                        ).reconcile
                    ):
                        raise GraphFault("RECONCILIATION_UNAVAILABLE")
                graph_input = Command(resume=source)
            else:
                if waits or snapshot.next:
                    raise GraphFault("RESUME_REQUIRED")
                if data and data["pendingTool"]:
                    raise GraphFault("TOOL_OUTCOME_UNRESOLVED")
                graph_input = {
                    "data": {
                        **data,
                        "phase": "intake",
                        "operationId": request["operationId"],
                        "message": request["message"],
                        "reported": (data["reported"] + [request["message"]])[-64:],
                        "decision": None,
                        "steps": 0,
                        "reply": "",
                    }
                    if data
                    else initial_state(request)
                }
            await self.compiled.ainvoke(
                graph_input, self._config(request["context"], signal), durability="sync"
            )
            if signal:
                signal.throw_if_aborted()
            _, final, waits = await self._snapshot(request["context"])
            if waits:
                reason = (
                    "resident_input"
                    if final["phase"] in ("clarify", "awaiting_resident")
                    else "human_review"
                    if final["phase"] == "handoff"
                    else "backend_event"
                )
                return {
                    "status": "interrupted",
                    "state": final,
                    "interrupts": [{"id": i.id, "reason": reason} for i in waits],
                }
            return {"status": "completed", "state": final}
        except asyncio.CancelledError:
            return {"status": "cancelled"}
        except Exception as error:  # noqa: BLE001 - sanitize arbitrary injected port/model errors.
            if signal and signal.aborted:
                return {"status": "cancelled"}
            return {
                "status": "failed",
                "code": error.code
                if isinstance(error, GraphFault)
                else "GRAPH_EXECUTION_FAILED",
                "retryable": error.retryable
                if isinstance(error, GraphFault)
                else False,
            }
