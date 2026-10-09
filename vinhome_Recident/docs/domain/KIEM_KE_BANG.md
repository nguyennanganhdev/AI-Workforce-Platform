# Kiểm kê bảng cơ sở dữ liệu

Kết quả bước 1 của đề xuất sau câu hỏi "sao lắm bảng thế". **Quyết định của bạn (09/10/2026):** giữ nhóm F và G; duyệt xóa nhóm H, đã thực hiện bằng migration `0008_remove_unused_tables.sql` (120 xuống 112 bảng); nhóm D giữ, và chọn hướng 1 cho câu hỏi §5.3: mọi yêu cầu do cư dân khởi đầu đều có hồ sơ cư dân (migration `0009`, kịch bản vàng G13). Các số liệu dưới đây là của trạng thái **trước** `0008`.

## 1. Cách đo

Cơ sở dữ liệu sau migration `0001`–`0007` có **120 bảng**: `schema_migrations` (sổ ghi migration), **20 bảng do `0006`/`0007` thêm** và **99 bảng thừa kế** từ `0002_tables.sql` (sau khi `0006` đã xóa 10 bảng hình agent). Bản kiểm kê này xét 99 bảng thừa kế, bằng bốn phép đo:

| Phép đo | Cách làm |
|---|---|
| Số dòng | Dựng database mới, `seed`, rồi `mock --profile standard --seed 42`; đếm dòng từng bảng sau seed và sau mock |
| Mã dùng | Đếm module Python trong `src/vinhomes_api` (ngoài thư mục schema) có nhắc tên bảng. Đây là tìm theo từ, nên có thể đếm cả chú thích |
| Kịch bản chạm | Chạy toàn bộ test backend; trước và sau **mỗi test** lấy dấu vân tay nội dung từng bảng (số dòng và tổng băm các dòng); bảng nào đổi thì test đó "chạm" bảng. 98 test dùng database được ghi nhận |
| Khóa ngoại | Đọc quan hệ khóa ngoại từ `pg_constraint` để biết xóa một bảng kéo theo gì |

Giới hạn: chỉ thấy phần test thực sự thực thi; công cụ đo làm chậm test: lần chạy đo có 1 test hỏng (G12) và 1 lỗi fixture (test follow-up của Reception), cả hai pass khi chạy riêng; bộ test chạy lại không có công cụ đo cho kết quả **121 passed, 10 skipped**. Số liệu "chạm" lấy từ lần chạy đo, nên hai test đó có thể thiếu một vài bảng.

## 2. Kết quả theo nhóm

| Nhóm | Số bảng | Đề xuất |
|---|---|---|
| A. Lõi: yêu cầu, công việc, trao đổi, nhật ký | 17 | Giữ |
| B. Nền: khu đô thị, người, quyền, đăng nhập | 23 | Giữ |
| C. Tệp và bằng chứng | 9 | Giữ |
| D. Hồ sơ của app cư dân (`vh_resident_*`) | 10 | Giữ (xem câu hỏi 3) |
| E. Hóa đơn theo yêu cầu và thu tiền | 5 | Giữ (xem câu hỏi 2) |
| F. Nghiệp vụ nhân viên chuyên ngành | 21 | Chờ bạn quyết (câu hỏi 1) |
| G. Phân loại và đánh giá yêu cầu (triage) | 6 | Chờ bạn quyết (câu hỏi 1) |
| H. Không mã nào dùng | 8 | Đề xuất xóa |
| **Cộng** | **99** | |

Nhóm A đến E là các bảng mà mã đang dùng; nhóm A có kịch bản vàng chạm tới. Nhóm F và G có mã nhưng không kịch bản vàng nào chạm tới và hầu như không có dữ liệu mẫu. Nhóm H không có mã nào dùng.

## 3. Đề xuất xóa (nhóm H, 8 bảng)

Không module Python nào nhắc tới, không có dòng dữ liệu nào trong seed hay thế giới mẫu, không test nào chạm. Vì còn khóa ngoại, xóa phải gỡ cả cột:

| Bảng | Còn ai trỏ tới | Việc phải làm cùng |
|---|---|---|
| `ticket_sla_cycles` | `tickets.active_sla_cycle_id`, `ticket_escalations`, `ticket_sla_adjustments` | Xóa cột `tickets.active_sla_cycle_id` và hai bảng kia. Hạn xử lý hiện do trigger `app_assign_sla` và `sla_policies` đảm nhiệm, nên bảng chu kỳ này thừa |
| `ticket_escalations`, `ticket_sla_adjustments` | không | Xóa cùng `ticket_sla_cycles` |
| `dispatch_queue` | `dispatch_attempts` | Xóa cùng `dispatch_attempts` |
| `dispatch_attempts` | `work_assignments.dispatch_attempt_id` | Xóa cột này |
| `triage_rules` | `ticket_triage_decisions.matched_rule_id` | Xóa cột này (bảng `ticket_triage_decisions` thuộc nhóm G, giữ) |
| `payment_webhook_receipts` | `payments.receipt_id` | Xóa cột này |
| `event_inbox` | không | Xóa |

