# Workforce v1: sổ tay vận hành

Cập nhật: 11/10/2026 (phase P5, phần S7a: PostgreSQL, migration, retention). Viết cho **người vận hành platform**. Cách nối một đối tác (client, khóa, route, MCP, integration) ở `docs/WORKFORCE_V1_HUONG_DAN_KET_NOI.md`; tài liệu này nói về *chạy* platform: biến môi trường, cơ sở dữ liệu, migration, bí mật, sao lưu và các vòng quét nền.

## 1. Những gì cần có

| Thành phần | Dev / một tiến trình | Nhiều tiến trình / production |
|---|---|---|
| Cơ sở dữ liệu | SQLite (`sqlite+aiosqlite:///./awp.db`), tự tạo bảng | **PostgreSQL 16** (`postgresql+asyncpg://…`), bảng tạo bằng migration |
| Bus phiên (AgentScope) | `InMemoryMessageBus` (mặc định) | Redis (`RedisMessageBus`) là điều kiện để chạy **nhiều tiến trình**. **Chưa nối vào `python -m awp`** ở phần S7a: `build_app(message_bus=…)` nhận bus từ mã, biến `AWP_REDIS_URL` thuộc phần S7b. Gói `redis` đã khai ở extra `redis`. |
| Lưu ảnh (A3) | chưa có | MinIO/S3 (phần S7 sau) |
| Python | 3.11 | 3.11 |

Cài driver: `pip install "awp[postgres]"` (asyncpg) và `"awp[redis]"` (redis). Trong venv của repo (`platform_VP/agentscope/.venv`, tạo bằng `uv`, không có pip) đã cài asyncpg 0.32.0 bằng: `uv pip install --python platform_VP/agentscope/.venv/Scripts/python.exe asyncpg`.

**Cỡ pool.** Mỗi tiến trình mở tối đa `AWP_DB_POOL_SIZE + AWP_DB_MAX_OVERFLOW` kết nối cho DB của awp (mặc định 10 + 20) và cùng số đó cho DB lưu trữ của AgentScope. `số tiến trình × 2 × (pool_size + max_overflow)` phải nhỏ hơn `max_connections` của PostgreSQL (mặc định 100) trừ phần dành cho người vận hành. Hết kết nối thì một request chờ `AWP_DB_POOL_TIMEOUT` giây rồi lỗi. Kết nối được kiểm (`pool_pre_ping`) mỗi lần lấy ra và tái tạo sau `AWP_DB_POOL_RECYCLE` giây, nên PostgreSQL khởi động lại hoặc proxy cắt kết nối rảnh không làm hỏng request. Mức cô lập là `READ COMMITTED` (đặt rõ trong engine, không nhờ mặc định của máy chủ): mã dựa vào khóa hàng của hội thoại (`events.lock_conversation`) và các UPDATE có điều kiện, không dựa vào snapshot.

## 2. Biến môi trường

