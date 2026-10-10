"""Full-platform acceptance requires the integrated test factory.

Set WORKFORCE_E2E_FACTORY to module:function returning an async context manager
whose client is the composed app with DB/worker and mock providers.
No replacement Customer API/runtime is implemented in this owner's fixtures.
"""

import asyncio
import importlib
import os

import pytest

from async_partners import CustomerBackend

FACTORY = os.environ.get("WORKFORCE_E2E_FACTORY")
pytestmark = pytest.mark.skipif(
    not FACTORY,
    reason=(
        "Foundation composition/worker and Registry/Builder/Lifecycle/"
        "Orchestration implementations missing"
    ),
)


def factory():
    module, name = FACTORY.split(":", 1)
    return getattr(importlib.import_module(module), name)


def test_case_79_read_only_auto_close_without_tracking():
    async def scenario():
        async with factory()() as system:
            customer = CustomerBackend(
                system.client,
                system.customer_headers,
                "resident-123",
                system.management_ref,
            )
            response = await customer.start(
                "READ-ONLY",
                "READ-CHAT",
                "Cho tôi biết tiện ích khách sạn giả lập",
            )
            assert response.status_code == 200
            assert (
                response.json()["workflow_state"] == "closed"
                and response.json()["next_action"] == "none"
            )
            assert (
                await system.count_operations(response.json()["workflow_id"])
                == 0
            )
            assert (
                await system.count_tracking_jobs(
                    response.json()["workflow_id"]
                )
                == 0
            )

    asyncio.run(scenario())


def test_cases_80_84_85_86_ticket_context_and_mismatch():
    async def scenario():
        async with factory()() as system:
            customer = CustomerBackend(
                system.client,
                system.customer_headers,
                "resident-123",
                system.management_ref,
            )
            a = (
                await customer.start(
                    "TICKET-A",
                    "CHAT-A",
                    "Lập kế hoạch hotel, ngân sách 10000000 VND",
                    "A1",
                )
            ).json()
            b = (
                await customer.start(
                    "TICKET-B",
                    "CHAT-B",
                    "Lập kế hoạch hotel, ngân sách 20000000 VND",
                    "B1",
                )
            ).json()
            assert (
                a["workflow_id"] != b["workflow_id"]
                and a["conversation_id"] != b["conversation_id"]
            )
            assert "group_id" not in a and "group_id" not in b
            before_a, before_b = (
                await system.runtime_state(a["workflow_id"]),
                await system.runtime_state(b["workflow_id"]),
            )
            assert before_a["group_id"] != before_b["group_id"]
            assert set(before_a["session_ids"]).isdisjoint(
                before_b["session_ids"]
            )
            a2 = (
                await customer.reply("TICKET-A", "Ưu tiên view biển", "A2")
            ).json()
            b2 = (
                await customer.reply(
                    "TICKET-B", "Ưu tiên phòng gia đình", "B2"
                )
            ).json()
            assert (
                a2["workflow_id"] == a["workflow_id"]
                and b2["workflow_id"] == b["workflow_id"]
            )
            assert (await system.runtime_state(a["workflow_id"]))[
                "group_id"
            ] == before_a["group_id"]
            assert (await system.runtime_state(b["workflow_id"]))[
                "group_id"
            ] == before_b["group_id"]
            calls_before = await system.model_tool_counts()
            wrong = await system.client.post(
                "/workforce/v1/partner/requests",
                headers=system.customer_headers,
                json={
                    "schema_version": "1",
                    "command_type": "workflow_reply",
                    "external_request_id": "BAD-TUPLE",
                    "external_management_ref": system.management_ref,
                    "external_user_id": "resident-123",
                    "external_ticket_id": "TICKET-B",
                    "external_conversation_id": "CHAT-B",
                    "workflow_id": a["workflow_id"],
                    "message": {"type": "text", "text": "must never dispatch"},
                },
            )
            assert (
                wrong.status_code == 409
                and wrong.json()["error"]["code"]
                == "WORKFLOW_BINDING_MISMATCH"
            )
            assert await system.model_tool_counts() == calls_before

    asyncio.run(scenario())


def test_case_87_parallel_start_has_one_binding_and_group():
    async def scenario():
        async with factory()() as system:
            one = CustomerBackend(
                system.client,
                system.customer_headers,
                "resident-123",
                system.management_ref,
            )
            two = CustomerBackend(
                system.client,
                system.customer_headers,
                "resident-123",
                system.management_ref,
            )
            responses = await asyncio.gather(
                one.start("TICKET-A", "CHAT-A", "Lập kế hoạch", "same-id"),
                two.start("TICKET-A", "CHAT-A", "Lập kế hoạch", "same-id"),
            )
            assert (
                responses[0].json()["workflow_id"]
                == responses[1].json()["workflow_id"]
            )
            assert await system.count_bindings("resident-123", "TICKET-A") == 1
            response = await system.client.post(
                "/workforce/v1/partner/requests",
                headers=system.customer_headers,
                json={
                    **one._base("TICKET-A", "CHAT-A", "new-id"),
                    "command_type": "start_workflow",
                    "message": {"type": "text", "text": "Lập kế hoạch"},
                },
            )
            assert (
                response.status_code == 409
                and response.json()["error"]["code"] == "TICKET_ALREADY_BOUND"
            )

    asyncio.run(scenario())
