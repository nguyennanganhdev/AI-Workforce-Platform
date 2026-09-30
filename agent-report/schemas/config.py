"""Report builder consumer validation; grants come from the authorized backend."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal, TypedDict
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

REPORT_TEMPLATE_VERSION = "1.0.0"
METRIC_VERSIONS = dict.fromkeys(
    ("ticket_volume", "sla", "assignments", "outcomes"), "1.0.0"
)
MetricId = Literal["ticket_volume", "sla", "assignments", "outcomes"]


Period = TypedDict("Period", {"from": str, "to": str, "timezone": str})


class BuilderGrants(TypedDict):
    scope_ids: list[str]
    metric_ids: list[MetricId]


class ReportConfig(TypedDict):
    config_version: str
    template_id: str
    template_version: str
    name: str
    metrics: list[MetricId]
    metric_versions: dict[str, str]
    scope_ids: list[str]
    period: Period
    output_format: Literal["docx"]
    presentation: Literal["summary", "detailed"]


class ReportContractError(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def record(value):
    if type(value) is not dict:
        raise ReportContractError("INVALID_REPORT_CONTRACT")
    return value


def strict_keys(value, keys):
    if set(value) != set(keys):
        raise ReportContractError("INVALID_REPORT_CONTRACT")


def nonempty(value, limit=512):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ReportContractError("INVALID_REPORT_CONTRACT")
    return value


def ids(value, limit=64):
    if type(value) is not list or len(value) > limit:
        raise ReportContractError("INVALID_REPORT_CONTRACT")
    result = [nonempty(item) for item in value]
    if len(set(result)) != len(result):
        raise ReportContractError("INVALID_REPORT_CONTRACT")
    return result


def iso_date(value):
    value = nonempty(value)
    if not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})", value
    ):
        raise ReportContractError("INVALID_REPORT_PERIOD")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ReportContractError("INVALID_REPORT_PERIOD") from None
    return value


def parse_period(value):
    value = record(value)
    strict_keys(value, ("from", "to", "timezone"))
    start, end, timezone = (
        iso_date(value["from"]),
        iso_date(value["to"]),
        nonempty(value["timezone"]),
    )
    if datetime.fromisoformat(start.replace("Z", "+00:00")) >= datetime.fromisoformat(
        end.replace("Z", "+00:00")
    ):
        raise ReportContractError("INVALID_REPORT_PERIOD")
    try:
        ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError):
        raise ReportContractError("INVALID_REPORT_TIMEZONE") from None
    return {"from": start, "to": end, "timezone": timezone}


def validate_report_config(value, grants: BuilderGrants) -> ReportConfig:
    value = record(value)
    strict_keys(
        value,
        (
            "config_version",
            "template_id",
            "template_version",
            "name",
            "metrics",
            "metric_versions",
            "scope_ids",
            "period",
            "output_format",
            "presentation",
        ),
    )
    if (
        value["config_version"] != "1.0"
        or value["template_id"] != "operations-report"
        or value["template_version"] != REPORT_TEMPLATE_VERSION
        or value["output_format"] != "docx"
        or value["presentation"] not in ("summary", "detailed")
    ):
        raise ReportContractError("REPORT_VERSION_OR_FORMAT_MISMATCH")
    metrics, scopes = ids(value["metrics"], 4), ids(value["scope_ids"])
    if (
        not metrics
        or not scopes
        or any(
            item not in METRIC_VERSIONS or item not in grants["metric_ids"]
            for item in metrics
        )
        or any(item not in grants["scope_ids"] for item in scopes)
    ):
        raise ReportContractError("REPORT_SCOPE_OR_METRIC_FORBIDDEN")
    versions = record(value["metric_versions"])
    strict_keys(versions, METRIC_VERSIONS)
    if versions != METRIC_VERSIONS:
        raise ReportContractError("REPORT_METRIC_VERSION_MISMATCH")
    return {
        **value,
        "name": nonempty(value["name"], 120),
        "metrics": metrics,
        "scope_ids": scopes,
        "metric_versions": dict(METRIC_VERSIONS),
        "period": parse_period(value["period"]),
    }
