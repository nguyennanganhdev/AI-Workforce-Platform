# G2: 55 kịch bản kiểm thử — Hội thoại và đánh giá — PHH-07–12

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
.\.venv\Scripts\python.exe -m pytest tests/workforce/orchestration/test_scenario_matrix.py -q -k "G2"
```

Chạy toàn bộ và cập nhật danh mục bằng kết quả thực:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/workforce/orchestration -q --junitxml=docs/workforce/handoffs/phan-huy-hoang/PYTEST_RESULTS.xml
.\.venv\Scripts\python.exe tests/workforce/orchestration/render_scenario_catalog.py
```

## Bước thực hiện theo nhóm

- **recipient**: Tạo run Hotel; duplicate_name thêm Car và đặt cả hai tên Same. Gán pending question/message/context theo input, gọi resolve_recipient, so sánh session với Hotel/leader.
- **entity**: Tạo candidates hotel theo ids; đặt selected/explicit_ref; gọi resolve_entity; phải trả đúng ID hoặc lỗi, không đoán entity.
- **message**: Tạo run Hotel trừ no_run; apply cancel/content/ID/target rồi send. Delivery kiểm tra message đã persist pending trước khi gửi. Retry kiểm tra receipt và số lần gửi.
- **context**: Facts có destination=Ha Long, preferences=[quiet], messages có private content. Chỉ lấy keys chỉ định; ca mutate thay bản sao và kiểm tra facts gốc không đổi.
- **evaluation**: Snapshot Hotel cùng scope/hash; guard do backend fixture cấp; invoke trả transcript/traces/cost theo input. Kiểm tra thứ tự guard/runtime và không gọi runtime khi input/guard sai.
- **member**: Tạo run Hotel rồi thêm Car batch khác; áp draft/reason hoặc thêm lại. Kiểm tra roster, session cũ, group và số provisioning operation.

## 50 ca tự động

Input `{}` sử dụng fixture mặc định của nhóm ở trên. `!CODE` nghĩa là phải ném lỗi nghiệp vụ đúng CODE; tuyệt đối không trả thành công.

