"""Render the human-readable matrix from the executable inventory and actual JUnit."""

import json
from pathlib import Path
import xml.etree.ElementTree as ET

from scenario_catalog import CASES, INTEGRATION


ROOT = Path(__file__).resolve().parents[3]
OUTPUT = ROOT / "docs/workforce/handoffs/phan-huy-hoang"
REPORT = OUTPUT / "PYTEST_RESULTS.xml"
STAGES = {
    "G1": "Nền tảng điều phối — PHH-01–06",
    "G2": "Hội thoại và đánh giá — PHH-07–12",
    "G3": "API đối tác và workflow — PHH-13–17",
}
PROCEDURES = {
    "conversation": "Tạo hoặc đọc hội thoại bằng ConversationService với input; kiểm tra mode/timezone hoặc lỗi; lỗi create không được ghi dữ liệu.",
    "router": "Áp thay đổi candidate/deployment theo input, gọi select với needs (mặc định hotel); so sánh tập agent hoặc mã lỗi; không provisioning.",
    "facts": "Gọi patch_facts revision 0 với facts/source; ca protect có budget=100 từ user; ca invalidate có proposal current; ca expired có expires_at=now=1000. Kiểm tra rollback, provenance hoặc stale/selection.",
    "handoff": "Tạo run Hotel; áp sender/recipient/timeout/limit; gọi create với task và refs. Chỉ task hợp lệ được dispatch; lỗi giữ nguyên kho dữ liệu.",
    "runtime": "Tạo run Hotel rồi thực hiện isolation/publish v4/timeout-retry hoặc sửa binding trả về từ hook; kiểm tra group/session/version và số lần tạo binding.",
    "recipient": "Tạo run Hotel; duplicate_name thêm Car và đặt cả hai tên Same. Gán pending question/message/context theo input, gọi resolve_recipient, so sánh session với Hotel/leader.",
    "entity": "Tạo candidates hotel theo ids; đặt selected/explicit_ref; gọi resolve_entity; phải trả đúng ID hoặc lỗi, không đoán entity.",
    "message": "Tạo run Hotel trừ no_run; apply cancel/content/ID/target rồi send. Delivery kiểm tra message đã persist pending trước khi gửi. Retry kiểm tra receipt và số lần gửi.",
    "context": "Facts có destination=Ha Long, preferences=[quiet], messages có private content. Chỉ lấy keys chỉ định; ca mutate thay bản sao và kiểm tra facts gốc không đổi.",
    "evaluation": "Snapshot Hotel cùng scope/hash; guard do backend fixture cấp; invoke trả transcript/traces/cost theo input. Kiểm tra thứ tự guard/runtime và không gọi runtime khi input/guard sai.",
    "member": "Tạo run Hotel rồi thêm Car batch khác; áp draft/reason hoặc thêm lại. Kiểm tra roster, session cũ, group và số provisioning operation.",
    "policy": "Gọi continuation với policy/outcome/http_pending; effect mặc định side_effect, outcome mặc định rỗng. So sánh đúng cặp workflow_state/next_action hoặc mã lỗi.",
    "http_status": "Gọi post_status với request status; so sánh 200/202. Đây là helper thuần, không phải request HTTP thật.",
    "checkpoint": "Checkpoint mặc định awaiting_user, revision=1, fence=7, group=g1/session=s1. Áp cause theo input; kiểm tra state/invoke/revision, giữ pins và không mutate bản gốc.",
    "close": "Checkpoint revision=1; gọi close với options; kiểm tra closed/none, không invoke; close lặp không tăng revision và không gọi provider.",
    "ingress": "Envelope schema 1, start_workflow, req-1/ticket/chat/user; actor mặc định authenticated-test-actor. Áp patch/remove/retry/enqueue failure; kiểm tra receipt, một job và rollback.",
    "event": "Event e1/m1, sequence=10, conversation=c1, workflow=w1, audience partner/user/ticket/chat; payload có credential giả. Áp thay đổi và kiểm tra projection/SSE/cursor.",
}


def cell(value):
    if not isinstance(value, str):
        value = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return value.replace("|", "\\|").replace("\n", "\\n").replace("\r", "\\r")


