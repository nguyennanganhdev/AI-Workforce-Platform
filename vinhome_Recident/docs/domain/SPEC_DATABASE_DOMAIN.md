# Spec: Database riêng cho domain Vinhomes

Trạng thái: **bước 1 và bước 2 đã làm**: database riêng chạy được, và họ bảng hình agent đã được thay bằng bề mặt tích hợp của đối tác (xem §10). Hợp đồng với platform: [HOP_DONG_TICH_HOP.md](HOP_DONG_TICH_HOP.md); các kịch bản: [KICH_BAN_VANG.md](KICH_BAN_VANG.md). Nghiệp vụ chi tiết: [NGHIEP_VU_VINHOMES.md](NGHIEP_VU_VINHOMES.md).

## 1. Mục tiêu

Domain Vinhomes tự sở hữu một database PostgreSQL hoàn chỉnh, tạo được từ đầu bằng các file trong gói này, không cần schema hay công cụ của platform cũ. Về sau platform nối vào như một khách hàng và nhận dữ liệu, tài liệu, gói tri thức của Vinhomes qua các đầu nối đã định nghĩa, không đọc thẳng bảng của domain.

Thành công nghĩa là:

1. Một lệnh dựng database trống thành database đúng schema domain, kèm dữ liệu mẫu.
2. Toàn bộ test backend cần database chạy được trên database đó (hiện 20 test bỏ qua và 6 file bị đánh dấu bỏ qua).
3. Không còn bảng, hàm, trigger hay cột nào chỉ phục vụ agent/Supervisor/platform ngoài đường nối đã chốt.
4. Mọi quy tắc nghiệp vụ mà database đang giữ hôm nay (trigger, ràng buộc, RLS) vẫn được giữ và có test.

## 2. Giả định (cần bạn xác nhận hoặc sửa)

1. Nghiệp vụ lấy từ chính mã trong gói. Không dùng `dev_TeamChien` hay nhánh cũ làm nguồn.
2. Định nghĩa cột và kiểu dữ liệu lấy từ schema của database đang chạy (`vinhomes_docker_complete`) làm tham chiếu **chỉ để đọc**. Đó là nguồn duy nhất còn đầy đủ vì file migration gốc nằm ngoài gói. Schema mới được viết lại thành file SQL của gói, không phải bản sao nguyên khối.
3. Giữ nguyên cách cô lập hiện có: mọi bảng có `tenant_id`, RLS bật và **bắt buộc** (`FORCE`), đặt ngữ cảnh bằng `app.tenant_id` và `app.user_id`.
4. Backend chạy bằng một role không phải superuser, không bypass RLS.

## 3. Hiện trạng đo được

| Điều đo | Kết quả | Cách đo |
|---|---|---|
| Bảng trong schema đang chạy | 201 (56 `vh_*`, 145 khác) | `information_schema` |
| Bảng mà SQL trong backend nhắc tới | 98 (cộng 3 bảng chỉ có trong dữ liệu mẫu) | quét `from/join/into/update` trong `src/` và `scripts/` |
| Bảng có `tenant_id`, RLS bật, RLS bắt buộc, có policy | 184 / 184 / 184 / 184 | `pg_class`, `pg_policies` |
| Trigger không nội bộ | 139 (77 trên bảng mã dùng) | `pg_trigger` |
| Hàm `app_*` giữ bất biến nghiệp vụ | 13 | `pg_proc` |
| Ràng buộc trên bảng mã dùng | 168 check, 394 khóa ngoại, 158 unique, 4 exclusion | `pg_constraint` |
| Extension | `btree_gist` (cần cho exclusion), `vector` (chỉ platform), `plpgsql` | `pg_extension` |
| Role runtime của domain | `vinhomes_v3_api` | `pg_roles` |

**Hai thế hệ dữ liệu chồng nhau trong gói.**

