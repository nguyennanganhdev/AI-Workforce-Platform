"""Adversarial G1 offline behavior tests; IDs map to the PHH phase plan."""

import asyncio
import unittest
from copy import deepcopy

from _support import FakeCatalog, FakeIdentity, FakeRepository, FakeRuntimeHooks, KEY, SCOPE
from wf_orchestration_under_test import (
    CapabilityRouter, ConversationService, HandoffService, RunService,
    SharedStateService, TeamRuntimeAdapter,
)
from wf_orchestration_under_test._context import build_role_context
from wf_orchestration_under_test._models import OrchestrationError, scope_key


class Stage1Tests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.repo, self.identity, self.catalog = FakeRepository(), FakeIdentity(), FakeCatalog()
        self.hooks = FakeRuntimeHooks(self.repo)
        self.runtime = TeamRuntimeAdapter(identity=self.identity,
            provision_pinned_group=self.hooks.provision, send_team_task=self.hooks.send)
        self.router = CapabilityRouter(self.catalog, self.identity)
        self.conversations = ConversationService(self.repo, self.identity)
        self.states = SharedStateService(self.repo, self.identity)
        self.runs = RunService(self.repo, self.identity, self.router, self.runtime)
        self.now = 1000.0
        self.tasks = HandoffService(self.repo, self.identity, self.runtime, clock=lambda: self.now)
        self.conversation = await self.conversations.create(SCOPE)

    async def run_for(self, requirements=("hotel",), conversation=None):
        conversation = conversation or self.conversation
        return await self.runs.start(SCOPE, conversation.conversation_id, requirements,
                                     expected_revision=conversation.state_revision)

    async def task_for(self, run=None, content="find hotel"):
        run = run or await self.run_for()
        task = await self.tasks.create(SCOPE, run.run_id, run.leader_session_id,
                                      "Hotel", content, ["selected-hotel"], timeout_seconds=10)
        return run, task

    async def test_G1_T01_travel_selects_four_and_simple_hotel_one(self):
        selected, _ = await self.router.select(SCOPE, ("plan", "hotel", "car", "calculate"))
        self.assertEqual({x["agent_id"] for x in selected}, {"Plan", "Hotel", "Car", "Calculator"})
        hotel, _ = await self.router.select(SCOPE, ("hotel",))
        self.assertEqual([x["agent_id"] for x in hotel], ["Hotel"])

    async def test_G1_T01_ambiguous_and_missing_fail_closed(self):
        self.catalog.add("Hotel2", "hotel")
        with self.assertRaisesRegex(OrchestrationError, "CAPABILITY_AMBIGUOUS"):
            await self.router.select(SCOPE, ("hotel",))
        with self.assertRaisesRegex(OrchestrationError, "CAPABILITY_MISSING"):
            await self.router.select(SCOPE, ("unknown",))

    async def test_G1_T02_draft_revoked_and_foreign_filtered(self):
        for mode in ("draft", "revoked", "foreign"):
            with self.subTest(mode=mode):
                self.catalog = FakeCatalog()
                if mode == "draft":
                    next(x for x in self.catalog.items if x["agent_id"] == "Hotel")["status"] = "draft"
                elif mode == "revoked":
                    self.catalog.deployments["Hotel"]["status"] = "revoked"
                else:
                    self.catalog.add("Hotel", "hotel", scope=("tenant", "domain", "area", "other"))
                router = CapabilityRouter(self.catalog, self.identity)
                with self.assertRaisesRegex(OrchestrationError, "CAPABILITY_MISSING"):
                    await router.select(SCOPE, ("hotel",))

    async def test_G1_T02_version_scope_hash_agent_and_capability_tamper(self):
        for field, value in (("scope", ("wrong",)), ("manifest_hash", "wrong"), ("agent_id", "other"),
                             ("manifest", {"agent": {"capabilities": []}})):
            with self.subTest(field=field):
                catalog = FakeCatalog()
                catalog.versions["Hotel-v3"][field] = value
                with self.assertRaisesRegex(OrchestrationError, "CAPABILITY_MISSING"):
                    await CapabilityRouter(catalog, self.identity).select(SCOPE, ("hotel",))

    async def test_G1_T03_two_groups_and_new_version_do_not_change_old_pins(self):
        first = await self.run_for()
        second_conversation = await self.conversations.create(SCOPE)
        second = await self.run_for(conversation=second_conversation)
        self.assertNotEqual(first.group_id, second.group_id)
        self.assertNotEqual(first.members[0]["session_id"], second.members[0]["session_id"])
        self.catalog.add("Hotel", "hotel", version="v4")
        third = await self.run_for(conversation=await self.conversations.create(SCOPE))
        self.assertEqual(third.members[0]["version_id"], "Hotel-v4")
        self.assertEqual(first.members[0]["version_id"], "Hotel-v3")
        self.assertEqual(first.members[0]["manifest"]["agent"]["model_config"]["model"], "model-v3")

    async def test_G1_T04_concurrent_cas_only_one_wins(self):
        results = await asyncio.gather(*[
            self.states.patch_facts(SCOPE, self.conversation.conversation_id, 0,
                {"destination": x}, source_kind="user", source_ref=x)
            for x in ("A", "B")], return_exceptions=True)
        self.assertEqual(sum(isinstance(x, OrchestrationError) for x in results), 1)
        self.assertEqual(sum(not isinstance(x, Exception) for x in results), 1)

    async def test_G1_T04_failed_money_update_rolls_back(self):
        with self.assertRaisesRegex(OrchestrationError, "RESERVE_EXCEEDS_BUDGET"):
            await self.states.patch_facts(SCOPE, self.conversation.conversation_id, 0,
                {"budget": 10, "reserve": 11}, source_kind="user", source_ref="message")
        state = await self.conversations.read_state(SCOPE, self.conversation.conversation_id)
        self.assertEqual(state.facts, {})
        self.assertEqual(state.state_revision, 0)

    async def test_G1_T05_changed_budget_invalidates_proposal_and_selection(self):
        key = ("conversation", KEY, self.conversation.conversation_id)
        self.repo.rows[key].proposals = {"p1": {"status": "current", "expires_at": 1200}}
        self.repo.rows[key].selected_refs = {"proposal_id": "p1"}
        state = await self.states.patch_facts(SCOPE, self.conversation.conversation_id, 0,
            {"budget": 10_000_000, "reserve": 2_000_000}, source_kind="user", source_ref="m1")
        self.assertEqual(state.proposals["p1"]["status"], "stale")
        self.assertEqual(state.selected_refs, {})
        with self.assertRaisesRegex(OrchestrationError, "PROPOSAL_STALE"):
            await self.states.select_proposal(SCOPE, state.conversation_id, state.state_revision, "p1", now=self.now)

    async def test_G1_T05_tool_cannot_overwrite_user_fact(self):
        await self.states.patch_facts(SCOPE, self.conversation.conversation_id, 0,
            {"destination": "Ha Long"}, source_kind="user", source_ref="m1")
        with self.assertRaisesRegex(OrchestrationError, "USER_FACT_PROTECTED"):
            await self.states.patch_facts(SCOPE, self.conversation.conversation_id, 1,
                {"destination": "Da Nang"}, source_kind="tool", source_ref="call")
        current = await self.conversations.read_state(SCOPE, self.conversation.conversation_id)
        self.assertEqual(current.facts["destination"], "Ha Long")

    async def test_G1_T05_quote_expired(self):
        self.repo.rows[("conversation", KEY, self.conversation.conversation_id)].proposals = {
            "p": {"status": "current", "expires_at": self.now}}
        with self.assertRaisesRegex(OrchestrationError, "QUOTE_EXPIRED"):
            await self.states.select_proposal(SCOPE, self.conversation.conversation_id, 0, "p", now=self.now)

    async def test_G1_T06_delivery_ack_completion_and_duplicate_completion(self):
        run, task = await self.task_for()
        self.assertEqual(task["status"], "delivered")
        member_session = run.members[0]["session_id"]
        ack = await self.tasks.transition(SCOPE, run.run_id, task["task_id"], "acknowledged", session_id=member_session)
        self.assertEqual(ack["status"], "acknowledged")
        with self.assertRaisesRegex(OrchestrationError, "TASK_RESULT_REQUIRED"):
            await self.tasks.transition(SCOPE, run.run_id, task["task_id"], "completed", session_id=member_session)
        for _ in range(2):
            result = await self.tasks.transition(SCOPE, run.run_id, task["task_id"], "completed",
                session_id=member_session, result={"hotel": "H1"}, tokens=5, cost_minor=2)
        self.assertEqual(result["status"], "completed")
        stored = self.repo.rows[("run", KEY, run.run_id)]
        self.assertEqual((stored.used_tokens, stored.used_cost_minor), (5, 2))

    async def test_G1_T06_wrong_session_cannot_complete(self):
        run, task = await self.task_for()
        with self.assertRaisesRegex(OrchestrationError, "TASK_ACTOR_INVALID"):
            await self.tasks.transition(SCOPE, run.run_id, task["task_id"], "completed",
                                        session_id="foreign", result="fake success")

    async def test_G1_T07_timeout_late_result_cancel_and_loop(self):
        run, task = await self.task_for()
        with self.assertRaisesRegex(OrchestrationError, "HANDOFF_LOOP"):
            await self.tasks.create(SCOPE, run.run_id, run.leader_session_id, "Hotel", "find hotel", [])
        self.now += 11
        late = await self.tasks.transition(SCOPE, run.run_id, task["task_id"], "completed",
                                          session_id=run.members[0]["session_id"], result="late")
        self.assertEqual(late["status"], "timed_out")
        self.assertNotIn("result", late)
        with self.assertRaisesRegex(OrchestrationError, "TASK_TERMINAL"):
            await self.tasks.transition(SCOPE, run.run_id, task["task_id"], "completed",
                                        session_id=run.members[0]["session_id"], result="late")
        run, second = await self.task_for(run, "new task")
        cancelled = await self.tasks.transition(SCOPE, run.run_id, second["task_id"], "cancelled", session_id=run.leader_session_id)
        self.assertEqual(cancelled["status"], "cancelled")

    async def test_G1_T07_concurrency_handoff_and_budget_limits(self):
        for attr, value, error in (("max_concurrent", 0, "CONCURRENCY_LIMIT"),
                                   ("max_handoffs", 0, "HANDOFF_LIMIT"),
                                   ("token_limit", 0, "RUN_BUDGET_EXHAUSTED")):
            run = await self.run_for(conversation=await self.conversations.create(SCOPE))
            setattr(self.repo.rows[("run", KEY, run.run_id)], attr, value)
            with self.subTest(attr=attr), self.assertRaisesRegex(OrchestrationError, error):
                await self.task_for(run)

    async def test_G1_T08_transport_loss_resume_same_runtime_ids(self):
        self.hooks.fail = True
        with self.assertRaises(TimeoutError):
            await self.run_for()
        current = await self.conversations.read_state(SCOPE, self.conversation.conversation_id)
        run = self.repo.rows[("run", KEY, current.active_run_id)]
        self.assertEqual(run.status, "materializing")
        old = deepcopy(run)
        self.hooks.fail = False
        resumed = await self.runs.resume_materialization(SCOPE, run.run_id)
        self.assertEqual(resumed.group_id, old.group_id)
        self.assertEqual(resumed.members, old.members)
        self.assertEqual(len(self.hooks.groups), 1)
        again = await self.runs.resume_materialization(SCOPE, run.run_id)
        self.assertEqual(resumed, again)

    async def test_cross_scope_and_revocation_fail_closed(self):
        other = {**SCOPE, "manager_account_id": "other"}
        with self.assertRaisesRegex(OrchestrationError, "RESOURCE_NOT_FOUND"):
            await self.conversations.read_state(other, self.conversation.conversation_id)
        self.identity.revoked = True
        with self.assertRaisesRegex(OrchestrationError, "SCOPE_REVOKED"):
            await self.run_for()
        self.assertEqual(self.hooks.groups, {})

    async def test_payload_validation_and_detached_state(self):
        with self.assertRaisesRegex(OrchestrationError, "SCOPE_REQUIRED"):
            scope_key({"manager_account_id": "manager"})
        with self.assertRaisesRegex(OrchestrationError, "MONEY_INVALID"):
            await self.states.patch_facts(SCOPE, self.conversation.conversation_id, 0,
                {"budget": True}, source_kind="user", source_ref="m")
        external = await self.conversations.read_state(SCOPE, self.conversation.conversation_id)
        external.facts["destination"] = "mutation"
        current = await self.conversations.read_state(SCOPE, self.conversation.conversation_id)
        self.assertEqual(current.facts, {})

    async def test_role_context_uses_current_roster_and_correct_context(self):
        run = await self.run_for(("plan", "hotel"))
        context = build_role_context(run, self.conversation, role="planner", agent_id="Plan")
        self.assertEqual({m["agent_id"] for m in context["roster"]}, {"Plan", "Hotel"})
        other = await self.conversations.create(SCOPE)
        with self.assertRaisesRegex(OrchestrationError, "CONTEXT_BINDING_INVALID"):
            build_role_context(run, other, role="leader")

    async def test_delivery_ack_race_does_not_regress_completed_task(self):
        run = await self.run_for()

        async def fast_worker(scope, group_id, session_id, task, *, idempotency_key):
            await self.tasks.transition(scope, run.run_id, task["task_id"], "completed",
                                        session_id=session_id, result="immediate result")

        self.runtime.send = fast_worker
        _, result = await self.task_for(run)
        self.assertEqual(result["status"], "completed")

    async def test_expired_task_releases_concurrency_capacity(self):
        run = await self.run_for()
        self.repo.rows[("run", KEY, run.run_id)].max_concurrent = 1
        _, previous = await self.task_for(run)
        self.now += 11
        _, following = await self.task_for(run, "next task")
        stored = self.repo.rows[("run", KEY, run.run_id)]
        self.assertEqual(stored.handoffs[previous["task_id"]]["status"], "timed_out")
        self.assertEqual(following["status"], "delivered")

    async def test_catalog_accepts_shared_dto_scope_dictionary(self):
        for item in self.catalog.items:
            item["scope"] = dict(SCOPE)
        for item in self.catalog.versions.values():
            item["scope"] = dict(SCOPE)
        for item in self.catalog.deployments.values():
            item["scope"] = dict(SCOPE)
        selected, _ = await self.router.select(SCOPE, ("hotel",))
        self.assertEqual(selected[0]["agent_id"], "Hotel")


if __name__ == "__main__":
    unittest.main()
