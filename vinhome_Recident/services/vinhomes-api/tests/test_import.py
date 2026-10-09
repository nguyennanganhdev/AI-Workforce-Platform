"""Data the domain owner supplies goes in by code, all or nothing, and twice is the same as once (docs/domain/NAP_DU_LIEU.md)."""

import asyncio
import csv
import json
from pathlib import Path

import pytest
from test_integration_auth import person
from test_resident_contract import TENANT, sql
from test_resident_contract import database as database  # noqa: F401 -- pytest fixture export

from vinhomes_api.import_data import load

FILES = {
    "buildings": [["code", "name", "zone_code"], ["IMP1", "Tòa nhập IMP1", "sapphire"]],
    "units": [["code", "building_code", "unit_kind", "floor"], ["IMP1-0101", "IMP1", "apartment", "1"], ["IMP1-0102", "IMP1", "apartment", "1"]],
    "residents": [["name", "phone", "unit_code", "relation", "status", "user_id"],
                  ["Lê Thị Nhập", "0911000001", "IMP1-0101", "owner", "verified", "imp-owner"],
                  ["Trần Văn Nhập", "0911000002", "IMP1-0101", "household", "verified", "imp-member"],
                  ["Phạm Chờ Duyệt", "0911000003", "IMP1-0102", "tenant", "pending", "imp-pending"]],
    "staff": [["employee_code", "name", "phone", "role", "specialties"], ["IMP-T1", "Kỹ thuật nhập", "0911000010", "staff", "technical"]],
    "shifts": [["employee_code", "starts_at", "ends_at"], ["IMP-T1", "2026-10-10T08:00:00+07:00", "2026-10-10T17:00:00+07:00"]],
    "vehicles": [["unit_code", "kind", "plate_no", "owner_name"], ["IMP1-0101", "motorbike", "29Z9-999.99", "Lê Thị Nhập"]],
    "cards": [["card_no", "kind", "unit_code", "plate_no", "status"], ["IMP-C1", "vehicle", "IMP1-0101", "29Z9-999.99", "active"], ["IMP-C2", "resident", "IMP1-0101", "", "lost"]],
    "debit_notes": [["doc_no", "unit_code", "period_month", "issue_date", "due_date", "subtotal", "vat_amount", "status", "paid_amount"],
                    ["IMP-DN-1", "IMP1-0101", "2026-09-01", "2026-09-05", "2026-09-25", "1000000", "100000", "overdue", "0"],
                    ["IMP-DN-2", "IMP1-0101", "2026-08-01", "2026-08-05", "2026-08-25", "900000", "90000", "paid", "0"]],
    "debit_note_lines": [["doc_no", "line_no", "fee_kind", "description", "amount"], ["IMP-DN-1", "1", "management", "Phí quản lý", "1000000"], ["IMP-DN-2", "1", "management", "Phí quản lý", "900000"]],
    "amenities": [["code", "name", "category_code", "zone_code", "areas", "price", "slot_minutes", "open_time", "close_time"], ["IMP-GYM", "Gym nhập", "gym", "sapphire", "main", "0", "60", "05:00", "22:00"]],
    "handbook": [["title", "body_md", "audience", "zone_code"], ["Nội quy nhập", "Giữ yên tĩnh sau 22:00.", "resident", "sapphire"]],
    "policies": [["code", "title", "kind", "version", "body_md", "audience", "effective_from"], ["imp-fees", "Biểu phí nhập", "fee_table", "1", "Phí 1.000đ", "resident|staff", "2026-01-01"]],
    "announcements": [["code", "kind", "title", "body_md", "status", "building_codes"], ["IMP-AN-1", "news", "Tin nhập", "Nội dung", "published", "IMP1"]],
}


def write(folder: Path, files=FILES):
    folder.mkdir(parents=True, exist_ok=True)
    for name, rows in files.items():
        with (folder / f"{name}.csv").open("w", encoding="utf-8", newline="") as handle:
            csv.writer(handle).writerows(rows)


def tables(database):
    names = ("buildings", "units", "unit_residents", "users", "staff_profiles", "vehicles", "access_cards", "debit_notes", "debit_note_lines",
             "amenities", "handbook_articles", "policy_documents", "announcements")
    return {n: sql(database, f"select count(*) as n from {n}")[0]["n"] for n in names}


def test_a_load_adds_what_was_supplied_and_a_second_load_adds_nothing(database, tmp_path):
    write(tmp_path)
    before = tables(database)
    added, problems = asyncio.run(load(database["admin"], str(tmp_path), False))
    assert problems == [] and added["units"] == 2 and added["residents"] == 3
    after = tables(database)
    assert after["buildings"] == before["buildings"] + 1 and after["units"] == before["units"] + 2 and after["debit_note_lines"] == before["debit_note_lines"] + 2
    asyncio.run(load(database["admin"], str(tmp_path), False))
    assert tables(database) == after                                                                           # idempotent

    states = {r["doc_no"]: (r["status"], r["paid_amount"], r["total_amount"]) for r in sql(database, "select doc_no,status,paid_amount,total_amount from debit_notes where doc_no like 'IMP-DN-%'")}
    assert states == {"IMP-DN-1": ("overdue", 0, 1100000), "IMP-DN-2": ("paid", 990000, 990000)}               # moved along by the rules, not written raw
    assert {r["card_no"]: r["status"] for r in sql(database, "select card_no,status from access_cards where card_no like 'IMP-C%'")} == {"IMP-C1": "active", "IMP-C2": "lost"}
    assert sql(database, "select count(*) as n from scoped_user_roles r join staff_profiles s on s.user_id=(select user_id from staff_profiles where employee_code='IMP-T1') where r.role_code='staff'")[0]["n"] > 0

    # what was loaded works through the API like anything else
    home = sql(database, "select id from units where code='IMP1-0101'")[0]["id"]
    with person(database, "imp-owner") as c:
        assert c.get(f"/resident/units/{home}/balance").json()["outstanding"] == 1100000
        assert c.get("/resident/announcements").json()["items"][0]["title"] == "Tin nhập"
    with person(database, "imp-member") as c:
        assert c.get(f"/resident/units/{home}/balance").status_code == 403
    with person(database, "imp-pending") as c:
        assert c.get(f"/resident/units/{sql(database, 'select id from units where code=$1', 'IMP1-0102')[0]['id']}/cards").status_code == 403


