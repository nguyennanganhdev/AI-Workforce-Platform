"""Staff specialty, accepted queue and active execution checks on isolated PostgreSQL."""



import asyncio
import time
from threading import Barrier
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from test_resident_contract import BASE, CATEGORY, OPS, TENANT, client, create, image, key, sql
from test_resident_contract import database as database  # noqa: PLC0414 -- pytest fixture export
from vinhomes_api.work_offers import offer_work


def approved_order(database, category=CATEGORY):
    """Use the resident, management and plan APIs to create a dispatchable job."""
    with client(database) as resident:
        case, _, _ = create(resident, description=f"Staff dispatch check {uuid4().hex[:8]}")
    with client(database, "management") as manager:
        intake = manager.post(OPS + "/" + case["id"] + "/tickets", headers=key(), json={
            "expectedVersion": case["version"], "categoryId": CATEGORY})
        assert intake.status_code == 201, intake.text
        ticket = intake.json()["ticketId"]
        version = manager.get("/tickets/" + ticket).json()["ticket"]["version"]
        plan = manager.post(f"/tickets/{ticket}/plans", json={
            "title": "Dispatch check", "ticket_version": version, "idempotency_key": str(uuid4()),
            "steps": [{"category_id": category, "description": "Complete assigned specialty work"}]})
        assert plan.status_code == 201, plan.text
        decided = manager.post(f"/plans/{plan.json()['id']}/management-decision", json={
            "version": plan.json()["version"], "decision": "approve", "note": "Proceed"})
        assert decided.status_code == 200, decided.text
    with client(database) as resident:
        pending = resident.get(f"{BASE}/requests/{case['id']}/plans").json()["items"][0]
        decided = resident.post(f"{BASE}/requests/{case['id']}/plans/{pending['id']}/decision", headers=key(), json={
            "expectedVersion": pending["version"], "decision": "approve", "note": "Proceed"})
        assert decided.status_code == 200, decided.text
    with client(database, "admin") as admin:
        order = admin.get("/tickets/" + ticket).json()["workOrders"][0]
    return order, plan.json()["id"]


