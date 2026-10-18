"""Proposal artifacts stay pending, contain no fabricated people and cannot pass operational import validation."""

import codecs
import csv
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

DEPLOY = Path(__file__).resolve().parents[3] / "deploy"
CATALOG = DEPLOY / "reference-data/owner-public-catalog-20261014.json"


def module(name):
    spec = importlib.util.spec_from_file_location(name, DEPLOY / (name + ".py"))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def test_all_three_sites_have_sourced_data_and_explicit_owner_requests(tmp_path):
    result = module("prepare-owner-proposals").write_pack(CATALOG, tmp_path)
    assert result["total_proposals"] == 113
    assert result["counts"] == {
        "geography": 55,
        "services": 34,
        "staffing_requirements": 9,
        "data_requests": 15,
    }
    rows = [
        json.loads(line)
        for line in (tmp_path / "proposals.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert len({row["proposal_id"] for row in rows}) == 113
    for site in result["site_codes"]:
        scoped = [row for row in rows if row["site_code"] == site]
        assert {row["dataset"] for row in scoped} == set(result["counts"])
        requests = [
            row["data"]["requested_dataset"]
            for row in scoped
            if row["dataset"] == "data_requests"
        ]
        assert set(requests) == {
            "operators",
            "units",
            "residents",
            "staff_roster",
            "staff_shifts",
        }
    assert all(
        row["review_status"] == "pending_owner_review"
        and not row["operational_import_allowed"]
        for row in rows
    )
    assert all(
        row["approved_by"] is None and row["approved_at"] is None for row in rows
    )
    assert all(
        row["data"].get("fee_amount") is None
        and row["data"].get("operating_hours") is None
        for row in rows
    )
    assert all(row["sources"] for row in rows if row["basis"].startswith("public_"))
    for name, digest in result["files"].items():
        assert hashlib.sha256((tmp_path / name).read_bytes()).hexdigest() == digest


def test_review_register_opens_as_utf8_csv_and_does_not_grant_approval(tmp_path):
    module("prepare-owner-proposals").write_pack(CATALOG, tmp_path)
    path = tmp_path / "review-register.csv"
    assert path.read_bytes().startswith(codecs.BOM_UTF8)
    with path.open(encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))
    assert len(rows) == 113
    assert all(row["decision"] == "pending" and row["reviewer"] == "" for row in rows)
    assert any("Vệ sinh" in row["title"] for row in rows)
    report = module("validate-owner-data").validate(tmp_path)
    assert report["valid"] is False and report["database_written"] is False


def test_regeneration_is_deterministic_without_overwriting_reviewer_edits(tmp_path):
    generator = module("prepare-owner-proposals")
    first, second = tmp_path / "first", tmp_path / "second"
    assert generator.write_pack(CATALOG, first) == generator.write_pack(CATALOG, second)
    review = first / "review-register.csv"
    review.write_text("Reviewer edits to preserve", encoding="utf-8")
    with pytest.raises(FileExistsError, match="reviewer edits"):
        generator.write_pack(CATALOG, first)
    assert review.read_text(encoding="utf-8") == "Reviewer edits to preserve"


def test_duplicate_or_approved_public_records_are_refused():
    generator = module("prepare-owner-proposals")
    records = json.loads(CATALOG.read_text(encoding="utf-8"))
    with pytest.raises(ValueError):
        generator.build(records + records[:1])
    records[0]["authority"] = "approved"
    with pytest.raises(ValueError):
        generator.build(records)
