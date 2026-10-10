# -*- coding: utf-8 -*-
"""Adversarial Phase A checks. No service, DB or worker execution."""

from copy import deepcopy
from datetime import datetime, timezone, timedelta
import itertools
import json
import random
from typing import Any, Callable
import unittest

from jsonschema import Draft202012Validator, FormatChecker
from pydantic import ValidationError

from agentscope.app.workforce.contracts import (
    ConversationEvent,
    RequestStatus,
    WorkforceModel,
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
    RuntimeTurnResult,
)
from fixtures import phase_a_samples


def assert_rejected(
    test: unittest.TestCase,
    model: type[WorkforceModel],
    sample: dict[str, Any],
) -> None:
    """Exercise Python-data and JSON entry points without coercing input."""
    with test.assertRaises(ValidationError):
        model.model_validate(sample)
    with test.assertRaises(ValidationError):
        model.model_validate_json(json.dumps(sample, allow_nan=False))


class PhaseAAdversarial(unittest.TestCase):
    def test_rfc3339_checker_is_active_and_rejects_naive_time(self) -> None:
        checker = FormatChecker()
        self.assertFalse(checker.conforms("2026-10-10T09:00:00", "date-time"))
        self.assertTrue(checker.conforms("2026-10-10T09:00:00Z", "date-time"))

    def test_each_workflow_guard_has_a_negative_witness(self) -> None:
        from mutation_checks import run_mutation_checks

        report = run_mutation_checks()
        self.assertGreater(report["count"], 0)
        self.assertEqual(report["survivors"], [])

    def test_duplicate_workflow_version_pin_rejected(self) -> None:
        sample = deepcopy(phase_a_samples()["models"]["PinnedRuntimeContext"])
        PinnedRuntimeContext.model_validate(sample)
        sample["workflow"]["version_pins"] *= 2
        assert_rejected(self, PinnedRuntimeContext, sample)

    def test_version_pin_permutation_is_allowed(self) -> None:
        sample = deepcopy(phase_a_samples()["models"]["PinnedRuntimeContext"])
        sample["workflow"]["version_pins"].append("version-2")
        sample["checkpoint"]["agent_version_pins"].append(
            {"agent_id": "agent-2", "version_id": "version-2"}
        )
        sample["workflow"]["version_pins"].reverse()
        PinnedRuntimeContext.model_validate(sample)

    def test_public_validator_rechecks_unvalidated_envelope_copy(self) -> None:
        event = ConversationEvent.model_validate(
            phase_a_samples()["models"]["ConversationEvent"]
        )
        for update in (
            {"sequence": 0},
            {"event_id": ""},
            {"schema_version": "2"},
        ):
            with self.subTest(update=update), self.assertRaises(ValueError):
                validate_public_event(event.model_copy(update=update))

    def test_public_validator_rejects_unknown_fields_on_constructed_event(
        self,
    ) -> None:
        sample = deepcopy(phase_a_samples()["models"]["ConversationEvent"])
        # model_copy deliberately skips validation; public validation must
        # not silently drop the newly injected field while checking shape.
        event = ConversationEvent.model_validate(sample)
        with self.assertRaises(ValueError):
            validate_public_event(event.model_copy(update={"scope": "secret"}))

    def test_public_validator_rechecks_mutated_payload(self) -> None:
        event = ConversationEvent.model_validate(
            phase_a_samples()["models"]["ConversationEvent"]
        )
        event.payload["prompt"] = "internal"
        with self.assertRaises(ValueError):
            validate_public_event(event)

    def test_seeded_cross_workflow_swaps_rejected(self) -> None:
        rng = random.Random(20261010)
        for _ in range(200):
            own, foreign = rng.sample(range(1, 100_000), 2)
            sample = deepcopy(phase_a_samples()["models"]["RuntimeTurnResult"])
            sample["checkpoint"]["workflow_id"] = f"workflow-{own}"
            sample["result"]["messages"][0]["workflow_id"] = f"workflow-{own}"
            RuntimeTurnResult.model_validate(sample)
            sample["result"]["messages"][0][
                "workflow_id"
            ] = f"workflow-{foreign}"
            assert_rejected(self, RuntimeTurnResult, sample)

    def test_dedupe_approval_cause_ignores_conflicting_approval_ref(
        self,
    ) -> None:
        sample = deepcopy(phase_a_samples()["models"]["WorkflowCheckpoint"])
        sample["last_processed_causes"] = [
            {"kind": "approval", "request_id": "same", "approval_id": "A"},
            {"kind": "approval", "request_id": "same", "approval_id": "B"},
        ]
        assert_rejected(self, WorkflowCheckpoint, sample)

    def test_dedupe_external_cause_ignores_conflicting_operation_ref(
        self,
    ) -> None:
        sample = deepcopy(phase_a_samples()["models"]["WorkflowCheckpoint"])
        sample["last_processed_causes"] = [
            {
                "kind": "external_event",
                "cause_event_id": "same",
                "operation_id": operation,
            }
            for operation in ("A", "B")
        ]
        assert_rejected(self, WorkflowCheckpoint, sample)

    def test_input_containers_are_not_aliased(self) -> None:
        sample = deepcopy(phase_a_samples()["models"]["RuntimeTurnResult"])
        instance = RuntimeTurnResult.model_validate(sample)
        sample["result"]["messages"][0]["text"] = "changed"
        sample["checkpoint"]["session_refs"].append("injected")
        self.assertNotEqual(instance.result.messages[0].text, "changed")
        self.assertNotIn("injected", instance.checkpoint.session_refs)

    def test_exported_schema_is_fresh_each_call(self) -> None:
        from agentscope.app.workforce.orchestration.phase_a import (
            phase_a_schema_bundle,
        )

        first = phase_a_schema_bundle()
        first["schemas"]["WorkflowTrigger"]["properties"].clear()
        self.assertIn(
            "cause",
            phase_a_schema_bundle()["schemas"]["WorkflowTrigger"][
                "properties"
            ],
        )


