import asyncio
import logging

import pytest

from awp.intake.service import IntakeError
from awp_vinhomes import DeliveryRejected, Unavailable, VinhomesPack, pack as pack_module
from fake_vinhomes import TICKET, stack, submitted
from helpers import ATTRS, result

run = asyncio.run


class FakeIntake:
    """The part of IntakeService the pack uses, with the same dedupe and the same refusals."""

    def __init__(self) -> None:
        self.cases: dict[str, object] = {}
        self.seen: set[str] = set()
        self.submits: list = []
        self.follow_ups: list = []
        self.fail_next: list[Exception] = []

    async def submit(self, tenant, domain, intake):
        if self.fail_next:
            raise self.fail_next.pop(0)
        replayed = intake.external_ref in self.cases
        self.seen.add(intake.message_id)
        if not replayed:
            self.cases[intake.external_ref] = intake
            self.submits.append(intake)
        return {"case_id": "case_1", "status": "open", "replayed": replayed}

    async def follow_up(self, tenant, domain, external_ref, msg):
        if external_ref not in self.cases:
            raise IntakeError(404, "no such case")
        if msg.message_id in self.seen:
            return {"replayed": True}
        self.seen.add(msg.message_id)
        self.follow_ups.append((external_ref, msg))
        return {"replayed": False}


async def started(client, tmp_path, intake=None, **kw):
    pack = VinhomesPack(client, cursor_file=tmp_path / "cursor.json", poll_seconds=0.02, start_delay=0, **kw)
    pack.tenant, pack.intake = "t1", intake or FakeIntake()
    return pack


def test_a_new_ticket_and_its_follow_ups_reach_the_core_once(tmp_path):
    async def go():
        async with stack() as (state, client):
            state.messages = [submitted(1), submitted(2, "information_provided", message="Nhà có người")]
            pack = await started(client, tmp_path)
            assert await pack.poll_once() is False
            assert [c.external_ref for c in pack.intake.submits] == [TICKET]
            assert [(r, m.kind) for r, m in pack.intake.follow_ups] == [(TICKET, "information_provided")]
            assert [r["message_type"] for r in state.results] == ["accepted"]  # the receipt
            cursor = pack.cursor
            assert cursor and (tmp_path / "cursor.json").exists()
            # nothing new: nothing happens
            await pack.poll_once()
            assert len(pack.intake.submits) == 1 and pack.cursor == cursor
            # a restart keeps the place
            again = await started(client, tmp_path)
            assert again.cursor == cursor
            await again.poll_once()
            assert again.intake.submits == []
    run(go())


def test_a_lost_cursor_costs_a_re_read_not_a_duplicate(tmp_path):
    async def go():
        async with stack() as (state, client):
            state.messages = [submitted(1), submitted(2, "plan_approved")]
            intake = FakeIntake()
            await (await started(client, tmp_path, intake)).poll_once()
            (tmp_path / "cursor.json").unlink()
            fresh = await started(client, tmp_path, intake)  # same core (it remembers message ids)
            assert fresh.cursor is None
            await fresh.poll_once()
            assert len(intake.submits) == 1 and len(intake.follow_ups) == 1
            assert [r["message_type"] for r in state.results] == ["accepted"]  # no second receipt
    run(go())


def test_pages_are_followed_until_the_inbox_is_empty(tmp_path):
    async def go():
        async with stack() as (state, client):
            state.messages = [submitted(1)] + [submitted(i, "information_provided") for i in range(2, 6)]
            pack = await started(client, tmp_path, page_size=2)
            pages = 0
            while True:
                pages += 1
                if not await pack.poll_once():
                    break
            assert len(pack.intake.follow_ups) == 4 and pages == 3
    run(go())


