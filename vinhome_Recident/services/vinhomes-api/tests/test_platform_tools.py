"""The tools of the platform's coordinator, staff progress and the acceptance on site
(docs/domain/NOI_WORKFORCE_V1.md sections 5.5, 6 and 7), on the generated test world.

The service functions are called directly, as the API's restricted role; the MCP server is called over HTTP by the
MCP client the platform uses. FakePlatform (test_platform_bridge) stands for the platform.
"""

import asyncio
import json
import re
import socket
import threading
import time
from datetime import datetime, timedelta
from uuid import UUID, uuid4

import httpx
import pytest
import uvicorn
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from test_domain_database import operation
from test_integration_auth import person
from test_knowledge import DOCUMENTS, write
from test_platform_bridge import FakePlatform, chat, commands, link, say, sync
from test_platform_bridge import on as on  # noqa: PLC0414 -- pytest fixture export
from test_platform_bridge import turns as turns  # noqa: PLC0414 -- pytest fixture export
from test_resident_contract import CATEGORY, TENANT, image, key, sql
from test_resident_contract import database as database  # noqa: PLC0414 -- pytest fixture export
from test_staff_dispatch import accept, advance, approved_order, offer

from vinhomes_api import knowledge
from vinhomes_api import platform_work as work
from vinhomes_api.jobs import sweep_tenant
from vinhomes_api.main import create_app
from vinhomes_api.mock_data import CAT_SEC, build
from vinhomes_api.platform import VN, link_ticket
from vinhomes_api.v3_config import V3Settings

AN, CHAU, MINH, HOA, TECH = "mock-an", "mock-chau", "mock-minh", "mock-hoa", "local-v3-technical"
TOKEN = "mcp-token-of-the-test-0123456789abcdef"
WHEN = r"\d\d:\d\d \d\d/\d\d/\d{4}"


@pytest.fixture(scope="module", autouse=True)
def world(database, tmp_path_factory):
    asyncio.run(build(database["admin"], "test", 42))
    asyncio.run(knowledge.load(database["admin"], write(tmp_path_factory.mktemp("knowledge"), DOCUMENTS), str(TENANT)))
    # The jobs of the generated history are not this test's: every technician starts with nothing in hand.
    sql(database, "update work_assignments set status='cancelled',ended_at=now() where status in ('offered','accepted') returning id")
    sql(database, "update staff_profiles set max_concurrent_jobs=3 returning id")


@pytest.fixture(autouse=True)
def words_only(monkeypatch):
    monkeypatch.delenv("VINHOMES_API_EMBEDDING_API_KEY", raising=False)


@pytest.fixture(autouse=True)
def unhurried(database):
    """Each test starts with the resident's message allowance of a new minute (the tests here write as one person)."""
    sql(database, "update messages set created_at=created_at-interval '2 minutes' where sender_kind='user' and created_at>now()-interval '2 minutes' returning id")


def put_down(database, job):
    """The technician no longer holds this job: the tests after this one find them free."""
    sql(database, "update work_assignments set status='cancelled',ended_at=now() where work_order_id=$1 and status in ('offered','accepted') returning id", UUID(job))
    sql(database, "update work_orders set status='cancelled' where id=$1 returning id", UUID(job))


def on_shift(database, *users):
    """Exactly these staff members have a shift running now (offers go only to people on shift)."""
    sql(database, "update staff_shifts set status='cancelled' returning id")
    for user in users:
        assert sql(database, """update staff_shifts set status='available',starts_at=now()-interval '1 hour',ends_at=now()+interval '8 hours'
            where id=(select s.id from staff_shifts s join staff_profiles p on p.id=s.staff_id where p.user_id=$1 order by s.starts_at limit 1)
            returning id""", user)


def call(database, function, *args):
    """One tool call: its own transaction, scoped to the tenant, as the API's database role."""
    async def run():
        engine = create_async_engine(database["runtime"])
        try:
            async with engine.begin() as db:
                await db.execute(text("select set_config('app.tenant_id',:tenant,true)"), {"tenant": str(TENANT)})
                return await function(db, *args)
        finally:
            await engine.dispose()
    answer = asyncio.run(run())
    if function is not sweep_tenant:
        # Nothing a tool says carries the internal code or a phone number.
        said = json.dumps(answer, ensure_ascii=False, default=str)
        assert "VH-" not in said and "+84" not in said and not re.search(r"\b0\d{9}\b", said), said
        assert not {"id", "job_id", "operation_id"} & set(answer)
    return answer


def ref():
    return "cr_" + uuid4().hex  # as the platform makes them


def decide(database, ticket, approval, approved, note):
    """The resident answers a quote or a result themselves, in their app (the only way a quote is answered)."""
    with person(database, AN) as c:
        version = sql(database, "select version from tickets where id=$1", UUID(ticket))[0]["version"]
        return c.post(f"/resident/approvals/{approval}/decision", headers=key(), json={"version": version, "approved": approved, "note": note})


def hand_over(c, words="Đèn phòng khách không sáng", plan=False):
    """Reception files the request from the chat; with the bridge on, the ticket is linked to the platform."""
    place = operation(c, "get_verified_resident_context")[0]["residences"][0]
    channel = c.post("/resident/chats", json={"title": "Công cụ của trợ lý"}).json()["id"]
    message = say(c, channel, words)
    draft, _ = operation(c, "create_ticket_draft", {
        "channel_id": channel, "domain_id": place["domain_id"], "building_id": place["building_id"],
        "unit_id": place["unit_id"], "category_id": CATEGORY})
    target = {"channel_id": channel, "draft_id": draft["draftId"]}
    operation(c, "update_ticket_incident", {**target, "fields": {"source_message_id": message, "facts": [
        {"key": "symptom", "value": "không sáng", "source": "customer_report", "source_message_id": message},
        {"key": "item", "value": "đèn phòng khách", "source": "customer_report", "source_message_id": message}]}})
    operation(c, "submit_ticket_assessment", {**target, "assessment": {"priority": "high", "severity": "minor", "reason": "Cư dân báo"}})
    handoff, _ = operation(c, "handoff_ticket", {**target, "plan_required": plan})
    assert handoff["accepted"], handoff
    return channel, handoff["ticket"]["id"]


def started(database, fake, user=AN, **how):
    """A request handed over and accepted by the platform: the link is open and progress is reported."""
    with person(database, user) as c:
        channel, ticket = hand_over(c, **how)
    sync(database, fake)
    assert link(database, ticket)["status"] == "open"
    return channel, ticket


def events(database, ticket, *kinds):
    rows = sql(database, "select event_type,payload,actor_kind,actor_client_id,actor_user_id from ticket_events where ticket_id=$1 order by seq", UUID(ticket))
    return [{**row, "payload": json.loads(row["payload"])} for row in rows if not kinds or row["event_type"] in kinds]


def outbox(database, ticket):
    rows = sql(database, "select * from platform_outbox where ticket_id=$1 order by provider_version,event_id", UUID(ticket))
    return [{**row, "data": json.loads(row["data"])} for row in rows]


def offers(database, work_order):
    return sql(database, """select a.id,a.status,a.eta_at,p.user_id,u.name from work_assignments a join staff_profiles p on p.id=a.staff_id
        join users u on u.id=p.user_id where a.work_order_id=$1 order by a.created_at,a.id""", UUID(work_order))


def refuse(database, work_order):
    """Whoever holds the offer says no, in the staff app."""
    offered = next(o for o in offers(database, work_order) if o["status"] == "offered")
    with person(database, offered["user_id"]) as worker:
        said = worker.post(f"/assignments/{offered['id']}/response", json={"status": "rejected", "rejection_reason": "Đang bận việc khác"})
        assert said.status_code == 200, said.text
    return offered["user_id"]


def photo(worker, ticket, order, assignment, purpose):
    # The file store has no "verification" kind; the evidence record carries it (as the staff app does).
    uploaded = worker.post(f"/tickets/{ticket}/files", content=image(), headers={"Content-Type": "application/octet-stream"},
                           params={"filename": purpose + ".png", "mimeType": "image/png", "purpose": "other" if purpose == "verification" else purpose})
    assert uploaded.status_code == 201, uploaded.text
    attached = worker.post(f"/tickets/{ticket}/evidence", json={
        "file_id": uploaded.json()["fileId"], "work_order_id": order, "assignment_id": assignment, "purpose": purpose})
    assert attached.status_code == 201, attached.text


# ---- look-ups ---------------------------------------------------------------------------------------------------------