def render():
    results = list(ET.parse(REPORT).getroot().iter("testcase"))
    for stage, title in STAGES.items():
        cases = [case for case in CASES if case["stage"] == stage]
        assert len(cases) == 50
        lines = [f"# {stage}: 55 kịch bản kiểm thử — {title}", "",
                 "Ngày cập nhật: 10/10/2026. 50 kịch bản tự động local + 5 kịch bản nghiệm thu tích hợp.", "",
                 "## Phạm vi và bằng chứng", "",
                 "- Nguồn duy nhất của 50 ca tự động: `tests/workforce/orchestration/scenario_catalog.py`.",
                 "- Mỗi ID được pytest collect và chạy độc lập tại `test_scenario_matrix.py::test_scenario[ID]`; không đếm subtest hoặc assertion thành kịch bản mới.",
                 "- Trạng thái dưới đây được đọc từ `PYTEST_RESULTS.xml`, không được suy ra từ việc đã viết code.",
                 "- Fixture local: scope tenant/domain/area/manager; catalog Plan/Hotel/Car/Calculator/Technical v3 published, deployment active; repo trong bộ nhớ có rollback và khóa toàn cục; runtime/identity/jobs là fake.",
                 "- PASS local không chứng minh PostgreSQL, HTTP, model, browser, worker hay provider thật. 5 ca tích hợp bên dưới không được tính vào số test đã pass.",
                 "- PASS local: kết quả/mã lỗi đúng oracle và mọi assertion về state/call count/rollback của ca đều đạt. Gate tích hợp vẫn mở cho tới khi có môi trường và bằng chứng tương ứng.", "",
                 "## Cách chạy", "", "Từ gốc `platform_VP/agentscope`:", "", "```powershell",
                 f'.\\.venv\\Scripts\\python.exe -m pytest tests/workforce/orchestration/test_scenario_matrix.py -q -k "{stage}"',
                 "```", "", "Chạy toàn bộ và cập nhật danh mục bằng kết quả thực:", "", "```powershell",
                 ".\\.venv\\Scripts\\python.exe -m pytest tests/workforce/orchestration -q --junitxml=docs/workforce/handoffs/phan-huy-hoang/PYTEST_RESULTS.xml",
                 ".\\.venv\\Scripts\\python.exe tests/workforce/orchestration/render_scenario_catalog.py", "```", "",
                 "## Bước thực hiện theo nhóm", ""]
        for action in dict.fromkeys(c["action"] for c in cases):
            lines.append(f"- **{action}**: {PROCEDURES[action]}")
        lines += ["", "## 50 ca tự động", "",
                  "Input `{}` sử dụng fixture mặc định của nhóm ở trên. `!CODE` nghĩa là phải ném lỗi nghiệp vụ đúng CODE; tuyệt đối không trả thành công.", "",
                  "| ID | Nhóm / kịch bản | Input hoặc thay đổi fixture | Expected result | Gate / kết quả JUnit |",
                  "|---|---|---|---|---|"]
        for case in cases:
            matches = [r for r in results if r.get("name", "") == f'test_scenario[{case["id"]}]']
            assert len(matches) == 1, f"Missing or duplicate JUnit evidence: {case['id']}"
            result = matches[0]
            state = "FAIL" if result.find("failure") is not None or result.find("error") is not None else "SKIPPED" if result.find("skipped") is not None else "PASS"
            lines.append(f'| {case["id"]} | {case["action"]}: {cell(case["title"])} | `{cell(case["input"])}` | `{cell(case["expected"])}` | {stage}-LOCAL / {state} |')
        lines += ["", "## 5 ca tích hợp cần môi trường thật", "",
                  "Owner triển khai/test phần PHH: Phan Huy Hoàng. Foundation cung cấp contracts/auth/migration/runtime/worker theo phân công; Execution cung cấp guard/approval/provider fixture. Các dependency chưa được coi là đã bàn giao.", "",
                  "| ID | Kịch bản | Input / thao tác | Expected result / điều kiện PASS | Suite hoặc runner cần có | Gate / trạng thái |",
                  "|---|---|---|---|---|---|"]
        for i, (name, inputs, expected, runner) in enumerate(INTEGRATION[stage], 1):
            lines.append(f"| {stage}-I{i:03d} | {cell(name)} | {cell(inputs)} | {cell(expected)} | {cell(runner)} | {stage}-INTEGRATION / NOT_RUN — thiếu tích hợp/môi trường |")
        lines += ["", "Khi nghiệm thu tích hợp, lưu test ID, phiên bản/build, fixture, log đã loại secret, kết quả thực và người/owner xác nhận. Không đổi NOT_RUN thành PASS từ test fake tương tự.", ""]
        (OUTPUT / f"KICH_BAN_TEST_{stage}.md").write_text("\n".join(lines), encoding="utf-8")
        print(f"{stage}: {len(cases)} executable + {len(INTEGRATION[stage])} integration scenarios")


if __name__ == "__main__":
    render()
