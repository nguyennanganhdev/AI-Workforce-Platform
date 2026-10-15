"""Complete synthetic pilot on real PostgreSQL/API/MCP; Platform is a strict HTTP stub.

No Reception model, embeddings, real Platform or VPS. Optional persistent acceptance:
OWNER_SANDBOX_CONNECTION_FILE=<private connections.secret.json> (fresh sandbox only).
Otherwise uses a disposable database with RESIDENT_TEST_ADMIN_URL/RUNTIME_URL.
"""

import asyncio
import importlib.util
import json
import os
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID, uuid4

import asyncpg
import pytest
from fastapi.testclient import TestClient
from test_account_administration import door
from test_domain_database import operation
from test_platform_bridge import BRIDGE, FakePlatform, chat, link, say, sync
from test_platform_bridge import turns as turns  # noqa: PLC0414
from test_platform_mcp_v2 import BOOTSTRAP, call, version
from test_platform_tools import photo
from test_resident_contract import TestDatabase, key, sql
from test_staff_dispatch import accept, advance
from vinhomes_api import database as tool
from vinhomes_api import owner_sandbox
from vinhomes_api.bootstrap import bootstrap
from vinhomes_api.main import create_app
from vinhomes_api.owner_bundle import inspect_bundle
from vinhomes_api.v3_config import V3Settings

DEPLOY = Path(__file__).resolve().parents[3] / "deploy"


@contextmanager
def person(database, user):
    settings = V3Settings(
        "127.0.0.1",
        8097,
        database["runtime"],
        UUID(tool.TENANT),
        user,
        local_file_storage=True,
        resident_local_storage=True,
        resident_allowed_origins=("http://testserver",),
    )
    with TestClient(create_app(settings), client=("127.0.0.1", 50000)) as client:
        yield client


def generate(folder):
    spec = importlib.util.spec_from_file_location(
        "sandbox_generator", DEPLOY / "prepare-owner-sandbox.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.prepare(folder)


def test_bundle_covers_all_datasets_without_claiming_operator_approval(tmp_path):
    report = generate(tmp_path)
    assert report["valid"] and sum(report["counts"].values()) == 25
    report, rows, manifest = inspect_bundle(tmp_path)
    assert manifest["data_mode"] == "synthetic_test"
    assert {s["fee_policy"] for s in rows["services"]} == {"free", "fixed", "quote"}
    assert {s["audience"] for s in rows["sops"]} == {"resident", "staff"}
    assert all(
        "SIMULATION" in row["approved_by"] for values in rows.values() for row in values
    )
    assert not report["operational_activation"]
    with pytest.raises(ValueError, match="overwrite"):
        generate(tmp_path)


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://nobody@127.0.0.1/vinhomes",
        "postgresql://nobody@103.238.235.156/owner_pilot_test_" + "a" * 32,
    ],
)
def test_synthetic_activation_refuses_wrong_target_before_connect(url, tmp_path):
    with pytest.raises(ValueError, match="loopback owner_pilot_test"):
        asyncio.run(owner_sandbox.materialize(url, tmp_path))


@pytest.fixture(scope="module")
def database(tmp_path_factory):
    private = os.getenv("OWNER_SANDBOX_CONNECTION_FILE")
    if private:
        values = json.loads(Path(private).read_text())
        owner_sandbox.guard(values["admin"])
        # Only this explicitly requested synthetic DB may be retained/changed.
        yield TestDatabase(**values)
        return
    base, runtime = (
        os.getenv("RESIDENT_TEST_ADMIN_URL"),
        os.getenv("RESIDENT_TEST_RUNTIME_URL"),
    )
    if not base or not runtime:
        pytest.skip("Isolated PostgreSQL configuration required")
    name = "owner_pilot_test_" + uuid4().hex
    target = urlunsplit(urlsplit(base)._replace(path="/" + name))
    api = urlunsplit(urlsplit(runtime)._replace(path="/" + name)).replace(
        "postgresql:", "postgresql+asyncpg:"
    )
    owner_sandbox.guard(target)
    folder = tmp_path_factory.mktemp("complete-synthetic-bundle")
    generate(folder)

    async def setup():
        await tool.create(base, name)
        await tool.migrate(target)
        await bootstrap(target)
        conn = await asyncpg.connect(target)
        try:
            with pytest.raises(ValueError, match="marker"):
                await owner_sandbox.materialize(target, folder)
            await conn.execute(
                f"COMMENT ON DATABASE \"{name}\" IS '{owner_sandbox.MARKER}'"
            )
        finally:
            await conn.close()
        await tool.role(target, urlsplit(runtime).username, None)
        # A late failure must roll back previously inserted people, roles and policies.
        with pytest.MonkeyPatch.context() as patch:
            original = owner_sandbox.password_hash
            calls = 0

            def fail_after_admin(value):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise ValueError("Injected failure after admin insertion")
                return original(value)

            patch.setattr(owner_sandbox, "password_hash", fail_after_admin)
            with pytest.raises(ValueError, match="Injected failure"):
                await owner_sandbox.materialize(target, folder)
        conn = await asyncpg.connect(target)
        try:
            assert await conn.fetchval("select count(*) from users") == 0
            assert await conn.fetchval("select count(*) from units") == 0
        finally:
            await conn.close()
        return await owner_sandbox.materialize(target, folder)

    async def drop():
        conn = await asyncpg.connect(base)
        try:
            owner_sandbox.guard(target)
            await conn.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
        finally:
            await conn.close()

    try:
        result = asyncio.run(setup())
        yield TestDatabase(
            admin=target,
            runtime=api,
            credentials=result["credentials"],
            bundle=str(folder),
        )
    finally:
        asyncio.run(drop())