def test_look_ups_read_the_ticket_the_home_and_the_documents_of_its_zone(database, on):
    on_shift(database, HOA)
    with person(database, AN) as c:
        channel, ticket = hand_over(c, "Đèn phòng khách không sáng từ tối qua")
    secret = sql(database, "select t.code,t.contact_phone,t.contact_name,u.phone_e164,u.name from tickets t join users u on u.id=t.requester_user_id where t.id=$1", UUID(ticket))[0]

    seen = call(database, work.ticket_get, ticket)
    # An ordinary state is "ticket_status": the platform takes a top-level "status" as proof that the work is done.
    assert seen["ticket_status"] in ("open", "triaging") and "status" not in seen
    assert (seen["unit"], seen["priority"], seen["work_orders"], seen["quote"], seen["completion_request"]) == ("S1.01-1201", "high", [], None, None)
    assert (seen["is_emergency"], seen["severity"], seen["resident_photos"]) == (False, "minor", 0)
    assert "Đèn phòng khách không sáng từ tối qua" in seen["description"] and re.fullmatch(WHEN, seen["created_at"])
    assert seen["milestones"][0]["what"] == "Tiếp nhận yêu cầu" and re.fullmatch(WHEN, seen["milestones"][0]["at"])
    assert secret["code"] not in json.dumps(seen) and secret["contact_phone"] not in json.dumps(seen)

    who = call(database, work.resident_context, ticket)
    assert who["resident"] == {"name": secret["name"], "address_as": "anh/chị " + secret["name"].split()[-1], "relation_to_home": "chủ hộ"}
    assert who["home"]["unit"] == "S1.01-1201" and who["home"]["building"] and who["home"]["zone"]
    assert secret["phone_e164"] not in json.dumps(who)

    # Documents: what holds for the whole site and for An's own tower; never another zone's, never the staff's.
    found = call(database, work.knowledge_search, ticket, "bể bơi mở cửa mấy giờ")
    assert found["found"] and found["passages"][0]["document"] == "Giờ mở cửa bể bơi" and "6 giờ đến 21 giờ" in found["passages"][0]["text"]
    assert all(p["document"] != "Quy trình vệ sinh bể bơi" for p in found["passages"])
    assert call(database, work.knowledge_search, ticket, "thang bộ thoát hiểm ở đâu")["passages"][0]["document"] == "Thoát hiểm tòa S1.01"
    assert call(database, work.knowledge_search, ticket, "cổng khu biệt thự Hải Âu đóng lúc mấy giờ")["passages"] == []
    with pytest.raises(work.Refused):
        call(database, work.knowledge_search, ticket, "   ")

    limits = call(database, work.rules, ticket)
    assert set(limits) == {"visits", "cards", "amenities"} and limits["cards"]["resident"] > 0

    owed = sql(database, """select coalesce(sum(n.total_amount-n.paid_amount),0) as owed from debit_notes n join units u on u.id=n.unit_id
        where u.code='S1.01-1201' and n.status in ('issued','partially_paid','overdue')""")[0]["owed"]
    balance = call(database, work.debts, ticket, "balance")
    assert balance["unit"] == "S1.01-1201" and balance["outstanding"] == owed > 0 and balance["currency"] == "VND"
    notes = call(database, work.debts, ticket, "open")
    assert notes["notes"] and all("id" not in note and note["doc_no"] for note in notes["notes"])
    with pytest.raises(work.Refused, match="view"):
        call(database, work.debts, ticket, "everything")
    # A member of the household does not answer for the home's money (golden scenario G01), through the tool either.
    with person(database, CHAU) as c:
        _, hers = hand_over(c)
    with pytest.raises(work.Refused, match="chủ hộ"):
        call(database, work.debts, hers, "balance")
    assert call(database, work.resident_context, hers)["resident"]["relation_to_home"] == "thành viên trong hộ"

    free = call(database, work.staff_available, ticket)
    hoa = sql(database, "select p.id,u.name from staff_profiles p join users u on u.id=p.user_id where p.user_id=$1", HOA)[0]
    assert [(s["staff_id"], s["name"], s["active_jobs"]) for s in free["staff"]] == [(str(hoa["id"]), hoa["name"], 0)]
    assert re.fullmatch(WHEN, free["staff"][0]["shift_ends_at"])
    on_shift(database)
    assert call(database, work.staff_available, ticket)["staff"] == []


def test_a_ticket_the_platform_is_not_working_on_is_refused_by_every_tool(database, on, monkeypatch):
    with person(database, AN) as c:
        _, linked = hand_over(c)
        monkeypatch.delenv("VINHOMES_API_PLATFORM_URL")
        _, never = hand_over(c)   # filed while the bridge was off: no link
    stranger = str(uuid4())
    sql(database, "update platform_links set status='closed' where ticket_id=$1 returning ticket_id", UUID(linked))
    looks = [(work.ticket_get,), (work.resident_context,), (work.knowledge_search, "bể bơi"), (work.rules,), (work.debts, "balance"), (work.staff_available,)]
    acts = [(work.dispatch, "Thay bóng đèn", None, None),
            (work.reschedule, "2030-01-01T09:00:00+07:00", "bận"), (work.cancel, "không cần nữa"), (work.add_note, "gọi trước khi đến")]
    for ticket in (never, linked, stranger, "VH-ABC123", ""):
        for function, *more in looks:
            with pytest.raises(work.Refused, match="ticket_id"):
                call(database, function, ticket, *more)
        for function, *more in acts:
            answer = call(database, function, ticket, *more, ref())
            assert answer["status"] == "failed" and "ticket_id" in answer["reason"]
    assert sql(database, "select count(*) as n from work_orders where ticket_id=any($1::uuid[])", [UUID(never), UUID(linked)]) == [{"n": 0}]
    assert sql(database, "select count(*) as n from platform_operations where ticket_id=any($1::uuid[])", [UUID(never), UUID(linked)]) == [{"n": 0}]
    # A link that failed is over as well; one that waits for the platform's first answer is being worked on.
    sql(database, "update platform_links set status='failed' where ticket_id=$1 returning ticket_id", UUID(linked))
    with pytest.raises(work.Refused):
        call(database, work.ticket_get, linked)
    sql(database, "update platform_links set status='pending' where ticket_id=$1 returning ticket_id", UUID(linked))
    assert call(database, work.ticket_get, linked)["ticket_status"]
    # An action without the platform's reference is not an action of the platform.
    assert call(database, work.add_note, linked, "x", "")["status"] == "failed"


# ---- the whole job ----------------------------------------------------------------------------------------------------

