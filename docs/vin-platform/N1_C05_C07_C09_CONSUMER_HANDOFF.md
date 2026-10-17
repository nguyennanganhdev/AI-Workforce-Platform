# N1 → N2: nối C05/C07/C09 trên UI/runtime hiện có

Ngày 18/10/2026. Contract `vin-platform-1`, event `vin-case-1`. Chỉ nối consumer trong file Người 2 sở hữu; không thay UI hay dựng authority mới.

## C05 — request/case riêng của khách hàng

| Consumer | API/helper đã có | Lưu ý |
| --- | --- | --- |
| Tạo yêu cầu | `POST /service-cases` → `{id,state,domain}` | Body `{link_id,idempotency_key,request}`. `request` theo resident Domain schema; không gửi owner/tenant/billing/manager |
| Đọc/list case | `GET /service-cases`, `GET /service-cases/{id}` | Chỉ owner. Kết quả detail chứa `data.domain`; `id` Platform khác `data.domain.id` của request Domain |
| Đối soát | `GET /service-cases/{id}?refresh=true` | Lưu projection SQL rồi mới gửi ACK hash/version sang Domain |
| Materialize | `POST /service-cases/{id}/tickets` | Body `{category_id,expected_version,idempotency_key}`; version lấy từ **Domain detail**, không dùng revision của row Platform |
| Intent | `POST /service-cases/{id}/decisions` | Body SourceIntent `{case_id,action,expected_version,payload,idempotency_key}`; refresh canonical trước consent. Chữ ký do backend tạo |
| Ảnh | `GET /service-cases/{id}/photos/{file_id}` | URL proxy cần auth, không bearer query. `photos` là intake, `result_photos` là ảnh staff sau ACK |

Runtime dùng `DomainAdapter(authority)` với context dựng từ verified user/session. `ticket_grant(context,case_id,ticket_id,tools)` là helper nội bộ, không trả bearer/config cho UI hoặc model. Cùng idempotency key + payload trả cùng kết quả; khác payload bị conflict. Khi mất phản hồi giữ correlation rồi retry đúng key, không tạo case/ticket thứ hai.

Case phải gắn vào hội thoại/Leader/team của chính khách hàng ở consumer Người 2. Không đưa `VIN_USER` vào manager scope, không route sang partner Leader BQL. Domain vẫn giữ staff queue/work orders/QC; status lấy từ projection canonical, không từ lời model. Người 2 quản lý session binding trong runtime của mình; nếu cần thêm field persistence trong case, gửi schema/CAS cụ thể cho N1.

## C07 — feed và publication là hai việc khác nhau

`GET /service-cases/{id}/events?after=0&limit=50&sync=true` trả `items`, `next_cursor`, `has_more`, `last_sequence`, `applied_sequence`, `sync_status`, `synced_at`, `canonical_version`.

- Mỗi item validate bằng `CaseEvent`: schema_version, event_id, case_id, sequence, canonical_version, event_type, occurred_at, audience, data. Owner/case/audience/sequence được backend kiểm.
- Lưu cursor **sau** khi consumer áp dụng các item; merge idempotent theo event_id trong case, không sắp lại theo thời gian nhận. Tiếp tục đọc khi has_more, giữ nhãn sync_pending khi chưa bắt kịp nguồn.
- `sync_status=applied` chỉ nói event page đã vào SQL projection; không thay ACK nội dung quyết định. Trước bật nút consent/ảnh kết quả, gọi refresh để backend ACK đúng canonical hash/version. HTTP accepted hoặc câu trả lời agent không tương đương applied/completed.
- Khi unlink/revoke, dừng tác vụ mới và xử lý lỗi Domain link, không fallback sang key/bootstrap token hoặc dữ liệu cư dân khác.

Fixture chạy xuyên Platform–Domain: `vinhome_Recident/services/vinhomes-api/tests/test_platform_customer_roundtrip.py`; staff/progress/photo/ACK: `test_platform_customers.py`. Dùng PYTHONPATH gồm src/tests của cả hai service. Chỉ PostgreSQL disposable + fake provider.

## C09 — job và execution context

**Bắt buộc upgrade tới `0023_personal_job_constraint` trước mount worker cá nhân.** `0022` một mình chưa đủ; rehearsal đã phát hiện CHECK cũ chỉ nhận scope/provider. Migration mới giữ dữ liệu/job cũ và thêm owner personal riêng; legacy workers bỏ qua personal jobs.

Public helper đã commit tại **`f52420d9`**:

```python
from agentscope.app.vin_platform._context import execution_scope

async def run_next(authority, worker_id, execute_job):
    jobs = authority.jobs
    job = await jobs.claim(worker_id, seconds=60)
    if job is None:
        return None
    context = await jobs.context_for(job)
    with execution_scope(context):
        result = await execute_job(job.job_type, job.payload["body"])
    await jobs.complete(job, worker_id, result)
    return job.job_id
```

`execute_job` trong ví dụ là callback runtime Người 2 cung cấp. Worker phải heartbeat trước hết lease, bắt lỗi theo contract và dùng fenced fail/checkpoint; không đánh dấu complete khi mới accepted. `context_for()` kiểm tenant/current role/eligibility/revision/workspace, trả purpose schedule/channel/delivery/builder. Gọi lại trước execution/delivery nếu claim đã chờ; không tự map actor/billing từ Discord sender hoặc payload.

`enqueue(context,kind,key,payload,not_before=None)` nhận schedule-run/channel-event/delivery/publish-batch. Payload cố định trong logical key; replay khác payload conflict. Model/business run không tự chạy lại sau crash; giữ OUTCOME_UNKNOWN để đối soát. Delivery là job riêng dùng body đã lưu, retry delivery không chạy lại model. Batch publish dùng `checkpoint` giữ manifest/repair cursor và `storage.activate_agents_batch` để activate atomically; staging workspace vẫn thuộc N2.

N1 chưa sửa consumer schedule/channel/router UI. Người 2 gửi field/state transition lệch qua handoff; N1 sửa storage/authority/migration, không đặt fallback fixture production. Không cần key model thật cho các gate tích hợp này.