- **Thế hệ A**: 16 bảng ORM (`vh_incident`, `vh_task`, `vh_work_order`, `vh_action_request`, `vh_checklist`, `vh_business_event`, `vh_outbox_message`…), 15 migration alembic, 13 package Python khoảng 5.600 dòng (`incidents`, `tasks`, `work_orders`, `qc`, `evidence`, `events`, `rules`, `approvals`, `actions`, `commands`, `outbox`, `resolution`, `db`). Bằng chứng không dùng: không có thao tác API nào trong 201 thao tác đang phục vụ thuộc nó, không module nào của nó với tới được từ `main`, và 15 trong 16 bảng không có trong database.
- **Thế hệ B (V3)**: các bảng `tickets`, `work_orders`, `work_assignments`, `vh_qc_results`… mà 201 thao tác API thật sự dùng. Đây là mô hình sống.

**Bảng cha ngoài tập mã dùng nhưng bảng domain tham chiếu bằng khóa ngoại** (phải đi cùng): `sla_policies`, `ticket_sla_cycles`, `triage_rules`, `dispatch_attempts`, `payment_webhook_receipts`. Hai bảng còn lại là của platform: `deployment_packages` (từ `agents`, `channels`) và `knowledge_documents` (từ `files`), nghĩa là `channels` và `files` đang mang cột trỏ sang platform cần cắt.

**Cơ chế ủy quyền của Reception đang dựa trên bảng hình platform**: `agents`, `agent_versions`, `agent_releases`, `agent_runs`, `execution_principals`, `runtime_backends`, `runtime_identities`, `runtime_session_bindings` (`reception_delegation.py`), cộng `agent_teams`, `team_members`, `channel_agents` cho kênh giao việc (`v3_reception_operations.py`, `v3_reception_supervisor.py`).

## 4. Phạm vi dữ liệu đề xuất

| Nhóm | Bảng | Số bảng | Đề xuất |
|---|---|---|---|
| **Domain đang dùng** | danh tính và tenant (`tenants`, `users`, `accounts`, `account_reviews`, `sessions`, `tenant_memberships`, `platform_admins`, `scoped_user_roles`, `access_scopes`, `workspaces`, `workspace_members`), địa điểm (`domains`, `sites`, `zones`, `buildings`, `units`, `unit_residents`), tổ chức (`management_units`, `management_coverage`, `service_categories`, `incident_types`, `staff_profiles`, `staff_specialties`, `staff_shifts`), ticket (`tickets`, `ticket_events`, `ticket_files`, `ticket_assessments`, `ticket_reviews`, `ticket_routing_history`, `ticket_triage_decisions`, `ticket_triage_reviews`, `triage_policy_versions`, `triage_policy_bindings`), việc (`work_orders`, `work_assignments`, `work_approvals`, `evidence_items`, `service_interruptions`, `interruption_scopes`, `vh_ticket_plans`, `vh_qc_results`, `vh_qc_redo_orders`, `vh_budget_approvals`, `vh_cleaning_plans`, `vh_operational_requests`, `vh_maintenance_records`, `vh_technical_measurements`, `vh_sensor_readings`, `vh_assets`, `vh_contractor_updates`), an ninh (`security_*` 4, `vh_security_*` 3), hóa đơn (`invoices`, `invoice_lines`, `payments`, `payment_allocations`, `payment_intents`), hồ sơ cư dân (`vh_resident_*` 10), tệp (`files`, `file_objects`, `file_uploads`, `storage_locations`, `ticket_files`, `message_files`, `vh_conversation_uploads`), hội thoại cư dân (`channels`, `channel_memberships`, `messages`), thông báo, kiểm toán, báo cáo (`notification_deliveries`, `audit_events`, `vh_report_exports`), `vh_command_receipt` | khoảng 88 | Giữ |
| **Domain đã thiết kế, mã chưa gọi** | SLA (`sla_policies`, `ticket_sla_cycles`, `ticket_sla_adjustments`, `ticket_escalations`), phân loại (`triage_rules`), điều chuyển (`work_reassignment_requests`, `work_approval_evidence`, `ticket_assessment_evidence`), hoàn tiền (`refunds`, `refund_allocations`, `payment_webhook_receipts`), tệp (`file_access_logs`, `file_deletion_requests`, `file_upload_parts`, `file_processing_jobs`, `storage_event_receipts`), sự kiện tích hợp (`event_outbox`, `event_inbox`), dữ liệu kỹ thuật (`vh_technical_sensors`, `vh_technical_sop_profiles`, `vh_technical_vendors`, `vh_technical_maintenance_events`, `vh_technical_measurement_records`, `vh_technical_sensor_samples`) | khoảng 24 | **Cần bạn quyết** (câu hỏi Q1) |
| **Ủy quyền Reception hình platform** | 8 bảng ở §3 | 11 | **Thay bằng mô hình nhỏ của domain** (quyết định D2); hai bảng `vh_reception_supervisor_messages` và `vh_reception_supervisor_pending` của kênh giao ticket đi theo câu hỏi Q3 |
| **Của platform, bỏ** | `agent_*`, `knowledge_*`, `mcp_*`, `skills`, `routines`, `memory_*`, `retrieval_*`, `runtime_memory_bindings`, `components`, `credentials`, `embedding_models`, `vh_agent_*`, `vh_private_chat*`, `vh_session_sources`, `vh_external_call_confirmations`, `vh_technical_agent_grants`, `vh_technical_api_*`, `vh_connection_policy`, `team_tasks`, `team_mailbox`, `mailbox_deliveries`, `deployment_packages`… và bảng đăng nhập cũ (`verifications`, `sso_providers`, `revoked_access`, `user_instructions`, `attachments`, `work_items`) | khoảng 75 | Không đưa vào |

