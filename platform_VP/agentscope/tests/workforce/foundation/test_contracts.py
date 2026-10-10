# -*- coding: utf-8 -*-
"""Phase-A contract tests owned by Nguyễn Chí Hoàng."""

from datetime import UTC, datetime
import json
from pathlib import Path
import unittest

from pydantic import ValidationError

from agentscope.app.workforce.contracts import (
    ActorContext,
    ActorKind,
    CredentialPurpose,
    InboundReceipt,
    ManagerRole,
    NextAction,
    PartnerCommandType,
    PartnerRequestEnvelope,
    ProviderEventEnvelope,
    RequestStatus,
    Scope,
    TextMessageInput,
    TicketConversationBinding,
    WorkflowState,
    contract_schema_bundle,
)


NOW = datetime(2026, 10, 10, tzinfo=UTC)


def _scope() -> Scope:
    return Scope(
        tenant_id="tenant-1",
        domain_id="property-management",
        area_id="ha-long",
        manager_account_id="manager-1",
    )


def _request(**overrides: object) -> PartnerRequestEnvelope:
    values: dict[str, object] = {
        "schema_version": "1",
        "command_type": PartnerCommandType.START_WORKFLOW,
        "external_request_id": "request-a-1",
        "external_management_ref": "BQL-HL-01",
        "external_user_id": "resident-123",
        "external_ticket_id": "ticket-a",
        "external_conversation_id": "chat-a",
        "message": TextMessageInput(type="text", text="Tôi cần hỗ trợ."),
    }
    values.update(overrides)
    return PartnerRequestEnvelope.model_validate(values)