def test_a_job_from_dispatch_to_the_residents_confirmation_is_reported_in_order(database, on):
    fake = FakePlatform()
    on_shift(database, HOA)
    channel, ticket = started(database, fake)
    dispatch = ref()
    answer = call(database, work.dispatch, ticket, "Thay bóng đèn phòng khách", None, None, dispatch)
    assert answer["status"] == "pending" and answer["offered_to"] == "Kỹ thuật viên Hoa" and re.fullmatch(WHEN, answer["offer_expires_at"])
    job = answer["external_job_id"]
    # The same reference again: the stored answer, and nothing done twice.
    assert call(database, work.dispatch, ticket, "Thay bóng đèn phòng khách", None, None, dispatch) == answer
    # The reference of one call answers that call only: another tool gets no stored answer and does nothing.
    stray = call(database, work.add_note, ticket, "Gọi trước khi đến", dispatch)
    assert stray["status"] == "failed" and "external_job_id" not in stray and events(database, ticket, "ticket.note_added") == []
    assert sql(database, "select id,status,description from work_orders where ticket_id=$1", UUID(ticket)) == [
        {"id": UUID(job), "status": "offered", "description": "Thay bóng đèn phòng khách"}]
    assert len(offers(database, job)) == 1 and len(events(database, ticket, "work_order.created")) == 1
    [stored] = sql(database, "select tool,work_order_id,answer from platform_operations where client_reference=$1", dispatch)
    assert (stored["tool"], stored["work_order_id"], json.loads(stored["answer"])) == ("vh_work_order_dispatch", UUID(job), answer)
    assert sql(database, "select status from tickets where id=$1", UUID(ticket)) == [{"status": "assigned"}]
    # The coordinator acts as the platform's client, not as a person.
    assert [(e["actor_kind"], e["actor_client_id"], e["actor_user_id"]) for e in events(database, ticket, "work_order.created", "work_order.offered")] == [
        ("agent", "platform", None)] * 2
    # A second job while one is open is refused, with words.
    second = call(database, work.dispatch, ticket, "Thay thêm công tắc", None, None, ref())
    assert second["status"] == "failed" and "chưa kết thúc" in second["reason"] and "external_job_id" not in second

    with person(database, HOA) as worker:
        mine = next(j for j in worker.get("/my-work-orders").json()["items"] if j["id"] == job)
        order = accept(worker, {"id": mine["assignment_id"], "work_order_id": job})
        for status in ("en_route", "arrived"):
            moved = advance(worker, order, status)
            assert moved.status_code == 200, moved.text
            order = moved.json()
        proposed = worker.post(f"/work-orders/{job}/repair-proposal", json={
            "version": order["version"], "note": "Thay bóng LED mới, nội bộ: gọi 0901234567", "labor_cost": 50000, "warranty_months": 3,
            "lines": [{"name": "Bóng LED", "quantity": "2", "unit": "cái", "unit_price": 75000}]})
        assert proposed.status_code == 201, proposed.text

    seen = call(database, work.ticket_get, ticket)   # `call` also checks the staff member's note with a phone number stays out
    quote = seen["quote"]
    assert quote == {"warranty_months": 3, "total": 200000, "items": [
        {"label": "Bóng LED (2 cái)", "amount": 150000}, {"label": "Tiền công", "amount": 50000}]}
    [shown] = seen["work_orders"]
    assert (shown["work_status"], shown["staff_name"], shown["offer"]) == ("awaiting_approval", "Kỹ thuật viên Hoa", "accepted")
    assert re.fullmatch(WHEN, shown["eta"]) and re.fullmatch(WHEN, shown["arrived_at"]) and shown["acceptance_report"] is None

    # The quote is a card in the resident's chat. The technician cannot answer it for the resident on their own
    # device (the on-site answer of requests the platform does not hold), and the staff app is told so.
    with person(database, HOA) as worker:
        waiting = worker.get(f"/work-orders/{job}").json()
        assert waiting["quoteInChat"] is True
        for approved in (True, False):
            onsite = worker.post(f"/work-orders/{job}/repair-proposal/onsite-decision", json={"version": waiting["workOrder"]["version"], "approved": approved})
            assert onsite.status_code == 409 and "own chat" in onsite.text
    assert sql(database, "select status,decided_by from work_approvals where id=$1", UUID(proposed.json()["id"])) == [{"status": "pending", "decided_by": None}]
    assert events(database, ticket, "work_approval.decided") == []
    sync(database, fake)
    [card] = [m["platform"] for m in chat(database, channel) if "platform" in m]
    assert (card["kind"], card["approval_id"], card["total"]) == ("quote", proposed.json()["id"], 200000)
    # The resident taps "Đồng ý" on the card: their own answer, through their own session.
    assert decide(database, ticket, card["approval_id"], True, "Tôi đồng ý").status_code == 200
    decided = events(database, ticket, "work_approval.decided")
    assert len(decided) == 1 and (decided[0]["actor_kind"], decided[0]["actor_client_id"], decided[0]["actor_user_id"]) == ("human", None, AN)
    assert sql(database, "select status,decided_by,decision_note from work_approvals where id=$1", UUID(card["approval_id"])) == [
        {"status": "approved", "decided_by": AN, "decision_note": "Tôi đồng ý"}]
    assert call(database, work.ticket_get, ticket)["quote"] is None

    with person(database, HOA) as worker:
        order = worker.get(f"/work-orders/{job}").json()["workOrder"]
        started_ = advance(worker, order, "in_progress")
        assert started_.status_code == 200, started_.text
        accept_at = f"/work-orders/{job}/onsite-acceptance"
        said = {"version": started_.json()["version"], "note": "Đã thay 2 bóng LED, đèn sáng tốt"}
        assert worker.post(accept_at, json=said).status_code == 409   # not finished yet
        for purpose in ("before", "after"):
            photo(worker, ticket, job, mine["assignment_id"], purpose)
        done = advance(worker, started_.json(), "completed")
        assert done.status_code == 200, done.text
        said["version"] = done.json()["version"]
        # Finished, not yet accepted: the request is not resolved and nothing says the work is proven done.
        waiting = call(database, work.ticket_get, ticket)
        assert waiting["ticket_status"] == "in_progress" and "status" not in waiting and waiting["completion_request"] is None
        # Work that was done, with an agreed quote, is not thrown away by a word in the chat.
        late = call(database, work.cancel, ticket, "Cư dân đổi ý", ref())
        assert late["status"] == "failed" and "không hủy được" in late["reason"]
        assert sql(database, "select t.status as ticket,w.status as work from tickets t join work_orders w on w.ticket_id=t.id where t.id=$1", UUID(ticket)) == [
            {"ticket": "in_progress", "work": "completed"}]
        assert [c["kind"] for c in commands(database, ticket)] == ["start_workflow"]

        # The acceptance report (5.5 step 2): only the person who did the job, on the current completed job, with a photo of the result.
        with person(database, MINH) as manager, person(database, TECH) as colleague:
            assert manager.post(accept_at, json=said).status_code == 403
            assert colleague.post(accept_at, json=said).status_code in (403, 404)
        # The technician reports; they cannot state that the resident accepted, nor in whose name.
        assert worker.post(accept_at, json={**said, "accepted": True}).status_code == 422
        assert worker.post(accept_at, json={**said, "resident_name": "Nguyễn Văn An"}).status_code == 422
        assert worker.post(accept_at, json={**said, "version": said["version"] - 1}).status_code == 409
        sql(database, "update evidence_items set status='withdrawn' where work_order_id=$1 and purpose='after' returning id", UUID(job))
        missing = worker.post(accept_at, json=said)
        assert missing.status_code == 409 and "photo" in missing.text
        sql(database, "update evidence_items set status='active' where work_order_id=$1 and purpose='after' returning id", UUID(job))
        assert sql(database, "select count(*) as n from vh_qc_results where work_order_id=$1", UUID(job)) == [{"n": 0}]
        # The acceptance screen adds its own photo, after the job was reported done.
        photo(worker, ticket, job, mine["assignment_id"], "verification")
        accepted = worker.post(accept_at, json=said)
        assert accepted.status_code == 201, accepted.text
        assert set(accepted.json()) == {"id", "work_order_id", "outcome", "checked_at", "ticket_status"}
        assert (accepted.json()["work_order_id"], accepted.json()["ticket_status"]) == (job, "resolved")
        assert worker.post(accept_at, json=said).status_code == 409   # once

    # Kept as what it is: the report of the technician who did the job, with their note and how many photos of the
    # result. Nothing says the resident checked. Then the usual publication: resolved, and the resident is asked.
    check = sql(database, "select outcome,checked_by,note,criteria from vh_qc_results where work_order_id=$1", UUID(job))
    assert [(c["outcome"], c["checked_by"], c["note"]) for c in check] == [("pass", HOA, "Đã thay 2 bóng LED, đèn sáng tốt")]
    assert json.loads(check[0]["criteria"]) == [{"name": "acceptance_report", "result": "pass", "photos": 2}]
    assert events(database, ticket, "work_order.qc_recorded")[0]["payload"]["channel"] == "acceptance_report"
    assert sql(database, "select status from tickets where id=$1", UUID(ticket)) == [{"status": "resolved"}]
    [request] = sql(database, "select id,kind,status,requested_to_user_id from work_approvals where work_order_id=$1 and kind='customer_completion'", UUID(job))
    assert (request["status"], request["requested_to_user_id"]) == ("pending", AN)

    # What the coordinator checks before asking the resident to confirm.
    final = call(database, work.ticket_get, ticket)
    assert (final["ticket_status"], final["status"]) == ("resolved", "completed") and final["completion_request"]["waiting_for_resident"]
    [shown] = final["work_orders"]
    assert shown["work_status"] == "completed" and shown["photos"] == {"before": 1, "after": 1, "verification": 1}
    # The technician's three files are the request's files too; the resident sent none.
    assert len(sql(database, "select 1 as x from ticket_files where ticket_id=$1", UUID(ticket))) == 3 and final["resident_photos"] == 0
    report = shown["acceptance_report"]
    assert {**report, "reported_at": None} == {"result": "pass", "reported_by": "Kỹ thuật viên Hoa", "reported_at": None,
                                                "note": "Đã thay 2 bóng LED, đèn sáng tốt"}
    assert re.fullmatch(WHEN, report["reported_at"]) and "acceptance" not in shown and "onsite" not in json.dumps(final)
    assert "Nhân viên gửi kết quả nghiệm thu" in [m["what"] for m in final["milestones"]]

    # Section 7: every step went out under the dispatch's reference, in order, each with a higher version.
    sync(database, fake)
    sync(database, fake)
    sent = outbox(database, ticket)
    assert [r["event_type"] for r in sent] == ["job.offered", "job.accepted", "job.en_route", "job.arrived", "job.quote_ready", "job.quote_approved",
                                               "job.started", "job.completed", "job.result_published"]
    assert all((r["client_reference"], r["external_job_id"], r["status"]) == (dispatch, job, "sent") for r in sent)
    versions = [r["provider_version"] for r in sent]
    assert versions == sorted(set(versions))
    got = [r["body"] for r in fake.received.values()]
    assert [b["event_type"] for b in got] == [r["event_type"] for r in sent] and all(b["client_reference"] == dispatch for b in got)
    assert sent[1]["data"]["staff_name"] == "Kỹ thuật viên Hoa" and re.fullmatch(WHEN, sent[1]["data"]["eta"])
    assert sent[4]["data"] == quote and sent[5]["data"] == {}
    assert sent[8]["data"] == {"summary": "Nhân viên đã làm xong và gửi kết quả nghiệm thu. Ghi chú của nhân viên: Đã thay 2 bóng LED, đèn sáng tốt",
                               "photo_count": 2, "reported_by": "Kỹ thuật viên Hoa"}
    # The resident has the result in the chat from the bridge itself, once, whatever the coordinator goes on to say.
    assert [m["text"] for m in chat(database, channel) if "platform" not in m][-1:] == [
        "Nhân viên đã làm xong và gửi kết quả nghiệm thu. Ghi chú của nhân viên: Đã thay 2 bóng LED, đèn sáng tốt\n"
        "Người gửi: Kỹ thuật viên Hoa. Số ảnh kết quả: 2.\nBạn xem rồi bấm Xác nhận hoàn thành hoặc Chưa đạt ngay trong hộp chat này."]
    with person(database, AN) as c:
        assert next(x for x in c.get("/resident/chats").json()["items"] if x["id"] == channel)["confirm_close"] is True
    # Every value a message template prints is one non-empty line.
    for row in sent:
        assert all(isinstance(v, (int, list)) or (v.strip() and "\n" not in v) for v in row["data"].values()), row["data"]
    assert "VH-" not in json.dumps(got, ensure_ascii=False) and "0901234567" not in json.dumps(got, ensure_ascii=False)

    # The resident confirms in the chat: closed, and the workflow is told to close (the bridge's part).
    confirmed = decide(database, ticket, request["id"], True, "Đã xong, cảm ơn")
    assert confirmed.status_code == 200, confirmed.text
    assert sql(database, "select status from tickets where id=$1", UUID(ticket)) == [{"status": "closed"}]
    assert (commands(database, ticket)[-1]["kind"], commands(database, ticket)[-1]["body"]) == ("close", {"reason": "resident_confirmed"})
    # The completion answer is not a quote answer: nothing more is reported for it.
    sync(database, fake)
    assert len(outbox(database, ticket)) == 9


