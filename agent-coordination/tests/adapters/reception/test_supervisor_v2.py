"""Real DEV-3 gateway + DEV-1 Supervisor + DEV-2 room; external I/O is faked.

Reuse DEV-1's test harness without editing it. The original mixed event catalog
is retained; V2 replies go through the gateway.
"""
import importlib.util
import sys
import unittest
from copy import deepcopy
from pathlib import Path

from adapters.backend.errors import AdapterError
from adapters.backend.documented_contracts import DocumentedContractValidator
from adapters.reception.reception_gateway import ReceptionGateway
from backend.support import client
from reception.support import Authentication, V2Transport, input_message

TESTS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(TESTS))
spec = importlib.util.spec_from_file_location("dev3_supervisor_test_support", TESTS / "supervisor/conftest.py")
support = importlib.util.module_from_spec(spec)
spec.loader.exec_module(support)


class SupervisorV2Tests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.rig = support.Rig()
        self.transport = V2Transport()
        self.transport.context = self.rig.ctx.model_dump(exclude_none=True)
        self.transport.cancelled = None
        self.rig.service.reception = ReceptionGateway(
            client(self.transport, validator=DocumentedContractValidator()), authentication=Authentication())
        self.resident_required = True
        self.all_done = True
        inspect = self.rig.authority.inspect

        async def authority(state):
            compatible = state.model_copy(deep=True)
            compatible.facts = [dict(report=f.get("message", "Ticket")) for f in state.facts]
            view = await inspect(compatible)
            view.reception_readers = ["A-v1", "B-v1"]
            view.ticket_version = str(int(state.ticket_version or "1") + 1)
            view.resident_approval_required = self.resident_required
            view.all_work_completed = self.all_done
            view.work_order_ids = ["work-order"]
            view.cancellation_confirmed = self.transport.cancelled
            view.cancellation_message = "Backend cancellation result"
            if state.question_draft:
                view.resident_request_type = "information_requested"
                view.resident_request_message = state.question_draft
            elif state.plan:
                view.resident_request_type = "plan_approval_requested"
                p = state.plan.proposal
                view.resident_request_message = "\n".join([p.summary, *p.canonical_steps(),
                    f"{p.cost.amount} {p.cost.currency}" if p.cost else "Chi phí chưa xác định"])
            return view
        self.rig.authority.inspect = authority
        self.proposal = support.proposal.__wrapped__()

    def raw(self, kind="ticket_submitted", *, identity="input-1", version="1"):
        raw = input_message(kind, identity=identity, version=version)
        for key in ("tenant_id", "domain_id", "workspace_id", "ticket_id", "ticket_generation"):
            raw[key] = getattr(self.rig.ctx, key)
        return raw

    async def reply(self, kind, *, identity="reply-1", version=None):
        state = await self.rig.state()
        return await self.rig.service.handle_reception(
            self.raw(kind, identity=identity, version=version or state.ticket_version), "verified-source")

    async def ready(self):
        await self.rig.service.handle_reception(self.raw(), "verified-source")
        self.rig.model.outputs = [dict(kind="open", agent_version_ids=["A-v1", "B-v1"]), self.proposal]
        await self.rig.resume()
        await self.rig.approve("management_plan")
        return await self.rig.resume()

    async def test_real_gateway_plan_management_staff_qc_completed(self):
        from supervisor.models import Publication

        state = await self.ready()
        self.assertEqual(state.phase, "waiting_resident_plan")
        plan = self.transport.delivered[-1]
        self.assertEqual(plan["message_type"], "plan_approval_requested")
        self.assertTrue(all(v in plan["message"] for v in ("45 minutes", "300000", "Resident available")))
        await self.reply("plan_approved")
        state = await self.rig.resume()
        self.assertEqual(state.phase, "executing")
        await self.rig.send("assignment.responded", {**state.assignment, "decision": "accept"})
        await self.rig.send("work.completed", dict(assignment_id=state.assignment["assignment_id"],
            assignment_version=1, result_id="result", result_version=1, summary="Staff done",
            before_file_ids=["before"], after_file_ids=["after"]))
        self.rig.authority.publication = Publication(result_id="result", result_version=1, plan_id="plan-1",
            plan_version=1, summary="QC verified", evidence_file_ids=["after"], final_cost=None, status="ok")
        self.all_done = False
        self.assertEqual((await self.rig.resume()).phase, "waiting_result_validation")
        self.assertFalse(any(m["message_type"] == "completed" for m in self.transport.delivered))
        self.all_done = True
        state = await self.rig.resume()
        self.assertEqual(state.phase, "completed")
        self.assertEqual(self.transport.delivered[-1]["result"]["evidence_ids"], ["after"])
        self.assertEqual([c["type"] for c in self.rig.transport.calls],
                         ["approval.requested", "assignment.offered"])

    async def test_question_does_not_authorize_plan(self):
        await self.rig.service.handle_reception(self.raw(), "verified-source")
        self.rig.model.outputs = [dict(kind="question", question="Where is the leak?")]
        state = await self.rig.resume()
        self.assertEqual(state.phase, "waiting_information")
        with self.assertRaisesRegex(AdapterError, "conflict"):
            await self.reply("plan_approved")
        state = await self.reply("information_provided", identity="information")
        self.assertEqual(state.phase, "planning")
        self.assertFalse(state.approvals)

    async def test_resident_rejection_and_changes_require_new_plan(self):
        for kind in ("plan_rejected", "plan_change_requested"):
            with self.subTest(kind=kind):
                self.setUp()
                state = await self.ready()
                old_version = state.ticket_version
                state = await self.reply(kind)
                self.assertEqual((state.phase, state.revision), ("planning", 2))
                state = await self.reply(kind, identity="same-decision-new-id")
                self.assertEqual(state.revision, 2)
                self.rig.model.outputs = [deepcopy(self.proposal)]
                state = await self.rig.resume()
                self.assertEqual(state.phase, "waiting_management")
                self.assertNotEqual(state.ticket_version, old_version)
                self.transport.current_version = state.ticket_version
                with self.assertRaisesRegex(AdapterError, "stale_version"):
                    await self.reply("plan_approved", identity="old-reply", version=old_version)

    async def test_backend_waiver_skips_resident_but_not_management(self):
        self.resident_required = False
        state = await self.ready()
        self.assertEqual(state.phase, "executing")
        self.assertFalse(any(m["message_type"] == "plan_approval_requested" for m in self.transport.delivered))
        self.assertEqual(self.rig.transport.calls[0]["payload"]["stage"], "management_plan")

    async def test_cancel_waits_for_backend_and_reports_confirmation_or_denial(self):
        for confirmed, phase, output in ((True, "cancelled", "cancelled"),
                                         (False, "waiting_resident_plan", "in_progress")):
            with self.subTest(confirmed=confirmed):
                self.setUp()
                await self.ready()
                self.assertEqual((await self.reply("cancel_requested")).phase, "waiting_cancellation")
                self.assertEqual((await self.rig.resume()).phase, "waiting_cancellation")
                self.transport.cancelled = confirmed
                self.assertEqual((await self.rig.resume()).phase, phase)
                self.assertEqual(self.transport.delivered[-1]["message_type"], output)

    async def test_duplicate_decision_does_not_assign_twice(self):
        await self.ready()
        await self.reply("plan_approved")
        await self.rig.resume()
        await self.reply("plan_approved", identity="new-id")
        await self.rig.resume()
        self.assertEqual(len(self.transport.decisions), 1)
        self.assertEqual(len([c for c in self.rig.transport.calls if c["type"] == "assignment.offered"]), 1)

    async def test_lost_ack_reconciles_same_wire_without_second_delivery(self):
        from supervisor.models import Reconciliation

        await self.rig.service.handle_reception(self.raw(), "verified-source")
        original_post = self.transport.post

        async def lost_ack(*args, **kwargs):
            await original_post(*args, **kwargs)
            raise TimeoutError("response lost")

        self.transport.post = lost_ack
        state = await self.rig.resume()
        self.assertEqual(state.action.status, "unknown")
        self.transport.post = original_post
        self.rig.authority.resolution = Reconciliation(outcome="not_applied")
        self.rig.model.outputs = [dict(kind="question", question="Where is the leak?")]
        await self.rig.resume()
        self.assertEqual(self.transport.calls[1][2], self.transport.calls[2][2])
        self.assertEqual(len([m for m in self.transport.delivered if m["message_type"] == "accepted"]), 1)
