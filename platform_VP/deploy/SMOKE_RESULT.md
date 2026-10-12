# Kết quả chạy khói trên Docker (B4, và P5b ở mục 10)

Ngày chạy: 12/10/2026, khoảng 10:45 giờ Việt Nam (03:45 UTC; giờ trong log container là UTC). Máy: Windows 11, Docker Desktop 29.6.2 (linux/amd64), Compose v5.3.1. Project compose `awp-platform`, profile `demo`.

**Phải đọc trước khi tin kết quả.** Model trong lần chạy này là **model kịch bản** (`deploy/demo/fake_model.py`), MCP đối tác là **server mẫu** (`deploy/demo/fake_mcp.py`). Kết quả chứng minh: image build được và chạy được, migration chạy trên PostgreSQL thật trong container, các dịch vụ nối được với nhau, và bộ máy workflow (cổng đánh giá, kho tool, đồng ý của cư dân, sổ operation, sự kiện provider có chữ ký, đóng workflow, phục hồi sau khi tiến trình bị giết) hoạt động qua HTTP thật. Kết quả **không** chứng minh gì về model thật, MCP thật của đối tác hay hạ tầng production.

## 1. Image

| | |
|---|---|
| Tên | `awp-platform:0.1.0` |
| Image id | `sha256:7845e29d24da0a845b83ecdce009b232da2e6d609a5b5a3bff97c29b1cfb708c` |
| Kích thước nén (`docker image inspect`, `.Size`) | 129.061.060 byte (khoảng 129 MB) |
| Kích thước trên đĩa (`docker images`) | 606 MB (ảnh nền `python:3.12-slim` 191 MB; virtualenv `/opt/venv` 319 MB) |
| Build từ | nhánh `wip/platform-core-mvp`, commit `5feaf84` **cộng các thay đổi chưa commit trong cây làm việc lúc build** (console quản trị đang được xây song song, và sửa `awp/__main__.py` của B4) |
| Gói bên thứ ba | 101 gói, đúng phiên bản của venv phát triển, có hash (`deploy/requirements.lock`); `pip check` chạy trong lúc build: "No broken requirements found." |
| Chạy bằng | uid/gid 10001 (`awp`), không có pip trong virtualenv, không có `.env`, `*.db` hay `models.yaml` trong image |

Các gói nặng nhất trong virtualenv (MB): numpy 42 + numpy.libs 28, sqlalchemy 28, openai 26, anthropic 26, grpc 19, cryptography 16, asyncpg 15, agentscope 13, dashscope 11. Trừ sqlalchemy, asyncpg và cryptography (awp cần), đó là phụ thuộc **bắt buộc** của AgentScope (không phải extra); không bỏ được nếu không sửa AgentScope.

## 2. Khởi động nguội

Từ volume rỗng (`docker compose -p awp-platform --profile demo up -d` khi chưa có container hay volume nào của project):

```
cold start, empty volumes (postgres init + both migrations + api): up -d returned after 14584 ms; health 200 after 17775 ms
migrate: started 2026-10-12T03:45:11.372643863Z finished 2026-10-12T03:45:18.525508778Z exit 0
api: started 2026-10-12T03:45:18.754342055Z
2026-10-12T03:45:21.934785502Z INFO:     Application startup complete.
migrate-1  | at revision 0005_key_owner_run_guards
migrate-1  | AgentScope storage at its latest revision
migrate-1  | up to date at revision 0005_key_owner_run_guards
```

- Cả stack từ volume rỗng tới `GET /platform/v1/health` trả 200: **17,8 giây** (PostgreSQL khởi tạo hai database, job `migrate` chạy cả hai lịch sử migration rồi `--check`, rồi API).
- Job `migrate`: 7,2 giây. Riêng tiến trình API: từ lúc container bắt đầu tới "Application startup complete" là **3,2 giây**.
- Khởi động lại API trên database đã có: health trả 200 sau 1,2 giây (Docker tự khởi động lại theo `restart: unless-stopped`) và 3,1 giây (qua `compose up -d`, có chạy lại job `migrate`); xem mục 5.

Mỗi con số là một lần đo trên một máy phát triển đang chạy nhiều stack khác; không phải số đo hiệu năng.

## 3. Lần chạy A: toàn bộ các bước, không gián đoạn

Lệnh: `python smoke.py --docker`. Kết quả: **21/21 bước PASS**.

