# Kế hoạch triển khai: kịch bản vàng và hợp đồng tích hợp

Trạng thái: **bản 0.2 (09/10/2026): T1 đến T7 đã làm và có test; T8 là phần tài liệu này**. Cần đọc trước: [KICH_BAN_VANG.md](KICH_BAN_VANG.md), [HOP_DONG_TICH_HOP.md](HOP_DONG_TICH_HOP.md). Nền: [SPEC_DATABASE_DOMAIN.md](SPEC_DATABASE_DOMAIN.md).

## 1. Cách làm

Mỗi bước: việc, điều kiện chấp nhận, lệnh kiểm. Chỉ sang bước sau khi bước trước qua kiểm. Không đổi mã trạng thái hay hợp đồng đã công bố ra API ngoài các điểm ghi ở §3. Mọi thay đổi schema là **migration mới** (`0006…`), không sửa migration đã áp.

## 2. Dùng gì từ schema tham chiếu của bạn

Schema tham chiếu (`schema.sql`, `domain_spec.json`: khoảng 135 bảng, id `bigint`, không có `tenant_id`) là thiết kế độc lập. Gói đã có 109 bảng chạy thật (id `uuid`, mọi bảng có `tenant_id` và RLS bắt buộc). **Nguyên tắc: không thay mô hình đang chạy; chỉ thêm thực thể mà một kịch bản vàng cần, theo quy ước của gói** (số nhiều, `uuid`, `tenant_id`, RLS, `created_at`/`updated_at`).

### 2.1 Thêm mới (17 bảng)

| Bảng của gói | Từ bảng của bạn | Gọn lại thế nào | Kịch bản |
|---|---|---|---|
| `debit_notes`, `debit_note_lines` | `debit_note`, `debit_note_line` | Bỏ `fee_type`, `fee_tariff`, `billing_period`, `meter*`: dòng phí mang `fee_kind` và mô tả; số liệu kỳ nằm ở cột `period_month` | G01 |
| `vehicles` | `vehicle` | giữ | G05 |
| `access_cards` | `access_card` | giữ; `holder` là người dùng hoặc tên (thẻ tạm) | G05 |
| `access_events` | `access_event` | cổng là mã chữ, không có bảng `gate`; chỉ thêm, không sửa | G04, G05 |
| `service_requests`, `service_request_events` | `service_request` + `card_request` + `goods_move_request` + `resident_profile_request` | ba bảng chi tiết gộp thành `details jsonb` theo `kind`; lịch sử là bảng riêng | G05 |
| `visitor_passes` | `visitor_pass` | giữ | G04 |
| `amenities`, `amenity_bookings`, `amenity_closures` | `amenity`, `amenity_booking`, `amenity_closure` | lịch mở, khung giờ, phí, hạn mức tuần nằm trong `amenities`; bỏ `amenity_area`, `ticket_type`, `participant`, `waitlist` | G06 |
| `construction_policies`, `construction_permits` | `construction_policy`, `construction_permit` | chỉ đọc ở v1; mốc thời gian là cột trên đơn, không có bảng sự kiện, nhà thầu là tên | G07 |
| `handbook_articles`, `policy_documents` | `handbook_article`, `policy_document` | thêm `audience[]`, `body_md` | G07, G08, tri thức |
| `announcements` | `announcement` + `announcement_target` | mục tiêu là `zone_ids`/`building_ids` dạng mảng | G08 |
| `state_transitions` | `state_machines` trong `domain_spec.json` | một bảng tham chiếu (`entity`, `from`, `to`, `actors`, `rule`), kèm một hàm chặn chuyển trạng thái ngoài từ điển cho các bảng mới | G04–G07 |

### 2.2 Đã có, dùng bảng hiện tại