def claim_case(
    status: str,
    is_new: bool,
    has_result: bool,
) -> Callable[[PhaseAAdversarial], None]:
    def run(self: PhaseAAdversarial) -> None:
        sample = dict(request_id="command-A", is_new=is_new, status=status)
        if has_result:
            sample["result"] = {"messages": [], "data": {}}
        valid = (not is_new or status == "accepted") and (
            (status == "completed") == has_result
        )
        if valid:
            CommandClaimResult.model_validate(sample)
            CommandClaimResult.model_validate_json(json.dumps(sample))
        else:
            assert_rejected(self, CommandClaimResult, sample)

    return run


for state, new, result in itertools.product(
    RequestStatus, (False, True), (False, True)
):
    setattr(
        PhaseAAdversarial,
        f"test_claim_{state}_{new}_{result}",
        claim_case(state.value, new, result),
    )


def numeric_case(
    field: str,
    value: Any,
) -> Callable[[PhaseAAdversarial], None]:
    def run(self: PhaseAAdversarial) -> None:
        sample = deepcopy(phase_a_samples()["models"]["WorkflowCheckpoint"])
        WorkflowCheckpoint.model_validate(sample)
        sample["used_budget"][field] = value
        assert_rejected(self, WorkflowCheckpoint, sample)

    return run


for field, (tag, value) in itertools.product(
    ("model_turns", "tool_calls", "input_tokens", "output_tokens"),
    (
        ("bool", False),
        ("float", 1.0),
        ("fraction", 0.5),
        ("string", "0"),
        ("null", None),
        ("list", []),
        ("object", {}),
    ),
):
    setattr(
        PhaseAAdversarial,
        f"test_budget_{field}_{tag}",
        numeric_case(field, value),
    )


def id_case(
    value: Any,
    valid: bool,
) -> Callable[[PhaseAAdversarial], None]:
    def run(self: PhaseAAdversarial) -> None:
        sample = deepcopy(phase_a_samples()["models"]["WorkflowTrigger"])
        sample["trigger_id"] = value
        validator = Draft202012Validator(WorkflowTrigger.model_json_schema())
        self.assertEqual(validator.is_valid(sample), valid)
        if valid:
            WorkflowTrigger.model_validate_json(json.dumps(sample))
        else:
            assert_rejected(self, WorkflowTrigger, sample)

    return run