```
smoke run c4272f against http://127.0.0.1:8800  (2026-10-12T03:45:23Z)
[01/21] PASS  API is up and protected  (0.2s)
         200 ok; without a key the admin API answers 401
[02/21] PASS  A model is available  (0.0s)
         3 available: demo-strong, demo-standard, demo-cheap [scripted demo model]
[03/21] PASS  Leader profile (draft)  (0.0s)
         draft smoke_leader_c4272f v1
[04/21] PASS  Evaluation of the draft  (2.1s)
         run passed (3 cases)
[05/21] PASS  Release gate and publish  (0.1s)
         evaluation passed, published through the gate; history: ['create', 'eval', 'publish'], published by admin:ddb2f93b
[06/21] PASS  Client and partner key  (0.0s)
         client_bcadb552e1964c42b5dd03e2e821f5bd (sandbox), key 2eca9ac9a7b40823; the partner key does not open /platform
[07/21] PASS  Manager and manager key  (0.0s)
         mgr_cc9b869755954032ac4905c9e62b2b60, key ae140a4b2ebb082a; a manager key cannot create clients (403)
[08/21] PASS  Integration, provider key, signing key  (0.1s)
         intg_03f93c8fc15e4b43be6fc4b9e6b99736 with an API key and a signing key (needs AWP_SECRET_KEY to seal it)
[09/21] PASS  Route (pending)  (0.0s)
         route_f9f4923c0dd54fb1a7b814e56fc64e6a for SMOKE-C4272F: pending, revision 1
[10/21] PASS  MCP server: add, enable, discover  (0.1s)
         3 tools discovered at http://fake-mcp:8901/mcp: look-ups active, book_repair proposed and unusable; the header value is not readable back
[11/21] PASS  Activate the action tool  (0.0s)
         book_repair active: an action that needs the resident's consent, followed by provider events
[12/21] PASS  Partner confirms the route  (0.0s)
         before: 403 ROUTE_NOT_AUTHORIZED; after the partner's confirmation: active, revision 2
[13/21] PASS  start_workflow parks on consent  (0.6s)
         wf_55ec76ea258843c18f545d7746ff2997 is awaiting_approval / submit_approval; the same request again returned the same ids; nothing was sent to the partner yet
[14/21] PASS  Event stream (SSE)  (0.0s)
         SSE delivered 4 events with cursors: ['request.accepted', 'workflow.status_changed', 'workflow.status_changed', 'approval.required']
[15/21] PASS  Snapshot shows the approval  (0.0s)
         approval appr_1240b8016c3f417192a03db851e69439 pending: {"text": "Book a repair visit for monday", "tool": "book_repair", "arguments": {"slot": "monday"}}; the manager's key sees this workflow only
[16/21] PASS  Resident approves; tool runs  (0.6s)
         approved (202); the tool ran and the workflow is waiting_external_event; the same decision again is answered the same
[17/21] PASS  One pending operation  (0.0s)
         one operation, pending, reference cr_2450c72871efcc5a707ee5c304bbe6c9, partner job JOB-1; the leader said: 'I asked for the visit on Monday; it is pending.'
[18/21] PASS  Signed provider events  (1.2s)
         wrong signature: 401; job.assigned applied without waking the leader; job.completed applied
[19/21] PASS  Leader asks to confirm  (0.1s)
         awaiting_confirmation / confirm_close; the leader asked: 'The partner reports the work finished. Is everything right?'
[20/21] PASS  Partner closes the workflow  (0.1s)
         closed by the partner after the resident confirmed
[21/21] PASS  Nothing happened twice  (0.5s)
         1 operation (completed), 1 approval (approved), 2 receipts (applied), 3 distinct messages to the resident, one approval.required/approval.resolved/workflow.closed; the same event again: 202 duplicate; the sample MCP server was called exactly once with this reference and holds one job for it (JOB-1); all its calls since it started, every workflow together: {'book_repair': 1}

SMOKE PASS: 21 of 21 steps passed (scripted demo model)
```

Ghi chú về bước 4 và 5: bản nháp leader được **đánh giá thật** trong sandbox (3 ca mặc định của platform, chạy bằng model kịch bản) và đạt, nên được phát hành **qua cổng**, không dùng ghi đè. Đường ghi đè (`override_reason`, sau khi kiểm rằng `publish` thường bị từ chối `409 EVAL_REQUIRED`) có trong script cho trường hợp đánh giá không đạt; **lần chạy này không đi qua nó, nên nhánh đó của script chưa được chạy thật.**

## 4. `docker compose ps` sau lần chạy A

```
NAME                        IMAGE                COMMAND                  SERVICE      CREATED          STATUS                      PORTS
awp-platform-api-1          awp-platform:0.1.0   "python -m awp"          api          24 seconds ago   Up 10 seconds (healthy)     127.0.0.1:8800->8800/tcp
awp-platform-fake-mcp-1     awp-platform:0.1.0   "python /demo/fake_m…"   fake-mcp     25 seconds ago   Up 23 seconds (healthy)     8800/tcp
awp-platform-fake-model-1   awp-platform:0.1.0   "python /demo/fake_m…"   fake-model   25 seconds ago   Up 23 seconds (healthy)     8800/tcp
awp-platform-migrate-1      awp-platform:0.1.0   "/bin/sh -c 'python …"   migrate      24 seconds ago   Exited (0) 10 seconds ago   
awp-platform-postgres-1     postgres:16-alpine   "docker-entrypoint.s…"   postgres     25 seconds ago   Up 23 seconds (healthy)     127.0.0.1:5590->5432/tcp
```

