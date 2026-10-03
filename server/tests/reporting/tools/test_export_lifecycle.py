"""Exercise real route decisions with stored fake rows, not canned repeated IDs.

PostgreSQL locks, RLS and transaction commits are deliberately NOT simulated.
"""

import asyncio
import io
from uuid import NAMESPACE_URL, UUID, uuid5
from zipfile import ZipFile

import httpx
import pytest
from fastapi import FastAPI, Request
from reporting.application.client import ReportBackend
from reporting.tools import ReportTools, RuntimeContext
from test_backend_routes import FakeDatabase, Rows
from test_tools import B1, B2, CATEGORY, PERIOD
from vinhomes_api.v3_auth import scoped_connection
from vinhomes_api.v3_report_jobs import router


class StoredFakeDatabase(FakeDatabase):
    def __init__(self):
        super().__init__()
        self.receipts = {}
        self.exports = {}
        self.allowed = {("A", B1), ("B", B1)}
        self.insert_count = 0
        self.content_reads = 0
        self.report_queries = 0

    async def execute(self, sql, params=None):
        query = " ".join(str(sql).split()).lower()
        if "join scoped_user_roles r" in query and query.startswith(
            "select 1 from buildings b"
        ):
            pair = (params["actor_id"], str(params["building_id"]))
            return Rows([{"exists": 1}] if pair in self.allowed else [])
        if query.startswith("select id,request_hash from vh_report_exports"):
            receipt = self.receipts.get((params["actor"], params["key"]))
            return Rows([receipt] if receipt else [])
        if query.startswith("insert into vh_report_exports"):
            self.insert_count += 1
            identifier = uuid5(NAMESPACE_URL, params["actor"] + ":" + params["key"])
            await super().execute(sql, params)
            row = {
                **self.export_row,
                "id": identifier,
                "created_by": params["actor"],
                "content": params["content"],
            }
            self.exports[str(identifier)] = row
            self.receipts[(params["actor"], params["key"])] = {
                "id": identifier,
                "request_hash": params["hash"],
            }
            return Rows(scalar=identifier)
        if query.startswith("select id,building_id,kind,status,error_code,created_at"):
            row = self.exports.get(str(params["id"]))
            if row is None or row["created_by"] != params["actor"]:
                return Rows()
            return Rows(
                [
                    {
                        key: row[key]
                        for key in (
                            "id",
                            "building_id",
                            "kind",
                            "status",
                            "error_code",
                            "created_at",
                        )
                    }
                ]
            )
        if query.startswith("select content from vh_report_exports"):
            self.content_reads += 1
            return Rows(scalar=self.exports[str(params["id"])]["content"])
        if query.startswith("select id from service_categories"):
            return Rows([{"id": UUID(CATEGORY)}])
        if query.startswith("select date_trunc(") and "from invoice_lines" in query:
            return Rows(
                [
                    {
                        "month": "2026-09-01",
                        "invoice_count": 1,
                        "net_amount": "100",
                        "tax_amount": "10",
                        "billed_amount": "110",
                        "currency": "VND",
                    }
                ]
            )
        if query.startswith(("with jobs as", "with amounts as", "select date_trunc(")):
            self.report_queries += 1
        return await super().execute(sql, params)


def setup():
    db, app = StoredFakeDatabase(), FastAPI()
    app.include_router(router)

    async def scope(request: Request):
        # Explicit test identity boundary. This is not an SSO test.
        yield db, request.cookies["actor"], False

    app.dependency_overrides[scoped_connection] = scope
    return db, app


def test_real_route_replay_and_changed_payload_conflict():
    async def run():
        db, app = setup()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app)) as client:
            tools = ReportTools(
                ReportBackend("https://business.example", client=client),
                RuntimeContext("A", (B1,), "actor=A"),
            )
            args = {
                **PERIOD,
                "kind": "incident_frequency",
                "idempotency_key": "fixed-key",
            }
            a = await tools.create_report_export(args)
            b = await tools.create_report_export(args)
            assert a["outcome"] == b["outcome"] == "success"
            assert a["data"]["reportId"] == b["data"]["reportId"]
            assert db.insert_count == 1
            changed = await tools.create_report_export(
                {**args, "to_date": "2026-10-02"}
            )
            assert (
                changed["error"] == "REPORT_CONFLICT"
                and not changed["execution_unknown"]
            )
            assert db.insert_count == 1

    asyncio.run(run())


