"""Presentation and roster maintenance for an explicitly marked synthetic release.

Stable identity/route IDs and source evidence are preserved. This does not certify
residency, tax rates, personnel or policies on behalf of an operator.
"""

import argparse
import asyncio
import hashlib
import json
import os
import re
import secrets
from collections import defaultdict
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit
from uuid import NAMESPACE_URL, uuid5

import asyncpg

from .database import TENANT, _url
from .knowledge import fold, passage
from .password_auth import password_hash
from .synthetic_op2 import transition_path

PROFILE = "operating-data-20261015-v1"
TEAMS = {"technician": ("kythuat", "Kỹ thuật"), "security": ("anninh", "An ninh"),
         "sanitation": ("vesinh", "Vệ sinh"), "desk": ("dichvu", "Hỗ trợ dịch vụ")}
LABELS = {"access": "Thẻ cư dân", "visitors": "Khách ra vào", "billing": "Công nợ",
          "amenities": "Tiện ích và đặt chỗ", "renovation": "Đăng ký cải tạo",
          "security": "Hỗ trợ an ninh", "sanitation": "Vệ sinh"}
PATCH_COLUMNS = {
    "users": {"email", "name"}, "zones": {"name", "metadata"},
    "buildings": {"name", "metadata"}, "units": {"code", "floor"},
    "management_units": {"name", "contact_email", "metadata"},
    "staff_profiles": {"employee_code"}, "domain_service_catalog": {"title", "policy"},
    "owner_data_records": {"title", "proposal", "source_hash"},
    "vehicles": {"owner_name", "plate_no"}, "access_cards": {"holder_name", "card_no"},
    "visitor_passes": {"guest_name", "code"}, "debit_notes": {"note", "doc_no"},
    "debit_note_lines": {"description"},
    "amenities": {"name", "rules_note"}, "construction_policies": {"note"},
    "construction_permits": {"contractor_name", "scope_description", "code"},
    "service_requests": {"details", "code"}, "zone_settings": {"note"},
    "vh_knowledge_documents": {"title", "version_id", "metadata"},
    "vh_knowledge_chunks": {"heading_path", "text_content", "text_hash", "embedding", "token_count"},
}
INSERT_TABLES = ["users", "accounts", "tenant_memberships", "scoped_user_roles", "staff_profiles", "staff_specialties", "staff_shifts", "owner_data_records", "vh_knowledge_documents", "vh_knowledge_chunks"]


def uid(value):
    return str(uuid5(NAMESPACE_URL, PROFILE + "/" + value))


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def display(value):
    return re.sub(r"\[MÔ PHỎNG(?: OP[123])?\]\s*", "", value or "").strip()


