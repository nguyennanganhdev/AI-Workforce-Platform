"""Validate owner CSV bundles offline; never writes to a database or prints personal records."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "services/vinhomes-api/src")
)
from vinhomes_api.owner_bundle import FIELDS, REVIEW, SITES, SOP_FIELDS, validate  # noqa: F401

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folder", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = validate(args.folder)
    except (OSError, ValueError, TypeError) as exc:
        report = {
            "valid": False,
            "errors": ["Invalid or unreadable bundle: " + type(exc).__name__],
            "database_written": False,
        }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["valid"] else 1)