def test_work_that_follows_a_plan_is_not_accepted_on_site(database):
    staff = sql(database, "select id from staff_profiles where user_id=$1", TECH)[0]["id"]
    on_shift(database, TECH)
    order, _ = approved_order(database)
    offered = offer(database, order, staff)
    assert offered.status_code == 201, offered.text
    with person(database, TECH) as worker:
        accept(worker, offered.json())
        done = sql(database, "update work_orders set status='completed',completed_at=now(),version=version+1 where id=$1 returning version", UUID(order["id"]))[0]
        refused = worker.post(f"/work-orders/{order['id']}/onsite-acceptance", json={"version": done["version"]})
        assert refused.status_code == 409 and "plan" in refused.text
    assert sql(database, "select count(*) as n from vh_qc_results where work_order_id=$1", UUID(order["id"])) == [{"n": 0}]


def finished(database, fake):
    """A dispatched job the technician reported done, with its photos, not yet inspected by anyone."""
    on_shift(database, HOA)
    channel, ticket = started(database, fake)
    job = call(database, work.dispatch, ticket, "Thay bóng đèn phòng khách", None, None, ref())["external_job_id"]
    with person(database, HOA) as worker:
        mine = next(j for j in worker.get("/my-work-orders").json()["items"] if j["id"] == job)
        order = accept(worker, {"id": mine["assignment_id"], "work_order_id": job})
        for status in ("en_route", "arrived"):
            moved = advance(worker, order, status)
            assert moved.status_code == 200, moved.text
            order = moved.json()
        proposed = worker.post(f"/work-orders/{job}/repair-proposal", json={
            "version": order["version"], "note": "Thay bóng LED mới", "labor_cost": 50000, "warranty_months": 3, "lines": []})
        assert proposed.status_code == 201, proposed.text
    assert decide(database, ticket, proposed.json()["id"], True, "Tôi đồng ý").status_code == 200
    with person(database, HOA) as worker:
        moved = advance(worker, worker.get(f"/work-orders/{job}").json()["workOrder"], "in_progress")
        assert moved.status_code == 200, moved.text
        order = moved.json()
        for purpose in ("before", "after"):
            photo(worker, ticket, job, mine["assignment_id"], purpose)
        done = advance(worker, order, "completed")
        assert done.status_code == 200, done.text
    return ticket, job, {"version": done.json()["version"]}


def test_the_acceptance_on_site_is_once_per_job_and_never_over_an_inspection(database, on):
    fake = FakePlatform()
    # Management inspected the job and failed it: the technician who did it cannot overrule that.
    ticket, job, said = finished(database, fake)
    with person(database, MINH) as manager:
        failed = manager.post(f"/work-orders/{job}/qc", json={"outcome": "fail", "criteria": [{"name": "đèn", "result": "fail"}], "note": "Đèn vẫn nhấp nháy"})
        assert failed.status_code == 201, failed.text
    with person(database, HOA) as worker:
        again = worker.post(f"/work-orders/{job}/onsite-acceptance", json=said)
        assert again.status_code == 409 and "inspected" in again.text
    assert sql(database, "select outcome from vh_qc_results where work_order_id=$1", UUID(job)) == [{"outcome": "fail"}]
    assert sql(database, "select status from tickets where id=$1", UUID(ticket)) == [{"status": "in_progress"}]

    # The resident refused the result in the chat: the same unchanged job is not published a second time.
    ticket, job, said = finished(database, fake)
    with person(database, HOA) as worker:
        assert worker.post(f"/work-orders/{job}/onsite-acceptance", json=said).status_code == 201
    [request] = sql(database, "select id from work_approvals where work_order_id=$1 and kind='customer_completion' and status='pending'", UUID(job))
    refused = decide(database, ticket, request["id"], False, "Đèn vẫn nhấp nháy sau khi thay")
    assert refused.status_code == 200, refused.text
    with person(database, HOA) as worker:
        assert worker.post(f"/work-orders/{job}/onsite-acceptance", json=said).status_code == 409
    assert sql(database, "select status from tickets where id=$1", UUID(ticket)) == [{"status": "triaging"}]
    assert sql(database, "select count(*) as n from vh_qc_results where work_order_id=$1", UUID(job)) == [{"n": 1}]


def test_a_quote_the_resident_refuses_on_the_card_is_reported_as_refused(database, on):
    fake = FakePlatform()
    on_shift(database, HOA)
    channel, ticket = started(database, fake)
    job = call(database, work.dispatch, ticket, "Thay bóng đèn phòng khách", None, None, ref())["external_job_id"]
    with person(database, HOA) as worker:
        mine = next(j for j in worker.get("/my-work-orders").json()["items"] if j["id"] == job)
        order = accept(worker, {"id": mine["assignment_id"], "work_order_id": job})
        for status in ("en_route", "arrived"):
            order = advance(worker, order, status).json()
        proposed = worker.post(f"/work-orders/{job}/repair-proposal", json={
            "version": order["version"], "note": "Thay cả bộ đèn", "labor_cost": 300000, "warranty_months": 0,
            "lines": [{"name": "Dây điện", "quantity": "1.5", "unit": "m", "unit_price": 20000}]})
        assert proposed.status_code == 201, proposed.text
    sync(database, fake)
    [card] = [m for m in chat(database, channel) if "platform" in m]
    # A part of a metre is a number with its fraction; no warranty, no warranty sentence.
    assert card["platform"]["lines"] == [{"name": "Dây điện", "quantity": 1.5, "unit": "m", "unit_price": 20000, "amount": 30000}]
    assert card["text"].splitlines()[1:4] == ["- Dây điện (1.5 m): 30.000 đồng", "- Tiền công: 300.000 đồng", "Tổng cộng: 330.000 đồng."]
    assert decide(database, ticket, proposed.json()["id"], False, "Giá cao quá, tôi chỉ cần thay bóng").status_code == 200
    with person(database, AN) as c:
        shown = [m["body"]["platform"] for m in c.get(f"/resident/chats/{channel}/messages").json()["items"] if m["body"].get("platform")]
    assert [(p["kind"], p["status"]) for p in shown] == [("quote", "rejected")]
    assert sql(database, "select status from work_orders where id=$1", UUID(job)) == [{"status": "arrived"}]
    sync(database, fake)
    sync(database, fake)
    assert [(r["event_type"], r["data"]) for r in outbox(database, ticket)][-2:] == [
        ("job.quote_ready", {"items": [{"label": "Dây điện (1.5 m)", "amount": 30000}, {"label": "Tiền công", "amount": 300000}],
                             "total": 330000, "warranty_months": 0}), ("job.quote_rejected", {})]
    put_down(database, job)