Kết quả nếu duyệt hết: 120 xuống 112 bảng. Migration `0008` sẽ gỡ khóa ngoại, xóa 4 cột, xóa 8 bảng, rồi chạy lại toàn bộ test trên database dựng từ đầu và trên database nâng từ `0007`.

## 4. Những gì nhóm A đến E dùng

Chi tiết từng bảng ở phụ lục. Tóm tắt các điểm đáng chú ý:

- **Nhóm A (17 bảng).** 16 bảng có kịch bản vàng chạm tới. `work_approvals` chỉ do test khác chạm.
- **Nhóm C (9 bảng).** Chuỗi tải ảnh và bằng chứng. `file_uploads`, `message_files` và `vh_conversation_uploads` chỉ có mã dùng, không test nào chạm; cùng thuộc một chuỗi nên giữ.
- **Nhóm D (10 bảng).** Là hồ sơ riêng của app cư dân (gửi yêu cầu, ảnh, phản hồi nghiệm thu), 11 test chạm tới. Nó chạy song song với `tickets`; xem câu hỏi 3.
- **Nhóm E (5 bảng).** `invoices` là hóa đơn sửa chữa phát hành theo từng yêu cầu (có `ticket_id` và `work_order_id`). Không trùng với `debit_notes` (thông báo phí định kỳ theo căn do tôi thêm), nhưng hai luồng tiền chưa nối với nhau: `payments` chỉ trỏ tới `invoices`.

## 5. Câu hỏi cần bạn quyết

1. **Nhóm F (21 bảng) và G (6 bảng): giữ hay chuyển ra ngoài phạm vi hiện tại?** Đây là các bảng của nhân viên kỹ thuật, vệ sinh/QC, an ninh, báo cáo, cắt nước điện và triage. Các tuyến backend `v3_technical`, `v3_specialized`, `v3_security`, `v3_water`, `v3_triage` đang dùng chúng (tôi chưa kiểm tra màn hình nhân viên nào gọi tới), nhưng chưa kịch bản vàng nào chạm tới và dữ liệu mẫu chỉ có 0–2 dòng mỗi bảng. Nếu xóa thì phải xóa cả các tuyến API tương ứng và phần giao diện gọi chúng. Đề xuất của tôi: **giữ**, nhưng không viết kịch bản mới cho chúng cho tới khi bạn đưa nghiệp vụ thật; khi nào quyết bỏ thì làm một đợt riêng cùng với mã.
2. **Thanh toán công nợ.** Thông báo phí (`debit_notes`) và hóa đơn sửa chữa (`invoices`) là hai thứ khác nhau, nhưng `payments` chỉ biết `invoices`. Cư dân hiện đọc được số dư nhưng chưa trả được. Khi làm thanh toán thật, `payments` cần trỏ được tới `debit_notes` hoặc cần một bảng phân bổ riêng. Chưa cần làm ngay.
3. **Hồ sơ cư dân (nhóm D) và `tickets`.** Hồ sơ cư dân gắn với `tickets` qua `vh_resident_case_tickets`, nên cùng một việc được ghi ở hai chỗ. Tôi không đề xuất gộp lúc này vì app cư dân đang chạy trên nó và 11 test phụ thuộc. Chỉ nêu để bạn biết đây là khoản nợ thiết kế lớn nhất còn lại.

## 6. Phát hiện khác: thế giới mẫu thiếu lịch sử xử lý

Thế giới mẫu `standard` có 922 yêu cầu (`tickets`) nhưng **0 dòng** ở `ticket_events`, `work_assignments`, `vh_ticket_plans`, `messages`; `work_orders` chỉ có 7 dòng từ seed. Một yêu cầu mẫu vì vậy không có dòng thời gian, công việc hay tin nhắn đi kèm. Các kịch bản vàng không bị ảnh hưởng vì chúng tự tạo dữ liệu qua API. Đề xuất: bổ sung cho `mock` một tỉ lệ yêu cầu có đủ lịch sử (sự kiện, công việc, tin nhắn). Việc này nhỏ và tách riêng, chưa làm.

