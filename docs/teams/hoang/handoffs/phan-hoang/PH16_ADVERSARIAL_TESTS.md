# PH16 — Kiểm thử các chuỗi sự cố

Thành viên: Phan Hoàng\
Task: PH16 — kiểm thử bổ sung; ghi nhận lỗi transport thuộc PH17\
Folder được phép sửa: `agent-reception/tests/tools/**`, tài liệu request/handoff `phan-hoang`\
Dependency đang dùng: tools thật, HTTP MockTransport, fixture graph hiện có; chưa có API producer thật.

Ngày: 01/10/2026. Nhánh: `dev_TeamHoang`.

## Kết quả thực chạy

Đã thêm `agent-reception/tests/tools/test_adversarial.py`: **50 ca kiểm thử thuộc
10 nhóm tình huống**, gồm **45 đạt và 5 thất bại**. Chạy cùng toàn bộ Python tests:
**332 đạt, 5 thất bại** trong 4.06 giây. Ruff check và format check đạt.

Năm ca thất bại tái hiện **hai vấn đề đã được review**, không phải năm lỗi độc lập.
Test assert hành vi cần đạt và đang để FAIL bình thường, không skip/xfail, không
đổi kỳ vọng sang hành vi sai để làm xanh bộ test. Lượt này bổ sung test/tài liệu;
code sản phẩm và dependency được giữ nguyên so với trước lượt kiểm thử.

## Các kịch bản

| Nhóm | Kịch bản gây rắc rối | Kết quả và giới hạn |
|---|---|---|
| AD01 | Lần đầu 503/`not_applied`, lần sau `ReadTimeout` hoặc `RemoteProtocolError`; chạy cả execute/reconcile | **4 FAIL**: trả phản hồi `not_applied` cũ; phải trả `unknown` |
| AD02 | Ghép graph hiện có với `BackendToolPort` mới | **1 FAIL**: pending `create_ticket_draft`, phase `waiting_operation`, HTTP calls = 0 |
| AD03 | Handoff mất phản hồi, lần thử tiếp theo nhận receipt đúng; execute/reconcile | **2 PASS**: body/key giữ nguyên, receipt hợp lệ được nhận |
| AD04 | HTTP 400/401/403/404/409/410/422/429/500/502/503/504 mang body giống success | **24 PASS**: không công nhận handoff thành công, retry có giới hạn và giữ body/key; 429/5xx giữ `unknown` |
| AD05 | HTTP 200 trả HTML/null/array hoặc 204 rỗng; execute/reconcile | **8 PASS**: lỗi contract, không tự gửi lại mutation, thông báo lỗi không chứa chuỗi bí mật giả trong HTML |
| AD06 | Backend giả đã nhận thao tác, sau đó trả accepted/mất response/task bị cancel; khôi phục pending bằng client mới | **3 PASS**: reconcile có thể còn accepted rồi success; một execute, hai reconcile cùng body/key, file được xác nhận cuối cùng |
| AD07 | Cư dân gửi hai file có ID trùng, backend chỉ xác nhận một file; sau đó reconcile trả đủ | **3 PASS** cho update/append/interaction: chặn receipt thiếu, giữ request gốc, reconcile cùng body/key và nhận xác nhận đủ |
| AD08 | Caller dùng lại key với nội dung khác, backend trả 409 conflict | **1 PASS**: chuyển nguyên failure có cấu trúc, không retry hoặc biến thành success |
| AD09 | Hai tenant gọi cùng lúc; trả kết quả theo thứ tự ngược, rồi thử tráo response giữa tenant | **2 PASS**: nhận đúng response dù đảo thứ tự; cả hai response tráo tenant/binding đều bị chặn |
| AD10 | Self-help đã offered nhưng lúc cư dân đồng ý, backend trả revoked/expired | **2 PASS**: trả trạng thái hiện tại, không lấy procedure/consent cũ gắn vào kết quả |

## Hai vấn đề cần khắc phục

### AD01 — mất phản hồi của lần thử cuối

