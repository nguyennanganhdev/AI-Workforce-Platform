"""PD08 consumer narrative. Backend supplies authorized metrics and lineage."""

from __future__ import annotations

import math

from schemas.config import (
    METRIC_VERSIONS,
    ReportContractError,
    ids,
    iso_date,
    nonempty,
    parse_period,
    record,
)

LABELS = {
    "ticket_volume": "Lượng ticket",
    "sla": "SLA",
    "assignments": "Phân công",
    "outcomes": "Kết quả xử lý",
}
UNITS = {
    "tickets": "ticket",
    "percent": "%",
    "assignments": "phân công",
    "work_orders": "work order",
}
METRIC_UNITS = dict(zip(LABELS, UNITS))


def format_number(value):
    whole, dot, fraction = f"{value:,.6f}".rstrip("0").rstrip(".").partition(".")
    return whole.replace(",", ".") + ("," + fraction if dot else "")


def build_report_narrative(raw, config, authorization):
    value = record(raw)
    request_id, workspace_id, snapshot_id = (
        nonempty(value.get(key))
        for key in ("report_request_id", "workspace_id", "snapshot_id")
    )
    nonempty(value.get("source_message_id"))
    scopes, period, as_of = (
        ids(value.get("scope_ids")),
        parse_period(value.get("period")),
        iso_date(value.get("as_of")),
    )
    if (
        request_id != authorization["report_request_id"]
        or workspace_id != authorization["workspace_id"]
        or not scopes
        or any(
            scope not in authorization["scope_ids"] or scope not in config["scope_ids"]
            for scope in scopes
        )
        or any(scope not in scopes for scope in config["scope_ids"])
    ):
        raise ReportContractError("REPORT_SCOPE_FORBIDDEN")
    if (
        value.get("template_version") != config["template_version"]
        or period != config["period"]
    ):
        raise ReportContractError("REPORT_SNAPSHOT_VERSION_OR_PERIOD_MISMATCH")
    status = value.get("status")
    if (
        status not in ("complete", "partial", "empty", "error")
        or type(value.get("metrics")) is not list
        or type(value.get("sources")) is not list
        or len(value["metrics"]) > 4
        or len(value["sources"]) > 256
    ):
        raise ReportContractError("INVALID_REPORT_CONTRACT")
    sources = []
    for item in value["sources"]:
        item = record(item)
        metric_id = nonempty(item.get("metric_id"))
        if (
            metric_id not in config["metrics"]
            or item.get("snapshot_id") != snapshot_id
            or item.get("metric_version") != METRIC_VERSIONS.get(metric_id)
            or nonempty(item.get("source_id")) not in authorization["source_ids"]
        ):
            raise ReportContractError("REPORT_SOURCE_FORBIDDEN_OR_STALE")
        sources.append(
            {
                "source_id": item["source_id"],
                "snapshot_id": snapshot_id,
                "metric_id": metric_id,
                "metric_version": nonempty(item.get("metric_version")),
                "reference_id": nonempty(item.get("reference_id")),
            }
        )
    if len({s["source_id"] for s in sources}) != len(sources):
        raise ReportContractError("REPORT_DUPLICATE_SOURCE")
    rows, seen, limitations = [], set(), []
    for item in value["metrics"]:
        metric = record(item)
        metric_id = nonempty(metric.get("id"))
        if (
            metric_id not in config["metrics"]
            or metric.get("version") != METRIC_VERSIONS.get(metric_id)
            or metric_id in seen
        ):
            raise ReportContractError("REPORT_METRIC_FORBIDDEN_OR_STALE")
        seen.add(metric_id)
        source_ids = ids(metric.get("source_ids"))
        if any(
            not any(
                source["source_id"] == source_id and source["metric_id"] == metric_id
                for source in sources
            )
            for source_id in source_ids
        ):
            raise ReportContractError("REPORT_LINEAGE_MISSING")
        if (
            metric.get("status") not in ("available", "missing", "error")
            or metric.get("unit") not in UNITS
        ):
            raise ReportContractError("INVALID_REPORT_CONTRACT")
        if metric["unit"] != METRIC_UNITS[metric_id]:
            raise ReportContractError("REPORT_METRIC_UNIT_MISMATCH")
        if metric["status"] == "available":
            number = metric.get("value")
            if (
                status in ("empty", "error")
                or type(number) not in (int, float)
                or not math.isfinite(number)
                or number < 0
                or not source_ids
                or (metric["unit"] == "percent" and number > 100)
                or (metric["unit"] != "percent" and number != int(number))
            ):
                raise ReportContractError("REPORT_VALUE_INVALID")
            rendered = format_number(number) + " " + UNITS[metric["unit"]]
        else:
            if "value" not in metric or metric["value"] is not None:
                raise ReportContractError("REPORT_MISSING_MUST_BE_NULL")
            rendered = (
                "Lỗi truy vấn" if metric["status"] == "error" else "Chưa có dữ liệu"
            )
            limitations.append(LABELS[metric_id] + ": " + rendered.lower() + ".")
        rows.append(
            {"metric": LABELS[metric_id], "value": rendered, "source_ids": source_ids}
        )
    for metric_id in config["metrics"]:
        if metric_id not in seen:
            rows.append(
                {
                    "metric": LABELS[metric_id],
                    "value": "Chưa có dữ liệu",
                    "source_ids": [],
                }
            )
            limitations.append(LABELS[metric_id] + ": chưa có dữ liệu.")
    if status == "complete" and limitations:
        raise ReportContractError("REPORT_COMPLETE_HAS_MISSING_METRICS")
    if status == "empty" and sources:
        raise ReportContractError("REPORT_EMPTY_HAS_SOURCES")
    summaries = {
        "empty": "Không có dữ liệu trong phạm vi và kỳ báo cáo này.",
        "error": "Không thể lập báo cáo do lỗi truy vấn dữ liệu. Đây không phải kết quả không có ticket.",
        "partial": "Báo cáo có dữ liệu một phần; một số chỉ số chưa có kết quả đầy đủ.",
        "complete": "Báo cáo sử dụng các chỉ số do công cụ tính toán và snapshot đã xác minh.",
    }
    return {
        "title": config["name"],
        "status": status,
        "as_of": as_of,
        "period": period,
        "rows": rows,
        "sources": sources,
        "summary": summaries[status],
        "limitations": limitations
        + [
            "Kỳ báo cáo [from,to); as_of là watermark snapshot, không phải cam kết truy vấn lịch sử tại mọi thời điểm."
        ],
    }