def test_a_transient_failure_keeps_the_cursor_and_loses_nothing(tmp_path):
    async def go():
        async with stack() as (state, client):
            state.messages = [submitted(1), submitted(2, "information_provided")]
            intake = FakeIntake()
            intake.fail_next = [IntakeError(503, "no model is configured")]
            pack = await started(client, tmp_path, intake)
            with pytest.raises(IntakeError):
                await pack.poll_once()
            assert pack.cursor is None and intake.submits == []
            await pack.poll_once()  # the model came back
            assert len(intake.submits) == 1 and len(intake.follow_ups) == 1
            # the domain itself being down is the same story
            state.messages.append(submitted(3, "plan_approved"))
            state.fail = [503]
            with pytest.raises(Unavailable):
                await pack.poll_once()
            await pack.poll_once()
            assert len(intake.follow_ups) == 2
    run(go())


def test_messages_that_can_never_be_handled_do_not_block_the_ones_behind(tmp_path, caplog):
    async def go():
        async with stack() as (state, client):
            broken = submitted(2, "information_provided")
            del broken["request"]
            other = submitted(3, "plan_approved", ticket="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")  # no such case
            state.messages = [submitted(1), broken, other, submitted(4, "cancel_requested")]
            intake = FakeIntake()
            pack = await started(client, tmp_path, intake)
            with caplog.at_level(logging.INFO, logger="awp.vinhomes"):
                await pack.poll_once()
            assert [m.kind for _r, m in intake.follow_ups] == ["cancel_requested"]
            assert pack.cursor is not None  # the page was finished, not retried forever
            assert any("skipping message m-2" in r.message for r in caplog.records)
    run(go())


def test_a_follow_up_for_a_finished_case_is_dropped(tmp_path):
    async def go():
        async with stack() as (state, client):
            state.messages = [submitted(1), submitted(2, "plan_approved")]
            intake = FakeIntake()

            async def closed(*a):
                raise IntakeError(409, "case is finalized")
            intake.follow_up = closed
            pack = await started(client, tmp_path, intake)
            await pack.poll_once()
            assert pack.cursor is not None
    run(go())


def test_a_failed_receipt_does_not_lose_the_ticket(tmp_path):
    async def go():
        async with stack() as (state, client):
            state.status = "closed"  # the domain refuses "accepted" for a final ticket
            state.messages = [submitted(1)]
            pack = await started(client, tmp_path)
            await pack.poll_once()
            assert len(pack.intake.submits) == 1 and state.results == []
    run(go())


def test_the_loop_runs_backs_off_and_stops_cleanly(tmp_path, monkeypatch):
    monkeypatch.setattr(pack_module, "MIN_BACKOFF", 0.02)

    async def go():
        async with stack() as (state, client):
            intake = FakeIntake()
            pack = VinhomesPack(client, cursor_file=tmp_path / "c.json", poll_seconds=0.02, start_delay=0)
            state.fail = [503, 503]  # the first two reads fail
            state.messages = [submitted(1)]
            await pack.start(None, intake, "t1")
            with pytest.raises(RuntimeError):  # one tenant per pack
                await pack.start(None, intake, "t2")
            for _ in range(200):
                if intake.submits:
                    break
                await asyncio.sleep(0.02)
            assert len(intake.submits) == 1
            state.messages.append(submitted(2, "information_provided"))  # arrives later
            for _ in range(200):
                if intake.follow_ups:
                    break
                await asyncio.sleep(0.02)
            assert len(intake.follow_ups) == 1
            task = pack._task
            await pack.stop()
            assert task.done() and pack._task is None
            await pack.stop()  # stopping twice is harmless
    run(go())


# ---- results ---------------------------------------------------------------------
CASE = {"id": "case_abc", "domain": "vinhomes", "external_ref": TICKET, "intake": {"attributes": ATTRS}}


async def deliver(client, tmp_path, **kw):
    pack = await started(client, tmp_path)
    await pack.deliver_result(CASE, result(**kw))
    return pack


def test_resolved_on_an_open_ticket_goes_back_as_in_progress(tmp_path):
    async def go():
        async with stack() as (state, client):
            pack = await started(client, tmp_path)
            await pack.deliver_result(CASE, result())
            await pack.deliver_result(CASE, result())  # the core may deliver twice
            assert [(r["message_type"], r["ticket_version"]) for r in state.results] == [("in_progress", "7")]
            assert state.result_posts == 2
    run(go())


