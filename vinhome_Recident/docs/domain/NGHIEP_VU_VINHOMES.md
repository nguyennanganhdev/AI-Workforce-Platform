# Nghiệp vụ Vinhomes — những gì gói `vinhome_Recident` thực sự cài đặt

Tài liệu mô tả **đúng và đủ** các quy trình nghiệp vụ mà mã, dữ liệu mẫu, tài liệu và giao diện trong thư mục `vinhome_Recident/` (nhánh `dev_Vinhome`) đang thể hiện. Không suy diễn từ kiến thức chung về quản lý chung cư. Điều gì không kiểm chứng được ghi là **"chưa xác minh"**. Những thứ tài liệu hoặc giao diện nhắc tới nhưng backend không có nằm ở mục 6.

## 1. Phạm vi, nguồn và quy ước trích dẫn

### 1.1 Nguồn đã đọc

Chỉ các tệp trong `vinhome_Recident/`: backend `services/vinhomes-api` (mã, `scripts/*.sql`, `scripts/*.py`, `migrations/`, `tests/`), `apps/resident-web`, `apps/staff-web`, `agents/reception`, `packages/shared`, `deploy/`, `docs/`, `README.md`. Không đọc nhánh git khác, không đọc tệp `.env` thật (chỉ tệp `*.example`, và chỉ tên biến).

### 1.2 Cách đọc trích dẫn `đường_dẫn:dòng`

Mọi đường dẫn tính từ `vinhome_Recident/`. Để gọn, các tiền tố sau được rút ngắn:

Quy ước: một trích dẫn trần dạng `:NNN` hoặc `:NNN-MMM` nghĩa là cùng tệp với trích dẫn đầy đủ gần nhất đứng trước nó trong cùng đoạn, mục danh sách hoặc ô bảng.

| Viết trong tài liệu | Nghĩa đầy đủ |
|---|---|
| `v3_mutations.py:448`, `work_orders/lifecycle.py:23` (tên module trần) | `services/vinhomes-api/src/vinhomes_api/v3_mutations.py` … |
| `scripts/…` | `services/vinhomes-api/scripts/…` |
| `migrations/…` | `services/vinhomes-api/migrations/…` |
| `staff/…` | `apps/staff-web/src/features/vinhomes-operations/…` |
| `staffsrc/…` | `apps/staff-web/src/…` (ngoài thư mục `features/vinhomes-operations`) |
| `resident/…` | `apps/resident-web/src/…` |
| `reception/…` | `agents/reception/…` (ví dụ `reception/src/runtime/service.py`) |
| `schema/…` | `services/vinhomes-api/src/vinhomes_api/schema/…` (bản nháp lược đồ, chỉ dùng ở Phụ lục D) |
| `deploy/…`, `docs/…`, `packages/…`, `README.md` | đúng đường dẫn tính từ gốc gói |

`services/vinhomes-api/README.md` luôn viết đủ để không nhầm với `README.md` ở gốc.

### 1.3 Bốn điều cần biết trước khi đọc

1. **Lược đồ database V3 không nằm trong gói.** Các bảng nghiệp vụ chính (`tickets`, `work_orders`, `work_assignments`, `work_approvals`, `users`, `scoped_user_roles`, …) và các bảng `vh_*` mở rộng được tạo bởi `server/scripts/migrate.ts` / `server/drizzle/*` (nằm ngoài gói: `scripts/setup_demo_database.ps1:15`, `scripts/setup_password_database.py:45`, `scripts/provision_connected.py:62`, `services/vinhomes-api/README.md:27-29`). Trong gói chỉ có 16 bảng `vh_*` của Alembic (`migrations/versions/0002…0015`), trong đó **chỉ `vh_command_receipt` còn được mã đang chạy dùng** (`v3_reception_operations.py:157,182`). Hệ quả: **không có CHECK constraint, enum hay khóa ngoại nào của bảng V3 để trích**. Mọi "trạng thái cho phép" dưới đây lấy từ mã (`Literal`, từ điển chuyển trạng thái, câu `where status …`), không phải từ ràng buộc DB. Xem mục 6.1.
2. **Backend "đang chạy" là các router của `main.py`** (`main.py:81-176`). Các module `actions/`, `approvals/`, `commands/`, `db/`, `events/`, `evidence/`, `incidents/`, `outbox/`, `qc/`, `resolution/`, `rules/`, `tasks/`, `work_orders/` và `demo_api.py` **không được gắn route** (`services/vinhomes-api/README.md:7`, `main.py`): xem mục 5.2.
3. **Giao diện "nối thật" chỉ phủ một phần.** Staff-web có tầng "preview/mock" (`staff/workspace/`, `staff/mock/`, `staff/hooks/use-operations-data.ts`, bật bằng `VITE_ENABLE_UI_PREVIEW`, `staff/auth/demo-access.ts:6`) — chỉ ghi nhận là có, không mô tả. Ở chế độ nối thật, `OperationsLayout` luôn vẽ `ConnectedOperations` và **không vẽ `<Outlet/>`** (`staff/layout/operations-layout.tsx:11-13`), nên các route con như `security`, `sanitation`, `contractor`, `approvals` chỉ hiện thông báo "Chức năng chưa được nối đầy đủ" (`staff/connected/ConnectedOperations.tsx:354-361,470-477`). Giao diện duy nhất của backend cho các luồng còn lại là trang demo `/demo/ui` (chỉ bật khi `VINHOMES_API_DEMO_MODE=1`, `main.py:177-183`).
4. **Cây làm việc đang thay đổi trong lúc tôi viết.** Khi tôi đọc, Alembic (`migrations/`), các gói `vh_*` thế hệ cũ và `scripts/seed_v3_*.sql` còn nguyên; về sau một tiến trình khác xóa/chuyển chúng (staged `D`/`R`) và thêm bản nháp lược đồ vào `src/vinhomes_api/schema/` (chưa commit). Quy ước: **trích dẫn trỏ về nội dung tôi đã đọc; với các tệp bị xóa/chuyển (chưa từng bị sửa) đó cũng là nội dung ở `HEAD` của `dev_Vinhome`** (ví dụ `scripts/seed_v3_faker.sql:30`, `migrations/versions/0013…`, `rules/demo.py:8`); bản nháp lược đồ chỉ xuất hiện ở Phụ lục D và vài chú thích ghi rõ "bản nháp". Mã nghiệp vụ đang gắn route, `agents/reception` và `apps/*` tôi đã đọc không đổi trong suốt thời gian đó (kiểm bằng thời điểm sửa tệp).

### 1.4 Bảng tóm tắt các quy trình

| # | Quy trình | Backend | Màn hình nối thật | Màn hình demo `/demo/ui` |
|---|---|---|---|---|
| 3.1 | Đăng ký, đăng nhập, tài khoản | có | resident: `/login` `/register`; staff: `/operations/login`, trang Tài khoản | không |
| 3.2 | Cư dân báo sự cố bằng form/chat trong app | có | resident: Trợ lý + form 3 bước | có |
| 3.3 | Hồ sơ "Case" của cư dân (hợp đồng v0.1) | có | **không có** (không app nào gọi) | không |
| 3.4 | Cư dân báo sự cố qua agent Reception | có (cần runtime) | resident: Trợ lý | một phần (trả lời mẫu) |
| 3.5 | Định tuyến ticket về đơn vị quản lý, tiếp nhận | có | staff: Công việc → Tiếp nhận | có |
| 3.6 | Triage (đánh giá, quyết định, duyệt) | có | **không có** | có |
| 3.7 | Thiết lập đơn vị quản lý, phạm vi, nhân sự | một phần | staff (quản trị): Đơn vị quản lý | không |
| 3.8 | Phiếu thi công, phân công, nhận/từ chối | có | staff: Công việc; Việc của tôi | có |
| 3.9 | Luồng hiện trường, bằng chứng ảnh | có | staff (field): Việc của tôi | có |
| 3.10 | Đề xuất sửa chữa/báo giá và đồng ý tại chỗ | có | staff (field) + resident | không |
| 3.11 | Khóa nước / gián đoạn dịch vụ | có | **không có** | có |
| 3.12 | Quyền thao tác kỹ thuật, đo đạc, tài sản, bảo trì | có | **không có** | không |
| 3.13 | Ngân sách | có | **không có** | có |
| 3.14 | Phương án (plan) của BQL và cư dân | có | **không có** (resident chỉ có đường qua Supervisor) | không |
| 3.15 | QC, làm lại, đóng ticket, cư dân xác nhận, đánh giá | có | staff: Nghiệm thu; resident: xác nhận | có |
| 3.16 | Vệ sinh (kế hoạch) và nhà thầu | có (lưu JSON) | **không có** | có |
| 3.17 | An ninh | có | **không có** | có (3 phần) |
| 3.18 | Hóa đơn, thanh toán, doanh thu | có (thanh toán chỉ demo) | **không có** | không |
| 3.19 | Báo cáo và xuất DOCX | có | staff: Báo cáo (2 loại) | có |
| 3.20 | Nhật ký kiểm toán, tổng quan quản trị | có | staff (quản trị): Nhật ký, Tổng quan | không |
| 3.21 | Tệp, ảnh, lưu trữ đối tượng | có | cả hai app | có |
| 3.22 | Thông báo, sự kiện, outbox | một phần | resident: không đọc bảng thông báo | có |
| 3.23 | SLA | **không có** | hiển thị cột hạn | — |
| 3.24 | Trao đổi Reception ⇄ Supervisor (phần còn sót) | có | resident: thẻ phản hồi | — |

## 2. Vai trò và phạm vi truy cập

### 2.1 Mã vai trò

| Mã | Ý nghĩa trong mã | Nguồn |
|---|---|---|
| `customer` | cư dân; dùng trong bảng `scoped_user_roles`; cư dân thao tác bằng `resident_connection` chỉ cần tenant membership `active`, không cần dòng vai trò | `password_auth.py:194`, `v3_auth.py:103-123`, `scripts/seed_v3_faker.sql:22-28` |
| `staff` | nhân viên hiện trường (kỹ thuật, an ninh, vệ sinh — phân biệt bằng chuyên môn, xem 2.4) | `password_auth.py:194`, `v3_auth.py:88` |
| `management` | Ban quản lý (BQL) | `password_auth.py:194`, `v3_auth.py:88` |
| quản trị viên | **không phải** `role_code`: là dòng trong bảng `platform_admins` | `v3_auth.py:76-80`, `password_auth.py:185-190` |

Danh sách giá trị cho `role_code` chỉ được ràng buộc ở tầng Pydantic (`Literal["customer","staff","management"]` tại `password_auth.py:194,199`, `v3_accounts.py:248`); CHECK ở DB: **chưa xác minh**.

Vai trò suy ra cho giao diện: `GET /operations/me` trả `admin` nếu là quản trị viên, `management` nếu có vai trò management đang hiệu lực, còn lại `staff` (`v3_operations.py:41-53`).

Ở chế độ demo, header `X-Demo-Actor` ∈ {`resident`,`management`,`technical`,`security`,`admin`} ánh xạ sang user `local-v3-*` (`v3_auth.py:21-27`), chỉ chạy trên loopback và đúng tenant `11111111-1111-5111-a111-111111111111` (`v3_config.py:56-66`).

### 2.2 Ba loại kết nối và cổng kiểm tra

| Loại | Điều kiện được vào | Nguồn |
|---|---|---|
| `scoped_connection` (mọi route vận hành) | user `users.status='active'`; và là quản trị viên **hoặc** có `tenant_memberships.status='active'` cùng dòng `scoped_user_roles` còn hiệu lực với `role_code in ('management','staff')`; không thì 403 "Operations role required" | `v3_auth.py:58-100` (dòng 88, 95) |
| `resident_connection` | user `active` + tenant membership `active` | `v3_auth.py:103-123` |
| `delegated_scope` (route `/internal/reception/*`) | token ủy quyền ký HMAC của một lượt Reception, hiệu lực ≤ 601 giây, đối chiếu lại `agent_runs`, binding, quyền cư dân mỗi lần gọi | `reception_delegation.py:44-89,183-207` |

Mỗi giao dịch đặt `app.tenant_id` và `app.user_id` để row level security của DB hoạt động (`v3_auth.py:66-69` và `services/vinhomes-api/README.md:13`; nội dung chính sách RLS: **chưa xác minh**, nằm ngoài gói).

### 2.3 Hai "cổng" đăng nhập cho nhân viên

Phiên đăng nhập tách theo header `X-Vinhomes-Surface` ∈ {``, `operations`, `field`, `resident`} với cookie tương ứng `vinhomes_session` / `vinhomes_staff_session` / `vinhomes_resident_session` (`password_auth.py:22-27,76-84`). Cổng `field` chỉ nhận vai trò `staff`; cổng `operations` từ chối `staff`; cổng rỗng nhận mọi vai trò (`v3_operations.py:29-35`, trả 403 `WRONG_DOOR` ở `:50-51`). Triển khai: cùng một image web, khác `VINHOMES_SURFACE` (`deploy/README.md`, mục "Một image, hai cổng đăng nhập").

### 2.4 Các loại nhân viên hiện trường

Không có cột "loại nhân viên". Loại được suy ra từ chuyên môn `staff_specialties.category_id` trỏ tới `service_categories.code` (`technical`, `security`, `cleaning`; xem 4.1). Ví dụ: nhân viên an ninh là người có chuyên môn category `security` (`scripts/seed_v3_faker.sql:54-57`); mã kiểm tra "việc an ninh" là `service_categories.code='security'` (`v3_mutations.py:506,594`, `v3_security.py:444`). Giao diện nối thật chỉ có một vai trò `staff` ("Nhân viên hiện trường", `staff/layout/connected-operations-shell.tsx:74`); các vai trò `technical/security/sanitation` trong `staff/workspace/model.ts:1-8` thuộc lớp preview.

### 2.5 Các loại phạm vi truy cập (`access_scopes.kind`)

Giá trị được mã dùng: `tenant`, `site`, `zone`, `building`, `management` (cột đi kèm: `site_id`, `zone_id`, `building_id`, `management_unit_id`) — `v3_auth.py:152-156`, `scripts/provision_connected.py:111-124`. Quản trị tạo đơn vị quản lý sinh thêm scope `management` và scope `building` nếu chưa có (`v3_admin.py:91-95`). Gán quyền: quản trị viên tạo/sửa tài khoản (`password_auth.py:206-236`):

* BQL không gắn đơn vị → scope `tenant` (toàn tenant) (`:230-233`);
* BQL gắn một đơn vị → scope `management` của đơn vị đó, đồng thời vào các phòng `channels.kind='management'` của workspace đơn vị (`:222-229`);
* `staff` và `customer` tạo bằng màn hình này cũng nhận scope `tenant` (`:230-235`), trong khi dữ liệu mẫu cho `staff` scope `site` (`scripts/seed_v3_demo_ui.sql:7-14`, `scripts/provision_connected.py:168`).

### 2.6 Cách xác định một ticket có hiển thị cho một người hay không

**Cư dân:** chỉ ticket có `tickets.requester_user_id = người đó` (`v3_resident.py:441,455`; `v3_plans.py:202`; `v3_ticket_result.py:33`); cuộc trò chuyện phải do chính họ tạo và họ là thành viên (`v3_resident.py:26-39`); căn hộ phải có `unit_residents.verification_status='verified'` trong khoảng `valid_from`…`valid_to` và đơn vị/tòa/site/domain đều `active` (`resident_cases.py:16-26`, `v3_resident.py:297-317`).

**Quản trị viên (platform_admins):** thấy mọi ticket của tenant (`:is_admin` ở `v3_auth.py:133`).

**BQL và nhân viên:** `TICKET_VISIBILITY` (`v3_auth.py:131-158`) đòi **đồng thời**:

1. `tickets.tenant_id` = tenant hiện tại;
2. membership `active` và một dòng `scoped_user_roles` còn hiệu lực (`valid_from<=now()` và `valid_to` rỗng hoặc tương lai) (`:137,150`);
3. vai trò là `management` — **hoặc** `staff` mà (a) có `work_assignments` trạng thái `offered`/`accepted`/`completed` trên một phiếu của ticket, qua `staff_profiles.user_id` đang `active`, **hoặc** (b) là người nhận một `security_alert_deliveries` của ticket (`:138-149`);
4. phạm vi của dòng vai trò khớp ticket: `tenant`; hoặc `management` với `management_unit_id = tickets.management_unit_id`; hoặc `site` với `tickets.site_id`; hoặc `zone` với `tickets.zone_id`; hoặc `building` với `tickets.building_id` (`:152-156`).

Hệ quả: nhân viên bị từ chối (`rejected`), hủy (`cancelled`) hoặc hết hạn không còn nhìn thấy ticket (chỉ `offered`/`accepted`/`completed` được tính, `:144`).

**Các kiểm tra ghi (mutation) dùng phạm vi hẹp hơn hoặc khác:**

| Hàm | Quy tắc | Nguồn |
|---|---|---|
| `management_access` | quản trị viên, hoặc `management` với scope `tenant`/`management` (đúng đơn vị)/`site`/`zone`/`building` khớp ticket | `v3_mutations.py:67-85` |
| `_responsible_management` | cùng quy tắc, dựa trên đơn vị/site/zone/tòa của phiếu | `v3_water.py:66-83` |
| `building_access` | quản trị viên hoặc `staff`/`management` với scope `tenant`/`building`/`site`/`zone` | `v3_security.py:31-49` |
| `site_access` (an ninh) | quản trị viên hoặc `staff`/`management` với scope **chỉ** `tenant` hoặc `site` | `v3_specialized.py:48-67` |
| `_management_building` (báo cáo) | quản trị viên hoặc `management` có scope bao tòa, kể cả qua `management_coverage` của scope `management` | `v3_reports.py:21-57` |
| `can_review` (triage) | quản trị viên hoặc `management` với scope `tenant`, đúng scope yêu cầu, hoặc `site`/`zone` chứa tòa của scope yêu cầu | `v3_triage.py:19-36` |
| Quyết định phê duyệt khóa nước | `management` bao ticket **và** (nếu có) đúng `requested_to_user_id`, đúng `required_scope_id` hoặc scope `tenant` | `v3_operations.py:340-361` |

Nhân viên chỉ ghi được trên phiếu mà họ có `work_assignments.status='accepted'` (`v3_mutations.py:459-467`, `v3_water.py:53-63`, `v3_technical.py:54-64`).

### 2.7 Giới hạn tần suất

Đăng nhập/đăng ký: 60 lần/IP và 10 lần/tài khoản trong 300 giây, trả 429 `Retry-After: 300` (`password_auth.py:63-73`). Hợp đồng cư dân và vận hành: 120 yêu cầu/phút/người (`resident_api.py:28-43`). Tin nhắn cư dân tới trợ lý: `VINHOMES_API_RESIDENT_MESSAGES_PER_MINUTE`, mặc định 30/phút (`v3_config.py:35,106`, `v3_resident.py:180-186`).

## 3. Các quy trình nghiệp vụ

Mỗi quy trình có sáu phần: **Tác nhân**, **Kích hoạt và các bước**, **Trạng thái và chuyển trạng thái**, **Quy tắc nghiệp vụ**, **Dữ liệu**, **Nguồn**. Ký hiệu "UI nối thật" là staff-web/resident-web ở chế độ kết nối backend; "UI demo" là `/demo/ui` (chỉ bật ở chế độ demo).

---

### 3.1 Đăng ký, đăng nhập và quản lý tài khoản

**Tác nhân.** Cư dân (tự đăng ký); BQL và nhân viên (do quản trị viên tạo hoặc duyệt); quản trị viên (`platform_admins`). Kiểm tra vai trò: `administrator()` đòi dòng trong `platform_admins` (`password_auth.py:185-190`); các route `/admin/accounts*` dùng `admin()` (`v3_accounts.py:22-24`). Đăng nhập bằng mật khẩu chỉ bật khi `VINHOMES_API_PASSWORD_AUTH=1`, loại trừ với demo/dev/auth ngoài (`v3_config.py:53-55`, `password_auth.py:55-60`).

**Kích hoạt và các bước.**

1. *Cư dân đăng ký*: UI resident `resident/features/auth/AuthPage.tsx` (chế độ `register`) → `resident/features/auth/auth-service.ts:34-37` → `POST /auth/register` (`password_auth.py:363-382`). Tạo `users` (`status='active'`), `accounts` (nhà cung cấp `vinhomes-password-v1`), `tenant_memberships` (`status='pending'`) (`:378-381`). **Không** tạo vai trò, **không** gắn căn hộ, **không** ghi số điện thoại. Trả `{"nextStep":"membership-pending"}`.
2. *Đăng nhập*: `POST /auth/login` (`:133-162`). Định danh khớp `lower(email)` hoặc `phone_e164`; membership `active` hoặc `pending` (`:140-147`). Luôn chạy băm scrypt cả khi tài khoản không tồn tại (`:148-151`). Tạo `sessions` hạn 8 giờ (`:29,158`), xóa phiên cũ của cùng cổng (`:155-157`), cookie `httponly`, `samesite=lax`, `secure` nếu https hoặc `VINHOMES_API_SECURE_COOKIES=1` (`:160`).
   * Cư dân: sau đăng nhập gọi `/auth/session` rồi `/resident/me` để chọn bước `administration` / `membership-pending` / `verification-required` (không có căn hộ xác minh) / `ready` (`resident/features/auth/auth-service.ts:26-33`); màn hình trạng thái ở `resident/features/auth/ResidentAccountStatus.tsx:16-57`.
   * Nhân viên/BQL: `staff/auth/auth-service.ts:23-45` đăng nhập rồi gọi `/operations/me`; sai cổng thì đăng xuất lại và báo (`:32-37` của cùng tệp; điều kiện ở `v3_operations.py:29-35`).
   * Phiên và đăng xuất: `GET /auth/session` (`:165-173`), `POST /auth/logout` (`:176-182`).
3. *Quản trị duyệt đăng ký / gán vai trò*: UI `staff/connected/admin/Accounts.tsx` (khối "tài khoản đang chờ bạn duyệt" dòng 135-176, nút "Duyệt"; hộp thoại sửa vai trò dòng 609-719) → `PATCH /auth/accounts/{id}` với `{role,status,management_unit_id?}` (`staffsrc/lib/admin/queries.ts:34-38`) → `grant_access` (`password_auth.py:206-236`): khóa dòng membership (`:211`), đặt `tenant_memberships.status` (`:214`), đóng mọi `scoped_user_roles` còn hiệu lực bằng `valid_to=now()` (`:215`), tạo dòng vai trò mới với scope phù hợp (xem 2.5), xóa mọi phiên `vinhomes-v1:%` của người đó (`:236`).
4. *Quản trị tạo tài khoản*: `POST /auth/accounts` (`:265-283`) với `role ∈ {customer, staff, management}`, mật khẩu 12–128, `management_unit_id` tùy chọn; UI `staff/connected/admin/Accounts.tsx:478-581`. Tạo user, account, membership `pending` rồi gọi ngay `grant_access(...,'active')`.
5. *Khóa / mở khóa*: `PATCH /auth/accounts/{id}` với `status ∈ {active, suspended}` (`:198-203`); UI nút "Khóa truy cập" (`staff/connected/admin/Accounts.tsx:290,636-643`).
6. *Đặt lại mật khẩu (do quản trị)*: `POST /auth/accounts/{id}/password` (`:311-331`), UI qua `resetPasswordMutationOptions` (`staffsrc/lib/admin/queries.ts:40-44`). Ghi `audit_events` loại `account.password_reset` (`:329-330`). **Cư dân không có cách tự đặt lại mật khẩu**: `requestPasswordReset` luôn ném lỗi (`resident/features/auth/auth-service.ts:38-42`), màn hình nói chưa hỗ trợ (`resident/features/auth/AuthPage.tsx:254`).
7. *Tự đổi mật khẩu*: `POST /auth/change-password` (`:385-399`), UI `staff/layout/change-password.tsx:19`. Xóa mọi phiên của người dùng (`:396`).
8. *Xóa tài khoản chưa có lịch sử*: `DELETE /auth/accounts/{id}` (`:334-360`); xóa lần lượt `sessions`, `channel_memberships`, `workspace_members`, `scoped_user_roles`, `tenant_memberships`, `accounts`, `users` trong một savepoint; nếu DB từ chối vì có bản ghi tham chiếu thì 409 và hướng dẫn dùng "Khóa truy cập" (`:348-357`). Ghi `account.deleted` (`:358-359`).
9. *Đường quản trị thứ hai `/admin/accounts*`* (`v3_accounts.py`): liệt kê (lọc `pending|active|suspended|ended`, `:64-85`), tạo (chỉ `demo_mode`, `:96-105`), thêm membership (`:153-183`), **quyết định** `approve|reject|activate|suspend|delete` kèm `reason` và `expected_updated_at` (`:186-231`), lịch sử (`:234-244`), xem/cấp vai trò theo `scope_id` (`:252-314`). **Không giao diện nào gọi nhóm route này**: UI quản trị chỉ gọi `/auth/*` và `/admin/units|overview|audit-events` (`staffsrc/lib/admin/queries.ts:22-87`, `staff/connected/admin/queries.ts:40-103`).

**Trạng thái và chuyển trạng thái.** `tenant_memberships.status ∈ {pending, active, suspended, ended}` (`v3_accounts.py:69`; `password_auth.py:107` chấp nhận `active|pending` khi có phiên). Hai cách chuyển, **không đồng nhất**:

| Cách | Chuyển cho phép | Nguồn |
|---|---|---|
| `POST /admin/accounts/{id}/decision` | `approve`: pending→active; `reject`: pending→ended; `activate`: suspended→active; `suspend`: active→suspended; `delete`: (khác ended)→ended. Sai trạng thái nguồn → 409. `reject/suspend/delete` bị cấm với chính mình hoặc quản trị viên (403) | `v3_accounts.py:200-221` |
| `PATCH /auth/accounts/{id}` | đặt thẳng `active` hoặc `suspended`, **không kiểm trạng thái nguồn** (kể cả từ `pending` hoặc `ended`) | `password_auth.py:214,297-304` |

**Quy tắc nghiệp vụ.**
* Mật khẩu 12–128 ký tự khi đăng ký/tạo/đổi/đặt lại (`password_auth.py:117-126,307-309`); tên 2–100, email 5–254 (`:117-120`); email phải chứa `@`, không có khoảng trắng (`:366-368`).
* Đăng ký bằng email đã tồn tại trả thông báo chung, không lộ tồn tại (`:376-377`); khóa advisory theo email chống đăng ký trùng đồng thời (`:374`).
* Không sửa vai trò/khóa/đặt lại mật khẩu/xóa **chính mình hoặc quản trị viên khác** qua màn hình này (409) (`:301-302,319-320,342-343`).
* `management_unit_id` chỉ hợp lệ với vai trò `management` (422, `:207-208`); đơn vị phải có scope `management` (404, `:223-225`).
* Chuyển người dùng giữa đơn vị: rời mọi phòng `management` cũ, vào phòng của đơn vị mới (`:216-229`); BQL toàn tenant giữ nguyên các phòng (`:216-218`).
* Danh sách tài khoản giới hạn 200 dòng mới nhất (`:260`); vai trò hiển thị mặc định `customer` nếu không có vai trò hiệu lực (`:254-255`).
* Giới hạn thử đăng nhập: xem 2.7. Băm tối đa 2 phép scrypt đồng thời (`:31`), tham số `n=131072,r=8,p=1` (`:36,45`).
* **Không ghi nhật ký** khi tạo tài khoản hoặc `PATCH` vai trò/trạng thái qua `/auth/*` (chỉ đặt lại mật khẩu và xóa có `audit`); chỉ đường `/admin/accounts*` ghi `account_reviews` (`v3_accounts.py:45-61`).

**Dữ liệu.** Đọc/ghi: `users`, `accounts`, `sessions`, `tenant_memberships`, `scoped_user_roles`, `access_scopes`, `channel_memberships`, `channels`, `workspaces`, `workspace_members`, `audit_events`, `account_reviews`. Đọc: `platform_admins`, `management_units`, `unit_residents`, `units`, `buildings`. Dòng mới: `users(id,email,name,status)`, `accounts(id,account_id,provider_id,user_id,password)`, `tenant_memberships(tenant_id,user_id,status)`, `scoped_user_roles(tenant_id,membership_id,scope_id,role_code,granted_by,valid_from)` (`password_auth.py:279-281,235`). Mật khẩu lưu dạng `scrypt-v1$salt$hash`; mã phiên lưu dạng `vinhomes-v1:` + SHA-256 (`:34-37,51-52`).

**Nguồn.** `password_auth.py`, `v3_accounts.py`, `v3_config.py`, `v3_operations.py:29-53`, `staff/connected/admin/Accounts.tsx`, `staffsrc/lib/admin/queries.ts`, `resident/features/auth/*`, `staff/auth/auth-service.ts`.

---

### 3.2 Cư dân báo sự cố bằng ứng dụng (chat và form)

**Tác nhân.** Cư dân (có căn hộ đã xác minh); hệ thống (chọn đơn vị quản lý, tạo thông báo); BQL nhận. Kiểm tra: `resident_connection` (`v3_auth.py:103-123`), `_owned_chat` (`v3_resident.py:26-39`), căn hộ `verified` (`:297-317`).

**Kích hoạt và các bước** (UI resident `resident/services/use-connected-resident.ts`).

1. *Mở hội thoại*: `POST /resident/chats` (`v3_resident.py:98-112`; UI `:247-255`, tiêu đề mặc định "Hội thoại mới"). Tạo `channels(kind='reception', created_by=cư dân)` và `channel_memberships`. Danh sách `GET /resident/chats` (`:115-138`) kèm số tin chưa đọc; đánh dấu đã đọc `POST /resident/chats/{id}/read` (`v3_resident_support.py:51-59`).
2. *Gửi tin*: `POST /resident/chats/{id}/messages` (`v3_resident.py:156-220`; UI `resident/services/use-connected-resident.ts:308-351`). Tin chèn vào `messages` với `sender_kind='user'`, `visibility='customer'` (`:192-201`). Nếu cấu hình `VINHOMES_API_RECEPTION_URL`: chạy lượt Reception ở nền (`:203-207`, xem 3.4). Nếu chỉ ở chế độ demo: trả một tin mẫu cố định (`:208-219`). **Nếu không có cả hai thì tin không được ai trả lời** (không có nhánh khác trong `send_message`).
3. *Gửi ảnh kèm tin*: UI `store()` (`resident/services/use-connected-resident.ts:56-62`, dùng `packages/shared/direct-image-upload.ts:6-28`) → `POST /resident/chats/{id}/direct-uploads` (`direct_uploads.py:94-97`); khi kho S3 công khai được bật thì nhận chữ ký POST tới bucket rồi `POST /direct-uploads/{id}/complete` (`:106-149`); nếu không thì backend trả `{"storage":"api"}` và UI đẩy byte qua `POST /resident/chats/{id}/photos?filename&mimeType` (`v3_resident_support.py:62-124`). Chi tiết lưu trữ ở 3.21.
4. *Đường form* (khi Reception báo không trả lời được, câu có chữ "biểu mẫu": `resident/services/chat-turn.ts:35-38`, câu dự phòng ở `v3_reception_runtime.py:31`): form ba bước `description → location → review` (`resident/services/chat-turn.ts:17-29`; `resident/services/use-connected-resident.ts:353-359`), cư dân chọn căn hộ, nhóm dịch vụ, nhập số điện thoại (`:360-370`) rồi `POST /resident/chats/{id}/tickets` kèm header `Idempotency-Key` (`:385-392`). `request_kind` luôn là `incident` (`:382`). Thành công thì chuyển tới `#/requests/{id}` (`:394`).
5. *Backend tạo ticket* — `create_resident_ticket` (`v3_resident.py:233-432`), xem Quy tắc.
6. *Theo dõi*: `GET /resident/tickets` (`:435-446`), `GET /resident/tickets/{id}` (`:449-475`: ticket, dòng thời gian chỉ gồm 8 loại sự kiện `ticket.created, ticket.routing_accepted, ticket.status_changed, work_order.status_changed, work_order.offered, work_assignment.responded, ticket.resolution_published, work_approval.decided` ở `:465-468`, và ảnh), `GET /resident/tickets/{id}/progress` (`v3_plans.py:303-335`, **UI không gọi**).
7. *Xác nhận kết quả hoặc yêu cầu xử lý lại*: xem 3.15.