Số bảng mỗi nhóm là ước lượng (88 + 24 + 11 + 2 + 75 = 200, lệch 1 so với 201 vì phân loại ranh giới); danh sách chính xác được khóa ở bước Plan.

## 5. Quyết định cần bạn duyệt

- **D1. Bỏ thế hệ A.** Xóa 13 package, 16 mô hình ORM và 15 migration alembic, vì không dùng, không có trong database, và alembic không tạo được mô hình sống. Rủi ro: mất 5.600 dòng mà một ngày nào đó bạn muốn dùng lại; chúng vẫn nằm trong lịch sử git của nhánh.
- **D2. Thay ủy quyền hình platform của Reception bằng mô hình nhỏ của domain**: ví dụ `reception_clients` (ai được gọi), `reception_delegations` (lượt ủy quyền ngắn hạn: cư dân, kênh, hết hạn, trạng thái) và đường nối giao ticket. Đổi mã ở `reception_delegation.py`, `v3_reception_operations.py`, `v3_reception_runtime.py`, `v3_reception_supervisor.py`. Rủi ro: đổi cơ chế bảo mật, cần test kỹ; lợi ích: domain không còn mang `agents`, `runtime_*`, `execution_principals`.
- **D3. Phương thức tạo schema**: file SQL đánh số (`0001_…sql`) cộng một bảng `schema_migrations` và một lệnh chạy, thay cho alembic. Lý do: RLS, trigger và hàm viết bằng SQL, alembic không giúp gì thêm. Đổi lại phải tự viết công cụ chạy file (khoảng 60 dòng).
- **D4. Đường nối cho platform**: giữ `event_outbox` (sự kiện domain phát ra, ví dụ `ticket.created`) làm kênh duy nhất để platform lấy dữ liệu về sau, thay cho việc platform đọc bảng.
- **D5. Role**: một role chủ sở hữu (chạy migration), một role runtime cho API (không superuser, không `BYPASSRLS`).

## 6. Sáu mục cốt lõi

**Công nghệ**: PostgreSQL 16 trở lên với `btree_gist`; không dùng `vector`. Python 3.12, `asyncpg`/SQLAlchemy như hiện có.

**Lệnh** (đề xuất, chưa tồn tại):

```
Dựng database trống:   python -m vinhomes_api.db create --url postgresql://…/postgres --name vinhomes
Áp migration:          python -m vinhomes_api.db migrate --url postgresql://…/vinhomes
Nạp dữ liệu mẫu:       python -m vinhomes_api.db seed --url postgresql://…/vinhomes
Test có database:      VINHOMES_TEST_ADMIN_URL=… python -m pytest services/vinhomes-api/tests
Kiểm tra schema:       python -m pytest services/vinhomes-api/tests/test_schema_contract.py
```