class WorkforceContractTests(unittest.TestCase):
    def test_only_area_manager_role_is_available(self) -> None:
        self.assertEqual(list(ManagerRole), [ManagerRole.AREA_MANAGER])
        actor = ActorContext(
            kind=ActorKind.MANAGER,
            actor_id="manager-1",
            role=ManagerRole.AREA_MANAGER,
            authentication_source="manager_jwt",
        )
        self.assertEqual(actor.role, ManagerRole.AREA_MANAGER)

    def test_machine_credential_purposes_are_separate(self) -> None:
        customer = ActorContext(
            kind=ActorKind.PARTNER,
            actor_id="partner-client-1",
            partner_client_id="partner-client-1",
            credential_id="credential-customer",
            credential_purpose=CredentialPurpose.CUSTOMER_API,
            authentication_source="api_key",
        )
        provider = customer.model_copy(
            update={
                "credential_id": "credential-provider",
                "credential_purpose": CredentialPurpose.PROVIDER_EVENTS,
            },
        )
        self.assertNotEqual(
            customer.credential_purpose,
            provider.credential_purpose,
        )

    def test_partner_cannot_inject_internal_group_or_scope(self) -> None:
        with self.assertRaises(ValidationError) as raised:
            _request(group_id="group-forged", area_id="area-forged")

        messages = str(raised.exception)
        self.assertIn("group_id", messages)
        self.assertIn("area_id", messages)

    def test_start_and_reply_have_unambiguous_target_rules(self) -> None:
        with self.assertRaisesRegex(
            ValidationError,
            "must not contain workflow_id",
        ):
            _request(workflow_id="workflow-a")

        with self.assertRaisesRegex(ValidationError, "requires workflow_id"):
            _request(command_type=PartnerCommandType.WORKFLOW_REPLY)

        reply = _request(
            command_type=PartnerCommandType.WORKFLOW_REPLY,
            workflow_id="workflow-a",
            external_request_id="request-a-2",
        )
        self.assertEqual(reply.workflow_id, "workflow-a")

    def test_same_user_two_tickets_have_independent_bindings(self) -> None:
        common = {
            "scope": _scope(),
            "partner_client_id": "partner-client-1",
            "external_user_id": "resident-123",
            "route_id": "route-1",
            "route_revision": 2,
            "created_at": NOW,
            "updated_at": NOW,
        }
        binding_a = TicketConversationBinding(
            **common,
            external_ticket_id="ticket-a",
            external_conversation_id="chat-a",
            workflow_id="workflow-a",
            conversation_id="conversation-a",
            group_id="group-a",
        )
        binding_b = TicketConversationBinding(
            **common,
            external_ticket_id="ticket-b",
            external_conversation_id="chat-b",
            workflow_id="workflow-b",
            conversation_id="conversation-b",
            group_id="group-b",
        )

        self.assertEqual(
            binding_a.external_user_id,
            binding_b.external_user_id,
        )
        self.assertNotEqual(
            binding_a.external_ticket_id,
            binding_b.external_ticket_id,
        )
        self.assertNotEqual(
            binding_a.conversation_id,
            binding_b.conversation_id,
        )
        self.assertNotEqual(binding_a.workflow_id, binding_b.workflow_id)
        self.assertNotEqual(binding_a.group_id, binding_b.group_id)

    def test_receipt_distinguishes_http_turn_from_open_workflow(self) -> None:
        pending = InboundReceipt(
            request_id="request-a-1",
            request_status=RequestStatus.RUNNING,
            external_ticket_id="ticket-a",
            conversation_id="conversation-a",
            workflow_id="workflow-a",
            workflow_state=WorkflowState.ACTIVE,
            next_action=NextAction.WATCH_REQUEST,
            workflow_revision=1,
            accepted_at=NOW,
            status_url="/workforce/v1/partner/requests/request-a-1",
            conversation_url=(
                "/workforce/v1/partner/conversations/conversation-a"
            ),
            event_stream_url=(
                "/workforce/v1/partner/conversations/conversation-a/events"
            ),
        )
        self.assertEqual(pending.request_status, RequestStatus.RUNNING)
        self.assertEqual(pending.workflow_state, WorkflowState.ACTIVE)

        with self.assertRaisesRegex(ValidationError, "pending request"):
            InboundReceipt.model_validate(
                pending.model_dump()
                | {"next_action": NextAction.SUBMIT_REPLY},
            )

    def test_provider_event_requires_a_persisted_correlation_key(self) -> None:
        with self.assertRaisesRegex(
            ValidationError,
            "external_job_id or client_reference is required",
        ):
            ProviderEventEnvelope(
                schema_version="1",
                external_event_id="provider-event-1",
                event_type="job.progressed",
                occurred_at=NOW,
            )

    def test_schema_bundle_contains_public_multiticket_fields(self) -> None:
        bundle = contract_schema_bundle()
        models = bundle["models"]
        self.assertIsInstance(models, dict)
        self.assertIn("PartnerRequestEnvelope", models)
        self.assertIn("TicketConversationBinding", models)
        self.assertIn("ProviderEventEnvelope", models)

        request_properties = models["PartnerRequestEnvelope"]["properties"]
        self.assertIn("external_ticket_id", request_properties)
        self.assertIn("external_conversation_id", request_properties)
        self.assertNotIn("group_id", request_properties)

    def test_two_ticket_sample_validates_without_internal_route_fields(
        self,
    ) -> None:
        repository_root = Path(__file__).resolve().parents[3]
        sample_path = (
            repository_root
            / "docs"
            / "workforce"
            / "contracts"
            / "samples"
            / "two-ticket-isolation.json"
        )
        sample = json.loads(sample_path.read_text(encoding="utf-8"))
        requests = [
            PartnerRequestEnvelope.model_validate(request)
            for request in sample["requests"]
        ]

        tickets = {request.external_ticket_id for request in requests}
        conversations = {
            request.external_conversation_id for request in requests
        }
        self.assertEqual(tickets, {"ticket-a", "ticket-b"})
        self.assertEqual(conversations, {"chat-a", "chat-b"})
        self.assertTrue(
            all("group_id" not in request for request in sample["requests"]),
        )


if __name__ == "__main__":
    unittest.main()