| Của bạn | Của gói | Ghi chú lệch nhau |
|---|---|---|
| `urban_area`, `zone`, `building`, `floor`, `unit` | `domains`, `sites`, `zones`, `buildings`, `units` | tầng là cột `units.floor` |
| `management_office`, `office_building`, `department` | `management_units`, `management_coverage`, `service_categories` | bộ phận suy ra từ nhóm dịch vụ và chuyên môn |
| `person`, `user_account` | `users`, `accounts` | điện thoại là `users.phone_e164` |
| `resident_unit` | `unit_residents` | `relation` ∈ `owner`/`tenant`/`household`; của bạn thêm `co_owner` (tính là `owner`), `authorized_person` (**không hỗ trợ**) |
| `staff`, `role`, `staff_role`, `staff_shift` | `staff_profiles`, `scoped_user_roles`, `staff_specialties`, `staff_shifts` | |
| `ticket_category`, `ticket`, `ticket_event` | `service_categories`, `tickets`, `ticket_events` | trạng thái của gói: `open, triaging, assigned, in_progress, resolved, closed, cancelled`; của bạn chi tiết hơn (đã có `planning`, `awaiting_*`). **Giữ của gói**, ánh xạ ở hợp đồng nếu cần |
| `work_plan` | `vh_ticket_plans` (cột `proposal`) | trạng thái `management_pending → resident_pending → approved`/`rejected`/`revision_requested` |
| `work_order` | `work_orders`, `work_assignments` | |
| `asset`, `maintenance_plan` | `vh_assets`, `vh_maintenance_records` | |
| `planned_outage` | `service_interruptions` (+ `announcements` mới) | cắt nước hiện gắn phiếu việc; thông báo cắt theo kế hoạch là bản tin loại `outage_notice` |
| `notification` | `notification_deliveries` | |
| `file_object`, `audit_log` | `files`, `file_objects`, `audit_events` | |
| `invoice` kiểu hóa đơn sửa chữa | `invoices`, `payments` | công nợ **hằng tháng** là `debit_notes` mới; hóa đơn sửa chữa theo ticket giữ nguyên |

### 2.3 Chưa dùng (đặc tả sau)

Thanh toán thật (`payment`, `payment_allocation`, `refund`, `saved_card`, `auto_payment_mandate`), điểm thưởng (`loyalty_*`), voucher (`merchant`, `voucher*`), bàn giao nhà (`handover_*`), vi phạm (`violation_*`), khảo sát (`survey*`), sự kiện cộng đồng (`community_event`, `event_registration`), xe buýt và môi trường (`bus_*`, `environment_reading`), hợp đồng mua bán (`sales_contract`, `installment`, `contract_document`), khuôn mặt (`face_enrollment`), sạc xe điện (`ev_charging_registration`), thiết bị trong căn, bảng giá sửa chữa, thợ và vận chuyển vật tư thi công, bãi xe thời gian thực. Lý do: không kịch bản vàng nào cần ở v1. Khi cần, thêm theo đúng quy ước §2.1.

## 3. Thay đổi so với mã hiện có

| Thay đổi | Lý do |
|---|---|
| Bỏ 9 bảng hình agent (`agent_versions`, `agent_releases`, `agent_teams`, `team_members`, `channel_agents`, `runtime_backends`, `runtime_identities`, `runtime_session_bindings`, `agent_runs`) và đổi `agents` thành `integration_clients` | Hợp đồng §1: chỉ còn client, lượt ủy quyền, hồ sơ |
| Thêm `delegations`, `integration_cases` | thay `agent_runs`, `agent_teams` |
| Cột `*_agent_id` đổi thành `*_client_id`; `*_run_id` thành `*_delegation_id` | cùng ý nghĩa, tên đúng khái niệm |
| Giữ `execution_principals` | `files.owner_principal_id` dùng; thay bằng `owner_user_id` là việc riêng, không chặn kịch bản nào |
| Giữ đường `/internal/reception/*` và dây `…/reception-supervisor/*` | Reception đang dựa vào; đường mới `/integration/v1/cases/*` chạy trên cùng dữ liệu |
| Đổi tên biến cấu hình `VINHOMES_API_SUPERVISOR_APPROVES_PLANS` | còn dấu vết Supervisor; giữ tên cũ thêm một bản làm bí danh |
| `event_outbox` thêm cột `seq` tăng đơn điệu | con trỏ cho nguồn sự kiện |