| ID | Nhóm / kịch bản | Input hoặc thay đổi fixture | Expected result | Gate / kết quả JUnit |
|---|---|---|---|---|
| G2-S001 | recipient: Target ID Hotel giữ nguyên session | `{"target_agent_id":"Hotel"}` | `Hotel` | G2-LOCAL / PASS |
| G2-S002 | recipient: Mention tên Hotel đúng duy nhất | `{"mention_name":"Hotel"}` | `Hotel` | G2-LOCAL / PASS |
| G2-S003 | recipient: Target ID ngoài nhóm bị chặn | `{"target_agent_id":"Car"}` | `!MEMBER_NOT_FOUND` | G2-LOCAL / PASS |
| G2-S004 | recipient: Tên mention không tồn tại bị chặn | `{"mention_name":"Unknown"}` | `!MEMBER_NOT_FOUND` | G2-LOCAL / PASS |
| G2-S005 | recipient: Hai thành viên trùng tên phải làm rõ | `{"duplicate_name":true,"mention_name":"Same"}` | `!MENTION_AMBIGUOUS` | G2-LOCAL / PASS |
| G2-S006 | recipient: Không target và không câu hỏi thì về leader | `{}` | `leader` | G2-LOCAL / PASS |
| G2-S007 | recipient: Một câu hỏi pending về đúng Hotel | `{"questions":"one"}` | `Hotel` | G2-LOCAL / PASS |
| G2-S008 | recipient: Hai câu hỏi pending phải làm rõ | `{"questions":"two"}` | `!PENDING_QUESTION_AMBIGUOUS` | G2-LOCAL / PASS |
| G2-S009 | recipient: Câu hỏi trỏ session ngoài nhóm bị chặn | `{"questions":"foreign"}` | `!QUESTION_TARGET_INVALID` | G2-LOCAL / PASS |
| G2-S010 | recipient: Reply message không tồn tại bị chặn | `{"reply_to_message_id":"missing"}` | `!MESSAGE_REFERENCE_INVALID` | G2-LOCAL / PASS |
| G2-S011 | recipient: Reply message của Hotel về đúng Hotel | `{"reply_to_message_id":"m1","message_agent":"Hotel"}` | `Hotel` | G2-LOCAL / PASS |
| G2-S012 | recipient: Run và conversation không cùng scope bị chặn | `{"foreign_context":true}` | `!CONTEXT_BINDING_INVALID` | G2-LOCAL / PASS |
| G2-S013 | entity: Một hotel candidate được resolve duy nhất | `{"ids":["H1"]}` | `H1` | G2-LOCAL / PASS |
| G2-S014 | entity: Không có candidate thì không bịa entity | `{"ids":[]}` | `!ENTITY_NOT_FOUND` | G2-LOCAL / PASS |
| G2-S015 | entity: Hai candidate không reference phải làm rõ | `{"ids":["H1","H2"]}` | `!ENTITY_AMBIGUOUS` | G2-LOCAL / PASS |
| G2-S016 | entity: Explicit ref chọn H2 trong hai candidate | `{"ids":["H1","H2"],"explicit_ref":"H2"}` | `H2` | G2-LOCAL / PASS |
| G2-S017 | entity: Selected ref hiện tại chọn H1 | `{"ids":["H1","H2"],"selected":"H1"}` | `H1` | G2-LOCAL / PASS |
| G2-S018 | entity: Explicit ref ưu tiên hơn selected ref | `{"ids":["H1","H2"],"selected":"H1","explicit_ref":"H2"}` | `H2` | G2-LOCAL / PASS |
| G2-S019 | entity: Reference không tồn tại không fallback | `{"ids":["H1"],"explicit_ref":"H9"}` | `!ENTITY_NOT_FOUND` | G2-LOCAL / PASS |
| G2-S020 | entity: Candidate trùng ID không được chọn tùy ý | `{"ids":["H1","H1"],"explicit_ref":"H1"}` | `!ENTITY_AMBIGUOUS` | G2-LOCAL / PASS |
| G2-S021 | message: Tin hợp lệ lưu trước và gửi một lần | `{}` | `delivered` | G2-LOCAL / PASS |
| G2-S022 | message: Tin rỗng không gọi delivery | `{"content":""}` | `!MESSAGE_INVALID` | G2-LOCAL / PASS |
| G2-S023 | message: Tin chỉ khoảng trắng bị chặn | `{"content":" \n "}` | `!MESSAGE_INVALID` | G2-LOCAL / PASS |
| G2-S024 | message: Tin dài đúng 32000 ký tự được gửi | `{"content_length":32000}` | `delivered` | G2-LOCAL / PASS |
| G2-S025 | message: Tin dài 32001 ký tự bị chặn | `{"content_length":32001}` | `!MESSAGE_INVALID` | G2-LOCAL / PASS |
| G2-S026 | message: Client message ID rỗng bị chặn | `{"client_message_id":""}` | `!MESSAGE_ID_INVALID` | G2-LOCAL / PASS |
| G2-S027 | message: Client message ID 129 ký tự bị chặn | `{"id_length":129}` | `!MESSAGE_ID_INVALID` | G2-LOCAL / PASS |
| G2-S028 | message: Retry cùng ID/nội dung không gửi lại | `{"retry":"same"}` | `one-delivery` | G2-LOCAL / PASS |
| G2-S029 | message: Cùng ID khác nội dung trả conflict | `{"retry":"changed"}` | `!MESSAGE_ID_CONFLICT` | G2-LOCAL / PASS |
| G2-S030 | message: Run đã hủy không nhận tin mới | `{"cancelled":true}` | `!RUN_UNAVAILABLE` | G2-LOCAL / PASS |
| G2-S031 | message: Tin trực tiếp đến agent ngoài nhóm bị chặn | `{"target_agent_id":"Car"}` | `!MEMBER_NOT_FOUND` | G2-LOCAL / PASS |
| G2-S032 | message: Hội thoại chưa có run không nhận tin | `{"no_run":true}` | `!RUN_REQUIRED` | G2-LOCAL / PASS |
| G2-S033 | context: Chỉ chuyển destination được chọn | `{"keys":["destination"]}` | `{"destination":"Ha Long"}` | G2-LOCAL / PASS |
| G2-S034 | context: Không chọn field thì context rỗng | `{"keys":[]}` | `{}` | G2-LOCAL / PASS |
| G2-S035 | context: Không cho chuyển private history | `{"keys":["messages"]}` | `!CONTEXT_FIELD_INVALID` | G2-LOCAL / PASS |
| G2-S036 | context: Context tách rời dữ kiện gốc | `{"keys":["preferences"],"mutate":true}` | `["quiet"]` | G2-LOCAL / PASS |
| G2-S037 | evaluation: Mock eval trả kết quả completed | `{}` | `completed` | G2-LOCAL / PASS |
| G2-S038 | evaluation: Sandbox eval đi qua backend guard | `{"mode":"sandbox"}` | `completed` | G2-LOCAL / PASS |
| G2-S039 | evaluation: Không cho client dùng production eval mode | `{"mode":"production"}` | `!EVALUATION_MODE_INVALID` | G2-LOCAL / PASS |
| G2-S040 | evaluation: Snapshot thiếu manifest bị chặn | `{"snapshot":"missing_manifest"}` | `!SNAPSHOT_INVALID` | G2-LOCAL / PASS |
| G2-S041 | evaluation: Snapshot manager khác không tới runtime | `{"snapshot":"foreign"}` | `!SNAPSHOT_SCOPE_INVALID` | G2-LOCAL / PASS |
| G2-S042 | evaluation: Guard không tồn tại không gọi runtime | `{"guard_none":true}` | `!EVALUATION_GUARD_REQUIRED` | G2-LOCAL / PASS |
| G2-S043 | evaluation: Runtime thiếu tool traces bị chặn | `{"result":"missing_traces"}` | `!EVALUATION_RESULT_INVALID` | G2-LOCAL / PASS |
| G2-S044 | evaluation: Runtime trả cost âm bị chặn | `{"result":"negative_cost"}` | `!EVALUATION_RESULT_INVALID` | G2-LOCAL / PASS |
| G2-S045 | evaluation: Runtime thất bại phải giữ failed | `{"result":"failed"}` | `failed` | G2-LOCAL / PASS |
| G2-S046 | evaluation: Runtime bị hủy phải giữ cancelled | `{"result":"cancelled"}` | `cancelled` | G2-LOCAL / PASS |
| G2-S047 | member: Thêm agent khác batch vào group hiện tại | `{"mode":"cross_batch"}` | `["Car","Hotel"]` | G2-LOCAL / PASS |
| G2-S048 | member: Thêm lại member không đổi session | `{"mode":"duplicate"}` | `true` | G2-LOCAL / PASS |
| G2-S049 | member: Thêm member thiếu lý do bị chặn | `{"reason":" "}` | `!SELECTION_REASON_REQUIRED` | G2-LOCAL / PASS |
| G2-S050 | member: Member chưa published không được thêm | `{"mode":"draft"}` | `!AGENT_NOT_PUBLISHED` | G2-LOCAL / PASS |

