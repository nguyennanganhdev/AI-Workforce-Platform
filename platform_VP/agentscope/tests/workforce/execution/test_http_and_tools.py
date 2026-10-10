"""ASGI boundaries and guarded SDK ToolBase behavior, without paid services."""

import asyncio
import json
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import insert, select

from agentscope.app.workforce.contracts import ActorContext, RequestResult
from agentscope.app.workforce.execution import (
    PartnerApprovalService,
    create_router,
)
from agentscope.app.workforce.execution._mcp_adapter import McpAdapter
from agentscope.app.workforce.execution._toolkit import guarded_tool
from agentscope.app.workforce.execution._utils import ExecutionError, digest
from execution_fakes import (
    MANAGER,
    PARTNER,
    SCOPE_A,
    SCOPE_B,
    approved_call,
    call_fixture,
    event_fixture,
    harness,
    test_events,
)


def run(test):
    return asyncio.run(test())


class Commands:
    """TEST ONLY shared namespace fake backed by the same transaction."""

    def __init__(self, env, typed_claim=False):
        self.env = env
        self.typed_claim = typed_claim

    def claim(self, **fields):
        if not self.typed_claim:
            return fields
        from agentscope.app.workforce.orchestration.workflows.phase_a import (
            CommandClaimResult,
        )

        return CommandClaimResult(
            status="accepted" if fields["is_new"] else "completed", **fields
        )

    async def authorize_approval(self, actor, approval_id, body, uow):
        record = await self.env.repo.get(
            "approvals", approval_id, uow, SCOPE_A
        )
        audience = record["audience_ref"]
        for field in (
            "external_user_id",
            "external_ticket_id",
            "external_conversation_id",
        ):
            if body[field] != audience[field]:
                raise ExecutionError("WORKFLOW_BINDING_MISMATCH")
        if body["workflow_id"] != record["workflow_id"]:
            raise ExecutionError("WORKFLOW_BINDING_MISMATCH")
        return {"scope": SCOPE_A, "audience": audience}

    async def claim_or_read(
        self, actor, request_id, command_kind, target_ref, payload_hash, uow
    ):
        assert isinstance(actor, ActorContext)
        key = "command-" + request_id
        rows = (
            (
                await uow.execute(
                    select(test_events).where(test_events.c.id == key)
                )
            )
            .mappings()
            .all()
        )
        if rows:
            payload = rows[0]["payload"]
            if payload["hash"] != payload_hash:
                raise ExecutionError("IDEMPOTENCY_CONFLICT")
            return self.claim(
                is_new=False, request_id=request_id, result=payload["result"]
            )
        await uow.execute(
            insert(test_events).values(id=key, payload={"hash": payload_hash})
        )
        return self.claim(is_new=True, request_id=request_id)

    async def record_result(self, request_id, result, uow):
        from sqlalchemy import update

        assert isinstance(result, RequestResult)
        row = (
            (
                await uow.execute(
                    select(test_events).where(
                        test_events.c.id == "command-" + request_id
                    )
                )
            )
            .mappings()
            .one()
        )
        await uow.execute(
            update(test_events)
            .where(test_events.c.id == row["id"])
            .values(
                payload={
                    **row["payload"],
                    "result": result.model_dump(mode="json"),
                }
            )
        )


def app_fixture(env, manager_scope=SCOPE_A, typed_claim=False):
    app = FastAPI()

    async def manager():
        return {"scope": manager_scope, "actor": MANAGER}

    async def customer():
        return ActorContext.model_validate(PARTNER)

    partner_approvals = PartnerApprovalService(
        env.approvals, Commands(env, typed_claim)
    )
    app.include_router(
        create_router(
            env.gateway,
            env.approvals,
            partner_approvals,
            env.ingress,
            manager,
            customer,
            env.auth,
            max_provider_bytes=1024,
        )
    )
    return app


