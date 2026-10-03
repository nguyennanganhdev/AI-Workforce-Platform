# Danh mục toàn bộ 193 bảng PostgreSQL

Cấu trúc thực tế từ catalog `vinhomes_v3`, kiểm ngày 04/10/2026; số dòng là thời điểm kiểm, có thể thay đổi. Không chứa dữ liệu cá nhân từ các dòng bảng. Ngữ nghĩa bảng/cột đối chiếu merged.json; các extension SQL không nằm trong design model được ghi rõ.

| Nhóm | Số bảng |
|---|---:|
| 01 Tài khoản, tenant và authority | 15 |
| 02 Địa bàn, nhân sự và danh mục | 16 |
| 03 Agent và Factory | 10 |
| 04 Runtime, run và context | 6 |
| 05 Chat, phòng agent và Reception | 18 |
| 06 RAG và memory | 19 |
| 07 File và storage | 11 |
| 08 Ticket, triage, SLA và dispatch | 17 |
| 09 Thực thi, phân công và nghiệm thu | 6 |
| 10 Chi phí và thanh toán | 9 |
| 11 Operations mở rộng | 11 |
| 12 Resident UI, intake và kết quả | 11 |
| 13 An ninh | 7 |
| 14 Technical agent API | 12 |
| 15 Báo cáo | 3 |
| 16 Tools, MCP, skills và computer | 14 |
| 17 Automation, events và audit | 8 |
| **Tổng** | **193** |

## 01 Tài khoản, tenant và authority

### tenants

Khách hàng tổ chức của platform

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **1**. RLS/FORCE: **False/False**. FK ra/vào: **0/166**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `code` | `text` | True | — | `—` | Mã định danh nghiệp vụ |
| `name` | `text` | True | — | `—` | Tên hiển thị |
| `status` | `text` | True | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `timezone` | `text` | True | — | `'Asia/Ho_Chi_Minh'::text` | Múi giờ IANA |
| `retention_policy` | `jsonb` | True | — | `'{}'::jsonb` | Chính sách lưu và xóa dữ liệu của tenant |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |

Ràng buộc:

- `tenants_check_0`: `CHECK (status = ANY (ARRAY['active'::text, 'suspended'::text, 'closed'::text]))`.
- `tenants_pkey`: `PRIMARY KEY (id)`.
- `tenants_unique_0`: `UNIQUE (code)`.

Chỉ mục:

- `CREATE UNIQUE INDEX tenants_pkey ON public.tenants USING btree (id)`.
- `CREATE UNIQUE INDEX tenants_unique_0 ON public.tenants USING btree (code)`.

### tenant_memberships

Người dùng thuộc tenant

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **26**. RLS/FORCE: **True/True**. FK ra/vào: **2/1**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `user_id` | `text` | True | FK | `—` | Tài khoản liên quan |
| `status` | `text` | True | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `joined_at` | `timestamp with time zone` | False | — | `—` | Thời điểm gia nhập |
| `ended_at` | `timestamp with time zone` | False | — | `—` | Thời điểm chấm dứt |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |

Ràng buộc:

- `tenant_memberships_check_0`: `CHECK (status = ANY (ARRAY['pending'::text, 'active'::text, 'suspended'::text, 'ended'::text]))`.
- `tenant_memberships_pkey`: `PRIMARY KEY (id)`.
- `tenant_memberships_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `tenant_memberships_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `tenant_memberships_unique_0`: `UNIQUE (tenant_id, user_id)`.
- `tenant_memberships_user_id_fk`: `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT`.

Chỉ mục:

- `CREATE UNIQUE INDEX tenant_memberships_pkey ON public.tenant_memberships USING btree (id)`.
- `CREATE UNIQUE INDEX tenant_memberships_tenant_key_uq ON public.tenant_memberships USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX tenant_memberships_unique_0 ON public.tenant_memberships USING btree (tenant_id, user_id)`.
- `CREATE INDEX tenant_memberships_user_id_idx ON public.tenant_memberships USING btree (tenant_id, user_id)`.

### platform_admins

Danh sách admin hệ thống

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **1**. RLS/FORCE: **False/False**. FK ra/vào: **2/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `user_id` | `text` | True | PK/FK | `—` | Tài khoản liên quan |
| `granted_by` | `text` | False | FK | `—` | Người cấp quyền |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |

Ràng buộc:

- `platform_admins_granted_by_fk`: `FOREIGN KEY (granted_by) REFERENCES users(id) ON DELETE RESTRICT`.
- `platform_admins_pkey`: `PRIMARY KEY (user_id)`.
- `platform_admins_user_id_fk`: `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT`.

Chỉ mục:

- `CREATE UNIQUE INDEX platform_admins_pkey ON public.platform_admins USING btree (user_id)`.

### users

Tài khoản người dùng chung của platform

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **26**. RLS/FORCE: **False/False**. FK ra/vào: **0/110**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `text` | True | PK | `—` | Định danh bản ghi |
| `email` | `text` | False | — | `—` | Địa chỉ email |
| `name` | `text` | False | — | `—` | Tên hiển thị |
| `image` | `text` | False | — | `—` | Ảnh đại diện |
| `email_verified` | `boolean` | True | — | `false` | Email đã được xác minh |
| `groups` | `text[]` | True | — | `'{}'::text[]` | Nhóm danh tính legacy; không dùng làm ACL mặc định |
| `onboarding_step` | `integer` | True | — | `0` | Bước onboarding hiện tại |
| `onboarding_completed_at` | `timestamp with time zone` | False | — | `—` | Thời điểm hoàn tất onboarding |
| `last_signed_in_at` | `timestamp with time zone` | False | — | `—` | Lần đăng nhập gần nhất |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |
| `phone_e164` | `text` | False | — | `—` | Số điện thoại đã chuẩn hóa E.164 |
| `phone_verified_at` | `timestamp with time zone` | False | — | `—` | Thời điểm xác minh số điện thoại |
| `status` | `text` | True | — | `'pending'::text` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `disabled_at` | `timestamp with time zone` | False | — | `—` | Thời điểm vô hiệu hóa |
| `deleted_at` | `timestamp with time zone` | False | — | `—` | Thời điểm xóa mềm |

Ràng buộc:

- `users_check_0`: `CHECK (status = ANY (ARRAY['pending'::text, 'active'::text, 'suspended'::text, 'deleted'::text]))`.
- `users_check_1`: `CHECK (status = 'deleted'::text OR email IS NOT NULL OR phone_e164 IS NOT NULL)`.
- `users_pkey`: `PRIMARY KEY (id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX users_partial_0 ON public.users USING btree (lower(email)) WHERE (email IS NOT NULL)`.
- `CREATE UNIQUE INDEX users_partial_1 ON public.users USING btree (phone_e164) WHERE (phone_e164 IS NOT NULL)`.
- `CREATE UNIQUE INDEX users_pkey ON public.users USING btree (id)`.

### user_roles

Role OpenBot cũ trong giai đoạn chuyển đổi

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **False/False**. FK ra/vào: **1/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `user_id` | `text` | True | PK/FK | `—` | Tài khoản liên quan |
| `role` | `role` | True | PK | `—` | Role legacy của OpenBot |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |

Ràng buộc:

- `user_roles_user_id_fk`: `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT`.
- `user_roles_user_id_role_pk`: `PRIMARY KEY (user_id, role)`.

Chỉ mục:

- `CREATE UNIQUE INDEX user_roles_user_id_role_pk ON public.user_roles USING btree (user_id, role)`.

### scoped_user_roles

Gán role theo phạm vi

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **27**. RLS/FORCE: **True/True**. FK ra/vào: **4/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `membership_id` | `uuid` | True | FK | `—` | Tham chiếu người dùng thuộc tenant |
| `scope_id` | `uuid` | True | FK | `—` | Tham chiếu phạm vi quyền có kiểu rõ ràng |
| `role_code` | `text` | True | — | `—` | Mã vai trò nghiệp vụ trong scope |
| `granted_by` | `text` | True | FK | `—` | Người cấp quyền |
| `valid_from` | `timestamp with time zone` | True | — | `—` | Bắt đầu hiệu lực |
| `valid_to` | `timestamp with time zone` | False | — | `—` | Kết thúc hiệu lực; NULL là chưa kết thúc |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |

Ràng buộc:

- `scoped_role_period_excl`: `EXCLUDE USING gist (membership_id WITH =, scope_id WITH =, role_code WITH =, tstzrange(valid_from, valid_to, '[)'::text) WITH &&)`.
- `scoped_user_roles_check_0`: `CHECK (role_code = ANY (ARRAY['management'::text, 'staff'::text, 'customer'::text]))`.
- `scoped_user_roles_check_1`: `CHECK (valid_to IS NULL OR valid_to > valid_from)`.
- `scoped_user_roles_granted_by_fk`: `FOREIGN KEY (granted_by) REFERENCES users(id) ON DELETE RESTRICT`.
- `scoped_user_roles_membership_id_fk`: `FOREIGN KEY (tenant_id, membership_id) REFERENCES tenant_memberships(tenant_id, id) ON DELETE RESTRICT`.
- `scoped_user_roles_pkey`: `PRIMARY KEY (id)`.
- `scoped_user_roles_scope_id_fk`: `FOREIGN KEY (tenant_id, scope_id) REFERENCES access_scopes(tenant_id, id) ON DELETE RESTRICT`.
- `scoped_user_roles_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `scoped_user_roles_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `scoped_user_roles_unique_0`: `UNIQUE (membership_id, scope_id, role_code, valid_from)`.

Chỉ mục:

- `CREATE INDEX scoped_role_period_excl ON public.scoped_user_roles USING gist (membership_id, scope_id, role_code, tstzrange(valid_from, valid_to, '[)'::text))`.
- `CREATE UNIQUE INDEX scoped_user_roles_pkey ON public.scoped_user_roles USING btree (id)`.
- `CREATE UNIQUE INDEX scoped_user_roles_tenant_key_uq ON public.scoped_user_roles USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX scoped_user_roles_unique_0 ON public.scoped_user_roles USING btree (membership_id, scope_id, role_code, valid_from)`.

### accounts

Liên kết phương thức đăng nhập và mật khẩu đã hash

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **False/False**. FK ra/vào: **1/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `text` | True | PK | `—` | Định danh bản ghi |
| `account_id` | `text` | True | — | `—` | Định danh tài khoản tại nhà cung cấp |
| `provider_id` | `text` | True | — | `—` | Định danh nhà cung cấp xác thực |
| `issuer` | `text` | False | — | `—` | Issuer xác thực |
| `user_id` | `text` | True | FK | `—` | Tài khoản liên quan |
| `access_token` | `text` | False | — | `—` | Access token; dữ liệu nhạy cảm |
| `refresh_token` | `text` | False | — | `—` | Refresh token; dữ liệu nhạy cảm |
| `id_token` | `text` | False | — | `—` | ID token; dữ liệu nhạy cảm |
| `access_token_expires_at` | `timestamp with time zone` | False | — | `—` | Thời điểm access token expires |
| `refresh_token_expires_at` | `timestamp with time zone` | False | — | `—` | Thời điểm refresh token expires |
| `scope` | `text` | False | — | `—` | Phạm vi OAuth hoặc quyền được cấp |
| `password` | `text` | False | — | `—` | Mật khẩu đã hash do Better Auth quản lý |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |

Ràng buộc:

- `accounts_pkey`: `PRIMARY KEY (id)`.
- `accounts_unique_0`: `UNIQUE (provider_id, account_id)`.
- `accounts_user_id_fk`: `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE`.

Chỉ mục:

- `CREATE UNIQUE INDEX accounts_pkey ON public.accounts USING btree (id)`.
- `CREATE UNIQUE INDEX accounts_unique_0 ON public.accounts USING btree (provider_id, account_id)`.
- `CREATE INDEX accounts_user_id_idx ON public.accounts USING btree (user_id)`.

### sessions

Phiên đăng nhập Better Auth, không phải session agent

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **False/False**. FK ra/vào: **1/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `text` | True | PK | `—` | Định danh bản ghi |
| `user_id` | `text` | True | FK | `—` | Tài khoản liên quan |
| `token` | `text` | True | — | `—` | Token phiên xác thực; chỉ auth service được truy cập |
| `expires_at` | `timestamp with time zone` | True | — | `—` | Thời điểm hết hạn |
| `ip_address` | `text` | False | — | `—` | IP đăng nhập |
| `user_agent` | `text` | False | — | `—` | Thông tin trình duyệt |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |

Ràng buộc:

- `sessions_pkey`: `PRIMARY KEY (id)`.
- `sessions_unique_0`: `UNIQUE (token)`.
- `sessions_user_id_fk`: `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE`.

Chỉ mục:

- `CREATE UNIQUE INDEX sessions_pkey ON public.sessions USING btree (id)`.
- `CREATE UNIQUE INDEX sessions_unique_0 ON public.sessions USING btree (token)`.
- `CREATE INDEX sessions_user_id_idx ON public.sessions USING btree (user_id)`.

### verifications

Mã xác minh do auth quản lý

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **False/False**. FK ra/vào: **0/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `text` | True | PK | `—` | Định danh bản ghi |
| `identifier` | `text` | True | — | `—` | Định danh đối tượng cần xác minh |
| `value` | `text` | True | — | `—` | Giá trị xác minh hoặc dữ liệu runtime |
| `expires_at` | `timestamp with time zone` | True | — | `—` | Thời điểm hết hạn |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |

Ràng buộc:

- `verifications_pkey`: `PRIMARY KEY (id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX verifications_pkey ON public.verifications USING btree (id)`.

### account_reviews

Duyệt đăng ký và thay đổi tài khoản

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **1**. RLS/FORCE: **True/True**. FK ra/vào: **3/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `user_id` | `text` | True | FK | `—` | Tài khoản liên quan |
| `action` | `text` | True | — | `—` | Hành động quản trị |
| `from_status` | `text` | False | — | `—` | Trạng thái trước |
| `to_status` | `text` | True | — | `—` | Trạng thái sau |
| `reason` | `text` | False | — | `—` | Lý do |
| `reviewer_user_id` | `text` | False | FK | `—` | Tham chiếu tài khoản người dùng chung của platform |
| `decided_at` | `timestamp with time zone` | False | — | `—` | Thời điểm ra quyết định |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |

Ràng buộc:

- `account_reviews_check_0`: `CHECK (action = ANY (ARRAY['register'::text, 'approve'::text, 'reject'::text, 'activate'::text, 'suspend'::text, 'delete'::text]))`.
- `account_reviews_pkey`: `PRIMARY KEY (id)`.
- `account_reviews_reviewer_user_id_fk`: `FOREIGN KEY (reviewer_user_id) REFERENCES users(id) ON DELETE RESTRICT`.
- `account_reviews_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `account_reviews_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `account_reviews_user_id_fk`: `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT`.

Chỉ mục:

- `CREATE UNIQUE INDEX account_reviews_pkey ON public.account_reviews USING btree (id)`.
- `CREATE UNIQUE INDEX account_reviews_tenant_key_uq ON public.account_reviews USING btree (tenant_id, id)`.
- `CREATE INDEX account_reviews_user_id_idx ON public.account_reviews USING btree (tenant_id, user_id)`.

### sso_providers

Nhà cung cấp SSO

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **False/False**. FK ra/vào: **1/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `text` | True | PK | `—` | Định danh bản ghi |
| `issuer` | `text` | True | — | `—` | Issuer xác thực |
| `oidc_config` | `text` | False | — | `—` | Cấu hình OIDC có thể chứa secret |
| `saml_config` | `text` | False | — | `—` | Cấu hình SAML |
| `user_id` | `text` | False | FK | `—` | Tài khoản liên quan |
| `provider_id` | `text` | True | — | `—` | Định danh nhà cung cấp xác thực |
| `organization_id` | `text` | False | — | `—` | Định danh tổ chức của auth provider |
| `domain` | `text` | True | — | `—` | Tên miền phục vụ định tuyến SSO |

Ràng buộc:

- `sso_providers_pkey`: `PRIMARY KEY (id)`.
- `sso_providers_user_id_fk`: `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT`.

Chỉ mục:

- `CREATE UNIQUE INDEX sso_providers_pkey ON public.sso_providers USING btree (id)`.
- `CREATE INDEX sso_providers_user_id_idx ON public.sso_providers USING btree (user_id)`.

### credentials

Kho bí mật mã hóa

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **2/3**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `kind` | `credential_kind` | True | — | `—` | Loại bản ghi |
| `provider` | `text` | True | — | `—` | Nhà cung cấp dịch vụ |
| `encrypted_value` | `text` | True | — | `—` | Secret đã mã hóa |
| `key_id` | `text` | True | — | `—` | Định danh khóa trong vault |
| `metadata` | `jsonb` | True | — | `—` | Metadata có cấu trúc |
| `revoked_at` | `timestamp with time zone` | False | — | `—` | Thời điểm thu hồi |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |
| `tenant_id` | `uuid` | False | FK | `—` | Tenant sở hữu dữ liệu |
| `workspace_id` | `uuid` | False | FK | `—` | Workspace của ban quản lý |
| `scope_kind` | `text` | True | — | `'platform'::text` | Phạm vi sở hữu credential |

Ràng buộc:

- `credentials_check_0`: `CHECK (scope_kind = 'platform'::text AND tenant_id IS NULL AND workspace_id IS NULL OR scope_kind = 'tenant'::text AND tenant_id IS NOT NULL AND workspace_id IS NULL OR scope_kind = 'workspace'::text AND tenant_id IS NOT NULL AND workspace_id IS NOT NULL)`.
- `credentials_check_1`: `CHECK (scope_kind = ANY (ARRAY['platform'::text, 'tenant'::text, 'workspace'::text]))`.
- `credentials_pkey`: `PRIMARY KEY (id)`.
- `credentials_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `credentials_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `credentials_workspace_id_fk`: `FOREIGN KEY (tenant_id, workspace_id) REFERENCES workspaces(tenant_id, id) ON DELETE RESTRICT`.

Chỉ mục:

- `CREATE UNIQUE INDEX credentials_partial_0 ON public.credentials USING btree (kind, provider, key_id) WHERE ((scope_kind = 'platform'::text) AND (revoked_at IS NULL))`.
- `CREATE UNIQUE INDEX credentials_partial_1 ON public.credentials USING btree (tenant_id, kind, provider, key_id) WHERE ((scope_kind = 'tenant'::text) AND (revoked_at IS NULL))`.
- `CREATE UNIQUE INDEX credentials_partial_2 ON public.credentials USING btree (tenant_id, workspace_id, kind, provider, key_id) WHERE ((scope_kind = 'workspace'::text) AND (revoked_at IS NULL))`.
- `CREATE UNIQUE INDEX credentials_pkey ON public.credentials USING btree (id)`.
- `CREATE UNIQUE INDEX credentials_tenant_key_uq ON public.credentials USING btree (tenant_id, id)`.
- `CREATE INDEX credentials_workspace_id_idx ON public.credentials USING btree (tenant_id, workspace_id)`.

### execution_principals

Danh tính thực thi thuộc tenant

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **2**. RLS/FORCE: **True/True**. FK ra/vào: **3/7**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `kind` | `text` | True | — | `—` | Loại bản ghi |
| `user_id` | `text` | False | FK | `—` | Tài khoản liên quan |
| `workspace_id` | `uuid` | False | FK | `—` | Workspace của ban quản lý |
| `status` | `text` | True | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `authz_version` | `bigint` | True | — | `1` | Bộ đếm thay đổi quyền dùng để vô hiệu cache/capability |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |

Ràng buộc:

- `execution_principals_check_0`: `CHECK (kind = 'user'::text AND user_id IS NOT NULL AND workspace_id IS NULL OR kind = 'workspace_service'::text AND user_id IS NULL AND workspace_id IS NOT NULL)`.
- `execution_principals_check_1`: `CHECK (kind = ANY (ARRAY['user'::text, 'workspace_service'::text]))`.
- `execution_principals_check_2`: `CHECK (status = ANY (ARRAY['active'::text, 'suspended'::text, 'revoked'::text]))`.
- `execution_principals_pkey`: `PRIMARY KEY (id)`.
- `execution_principals_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `execution_principals_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `execution_principals_user_id_fk`: `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT`.
- `execution_principals_workspace_id_fk`: `FOREIGN KEY (tenant_id, workspace_id) REFERENCES workspaces(tenant_id, id) ON DELETE RESTRICT`.

Chỉ mục:

- `CREATE UNIQUE INDEX execution_principals_partial_0 ON public.execution_principals USING btree (tenant_id, user_id) WHERE (kind = 'user'::text)`.
- `CREATE UNIQUE INDEX execution_principals_partial_1 ON public.execution_principals USING btree (tenant_id, workspace_id) WHERE (kind = 'workspace_service'::text)`.
- `CREATE UNIQUE INDEX execution_principals_pkey ON public.execution_principals USING btree (id)`.
- `CREATE UNIQUE INDEX execution_principals_tenant_key_uq ON public.execution_principals USING btree (tenant_id, id)`.
- `CREATE INDEX execution_principals_user_id_idx ON public.execution_principals USING btree (tenant_id, user_id)`.
- `CREATE INDEX execution_principals_workspace_id_idx ON public.execution_principals USING btree (tenant_id, workspace_id)`.

### revoked_access

Chặn tài khoản đã bị thu hồi quyền toàn platform

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **False/False**. FK ra/vào: **0/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `email` | `text` | True | PK | `—` | Địa chỉ email |
| `revoked_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm thu hồi |
| `revoked_by` | `text` | True | — | `—` | Người thu hồi quyền |

Ràng buộc:

- `revoked_access_pkey`: `PRIMARY KEY (email)`.

Chỉ mục:

- `CREATE UNIQUE INDEX revoked_access_pkey ON public.revoked_access USING btree (email)`.

### interruption_scopes

Địa bàn bị ảnh hưởng

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **3/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `tenant_id` | `uuid` | True | PK/FK | `—` | Tenant sở hữu dữ liệu |
| `interruption_id` | `uuid` | True | PK/FK | `—` | Tham chiếu đợt cắt và mở nước |
| `scope_id` | `uuid` | True | PK/FK | `—` | Tham chiếu phạm vi quyền có kiểu rõ ràng |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |

Ràng buộc:

- `interruption_scopes_interruption_id_fk`: `FOREIGN KEY (tenant_id, interruption_id) REFERENCES service_interruptions(tenant_id, id) ON DELETE RESTRICT`.
- `interruption_scopes_scope_id_fk`: `FOREIGN KEY (tenant_id, scope_id) REFERENCES access_scopes(tenant_id, id) ON DELETE RESTRICT`.
- `interruption_scopes_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `interruption_scopes_tenant_id_interruption_id_scope_id_pk`: `PRIMARY KEY (tenant_id, interruption_id, scope_id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX interruption_scopes_tenant_id_interruption_id_scope_id_pk ON public.interruption_scopes USING btree (tenant_id, interruption_id, scope_id)`.

## 02 Địa bàn, nhân sự và danh mục

### domains

Miền nghiệp vụ có thể cấu hình

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **1**. RLS/FORCE: **True/True**. FK ra/vào: **1/7**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `code` | `text` | True | — | `—` | Mã định danh nghiệp vụ |
| `name` | `text` | True | — | `—` | Tên hiển thị |
| `description` | `text` | False | — | `—` | Mô tả |
| `status` | `text` | True | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |

Ràng buộc:

- `domains_pkey`: `PRIMARY KEY (id)`.
- `domains_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `domains_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `domains_unique_0`: `UNIQUE (tenant_id, code)`.

Chỉ mục:

- `CREATE UNIQUE INDEX domains_pkey ON public.domains USING btree (id)`.
- `CREATE UNIQUE INDEX domains_tenant_key_uq ON public.domains USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX domains_unique_0 ON public.domains USING btree (tenant_id, code)`.

### sites

Khu đô thị

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **1**. RLS/FORCE: **True/True**. FK ra/vào: **2/9**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `domain_id` | `uuid` | True | FK | `—` | Tham chiếu miền nghiệp vụ có thể cấu hình |
| `code` | `text` | True | — | `—` | Mã định danh nghiệp vụ |
| `name` | `text` | True | — | `—` | Tên hiển thị |
| `address` | `text` | True | — | `—` | Địa chỉ |
| `timezone` | `text` | True | — | `'Asia/Ho_Chi_Minh'::text` | Múi giờ IANA |
| `status` | `text` | True | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |

Ràng buộc:

- `sites_domain_id_fk`: `FOREIGN KEY (tenant_id, domain_id) REFERENCES domains(tenant_id, id) ON DELETE RESTRICT`.
- `sites_pkey`: `PRIMARY KEY (id)`.
- `sites_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `sites_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `sites_unique_0`: `UNIQUE (domain_id, code)`.

Chỉ mục:

- `CREATE UNIQUE INDEX sites_pkey ON public.sites USING btree (id)`.
- `CREATE UNIQUE INDEX sites_tenant_key_uq ON public.sites USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX sites_unique_0 ON public.sites USING btree (domain_id, code)`.

### zones

Phân khu

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **8**. RLS/FORCE: **True/True**. FK ra/vào: **2/4**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `site_id` | `uuid` | True | FK | `—` | Tham chiếu khu đô thị |
| `code` | `text` | True | — | `—` | Mã định danh nghiệp vụ |
| `name` | `text` | True | — | `—` | Tên hiển thị |
| `status` | `text` | True | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |

Ràng buộc:

- `zones_pkey`: `PRIMARY KEY (id)`.
- `zones_site_id_fk`: `FOREIGN KEY (tenant_id, site_id) REFERENCES sites(tenant_id, id) ON DELETE RESTRICT`.
- `zones_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `zones_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `zones_unique_0`: `UNIQUE (site_id, code)`.

Chỉ mục:

- `CREATE UNIQUE INDEX zones_pkey ON public.zones USING btree (id)`.
- `CREATE UNIQUE INDEX zones_tenant_key_uq ON public.zones USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX zones_unique_0 ON public.zones USING btree (site_id, code)`.

### buildings

Tòa nhà

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **14**. RLS/FORCE: **True/True**. FK ra/vào: **3/13**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `site_id` | `uuid` | True | FK | `—` | Tham chiếu khu đô thị |
| `zone_id` | `uuid` | False | FK | `—` | Tham chiếu phân khu |
| `code` | `text` | True | — | `—` | Mã định danh nghiệp vụ |
| `name` | `text` | True | — | `—` | Tên hiển thị |
| `status` | `text` | True | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |

Ràng buộc:

- `buildings_pkey`: `PRIMARY KEY (id)`.
- `buildings_site_id_fk`: `FOREIGN KEY (tenant_id, site_id) REFERENCES sites(tenant_id, id) ON DELETE RESTRICT`.
- `buildings_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `buildings_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `buildings_unique_0`: `UNIQUE (site_id, code)`.
- `buildings_zone_id_fk`: `FOREIGN KEY (tenant_id, zone_id) REFERENCES zones(tenant_id, id) ON DELETE RESTRICT`.

Chỉ mục:

- `CREATE UNIQUE INDEX buildings_pkey ON public.buildings USING btree (id)`.
- `CREATE UNIQUE INDEX buildings_tenant_key_uq ON public.buildings USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX buildings_unique_0 ON public.buildings USING btree (site_id, code)`.

### units

Căn hộ hoặc nhà liền kề

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **20**. RLS/FORCE: **True/True**. FK ra/vào: **4/5**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `site_id` | `uuid` | True | FK | `—` | Tham chiếu khu đô thị |
| `zone_id` | `uuid` | False | FK | `—` | Tham chiếu phân khu |
| `building_id` | `uuid` | False | FK | `—` | Tham chiếu tòa nhà |
| `code` | `text` | True | — | `—` | Mã định danh nghiệp vụ |
| `unit_kind` | `text` | True | — | `—` | Loại căn hộ hoặc nhà ở |
| `floor` | `text` | False | — | `—` | Tầng |
| `status` | `text` | True | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |

Ràng buộc:

- `units_building_id_fk`: `FOREIGN KEY (tenant_id, building_id) REFERENCES buildings(tenant_id, id) ON DELETE RESTRICT`.
- `units_check_0`: `CHECK (unit_kind = ANY (ARRAY['apartment'::text, 'townhouse'::text, 'villa'::text, 'other'::text]))`.
- `units_pkey`: `PRIMARY KEY (id)`.
- `units_site_id_fk`: `FOREIGN KEY (tenant_id, site_id) REFERENCES sites(tenant_id, id) ON DELETE RESTRICT`.
- `units_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `units_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `units_zone_id_fk`: `FOREIGN KEY (tenant_id, zone_id) REFERENCES zones(tenant_id, id) ON DELETE RESTRICT`.

Chỉ mục:

- `CREATE UNIQUE INDEX units_partial_0 ON public.units USING btree (building_id, code) WHERE (building_id IS NOT NULL)`.
- `CREATE UNIQUE INDEX units_partial_1 ON public.units USING btree (zone_id, code) WHERE (building_id IS NULL)`.
- `CREATE UNIQUE INDEX units_pkey ON public.units USING btree (id)`.
- `CREATE UNIQUE INDEX units_tenant_key_uq ON public.units USING btree (tenant_id, id)`.

### unit_residents

Quyền cư trú đã xác minh

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **20**. RLS/FORCE: **True/True**. FK ra/vào: **4/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `unit_id` | `uuid` | True | FK | `—` | Tham chiếu căn hộ hoặc nhà liền kề |
| `user_id` | `text` | True | FK | `—` | Tài khoản liên quan |
| `relation` | `text` | True | — | `—` | Quan hệ cư trú |
| `verification_status` | `text` | True | — | `—` | Trạng thái xác minh cư trú |
| `valid_from` | `timestamp with time zone` | True | — | `—` | Bắt đầu hiệu lực |
| `valid_to` | `timestamp with time zone` | False | — | `—` | Kết thúc hiệu lực; NULL là chưa kết thúc |
| `verified_by` | `text` | False | FK | `—` | Tham chiếu tài khoản người dùng chung của platform |
| `verified_at` | `timestamp with time zone` | False | — | `—` | Thời điểm xác minh |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |

Ràng buộc:

- `unit_residents_check_0`: `CHECK (relation = ANY (ARRAY['owner'::text, 'tenant'::text, 'household'::text]))`.
- `unit_residents_check_1`: `CHECK (verification_status = ANY (ARRAY['pending'::text, 'verified'::text, 'rejected'::text, 'expired'::text]))`.
- `unit_residents_pkey`: `PRIMARY KEY (id)`.
- `unit_residents_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `unit_residents_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `unit_residents_unit_id_fk`: `FOREIGN KEY (tenant_id, unit_id) REFERENCES units(tenant_id, id) ON DELETE RESTRICT`.
- `unit_residents_user_id_fk`: `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT`.
- `unit_residents_verified_by_fk`: `FOREIGN KEY (verified_by) REFERENCES users(id) ON DELETE RESTRICT`.

Chỉ mục:

- `CREATE UNIQUE INDEX unit_residents_pkey ON public.unit_residents USING btree (id)`.
- `CREATE UNIQUE INDEX unit_residents_tenant_key_uq ON public.unit_residents USING btree (tenant_id, id)`.
- `CREATE INDEX unit_residents_user_id_idx ON public.unit_residents USING btree (tenant_id, user_id)`.

### management_units

Ban quản lý như một tổ chức

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **1**. RLS/FORCE: **True/True**. FK ra/vào: **1/10**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `code` | `text` | True | — | `—` | Mã định danh nghiệp vụ |
| `name` | `text` | True | — | `—` | Tên hiển thị |
| `status` | `text` | True | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `contact_phone` | `text` | False | — | `—` | Số liên hệ được chụp tại thời điểm tạo |
| `contact_email` | `text` | False | — | `—` | Email liên hệ |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |

Ràng buộc:

- `management_units_pkey`: `PRIMARY KEY (id)`.
- `management_units_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `management_units_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `management_units_unique_0`: `UNIQUE (tenant_id, code)`.

Chỉ mục:

- `CREATE UNIQUE INDEX management_units_pkey ON public.management_units USING btree (id)`.
- `CREATE UNIQUE INDEX management_units_tenant_key_uq ON public.management_units USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX management_units_unique_0 ON public.management_units USING btree (tenant_id, code)`.

### management_coverage

Địa bàn phụ trách theo thời gian

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **2**. RLS/FORCE: **True/True**. FK ra/vào: **4/1**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `management_unit_id` | `uuid` | True | FK | `—` | Tham chiếu ban quản lý như một tổ chức |
| `scope_id` | `uuid` | True | FK | `—` | Tham chiếu phạm vi quyền có kiểu rõ ràng |
| `service_category_id` | `uuid` | True | FK | `—` | Tham chiếu phân loại chuẩn cho routing và báo cáo |
| `valid_from` | `timestamp with time zone` | True | — | `—` | Bắt đầu hiệu lực |
| `valid_to` | `timestamp with time zone` | False | — | `—` | Kết thúc hiệu lực; NULL là chưa kết thúc |
| `priority` | `integer` | True | — | `0` | Mức ưu tiên hoặc trọng số xếp hàng |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |

Ràng buộc:

- `management_coverage_management_unit_id_fk`: `FOREIGN KEY (tenant_id, management_unit_id) REFERENCES management_units(tenant_id, id) ON DELETE RESTRICT`.
- `management_coverage_period_excl`: `EXCLUDE USING gist (scope_id WITH =, service_category_id WITH =, tstzrange(valid_from, valid_to, '[)'::text) WITH &&)`.
- `management_coverage_pkey`: `PRIMARY KEY (id)`.
- `management_coverage_scope_id_fk`: `FOREIGN KEY (tenant_id, scope_id) REFERENCES access_scopes(tenant_id, id) ON DELETE RESTRICT`.
- `management_coverage_service_category_id_fk`: `FOREIGN KEY (tenant_id, service_category_id) REFERENCES service_categories(tenant_id, id) ON DELETE RESTRICT`.
- `management_coverage_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `management_coverage_tenant_key_uq`: `UNIQUE (tenant_id, id)`.

Chỉ mục:

- `CREATE INDEX management_coverage_period_excl ON public.management_coverage USING gist (scope_id, service_category_id, tstzrange(valid_from, valid_to, '[)'::text))`.
- `CREATE UNIQUE INDEX management_coverage_pkey ON public.management_coverage USING btree (id)`.
- `CREATE UNIQUE INDEX management_coverage_tenant_key_uq ON public.management_coverage USING btree (tenant_id, id)`.

### access_scopes

Phạm vi quyền có kiểu rõ ràng

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **24**. RLS/FORCE: **True/True**. FK ra/vào: **5/11**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `kind` | `text` | True | — | `—` | Loại bản ghi |
| `management_unit_id` | `uuid` | False | FK | `—` | Tham chiếu ban quản lý như một tổ chức |
| `site_id` | `uuid` | False | FK | `—` | Tham chiếu khu đô thị |
| `zone_id` | `uuid` | False | FK | `—` | Tham chiếu phân khu |
| `building_id` | `uuid` | False | FK | `—` | Tham chiếu tòa nhà |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |

Ràng buộc:

- `access_scopes_building_id_fk`: `FOREIGN KEY (tenant_id, building_id) REFERENCES buildings(tenant_id, id) ON DELETE RESTRICT`.
- `access_scopes_check_0`: `CHECK (kind = ANY (ARRAY['tenant'::text, 'management'::text, 'site'::text, 'zone'::text, 'building'::text]))`.
- `access_scopes_management_unit_id_fk`: `FOREIGN KEY (tenant_id, management_unit_id) REFERENCES management_units(tenant_id, id) ON DELETE RESTRICT`.
- `access_scopes_pkey`: `PRIMARY KEY (id)`.
- `access_scopes_site_id_fk`: `FOREIGN KEY (tenant_id, site_id) REFERENCES sites(tenant_id, id) ON DELETE RESTRICT`.
- `access_scopes_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `access_scopes_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `access_scopes_zone_id_fk`: `FOREIGN KEY (tenant_id, zone_id) REFERENCES zones(tenant_id, id) ON DELETE RESTRICT`.

Chỉ mục:

- `CREATE UNIQUE INDEX access_scopes_partial_0 ON public.access_scopes USING btree (tenant_id) WHERE (kind = 'tenant'::text)`.
- `CREATE UNIQUE INDEX access_scopes_partial_1 ON public.access_scopes USING btree (tenant_id, management_unit_id) WHERE (kind = 'management'::text)`.
- `CREATE UNIQUE INDEX access_scopes_partial_2 ON public.access_scopes USING btree (tenant_id, site_id) WHERE (kind = 'site'::text)`.
- `CREATE UNIQUE INDEX access_scopes_partial_3 ON public.access_scopes USING btree (tenant_id, zone_id) WHERE (kind = 'zone'::text)`.
- `CREATE UNIQUE INDEX access_scopes_partial_4 ON public.access_scopes USING btree (tenant_id, building_id) WHERE (kind = 'building'::text)`.
- `CREATE UNIQUE INDEX access_scopes_pkey ON public.access_scopes USING btree (id)`.
- `CREATE UNIQUE INDEX access_scopes_tenant_key_uq ON public.access_scopes USING btree (tenant_id, id)`.

### service_categories

Phân loại chuẩn cho routing và báo cáo

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **2**. RLS/FORCE: **True/True**. FK ra/vào: **2/11**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `parent_id` | `uuid` | False | FK | `—` | Tham chiếu phân loại chuẩn cho routing và báo cáo |
| `code` | `text` | True | — | `—` | Mã định danh nghiệp vụ |
| `name` | `text` | True | — | `—` | Tên hiển thị |
| `enabled` | `boolean` | True | — | `true` | Có được bật hay không |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |

Ràng buộc:

- `service_categories_parent_id_fk`: `FOREIGN KEY (tenant_id, parent_id) REFERENCES service_categories(tenant_id, id) ON DELETE RESTRICT`.
- `service_categories_pkey`: `PRIMARY KEY (id)`.
- `service_categories_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `service_categories_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `service_categories_unique_0`: `UNIQUE (tenant_id, code)`.

Chỉ mục:

- `CREATE UNIQUE INDEX service_categories_pkey ON public.service_categories USING btree (id)`.
- `CREATE UNIQUE INDEX service_categories_tenant_key_uq ON public.service_categories USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX service_categories_unique_0 ON public.service_categories USING btree (tenant_id, code)`.

### incident_types

Loại sự cố thống kê được

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **2/1**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `category_id` | `uuid` | True | FK | `—` | Tham chiếu phân loại chuẩn cho routing và báo cáo |
| `code` | `text` | True | — | `—` | Mã định danh nghiệp vụ |
| `name` | `text` | True | — | `—` | Tên hiển thị |
| `default_priority` | `text` | True | — | `—` | Mức ưu tiên mặc định |
| `requires_visit` | `boolean` | True | — | `—` | Có cần đến hiện trường |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |

Ràng buộc:

- `incident_types_category_id_fk`: `FOREIGN KEY (tenant_id, category_id) REFERENCES service_categories(tenant_id, id) ON DELETE RESTRICT`.
- `incident_types_pkey`: `PRIMARY KEY (id)`.
- `incident_types_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `incident_types_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `incident_types_unique_0`: `UNIQUE (tenant_id, code)`.

Chỉ mục:

- `CREATE UNIQUE INDEX incident_types_pkey ON public.incident_types USING btree (id)`.
- `CREATE UNIQUE INDEX incident_types_tenant_key_uq ON public.incident_types USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX incident_types_unique_0 ON public.incident_types USING btree (tenant_id, code)`.

### sla_policies

Thời hạn phục vụ theo phạm vi

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **4/3**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `management_unit_id` | `uuid` | True | FK | `—` | Tham chiếu ban quản lý như một tổ chức |
| `category_id` | `uuid` | True | FK | `—` | Tham chiếu phân loại chuẩn cho routing và báo cáo |
| `priority` | `text` | True | — | `—` | Mức ưu tiên hoặc trọng số xếp hàng |
| `response_minutes` | `integer` | True | — | `—` | Thời hạn phản hồi theo phút |
| `resolution_minutes` | `integer` | True | — | `—` | Thời hạn giải quyết theo phút |
| `effective_from` | `timestamp with time zone` | True | — | `—` | Bắt đầu áp dụng |
| `effective_to` | `timestamp with time zone` | False | — | `—` | Kết thúc áp dụng |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |
| `domain_id` | `uuid` | True | FK | `—` | Tham chiếu domains.id |
| `request_kind` | `text` | True | — | `—` | incident/service_request |
| `version_no` | `integer` | True | — | `—` | Số phiên bản policy cùng scope |
| `clock_basis` | `text` | True | — | `'elapsed_24x7'::text` | elapsed_24x7; V3 chỉ hỗ trợ kiểu này |

Ràng buộc:

- `sla_policies_category_id_fk`: `FOREIGN KEY (tenant_id, category_id) REFERENCES service_categories(tenant_id, id) ON DELETE RESTRICT`.
- `sla_policies_check_0`: `CHECK (response_minutes > 0 AND resolution_minutes > 0)`.
- `sla_policies_check_1`: `CHECK (effective_to IS NULL OR effective_to > effective_from)`.
- `sla_policies_check_2`: `CHECK (clock_basis = 'elapsed_24x7'::text)`.
- `sla_policies_check_3`: `CHECK (request_kind = ANY (ARRAY['incident'::text, 'service_request'::text]))`.
- `sla_policies_domain_id_fk`: `FOREIGN KEY (tenant_id, domain_id) REFERENCES domains(tenant_id, id) ON DELETE RESTRICT`.
- `sla_policies_management_unit_id_fk`: `FOREIGN KEY (tenant_id, management_unit_id) REFERENCES management_units(tenant_id, id) ON DELETE RESTRICT`.
- `sla_policies_pkey`: `PRIMARY KEY (id)`.
- `sla_policies_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `sla_policies_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `sla_policies_unique_0`: `UNIQUE (tenant_id, domain_id, management_unit_id, category_id, request_kind, priority, version_no)`.
- `sla_policy_period_excl`: `EXCLUDE USING gist (tenant_id WITH =, domain_id WITH =, management_unit_id WITH =, category_id WITH =, request_kind WITH =, priority WITH =, tstzrange(effective_from, effective_to, '[)'::text) WITH &&)`.

Chỉ mục:

- `CREATE UNIQUE INDEX sla_policies_pkey ON public.sla_policies USING btree (id)`.
- `CREATE UNIQUE INDEX sla_policies_tenant_key_uq ON public.sla_policies USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX sla_policies_unique_0 ON public.sla_policies USING btree (tenant_id, domain_id, management_unit_id, category_id, request_kind, priority, version_no)`.
- `CREATE INDEX sla_policy_period_excl ON public.sla_policies USING gist (tenant_id, domain_id, management_unit_id, category_id, request_kind, priority, tstzrange(effective_from, effective_to, '[)'::text))`.

### staff_profiles

Thông tin vận hành nhân viên

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **2**. RLS/FORCE: **True/True**. FK ra/vào: **3/5**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `user_id` | `text` | True | FK | `—` | Tài khoản liên quan |
| `management_unit_id` | `uuid` | True | FK | `—` | Tham chiếu ban quản lý như một tổ chức |
| `employee_code` | `text` | True | — | `—` | Mã nhân viên |
| `availability` | `text` | True | — | `—` | Tình trạng sẵn sàng vận hành |
| `max_concurrent_jobs` | `integer` | True | — | `1` | Số việc đồng thời tối đa |
| `active` | `boolean` | True | — | `true` | Có đang hoạt động |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |

Ràng buộc:

- `staff_profiles_check_0`: `CHECK (availability = ANY (ARRAY['available'::text, 'busy'::text, 'offline'::text, 'on_leave'::text]))`.
- `staff_profiles_management_unit_id_fk`: `FOREIGN KEY (tenant_id, management_unit_id) REFERENCES management_units(tenant_id, id) ON DELETE RESTRICT`.
- `staff_profiles_pkey`: `PRIMARY KEY (id)`.
- `staff_profiles_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `staff_profiles_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `staff_profiles_unique_0`: `UNIQUE (tenant_id, user_id)`.
- `staff_profiles_unique_1`: `UNIQUE (tenant_id, employee_code)`.
- `staff_profiles_user_id_fk`: `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT`.

Chỉ mục:

- `CREATE UNIQUE INDEX staff_profiles_pkey ON public.staff_profiles USING btree (id)`.
- `CREATE UNIQUE INDEX staff_profiles_tenant_key_uq ON public.staff_profiles USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX staff_profiles_unique_0 ON public.staff_profiles USING btree (tenant_id, user_id)`.
- `CREATE UNIQUE INDEX staff_profiles_unique_1 ON public.staff_profiles USING btree (tenant_id, employee_code)`.
- `CREATE INDEX staff_profiles_user_id_idx ON public.staff_profiles USING btree (tenant_id, user_id)`.

### staff_shifts

Ca làm việc và nghỉ

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **2**. RLS/FORCE: **True/True**. FK ra/vào: **2/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `staff_id` | `uuid` | True | FK | `—` | Tham chiếu thông tin vận hành nhân viên |
| `starts_at` | `timestamp with time zone` | True | — | `—` | Bắt đầu ca |
| `ends_at` | `timestamp with time zone` | True | — | `—` | Kết thúc ca |
| `status` | `text` | True | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |

Ràng buộc:

- `staff_shifts_check_0`: `CHECK (status = ANY (ARRAY['scheduled'::text, 'available'::text, 'leave'::text, 'cancelled'::text]))`.
- `staff_shifts_pkey`: `PRIMARY KEY (id)`.
- `staff_shifts_staff_id_fk`: `FOREIGN KEY (tenant_id, staff_id) REFERENCES staff_profiles(tenant_id, id) ON DELETE RESTRICT`.
- `staff_shifts_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `staff_shifts_tenant_key_uq`: `UNIQUE (tenant_id, id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX staff_shifts_pkey ON public.staff_shifts USING btree (id)`.
- `CREATE UNIQUE INDEX staff_shifts_tenant_key_uq ON public.staff_shifts USING btree (tenant_id, id)`.

### staff_specialties

Chuyên môn nhân viên

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **2**. RLS/FORCE: **True/True**. FK ra/vào: **3/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `tenant_id` | `uuid` | True | PK/FK | `—` | Tenant sở hữu dữ liệu |
| `staff_id` | `uuid` | True | PK/FK | `—` | Tham chiếu thông tin vận hành nhân viên |
| `category_id` | `uuid` | True | PK/FK | `—` | Tham chiếu phân loại chuẩn cho routing và báo cáo |
| `proficiency` | `text` | True | — | `—` | Mức chuyên môn |
| `active` | `boolean` | True | — | `true` | Có đang hoạt động |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |

Ràng buộc:

- `staff_specialties_category_id_fk`: `FOREIGN KEY (tenant_id, category_id) REFERENCES service_categories(tenant_id, id) ON DELETE RESTRICT`.
- `staff_specialties_staff_id_fk`: `FOREIGN KEY (tenant_id, staff_id) REFERENCES staff_profiles(tenant_id, id) ON DELETE RESTRICT`.
- `staff_specialties_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `staff_specialties_tenant_id_staff_id_category_id_pk`: `PRIMARY KEY (tenant_id, staff_id, category_id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX staff_specialties_tenant_id_staff_id_category_id_pk ON public.staff_specialties USING btree (tenant_id, staff_id, category_id)`.

### service_interruptions

Đợt cắt và mở nước

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **4/2**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `work_order_id` | `uuid` | True | FK | `—` | Tham chiếu công việc hiện trường thuộc ticket |
| `approval_id` | `uuid` | True | FK | `—` | Tham chiếu chấp thuận sửa chữa hoặc can thiệp |
| `utility` | `text` | True | — | `—` | Nước hoặc điện |
| `reason` | `text` | True | — | `—` | Lý do |
| `planned_start` | `timestamp with time zone` | True | — | `—` | Thời điểm dự kiến cắt dịch vụ |
| `planned_end` | `timestamp with time zone` | True | — | `—` | Thời điểm dự kiến khôi phục |
| `actual_start` | `timestamp with time zone` | False | — | `—` | Thời điểm cắt thực tế |
| `actual_end` | `timestamp with time zone` | False | — | `—` | Thời điểm khôi phục thực tế |
| `status` | `text` | True | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `operated_by` | `text` | False | FK | `—` | Tham chiếu tài khoản người dùng chung của platform |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |

Ràng buộc:

- `service_interruptions_approval_id_fk`: `FOREIGN KEY (tenant_id, approval_id) REFERENCES work_approvals(tenant_id, id) ON DELETE RESTRICT`.
- `service_interruptions_check_0`: `CHECK (utility = ANY (ARRAY['water'::text, 'power'::text]))`.
- `service_interruptions_check_1`: `CHECK (status = ANY (ARRAY['proposed'::text, 'approved'::text, 'notified'::text, 'active'::text, 'restored'::text, 'cancelled'::text]))`.
- `service_interruptions_operated_by_fk`: `FOREIGN KEY (operated_by) REFERENCES users(id) ON DELETE RESTRICT`.
- `service_interruptions_pkey`: `PRIMARY KEY (id)`.
- `service_interruptions_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `service_interruptions_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `service_interruptions_work_order_id_fk`: `FOREIGN KEY (tenant_id, work_order_id) REFERENCES work_orders(tenant_id, id) ON DELETE RESTRICT`.

Chỉ mục:

- `CREATE UNIQUE INDEX service_interruptions_pkey ON public.service_interruptions USING btree (id)`.
- `CREATE UNIQUE INDEX service_interruptions_tenant_key_uq ON public.service_interruptions USING btree (tenant_id, id)`.

## 03 Agent và Factory

### agents

Danh mục agent của platform

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **4**. RLS/FORCE: **True/True**. FK ra/vào: **3/26**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `text` | True | PK | `—` | Định danh bản ghi |
| `name` | `text` | True | — | `—` | Tên hiển thị |
| `type` | `agent_type` | True | — | `—` | Giá trị type; ý nghĩa và phạm vi theo quy tắc bảng |
| `configuration` | `jsonb` | True | — | `—` | Cấu hình agent legacy |
| `package_id` | `uuid` | False | FK | `—` | Tham chiếu gói triển khai cấu hình tenant |
| `override` | `jsonb` | False | — | `—` | Cấu hình ghi đè |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |
| `tenant_id` | `uuid` | True | FK | `(NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid` | Tenant sở hữu dữ liệu |
| `workspace_id` | `uuid` | False | FK | `(NULLIF(current_setting('app.workspace_id'::text, true), ''::text))::uuid` | Workspace của ban quản lý |
| `purpose` | `text` | True | — | `'specialist'::text` | Vai trò chức năng agent hoặc mục đích file |
| `status` | `text` | True | — | `'active'::text` | Trạng thái; xem tập giá trị và quy tắc bên dưới |

Ràng buộc:

- `agents_check_0`: `CHECK (purpose = 'reception'::text AND workspace_id IS NULL OR (purpose = ANY (ARRAY['supervisor'::text, 'specialist'::text])) AND workspace_id IS NOT NULL)`.
- `agents_check_1`: `CHECK (purpose = ANY (ARRAY['reception'::text, 'supervisor'::text, 'specialist'::text]))`.
- `agents_check_2`: `CHECK (status = ANY (ARRAY['draft'::text, 'active'::text, 'archived'::text]))`.
- `agents_package_id_fk`: `FOREIGN KEY (tenant_id, package_id) REFERENCES deployment_packages(tenant_id, id) ON DELETE RESTRICT`.
- `agents_pkey`: `PRIMARY KEY (id)`.
- `agents_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `agents_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `agents_workspace_id_fk`: `FOREIGN KEY (tenant_id, workspace_id) REFERENCES workspaces(tenant_id, id) ON DELETE RESTRICT`.

Chỉ mục:

- `CREATE UNIQUE INDEX agents_partial_0 ON public.agents USING btree (tenant_id) WHERE ((purpose = 'reception'::text) AND (status = 'active'::text))`.
- `CREATE UNIQUE INDEX agents_pkey ON public.agents USING btree (id)`.
- `CREATE UNIQUE INDEX agents_tenant_key_uq ON public.agents USING btree (tenant_id, id)`.
- `CREATE INDEX agents_workspace_id_idx ON public.agents USING btree (tenant_id, workspace_id)`.

### agent_versions

Snapshot cấu hình agent bất biến

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **1**. RLS/FORCE: **True/True**. FK ra/vào: **4/4**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `agent_id` | `text` | True | FK | `—` | Tham chiếu danh mục agent của platform |
| `version_no` | `integer` | True | — | `—` | Số phiên bản tăng dần |
| `runtime` | `text` | True | — | `—` | Loại runtime thực thi |
| `framework_version` | `text` | True | — | `—` | Phiên bản framework đã khóa |
| `model_profile_id` | `uuid` | False | FK | `—` | Tham chiếu cấu hình model dùng chung có kiểm soát |
| `instructions` | `text` | True | — | `—` | Nội dung chỉ dẫn |
| `config` | `jsonb` | True | — | `—` | Cấu hình có schema version |
| `config_hash` | `text` | True | — | `—` | Hash cấu hình |
| `created_by` | `text` | True | FK | `—` | Tham chiếu tài khoản người dùng chung của platform |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |

Ràng buộc:

- `agent_versions_agent_id_fk`: `FOREIGN KEY (tenant_id, agent_id) REFERENCES agents(tenant_id, id) ON DELETE RESTRICT`.
- `agent_versions_check_0`: `CHECK (runtime = ANY (ARRAY['langgraph'::text, 'agentscope'::text, 'remote'::text]))`.
- `agent_versions_created_by_fk`: `FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT`.
- `agent_versions_model_profile_id_fk`: `FOREIGN KEY (tenant_id, model_profile_id) REFERENCES model_profiles(tenant_id, id) ON DELETE RESTRICT`.
- `agent_versions_pkey`: `PRIMARY KEY (id)`.
- `agent_versions_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `agent_versions_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `agent_versions_unique_0`: `UNIQUE (agent_id, version_no)`.

Chỉ mục:

- `CREATE UNIQUE INDEX agent_versions_pkey ON public.agent_versions USING btree (id)`.
- `CREATE UNIQUE INDEX agent_versions_tenant_key_uq ON public.agent_versions USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX agent_versions_unique_0 ON public.agent_versions USING btree (agent_id, version_no)`.

### agent_profiles

Hồ sơ và người tạo agent

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **3/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `agent_id` | `text` | True | PK/FK | `—` | Tham chiếu danh mục agent của platform |
| `owner_user_id` | `text` | False | FK | `—` | Tham chiếu tài khoản người dùng chung của platform |
| `title` | `text` | True | — | `—` | Tiêu đề |
| `role_description` | `text` | True | — | `—` | Mô tả nhiệm vụ agent |
| `avatar_seed` | `text` | True | — | `—` | Seed tạo avatar |
| `visibility` | `agent_visibility` | True | — | `—` | Phạm vi hiển thị |
| `callback_token_hash` | `text` | False | — | `—` | Hash token callback; không lưu token gốc |
| `callback_token_issued_at` | `timestamp with time zone` | False | — | `—` | Thời điểm cấp callback token |
| `deleted_at` | `timestamp with time zone` | False | — | `—` | Thời điểm xóa mềm |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |
| `tenant_id` | `uuid` | True | FK | `(NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid` | Tenant sở hữu dữ liệu |

Ràng buộc:

- `agent_profiles_agent_id_fk`: `FOREIGN KEY (tenant_id, agent_id) REFERENCES agents(tenant_id, id) ON DELETE RESTRICT`.
- `agent_profiles_owner_user_id_fk`: `FOREIGN KEY (owner_user_id) REFERENCES users(id) ON DELETE RESTRICT`.
- `agent_profiles_pkey`: `PRIMARY KEY (agent_id)`.
- `agent_profiles_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `agent_profiles_tenant_key_uq`: `UNIQUE (tenant_id, agent_id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX agent_profiles_pkey ON public.agent_profiles USING btree (agent_id)`.
- `CREATE UNIQUE INDEX agent_profiles_tenant_key_uq ON public.agent_profiles USING btree (tenant_id, agent_id)`.

### agent_preferences

Tùy chọn hiển thị agent theo người dùng

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **3/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `user_id` | `text` | True | PK/FK | `—` | Tài khoản liên quan |
| `agent_id` | `text` | True | PK/FK | `—` | Tham chiếu danh mục agent của platform |
| `hidden_at` | `timestamp with time zone` | False | — | `—` | Thời điểm ẩn agent |
| `tenant_id` | `uuid` | True | FK | `(NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid` | Tenant sở hữu dữ liệu |

Ràng buộc:

- `agent_preferences_agent_id_fk`: `FOREIGN KEY (tenant_id, agent_id) REFERENCES agents(tenant_id, id) ON DELETE RESTRICT`.
- `agent_preferences_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `agent_preferences_user_id_agent_id_pk`: `PRIMARY KEY (user_id, agent_id)`.
- `agent_preferences_user_id_fk`: `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT`.

Chỉ mục:

- `CREATE UNIQUE INDEX agent_preferences_user_id_agent_id_pk ON public.agent_preferences USING btree (user_id, agent_id)`.

### agent_releases

Phát hành một version

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **4/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `agent_id` | `text` | True | FK | `—` | Tham chiếu danh mục agent của platform |
| `version_id` | `uuid` | True | FK | `—` | Tham chiếu snapshot cấu hình agent bất biến |
| `status` | `text` | True | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `published_by` | `text` | False | FK | `—` | Tham chiếu tài khoản người dùng chung của platform |
| `published_at` | `timestamp with time zone` | False | — | `—` | Thời điểm công bố |
| `revoked_at` | `timestamp with time zone` | False | — | `—` | Thời điểm thu hồi |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |

Ràng buộc:

- `agent_releases_agent_id_fk`: `FOREIGN KEY (tenant_id, agent_id) REFERENCES agents(tenant_id, id) ON DELETE RESTRICT`.
- `agent_releases_check_0`: `CHECK (status = ANY (ARRAY['draft'::text, 'published'::text, 'revoked'::text]))`.
- `agent_releases_pkey`: `PRIMARY KEY (id)`.
- `agent_releases_published_by_fk`: `FOREIGN KEY (published_by) REFERENCES users(id) ON DELETE RESTRICT`.
- `agent_releases_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `agent_releases_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `agent_releases_version_id_fk`: `FOREIGN KEY (tenant_id, version_id) REFERENCES agent_versions(tenant_id, id) ON DELETE RESTRICT`.

Chỉ mục:

- `CREATE UNIQUE INDEX agent_releases_partial_0 ON public.agent_releases USING btree (agent_id) WHERE ((status = 'published'::text) AND (revoked_at IS NULL))`.
- `CREATE UNIQUE INDEX agent_releases_pkey ON public.agent_releases USING btree (id)`.
- `CREATE UNIQUE INDEX agent_releases_tenant_key_uq ON public.agent_releases USING btree (tenant_id, id)`.

### agent_build_requests

Hội thoại bổ sung thông tin khi tạo agent

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **5/1**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `workspace_id` | `uuid` | True | FK | `—` | Workspace của ban quản lý |
| `requested_by` | `text` | True | FK | `—` | Tham chiếu tài khoản người dùng chung của platform |
| `channel_id` | `text` | True | FK | `—` | Tham chiếu cửa sổ reception hoặc groupchat quản lý |
| `proposed_name` | `text` | True | — | `—` | Tên agent được đề xuất |
| `proposed_description` | `text` | True | — | `—` | Mô tả agent được đề xuất |
| `missing_fields` | `jsonb` | True | — | `—` | Thông tin còn thiếu cần hỏi người dùng |
| `draft_config` | `jsonb` | True | — | `—` | Cấu hình nháp |
| `status` | `text` | True | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `result_agent_id` | `text` | False | FK | `—` | Tham chiếu danh mục agent của platform |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |

Ràng buộc:

- `agent_build_requests_channel_id_fk`: `FOREIGN KEY (tenant_id, channel_id) REFERENCES channels(tenant_id, id) ON DELETE RESTRICT`.
- `agent_build_requests_check_0`: `CHECK (status = ANY (ARRAY['collecting'::text, 'ready'::text, 'confirmed'::text, 'created'::text, 'cancelled'::text]))`.
- `agent_build_requests_pkey`: `PRIMARY KEY (id)`.
- `agent_build_requests_requested_by_fk`: `FOREIGN KEY (requested_by) REFERENCES users(id) ON DELETE RESTRICT`.
- `agent_build_requests_result_agent_id_fk`: `FOREIGN KEY (tenant_id, result_agent_id) REFERENCES agents(tenant_id, id) ON DELETE RESTRICT`.
- `agent_build_requests_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `agent_build_requests_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `agent_build_requests_workspace_id_fk`: `FOREIGN KEY (tenant_id, workspace_id) REFERENCES workspaces(tenant_id, id) ON DELETE RESTRICT`.

Chỉ mục:

- `CREATE UNIQUE INDEX agent_build_requests_pkey ON public.agent_build_requests USING btree (id)`.
- `CREATE UNIQUE INDEX agent_build_requests_tenant_key_uq ON public.agent_build_requests USING btree (tenant_id, id)`.
- `CREATE INDEX agent_build_requests_workspace_id_idx ON public.agent_build_requests USING btree (tenant_id, workspace_id)`.

### agent_build_answers

Câu hỏi và câu trả lời của builder

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **3/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `request_id` | `uuid` | True | FK | `—` | Mã tương quan request trong audit |
| `question_key` | `text` | True | — | `—` | Mã câu hỏi bổ sung |
| `question` | `text` | True | — | `—` | Câu hỏi |
| `answer` | `jsonb` | False | — | `—` | Câu trả lời |
| `answered_by` | `text` | False | FK | `—` | Tham chiếu tài khoản người dùng chung của platform |
| `answered_at` | `timestamp with time zone` | False | — | `—` | Thời điểm trả lời |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `revision_no` | `integer` | True | — | `—` | Giá trị revision_no; ý nghĩa và phạm vi theo quy tắc bảng |
| `confirmed` | `boolean` | True | — | `false` | Giá trị confirmed; ý nghĩa và phạm vi theo quy tắc bảng |

Ràng buộc:

- `agent_build_answers_answered_by_fk`: `FOREIGN KEY (answered_by) REFERENCES users(id) ON DELETE RESTRICT`.
- `agent_build_answers_pkey`: `PRIMARY KEY (id)`.
- `agent_build_answers_request_id_fk`: `FOREIGN KEY (tenant_id, request_id) REFERENCES agent_build_requests(tenant_id, id) ON DELETE RESTRICT`.
- `agent_build_answers_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `agent_build_answers_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `agent_build_answers_unique_0`: `UNIQUE (request_id, question_key, revision_no)`.

Chỉ mục:

- `CREATE UNIQUE INDEX agent_build_answers_pkey ON public.agent_build_answers USING btree (id)`.
- `CREATE UNIQUE INDEX agent_build_answers_tenant_key_uq ON public.agent_build_answers USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX agent_build_answers_unique_0 ON public.agent_build_answers USING btree (request_id, question_key, revision_no)`.

### deployment_packages

Gói triển khai cấu hình tenant

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **1/2**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `source_path` | `text` | True | — | `—` | Đường dẫn gói nguồn |
| `checksum` | `text` | True | — | `—` | Checksum kiểm tra toàn vẹn |
| `loaded_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm nạp gói |
| `external_tenant_key` | `text` | True | — | `—` | Mã tenant chuỗi từ gói triển khai cũ |
| `tenant_id` | `uuid` | True | FK | `(NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid` | Tenant sở hữu dữ liệu |

Ràng buộc:

- `deployment_packages_pkey`: `PRIMARY KEY (id)`.
- `deployment_packages_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `deployment_packages_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `deployment_packages_unique_0`: `UNIQUE (tenant_id)`.
- `deployment_packages_unique_1`: `UNIQUE (external_tenant_key)`.

Chỉ mục:

- `CREATE UNIQUE INDEX deployment_packages_pkey ON public.deployment_packages USING btree (id)`.
- `CREATE UNIQUE INDEX deployment_packages_tenant_key_uq ON public.deployment_packages USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX deployment_packages_unique_0 ON public.deployment_packages USING btree (tenant_id)`.
- `CREATE UNIQUE INDEX deployment_packages_unique_1 ON public.deployment_packages USING btree (external_tenant_key)`.

### model_profiles

Cấu hình model dùng chung có kiểm soát

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **3/1**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `workspace_id` | `uuid` | False | FK | `—` | Workspace của ban quản lý |
| `code` | `text` | True | — | `—` | Mã định danh nghiệp vụ |
| `provider` | `text` | True | — | `—` | Nhà cung cấp dịch vụ |
| `model_name` | `text` | True | — | `—` | Tên model |
| `credential_id` | `uuid` | True | FK | `—` | Tham chiếu kho bí mật mã hóa |
| `parameters` | `jsonb` | True | — | `—` | Tham số cấu hình |
| `enabled` | `boolean` | True | — | `true` | Có được bật hay không |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |

Ràng buộc:

- `model_profiles_credential_id_fk`: `FOREIGN KEY (credential_id) REFERENCES credentials(id) ON DELETE RESTRICT`.
- `model_profiles_pkey`: `PRIMARY KEY (id)`.
- `model_profiles_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `model_profiles_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `model_profiles_workspace_id_fk`: `FOREIGN KEY (tenant_id, workspace_id) REFERENCES workspaces(tenant_id, id) ON DELETE RESTRICT`.

Chỉ mục:

- `CREATE UNIQUE INDEX model_profiles_partial_0 ON public.model_profiles USING btree (tenant_id, code) WHERE (workspace_id IS NULL)`.
- `CREATE UNIQUE INDEX model_profiles_partial_1 ON public.model_profiles USING btree (workspace_id, code) WHERE (workspace_id IS NOT NULL)`.
- `CREATE UNIQUE INDEX model_profiles_pkey ON public.model_profiles USING btree (id)`.
- `CREATE UNIQUE INDEX model_profiles_tenant_key_uq ON public.model_profiles USING btree (tenant_id, id)`.
- `CREATE INDEX model_profiles_workspace_id_idx ON public.model_profiles USING btree (tenant_id, workspace_id)`.

### user_instructions

Chỉ dẫn cá nhân của người dùng

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **False/False**. FK ra/vào: **1/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `user_id` | `text` | True | PK/FK | `—` | Tài khoản liên quan |
| `instructions` | `text` | True | — | `—` | Nội dung chỉ dẫn |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |

Ràng buộc:

- `user_instructions_pkey`: `PRIMARY KEY (user_id)`.
- `user_instructions_user_id_fk`: `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE`.

Chỉ mục:

- `CREATE UNIQUE INDEX user_instructions_pkey ON public.user_instructions USING btree (user_id)`.

## 04 Runtime, run và context

### runtime_backends

Một deployment lưu trạng thái framework

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **2**. RLS/FORCE: **False/False**. FK ra/vào: **0/3**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `code` | `text` | True | — | `—` | Mã định danh nghiệp vụ |
| `framework` | `text` | True | — | `—` | Framework quản lý trạng thái thực thi |
| `sdk_language` | `text` | True | — | `—` | Ngôn ngữ SDK được triển khai |
| `package_version` | `text` | True | — | `—` | Phiên bản package đã khóa trong deployment |
| `backend_kind` | `text` | True | — | `—` | Loại cơ chế persistence |
| `connection_secret_ref` | `text` | True | — | `—` | Tham chiếu secret kết nối, không lưu DSN thô |
| `schema_name` | `text` | True | — | `—` | Schema vật lý dành riêng cho backend |
| `enabled` | `boolean` | True | — | `true` | Có được bật hay không |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |

Ràng buộc:

- `runtime_backends_check_0`: `CHECK (framework = ANY (ARRAY['langgraph'::text, 'agentscope'::text]))`.
- `runtime_backends_check_1`: `CHECK (sdk_language = ANY (ARRAY['python'::text, 'javascript'::text, 'java'::text]))`.
- `runtime_backends_check_2`: `CHECK (backend_kind = ANY (ARRAY['postgres'::text, 'sqlalchemy'::text, 'custom'::text]))`.
- `runtime_backends_pkey`: `PRIMARY KEY (id)`.
- `runtime_backends_unique_0`: `UNIQUE (code)`.

Chỉ mục:

- `CREATE UNIQUE INDEX runtime_backends_pkey ON public.runtime_backends USING btree (id)`.
- `CREATE UNIQUE INDEX runtime_backends_unique_0 ON public.runtime_backends USING btree (code)`.

### runtime_identities

Ánh xạ principal sang user namespace của backend

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **3/2**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `backend_id` | `uuid` | True | FK | `—` | Tham chiếu runtime_backends |
| `principal_id` | `uuid` | True | FK | `—` | Tham chiếu execution_principals |
| `runtime_user_key` | `text` | True | — | `—` | User key opaque được adapter truyền cho framework |
| `status` | `text` | True | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |

Ràng buộc:

- `runtime_identities_backend_id_fk`: `FOREIGN KEY (backend_id) REFERENCES runtime_backends(id) ON DELETE RESTRICT`.
- `runtime_identities_check_0`: `CHECK (status = ANY (ARRAY['active'::text, 'revoked'::text]))`.
- `runtime_identities_pkey`: `PRIMARY KEY (id)`.
- `runtime_identities_principal_id_fk`: `FOREIGN KEY (tenant_id, principal_id) REFERENCES execution_principals(tenant_id, id) ON DELETE RESTRICT`.
- `runtime_identities_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `runtime_identities_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `runtime_identities_unique_0`: `UNIQUE (backend_id, principal_id)`.
- `runtime_identities_unique_1`: `UNIQUE (backend_id, runtime_user_key)`.
- `runtime_identities_unique_2`: `UNIQUE (tenant_id, id, backend_id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX runtime_identities_pkey ON public.runtime_identities USING btree (id)`.
- `CREATE UNIQUE INDEX runtime_identities_tenant_key_uq ON public.runtime_identities USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX runtime_identities_unique_0 ON public.runtime_identities USING btree (backend_id, principal_id)`.
- `CREATE UNIQUE INDEX runtime_identities_unique_1 ON public.runtime_identities USING btree (backend_id, runtime_user_key)`.
- `CREATE UNIQUE INDEX runtime_identities_unique_2 ON public.runtime_identities USING btree (tenant_id, id, backend_id)`.

### runtime_session_bindings

Chủ sở hữu và phạm vi của một thread hoặc session thực thi

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **10/6**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `identity_id` | `uuid` | True | FK | `—` | Tham chiếu runtime_identities |
| `channel_id` | `text` | True | FK | `—` | Tham chiếu cửa sổ reception hoặc groupchat quản lý |
| `agent_id` | `text` | True | FK | `—` | Tham chiếu danh mục agent của platform |
| `agent_version_id` | `uuid` | True | FK | `—` | Tham chiếu snapshot cấu hình agent bất biến |
| `team_member_id` | `uuid` | False | FK | `—` | Tham chiếu agent và context riêng của team |
| `audience_kind` | `text` | True | — | `—` | Phiên cá nhân hay context agent của nhóm |
| `customer_user_id` | `text` | False | FK | `—` | Tham chiếu tài khoản người dùng chung của platform |
| `started_by_user_id` | `text` | False | FK | `—` | Tham chiếu tài khoản người dùng chung của platform |
| `runtime_session_key` | `text` | True | — | `—` | Thread ID hoặc session ID thực sự của framework |
| `checkpoint_namespace` | `text` | True | — | `''::text` | Namespace gốc của graph trong thread |
| `status` | `text` | True | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `generation` | `integer` | True | — | `1` | Thế hệ điểm chờ để chống resume cũ |
| `policy_version` | `text` | True | — | `—` | Phiên bản policy khi chọn dữ liệu |
| `lock_version` | `bigint` | True | — | `0` | Bộ đếm CAS và fencing chống worker cũ ghi tiếp |
| `lease_owner` | `text` | False | — | `—` | Worker giữ lease |
| `lease_until` | `timestamp with time zone` | False | — | `—` | Thời điểm hết lease |
| `last_access_at` | `timestamp with time zone` | False | — | `—` | Thời điểm last access |
| `expires_at` | `timestamp with time zone` | False | — | `—` | Thời điểm hết hạn |
| `purged_at` | `timestamp with time zone` | False | — | `—` | Thời điểm purged |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |
| `backend_id` | `uuid` | True | FK | `—` | Tham chiếu runtime_backends |

Ràng buộc:

- `binding_identity_backend_fk`: `FOREIGN KEY (tenant_id, identity_id, backend_id) REFERENCES runtime_identities(tenant_id, id, backend_id)`.
- `runtime_session_bindings_agent_id_fk`: `FOREIGN KEY (tenant_id, agent_id) REFERENCES agents(tenant_id, id) ON DELETE RESTRICT`.
- `runtime_session_bindings_agent_version_id_fk`: `FOREIGN KEY (tenant_id, agent_version_id) REFERENCES agent_versions(tenant_id, id) ON DELETE RESTRICT`.
- `runtime_session_bindings_backend_id_fk`: `FOREIGN KEY (backend_id) REFERENCES runtime_backends(id) ON DELETE RESTRICT`.
- `runtime_session_bindings_channel_id_fk`: `FOREIGN KEY (tenant_id, channel_id) REFERENCES channels(tenant_id, id) ON DELETE RESTRICT`.
- `runtime_session_bindings_check_0`: `CHECK (audience_kind = 'personal'::text AND customer_user_id IS NOT NULL AND team_member_id IS NULL OR audience_kind = 'team'::text AND customer_user_id IS NULL AND team_member_id IS NOT NULL)`.
- `runtime_session_bindings_check_1`: `CHECK (generation > 0)`.
- `runtime_session_bindings_check_2`: `CHECK (audience_kind = ANY (ARRAY['personal'::text, 'team'::text]))`.
- `runtime_session_bindings_check_3`: `CHECK (status = ANY (ARRAY['provisioning'::text, 'active'::text, 'interrupted'::text, 'closed'::text, 'revoked'::text, 'purging'::text, 'purged'::text, 'failed'::text]))`.
- `runtime_session_bindings_customer_user_id_fk`: `FOREIGN KEY (customer_user_id) REFERENCES users(id) ON DELETE RESTRICT`.
- `runtime_session_bindings_identity_id_fk`: `FOREIGN KEY (tenant_id, identity_id) REFERENCES runtime_identities(tenant_id, id) ON DELETE RESTRICT`.
- `runtime_session_bindings_pkey`: `PRIMARY KEY (id)`.
- `runtime_session_bindings_started_by_user_id_fk`: `FOREIGN KEY (started_by_user_id) REFERENCES users(id) ON DELETE RESTRICT`.
- `runtime_session_bindings_team_member_id_fk`: `FOREIGN KEY (tenant_id, team_member_id) REFERENCES team_members(tenant_id, id) ON DELETE RESTRICT`.
- `runtime_session_bindings_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `runtime_session_bindings_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `runtime_session_bindings_unique_2`: `UNIQUE (backend_id, runtime_session_key)`.

Chỉ mục:

- `CREATE UNIQUE INDEX runtime_session_bindings_partial_0 ON public.runtime_session_bindings USING btree (tenant_id, channel_id, agent_id) WHERE ((audience_kind = 'personal'::text) AND (status = ANY (ARRAY['active'::text, 'provisioning'::text, 'interrupted'::text])))`.
- `CREATE UNIQUE INDEX runtime_session_bindings_partial_1 ON public.runtime_session_bindings USING btree (team_member_id) WHERE ((audience_kind = 'team'::text) AND (status = ANY (ARRAY['active'::text, 'provisioning'::text, 'interrupted'::text])))`.
- `CREATE UNIQUE INDEX runtime_session_bindings_pkey ON public.runtime_session_bindings USING btree (id)`.
- `CREATE UNIQUE INDEX runtime_session_bindings_tenant_key_uq ON public.runtime_session_bindings USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX runtime_session_bindings_unique_2 ON public.runtime_session_bindings USING btree (backend_id, runtime_session_key)`.

### runtime_session_operations

Nhật ký lệnh chạy resume và xóa có chống lặp

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **6/1**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `binding_id` | `uuid` | True | FK | `—` | Tham chiếu runtime_session_bindings |
| `actor_principal_id` | `uuid` | True | FK | `—` | Tham chiếu execution_principals |
| `initiated_by_user_id` | `text` | False | FK | `—` | Tham chiếu tài khoản người dùng chung của platform |
| `operation` | `text` | True | — | `—` | Lệnh runtime được cấp quyền và theo dõi |
| `idempotency_key` | `text` | True | — | `—` | Khóa chống xử lý lặp |
| `expected_generation` | `integer` | True | — | `—` | Thế hệ binding mà lệnh được phép tác động |
| `expected_lock_version` | `bigint` | True | — | `—` | Fencing version lệnh phải đối chiếu khi thực thi |
| `trigger_event_id` | `uuid` | False | FK | `—` | Tham chiếu lịch sử nghiệp vụ bất biến |
| `interrupt_id` | `text` | False | — | `—` | ID điểm dừng của runtime |
| `status` | `text` | True | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `result_run_id` | `uuid` | False | FK | `—` | Tham chiếu theo dõi thực thi xuyên framework |
| `failure_code` | `text` | False | — | `—` | Mã lỗi đã loại thông tin nhạy cảm |
| `finished_at` | `timestamp with time zone` | False | — | `—` | Thời điểm kết thúc |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |

Ràng buộc:

- `runtime_session_operations_actor_principal_id_fk`: `FOREIGN KEY (tenant_id, actor_principal_id) REFERENCES execution_principals(tenant_id, id) ON DELETE RESTRICT`.
- `runtime_session_operations_binding_id_fk`: `FOREIGN KEY (tenant_id, binding_id) REFERENCES runtime_session_bindings(tenant_id, id) ON DELETE RESTRICT`.
- `runtime_session_operations_check_0`: `CHECK (operation = ANY (ARRAY['invoke'::text, 'resume'::text, 'read'::text, 'export'::text, 'purge'::text]))`.
- `runtime_session_operations_check_1`: `CHECK (status = ANY (ARRAY['pending'::text, 'running'::text, 'succeeded'::text, 'failed'::text, 'cancelled'::text]))`.
- `runtime_session_operations_initiated_by_user_id_fk`: `FOREIGN KEY (initiated_by_user_id) REFERENCES users(id) ON DELETE RESTRICT`.
- `runtime_session_operations_pkey`: `PRIMARY KEY (id)`.
- `runtime_session_operations_result_run_id_fk`: `FOREIGN KEY (tenant_id, result_run_id) REFERENCES agent_runs(tenant_id, id) ON DELETE RESTRICT`.
- `runtime_session_operations_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `runtime_session_operations_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `runtime_session_operations_trigger_event_id_fk`: `FOREIGN KEY (tenant_id, trigger_event_id) REFERENCES ticket_events(tenant_id, id) ON DELETE RESTRICT`.
- `runtime_session_operations_unique_0`: `UNIQUE (binding_id, idempotency_key)`.

Chỉ mục:

- `CREATE UNIQUE INDEX runtime_session_operations_pkey ON public.runtime_session_operations USING btree (id)`.
- `CREATE UNIQUE INDEX runtime_session_operations_tenant_key_uq ON public.runtime_session_operations USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX runtime_session_operations_unique_0 ON public.runtime_session_operations USING btree (binding_id, idempotency_key)`.

### agent_runs

Theo dõi thực thi xuyên framework

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **11/12**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `channel_id` | `text` | True | FK | `—` | Tham chiếu cửa sổ reception hoặc groupchat quản lý |
| `agent_id` | `text` | True | FK | `—` | Tham chiếu danh mục agent của platform |
| `version_id` | `uuid` | True | FK | `—` | Tham chiếu snapshot cấu hình agent bất biến |
| `team_member_id` | `uuid` | False | FK | `—` | Tham chiếu agent và context riêng của team |
| `actor_user_id` | `text` | False | FK | `—` | Tham chiếu tài khoản người dùng chung của platform |
| `parent_run_id` | `uuid` | False | FK | `—` | Tham chiếu theo dõi thực thi xuyên framework |
| `trigger_event_id` | `uuid` | False | FK | `—` | Tham chiếu lịch sử nghiệp vụ bất biến |
| `idempotency_key` | `text` | True | — | `—` | Khóa chống xử lý lặp |
| `status` | `text` | True | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `started_at` | `timestamp with time zone` | False | — | `—` | Thời điểm bắt đầu |
| `finished_at` | `timestamp with time zone` | False | — | `—` | Thời điểm kết thúc |
| `error_code` | `text` | False | — | `—` | Mã lỗi ổn định |
| `input_tokens` | `bigint` | True | — | `0` | Số token đầu vào |
| `output_tokens` | `bigint` | True | — | `0` | Số token đầu ra |
| `estimated_cost` | `numeric(18,6)` | True | — | `'0'::numeric` | Chi phí model ước tính, không phải doanh thu sửa chữa |
| `trace_id` | `text` | True | — | `—` | ID tracing |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |
| `binding_id` | `uuid` | True | FK | `—` | Tham chiếu runtime_session_bindings |
| `authority_principal_id` | `uuid` | True | FK | `—` | Tham chiếu execution_principals |
| `on_behalf_of_user_id` | `text` | False | FK | `—` | Tham chiếu tài khoản người dùng chung của platform |
| `policy_version` | `text` | True | — | `—` | Phiên bản policy khi chọn dữ liệu |
| `authority_version` | `bigint` | True | — | `—` | Giá trị authority_version; ý nghĩa và phạm vi theo quy tắc bảng |

Ràng buộc:

- `agent_runs_actor_user_id_fk`: `FOREIGN KEY (actor_user_id) REFERENCES users(id) ON DELETE RESTRICT`.
- `agent_runs_agent_id_fk`: `FOREIGN KEY (tenant_id, agent_id) REFERENCES agents(tenant_id, id) ON DELETE RESTRICT`.
- `agent_runs_authority_principal_id_fk`: `FOREIGN KEY (tenant_id, authority_principal_id) REFERENCES execution_principals(tenant_id, id) ON DELETE RESTRICT`.
- `agent_runs_binding_id_fk`: `FOREIGN KEY (tenant_id, binding_id) REFERENCES runtime_session_bindings(tenant_id, id) ON DELETE RESTRICT`.
- `agent_runs_channel_id_fk`: `FOREIGN KEY (tenant_id, channel_id) REFERENCES channels(tenant_id, id) ON DELETE RESTRICT`.
- `agent_runs_check_0`: `CHECK (status = ANY (ARRAY['queued'::text, 'running'::text, 'interrupted'::text, 'succeeded'::text, 'failed'::text, 'cancelled'::text]))`.
- `agent_runs_on_behalf_of_user_id_fk`: `FOREIGN KEY (on_behalf_of_user_id) REFERENCES users(id) ON DELETE RESTRICT`.
- `agent_runs_parent_run_id_fk`: `FOREIGN KEY (tenant_id, parent_run_id) REFERENCES agent_runs(tenant_id, id) ON DELETE RESTRICT`.
- `agent_runs_pkey`: `PRIMARY KEY (id)`.
- `agent_runs_team_member_id_fk`: `FOREIGN KEY (tenant_id, team_member_id) REFERENCES team_members(tenant_id, id) ON DELETE RESTRICT`.
- `agent_runs_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `agent_runs_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `agent_runs_trigger_event_id_fk`: `FOREIGN KEY (tenant_id, trigger_event_id) REFERENCES ticket_events(tenant_id, id) ON DELETE RESTRICT`.
- `agent_runs_unique_0`: `UNIQUE (tenant_id, idempotency_key)`.
- `agent_runs_version_id_fk`: `FOREIGN KEY (tenant_id, version_id) REFERENCES agent_versions(tenant_id, id) ON DELETE RESTRICT`.

Chỉ mục:

- `CREATE UNIQUE INDEX agent_runs_pkey ON public.agent_runs USING btree (id)`.
- `CREATE UNIQUE INDEX agent_runs_tenant_key_uq ON public.agent_runs USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX agent_runs_unique_0 ON public.agent_runs USING btree (tenant_id, idempotency_key)`.

### context_snapshots

Context Builder có thể truy vết

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **4/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `run_id` | `uuid` | True | FK | `—` | Tham chiếu theo dõi thực thi xuyên framework |
| `requested_message_id` | `uuid` | False | FK | `—` | Tham chiếu transcript chính của room |
| `ticket_id` | `uuid` | False | FK | `—` | Tham chiếu nguồn chuẩn của yêu cầu cư dân |
| `message_ids` | `jsonb` | True | — | `—` | Danh sách message đã chọn vào context |
| `task_ids` | `jsonb` | True | — | `—` | Danh sách task đã chọn vào context |
| `retrieval_ids` | `jsonb` | True | — | `—` | Danh sách lượt retrieval tham chiếu |
| `policy_version` | `text` | True | — | `—` | Phiên bản policy khi chọn dữ liệu |
| `token_budget` | `integer` | True | — | `—` | Giới hạn token context |
| `content_hash` | `text` | True | — | `—` | Hash nội dung |
| `redacted_context` | `jsonb` | True | — | `—` | Context thực tế đã lọc quyền và PII |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |

Ràng buộc:

- `context_snapshots_pkey`: `PRIMARY KEY (id)`.
- `context_snapshots_requested_message_id_fk`: `FOREIGN KEY (tenant_id, requested_message_id) REFERENCES messages(tenant_id, id) ON DELETE RESTRICT`.
- `context_snapshots_run_id_fk`: `FOREIGN KEY (tenant_id, run_id) REFERENCES agent_runs(tenant_id, id) ON DELETE RESTRICT`.
- `context_snapshots_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `context_snapshots_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `context_snapshots_ticket_id_fk`: `FOREIGN KEY (tenant_id, ticket_id) REFERENCES tickets(tenant_id, id) ON DELETE RESTRICT`.
- `context_snapshots_unique_0`: `UNIQUE (run_id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX context_snapshots_pkey ON public.context_snapshots USING btree (id)`.
- `CREATE INDEX context_snapshots_run_id_idx ON public.context_snapshots USING btree (tenant_id, run_id)`.
- `CREATE UNIQUE INDEX context_snapshots_tenant_key_uq ON public.context_snapshots USING btree (tenant_id, id)`.
- `CREATE INDEX context_snapshots_ticket_id_idx ON public.context_snapshots USING btree (tenant_id, ticket_id)`.
- `CREATE UNIQUE INDEX context_snapshots_unique_0 ON public.context_snapshots USING btree (run_id)`.

## 05 Chat, phòng agent và Reception

### workspaces

Không gian builder và điều phối

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **1**. RLS/FORCE: **True/True**. FK ra/vào: **2/17**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `management_unit_id` | `uuid` | True | FK | `—` | Tham chiếu ban quản lý như một tổ chức |
| `code` | `text` | True | — | `—` | Mã định danh nghiệp vụ |
| `name` | `text` | True | — | `—` | Tên hiển thị |
| `status` | `text` | True | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |

Ràng buộc:

- `workspaces_management_unit_id_fk`: `FOREIGN KEY (tenant_id, management_unit_id) REFERENCES management_units(tenant_id, id) ON DELETE RESTRICT`.
- `workspaces_pkey`: `PRIMARY KEY (id)`.
- `workspaces_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `workspaces_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `workspaces_unique_0`: `UNIQUE (tenant_id, management_unit_id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX workspaces_pkey ON public.workspaces USING btree (id)`.
- `CREATE UNIQUE INDEX workspaces_tenant_key_uq ON public.workspaces USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX workspaces_unique_0 ON public.workspaces USING btree (tenant_id, management_unit_id)`.

### workspace_members

Thành viên workspace

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **1**. RLS/FORCE: **True/True**. FK ra/vào: **3/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `tenant_id` | `uuid` | True | PK/FK | `—` | Tenant sở hữu dữ liệu |
| `workspace_id` | `uuid` | True | PK/FK | `—` | Workspace của ban quản lý |
| `user_id` | `text` | True | PK/FK | `—` | Tài khoản liên quan |
| `status` | `text` | True | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `joined_at` | `timestamp with time zone` | True | — | `—` | Thời điểm gia nhập |
| `left_at` | `timestamp with time zone` | False | — | `—` | Thời điểm rời workspace |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |

Ràng buộc:

- `workspace_members_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `workspace_members_tenant_id_workspace_id_user_id_pk`: `PRIMARY KEY (tenant_id, workspace_id, user_id)`.
- `workspace_members_user_id_fk`: `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT`.
- `workspace_members_workspace_id_fk`: `FOREIGN KEY (tenant_id, workspace_id) REFERENCES workspaces(tenant_id, id) ON DELETE RESTRICT`.

Chỉ mục:

- `CREATE UNIQUE INDEX workspace_members_tenant_id_workspace_id_user_id_pk ON public.workspace_members USING btree (tenant_id, workspace_id, user_id)`.

### channels

Cửa sổ Reception hoặc groupchat quản lý

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **23**. RLS/FORCE: **True/True**. FK ra/vào: **5/16**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `text` | True | PK | `—` | Định danh bản ghi |
| `name` | `text` | True | — | `—` | Tên hiển thị |
| `description` | `text` | True | — | `—` | Mô tả |
| `suggested_prompts` | `text[]` | True | — | `'{}'::text[]` | Các câu hỏi gợi ý |
| `allowed_groups` | `text[]` | True | — | `'{}'::text[]` | Nhóm kênh legacy; không thay membership |
| `package_id` | `uuid` | False | FK | `—` | Tham chiếu gói triển khai cấu hình tenant |
| `override` | `jsonb` | False | — | `—` | Cấu hình ghi đè |
| `summary` | `text` | False | — | `—` | Tóm tắt |
| `summary_at` | `timestamp with time zone` | False | — | `—` | Thời điểm tạo tóm tắt |
| `last_message` | `text` | False | — | `—` | Bản xem trước tin nhắn gần nhất |
| `last_message_at` | `timestamp with time zone` | False | — | `—` | Thời điểm tin nhắn gần nhất |
| `last_message_agent_id` | `text` | False | FK | `—` | Tham chiếu danh mục agent của platform |
| `deleted_at` | `timestamp with time zone` | False | — | `—` | Thời điểm xóa mềm |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |
| `tenant_id` | `uuid` | True | FK | `(NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid` | Tenant sở hữu dữ liệu |
| `workspace_id` | `uuid` | False | FK | `(NULLIF(current_setting('app.workspace_id'::text, true), ''::text))::uuid` | Workspace của ban quản lý |
| `kind` | `text` | True | — | `'management'::text` | Loại bản ghi |
| `created_by` | `text` | False | FK | `—` | Tham chiếu tài khoản người dùng chung của platform |
| `is_dispatch_default` | `boolean` | True | — | `false` | Room điều phối mặc định của workspace |
| `next_message_seq` | `bigint` | True | — | `1` | Bộ đếm cấp thứ tự tin nhắn |

Ràng buộc:

- `channels_check_0`: `CHECK (kind = 'reception'::text AND workspace_id IS NULL OR (kind = ANY (ARRAY['management'::text, 'agent_builder'::text])) AND workspace_id IS NOT NULL)`.
- `channels_check_1`: `CHECK (kind = ANY (ARRAY['reception'::text, 'management'::text, 'agent_builder'::text]))`.
- `channels_created_by_fk`: `FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT`.
- `channels_last_message_agent_id_fk`: `FOREIGN KEY (tenant_id, last_message_agent_id) REFERENCES agents(tenant_id, id) ON DELETE RESTRICT`.
- `channels_package_id_fk`: `FOREIGN KEY (tenant_id, package_id) REFERENCES deployment_packages(tenant_id, id) ON DELETE RESTRICT`.
- `channels_pkey`: `PRIMARY KEY (id)`.
- `channels_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `channels_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `channels_workspace_id_fk`: `FOREIGN KEY (tenant_id, workspace_id) REFERENCES workspaces(tenant_id, id) ON DELETE RESTRICT`.

Chỉ mục:

- `CREATE UNIQUE INDEX channels_partial_0 ON public.channels USING btree (workspace_id) WHERE (is_dispatch_default AND (deleted_at IS NULL))`.
- `CREATE UNIQUE INDEX channels_pkey ON public.channels USING btree (id)`.
- `CREATE UNIQUE INDEX channels_tenant_key_uq ON public.channels USING btree (tenant_id, id)`.
- `CREATE INDEX channels_workspace_id_idx ON public.channels USING btree (tenant_id, workspace_id)`.

### channel_memberships

Thành viên và trạng thái đã đọc của kênh

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **23**. RLS/FORCE: **True/True**. FK ra/vào: **3/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `channel_id` | `text` | True | PK/FK | `—` | Tham chiếu cửa sổ reception hoặc groupchat quản lý |
| `user_id` | `text` | True | PK/FK | `—` | Tài khoản liên quan |
| `pinned_at` | `timestamp with time zone` | False | — | `—` | Thời điểm ghim |
| `last_read_at` | `timestamp with time zone` | False | — | `—` | Thời điểm đọc gần nhất |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `tenant_id` | `uuid` | True | FK | `(NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid` | Tenant sở hữu dữ liệu |
| `last_read_seq` | `bigint` | True | — | `0` | Số thứ tự tin nhắn đã đọc |

Ràng buộc:

- `channel_memberships_channel_id_fk`: `FOREIGN KEY (tenant_id, channel_id) REFERENCES channels(tenant_id, id) ON DELETE RESTRICT`.
- `channel_memberships_channel_id_user_id_pk`: `PRIMARY KEY (channel_id, user_id)`.
- `channel_memberships_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `channel_memberships_user_id_fk`: `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT`.

Chỉ mục:

- `CREATE UNIQUE INDEX channel_memberships_channel_id_user_id_pk ON public.channel_memberships USING btree (channel_id, user_id)`.

### channel_agents

Các agent được tham gia kênh

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **2**. RLS/FORCE: **True/True**. FK ra/vào: **3/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `channel_id` | `text` | True | PK/FK | `—` | Tham chiếu cửa sổ reception hoặc groupchat quản lý |
| `agent_id` | `text` | True | PK/FK | `—` | Tham chiếu danh mục agent của platform |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `tenant_id` | `uuid` | True | FK | `(NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid` | Tenant sở hữu dữ liệu |

Ràng buộc:

- `channel_agents_agent_id_fk`: `FOREIGN KEY (tenant_id, agent_id) REFERENCES agents(tenant_id, id) ON DELETE RESTRICT`.
- `channel_agents_channel_id_agent_id_pk`: `PRIMARY KEY (channel_id, agent_id)`.
- `channel_agents_channel_id_fk`: `FOREIGN KEY (tenant_id, channel_id) REFERENCES channels(tenant_id, id) ON DELETE RESTRICT`.
- `channel_agents_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.

Chỉ mục:

- `CREATE UNIQUE INDEX channel_agents_channel_id_agent_id_pk ON public.channel_agents USING btree (channel_id, agent_id)`.

### messages

Transcript chính của room

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **7/8**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `channel_id` | `text` | True | FK | `—` | Tham chiếu cửa sổ reception hoặc groupchat quản lý |
| `seq` | `bigint` | True | — | `—` | Số thứ tự trong ticket hoặc channel |
| `sender_kind` | `text` | True | — | `—` | Loại người gửi |
| `sender_user_id` | `text` | False | FK | `—` | Tham chiếu tài khoản người dùng chung của platform |
| `sender_agent_id` | `text` | False | FK | `—` | Tham chiếu danh mục agent của platform |
| `run_id` | `uuid` | False | FK | `—` | Tham chiếu theo dõi thực thi xuyên framework |
| `reply_to_id` | `uuid` | False | FK | `—` | Tham chiếu transcript chính của room |
| `visibility` | `text` | True | — | `—` | Phạm vi hiển thị |
| `body` | `jsonb` | True | — | `—` | Nội dung message có cấu trúc |
| `client_message_id` | `text` | False | — | `—` | Khóa chống gửi tin nhắn lặp từ client |
| `source_event_id` | `uuid` | False | FK | `—` | Tham chiếu lịch sử nghiệp vụ bất biến |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |

Ràng buộc:

- `messages_channel_id_fk`: `FOREIGN KEY (tenant_id, channel_id) REFERENCES channels(tenant_id, id) ON DELETE RESTRICT`.
- `messages_check_0`: `CHECK (visibility = ANY (ARRAY['room'::text, 'internal'::text, 'customer'::text]))`.
- `messages_pkey`: `PRIMARY KEY (id)`.
- `messages_reply_to_id_fk`: `FOREIGN KEY (tenant_id, reply_to_id) REFERENCES messages(tenant_id, id) ON DELETE RESTRICT`.
- `messages_run_id_fk`: `FOREIGN KEY (tenant_id, run_id) REFERENCES agent_runs(tenant_id, id) ON DELETE RESTRICT`.
- `messages_sender_agent_id_fk`: `FOREIGN KEY (tenant_id, sender_agent_id) REFERENCES agents(tenant_id, id) ON DELETE RESTRICT`.
- `messages_sender_user_id_fk`: `FOREIGN KEY (sender_user_id) REFERENCES users(id) ON DELETE RESTRICT`.
- `messages_source_event_id_fk`: `FOREIGN KEY (tenant_id, source_event_id) REFERENCES ticket_events(tenant_id, id) ON DELETE RESTRICT`.
- `messages_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `messages_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `messages_unique_0`: `UNIQUE (channel_id, seq)`.
- `messages_unique_1`: `UNIQUE (channel_id, sender_user_id, client_message_id)`.
- `messages_unique_2`: `UNIQUE (channel_id, source_event_id, sender_agent_id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX messages_pkey ON public.messages USING btree (id)`.
- `CREATE INDEX messages_run_id_idx ON public.messages USING btree (tenant_id, run_id)`.
- `CREATE UNIQUE INDEX messages_tenant_key_uq ON public.messages USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX messages_unique_0 ON public.messages USING btree (channel_id, seq)`.
- `CREATE UNIQUE INDEX messages_unique_1 ON public.messages USING btree (channel_id, sender_user_id, client_message_id)`.
- `CREATE UNIQUE INDEX messages_unique_2 ON public.messages USING btree (channel_id, source_event_id, sender_agent_id)`.

### message_mentions

Đích @agent đã phân giải

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **5/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `tenant_id` | `uuid` | True | PK/FK | `—` | Tenant sở hữu dữ liệu |
| `message_id` | `uuid` | True | PK/FK | `—` | Tham chiếu transcript chính của room |
| `agent_id` | `text` | True | PK/FK | `—` | Tham chiếu danh mục agent của platform |
| `requested_by` | `text` | True | FK | `—` | Tham chiếu tài khoản người dùng chung của platform |
| `status` | `text` | True | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `resolved_run_id` | `uuid` | False | FK | `—` | Tham chiếu theo dõi thực thi xuyên framework |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |

Ràng buộc:

- `message_mentions_agent_id_fk`: `FOREIGN KEY (tenant_id, agent_id) REFERENCES agents(tenant_id, id) ON DELETE RESTRICT`.
- `message_mentions_check_0`: `CHECK (status = ANY (ARRAY['queued'::text, 'running'::text, 'done'::text, 'failed'::text, 'refused'::text]))`.
- `message_mentions_message_id_fk`: `FOREIGN KEY (tenant_id, message_id) REFERENCES messages(tenant_id, id) ON DELETE RESTRICT`.
- `message_mentions_requested_by_fk`: `FOREIGN KEY (requested_by) REFERENCES users(id) ON DELETE RESTRICT`.
- `message_mentions_resolved_run_id_fk`: `FOREIGN KEY (tenant_id, resolved_run_id) REFERENCES agent_runs(tenant_id, id) ON DELETE RESTRICT`.
- `message_mentions_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `message_mentions_tenant_id_message_id_agent_id_pk`: `PRIMARY KEY (tenant_id, message_id, agent_id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX message_mentions_tenant_id_message_id_agent_id_pk ON public.message_mentions USING btree (tenant_id, message_id, agent_id)`.

### intelligence_channel_mappings

Ánh xạ thread Intelligence cũ

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **False/False**. FK ra/vào: **2/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `user_id` | `text` | True | PK/FK | `—` | Tài khoản liên quan |
| `channel_id` | `text` | True | PK/FK | `—` | Tham chiếu cửa sổ reception hoặc groupchat quản lý |
| `thread_id` | `text` | True | — | `—` | Định danh thread runtime |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |

Ràng buộc:

- `intelligence_channel_mappings_channel_id_fk`: `FOREIGN KEY (channel_id) REFERENCES channels(id) ON DELETE RESTRICT`.
- `intelligence_channel_mappings_unique_0`: `UNIQUE (thread_id)`.
- `intelligence_channel_mappings_user_id_channel_id_pk`: `PRIMARY KEY (user_id, channel_id)`.
- `intelligence_channel_mappings_user_id_fk`: `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT`.

Chỉ mục:

- `CREATE UNIQUE INDEX intelligence_channel_mappings_unique_0 ON public.intelligence_channel_mappings USING btree (thread_id)`.
- `CREATE UNIQUE INDEX intelligence_channel_mappings_user_id_channel_id_pk ON public.intelligence_channel_mappings USING btree (user_id, channel_id)`.

### reception_sessions

Một thread Reception mỗi cửa sổ cư dân

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **5/1**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `channel_id` | `text` | True | FK | `—` | Tham chiếu cửa sổ reception hoặc groupchat quản lý |
| `customer_user_id` | `text` | True | FK | `—` | Tham chiếu tài khoản người dùng chung của platform |
| `system_agent_id` | `text` | True | FK | `—` | Tham chiếu danh mục agent của platform |
| `workflow_version` | `text` | True | — | `—` | Phiên bản graph/workflow |
| `status` | `text` | True | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `last_event_seq` | `bigint` | True | — | `0` | Event cuối đã được ghi hoặc xử lý theo phạm vi bảng |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |
| `binding_id` | `uuid` | True | FK | `—` | Tham chiếu runtime_session_bindings |

Ràng buộc:

- `reception_sessions_binding_id_fk`: `FOREIGN KEY (tenant_id, binding_id) REFERENCES runtime_session_bindings(tenant_id, id) ON DELETE RESTRICT`.
- `reception_sessions_channel_id_fk`: `FOREIGN KEY (tenant_id, channel_id) REFERENCES channels(tenant_id, id) ON DELETE RESTRICT`.
- `reception_sessions_check_0`: `CHECK (status = ANY (ARRAY['active'::text, 'waiting'::text, 'closed'::text, 'failed'::text]))`.
- `reception_sessions_customer_user_id_fk`: `FOREIGN KEY (customer_user_id) REFERENCES users(id) ON DELETE RESTRICT`.
- `reception_sessions_pkey`: `PRIMARY KEY (id)`.
- `reception_sessions_system_agent_id_fk`: `FOREIGN KEY (tenant_id, system_agent_id) REFERENCES agents(tenant_id, id) ON DELETE RESTRICT`.
- `reception_sessions_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `reception_sessions_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `reception_sessions_unique_0`: `UNIQUE (channel_id)`.
- `reception_sessions_unique_1`: `UNIQUE (binding_id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX reception_sessions_pkey ON public.reception_sessions USING btree (id)`.
- `CREATE UNIQUE INDEX reception_sessions_tenant_key_uq ON public.reception_sessions USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX reception_sessions_unique_0 ON public.reception_sessions USING btree (channel_id)`.
- `CREATE UNIQUE INDEX reception_sessions_unique_1 ON public.reception_sessions USING btree (binding_id)`.

### reception_waits

Điểm chờ đúng ticket và interrupt

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **5/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `session_id` | `uuid` | True | FK | `—` | Tham chiếu một thread reception mỗi cửa sổ cư dân |
| `ticket_id` | `uuid` | True | FK | `—` | Tham chiếu nguồn chuẩn của yêu cầu cư dân |
| `interrupt_id` | `text` | False | — | `—` | ID điểm dừng của runtime |
| `generation` | `integer` | True | — | `—` | Thế hệ điểm chờ để chống resume cũ |
| `expected_event_types` | `text[]` | True | — | `—` | Những loại sự kiện có thể đánh thức điểm chờ |
| `after_event_seq` | `bigint` | True | — | `—` | Chỉ xét event có seq lớn hơn mốc này |
| `status` | `text` | True | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `resumed_event_id` | `uuid` | False | FK | `—` | Tham chiếu lịch sử nghiệp vụ bất biến |
| `expires_at` | `timestamp with time zone` | False | — | `—` | Thời điểm hết hạn |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |
| `operation_id` | `uuid` | False | FK | `—` | Tham chiếu runtime_session_operations |

Ràng buộc:

- `reception_waits_check_0`: `CHECK ((status <> ALL (ARRAY['open'::text, 'resuming'::text, 'consumed'::text])) OR interrupt_id IS NOT NULL)`.
- `reception_waits_operation_id_fk`: `FOREIGN KEY (tenant_id, operation_id) REFERENCES runtime_session_operations(tenant_id, id) ON DELETE RESTRICT`.
- `reception_waits_pkey`: `PRIMARY KEY (id)`.
- `reception_waits_resumed_event_id_fk`: `FOREIGN KEY (tenant_id, resumed_event_id) REFERENCES ticket_events(tenant_id, id) ON DELETE RESTRICT`.
- `reception_waits_session_id_fk`: `FOREIGN KEY (tenant_id, session_id) REFERENCES reception_sessions(tenant_id, id) ON DELETE RESTRICT`.
- `reception_waits_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `reception_waits_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `reception_waits_ticket_id_fk`: `FOREIGN KEY (tenant_id, ticket_id) REFERENCES tickets(tenant_id, id) ON DELETE RESTRICT`.
- `reception_waits_unique_0`: `UNIQUE (session_id, interrupt_id, generation)`.

Chỉ mục:

- `CREATE UNIQUE INDEX reception_waits_partial_0 ON public.reception_waits USING btree (session_id) WHERE (status = ANY (ARRAY['preparing'::text, 'open'::text, 'resuming'::text]))`.
- `CREATE UNIQUE INDEX reception_waits_pkey ON public.reception_waits USING btree (id)`.
- `CREATE UNIQUE INDEX reception_waits_tenant_key_uq ON public.reception_waits USING btree (tenant_id, id)`.
- `CREATE INDEX reception_waits_ticket_id_idx ON public.reception_waits USING btree (tenant_id, ticket_id)`.
- `CREATE UNIQUE INDEX reception_waits_unique_0 ON public.reception_waits USING btree (session_id, interrupt_id, generation)`.

### agent_teams

Một phiên cộng tác

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **7/8**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `workspace_id` | `uuid` | True | FK | `—` | Workspace của ban quản lý |
| `channel_id` | `text` | True | FK | `—` | Tham chiếu cửa sổ reception hoặc groupchat quản lý |
| `ticket_id` | `uuid` | False | FK | `—` | Tham chiếu nguồn chuẩn của yêu cầu cư dân |
| `request_message_id` | `uuid` | False | FK | `—` | Tham chiếu transcript chính của room |
| `ticket_generation` | `integer` | True | — | `0` | Lượt xử lý lại tương ứng reopen_count |
| `supervisor_agent_id` | `text` | True | FK | `—` | Tham chiếu danh mục agent của platform |
| `status` | `text` | True | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `shared_state` | `jsonb` | True | — | `—` | Trạng thái phối hợp chung của team |
| `state_version` | `bigint` | True | — | `0` | Phiên bản CAS của trạng thái |
| `finished_at` | `timestamp with time zone` | False | — | `—` | Thời điểm kết thúc |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |
| `requested_by_user_id` | `text` | False | FK | `—` | Tham chiếu tài khoản người dùng chung của platform |

Ràng buộc:

- `agent_teams_channel_id_fk`: `FOREIGN KEY (tenant_id, channel_id) REFERENCES channels(tenant_id, id) ON DELETE RESTRICT`.
- `agent_teams_check_0`: `CHECK (num_nonnulls(ticket_id, request_message_id) = 1)`.
- `agent_teams_check_1`: `CHECK (status = ANY (ARRAY['queued'::text, 'running'::text, 'waiting'::text, 'completed'::text, 'failed'::text, 'cancelled'::text]))`.
- `agent_teams_pkey`: `PRIMARY KEY (id)`.
- `agent_teams_request_message_id_fk`: `FOREIGN KEY (tenant_id, request_message_id) REFERENCES messages(tenant_id, id) ON DELETE RESTRICT`.
- `agent_teams_requested_by_user_id_fk`: `FOREIGN KEY (requested_by_user_id) REFERENCES users(id) ON DELETE RESTRICT`.
- `agent_teams_supervisor_agent_id_fk`: `FOREIGN KEY (tenant_id, supervisor_agent_id) REFERENCES agents(tenant_id, id) ON DELETE RESTRICT`.
- `agent_teams_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `agent_teams_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `agent_teams_ticket_id_fk`: `FOREIGN KEY (tenant_id, ticket_id) REFERENCES tickets(tenant_id, id) ON DELETE RESTRICT`.
- `agent_teams_unique_0`: `UNIQUE (ticket_id, ticket_generation)`.
- `agent_teams_unique_1`: `UNIQUE (workspace_id, request_message_id)`.
- `agent_teams_workspace_id_fk`: `FOREIGN KEY (tenant_id, workspace_id) REFERENCES workspaces(tenant_id, id) ON DELETE RESTRICT`.

Chỉ mục:

- `CREATE UNIQUE INDEX agent_teams_pkey ON public.agent_teams USING btree (id)`.
- `CREATE UNIQUE INDEX agent_teams_tenant_key_uq ON public.agent_teams USING btree (tenant_id, id)`.
- `CREATE INDEX agent_teams_ticket_id_idx ON public.agent_teams USING btree (tenant_id, ticket_id)`.
- `CREATE UNIQUE INDEX agent_teams_unique_0 ON public.agent_teams USING btree (ticket_id, ticket_generation)`.
- `CREATE UNIQUE INDEX agent_teams_unique_1 ON public.agent_teams USING btree (workspace_id, request_message_id)`.
- `CREATE INDEX agent_teams_workspace_id_idx ON public.agent_teams USING btree (tenant_id, workspace_id)`.

### team_members

Agent và context riêng của team

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **5/6**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `team_id` | `uuid` | True | FK | `—` | Tham chiếu một phiên cộng tác |
| `agent_id` | `text` | True | FK | `—` | Tham chiếu danh mục agent của platform |
| `version_id` | `uuid` | True | FK | `—` | Tham chiếu snapshot cấu hình agent bất biến |
| `member_kind` | `text` | True | — | `—` | Supervisor hoặc worker, không phải role người dùng |
| `status` | `text` | True | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |
| `binding_id` | `uuid` | False | FK | `—` | Tham chiếu runtime_session_bindings |

Ràng buộc:

- `team_members_agent_id_fk`: `FOREIGN KEY (tenant_id, agent_id) REFERENCES agents(tenant_id, id) ON DELETE RESTRICT`.
- `team_members_binding_id_fk`: `FOREIGN KEY (tenant_id, binding_id) REFERENCES runtime_session_bindings(tenant_id, id) ON DELETE RESTRICT`.
- `team_members_check_0`: `CHECK (status = ANY (ARRAY['provisioning'::text, 'active'::text, 'closed'::text, 'failed'::text]))`.
- `team_members_pkey`: `PRIMARY KEY (id)`.
- `team_members_team_id_fk`: `FOREIGN KEY (tenant_id, team_id) REFERENCES agent_teams(tenant_id, id) ON DELETE RESTRICT`.
- `team_members_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `team_members_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `team_members_unique_0`: `UNIQUE (team_id, agent_id)`.
- `team_members_unique_1`: `UNIQUE (binding_id)`.
- `team_members_version_id_fk`: `FOREIGN KEY (tenant_id, version_id) REFERENCES agent_versions(tenant_id, id) ON DELETE RESTRICT`.

Chỉ mục:

- `CREATE UNIQUE INDEX team_members_pkey ON public.team_members USING btree (id)`.
- `CREATE UNIQUE INDEX team_members_tenant_key_uq ON public.team_members USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX team_members_unique_0 ON public.team_members USING btree (team_id, agent_id)`.
- `CREATE UNIQUE INDEX team_members_unique_1 ON public.team_members USING btree (binding_id)`.

### team_tasks

Shared Task Board bền vững

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **5/4**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `team_id` | `uuid` | True | FK | `—` | Tham chiếu một phiên cộng tác |
| `parent_task_id` | `uuid` | False | FK | `—` | Tham chiếu shared task board bền vững |
| `ticket_id` | `uuid` | False | FK | `—` | Tham chiếu nguồn chuẩn của yêu cầu cư dân |
| `title` | `text` | True | — | `—` | Tiêu đề |
| `description` | `text` | True | — | `—` | Mô tả |
| `status` | `text` | True | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `priority` | `integer` | True | — | `0` | Mức ưu tiên hoặc trọng số xếp hàng |
| `assigned_member_id` | `uuid` | False | FK | `—` | Tham chiếu agent và context riêng của team |
| `result` | `jsonb` | False | — | `—` | Kết quả tác vụ |
| `version` | `bigint` | True | — | `0` | Phiên bản cấu hình hoặc bộ đếm chống ghi đè |
| `lease_owner` | `text` | False | — | `—` | Worker giữ lease |
| `lease_until` | `timestamp with time zone` | False | — | `—` | Thời điểm hết lease |
| `idempotency_key` | `text` | True | — | `—` | Khóa chống xử lý lặp |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |

Ràng buộc:

- `team_tasks_assigned_member_id_fk`: `FOREIGN KEY (tenant_id, assigned_member_id) REFERENCES team_members(tenant_id, id) ON DELETE RESTRICT`.
- `team_tasks_check_0`: `CHECK (status = ANY (ARRAY['pending'::text, 'ready'::text, 'running'::text, 'blocked'::text, 'done'::text, 'failed'::text, 'cancelled'::text]))`.
- `team_tasks_parent_task_id_fk`: `FOREIGN KEY (tenant_id, parent_task_id) REFERENCES team_tasks(tenant_id, id) ON DELETE RESTRICT`.
- `team_tasks_pkey`: `PRIMARY KEY (id)`.
- `team_tasks_team_id_fk`: `FOREIGN KEY (tenant_id, team_id) REFERENCES agent_teams(tenant_id, id) ON DELETE RESTRICT`.
- `team_tasks_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `team_tasks_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `team_tasks_ticket_id_fk`: `FOREIGN KEY (tenant_id, ticket_id) REFERENCES tickets(tenant_id, id) ON DELETE RESTRICT`.
- `team_tasks_unique_0`: `UNIQUE (team_id, idempotency_key)`.

Chỉ mục:

- `CREATE UNIQUE INDEX team_tasks_pkey ON public.team_tasks USING btree (id)`.
- `CREATE UNIQUE INDEX team_tasks_tenant_key_uq ON public.team_tasks USING btree (tenant_id, id)`.
- `CREATE INDEX team_tasks_ticket_id_idx ON public.team_tasks USING btree (tenant_id, ticket_id)`.
- `CREATE UNIQUE INDEX team_tasks_unique_0 ON public.team_tasks USING btree (team_id, idempotency_key)`.

### task_dependencies

Phụ thuộc giữa các task

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **3/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `tenant_id` | `uuid` | True | PK/FK | `—` | Tenant sở hữu dữ liệu |
| `task_id` | `uuid` | True | PK/FK | `—` | Tham chiếu shared task board bền vững |
| `depends_on_id` | `uuid` | True | PK/FK | `—` | Tham chiếu shared task board bền vững |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |

Ràng buộc:

- `task_dependencies_depends_on_id_fk`: `FOREIGN KEY (tenant_id, depends_on_id) REFERENCES team_tasks(tenant_id, id) ON DELETE RESTRICT`.
- `task_dependencies_task_id_fk`: `FOREIGN KEY (tenant_id, task_id) REFERENCES team_tasks(tenant_id, id) ON DELETE RESTRICT`.
- `task_dependencies_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `task_dependencies_tenant_id_task_id_depends_on_id_pk`: `PRIMARY KEY (tenant_id, task_id, depends_on_id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX task_dependencies_tenant_id_task_id_depends_on_id_pk ON public.task_dependencies USING btree (tenant_id, task_id, depends_on_id)`.

### team_mailbox

Gửi trực tiếp và broadcast

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **5/1**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `team_id` | `uuid` | True | FK | `—` | Tham chiếu một phiên cộng tác |
| `sender_member_id` | `uuid` | True | FK | `—` | Tham chiếu agent và context riêng của team |
| `recipient_member_id` | `uuid` | False | FK | `—` | Tham chiếu agent và context riêng của team |
| `task_id` | `uuid` | False | FK | `—` | Tham chiếu shared task board bền vững |
| `message_kind` | `text` | True | — | `—` | Loại thư direct/broadcast/result |
| `content` | `jsonb` | True | — | `—` | Nội dung thư có cấu trúc |
| `correlation_id` | `uuid` | True | — | `—` | ID liên kết toàn bộ luồng xử lý |
| `idempotency_key` | `text` | True | — | `—` | Khóa chống xử lý lặp |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |

Ràng buộc:

- `team_mailbox_check_0`: `CHECK (message_kind = ANY (ARRAY['direct'::text, 'broadcast'::text, 'result'::text]))`.
- `team_mailbox_pkey`: `PRIMARY KEY (id)`.
- `team_mailbox_recipient_member_id_fk`: `FOREIGN KEY (tenant_id, recipient_member_id) REFERENCES team_members(tenant_id, id) ON DELETE RESTRICT`.
- `team_mailbox_sender_member_id_fk`: `FOREIGN KEY (tenant_id, sender_member_id) REFERENCES team_members(tenant_id, id) ON DELETE RESTRICT`.
- `team_mailbox_task_id_fk`: `FOREIGN KEY (tenant_id, task_id) REFERENCES team_tasks(tenant_id, id) ON DELETE RESTRICT`.
- `team_mailbox_team_id_fk`: `FOREIGN KEY (tenant_id, team_id) REFERENCES agent_teams(tenant_id, id) ON DELETE RESTRICT`.
- `team_mailbox_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `team_mailbox_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `team_mailbox_unique_0`: `UNIQUE (team_id, idempotency_key)`.

Chỉ mục:

- `CREATE UNIQUE INDEX team_mailbox_pkey ON public.team_mailbox USING btree (id)`.
- `CREATE UNIQUE INDEX team_mailbox_tenant_key_uq ON public.team_mailbox USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX team_mailbox_unique_0 ON public.team_mailbox USING btree (team_id, idempotency_key)`.

### mailbox_deliveries

Trạng thái nhận theo từng agent

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **3/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `mailbox_id` | `uuid` | True | FK | `—` | Tham chiếu gửi trực tiếp và broadcast |
| `recipient_member_id` | `uuid` | True | FK | `—` | Tham chiếu agent và context riêng của team |
| `status` | `text` | True | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `attempts` | `integer` | True | — | `0` | Số lần thử |
| `available_at` | `timestamp with time zone` | True | — | `—` | Thời điểm có thể xử lý |
| `ack_at` | `timestamp with time zone` | False | — | `—` | Thời điểm xác nhận đã nhận |
| `last_error` | `text` | False | — | `—` | Lỗi cuối đã lọc dữ liệu nhạy cảm |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |

Ràng buộc:

- `mailbox_deliveries_check_0`: `CHECK (status = ANY (ARRAY['pending'::text, 'delivered'::text, 'acked'::text, 'dead'::text]))`.
- `mailbox_deliveries_mailbox_id_fk`: `FOREIGN KEY (tenant_id, mailbox_id) REFERENCES team_mailbox(tenant_id, id) ON DELETE RESTRICT`.
- `mailbox_deliveries_pkey`: `PRIMARY KEY (id)`.
- `mailbox_deliveries_recipient_member_id_fk`: `FOREIGN KEY (tenant_id, recipient_member_id) REFERENCES team_members(tenant_id, id) ON DELETE RESTRICT`.
- `mailbox_deliveries_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `mailbox_deliveries_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `mailbox_deliveries_unique_0`: `UNIQUE (mailbox_id, recipient_member_id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX mailbox_deliveries_pkey ON public.mailbox_deliveries USING btree (id)`.
- `CREATE UNIQUE INDEX mailbox_deliveries_tenant_key_uq ON public.mailbox_deliveries USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX mailbox_deliveries_unique_0 ON public.mailbox_deliveries USING btree (mailbox_id, recipient_member_id)`.

### vh_reception_supervisor_messages

Extension được tạo bằng migration SQL; xem định nghĩa cột và FK bên dưới.

Migration tạo: `0007_reception_supervisor_v2.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **5/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | — |
| `tenant_id` | `uuid` | True | FK | `—` | — |
| `direction` | `text` | True | — | `—` | — |
| `message_id` | `text` | True | — | `—` | — |
| `correlation_id` | `text` | True | — | `—` | — |
| `ticket_id` | `uuid` | True | FK | `—` | — |
| `team_id` | `uuid` | True | FK | `—` | — |
| `ticket_generation` | `integer` | True | — | `—` | — |
| `message_type` | `text` | True | — | `—` | — |
| `payload` | `jsonb` | True | — | `—` | — |
| `payload_hash` | `text` | True | — | `—` | — |
| `response_body` | `jsonb` | True | — | `—` | — |
| `created_by` | `text` | False | FK | `—` | — |
| `created_at` | `timestamp with time zone` | True | — | `now()` | — |
| `created_by_agent_id` | `text` | False | FK | `—` | — |

Ràng buộc:

- `vh_reception_supervisor_messages_author_check`: `CHECK (num_nonnulls(created_by, created_by_agent_id) = 1)`.
- `vh_reception_supervisor_messages_correlation_id_check`: `CHECK (length(correlation_id) >= 1 AND length(correlation_id) <= 200)`.
- `vh_reception_supervisor_messages_created_by_agent_fk`: `FOREIGN KEY (tenant_id, created_by_agent_id) REFERENCES agents(tenant_id, id) ON DELETE RESTRICT`.
- `vh_reception_supervisor_messages_created_by_fk`: `FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT`.
- `vh_reception_supervisor_messages_direction_check`: `CHECK (direction = ANY (ARRAY['reception_to_supervisor'::text, 'supervisor_to_reception'::text]))`.
- `vh_reception_supervisor_messages_generation_check`: `CHECK (ticket_generation >= 0)`.
- `vh_reception_supervisor_messages_hash_check`: `CHECK (payload_hash ~ '^[0-9a-f]{64}$'::text)`.
- `vh_reception_supervisor_messages_message_id_check`: `CHECK (length(message_id) >= 1 AND length(message_id) <= 200)`.
- `vh_reception_supervisor_messages_message_id_uq`: `UNIQUE (tenant_id, message_id)`.
- `vh_reception_supervisor_messages_payload_check`: `CHECK (jsonb_typeof(payload) = 'object'::text)`.
- `vh_reception_supervisor_messages_pkey`: `PRIMARY KEY (id)`.
- `vh_reception_supervisor_messages_response_check`: `CHECK (jsonb_typeof(response_body) = 'object'::text)`.
- `vh_reception_supervisor_messages_team_id_fk`: `FOREIGN KEY (tenant_id, team_id) REFERENCES agent_teams(tenant_id, id) ON DELETE RESTRICT`.
- `vh_reception_supervisor_messages_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `vh_reception_supervisor_messages_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `vh_reception_supervisor_messages_ticket_id_fk`: `FOREIGN KEY (tenant_id, ticket_id) REFERENCES tickets(tenant_id, id) ON DELETE RESTRICT`.
- `vh_reception_supervisor_messages_type_check`: `CHECK (direction = 'reception_to_supervisor'::text AND (message_type = ANY (ARRAY['ticket_submitted'::text, 'information_provided'::text, 'plan_approved'::text, 'plan_rejected'::text, 'plan_change_requested'::text, 'cancel_requested'::text])) OR direction = 'supervisor_to_reception'::text AND (message_type = ANY (ARRAY['accepted'::text, 'in_progress'::text, 'information_requested'::text, 'plan_approval_requested'::text, 'completed'::text, 'failed'::text, 'cancelled'::text])))`.

Chỉ mục:

- `CREATE UNIQUE INDEX vh_reception_supervisor_messages_message_id_uq ON public.vh_reception_supervisor_messages USING btree (tenant_id, message_id)`.
- `CREATE UNIQUE INDEX vh_reception_supervisor_messages_pkey ON public.vh_reception_supervisor_messages USING btree (id)`.
- `CREATE INDEX vh_reception_supervisor_messages_team_page_idx ON public.vh_reception_supervisor_messages USING btree (tenant_id, team_id, created_at DESC, id DESC)`.
- `CREATE UNIQUE INDEX vh_reception_supervisor_messages_tenant_key_uq ON public.vh_reception_supervisor_messages USING btree (tenant_id, id)`.
- `CREATE INDEX vh_reception_supervisor_messages_ticket_page_idx ON public.vh_reception_supervisor_messages USING btree (tenant_id, ticket_id, ticket_generation, created_at DESC, id DESC)`.

### vh_reception_supervisor_pending

Extension được tạo bằng migration SQL; xem định nghĩa cột và FK bên dưới.

Migration tạo: `0007_reception_supervisor_v2.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **4/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `tenant_id` | `uuid` | True | PK/FK | `—` | — |
| `ticket_id` | `uuid` | True | PK/FK | `—` | — |
| `team_id` | `uuid` | True | FK | `—` | — |
| `ticket_generation` | `integer` | True | PK | `—` | — |
| `correlation_id` | `text` | True | — | `—` | — |
| `pending_kind` | `text` | True | — | `—` | — |
| `supervisor_message_id` | `text` | True | — | `—` | — |
| `plan_id` | `uuid` | False | FK | `—` | — |
| `plan_version` | `bigint` | False | — | `—` | — |
| `created_at` | `timestamp with time zone` | True | — | `now()` | — |

Ràng buộc:

- `vh_reception_supervisor_pending_correlation_check`: `CHECK (length(correlation_id) >= 1 AND length(correlation_id) <= 200)`.
- `vh_reception_supervisor_pending_generation_check`: `CHECK (ticket_generation >= 0)`.
- `vh_reception_supervisor_pending_kind_check`: `CHECK (pending_kind = ANY (ARRAY['information'::text, 'plan_approval'::text]))`.
- `vh_reception_supervisor_pending_message_uq`: `UNIQUE (tenant_id, supervisor_message_id)`.
- `vh_reception_supervisor_pending_pk`: `PRIMARY KEY (tenant_id, ticket_id, ticket_generation)`.
- `vh_reception_supervisor_pending_plan_check`: `CHECK (pending_kind = 'information'::text AND plan_id IS NULL AND plan_version IS NULL OR pending_kind = 'plan_approval'::text AND plan_id IS NOT NULL AND plan_version IS NOT NULL)`.
- `vh_reception_supervisor_pending_plan_id_fk`: `FOREIGN KEY (tenant_id, plan_id) REFERENCES vh_ticket_plans(tenant_id, id) ON DELETE RESTRICT`.
- `vh_reception_supervisor_pending_team_id_fk`: `FOREIGN KEY (tenant_id, team_id) REFERENCES agent_teams(tenant_id, id) ON DELETE RESTRICT`.
- `vh_reception_supervisor_pending_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `vh_reception_supervisor_pending_ticket_id_fk`: `FOREIGN KEY (tenant_id, ticket_id) REFERENCES tickets(tenant_id, id) ON DELETE RESTRICT`.

Chỉ mục:

- `CREATE UNIQUE INDEX vh_reception_supervisor_pending_message_uq ON public.vh_reception_supervisor_pending USING btree (tenant_id, supervisor_message_id)`.
- `CREATE UNIQUE INDEX vh_reception_supervisor_pending_pk ON public.vh_reception_supervisor_pending USING btree (tenant_id, ticket_id, ticket_generation)`.
- `CREATE INDEX vh_reception_supervisor_pending_team_idx ON public.vh_reception_supervisor_pending USING btree (tenant_id, team_id, created_at DESC)`.

## 06 RAG và memory

### knowledge_bases

Bộ sưu tập tri thức

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **2**. RLS/FORCE: **True/True**. FK ra/vào: **2/3**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `domain_id` | `uuid` | True | FK | `—` | Tham chiếu miền nghiệp vụ có thể cấu hình |
| `code` | `text` | True | — | `—` | Mã định danh nghiệp vụ |
| `name` | `text` | True | — | `—` | Tên hiển thị |
| `description` | `text` | False | — | `—` | Mô tả |
| `status` | `text` | True | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |

Ràng buộc:

- `knowledge_bases_check_0`: `CHECK (status = ANY (ARRAY['active'::text, 'archived'::text]))`.
- `knowledge_bases_domain_id_fk`: `FOREIGN KEY (tenant_id, domain_id) REFERENCES domains(tenant_id, id) ON DELETE RESTRICT`.
- `knowledge_bases_pkey`: `PRIMARY KEY (id)`.
- `knowledge_bases_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `knowledge_bases_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `knowledge_bases_unique_0`: `UNIQUE (tenant_id, code)`.

Chỉ mục:

- `CREATE UNIQUE INDEX knowledge_bases_pkey ON public.knowledge_bases USING btree (id)`.
- `CREATE UNIQUE INDEX knowledge_bases_tenant_key_uq ON public.knowledge_bases USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX knowledge_bases_unique_0 ON public.knowledge_bases USING btree (tenant_id, code)`.

### knowledge_categories

Loại tài liệu cho key search

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **1**. RLS/FORCE: **True/True**. FK ra/vào: **2/2**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `code` | `text` | True | — | `—` | Mã định danh nghiệp vụ |
| `name` | `text` | True | — | `—` | Tên hiển thị |
| `parent_id` | `uuid` | False | FK | `—` | Tham chiếu loại tài liệu cho key search |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |

Ràng buộc:

- `knowledge_categories_parent_id_fk`: `FOREIGN KEY (tenant_id, parent_id) REFERENCES knowledge_categories(tenant_id, id) ON DELETE RESTRICT`.
- `knowledge_categories_pkey`: `PRIMARY KEY (id)`.
- `knowledge_categories_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `knowledge_categories_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `knowledge_categories_unique_0`: `UNIQUE (tenant_id, code)`.

Chỉ mục:

- `CREATE UNIQUE INDEX knowledge_categories_pkey ON public.knowledge_categories USING btree (id)`.
- `CREATE UNIQUE INDEX knowledge_categories_tenant_key_uq ON public.knowledge_categories USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX knowledge_categories_unique_0 ON public.knowledge_categories USING btree (tenant_id, code)`.

### knowledge_documents

Định danh tài liệu và chủ quản

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **116**. RLS/FORCE: **True/True**. FK ra/vào: **6/5**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `knowledge_base_id` | `uuid` | True | FK | `—` | Tham chiếu bộ sưu tập tri thức |
| `category_id` | `uuid` | True | FK | `—` | Tham chiếu loại tài liệu cho key search |
| `code` | `text` | True | — | `—` | Mã định danh nghiệp vụ |
| `title` | `text` | True | — | `—` | Tiêu đề |
| `owner_management_id` | `uuid` | False | FK | `—` | Tham chiếu ban quản lý như một tổ chức |
| `status` | `text` | True | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `language` | `text` | True | — | `'vi'::text` | Ngôn ngữ tài liệu |
| `active_version_id` | `uuid` | False | FK | `—` | Tham chiếu nội dung tài liệu có phiên bản |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |
| `memory_namespace_id` | `uuid` | False | FK | `—` | Tham chiếu memory_namespaces |

Ràng buộc:

- `knowledge_documents_active_version_id_fk`: `FOREIGN KEY (tenant_id, active_version_id) REFERENCES document_versions(tenant_id, id) ON DELETE RESTRICT`.
- `knowledge_documents_category_id_fk`: `FOREIGN KEY (tenant_id, category_id) REFERENCES knowledge_categories(tenant_id, id) ON DELETE RESTRICT`.
- `knowledge_documents_check_0`: `CHECK (status = ANY (ARRAY['draft'::text, 'published'::text, 'archived'::text]))`.
- `knowledge_documents_knowledge_base_id_fk`: `FOREIGN KEY (tenant_id, knowledge_base_id) REFERENCES knowledge_bases(tenant_id, id) ON DELETE RESTRICT`.
- `knowledge_documents_memory_namespace_id_fk`: `FOREIGN KEY (tenant_id, memory_namespace_id) REFERENCES memory_namespaces(tenant_id, id) ON DELETE RESTRICT`.
- `knowledge_documents_owner_management_id_fk`: `FOREIGN KEY (tenant_id, owner_management_id) REFERENCES management_units(tenant_id, id) ON DELETE RESTRICT`.
- `knowledge_documents_pkey`: `PRIMARY KEY (id)`.
- `knowledge_documents_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `knowledge_documents_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `knowledge_documents_unique_0`: `UNIQUE (knowledge_base_id, code)`.

Chỉ mục:

- `CREATE UNIQUE INDEX knowledge_documents_pkey ON public.knowledge_documents USING btree (id)`.
- `CREATE UNIQUE INDEX knowledge_documents_tenant_key_uq ON public.knowledge_documents USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX knowledge_documents_unique_0 ON public.knowledge_documents USING btree (knowledge_base_id, code)`.

### document_versions

Nội dung tài liệu có phiên bản

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **115**. RLS/FORCE: **True/True**. FK ra/vào: **4/5**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `document_id` | `uuid` | True | FK | `—` | Tham chiếu định danh tài liệu và chủ quản |
| `version_no` | `integer` | True | — | `—` | Số phiên bản tăng dần |
| `file_id` | `uuid` | True | FK | `—` | Tham chiếu metadata file dùng chung |
| `content_hash` | `text` | True | — | `—` | Hash nội dung |
| `effective_from` | `timestamp with time zone` | True | — | `—` | Bắt đầu áp dụng |
| `effective_to` | `timestamp with time zone` | False | — | `—` | Kết thúc áp dụng |
| `submitted_by` | `text` | True | FK | `—` | Tham chiếu tài khoản người dùng chung của platform |
| `extraction_config` | `jsonb` | True | — | `—` | Cấu hình trích xuất |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |

Ràng buộc:

- `document_versions_document_id_fk`: `FOREIGN KEY (tenant_id, document_id) REFERENCES knowledge_documents(tenant_id, id) ON DELETE RESTRICT`.
- `document_versions_file_id_fk`: `FOREIGN KEY (tenant_id, file_id) REFERENCES files(tenant_id, id) ON DELETE RESTRICT`.
- `document_versions_pkey`: `PRIMARY KEY (id)`.
- `document_versions_submitted_by_fk`: `FOREIGN KEY (submitted_by) REFERENCES users(id) ON DELETE RESTRICT`.
- `document_versions_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `document_versions_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `document_versions_unique_0`: `UNIQUE (document_id, version_no)`.

Chỉ mục:

- `CREATE UNIQUE INDEX document_versions_pkey ON public.document_versions USING btree (id)`.
- `CREATE UNIQUE INDEX document_versions_tenant_key_uq ON public.document_versions USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX document_versions_unique_0 ON public.document_versions USING btree (document_id, version_no)`.

### document_scopes

Metadata phạm vi truy hồi trước semantic

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **127**. RLS/FORCE: **True/True**. FK ra/vào: **3/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `tenant_id` | `uuid` | True | PK/FK | `—` | Tenant sở hữu dữ liệu |
| `document_id` | `uuid` | True | PK/FK | `—` | Tham chiếu định danh tài liệu và chủ quản |
| `scope_id` | `uuid` | True | PK/FK | `—` | Tham chiếu phạm vi quyền có kiểu rõ ràng |
| `applies_to_descendants` | `boolean` | True | — | `true` | Cho phép tài liệu áp dụng xuống địa bàn con |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |

Ràng buộc:

- `document_scopes_document_id_fk`: `FOREIGN KEY (tenant_id, document_id) REFERENCES knowledge_documents(tenant_id, id) ON DELETE RESTRICT`.
- `document_scopes_scope_id_fk`: `FOREIGN KEY (tenant_id, scope_id) REFERENCES access_scopes(tenant_id, id) ON DELETE RESTRICT`.
- `document_scopes_tenant_id_document_id_scope_id_pk`: `PRIMARY KEY (tenant_id, document_id, scope_id)`.
- `document_scopes_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.

Chỉ mục:

- `CREATE UNIQUE INDEX document_scopes_tenant_id_document_id_scope_id_pk ON public.document_scopes USING btree (tenant_id, document_id, scope_id)`.

### document_acl

Đối tượng được đọc tài liệu

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **4/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `document_id` | `uuid` | True | FK | `—` | Tham chiếu định danh tài liệu và chủ quản |
| `principal_kind` | `text` | True | — | `—` | Loại chủ thể được cấp hoặc từ chối quyền |
| `role_code` | `text` | False | — | `—` | Mã vai trò nghiệp vụ trong scope |
| `user_id` | `text` | False | FK | `—` | Tài khoản liên quan |
| `workspace_id` | `uuid` | False | FK | `—` | Workspace của ban quản lý |
| `effect` | `text` | True | — | `'allow'::text` | allow hoặc deny đối với ACL; tác động công cụ đối với MCP |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |

Ràng buộc:

- `document_acl_check_0`: `CHECK (principal_kind = ANY (ARRAY['role'::text, 'user'::text, 'workspace'::text]))`.
- `document_acl_check_1`: `CHECK (effect = ANY (ARRAY['allow'::text, 'deny'::text]))`.
- `document_acl_document_id_fk`: `FOREIGN KEY (tenant_id, document_id) REFERENCES knowledge_documents(tenant_id, id) ON DELETE RESTRICT`.
- `document_acl_pkey`: `PRIMARY KEY (id)`.
- `document_acl_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `document_acl_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `document_acl_user_id_fk`: `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT`.
- `document_acl_workspace_id_fk`: `FOREIGN KEY (tenant_id, workspace_id) REFERENCES workspaces(tenant_id, id) ON DELETE RESTRICT`.

Chỉ mục:

- `CREATE UNIQUE INDEX document_acl_pkey ON public.document_acl USING btree (id)`.
- `CREATE UNIQUE INDEX document_acl_tenant_key_uq ON public.document_acl USING btree (tenant_id, id)`.
- `CREATE INDEX document_acl_user_id_idx ON public.document_acl USING btree (tenant_id, user_id)`.
- `CREATE INDEX document_acl_workspace_id_idx ON public.document_acl USING btree (tenant_id, workspace_id)`.

### knowledge_reviews

Duyệt tài liệu và tri thức học được

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **3**. RLS/FORCE: **True/True**. FK ra/vào: **4/1**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `document_version_id` | `uuid` | False | FK | `—` | Tham chiếu nội dung tài liệu có phiên bản |
| `memory_candidate_id` | `uuid` | False | FK | `—` | Tham chiếu tri thức rút ra cần admin duyệt |
| `decision` | `text` | True | — | `—` | Quyết định duyệt |
| `reviewer_user_id` | `text` | True | FK | `—` | Tham chiếu tài khoản người dùng chung của platform |
| `reason` | `text` | False | — | `—` | Lý do |
| `reviewed_at` | `timestamp with time zone` | True | — | `—` | Thời điểm duyệt |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `subject_seq` | `bigint` | True | — | `—` | Số thứ tự quyết định được cấp dưới khóa đối tượng |
| `subject_hash` | `text` | True | — | `—` | Hash phiên bản nội dung mà quyết định áp dụng |

Ràng buộc:

- `knowledge_reviews_check_0`: `CHECK (num_nonnulls(document_version_id, memory_candidate_id) = 1)`.
- `knowledge_reviews_check_1`: `CHECK (decision = ANY (ARRAY['approve'::text, 'reject'::text, 'revoke'::text]))`.
- `knowledge_reviews_document_version_id_fk`: `FOREIGN KEY (tenant_id, document_version_id) REFERENCES document_versions(tenant_id, id) ON DELETE RESTRICT`.
- `knowledge_reviews_memory_candidate_id_fk`: `FOREIGN KEY (tenant_id, memory_candidate_id) REFERENCES memory_candidates(tenant_id, id) ON DELETE RESTRICT`.
- `knowledge_reviews_pkey`: `PRIMARY KEY (id)`.
- `knowledge_reviews_reviewer_user_id_fk`: `FOREIGN KEY (reviewer_user_id) REFERENCES users(id) ON DELETE RESTRICT`.
- `knowledge_reviews_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `knowledge_reviews_tenant_key_uq`: `UNIQUE (tenant_id, id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX knowledge_reviews_partial_0 ON public.knowledge_reviews USING btree (document_version_id, subject_seq) WHERE (document_version_id IS NOT NULL)`.
- `CREATE UNIQUE INDEX knowledge_reviews_partial_1 ON public.knowledge_reviews USING btree (memory_candidate_id, subject_seq) WHERE (memory_candidate_id IS NOT NULL)`.
- `CREATE UNIQUE INDEX knowledge_reviews_pkey ON public.knowledge_reviews USING btree (id)`.
- `CREATE UNIQUE INDEX knowledge_reviews_tenant_key_uq ON public.knowledge_reviews USING btree (tenant_id, id)`.

### ingestion_jobs

Pipeline parse chunk embed có retry

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **115**. RLS/FORCE: **True/True**. FK ra/vào: **3/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `version_id` | `uuid` | True | FK | `—` | Tham chiếu nội dung tài liệu có phiên bản |
| `embedding_model_id` | `uuid` | True | FK | `—` | Tham chiếu không gian vector có định danh |
| `status` | `text` | True | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `idempotency_key` | `text` | True | — | `—` | Khóa chống xử lý lặp |
| `parser_version` | `text` | True | — | `—` | Phiên bản parser |
| `chunker_version` | `text` | True | — | `—` | Phiên bản chunker |
| `attempts` | `integer` | True | — | `0` | Số lần thử |
| `lease_owner` | `text` | False | — | `—` | Worker giữ lease |
| `lease_until` | `timestamp with time zone` | False | — | `—` | Thời điểm hết lease |
| `expected_chunks` | `integer` | False | — | `—` | Số chunk kỳ vọng |
| `completed_chunks` | `integer` | True | — | `0` | Số chunk đã xử lý |
| `error_code` | `text` | False | — | `—` | Mã lỗi ổn định |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |

Ràng buộc:

- `ingestion_jobs_check_0`: `CHECK (status = ANY (ARRAY['queued'::text, 'parsing'::text, 'embedding'::text, 'completed'::text, 'failed'::text, 'cancelled'::text]))`.
- `ingestion_jobs_embedding_model_id_fk`: `FOREIGN KEY (embedding_model_id) REFERENCES embedding_models(id) ON DELETE RESTRICT`.
- `ingestion_jobs_pkey`: `PRIMARY KEY (id)`.
- `ingestion_jobs_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `ingestion_jobs_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `ingestion_jobs_unique_0`: `UNIQUE (tenant_id, idempotency_key)`.
- `ingestion_jobs_version_id_fk`: `FOREIGN KEY (tenant_id, version_id) REFERENCES document_versions(tenant_id, id) ON DELETE RESTRICT`.

Chỉ mục:

- `CREATE UNIQUE INDEX ingestion_jobs_pkey ON public.ingestion_jobs USING btree (id)`.
- `CREATE UNIQUE INDEX ingestion_jobs_tenant_key_uq ON public.ingestion_jobs USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX ingestion_jobs_unique_0 ON public.ingestion_jobs USING btree (tenant_id, idempotency_key)`.

### knowledge_chunks

Nội dung đoạn và vị trí trích dẫn

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **279**. RLS/FORCE: **True/True**. FK ra/vào: **2/2**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `version_id` | `uuid` | True | FK | `—` | Tham chiếu nội dung tài liệu có phiên bản |
| `ordinal` | `integer` | True | — | `—` | Thứ tự |
| `text_content` | `text` | True | — | `—` | Nội dung đoạn tài liệu |
| `text_hash` | `text` | True | — | `—` | Hash đoạn văn |
| `token_count` | `integer` | True | — | `—` | Số token |
| `page_start` | `integer` | False | — | `—` | Trang bắt đầu |
| `page_end` | `integer` | False | — | `—` | Trang kết thúc |
| `heading_path` | `text` | False | — | `—` | Đường dẫn tiêu đề trong nguồn |
| `search_tsv` | `tsvector` | True | — | `—` | Chỉ mục tìm kiếm từ khóa |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |

Ràng buộc:

- `knowledge_chunks_pkey`: `PRIMARY KEY (id)`.
- `knowledge_chunks_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `knowledge_chunks_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `knowledge_chunks_unique_0`: `UNIQUE (version_id, ordinal)`.
- `knowledge_chunks_version_id_fk`: `FOREIGN KEY (tenant_id, version_id) REFERENCES document_versions(tenant_id, id) ON DELETE RESTRICT`.

Chỉ mục:

- `CREATE UNIQUE INDEX knowledge_chunks_pkey ON public.knowledge_chunks USING btree (id)`.
- `CREATE INDEX knowledge_chunks_search_idx ON public.knowledge_chunks USING gin (search_tsv)`.
- `CREATE UNIQUE INDEX knowledge_chunks_tenant_key_uq ON public.knowledge_chunks USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX knowledge_chunks_unique_0 ON public.knowledge_chunks USING btree (version_id, ordinal)`.

### embedding_models

Không gian vector có định danh

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **1**. RLS/FORCE: **False/False**. FK ra/vào: **0/3**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `provider` | `text` | True | — | `—` | Nhà cung cấp dịch vụ |
| `model_name` | `text` | True | — | `—` | Tên model |
| `model_revision` | `text` | True | — | `—` | Phiên bản model embedding |
| `dimension` | `integer` | True | — | `—` | Số chiều embedding |
| `distance_metric` | `text` | True | — | `—` | Phép đo khoảng cách |
| `active` | `boolean` | True | — | `true` | Có đang hoạt động |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |

Ràng buộc:

- `embedding_models_pkey`: `PRIMARY KEY (id)`.
- `embedding_models_unique_0`: `UNIQUE (provider, model_name, model_revision, dimension)`.

Chỉ mục:

- `CREATE UNIQUE INDEX embedding_models_pkey ON public.embedding_models USING btree (id)`.
- `CREATE UNIQUE INDEX embedding_models_unique_0 ON public.embedding_models USING btree (provider, model_name, model_revision, dimension)`.

### knowledge_embeddings

Bảng vector chung duy nhất

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **279**. RLS/FORCE: **True/True**. FK ra/vào: **3/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `chunk_id` | `uuid` | True | FK | `—` | Tham chiếu nội dung đoạn và vị trí trích dẫn |
| `model_id` | `uuid` | True | FK | `—` | Tham chiếu không gian vector có định danh |
| `embedding` | `vector(1536)` | True | — | `—` | Vector biểu diễn nội dung |
| `content_hash` | `text` | True | — | `—` | Hash nội dung |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |

Ràng buộc:

- `knowledge_embeddings_chunk_id_fk`: `FOREIGN KEY (tenant_id, chunk_id) REFERENCES knowledge_chunks(tenant_id, id) ON DELETE RESTRICT`.
- `knowledge_embeddings_model_id_fk`: `FOREIGN KEY (model_id) REFERENCES embedding_models(id) ON DELETE RESTRICT`.
- `knowledge_embeddings_pkey`: `PRIMARY KEY (id)`.
- `knowledge_embeddings_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `knowledge_embeddings_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `knowledge_embeddings_unique_0`: `UNIQUE (chunk_id, model_id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX knowledge_embeddings_pkey ON public.knowledge_embeddings USING btree (id)`.
- `CREATE UNIQUE INDEX knowledge_embeddings_tenant_key_uq ON public.knowledge_embeddings USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX knowledge_embeddings_unique_0 ON public.knowledge_embeddings USING btree (chunk_id, model_id)`.

### retrieval_runs

Truy vết một lần RAG

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **7/1**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `agent_run_id` | `uuid` | True | FK | `—` | Tham chiếu theo dõi thực thi xuyên framework |
| `actor_user_id` | `text` | False | FK | `—` | Tham chiếu tài khoản người dùng chung của platform |
| `knowledge_base_id` | `uuid` | True | FK | `—` | Tham chiếu bộ sưu tập tri thức |
| `model_id` | `uuid` | True | FK | `—` | Tham chiếu không gian vector có định danh |
| `query_text_redacted` | `text` | True | — | `—` | Câu truy vấn đã loại PII |
| `metadata_filter` | `jsonb` | True | — | `—` | Bộ lọc metadata đã xác thực |
| `authorized_document_ids` | `jsonb` | True | — | `—` | Tập tài liệu được phép truy hồi |
| `top_k` | `integer` | True | — | `—` | Số kết quả tối đa |
| `policy_version` | `text` | True | — | `—` | Phiên bản policy khi chọn dữ liệu |
| `latency_ms` | `integer` | True | — | `—` | Độ trễ mili giây |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `principal_id` | `uuid` | True | FK | `—` | Tham chiếu execution_principals |
| `binding_id` | `uuid` | True | FK | `—` | Tham chiếu runtime_session_bindings |

Ràng buộc:

- `retrieval_runs_actor_user_id_fk`: `FOREIGN KEY (actor_user_id) REFERENCES users(id) ON DELETE RESTRICT`.
- `retrieval_runs_agent_run_id_fk`: `FOREIGN KEY (tenant_id, agent_run_id) REFERENCES agent_runs(tenant_id, id) ON DELETE RESTRICT`.
- `retrieval_runs_binding_id_fk`: `FOREIGN KEY (tenant_id, binding_id) REFERENCES runtime_session_bindings(tenant_id, id) ON DELETE RESTRICT`.
- `retrieval_runs_knowledge_base_id_fk`: `FOREIGN KEY (tenant_id, knowledge_base_id) REFERENCES knowledge_bases(tenant_id, id) ON DELETE RESTRICT`.
- `retrieval_runs_model_id_fk`: `FOREIGN KEY (model_id) REFERENCES embedding_models(id) ON DELETE RESTRICT`.
- `retrieval_runs_pkey`: `PRIMARY KEY (id)`.
- `retrieval_runs_principal_id_fk`: `FOREIGN KEY (tenant_id, principal_id) REFERENCES execution_principals(tenant_id, id) ON DELETE RESTRICT`.
- `retrieval_runs_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `retrieval_runs_tenant_key_uq`: `UNIQUE (tenant_id, id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX retrieval_runs_pkey ON public.retrieval_runs USING btree (id)`.
- `CREATE UNIQUE INDEX retrieval_runs_tenant_key_uq ON public.retrieval_runs USING btree (tenant_id, id)`.

### retrieval_hits

Nguồn đoạn đã đưa vào context

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **3/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `tenant_id` | `uuid` | True | PK/FK | `—` | Tenant sở hữu dữ liệu |
| `retrieval_run_id` | `uuid` | True | PK/FK | `—` | Tham chiếu truy vết một lần rag |
| `chunk_id` | `uuid` | True | PK/FK | `—` | Tham chiếu nội dung đoạn và vị trí trích dẫn |
| `rank` | `integer` | True | — | `—` | Thứ hạng retrieval |
| `similarity` | `numeric(9,6)` | True | — | `—` | Điểm tương đồng |
| `included` | `boolean` | True | — | `—` | Có được đưa vào context |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |

Ràng buộc:

- `retrieval_hits_chunk_id_fk`: `FOREIGN KEY (tenant_id, chunk_id) REFERENCES knowledge_chunks(tenant_id, id) ON DELETE RESTRICT`.
- `retrieval_hits_retrieval_run_id_fk`: `FOREIGN KEY (tenant_id, retrieval_run_id) REFERENCES retrieval_runs(tenant_id, id) ON DELETE RESTRICT`.
- `retrieval_hits_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `retrieval_hits_tenant_id_retrieval_run_id_chunk_id_pk`: `PRIMARY KEY (tenant_id, retrieval_run_id, chunk_id)`.
- `retrieval_hits_unique_0`: `UNIQUE (retrieval_run_id, rank)`.

Chỉ mục:

- `CREATE UNIQUE INDEX retrieval_hits_tenant_id_retrieval_run_id_chunk_id_pk ON public.retrieval_hits USING btree (tenant_id, retrieval_run_id, chunk_id)`.
- `CREATE UNIQUE INDEX retrieval_hits_unique_0 ON public.retrieval_hits USING btree (retrieval_run_id, rank)`.

### agent_knowledge_grants

Knowledge base agent được phép dùng

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **1**. RLS/FORCE: **True/True**. FK ra/vào: **4/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `tenant_id` | `uuid` | True | PK/FK | `—` | Tenant sở hữu dữ liệu |
| `agent_id` | `text` | True | PK/FK | `—` | Tham chiếu danh mục agent của platform |
| `knowledge_base_id` | `uuid` | True | PK/FK | `—` | Tham chiếu bộ sưu tập tri thức |
| `granted_by` | `text` | True | FK | `—` | Người cấp quyền |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |

Ràng buộc:

- `agent_knowledge_grants_agent_id_fk`: `FOREIGN KEY (tenant_id, agent_id) REFERENCES agents(tenant_id, id) ON DELETE RESTRICT`.
- `agent_knowledge_grants_granted_by_fk`: `FOREIGN KEY (granted_by) REFERENCES users(id) ON DELETE RESTRICT`.
- `agent_knowledge_grants_knowledge_base_id_fk`: `FOREIGN KEY (tenant_id, knowledge_base_id) REFERENCES knowledge_bases(tenant_id, id) ON DELETE RESTRICT`.
- `agent_knowledge_grants_tenant_id_agent_id_knowledge_base_id_pk`: `PRIMARY KEY (tenant_id, agent_id, knowledge_base_id)`.
- `agent_knowledge_grants_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.

Chỉ mục:

- `CREATE UNIQUE INDEX agent_knowledge_grants_tenant_id_agent_id_knowledge_base_id_pk ON public.agent_knowledge_grants USING btree (tenant_id, agent_id, knowledge_base_id)`.

### memory_candidates

Tri thức rút ra cần admin duyệt

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **4**. RLS/FORCE: **True/True**. FK ra/vào: **9/3**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `source_ticket_id` | `uuid` | False | FK | `—` | Tham chiếu nguồn chuẩn của yêu cầu cư dân |
| `source_run_id` | `uuid` | False | FK | `—` | Tham chiếu theo dõi thực thi xuyên framework |
| `scope_id` | `uuid` | True | FK | `—` | Tham chiếu phạm vi quyền có kiểu rõ ràng |
| `proposed_text` | `text` | True | — | `—` | Tri thức đề xuất để duyệt |
| `evidence` | `jsonb` | True | — | `—` | Bằng chứng và nguồn tri thức |
| `pii_redacted` | `boolean` | True | — | `false` | Đã loại thông tin cá nhân |
| `status` | `text` | True | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `proposed_by_agent_id` | `text` | False | FK | `—` | Tham chiếu danh mục agent của platform |
| `reason` | `text` | True | — | `—` | Lý do |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |
| `namespace_id` | `uuid` | True | FK | `—` | Tham chiếu memory_namespaces |
| `source_binding_id` | `uuid` | False | FK | `—` | Tham chiếu runtime_session_bindings |
| `subject_user_id` | `text` | False | FK | `—` | Tham chiếu tài khoản người dùng chung của platform |
| `proposal_revision` | `integer` | True | — | `1` | Số phiên bản nội dung đề xuất trong chuỗi thay thế |
| `proposal_hash` | `text` | True | — | `—` | Hash nội dung bất biến được đem ra duyệt |
| `supersedes_candidate_id` | `uuid` | False | FK | `—` | Tham chiếu tri thức rút ra cần admin duyệt |

Ràng buộc:

- `memory_candidates_check_0`: `CHECK (status = ANY (ARRAY['pending'::text, 'approved'::text, 'rejected'::text, 'published'::text, 'revoked'::text]))`.
- `memory_candidates_namespace_id_fk`: `FOREIGN KEY (tenant_id, namespace_id) REFERENCES memory_namespaces(tenant_id, id) ON DELETE RESTRICT`.
- `memory_candidates_pkey`: `PRIMARY KEY (id)`.
- `memory_candidates_proposed_by_agent_id_fk`: `FOREIGN KEY (tenant_id, proposed_by_agent_id) REFERENCES agents(tenant_id, id) ON DELETE RESTRICT`.
- `memory_candidates_scope_id_fk`: `FOREIGN KEY (tenant_id, scope_id) REFERENCES access_scopes(tenant_id, id) ON DELETE RESTRICT`.
- `memory_candidates_source_binding_id_fk`: `FOREIGN KEY (tenant_id, source_binding_id) REFERENCES runtime_session_bindings(tenant_id, id) ON DELETE RESTRICT`.
- `memory_candidates_source_run_id_fk`: `FOREIGN KEY (tenant_id, source_run_id) REFERENCES agent_runs(tenant_id, id) ON DELETE RESTRICT`.
- `memory_candidates_source_ticket_id_fk`: `FOREIGN KEY (tenant_id, source_ticket_id) REFERENCES tickets(tenant_id, id) ON DELETE RESTRICT`.
- `memory_candidates_subject_user_id_fk`: `FOREIGN KEY (subject_user_id) REFERENCES users(id) ON DELETE RESTRICT`.
- `memory_candidates_supersedes_candidate_id_fk`: `FOREIGN KEY (tenant_id, supersedes_candidate_id) REFERENCES memory_candidates(tenant_id, id) ON DELETE RESTRICT`.
- `memory_candidates_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `memory_candidates_tenant_key_uq`: `UNIQUE (tenant_id, id)`.

Chỉ mục:

- `CREATE INDEX memory_candidates_namespace_id_idx ON public.memory_candidates USING btree (tenant_id, namespace_id)`.
- `CREATE UNIQUE INDEX memory_candidates_partial_0 ON public.memory_candidates USING btree (supersedes_candidate_id) WHERE (supersedes_candidate_id IS NOT NULL)`.
- `CREATE UNIQUE INDEX memory_candidates_pkey ON public.memory_candidates USING btree (id)`.
- `CREATE UNIQUE INDEX memory_candidates_tenant_key_uq ON public.memory_candidates USING btree (tenant_id, id)`.

### memory_publications

Bộ nhớ dài hạn đã được xuất bản

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **6/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `candidate_id` | `uuid` | True | FK | `—` | Tham chiếu tri thức rút ra cần admin duyệt |
| `approval_review_id` | `uuid` | True | FK | `—` | Tham chiếu duyệt tài liệu và tri thức học được |
| `document_id` | `uuid` | True | FK | `—` | Tham chiếu định danh tài liệu và chủ quản |
| `version_id` | `uuid` | True | FK | `—` | Tham chiếu nội dung tài liệu có phiên bản |
| `published_at` | `timestamp with time zone` | True | — | `—` | Thời điểm công bố |
| `revoked_at` | `timestamp with time zone` | False | — | `—` | Thời điểm thu hồi |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |
| `namespace_id` | `uuid` | True | FK | `—` | Tham chiếu memory_namespaces |

Ràng buộc:

- `memory_publications_approval_review_id_fk`: `FOREIGN KEY (tenant_id, approval_review_id) REFERENCES knowledge_reviews(tenant_id, id) ON DELETE RESTRICT`.
- `memory_publications_candidate_id_fk`: `FOREIGN KEY (tenant_id, candidate_id) REFERENCES memory_candidates(tenant_id, id) ON DELETE RESTRICT`.
- `memory_publications_document_id_fk`: `FOREIGN KEY (tenant_id, document_id) REFERENCES knowledge_documents(tenant_id, id) ON DELETE RESTRICT`.
- `memory_publications_namespace_id_fk`: `FOREIGN KEY (tenant_id, namespace_id) REFERENCES memory_namespaces(tenant_id, id) ON DELETE RESTRICT`.
- `memory_publications_pkey`: `PRIMARY KEY (id)`.
- `memory_publications_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `memory_publications_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `memory_publications_unique_0`: `UNIQUE (candidate_id)`.
- `memory_publications_version_id_fk`: `FOREIGN KEY (tenant_id, version_id) REFERENCES document_versions(tenant_id, id) ON DELETE RESTRICT`.

Chỉ mục:

- `CREATE INDEX memory_publications_namespace_id_idx ON public.memory_publications USING btree (tenant_id, namespace_id)`.
- `CREATE UNIQUE INDEX memory_publications_pkey ON public.memory_publications USING btree (id)`.
- `CREATE UNIQUE INDEX memory_publications_tenant_key_uq ON public.memory_publications USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX memory_publications_unique_0 ON public.memory_publications USING btree (candidate_id)`.

### memory_namespaces

Phạm vi đọc ghi memory xuyên thread

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **1**. RLS/FORCE: **True/True**. FK ra/vào: **4/5**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `owner_principal_id` | `uuid` | True | FK | `—` | Tham chiếu execution_principals |
| `kind` | `text` | True | — | `—` | Loại bản ghi |
| `workspace_id` | `uuid` | False | FK | `—` | Workspace của ban quản lý |
| `team_id` | `uuid` | False | FK | `—` | Tham chiếu một phiên cộng tác |
| `namespace_key` | `text` | True | — | `—` | Khóa namespace nghiệp vụ do server cấp |
| `purpose` | `text` | True | — | `—` | Vai trò chức năng agent hoặc mục đích file |
| `status` | `text` | True | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `retention_days` | `integer` | False | — | `—` | Số ngày giữ memory trước quy trình thu hồi/xóa |
| `authz_version` | `bigint` | True | — | `1` | Bộ đếm thay đổi quyền dùng để vô hiệu cache/capability |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |

Ràng buộc:

- `memory_namespaces_check_0`: `CHECK (kind = 'personal'::text AND workspace_id IS NULL AND team_id IS NULL OR kind = 'workspace'::text AND workspace_id IS NOT NULL AND team_id IS NULL OR kind = 'team'::text AND workspace_id IS NOT NULL AND team_id IS NOT NULL)`.
- `memory_namespaces_check_1`: `CHECK (kind = ANY (ARRAY['personal'::text, 'team'::text, 'workspace'::text]))`.
- `memory_namespaces_check_2`: `CHECK (status = ANY (ARRAY['active'::text, 'revoked'::text, 'purging'::text, 'purged'::text]))`.
- `memory_namespaces_owner_principal_id_fk`: `FOREIGN KEY (tenant_id, owner_principal_id) REFERENCES execution_principals(tenant_id, id) ON DELETE RESTRICT`.
- `memory_namespaces_pkey`: `PRIMARY KEY (id)`.
- `memory_namespaces_team_id_fk`: `FOREIGN KEY (tenant_id, team_id) REFERENCES agent_teams(tenant_id, id) ON DELETE RESTRICT`.
- `memory_namespaces_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `memory_namespaces_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `memory_namespaces_workspace_id_fk`: `FOREIGN KEY (tenant_id, workspace_id) REFERENCES workspaces(tenant_id, id) ON DELETE RESTRICT`.

Chỉ mục:

- `CREATE UNIQUE INDEX memory_namespaces_partial_0 ON public.memory_namespaces USING btree (owner_principal_id, kind, purpose) WHERE (kind = 'personal'::text)`.
- `CREATE UNIQUE INDEX memory_namespaces_partial_1 ON public.memory_namespaces USING btree (team_id, purpose) WHERE (kind = 'team'::text)`.
- `CREATE UNIQUE INDEX memory_namespaces_partial_2 ON public.memory_namespaces USING btree (workspace_id, purpose) WHERE (kind = 'workspace'::text)`.
- `CREATE UNIQUE INDEX memory_namespaces_pkey ON public.memory_namespaces USING btree (id)`.
- `CREATE UNIQUE INDEX memory_namespaces_tenant_key_uq ON public.memory_namespaces USING btree (tenant_id, id)`.
- `CREATE INDEX memory_namespaces_workspace_id_idx ON public.memory_namespaces USING btree (tenant_id, workspace_id)`.

### runtime_memory_bindings

Ánh xạ memory namespace vào Store của framework

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **3/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `namespace_id` | `uuid` | True | FK | `—` | Tham chiếu memory_namespaces |
| `backend_id` | `uuid` | True | FK | `—` | Tham chiếu runtime_backends |
| `runtime_namespace` | `jsonb` | True | — | `—` | Mảng thành phần namespace đúng định dạng adapter |
| `status` | `text` | True | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `sync_generation` | `bigint` | True | — | `1` | Thế hệ đồng bộ chống ghi lại memory đã thu hồi |
| `last_synced_at` | `timestamp with time zone` | False | — | `—` | Thời điểm last synced |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |

Ràng buộc:

- `runtime_memory_bindings_backend_id_fk`: `FOREIGN KEY (backend_id) REFERENCES runtime_backends(id) ON DELETE RESTRICT`.
- `runtime_memory_bindings_check_0`: `CHECK (status = ANY (ARRAY['disabled'::text, 'active'::text, 'revoked'::text]))`.
- `runtime_memory_bindings_namespace_id_fk`: `FOREIGN KEY (tenant_id, namespace_id) REFERENCES memory_namespaces(tenant_id, id) ON DELETE RESTRICT`.
- `runtime_memory_bindings_pkey`: `PRIMARY KEY (id)`.
- `runtime_memory_bindings_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `runtime_memory_bindings_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `runtime_memory_bindings_unique_0`: `UNIQUE (namespace_id, backend_id)`.
- `runtime_memory_bindings_unique_1`: `UNIQUE (backend_id, runtime_namespace)`.

Chỉ mục:

- `CREATE INDEX runtime_memory_bindings_namespace_id_idx ON public.runtime_memory_bindings USING btree (tenant_id, namespace_id)`.
- `CREATE UNIQUE INDEX runtime_memory_bindings_pkey ON public.runtime_memory_bindings USING btree (id)`.
- `CREATE UNIQUE INDEX runtime_memory_bindings_tenant_key_uq ON public.runtime_memory_bindings USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX runtime_memory_bindings_unique_0 ON public.runtime_memory_bindings USING btree (namespace_id, backend_id)`.
- `CREATE UNIQUE INDEX runtime_memory_bindings_unique_1 ON public.runtime_memory_bindings USING btree (backend_id, runtime_namespace)`.

### run_memory_access

Các namespace mà một run thực sự được cấp

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **3/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `run_id` | `uuid` | True | FK | `—` | Tham chiếu theo dõi thực thi xuyên framework |
| `namespace_id` | `uuid` | True | FK | `—` | Tham chiếu memory_namespaces |
| `access_mode` | `text` | True | — | `—` | Quyền đọc hoặc đề xuất memory cho run |
| `authz_version` | `bigint` | True | — | `—` | Bộ đếm thay đổi quyền dùng để vô hiệu cache/capability |
| `policy_version` | `text` | True | — | `—` | Phiên bản policy khi chọn dữ liệu |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |

Ràng buộc:

- `run_memory_access_check_0`: `CHECK (access_mode = ANY (ARRAY['read'::text, 'propose'::text]))`.
- `run_memory_access_namespace_id_fk`: `FOREIGN KEY (tenant_id, namespace_id) REFERENCES memory_namespaces(tenant_id, id) ON DELETE RESTRICT`.
- `run_memory_access_pkey`: `PRIMARY KEY (id)`.
- `run_memory_access_run_id_fk`: `FOREIGN KEY (tenant_id, run_id) REFERENCES agent_runs(tenant_id, id) ON DELETE RESTRICT`.
- `run_memory_access_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `run_memory_access_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `run_memory_access_unique_0`: `UNIQUE (run_id, namespace_id, access_mode)`.

Chỉ mục:

- `CREATE INDEX run_memory_access_namespace_id_idx ON public.run_memory_access USING btree (tenant_id, namespace_id)`.
- `CREATE UNIQUE INDEX run_memory_access_pkey ON public.run_memory_access USING btree (id)`.
- `CREATE INDEX run_memory_access_run_id_idx ON public.run_memory_access USING btree (tenant_id, run_id)`.
- `CREATE UNIQUE INDEX run_memory_access_tenant_key_uq ON public.run_memory_access USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX run_memory_access_unique_0 ON public.run_memory_access USING btree (run_id, namespace_id, access_mode)`.

## 07 File và storage

### storage_locations

Bucket và prefix được cấp cho tenant

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **1**. RLS/FORCE: **True/True**. FK ra/vào: **1/4**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `provider` | `text` | True | — | `—` | Nhà cung cấp dịch vụ |
| `endpoint_ref` | `text` | True | — | `—` | Mã endpoint được quản trị allowlist |
| `region` | `text` | False | — | `—` | Region cấu hình của object store |
| `bucket_name` | `text` | True | — | `—` | Tên bucket vật lý |
| `tenant_prefix` | `text` | True | — | `—` | Prefix object riêng cho tenant |
| `credential_secret_ref` | `text` | True | — | `—` | Tham chiếu bộ thông tin truy cập object store trong vault |
| `versioning_required` | `boolean` | True | — | `true` | Yêu cầu bucket có versioning trước khi ghi |
| `encryption_mode` | `text` | True | — | `—` | Chế độ mã hóa phía object store |
| `kms_key_ref` | `text` | False | — | `—` | Tham chiếu khóa KMS, không chứa vật liệu khóa |
| `purpose` | `text` | True | — | `—` | Vai trò chức năng agent hoặc mục đích file |
| `status` | `text` | True | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |

Ràng buộc:

- `storage_locations_check_0`: `CHECK (purpose = ANY (ARRAY['staging'::text, 'evidence'::text, 'derived'::text, 'documents'::text, 'reports'::text]))`.
- `storage_locations_check_1`: `CHECK (status = ANY (ARRAY['active'::text, 'readonly'::text, 'disabled'::text]))`.
- `storage_locations_pkey`: `PRIMARY KEY (id)`.
- `storage_locations_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `storage_locations_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `storage_locations_unique_0`: `UNIQUE (endpoint_ref, bucket_name, tenant_prefix)`.

Chỉ mục:

- `CREATE UNIQUE INDEX storage_locations_pkey ON public.storage_locations USING btree (id)`.
- `CREATE UNIQUE INDEX storage_locations_tenant_key_uq ON public.storage_locations USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX storage_locations_unique_0 ON public.storage_locations USING btree (endpoint_ref, bucket_name, tenant_prefix)`.

### files

Metadata file dùng chung

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **1**. RLS/FORCE: **True/True**. FK ra/vào: **9/16**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `uploaded_by` | `text` | False | FK | `—` | Tham chiếu tài khoản người dùng chung của platform |
| `original_name` | `text` | True | — | `—` | Tên file gốc |
| `retention_until` | `timestamp with time zone` | False | — | `—` | Mốc giữ file |
| `deleted_at` | `timestamp with time zone` | False | — | `—` | Thời điểm xóa mềm |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |
| `owner_principal_id` | `uuid` | True | FK | `—` | Tham chiếu execution_principals |
| `scope_kind` | `text` | True | — | `—` | Phạm vi sở hữu credential |
| `ticket_id` | `uuid` | False | FK | `—` | Tham chiếu nguồn chuẩn của yêu cầu cư dân |
| `channel_id` | `text` | False | FK | `—` | Tham chiếu cửa sổ reception hoặc groupchat quản lý |
| `document_id` | `uuid` | False | FK | `—` | Tham chiếu định danh tài liệu và chủ quản |
| `report_id` | `uuid` | False | FK | `—` | Tham chiếu yêu cầu báo cáo docx |
| `status` | `text` | True | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `accepted_object_id` | `uuid` | False | FK | `—` | Tham chiếu file_objects |
| `declared_mime_type` | `text` | False | — | `—` | MIME client khai báo trước khi verifier kiểm tra |
| `legal_hold` | `boolean` | True | — | `false` | Chặn xóa theo quyết định giữ dữ liệu của ứng dụng |
| `unit_id` | `uuid` | False | FK | `—` | — |

Ràng buộc:

- `file_original_scope`: `TRIGGER DEFERRABLE INITIALLY DEFERRED`.
- `files_accepted_object_id_fk`: `FOREIGN KEY (tenant_id, accepted_object_id) REFERENCES file_objects(tenant_id, id) ON DELETE RESTRICT`.
- `files_channel_id_fk`: `FOREIGN KEY (tenant_id, channel_id) REFERENCES channels(tenant_id, id) ON DELETE RESTRICT`.
- `files_check_0`: `CHECK (num_nonnulls(ticket_id, channel_id, document_id, report_id, unit_id) = 1)`.
- `files_check_1`: `CHECK (scope_kind = 'ticket'::text AND ticket_id IS NOT NULL OR scope_kind = 'channel'::text AND channel_id IS NOT NULL OR scope_kind = 'document'::text AND document_id IS NOT NULL OR scope_kind = 'report'::text AND report_id IS NOT NULL OR scope_kind = 'resident'::text AND unit_id IS NOT NULL)`.
- `files_check_2`: `CHECK (status <> 'ready'::text OR accepted_object_id IS NOT NULL)`.
- `files_check_3`: `CHECK (scope_kind = ANY (ARRAY['ticket'::text, 'channel'::text, 'document'::text, 'report'::text, 'resident'::text]))`.
- `files_check_4`: `CHECK (status = ANY (ARRAY['staged'::text, 'verifying'::text, 'ready'::text, 'rejected'::text, 'deletion_pending'::text, 'deleted'::text, 'missing'::text]))`.
- `files_document_id_fk`: `FOREIGN KEY (tenant_id, document_id) REFERENCES knowledge_documents(tenant_id, id) ON DELETE RESTRICT`.
- `files_owner_principal_id_fk`: `FOREIGN KEY (tenant_id, owner_principal_id) REFERENCES execution_principals(tenant_id, id) ON DELETE RESTRICT`.
- `files_pkey`: `PRIMARY KEY (id)`.
- `files_report_id_fk`: `FOREIGN KEY (tenant_id, report_id) REFERENCES report_requests(tenant_id, id) ON DELETE RESTRICT`.
- `files_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `files_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `files_ticket_id_fk`: `FOREIGN KEY (tenant_id, ticket_id) REFERENCES tickets(tenant_id, id) ON DELETE RESTRICT`.
- `files_unit_id_fk`: `FOREIGN KEY (tenant_id, unit_id) REFERENCES units(tenant_id, id)`.
- `files_uploaded_by_fk`: `FOREIGN KEY (uploaded_by) REFERENCES users(id) ON DELETE RESTRICT`.

Chỉ mục:

- `CREATE UNIQUE INDEX files_pkey ON public.files USING btree (id)`.
- `CREATE UNIQUE INDEX files_tenant_key_uq ON public.files USING btree (tenant_id, id)`.
- `CREATE INDEX files_ticket_id_idx ON public.files USING btree (tenant_id, ticket_id)`.

### file_objects

Một object version vật lý bất biến của file

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **4/7**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `file_id` | `uuid` | True | FK | `—` | Tham chiếu metadata file dùng chung |
| `location_id` | `uuid` | True | FK | `—` | Tham chiếu storage_locations |
| `object_key` | `text` | True | — | `—` | Khóa object, không phải signed URL |
| `version_id` | `text` | True | — | `—` | Version ID của S3/MinIO, không phải phiên bản agent hoặc document |
| `variant` | `text` | True | — | `—` | Vai trò của object: gốc, thumbnail, che PII hoặc preview |
| `variant_revision` | `integer` | True | — | `1` | Phiên bản xử lý của cùng loại biến thể |
| `source_object_id` | `uuid` | False | FK | `—` | Tham chiếu file_objects |
| `mime_type` | `text` | True | — | `—` | MIME đã kiểm tra |
| `size_bytes` | `bigint` | True | — | `—` | Kích thước byte |
| `sha256` | `text` | True | — | `—` | Hash SHA-256 |
| `etag` | `text` | False | — | `—` | ETag do provider trả; không mặc định là MD5 |
| `checksum_algorithm` | `text` | False | — | `—` | Thuật toán checksum provider trả |
| `checksum_value` | `text` | False | — | `—` | Giá trị checksum provider; không thay full-file SHA256 |
| `checksum_type` | `text` | False | — | `—` | Checksum toàn file hoặc composite multipart |
| `width_px` | `integer` | False | — | `—` | Chiều rộng ảnh sau kiểm tra định dạng |
| `height_px` | `integer` | False | — | `—` | Chiều cao ảnh sau kiểm tra định dạng |
| `scan_status` | `text` | True | — | `—` | Trạng thái kiểm tra an toàn file |
| `verified_at` | `timestamp with time zone` | False | — | `—` | Thời điểm xác minh |
| `encryption_mode` | `text` | True | — | `—` | Chế độ mã hóa phía object store |
| `kms_key_ref` | `text` | False | — | `—` | Tham chiếu khóa KMS, không chứa vật liệu khóa |
| `object_retain_until` | `timestamp with time zone` | False | — | `—` | Mốc retention lock quan sát được trên object store |
| `object_legal_hold` | `boolean` | True | — | `false` | Trạng thái Object Lock legal hold quan sát được |
| `status` | `text` | True | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |

Ràng buộc:

- `file_objects_check_0`: `CHECK (size_bytes >= 0)`.
- `file_objects_check_1`: `CHECK (sha256 ~ '^[0-9a-f]{64}$'::text)`.
- `file_objects_check_2`: `CHECK (variant_revision > 0)`.
- `file_objects_check_3`: `CHECK (variant = 'original'::text OR source_object_id IS NOT NULL)`.
- `file_objects_check_4`: `CHECK (status <> 'ready'::text OR scan_status = 'clean'::text AND verified_at IS NOT NULL)`.
- `file_objects_check_5`: `CHECK (version_id <> ''::text AND version_id <> 'null'::text)`.
- `file_objects_check_6`: `CHECK (variant = ANY (ARRAY['original'::text, 'thumbnail'::text, 'redacted'::text, 'preview'::text]))`.
- `file_objects_check_7`: `CHECK (scan_status = ANY (ARRAY['pending'::text, 'clean'::text, 'infected'::text, 'failed'::text]))`.
- `file_objects_check_8`: `CHECK (status = ANY (ARRAY['verifying'::text, 'ready'::text, 'rejected'::text, 'deletion_pending'::text, 'deleted'::text, 'missing'::text]))`.
- `file_objects_file_id_fk`: `FOREIGN KEY (tenant_id, file_id) REFERENCES files(tenant_id, id) ON DELETE RESTRICT`.
- `file_objects_location_id_fk`: `FOREIGN KEY (tenant_id, location_id) REFERENCES storage_locations(tenant_id, id) ON DELETE RESTRICT`.
- `file_objects_pkey`: `PRIMARY KEY (id)`.
- `file_objects_source_object_id_fk`: `FOREIGN KEY (tenant_id, source_object_id) REFERENCES file_objects(tenant_id, id) ON DELETE RESTRICT`.
- `file_objects_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `file_objects_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `file_objects_unique_0`: `UNIQUE (location_id, object_key, version_id)`.
- `file_objects_unique_1`: `UNIQUE (file_id, variant, variant_revision)`.

Chỉ mục:

- `CREATE UNIQUE INDEX file_objects_pkey ON public.file_objects USING btree (id)`.
- `CREATE UNIQUE INDEX file_objects_tenant_key_uq ON public.file_objects USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX file_objects_unique_0 ON public.file_objects USING btree (location_id, object_key, version_id)`.
- `CREATE UNIQUE INDEX file_objects_unique_1 ON public.file_objects USING btree (file_id, variant, variant_revision)`.

### file_uploads

Phiên upload staging do server cấp

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **5/2**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `file_id` | `uuid` | True | FK | `—` | Tham chiếu metadata file dùng chung |
| `requested_by` | `text` | True | FK | `—` | Tham chiếu tài khoản người dùng chung của platform |
| `location_id` | `uuid` | True | FK | `—` | Tham chiếu storage_locations |
| `staging_key` | `text` | True | — | `—` | Khóa upload cách ly do server sinh |
| `source_version_id` | `text` | False | — | `—` | Version staging được xác minh và dùng làm nguồn copy |
| `upload_mode` | `text` | True | — | `—` | Upload một request hoặc multipart |
| `multipart_upload_id` | `text` | False | — | `—` | ID multipart do object store cấp |
| `expected_size_bytes` | `bigint` | True | — | `—` | Kích thước client khai báo để đối soát |
| `expected_sha256` | `text` | False | — | `—` | SHA256 client khai báo; verifier vẫn tự tính |
| `allowed_mime_types` | `text[]` | True | — | `—` | Allowlist MIME do policy server chốt cho upload |
| `max_size_bytes` | `bigint` | True | — | `—` | Dung lượng tối đa policy cho phép |
| `status` | `text` | True | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `idempotency_key` | `text` | True | — | `—` | Khóa chống xử lý lặp |
| `expires_at` | `timestamp with time zone` | True | — | `—` | Thời điểm hết hạn |
| `finalized_at` | `timestamp with time zone` | False | — | `—` | Thời điểm finalized |
| `result_object_id` | `uuid` | False | FK | `—` | Tham chiếu file_objects |
| `failure_code` | `text` | False | — | `—` | Mã lỗi đã loại thông tin nhạy cảm |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |

Ràng buộc:

- `file_uploads_check_0`: `CHECK (expected_size_bytes > 0 AND expected_size_bytes <= max_size_bytes)`.
- `file_uploads_check_1`: `CHECK (upload_mode <> 'multipart'::text OR multipart_upload_id IS NOT NULL)`.
- `file_uploads_check_2`: `CHECK (upload_mode = ANY (ARRAY['single'::text, 'multipart'::text]))`.
- `file_uploads_check_3`: `CHECK (status = ANY (ARRAY['issued'::text, 'uploading'::text, 'uploaded'::text, 'verifying'::text, 'accepted'::text, 'rejected'::text, 'expired'::text, 'aborted'::text]))`.
- `file_uploads_file_id_fk`: `FOREIGN KEY (tenant_id, file_id) REFERENCES files(tenant_id, id) ON DELETE RESTRICT`.
- `file_uploads_location_id_fk`: `FOREIGN KEY (tenant_id, location_id) REFERENCES storage_locations(tenant_id, id) ON DELETE RESTRICT`.
- `file_uploads_pkey`: `PRIMARY KEY (id)`.
- `file_uploads_requested_by_fk`: `FOREIGN KEY (requested_by) REFERENCES users(id) ON DELETE RESTRICT`.
- `file_uploads_result_object_id_fk`: `FOREIGN KEY (tenant_id, result_object_id) REFERENCES file_objects(tenant_id, id) ON DELETE RESTRICT`.
- `file_uploads_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `file_uploads_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `file_uploads_unique_0`: `UNIQUE (tenant_id, requested_by, idempotency_key)`.
- `file_uploads_unique_1`: `UNIQUE (location_id, staging_key)`.

Chỉ mục:

- `CREATE UNIQUE INDEX file_uploads_partial_0 ON public.file_uploads USING btree (file_id) WHERE (status = ANY (ARRAY['issued'::text, 'uploading'::text, 'uploaded'::text, 'verifying'::text]))`.
- `CREATE UNIQUE INDEX file_uploads_pkey ON public.file_uploads USING btree (id)`.
- `CREATE UNIQUE INDEX file_uploads_tenant_key_uq ON public.file_uploads USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX file_uploads_unique_0 ON public.file_uploads USING btree (tenant_id, requested_by, idempotency_key)`.
- `CREATE UNIQUE INDEX file_uploads_unique_1 ON public.file_uploads USING btree (location_id, staging_key)`.

### file_upload_parts

Các part multipart đã đối soát

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **2/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `upload_id` | `uuid` | True | FK | `—` | Tham chiếu file_uploads |
| `part_number` | `integer` | True | — | `—` | Số thứ tự part trong multipart upload |
| `etag` | `text` | True | — | `—` | ETag do provider trả; không mặc định là MD5 |
| `size_bytes` | `bigint` | True | — | `—` | Kích thước byte |
| `checksum_value` | `text` | False | — | `—` | Giá trị checksum provider; không thay full-file SHA256 |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |

Ràng buộc:

- `file_upload_parts_check_0`: `CHECK (part_number >= 1 AND part_number <= 10000)`.
- `file_upload_parts_check_1`: `CHECK (size_bytes > 0)`.
- `file_upload_parts_pkey`: `PRIMARY KEY (id)`.
- `file_upload_parts_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `file_upload_parts_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `file_upload_parts_unique_0`: `UNIQUE (upload_id, part_number)`.
- `file_upload_parts_upload_id_fk`: `FOREIGN KEY (tenant_id, upload_id) REFERENCES file_uploads(tenant_id, id) ON DELETE RESTRICT`.

Chỉ mục:

- `CREATE UNIQUE INDEX file_upload_parts_pkey ON public.file_upload_parts USING btree (id)`.
- `CREATE UNIQUE INDEX file_upload_parts_tenant_key_uq ON public.file_upload_parts USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX file_upload_parts_unique_0 ON public.file_upload_parts USING btree (upload_id, part_number)`.

### file_processing_jobs

Queue kiểm tra copy ảnh và xóa có lease

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **4/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `file_id` | `uuid` | True | FK | `—` | Tham chiếu metadata file dùng chung |
| `upload_id` | `uuid` | False | FK | `—` | Tham chiếu file_uploads |
| `object_id` | `uuid` | False | FK | `—` | Tham chiếu file_objects |
| `kind` | `text` | True | — | `—` | Loại bản ghi |
| `dedupe_key` | `text` | True | — | `—` | Khóa chống thông báo trùng |
| `status` | `text` | True | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `available_at` | `timestamp with time zone` | True | — | `—` | Thời điểm có thể xử lý |
| `attempts` | `integer` | True | — | `0` | Số lần thử |
| `lease_owner` | `text` | False | — | `—` | Worker giữ lease |
| `lease_until` | `timestamp with time zone` | False | — | `—` | Thời điểm hết lease |
| `fencing_version` | `bigint` | True | — | `0` | Thế hệ lease, tăng mỗi lần worker claim |
| `payload` | `jsonb` | True | — | `—` | Payload có cấu trúc, không chứa secret thô |
| `finished_at` | `timestamp with time zone` | False | — | `—` | Thời điểm kết thúc |
| `failure_code` | `text` | False | — | `—` | Mã lỗi đã loại thông tin nhạy cảm |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |

Ràng buộc:

- `file_processing_jobs_check_0`: `CHECK (kind = ANY (ARRAY['verify'::text, 'promote'::text, 'thumbnail'::text, 'redact'::text, 'delete'::text, 'reconcile'::text]))`.
- `file_processing_jobs_check_1`: `CHECK (status = ANY (ARRAY['pending'::text, 'running'::text, 'succeeded'::text, 'failed'::text, 'dead'::text, 'cancelled'::text]))`.
- `file_processing_jobs_file_id_fk`: `FOREIGN KEY (tenant_id, file_id) REFERENCES files(tenant_id, id) ON DELETE RESTRICT`.
- `file_processing_jobs_object_id_fk`: `FOREIGN KEY (tenant_id, object_id) REFERENCES file_objects(tenant_id, id) ON DELETE RESTRICT`.
- `file_processing_jobs_pkey`: `PRIMARY KEY (id)`.
- `file_processing_jobs_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `file_processing_jobs_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `file_processing_jobs_unique_0`: `UNIQUE (tenant_id, dedupe_key)`.
- `file_processing_jobs_upload_id_fk`: `FOREIGN KEY (tenant_id, upload_id) REFERENCES file_uploads(tenant_id, id) ON DELETE RESTRICT`.

Chỉ mục:

- `CREATE UNIQUE INDEX file_processing_jobs_pkey ON public.file_processing_jobs USING btree (id)`.
- `CREATE UNIQUE INDEX file_processing_jobs_tenant_key_uq ON public.file_processing_jobs USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX file_processing_jobs_unique_0 ON public.file_processing_jobs USING btree (tenant_id, dedupe_key)`.

### storage_event_receipts

Dedupe thông báo object store

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **2/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `location_id` | `uuid` | True | FK | `—` | Tham chiếu storage_locations |
| `provider_event_key` | `text` | True | — | `—` | Khóa sự kiện canonical phục vụ dedupe theo provider |
| `event_type` | `text` | True | — | `—` | Loại sự kiện |
| `object_key` | `text` | True | — | `—` | Khóa object, không phải signed URL |
| `version_id` | `text` | False | — | `—` | Version ID của S3/MinIO, không phải phiên bản agent hoặc document |
| `sequencer` | `text` | False | — | `—` | Thứ tự provider cung cấp cho cùng object key |
| `event_time` | `timestamp with time zone` | False | — | `—` | Thời điểm sự kiện do provider ghi nhận |
| `received_at` | `timestamp with time zone` | True | — | `—` | Thời điểm tiếp nhận |
| `payload_hash` | `text` | True | — | `—` | Hash payload canonical dùng đối soát |
| `status` | `text` | True | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `processed_at` | `timestamp with time zone` | False | — | `—` | Thời điểm xử lý xong |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |

Ràng buộc:

- `storage_event_receipts_check_0`: `CHECK (status = ANY (ARRAY['pending'::text, 'done'::text, 'ignored'::text, 'failed'::text]))`.
- `storage_event_receipts_location_id_fk`: `FOREIGN KEY (tenant_id, location_id) REFERENCES storage_locations(tenant_id, id) ON DELETE RESTRICT`.
- `storage_event_receipts_pkey`: `PRIMARY KEY (id)`.
- `storage_event_receipts_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `storage_event_receipts_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `storage_event_receipts_unique_0`: `UNIQUE (location_id, provider_event_key)`.

Chỉ mục:

- `CREATE UNIQUE INDEX storage_event_receipts_pkey ON public.storage_event_receipts USING btree (id)`.
- `CREATE UNIQUE INDEX storage_event_receipts_tenant_key_uq ON public.storage_event_receipts USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX storage_event_receipts_unique_0 ON public.storage_event_receipts USING btree (location_id, provider_event_key)`.

### file_access_logs

Ai đã được cấp quyền tải ảnh nào

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **6/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `file_id` | `uuid` | True | FK | `—` | Tham chiếu metadata file dùng chung |
| `object_id` | `uuid` | False | FK | `—` | Tham chiếu file_objects |
| `actor_user_id` | `text` | False | FK | `—` | Tham chiếu tài khoản người dùng chung của platform |
| `actor_principal_id` | `uuid` | True | FK | `—` | Tham chiếu execution_principals |
| `run_id` | `uuid` | False | FK | `—` | Tham chiếu theo dõi thực thi xuyên framework |
| `action` | `text` | True | — | `—` | Hành động quản trị |
| `decision` | `text` | True | — | `—` | Quyết định duyệt |
| `purpose` | `text` | True | — | `—` | Vai trò chức năng agent hoặc mục đích file |
| `request_id` | `text` | True | — | `—` | Mã tương quan request trong audit |
| `signed_url_expires_at` | `timestamp with time zone` | False | — | `—` | Thời điểm signed url expires |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |

Ràng buộc:

- `file_access_logs_actor_principal_id_fk`: `FOREIGN KEY (tenant_id, actor_principal_id) REFERENCES execution_principals(tenant_id, id) ON DELETE RESTRICT`.
- `file_access_logs_actor_user_id_fk`: `FOREIGN KEY (actor_user_id) REFERENCES users(id) ON DELETE RESTRICT`.
- `file_access_logs_check_0`: `CHECK (action = ANY (ARRAY['view'::text, 'download'::text, 'presign'::text, 'upload'::text, 'deny'::text]))`.
- `file_access_logs_check_1`: `CHECK (decision = ANY (ARRAY['allow'::text, 'deny'::text]))`.
- `file_access_logs_file_id_fk`: `FOREIGN KEY (tenant_id, file_id) REFERENCES files(tenant_id, id) ON DELETE RESTRICT`.
- `file_access_logs_object_id_fk`: `FOREIGN KEY (tenant_id, object_id) REFERENCES file_objects(tenant_id, id) ON DELETE RESTRICT`.
- `file_access_logs_pkey`: `PRIMARY KEY (id)`.
- `file_access_logs_run_id_fk`: `FOREIGN KEY (tenant_id, run_id) REFERENCES agent_runs(tenant_id, id) ON DELETE RESTRICT`.
- `file_access_logs_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `file_access_logs_tenant_key_uq`: `UNIQUE (tenant_id, id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX file_access_logs_pkey ON public.file_access_logs USING btree (id)`.
- `CREATE INDEX file_access_logs_run_id_idx ON public.file_access_logs USING btree (tenant_id, run_id)`.
- `CREATE UNIQUE INDEX file_access_logs_tenant_key_uq ON public.file_access_logs USING btree (tenant_id, id)`.

### file_deletion_requests

Tombstone và điều phối xóa vật lý

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **3/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `file_id` | `uuid` | True | FK | `—` | Tham chiếu metadata file dùng chung |
| `requested_by` | `text` | False | FK | `—` | Tham chiếu tài khoản người dùng chung của platform |
| `reason` | `text` | True | — | `—` | Lý do |
| `not_before` | `timestamp with time zone` | True | — | `—` | Thời điểm sớm nhất được thực hiện xóa |
| `status` | `text` | True | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `completed_at` | `timestamp with time zone` | False | — | `—` | Thời điểm hoàn thành |
| `failure_code` | `text` | False | — | `—` | Mã lỗi đã loại thông tin nhạy cảm |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |

Ràng buộc:

- `file_deletion_requests_check_0`: `CHECK (status = ANY (ARRAY['pending'::text, 'running'::text, 'blocked'::text, 'completed'::text, 'cancelled'::text]))`.
- `file_deletion_requests_file_id_fk`: `FOREIGN KEY (tenant_id, file_id) REFERENCES files(tenant_id, id) ON DELETE RESTRICT`.
- `file_deletion_requests_pkey`: `PRIMARY KEY (id)`.
- `file_deletion_requests_requested_by_fk`: `FOREIGN KEY (requested_by) REFERENCES users(id) ON DELETE RESTRICT`.
- `file_deletion_requests_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `file_deletion_requests_tenant_key_uq`: `UNIQUE (tenant_id, id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX file_deletion_requests_partial_0 ON public.file_deletion_requests USING btree (file_id) WHERE (status = ANY (ARRAY['pending'::text, 'running'::text, 'blocked'::text]))`.
- `CREATE UNIQUE INDEX file_deletion_requests_pkey ON public.file_deletion_requests USING btree (id)`.
- `CREATE UNIQUE INDEX file_deletion_requests_tenant_key_uq ON public.file_deletion_requests USING btree (tenant_id, id)`.

### message_files

Đính kèm transcript

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **3/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `tenant_id` | `uuid` | True | PK/FK | `—` | Tenant sở hữu dữ liệu |
| `message_id` | `uuid` | True | PK/FK | `—` | Tham chiếu transcript chính của room |
| `file_id` | `uuid` | True | PK/FK | `—` | Tham chiếu metadata file dùng chung |
| `ordinal` | `integer` | True | — | `0` | Thứ tự |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |

Ràng buộc:

- `message_files_file_id_fk`: `FOREIGN KEY (tenant_id, file_id) REFERENCES files(tenant_id, id) ON DELETE RESTRICT`.
- `message_files_message_id_fk`: `FOREIGN KEY (tenant_id, message_id) REFERENCES messages(tenant_id, id) ON DELETE RESTRICT`.
- `message_files_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `message_files_tenant_id_message_id_file_id_pk`: `PRIMARY KEY (tenant_id, message_id, file_id)`.
- `message_files_unique_0`: `UNIQUE (message_id, ordinal)`.

Chỉ mục:

- `CREATE UNIQUE INDEX message_files_tenant_id_message_id_file_id_pk ON public.message_files USING btree (tenant_id, message_id, file_id)`.
- `CREATE UNIQUE INDEX message_files_unique_0 ON public.message_files USING btree (message_id, ordinal)`.

### attachments

Đính kèm OpenBot cũ trong giai đoạn chuyển sang files

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **False/False**. FK ra/vào: **3/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `channel_id` | `text` | True | FK | `—` | Tham chiếu cửa sổ reception hoặc groupchat quản lý |
| `uploaded_by` | `text` | True | FK | `—` | Tham chiếu tài khoản người dùng chung của platform |
| `name` | `text` | True | — | `—` | Tên hiển thị |
| `mime_type` | `text` | True | — | `—` | MIME đã kiểm tra |
| `size_bytes` | `integer` | True | — | `—` | Kích thước byte |
| `bytes` | `bytea` | True | — | `—` | Nội dung nhị phân legacy |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `attached_at` | `timestamp with time zone` | False | — | `—` | Thời điểm gắn vào tin nhắn |
| `upload_group` | `text` | False | — | `—` | Nhóm file của một composer session |
| `file_id` | `uuid` | False | FK | `—` | Tham chiếu metadata file dùng chung |

Ràng buộc:

- `attachments_channel_id_fk`: `FOREIGN KEY (channel_id) REFERENCES channels(id) ON DELETE RESTRICT`.
- `attachments_file_id_fk`: `FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE RESTRICT`.
- `attachments_pkey`: `PRIMARY KEY (id)`.
- `attachments_uploaded_by_fk`: `FOREIGN KEY (uploaded_by) REFERENCES users(id) ON DELETE RESTRICT`.

Chỉ mục:

- `CREATE UNIQUE INDEX attachments_pkey ON public.attachments USING btree (id)`.

## 08 Ticket, triage, SLA và dispatch

### tickets

Nguồn chuẩn của yêu cầu cư dân

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **22**. RLS/FORCE: **True/True**. FK ra/vào: **16/25**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `code` | `text` | True | — | `—` | Mã định danh nghiệp vụ |
| `requester_user_id` | `text` | True | FK | `—` | Tham chiếu tài khoản người dùng chung của platform |
| `channel_id` | `text` | True | FK | `—` | Tham chiếu cửa sổ reception hoặc groupchat quản lý |
| `unit_id` | `uuid` | False | FK | `—` | Tham chiếu căn hộ hoặc nhà liền kề |
| `site_id` | `uuid` | False | FK | `—` | Tham chiếu khu đô thị |
| `zone_id` | `uuid` | False | FK | `—` | Tham chiếu phân khu |
| `building_id` | `uuid` | False | FK | `—` | Tham chiếu tòa nhà |
| `management_unit_id` | `uuid` | False | FK | `—` | Tham chiếu ban quản lý như một tổ chức |
| `coverage_id` | `uuid` | False | FK | `—` | Tham chiếu địa bàn phụ trách theo thời gian |
| `category_id` | `uuid` | False | FK | `—` | Tham chiếu phân loại chuẩn cho routing và báo cáo |
| `incident_type_id` | `uuid` | False | FK | `—` | Tham chiếu loại sự cố thống kê được |
| `title` | `text` | True | — | `—` | Tiêu đề |
| `description` | `text` | True | — | `—` | Mô tả |
| `priority` | `text` | False | — | `—` | Mức ưu tiên hoặc trọng số xếp hàng |
| `status` | `text` | True | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `resolution_mode` | `text` | False | — | `—` | Hướng dẫn tự xử lý hoặc sửa tại hiện trường |
| `contact_name` | `text` | True | — | `—` | Tên người liên hệ tại thời điểm tạo |
| `contact_phone` | `text` | True | — | `—` | Số liên hệ được chụp tại thời điểm tạo |
| `address_snapshot` | `jsonb` | True | — | `—` | Địa chỉ lịch sử đã chụp |
| `assigned_team_id` | `uuid` | False | FK | `—` | Tham chiếu một phiên cộng tác |
| `sla_policy_id` | `uuid` | False | FK | `—` | Tham chiếu thời hạn phục vụ theo phạm vi |
| `response_due_at` | `timestamp with time zone` | False | — | `—` | Hạn phản hồi |
| `resolution_due_at` | `timestamp with time zone` | False | — | `—` | Hạn giải quyết |
| `first_response_at` | `timestamp with time zone` | False | — | `—` | Thời điểm phản hồi đầu |
| `resolved_at` | `timestamp with time zone` | False | — | `—` | Thời điểm giải quyết kỹ thuật |
| `closed_at` | `timestamp with time zone` | False | — | `—` | Thời điểm hoàn tất ticket |
| `version` | `bigint` | True | — | `0` | Phiên bản cấu hình hoặc bộ đếm chống ghi đè |
| `last_event_seq` | `bigint` | True | — | `0` | Event cuối đã được ghi hoặc xử lý theo phạm vi bảng |
| `reopen_count` | `integer` | True | — | `0` | Số lần mở lại |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |
| `domain_id` | `uuid` | True | FK | `—` | Tham chiếu domains.id |
| `request_kind` | `text` | True | — | `—` | incident/service_request |
| `severity` | `text` | True | — | `'unknown'::text` | unknown/minor/moderate/major/critical/not_applicable |
| `triage_status` | `text` | True | — | `'pending'::text` | pending/provisional/confirmed/review_required |
| `current_triage_decision_id` | `uuid` | False | FK | `—` | Tham chiếu ticket_triage_decisions.id |
| `is_emergency` | `boolean` | True | — | `false` | Projection từ current applied decision |
| `active_sla_cycle_id` | `uuid` | False | FK | `—` | Tham chiếu ticket_sla_cycles.id |

Ràng buộc:

- `ticket_triage_projection`: `TRIGGER DEFERRABLE INITIALLY DEFERRED`.
- `tickets_active_sla_cycle_id_fk`: `FOREIGN KEY (tenant_id, active_sla_cycle_id) REFERENCES ticket_sla_cycles(tenant_id, id) ON DELETE RESTRICT`.
- `tickets_assigned_team_id_fk`: `FOREIGN KEY (tenant_id, assigned_team_id) REFERENCES agent_teams(tenant_id, id) ON DELETE RESTRICT`.
- `tickets_building_id_fk`: `FOREIGN KEY (tenant_id, building_id) REFERENCES buildings(tenant_id, id) ON DELETE RESTRICT`.
- `tickets_category_id_fk`: `FOREIGN KEY (tenant_id, category_id) REFERENCES service_categories(tenant_id, id) ON DELETE RESTRICT`.
- `tickets_channel_id_fk`: `FOREIGN KEY (tenant_id, channel_id) REFERENCES channels(tenant_id, id) ON DELETE RESTRICT`.
- `tickets_check_0`: `CHECK (priority IS NULL OR (priority = ANY (ARRAY['low'::text, 'normal'::text, 'high'::text, 'critical'::text])))`.
- `tickets_check_1`: `CHECK (severity = ANY (ARRAY['unknown'::text, 'minor'::text, 'moderate'::text, 'major'::text, 'critical'::text, 'not_applicable'::text]))`.
- `tickets_check_2`: `CHECK (request_kind = ANY (ARRAY['incident'::text, 'service_request'::text]))`.
- `tickets_check_3`: `CHECK (NOT is_emergency OR priority = 'critical'::text)`.
- `tickets_check_4`: `CHECK (resolution_mode = ANY (ARRAY['guided'::text, 'onsite'::text]))`.
- `tickets_check_5`: `CHECK (triage_status = ANY (ARRAY['pending'::text, 'provisional'::text, 'confirmed'::text, 'review_required'::text]))`.
- `tickets_coverage_id_fk`: `FOREIGN KEY (tenant_id, coverage_id) REFERENCES management_coverage(tenant_id, id) ON DELETE RESTRICT`.
- `tickets_current_triage_decision_id_fk`: `FOREIGN KEY (tenant_id, current_triage_decision_id) REFERENCES ticket_triage_decisions(tenant_id, id) ON DELETE RESTRICT`.
- `tickets_domain_id_fk`: `FOREIGN KEY (tenant_id, domain_id) REFERENCES domains(tenant_id, id) ON DELETE RESTRICT`.
- `tickets_incident_type_id_fk`: `FOREIGN KEY (tenant_id, incident_type_id) REFERENCES incident_types(tenant_id, id) ON DELETE RESTRICT`.
- `tickets_management_unit_id_fk`: `FOREIGN KEY (tenant_id, management_unit_id) REFERENCES management_units(tenant_id, id) ON DELETE RESTRICT`.
- `tickets_pkey`: `PRIMARY KEY (id)`.
- `tickets_requester_user_id_fk`: `FOREIGN KEY (requester_user_id) REFERENCES users(id) ON DELETE RESTRICT`.
- `tickets_site_id_fk`: `FOREIGN KEY (tenant_id, site_id) REFERENCES sites(tenant_id, id) ON DELETE RESTRICT`.
- `tickets_sla_policy_id_fk`: `FOREIGN KEY (tenant_id, sla_policy_id) REFERENCES sla_policies(tenant_id, id) ON DELETE RESTRICT`.
- `tickets_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `tickets_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `tickets_unique_0`: `UNIQUE (tenant_id, code)`.
- `tickets_unit_id_fk`: `FOREIGN KEY (tenant_id, unit_id) REFERENCES units(tenant_id, id) ON DELETE RESTRICT`.
- `tickets_zone_id_fk`: `FOREIGN KEY (tenant_id, zone_id) REFERENCES zones(tenant_id, id) ON DELETE RESTRICT`.

Chỉ mục:

- `CREATE UNIQUE INDEX tickets_pkey ON public.tickets USING btree (id)`.
- `CREATE UNIQUE INDEX tickets_tenant_key_uq ON public.tickets USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX tickets_unique_0 ON public.tickets USING btree (tenant_id, code)`.

### ticket_events

Lịch sử nghiệp vụ bất biến

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **5/12**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `ticket_id` | `uuid` | True | FK | `—` | Tham chiếu nguồn chuẩn của yêu cầu cư dân |
| `seq` | `bigint` | True | — | `—` | Số thứ tự trong ticket hoặc channel |
| `event_type` | `text` | True | — | `—` | Loại sự kiện |
| `schema_version` | `integer` | True | — | `1` | Phiên bản cấu trúc payload |
| `from_status` | `text` | False | — | `—` | Trạng thái trước |
| `to_status` | `text` | False | — | `—` | Trạng thái sau |
| `actor_kind` | `text` | True | — | `—` | Giá trị actor_kind; ý nghĩa và phạm vi theo quy tắc bảng |
| `actor_user_id` | `text` | False | FK | `—` | Tham chiếu tài khoản người dùng chung của platform |
| `actor_agent_id` | `text` | False | FK | `—` | Tham chiếu danh mục agent của platform |
| `idempotency_key` | `text` | True | — | `—` | Khóa chống xử lý lặp |
| `correlation_id` | `uuid` | True | — | `—` | ID liên kết toàn bộ luồng xử lý |
| `causation_event_id` | `uuid` | False | FK | `—` | Tham chiếu lịch sử nghiệp vụ bất biến |
| `payload` | `jsonb` | True | — | `—` | Payload có cấu trúc, không chứa secret thô |
| `occurred_at` | `timestamp with time zone` | True | — | `—` | Thời điểm sự kiện xảy ra ở nguồn |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |

Ràng buộc:

- `ticket_events_actor_agent_id_fk`: `FOREIGN KEY (tenant_id, actor_agent_id) REFERENCES agents(tenant_id, id) ON DELETE RESTRICT`.
- `ticket_events_actor_user_id_fk`: `FOREIGN KEY (actor_user_id) REFERENCES users(id) ON DELETE RESTRICT`.
- `ticket_events_causation_event_id_fk`: `FOREIGN KEY (tenant_id, causation_event_id) REFERENCES ticket_events(tenant_id, id) ON DELETE RESTRICT`.
- `ticket_events_pkey`: `PRIMARY KEY (id)`.
- `ticket_events_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `ticket_events_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `ticket_events_ticket_id_fk`: `FOREIGN KEY (tenant_id, ticket_id) REFERENCES tickets(tenant_id, id) ON DELETE RESTRICT`.
- `ticket_events_unique_0`: `UNIQUE (ticket_id, seq)`.
- `ticket_events_unique_1`: `UNIQUE (ticket_id, idempotency_key)`.

Chỉ mục:

- `CREATE UNIQUE INDEX ticket_events_pkey ON public.ticket_events USING btree (id)`.
- `CREATE UNIQUE INDEX ticket_events_tenant_key_uq ON public.ticket_events USING btree (tenant_id, id)`.
- `CREATE INDEX ticket_events_ticket_id_idx ON public.ticket_events USING btree (tenant_id, ticket_id)`.
- `CREATE UNIQUE INDEX ticket_events_unique_0 ON public.ticket_events USING btree (ticket_id, seq)`.
- `CREATE UNIQUE INDEX ticket_events_unique_1 ON public.ticket_events USING btree (ticket_id, idempotency_key)`.

### ticket_files

Ảnh và chứng cứ sự cố

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **6/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `tenant_id` | `uuid` | True | PK/FK | `—` | Tenant sở hữu dữ liệu |
| `ticket_id` | `uuid` | True | PK/FK | `—` | Tham chiếu nguồn chuẩn của yêu cầu cư dân |
| `file_id` | `uuid` | True | PK/FK | `—` | Tham chiếu metadata file dùng chung |
| `event_id` | `uuid` | False | FK | `—` | Tham chiếu lịch sử nghiệp vụ bất biến |
| `purpose` | `text` | True | — | `—` | Vai trò chức năng agent hoặc mục đích file |
| `uploaded_by` | `text` | True | FK | `—` | Tham chiếu tài khoản người dùng chung của platform |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `evidence_id` | `uuid` | False | FK | `—` | Tham chiếu evidence_items |

Ràng buộc:

- `ticket_files_check_0`: `CHECK (purpose = ANY (ARRAY['issue'::text, 'before'::text, 'after'::text, 'other'::text]))`.
- `ticket_files_event_id_fk`: `FOREIGN KEY (tenant_id, event_id) REFERENCES ticket_events(tenant_id, id) ON DELETE RESTRICT`.
- `ticket_files_evidence_id_fk`: `FOREIGN KEY (tenant_id, evidence_id) REFERENCES evidence_items(tenant_id, id) ON DELETE RESTRICT`.
- `ticket_files_file_id_fk`: `FOREIGN KEY (tenant_id, file_id) REFERENCES files(tenant_id, id) ON DELETE RESTRICT`.
- `ticket_files_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `ticket_files_tenant_id_ticket_id_file_id_pk`: `PRIMARY KEY (tenant_id, ticket_id, file_id)`.
- `ticket_files_ticket_id_fk`: `FOREIGN KEY (tenant_id, ticket_id) REFERENCES tickets(tenant_id, id) ON DELETE RESTRICT`.
- `ticket_files_uploaded_by_fk`: `FOREIGN KEY (uploaded_by) REFERENCES users(id) ON DELETE RESTRICT`.

Chỉ mục:

- `CREATE UNIQUE INDEX ticket_files_tenant_id_ticket_id_file_id_pk ON public.ticket_files USING btree (tenant_id, ticket_id, file_id)`.

### ticket_reviews

Đánh giá từng nhân viên

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **5/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `ticket_id` | `uuid` | True | FK | `—` | Tham chiếu nguồn chuẩn của yêu cầu cư dân |
| `assignment_id` | `uuid` | True | FK | `—` | Tham chiếu lịch sử phân công có nhận việc |
| `reviewer_user_id` | `text` | True | FK | `—` | Tham chiếu tài khoản người dùng chung của platform |
| `staff_id` | `uuid` | True | FK | `—` | Tham chiếu thông tin vận hành nhân viên |
| `score` | `smallint` | True | — | `—` | Điểm từ 1 đến 5 |
| `comment` | `text` | False | — | `—` | Nhận xét |
| `submitted_at` | `timestamp with time zone` | True | — | `—` | Thời điểm gửi |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |

Ràng buộc:

- `ticket_reviews_assignment_id_fk`: `FOREIGN KEY (tenant_id, assignment_id) REFERENCES work_assignments(tenant_id, id) ON DELETE RESTRICT`.
- `ticket_reviews_check_0`: `CHECK (score >= 1 AND score <= 5)`.
- `ticket_reviews_pkey`: `PRIMARY KEY (id)`.
- `ticket_reviews_reviewer_user_id_fk`: `FOREIGN KEY (reviewer_user_id) REFERENCES users(id) ON DELETE RESTRICT`.
- `ticket_reviews_staff_id_fk`: `FOREIGN KEY (tenant_id, staff_id) REFERENCES staff_profiles(tenant_id, id) ON DELETE RESTRICT`.
- `ticket_reviews_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `ticket_reviews_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `ticket_reviews_ticket_id_fk`: `FOREIGN KEY (tenant_id, ticket_id) REFERENCES tickets(tenant_id, id) ON DELETE RESTRICT`.
- `ticket_reviews_unique_0`: `UNIQUE (ticket_id, assignment_id, reviewer_user_id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX ticket_reviews_pkey ON public.ticket_reviews USING btree (id)`.
- `CREATE UNIQUE INDEX ticket_reviews_tenant_key_uq ON public.ticket_reviews USING btree (tenant_id, id)`.
- `CREATE INDEX ticket_reviews_ticket_id_idx ON public.ticket_reviews USING btree (tenant_id, ticket_id)`.
- `CREATE UNIQUE INDEX ticket_reviews_unique_0 ON public.ticket_reviews USING btree (ticket_id, assignment_id, reviewer_user_id)`.

### ticket_routing_history

Chuyển tuyến và ACK

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **6/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `ticket_id` | `uuid` | True | FK | `—` | Tham chiếu nguồn chuẩn của yêu cầu cư dân |
| `from_management_id` | `uuid` | False | FK | `—` | Tham chiếu ban quản lý như một tổ chức |
| `to_management_id` | `uuid` | True | FK | `—` | Tham chiếu ban quản lý như một tổ chức |
| `team_id` | `uuid` | False | FK | `—` | Tham chiếu một phiên cộng tác |
| `status` | `text` | True | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `reason` | `text` | True | — | `—` | Lý do |
| `ack_event_id` | `uuid` | False | FK | `—` | Tham chiếu lịch sử nghiệp vụ bất biến |
| `requested_at` | `timestamp with time zone` | True | — | `—` | Thời điểm yêu cầu |
| `acknowledged_at` | `timestamp with time zone` | False | — | `—` | Thời điểm ACK điều phối |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |

Ràng buộc:

- `ticket_routing_history_ack_event_id_fk`: `FOREIGN KEY (tenant_id, ack_event_id) REFERENCES ticket_events(tenant_id, id) ON DELETE RESTRICT`.
- `ticket_routing_history_check_0`: `CHECK (status = ANY (ARRAY['requested'::text, 'accepted'::text, 'rejected'::text, 'timeout'::text]))`.
- `ticket_routing_history_from_management_id_fk`: `FOREIGN KEY (tenant_id, from_management_id) REFERENCES management_units(tenant_id, id) ON DELETE RESTRICT`.
- `ticket_routing_history_pkey`: `PRIMARY KEY (id)`.
- `ticket_routing_history_team_id_fk`: `FOREIGN KEY (tenant_id, team_id) REFERENCES agent_teams(tenant_id, id) ON DELETE RESTRICT`.
- `ticket_routing_history_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `ticket_routing_history_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `ticket_routing_history_ticket_id_fk`: `FOREIGN KEY (tenant_id, ticket_id) REFERENCES tickets(tenant_id, id) ON DELETE RESTRICT`.
- `ticket_routing_history_to_management_id_fk`: `FOREIGN KEY (tenant_id, to_management_id) REFERENCES management_units(tenant_id, id) ON DELETE RESTRICT`.

Chỉ mục:

- `CREATE UNIQUE INDEX ticket_routing_history_pkey ON public.ticket_routing_history USING btree (id)`.
- `CREATE UNIQUE INDEX ticket_routing_history_tenant_key_uq ON public.ticket_routing_history USING btree (tenant_id, id)`.
- `CREATE INDEX ticket_routing_history_ticket_id_idx ON public.ticket_routing_history USING btree (tenant_id, ticket_id)`.

### ticket_assessments

Đề xuất đánh giá bất biến từ Reception chuyên gia hoặc người phụ trách

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **6/5**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `ticket_id` | `uuid` | True | FK | `—` | Tham chiếu tickets.id |
| `ticket_generation` | `integer` | True | — | `—` | Snapshot tickets.reopen_count |
| `basis_ticket_version` | `bigint` | True | — | `—` | Version của ticket mà người đánh giá đã đọc |
| `basis_decision_id` | `uuid` | False | FK | `—` | Tham chiếu ticket_triage_decisions.id |
| `stage` | `text` | True | — | `—` | intake/specialist/onsite/reassessment |
| `assessor_kind` | `text` | True | — | `—` | agent/human/system |
| `assessor_user_id` | `text` | False | FK | `—` | Tham chiếu users.id |
| `source_run_id` | `uuid` | False | FK | `—` | Tham chiếu agent_runs.id |
| `input_schema_version` | `text` | True | — | `—` | Phiên bản facts schema đã sử dụng |
| `facts` | `jsonb` | True | — | `—` | Facts có value, observed_at, provenance, confidence nếu có; không chứa chain-of-thought |
| `proposed_severity` | `text` | True | — | `—` | unknown/minor/moderate/major/critical/not_applicable |
| `proposed_urgency` | `text` | True | — | `—` | unknown/routine/soon/immediate |
| `proposed_priority` | `text` | False | — | `—` | Đề xuất low/normal/high/critical; NULL chưa đề xuất |
| `confidence` | `numeric(5,4)` | False | — | `—` | Tự báo độ chắc chắn 0..1; không phải xác suất đã hiệu chuẩn |
| `rationale` | `text` | True | — | `—` | Giải thích nghiệp vụ ngắn, dựa trên dữ kiện |
| `observed_at` | `timestamp with time zone` | True | — | `—` | Thời điểm sự kiện/dữ kiện được quan sát |
| `submitted_at` | `timestamp with time zone` | True | — | `—` | Thời điểm server nhận đánh giá |
| `idempotency_key` | `text` | True | — | `—` | Khóa chống lặp trong ticket |
| `supersedes_assessment_id` | `uuid` | False | FK | `—` | Tham chiếu ticket_assessments.id |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm server ghi nhận |

Ràng buộc:

- `ticket_assessments_assessor_user_id_fk`: `FOREIGN KEY (assessor_user_id) REFERENCES users(id) ON DELETE RESTRICT`.
- `ticket_assessments_basis_decision_id_fk`: `FOREIGN KEY (tenant_id, basis_decision_id) REFERENCES ticket_triage_decisions(tenant_id, id) ON DELETE RESTRICT`.
- `ticket_assessments_check_0`: `CHECK (ticket_generation >= 0 AND basis_ticket_version >= 0)`.
- `ticket_assessments_check_1`: `CHECK (confidence IS NULL OR confidence >= 0::numeric AND confidence <= 1::numeric)`.
- `ticket_assessments_check_2`: `CHECK (assessor_kind = 'agent'::text AND source_run_id IS NOT NULL AND assessor_user_id IS NULL OR assessor_kind = 'human'::text AND assessor_user_id IS NOT NULL AND source_run_id IS NULL OR assessor_kind = 'system'::text AND assessor_user_id IS NULL AND source_run_id IS NULL)`.
- `ticket_assessments_check_3`: `CHECK (stage = ANY (ARRAY['intake'::text, 'specialist'::text, 'onsite'::text, 'reassessment'::text]))`.
- `ticket_assessments_check_4`: `CHECK (assessor_kind = ANY (ARRAY['agent'::text, 'human'::text, 'system'::text]))`.
- `ticket_assessments_check_5`: `CHECK (proposed_severity = ANY (ARRAY['unknown'::text, 'minor'::text, 'moderate'::text, 'major'::text, 'critical'::text, 'not_applicable'::text]))`.
- `ticket_assessments_check_6`: `CHECK (proposed_urgency = ANY (ARRAY['unknown'::text, 'routine'::text, 'soon'::text, 'immediate'::text]))`.
- `ticket_assessments_pkey`: `PRIMARY KEY (id)`.
- `ticket_assessments_source_run_id_fk`: `FOREIGN KEY (tenant_id, source_run_id) REFERENCES agent_runs(tenant_id, id) ON DELETE RESTRICT`.
- `ticket_assessments_supersedes_assessment_id_fk`: `FOREIGN KEY (tenant_id, supersedes_assessment_id) REFERENCES ticket_assessments(tenant_id, id) ON DELETE RESTRICT`.
- `ticket_assessments_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `ticket_assessments_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `ticket_assessments_ticket_id_fk`: `FOREIGN KEY (tenant_id, ticket_id) REFERENCES tickets(tenant_id, id) ON DELETE RESTRICT`.
- `ticket_assessments_unique_0`: `UNIQUE (ticket_id, idempotency_key)`.

Chỉ mục:

- `CREATE UNIQUE INDEX ticket_assessments_pkey ON public.ticket_assessments USING btree (id)`.
- `CREATE UNIQUE INDEX ticket_assessments_tenant_key_uq ON public.ticket_assessments USING btree (tenant_id, id)`.
- `CREATE INDEX ticket_assessments_ticket_id_idx ON public.ticket_assessments USING btree (tenant_id, ticket_id)`.
- `CREATE UNIQUE INDEX ticket_assessments_unique_0 ON public.ticket_assessments USING btree (ticket_id, idempotency_key)`.

### ticket_assessment_evidence

Nguồn chứng minh cho từng dữ kiện của đánh giá

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **6/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `assessment_id` | `uuid` | True | FK | `—` | Tham chiếu ticket_assessments.id |
| `fact_key` | `text` | True | — | `—` | Khóa hoặc JSON pointer có trong facts schema |
| `message_id` | `uuid` | False | FK | `—` | Tham chiếu messages.id |
| `event_id` | `uuid` | False | FK | `—` | Tham chiếu ticket_events.id |
| `evidence_item_id` | `uuid` | False | FK | `—` | Tham chiếu evidence_items.id |
| `object_id` | `uuid` | False | FK | `—` | Tham chiếu file_objects.id |
| `source_hash` | `text` | True | — | `—` | SHA256 nội dung snapshot hoặc object gốc |
| `excerpt_redacted` | `text` | False | — | `—` | Trích yếu đã giảm PII; có thể NULL |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm server ghi nhận |

Ràng buộc:

- `ticket_assessment_evidence_assessment_id_fk`: `FOREIGN KEY (tenant_id, assessment_id) REFERENCES ticket_assessments(tenant_id, id) ON DELETE RESTRICT`.
- `ticket_assessment_evidence_check_0`: `CHECK (num_nonnulls(message_id, event_id, evidence_item_id) = 1)`.
- `ticket_assessment_evidence_check_1`: `CHECK ((evidence_item_id IS NULL) = (object_id IS NULL))`.
- `ticket_assessment_evidence_event_id_fk`: `FOREIGN KEY (tenant_id, event_id) REFERENCES ticket_events(tenant_id, id) ON DELETE RESTRICT`.
- `ticket_assessment_evidence_evidence_item_id_fk`: `FOREIGN KEY (tenant_id, evidence_item_id) REFERENCES evidence_items(tenant_id, id) ON DELETE RESTRICT`.
- `ticket_assessment_evidence_message_id_fk`: `FOREIGN KEY (tenant_id, message_id) REFERENCES messages(tenant_id, id) ON DELETE RESTRICT`.
- `ticket_assessment_evidence_object_id_fk`: `FOREIGN KEY (tenant_id, object_id) REFERENCES file_objects(tenant_id, id) ON DELETE RESTRICT`.
- `ticket_assessment_evidence_pkey`: `PRIMARY KEY (id)`.
- `ticket_assessment_evidence_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `ticket_assessment_evidence_tenant_key_uq`: `UNIQUE (tenant_id, id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX ticket_assessment_evidence_partial_0 ON public.ticket_assessment_evidence USING btree (assessment_id, fact_key, message_id) WHERE (message_id IS NOT NULL)`.
- `CREATE UNIQUE INDEX ticket_assessment_evidence_partial_1 ON public.ticket_assessment_evidence USING btree (assessment_id, fact_key, event_id) WHERE (event_id IS NOT NULL)`.
- `CREATE UNIQUE INDEX ticket_assessment_evidence_partial_2 ON public.ticket_assessment_evidence USING btree (assessment_id, fact_key, evidence_item_id) WHERE (evidence_item_id IS NOT NULL)`.
- `CREATE UNIQUE INDEX ticket_assessment_evidence_pkey ON public.ticket_assessment_evidence USING btree (id)`.
- `CREATE UNIQUE INDEX ticket_assessment_evidence_tenant_key_uq ON public.ticket_assessment_evidence USING btree (tenant_id, id)`.

### triage_policy_versions

Phiên bản chính sách phân loại mức độ và ưu tiên

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **1**. RLS/FORCE: **True/True**. FK ra/vào: **4/3**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `domain_id` | `uuid` | True | FK | `—` | Tham chiếu domains.id |
| `policy_code` | `text` | True | — | `—` | Mã dòng chính sách trong domain |
| `version_no` | `integer` | True | — | `—` | Phiên bản dương, không sửa nội dung sau publish |
| `status` | `text` | True | — | `—` | draft/published/retired |
| `engine_version` | `text` | True | — | `—` | Phiên bản bộ diễn giải rule cần để tái hiện |
| `input_schema_version` | `text` | True | — | `—` | Phiên bản JSON Schema facts, bao gồm kiểu và đơn vị |
| `input_schema` | `jsonb` | True | — | `—` | Schema facts allowlist; unknown khác false |
| `unknown_priority` | `text` | True | — | `—` | Ưu tiên dự phòng khi thiếu thông tin: normal/high/critical |
| `review_timeout_seconds` | `integer` | True | — | `—` | Hạn yêu cầu người có thẩm quyền xác minh; >0 |
| `max_fact_age_seconds` | `integer` | True | — | `—` | Ngưỡng facts cần xác minh lại; >0 |
| `max_queue_wait_seconds` | `integer` | True | — | `—` | Ngưỡng chờ cần escalation; >0 |
| `policy_hash` | `text` | True | — | `—` | SHA256 canonical của schema, tham số và toàn bộ rules |
| `created_by` | `text` | True | FK | `—` | Tham chiếu users.id |
| `published_by` | `text` | False | FK | `—` | Tham chiếu users.id |
| `published_at` | `timestamp with time zone` | False | — | `—` | Thời điểm publish |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm server ghi nhận |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật bởi transaction nghiệp vụ |

Ràng buộc:

- `triage_policy_versions_check_0`: `CHECK (version_no > 0)`.
- `triage_policy_versions_check_1`: `CHECK (unknown_priority = ANY (ARRAY['normal'::text, 'high'::text, 'critical'::text]))`.
- `triage_policy_versions_check_2`: `CHECK (review_timeout_seconds > 0 AND max_fact_age_seconds > 0 AND max_queue_wait_seconds > 0)`.
- `triage_policy_versions_check_3`: `CHECK (status <> 'published'::text OR published_by IS NOT NULL AND published_at IS NOT NULL)`.
- `triage_policy_versions_check_4`: `CHECK (status = ANY (ARRAY['draft'::text, 'published'::text, 'retired'::text]))`.
- `triage_policy_versions_created_by_fk`: `FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT`.
- `triage_policy_versions_domain_id_fk`: `FOREIGN KEY (tenant_id, domain_id) REFERENCES domains(tenant_id, id) ON DELETE RESTRICT`.
- `triage_policy_versions_pkey`: `PRIMARY KEY (id)`.
- `triage_policy_versions_published_by_fk`: `FOREIGN KEY (published_by) REFERENCES users(id) ON DELETE RESTRICT`.
- `triage_policy_versions_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `triage_policy_versions_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `triage_policy_versions_unique_0`: `UNIQUE (tenant_id, domain_id, policy_code, version_no)`.

Chỉ mục:

- `CREATE UNIQUE INDEX triage_policy_versions_pkey ON public.triage_policy_versions USING btree (id)`.
- `CREATE UNIQUE INDEX triage_policy_versions_tenant_key_uq ON public.triage_policy_versions USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX triage_policy_versions_unique_0 ON public.triage_policy_versions USING btree (tenant_id, domain_id, policy_code, version_no)`.

### triage_policy_bindings

Gắn chính sách vào domain địa bàn và loại dịch vụ

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **1**. RLS/FORCE: **True/True**. FK ra/vào: **6/1**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `domain_id` | `uuid` | True | FK | `—` | Tham chiếu domains.id |
| `scope_id` | `uuid` | True | FK | `—` | Tham chiếu access_scopes.id |
| `category_id` | `uuid` | False | FK | `—` | Tham chiếu service_categories.id |
| `request_kind` | `text` | True | — | `—` | incident/service_request |
| `policy_version_id` | `uuid` | True | FK | `—` | Tham chiếu triage_policy_versions.id |
| `valid_from` | `timestamp with time zone` | True | — | `—` | Bắt đầu áp dụng |
| `valid_to` | `timestamp with time zone` | False | — | `—` | Kết thúc loại trừ, NULL vô hạn |
| `status` | `text` | True | — | `—` | active/disabled |
| `configured_by` | `text` | True | FK | `—` | Tham chiếu users.id |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm server ghi nhận |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật bởi transaction nghiệp vụ |

Ràng buộc:

- `triage_binding_category_excl`: `EXCLUDE USING gist (tenant_id WITH =, domain_id WITH =, scope_id WITH =, category_id WITH =, request_kind WITH =, tstzrange(valid_from, valid_to, '[)'::text) WITH &&) WHERE (status = 'active'::text AND category_id IS NOT NULL)`.
- `triage_binding_fallback_excl`: `EXCLUDE USING gist (tenant_id WITH =, domain_id WITH =, scope_id WITH =, request_kind WITH =, tstzrange(valid_from, valid_to, '[)'::text) WITH &&) WHERE (status = 'active'::text AND category_id IS NULL)`.
- `triage_policy_bindings_category_id_fk`: `FOREIGN KEY (tenant_id, category_id) REFERENCES service_categories(tenant_id, id) ON DELETE RESTRICT`.
- `triage_policy_bindings_check_0`: `CHECK (valid_to IS NULL OR valid_to > valid_from)`.
- `triage_policy_bindings_check_1`: `CHECK (request_kind = ANY (ARRAY['incident'::text, 'service_request'::text]))`.
- `triage_policy_bindings_check_2`: `CHECK (status = ANY (ARRAY['active'::text, 'disabled'::text]))`.
- `triage_policy_bindings_configured_by_fk`: `FOREIGN KEY (configured_by) REFERENCES users(id) ON DELETE RESTRICT`.
- `triage_policy_bindings_domain_id_fk`: `FOREIGN KEY (tenant_id, domain_id) REFERENCES domains(tenant_id, id) ON DELETE RESTRICT`.
- `triage_policy_bindings_pkey`: `PRIMARY KEY (id)`.
- `triage_policy_bindings_policy_version_id_fk`: `FOREIGN KEY (tenant_id, policy_version_id) REFERENCES triage_policy_versions(tenant_id, id) ON DELETE RESTRICT`.
- `triage_policy_bindings_scope_id_fk`: `FOREIGN KEY (tenant_id, scope_id) REFERENCES access_scopes(tenant_id, id) ON DELETE RESTRICT`.
- `triage_policy_bindings_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `triage_policy_bindings_tenant_key_uq`: `UNIQUE (tenant_id, id)`.

Chỉ mục:

- `CREATE INDEX triage_binding_category_excl ON public.triage_policy_bindings USING gist (tenant_id, domain_id, scope_id, category_id, request_kind, tstzrange(valid_from, valid_to, '[)'::text)) WHERE ((status = 'active'::text) AND (category_id IS NOT NULL))`.
- `CREATE INDEX triage_binding_fallback_excl ON public.triage_policy_bindings USING gist (tenant_id, domain_id, scope_id, request_kind, tstzrange(valid_from, valid_to, '[)'::text)) WHERE ((status = 'active'::text) AND (category_id IS NULL))`.
- `CREATE UNIQUE INDEX triage_policy_bindings_pkey ON public.triage_policy_bindings USING btree (id)`.
- `CREATE UNIQUE INDEX triage_policy_bindings_tenant_key_uq ON public.triage_policy_bindings USING btree (tenant_id, id)`.

### triage_rules

Các điều kiện và kết quả do backend thực thi xác định

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **2/1**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `policy_version_id` | `uuid` | True | FK | `—` | Tham chiếu triage_policy_versions.id |
| `rule_code` | `text` | True | — | `—` | Mã ổn định trong policy version |
| `rule_kind` | `text` | True | — | `—` | emergency_floor/decision |
| `precedence` | `integer` | True | — | `—` | Thứ tự dương trong từng loại rule |
| `condition_expr` | `jsonb` | True | — | `—` | AST allowlist: all/any/not/eq/in/gt/gte/exists; không code tự do |
| `severity_result` | `text` | True | — | `—` | minor/moderate/major/critical; decision cho service_request cho phép not_applicable |
| `priority_result` | `text` | True | — | `—` | low/normal/high/critical; emergency_floor là mức sàn |
| `requires_human_review` | `boolean` | True | — | `false` | Bắt buộc mở phiếu xác minh |
| `reason_template` | `text` | True | — | `—` | Mẫu giải thích có mã facts, không chứa PII cố định |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm server ghi nhận |

Ràng buộc:

- `triage_rules_check_0`: `CHECK (precedence > 0)`.
- `triage_rules_check_1`: `CHECK (rule_kind <> 'emergency_floor'::text OR severity_result <> 'not_applicable'::text)`.
- `triage_rules_check_2`: `CHECK (rule_kind = ANY (ARRAY['emergency_floor'::text, 'decision'::text]))`.
- `triage_rules_check_3`: `CHECK (severity_result = ANY (ARRAY['minor'::text, 'moderate'::text, 'major'::text, 'critical'::text]))`.
- `triage_rules_check_4`: `CHECK (priority_result = ANY (ARRAY['low'::text, 'normal'::text, 'high'::text, 'critical'::text]))`.
- `triage_rules_pkey`: `PRIMARY KEY (id)`.
- `triage_rules_policy_version_id_fk`: `FOREIGN KEY (tenant_id, policy_version_id) REFERENCES triage_policy_versions(tenant_id, id) ON DELETE RESTRICT`.
- `triage_rules_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `triage_rules_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `triage_rules_unique_0`: `UNIQUE (policy_version_id, rule_code)`.
- `triage_rules_unique_1`: `UNIQUE (policy_version_id, rule_kind, precedence)`.

Chỉ mục:

- `CREATE UNIQUE INDEX triage_rules_pkey ON public.triage_rules USING btree (id)`.
- `CREATE UNIQUE INDEX triage_rules_tenant_key_uq ON public.triage_rules USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX triage_rules_unique_0 ON public.triage_rules USING btree (policy_version_id, rule_code)`.
- `CREATE UNIQUE INDEX triage_rules_unique_1 ON public.triage_rules USING btree (policy_version_id, rule_kind, precedence)`.

### ticket_triage_decisions

Kết quả engine và quyết định áp dụng ưu tiên có nguồn gốc

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **9/11**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `ticket_id` | `uuid` | True | FK | `—` | Tham chiếu tickets.id |
| `ticket_generation` | `integer` | True | — | `—` | Thế hệ ticket |
| `decision_seq` | `integer` | True | — | `—` | Thứ tự tăng dưới khóa ticket |
| `assessment_id` | `uuid` | True | FK | `—` | Tham chiếu ticket_assessments.id |
| `policy_binding_id` | `uuid` | True | FK | `—` | Tham chiếu triage_policy_bindings.id |
| `policy_version_id` | `uuid` | True | FK | `—` | Tham chiếu triage_policy_versions.id |
| `matched_rule_id` | `uuid` | False | FK | `—` | Tham chiếu triage_rules.id |
| `previous_applied_id` | `uuid` | False | FK | `—` | Tham chiếu ticket_triage_decisions.id |
| `review_id` | `uuid` | False | FK | `—` | Tham chiếu ticket_triage_reviews.id |
| `outcome` | `text` | True | — | `—` | applied/review_required/rejected/stale |
| `decision_mode` | `text` | True | — | `—` | automatic/provisional/human_confirmed/human_override |
| `severity` | `text` | True | — | `—` | unknown/minor/moderate/major/critical/not_applicable |
| `priority` | `text` | True | — | `—` | low/normal/high/critical |
| `is_emergency` | `boolean` | True | — | `—` | Cờ lane khẩn, chỉ từ rule floor hoặc người được phép xác nhận |
| `evaluation_trace` | `jsonb` | True | — | `—` | Mã rules đã xét, floor rules, facts còn thiếu, hash policy/engine; không raw reasoning |
| `reason` | `text` | True | — | `—` | Lý do áp dụng hoặc không áp dụng |
| `basis_ticket_version` | `bigint` | True | — | `—` | Version CAS đầu vào |
| `applied_ticket_version` | `bigint` | False | — | `—` | Version ticket sau apply, chỉ khi outcome=applied |
| `decided_at` | `timestamp with time zone` | True | — | `—` | Thời điểm backend quyết định |
| `approved_by` | `text` | False | FK | `—` | Tham chiếu users.id |
| `idempotency_key` | `text` | True | — | `—` | Khóa duy nhất trong ticket |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm server ghi nhận |

Ràng buộc:

- `applied_decision_projection`: `TRIGGER DEFERRABLE INITIALLY DEFERRED`.
- `ticket_triage_decisions_approved_by_fk`: `FOREIGN KEY (approved_by) REFERENCES users(id) ON DELETE RESTRICT`.
- `ticket_triage_decisions_assessment_id_fk`: `FOREIGN KEY (tenant_id, assessment_id) REFERENCES ticket_assessments(tenant_id, id) ON DELETE RESTRICT`.
- `ticket_triage_decisions_check_0`: `CHECK (ticket_generation >= 0 AND decision_seq > 0)`.
- `ticket_triage_decisions_check_1`: `CHECK (NOT is_emergency OR priority = 'critical'::text)`.
- `ticket_triage_decisions_check_2`: `CHECK ((outcome = 'applied'::text) = (applied_ticket_version IS NOT NULL))`.
- `ticket_triage_decisions_check_3`: `CHECK ((decision_mode = ANY (ARRAY['human_confirmed'::text, 'human_override'::text])) AND approved_by IS NOT NULL AND review_id IS NOT NULL OR (decision_mode = ANY (ARRAY['automatic'::text, 'provisional'::text])) AND approved_by IS NULL)`.
- `ticket_triage_decisions_check_4`: `CHECK (outcome = ANY (ARRAY['applied'::text, 'review_required'::text, 'rejected'::text, 'stale'::text]))`.
- `ticket_triage_decisions_check_5`: `CHECK (decision_mode = ANY (ARRAY['automatic'::text, 'provisional'::text, 'human_confirmed'::text, 'human_override'::text]))`.
- `ticket_triage_decisions_check_6`: `CHECK (severity = ANY (ARRAY['unknown'::text, 'minor'::text, 'moderate'::text, 'major'::text, 'critical'::text, 'not_applicable'::text]))`.
- `ticket_triage_decisions_check_7`: `CHECK (priority = ANY (ARRAY['low'::text, 'normal'::text, 'high'::text, 'critical'::text]))`.
- `ticket_triage_decisions_matched_rule_id_fk`: `FOREIGN KEY (tenant_id, matched_rule_id) REFERENCES triage_rules(tenant_id, id) ON DELETE RESTRICT`.
- `ticket_triage_decisions_pkey`: `PRIMARY KEY (id)`.
- `ticket_triage_decisions_policy_binding_id_fk`: `FOREIGN KEY (tenant_id, policy_binding_id) REFERENCES triage_policy_bindings(tenant_id, id) ON DELETE RESTRICT`.
- `ticket_triage_decisions_policy_version_id_fk`: `FOREIGN KEY (tenant_id, policy_version_id) REFERENCES triage_policy_versions(tenant_id, id) ON DELETE RESTRICT`.
- `ticket_triage_decisions_previous_applied_id_fk`: `FOREIGN KEY (tenant_id, previous_applied_id) REFERENCES ticket_triage_decisions(tenant_id, id) ON DELETE RESTRICT`.
- `ticket_triage_decisions_review_id_fk`: `FOREIGN KEY (tenant_id, review_id) REFERENCES ticket_triage_reviews(tenant_id, id) ON DELETE RESTRICT`.
- `ticket_triage_decisions_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `ticket_triage_decisions_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `ticket_triage_decisions_ticket_id_fk`: `FOREIGN KEY (tenant_id, ticket_id) REFERENCES tickets(tenant_id, id) ON DELETE RESTRICT`.
- `ticket_triage_decisions_unique_0`: `UNIQUE (ticket_id, decision_seq)`.
- `ticket_triage_decisions_unique_1`: `UNIQUE (ticket_id, idempotency_key)`.

Chỉ mục:

- `CREATE UNIQUE INDEX ticket_triage_decisions_partial_0 ON public.ticket_triage_decisions USING btree (review_id) WHERE ((review_id IS NOT NULL) AND (outcome = 'applied'::text))`.
- `CREATE UNIQUE INDEX ticket_triage_decisions_pkey ON public.ticket_triage_decisions USING btree (id)`.
- `CREATE UNIQUE INDEX ticket_triage_decisions_tenant_key_uq ON public.ticket_triage_decisions USING btree (tenant_id, id)`.
- `CREATE INDEX ticket_triage_decisions_ticket_id_idx ON public.ticket_triage_decisions USING btree (tenant_id, ticket_id)`.
- `CREATE UNIQUE INDEX ticket_triage_decisions_unique_0 ON public.ticket_triage_decisions USING btree (ticket_id, decision_seq)`.
- `CREATE UNIQUE INDEX ticket_triage_decisions_unique_1 ON public.ticket_triage_decisions USING btree (ticket_id, idempotency_key)`.

### ticket_triage_reviews

Hàng đợi người phụ trách xác minh đánh giá rủi ro

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **8/2**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `ticket_id` | `uuid` | True | FK | `—` | Tham chiếu tickets.id |
| `ticket_generation` | `integer` | True | — | `—` | Thế hệ cần xét |
| `assessment_id` | `uuid` | True | FK | `—` | Tham chiếu ticket_assessments.id |
| `pending_decision_id` | `uuid` | True | FK | `—` | Tham chiếu ticket_triage_decisions.id |
| `required_scope_id` | `uuid` | True | FK | `—` | Tham chiếu access_scopes.id |
| `reason_code` | `text` | True | — | `—` | unknown_facts/conflict/downgrade/emergency_override/overdue_review |
| `status` | `text` | True | — | `—` | pending/claimed/approved/rejected/superseded/expired |
| `due_at` | `timestamp with time zone` | True | — | `—` | Hạn xác minh từ policy, không phải hạn hoàn thành ticket |
| `claimed_by` | `text` | False | FK | `—` | Tham chiếu users.id |
| `claim_until` | `timestamp with time zone` | False | — | `—` | Hạn khóa nhận review |
| `version` | `bigint` | True | — | `0` | CAS chống hai người duyệt |
| `decided_by` | `text` | False | FK | `—` | Tham chiếu users.id |
| `decided_at` | `timestamp with time zone` | False | — | `—` | Thời điểm xử lý review |
| `decision_note` | `text` | False | — | `—` | Lý do bắt buộc khi kết luận |
| `result_decision_id` | `uuid` | False | FK | `—` | Tham chiếu ticket_triage_decisions.id |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm server ghi nhận |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật bởi transaction nghiệp vụ |

Ràng buộc:

- `ticket_triage_reviews_assessment_id_fk`: `FOREIGN KEY (tenant_id, assessment_id) REFERENCES ticket_assessments(tenant_id, id) ON DELETE RESTRICT`.
- `ticket_triage_reviews_check_0`: `CHECK (reason_code = ANY (ARRAY['unknown_facts'::text, 'conflict'::text, 'downgrade'::text, 'emergency_override'::text, 'overdue_review'::text]))`.
- `ticket_triage_reviews_check_1`: `CHECK (status = ANY (ARRAY['pending'::text, 'claimed'::text, 'approved'::text, 'rejected'::text, 'superseded'::text, 'expired'::text]))`.
- `ticket_triage_reviews_claimed_by_fk`: `FOREIGN KEY (claimed_by) REFERENCES users(id) ON DELETE RESTRICT`.
- `ticket_triage_reviews_decided_by_fk`: `FOREIGN KEY (decided_by) REFERENCES users(id) ON DELETE RESTRICT`.
- `ticket_triage_reviews_pending_decision_id_fk`: `FOREIGN KEY (tenant_id, pending_decision_id) REFERENCES ticket_triage_decisions(tenant_id, id) ON DELETE RESTRICT`.
- `ticket_triage_reviews_pkey`: `PRIMARY KEY (id)`.
- `ticket_triage_reviews_required_scope_id_fk`: `FOREIGN KEY (tenant_id, required_scope_id) REFERENCES access_scopes(tenant_id, id) ON DELETE RESTRICT`.
- `ticket_triage_reviews_result_decision_id_fk`: `FOREIGN KEY (tenant_id, result_decision_id) REFERENCES ticket_triage_decisions(tenant_id, id) ON DELETE RESTRICT`.
- `ticket_triage_reviews_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `ticket_triage_reviews_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `ticket_triage_reviews_ticket_id_fk`: `FOREIGN KEY (tenant_id, ticket_id) REFERENCES tickets(tenant_id, id) ON DELETE RESTRICT`.
- `ticket_triage_reviews_unique_0`: `UNIQUE (pending_decision_id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX ticket_triage_reviews_pkey ON public.ticket_triage_reviews USING btree (id)`.
- `CREATE UNIQUE INDEX ticket_triage_reviews_tenant_key_uq ON public.ticket_triage_reviews USING btree (tenant_id, id)`.
- `CREATE INDEX ticket_triage_reviews_ticket_id_idx ON public.ticket_triage_reviews USING btree (tenant_id, ticket_id)`.
- `CREATE UNIQUE INDEX ticket_triage_reviews_unique_0 ON public.ticket_triage_reviews USING btree (pending_decision_id)`.
- `CREATE INDEX triage_reviews_due_idx ON public.ticket_triage_reviews USING btree (tenant_id, due_at) WHERE (status = ANY (ARRAY['pending'::text, 'claimed'::text]))`.

### ticket_sla_cycles

Đồng hồ SLA riêng cho từng lần mở ticket

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **4/3**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `ticket_id` | `uuid` | True | FK | `—` | Tham chiếu tickets.id |
| `ticket_generation` | `integer` | True | — | `—` | 0 lần đầu, tăng theo reopen_count |
| `initial_policy_id` | `uuid` | True | FK | `—` | Tham chiếu sla_policies.id |
| `initial_decision_id` | `uuid` | True | FK | `—` | Tham chiếu ticket_triage_decisions.id |
| `started_at` | `timestamp with time zone` | True | — | `—` | Mốc tiếp nhận server của lần mở này |
| `response_minutes_snapshot` | `integer` | True | — | `—` | Ngân sách phản hồi >0, chụp bất biến |
| `resolution_minutes_snapshot` | `integer` | True | — | `—` | Ngân sách giải quyết >0, chụp bất biến |
| `initial_response_due_at` | `timestamp with time zone` | True | — | `—` | Hạn phản hồi gốc bất biến |
| `initial_resolution_due_at` | `timestamp with time zone` | True | — | `—` | Hạn giải quyết gốc bất biến |
| `current_response_due_at` | `timestamp with time zone` | True | — | `—` | Hạn phản hồi sau điều chỉnh |
| `current_resolution_due_at` | `timestamp with time zone` | True | — | `—` | Hạn giải quyết sau điều chỉnh |
| `responded_at` | `timestamp with time zone` | False | — | `—` | Mốc phản hồi có ý nghĩa đầu tiên của chu kỳ |
| `resolved_at` | `timestamp with time zone` | False | — | `—` | Mốc giải quyết kỹ thuật của chu kỳ |
| `response_breached_at` | `timestamp with time zone` | False | — | `—` | Lần đầu xác định đã vi phạm phản hồi; không xóa |
| `resolution_breached_at` | `timestamp with time zone` | False | — | `—` | Lần đầu xác định đã vi phạm giải quyết; không xóa |
| `status` | `text` | True | — | `—` | active/resolved/cancelled |
| `version` | `bigint` | True | — | `0` | CAS khi điều chỉnh clock |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm server ghi nhận |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật bởi transaction nghiệp vụ |

Ràng buộc:

- `ticket_sla_cycles_check_0`: `CHECK (response_minutes_snapshot > 0 AND resolution_minutes_snapshot > 0)`.
- `ticket_sla_cycles_check_1`: `CHECK (ticket_generation >= 0)`.
- `ticket_sla_cycles_check_2`: `CHECK (status = ANY (ARRAY['active'::text, 'resolved'::text, 'cancelled'::text]))`.
- `ticket_sla_cycles_initial_decision_id_fk`: `FOREIGN KEY (tenant_id, initial_decision_id) REFERENCES ticket_triage_decisions(tenant_id, id) ON DELETE RESTRICT`.
- `ticket_sla_cycles_initial_policy_id_fk`: `FOREIGN KEY (tenant_id, initial_policy_id) REFERENCES sla_policies(tenant_id, id) ON DELETE RESTRICT`.
- `ticket_sla_cycles_pkey`: `PRIMARY KEY (id)`.
- `ticket_sla_cycles_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `ticket_sla_cycles_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `ticket_sla_cycles_ticket_id_fk`: `FOREIGN KEY (tenant_id, ticket_id) REFERENCES tickets(tenant_id, id) ON DELETE RESTRICT`.
- `ticket_sla_cycles_unique_0`: `UNIQUE (ticket_id, ticket_generation)`.

Chỉ mục:

- `CREATE UNIQUE INDEX ticket_sla_cycles_pkey ON public.ticket_sla_cycles USING btree (id)`.
- `CREATE UNIQUE INDEX ticket_sla_cycles_tenant_key_uq ON public.ticket_sla_cycles USING btree (tenant_id, id)`.
- `CREATE INDEX ticket_sla_cycles_ticket_id_idx ON public.ticket_sla_cycles USING btree (tenant_id, ticket_id)`.
- `CREATE UNIQUE INDEX ticket_sla_cycles_unique_0 ON public.ticket_sla_cycles USING btree (ticket_id, ticket_generation)`.

### ticket_sla_adjustments

Lịch sử thay đổi deadline không xóa dấu vết vi phạm

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **5/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `cycle_id` | `uuid` | True | FK | `—` | Tham chiếu ticket_sla_cycles.id |
| `decision_id` | `uuid` | True | FK | `—` | Tham chiếu ticket_triage_decisions.id |
| `target_policy_id` | `uuid` | True | FK | `—` | Tham chiếu sla_policies.id |
| `adjustment_kind` | `text` | True | — | `—` | tighten/keep/exception_extend |
| `old_response_due_at` | `timestamp with time zone` | True | — | `—` | Deadline trước thay đổi |
| `new_response_due_at` | `timestamp with time zone` | True | — | `—` | Deadline sau thay đổi |
| `old_resolution_due_at` | `timestamp with time zone` | True | — | `—` | Deadline trước thay đổi |
| `new_resolution_due_at` | `timestamp with time zone` | True | — | `—` | Deadline sau thay đổi |
| `authorized_by` | `text` | False | FK | `—` | Tham chiếu users.id |
| `reason` | `text` | True | — | `—` | Lý do nghiệp vụ |
| `idempotency_key` | `text` | True | — | `—` | Chống lặp trong cycle |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm server ghi nhận |

Ràng buộc:

- `ticket_sla_adjustments_authorized_by_fk`: `FOREIGN KEY (authorized_by) REFERENCES users(id) ON DELETE RESTRICT`.
- `ticket_sla_adjustments_check_0`: `CHECK (adjustment_kind <> 'exception_extend'::text OR authorized_by IS NOT NULL)`.
- `ticket_sla_adjustments_check_1`: `CHECK (adjustment_kind = ANY (ARRAY['tighten'::text, 'keep'::text, 'exception_extend'::text]))`.
- `ticket_sla_adjustments_cycle_id_fk`: `FOREIGN KEY (tenant_id, cycle_id) REFERENCES ticket_sla_cycles(tenant_id, id) ON DELETE RESTRICT`.
- `ticket_sla_adjustments_decision_id_fk`: `FOREIGN KEY (tenant_id, decision_id) REFERENCES ticket_triage_decisions(tenant_id, id) ON DELETE RESTRICT`.
- `ticket_sla_adjustments_pkey`: `PRIMARY KEY (id)`.
- `ticket_sla_adjustments_target_policy_id_fk`: `FOREIGN KEY (tenant_id, target_policy_id) REFERENCES sla_policies(tenant_id, id) ON DELETE RESTRICT`.
- `ticket_sla_adjustments_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `ticket_sla_adjustments_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `ticket_sla_adjustments_unique_0`: `UNIQUE (cycle_id, idempotency_key)`.
- `ticket_sla_adjustments_unique_1`: `UNIQUE (cycle_id, decision_id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX ticket_sla_adjustments_pkey ON public.ticket_sla_adjustments USING btree (id)`.
- `CREATE UNIQUE INDEX ticket_sla_adjustments_tenant_key_uq ON public.ticket_sla_adjustments USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX ticket_sla_adjustments_unique_0 ON public.ticket_sla_adjustments USING btree (cycle_id, idempotency_key)`.
- `CREATE UNIQUE INDEX ticket_sla_adjustments_unique_1 ON public.ticket_sla_adjustments USING btree (cycle_id, decision_id)`.

### ticket_escalations

Vụ việc cần người phụ trách can thiệp do khẩn cấp hoặc quá hạn

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **10/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `ticket_id` | `uuid` | True | FK | `—` | Tham chiếu tickets.id |
| `ticket_generation` | `integer` | True | — | `—` | Thế hệ ticket |
| `decision_id` | `uuid` | False | FK | `—` | Tham chiếu ticket_triage_decisions.id |
| `sla_cycle_id` | `uuid` | False | FK | `—` | Tham chiếu ticket_sla_cycles.id |
| `review_id` | `uuid` | False | FK | `—` | Tham chiếu ticket_triage_reviews.id |
| `work_order_id` | `uuid` | False | FK | `—` | Tham chiếu work_orders.id |
| `required_scope_id` | `uuid` | True | FK | `—` | Tham chiếu access_scopes.id |
| `reason_code` | `text` | True | — | `—` | emergency/response_breach/resolution_breach/review_overdue/risk_signal_pending/queue_wait/no_capacity/policy_missing |
| `dedupe_key` | `text` | True | — | `—` | Khóa ổn định theo ticket/generation/reason/nguồn |
| `status` | `text` | True | — | `—` | open/acknowledged/resolved/cancelled |
| `detected_at` | `timestamp with time zone` | True | — | `—` | Lúc backend phát hiện |
| `next_notify_at` | `timestamp with time zone` | True | — | `—` | Lần nhắc kế tiếp |
| `acknowledged_by` | `text` | False | FK | `—` | Tham chiếu users.id |
| `acknowledged_at` | `timestamp with time zone` | False | — | `—` | Thời điểm người phụ trách tiếp nhận |
| `resolved_by` | `text` | False | FK | `—` | Tham chiếu users.id |
| `resolved_at` | `timestamp with time zone` | False | — | `—` | Thời điểm xử lý escalation |
| `resolution_note` | `text` | False | — | `—` | Bằng chứng/lý do đóng |
| `assessment_id` | `uuid` | False | FK | `—` | Tham chiếu ticket_assessments.id |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm server ghi nhận |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật bởi transaction nghiệp vụ |

Ràng buộc:

- `ticket_escalations_acknowledged_by_fk`: `FOREIGN KEY (acknowledged_by) REFERENCES users(id) ON DELETE RESTRICT`.
- `ticket_escalations_assessment_id_fk`: `FOREIGN KEY (tenant_id, assessment_id) REFERENCES ticket_assessments(tenant_id, id) ON DELETE RESTRICT`.
- `ticket_escalations_check_0`: `CHECK (reason_code = ANY (ARRAY['emergency'::text, 'response_breach'::text, 'resolution_breach'::text, 'review_overdue'::text, 'risk_signal_pending'::text, 'queue_wait'::text, 'no_capacity'::text, 'policy_missing'::text]))`.
- `ticket_escalations_check_1`: `CHECK (status = ANY (ARRAY['open'::text, 'acknowledged'::text, 'resolved'::text, 'cancelled'::text]))`.
- `ticket_escalations_decision_id_fk`: `FOREIGN KEY (tenant_id, decision_id) REFERENCES ticket_triage_decisions(tenant_id, id) ON DELETE RESTRICT`.
- `ticket_escalations_pkey`: `PRIMARY KEY (id)`.
- `ticket_escalations_required_scope_id_fk`: `FOREIGN KEY (tenant_id, required_scope_id) REFERENCES access_scopes(tenant_id, id) ON DELETE RESTRICT`.
- `ticket_escalations_resolved_by_fk`: `FOREIGN KEY (resolved_by) REFERENCES users(id) ON DELETE RESTRICT`.
- `ticket_escalations_review_id_fk`: `FOREIGN KEY (tenant_id, review_id) REFERENCES ticket_triage_reviews(tenant_id, id) ON DELETE RESTRICT`.
- `ticket_escalations_sla_cycle_id_fk`: `FOREIGN KEY (tenant_id, sla_cycle_id) REFERENCES ticket_sla_cycles(tenant_id, id) ON DELETE RESTRICT`.
- `ticket_escalations_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `ticket_escalations_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `ticket_escalations_ticket_id_fk`: `FOREIGN KEY (tenant_id, ticket_id) REFERENCES tickets(tenant_id, id) ON DELETE RESTRICT`.
- `ticket_escalations_unique_0`: `UNIQUE (ticket_id, dedupe_key)`.
- `ticket_escalations_work_order_id_fk`: `FOREIGN KEY (tenant_id, work_order_id) REFERENCES work_orders(tenant_id, id) ON DELETE RESTRICT`.

Chỉ mục:

- `CREATE INDEX escalation_notify_idx ON public.ticket_escalations USING btree (tenant_id, next_notify_at) WHERE (status = ANY (ARRAY['open'::text, 'acknowledged'::text]))`.
- `CREATE UNIQUE INDEX ticket_escalations_pkey ON public.ticket_escalations USING btree (id)`.
- `CREATE UNIQUE INDEX ticket_escalations_tenant_key_uq ON public.ticket_escalations USING btree (tenant_id, id)`.
- `CREATE INDEX ticket_escalations_ticket_id_idx ON public.ticket_escalations USING btree (tenant_id, ticket_id)`.
- `CREATE UNIQUE INDEX ticket_escalations_unique_0 ON public.ticket_escalations USING btree (ticket_id, dedupe_key)`.

### dispatch_queue

Hàng chờ nhân viên rảnh

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **5/1**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `work_order_id` | `uuid` | True | FK | `—` | Tham chiếu công việc hiện trường thuộc ticket |
| `management_unit_id` | `uuid` | True | FK | `—` | Tham chiếu ban quản lý như một tổ chức |
| `category_id` | `uuid` | True | FK | `—` | Tham chiếu phân loại chuẩn cho routing và báo cáo |
| `queued_at` | `timestamp with time zone` | True | — | `—` | Thời điểm vào hàng chờ |
| `available_at` | `timestamp with time zone` | True | — | `—` | Thời điểm có thể xử lý |
| `state` | `text` | True | — | `—` | Trạng thái xử lý |
| `attempts` | `integer` | True | — | `0` | Số lần thử |
| `lease_owner` | `text` | False | — | `—` | Worker giữ lease |
| `lease_until` | `timestamp with time zone` | False | — | `—` | Thời điểm hết lease |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |
| `priority_decision_id` | `uuid` | True | FK | `—` | Tham chiếu ticket_triage_decisions.id |
| `priority_rank` | `integer` | True | — | `—` | 10 low;20 normal;30 high;40 critical |
| `is_emergency` | `boolean` | True | — | `—` | Lane khẩn từ decision |
| `dispatch_due_at` | `timestamp with time zone` | False | — | `—` | Mốc mục tiêu phân công; NULL nếu chưa cấu hình SLA |
| `eligible_since` | `timestamp with time zone` | True | — | `—` | Mốc bắt đầu đủ điều kiện tham gia hàng đợi |
| `version` | `bigint` | True | — | `0` | CAS mỗi thay đổi ảnh hưởng claim |
| `fencing_token` | `bigint` | True | — | `0` | Tăng mỗi lần cấp/thu hồi claim |

Ràng buộc:

- `dispatch_queue_category_id_fk`: `FOREIGN KEY (tenant_id, category_id) REFERENCES service_categories(tenant_id, id) ON DELETE RESTRICT`.
- `dispatch_queue_check_0`: `CHECK (priority_rank = ANY (ARRAY[10, 20, 30, 40]))`.
- `dispatch_queue_check_1`: `CHECK (NOT is_emergency OR priority_rank = 40)`.
- `dispatch_queue_check_2`: `CHECK (state = ANY (ARRAY['waiting'::text, 'claimed'::text, 'dispatched'::text, 'cancelled'::text, 'dead'::text]))`.
- `dispatch_queue_management_unit_id_fk`: `FOREIGN KEY (tenant_id, management_unit_id) REFERENCES management_units(tenant_id, id) ON DELETE RESTRICT`.
- `dispatch_queue_pkey`: `PRIMARY KEY (id)`.
- `dispatch_queue_priority_decision_id_fk`: `FOREIGN KEY (tenant_id, priority_decision_id) REFERENCES ticket_triage_decisions(tenant_id, id) ON DELETE RESTRICT`.
- `dispatch_queue_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `dispatch_queue_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `dispatch_queue_unique_0`: `UNIQUE (work_order_id)`.
- `dispatch_queue_work_order_id_fk`: `FOREIGN KEY (tenant_id, work_order_id) REFERENCES work_orders(tenant_id, id) ON DELETE RESTRICT`.

Chỉ mục:

- `CREATE UNIQUE INDEX dispatch_queue_pkey ON public.dispatch_queue USING btree (id)`.
- `CREATE INDEX dispatch_queue_priority_idx ON public.dispatch_queue USING btree (tenant_id, management_unit_id, is_emergency DESC, priority_rank DESC, dispatch_due_at, eligible_since, id) WHERE (state = 'waiting'::text)`.
- `CREATE UNIQUE INDEX dispatch_queue_tenant_key_uq ON public.dispatch_queue USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX dispatch_queue_unique_0 ON public.dispatch_queue USING btree (work_order_id)`.

### dispatch_attempts

Dấu vết mỗi lần claim và phân công có kiểm tra phiên ưu tiên

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **5/1**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `queue_id` | `uuid` | True | FK | `—` | Tham chiếu dispatch_queue.id |
| `work_order_id` | `uuid` | True | FK | `—` | Tham chiếu work_orders.id |
| `decision_id` | `uuid` | True | FK | `—` | Tham chiếu ticket_triage_decisions.id |
| `queue_version` | `bigint` | True | — | `—` | Version hàng đợi khi claim |
| `fencing_token` | `bigint` | True | — | `—` | Token chống worker hết lease ghi kết quả |
| `worker_id` | `text` | True | — | `—` | Worker đang claim |
| `priority_rank_snapshot` | `integer` | True | — | `—` | 10/20/30/40 chụp tại claim |
| `emergency_snapshot` | `boolean` | True | — | `—` | Lane khẩn tại claim |
| `status` | `text` | True | — | `—` | claimed/offered/no_capacity/stale/expired/failed |
| `claimed_at` | `timestamp with time zone` | True | — | `—` | Thời điểm claim |
| `lease_until` | `timestamp with time zone` | True | — | `—` | Hết hạn claim |
| `assignment_id` | `uuid` | False | FK | `—` | Tham chiếu work_assignments.id |
| `finished_at` | `timestamp with time zone` | False | — | `—` | Kết thúc attempt |
| `reason` | `text` | False | — | `—` | Lý do không phân công hoặc stale |
| `idempotency_key` | `text` | True | — | `—` | Khóa chống lặp mỗi queue |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm server ghi nhận |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật bởi transaction nghiệp vụ |

Ràng buộc:

- `dispatch_attempts_assignment_id_fk`: `FOREIGN KEY (tenant_id, assignment_id) REFERENCES work_assignments(tenant_id, id) ON DELETE RESTRICT`.
- `dispatch_attempts_check_0`: `CHECK (priority_rank_snapshot = ANY (ARRAY[10, 20, 30, 40]))`.
- `dispatch_attempts_check_1`: `CHECK (status <> 'offered'::text OR assignment_id IS NOT NULL)`.
- `dispatch_attempts_check_2`: `CHECK (status = ANY (ARRAY['claimed'::text, 'offered'::text, 'no_capacity'::text, 'stale'::text, 'expired'::text, 'failed'::text]))`.
- `dispatch_attempts_decision_id_fk`: `FOREIGN KEY (tenant_id, decision_id) REFERENCES ticket_triage_decisions(tenant_id, id) ON DELETE RESTRICT`.
- `dispatch_attempts_pkey`: `PRIMARY KEY (id)`.
- `dispatch_attempts_queue_id_fk`: `FOREIGN KEY (tenant_id, queue_id) REFERENCES dispatch_queue(tenant_id, id) ON DELETE RESTRICT`.
- `dispatch_attempts_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `dispatch_attempts_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `dispatch_attempts_unique_0`: `UNIQUE (queue_id, idempotency_key)`.
- `dispatch_attempts_unique_1`: `UNIQUE (queue_id, fencing_token)`.
- `dispatch_attempts_work_order_id_fk`: `FOREIGN KEY (tenant_id, work_order_id) REFERENCES work_orders(tenant_id, id) ON DELETE RESTRICT`.

Chỉ mục:

- `CREATE UNIQUE INDEX dispatch_attempts_pkey ON public.dispatch_attempts USING btree (id)`.
- `CREATE UNIQUE INDEX dispatch_attempts_tenant_key_uq ON public.dispatch_attempts USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX dispatch_attempts_unique_0 ON public.dispatch_attempts USING btree (queue_id, idempotency_key)`.
- `CREATE UNIQUE INDEX dispatch_attempts_unique_1 ON public.dispatch_attempts USING btree (queue_id, fencing_token)`.

## 09 Thực thi, phân công và nghiệm thu

### work_orders

Công việc hiện trường thuộc ticket

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **7**. RLS/FORCE: **True/True**. FK ra/vào: **4/21**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `ticket_id` | `uuid` | True | FK | `—` | Tham chiếu nguồn chuẩn của yêu cầu cư dân |
| `category_id` | `uuid` | True | FK | `—` | Tham chiếu phân loại chuẩn cho routing và báo cáo |
| `description` | `text` | True | — | `—` | Mô tả |
| `status` | `text` | True | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `required_specialty_id` | `uuid` | True | FK | `—` | Tham chiếu phân loại chuẩn cho routing và báo cáo |
| `scheduled_at` | `timestamp with time zone` | False | — | `—` | Lịch đến dự kiến |
| `arrived_at` | `timestamp with time zone` | False | — | `—` | Thời điểm đến hiện trường |
| `started_at` | `timestamp with time zone` | False | — | `—` | Thời điểm bắt đầu |
| `completed_at` | `timestamp with time zone` | False | — | `—` | Thời điểm hoàn thành |
| `diagnosis` | `text` | False | — | `—` | Kết quả chẩn đoán |
| `repair_notes` | `text` | False | — | `—` | Ghi chú sửa chữa |
| `version` | `bigint` | True | — | `0` | Phiên bản cấu hình hoặc bộ đếm chống ghi đè |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |
| `required` | `boolean` | True | — | `true` | Hạng mục bắt buộc để ticket được hoàn tất |

Ràng buộc:

- `work_orders_category_id_fk`: `FOREIGN KEY (tenant_id, category_id) REFERENCES service_categories(tenant_id, id) ON DELETE RESTRICT`.
- `work_orders_check_0`: `CHECK (status = ANY (ARRAY['queued'::text, 'offered'::text, 'accepted'::text, 'en_route'::text, 'arrived'::text, 'awaiting_approval'::text, 'in_progress'::text, 'completed'::text, 'rejected'::text, 'cancelled'::text]))`.
- `work_orders_pkey`: `PRIMARY KEY (id)`.
- `work_orders_required_specialty_id_fk`: `FOREIGN KEY (tenant_id, required_specialty_id) REFERENCES service_categories(tenant_id, id) ON DELETE RESTRICT`.
- `work_orders_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `work_orders_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `work_orders_ticket_id_fk`: `FOREIGN KEY (tenant_id, ticket_id) REFERENCES tickets(tenant_id, id) ON DELETE RESTRICT`.

Chỉ mục:

- `CREATE UNIQUE INDEX work_orders_pkey ON public.work_orders USING btree (id)`.
- `CREATE UNIQUE INDEX work_orders_tenant_key_uq ON public.work_orders USING btree (tenant_id, id)`.
- `CREATE INDEX work_orders_ticket_id_idx ON public.work_orders USING btree (tenant_id, ticket_id)`.

### work_assignments

Lịch sử phân công có nhận việc

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **6/5**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `work_order_id` | `uuid` | True | FK | `—` | Tham chiếu công việc hiện trường thuộc ticket |
| `staff_id` | `uuid` | True | FK | `—` | Tham chiếu thông tin vận hành nhân viên |
| `assigned_by_user_id` | `text` | False | FK | `—` | Tham chiếu tài khoản người dùng chung của platform |
| `assigned_by_agent_id` | `text` | False | FK | `—` | Tham chiếu danh mục agent của platform |
| `status` | `text` | True | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `offered_at` | `timestamp with time zone` | True | — | `—` | Thời điểm đề nghị nhận việc |
| `accepted_at` | `timestamp with time zone` | False | — | `—` | Thời điểm nhận việc |
| `eta_at` | `timestamp with time zone` | False | — | `—` | Giờ dự kiến đến |
| `ended_at` | `timestamp with time zone` | False | — | `—` | Thời điểm chấm dứt |
| `rejection_reason` | `text` | False | — | `—` | Lý do từ chối |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |
| `offer_expires_at` | `timestamp with time zone` | False | — | `—` | Thời điểm offer expires |
| `dispatch_attempt_id` | `uuid` | False | FK | `—` | Tham chiếu dispatch_attempts.id |

Ràng buộc:

- `work_assignments_assigned_by_agent_id_fk`: `FOREIGN KEY (tenant_id, assigned_by_agent_id) REFERENCES agents(tenant_id, id) ON DELETE RESTRICT`.
- `work_assignments_assigned_by_user_id_fk`: `FOREIGN KEY (assigned_by_user_id) REFERENCES users(id) ON DELETE RESTRICT`.
- `work_assignments_check_0`: `CHECK (status = ANY (ARRAY['offered'::text, 'accepted'::text, 'rejected'::text, 'released'::text, 'completed'::text, 'cancelled'::text]))`.
- `work_assignments_dispatch_attempt_id_fk`: `FOREIGN KEY (tenant_id, dispatch_attempt_id) REFERENCES dispatch_attempts(tenant_id, id) ON DELETE RESTRICT`.
- `work_assignments_pkey`: `PRIMARY KEY (id)`.
- `work_assignments_staff_id_fk`: `FOREIGN KEY (tenant_id, staff_id) REFERENCES staff_profiles(tenant_id, id) ON DELETE RESTRICT`.
- `work_assignments_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `work_assignments_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `work_assignments_work_order_id_fk`: `FOREIGN KEY (tenant_id, work_order_id) REFERENCES work_orders(tenant_id, id) ON DELETE RESTRICT`.

Chỉ mục:

- `CREATE UNIQUE INDEX work_assignments_partial_0 ON public.work_assignments USING btree (work_order_id) WHERE (status = ANY (ARRAY['offered'::text, 'accepted'::text]))`.
- `CREATE UNIQUE INDEX work_assignments_pkey ON public.work_assignments USING btree (id)`.
- `CREATE UNIQUE INDEX work_assignments_tenant_key_uq ON public.work_assignments USING btree (tenant_id, id)`.

### work_approvals

Chấp thuận sửa chữa hoặc can thiệp

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **6/2**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `work_order_id` | `uuid` | True | FK | `—` | Tham chiếu công việc hiện trường thuộc ticket |
| `kind` | `text` | True | — | `—` | Loại bản ghi |
| `requested_to_user_id` | `text` | False | FK | `—` | Tham chiếu tài khoản người dùng chung của platform |
| `required_scope_id` | `uuid` | False | FK | `—` | Tham chiếu phạm vi quyền có kiểu rõ ràng |
| `request_detail` | `jsonb` | True | — | `—` | Chi tiết cần phê duyệt |
| `status` | `text` | True | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `decided_by` | `text` | False | FK | `—` | Tham chiếu tài khoản người dùng chung của platform |
| `decided_at` | `timestamp with time zone` | False | — | `—` | Thời điểm ra quyết định |
| `decision_note` | `text` | False | — | `—` | Ghi chú quyết định |
| `expires_at` | `timestamp with time zone` | False | — | `—` | Thời điểm hết hạn |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |
| `evidence_cutoff_at` | `timestamp with time zone` | False | — | `—` | Thời điểm evidence cutoff |
| `request_hash` | `text` | True | — | `—` | Hash nội dung và tập chứng cứ của đề nghị duyệt |
| `decided_event_id` | `uuid` | False | FK | `—` | Tham chiếu lịch sử nghiệp vụ bất biến |

Ràng buộc:

- `work_approvals_check_0`: `CHECK (num_nonnulls(requested_to_user_id, required_scope_id) = 1)`.
- `work_approvals_check_1`: `CHECK (kind = ANY (ARRAY['customer_repair'::text, 'management_water_shutdown'::text, 'customer_completion'::text, 'management_security_dispatch'::text, 'management_security_cancel'::text]))`.
- `work_approvals_check_2`: `CHECK (status = ANY (ARRAY['pending'::text, 'approved'::text, 'rejected'::text, 'expired'::text, 'cancelled'::text]))`.
- `work_approvals_decided_by_fk`: `FOREIGN KEY (decided_by) REFERENCES users(id) ON DELETE RESTRICT`.
- `work_approvals_decided_event_id_fk`: `FOREIGN KEY (tenant_id, decided_event_id) REFERENCES ticket_events(tenant_id, id) ON DELETE RESTRICT`.
- `work_approvals_pkey`: `PRIMARY KEY (id)`.
- `work_approvals_requested_to_user_id_fk`: `FOREIGN KEY (requested_to_user_id) REFERENCES users(id) ON DELETE RESTRICT`.
- `work_approvals_required_scope_id_fk`: `FOREIGN KEY (tenant_id, required_scope_id) REFERENCES access_scopes(tenant_id, id) ON DELETE RESTRICT`.
- `work_approvals_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `work_approvals_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `work_approvals_work_order_id_fk`: `FOREIGN KEY (tenant_id, work_order_id) REFERENCES work_orders(tenant_id, id) ON DELETE RESTRICT`.

Chỉ mục:

- `CREATE UNIQUE INDEX work_approvals_pkey ON public.work_approvals USING btree (id)`.
- `CREATE UNIQUE INDEX work_approvals_tenant_key_uq ON public.work_approvals USING btree (tenant_id, id)`.

### work_approval_evidence

Danh sách chứng cứ cố định được đem ra nghiệm thu

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **4/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `approval_id` | `uuid` | True | FK | `—` | Tham chiếu chấp thuận sửa chữa hoặc can thiệp |
| `evidence_id` | `uuid` | True | FK | `—` | Tham chiếu evidence_items |
| `original_object_id` | `uuid` | True | FK | `—` | Tham chiếu file_objects |
| `sha256_snapshot` | `text` | True | — | `—` | SHA256 của object gốc tại lúc lập đề nghị |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |

Ràng buộc:

- `work_approval_evidence_approval_id_fk`: `FOREIGN KEY (tenant_id, approval_id) REFERENCES work_approvals(tenant_id, id) ON DELETE RESTRICT`.
- `work_approval_evidence_evidence_id_fk`: `FOREIGN KEY (tenant_id, evidence_id) REFERENCES evidence_items(tenant_id, id) ON DELETE RESTRICT`.
- `work_approval_evidence_original_object_id_fk`: `FOREIGN KEY (tenant_id, original_object_id) REFERENCES file_objects(tenant_id, id) ON DELETE RESTRICT`.
- `work_approval_evidence_pkey`: `PRIMARY KEY (id)`.
- `work_approval_evidence_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `work_approval_evidence_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `work_approval_evidence_unique_0`: `UNIQUE (approval_id, evidence_id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX work_approval_evidence_pkey ON public.work_approval_evidence USING btree (id)`.
- `CREATE UNIQUE INDEX work_approval_evidence_tenant_key_uq ON public.work_approval_evidence USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX work_approval_evidence_unique_0 ON public.work_approval_evidence USING btree (approval_id, evidence_id)`.

### evidence_items

Ảnh hiện trường gắn đúng công việc và lượt phân công

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **7/4**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `ticket_id` | `uuid` | True | FK | `—` | Tham chiếu nguồn chuẩn của yêu cầu cư dân |
| `work_order_id` | `uuid` | False | FK | `—` | Tham chiếu công việc hiện trường thuộc ticket |
| `assignment_id` | `uuid` | False | FK | `—` | Tham chiếu lịch sử phân công có nhận việc |
| `file_id` | `uuid` | True | FK | `—` | Tham chiếu metadata file dùng chung |
| `purpose` | `text` | True | — | `—` | Vai trò chức năng agent hoặc mục đích file |
| `captured_at` | `timestamp with time zone` | False | — | `—` | Thời điểm chụp |
| `uploaded_at` | `timestamp with time zone` | True | — | `—` | Thời điểm uploaded |
| `uploaded_by` | `text` | True | FK | `—` | Tham chiếu tài khoản người dùng chung của platform |
| `caption` | `text` | False | — | `—` | Mô tả ảnh do người dùng cung cấp |
| `provenance` | `text` | True | — | `—` | Nguồn gốc thành phần |
| `supersedes_id` | `uuid` | False | FK | `—` | Tham chiếu evidence_items |
| `status` | `text` | True | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `withdrawn_reason` | `text` | False | — | `—` | Lý do rút chứng cứ khỏi quy trình hiện tại |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |

Ràng buộc:

- `evidence_items_assignment_id_fk`: `FOREIGN KEY (tenant_id, assignment_id) REFERENCES work_assignments(tenant_id, id) ON DELETE RESTRICT`.
- `evidence_items_check_0`: `CHECK (purpose = ANY (ARRAY['issue'::text, 'before'::text, 'after'::text, 'verification'::text]))`.
- `evidence_items_check_1`: `CHECK (provenance = ANY (ARRAY['camera'::text, 'upload'::text, 'import'::text]))`.
- `evidence_items_check_2`: `CHECK (status = ANY (ARRAY['active'::text, 'withdrawn'::text]))`.
- `evidence_items_file_id_fk`: `FOREIGN KEY (tenant_id, file_id) REFERENCES files(tenant_id, id) ON DELETE RESTRICT`.
- `evidence_items_pkey`: `PRIMARY KEY (id)`.
- `evidence_items_supersedes_id_fk`: `FOREIGN KEY (tenant_id, supersedes_id) REFERENCES evidence_items(tenant_id, id) ON DELETE RESTRICT`.
- `evidence_items_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `evidence_items_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `evidence_items_ticket_id_fk`: `FOREIGN KEY (tenant_id, ticket_id) REFERENCES tickets(tenant_id, id) ON DELETE RESTRICT`.
- `evidence_items_unique_0`: `UNIQUE (ticket_id, file_id, purpose)`.
- `evidence_items_uploaded_by_fk`: `FOREIGN KEY (uploaded_by) REFERENCES users(id) ON DELETE RESTRICT`.
- `evidence_items_work_order_id_fk`: `FOREIGN KEY (tenant_id, work_order_id) REFERENCES work_orders(tenant_id, id) ON DELETE RESTRICT`.

Chỉ mục:

- `CREATE UNIQUE INDEX evidence_items_pkey ON public.evidence_items USING btree (id)`.
- `CREATE UNIQUE INDEX evidence_items_tenant_key_uq ON public.evidence_items USING btree (tenant_id, id)`.
- `CREATE INDEX evidence_items_ticket_id_idx ON public.evidence_items USING btree (tenant_id, ticket_id)`.
- `CREATE UNIQUE INDEX evidence_items_unique_0 ON public.evidence_items USING btree (ticket_id, file_id, purpose)`.

### work_reassignment_requests

Yêu cầu điều chuyển nhân viên đang xử lý việc khác

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **9/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `source_assignment_id` | `uuid` | True | FK | `—` | Tham chiếu work_assignments.id |
| `target_work_order_id` | `uuid` | True | FK | `—` | Tham chiếu work_orders.id |
| `target_decision_id` | `uuid` | True | FK | `—` | Tham chiếu ticket_triage_decisions.id |
| `requested_by` | `text` | False | FK | `—` | Tham chiếu users.id |
| `source_run_id` | `uuid` | False | FK | `—` | Tham chiếu agent_runs.id |
| `reason` | `text` | True | — | `—` | Vì sao cần điều chuyển và các lựa chọn đã kiểm tra |
| `status` | `text` | True | — | `—` | requested/approved/rejected/executing/completed/cancelled/expired |
| `approved_by` | `text` | False | FK | `—` | Tham chiếu users.id |
| `approved_at` | `timestamp with time zone` | False | — | `—` | Thời điểm cho phép điều chuyển |
| `safe_stop_confirmed_by` | `text` | False | FK | `—` | Tham chiếu users.id |
| `safe_stop_confirmed_at` | `timestamp with time zone` | False | — | `—` | Xác nhận công việc nguồn có thể dừng/chuyển giao |
| `handover_snapshot` | `jsonb` | True | — | `—` | Biên bản công việc nguồn, phần đã làm, người nhận bàn giao nếu có |
| `new_assignment_id` | `uuid` | False | FK | `—` | Tham chiếu work_assignments.id |
| `expires_at` | `timestamp with time zone` | True | — | `—` | Hạn yêu cầu |
| `idempotency_key` | `text` | True | — | `—` | Khóa chống lặp theo tenant |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm server ghi nhận |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật bởi transaction nghiệp vụ |

Ràng buộc:

- `work_reassignment_requests_approved_by_fk`: `FOREIGN KEY (approved_by) REFERENCES users(id) ON DELETE RESTRICT`.
- `work_reassignment_requests_check_0`: `CHECK (num_nonnulls(requested_by, source_run_id) = 1)`.
- `work_reassignment_requests_check_1`: `CHECK ((status <> ALL (ARRAY['executing'::text, 'completed'::text])) OR approved_by IS NOT NULL AND safe_stop_confirmed_by IS NOT NULL AND safe_stop_confirmed_at IS NOT NULL)`.
- `work_reassignment_requests_check_2`: `CHECK (status <> 'completed'::text OR new_assignment_id IS NOT NULL)`.
- `work_reassignment_requests_check_3`: `CHECK (status = ANY (ARRAY['requested'::text, 'approved'::text, 'rejected'::text, 'executing'::text, 'completed'::text, 'cancelled'::text, 'expired'::text]))`.
- `work_reassignment_requests_new_assignment_id_fk`: `FOREIGN KEY (tenant_id, new_assignment_id) REFERENCES work_assignments(tenant_id, id) ON DELETE RESTRICT`.
- `work_reassignment_requests_pkey`: `PRIMARY KEY (id)`.
- `work_reassignment_requests_requested_by_fk`: `FOREIGN KEY (requested_by) REFERENCES users(id) ON DELETE RESTRICT`.
- `work_reassignment_requests_safe_stop_confirmed_by_fk`: `FOREIGN KEY (safe_stop_confirmed_by) REFERENCES users(id) ON DELETE RESTRICT`.
- `work_reassignment_requests_source_assignment_id_fk`: `FOREIGN KEY (tenant_id, source_assignment_id) REFERENCES work_assignments(tenant_id, id) ON DELETE RESTRICT`.
- `work_reassignment_requests_source_run_id_fk`: `FOREIGN KEY (tenant_id, source_run_id) REFERENCES agent_runs(tenant_id, id) ON DELETE RESTRICT`.
- `work_reassignment_requests_target_decision_id_fk`: `FOREIGN KEY (tenant_id, target_decision_id) REFERENCES ticket_triage_decisions(tenant_id, id) ON DELETE RESTRICT`.
- `work_reassignment_requests_target_work_order_id_fk`: `FOREIGN KEY (tenant_id, target_work_order_id) REFERENCES work_orders(tenant_id, id) ON DELETE RESTRICT`.
- `work_reassignment_requests_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `work_reassignment_requests_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `work_reassignment_requests_unique_0`: `UNIQUE (tenant_id, idempotency_key)`.

Chỉ mục:

- `CREATE UNIQUE INDEX work_reassignment_requests_partial_0 ON public.work_reassignment_requests USING btree (source_assignment_id) WHERE (status = ANY (ARRAY['requested'::text, 'approved'::text, 'executing'::text]))`.
- `CREATE UNIQUE INDEX work_reassignment_requests_pkey ON public.work_reassignment_requests USING btree (id)`.
- `CREATE UNIQUE INDEX work_reassignment_requests_tenant_key_uq ON public.work_reassignment_requests USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX work_reassignment_requests_unique_0 ON public.work_reassignment_requests USING btree (tenant_id, idempotency_key)`.

## 10 Chi phí và thanh toán

### invoices

Hóa đơn theo ticket

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **20**. RLS/FORCE: **True/True**. FK ra/vào: **7/5**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `ticket_id` | `uuid` | True | FK | `—` | Tham chiếu nguồn chuẩn của yêu cầu cư dân |
| `work_order_id` | `uuid` | False | FK | `—` | Tham chiếu công việc hiện trường thuộc ticket |
| `invoice_no` | `text` | True | — | `—` | Số hóa đơn |
| `issued_by_staff_id` | `uuid` | True | FK | `—` | Tham chiếu thông tin vận hành nhân viên |
| `bill_to_user_id` | `text` | True | FK | `—` | Tham chiếu tài khoản người dùng chung của platform |
| `status` | `text` | True | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `currency` | `character(3)` | True | — | `'VND'::bpchar` | Mã tiền tệ ISO 4217 |
| `subtotal` | `numeric(18,2)` | True | — | `—` | Tổng trước thuế và giảm giá |
| `tax_total` | `numeric(18,2)` | True | — | `—` | Tổng thuế |
| `discount_total` | `numeric(18,2)` | True | — | `'0'::numeric` | Tổng giảm giá |
| `grand_total` | `numeric(18,2)` | True | — | `—` | Tổng phải thanh toán |
| `issued_at` | `timestamp with time zone` | False | — | `—` | Thời điểm phát hành |
| `due_at` | `timestamp with time zone` | False | — | `—` | Hạn thanh toán |
| `provider` | `text` | False | — | `—` | Nhà cung cấp dịch vụ |
| `provider_invoice_id` | `text` | False | — | `—` | ID hóa đơn điện tử tại provider |
| `legal_invoice_file_id` | `uuid` | False | FK | `—` | Tham chiếu metadata file dùng chung |
| `supersedes_invoice_id` | `uuid` | False | FK | `—` | Tham chiếu hóa đơn theo ticket |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |
| `provider_account_ref` | `text` | False | — | `—` | Giá trị provider_account_ref; ý nghĩa và phạm vi theo quy tắc bảng |

Ràng buộc:

- `invoices_bill_to_user_id_fk`: `FOREIGN KEY (bill_to_user_id) REFERENCES users(id) ON DELETE RESTRICT`.
- `invoices_check_0`: `CHECK (grand_total = (subtotal + tax_total - discount_total))`.
- `invoices_check_1`: `CHECK (grand_total >= 0::numeric)`.
- `invoices_check_2`: `CHECK (status = ANY (ARRAY['draft'::text, 'issued'::text, 'void'::text, 'replaced'::text]))`.
- `invoices_issued_by_staff_id_fk`: `FOREIGN KEY (tenant_id, issued_by_staff_id) REFERENCES staff_profiles(tenant_id, id) ON DELETE RESTRICT`.
- `invoices_legal_invoice_file_id_fk`: `FOREIGN KEY (tenant_id, legal_invoice_file_id) REFERENCES files(tenant_id, id) ON DELETE RESTRICT`.
- `invoices_pkey`: `PRIMARY KEY (id)`.
- `invoices_supersedes_invoice_id_fk`: `FOREIGN KEY (tenant_id, supersedes_invoice_id) REFERENCES invoices(tenant_id, id) ON DELETE RESTRICT`.
- `invoices_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `invoices_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `invoices_ticket_id_fk`: `FOREIGN KEY (tenant_id, ticket_id) REFERENCES tickets(tenant_id, id) ON DELETE RESTRICT`.
- `invoices_unique_0`: `UNIQUE (tenant_id, invoice_no)`.
- `invoices_unique_1`: `UNIQUE (provider, provider_account_ref, provider_invoice_id)`.
- `invoices_work_order_id_fk`: `FOREIGN KEY (tenant_id, work_order_id) REFERENCES work_orders(tenant_id, id) ON DELETE RESTRICT`.

Chỉ mục:

- `CREATE UNIQUE INDEX invoices_pkey ON public.invoices USING btree (id)`.
- `CREATE UNIQUE INDEX invoices_tenant_key_uq ON public.invoices USING btree (tenant_id, id)`.
- `CREATE INDEX invoices_ticket_id_idx ON public.invoices USING btree (tenant_id, ticket_id)`.
- `CREATE UNIQUE INDEX invoices_unique_0 ON public.invoices USING btree (tenant_id, invoice_no)`.
- `CREATE UNIQUE INDEX invoices_unique_1 ON public.invoices USING btree (provider, provider_account_ref, provider_invoice_id)`.

### invoice_lines

Chi tiết phí sửa chữa

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **20**. RLS/FORCE: **True/True**. FK ra/vào: **3/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `invoice_id` | `uuid` | True | FK | `—` | Tham chiếu hóa đơn theo ticket |
| `line_no` | `integer` | True | — | `—` | Thứ tự dòng hóa đơn |
| `category_id` | `uuid` | True | FK | `—` | Tham chiếu phân loại chuẩn cho routing và báo cáo |
| `description` | `text` | True | — | `—` | Mô tả |
| `quantity` | `numeric(12,3)` | True | — | `—` | Số lượng |
| `unit_price` | `numeric(18,2)` | True | — | `—` | Đơn giá |
| `discount` | `numeric(18,2)` | True | — | `'0'::numeric` | Giảm giá dòng |
| `tax_rate` | `numeric(9,4)` | True | — | `'0'::numeric` | Thuế suất |
| `net_amount` | `numeric(18,2)` | True | — | `—` | Giá trị sau giảm giá, chưa thuế |
| `tax_amount` | `numeric(18,2)` | True | — | `—` | Tiền thuế |
| `total_amount` | `numeric(18,2)` | True | — | `—` | Giá trị dòng gồm thuế |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |

Ràng buộc:

- `invoice_lines_category_id_fk`: `FOREIGN KEY (tenant_id, category_id) REFERENCES service_categories(tenant_id, id) ON DELETE RESTRICT`.
- `invoice_lines_check_0`: `CHECK (quantity > 0::numeric AND unit_price >= 0::numeric)`.
- `invoice_lines_check_1`: `CHECK (tax_rate >= 0::numeric AND tax_rate <= 1::numeric)`.
- `invoice_lines_check_2`: `CHECK (discount >= 0::numeric)`.
- `invoice_lines_check_3`: `CHECK (total_amount = (net_amount + tax_amount))`.
- `invoice_lines_invoice_id_fk`: `FOREIGN KEY (tenant_id, invoice_id) REFERENCES invoices(tenant_id, id) ON DELETE RESTRICT`.
- `invoice_lines_pkey`: `PRIMARY KEY (id)`.
- `invoice_lines_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `invoice_lines_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `invoice_lines_unique_0`: `UNIQUE (invoice_id, line_no)`.

Chỉ mục:

- `CREATE UNIQUE INDEX invoice_lines_pkey ON public.invoice_lines USING btree (id)`.
- `CREATE UNIQUE INDEX invoice_lines_tenant_key_uq ON public.invoice_lines USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX invoice_lines_unique_0 ON public.invoice_lines USING btree (invoice_id, line_no)`.

### payment_intents

Yêu cầu thanh toán và QR

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **2/2**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `invoice_id` | `uuid` | True | FK | `—` | Tham chiếu hóa đơn theo ticket |
| `provider` | `text` | True | — | `—` | Nhà cung cấp dịch vụ |
| `merchant_account_ref` | `text` | True | — | `—` | Mã tài khoản nhận tiền đã cấu hình |
| `provider_intent_id` | `text` | False | — | `—` | ID yêu cầu thanh toán ở provider |
| `idempotency_key` | `text` | True | — | `—` | Khóa chống xử lý lặp |
| `amount` | `numeric(18,2)` | True | — | `—` | Số tiền |
| `currency` | `character(3)` | True | — | `—` | Mã tiền tệ ISO 4217 |
| `status` | `text` | True | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `qr_payload_ciphertext` | `text` | False | — | `—` | Payload QR đã mã hóa nếu có dữ liệu nhạy cảm |
| `expires_at` | `timestamp with time zone` | True | — | `—` | Thời điểm hết hạn |
| `paid_at` | `timestamp with time zone` | False | — | `—` | Thời điểm intent được xác nhận đã trả |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |

Ràng buộc:

- `payment_intents_check_0`: `CHECK (status = ANY (ARRAY['created'::text, 'pending'::text, 'succeeded'::text, 'expired'::text, 'cancelled'::text, 'failed'::text]))`.
- `payment_intents_invoice_id_fk`: `FOREIGN KEY (tenant_id, invoice_id) REFERENCES invoices(tenant_id, id) ON DELETE RESTRICT`.
- `payment_intents_pkey`: `PRIMARY KEY (id)`.
- `payment_intents_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `payment_intents_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `payment_intents_unique_0`: `UNIQUE (tenant_id, idempotency_key)`.
- `payment_intents_unique_1`: `UNIQUE (provider, merchant_account_ref, provider_intent_id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX payment_intents_pkey ON public.payment_intents USING btree (id)`.
- `CREATE UNIQUE INDEX payment_intents_tenant_key_uq ON public.payment_intents USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX payment_intents_unique_0 ON public.payment_intents USING btree (tenant_id, idempotency_key)`.
- `CREATE UNIQUE INDEX payment_intents_unique_1 ON public.payment_intents USING btree (provider, merchant_account_ref, provider_intent_id)`.

### payment_webhook_receipts

Bằng chứng callback nhà cung cấp

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **2/1**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `provider` | `text` | True | — | `—` | Nhà cung cấp dịch vụ |
| `merchant_account_ref` | `text` | True | — | `—` | Mã tài khoản nhận tiền đã cấu hình |
| `provider_event_id` | `text` | True | — | `—` | ID callback phía provider |
| `raw_body_hash` | `text` | True | — | `—` | Hash body callback gốc |
| `signature_valid` | `boolean` | True | — | `—` | Kết quả xác minh chữ ký callback |
| `received_at` | `timestamp with time zone` | True | — | `—` | Thời điểm tiếp nhận |
| `payload_redacted` | `jsonb` | True | — | `—` | Payload đã ẩn thông tin nhạy cảm |
| `intent_id` | `uuid` | False | FK | `—` | Tham chiếu yêu cầu thanh toán và qr |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |

Ràng buộc:

- `payment_webhook_receipts_intent_id_fk`: `FOREIGN KEY (tenant_id, intent_id) REFERENCES payment_intents(tenant_id, id) ON DELETE RESTRICT`.
- `payment_webhook_receipts_pkey`: `PRIMARY KEY (id)`.
- `payment_webhook_receipts_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `payment_webhook_receipts_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `payment_webhook_receipts_unique_0`: `UNIQUE (provider, merchant_account_ref, provider_event_id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX payment_webhook_receipts_pkey ON public.payment_webhook_receipts USING btree (id)`.
- `CREATE UNIQUE INDEX payment_webhook_receipts_tenant_key_uq ON public.payment_webhook_receipts USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX payment_webhook_receipts_unique_0 ON public.payment_webhook_receipts USING btree (provider, merchant_account_ref, provider_event_id)`.

### payments

Giao dịch tiền thực sự xác nhận

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **4/2**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `invoice_id` | `uuid` | True | FK | `—` | Tham chiếu hóa đơn theo ticket |
| `intent_id` | `uuid` | True | FK | `—` | Tham chiếu yêu cầu thanh toán và qr |
| `receipt_id` | `uuid` | False | FK | `—` | Tham chiếu bằng chứng callback nhà cung cấp |
| `provider` | `text` | True | — | `—` | Nhà cung cấp dịch vụ |
| `merchant_account_ref` | `text` | True | — | `—` | Mã tài khoản nhận tiền đã cấu hình |
| `provider_transaction_id` | `text` | True | — | `—` | Mã giao dịch ngân hàng/provider |
| `amount` | `numeric(18,2)` | True | — | `—` | Số tiền |
| `currency` | `character(3)` | True | — | `—` | Mã tiền tệ ISO 4217 |
| `settled_at` | `timestamp with time zone` | True | — | `—` | Thời điểm đối soát thành công |
| `reconciliation_status` | `text` | True | — | `—` | confirmed hoặc review_required |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |

Ràng buộc:

- `payments_check_0`: `CHECK (amount > 0::numeric)`.
- `payments_check_1`: `CHECK (reconciliation_status = ANY (ARRAY['confirmed'::text, 'review_required'::text]))`.
- `payments_intent_id_fk`: `FOREIGN KEY (tenant_id, intent_id) REFERENCES payment_intents(tenant_id, id) ON DELETE RESTRICT`.
- `payments_invoice_id_fk`: `FOREIGN KEY (tenant_id, invoice_id) REFERENCES invoices(tenant_id, id) ON DELETE RESTRICT`.
- `payments_pkey`: `PRIMARY KEY (id)`.
- `payments_receipt_id_fk`: `FOREIGN KEY (tenant_id, receipt_id) REFERENCES payment_webhook_receipts(tenant_id, id) ON DELETE RESTRICT`.
- `payments_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `payments_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `payments_unique_0`: `UNIQUE (provider, merchant_account_ref, provider_transaction_id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX payments_pkey ON public.payments USING btree (id)`.
- `CREATE UNIQUE INDEX payments_tenant_key_uq ON public.payments USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX payments_unique_0 ON public.payments USING btree (provider, merchant_account_ref, provider_transaction_id)`.

### payment_allocations

Phân bổ tiền đối soát vào hóa đơn

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **3/1**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `payment_id` | `uuid` | True | FK | `—` | Tham chiếu giao dịch tiền thực sự xác nhận |
| `invoice_id` | `uuid` | True | FK | `—` | Tham chiếu hóa đơn theo ticket |
| `amount` | `numeric(18,2)` | True | — | `—` | Số tiền |
| `allocated_at` | `timestamp with time zone` | True | — | `—` | Thời điểm allocated |
| `idempotency_key` | `text` | True | — | `—` | Khóa chống xử lý lặp |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |

Ràng buộc:

- `payment_allocations_check_0`: `CHECK (amount > 0::numeric)`.
- `payment_allocations_invoice_id_fk`: `FOREIGN KEY (tenant_id, invoice_id) REFERENCES invoices(tenant_id, id) ON DELETE RESTRICT`.
- `payment_allocations_payment_id_fk`: `FOREIGN KEY (tenant_id, payment_id) REFERENCES payments(tenant_id, id) ON DELETE RESTRICT`.
- `payment_allocations_pkey`: `PRIMARY KEY (id)`.
- `payment_allocations_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `payment_allocations_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `payment_allocations_unique_0`: `UNIQUE (tenant_id, idempotency_key)`.

Chỉ mục:

- `CREATE UNIQUE INDEX payment_allocations_pkey ON public.payment_allocations USING btree (id)`.
- `CREATE UNIQUE INDEX payment_allocations_tenant_key_uq ON public.payment_allocations USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX payment_allocations_unique_0 ON public.payment_allocations USING btree (tenant_id, idempotency_key)`.

### refunds

Hoàn tiền có lịch sử

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **4/1**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `payment_id` | `uuid` | True | FK | `—` | Tham chiếu giao dịch tiền thực sự xác nhận |
| `amount` | `numeric(18,2)` | True | — | `—` | Số tiền |
| `reason` | `text` | True | — | `—` | Lý do |
| `status` | `text` | True | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `provider_refund_id` | `text` | False | — | `—` | Mã hoàn tiền ở provider |
| `idempotency_key` | `text` | True | — | `—` | Khóa chống xử lý lặp |
| `requested_by` | `text` | True | FK | `—` | Tham chiếu tài khoản người dùng chung của platform |
| `approved_by` | `text` | False | FK | `—` | Tham chiếu tài khoản người dùng chung của platform |
| `settled_at` | `timestamp with time zone` | False | — | `—` | Thời điểm đối soát thành công |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |

Ràng buộc:

- `refunds_approved_by_fk`: `FOREIGN KEY (approved_by) REFERENCES users(id) ON DELETE RESTRICT`.
- `refunds_check_0`: `CHECK (amount > 0::numeric)`.
- `refunds_check_1`: `CHECK (status = ANY (ARRAY['requested'::text, 'approved'::text, 'pending'::text, 'succeeded'::text, 'failed'::text]))`.
- `refunds_payment_id_fk`: `FOREIGN KEY (tenant_id, payment_id) REFERENCES payments(tenant_id, id) ON DELETE RESTRICT`.
- `refunds_pkey`: `PRIMARY KEY (id)`.
- `refunds_requested_by_fk`: `FOREIGN KEY (requested_by) REFERENCES users(id) ON DELETE RESTRICT`.
- `refunds_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `refunds_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `refunds_unique_0`: `UNIQUE (tenant_id, idempotency_key)`.

Chỉ mục:

- `CREATE UNIQUE INDEX refunds_pkey ON public.refunds USING btree (id)`.
- `CREATE UNIQUE INDEX refunds_tenant_key_uq ON public.refunds USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX refunds_unique_0 ON public.refunds USING btree (tenant_id, idempotency_key)`.

### refund_allocations

Phần hoàn tiền làm giảm phân bổ hóa đơn

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **3/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `refund_id` | `uuid` | True | FK | `—` | Tham chiếu hoàn tiền có lịch sử |
| `payment_allocation_id` | `uuid` | True | FK | `—` | Tham chiếu payment_allocations |
| `amount` | `numeric(18,2)` | True | — | `—` | Số tiền |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |

Ràng buộc:

- `refund_allocations_check_0`: `CHECK (amount > 0::numeric)`.
- `refund_allocations_payment_allocation_id_fk`: `FOREIGN KEY (tenant_id, payment_allocation_id) REFERENCES payment_allocations(tenant_id, id) ON DELETE RESTRICT`.
- `refund_allocations_pkey`: `PRIMARY KEY (id)`.
- `refund_allocations_refund_id_fk`: `FOREIGN KEY (tenant_id, refund_id) REFERENCES refunds(tenant_id, id) ON DELETE RESTRICT`.
- `refund_allocations_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `refund_allocations_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `refund_allocations_unique_0`: `UNIQUE (refund_id, payment_allocation_id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX refund_allocations_pkey ON public.refund_allocations USING btree (id)`.
- `CREATE UNIQUE INDEX refund_allocations_tenant_key_uq ON public.refund_allocations USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX refund_allocations_unique_0 ON public.refund_allocations USING btree (refund_id, payment_allocation_id)`.

### vh_budget_approvals

Extension được tạo bằng migration SQL; xem định nghĩa cột và FK bên dưới.

Migration tạo: `0001_vinhomes_operations.sql`. Dòng hiện tại: **1**. RLS/FORCE: **True/True**. FK ra/vào: **4/0**. Có trong ORM registry: **False**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | — |
| `tenant_id` | `uuid` | True | FK | `—` | — |
| `work_order_id` | `uuid` | True | FK | `—` | — |
| `requested_by` | `text` | True | FK | `—` | — |
| `reviewer_user_id` | `text` | True | FK | `—` | — |
| `amount_vnd` | `numeric(18,2)` | True | — | `—` | — |
| `purpose` | `text` | True | — | `—` | — |
| `status` | `text` | True | — | `—` | — |
| `version` | `bigint` | True | — | `0` | — |
| `decided_by` | `text` | False | FK | `—` | — |
| `decided_at` | `timestamp with time zone` | False | — | `—` | — |
| `decision_note` | `text` | False | — | `—` | — |
| `created_at` | `timestamp with time zone` | True | — | `now()` | — |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | — |

Ràng buộc:

- `vh_budget_approvals_amount_vnd_check`: `CHECK (amount_vnd > 0::numeric)`.
- `vh_budget_approvals_decided_by_fkey`: `FOREIGN KEY (decided_by) REFERENCES users(id)`.
- `vh_budget_approvals_pkey`: `PRIMARY KEY (id)`.
- `vh_budget_approvals_requested_by_fkey`: `FOREIGN KEY (requested_by) REFERENCES users(id)`.
- `vh_budget_approvals_reviewer_user_id_fkey`: `FOREIGN KEY (reviewer_user_id) REFERENCES users(id)`.
- `vh_budget_approvals_status_check`: `CHECK (status = ANY (ARRAY['pending'::text, 'approved'::text, 'rejected'::text, 'cancelled'::text]))`.
- `vh_budget_approvals_tenant_id_id_key`: `UNIQUE (tenant_id, id)`.
- `vh_budget_approvals_tenant_id_work_order_id_fkey`: `FOREIGN KEY (tenant_id, work_order_id) REFERENCES work_orders(tenant_id, id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX vh_budget_approvals_pkey ON public.vh_budget_approvals USING btree (id)`.
- `CREATE UNIQUE INDEX vh_budget_approvals_tenant_id_id_key ON public.vh_budget_approvals USING btree (tenant_id, id)`.

## 11 Operations mở rộng

### vh_assets

Extension được tạo bằng migration SQL; xem định nghĩa cột và FK bên dưới.

Migration tạo: `0004_vinhomes_business_flows.sql`. Dòng hiện tại: **1**. RLS/FORCE: **True/True**. FK ra/vào: **2/2**. Có trong ORM registry: **False**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | — |
| `tenant_id` | `uuid` | True | FK | `—` | — |
| `building_id` | `uuid` | True | FK | `—` | — |
| `code` | `text` | True | — | `—` | — |
| `name` | `text` | True | — | `—` | — |
| `details` | `jsonb` | True | — | `'{}'::jsonb` | — |
| `status` | `text` | True | — | `—` | — |
| `created_at` | `timestamp with time zone` | True | — | `now()` | — |

Ràng buộc:

- `vh_assets_pkey`: `PRIMARY KEY (id)`.
- `vh_assets_status_check`: `CHECK (status = ANY (ARRAY['active'::text, 'inactive'::text]))`.
- `vh_assets_tenant_id_building_id_code_key`: `UNIQUE (tenant_id, building_id, code)`.
- `vh_assets_tenant_id_building_id_fkey`: `FOREIGN KEY (tenant_id, building_id) REFERENCES buildings(tenant_id, id)`.
- `vh_assets_tenant_id_fkey`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id)`.
- `vh_assets_tenant_id_id_key`: `UNIQUE (tenant_id, id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX vh_assets_pkey ON public.vh_assets USING btree (id)`.
- `CREATE UNIQUE INDEX vh_assets_tenant_id_building_id_code_key ON public.vh_assets USING btree (tenant_id, building_id, code)`.
- `CREATE UNIQUE INDEX vh_assets_tenant_id_id_key ON public.vh_assets USING btree (tenant_id, id)`.

### vh_maintenance_records

Extension được tạo bằng migration SQL; xem định nghĩa cột và FK bên dưới.

Migration tạo: `0004_vinhomes_business_flows.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **4/0**. Có trong ORM registry: **False**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | — |
| `tenant_id` | `uuid` | True | FK | `—` | — |
| `asset_id` | `uuid` | True | FK | `—` | — |
| `work_order_id` | `uuid` | True | FK | `—` | — |
| `note` | `text` | True | — | `—` | — |
| `confirmed_by` | `text` | True | FK | `—` | — |
| `created_at` | `timestamp with time zone` | True | — | `now()` | — |

Ràng buộc:

- `vh_maintenance_records_confirmed_by_fkey`: `FOREIGN KEY (confirmed_by) REFERENCES users(id)`.
- `vh_maintenance_records_pkey`: `PRIMARY KEY (id)`.
- `vh_maintenance_records_tenant_id_asset_id_fkey`: `FOREIGN KEY (tenant_id, asset_id) REFERENCES vh_assets(tenant_id, id)`.
- `vh_maintenance_records_tenant_id_asset_id_work_order_id_key`: `UNIQUE (tenant_id, asset_id, work_order_id)`.
- `vh_maintenance_records_tenant_id_fkey`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id)`.
- `vh_maintenance_records_tenant_id_id_key`: `UNIQUE (tenant_id, id)`.
- `vh_maintenance_records_tenant_id_work_order_id_fkey`: `FOREIGN KEY (tenant_id, work_order_id) REFERENCES work_orders(tenant_id, id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX vh_maintenance_records_pkey ON public.vh_maintenance_records USING btree (id)`.
- `CREATE UNIQUE INDEX vh_maintenance_records_tenant_id_asset_id_work_order_id_key ON public.vh_maintenance_records USING btree (tenant_id, asset_id, work_order_id)`.
- `CREATE UNIQUE INDEX vh_maintenance_records_tenant_id_id_key ON public.vh_maintenance_records USING btree (tenant_id, id)`.

### vh_sensor_readings

Extension được tạo bằng migration SQL; xem định nghĩa cột và FK bên dưới.

Migration tạo: `0004_vinhomes_business_flows.sql`. Dòng hiện tại: **1**. RLS/FORCE: **True/True**. FK ra/vào: **3/0**. Có trong ORM registry: **False**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | — |
| `tenant_id` | `uuid` | True | FK | `—` | — |
| `asset_id` | `uuid` | True | FK | `—` | — |
| `parameter` | `text` | True | — | `—` | — |
| `value` | `numeric` | True | — | `—` | — |
| `unit` | `text` | True | — | `—` | — |
| `measured_at` | `timestamp with time zone` | True | — | `—` | — |
| `source` | `text` | True | — | `—` | — |
| `recorded_by` | `text` | True | FK | `—` | — |
| `created_at` | `timestamp with time zone` | True | — | `now()` | — |

Ràng buộc:

- `vh_sensor_readings_pkey`: `PRIMARY KEY (id)`.
- `vh_sensor_readings_recorded_by_fkey`: `FOREIGN KEY (recorded_by) REFERENCES users(id)`.
- `vh_sensor_readings_tenant_id_asset_id_fkey`: `FOREIGN KEY (tenant_id, asset_id) REFERENCES vh_assets(tenant_id, id)`.
- `vh_sensor_readings_tenant_id_fkey`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id)`.
- `vh_sensor_readings_tenant_id_id_key`: `UNIQUE (tenant_id, id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX vh_sensor_readings_pkey ON public.vh_sensor_readings USING btree (id)`.
- `CREATE UNIQUE INDEX vh_sensor_readings_tenant_id_id_key ON public.vh_sensor_readings USING btree (tenant_id, id)`.

### vh_agent_reviews

Extension được tạo bằng migration SQL; xem định nghĩa cột và FK bên dưới.

Migration tạo: `0004_vinhomes_business_flows.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **4/0**. Có trong ORM registry: **False**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | — |
| `tenant_id` | `uuid` | True | FK | `—` | — |
| `agent_id` | `text` | True | FK | `—` | — |
| `submitted_by` | `text` | True | FK | `—` | — |
| `config_hash` | `text` | True | — | `—` | — |
| `evaluation` | `jsonb` | True | — | `—` | — |
| `status` | `text` | True | — | `—` | — |
| `version` | `bigint` | True | — | `0` | — |
| `decided_by` | `text` | False | FK | `—` | — |
| `decision_note` | `text` | False | — | `—` | — |
| `decided_at` | `timestamp with time zone` | False | — | `—` | — |
| `created_at` | `timestamp with time zone` | True | — | `now()` | — |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | — |

Ràng buộc:

- `vh_agent_reviews_decided_by_fkey`: `FOREIGN KEY (decided_by) REFERENCES users(id)`.
- `vh_agent_reviews_pkey`: `PRIMARY KEY (id)`.
- `vh_agent_reviews_status_check`: `CHECK (status = ANY (ARRAY['pending'::text, 'approved'::text, 'rejected'::text]))`.
- `vh_agent_reviews_submitted_by_fkey`: `FOREIGN KEY (submitted_by) REFERENCES users(id)`.
- `vh_agent_reviews_tenant_id_agent_id_fkey`: `FOREIGN KEY (tenant_id, agent_id) REFERENCES agents(tenant_id, id)`.
- `vh_agent_reviews_tenant_id_fkey`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id)`.
- `vh_agent_reviews_tenant_id_id_key`: `UNIQUE (tenant_id, id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX vh_agent_pending_review ON public.vh_agent_reviews USING btree (tenant_id, agent_id) WHERE (status = 'pending'::text)`.
- `CREATE UNIQUE INDEX vh_agent_reviews_pkey ON public.vh_agent_reviews USING btree (id)`.
- `CREATE UNIQUE INDEX vh_agent_reviews_tenant_id_id_key ON public.vh_agent_reviews USING btree (tenant_id, id)`.

### vh_cleaning_plans

Extension được tạo bằng migration SQL; xem định nghĩa cột và FK bên dưới.

Migration tạo: `0001_vinhomes_operations.sql`. Dòng hiện tại: **1**. RLS/FORCE: **True/True**. FK ra/vào: **2/0**. Có trong ORM registry: **False**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | — |
| `tenant_id` | `uuid` | True | FK | `—` | — |
| `work_order_id` | `uuid` | True | FK | `—` | — |
| `plan` | `jsonb` | True | — | `—` | — |
| `status` | `text` | True | — | `—` | — |
| `version` | `bigint` | True | — | `0` | — |
| `updated_by` | `text` | True | FK | `—` | — |
| `created_at` | `timestamp with time zone` | True | — | `now()` | — |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | — |

Ràng buộc:

- `vh_cleaning_plans_pkey`: `PRIMARY KEY (id)`.
- `vh_cleaning_plans_status_check`: `CHECK (status = ANY (ARRAY['draft'::text, 'in_progress'::text, 'completed'::text, 'cancelled'::text]))`.
- `vh_cleaning_plans_tenant_id_id_key`: `UNIQUE (tenant_id, id)`.
- `vh_cleaning_plans_tenant_id_work_order_id_fkey`: `FOREIGN KEY (tenant_id, work_order_id) REFERENCES work_orders(tenant_id, id)`.
- `vh_cleaning_plans_tenant_id_work_order_id_key`: `UNIQUE (tenant_id, work_order_id)`.
- `vh_cleaning_plans_updated_by_fkey`: `FOREIGN KEY (updated_by) REFERENCES users(id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX vh_cleaning_plans_pkey ON public.vh_cleaning_plans USING btree (id)`.
- `CREATE UNIQUE INDEX vh_cleaning_plans_tenant_id_id_key ON public.vh_cleaning_plans USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX vh_cleaning_plans_tenant_id_work_order_id_key ON public.vh_cleaning_plans USING btree (tenant_id, work_order_id)`.

### vh_contractor_updates

Extension được tạo bằng migration SQL; xem định nghĩa cột và FK bên dưới.

Migration tạo: `0001_vinhomes_operations.sql`. Dòng hiện tại: **1**. RLS/FORCE: **True/True**. FK ra/vào: **2/0**. Có trong ORM registry: **False**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | — |
| `tenant_id` | `uuid` | True | FK | `—` | — |
| `work_order_id` | `uuid` | True | FK | `—` | — |
| `status` | `text` | True | — | `—` | — |
| `worker_name` | `text` | False | — | `—` | — |
| `materials` | `jsonb` | True | — | `'[]'::jsonb` | — |
| `note` | `text` | False | — | `—` | — |
| `version` | `bigint` | True | — | `0` | — |
| `updated_by` | `text` | True | FK | `—` | — |
| `created_at` | `timestamp with time zone` | True | — | `now()` | — |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | — |

Ràng buộc:

- `vh_contractor_updates_pkey`: `PRIMARY KEY (id)`.
- `vh_contractor_updates_status_check`: `CHECK (status = ANY (ARRAY['pending'::text, 'accepted'::text, 'rejected'::text, 'in_progress'::text, 'completed'::text]))`.
- `vh_contractor_updates_tenant_id_id_key`: `UNIQUE (tenant_id, id)`.
- `vh_contractor_updates_tenant_id_work_order_id_fkey`: `FOREIGN KEY (tenant_id, work_order_id) REFERENCES work_orders(tenant_id, id)`.
- `vh_contractor_updates_tenant_id_work_order_id_key`: `UNIQUE (tenant_id, work_order_id)`.
- `vh_contractor_updates_updated_by_fkey`: `FOREIGN KEY (updated_by) REFERENCES users(id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX vh_contractor_updates_pkey ON public.vh_contractor_updates USING btree (id)`.
- `CREATE UNIQUE INDEX vh_contractor_updates_tenant_id_id_key ON public.vh_contractor_updates USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX vh_contractor_updates_tenant_id_work_order_id_key ON public.vh_contractor_updates USING btree (tenant_id, work_order_id)`.

### vh_operational_requests

Extension được tạo bằng migration SQL; xem định nghĩa cột và FK bên dưới.

Migration tạo: `0004_vinhomes_business_flows.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **4/0**. Có trong ORM registry: **False**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | — |
| `tenant_id` | `uuid` | True | FK | `—` | — |
| `work_order_id` | `uuid` | True | FK | `—` | — |
| `kind` | `text` | True | — | `—` | — |
| `details` | `jsonb` | True | — | `—` | — |
| `reason` | `text` | True | — | `—` | — |
| `requested_by` | `text` | True | FK | `—` | — |
| `status` | `text` | True | — | `—` | — |
| `version` | `bigint` | True | — | `0` | — |
| `idempotency_key` | `text` | True | — | `—` | — |
| `request_hash` | `text` | True | — | `—` | — |
| `decided_by` | `text` | False | FK | `—` | — |
| `decision_note` | `text` | False | — | `—` | — |
| `decided_at` | `timestamp with time zone` | False | — | `—` | — |
| `created_at` | `timestamp with time zone` | True | — | `now()` | — |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | — |

Ràng buộc:

- `vh_operational_requests_decided_by_fkey`: `FOREIGN KEY (decided_by) REFERENCES users(id)`.
- `vh_operational_requests_kind_check`: `CHECK (kind = ANY (ARRAY['utility_isolation'::text, 'area_restriction'::text, 'apartment_entry'::text, 'vendor_dispatch'::text]))`.
- `vh_operational_requests_pkey`: `PRIMARY KEY (id)`.
- `vh_operational_requests_requested_by_fkey`: `FOREIGN KEY (requested_by) REFERENCES users(id)`.
- `vh_operational_requests_status_check`: `CHECK (status = ANY (ARRAY['pending'::text, 'approved'::text, 'rejected'::text, 'completed'::text, 'cancelled'::text]))`.
- `vh_operational_requests_tenant_id_fkey`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id)`.
- `vh_operational_requests_tenant_id_id_key`: `UNIQUE (tenant_id, id)`.
- `vh_operational_requests_tenant_id_work_order_id_fkey`: `FOREIGN KEY (tenant_id, work_order_id) REFERENCES work_orders(tenant_id, id)`.
- `vh_operational_requests_tenant_id_work_order_id_idempotency_key`: `UNIQUE (tenant_id, work_order_id, idempotency_key)`.

Chỉ mục:

- `CREATE UNIQUE INDEX vh_operational_requests_pkey ON public.vh_operational_requests USING btree (id)`.
- `CREATE UNIQUE INDEX vh_operational_requests_tenant_id_id_key ON public.vh_operational_requests USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX vh_operational_requests_tenant_id_work_order_id_idempotency_key ON public.vh_operational_requests USING btree (tenant_id, work_order_id, idempotency_key)`.

### vh_qc_results

Extension được tạo bằng migration SQL; xem định nghĩa cột và FK bên dưới.

Migration tạo: `0001_vinhomes_operations.sql`. Dòng hiện tại: **1**. RLS/FORCE: **True/True**. FK ra/vào: **2/1**. Có trong ORM registry: **False**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | — |
| `tenant_id` | `uuid` | True | FK | `—` | — |
| `work_order_id` | `uuid` | True | FK | `—` | — |
| `outcome` | `text` | True | — | `—` | — |
| `criteria` | `jsonb` | True | — | `—` | — |
| `redo_required` | `boolean` | True | — | `false` | — |
| `note` | `text` | False | — | `—` | — |
| `checked_by` | `text` | True | FK | `—` | — |
| `checked_at` | `timestamp with time zone` | True | — | `now()` | — |
| `created_at` | `timestamp with time zone` | True | — | `now()` | — |

Ràng buộc:

- `vh_qc_results_check`: `CHECK (NOT redo_required OR outcome = 'fail'::text)`.
- `vh_qc_results_checked_by_fkey`: `FOREIGN KEY (checked_by) REFERENCES users(id)`.
- `vh_qc_results_outcome_check`: `CHECK (outcome = ANY (ARRAY['pass'::text, 'fail'::text, 'inconclusive'::text]))`.
- `vh_qc_results_pkey`: `PRIMARY KEY (id)`.
- `vh_qc_results_tenant_id_id_key`: `UNIQUE (tenant_id, id)`.
- `vh_qc_results_tenant_id_work_order_id_fkey`: `FOREIGN KEY (tenant_id, work_order_id) REFERENCES work_orders(tenant_id, id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX vh_qc_results_pkey ON public.vh_qc_results USING btree (id)`.
- `CREATE UNIQUE INDEX vh_qc_results_tenant_id_id_key ON public.vh_qc_results USING btree (tenant_id, id)`.

### vh_qc_redo_orders

Extension được tạo bằng migration SQL; xem định nghĩa cột và FK bên dưới.

Migration tạo: `0002_vinhomes_qc_redo.sql`. Dòng hiện tại: **1**. RLS/FORCE: **True/True**. FK ra/vào: **4/0**. Có trong ORM registry: **False**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | — |
| `tenant_id` | `uuid` | True | FK | `—` | — |
| `qc_result_id` | `uuid` | True | FK | `—` | — |
| `source_work_order_id` | `uuid` | True | FK | `—` | — |
| `redo_work_order_id` | `uuid` | True | FK | `—` | — |
| `created_by` | `text` | True | FK | `—` | — |
| `created_at` | `timestamp with time zone` | True | — | `now()` | — |

Ràng buộc:

- `vh_qc_redo_orders_created_by_fkey`: `FOREIGN KEY (created_by) REFERENCES users(id)`.
- `vh_qc_redo_orders_pkey`: `PRIMARY KEY (id)`.
- `vh_qc_redo_orders_tenant_id_id_key`: `UNIQUE (tenant_id, id)`.
- `vh_qc_redo_orders_tenant_id_qc_result_id_fkey`: `FOREIGN KEY (tenant_id, qc_result_id) REFERENCES vh_qc_results(tenant_id, id)`.
- `vh_qc_redo_orders_tenant_id_qc_result_id_key`: `UNIQUE (tenant_id, qc_result_id)`.
- `vh_qc_redo_orders_tenant_id_redo_work_order_id_fkey`: `FOREIGN KEY (tenant_id, redo_work_order_id) REFERENCES work_orders(tenant_id, id)`.
- `vh_qc_redo_orders_tenant_id_redo_work_order_id_key`: `UNIQUE (tenant_id, redo_work_order_id)`.
- `vh_qc_redo_orders_tenant_id_source_work_order_id_fkey`: `FOREIGN KEY (tenant_id, source_work_order_id) REFERENCES work_orders(tenant_id, id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX vh_qc_redo_orders_pkey ON public.vh_qc_redo_orders USING btree (id)`.
- `CREATE UNIQUE INDEX vh_qc_redo_orders_tenant_id_id_key ON public.vh_qc_redo_orders USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX vh_qc_redo_orders_tenant_id_qc_result_id_key ON public.vh_qc_redo_orders USING btree (tenant_id, qc_result_id)`.
- `CREATE UNIQUE INDEX vh_qc_redo_orders_tenant_id_redo_work_order_id_key ON public.vh_qc_redo_orders USING btree (tenant_id, redo_work_order_id)`.

### vh_command_receipt

Extension được tạo bằng migration SQL; xem định nghĩa cột và FK bên dưới.

Migration tạo: `0008_reception_command_receipt.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **1/0**. Có trong ORM registry: **False**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | — |
| `tenant_id` | `uuid` | True | FK | `—` | — |
| `actor_type` | `character varying(16)` | True | — | `—` | — |
| `actor_id` | `character varying(128)` | True | — | `—` | — |
| `command_type` | `character varying(128)` | True | — | `—` | — |
| `idempotency_key` | `character varying(128)` | True | — | `—` | — |
| `payload_hash` | `character varying(72)` | True | — | `—` | — |
| `subject_type` | `character varying(128)` | True | — | `—` | — |
| `subject_id` | `character varying(128)` | False | — | `—` | — |
| `response_json` | `jsonb` | False | — | `—` | — |
| `status` | `character varying(16)` | True | — | `—` | — |
| `created_at` | `timestamp with time zone` | True | — | `now()` | — |
| `completed_at` | `timestamp with time zone` | False | — | `—` | — |

Ràng buộc:

- `uq_vh_command_receipt_tenant_actor_command_key`: `UNIQUE (tenant_id, actor_type, actor_id, command_type, idempotency_key)`.
- `vh_command_receipt_pkey`: `PRIMARY KEY (id)`.
- `vh_command_receipt_status_check`: `CHECK (status::text = ANY (ARRAY['IN_PROGRESS'::character varying::text, 'COMPLETED'::character varying::text]))`.
- `vh_command_receipt_tenant_id_fkey`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id)`.

Chỉ mục:

- `CREATE INDEX ix_vh_command_receipt_tenant_created ON public.vh_command_receipt USING btree (tenant_id, created_at)`.
- `CREATE UNIQUE INDEX uq_vh_command_receipt_tenant_actor_command_key ON public.vh_command_receipt USING btree (tenant_id, actor_type, actor_id, command_type, idempotency_key)`.
- `CREATE UNIQUE INDEX vh_command_receipt_pkey ON public.vh_command_receipt USING btree (id)`.

### vh_ticket_plans

Extension được tạo bằng migration SQL; xem định nghĩa cột và FK bên dưới.

Migration tạo: `0004_vinhomes_business_flows.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **5/1**. Có trong ORM registry: **False**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | — |
| `tenant_id` | `uuid` | True | FK | `—` | — |
| `ticket_id` | `uuid` | True | FK | `—` | — |
| `proposed_by` | `text` | True | FK | `—` | — |
| `title` | `text` | True | — | `—` | — |
| `steps` | `jsonb` | True | — | `—` | — |
| `estimated_amount` | `numeric(18,2)` | True | — | `—` | — |
| `status` | `text` | True | — | `—` | — |
| `version` | `bigint` | True | — | `0` | — |
| `idempotency_key` | `text` | True | — | `—` | — |
| `request_hash` | `text` | True | — | `—` | — |
| `management_by` | `text` | False | FK | `—` | — |
| `management_note` | `text` | False | — | `—` | — |
| `management_at` | `timestamp with time zone` | False | — | `—` | — |
| `resident_by` | `text` | False | FK | `—` | — |
| `resident_note` | `text` | False | — | `—` | — |
| `resident_at` | `timestamp with time zone` | False | — | `—` | — |
| `created_at` | `timestamp with time zone` | True | — | `now()` | — |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | — |

Ràng buộc:

- `vh_ticket_plans_estimated_amount_check`: `CHECK (estimated_amount >= 0::numeric)`.
- `vh_ticket_plans_management_by_fkey`: `FOREIGN KEY (management_by) REFERENCES users(id)`.
- `vh_ticket_plans_pkey`: `PRIMARY KEY (id)`.
- `vh_ticket_plans_proposed_by_fkey`: `FOREIGN KEY (proposed_by) REFERENCES users(id)`.
- `vh_ticket_plans_resident_by_fkey`: `FOREIGN KEY (resident_by) REFERENCES users(id)`.
- `vh_ticket_plans_status_check`: `CHECK (status = ANY (ARRAY['management_pending'::text, 'resident_pending'::text, 'approved'::text, 'rejected'::text, 'revision_requested'::text]))`.
- `vh_ticket_plans_tenant_id_fkey`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id)`.
- `vh_ticket_plans_tenant_id_id_key`: `UNIQUE (tenant_id, id)`.
- `vh_ticket_plans_tenant_id_ticket_id_fkey`: `FOREIGN KEY (tenant_id, ticket_id) REFERENCES tickets(tenant_id, id)`.
- `vh_ticket_plans_tenant_id_ticket_id_idempotency_key_key`: `UNIQUE (tenant_id, ticket_id, idempotency_key)`.

Chỉ mục:

- `CREATE UNIQUE INDEX vh_one_pending_plan ON public.vh_ticket_plans USING btree (tenant_id, ticket_id) WHERE (status = ANY (ARRAY['management_pending'::text, 'resident_pending'::text]))`.
- `CREATE UNIQUE INDEX vh_ticket_plans_pkey ON public.vh_ticket_plans USING btree (id)`.
- `CREATE UNIQUE INDEX vh_ticket_plans_tenant_id_id_key ON public.vh_ticket_plans USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX vh_ticket_plans_tenant_id_ticket_id_idempotency_key_key ON public.vh_ticket_plans USING btree (tenant_id, ticket_id, idempotency_key)`.

## 12 Resident UI, intake và kết quả

### vh_resident_cases

Extension được tạo bằng migration SQL; xem định nghĩa cột và FK bên dưới.

Migration tạo: `0006_resident_contract.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **8/6**. Có trong ORM registry: **False**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK/FK | `gen_random_uuid()` | — |
| `tenant_id` | `uuid` | True | FK | `—` | — |
| `requester_user_id` | `text` | True | FK | `—` | — |
| `unit_id` | `uuid` | True | FK | `—` | — |
| `building_id` | `uuid` | True | FK | `—` | — |
| `site_id` | `uuid` | True | FK | `—` | — |
| `domain_id` | `uuid` | True | FK | `—` | — |
| `channel_id` | `text` | True | FK | `—` | — |
| `code` | `text` | True | — | `—` | — |
| `title` | `text` | True | — | `—` | — |
| `description` | `text` | True | — | `—` | — |
| `location_description` | `text` | True | — | `—` | — |
| `location_label` | `text` | True | — | `—` | — |
| `status` | `text` | True | — | `'received'::text` | — |
| `version` | `bigint` | True | — | `1` | — |
| `current_resolution_id` | `uuid` | False | FK | `—` | — |
| `created_at` | `timestamp with time zone` | True | — | `now()` | — |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | — |

Ràng buộc:

- `vh_resident_cases_check`: `CHECK ((status <> ALL (ARRAY['confirmation'::text, 'completed'::text])) OR current_resolution_id IS NOT NULL)`.
- `vh_resident_cases_description_check`: `CHECK (length(description) >= 8 AND length(description) <= 5000)`.
- `vh_resident_cases_location_description_check`: `CHECK (length(location_description) >= 3 AND length(location_description) <= 500)`.
- `vh_resident_cases_pkey`: `PRIMARY KEY (id)`.
- `vh_resident_cases_requester_user_id_fkey`: `FOREIGN KEY (requester_user_id) REFERENCES users(id)`.
- `vh_resident_cases_resolution_fk`: `FOREIGN KEY (tenant_id, id, current_resolution_id) REFERENCES vh_resident_resolutions(tenant_id, case_id, id)`.
- `vh_resident_cases_status_check`: `CHECK (status = ANY (ARRAY['received'::text, 'processing'::text, 'confirmation'::text, 'completed'::text]))`.
- `vh_resident_cases_tenant_id_building_id_fkey`: `FOREIGN KEY (tenant_id, building_id) REFERENCES buildings(tenant_id, id)`.
- `vh_resident_cases_tenant_id_channel_id_fkey`: `FOREIGN KEY (tenant_id, channel_id) REFERENCES channels(tenant_id, id)`.
- `vh_resident_cases_tenant_id_channel_id_key`: `UNIQUE (tenant_id, channel_id)`.
- `vh_resident_cases_tenant_id_code_key`: `UNIQUE (tenant_id, code)`.
- `vh_resident_cases_tenant_id_domain_id_fkey`: `FOREIGN KEY (tenant_id, domain_id) REFERENCES domains(tenant_id, id)`.
- `vh_resident_cases_tenant_id_fkey`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id)`.
- `vh_resident_cases_tenant_id_id_key`: `UNIQUE (tenant_id, id)`.
- `vh_resident_cases_tenant_id_site_id_fkey`: `FOREIGN KEY (tenant_id, site_id) REFERENCES sites(tenant_id, id)`.
- `vh_resident_cases_tenant_id_unit_id_fkey`: `FOREIGN KEY (tenant_id, unit_id) REFERENCES units(tenant_id, id)`.
- `vh_resident_cases_title_check`: `CHECK (length(title) >= 1 AND length(title) <= 90)`.
- `vh_resident_cases_version_check`: `CHECK (version >= 1)`.

Chỉ mục:

- `CREATE INDEX vh_resident_cases_owner_page ON public.vh_resident_cases USING btree (tenant_id, requester_user_id, created_at DESC, id DESC)`.
- `CREATE UNIQUE INDEX vh_resident_cases_pkey ON public.vh_resident_cases USING btree (id)`.
- `CREATE UNIQUE INDEX vh_resident_cases_tenant_id_channel_id_key ON public.vh_resident_cases USING btree (tenant_id, channel_id)`.
- `CREATE UNIQUE INDEX vh_resident_cases_tenant_id_code_key ON public.vh_resident_cases USING btree (tenant_id, code)`.
- `CREATE UNIQUE INDEX vh_resident_cases_tenant_id_id_key ON public.vh_resident_cases USING btree (tenant_id, id)`.

### vh_resident_case_tickets

Extension được tạo bằng migration SQL; xem định nghĩa cột và FK bên dưới.

Migration tạo: `0006_resident_contract.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **4/0**. Có trong ORM registry: **False**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `tenant_id` | `uuid` | True | PK/FK | `—` | — |
| `case_id` | `uuid` | True | PK/FK | `—` | — |
| `ticket_id` | `uuid` | True | PK/FK | `—` | — |
| `linked_by` | `text` | True | FK | `—` | — |
| `created_at` | `timestamp with time zone` | True | — | `now()` | — |

Ràng buộc:

- `vh_resident_case_tickets_linked_by_fkey`: `FOREIGN KEY (linked_by) REFERENCES users(id)`.
- `vh_resident_case_tickets_pkey`: `PRIMARY KEY (tenant_id, case_id, ticket_id)`.
- `vh_resident_case_tickets_tenant_id_case_id_fkey`: `FOREIGN KEY (tenant_id, case_id) REFERENCES vh_resident_cases(tenant_id, id)`.
- `vh_resident_case_tickets_tenant_id_fkey`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id)`.
- `vh_resident_case_tickets_tenant_id_ticket_id_fkey`: `FOREIGN KEY (tenant_id, ticket_id) REFERENCES tickets(tenant_id, id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX vh_resident_case_tickets_pkey ON public.vh_resident_case_tickets USING btree (tenant_id, case_id, ticket_id)`.
- `CREATE INDEX vh_resident_case_tickets_source ON public.vh_resident_case_tickets USING btree (tenant_id, ticket_id)`.

### vh_resident_submissions

Extension được tạo bằng migration SQL; xem định nghĩa cột và FK bên dưới.

Migration tạo: `0006_resident_contract.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **3/0**. Có trong ORM registry: **False**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | — |
| `tenant_id` | `uuid` | True | FK | `—` | — |
| `case_id` | `uuid` | True | FK | `—` | — |
| `submitted_by` | `text` | True | FK | `—` | — |
| `description` | `text` | True | — | `—` | — |
| `location_description` | `text` | True | — | `—` | — |
| `created_at` | `timestamp with time zone` | True | — | `now()` | — |

Ràng buộc:

- `vh_resident_submissions_pkey`: `PRIMARY KEY (id)`.
- `vh_resident_submissions_submitted_by_fkey`: `FOREIGN KEY (submitted_by) REFERENCES users(id)`.
- `vh_resident_submissions_tenant_id_case_id_fkey`: `FOREIGN KEY (tenant_id, case_id) REFERENCES vh_resident_cases(tenant_id, id)`.
- `vh_resident_submissions_tenant_id_fkey`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id)`.
- `vh_resident_submissions_tenant_id_id_key`: `UNIQUE (tenant_id, id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX vh_resident_submissions_pkey ON public.vh_resident_submissions USING btree (id)`.
- `CREATE UNIQUE INDEX vh_resident_submissions_tenant_id_id_key ON public.vh_resident_submissions USING btree (tenant_id, id)`.

### vh_resident_photos

Extension được tạo bằng migration SQL; xem định nghĩa cột và FK bên dưới.

Migration tạo: `0006_resident_contract.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **5/0**. Có trong ORM registry: **False**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `tenant_id` | `uuid` | True | PK/FK | `—` | — |
| `file_id` | `uuid` | True | PK/FK | `—` | — |
| `unit_id` | `uuid` | True | FK | `—` | — |
| `uploaded_by` | `text` | True | FK | `—` | — |
| `case_id` | `uuid` | False | FK | `—` | — |
| `expires_at` | `timestamp with time zone` | True | — | `(now() + '24:00:00'::interval)` | — |
| `created_at` | `timestamp with time zone` | True | — | `now()` | — |

Ràng buộc:

- `vh_resident_photos_pkey`: `PRIMARY KEY (tenant_id, file_id)`.
- `vh_resident_photos_tenant_id_case_id_fkey`: `FOREIGN KEY (tenant_id, case_id) REFERENCES vh_resident_cases(tenant_id, id)`.
- `vh_resident_photos_tenant_id_file_id_fkey`: `FOREIGN KEY (tenant_id, file_id) REFERENCES files(tenant_id, id)`.
- `vh_resident_photos_tenant_id_fkey`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id)`.
- `vh_resident_photos_tenant_id_unit_id_fkey`: `FOREIGN KEY (tenant_id, unit_id) REFERENCES units(tenant_id, id)`.
- `vh_resident_photos_uploaded_by_fkey`: `FOREIGN KEY (uploaded_by) REFERENCES users(id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX vh_resident_photos_pkey ON public.vh_resident_photos USING btree (tenant_id, file_id)`.

### vh_resident_command_receipts

Extension được tạo bằng migration SQL; xem định nghĩa cột và FK bên dưới.

Migration tạo: `0006_resident_contract.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **2/0**. Có trong ORM registry: **False**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `tenant_id` | `uuid` | True | PK/FK | `—` | — |
| `actor_id` | `text` | True | PK/FK | `—` | — |
| `operation` | `text` | True | PK | `—` | — |
| `resource` | `text` | True | PK | `—` | — |
| `key` | `text` | True | PK | `—` | — |
| `request_hash` | `text` | True | — | `—` | — |
| `response_status` | `integer` | True | — | `—` | — |
| `response_body` | `jsonb` | True | — | `—` | — |
| `result_id` | `uuid` | True | — | `—` | — |
| `created_at` | `timestamp with time zone` | True | — | `now()` | — |

Ràng buộc:

- `vh_resident_command_receipts_actor_id_fkey`: `FOREIGN KEY (actor_id) REFERENCES users(id)`.
- `vh_resident_command_receipts_key_check`: `CHECK (length(key) >= 8 AND length(key) <= 128)`.
- `vh_resident_command_receipts_pkey`: `PRIMARY KEY (tenant_id, actor_id, operation, resource, key)`.
- `vh_resident_command_receipts_tenant_id_fkey`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX vh_resident_command_receipts_pkey ON public.vh_resident_command_receipts USING btree (tenant_id, actor_id, operation, resource, key)`.

### vh_resident_outbox

Extension được tạo bằng migration SQL; xem định nghĩa cột và FK bên dưới.

Migration tạo: `0006_resident_contract.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **3/0**. Có trong ORM registry: **False**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | — |
| `tenant_id` | `uuid` | True | FK | `—` | — |
| `case_id` | `uuid` | True | FK | `—` | — |
| `event_id` | `uuid` | True | FK | `—` | — |
| `event_type` | `text` | True | — | `—` | — |
| `payload` | `jsonb` | True | — | `—` | — |
| `created_at` | `timestamp with time zone` | True | — | `now()` | — |
| `delivered_at` | `timestamp with time zone` | False | — | `—` | — |

Ràng buộc:

- `vh_resident_outbox_pkey`: `PRIMARY KEY (id)`.
- `vh_resident_outbox_tenant_id_case_id_fkey`: `FOREIGN KEY (tenant_id, case_id) REFERENCES vh_resident_cases(tenant_id, id)`.
- `vh_resident_outbox_tenant_id_event_id_fkey`: `FOREIGN KEY (tenant_id, event_id) REFERENCES vh_resident_public_events(tenant_id, id)`.
- `vh_resident_outbox_tenant_id_event_id_key`: `UNIQUE (tenant_id, event_id)`.
- `vh_resident_outbox_tenant_id_fkey`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id)`.
- `vh_resident_outbox_tenant_id_id_key`: `UNIQUE (tenant_id, id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX vh_resident_outbox_pkey ON public.vh_resident_outbox USING btree (id)`.
- `CREATE UNIQUE INDEX vh_resident_outbox_tenant_id_event_id_key ON public.vh_resident_outbox USING btree (tenant_id, event_id)`.
- `CREATE UNIQUE INDEX vh_resident_outbox_tenant_id_id_key ON public.vh_resident_outbox USING btree (tenant_id, id)`.

### vh_resident_public_events

Extension được tạo bằng migration SQL; xem định nghĩa cột và FK bên dưới.

Migration tạo: `0006_resident_contract.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **2/1**. Có trong ORM registry: **False**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | — |
| `tenant_id` | `uuid` | True | FK | `—` | — |
| `case_id` | `uuid` | True | FK | `—` | — |
| `label` | `text` | True | — | `—` | — |
| `note` | `text` | False | — | `—` | — |
| `occurred_at` | `timestamp with time zone` | True | — | `clock_timestamp()` | — |

Ràng buộc:

- `vh_resident_public_events_pkey`: `PRIMARY KEY (id)`.
- `vh_resident_public_events_tenant_id_case_id_fkey`: `FOREIGN KEY (tenant_id, case_id) REFERENCES vh_resident_cases(tenant_id, id)`.
- `vh_resident_public_events_tenant_id_fkey`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id)`.
- `vh_resident_public_events_tenant_id_id_key`: `UNIQUE (tenant_id, id)`.

Chỉ mục:

- `CREATE INDEX vh_resident_events_page ON public.vh_resident_public_events USING btree (tenant_id, case_id, occurred_at, id)`.
- `CREATE UNIQUE INDEX vh_resident_public_events_pkey ON public.vh_resident_public_events USING btree (id)`.
- `CREATE UNIQUE INDEX vh_resident_public_events_tenant_id_id_key ON public.vh_resident_public_events USING btree (tenant_id, id)`.

### vh_resident_resolutions

Extension được tạo bằng migration SQL; xem định nghĩa cột và FK bên dưới.

Migration tạo: `0006_resident_contract.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **3/3**. Có trong ORM registry: **False**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | — |
| `tenant_id` | `uuid` | True | FK | `—` | — |
| `case_id` | `uuid` | True | FK | `—` | — |
| `summary` | `text` | True | — | `—` | — |
| `published_by` | `text` | True | FK | `—` | — |
| `basis_versions` | `jsonb` | True | — | `—` | — |
| `published_at` | `timestamp with time zone` | True | — | `now()` | — |

Ràng buộc:

- `vh_resident_resolutions_basis_versions_check`: `CHECK (jsonb_typeof(basis_versions) = 'object'::text)`.
- `vh_resident_resolutions_pkey`: `PRIMARY KEY (id)`.
- `vh_resident_resolutions_published_by_fkey`: `FOREIGN KEY (published_by) REFERENCES users(id)`.
- `vh_resident_resolutions_summary_check`: `CHECK (length(summary) >= 8 AND length(summary) <= 5000)`.
- `vh_resident_resolutions_tenant_id_case_id_fkey`: `FOREIGN KEY (tenant_id, case_id) REFERENCES vh_resident_cases(tenant_id, id)`.
- `vh_resident_resolutions_tenant_id_case_id_id_key`: `UNIQUE (tenant_id, case_id, id)`.
- `vh_resident_resolutions_tenant_id_fkey`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id)`.
- `vh_resident_resolutions_tenant_id_id_key`: `UNIQUE (tenant_id, id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX vh_resident_resolutions_pkey ON public.vh_resident_resolutions USING btree (id)`.
- `CREATE UNIQUE INDEX vh_resident_resolutions_tenant_id_case_id_id_key ON public.vh_resident_resolutions USING btree (tenant_id, case_id, id)`.
- `CREATE UNIQUE INDEX vh_resident_resolutions_tenant_id_id_key ON public.vh_resident_resolutions USING btree (tenant_id, id)`.

### vh_resident_resolution_photos

Extension được tạo bằng migration SQL; xem định nghĩa cột và FK bên dưới.

Migration tạo: `0006_resident_contract.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **3/0**. Có trong ORM registry: **False**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `tenant_id` | `uuid` | True | PK/FK | `—` | — |
| `resolution_id` | `uuid` | True | PK/FK | `—` | — |
| `file_id` | `uuid` | True | PK/FK | `—` | — |

Ràng buộc:

- `vh_resident_resolution_photos_pkey`: `PRIMARY KEY (tenant_id, resolution_id, file_id)`.
- `vh_resident_resolution_photos_tenant_id_file_id_fkey`: `FOREIGN KEY (tenant_id, file_id) REFERENCES files(tenant_id, id)`.
- `vh_resident_resolution_photos_tenant_id_fkey`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id)`.
- `vh_resident_resolution_photos_tenant_id_resolution_id_fkey`: `FOREIGN KEY (tenant_id, resolution_id) REFERENCES vh_resident_resolutions(tenant_id, id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX vh_resident_resolution_photos_pkey ON public.vh_resident_resolution_photos USING btree (tenant_id, resolution_id, file_id)`.

### vh_resident_resolution_responses

Extension được tạo bằng migration SQL; xem định nghĩa cột và FK bên dưới.

Migration tạo: `0006_resident_contract.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **3/0**. Có trong ORM registry: **False**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | — |
| `tenant_id` | `uuid` | True | FK | `—` | — |
| `case_id` | `uuid` | True | FK | `—` | — |
| `resolution_id` | `uuid` | True | FK | `—` | — |
| `actor_id` | `text` | True | FK | `—` | — |
| `decision` | `text` | True | — | `—` | — |
| `reason` | `text` | False | — | `—` | — |
| `created_at` | `timestamp with time zone` | True | — | `now()` | — |

Ràng buộc:

- `vh_resident_resolution_respon_tenant_id_case_id_resolution_fkey`: `FOREIGN KEY (tenant_id, case_id, resolution_id) REFERENCES vh_resident_resolutions(tenant_id, case_id, id)`.
- `vh_resident_resolution_responses_actor_id_fkey`: `FOREIGN KEY (actor_id) REFERENCES users(id)`.
- `vh_resident_resolution_responses_check`: `CHECK (decision <> 'reopen'::text OR length(reason) >= 8 AND length(reason) <= 2000)`.
- `vh_resident_resolution_responses_decision_check`: `CHECK (decision = ANY (ARRAY['confirm'::text, 'reopen'::text]))`.
- `vh_resident_resolution_responses_pkey`: `PRIMARY KEY (id)`.
- `vh_resident_resolution_responses_tenant_id_fkey`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id)`.
- `vh_resident_resolution_responses_tenant_id_id_key`: `UNIQUE (tenant_id, id)`.
- `vh_resident_resolution_responses_tenant_id_resolution_id_key`: `UNIQUE (tenant_id, resolution_id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX vh_resident_resolution_responses_pkey ON public.vh_resident_resolution_responses USING btree (id)`.
- `CREATE UNIQUE INDEX vh_resident_resolution_responses_tenant_id_id_key ON public.vh_resident_resolution_responses USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX vh_resident_resolution_responses_tenant_id_resolution_id_key ON public.vh_resident_resolution_responses USING btree (tenant_id, resolution_id)`.

### vh_conversation_uploads

Extension được tạo bằng migration SQL; xem định nghĩa cột và FK bên dưới.

Migration tạo: `0004_vinhomes_business_flows.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **5/0**. Có trong ORM registry: **False**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | — |
| `tenant_id` | `uuid` | True | FK | `—` | — |
| `file_id` | `uuid` | True | FK | `—` | — |
| `channel_id` | `text` | True | FK | `—` | — |
| `requested_by` | `text` | True | FK | `—` | — |
| `location_id` | `uuid` | True | FK | `—` | — |
| `object_key` | `text` | True | — | `—` | — |
| `expected_size` | `bigint` | True | — | `—` | — |
| `expected_sha256` | `text` | True | — | `—` | — |
| `mime_type` | `text` | True | — | `—` | — |
| `status` | `text` | True | — | `—` | — |
| `idempotency_key` | `text` | True | — | `—` | — |
| `request_hash` | `text` | True | — | `—` | — |
| `created_at` | `timestamp with time zone` | True | — | `now()` | — |

Ràng buộc:

- `vh_conversation_uploads_expected_sha256_check`: `CHECK (expected_sha256 ~ '^[a-f0-9]{64}$'::text)`.
- `vh_conversation_uploads_expected_size_check`: `CHECK (expected_size > 0 AND expected_size <= 10485760)`.
- `vh_conversation_uploads_pkey`: `PRIMARY KEY (id)`.
- `vh_conversation_uploads_requested_by_fkey`: `FOREIGN KEY (requested_by) REFERENCES users(id)`.
- `vh_conversation_uploads_status_check`: `CHECK (status = ANY (ARRAY['issued'::text, 'uploaded'::text, 'ready'::text]))`.
- `vh_conversation_uploads_tenant_id_channel_id_fkey`: `FOREIGN KEY (tenant_id, channel_id) REFERENCES channels(tenant_id, id)`.
- `vh_conversation_uploads_tenant_id_channel_id_requested_by_i_key`: `UNIQUE (tenant_id, channel_id, requested_by, idempotency_key)`.
- `vh_conversation_uploads_tenant_id_file_id_fkey`: `FOREIGN KEY (tenant_id, file_id) REFERENCES files(tenant_id, id)`.
- `vh_conversation_uploads_tenant_id_file_id_key`: `UNIQUE (tenant_id, file_id)`.
- `vh_conversation_uploads_tenant_id_fkey`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id)`.
- `vh_conversation_uploads_tenant_id_id_key`: `UNIQUE (tenant_id, id)`.
- `vh_conversation_uploads_tenant_id_location_id_fkey`: `FOREIGN KEY (tenant_id, location_id) REFERENCES storage_locations(tenant_id, id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX vh_conversation_uploads_pkey ON public.vh_conversation_uploads USING btree (id)`.
- `CREATE UNIQUE INDEX vh_conversation_uploads_tenant_id_channel_id_requested_by_i_key ON public.vh_conversation_uploads USING btree (tenant_id, channel_id, requested_by, idempotency_key)`.
- `CREATE UNIQUE INDEX vh_conversation_uploads_tenant_id_file_id_key ON public.vh_conversation_uploads USING btree (tenant_id, file_id)`.
- `CREATE UNIQUE INDEX vh_conversation_uploads_tenant_id_id_key ON public.vh_conversation_uploads USING btree (tenant_id, id)`.

## 13 An ninh

### security_cameras

Extension được tạo bằng migration SQL; xem định nghĩa cột và FK bên dưới.

Migration tạo: `0003_vinhomes_security.sql`. Dòng hiện tại: **2**. RLS/FORCE: **True/True**. FK ra/vào: **2/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | — |
| `tenant_id` | `uuid` | True | FK | `—` | — |
| `building_id` | `uuid` | True | FK | `—` | — |
| `code` | `text` | True | — | `—` | — |
| `name` | `text` | True | — | `—` | — |
| `location` | `text` | True | — | `—` | — |
| `status` | `text` | True | — | `—` | — |
| `created_at` | `timestamp with time zone` | True | — | `now()` | — |

Ràng buộc:

- `security_cameras_code`: `UNIQUE (tenant_id, building_id, code)`.
- `security_cameras_pkey`: `PRIMARY KEY (id)`.
- `security_cameras_status`: `CHECK (status = ANY (ARRAY['online'::text, 'offline'::text, 'maintenance'::text]))`.
- `security_cameras_tenant_id_building_id_buildings_tenant_id_id_f`: `FOREIGN KEY (tenant_id, building_id) REFERENCES buildings(tenant_id, id)`.
- `security_cameras_tenant_id_tenants_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id)`.
- `security_cameras_tenant_key`: `UNIQUE (tenant_id, id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX security_cameras_code ON public.security_cameras USING btree (tenant_id, building_id, code)`.
- `CREATE UNIQUE INDEX security_cameras_pkey ON public.security_cameras USING btree (id)`.
- `CREATE UNIQUE INDEX security_cameras_tenant_key ON public.security_cameras USING btree (tenant_id, id)`.

### security_emergency_contacts

Extension được tạo bằng migration SQL; xem định nghĩa cột và FK bên dưới.

Migration tạo: `0003_vinhomes_security.sql`. Dòng hiện tại: **2**. RLS/FORCE: **True/True**. FK ra/vào: **3/1**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | — |
| `tenant_id` | `uuid` | True | FK | `—` | — |
| `building_id` | `uuid` | True | FK | `—` | — |
| `user_id` | `text` | True | FK | `—` | — |
| `name` | `text` | True | — | `—` | — |
| `role_label` | `text` | True | — | `—` | — |
| `phone` | `text` | True | — | `—` | — |
| `position` | `integer` | True | — | `—` | — |
| `ack_timeout_seconds` | `integer` | True | — | `60` | — |
| `status` | `text` | True | — | `'active'::text` | — |

Ràng buộc:

- `security_contacts_order`: `UNIQUE (tenant_id, building_id, "position")`.
- `security_contacts_tenant_key`: `UNIQUE (tenant_id, id)`.
- `security_contacts_values`: `CHECK ("position" > 0 AND ack_timeout_seconds >= 5 AND ack_timeout_seconds <= 3600 AND (status = ANY (ARRAY['active'::text, 'disabled'::text])))`.
- `security_emergency_contacts_pkey`: `PRIMARY KEY (id)`.
- `security_emergency_contacts_tenant_id_building_id_buildings_ten`: `FOREIGN KEY (tenant_id, building_id) REFERENCES buildings(tenant_id, id)`.
- `security_emergency_contacts_tenant_id_tenants_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id)`.
- `security_emergency_contacts_user_id_users_id_fk`: `FOREIGN KEY (user_id) REFERENCES users(id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX security_contacts_order ON public.security_emergency_contacts USING btree (tenant_id, building_id, "position")`.
- `CREATE UNIQUE INDEX security_contacts_tenant_key ON public.security_emergency_contacts USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX security_emergency_contacts_pkey ON public.security_emergency_contacts USING btree (id)`.

### security_alerts

Extension được tạo bằng migration SQL; xem định nghĩa cột và FK bên dưới.

Migration tạo: `0003_vinhomes_security.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **3/1**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | — |
| `tenant_id` | `uuid` | True | FK | `—` | — |
| `ticket_id` | `uuid` | True | FK | `—` | — |
| `created_by` | `text` | True | FK | `—` | — |
| `message` | `text` | True | — | `—` | — |
| `idempotency_key` | `text` | True | — | `—` | — |
| `request_hash` | `text` | True | — | `—` | — |
| `status` | `text` | True | — | `'open'::text` | — |
| `version` | `integer` | True | — | `0` | — |
| `created_at` | `timestamp with time zone` | True | — | `now()` | — |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | — |

Ràng buộc:

- `security_alerts_created_by_users_id_fk`: `FOREIGN KEY (created_by) REFERENCES users(id)`.
- `security_alerts_idempotency`: `UNIQUE (tenant_id, ticket_id, idempotency_key)`.
- `security_alerts_pkey`: `PRIMARY KEY (id)`.
- `security_alerts_status`: `CHECK ((status = ANY (ARRAY['open'::text, 'acknowledged'::text, 'exhausted'::text])) AND version >= 0)`.
- `security_alerts_tenant_id_tenants_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id)`.
- `security_alerts_tenant_id_ticket_id_tickets_tenant_id_id_fk`: `FOREIGN KEY (tenant_id, ticket_id) REFERENCES tickets(tenant_id, id)`.
- `security_alerts_tenant_key`: `UNIQUE (tenant_id, id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX security_alerts_idempotency ON public.security_alerts USING btree (tenant_id, ticket_id, idempotency_key)`.
- `CREATE UNIQUE INDEX security_alerts_pkey ON public.security_alerts USING btree (id)`.
- `CREATE UNIQUE INDEX security_alerts_tenant_key ON public.security_alerts USING btree (tenant_id, id)`.

### security_alert_deliveries

Extension được tạo bằng migration SQL; xem định nghĩa cột và FK bên dưới.

Migration tạo: `0003_vinhomes_security.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **4/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | — |
| `tenant_id` | `uuid` | True | FK | `—` | — |
| `alert_id` | `uuid` | True | FK | `—` | — |
| `contact_id` | `uuid` | True | FK | `—` | — |
| `recipient_user_id` | `text` | True | FK | `—` | — |
| `position` | `integer` | True | — | `—` | — |
| `ack_timeout_seconds` | `integer` | True | — | `—` | — |
| `status` | `text` | True | — | `'waiting'::text` | — |
| `notified_at` | `timestamp with time zone` | False | — | `—` | — |
| `deadline_at` | `timestamp with time zone` | False | — | `—` | — |
| `acknowledged_at` | `timestamp with time zone` | False | — | `—` | — |

Ràng buộc:

- `security_alert_deliveries_pkey`: `PRIMARY KEY (id)`.
- `security_alert_deliveries_recipient_user_id_users_id_fk`: `FOREIGN KEY (recipient_user_id) REFERENCES users(id)`.
- `security_alert_deliveries_tenant_id_alert_id_security_alerts_te`: `FOREIGN KEY (tenant_id, alert_id) REFERENCES security_alerts(tenant_id, id)`.
- `security_alert_deliveries_tenant_id_contact_id_security_emergen`: `FOREIGN KEY (tenant_id, contact_id) REFERENCES security_emergency_contacts(tenant_id, id)`.
- `security_alert_deliveries_tenant_id_tenants_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id)`.
- `security_deliveries_order`: `UNIQUE (tenant_id, alert_id, "position")`.
- `security_deliveries_status`: `CHECK ((status = ANY (ARRAY['waiting'::text, 'pending'::text, 'acknowledged'::text, 'timed_out'::text, 'cancelled'::text])) AND "position" > 0 AND ack_timeout_seconds >= 5 AND ack_timeout_seconds <= 3600)`.
- `security_deliveries_tenant_key`: `UNIQUE (tenant_id, id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX security_alert_deliveries_pkey ON public.security_alert_deliveries USING btree (id)`.
- `CREATE UNIQUE INDEX security_deliveries_order ON public.security_alert_deliveries USING btree (tenant_id, alert_id, "position")`.
- `CREATE UNIQUE INDEX security_deliveries_tenant_key ON public.security_alert_deliveries USING btree (tenant_id, id)`.

### vh_security_checkpoints

Extension được tạo bằng migration SQL; xem định nghĩa cột và FK bên dưới.

Migration tạo: `0001_vinhomes_operations.sql`. Dòng hiện tại: **1**. RLS/FORCE: **True/True**. FK ra/vào: **2/0**. Có trong ORM registry: **False**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | — |
| `tenant_id` | `uuid` | True | FK | `—` | — |
| `site_id` | `uuid` | True | FK | `—` | — |
| `name` | `text` | True | — | `—` | — |
| `location` | `text` | True | — | `—` | — |
| `sort_order` | `integer` | True | — | `0` | — |
| `status` | `text` | True | — | `—` | — |
| `checked_at` | `timestamp with time zone` | False | — | `—` | — |
| `guard_user_id` | `text` | False | FK | `—` | — |
| `notes` | `text` | False | — | `—` | — |
| `created_at` | `timestamp with time zone` | True | — | `now()` | — |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | — |

Ràng buộc:

- `vh_security_checkpoints_guard_user_id_fkey`: `FOREIGN KEY (guard_user_id) REFERENCES users(id)`.
- `vh_security_checkpoints_pkey`: `PRIMARY KEY (id)`.
- `vh_security_checkpoints_status_check`: `CHECK (status = ANY (ARRAY['pending'::text, 'checked'::text, 'missed'::text]))`.
- `vh_security_checkpoints_tenant_id_id_key`: `UNIQUE (tenant_id, id)`.
- `vh_security_checkpoints_tenant_id_site_id_fkey`: `FOREIGN KEY (tenant_id, site_id) REFERENCES sites(tenant_id, id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX vh_security_checkpoints_pkey ON public.vh_security_checkpoints USING btree (id)`.
- `CREATE UNIQUE INDEX vh_security_checkpoints_tenant_id_id_key ON public.vh_security_checkpoints USING btree (tenant_id, id)`.

### vh_security_handovers

Extension được tạo bằng migration SQL; xem định nghĩa cột và FK bên dưới.

Migration tạo: `0001_vinhomes_operations.sql`. Dòng hiện tại: **1**. RLS/FORCE: **True/True**. FK ra/vào: **3/0**. Có trong ORM registry: **False**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | — |
| `tenant_id` | `uuid` | True | FK | `—` | — |
| `site_id` | `uuid` | True | FK | `—` | — |
| `shift_name` | `text` | True | — | `—` | — |
| `shift_date` | `date` | True | — | `—` | — |
| `payload` | `jsonb` | True | — | `—` | — |
| `from_user_id` | `text` | True | FK | `—` | — |
| `to_user_id` | `text` | True | FK | `—` | — |
| `confirmed` | `boolean` | True | — | `false` | — |
| `created_at` | `timestamp with time zone` | True | — | `now()` | — |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | — |

Ràng buộc:

- `vh_security_handovers_from_user_id_fkey`: `FOREIGN KEY (from_user_id) REFERENCES users(id)`.
- `vh_security_handovers_pkey`: `PRIMARY KEY (id)`.
- `vh_security_handovers_shift_name_check`: `CHECK (shift_name = ANY (ARRAY['ca_sang'::text, 'ca_chieu'::text, 'ca_dem'::text]))`.
- `vh_security_handovers_tenant_id_id_key`: `UNIQUE (tenant_id, id)`.
- `vh_security_handovers_tenant_id_site_id_fkey`: `FOREIGN KEY (tenant_id, site_id) REFERENCES sites(tenant_id, id)`.
- `vh_security_handovers_to_user_id_fkey`: `FOREIGN KEY (to_user_id) REFERENCES users(id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX vh_security_handovers_pkey ON public.vh_security_handovers USING btree (id)`.
- `CREATE UNIQUE INDEX vh_security_handovers_tenant_id_id_key ON public.vh_security_handovers USING btree (tenant_id, id)`.

### vh_security_incidents

Extension được tạo bằng migration SQL; xem định nghĩa cột và FK bên dưới.

Migration tạo: `0001_vinhomes_operations.sql`. Dòng hiện tại: **1**. RLS/FORCE: **True/True**. FK ra/vào: **3/0**. Có trong ORM registry: **False**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | — |
| `tenant_id` | `uuid` | True | FK | `—` | — |
| `site_id` | `uuid` | True | FK | `—` | — |
| `ticket_id` | `uuid` | False | FK | `—` | — |
| `title` | `text` | True | — | `—` | — |
| `location` | `text` | True | — | `—` | — |
| `severity` | `text` | True | — | `—` | — |
| `report` | `jsonb` | True | — | `—` | — |
| `status` | `text` | True | — | `—` | — |
| `reported_by` | `text` | True | FK | `—` | — |
| `reported_at` | `timestamp with time zone` | True | — | `now()` | — |
| `created_at` | `timestamp with time zone` | True | — | `now()` | — |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | — |

Ràng buộc:

- `vh_security_incidents_pkey`: `PRIMARY KEY (id)`.
- `vh_security_incidents_reported_by_fkey`: `FOREIGN KEY (reported_by) REFERENCES users(id)`.
- `vh_security_incidents_severity_check`: `CHECK (severity = ANY (ARRAY['p1'::text, 'p2'::text, 'p3'::text, 'p4'::text]))`.
- `vh_security_incidents_status_check`: `CHECK (status = ANY (ARRAY['investigating'::text, 'resolved'::text, 'escalated_to_police'::text]))`.
- `vh_security_incidents_tenant_id_id_key`: `UNIQUE (tenant_id, id)`.
- `vh_security_incidents_tenant_id_site_id_fkey`: `FOREIGN KEY (tenant_id, site_id) REFERENCES sites(tenant_id, id)`.
- `vh_security_incidents_tenant_id_ticket_id_fkey`: `FOREIGN KEY (tenant_id, ticket_id) REFERENCES tickets(tenant_id, id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX vh_security_incidents_pkey ON public.vh_security_incidents USING btree (id)`.
- `CREATE UNIQUE INDEX vh_security_incidents_tenant_id_id_key ON public.vh_security_incidents USING btree (tenant_id, id)`.

## 14 Technical agent API

### vh_technical_agent_grants

Extension được tạo bằng migration SQL; xem định nghĩa cột và FK bên dưới.

Migration tạo: `0009_technical_agent_api.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **3/0**. Có trong ORM registry: **False**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `tenant_id` | `uuid` | True | PK/FK | `—` | — |
| `agent_id` | `text` | True | PK/FK | `—` | — |
| `capability` | `text` | True | PK | `—` | — |
| `scope_id` | `uuid` | True | PK/FK | `—` | — |

Ràng buộc:

- `vh_technical_agent_grants_agent_id_fkey`: `FOREIGN KEY (agent_id) REFERENCES agents(id)`.
- `vh_technical_agent_grants_pkey`: `PRIMARY KEY (tenant_id, agent_id, capability, scope_id)`.
- `vh_technical_agent_grants_tenant_id_fkey`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id)`.
- `vh_technical_agent_grants_tenant_id_scope_id_fkey`: `FOREIGN KEY (tenant_id, scope_id) REFERENCES access_scopes(tenant_id, id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX vh_technical_agent_grants_pkey ON public.vh_technical_agent_grants USING btree (tenant_id, agent_id, capability, scope_id)`.

### vh_technical_api_audit

Extension được tạo bằng migration SQL; xem định nghĩa cột và FK bên dưới.

Migration tạo: `0009_technical_agent_api.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **1/0**. Có trong ORM registry: **False**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | — |
| `tenant_id` | `uuid` | True | FK | `—` | — |
| `metadata` | `jsonb` | True | — | `—` | — |
| `created_at` | `timestamp with time zone` | True | — | `now()` | — |

Ràng buộc:

- `vh_technical_api_audit_pkey`: `PRIMARY KEY (id)`.
- `vh_technical_api_audit_tenant_id_fkey`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX vh_technical_api_audit_pkey ON public.vh_technical_api_audit USING btree (id)`.

### vh_technical_api_receipts

Extension được tạo bằng migration SQL; xem định nghĩa cột và FK bên dưới.

Migration tạo: `0009_technical_agent_api.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **1/0**. Có trong ORM registry: **False**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `tenant_id` | `uuid` | True | PK/FK | `—` | — |
| `actor_id` | `text` | True | PK | `—` | — |
| `tool` | `text` | True | PK | `—` | — |
| `idempotency_key` | `text` | True | PK | `—` | — |
| `payload_hash` | `text` | True | — | `—` | — |
| `outcome` | `jsonb` | True | — | `—` | — |
| `response` | `jsonb` | True | — | `—` | — |
| `created_at` | `timestamp with time zone` | True | — | `now()` | — |

Ràng buộc:

- `vh_technical_api_receipts_pkey`: `PRIMARY KEY (tenant_id, actor_id, tool, idempotency_key)`.
- `vh_technical_api_receipts_tenant_id_fkey`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX vh_technical_api_receipts_pkey ON public.vh_technical_api_receipts USING btree (tenant_id, actor_id, tool, idempotency_key)`.

### vh_technical_approval_requests

Extension được tạo bằng migration SQL; xem định nghĩa cột và FK bên dưới.

Migration tạo: `0009_technical_agent_api.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **3/0**. Có trong ORM registry: **False**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `tenant_id` | `uuid` | True | PK/FK | `—` | — |
| `id` | `text` | True | PK | `—` | — |
| `building_id` | `uuid` | True | FK | `—` | — |
| `incident_id` | `uuid` | True | FK | `—` | — |
| `kind` | `text` | True | — | `—` | — |
| `status` | `text` | True | — | `'pending'::text` | — |
| `payload` | `jsonb` | True | — | `—` | — |

Ràng buộc:

- `vh_technical_approval_requests_kind_check`: `CHECK (kind = ANY (ARRAY['power_isolation'::text, 'area_restriction'::text, 'apartment_entry'::text, 'vendor_dispatch'::text]))`.
- `vh_technical_approval_requests_pkey`: `PRIMARY KEY (tenant_id, id)`.
- `vh_technical_approval_requests_status_check`: `CHECK (status = ANY (ARRAY['pending'::text, 'approved'::text, 'rejected'::text, 'cancelled'::text, 'completed'::text]))`.
- `vh_technical_approval_requests_tenant_id_building_id_fkey`: `FOREIGN KEY (tenant_id, building_id) REFERENCES buildings(tenant_id, id)`.
- `vh_technical_approval_requests_tenant_id_fkey`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id)`.
- `vh_technical_approval_requests_tenant_id_incident_id_fkey`: `FOREIGN KEY (tenant_id, incident_id) REFERENCES tickets(tenant_id, id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX vh_technical_approval_requests_pkey ON public.vh_technical_approval_requests USING btree (tenant_id, id)`.

### vh_technical_executor_results

Extension được tạo bằng migration SQL; xem định nghĩa cột và FK bên dưới.

Migration tạo: `0009_technical_agent_api.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **3/0**. Có trong ORM registry: **False**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `tenant_id` | `uuid` | True | PK/FK | `—` | — |
| `id` | `text` | True | PK | `—` | — |
| `building_id` | `uuid` | True | FK | `—` | — |
| `work_order_id` | `uuid` | True | FK | `—` | — |
| `payload` | `jsonb` | True | — | `—` | — |

Ràng buộc:

- `vh_technical_executor_results_pkey`: `PRIMARY KEY (tenant_id, id)`.
- `vh_technical_executor_results_tenant_id_building_id_fkey`: `FOREIGN KEY (tenant_id, building_id) REFERENCES buildings(tenant_id, id)`.
- `vh_technical_executor_results_tenant_id_fkey`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id)`.
- `vh_technical_executor_results_tenant_id_work_order_id_fkey`: `FOREIGN KEY (tenant_id, work_order_id) REFERENCES work_orders(tenant_id, id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX vh_technical_executor_results_pkey ON public.vh_technical_executor_results USING btree (tenant_id, id)`.

### vh_technical_maintenance_events

Extension được tạo bằng migration SQL; xem định nghĩa cột và FK bên dưới.

Migration tạo: `0009_technical_agent_api.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **4/1**. Có trong ORM registry: **False**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `tenant_id` | `uuid` | True | PK/FK | `—` | — |
| `id` | `text` | True | PK | `—` | — |
| `building_id` | `uuid` | True | FK | `—` | — |
| `asset_id` | `text` | True | — | `—` | — |
| `work_order_id` | `uuid` | False | FK | `—` | — |
| `supersedes_event_id` | `text` | False | FK | `—` | — |
| `occurred_at` | `timestamp with time zone` | True | — | `—` | — |
| `payload` | `jsonb` | True | — | `—` | — |

Ràng buộc:

- `vh_technical_maintenance_even_tenant_id_supersedes_event_i_fkey`: `FOREIGN KEY (tenant_id, supersedes_event_id) REFERENCES vh_technical_maintenance_events(tenant_id, id)`.
- `vh_technical_maintenance_even_tenant_id_supersedes_event_id_key`: `UNIQUE (tenant_id, supersedes_event_id)`.
- `vh_technical_maintenance_events_pkey`: `PRIMARY KEY (tenant_id, id)`.
- `vh_technical_maintenance_events_tenant_id_building_id_fkey`: `FOREIGN KEY (tenant_id, building_id) REFERENCES buildings(tenant_id, id)`.
- `vh_technical_maintenance_events_tenant_id_fkey`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id)`.
- `vh_technical_maintenance_events_tenant_id_work_order_id_fkey`: `FOREIGN KEY (tenant_id, work_order_id) REFERENCES work_orders(tenant_id, id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX vh_technical_maintenance_even_tenant_id_supersedes_event_id_key ON public.vh_technical_maintenance_events USING btree (tenant_id, supersedes_event_id)`.
- `CREATE UNIQUE INDEX vh_technical_maintenance_events_pkey ON public.vh_technical_maintenance_events USING btree (tenant_id, id)`.

### vh_technical_measurement_records

Extension được tạo bằng migration SQL; xem định nghĩa cột và FK bên dưới.

Migration tạo: `0009_technical_agent_api.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **3/0**. Có trong ORM registry: **False**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `tenant_id` | `uuid` | True | PK/FK | `—` | — |
| `id` | `text` | True | PK | `—` | — |
| `building_id` | `uuid` | True | FK | `—` | — |
| `work_order_id` | `uuid` | True | FK | `—` | — |
| `asset_id` | `text` | False | — | `—` | — |
| `payload` | `jsonb` | True | — | `—` | — |

Ràng buộc:

- `vh_technical_measurement_records_pkey`: `PRIMARY KEY (tenant_id, id)`.
- `vh_technical_measurement_records_tenant_id_building_id_fkey`: `FOREIGN KEY (tenant_id, building_id) REFERENCES buildings(tenant_id, id)`.
- `vh_technical_measurement_records_tenant_id_fkey`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id)`.
- `vh_technical_measurement_records_tenant_id_work_order_id_fkey`: `FOREIGN KEY (tenant_id, work_order_id) REFERENCES work_orders(tenant_id, id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX vh_technical_measurement_records_pkey ON public.vh_technical_measurement_records USING btree (tenant_id, id)`.

### vh_technical_measurements

Extension được tạo bằng migration SQL; xem định nghĩa cột và FK bên dưới.

Migration tạo: `0004_vinhomes_business_flows.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **3/0**. Có trong ORM registry: **False**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | — |
| `tenant_id` | `uuid` | True | FK | `—` | — |
| `work_order_id` | `uuid` | True | FK | `—` | — |
| `parameter` | `text` | True | — | `—` | — |
| `value` | `numeric` | True | — | `—` | — |
| `unit` | `text` | True | — | `—` | — |
| `note` | `text` | True | — | `—` | — |
| `recorded_by` | `text` | True | FK | `—` | — |
| `measured_at` | `timestamp with time zone` | True | — | `—` | — |
| `created_at` | `timestamp with time zone` | True | — | `now()` | — |

Ràng buộc:

- `vh_technical_measurements_pkey`: `PRIMARY KEY (id)`.
- `vh_technical_measurements_recorded_by_fkey`: `FOREIGN KEY (recorded_by) REFERENCES users(id)`.
- `vh_technical_measurements_tenant_id_fkey`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id)`.
- `vh_technical_measurements_tenant_id_id_key`: `UNIQUE (tenant_id, id)`.
- `vh_technical_measurements_tenant_id_work_order_id_fkey`: `FOREIGN KEY (tenant_id, work_order_id) REFERENCES work_orders(tenant_id, id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX vh_technical_measurements_pkey ON public.vh_technical_measurements USING btree (id)`.
- `CREATE UNIQUE INDEX vh_technical_measurements_tenant_id_id_key ON public.vh_technical_measurements USING btree (tenant_id, id)`.

### vh_technical_sensor_samples

Extension được tạo bằng migration SQL; xem định nghĩa cột và FK bên dưới.

Migration tạo: `0009_technical_agent_api.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **1/0**. Có trong ORM registry: **False**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | — |
| `tenant_id` | `uuid` | True | FK | `—` | — |
| `sensor_id` | `text` | True | FK | `—` | — |
| `value` | `numeric` | True | — | `—` | — |
| `unit` | `text` | True | — | `—` | — |
| `observed_at` | `timestamp with time zone` | True | — | `—` | — |
| `quality` | `text` | True | — | `—` | — |

Ràng buộc:

- `vh_technical_sensor_samples_pkey`: `PRIMARY KEY (id)`.
- `vh_technical_sensor_samples_quality_check`: `CHECK (quality = ANY (ARRAY['good'::text, 'uncertain'::text, 'bad'::text, 'unknown'::text]))`.
- `vh_technical_sensor_samples_tenant_id_sensor_id_fkey`: `FOREIGN KEY (tenant_id, sensor_id) REFERENCES vh_technical_sensors(tenant_id, sensor_id)`.

Chỉ mục:

- `CREATE INDEX vh_technical_samples_time ON public.vh_technical_sensor_samples USING btree (tenant_id, sensor_id, observed_at)`.
- `CREATE UNIQUE INDEX vh_technical_sensor_samples_pkey ON public.vh_technical_sensor_samples USING btree (id)`.

### vh_technical_sensors

Extension được tạo bằng migration SQL; xem định nghĩa cột và FK bên dưới.

Migration tạo: `0009_technical_agent_api.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **2/1**. Có trong ORM registry: **False**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `tenant_id` | `uuid` | True | PK/FK | `—` | — |
| `sensor_id` | `text` | True | PK | `—` | — |
| `building_id` | `uuid` | True | FK | `—` | — |
| `asset_id` | `text` | False | — | `—` | — |
| `metric` | `text` | True | — | `—` | — |
| `unit` | `text` | True | — | `—` | — |

Ràng buộc:

- `vh_technical_sensors_pkey`: `PRIMARY KEY (tenant_id, sensor_id)`.
- `vh_technical_sensors_tenant_id_building_id_fkey`: `FOREIGN KEY (tenant_id, building_id) REFERENCES buildings(tenant_id, id)`.
- `vh_technical_sensors_tenant_id_fkey`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX vh_technical_sensors_pkey ON public.vh_technical_sensors USING btree (tenant_id, sensor_id)`.

### vh_technical_sop_profiles

Extension được tạo bằng migration SQL; xem định nghĩa cột và FK bên dưới.

Migration tạo: `0009_technical_agent_api.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **1/0**. Có trong ORM registry: **False**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `tenant_id` | `uuid` | True | PK/FK | `—` | — |
| `document_code` | `text` | True | PK | `—` | — |
| `version_no` | `integer` | True | PK | `—` | — |
| `issue_codes` | `jsonb` | True | — | `—` | — |
| `excerpt` | `text` | True | — | `—` | — |
| `acceptance_criteria` | `jsonb` | True | — | `—` | — |

Ràng buộc:

- `vh_technical_sop_profiles_pkey`: `PRIMARY KEY (tenant_id, document_code, version_no)`.
- `vh_technical_sop_profiles_tenant_id_fkey`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX vh_technical_sop_profiles_pkey ON public.vh_technical_sop_profiles USING btree (tenant_id, document_code, version_no)`.

### vh_technical_vendors

Extension được tạo bằng migration SQL; xem định nghĩa cột và FK bên dưới.

Migration tạo: `0009_technical_agent_api.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **1/0**. Có trong ORM registry: **False**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `tenant_id` | `uuid` | True | PK/FK | `—` | — |
| `id` | `text` | True | PK | `—` | — |
| `payload` | `jsonb` | True | — | `—` | — |

Ràng buộc:

- `vh_technical_vendors_pkey`: `PRIMARY KEY (tenant_id, id)`.
- `vh_technical_vendors_tenant_id_fkey`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX vh_technical_vendors_pkey ON public.vh_technical_vendors USING btree (tenant_id, id)`.

## 15 Báo cáo

### report_requests

Yêu cầu báo cáo DOCX

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **8/2**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `workspace_id` | `uuid` | True | FK | `—` | Workspace của ban quản lý |
| `requested_by` | `text` | True | FK | `—` | Tham chiếu tài khoản người dùng chung của platform |
| `channel_id` | `text` | True | FK | `—` | Tham chiếu cửa sổ reception hoặc groupchat quản lý |
| `source_message_id` | `uuid` | True | FK | `—` | Tham chiếu transcript chính của room |
| `report_type` | `text` | True | — | `—` | Loại báo cáo |
| `scope_id` | `uuid` | True | FK | `—` | Tham chiếu phạm vi quyền có kiểu rõ ràng |
| `period_from` | `timestamp with time zone` | True | — | `—` | Đầu kỳ báo cáo |
| `period_to` | `timestamp with time zone` | True | — | `—` | Cuối kỳ loại trừ |
| `filters` | `jsonb` | True | — | `—` | Bộ lọc đã xác thực scope |
| `metric_version` | `text` | True | — | `—` | Phiên bản định nghĩa chỉ số |
| `as_of` | `timestamp with time zone` | True | — | `—` | Mốc dữ liệu báo cáo |
| `status` | `text` | True | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `run_id` | `uuid` | False | FK | `—` | Tham chiếu theo dõi thực thi xuyên framework |
| `result_file_id` | `uuid` | False | FK | `—` | Tham chiếu metadata file dùng chung |
| `row_count` | `bigint` | False | — | `—` | Số dòng dữ liệu |
| `error_code` | `text` | False | — | `—` | Mã lỗi ổn định |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |

Ràng buộc:

- `report_requests_channel_id_fk`: `FOREIGN KEY (tenant_id, channel_id) REFERENCES channels(tenant_id, id) ON DELETE RESTRICT`.
- `report_requests_check_0`: `CHECK (status = ANY (ARRAY['queued'::text, 'running'::text, 'completed'::text, 'failed'::text, 'cancelled'::text]))`.
- `report_requests_pkey`: `PRIMARY KEY (id)`.
- `report_requests_requested_by_fk`: `FOREIGN KEY (requested_by) REFERENCES users(id) ON DELETE RESTRICT`.
- `report_requests_result_file_id_fk`: `FOREIGN KEY (tenant_id, result_file_id) REFERENCES files(tenant_id, id) ON DELETE RESTRICT`.
- `report_requests_run_id_fk`: `FOREIGN KEY (tenant_id, run_id) REFERENCES agent_runs(tenant_id, id) ON DELETE RESTRICT`.
- `report_requests_scope_id_fk`: `FOREIGN KEY (tenant_id, scope_id) REFERENCES access_scopes(tenant_id, id) ON DELETE RESTRICT`.
- `report_requests_source_message_id_fk`: `FOREIGN KEY (tenant_id, source_message_id) REFERENCES messages(tenant_id, id) ON DELETE RESTRICT`.
- `report_requests_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `report_requests_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `report_requests_workspace_id_fk`: `FOREIGN KEY (tenant_id, workspace_id) REFERENCES workspaces(tenant_id, id) ON DELETE RESTRICT`.

Chỉ mục:

- `CREATE UNIQUE INDEX report_requests_pkey ON public.report_requests USING btree (id)`.
- `CREATE INDEX report_requests_run_id_idx ON public.report_requests USING btree (tenant_id, run_id)`.
- `CREATE UNIQUE INDEX report_requests_tenant_key_uq ON public.report_requests USING btree (tenant_id, id)`.
- `CREATE INDEX report_requests_workspace_id_idx ON public.report_requests USING btree (tenant_id, workspace_id)`.

### report_sources

Tái lập số liệu báo cáo

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **3/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `report_id` | `uuid` | True | FK | `—` | Tham chiếu yêu cầu báo cáo docx |
| `dataset` | `text` | True | — | `—` | Tên tập dữ liệu |
| `query_template` | `text` | True | — | `—` | ID truy vấn allowlist, không phải SQL tùy ý |
| `parameters` | `jsonb` | True | — | `—` | Tham số cấu hình |
| `source_watermark` | `timestamp with time zone` | True | — | `—` | Mốc dữ liệu nguồn |
| `row_count` | `bigint` | True | — | `—` | Số dòng dữ liệu |
| `result_hash` | `text` | True | — | `—` | Hash kết quả |
| `snapshot_file_id` | `uuid` | False | FK | `—` | Tham chiếu metadata file dùng chung |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |

Ràng buộc:

- `report_sources_pkey`: `PRIMARY KEY (id)`.
- `report_sources_report_id_fk`: `FOREIGN KEY (tenant_id, report_id) REFERENCES report_requests(tenant_id, id) ON DELETE RESTRICT`.
- `report_sources_snapshot_file_id_fk`: `FOREIGN KEY (tenant_id, snapshot_file_id) REFERENCES files(tenant_id, id) ON DELETE RESTRICT`.
- `report_sources_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `report_sources_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `report_sources_unique_0`: `UNIQUE (report_id, dataset)`.

Chỉ mục:

- `CREATE UNIQUE INDEX report_sources_pkey ON public.report_sources USING btree (id)`.
- `CREATE UNIQUE INDEX report_sources_tenant_key_uq ON public.report_sources USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX report_sources_unique_0 ON public.report_sources USING btree (report_id, dataset)`.

### vh_report_exports

Extension được tạo bằng migration SQL; xem định nghĩa cột và FK bên dưới.

Migration tạo: `0004_vinhomes_business_flows.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **3/0**. Có trong ORM registry: **False**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | — |
| `tenant_id` | `uuid` | True | FK | `—` | — |
| `building_id` | `uuid` | True | FK | `—` | — |
| `created_by` | `text` | True | FK | `—` | — |
| `kind` | `text` | True | — | `—` | — |
| `filters` | `jsonb` | True | — | `—` | — |
| `status` | `text` | True | — | `—` | — |
| `content` | `bytea` | False | — | `—` | — |
| `error_code` | `text` | False | — | `—` | — |
| `idempotency_key` | `text` | True | — | `—` | — |
| `request_hash` | `text` | True | — | `—` | — |
| `created_at` | `timestamp with time zone` | True | — | `now()` | — |

Ràng buộc:

- `vh_report_exports_check`: `CHECK (status = 'ready'::text AND content IS NOT NULL OR status = 'failed'::text AND content IS NULL)`.
- `vh_report_exports_created_by_fkey`: `FOREIGN KEY (created_by) REFERENCES users(id)`.
- `vh_report_exports_kind_check`: `CHECK (kind = ANY (ARRAY['incident_frequency'::text, 'issued_revenue'::text]))`.
- `vh_report_exports_pkey`: `PRIMARY KEY (id)`.
- `vh_report_exports_status_check`: `CHECK (status = ANY (ARRAY['ready'::text, 'failed'::text]))`.
- `vh_report_exports_tenant_id_building_id_fkey`: `FOREIGN KEY (tenant_id, building_id) REFERENCES buildings(tenant_id, id)`.
- `vh_report_exports_tenant_id_created_by_idempotency_key_key`: `UNIQUE (tenant_id, created_by, idempotency_key)`.
- `vh_report_exports_tenant_id_fkey`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id)`.
- `vh_report_exports_tenant_id_id_key`: `UNIQUE (tenant_id, id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX vh_report_exports_pkey ON public.vh_report_exports USING btree (id)`.
- `CREATE UNIQUE INDEX vh_report_exports_tenant_id_created_by_idempotency_key_key ON public.vh_report_exports USING btree (tenant_id, created_by, idempotency_key)`.
- `CREATE UNIQUE INDEX vh_report_exports_tenant_id_id_key ON public.vh_report_exports USING btree (tenant_id, id)`.

## 16 Tools, MCP, skills và computer

### action_policy

Chính sách computer-use toàn platform

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **False/False**. FK ra/vào: **0/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `text` | True | PK | `—` | Định danh bản ghi |
| `mode` | `text` | True | — | `—` | Chế độ thực thi policy |
| `deny` | `text[]` | True | — | `—` | Danh sách bị chặn |
| `allow` | `text[]` | True | — | `—` | Danh sách được cho phép |
| `updated_by` | `text` | False | — | `—` | Giá trị updated_by; ý nghĩa và phạm vi theo quy tắc bảng |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |

Ràng buộc:

- `action_policy_check_0`: `CHECK (mode = ANY (ARRAY['enforce'::text, 'dry'::text]))`.
- `action_policy_pkey`: `PRIMARY KEY (id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX action_policy_pkey ON public.action_policy USING btree (id)`.

### mcp_servers

Danh mục MCP server

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **3/2**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `text` | True | PK | `—` | Định danh bản ghi |
| `title` | `text` | True | — | `—` | Tiêu đề |
| `vendor` | `text` | True | — | `—` | Nhà cung cấp MCP |
| `url` | `text` | True | — | `—` | Địa chỉ endpoint |
| `provenance` | `text` | True | — | `'first-party'::text` | Nguồn gốc thành phần |
| `credential_id` | `uuid` | False | FK | `—` | Tham chiếu kho bí mật mã hóa |
| `auth_scheme` | `text` | False | — | `—` | Cơ chế xác thực |
| `tools_refreshed_at` | `timestamp with time zone` | False | — | `—` | Thời điểm đồng bộ công cụ |
| `last_error` | `text` | False | — | `—` | Lỗi cuối đã lọc dữ liệu nhạy cảm |
| `added_by` | `text` | False | — | `—` | Người thêm |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |
| `tenant_id` | `uuid` | True | FK | `(NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid` | Tenant sở hữu dữ liệu |
| `workspace_id` | `uuid` | False | FK | `—` | Workspace của ban quản lý |

Ràng buộc:

- `mcp_servers_credential_id_fk`: `FOREIGN KEY (credential_id) REFERENCES credentials(id) ON DELETE RESTRICT`.
- `mcp_servers_pkey`: `PRIMARY KEY (id)`.
- `mcp_servers_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `mcp_servers_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `mcp_servers_workspace_id_fk`: `FOREIGN KEY (tenant_id, workspace_id) REFERENCES workspaces(tenant_id, id) ON DELETE RESTRICT`.

Chỉ mục:

- `CREATE UNIQUE INDEX mcp_servers_pkey ON public.mcp_servers USING btree (id)`.
- `CREATE UNIQUE INDEX mcp_servers_tenant_key_uq ON public.mcp_servers USING btree (tenant_id, id)`.
- `CREATE INDEX mcp_servers_workspace_id_idx ON public.mcp_servers USING btree (tenant_id, workspace_id)`.

### mcp_tools

Công cụ được khám phá từ MCP server

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **2/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `server_id` | `text` | True | PK/FK | `—` | Tham chiếu danh mục mcp server |
| `name` | `text` | True | PK | `—` | Tên hiển thị |
| `description` | `text` | True | — | `''::text` | Mô tả |
| `input_schema` | `jsonb` | True | — | `'{}'::jsonb` | JSON Schema đầu vào |
| `effect` | `text` | False | — | `—` | allow hoặc deny đối với ACL; tác động công cụ đối với MCP |
| `destructive` | `boolean` | True | — | `false` | Công cụ có thao tác phá hủy |
| `version` | `text` | False | — | `—` | Phiên bản cấu hình hoặc bộ đếm chống ghi đè |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `tenant_id` | `uuid` | True | FK | `(NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid` | Tenant sở hữu dữ liệu |

Ràng buộc:

- `mcp_tools_server_id_fk`: `FOREIGN KEY (tenant_id, server_id) REFERENCES mcp_servers(tenant_id, id) ON DELETE RESTRICT`.
- `mcp_tools_server_id_name_pk`: `PRIMARY KEY (server_id, name)`.
- `mcp_tools_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.

Chỉ mục:

- `CREATE UNIQUE INDEX mcp_tools_server_id_name_pk ON public.mcp_tools USING btree (server_id, name)`.

### mcp_user_credentials

Credential MCP gắn với từng người dùng

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **4/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `server_id` | `text` | True | PK/FK | `—` | Tham chiếu danh mục mcp server |
| `user_id` | `text` | True | PK/FK | `—` | Tài khoản liên quan |
| `credential_id` | `uuid` | True | FK | `—` | Tham chiếu kho bí mật mã hóa |
| `scope` | `text` | True | — | `—` | Phạm vi OAuth hoặc quyền được cấp |
| `connected_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm kết nối |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |
| `tenant_id` | `uuid` | True | PK/FK | `(NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid` | Tenant sở hữu dữ liệu |

Ràng buộc:

- `mcp_user_credentials_credential_id_fk`: `FOREIGN KEY (credential_id) REFERENCES credentials(id) ON DELETE RESTRICT`.
- `mcp_user_credentials_server_id_fk`: `FOREIGN KEY (tenant_id, server_id) REFERENCES mcp_servers(tenant_id, id) ON DELETE RESTRICT`.
- `mcp_user_credentials_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `mcp_user_credentials_tenant_id_server_id_user_id_pk`: `PRIMARY KEY (tenant_id, server_id, user_id)`.
- `mcp_user_credentials_user_id_fk`: `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT`.

Chỉ mục:

- `CREATE UNIQUE INDEX mcp_user_credentials_tenant_id_server_id_user_id_pk ON public.mcp_user_credentials USING btree (tenant_id, server_id, user_id)`.

### skills

Danh mục skill

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **3/1**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `text` | True | PK | `—` | Định danh bản ghi |
| `owner_user_id` | `text` | False | FK | `—` | Tham chiếu tài khoản người dùng chung của platform |
| `slug` | `text` | True | — | `—` | Định danh skill |
| `title` | `text` | True | — | `—` | Tiêu đề |
| `summary` | `text` | True | — | `—` | Tóm tắt |
| `instructions` | `text` | True | — | `—` | Nội dung chỉ dẫn |
| `origin` | `text` | True | — | `'yours'::text` | Nguồn skill |
| `installed_by` | `text` | False | — | `—` | Người cài đặt |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |
| `tenant_id` | `uuid` | True | FK | `(NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid` | Tenant sở hữu dữ liệu |
| `workspace_id` | `uuid` | False | FK | `—` | Workspace của ban quản lý |

Ràng buộc:

- `skills_owner_user_id_fk`: `FOREIGN KEY (owner_user_id) REFERENCES users(id) ON DELETE RESTRICT`.
- `skills_pkey`: `PRIMARY KEY (id)`.
- `skills_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `skills_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `skills_workspace_id_fk`: `FOREIGN KEY (tenant_id, workspace_id) REFERENCES workspaces(tenant_id, id) ON DELETE RESTRICT`.

Chỉ mục:

- `CREATE UNIQUE INDEX skills_partial_0 ON public.skills USING btree (tenant_id, slug) WHERE ((workspace_id IS NULL) AND (owner_user_id IS NULL))`.
- `CREATE UNIQUE INDEX skills_partial_1 ON public.skills USING btree (tenant_id, owner_user_id, slug) WHERE ((workspace_id IS NULL) AND (owner_user_id IS NOT NULL))`.
- `CREATE UNIQUE INDEX skills_partial_2 ON public.skills USING btree (tenant_id, workspace_id, slug) WHERE ((workspace_id IS NOT NULL) AND (owner_user_id IS NULL))`.
- `CREATE UNIQUE INDEX skills_partial_3 ON public.skills USING btree (tenant_id, workspace_id, owner_user_id, slug) WHERE ((workspace_id IS NOT NULL) AND (owner_user_id IS NOT NULL))`.
- `CREATE UNIQUE INDEX skills_pkey ON public.skills USING btree (id)`.
- `CREATE UNIQUE INDEX skills_tenant_key_uq ON public.skills USING btree (tenant_id, id)`.
- `CREATE INDEX skills_workspace_id_idx ON public.skills USING btree (tenant_id, workspace_id)`.

### skill_tools

Công cụ được skill khai báo

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **2/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `skill_id` | `text` | True | PK/FK | `—` | Tham chiếu danh mục skill |
| `ref` | `text` | True | PK | `—` | Tham chiếu plugin/công cụ đa hình, phải validate bằng resolver |
| `declared_by` | `text` | False | — | `—` | Người khai báo |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `tenant_id` | `uuid` | True | PK/FK | `(NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid` | Tenant sở hữu dữ liệu |

Ràng buộc:

- `skill_tools_skill_id_fk`: `FOREIGN KEY (tenant_id, skill_id) REFERENCES skills(tenant_id, id) ON DELETE RESTRICT`.
- `skill_tools_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `skill_tools_tenant_id_skill_id_ref_pk`: `PRIMARY KEY (tenant_id, skill_id, ref)`.

Chỉ mục:

- `CREATE UNIQUE INDEX skill_tools_tenant_id_skill_id_ref_pk ON public.skill_tools USING btree (tenant_id, skill_id, ref)`.

### plugin_grants

Quyền agent sử dụng plugin hoặc gọi agent khác

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **2/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `kind` | `text` | True | PK | `—` | Loại bản ghi |
| `ref` | `text` | True | PK | `—` | Tham chiếu plugin/công cụ đa hình, phải validate bằng resolver |
| `agent_id` | `text` | True | PK/FK | `—` | Tham chiếu danh mục agent của platform |
| `granted_by` | `text` | False | — | `—` | Người cấp quyền |
| `granted_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cấp quyền |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |
| `tenant_id` | `uuid` | True | PK/FK | `(NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid` | Tenant sở hữu dữ liệu |

Ràng buộc:

- `plugin_grants_agent_id_fk`: `FOREIGN KEY (tenant_id, agent_id) REFERENCES agents(tenant_id, id) ON DELETE RESTRICT`.
- `plugin_grants_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `plugin_grants_tenant_id_kind_ref_agent_id_pk`: `PRIMARY KEY (tenant_id, kind, ref, agent_id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX plugin_grants_tenant_id_kind_ref_agent_id_pk ON public.plugin_grants USING btree (tenant_id, kind, ref, agent_id)`.

### composio_connections

Kết nối Composio của từng người dùng

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **2/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `toolkit` | `text` | True | PK | `—` | Mã toolkit Composio |
| `user_id` | `text` | True | PK/FK | `—` | Tài khoản liên quan |
| `connected_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm kết nối |
| `verified` | `boolean` | True | — | `false` | Đã kiểm tra kết nối |
| `verified_at` | `timestamp with time zone` | False | — | `—` | Thời điểm xác minh |
| `probe_action` | `text` | False | — | `—` | Action kiểm tra kết nối |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |
| `tenant_id` | `uuid` | True | PK/FK | `(NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid` | Tenant sở hữu dữ liệu |

Ràng buộc:

- `composio_connections_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `composio_connections_tenant_id_toolkit_user_id_pk`: `PRIMARY KEY (tenant_id, toolkit, user_id)`.
- `composio_connections_user_id_fk`: `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT`.

Chỉ mục:

- `CREATE UNIQUE INDEX composio_connections_tenant_id_toolkit_user_id_pk ON public.composio_connections USING btree (tenant_id, toolkit, user_id)`.

### components

Catalog thành phần UI được biên dịch cùng ứng dụng

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **False/False**. FK ra/vào: **0/2**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `name` | `text` | True | PK | `—` | Tên hiển thị |
| `title` | `text` | True | — | `—` | Tiêu đề |
| `kind` | `text` | True | — | `—` | Loại bản ghi |
| `draft_description` | `text` | True | — | `—` | Bản nháp của description |
| `published_description` | `text` | False | — | `—` | Bản đã công bố của description |
| `published` | `boolean` | True | — | `false` | Đã công bố |
| `published_at` | `timestamp with time zone` | False | — | `—` | Thời điểm công bố |
| `updated_by` | `text` | False | — | `—` | Giá trị updated_by; ý nghĩa và phạm vi theo quy tắc bảng |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |

Ràng buộc:

- `components_pkey`: `PRIMARY KEY (name)`.

Chỉ mục:

- `CREATE UNIQUE INDEX components_pkey ON public.components USING btree (name)`.

### component_exclusions

Agent không được dùng thành phần UI

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **3/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `component_name` | `text` | True | PK/FK | `—` | Tên component trong catalog |
| `agent_id` | `text` | True | PK/FK | `—` | Tham chiếu danh mục agent của platform |
| `withheld_by` | `text` | False | — | `—` | Người chặn component |
| `withheld_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm chặn |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |
| `tenant_id` | `uuid` | True | FK | `(NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid` | Tenant sở hữu dữ liệu |

Ràng buộc:

- `component_exclusions_agent_id_fk`: `FOREIGN KEY (tenant_id, agent_id) REFERENCES agents(tenant_id, id) ON DELETE RESTRICT`.
- `component_exclusions_component_name_agent_id_pk`: `PRIMARY KEY (component_name, agent_id)`.
- `component_exclusions_component_name_fk`: `FOREIGN KEY (component_name) REFERENCES components(name) ON DELETE RESTRICT`.
- `component_exclusions_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.

Chỉ mục:

- `CREATE UNIQUE INDEX component_exclusions_component_name_agent_id_pk ON public.component_exclusions USING btree (component_name, agent_id)`.

### component_functions

Hàm dữ liệu mà thành phần UI được gọi

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **False/False**. FK ra/vào: **1/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `component_name` | `text` | True | PK/FK | `—` | Tên component trong catalog |
| `function_name` | `text` | True | PK | `—` | Tên hàm có trong code |
| `granted_by` | `text` | False | — | `—` | Người cấp quyền |
| `granted_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cấp quyền |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |

Ràng buộc:

- `component_functions_component_name_fk`: `FOREIGN KEY (component_name) REFERENCES components(name) ON DELETE RESTRICT`.
- `component_functions_component_name_function_name_pk`: `PRIMARY KEY (component_name, function_name)`.

Chỉ mục:

- `CREATE UNIQUE INDEX component_functions_component_name_function_name_pk ON public.component_functions USING btree (component_name, function_name)`.

### sandboxed_components

Thành phần UI do người dùng tạo

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **2/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `name` | `text` | True | PK | `—` | Tên hiển thị |
| `title` | `text` | True | — | `—` | Tiêu đề |
| `draft_description` | `text` | True | — | `''::text` | Bản nháp của description |
| `draft_html` | `text` | True | — | `''::text` | Bản nháp của html |
| `draft_css` | `text` | True | — | `''::text` | Bản nháp của css |
| `draft_js_functions` | `text` | True | — | `''::text` | Bản nháp của js functions |
| `draft_argument_schema` | `jsonb` | True | — | `'{}'::jsonb` | Bản nháp của argument schema |
| `published_description` | `text` | False | — | `—` | Bản đã công bố của description |
| `published_html` | `text` | False | — | `—` | Bản đã công bố của html |
| `published_css` | `text` | False | — | `—` | Bản đã công bố của css |
| `published_js_functions` | `text` | False | — | `—` | Bản đã công bố của js functions |
| `published_argument_schema` | `jsonb` | False | — | `—` | Bản đã công bố của argument schema |
| `sample_arguments` | `jsonb` | True | — | `'{}'::jsonb` | Dữ liệu mẫu dùng kiểm thử component |
| `revision` | `integer` | True | — | `0` | Số phiên bản |
| `published` | `boolean` | True | — | `false` | Đã công bố |
| `published_at` | `timestamp with time zone` | False | — | `—` | Thời điểm công bố |
| `authored_by` | `text` | False | — | `—` | Người soạn UI |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |
| `tenant_id` | `uuid` | True | PK/FK | `(NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid` | Tenant sở hữu dữ liệu |
| `workspace_id` | `uuid` | True | FK | `(NULLIF(current_setting('app.workspace_id'::text, true), ''::text))::uuid` | Workspace của ban quản lý |

Ràng buộc:

- `sandboxed_components_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `sandboxed_components_tenant_id_name_pk`: `PRIMARY KEY (tenant_id, name)`.
- `sandboxed_components_workspace_id_fk`: `FOREIGN KEY (tenant_id, workspace_id) REFERENCES workspaces(tenant_id, id) ON DELETE RESTRICT`.

Chỉ mục:

- `CREATE UNIQUE INDEX sandboxed_components_tenant_id_name_pk ON public.sandboxed_components USING btree (tenant_id, name)`.
- `CREATE INDEX sandboxed_components_workspace_id_idx ON public.sandboxed_components USING btree (tenant_id, workspace_id)`.

### computer_page_frame

Ảnh màn hình theo lượt dùng công cụ

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **2/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `computer_id` | `text` | True | PK | `—` | Định danh computer runtime |
| `tool_call_id` | `text` | True | PK | `—` | Định danh lần gọi công cụ |
| `url` | `text` | True | — | `—` | Địa chỉ endpoint |
| `title` | `text` | False | — | `—` | Tiêu đề |
| `frame` | `text` | True | — | `—` | Ảnh trang theo lượt dùng công cụ |
| `captured_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm chụp |
| `tenant_id` | `uuid` | True | FK | `(NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid` | Tenant sở hữu dữ liệu |
| `agent_id` | `text` | True | FK | `—` | Tham chiếu danh mục agent của platform |

Ràng buộc:

- `computer_page_frame_agent_id_fk`: `FOREIGN KEY (tenant_id, agent_id) REFERENCES agents(tenant_id, id) ON DELETE RESTRICT`.
- `computer_page_frame_computer_id_tool_call_id_pk`: `PRIMARY KEY (computer_id, tool_call_id)`.
- `computer_page_frame_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.

Chỉ mục:

- `CREATE UNIQUE INDEX computer_page_frame_computer_id_tool_call_id_pk ON public.computer_page_frame USING btree (computer_id, tool_call_id)`.

### computer_snapshot

Snapshot mới nhất của computer agent

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **2/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `computer_id` | `text` | True | PK | `—` | Định danh computer runtime |
| `snapshot_id` | `integer` | True | — | `—` | Thế hệ snapshot |
| `url` | `text` | True | — | `—` | Địa chỉ endpoint |
| `elements` | `jsonb` | True | — | `—` | Các phần tử UI của snapshot |
| `taken_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm chụp |
| `session` | `text` | False | — | `—` | Thế hệ phiên computer |
| `tenant_id` | `uuid` | True | FK | `(NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid` | Tenant sở hữu dữ liệu |
| `agent_id` | `text` | True | FK | `—` | Tham chiếu danh mục agent của platform |

Ràng buộc:

- `computer_snapshot_agent_id_fk`: `FOREIGN KEY (tenant_id, agent_id) REFERENCES agents(tenant_id, id) ON DELETE RESTRICT`.
- `computer_snapshot_pkey`: `PRIMARY KEY (computer_id)`.
- `computer_snapshot_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `computer_snapshot_tenant_key_uq`: `UNIQUE (tenant_id, computer_id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX computer_snapshot_pkey ON public.computer_snapshot USING btree (computer_id)`.
- `CREATE UNIQUE INDEX computer_snapshot_tenant_key_uq ON public.computer_snapshot USING btree (tenant_id, computer_id)`.

## 17 Automation, events và audit

### work_items

Hàng đợi tác vụ có lease của OpenBot

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **1/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `kind` | `text` | True | PK | `—` | Loại bản ghi |
| `key` | `text` | True | PK | `—` | Khóa idempotency của tác vụ trong kind |
| `run_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tác vụ đủ điều kiện chạy |
| `claimed_by` | `text` | False | — | `—` | Replica đang giữ việc |
| `lease_until` | `timestamp with time zone` | False | — | `—` | Thời điểm hết lease |
| `attempts` | `integer` | True | — | `0` | Số lần thử |
| `finished_at` | `timestamp with time zone` | False | — | `—` | Thời điểm kết thúc |
| `last_error` | `text` | False | — | `—` | Lỗi cuối đã lọc dữ liệu nhạy cảm |
| `payload` | `jsonb` | True | — | `'{}'::jsonb` | Payload có cấu trúc, không chứa secret thô |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |
| `tenant_id` | `uuid` | False | FK | `—` | Tenant sở hữu dữ liệu |

Ràng buộc:

- `work_items_kind_key_pk`: `PRIMARY KEY (kind, key)`.
- `work_items_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.

Chỉ mục:

- `CREATE UNIQUE INDEX work_items_kind_key_pk ON public.work_items USING btree (kind, key)`.

### routines

Lịch chạy agent

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **5/1**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `text` | True | PK | `—` | Định danh bản ghi |
| `owner_user_id` | `text` | True | FK | `—` | Tham chiếu tài khoản người dùng chung của platform |
| `agent_id` | `text` | True | FK | `—` | Tham chiếu danh mục agent của platform |
| `channel_id` | `text` | True | FK | `—` | Tham chiếu cửa sổ reception hoặc groupchat quản lý |
| `instruction` | `text` | True | — | `—` | Chỉ dẫn cho lượt chạy |
| `cron` | `text` | True | — | `—` | Biểu thức cron 5 trường |
| `timezone` | `text` | True | — | `'UTC'::text` | Múi giờ IANA |
| `enabled` | `boolean` | True | — | `true` | Có được bật hay không |
| `next_run_at` | `timestamp with time zone` | True | — | `—` | Thời điểm chạy tiếp theo |
| `last_run_at` | `timestamp with time zone` | False | — | `—` | Mốc occurrence scheduler gần nhất |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |
| `tenant_id` | `uuid` | True | FK | `(NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid` | Tenant sở hữu dữ liệu |
| `workspace_id` | `uuid` | False | FK | `—` | Workspace của ban quản lý |

Ràng buộc:

- `routines_agent_id_fk`: `FOREIGN KEY (tenant_id, agent_id) REFERENCES agents(tenant_id, id) ON DELETE RESTRICT`.
- `routines_channel_id_fk`: `FOREIGN KEY (tenant_id, channel_id) REFERENCES channels(tenant_id, id) ON DELETE RESTRICT`.
- `routines_owner_user_id_fk`: `FOREIGN KEY (owner_user_id) REFERENCES users(id) ON DELETE RESTRICT`.
- `routines_pkey`: `PRIMARY KEY (id)`.
- `routines_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `routines_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `routines_workspace_id_fk`: `FOREIGN KEY (tenant_id, workspace_id) REFERENCES workspaces(tenant_id, id) ON DELETE RESTRICT`.

Chỉ mục:

- `CREATE UNIQUE INDEX routines_pkey ON public.routines USING btree (id)`.
- `CREATE UNIQUE INDEX routines_tenant_key_uq ON public.routines USING btree (tenant_id, id)`.
- `CREATE INDEX routines_workspace_id_idx ON public.routines USING btree (tenant_id, workspace_id)`.

### routine_runs

Lịch sử thực thi lịch chạy

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **3/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `text` | True | PK | `—` | Định danh bản ghi |
| `routine_id` | `text` | True | FK | `—` | Tham chiếu lịch chạy agent |
| `started_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm bắt đầu |
| `finished_at` | `timestamp with time zone` | False | — | `—` | Thời điểm kết thúc |
| `status` | `routine_run_status` | False | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `error` | `text` | False | — | `—` | Lỗi đã kiểm soát và loại dữ liệu nhạy cảm |
| `tenant_id` | `uuid` | True | FK | `(NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid` | Tenant sở hữu dữ liệu |
| `workspace_id` | `uuid` | False | FK | `—` | Workspace của ban quản lý |
| `scheduled_for` | `timestamp with time zone` | True | — | `—` | Mốc lịch dự kiến của lượt chạy |

Ràng buộc:

- `routine_runs_pkey`: `PRIMARY KEY (id)`.
- `routine_runs_routine_id_fk`: `FOREIGN KEY (tenant_id, routine_id) REFERENCES routines(tenant_id, id) ON DELETE RESTRICT`.
- `routine_runs_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `routine_runs_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `routine_runs_unique_0`: `UNIQUE (routine_id, scheduled_for)`.
- `routine_runs_workspace_id_fk`: `FOREIGN KEY (tenant_id, workspace_id) REFERENCES workspaces(tenant_id, id) ON DELETE RESTRICT`.

Chỉ mục:

- `CREATE UNIQUE INDEX routine_runs_pkey ON public.routine_runs USING btree (id)`.
- `CREATE UNIQUE INDEX routine_runs_tenant_key_uq ON public.routine_runs USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX routine_runs_unique_0 ON public.routine_runs USING btree (routine_id, scheduled_for)`.
- `CREATE INDEX routine_runs_workspace_id_idx ON public.routine_runs USING btree (tenant_id, workspace_id)`.

### routine_sweeps

Dấu vết lượt quét scheduler

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **False/False**. FK ra/vào: **0/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `text` | True | PK | `—` | Định danh bản ghi |
| `swept_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm quét |
| `owner` | `text` | False | — | `—` | Replica sở hữu lượt quét |

Ràng buộc:

- `routine_sweeps_pkey`: `PRIMARY KEY (id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX routine_sweeps_pkey ON public.routine_sweeps USING btree (id)`.

### event_inbox

Dedupe cho từng consumer

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **2/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `consumer` | `text` | True | — | `—` | Consumer xử lý sự kiện |
| `event_id` | `uuid` | True | FK | `—` | Tham chiếu lịch sử nghiệp vụ bất biến |
| `status` | `text` | True | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `attempts` | `integer` | True | — | `0` | Số lần thử |
| `available_at` | `timestamp with time zone` | True | — | `—` | Thời điểm có thể xử lý |
| `lease_owner` | `text` | False | — | `—` | Worker giữ lease |
| `lease_until` | `timestamp with time zone` | False | — | `—` | Thời điểm hết lease |
| `processed_at` | `timestamp with time zone` | False | — | `—` | Thời điểm xử lý xong |
| `last_error` | `text` | False | — | `—` | Lỗi cuối đã lọc dữ liệu nhạy cảm |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |

Ràng buộc:

- `event_inbox_check_0`: `CHECK (status = ANY (ARRAY['pending'::text, 'processing'::text, 'done'::text, 'dead'::text]))`.
- `event_inbox_event_id_fk`: `FOREIGN KEY (tenant_id, event_id) REFERENCES ticket_events(tenant_id, id) ON DELETE RESTRICT`.
- `event_inbox_pkey`: `PRIMARY KEY (id)`.
- `event_inbox_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `event_inbox_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `event_inbox_unique_0`: `UNIQUE (tenant_id, consumer, event_id)`.

Chỉ mục:

- `CREATE UNIQUE INDEX event_inbox_pkey ON public.event_inbox USING btree (id)`.
- `CREATE UNIQUE INDEX event_inbox_tenant_key_uq ON public.event_inbox USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX event_inbox_unique_0 ON public.event_inbox USING btree (tenant_id, consumer, event_id)`.

### event_outbox

Phát sự kiện cùng transaction nghiệp vụ

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **2/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `event_id` | `uuid` | True | FK | `—` | Tham chiếu lịch sử nghiệp vụ bất biến |
| `topic` | `text` | True | — | `—` | Kênh sự kiện logic |
| `payload` | `jsonb` | True | — | `—` | Payload có cấu trúc, không chứa secret thô |
| `schema_version` | `integer` | True | — | `—` | Phiên bản cấu trúc payload |
| `available_at` | `timestamp with time zone` | True | — | `—` | Thời điểm có thể xử lý |
| `published_at` | `timestamp with time zone` | False | — | `—` | Thời điểm công bố |
| `attempts` | `integer` | True | — | `0` | Số lần thử |
| `lease_owner` | `text` | False | — | `—` | Worker giữ lease |
| `lease_until` | `timestamp with time zone` | False | — | `—` | Thời điểm hết lease |
| `last_error` | `text` | False | — | `—` | Lỗi cuối đã lọc dữ liệu nhạy cảm |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |

Ràng buộc:

- `event_outbox_event_id_fk`: `FOREIGN KEY (tenant_id, event_id) REFERENCES ticket_events(tenant_id, id) ON DELETE RESTRICT`.
- `event_outbox_pkey`: `PRIMARY KEY (id)`.
- `event_outbox_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `event_outbox_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `event_outbox_unique_0`: `UNIQUE (event_id, topic)`.

Chỉ mục:

- `CREATE UNIQUE INDEX event_outbox_pkey ON public.event_outbox USING btree (id)`.
- `CREATE UNIQUE INDEX event_outbox_tenant_key_uq ON public.event_outbox USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX event_outbox_unique_0 ON public.event_outbox USING btree (event_id, topic)`.

### notification_deliveries

Thông báo và read marker từng người

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **5/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | True | FK | `—` | Tenant sở hữu dữ liệu |
| `user_id` | `text` | True | FK | `—` | Tài khoản liên quan |
| `ticket_event_id` | `uuid` | False | FK | `—` | Tham chiếu lịch sử nghiệp vụ bất biến |
| `message_id` | `uuid` | False | FK | `—` | Tham chiếu transcript chính của room |
| `interruption_id` | `uuid` | False | FK | `—` | Tham chiếu đợt cắt và mở nước |
| `channel` | `text` | True | — | `—` | Kênh giao thông báo hoặc state channel runtime |
| `dedupe_key` | `text` | True | — | `—` | Khóa chống thông báo trùng |
| `payload` | `jsonb` | True | — | `—` | Payload có cấu trúc, không chứa secret thô |
| `status` | `text` | True | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `attempts` | `integer` | True | — | `0` | Số lần thử |
| `available_at` | `timestamp with time zone` | True | — | `—` | Thời điểm có thể xử lý |
| `sent_at` | `timestamp with time zone` | False | — | `—` | Thời điểm gửi |
| `read_at` | `timestamp with time zone` | False | — | `—` | Thời điểm đọc |
| `provider_message_id` | `text` | False | — | `—` | ID thông báo ở nhà cung cấp |
| `last_error` | `text` | False | — | `—` | Lỗi cuối đã lọc dữ liệu nhạy cảm |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm cập nhật |

Ràng buộc:

- `notification_deliveries_check_0`: `CHECK (channel = ANY (ARRAY['in_app'::text, 'push'::text, 'sms'::text, 'email'::text]))`.
- `notification_deliveries_check_1`: `CHECK (status = ANY (ARRAY['pending'::text, 'sent'::text, 'failed'::text, 'dead'::text]))`.
- `notification_deliveries_interruption_id_fk`: `FOREIGN KEY (tenant_id, interruption_id) REFERENCES service_interruptions(tenant_id, id) ON DELETE RESTRICT`.
- `notification_deliveries_message_id_fk`: `FOREIGN KEY (tenant_id, message_id) REFERENCES messages(tenant_id, id) ON DELETE RESTRICT`.
- `notification_deliveries_pkey`: `PRIMARY KEY (id)`.
- `notification_deliveries_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `notification_deliveries_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `notification_deliveries_ticket_event_id_fk`: `FOREIGN KEY (tenant_id, ticket_event_id) REFERENCES ticket_events(tenant_id, id) ON DELETE RESTRICT`.
- `notification_deliveries_unique_0`: `UNIQUE (tenant_id, user_id, channel, dedupe_key)`.
- `notification_deliveries_user_id_fk`: `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT`.

Chỉ mục:

- `CREATE UNIQUE INDEX notification_deliveries_pkey ON public.notification_deliveries USING btree (id)`.
- `CREATE UNIQUE INDEX notification_deliveries_tenant_key_uq ON public.notification_deliveries USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX notification_deliveries_unique_0 ON public.notification_deliveries USING btree (tenant_id, user_id, channel, dedupe_key)`.
- `CREATE INDEX notification_deliveries_user_id_idx ON public.notification_deliveries USING btree (tenant_id, user_id)`.

### audit_events

Nhật ký kiểm toán bất biến

Migration tạo: `0000_grey_blockbuster.sql`. Dòng hiện tại: **0**. RLS/FORCE: **True/True**. FK ra/vào: **2/0**. Có trong ORM registry: **True**.

| Cột | Kiểu | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | True | PK | `gen_random_uuid()` | Định danh bản ghi |
| `actor_user_id` | `text` | False | — | `—` | Giá trị actor_user_id; ý nghĩa và phạm vi theo quy tắc bảng |
| `initiator_kind` | `text` | True | — | `'person'::text` | Loại nguồn khởi tạo |
| `initiator_id` | `text` | False | — | `—` | Định danh nguồn khởi tạo |
| `event_type` | `text` | True | — | `—` | Loại sự kiện |
| `target_type` | `text` | True | — | `—` | Loại tài nguyên đích |
| `target_id` | `text` | False | — | `—` | Định danh tài nguyên đích |
| `payload` | `jsonb` | True | — | `—` | Payload có cấu trúc, không chứa secret thô |
| `created_at` | `timestamp with time zone` | True | — | `now()` | Thời điểm tạo |
| `tenant_id` | `uuid` | False | FK | `—` | Tenant sở hữu dữ liệu |
| `workspace_id` | `uuid` | False | FK | `—` | Workspace của ban quản lý |
| `request_id` | `text` | False | — | `—` | Mã tương quan request trong audit |
| `correlation_id` | `uuid` | False | — | `—` | ID liên kết toàn bộ luồng xử lý |
| `actor_snapshot` | `jsonb` | True | — | `'{}'::jsonb` | Thông tin actor tối thiểu tại thời điểm hành động |

Ràng buộc:

- `audit_events_pkey`: `PRIMARY KEY (id)`.
- `audit_events_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `audit_events_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `audit_events_workspace_id_fk`: `FOREIGN KEY (tenant_id, workspace_id) REFERENCES workspaces(tenant_id, id) ON DELETE RESTRICT`.

Chỉ mục:

- `CREATE UNIQUE INDEX audit_events_pkey ON public.audit_events USING btree (id)`.
- `CREATE UNIQUE INDEX audit_events_tenant_key_uq ON public.audit_events USING btree (tenant_id, id)`.
- `CREATE INDEX audit_events_workspace_id_idx ON public.audit_events USING btree (tenant_id, workspace_id)`.