def test_same_key_is_separate_for_two_principals_and_owner_guard_applies():
    async def run():
        db, app = setup()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app)) as client:
            backend = ReportBackend("https://business.example", client=client)
            tools_a = ReportTools(backend, RuntimeContext("A", (B1,), "actor=A"))
            tools_b = ReportTools(backend, RuntimeContext("B", (B1,), "actor=B"))
            args = {
                **PERIOD,
                "kind": "incident_frequency",
                "idempotency_key": "same-key",
            }
            a, b = (
                await tools_a.create_report_export(args),
                await tools_b.create_report_export(args),
            )
            assert (
                a["data"]["reportId"] != b["data"]["reportId"] and db.insert_count == 2
            )
            denied = await tools_b.get_report_export_status(
                {"export_id": a["data"]["reportId"]}
            )
            assert denied["error"] == "REPORT_NOT_FOUND"

    asyncio.run(run())


def test_non_admin_building_revocation_blocks_status_replay_and_download():
    async def run():
        db, app = setup()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app)) as client:
            tools = ReportTools(
                ReportBackend("https://business.example", client=client),
                RuntimeContext("A", (B1,), "actor=A"),
            )
            args = {
                **PERIOD,
                "kind": "incident_frequency",
                "idempotency_key": "revoked-key",
            }
            result = await tools.create_report_export(args)
            export_id = result["data"]["reportId"]
            db.allowed.remove(("A", B1))
            status = await tools.get_report_export_status({"export_id": export_id})
            replay = await tools.create_report_export(args)
            download = await client.get(
                "https://business.example" + result["data"]["downloadUrl"],
                headers={"Cookie": "actor=A"},
            )
            assert status["error"] == replay["error"] == "REPORT_SCOPE_FORBIDDEN"
            assert (
                download.status_code == 403
                and db.content_reads == 0
                and db.insert_count == 1
            )

    asyncio.run(run())


def test_stale_runtime_grant_is_not_backend_authorization():
    async def run():
        db, app = setup()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app)) as client:
            tools = ReportTools(
                ReportBackend("https://business.example", client=client),
                RuntimeContext("A", (B1, B2), "actor=A"),
            )
            result = await tools.get_employee_performance_summary(
                {**PERIOD, "building_id": B2}
            )
            assert (
                result["error"] == "REPORT_SCOPE_FORBIDDEN" and db.report_queries == 0
            )

    asyncio.run(run())


@pytest.mark.parametrize("kind", ["incident_frequency", "issued_revenue"])
def test_download_matches_export_kind_and_period(kind):
    async def run():
        db, app = setup()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app)) as client:
            tools = ReportTools(
                ReportBackend("https://business.example", client=client),
                RuntimeContext("A", (B1,), "actor=A"),
            )
            args = {**PERIOD, "kind": kind, "idempotency_key": kind}
            if kind == "issued_revenue":
                args["category_id"] = CATEGORY
            result = await tools.create_report_export(args)
            assert result["outcome"] == "success"
            content = await client.get(
                "https://business.example" + result["data"]["downloadUrl"],
                headers={"Cookie": "actor=A"},
            )
            assert content.status_code == 200
            assert (
                content.headers["content-type"]
                == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
            with ZipFile(io.BytesIO(content.content)) as z:
                assert z.testzip() is None
                document = z.read("word/document.xml").decode()
                assert (
                    kind in document
                    and PERIOD["from_date"] in document
                    and PERIOD["to_date"] in document
                )
                if kind == "issued_revenue":
                    assert (
                        "billed_amount" in document
                        and "collected_amount" not in document
                    )
            assert db.content_reads == 1

    asyncio.run(run())
