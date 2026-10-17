# N2 — chạy lại browser/runtime và gate PostgreSQL

Source N2 đã rebase N1 `902bf056`, nhận API admin `e562059b`, consent/C07 `fb70de9e` và canonical close `3df1f1aa`. Đây là harness offline integration, không deploy hay model-quality UAT. Migration ứng dụng cần **0024_vin_admin_revisions** trước khi chạy phiên bản này; runner chỉ migrate DB fixture do nó tạo.

## Browser toàn hành trình

Yêu cầu Python 3.11 venv của Platform có Playwright/Chromium, dependency Domain, PostgreSQL disposable có pgvector. Không load `.env`. Fixture PostgreSQL phải có role admin tạo DB/role, chỉ loopback. Lệnh minh họa dùng đúng container fixture đã tạo trong phiên, không dùng DSN ứng dụng:

```powershell
# Từ platform_VP/agentscope/examples/web_ui/frontend:
$env:VITE_VIN_EXPERIENCE_ENABLED='true'
$env:VITE_API_BASE_URL='/api'
pnpm build

# Từ platform_VP/agentscope:
.venv\Scripts\python.exe scripts/workforce/check_vin_journey.py --admin-url postgresql://postgres:offline-n2-fixture-password@127.0.0.1:55441/postgres
```

Runner tự mở Uvicorn trên port loopback ngẫu nhiên và phục vụ đúng bundle `dist`, không cần Vite preview. Có thể truyền `--ui-dir` để pin build khác. API `/api` được strip prefix và refresh-cookie path được rewrite như nginx hiện có. Auth/session/JWT/capability, storage, C05/C06/C07, C09 và Domain business APIs đều dùng code thật. Platform và Domain có DB mới tách biệt, Domain và Platform runtime role NOSUPERUSER/NOBYPASSRLS; chỉ seed identity/catalog, không SQL inject workflow. Teardown DROP đúng DB/role namespace do fixture tạo, không dừng stack hiện có.

Năm ca trong `tests/vin_journey_browser_test.py`:

1. **Customer browser-link:** UI link/consent/callback → Leader chat thật với scripted model gọi CustomerService → case/ticket → Domain staff work order/assignment/status/quote → nút UI duyệt repair → ảnh trước/sau, completed/QC → nút UI xác nhận completion → replay receipt → canonical case completed + zero BQL commands → revoke link. Xem/mở/hủy thẻ không được gửi intent. Ảnh proxy cần auth và ACK, không bearer trong URL/model/UI.
2. **Customer HTTP-link:** cùng downstream runtime/consent/photo flow nhưng link qua HTTP adapter. Ca riêng giúp phân biệt lỗi redirect HTML với runtime, không thay thế ca browser-link.
3. **Admin:** 14 policies và phân trang, read/CAS/conflicting admin edit/409/reload, remove override, inactive catalog không grant caller, KB document review, revoke grant/membership, xác minh SQL revisions.
4. **Builder:** bắt đầu từ draft fixture đã review, nút chạy lại eval trên 5 ca scripted, publish C09 batch/activate atomic, reload không thêm agent/version. Không tuyên bố outline generation/model quality hoặc C08 thật từ ca text-only này; positive C08 được kiểm riêng ở strict contracts.
5. **Automation:** config once/bot và identity verified được seed bằng storage/authority fixture; hai timer và duplicate Discord message dùng C09/run thật + ChatService thật; saved delivery chạy REST implementation trên fake HTTP, nonce replay không gọi model. Browser xem ledger schedule/channel. Không chứng minh đăng nhập OAuth hoặc bot Discord thật; OAuth callback/scope/privacy có suite browser và contract riêng.

Model IO thay bằng scripted provider, Discord metadata/REST IO thay bằng fixture, Domain IdP thay bằng identity fixture. HTTP business giữa Platform–Domain đi qua ASGI transport in-process; browser gọi Platform Uvicorn thật. Icon Discord là static SVG fixture. Không dựng response API nghiệp vụ cho browser. Harness không cho outbound Python ngoài PostgreSQL fixture, browser abort ngoài origin cục bộ và các origin link synthetic đã pin. Không dùng model key thật. Các ca này bổ sung cho [Docker E2E của N1](N1_DOCKER_E2E_RUNBOOK_20261018.md), không đồng nhất với test Domain password/staff app thật hoặc RC images.

Chạy riêng ca để chẩn đoán:

```powershell
.venv\Scripts\python.exe scripts/workforce/check_vin_journey.py --scenario customer --admin-url postgresql://postgres:offline-n2-fixture-password@127.0.0.1:55441/postgres
.venv\Scripts\python.exe scripts/workforce/check_vin_journey.py --scenario admin --admin-url postgresql://postgres:offline-n2-fixture-password@127.0.0.1:55441/postgres
.venv\Scripts\python.exe scripts/workforce/check_vin_journey.py --scenario builder --admin-url postgresql://postgres:offline-n2-fixture-password@127.0.0.1:55441/postgres
.venv\Scripts\python.exe scripts/workforce/check_vin_journey.py --scenario automation --admin-url postgresql://postgres:offline-n2-fixture-password@127.0.0.1:55441/postgres
```

Evidence: `.artifacts/vin-journey/pytest.xml`, `summary.json`, ảnh/JSON từng luồng. JSON chỉ ghi method/path, không Authorization, cookie, bearer, intent proof/signature hoặc model input thô. Lượt lỗi có log riêng; không sửa thành PASS hoặc bỏ assertion closure/photo/replay. Dùng một runner journey tại một thời điểm để không ghi đè artifact.

## Concurrency và contracts

```powershell
.venv\Scripts\python.exe scripts/workforce/check_personal_postgres.py --admin-url postgresql://postgres:offline-n2-fixture-password@127.0.0.1:55441/postgres
.venv\Scripts\python.exe scripts/workforce/check_builder.py --contracts-only
.venv\Scripts\python.exe scripts/workforce/check_builder.py --runtime --automation
```

Chạy hai lệnh check_builder **tuần tự** vì cùng ghi `.artifacts/builder-check`. Concurrency runner chạy nguyên ca `personal_chat_test.py::test_group_runs_real_agents_and_dispatcher_with_deterministic_provider[sql]` trên DB fresh + vector, không SQLite fallback; SKIP là gate fail. Contract runner cũng fail nếu có SKIP. Runtime generic vẫn SKIP browser khi thiếu VIN_UI_TEST_URL và PG khi thiếu GROUP_TEST_POSTGRES_URL; số PASS của các runner riêng là evidence riêng, không viết lại số SKIP lịch sử hoặc cộng coverage trùng.

Gói model thật: [lệnh, dữ liệu và ngân sách cho chủ dự án](N2_MODEL_OWNER_TEST_RUNBOOK_20261018.md). Tất cả ô model thật vẫn NOT_RUN; không chạy gói này bằng agent.