## 4. Các bước

| # | Việc | Chấp nhận | Kiểm |
|---|---|---|---|
| T1 | Migration `0006_integration_surface.sql`; viết lại `reception_delegation.py` và các chỗ gọi 9 bảng; cập nhật dữ liệu mẫu | Không còn bảng/cột hình agent; Reception chạy như cũ (nhận ủy quyền từng lượt, bàn giao hồ sơ); số test backend không giảm ngoài test của phần đã bỏ | `pytest services/vinhomes-api/tests`; `test_schema_contract` mở rộng danh sách bảng bị cấm; bảng đối chiếu đường gọi |
| T2 | Xác thực tích hợp: bí mật client, token ủy quyền, danh mục cho phép, ghi `initiator_kind='agent'`; điểm cuối `delegations/self`, `delegations/{id}/finish`, `tools`, `me` | Hợp đồng §2, §3, §4, §11 (b)(c)(d) | `tests/test_integration_auth.py` |
| T3 | Migration `0007_domain_entities.sql` (17 bảng §2.1) + `state_transitions` + hàm chặn chuyển trạng thái + RLS + quyền role | Schema contract (mọi bảng có `tenant_id`, RLS bắt buộc) vẫn qua; chuyển trạng thái ngoài từ điển bị chặn | `test_schema_contract`, `test_state_transitions` |
| T4 | Điểm cuối nghiệp vụ cho thực thể mới: công nợ, xe/thẻ, khách, tiện ích, thi công (đọc), thông báo chung; ghi cho G04–G06 | Kịch bản G01, G04–G07, G09 (phần dữ liệu mới) | `test_golden.py::G01`… |
| T5 | Hồ sơ và phương án cho agent ngoài (`/integration/v1/cases/*`), hạn xử lý khi tạo yêu cầu, tác vụ quét quá hạn, nguồn sự kiện, gói tri thức | G02, G08, G11, G12; hợp đồng §5–§7 | `test_golden.py::G02`, `G08`, `G11`, `G12`; `test_integration_events.py`, `test_integration_knowledge.py` |
| T6 | `database mock`, `database import`, `database reset` | Hợp đồng §8; cùng seed cho cùng dữ liệu; nạp hai lần không nhân đôi; `--dry-run` không ghi | `test_mock_import.py` |
| T7 | Bộ test `G01`…`G12` đầy đủ trên thế giới mẫu | Mọi dòng "Chấp nhận" của mỗi kịch bản | `pytest -k golden` |
| T8 | Cập nhật tài liệu, bộ nhớ, kiểm đường gọi, báo cáo | Mọi thứ khớp | bảng đối chiếu đường gọi; `npm run typecheck` + test web |

## 5. Rủi ro

| Rủi ro | Cách giảm |
|---|---|
| Viết lại ủy quyền của Reception làm vỡ mỗi lượt chat của cư dân (đã từng xảy ra khi bỏ `model-config`) | T1 giữ nguyên đường `/internal/reception/*`; thêm test chạy trọn một lượt (cấp ủy quyền → gọi `context` → `intake` → `execute` → kết thúc) trên database thật, không chỉ Reception với backend giả |
| Đổi tên cột lan khắp mã SQL viết tay | Tìm bằng `grep` mọi tên cũ, thêm test quét mã nguồn (đã có `test_the_backend_sql_never_names_a_platform_table`) cho tên cột/bảng cũ |
| Hai bên (apps, agent) cùng gọi một API: thêm điểm cuối cho agent làm lộ thao tác ngoài ý | Danh sách cho phép, từ chối mặc định; test hợp đồng §11(b) quét danh mục tìm thao tác cấm |
| Dữ liệu giả lệch nghiệp vụ | Sinh dữ liệu **qua trigger và ràng buộc thật**, sau đó chạy truy vấn kiểm nhất quán (tổng dòng = tổng phiếu, đã trả ≤ tổng) |
| Khối lượng lớn | Từng bước tự đứng được; nếu dừng giữa chừng, gói vẫn chạy được ở bước trước |

