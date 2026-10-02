"""Explicit synthetic preview CLI; never imported by production composition."""

import json
import sys
from copy import deepcopy
from pathlib import Path

if __name__ == "__main__":
    # Local example entrypoint only; production composition supplies import paths.
    sys.path[:0] = [
        str(Path(__file__).resolve().parents[1]),
        str(Path(__file__).resolve().parents[2] / "server" / "src"),
    ]

from reporting.layouts.operations import render_report_preview
from reporting.narrative.operations import build_report_narrative
from schemas.config import validate_report_config


def synthetic_example():
    config = validate_report_config(
        json.loads(
            Path(__file__).with_name("management-a.json").read_text(encoding="utf-8")
        ),
        {"scope_ids": ["scope-synthetic-a"], "metric_ids": ["ticket_volume", "sla"]},
    )
    auth = {
        "report_request_id": "report-synthetic",
        "workspace_id": "workspace-synthetic-a",
        "scope_ids": config["scope_ids"],
        "source_ids": ["source-volume-synthetic", "source-sla-synthetic"],
    }
    snapshot = {
        "report_request_id": auth["report_request_id"],
        "source_message_id": "message-synthetic",
        "workspace_id": auth["workspace_id"],
        "scope_ids": config["scope_ids"],
        "snapshot_id": "snapshot-synthetic",
        "as_of": "2026-09-30T00:00:00Z",
        "template_version": "1.0.0",
        "period": config["period"],
        "status": "complete",
        "metrics": [],
        "sources": [],
    }
    for metric_id, label, value, unit in (
        ("ticket_volume", "volume", 12, "tickets"),
        ("sla", "sla", 90, "percent"),
    ):
        source_id = f"source-{label}-synthetic"
        snapshot["metrics"].append(
            {
                "id": metric_id,
                "version": "1.0.0",
                "value": value,
                "unit": unit,
                "status": "available",
                "source_ids": [source_id],
            }
        )
        snapshot["sources"].append(
            {
                "source_id": source_id,
                "snapshot_id": snapshot["snapshot_id"],
                "metric_id": metric_id,
                "metric_version": "1.0.0",
                "reference_id": "dataset-ref-synthetic-" + label,
            }
        )
    return config, auth, snapshot


def generate_previews():
    config, auth, base = synthetic_example()
    for status in ("complete", "partial", "empty", "error"):
        snapshot = deepcopy(base)
        snapshot["status"] = status
        if status == "partial":
            snapshot["metrics"][1].update(value=None, status="missing", source_ids=[])
            snapshot["sources"] = snapshot["sources"][:1]
        elif status in ("empty", "error"):
            snapshot.update(metrics=[], sources=[])
        document = build_report_narrative(snapshot, config, auth)
        Path(__file__).with_name("preview-" + status + ".html").write_text(
            render_report_preview(document), encoding="utf-8"
        )


if __name__ == "__main__":
    generate_previews()
    print("Generated four synthetic Report previews; no backend integration claimed.")