Cột PORTS của `fake-mcp` và `fake-model` ghi `8800/tcp` vì chúng chạy cùng image (dòng `EXPOSE`); không cổng nào của chúng được publish ra máy chủ. Chỉ có `127.0.0.1:8800` (API) và `127.0.0.1:5590` (PostgreSQL).

## 5. Lần chạy B: giết tiến trình API hai lần giữa một workflow

Một workflow mới (run `50a3e1`). Bản ghi dưới đây là nguyên văn; lệnh đầu chỉ giữ 6 dòng cuối (13 bước trước đó PASS như lần chạy A).

```
$ python smoke.py --until approval
[14/21] PASS  Event stream (SSE)  (0.0s)
         SSE delivered 4 events with cursors: ['request.accepted', 'workflow.status_changed', 'workflow.status_changed', 'approval.required']
[15/21] PASS  Snapshot shows the approval  (0.0s)
         approval appr_72a95c818071402395bf964e23f693d8 pending: {"text": "Book a repair visit for monday", "tool": "book_repair", "arguments": {"slot": "monday"}}; the manager's key sees this workflow only

PAUSED after step 'approval' (state in .smoke_state.json; it holds this run's keys). Go on with: python smoke.py --resume

$ # kill 1: SIGKILL to the Python process INSIDE the container (the container dies; the restart policy brings it back)
kill -9 pid 7 (python -m awp)
api container: status=running RestartCount=1 started=2026-10-12T03:45:32.756740572Z

$ python smoke.py --resume --until waiting
smoke run 50a3e1 against http://127.0.0.1:8800  (2026-10-12T03:45:34Z)
RESUME after step 'approval': API healthy after 1.2s; workflow wf_a1f35b16f51c44588ad24bfd097f3282 is awaiting_approval (revision 3)
[16/21] PASS  Resident approves; tool runs  (1.1s)
         approved (202); the tool ran and the workflow is waiting_external_event; the same decision again is answered the same
[17/21] PASS  One pending operation  (0.0s)
         one operation, pending, reference cr_83adb7d375bd62f553e929b8b129c6dd, partner job JOB-2; the leader said: 'I asked for the visit on Monday; it is pending.'

PAUSED after step 'waiting' (state in .smoke_state.json; it holds this run's keys). Go on with: python smoke.py --resume

$ # kill 2: docker kill -s KILL on the api container only, then compose up -d
$ docker kill -s KILL awp-platform-api-1
awp-platform-api-1
api container: status=exited exit=137
$ docker compose -p awp-platform --profile demo up -d
 Container awp-platform-migrate-1 Waiting 
 Container awp-platform-migrate-1 Exited 
 Container awp-platform-api-1 Starting 
 Container awp-platform-api-1 Started 

$ python smoke.py --resume --docker
smoke run 50a3e1 against http://127.0.0.1:8800  (2026-10-12T03:45:48Z)
RESUME after step 'waiting': API healthy after 3.1s; workflow wf_a1f35b16f51c44588ad24bfd097f3282 is waiting_external_event (revision 6)
[18/21] PASS  Signed provider events  (1.1s)
         wrong signature: 401; job.assigned applied without waking the leader; job.completed applied
[19/21] PASS  Leader asks to confirm  (0.6s)
         awaiting_confirmation / confirm_close; the leader asked: 'The partner reports the work finished. Is everything right?'
[20/21] PASS  Partner closes the workflow  (0.1s)
         closed by the partner after the resident confirmed
[21/21] PASS  Nothing happened twice  (0.5s)
         1 operation (completed), 1 approval (approved), 2 receipts (applied), 3 distinct messages to the resident, one approval.required/approval.resolved/workflow.closed; the same event again: 202 duplicate; the sample MCP server was called exactly once with this reference and holds one job for it (JOB-2); all its calls since it started, every workflow together: {'book_repair': 2}

SMOKE PASS: 21 of 21 steps passed (scripted demo model)

$ docker compose -p awp-platform --profile demo ps -a
NAME                        IMAGE                COMMAND                  SERVICE      CREATED          STATUS                     PORTS
awp-platform-api-1          awp-platform:0.1.0   "python -m awp"          api          49 seconds ago   Up 6 seconds (healthy)     127.0.0.1:8800->8800/tcp
awp-platform-fake-mcp-1     awp-platform:0.1.0   "python /demo/fake_m…"   fake-mcp     50 seconds ago   Up 48 seconds (healthy)    8800/tcp
awp-platform-fake-model-1   awp-platform:0.1.0   "python /demo/fake_m…"   fake-model   50 seconds ago   Up 48 seconds (healthy)    8800/tcp
awp-platform-migrate-1      awp-platform:0.1.0   "/bin/sh -c 'python …"   migrate      49 seconds ago   Exited (0) 6 seconds ago   
awp-platform-postgres-1     postgres:16-alpine   "docker-entrypoint.s…"   postgres     50 seconds ago   Up 48 seconds (healthy)    127.0.0.1:5590->5432/tcp
```

