# G1: 55 kịch bản kiểm thử — Nền tảng điều phối — PHH-01–06

Ngày cập nhật: 10/10/2026. 50 kịch bản tự động local + 5 kịch bản nghiệm thu tích hợp.

## Phạm vi và bằng chứng

- Nguồn duy nhất của 50 ca tự động: `tests/workforce/orchestration/scenario_catalog.py`.
- Mỗi ID được pytest collect và chạy độc lập tại `test_scenario_matrix.py::test_scenario[ID]`; không đếm subtest hoặc assertion thành kịch bản mới.
- Trạng thái dưới đây được đọc từ `PYTEST_RESULTS.xml`, không được suy ra từ việc đã viết code.
- Fixture local: scope tenant/domain/area/manager; catalog Plan/Hotel/Car/Calculator/Technical v3 published, deployment active; repo trong bộ nhớ có rollback và khóa toàn cục; runtime/identity/jobs là fake.
- PASS local không chứng minh PostgreSQL, HTTP, model, browser, worker hay provider thật. 5 ca tích hợp bên dưới không được tính vào số test đã pass.
- PASS local: kết quả/mã lỗi đúng oracle và mọi assertion về state/call count/rollback của ca đều đạt. Gate tích hợp vẫn mở cho tới khi có môi trường và bằng chứng tương ứng.

## Cách chạy

Từ gốc `platform_VP/agentscope`:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/workforce/orchestration/test_scenario_matrix.py -q -k "G1"
```

Chạy toàn bộ và cập nhật danh mục bằng kết quả thực:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/workforce/orchestration -q --junitxml=docs/workforce/handoffs/phan-huy-hoang/PYTEST_RESULTS.xml
.\.venv\Scripts\python.exe tests/workforce/orchestration/render_scenario_catalog.py
```

## Bước thực hiện theo nhóm

- **conversation**: Tạo hoặc đọc hội thoại bằng ConversationService với input; kiểm tra mode/timezone hoặc lỗi; lỗi create không được ghi dữ liệu.
- **router**: Áp thay đổi candidate/deployment theo input, gọi select với needs (mặc định hotel); so sánh tập agent hoặc mã lỗi; không provisioning.
- **facts**: Gọi patch_facts revision 0 với facts/source; ca protect có budget=100 từ user; ca invalidate có proposal current; ca expired có expires_at=now=1000. Kiểm tra rollback, provenance hoặc stale/selection.
- **handoff**: Tạo run Hotel; áp sender/recipient/timeout/limit; gọi create với task và refs. Chỉ task hợp lệ được dispatch; lỗi giữ nguyên kho dữ liệu.
- **runtime**: Tạo run Hotel rồi thực hiện isolation/publish v4/timeout-retry hoặc sửa binding trả về từ hook; kiểm tra group/session/version và số lần tạo binding.

## 50 ca tự động

Input `{}` sử dụng fixture mặc định của nhóm ở trên. `!CODE` nghĩa là phải ném lỗi nghiệp vụ đúng CODE; tuyệt đối không trả thành công.

