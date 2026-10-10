# -*- coding: utf-8 -*-
"""Executable Phase A acceptance for schemas and proposals."""

from copy import deepcopy
import inspect
import json
from pathlib import Path
from typing import Any, Callable
import unittest

from jsonschema import Draft202012Validator, FormatChecker
from pydantic import ValidationError

from agentscope.app.workforce import contracts
from agentscope.app.workforce.orchestration.phase_a import (
    PROPOSED_MODELS,
    SHARED_MODELS,
    phase_a_schema_bundle,
)
from agentscope.app.workforce.orchestration.partner_events.phase_a import (
    PUBLIC_PAYLOAD_MODELS,
    validate_public_event,
)
from agentscope.app.workforce.orchestration.workflows.phase_a import (
    CommandClaimResult,
    PinnedRuntimeContext,
    WorkflowCheckpoint,
    WorkflowTrigger,
    cause_key,
)
from fixtures import phase_a_samples


HANDOFF = (
    Path(__file__).resolve().parents[4]
    / "docs/workforce/handoffs/phan-huy-hoang/phase_a"
)
MODELS = {
    model.__name__: model for model in (*SHARED_MODELS, *PROPOSED_MODELS)
}
NEGATIVE_CASES = []


def reject(
    model: str,
    path: str,
    value: Any = None,
    *,
    delete: bool = False,
    description: str | None = None,
) -> None:
    NEGATIVE_CASES.append(
        dict(
            id=f"PHA-{len(NEGATIVE_CASES) + 1:03d}",
            model=model,
            path=path.split("."),
            value=value,
            delete=delete,
            description=description
            or f"{'Remove' if delete else 'Set'} {path}"
            + ("" if delete else f" = {value!r}"),
        )
    )


for field in ("trigger_id", "workflow_id", "cause"):
    reject("WorkflowTrigger", field, delete=True)
for field in (
    "workflow_id",
    "state_revision",
    "session_refs",
    "agent_version_pins",
    "shared_state_ref",
    "used_budget",
):
    reject("WorkflowCheckpoint", field, delete=True)
for field in ("tenant_id", "domain_id", "area_id", "manager_account_id"):
    reject("WorkflowRecord", f"scope.{field}", delete=True)
for field in ("group_id", "route_id", "route_revision"):
    reject("WorkflowRecord", field, delete=True)
for field in ("request_id", "is_new", "status"):
    reject("CommandClaimResult", field, delete=True)
for field in (
    "event_id",
    "sequence",
    "conversation_id",
    "external_conversation_id",
    "external_user_id",
):
    reject("ConversationEvent", field, delete=True)

reject("WorkflowTrigger", "cause.kind", "provider_instruction")
reject("WorkflowTrigger", "cause.request_id", delete=True)
reject(
    "WorkflowTrigger",
    "cause.timer_id",
    "timer-A",
    description="Request cause also supplies timer identity",
)
reject(
    "WorkflowTrigger",
    "cause",
    {"kind": "approval", "request_id": "approval-request-A"},
)
reject(
    "WorkflowTrigger",
    "cause",
    {"kind": "approval", "approval_id": "approval-A"},
)
reject(
    "WorkflowTrigger",
    "cause",
    {"kind": "external_event", "cause_event_id": "inbox-A"},
)
reject(
    "WorkflowTrigger",
    "cause",
    {"kind": "external_event", "operation_id": "operation-A"},
)
reject("WorkflowTrigger", "cause", {"kind": "timer", "timer_id": ""})
for field in ("scope", "group_id", "actor", "credential", "callback_url"):
    reject(
        "WorkflowTrigger",
        field,
        "untrusted",
        description=f"Inject {field} into queued trigger",
    )
for value in (0, -1, True, "1"):
    reject("WorkflowTrigger", "expected_state_revision", value)
reject("WorkflowCheckpoint", "schema_version", "production-v1")
reject("WorkflowCheckpoint", "session_refs", [])
reject("WorkflowCheckpoint", "agent_version_pins", [])
reject("WorkflowCheckpoint", "agent_version_pins.0.version_id", "")
reject("WorkflowCheckpoint", "protocol_pins.0.schema_hash", "")
for field in (
    "session_refs",
    "pending_task_ids",
    "pending_question_ids",
    "pending_approval_ids",
    "operation_refs",
):
    reject(
        "WorkflowCheckpoint",
        field,
        ["same-id", "same-id"],
        description=f"Duplicate {field}",
    )
