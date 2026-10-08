"""Fault sequences at the real facade/HTTP boundary, with synthetic backends.

These prove client behavior only, not production idempotency/authentication.
Known failures are documented in the PH16_ADVERSARIAL_TESTS handoff.
"""

import asyncio
import json
from copy import deepcopy
from dataclasses import replace

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


def backend(client, **options):
    return BackendToolPort(
        BackendToolConfig("https://backend.test", "synthetic-token", **options),
        client,
    )


def client_for(handler):
    return httpx.AsyncClient(
        base_url="https://backend.test", transport=httpx.MockTransport(handler)
    )


@pytest.mark.parametrize("method", ["invoke", "reconcile"])
@pytest.mark.parametrize(
    "lost_response", [httpx.ReadTimeout, httpx.RemoteProtocolError]
)
def test_last_attempt_response_loss_must_not_reuse_previous_not_applied(
    method, lost_response
):
    calls = []

    def handler(req):
        calls.append((req.content, req.headers["Idempotency-Key"]))
        if len(calls) == 1:
            return httpx.Response(
                503,
                json={
                    "kind": "failure",
                    "code": "BUSY",
                    "retryable": True,
                    "outcome": "not_applied",
                },
            )
        # Execute may have committed; reconcile may have found its stored result.
        # In either case the client did not receive that result.
        raise lost_response("synthetic response loss", request=req)

    async def scenario():
        async with client_for(handler) as client:
            result = await getattr(backend(client), method)(
                request("append_ticket_information")
            )
            assert len(calls) == 2 and calls[0] == calls[1]
            assert result["outcome"] == "unknown", result

    asyncio.run(scenario())


@pytest.mark.parametrize("method", ["invoke", "reconcile"])
def test_response_loss_followed_by_success_uses_same_operation(method):
    calls = []
    _, output = case("handoff_ticket")

    def handler(req):
        calls.append((req.content, req.headers["Idempotency-Key"]))
        if len(calls) == 1:
            raise httpx.ReadTimeout("synthetic lost receipt", request=req)
        return httpx.Response(200, json=success(output))

    async def scenario():
        async with client_for(handler) as client:
            result = await getattr(backend(client), method)(request("handoff_ticket"))
            assert result == success(output)

    asyncio.run(scenario())
    assert len(calls) == 2 and calls[0] == calls[1]


@pytest.mark.parametrize("method", ["invoke", "reconcile"])
@pytest.mark.parametrize(
    "status", [400, 401, 403, 404, 409, 410, 422, 429, 500, 502, 503, 504]
)
def test_http_error_cannot_claim_handoff_success(method, status):
    calls = []
    _, output = case("handoff_ticket")

    def handler(req):
        calls.append((req.content, req.headers["Idempotency-Key"]))
        # A proxy/error endpoint sends success-shaped JSON with an error status.
        return httpx.Response(status, json=success(output))

    async def scenario():
        async with client_for(handler) as client:
            result = await getattr(backend(client), method)(request("handoff_ticket"))
            assert result["kind"] == "failure"
            assert "value" not in result
            if status in (429, 500, 502, 503, 504):
                assert result["outcome"] == "unknown"

    asyncio.run(scenario())
    assert 1 <= len(calls) <= 2
    assert all(call == calls[0] for call in calls)


@pytest.mark.parametrize("method", ["invoke", "reconcile"])
@pytest.mark.parametrize(
    "status,body",
    [(200, b"<html>synthetic-secret</html>"), (204, b""), (200, b"null"), (200, b"[]")],
    ids=["html", "empty-204", "null", "array"],
)
def test_malformed_http_success_is_not_retried_as_a_new_mutation(method, status, body):
    calls = []

    def handler(req):
        calls.append(req)
        return httpx.Response(status, content=body)

    async def scenario():
        async with client_for(handler) as client:
            with pytest.raises(ToolContractError) as error:
                await getattr(backend(client), method)(request("handoff_ticket"))
            assert "synthetic-secret" not in str(error.value)

    asyncio.run(scenario())
    assert len(calls) == 1