Lệnh giết lần 1 (chạy trong container, vì image không có `pkill`):

```
docker exec awp-platform-api-1 python -c "
import os,signal
for p in os.listdir('/proc'):
    if p.isdigit() and int(p)!=os.getpid() and open(f'/proc/{p}/cmdline','rb').read().startswith(b'python\0-m\0awp'):
        print('kill -9 pid', p, '(python -m awp)'); os.kill(int(p), signal.SIGKILL)"
```

Điều bản ghi cho thấy:

1. **Giết lần 1** (`kill -9` vào tiến trình `python -m awp` **bên trong** container, lúc workflow đang `awaiting_approval`, chưa có gì gửi sang đối tác): container chết, Docker tự khởi động lại theo `restart: unless-stopped` (`RestartCount=1`), health trả 200 sau 1,2 giây. Workflow vẫn `awaiting_approval`, revision 3. Cư dân đồng ý **sau** khi khởi động lại: tool chạy, workflow sang `waiting_external_event`, đúng một operation `pending`.
2. **Giết lần 2** (`docker kill -s KILL` vào riêng container `api`, lúc workflow đang `waiting_external_event` với một operation đang chờ đối tác), rồi `docker compose up -d` (job `migrate` chạy lại, không đổi gì). Workflow vẫn `waiting_external_event`, revision 6. Sự kiện provider có chữ ký gửi **sau** khi khởi động lại được áp, leader hỏi xác nhận, đối tác đóng workflow.
3. **Không có gì bị lặp**: 1 operation (`completed`), 1 approval (`approved`), 2 biên nhận (`applied`), 3 tin nhắn khác nhau tới cư dân, mỗi loại `approval.required`/`approval.resolved`/`workflow.closed` đúng một lần; server MCP mẫu được gọi **đúng một lần** với `client_reference` của workflow này và giữ đúng một job cho nó (`JOB-2`). Con số `{'book_repair': 2}` là tổng của server mẫu từ lúc nó khởi động: một lần của lần chạy A (`JOB-1`), một lần của lần chạy B (`JOB-2`).

**Giới hạn của phép thử này (nói thẳng).** Cả hai lần giết xảy ra khi workflow đang **đỗ** (chờ cư dân, chờ đối tác): không có lượt nào của agent đang chạy và không có lời gọi MCP nào đang dở. Giết giữa một lượt đang chạy hoặc giữa một lời gọi tool **không** được thử ở đây; các trường hợp đó chỉ có trong bộ test của repo dưới dạng crash mô phỏng trong một tiến trình, không phải kill thật trên container. Mỗi kịch bản giết chỉ chạy một lần.

## 6. Tắt êm (SIGTERM)

Đo bằng `docker compose stop api` (SIGTERM, `stop_grace_period: 45s`), mỗi ô một lần đo:

| Tình huống | Trước khi sửa | Sau khi sửa `awp/__main__.py` |
|---|---|---|
| Không có kết nối SSE nào mở | (không đo) | 0,7 giây, log "Application shutdown complete", mã thoát 143 |
| Có một kết nối SSE đang mở | **45,6 giây rồi bị SIGKILL** (mã thoát 137), phần tắt của ứng dụng không chạy | 20,7 giây, log "Application shutdown complete", mã thoát 143 |

Nguyên nhân: uvicorn chờ mọi request đang mở kết thúc, mà một luồng SSE không tự kết thúc. Sửa: `uvicorn.run(..., timeout_graceful_shutdown=AWP_SHUTDOWN_SECONDS hoặc 20)`. Sau thời gian đó các request còn mở bị hủy (client SSE nối lại bằng cursor) và phần tắt của ứng dụng chạy. Mã thoát 143 (128 + SIGTERM) là cách uvicorn kết thúc sau khi tắt xong, không phải lỗi. Còn lại: mỗi lần dừng khi có luồng SSE mở mất 20 giây và để lại một traceback `CancelledError` trong log cho mỗi luồng.

## 7. Những thứ khác đã chạy thật