**Trạng thái và chuyển trạng thái (ticket — dùng chung cho mọi quy trình).**

`tickets.status ∈ {open, triaging, assigned, in_progress, resolved, closed, cancelled}` (`v3_mutations.py:116`). `PATCH /tickets/{id}/status` chỉ cho phép (`TICKET_TRANSITIONS`, `:120-126`): `open→{triaging,cancelled}`, `triaging→{assigned,cancelled}`, `assigned→{in_progress,cancelled}`, `in_progress→{resolved,cancelled}`, `resolved→{closed}`; `closed`, `cancelled` là trạng thái cuối. Ngoài đường PATCH, mã đổi trạng thái ticket ở những chỗ sau (không đi qua từ điển trên):

| Chuyển | Điều kiện | Nguồn |
|---|---|---|
| (tạo) → `open` | tạo ticket | `v3_resident.py:357`, `v3_mutations.py:196` |
| → `assigned` | BQL tạo phiếu thi công thủ công; hoặc cư dân duyệt phương án và sinh phiếu | `v3_mutations.py:348`, `v3_plans.py:269-271` |
| → `in_progress` | phiếu chuyển `in_progress` | `v3_mutations.py:557-558` |
| → `resolved` | (ticket "có phương án") mọi phiếu bắt buộc đã xong; hoặc sau QC đạt toàn bộ (`publish_completion`) | `v3_mutations.py:554-556`, `v3_completion.py:29` |
| `resolved` → `in_progress` | QC mới được ghi khi ticket đang `resolved` | `v3_specialized.py:102-108` |
| → `closed` | cư dân đồng ý kết quả | `v3_resident.py:554-557` |
| → `in_progress` | (ticket có phương án) cư dân từ chối kết quả | `v3_resident.py:539-540,554-557` |
| → `triaging`, `reopen_count+1` | (ticket không phương án) cư dân từ chối kết quả | `v3_resident.py:558-561` |
| → `cancelled` | phê duyệt hủy việc an ninh làm hết phiếu; hoặc BQL qua PATCH | `v3_security.py:677-689`, `v3_mutations.py:121-125` |

Trạng thái hiển thị cho cư dân: `open/triaging/assigned→received`, `in_progress→processing`, `resolved→confirmation` (khi có phê duyệt `customer_completion` chờ) hoặc `processing`, `closed→completed`, `cancelled` (`resident/services/resident-api.ts:115-123`, nhãn `resident/services/types.ts:56-62`).

**Quy tắc nghiệp vụ** (`create_resident_ticket`, `v3_resident.py:233-432`).
* Đầu vào bị cấm trường lạ: `domain_id, building_id, unit_id, category_id`, `title` 1–300, `description` 1–10000, `contact_name` 1–200, `contact_phone` 1–30, `request_kind ∈ {incident, service_request}`, `file_ids` ≤ 3, `location` 3–500 (`:82-95`).
* *Hai kiểu idempotency*: (a) Ứng dụng cư dân gửi header `Idempotency-Key` dài 8–120, bắt buộc có `location`; cùng khóa cùng nội dung trả lại biên nhận đã lưu, khác nội dung 409 (`:246-261`); mỗi cuộc trò chuyện chỉ có **một** ticket theo đường này (409 "This chat already has a ticket", `:262-267`). (b) Đường agent dùng `idempotency_key` trong thân: id ticket sinh bằng `uuid5(tenant, kênh, người, khóa)`, lệch nội dung 409 (`:282-296`).
* Căn hộ phải `unit_residents.verification_status='verified'`, còn hiệu lực, cùng tòa/miền chỉ định, mọi bậc `active`; không thì 403 (`:297-317`).
* Đơn vị quản lý chọn từ `management_coverage` còn hiệu lực với nhóm dịch vụ `enabled`, đơn vị `active`; xếp theo độ cụ thể `building(4) > zone(3) > site(2) > tenant(1)` rồi `priority`; hai ứng viên đồng hạng khác đơn vị → 409 "Ambiguous management coverage"; không có → 404 (`:318-344`).
* Ticket mới: `status='open'`, `priority='normal'` (hoặc theo đánh giá của agent), mã `VH-` + 12 ký tự hex đầu của UUID (in hoa) (`:347-373`), `address_snapshot` gồm `building`, `unit`, `location` (`:368-370`).
* Sự kiện `ticket.created` mang `source='resident_chat'`, `requestHash`; với biên nhận thì **không** có cờ `requiresPlan` ⇒ ticket đi theo luồng "QC trước", còn đường agent mặc định gắn `requiresPlan:true` (`:375-381`; giải thích ở `v3_mutations.py:36-45`).
* Bản ghi định tuyến `ticket_routing_history(status='requested', reason='initial_reception_handoff')` (`:382-389`); thông báo trong ứng dụng cho mọi người dùng `management` thuộc phạm vi (`:390-413`) với khóa chống trùng `ticket:{id}:created`.
* Ảnh: tối đa 3; mỗi ảnh phải `ready`, cùng cuộc trò chuyện, do chính cư dân tải; bỏ `retention_until`; thêm `ticket_files(purpose='issue')` (`:414-427`).
* Đánh giá của agent (nếu có) bị kiểm: `priority ∈ {low,normal,high,critical}`, `severity ∈ {unknown,minor,moderate,major,critical,not_applicable}`, khẩn cấp thì `priority='critical'`, `reason` 1–2000 ký tự (`:269-281`).
* Nếu có dòng `ticket_events` cùng `idempotency_key`, mỗi sự kiện có `seq` tăng dần và làm tăng `tickets.version` (`v3_mutations.py:88-111`).

**Dữ liệu.** Ghi: `channels`, `channel_memberships`, `messages`, `tickets`, `ticket_events`, `ticket_routing_history`, `notification_deliveries`, `ticket_files`, `files`, `file_objects`, `file_uploads`, `execution_principals`, `vh_resident_public_events`/`vh_resident_outbox` (qua `append_domain_event`). Đọc: `unit_residents`, `units`, `buildings`, `sites`, `domains`, `management_coverage`, `access_scopes`, `management_units`, `service_categories`, `storage_locations`.

**Nguồn.** `v3_resident.py`, `v3_resident_support.py`, `direct_uploads.py`, `v3_ticket_result.py`, `v3_mutations.py:88-111`, `resident/services/use-connected-resident.ts`, `resident/services/chat-turn.ts`, `resident/services/resident-api.ts`, `packages/shared/direct-image-upload.ts`.

---

### 3.3 Hồ sơ "Case" của cư dân (hợp đồng v0.1) — có backend, không có giao diện

**Tác nhân.** Cư dân; BQL/quản trị (cổng nhập hồ sơ); hệ thống. Kiểm tra: cư dân qua `resident_scope` (người dùng + `OWNER` = `requester_user_id` và căn hộ `verified`, `resident_cases.py:28-35`); BQL qua `operations_scope` + `MANAGEMENT` (quản trị viên hoặc `management` có scope bao `site`/`building`/`zone`/`tenant`/`management` của hồ sơ, `:37-52`).

Hợp đồng nằm ở tiền tố `/api/domains/vinhomes/resident` và `/api/domains/vinhomes/operations/resident-cases` (`resident_contract.py:17-18`). **Không có ứng dụng nào trong gói gọi hợp đồng này**: resident-web gọi `/api/business/resident/*` (`resident/services/resident-api.ts:12`, `use-connected-resident.ts`), staff-web không có màn hình hồ sơ Case; tài liệu `docs/resident-web/README.md:10` còn gọi `resident-api.openapi.yaml` là "proposal cũ, không phải OpenAPI đang phục vụ" dù backend đã cài hợp đồng này. Có kiểm thử `tests/test_resident_contract.py`.

**Kích hoạt và các bước.**

Phía cư dân (`resident_api.py`):
1. `GET /me` (căn hộ xác minh + giới hạn tải ảnh) (`:114-122`).
2. `POST /photos` tải ảnh (form có đúng `file`, `apartmentId`) (`:125-131`, `resident_photos.py:101-153`).
3. `POST /requests` tạo hồ sơ (`:163-167`, `resident_cases.py:204-246`): kiểm căn hộ, kiểm ảnh, tạo kênh chat (qua `create_chat`), `vh_resident_cases` (mã `YC-` + 12 hex), `vh_resident_submissions`, gắn ảnh, sự kiện công khai "Đã tiếp nhận phản ánh".
4. `GET /requests` (lọc `all|open|completed`, `q` ≤ 100, `limit` 1–50, phân trang bằng con trỏ ký HMAC) và `GET /requests/{id}` (`:139-177`).
5. `POST /requests/{id}/confirm` và `/reopen` (`:175-177,223-225`, `resident_cases.py:249-274`).
6. `GET /requests/{id}/plans`, `POST /requests/{id}/plans/{plan}/decision` (gọi `v3_plans.resident_decision`) (`:186-220`).

Phía BQL (`/operations/resident-cases`):
7. Danh sách và chi tiết hồ sơ (`:249-265`); ảnh phản ánh của ticket liên kết `GET /tickets/{id}/resident-intake-photos` (`:70-111`).
8. *Biến thành ticket*: `POST /{case}/tickets` gọi lại `create_resident_ticket` (cần số điện thoại; nếu cư dân chưa có thì 422) rồi liên kết (`:286-311`); hoặc liên kết ticket có sẵn `POST /{case}/ticket-links` (`:314-326`).
9. *Công bố kết quả*: `POST /{case}/resolution` (`:329-380`).

**Trạng thái và chuyển trạng thái.** `vh_resident_cases.status` được mã đặt: `processing` (khi liên kết ticket, `resident_api.py:280`), `confirmation` (khi công bố, `:375`), `completed` (khi cư dân xác nhận), `processing` (khi cư dân yêu cầu xử lý lại, kèm xóa `current_resolution_id`) (`resident_cases.py:266-269`). Giá trị đầu khi tạo (`received`) không được mã đặt tường minh: **chưa xác minh** (mặc định ở DB ngoài gói).
Trạng thái công khai `public_status ∈ {received, processing, confirmation, completed}` được tính trong `PROJECTION` (`resident_cases.py:57-74`): `confirmation` chỉ giữ khi `basis_versions` của kết quả công bố **bằng** phiên bản hiện tại của mọi ticket liên kết; mọi sự kiện miền làm lệch phiên bản sẽ hạ về `processing` ngay (`:54-56,62`).

**Quy tắc nghiệp vụ.**
* Mô tả 8–5000 ký tự, vị trí 3–500, tối đa 3 ảnh không trùng (`resident_contract.py:23,31,38-45`); ảnh ≤ 10 MiB, JPEG/PNG/WebP, ≤ 20.000.000 pixel, ảnh được giải mã và mã hóa lại (`:20-21`, `resident_photos.py:21,34-56`); ảnh chưa gắn hồ sơ hết hạn sau 24 giờ (`resident_photos.py:139`, kiểm hạn `resident_cases.py:222-224`).
* Mọi lệnh ghi cần `Idempotency-Key` 8–128 ký tự ASCII (`resident_contract.py:279-287`); biên nhận `vh_resident_command_receipts` (khóa gồm tenant, người, thao tác, tài nguyên, khóa) trả lại kết quả cũ hoặc 409 `IDEMPOTENCY_CONFLICT` (`resident_cases.py:177-196`).
* Khóa lạc quan: `expectedVersion` so với `public_version = version hồ sơ + tổng version các ticket liên kết`; lệch → 409 `VERSION_CONFLICT` kèm `currentVersion` (`resident_cases.py:57-60,199-201`).
* Xác nhận/yêu cầu làm lại: phải đúng `resolutionRevision` hiện hành và trạng thái công khai `confirmation` (409 `RESOLUTION_CHANGED`/`INVALID_STATE`), `reason` 8–2000 ký tự khi làm lại (`resident_cases.py:255-260`, `resident_contract.py:53-55`).
* Công bố kết quả: hồ sơ phải còn mở và đã có ticket liên kết; **mọi** ticket liên kết ở `resolved`/`closed`; mọi phiếu bắt buộc `completed`; QC mới nhất của từng phiếu `pass` **và** `resolution-check.ready` (`resident_api.py:338-353`, dùng `v3_technical.resolution`); không công bố lại đúng nền phiên bản đã bị cư dân yêu cầu làm lại (`:354-358`); ảnh kết quả phải là bằng chứng `after|verification` đang `active`, đã quét `clean`, thuộc ticket liên kết (`:359-368`); tóm tắt 8–5000 ký tự, ≤ 20 ảnh (`resident_contract.py:156-158`).
* Ranh giới HTTP: giới hạn thân 64 KiB (12 MiB cho `/photos`) trước khi đọc, kiểm `Origin`, mọi phản hồi `Cache-Control: no-store` và `X-Correlation-ID` (`resident_contract.py:319-364`); con trỏ phân trang gắn chữ ký HMAC theo phạm vi truy vấn (`:294-316`); liên kết ảnh ký, hạn 900 giây (`resident_photos.py:24-31`).
* Chỉ thông báo công khai các nhãn nằm trong danh sách trắng (`ticket.routing_accepted`, `work_order.offered`, `work_assignment.responded`, `work_order.status_changed`, `work_order.qc_recorded`, `work_order.redo_created`, `ticket.status_changed`, `plan.proposed`, `plan.management_decided`, `plan.resident_decided`) (`resident_cases.py:153-174`).

**Dữ liệu.** Ghi: `vh_resident_cases`, `vh_resident_submissions`, `vh_resident_photos`, `vh_resident_case_tickets`, `vh_resident_public_events`, `vh_resident_outbox`, `vh_resident_command_receipts`, `vh_resident_resolutions`, `vh_resident_resolution_photos`, `vh_resident_resolution_responses`, `files`, `file_objects`, `execution_principals`. Đọc: `tickets`, `work_orders`, `vh_qc_results`, `evidence_items`, `vh_ticket_plans`, `storage_locations`.

**Nguồn.** `resident_api.py`, `resident_contract.py`, `resident_cases.py`, `resident_photos.py`, `docs/resident-web/resident-api.openapi.yaml`, `docs/resident-web/README.md`.

---

### 3.4 Cư dân báo sự cố qua agent Reception

**Tác nhân.** Cư dân; agent Reception (dịch vụ Python riêng, cổng 4202); backend (quyết định chính sách, ghi dữ liệu); BQL (nhận ticket). Reception **không có quyền riêng**: mỗi lượt có token ủy quyền gắn với đúng cư dân, kênh, binding (`reception_delegation.py:103-170`, `reception/README.md` mục "Ủy quyền").

**Kích hoạt và các bước.**

1. *Kích hoạt*: tin nhắn cư dân được ghi xong thì `dispatch_turn` chạy nền (`v3_resident.py:203-207`). `dispatch_turn` (`v3_reception_runtime.py:289-334`): (a) trả lời "không phản hồi được" cho các tin của cư dân bị bỏ sót từ 4 phút đến 1 ngày trước (`:297-307`); (b) mở một `agent_runs` + token ủy quyền (`reception_delegation.py:103-170`; token sống 600 giây, hợp lệ tối đa 601 giây `:162`, `read:54`); (c) `POST {RECEPTION_URL}/v1/turns` timeout 180 giây (`:310-316`); (d) đóng run và nếu thất bại ghi câu `UNAVAILABLE_REPLY` (`:326-334`; câu ở `:31`). Run `running` quá 15 phút bị đánh dấu `failed/abandoned` (`reception_delegation.py:127-130`).
2. *Runtime nhận lượt*: `POST /v1/turns` (`reception/src/runtime/service.py:241-318`), mỗi cuộc trò chuyện một khóa (`:257`). Chế độ do `RECEPTION_AGENT`: `loop` (mô hình dẫn dắt, **mặc định của bản đóng gói**: `deploy/compose.yml:62`, `deploy/deployment.env.example:26`) hoặc `graph` (quy trình cố định; mặc định của mã nguồn `reception/src/runtime/service.py:79`). Cả hai chế độ gọi `GET /internal/reception/v1/model-config` trước khi chạy (`reception/src/runtime/service.py:261-266`) — **route này không tồn tại ở backend** (xem 6.2).
3. *Chế độ `loop`* (`reception/src/runtime/service.py:161-199`; `reception/src/agent/*`):
   * Đọc ngữ cảnh: `GET /internal/reception/chats/{id}/context` (30 tin gần nhất, yêu cầu đang mở, 5 yêu cầu trước của chính cư dân; `v3_reception_runtime.py:157-191`), thao tác `get_verified_resident_context`, `GET /internal/reception/catalog` (nhóm dịch vụ `enabled`, `:75-78`), `POST /internal/reception/policy/evaluate` (`:81-104`).
   * *Khẩn cấp*: nếu chính sách trả `emergency` thì không gọi mô hình: `emergency_request()` (`reception/src/agent/tools.py:205-236`); trả câu cố định "Mình đã chuyển yêu cầu của bạn đến Ban quản lý ở mức khẩn cấp." cộng câu an toàn do BQL duyệt nếu có (`reception/src/runtime/service.py:172-175`); nếu không chuyển được thì khuyên gọi ngay bảo vệ/BQL (`reception/src/agent/loop.py:13-14`).
   * *Ảnh và câu trả lời bổ sung* khi đã có yêu cầu mở: `POST /internal/reception/chats/{id}/follow-up` gắn ảnh mới vào ticket và, nếu Supervisor đang chờ thông tin, chuyển **nguyên văn** tin cư dân thành `information_provided` (`v3_reception_runtime.py:220-256`; `reception/src/runtime/service.py:176-188`).
   * *Mô hình* được gọi tối đa 6 bước (`reception/src/agent/loop.py:10`) với 5 công cụ: `search_knowledge`, `file_request`, `report_emergency`, `request_status`, `cancel_request` (`reception/src/agent/tools.py:31-56`); câu trả lời cuối bị kiểm (không dùng từ nội bộ, không nêu con số lạ, không hứa thời gian/miễn phí, không nói "đã ghi nhận" khi chưa có hành động) và bị trả lại 1 lần rồi thay bằng câu an toàn (`reception/src/agent/loop.py:33-53,113-120`).
   * Mỗi lượt giới hạn 150 giây (`reception/src/runtime/service.py:47,273`).
4. *Lập yêu cầu* (`reception/src/agent/tools.py:135-195`): `file_request` → kiểm quy tắc tiếp nhận của backend (`POST /internal/reception/chats/{id}/intake`, `v3_reception_runtime.py:203-211`) → nếu đủ thì chuỗi thao tác `create_ticket_draft` → `update_ticket_incident` → `submit_ticket_assessment` → `resolve_management_destination` → `handoff_ticket` qua `POST /internal/reception/v1/execute` (`reception_runtime_api.py:38-43` → `v3_reception_operations.py:1270-1299`). Mỗi lệnh có khóa idempotency sinh từ kênh + id tin + bước (`reception/src/agent/tools.py:85-93`) và biên nhận `vh_command_receipt` trạng thái `IN_PROGRESS`→`COMPLETED` (`v3_reception_operations.py:147-216`).
   * Mười bốn thao tác hợp lệ (`Operation`, `:39-54`): `create_ticket_draft`, `get_verified_resident_context`, `update_ticket_incident`, `submit_ticket_assessment`, `resolve_management_destination`, `handoff_ticket`, `register_supervisor_wait`, `get_supervisor_event`, `append_ticket_information`, `respond_supervisor_interaction`, `request_ticket_cancellation`, `get_ticket_status`, `process_self_help`, `escalate_emergency`.
   * *Bàn giao* (`_handoff_draft`, `:852-1164`): thiếu `title, description, domain_id, building_id, unit_id, category_id, request_kind` hoặc đánh giá → `accepted:false` (`:865-892`); chỉ bàn giao khi quy tắc tiếp nhận báo `ready` **hoặc** là khẩn cấp (`:903-917`); cư dân phải có họ tên và `phone_e164`, thiếu → `accepted:false` (`:919-930`); tạo ticket qua `commit_draft` (`:965`); gắn ảnh (`:969-980`); nếu đơn vị quản lý không có Supervisor khả dụng thì **vẫn tạo ticket**, `team=None`, BQL xử lý thủ công (`:939-952,1008-1012`); ngược lại tạo `agent_teams`/`team_members` và lưu thông điệp `ticket_submitted` (mục 3.24). Cả hai chế độ agent gửi `plan_required:false` (`reception/src/agent/tools.py:153`, `reception/src/runtime/backend.py:327`) nên ticket của Reception đi theo luồng "QC trước" (không cần phương án).
5. *Chế độ `graph`* (`reception/src/graph/workflow.py:49-68`): 18 nút `receive_message, assess_request, answer_or_escalate, retrieve_self_help, emergency_handoff, create_ticket_draft, load_resident_context, collect_incident_details, submit_assessment, resolve_management_destination, handoff_to_supervisor, wait_for_supervisor, active_ticket_dialogue, process_supervisor_event, execute_operation, wait_for_operation, wait_for_resident, human_review`. Quyết định hành động do `decide_request` (`reception/src/graph/assessment.py:101-163`): chính sách khẩn cấp thắng; có ticket mở thì `continue_existing_ticket` (trừ câu hỏi thông tin thuần); mô hình đề xuất `ask_clarification` mà còn thiếu thì hỏi; `staff_required` thì `start_ticket`; câu hỏi thông tin thì `retrieve_knowledge`; tự xử lý chỉ khi chính sách cho phép (mà backend luôn trả `self_help_allowed:false`, `v3_reception_runtime.py:99`). Số lần hỏi lại tối đa 4 (`reception/src/graph/workflow_contracts.py:118`, `reception/src/graph/workflow.py:190`), quá thì vào `human_review` — nút này chỉ **chờ** tin tiếp theo của cư dân hoặc sự kiện, **không** chuyển cho BQL (`reception/src/graph/workflow.py:176-183,1288-1292`).
6. *Hỏi tiến độ*: `request_status` → thao tác `get_ticket_status` → `get_my_ticket` (`reception/src/agent/tools.py:238-243`, `v3_reception_operations.py:1241-1247`); nhãn tiếng Việt `reception/src/agent/tools.py:19-24`.
7. *Hủy yêu cầu*: `cancel_request` (`reception/src/agent/tools.py:245-257`) chỉ phát thông điệp `cancel_requested` tới Supervisor khi ticket đã được bàn giao cho một Supervisor; nếu không thì chỉ trả ghi chú "Đề nghị hủy được ghi trong hội thoại". Backend ghi thông điệp và không đổi trạng thái ticket (`v3_reception_supervisor.py:593-594`). **Ticket chỉ bị hủy bởi BQL** (PATCH trạng thái) hoặc phê duyệt hủy việc an ninh (3.17); staff-web không có nút hủy ticket.
8. *Kiến thức / hỏi thông tin*: `search_knowledge` gọi `{RECEPTION_KNOWLEDGE_URL}/internal/knowledge/search`; không đặt URL thì trả "Không có nguồn" (`reception/src/agent/tools.py:113-128`). Gói không chứa dịch vụ tri thức (`deploy/README.md`, mục "Những gì compose không làm"). `process_self_help` luôn trả 501 (`v3_reception_operations.py:1262-1266`).

*Khẩn cấp ở phía backend* — `escalate_emergency` (`v3_reception_operations.py:679-814`): ticket đã ở trạng thái cuối → 409; id tin nguồn phải là tin của chính cư dân trong kênh (422); nếu ticket chưa `is_emergency` thì đặt `priority='critical'`, `severity='critical'`, `is_emergency=true` và ghi `ticket.emergency_escalated`; nếu đã khẩn cấp từ lúc tạo thì dùng lại sự kiện `ticket.created` để không làm lệch phiên bản; tạo thông báo trong ứng dụng cho `management` thuộc phạm vi với khóa `ticket:{id}:emergency:{event}`; kết quả báo `deliveryStatus` `pending` hoặc `no_matching_bql_recipient`.
*Phát hiện khẩn cấp* (`v3_reception_runtime.py:36-104`): từ khóa theo loại — `fire` (cháy, bốc khói, khói bốc, khói đen, mùi khét, tia lửa, nổ lớn), `gas` (mùi gas, mùi ga, rò gas, rò rỉ gas), `electric` (chập điện, giật điện), `elevator` (kẹt thang máy, kẹt trong thang), `water` (ngập nước, vỡ ống nước), `structure` (sập trần); loại bỏ cụm vô hại (ví dụ "bóng đèn bị cháy") và cụm bị phủ định ("không có mùi khét"). Mô hình có thể **nâng** khẩn cấp (`proposed_action='emergency_handoff'`) nhưng không hạ được mức mà từ khóa đã thấy (`:86-87`). Câu hướng dẫn an toàn chỉ có khi BQL đã duyệt; hiện `guidance=None` (`:90`).

**Trạng thái và chuyển trạng thái.**
* `agent_runs.status`: `running` → `succeeded`|`failed` (`reception_delegation.py:153-156,173-180`; `failed/abandoned` khi quá 15 phút, `:127-130`).
* Biên nhận lệnh `vh_command_receipt.status`: `IN_PROGRESS` → `COMPLETED` (`v3_reception_operations.py:180-216`; `migrations/versions/0013_vh_command_receipt.py:37-47`, CHECK có trong gói). Gửi lại khi còn `IN_PROGRESS` → 409 `OPERATION_IN_PROGRESS`; dùng lại khóa với nội dung khác → 409 `IDEMPOTENCY_KEY_REUSED` (`:172-178`); `POST /internal/reception/v1/reconcile` trả `not_found|in_progress|completed` (`:1302-1346`).
* Bản nháp ticket (`messages.body.type='ticket_draft'`): `incidents[i]` có `ready` khi mọi trường khác null (`v3_reception.py:73-87`); `intake[i]` ghi `ready/review/missing/question` (`v3_reception_operations.py:329-332`).
* Ticket: như 3.2.

**Quy tắc nghiệp vụ.**
* *Nội dung yêu cầu là lời cư dân*: `title`/`description` lấy nguyên văn từ tin nhắn cư dân mà các dữ kiện dẫn tới (tiêu đề = dòng đầu ≤ 120 ký tự, mô tả ghép tối đa 10000), không dùng văn bản do mô hình viết (`reception_intake.py:122-126`). Một dữ kiện `customer_report` chỉ được giữ khi `value` có trong đúng tin nhắn nó dẫn và không bị phủ định ngay trước (`:54-58,96-109`); câu xác nhận trống ("ok", "vâng") không là dữ kiện (`:101-103`).
* *Điều kiện bàn giao một sự cố thường*: có `symptom`; và nếu là hỏng hóc (hoặc `service_request` mà mô tả có từ "hỏng/rò/…") thì phải có `item` (vật/điểm cụ thể, không chỉ tên phòng) hoặc `item_unknown` (cư dân nói không biết) (`:111-132`). Thiếu thì backend trả câu hỏi; hỏi tối đa `MAX_QUESTIONS = 2` lần cho `item`, sau đó bàn giao nguyên trạng, đánh dấu `review` (`:17,134-135`). Khẩn cấp không bị giữ lại để hỏi (`:129`).
* Ảnh của mọi tin cư dân trong cuộc trò chuyện được gắn vào yêu cầu khi tạo (`:141`, `v3_reception_operations.py:969-980`). Mô hình **không nhìn thấy ảnh**; tin chỉ có ảnh hiện cho mô hình là "[Cư dân gửi N ảnh, không viết gì]" (`reception/src/agent/loop.py:70-73`, `reception/src/agent/prompt.py:16-17`).
* Một cuộc trò chuyện một yêu cầu đang mở; sự cố khác phải bấm "Chat mới" (`reception/src/agent/tools.py:174-176`). Cư dân nhiều căn hộ phải chọn căn (`:182-183`); riêng khẩn cấp không hỏi, lấy căn đầu và ghi chú để BQL xác nhận (`:223-231`).
* Mức ưu tiên mô hình được chọn: `low|normal|high` (`reception/src/agent/tools.py:48`); `critical` chỉ do chính sách khẩn cấp (`:229`).
* Chặn đầu vào: tổng `input+context` ≤ 80 KB; id ngữ cảnh ≤ 200 ký tự (`v3_reception_operations.py:65-83`); `context.principalId` phải trùng người xác thực, `tenantId` phải trùng tenant (`:103-138`).
* Giới hạn tin nhắn 30/phút/người (`v3_config.py:35`); lượt tự dừng sau 150 giây (`reception/src/runtime/service.py:47`).

**Dữ liệu.** Ghi: `messages`, `channels`, `tickets`, `ticket_events`, `ticket_routing_history`, `notification_deliveries`, `ticket_files`, `vh_command_receipt`, `agent_runs`, `runtime_identities`, `runtime_session_bindings`, `execution_principals`, `agent_versions`, `agents`, `audit_events` (`reception.delegation_issued`), và khi có Supervisor: `agent_teams`, `team_members`, `vh_reception_supervisor_messages`. Đọc: `service_categories`, `unit_residents`, `management_coverage`, `workspaces`, `channel_agents`, `agent_releases`. Runtime còn tự lưu SQLite `reception_records` và checkpoint LangGraph (`reception/src/runtime/backend.py:59`, `reception/src/persistence/sqlite.py`).

**Nguồn.** `v3_reception.py`, `v3_reception_operations.py`, `v3_reception_runtime.py`, `reception_runtime_api.py`, `reception_intake.py`, `reception_delegation.py`, `reception/src/runtime/service.py`, `reception/src/runtime/backend.py`, `reception/src/agent/{prompt,tools,loop}.py`, `reception/src/graph/{workflow,assessment}.py`, `reception/README.md`, `deploy/compose.yml`.

---

### 3.5 Định tuyến ticket về đơn vị quản lý và BQL tiếp nhận

**Tác nhân.** Hệ thống (chọn đơn vị theo phạm vi phủ), BQL phụ trách (tiếp nhận), cư dân (nhận thông báo).

**Kích hoạt và các bước.**
1. *Chọn đơn vị lúc tạo ticket*: theo bảng độ cụ thể ở 3.2 (đường cư dân/agent, `v3_resident.py:318-344`; `v3_reception_operations.py:452-493`) hoặc `GET /management-units/resolve?buildingId&domainId&serviceCategoryId?` (`v3_routes.py:27-97`): tòa phải `active` trong miền (404); người gọi phải có phạm vi vận hành bao tòa (403, `:49-66`); với mỗi nhóm dịch vụ chọn dòng có (độ cụ thể, `priority`) cao nhất; hai đơn vị đồng hạng → 409; kết quả có nhiều đơn vị khác nhau theo nhóm mà không nêu `serviceCategoryId` → 409 (`:67-95`); không có phủ → 404 (`:91-92`). `POST /tickets` của BQL dùng chính hàm này (`v3_mutations.py:174-177`).
2. *Thông báo BQL*: xem 3.2 bước tạo ticket (`notification_deliveries` kênh `in_app`).
3. *BQL tiếp nhận*: UI nối thật `staff/connected/ConnectedOperations.tsx:536-551` (nút "Tiếp nhận" khi ticket `open|triaging`) → `POST /tickets/{id}/routing/ack` (`v3_operations.py:249-305`). Điều kiện: BQL có scope bao ticket (`tenant`/`management` đúng đơn vị/`site`/`zone`/`building`) (403, `:254-272`); tồn tại `ticket_routing_history` của đúng đơn vị và đang `requested` (404/409, `:273-284`). Hiệu lực: ghi sự kiện `ticket.routing_accepted`, đặt `ticket_routing_history.status='accepted'`, `acknowledged_at`, `ack_event_id`, và gửi thông báo cho cư dân với khóa `ticket:{id}:routing-accepted` (`:285-304`). **Không đổi `tickets.status`** (ticket vẫn `open` tới khi có phiếu thi công).
4. *Quản lý danh sách*: `GET /tickets` (lọc `status`, `buildingId`, `priority`, `limit` ≤ 100) và chi tiết `GET /tickets/{id}` kèm 100 sự kiện và phiếu (`v3_routes.py:100-156`); dòng thời gian `GET /tickets/{id}/timeline` (≤ 200 sự kiện, `v3_operations.py:236-246`); hội thoại gốc `GET /tickets/{id}/conversation` (≤ 100 tin, `v3_request_presentation.py:24-32`). UI: bảng/kanban "Công việc" (`staff/connected/ConnectedOperations.tsx:496-506`, nhãn `:68-84`), tự động làm mới mỗi 5 giây (`:239-245`).