| ID | Nhóm / kịch bản | Input hoặc thay đổi fixture | Expected result | Gate / kết quả JUnit |
|---|---|---|---|---|
| G1-S001 | conversation: Tạo hội thoại nhóm với UTC | `{}` | `group` | G1-LOCAL / PASS |
| G1-S002 | conversation: Tạo chat riêng cho Hotel với múi giờ Việt Nam | `{"mode":"direct","direct_agent_id":"Hotel","timezone":"Asia/Ho_Chi_Minh"}` | `direct` | G1-LOCAL / PASS |
| G1-S003 | conversation: Chat riêng thiếu agent | `{"mode":"direct"}` | `!DIRECT_AGENT_REQUIRED` | G1-LOCAL / PASS |
| G1-S004 | conversation: Chat nhóm gán nhầm direct agent | `{"direct_agent_id":"Hotel"}` | `!DIRECT_AGENT_REQUIRED` | G1-LOCAL / PASS |
| G1-S005 | conversation: Từ chối mode không hỗ trợ | `{"mode":"broadcast"}` | `!CONVERSATION_MODE_INVALID` | G1-LOCAL / PASS |
| G1-S006 | conversation: Từ chối múi giờ không tồn tại | `{"timezone":"wrong/zone"}` | `!TIMEZONE_INVALID` | G1-LOCAL / PASS |
| G1-S007 | conversation: Không đọc hội thoại của manager khác | `{"read_foreign":true}` | `!RESOURCE_NOT_FOUND` | G1-LOCAL / PASS |
| G1-S008 | conversation: Scope bị thu hồi không tạo hội thoại | `{"revoked":true}` | `!SCOPE_REVOKED` | G1-LOCAL / PASS |
| G1-S009 | router: Yêu cầu khách sạn chỉ chọn Hotel | `{"needs":["hotel"]}` | `["Hotel"]` | G1-LOCAL / PASS |
| G1-S010 | router: Du lịch chọn bốn agent và loại Technical | `{"needs":["plan","hotel","car","calculate"]}` | `["Calculator","Car","Hotel","Plan"]` | G1-LOCAL / PASS |
| G1-S011 | router: Không tìm thấy năng lực yêu cầu | `{"needs":["flight"]}` | `!CAPABILITY_MISSING` | G1-LOCAL / PASS |
| G1-S012 | router: Danh sách nhu cầu rỗng bị chặn | `{"needs":[]}` | `!CAPABILITY_REQUIRED` | G1-LOCAL / PASS |
| G1-S013 | router: Agent draft không được chọn | `{"mutation":"draft"}` | `!CAPABILITY_MISSING` | G1-LOCAL / PASS |
| G1-S014 | router: Deployment bị thu hồi không được chọn | `{"mutation":"revoked"}` | `!CAPABILITY_MISSING` | G1-LOCAL / PASS |
| G1-S015 | router: Candidate manager khác không được chọn | `{"mutation":"foreign"}` | `!CAPABILITY_MISSING` | G1-LOCAL / PASS |
| G1-S016 | router: Manifest hash không khớp bị loại | `{"mutation":"hash"}` | `!CAPABILITY_MISSING` | G1-LOCAL / PASS |
| G1-S017 | router: Deployment trỏ phiên bản khác bị loại | `{"mutation":"version"}` | `!CAPABILITY_MISSING` | G1-LOCAL / PASS |
| G1-S018 | router: Hai agent cùng đáp ứng hotel phải làm rõ | `{"mutation":"ambiguous"}` | `!CAPABILITY_AMBIGUOUS` | G1-LOCAL / PASS |
| G1-S019 | facts: Lưu budget/reserve và provenance người dùng | `{"facts":{"budget":100,"reserve":20}}` | `{"budget":100,"reserve":20}` | G1-LOCAL / PASS |
| G1-S020 | facts: Ngân sách bằng không hợp lệ | `{"facts":{"budget":0}}` | `{"budget":0}` | G1-LOCAL / PASS |
| G1-S021 | facts: Budget âm bị chặn | `{"facts":{"budget":-1}}` | `!MONEY_INVALID` | G1-LOCAL / PASS |
| G1-S022 | facts: Budget số thực bị chặn | `{"facts":{"budget":1.5}}` | `!MONEY_INVALID` | G1-LOCAL / PASS |
| G1-S023 | facts: Boolean không được coi là tiền | `{"facts":{"budget":true}}` | `!MONEY_INVALID` | G1-LOCAL / PASS |
| G1-S024 | facts: Reserve vượt budget rollback toàn bộ | `{"facts":{"budget":10,"reserve":11}}` | `!RESERVE_EXCEEDS_BUDGET` | G1-LOCAL / PASS |
| G1-S025 | facts: Không ghi trường dữ kiện ngoài contract | `{"facts":{"password":"test-only"}}` | `!FACT_FIELD_INVALID` | G1-LOCAL / PASS |
| G1-S026 | facts: Nguồn dữ kiện không hợp lệ bị chặn | `{"facts":{},"source_kind":"model"}` | `!FACT_SOURCE_INVALID` | G1-LOCAL / PASS |
| G1-S027 | facts: Thiếu tham chiếu nguồn bị chặn | `{"facts":{},"source_ref":""}` | `!FACT_SOURCE_REQUIRED` | G1-LOCAL / PASS |
| G1-S028 | facts: Tool không ghi đè budget người dùng | `{"protect":true,"facts":{"budget":80}}` | `!USER_FACT_PROTECTED` | G1-LOCAL / PASS |
| G1-S029 | facts: Đổi budget làm stale proposal và bỏ lựa chọn | `{"invalidate":true,"facts":{"budget":200}}` | `stale-and-cleared` | G1-LOCAL / PASS |
| G1-S030 | facts: Quote hết hạn đúng thời điểm hiện tại bị chặn | `{"expired_proposal":true}` | `!QUOTE_EXPIRED` | G1-LOCAL / PASS |
| G1-S031 | handoff: Giao task hợp lệ chỉ đạt delivered | `{}` | `delivered` | G1-LOCAL / PASS |
| G1-S032 | handoff: Task trắng bị chặn trước dispatch | `{"content":"   "}` | `!TASK_CONTENT_INVALID` | G1-LOCAL / PASS |
| G1-S033 | handoff: Task vượt 32000 ký tự bị chặn | `{"content_length":32001}` | `!TASK_CONTENT_INVALID` | G1-LOCAL / PASS |
| G1-S034 | handoff: Timeout bằng không bị chặn | `{"timeout_seconds":0}` | `!TASK_TIMEOUT_INVALID` | G1-LOCAL / PASS |
| G1-S035 | handoff: Timeout âm bị chặn | `{"timeout_seconds":-1}` | `!TASK_TIMEOUT_INVALID` | G1-LOCAL / PASS |
| G1-S036 | handoff: Session ngoài nhóm không được giao việc | `{"sender":"foreign"}` | `!SENDER_NOT_MEMBER` | G1-LOCAL / PASS |
| G1-S037 | handoff: Agent tự giao việc cho mình bị chặn | `{"sender":"self"}` | `!HANDOFF_SELF_LOOP` | G1-LOCAL / PASS |
| G1-S038 | handoff: Recipient không thuộc nhóm bị chặn | `{"recipient":"Car"}` | `!MEMBER_NOT_FOUND` | G1-LOCAL / PASS |
| G1-S039 | handoff: Context ref sai kiểu bị chặn | `{"context_refs":[123]}` | `!CONTEXT_REFS_INVALID` | G1-LOCAL / PASS |
| G1-S040 | handoff: Đạt tổng số handoff thì không dispatch mới | `{"limit":"max_handoffs"}` | `!HANDOFF_LIMIT` | G1-LOCAL / PASS |
| G1-S041 | handoff: Hết slot đồng thời thì không dispatch mới | `{"limit":"max_concurrent"}` | `!CONCURRENCY_LIMIT` | G1-LOCAL / PASS |
| G1-S042 | handoff: Hết ngân sách token thì không dispatch mới | `{"limit":"token_limit"}` | `!RUN_BUDGET_EXHAUSTED` | G1-LOCAL / PASS |
| G1-S043 | runtime: Hai hội thoại dùng Hotel có group/session riêng | `{"mode":"isolation"}` | `true` | G1-LOCAL / PASS |
| G1-S044 | runtime: Publish v4 không đổi pin v3 của nhóm cũ | `{"mode":"version"}` | `["Hotel-v3","Hotel-v4"]` | G1-LOCAL / PASS |
| G1-S045 | runtime: Timeout provisioning phục hồi cùng binding | `{"mode":"retry"}` | `true` | G1-LOCAL / PASS |
| G1-S046 | runtime: Hook trả group khác bị từ chối | `{"tamper":"group_id"}` | `!RUNTIME_BINDING_INVALID` | G1-LOCAL / PASS |
| G1-S047 | runtime: Hook trả leader session khác bị từ chối | `{"tamper":"leader_session_id"}` | `!RUNTIME_BINDING_INVALID` | G1-LOCAL / PASS |
| G1-S048 | runtime: Hook trả member session khác bị từ chối | `{"tamper":"session_id"}` | `!RUNTIME_BINDING_INVALID` | G1-LOCAL / PASS |
| G1-S049 | runtime: Hook trả member hash khác bị từ chối | `{"tamper":"manifest_hash"}` | `!RUNTIME_BINDING_INVALID` | G1-LOCAL / PASS |
| G1-S050 | runtime: Scope sai không tới provisioning hook | `{"mode":"foreign"}` | `!RESOURCE_NOT_FOUND` | G1-LOCAL / PASS |

