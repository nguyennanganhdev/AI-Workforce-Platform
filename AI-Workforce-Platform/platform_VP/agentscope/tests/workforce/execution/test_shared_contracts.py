"""Cross-module DTO interoperability and pre-Phase-A replay compatibility."""

import asyncio

import pytest

from agentscope.app.workforce.contracts import (
    ActorContext,
    ErrorResponse,
    PartnerApprovalDecision,
    PartnerAudience,
    ProviderEventEnvelope,
    ProviderEventReceipt,
    Scope,
    ToolDescriptor,
)
from agentscope.app.workforce.execution import (
    ExecutionError,
    PartnerApprovalService,
    calculator_catalog_descriptor,
)
from agentscope.app.workforce.execution._router import check_decision
from agentscope.app.workforce.execution._utils import digest
from execution_fakes import (
    PARTNER,
    AUDIENCE,
    PROVIDER,
    SCOPE_A,
    SCOPE_B,
    approved_call,
    call_fixture,
    event_fixture,
    harness,
)


def test_shared_scope_reaches_gateway_and_preserves_owner_isolation():
    async def scenario():
        async with harness() as env:
            call = await approved_call(env)
            result = await env.gateway.execute(Scope(**SCOPE_A), call)
            assert result["status"] == "succeeded"
            with pytest.raises(ExecutionError, match="RESOURCE_NOT_FOUND"):
                await env.gateway.get_call(Scope(**SCOPE_B), call["call_id"])
            with pytest.raises(ExecutionError, match="SCOPE_REQUIRED"):
                await env.gateway.get_call(
                    {**SCOPE_A, "manager_account_id": 123}, call["call_id"]
                )
            assert env.provider.calls == 1

    asyncio.run(scenario())


def test_public_error_is_canonical_and_has_stable_nonempty_request_id():
    error = ExecutionError("PROVIDER_EXECUTION_UNKNOWN", 503, retryable=True)
    first = ErrorResponse.model_validate(error.public())
    second = ErrorResponse.model_validate(error.public())
    assert first.error.request_id == second.error.request_id
    assert first.error.request_id and first.error.retryable
    assert first.error.details == {}


def test_calculator_can_be_handed_to_canonical_registry_without_extra_fields():
    descriptor = calculator_catalog_descriptor(Scope(**SCOPE_A))
    assert isinstance(descriptor, ToolDescriptor)
    assert descriptor.effect == "read"
    assert descriptor.tool_version_id == "builtin.money.v1"
    assert "scope" not in descriptor.model_dump()
    assert "effect_reviewed" not in descriptor.model_dump()


def test_provider_dto_and_nullable_wire_share_receipt_and_original_timestamp():
    async def scenario():
        async with harness(tracking=True) as env:
            wire = event_fixture(correlation="unbound")
            first = ProviderEventReceipt.model_validate(
                await env.ingress.accept(PROVIDER, wire)
            )
            env.clock.advance(30)
            dto = ProviderEventEnvelope.model_validate(wire)
            replay = ProviderEventReceipt.model_validate(
                await env.ingress.accept(PROVIDER, dto)
            )
            assert replay.receipt_id == first.receipt_id
            assert replay.received_at == first.received_at
            assert replay.duplicate
            assert (
                await env.processor.process(first.receipt_id) == "quarantined"
            )
            public = await env.ingress.read_receipt(PROVIDER, first.receipt_id)
            assert ProviderEventReceipt.model_validate(public)
            assert "error" not in public and "scope" not in public

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "change",
    [
        {"external_event_id": "x" * 201},
        {"external_job_id": None, "client_reference": None},
        {"provider_version": True},
        {"provider_version": 1.5},
        {"occurred_at": "2026-10-09T02:30:00"},
        {"occurred_at": 1791513000},
        {"scope": SCOPE_A},
    ],
)
def test_shared_provider_boundary_rejects_invalid_data_before_inbox(change):
    async def scenario():
        async with harness(tracking=True) as env:
            with pytest.raises(ExecutionError, match="PROVIDER_EVENT_INVALID"):
                await env.ingress.accept(
                    PROVIDER,
                    {**event_fixture(correlation="unbound"), **change},
                )
            async with env.repo.transaction() as uow:
                assert await env.repo.find("inbox", {}, uow) == []

    asyncio.run(scenario())