for tag, value, valid in (
    ("empty", "", False),
    ("one", "A", True),
    ("max", "A" * 200, True),
    ("over", "A" * 201, False),
    ("unicode", "ế" * 200, True),
    ("unicode_over", "ế" * 201, False),
    ("null", None, False),
    ("integer", 1, False),
    ("bool", True, False),
    ("array", ["A"], False),
    ("object", {"id": "A"}, False),
):
    setattr(
        PhaseAAdversarial,
        f"test_trigger_id_boundary_{tag}",
        id_case(value, valid),
    )


def timestamp_case(
    event_type: str,
    field: str,
    value: Any,
    valid: bool,
) -> Callable[[PhaseAAdversarial], None]:
    def run(self: PhaseAAdversarial) -> None:
        model = PUBLIC_PAYLOAD_MODELS[event_type]
        sample = deepcopy(phase_a_samples()["public_payloads"][event_type])
        model.model_validate(sample)
        sample[field] = value
        if valid:
            instance = model.model_validate(sample)
            Draft202012Validator(
                model.model_json_schema(), format_checker=FormatChecker()
            ).validate(instance.model_dump(mode="json"))
        else:
            assert_rejected(self, model, sample)

    return run


for (event_type, field), (tag, value, valid) in itertools.product(
    (("approval.required", "expires_at"), ("workflow.closed", "closed_at")),
    (
        ("utc", "2026-10-10T09:00:00Z", True),
        ("offset", "2026-10-10T16:00:00+07:00", True),
        ("naive", "2026-10-10T09:00:00", False),
        ("date_only", "2026-10-10", False),
        ("epoch_string", "0", False),
        ("offset_no_colon", "2026-10-10T09:00:00+0700", False),
        ("space_separator", "2026-10-10 09:00:00Z", False),
        ("fraction", "2026-10-10T09:00:00.123456Z", True),
        ("epoch", 0, False),
        ("null", None, False),
        ("invalid_day", "2026-02-30T09:00:00Z", False),
    ),
):
    setattr(
        PhaseAAdversarial,
        f"test_timestamp_{field}_{tag}",
        timestamp_case(event_type, field, value, valid),
    )


def timestamp_python_case(
    event_type: str,
    field: str,
) -> Callable[[PhaseAAdversarial], None]:
    def run(self: PhaseAAdversarial) -> None:
        sample = deepcopy(phase_a_samples()["public_payloads"][event_type])
        sample[field] = datetime(
            2026, 10, 10, tzinfo=timezone(timedelta(hours=7))
        )
        PUBLIC_PAYLOAD_MODELS[event_type].model_validate(sample)
        sample[field] = datetime(2026, 10, 10)
        with self.assertRaises(ValidationError):
            PUBLIC_PAYLOAD_MODELS[event_type].model_validate(sample)

    return run


for event_type, field in (
    ("approval.required", "expires_at"),
    ("workflow.closed", "closed_at"),
):
    setattr(
        PhaseAAdversarial,
        f"test_python_datetime_{field}",
        timestamp_python_case(event_type, field),
    )


def payload_case(
    event_type: str,
    injected: str,
) -> Callable[[PhaseAAdversarial], None]:
    def run(self: PhaseAAdversarial) -> None:
        model = PUBLIC_PAYLOAD_MODELS[event_type]
        sample = deepcopy(phase_a_samples()["public_payloads"][event_type])
        model.model_validate(sample)
        sample[injected] = {"value": "private"}
        assert_rejected(self, model, sample)
        self.assertFalse(
            Draft202012Validator(model.model_json_schema()).is_valid(sample)
        )

    return run


for event_type, injected in itertools.product(
    PUBLIC_PAYLOAD_MODELS,
    ("manager_account_id", "provider_integration_id", "raw_tool_trace"),
):
    setattr(
        PhaseAAdversarial,
        f"test_payload_{event_type.replace('.', '_')}_{injected}",
        payload_case(event_type, injected),
    )
