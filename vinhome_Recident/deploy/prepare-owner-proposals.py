"""Build a pending-review handoff from the sourced catalog. Offline; never imports operational data."""

import argparse
import csv
import hashlib
import io
import json
from collections import Counter
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

SITES = ("ocean-park-1", "ocean-park-2", "ocean-park-3")
CATEGORIES = {"technical": "Kỹ thuật", "security": "An ninh", "sanitation": "Vệ sinh"}
POLICY_FIELDS = (
    "operator_code",
    "scope_reference",
    "eligibility",
    "fee_policy",
    "fee_amount",
    "currency",
    "fee_unit",
    "vat_policy",
    "operating_hours",
    "warranty_policy",
    "booking_policy",
    "cancellation_policy",
    "contact_reference",
    "sop_reference",
    "sla_reference",
)
REQUESTS = {
    "operators": (
        "Đơn vị vận hành",
        "Tên pháp lý, mã đơn vị, hợp đồng/bàn giao, đầu mối và phạm vi thực tế",
    ),
    "units": (
        "Danh sách căn/lô",
        "Mã chuẩn, khu/phân khu/tòa/dãy, căn/lô, địa chỉ hiện hành, loại tài sản, đơn vị quản lý",
    ),
    "residents": (
        "Hồ sơ cư trú",
        "Mã tài khoản, liên hệ cần thiết, căn/lô, quan hệ, hiệu lực, mã hồ sơ và người xác minh",
    ),
    "staff_roster": (
        "Danh sách nhân sự",
        "Mã nhân viên, tài khoản, chuyên môn, đơn vị, phạm vi, năng lực đồng thời và người dự phòng",
    ),
    "staff_shifts": (
        "Lịch trực",
        "Mã nhân viên, phạm vi, bắt đầu/kết thúc có múi giờ, nghỉ phép, trực dự phòng và kỳ bàn giao",
    ),
}


def build(source):
    records = []

    def add(site, dataset, key, title, basis, sources, data, missing):
        records.append(
            {
                "proposal_id": str(
                    uuid5(
                        NAMESPACE_URL,
                        f"vinhomes-owner-proposal/v1/{site}/{dataset}/{key}",
                    )
                ),
                "site_code": site,
                "dataset": dataset,
                "proposal_code": key,
                "title": title,
                "basis": basis,
                "sources": sources,
                "review_status": "pending_owner_review",
                "operational_import_allowed": False,
                "data": data,
                "requires_confirmation": missing,
                "approved_by": None,
                "approved_at": None,
                "document_reference": None,
                "effective_from": None,
                "effective_until": None,
            }
        )

    seen = set()
    for row in source:
        key = (row["site_code"], row["record_code"])
        if (
            row["site_code"] not in SITES
            or row["authority"] != "reference"
            or row["kind"] not in {"subdivision", "building", "amenity"}
            or key in seen
        ):
            raise ValueError("Expected unique, site-scoped public reference records")
        seen.add(key)
        if row["kind"] == "amenity":
            add(
                row["site_code"],
                "services",
                row["record_code"],
                row["name"],
                "public_amenity_reference",
                row["sources"],
                {
                    "service_code": None,
                    "category_code": None,
                    "reference_kind": "amenity",
                    "source_published_at": row["source_published_at"],
                    "retrieved_at": row["retrieved_at"],
                    **dict.fromkeys(POLICY_FIELDS),
                },
                [
                    "Tên/mã dịch vụ vận hành và tình trạng phục vụ hiện tại",
                    "Có thuộc quyền cư dân hay phục vụ khách/đơn vị độc lập",
                    *POLICY_FIELDS,
                ],
            )
        else:
            add(
                row["site_code"],
                "geography",
                row["record_code"],
                row["name"],
                "public_geography_reference",
                row["sources"],
                {
                    "kind": row["kind"],
                    "official_code": row["official_code"],
                    "public_parent_name": row.get("parent_name"),
                    "zone_code": None,
                    "building_code": None,
                    "operator_code": None,
                    "current_address": None,
                    "operational_status": None,
                    "source_published_at": row["source_published_at"],
                    "retrieved_at": row["retrieved_at"],
                },
                [
                    "Đối chiếu tên/mã và quan hệ cha-con trên master hiện hành",
                    "Địa chỉ hiện hành, tình trạng bàn giao và đơn vị vận hành",
                    "Danh sách căn/lô cần cấp riêng; không suy ra từ mã tòa",
                ],
            )
    for site in SITES:
        for category, name in CATEGORIES.items():
            add(
                site,
                "services",
                "capability/" + category,
                name,
                "software_capability_proposal",
                ["repo:services/vinhomes-api/src/vinhomes_api/bootstrap.py"],
                {
                    "service_code": None,
                    "category_code": category,
                    "reference_kind": "workflow_proposal",
                    **dict.fromkeys(POLICY_FIELDS),
                    "platform_route_id": None,
                    "route_revision": None,
                    "proposed_workflow": "Reception tiếp nhận → Domain gửi ticket → Platform giao việc và quản lý tiến độ → staff phản hồi qua Domain → Platform gửi kết quả để cư dân quyết định",
                },
                [
                    "Đơn vị vận hành xác nhận có cung cấp dịch vụ và phạm vi từng khu/tòa",
                    "Phân biệt tài sản chung, trong căn, nhà thầu và trường hợp khẩn cấp",
                    "Route/revision, nhân sự, bước cư dân đồng ý và tiêu chí nghiệm thu",
                    *POLICY_FIELDS,
                ],
            )
            add(
                site,
                "staffing_requirements",
                category,
                "Yêu cầu nhân sự " + name,
                "staffing_requirement_proposal",
                [],
                {
                    "category_code": category,
                    "operator_code": None,
                    "scope_reference": None,
                    "required_headcount": None,
                    "max_concurrent_jobs": None,
                    "backup_policy": None,
                    "shift_plan_reference": None,
                    "qualification_reference": None,
                },
                [
                    "Danh sách nhân sự thật, chuyên môn, phạm vi và trạng thái làm việc",
                    "Năng lực đồng thời, lịch trực có múi giờ, nghỉ phép và người dự phòng",
                    "Không phải tài khoản nhân viên; chưa cho phép giao việc",
                ],
            )
        for dataset, (title, required) in REQUESTS.items():
            add(
                site,
                "data_requests",
                dataset,
                title,
                "owner_data_request",
                [],
                {
                    "requested_dataset": dataset,
                    "required_information": required,
                    "data_owner": None,
                    "secure_handoff_reference": None,
                },
                [
                    "Đơn vị sở hữu cấp export/API được phép và xác nhận nguồn/hiệu lực",
                    "Không đưa mật khẩu, giấy tờ định danh hay danh sách cá nhân vào Git/chat",
                ],
            )
    return records


