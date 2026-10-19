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

Nested request Vinhomes có [schema + example xuất từ DTO thật](vinhomes-create-request-v1.schema.json): `apartmentId`, `description`, `location.description`, `photoIds`. Domain hiện cho tối đa **3 ảnh/request**, không suy từ đề xuất 4 ảnh của vision profile. Consumer gửi photo ID đã upload/được cấp, không URL hoặc resident ID tự nhập. Test `test_platform_request_schema.py` chặn drift giữa fixture này và CreateRequest production.

Case phải gắn vào hội thoại/Leader/team của chính khách hàng ở consumer Người 2. Không đưa `VIN_USER` vào manager scope, không route sang partner Leader BQL. Domain vẫn giữ staff queue/work orders/QC; status lấy từ projection canonical, không từ lời model. Người 2 quản lý session binding trong runtime của mình; nếu cần thêm field persistence trong case, gửi schema/CAS cụ thể cho N1.

## C07 — feed và publication là hai việc khác nhau

### Bổ sung phương án riêng — 18/10

`GET /service-cases/{id}?refresh=true` trả **`data.domain.plans[]`**. Mỗi item theo `CustomerPlan`: `id,title,status,version,estimatedAmount,steps,canDecide`. Đây là phương án `vh_ticket_plans`, **khác** work-order `pending_decisions[]`. Dùng lại resident-safe projection của Domain: chỉ phương án đã đến bước cư dân hoặc lịch sử đã công khai; không trả proposal thô, management note, actor hay cấu hình nội bộ. Phương án chờ cư dân làm `service_status=waiting_for_customer`, `next_action=review_current_decision`.

Consumer chỉ mở lựa chọn khi `canDecide=true` và `status=resident_pending`, sau refresh/ACK. Gửi `SourceIntent.action="plan-decision"`; outer `expected_version=data.domain.canonical_version`, còn `payload={plan_id:plan.id,expectedVersion:plan.version,decision:"approve"|"reject",note:"..."}` theo `PlanDecisionPayload`. **Không thay plan version bằng case/ticket version.** Note bắt buộc 1–2000 ký tự sau trim. Dùng idempotency key cố định cho cùng lần bấm; payload thay đổi thì tạo key mới. Không gọi endpoint quyết định từ model.

Danh sách/nội dung/version phương án được đưa vào `projection_hash`, vì vậy đổi phương án làm ACK cũ hết hiệu lực. Domain vẫn kiểm signed intent, owner, liên kết plan→case, cả hai version và receipt replay. Schema `CustomerPlan`/`PlanDecisionPayload` có trong `contracts-v1.schema.json` và OpenAPI components; fixture: [`fixtures/c07-plan-decision-v1.json`](fixtures/c07-plan-decision-v1.json).

Kiểm tra mới: Platform Python 3.11 Linux **2 PASS / 0 SKIP**; Domain PostgreSQL với restricted role, approve/reject + stale plan/case version + ACK/hash/replay và regression khách hàng **6 PASS / 0 SKIP / 0 FAIL / 0 ERROR**. Test đầu dùng admin thiếu management scope đã FAIL; fixture chuyển sang actor management Domain có sẵn, không nới quyền production. Test bắt lỗi Decimal trong stale-case error serialization, đã sửa về integer để trả 409 đúng. Không dùng key model thật; chưa chạy lại E2E browser cho slice này. Người 2 nối `decision_actions`/thẻ hiện có, N1 không sửa file consumer.

R04 contract clarification: `pending_decisions[].version` is the **ticket version** consumed by the existing Domain `ResidentApprovalDecision.version`, also exposed as `ticket_version`. The production work_approvals table has no integer revision column. Do not invent an approval-row revision or substitute the case canonical_version; the signed outer expected_version remains the case version. The refreshed projection/hash includes request_detail and this version. N2's existing decision_actions can consume this explicit `version` field. Current Domain decision API locks the ticket and rejects a stale ticket version; no new approval authority/bridge is introduced.

`GET /service-cases/{id}/events?after=0&limit=50&sync=true` trả `items`, `next_cursor`, `has_more`, `last_sequence`, `applied_sequence`, `sync_status`, `synced_at`, `canonical_version`.

- Mỗi item validate bằng `CaseEvent`: schema_version, event_id, case_id, sequence, canonical_version, event_type, occurred_at, audience, data. Owner/case/audience/sequence được backend kiểm.
- Lưu cursor **sau** khi consumer áp dụng các item; merge idempotent theo event_id trong case, không sắp lại theo thời gian nhận. Tiếp tục đọc khi has_more, giữ nhãn sync_pending khi chưa bắt kịp nguồn.
- `sync_status=applied` chỉ nói event page đã vào SQL projection; không thay ACK nội dung quyết định. Trước bật nút consent/ảnh kết quả, gọi refresh để backend ACK đúng canonical hash/version. HTTP accepted hoặc câu trả lời agent không tương đương applied/completed.
- Khi unlink/revoke, dừng tác vụ mới và xử lý lỗi Domain link, không fallback sang key/bootstrap token hoặc dữ liệu cư dân khác.

Fixture chạy xuyên Platform–Domain: `vinhome_Recident/services/vinhomes-api/tests/test_platform_customer_roundtrip.py`; staff/progress/photo/ACK: `test_platform_customers.py`. Dùng PYTHONPATH gồm src/tests của cả hai service. Chỉ PostgreSQL disposable + fake provider.

## C09 — job và execution context

### Bổ sung phân trang trên 100 job — 18/10

R05 bổ sung theo yêu cầu nghiệm thu N2:

Sửa nghiệm thu ordering: expected trong test phải sort **(created_at,job_id)**, không theo thứ tự enqueue. Fixture test hiện cố định timestamp trùng trong từng nguồn; kiểm 125 ID duy nhất, lookup đúng job sequence 249 độc lập vị trí keyset và giữ toàn bộ scope/revoke checks. Sau tái hiện RED 1 FAIL, cả **Python 3.11 Windows và Linux đều 15 PASS / 0 SKIP / 0 FAIL / 0 ERROR** (SQLite + PostgreSQL). Đây là sửa test N1, không đổi thứ tự production để làm xanh.

```python
page = await authority.jobs.list_page(context, "schedule-run", source_id=schedule_id, cursor=cursor)
job = await authority.jobs.get(context, "schedule-run", job_id, source_id=schedule_id)
deliveries = await authority.jobs.list_page(context, "delivery", source_id=channel_id, run_id=job.job_id)
batch = await authority.jobs.get(context, "publish-batch", job_id, source_id=conversation_id)
```

`source_id` được lọc **trong SQL trước LIMIT**, theo field server cố định: schedule-run→body.schedule_id, channel-event/delivery→body.channel_id, publish-batch→body.conversation_id. `run_id` chỉ dành delivery, match literal prefix `delivery:<run_id>:` với wildcard escape; không gọi lại model. Hai filter là keyword optional của cả list_page/list/get. Đổi filter giữa các trang làm cursor không thuộc selection bị 422. Consumer không gửi tenant/owner để query.

`get` query thẳng ID + tenant + owner + kind + filters, không quét list và không có cap 100; sai phạm vi/không tồn tại trả `JOB_NOT_FOUND` (404), ID/filter không hợp lệ trả 422. Trước trả job repair, kiểm current context eligible và `context_for(job)` kiểm saved revision/workspace/environment; revoke/restore không làm job cũ tự được chạy lại. History list vẫn đọc được bởi owner hiện hành dù job đã mất quyền thực thi. Lookup không claim job, không thay lease/fencing và không thay việc worker recheck context ngay trước IO.

Test R05: **15 PASS / 0 SKIP / 0 FAIL / 0 ERROR** trên Python 3.11 Linux (3 ca lookup/filter × SQLite/PostgreSQL + 9 regression trước). PG nâng schema thật tới 0024 trên DB disposable, kiểm 125 job nguồn B nằm sau 125 job nguồn A và owner khác, 100+25 theo nguồn B, ID cuối đọc trực tiếp, wrong-filter cursor, restore/revoke và wildcard prefix. Đây là PG dialect/persistence proof; không gọi nó là test concurrency hoặc whole browser acceptance. Fixture `seed_personal_job_history(...,source_ids=[...],count=...)` dùng được cho N2; không cần migration mới.

Internal helper: **`await authority.jobs.list_page(context, kind, *, cursor=None, limit=100)`**, trả **`PersonalJobPage(items: list[DurableJob], next_cursor: str | None, has_more: bool)`**. `kind` là schedule-run/channel-event/delivery/publish-batch, limit nguyên 1–100; sai loại/limit trả `INVALID_JOB_KIND`/`INVALID_PAGINATION` (422).

```python
cursor = None
while True:
    page = await authority.jobs.list_page(context, "schedule-run", cursor=cursor, limit=100)
    for job in page.items:
        consume(job)  # consumer N2 xử lý/chiếu DTO, không đổi billing hoặc owner
    if not page.has_more:
        break
    cursor = page.next_cursor
```

Thứ tự tăng ổn định **(created_at, job_id)**; cursor là last returned job ID của trang còn tiếp, không phải offset hay bearer. Trang cuối `has_more=false,next_cursor=null`; không cần request trang rỗng nữa. Mỗi trang kiểm lại current authorization, tenant, personal owner và kind. Cursor sai owner/tenant/kind/không tồn tại/trỏ row đã purge trả `INVALID_JOB_CURSOR` (422): reload từ đầu; không fallback sang job của người khác. Đây là live keyset, không phải snapshot nhiều trang: không backdate created_at, consumer tự dedup theo job_id nếu reload.

**Tương thích:** `await jobs.list(context, kind)` vẫn trả `list[DurableJob]` như cũ, nay đọc hết các trang thay vì cắt thầm ở 100. N2 có thể nhận SHA mà chưa phải đổi mọi caller; lịch sử/list UI nên chuyển sang list_page để tránh nạp toàn bộ. Helper là server-internal; không đưa nguyên payload/lease/internal context trong DurableJob ra UI. N1 không thêm public job endpoint hoặc sửa router/consumer N2.

Fixture chung: `from vin_fixtures import authority, seed_personal_job_history`; `context,jobs = await seed_personal_job_history(authority, count=205)` tạo queue thật và 205 job cá nhân, không model IO. `PersonalJobPage` cùng nested DurableJob có trong DTO schema và OpenAPI components. Python **3.11 Linux, 9 PASS / 0 SKIP / 0 FAIL / 0 ERROR** cho pagination + existing personal job fences/context + C07 contract + shared fixture. Test pagination buộc tất cả created_at trùng nhau: **100 + 100 + 5**, không lặp/mất ID; kiểm compatibility list đủ 205, cross owner/kind/tenant cursor, empty page, limit sai, deleted cursor và revoke giữa các trang. Adapter pagination kiểm trên SQLite trong lượt này; không gọi đó là PostgreSQL concurrency proof. Ruff/diff checks đạt, không dùng key model thật.

Không cần migration mới cho hai bổ sung C07/C09 này. **Bắt buộc upgrade đủ graph hiện tại tới `0024_vin_admin_revisions`; queue cá nhân cần `0023_personal_job_constraint`.** `0022` một mình chưa đủ; rehearsal đã phát hiện CHECK cũ chỉ nhận scope/provider. Migration mới giữ dữ liệu/job cũ và thêm owner personal riêng; legacy workers bỏ qua personal jobs.

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