- `python init_env.py --demo` tạo `deploy/.env`; chạy lần hai thoát mã 1 và **không ghi đè**. `git check-ignore` xác nhận `deploy/.env` bị bỏ qua. Chế độ không `--demo` cũng sinh được tệp (không còn placeholder, `AWP_MCP_ALLOW_PRIVATE=0`, chép `models.example.yaml` thành `deploy/models.yaml`), nhưng **chưa có stack nào được khởi động bằng tệp đó** (cần khóa model thật).
- `docker compose --profile demo --profile not-wired config --quiet`: hợp lệ.
- Profile `not-wired`: `redis` và `minio` khởi động và báo `healthy` (MinIO ở `127.0.0.1:9190/9191`). **Không có gì trong platform nối tới chúng**; phép thử này chỉ nói rằng hai container tự chạy được.
- Sao lưu: `pg_dump -Fc` cho cả `awp` và `awp_storage` qua `docker compose exec` chạy được (bản dump của `awp` liệt kê 37 mục TABLE DATA); nén volume `awp-platform_workspaces` bằng một container tạm chạy được. **Khôi phục (`pg_restore` vào một stack mới) chưa được thử.**
- `python -m awp migrate --check` trong container API: "up to date at revision 0005_key_owner_run_guards".
- `docs/openapi.json` xuất từ container đang chạy (`GET /openapi.json` với khóa admin; không khóa trả 401): OpenAPI 3.1.0, 146 đường dẫn (11 dưới `/workforce`, 61 dưới `/platform`, còn lại là API của AgentScope). Trường `info.version` ghi `2.0.10dev`: đó là phiên bản AgentScope, không phải phiên bản của hợp đồng đối tác.
- Console: `GET /console` trả 200 từ container (không kiểm gì thêm ở đây; console thuộc phần việc khác).

Chưa chạy: nâng cấp và rollback bằng tag image (chỉ có một tag), smoke với model thật, smoke với nhiều hơn một bản sao API.

## 8. Dọn dẹp

Sau khi ghi kết quả: `docker compose -p awp-platform --profile demo --profile not-wired down -v`. Kiểm lại: không còn container, volume hay network nào tên `awp-platform*`; các cổng 8800, 5590, 9190, 9191 trống; `deploy/.env` của lần chạy (bí mật của một database đã xóa) đã được xóa. Image `awp-platform:0.1.0` được giữ lại. Không container, volume, network hay image nào của các stack khác trên máy bị dừng, xóa, khởi động lại hay sửa.

## 9. Chạy lại

```
cd platform_VP/deploy
python init_env.py --demo
docker compose build
docker compose --profile demo up -d
python smoke.py --docker
docker compose --profile demo down -v      # -v xóa cả dữ liệu; bỏ -v để giữ
```

## 10. P5b: Redis đã nối và hai bản sao API (chạy lại 12/10/2026)

Các mục 1 đến 9 ở trên là lần chạy của bước B4 (image `0.1.0`, một bản sao, chưa có Redis) và được giữ nguyên làm lịch sử. Mục này là lần chạy của slice P5b trên mã có Redis, hai bản sao và phục hồi sau khi một bản sao bị giết. Vẫn là **model kịch bản** và **MCP mẫu**: không nói gì về model thật hay đối tác thật.

| | |
|---|---|
| Image | `awp-platform:0.2.0`, id `sha256:eed4fad8b81ae9671e907729f879684de15c19a6b01a1f130df67db1a23734ad`, 130.675.117 byte nén (614 MB trên đĩa); 102 gói bên thứ ba (thêm `redis` 8.1.0) |
| Build từ | nhánh `wip/platform-core-mvp`, cây làm việc của slice P5b ngay trước commit của nó |
| Stack | `docker compose --profile demo --profile two up -d`: `postgres`, `redis` (có mật khẩu, `appendonly yes`), `migrate`, `api` (127.0.0.1:8800), `api2` (127.0.0.1:8801), `fake-model`, `fake-mcp` |
| Migration | `at revision 0006_operation_node`, `AgentScope storage at its latest revision`, `up to date at revision 0006_operation_node` |
| Khởi động nguội | từ volume rỗng tới `GET /platform/v1/health` trả 200: 17 giây (một lần đo, máy đang chạy cả bộ test) |
| Cấu hình | mặc định của `deploy/.env.example` (`AWP_WF_LEASE_SECONDS` = 60) |