Bắt buộc (trừ `AWP_DEV_OPEN=1`): `AWP_ADMIN_KEYS`, `AWP_SECRET_KEY`. Tất cả còn lại có mặc định. Danh sách đủ ở `platform_VP/core/.env.example`; nhóm quan trọng:

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `AWP_DB_URL` | `sqlite+aiosqlite:///./awp.db` | DB của awp (`awp_*`, `wf_*`). |
| `AWP_AGENTSCOPE_DB_URL` | `sqlite+aiosqlite:///./agentscope.db` | DB lưu trữ của AgentScope (phiên, tin nhắn). Có thể trùng DB trên (hai lịch sử migration dùng hai bảng phiên bản khác tên: `awp_alembic_version`, `alembic_version`). |
| `AWP_AUTO_CREATE` | `1` | `1`: lúc khởi động tạo bảng thiếu bằng `create_all` (dev, SQLite, test). **Production đặt `0`**: bảng chỉ do migration tạo, và tiến trình từ chối khởi động nếu DB chưa ở revision mới nhất. |
| `AWP_DB_POOL_SIZE`, `AWP_DB_MAX_OVERFLOW`, `AWP_DB_POOL_TIMEOUT`, `AWP_DB_POOL_RECYCLE` | 10, 20, 30, 1800 | Pool kết nối PostgreSQL (mục 1). Không có tác dụng với SQLite. |
| `AWP_EVENT_RETENTION_DAYS` | 90 | Event công khai giữ bấy nhiêu ngày sau khi workflow đóng. `0` = không dọn. |
| `AWP_INBOX_RETENTION_DAYS` | 180 | Hàng dedupe của hộp thư provider. `0` = không dọn. |
| `AWP_CLOSED_RETENTION_DAYS` | 90 | Job và lượt chạy đã xong của workflow đã đóng. `0` = không dọn. |
| `AWP_RETENTION_EVERY_SECONDS` | 3600 | Chu kỳ dọn. `0` = tắt hẳn lịch dọn. |
| `AWP_HOST`, `AWP_PORT` | `127.0.0.1`, `8800` | Địa chỉ nghe. |
| `AWP_EVAL_GATE` | `1` | Cổng phát hành: version chỉ được `publish` khi lần đánh giá gần nhất của đúng version đó đạt, hoặc có `override_reason`. **Để `1` ở production**; `0` chỉ cho máy phát triển không có model. |
| `AWP_EVAL_CASE_TIMEOUT_SECONDS`, `AWP_EVAL_CASE_BUDGET_USD`, `AWP_EVAL_CASE_BUDGET_TOKENS`, `AWP_EVAL_PARALLEL` | 180, 0.5, 400000, 2 | Giới hạn của một ca đánh giá (thời gian, ngân sách) và số lần chạy đánh giá đồng thời **của một tenant** trong một tiến trình (mỗi tenant có chỗ riêng; mục 9). |
| `AWP_BUILDER_OVERLAP_THRESHOLD`, `AWP_BUILDER_TIMEOUT_SECONDS` | 0.5, 90 | Ngưỡng trùng (0..1) để builder đổi `create` thành `reuse` (điểm cao hơn trong hai điểm: `handles` riêng, và `handles` + `mission`); thời gian tối đa cho một câu trả lời của model builder. |

Hợp đồng (mục 12) đòi giữ event tối thiểu 90 ngày sau close và dedupe tối thiểu 180 ngày, "trừ thỏa thuận khác". Đặt thấp hơn là một ngoại lệ hợp đồng phải được ghi lại; platform chỉ ghi cảnh báo lúc khởi động.

## 3. Migration (Alembic)

Có hai lịch sử migration độc lập và cả hai phải ở revision mới nhất trước khi chạy với `AWP_AUTO_CREATE=0`:

1. **Bảng của awp** (`awp_*`, `wf_*`): scripts ở `platform_VP/core/src/awp/migrations/`, bảng phiên bản `awp_alembic_version`.
2. **Bảng lưu trữ của AgentScope**: scripts riêng của AgentScope (`agentscope/app/storage/_sql/_alembic`, bảng phiên bản `alembic_version`). Đây là điều tài liệu nghiên cứu `docs/research/AGENTSCOPE_CHO_WORKFORCE_V1.md` mục 5 dặn: **không** dùng `auto_migrate` của AgentScope với nhiều bản sao (chúng đua nhau migration); chạy migration như một bước triển khai riêng, một lần.

Bước triển khai (một lần cho mỗi phiên bản, trước khi khởi động các tiến trình):

```
export AWP_DB_URL=postgresql+asyncpg://awp:***@db:5432/awp
export AWP_AGENTSCOPE_DB_URL=postgresql+asyncpg://awp:***@db:5432/awp_storage
python -m awp migrate --storage     # bảng awp tới revision mới nhất, rồi bảng của AgentScope bằng script của AgentScope
python -m awp migrate --check       # thoát 1 và nói lý do nếu DB chưa ở revision mới nhất hoặc khác mô hình
```

`--check` chạy tốt làm bước kiểm trước khi bật tiến trình mới (nó so sơ đồ thật với mô hình bằng chính autogenerate của Alembic). Một DB đã tạo bằng `create_all` (dev, hoặc tạo trước P5) và đúng với mô hình thì nhận lịch sử migration bằng `python -m awp migrate --stamp` (từ chối nếu sơ đồ khác mô hình); sau đó dùng `migrate` như thường. Hạ cấp: có hàm `awp.migrate.downgrade(url, revision)`, chưa có lệnh dòng lệnh (xuống revision là việc hiếm, làm từ shell Python và có sao lưu).

Thêm một thay đổi sơ đồ: sửa `awp/db.py` hoặc `awp/workforce/tables.py`, rồi sinh revision (`alembic` với cấu hình của `awp.migrate.config(url)`: `command.revision(cfg, autogenerate=True, message=…)`), đọc lại script sinh ra, và **giữ revision đầu tiên nguyên vẹn** (nó là ảnh chụp đóng băng, không gọi `create_all`). Test `tests/workforce/test_wf_migrations.py::test_models_and_migrations_never_drift` đỏ khi mô hình và migration lệch nhau: đó là lưới chặn trong CI.

