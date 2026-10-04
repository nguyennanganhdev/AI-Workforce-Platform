"""Actual six backend routes; SQL result boundary and authentication are explicit fakes."""

import asyncio
from copy import deepcopy
from datetime import datetime
from decimal import Decimal
from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI
from helpers import ARGS, B1, B2, CATALOG, STAFF, STAR_ARGS, TYPE, Z1, dataset
from reporting.application.client import ReportBackend
from reporting.tools import ReportTools, RuntimeContext
from vinhomes_api.v3_auth import scoped_connection
from vinhomes_api.v3_billing import router as billing
from vinhomes_api.v3_operations import router as operations
from vinhomes_api.v3_report_jobs import router as reports


class Rows:
    def __init__(self, rows=(), scalar=None):
        self.rows, self.scalar = list(rows), scalar

    def mappings(self):
        return self

    def all(self):
        return self.rows

    def first(self):
        return self.rows[0] if self.rows else None

    def scalar_one(self):
        return self.scalar

    def __iter__(self):
        return iter(self.rows)


class FakeSQL:
    def __init__(self, grants):
        self.data, self.grants = dataset(), grants

    async def execute(self, sql, params=None):
        query = " ".join(str(sql).lower().split())
        params = params or {}
        building = str(
            params.get("building", params.get("building_id", params.get("id", "")))
        )
        if query.startswith("select id, site_id, zone_id, code, name from buildings"):
            return Rows(
                [
                    {**b, "site_id": UUID(Z1), "code": b["name"]}
                    for b in CATALOG["buildings"]
                ]
            )
        if query.startswith("select id, site_id, code, name from zones"):
            return Rows(
                [
                    {**z, "site_id": UUID(Z1), "code": z["name"]}
                    for z in CATALOG["zones"]
                ]
            )
        if query.startswith("select id,name from buildings"):
            return Rows(deepcopy(CATALOG["buildings"]))
        if query.startswith(
            ("select 1 from buildings b", "select 1 from scoped_user_roles")
        ):
            return Rows(
                [{"allowed": 1}]
                if building in self.grants
                or query.startswith("select 1 from scoped_user_roles")
                else []
            )
        if query.startswith("select distinct sp.id,u.name,sp.employee_code"):
            return Rows([{"id": UUID(STAFF), "name": "A", "employee_code": "A01"}])
        if query.startswith("select id,name,code from service_categories"):
            return Rows([{"id": UUID(TYPE), "name": "Điện", "code": "electric"}])
        if query.startswith("select i.id,i.invoice_no"):
            values = deepcopy(self.data["invoices"][building])
            for value in values:
                value["grand_total"] = Decimal(value["grand_total"])
                value["issued_at"] = datetime.fromisoformat(value["issued_at"])
            return Rows(values)
        if query.startswith("select t.id,t.code,t.title"):
            return Rows(deepcopy(self.data["tickets"][building]))
        if query.startswith("select date_trunc"):
            return Rows(
                [
                    {
                        "period": "2026-09-01",
                        "category_id": UUID(TYPE),
                        "category_name": "Điện",
                        "incident_type_id": UUID(TYPE),
                        "incident_type": "Điện",
                        "incident_count": 2,
                    }
                ]
            )
        if query.startswith("select r.id,r.score"):
            return Rows(
                deepcopy(
                    self.data["feedback"].get((building, str(params["staff"])), [])
                )
            )
        if query.startswith("select * from invoices"):
            value = deepcopy(self.data["details"][str(params["id"])]["invoice"])
            value["grand_total"] = Decimal(value["grand_total"])
            value["issued_at"] = datetime.fromisoformat(value["issued_at"])
            return Rows([value])
        if query.startswith("select * from invoice_lines"):
            values = deepcopy(self.data["details"][str(params["id"])]["lines"])
            for value in values:
                value["total_amount"] = Decimal(value["total_amount"])
            return Rows(values)
        if query.startswith("select coalesce(sum(pa.amount)"):
            return Rows(scalar=0)
        if query.startswith("select t.id, t.status"):
            for b, invoices in self.data["invoices"].items():
                if invoices[0]["ticket_id"] == str(params["ticket_id"]):
                    return Rows(
                        [
                            {
                                "id": params["ticket_id"],
                                "building_id": UUID(b),
                                "zone_id": UUID(Z1),
                                "site_id": UUID(Z1),
                                "management_unit_id": UUID(Z1),
                            }
                        ]
                    )
        if "from" in query and query.startswith(("select id,", "select sp.id,")):
            return Rows()
        raise AssertionError("Uncovered SQL fake: " + query)


@pytest.mark.parametrize(
    "operation,args",
    [
        ("filter_report_scope", {}),
        ("get_repair_bill_summary", ARGS),
        ("get_ticket_frequency_summary", ARGS),
        ("get_employee_star_summary", STAR_ARGS),
    ],
)
def test_four_tools_with_existing_real_fastapi_routes(operation, args):
    async def invoke():
        app = FastAPI()
        app.include_router(operations)
        app.include_router(reports)
        app.include_router(billing)
        db = FakeSQL({B1, B2})

        async def scope():
            yield db, "actor", False

        app.dependency_overrides[scoped_connection] = scope
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app)) as client:
            tools = ReportTools(
                ReportBackend("http://localhost", client=client),
                RuntimeContext("actor", (B1, B2), "session=fake", (TYPE,)),
            )
            result = await tools.invoke(operation, args)
            assert result["outcome"] == "success", result
            if operation == "get_repair_bill_summary":
                assert (
                    result["data"]["items"][0]["billed_amount"] == "9007199254740993.02"
                )

    asyncio.run(invoke())