def test_runtime_data_accounts_and_private_source_boundary(database):
    expected = {
        "management_units": 1,
        "zones": 1,
        "buildings": 1,
        "units": 2,
        "users": 5,
        "accounts": 5,
        "unit_residents": 2,
        "staff_profiles": 2,
        "staff_shifts": 6,
        "management_coverage": 1,
        "domain_service_catalog": 3,
        "owner_operational_records": 25,
        "sla_policies": 1,
    }
    for table, count in expected.items():
        assert sql(database, "select count(*) as n from " + table)[0]["n"] == count
    assert (
        sql(
            database,
            "select count(*) as n from scoped_user_roles where role_code='management'",
        )[0]["n"]
        == 0
    )
    assert (
        sql(
            database,
            "select count(*) as n from owner_data_records where operational_verified",
        )[0]["n"]
        == 0
    )
    assert (
        sql(
            database,
            "select count(*) as n from vh_knowledge_documents where category='synthetic-sop' and unverified",
        )[0]["n"]
        == 6
    )
    credentials = database.get("credentials")
    if not credentials:
        credentials = json.loads(
            Path(os.environ["OWNER_SANDBOX_CONNECTION_FILE"])
            .with_name("accounts.secret.json")
            .read_text(encoding="utf-8")
        )
    for account in credentials:
        with door(database) as c:
            result = c.post(
                "/auth/login",
                json={"identifier": account["email"], "password": account["password"]},
            )
            assert result.status_code == 200
            session = c.get("/auth/session").json()
            assert session["administrator"] == (account["role"] == "admin")
            if account["role"] == "staff":
                assert session["operationsRole"] == "staff"

    async def runtime_boundary():
        conn = await asyncpg.connect(tool._url(database["runtime"]))
        try:
            role = await conn.fetchrow(
                "select rolsuper,rolbypassrls from pg_roles where rolname=current_user"
            )
            assert not role["rolsuper"] and not role["rolbypassrls"]
            for table in ("owner_operational_batches", "owner_operational_records"):
                with pytest.raises(asyncpg.InsufficientPrivilegeError):
                    await conn.fetch("select * from " + table)
        finally:
            await conn.close()

    asyncio.run(runtime_boundary())