Tạo bảng AgentScope trên DB trống mà không migration (dev): để `AWP_AUTO_CREATE=1`. Với `AWP_AUTO_CREATE=0` platform cũng bảo AgentScope không tự `create_all`.

## 4. Bí mật

- `AWP_ADMIN_KEYS`: khóa Bearer của admin theo tenant. Dài, ngẫu nhiên, xoay bằng cách đổi biến và khởi động lại.
- `AWP_SECRET_KEY`: khóa Fernet niêm khóa ký provider và header MCP trong DB. **Mất khóa này là mất các bí mật đã niêm** (phải tạo lại khóa ký và cấu hình MCP); đổi khóa không tự giải mã lại bản cũ. Sao lưu riêng với DB.
- Khóa API của đối tác (`dp_<id>.<secret>`): chỉ lưu băm SHA-256, hiện đúng một lần lúc tạo. Mất thì xoay.
- Mật khẩu DB nằm trong URL: đặt qua trình quản lý bí mật của nơi triển khai, không commit `.env`. Log của platform không ghi URL, khóa hay header Authorization.
- Khóa model (`OPENAI_API_KEY`…) theo `models.yaml`.

## 5. Sao lưu và khôi phục

- Sao lưu **cả hai** DB (awp và lưu trữ AgentScope) cùng một thời điểm nếu được (`pg_dump` cùng lúc, hoặc snapshot): workflow tham chiếu phiên AgentScope bằng id (`awp_cases.leader_session_id`). Khôi phục một DB cũ hơn DB kia để lại workflow có phiên không còn.
- Thêm `AWP_SECRET_KEY` vào bản sao lưu bí mật (mục 4), không vào bản sao lưu DB.
- Thư mục workspace (`AWP_WORKSPACE_DIR`) chứa bộ nhớ dài hạn và offload ngữ cảnh theo workflow; sao lưu nếu dùng bộ nhớ dài hạn. Với nhiều máy cần workspace dùng chung (xem tài liệu nghiên cứu mục 5, rủi ro 4).
- Sau khi khôi phục: `python -m awp migrate --check`, rồi khởi động. Khi khởi động engine tự xếp lại job hết lease và đóng các lượt dở (xem `recover.py`).
- Dung lượng: event, hộp thư provider, job và lượt chạy tăng theo thời gian; chúng được dọn theo mục 6. Tin nhắn, request, operation, approval và workflow **không bao giờ bị dọn** (là dấu vết kiểm toán và khóa idempotency).

## 6. Các vòng quét nền (làm gì, ai làm)

Mỗi tiến trình chạy một vòng quét mỗi 2 giây (`build_app(sweep_every=…)`). Trong đó:

| Việc | Mọi tiến trình đều làm? | Chi tiết |
|---|---|---|
| Nhặt job đang chờ, trả lại job mất chủ, đóng lượt dở | có (an toàn: mọi bước là so sánh-và-đặt dưới khóa hội thoại; trên PostgreSQL một bước không chờ khóa hội thoại của người khác mà bỏ qua, vòng sau làm lại) | `runner.sweep`, `recover.py` |
| Hết hạn approval, workflow kẹt, chờ ngoài quá hạn | có (như trên) | `expiry.py` |
| Áp sự kiện provider đang chờ / nối lại sự kiện quarantined | có | `provider_sweep.py` |
| Đối soát operation dở, hỏi `status_query` | có | `reconcile.py` |
| **Dọn dữ liệu cũ (retention)** | **một tiến trình mỗi chu kỳ** | Xem dưới. |

**Retention** chạy dưới một *lease* trong bảng `wf_leases` (tên `retention`): tiến trình nào giành được dòng đó thì dọn, các tiến trình khác bỏ qua; mỗi `AWP_RETENTION_EVERY_SECONDS` giây một lần cho cả đội tiến trình. Lease hết sau 10 phút nếu tiến trình chết giữa chừng và lần dọn bị coi là chưa chạy, nên tiến trình khác làm lại từ đầu (việc dọn lặp lại được). Lần dọn đầu tiên của một DB mới chạy ngay lúc khởi động. Mỗi lần dọn:

