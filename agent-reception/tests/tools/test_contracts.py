import asyncio
import json
from copy import deepcopy
from datetime import datetime, timezone

import httpx
import pytest
from src.tools import (
    BackendToolConfig,
    BackendToolPort,
    ReceptionTools,
    ToolContractError,
)
from src.tools import contracts as c
from src.tools.validation import (
    LLM_TOOLS,
    OPERATION_CONTRACTS,
    OPERATIONS,
    prepare_call,
    validate_input,
    validate_result,
)
from tool_fixtures import CASES, CONTEXT, EVENT, REF, case, request, success


def validated(operation, value=None, output=None):
    fixture_input, fixture_output = case(operation)
    value = fixture_input if value is None else value
    output = fixture_output if output is None else output
    return validate_result(
        operation,
        validate_input(operation, value),
        c.VerifiedContext(**CONTEXT),
        success(output),
        now=datetime(2026, 10, 1, tzinfo=timezone.utc),
    )


def test_catalogue_covers_graph_operations_without_exposing_model_tools():
    from src.graph.workflow_contracts import OPERATIONS as GRAPH_OPERATIONS

    assert (
        set(CASES)
        == set(OPERATIONS)
        == set(OPERATION_CONTRACTS)
        == set(GRAPH_OPERATIONS)
    )
    assert LLM_TOOLS == ()
    assert not hasattr(ReceptionTools, "invoke")
    assert not hasattr(ReceptionTools, "reconcile")
    for operation in OPERATIONS:
        assert hasattr(ReceptionTools, operation)
        assert OPERATION_CONTRACTS[operation].visibility == "system/internal"


@pytest.mark.parametrize("operation", OPERATIONS)
def test_named_facade_runs_validated_http_operation(operation):
    value, output = case(operation)
    captured = []

    def handler(req):
        captured.append(json.loads(req.content))
        assert req.url.path == "/internal/reception/operations/execute"
        assert req.headers["Idempotency-Key"] == "stable-key"
        return httpx.Response(200, json=success(output))

    async def scenario():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="https://backend.test"
        ) as client:
            backend = BackendToolPort(
                BackendToolConfig("https://backend.test", "synthetic-token"), client
            )
            facade = ReceptionTools(backend)
            result = await getattr(facade, operation)(
                validate_input(operation, value),
                context=c.VerifiedContext(**CONTEXT),
                idempotency_key="stable-key",
            )
            assert isinstance(result, c.Success)
            assert result.value.model_dump(mode="json", exclude_none=True) == output

    asyncio.run(scenario())
    assert len(captured) == 1
    assert captured[0]["operation"] == operation
    assert captured[0]["context"] == CONTEXT
    assert captured[0]["idempotency_key"] == "stable-key"


@pytest.mark.parametrize("operation", OPERATIONS)
def test_every_input_is_closed_and_has_required_fields(operation):
    value, _ = case(operation)
    for field in (
        "workspace_id",
        "management_unit_id",
        "team_id",
        "tenant_id",
        "resident_id",
        "phone_number",
        "building_id",
        "domain_id",
        "severity",
        "priority",
        "permissions",
    ):
        with pytest.raises(ToolContractError, match="TOOL_INPUT_INVALID"):
            validate_input(operation, {**value, field: "model-injected"})
    with pytest.raises(ToolContractError):
        validate_input(operation, {})


@pytest.mark.parametrize("operation", OPERATIONS)
def test_every_output_rejects_unknown_fields_missing_fields_and_wrong_shape(operation):
    _, output = case(operation)
    for invalid in (
        {**output, "raw_token": "synthetic-secret"},
        {},
        [],
        None,
        "success",
    ):
        input_value = validate_input(operation, case(operation)[0])
        with pytest.raises(
            ToolContractError, match="BACKEND_TOOL_RESULT_INVALID"
        ) as error:
            validate_result(
                operation, input_value, c.VerifiedContext(**CONTEXT), success(invalid)
            )
        assert "synthetic-secret" not in str(error.value)


@pytest.mark.parametrize("operation", OPERATIONS)
def test_pending_and_failure_never_fabricate_a_success(operation):
    value = validate_input(operation, case(operation)[0])
    for raw in (
        {"kind": "accepted", "operationId": "operation-synthetic"},
        {
            "kind": "failure",
            "code": "BACKEND_UNKNOWN",
            "retryable": False,
            "outcome": "unknown",
        },
        {
            "kind": "failure",
            "code": "BACKEND_REJECTED",
            "retryable": False,
            "outcome": "not_applied",
        },
    ):
        result = validate_result(operation, value, c.VerifiedContext(**CONTEXT), raw)
        assert result.model_dump() == raw
        assert not isinstance(result, c.Success)
    with pytest.raises(ToolContractError):
        validate_result(
            operation,
            value,
            c.VerifiedContext(**CONTEXT),
            {"kind": "accepted", "operationId": "operation-synthetic", "value": {}},
        )


