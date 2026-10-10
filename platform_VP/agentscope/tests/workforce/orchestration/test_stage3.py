"""Local G3 lifecycle/checkpoint/projection tests, not API/worker E2E proof."""

import unittest
from copy import deepcopy

import _support
from wf_orchestration_under_test.workflows._policy import continuation, post_status
from wf_orchestration_under_test.workflows._checkpoint import apply_cause, assert_binding, close_checkpoint
from wf_orchestration_under_test.partner_events._projection import project_event, encode_sse, validate_cursor
from wf_orchestration_under_test._models import OrchestrationError


class Stage3Tests(unittest.TestCase):
    def setUp(self):
        self.checkpoint = {"state": "waiting_external_event", "revision": 1, "fence": 7,
                           "applied_causes": [], "pending_causes": [], "group_id": "group-A",
                           "session_ids": ["session-A"], "invoke_runtime": False}
        self.audience = {"partner_client_id": "client", "external_user_id": "customer",
                         "external_ticket_id": "ticket-A", "external_conversation_id": "chat-A"}
        self.binding = {"conversation_id": "conversation-A", "workflow_id": "workflow-A", "audience": self.audience}
        self.event = {"event_id": "event-A", "event_type": "assistant.message", "sequence": 10,
                      "conversation_id": "conversation-A", "workflow_id": "workflow-A", "created_at": "2026-10-10T00:00:00Z",
                      "payload": {"message_id": "message-A", "speaker": "Hotel", "content": "answer", "credential": "private"}}

    def test_G3_T01_response_only_and_http_fallback(self):
        self.assertEqual(continuation(policy={"effect": "read_only", "auto_close": True}, outcome={"terminal": True}), ("closed", "none"))
        self.assertEqual(post_status("running"), 202)
        self.assertEqual(post_status("completed"), 200)
        self.assertEqual(post_status("failed"), 200)

    def test_G3_T02_interactive_tracking_and_unknown(self):
        policy = {"effect": "side_effect", "tracking_protocol": "v1"}
        for outcome, expected in (({"needs_user": True}, ("awaiting_user", "submit_reply")),
                                  ({"needs_approval": True}, ("awaiting_approval", "submit_approval")),
                                  ({"terminal": True}, ("awaiting_confirmation", "confirm_close")),
                                  ({"operation_pending": True}, ("waiting_external_event", "watch_events")),
                                  ({"creation_status": "unknown"}, ("needs_attention", "resolve_attention"))):
            self.assertEqual(continuation(policy=policy, outcome=outcome), expected)
        with self.assertRaisesRegex(OrchestrationError, "TRACKING_CAPABILITY_MISSING"):
            continuation(policy={"effect": "side_effect"}, outcome={"operation_pending": True})

    def test_G3_T05_T06_binding_mismatch_and_cross_stream_blocked(self):
        audience_b = {**self.audience, "external_ticket_id": "ticket-B", "external_conversation_id": "chat-B"}
        with self.assertRaisesRegex(OrchestrationError, "WORKFLOW_BINDING_MISMATCH"):
            assert_binding(self.binding, audience_b, "workflow-A")
        with self.assertRaisesRegex(OrchestrationError, "AUDIENCE_FORBIDDEN"):
            project_event(self.event, self.binding, authorized_audience=audience_b)
        with self.assertRaisesRegex(OrchestrationError, "WORKFLOW_BINDING_MISMATCH"):
            project_event({**self.event, "workflow_id": "workflow-B"}, self.binding, authorized_audience=self.audience)

    def test_G3_T09_fencing_duplicate_and_group_pins_preserved(self):
        cause = {"cause_id": "cause", "kind": "operation_progress"}
        with self.assertRaisesRegex(OrchestrationError, "STALE_WORKER"):
            apply_cause(self.checkpoint, cause, fence=6, expected_revision=1)
        applied = apply_cause(self.checkpoint, cause, fence=7, expected_revision=1)
        repeated = apply_cause(applied, cause, fence=7, expected_revision=2)
        self.assertEqual(applied, repeated)
        self.assertEqual(applied["group_id"], "group-A")
        self.assertEqual(applied["session_ids"], ["session-A"])

    def test_G3_T10_status_does_not_break_pending_hitl(self):
        self.checkpoint["pending_hitl"] = True
        result = apply_cause(self.checkpoint, {"cause_id": "c", "kind": "operation_progress"}, fence=7, expected_revision=1)
        self.assertFalse(result["invoke_runtime"])
        self.assertEqual(result["state"], "waiting_external_event")
        self.assertEqual(len(result["pending_causes"]), 1)

    def test_G3_T11_public_message_identity_and_secret_filter(self):
        projected = project_event(self.event, self.binding, authorized_audience=self.audience)
        self.assertEqual(projected["payload"]["message_id"], "message-A")
        self.assertNotIn("credential", projected["payload"])
        encoded = encode_sse(projected)
        self.assertIn("id: event-A\n", encoded)
        self.assertTrue(encoded.endswith("\n\n"))
        with self.assertRaisesRegex(OrchestrationError, "EVENT_ID_INVALID"):
            encode_sse({**projected, "event_id": "injected\nevent: bad"})

    def test_G3_T12_cursor_scope_and_retention(self):
        cursor = {"conversation_id": "conversation-A", "audience": self.audience, "sequence": 10}
        self.assertEqual(validate_cursor(cursor, conversation_id="conversation-A", audience=self.audience, retention_floor=5), 10)
        with self.assertRaisesRegex(OrchestrationError, "EVENT_CURSOR_INVALID"):
            validate_cursor(cursor, conversation_id="conversation-B", audience=self.audience, retention_floor=5)
        with self.assertRaisesRegex(OrchestrationError, "EVENT_CURSOR_EXPIRED"):
            validate_cursor(cursor, conversation_id="conversation-A", audience=self.audience, retention_floor=11)

    def test_G3_T13_close_cas_and_no_reopen(self):
        with self.assertRaisesRegex(OrchestrationError, "STOP_TRACKING_CONFIRMATION_REQUIRED"):
            close_checkpoint(self.checkpoint, expected_revision=1, operation_pending=True)
        closed = close_checkpoint(self.checkpoint, expected_revision=1, operation_pending=True, stop_tracking_only=True)
        self.assertEqual((closed["state"], closed["next_action"]), ("closed", "none"))
        with self.assertRaisesRegex(OrchestrationError, "WORKFLOW_CLOSED"):
            apply_cause(closed, {"cause_id": "c", "kind": "operation_progress"}, fence=7, expected_revision=2)
        with self.assertRaisesRegex(OrchestrationError, "REVISION_CONFLICT"):
            close_checkpoint(closed, expected_revision=1)

    def test_approval_cannot_be_replaced_by_text_reply(self):
        self.checkpoint["state"] = "awaiting_approval"
        with self.assertRaisesRegex(OrchestrationError, "APPROVAL_REQUIRED"):
            apply_cause(self.checkpoint, {"cause_id": "c", "kind": "user_reply"}, fence=7, expected_revision=1)
        self.checkpoint["state"] = "blocked_authorization"
        with self.assertRaisesRegex(OrchestrationError, "WORKFLOW_BLOCKED"):
            apply_cause(self.checkpoint, {"cause_id": "c", "kind": "approval_result"}, fence=7, expected_revision=1)