## Phụ lục: từng bảng thừa kế

Cột: `seed` = số dòng sau seed; `mock` = sau thế giới mẫu `standard`; `mã` = số module Python nhắc tới; `kịch bản` = kịch bản vàng chạm tới; `test khác` = số test khác chạm tới.

### A. Lõi: yêu cầu, công việc, trao đổi, nhật ký

| Bảng | seed | mock | mã | kịch bản | test khác |
|---|---|---|---|---|---|
| `audit_events` | 0 | 0 | 3 | G01, G02, G03, G04, G05, G06, G07, G08, G09 | 22 |
| `channel_memberships` | 23 | 323 | 7 | G02, G03 | 26 |
| `channels` | 23 | 323 | 13 | G02, G03 | 26 |
| `event_outbox` | 0 | 0 | 2 | G02, G03, G04, G08, G09, G12 | 16 |
| `messages` | 0 | 0 | 10 | G02, G03 | 14 |
| `notification_deliveries` | 0 | 0 | 8 | G02, G03, G08 | 17 |
| `staff_shifts` | 2 | 1405 | 7 | G02 | 2 |
| `ticket_events` | 0 | 0 | 9 | G02, G03 | 18 |
| `ticket_routing_history` | 0 | 0 | 2 | G02 | 16 |
| `tickets` | 22 | 922 | 37 | G02, G03 | 18 |
| `unit_residents` | 20 | 690 | 13 | G09 | 1 |
| `vh_command_receipt` | 0 | 0 | 1 | G02 | 6 |
| `vh_reception_supervisor_messages` | 0 | 0 | 5 | G02 | 4 |
| `vh_ticket_plans` | 0 | 0 | 11 | G02 | 8 |
| `work_approvals` | 0 | 0 | 10 | – | 4 |
| `work_assignments` | 0 | 0 | 12 | G02 | 7 |
| `work_orders` | 7 | 7 | 21 | G02 | 9 |

### B. Nền: khu đô thị, người, quyền, đăng nhập

| Bảng | seed | mock | mã | kịch bản | test khác |
|---|---|---|---|---|---|
| `access_scopes` | 24 | 26 | 21 | – | 3 |
| `account_reviews` | 1 | 1 | 1 | – | 0 |
| `accounts` | 0 | 0 | 2 | – | 1 |
| `buildings` | 14 | 16 | 22 | – | 2 |
| `domains` | 1 | 1 | 13 | – | 0 |
| `management_coverage` | 2 | 14 | 11 | – | 2 |
| `management_units` | 1 | 1 | 8 | – | 1 |
| `platform_admins` | 1 | 1 | 8 | – | 0 |
| `scoped_user_roles` | 27 | 196 | 20 | – | 1 |
| `service_categories` | 2 | 2 | 15 | – | 1 |
| `sessions` | 0 | 0 | 1 | – | 1 |
| `sites` | 1 | 1 | 11 | – | 0 |
| `sla_policies` | 16 | 16 | 0 | – | 0 |
| `staff_profiles` | 2 | 26 | 17 | – | 6 |
| `staff_specialties` | 2 | 26 | 8 | – | 2 |
| `tenant_memberships` | 26 | 720 | 23 | – | 3 |
| `tenants` | 1 | 1 | 4 | – | 0 |
| `units` | 20 | 380 | 19 | – | 1 |
| `users` | 26 | 720 | 24 | – | 1 |
| `vh_reception_supervisor_pending` | 0 | 0 | 4 | – | 0 |
| `workspace_members` | 1 | 1 | 2 | – | 1 |
| `workspaces` | 1 | 1 | 5 | – | 1 |
| `zones` | 8 | 8 | 6 | – | 0 |

### C. Tệp và bằng chứng

| Bảng | seed | mock | mã | kịch bản | test khác |
|---|---|---|---|---|---|
| `evidence_items` | 0 | 0 | 5 | – | 4 |
| `execution_principals` | 0 | 0 | 5 | – | 3 |
| `file_objects` | 0 | 0 | 8 | – | 5 |
| `file_uploads` | 0 | 0 | 2 | – | 0 |
| `files` | 0 | 0 | 19 | – | 5 |
| `message_files` | 0 | 0 | 1 | – | 0 |
| `storage_locations` | 1 | 1 | 9 | – | 0 |
| `ticket_files` | 0 | 0 | 9 | – | 4 |
| `vh_conversation_uploads` | 0 | 0 | 2 | – | 0 |

### D. Hồ sơ của app cư dân (`vh_resident_*`)

