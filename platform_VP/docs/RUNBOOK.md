# Vận hành standalone platform

## Khởi động và cấu hình

Chạy Compose trong `platform_VP/deploy`. `init-local.ps1` sinh secret một lần và từ chối ghi đè `.env`. Giữ `VP_ENCRYPTION_KEY`: mất khóa sẽ không giải mã được credentials đã lưu. `.env` và `.local/accounts.txt` bị gitignore. Không paste nội dung chúng vào log hoặc issue.

```powershell
docker compose up -d --build
docker compose ps
docker compose logs --tail 60 api worker
Invoke-RestMethod http://localhost:3080/api/health
```

Đây là stack loopback cho phát triển. Để truy cập từ bên ngoài: đặt HTTPS reverse proxy, `VP_COOKIE_SECURE=true`, sửa `VP_TRUSTED_ORIGINS` đúng origin và quản lý secrets/backup; không mở thẳng DB/Redis/Qdrant. Bootstrap chỉ tạo admin khi DB chưa có user; thay biến password sau đó không đổi mật khẩu user hiện hữu.

Thông số chính: `VP_WORKERS=8`, `VP_MAX_SESSIONS=20`, `VP_LEASE_SECONDS=120`, `VP_MODEL_TIMEOUT_SECONDS=90`, `VP_MONTHLY_BUDGET_MICROS=100000000`, `VP_SESSION_BUDGET_MICROS=500000`. Worker replicas cùng DB dùng lease chung. 20 là giới hạn phiên được nhận chạy, không phải cam kết latency của mọi provider; throughput phụ thuộc số worker, model, quota và thời gian tools.

## Thiết lập luồng đầu tiên

1. Tạo **Khóa kết nối**, dán khóa tài khoản provider riêng cho platform.
2. Tạo model: native adapter, model ID đúng provider, endpoint nếu cần, tools+JSON capability, output/context cap, giá micro USD / triệu token và RPM/TPM thực tế. Giá $1/triệu token = `1000000` micro USD / triệu token. Không khai giá 0 cho provider có phí.
3. Tạo KB/tài liệu nếu cần. Gán embedding catalog nếu dùng semantic search; keyword search không cần API embedding.
4. Tạo agent charter cụ thể, model/fallback, grants, KB/skills. Kiểm tra chính sách và publish. Tạo coordinator và specialist khác nhau về trách nhiệm xác minh.
5. Chạy evaluation với câu hỏi có đáp án/nguồn chuẩn, câu thiếu dữ liệu, nguồn mâu thuẫn/hết hạn và prompt injection. Kiểm tra **Nguồn / Context / Trao đổi**, chi phí và unknowns trước khi dùng dữ liệu thật.
6. Tạo session, chọn coordinator trước, specialists sau. Agent thiếu dữ liệu sẽ needs_input; gửi bổ sung vào cùng session. Không giải quyết “thiếu dữ liệu” bằng nới quyền tool.

## Quan sát, dừng và phục hồi

- **Vận hành & chi phí**: wallet spent/reserved, usage reported/estimated uncertain, jobs/generation/error, worker heartbeat và audit. Heartbeat cũ quá 30 giây được đánh dấu unhealthy.
- Session **Dừng** vô hiệu hóa lượt đang chạy; không thu hồi được request đã gửi provider hay tác động tool đã xảy ra. Chi phí còn reserved được maintenance đối soát khi lease hết hạn.
- Crash worker: khởi động lại, đợi lease hết hạn; generation mới chặn kết quả worker cũ. Không sửa trực tiếp status/reservation DB để “giải phóng tiền”.
- `provider_rate_limit`: job được hoãn một phút, không tính là crash retry. `request_exceeds_model_tpm`: giảm context/output hoặc điều chỉnh quota và tạo revision/lượt mới; chờ không giải quyết request đơn lẻ quá quota.
- `budget_exhausted`: kiểm tra usage trước; admin tăng trần tháng hoặc ngân sách session rồi yêu cầu retry an toàn / gửi lượt mới. Ledger không tự hoàn tiền lượt mất phản hồi.
- `provider_error`/`agent_incomplete`: kiểm tra catalog/credentials và provider. Nút retry chỉ áp dụng job được server xác nhận an toàn. Revision cũ giữ cấu hình chốt; đổi model cap/skill cần revision và session mới.
- MCP `uncertain`: đối soát hệ thống bên ngoài bằng execution ID/tham số; không bấm lại để thử. `tool_config_changed_requires_new_approval`: kiểm tra endpoint mới, tạo lượt/intent mới và duyệt lại. Không sửa intent cũ thành succeeded nếu chưa có bằng chứng.
- Owner bị vô hiệu hóa/hạ quyền: các model/tool/index job kiểm tra lại trước thực thi; thao tác đã gửi trước khi thu hồi vẫn phải đối soát.

## Kiểm thử và xác minh bản đang chạy

```powershell
# Chỉ tạo database test riêng, không chạy drop_all trên DB chính:
docker compose exec -T postgres psql -U vp_platform -d postgres -c 'CREATE DATABASE vp_platform_test'
.\test-postgres.ps1
```

Lệnh CREATE DATABASE chỉ chạy lần đầu. Test script chỉ đọc local secret, không in password. Fixture từ chối PostgreSQL DB không kết thúc `_test`; toàn bộ schema DB test được reset giữa từng test. Không trỏ VP_TEST_DATABASE_URL đến dữ liệu dùng thật.

Frontend: `pnpm build`, `pnpm test` trong `apps/platform-web`. Browser server 8099 và Vite 3081 dùng DB/credential tổng hợp riêng, tự dừng sau test; production không có fixture-provider endpoint. Screenshot kiểm tra tại `test-results/`.

Sau rebuild/recreate, đối chiếu hash `dist/index.html` với HTML phục vụ cổng 3080 và source backend trong container, không chỉ dựa vào build thành công. Kiểm tra `docker compose ps`, `/api/health`, worker heartbeat và asset names. CI scoped tại `.github/workflows/platform.yml`; kết quả local không chứng minh CI trên GitHub đã chạy.

## Backup và nâng cấp

Backup PostgreSQL bằng `pg_dump -Fc` của database `vp_platform`, khóa Fernet ở kho secrets riêng, và Qdrant snapshot/volume nhất quán khi dùng vectors. Kiểm tra restore vào một database/stack mới trước khi chấp nhận backup; chưa có restore drill tự động trong bản này. Không xóa Compose volumes để reset nếu cần dữ liệu cũ. Lệnh `docker compose down` giữ volumes, không dùng `-v` cho vận hành thường ngày.

Schema hiện tại v1. Nâng cấp schema phải thêm migration versioned và thử trên bản restore; create_all không thay đổi cột của bảng hiện có. Retention của audit/event/SDK snapshots/vector đã thu hồi/backup cần được quyết định theo dữ liệu triển khai. Xóa memory/thu hồi tài liệu qua UI không đồng nghĩa purge toàn bộ bản sao vật lý.

## Jev tùy chọn

Giữ `VP_JEV_ENABLED=false`. Khi thử: cấu hình `VP_JEV_ENABLED=true`, `VP_JEV_API_KEY` và model pinned `jev-1.13.0`, recreate API/worker; gửi bộ state giả cùng expected route ở **Đánh giá → Jev shadow**. So sánh baseline deterministic, latency/usage và quyết định kỳ vọng. Không đưa PII vào state thử và không dùng confidence làm xác suất đúng. Tắt lại sau thí nghiệm; không có đường shadow đổi quyền hoặc quyết định runtime chính.