# ---- emergencies and photos -----------------------------------------------------------------------------------------

def test_an_emergency_is_handed_over_with_its_level_and_guard_work_is_still_not_dispatched(database, on):
    fake = FakePlatform()
    on_shift(database, HOA)
    channel, ticket = started(database, fake)
    with person(database, AN) as c:
        # In the handed-over chat the resident reports smoke: Reception's emergency handling escalates the request
        # (its operation, as its agent calls it) and the coordinator is told.
        message = say(c, channel, "Ổ điện phòng khách đang bốc khói")
        told = commands(database, ticket)[-1]
        assert told["kind"] == "workflow_reply" and told["body"]["text"].startswith("Cư dân vừa báo tình huống khẩn cấp (cháy hoặc khói).")
        assert told["body"]["text"].endswith("Lời cư dân:\nỔ điện phòng khách đang bốc khói") and told["body"]["own"] is True
        escalated, _ = operation(c, "escalate_emergency", {"ticket_id": ticket, "reason": "Cư dân báo ổ điện bốc khói", "source_message_id": message})
        assert escalated["isEmergency"] is True
    seen = call(database, work.ticket_get, ticket)
    assert (seen["is_emergency"], seen["severity"], seen["priority"]) == (True, "critical", "critical")
    # The coordinator dispatches at once, like any other repair.
    sent = call(database, work.dispatch, ticket, "Kiểm tra ổ điện phòng khách bốc khói", None, None, ref())
    assert sent["status"] == "pending"
    put_down(database, sent["external_job_id"])

    # An emergency of the security category is told to the platform as well; guards stay management's to send.
    with person(database, AN) as c:
        _, guard = hand_over(c)
    sql(database, "delete from platform_commands where ticket_id=$1 returning id", UUID(guard))
    sql(database, "delete from platform_links where ticket_id=$1 returning ticket_id", UUID(guard))
    sql(database, "update tickets set category_id=$2,is_emergency=true,priority='critical',severity='critical' where id=$1 returning id", UUID(guard), CAT_SEC)

    async def handed(db, ticket):
        await link_ticket(db, ticket)
        return {}

    call(database, handed, guard)
    [start] = commands(database, guard)
    assert "Mức khẩn cấp do Lễ tân đánh giá: KHẨN CẤP; mức độ nghiêm trọng: nghiêm trọng" in start["body"]["text"].splitlines()
    refused = call(database, work.dispatch, guard, "Cử bảo vệ lên kiểm tra", None, None, ref())
    assert refused["status"] == "failed" and "an ninh" in refused["reason"]
    assert sql(database, "select count(*) as n from work_orders where ticket_id=$1", UUID(guard)) == [{"n": 0}]


def test_an_emergency_while_the_result_waits_for_the_resident_still_reaches_management(database, on):
    fake = FakePlatform()
    channel, ticket = started(database, fake)
    sql(database, "update tickets set status='resolved',resolved_at=now() where id=$1 returning id", UUID(ticket))
    with person(database, AN) as c:
        message = say(c, channel, "Ổ điện vừa sửa lại chập điện, bốc khói")
        assert commands(database, ticket)[-1]["body"]["text"].startswith("Cư dân vừa báo tình huống khẩn cấp (cháy hoặc khói). Lời cư dân:")
        escalated, _ = operation(c, "escalate_emergency", {"ticket_id": ticket, "reason": "Ổ điện bốc khói", "source_message_id": message})
    assert escalated["isEmergency"] is True and escalated["notificationQueued"] is True
    assert sql(database, "select status,is_emergency,priority from tickets where id=$1", UUID(ticket)) == [
        {"status": "resolved", "is_emergency": True, "priority": "critical"}]


def test_photos_sent_after_the_hand_over_are_counted_by_the_ticket_look_up(database, on):
    fake = FakePlatform()
    channel, ticket = started(database, fake)
    with person(database, AN) as c:
        sent = []
        for name in ("a.png", "b.png"):
            photo_ = c.post(f"/resident/chats/{channel}/photos?filename={name}&mimeType=image/png", content=image(), headers=key())
            assert photo_.status_code == 201, photo_.text
            sent.append(photo_.json()["id"])
        posted = c.post(f"/resident/chats/{channel}/messages", json={"text": "Ảnh chỗ hỏng đây ạ", "client_message_id": str(uuid4()), "file_ids": sent})
        assert posted.status_code == 201, posted.text
    assert commands(database, ticket)[-1]["body"] == {"text": "Ảnh chỗ hỏng đây ạ\nCư dân gửi thêm 2 ảnh."}
    assert call(database, work.ticket_get, ticket)["resident_photos"] == 2
    assert [e["payload"] for e in events(database, ticket, "ticket.conversation_images_attached")] == [{"fileIds": sent}]


# ---- offers ------------------------------------------------------------------------------------------------------------

def test_a_refused_offer_goes_to_the_next_person_and_when_nobody_is_left_it_is_said_once(database, on):
    fake = FakePlatform()
    on_shift(database, HOA, TECH)
    channel, ticket = started(database, fake)
    free = call(database, work.staff_available, ticket)["staff"]
    assert len(free) == 2
    # The coordinator names the person the automatic choice would not take first.
    chosen, dispatch = free[1], ref()
    answer = call(database, work.dispatch, ticket, "Kiểm tra đèn phòng khách", chosen["staff_id"], None, dispatch)
    assert (answer["status"], answer["offered_to"]) == ("pending", chosen["name"])
    job = answer["external_job_id"]

    first = refuse(database, job)
    held = offers(database, job)
    # At once, in the transaction of the refusal: the other technician has it.
    assert [(o["name"], o["status"]) for o in held] == [(chosen["name"], "rejected"), (free[0]["name"], "offered")]
    assert sql(database, "select status from work_orders where id=$1", UUID(job)) == [{"status": "offered"}]
    second = refuse(database, job)
    assert {first, second} == {HOA, TECH}
    assert sql(database, "select status from work_orders where id=$1", UUID(job)) == [{"status": "queued"}]
    kinds = ("work_order.offered", "work_assignment.responded", "work_order.unassigned")
    assert [e["event_type"] for e in events(database, ticket, *kinds)] == [
        "work_order.offered", "work_assignment.responded", "work_order.offered", "work_assignment.responded", "work_order.unassigned"]
    assert events(database, ticket, "work_order.unassigned")[0]["payload"] == {"workOrderId": job}

    # The sweep keeps trying, but not with the two who refused, and does not say "nobody" again.
    assert call(database, sweep_tenant)["offers_expired"] == 0
    assert len(offers(database, job)) == 2 and len(events(database, ticket, "work_order.unassigned")) == 1
    again = call(database, work.dispatch, ticket, "Kiểm tra đèn phòng khách, giao lại", None, None, ref())
    assert again["status"] == "failed" and "xếp hàng" in again["reason"]
    # Someone new comes on shift: the next sweep offers them the job that waited.
    other = sql(database, """select p.user_id,u.name from staff_profiles p join users u on u.id=p.user_id
        join staff_specialties s on s.staff_id=p.id and s.category_id=$1 where p.availability='available' and p.active
          and p.user_id<>all($2::text[]) order by p.user_id limit 1""", UUID(CATEGORY), [HOA, TECH])[0]
    on_shift(database, HOA, TECH, other["user_id"])
    call(database, sweep_tenant)
    assert [(o["name"], o["status"]) for o in offers(database, job)][-1] == (other["name"], "offered")
    assert len(events(database, ticket, "work_order.unassigned")) == 1

    sync(database, fake)
    sync(database, fake)
    sent = outbox(database, ticket)
    assert [r["event_type"] for r in sent] == ["job.offered", "job.declined", "job.offered", "job.declined", "job.unassigned", "job.offered"]
    assert all((r["client_reference"], r["external_job_id"], r["data"]) == (dispatch, job, {}) for r in sent)


