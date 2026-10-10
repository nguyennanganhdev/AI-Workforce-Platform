# PHH — Phase A: gói hợp đồng để review

Ngày kiểm tra: 2026-10-10. Thành viên: Phan Huy Hoàng.

Clone từ `origin/develop2`, commit nền `254ec21a52c0f23511aee44248e9ca732b9c6cd3`.
Nhánh bàn giao: `dev2PHH`; đích pull request: `develop2`. Phạm vi bàn giao chỉ gồm Phase A của PHH.

**Hoàn thành phần chuẩn bị hợp đồng Phase A của PHH theo mục 17.9:** schema workflow/checkpoint/trigger/event, mẫu dữ liệu, kiểm thử và yêu cầu tích hợp. **Chỉ được làm Phase A theo yêu cầu người dùng. Chưa có xác nhận MA; chưa bắt đầu Phase B và không tự chuyển sang B.** Không đánh dấu toàn bộ PHH-12–PHH-17 hoàn thành vì các task này còn implementation ở giai đoạn sau.

## Đầu ra và phạm vi

- [PHASE_A.md](PHASE_A.md): đối chiếu đầu vào, invariants, transaction ordering và điều kiện sang B.
- [INTEGRATION_REQUEST_PHH_PHASE_A.md](INTEGRATION_REQUEST_PHH_PHASE_A.md): chữ ký hiện tại/đề xuất, điểm chưa thống nhất và owner cần chốt.
- [phase_a/schemas.json](phase_a/schemas.json): 9 model canonical tái xuất nguyên schema; 5 aggregate PHH đề xuất; 11 public payload schema.
- [phase_a/samples.json](phase_a/samples.json): mẫu hợp lệ, 4 loại cause, 3 pattern, 2 ticket cùng user/agent nhưng khác workflow/group/session.
- [phase_a/TEST_MATRIX.md](phase_a/TEST_MATRIX.md): 80 ca âm gốc có ID, input mutation và kết quả mong đợi. Suite hiện có tổng 242 tests, gồm cả kiểm thử đối kháng mới.
- [phase_a/QA_RESULTS.md](phase_a/QA_RESULTS.md): lỗi trước sửa, bản sửa, mutation testing và các điểm shared contract còn mở.
- Source trong `src/agentscope/app/workforce/orchestration/{phase_a.py,workflows/phase_a.py,partner_events/phase_a.py}`.
- Test/runner trong `tests/workforce/orchestration/phase_a/`.

Export review: `orchestration.phase_a.phase_a_schema_bundle()`, version `phh-phase-a-1`, status `proposal_pending_owner_acceptance`. DTO canonical vẫn lấy trực tiếp từ `workforce.contracts`; không sửa `contracts/`, migration, composition root, dependency manifest hay UI.

## Kiểm chứng

**242/242 unittest PHH PASS; 0 fail, 0 error, 0 skip.** Có 200 biến thể trộn workflow với seed cố định trong một test; không cộng các vòng lặp đó vào số 242. Thử vô hiệu hóa từng chốt `ValueError` của workflow trong bộ nhớ: **13/13 mutant bị test phát hiện**. Kiểm toán shared riêng vẫn có **2 điểm OPEN**, không gộp thành PASS.

Đã kiểm tra JSON Schema Draft 2020-12 với RFC3339 checker thực sự hoạt động, mẫu hợp lệ, serializer và model validators. Test âm xác nhận mẫu gốc hợp lệ trước khi sửa, tránh pass do fixture sai sẵn. Checkpoint nhận snapshot thật sinh bởi `AsyncToolProtocol.snapshot_ref` của NPD với các mẫu NPD trong checkout này. Bộ cũ 110 tests chưa phát hiện hết các lỗi nay đã sửa; chi tiết trước/sau ở QA_RESULTS.

Log: [phase_a/test-results.txt](phase_a/test-results.txt). Chín file Python qua Black 23.3.0 (79 cột), Flake8 6.1.0 và AST parse; các link local trong handoff hợp lệ. Chưa chạy toàn bộ pre-commit hooks hoặc full repo suite.

Môi trường chạy: Python 3.12.14 bundled, Pydantic 2.13.5; jsonschema 4.25.1 và rfc3339-validator 0.1.4 cài riêng vào `.venv/Lib/site-packages`. Windows Application Control chặn interpreter của venv mới nên dùng interpreter đã có; không thay chính sách máy. Không cài toàn bộ service stack.

Từ `platform_VP/agentscope`, chạy với Python đã có Pydantic, jsonschema và rfc3339-validator:

```powershell
python tests/workforce/orchestration/phase_a/run_phase_a.py --isolated-imports
```

Lệnh thực tế trên máy này:

```powershell
& 'C:\Users\hoang\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' tests/workforce/orchestration/phase_a/run_phase_a.py --isolated-imports --dependency-path .venv/Lib/site-packages
```

`--isolated-imports` chỉ bỏ initializer của `agentscope`/`agentscope.app` trong tiến trình test; vẫn import source thật của workforce/contracts và module PHH/NPD. Đây là bằng chứng contract-only, **không phải application bootstrap, integration runtime hay full regression**. Trong môi trường service đầy đủ, có thể bỏ cờ này. `--export` là thao tác riêng, chủ động tái tạo artifact; lần chạy test thông thường không ghi lại expected output.

## Phụ thuộc và giới hạn

Đầu vào thật đã đọc: NCH shared DTO/ports/UOW; NPD protocol/schema/hash; BHN requirements/policy proposal; PTA validation/eval schema; PHD operation/inbox và integration requests. Mẫu trong gói PHH là dữ liệu test, không có backend/provider thật hay fake service trả thành công. Không tái sử dụng implementation `dev2PHH` cũ.

Các yêu cầu còn mở: promotion DTO và chữ ký port (NCH/PHH/PHD); thống nhất policy BHN/PTA; resolver protocol snapshot (NPD/NCH); mapping operation/event/approval và UOW (PHD/NCH/PHH). Xem integration request để có chữ ký và owner cụ thể.

Chưa chạy/chưa triển khai: DB constraints/migration; inbox/outbox commit; lease/fence; replay/SSE; close/update race; crash/restart; quyền trên request thật; AgentScope turn; provider sandbox; UI. Schema không chứng minh các tính chất này.

Việc tiếp theo trong A: owner review các đề xuất, NCH xử lý IR-PHH-A05 và hợp nhất canonical contracts, rồi cập nhật artifact/test theo chữ ký đã chốt. Chưa được làm B trong yêu cầu hiện tại, kể cả khi checklist MA được cập nhật sau này; cần yêu cầu mới của người dùng.
