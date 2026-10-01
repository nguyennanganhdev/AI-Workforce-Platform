import asyncio
import copy
import json
import unittest

from adapters.backend.approval_client import ApprovalClient
from adapters.backend.client import HttpResponse
from adapters.backend.errors import AdapterError
from adapters.backend.messages import validate_request
from adapters.reception.reception_gateway import ReceptionGateway
from backend.support import CONTEXT, client, request
from reception.support import Authentication, gateway_parts, input_message, output_message


class ReceptionV2Tests(unittest.IsolatedAsyncioTestCase):
    async def test_all_inputs_verify_full_snapshot_and_keep_source_and_null_facts(self):
        for kind in ("ticket_submitted", "information_provided", "plan_approved",
                     "plan_rejected", "plan_change_requested", "cancel_requested"):
            with self.subTest(kind=kind):
                gateway, backend, validator = gateway_parts()
                backend.pending = "plan_approval_requested"
                raw = input_message(kind)
                verified = await gateway.verify(raw, "verified-source")
                url, headers, sent, _ = backend.calls[0]
                self.assertTrue(url.endswith("reception.verify"))
                self.assertEqual(sent, raw)
                self.assertIsNone(sent["facts"][0]["value"])
                self.assertEqual(verified.context.model_dump(exclude_none=True), CONTEXT)
                self.assertEqual(verified.supervisor_run_id, "supervisor-run-1")
                self.assertEqual(verified.message.message_type, kind)
                self.assertEqual(headers["Idempotency-Key"], raw["message_id"])
                self.assertEqual(headers["X-Correlation-Id"], raw["correlation_id"])
                self.assertNotIn("X-Request-Id", headers)
                self.assertEqual([k for k, _ in validator.seen],
                                 ["reception_input", "reception_response", "reception_verified"])

    async def test_all_outputs_preserve_wire_and_use_backend_only(self):
        for kind in ("accepted", "in_progress", "information_requested", "plan_approval_requested",
                     "completed", "failed", "cancelled"):
            with self.subTest(kind=kind):
                gateway, backend, validator = gateway_parts()
                backend.cancelled = True
                raw = output_message(kind)
                ack = await gateway.send(raw, CONTEXT)
                self.assertEqual(ack, {"message_id": raw["message_id"], "status": "accepted"})
                self.assertEqual(backend.calls[0][2], {"message": raw, "context": CONTEXT})
                self.assertEqual(backend.delivered, [raw])
                self.assertNotIn("status", backend.delivered[0])
                self.assertEqual([k for k, _ in validator.seen],
                                 ["reception_output", "reception_delivery", "reception_response"])

    async def test_typed_models_match_supervisor_port_and_preserve_null_fact(self):
        from groupchat.models import Context
        from groupchat.reception import ReceptionMessage, SupervisorMessage

        gateway, backend, _ = gateway_parts()
        message = ReceptionMessage.model_validate(input_message())
        verified = await gateway.verify(message, "verified-source")
        self.assertEqual(verified.message, message)
        self.assertIn("value", backend.calls[0][2]["facts"][0])
        result = SupervisorMessage.model_validate(output_message("completed"))
        await gateway.send(result, Context.model_validate(CONTEXT))
        self.assertEqual(backend.delivered[-1], output_message("completed"))

    async def test_v1_and_removed_fields_are_rejected_before_network(self):
        gateway, backend, _ = gateway_parts()
        for old in (request(), {**input_message(), "schema_version": "1"},
                    {**input_message(), "message_type": "completion.responded"}):
            with self.subTest(old=old), self.assertRaises(AdapterError):
                await gateway.verify(old, "verified-source")
        for field in ("status", "customer_message", "resident_decision", "requires_resident_approval",
                      "additional_information", "cancel_request", "requested_information", "mentioned_agent_id"):
            with self.subTest(field=field), self.assertRaises(AdapterError):
                await gateway.verify({**input_message(), field: "old"}, "verified-source")
            with self.subTest(field=field), self.assertRaises(AdapterError):
                await gateway.send({**output_message(), field: "old"}, CONTEXT)
        self.assertFalse(backend.calls)
        self.assertFalse(hasattr(gateway, "receive_completion_response"))

    async def test_required_source_snapshot_enum_and_time_are_checked(self):
        gateway, backend, _ = gateway_parts()
        variants = []
        for key in ("resident", "location", "request", "facts", "file_ids", "domain_id", "created_at"):
            raw = input_message("information_provided")
            del raw[key]
            variants.append(raw)
        for changes in (dict(source_message_id=None), dict(source_message_id=""),
                        dict(message_type="approve"), dict(ticket_generation=True),
                        dict(sent_at="2026-10-01T10:00:00"), dict(created_at="2026-10-01")):
            variants.append(input_message("information_provided", **changes))
        raw = input_message()
        raw["facts"][0]["value"] = float("nan")
        variants.append(raw)
        for raw in variants:
            with self.subTest(raw=raw), self.assertRaises(AdapterError):
                await gateway.verify(raw, "verified-source")
        self.assertFalse(backend.calls)

    async def test_no_model_coercion_or_decision_inference(self):
        gateway, backend, _ = gateway_parts()
        raw = input_message("information_provided", message="Tôi đồng ý @AgentB")
        result = await gateway.verify(raw, "verified-source")
        self.assertEqual(result.message.message_type, "information_provided")
        self.assertFalse(backend.decisions)
        raw["request"]["is_emergency"] = "false"
        with self.assertRaises(AdapterError):
            await gateway.verify(raw, "verified-source")

    async def test_authentication_is_request_scoped_and_cannot_be_self_asserted(self):
        gateway, backend, _ = gateway_parts()
        with self.assertRaisesRegex(AdapterError, "reception_not_authorized"):
            await gateway.verify(input_message(), {"resident_id": "resident-1"})
        with self.assertRaisesRegex(AdapterError, "reception_authentication_required"):
            await ReceptionGateway(client(backend)).verify(input_message(), "verified-source")
        self.assertFalse(backend.calls)

    async def test_delegated_headers_cannot_override_service_or_identity(self):
        for headers in ({"Authorization": "other"}, {"X-Message-Id": "other"},
                        {"X-Source": "secret\r\nInjected: bad"}, {}):
            class BadAuthentication(Authentication):
                async def headers(self, authentication):
                    return headers

            _, backend, _ = gateway_parts()
            gateway = ReceptionGateway(client(backend), authentication=BadAuthentication())
            with self.subTest(headers=headers), self.assertRaises(AdapterError):
                await gateway.verify(input_message(), "verified-source")
            self.assertFalse(backend.calls)

    async def test_backend_rejects_stale_generation_version_and_wrong_step(self):
        gateway, backend, _ = gateway_parts()
        backend.current_version = "12"
        with self.assertRaisesRegex(AdapterError, "stale_version"):
            await gateway.verify(input_message("plan_approved", version="11"), "verified-source")
        backend.pending = "information_requested"
        with self.assertRaisesRegex(AdapterError, "conflict"):
            await gateway.verify(input_message("plan_approved", version="12"), "verified-source")
        with self.assertRaisesRegex(AdapterError, "forbidden"):
            await gateway.verify(input_message(ticket_generation=0), "verified-source")
        self.assertFalse(backend.decisions)

    async def test_backend_cannot_upgrade_or_rewrite_verified_snapshot(self):
        for field, value in (("ticket_version", "99"), ("message", "rewritten"),
                             ("ticket_generation", 99), ("correlation_id", "new")):
            gateway, backend, _ = gateway_parts()
            raw = input_message("information_provided")
            changed = {**raw, field: value}
            backend.response = backend.response_json(dict(message_id=raw["message_id"], status="accepted",
                data=dict(message=changed, context=CONTEXT, supervisor_run_id="supervisor-run-1")))
            with self.subTest(field=field), self.assertRaisesRegex(AdapterError, "invalid_backend_response"):
                await gateway.verify(raw, "verified-source")

    async def test_verified_routing_must_match_input_scope(self):
        for key, value in (("tenant_id", "other"), ("ticket_id", "other"), ("domain_id", "other"),
                           ("workspace_id", "other"), ("ticket_generation", 2)):
            gateway, backend, _ = gateway_parts()
            raw = input_message()
            backend.response = backend.response_json(dict(message_id=raw["message_id"], status="accepted",
                data=dict(message=raw, context={**CONTEXT, key: value}, supervisor_run_id="run")))
            with self.subTest(key=key), self.assertRaisesRegex(AdapterError, "invalid_backend_response"):
                await gateway.verify(raw, "verified-source")

    async def test_output_scope_mismatch_fails_before_network(self):
        gateway, backend, _ = gateway_parts()
        for key, value in (("tenant_id", "other"), ("ticket_id", "other"),
                           ("workspace_id", "other"), ("ticket_generation", 2)):
            with self.subTest(key=key), self.assertRaisesRegex(AdapterError, "scope_mismatch"):
                await gateway.send(output_message(), {**CONTEXT, key: value})
        self.assertFalse(backend.calls)

    async def test_message_and_semantic_decision_dedup_remain_backend_owned(self):
        gateway, backend, _ = gateway_parts()
        backend.pending = "plan_approval_requested"
        raw = input_message("plan_approved")
        await asyncio.gather(*(gateway.verify(raw, "verified-source") for _ in range(10)))
        await gateway.verify({**raw, "message_id": "new-id-same-decision"}, "verified-source")
        self.assertEqual(len(backend.decisions), 1)
        with self.assertRaisesRegex(AdapterError, "conflict"):
            await gateway.verify({**raw, "message": "changed"}, "verified-source")
        with self.assertRaisesRegex(AdapterError, "conflict"):
            await gateway.verify({**raw, "message_id": "different-decision", "message_type": "plan_rejected"},
                                 "verified-source")

    async def test_retry_keeps_wire_id_and_backend_delivery_exactly_once(self):
        gateway, backend, _ = gateway_parts()
        raw = output_message("plan_approval_requested")
        await gateway.send(raw, CONTEXT)
        replacement = ReceptionGateway(client(backend), authentication=Authentication())
        await replacement.send(raw, CONTEXT)
        self.assertEqual(backend.calls[0], backend.calls[1])
        self.assertEqual(backend.delivered, [raw])

    async def test_only_one_pending_question_or_plan(self):
        gateway, backend, _ = gateway_parts()
        await gateway.send(output_message("information_requested"), CONTEXT)
        with self.assertRaisesRegex(AdapterError, "conflict"):
            await gateway.send(output_message("plan_approval_requested", identity="second"), CONTEXT)
        self.assertEqual(len(backend.delivered), 1)

    async def test_plan_cancellation_completion_require_backend_authorization(self):
        for kind, policy in (("plan_approval_requested", "management_approved"),
                             ("completed", "qc_approved"), ("cancelled", "cancelled")):
            gateway, backend, _ = gateway_parts()
            setattr(backend, policy, False)
            with self.subTest(kind=kind), self.assertRaisesRegex(AdapterError, "forbidden"):
                await gateway.send(output_message(kind), CONTEXT)
            self.assertFalse(backend.delivered)

    async def test_completed_requires_work_completed_result(self):
        gateway, backend, _ = gateway_parts()
        for result in (None, {**output_message("completed")["result"], "outcome": "needs_human_review"}):
            with self.subTest(result=result), self.assertRaises(AdapterError):
                await gateway.send(output_message("completed", result=result), CONTEXT)
        self.assertFalse(backend.calls)

    async def test_failed_does_not_replace_resident_message_with_technical_error(self):
        gateway, backend, _ = gateway_parts()
        raw = output_message("failed", message="Cần nhân viên hỗ trợ.",
            error=dict(code="PROVIDER_FAILED", retryable=False, message="Private technical detail"))
        await gateway.send(raw, CONTEXT)
        self.assertEqual(backend.delivered[0]["message"], "Cần nhân viên hỗ trợ.")
        self.assertEqual(backend.delivered[0]["error"], raw["error"])

    async def test_backend_completion_handoff_can_start_new_generation(self):
        gateway, backend, _ = gateway_parts()
        await gateway.send(output_message("completed"), CONTEXT)
        backend.context["ticket_generation"] = 2
        verified = await gateway.verify(input_message(identity="reopened", ticket_generation=2), "verified-source")
        self.assertEqual(verified.context.ticket_generation, 2)
        self.assertEqual(verified.message.message_type, "ticket_submitted")
        self.assertFalse(hasattr(gateway, "receive_completion_response"))

    async def test_backend_errors_and_timeout_are_sanitized_without_implicit_retry(self):
        gateway, backend, _ = gateway_parts()
        backend.failure = TimeoutError("secret")
        with self.assertRaises(AdapterError) as caught:
            await gateway.send(output_message(), CONTEXT)
        self.assertTrue(caught.exception.outcome_unknown)
        self.assertEqual(caught.exception.code, "timeout")
        self.assertEqual(len(backend.calls), 1)
        self.assertNotIn("secret", str(caught.exception))

    async def test_correlated_receipt_and_canonical_validation_fail_closed(self):
        for reply in (b"[]", b"not json", json.dumps(dict(message_id="wrong", status="accepted", data={})).encode(),
                      json.dumps(dict(message_id="output-1", status="closed", data={})).encode()):
            gateway, backend, _ = gateway_parts()
            backend.response = HttpResponse(200, reply)
            with self.subTest(reply=reply), self.assertRaisesRegex(AdapterError, "invalid_backend_response"):
                await gateway.send(output_message(), CONTEXT)
        for kind in ("reception_input", "reception_output", "reception_delivery"):
            gateway, backend, validator = gateway_parts()
            validator.reject = kind
            with self.subTest(kind=kind), self.assertRaises(AdapterError):
                if kind == "reception_input":
                    await gateway.verify(input_message(), "verified-source")
                else:
                    await gateway.send(output_message(), CONTEXT)
            self.assertFalse(backend.calls)

    async def test_wrappers_select_enum_and_management_uses_separate_client(self):
        gateway, backend, _ = gateway_parts()
        verified = await gateway.receive_ticket(input_message(), authentication="verified-source")
        self.assertEqual(verified.message.message_type, "ticket_submitted")
        with self.assertRaises(AdapterError):
            await gateway.receive_plan_response(input_message("information_provided"), authentication="verified-source")
        with self.assertRaises(AdapterError):
            await gateway.send_plan(output_message("information_requested"), context=CONTEXT)
        wire = request("approval.requested")
        validate_request(wire)
        await ApprovalClient(client()).request_plan(wire)
        wire["payload"]["stage"] = "resident_plan"
        with self.assertRaises(AdapterError):
            await ApprovalClient(client()).request_plan(wire)
        with self.assertRaisesRegex(AdapterError, "reception_protocol_not_supported"):
            await ApprovalClient(client()).request_completion({})

    async def test_caller_or_validator_cannot_mutate_saved_wire(self):
        gateway, backend, _ = gateway_parts()
        raw = input_message()
        original = copy.deepcopy(raw)

        class MutatingAuthentication(Authentication):
            async def headers(self, authentication):
                raw["ticket_version"] = "99"
                return await super().headers(authentication)

        gateway = ReceptionGateway(client(backend), authentication=MutatingAuthentication())
        verified = await gateway.verify(raw, "verified-source")
        self.assertEqual(backend.calls[0][2], original)
        self.assertEqual(verified.message.ticket_version, "1")

    async def test_mention_uses_trusted_command_sidecar_only(self):
        gateway, backend, _ = gateway_parts()
        raw = input_message("information_provided", message="@AgentB kiểm tra giúp")
        command = dict(contract_version="1", request_id="backend-command", trace_id="backend-trace",
            idempotency_key="backend-key", context=CONTEXT, payload=dict(version=2, operation="mention_agent",
                room_id="backend-room", expected_room_version=3, mentioned_agent_id="backend-agent-id",
                instruction=raw["message"]))
        backend.room_command = command
        resolved = await gateway.resolve(raw, "verified-source")
        self.assertEqual(resolved.room_command.request_id, "backend-command")
        self.assertEqual(resolved.room_command.payload.mentioned_agent_id, "backend-agent-id")
        self.assertNotIn("mentioned_agent_id", backend.calls[0][2])
        with self.assertRaisesRegex(AdapterError, "mention_requires_groupchat"):
            await gateway.verify(raw, "verified-source")

    async def test_invalid_mention_context_or_operation_is_never_forwarded(self):
        gateway, backend, _ = gateway_parts()
        raw = input_message("information_provided")
        backend.room_command = dict(contract_version="1", request_id="command", trace_id="trace",
            idempotency_key="key", context={**CONTEXT, "ticket_id": "other"},
            payload=dict(version=2, operation="mention_agent", room_id="room", expected_room_version=1,
                         mentioned_agent_id="agent", instruction=raw["message"]))
        with self.assertRaisesRegex(AdapterError, "invalid_backend_response"):
            await gateway.resolve(raw, "verified-source")

    async def test_two_tenants_same_message_id_never_share_routing_or_delivery(self):
        from reception.support import V2Transport

        first, second = V2Transport(), V2Transport()
        second.context.update(tenant_id="tenant-b", ticket_id="ticket-2", workspace_id="workspace-2",
                              domain_id="domain-2", binding_id="binding-2", run_id="run-2")

        class TwoRooms:
            async def post(self, url, *, headers, body, timeout):
                wire = json.loads(body)
                message = wire if "message_type" in wire else wire["message"]
                target = first if message["tenant_id"] == CONTEXT["tenant_id"] else second
                return await target.post(url, headers=headers, body=body, timeout=timeout)

        gateway = ReceptionGateway(client(TwoRooms()), authentication=Authentication())
        a = input_message()
        b = {**a, **{key: second.context[key] for key in
             ("tenant_id", "domain_id", "workspace_id", "ticket_id", "ticket_generation")}}
        results = await asyncio.gather(gateway.verify(a, "verified-source"), gateway.verify(b, "verified-source"))
        self.assertEqual(results[0].context.binding_id, "binding-1")
        self.assertEqual(results[1].context.binding_id, "binding-2")
        out_a = output_message()
        out_b = {**out_a, **{key: second.context[key] for key in
                 ("tenant_id", "workspace_id", "ticket_id", "ticket_generation")}}
        await asyncio.gather(gateway.send(out_a, CONTEXT), gateway.send(out_b, second.context))
        self.assertEqual(first.delivered, [out_a])
        self.assertEqual(second.delivered, [out_b])

    async def test_bad_verified_receipt_and_validator_rejection_are_unknown(self):
        for data in ({}, dict(message=input_message(), context=CONTEXT, supervisor_run_id=""),
                     dict(message=input_message(), context=CONTEXT, supervisor_run_id="run", unexpected=True)):
            gateway, backend, _ = gateway_parts()
            backend.response = backend.response_json(dict(message_id="input-1", status="accepted", data=data))
            with self.assertRaises(AdapterError) as caught:
                await gateway.verify(input_message(), "verified-source")
            self.assertEqual(caught.exception.code, "invalid_backend_response")
            self.assertTrue(caught.exception.outcome_unknown)
        gateway, _, validator = gateway_parts()
        validator.reject = "reception_verified"
        with self.assertRaisesRegex(AdapterError, "invalid_backend_response"):
            await gateway.verify(input_message(), "verified-source")

    async def test_authentication_deadline_and_unconfigured_v2_operation(self):
        class SlowAuthentication:
            async def headers(self, authentication):
                await asyncio.sleep(1)

        _, backend, _ = gateway_parts()
        gateway = ReceptionGateway(client(backend), authentication=SlowAuthentication(), timeout=0.01)
        with self.assertRaisesRegex(AdapterError, "verification_unavailable"):
            await gateway.verify(input_message(), "verified-source")
        self.assertFalse(backend.calls)
        from adapters.backend.client import BackendClient
        from backend.support import Headers, Validator

        gateway = ReceptionGateway(BackendClient(base_url="https://backend.test", routes={},
            transport=backend, headers=Headers(), validator=Validator()), authentication=Authentication())
        with self.assertRaisesRegex(AdapterError, "operation_not_configured"):
            await gateway.verify(input_message(), "verified-source")
        self.assertFalse(backend.calls)
