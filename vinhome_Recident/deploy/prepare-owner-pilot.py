"""Prepare an empty OP1/technical pilot bundle outside Git; never creates people or approvals."""

import argparse
import csv
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "services/vinhomes-api/src")
)
from vinhomes_api.owner_bundle import FIELDS, REVIEW, SOP_FIELDS


def prepare(output, zone_code="", building_code=""):
    if output.exists() and any(output.iterdir()):
        raise ValueError(
            "Output folder must be empty; existing owner edits are preserved"
        )
    output.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": 2,
        "bundle_code": "op1-technical-pilot",
        "version": "draft-1",
        "data_mode": "owner_candidate",
        "site_codes": ["ocean-park-1"],
        "data_owner": "",
        "exported_at": "",
        "document_reference": "",
        "pilot": {
            "site_code": "ocean-park-1",
            "zone_code": zone_code,
            "building_code": building_code,
            "category_codes": ["technical"],
        },
        "source_documents": [],
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    for name, fields in {**FIELDS, "sops": SOP_FIELDS}.items():
        with (output / (name + ".csv")).open(
            "w", encoding="utf-8-sig", newline=""
        ) as stream:
            csv.writer(stream).writerow(fields.split() + REVIEW)
    (output / "evidence").mkdir(exist_ok=True)
    template = Path(__file__).resolve().parent / "owner-data-pilot/op1-technical"
    for name in ("README.md", "system-workflow.json"):
        shutil.copyfile(template / name, output / name)
    return {
        "schema_version": 2,
        "csv_files": 10,
        "personal_records": 0,
        "owner_approved": False,
        "database_written": False,
        "operational_activation": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--zone-code", default="")
    parser.add_argument("--building-code", default="")
    args = parser.parse_args()
    try:
        result = prepare(args.output, args.zone_code, args.building_code)
    except (ValueError, OSError) as exc:
        parser.exit(1, type(exc).__name__ + ": output refused\n")
    print(json.dumps(result, indent=2))