def test_a_bad_row_is_reported_with_its_line_and_nothing_is_written(database, tmp_path):
    bad = {**FILES, "buildings": [["code", "name", "zone_code"], ["IMP2", "Tòa lỗi", "sapphire"]],
           "units": [["code", "building_code", "unit_kind"], ["IMP2-0101", "IMP2", "apartment"], ["IMP2-0102", "NOPE", "apartment"], ["IMP2-0103", "IMP2", "castle"]],
           "residents": [["name", "unit_code", "relation"], ["Ai Đó", "IMP2-9999", "owner"]]}
    write(tmp_path, {k: bad[k] for k in ("buildings", "units", "residents")})
    before = tables(database)
    added, problems = asyncio.run(load(database["admin"], str(tmp_path), False))
    assert len(problems) == 3
    assert "units.csv line 3" in problems[0] and "NOPE" in problems[0]
    assert "units.csv line 4" in problems[1] and "castle" in problems[1]
    assert "residents.csv line 2" in problems[2] and "IMP2-9999" in problems[2]
    assert tables(database) == before                                                                          # all or nothing


def test_a_dry_run_writes_nothing_and_json_files_are_read_too(database, tmp_path):
    tmp_path.joinpath("handbook.json").write_text(json.dumps([{"title": "Chỉ thử", "body_md": "Không ghi", "audience": "resident"}]), encoding="utf-8")
    before = tables(database)
    added, problems = asyncio.run(load(database["admin"], str(tmp_path), True))
    assert problems == [] and added == {"handbook": 1}
    assert tables(database) == before


def test_audiences_and_unknown_values_are_refused(database, tmp_path):
    write(tmp_path, {"policies": [["code", "title", "kind", "version", "effective_from", "audience"], ["x", "X", "fee_table", "1", "2026-01-01", "everyone"], ["y", "Y", "nonsense", "1", "2026-01-01", "resident"]]})
    _, problems = asyncio.run(load(database["admin"], str(tmp_path), False))
    assert len(problems) == 2 and "audience" in problems[0] and "nonsense" in problems[1]


ZONE_HEADER = ["zone_code", "visit_max_waiting", "visit_max_hours", "visit_auto_approve_purposes", "visit_auto_approve_max_guests", "card_limit_vehicle", "note"]


def zone_rows(database):
    return sql(database, """select z.code,s.visit_max_waiting,s.visit_max_hours,s.visit_auto_approve_purposes,s.card_limit_vehicle,s.card_limit_resident
                            from zone_settings s left join zones z on z.id=s.zone_id and z.tenant_id=s.tenant_id
                            where s.note like 'imp:%' order by z.code nulls first""")


def test_zone_rules_are_loaded_replace_the_zone_row_and_an_empty_cell_inherits(database, tmp_path):
    rows = [ZONE_HEADER, ["", "12", "", "family_visit|delivery|business", "", "5", "imp: toàn khu"],
            ["hai-au", "30", "120", "", "9", "", "imp: villa"]]
    write(tmp_path, {"zone_settings": rows})
    added, problems = asyncio.run(load(database["admin"], str(tmp_path), False))
    assert problems == [] and added["zone_settings"] == 2
    assert zone_rows(database) == [
        {"code": None, "visit_max_waiting": 12, "visit_max_hours": None, "visit_auto_approve_purposes": ["family_visit", "delivery", "business"], "card_limit_vehicle": 5, "card_limit_resident": None},
        {"code": "hai-au", "visit_max_waiting": 30, "visit_max_hours": 120, "visit_auto_approve_purposes": None, "card_limit_vehicle": None, "card_limit_resident": None}]
    again, _ = asyncio.run(load(database["admin"], str(tmp_path), False))
    assert again.get("zone_settings", 0) == 0                                                                  # the same file changes nothing

    rows[2] = ["hai-au", "40", "", "", "", "", "imp: villa"]                                                    # a new file replaces the zone's row: an empty cell inherits again
    write(tmp_path, {"zone_settings": rows})
    changed, problems = asyncio.run(load(database["admin"], str(tmp_path), False))
    assert problems == [] and changed["zone_settings"] == 1
    villa = next(r for r in zone_rows(database) if r["code"] == "hai-au")
    assert (villa["visit_max_waiting"], villa["visit_max_hours"]) == (40, None)


def test_a_zone_rule_that_makes_no_sense_or_names_no_zone_is_refused(database, tmp_path):
    write(tmp_path, {"zone_settings": [ZONE_HEADER, ["hai-au", "0", "", "", "", "", "imp: bad"], ["khong-co", "5", "", "", "", "", "imp: bad"],
                                       ["sapphire", "5", "", "nonsense", "", "", "imp: bad"], ["sapphire", "abc", "", "", "", "", "imp: bad"]]})
    added, problems = asyncio.run(load(database["admin"], str(tmp_path), False))
    assert added == {} and len(problems) == 4 and all(p.startswith("zone_settings.csv line") for p in problems), problems
    assert not sql(database, "select 1 from zone_settings where note='imp: bad'")