def test_provider_http_raw_auth_precedes_parse_and_ack_is_durable():
    async def scenario():
        async with harness(tracking=True) as env:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_fixture(env)),
                base_url="http://test",
            ) as client:
                response = await client.post(
                    "/workforce/v1/provider/job-events",
                    content=b"invalid JSON",
                )
                assert response.status_code == 401
                headers = {"Authorization": "Bearer TEST-ONLY-PROVIDER"}
                response = await client.post(
                    "/workforce/v1/provider/job-events",
                    content=b"invalid JSON",
                    headers=headers,
                )
                assert response.status_code == 422
                response = await client.post(
                    "/workforce/v1/provider/job-events",
                    content=b"x" * 1025,
                    headers=headers,
                )
                assert response.status_code == 413
                event = event_fixture(correlation="unbound")
                response = await client.post(
                    "/workforce/v1/provider/job-events",
                    json={**event, "manager_account_id": "B"},
                    headers=headers,
                )
                assert response.status_code == 422
                env.jobs.fail = True
                transport = httpx.ASGITransport(
                    app=app_fixture(env), raise_app_exceptions=False
                )
                async with httpx.AsyncClient(
                    transport=transport, base_url="http://test"
                ) as broken:
                    response = await broken.post(
                        "/workforce/v1/provider/job-events",
                        json=event,
                        headers=headers,
                    )
                    assert response.status_code == 500
                env.jobs.fail = False
                response = await client.post(
                    "/workforce/v1/provider/job-events",
                    json=event,
                    headers=headers,
                )
                assert response.status_code == 202
                receipt = response.json()
                await env.processor.process(receipt["receipt_id"])
                response = await client.get(
                    "/workforce/v1/provider/event-receipts/"
                    + receipt["receipt_id"],
                    headers=headers,
                )
                assert response.json()["ingestion_status"] == "quarantined"
                assert set(response.json()) == {
                    "receipt_id",
                    "ingestion_status",
                    "duplicate",
                    "received_at",
                }

    run(scenario)


def test_http_execution_owner_and_no_public_execute_endpoint():
    async def scenario():
        async with harness() as env:
            call = await approved_call(env)
            await env.gateway.execute(SCOPE_A, call)
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_fixture(env, SCOPE_B)),
                base_url="http://test",
            ) as client:
                response = await client.get("/workforce/v1/executions/call-A")
                assert response.status_code == 404
                response = await client.post(
                    "/workforce/v1/executions", json=call
                )
                assert response.status_code == 404

    run(scenario)


@pytest.mark.parametrize("typed_claim", [False, True])
def test_partner_consent_shared_idempotency_and_ticket_binding(typed_claim):
    async def scenario():
        async with harness() as env:
            env.runtime.contexts["run-A"]["allowed_decider"] = {
                "kind": "partner",
                "partner_client_id": "customer",
                "external_user_id": "resident-123",
            }
            proposed = await env.gateway.execute(SCOPE_A, call_fixture())
            approval = await env.repo.read(
                "approvals", SCOPE_A, proposed["approval_id"]
            )
            body = {
                "schema_version": "1",
                "external_request_id": "consent-1",
                "external_user_id": "resident-123",
                "external_ticket_id": "TICKET-A",
                "external_conversation_id": "CHAT-A",
                "workflow_id": "workflow-A",
                "decision": "approve",
                "expected_revision": approval["revision"],
                "arguments_hash": approval["arguments_hash"],
                "quote_ref": approval["quote"]["quote_ref"],
            }
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(
                    app=app_fixture(env, typed_claim=typed_claim)
                ),
                base_url="http://test",
            ) as client:
                path = (
                    "/workforce/v1/partner/approvals/"
                    + approval["id"]
                    + "/decision"
                )
                response = await client.post(
                    path, json={**body, "external_ticket_id": "TICKET-B"}
                )
                assert response.status_code == 409
                response = await client.post(
                    path, json={**body, "quote_ref": "stale"}
                )
                assert response.status_code == 409
                first = await client.post(path, json=body)
                replay = await client.post(path, json=body)
                assert first.status_code == replay.status_code == 202
                assert first.json() == replay.json()
                env.runtime.active = False
                denied_replay = await client.post(path, json=body)
                assert denied_replay.status_code == 403
                assert env.provider.calls == 0
                env.runtime.active = True
                conflict = await client.post(
                    path, json={**body, "decision": "reject"}
                )
                assert conflict.status_code == 409
                manager_path = (
                    "/workforce/v1/approvals/" + approval["id"] + "/decision"
                )
                denied = await client.post(
                    manager_path,
                    json={
                        "decision": "approve",
                        "arguments_hash": approval["arguments_hash"],
                        "quote_hash": approval["quote_hash"],
                    },
                )
                assert denied.status_code == 403
                result = await env.gateway.execute(
                    SCOPE_A, {**call_fixture(), "approval_id": approval["id"]}
                )
                assert (
                    result["status"] == "succeeded" and env.provider.calls == 1
                )

    run(scenario)