**Trạng thái.** `ticket_routing_history.status`: `requested` → `accepted` (giá trị khác: **chưa xác minh**). Ticket: như 3.2.

**Quy tắc nghiệp vụ.** Độ cụ thể `building=4, zone=3, site=2, tenant=1`, sau đó `management_coverage.priority` giảm dần (`v3_routes.py:69-80`); bản ghi phủ phải còn hiệu lực `valid_from<=now()<valid_to` và đơn vị `active` (`:74-79`). Quản trị khi tạo đơn vị bị chặn nếu tòa đã có đơn vị khác phụ trách nhóm dịch vụ (3.7). Mức ưu tiên trên UI: `critical→P0, high→P1, normal→P2, low→P3` (`staff/connected/ConnectedOperations.tsx:86`).

**Dữ liệu.** Đọc: `buildings`, `sites`, `domains`, `management_coverage`, `access_scopes`, `management_units`. Ghi: `ticket_routing_history`, `ticket_events`, `notification_deliveries`.

**Nguồn.** `v3_routes.py`, `v3_operations.py:249-305`, `v3_mutations.py:88-111`, `staff/connected/ConnectedOperations.tsx`.

---

### 3.6 Phân loại (triage): đánh giá, đề xuất, duyệt

**Tác nhân.** Người dùng có quyền thấy ticket (đề xuất/đánh giá); `management` có quyền theo scope của chính sách hoặc quản trị viên (duyệt). Backend có chính sách triage công bố theo phạm vi.

**Kích hoạt và các bước.** *Không có giao diện nối thật* (staff-web không gọi các route này; `/operations/triage` chỉ chuyển hướng sang trang phản ánh, `staffsrc/routes/_authed/operations/triage.tsx:4-6`). Giao diện duy nhất là demo `/demo/ui` (`business.js`: `/tickets/{id}/triage`, `/triage-decisions`, `/triage-reviews/{id}/decision`).
1. *Đánh giá của người*: `POST /tickets/{id}/assessments` (`v3_mutations.py:278-309`): `stage ∈ {intake, specialist, onsite, reassessment}`, `severity` (6 giá trị), `urgency ∈ {unknown, routine, soon, immediate}`, `rationale`, `facts`, `idempotency_key` ≤ 200, `version` của ticket. Trùng khóa → trả lại bản cũ (`replayed:true`); lệch phiên bản → 409. Ghi `ticket_assessments` (người đánh giá `assessor_kind='human'`, thế hệ = `reopen_count`) và sự kiện `ticket.assessed`.
2. *Đề xuất quyết định*: `POST /tickets/{id}/triage-decisions` (`v3_triage.py:51-138`): `assessment_id` phải thuộc đúng ticket và đúng thế hệ hiện tại (422); `priority ∈ {low,normal,high,critical}`; khẩn cấp thì `priority` phải là `critical` (422, `:55-56`); lý do duyệt `review_reason ∈ {unknown_facts, conflict, downgrade, emergency_override, overdue_review}`. Chọn chính sách: `triage_policy_bindings` `active` còn hiệu lực + `triage_policy_versions.status='published'`, khớp `domain`, `request_kind`, `category` (hoặc NULL), phạm vi `tenant|site|building`; ưu tiên building(3) > site(2) > tenant(1) rồi ràng buộc theo nhóm cụ thể rồi `valid_from` mới nhất (`:74-90`); không có → 409 (`:92-93`). Ghi `ticket_triage_decisions` (`outcome='review_required'`, `decision_mode='provisional'`, `decision_seq` tăng), tạo `ticket_triage_reviews(status='pending', due_at = now + review_timeout_seconds)` và đặt `tickets.triage_status='review_required'`; sự kiện `triage.review_requested`.
3. *Duyệt*: `GET /triage-reviews` (≤ 100, chỉ `pending`, lọc theo phạm vi, sắp theo `due_at`, `:147-170`) và `POST /triage-reviews/{id}/decision` (`:173-252`) `{approve, note, ticket_version}`: duyệt → chèn quyết định `outcome='applied'`, `decision_mode='human_confirmed'`, cập nhật `tickets.severity/priority/is_emergency`, `triage_status='confirmed'`, `current_triage_decision_id`; từ chối → `triage_status='pending'`; cập nhật `ticket_triage_reviews.status ∈ {approved, rejected}`; sự kiện `triage.review_resolved`.
4. *Xem*: `GET /tickets/{id}/triage` trả đánh giá, quyết định, review (mỗi loại ≤ 100) (`v3_routes.py:159-183`).

**Trạng thái và chuyển trạng thái.**
* `tickets.triage_status`: `pending` (khi từ chối duyệt) ↔ `review_required` (khi đề xuất) → `confirmed` (khi duyệt) (`v3_triage.py:133-135,231-241`); giá trị khởi tạo: **chưa xác minh**.
* `ticket_triage_reviews.status`: `pending` → `approved` | `rejected` (`:243-247`).
* `ticket_triage_decisions.outcome`: `review_required` | `applied`; `decision_mode`: `provisional` | `human_confirmed` (`:105-108,215-217`).

**Quy tắc nghiệp vụ.** Review hết hạn (`due_at` ≤ hiện tại) hoặc đã quyết → 409 (`:193-194`); lệch `ticket_version` → 409 (`:183-184`); thế hệ đổi (ticket mở lại) → 409 (`:197-198`); quyền duyệt theo `can_review` (2.6); idempotency của đề xuất theo `idempotency_key` ≤ 200 (`:58-64`). Dữ liệu mẫu: chính sách `local-triage`/`ocean-park-triage` với `review_timeout_seconds=3600`, `max_fact_age_seconds=86400`, `max_queue_wait_seconds=3600`, `unknown_priority='normal'` (`scripts/seed_v3_local.sql:53-76`, `scripts/provision_connected.py:130-139`); mã chỉ đọc `review_timeout_seconds`. Không có tiến trình nào xử lý review quá hạn.

**Dữ liệu.** Ghi: `ticket_assessments`, `ticket_triage_decisions`, `ticket_triage_reviews`, `tickets`, `ticket_events`. Đọc: `triage_policy_bindings`, `triage_policy_versions`, `access_scopes`, `buildings`.

**Nguồn.** `v3_triage.py`, `v3_mutations.py:268-309`, `v3_routes.py:159-183`, `scripts/seed_v3_local.sql`, `scripts/provision_connected.py`.
---

### 3.7 Thiết lập đơn vị quản lý, phạm vi phủ, workspace và nhân sự

**Tác nhân.** Quản trị viên (tạo đơn vị qua giao diện); người vận hành hệ thống chạy script (tạo tổ chức, tòa nhà, nhân viên, chuyên môn, ca). Kiểm tra: `admin()` (`v3_admin.py:25-27`).

**Kích hoạt và các bước.**
1. *Danh mục chọn*: `GET /admin/unit-options` (tòa nhà `active`, nhóm dịch vụ `enabled`) (`v3_admin.py:52-58`).
2. *Tạo đơn vị*: UI `staff/connected/admin/Units.tsx` (hộp thoại "Tạo đơn vị quản lý", dòng 197-261) → `POST /admin/units` (`v3_admin.py:61-108`). Trong một giao dịch có khóa advisory: kiểm mã chưa dùng (409), tòa nhà/nhóm dịch vụ tồn tại và đang hoạt động (422), **không có đơn vị `active` nào khác đang phụ trách cùng tòa + cùng nhóm dịch vụ** (kể cả qua phạm vi tenant/site/zone) (409 "…đã có … phụ trách dịch vụ được chọn", `:75-85`). Rồi tạo: `management_units(status='active')`, `access_scopes(kind='management')`, `access_scopes(kind='building')` nếu thiếu, một `management_coverage(valid_from=now())` cho mỗi cặp tòa × nhóm dịch vụ, `workspaces`, `workspace_members` (người tạo), một phòng `channels(kind='management', is_dispatch_default=true)` + `channel_memberships`, và `audit_events` `management_unit.created` (`:86-107`).
3. *Xem đơn vị*: `GET /admin/units` — mỗi đơn vị kèm danh sách tòa nhà phủ còn hiệu lực, các nhóm (workspace) với số thành viên, số nhân viên (`staff_profiles`), số ticket chưa `closed|cancelled` (`:111-130`).
4. *Gắn người dùng BQL vào đơn vị*: qua tài khoản (3.1, bước 3-4): scope `management` + vào phòng của đơn vị.
5. *Dữ liệu tổ chức và nhân sự được nạp bằng script, không có API*: `scripts/provision_connected.py` (miền `vinhomes`; nhóm dịch vụ `technical` "Kỹ thuật" và `security` "An ninh"; site `ocean-park-1` "Vinhomes Ocean Park 1"; 8 phân khu; 14 tòa; 20 căn hộ `1201…1220` của S1.01; đơn vị `bql-sapphire` phủ phân khu Sapphire cho cả hai nhóm; chính sách triage; kho lưu `local_fs`; tài khoản BQL/kỹ thuật/cư dân; hồ sơ nhân viên `KT-SAPPHIRE-01` với chuyên môn `technical` và ca 5 năm; workspace + phòng `bql-sapphire`; agent `system-reception`; ngữ cảnh bộ nhớ) (`:32-42,86-203`); `scripts/add_cleaning_service.py` (nhóm `cleaning` "Vệ sinh & cảnh quan", phủ cùng phạm vi với `technical`, nhân viên `VS-SAPPHIRE-01`) (`:48-87`); `scripts/seed_v3_*.sql` cho demo.
6. *Nhân viên*: `staff_profiles(user_id, management_unit_id, employee_code, availability, active, max_concurrent_jobs)`, `staff_specialties(staff_id, category_id, proficiency, active)`, `staff_shifts(staff_id, starts_at, ends_at, status)` — **chỉ được tạo bởi script/seed** (`scripts/seed_v3_faker.sql:47-62`, `scripts/provision_connected.py:170-177`, `scripts/add_cleaning_service.py:80-87`). Không có route nào tạo, sửa hay đóng các bảng này (xem 6.3); quyền DB `UPDATE(availability)` trên `staff_profiles` được cấp nhưng không có mã dùng (`scripts/grant_v3_api_role.sql:57`).

**Trạng thái.** `management_units.status`, `workspaces.status`: `active` (giá trị khác: chưa xác minh). `management_coverage`: hiệu lực khi `valid_from<=now()` và `valid_to` rỗng hoặc ở tương lai (`v3_routes.py:74-76`); mã **không bao giờ đặt `valid_to`** (quyền DB chỉ `INSERT`, `scripts/grant_v3_api_role.sql:30`). `staff_profiles.availability`: giá trị `available` là giá trị duy nhất mã đọc (`v3_operations.py:161`); `staff_shifts.status`: `available` (`:163`).

**Quy tắc nghiệp vụ.** Mã đơn vị `^[a-z0-9][a-z0-9-]{1,59}$`; tên 2–160; 1–100 tòa, 1–30 nhóm dịch vụ, không trùng (`v3_admin.py:30-49`). Phòng BQL id `bql-{uuid đơn vị}` (`:87`). Nhân viên đủ điều kiện nhận việc khi: `staff_profiles.active`, `availability='available'`, thuộc đúng đơn vị của ticket, có `staff_specialties` `active` cho nhóm dịch vụ của phiếu, có `staff_shifts.status='available'` bao thời điểm hiện tại, và số việc đang giữ < `max_concurrent_jobs` (xem 3.8).

**Dữ liệu.** Ghi (API): `management_units`, `access_scopes`, `management_coverage`, `workspaces`, `workspace_members`, `channels`, `channel_memberships`, `audit_events`. Ghi (script): thêm `domains`, `service_categories`, `sites`, `zones`, `buildings`, `units`, `unit_residents`, `staff_profiles`, `staff_specialties`, `staff_shifts`, `triage_policy_versions`, `triage_policy_bindings`, `storage_locations`, `agents`, `execution_principals`, `memory_namespaces`.

**Nguồn.** `v3_admin.py:30-130`, `staff/connected/admin/Units.tsx`, `scripts/provision_connected.py`, `scripts/add_cleaning_service.py`, `scripts/seed_v3_faker.sql`, `scripts/seed_v3_local.sql`, `scripts/seed_v3_ocean_park.sql`, `scripts/grant_v3_api_role.sql`.

---

### 3.8 Phiếu thi công, phân công và nhận / từ chối việc

**Tác nhân.** BQL phụ trách (tạo phiếu, phân công); nhân viên hiện trường (nhận/từ chối); hệ thống (tự đề nghị việc trong hàng đợi — chỉ cho phương án do agent). Kiểm tra: `management_access` (tạo phiếu, phân công), nhân viên được giao qua `staff_profiles.user_id` (phản hồi).

**Kích hoạt và các bước.**
1. *Tạo phiếu*: UI nút "Tạo phiếu thi công" khi ticket `open|triaging` (`staff/connected/ConnectedOperations.tsx:552-571`) → `POST /tickets/{id}/work-orders` `{category_id, required_specialty_id, description, ticket_version}` (`v3_mutations.py:312-349`; UI gửi `required_specialty_id = category_id`, `:560-561`). Tạo `work_orders(status='queued')`, ticket → `assigned`, sự kiện `work_order.created` (`:337-348`).
2. *Chọn nhân viên*: `GET /staff/available?managementUnitId&categoryId` (`v3_operations.py:128-169`), UI nạp khi mở ticket (`staff/connected/ConnectedOperations.tsx:290-300`).
3. *Phân công*: UI hộp chọn nhân viên + nút "Phân công" cho phiếu `queued` (`:610-644`) → `POST /work-orders/{id}/assignments` `{staff_id, offer_expires_at, work_order_version}` (`v3_mutations.py:565-658`). UI luôn đặt hạn đề nghị = **30 phút** sau (`staff/connected/ConnectedOperations.tsx:633-635`).
4. *Nhân viên phản hồi*: UI "Nhận việc" (chọn "Bạn sẽ đến sau" 15 / 30 / 60 / 120 phút, `staff/connected/field/FieldJob.tsx:20,106-120`) → `POST /assignments/{id}/response` `{status:'accepted', eta_at}`; hoặc "Từ chối việc này" chọn lý do `BUSY` "Đang bận việc khác" / `WRONG_SKILL` "Không đúng chuyên môn" / `OFF_SHIFT` "Đã hết ca" / `OTHER` "Lý do khác" (`staff/connected/field/model.ts:68`; `staff/connected/field/FieldJob.tsx:121-137`) → `{status:'rejected', rejection_reason}`; chuỗi gửi đi là **nhãn tiếng Việt**, không phải mã (`staff/connected/field/FieldJob.tsx:77`). Backend: `v3_mutations.py:667-715`.
5. *Đề nghị tự động*: `work_offers.offer_work` chọn nhân viên rảnh nhất của đơn vị (ít việc nhất, có chuyên môn và ca đang chạy, khóa `skip locked`) và tạo đề nghị hạn **24 giờ** (`work_offers.py:14,35-67`); `offer_queued_work` dùng chỗ trống khi một phiếu hoàn tất/hủy hoặc một đề nghị bị từ chối, nhưng chỉ cho phiếu thuộc phương án `approved` do **agent** đề xuất mà không có người duyệt (`proposed_by_agent_id is not null and management_by is null`, `work_offers.py:84-93`) — gói không còn agent nào ghi phương án loại này (xem 6.4). `offer_planned_work` (24 giờ) đề nghị cho người thực hiện đã chọn trong phương án (`v3_request_presentation.py:152-198`).
6. *Xem*: `GET /work-orders`, `GET /dispatch-queue` (phiếu `queued`), `GET /work-orders/{id}` (kèm phân công, phê duyệt, QC, làm lại), `GET /my-work-orders` (phiếu của chính mình), `GET /tasks`, `GET /approvals`, `GET /dashboard` (đếm theo trạng thái) (`v3_routes.py:186-242`, `v3_operations.py:86-218`).

**Trạng thái và chuyển trạng thái.**

`work_orders.status ∈ {queued, offered, accepted, en_route, arrived, awaiting_approval, in_progress, completed, rejected, cancelled}` (`v3_mutations.py:354-355`, `queued` ở `:341`). Từ điển cho `PATCH /work-orders/{id}/status` (`ALLOWED_TRANSITIONS`, `:439-445`): `queued→{offered,cancelled}`, `offered→{accepted,rejected,cancelled}`, `accepted→{en_route,cancelled}`, `en_route→{arrived,cancelled}`, `arrived→{in_progress,awaiting_approval}`, `awaiting_approval→{in_progress,cancelled}`, `in_progress→{completed,awaiting_approval}`; `completed`, `rejected`, `cancelled` là cuối. Ngoài PATCH:

| Chuyển | Do | Nguồn |
|---|---|---|
| `queued/offered → offered` | phân công thủ công, đề nghị tự động | `v3_mutations.py:652-655`, `work_offers.py:64`, `v3_request_presentation.py:190` |
| `offered → accepted` | nhân viên nhận | `v3_mutations.py:705-709` |
| `offered → queued` | nhân viên từ chối | `v3_mutations.py:705-709` |
| `arrived → awaiting_approval` | gửi đề xuất sửa chữa | `v3_mutations.py:395` |
| `awaiting_approval → arrived` | cư dân/nhân viên (tại chỗ) không đồng ý | `v3_mutations.py:430-431`, `v3_resident.py:525-526` |
| bất kỳ chưa cuối `→ cancelled` | phê duyệt hủy việc an ninh | `v3_security.py:671-675` |

Không có mã nào đặt `work_orders.status='rejected'` (chỉ đọc để loại trừ).

`work_assignments.status ∈ {offered, accepted, rejected, completed, cancelled}` do mã đặt (`v3_mutations.py:645-647,697-701,538-541`, `v3_security.py:665-670`); thêm trạng thái **suy ra** `expired` khi `offered` và `offer_expires_at<=now()` (`v3_operations.py:111-112`). Khi phiếu `completed|cancelled` mà ticket **không** theo phương án, các phân công `accepted|offered` đổi theo trạng thái phiếu và ghi `ended_at`; với ticket theo phương án, người thực hiện được giữ lại (`v3_mutations.py:536-541`).

**Quy tắc nghiệp vụ.**
* *Tạo phiếu*: BQL có quyền trên ticket (403); lệch `ticket_version` (409); **ticket có cờ `requiresPlan` bị chặn** — "Create a ticket plan; resident approval creates its work orders" (409, `:327-329`); ticket phải `open|triaging` (409, `:330-331`); nhóm dịch vụ phải `enabled` (422, `:332-336`).
* *Phân công* (`create_assignment`): BQL có quyền (403); chặn khi còn phương án `management_pending|resident_pending` (409, `:585-587`); ticket có phương án thì phiếu phải nằm trong `steps[].work_order_id` của một phương án `approved` (409, `:588-592`); **phiếu `security` cần một `work_approvals` `management_security_dispatch` đã `approved` khớp đúng `staff_id` và `work_order_version`** (409, `:593-602`); `work_order_version` đúng (409) và phiếu `queued|offered` (409, `:603-610`); `offer_expires_at` có múi giờ và ở tương lai (422, `:611-614`); chưa có phân công `accepted` hoặc `offered` còn hạn (409, `:615-620`); nhân viên `active`, `availability='available'`, thuộc đơn vị của ticket, có chuyên môn `active` đúng nhóm dịch vụ của phiếu, đang trong ca `available` (422, `:621-634`); số việc đang giữ ≥ `max_concurrent_jobs` → 409 "Staff is busy; work remains queued" (`:635-641`) — "việc đang giữ" là phân công `accepted`, hoặc `offered` còn hạn, trên phiếu chưa `completed|cancelled|rejected` (`:635-639`).
* *Danh sách nhân viên khả dụng* áp cùng điều kiện, sắp theo số việc tăng dần (`v3_operations.py:149-168`), và chỉ BQL có scope `tenant` hoặc `management` đúng đơn vị được xem (403, `:136-148`).
* *Phản hồi* (`respond_assignment`): chỉ nhân viên được giao (403); đề nghị phải còn hạn và đang `offered` (409, `:684-689`); nhận thì bắt buộc `eta_at` (422), mọi `eta_at` phải có múi giờ (422), từ chối thì bắt buộc `rejection_reason` (422) (`:690-695`); sau từ chối, hệ thống thử đề nghị việc đang chờ khác cho đúng đơn vị/chuyên môn (`:712-714`).
* *Hàng đợi* (DB cũng giữ quy tắc này bằng trigger `assignment_capacity`, Phụ lục D.3): nhận việc giữ chỗ trong hàng đợi; chỉ một việc ở `en_route|arrived|awaiting_approval|in_progress` cho mỗi nhân viên — bắt đầu việc thứ hai bị 409 "Finish the active work order before starting another; this work remains queued" (`:477-494`).
* Hết hạn đề nghị: **không có tiến trình** nào chuyển phiếu `offered` về `queued` hay thông báo BQL; phiếu giữ nguyên `offered`, giao diện nhân viên bỏ phiếu đã hết hạn khỏi danh sách (`staff/connected/field/model.ts:25`), và BQL có thể đề nghị lại vì điều kiện "không có đề nghị còn hạn" đã thỏa (`v3_mutations.py:609-620`). Mô tả "chờ OFFER_HOURS rồi BQL phải can thiệp" ở `work_offers.py:3-4` chỉ là chú thích.

**Dữ liệu.** Ghi: `work_orders` (`tenant_id, ticket_id, category_id, required_specialty_id, description, status`), `work_assignments` (`tenant_id, work_order_id, staff_id, assigned_by_user_id | assigned_by_agent_id, status, offered_at, offer_expires_at, accepted_at, eta_at, rejection_reason, ended_at`), `ticket_events`, `tickets`. Đọc: `staff_profiles`, `staff_specialties`, `staff_shifts`, `users`, `vh_ticket_plans`, `work_approvals`, `service_categories`.

**Nguồn.** `v3_mutations.py:312-349,565-715`, `v3_operations.py:86-218`, `v3_routes.py:186-242`, `work_offers.py`, `v3_request_presentation.py:152-198`, `staff/connected/ConnectedOperations.tsx:290-300,363-376,552-644`, `staff/connected/field/FieldJob.tsx`, `staff/connected/field/model.ts`.

---

### 3.9 Luồng hiện trường: di chuyển, đến nơi, xử lý, hoàn thành và bằng chứng ảnh

**Tác nhân.** Nhân viên được giao (phiếu có `work_assignments.status='accepted'`); quản trị viên (được phép đổi trạng thái thay); BQL (đính kèm bằng chứng). Kiểm tra: `change_work_order_status` (`v3_mutations.py:448-562`, quyền ở `:459-467`).

**Kích hoạt và các bước** (UI field `staff/connected/field/FieldJob.tsx`; bước hiển thị `STEPS = ["Nhận việc","Đến nơi","Thực hiện","Báo cáo"]` `staff/connected/field/model.ts:29`).
1. *Bắt đầu di chuyển* (`accepted→en_route`) rồi *Tôi đã đến* (`en_route→arrived`): nút một chạm (`staff/connected/field/FieldJob.tsx:139-141`) → `PATCH /work-orders/{id}/status {version,status,note}`; `note` rỗng được thay bằng nhãn trạng thái (`staff/connected/ConnectedOperations.tsx:374-376`).
2. *Khảo sát và đề xuất chi phí* (`arrived`): xem 3.10.
3. *Bắt đầu xử lý* (`arrived|awaiting_approval→in_progress`): chỉ khi cư dân đã đồng ý đề xuất (`staff/connected/field/FieldJob.tsx:158-163`).
4. *Chụp ảnh trước và sau* (`in_progress`): nút "Thêm ảnh" (camera) cho "Ảnh trước khi xử lý" và "Ảnh sau khi xử lý" (`staff/connected/field/FieldJob.tsx:165-175`) → `uploadImage` (3.21) rồi `POST /tickets/{ticket}/evidence {file_id, work_order_id, assignment_id, purpose, caption}` (`staff/connected/ConnectedOperations.tsx:383-389`, backend `v3_mutations.py:726-772`).
5. *Gửi kết quả* (`in_progress→completed`): nút bị khóa tới khi có **ít nhất 1 ảnh trước và 1 ảnh sau** của phiếu (`staff/connected/field/FieldJob.tsx:72-73,172-173`). Backend kiểm các điều kiện hoàn tất bên dưới.
6. Sau khi gửi: màn hình nói "Đã gửi kết quả" và trạng thái chờ theo ticket (`AFTER`, `staff/connected/field/model.ts:61-66`).
7. Tab danh sách của nhân viên: "Đang làm", "Hàng đợi", "Chờ xác nhận", "Lịch sử" (`staff/connected/field/model.ts:52-59`).

**Trạng thái.** Như 3.8. Mốc thời gian được mã đặt: `arrived_at` (khi `arrived`), `started_at` (khi `in_progress`), `completed_at` (khi `completed`) (`v3_mutations.py:529-535`); không có cột mốc cho `en_route` ở mã.

**Quy tắc nghiệp vụ.**
* `version` phiếu phải khớp (409), trạng thái phải nằm trong từ điển (409), ghi chú `note` 1–2000 (`:352-356,473-476`).
* Nhân viên không phải quản trị viên phải có phân công `accepted` trên phiếu (403, `:459-467`).
* Ra khỏi hàng đợi: `en_route|arrived|in_progress` bị chặn nếu nhân viên đang có phiếu khác ở `en_route|arrived|awaiting_approval|in_progress` (409, `:477-494`).
* `in_progress`: phải có đồng ý sửa chữa mới nhất `approved` — với ticket **không** theo phương án là luôn bắt buộc (không có đề xuất thì cũng 409); với ticket theo phương án chỉ bắt buộc khi đã có đề xuất (`:495-503`).
* `cancelled` bị cấm cho phiếu `security` (cần phê duyệt hủy, `:504-507`).
* `completed` đòi: ít nhất một bằng chứng `purpose='before'` đang `active` (409, `:509-514`); không còn `vh_operational_requests` ở `pending|approved` (409, `:515-517`); không còn `service_interruptions` chưa `restored|cancelled` (409, `:518-523`); ít nhất một bằng chứng `after|verification` đang `active` (409, `:524-528`).
* Sau `completed`: ticket **không** theo phương án → phân công kết thúc, ticket vẫn `in_progress` chờ BQL nghiệm thu (3.15); ticket theo phương án → tạo `work_approvals(kind='customer_completion', status='pending')` gửi người yêu cầu, và nếu không còn phiếu bắt buộc chưa xong thì ticket → `resolved` (`:546-556`).
* Bằng chứng (`POST /tickets/{id}/evidence`): `purpose ∈ {issue, before, after, verification}`; `before|after` bắt buộc kèm `work_order_id` và `assignment_id` (422); tệp phải `files.status='ready'` thuộc ticket (trực tiếp hoặc qua `ticket_files`) (422); phiếu phải thuộc ticket (422); người ghi phải là BQL có quyền hoặc người thực hiện `accepted` (403); phân công phải thuộc phiếu (422) (`:726-772`). Dòng ghi `provenance='upload'`, `status='active'`, sự kiện `ticket.evidence_attached`.
* **Checklist**: không có route, bảng hay màn hình nối thật nào cho checklist thực hiện; các mẫu checklist (`ELECTRIC`, …) chỉ nằm ở lớp preview `staff/lib/field-flow.ts:37-61` (tài liệu tham chiếu `docs/vinhomes-operations-staff-field-flow.md` **không** có trong gói). Bảng Alembic `vh_checklist*` thuộc mã cũ không gắn route (`migrations/versions/0009_vh_checklist_execution.py`).

**Dữ liệu.** Ghi: `work_orders`, `work_assignments`, `evidence_items`, `ticket_events`, `tickets`, `work_approvals`, `files`/`ticket_files` (qua 3.21). Đọc: `vh_operational_requests`, `service_interruptions`, `service_categories`.

**Nguồn.** `v3_mutations.py:439-562,718-772`, `staff/connected/field/*`, `staff/connected/ConnectedOperations.tsx:363-390`.

---

### 3.10 Đề xuất sửa chữa (báo giá) và cư dân đồng ý — kể cả tại hiện trường

**Tác nhân.** Nhân viên được giao (lập đề xuất, ghi nhận đồng ý tại chỗ); cư dân (yêu cầu) đồng ý hoặc từ chối trên ứng dụng của mình.

**Kích hoạt và các bước.**
1. *Lập đề xuất* (phiếu `arrived`): UI "Hiện trạng và cách xử lý" (≥ 8 ký tự) + `QuoteForm` (danh mục vật tư, số lượng, đơn giá, tiền công, bảo hành) (`staff/connected/field/FieldJob.tsx:148-156`, `staff/connected/RepairQuote.tsx:23-117`) → `POST /work-orders/{id}/repair-proposal` (`v3_mutations.py:374-397`). Tổng tiền **do backend tính lại**, không tin tổng từ client (`:383-388`). Tạo `work_approvals(kind='customer_repair', status='pending', requested_to_user_id=người yêu cầu ticket, request_detail JSON)`; phiếu → `awaiting_approval`; sự kiện `work_order.repair_proposed`.
2. *Cư dân quyết định trên app*: thẻ "Phương án sửa chữa cần bạn xác nhận" với nút "Đồng ý phương án" / "Chưa đồng ý" (`resident/app/App.tsx:566-605`) → `POST /resident/approvals/{id}/decision` (`v3_resident.py:478-575`).
3. *Hoặc quyết định tại chỗ trên máy nhân viên*: `OnsiteConsent` hiển thị đề xuất, nút "Cư dân đồng ý tại chỗ" / "Chưa đồng ý, lập lại" (`staff/connected/RepairQuote.tsx:120-205`) → `POST /work-orders/{id}/repair-proposal/onsite-decision {version, approved}` (`v3_mutations.py:405-436`); đồng ý do nhân viên xác nhận thay cư dân, ghi `decision_note` cố định "Cư dân trả lời tại hiện trường trên thiết bị của nhân viên." (`:429`).
4. Màn hình nhân viên thăm dò mỗi 5 giây để biết cư dân đã đồng ý chưa (`staff/connected/RepairQuote.tsx:154`).
5. Đồng ý → nhân viên bấm "Bắt đầu xử lý" (`staff/connected/field/FieldJob.tsx:161`). Không đồng ý → phiếu về `arrived`, nhân viên lập đề xuất mới.

**Trạng thái.** `work_approvals.status` của `customer_repair`: `pending → approved | rejected`. Khi `rejected` phiếu `awaiting_approval → arrived` (`v3_mutations.py:430-431`, `v3_resident.py:525-526`). Vòng lập lại: mỗi đề xuất mới tạo một dòng `work_approvals` mới; điều kiện bắt đầu xử lý chỉ xét dòng **mới nhất** (`:496-503`).