def test_synthetic_api_mcp_staff_resident_happy_case(
    database, monkeypatch, tmp_path, turns
):
    import vinhomes_api.v3_files as files
    import vinhomes_api.v3_resident_support as support

    # Retained DB evidence must survive pytest's temporary-directory cleanup.
    private = os.getenv("OWNER_SANDBOX_CONNECTION_FILE")
    file_root = Path(private).resolve().with_name("files") if private else tmp_path
    file_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(files, "FILE_ROOT", file_root)
    monkeypatch.setattr(support, "FILE_ROOT", file_root)
    monkeypatch.setenv("VINHOMES_API_PLATFORM_URL", BRIDGE.url)
    monkeypatch.setenv("VINHOMES_API_PLATFORM_MCP_TOKEN", BOOTSTRAP)
    monkeypatch.setenv("VINHOMES_API_MCP_ALLOWED_HOSTS", "testserver")
    monkeypatch.delenv("VINHOMES_API_EMBEDDING_API_KEY", raising=False)
    monkeypatch.setenv("VINHOMES_API_S3_ENDPOINT", "")
    fake = FakePlatform()
    with person(database, "sim-resident-1") as resident:
        place = operation(resident, "get_verified_resident_context")[0]["residences"][0]
        channel = resident.post(
            "/resident/chats", json={"title": "MÔ PHỎNG: nghiệm thu dữ liệu"}
        ).json()["id"]
        message = say(resident, channel, "MÔ PHỎNG: Đèn phòng khách không sáng")
        draft, _ = operation(
            resident,
            "create_ticket_draft",
            {
                "channel_id": channel,
                "domain_id": place["domain_id"],
                "building_id": place["building_id"],
                "unit_id": place["unit_id"],
                "category_id": str(owner_sandbox.CATEGORY),
            },
        )
        target = {"channel_id": channel, "draft_id": draft["draftId"]}
        operation(
            resident,
            "update_ticket_incident",
            {
                **target,
                "fields": {
                    "request_kind": "service_request",
                    "source_message_id": message,
                    "facts": [
                        {
                            "key": "item",
                            "value": "đèn phòng khách",
                            "source": "customer_report",
                            "source_message_id": message,
                        },
                        {
                            "key": "symptom",
                            "value": "không sáng",
                            "source": "customer_report",
                            "source_message_id": message,
                        },
                    ],
                },
            },
        )
        operation(
            resident,
            "submit_ticket_assessment",
            {
                **target,
                "assessment": {
                    "priority": "normal",
                    "severity": "minor",
                    "reason": "MÔ PHỎNG: sự cố thông thường",
                },
            },
        )
        handoff, _ = operation(
            resident, "handoff_ticket", {**target, "plan_required": False}
        )
        assert handoff["accepted"], handoff
        ticket = handoff["ticket"]["id"]
    sync(database, fake)
    flow = next(f for f in fake.flows.values() if f["ticket"] == ticket)
    assert link(database, ticket)["status"] == "open"
    command = sql(
        database,
        "select id from platform_commands where ticket_id=$1 and kind='start_workflow'",
        UUID(ticket),
    )[0]["id"]
    with door(database) as platform:
        granted = platform.post(
            "/platform/mcp-grants",
            headers={"Authorization": "Bearer " + BOOTSTRAP},
            json={
                "ticket_id": ticket,
                "external_request_id": str(command),
                "workflow_id": flow["workflow_id"],
                "grant_request_id": str(uuid4()),
                "tools": [
                    "vh_ticket_get",
                    "vh_staff_available",
                    "vh_work_order_dispatch",
                ],
                "ttl_seconds": 3600,
            },
        )
        assert granted.status_code == 200, granted.text
        token = granted.json()["bearer_token"]
        snapshot = call(platform, token, "vh_ticket_get", {"ticket_id": ticket})
        assert (
            snapshot["sla"]["response_due_at"] and snapshot["sla"]["resolution_due_at"]
        )
        assert (
            call(platform, token, "vh_ticket_get", {"ticket_id": str(uuid4())}, True)[
                "error"
            ]["code"]
            == "TICKET_SCOPE_FORBIDDEN"
        )
        dispatch = {
            "ticket_id": ticket,
            "client_reference": "cr_" + uuid4().hex,
            "description": "MÔ PHỎNG: kiểm tra và thay bóng đèn",
            "expected_ticket_version": version(database, UUID(ticket)),
        }
        answer = call(platform, token, "vh_work_order_dispatch", dispatch)
        assert answer["status"] == "pending", answer
        job = answer["external_job_id"]
        assert (
            call(platform, token, "vh_work_order_dispatch", dispatch)["external_job_id"]
            == job
        )
    assert (
        sql(
            database,
            "select count(*) as n from work_orders where ticket_id=$1",
            UUID(ticket),
        )[0]["n"]
        == 1
    )
    assignment = sql(
        database,
        "select a.id,p.user_id from work_assignments a join staff_profiles p on p.id=a.staff_id where a.work_order_id=$1",
        UUID(job),
    )[0]
    staff = assignment["user_id"]
    colleague = "sim-tech-2" if staff == "sim-tech-1" else "sim-tech-1"
    with person(database, colleague) as other:
        assert other.post(
            f"/assignments/{assignment['id']}/response",
            json={
                "status": "rejected",
                "rejection_reason": "Must not change a colleague assignment",
            },
        ).status_code in (403, 404)
    with person(database, staff) as worker:
        order = accept(worker, {"id": str(assignment["id"]), "work_order_id": job})
        for status in ("en_route", "arrived"):
            response = advance(worker, order, status)
            assert response.status_code == 200, response.text
            order = response.json()
        proposal = worker.post(
            f"/work-orders/{job}/repair-proposal",
            json={
                "version": order["version"],
                "note": "MÔ PHỎNG: thay bóng",
                "labor_cost": 50000,
                "warranty_months": 3,
                "lines": [
                    {
                        "name": "Bóng mô phỏng",
                        "quantity": "1",
                        "unit": "cái",
                        "unit_price": 75000,
                    }
                ],
            },
        )
        assert proposal.status_code == 201, proposal.text
        approval = proposal.json()["id"]
    with person(database, "sim-resident-1") as resident:
        early = resident.post(
            f"/resident/approvals/{approval}/decision",
            headers=key(),
            json={
                "version": version(database, UUID(ticket)),
                "approved": True,
                "note": "Premature simulated approval",
            },
        )
        assert (
            early.status_code == 409
        )  # Platform has not yet received/published the quote.
    sync(database, fake)
    assert any(
        m.get("platform", {}).get("kind") == "quote" for m in chat(database, channel)
    )
    with person(database, "sim-resident-2") as other:
        assert other.get(f"/resident/tickets/{ticket}").status_code == 404
        assert other.post(
            f"/resident/approvals/{approval}/decision",
            headers=key(),
            json={
                "version": version(database, UUID(ticket)),
                "approved": True,
                "note": "Other resident must be refused",
            },
        ).status_code in (403, 404)
    with person(database, "sim-resident-1") as resident:
        agreed = resident.post(
            f"/resident/approvals/{approval}/decision",
            headers=key(),
            json={
                "version": version(database, UUID(ticket)),
                "approved": True,
                "note": "Đồng ý mô phỏng",
            },
        )
        assert agreed.status_code == 200, agreed.text
    with person(database, staff) as worker:
        order = worker.get(f"/work-orders/{job}").json()["workOrder"]
        started = advance(worker, order, "in_progress")
        assert started.status_code == 200, started.text
        assert advance(worker, started.json(), "completed").status_code == 409
        for purpose in ("before", "after", "verification"):
            photo(worker, ticket, job, str(assignment["id"]), purpose)
        done = advance(worker, started.json(), "completed")
        assert done.status_code == 200, done.text
        accepted = worker.post(
            f"/work-orders/{job}/onsite-acceptance",
            json={
                "version": done.json()["version"],
                "note": "MÔ PHỎNG: đã sửa, đủ ảnh và kết quả",
            },
        )
        assert accepted.status_code == 201, accepted.text
    sync(database, fake)
    sync(database, fake)
    kinds = [
        "job.offered",
        "job.accepted",
        "job.en_route",
        "job.arrived",
        "job.quote_ready",
        "job.quote_approved",
        "job.started",
        "job.completed",
        "job.result_published",
    ]
    assert [r["body"]["event_type"] for r in fake.received.values()] == kinds
    assert all(r["body"]["external_job_id"] == job for r in fake.received.values())
    assert "@op1-sandbox.test" not in json.dumps(
        [r["body"] for r in fake.received.values()]
    )
    approval = sql(
        database,
        "select id from work_approvals where work_order_id=$1 and kind='customer_completion'",
        UUID(job),
    )[0]["id"]
    with person(database, "sim-resident-1") as resident:
        assert not any(
            str(a["id"]) == str(approval)
            for a in resident.get("/resident/approvals").json()["items"]
        )
    fake.say(flow, "MÔ PHỎNG: Platform đã nhận kết quả, mời cư dân nghiệm thu.")
    fake.move(flow, "awaiting_confirmation", "operation_completed")
    sync(database, fake)
    with person(database, "sim-resident-1") as resident:
        body = {
            "version": version(database, UUID(ticket)),
            "approved": True,
            "note": "Xác nhận hoàn thành mô phỏng",
        }
        headers = key()
        response = resident.post(
            f"/resident/approvals/{approval}/decision", headers=headers, json=body
        )
        assert response.status_code == 200, response.text
        assert (
            resident.post(
                f"/resident/approvals/{approval}/decision", headers=headers, json=body
            ).json()
            == response.json()
        )
    sync(database, fake)
    assert sql(database, "select status from tickets where id=$1", UUID(ticket)) == [
        {"status": "closed"}
    ]
    assert link(database, ticket)["status"] == "closed"
    assert {
        r["status"]
        for r in sql(
            database,
            "select status from platform_outbox where ticket_id=$1",
            UUID(ticket),
        )
    } == {"sent"}
    # Never accept destructive reruns which would replace user passwords/history.
    folder = Path(
        database.get("bundle")
        or Path(os.environ["OWNER_SANDBOX_CONNECTION_FILE"]).with_name("bundle")
    )
    with pytest.raises(ValueError, match="empty operational"):
        asyncio.run(owner_sandbox.materialize(database["admin"], folder))
