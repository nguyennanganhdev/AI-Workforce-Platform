"""Four requested tools, composing existing read APIs without SQL or new endpoints."""

import asyncio
import unicodedata
from datetime import date, datetime, timezone
from decimal import Decimal, localcontext

from pydantic import ValidationError

from ..metrics.normalize import (
    bill_data,
    count,
    identity,
    invalid,
    money,
    rating_data,
    rows,
    text,
    ticket_data,
)
from .catalog import MODELS, OUTPUTS
from .contracts import FilterInput, ReportToolError, ResponsePeriod, Scope

LIMITATIONS = [
    "Các API/trang là các lần đọc riêng; chưa có snapshot nhất quán hoặc lineage đầy đủ cho từng KPI.",
    "Phân khu dùng membership các tòa active hiện tại; không khẳng định membership lịch sử.",
]


def comparable_name(value):
    return " ".join(unicodedata.normalize("NFC", value).casefold().split())


def metadata(payload, operation, expected):
    meta = payload.get("agentContext")
    if (
        type(meta) is not dict
        or meta.get("operation") != operation
        or meta.get("source") != "business_api"
        or type(meta.get("resourceContext")) is not dict
        or type(meta.get("facts")) is not dict
        or type(meta.get("missingFields")) is not list
        or any(type(v) is not str for v in meta["missingFields"])
    ):
        invalid()
    for key, expected_value in expected.items():
        actual = meta["resourceContext"].get(key)
        if type(actual) is not type(expected_value) or actual != expected_value:
            invalid()
    for key, fact in meta["facts"].items():
        if key in payload and (
            type(fact) is not type(payload[key]) or fact != payload[key]
        ):
            invalid()


def timestamp(value):
    if type(value) is not str:
        invalid()
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        invalid()
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        invalid()
    return parsed