reject(
    "WorkflowCheckpoint",
    "agent_version_pins",
    [
        {"agent_id": "agent-1", "version_id": "v1"},
        {"agent_id": "agent-1", "version_id": "v2"},
    ],
    description="Same agent pinned to two versions",
)
reject(
    "WorkflowCheckpoint",
    "last_processed_causes",
    [
        {"kind": "timer", "timer_id": "timer-A"},
        {"kind": "timer", "timer_id": "timer-A"},
    ],
    description="Duplicate processed timer cause",
)
for field in ("model_turns", "tool_calls", "input_tokens", "output_tokens"):
    reject("WorkflowCheckpoint", f"used_budget.{field}", -1)
reject("WorkflowCheckpoint", "used_budget.tool_calls", True)
reject("WorkflowCheckpoint", "used_budget.input_tokens", 1.5)
reject(
    "CommandClaimResult",
    "is_new",
    True,
    description="New claim incorrectly reports completed result",
)
reject("CommandClaimResult", "is_new", "false")
reject(
    "CommandClaimResult",
    "result",
    None,
    description="Completed command has no stored result",
)
reject(
    "CommandClaimResult",
    "status",
    "running",
    description="Running command incorrectly has completed result",
)
reject("PinnedRuntimeContext", "checkpoint.workflow_id", "workflow-B")
reject("PinnedRuntimeContext", "checkpoint.state_revision", 2)
reject(
    "PinnedRuntimeContext",
    "checkpoint.agent_version_pins.0.version_id",
    "unpublished-v2",
)
reject(
    "RuntimeTurnResult",
    "checkpoint.state_revision",
    1,
    description="Candidate keeps old revision",
)
reject(
    "RuntimeTurnResult",
    "checkpoint.state_revision",
    3,
    description="Candidate skips a revision",
)
reject("RuntimeTurnResult", "result.messages.0.workflow_id", "workflow-B")
reject("ConversationEvent", "sequence", 0)
reject("ConversationEvent", "schema_version", "2")
reject("ConversationEvent", "scope", {"tenant_id": "secret"})
reject("ConversationEvent", "group_id", "internal-group")
reject(
    "WorkflowRecord",
    "state",
    "technician_on_the_way",
    description="Provider status must not become core workflow state",
)
reject(
    "PartnerRequestEnvelope",
    "workflow_id",
    "workflow-A",
    description="Start command supplies existing workflow ID",
)
reject(
    "PartnerRequestEnvelope",
    "command_type",
    "workflow_reply",
    description="Reply lacks workflow ID",
)
reject("PartnerRequestEnvelope", "scope", {"tenant_id": "attacker"})
reject(
    "InboundReceipt",
    "workflow_state",
    "closed",
    description="Closed workflow still requests reply",
)
reject(
    "InboundReceipt",
    "next_action",
    "watch_request",
    description="Completed request incorrectly waits for itself",
)
reject("CloseWorkflowCommand", "expected_revision", 0)


def mutate(sample: dict[str, Any], case: dict[str, Any]) -> None:
    target = sample
    for key in case["path"][:-1]:
        target = target[int(key)] if isinstance(target, list) else target[key]
    key = case["path"][-1]
    if isinstance(target, list):
        key = int(key)
    if case["delete"]:
        del target[key]
    else:
        target[key] = deepcopy(case["value"])


