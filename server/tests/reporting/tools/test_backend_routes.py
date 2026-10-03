"""Real FastAPI route contract, with an explicitly fake SQL result boundary.

This checks serialization/input mapping, not PostgreSQL SQL semantics or SSO.
"""

import asyncio
import sys
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import httpx
from fastapi import FastAPI, HTTPException

sys.path.insert(
    0, str(Path(__file__).resolve().parents[4] / "services" / "vinhomes-api" / "src")
)

from reporting.application.client import ReportBackend
from reporting.tools import ReportTools, RuntimeContext
from vinhomes_api.v3_auth import scoped_connection
from vinhomes_api.v3_report_jobs import router

B1 = "11111111-1111-4111-8111-111111111111"
STAFF = "33333333-3333-4333-8333-333333333333"
CATEGORY = "44444444-4444-4444-8444-444444444444"
EXPORT = "55555555-5555-4555-8555-555555555555"
PERIOD = {"building_id": B1, "from_date": "2026-09-01", "to_date": "2026-10-01"}


class Rows:
    def __init__(self, rows=(), scalar=None):
        self.rows, self.scalar = list(rows), scalar

    def mappings(self):
        return self

    def __iter__(self):
        return iter(self.rows)

    def first(self):
        return self.rows[0] if self.rows else None

    def scalar_one(self):
        return self.scalar


class FakeDatabase:
    def __init__(self):
        self.export_row = None

    async def execute(self, sql, params=None):
        query = " ".join(str(sql).split()).lower()
        if "select 1 from buildings" in query:
            return Rows([{"exists": 1}])
        if query.startswith("select id,name from buildings"):
            return Rows([{"id": UUID(B1), "name": "Tòa A"}])
        if query.startswith("select id,name,code from service_categories"):
            return Rows([{"id": UUID(CATEGORY), "name": "Điện", "code": "electric"}])
        if query.startswith("select distinct sp.id,u.name,sp.employee_code"):
            return Rows(
                [{"id": UUID(STAFF), "name": "Kỹ thuật A", "employee_code": "E01"}]
            )
        if query.startswith("with jobs as"):
            return Rows(
                [
                    {
                        "staff_id": UUID(STAFF),
                        "name": "Kỹ thuật A",
                        "assigned_count": 4,
                        "completed_count": 2,
                        "timed_completion_count": 2,
                        "on_time_count": 1,
                        "average_processing_seconds": Decimal(300),
                        "redo_count": 1,
                        "average_rating": Decimal("4.5"),
                        "rating_count": 2,
                    }
                ]
            )
        if query.startswith("with amounts as"):
            return Rows(
                [
                    {
                        "currency": "VND",
                        "billed_amount": Decimal("100000.10"),
                        "collected_amount": Decimal("80000.05"),
                        "outstanding_amount": Decimal("20000.05"),
                        "billed_work_count": 1,
                        "invoice_count": 1,
                    }
                ]
            )
        if "from ticket_reviews r join tickets" in query:
            return Rows(
                [
                    {
                        "id": UUID(EXPORT),
                        "score": 5,
                        "comment": "Tốt",
                        "ticket_id": UUID(EXPORT),
                    }
                ]
            )
        if query.startswith("select date_trunc("):
            return Rows(
                [
                    {
                        "period": date(2026, 9, 1),
                        "month": date(2026, 9, 1),
                        "category_id": UUID(CATEGORY),
                        "incident_type_id": UUID(CATEGORY),
                        "category_name": "Điện",
                        "incident_type": "Mất điện",
                        "incident_count": 2,
                    }
                ]
            )
        if query.startswith("select t.id,t.code,t.title"):
            return Rows(
                [
                    {
                        "id": UUID(EXPORT),
                        "code": "VH-1",
                        "title": "Mất điện",
                        "status": "closed",
                    }
                ]
            )
        if query.startswith("select id,request_hash from vh_report_exports"):
            return Rows()
        if query.startswith("insert into vh_report_exports"):
            self.export_row = {
                "id": UUID(EXPORT),
                "building_id": params["building"],
                "kind": params["kind"],
                "status": "ready",
                "error_code": None,
                "created_at": datetime(2026, 10, 1, tzinfo=timezone.utc),
            }
            assert params["content"].startswith(b"PK")
            return Rows(scalar=UUID(EXPORT))
        if query.startswith("select id,building_id,kind,status,error_code,created_at"):
            return Rows([self.export_row] if self.export_row else [])
        if "pg_advisory_xact_lock" in query:
            return Rows()
        raise AssertionError("Unhandled fake SQL boundary: " + query[:100])


def test_all_tools_against_current_backend_routes():
    async def run():
        app = FastAPI()
        app.include_router(router)
        db = FakeDatabase()

        async def scope():
            yield db, "verified-A", True

        app.dependency_overrides[scoped_connection] = scope
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app)) as client:
            backend = ReportBackend(
                "https://business.example", client=client, read_retries=0
            )
            tools = ReportTools(backend, RuntimeContext("A", (B1,), "session=A"))
            args = {
                "get_report_filter_options": {},
                "get_employee_performance_summary": PERIOD,
                "get_employee_feedback_details": {"building_id": B1, "staff_id": STAFF},
                "get_repair_revenue_summary": {**PERIOD, "category_id": CATEGORY},
                "get_incident_frequency_summary": PERIOD,
                "get_report_supporting_records": PERIOD,
                "create_report_export": {
                    **PERIOD,
                    "kind": "incident_frequency",
                    "idempotency_key": "run-A-export",
                },
                "get_report_export_status": {"export_id": EXPORT},
            }
            for operation, arguments in args.items():
                result = await tools.invoke(operation, arguments)
                assert result["outcome"] in ("success", "partial"), (operation, result)
                if operation == "get_employee_performance_summary":
                    assert result["data"]["items"][0]["on_time_rate"] == 0.5
                if operation == "get_repair_revenue_summary":
                    assert result["data"]["items"][0]["billed_amount"] == "100000.10"

            async def revoked():
                raise HTTPException(403, "Grant revoked")

            app.dependency_overrides[scoped_connection] = revoked
            result = await tools.get_report_export_status({"export_id": EXPORT})
            assert result["error"] == "REPORT_SCOPE_FORBIDDEN"

    asyncio.run(run())
