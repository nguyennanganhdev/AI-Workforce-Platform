"""Eight runtime-bindable tools against the current dev_TeamChien API."""

from __future__ import annotations

from pydantic import ValidationError

from ..application.client import ReportBackend
from ..metrics.normalize import INTERPRETATION_VERSION, normalize
from . import contracts as c
from .catalog import MODELS

ROUTES = {
    "get_report_filter_options": "/reports/filter-options",
    "get_employee_performance_summary": "/reports/employee-performance",
    "get_employee_feedback_details": "/reports/employee-feedback",
    "get_repair_revenue_summary": "/reports/repair-revenue",
    "get_incident_frequency_summary": "/reports/incident-frequency-summary",
    "get_report_supporting_records": "/reports/supporting-records",
    "create_report_export": "/reports/exports",
}
ALIASES = {
    "building_id": "buildingId",
    "staff_id": "staffId",
    "category_id": "categoryId",
    "from_date": "fromDate",
    "to_date": "toDate",
}


class ReportTools:
    """One instance per authenticated principal/run. Never bind the context to an LLM."""

    def __init__(self, backend: ReportBackend, context: c.RuntimeContext):
        self.backend, self.context = backend, context

    async def invoke(self, operation: str, arguments: dict):
        """Model-facing boundary returns sanitized errors, never HTTP bodies/credentials."""
        if type(operation) is not str or operation not in MODELS:
            return c.ReportToolError("REPORT_OPERATION_UNKNOWN").result()
        try:
            value = MODELS[operation].model_validate(arguments)
            return await self._call(operation, value)
        except ValidationError:
            return c.ReportToolError("REPORT_INPUT_INVALID").result()
        except c.ReportToolError as error:
            return error.result()

    async def _call(self, operation: str, value: c.Input):
        write = operation == "create_report_export"
        if (
            isinstance(value, c.BuildingInput)
            and value.building_id not in self.context.allowed_building_ids
        ):
            raise c.ReportToolError("REPORT_SCOPE_FORBIDDEN")
        raw = value.model_dump(exclude_none=True)
        raw.pop("timezone", None)  # Backend has no timezone parameter.
        path = ROUTES.get(operation, "/reports/exports/" + raw.get("export_id", ""))
        params = (
            None
            if write
            else {
                ALIASES.get(key, key): val
                for key, val in raw.items()
                if key != "export_id"
            }
        )
        payload = await self.backend.request(
            "POST" if write else "GET",
            path,
            self.context,
            params=params,
            body=raw if write else None,
        )
        try:
            self._validate_response(operation, value, payload)
            data, missing = normalize(operation, payload)
        except c.ReportToolError:
            raise c.ReportToolError(
                "BACKEND_CONTRACT_INVALID", execution_unknown=write
            ) from None
        limitations = [
            "Backend chưa cung cấp snapshot nhất quán, as_of hoặc metric_version; không khẳng định time travel.",
            "Source reference là lần gọi API/bản ghi đối chiếu, chưa phải source lineage của snapshot.",
        ]
        period = None
        if isinstance(value, c.PeriodInput):
            period = {
                "from": value.from_date,
                "to": value.to_date,
                "timezone": value.timezone,
                "boundary": "[from,to)",
                "timezone_applied_by_backend": False,
            }
            limitations.append(
                "API nhận ngày YYYY-MM-DD, chưa áp dụng timezone yêu cầu; thống kê phụ thuộc timezone của database."
            )
        if operation == "get_employee_performance_summary":
            limitations.append(
                "Cohort theo ngày tạo phân công; điểm theo ngày gửi đánh giá. Thời lượng là completed_at - started_at, chưa trừ pause."
            )
        if operation == "get_employee_feedback_details":
            limitations.append(
                "API phản hồi chưa hỗ trợ lọc kỳ; trang này có thể gồm dữ liệu ngoài kỳ báo cáo."
            )
        if operation == "get_repair_revenue_summary":
            limitations.append(
                "Cohort hóa đơn issued trong kỳ; thực thu là phân bổ xác nhận trước toDate, không phải dòng tiền chỉ phát sinh trong kỳ hoặc cohort ngày hoàn thành."
            )
            limitations.append(
                "Chưa tách tiền công/vật tư; không cộng các loại tiền tệ với nhau."
            )
        if operation == "get_report_supporting_records":
            limitations.append(
                "Ngày của bản ghi theo created_at hoặc issued_at; bộ lọc không chứng minh cohort/source của mọi KPI."
            )
        if write:
            limitations.append(
                "Export hiện đồng bộ; issued_revenue chỉ là giá trị hóa đơn, chưa xuất số thực thu/hiệu suất nhân viên."
            )
        empty = "items" in data and not data["items"]
        return {
            "outcome": "empty" if empty else "partial" if missing else "success",
            "operation": operation,
            "data": data,
            "period": period,
            "scope": {"building_id": getattr(value, "building_id", None)},
            "as_of": None,
            "snapshot_id": None,
            "metric_version": None,
            "interpretation_version": INTERPRETATION_VERSION,
            "missing_data": missing
            + ["snapshot_id", "as_of", "metric_version", "backend_timezone"],
            "source_references": [
                {
                    "type": "business_api",
                    "method": "POST" if write else "GET",
                    "path": path,
                    "filters": {k: v for k, v in raw.items() if k != "idempotency_key"},
                }
            ],
            "limitations": limitations,
        }

    def _validate_response(self, operation, value, payload):
        meta = payload.get("agentContext")
        if (
            type(meta) is not dict
            or meta.get("operation") != operation
            or meta.get("source") != "business_api"
            or type(meta.get("resourceContext")) is not dict
            or type(meta.get("facts")) is not dict
            or type(meta.get("missingFields")) is not list
            or any(type(field) is not str for field in meta["missingFields"])
        ):
            raise c.ReportToolError("BACKEND_CONTRACT_INVALID")
        for key, fact in meta["facts"].items():
            if key in payload and (
                type(fact) is not type(payload[key]) or fact != payload[key]
            ):
                raise c.ReportToolError("BACKEND_CONTRACT_INVALID")
        require_resource = operation not in (
            "get_report_filter_options",
            "create_report_export",
            "get_report_export_status",
        )
        for key, expected in value.model_dump(exclude_none=True).items():
            if key == "timezone":
                continue
            if require_resource and (
                type(meta["resourceContext"].get(key)) is not type(expected)
                or meta["resourceContext"].get(key) != expected
            ):
                raise c.ReportToolError("BACKEND_CONTRACT_INVALID")
        if operation == "get_report_filter_options":
            for key in ("buildings", "categories", "employees", "exportFormats"):
                if type(payload.get(key)) is not list:
                    raise c.ReportToolError("BACKEND_CONTRACT_INVALID")
            if payload["exportFormats"] != ["docx"]:
                raise c.ReportToolError("BACKEND_CONTRACT_INVALID")
            for key in ("buildings", "categories", "employees"):
                seen = set()
                for item in payload[key]:
                    try:
                        identifier = c.uuid_string(item["id"])
                    except (KeyError, TypeError, ValueError, AttributeError):
                        raise c.ReportToolError("BACKEND_CONTRACT_INVALID") from None
                    if identifier in seen or (
                        key == "buildings"
                        and identifier not in self.context.allowed_building_ids
                    ):
                        raise c.ReportToolError("BACKEND_CONTRACT_INVALID")
                    seen.add(identifier)
        if operation in (
            "get_employee_feedback_details",
            "get_report_supporting_records",
        ):
            rows, next_offset = payload.get("items"), payload.get("nextOffset")
            if (
                type(rows) is not list
                or len(rows) > value.limit
                or "nextOffset" not in payload
                or next_offset
                != (value.offset + len(rows) if len(rows) == value.limit else None)
            ):
                raise c.ReportToolError("BACKEND_CONTRACT_INVALID")
        if operation == "get_incident_frequency_summary" and (
            payload.get("buildingId") != value.building_id
            or payload.get("interval") != value.interval
        ):
            raise c.ReportToolError("BACKEND_CONTRACT_INVALID")
        if operation in ("create_report_export", "get_report_export_status"):
            try:
                report_id = c.uuid_string(payload["reportId"])
            except (KeyError, ValueError, TypeError, AttributeError):
                raise c.ReportToolError("BACKEND_CONTRACT_INVALID") from None
            if (
                payload.get("jobId") != report_id
                or payload.get("id") != report_id
                or payload.get("status")
                not in ("ready", "failed", "pending", "running")
                or payload.get("building_id") not in self.context.allowed_building_ids
                or (
                    isinstance(value, c.ExportStatusInput)
                    and report_id != value.export_id
                )
                or (
                    isinstance(value, c.ExportInput)
                    and (
                        payload.get("building_id") != value.building_id
                        or payload.get("kind") != value.kind
                    )
                )
            ):
                raise c.ReportToolError("BACKEND_CONTRACT_INVALID")
            if (
                payload.get("kind") not in ("incident_frequency", "issued_revenue")
                or payload.get("execution") != "synchronous"
                or payload["status"] not in ("ready", "failed")
                or "downloadUrl" not in payload
            ):
                raise c.ReportToolError("BACKEND_CONTRACT_INVALID")
            expected_url = (
                f"/reports/exports/{report_id}/content"
                if payload["status"] == "ready"
                else None
            )
            if payload.get("downloadUrl") != expected_url:
                raise c.ReportToolError("BACKEND_CONTRACT_INVALID")

    async def get_report_filter_options(self):
        return await self.invoke("get_report_filter_options", {})

    async def get_employee_performance_summary(self, arguments: dict):
        return await self.invoke("get_employee_performance_summary", arguments)

    async def get_employee_feedback_details(self, arguments: dict):
        return await self.invoke("get_employee_feedback_details", arguments)

    async def get_repair_revenue_summary(self, arguments: dict):
        return await self.invoke("get_repair_revenue_summary", arguments)

    async def get_incident_frequency_summary(self, arguments: dict):
        return await self.invoke("get_incident_frequency_summary", arguments)

    async def get_report_supporting_records(self, arguments: dict):
        return await self.invoke("get_report_supporting_records", arguments)

    async def create_report_export(self, arguments: dict):
        return await self.invoke("create_report_export", arguments)

    async def get_report_export_status(self, arguments: dict):
        return await self.invoke("get_report_export_status", arguments)
