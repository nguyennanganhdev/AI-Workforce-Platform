"""Independent scenarios; each negative case starts from a working control."""

import asyncio
from copy import deepcopy
from datetime import timedelta
import json
import unittest

from agentscope.app.workforce.contracts import EventHistoryPage
from agentscope.app.workforce.orchestration.partner_events import (
    EventCursorExpired,
)
from agentscope.app.workforce.orchestration.workflows import (
    WorkflowClosed,
    WorkflowConflict,
    next_action,
)
from fakes import ACTOR, SCOPE, Harness, Uow


class PhaseB(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.h = Harness()
        self.a = await self.h.start()
        self.trigger = self.h.trigger(self.a.workflow_id)

    async def run_turn(self):
        return await self.h.continuation.run(SCOPE, self.trigger, "worker-A")

    async def close(self, **changes):
        return await self.h.workflows.close(
            SCOPE,
            ACTOR,
            self.a.audience,
            self.h.close_command(self.a, **changes),
        )

    async def test_B001_start_reserves_binding_and_checkpoint_job_atomically(
        self,
    ):
        self.assertEqual(len(self.h.store.data["workflows"]), 1)
        self.assertEqual(len(self.h.store.data["jobs"]), 1)
        self.assertEqual(len(self.h.store.data["checkpoints"]), 1)
        self.assertEqual(self.h.store.commits, 1)
        self.assertEqual(len(self.h.signals.notifications), 1)

    async def test_B002_retry_reuses_group_and_job(self):
        retry = await self.h.start()
        self.assertEqual(retry, self.a)
        self.assertEqual(len(self.h.store.data["jobs"]), 1)
        self.assertEqual(
            len(self.h.store.data["events"][self.a.conversation_id]), 1
        )
        self.assertEqual(len(self.h.store.data["checkpoints"]), 1)

    async def test_B003_two_tickets_same_user_and_agent_have_separate_sessions(
        self,
    ):
        b = await self.h.start("B")
        aa, bb = await self.h.repo.load(
            SCOPE, self.a.workflow_id
        ), await self.h.repo.load(SCOPE, b.workflow_id)
        self.assertEqual(
            aa.checkpoint.agent_version_pins, bb.checkpoint.agent_version_pins
        )
        self.assertNotEqual(
            aa.checkpoint.session_refs, bb.checkpoint.session_refs
        )
        self.assertNotEqual(self.a.group_id, b.group_id)

    async def test_B004_start_commit_failure_rolls_back(
        self,
    ):
        before = deepcopy(self.h.store.data)
        self.h.store.fail_commit = True
        with self.assertRaises(WorkflowConflict):
            await self.h.start("B")
        self.assertEqual(before, self.h.store.data)
        self.assertEqual(len(self.h.signals.notifications), 1)

    async def test_B005_reply_keeps_group_session_and_pins(self):
        result = await self.h.workflows.accept_reply(
            SCOPE,
            ACTOR,
            self.a.audience,
            self.a.workflow_id,
            dict(request_id="reply-A", text="Trả lời", expected_revision=1),
        )
        self.assertEqual(result.group_id, self.a.group_id)
        await self.h.continuation.run(
            SCOPE, self.h.trigger(self.a.workflow_id, "reply-A"), "worker-A"
        )
        context = self.h.runtime.calls[0][1]
        self.assertEqual(context.workflow.group_id, self.a.group_id)
        self.assertEqual(context.checkpoint.session_refs, ("session-1",))

    async def test_B006_reply_to_other_ticket_is_denied(self):
        b = await self.h.start("B")
        with self.assertRaises(PermissionError):
            await self.h.workflows.accept_reply(
                SCOPE,
                ACTOR,
                b.audience,
                self.a.workflow_id,
                dict(
                    request_id="reply-A", text="Trả lời", expected_revision=1
                ),
            )

    async def test_B007_reply_stale_revision_does_not_enqueue(self):
        before = deepcopy(self.h.store.data["jobs"])
        with self.assertRaises(WorkflowConflict):
            await self.h.workflows.accept_reply(
                SCOPE,
                ACTOR,
                self.a.audience,
                self.a.workflow_id,
                dict(
                    request_id="reply-A", text="Trả lời", expected_revision=2
                ),
            )
        self.assertEqual(before, self.h.store.data["jobs"])

    async def test_B008_reply_changed_content_same_id_conflicts(self):
        with self.assertRaises(WorkflowConflict):
            await self.h.workflows.accept_reply(
                SCOPE,
                ACTOR,
                self.a.audience,
                self.a.workflow_id,
                dict(
                    request_id="request-A",
                    text="Nội dung khác",
                    expected_revision=1,
                ),
            )

    async def test_B009_revoked_actor_cannot_reply(self):
        self.h.auth.revoked = True
        with self.assertRaises(PermissionError):
            await self.h.workflows.accept_reply(
                SCOPE,
                ACTOR,
                self.a.audience,
                self.a.workflow_id,
                dict(
                    request_id="reply-A", text="Trả lời", expected_revision=1
                ),
            )

    async def test_B010_provider_credential_cannot_read_customer_events(self):
        actor = ACTOR.model_copy(
            update={"credential_purpose": "provider_events"}
        )
        with self.assertRaises(PermissionError):
            await self.h.events.list_after(
                actor, self.a.conversation_id, None, 10
            )

    async def test_B011_pending_request_runs_once_and_persists_processed_cause(
        self,
    ):
        self.assertEqual(await self.run_turn(), "applied")
        self.assertEqual(await self.run_turn(), "duplicate")
        self.assertEqual(len(self.h.runtime.calls), 1)
        self.assertEqual(
            (
                await self.h.repo.load(SCOPE, self.a.workflow_id)
            ).workflow.revision,
            2,
        )

    async def test_B012_message_id_is_identical_in_result_event_and_snapshot(
        self,
    ):
        await self.run_turn()
        result = self.h.store.data["results"]["request-A"]
        page = await self.h.events.list_after(
            ACTOR, self.a.conversation_id, None, 10
        )
        message = next(
            e for e in page.items if e.event_type == "assistant.message"
        )
        snapshot = await self.h.events.snapshot(ACTOR, self.a.conversation_id)
        self.assertEqual(
            result.messages[0].message_id, message.payload["message_id"]
        )
        self.assertEqual(
            snapshot["messages"][0]["message_id"],
            result.messages[0].message_id,
        )

    async def test_B013_response_only_published_read_only_auto_closes(self):
        self.h.configure(
            self.a, pattern="response_only", published_read_only=True
        )
        self.h.runtime.state = "closed"
        await self.run_turn()
        bundle = await self.h.repo.load(SCOPE, self.a.workflow_id)
        self.assertEqual(bundle.workflow.state, "closed")
        self.assertEqual(next_action(bundle.workflow.state), "none")

    async def test_B014_interactive_cannot_auto_close(self):
        self.h.runtime.state = "closed"
        with self.assertRaises(WorkflowConflict):
            await self.run_turn()
        self.assertNotIn("request-A", self.h.store.data["results"])

    async def test_B015_approval_wait_requires_real_pending_ref(self):
        self.h.runtime.state = "awaiting_approval"
        with self.assertRaises(WorkflowConflict):
            await self.run_turn()

    async def test_B016_wait_requires_tracking_pattern_and_pending_operation(
        self,
    ):
        self.h.add_operation(self.a)
        self.h.runtime.state = "waiting_external_event"
        await self.run_turn()
        bundle = await self.h.repo.load(SCOPE, self.a.workflow_id)
        self.assertEqual(bundle.workflow.pending_waits, ("operation-A",))

    async def test_B017_terminal_operation_cannot_enter_external_wait(self):
        self.h.add_operation(self.a)
        self.h.ops.pending = False
        self.h.runtime.state = "waiting_external_event"
        with self.assertRaises(WorkflowConflict):
            await self.run_turn()

    async def test_B018_no_operation_cannot_enter_external_wait(self):
        self.h.runtime.state = "waiting_external_event"
        with self.assertRaises(WorkflowConflict):
            await self.run_turn()

    async def test_B019_interleaved_turns_keep_correct_group_and_messages(
        self,
    ):
        b = await self.h.start("B")
        await self.run_turn()
        await self.h.continuation.run(
            SCOPE, self.h.trigger(b.workflow_id, "request-B"), "worker-B"
        )
        contexts = [c[1].workflow for c in self.h.runtime.calls]
        self.assertEqual(
            [c.group_id for c in contexts], [self.a.group_id, b.group_id]
        )
        for wf in (self.a, b):
            page = await self.h.events.list_after(
                ACTOR, wf.conversation_id, None, 10
            )
            self.assertTrue(
                all(e.workflow_id == wf.workflow_id for e in page.items)
            )

    async def test_B020_unbound_trigger_is_rejected_before_runtime(self):
        self.trigger["cause"]["request_id"] = "request-B"
        with self.assertRaises(PermissionError):
            await self.run_turn()
        self.assertFalse(self.h.runtime.calls)

    async def test_B021_forged_approval_cannot_resume(self):
        self.h.configure(
            self.a,
            state="awaiting_approval",
            checkpoint=dict(pending_approval_ids=["approval-A"]),
        )
        self.trigger = self.h.trigger(
            self.a.workflow_id, "forged", "approval", approval_id="approval-A"
        )
        with self.assertRaises(PermissionError):
            await self.run_turn()

    async def test_B022_verified_approval_preserves_other_pins(self):
        self.h.configure(
            self.a,
            state="awaiting_approval",
            checkpoint=dict(pending_approval_ids=["approval-A"]),
        )
        self.trigger = self.h.trigger(
            self.a.workflow_id,
            "verified-approval-request",
            "approval",
            approval_id="approval-A",
        )
        await self.run_turn()
        bundle = await self.h.repo.load(SCOPE, self.a.workflow_id)
        self.assertEqual(bundle.checkpoint.pending_approval_ids, ())
        self.assertEqual(bundle.checkpoint.session_refs, ("session-1",))

    async def test_B023_lease_prevents_two_workers_running_same_workflow(self):
        lease = await self.h.repo.claim(
            SCOPE, self.a.workflow_id, "worker-B", timedelta(seconds=120)
        )
        self.assertIsNotNone(lease)
        with self.assertRaises(WorkflowConflict):
            await self.run_turn()
        self.assertFalse(self.h.runtime.calls)

    async def test_B024_expired_lease_candidate_cannot_commit(self):
        async def expire(guard):
            self.h.clock.tick(121)

        self.h.runtime.hook = expire
        with self.assertRaises(WorkflowConflict):
            await self.run_turn()
        self.assertEqual(
            (
                await self.h.repo.load(SCOPE, self.a.workflow_id)
            ).workflow.revision,
            1,
        )
        self.assertFalse(self.h.store.data["results"])

    async def test_B025_replaced_fence_candidate_cannot_commit(self):
        async def replace(guard):
            self.h.clock.tick(121)
            await self.h.repo.claim(
                SCOPE, self.a.workflow_id, "worker-B", timedelta(seconds=120)
            )

        self.h.runtime.hook = replace
        with self.assertRaises(WorkflowConflict):
            await self.run_turn()
        self.assertEqual(
            self.h.store.leases[self.a.workflow_id].owner, "worker-B"
        )

    async def test_B026_close_during_turn_discards_late_message(self):
        async def close(guard):
            await self.close()

        self.h.runtime.hook = close
        with self.assertRaises(WorkflowClosed):
            await self.run_turn()
        self.assertEqual(
            (await self.h.repo.load(SCOPE, self.a.workflow_id)).workflow.state,
            "closed",
        )
        page = await self.h.events.list_after(
            ACTOR, self.a.conversation_id, None, 10
        )
        self.assertFalse(
            any(e.event_type == "assistant.message" for e in page.items)
        )

    async def test_B027_runtime_guard_blocks_side_effect_after_close(self):
        async def close(guard):
            await self.close()
            await guard.check()

        self.h.runtime.hook = close
        with self.assertRaises(WorkflowClosed):
            await self.run_turn()

    async def test_B028_runtime_exception_releases_lease(
        self,
    ):
        async def fail(guard):
            raise ConnectionError("runtime crash")

        self.h.runtime.hook = fail
        with self.assertRaises(ConnectionError):
            await self.run_turn()
        self.assertFalse(self.h.store.leases)
        self.assertEqual(
            (
                await self.h.repo.load(SCOPE, self.a.workflow_id)
            ).workflow.revision,
            1,
        )

    async def test_B029_commit_failure_can_retry_from_last_checkpoint(self):
        self.h.store.fail_commit = True
        with self.assertRaises(WorkflowConflict):
            await self.run_turn()
        self.assertFalse(self.h.store.data["results"])
        self.h.store.fail_commit = False
        self.assertEqual(await self.run_turn(), "applied")
        self.assertEqual(len(self.h.runtime.calls), 2)
        self.assertEqual(len(self.h.store.data["results"]), 1)

    async def test_B030_revoked_grant_during_runtime_discards_result(self):
        async def revoke(guard):
            self.h.auth.revoked = True

        self.h.runtime.hook = revoke
        with self.assertRaises(PermissionError):
            await self.run_turn()
        self.assertFalse(self.h.store.data["results"])

    async def test_B031_event_fault_rolls_back_checkpoint_result_and_messages(
        self,
    ):
        before = deepcopy(self.h.store.data)
        self.h.store.fail_event = True
        with self.assertRaises(RuntimeError):
            await self.run_turn()
        self.assertEqual(before, self.h.store.data)
        self.assertFalse(self.h.completion.notifications)

    async def test_B032_signal_loss_still_keeps_result_replayable(self):
        self.h.signals.drop = self.h.completion.drop = True
        await self.run_turn()
        self.assertIn("request-A", self.h.store.data["results"])
        page = await self.h.events.list_after(
            ACTOR, self.a.conversation_id, None, 10
        )
        self.assertEqual(len(page.items), 3)

    async def test_B033_external_event_applies_fact_and_checkpoint_without_llm(
        self,
    ):
        self.h.add_operation(self.a)
        record = await self.h.workflows.apply_external_event(
            SCOPE, "operation-A", self.h.event()
        )
        self.assertEqual(record.revision, 2)
        self.assertFalse(self.h.runtime.calls)
        page = await self.h.events.list_after(
            ACTOR, record.conversation_id, None, 10
        )
        status = page.items[-1]
        self.assertEqual(status.payload["status_schema"], "1")
        self.assertNotIn("secret", json.dumps(status.model_dump(mode="json")))

    async def test_B034_duplicate_external_event_no_new_job_or_event(self):
        self.h.add_operation(self.a)
        await self.h.workflows.apply_external_event(
            SCOPE, "operation-A", self.h.event()
        )
        before = deepcopy(self.h.store.data)
        await self.h.workflows.apply_external_event(
            SCOPE, "operation-A", self.h.event()
        )
        self.assertEqual(before, self.h.store.data)

    async def test_B035_old_provider_version_does_not_revert_status(self):
        self.h.add_operation(self.a)
        await self.h.workflows.apply_external_event(
            SCOPE, "operation-A", self.h.event(provider_version=3)
        )
        before = deepcopy(self.h.store.data)
        await self.h.workflows.apply_external_event(
            SCOPE,
            "operation-A",
            self.h.event(
                inbox_event_id="inbox-old",
                provider_version=2,
                normalized_status="created",
            ),
        )
        self.assertEqual(before, self.h.store.data)

    async def test_B036_external_event_during_approval_keeps_HITL(
        self,
    ):
        self.h.add_operation(self.a)
        self.h.configure(
            self.a,
            state="awaiting_approval",
            checkpoint=dict(pending_approval_ids=["approval-A"]),
        )
        await self.h.workflows.apply_external_event(
            SCOPE, "operation-A", self.h.event()
        )
        trigger = next(
            p
            for p in self.h.store.data["jobs"].values()
            if p["cause"]["kind"] == "external_event"
        )
        result = await self.h.continuation.run(SCOPE, trigger, "worker-A")
        self.assertEqual(result, "deferred_hitl")
        bundle = await self.h.repo.load(SCOPE, self.a.workflow_id)
        self.assertEqual(bundle.workflow.state, "awaiting_approval")
        self.assertEqual(
            bundle.checkpoint.pending_approval_ids, ("approval-A",)
        )
        self.assertFalse(self.h.runtime.calls)

    async def test_B037_wait_time_does_not_spend_tokens(self):
        self.h.clock.tick(3600)
        bundle = await self.h.repo.load(SCOPE, self.a.workflow_id)
        self.assertEqual(bundle.checkpoint.used_budget.model_turns, 0)
        self.assertFalse(self.h.runtime.calls)

    async def test_B038_external_event_commit_failure_rolls_back_all(self):
        self.h.add_operation(self.a)
        before = deepcopy(self.h.store.data)
        self.h.store.fail_commit = True
        with self.assertRaises(WorkflowConflict):
            await self.h.workflows.apply_external_event(
                SCOPE, "operation-A", self.h.event()
            )
        self.assertEqual(before, self.h.store.data)

    async def test_B039_close_is_idempotent_and_no_duplicate_public_close(
        self,
    ):
        closed = await self.close()
        retry = await self.close()
        self.assertEqual(closed, retry)
        self.assertEqual(
            len(self.h.store.data["events"][self.a.conversation_id]), 2
        )

    async def test_B040_close_wrong_revision_is_rejected(self):
        with self.assertRaises(WorkflowConflict):
            await self.close(expected_revision=2)

    async def test_B041_close_wrong_ticket_is_rejected(self):
        with self.assertRaises(PermissionError):
            await self.close(external_ticket_id="ticket-B")

    async def test_B042_close_does_not_close_other_workflow(self):
        b = await self.h.start("B")
        await self.close()
        self.assertEqual(
            (await self.h.repo.load(SCOPE, b.workflow_id)).workflow.state,
            "accepted",
        )

    async def test_B043_closed_workflow_reply_cannot_reopen(self):
        await self.close()
        with self.assertRaises(WorkflowClosed):
            await self.h.workflows.accept_reply(
                SCOPE,
                ACTOR,
                self.a.audience,
                self.a.workflow_id,
                dict(
                    request_id="reply-A", text="Trả lời", expected_revision=2
                ),
            )

    async def test_B044_closed_turn_uses_no_model(self):
        await self.close()
        self.assertEqual(await self.run_turn(), "closed")
        self.assertFalse(self.h.runtime.calls)

    async def test_B045_pending_operation_requires_explicit_stop_tracking(
        self,
    ):
        self.h.add_operation(self.a)
        with self.assertRaises(WorkflowConflict):
            await self.close(stop_tracking_only=False)
        result = await self.close(stop_tracking_only=True)
        self.assertEqual(result.state, "closed")
        self.assertEqual(
            self.h.store.data["operations"]["operation-A"].job_status, None
        )

    async def test_B046_pending_approval_cannot_be_bypassed_by_stop_tracking(
        self,
    ):
        self.h.configure(
            self.a, checkpoint=dict(pending_approval_ids=["approval-A"])
        )
        with self.assertRaises(WorkflowConflict):
            await self.close(stop_tracking_only=True)

    async def test_B047_close_event_failure_rolls_back_state(self):
        self.h.store.fail_event = True
        with self.assertRaises(RuntimeError):
            await self.close()
        self.assertEqual(
            (await self.h.repo.load(SCOPE, self.a.workflow_id)).workflow.state,
            "accepted",
        )

    async def test_B048_history_paginates_in_order(self):
        await self.run_turn()
        first = await self.h.events.list_after(
            ACTOR, self.a.conversation_id, None, 1
        )
        second = await self.h.events.list_after(
            ACTOR, self.a.conversation_id, first.next_cursor, 1
        )
        self.assertTrue(first.has_more)
        self.assertEqual(
            [first.items[0].sequence, second.items[0].sequence], [1, 2]
        )

    async def test_B049_foreign_cursor_never_reads_from_start(self):
        b = await self.h.start("B")
        foreign = self.h.store.data["events"][b.conversation_id][0].event_id
        with self.assertRaises(EventCursorExpired):
            await self.h.events.list_after(
                ACTOR, self.a.conversation_id, foreign, 10
            )

    async def test_B050_expired_cursor_requires_snapshot(self):
        with self.assertRaises(EventCursorExpired):
            await self.h.events.list_after(
                ACTOR, self.a.conversation_id, "expired", 10
            )
        snapshot = await self.h.events.snapshot(ACTOR, self.a.conversation_id)
        self.assertEqual(
            snapshot["snapshot_cursor"],
            self.h.store.data["events"][self.a.conversation_id][-1].event_id,
        )

    async def test_B051_snapshot_and_history_recheck_revoked_grant(self):
        await self.h.events.snapshot(ACTOR, self.a.conversation_id)
        self.h.auth.revoked = True
        with self.assertRaises(PermissionError):
            await self.h.events.snapshot(ACTOR, self.a.conversation_id)
        with self.assertRaises(PermissionError):
            await self.h.events.list_after(
                ACTOR, self.a.conversation_id, None, 10
            )

    async def test_B052_replay_rejects_repository_cross_conversation_leak(
        self,
    ):
        b = await self.h.start("B")
        event = self.h.store.data["events"][b.conversation_id][0]
        self.h.event_repo.bad_page = EventHistoryPage(
            items=(event,), next_cursor=event.event_id, has_more=False
        )
        with self.assertRaises(PermissionError):
            await self.h.events.list_after(
                ACTOR, self.a.conversation_id, None, 10
            )

    async def test_B053_sse_replays_durable_records_before_wait(self):
        await self.run_turn()
        stream = self.h.events.stream(ACTOR, self.a.conversation_id)
        try:
            frames = [await anext(stream) for _ in range(3)]
            self.assertIn(b"id:", frames[0])
            self.assertIn(b"assistant.message", frames[1])
            self.assertIn(b'"ticket_id":null', frames[0])
        finally:
            await stream.aclose()

    async def test_B054_sse_lost_signal_catches_up_from_log_after_heartbeat(
        self,
    ):
        stream = self.h.events.stream(ACTOR, self.a.conversation_id)
        await anext(stream)
        self.h.signals.drop = True
        self.h.signals.hook = self.run_turn
        try:
            self.assertEqual(await anext(stream), b": heartbeat\n\n")
            self.assertIn(b"assistant.message", await anext(stream))
        finally:
            await stream.aclose()

    async def test_B055_sse_revocation_checked_on_next_replay_page(self):
        stream = self.h.events.stream(ACTOR, self.a.conversation_id)
        await anext(stream)
        self.h.auth.revoked = True
        await anext(stream)
        with self.assertRaises(PermissionError):
            await anext(stream)
        await stream.aclose()

    async def test_B056_injected_uow_does_not_commit_or_notify_early(self):
        tx = Uow(self.h.store)
        await self.h.workflows.close(
            SCOPE, ACTOR, self.a.audience, self.h.close_command(self.a), tx
        )
        self.assertFalse(tx.committed)
        self.assertEqual(
            self.h.store.data["workflows"][self.a.workflow_id].workflow.state,
            "accepted",
        )
        self.assertEqual(len(self.h.signals.notifications), 1)
        await tx.rollback()
        self.assertFalse(tx.callbacks)

    async def test_B057_runtime_does_not_hold_open_transaction(self):
        async def assert_outside(guard):
            self.assertEqual(self.h.store.commits, 1)
            # Independent reads/writes progress while the model is running.
            b = await self.h.start("B")
            self.assertIsNotNone(b)

        self.h.runtime.hook = assert_outside
        await self.run_turn()

    async def test_B058_new_instance_resumes_checkpoint_without_rebuild(
        self,
    ):
        await self.run_turn()
        before = self.h.bootstrap.count
        from agentscope.app.workforce.orchestration.workflows import (
            WorkflowContinuation,
        )
        from fakes import Commands

        worker = WorkflowContinuation(
            self.h.workflows, Commands(), self.h.completion
        )
        self.assertEqual(
            await worker.run(SCOPE, self.trigger, "new-worker"), "duplicate"
        )
        self.assertEqual(self.h.bootstrap.count, before)

    async def test_B059_external_event_after_close_cannot_create_trigger(self):
        self.h.add_operation(self.a)
        await self.close(stop_tracking_only=True)
        before = deepcopy(self.h.store.data)
        await self.h.workflows.apply_external_event(
            SCOPE, "operation-A", self.h.event()
        )
        self.assertEqual(before, self.h.store.data)

    async def test_B060_parallel_claims_run_model_once(self):
        entered, release = asyncio.Event(), asyncio.Event()

        async def pause(guard):
            entered.set()
            await release.wait()

        self.h.runtime.hook = pause
        task = asyncio.create_task(self.run_turn())
        await entered.wait()
        try:
            with self.assertRaises(WorkflowConflict):
                await self.h.continuation.run(SCOPE, self.trigger, "worker-B")
        finally:
            release.set()
        self.assertEqual(await task, "applied")
        self.assertEqual(len(self.h.runtime.calls), 1)


def runtime_mutation(path, value):
    def mutate(plan):
        target = plan
        for field in path[:-1]:
            target = target[field]
        target[path[-1]] = value

    return mutate


RUNTIME_CASES = [
    ("B061", ["candidate", "trigger_id"], "trigger-B"),
    ("B062", ["candidate", "expected_state_revision"], 2),
    ("B063", ["candidate", "checkpoint", "workflow_id"], "workflow-B"),
    ("B064", ["candidate", "checkpoint", "session_refs"], ["session-B"]),
    (
        "B065",
        ["candidate", "checkpoint", "agent_version_pins"],
        [{"agent_id": "agent-1", "version_id": "version-new"}],
    ),
    ("B066", ["candidate", "checkpoint", "protocol_pins"], []),
    (
        "B067",
        ["candidate", "checkpoint", "last_processed_causes"],
        [{"kind": "request", "request_id": "request-B"}],
    ),
    ("B068", ["candidate", "checkpoint", "used_budget", "model_turns"], 101),
    ("B069", ["candidate", "checkpoint", "used_budget", "tool_calls"], 1001),
    (
        "B070",
        ["candidate", "checkpoint", "used_budget", "input_tokens"],
        1_000_001,
    ),
    (
        "B071",
        ["candidate", "result", "messages", 0, "workflow_id"],
        "workflow-B",
    ),
]


for case_id, path, value in RUNTIME_CASES:

    async def scenario(self, path=path, value=value):
        self.assertEqual(await self.run_turn(), "applied")
        self.h = Harness()
        self.a = await self.h.start()
        self.trigger = self.h.trigger(self.a.workflow_id)
        self.h.runtime.mutate = runtime_mutation(path, value)
        with self.assertRaises((WorkflowConflict, ValueError)):
            await self.run_turn()
        self.assertFalse(self.h.store.data["results"])
        self.assertEqual(
            (
                await self.h.repo.load(SCOPE, self.a.workflow_id)
            ).workflow.revision,
            1,
        )

    scenario.__doc__ = f"Reject runtime mutation {'.'.join(map(str, path))}"
    setattr(PhaseB, f"test_{case_id}_runtime_boundary", scenario)


for offset, (field, value) in enumerate(
    [
        ("provider_integration_id", "provider-B"),
        ("protocol_schema_hash", "hash-B"),
        ("external_job_id", "job-B"),
        ("client_reference", "correlation-B"),
    ]
):

    async def scenario(self, field=field, value=value):
        self.h.add_operation(self.a)
        await self.h.workflows.apply_external_event(
            SCOPE, "operation-A", self.h.event()
        )
        before = deepcopy(self.h.store.data)
        changes = dict(
            inbox_event_id="inbox-B", provider_version=2, **{field: value}
        )
        if field == "client_reference":
            changes["external_job_id"] = None
        with self.assertRaises(PermissionError):
            await self.h.workflows.apply_external_event(
                SCOPE, "operation-A", self.h.event(**changes)
            )
        self.assertEqual(before, self.h.store.data)

    setattr(PhaseB, f"test_B{72 + offset:03d}_event_{field}", scenario)


for offset, limit in enumerate([0, -1, 501, True, 1.5]):

    async def scenario(self, limit=limit):
        page = await self.h.events.list_after(
            ACTOR, self.a.conversation_id, None, 10
        )
        self.assertTrue(page.items)
        with self.assertRaises(ValueError):
            await self.h.events.list_after(
                ACTOR, self.a.conversation_id, None, limit
            )

    setattr(PhaseB, f"test_B{76 + offset:03d}_invalid_page_limit", scenario)