**Cấu trúc**:

```
services/vinhomes-api/db/
  migrations/0001_*.sql …   schema theo thứ tự phụ thuộc (khóa ngoại), mỗi file một nhóm nghiệp vụ
  seed/*.sql                dữ liệu mẫu theo nhóm, chạy được lặp lại
  roles.sql                 role chủ sở hữu và role runtime, quyền tối thiểu
src/vinhomes_api/db_tool.py   công cụ create/migrate/seed
tests/test_schema_contract.py mọi bảng có tenant_id+RLS bắt buộc, mọi bảng mã nhắc đều tồn tại, role runtime không bypass
tests/test_invariants.py      từng trigger bất biến (append-only, sức chứa phân công, quyết định phân loại…)
```

**Phong cách**: tên bảng số nhiều snake_case, tiền tố `vh_` chỉ cho bảng riêng của Vinhomes; khóa chính `uuid`; mọi bảng có `tenant_id uuid not null`, `created_at`, `updated_at` (trigger `app_touch_updated_at`), cột `version int` cho bảng cập nhật đồng thời; trạng thái bằng `text` kèm `check` (không dùng enum PostgreSQL, để thêm giá trị bằng migration thường).

**Kiểm thử**: dựng database sạch từ migration, nạp seed, chạy toàn bộ test backend; thêm test hợp đồng schema và test cho từng trigger bất biến; một test cô lập tenant (hai tenant, một role runtime, chứng minh không đọc chéo).

**Ranh giới**:

- Luôn: `tenant_id`, RLS bật và bắt buộc trên mọi bảng; role runtime không superuser; migration chạy được lặp lại trên database mới.
- Hỏi trước: xóa hoặc đổi tên bảng đang có dữ liệu thật; thêm extension; đổi giá trị trạng thái đã công bố ra API.
- Không bao giờ: dùng superuser hay `BYPASSRLS` cho API; đưa mật khẩu hay khóa vào file SQL hay seed; sửa database `vinhomes_docker_complete` đang chạy của bạn (chỉ đọc).

## 7. Câu hỏi mở

- **Q1.** Nhóm "đã thiết kế, mã chưa gọi" (SLA, hoàn tiền, điều chuyển, sự kiện tích hợp, dữ liệu kỹ thuật): giữ hết, giữ một phần, hay chỉ làm khi mã gọi? Tôi nghiêng về giữ SLA và `event_outbox` (khóa ngoại và đường nối cần chúng) và hoãn phần còn lại.
- **Q2.** Dữ liệu kỹ thuật (`vh_technical_sensors`, SOP, nhà thầu): bạn sẽ cung cấp như một phần dữ liệu/tri thức cho platform, hay thuộc database nghiệp vụ?
- **Q3.** Sau D2, kênh giao ticket của Reception (tên hiện là "Supervisor") giữ nguyên hợp đồng `schema_v2` hay đổi tên và hợp đồng?
- **Q4.** Dữ liệu mẫu: dùng lại dữ liệu mẫu hiện có (`seed_v3_*.sql`) hay viết bộ mới nhỏ hơn?

## 8. Kết quả bước 1 (đã làm và đã kiểm chứng)

Các quyết định đã áp dụng theo khuyến nghị của tôi sau khi bạn bảo tiếp tục. Mỗi quyết định đảo lại được vì schema là file SQL của gói.