@pytest.mark.parametrize("initial_result", ["accepted", "response_lost", "cancelled"])
def test_pending_request_survives_new_client_and_reconciles_without_execute(
    initial_result, tmp_path
):
    call = request("append_ticket_information")
    call["input"]["file_ids"] = ["file-1", "file-1"]
    original = deepcopy(call)
    checkpoint = tmp_path / "pending.json"
    checkpoint.write_text(json.dumps(call), encoding="utf-8")
    calls = []
    writes = 0
    _, output = case("append_ticket_information")

    async def scenario():
        committed = asyncio.Event()

        async def handler(req):
            nonlocal writes
            calls.append((req.url.path, req.content, req.headers["Idempotency-Key"]))
            if req.url.path.endswith("/execute"):
                writes += 1
                committed.set()
                if initial_result == "response_lost":
                    raise httpx.ReadTimeout("lost after synthetic commit", request=req)
                if initial_result == "cancelled":
                    await asyncio.Event().wait()
                return httpx.Response(
                    202, json={"kind": "accepted", "operationId": "pending-synthetic"}
                )
            assert req.url.path.endswith("/reconcile")
            if len(calls) == 2:
                return httpx.Response(
                    202, json={"kind": "accepted", "operationId": "pending-synthetic"}
                )
            return httpx.Response(200, json=success(output))

        async with client_for(handler) as first_client:
            port = backend(first_client, max_attempts=1)
            if initial_result == "cancelled":
                task = asyncio.create_task(port.invoke(call))
                try:
                    await asyncio.wait_for(committed.wait(), timeout=2)
                finally:
                    task.cancel()
                    with pytest.raises(asyncio.CancelledError):
                        await task
            else:
                result = await port.invoke(call)
                assert result["kind"] != "success"
                if initial_result == "response_lost":
                    assert result["outcome"] == "unknown"
            assert call == original

        # Simulated caller checkpoint, not a claim about the graph's migration.
        recovered = json.loads(checkpoint.read_text(encoding="utf-8"))
        async with client_for(handler) as second_client:
            recreated = backend(second_client)
            result = await recreated.reconcile(recovered)
            assert result["kind"] == "accepted" and "value" not in result
            assert recovered == original
            result = await recreated.reconcile(recovered)
            assert result["value"]["linked_file_ids"] == ["file-1"]

    asyncio.run(scenario())
    assert writes == 1
    assert len(calls) == 3
    assert len({(body, key) for _, body, key in calls}) == 1


@pytest.mark.parametrize(
    "operation",
    [
        "update_ticket_incident",
        "append_ticket_information",
        "respond_supervisor_interaction",
    ],
)
def test_partial_file_confirmation_then_reconcile_preserves_original_request(operation):
    value, output = case(operation)
    files = value["incident"] if operation == "update_ticket_incident" else value
    files["file_ids"] = ["file-1", "file-2", "file-1"]
    if operation == "update_ticket_incident":
        output["incident"]["file_ids"] = ["file-1", "file-2"]
    else:
        output["linked_file_ids"] = ["file-1", "file-2"]
    partial = deepcopy(output)
    if operation == "update_ticket_incident":
        partial["incident"]["file_ids"] = ["file-1"]
    else:
        partial["linked_file_ids"] = ["file-1"]
    call = request(operation, value)
    original = deepcopy(call)
    calls = []

    def handler(req):
        calls.append((req.url.path, req.content, req.headers["Idempotency-Key"]))
        return httpx.Response(
            200, json=success(partial if req.url.path.endswith("/execute") else output)
        )

    async def scenario():
        async with client_for(handler) as client:
            port = backend(client)
            with pytest.raises(
                ToolContractError, match="FILE_LINK_CONFIRMATION_MISSING"
            ):
                await port.invoke(call)
            assert call == original and len(calls) == 1
            # A recreated adapter must validate the original operation's receipt.
            result = await backend(client).reconcile(call)
            assert result == success(output)
            assert call == original

    asyncio.run(scenario())
    assert len(calls) == 2
    assert calls[0][1:] == calls[1][1:]


def test_same_key_different_body_conflict_is_not_retried_or_turned_into_success():
    first = request("append_ticket_information")
    changed = deepcopy(first)
    changed["input"]["message"] = "Different resident follow-up"
    calls = []
    _, output = case("append_ticket_information")

    def handler(req):
        calls.append((req.content, req.headers["Idempotency-Key"]))
        if len(calls) == 1:
            return httpx.Response(200, json=success(output))
        return httpx.Response(
            409,
            json={
                "kind": "failure",
                "code": "IDEMPOTENCY_CONFLICT",
                "retryable": False,
                "outcome": "not_applied",
            },
        )

    async def scenario():
        async with client_for(handler) as client:
            port = backend(client)
            assert (await port.invoke(first))["kind"] == "success"
            result = await port.invoke(changed)
            assert result["kind"] == "failure"
            assert result["code"] == "IDEMPOTENCY_CONFLICT"
            assert "value" not in result

    asyncio.run(scenario())
    assert len(calls) == 2
    assert calls[0][1] == calls[1][1]
    assert calls[0][0] != calls[1][0]


