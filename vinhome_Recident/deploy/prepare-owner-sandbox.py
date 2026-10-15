"""Generate complete synthetic OP1 technical data; never operator-certified data.

python prepare-owner-sandbox.py --output DIR
Output is a new directory. Import is separately guarded by owner_sandbox.py.
"""

import argparse
import csv
import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from vinhomes_api.owner_bundle import FIELDS, REVIEW, SOP_FIELDS, validate


def prepare(output: Path, now=None):
    now = (now or datetime.now(UTC)).replace(microsecond=0)
    if output.exists() and any(output.iterdir()):
        raise ValueError("Refusing to overwrite an existing bundle")
    output.mkdir(parents=True, exist_ok=True)
    stamp = lambda value: value.isoformat()
    start, end = now - timedelta(days=1), now + timedelta(days=30)
    review = {
        "document_reference": "SIMULATION-NOT-OWNER-APPROVAL",
        "approved_by": "SIMULATION-REVIEWER-NOT-OPERATOR",
        "approved_at": stamp(start),
        "effective_from": stamp(start),
        "effective_until": stamp(end),
    }
    scope = {
        "site_code": "ocean-park-1",
        "zone_code": "SIM-OP1-ZONE",
        "building_code": "SIM-OP1-TOWER",
    }
    operator = "SIM-TECH-OPERATOR"
    rows = {name: [] for name in (*FIELDS, "sops")}

    def add(table, **values):
        fields = (SOP_FIELDS if table == "sops" else FIELDS[table]).split() + REVIEW
        rows[table].append(
            {key: str(({**review, **scope, **values}).get(key, "")) for key in fields}
        )

    add(
        "operators",
        operator_code=operator,
        legal_name="[MÔ PHỎNG] Đơn vị kỹ thuật OP1",
        contact_reference="SIM-HELPDESK: sandbox only, no real phone/email delivery",
    )
    add(
        "zones",
        name="[MÔ PHỎNG] Phân khu nghiệm thu OP1",
        operator_code=operator,
        current_address="Địa bàn giả lập trong OP1; không đại diện phân khu thực",
    )
    add(
        "buildings",
        name="[MÔ PHỎNG] Tòa nghiệm thu kỹ thuật",
        operator_code=operator,
        current_address="Tòa giả lập; không phải master căn hộ của Vinhomes",
    )
    for index, relation in ((1, "owner"), (2, "tenant")):
        add(
            "units",
            unit_code=f"SIM-UNIT-{index:03d}",
            asset_type="apartment",
            operator_code=operator,
        )
        add(
            "residents",
            unit_code=f"SIM-UNIT-{index:03d}",
            account_code=f"sim-resident-{index}",
            name=f"[MÔ PHỎNG] Cư dân {index}",
            email=f"resident{index}@op1-sandbox.test",
            relation=relation,
            valid_from=stamp(start),
            valid_until=stamp(end),
            verification_reference="SIMULATED-RESIDENCY-NOT-REAL-VERIFICATION",
        )
    add(
        "coverage",
        operator_code=operator,
        category_code="technical",
        platform_route_id="sim-op1-technical",
        route_revision="1",
    )
    for index in (1, 2):
        add(
            "staff",
            employee_code=f"SIM-TECH-{index}",
            name=f"[MÔ PHỎNG] Kỹ thuật viên {index}",
            email=f"technician{index}@op1-sandbox.test",
            operator_code=operator,
            category_code="technical",
            max_concurrent_jobs="1",
            backup_employee_code=f"SIM-TECH-{3 - index}",
        )
        for day in range(3):
            shift = now - timedelta(minutes=30) + timedelta(days=day)
            add(
                "shifts",
                employee_code=f"SIM-TECH-{index}",
                starts_at=stamp(shift),
                ends_at=stamp(shift + timedelta(hours=8)),
            )
    for code, title, fee, amount in (
        ("SIM-ELECTRIC", "Kiểm tra đèn/ổ điện", "quote", ""),
        ("SIM-WATER", "Kiểm tra rò nước", "fixed", "100000"),
        ("SIM-HVAC", "Kiểm tra điều hòa", "free", "0"),
    ):
        add(
            "services",
            service_code=code,
            title="[MÔ PHỎNG] " + title,
            category_code="technical",
            operator_code=operator,
            eligibility="Chỉ hai căn SIM đã xác minh giả lập; không nhận việc thực",
            fee_policy=fee,
            fee_amount=amount,
            currency="VND",
            fee_unit="lượt kiểm tra mô phỏng",
            vat_policy="MÔ PHỎNG: giá thử nghiệm đã gồm VAT giả định 10%; không phải hóa đơn/thuế thực",
            operating_hours="Theo ca sandbox 8 giờ/ngày trong shifts.csv, 3 ngày từ lúc sinh dữ liệu",
            warranty_policy="MÔ PHỎNG: 3 tháng cho phần thay thế đã được cư dân đồng ý",
            booking_policy="Cư dân chọn lịch; Platform phân công người đang có ca và còn năng lực",
            cancellation_policy="Hủy trước nhận việc không phí giả lập; sau nhận phải xác nhận qua Platform",
            contact_reference="SIM-HELPDESK: chỉ hộp thư nội bộ sandbox",
        )
        for audience in ("resident", "staff"):
            add(
                "sops",
                sop_code=f"{code}-{audience}",
                service_code=code,
                title=f"[MÔ PHỎNG] SOP {title} — {audience}",
                audience=audience,
                request_kind="service_request",
                priority="normal",
                response_minutes="30",
                resolution_minutes="240",
                clock_policy="elapsed",
                intake_requirements="Vị trí, thiết bị, triệu chứng, thời điểm, ảnh nếu có; giữ mọi hạng mục đã cung cấp",
                safety_policy="Không tự thao tác nguồn điện/rò nước. Nguy cơ cháy/điện giật: dừng xử lý thường và chuyển khẩn cấp; không thử nguy hiểm",
                escalation_policy="Không có người/ca hoặc quá SLA: báo Platform; Platform điều phối người dự phòng, không tự gán người ngoài phạm vi",
                evidence_requirements="Ảnh trước và sau gắn đúng ticket/work order; kết quả, vật tư, chi phí và thời điểm",
                acceptance_criteria="Staff báo kết quả; Platform tổng hợp; cư dân xác nhận hoặc yêu cầu xử lý lại với lý do",
                approval_policy="resident_quote_and_completion",
                steps="Tiếp nhận → ticket → Platform → mời staff → nhận với ETA/từ chối có lý do → di chuyển → đến nơi → báo giá → cư dân đồng ý → thực hiện → ảnh trước/sau → Platform báo kết quả → cư dân nghiệm thu/xử lý lại",
            )
    evidence = output / "evidence"
    evidence.mkdir(exist_ok=True)
    proof = evidence / "simulation.txt"
    proof.write_text(
        "SYNTHETIC TEST ONLY. No operator approval, real persons, real units, tariff or SLA.\n",
        encoding="utf-8",
    )
    manifest = {
        "schema_version": 2,
        "bundle_code": "op1-technical-simulation",
        "version": now.strftime("%Y%m%dT%H%M%SZ"),
        "data_mode": "synthetic_test",
        "data_owner": "SIMULATION-NOT-OPERATOR",
        "exported_at": stamp(now),
        "document_reference": review["document_reference"],
        "site_codes": [scope["site_code"]],
        "pilot": {**scope, "category_codes": ["technical"]},
        "source_documents": [
            {
                "document_reference": review["document_reference"],
                "file": "evidence/simulation.txt",
                "sha256": hashlib.sha256(proof.read_bytes()).hexdigest(),
            }
        ],
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    for table, records in rows.items():
        with (output / f"{table}.csv").open(
            "w", encoding="utf-8-sig", newline=""
        ) as stream:
            writer = csv.DictWriter(
                stream,
                fieldnames=(SOP_FIELDS if table == "sops" else FIELDS[table]).split()
                + REVIEW,
            )
            writer.writeheader()
            writer.writerows(records)
    (output / "README.md").write_text(
        "# OP1/Kỹ thuật — dữ liệu mô phỏng\n\n"
        "Chỉ dùng database sandbox riêng `owner_pilot_test_<32 hex>`. Không dùng trên VPS production.\n\n"
        "25 bản ghi: 1 đơn vị, 1 phân khu, 1 tòa, 2 căn, 2 cư trú, 1 tuyến, 2 staff, 6 ca, 3 dịch vụ, 6 SOP. "
        "Mọi người/căn/phí/VAT/SLA/giờ/bảo hành/phê duyệt đều giả lập. Không có hồ sơ vận hành được xác nhận.\n\n"
        "Ca đầu hoạt động ngay trong 7,5 giờ; hai ca tiếp theo cùng giờ trong hai ngày kế. "
        "Sau đó sinh bundle mới trong sandbox mới. Không sửa thời gian để làm giả hiệu lực hồ sơ thật.\n\n"
        "Platform chỉ nhận ngữ cảnh ticket và quyền MCP; CSV cư trú/nhân sự không được xuất sang Platform. "
        "Báo cáo CSV hợp lệ chứng minh tính đầy đủ/liên kết, không chứng minh đơn vị vận hành xác nhận.\n",
        encoding="utf-8",
    )
    report = validate(output, now)
    if not report["valid"]:
        raise ValueError(
            "Generated bundle failed validation: " + "; ".join(report["errors"])
        )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.output), ensure_ascii=False, indent=2))