Vị trí: `agent-reception/src/tools/backend.py`, `_post`, biến `last_response`.
Sau lần đầu nhận response, lần tiếp theo mất phản hồi nhưng biến này vẫn trỏ về
response cũ. Khi hết lượt thử, adapter decode lại response cũ và trả `not_applied`.

Ở execute, lần sau có thể đã ghi dữ liệu trước khi mất phản hồi. Ở reconcile,
response bị mất có thể chứa kết quả đối soát mới. Không thể dùng response của lần
trước để kết luận thao tác chưa được áp dụng. Graph hiện tại xóa `pending` khi thấy
`not_applied` tại `_execute_operation`, làm mất đường đối soát thao tác chưa rõ kết quả.

Khắc phục đề xuất cho Phan Hoàng/PH17: phân biệt kết quả của lần thử cuối; nếu mất
phản hồi thì trả `unknown`, không tái sử dụng response cũ. Giữ nguyên input/key khi
đối soát. Đây là lỗi đã tồn tại trong HTTP baseline, không phải lỗi mới của validator.

### AD02 — graph chưa chuyển sang contract mới

Vị trí: `agent-reception/src/tools/backend.py` gọi `prepare_call`; graph vẫn truyền
`timeoutMs`, `signal` và context có trường ngoài envelope mới. Request bị từ chối
trước HTTP; graph chuyển sang chờ đối soát dù chưa gửi thao tác.

Khắc phục đề xuất: Phan Dũng chuyển protocol/nodes sang các method có kiểu, mapping
V2 và xử lý checkpoint cũ theo
[integration request](../../requests/phan-hoang/PH16_TYPED_TOOLS_INTEGRATION.md).
Sau migration phải mở rộng kiểm thử thành graph + facade + HTTP chạy đủ luồng;
AD02 hiện chỉ kiểm tra điều kiện tối thiểu là graph gửi được HTTP, không thay thế
nghiệm thu toàn bộ flow.

## Cách chạy lại

Từ root repo, PowerShell, dùng virtualenv đã cài:

```powershell
.\.codex-artifacts\ph16\venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider agent-reception/tests/tools/test_adversarial.py --tb=short
# 5 failed, 45 passed; exit 1 cho tới khi xử lý hai vấn đề trên.

.\.codex-artifacts\ph16\venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider agent-reception/tests --tb=short --junitxml=.codex-artifacts/ph16/adversarial-results.xml
# 5 failed, 332 passed; XML nằm trong thư mục Git ignored.

.\.codex-artifacts\ph16\venv\Scripts\python.exe -m ruff check agent-reception/src/tools agent-reception/tests/tools
.\.codex-artifacts\ph16\venv\Scripts\python.exe -m ruff format --check agent-reception/src/tools agent-reception/tests/tools
```

## Phạm vi bằng chứng

- Bộ cũ đã kiểm tra happy path và validation cho đủ 14 operation. Các test hiện có
  còn kiểm tra receipt/event sai ticket, generation, version, correlation; V1/V2;
  input giả quyền; self-help policy/consent; graph baseline xử lý event trùng/cũ.
- Các test mới chủ yếu kiểm tra chuỗi lỗi ở facade/adapter. AD02 dùng graph thật với
  model/intake/resolver/checkpointer fixture hiện có; chưa vượt qua bước gọi tool đầu.
- AD06 lưu JSON pending của caller thử nghiệm rồi tạo client mới. Đây không phải
  kiểm chứng restart toàn bộ graph, checkpoint production hoặc crash của process.
- Số lần ghi dữ liệu và phản hồi conflict do backend giả mô phỏng. Test chứng minh
  hành vi client, không chứng minh backend thật đã triển khai dedup/transaction/auth.
- Chưa có producer-consumer/E2E với Team Chiến/Supervisor, auth thật, event bus,
  nhiều process/replica hoặc kiểm thử tải. Không đo coverage phần trăm và không kết
  luận đã test hết mọi chức năng chỉ từ số ca đạt.

PH16 vẫn chưa DONE; PH17 chưa được nghiệm thu toàn bộ; PH18 còn chờ API thật.