@pytest.mark.parametrize(
    "swapped", [False, True], ids=["reordered-valid", "cross-tenant-response"]
)
def test_concurrent_event_responses_stay_scoped_to_each_caller(swapped):
    contexts, inputs, outputs = {}, {}, {}
    for name in ("a", "b"):
        contexts[name] = {
            **CONTEXT,
            "tenantId": "tenant-" + name,
            "bindingId": "binding-" + name,
        }
        value, output = case("get_supervisor_event")
        # Keep ticket/correlation identical to isolate tenant and binding checks.
        output["binding_id"] = contexts[name]["bindingId"]
        output["payload"]["tenant_id"] = contexts[name]["tenantId"]
        inputs[name], outputs[name] = value, output
    arrival = []

    async def scenario():
        second_arrived = asyncio.Event()

        async def handler(req):
            body = json.loads(req.content)
            name = body["context"]["tenantId"][-1]
            if name == "a":
                await second_arrived.wait()
            else:
                second_arrived.set()
            arrival.append(name)
            owner = ("b" if name == "a" else "a") if swapped else name
            return httpx.Response(200, json=success(outputs[owner]))

        async with client_for(handler) as client:
            facade = ReceptionTools(backend(client))
            results = await asyncio.wait_for(
                asyncio.gather(
                    *[
                        facade.get_supervisor_event(
                            c.EventInput(**inputs[name]),
                            context=c.VerifiedContext(**contexts[name]),
                            idempotency_key="same-key-in-separate-tenants",
                        )
                        for name in ("a", "b")
                    ],
                    return_exceptions=True,
                ),
                timeout=2,
            )
            for name, result in zip(("a", "b"), results):
                if swapped:
                    assert isinstance(result, ToolContractError)
                    assert str(result) == "BACKEND_EVENT_SCOPE_MISMATCH"
                else:
                    assert result.value.payload.tenant_id == contexts[name]["tenantId"]

    asyncio.run(scenario())
    assert arrival == ["b", "a"]


@pytest.mark.parametrize("status", ["revoked", "expired"])
def test_self_help_recheck_does_not_reuse_previously_offered_steps(status):
    value, offered = case("process_self_help")
    calls = []

    def handler(req):
        calls.append(json.loads(req.content))
        if len(calls) == 1:
            return httpx.Response(200, json=success(offered))
        return httpx.Response(
            200,
            json=success({"status": status, "policy_version": value["policy_version"]}),
        )

    async def scenario():
        async with client_for(handler) as client:
            facade = ReceptionTools(backend(client))
            context = c.VerifiedContext(**CONTEXT)
            proposal = await facade.process_self_help(
                c.SelfHelpInput(**value), context=context, idempotency_key="offer-key"
            )
            assert proposal.value.status == "offered"
            follow_up = deepcopy(value)
            follow_up["source_message"].update(id="consent-message", text="I agree")
            follow_up["attempt"] = {
                "attempt_id": proposal.value.attempt_id,
                "procedure_version": proposal.value.procedure.version,
                "status": "offered",
            }
            result = await facade.process_self_help(
                c.SelfHelpInput(**follow_up),
                context=context,
                idempotency_key="consent-key",
            )
            assert result.value.status == status
            assert not hasattr(result.value, "procedure")
            assert not hasattr(result.value, "consent_recorded")

    asyncio.run(scenario())
    assert len(calls) == 2
    assert calls[0]["idempotency_key"] != calls[1]["idempotency_key"]


@pytest.mark.xfail(strict=True, reason=(
    "The typed port (src/tools) is not wired into the runtime: its call envelope refuses the graph's request "
    "(timeoutMs, signal and the context's checkpoint, initiatedBy and permissions), so nothing reaches HTTP. "
    "The runtime uses src/runtime/backend.py."))
def test_existing_graph_can_reach_http_with_new_backend_port():
    from workflow_fixture import REQUEST, harness

    calls = []

    def handler(req):
        calls.append(req)
        return httpx.Response(200, json=success(case("create_ticket_draft")[1]))

    async def scenario():
        async with client_for(handler) as client:
            h = harness()
            graph = h.factory.create(replace(h.dependencies, tools=backend(client)))
            result = await graph.run(deepcopy(REQUEST))
            assert calls, {
                "phase": result["state"]["phase"],
                "pending": result["state"]["pending"]["operation"],
                "http_calls": len(calls),
            }

    asyncio.run(scenario())