def offer(database, order, staff_id):
    with client(database, "management") as manager:
        return manager.post(f"/work-orders/{order['id']}/assignments", json={
            "staff_id": str(staff_id), "work_order_version": order["version"],
            "offer_expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat()})


def accept(worker, assignment):
    accepted = worker.post(f"/assignments/{assignment['id']}/response", json={
        "status": "accepted", "eta_at": datetime.now(UTC).isoformat()})
    assert accepted.status_code == 200, accepted.text
    return worker.get(f"/work-orders/{assignment['work_order_id']}").json()["workOrder"]


def advance(worker, order, status):
    return worker.patch(f"/work-orders/{order['id']}/status", json={
        "version": order["version"], "status": status, "note": "Staff dispatch regression"})


def test_manual_dispatch_rejects_a_worker_without_the_work_specialty(database):
    technical = sql(database, "select id from staff_profiles where user_id='local-v3-technical'")[0]["id"]
    security = sql(database, "select id from staff_profiles where user_id='local-v3-security'")[0]["id"]
    category = str(uuid4())
    sql(database, "insert into service_categories(id,tenant_id,code,name) values($1,$2,'cleaning','Vệ sinh & cảnh quan') returning id",
        UUID(category), TENANT)
    # The existing second staff identity is given only the cleaning specialty for this fixture.
    sql(database, "insert into staff_specialties(tenant_id,staff_id,category_id,proficiency) values($1,$2,$3,'standard') returning staff_id",
        TENANT, security, UUID(category))
    order, _ = approved_order(database, category)
    refused = offer(database, order, technical)
    assert refused.status_code == 422, refused.text
    assert sql(database, "select status from work_orders where id=$1", UUID(order["id"])) == [{"status": "queued"}]
    offered = offer(database, order, security)
    assert offered.status_code == 201, offered.text
    with client(database, "technical") as wrong_worker, client(database, "security") as cleaning_worker:
        assert not any(job["id"] == order["id"] for job in wrong_worker.get("/my-work-orders").json()["items"])
        mine = cleaning_worker.get("/my-work-orders").json()["items"]
        assert any(job["id"] == order["id"] and job["assignment_status"] == "offered" for job in mine)
        assert wrong_worker.post(f"/assignments/{offered.json()['id']}/response", json={
            "status": "accepted", "eta_at": datetime.now(UTC).isoformat()}).status_code == 403


def test_accepted_jobs_queue_and_concurrent_starts_allow_only_one_active_order(database):
    sql(database, "update staff_profiles set max_concurrent_jobs=2 where user_id='local-v3-technical' returning id")
    staff = sql(database, "select id from staff_profiles where user_id='local-v3-technical'")[0]["id"]
    orders = [approved_order(database)[0] for _ in range(2)]
    assignments = [offer(database, order, staff) for order in orders]
    assert all(response.status_code == 201 for response in assignments), [response.text for response in assignments]
    with client(database, "technical") as worker:
        accepted = [accept(worker, response.json()) for response in assignments]
        mine = worker.get("/my-work-orders").json()["items"]
        assert all(next(job for job in mine if job["id"] == order["id"])["status"] == "accepted" for order in accepted)

    def start(order):
        with client(database, "technical") as worker:
            return advance(worker, order, "en_route")

    with ThreadPoolExecutor(max_workers=2) as pool:
        attempts = list(pool.map(start, accepted))
    assert sorted(response.status_code for response in attempts) == [200, 409], [response.text for response in attempts]
    active_index = next(index for index, response in enumerate(attempts) if response.status_code == 200)
    active, queued = attempts[active_index].json(), accepted[1 - active_index]
    with client(database, "technical") as worker:
        waiting = worker.get(f"/work-orders/{queued['id']}").json()["workOrder"]
        assert waiting["status"] == "accepted" and waiting["version"] == queued["version"]
        cancelled = advance(worker, active, "cancelled")
        assert cancelled.status_code == 200, cancelled.text
        promoted = advance(worker, queued, "en_route")
        assert promoted.status_code == 200, promoted.text
        assert advance(worker, promoted.json(), "cancelled").status_code == 200


def test_completed_work_releases_capacity_and_offers_the_next_supervisor_job(database):
    sql(database, "update staff_profiles set max_concurrent_jobs=1 where user_id='local-v3-technical' returning id")
    staff = sql(database, "select id from staff_profiles where user_id='local-v3-technical'")[0]["id"]
    first, _ = approved_order(database)
    next_order, next_plan = approved_order(database)
    # The queued plan has the same persisted actor/approval shape as an automatic Supervisor plan.
    sql(database, "update vh_ticket_plans set proposed_by=null,proposed_by_client_id='demo-platform',management_by=null where id=$1 returning id",
        UUID(next_plan))
    assignment = offer(database, first, staff)
    assert assignment.status_code == 201, assignment.text
    capacity = offer(database, next_order, staff)
    assert capacity.status_code == 409 and "busy" in capacity.text, capacity.text
    with client(database, "technical") as worker:
        order = accept(worker, assignment.json())
        for status in ("en_route", "arrived"):
            changed = advance(worker, order, status)
            assert changed.status_code == 200, changed.text
            order = changed.json()
        proposed = worker.post(f"/work-orders/{order['id']}/repair-proposal", json={
            "version": order["version"], "note": "Additional repair needing new consent", "labor_cost": 10000})
        assert proposed.status_code == 201, proposed.text
        order = worker.get(f"/work-orders/{order['id']}").json()["workOrder"]
        refused = advance(worker, order, "in_progress")
        assert refused.status_code == 409 and "approve" in refused.text, refused.text
        listed = next(job for job in worker.get("/my-work-orders").json()["items"] if job["id"] == order["id"])
        assert listed["repair_approval_status"] == "pending"
        denied = worker.post(f"/work-orders/{order['id']}/repair-proposal/onsite-decision", json={
            "version": order["version"], "approved": False})
        assert denied.status_code == 200, denied.text
        listed = next(job for job in worker.get("/my-work-orders").json()["items"] if job["id"] == order["id"])
        assert listed["status"] == "arrived" and listed["repair_approval_status"] == "rejected"
        order = worker.get(f"/work-orders/{order['id']}").json()["workOrder"]
        assert advance(worker, order, "in_progress").status_code == 409
        revised = worker.post(f"/work-orders/{order['id']}/repair-proposal", json={
            "version": order["version"], "note": "Revised repair quote after resident refusal", "labor_cost": 5000})
        assert revised.status_code == 201, revised.text
        assert revised.json()["id"] != proposed.json()["id"]
        listed = next(job for job in worker.get("/my-work-orders").json()["items"] if job["id"] == order["id"])
        assert listed["status"] == "awaiting_approval" and listed["repair_approval_status"] == "pending"
        order = worker.get(f"/work-orders/{order['id']}").json()["workOrder"]
        decided = worker.post(f"/work-orders/{order['id']}/repair-proposal/onsite-decision", json={
            "version": order["version"], "approved": True})
        assert decided.status_code == 200, decided.text
        listed = next(job for job in worker.get("/my-work-orders").json()["items"] if job["id"] == order["id"])
        assert listed["repair_approval_status"] == "approved"
        started = advance(worker, order, "in_progress")
        assert started.status_code == 200, started.text
        order = started.json()
        missing_before = advance(worker, order, "completed")
        assert missing_before.status_code == 409 and "before-work evidence" in missing_before.text
        for purpose in ("before", "after"):
            uploaded = worker.post(f"/tickets/{first['ticket_id']}/files", content=image(),
                headers={"Content-Type": "application/octet-stream"},
                params={"filename": purpose + ".png", "mimeType": "image/png", "purpose": purpose})
            assert uploaded.status_code == 201, uploaded.text
            version = worker.get(f"/tickets/{first['ticket_id']}").json()["ticket"]["version"]
            evidence = worker.post(f"/tickets/{first['ticket_id']}/evidence", json={
                "file_id": uploaded.json()["fileId"], "work_order_id": order["id"],
                "assignment_id": assignment.json()["id"], "purpose": purpose, "version": version})
            assert evidence.status_code == 201, evidence.text
            if purpose == "before":
                missing_after = advance(worker, order, "completed")
                assert missing_after.status_code == 409 and "completion evidence" in missing_after.text
        completed = advance(worker, order, "completed")
        assert completed.status_code == 200, completed.text
        next_visible = next(job for job in worker.get("/my-work-orders").json()["items"] if job["id"] == next_order["id"])
        assert next_visible["status"] == "offered" and next_visible["assignment_status"] == "offered"
        approvals = sql(database, "select kind,status from work_approvals where work_order_id=$1", UUID(order["id"]))
        assert {"kind": "customer_completion", "status": "pending"} in approvals
        rejected = worker.post(f"/assignments/{next_visible['assignment_id']}/response", json={
            "status": "rejected", "rejection_reason": "Release this test fixture's queue slot"})
        assert rejected.status_code == 200, rejected.text


def test_expired_offers_are_not_presented_as_new_work(database):
    sql(database, "update staff_profiles set max_concurrent_jobs=3 where user_id='local-v3-technical' returning id")
    staff = sql(database, "select id from staff_profiles where user_id='local-v3-technical'")[0]["id"]
    order, _ = approved_order(database)
    assignment = offer(database, order, staff)
    assert assignment.status_code == 201, assignment.text
    sql(database, "update work_assignments set offer_expires_at=now()+interval '1 second' where id=$1 returning id",
        UUID(assignment.json()["id"]))
    time.sleep(1.2)
    with client(database, "technical") as worker:
        job = next(job for job in worker.get("/my-work-orders").json()["items"] if job["id"] == order["id"])
        assert job["assignment_status"] == "expired"


def test_simultaneous_supervisor_offers_do_not_exceed_staff_capacity(database):
    sql(database, "update staff_profiles set max_concurrent_jobs=1 where user_id='local-v3-technical' returning id")
    orders = [approved_order(database)[0] for _ in range(2)]
    barrier = Barrier(2)

    def dispatch(order):
        async def run():
            engine = create_async_engine(database["runtime"])
            try:
                async with engine.begin() as connection:
                    await connection.execute(text("select set_config('app.tenant_id',:tenant,true)"), {"tenant": str(TENANT)})
                    return await offer_work(connection, UUID(order["ticket_id"]), UUID(order["id"]), "demo-platform")
            finally:
                await engine.dispose()
        barrier.wait()
        return asyncio.run(run())

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(dispatch, orders)) == [False, True]
    statuses = sql(database, "select status,count(*) as n from work_orders where id=any($1::uuid[]) group by status",
                   [UUID(order["id"]) for order in orders])
    assert {row["status"]: row["n"] for row in statuses} == {"offered": 1, "queued": 1}