class ReportTools:
    def __init__(self, backend, context):
        self.backend, self.context = backend, context

    async def invoke(self, operation, arguments):
        if type(operation) is not str or operation not in MODELS:
            return ReportToolError("REPORT_OPERATION_UNKNOWN").result()
        try:
            value = MODELS[operation].model_validate(arguments)
        except ValidationError:
            return ReportToolError("REPORT_INPUT_INVALID").result()
        try:
            async with asyncio.timeout(self.backend.operation_timeout_seconds):
                return await self._call(operation, value)
        except TimeoutError:
            return ReportToolError("BACKEND_UNAVAILABLE", retryable=True).result()
        except ValidationError:
            return ReportToolError("BACKEND_CONTRACT_INVALID").result()
        except ReportToolError as error:
            return error.result()

    async def _scope_options(self, sources):
        catalog = await self._get("/catalogs", sources)
        allowed = await self._get("/reports/filter-options", sources)
        metadata(allowed, "get_report_filter_options", {})
        grants = set(self.context.allowed_building_ids)
        available = set()
        for row in rows(allowed.get("buildings")):
            identifier = identity(row.get("id"))
            if identifier in available:
                invalid()
            available.add(identifier)
        grants &= available
        zones, buildings, seen = {}, {}, set()
        for row in rows(catalog.get("zones")):
            identifier = identity(row.get("id"))
            if identifier in zones:
                invalid()
            zones[identifier] = text(row.get("name"))
        for row in rows(catalog.get("buildings")):
            identifier = identity(row.get("id"))
            if identifier in seen:
                invalid()
            seen.add(identifier)
            zone = identity(row["zone_id"]) if row.get("zone_id") is not None else None
            if zone is not None and zone not in zones:
                invalid()
            buildings[identifier] = (text(row.get("name")), zone)
        if not available <= set(buildings):
            invalid()
        options = [
            Scope(scope_type="building", scope_id=i, scope_name=name, building_ids=[i])
            for i, (name, _) in buildings.items()
            if i in grants
        ]
        partial_zones = set()
        for identifier, name in zones.items():
            members = sorted(
                i for i, (_, zone) in buildings.items() if zone == identifier
            )
            if members and set(members) <= grants:
                options.append(
                    Scope(
                        scope_type="zone",
                        scope_id=identifier,
                        scope_name=name,
                        building_ids=members,
                    )
                )
            elif set(members) & grants:
                partial_zones.add(identifier)
        employees, employee_seen = [], set()
        for row in rows(allowed.get("employees")):
            identifier = identity(row.get("id"))
            if identifier in employee_seen:
                invalid()
            employee_seen.add(identifier)
            employees.append(
                {"staff_id": identifier, "staff_name": text(row.get("name"))}
            )
        options.sort(
            key=lambda s: (s.scope_type, comparable_name(s.scope_name), s.scope_id)
        )
        return options, partial_zones, employees

    def _select(self, options, value, partial_zones):
        kind, identifier, name = (
            value.scope_type,
            value.scope_id,
            getattr(value, "name", None),
        )
        candidates = [s for s in options if kind is None or s.scope_type == kind]
        if identifier is not None:
            if kind == "zone" and identifier in partial_zones:
                raise ReportToolError("REPORT_SCOPE_INCOMPLETE")
            candidates = [s for s in candidates if s.scope_id == identifier]
            if not candidates:
                raise ReportToolError("REPORT_SCOPE_FORBIDDEN_OR_NOT_FOUND")
        elif name is not None:
            candidates = [
                s
                for s in candidates
                if comparable_name(s.scope_name) == comparable_name(name)
            ]
            if not candidates:
                raise ReportToolError("REPORT_SCOPE_NOT_FOUND")
            if len(candidates) > 1:
                raise ReportToolError(
                    "REPORT_SCOPE_AMBIGUOUS",
                    candidates=[s.model_dump() for s in candidates],
                )
        return candidates

    async def _get(self, path, sources, params=None):
        result = await self.backend.request(path, self.context, params=params)
        reference = {"method": "GET", "path": path}
        if reference not in sources:
            sources.append(reference)
        return result

    async def _records(self, path, operation, resource, aliases, sources, seen):
        result, offset, limit = [], 0, 100
        for _ in range(self.backend.max_pages):
            expected = {**resource, "limit": limit, "offset": offset}
            params = {aliases.get(k, k): v for k, v in expected.items()}
            payload = await self._get(path, sources, params)
            metadata(payload, operation, expected)
            page = rows(payload.get("items"))
            if len(page) > limit or "nextOffset" not in payload:
                invalid()
            next_offset = payload["nextOffset"]
            expected_next = offset + len(page) if len(page) == limit else None
            if (
                type(next_offset) not in (int, type(None))
                or next_offset != expected_next
            ):
                invalid()
            for row in page:
                identifier = identity(row.get("id"))
                if identifier in seen:
                    raise ReportToolError("REPORT_SOURCE_DUPLICATED")
                seen.add(identifier)
                if len(seen) > self.backend.max_records:
                    raise ReportToolError("REPORT_DATA_LIMIT_REACHED")
                result.append(row)
            if next_offset is None:
                return result
            offset = next_offset
        raise ReportToolError("REPORT_DATA_LIMIT_REACHED")

    async def _supporting(self, building, value, kind, sources, seen):
        resource = {
            "building_id": building,
            "from_date": value.from_date,
            "to_date": value.to_date,
            "kind": kind,
        }
        aliases = {
            "building_id": "buildingId",
            "from_date": "fromDate",
            "to_date": "toDate",
        }
        return await self._records(
            "/reports/supporting-records",
            "get_report_supporting_records",
            resource,
            aliases,
            sources,
            seen,
        )

    async def _bills(self, scope, value, sources):
        repair = set(self.context.repair_category_ids)
        seen, totals = set(), {}
        with localcontext() as decimal_context:
            decimal_context.prec = 100
            for building in scope.building_ids:
                for row in await self._supporting(
                    building, value, "invoices", sources, seen
                ):
                    identifier = identity(row["id"])
                    price = money(row.get("grand_total"))
                    currency = row.get("currency")
                    if row.get("status") != "issued":
                        invalid()
                    issued_at = timestamp(row.get("issued_at"))
                    invoice_result = await self._get("/invoices/" + identifier, sources)
                    invoice = invoice_result.get("invoice")
                    if (
                        type(invoice) is not dict
                        or identity(invoice.get("id")) != identifier
                        or invoice.get("status") != "issued"
                        or invoice.get("currency") != currency
                        or invoice.get("ticket_id") != row.get("ticket_id")
                        or invoice.get("work_order_id") != row.get("work_order_id")
                        or timestamp(invoice.get("issued_at")) != issued_at
                    ):
                        invalid()
                    lines = rows(invoice_result.get("lines"))
                    if not lines:
                        invalid()
                    # Detail's untyped FastAPI route can serialize NUMERIC as float.
                    # Price comes exclusively from the typed list route; detail is
                    # used for identity/status/category binding, never arithmetic.
                    categories, line_ids = set(), set()
                    for line in lines:
                        line_id = identity(line.get("id"))
                        if (
                            line_id in line_ids
                            or identity(line.get("invoice_id")) != identifier
                        ):
                            invalid()
                        line_ids.add(line_id)
                        categories.add(identity(line.get("category_id")))
                    if not categories & repair:
                        continue
                    if not categories <= repair:
                        raise ReportToolError("REPORT_MIXED_INVOICE")
                    if (
                        type(currency) is not str
                        or len(currency) != 3
                        or not currency.isascii()
                        or not currency.isupper()
                        or not currency.isalpha()
                    ):
                        invalid()
                    n, amount = totals.get(currency, (0, Decimal(0)))
                    totals[currency] = (n + 1, amount + Decimal(price))
            items = [
                {
                    "currency": currency,
                    "invoice_count": n,
                    "billed_amount": format(amount, "f"),
                }
                for currency, (n, amount) in sorted(totals.items())
            ]
        return bill_data({"basis": "issued_repair_invoice_grand_total", "items": items})

    async def _tickets(self, scope, value, sources):
        seen, groups, incident = set(), {}, 0
        for building in scope.building_ids:
            await self._supporting(building, value, "tickets", sources, seen)
            expected = {
                "building_id": building,
                "from_date": value.from_date,
                "to_date": value.to_date,
                "interval": "month",
            }
            params = {
                "buildingId": building,
                "fromDate": value.from_date,
                "toDate": value.to_date,
                "interval": "month",
            }
            payload = await self._get(
                "/reports/incident-frequency-summary", sources, params
            )
            metadata(payload, "get_incident_frequency_summary", expected)
            if (
                payload.get("buildingId") != building
                or payload.get("interval") != "month"
            ):
                invalid()
            group_seen, subtotal = set(), 0
            for row in rows(payload.get("items")):
                kind = (
                    identity(row["incident_type_id"])
                    if row.get("incident_type_id") is not None
                    else None
                )
                category = (
                    identity(row["category_id"])
                    if row.get("category_id") is not None
                    else None
                )
                bucket = row.get("period")
                try:
                    if (
                        type(bucket) is not str
                        or date.fromisoformat(bucket).isoformat() != bucket
                    ):
                        invalid()
                except ValueError:
                    invalid()
                if "category_id" not in row or "incident_type_id" not in row:
                    invalid()
                key = (bucket, category, kind)
                if key in group_seen:
                    invalid()
                group_seen.add(key)
                amount = count(row.get("incident_count"))
                name = text(row.get("incident_type"))
                if not amount or (kind in groups and groups[kind][0] != name):
                    invalid()
                previous = groups.get(kind, (name, 0))[1]
                groups[kind] = (name, previous + amount)
                subtotal += amount
            if subtotal != count(payload.get("totalTickets")):
                invalid()
            incident += subtotal
        if incident > len(seen):
            raise ReportToolError("REPORT_SOURCE_INCONSISTENT")
        data = {
            "total_ticket_count": len(seen),
            "incident_ticket_count": incident,
            "non_incident_ticket_count": len(seen) - incident,
            "items": [
                {
                    "incident_type_id": kind,
                    "incident_type_name": name,
                    "ticket_count": amount,
                }
                for kind, (name, amount) in sorted(
                    groups.items(), key=lambda pair: pair[0] or ""
                )
            ],
        }
        return ticket_data(data)

    async def _stars(self, scope, value, sources, employees):
        names = {row["staff_id"]: row["staff_name"] for row in employees}
        seen, items = set(), []
        for staff in value.staff_ids:
            histogram = {str(s): 0 for s in range(1, 6)}
            for building in scope.building_ids:
                resource = {"building_id": building, "staff_id": staff}
                aliases = {"building_id": "buildingId", "staff_id": "staffId"}
                records = await self._records(
                    "/reports/employee-feedback",
                    "get_employee_feedback_details",
                    resource,
                    aliases,
                    sources,
                    seen,
                )
                for row in records:
                    score = count(row.get("score"))
                    if not 1 <= score <= 5:
                        invalid()
                    submitted = (
                        timestamp(row.get("submitted_at"))
                        .astimezone(timezone.utc)
                        .date()
                        .isoformat()
                    )
                    if value.from_date <= submitted < value.to_date:
                        histogram[str(score)] += 1
            items.append(
                {
                    "staff_id": staff,
                    "staff_name": names.get(staff),
                    "rating_count": sum(histogram.values()),
                    "star_counts": histogram,
                }
            )
        return rating_data({"basis": "customer_review_submission", "items": items})

    async def _call(self, operation, value):
        if (
            operation == "get_repair_bill_summary"
            and not self.context.repair_category_ids
        ):
            raise ReportToolError("REPORT_REPAIR_CATEGORIES_REQUIRED")
        sources = []
        options, partial_zones, employees = await self._scope_options(sources)
        selected = self._select(options, value, partial_zones)
        if isinstance(value, FilterInput):
            return OUTPUTS[operation](
                outcome="success" if selected else "empty",
                operation=operation,
                data=selected,
                employee_options=employees,
                sources=sources,
                limitations=LIMITATIONS
                + [
                    "Employee options là danh sách backend cho phép; không chứng minh từng người thuộc mọi tòa."
                ],
            ).model_dump(mode="json")
        scope = selected[0]
        limitations = list(LIMITATIONS)
        period = ResponsePeriod(
            from_date=value.from_date, to_date=value.to_date, boundary="[from,to)"
        )
        if operation == "get_repair_bill_summary":
            data, empty = await self._bills(scope, value, sources)
            limitations += [
                "Tổng grand_total hóa đơn issued trong kỳ; không phải tiền đã thực thu.",
                "Nhóm sửa chữa do runtime cấu hình; hóa đơn lẫn nhóm khác bị chặn, không cộng cả bill.",
                "API lọc ngày theo timezone DB/session chưa được backend công bố.",
            ]
            limitations.append(
                "Giá lấy từ supporting-records; tiền trong invoice detail không dùng để cộng vì serializer có thể mất độ chính xác. Chưa có snapshot để đối chiếu giá giữa hai lần đọc."
            )
        elif operation == "get_ticket_frequency_summary":
            data, empty = await self._tickets(scope, value, sources)
            limitations += [
                "Ticket theo created_at; non_incident không khẳng định tất cả là service_request.",
                "API lọc ngày theo timezone DB/session chưa được backend công bố.",
            ]
        else:
            data, empty = await self._stars(scope, value, sources, employees)
            period.timezone = "UTC"
            limitations += [
                "Chỉ báo cáo các staff_ids đã chọn; không khẳng định gồm toàn bộ nhân viên.",
                "Đọc đủ feedback history rồi lọc submitted_at theo ngày UTC; API chưa lọc kỳ.",
                "Điểm trung bình làm tròn 2 chữ số HALF_UP; không xếp hạng hoặc suy ra hiệu suất công việc.",
            ]
        return OUTPUTS[operation](
            outcome="empty" if empty else "success",
            operation=operation,
            scope=scope,
            period=period,
            data=data,
            sources=sources,
            limitations=limitations,
        ).model_dump(mode="json")

    async def filter_report_scope(self, arguments=None):
        return await self.invoke(
            "filter_report_scope", {} if arguments is None else arguments
        )

    async def get_repair_bill_summary(self, arguments):
        return await self.invoke("get_repair_bill_summary", arguments)

    async def get_ticket_frequency_summary(self, arguments):
        return await self.invoke("get_ticket_frequency_summary", arguments)

    async def get_employee_star_summary(self, arguments):
        return await self.invoke("get_employee_star_summary", arguments)