def write_pack(catalog, output):
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(
            "Output must be empty; existing reviewer edits must be preserved."
        )
    records = build(json.loads(catalog.read_text(encoding="utf-8")))
    output.mkdir(parents=True, exist_ok=True)
    # Keep the recorded file hashes stable in Windows and Linux Git checkouts.
    (output / ".gitattributes").write_text(
        "*.csv -text whitespace=cr-at-eol\n**/*.csv -text whitespace=cr-at-eol\n*.jsonl text eol=lf\n", encoding="utf-8"
    )
    review_fields = [
        "proposal_id",
        "site_code",
        "dataset",
        "proposal_code",
        "title",
        "basis",
        "decision",
        "reviewer",
        "reviewed_at",
        "document_reference",
        "effective_from",
        "effective_until",
        "correction",
        "notes",
    ]
    files = {}

    def csv_bytes(rows, fields):
        buffer = io.StringIO(newline="")
        writer = csv.DictWriter(buffer, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
        return buffer.getvalue().encode("utf-8-sig")

    for site in SITES:
        for dataset in (
            "geography",
            "services",
            "staffing_requirements",
            "data_requests",
        ):
            selected = [
                row
                for row in records
                if row["site_code"] == site and row["dataset"] == dataset
            ]
            fields = [
                "proposal_id",
                "site_code",
                "proposal_code",
                "title",
                "basis",
                "review_status",
                "sources",
            ]
            fields += list(
                dict.fromkeys(key for row in selected for key in row["data"])
            )
            fields += ["requires_confirmation"]
            flat = []
            for row in selected:
                values = {key: row[key] for key in fields[:6]}
                values.update(row["data"])
                values["sources"] = " | ".join(row["sources"])
                values["requires_confirmation"] = " | ".join(
                    row["requires_confirmation"]
                )
                flat.append(values)
            files[f"{site}/{dataset}.csv"] = csv_bytes(flat, fields)
    reviews = [
        {field: row.get(field, "") for field in review_fields} for row in records
    ]
    for row in reviews:
        row["decision"] = "pending"
    files["review-register.csv"] = csv_bytes(reviews, review_fields)
    files["proposals.jsonl"] = (
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
            for row in records
        )
    ).encode("utf-8")
    for name, content in files.items():
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    manifest = {
        "schema_version": "owner-proposal-v1",
        "prepared_on": "2026-10-14",
        "site_codes": list(SITES),
        "review_status": "pending_owner_review",
        "operational_import_allowed": False,
        "data_owner": None,
        "document_reference": None,
        "source_catalog_sha256": hashlib.sha256(catalog.read_bytes()).hexdigest(),
        "counts": dict(Counter(row["dataset"] for row in records)),
        "total_proposals": len(records),
        "files": {
            name: hashlib.sha256(content).hexdigest() for name, content in files.items()
        },
        "note": "Đây là hồ sơ đề xuất chờ đối soát; sửa CSV không tự duyệt, cấp quyền hoặc ghi database.",
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = write_pack(args.catalog, args.output)
    print(
        json.dumps(
            {
                "total_proposals": report["total_proposals"],
                "counts": report["counts"],
                "review_status": report["review_status"],
                "database_written": False,
            }
        )
    )