**Quy tắc nghiệp vụ.**
* Đề xuất: phiếu phải đang `arrived` và đúng `version` (409) (`:380-382`); người gọi phải là BQL có quyền hoặc người thực hiện `accepted` (403) (`:377-379`); `note` 8–2000; tối đa 50 dòng vật tư, mỗi dòng: tên ≤ 200, số lượng > 0 và ≤ 10000 (3 chữ số thập phân), đơn vị ≤ 30, đơn giá 0…1.000.000.000 VND; tiền công 0…1.000.000.000; bảo hành 0…120 tháng (`:359-372`). Thành tiền dòng = `round(số lượng × đơn giá)` (ROUND_HALF_UP, VND nguyên) (`:384-388`).
* Đồng ý tại chỗ: phiếu phải `awaiting_approval` đúng `version`; còn một `customer_repair` `pending` chưa hết hạn (409) (`:413-423`). Bản ghi đồng ý trên app của cư dân thắng nếu đến trước (chú thích `:407`).
* Cư dân: phải gửi `Idempotency-Key` 8–120 (422) và `version` ticket đúng (409); nếu từ chối phải nêu lý do ≥ 8 ký tự (422); chỉ quyết được phê duyệt gửi đến chính mình và trên ticket của mình (404); phê duyệt phải còn `pending` và chưa hết hạn (409) (`:478-522`). Biên nhận lưu trong `ticket_events` (khóa `idempotency_key`) — gửi lại cùng khóa cùng nội dung trả lại kết quả cũ, khác nội dung 409 (`:503-510`).
* `work_approvals.expires_at` của `customer_repair` **không** được đặt ở đâu trong mã (chỉ kiểm khi có).
* Danh mục vật tư gợi ý (16 mục, đơn giá cố định) là hằng số giao diện `MATERIAL_CATALOG` (`staff/lib/field-flow.ts:18-35`), không có bảng vật tư ở backend.

**Dữ liệu.** `work_approvals`, `work_orders`, `ticket_events`. Cột chính khi tạo: `tenant_id, work_order_id, kind='customer_repair', requested_to_user_id, request_detail{note, lines[{name,quantity,unit,unit_price,amount}], labor_cost, warranty_months, total}, status='pending', request_hash`.

**Nguồn.** `v3_mutations.py:359-436`, `v3_resident.py:478-593`, `staff/connected/RepairQuote.tsx`, `staff/connected/field/FieldJob.tsx`, `resident/app/App.tsx:566-605`, `resident/services/use-connected-resident.ts:396-427`.

---

### 3.11 Khóa nước / gián đoạn dịch vụ và thông báo cư dân

**Tác nhân.** Nhân viên được giao (đề nghị, bắt đầu, mở lại); BQL phụ trách (duyệt, thông báo); cư dân trong phạm vi bị ảnh hưởng (nhận thông báo). **Không có màn hình nối thật**; chỉ có nút trong trang demo `/demo/ui` (`business.js`: `water-shutdown-request`, `notify`, `start`/`restore`).

**Kích hoạt và các bước** (`v3_water.py`).
1. *Đề nghị*: `POST /work-orders/{id}/water-shutdown-request {reason ≤ 2000, affected_scope_id, planned_start, planned_end}` (`:86-157`). Người gọi phải có phân công `accepted` đang hoạt động (403, `:53-63`); `affected_scope` phải là scope của **tòa** hoặc **phân khu** của ticket (422, `:94-102`); đơn vị phải có scope `management` (409, `:103-111`); `planned_start/end` có múi giờ và `start < end` (`:30-35`). Idempotent theo băm nội dung: đã có gián đoạn chưa `cancelled|restored` cùng băm thì trả lại (`:112-125`). Tạo `work_approvals(kind='management_water_shutdown', status='pending', required_scope_id)`, `service_interruptions(utility='water', status='proposed')`, `interruption_scopes`; sự kiện `water.shutdown_requested`.
2. *Duyệt*: `POST /approvals/{id}/decision {status ∈ {approved, rejected}, note 1–2000}` (`v3_operations.py:313-380`): chỉ loại `management_water_shutdown` được xử lý ở đây (loại `customer_*` → 403 "requires its assigned customer"; hai loại an ninh → `decide_security`, 3.17); phải còn `pending` và chưa hết hạn (409); người duyệt là `management` bao ticket, đúng `required_scope_id` hoặc scope `tenant` (403) (`:330-361`). Cập nhật `service_interruptions`: `proposed → approved` (đồng ý) hoặc `proposed → cancelled` (từ chối) (`:369-374`); sự kiện `work_approval.decided`. Hàng đợi `GET /approvals` hiện ba loại `management_water_shutdown|management_security_dispatch|management_security_cancel` (`:195-218`).
3. *Thông báo cư dân*: `POST /water-interruptions/{id}/notify` (`:217-232`): BQL phụ trách; trạng thái phải `approved` (409). Chèn `notification_deliveries` kênh `in_app` cho mọi cư dân **đã xác minh** (còn hiệu lực, user `active`) của các căn thuộc tòa/phân khu bị ảnh hưởng, khóa chống trùng `water:{id}:shutdown` (`:192-214`); → `notified`; sự kiện `water.shutdown_notified`.
4. *Bắt đầu khóa*: `POST /water-interruptions/{id}/start` (`:235-249`): nhân viên được giao; trạng thái phải `notified` (409); → `active`, `actual_start=now()`, `operated_by`.
5. *Mở lại nước*: `POST /water-interruptions/{id}/restore` (`:252-267`): nhân viên được giao; phải `active` (409); → `restored`, `actual_end=now()`, thông báo cư dân khóa `water:{id}:restored`.
6. Đọc: `GET /work-orders/{id}/water-interruptions`; `GET /technical/active-outages?buildingId` (gián đoạn chưa `restored|cancelled` của tòa) (`v3_technical.py:233-246`).

**Trạng thái và chuyển trạng thái.**
* `service_interruptions.status`: `proposed → approved → notified → active → restored`; `proposed → cancelled` (khi từ chối) (nguồn: `v3_water.py:140-143,223-224,240-246,257-263`, `v3_operations.py:369-374`).
* `work_approvals.status` (loại này): `pending → approved | rejected`.

**Quy tắc nghiệp vụ.** Hoàn tất phiếu bị chặn khi còn gián đoạn chưa `restored|cancelled` gắn với phê duyệt của phiếu (409 "Restore water before completing work") (`v3_mutations.py:518-523`); gián đoạn bị từ chối (`cancelled`) không chặn. Không bắt buộc đến hiện trường (`arrived`) trước khi đề nghị: mã chỉ yêu cầu phân công `accepted` (xem `_assigned_staff`). Phê duyệt này **không** đặt `expires_at` (khác phê duyệt an ninh). Điện được ghi qua kênh khác (3.12).

**Dữ liệu.** Ghi: `work_approvals`, `service_interruptions`, `interruption_scopes`, `notification_deliveries`, `ticket_events`. Đọc: `access_scopes`, `units`, `unit_residents`, `users`, `work_orders`, `tickets`.

**Nguồn.** `v3_water.py`, `v3_operations.py:195-218,313-380`, `v3_technical.py:233-246`, `v3_mutations.py:518-523`.

---

### 3.12 Quyền thao tác kỹ thuật, đo đạc, tài sản và bảo trì (không điều khiển thiết bị)

**Tác nhân.** Nhân viên được giao hoặc BQL (ghi); BQL phụ trách (duyệt); người có phạm vi tòa (đọc tài sản). Kiểm tra: `work_access` (BQL hoặc phân công `accepted`, `v3_technical.py:24-65`), `_responsible_management` cho duyệt, `building_access` cho tài sản (`v3_security.py:31-49`). Không có giao diện nối thật (không có trong staff-web nối thật; tài liệu mô tả "không điều khiển thiết bị", `v3_technical.py:1`).

**Kích hoạt và các bước.**
1. *Yêu cầu quyền thao tác*: `POST /work-orders/{id}/permission-requests {kind, reason ≤ 2000, details (≤ 20 khóa, giá trị chuỗi/số/bool), work_order_version, idempotency_key ≤ 160}`; `kind ∈ {utility_isolation, area_restriction, apartment_entry, vendor_dispatch}`; riêng `utility_isolation` chỉ nhận điện (`details.utility == 'electricity'`), nước phải dùng 3.11 (422) (`v3_technical.py:249-321`).
2. *Duyệt / đóng*: `POST /permission-requests/{id}/decision {status ∈ {approved, rejected, completed, cancelled}, version, note}` (`:343-405`): `_responsible_management` (**không có ngoại lệ cho quản trị viên**, `v3_water.py:66-83`).
3. *Đo đạc*: `POST /work-orders/{id}/measurements {parameter ≤ 120, value, unit ≤ 40, measured_at (có múi giờ), source (mặc định "executor"), note 1–2000}` và `GET` (`:183-230`); không ghi khi phiếu đã cuối (409).
4. *Kiểm tra điều kiện hoàn tất*: `GET /work-orders/{id}/resolution-check` trả `ready` và bốn kiểm tra `completionEvidence`, `waterRestored`, `permissionsFinished`, `qcPassed` (QC mới nhất là `pass`, mặc định `true` nếu chưa có QC) (`:408-433`).
5. *Kết quả người thực hiện*: `POST /work-orders/{id}/executor-results {version, diagnosis ≤ 5000, repair_notes ≤ 5000}` (`:447-501`): phiếu phải `in_progress` đúng `version`, có bằng chứng "trước", `resolution-check` phải `ready`; lưu `diagnosis`, `repair_notes` rồi gọi lại `change_work_order_status → completed`. Lỗi trả danh sách kiểm tra thất bại (`agent_blocked`).
6. *Tài sản*: `GET /assets?buildingId`, `GET /assets/{id}` (`:84-102`); cảm biến `GET/POST /assets/{id}/sensor-readings` (POST chỉ BQL có phạm vi tòa; `source` bắt buộc, "database; no live BMS connection") (`:105-157`); lịch sử bảo trì `GET /assets/{id}/maintenance-history` (limit ≤ 100) và `POST` (`:160-180,504-554`).
7. *Xác nhận bảo trì*: `POST /assets/{id}/maintenance-history {work_order_id, note ≤ 5000}`: BQL phụ trách; tòa của tài sản phải trùng tòa của ticket (422); phiếu phải `completed` **và** `resolution-check.ready` (409); bản ghi đã xác nhận là bất biến — ghi lại cùng phiếu với ghi chú khác → 409 (`:509-554`). Sự kiện `maintenance.confirmed`.

**Trạng thái.** `vh_operational_requests.status`: `pending → {approved, rejected, cancelled}`; `approved → {completed, cancelled}` (`transitions`, `:377-380`); lệch `version` hoặc chuyển sai → 409; duyệt `approved` khi phiếu đã cuối → 409 (`:385-390`).

**Quy tắc nghiệp vụ.** Yêu cầu trùng `idempotency_key` mà người gửi/nội dung khác → 409 "Request key already used"; phiếu đổi phiên bản hoặc đã cuối → 409 (`:279-290`). Yêu cầu `pending|approved` chặn hoàn tất phiếu (`v3_mutations.py:515-517`). Sự kiện: `permission.requested`, `permission.decided`, `technical.measurement_recorded`, `maintenance.confirmed`.

**Dữ liệu.** `vh_operational_requests`, `vh_technical_measurements`, `vh_assets`, `vh_sensor_readings`, `vh_maintenance_records`, `evidence_items`, `service_interruptions`, `vh_qc_results`, `work_orders`, `ticket_events`.

**Nguồn.** `v3_technical.py`, `v3_security.py:31-49`, `v3_water.py:66-83`.

---

### 3.13 Phê duyệt ngân sách

**Tác nhân.** BQL phụ trách (đề nghị); người duyệt được chỉ định (quản trị viên hoặc người có vai trò `management` đang hiệu lực). **Không có màn hình nối thật**; có trong demo `/demo/ui`.

**Các bước** (`v3_specialized.py`).
1. `POST /work-orders/{id}/budget-approvals {reviewer_user_id, amount_vnd > 0, purpose}` (`:291-343`): phải là BQL có quyền trên ticket (403); `reviewer_user_id` phải là user `active` và là quản trị viên hoặc `management` hiệu lực (422); tạo `vh_budget_approvals(status='pending')`; sự kiện `budget_approval.requested`.
2. `GET /budget-approvals?status=` (≤ 100): quản trị viên xem tất cả, người khác chỉ thấy cái mình là người duyệt hoặc người đề nghị (`:297-308`).
3. `POST /budget-approvals/{id}/decision {status ∈ {approved, rejected}, note, version}` (`:346-376`): chỉ người duyệt được chỉ định hoặc quản trị viên (403); cập nhật có điều kiện `status='pending' and version=:version`, nếu không khớp → 409; sự kiện `budget_approval.decided`.

**Trạng thái.** `pending → approved | rejected` (`version` tăng mỗi lần). **Không** có bước nào trong mã bắt buộc phải có ngân sách đã duyệt (chưa thấy ràng buộc nào liên kết với phân công hay hoàn tất). Dữ liệu mẫu ghi người đề nghị là nhân viên kỹ thuật (`scripts/seed_v3_remaining.sql:93-95`) trái với API (chỉ BQL đề nghị được).

**Dữ liệu.** `vh_budget_approvals(tenant_id, work_order_id, requested_by, reviewer_user_id, amount_vnd, purpose, status, version)`, `ticket_events`.

**Nguồn.** `v3_specialized.py:291-376`.

---

### 3.14 Phương án (plan) của BQL và cư dân

**Tác nhân.** BQL phụ trách (đề xuất, chỉnh sửa, duyệt); cư dân yêu cầu (duyệt lần hai). Áp dụng cho ticket có cờ `requiresPlan` (tạo bằng `POST /tickets`, hoặc nháp commit mặc định) — **không** áp dụng cho ticket cư dân tạo bằng form hay qua Reception (3.2, 3.4). Kiểm tra: `_responsible_management`, cư dân qua `requester_user_id`.

**Kích hoạt và các bước.** *Không có màn hình BQL nối thật.* Phía cư dân chỉ có thẻ `SupervisorResponse` (3.24) khi có bản ghi chờ.
1. *Đề xuất*: `POST /tickets/{id}/plans {title ≤ 300, steps[1..20]{category_id, description ≤ 2000}, estimated_amount ≥ 0 (18 chữ số, 2 thập phân), ticket_version, idempotency_key ≤ 160}` (`v3_plans.py:23-103`): BQL có quyền; trùng khóa thì trả bản cũ (lệch nội dung/người → 409); ticket phải đúng phiên bản và chưa `closed|cancelled|resolved` (409); không có phương án nào đang `management_pending|resident_pending` (409 "Decide the existing plan first"); mọi nhóm dịch vụ `enabled` (422). Tạo `vh_ticket_plans(status='management_pending')`; sự kiện `plan.proposed`.
2. *Chỉnh bản trình bày*: `PATCH /plans/{id}/presentation {version, summary ≤ 300, steps (≤ 20 mục, mỗi mục ≤ 2000, tổng nối ≤ 1900 ký tự), performer_staff_id?, appointment_at?}` (`v3_request_presentation.py:73-150`): chỉ khi plan `management_pending` đúng `version` và ticket chưa kết thúc; người thực hiện phải thuộc đơn vị và có chuyên môn đúng nhóm dịch vụ của ticket (422); giờ hẹn có múi giờ và ở tương lai (422); tăng `version`, ghi `audit_events` `plan.presentation_updated`. Plan do con người đề xuất phải giữ nguyên số bước (422, `:138-142`).
3. *BQL quyết định*: `POST /plans/{id}/management-decision {decision ∈ {approve, reject}, version, note}` (`:151-195`) → `resident_pending` hoặc `rejected`; thông báo cho cư dân khóa `plan:{id}:management`.
4. *Cư dân quyết định*: `POST /resident/plans/{id}/decision` (`:209-300`): ticket phải của chính họ; plan phải `resident_pending` đúng `version` và ticket chưa `closed|cancelled|resolved` (409). Đồng ý → mỗi bước tạo một `work_orders(status='queued', scheduled_at=giờ hẹn?)` (với `required_specialty_id = category_id`), ghi `work_order_id` vào `steps`, ticket → `assigned`; sau đó nếu có người thực hiện đã chọn thì `offer_planned_work`, nếu plan do agent đề xuất không qua BQL thì `offer_work` (`:291-299`).
5. Xem: `GET /tickets/{id}/plans`, `GET /plans?status=` (mặc định `management_pending`, giá trị cho phép chỉ 4: `management_pending|resident_pending|approved|rejected`), `GET /resident/plans` (`:106-132,198-206`).

**Trạng thái và chuyển trạng thái.** `vh_ticket_plans.status`: `management_pending → resident_pending | rejected`; `resident_pending → approved | rejected | revision_requested` (giá trị cuối chỉ do tin `plan_change_requested` từ Reception, `v3_reception_supervisor.py:566-582`). `revision_requested` không nằm trong các `Literal` của `GET /plans` (`v3_plans.py:121-123`) hay của `ResidentPlan` (`resident_contract.py:172`) — xem 6.5.

**Quy tắc nghiệp vụ.** Ticket có `requiresPlan`: không tạo phiếu thủ công (409), không phân công khi plan chờ (409), không `resolved|closed` nếu chưa có plan `approved` (409) (`v3_mutations.py:222-234,327-329,585-592`). Ticket không có cờ này (đa số) không dùng plan.

**Dữ liệu.** `vh_ticket_plans(tenant_id, ticket_id, proposed_by, title, steps JSONB, estimated_amount, status, idempotency_key, request_hash, version, management_by/note/at, resident_by/note/at, proposal JSONB, proposed_by_agent_id)`, `work_orders`, `tickets`, `ticket_events`, `notification_deliveries`, `audit_events`.

**Nguồn.** `v3_plans.py`, `v3_request_presentation.py`, `v3_mutations.py`.
---

### 3.15 Nghiệm thu (QC), làm lại, đóng ticket, cư dân xác nhận và đánh giá nhân viên

**Tác nhân.** BQL phụ trách (nghiệm thu, tạo lượt làm lại); hệ thống (`publish_completion`); cư dân yêu cầu (xác nhận, yêu cầu xử lý lại, đánh giá). Quản trị viên có thể đổi trạng thái ticket qua PATCH.

**Kích hoạt và các bước.**
1. *Nghiệm thu*: UI nối thật (`staff/connected/ConnectedOperations.tsx:645-705`), nút xuất hiện trên phiếu `completed` khi ticket chưa `resolved|closed`:
   * "Nghiệm thu đạt" → `POST /work-orders/{id}/qc {outcome:'pass', criteria:[{name:'Kết quả hiện trường', passed:true}], note}`;
   * "Không đạt · tạo lượt làm lại" (cần ghi chú) → `POST …/qc {outcome:'fail', redo_required:true, note}` rồi `POST /work-orders/{id}/redo {qc_result_id, work_order_version, instruction}`.
   Tiêu chí kiểm là mảng tự do (`QcSubmit.criteria: list[dict]`, `v3_specialized.py:70-74`); UI chỉ gửi một tiêu chí cố định. Màn hình QC (`/operations/qc`) chỉ lọc ticket có phiếu `completed` (`staff/connected/ConnectedOperations.tsx:344-353`).
2. *Backend QC* (`submit_qc`, `v3_specialized.py:86-128`): `redo_required` chỉ hợp lệ với `outcome='fail'` (422); BQL có quyền (403); ticket chưa `closed|cancelled` (409); **người đã có phân công `accepted|completed` trên phiếu không được nghiệm thu chính phiếu đó** — "QC must be performed by an independent reviewer" (403, `:96-101`); nếu ticket đang `resolved` thì hủy các `work_approvals` `customer_completion` còn `pending` và đưa ticket về `in_progress` (`:102-108`); phiếu phải `completed` (409); ghi `vh_qc_results(outcome ∈ pass|fail|inconclusive)`; sự kiện `work_order.qc_recorded`; gọi `publish_completion`.
3. *Công bố kết quả* (`publish_completion`, `v3_completion.py:7-36`): nếu ticket chưa cuối và **mọi** phiếu (trừ `cancelled|rejected` và trừ phiếu đã có lượt làm lại) đều `completed` với QC mới nhất `pass`, thì tạo `work_approvals(kind='customer_completion', status='pending')` gửi người yêu cầu, đặt ticket `resolved` (`resolved_at=now()`), sự kiện `ticket.resolution_published`, thông báo cư dân.
4. *Làm lại* (`create_redo`, `:131-187`): BQL có quyền; phiếu nguồn đúng `version` và `completed`; QC mới nhất phải đúng `qc_result_id`, `outcome='fail'` và `redo_required` (409); mỗi kết quả QC chỉ có một lượt làm lại (409). Tạo phiếu mới `queued` cùng nhóm/chuyên môn với mô tả = `instruction`, và `vh_qc_redo_orders`; sự kiện `work_order.redo_created`. Phiếu làm lại đi tiếp theo 3.8.
5. *Cư dân xác nhận*: UI `RequestDetail` có nút xác nhận hoặc "yêu cầu xử lý lại" kèm lý do (`resident/features/requests/Requests.tsx:136-221`) → `live.decide(...)` (`resident/app/App.tsx:553-558`) → `POST /resident/approvals/{id}/decision {approved, note, version}` + header `Idempotency-Key` (`resident/services/use-connected-resident.ts:403-427`; `v3_resident.py:478-575`). Ghi chú mặc định khi đồng ý: "Tôi xác nhận kết quả đã hoàn tất." (`resident/services/use-connected-resident.ts:419`).
6. *Đóng thủ công của BQL*: `PATCH /tickets/{id}/status` (`v3_mutations.py:215-265`) — **chỉ dùng được cho ticket có cờ `requiresPlan`**; ticket không theo phương án không thể `resolved|closed` bằng tay (409 "Completion requires all QC results and the resident decision", `:222-223`). Staff-web nối thật không có nút này.
7. *Đánh giá nhân viên*: `POST /resident/assignments/{id}/review {score 1–5, comment ≤ 2000}` (`v3_reception.py:232-312`): chỉ người yêu cầu của ticket; phiếu phải `completed`; cư dân phải đã `approved` phê duyệt `customer_completion`; trùng đánh giá cùng nội dung thì trả bản cũ, khác nội dung → 409; ghi `ticket_reviews`, sự kiện `work.reviewed`. **Không có màn hình nào gọi route này.**

**Trạng thái và chuyển trạng thái.**
* `vh_qc_results.outcome ∈ {pass, fail, inconclusive}`; một kết quả `fail` coi là "chưa giải quyết" cho tới khi có kết quả mới hơn hoặc lượt làm lại đã `completed` và có QC `pass` (`UNRESOLVED_QC`, `v3_mutations.py:19-33`).
* `work_approvals.status` của `customer_completion`: `pending → approved | rejected | cancelled` (`cancelled` do QC mới, `v3_specialized.py:103-107`).
* Ticket: xem bảng ở 3.2. Quyết định của cư dân (`v3_resident.py:527-561`):

| Quyết định | Ticket **có phương án** | Ticket **không có phương án** |
|---|---|---|
| Đồng ý | phiếu của phê duyệt phải `completed` và ticket chưa cuối (409); ticket → `closed` chỉ khi **không còn** phiếu bắt buộc nào chưa xong, chưa được cư dân chấp nhận, hoặc còn QC `fail` chưa giải quyết; còn thì giữ nguyên | ticket phải đang `resolved` (409); **mọi phiếu** (trừ đã hủy/làm lại) phải `completed` và QC mới nhất `pass` (409); ticket → `closed` |
| Từ chối | ticket → `in_progress` (phiếu giữ `completed`) | ticket → `triaging`, `reopen_count + 1` (lịch sử phiếu, bằng chứng, QC được giữ) |

* Khi đóng: `closed_at=now()`; khi không đóng: `resolved_at` xóa (`:554-561`).

**Quy tắc nghiệp vụ.** Xác nhận của cư dân cần header `Idempotency-Key` (8–120), `version` ticket khớp (409), lý do từ chối ≥ 8 ký tự (422), phê duyệt còn `pending` và chưa hết hạn (409) (`v3_resident.py:500-522`). Luồng "QC trước" (ticket do cư dân/Reception tạo): kết quả chỉ tới cư dân sau khi **mọi** phiếu bắt buộc qua QC; luồng "có phương án": cư dân có thể xác nhận ngay khi nhân viên báo hoàn thành, QC là tùy chọn nhưng nếu đã `fail` thì chặn (`:533-536`). `PATCH` đóng thủ công ticket có phương án đòi: plan `approved`, không còn QC `fail`, phiếu bắt buộc đã xong, và (khi `closed`) mọi phiếu `completed` đã có `customer_completion` `approved` (`v3_mutations.py:222-256`). Cột `work_orders.required` được đọc (`:237,242`) nhưng không có mã nào đặt nó (mặc định: chưa xác minh).

**Dữ liệu.** `vh_qc_results(tenant_id, work_order_id, outcome, criteria, redo_required, note, checked_by, checked_at)`, `vh_qc_redo_orders(qc_result_id, source_work_order_id, redo_work_order_id, created_by)`, `work_approvals`, `tickets`, `work_orders`, `ticket_reviews(ticket_id, assignment_id, reviewer_user_id, staff_id, score, comment, submitted_at)`, `ticket_events`, `notification_deliveries`.

**Nguồn.** `v3_specialized.py:70-187`, `v3_completion.py`, `v3_mutations.py:19-33,215-265`, `v3_resident.py:478-575`, `v3_reception.py:232-312`, `staff/connected/ConnectedOperations.tsx:645-705`, `resident/features/requests/Requests.tsx`.

---

### 3.16 Vệ sinh (kế hoạch) và nhà thầu

**Tác nhân.** BQL hoặc người thực hiện được giao (nhân viên vệ sinh: người có chuyên môn category `cleaning`, 4.1). **Không có màn hình nối thật** (`sanitation`, `contractor` hiện "Chức năng chưa được nối đầy đủ", `staff/connected/ConnectedOperations.tsx:354-361`); có trong demo `/demo/ui` (`/work-orders/{id}/cleaning-plan`, `/contractor`).

**Các bước.**
1. *Kế hoạch vệ sinh*: `GET`/`PUT /work-orders/{id}/cleaning-plan {plan: object tự do, status, version?}` (`v3_specialized.py:190-236`).
2. *Tiến độ nhà thầu*: `GET`/`PUT /work-orders/{id}/contractor {status, worker_name?, materials[], note?, version?}` (`:239-288`).
Cả hai cần `can_work_order` (BQL có quyền hoặc phân công `accepted`) (403) (`:35-45`).

**Trạng thái.** Kế hoạch: `status ∈ {draft, in_progress, completed, cancelled}`. Nhà thầu: `status ∈ {pending, accepted, rejected, in_progress, completed}`. **Không có từ điển chuyển trạng thái**: mọi giá trị hợp lệ có thể đặt từ mọi giá trị khác.

**Quy tắc nghiệp vụ.** Khóa lạc quan: nếu bản ghi đã có thì `version` gửi lên phải bằng version hiện tại (409); nếu chưa có thì không được gửi `version` (kế hoạch: 409 "Cleaning plan does not exist yet"; nhà thầu: so sánh `None`) (`:217-221,268-270`). Mỗi lần lưu tăng `version`, ghi sự kiện `cleaning_plan.saved` / `contractor.progress_recorded`. Nội dung `plan`/`materials` không được kiểm lược đồ. Không có bước nào cho "kết thúc lượt vệ sinh" ràng buộc với hoàn tất phiếu. Phiếu `cleaning` đi theo luồng phiếu thông thường (3.8–3.9) — mã không phân nhánh theo `cleaning`; chỉ có nhánh riêng cho `security`.

**Dữ liệu.** `vh_cleaning_plans(tenant_id, work_order_id, plan, status, updated_by, version)`, `vh_contractor_updates(tenant_id, work_order_id, status, worker_name, materials, note, updated_by, version)`, `ticket_events`.

**Nguồn.** `v3_specialized.py:190-288`, `scripts/add_cleaning_service.py`.

---

### 3.17 An ninh: cảnh báo khẩn cấp, điều động/hủy, điểm tuần tra, báo cáo sự cố, bàn giao ca

**Tác nhân.** BQL phụ trách (tạo cảnh báo, leo thang, duyệt điều động/hủy); bảo vệ (xác nhận cảnh báo, kiểm tra điểm, báo cáo sự cố, bàn giao ca); quản trị viên (tạo điểm tuần tra). **Không có màn hình nối thật.** Demo `/demo/ui` chỉ có điểm tuần tra, sự cố, bàn giao (`business.js`).

**A. Cảnh báo khẩn cấp có chuỗi liên hệ** (`v3_security.py`).
1. Điều kiện: ticket đang `is_emergency` và chưa `closed|cancelled`, có tòa nhà. BQL gọi `POST /tickets/{id}/emergency-alerts {message ≤ 2000, ticket_version, idempotency_key ≤ 160}` (`:180-247`; 409 nếu lệch phiên bản, chưa khẩn cấp, thiếu tòa, hoặc không có người nhận đang hoạt động).
2. Hệ thống tạo `security_alerts` và một `security_alert_deliveries` cho mỗi `security_emergency_contacts` `active` của tòa (user phải `active` và còn membership `active`) (`:212-238`); gửi cho người đứng đầu hàng: `status 'waiting'→'pending'`, `notified_at`, `deadline_at = now + ack_timeout_seconds`, thông báo `alert:{alert}:{delivery}` (`:109-152`).
3. Người nhận xác nhận: `POST /security/alerts/{id}/ack {version}` (`:296-361`): chỉ người nhận đang chờ; quá hạn → 409 "ACK deadline passed; management must escalate"; thành công → delivery `acknowledged`, các delivery còn `waiting` → `cancelled`, alert `acknowledged`, thông báo người tạo.
4. Không ai xác nhận: BQL bấm leo thang `POST /security/alerts/{id}/escalate {version}` (`:364-412`): chỉ khi hạn của người nhận hiện tại đã qua (409 nếu còn thời gian); delivery → `timed_out`, chuyển sang người kế tiếp; hết người → alert `exhausted`, các delivery chờ → `cancelled`, thông báo người tạo. **Không có bộ đếm giờ tự động**: leo thang chỉ xảy ra khi BQL gọi.
5. Đọc: `GET /security/alerts` (≤ 100), `GET /security/cameras?buildingId`, `GET /security/emergency-contacts?buildingId` (`:52-84,250-273`). Camera và liên hệ chỉ **đọc** (không có API thêm/sửa; dữ liệu mẫu ở `scripts/seed_v3_remaining.sql:15-26`: ack timeout 60 giây, hai liên hệ theo `position`).
* Trạng thái: `security_alerts.status`: `open → acknowledged | exhausted` (mã đọc `open` ở `:313`); `security_alert_deliveries.status`: `waiting → pending → acknowledged | timed_out`, `waiting → cancelled`.

**B. Yêu cầu điều động / hủy việc an ninh** (`v3_security.py:415-735`).
1. Người yêu cầu: BQL có quyền hoặc bảo vệ đã nhận phiếu: `POST /work-orders/{id}/security/dispatch-request {reason, work_order_version, idempotency_key, staff_id}` hoặc `…/cancel-request {reason, work_order_version, idempotency_key}`. Phiếu phải thuộc nhóm `security` (422); phiếu đúng phiên bản và chưa cuối (409); ticket chưa `closed|cancelled` (409); điều động chỉ cho phiếu `queued` và bảo vệ `active` có chuyên môn đúng, cùng đơn vị (422); chỉ một phê duyệt cùng loại đang chờ (409) (`:449-515`).
2. Tạo `work_approvals(kind ∈ management_security_dispatch | management_security_cancel, required_scope_id=scope management của đơn vị, status='pending', expires_at = now + 1 giờ)`; thông báo mọi `management` của scope đó (`:517-562`).
3. BQL quyết định qua `POST /approvals/{id}/decision` → `decide_security` (`:600-735`): phải `pending` và chưa hết hạn (409); người duyệt phải có vai trò `management` thuộc `required_scope_id` hoặc scope `tenant` (403); duyệt phải còn đúng `work_order_version` (409). *Điều động duyệt*: tự gọi `create_assignment` với hạn đề nghị **1 giờ** (`:651-663`). *Hủy duyệt*: hủy phân công `offered|accepted`, phiếu → `cancelled`, và nếu mọi phiếu của ticket đã cuối mà ticket chưa `closed|resolved` thì ticket → `cancelled` (`:664-689`). Thông báo cho người yêu cầu và bảo vệ liên quan (`:700-731`).
* Trạng thái `work_approvals`: `pending → approved | rejected`; hết hạn khi `expires_at<=now()` (409 khi quyết định).