def test_old_inbox_replay_preserves_audit_and_rejects_conflict():
    async def scenario():
        async with harness(tracking=True) as env:
            old = event_fixture(correlation="unbound")
            old["occurred_at"] = "2026-10-09T02:30:00+00:00"
            receipt = await env.ingress.accept(PROVIDER, old)
            async with env.repo.transaction() as uow:
                row = await env.repo.get("inbox", receipt["receipt_id"], uow)
                row.update(envelope=old, payload_hash=digest(old))
                await env.repo.save("inbox", row, row["revision"], uow)
            replay = await env.ingress.accept(
                PROVIDER, ProviderEventEnvelope.model_validate(old)
            )
            assert replay["duplicate"]
            with pytest.raises(ExecutionError, match="EVENT_ID_CONFLICT"):
                await env.ingress.accept(
                    PROVIDER, {**old, "data": {"status": "completed"}}
                )
            async with env.repo.transaction() as uow:
                row = await env.repo.get("inbox", receipt["receipt_id"], uow)
                assert row["payload_hash"] == digest(old)

    asyncio.run(scenario())


def test_stale_fact_has_rejected_receipt_and_no_new_transition():
    async def scenario():
        async with harness(tracking=True) as env:
            call = await approved_call(env)
            await env.gateway.execute(SCOPE_A, call)
            op = (
                await env.operations.get_for_workflow(SCOPE_A, "workflow-A")
            )[0]
            latest = await env.ingress.accept(
                PROVIDER,
                event_fixture(
                    "LATEST", job_id=op["external_job_id"], version=2
                ),
            )
            await env.processor.process(latest["receipt_id"])
            op = await env.repo.read("operations", SCOPE_A, op["id"])
            receipt = await env.ingress.accept(
                PROVIDER,
                event_fixture(job_id=op["external_job_id"], version=0),
            )
            assert (
                await env.processor.process(receipt["receipt_id"]) == "ignored"
            )
            public = ProviderEventReceipt.model_validate(
                await env.ingress.read_receipt(PROVIDER, receipt["receipt_id"])
            )
            assert public.ingestion_status == "rejected"
            unchanged = await env.repo.read("operations", SCOPE_A, op["id"])
            assert unchanged["revision"] == op["revision"]

    asyncio.run(scenario())


def test_partner_dto_optional_fields_do_not_require_private_routing_fields():
    dto = PartnerApprovalDecision(
        schema_version="1",
        external_request_id="request-1",
        external_user_id="resident-123",
        external_conversation_id="CHAT-A",
        workflow_id="workflow-A",
        decision="approve",
        expected_revision=1,
        arguments_hash="hash",
    )
    check_decision(dto.model_dump(mode="json"), partner=True)
    with pytest.raises(ExecutionError, match="APPROVAL_DECISION_INVALID"):
        check_decision(
            {**dto.model_dump(mode="json"), "scope": SCOPE_A}, partner=True
        )


def test_provider_purpose_actor_cannot_use_customer_approval_path():
    async def scenario():
        actor = ActorContext.model_validate(
            {**PARTNER, "credential_purpose": "provider_events"}
        )
        async with harness() as env:
            service = PartnerApprovalService(env.approvals, commands=None)
            with pytest.raises(ExecutionError, match="CUSTOMER_AUTH_REQUIRED"):
                await service.decide(actor, "unread-approval", {})
            assert env.provider.calls == 0

    asyncio.run(scenario())


def test_partner_audience_dto_preserves_consent_and_resident_isolation():
    async def scenario():
        async with harness() as env:
            context = env.runtime.contexts["run-A"]
            context["allowed_decider"] = {
                "kind": "partner",
                "partner_client_id": "customer",
                "external_user_id": "resident-123",
            }
            proposed = await env.gateway.execute(SCOPE_A, call_fixture())
            approval = await env.repo.read(
                "approvals", SCOPE_A, proposed["approval_id"]
            )
            dto = PartnerAudience(**AUDIENCE)
            # A canonical runtime dump includes residence_id=null, while old
            # stored consent omitted it. This must preserve the same binding.
            context["partner_audience"] = dto.model_dump(mode="json")
            for audience, denied in (
                (dto.model_copy(update={"external_user_id": "other"}), True),
                (dto, False),
            ):

                async def decide():
                    async with env.repo.transaction() as uow:
                        return await env.approvals.decide_in_uow(
                            Scope(**SCOPE_A),
                            approval["id"],
                            "approve",
                            ActorContext.model_validate(PARTNER),
                            audience,
                            approval["arguments_hash"],
                            approval["quote_hash"],
                            uow,
                        )

                if denied:
                    with pytest.raises(
                        ExecutionError, match="APPROVAL_AUDIENCE_FORBIDDEN"
                    ):
                        await decide()
                else:
                    assert (await decide())["status"] == "approved"
            result = await env.gateway.execute(
                Scope(**SCOPE_A),
                {**call_fixture(), "approval_id": approval["id"]},
            )
            assert result["status"] == "succeeded" and env.provider.calls == 1

    asyncio.run(scenario())