def test_with_nobody_free_the_job_waits_then_is_offered_and_an_offer_nobody_answers_runs_out(database, on):
    fake = FakePlatform()
    on_shift(database)
    channel, ticket = started(database, fake)
    dispatch = ref()
    answer = call(database, work.dispatch, ticket, "Thay bóng đèn phòng khách", None, None, dispatch)
    job = answer["external_job_id"]
    assert answer["status"] == "queued" and "offered_to" not in answer
    assert call(database, work.dispatch, ticket, "Thay bóng đèn phòng khách", None, None, dispatch) == answer
    assert sql(database, "select status from work_orders where ticket_id=$1", UUID(ticket)) == [{"status": "queued"}]
    assert offers(database, job) == [] and events(database, ticket, "work_order.unassigned") == []
    assert call(database, sweep_tenant)["offers_expired"] == 0 and offers(database, job) == []

    # A technician comes on shift: the sweep offers the job without anyone asking again.
    on_shift(database, HOA)
    call(database, sweep_tenant)
    [held] = offers(database, job)
    assert (held["user_id"], held["status"]) == (HOA, "offered")
    assert call(database, sweep_tenant)["offers_expired"] == 0 and len(offers(database, job)) == 1

    # Nobody answers. The offer runs out: ended, said once, and with nobody else on shift the job is unassigned.
    sql(database, "update work_assignments set offer_expires_at=now()+interval '1 second' where id=$1 returning id", held["id"])
    time.sleep(1.3)
    assert call(database, sweep_tenant)["offers_expired"] == 1
    assert [(o["user_id"], o["status"]) for o in offers(database, job)] == [(HOA, "released")]
    assert sql(database, "select status from work_orders where id=$1", UUID(job)) == [{"status": "queued"}]
    [expired] = events(database, ticket, "work_assignment.expired")
    assert expired["payload"] == {"assignmentId": str(held["id"]), "workOrderId": job} and expired["actor_client_id"] == "platform"
    assert call(database, sweep_tenant)["offers_expired"] == 0
    assert len(events(database, ticket, "work_assignment.expired")) == 1 and len(events(database, ticket, "work_order.unassigned")) == 1
    # The next person on shift gets it; the one who let it run out is not asked again.
    on_shift(database, HOA, TECH)
    call(database, sweep_tenant)
    assert [(o["user_id"], o["status"]) for o in offers(database, job)] == [(HOA, "released"), (TECH, "offered")]

    sync(database, fake)
    sync(database, fake)
    assert [r["event_type"] for r in outbox(database, ticket)] == ["job.offered", "job.offer_expired", "job.unassigned", "job.offered"]

    # An offer of work the platform did not dispatch is left as it was: it only reads as expired (as before).
    order, _ = approved_order(database)
    manual = offer(database, order, sql(database, "select id from staff_profiles where user_id=$1", HOA)[0]["id"])
    assert manual.status_code == 201, manual.text
    sql(database, "update work_assignments set offer_expires_at=now()+interval '1 second' where id=$1 returning id", UUID(manual.json()["id"]))
    time.sleep(1.3)
    assert call(database, sweep_tenant)["offers_expired"] == 0
    assert sql(database, "select status from work_assignments where id=$1", UUID(manual.json()["id"])) == [{"status": "offered"}]


# ---- the other actions --------------------------------------------------------------------------------------------------