## 6. Ranh giới

- **Luôn:** `tenant_id` + RLS bắt buộc trên bảng mới; migration mới thay vì sửa; test trước khi báo xong; không in bí mật.
- **Hỏi trước:** đổi mã trạng thái đã công bố; thêm phụ thuộc Python; mở thêm thao tác cho agent ngoài danh mục §4; nạp dữ liệu vào database đang chạy của bạn.
- **Không bao giờ:** cho agent thao tác nhóm cấm §3.3; đọc nhánh khác; đụng database `vinhomes_docker_*`/`vinhomes_eval*`; commit khi chưa được bảo.

## 7. Kết quả

| Bước | Đã làm | Kiểm bằng |
|---|---|---|
| T1 | Migration `0006`: bỏ 10 bảng hình agent (`agents`, `agent_versions`, `agent_releases`, `agent_runs`, `agent_teams`, `team_members`, `channel_agents`, `runtime_backends`, `runtime_identities`, `runtime_session_bindings`), thêm `integration_clients`, `delegations`, `integration_cases`; dữ liệu cũ mang sang (đã thử nâng một database dựng theo kiểu cũ); `reception_delegation.py` viết lại; Reception chạy như cũ (một lượt chat đầy đủ qua ủy quyền mới nằm trong `test_domain_database.py`) | `test_schema_contract.py` (danh sách bảng cấm), `test_domain_database.py` |
| T2 | `integration.py`: bí mật client, token ủy quyền, danh sách cho phép 45 công cụ (nay 46, thêm `resident.home_rules`), ghi kiểm toán với `initiator_kind='agent'`, `tools`, `me`, `delegations/self|finish`, lỗi đúng dạng | `test_integration_auth.py` (11 test) |
| T3 | Migration `0007`: 17 bảng (§2.1), bảng `state_transitions` (76 bước lấy thẳng từ `domain_spec.json` của bạn) và hàm chặn chuyển trạng thái, gán hạn SLA ở cơ sở dữ liệu, quyền cho vai trò API | `test_domain_entities.py` (8), `test_schema_contract.py` |
| T4 | `resident_services.py` (công nợ, khách, thẻ, đơn lễ tân, tiện ích, thi công, thông báo, báo khẩn), `operations_services.py` (cổng, bàn lễ tân, đóng tiện ích, thông báo) | `test_golden.py` G01, G03 đến G09 |
| T5 | `integration_cases.py` (hộp thư hồ sơ, kết quả, **đề xuất phương án**, nguồn sự kiện, gói tri thức, lát cắt OpenAPI), `jobs.py` (tác vụ hạn), `events.py`; `GET /tickets?overdue=true` | `test_golden.py` G02, G11, G12; `test_request_presentation.py` (hai test từng bị bỏ qua nay chạy) |
| T6 | `mock_data.py`, `import_data.py`, lệnh `mock`, `import`, `client`, `reset` | `test_import.py` (4), `test_database_tool.py` (2), mọi test golden chạy trên thế giới mẫu |
| T7 | `test_golden.py`: 12 kịch bản + gói tri thức | 13 test |