```
NAME                        IMAGE                STATUS                      PORTS
awp-platform-api-1          awp-platform:0.2.0   Up 10 seconds (healthy)     127.0.0.1:8800->8800/tcp
awp-platform-api2-1         awp-platform:0.2.0   Up 10 seconds (healthy)     127.0.0.1:8801->8800/tcp
awp-platform-fake-mcp-1     awp-platform:0.2.0   Up 23 seconds (healthy)     8800/tcp
awp-platform-fake-model-1   awp-platform:0.2.0   Up 23 seconds (healthy)     8800/tcp
awp-platform-migrate-1      awp-platform:0.2.0   Exited (0) 11 seconds ago   
awp-platform-postgres-1     postgres:16-alpine   Up 23 seconds (healthy)     127.0.0.1:5590->5432/tcp
awp-platform-redis-1        redis:7-alpine       Up 23 seconds (healthy)     6379/tcp
```

### 10.1 Lần chạy A: cả 22 bước qua bản sao 1, luồng SSE đọc từ bản sao 2

Lệnh: `python smoke.py --docker --sse-base http://127.0.0.1:8801`. **22/22 PASS**. Bước 2 là bước mới (console lấy từ container); bước 15 đọc SSE từ bản sao **không** nhận request nào của workflow đó.

```
smoke run b0233d against http://127.0.0.1:8800  (2026-10-12T05:12:57Z)
[01/22] PASS  API is up and protected  (0.0s)
         200 ok; without a key the admin API answers 401
[02/22] PASS  Admin console is served  (0.0s)
         GET /console: 200 text/html (567 bytes) with its CSP; app.js 97351 and app.css 11503 bytes from the container; no key needed, nothing loaded from elsewhere
[03/22] PASS  A model is available  (0.0s)
         3 available: demo-strong, demo-standard, demo-cheap [scripted demo model]
[04/22] PASS  Leader profile (draft)  (0.0s)
         draft smoke_leader_b0233d v1
[05/22] PASS  Evaluation of the draft  (2.1s)
         run passed (3 cases)
[06/22] PASS  Release gate and publish  (0.0s)
         evaluation passed, published through the gate; history: ['create', 'eval', 'publish'], published by admin:80773f07
[07/22] PASS  Client and partner key  (0.1s)
         client_a3ea47ec539a4b11aee01d80f4ea7437 (sandbox), key 20b09f3c3072675f; the partner key does not open /platform
[08/22] PASS  Manager and manager key  (0.1s)
         mgr_312c1e664a924b3a968ac7bacf32d891, key ca9a43f6acd89062; a manager key cannot create clients (403)
[09/22] PASS  Integration, provider key, signing key  (0.0s)
         intg_16a0f3c0a5434c2a9ff5fb29883738a5 with an API key and a signing key (needs AWP_SECRET_KEY to seal it)
[10/22] PASS  Route (pending)  (0.0s)
         route_36bdee74a7a94a38b278bc35d5906821 for SMOKE-B0233D: pending, revision 1
[11/22] PASS  MCP server: add, enable, discover  (0.1s)
         3 tools discovered at http://fake-mcp:8901/mcp: look-ups active, book_repair proposed and unusable; the header value is not readable back
[12/22] PASS  Activate the action tool  (0.0s)
         book_repair active: an action that needs the resident's consent, followed by provider events, safe to send again with the same reference
[13/22] PASS  Partner confirms the route  (0.0s)
         before: 403 ROUTE_NOT_AUTHORIZED; after the partner's confirmation: active, revision 2
[14/22] PASS  start_workflow parks on consent  (0.5s)
         wf_c26af8d64e7649cb9021ad393a1e6d12 is awaiting_approval / submit_approval; the same request again returned the same ids; nothing was sent to the partner yet
[15/22] PASS  Event stream (SSE)  (0.1s)
         SSE delivered 4 events with cursors (read from http://127.0.0.1:8801, the requests went to http://127.0.0.1:8800): ['request.accepted', 'workflow.status_changed', 'workflow.status_changed', 'approval.required']
[16/22] PASS  Snapshot shows the approval  (0.0s)
         approval appr_06ddb7c980ae4f5989317d9a0c7fd153 pending: {"text": "Book a repair visit for monday", "tool": "book_repair", "arguments": {"slot": "monday"}}; the manager's key sees this workflow only
[17/22] PASS  Resident approves; tool runs  (1.1s)
         approved (202); the tool ran and the workflow is waiting_external_event; the same decision again is answered the same
[18/22] PASS  One pending operation  (0.0s)
         one operation, pending, reference cr_c7bbf45749064d0964404a13b9efa6d4, partner job JOB-1; the leader said: 'I asked for the visit on Monday; it is pending.'
[19/22] PASS  Signed provider events  (1.2s)
         wrong signature: 401; job.assigned applied without waking the leader; job.completed applied
[20/22] PASS  Leader asks to confirm  (0.0s)
         awaiting_confirmation / confirm_close; the leader asked: 'The partner reports the work finished. Is everything right?'
[21/22] PASS  Partner closes the workflow  (0.3s)
         closed by the partner after the resident confirmed
[22/22] PASS  Nothing happened twice  (0.8s)
         1 operation (completed), 1 approval (approved), 2 receipts (applied), 3 distinct messages to the resident, one approval.required/approval.resolved/workflow.closed; the same event again: 202 duplicate; the sample MCP server was called exactly once with this reference and holds one job for it (JOB-1); all its calls since it started, every workflow together: {'book_repair': 1}

SMOKE PASS: 22 of 22 steps passed (scripted demo model)
```

