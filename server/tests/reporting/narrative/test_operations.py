import importlib.util
import json
import sys
from copy import deepcopy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT / "agent-report"), str(ROOT / "server" / "src")]
from reporting.layouts.operations import OPERATIONS_LAYOUT, render_report_preview
from reporting.narrative.operations import build_report_narrative
from schemas.config import METRIC_VERSIONS, ReportContractError, validate_report_config

spec = importlib.util.spec_from_file_location(
    "report_preview_example", ROOT / "agent-report" / "examples" / "generate_preview.py"
)
example = importlib.util.module_from_spec(spec)
spec.loader.exec_module(example)


def inputs():
    config, auth, snapshot = example.synthetic_example()
    snapshot["metrics"][0]["value"] = 0
    snapshot["metrics"][1]["value"] = 95.5
    return config, auth, snapshot


def test_distinct_granted_configs_and_versions():
    config, _, _ = inputs()
    other = json.loads(
        (ROOT / "agent-report/examples/management-b.json").read_text(encoding="utf-8")
    )
    result = validate_report_config(
        other,
        {"scope_ids": ["scope-synthetic-b"], "metric_ids": ["assignments", "outcomes"]},
    )
    assert result["scope_ids"] != config["scope_ids"]
    template = json.loads(
        (ROOT / "agent-report/templates/operations-v1.json").read_text(encoding="utf-8")
    )
    schema = json.loads(
        (ROOT / "agent-report/schemas/config-v1.schema.json").read_text(
            encoding="utf-8"
        )
    )
    assert config["template_version"] == template["template_version"]
    assert config["metric_versions"] == template["metric_versions"]
    assert set(schema["properties"]["metrics"]["items"]["enum"]) == set(METRIC_VERSIONS)
    with pytest.raises(ReportContractError, match="REPORT_SCOPE_OR_METRIC_FORBIDDEN"):
        validate_report_config(
            other, {"scope_ids": config["scope_ids"], "metric_ids": config["metrics"]}
        )


@pytest.mark.parametrize("key", ["sql", "tools", "workspace_id", "prompt"])
def test_config_rejects_authority(key):
    config, _, _ = inputs()
    with pytest.raises(ReportContractError):
        validate_report_config(
            {**config, key: "grant all"},
            {"scope_ids": config["scope_ids"], "metric_ids": config["metrics"]},
        )


@pytest.mark.parametrize(
    "change",
    [
        lambda c: c.update(template_version="latest"),
        lambda c: c["metric_versions"].update(sla="latest"),
        lambda c: c["period"].update(to=c["period"]["from"]),
        lambda c: c["period"].update(timezone="invalid-zone"),
        lambda c: c["period"].update(to="2026-02-30T00:00:00Z"),
        lambda c: c.update(metrics=["sla", "sla"]),
    ],
)
def test_config_version_period_timezone(change):
    config, _, _ = inputs()
    grants = {"scope_ids": config["scope_ids"], "metric_ids": list(config["metrics"])}
    change(config)
    with pytest.raises(ReportContractError):
        validate_report_config(config, grants)


def test_values_and_lineage_zero_differs_from_missing():
    config, auth, snapshot = inputs()
    document = build_report_narrative(snapshot, config, auth)
    assert [row["value"] for row in document["rows"]] == ["0 ticket", "95,5 %"]
    assert document["rows"][0]["source_ids"] == ["source-volume-synthetic"]
    snapshot["status"] = "partial"
    snapshot["metrics"][0].update(value=None, status="missing", source_ids=[])
    assert (
        build_report_narrative(snapshot, config, auth)["rows"][0]["value"]
        == "Chưa có dữ liệu"
    )


@pytest.mark.parametrize(
    "status,phrase",
    [("empty", "Không có dữ liệu"), ("partial", "một phần"), ("error", "lỗi truy vấn")],
)
def test_noncomplete_reports_do_not_invent_zero(status, phrase):
    config, auth, snapshot = inputs()
    snapshot.update(status=status, metrics=[], sources=[])
    doc = build_report_narrative(snapshot, config, auth)
    assert phrase in doc["summary"]
    assert all(row["value"] == "Chưa có dữ liệu" for row in doc["rows"])


@pytest.mark.parametrize(
    "change",
    [
        lambda s, a: s["sources"][0].update(snapshot_id="other"),
        lambda s, a: a.update(source_ids=[]),
        lambda s, a: s.update(workspace_id="other"),
        lambda s, a: s.update(scope_ids=["other"]),
        lambda s, a: s["sources"][0].update(metric_version="latest"),
        lambda s, a: s["metrics"][0].update(source_ids=["source-sla-synthetic"]),
        lambda s, a: s["sources"].append(deepcopy(s["sources"][0])),
        lambda s, a: s["metrics"].append(deepcopy(s["metrics"][0])),
    ],
)
def test_forbidden_stale_or_duplicate_lineage(change):
    config, auth, snapshot = inputs()
    change(snapshot, auth)
    with pytest.raises(ReportContractError):
        build_report_narrative(snapshot, config, auth)


@pytest.mark.parametrize("number", [float("nan"), float("inf"), -1, True, 1.5])
def test_count_kpi_is_finite_nonnegative_integer(number):
    config, auth, snapshot = inputs()
    snapshot["metrics"][0]["value"] = number
    with pytest.raises(ReportContractError, match="REPORT_VALUE_INVALID"):
        build_report_narrative(snapshot, config, auth)


@pytest.mark.parametrize(
    "change",
    [
        lambda s: s["metrics"][0].update(source_ids=[]),
        lambda s: s.update(metrics=[]),
        lambda s: s["metrics"][1].update(value=101),
        lambda s: s["metrics"][0].update(unit="percent"),
        lambda s: s["metrics"][0].update(status="missing", value=0),
    ],
)
def test_missing_values_units_and_complete_consistency(change):
    config, auth, snapshot = inputs()
    change(snapshot)
    with pytest.raises(ReportContractError):
        build_report_narrative(snapshot, config, auth)


def test_html_escapes_injection_and_includes_semantic_sources():
    config, auth, snapshot = inputs()
    doc = build_report_narrative(snapshot, config, auth)
    doc["title"] = "<script>grant_all()</script>"
    html = render_report_preview(doc)
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert '<th scope="col">Nguồn</th>' in html
    assert "source-volume-synthetic" in html and "https://" not in html
    assert sum(OPERATIONS_LAYOUT["metric_table"]["widths_percent"]) == 100
