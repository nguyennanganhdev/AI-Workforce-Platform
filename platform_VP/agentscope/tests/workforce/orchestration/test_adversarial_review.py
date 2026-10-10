"""Regressions found by the second PHH testing pass."""

import unittest
import test_stage1 as fixtures
from _support import SCOPE, KEY
from wf_orchestration_under_test._models import OrchestrationError
from wf_orchestration_under_test._messages import MessageService
from wf_orchestration_under_test._evaluation import EvaluationRunner


class AdversarialReviewTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = fixtures.Stage1Tests.asyncSetUp
    run_for = fixtures.Stage1Tests.run_for
    task_for = fixtures.Stage1Tests.task_for

    async def test_pending_message_retry_cannot_dispatch_cancelled_run(self):
        run = await self.run_for()
        attempts = []

        async def delivery(scope, message, *, idempotency_key):
            attempts.append(message)
            raise TimeoutError("lost delivery ACK")

        service = MessageService(self.repo, self.identity, delivery)
        with self.assertRaises(TimeoutError):
            await service.send_message(SCOPE, run.conversation_id, client_message_id="retry", content="hello")
        self.repo.rows[("run", KEY, run.run_id)].status = "cancelled"
        with self.assertRaisesRegex(OrchestrationError, "RUN_UNAVAILABLE"):
            await service.send_message(SCOPE, run.conversation_id, client_message_id="retry", content="hello")
        self.assertEqual(len(attempts), 1)

    async def test_late_worker_cannot_complete_task_in_cancelled_run(self):
        run, task = await self.task_for()
        self.repo.rows[("run", KEY, run.run_id)].status = "cancelled"
        with self.assertRaisesRegex(OrchestrationError, "RUN_UNAVAILABLE"):
            await self.tasks.transition(SCOPE, run.run_id, task["task_id"], "completed",
                                        session_id=run.members[0]["session_id"], result="late")

    async def test_foreign_snapshot_never_reaches_evaluation_runtime(self):
        calls = []

        async def guard(*args):
            calls.append("guard")
            return object()

        async def invoke(*args):
            calls.append("invoke")
            return {"status": "completed", "transcript": [], "tool_traces": [], "cost_minor": 0}

        runner = EvaluationRunner(self.identity, invoke, invoke, guard)
        foreign = {"manifest_hash": "hash", "manifest": {"agent": {}},
                   "scope": {**SCOPE, "manager_account_id": "other"}}
        with self.assertRaisesRegex(OrchestrationError, "SNAPSHOT_SCOPE_INVALID"):
            await runner.run_case(SCOPE, foreign, {}, "mock")
        self.assertEqual(calls, [])

    async def test_missing_snapshot_scope_fails_before_guard(self):
        async def never(*args):
            self.fail("invalid snapshot must not reach a runtime dependency")
        with self.assertRaisesRegex(OrchestrationError, "SCOPE_REQUIRED"):
            await EvaluationRunner(self.identity, never, never, never).run_case(
                SCOPE, {"manifest_hash": "hash", "manifest": {"agent": {}}}, {}, "mock")

    async def test_pending_message_cannot_move_to_another_active_run(self):
        run = await self.run_for()
        calls = []
        async def delivery(scope, message, *, idempotency_key):
            calls.append(message)
            raise TimeoutError()
        service = MessageService(self.repo, self.identity, delivery)
        with self.assertRaises(TimeoutError):
            await service.send_message(SCOPE, run.conversation_id, client_message_id="m", content="hello")
        self.repo.rows[("conversation", KEY, run.conversation_id)].active_run_id = "other-run"
        with self.assertRaisesRegex(OrchestrationError, "RUN_BINDING_MISMATCH"):
            await service.send_message(SCOPE, run.conversation_id, client_message_id="m", content="hello")
        self.assertEqual(len(calls), 1)

    async def test_pending_message_cannot_reach_removed_member_session(self):
        run = await self.run_for()
        calls = []
        async def delivery(scope, message, *, idempotency_key):
            calls.append(message)
            raise TimeoutError()
        service = MessageService(self.repo, self.identity, delivery)
        with self.assertRaises(TimeoutError):
            await service.send_message(SCOPE, run.conversation_id, client_message_id="m", content="hello", target_agent_id="Hotel")
        self.repo.rows[("run", KEY, run.run_id)].members = []
        with self.assertRaisesRegex(OrchestrationError, "MEMBER_NOT_FOUND"):
            await service.send_message(SCOPE, run.conversation_id, client_message_id="m", content="hello", target_agent_id="Hotel")
        self.assertEqual(len(calls), 1)

    async def test_delivered_message_retry_after_cancel_reads_receipt_only(self):
        run = await self.run_for()
        calls = []
        async def delivery(scope, message, *, idempotency_key):
            calls.append(message)
        service = MessageService(self.repo, self.identity, delivery)
        first = await service.send_message(SCOPE, run.conversation_id, client_message_id="m", content="hello")
        self.repo.rows[("run", KEY, run.run_id)].status = "cancelled"
        repeated = await service.send_message(SCOPE, run.conversation_id, client_message_id="m", content="hello")
        self.assertEqual(first, repeated)
        self.assertEqual(len(calls), 1)

    async def test_cancelled_run_allows_cleanup_but_not_worker_ack(self):
        run, task = await self.task_for()
        self.repo.rows[("run", KEY, run.run_id)].status = "cancelled"
        with self.assertRaisesRegex(OrchestrationError, "RUN_UNAVAILABLE"):
            await self.tasks.transition(SCOPE, run.run_id, task["task_id"], "acknowledged",
                                        session_id=run.members[0]["session_id"])
        cleaned = await self.tasks.transition(SCOPE, run.run_id, task["task_id"], "cancelled", session_id=run.leader_session_id)
        self.assertEqual(cleaned["status"], "cancelled")

    async def test_already_completed_task_receipt_remains_idempotent_after_cancel(self):
        run, task = await self.task_for()
        first = await self.tasks.transition(SCOPE, run.run_id, task["task_id"], "completed",
                                           session_id=run.members[0]["session_id"], result="done", tokens=2)
        self.repo.rows[("run", KEY, run.run_id)].status = "cancelled"
        retry = await self.tasks.transition(SCOPE, run.run_id, task["task_id"], "completed",
                                           session_id=run.members[0]["session_id"], result="done", tokens=2)
        self.assertEqual(first, retry)
        self.assertEqual(self.repo.rows[("run", KEY, run.run_id)].used_tokens, 2)