1. **Event công khai** của hội thoại mà *mọi* workflow đã đóng quá `AWP_EVENT_RETENTION_DAYS` ngày: xóa, để lại tombstone và đặt `purged_through` (cursor cũ trả `410 EVENT_CURSOR_EXPIRED`, snapshot vẫn đọc được). Event mới nhất của hội thoại luôn ở lại.
2. **Hộp thư provider** (`wf_provider_inbox`) quá `AWP_INBOX_RETENTION_DAYS` ngày, chỉ các biên nhận đã có kết cục (`applied`, `duplicate`, `rejected`, `needs_attention`).
3. **Job và lượt chạy đã kết thúc** (`done`/`failed`, `completed`/`error`/`interrupted`) của workflow đã đóng quá `AWP_CLOSED_RETENTION_DAYS` ngày.

**Không bao giờ dọn**: workflow đang mở và mọi thứ của nó; workflow đã đóng còn operation `intent`/`sent`/`pending`/`unknown` (event, biên nhận, job, lượt chạy của nó); biên nhận đang xử lý (`accepted`, `processing`, `quarantined`); job `queued`/`dispatched` và lượt `running`; tombstone.

Muốn giữ vô hạn một loại dữ liệu: đặt số ngày của nó là `0`. Muốn tắt cả lịch: `AWP_RETENTION_EVERY_SECONDS=0`. Xem lần dọn gần nhất: `select name, owner, last_run_at from wf_leases`.

## 7. Kiểm tra sức khỏe sau khi triển khai

1. `GET /platform/v1/health` trả 200.
2. `python -m awp migrate --check` thoát 0.
3. `select count(*) from wf_jobs where status='dispatched' and lease_until < extract(epoch from now())` gần 0 (job mất chủ được nhặt trong vài giây).
4. `GET /platform/v1/wf/workflows` lọc `needs_attention`: mỗi dòng có `attention_reason`.

## 8. Chạy thử trên PostgreSQL ở máy phát triển

Bộ test chạy trên PostgreSQL thật khi đặt `AWP_TEST_PG_URL` (tài khoản được tạo database); mỗi test có hai database riêng, nhân bản từ một template, xóa khi xong:

```
docker run -d --name awp-test-pg -p 127.0.0.1:55432:5432 -e POSTGRES_USER=awp -e POSTGRES_PASSWORD=awp postgres:16-alpine \
  -c fsync=off -c synchronous_commit=off -c full_page_writes=off -c max_connections=400
export AWP_TEST_PG_URL=postgresql://awp:awp@127.0.0.1:55432/postgres
cd platform_VP/core && PYTHONPATH=src ../agentscope/.venv/Scripts/python.exe -m pytest -q
docker rm -f awp-test-pg
```

Không đặt biến thì bộ test chạy trên SQLite như trước. Trên SQLite cả bộ chạy song song được bằng pytest-xdist (extra `test` của `pyproject.toml`; trong venv của repo: `uv pip install --python platform_VP/agentscope/.venv/Scripts/python.exe pytest-xdist`): `PYTHONPATH=src ../agentscope/.venv/Scripts/python.exe -m pytest -q -n 8 -p no:cacheprovider`, khoảng 5 phút thay vì 30. **Không dùng `-n` với `AWP_TEST_PG_URL`**: `tests/dbtest.py` dựng template và dọn mọi database `awpt_*` một lần cho mỗi tiến trình, nên các worker song song sẽ xóa database của nhau; trên PostgreSQL chạy tuần tự. Các test chỉ có nghĩa với PostgreSQL thật (deadlock hai phiên, `40001`) tự bỏ qua trên SQLite, có ghi lý do.

## 9. Build, đánh giá và phát hành agent (B2)

**Build qua chat** (`/platform/v1/builder/sessions`, chỉ admin). Model tầng `strong` đề xuất; platform quyết: `create` trùng nghiệp vụ với agent cùng vai đã có thành `reuse`: điểm Jaccard ≥ `AWP_BUILDER_OVERLAP_THRESHOLD`, lấy điểm cao hơn giữa `handles` riêng và `handles` + `mission` (cùng `handles` là cùng việc dù `mission` viết khác), so với **cả bản đang phát hành lẫn bản nháp mới nhất** của mỗi agent; `tools_allow` chỉ giữ tool đang `active` trong kho tool của tenant; `apply` chỉ tạo **bản nháp**, trong một giao dịch có khóa phiên: nhiều lần `apply` cùng lúc của một phiên chỉ tạo một bản nháp và đều trả về bản đó. Một key hồ sơ thuộc đúng một tenant tại một thời điểm (bảng `awp_profile_keys`): tenant khác chỉ lấy được key khi tenant đang giữ không còn bản nháp hay bản phát hành nào; `rollback` vào một key đã thuộc tenant khác trả `409`. Chi phí mỗi lời gọi model của builder nằm trong `awp_ledger` của tenant (`agent_name = builder`, `case_id` trống) và hiện ở `GET /platform/v1/cost`. Không có model thì builder trả `503`; model trả sai dạng thì `502` và phiên không đổi.