### 10.2 Lần chạy B: giết bản sao đang chạy lời gọi đã duyệt

Lệnh: `python smoke.py --docker --sse-base http://127.0.0.1:8801 --failover-to http://127.0.0.1:8800 --kill awp-platform-api2-1` (trước đó `docker update --restart no awp-platform-api2-1` để bản sao bị giết **không** tự lên lại). Ở bước 17 script giữ câu trả lời của MCP mẫu, gửi quyết định, chờ tới khi lời gọi `book_repair` đang treo ở đối tác, rồi `docker kill -s KILL`. Trong lần này lượt của agent đang chạy ở chính bản sao bị giết. **22/22 PASS**; các bước khác giống lần A.

```
[15/22] PASS  Event stream (SSE)  (0.0s)
         SSE delivered 4 events with cursors (read from http://127.0.0.1:8801, the requests went to http://127.0.0.1:8800): ['request.accepted', 'workflow.status_changed', 'workflow.status_changed', 'approval.required']
[17/22] PASS  Resident approves; tool runs  (54.8s)
         approved (202); awp-platform-api2-1 was killed (SIGKILL) inside the approved call to the partner; http://127.0.0.1:8800 took the workflow over 53s later (it waits for the dead process's lease) instead of http://127.0.0.1:8800 and the workflow is waiting_external_event; the same decision again is answered the same
[18/22] PASS  One pending operation  (0.1s)
         one operation, pending, reference cr_41d2334abb83c770bd4ac55df92ce543, partner job JOB-2; the leader said: 'Your request for a visit is being handled; I will tell you when it changes.'
[19/22] PASS  Signed provider events  (0.7s)
         wrong signature: 401; job.assigned applied without waking the leader; job.completed applied
[20/22] PASS  Leader asks to confirm  (0.0s)
         awaiting_confirmation / confirm_close; the leader asked: 'The partner reports the work finished. Is everything right?'
[21/22] PASS  Partner closes the workflow  (0.1s)
         closed by the partner after the resident confirmed
[22/22] PASS  Nothing happened twice  (0.7s)
         1 operation (completed), 1 approval (approved), 2 receipts (applied), 3 distinct messages to the resident, one approval.required/approval.resolved/workflow.closed; the same event again: 202 duplicate; the sample MCP server was called twice with this reference (the second time by the replica that took over) and made ONE job for it (JOB-2); all its calls since it started, every workflow together: {'book_repair': 3}

SMOKE PASS: 22 of 22 steps passed (scripted demo model)
```

Log của bản sao còn sống (`api`), nguyên văn:

```
api-1  | node n9fe85f95ed9e4708 is gone: released 1 session lock(s) it left
api-1  | approval appr_7e0c990eef594df3b2072359e87dee1b: its agent was handed the answer by a process that died; it is handed over again
api-1  | node(s) n9fe85f95ed9e4708 did not say they live for a whole lease and were taken over
api-1  | workflow wf_97389d97f4eb46e2a02894cb5e200553: 1 turn(s) were left running and are closed
```

```
NAME                        STATUS                          PORTS
awp-platform-api-1          Up About a minute (healthy)     127.0.0.1:8800->8800/tcp
awp-platform-api2-1         Exited (137) 55 seconds ago     
awp-platform-fake-mcp-1     Up About a minute (healthy)     8800/tcp
awp-platform-fake-model-1   Up About a minute (healthy)     8800/tcp
awp-platform-migrate-1      Exited (0) About a minute ago   
awp-platform-postgres-1     Up About a minute (healthy)     127.0.0.1:5590->5432/tcp
awp-platform-redis-1        Up About a minute (healthy)     6379/tcp
```

Điều bản ghi cho thấy: bản sao còn sống chờ lease của bản sao chết hết hạn (53 giây trong lần này), xóa khóa phiên nó để lại trong Redis, đóng lượt dở, đưa quyết định lại cho agent còn đang đỗ, và hỏi lại đối tác **với cùng `client_reference`**. Đối tác nhận hai lời gọi với reference đó và giữ **một** job. Cư dân nhận ba tin khác nhau, không tin nào lặp; mỗi loại `approval.required`/`approval.resolved`/`workflow.closed` đúng một lần.

### 10.3 Lần chạy C: giết bản sao nhận request, lượt chạy ở bản sao kia