@pytest.mark.parametrize(
    "field,bad",
    [
        ("ticket_generation", True),
        ("ticket_generation", -1),
        ("ticket_generation", "1"),
        ("ticket_generation", 2**53),
        ("ticket_version", 1),
        ("ticket_version", " "),
        ("ticket_id", None),
        ("ticket_id", "x" * 513),
    ],
)
def test_ticket_references_reject_wrong_types_and_versions(field, bad):
    with pytest.raises(ToolContractError):
        validate_input("get_ticket_status", {**REF, field: bad})


@pytest.mark.parametrize("bad", ["invalid", "STAFF", "", 1, None])
def test_handoff_reason_is_an_enum(bad):
    value, _ = case("create_ticket_draft")
    with pytest.raises(ToolContractError):
        validate_input("create_ticket_draft", {**value, "handoff_reason": bad})


def test_nested_input_fields_and_fact_authority_cannot_be_smuggled():
    value, _ = case("update_ticket_incident")
    for injected in (
        {**value["incident"], "priority": "critical"},
        {
            **value["incident"],
            "facts": [{**value["incident"]["facts"][0], "source": "staff_verified"}],
        },
        {
            **value["incident"],
            "facts": [{**value["incident"]["facts"][0], "value": float("nan")}],
        },
        {**value["incident"], "file_ids": [{"url": "https://private.invalid/image"}]},
        {**value["incident"], "file_ids": ["https://private.invalid/image"]},
        {**value["incident"], "file_ids": ["data:image/png;base64,synthetic"]},
    ):
        with pytest.raises(ToolContractError):
            validate_input("update_ticket_incident", {**value, "incident": injected})


@pytest.mark.parametrize(
    "field,bad",
    [
        ("priority", "urgent"),
        ("severity", "maximum"),
        ("request_kind", "payment"),
        ("is_emergency", 1),
    ],
)
def test_official_triage_rejects_invalid_enums_and_coercion(field, bad):
    value, output = case("submit_ticket_assessment")
    output["triage"][field] = bad
    with pytest.raises(ToolContractError):
        validated("submit_ticket_assessment", value, output)


def test_service_credential_is_not_in_config_representation():
    assert "synthetic-secret" not in repr(
        BackendToolConfig("https://backend.test", "synthetic-secret")
    )


@pytest.mark.parametrize(
    "operation,output",
    [
        (
            "get_verified_resident_context",
            {"kind": "selection_required", "questions": ["Bạn chọn căn hộ nào?"]},
        ),
        ("submit_ticket_assessment", {"status": "policy_missing"}),
        ("resolve_management_destination", {"kind": "unresolved"}),
        ("process_self_help", {"status": "revoked", "policy_version": "policy-v1"}),
    ],
)
def test_non_actionable_results_are_preserved_without_fabricated_data(
    operation, output
):
    result = validated(operation, output=output)
    assert result.value.model_dump() == output


def test_null_fact_is_preserved_through_facade_http_and_result():
    value, output = case("update_ticket_incident")
    value["incident"]["facts"][0]["value"] = None
    output["incident"]["facts"][0]["value"] = None

    def handler(req):
        body = json.loads(req.content)
        assert "value" in body["input"]["incident"]["facts"][0]
        assert body["input"]["incident"]["facts"][0]["value"] is None
        return httpx.Response(200, json=success(output))

    async def scenario():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="https://backend.test"
        ) as client:
            facade = ReceptionTools(
                BackendToolPort(
                    BackendToolConfig("https://backend.test", "synthetic-token"), client
                )
            )
            result = await facade.update_ticket_incident(
                c.IncidentInput(**value),
                context=c.VerifiedContext(**CONTEXT),
                idempotency_key="unknown-fact-key",
            )
            assert result.value.incident.facts[0].value is None

    asyncio.run(scenario())


def test_file_dedup_is_pure_and_applies_to_reconciliation_too():
    for operation in (
        "update_ticket_incident",
        "append_ticket_information",
        "respond_supervisor_interaction",
    ):
        value, _ = case(operation)
        container = (
            value["incident"] if operation == "update_ticket_incident" else value
        )
        container["file_ids"] = ["file-1", "file-1", "file-2"]
        original = deepcopy(value)
        _, _, body = prepare_call(request(operation, value))
        normalized = (
            body["input"]["incident"]
            if operation == "update_ticket_incident"
            else body["input"]
        )
        assert normalized["file_ids"] == ["file-1", "file-2"]
        assert value == original


