# Kết quả kiểm tra local PHH — 10/10/2026

Nhánh bàn giao: dev2PHH. Bộ test chạy trên thay đổi local từ feat/wf-orchestration, baseline develop2@6bc7d60; mã sản phẩm không đổi khi tách nhánh bàn giao. Công bố nhánh theo yêu cầu người dùng không phải bằng chứng CI/merge/deploy.

## Python

Lệnh thực tế từ gốc agentscope:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/workforce/orchestration -q --junitxml=docs/workforce/handoffs/phan-huy-hoang/PYTEST_RESULTS.xml
```

Kết quả cuối sau bổ sung 150 kịch bản: **227 passed, 14 subtests passed in 3.49s**, exit code 0. Runner pytest 9.1.1, Python 3.12 môi trường local riêng. Artifact thực tế: `PYTEST_RESULTS.xml`. React/TypeScript ở lượt trước đạt 7 behavioral tests PASS và strict PASS; không đổi UI trong lượt này.

## Danh mục theo giai đoạn

| Giai đoạn | Ca tự động mới | Ca tích hợp đã mô tả, chưa chạy | Danh mục |
|---|---:|---:|---|
| G1 | 50 PASS local | 5 NOT_RUN | [55 kịch bản G1](KICH_BAN_TEST_G1.md) |
| G2 | 50 PASS local | 5 NOT_RUN | [55 kịch bản G2](KICH_BAN_TEST_G2.md) |
| G3 | 50 PASS local | 5 NOT_RUN | [55 kịch bản G3](KICH_BAN_TEST_G3.md) |

Mỗi ca Gx-S001–S050 được pytest collect riêng, có input và expected cố định trong `scenario_catalog.py`; `test_scenario_matrix.py` thực thi assertion kết quả/mã lỗi, state, rollback hoặc call count phù hợp. Có thêm một test bảo đảm ID duy nhất và đúng 50 ca mỗi giai đoạn. Tổng 227 = 76 test cũ + 150 ca mới + 1 test kiểm tra danh mục; 14 subtests được báo riêng, không dùng để đạt chỉ tiêu 50 ca/giai đoạn.

`render_scenario_catalog.py` lấy trạng thái từng ID từ JUnit để xuất ba danh mục. Các ca Gx-I001–I005 chỉ là kịch bản nghiệm thu tích hợp, có input/expected/dependency/runner; không tạo skip giả hoặc đưa vào số pass. Các fixture service trong 150 ca mới đều local/fake, chưa chứng minh HTTP/model/PostgreSQL/worker production.

| Suite | Nội dung / phạm vi chứng minh |
|---|---|
| test_stage1.py | Capability/scope/pins/state/CAS/handoff/recovery; fake identity/catalog/repository/runtime |
| test_sql_repository.py | SQLite persistence/reopen/rollback/owner filter/immutable fields; metadata compile PostgreSQL |
| test_stage2.py | Mention/question/entity/direct/context/member/eval/message retry; fake dependencies |
| test_stage3.py | Pure policy/checkpoint/binding/projection/cursor/close invariants |
| test_ingress.py | Ticketed ingress/idempotency/UOW rollback/A-B group binding/remap; fake guard/jobs/repository |
| test_adversarial_review.py | 9 ca bổ sung về cancelled run, pending message binding/session và scope evaluation; fake dependencies |
| test_member_recovery.py | 12 ca về task completion khi add, recovery xen kẽ/đồng thời, pending member task/message, operation ID ổn định, cancel, ambiguity đầy đủ/chồng lấn một phần, chống thay session/pending intent |
| test_scenario_matrix.py | 150 ca G1/G2/G3 collect độc lập và 1 ca kiểm tra danh mục; fake service/runtime/identity/catalog/jobs |

Lượt kiểm tra lại phát hiện và sửa thêm tie giữa các agent có coverage chồng lấn một phần: ca đổi ID FAIL trước sửa, PASS sau khi kiểm tra overlap trên toàn bộ top rank. Hai ca mới còn lại xác nhận recovery đồng thời và message routing trong lúc add. Tổng lượt này thêm 3 tests và 2 subtests; toàn bộ suite được chạy lại sau sửa. Các ca concurrency này dùng fake repository/runtime, không chứng minh cạnh tranh xuyên process trên PostgreSQL.

Lượt sửa mới bổ sung tổng cộng 10 tests, gồm 9 ca membership/router và 1 SQLite recovery qua engine reopen. Trước sửa, các ca mới tái hiện lỗi completion/ACK trong lúc thêm thành viên, lỗi giả khi recovery thắng race và chọn agent theo ID. Sau sửa toàn bộ suite PASS. SQLite reopen xác minh pending membership, operation ID và session được lưu/khôi phục; vẫn không phải bằng chứng PostgreSQL hay adapter production.

## Lỗi phát hiện trong lượt kiểm thử bổ sung

Baseline 54 tests vẫn PASS, nhưng **4 ca mới FAIL trước sửa**. Đã sửa 3 nhóm lỗi rồi chạy lại toàn bộ:

1. Pending message retry đã bypass kiểm tra run status: có thể gửi tiếp khi run cancelled. Giờ persist run/group binding và kiểm tra status, current active run và recipient session trước retry; không reroute sang group mới.
2. Worker vẫn complete/ACK task pending sau khi run cancelled. Giờ chặn chuyển trạng thái hoạt động, vẫn cho cleanup cancelled/timed_out và đọc lại receipt terminal đã có.
3. Evaluation snapshot thiếu scope hoặc scope của manager khác vẫn tới guard/runtime. Giờ normalize DTO và kiểm tra scope bắt buộc, cùng owner trước khi gọi dependency.

Thêm các ca bảo vệ idempotency: receipt đã delivered/completed được đọc lại sau cancel mà không gửi lại/count usage lần hai; pending message không tới session đã gỡ hoặc active run khác. Tổng ca bổ sung: 9, đều PASS sau sửa.

Race cancel sau bước DB check và trước callback network còn phải được concrete runtime/delivery guard kiểm tra lại bằng current state/fence. Chưa có concrete adapter để xác minh race xuyên process; không coi tests trên fake là chứng minh đã loại bỏ mọi race production.

Các lỗi được tìm và sửa trong lượt này: delivery ACK đến sau worker completion không làm lùi trạng thái; expired task giải phóng concurrency slot; shared DTO scope mapping được normalize; direct chat không được khởi tạo run có member khác; SQL save chặn đổi immutable identity/binding. Test IDs trong source liên kết G1/G2/G3 plan.

## React / TypeScript

```powershell
node tests/workforce/orchestration/check_ui.cjs "$env:TEMP\phh-ui-check-20261010"
```

Kết quả: TypeScript strict PASS cho WorkforceChat/TicketTimeline; **7 React behavior tests PASS**, exit code 0.

- G2-T09: dedupe message, pending question và injected approval slot.
- G2-T09: loading chặn send.
- G2-T01: mention truyền agent ID, retry giữ client message ID.
- G2-T09: add/direct/quote/cancel/resume gọi đúng callback.
- G2-T09: expired quote không chọn được.
- G3-T11: timeline dedupe và close đúng workflow/revision.
- G3-T13: ticket closed không close lại; close lỗi hiển thị error.

TypeScript 6.0.2, React 19.2.6, @types/react 19.2.14, Testing Library và jsdom cài trong host TEMP; không sửa package.json/lock chung. Tests chạy trong DOM giả lập, chưa xác minh toàn app, browser/proxy thật hoặc backend calls.

## Chưa chạy / không được suy ra PASS

- PostgreSQL thật: NOT_RUN — Docker daemon không chạy; SQLite + DDL compile không chứng minh lock/race/JSONB runtime.
- Production AgentScope adapter, catalog, Execution, workflow worker: NOT_RUN — các Workforce provider modules/common contracts còn scaffold.
- Alembic migration, root wiring và toàn app build/lint: NOT_RUN — thuộc owner khác, chưa nối.
- Durable SSE/replay/history/snapshot/timers/retention/proxy/slow consumers: chưa triển khai đầy đủ, không đánh dấu PASS.
- Full request-to-Leader-to-Execution-to-result flow: chưa tích hợp.
- CI, sandbox/provider/model/booking thật, production: NOT_RUN, không được gọi trong test này.

Xem STATUS.md và INTEGRATION_REQUEST_PHH_FOUNDATION.md để tiếp tục. Báo cáo này tổng hợp output đã quan sát; không phải log CI hoặc xác nhận nghiệm thu 3 giai đoạn.