class PhaseAAcceptance(unittest.TestCase):
    def test_artifacts_have_no_drift(self) -> None:
        self.assertEqual(
            json.loads((HANDOFF / "schemas.json").read_text(encoding="utf-8")),
            phase_a_schema_bundle(),
        )
        self.assertEqual(
            json.loads((HANDOFF / "samples.json").read_text(encoding="utf-8")),
            phase_a_samples(),
        )

    def test_shared_models_are_canonical_objects(self) -> None:
        for model in SHARED_MODELS:
            with self.subTest(model=model.__name__):
                self.assertIs(model, getattr(contracts, model.__name__))
        self.assertIs(
            PinnedRuntimeContext.model_fields["workflow"].annotation,
            contracts.WorkflowRecord,
        )
        self.assertIs(
            CommandClaimResult.model_fields["status"].annotation,
            contracts.RequestStatus,
        )

    def test_checkpoint_accepts_registry_actual_snapshot_refs(self) -> None:
        from agentscope.app.workforce.registry.event_protocols import (
            AsyncToolProtocol,
        )

        source = (
            HANDOFF.parent.parent / "nguyen-phuong-dong/phase_a_samples.json"
        )
        protocols = json.loads(source.read_text(encoding="utf-8"))["protocols"]
        for name, data in protocols.items():
            with self.subTest(protocol=name):
                protocol = AsyncToolProtocol.model_validate(data)
                snapshot = protocol.snapshot_ref
                self.assertIs(
                    type(snapshot), contracts.AsyncProtocolSnapshotRef
                )
                sample = deepcopy(
                    phase_a_samples()["models"]["WorkflowCheckpoint"]
                )
                sample["protocol_pins"] = [snapshot.model_dump(mode="json")]
                checkpoint = WorkflowCheckpoint.model_validate(sample)
                self.assertEqual(checkpoint.protocol_pins[0], snapshot)

    def test_all_structural_schemas_and_samples(self) -> None:
        bundle, samples = phase_a_schema_bundle(), phase_a_samples()
        for section, sample_key in (
            ("schemas", "models"),
            ("public_payloads", "public_payloads"),
        ):
            self.assertEqual(set(bundle[section]), set(samples[sample_key]))
            for name, schema in bundle[section].items():
                with self.subTest(section=section, name=name):
                    Draft202012Validator.check_schema(schema)
                    Draft202012Validator(
                        schema, format_checker=FormatChecker()
                    ).validate(samples[sample_key][name])

    def test_four_causes_are_disjoint_and_deduped_by_cause(self) -> None:
        triggers = [
            WorkflowTrigger.model_validate(item)
            for item in phase_a_samples()["triggers"]
        ]
        self.assertEqual(
            {item.cause.kind for item in triggers},
            {"request", "approval", "external_event", "timer"},
        )
        for item in triggers:
            retry = item.model_copy(
                update={"trigger_id": "new-queue-delivery"}
            )
            self.assertEqual(cause_key(item.cause), cause_key(retry.cause))
        self.assertEqual(len({cause_key(item.cause) for item in triggers}), 4)

    def test_two_tickets_share_agent_but_not_runtime_references(self) -> None:
        left, right = [
            PinnedRuntimeContext.model_validate(item)
            for item in phase_a_samples()["ticket_contexts"]
        ]
        self.assertEqual(left.workflow.scope, right.workflow.scope)
        self.assertEqual(
            left.workflow.audience.external_user_id,
            right.workflow.audience.external_user_id,
        )
        self.assertEqual(
            left.checkpoint.agent_version_pins,
            right.checkpoint.agent_version_pins,
        )
        for field in (
            "workflow_id",
            "conversation_id",
            "group_id",
            "checkpoint_ref",
        ):
            self.assertNotEqual(
                getattr(left.workflow, field), getattr(right.workflow, field)
            )
        for field in ("session_refs", "shared_state_ref", "operation_refs"):
            self.assertNotEqual(
                getattr(left.checkpoint, field),
                getattr(right.checkpoint, field),
            )

    def test_three_patterns_and_timeout_receipt_shapes(self) -> None:
        for sample in phase_a_samples()["patterns"].values():
            contracts.InboundReceipt.model_validate(sample)
        sample = deepcopy(phase_a_samples()["models"]["InboundReceipt"])
        sample.update(
            request_status="running",
            next_action="watch_request",
            result=None,
            completed_at=None,
        )
        receipt = contracts.InboundReceipt.model_validate(sample)
        self.assertEqual(receipt.workflow_id, "workflow-A")

    def test_new_and_cached_pending_claim_shapes(self) -> None:
        for is_new in (True, False):
            claim = CommandClaimResult(
                request_id="approval-without-workflow",
                is_new=is_new,
                status="accepted",
            )
            self.assertIsNone(claim.result)

    def test_duplicate_message_ids_rejected(self) -> None:
        sample = deepcopy(phase_a_samples()["models"]["RuntimeTurnResult"])
        sample["result"]["messages"] *= 2
        with self.assertRaises(ValidationError):
            MODELS["RuntimeTurnResult"].model_validate(sample)

    def test_duplicate_protocol_tool_version_rejected(self) -> None:
        sample = deepcopy(phase_a_samples()["models"]["WorkflowCheckpoint"])
        sample["protocol_pins"] *= 2
        with self.assertRaises(ValidationError):
            WorkflowCheckpoint.model_validate(sample)

    def test_public_events_exactly_match_contract_section_9_7(self) -> None:
        self.assertEqual(
            set(PUBLIC_PAYLOAD_MODELS),
            {
                "request.accepted",
                "workflow.status_changed",
                "ticket.created",
                "ticket.status_changed",
                "assistant.message",
                "approval.required",
                "approval.resolved",
                "operation.status_changed",
                "workflow.awaiting_user",
                "workflow.needs_attention",
                "workflow.closed",
            },
        )
        for event_type, payload in phase_a_samples()[
            "public_payloads"
        ].items():
            event = contracts.ConversationEvent.model_validate(
                {
                    **phase_a_samples()["models"]["ConversationEvent"],
                    "event_type": event_type,
                    "payload": payload,
                }
            )
            self.assertIs(validate_public_event(event), event)

    def test_internal_event_names_not_public(self) -> None:
        for event_type in (
            "provider.event_received",
            "provider.event_quarantined",
            "workflow.waiting",
        ):
            event = contracts.ConversationEvent.model_validate(
                {
                    **phase_a_samples()["models"]["ConversationEvent"],
                    "event_type": event_type,
                }
            )
            with self.assertRaises(ValueError):
                validate_public_event(event)

    def test_payload_allowlist_rejects_internal_fields(self) -> None:
        for name, model in PUBLIC_PAYLOAD_MODELS.items():
            for forbidden in (
                "scope",
                "credential",
                "group_id",
                "prompt",
                "raw_tool_trace",
            ):
                with self.subTest(event=name, field=forbidden):
                    sample = deepcopy(
                        phase_a_samples()["public_payloads"][name]
                    )
                    sample[forbidden] = "internal"
                    with self.assertRaises(ValidationError):
                        model.model_validate(sample)

    def test_post_and_event_reference_same_message(self) -> None:
        samples = phase_a_samples()["models"]
        message = samples["InboundReceipt"]["result"]["messages"][0]
        self.assertEqual(
            message["message_id"],
            samples["ConversationEvent"]["payload"]["message_id"],
        )
        self.assertEqual(
            message["text"], samples["ConversationEvent"]["payload"]["text"]
        )

    def test_event_round_trip_preserves_nullable_wire_keys(self) -> None:
        event = contracts.ConversationEvent.model_validate(
            phase_a_samples()["models"]["ConversationEvent"]
        )
        wire = event.model_dump(mode="json")
        self.assertIn("ticket_id", wire)
        self.assertIsNone(wire["ticket_id"])
        page = contracts.EventHistoryPage(
            items=(event,), next_cursor=event.event_id, has_more=False
        )
        self.assertEqual(page.model_dump(mode="json")["items"][0], wire)

    def test_current_shared_port_signatures_are_documented_baseline(
        self,
    ) -> None:
        expected = {
            contracts.PartnerCommandPort.claim_or_read: [
                "self",
                "actor",
                "external_request_id",
                "command_kind",
                "target_ref",
                "payload_hash",
                "uow",
            ],
            contracts.WorkflowPort.apply_external_event: [
                "self",
                "scope",
                "operation_ref",
                "normalized_event",
                "uow",
            ],
            contracts.RuntimeContinuationPort.invoke_turn: [
                "self",
                "scope",
                "trigger",
                "checkpoint",
                "execution_guard",
            ],
        }
        for method, parameters in expected.items():
            self.assertEqual(
                list(inspect.signature(method).parameters), parameters
            )


def negative_test(
    case: dict[str, Any],
) -> Callable[[PhaseAAcceptance], None]:
    def run(self: PhaseAAcceptance) -> None:
        sample = deepcopy(phase_a_samples()["models"][case["model"]])
        MODELS[case["model"]].model_validate(sample)
        mutate(sample, case)
        with self.assertRaises(ValidationError):
            MODELS[case["model"]].model_validate(sample)

    run.__doc__ = case["description"]
    return run


def positive_test(
    name: str,
    model: type[contracts.WorkforceModel],
) -> Callable[[PhaseAAcceptance], None]:
    def run(self: PhaseAAcceptance) -> None:
        instance = model.model_validate(phase_a_samples()["models"][name])
        self.assertEqual(
            model.model_validate_json(instance.model_dump_json()), instance
        )

    return run


for case in NEGATIVE_CASES:
    setattr(
        PhaseAAcceptance,
        "test_" + case["id"].replace("-", "_"),
        negative_test(case),
    )
for name, model in MODELS.items():
    setattr(PhaseAAcceptance, "test_valid_" + name, positive_test(name, model))
