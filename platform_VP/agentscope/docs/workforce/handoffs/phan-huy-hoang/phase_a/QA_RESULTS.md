# Kiểm thử đối kháng Phase A — 2026-10-10

Phạm vi bàn giao trên `dev2PHH`: schema, validator, fixture, test và tài liệu PHH. Không làm Phase B, không sửa shared contracts. Pull request nhắm vào `develop2` theo yêu cầu người dùng.

## Kết quả và lỗi đã sửa

**242/242 unittest PHH PASS, không skip.** [Log cuối](test-results.txt). Bộ này kiểm tra dữ liệu/contract, không chứng minh DB transaction, quyền runtime, SSE, worker hay E2E.

Lần chạy đối kháng trước sửa có 232 tests, ghi nhận **13 failure outcomes** (bao gồm subtests) thuộc 3 nhóm. [Log trước sửa](adversarial-before.txt) được giữ nguyên:

| Phát hiện | Sửa trong lane PHH | Bằng chứng sau sửa |
|---|---|---|
| So sánh tập version làm mất dấu pin trùng trong WorkflowRecord khi ghép context | PinnedRuntimeContext kiểm tra uniqueness trước so sánh tập | Reject duplicate, vẫn chấp nhận permutation hợp lệ |
| Public payload timestamp nhận thời gian thiếu timezone, date-only hoặc epoch ngầm | AwareDatetime + kiểm tra dạng RFC3339 và timezone; schema có pattern tương ứng | UTC/offset/fraction hợp lệ; thiếu timezone, epoch số/chuỗi, ngày sai, offset sai dạng bị từ chối |
| Validator public event chỉ kiểm payload, bỏ qua envelope bị sửa bằng model_copy | Validate lại dict(event) qua canonical ConversationEvent, giữ được extra fields để reject | Bắt sequence=0, event_id rỗng, schema_version sai và scope thêm trái phép |

Ngoài ra phát hiện vấn đề ở môi trường test cũ: jsonschema có thể bỏ qua `date-time` khi thiếu dependency RFC3339. Đã cài **rfc3339-validator 0.1.4** vào môi trường test cục bộ và thêm kiểm tra fail-fast. Runner hiện dừng lỗi nếu thiếu checker; không còn báo format validation thành công khi thực tế bị bỏ qua. Không thay dependency manifest dự án.

## Độ mạnh của bộ kiểm thử

- 80 ca âm có ID từ bộ gốc, cùng positive controls và schema drift checks.
- Thử đầy đủ 24 tổ hợp status/is_new/result của claim, cả Python và JSON input.
- Budget nhận nhầm bool/float/string/null/list/object; ID biên 0/1/200/201 ký tự, Unicode và sai kiểu.
- Public payload của cả 11 loại event bị thử chèn manager/provider identity và raw trace; kiểm tra bằng Pydantic lẫn JSON Schema.
- 200 biến thể trộn workflow có seed `20261010`; xác nhận mẫu cùng workflow pass trước khi thay message bằng workflow khác. Đây là các vòng trong một test, không tính thành 200 test độc lập.
- Kiểm tra cause dedupe khi cùng inbox/request nhưng operation/approval ref khác; tránh coi metadata bị đổi là cause mới.
- Kiểm tra copy/mutation container, JSON round-trip, sample/schema drift và checkpoint nhận NPD snapshot ref thật.

Mutation testing: thử xóa từng `raise ValueError` guard trong source workflow bằng AST **trong bộ nhớ**. Bộ witness phát hiện **13/13**, không có survivor. [Chi tiết](mutation-results.json) ghi guard và case phát hiện. Không sửa file source hay class shared khi chạy. Kết quả chỉ áp dụng cho 13 phép biến đổi guard này, không phải mutation coverage toàn sản phẩm.

## Các điểm còn mở, không giấu trong số PASS

[Audit shared](shared-boundary-audit.json) hiện trả **2 OPEN**, exit code 1: WorkflowRecord nhận `revision=true`; ConversationEvent nhận thời gian không có timezone dù schema từ chối. Đã ghi IR-PHH-A05 để NCH review. PHH không tự sửa phần của owner khác. Ngoài ra các request policy BHN/PTA, runtime DTO/UOW/authorization và protocol resolver trước đó vẫn mở.

242 tests PHH pass không đồng nghĩa toàn bộ Phase A của team đã đạt MA. Chưa chạy full repository/pre-commit suite hay bootstrap service stack. Các định danh trong checkpoint vẫn cần DB xác minh đúng owner/binding ở giai đoạn được giao sau; schema không thể chứng minh ref thực sự thuộc workflow nào.

## Chạy lại

Dùng lệnh trong [STATUS.md](../STATUS.md). Các chế độ thêm:

- Không thêm cờ: 242 tests, dừng lỗi nếu không có RFC3339 checker hoặc không tìm thấy test.
- `--mutation-check`: xuất mutation-results.json, exit 0 khi không có guard mutant sống sót.
- `--shared-audit`: xuất shared-boundary-audit.json; **hiện exit 1** vì còn 2 OPEN.
- `--export`: chỉ tái xuất schema/mẫu khi chủ động thay contract; lần chạy test bình thường không cập nhật expected artifact.

Chỉ tiếp tục xử lý Phase A. Việc pass kiểm thử không tự cấp phép làm Phase B.
