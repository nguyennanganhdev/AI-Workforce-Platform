"""Behavior at membership provisioning, completion and recovery boundaries."""

import asyncio
import unittest

import test_stage1 as fixtures
from _support import KEY, SCOPE
from wf_orchestration_under_test._members import MemberService
from wf_orchestration_under_test._models import OrchestrationError


class MemberRecoveryTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = fixtures.Stage1Tests.asyncSetUp
    run_for = fixtures.Stage1Tests.run_for
    task_for = fixtures.Stage1Tests.task_for

    async def add_car(self, run):
        current = self.repo.rows[("run", KEY, run.run_id)]
        candidate = next(c for c in self.catalog.items if c["agent_id"] == "Car")
        return await MemberService(self.repo, self.identity, self.router, self.runtime).add(
            SCOPE, run.run_id, candidate, expected_revision=current.revision, reason="need car")

    async def test_existing_task_completes_while_new_member_is_provisioning(self):
        run, task = await self.task_for()
        original = self.runtime.materialize

        async def during_add(scope, pending):
            await self.tasks.transition(scope, run.run_id, task["task_id"], "acknowledged",
                                        session_id=run.members[0]["session_id"])
            await self.tasks.transition(scope, run.run_id, task["task_id"], "completed",
                                        session_id=run.members[0]["session_id"], result="ready", tokens=7)
            return await original(scope, pending)

        self.runtime.materialize = during_add
        added = await self.add_car(run)
        self.assertEqual(added.handoffs[task["task_id"]]["status"], "completed")
        self.assertEqual(added.used_tokens, 7)
        self.assertEqual({m["agent_id"] for m in added.members}, {"Hotel", "Car"})

    async def test_recovery_winning_race_returns_success_for_same_membership(self):
        run = await self.run_for()
        original = self.runtime.materialize

        async def recover_first(scope, pending):
            await original(scope, pending)
            self.runtime.materialize = original
            await self.runs.resume_materialization(scope, run.run_id)

        self.runtime.materialize = recover_first
        added = await self.add_car(run)
        self.assertEqual(added.status, "running")
        self.assertEqual(len([m for m in added.members if m["agent_id"] == "Car"]), 1)
        self.assertEqual(len(self.hooks.groups), 2)

    async def test_pending_member_cannot_receive_tasks_before_recovery(self):
        run = await self.run_for()
        self.hooks.fail = True
        with self.assertRaises(TimeoutError):
            await self.add_car(run)
        with self.assertRaisesRegex(OrchestrationError, "MEMBER_NOT_FOUND"):
            await self.tasks.create(SCOPE, run.run_id, run.leader_session_id, "Car", "find car", [])
        self.hooks.fail = False
        recovered = await self.runs.resume_materialization(SCOPE, run.run_id)
        task = await self.tasks.create(SCOPE, run.run_id, recovered.leader_session_id, "Car", "find car", [])
        self.assertEqual(task["status"], "delivered")

    async def test_timeout_retry_keeps_operation_key_after_existing_task_updates(self):
        run, task = await self.task_for()
        self.hooks.fail = True
        with self.assertRaises(TimeoutError):
            await self.add_car(run)
        await self.tasks.transition(SCOPE, run.run_id, task["task_id"], "completed",
                                    session_id=run.members[0]["session_id"], result="done")
        keys = set(self.hooks.groups)
        self.hooks.fail = False
        recovered = await self.add_car(run)
        self.assertEqual(set(self.hooks.groups), keys)
        self.assertEqual(len(recovered.members), 2)
        self.assertEqual(recovered.handoffs[task["task_id"]]["status"], "completed")

    async def test_cancel_during_add_does_not_reactivate_run_or_accept_late_result(self):
        run, task = await self.task_for()
        original = self.runtime.materialize

        async def cancel_before_return(scope, pending):
            await original(scope, pending)
            self.repo.rows[("run", KEY, run.run_id)].status = "cancelled"

        self.runtime.materialize = cancel_before_return
        with self.assertRaises(OrchestrationError):
            await self.add_car(run)
        with self.assertRaisesRegex(OrchestrationError, "RUN_UNAVAILABLE"):
            await self.tasks.transition(SCOPE, run.run_id, task["task_id"], "completed",
                                        session_id=run.members[0]["session_id"], result="late")
        self.assertEqual(self.repo.rows[("run", KEY, run.run_id)].status, "cancelled")

    async def test_equal_relevant_capabilities_are_ambiguous_regardless_of_agent_id(self):
        for agent_id in ("AHotelCar", "ZHotelCar"):
            with self.subTest(agent_id=agent_id):
                await self.asyncSetUp()
                self.catalog.add(agent_id, "hotel")
                candidate = next(c for c in self.catalog.items if c["agent_id"] == agent_id)
                candidate["capabilities"].append("car")
                self.catalog.versions[candidate["version_id"]]["manifest"]["agent"]["capabilities"].append("car")
                with self.assertRaisesRegex(OrchestrationError, "CAPABILITY_AMBIGUOUS"):
                    await self.router.select(SCOPE, ("hotel",))

    async def test_complementary_agents_are_not_ambiguous(self):
        selected, _ = await self.router.select(SCOPE, ("hotel", "car"))
        self.assertEqual({m["agent_id"] for m in selected}, {"Hotel", "Car"})

    async def test_second_add_cannot_replace_pending_intent(self):
        run = await self.run_for()
        self.hooks.fail = True
        with self.assertRaises(TimeoutError):
            await self.add_car(run)
        pending = self.repo.rows[("run", KEY, run.run_id)]
        candidate = next(c for c in self.catalog.items if c["agent_id"] == "Plan")
        with self.assertRaisesRegex(OrchestrationError, "MEMBERSHIP_UPDATE_PENDING"):
            await MemberService(self.repo, self.identity, self.router, self.runtime).add(
                SCOPE, run.run_id, candidate, expected_revision=pending.revision, reason="need planner")
        self.assertEqual(self.repo.rows[("run", KEY, run.run_id)], pending)

    async def test_recovery_does_not_accept_different_member_session_as_success(self):
        run = await self.run_for()
        original = self.runtime.materialize

        async def replace_after_recovery(scope, pending):
            await original(scope, pending)
            self.runtime.materialize = original
            await self.runs.resume_materialization(scope, run.run_id)
            stored = self.repo.rows[("run", KEY, run.run_id)]
            next(m for m in stored.members if m["agent_id"] == "Car")["session_id"] = "different-session"

        self.runtime.materialize = replace_after_recovery
        with self.assertRaisesRegex(OrchestrationError, "MEMBERSHIP_BINDING_INVALID"):
            await self.add_car(run)

    async def test_two_recovery_workers_commit_one_membership(self):
        run = await self.run_for()
        self.hooks.fail = True
        with self.assertRaises(TimeoutError):
            await self.add_car(run)
        self.hooks.fail = False
        keys = set(self.hooks.groups)
        original = self.runtime.materialize
        both_started = asyncio.Event()
        arrivals = 0

        async def simultaneous(scope, pending):
            nonlocal arrivals
            arrivals += 1
            if arrivals == 2:
                both_started.set()
            await asyncio.wait_for(both_started.wait(), 2)
            return await original(scope, pending)

        self.runtime.materialize = simultaneous
        first, second = await asyncio.gather(
            self.runs.resume_materialization(SCOPE, run.run_id),
            self.runs.resume_materialization(SCOPE, run.run_id))
        self.assertEqual(first, second)
        self.assertEqual(len(first.members), 2)
        self.assertEqual(first.pending_members, [])
        self.assertEqual(set(self.hooks.groups), keys)

    async def test_pending_member_message_is_blocked_but_existing_member_keeps_session(self):
        from wf_orchestration_under_test._messages import MessageService

        run = await self.run_for()
        self.hooks.fail = True
        with self.assertRaises(TimeoutError):
            await self.add_car(run)
        delivered = []

        async def delivery(scope, message, *, idempotency_key):
            delivered.append(message)

        service = MessageService(self.repo, self.identity, delivery)
        with self.assertRaisesRegex(OrchestrationError, "MEMBER_NOT_FOUND"):
            await service.send_message(SCOPE, run.conversation_id,
                                       client_message_id="pending", content="hello", target_agent_id="Car")
        receipt = await service.send_message(SCOPE, run.conversation_id,
                                             client_message_id="ready", content="hello", target_agent_id="Hotel")
        self.assertEqual(receipt["target_session_id"], run.members[0]["session_id"])
        self.assertEqual(len(delivered), 1)

    async def test_overlapping_equal_rank_choices_do_not_depend_on_id_order(self):
        for ids in (("A", "B", "C"), ("C", "B", "A")):
            with self.subTest(ids=ids):
                await self.asyncSetUp()
                self.catalog.items = []
                for agent_id, capabilities in zip(ids, (("a", "b"), ("b", "c"), ("a", "d"))):
                    self.catalog.add(agent_id, capabilities[0])
                    candidate = next(c for c in self.catalog.items if c["agent_id"] == agent_id)
                    candidate["capabilities"] = list(capabilities)
                    self.catalog.versions[candidate["version_id"]]["manifest"]["agent"]["capabilities"] = list(capabilities)
                with self.assertRaisesRegex(OrchestrationError, "CAPABILITY_AMBIGUOUS"):
                    await self.router.select(SCOPE, ("a", "b", "c", "d"))