| Quyết định | Áp dụng |
|---|---|
| D1 bỏ thế hệ A | Đã xóa 13 package, ORM, alembic và 2 dependency. Không thao tác API nào bị ảnh hưởng. |
| D3 SQL đánh số thay alembic | `vinhomes_api.database` (`create / migrate / seed / role`), bảng `schema_migrations` có checksum, đọc `DATABASE_URL` từ môi trường. |
| D4 đường nối cho platform | `event_outbox` đã có mã ghi (`events.py`) và là nguồn sự kiện của hợp đồng tích hợp; `event_inbox` đã xóa ở migration `0008` (domain chỉ phát sự kiện, không nhận). |
| D5 role | Role chủ chạy migration; role API tạo bằng `database role`, từ chối nếu là superuser hoặc `BYPASSRLS`. |
| Q1 | Quyết định ban đầu: giữ SLA (4 bảng), `triage_rules`, `dispatch_*`, `payment_webhook_receipts`, `event_*`; hoãn hoàn tiền, tệp mở rộng, dữ liệu kỹ thuật mở rộng. **Thay đổi 09/10/2026** sau [kiểm kê bảng](KIEM_KE_BANG.md): migration `0008` xóa 8 bảng không mã nào dùng (`ticket_sla_cycles`, `ticket_sla_adjustments`, `ticket_escalations`, `triage_rules`, `dispatch_queue`, `dispatch_attempts`, `payment_webhook_receipts`, `event_inbox`). Giữ `sla_policies` (trigger gán hạn xử lý đang dùng) và `event_outbox`. |
| Q2, Q4 | Dữ liệu kỹ thuật mở rộng không đưa vào; dữ liệu mẫu hiện có được dùng lại, bỏ phần `memory_*`. |
| Q3 | Giữ nguyên hợp đồng `schema_v2` của kênh giao ticket (chưa đổi tên). |
| D2 | **Chưa làm.** Cơ chế ủy quyền của Reception và việc tải tệp vẫn dùng 11 bảng hình platform. |

**Schema**: 5 migration, 109 bảng nghiệp vụ cộng `schema_migrations`; chỉ cắt 3 cột trỏ sang platform (`agents.package_id`, `channels.package_id`, `files.document_id`) và nhánh phạm vi `document` của `files`. 103 bảng có `tenant_id` và đều có RLS bắt buộc cùng đúng một policy; 6 bảng danh tính dùng chung không có. 83 trigger, 15 hàm. Dòng tham chiếu `runtime_backends` của Reception nằm ở `0005_reference_data.sql`.

**Kiểm chứng** (database tạm trong container Postgres, role tạm, xóa sau khi chạy):

- Dựng database trống bằng công cụ, chạy lại lần hai báo "up to date", nạp dữ liệu mẫu hai lần không lỗi.
- Role API thấy 22 ticket với đúng tenant, 0 với tenant khác, 0 khi không đặt tenant; chèn không có ngữ cảnh tenant bị từ chối.
- Backend: 81 test qua và 13 bỏ qua trên database dựng từ gói (trước đó 29 qua). Bảy test hợp đồng schema mới (`tests/test_schema_contract.py`) chặn quay lại: thiếu RLS, bảng platform xuất hiện, SQL nhắc bảng platform, role vượt RLS, nhật ký sửa được, migration bị sửa sau khi áp.
- Job `migrate` chạy trong container API: lần đầu áp 5 migration, lần hai "up to date".
- Kiểm tra hợp đồng gọi: 10 đường Reception → backend, 14 đường app cư dân, 28 đường app nhân viên đều có route, trừ `/internal/reception/session/resolve` (chưa bao giờ được phục vụ, adapter không ai gọi).

**Một lỗi hồi quy do tôi gây ra và đã sửa**: khi xóa `v3_models` tôi làm mất `GET /internal/reception/v1/model-config`, mà Reception gọi mỗi lượt; cư dân sẽ nhận câu trả lời lỗi. Test của Reception không bắt được vì chúng dùng backend giả. Đã bỏ lời gọi này khỏi Reception (nó dùng cấu hình model của môi trường triển khai) và đã thêm kiểm tra hợp đồng gọi ở trên.

## 9. Điều tài liệu nghiệp vụ cho thấy còn thiếu, liên quan đến dữ liệu bạn sẽ cung cấp

Rút từ phần 6 của [NGHIEP_VU_VINHOMES.md](NGHIEP_VU_VINHOMES.md) (24 quy trình, 773 trích dẫn `path:line`; tác giả báo chưa đối chiếu nội dung với mã hết phần sau dòng 470, tôi đã đối chiếu độc lập các điểm 1 và 2 ở trên):

