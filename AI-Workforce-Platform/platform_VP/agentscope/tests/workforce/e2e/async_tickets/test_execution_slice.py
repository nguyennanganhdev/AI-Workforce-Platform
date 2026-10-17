"""Execution integration slice with real DB/ASGI and fake adjacent ports.

This is not the full Customer API/Orchestration/worker/SSE acceptance gate.
"""

import asyncio

import httpx
from fastapi import FastAPI
from sqlalchemy import select

from agentscope.app.workforce.execution import create_router
from async_partners import ProviderBackend
from execution_fakes import (
    AUDIENCE,
    SCOPE_A,
    approved_call,
    call_fixture,
    event_fixture,
    harness,
    test_events,
)


def test_two_tickets_reuse_agent_but_isolate_operation_and_provider_updates():
    async def scenario():
        async with harness(tracking=True) as env:
            env.runtime.add_run(
                "run-B",
                audience={
                    **AUDIENCE,
                    "external_ticket_id": "TICKET-B",
                    "external_conversation_id": "CHAT-B",
                },
            )
            call_a = await approved_call(env, call_fixture("call-A", "run-A"))
            call_b = await approved_call(env, call_fixture("call-B", "run-B"))
            await env.gateway.execute(SCOPE_A, call_a)
            await env.gateway.execute(SCOPE_A, call_b)
            op_a = (
                await env.operations.get_for_workflow(SCOPE_A, "workflow-A")
            )[0]
            op_b = (
                await env.operations.get_for_workflow(SCOPE_A, "workflow-B")
            )[0]
            assert op_a["correlation_id"] != op_b["correlation_id"]
            assert op_a["external_job_id"] != op_b["external_job_id"]
            app = FastAPI()

            async def unavailable_identity():
                raise AssertionError(
                    "Provider requests cannot invoke a manager/customer "
                    "identity path"
                )

            app.include_router(
                create_router(
                    env.gateway,
                    env.approvals,
                    None,
                    env.ingress,
                    unavailable_identity,
                    unavailable_identity,
                    env.auth,
                )
            )
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client:
                provider = ProviderBackend(
                    client, {"Authorization": "Bearer TEST-ONLY-PROVIDER"}
                )
                for operation, suffix, version, status in [
                    (op_a, "A1", 1, "assigned"),
                    (op_b, "B1", 1, "assigned"),
                    (op_a, "A2", 2, "completed"),
                    (op_b, "B2", 2, "on_the_way"),
                ]:
                    receipt = await provider.send(
                        event_fixture(
                            suffix,
                            job_id=operation["external_job_id"],
                            correlation=operation["correlation_id"],
                            version=version,
                            status=status,
                        )
                    )
                    assert (
                        await env.processor.process(receipt["receipt_id"])
                        == "applied"
                    )
                env.workflow.closed.add("workflow-A")
                late = await provider.send(
                    event_fixture(
                        "A3",
                        job_id=op_a["external_job_id"],
                        version=3,
                        status="on_the_way",
                    )
                )
                assert (
                    await env.processor.process(late["receipt_id"])
                    == "ignored"
                )
                assert (await provider.receipt("B2"))[
                    "ingestion_status"
                ] == "applied"
            async with env.repo.transaction() as uow:
                events = (
                    (await uow.execute(select(test_events))).mappings().all()
                )
                facts = [
                    r["payload"]
                    for r in events
                    if r["id"].startswith("apply-")
                ]
                assert [f["workflow_id"] for f in facts] == [
                    "workflow-A",
                    "workflow-B",
                    "workflow-A",
                    "workflow-B",
                ]
            current_b = await env.repo.read("operations", SCOPE_A, op_b["id"])
            assert (
                current_b["job_status"] == "on_the_way"
                and current_b["pending"]
            )
            assert env.provider.calls == 2

    asyncio.run(scenario())