| Bảng | seed | mock | mã | kịch bản | test khác |
|---|---|---|---|---|---|
| `vh_resident_case_tickets` | 0 | 0 | 2 | – | 8 |
| `vh_resident_cases` | 0 | 0 | 4 | – | 11 |
| `vh_resident_command_receipts` | 0 | 0 | 1 | – | 11 |
| `vh_resident_outbox` | 0 | 0 | 1 | – | 11 |
| `vh_resident_photos` | 0 | 0 | 4 | – | 1 |
| `vh_resident_public_events` | 0 | 0 | 1 | – | 11 |
| `vh_resident_resolution_photos` | 0 | 0 | 3 | – | 3 |
| `vh_resident_resolution_responses` | 0 | 0 | 2 | – | 3 |
| `vh_resident_resolutions` | 0 | 0 | 2 | – | 3 |
| `vh_resident_submissions` | 0 | 0 | 1 | – | 11 |

### E. Hóa đơn theo yêu cầu và thu tiền

| Bảng | seed | mock | mã | kịch bản | test khác |
|---|---|---|---|---|---|
| `invoice_lines` | 20 | 20 | 3 | – | 1 |
| `invoices` | 20 | 20 | 3 | – | 1 |
| `payment_allocations` | 0 | 0 | 2 | – | 1 |
| `payment_intents` | 0 | 0 | 1 | – | 1 |
| `payments` | 0 | 0 | 2 | – | 1 |

### F. Nghiệp vụ nhân viên chuyên ngành

| Bảng | seed | mock | mã | kịch bản | test khác |
|---|---|---|---|---|---|
| `incident_types` | 0 | 0 | 3 | – | 0 |
| `interruption_scopes` | 0 | 0 | 1 | – | 0 |
| `security_alert_deliveries` | 0 | 0 | 3 | – | 1 |
| `security_alerts` | 0 | 0 | 3 | – | 1 |
| `security_cameras` | 2 | 2 | 2 | – | 0 |
| `security_emergency_contacts` | 2 | 2 | 2 | – | 0 |
| `service_interruptions` | 0 | 0 | 4 | – | 0 |
| `vh_assets` | 1 | 1 | 1 | – | 0 |
| `vh_budget_approvals` | 1 | 1 | 2 | – | 0 |
| `vh_cleaning_plans` | 1 | 1 | 2 | – | 0 |
| `vh_contractor_updates` | 1 | 1 | 1 | – | 0 |
| `vh_maintenance_records` | 0 | 0 | 1 | – | 0 |
| `vh_operational_requests` | 0 | 0 | 2 | – | 0 |
| `vh_qc_redo_orders` | 1 | 1 | 7 | – | 0 |
| `vh_qc_results` | 1 | 1 | 8 | – | 3 |
| `vh_report_exports` | 0 | 0 | 1 | – | 1 |
| `vh_security_checkpoints` | 1 | 1 | 1 | – | 0 |
| `vh_security_handovers` | 1 | 1 | 1 | – | 0 |
| `vh_security_incidents` | 1 | 1 | 2 | – | 0 |
| `vh_sensor_readings` | 1 | 1 | 1 | – | 1 |
| `vh_technical_measurements` | 0 | 0 | 1 | – | 0 |

### G. Phân loại và đánh giá yêu cầu (triage)

| Bảng | seed | mock | mã | kịch bản | test khác |
|---|---|---|---|---|---|
| `ticket_assessments` | 0 | 0 | 3 | – | 0 |
| `ticket_reviews` | 0 | 0 | 2 | – | 0 |
| `ticket_triage_decisions` | 0 | 0 | 2 | – | 0 |
| `ticket_triage_reviews` | 0 | 0 | 2 | – | 0 |
| `triage_policy_bindings` | 1 | 1 | 1 | – | 0 |
| `triage_policy_versions` | 1 | 1 | 1 | – | 0 |

### H. Không mã nào dùng

| Bảng | seed | mock | mã | kịch bản | test khác |
|---|---|---|---|---|---|
| `dispatch_attempts` | 0 | 0 | 0 | – | 0 |
| `dispatch_queue` | 0 | 0 | 1 | – | 0 |
| `event_inbox` | 0 | 0 | 0 | – | 0 |
| `payment_webhook_receipts` | 0 | 0 | 0 | – | 0 |
| `ticket_escalations` | 0 | 0 | 0 | – | 0 |
| `ticket_sla_adjustments` | 0 | 0 | 0 | – | 0 |
| `ticket_sla_cycles` | 0 | 0 | 0 | – | 0 |
| `triage_rules` | 0 | 0 | 0 | – | 0 |