**C. Điểm tuần tra** (`v3_specialized.py:379-432`): `GET /security/checkpoints?siteId`; `POST` chỉ quản trị viên (403 nếu khác) tạo điểm `status='pending'` (`name`, `location`, `sort_order`); `PATCH …/{id} {status ∈ checked|missed, notes}` ghi `guard_user_id`, `checked_at`. Quyền xem/ghi: `site_access` (staff/management scope tenant hoặc site) (`:48-67`).
**D. Báo cáo sự cố an ninh** (`:435-518`): `POST /security/incidents {site_id, ticket_id?, title, location, severity ∈ p1..p4 hoặc business_severity ∈ P0..P3, report}` — hai giá trị phải khớp (`P0→p1, P1→p2, P2→p3, P3→p4`); ticket (nếu có) phải thuộc cùng site (422); tạo ở trạng thái `investigating`; `PATCH {status ∈ investigating|resolved|escalated_to_police, report}` **không có ràng buộc thứ tự**; "escalated_to_police" chỉ ghi nhận trạng thái, không gọi hệ thống ngoài (`services/vinhomes-api/README.md:121`). Sự kiện `security.incident_reported|updated` gắn vào ticket nếu có.
**E. Bàn giao ca** (`:521-577`): `POST /security/handovers {site_id, shift_name ∈ ca_sang|ca_chieu|ca_dem, shift_date, to_user_id (user active), payload}`; người nhận (hoặc quản trị viên) `POST …/{id}/confirm` → `confirmed=true`; xác nhận lần hai → 409.

**Quy tắc chung.** Phiếu `security` không hủy qua PATCH (`v3_mutations.py:504-507`) và không phân công nếu chưa có phê duyệt điều động khớp (`:593-602`). Bảo vệ có `security_alert_deliveries` được thấy ticket tương ứng (`v3_auth.py:145-149`). Tài liệu cũ nói "API chặn hoàn tất ticket khẩn cấp khi chưa có ACK" (`docs/backend/HUONG_DAN_DEMO_MOCK.md`, mục 5) — mã hiện tại **không** có kiểm tra này (xem 6.6).

**Dữ liệu.** `security_alerts`, `security_alert_deliveries`, `security_cameras`, `security_emergency_contacts`, `vh_security_checkpoints`, `vh_security_incidents`, `vh_security_handovers`, `work_approvals`, `work_assignments`, `notification_deliveries`, `ticket_events`.

**Nguồn.** `v3_security.py`, `v3_specialized.py:379-577`, `v3_mutations.py:504-507,593-602`, `scripts/seed_v3_remaining.sql`.

---

### 3.18 Hóa đơn, thanh toán và doanh thu sửa chữa

**Tác nhân.** BQL phụ trách (lập, phát hành hóa đơn, ghi thanh toán thử); không có màn hình nối thật (`/demo/ui` cũng không có hóa đơn). Kiểm tra: `invoice_access` đòi `_responsible_management` (`v3_billing.py:42-67`) — cư dân **không** xem được hóa đơn qua API này.

**Các bước.**
1. *Lập hóa đơn*: `POST /tickets/{id}/invoices {issued_by_staff_id, bill_to_user_id, work_order_id?, lines[1..30], idempotency_key ≤ 160}` (`:70-201`).
2. *Phát hành*: `POST /invoices/{id}/issue` (`:250-266`) — `draft → issued`, `issued_at=now()`, sự kiện `invoice.issued`; gọi lại khi đã `issued` trả kết quả cũ.
3. *Ghi thanh toán (chỉ chế độ demo)*: `POST /invoices/{id}/demo-payments {amount > 0, idempotency_key}` (`:269-345`) — `409` ngoài demo; hóa đơn phải `issued`; số tiền ≤ còn nợ; tạo `payment_intents(provider='demo', status='succeeded')`, `payments(reconciliation_status='confirmed')`, `payment_allocations`; sự kiện `payment.demo_recorded`.
4. *Xem*: `GET /invoices/{id}` (kèm dòng, `collectedAmount` = tổng phân bổ của thanh toán `confirmed`, `outstandingAmount`), `GET /tickets/{id}/financial-summary` (ước tính từ `vh_ticket_plans` + hóa đơn) (`:204-247`).
5. *Doanh thu*: xem 3.19 (`issued-revenue`, `repair-revenue`).

**Trạng thái.** `invoices.status`: `draft → issued` (mã không có `void`, `paid`, `cancelled`). `payments.reconciliation_status`: mã chỉ tạo `confirmed`. **Không có hoàn tiền, hủy hóa đơn, ghi giảm, hay cổng thanh toán thật** (tìm toàn gói không thấy chữ "refund"; xem 6.7).

**Quy tắc nghiệp vụ.** Mỗi dòng: nhóm dịch vụ `enabled`; `quantity > 0` (≤ 12 chữ số, 3 thập phân); `unit_price ≥ 0` (18, 2); `discount` ≥ 0 và không vượt thành tiền; `tax_rate` 0…1 (4 thập phân); thành tiền, thuế làm tròn 2 chữ số ROUND_HALF_UP (`:21-31,141-160`). Người lập (`issued_by_staff_id`) phải là nhân viên `active` thuộc đúng đơn vị quản lý của ticket (422, `:105-114`). Người thanh toán (`bill_to_user_id`) phải là thành viên `active`, và phải là người yêu cầu ticket **hoặc** tài khoản BQL có trách nhiệm của đơn vị (422) — "Payer responsibility is an explicit input from management" (`:115-140`). Phiếu (nếu có) phải thuộc ticket (422). Số hóa đơn là `"DEMO-" + 20 ký tự hex` (không có quy tắc đánh số thật, `:168`); tiền tệ `VND`; `discount_total` luôn lưu 0 (`:163`). Idempotency theo `uuid5(tenant, ticket, người, khóa)` + băm nội dung (`:77-97`).

**Dữ liệu.** Ghi: `invoices`, `invoice_lines`, `payment_intents`, `payments`, `payment_allocations`, `ticket_events`. Đọc: `staff_profiles`, `tenant_memberships`, `scoped_user_roles`, `vh_ticket_plans`. Dữ liệu mẫu: 20 hóa đơn `issued` (`scripts/seed_v3_faker.sql:144-153`).

**Nguồn.** `v3_billing.py`, `scripts/seed_v3_faker.sql`.

---

### 3.19 Báo cáo và xuất DOCX

**Tác nhân.** BQL có phạm vi tòa nhà (hoặc quản trị viên). Kiểm tra: `_management_building` (`v3_reports.py:21-57`, 403 nếu ngoài phạm vi, 404 nếu tòa không hoạt động).

**Các bước.**
1. UI nối thật `staff/workspace/LiveReportsPage.tsx` (trang Báo cáo, chỉ BQL; `staff/connected/ConnectedOperations.tsx:438`): chọn tòa, loại báo cáo ("Tần suất sự cố" hoặc "Giá trị hóa đơn đã phát hành"), nhóm dịch vụ (cho doanh thu), khoảng ngày (mặc định 30 ngày gần nhất theo giờ Việt Nam, `:22-23`). Ngày cuối do người dùng nhập là bao gồm; UI cộng thêm 1 ngày để gọi API nửa mở (`:37-39`). Gọi `GET /reports/incident-frequency` hoặc `/reports/issued-revenue`; tải `…docx` (`:43-62`).
2. Backend (`v3_reports.py`): `incident-frequency` (đếm ticket `request_kind='incident'` theo tháng và `incident_types.name`; `fromDate < toDate` bắt buộc, 422) và `issued-revenue` (cộng `invoice_lines` của hóa đơn `issued` theo tháng `issued_at`, theo nhóm dịch vụ; nhóm phải `enabled`, 404) (`:60-107,138-210`). DOCX là tài liệu Word tối thiểu (mỗi dòng một đoạn, không định dạng) (`:110-135`).
3. Báo cáo mở rộng (`v3_report_jobs.py`, **không có UI**): `GET /reports/filter-options` (tòa trong phạm vi, nhóm dịch vụ, nhân viên của các đơn vị phủ), `employee-performance` (số việc, hoàn thành, đúng hạn so với `tickets.resolution_due_at`, thời gian xử lý trung bình, số lần làm lại, điểm đánh giá), `employee-feedback`, `repair-revenue` (đã lập hóa đơn / đã thu theo phân bổ `confirmed` / còn nợ, phân bổ theo tỷ lệ cho hóa đơn nhiều nhóm; `laborMaterialsSplit: null` vì dòng hóa đơn không phân biệt công/vật tư), `incident-frequency-summary` (theo ngày/tuần/tháng, có tỷ lệ), `supporting-records` (`tickets|work_orders|invoices`, ≤ 100/lần) (`:28-276`).
4. Tệp xuất lưu: `POST /reports/exports {kind ∈ incident_frequency|issued_revenue, building_id, category_id?, from_date, to_date, format:'docx', idempotency_key}` (`:279-345`) → tạo `vh_report_exports(status='ready', content=DOCX)` **đồng bộ** (`execution:"synchronous"`); `GET /reports/exports/{id}` và `/content` chỉ cho **người tạo** (`:348-397`).

**Trạng thái.** `vh_report_exports.status`: mã chỉ tạo `ready` (cột `error_code` có đọc; giá trị khác chưa xác minh).

**Quy tắc nghiệp vụ.** Khoảng ngày: `from < to` và không quá 3660 ngày (10 năm) cho nhóm báo cáo mở rộng (`v3_report_jobs.py:22-25`). Doanh thu đếm theo **hóa đơn đã phát hành**, không phải tiền đã thu (ghi chú trên UI, `staff/workspace/LiveReportsPage.tsx:73`). Báo cáo tần suất nhóm theo `incident_types` nhưng **không có mã nào đặt `tickets.incident_type_id`**, nên mọi dòng rơi vào "Không phân loại" trừ khi DB tự đặt (xem 6.8). Idempotency xuất tệp theo (người, khóa) + băm nội dung (409 nếu lệch) (`v3_report_jobs.py:292-314`).

**Dữ liệu.** Đọc: `tickets`, `incident_types`, `invoices`, `invoice_lines`, `payments`, `payment_allocations`, `work_assignments`, `work_orders`, `ticket_reviews`, `vh_qc_redo_orders`, `staff_profiles`, `management_coverage`. Ghi: `vh_report_exports`.

**Nguồn.** `v3_reports.py`, `v3_report_jobs.py`, `staff/workspace/LiveReportsPage.tsx`.

---

### 3.20 Nhật ký kiểm toán và tổng quan quản trị

**Tác nhân.** Quản trị viên (`admin()`).

**Các bước.** UI `staff/connected/admin/Audit.tsx`, `Overview.tsx` (trang "Nhật ký", "Tổng quan vận hành").
1. `GET /admin/audit-events` (`v3_admin.py:133-166`): lọc `kind` (tiền tố loại sự kiện, `^[a-z_.-]*$`), `from`/`to` (ngày theo giờ Việt Nam; `to ≥ from`, 422), `actor`, `action`, `search`, `result ∈ {success, failed, recorded}`; phân trang bằng cặp (`before`, `before_id`), `limit` 1–100. `result` suy ra: `failed` nếu `payload.ok=false|success=false|status='failed'` hoặc loại kết thúc `.failed`; `success` nếu `ok|success=true`; còn lại `recorded` (`:149-150`). Trả danh sách `kinds` (phần trước dấu chấm đầu tiên) và `actions` để lọc.
2. `GET /admin/audit-events/export?from&to&…` (`:179-213`): CSV UTF-8 có BOM, tên `nhat-ky-{từ}-{đến}.csv`, cột: thời điểm (giờ Việt Nam), sự kiện, người/agent, loại người thực hiện, loại đối tượng, đối tượng, chi tiết; sắp cũ → mới; tối đa **50.000** dòng (413 nếu vượt); ô bắt đầu bằng `= + - @` được thêm `'` chống công thức (`:169-176`); việc xuất tự ghi `audit.exported` (`:210`).
3. `GET /admin/overview` (`:216-233`): số ticket mở (`not in (closed, cancelled)`), số ticket quá hạn (`resolution_due_at<now()`), số membership `pending`, số ticket mỗi ngày trong 14 ngày gần nhất (giờ Việt Nam), 5 tài khoản chờ duyệt đầu.

**Loại sự kiện ghi vào `audit_events`** (hàm `audit`, `v3_audit.py:8-29`; `initiator_kind='person'`): `account.password_reset`, `account.deleted`, `account.role_granted`, `management_unit.created`, `audit.exported`, `plan.presentation_updated`, `reception.delegation_issued`, `team.created`, `reception_supervisor.input_received`, `reception_supervisor.result_received` (nguồn: các lời gọi `audit(` đã liệt kê ở 3.1, 3.4, 3.7, 3.14, 3.24). Sự kiện của riêng ticket nằm ở `ticket_events` (3.22), không nằm ở `audit_events`. **Không được ghi**: tạo tài khoản và đổi vai trò/trạng thái qua `/auth/accounts*`, quyết định phê duyệt, tạo hóa đơn… (các thao tác này chỉ để lại `ticket_events` hoặc không để lại gì ở nhật ký quản trị).

**Dữ liệu.** `audit_events(tenant_id, actor_user_id, initiator_kind, initiator_id, event_type, target_type, target_id, payload, correlation_id, created_at)` đọc/ghi; `users`, `tickets`, `management_units` đọc để dán nhãn.

**Nguồn.** `v3_admin.py:133-233`, `v3_audit.py`, `staff/connected/admin/Audit.tsx`, `staff/connected/admin/Overview.tsx`.

---

### 3.21 Tệp, ảnh và lưu trữ đối tượng

**Tác nhân.** Cư dân (ảnh phản ánh), nhân viên/BQL (ảnh bằng chứng), hệ thống; người vận hành (script di chuyển, dọn dẹp).

**Các đường tải lên.**
| Đường | Endpoint | Ai | Ghi chú | Nguồn |
|---|---|---|---|---|
| A. Ảnh bằng chứng của ticket (nhân viên/BQL) | `POST /tickets/{id}/direct-uploads` (khi có S3 công khai) → tải thẳng tới bucket → `POST /direct-uploads/{id}/complete`; nếu không: `POST /tickets/{id}/files?filename&mimeType&purpose` thân là byte ảnh | scoped | UI `staff/connected/ConnectedOperations.tsx:383-389` qua `packages/shared/direct-image-upload.ts` | `direct_uploads.py:100-149`, `v3_files.py:55-154` |
| B. Ảnh trong cuộc trò chuyện (cư dân) | `POST /resident/chats/{id}/direct-uploads` hoặc `POST /resident/chats/{id}/photos` | cư dân | UI `resident/services/use-connected-resident.ts:56-62` | `direct_uploads.py:94-97`, `v3_resident_support.py:62-124` |
| C. Ảnh của hợp đồng Case | `POST /api/domains/vinhomes/resident/photos` | cư dân | không có UI | `resident_photos.py:101-153` |
| D. Phiên tải ảnh cho agent (`image-uploads`) | `POST /resident/chats/{id}/image-uploads` → `PUT /image-uploads/{id}/content` → `POST /image-uploads/{id}/complete` | cư dân | lưu cục bộ (`storage:"local-demo"`) | `v3_conversation_images.py:48-284` |

**Quy tắc.**
* Chỉ `image/jpeg`, `image/png`, `image/webp`; tối đa **10 MiB** (`v3_files.py:23`, `direct_uploads.py:32`, `resident_contract.py:20`); đường A/B đọc ảnh bằng Pillow (`verify` + `load`), kiểm khớp định dạng khai báo và chữ ký byte (`v3_files.py:24-26,43-52,96-99`); đường C còn giới hạn 20.000.000 pixel, bỏ ảnh động, giải mã rồi mã hóa lại (`resident_photos.py:34-56`). Tên tệp phải là tên thuần (không đường dẫn, không ký tự điều khiển, ≤ 255).
* Tải trực tiếp S3 (`direct_uploads.py`): chữ ký POST ràng buộc `key`, `Content-Type` và **đúng** kích thước; phiên hiệu lực **5 phút** (`:87`); lúc `complete` backend đọc lại byte, so kích thước và SHA-256 đã khai, kiểm ảnh, ghi sang khóa `accepted/` (khóa `staging/` chỉ để tải lên) rồi xóa bản staging (`:106-149`). Idempotency theo (người, `idempotency_key`) và nội dung/mục đích khớp (`:55-68`). Đường A lưu `ticket_files(purpose ∈ issue|before|after|other)`.
* Khóa đối tượng khi lưu: `{tenant_prefix}{file_id.hex}{ext}` (đường A, `v3_files.py:86`); `{tenant_prefix}{file_id.hex}` không đuôi (đường B qua API, `v3_resident_support.py:100`); `{prefix}staging/{file}{ext}` rồi `{prefix}accepted/…` (S3 trực tiếp, `direct_uploads.py:76,134`); `{prefix}resident/{file}{ext}` (đường C, `resident_photos.py:127`).
* Quét mã độc: **không có**; `scan_status='clean'` và `encryption_mode='none'` được ghi cứng khi tạo `file_objects` (`v3_files.py:134-136`, `direct_uploads.py:138-140`, `resident_photos.py:141`), trái với yêu cầu "cần dịch vụ lưu trữ đối tượng và quét tệp" của README (`services/vinhomes-api/README.md:36-38`).
* Nơi lưu: `provider()` = `s3` nếu đặt `VINHOMES_API_S3_ENDPOINT`, ngược lại `local_fs` (`storage.py:24-26`); bản ghi `storage_locations.provider` phải trùng. Đường lưu đĩa chỉ được bật trên loopback, trừ khi `VINHOMES_API_VOLUME_FILE_STORAGE=1` (`v3_files.py:29-40`). Công cụ `python -m vinhomes_api.storage_setup` tạo bucket, (nếu có tài khoản admin MinIO) tạo người dùng chỉ đọc/ghi bucket đó, chép các tệp đĩa lên bucket và chuyển `storage_locations` sang `s3` (`storage_setup.py:59-86`).
* Truy cập: staff `GET /files/{id}/content?inline` (ticket phải hiển thị với người gọi; ảnh trò chuyện chưa gắn ticket đi qua `read_image`) (`v3_files.py:157-188`); liệt kê `GET /tickets/{id}/files` (`:191-201`); cư dân `GET /resident/photos/{id}` (chỉ tệp do chính mình tải thuộc chat/ticket của mình) (`v3_resident_support.py:127-145`); liên kết ký có hạn: 900 giây cho Case (`resident_photos.py:24-31`), 300 giây cho `conversation-images/{id}/read-access` (`v3_conversation_images.py:448-471`). Phản hồi luôn `private, no-store` + `nosniff`. **Không có bảng hay nhật ký truy cập tệp** (tìm trong toàn bộ mã: chưa thấy).
* Lưu giữ và dọn dẹp:
  - Ảnh cư dân chưa gắn: `files.retention_until = now + 24 giờ` khi tải ở đường B-api và C (`v3_resident_support.py:117`, `resident_photos.py:139`); khi gắn vào ticket hoặc Case thì `retention_until = NULL` (`v3_resident.py:418`, `resident_cases.py:242`).
  - `python -m vinhomes_api.file_cleanup` (nên chạy mỗi ngày, `file_cleanup.py:15`): (1) xóa tệp của phòng `kind='management'` chưa được tin nhắn nào dùng sau **24 giờ** (`KEEP`, `:28`), (2) đánh dấu phiên tải trực tiếp quá hạn `expired` và xóa đối tượng `staging/` cũ hơn **1 giờ** (`SETTLED`, `:30,54-72`).
  - `scripts/cleanup_resident_photos.py`: xóa ảnh Case chưa gắn đã hết hạn, mặc định chạy thử (`--apply` mới xóa), tối đa 1000/lần, chỉ `local_fs`, không đụng tệp `legal_hold` hoặc tệp còn được tham chiếu (`:19-57`).
  - Docker compose **không** lên lịch các tác vụ này (`deploy/compose.yml`, `deploy/README.md`); ảnh trò chuyện của cư dân (đường B) chưa gắn ticket **không** thuộc diện của tác vụ nào ở trên (xem 6.9).

**Trạng thái.** `files.status`: `staged → ready` (khi có `accepted_object_id`), và `deleted`/`deletion_pending` được mã dọn dẹp đọc/ghi (`file_cleanup.py:49-50`, `scripts/cleanup_resident_photos.py:35`); `file_objects.status`: `ready`, `deleted`; `file_uploads.status`: `issued → accepted | expired`; `vh_conversation_uploads.status`: `issued → uploaded → ready`; `evidence_items.status`: `active` (giá trị khác: chưa xác minh).

**Dữ liệu.** `files`, `file_objects`, `file_uploads`, `vh_conversation_uploads`, `storage_locations`, `ticket_files`, `evidence_items`, `execution_principals`, `message_files`, `vh_resident_photos`.

**Nguồn.** `v3_files.py`, `direct_uploads.py`, `storage.py`, `storage_setup.py`, `file_cleanup.py`, `v3_resident_support.py`, `v3_conversation_images.py`, `resident_photos.py`, `scripts/cleanup_resident_photos.py`, `packages/shared/direct-image-upload.ts`.

---

### 3.22 Thông báo, sự kiện và outbox

**Tác nhân.** Hệ thống (ghi); cư dân (đọc thông báo). Không có bộ phát thông báo.

**Cơ chế.**
1. *Sự kiện ticket (`ticket_events`)*: mỗi thay đổi nghiệp vụ gọi `record_event` — gán `seq = last_event_seq + 1`, `actor_kind='human'`, `idempotency_key` (mặc định = id sự kiện), `payload`, `from_status/to_status`; tăng `tickets.version` (`v3_mutations.py:88-111`). Sự kiện của agent dùng `agent_event` (`actor_kind='agent'`, `work_offers.py:17-32`). Loại sự kiện mã ghi: `ticket.created`, `ticket.routing_accepted`, `ticket.assessed`, `ticket.status_changed`, `ticket.evidence_attached`, `ticket.file_uploaded`, `ticket.conversation_images_attached`, `ticket.emergency_escalated`, `ticket.resolution_published`, `triage.review_requested`, `triage.review_resolved`, `plan.proposed`, `plan.management_decided`, `plan.resident_decided`, `plan.resident_change_requested`, `plan.presentation_updated`, `work_order.created`, `work_order.offered`, `work_order.status_changed`, `work_order.repair_proposed`, `work_order.qc_recorded`, `work_order.redo_created`, `work_assignment.responded`, `work_approval.decided`, `water.shutdown_requested|notified|started`, `water.restored`, `permission.requested|decided`, `technical.measurement_recorded`, `maintenance.confirmed`, `budget_approval.requested|decided`, `cleaning_plan.saved`, `contractor.progress_recorded`, `security.alert_created|acknowledged|escalated`, `security.approval_requested|decided`, `security.incident_reported|updated`, `invoice.created|issued`, `payment.demo_recorded`, `work.reviewed` (tổng hợp từ các mục 3.2–3.19).
2. *Thông báo trong ứng dụng (`notification_deliveries`)*: kênh duy nhất là `in_app`; khi tạo, `status='pending'`, `available_at=now()`; khóa duy nhất (`tenant, user, channel, dedupe_key`) chống trùng (`ON CONFLICT DO NOTHING`). Nơi sinh: ticket mới → BQL (`ticket:{id}:created`, `v3_resident.py:390-413`); BQL tiếp nhận → cư dân (`ticket:{id}:routing-accepted`, `v3_operations.py:292-304`); khẩn cấp → BQL (`ticket:{id}:emergency:{event}`, `v3_reception_operations.py:768-798`); công bố kết quả → cư dân (khóa = id sự kiện, `v3_completion.py:31-36`); phương án → cư dân (`plan:{id}:management`, `v3_plans.py:188-194`); khóa/mở nước → cư dân trong phạm vi (`water:{id}:shutdown|restored`, `v3_water.py:192-214`); an ninh (`alert:…`, `security-approval:…`, `v3_security.py:87-106`); phản hồi mẫu của Reception demo (`reception:{message}`, `v3_resident.py:217-219`).
3. *Đọc*: `GET /my/notifications` (≤ 100, theo `created_at` giảm dần) và `POST /my/notifications/{id}/read` đặt `read_at` (`v3_resident.py:596-623`). **Không mã nào đặt `sent_at` hoặc đổi `status` khỏi `pending`**; không có bộ gửi (push/SMS/email) trong gói.
4. *Giao diện*: trang "Thông báo" của resident-web **không** gọi `/my/notifications` mà tự dựng từ danh sách yêu cầu và hội thoại (`resident/app/App.tsx:678-690`, `resident/features/utilities/Utilities.tsx:153-229`); staff-web dựng chuông thông báo từ danh sách phiếu (`staff/connected/ConnectedOperations.tsx:325-328`), cũng không đọc bảng này. Hệ quả: các thông báo ở mục 2 chỉ nằm trong DB (xem 6.10).
5. *Sự kiện công khai của hồ sơ Case*: `vh_resident_public_events` và `vh_resident_outbox` được ghi cùng nhau (`resident_cases.py:145-150`); không có consumer của `vh_resident_outbox` trong gói.
6. *Outbox/sự kiện cũ*: `outbox/repository.py`, `events/*`, bảng `vh_outbox_message` (trạng thái `PENDING|PUBLISHED|DEAD_LETTER`, `db/outbox_message.py:25-28`) và `vh_business_event` (có trigger chống sửa, `migrations/versions/0007_vh_business_event.py`) thuộc mã không gắn route (mục 5.2).

**Dữ liệu.** `ticket_events`, `notification_deliveries`, `vh_resident_public_events`, `vh_resident_outbox`.

**Nguồn.** `v3_mutations.py:88-111`, `v3_resident.py:390-413,596-623`, `v3_completion.py`, `v3_plans.py`, `v3_water.py`, `v3_security.py`, `resident_cases.py:145-174`, `work_offers.py`.

---

### 3.23 SLA và hạn xử lý

**Kết luận: gói không cài đặt chính sách SLA.**
* `tickets.response_due_at` và `tickets.resolution_due_at` chỉ được **đọc** (danh sách/chi tiết, `v3_routes.py:111-117`; cư dân `v3_resident.py:453-454`; tổng quan quản trị `v3_admin.py:223`; báo cáo "đúng hạn" `v3_report_jobs.py:74-84`; cột hạn trên UI `staff/connected/ConnectedOperations.tsx:492`). **Không có mã, seed hay script nào ghi hai cột này** và không có bảng chính sách SLA trong mã.
* Chính sách triage có `max_fact_age_seconds` (86400) và `max_queue_wait_seconds` (3600) trong dữ liệu mẫu (`scripts/seed_v3_local.sql:53-64`, `scripts/provision_connected.py:130-135`) nhưng mã chỉ đọc `review_timeout_seconds` (`v3_triage.py:75,126-130`).
* Các hạn đang có trong mã (tổng hợp): đề nghị việc 24 giờ (`work_offers.py:14`) / 30 phút từ giao diện BQL (`staff/connected/ConnectedOperations.tsx:633-635`) / 1 giờ khi duyệt điều động an ninh (`v3_security.py:659`); phê duyệt an ninh hết hạn sau 1 giờ (`:529`); thời hạn xác nhận cảnh báo = `ack_timeout_seconds` của từng liên hệ (60 giây trong dữ liệu mẫu, `scripts/seed_v3_remaining.sql:24-25`); hạn duyệt triage = `review_timeout_seconds` (3600 giây); phiên 8 giờ; ảnh chưa gắn 24 giờ; phiên tải ảnh 5 phút; token Reception 10 phút; run Reception bỏ dở 15 phút.
* Mã cũ không gắn route có `vh_incident.sla_due_at` và cách tính "còn lại/quá hạn" (`incidents/schemas.py:73-87`, `migrations/versions/0002_vh_incident.py:64`).
* Bản nháp lược đồ (Phụ lục D.4) đã thiết kế SLA ở tầng DB — `sla_policies` (phút phản hồi / xử lý theo đơn vị × nhóm dịch vụ × ưu tiên × loại yêu cầu), `ticket_sla_cycles`, `ticket_sla_adjustments`, `ticket_escalations` — nhưng không có mã nào gọi chúng.

---

### 3.24 Trao đổi Reception ⇄ Supervisor (phần còn sót có chủ đích)

Không phải quy trình nghiệp vụ của miền; ghi lại để biết nó làm gì (`README.md:62-64`). Hợp đồng `schema_v2` giữa Reception và một "Supervisor" (phần quản lý agent đã bị gỡ):
* *Hộp thư vào của Supervisor*: Reception ghi thông điệp `ticket_submitted | information_provided | plan_approved | plan_rejected | plan_change_requested | cancel_requested` bằng `POST /api/domains/vinhomes/resident/reception-supervisor/messages` (`v3_reception_supervisor.py:497-611`), lưu `vh_reception_supervisor_messages(direction='reception_to_supervisor')`; đọc bằng `GET …/operations/resident-cases/reception-supervisor/teams/{team}/inbox` (`:614-637`).
* *Kết quả trả về*: `POST …/operations/…/reception-supervisor/results` nhận `accepted | in_progress | information_requested | plan_approval_requested | completed | failed | cancelled` (`:640-801`); `information_requested` / `plan_approval_requested` tạo `vh_reception_supervisor_pending` (một bản ghi chờ mỗi thế hệ ticket); `completed` đòi ticket đã `resolved|closed` và mọi phiếu bắt buộc `completed`; `cancelled` đòi ticket đã `cancelled`. Cư dân đọc `GET …/reception-supervisor/tickets/{id}/results` (`:804-832`).
* *Cư dân trả lời*: `GET /resident/supervisor-interactions` và `POST /resident/tickets/{id}/supervisor-response {decision ∈ information|approve|reject|request_changes, note ≤ 2000, ticket_version, request_id}` (`v3_resident_interactions.py:19-82`); thẻ giao diện `resident/features/requests/SupervisorResponse.tsx` và `resident/features/assistant/QuestionCard.tsx`.
* *Ràng buộc đáng chú ý*: thông điệp cùng `message_id` chỉ được gửi lại với đúng nội dung (409); snapshot ticket gửi lên phải khớp trạng thái hiện tại (409 "stale or mismatched"); mỗi thế hệ ticket chỉ `ticket_submitted` một lần (409); khi cư dân duyệt/từ chối phương án qua đường này thì gọi lại `v3_plans.resident_decision` (`:540-565`).
* **Không có ai đọc hộp thư và không có ai ghi kết quả** trong gói: các bảng `vh_reception_supervisor_*` chỉ được lấp bởi Reception khi đơn vị quản lý có Supervisor (dữ liệu mẫu demo `scripts/seed_v3_faker.sql:94-115`); bản đóng gói `provision_connected.py` không tạo Supervisor nên nhánh này không xảy ra (`v3_reception_operations.py:595-616`).
---

## 4. Danh mục tham chiếu

Chỉ liệt kê giá trị **xuất hiện trong mã, dữ liệu mẫu, script hoặc giao diện**. Ràng buộc CHECK/enum của DB V3 không có trong gói (xem 1.3, 6.1), nên cột "nguồn" luôn là mã hoặc dữ liệu mẫu.

### 4.1 Nhóm dịch vụ (`service_categories`)

| `code` | Tên trong dữ liệu | Nguồn |
|---|---|---|
| `technical` | "Technical" (seed cục bộ), "Kỹ thuật" (tổ chức thật) | `scripts/seed_v3_local.sql:22-24`, `scripts/provision_connected.py:42` |
| `security` | "An ninh demo", "An ninh" | `scripts/seed_v3_faker.sql:30-32`, `scripts/provision_connected.py:42` |
| `cleaning` | "Vệ sinh & cảnh quan" | `scripts/add_cleaning_service.py:48` |