@pytest.mark.parametrize(
    "operation",
    [
        "update_ticket_incident",
        "append_ticket_information",
        "respond_supervisor_interaction",
    ],
)
def test_success_requires_all_files_to_be_confirmed(operation):
    value, output = case(operation)
    if operation == "update_ticket_incident":
        output["incident"]["file_ids"] = []
    else:
        output["linked_file_ids"] = []
    with pytest.raises(ToolContractError, match="FILE_LINK_CONFIRMATION_MISSING"):
        validated(operation, value, output)
    # The pending references the caller owns have not been consumed.
    assert (value["incident"] if operation == "update_ticket_incident" else value)[
        "file_ids"
    ]


def test_conflicting_interaction_does_not_claim_files_were_linked():
    value, output = case("respond_supervisor_interaction")
    output.update(status="conflict", linked_file_ids=[])
    result = validated("respond_supervisor_interaction", value, output)
    assert result.value.status == "conflict"
    assert result.value.linked_file_ids == []


@pytest.mark.parametrize(
    "operation",
    [
        "update_ticket_incident",
        "submit_ticket_assessment",
        "append_ticket_information",
        "respond_supervisor_interaction",
        "request_ticket_cancellation",
        "get_ticket_status",
    ],
)
def test_ticket_result_cannot_change_ticket_or_generation(operation):
    value, output = case(operation)
    for field, bad in (("ticket_id", "other-ticket"), ("ticket_generation", 99)):
        invalid = deepcopy(output)
        invalid["ticket"][field] = bad
        with pytest.raises(ToolContractError, match="BACKEND_TICKET_MISMATCH"):
            validated(operation, value, invalid)
    output["ticket"]["ticket_version"] = "new-opaque-version"
    assert (
        validated(operation, value, output).value.ticket.ticket_version
        == "new-opaque-version"
    )


@pytest.mark.parametrize(
    "field,bad",
    [
        ("persisted", False),
        ("persisted", 1),
        ("enqueued", False),
        ("enqueued", "true"),
        ("ticket_id", "other-ticket"),
        ("ticket_generation", 8),
        ("ticket_version", "stale"),
        ("correlation_id", "other-correlation"),
        ("schema_version", "1.0"),
    ],
)
def test_handoff_requires_persisted_enqueued_matching_receipt(field, bad):
    value, output = case("handoff_ticket")
    with pytest.raises(ToolContractError):
        validated("handoff_ticket", value, {**output, field: bad})


@pytest.mark.parametrize(
    "field,bad",
    [
        ("schema_version", "1.0"),
        ("message_type", "waiting_for_customer"),
        ("message_type", "completion.requested"),
        ("ticket_version", "other-version"),
        ("ticket_generation", 9),
        ("tenant_id", "other-tenant"),
        ("correlation_id", "other-correlation"),
        ("sent_at", "2026-10-01T00:00:00"),
        ("status", "in_progress"),
    ],
)
def test_supervisor_event_v2_is_strict_and_scoped(field, bad):
    value, output = case("get_supervisor_event")
    output["payload"][field] = bad
    with pytest.raises(ToolContractError):
        validated("get_supervisor_event", value, output)


@pytest.mark.parametrize(
    "field,bad",
    [
        ("binding_id", "other-binding"),
        ("event_id", "other-event"),
        ("aggregate_version", 9),
    ],
)
def test_event_identity_is_checked(field, bad):
    value, output = case("get_supervisor_event")
    with pytest.raises(ToolContractError):
        validated("get_supervisor_event", value, {**output, field: bad})


def test_wait_validates_buffered_event_without_losing_a_newer_version():
    value, output = case("register_supervisor_wait")
    output["buffered_event"] = deepcopy(EVENT)
    output["buffered_event"]["payload"]["ticket_version"] = "v2"
    assert validated("register_supervisor_wait", value, output).value.buffered_event
    output["buffered_event"]["payload"]["tenant_id"] = "other-tenant"
    with pytest.raises(ToolContractError, match="SCOPE_MISMATCH"):
        validated("register_supervisor_wait", value, output)