def build(snapshot, *, email_domain="accounts.vinhome.test", now=None, hasher=password_hash, reference_documents=()):
    """Return a replayable private plan and credentials for NEW staff only."""
    if not re.fullmatch(r"[a-z0-9.-]+\.test", email_domain) or ".." in email_domain:
        raise ValueError("Generated logins require a reserved .test domain")
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        raise ValueError("An aware timestamp is required")
    plan = {"profile": PROFILE, "data_mode": "synthetic_test", "email_domain": email_domain,
            "patches": defaultdict(list), "inserts": {t: [] for t in INSERT_TABLES}, "cancel_shifts": [],
            "created_at": now.isoformat(), "identities": []}
    credentials = []

    def patch(table, row, **changes):
        changed = {k: v for k, v in changes.items() if row.get(k) != v}
        if changed:
            key = "zone_id" if table == "zone_settings" else "id"
            plan["patches"][table].append({"key": key, "id": row[key], "before": {k: row.get(k) for k in changed}, "after": changed})

    sites = {s["id"]: "op" + s["code"][-1] for s in snapshot["sites"]}
    users = {u["id"]: u for u in snapshot["users"]}
    admins = {r["user_id"] for r in snapshot["platform_admins"]}
    residents = {r["user_id"]: r for r in snapshot["unit_residents"]}
    units = {u["id"]: u for u in snapshot["units"]}
    operators = {m["id"]: m for m in snapshot["management_units"] if m["code"].startswith("SIM-")}
    operator_sites = {m["id"]: ("op1" if m["code"] == "SIM-TECH-OPERATOR" else "op" + m["code"][6]) for m in operators.values()}
    profiles = deepcopy(snapshot["staff_profiles"])
    memberships = {m["user_id"]: m for m in snapshot["tenant_memberships"]}
    op1_profiles = [p for p in profiles if operator_sites.get(p["management_unit_id"]) == "op1"]
    if len(op1_profiles) != 8:
        raise ValueError("Expected the bounded eight-person OP1 roster")
    for cohort in (2, 3):
        for original in op1_profiles:
            old = users[original["user_id"]]
            user_id = "sim-op1-c" + str(cohort) + "-" + old["id"]
            user = {**old, "id": user_id, "phone_e164": None, "phone_verified_at": None,
                    "last_signed_in_at": None, "created_at": now.isoformat(), "updated_at": now.isoformat()}
            member = {**memberships[old["id"]], "id": uid("membership/" + user_id), "user_id": user_id}
            role = next(r for r in snapshot["scoped_user_roles"] if r["membership_id"] == memberships[old["id"]]["id"] and r["role_code"] == "staff")
            profile = {**original, "id": uid("staff/" + user_id), "user_id": user_id, "availability": "available"}
            plan["inserts"]["tenant_memberships"].append(member)
            plan["inserts"]["scoped_user_roles"].append({**role, "id": uid("role/" + user_id), "membership_id": member["id"]})
            for specialty in snapshot["staff_specialties"]:
                if specialty["staff_id"] == original["id"]:
                    plan["inserts"]["staff_specialties"].append({**specialty, "staff_id": profile["id"]})
            profile["_cohort"] = cohort
            profiles.append(profile)
            user["_source_email"] = old["email"]
            users[user_id] = user

    profile_by_user = {p["user_id"]: p for p in profiles}
    counters = defaultdict(int)
    building_names = {}
    for site_id, slug in sites.items():
        buildings = sorted((b for b in snapshot["buildings"] if b["site_id"] == site_id and b["metadata"].get("data_mode") == "synthetic_test"), key=lambda b: b["code"])
        for n, b in enumerate(buildings, 1):
            code = slug.upper() + "-" + chr(64 + n)
            building_names[b["id"]] = code
            patch("buildings", b, name="Tòa " + code, metadata={**b["metadata"], "presentation_profile": PROFILE})
            for index, unit in enumerate(sorted((u for u in units.values() if u["building_id"] == b["id"]), key=lambda u: u["code"]), 1):
                patch("units", unit, code=code + f"-01{index:02d}", floor="1")
        for z in snapshot["zones"]:
            if z["site_id"] == site_id and z["metadata"].get("data_mode") == "synthetic_test":
                patch("zones", z, name="Khu dịch vụ cư dân " + slug.upper(), metadata={**z["metadata"], "presentation_profile": PROFILE})

    def identity_order(user):
        original = user.get("_source_email", user["email"])
        p = profile_by_user.get(user["id"], {})
        match = re.search(r"\.c([123])", original)
        return (re.sub(r"[0-9].*", "", original), p.get("_cohort", int(match[1]) if match else 1), original)

    for user in sorted(users.values(), key=identity_order):
        if user["id"] in admins:
            slug, team, label, cohort, role = "all", "admin", "Quản trị hệ thống", None, "admin"
        elif user["id"] in residents:
            slug = sites[units[residents[user["id"]]["unit_id"]]["site_id"]]
            team, label, cohort, role = "cudan", "Cư dân", None, "customer"
        elif user["id"] in profile_by_user:
            p = profile_by_user[user["id"]]
            slug = operator_sites[p["management_unit_id"]]
            stem = user.get("_source_email", user["email"]).split("@", 1)[0]
            original_team = next(t for t in TEAMS if stem.startswith(t))
            team, label = TEAMS[original_team]
            match = re.search(r"\.c([123])", stem)
            cohort = p.get("_cohort", int(match[1]) if match else 1)
            role = "staff"
        else:
            raise ValueError("Refusing an identity outside the known release")
        counters[(slug, team)] += 1
        index = counters[(slug, team)]
        email = f"{slug}.{team}.{index:02d}@{email_domain}"
        name = f"{label} {slug.upper()} · {index:02d}" if slug != "all" else f"{label} · {index:02d}"
        identity = {"user_id": user["id"], "previous_email": user["email"], "email": email, "name": name,
                    "site": slug, "role": role, "team": team, "cohort": cohort,
                    "unit_id": residents.get(user["id"], {}).get("unit_id"), "data_mode": "synthetic_test"}
        plan["identities"].append(identity)
        if "_source_email" in user:
            password = secrets.token_urlsafe(24)
            plan["inserts"]["users"].append({k: v for k, v in {**user, "email": email, "name": name}.items() if not k.startswith("_")})
            plan["inserts"]["accounts"].append({"id": uid("account/" + user["id"]), "account_id": user["id"], "provider_id": "vinhomes-password-v1", "user_id": user["id"], "password": hasher(password)})
            credentials.append({**identity, "password": password})
            p = profile_by_user[user["id"]]
            plan["inserts"]["staff_profiles"].append({k: v for k, v in {**p, "employee_code": f"{slug.upper()}-{team.upper()}-{index:02d}"}.items() if not k.startswith("_")})
        else:
            patch("users", user, email=email, name=name)
            if role == "staff":
                patch("staff_profiles", profile_by_user[user["id"]], employee_code=f"{slug.upper()}-{team.upper()}-{index:02d}")

    identities = {u["user_id"]: u for u in plan["identities"]}
    # Preserve historical shifts; cancel only the old, not-yet-started OP1 slots.
    old_staff = {p["id"] for p in op1_profiles}
    plan["cancel_shifts"] = [s["id"] for s in snapshot["staff_shifts"] if s["staff_id"] in old_staff and datetime.fromisoformat(s["starts_at"]) > now and s["status"] in {"available", "scheduled"}]
    start = now.replace(hour=(now.hour // 8) * 8, minute=0, second=0, microsecond=0)
    for p in profiles:
        identity = identities[p["user_id"]]
        if identity["site"] != "op1":
            continue
        for day in range(14):
            at = start + timedelta(days=day, hours=8 * (identity["cohort"] - 1))
            # Explicit future leave for one backup; its partner covers the same specialty.
            leave = identity["cohort"] == 2 and identity["team"] == "anninh" and p["user_id"].endswith("security-2") and day == 3
            plan["inserts"]["staff_shifts"].append({"id": uid(f"shift/{p['id']}/{at.isoformat()}"), "tenant_id": TENANT, "staff_id": p["id"], "starts_at": at.isoformat(), "ends_at": (at + timedelta(hours=8)).isoformat(), "status": "leave" if leave else "available"})

    for m in operators.values():
        slug = operator_sites[m["id"]]
        patch("management_units", m, name="Đội dịch vụ cư dân " + slug.upper(), contact_email=f"{slug}.dichvu@{email_domain}", metadata={**m["metadata"], "presentation_profile": PROFILE, "operator_approval": False})
    for table, column, user_key in (("vehicles", "owner_name", "owner_user_id"), ("access_cards", "holder_name", "holder_user_id")):
        for row in snapshot[table]:
            if row[user_key] in identities:
                patch(table, row, **{column: identities[row[user_key]]["name"]})
    for row in snapshot["visitor_passes"]:
        patch("visitor_passes", row, guest_name="Khách thăm " + identities[row["host_user_id"]]["name"])
    for row in snapshot["amenities"]:
        slug = sites[next(z["site_id"] for z in snapshot["zones"] if z["id"] == row["zone_id"])]
        patch("amenities", row, name=("Phòng sinh hoạt cộng đồng " if row["category"] == "community_room" else "Khu BBQ ") + slug.upper(), rules_note="Đặt theo khung giờ và số chỗ còn trống; kiểm tra điều kiện trên phiếu trước khi xác nhận.")
    for row in snapshot["debit_notes"]:
        patch("debit_notes", row, note="Bảng kê phục vụ đối soát trên hệ thống; kiểm tra chi tiết trước khi xác nhận. Không phải hóa đơn thuế.")
    for row in snapshot["zone_settings"]:
        patch("zone_settings", row, note="Áp dụng trong phạm vi khu; kiểm tra trạng thái và điều kiện trước khi tiếp nhận.")
    for row in snapshot["construction_policies"]:
        patch("construction_policies", row, note="Đối chiếu khung giờ, tiền đặt cọc và phạm vi thi công trên hồ sơ; chỉ triển khai sau bước duyệt tương ứng.")
    for row in snapshot["construction_permits"]:
        patch("construction_permits", row, contractor_name="Đơn vị thi công đăng ký", scope_description="Cải tạo nội thất trong phạm vi căn; không can thiệp kết cấu và hệ thống chung.")
    # Operational record IDs stay stable; clean the human-facing reference numbers.
    for table, column, prefix in (("vehicles", "plate_no", "XE"), ("access_cards", "card_no", "THE"), ("visitor_passes", "code", "KH"), ("debit_notes", "doc_no", "BK"), ("construction_permits", "code", "CT"), ("service_requests", "code", "DV")):
        numbers = defaultdict(int)
        for row in sorted(snapshot[table], key=lambda r: r["id"]):
            slug = sites[units[row["unit_id"]]["site_id"]]
            numbers[slug] += 1
            values = {column: f"{slug.upper()}-{prefix}-{numbers[slug]:04d}"}
            if table == "service_requests":
                values["details"] = {**row["details"], "note": "Yêu cầu cấp lại thẻ cư dân; đối chiếu thẻ hiện tại và điều kiện xử lý."}
            existing = next((p for p in plan["patches"][table] if p["id"] == row["id"]), None)
            if existing:
                existing["before"].update({k: row.get(k) for k in values})
                existing["after"].update(values)
            else:
                patch(table, row, **values)
    for row in snapshot.get("debit_note_lines", []):
        patch("debit_note_lines", row, description="Phí dịch vụ theo bảng kê của kỳ đối soát")

    for row in snapshot["domain_service_catalog"]:
        if row["policy"].get("data_mode") != "synthetic_test":
            continue
        title = LABELS.get(row["category_code"], display(row["title"]))
        policy = {**row["policy"], "title": title, "presentation_profile": PROFILE,
                  "operational_verified": False, "eligibility": "Cư dân có quan hệ cư trú hiệu lực trong phạm vi phục vụ.",
                  "operating_hours": "Theo lịch ca và năng lực được hệ thống công bố; lịch hẹn phải được xác nhận.",
                  "vat_policy": "Theo báo giá hiển thị của bộ dữ liệu dự án; không phải mức thuế hay hóa đơn chính thức.",
                  "booking_policy": "Tra cứu không giữ chỗ. Chọn lịch, kiểm tra khả dụng và xác nhận qua Platform.",
                  "cancellation_policy": "Gửi yêu cầu hủy qua Platform; kiểm tra trạng thái, chi phí đã thống nhất trước khi thực hiện.",
                  "warranty_policy": "Đối chiếu nội dung bảo hành trong phương án đã được cư dân đồng ý.",
                  "contact_reference": "Trợ lý cư dân và đầu mối được chỉ định trên ticket; không có hotline được xác minh.",
                  "policy_owner": "Nhóm quản trị dữ liệu dự án", "policy_version": PROFILE,
                  "review_status": "pending_operator_confirmation"}
        policy["fee_unit"] = "lượt kiểm tra" if row["category_code"] == "technical" else "lượt dịch vụ"
        patch("domain_service_catalog", row, title=title, policy=policy)
        record = next(r for r in snapshot["owner_data_records"] if r["id"] == row["id"])
        patch("owner_data_records", record, title=title, proposal=policy, source_hash=digest(policy))

    for d in snapshot["vh_knowledge_documents"]:
        if not d["category"].startswith("synthetic"):
            continue
        code = d["code"]
        category = next((c for c in LABELS if c in code), "technical")
        title = LABELS.get(category, display(d["title"]).replace(" — resident", "").replace(" — staff", "").removeprefix("SOP "))
        slug = sites[d["site_id"]]
        title = f"{slug.upper()} · {title} · " + ("Hướng dẫn cư dân" if d["audience"] == "resident" else "Quy trình nhân viên")
        text = service_text(category, d["audience"], slug.upper())
        patch("vh_knowledge_documents", d, title=title, version_id=uid("version/" + d["id"]), metadata={**d["metadata"], "presentation_profile": PROFILE, "data_mode": "synthetic_test", "operational_verified": False, "review_status": "pending_operator_confirmation", "content_owner": "Nhóm quản trị dữ liệu dự án", "effective_from": now.date().isoformat()})
        for chunk in snapshot["vh_knowledge_chunks"]:
            if chunk["document_id"] == d["id"]:
                patch("vh_knowledge_chunks", chunk, heading_path=title, text_content=text, text_hash=hashlib.sha256(text.encode()).hexdigest(), embedding=None, token_count=len(text.split()) * 2)

    for site_id, slug in sites.items():
        team = [i for i in plan["identities"] if i["site"] == slug and i["role"] == "staff"]
        roster = [{"user_id": i["user_id"], "team": i["team"], "cohort": i["cohort"], "capacity": 1,
                   "backup_user_ids": [j["user_id"] for j in team if j["team"] == i["team"] and j["cohort"] == i["cohort"] and j["user_id"] != i["user_id"]]} for i in team]
        for kind, payload in {
            "geography": {"building_ids": [k for k in building_names if next(b for b in snapshot["buildings"] if b["id"] == k)["site_id"] == site_id], "unit_ids": [u["id"] for u in units.values() if u["site_id"] == site_id]},
            "residency": {"relations": [r for r in snapshot["unit_residents"] if units[r["unit_id"]]["site_id"] == site_id], "real_subject_consent": "not_collected_no_real_subjects"},
            "staffing": {"roster": roster, "leave_shift_ids": [r["id"] for r in plan["inserts"]["staff_shifts"] if r["status"] == "leave"] if slug == "op1" else []},
            "service-policy": {"catalog_ids": [r["id"] for r in snapshot["domain_service_catalog"] if r["site_id"] == site_id], "authority": "project_scenario"},
        }.items():
            proposal = {"data_mode": "synthetic_test", "profile": PROFILE, "site": slug, "record_type": kind, "content": payload, "operator_approval": False}
            plan["inserts"]["owner_data_records"].append({"id": uid(slug + "/register/" + kind), "tenant_id": TENANT, "site_id": site_id,
                "dataset": "geography" if kind == "geography" else "data_requests", "proposal_code": f"{slug.upper()}-{PROFILE}-{kind}", "title": f"{slug.upper()} · Hồ sơ {kind}", "source_hash": digest(proposal), "proposal": proposal,
                "project_approval": {"scope": "project_dataset_maintenance", "operator_approval": False}, "operational_verified": False})
    known_codes = {d["code"] for d in snapshot["vh_knowledge_documents"]}
    for source in reference_documents:
        for site_code in source["sites"]:
            site = next((s for s in snapshot["sites"] if s["code"] == site_code), None)
            if site is None:
                raise ValueError("Unknown reference-document site")
            code = PROFILE + "/" + site_code + "/" + source["code"]
            if code in known_codes:
                raise ValueError("Reference already exists; replay the saved plan")
            document_id = uid(code)
            title = source["title"]
            text = source["text"]
            plan["inserts"]["vh_knowledge_documents"].append({"id": document_id, "tenant_id": TENANT, "site_id": site["id"],
                "code": code, "version_id": uid(code + "/version"), "title": title, "category": "resident-care-public-reference", "audience": "resident", "zone_id": None, "building_ids": None,
                "unverified": True, "metadata": {"data_mode": "public_reference", "operational_verified": False, "sources": source["sources"], "retrieved_at": "2026-10-15", "presentation_profile": PROFILE, "review_status": "pending_operator_confirmation"}})
            plan["inserts"]["vh_knowledge_chunks"].append({"id": uid(code + "/chunk"), "tenant_id": TENANT, "document_id": document_id, "ordinal": 0, "heading_path": title, "text_content": text,
                "text_hash": hashlib.sha256(text.encode()).hexdigest(), "token_count": len(text.split()) * 2, "search_tsv": "", "embedding": None})
    return plan, credentials


def service_text(category, audience, site):
    details = {
        "technical": "Nêu rõ từng thiết bị, sự cố, vị trí trong căn và ảnh đính kèm. Một tin có nhiều hạng mục phải giữ đủ từng hạng mục, không hỏi lặp thông tin đã có.",
        "security": "Nêu vị trí, thời điểm và dấu hiệu mất an toàn. Nếu có nguy hiểm tức thời, ưu tiên tránh xa khu vực nguy hiểm và liên hệ lực lượng khẩn cấp địa phương; không chờ chat thay ứng cứu.",
        "sanitation": "Nêu khu vực, loại vết bẩn/rác, ảnh và thời gian mong muốn. Phân biệt khu chung với phần riêng trong căn để xác định phạm vi.",
        "access": "Kiểm tra thẻ của đúng căn, loại thẻ, hiệu lực và trạng thái. Không đưa số thẻ hoặc quyền căn khác cho người yêu cầu; không tự cam kết phát hành/kích hoạt.",
        "visitors": "Ghi tên khách, số người, mục đích và thời gian đến/rời. Kiểm tra người bảo lãnh, phạm vi căn và giới hạn trên hồ sơ; dữ liệu tra cứu không thay phê duyệt ra vào.",
        "billing": "Tra cứu bảng kê, kỳ phí, hạn và khoản còn phải trả của đúng căn. Phân biệt bảng kê với hóa đơn thuế. Không suy diễn đã thanh toán từ lời nhắn hoặc tự sửa công nợ.",
        "amenities": "Chọn tiện ích, ngày, khung giờ, số người và xem điều kiện/giá hiển thị. Tra cứu chỗ trống không giữ chỗ; chỉ coi là đặt thành công khi có kết quả xác nhận.",
        "renovation": "Nêu phạm vi, lịch thi công, đơn vị thi công và hồ sơ liên quan. Kiểm tra giờ ồn, đặt cọc và các bước duyệt; không can thiệp kết cấu hoặc hệ thống chung khi chưa được phép.",
    }[category]
    if audience == "resident":
        flow = "Platform quản lý điều phối và tiến độ. Cư dân trả lời lịch hẹn, phương án/chi phí qua thẻ xác nhận; nhận kết quả để xác nhận hoàn thành hoặc yêu cầu xử lý lại."
    elif category in {"technical", "security", "sanitation"}:
        flow = "Nhận hoặc từ chối có lý do; nhận việc kèm ETA. Cập nhật di chuyển, đến nơi, phương án/chi phí, ảnh trước/sau và kết quả qua Domain để gửi Platform. Platform quản lý tiến độ và trả thông tin cho cư dân. Không tự bỏ qua bước đồng ý chi phí hoặc tự xác nhận thay cư dân."
    else:
        flow = "Kiểm tra hồ sơ, quyền theo căn và trạng thái yêu cầu. Nhận xử lý hoặc trả lại có lý do; cập nhật thông tin cần bổ sung, kết quả đối soát và bằng chứng nghiệp vụ qua Domain để gửi Platform quản lý và thông báo cho cư dân. Chỉ thực thi thao tác khi có endpoint, quyền và bước duyệt tương ứng; công cụ tra cứu không tự cấp thẻ, điều chỉnh công nợ, phê duyệt cải tạo hoặc xác nhận booking. Không tự thu/hoàn tiền hoặc xác nhận thay cư dân."
    return f"Phạm vi {site}. {details} {flow} Mức phí, giờ và SLA trong bộ dữ liệu dự án cần được đơn vị vận hành xác nhận trước khi áp dụng thực tế."


def validate(plan, url):
    name = urlsplit(_url(url)).path.lstrip("/")
    if not re.fullmatch(r"(?:vinhomes_release_20261015_[a-f0-9]{8}|clean_data_test_[a-f0-9]{32})", name):
        raise ValueError("Refusing an unrelated database")
    if plan.get("profile") != PROFILE or plan.get("data_mode") != "synthetic_test":
        raise ValueError("Invalid maintenance profile")
    for table, rows in plan["patches"].items():
        for row in rows:
            if table not in PATCH_COLUMNS or not set(row["after"]) <= PATCH_COLUMNS[table] or set(row["before"]) != set(row["after"]):
                raise ValueError("Unapproved patch columns")
            if row["key"] != ("zone_id" if table == "zone_settings" else "id"):
                raise ValueError("Invalid patch key")
    if set(plan["inserts"]) != set(INSERT_TABLES):
        raise ValueError("Unapproved insertion tables")
    if any(r.get("role_code") != "staff" for r in plan["inserts"]["scoped_user_roles"]):
        raise ValueError("No new privileged roles")
    if any(r.get("operational_verified") is not False for r in plan["inserts"]["owner_data_records"]):
        raise ValueError("No invented operator verification")
    if any(not r.get("unverified") for r in plan["inserts"]["vh_knowledge_documents"]):
        raise ValueError("No invented document approval")
    emails = [i["email"] for i in plan["identities"]]
    if len(set(emails)) != len(emails) or any(not e.endswith("@" + plan["email_domain"]) for e in emails):
        raise ValueError("Conflicting login identities")


async def apply(url, plan):
    validate(plan, url)
    conn = await asyncpg.connect(_url(url))
    counts = {"patched": 0, "inserted": 0, "cancelled_shifts": 0}
    try:
        async with conn.transaction():
            if await conn.fetchval("select shobj_description(oid,'pg_database') from pg_database where datname=current_database()") != "vinhomes-synthetic-sandbox-v1":
                raise ValueError("Database is not marked as a project simulation")
            await conn.execute("select pg_advisory_xact_lock(hashtextextended($1,0))", PROFILE)
            await conn.execute("select set_config('app.tenant_id',$1,true)", TENANT)
            transitions = await conn.fetch("select * from state_transitions")
            guarded = {r["name"] for r in await conn.fetch("select tgrelid::regclass::text name from pg_trigger where tgfoid='app_enforce_transition'::regproc and not tgisinternal")}
            for table, patches in plan["patches"].items():
                for p in patches:
                    current = await conn.fetchval(f'SELECT row_to_json(t)::text FROM "{table}" t WHERE "{p["key"]}"::text=$1 FOR UPDATE', p["id"])
                    if current is None:
                        raise ValueError("Missing target row: " + table)
                    current = json.loads(current)
                    if all(current[k] == v for k, v in p["after"].items()):
                        continue
                    if any(current[k] != v for k, v in p["before"].items()):
                        raise ValueError("Source changed since snapshot: " + table)
                    columns = ",".join('"' + c + '"=r."' + c + '"' for c in p["after"])
                    await conn.execute(f'UPDATE "{table}" t SET {columns} FROM json_populate_record(null::"{table}",$2::json) r WHERE t."{p["key"]}"::text=$1', p["id"], json.dumps(p["after"], ensure_ascii=False))
                    counts["patched"] += 1
            for table in INSERT_TABLES:
                for row in plan["inserts"][table]:
                    row = dict(row)
                    if row.get("tenant_id", TENANT) != TENANT:
                        raise ValueError("Cross-tenant row")
                    if row.get("id") and await conn.fetchval(f'select exists(select 1 from "{table}" where id::text=$1)', str(row["id"])):
                        continue
                    if table == "staff_specialties" and await conn.fetchval("select exists(select 1 from staff_specialties where staff_id::text=$1 and category_id::text=$2)", row["staff_id"], row["category_id"]):
                        continue
                    path = transition_path(transitions, table, row["status"]) if table in guarded else []
                    target = row.get("status")
                    if path:
                        row["status"] = path[0]
                    cols = ",".join('"' + k + '"' for k in row)
                    await conn.execute(f'INSERT INTO "{table}" ({cols}) SELECT {cols} FROM json_populate_record(null::"{table}",$1::json)', json.dumps(row, ensure_ascii=False))
                    for status in path[1:]:
                        await conn.execute(f'UPDATE "{table}" SET status=$2 WHERE id::text=$1', row["id"], status)
                    if path and path[-1] != target:
                        raise ValueError("State transition mismatch")
                    counts["inserted"] += 1
            for identifier in plan["cancel_shifts"]:
                result = await conn.execute("update staff_shifts set status='cancelled' where id::text=$1 and starts_at>$2 and status in ('available','scheduled')", identifier, datetime.fromisoformat(plan["created_at"]))
                counts["cancelled_shifts"] += int(result.split()[-1])
            for row in plan["patches"].get("vh_knowledge_chunks", []) + [{"id": r["id"], "after": r} for r in plan["inserts"]["vh_knowledge_chunks"]]:
                values = row["after"]
                indexed = passage(values["heading_path"], values["text_content"])
                await conn.execute("update vh_knowledge_chunks set search_tsv=to_tsvector('simple',$2) where id::text=$1 and search_tsv is distinct from to_tsvector('simple',$2)", row["id"], indexed + " " + fold(indexed))
        return {"profile": PROFILE, **counts}
    finally:
        await conn.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--allow-project-data-maintenance", action="store_true")
    args = parser.parse_args()
    if not args.allow_project_data_maintenance:
        parser.error("Explicit --allow-project-data-maintenance is required")
    print(json.dumps(asyncio.run(apply(os.environ["DATABASE_URL"], json.loads(args.plan.read_text(encoding="utf-8"))))))


if __name__ == "__main__":
    main()
