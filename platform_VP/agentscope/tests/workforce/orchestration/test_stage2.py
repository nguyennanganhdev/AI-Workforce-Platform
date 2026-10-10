"""G2 routing/context/evaluation behavioral tests using test-only hooks."""

from copy import deepcopy

import unittest
import test_stage1 as stage1
from _support import SCOPE, KEY
from wf_orchestration_under_test._evaluation import EvaluationRunner
from wf_orchestration_under_test._members import MemberService
from wf_orchestration_under_test._messages import MessageService, shared_context
from wf_orchestration_under_test._mentions import resolve_entity, resolve_recipient
from wf_orchestration_under_test._models import OrchestrationError


class Stage2Tests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = stage1.Stage1Tests.asyncSetUp
    run_for = stage1.Stage1Tests.run_for
    task_for = stage1.Stage1Tests.task_for
    async def test_G2_T01_mention_same_session_and_idempotent_message(self):
        run = await self.run_for()
        deliveries = {}

        async def deliver(scope, message, *, idempotency_key):
            deliveries.setdefault(idempotency_key, deepcopy(message))

        service = MessageService(self.repo, self.identity, deliver)
        first = await service.send_message(SCOPE, run.conversation_id,
            client_message_id="c1", content="hotel amenities?", target_agent_id="Hotel")
        retry = await service.send_message(SCOPE, run.conversation_id,
            client_message_id="c1", content="hotel amenities?", target_agent_id="Hotel")
        self.assertEqual(first, retry)
        self.assertEqual(first["target_session_id"], run.members[0]["session_id"])
        self.assertEqual(len(deliveries), 1)
        with self.assertRaisesRegex(OrchestrationError, "MESSAGE_ID_CONFLICT"):
            await service.send_message(SCOPE, run.conversation_id,
                client_message_id="c1", content="changed", target_agent_id="Hotel")

    async def test_G2_T02_unknown_target_and_duplicate_names(self):
        run = await self.run_for(("hotel", "car"))
        with self.assertRaisesRegex(OrchestrationError, "MEMBER_NOT_FOUND"):
            resolve_recipient(run, self.conversation, target_agent_id="foreign")
        for member in run.members:
            member["name"] = "same-name"
        with self.assertRaisesRegex(OrchestrationError, "MENTION_AMBIGUOUS"):
            resolve_recipient(run, self.conversation, mention_name="same-name")

    async def test_G2_T03_pending_question_targets_planner_and_ambiguity(self):
        run = await self.run_for(("plan", "hotel"))
        planner = next(m for m in run.members if m["agent_id"] == "Plan")
        self.conversation.pending_questions = {"q1": {"message_id": "m1", "session_id": planner["session_id"]}}
        self.assertEqual(resolve_recipient(run, self.conversation), planner["session_id"])
        self.conversation.pending_questions["q2"] = {"message_id": "m2", "session_id": run.leader_session_id}
        with self.assertRaisesRegex(OrchestrationError, "PENDING_QUESTION_AMBIGUOUS"):
            resolve_recipient(run, self.conversation)

    async def test_G2_T04_entity_requires_explicit_or_unique_reference(self):
        self.conversation.facts["candidates"] = {"hotel": [{"id": "H1"}, {"id": "H2"}]}
        with self.assertRaisesRegex(OrchestrationError, "ENTITY_AMBIGUOUS"):
            resolve_entity(self.conversation, "hotel")
        self.conversation.selected_refs["hotel"] = "H2"
        self.assertEqual(resolve_entity(self.conversation, "hotel"), {"id": "H2"})

    async def test_G2_T05_selected_context_does_not_include_history(self):
        self.conversation.facts = {"destination": "Ha Long", "budget": 10}
        self.conversation.messages = [{"content": "private message"}]
        context = shared_context(self.conversation, selected_fact_keys=["destination"])
        self.assertEqual(context, {"destination": "Ha Long"})
        with self.assertRaisesRegex(OrchestrationError, "CONTEXT_FIELD_INVALID"):
            shared_context(self.conversation, selected_fact_keys=["messages"])

    async def test_G2_T05_direct_chat_refuses_another_member(self):
        direct = await self.conversations.create(SCOPE, mode="direct", direct_agent_id="Hotel")
        run = await self.run_for(conversation=direct)

        async def deliver(*args, **kwargs):
            raise AssertionError("must not dispatch")

        with self.assertRaisesRegex(OrchestrationError, "DIRECT_TARGET_INVALID"):
            await MessageService(self.repo, self.identity, deliver).send_message(
                SCOPE, run.conversation_id, client_message_id="c", content="private", target_agent_id="Car")

    async def test_G2_T06_add_cross_batch_no_duplicate_preserves_pending_tasks(self):
        self.catalog.add("Hotel", "hotel", batch="B")
        run = await self.run_for(("plan",))
        service = MemberService(self.repo, self.identity, self.router, self.runtime)
        candidate = next(x for x in self.catalog.items if x["agent_id"] == "Hotel")
        added = await service.add(SCOPE, run.run_id, candidate, expected_revision=run.revision, reason="hotel request")
        self.assertEqual({x["agent_id"] for x in added.members}, {"Plan", "Hotel"})
        again = await service.add(SCOPE, run.run_id, candidate, expected_revision=added.revision, reason="retry")
        self.assertEqual(again.members, added.members)
        self.assertEqual(again.handoffs, added.handoffs)

    async def test_G2_T07_evaluation_same_runtime_with_backend_guard(self):
        calls = []

        async def guard_factory(scope, mode):
            return {"mode": mode, "fixed_clock": 1000}

        async def invoke(scope, snapshot, case, guard):
            calls.append((snapshot, case, guard))
            return {"status": "completed", "transcript": ["answer"], "tool_traces": [], "cost_minor": 0}

        async def cancel(scope, case_id):
            return {"case_run_id": case_id, "status": "cancelled"}

        runner = EvaluationRunner(self.identity, invoke, cancel, guard_factory)
        result = await runner.run_case(SCOPE, {"scope": SCOPE, "manifest_hash": "h", "manifest": {"agent": {}}}, {"input": "question"}, "mock")
        self.assertEqual(result["status"], "completed")
        self.assertEqual(calls[0][2], {"mode": "mock", "fixed_clock": 1000})
        with self.assertRaisesRegex(OrchestrationError, "EVALUATION_MODE_INVALID"):
            await runner.run_case(SCOPE, {}, {}, "production")
        self.assertEqual((await runner.cancel_case(SCOPE, "case1"))["status"], "cancelled")

    async def test_G2_T08_evaluation_failure_not_promoted_to_pass(self):
        async def guard(*args):
            return object()

        async def invoke(*args):
            return {"status": "failed", "transcript": [], "tool_traces": [], "cost_minor": 1}

        result = await EvaluationRunner(self.identity, invoke, invoke, guard).run_case(
            SCOPE, {"scope": SCOPE, "manifest_hash": "h", "manifest": {"agent": {}}}, {}, "mock")
        self.assertEqual(result["status"], "failed")

    async def test_message_timeout_retry_same_id_and_session(self):
        run = await self.run_for()
        deliveries = set()
        fail = True

        async def deliver(scope, message, *, idempotency_key):
            deliveries.add(idempotency_key)
            if fail:
                raise TimeoutError("transport loss")

        service = MessageService(self.repo, self.identity, deliver)
        with self.assertRaises(TimeoutError):
            await service.send_message(SCOPE, run.conversation_id, client_message_id="c", content="hello")
        fail = False
        result = await service.send_message(SCOPE, run.conversation_id, client_message_id="c", content="hello")
        self.assertEqual(len(deliveries), 1)
        self.assertEqual(result["delivery_status"], "delivered")

    async def test_manual_add_timeout_recovers_same_session(self):
        run = await self.run_for(("plan",))
        self.hooks.fail = True
        candidate = next(x for x in self.catalog.items if x["agent_id"] == "Hotel")
        service = MemberService(self.repo, self.identity, self.router, self.runtime)
        with self.assertRaises(TimeoutError):
            await service.add(SCOPE, run.run_id, candidate, expected_revision=run.revision, reason="hotel")
        pending = deepcopy(self.repo.rows[("run", KEY, run.run_id)])
        self.assertEqual(pending.status, "running")
        self.assertEqual([m["agent_id"] for m in pending.pending_members], ["Hotel"])
        self.hooks.fail = False
        recovered = await self.runs.resume_materialization(SCOPE, run.run_id)
        self.assertEqual(pending.members + pending.pending_members, recovered.members)
        self.assertEqual(recovered.pending_members, [])
        self.assertEqual(recovered.status, "running")