Lệnh: `python smoke.py --docker --sse-base http://127.0.0.1:8801 --failover-to http://127.0.0.1:8801 --kill awp-platform-api-1` (sau khi `docker start awp-platform-api2-1`; `api` đặt `--restart no`). **22/22 PASS**.

```
[15/22] PASS  Event stream (SSE)  (0.1s)
         SSE delivered 4 events with cursors (read from http://127.0.0.1:8801, the requests went to http://127.0.0.1:8800): ['request.accepted', 'workflow.status_changed', 'workflow.status_changed', 'approval.required']
[17/22] PASS  Resident approves; tool runs  (61.3s)
         approved (202); awp-platform-api-1 was killed (SIGKILL) inside the approved call to the partner; http://127.0.0.1:8801 took the workflow over 60s later (it waits for the dead process's lease) instead of http://127.0.0.1:8800 and the workflow is waiting_external_event; the same decision again is answered the same
[18/22] PASS  One pending operation  (0.1s)
         one operation, pending, reference cr_1569f3c2cdc414a9bf384e43c94713b8, partner job JOB-3; the leader said: 'I asked for the visit on Monday; it is pending.'
[22/22] PASS  Nothing happened twice  (0.7s)
         1 operation (completed), 1 approval (approved), 2 receipts (applied), 3 distinct messages to the resident, one approval.required/approval.resolved/workflow.closed; the same event again: 202 duplicate; the sample MCP server was called exactly once with this reference and holds one job for it (the call was running in the replica that survived; the killed one held the job) (JOB-3); all its calls since it started, every workflow together: {'book_repair': 4}

SMOKE PASS: 22 of 22 steps passed (scripted demo model)
```

```
api2-1  | node(s) n14150754b6794e42 did not say they live for a whole lease and were taken over
```

```
NAME                        STATUS                            PORTS
awp-platform-api-1          Exited (137) About a minute ago   
awp-platform-api2-1         Up About a minute (healthy)       127.0.0.1:8801->8800/tcp
awp-platform-fake-mcp-1     Up 2 minutes (healthy)            8800/tcp
awp-platform-fake-model-1   Up 2 minutes (healthy)            8800/tcp
awp-platform-migrate-1      Exited (0) 2 minutes ago          
awp-platform-postgres-1     Up 2 minutes (healthy)            127.0.0.1:5590->5432/tcp
awp-platform-redis-1        Up 2 minutes (healthy)            6379/tcp
```

Lần này bản sao bị giết là bản giữ job, còn lời gọi đối tác đang chạy ở bản sao kia (quyết định đánh thức agent qua hàng đợi của AgentScope, bản sao nào lấy được thì chạy): lời gọi cứ thế xong, đối tác nhận đúng một lời gọi, và job mồ côi được bản sao còn sống đóng sau khi lease hết.

### 10.4 Giới hạn của phép thử này (nói thẳng)

- Bản sao nào chạy lượt sau một quyết định **không điều khiển được** từ ngoài; lần B và lần C rơi vào hai nhánh khác nhau vì chọn giết hai container khác nhau, không phải vì script ép được. `smoke.py` chấp nhận cả hai nhánh và ghi nhánh nào đã xảy ra. Nhánh xác định (giết đúng tiến trình đang chạy lượt) nằm ở bộ test `multiproc`.
- Một lần chạy đầu của lần B (image trước khi sửa) **đã đỏ ở bước 18** ("the leader said nothing to the resident"): bản sao giữ job còn sống, bản sao chạy lượt chết, và job kết thúc trong khi agent vẫn đỗ. Đó là lỗi thật, đã sửa trong `resume.run` (xem `docs/WORKFORCE_V1_QUYET_DINH.md`, mục P5b); các bản ghi ở trên là của image sau khi sửa.
- Chỉ giết ở một điểm (trong lời gọi đã duyệt). Giữa lời gọi model, giữa commit và giao SSE, và các điểm khác: bộ test `multiproc`, không phải Docker.
- Không thử: giết Redis, giết PostgreSQL, hơn hai bản sao, hai máy, model thật.
- `docs/openapi.json` xuất lại từ container `0.2.0` (`GET /openapi.json` với khóa admin): 146 đường dẫn (11 dưới `/workforce`, 61 dưới `/platform`), không thêm bớt đường dẫn nào so với bản trước.

### 10.5 Dọn dẹp

`docker compose --profile demo --profile two --profile not-wired down -v`, xóa `deploy/.env` của lần chạy. Kiểm lại: không còn container, volume hay network nào tên `awp-platform*`. Image `awp-platform:0.2.0` được giữ lại; `awp-platform:0.1.0` đã bị lần build đầu của slice này ghi đè và được dựng lại từ mã đã commit của B4 (id mới, không còn là `7845e29d…` ở mục 1).