def test_completed_event_requires_backend_work_completed_result():
    value, output = case("get_supervisor_event")
    output["payload"]["message_type"] = "completed"
    with pytest.raises(ToolContractError):
        validated("get_supervisor_event", value, output)
    output["payload"]["result"] = {
        "outcome": "needs_human_review",
        "summary": "Mẫu",
        "work_order_ids": [],
        "evidence_ids": [],
    }
    with pytest.raises(ToolContractError):
        validated("get_supervisor_event", value, output)
    output["payload"]["result"]["outcome"] = "work_completed"
    assert (
        validated("get_supervisor_event", value, output).value.payload.message_type
        == "completed"
    )


@pytest.mark.parametrize(
    "message_type",
    ["information_provided", "plan_approved", "plan_rejected", "plan_change_requested"],
)
def test_resident_decision_is_explicit_and_keeps_the_version_they_saw(message_type):
    value, _ = case("respond_supervisor_interaction")
    value.update(message_type=message_type, ticket_version="version-resident-saw")
    result = validate_input("respond_supervisor_interaction", value)
    assert result.message_type == message_type
    assert result.ticket_version == "version-resident-saw"
    # Ordinary appended prose never turns into an approval operation.
    ordinary = validate_input(
        "append_ticket_information",
        {**case("append_ticket_information")[0], "message": "đồng ý"},
    )
    assert not hasattr(ordinary, "message_type")


def test_empty_image_only_follow_up_and_invalid_empty_message():
    value, _ = case("append_ticket_information")
    value.update(message="", facts=[], file_ids=["file-1"])
    assert validate_input("append_ticket_information", value).file_ids == ["file-1"]
    with pytest.raises(ToolContractError):
        validate_input("append_ticket_information", {**value, "file_ids": []})


def test_self_help_checks_policy_procedure_consent_and_outcome():
    value, output = case("process_self_help")
    for field, bad in (
        ("approved", False),
        ("eligible", 1),
        ("expires_at", "2020-01-01T00:00:00Z"),
        ("policy_version", "other-policy"),
        ("citations", []),
    ):
        invalid = deepcopy(output)
        invalid["procedure"][field] = bad
        with pytest.raises(ToolContractError):
            validated("process_self_help", value, invalid)
    value["attempt"] = {
        "attempt_id": "attempt-synthetic",
        "procedure_version": "procedure-v1",
        "status": "offered",
    }
    output.update(
        status="accepted",
        consent_recorded=True,
        consent_source_message_id=value["source_message"]["id"],
    )
    assert validated("process_self_help", value, output).value.status == "accepted"
    output["consent_source_message_id"] = "different-message"
    with pytest.raises(ToolContractError, match="CONSENT_MISMATCH"):
        validated("process_self_help", value, output)
    recorded = {
        "status": "succeeded",
        "attempt_id": "attempt-synthetic",
        "policy_version": "policy-v1",
        "recorded": True,
        "source_message_id": value["source_message"]["id"],
    }
    assert validated("process_self_help", value, recorded).value.recorded
    recorded["source_message_id"] = "different-message"
    with pytest.raises(ToolContractError, match="OUTCOME_MISMATCH"):
        validated("process_self_help", value, recorded)


def test_emergency_existing_ticket_requires_complete_reference_and_receipt():
    value, output = case("escalate_emergency")
    with pytest.raises(ToolContractError):
        validate_input("escalate_emergency", {**value, "ticket_id": REF["ticket_id"]})
    with pytest.raises(ToolContractError, match="BACKEND_TICKET_MISMATCH"):
        validated("escalate_emergency", {**value, **REF}, output)
    with pytest.raises(ToolContractError, match="POLICY_VERSION_MISMATCH"):
        validated(
            "escalate_emergency", value, {**output, "policy_version": "other-policy"}
        )


def test_facade_revalidates_mutated_models_and_injected_port_responses():
    calls = []

    class Port:
        async def invoke(self, call):
            calls.append(call)
            return success({"raw_secret": "synthetic-private-value"})

    async def scenario():
        facade = ReceptionTools(Port())
        value = c.IncidentInput(**case("update_ticket_incident")[0])
        value.incident.file_ids.append(42)
        with pytest.raises(ToolContractError):
            await facade.update_ticket_incident(
                value, context=c.VerifiedContext(**CONTEXT), idempotency_key="key"
            )
        assert not calls
        with pytest.raises(ToolContractError) as error:
            await facade.create_ticket_draft(
                c.DraftInput(**case("create_ticket_draft")[0]),
                context=c.VerifiedContext(**CONTEXT),
                idempotency_key="key",
            )
        assert "synthetic-private-value" not in str(error.value)

    asyncio.run(scenario())
