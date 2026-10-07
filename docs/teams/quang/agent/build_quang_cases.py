"""Turn Team Quang's labelled cases into an evaluation set for the technical agent.

    python docs/teams/quang/agent/build_quang_cases.py

Reads `technical-data/SYNTHETIC_CASES.jsonl` (16) and `EDGE_CASES.jsonl` (16) and writes
`technical-agent-quang.json`: the same agent as `technical-agent.json` (instructions, tools, tool
defaults) with these 32 cases. Run it without storing anything:

    python -m vinhomes.publish docs/teams/quang/agent/technical-agent-quang.json --check

Only what the labels state is checked by pattern, on the agent's own answer format:
- an escalation label (escalate_now…, falling glass or objects, safety_escalation…): Level 1 and the
  first line "LEVEL 1 - CHUYỂN NGƯỜI TRỰC NGAY", with the labelled issue code;
- a label that asks or requests first (ask_…, request_…, check_…): no Level 1, the issue code is the
  labelled one or CHƯA XÁC ĐỊNH, and "Thông tin cần bổ sung" is not "Không cần";
- any other label (investigate, inspect, assess, triage): the labelled issue code.
What must not be said in words (`prohibited`, `must_not`) is kept in `expected` for the reader.
Every case is synthetic (data_kind=synthetic): a test of conduct, not of real Vinhomes data.
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "technical-data"
LEVEL1 = "LEVEL 1 - CHUYỂN NGƯỜI TRỰC NGAY"
PLACES = {"common_area": "Hành lang tầng 12, tòa S1.01", "multiple_units": "Căn 1201 và căn 1202, tòa S1.01"}
ASKING = ("ask_", "request_", "check_", "clarify_", "split_", "differentiate_")  # gather facts first


def escalation(label: str) -> bool:
    return label.startswith(("escalate_now", "escalate_fall", "escalate_falling", "safety_escalation"))


def case(name: str, code: str, report: str, place: str, label: str, words: str) -> dict:
    exact = re.escape(code)
    must, must_not = [], []
    if escalation(label):
        must += [exact, r"Mức:\s*Level 1", re.escape(LEVEL1)]
    elif label.startswith(ASKING):
        must += [f"({exact}|CHƯA XÁC ĐỊNH)"]
        must_not += [re.escape(LEVEL1), r"Thông tin cần bổ sung:\s*Không cần"]
    else:
        must += [exact]
    title = re.split(r"[;,.]", report, maxsplit=1)[0].strip()
    return {"name": name, "instruction": "Phân loại sự cố, xác định mức độ và nêu việc cần làm.",
            "ticket": {"title": title, "description": report, "location": place,
                       "building_id": "77777777-7777-5777-a777-777777777777", "created_at": "2026-10-04T08:30:00+07:00"},
            "must": must, "must_not": must_not,
            "expected": f"Nhãn của Team Quang: {label} (mã {code}). {words}".strip()}


def main() -> None:
    base = json.loads((HERE / "technical-agent.json").read_text(encoding="utf-8"))
    cases = []
    for line in (DATA / "SYNTHETIC_CASES.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        expected = row["expected"]
        words = "; ".join(filter(None, ["Cần hỏi: " + " / ".join(expected.get("ask", [])) if expected.get("ask") else "",
                                        "Không được: " + " / ".join(expected.get("prohibited", [])) if expected.get("prohibited") else ""]))
        place = PLACES.get(row["facts"].get("location_kind"), "Căn 1201, tòa S1.01")
        cases.append(case("quang-" + row["case_id"].lower(), row["issue_code"], row["report"], place, expected["action"], words))
    for line in (DATA / "EDGE_CASES.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        words = f"Biến thể {row['variant']}; còn thiếu: {', '.join(row.get('missing', []))}; không được: {row.get('must_not', '')}."
        cases.append(case("quang-" + row["case_id"].lower(), row["issue_code"], row["report"], "Căn 1201, tòa S1.01",
                          row["expected_route"], words))
    definition = {**base, "name": base["name"], "cases": cases}
    out = HERE / "technical-agent-quang.json"
    out.write_text(json.dumps(definition, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(cases)} cases -> {out.name}")


if __name__ == "__main__":
    main()