**Đánh giá** (`POST /platform/v1/profiles/{key}/versions/{v}/evals`, body tùy chọn `{"wait_seconds": n}`; trả `202` khi còn chạy, `200` khi xong; kết quả ở `GET` cùng đường). Mỗi lần chạy gồm bộ ca của platform (không bịa số, nói không biết khi thiếu dữ liệu, từ chối việc trong `refuses`; leader thêm "việc đơn giản không cần team" và "chọn đúng chuyên viên") cộng các ca của tenant (`/profiles/{key}/eval-cases`). Mỗi ca là một workflow thật trên engine, trong **sandbox**:

- Mỗi tenant có một client và một route nội bộ (`environment = eval`, id suy ra từ tenant). Client này không bao giờ có khóa (API admin không nhìn thấy nó), route không có MCP server hay tool, nên không gì của sandbox đọc được qua `/workforce/v1` và không lời gọi nào tới đối tác. Các màn hình admin (`/wf/clients`, `/wf/routes`, `/wf/workflows`, `/cases`) không liệt kê sandbox; hồ sơ vụ của một ca đọc bằng `GET /platform/v1/cases/{case_id}/items` (id nằm trong kết quả lần chạy).
- Tool của agent trong sandbox là câu trả lời ghi sẵn (`fixtures` của ca). Tool nào hồ sơ cho phép mà ca không có fixture thì agent không có tool đó.
- Chuyên viên chạy dưới một leader đánh giá của platform (hồ sơ `awp_eval_leader`, không thuộc tenant nào; tiền tố `awp_` bị cấm với hồ sơ của tenant). Leader chạy đúng version đang nháp trong một workflow sandbox; chuyên viên nó gọi là các bản đã phát hành.
- Giới hạn: mỗi ca tối đa `AWP_EVAL_CASE_TIMEOUT_SECONDS` giây và ngân sách `AWP_EVAL_CASE_BUDGET_USD`/`_TOKENS`; hết giờ thì workflow sandbox bị đóng, agent bị ngắt, ca trượt. Một version chỉ có một lần chạy tại một thời điểm (`409`; chỉ mục duy nhất `uq_eval_run_running` giữ điều đó cả giữa các tiến trình). Tiến trình đang chạy một lần đánh giá gia hạn `deadline` của nó mỗi ~22 giây (hạn 90 giây); lần chạy còn `running` sau hạn (tiến trình chết) tự thành `error`: sau khi platform chết đột ngột, version đó bị chặn tối đa 90 giây. Workflow sandbox chỉ được engine cho chạy khi lần đánh giá của nó đang sống trong chính tiến trình đó; workflow sandbox mà lần đánh giá đã hết (tiến trình chết giữa một ca) không được chạy lượt nào (job `failed`, không lời gọi model) và được đóng ở vòng quét kế tiếp.
- Chi phí đánh giá là chi phí thật của tenant (ledger, theo vụ sandbox).

**Phát hành** (`POST …/publish`): `409` với `detail.code = EVAL_REQUIRED` khi version chưa có lần đánh giá, lần gần nhất chưa đạt/đang chạy, bản nháp đã sửa sau khi đánh giá, hoặc **bộ ca đã đổi** sau khi đánh giá (kết quả gắn với băm nội dung hồ sơ và băm bộ ca: ca của platform + ca của tenant; thêm/sửa/xóa một ca, hoặc đổi hồ sơ thành viên team mà ca "chọn đúng chuyên viên" dựa vào, đều buộc chạy lại). Admin ghi đè bằng `{"override_reason": "..."}` (tối đa 300 ký tự), được ghi vào lịch sử cùng khóa admin đã dùng (`admin:<8 ký tự HMAC-SHA256 của khóa, khóa HMAC là AWP_SECRET_KEY>`: không phải băm trần của khóa admin, vì nhãn này hiện cho cả khóa manager; đổi `AWP_SECRET_KEY` thì nhãn của cùng một khóa admin đổi theo). **Rollback** (`POST /profiles/{key}/rollback {"to_version": n}`) đưa một version `retired` trở lại; workflow đang chạy giữ leader nó bắt đầu, chuyên viên được tạo sau đó và workflow mới dùng version vừa quay về. **Lịch sử**: `GET /profiles/{key}/history` (`create`, `eval`, `publish`, `override`, `rollback`, `retire`; ai, khi nào).