Số liệu sau đợt này: 120 bảng (113 bật RLS bắt buộc; 7 bảng chung), 103 trigger (sau migration `0008` xóa 8 bảng không dùng: 112 bảng, 105 bật RLS bắt buộc, 95 trigger; xem [KIEM_KE_BANG.md](KIEM_KE_BANG.md); migration `0009` thêm hàm `app_ensure_case`, không thêm bảng, và kịch bản G13 cùng test đăng nhập chung đưa số test backend lên 123 qua, 10 bỏ qua; app cư dân 25 test, app nhân viên 113 test), 242 thao tác API (215 đường dẫn), backend 121 test qua (10 bỏ qua, xem dưới) trên database dựng từ gói, Reception 373 test qua.

**Khác với kế hoạch:** (1) hàm quy tắc "ai được chuyển trạng thái" (`actors`) mới được ghi trong dữ liệu và kiểm ở tầng API cho bàn lễ tân; chưa có kiểm ở cơ sở dữ liệu. (2) Không thêm phụ thuộc Python: múi giờ của tiện ích tính trong PostgreSQL vì Python trên Windows không có cơ sở dữ liệu múi giờ. (3) `execution_principals` vẫn còn, chỉ phục vụ chủ sở hữu tệp. (4) Quy tắc khách tự duyệt (khách gia đình hoặc giao hàng, tối đa 5 người) và hạn mức thẻ (6 thẻ cư dân, 4 thẻ xe mỗi căn) lúc đầu là hằng số trong mã; nay là cấu hình theo phân khu (bảng `zone_settings`, migration `0012`, xem [NAP_DU_LIEU.md](NAP_DU_LIEU.md)).

## 8. Đợt hoàn thiện sau kiểm kê (09/10/2026)

| Việc | Kết quả | Kiểm bằng |
|---|---|---|
| Thông báo cho nhân viên khi có việc mới | Migration `0010`: mỗi phân công ở trạng thái `offered` (giao tay, phương án được duyệt, việc xếp hàng chờ) tạo đúng một thông báo trong app cho nhân viên; app nhân viên hỏi lại danh sách mỗi 30 giây khi tab bị ẩn. Chưa đẩy push/SMS/email | `test_staff_notifications.py`, `polling.test.ts` |
| Lịch sử xử lý cho thế giới mẫu | `mock` tạo cho mỗi yêu cầu lịch sử: cuộc trò chuyện, sự kiện theo thứ tự, tiếp nhận, phương án đã duyệt, phiếu việc, phân công (không quá sức chứa nhân viên), hồ sơ cư dân với dòng thời gian; migration `0011` sửa hồ sơ của yêu cầu "đã xử lý" thành chờ cư dân xác nhận | `test_mock_history.py` (6) |
| Quy tắc cứng thành cấu hình theo phân khu | Migration `0012`: bảng `zone_settings` và hàm `app_zone_rules`; nạp bằng tệp `zone_settings`; đọc ở `GET /resident/units/{id}/rules` và công cụ `resident.home_rules` | `test_zone_rules.py` (6), `test_import.py` (2) |
| Dọn dữ liệu giả cũ ở app nhân viên | Màn hình thật: bỏ cột agent và kết nối ngoài ở trang Đơn vị quản lý (trước đó hiện NaN vì API không còn trả các số này), nhãn Nhật ký chỉ còn các sự kiện domain thật (và có nhãn cho sự kiện khách, thẻ, tiện ích, đơn dịch vụ), bỏ kiểu và hàm cho `model-registry` không còn route. Chế độ xem trước: bỏ phiên điều phối nhiều agent (thẻ, báo giá, đóng phiên), trang nhóm với agent, và dữ liệu mẫu tương ứng. Hơn 2.100 dòng bị xóa | `operations-admin.test.tsx`, toàn bộ 114 test của app |

Chưa dọn, có chủ ý: các tác nhân loại `AGENT` trong dữ liệu mẫu xem trước (tin nhắn, yêu cầu duyệt do "agent" tạo) vì domain vẫn có agent ngoài đề xuất phương án; vai trò "giám sát vệ sinh" (người thật, không phải Supervisor).