* Mã có xử lý riêng theo `code`: `security` (phiếu an ninh không hủy bằng PATCH, cần phê duyệt điều động: `v3_mutations.py:504-507,593-602`; yêu cầu điều động/hủy: `v3_security.py:444`; không tự đề nghị cho người thực hiện: `v3_request_presentation.py:162-164`), `technical` (nhóm mặc định của báo khẩn cấp Reception: `reception/src/agent/tools.py:227`). `cleaning` không có nhánh riêng trong mã.
* Mọi nhóm phải `enabled` mới dùng được (`v3_resident.py:326`, `v3_mutations.py:170,333`). Cột `parent_id` được đọc (`v3_operations.py:79`) nhưng không dùng để suy luận.
* Phiếu thi công dùng chính `category_id` làm `required_specialty_id` (`v3_plans.py:257-263`, `staff/connected/ConnectedOperations.tsx:560-561`, `scripts/seed_v3_local.sql:105-115`).
* Biến cấu hình `VINHOMES_API_REPAIR_CATEGORY_CODES` có trong compose và env mẫu nhưng **không mã nào đọc** (`deploy/compose.yml:29`, `services/vinhomes-api/connected.env.example:31`).
* `incident_types(id, category_id, code, name)`: chỉ được đọc (`v3_operations.py:80`); không có dữ liệu mẫu hay route ghi.

### 4.2 Mức ưu tiên, mức độ, loại yêu cầu

| Danh mục | Giá trị | Nguồn |
|---|---|---|
| `tickets.priority` | `low`, `normal`, `high`, `critical` | `v3_triage.py:42`, `v3_resident.py:274`, `v3_reception_operations.py:89`, `reception/src/agent/tools.py:48` (agent chỉ dùng `low|normal|high`) |
| Mã hiển thị trên UI | `critical→P0`, `high→P1`, `normal→P2`, `low→P3` | `staff/connected/ConnectedOperations.tsx:86` |
| `severity` | `unknown`, `minor`, `moderate`, `major`, `critical`, `not_applicable` | `v3_mutations.py:270`, `v3_triage.py:41` |
| `urgency` (đánh giá) | `unknown`, `routine`, `soon`, `immediate` | `v3_mutations.py:271` |
| `stage` (đánh giá) | `intake`, `specialist`, `onsite`, `reassessment` | `v3_mutations.py:269` |
| `request_kind` | `incident`, `service_request` | `v3_mutations.py:136`, `v3_resident.py:92` |
| `triage_status` | `pending`, `review_required`, `confirmed` | `v3_triage.py:133-135,231-241` |
| Lý do duyệt triage | `unknown_facts`, `conflict`, `downgrade`, `emergency_override`, `overdue_review` | `v3_triage.py:45-46` |
| Kết quả quyết định triage | `review_required`, `applied`; chế độ `provisional`, `human_confirmed` | `v3_triage.py:105-108,215-217` |
| Mức an ninh | DB `p1…p4`, nghiệp vụ `P0…P3` (`P0→p1, P1→p2, P2→p3, P3→p4`) | `v3_specialized.py:440-451` |
| Lý do bàn giao Reception | `needs_staff`, `self_help_declined`, `self_help_failed`, `emergency` | `v3_reception_supervisor.py:86-88`, `v3_reception_runtime.py:101-102` |
| Loại khẩn cấp (từ khóa) | `fire`, `gas`, `electric`, `elevator`, `water`, `structure` | `v3_reception_runtime.py:36-43` |
| Nguồn dữ kiện | `customer_report`, `staff_verified`, `agent_inference` | `v3_reception_supervisor.py:46-51` |

### 4.3 Trạng thái các đối tượng (tổng hợp)

| Đối tượng | Giá trị mã dùng | Mục |
|---|---|---|
| `tickets.status` | `open, triaging, assigned, in_progress, resolved, closed, cancelled` | 3.2 |
| `work_orders.status` | `queued, offered, accepted, en_route, arrived, awaiting_approval, in_progress, completed, rejected, cancelled` | 3.8 |
| `work_assignments.status` | `offered, accepted, rejected, completed, cancelled` (+ `expired` suy ra) | 3.8 |
| `work_approvals.status` | `pending, approved, rejected, cancelled` (`cancelled` do QC mới) | 3.10, 3.11, 3.15 |
| `work_approvals.kind` | `customer_repair`, `customer_completion`, `management_water_shutdown`, `management_security_dispatch`, `management_security_cancel` | `v3_operations.py:200`, `v3_mutations.py:391,550` |
| `service_interruptions.status` | `proposed, approved, notified, active, restored, cancelled` | 3.11 |
| `vh_operational_requests` | `kind`: `utility_isolation, area_restriction, apartment_entry, vendor_dispatch`; `status`: `pending, approved, rejected, completed, cancelled` | 3.12 |
| `vh_budget_approvals.status` | `pending, approved, rejected` | 3.13 |
| `vh_ticket_plans.status` | `management_pending, resident_pending, approved, rejected, revision_requested` | 3.14 |
| `vh_qc_results.outcome` | `pass, fail, inconclusive` | 3.15 |
| `vh_cleaning_plans.status` | `draft, in_progress, completed, cancelled` | 3.16 |
| `vh_contractor_updates.status` | `pending, accepted, rejected, in_progress, completed` | 3.16 |
| `security_alerts.status` | `open, acknowledged, exhausted` | 3.17 |
| `security_alert_deliveries.status` | `waiting, pending, acknowledged, timed_out, cancelled` | 3.17 |
| `vh_security_checkpoints.status` | `pending, checked, missed` | 3.17 |
| `vh_security_incidents.status` | `investigating, resolved, escalated_to_police` | 3.17 |
| `invoices.status` | `draft, issued` | 3.18 |
| `tenant_memberships.status` | `pending, active, suspended, ended` | 3.1 |
| `ticket_triage_reviews.status` | `pending, approved, rejected` | 3.6 |
| `ticket_routing_history.status` | `requested, accepted` | 3.5 |
| `vh_resident_cases.status` / `public_status` | `processing, confirmation, completed` / `received, processing, confirmation, completed` | 3.3 |
| `files.status` | `staged, ready, deleted, deletion_pending` | 3.21 |
| `file_uploads.status` | `issued, accepted, expired` | 3.21 |
| `vh_conversation_uploads.status` | `issued, uploaded, ready` | 3.21 |
| `notification_deliveries.status` | `pending` (không đổi) | 3.22 |
| `agent_runs.status` | `running, succeeded, failed` | 3.4 |
| `vh_command_receipt.status` | `IN_PROGRESS, COMPLETED` (có CHECK trong gói) | 3.4 |
| `agent_teams.status` (đọc) | `queued, completed, failed, cancelled` (và trạng thái hoạt động khác — chưa xác minh) | 3.24 |

Nhãn tiếng Việt trong giao diện nhân viên: `open` "Mới tiếp nhận", `triaging` "Đang phân loại", `assigned` "Đã giao việc", `in_progress` "Đang xử lý", `resolved` "Chờ cư dân xác nhận", `closed` "Hoàn tất", `cancelled` "Đã hủy", `queued` "Chờ phân công", `offered` "Đã mời nhận việc", `accepted` "Đã nhận việc", `en_route` "Đang di chuyển", `arrived` "Đã đến hiện trường", `completed` "Đã thi công xong", `awaiting_approval` "Chờ đồng ý", `rejected` "Từ chối" (`staff/connected/ConnectedOperations.tsx:68-84`).

### 4.4 Các danh mục khác

| Danh mục | Giá trị | Nguồn |
|---|---|---|
| `role_code` | `customer`, `staff`, `management` | 2.1 |
| `access_scopes.kind` | `tenant`, `site`, `zone`, `building`, `management` | 2.5 |
| Mục đích bằng chứng | `issue`, `before`, `after`, `verification` | `v3_mutations.py:721` |
| Mục đích `ticket_files` | `issue`, `before`, `after`, `other` (+ `verification` không dùng) | `v3_files.py:63`, `direct_uploads.py:35` |
| Loại ảnh được nhận | `image/jpeg`, `image/png`, `image/webp` | `v3_files.py:24-26` |
| Ca trực bàn giao | `ca_sang`, `ca_chieu`, `ca_dem` | `v3_specialized.py:523` |
| Hành động trong `account_reviews` | `register`, `approve`, `reject`, `activate`, `suspend`, `delete` | `v3_accounts.py:137-141,187` |
| Nhà cung cấp tài khoản | `vinhomes-password-v1` | `password_auth.py:28` |
| `storage_locations.provider` / `purpose` | `s3` hoặc `local_fs` / `evidence` | `storage.py:24-26`, `v3_files.py:75-79` |
| `execution_principals.kind` | `user`, `workspace_service` | `v3_files.py:107-119`, `reception_delegation.py:116-118`, `scripts/seed_v3_remaining.sql:50-52` |
| `messages.visibility` / `sender_kind` | `customer`, `room` / `user`, `agent` | `v3_resident.py:146-149,196`, `v3_reception_runtime.py:114` |
| `channels.kind` | `reception`, `management` | `v3_resident.py:103-105`, `v3_admin.py:103` |
| Thông điệp Reception → Supervisor | `ticket_submitted, information_provided, plan_approved, plan_rejected, plan_change_requested, cancel_requested` | `v3_reception_supervisor.py:96-103` |
| Thông điệp Supervisor → Reception | `accepted, in_progress, information_requested, plan_approval_requested, completed, failed, cancelled` | `:168-176` |
| Lý do từ chối nhận việc trên UI | `BUSY`, `WRONG_SKILL`, `OFF_SHIFT`, `OTHER` | `staff/connected/field/model.ts:68` |
| Mốc "sẽ đến sau" trên UI | 15, 30, 60, 120 phút | `staff/connected/field/FieldJob.tsx:20` |
| Danh mục vật tư gợi ý (UI) | 16 mục từ `VT-VAN-DN15` đến `VT-SILICON` với đơn giá cố định | `staff/lib/field-flow.ts:18-35` |

### 4.5 Địa bàn mẫu

Miền `vinhomes`; site `ocean-park-1` "Vinhomes Ocean Park 1" (Gia Lâm, Hà Nội); 8 phân khu `sapphire, pavilion, zenpark, hai-au, ngoc-trai, san-ho, sao-bien, masteri-waterfront`; 14 tòa `S1.01, S1.02, S2.01, S2.05, P1, P2, R1.02, R1.03, M1, M2, M3, H1, H2, H3`; căn hộ `1201…1220` của S1.01; đơn vị quản lý `bql-sapphire` phủ phân khu Sapphire (`scripts/provision_connected.py:32-41,86-143`, `scripts/seed_v3_ocean_park.sql:15-39`). Dữ liệu demo: tenant `11111111-1111-5111-a111-111111111111`, 20 căn hộ, 20 cư dân, 21 ticket, 20 hóa đơn (`scripts/seed_v3_faker.sql`, `docs/backend/HUONG_DAN_DEMO_DATABASE_V3.md`, mục "Dữ liệu seed"). Masteri Waterfront do Masterise quản lý, không thuộc Vinhomes (chú thích `scripts/seed_v3_ocean_park.sql:5-7`).

---

## 5. Phần còn sót lại và mã không còn là quy trình

### 5.1 Dấu vết của Supervisor, quản lý agent và nền tảng

* Trao đổi Reception ⇄ Supervisor: 3.24.
* Bảng nền tảng mà Reception còn dùng để ủy quyền: `agents, agent_versions, agent_runs, agent_teams, team_members, agent_releases, channel_agents, runtime_backends, runtime_identities, runtime_session_bindings, execution_principals` (`reception_delegation.py:62-100,103-170`, `v3_reception_operations.py:570-591,629-636,1016-1086`). README gốc xác nhận: backend cần schema do platform cũ tạo, "gồm cả bảng agent mà cơ chế ủy quyền còn dùng" (`README.md:62`).
* Quyền DB cấp cho bảng không còn mã dùng: `mcp_servers, mcp_tools, credentials, knowledge_reviews, memory_candidates, retrieval_runs, retrieval_hits, team_mailbox, team_tasks, routine_runs, vh_private_chats, vh_private_chat_sources, vh_session_sources, vh_connection_policy, vh_external_call_confirmations, vh_agent_skills, vh_agent_reviews, admin_model_registry, admin_role_models, vh_agent_eval_*` (`scripts/grant_v3_api_role.sql:14,23,35-76`).
* Dữ liệu mẫu còn agent/phòng/bộ nhớ: `agents` (`demo-supervisor`, `demo-report`, `demo-reception`, `demo-room-unlinked`, `system-reception`), `channel_agents`, `agent_versions`, `memory_namespaces`, `memory_candidates` (`scripts/seed_v3_faker.sql:94-115`, `scripts/seed_v3_remaining.sql:5-14,46-61`, `scripts/provision_connected.py:193-202`); `GET /demo/fixtures` trả `roomAgents` (`v3_demo.py:30`).
* Mã tham chiếu mô-đun không còn: `file_cleanup.py:7` nhắc `v3_room_files.py` (không có trong gói); `file_cleanup.clean` chỉ dọn tệp của phòng `kind='management'` (`:40-47`).
* Staff-web: `staff/connected/admin/queries.ts:5-27,57-62` (kiểu `RegisteredModel`, `ModelRegistry`, gọi `/admin/model-registry`), `Overview.new_connections` (`:32`), cột "agent"/"kết nối" trong `staff/connected/admin/Units.tsx:25-27,120-121`, khóa `["coordination"]` (`staffsrc/lib/admin/queries.ts:67`), và lớp preview có phòng, agent, `coordinationSessions` (`staff/workspace/model.ts:21-45`, `staff/components/incidents-workspace.tsx:121`).
* `packages/shared/attachments.ts` (đính kèm tin nhắn cho nền tảng cũ; tham chiếu `server/src/channels/attachment-parts.ts`) chỉ được kiểm thử, không app nào import (`packages/shared/attachments.test.ts`).
* `reception/src/tools/*` (facade 14 công cụ "PH16 draft") không được runtime dùng (runtime dùng `agent/tools.py` và `runtime/backend.py`; `reception/README.md`, mục "Reception tools — PH16").
* Cấu hình xác thực cũ: `VINHOMES_API_AUTH_URL` (chuyển cookie tới `/api/me` của nền tảng) và `deployment_tenant_uuid` (khớp `server/src/db/deployment-scope.ts`) (`v3_config.py:10-13`, `v3_auth.py:32-55`).

### 5.2 Mã `vh_*` cũ không gắn route (không phải quy trình đang chạy)

`main.py` không import các gói sau (`main.py:20-49`); `services/vinhomes-api/README.md:7` gọi chúng là tham chiếu cũ và cấm chạy migration Alembic trên DB V3.

| Mô-đun | Nội dung | Nguồn |
|---|---|---|
| `incidents/`, `tasks/`, `db/incident.py`, `db/task.py` | `vh_incident` (`NEW/OPEN/RESOLVED/CLOSED`, giai đoạn `INTAKE/TRIAGE/PLANNING/EXECUTION/QC/RESIDENT_CONFIRMATION`, `sla_due_at`), `vh_task` (`OPEN/ASSIGNED/IN_PROGRESS/BLOCKED/DONE/CANCELLED`; miền `SANITATION/LANDSCAPE/TECHNICAL/SECURITY`) | `db/incident.py:16-29`, `db/task.py:15-28` |
| `actions/`, `approvals/`, `rules/` | yêu cầu hành động (`PROPOSED…SUCCEEDED/FAILED`), phê duyệt (`PENDING/APPROVED/REJECTED/EXPIRED`), luật demo: `CLEAN_AREA`, `WATER_PLANTS` cho phép; `HIGH_RISK_MAINTENANCE` cần duyệt; `MATERIAL_PURCHASE` cần duyệt từ **500.000 VND**; `PROHIBITED_ACTION` bị từ chối | `db/action_request.py:25-43`, `db/approval.py:13-18`, `rules/demo.py:8,14-58` |
| `work_orders/` | phiếu cũ (`OPEN/ASSIGNED/IN_PROGRESS/COMPLETED/FAILED/CANCELLED`), phân công, checklist, hiện trường (tạm dừng/tiếp tục, check-in, bàn giao an ninh, chặn, leo thang, yêu cầu hỗ trợ, phản hồi nhà thầu, kế hoạch đến nơi) | `db/work_order.py:25-32`, `work_orders/routes.py`, `work_orders/field_operations_routes.py:186-429` |
| `evidence/`, `qc/`, `resolution/` | bằng chứng (`BEFORE/AFTER/QC/OTHER`), QC (`PASS/FAIL/INCONCLUSIVE`), kết luận | `db/evidence.py:27-31`, `db/qc_result.py:23-26` |
| `events/`, `outbox/`, `commands/` | sự kiện nghiệp vụ bất biến, outbox (`PENDING/PUBLISHED/DEAD_LETTER`), idempotency | `db/outbox_message.py:25-28`, `migrations/versions/0007…0014` |
| `request_context.py`, `config.py` | ngữ cảnh từ middleware tin cậy (chỉ các route cũ import), cấu hình `VINHOMES_API_APPROVAL_TTL_SECONDS`, `VINHOMES_API_RULE_SET` | `config.py:33-51` |
| `demo_api.py` + `tests/test_demo_api.py` | ứng dụng FastAPI giả lập hoàn toàn trong RAM, không dùng DB, chỉ được test dùng | `demo_api.py:1-12` |

Các quy trình hiện trường mà mã cũ có (tạm dừng, chặn việc, yêu cầu hỗ trợ, check-in/check-out an ninh, kế hoạch đến nơi) **không có tương đương** trong backend đang chạy.

---

## 6. Còn thiếu hoặc mâu thuẫn

> **Trạng thái xử lý (cập nhật sau khi tài liệu được viết).** Đã xong: lược đồ DB, ràng buộc, RLS và trigger nay nằm trong gói (`schema/migrations/0001…0005`, mục 6.1); dòng `runtime_backends` `reception-langgraph` có ở `0005_reference_data.sql`; Reception không còn gọi `GET /internal/reception/v1/model-config` (mục 6.2, gạch đầu dòng đầu); các test DB được dựng lại trên database sinh từ gói, trừ hai test sửa phương án chờ điểm vào đề xuất phương án. Các mục còn lại bên dưới vẫn đúng.

Sắp theo mức ảnh hưởng tới việc chạy đúng các quy trình ở mục 3.

### 6.1 Lược đồ DB và ràng buộc không nằm trong gói

* Tại thời điểm tôi đọc, Alembic chỉ tạo 16 bảng `vh_*` cũ (`vh_action_approval, vh_action_request, vh_business_event, vh_checklist, vh_checklist_version, vh_command_receipt, vh_evidence_ref, vh_file_object, vh_incident, vh_outbox_message, vh_qc_result, vh_qc_result_evidence, vh_rule_evaluation, vh_task, vh_work_order, vh_work_order_assignment`; `migrations/versions/0002…0015`). Chỉ **`vh_command_receipt`** được mã đang chạy dùng (`v3_reception_operations.py:157,182`); `migrations/versions/0001_vinhomes_schema_baseline.py` không tạo gì. Sau đó Alembic bị xóa khỏi cây làm việc và một bản nháp lược đồ 109 bảng xuất hiện (Phụ lục D): bản nháp **chưa commit**, nên với nhánh `dev_Vinhome` hiện tại kết luận bên dưới vẫn đúng.
* Các bảng mã đang chạy đọc/ghi **nhưng không tệp nào trong gói tạo ra**: `tickets, ticket_events, ticket_assessments, ticket_triage_decisions, ticket_triage_reviews, ticket_routing_history, ticket_files, ticket_reviews, work_orders, work_assignments, work_approvals, evidence_items, service_interruptions, interruption_scopes, notification_deliveries, channels, channel_memberships, channel_agents, messages, message_files, files, file_objects, file_uploads, storage_locations, users, accounts, sessions, tenants, tenant_memberships, scoped_user_roles, access_scopes, platform_admins, account_reviews, audit_events, domains, sites, zones, buildings, units, unit_residents, service_categories, incident_types, management_units, management_coverage, workspaces, workspace_members, staff_profiles, staff_specialties, staff_shifts, triage_policy_versions, triage_policy_bindings, execution_principals, agents, agent_versions, agent_runs, agent_teams, agent_releases, team_members, runtime_backends, runtime_identities, runtime_session_bindings, security_alerts, security_alert_deliveries, security_cameras, security_emergency_contacts, invoices, invoice_lines, payment_intents, payments, payment_allocations` và các bảng mở rộng `vh_assets, vh_sensor_readings, vh_technical_measurements, vh_maintenance_records, vh_operational_requests, vh_qc_results, vh_qc_redo_orders, vh_cleaning_plans, vh_contractor_updates, vh_budget_approvals, vh_security_checkpoints, vh_security_incidents, vh_security_handovers, vh_ticket_plans, vh_report_exports, vh_conversation_uploads, vh_resident_cases, vh_resident_case_tickets, vh_resident_submissions, vh_resident_photos, vh_resident_public_events, vh_resident_outbox, vh_resident_command_receipts, vh_resident_resolutions, vh_resident_resolution_photos, vh_resident_resolution_responses, vh_reception_supervisor_messages, vh_reception_supervisor_pending` (danh sách trích từ các câu SQL trong `*.py`/`*.sql`; xem Phụ lục B).
* `GET /ready` yêu cầu 17 bảng này tồn tại (`main.py:115-135`) — không có tệp nào tạo chúng.
* README và script trỏ tới `server/drizzle/0001_vinhomes_operations.sql`, `0002_vinhomes_qc_redo.sql`, `server/scripts/migrate.ts` (`services/vinhomes-api/README.md:27-29`, `scripts/setup_demo_database.ps1:15`, `scripts/provision_connected.py:62`) — không có trong gói. Tài liệu `docs/teams/chien/…` mà README trỏ tới (`services/vinhomes-api/README.md:57`, `docs/resident-web/README.md:6-8`) cũng không có. `deploy/README.md` và `README.md:56` nói thẳng: "chưa có job tạo schema".
* Hệ quả: **không thể kiểm chứng từ mã và script đã commit** CHECK/enum/khóa ngoại/trigger/RLS của bảng V3 (bản nháp lược đồ ở Phụ lục D cho phép đối chiếu, với mọi dè dặt đã nêu ở D.1). Thêm một dòng dữ liệu nền mà mã đòi nhưng không script nào tạo: `runtime_backends` mã `reception-langgraph` đang bật — thiếu thì mỗi lượt Reception bị 503 "Reception runtime backend is not registered" (`reception_delegation.py:24,111-114`); bản nháp có dòng này ở `schema/migrations/0005_reference_data.sql`. Quy tắc mã giả định có các ràng buộc (ví dụ "DB từ chối xóa tài khoản có lịch sử", `password_auth.py:336-338,356-357`; "khóa duy nhất `(tenant,user,channel,dedupe_key)`", `v3_resident.py:408`), nhưng gói không chứng minh. Lúc đọc, sáu tệp kiểm thử DB bị bỏ qua cấp module (`tests/test_direct_uploads.py:4`, `tests/test_object_storage.py:7`, `tests/test_reception_follow_up.py:4`, `tests/test_request_presentation.py:4`, `tests/test_staff_dispatch.py:4`, `tests/test_v3_admin.py:4`) và ba tệp khác cần DB/biến môi trường mới chạy (`tests/test_password_database.py:16`, `tests/test_resident_contract.py:64`, `tests/test_resident_integration.py:17`).
* Cột mã dùng mà không nơi nào định nghĩa/đặt giá trị: `work_orders.required` (đọc ở `v3_mutations.py:237,242`; không mã nào ghi), `tickets.incident_type_id` (đọc ở `v3_reports.py:70`; không mã nào ghi), `staff_profiles.max_concurrent_jobs` (đọc ở `v3_operations.py:151`; không có giá trị trong seed).

### 6.2 Agent Reception: chỗ phụ thuộc vào thứ backend không có

* **`GET /internal/reception/v1/model-config` không tồn tại ở backend.** Cả hai chế độ gọi nó trước mỗi lượt, trừ khi một mô hình được tiêm sẵn (chỉ test làm vậy) (`reception/src/runtime/service.py:261-266`). `BackendClient.call` coi 404 là `OperationRejected` (`reception/src/runtime/backend.py:21,100-106`), nên lượt rơi vào nhánh `except Exception` và cư dân nhận `FAILED_REPLY` ("Xin lỗi, tôi chưa xử lý được tin nhắn này…", `reception/src/runtime/service.py:40,274-277,290-295`). Tìm toàn bộ gói: không route nào có chuỗi `model-config`. (Cần xác nhận lại nếu route này sống ở nơi ngoài gói.)
* `RECEPTION_KNOWLEDGE_URL`/`/internal/knowledge/search`: không có dịch vụ tri thức trong gói; để trống thì Reception không trả lời câu hỏi thông tin từ nguồn nào (`deploy/README.md`; `reception/src/agent/tools.py:113-128`). Nội dung hướng dẫn an toàn khẩn cấp để trống (`README.md:65`, `v3_reception_runtime.py:90`). `process_self_help` luôn trả 501 (`v3_reception_operations.py:1262-1266`).
* `reception/README.md` mô tả các thứ **không còn trong mã**: `runtime/curator.py` và `POST /v1/curations` (`v3_learning.decide`), `runtime/inquiry.py` và `POST /internal/reception/chats/{id}/inquiries` (chuyển câu hỏi về BQL, `inquiry.to_management`). Hai tệp `curator.py`, `inquiry.py` đã bị xóa khỏi `reception/src/runtime/`; backend không có các route đó. Hệ quả: câu hỏi ngoài tri thức không được chuyển cho BQL bằng đường nào; nút `human_review` của graph chỉ chờ (3.4).
* Hủy yêu cầu từ cư dân không có tác dụng lên ticket (3.4, bước 7).
* Chế độ `graph` đòi `agent_teams`, `team_members`, `agent_versions`… do platform cũ tạo; bản đóng gói `provision_connected.py` chỉ tạo agent `system-reception`, không có Supervisor, nên `resolve_management_destination` trả `available:false`, `team` luôn `None` (`v3_reception_operations.py:615-616,1008-1012`) và `register_supervisor_wait` trả `registered:false` (`:643-651`).

### 6.3 Dữ liệu nền không có API hoặc màn hình tạo/sửa

| Cần cho quy trình | Hiện có | Bằng chứng |
|---|---|---|
| Gắn cư dân vào căn hộ (`unit_residents`, `verification_status='verified'`) — điều kiện để báo sự cố (3.2) | chỉ seed/script | không câu `insert/update unit_residents` nào trong `src` (grep); `scripts/provision_connected.py:178-180`, `scripts/seed_v3_faker.sql:70-74`; UI chỉ **hiển thị** `apartment_scope` (`staff/connected/admin/Accounts.tsx:95,709`); trang trạng thái cư dân hứa "Ban quản lý xác nhận thông tin cư dân và căn hộ" (`resident/features/auth/ResidentAccountStatus.tsx:50-52`) |
| Số điện thoại cư dân (`users.phone_e164`) — Reception không bàn giao nếu thiếu (`v3_reception_operations.py:919-930`); Case cần khi tạo ticket (`resident_api.py:297-300`) | chỉ seed/script | `/auth/register` không nhận số điện thoại (`password_auth.py:117-120`); không route cập nhật |
| Nhân viên, chuyên môn, ca, tải tối đa, trạng thái sẵn sàng | chỉ seed/script | 3.7 |
| Chấm dứt/sửa phạm vi phủ, đổi tên/đóng đơn vị quản lý | không | `scripts/grant_v3_api_role.sql:30` chỉ `INSERT`; không route |
| Tạo/sửa tòa nhà, phân khu, căn hộ, nhóm dịch vụ, loại sự cố | không | chỉ script (`provision_connected.py`) |
| Camera, liên hệ khẩn cấp, tài sản, cảm biến (ghi cảm biến có, tài sản/camera không) | camera/liên hệ/tài sản chỉ seed | `v3_security.py:52-84`, `v3_technical.py:84-102` chỉ có `GET` |
| Chính sách triage, `storage_locations` | chỉ script | `scripts/provision_connected.py:130-143`, `scripts/configure_local_storage.py:37-43` |
| Hết hạn / hoàn tất `valid_to` của vai trò | `grant_access` đóng vai trò cũ, không có thao tác thu hồi riêng | `password_auth.py:215` |
Hệ quả thực tế: tài khoản cư dân tự đăng ký xong, được quản trị duyệt (`PATCH /auth/accounts`), vẫn **không thể báo sự cố** (403 "Verified residence in this building required", `v3_resident.py:297-317`) cho tới khi có người chạy SQL/script gắn căn hộ.

### 6.4 Nhánh có mã nhưng không có nguồn tạo dữ liệu

* `work_offers.offer_queued_work` chỉ chạy với phương án `approved` do **agent** đề xuất không qua người (`work_offers.py:84-93`); gói không còn agent nào ghi `vh_ticket_plans.proposed_by_agent_id` (chỉ đọc ở `v3_plans.py:295`, `v3_request_presentation.py:138`). Nhánh này, cùng `offer_work`, chỉ có thể chạy nếu một hệ thống ngoài ghi loại phương án đó.
* Phương án của BQL/cư dân (3.14) không có màn hình BQL; cư dân chỉ quyết định phương án qua `vh_reception_supervisor_pending(pending_kind='plan_approval')`, bản ghi chỉ do `submit_supervisor_result` tạo (`v3_reception_supervisor.py:754-777`) mà không ai gọi trong gói. Các route `GET/POST /resident/plans*` không được resident-web gọi.
* Đề nghị việc hết hạn không được xử lý (3.8); review triage quá hạn không được xử lý (3.6); chuỗi cảnh báo an ninh không tự leo thang (3.17).
* Bảng `ticket_reviews` có route ghi nhưng không có màn hình; báo cáo `employee-performance` phụ thuộc vào nó (`v3_report_jobs.py:79-81`).

### 6.5 Trạng thái mâu thuẫn hoặc không đồng nhất trong mã

* **`vh_ticket_plans.status='revision_requested'`** được ghi ở `v3_reception_supervisor.py:567-582`, nhưng: `GET /plans` chỉ nhận `management_pending|resident_pending|approved|rejected` (`v3_plans.py:121-123`); `ResidentPlan.status` là `Literal` của đúng bốn giá trị đó (`resident_contract.py:172`) trong khi `GET /requests/{id}/plans` chọn cả plan có `resident_at is not null` (`resident_api.py:193`) — plan `revision_requested` có `resident_at` nên sẽ bị chọn và vi phạm `response_model` (lỗi 500 dự kiến; chưa chạy thử). Không route nào xử lý tiếp plan này (cả `management-decision` đòi `management_pending`, `v3_plans.py:167`).
* Hai đường quản trị tài khoản có từ điển trạng thái khác nhau (bảng ở 3.1): `/auth/accounts/{id}` cho chuyển `ended → active`/`pending → suspended` bất kỳ; `/admin/accounts/{id}/decision` thì không.
* Hạn đề nghị việc: 24 giờ (`work_offers.py:14`, `v3_request_presentation.py:187`), 30 phút (`staff/connected/ConnectedOperations.tsx:633-635`), 1 giờ (`v3_security.py:659`) cho cùng một khái niệm.
* `work_orders.status='rejected'` được liệt kê trong mọi tập loại trừ và trong `Literal` (`v3_mutations.py:354-355`) nhưng không có mã nào đặt; đề nghị bị từ chối đưa phiếu về `queued`, không về `rejected` (`:705-709`).
* Giá trị khởi tạo không được mã đặt (phụ thuộc DB ngoài gói): `tickets.triage_status`, `vh_resident_cases.status`, `security_alerts.status` (`open`), `staff_profiles.max_concurrent_jobs`, `work_orders.required`.
* Về "trạng thái mã dùng mà ràng buộc không cho phép": **không thể kết luận** vì không có ràng buộc V3 trong gói; bảng duy nhất có CHECK nằm trong gói và đang được dùng là `vh_command_receipt`, và mã dùng đúng hai giá trị `IN_PROGRESS|COMPLETED` (`v3_reception_operations.py:185,205-215`, `migrations/versions/0013_vh_command_receipt.py:37-47`).

