import asyncio
import json
from copy import deepcopy

import httpx
import pytest
from src.tools import (
    BackendToolConfig,
    BackendToolPort,
    ReceptionTools,
    ToolContractError,
)
from src.tools import contracts as c
from tool_fixtures import CONTEXT, case, request, success


def test_first_ticket_flow_uses_named_operations_and_backend_versions():
    expected_order = [
        "create_ticket_draft",
        "get_verified_resident_context",
        "update_ticket_incident",
        "submit_ticket_assessment",
        "resolve_management_destination",
        "handoff_ticket",
        "register_supervisor_wait",
        "get_supervisor_event",
    ]
    captured = []

    def handler(req):
        body = json.loads(req.content)
        operation = body["operation"]
        assert operation == expected_order[len(captured)]
        captured.append(body)
        _, output = case(operation)
        if "ticket_version" in body["input"]:
            assert body["input"]["ticket_version"] == (
                "v1" if len(captured) <= 3 else "v2" if len(captured) == 4 else "v3"
            )
        if operation in ("update_ticket_incident", "submit_ticket_assessment"):
            version = 2 if operation == "update_ticket_incident" else 3
            output["ticket"].update(
                ticket_version=f"v{version}", aggregate_version=version
            )
        if operation == "resolve_management_destination":
            output["route"]["ticket_version"] = "v3"
        if operation in ("handoff_ticket", "register_supervisor_wait"):
            output["ticket_version"] = "v3"
        if operation == "get_supervisor_event":
            output["payload"]["ticket_version"] = "v3"
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
            context = c.VerifiedContext(**CONTEXT)
            draft = await facade.create_ticket_draft(
                c.DraftInput(**case("create_ticket_draft")[0]),
                context=context,
                idempotency_key="draft-key",
            )

            def ref(ticket):
                return {
                    key: getattr(ticket, key)
                    for key in ("ticket_id", "ticket_generation", "ticket_version")
                }

            ticket = draft.value
            await facade.get_verified_resident_context(
                c.ProfileInput(
                    **{**case("get_verified_resident_context")[0], **ref(ticket)}
                ),
                context=context,
                idempotency_key="profile-key",
            )
            incident = await facade.update_ticket_incident(
                c.IncidentInput(**{**case("update_ticket_incident")[0], **ref(ticket)}),
                context=context,
                idempotency_key="incident-key",
            )
            assessment = await facade.submit_ticket_assessment(
                c.AssessmentInput(
                    **{
                        **case("submit_ticket_assessment")[0],
                        **ref(incident.value.ticket),
                    }
                ),
                context=context,
                idempotency_key="assessment-key",
            )
            ticket = assessment.value.ticket
            route = await facade.resolve_management_destination(
                c.TicketRef(**ref(ticket)), context=context, idempotency_key="route-key"
            )
            assert route.value.route.workspace_id == "workspace-synthetic"
            handoff = await facade.handoff_ticket(
                c.HandoffInput(**{**case("handoff_ticket")[0], **ref(ticket)}),
                context=context,
                idempotency_key="handoff-key",
            )
            wait = await facade.register_supervisor_wait(
                c.WaitInput(**ref(ticket), correlation_id=handoff.value.correlation_id),
                context=context,
                idempotency_key="wait-key",
            )
            assert wait.value.registered is True
            event = await facade.get_supervisor_event(
                c.EventInput(**{**case("get_supervisor_event")[0], **ref(ticket)}),
                context=context,
                idempotency_key="event-key",
            )
            assert event.value.payload.message_type == "in_progress"

    asyncio.run(scenario())
    assert [body["operation"] for body in captured] == expected_order
    assert len({body["idempotency_key"] for body in captured}) == 8
    assert all(body["context"] == CONTEXT for body in captured)
    assert all(
        not ({"workspace_id", "team_id", "resident", "location"} & body["input"].keys())
        for body in captured
    )


def test_reconcile_uses_identical_normalized_body_and_result_validation():
    captured = []
    value, output = case("append_ticket_information")
    value["file_ids"] = ["file-1", "file-1"]
    original = deepcopy(value)

    def handler(req):
        captured.append((req.url.path, req.content, req.headers["Idempotency-Key"]))
        if req.url.path == "/execute-configured":
            raise httpx.ReadTimeout("synthetic timeout", request=req)
        return httpx.Response(200, json=success(output))

    async def scenario():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="https://backend.test"
        ) as client:
            port = BackendToolPort(
                BackendToolConfig(
                    "https://backend.test",
                    "synthetic-token",
                    operation_path="/execute-configured",
                    reconcile_path="/reconcile-configured",
                ),
                client,
            )
            call = request("append_ticket_information", value)
            result = await port.invoke(call)
            assert result["kind"] == "failure" and result["outcome"] == "unknown"
            result = await port.reconcile(call)
            assert result["kind"] == "success"
            assert result["value"]["linked_file_ids"] == ["file-1"]

    asyncio.run(scenario())
    assert [item[0] for item in captured] == [
        "/execute-configured",
        "/execute-configured",
        "/reconcile-configured",
    ]
    assert len({(item[1], item[2]) for item in captured}) == 1
    assert value == original


@pytest.mark.parametrize("method", ["invoke", "reconcile"])
def test_invalid_requests_never_reach_http_and_errors_do_not_leak(method, caplog):
    captured = []

    def handler(req):
        captured.append(req)
        return httpx.Response(500)

    invalids = []
    for field in CONTEXT:
        call = request("create_ticket_draft")
        del call["context"][field]
        invalids.append(call)
    for key, value in (
        ("operation", "model-chosen-operation"),
        ("operation", []),
        ("idempotencyKey", " "),
        ("extra", "synthetic-secret"),
    ):
        invalids.append({**request("create_ticket_draft"), key: value})
    call = request("create_ticket_draft")
    call["context"]["permissions"] = ["admin"]
    invalids.append(call)
    call = request("create_ticket_draft")
    call["input"]["workspace_id"] = "synthetic-private-scope"
    invalids.append(call)

    async def scenario():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="https://backend.test"
        ) as client:
            port = BackendToolPort(
                BackendToolConfig("https://backend.test", "synthetic-token"), client
            )
            for call in invalids:
                with pytest.raises(ToolContractError) as error:
                    await getattr(port, method)(call)
                assert "synthetic-" not in str(error.value)

    asyncio.run(scenario())
    assert captured == []
    assert "synthetic-" not in caplog.text


@pytest.mark.parametrize("method", ["invoke", "reconcile"])
def test_malformed_success_is_not_a_success_or_an_automatic_new_mutation(method):
    captured = []

    def handler(req):
        captured.append(req)
        return httpx.Response(200, json=success({"persisted": True, "enqueued": True}))

    async def scenario():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="https://backend.test"
        ) as client:
            port = BackendToolPort(
                BackendToolConfig("https://backend.test", "synthetic-token"), client
            )
            with pytest.raises(ToolContractError):
                await getattr(port, method)(request("handoff_ticket"))

    asyncio.run(scenario())
    assert len(captured) == 1