def test_reschedule_note_and_cancel_do_their_work_once_and_refuse_once_staff_is_under_way(database, on):
    fake = FakePlatform()
    on_shift(database, HOA)
    channel, ticket = started(database, fake)
    morning = (datetime.now(VN) + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
    evening = morning.replace(hour=18, minute=30)
    assert call(database, work.reschedule, ticket, evening.isoformat(), "x", ref())["status"] == "failed"   # nothing to move yet
    for bad in ("hôm qua", "2020-01-01T09:00:00+07:00"):
        refused = call(database, work.dispatch, ticket, "Thay bóng đèn", None, bad, ref())
        assert refused["status"] == "failed" and "Giờ hẹn" in refused["reason"]
    assert call(database, work.dispatch, ticket, "  ", None, None, ref())["status"] == "failed"
    assert sql(database, "select count(*) as n from work_orders where ticket_id=$1", UUID(ticket)) == [{"n": 0}]
    dispatch = ref()
    answer = call(database, work.dispatch, ticket, "Thay bóng đèn", "khong-phai-ma-nhan-vien", morning.isoformat(), dispatch)
    job = answer["external_job_id"]
    assert answer["status"] == "pending" and answer["appointment"] == morning.strftime("%H:%M %d/%m/%Y")
    assert offers(database, job)[0]["eta_at"] == morning

    # Without an offset the time is Vietnam time, as the resident said it.
    change = ref()
    moved = call(database, work.reschedule, ticket, evening.replace(tzinfo=None).isoformat(), "Cư dân bận buổi sáng", change)
    assert moved == {"status": "confirmed", "appointment": evening.strftime("%H:%M %d/%m/%Y")}
    assert call(database, work.reschedule, ticket, evening.replace(tzinfo=None).isoformat(), "Cư dân bận buổi sáng", change) == moved
    assert sql(database, "select scheduled_at from work_orders where id=$1", UUID(job)) == [{"scheduled_at": evening}]
    assert offers(database, job)[0]["eta_at"] == evening
    [changed] = events(database, ticket, "work_order.rescheduled")
    assert changed["payload"] == {"workOrderId": job, "appointmentAt": evening.isoformat(), "reason": "Cư dân bận buổi sáng"}
    told = sql(database, "select payload from notification_deliveries where user_id=$1 and payload->>'type'='work.rescheduled' and payload->>'workOrderId'=$2", HOA, job)
    assert len(told) == 1 and json.loads(told[0]["payload"])["appointmentAt"] == evening.isoformat()
    assert call(database, work.reschedule, ticket, "2020-01-01T09:00:00+07:00", "", ref())["status"] == "failed"

    note = ref()
    assert call(database, work.add_note, ticket, "Gọi chuông hai lần, chuông hơi nhỏ", note) == {"status": "confirmed"}
    assert call(database, work.add_note, ticket, "Gọi chuông hai lần, chuông hơi nhỏ", note) == {"status": "confirmed"}
    assert [e["payload"] for e in events(database, ticket, "ticket.note_added")] == [{"note": "Gọi chuông hai lần, chuông hơi nhỏ"}]
    assert call(database, work.add_note, ticket, " ", ref())["status"] == "failed"

    with person(database, HOA) as worker:
        mine = next(j for j in worker.get("/my-work-orders").json()["items"] if j["id"] == job)
        order = accept(worker, {"id": mine["assignment_id"], "work_order_id": job})
        order = advance(worker, order, "en_route").json()
        late = call(database, work.reschedule, ticket, morning.isoformat(), "Đổi lại", ref())
        assert late["status"] == "failed" and "lên đường" in late["reason"]
        assert advance(worker, order, "arrived").status_code == 200
    # Work that reached the home cannot be cancelled by the coordinator.
    stopped = call(database, work.cancel, ticket, "Cư dân đổi ý", ref())
    assert stopped["status"] == "failed" and "không hủy được" in stopped["reason"]
    assert sql(database, "select t.status as ticket,w.status as work from tickets t join work_orders w on w.ticket_id=t.id where t.id=$1", UUID(ticket)) == [
        {"ticket": "assigned", "work": "arrived"}]
    assert events(database, ticket, "ticket.status_changed") == []

    sync(database, fake)
    sync(database, fake)
    sent = outbox(database, ticket)
    assert [r["event_type"] for r in sent] == ["job.offered", "job.rescheduled", "job.accepted", "job.en_route", "job.arrived"]
    assert sent[1]["data"] == {"appointment": evening.strftime("%H:%M %d/%m/%Y")} and sent[1]["client_reference"] == dispatch

    # Before anyone set out, cancelling ends the ticket, its work and the offer together.
    channel, other = started(database, fake)
    # The reference of the first ticket's dispatch says nothing about this ticket and does nothing to it.
    stray = call(database, work.cancel, other, "nhầm", dispatch)
    assert stray["status"] == "failed" and "external_job_id" not in stray
    assert sql(database, "select status from tickets where id=$1", UUID(other))[0]["status"] in ("open", "triaging")
    dispatch = ref()
    job = call(database, work.dispatch, other, "Thay bóng đèn", None, None, dispatch)["external_job_id"]
    cancel = ref()
    gone = call(database, work.cancel, other, "Cư dân tự sửa được rồi", cancel)
    assert gone == {"status": "confirmed", "ticket_status": "cancelled", "cancelled_work_orders": 1}
    assert call(database, work.cancel, other, "Cư dân tự sửa được rồi", cancel) == gone
    assert sql(database, "select t.status as ticket,w.status as work from tickets t join work_orders w on w.ticket_id=t.id where t.id=$1", UUID(other)) == [
        {"ticket": "cancelled", "work": "cancelled"}]
    assert [o["status"] for o in offers(database, job)] == ["cancelled"]
    # The workflow has nothing left to do: it is closed after the coordinator's turn, once.
    assert [(c["kind"], c["body"]) for c in commands(database, other) if c["kind"] == "close"] == [("close", {"reason": "resident_cancelled"})]
    [ended] = events(database, other, "ticket.status_changed")
    assert ended["payload"] == {"reason": "Cư dân tự sửa được rồi", "cancelledBy": "resident"} and len(events(database, other, "work_order.status_changed")) == 1
    for function, *more in ((work.cancel, "lần nữa"), (work.dispatch, "Thay bóng đèn", None, None)):
        assert call(database, function, other, *more, ref())["status"] == "failed"
    sync(database, fake)
    sync(database, fake)
    sent = outbox(database, other)
    assert [r["event_type"] for r in sent] == ["job.offered", "job.cancelled"]
    # The reason the resident reads is a fixed sentence, not what the coordinator typed.
    assert sent[1]["data"] == {"reason": "Yêu cầu được hủy theo đề nghị của cư dân"} and sent[1]["client_reference"] == dispatch


def test_dispatch_is_refused_for_plan_tickets_and_for_guard_work(database, on, monkeypatch):
    on_shift(database, HOA)
    with person(database, AN) as c:
        _, planned = hand_over(c, plan=True)
        _, guard = hand_over(c)
    sql(database, "update tickets set category_id=$2 where id=$1 returning id", UUID(guard), CAT_SEC)
    plan = call(database, work.dispatch, planned, "Thay bóng đèn", None, None, ref())
    assert plan["status"] == "failed" and "phương án" in plan["reason"]
    security = call(database, work.dispatch, guard, "Cử bảo vệ kiểm tra", None, None, ref())
    assert security["status"] == "failed" and "an ninh" in security["reason"]
    assert sql(database, "select count(*) as n from work_orders where ticket_id=any($1::uuid[])", [UUID(planned), UUID(guard)]) == [{"n": 0}]
    assert sql(database, "select status from tickets where id=$1", UUID(planned))[0]["status"] in ("open", "triaging")

    # Security requests also get a platform session; receiving them does not allow guard dispatch.
    monkeypatch.delenv("VINHOMES_API_PLATFORM_URL")
    with person(database, AN) as c:
        _, patrol = hand_over(c)
    monkeypatch.setenv("VINHOMES_API_PLATFORM_URL", "http://platform.test")

    async def handed(db, ticket):
        await link_ticket(db, ticket)
        return {}

    # Both incident and service tickets are handed over once, without a management reception gate.
    for category, kind, links in ((CAT_SEC, "incident", 1), (CAT_SEC, "service_request", 1)):
        sql(database, "update tickets set category_id=$2,request_kind=$3 where id=$1 returning id", UUID(patrol), category, kind)
        call(database, handed, patrol)
        assert sql(database, "select count(*) as n from platform_links where ticket_id=$1", UUID(patrol)) == [{"n": links}]


# ---- the MCP server -----------------------------------------------------------------------------------------------------

def serve(database):
    """The API on a real port, as the platform reaches it."""
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    app = create_app(V3Settings("127.0.0.1", port, database["runtime"], TENANT, None))
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(200):
        if server.started:
            break
        time.sleep(0.05)
    assert server.started
    return server, thread, f"http://127.0.0.1:{port}/mcp"


def test_the_mcp_server_lists_and_runs_the_tools_only_for_the_token(database, on, monkeypatch):
    with person(database, AN) as c:
        _, ticket = hand_over(c)
        # Without a token the bridge serves no tools at all.
        assert c.post("/mcp", json={}).status_code == 404
    monkeypatch.setenv("VINHOMES_API_PLATFORM_MCP_TOKEN", TOKEN)
    server, thread, url = serve(database)
    hello = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}}}
    accepts = {"Accept": "application/json, text/event-stream"}
    note = ref()

    async def session(run):
        # A new session for every call, static headers: how the platform calls (mcp-requirements, fact 1).
        async with httpx.AsyncClient(headers={"Authorization": "Bearer " + TOKEN, "Accept-Encoding": "identity"}, follow_redirects=False) as http:
            async with streamable_http_client(url, http_client=http) as (read, write, _):
                async with ClientSession(read, write) as client:
                    await client.initialize()
                    return await run(client)

    try:
        for headers in ({}, {"Authorization": "Bearer " + TOKEN[:-1] + "x"}, {"Authorization": TOKEN}, {"Authorization": "Bearer " + TOKEN + "x"}):
            refused = httpx.post(url, json=hello, headers={**accepts, **headers})
            assert refused.status_code == 401 and TOKEN not in refused.text, headers
            assert httpx.get(url, headers=headers).status_code == 401
        direct = httpx.post(url, json=hello, headers={**accepts, "Authorization": "Bearer " + TOKEN})
        assert direct.status_code == 200 and direct.json()["result"]["serverInfo"]["name"] == "vinhomes"
        assert "mcp-session-id" not in direct.headers   # stateless

        tools = {tool.name: tool for tool in asyncio.run(session(lambda client: client.list_tools())).tools}
        looks = {"vh_ticket_get", "vh_knowledge_search", "vh_staff_available"}
        acts = {"vh_work_order_dispatch", "vh_work_order_reschedule", "vh_ticket_cancel", "vh_ticket_add_note"}
        # Nothing records an answer to a quote: that is the resident's own tap on the card.
        assert set(tools) == looks | acts
        for name, tool in tools.items():
            # A look-up says it only reads; an action declares the reference the platform fills in.
            assert bool(tool.annotations and tool.annotations.readOnlyHint) == (name in looks)
            assert ("client_reference" in tool.inputSchema["properties"]) == (name in acts) and "ticket_id" in tool.inputSchema["required"]
            assert "$ref" not in json.dumps(tool.inputSchema) and len(tool.description) <= 1000

        seen = asyncio.run(session(lambda client: client.call_tool("vh_ticket_get", {"ticket_id": ticket})))
        assert not seen.isError and json.loads(seen.content[0].text)["ticket_status"] in ("open", "triaging")
        unknown = asyncio.run(session(lambda client: client.call_tool("vh_ticket_get", {"ticket_id": str(uuid4())})))
        assert not unknown.isError and "ticket_id" in unknown.content[0].text and not unknown.content[0].text.startswith("{")
        for _ in range(2):   # the same reference twice
            done = asyncio.run(session(lambda client: client.call_tool("vh_ticket_add_note", {
                "ticket_id": ticket, "note": "Cư dân dặn gọi trước khi đến", "client_reference": note})))
            assert not done.isError and json.loads(done.content[0].text) == {"status": "confirmed"}
        refused = asyncio.run(session(lambda client: client.call_tool("vh_ticket_cancel", {
            "ticket_id": str(uuid4()), "reason": "thử", "client_reference": ref()})))
        answer = json.loads(refused.content[0].text)
        assert answer["status"] == "failed" and answer["reason"]
    finally:
        server.should_exit = True
        thread.join(timeout=10)
    assert [e["payload"] for e in events(database, ticket, "ticket.note_added")] == [{"note": "Cư dân dặn gọi trước khi đến"}]


def test_a_visitor_is_announced_once_under_the_rules_of_the_zone_and_the_notices_are_those_of_the_home(database, on):
    with person(database, AN) as c:
        _, ticket = hand_over(c)
    soon = (datetime.now(VN) + timedelta(hours=3)).isoformat()
    later = (datetime.now(VN) + timedelta(hours=6)).isoformat()

    def passes():
        return sql(database, "select status,guest_count,host_user_id from visitor_passes where guest_name like 'Khách thử%' order by created_at")

    first = ref()
    made = call(database, work.visitor_register, ticket, "Khách thử Một", soon, later, "family_visit", 2, None, first)
    assert (made["status"], made["visit_status"], made["needs_desk_approval"]) == ("confirmed", "approved", False)      # 1: a family visit of two needs no desk
    assert re.fullmatch(WHEN, made["visit_from"]) and "qr_token" not in made and "code" not in made
    assert call(database, work.visitor_register, ticket, "Khách thử Một", soon, later, "family_visit", 2, None, first) == made
    assert [(p["status"], p["host_user_id"]) for p in passes()] == [("approved", AN)]                                    # 2: asked twice, announced once, as the resident
    big = call(database, work.visitor_register, ticket, "Khách thử Hai", soon, later, "family_visit", 8, None, ref())
    assert (big["status"], big["visit_status"], big["needs_desk_approval"]) == ("confirmed", "pending_approval", True)   # 3: eight people wait for the desk
    for bad in (("Khách thử Ba", "mai", later, "family_visit"), ("Khách thử Ba", later, soon, "family_visit"), ("Khách thử Ba", soon, later, "party"), ("", soon, later, "other")):
        refused = call(database, work.visitor_register, ticket, *bad, 1, None, ref())
        assert refused["status"] == "failed" and refused["reason"]                                                       # 4: refused in words, nothing written
    assert len(passes()) == 2
    assert call(database, work.visitor_register, str(uuid4()), "Khách thử Tư", soon, later, "other", 1, None, ref())["status"] == "failed"

    seen = call(database, work.notices, ticket)["announcements"]
    mine = sql(database, """select a.title from announcements a where a.status='published' and a.published_at<=now() and (a.expire_at is null or a.expire_at>now())
        and ((cardinality(a.zone_ids)=0 and cardinality(a.building_ids)=0) or exists (select 1 from unit_residents ur join units u on u.id=ur.unit_id
          where ur.user_id=$1 and (u.building_id=any(a.building_ids) or u.zone_id=any(a.zone_ids)))) order by a.published_at desc limit 10""", AN)
    assert seen and [a["title"] for a in seen] == [a["title"] for a in mine]                                             # 5: what the resident's own app lists
    assert all(re.fullmatch(WHEN, a["published_at"]) for a in seen)