**Khóa manager**: với hồ sơ mà route của mình dùng (leader và team của leader) được xem ca/lần chạy/lịch sử và chạy đánh giá; nếu hồ sơ không được route của manager khác dùng thì còn được sửa ca, phát hành (phải có đánh giá đạt, không được ghi đè) và rollback. Hồ sơ dùng chung do admin phát hành. Leader **không khai team** được tạo mọi chuyên viên của tenant, nên route dùng leader như vậy được tính là dùng mọi chuyên viên của tenant (các chuyên viên đó thành dùng chung). Rollback bằng khóa manager chỉ là hoàn tác một lần phát hành: phải đang có một version phát hành (agent admin đã `retire` thì chỉ admin đưa lại, `403`) và version đích không phải bản từng lên bằng ghi đè của admin (`403`). Builder và sửa hồ sơ chỉ dành cho admin.

**Dữ liệu sandbox không tự dọn**: mỗi ca để lại một workflow đã đóng, một vụ, các agent/phiên AgentScope và một thư mục workspace. Event của chúng được dọn theo mục 6 như mọi workflow đã đóng; phần còn lại ở lại (xem `select count(*) from wf_workflows where client_id like 'client_eval_%'`).

## 10. Console quản trị (`/console`)

Platform tự phục vụ một trang quản trị tại `http://<AWP_HOST>:<AWP_PORT>/console` (bốn tệp tĩnh trong gói `awp.console`: HTML, một tệp JS, một tệp CSS, một biểu tượng; không bước build, không tải gì từ nơi khác). Không cần cấu hình thêm và không có biến môi trường riêng.

- **Đăng nhập** bằng một khóa trong `AWP_ADMIN_KEYS` hoặc một khóa manager (`mk_…`, mục 3 của hướng dẫn nối). Khóa chỉ nằm trong `sessionStorage` của tab đó (mất khi đóng tab hoặc bấm Đăng xuất), chỉ được gửi trong header `Authorization: Bearer`, không bao giờ nằm trong địa chỉ trang; không có cookie. Khi một lời gọi trả `401` (khóa bị thu hồi, tài khoản manager bị tắt), trang bỏ khóa và về màn đăng nhập.
- **Trang không chứa dữ liệu và không có luật riêng**: mọi màn hình là một lần đọc API admin (`/platform/v1/…`), nên API quyết định mỗi khóa thấy gì. Khóa admin có năm màn hình (Kho tool, Agent kèm "Tạo agent qua chat", Đối tác, Vận hành, Chi phí); khóa manager có ba (Kho tool, Agent, Vận hành) và chỉ thấy route, workflow, agent của chính tài khoản đó. Mở `/console` không cần khóa (chỉ là tệp tĩnh); mọi đường khác vẫn cần.
- **Header của các tệp tĩnh**: `Content-Security-Policy: default-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `X-Frame-Options: DENY`, `Cache-Control: no-store`. Nếu đặt platform sau một reverse proxy thì giữ nguyên các header này và phục vụ `/console` cùng origin với `/platform/v1` (trang chỉ gọi origin của chính nó). Ngoài máy phát triển phải dùng HTTPS: khóa đi trong header của mọi lời gọi.
- **Trang không tự làm mới**: dữ liệu là của lúc mở màn hình; bấm "Tải lại dữ liệu" (góc dưới thanh bên) để đọc lại. Ngoại lệ duy nhất: khi một lần đánh giá đang chạy, màn hình agent hỏi lại kết quả mỗi 3 giây.
- **Bí mật** (khóa đối tác, khóa manager, khóa provider, bí mật ký) hiện đúng một lần trong hộp thoại có nút Chép, đúng như API; đóng hộp thoại là không xem lại được.
- **Kiểm bằng trình duyệt thật** (không nằm trong lần chạy mặc định): `AWP_TEST_BROWSER=1 pytest tests/workforce/test_wf_console_browser.py` cần Chrome hoặc Edge trên máy (`AWP_TEST_BROWSER_PATH` để chỉ đường dẫn khác) và gói `websockets` (đã có trong venv); thêm `AWP_CONSOLE_SHOTS=<thư mục>` để lưu ảnh từng màn hình (ảnh của lần chạy 12/10/2026 ở `docs/console/`).
