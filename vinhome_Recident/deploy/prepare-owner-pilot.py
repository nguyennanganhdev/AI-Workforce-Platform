"""Prepare empty or sourced-reference OP1 pilot files; never creates people or owner approvals."""

import argparse
import csv
import hashlib
import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

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


def prepare_candidate(output, catalog, building_code="S1.01"):
    """Prefill public geography and software workflow only; missing owner facts stay missing."""
    public = json.loads(catalog.read_text(encoding="utf-8"))
    buildings = [
        r
        for r in public
        if r["site_code"] == "ocean-park-1"
        and r.get("kind") == "building"
        and r.get("official_code") == building_code
    ]
    if len(buildings) != 1:
        raise ValueError("Exactly one publicly sourced OP1 building is required")
    building = buildings[0]
    zones = [
        r
        for r in public
        if r["site_code"] == "ocean-park-1"
        and r.get("kind") == "subdivision"
        and r.get("name") == building.get("parent_name")
    ]
    if len(zones) != 1:
        raise ValueError("Building needs one sourced parent subdivision")
    zone = zones[0]
    for record in [zone, building]:
        if record.get("authority") != "reference" or not record.get("sources"):
            raise ValueError("Only sourced reference geography may prefill a candidate")
        for url in record["sources"]:
            address = urlsplit(url)
            if (
                address.scheme != "https"
                or address.username
                or address.password
                or not (address.hostname or "").endswith(".vinhomes.vn")
            ):
                raise ValueError("Official Vinhomes geography source required")
    # This matches the reference key created by owner_review; it is never an official zone master code.
    zone_code = "ref-" + zone["record_code"].split("/", 1)[1]
    result = prepare(output, zone_code, building_code)
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    manifest.update(
        version="reference-draft-20261015", exported_at=datetime.now(UTC).isoformat()
    )
    manifest["prefill"] = {
        "status": "pending_owner_review",
        "zone_code_kind": "internal_reference",
        "building_code_kind": "public_source",
        "master_activation": False,
        "policy_activation": False,
    }
    geography = output / "evidence/public-geography.json"
    geography.write_text(
        json.dumps([zone, building], ensure_ascii=False, indent=2),
        encoding="utf-8",
        newline="\n",
    )
    workflow = output / "evidence/software-workflow.json"
    workflow.write_text(
        (output / "system-workflow.json").read_text(encoding="utf-8"),
        encoding="utf-8",
        newline="\n",
    )
    references = {
        "PUBLIC-OP1-GEOGRAPHY-20261015": geography,
        "SYSTEM-WORKFLOW-PROPOSAL-20261015": workflow,
    }
    manifest["source_documents"] = [
        {
            "document_reference": code,
            "file": p.relative_to(output).as_posix(),
            "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
        }
        for code, p in references.items()
    ]
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    fields = {**FIELDS, "sops": SOP_FIELDS}
    rows = {table: [] for table in fields}
    base = {
        "site_code": "ocean-park-1",
        "zone_code": zone_code,
        "building_code": building_code,
    }
    rows["zones"] = [
        {
            **base,
            "name": zone["name"],
            "document_reference": "PUBLIC-OP1-GEOGRAPHY-20261015",
        }
    ]
    rows["buildings"] = [
        {
            **base,
            "name": building["name"],
            "document_reference": "PUBLIC-OP1-GEOGRAPHY-20261015",
        }
    ]
    rows["coverage"] = [
        {
            **base,
            "category_code": "technical",
            "document_reference": "SYSTEM-WORKFLOW-PROPOSAL-20261015",
        }
    ]
    for code, title in [
        ("electrical", "điện và chiếu sáng"),
        ("water", "cấp thoát nước"),
        ("hvac", "điều hòa và thông gió"),
    ]:
        service = {
            **base,
            "service_code": "proposal-technical-" + code,
            "title": "Đề xuất tiếp nhận sự cố " + title,
            "category_code": "technical",
            "currency": "VND",
            "document_reference": "SYSTEM-WORKFLOW-PROPOSAL-20261015",
        }
        rows["services"].append(service)
        for audience in ["resident", "staff"]:
            rows["sops"].append(
                {
                    **base,
                    "sop_code": "proposal-" + code + "-" + audience,
                    "service_code": service["service_code"],
                    "title": "Dự thảo luồng phần mềm — " + title + " — " + audience,
                    "audience": audience,
                    "request_kind": "incident",
                    "clock_policy": "elapsed",
                    "approval_policy": "resident_quote_and_completion",
                    "document_reference": "SYSTEM-WORKFLOW-PROPOSAL-20261015",
                    "intake_requirements": "Giữ nguyên các hạng mục cư dân báo, vị trí và ảnh đính kèm; danh tính/cư trú lấy từ quyền và ticket đã xác minh, không yêu cầu Platform xác định lại cư dân.",
                    "evidence_requirements": "Ảnh trước/sau đúng work order, kết quả xử lý; bổ sung ảnh nghiệm thu khi bước nghiệm thu yêu cầu.",
                    "acceptance_criteria": "Cư dân tự quyết định phương án/chi phí và xác nhận kết quả hoặc yêu cầu xử lý lại; không tự suy ra đã đồng ý. Tiêu chí kỹ thuật cần đơn vị vận hành bổ sung.",
                    "steps": "Reception tiếp nhận → Domain tạo ticket → Platform điều phối → staff nhận/ETA, di chuyển, đến nơi → phương án/chi phí → cư dân quyết định → xử lý và bằng chứng → Platform cập nhật → cư dân nghiệm thu/xử lý lại. Đây là khung phần mềm, chưa phải SOP vận hành được duyệt.",
                }
            )
    gaps = []
    for table, records in rows.items():
        header = fields[table].split() + REVIEW
        cleaned = [{field: row.get(field, "") for field in header} for row in records]
        with (output / (table + ".csv")).open(
            "w", encoding="utf-8-sig", newline=""
        ) as stream:
            writer = csv.DictWriter(stream, fieldnames=header)
            writer.writeheader()
            writer.writerows(cleaned)
        if not cleaned:
            gaps.append(
                {
                    "dataset": table,
                    "row": "",
                    "field": "owner_records",
                    "reason": "Chưa có hồ sơ được phép sử dụng; không tạo người/căn/ca hoặc pháp nhân giả.",
                }
            )
        for index, row in enumerate(cleaned, 2):
            for key, value in row.items():
                if not value and key not in {"effective_until", "fee_amount"}:
                    gaps.append(
                        {
                            "dataset": table,
                            "row": index,
                            "field": key,
                            "reason": "Cần đơn vị chủ dữ liệu đối soát/xác nhận; không suy ra từ nguồn công khai.",
                        }
                    )
    with (output / "missing-data.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as stream:
        writer = csv.DictWriter(
            stream, fieldnames=["dataset", "row", "field", "reason"]
        )
        writer.writeheader()
        writer.writerows(gaps)
    summary = {
        **result,
        "candidate_rows": {table: len(records) for table, records in rows.items()},
        "missing_items": len(gaps),
        "operational_ready": False,
        "source_catalog_sha256": hashlib.sha256(
            catalog.read_bytes().replace(b"\r\n", b"\n")
        ).hexdigest(),
        "source_catalog_hash_encoding": "UTF-8 with LF line endings",
    }
    (output / "candidate-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--zone-code", default="")
    parser.add_argument("--building-code", default="")
    parser.add_argument(
        "--reference-catalog",
        type=Path,
        help="Prefill a candidate with sourced geography and proposed software steps; never owner approval",
    )
    args = parser.parse_args()
    try:
        result = (
            prepare_candidate(
                args.output, args.reference_catalog, args.building_code or "S1.01"
            )
            if args.reference_catalog
            else prepare(args.output, args.zone_code, args.building_code)
        )
    except (ValueError, OSError) as exc:
        parser.exit(1, type(exc).__name__ + ": output refused\n")
    print(json.dumps(result, indent=2))