def test_the_services_of_the_home_are_read_and_changed_as_the_resident_would_and_a_booking_waits_for_their_tap(database, on):
    with person(database, AN) as c:
        channel, ticket = hand_over(c)
    home = sql(database, "select unit_id from tickets where id=$1", UUID(ticket))[0]["unit_id"]
    soon, later = (datetime.now(VN) + timedelta(hours=3)).isoformat(), (datetime.now(VN) + timedelta(hours=6)).isoformat()

    # Visitors: listed with a reference, cancelled once.
    call(database, work.visitor_register, ticket, "Khách dịch vụ", soon, later, "family_visit", 1, None, ref())
    visit = next(v for v in call(database, work.visitors, ticket)["visits"] if v["guest_name"] == "Khách dịch vụ")
    assert visit["visit_status"] == "approved" and re.fullmatch(WHEN, visit["visit_from"])
    assert call(database, work.visitor_cancel, ticket, visit["visit_ref"], ref()) == {"status": "confirmed", "visit_status": "cancelled"}   # 1
    assert call(database, work.visitor_cancel, ticket, visit["visit_ref"], ref())["status"] == "failed"                                     # 2: not twice
    assert call(database, work.visitor_cancel, ticket, "không-phải-mã", ref())["status"] == "failed"

    # Cards: the number is masked; a lost card is blocked; a card of another home cannot be touched.
    sql(database, "insert into access_cards(tenant_id,card_no,kind,unit_id,status,holder_name) values($1,'C-TOOL-778899','resident',$2,'pending_issue','Người giữ thẻ') returning id", TENANT, home)
    elsewhere = sql(database, "insert into access_cards(tenant_id,card_no,kind,unit_id,status) select $1,'C-TOOL-OTHER','resident',id,'pending_issue' from units where id<>$2 limit 1 returning id", TENANT, home)[0]["id"]
    sql(database, "update access_cards set status='active' where card_no like 'C-TOOL-%' returning id")
    mine = next(k for k in call(database, work.access_cards, ticket)["cards"] if k["holder_name"] == "Người giữ thẻ")
    assert mine["card_no"].endswith("8899") and mine["card_no"].startswith("*") and mine["card_status"] == "active"                        # 3
    assert call(database, work.card_lost, ticket, mine["card_ref"], ref())["card_status"] == "lost"                                         # 4
    assert sql(database, "select status from access_cards where card_no='C-TOOL-778899'")[0]["status"] == "lost"
    assert call(database, work.card_lost, ticket, str(elsewhere), ref())["status"] == "failed"                                              # 5
    assert sql(database, "select status from access_cards where id=$1", elsewhere)[0]["status"] == "active"

    # Amenities: a free slot the day after tomorrow, offered on a card; nothing is booked until the resident taps.
    day = (datetime.now(VN) + timedelta(days=2)).date().isoformat()
    places = call(database, work.amenity_list, ticket)["amenities"]
    assert places and all(a["amenity_ref"] and a["name"] for a in places)
    # Only the places of the home's own zone: the villa zone's pool is not offered to a tower, nor booked for it.
    villa = sql(database, "select id,name from amenities where code='POOL-V2'")[0]
    assert villa["name"] not in [a["name"] for a in places]
    wrong = call(database, work.amenity_book, ticket, str(villa["id"]), f"{day}T10:00:00+07:00", f"{day}T11:00:00+07:00", "main", 1, ref())
    assert wrong["status"] == "failed" and "phân khu khác" in wrong["reason"]
    place, area, slot = next((a, f["area"], f["free_slots"][0]) for a in places if a["open_now_for_booking"]
                             for f in call(database, work.amenity_free, ticket, a["amenity_ref"], day)["areas"] if f["free_slots"])
    start, end = (f"{day}T{part}:00+07:00" for part in slot.split("-"))
    before = sql(database, "select count(*) as n from amenity_bookings")[0]["n"]
    card_id = ref()
    offered = call(database, work.amenity_book, ticket, place["amenity_ref"], start, end, area, 2, card_id)
    assert (offered["status"], offered["card_shown"], offered["booked"]) == ("confirmed", True, False)                                      # 6
    assert offered["total"] == place["price_per_slot"] and sql(database, "select count(*) as n from amenity_bookings")[0]["n"] == before  # 7: no booking yet
    assert call(database, work.amenity_book, ticket, place["amenity_ref"], start, end, area, 2, card_id) == offered
    shown = [m for m in chat(database, channel) if (m.get("platform") or {}).get("kind") == "booking"]
    assert len(shown) == 1 and place["name"] in shown[0]["text"]                                                                           # 8: one card

    def card(c):
        return next(m["body"]["platform"] for m in c.get(f"/resident/chats/{channel}/messages").json()["items"] if (m["body"].get("platform") or {}).get("kind") == "booking")

    with person(database, CHAU) as other:
        assert other.post(f"/resident/platform/bookings/{card_id}/confirm", headers=key()).status_code == 404                               # 9: only its resident
    with person(database, AN) as c:
        assert card(c)["status"] == "pending"
        done = c.post(f"/resident/platform/bookings/{card_id}/confirm", headers=key())
        assert done.status_code == 200 and done.json()["status"] == "booked", done.text                                                    # 10: the resident's tap books
        assert c.post(f"/resident/platform/bookings/{card_id}/confirm", headers=key()).json() == done.json()
        assert card(c)["status"] == "booked" and card(c)["booking_status"] == done.json()["booking_status"]
    booked = sql(database, "select status,booked_by_user_id,guests from amenity_bookings where idempotency_key=$1", f"{AN}:{card_id}")
    assert len(booked) == 1 and booked[0]["booked_by_user_id"] == AN and booked[0]["guests"] == 2
    told = [x["body"]["text"] for x in commands(database, ticket) if x["kind"] == "workflow_reply"]
    assert len(told) == 1 and told[0].startswith("Tôi đã bấm xác nhận đặt " + place["name"])                                              # 11: the coordinator is told, once
    mine = call(database, work.amenity_list, ticket)["bookings"]
    assert [b["amenity"] for b in mine if b["start"] == offered["start"]] == [place["name"]]
    held = next(b for b in mine if b["start"] == offered["start"])
    assert call(database, work.amenity_cancel, ticket, held["booking_ref"], ref()) == {"status": "confirmed", "booking_status": "cancelled"}   # 12
    for bad in ((place["amenity_ref"], start, start, area), (str(uuid4()), start, end, area), (place["amenity_ref"], start, end, "khu-khong-co")):
        assert call(database, work.amenity_book, ticket, *bad, 1, ref())["status"] == "failed"                                              # 13
    assert len([m for m in chat(database, channel) if (m.get("platform") or {}).get("kind") == "booking"]) == 1

    # The rest only reads, and never names another request by its code.
    assert isinstance(call(database, work.desk_requests, ticket)["requests"], list)
    assert set(call(database, work.renovation, ticket)) == {"rules", "permits"}
    with person(database, AN) as c:
        hand_over(c, "Đèn phòng khách không sáng lần hai")
    others = call(database, work.other_requests, ticket)["requests"]
    assert len(others) == min(20, sql(database, "select count(*) as n from tickets where requester_user_id=$1", AN)[0]["n"]) - 1 and "lần hai" in others[0]["title"] and all(set(o) == {"title", "request_status", "priority", "created_at", "updated_at"} for o in others)                    # 14
