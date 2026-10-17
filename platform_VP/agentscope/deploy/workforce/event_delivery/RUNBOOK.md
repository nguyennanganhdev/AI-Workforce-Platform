# Workforce async runtime runbook

Runbook này áp dụng cho Customer API, Provider Event API, durable worker và
SSE/history của platform. Platform không gọi webhook ngược sang đối tác.

## Điều kiện trước khi mở traffic

1. Backup PostgreSQL hoàn tất và restore rehearsal sang database tách biệt pass.
2. Alembic có đúng một head `0011_workforce_releases`.
3. API/worker chạy cùng image và commit; không trộn schema/code khác commit.
4. Redis chỉ dùng signal/fan-out. PostgreSQL là nguồn chuẩn cho inbox, workflow,
   checkpoint, public event và durable job.
5. Proxy SSE áp dụng [proxy.example.conf](proxy.example.conf); kiểm tra
   `X-Accel-Buffering: no`, heartbeat và `Last-Event-ID` qua proxy thật.
6. Metrics adapter phải xuất đúng tên metric trong
   [alerts.example.yml](alerts.example.yml). Không đưa ID người dùng, credential
   hoặc raw payload vào label/log.

## Deploy và migration

```powershell
$env:AGENTSCOPE_SQL_URL='<postgresql+asyncpg DSN>'
.\.venv\Scripts\python.exe scripts\workforce\check_phase_d_environment.py
.\.venv\Scripts\python.exe -m alembic -c src\agentscope\app\storage\_sql\_alembic\alembic.ini upgrade head
```

Migration phải additive. Không chạy runtime `create_all`, không downgrade xóa
inbox/workflow/event đang mở. Rollback ứng dụng dùng image cũ tương thích schema
mới và tắt nhận request mới bằng feature flag; worker/provider ingress vẫn chạy
để không mất event đã ACK.

## Backup và restore rehearsal

- Dùng `pg_dump --format=custom` trên database nguồn.
- Restore bằng `pg_restore --exit-on-error --no-owner --no-privileges` vào một
  database kiểm tra rỗng, tuyệt đối không restore đè database nguồn.
- Chạy `alembic current`, xác nhận `0011_workforce_releases`, sau đó chạy smoke
  Customer request/history và kiểm tra số workflow/inbox/public event.
- CI thực hiện rehearsal này trong PostgreSQL service trước khi tạo D7 report.

## Worker restart

1. Xác nhận process supervisor còn chạy và xem
   `workforce_worker_restarts_total` theo `error_type`.
2. Kiểm tra clock/DB connectivity trước khi restart process.
3. Không sửa trực tiếp trạng thái job. Lease hết hạn sẽ được worker khác reclaim;
   fencing token ngăn worker cũ commit.
4. Sau restart, theo dõi outcome `succeeded`, `retry_scheduled`, `lease_lost` và
   đối chiếu side effect bằng idempotency key.

## Durable job backlog

Phân loại theo `job_type`, `status`, `not_before`, `attempt`. Không retry mù
operation đã ra ngoài. Với trạng thái `unknown`, chạy reconciliation/status-query
theo protocol pin; nếu không có query capability thì chuyển xử lý thủ công.

## Provider event quarantine

Đối chiếu `receipt_id`, provider integration, protocol pin và error code. Các lỗi
binding/signature/schema/order không được route bằng LLM hoặc sửa owner. Sau khi
khắc phục cấu hình, replay bằng công cụ nội bộ theo đúng receipt/idempotency;
không yêu cầu đối tác đổi `external_event_id` để né dedupe.

## SSE reconnect và cursor hết hạn

Client reconnect bằng `Last-Event-ID`. Khi nhận `410 EVENT_CURSOR_EXPIRED`, tải
snapshot/history mới rồi mở stream từ cursor được trả. Không tăng retention bằng
cách giữ HTTP POST hoặc giữ model loop đang chạy.

## Rotate provider key

Tạo key mới, cho phép overlap ngắn, cập nhật secret store rồi test chữ ký mới.
Sau đó revoke key cũ và theo dõi `AUTHORIZATION_DENIED`. Rotation không đổi
provider integration, operation correlation hoặc idempotency namespace.

## Release và rollback

Checklist bắt buộc nằm tại [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md). Rollback
không đổi version/protocol pin của workflow đang mở. Archive/disable chỉ chặn
lựa chọn/call mới theo policy; không hard-delete version đang được retention
reader tham chiếu.