## 5 ca tích hợp cần môi trường thật

Owner triển khai/test phần PHH: Phan Huy Hoàng. Foundation cung cấp contracts/auth/migration/runtime/worker theo phân công; Execution cung cấp guard/approval/provider fixture. Các dependency chưa được coi là đã bàn giao.

| ID | Kịch bản | Input / thao tác | Expected result / điều kiện PASS | Suite hoặc runner cần có | Gate / trạng thái |
|---|---|---|---|---|---|
| G2-I001 | UI đổi hội thoại | Draft/retry ở A; chuyển B rồi gửi | Không gửi draft/target/client ID của A vào B | Browser + shell + API thật | G2-INTEGRATION / NOT_RUN — thiếu tích hợp/môi trường |
| G2-I002 | Hành trình approval | Chọn quote; cần approval; approve rồi retry do mất mạng | Đúng approval/ticket; side effect chỉ một lần | Browser + Execution ApprovalCard + sandbox | G2-INTEGRATION / NOT_RUN — thiếu tích hợp/môi trường |
| G2-I003 | Eval bằng runtime thật | Chạy bộ câu hỏi có đáp án/rubric qua mock và sandbox | Transcript/traces/cost thật; không coi completed là đúng đáp án | Evaluation/runtime/guard composition | G2-INTEGRATION / NOT_RUN — thiếu tích hợp/môi trường |
| G2-I004 | Private context transfer | Chọn một fact từ direct chat để chuyển group | Chỉ fact được cho phép được chuyển; không lộ private history | Context transfer API + hai phiên browser | G2-INTEGRATION / NOT_RUN — thiếu tích hợp/môi trường |
| G2-I005 | Ngắt kết nối rồi tiếp tục | Mất mạng trong lúc gửi và cancel/resume | Hiển thị đúng trạng thái server; retry không nhân tin/task | Browser transport + backend cancel/resume | G2-INTEGRATION / NOT_RUN — thiếu tích hợp/môi trường |

Khi nghiệm thu tích hợp, lưu test ID, phiên bản/build, fixture, log đã loại secret, kết quả thực và người/owner xác nhận. Không đổi NOT_RUN thành PASS từ test fake tương tự.