1. **Không có đường nào đưa dữ liệu nền vào ngoài SQL/script**: gắn cư dân vào căn hộ (`unit_residents`), số điện thoại, nhân viên và chuyên môn, ca làm, phạm vi phủ, tòa nhà/căn hộ/nhóm dịch vụ, camera, tài sản. Hệ quả thực tế: cư dân tự đăng ký được duyệt vẫn **không báo được sự cố** cho đến khi có người gắn căn hộ. Vì bạn sẽ cung cấp dữ liệu, cần một **đường nhập dữ liệu** (CSV/JSON qua công cụ `database`) hoặc các API quản trị tương ứng.
2. **Chưa cài đặt**: SLA (hạn xử lý không bao giờ được ghi), bộ gửi thông báo (`notification_deliveries` kẹt ở `pending`), hoàn tiền và thanh toán thật (chỉ demo), quét mã độc, tác dụng của việc cư dân hủy yêu cầu.
3. **Chưa có điểm vào cho agent bên ngoài**: đề xuất kế hoạch xử lý (hai test đang bỏ qua vì thiếu nó), cùng với bất kỳ thao tác nào platform sẽ gọi sau này.
4. **Giao diện nối thật mới phủ một phần**: an ninh, vệ sinh, nhà thầu, phê duyệt, khóa nước, ngân sách, kế hoạch, phân loại, thanh toán có backend nhưng chưa có màn hình ở app nhân viên.
5. **Không nhất quán đáng sửa**: trạng thái kế hoạch `revision_requested` bị response model từ chối (dự kiến lỗi 500); quản trị viên bị 403 ở vài thao tác mà các route khác cho qua; ba hạn đề nghị việc khác nhau (24 giờ, 30 phút, 1 giờ) cho cùng một khái niệm.

## 10. Bước 2: bề mặt tích hợp và thực thể của các kịch bản (09/10/2026)

- **D2 đã làm.** Migration `0006` bỏ 10 bảng hình agent và thay bằng `integration_clients`, `delegations`, `integration_cases`; các cột `*_agent_id` thành `*_client_id`, `*_run_id` thành `*_delegation_id`. Một database dựng theo kiểu cũ được nâng lên tại chỗ (đã thử). Đường `/internal/reception/*` và dây `schema_v2` giữ nguyên; Reception không đổi ngoài một tên trường.
- **Thực thể mới** (migration `0007`, 17 bảng): thông báo phí, xe, thẻ, lượt qua cổng, đơn lễ tân, khách, tiện ích và đặt chỗ, quy định và đơn thi công, cẩm nang, văn bản quy định, thông báo chung, cùng bảng `state_transitions` giữ từ điển trạng thái (76 bước, lấy từ `domain_spec.json` của bạn) và một hàm chặn chuyển trạng thái ngoài từ điển. Đặt chỗ tiện ích không thể trùng nhau nhờ ràng buộc loại trừ ở cơ sở dữ liệu. Hạn xử lý của yêu cầu do trigger gán theo `sla_policies`.
- **Các khoảng trống ở §9 nay:** (1) đường nạp dữ liệu nền: **có** (`import`, [NAP_DU_LIEU.md](NAP_DU_LIEU.md)); (2) SLA: hạn được **gán** và cảnh báo hạn được phát qua sự kiện; leo thang, bộ gửi thông báo thật, thanh toán thật, quét mã độc và tác dụng của việc cư dân hủy yêu cầu **vẫn chưa làm**; (3) điểm vào cho agent ngoài đề xuất phương án: **có**; (4) lớp xem thử ở app nhân viên còn dữ liệu giả về phòng và agent: **chưa dọn**; (5) `event_outbox` nay được ghi và đọc; `event_inbox` vẫn chưa dùng.
- Còn lại: `execution_principals` chỉ phục vụ chủ sở hữu tệp (thay bằng `owner_user_id` là việc riêng); `test_password_database.py` có các test tùy chọn nhắc tới route phòng đã bỏ.