def test_guarded_tool_call_and_dunder_call_both_use_policy():
    async def scenario():
        async with harness() as env:

            async def factory(tool_id, arguments):
                return {**call_fixture(), "arguments": arguments}

            tool = guarded_tool(env.gateway, SCOPE_A, env.descriptor, factory)
            env.runtime.active = False
            for invoke in (tool.call, tool.__call__):
                chunk = await invoke(room="FAKE-seaview")
                assert "AUTHORIZATION_REVOKED" in chunk.content[0].text
            assert env.provider.calls == 0

    run(scenario)


def test_prepare_toolkit_contains_only_pinned_guarded_bindings():
    async def scenario():
        async with harness() as env:

            async def call_factory(scope, context, spec, tool_id, arguments):
                return {**call_fixture(), "arguments": arguments}

            env.gateway.call_factory = call_factory
            spec = {
                **env.runtime.spec,
                "tool_bindings": env.runtime.spec["tool_bindings"]
                + [
                    {
                        "tool_id": "technical",
                        "tool_version_id": "technical.v1",
                        "schema_hash": "fake",
                        "required_capability": "technical",
                    }
                ],
            }
            toolkit = await env.gateway.prepare_toolkit(
                SCOPE_A, env.runtime.contexts["run-A"], spec
            )
            schemas = await toolkit.get_tool_schemas()
            assert [schema["function"]["name"] for schema in schemas] == [
                env.descriptor["llm_alias"]
            ]
            tool = await toolkit.get_tool(env.descriptor["llm_alias"])
            chunk = await tool(room="FAKE-seaview")
            assert (
                "awaiting_approval" in chunk.content[0].text
                and env.provider.calls == 0
            )

    run(scenario)


def test_real_stdio_mcp_mock_schema_and_idempotency():
    async def scenario():
        from agentscope.mcp import MCPClient, StdioMCPConfig

        script = (
            Path(__file__).resolve().parents[1] / "fixtures" / "mock_mcp.py"
        )
        client = MCPClient(
            name="FAKE-stdio",
            is_stateful=True,
            mcp_config=StdioMCPConfig(
                command=sys.executable, args=[str(script)]
            ),
        )
        await client.connect()
        try:
            search = await client.get_tool("hotel_search")
            chunk = await search(location="Bai Chay")
            assert "FAKE" in chunk.content[0].text
            booking = await client.get_tool("hotel_book")
            first = await booking(room="FAKE-room", idempotency_key="test-1")
            again = await booking(room="FAKE-room", idempotency_key="test-1")
            assert first.content[0].text == again.content[0].text
            # Exercise the actual MCPAdapter around an owned SDK client.
            async with harness() as env:
                env.descriptor["input_schema"] = booking.input_schema
                env.descriptor["schema_hash"] = digest(booking.input_schema)
                env.runtime.spec["tool_bindings"][0]["schema_hash"] = (
                    env.descriptor["schema_hash"]
                )

                class JsonProjector:
                    async def project(self, scope, descriptor, chunk):
                        return json.loads(chunk.content[0].text)

                @asynccontextmanager
                async def factory(scope, descriptor, credential):
                    yield client

                env.gateway.mcp = McpAdapter(
                    env.secrets,
                    factory,
                    JsonProjector(),
                    idempotency_fields={"hotel.book.v1": "idempotency_key"},
                )
                call = call_fixture()
                call = await approved_call(env, call)
                result = await env.gateway.execute(SCOPE_A, call)
                assert (
                    result["status"] == "succeeded"
                    and result["output"]["fixture"]
                )
        finally:
            await client.close()

    run(scenario)