def test_resolved_on_a_resolved_ticket_is_completed(tmp_path):
    async def go():
        async with stack() as (state, client):
            state.status = "resolved"
            await deliver(client, tmp_path)
            assert [r["message_type"] for r in state.results] == ["completed"]
    run(go())


def test_a_completion_the_domain_does_not_accept_is_kept_not_downgraded(tmp_path):
    async def go():
        async with stack() as (state, client):
            state.status, state.work_incomplete = "resolved", True
            with pytest.raises(DeliveryRejected) as e:
                await deliver(client, tmp_path)
            assert "work orders" in str(e.value)
            assert state.result_posts == 1 and state.results == []
    run(go())


def test_every_other_outcome_is_a_valid_message(tmp_path):
    async def go():
        async with stack() as (state, client):
            await deliver(client, tmp_path, outcome="needs_human", answer="Cần BQL.", unknowns=["thiếu giờ"])
            await deliver(client, tmp_path, outcome="cannot_resolve", answer="")
            await deliver(client, tmp_path, outcome="failed", answer="Mình chưa có thông tin.")
            assert [(r["message_type"], r["error"]["code"]) for r in state.results] == [
                ("failed", "NEEDS_HUMAN_REVIEW"), ("failed", "CANNOT_RESOLVE"), ("failed", "PLATFORM_ERROR")]
            state.status = "cancelled"
            await deliver(client, tmp_path)
            assert state.results[-1]["message_type"] == "cancelled"
    run(go())


def test_a_ticket_that_changed_underneath_is_read_again_and_sent_once_more(tmp_path):
    async def go():
        async with stack() as (state, client):
            state.bump_after_get = True  # version 7 is read, then the ticket becomes 8
            await deliver(client, tmp_path)
            assert state.result_posts == 2
            assert [r["ticket_version"] for r in state.results] == ["8"]
    run(go())


def test_a_conflict_that_is_not_staleness_is_not_retried(tmp_path):
    async def go():
        async with stack() as (state, client):
            state.force_409 = "something else is wrong"
            with pytest.raises(DeliveryRejected) as e:
                await deliver(client, tmp_path)
            assert "something else is wrong" in str(e.value)
            assert state.result_posts == 1 and state.results == []
    run(go())


def test_a_result_for_an_older_round_of_the_ticket_is_dropped(tmp_path):
    async def go():
        async with stack() as (state, client):
            state.generation = 1  # reopened since this case started
            await deliver(client, tmp_path)
            assert state.result_posts == 0
    run(go())


def test_temporary_trouble_raises_so_the_core_tries_again(tmp_path):
    async def go():
        async with stack() as (state, client):
            state.fail = [503]
            with pytest.raises(Unavailable):
                await deliver(client, tmp_path)
            state.fail = []
            await deliver(client, tmp_path)
            assert len(state.results) == 1
            # trouble on the POST itself
            state.status = "open"
            state.messages = []
            pack = await started(client, tmp_path)
            state.fail = []
            real = client.post_result

            async def down(*a, **k):
                raise Unavailable(503, "UNAVAILABLE", "try later", retryable=True)
            client.post_result = down
            with pytest.raises(Unavailable):
                await pack.deliver_result(CASE, result("needs_human"))
            client.post_result = real
    run(go())


def test_a_case_without_a_ticket_is_rejected_loudly(tmp_path):
    async def go():
        async with stack() as (state, client):
            pack = await started(client, tmp_path)
            with pytest.raises(DeliveryRejected):
                await pack.deliver_result({"id": "x", "intake": {}}, result())
    run(go())


def test_the_pack_hands_the_core_what_it_asks_for(tmp_path):
    async def go():
        async with stack() as (state, client):
            pack = await started(client, tmp_path)
            assert pack.domain == "vinhomes" and pack.default_leader == "vinhomes_supervisor"
            keys = {p.key for p in pack.profiles()}
            leader = next(p for p in pack.profiles() if p.role == "leader")
            assert leader.key == pack.default_leader and set(leader.team) <= keys
            granted = {t for p in pack.profiles() for t in p.tools_allow}
            tools = pack.tools(None, None)
            assert granted == {t.name for t in tools}
            assert pack.rules().safe_reply
    run(go())