### 6.13 Quyền và truy cập không đồng nhất

* `_responsible_management` **không có ngoại lệ cho quản trị viên** (`v3_water.py:66-83`): quản trị viên không có vai trò `management` sẽ bị 403 khi duyệt khóa nước (`v3_operations.py:340-361`), duyệt quyền thao tác kỹ thuật, quyết định/đề xuất phương án, tạo cảnh báo khẩn cấp, lập hóa đơn. Ngược lại `management_access` và các route khác cho quản trị viên qua (`v3_mutations.py:67-69`).
* `site_access` (an ninh) chỉ chấp nhận scope `tenant|site` (`v3_specialized.py:63`) trong khi `building_access` chấp nhận thêm `zone|building` (`v3_security.py:41-42`): BQL phạm vi tòa xem được camera nhưng không xem được điểm tuần tra.
* `staff`/`customer` tạo qua `/auth/accounts` nhận scope `tenant` (`password_auth.py:230-235`), khác dữ liệu mẫu dùng scope `site`/`building`.
* `ticket_events` do cư dân ghi dùng `actor_kind='human'` (`v3_mutations.py:95-98`) kể cả khi hành động do Reception thay mặt (chỉ `agent_event` ghi `agent`).

### 6.6 Tài liệu / giao diện hứa nhưng backend không làm

| Nguồn | Điều hứa | Thực tế |
|---|---|---|
| `services/vinhomes-api/README.md:18-20,126-129` | phòng ban quản lý, tra cứu tri thức, duyệt bộ nhớ, `scoped knowledge search`, `admin memory review` | `main.py` không gắn route `/rooms`, `/knowledge/search`, `/admin/memory-candidates`; trang demo vẫn gọi chúng (`demo_ui/business.js`) ⇒ các trang đó lỗi |
| `docs/backend/HUONG_DAN_DEMO_DATABASE_V3.md:72`, `docs/backend/HUONG_DAN_DEMO_MOCK.md:80-86` | `/rooms/…/messages`, mention agent, `/memory-candidates`, `/knowledge/search` | không có route |
| `docs/backend/HUONG_DAN_DEMO_DATABASE_V3.md:79` | camera/liên hệ, chuỗi cảnh báo/ACK, phê duyệt điều động/hủy "chưa có router V3"; "`work_approvals.kind` chưa có loại điều động/hủy" | đã cài đặt: `v3_security.py:52-84,180-412,415-735` |
| `docs/backend/HUONG_DAN_DEMO_MOCK.md:76` | "API chặn hoàn tất ticket khẩn cấp khi chưa có ACK" | không có kiểm tra nào như vậy trong `change_work_order_status` hay `change_ticket_status` (`v3_mutations.py:215-265,448-562`) |
| `docs/backend/HUONG_DAN_DEMO_DATABASE_V3.md:67`, `docs/backend/HUONG_DAN_DEMO_MOCK.md:52` | cư dân từ chối ⇒ "ticket/work order về `in_progress`" | ticket có phương án → `in_progress` (phiếu giữ `completed`); ticket không phương án → `triaging` + `reopen_count+1` (`v3_resident.py:538-561`) |
| `services/vinhomes-api/README.md:101-107` (Khóa nước), `:109-114` (QC, vệ sinh, nhà thầu, ngân sách), `:116-122` (An ninh) | thao tác qua giao diện | chỉ tồn tại ở trang demo `/demo/ui`; staff-web nối thật hiển thị "Chức năng chưa được nối đầy đủ" (`staff/connected/ConnectedOperations.tsx:354-361`) |
| `services/vinhomes-api/README.md:45` | "seven vh_* extension tables" | mã dùng 29 bảng `vh_*` (Phụ lục B) |
| `apps/resident-web/README.md:13,33,41` | "Router Vinhomes vẫn là scaffold", "auth backend chưa kết nối", "Chưa kết nối AI/backend/BQL" | đã nối: `resident/services/use-connected-resident.ts`, `resident/features/auth/auth-service.ts` |
| `apps/staff-web/README.md:41` | màn hình "agent" | không còn |
| `resident/features/utilities/Utilities.tsx` (Tòa nhà) | "Danh bạ và giờ làm việc chính thức sẽ hiển thị khi hệ thống được kết nối"; tiện ích "Ban quản lý chưa công bố danh mục" | không có dữ liệu/route cho cư dân; `security_emergency_contacts` chỉ phục vụ BQL (`v3_security.py:68-84`) |
| `staff/connected/field/model.ts:1-4`, `staff/lib/field-flow.ts:3` | tài liệu `docs/vinhomes-operations-staff-field-flow.md` | không có trong gói |
| `staff/connected/admin/Overview.tsx:54` | liên kết "quá hạn" `/operations/kanban?overdue=true` | route `kanban` chỉ nhận `ticket|job|task|view` (`staffsrc/routes/_authed/operations/kanban.tsx:4-11`), tham số bị bỏ qua |
| `staff/connected/admin/Units.tsx:25-27,120-121` | cột số agent / kết nối của nhóm | `GET /admin/units` chỉ trả `id,name,members` cho mỗi nhóm (`v3_admin.py:123-125`) |
| `deploy/compose.yml:29` | `VINHOMES_API_REPAIR_CATEGORY_CODES` | không mã nào đọc |
| `deploy/README.md` | các container tự chạy được | thiếu PostgreSQL, S3, dịch vụ tri thức và job dọn dẹp; thiếu schema (6.1) |

### 6.7 Thanh toán

* Không có hoàn tiền / ghi giảm / hủy hóa đơn / trạng thái `paid`: tìm toàn gói không thấy "refund" hay "hoàn tiền". Thanh toán chỉ là bản ghi tổng hợp, chỉ bật khi `demo_mode` (`v3_billing.py:274-279`). Không có tích hợp cổng thanh toán; `payments.provider='demo'`.
* Cư dân không xem được hóa đơn của mình (`invoice_access` đòi BQL, `v3_billing.py:42-67`); không có màn hình hóa đơn ở cả hai app. Số hóa đơn là `DEMO-…` (`:168`).
* `invoices.discount_total` luôn 0 dù từng dòng có chiết khấu (`:163`).
* Doanh thu sửa chữa theo phân bổ tỷ lệ cho hóa đơn nhiều nhóm; không tách công/vật tư (`v3_report_jobs.py:174-177`).
* Không có bước nào lập hóa đơn tự động khi phiếu hoàn tất (tài liệu ghi rõ "chưa tự phát hành hóa đơn cho mọi việc mới": `docs/backend/HUONG_DAN_DEMO_DATABASE_V3.md:71`; bản RAM cũ phát hành 150.000 VND khi hoàn tất: `docs/backend/HUONG_DAN_DEMO_MOCK.md:55`).

### 6.8 SLA, báo cáo

* Không có chính sách SLA (3.23): `response_due_at`/`resolution_due_at` không bao giờ được ghi, nên "ticket quá hạn" trong tổng quan quản trị (`v3_admin.py:223`), "đúng hạn" trong báo cáo nhân viên (`v3_report_jobs.py:83-84`) và cột hạn trên UI (`staff/connected/ConnectedOperations.tsx:492`) luôn rỗng/0 nếu DB không tự đặt.
* Báo cáo tần suất theo loại sự cố nhưng không ghi `incident_type_id` (3.19).
* DOCX là văn bản thô, bản xuất lưu `vh_report_exports` chỉ có hai loại (`incident_frequency`, `issued_revenue`) (`v3_report_jobs.py:280`); các báo cáo còn lại không xuất được.

### 6.9 Tệp và lưu giữ

* Không có quét mã độc; `scan_status='clean'` ghi cứng (3.21). Không có nhật ký truy cập tệp.
* Ảnh trò chuyện của cư dân chưa gắn ticket có `retention_until` (đường B-api) nhưng **không tác vụ nào trong gói xóa** chúng (`file_cleanup.py:40-47` chỉ phòng `management`; `scripts/cleanup_resident_photos.py:30-40` chỉ ảnh Case). Ảnh qua tải trực tiếp S3 hoặc `image-uploads` còn không có `retention_until` (`direct_uploads.py:78-81`, `v3_conversation_images.py:118-130`).
* Hai tác vụ dọn dẹp không được lên lịch trong compose (`deploy/compose.yml`, `deploy/README.md`); `file_cleanup.py:15` yêu cầu chạy hằng ngày từ scheduler của máy chủ.
* Quyền xem tệp của nhân viên: một tệp chỉ gắn với tin nhắn chưa thuộc ticket nào bị trả 404 cho người khác ngoài chủ (`v3_conversation_images.py:408-437`).

### 6.10 Thông báo

* Không có bộ gửi; `notification_deliveries` kẹt ở `pending` (`sent_at` không bao giờ đặt) và **không giao diện nào đọc** (3.22). Cư dân không nhận được: tiếp nhận của BQL, kết quả đạt nghiệm thu, khóa/mở nước, duyệt phương án — ngoài việc tự thấy thay đổi trạng thái khi mở app.
* BQL không có thông báo nào khác ngoài chuông tự dựng từ danh sách phiếu (`staff/connected/ConnectedOperations.tsx:325-328`); cảnh báo khẩn cấp, ghi vào `notification_deliveries` cho BQL, không hiện.

### 6.11 Quy trình không có đường đi trọn vẹn trong giao diện nối thật

| Quy trình | Backend | Giao diện nối thật |
|---|---|---|
| Cư dân hủy yêu cầu | chỉ tin nhắn `cancel_requested` | không (agent chỉ ghi nhận lời) |
| BQL hủy/đóng ticket thủ công | `PATCH /tickets/{id}/status` (chỉ ticket có phương án để đóng) | không có nút |
| Triage, đánh giá | có | không |
| Phương án BQL → cư dân | có | không |
| Khóa nước, quyền kỹ thuật, ngân sách | có | không |
| Vệ sinh / nhà thầu | có (JSON tự do) | không |
| An ninh (cảnh báo, điểm, sự cố, bàn giao, điều động) | có | không |
| Hóa đơn / thanh toán | có (thanh toán chỉ demo) | không |
| Đánh giá nhân viên | có | không |
| Hồ sơ Case (v0.1) | có | không |
| Báo cáo ngoài 2 loại | có | không |
| Thông báo cho cư dân từ `notification_deliveries` | có (ghi) | không (không đọc) |
| Đổi mật khẩu của cư dân | có `/auth/change-password` (`password_auth.py:385`) | resident-web không gọi route này (không có chuỗi `change-password` trong `apps/resident-web/src`); chỉ nhân viên có màn hình (`staff/layout/change-password.tsx:19`) |

### 6.12 Cấu hình vận hành

* Với `VINHOMES_API_PASSWORD_AUTH=1` (đóng gói), `VINHOMES_API_AUTH_URL` bị cấm đồng thời (`v3_config.py:53-55`) nên đường xác thực của nền tảng cũ không dùng được.
* `CORS` của hợp đồng cư dân chỉ cho `GET, POST, OPTIONS` (`main.py:86-88`); các app đều đi qua proxy cùng origin nên không ảnh hưởng, nhưng `PATCH/PUT/DELETE` của nhân viên không thể gọi chéo origin.
* Middleware chặn ghi từ trình duyệt khác origin (`main.py:90-101`) dùng `VINHOMES_API_ALLOWED_ORIGINS`; compose dùng chung một danh sách cho cả hai cấu hình (`deploy/compose.yml:41-42`).

---

## 7. Phụ lục

### Phụ lục A — Chỉ mục endpoint của backend đang gắn route

Nhóm theo module; "cổng" nêu loại kiểm tra truy cập (2.2). Ngoài bảng dưới còn `GET /health` và `GET /ready` (`main.py:103-140`), trang demo `GET /demo/ui` và tài nguyên `/demo/assets/*` (chỉ khi `VINHOMES_API_DEMO_MODE=1`, `main.py:177-183`), tài liệu `/docs`, `/openapi.json` của FastAPI. Các route `/internal/reception/*` dành cho dịch vụ Reception, không dành cho người dùng cuối.

**`password_auth.py`** — cổng: cookie phiên; `/auth/accounts*`, `/auth/management-units` đòi quản trị viên

| Phương thức | Đường dẫn | Dòng |
|---|---|---|
| GET | `/auth/config` | `password_auth.py:128` |
| POST | `/auth/login` | `password_auth.py:133` |
| GET | `/auth/session` | `password_auth.py:165` |
| POST | `/auth/logout` | `password_auth.py:176` |
| GET | `/auth/accounts` | `password_auth.py:239` |
| POST | `/auth/accounts` | `password_auth.py:265` |
| GET | `/auth/management-units` | `password_auth.py:286` |
| PATCH | `/auth/accounts/{user_id}` | `password_auth.py:297` |
| POST | `/auth/accounts/{user_id}/password` | `password_auth.py:311` |
| DELETE | `/auth/accounts/{user_id}` | `password_auth.py:334` |
| POST | `/auth/register` | `password_auth.py:363` |
| POST | `/auth/change-password` | `password_auth.py:385` |

**`v3_accounts.py`** — cổng: quản trị viên

| Phương thức | Đường dẫn | Dòng |
|---|---|---|
| GET | `/admin/accounts` | `v3_accounts.py:64` |
| POST | `/admin/accounts` | `v3_accounts.py:96` |
| POST | `/admin/accounts/memberships` | `v3_accounts.py:153` |
| POST | `/admin/accounts/{user_id}/decision` | `v3_accounts.py:192` |
| GET | `/admin/accounts/{user_id}/history` | `v3_accounts.py:234` |
| GET | `/admin/accounts/{user_id}/roles` | `v3_accounts.py:252` |
| POST | `/admin/accounts/{user_id}/roles` | `v3_accounts.py:267` |

**`v3_admin.py`** — cổng: quản trị viên

| Phương thức | Đường dẫn | Dòng |
|---|---|---|
| GET | `/admin/unit-options` | `v3_admin.py:52` |
| POST | `/admin/units` | `v3_admin.py:61` |
| GET | `/admin/units` | `v3_admin.py:111` |
| GET | `/admin/audit-events` | `v3_admin.py:133` |
| GET | `/admin/audit-events/export` | `v3_admin.py:179` |
| GET | `/admin/overview` | `v3_admin.py:216` |

**`v3_routes.py`** — cổng: scoped (BQL/nhân viên/quản trị)

| Phương thức | Đường dẫn | Dòng |
|---|---|---|
| GET | `/management-units/resolve` | `v3_routes.py:27` |
| GET | `/tickets` | `v3_routes.py:100` |
| GET | `/tickets/{ticket_id}` | `v3_routes.py:131` |
| GET | `/tickets/{ticket_id}/triage` | `v3_routes.py:159` |
| GET | `/work-orders` | `v3_routes.py:186` |
| GET | `/dispatch-queue` | `v3_routes.py:209` |
| GET | `/work-orders/{work_order_id}` | `v3_routes.py:214` |

**`v3_operations.py`** — cổng: scoped

| Phương thức | Đường dẫn | Dòng |
|---|---|---|
| GET | `/operations/me` | `v3_operations.py:38` |
| GET | `/operations-profile` | `v3_operations.py:56` |
| GET | `/catalogs` | `v3_operations.py:69` |
| GET | `/dashboard` | `v3_operations.py:86` |
| GET | `/my-work-orders` | `v3_operations.py:107` |
| GET | `/staff/available` | `v3_operations.py:128` |
| GET | `/tasks` | `v3_operations.py:172` |
| GET | `/approvals` | `v3_operations.py:195` |
| GET | `/tickets/{ticket_id}/evidence` | `v3_operations.py:221` |
| GET | `/tickets/{ticket_id}/timeline` | `v3_operations.py:236` |
| POST | `/tickets/{ticket_id}/routing/ack` | `v3_operations.py:249` |
| POST | `/approvals/{approval_id}/decision` | `v3_operations.py:313` |

**`v3_mutations.py`** — cổng: scoped

| Phương thức | Đường dẫn | Dòng |
|---|---|---|
| POST | `/tickets` | `v3_mutations.py:140` |
| PATCH | `/tickets/{ticket_id}/status` | `v3_mutations.py:215` |
| POST | `/tickets/{ticket_id}/assessments` | `v3_mutations.py:278` |
| POST | `/tickets/{ticket_id}/work-orders` | `v3_mutations.py:319` |
| POST | `/work-orders/{work_order_id}/repair-proposal` | `v3_mutations.py:374` |
| POST | `/work-orders/{work_order_id}/repair-proposal/onsite-decision` | `v3_mutations.py:405` |
| PATCH | `/work-orders/{work_order_id}/status` | `v3_mutations.py:448` |
| POST | `/work-orders/{work_order_id}/assignments` | `v3_mutations.py:571` |
| POST | `/assignments/{assignment_id}/response` | `v3_mutations.py:667` |
| POST | `/tickets/{ticket_id}/evidence` | `v3_mutations.py:726` |

**`v3_triage.py`** — cổng: scoped

| Phương thức | Đường dẫn | Dòng |
|---|---|---|
| POST | `/tickets/{ticket_id}/triage-decisions` | `v3_triage.py:51` |
| GET | `/triage-reviews` | `v3_triage.py:147` |
| POST | `/triage-reviews/{review_id}/decision` | `v3_triage.py:173` |

**`v3_specialized.py`** — cổng: scoped

| Phương thức | Đường dẫn | Dòng |
|---|---|---|
| GET | `/work-orders/{work_order_id}/qc` | `v3_specialized.py:77` |
| POST | `/work-orders/{work_order_id}/qc` | `v3_specialized.py:86` |
| POST | `/work-orders/{work_order_id}/redo` | `v3_specialized.py:137` |
| GET | `/work-orders/{work_order_id}/cleaning-plan` | `v3_specialized.py:196` |
| PUT | `/work-orders/{work_order_id}/cleaning-plan` | `v3_specialized.py:208` |
| GET | `/work-orders/{work_order_id}/contractor` | `v3_specialized.py:247` |
| PUT | `/work-orders/{work_order_id}/contractor` | `v3_specialized.py:259` |
| GET | `/budget-approvals` | `v3_specialized.py:297` |
| POST | `/work-orders/{work_order_id}/budget-approvals` | `v3_specialized.py:311` |
| POST | `/budget-approvals/{approval_id}/decision` | `v3_specialized.py:352` |
| GET | `/security/checkpoints` | `v3_specialized.py:386` |
| POST | `/security/checkpoints` | `v3_specialized.py:396` |
| PATCH | `/security/checkpoints/{checkpoint_id}` | `v3_specialized.py:416` |
| GET | `/security/incidents` | `v3_specialized.py:454` |
| POST | `/security/incidents` | `v3_specialized.py:464` |
| PATCH | `/security/incidents/{incident_id}` | `v3_specialized.py:497` |
| GET | `/security/handovers` | `v3_specialized.py:529` |
| POST | `/security/handovers` | `v3_specialized.py:539` |
| POST | `/security/handovers/{handover_id}/confirm` | `v3_specialized.py:559` |

**`v3_water.py`** — cổng: scoped

| Phương thức | Đường dẫn | Dòng |
|---|---|---|
| POST | `/work-orders/{work_order_id}/water-shutdown-request` | `v3_water.py:86` |
| GET | `/work-orders/{work_order_id}/water-interruptions` | `v3_water.py:160` |
| POST | `/water-interruptions/{interruption_id}/notify` | `v3_water.py:217` |
| POST | `/water-interruptions/{interruption_id}/start` | `v3_water.py:235` |
| POST | `/water-interruptions/{interruption_id}/restore` | `v3_water.py:252` |

**`v3_technical.py`** — cổng: scoped

| Phương thức | Đường dẫn | Dòng |
|---|---|---|
| GET | `/assets` | `v3_technical.py:84` |
| GET | `/assets/{asset_id}` | `v3_technical.py:98` |
| GET | `/assets/{asset_id}/sensor-readings` | `v3_technical.py:105` |
| POST | `/assets/{asset_id}/sensor-readings` | `v3_technical.py:139` |
| GET | `/assets/{asset_id}/maintenance-history` | `v3_technical.py:160` |
| POST | `/work-orders/{work_order_id}/measurements` | `v3_technical.py:188` |
| GET | `/work-orders/{work_order_id}/measurements` | `v3_technical.py:215` |
| GET | `/technical/active-outages` | `v3_technical.py:233` |
| POST | `/work-orders/{work_order_id}/permission-requests` | `v3_technical.py:259` |
| GET | `/work-orders/{work_order_id}/permission-requests` | `v3_technical.py:324` |
| POST | `/permission-requests/{request_id}/decision` | `v3_technical.py:349` |
| GET | `/work-orders/{work_order_id}/resolution-check` | `v3_technical.py:408` |
| POST | `/work-orders/{work_order_id}/executor-results` | `v3_technical.py:447` |
| POST | `/assets/{asset_id}/maintenance-history` | `v3_technical.py:504` |

**`v3_plans.py`** — cổng: scoped; `/resident/*` là cư dân

| Phương thức | Đường dẫn | Dòng |
|---|---|---|
| POST | `/tickets/{ticket_id}/plans` | `v3_plans.py:44` |
| GET | `/tickets/{ticket_id}/plans` | `v3_plans.py:106` |
| GET | `/plans` | `v3_plans.py:118` |
| POST | `/plans/{plan_id}/management-decision` | `v3_plans.py:151` |
| GET | `/resident/plans` | `v3_plans.py:198` |
| POST | `/resident/plans/{plan_id}/decision` | `v3_plans.py:209` |
| GET | `/resident/tickets/{ticket_id}/progress` | `v3_plans.py:303` |

**`v3_request_presentation.py`** — cổng: scoped

| Phương thức | Đường dẫn | Dòng |
|---|---|---|
| GET | `/tickets/{ticket_id}/conversation` | `v3_request_presentation.py:24` |
| GET | `/tickets/{ticket_id}/presentation` | `v3_request_presentation.py:35` |
| PATCH | `/plans/{plan_id}/presentation` | `v3_request_presentation.py:105` |

**`v3_resident.py`** — cổng: cư dân

| Phương thức | Đường dẫn | Dòng |
|---|---|---|
| POST | `/resident/chats` | `v3_resident.py:98` |
| GET | `/resident/chats` | `v3_resident.py:115` |
| GET | `/resident/chats/{channel_id}/messages` | `v3_resident.py:141` |
| POST | `/resident/chats/{channel_id}/messages` | `v3_resident.py:156` |
| POST | `/resident/chats/{channel_id}/tickets` | `v3_resident.py:223` |
| GET | `/resident/tickets` | `v3_resident.py:435` |
| GET | `/resident/tickets/{ticket_id}` | `v3_resident.py:449` |
| POST | `/resident/approvals/{approval_id}/decision` | `v3_resident.py:478` |
| GET | `/resident/approvals` | `v3_resident.py:578` |
| GET | `/my/notifications` | `v3_resident.py:596` |
| POST | `/my/notifications/{notification_id}/read` | `v3_resident.py:611` |

**`v3_resident_support.py`** — cổng: cư dân

| Phương thức | Đường dẫn | Dòng |
|---|---|---|
| GET | `/resident/me` | `v3_resident_support.py:26` |
| POST | `/resident/chats/{channel_id}/read` | `v3_resident_support.py:51` |
| POST | `/resident/chats/{channel_id}/photos` | `v3_resident_support.py:62` |
| GET | `/resident/photos/{file_id}` | `v3_resident_support.py:127` |

**`v3_resident_interactions.py`** — cổng: cư dân

| Phương thức | Đường dẫn | Dòng |
|---|---|---|
| GET | `/resident/supervisor-interactions` | `v3_resident_interactions.py:19` |
| POST | `/resident/tickets/{ticket_id}/supervisor-response` | `v3_resident_interactions.py:38` |

**`resident_api.py`** — cổng: cư dân (`/api/domains/vinhomes/resident`) hoặc scoped (`…/operations/…`)

| Phương thức | Đường dẫn | Dòng |
|---|---|---|
| GET | `/tickets/{ticket_id}/resident-intake-photos` | `resident_api.py:87` |
| GET | `/tickets/{ticket_id}/resident-intake-photos/{file_id}/content` | `resident_api.py:97` |
| GET | `/api/domains/vinhomes/resident/me` | `resident_api.py:114` |
| POST | `/api/domains/vinhomes/resident/photos` | `resident_api.py:125` |
| GET | `/api/domains/vinhomes/resident/photos/{file_id}/content` | `resident_api.py:134` |
| GET | `/api/domains/vinhomes/resident/requests` | `resident_api.py:139` |
| POST | `/api/domains/vinhomes/resident/requests` | `resident_api.py:163` |
| GET | `/api/domains/vinhomes/resident/requests/{request_id}` | `resident_api.py:170` |
| POST | `/api/domains/vinhomes/resident/requests/{request_id}/confirm` | `resident_api.py:175` |
| GET | `/api/domains/vinhomes/resident/requests/{request_id}/plans` | `resident_api.py:186` |
| POST | `/api/domains/vinhomes/resident/requests/{request_id}/plans/{plan_id}/decision` | `resident_api.py:198` |
| POST | `/api/domains/vinhomes/resident/requests/{request_id}/reopen` | `resident_api.py:223` |
| GET | `/api/domains/vinhomes/operations/resident-cases/photos/{file_id}/content` | `resident_api.py:228` |
| GET | `/api/domains/vinhomes/operations/resident-cases` | `resident_api.py:249` |
| GET | `/api/domains/vinhomes/operations/resident-cases/{case_id}` | `resident_api.py:263` |
| POST | `/api/domains/vinhomes/operations/resident-cases/{case_id}/tickets` | `resident_api.py:286` |
| POST | `/api/domains/vinhomes/operations/resident-cases/{case_id}/ticket-links` | `resident_api.py:314` |
| POST | `/api/domains/vinhomes/operations/resident-cases/{case_id}/resolution` | `resident_api.py:329` |

**`v3_reception.py`** — cổng: cư dân (agent gọi qua ủy quyền)

| Phương thức | Đường dẫn | Dòng |
|---|---|---|
| GET | `/resident/context` | `v3_reception.py:21` |
| POST | `/resident/chats/{channel_id}/ticket-drafts` | `v3_reception.py:90` |
| GET | `/resident/chats/{channel_id}/ticket-drafts` | `v3_reception.py:150` |
| POST | `/resident/chats/{channel_id}/ticket-drafts/{draft_id}/incidents/{index}/commit` | `v3_reception.py:168` |
| POST | `/resident/assignments/{assignment_id}/review` | `v3_reception.py:237` |

**`v3_reception_operations.py`** — cổng: cư dân/ủy quyền Reception

| Phương thức | Đường dẫn | Dòng |
|---|---|---|
| POST | `/internal/reception/operations/execute` | `v3_reception_operations.py:1270` |
| POST | `/internal/reception/operations/reconcile` | `v3_reception_operations.py:1302` |

**`v3_reception_runtime.py`** — cổng: token ủy quyền Reception

| Phương thức | Đường dẫn | Dòng |
|---|---|---|
| GET | `/internal/reception/catalog` | `v3_reception_runtime.py:75` |
| POST | `/internal/reception/policy/evaluate` | `v3_reception_runtime.py:81` |
| GET | `/internal/reception/chats/{channel_id}/context` | `v3_reception_runtime.py:157` |
| POST | `/internal/reception/chats/{channel_id}/intake` | `v3_reception_runtime.py:203` |
| POST | `/internal/reception/chats/{channel_id}/follow-up` | `v3_reception_runtime.py:220` |
| POST | `/internal/reception/chats/{channel_id}/replies` | `v3_reception_runtime.py:267` |

**`reception_runtime_api.py`** — cổng: token ủy quyền Reception

| Phương thức | Đường dẫn | Dòng |
|---|---|---|
| POST | `/internal/reception/v1/execute` | `reception_runtime_api.py:38` |
| POST | `/internal/reception/v1/reconcile` | `reception_runtime_api.py:46` |

### Phụ lục B — Bảng dữ liệu mà mã nghiệp vụ tham chiếu

Danh sách rút từ các câu SQL trong `src/vinhomes_api/*.py` (mệnh đề `from/join/into/update`). Cột "Alembic tạo (lúc đọc)": 16 bảng `vh_*` cũ mà `migrations/versions/0002…0015` tạo trước khi bị gỡ. Cột "Có trong bản nháp `schema/`": theo `schema/migrations/0002_tables.sql` lúc 23:47 (Phụ lục D). Dòng "— (chỉ script/seed)" nghĩa là chỉ script hoặc dữ liệu mẫu đụng tới bảng. Bảng chỉ có trong bản nháp (không do mã nghiệp vụ gọi): `dispatch_attempts, dispatch_queue, event_inbox, event_outbox, payment_webhook_receipts, sla_policies, ticket_escalations, ticket_sla_adjustments, ticket_sla_cycles, triage_rules`.