## 5 ca tích hợp cần môi trường thật

Owner triển khai/test phần PHH: Phan Huy Hoàng. Foundation cung cấp contracts/auth/migration/runtime/worker theo phân công; Execution cung cấp guard/approval/provider fixture. Các dependency chưa được coi là đã bàn giao.

| ID | Kịch bản | Input / thao tác | Expected result / điều kiện PASS | Suite hoặc runner cần có | Gate / trạng thái |
|---|---|---|---|---|---|
| G1-I001 | Leader/Planner thật | Yêu cầu tiếng Việt: đi Bãi Cháy, ngân sách 10 triệu, thiếu ngày/số người | Chọn đúng subset; hỏi phần thiếu; không gọi booking; lưu transcript | Runtime AgentScope + catalog + Execution sandbox | G1-INTEGRATION / NOT_RUN — thiếu tích hợp/môi trường |
| G1-I002 | CAS trên PostgreSQL | Hai process cập nhật budget cùng revision | Một commit, một conflict; không mất facts/provenance | PostgreSQL + hai kết nối độc lập | G1-INTEGRATION / NOT_RUN — thiếu tích hợp/môi trường |
| G1-I003 | Crash sau provisioning | Dừng worker sau tạo session, trước lưu ACK; khởi động lại | Giữ group/session/version; không tạo phiên thứ hai | Worker + PostgreSQL + concrete adapter | G1-INTEGRATION / NOT_RUN — thiếu tích hợp/môi trường |
| G1-I004 | Thu hồi quyền khi dispatch | Revoke grant sau lưu task, trước tool execution | Runtime guard chặn side effect; ghi trạng thái có thể đối soát | Identity/Execution adapter thật | G1-INTEGRATION / NOT_RUN — thiếu tích hợp/môi trường |
| G1-I005 | Giới hạn chi phí thực | Hai task đang chạy cùng gần hết ngân sách | Execution áp giới hạn/reservation đã chốt; usage được đối soát một lần | Model sandbox + token/cost metering | G1-INTEGRATION / NOT_RUN — thiếu tích hợp/môi trường |

Khi nghiệm thu tích hợp, lưu test ID, phiên bản/build, fixture, log đã loại secret, kết quả thực và người/owner xác nhận. Không đổi NOT_RUN thành PASS từ test fake tương tự.