| Bảng | Module `src/vinhomes_api` đọc/ghi (câu SQL from/join/into/update) | Alembic tạo (lúc đọc) | Có trong bản nháp `schema/` |
|---|---|---|---|
| `access_scopes` | password_auth, resident_cases, v3_accounts, v3_admin, v3_auth, v3_billing, v3_demo, v3_mutations, v3_operations, v3_reception_operations, v3_report_jobs, v3_reports, v3_resident, v3_routes, v3_security, v3_specialized, v3_triage, v3_water | không | có |
| `account_reviews` | v3_accounts | không | có |
| `accounts` | password_auth | không | có |
| `agent_releases` | v3_reception_operations | không | có |
| `agent_runs` | reception_delegation | không | có |
| `agent_teams` | v3_reception_operations, v3_reception_supervisor | không | có |
| `agent_versions` | reception_delegation, v3_reception_operations | không | có |
| `agents` | reception_delegation, v3_demo, v3_reception_operations | không | có |
| `audit_events` | password_auth, v3_admin, v3_audit | không | có |
| `buildings` | password_auth, resident_cases, v3_admin, v3_demo, v3_mutations, v3_operations, v3_reception, v3_reception_operations, v3_reception_supervisor, v3_report_jobs, v3_reports, v3_resident, v3_resident_support, v3_routes, v3_security, v3_ticket_result, v3_triage | không | có |
| `channel_agents` | v3_demo, v3_reception_operations | không | có |
| `channel_memberships` | password_auth, v3_admin, v3_demo, v3_resident, v3_resident_interactions, v3_resident_support | không | có |
| `channels` | file_cleanup, password_auth, reception_delegation, v3_admin, v3_mutations, v3_reception, v3_reception_operations, v3_reception_runtime, v3_reception_supervisor, v3_resident, v3_resident_interactions, v3_resident_support | không | có |
| `domains` | resident_cases, v3_demo, v3_mutations, v3_operations, v3_reception, v3_reception_operations, v3_reception_supervisor, v3_resident, v3_resident_support, v3_routes, v3_ticket_result | không | có |
| `evidence_items` | resident_api, v3_mutations, v3_operations, v3_reception_supervisor, v3_technical | không | có |
| `execution_principals` | direct_uploads, reception_delegation, resident_photos, v3_conversation_images, v3_files, v3_reception_operations, v3_resident_support | không | có |
| `file_objects` | direct_uploads, file_cleanup, resident_api, resident_photos, storage_setup, v3_conversation_images, v3_files, v3_resident_support | không | có |
| `file_uploads` | direct_uploads, file_cleanup | không | có |
| `files` | direct_uploads, file_cleanup, resident_api, resident_cases, resident_photos, v3_conversation_images, v3_files, v3_mutations, v3_operations, v3_reception_supervisor, v3_request_presentation, v3_resident, v3_resident_support, v3_ticket_result | không | có |
| `incident_types` | v3_operations, v3_report_jobs, v3_reports | không | có |
| `interruption_scopes` | v3_water | không | có |
| `invoice_lines` | v3_billing, v3_report_jobs, v3_reports | không | có |
| `invoices` | v3_billing, v3_report_jobs, v3_reports | không | có |
| `management_coverage` | resident_cases, v3_admin, v3_reception_operations, v3_reception_supervisor, v3_report_jobs, v3_reports, v3_resident, v3_routes | không | có |
| `management_units` | password_auth, v3_admin, v3_demo, v3_operations, v3_reception_operations, v3_resident, v3_routes, v3_ticket_result | không | có |
| `memory_candidates` | — (chỉ script/seed) | không | không |
| `memory_namespaces` | — (chỉ script/seed) | không | không |
| `message_files` | file_cleanup | không | có |
| `messages` | reception_intake, v3_conversation_images, v3_reception, v3_reception_operations, v3_reception_runtime, v3_reception_supervisor, v3_request_presentation, v3_resident, v3_resident_interactions, v3_ticket_result | không | có |
| `notification_deliveries` | v3_completion, v3_operations, v3_reception_operations, v3_resident, v3_security, v3_ticket_result, v3_water | không | có |
| `payment_allocations` | v3_billing, v3_report_jobs | không | có |
| `payment_intents` | v3_billing | không | có |
| `payments` | v3_billing, v3_report_jobs | không | có |
| `platform_admins` | direct_uploads, password_auth, v3_accounts, v3_auth, v3_conversation_images, v3_reception_supervisor, v3_specialized | không | có |
| `runtime_backends` | reception_delegation | không | có |
| `runtime_identities` | reception_delegation | không | có |
| `runtime_session_bindings` | reception_delegation | không | có |
| `scoped_user_roles` | password_auth, resident_cases, v3_accounts, v3_auth, v3_billing, v3_demo, v3_mutations, v3_operations, v3_reception_operations, v3_reports, v3_resident, v3_routes, v3_security, v3_specialized, v3_triage, v3_water | không | có |
| `security_alert_deliveries` | v3_auth, v3_security | không | có |
| `security_alerts` | v3_auth, v3_security | không | có |
| `security_cameras` | v3_security | không | có |
| `security_emergency_contacts` | v3_security | không | có |
| `service_categories` | v3_admin, v3_billing, v3_demo, v3_mutations, v3_operations, v3_plans, v3_reception_operations, v3_reception_runtime, v3_report_jobs, v3_reports, v3_request_presentation, v3_resident, v3_resident_support, v3_security, v3_ticket_result | không | có |
| `service_interruptions` | v3_mutations, v3_operations, v3_technical, v3_water | không | có |
| `sessions` | password_auth | không | có |
| `sites` | resident_cases, v3_demo, v3_mutations, v3_operations, v3_reception, v3_reception_operations, v3_resident, v3_resident_support, v3_routes, v3_specialized | không | có |
| `staff_profiles` | v3_admin, v3_auth, v3_billing, v3_demo, v3_mutations, v3_operations, v3_report_jobs, v3_request_presentation, v3_security, v3_specialized, v3_technical, v3_water, work_offers | không | có |
| `staff_shifts` | v3_mutations, v3_operations, v3_request_presentation, work_offers | không | có |
| `staff_specialties` | v3_mutations, v3_operations, v3_request_presentation, v3_security, work_offers | không | có |
| `storage_locations` | direct_uploads, file_cleanup, resident_api, resident_photos, storage_setup, v3_conversation_images, v3_files, v3_resident_support | không | có |
| `team_members` | v3_reception_operations | không | có |
| `tenant_memberships` | password_auth, reception_delegation, resident_cases, v3_accounts, v3_admin, v3_auth, v3_billing, v3_demo, v3_mutations, v3_operations, v3_reception_operations, v3_reports, v3_resident, v3_routes, v3_security, v3_specialized, v3_triage, v3_water | không | có |
| `tenants` | — (chỉ script/seed) | không | có |
| `ticket_assessments` | v3_mutations, v3_routes, v3_triage | không | có |
| `ticket_events` | v3_billing, v3_mutations, v3_operations, v3_plans, v3_reception_operations, v3_resident, v3_routes, v3_ticket_result, work_offers | không | có |
| `ticket_files` | direct_uploads, v3_conversation_images, v3_files, v3_mutations, v3_reception_runtime, v3_reception_supervisor, v3_request_presentation, v3_resident, v3_ticket_result | không | có |
| `ticket_reviews` | v3_reception, v3_report_jobs | không | có |
| `ticket_routing_history` | v3_operations, v3_resident | không | có |
| `ticket_triage_decisions` | v3_routes, v3_triage | không | có |
| `ticket_triage_reviews` | v3_routes, v3_triage | không | có |
| `tickets` | reception_runtime_api, resident_api, resident_cases, v3_admin, v3_billing, v3_completion, v3_conversation_images, v3_mutations, v3_operations, v3_plans, v3_reception, v3_reception_operations, v3_reception_runtime, v3_reception_supervisor, v3_report_jobs, v3_reports, v3_request_presentation, v3_resident, v3_resident_interactions, v3_resident_support, v3_routes, v3_security, v3_specialized, v3_technical, v3_ticket_result, v3_triage, v3_water, work_offers | không | có |
| `triage_policy_bindings` | v3_triage | không | có |
| `triage_policy_versions` | v3_triage | không | có |
| `unit_residents` | password_auth, resident_cases, v3_demo, v3_reception, v3_reception_operations, v3_resident, v3_resident_support, v3_water | không | có |
| `units` | password_auth, resident_api, resident_cases, v3_demo, v3_reception, v3_reception_operations, v3_reception_supervisor, v3_resident, v3_resident_support, v3_routes, v3_ticket_result, v3_water | không | có |
| `users` | password_auth, reception_delegation, resident_api, v3_accounts, v3_admin, v3_auth, v3_billing, v3_demo, v3_operations, v3_reception, v3_reception_operations, v3_report_jobs, v3_request_presentation, v3_resident, v3_resident_support, v3_security, v3_specialized, v3_water, work_offers | không | có |
| `vh_assets` | v3_technical | không | có |
| `vh_budget_approvals` | v3_specialized | không | có |
| `vh_cleaning_plans` | v3_specialized | không | có |
| `vh_command_receipt` | v3_reception_operations | có | có |
| `vh_contractor_updates` | v3_specialized | không | có |
| `vh_conversation_uploads` | v3_conversation_images | không | có |
| `vh_maintenance_records` | v3_technical | không | có |
| `vh_operational_requests` | v3_mutations, v3_technical | không | có |
| `vh_qc_redo_orders` | v3_completion, v3_mutations, v3_report_jobs, v3_resident, v3_routes, v3_specialized | không | có |
| `vh_qc_results` | resident_api, v3_completion, v3_mutations, v3_resident, v3_routes, v3_specialized, v3_technical | không | có |
| `vh_reception_supervisor_messages` | v3_reception_runtime, v3_reception_supervisor, v3_resident_interactions | không | có |
| `vh_reception_supervisor_pending` | v3_reception_runtime, v3_reception_supervisor, v3_resident_interactions | không | có |
| `vh_report_exports` | v3_report_jobs | không | có |
| `vh_resident_case_tickets` | resident_api, resident_cases | không | có |
| `vh_resident_cases` | resident_api, resident_cases, resident_photos | không | có |
| `vh_resident_command_receipts` | resident_cases | không | có |
| `vh_resident_outbox` | resident_cases | không | có |
| `vh_resident_photos` | resident_api, resident_cases, resident_photos | không | có |
| `vh_resident_public_events` | resident_cases | không | có |
| `vh_resident_resolution_photos` | resident_api, resident_cases, resident_photos | không | có |
| `vh_resident_resolution_responses` | resident_api, resident_cases | không | có |
| `vh_resident_resolutions` | resident_api, resident_cases | không | có |
| `vh_resident_submissions` | resident_cases | không | có |
| `vh_security_checkpoints` | v3_specialized | không | có |
| `vh_security_handovers` | v3_specialized | không | có |
| `vh_security_incidents` | v3_specialized | không | có |
| `vh_sensor_readings` | v3_technical | không | có |
| `vh_technical_measurements` | v3_technical | không | có |
| `vh_ticket_plans` | resident_api, v3_billing, v3_mutations, v3_plans, v3_reception_supervisor, v3_request_presentation, v3_resident_interactions, v3_ticket_result, work_offers | không | có |
| `work_approvals` | v3_completion, v3_mutations, v3_operations, v3_reception, v3_resident, v3_routes, v3_security, v3_specialized, v3_technical, v3_water | không | có |
| `work_assignments` | v3_auth, v3_mutations, v3_operations, v3_reception, v3_report_jobs, v3_request_presentation, v3_routes, v3_security, v3_specialized, v3_technical, v3_water, work_offers | không | có |
| `work_orders` | resident_api, v3_auth, v3_billing, v3_completion, v3_mutations, v3_operations, v3_plans, v3_reception, v3_reception_supervisor, v3_report_jobs, v3_request_presentation, v3_resident, v3_routes, v3_security, v3_specialized, v3_technical, v3_ticket_result, v3_water, work_offers | không | có |
| `workspace_members` | password_auth, v3_admin | không | có |
| `workspaces` | password_auth, v3_admin, v3_reception_operations, v3_reception_supervisor | không | có |
| `zones` | v3_operations | không | có |

### Phụ lục C — Script, tác vụ vận hành và biến cấu hình (chỉ tên biến)

**C.1 Script và lệnh vận hành** (đều không có trong compose; chạy tay hoặc bằng scheduler của máy chủ).

| Lệnh | Việc làm | Nguồn |
|---|---|---|
| `scripts/setup_demo_database.ps1` | dựng PostgreSQL Docker cổng 5544, chạy `server/scripts/migrate.ts` (ngoài gói), nạp dữ liệu mẫu | `scripts/setup_demo_database.ps1:6-21` |
| `scripts/prepare_demo_database.py prepare|seed|upgrade`, `scripts/upgrade_demo_database.ps1` | sinh cấu hình cục bộ, nạp/ nâng cấp dữ liệu mẫu | `scripts/prepare_demo_database.py`, `scripts/upgrade_demo_database.ps1:1-16` |
| `scripts/start_demo.ps1`, `launch_demo.ps1`, `launchers/CHAY_DEMO_API.cmd` | chạy API ở chế độ demo (`VINHOMES_API_DEMO_MODE=1`) và mở `/demo/ui` | `services/vinhomes-api/README.md:52-67` |
| `scripts/setup_password_database.py` | tạo database `vinhomes_connected`, tenant `resident-local`, tài khoản quản trị đầu tiên, role runtime không `BYPASSRLS`, ghi thông tin đăng nhập vào tệp bị git bỏ qua | `scripts/setup_password_database.py:27-74` |
| `scripts/provision_connected.py` | nạp tổ chức Ocean Park 1 và ba tài khoản đầu (BQL, kỹ thuật, cư dân) | 3.7 |
| `scripts/add_cleaning_service.py` | thêm nhóm `cleaning` và nhân viên vệ sinh | 3.7 |
| `scripts/configure_local_storage.py` | tạo `storage_locations` kiểu `local_fs` cho database kết nối cục bộ | `scripts/configure_local_storage.py:27-50` |
| `scripts/grant_v3_api_role.sql` | cấp quyền DB cho role runtime (không `BYPASSRLS`) | `scripts/grant_v3_api_role.sql:1-76` |
| `python -m vinhomes_api.storage_setup [--allow-missing]` | tạo bucket, chép tệp từ đĩa lên bucket, chuyển `storage_locations` sang `s3` | `storage_setup.py:59-104` |
| `python -m vinhomes_api.file_cleanup` | dọn tệp phòng quản lý chưa dùng và đối tượng `staging/` quá hạn | `file_cleanup.py:33-89` |
| `scripts/cleanup_resident_photos.py [--apply] [--limit 1..1000]` | dọn ảnh Case chưa gắn đã hết hạn | `scripts/cleanup_resident_photos.py:19-57` |
| `python -m uvicorn src.runtime.service:create_app --factory --port 4202` (trong `agents/reception/`), `scripts/start_runtime.ps1` | chạy runtime Reception | `reception/README.md`, mục "Runtime service" |

**C.2 Biến cấu hình mà mã đọc** (tên, không giá trị).
* Backend: `VINHOMES_API_HOST`, `VINHOMES_API_PORT`, `VINHOMES_API_DATABASE_URL`, `VINHOMES_API_TENANT_ID`, `VINHOMES_API_TENANT_KEY`, `VINHOMES_API_AUTH_URL`, `VINHOMES_API_DEV_USER_ID`, `VINHOMES_API_DEMO_MODE`, `VINHOMES_API_PASSWORD_AUTH`, `VINHOMES_API_LOCAL_FILE_STORAGE`, `VINHOMES_API_RESIDENT_LOCAL_STORAGE`, `VINHOMES_API_VOLUME_FILE_STORAGE`, `VINHOMES_API_RESIDENT_ALLOWED_ORIGINS`, `VINHOMES_API_ALLOWED_ORIGINS`, `VINHOMES_API_RESIDENT_SIGNING_KEY`, `VINHOMES_API_RECEPTION_SERVICE_TOKEN`, `VINHOMES_API_RECEPTION_URL`, `RECEPTION_DELEGATION_KEY`, `VINHOMES_API_RESIDENT_MESSAGES_PER_MINUTE`, `VINHOMES_API_SECURE_COOKIES`, `VINHOMES_RESIDENT_FILE_ROOT` (`v3_config.py:37-107`, `main.py:95`, `password_auth.py:160`, `v3_files.py:22`).
* Lưu trữ đối tượng: `VINHOMES_API_S3_ENDPOINT`, `VINHOMES_API_S3_BUCKET`, `VINHOMES_API_S3_ACCESS_KEY`, `VINHOMES_API_S3_SECRET_KEY`, `VINHOMES_API_S3_REGION`, `VINHOMES_API_S3_PUBLIC_ENDPOINT`, `VINHOMES_API_S3_ADMIN_ACCESS_KEY`, `VINHOMES_API_S3_ADMIN_SECRET_KEY` (`storage.py:24-65`, `storage_setup.py:35-56`).
* Reception: `RECEPTION_SERVICE_TOKEN`, `RECEPTION_BACKEND_URL`, `RECEPTION_STATE_PATH`, `RECEPTION_KNOWLEDGE_URL`, `RECEPTION_AGENT` (`graph` hoặc `loop`), `RECEPTION_MODEL`, `RECEPTION_MODEL_PROVIDER`, `RECEPTION_MODEL_API_KEY`, `RECEPTION_MODEL_BASE_URL`, `OPENAI_API_KEY`, `OPENAI_BASE_URL` (`reception/src/runtime/service.py:67-86`, `agents/reception/.env.example`).
* Giao diện: `VITE_ALLOW_DEMO_BACKEND`, `VITE_ENABLE_UI_PREVIEW`, `VINHOMES_API_URL`, `VINHOMES_API_ORIGIN`, `VINHOMES_SURFACE`, `APP_PORT` (`staffsrc/routes/_authed.tsx:39,67-69`, `staff/auth/demo-access.ts:6`, `apps/staff-web/README.md`).
* Khai báo trong compose/env mẫu nhưng không mã nào đọc: `VINHOMES_API_REPAIR_CATEGORY_CODES` (4.1).

### Phụ lục D — Đối chiếu với bản nháp lược đồ database (đang được tạo song song)

**D.1 Đây là gì và vì sao tách riêng.** Trong lúc tôi viết tài liệu này, một tiến trình khác thêm vào gói một bộ SQL mới, lần đầu ở `services/vinhomes-api/db/migrations/`, sau đó chuyển sang `services/vinhomes-api/src/vinhomes_api/schema/migrations/` (ghi theo vị trí thấy lúc 23:47; tệp **chưa được commit** — `git status` báo untracked). Tiêu đề tệp: "Generated once from the running schema, then kept by hand" (`schema/migrations/0001_extensions_types.sql:1`, `schema/migrations/0002_tables.sql:1`). Gồm: `0001_extensions_types.sql` (extension `btree_gist`, kiểu `agent_type`), `0002_tables.sql` (109 câu `CREATE TABLE`, bảng nào cũng `FORCE ROW LEVEL SECURITY`), `0003_functions.sql` (15 hàm), `0004_constraints_indexes_triggers_policies.sql` (khóa, chỉ mục, 83 trigger, 103 chính sách RLS), cùng `schema/roles.sql` và thư mục `schema/seed/`. Kèm một bản đặc tả nháp `docs/domain/SPEC_DATABASE_DOMAIN.md` ("bản nháp chờ duyệt"; nó nói rõ lấy cột/kiểu từ một database đang chạy, thứ tôi không được phép mở). **Các mục 3–6 chỉ dựa vào mã nghiệp vụ, dữ liệu mẫu, tài liệu và giao diện**; phụ lục này chỉ dùng bản nháp để đối chiếu ràng buộc, không coi nó là nghiệp vụ đã triển khai.

Cùng lúc đó Alembic (`migrations/`, `alembic.ini`), các gói thế hệ cũ (`actions/`, `approvals/`, `commands/`, `db/`, `events/`, `evidence/`, `incidents/`, `outbox/`, `qc/`, `resolution/`, `rules/`, `tasks/`, `work_orders/`, `_vendor/`) và các seed `scripts/seed_v3_*.sql` bị xóa hoặc chuyển khỏi cây làm việc (trạng thái staged `D`/`R`). Mọi trích dẫn tới các tệp đó trong tài liệu là theo nội dung tôi đọc trước khi chúng bị gỡ (với các tệp này cũng là nội dung ở `HEAD` của `dev_Vinhome`, vì chúng chưa từng bị sửa). Mã nghiệp vụ đang được gắn route (các module `v3_*.py`, `resident_*.py`, …), `agents/reception`, `apps/*` không thay đổi trong lúc tôi đọc (thời điểm sửa cuối đều trước 22:10).

**D.2 Đối chiếu giá trị trạng thái: ràng buộc CHECK của bản nháp so với giá trị mã ghi.** Số dòng dẫn là của `schema/migrations/0002_tables.sql` nếu không ghi khác.

| Cột | CHECK trong bản nháp | Mã ghi (mục) | Nhận xét |
|---|---|---|---|
| `tickets.status` | **không có CHECK** và không có trigger chuyển trạng thái (`:1577-1624`; 83 trigger ở `0004` chỉ gồm `touch`, `append_only`, kiểm chiếu triage, …) | `open…cancelled` (3.2) | máy trạng thái ticket chỉ nằm trong mã (`v3_mutations.py:120-126` và các nơi khác) |
| `tickets.priority` / `severity` / `request_kind` | `:1618-1620` | khớp (4.2) | `tickets_check_3`: `is_emergency ⇒ priority='critical'` (`:1621`) — mã khớp (`v3_reception_operations.py:742`, `v3_triage.py:55-56`) |
| `tickets.triage_status` | `pending, provisional, confirmed, review_required` (`:1623`) | `pending, review_required, confirmed` | `provisional` không bao giờ được đặt |
| `tickets.resolution_mode` | `guided, onsite` (`:1622`) | không | cột không có đường ghi |
| `work_orders.status` | 10 giá trị (`:2468`) | khớp (3.8) | — |
| `work_assignments.status` | `offered, accepted, rejected, released, completed, cancelled` (`:2441`) | không ghi `released` | `expired` chỉ suy ra khi đọc (`v3_operations.py:111`) |
| `work_approvals.kind` | 5 loại (`:2414`) | khớp | — |
| `work_approvals.status` | `pending, approved, rejected, expired, cancelled` (`:2415`) | không bao giờ ghi `expired` | hết hạn chỉ xét qua `expires_at` lúc quyết định |
| `work_approvals` người nhận | đúng một trong `requested_to_user_id`, `required_scope_id` (`:2413`) | khớp mọi `INSERT` (`v3_mutations.py:390`, `v3_water.py:127`, `v3_security.py:528`, `v3_completion.py:24`) | — |
| `service_interruptions` | `utility ∈ {water, power}`, 6 trạng thái (`:1085-1086`) | chỉ `water`, trạng thái khớp | điện đi qua `vh_operational_requests` (3.12) |
| `tenant_memberships.status` | 4 giá trị (`:1265`) | khớp (3.1) | — |
| `users.status` | `pending, active, suspended, deleted` (`:1777`) | chỉ `active` | mã xóa hẳn người dùng chưa có lịch sử (`password_auth.py:350-355`), không dùng `deleted` |
| `scoped_user_roles` | `role_code` 3 giá trị (`:963`) + loại trừ chồng lấn thời gian (`0004:789`) | khớp | `grant_access` đóng vai trò cũ trước khi mở vai trò mới (`password_auth.py:215`) |
| `management_coverage` | loại trừ chồng lấn theo (`scope_id`, nhóm dịch vụ, khoảng thời gian) (`0004:509`) | khớp | một scope + một nhóm không thể có hai đơn vị trùng thời gian |
| `evidence_items` | `purpose` 4 giá trị, `provenance ∈ {camera, upload, import}`, `status ∈ {active, withdrawn}` (`:440-442`) | `purpose` khớp; chỉ `upload`, `active` | chưa có thao tác "rút" bằng chứng |
| `staff_profiles.availability` | `available, busy, offline, on_leave` (`:1168`) | chỉ đọc `available` | không có đường ghi |
| `staff_shifts.status` | `scheduled, available, leave, cancelled` (`:1186`) | chỉ đọc `available` | — |
| `ticket_routing_history.status` | `requested, accepted, rejected, timeout` (`:1439`) | `requested → accepted` | `rejected`, `timeout` không có đường ghi |
| `ticket_triage_reviews.status` | `pending, claimed, approved, rejected, superseded, expired` (`:1568`) | `pending, approved, rejected` | không có bước nào ghi `claimed`, `superseded`, `expired` |
| `ticket_triage_decisions` | `outcome` 4 giá trị, `decision_mode` 4 giá trị, `outcome='applied' ⇔ applied_ticket_version` không rỗng (`:1533-1536`) | `review_required/applied`; `provisional/human_confirmed` | khớp |
| `vh_ticket_plans.status` | có **`revision_requested`** (`:2386`) | ghi ở `v3_reception_supervisor.py:567-582` | **DB cho phép; `Literal` của API không** (6.5) |
| `vh_budget_approvals.status` | thêm `cancelled` (`:1819`) | không ghi | — |
| `vh_report_exports` | `status ∈ {ready, failed}`; `failed ⇒ content` rỗng; `kind` 2 giá trị (`:2066-2068`) | chỉ `ready` | — |
| `vh_resident_cases.status` | `received, processing, confirmation, completed`; `confirmation|completed ⇒ current_resolution_id` không rỗng (`:2110,2113`) | `processing, confirmation, completed` | giá trị đầu `received` do DB đặt (không thấy trong mã) |
| `files.status`, `file_objects.status` | `files`: `staged, verifying, ready, rejected, deletion_pending, deleted, missing` (`:573`); `file_objects`: `verifying, ready, rejected, deletion_pending, deleted, missing` (`:508`) | `staged, ready, deleted, deletion_pending` | — |
| `file_objects.scan_status` | `pending, clean, infected, failed`; `status='ready' ⇒ scan_status='clean' ∧ verified_at` không rỗng (`:504,507`) | luôn ghi `clean` | giải thích vì sao mã ghi cứng `clean`; không có cách ghi `infected` |
| `file_uploads.status` | 8 giá trị (`:542`) | `issued, accepted, expired` | — |
| `notification_deliveries` | `channel ∈ {in_app, push, sms, email}`, `status ∈ {pending, sent, failed, dead}` (`:769-770`) | chỉ `in_app`, `pending` | DB đã thiết kế vòng đời gửi; **không có bộ gửi** (3.22) |
| `invoices.status` | `draft, issued, void, replaced`; `grand_total = subtotal + tax_total − discount_total` (`:664-666`) | `draft, issued`; `discount_total = 0` | `void`/`replaced` không có đường ghi |
| `payments`, `payment_intents` | `reconciliation_status ∈ {confirmed, review_required}`; intent 6 trạng thái (`:813,857`) | `confirmed`, `succeeded` | — |
| `channels` | `kind ∈ {reception, management, agent_builder, personal}`; `reception ⇒ workspace_id` rỗng (`:287-288`) | `reception`, `management` | khớp |
| `messages.visibility` | `room, internal, customer` (`:741`) | đọc `room`, `customer` | — |
| `security_*` | `alerts`: `open/acknowledged/exhausted` (`:1006`); `deliveries`: 5 trạng thái và `ack_timeout_seconds ∈ [5,3600]` (`:985`); contacts `active/disabled` (`:1044`); cameras `online/offline/maintenance` (`:1024`) | khớp | — |
| `vh_security_*`, `vh_operational_requests`, `vh_cleaning_plans`, `vh_contractor_updates`, `vh_qc_results`, `vh_conversation_uploads` | khớp 3.12, 3.15, 3.16, 3.17, 3.21 (`:1838,1882,1906-1908,1950-1951,1987-1988,2270,2291,2314-2315`) | khớp | `vh_qc_results_check`: `redo_required ⇒ outcome='fail'` (`:1987`) khớp `v3_specialized.py:89-90` |
| `unit_residents.verification_status` | `pending, verified, rejected, expired` (`:1730`) | chỉ đọc `verified` | không có API gắn cư dân vào căn hộ (6.3) |
| `vh_command_receipt.status` | `IN_PROGRESS, COMPLETED` (`:1861`) | khớp | — |

Kết luận cho "trạng thái mã dùng mà không ràng buộc nào cho phép": **không tìm thấy giá trị nào mã ghi mà CHECK của bản nháp từ chối**. Các khác biệt thật là: (a) mã không bao giờ dùng nhiều giá trị DB cho phép (cột "Nhận xét"); (b) lớp API chặn một giá trị DB cho phép (`revision_requested`); (c) hai quy tắc DB mà mã không biết hoặc vi phạm (D.5).

**D.3 Quy tắc DB giữ (trigger/ràng buộc), bổ sung cho mục 3.**

| Cơ chế | Nội dung | Nguồn |
|---|---|---|
| `assignment_capacity` | từ chối phân công `offered|accepted` khi số việc đang giữ ≥ `max_concurrent_jobs` ("Staff capacity exhausted"); `offered` cần `offer_expires_at` ở tương lai; `accepted` cần `accepted_at` và `eta_at` | `0003_functions.sql:20-39`, `0004:2464` |
| `evidence_scope` | bằng chứng: tệp phải `ready`, `scope_kind='ticket'`, đúng `ticket_id`; `before|after` cần phiếu và phân công | `0003:99-117`, `0004:2524` |
| `file_original_scope`, `object_version_scope` | tệp `ready` phải có đối tượng gốc đã xác minh; byte đã chấp nhận bất biến; khóa đối tượng phải nằm dưới `tenant_prefix` của `storage_locations` | `0003:119-151`, `0004:2542,2596` |
| Append-only | `ticket_events`, `ticket_assessments`, `ticket_triage_decisions`, `payment_allocations`, `agent_versions`, `ticket_sla_adjustments`, `vh_reception_supervisor_messages`, `vh_resident_command_receipts`, `vh_resident_resolutions`, `vh_resident_resolution_responses` | `0004:2440,2602,2728,2746,2764,2782,2848-2866` |
| `audit_events` | không sửa; chỉ xóa được bản ghi cũ hơn `openbot.audit_retention_days` khi tham số này được đặt | `0003:201-212`, `0004:2470` |
| Triage | quyết định `applied` phải khớp phiên bản/thế hệ ticket, không hạ ưu tiên hay bỏ cờ khẩn cấp khi chưa có người duyệt; chính sách đã công bố bất biến | `0003:41-90,178-199`, `0004:2458,2620,2626,2794,2812` |
| Chống chồng lấn | phủ quản lý, vai trò theo thời gian, chính sách SLA, gán chính sách triage | `0004:509,789,992,1363,1370` |
| Idempotency | duy nhất `(tenant, user, channel, dedupe_key)` cho thông báo; `(ticket, idempotency_key)` cho `ticket_events` và `ticket_assessments`; `(tenant, ticket, idempotency_key)` cho `security_alerts`; `(tenant, idempotency_key)` cho `payment_intents`, `payment_allocations` | `0004:614,635,656,824,1146,1195` |
| RLS | 103 chính sách, **chỉ theo `app.tenant_id`**; `app.user_id` không xuất hiện trong chính sách nào ⇒ quyền theo người dùng (ai thấy ticket nào) nằm hoàn toàn trong mã (`TICKET_VISIBILITY`) | `0004` (các câu `CREATE POLICY`) |

**D.4 Thiết kế có trong bản nháp nhưng mã đang chạy không dùng.**
* *SLA*: `sla_policies` (theo đơn vị × nhóm dịch vụ × ưu tiên × loại yêu cầu; `response_minutes`, `resolution_minutes`; `clock_basis` chỉ `elapsed_24x7`) (`0002:1129-1148`), `ticket_sla_cycles` (`:1473-1497`), `ticket_sla_adjustments` (`:1448-1464`), `ticket_escalations` với lý do `emergency, response_breach, resolution_breach, review_overdue, risk_signal_pending, queue_wait, no_capacity, policy_missing` (`:1328-1352`); cột `tickets.sla_policy_id`, `first_response_at`, `active_sla_cycle_id` (`:1577-1624`). Không câu SQL nào trong mã gọi các bảng/cột này (3.23).
* *Điều phối*: `dispatch_queue` (trạng thái `waiting, claimed, dispatched, cancelled, dead`; hạng ưu tiên 10/20/30/40, khẩn cấp luôn 40) và `dispatch_attempts` (`0002:297-351`).
* *Triage theo luật*: `triage_rules` (`0002:1690-1707`); mã chỉ tạo quyết định do người đề xuất (`"source":"human_proposal"`, `v3_triage.py:116`).
* *Sự kiện, webhook thanh toán*: `event_inbox`, `event_outbox`, `payment_webhook_receipts` (`0002:377,400,822`).

**D.5 Mâu thuẫn mã ↔ ràng buộc DB (bản nháp).**
1. **Bằng chứng từ ảnh trò chuyện.** `POST /tickets/{id}/evidence` chấp nhận tệp `ready` chỉ gắn với ticket qua `ticket_files` (tệp phạm vi `channel`) (`v3_mutations.py:735-740`), nhưng trigger `evidence_scope` đòi `files.scope_kind='ticket'` và `files.ticket_id` đúng ticket (`0003:99-117`). Tệp phạm vi `channel` (ảnh cư dân gửi trong trò chuyện) sẽ bị DB từ chối bằng `RAISE EXCEPTION` thường (không phải lỗi ràng buộc); `scoped_connection` chỉ đổi `IntegrityError` thành 409, còn lỗi khác thành 503 (`v3_auth.py:97-100`). Giao diện nhân viên không gặp lỗi này vì chỉ gắn ảnh tải bằng `/tickets/{id}/files|direct-uploads` (phạm vi `ticket`).
2. **`revision_requested`**: DB cho phép, API chặn (6.5).
3. **Mã dùng ít hơn DB cho phép** (D.2): nhiều trạng thái cuối vòng đời không có đường ghi (`expired`, `released`, `timeout`, `rejected` của định tuyến, `void`, `sent/failed/dead`, `infected`, …). Các quy trình tương ứng (hết hạn phê duyệt, hết hạn review triage, gửi thông báo, quét tệp, hủy hóa đơn) chỉ tồn tại ở tầng lược đồ.
4. **Phủ quản lý đồng hạng**: ràng buộc loại trừ (`0004:509`) ngăn hai phủ trùng thời gian trên cùng `scope_id` + nhóm dịch vụ; lỗi 409 "Ambiguous management coverage" (`v3_resident.py:341-344`, `v3_routes.py:88-90`) vì vậy chỉ xảy ra khi có hai dòng `access_scopes` khác nhau cùng cấp và cùng đích — **chưa xác minh** có xảy ra thực tế hay không.
