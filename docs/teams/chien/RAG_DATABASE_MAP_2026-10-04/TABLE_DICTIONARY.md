# Từ điển 57 bảng liên quan RAG

Cột, kiểu, nullability, mặc định, PK/FK/UNIQUE/CHECK, indexes, triggers và RLS dưới đây được lấy từ PostgreSQL đã khôi phục bản backup ngày 03/10/2026. Mô tả ngữ nghĩa đối chiếu `server/src/db/design/merged.json` ở checkout `a24ecd7568fedebec6d412da73d685bb820c1a5d`. Nếu có khác biệt, cấu trúc snapshot là nguồn cho báo cáo này.

Phạm vi: 19 bảng lõi RAG/memory, các bảng trực tiếp tham chiếu/được tham chiếu bởi lõi, và lớp quyền/nơi ở/file/runtime mà code Reception/RAG đọc. Không kéo toàn bộ các bảng thanh toán, kỹ thuật và xử lý ticket vào RAG. Catalog thô đầy đủ nằm trong `schema-snapshot.json`.

| Bảng | Dòng snapshot | Vai trò |
|---|---:|---|
| [access_scopes](#access_scopes) | 24 | Địa bàn có kiểu: tenant/site/zone/building/management/...; dùng để giới hạn tài liệu. |
| [agent_knowledge_grants](#agent_knowledge_grants) | 1 | Bảng nối agent với kho được cấp; quyền này vẫn giao với quyền cư dân và tài liệu. |
| [agent_runs](#agent_runs) | 0 | Một lượt thực thi agent; nguồn audit và authority cho retrieval. |
| [agent_teams](#agent_teams) | 0 | Nhóm agent; có thể là audience/namespace shared team. |
| [agent_versions](#agent_versions) | 1 | Phiên bản agent được chọn cho một binding/run. |
| [agents](#agents) | 4 | Danh mục agent; agent Lễ tân được cấp knowledge grant. |
| [buildings](#buildings) | 14 | Tòa nhà thuộc site/zone. |
| [channel_memberships](#channel_memberships) | 23 | Thành viên của kênh và audience được đọc. |
| [channels](#channels) | 23 | Kênh trao đổi chứa câu hỏi/câu trả lời. |
| [context_snapshots](#context_snapshots) | 0 | Context đã chọn của agent run; retrieval_ids là provenance JSON, không phải FK hay quyền truy cập. |
| [document_acl](#document_acl) | 0 | Allow/deny riêng cho user, role hoặc workspace. |
| [document_scopes](#document_scopes) | 127 | Bảng nối tài liệu với địa bàn; applies_to_descendants cho phép áp dụng xuống cấp con. |
| [document_versions](#document_versions) | 115 | Nội dung có phiên bản, hash, file nguồn, thời gian hiệu lực và metadata. |
| [domains](#domains) | 1 | Miền nghiệp vụ của tenant; knowledge base gắn vào domain. |
| [embedding_models](#embedding_models) | 1 | Danh mục không gian vector: provider/model/revision/dimension/metric/active. |
| [execution_principals](#execution_principals) | 2 | Chủ thể thực thi được backend xác minh; có authz_version. |
| [file_access_logs](#file_access_logs) | 0 | Nhật ký truy cập file. |
| [file_objects](#file_objects) | 0 | Đối tượng lưu trữ vật lý của một file. |
| [file_processing_jobs](#file_processing_jobs) | 0 | Job xử lý file ở lớp storage. |
| [file_upload_parts](#file_upload_parts) | 0 | Các phần của upload nhiều phần. |
| [file_uploads](#file_uploads) | 0 | Phiên upload file. |
| [files](#files) | 1 | Định danh file; document_versions.file_id bắt buộc tham chiếu ở đây. |
| [ingestion_jobs](#ingestion_jobs) | 115 | Theo dõi nạp phiên bản bằng một model; chống trùng, trạng thái, lease và số chunks. |
| [knowledge_bases](#knowledge_bases) | 2 | Kho tri thức theo tenant/domain; chứa nhiều tài liệu. |
| [knowledge_categories](#knowledge_categories) | 1 | Danh mục tài liệu; parent_id tạo cây danh mục. |
| [knowledge_chunks](#knowledge_chunks) | 279 | Đoạn văn bản; heading, thứ tự, hash, ước lượng tokens và chỉ mục từ khóa search_tsv. |
| [knowledge_documents](#knowledge_documents) | 116 | Định danh tài liệu; trỏ phiên bản đang phục vụ qua active_version_id. |
| [knowledge_embeddings](#knowledge_embeddings) | 279 | Vector của một chunk với một model; UNIQUE(chunk_id,model_id). |
| [knowledge_reviews](#knowledge_reviews) | 3 | Duyệt một phiên bản tài liệu HOẶC một ứng viên memory, không phải cả hai. |
| [management_coverage](#management_coverage) | 2 | Phạm vi địa bàn mà một đơn vị quản lý phụ trách. |
| [management_units](#management_units) | 1 | Đơn vị quản lý và chủ quản tài liệu. |
| [memory_candidates](#memory_candidates) | 4 | Tri thức đề xuất từ tương tác/nghiệp vụ, có evidence, namespace, phạm vi và trạng thái duyệt. |
| [memory_namespaces](#memory_namespaces) | 1 | Phân vùng bộ nhớ theo owner và audience; đây không phải bảng embedding. |
| [memory_publications](#memory_publications) | 0 | Liên kết ứng viên đã duyệt với tài liệu/phiên bản xuất bản theo cơ chế memory chuẩn. |
| [messages](#messages) | 0 | Nội dung trao đổi; câu hỏi và câu trả lời trong luồng Reception. |
| [reception_sessions](#reception_sessions) | 0 | Trạng thái phiên Reception; không phải kho vector. |
| [report_sources](#report_sources) | 0 | Dataset báo cáo: query_template allowlist, parameters, watermark, row_count, result_hash và file snapshot; không có FK trực tiếp tới document/version/chunk. |
| [retrieval_hits](#retrieval_hits) | 0 | Các chunk được xếp hạng trong một retrieval run; lưu similarity và included. |
| [retrieval_runs](#retrieval_runs) | 0 | Nhật ký một lần tra cứu: người, principal, binding, agent run, query, quyền và độ trễ. |
| [run_memory_access](#run_memory_access) | 0 | Ghi quyền đọc/ghi namespace của một agent run tại một authz_version. |
| [runtime_backends](#runtime_backends) | 1 | Danh mục runtime backend có bật/tắt. |
| [runtime_identities](#runtime_identities) | 0 | Ánh xạ execution principal sang định danh runtime. |
| [runtime_memory_bindings](#runtime_memory_bindings) | 0 | Ánh xạ namespace bộ nhớ của platform sang backend runtime. |
| [runtime_session_bindings](#runtime_session_bindings) | 0 | Ràng buộc agent, version, channel và audience; token phải phù hợp binding đang active. |
| [runtime_session_operations](#runtime_session_operations) | 0 | Nhật ký các thao tác lên phiên runtime; hỗ trợ vòng đời binding. |
| [scoped_user_roles](#scoped_user_roles) | 27 | Vai trò management/staff/... trong một phạm vi và thời gian hiệu lực. |
| [sites](#sites) | 1 | Đô thị/dự án. |
| [storage_locations](#storage_locations) | 1 | Vị trí/bucket lưu trữ; không phải vector store. |
| [tenant_memberships](#tenant_memberships) | 26 | Thành viên đang có hiệu lực của tenant. |
| [tenants](#tenants) | 1 | Ranh giới tenant dùng chung cho dữ liệu và RLS. |
| [tickets](#tickets) | 22 | Nguồn nghiệp vụ có thể sinh memory candidate. |
| [unit_residents](#unit_residents) | 20 | Cư dân–căn hộ; verification_status và valid_from/to quyết định quyền nơi ở. |
| [units](#units) | 20 | Căn hộ thuộc tòa. |
| [users](#users) | 26 | Tài khoản người dùng, người hỏi, người xuất bản và người duyệt. |
| [workspace_members](#workspace_members) | 1 | Thành viên workspace; liên quan ACL/audience. |
| [workspaces](#workspaces) | 1 | Không gian hoạt động của agent/team. |
| [zones](#zones) | 8 | Phân khu thuộc site. |

PK = khóa chính; FK = khóa ngoại. FK `(tenant_id,id)` bảo vệ cùng tenant. RLS tenant không tự thay thế quyền scope/ACL/audience.

## access_scopes

Địa bàn có kiểu: tenant/site/zone/building/management/...; dùng để giới hạn tài liệu.

Số dòng trong snapshot: **24**. RLS: **bật**; FORCE RLS: **bật**.

| Cột | Kiểu PostgreSQL | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | Có | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | Có | FK | `—` | Tenant sở hữu dữ liệu |
| `kind` | `text` | Có | — | `—` | Loại bản ghi |
| `management_unit_id` | `uuid` | Không | FK | `—` | Tham chiếu ban quản lý như một tổ chức |
| `site_id` | `uuid` | Không | FK | `—` | Tham chiếu khu đô thị |
| `zone_id` | `uuid` | Không | FK | `—` | Tham chiếu phân khu |
| `building_id` | `uuid` | Không | FK | `—` | Tham chiếu tòa nhà |
| `created_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm cập nhật |

### Ràng buộc thực tế

- `access_scopes_building_id_fk`: `FOREIGN KEY (tenant_id, building_id) REFERENCES buildings(tenant_id, id) ON DELETE RESTRICT`.
- `access_scopes_check_0`: `CHECK (kind = ANY (ARRAY['tenant'::text, 'management'::text, 'site'::text, 'zone'::text, 'building'::text]))`.
- `access_scopes_management_unit_id_fk`: `FOREIGN KEY (tenant_id, management_unit_id) REFERENCES management_units(tenant_id, id) ON DELETE RESTRICT`.
- `access_scopes_pkey`: `PRIMARY KEY (id)`.
- `access_scopes_site_id_fk`: `FOREIGN KEY (tenant_id, site_id) REFERENCES sites(tenant_id, id) ON DELETE RESTRICT`.
- `access_scopes_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `access_scopes_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `access_scopes_zone_id_fk`: `FOREIGN KEY (tenant_id, zone_id) REFERENCES zones(tenant_id, id) ON DELETE RESTRICT`.

### Chỉ mục

- `CREATE UNIQUE INDEX access_scopes_partial_0 ON public.access_scopes USING btree (tenant_id) WHERE (kind = 'tenant'::text)`.
- `CREATE UNIQUE INDEX access_scopes_partial_1 ON public.access_scopes USING btree (tenant_id, management_unit_id) WHERE (kind = 'management'::text)`.
- `CREATE UNIQUE INDEX access_scopes_partial_2 ON public.access_scopes USING btree (tenant_id, site_id) WHERE (kind = 'site'::text)`.
- `CREATE UNIQUE INDEX access_scopes_partial_3 ON public.access_scopes USING btree (tenant_id, zone_id) WHERE (kind = 'zone'::text)`.
- `CREATE UNIQUE INDEX access_scopes_partial_4 ON public.access_scopes USING btree (tenant_id, building_id) WHERE (kind = 'building'::text)`.
- `CREATE UNIQUE INDEX access_scopes_pkey ON public.access_scopes USING btree (id)`.
- `CREATE UNIQUE INDEX access_scopes_tenant_key_uq ON public.access_scopes USING btree (tenant_id, id)`.

### Trigger và chính sách tenant

- `access_scopes_touch` → `app_touch_updated_at`: `CREATE TRIGGER access_scopes_touch BEFORE UPDATE ON access_scopes FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at()`.

- Policy `access_scopes_tenant_policy` (ALL); USING `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`; WITH CHECK `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`.

## agent_knowledge_grants

Bảng nối agent với kho được cấp; quyền này vẫn giao với quyền cư dân và tài liệu.

Số dòng trong snapshot: **1**. RLS: **bật**; FORCE RLS: **bật**.

| Cột | Kiểu PostgreSQL | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `tenant_id` | `uuid` | Có | PK/FK | `—` | Tenant sở hữu dữ liệu |
| `agent_id` | `text` | Có | PK/FK | `—` | Tham chiếu danh mục agent của platform |
| `knowledge_base_id` | `uuid` | Có | PK/FK | `—` | Tham chiếu bộ sưu tập tri thức |
| `granted_by` | `text` | Có | FK | `—` | Người cấp quyền |
| `created_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm tạo |

### Ràng buộc thực tế

- `agent_knowledge_grants_agent_id_fk`: `FOREIGN KEY (tenant_id, agent_id) REFERENCES agents(tenant_id, id) ON DELETE RESTRICT`.
- `agent_knowledge_grants_granted_by_fk`: `FOREIGN KEY (granted_by) REFERENCES users(id) ON DELETE RESTRICT`.
- `agent_knowledge_grants_knowledge_base_id_fk`: `FOREIGN KEY (tenant_id, knowledge_base_id) REFERENCES knowledge_bases(tenant_id, id) ON DELETE RESTRICT`.
- `agent_knowledge_grants_tenant_id_agent_id_knowledge_base_id_pk`: `PRIMARY KEY (tenant_id, agent_id, knowledge_base_id)`.
- `agent_knowledge_grants_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.

### Chỉ mục

- `CREATE UNIQUE INDEX agent_knowledge_grants_tenant_id_agent_id_knowledge_base_id_pk ON public.agent_knowledge_grants USING btree (tenant_id, agent_id, knowledge_base_id)`.

### Trigger và chính sách tenant

Không có user trigger trong snapshot.

- Policy `agent_knowledge_grants_tenant_policy` (ALL); USING `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`; WITH CHECK `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`.

## agent_runs

Một lượt thực thi agent; nguồn audit và authority cho retrieval.

Số dòng trong snapshot: **0**. RLS: **bật**; FORCE RLS: **bật**.

| Cột | Kiểu PostgreSQL | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | Có | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | Có | FK | `—` | Tenant sở hữu dữ liệu |
| `channel_id` | `text` | Có | FK | `—` | Tham chiếu cửa sổ reception hoặc groupchat quản lý |
| `agent_id` | `text` | Có | FK | `—` | Tham chiếu danh mục agent của platform |
| `version_id` | `uuid` | Có | FK | `—` | Tham chiếu snapshot cấu hình agent bất biến |
| `team_member_id` | `uuid` | Không | FK | `—` | Tham chiếu agent và context riêng của team |
| `actor_user_id` | `text` | Không | FK | `—` | Tham chiếu tài khoản người dùng chung của platform |
| `parent_run_id` | `uuid` | Không | FK | `—` | Tham chiếu theo dõi thực thi xuyên framework |
| `trigger_event_id` | `uuid` | Không | FK | `—` | Tham chiếu lịch sử nghiệp vụ bất biến |
| `idempotency_key` | `text` | Có | — | `—` | Khóa chống xử lý lặp |
| `status` | `text` | Có | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `started_at` | `timestamp with time zone` | Không | — | `—` | Thời điểm bắt đầu |
| `finished_at` | `timestamp with time zone` | Không | — | `—` | Thời điểm kết thúc |
| `error_code` | `text` | Không | — | `—` | Mã lỗi ổn định |
| `input_tokens` | `bigint` | Có | — | `0` | Số token đầu vào |
| `output_tokens` | `bigint` | Có | — | `0` | Số token đầu ra |
| `estimated_cost` | `numeric(18,6)` | Có | — | `'0'::numeric` | Chi phí model ước tính, không phải doanh thu sửa chữa |
| `trace_id` | `text` | Có | — | `—` | ID tracing |
| `created_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm cập nhật |
| `binding_id` | `uuid` | Có | FK | `—` | Tham chiếu runtime_session_bindings |
| `authority_principal_id` | `uuid` | Có | FK | `—` | Tham chiếu execution_principals |
| `on_behalf_of_user_id` | `text` | Không | FK | `—` | Tham chiếu tài khoản người dùng chung của platform |
| `policy_version` | `text` | Có | — | `—` | Phiên bản policy khi chọn dữ liệu |
| `authority_version` | `bigint` | Có | — | `—` | Giá trị authority_version; ý nghĩa và phạm vi theo quy tắc bảng |

### Ràng buộc thực tế

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

### Chỉ mục

- `CREATE UNIQUE INDEX agent_runs_pkey ON public.agent_runs USING btree (id)`.
- `CREATE UNIQUE INDEX agent_runs_tenant_key_uq ON public.agent_runs USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX agent_runs_unique_0 ON public.agent_runs USING btree (tenant_id, idempotency_key)`.

### Trigger và chính sách tenant

- `agent_runs_touch` → `app_touch_updated_at`: `CREATE TRIGGER agent_runs_touch BEFORE UPDATE ON agent_runs FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at()`.

- Policy `agent_runs_tenant_policy` (ALL); USING `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`; WITH CHECK `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`.

## agent_teams

Nhóm agent; có thể là audience/namespace shared team.

Số dòng trong snapshot: **0**. RLS: **bật**; FORCE RLS: **bật**.

| Cột | Kiểu PostgreSQL | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | Có | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | Có | FK | `—` | Tenant sở hữu dữ liệu |
| `workspace_id` | `uuid` | Có | FK | `—` | Workspace của ban quản lý |
| `channel_id` | `text` | Có | FK | `—` | Tham chiếu cửa sổ reception hoặc groupchat quản lý |
| `ticket_id` | `uuid` | Không | FK | `—` | Tham chiếu nguồn chuẩn của yêu cầu cư dân |
| `request_message_id` | `uuid` | Không | FK | `—` | Tham chiếu transcript chính của room |
| `ticket_generation` | `integer` | Có | — | `0` | Lượt xử lý lại tương ứng reopen_count |
| `supervisor_agent_id` | `text` | Có | FK | `—` | Tham chiếu danh mục agent của platform |
| `status` | `text` | Có | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `shared_state` | `jsonb` | Có | — | `—` | Trạng thái phối hợp chung của team |
| `state_version` | `bigint` | Có | — | `0` | Phiên bản CAS của trạng thái |
| `finished_at` | `timestamp with time zone` | Không | — | `—` | Thời điểm kết thúc |
| `created_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm cập nhật |
| `requested_by_user_id` | `text` | Không | FK | `—` | Tham chiếu tài khoản người dùng chung của platform |

### Ràng buộc thực tế

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

### Chỉ mục

- `CREATE UNIQUE INDEX agent_teams_pkey ON public.agent_teams USING btree (id)`.
- `CREATE UNIQUE INDEX agent_teams_tenant_key_uq ON public.agent_teams USING btree (tenant_id, id)`.
- `CREATE INDEX agent_teams_ticket_id_idx ON public.agent_teams USING btree (tenant_id, ticket_id)`.
- `CREATE UNIQUE INDEX agent_teams_unique_0 ON public.agent_teams USING btree (ticket_id, ticket_generation)`.
- `CREATE UNIQUE INDEX agent_teams_unique_1 ON public.agent_teams USING btree (workspace_id, request_message_id)`.
- `CREATE INDEX agent_teams_workspace_id_idx ON public.agent_teams USING btree (tenant_id, workspace_id)`.

### Trigger và chính sách tenant

- `agent_teams_touch` → `app_touch_updated_at`: `CREATE TRIGGER agent_teams_touch BEFORE UPDATE ON agent_teams FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at()`.

- Policy `agent_teams_tenant_policy` (ALL); USING `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`; WITH CHECK `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`.

## agent_versions

Phiên bản agent được chọn cho một binding/run.

Số dòng trong snapshot: **1**. RLS: **bật**; FORCE RLS: **bật**.

| Cột | Kiểu PostgreSQL | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | Có | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | Có | FK | `—` | Tenant sở hữu dữ liệu |
| `agent_id` | `text` | Có | FK | `—` | Tham chiếu danh mục agent của platform |
| `version_no` | `integer` | Có | — | `—` | Số phiên bản tăng dần |
| `runtime` | `text` | Có | — | `—` | Loại runtime thực thi |
| `framework_version` | `text` | Có | — | `—` | Phiên bản framework đã khóa |
| `model_profile_id` | `uuid` | Không | FK | `—` | Tham chiếu cấu hình model dùng chung có kiểm soát |
| `instructions` | `text` | Có | — | `—` | Nội dung chỉ dẫn |
| `config` | `jsonb` | Có | — | `—` | Cấu hình có schema version |
| `config_hash` | `text` | Có | — | `—` | Hash cấu hình |
| `created_by` | `text` | Có | FK | `—` | Tham chiếu tài khoản người dùng chung của platform |
| `created_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm tạo |

### Ràng buộc thực tế

- `agent_versions_agent_id_fk`: `FOREIGN KEY (tenant_id, agent_id) REFERENCES agents(tenant_id, id) ON DELETE RESTRICT`.
- `agent_versions_check_0`: `CHECK (runtime = ANY (ARRAY['langgraph'::text, 'agentscope'::text, 'remote'::text]))`.
- `agent_versions_created_by_fk`: `FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT`.
- `agent_versions_model_profile_id_fk`: `FOREIGN KEY (tenant_id, model_profile_id) REFERENCES model_profiles(tenant_id, id) ON DELETE RESTRICT`.
- `agent_versions_pkey`: `PRIMARY KEY (id)`.
- `agent_versions_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `agent_versions_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `agent_versions_unique_0`: `UNIQUE (agent_id, version_no)`.

### Chỉ mục

- `CREATE UNIQUE INDEX agent_versions_pkey ON public.agent_versions USING btree (id)`.
- `CREATE UNIQUE INDEX agent_versions_tenant_key_uq ON public.agent_versions USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX agent_versions_unique_0 ON public.agent_versions USING btree (agent_id, version_no)`.

### Trigger và chính sách tenant

- `agent_versions_immutable` → `app_append_only`: `CREATE TRIGGER agent_versions_immutable BEFORE DELETE OR UPDATE ON agent_versions FOR EACH ROW EXECUTE FUNCTION app_append_only()`.
- `agent_versions_no_truncate` → `app_append_only`: `CREATE TRIGGER agent_versions_no_truncate BEFORE TRUNCATE ON agent_versions FOR EACH STATEMENT EXECUTE FUNCTION app_append_only()`.

- Policy `agent_versions_tenant_policy` (ALL); USING `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`; WITH CHECK `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`.

## agents

Danh mục agent; agent Lễ tân được cấp knowledge grant.

Số dòng trong snapshot: **4**. RLS: **bật**; FORCE RLS: **bật**.

| Cột | Kiểu PostgreSQL | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `text` | Có | PK | `—` | Định danh bản ghi |
| `name` | `text` | Có | — | `—` | Tên hiển thị |
| `type` | `agent_type` | Có | — | `—` | Giá trị type; ý nghĩa và phạm vi theo quy tắc bảng |
| `configuration` | `jsonb` | Có | — | `—` | Cấu hình agent legacy |
| `package_id` | `uuid` | Không | FK | `—` | Tham chiếu gói triển khai cấu hình tenant |
| `override` | `jsonb` | Không | — | `—` | Cấu hình ghi đè |
| `created_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm cập nhật |
| `tenant_id` | `uuid` | Có | FK | `(NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid` | Tenant sở hữu dữ liệu |
| `workspace_id` | `uuid` | Không | FK | `(NULLIF(current_setting('app.workspace_id'::text, true), ''::text))::uuid` | Workspace của ban quản lý |
| `purpose` | `text` | Có | — | `'specialist'::text` | Vai trò chức năng agent hoặc mục đích file |
| `status` | `text` | Có | — | `'active'::text` | Trạng thái; xem tập giá trị và quy tắc bên dưới |

### Ràng buộc thực tế

- `agents_check_0`: `CHECK (purpose = 'reception'::text AND workspace_id IS NULL OR (purpose = ANY (ARRAY['supervisor'::text, 'specialist'::text])) AND workspace_id IS NOT NULL)`.
- `agents_check_1`: `CHECK (purpose = ANY (ARRAY['reception'::text, 'supervisor'::text, 'specialist'::text]))`.
- `agents_check_2`: `CHECK (status = ANY (ARRAY['draft'::text, 'active'::text, 'archived'::text]))`.
- `agents_package_id_fk`: `FOREIGN KEY (tenant_id, package_id) REFERENCES deployment_packages(tenant_id, id) ON DELETE RESTRICT`.
- `agents_pkey`: `PRIMARY KEY (id)`.
- `agents_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `agents_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `agents_workspace_id_fk`: `FOREIGN KEY (tenant_id, workspace_id) REFERENCES workspaces(tenant_id, id) ON DELETE RESTRICT`.

### Chỉ mục

- `CREATE UNIQUE INDEX agents_partial_0 ON public.agents USING btree (tenant_id) WHERE ((purpose = 'reception'::text) AND (status = 'active'::text))`.
- `CREATE UNIQUE INDEX agents_pkey ON public.agents USING btree (id)`.
- `CREATE UNIQUE INDEX agents_tenant_key_uq ON public.agents USING btree (tenant_id, id)`.
- `CREATE INDEX agents_workspace_id_idx ON public.agents USING btree (tenant_id, workspace_id)`.

### Trigger và chính sách tenant

- `agents_touch` → `app_touch_updated_at`: `CREATE TRIGGER agents_touch BEFORE UPDATE ON agents FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at()`.

- Policy `agents_tenant_policy` (ALL); USING `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`; WITH CHECK `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`.

## buildings

Tòa nhà thuộc site/zone.

Số dòng trong snapshot: **14**. RLS: **bật**; FORCE RLS: **bật**.

| Cột | Kiểu PostgreSQL | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | Có | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | Có | FK | `—` | Tenant sở hữu dữ liệu |
| `site_id` | `uuid` | Có | FK | `—` | Tham chiếu khu đô thị |
| `zone_id` | `uuid` | Không | FK | `—` | Tham chiếu phân khu |
| `code` | `text` | Có | — | `—` | Mã định danh nghiệp vụ |
| `name` | `text` | Có | — | `—` | Tên hiển thị |
| `status` | `text` | Có | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `created_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm cập nhật |

### Ràng buộc thực tế

- `buildings_pkey`: `PRIMARY KEY (id)`.
- `buildings_site_id_fk`: `FOREIGN KEY (tenant_id, site_id) REFERENCES sites(tenant_id, id) ON DELETE RESTRICT`.
- `buildings_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `buildings_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `buildings_unique_0`: `UNIQUE (site_id, code)`.
- `buildings_zone_id_fk`: `FOREIGN KEY (tenant_id, zone_id) REFERENCES zones(tenant_id, id) ON DELETE RESTRICT`.

### Chỉ mục

- `CREATE UNIQUE INDEX buildings_pkey ON public.buildings USING btree (id)`.
- `CREATE UNIQUE INDEX buildings_tenant_key_uq ON public.buildings USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX buildings_unique_0 ON public.buildings USING btree (site_id, code)`.

### Trigger và chính sách tenant

- `buildings_touch` → `app_touch_updated_at`: `CREATE TRIGGER buildings_touch BEFORE UPDATE ON buildings FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at()`.

- Policy `buildings_tenant_policy` (ALL); USING `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`; WITH CHECK `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`.

## channel_memberships

Thành viên của kênh và audience được đọc.

Số dòng trong snapshot: **23**. RLS: **bật**; FORCE RLS: **bật**.

| Cột | Kiểu PostgreSQL | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `channel_id` | `text` | Có | PK/FK | `—` | Tham chiếu cửa sổ reception hoặc groupchat quản lý |
| `user_id` | `text` | Có | PK/FK | `—` | Tài khoản liên quan |
| `pinned_at` | `timestamp with time zone` | Không | — | `—` | Thời điểm ghim |
| `last_read_at` | `timestamp with time zone` | Không | — | `—` | Thời điểm đọc gần nhất |
| `created_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm tạo |
| `tenant_id` | `uuid` | Có | FK | `(NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid` | Tenant sở hữu dữ liệu |
| `last_read_seq` | `bigint` | Có | — | `0` | Số thứ tự tin nhắn đã đọc |

### Ràng buộc thực tế

- `channel_memberships_channel_id_fk`: `FOREIGN KEY (tenant_id, channel_id) REFERENCES channels(tenant_id, id) ON DELETE RESTRICT`.
- `channel_memberships_channel_id_user_id_pk`: `PRIMARY KEY (channel_id, user_id)`.
- `channel_memberships_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `channel_memberships_user_id_fk`: `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT`.

### Chỉ mục

- `CREATE UNIQUE INDEX channel_memberships_channel_id_user_id_pk ON public.channel_memberships USING btree (channel_id, user_id)`.

### Trigger và chính sách tenant

Không có user trigger trong snapshot.

- Policy `channel_memberships_tenant_policy` (ALL); USING `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`; WITH CHECK `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`.

## channels

Kênh trao đổi chứa câu hỏi/câu trả lời.

Số dòng trong snapshot: **23**. RLS: **bật**; FORCE RLS: **bật**.

| Cột | Kiểu PostgreSQL | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `text` | Có | PK | `—` | Định danh bản ghi |
| `name` | `text` | Có | — | `—` | Tên hiển thị |
| `description` | `text` | Có | — | `—` | Mô tả |
| `suggested_prompts` | `text[]` | Có | — | `'{}'::text[]` | Các câu hỏi gợi ý |
| `allowed_groups` | `text[]` | Có | — | `'{}'::text[]` | Nhóm kênh legacy; không thay membership |
| `package_id` | `uuid` | Không | FK | `—` | Tham chiếu gói triển khai cấu hình tenant |
| `override` | `jsonb` | Không | — | `—` | Cấu hình ghi đè |
| `summary` | `text` | Không | — | `—` | Tóm tắt |
| `summary_at` | `timestamp with time zone` | Không | — | `—` | Thời điểm tạo tóm tắt |
| `last_message` | `text` | Không | — | `—` | Bản xem trước tin nhắn gần nhất |
| `last_message_at` | `timestamp with time zone` | Không | — | `—` | Thời điểm tin nhắn gần nhất |
| `last_message_agent_id` | `text` | Không | FK | `—` | Tham chiếu danh mục agent của platform |
| `deleted_at` | `timestamp with time zone` | Không | — | `—` | Thời điểm xóa mềm |
| `created_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm cập nhật |
| `tenant_id` | `uuid` | Có | FK | `(NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid` | Tenant sở hữu dữ liệu |
| `workspace_id` | `uuid` | Không | FK | `(NULLIF(current_setting('app.workspace_id'::text, true), ''::text))::uuid` | Workspace của ban quản lý |
| `kind` | `text` | Có | — | `'management'::text` | Loại bản ghi |
| `created_by` | `text` | Không | FK | `—` | Tham chiếu tài khoản người dùng chung của platform |
| `is_dispatch_default` | `boolean` | Có | — | `false` | Room điều phối mặc định của workspace |
| `next_message_seq` | `bigint` | Có | — | `1` | Bộ đếm cấp thứ tự tin nhắn |

### Ràng buộc thực tế

- `channels_check_0`: `CHECK (kind = 'reception'::text AND workspace_id IS NULL OR (kind = ANY (ARRAY['management'::text, 'agent_builder'::text])) AND workspace_id IS NOT NULL)`.
- `channels_check_1`: `CHECK (kind = ANY (ARRAY['reception'::text, 'management'::text, 'agent_builder'::text]))`.
- `channels_created_by_fk`: `FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT`.
- `channels_last_message_agent_id_fk`: `FOREIGN KEY (tenant_id, last_message_agent_id) REFERENCES agents(tenant_id, id) ON DELETE RESTRICT`.
- `channels_package_id_fk`: `FOREIGN KEY (tenant_id, package_id) REFERENCES deployment_packages(tenant_id, id) ON DELETE RESTRICT`.
- `channels_pkey`: `PRIMARY KEY (id)`.
- `channels_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `channels_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `channels_workspace_id_fk`: `FOREIGN KEY (tenant_id, workspace_id) REFERENCES workspaces(tenant_id, id) ON DELETE RESTRICT`.

### Chỉ mục

- `CREATE UNIQUE INDEX channels_partial_0 ON public.channels USING btree (workspace_id) WHERE (is_dispatch_default AND (deleted_at IS NULL))`.
- `CREATE UNIQUE INDEX channels_pkey ON public.channels USING btree (id)`.
- `CREATE UNIQUE INDEX channels_tenant_key_uq ON public.channels USING btree (tenant_id, id)`.
- `CREATE INDEX channels_workspace_id_idx ON public.channels USING btree (tenant_id, workspace_id)`.

### Trigger và chính sách tenant

- `channels_touch` → `app_touch_updated_at`: `CREATE TRIGGER channels_touch BEFORE UPDATE ON channels FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at()`.

- Policy `channels_tenant_policy` (ALL); USING `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`; WITH CHECK `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`.

## context_snapshots

Context đã chọn của agent run; retrieval_ids là provenance JSON, không phải FK hay quyền truy cập.

Số dòng trong snapshot: **0**. RLS: **bật**; FORCE RLS: **bật**.

| Cột | Kiểu PostgreSQL | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | Có | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | Có | FK | `—` | Tenant sở hữu dữ liệu |
| `run_id` | `uuid` | Có | FK | `—` | Tham chiếu theo dõi thực thi xuyên framework |
| `requested_message_id` | `uuid` | Không | FK | `—` | Tham chiếu transcript chính của room |
| `ticket_id` | `uuid` | Không | FK | `—` | Tham chiếu nguồn chuẩn của yêu cầu cư dân |
| `message_ids` | `jsonb` | Có | — | `—` | Danh sách message đã chọn vào context |
| `task_ids` | `jsonb` | Có | — | `—` | Danh sách task đã chọn vào context |
| `retrieval_ids` | `jsonb` | Có | — | `—` | Danh sách lượt retrieval tham chiếu |
| `policy_version` | `text` | Có | — | `—` | Phiên bản policy khi chọn dữ liệu |
| `token_budget` | `integer` | Có | — | `—` | Giới hạn token context |
| `content_hash` | `text` | Có | — | `—` | Hash nội dung |
| `redacted_context` | `jsonb` | Có | — | `—` | Context thực tế đã lọc quyền và PII |
| `created_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm tạo |

### Ràng buộc thực tế

- `context_snapshots_pkey`: `PRIMARY KEY (id)`.
- `context_snapshots_requested_message_id_fk`: `FOREIGN KEY (tenant_id, requested_message_id) REFERENCES messages(tenant_id, id) ON DELETE RESTRICT`.
- `context_snapshots_run_id_fk`: `FOREIGN KEY (tenant_id, run_id) REFERENCES agent_runs(tenant_id, id) ON DELETE RESTRICT`.
- `context_snapshots_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `context_snapshots_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `context_snapshots_ticket_id_fk`: `FOREIGN KEY (tenant_id, ticket_id) REFERENCES tickets(tenant_id, id) ON DELETE RESTRICT`.
- `context_snapshots_unique_0`: `UNIQUE (run_id)`.

### Chỉ mục

- `CREATE UNIQUE INDEX context_snapshots_pkey ON public.context_snapshots USING btree (id)`.
- `CREATE INDEX context_snapshots_run_id_idx ON public.context_snapshots USING btree (tenant_id, run_id)`.
- `CREATE UNIQUE INDEX context_snapshots_tenant_key_uq ON public.context_snapshots USING btree (tenant_id, id)`.
- `CREATE INDEX context_snapshots_ticket_id_idx ON public.context_snapshots USING btree (tenant_id, ticket_id)`.
- `CREATE UNIQUE INDEX context_snapshots_unique_0 ON public.context_snapshots USING btree (run_id)`.

### Trigger và chính sách tenant

- `context_snapshots_immutable` → `app_append_only`: `CREATE TRIGGER context_snapshots_immutable BEFORE DELETE OR UPDATE ON context_snapshots FOR EACH ROW EXECUTE FUNCTION app_append_only()`.
- `context_snapshots_no_truncate` → `app_append_only`: `CREATE TRIGGER context_snapshots_no_truncate BEFORE TRUNCATE ON context_snapshots FOR EACH STATEMENT EXECUTE FUNCTION app_append_only()`.

- Policy `context_snapshots_tenant_policy` (ALL); USING `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`; WITH CHECK `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`.

## document_acl

Allow/deny riêng cho user, role hoặc workspace.

Số dòng trong snapshot: **0**. RLS: **bật**; FORCE RLS: **bật**.

| Cột | Kiểu PostgreSQL | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | Có | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | Có | FK | `—` | Tenant sở hữu dữ liệu |
| `document_id` | `uuid` | Có | FK | `—` | Tham chiếu định danh tài liệu và chủ quản |
| `principal_kind` | `text` | Có | — | `—` | Loại chủ thể được cấp hoặc từ chối quyền |
| `role_code` | `text` | Không | — | `—` | Mã vai trò nghiệp vụ trong scope |
| `user_id` | `text` | Không | FK | `—` | Tài khoản liên quan |
| `workspace_id` | `uuid` | Không | FK | `—` | Workspace của ban quản lý |
| `effect` | `text` | Có | — | `'allow'::text` | allow hoặc deny đối với ACL; tác động công cụ đối với MCP |
| `created_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm cập nhật |

### Ràng buộc thực tế

- `document_acl_check_0`: `CHECK (principal_kind = ANY (ARRAY['role'::text, 'user'::text, 'workspace'::text]))`.
- `document_acl_check_1`: `CHECK (effect = ANY (ARRAY['allow'::text, 'deny'::text]))`.
- `document_acl_document_id_fk`: `FOREIGN KEY (tenant_id, document_id) REFERENCES knowledge_documents(tenant_id, id) ON DELETE RESTRICT`.
- `document_acl_pkey`: `PRIMARY KEY (id)`.
- `document_acl_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `document_acl_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `document_acl_user_id_fk`: `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT`.
- `document_acl_workspace_id_fk`: `FOREIGN KEY (tenant_id, workspace_id) REFERENCES workspaces(tenant_id, id) ON DELETE RESTRICT`.

### Chỉ mục

- `CREATE UNIQUE INDEX document_acl_pkey ON public.document_acl USING btree (id)`.
- `CREATE UNIQUE INDEX document_acl_tenant_key_uq ON public.document_acl USING btree (tenant_id, id)`.
- `CREATE INDEX document_acl_user_id_idx ON public.document_acl USING btree (tenant_id, user_id)`.
- `CREATE INDEX document_acl_workspace_id_idx ON public.document_acl USING btree (tenant_id, workspace_id)`.

### Trigger và chính sách tenant

- `document_acl_touch` → `app_touch_updated_at`: `CREATE TRIGGER document_acl_touch BEFORE UPDATE ON document_acl FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at()`.

- Policy `document_acl_tenant_policy` (ALL); USING `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`; WITH CHECK `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`.

## document_scopes

Bảng nối tài liệu với địa bàn; applies_to_descendants cho phép áp dụng xuống cấp con.

Số dòng trong snapshot: **127**. RLS: **bật**; FORCE RLS: **bật**.

| Cột | Kiểu PostgreSQL | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `tenant_id` | `uuid` | Có | PK/FK | `—` | Tenant sở hữu dữ liệu |
| `document_id` | `uuid` | Có | PK/FK | `—` | Tham chiếu định danh tài liệu và chủ quản |
| `scope_id` | `uuid` | Có | PK/FK | `—` | Tham chiếu phạm vi quyền có kiểu rõ ràng |
| `applies_to_descendants` | `boolean` | Có | — | `true` | Cho phép tài liệu áp dụng xuống địa bàn con |
| `created_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm tạo |

### Ràng buộc thực tế

- `document_scopes_document_id_fk`: `FOREIGN KEY (tenant_id, document_id) REFERENCES knowledge_documents(tenant_id, id) ON DELETE RESTRICT`.
- `document_scopes_scope_id_fk`: `FOREIGN KEY (tenant_id, scope_id) REFERENCES access_scopes(tenant_id, id) ON DELETE RESTRICT`.
- `document_scopes_tenant_id_document_id_scope_id_pk`: `PRIMARY KEY (tenant_id, document_id, scope_id)`.
- `document_scopes_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.

### Chỉ mục

- `CREATE UNIQUE INDEX document_scopes_tenant_id_document_id_scope_id_pk ON public.document_scopes USING btree (tenant_id, document_id, scope_id)`.

### Trigger và chính sách tenant

Không có user trigger trong snapshot.

- Policy `document_scopes_tenant_policy` (ALL); USING `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`; WITH CHECK `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`.

## document_versions

Nội dung có phiên bản, hash, file nguồn, thời gian hiệu lực và metadata.

Số dòng trong snapshot: **115**. RLS: **bật**; FORCE RLS: **bật**.

| Cột | Kiểu PostgreSQL | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | Có | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | Có | FK | `—` | Tenant sở hữu dữ liệu |
| `document_id` | `uuid` | Có | FK | `—` | Tham chiếu định danh tài liệu và chủ quản |
| `version_no` | `integer` | Có | — | `—` | Số phiên bản tăng dần |
| `file_id` | `uuid` | Có | FK | `—` | Tham chiếu metadata file dùng chung |
| `content_hash` | `text` | Có | — | `—` | Hash nội dung |
| `effective_from` | `timestamp with time zone` | Có | — | `—` | Bắt đầu áp dụng |
| `effective_to` | `timestamp with time zone` | Không | — | `—` | Kết thúc áp dụng |
| `submitted_by` | `text` | Có | FK | `—` | Tham chiếu tài khoản người dùng chung của platform |
| `extraction_config` | `jsonb` | Có | — | `—` | Cấu hình trích xuất |
| `created_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm tạo |

### Ràng buộc thực tế

- `document_versions_document_id_fk`: `FOREIGN KEY (tenant_id, document_id) REFERENCES knowledge_documents(tenant_id, id) ON DELETE RESTRICT`.
- `document_versions_file_id_fk`: `FOREIGN KEY (tenant_id, file_id) REFERENCES files(tenant_id, id) ON DELETE RESTRICT`.
- `document_versions_pkey`: `PRIMARY KEY (id)`.
- `document_versions_submitted_by_fk`: `FOREIGN KEY (submitted_by) REFERENCES users(id) ON DELETE RESTRICT`.
- `document_versions_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `document_versions_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `document_versions_unique_0`: `UNIQUE (document_id, version_no)`.

### Chỉ mục

- `CREATE UNIQUE INDEX document_versions_pkey ON public.document_versions USING btree (id)`.
- `CREATE UNIQUE INDEX document_versions_tenant_key_uq ON public.document_versions USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX document_versions_unique_0 ON public.document_versions USING btree (document_id, version_no)`.

### Trigger và chính sách tenant

Không có user trigger trong snapshot.

- Policy `document_versions_tenant_policy` (ALL); USING `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`; WITH CHECK `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`.

## domains

Miền nghiệp vụ của tenant; knowledge base gắn vào domain.

Số dòng trong snapshot: **1**. RLS: **bật**; FORCE RLS: **bật**.

| Cột | Kiểu PostgreSQL | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | Có | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | Có | FK | `—` | Tenant sở hữu dữ liệu |
| `code` | `text` | Có | — | `—` | Mã định danh nghiệp vụ |
| `name` | `text` | Có | — | `—` | Tên hiển thị |
| `description` | `text` | Không | — | `—` | Mô tả |
| `status` | `text` | Có | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `created_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm cập nhật |

### Ràng buộc thực tế

- `domains_pkey`: `PRIMARY KEY (id)`.
- `domains_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `domains_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `domains_unique_0`: `UNIQUE (tenant_id, code)`.

### Chỉ mục

- `CREATE UNIQUE INDEX domains_pkey ON public.domains USING btree (id)`.
- `CREATE UNIQUE INDEX domains_tenant_key_uq ON public.domains USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX domains_unique_0 ON public.domains USING btree (tenant_id, code)`.

### Trigger và chính sách tenant

- `domains_touch` → `app_touch_updated_at`: `CREATE TRIGGER domains_touch BEFORE UPDATE ON domains FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at()`.

- Policy `domains_tenant_policy` (ALL); USING `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`; WITH CHECK `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`.

## embedding_models

Danh mục không gian vector: provider/model/revision/dimension/metric/active.

Số dòng trong snapshot: **1**. RLS: **tắt**; FORCE RLS: **tắt**.

| Cột | Kiểu PostgreSQL | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | Có | PK | `gen_random_uuid()` | Định danh bản ghi |
| `provider` | `text` | Có | — | `—` | Nhà cung cấp dịch vụ |
| `model_name` | `text` | Có | — | `—` | Tên model |
| `model_revision` | `text` | Có | — | `—` | Phiên bản model embedding |
| `dimension` | `integer` | Có | — | `—` | Số chiều embedding |
| `distance_metric` | `text` | Có | — | `—` | Phép đo khoảng cách |
| `active` | `boolean` | Có | — | `true` | Có đang hoạt động |
| `created_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm cập nhật |

### Ràng buộc thực tế

- `embedding_models_pkey`: `PRIMARY KEY (id)`.
- `embedding_models_unique_0`: `UNIQUE (provider, model_name, model_revision, dimension)`.

### Chỉ mục

- `CREATE UNIQUE INDEX embedding_models_pkey ON public.embedding_models USING btree (id)`.
- `CREATE UNIQUE INDEX embedding_models_unique_0 ON public.embedding_models USING btree (provider, model_name, model_revision, dimension)`.

### Trigger và chính sách tenant

- `embedding_models_touch` → `app_touch_updated_at`: `CREATE TRIGGER embedding_models_touch BEFORE UPDATE ON embedding_models FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at()`.

## execution_principals

Chủ thể thực thi được backend xác minh; có authz_version.

Số dòng trong snapshot: **2**. RLS: **bật**; FORCE RLS: **bật**.

| Cột | Kiểu PostgreSQL | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | Có | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | Có | FK | `—` | Tenant sở hữu dữ liệu |
| `kind` | `text` | Có | — | `—` | Loại bản ghi |
| `user_id` | `text` | Không | FK | `—` | Tài khoản liên quan |
| `workspace_id` | `uuid` | Không | FK | `—` | Workspace của ban quản lý |
| `status` | `text` | Có | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `authz_version` | `bigint` | Có | — | `1` | Bộ đếm thay đổi quyền dùng để vô hiệu cache/capability |
| `created_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm cập nhật |

### Ràng buộc thực tế

- `execution_principals_check_0`: `CHECK (kind = 'user'::text AND user_id IS NOT NULL AND workspace_id IS NULL OR kind = 'workspace_service'::text AND user_id IS NULL AND workspace_id IS NOT NULL)`.
- `execution_principals_check_1`: `CHECK (kind = ANY (ARRAY['user'::text, 'workspace_service'::text]))`.
- `execution_principals_check_2`: `CHECK (status = ANY (ARRAY['active'::text, 'suspended'::text, 'revoked'::text]))`.
- `execution_principals_pkey`: `PRIMARY KEY (id)`.
- `execution_principals_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `execution_principals_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `execution_principals_user_id_fk`: `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT`.
- `execution_principals_workspace_id_fk`: `FOREIGN KEY (tenant_id, workspace_id) REFERENCES workspaces(tenant_id, id) ON DELETE RESTRICT`.

### Chỉ mục

- `CREATE UNIQUE INDEX execution_principals_partial_0 ON public.execution_principals USING btree (tenant_id, user_id) WHERE (kind = 'user'::text)`.
- `CREATE UNIQUE INDEX execution_principals_partial_1 ON public.execution_principals USING btree (tenant_id, workspace_id) WHERE (kind = 'workspace_service'::text)`.
- `CREATE UNIQUE INDEX execution_principals_pkey ON public.execution_principals USING btree (id)`.
- `CREATE UNIQUE INDEX execution_principals_tenant_key_uq ON public.execution_principals USING btree (tenant_id, id)`.
- `CREATE INDEX execution_principals_user_id_idx ON public.execution_principals USING btree (tenant_id, user_id)`.
- `CREATE INDEX execution_principals_workspace_id_idx ON public.execution_principals USING btree (tenant_id, workspace_id)`.

### Trigger và chính sách tenant

- `execution_principals_touch` → `app_touch_updated_at`: `CREATE TRIGGER execution_principals_touch BEFORE UPDATE ON execution_principals FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at()`.

- Policy `execution_principals_tenant_policy` (ALL); USING `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`; WITH CHECK `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`.

## file_access_logs

Nhật ký truy cập file.

Số dòng trong snapshot: **0**. RLS: **bật**; FORCE RLS: **bật**.

| Cột | Kiểu PostgreSQL | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | Có | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | Có | FK | `—` | Tenant sở hữu dữ liệu |
| `file_id` | `uuid` | Có | FK | `—` | Tham chiếu metadata file dùng chung |
| `object_id` | `uuid` | Không | FK | `—` | Tham chiếu file_objects |
| `actor_user_id` | `text` | Không | FK | `—` | Tham chiếu tài khoản người dùng chung của platform |
| `actor_principal_id` | `uuid` | Có | FK | `—` | Tham chiếu execution_principals |
| `run_id` | `uuid` | Không | FK | `—` | Tham chiếu theo dõi thực thi xuyên framework |
| `action` | `text` | Có | — | `—` | Hành động quản trị |
| `decision` | `text` | Có | — | `—` | Quyết định duyệt |
| `purpose` | `text` | Có | — | `—` | Vai trò chức năng agent hoặc mục đích file |
| `request_id` | `text` | Có | — | `—` | Mã tương quan request trong audit |
| `signed_url_expires_at` | `timestamp with time zone` | Không | — | `—` | Thời điểm signed url expires |
| `created_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm tạo |

### Ràng buộc thực tế

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

### Chỉ mục

- `CREATE UNIQUE INDEX file_access_logs_pkey ON public.file_access_logs USING btree (id)`.
- `CREATE INDEX file_access_logs_run_id_idx ON public.file_access_logs USING btree (tenant_id, run_id)`.
- `CREATE UNIQUE INDEX file_access_logs_tenant_key_uq ON public.file_access_logs USING btree (tenant_id, id)`.

### Trigger và chính sách tenant

- `file_access_logs_immutable` → `app_append_only`: `CREATE TRIGGER file_access_logs_immutable BEFORE DELETE OR UPDATE ON file_access_logs FOR EACH ROW EXECUTE FUNCTION app_append_only()`.
- `file_access_logs_no_truncate` → `app_append_only`: `CREATE TRIGGER file_access_logs_no_truncate BEFORE TRUNCATE ON file_access_logs FOR EACH STATEMENT EXECUTE FUNCTION app_append_only()`.

- Policy `file_access_logs_tenant_policy` (ALL); USING `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`; WITH CHECK `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`.

## file_objects

Đối tượng lưu trữ vật lý của một file.

Số dòng trong snapshot: **0**. RLS: **bật**; FORCE RLS: **bật**.

| Cột | Kiểu PostgreSQL | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | Có | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | Có | FK | `—` | Tenant sở hữu dữ liệu |
| `file_id` | `uuid` | Có | FK | `—` | Tham chiếu metadata file dùng chung |
| `location_id` | `uuid` | Có | FK | `—` | Tham chiếu storage_locations |
| `object_key` | `text` | Có | — | `—` | Khóa object, không phải signed URL |
| `version_id` | `text` | Có | — | `—` | Version ID của S3/MinIO, không phải phiên bản agent hoặc document |
| `variant` | `text` | Có | — | `—` | Vai trò của object: gốc, thumbnail, che PII hoặc preview |
| `variant_revision` | `integer` | Có | — | `1` | Phiên bản xử lý của cùng loại biến thể |
| `source_object_id` | `uuid` | Không | FK | `—` | Tham chiếu file_objects |
| `mime_type` | `text` | Có | — | `—` | MIME đã kiểm tra |
| `size_bytes` | `bigint` | Có | — | `—` | Kích thước byte |
| `sha256` | `text` | Có | — | `—` | Hash SHA-256 |
| `etag` | `text` | Không | — | `—` | ETag do provider trả; không mặc định là MD5 |
| `checksum_algorithm` | `text` | Không | — | `—` | Thuật toán checksum provider trả |
| `checksum_value` | `text` | Không | — | `—` | Giá trị checksum provider; không thay full-file SHA256 |
| `checksum_type` | `text` | Không | — | `—` | Checksum toàn file hoặc composite multipart |
| `width_px` | `integer` | Không | — | `—` | Chiều rộng ảnh sau kiểm tra định dạng |
| `height_px` | `integer` | Không | — | `—` | Chiều cao ảnh sau kiểm tra định dạng |
| `scan_status` | `text` | Có | — | `—` | Trạng thái kiểm tra an toàn file |
| `verified_at` | `timestamp with time zone` | Không | — | `—` | Thời điểm xác minh |
| `encryption_mode` | `text` | Có | — | `—` | Chế độ mã hóa phía object store |
| `kms_key_ref` | `text` | Không | — | `—` | Tham chiếu khóa KMS, không chứa vật liệu khóa |
| `object_retain_until` | `timestamp with time zone` | Không | — | `—` | Mốc retention lock quan sát được trên object store |
| `object_legal_hold` | `boolean` | Có | — | `false` | Trạng thái Object Lock legal hold quan sát được |
| `status` | `text` | Có | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `created_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm cập nhật |

### Ràng buộc thực tế

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

### Chỉ mục

- `CREATE UNIQUE INDEX file_objects_pkey ON public.file_objects USING btree (id)`.
- `CREATE UNIQUE INDEX file_objects_tenant_key_uq ON public.file_objects USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX file_objects_unique_0 ON public.file_objects USING btree (location_id, object_key, version_id)`.
- `CREATE UNIQUE INDEX file_objects_unique_1 ON public.file_objects USING btree (file_id, variant, variant_revision)`.

### Trigger và chính sách tenant

- `file_objects_touch` → `app_touch_updated_at`: `CREATE TRIGGER file_objects_touch BEFORE UPDATE ON file_objects FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at()`.
- `object_version_scope` → `app_validate_object`: `CREATE TRIGGER object_version_scope BEFORE INSERT OR UPDATE ON file_objects FOR EACH ROW EXECUTE FUNCTION app_validate_object()`.

- Policy `file_objects_tenant_policy` (ALL); USING `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`; WITH CHECK `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`.

## file_processing_jobs

Job xử lý file ở lớp storage.

Số dòng trong snapshot: **0**. RLS: **bật**; FORCE RLS: **bật**.

| Cột | Kiểu PostgreSQL | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | Có | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | Có | FK | `—` | Tenant sở hữu dữ liệu |
| `file_id` | `uuid` | Có | FK | `—` | Tham chiếu metadata file dùng chung |
| `upload_id` | `uuid` | Không | FK | `—` | Tham chiếu file_uploads |
| `object_id` | `uuid` | Không | FK | `—` | Tham chiếu file_objects |
| `kind` | `text` | Có | — | `—` | Loại bản ghi |
| `dedupe_key` | `text` | Có | — | `—` | Khóa chống thông báo trùng |
| `status` | `text` | Có | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `available_at` | `timestamp with time zone` | Có | — | `—` | Thời điểm có thể xử lý |
| `attempts` | `integer` | Có | — | `0` | Số lần thử |
| `lease_owner` | `text` | Không | — | `—` | Worker giữ lease |
| `lease_until` | `timestamp with time zone` | Không | — | `—` | Thời điểm hết lease |
| `fencing_version` | `bigint` | Có | — | `0` | Thế hệ lease, tăng mỗi lần worker claim |
| `payload` | `jsonb` | Có | — | `—` | Payload có cấu trúc, không chứa secret thô |
| `finished_at` | `timestamp with time zone` | Không | — | `—` | Thời điểm kết thúc |
| `failure_code` | `text` | Không | — | `—` | Mã lỗi đã loại thông tin nhạy cảm |
| `created_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm cập nhật |

### Ràng buộc thực tế

- `file_processing_jobs_check_0`: `CHECK (kind = ANY (ARRAY['verify'::text, 'promote'::text, 'thumbnail'::text, 'redact'::text, 'delete'::text, 'reconcile'::text]))`.
- `file_processing_jobs_check_1`: `CHECK (status = ANY (ARRAY['pending'::text, 'running'::text, 'succeeded'::text, 'failed'::text, 'dead'::text, 'cancelled'::text]))`.
- `file_processing_jobs_file_id_fk`: `FOREIGN KEY (tenant_id, file_id) REFERENCES files(tenant_id, id) ON DELETE RESTRICT`.
- `file_processing_jobs_object_id_fk`: `FOREIGN KEY (tenant_id, object_id) REFERENCES file_objects(tenant_id, id) ON DELETE RESTRICT`.
- `file_processing_jobs_pkey`: `PRIMARY KEY (id)`.
- `file_processing_jobs_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `file_processing_jobs_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `file_processing_jobs_unique_0`: `UNIQUE (tenant_id, dedupe_key)`.
- `file_processing_jobs_upload_id_fk`: `FOREIGN KEY (tenant_id, upload_id) REFERENCES file_uploads(tenant_id, id) ON DELETE RESTRICT`.

### Chỉ mục

- `CREATE UNIQUE INDEX file_processing_jobs_pkey ON public.file_processing_jobs USING btree (id)`.
- `CREATE UNIQUE INDEX file_processing_jobs_tenant_key_uq ON public.file_processing_jobs USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX file_processing_jobs_unique_0 ON public.file_processing_jobs USING btree (tenant_id, dedupe_key)`.

### Trigger và chính sách tenant

- `file_processing_jobs_touch` → `app_touch_updated_at`: `CREATE TRIGGER file_processing_jobs_touch BEFORE UPDATE ON file_processing_jobs FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at()`.

- Policy `file_processing_jobs_tenant_policy` (ALL); USING `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`; WITH CHECK `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`.

## file_upload_parts

Các phần của upload nhiều phần.

Số dòng trong snapshot: **0**. RLS: **bật**; FORCE RLS: **bật**.

| Cột | Kiểu PostgreSQL | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | Có | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | Có | FK | `—` | Tenant sở hữu dữ liệu |
| `upload_id` | `uuid` | Có | FK | `—` | Tham chiếu file_uploads |
| `part_number` | `integer` | Có | — | `—` | Số thứ tự part trong multipart upload |
| `etag` | `text` | Có | — | `—` | ETag do provider trả; không mặc định là MD5 |
| `size_bytes` | `bigint` | Có | — | `—` | Kích thước byte |
| `checksum_value` | `text` | Không | — | `—` | Giá trị checksum provider; không thay full-file SHA256 |
| `created_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm cập nhật |

### Ràng buộc thực tế

- `file_upload_parts_check_0`: `CHECK (part_number >= 1 AND part_number <= 10000)`.
- `file_upload_parts_check_1`: `CHECK (size_bytes > 0)`.
- `file_upload_parts_pkey`: `PRIMARY KEY (id)`.
- `file_upload_parts_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `file_upload_parts_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `file_upload_parts_unique_0`: `UNIQUE (upload_id, part_number)`.
- `file_upload_parts_upload_id_fk`: `FOREIGN KEY (tenant_id, upload_id) REFERENCES file_uploads(tenant_id, id) ON DELETE RESTRICT`.

### Chỉ mục

- `CREATE UNIQUE INDEX file_upload_parts_pkey ON public.file_upload_parts USING btree (id)`.
- `CREATE UNIQUE INDEX file_upload_parts_tenant_key_uq ON public.file_upload_parts USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX file_upload_parts_unique_0 ON public.file_upload_parts USING btree (upload_id, part_number)`.

### Trigger và chính sách tenant

- `file_upload_parts_touch` → `app_touch_updated_at`: `CREATE TRIGGER file_upload_parts_touch BEFORE UPDATE ON file_upload_parts FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at()`.

- Policy `file_upload_parts_tenant_policy` (ALL); USING `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`; WITH CHECK `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`.

## file_uploads

Phiên upload file.

Số dòng trong snapshot: **0**. RLS: **bật**; FORCE RLS: **bật**.

| Cột | Kiểu PostgreSQL | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | Có | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | Có | FK | `—` | Tenant sở hữu dữ liệu |
| `file_id` | `uuid` | Có | FK | `—` | Tham chiếu metadata file dùng chung |
| `requested_by` | `text` | Có | FK | `—` | Tham chiếu tài khoản người dùng chung của platform |
| `location_id` | `uuid` | Có | FK | `—` | Tham chiếu storage_locations |
| `staging_key` | `text` | Có | — | `—` | Khóa upload cách ly do server sinh |
| `source_version_id` | `text` | Không | — | `—` | Version staging được xác minh và dùng làm nguồn copy |
| `upload_mode` | `text` | Có | — | `—` | Upload một request hoặc multipart |
| `multipart_upload_id` | `text` | Không | — | `—` | ID multipart do object store cấp |
| `expected_size_bytes` | `bigint` | Có | — | `—` | Kích thước client khai báo để đối soát |
| `expected_sha256` | `text` | Không | — | `—` | SHA256 client khai báo; verifier vẫn tự tính |
| `allowed_mime_types` | `text[]` | Có | — | `—` | Allowlist MIME do policy server chốt cho upload |
| `max_size_bytes` | `bigint` | Có | — | `—` | Dung lượng tối đa policy cho phép |
| `status` | `text` | Có | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `idempotency_key` | `text` | Có | — | `—` | Khóa chống xử lý lặp |
| `expires_at` | `timestamp with time zone` | Có | — | `—` | Thời điểm hết hạn |
| `finalized_at` | `timestamp with time zone` | Không | — | `—` | Thời điểm finalized |
| `result_object_id` | `uuid` | Không | FK | `—` | Tham chiếu file_objects |
| `failure_code` | `text` | Không | — | `—` | Mã lỗi đã loại thông tin nhạy cảm |
| `created_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm cập nhật |

### Ràng buộc thực tế

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

### Chỉ mục

- `CREATE UNIQUE INDEX file_uploads_partial_0 ON public.file_uploads USING btree (file_id) WHERE (status = ANY (ARRAY['issued'::text, 'uploading'::text, 'uploaded'::text, 'verifying'::text]))`.
- `CREATE UNIQUE INDEX file_uploads_pkey ON public.file_uploads USING btree (id)`.
- `CREATE UNIQUE INDEX file_uploads_tenant_key_uq ON public.file_uploads USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX file_uploads_unique_0 ON public.file_uploads USING btree (tenant_id, requested_by, idempotency_key)`.
- `CREATE UNIQUE INDEX file_uploads_unique_1 ON public.file_uploads USING btree (location_id, staging_key)`.

### Trigger và chính sách tenant

- `file_uploads_touch` → `app_touch_updated_at`: `CREATE TRIGGER file_uploads_touch BEFORE UPDATE ON file_uploads FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at()`.

- Policy `file_uploads_tenant_policy` (ALL); USING `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`; WITH CHECK `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`.

## files

Định danh file; document_versions.file_id bắt buộc tham chiếu ở đây.

Số dòng trong snapshot: **1**. RLS: **bật**; FORCE RLS: **bật**.

| Cột | Kiểu PostgreSQL | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | Có | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | Có | FK | `—` | Tenant sở hữu dữ liệu |
| `uploaded_by` | `text` | Không | FK | `—` | Tham chiếu tài khoản người dùng chung của platform |
| `original_name` | `text` | Có | — | `—` | Tên file gốc |
| `retention_until` | `timestamp with time zone` | Không | — | `—` | Mốc giữ file |
| `deleted_at` | `timestamp with time zone` | Không | — | `—` | Thời điểm xóa mềm |
| `created_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm cập nhật |
| `owner_principal_id` | `uuid` | Có | FK | `—` | Tham chiếu execution_principals |
| `scope_kind` | `text` | Có | — | `—` | Phạm vi sở hữu credential |
| `ticket_id` | `uuid` | Không | FK | `—` | Tham chiếu nguồn chuẩn của yêu cầu cư dân |
| `channel_id` | `text` | Không | FK | `—` | Tham chiếu cửa sổ reception hoặc groupchat quản lý |
| `document_id` | `uuid` | Không | FK | `—` | Tham chiếu định danh tài liệu và chủ quản |
| `report_id` | `uuid` | Không | FK | `—` | Tham chiếu yêu cầu báo cáo docx |
| `status` | `text` | Có | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `accepted_object_id` | `uuid` | Không | FK | `—` | Tham chiếu file_objects |
| `declared_mime_type` | `text` | Không | — | `—` | MIME client khai báo trước khi verifier kiểm tra |
| `legal_hold` | `boolean` | Có | — | `false` | Chặn xóa theo quyết định giữ dữ liệu của ứng dụng |
| `unit_id` | `uuid` | Không | FK | `—` |  |

### Ràng buộc thực tế

- `file_original_scope`: `TRIGGER DEFERRABLE INITIALLY DEFERRED; DEFERRABLE INITIALLY DEFERRED`.
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

### Chỉ mục

- `CREATE UNIQUE INDEX files_pkey ON public.files USING btree (id)`.
- `CREATE UNIQUE INDEX files_tenant_key_uq ON public.files USING btree (tenant_id, id)`.
- `CREATE INDEX files_ticket_id_idx ON public.files USING btree (tenant_id, ticket_id)`.

### Trigger và chính sách tenant

- `file_original_scope` → `app_validate_file`: `CREATE CONSTRAINT TRIGGER file_original_scope AFTER INSERT OR UPDATE ON files DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION app_validate_file()`.
- `files_touch` → `app_touch_updated_at`: `CREATE TRIGGER files_touch BEFORE UPDATE ON files FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at()`.

- Policy `files_tenant_policy` (ALL); USING `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`; WITH CHECK `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`.

## ingestion_jobs

Theo dõi nạp phiên bản bằng một model; chống trùng, trạng thái, lease và số chunks.

Số dòng trong snapshot: **115**. RLS: **bật**; FORCE RLS: **bật**.

| Cột | Kiểu PostgreSQL | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | Có | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | Có | FK | `—` | Tenant sở hữu dữ liệu |
| `version_id` | `uuid` | Có | FK | `—` | Tham chiếu nội dung tài liệu có phiên bản |
| `embedding_model_id` | `uuid` | Có | FK | `—` | Tham chiếu không gian vector có định danh |
| `status` | `text` | Có | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `idempotency_key` | `text` | Có | — | `—` | Khóa chống xử lý lặp |
| `parser_version` | `text` | Có | — | `—` | Phiên bản parser |
| `chunker_version` | `text` | Có | — | `—` | Phiên bản chunker |
| `attempts` | `integer` | Có | — | `0` | Số lần thử |
| `lease_owner` | `text` | Không | — | `—` | Worker giữ lease |
| `lease_until` | `timestamp with time zone` | Không | — | `—` | Thời điểm hết lease |
| `expected_chunks` | `integer` | Không | — | `—` | Số chunk kỳ vọng |
| `completed_chunks` | `integer` | Có | — | `0` | Số chunk đã xử lý |
| `error_code` | `text` | Không | — | `—` | Mã lỗi ổn định |
| `created_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm cập nhật |

### Ràng buộc thực tế

- `ingestion_jobs_check_0`: `CHECK (status = ANY (ARRAY['queued'::text, 'parsing'::text, 'embedding'::text, 'completed'::text, 'failed'::text, 'cancelled'::text]))`.
- `ingestion_jobs_embedding_model_id_fk`: `FOREIGN KEY (embedding_model_id) REFERENCES embedding_models(id) ON DELETE RESTRICT`.
- `ingestion_jobs_pkey`: `PRIMARY KEY (id)`.
- `ingestion_jobs_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `ingestion_jobs_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `ingestion_jobs_unique_0`: `UNIQUE (tenant_id, idempotency_key)`.
- `ingestion_jobs_version_id_fk`: `FOREIGN KEY (tenant_id, version_id) REFERENCES document_versions(tenant_id, id) ON DELETE RESTRICT`.

### Chỉ mục

- `CREATE UNIQUE INDEX ingestion_jobs_pkey ON public.ingestion_jobs USING btree (id)`.
- `CREATE UNIQUE INDEX ingestion_jobs_tenant_key_uq ON public.ingestion_jobs USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX ingestion_jobs_unique_0 ON public.ingestion_jobs USING btree (tenant_id, idempotency_key)`.

### Trigger và chính sách tenant

- `ingestion_jobs_touch` → `app_touch_updated_at`: `CREATE TRIGGER ingestion_jobs_touch BEFORE UPDATE ON ingestion_jobs FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at()`.

- Policy `ingestion_jobs_tenant_policy` (ALL); USING `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`; WITH CHECK `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`.

## knowledge_bases

Kho tri thức theo tenant/domain; chứa nhiều tài liệu.

Số dòng trong snapshot: **2**. RLS: **bật**; FORCE RLS: **bật**.

| Cột | Kiểu PostgreSQL | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | Có | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | Có | FK | `—` | Tenant sở hữu dữ liệu |
| `domain_id` | `uuid` | Có | FK | `—` | Tham chiếu miền nghiệp vụ có thể cấu hình |
| `code` | `text` | Có | — | `—` | Mã định danh nghiệp vụ |
| `name` | `text` | Có | — | `—` | Tên hiển thị |
| `description` | `text` | Không | — | `—` | Mô tả |
| `status` | `text` | Có | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `created_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm cập nhật |

### Ràng buộc thực tế

- `knowledge_bases_check_0`: `CHECK (status = ANY (ARRAY['active'::text, 'archived'::text]))`.
- `knowledge_bases_domain_id_fk`: `FOREIGN KEY (tenant_id, domain_id) REFERENCES domains(tenant_id, id) ON DELETE RESTRICT`.
- `knowledge_bases_pkey`: `PRIMARY KEY (id)`.
- `knowledge_bases_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `knowledge_bases_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `knowledge_bases_unique_0`: `UNIQUE (tenant_id, code)`.

### Chỉ mục

- `CREATE UNIQUE INDEX knowledge_bases_pkey ON public.knowledge_bases USING btree (id)`.
- `CREATE UNIQUE INDEX knowledge_bases_tenant_key_uq ON public.knowledge_bases USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX knowledge_bases_unique_0 ON public.knowledge_bases USING btree (tenant_id, code)`.

### Trigger và chính sách tenant

- `knowledge_bases_touch` → `app_touch_updated_at`: `CREATE TRIGGER knowledge_bases_touch BEFORE UPDATE ON knowledge_bases FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at()`.

- Policy `knowledge_bases_tenant_policy` (ALL); USING `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`; WITH CHECK `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`.

## knowledge_categories

Danh mục tài liệu; parent_id tạo cây danh mục.

Số dòng trong snapshot: **1**. RLS: **bật**; FORCE RLS: **bật**.

| Cột | Kiểu PostgreSQL | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | Có | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | Có | FK | `—` | Tenant sở hữu dữ liệu |
| `code` | `text` | Có | — | `—` | Mã định danh nghiệp vụ |
| `name` | `text` | Có | — | `—` | Tên hiển thị |
| `parent_id` | `uuid` | Không | FK | `—` | Tham chiếu loại tài liệu cho key search |
| `created_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm cập nhật |

### Ràng buộc thực tế

- `knowledge_categories_parent_id_fk`: `FOREIGN KEY (tenant_id, parent_id) REFERENCES knowledge_categories(tenant_id, id) ON DELETE RESTRICT`.
- `knowledge_categories_pkey`: `PRIMARY KEY (id)`.
- `knowledge_categories_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `knowledge_categories_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `knowledge_categories_unique_0`: `UNIQUE (tenant_id, code)`.

### Chỉ mục

- `CREATE UNIQUE INDEX knowledge_categories_pkey ON public.knowledge_categories USING btree (id)`.
- `CREATE UNIQUE INDEX knowledge_categories_tenant_key_uq ON public.knowledge_categories USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX knowledge_categories_unique_0 ON public.knowledge_categories USING btree (tenant_id, code)`.

### Trigger và chính sách tenant

- `knowledge_categories_touch` → `app_touch_updated_at`: `CREATE TRIGGER knowledge_categories_touch BEFORE UPDATE ON knowledge_categories FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at()`.

- Policy `knowledge_categories_tenant_policy` (ALL); USING `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`; WITH CHECK `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`.

## knowledge_chunks

Đoạn văn bản; heading, thứ tự, hash, ước lượng tokens và chỉ mục từ khóa search_tsv.

Số dòng trong snapshot: **279**. RLS: **bật**; FORCE RLS: **bật**.

| Cột | Kiểu PostgreSQL | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | Có | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | Có | FK | `—` | Tenant sở hữu dữ liệu |
| `version_id` | `uuid` | Có | FK | `—` | Tham chiếu nội dung tài liệu có phiên bản |
| `ordinal` | `integer` | Có | — | `—` | Thứ tự |
| `text_content` | `text` | Có | — | `—` | Nội dung đoạn tài liệu |
| `text_hash` | `text` | Có | — | `—` | Hash đoạn văn |
| `token_count` | `integer` | Có | — | `—` | Số token |
| `page_start` | `integer` | Không | — | `—` | Trang bắt đầu |
| `page_end` | `integer` | Không | — | `—` | Trang kết thúc |
| `heading_path` | `text` | Không | — | `—` | Đường dẫn tiêu đề trong nguồn |
| `search_tsv` | `tsvector` | Có | — | `—` | Chỉ mục tìm kiếm từ khóa |
| `created_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm tạo |

### Ràng buộc thực tế

- `knowledge_chunks_pkey`: `PRIMARY KEY (id)`.
- `knowledge_chunks_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `knowledge_chunks_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `knowledge_chunks_unique_0`: `UNIQUE (version_id, ordinal)`.
- `knowledge_chunks_version_id_fk`: `FOREIGN KEY (tenant_id, version_id) REFERENCES document_versions(tenant_id, id) ON DELETE RESTRICT`.

### Chỉ mục

- `CREATE UNIQUE INDEX knowledge_chunks_pkey ON public.knowledge_chunks USING btree (id)`.
- `CREATE INDEX knowledge_chunks_search_idx ON public.knowledge_chunks USING gin (search_tsv)`.
- `CREATE UNIQUE INDEX knowledge_chunks_tenant_key_uq ON public.knowledge_chunks USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX knowledge_chunks_unique_0 ON public.knowledge_chunks USING btree (version_id, ordinal)`.

### Trigger và chính sách tenant

- `knowledge_chunks_immutable` → `app_append_only`: `CREATE TRIGGER knowledge_chunks_immutable BEFORE DELETE OR UPDATE ON knowledge_chunks FOR EACH ROW EXECUTE FUNCTION app_append_only()`.
- `knowledge_chunks_no_truncate` → `app_append_only`: `CREATE TRIGGER knowledge_chunks_no_truncate BEFORE TRUNCATE ON knowledge_chunks FOR EACH STATEMENT EXECUTE FUNCTION app_append_only()`.

- Policy `knowledge_chunks_tenant_policy` (ALL); USING `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`; WITH CHECK `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`.

## knowledge_documents

Định danh tài liệu; trỏ phiên bản đang phục vụ qua active_version_id.

Số dòng trong snapshot: **116**. RLS: **bật**; FORCE RLS: **bật**.

| Cột | Kiểu PostgreSQL | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | Có | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | Có | FK | `—` | Tenant sở hữu dữ liệu |
| `knowledge_base_id` | `uuid` | Có | FK | `—` | Tham chiếu bộ sưu tập tri thức |
| `category_id` | `uuid` | Có | FK | `—` | Tham chiếu loại tài liệu cho key search |
| `code` | `text` | Có | — | `—` | Mã định danh nghiệp vụ |
| `title` | `text` | Có | — | `—` | Tiêu đề |
| `owner_management_id` | `uuid` | Không | FK | `—` | Tham chiếu ban quản lý như một tổ chức |
| `status` | `text` | Có | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `language` | `text` | Có | — | `'vi'::text` | Ngôn ngữ tài liệu |
| `active_version_id` | `uuid` | Không | FK | `—` | Tham chiếu nội dung tài liệu có phiên bản |
| `created_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm cập nhật |
| `memory_namespace_id` | `uuid` | Không | FK | `—` | Tham chiếu memory_namespaces |

### Ràng buộc thực tế

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

### Chỉ mục

- `CREATE UNIQUE INDEX knowledge_documents_pkey ON public.knowledge_documents USING btree (id)`.
- `CREATE UNIQUE INDEX knowledge_documents_tenant_key_uq ON public.knowledge_documents USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX knowledge_documents_unique_0 ON public.knowledge_documents USING btree (knowledge_base_id, code)`.

### Trigger và chính sách tenant

- `knowledge_documents_touch` → `app_touch_updated_at`: `CREATE TRIGGER knowledge_documents_touch BEFORE UPDATE ON knowledge_documents FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at()`.

- Policy `knowledge_documents_tenant_policy` (ALL); USING `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`; WITH CHECK `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`.

## knowledge_embeddings

Vector của một chunk với một model; UNIQUE(chunk_id,model_id).

Số dòng trong snapshot: **279**. RLS: **bật**; FORCE RLS: **bật**.

| Cột | Kiểu PostgreSQL | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | Có | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | Có | FK | `—` | Tenant sở hữu dữ liệu |
| `chunk_id` | `uuid` | Có | FK | `—` | Tham chiếu nội dung đoạn và vị trí trích dẫn |
| `model_id` | `uuid` | Có | FK | `—` | Tham chiếu không gian vector có định danh |
| `embedding` | `vector(1536)` | Có | — | `—` | Vector biểu diễn nội dung |
| `content_hash` | `text` | Có | — | `—` | Hash nội dung |
| `created_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm tạo |

### Ràng buộc thực tế

- `knowledge_embeddings_chunk_id_fk`: `FOREIGN KEY (tenant_id, chunk_id) REFERENCES knowledge_chunks(tenant_id, id) ON DELETE RESTRICT`.
- `knowledge_embeddings_model_id_fk`: `FOREIGN KEY (model_id) REFERENCES embedding_models(id) ON DELETE RESTRICT`.
- `knowledge_embeddings_pkey`: `PRIMARY KEY (id)`.
- `knowledge_embeddings_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `knowledge_embeddings_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `knowledge_embeddings_unique_0`: `UNIQUE (chunk_id, model_id)`.

### Chỉ mục

- `CREATE UNIQUE INDEX knowledge_embeddings_pkey ON public.knowledge_embeddings USING btree (id)`.
- `CREATE UNIQUE INDEX knowledge_embeddings_tenant_key_uq ON public.knowledge_embeddings USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX knowledge_embeddings_unique_0 ON public.knowledge_embeddings USING btree (chunk_id, model_id)`.

### Trigger và chính sách tenant

- `embedding_dimension` → `app_embedding_dimension`: `CREATE TRIGGER embedding_dimension BEFORE INSERT OR UPDATE ON knowledge_embeddings FOR EACH ROW EXECUTE FUNCTION app_embedding_dimension()`.

- Policy `knowledge_embeddings_tenant_policy` (ALL); USING `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`; WITH CHECK `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`.

## knowledge_reviews

Duyệt một phiên bản tài liệu HOẶC một ứng viên memory, không phải cả hai.

Số dòng trong snapshot: **3**. RLS: **bật**; FORCE RLS: **bật**.

| Cột | Kiểu PostgreSQL | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | Có | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | Có | FK | `—` | Tenant sở hữu dữ liệu |
| `document_version_id` | `uuid` | Không | FK | `—` | Tham chiếu nội dung tài liệu có phiên bản |
| `memory_candidate_id` | `uuid` | Không | FK | `—` | Tham chiếu tri thức rút ra cần admin duyệt |
| `decision` | `text` | Có | — | `—` | Quyết định duyệt |
| `reviewer_user_id` | `text` | Có | FK | `—` | Tham chiếu tài khoản người dùng chung của platform |
| `reason` | `text` | Không | — | `—` | Lý do |
| `reviewed_at` | `timestamp with time zone` | Có | — | `—` | Thời điểm duyệt |
| `created_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm tạo |
| `subject_seq` | `bigint` | Có | — | `—` | Số thứ tự quyết định được cấp dưới khóa đối tượng |
| `subject_hash` | `text` | Có | — | `—` | Hash phiên bản nội dung mà quyết định áp dụng |

### Ràng buộc thực tế

- `knowledge_reviews_check_0`: `CHECK (num_nonnulls(document_version_id, memory_candidate_id) = 1)`.
- `knowledge_reviews_check_1`: `CHECK (decision = ANY (ARRAY['approve'::text, 'reject'::text, 'revoke'::text]))`.
- `knowledge_reviews_document_version_id_fk`: `FOREIGN KEY (tenant_id, document_version_id) REFERENCES document_versions(tenant_id, id) ON DELETE RESTRICT`.
- `knowledge_reviews_memory_candidate_id_fk`: `FOREIGN KEY (tenant_id, memory_candidate_id) REFERENCES memory_candidates(tenant_id, id) ON DELETE RESTRICT`.
- `knowledge_reviews_pkey`: `PRIMARY KEY (id)`.
- `knowledge_reviews_reviewer_user_id_fk`: `FOREIGN KEY (reviewer_user_id) REFERENCES users(id) ON DELETE RESTRICT`.
- `knowledge_reviews_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `knowledge_reviews_tenant_key_uq`: `UNIQUE (tenant_id, id)`.

### Chỉ mục

- `CREATE UNIQUE INDEX knowledge_reviews_partial_0 ON public.knowledge_reviews USING btree (document_version_id, subject_seq) WHERE (document_version_id IS NOT NULL)`.
- `CREATE UNIQUE INDEX knowledge_reviews_partial_1 ON public.knowledge_reviews USING btree (memory_candidate_id, subject_seq) WHERE (memory_candidate_id IS NOT NULL)`.
- `CREATE UNIQUE INDEX knowledge_reviews_pkey ON public.knowledge_reviews USING btree (id)`.
- `CREATE UNIQUE INDEX knowledge_reviews_tenant_key_uq ON public.knowledge_reviews USING btree (tenant_id, id)`.

### Trigger và chính sách tenant

Không có user trigger trong snapshot.

- Policy `knowledge_reviews_tenant_policy` (ALL); USING `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`; WITH CHECK `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`.

## management_coverage

Phạm vi địa bàn mà một đơn vị quản lý phụ trách.

Số dòng trong snapshot: **2**. RLS: **bật**; FORCE RLS: **bật**.

| Cột | Kiểu PostgreSQL | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | Có | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | Có | FK | `—` | Tenant sở hữu dữ liệu |
| `management_unit_id` | `uuid` | Có | FK | `—` | Tham chiếu ban quản lý như một tổ chức |
| `scope_id` | `uuid` | Có | FK | `—` | Tham chiếu phạm vi quyền có kiểu rõ ràng |
| `service_category_id` | `uuid` | Có | FK | `—` | Tham chiếu phân loại chuẩn cho routing và báo cáo |
| `valid_from` | `timestamp with time zone` | Có | — | `—` | Bắt đầu hiệu lực |
| `valid_to` | `timestamp with time zone` | Không | — | `—` | Kết thúc hiệu lực; NULL là chưa kết thúc |
| `priority` | `integer` | Có | — | `0` | Mức ưu tiên hoặc trọng số xếp hàng |
| `created_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm cập nhật |

### Ràng buộc thực tế

- `management_coverage_management_unit_id_fk`: `FOREIGN KEY (tenant_id, management_unit_id) REFERENCES management_units(tenant_id, id) ON DELETE RESTRICT`.
- `management_coverage_period_excl`: `EXCLUDE USING gist (scope_id WITH =, service_category_id WITH =, tstzrange(valid_from, valid_to, '[)'::text) WITH &&)`.
- `management_coverage_pkey`: `PRIMARY KEY (id)`.
- `management_coverage_scope_id_fk`: `FOREIGN KEY (tenant_id, scope_id) REFERENCES access_scopes(tenant_id, id) ON DELETE RESTRICT`.
- `management_coverage_service_category_id_fk`: `FOREIGN KEY (tenant_id, service_category_id) REFERENCES service_categories(tenant_id, id) ON DELETE RESTRICT`.
- `management_coverage_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `management_coverage_tenant_key_uq`: `UNIQUE (tenant_id, id)`.

### Chỉ mục

- `CREATE INDEX management_coverage_period_excl ON public.management_coverage USING gist (scope_id, service_category_id, tstzrange(valid_from, valid_to, '[)'::text))`.
- `CREATE UNIQUE INDEX management_coverage_pkey ON public.management_coverage USING btree (id)`.
- `CREATE UNIQUE INDEX management_coverage_tenant_key_uq ON public.management_coverage USING btree (tenant_id, id)`.

### Trigger và chính sách tenant

- `management_coverage_touch` → `app_touch_updated_at`: `CREATE TRIGGER management_coverage_touch BEFORE UPDATE ON management_coverage FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at()`.

- Policy `management_coverage_tenant_policy` (ALL); USING `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`; WITH CHECK `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`.

## management_units

Đơn vị quản lý và chủ quản tài liệu.

Số dòng trong snapshot: **1**. RLS: **bật**; FORCE RLS: **bật**.

| Cột | Kiểu PostgreSQL | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | Có | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | Có | FK | `—` | Tenant sở hữu dữ liệu |
| `code` | `text` | Có | — | `—` | Mã định danh nghiệp vụ |
| `name` | `text` | Có | — | `—` | Tên hiển thị |
| `status` | `text` | Có | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `contact_phone` | `text` | Không | — | `—` | Số liên hệ được chụp tại thời điểm tạo |
| `contact_email` | `text` | Không | — | `—` | Email liên hệ |
| `created_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm cập nhật |

### Ràng buộc thực tế

- `management_units_pkey`: `PRIMARY KEY (id)`.
- `management_units_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `management_units_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `management_units_unique_0`: `UNIQUE (tenant_id, code)`.

### Chỉ mục

- `CREATE UNIQUE INDEX management_units_pkey ON public.management_units USING btree (id)`.
- `CREATE UNIQUE INDEX management_units_tenant_key_uq ON public.management_units USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX management_units_unique_0 ON public.management_units USING btree (tenant_id, code)`.

### Trigger và chính sách tenant

- `management_units_touch` → `app_touch_updated_at`: `CREATE TRIGGER management_units_touch BEFORE UPDATE ON management_units FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at()`.

- Policy `management_units_tenant_policy` (ALL); USING `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`; WITH CHECK `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`.

## memory_candidates

Tri thức đề xuất từ tương tác/nghiệp vụ, có evidence, namespace, phạm vi và trạng thái duyệt.

Số dòng trong snapshot: **4**. RLS: **bật**; FORCE RLS: **bật**.

| Cột | Kiểu PostgreSQL | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | Có | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | Có | FK | `—` | Tenant sở hữu dữ liệu |
| `source_ticket_id` | `uuid` | Không | FK | `—` | Tham chiếu nguồn chuẩn của yêu cầu cư dân |
| `source_run_id` | `uuid` | Không | FK | `—` | Tham chiếu theo dõi thực thi xuyên framework |
| `scope_id` | `uuid` | Có | FK | `—` | Tham chiếu phạm vi quyền có kiểu rõ ràng |
| `proposed_text` | `text` | Có | — | `—` | Tri thức đề xuất để duyệt |
| `evidence` | `jsonb` | Có | — | `—` | Bằng chứng và nguồn tri thức |
| `pii_redacted` | `boolean` | Có | — | `false` | Đã loại thông tin cá nhân |
| `status` | `text` | Có | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `proposed_by_agent_id` | `text` | Không | FK | `—` | Tham chiếu danh mục agent của platform |
| `reason` | `text` | Có | — | `—` | Lý do |
| `created_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm cập nhật |
| `namespace_id` | `uuid` | Có | FK | `—` | Tham chiếu memory_namespaces |
| `source_binding_id` | `uuid` | Không | FK | `—` | Tham chiếu runtime_session_bindings |
| `subject_user_id` | `text` | Không | FK | `—` | Tham chiếu tài khoản người dùng chung của platform |
| `proposal_revision` | `integer` | Có | — | `1` | Số phiên bản nội dung đề xuất trong chuỗi thay thế |
| `proposal_hash` | `text` | Có | — | `—` | Hash nội dung bất biến được đem ra duyệt |
| `supersedes_candidate_id` | `uuid` | Không | FK | `—` | Tham chiếu tri thức rút ra cần admin duyệt |

### Ràng buộc thực tế

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

### Chỉ mục

- `CREATE INDEX memory_candidates_namespace_id_idx ON public.memory_candidates USING btree (tenant_id, namespace_id)`.
- `CREATE UNIQUE INDEX memory_candidates_partial_0 ON public.memory_candidates USING btree (supersedes_candidate_id) WHERE (supersedes_candidate_id IS NOT NULL)`.
- `CREATE UNIQUE INDEX memory_candidates_pkey ON public.memory_candidates USING btree (id)`.
- `CREATE UNIQUE INDEX memory_candidates_tenant_key_uq ON public.memory_candidates USING btree (tenant_id, id)`.

### Trigger và chính sách tenant

- `memory_candidates_touch` → `app_touch_updated_at`: `CREATE TRIGGER memory_candidates_touch BEFORE UPDATE ON memory_candidates FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at()`.

- Policy `memory_candidates_tenant_policy` (ALL); USING `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`; WITH CHECK `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`.

## memory_namespaces

Phân vùng bộ nhớ theo owner và audience; đây không phải bảng embedding.

Số dòng trong snapshot: **1**. RLS: **bật**; FORCE RLS: **bật**.

| Cột | Kiểu PostgreSQL | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | Có | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | Có | FK | `—` | Tenant sở hữu dữ liệu |
| `owner_principal_id` | `uuid` | Có | FK | `—` | Tham chiếu execution_principals |
| `kind` | `text` | Có | — | `—` | Loại bản ghi |
| `workspace_id` | `uuid` | Không | FK | `—` | Workspace của ban quản lý |
| `team_id` | `uuid` | Không | FK | `—` | Tham chiếu một phiên cộng tác |
| `namespace_key` | `text` | Có | — | `—` | Khóa namespace nghiệp vụ do server cấp |
| `purpose` | `text` | Có | — | `—` | Vai trò chức năng agent hoặc mục đích file |
| `status` | `text` | Có | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `retention_days` | `integer` | Không | — | `—` | Số ngày giữ memory trước quy trình thu hồi/xóa |
| `authz_version` | `bigint` | Có | — | `1` | Bộ đếm thay đổi quyền dùng để vô hiệu cache/capability |
| `created_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm cập nhật |

### Ràng buộc thực tế

- `memory_namespaces_check_0`: `CHECK (kind = 'personal'::text AND workspace_id IS NULL AND team_id IS NULL OR kind = 'workspace'::text AND workspace_id IS NOT NULL AND team_id IS NULL OR kind = 'team'::text AND workspace_id IS NOT NULL AND team_id IS NOT NULL)`.
- `memory_namespaces_check_1`: `CHECK (kind = ANY (ARRAY['personal'::text, 'team'::text, 'workspace'::text]))`.
- `memory_namespaces_check_2`: `CHECK (status = ANY (ARRAY['active'::text, 'revoked'::text, 'purging'::text, 'purged'::text]))`.
- `memory_namespaces_owner_principal_id_fk`: `FOREIGN KEY (tenant_id, owner_principal_id) REFERENCES execution_principals(tenant_id, id) ON DELETE RESTRICT`.
- `memory_namespaces_pkey`: `PRIMARY KEY (id)`.
- `memory_namespaces_team_id_fk`: `FOREIGN KEY (tenant_id, team_id) REFERENCES agent_teams(tenant_id, id) ON DELETE RESTRICT`.
- `memory_namespaces_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `memory_namespaces_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `memory_namespaces_workspace_id_fk`: `FOREIGN KEY (tenant_id, workspace_id) REFERENCES workspaces(tenant_id, id) ON DELETE RESTRICT`.

### Chỉ mục

- `CREATE UNIQUE INDEX memory_namespaces_partial_0 ON public.memory_namespaces USING btree (owner_principal_id, kind, purpose) WHERE (kind = 'personal'::text)`.
- `CREATE UNIQUE INDEX memory_namespaces_partial_1 ON public.memory_namespaces USING btree (team_id, purpose) WHERE (kind = 'team'::text)`.
- `CREATE UNIQUE INDEX memory_namespaces_partial_2 ON public.memory_namespaces USING btree (workspace_id, purpose) WHERE (kind = 'workspace'::text)`.
- `CREATE UNIQUE INDEX memory_namespaces_pkey ON public.memory_namespaces USING btree (id)`.
- `CREATE UNIQUE INDEX memory_namespaces_tenant_key_uq ON public.memory_namespaces USING btree (tenant_id, id)`.
- `CREATE INDEX memory_namespaces_workspace_id_idx ON public.memory_namespaces USING btree (tenant_id, workspace_id)`.

### Trigger và chính sách tenant

- `memory_namespace_scope` → `app_validate_memory_namespace`: `CREATE TRIGGER memory_namespace_scope BEFORE INSERT OR UPDATE ON memory_namespaces FOR EACH ROW EXECUTE FUNCTION app_validate_memory_namespace()`.
- `memory_namespaces_touch` → `app_touch_updated_at`: `CREATE TRIGGER memory_namespaces_touch BEFORE UPDATE ON memory_namespaces FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at()`.

- Policy `memory_namespaces_tenant_policy` (ALL); USING `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`; WITH CHECK `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`.

## memory_publications

Liên kết ứng viên đã duyệt với tài liệu/phiên bản xuất bản theo cơ chế memory chuẩn.

Số dòng trong snapshot: **0**. RLS: **bật**; FORCE RLS: **bật**.

| Cột | Kiểu PostgreSQL | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | Có | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | Có | FK | `—` | Tenant sở hữu dữ liệu |
| `candidate_id` | `uuid` | Có | FK | `—` | Tham chiếu tri thức rút ra cần admin duyệt |
| `approval_review_id` | `uuid` | Có | FK | `—` | Tham chiếu duyệt tài liệu và tri thức học được |
| `document_id` | `uuid` | Có | FK | `—` | Tham chiếu định danh tài liệu và chủ quản |
| `version_id` | `uuid` | Có | FK | `—` | Tham chiếu nội dung tài liệu có phiên bản |
| `published_at` | `timestamp with time zone` | Có | — | `—` | Thời điểm công bố |
| `revoked_at` | `timestamp with time zone` | Không | — | `—` | Thời điểm thu hồi |
| `created_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm cập nhật |
| `namespace_id` | `uuid` | Có | FK | `—` | Tham chiếu memory_namespaces |

### Ràng buộc thực tế

- `memory_publications_approval_review_id_fk`: `FOREIGN KEY (tenant_id, approval_review_id) REFERENCES knowledge_reviews(tenant_id, id) ON DELETE RESTRICT`.
- `memory_publications_candidate_id_fk`: `FOREIGN KEY (tenant_id, candidate_id) REFERENCES memory_candidates(tenant_id, id) ON DELETE RESTRICT`.
- `memory_publications_document_id_fk`: `FOREIGN KEY (tenant_id, document_id) REFERENCES knowledge_documents(tenant_id, id) ON DELETE RESTRICT`.
- `memory_publications_namespace_id_fk`: `FOREIGN KEY (tenant_id, namespace_id) REFERENCES memory_namespaces(tenant_id, id) ON DELETE RESTRICT`.
- `memory_publications_pkey`: `PRIMARY KEY (id)`.
- `memory_publications_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `memory_publications_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `memory_publications_unique_0`: `UNIQUE (candidate_id)`.
- `memory_publications_version_id_fk`: `FOREIGN KEY (tenant_id, version_id) REFERENCES document_versions(tenant_id, id) ON DELETE RESTRICT`.

### Chỉ mục

- `CREATE INDEX memory_publications_namespace_id_idx ON public.memory_publications USING btree (tenant_id, namespace_id)`.
- `CREATE UNIQUE INDEX memory_publications_pkey ON public.memory_publications USING btree (id)`.
- `CREATE UNIQUE INDEX memory_publications_tenant_key_uq ON public.memory_publications USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX memory_publications_unique_0 ON public.memory_publications USING btree (candidate_id)`.

### Trigger và chính sách tenant

- `memory_publications_touch` → `app_touch_updated_at`: `CREATE TRIGGER memory_publications_touch BEFORE UPDATE ON memory_publications FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at()`.

- Policy `memory_publications_tenant_policy` (ALL); USING `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`; WITH CHECK `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`.

## messages

Nội dung trao đổi; câu hỏi và câu trả lời trong luồng Reception.

Số dòng trong snapshot: **0**. RLS: **bật**; FORCE RLS: **bật**.

| Cột | Kiểu PostgreSQL | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | Có | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | Có | FK | `—` | Tenant sở hữu dữ liệu |
| `channel_id` | `text` | Có | FK | `—` | Tham chiếu cửa sổ reception hoặc groupchat quản lý |
| `seq` | `bigint` | Có | — | `—` | Số thứ tự trong ticket hoặc channel |
| `sender_kind` | `text` | Có | — | `—` | Loại người gửi |
| `sender_user_id` | `text` | Không | FK | `—` | Tham chiếu tài khoản người dùng chung của platform |
| `sender_agent_id` | `text` | Không | FK | `—` | Tham chiếu danh mục agent của platform |
| `run_id` | `uuid` | Không | FK | `—` | Tham chiếu theo dõi thực thi xuyên framework |
| `reply_to_id` | `uuid` | Không | FK | `—` | Tham chiếu transcript chính của room |
| `visibility` | `text` | Có | — | `—` | Phạm vi hiển thị |
| `body` | `jsonb` | Có | — | `—` | Nội dung message có cấu trúc |
| `client_message_id` | `text` | Không | — | `—` | Khóa chống gửi tin nhắn lặp từ client |
| `source_event_id` | `uuid` | Không | FK | `—` | Tham chiếu lịch sử nghiệp vụ bất biến |
| `created_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm tạo |

### Ràng buộc thực tế

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

### Chỉ mục

- `CREATE UNIQUE INDEX messages_pkey ON public.messages USING btree (id)`.
- `CREATE INDEX messages_run_id_idx ON public.messages USING btree (tenant_id, run_id)`.
- `CREATE UNIQUE INDEX messages_tenant_key_uq ON public.messages USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX messages_unique_0 ON public.messages USING btree (channel_id, seq)`.
- `CREATE UNIQUE INDEX messages_unique_1 ON public.messages USING btree (channel_id, sender_user_id, client_message_id)`.
- `CREATE UNIQUE INDEX messages_unique_2 ON public.messages USING btree (channel_id, source_event_id, sender_agent_id)`.

### Trigger và chính sách tenant

Không có user trigger trong snapshot.

- Policy `messages_tenant_policy` (ALL); USING `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`; WITH CHECK `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`.

## reception_sessions

Trạng thái phiên Reception; không phải kho vector.

Số dòng trong snapshot: **0**. RLS: **bật**; FORCE RLS: **bật**.

| Cột | Kiểu PostgreSQL | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | Có | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | Có | FK | `—` | Tenant sở hữu dữ liệu |
| `channel_id` | `text` | Có | FK | `—` | Tham chiếu cửa sổ reception hoặc groupchat quản lý |
| `customer_user_id` | `text` | Có | FK | `—` | Tham chiếu tài khoản người dùng chung của platform |
| `system_agent_id` | `text` | Có | FK | `—` | Tham chiếu danh mục agent của platform |
| `workflow_version` | `text` | Có | — | `—` | Phiên bản graph/workflow |
| `status` | `text` | Có | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `last_event_seq` | `bigint` | Có | — | `0` | Event cuối đã được ghi hoặc xử lý theo phạm vi bảng |
| `created_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm cập nhật |
| `binding_id` | `uuid` | Có | FK | `—` | Tham chiếu runtime_session_bindings |

### Ràng buộc thực tế

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

### Chỉ mục

- `CREATE UNIQUE INDEX reception_sessions_pkey ON public.reception_sessions USING btree (id)`.
- `CREATE UNIQUE INDEX reception_sessions_tenant_key_uq ON public.reception_sessions USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX reception_sessions_unique_0 ON public.reception_sessions USING btree (channel_id)`.
- `CREATE UNIQUE INDEX reception_sessions_unique_1 ON public.reception_sessions USING btree (binding_id)`.

### Trigger và chính sách tenant

- `reception_sessions_touch` → `app_touch_updated_at`: `CREATE TRIGGER reception_sessions_touch BEFORE UPDATE ON reception_sessions FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at()`.

- Policy `reception_sessions_tenant_policy` (ALL); USING `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`; WITH CHECK `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`.

## report_sources

Dataset báo cáo: query_template allowlist, parameters, watermark, row_count, result_hash và file snapshot; không có FK trực tiếp tới document/version/chunk.

Số dòng trong snapshot: **0**. RLS: **bật**; FORCE RLS: **bật**.

| Cột | Kiểu PostgreSQL | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | Có | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | Có | FK | `—` | Tenant sở hữu dữ liệu |
| `report_id` | `uuid` | Có | FK | `—` | Tham chiếu yêu cầu báo cáo docx |
| `dataset` | `text` | Có | — | `—` | Tên tập dữ liệu |
| `query_template` | `text` | Có | — | `—` | ID truy vấn allowlist, không phải SQL tùy ý |
| `parameters` | `jsonb` | Có | — | `—` | Tham số cấu hình |
| `source_watermark` | `timestamp with time zone` | Có | — | `—` | Mốc dữ liệu nguồn |
| `row_count` | `bigint` | Có | — | `—` | Số dòng dữ liệu |
| `result_hash` | `text` | Có | — | `—` | Hash kết quả |
| `snapshot_file_id` | `uuid` | Không | FK | `—` | Tham chiếu metadata file dùng chung |
| `created_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm tạo |

### Ràng buộc thực tế

- `report_sources_pkey`: `PRIMARY KEY (id)`.
- `report_sources_report_id_fk`: `FOREIGN KEY (tenant_id, report_id) REFERENCES report_requests(tenant_id, id) ON DELETE RESTRICT`.
- `report_sources_snapshot_file_id_fk`: `FOREIGN KEY (tenant_id, snapshot_file_id) REFERENCES files(tenant_id, id) ON DELETE RESTRICT`.
- `report_sources_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `report_sources_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `report_sources_unique_0`: `UNIQUE (report_id, dataset)`.

### Chỉ mục

- `CREATE UNIQUE INDEX report_sources_pkey ON public.report_sources USING btree (id)`.
- `CREATE UNIQUE INDEX report_sources_tenant_key_uq ON public.report_sources USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX report_sources_unique_0 ON public.report_sources USING btree (report_id, dataset)`.

### Trigger và chính sách tenant

Không có user trigger trong snapshot.

- Policy `report_sources_tenant_policy` (ALL); USING `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`; WITH CHECK `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`.

## retrieval_hits

Các chunk được xếp hạng trong một retrieval run; lưu similarity và included.

Số dòng trong snapshot: **0**. RLS: **bật**; FORCE RLS: **bật**.

| Cột | Kiểu PostgreSQL | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `tenant_id` | `uuid` | Có | PK/FK | `—` | Tenant sở hữu dữ liệu |
| `retrieval_run_id` | `uuid` | Có | PK/FK | `—` | Tham chiếu truy vết một lần rag |
| `chunk_id` | `uuid` | Có | PK/FK | `—` | Tham chiếu nội dung đoạn và vị trí trích dẫn |
| `rank` | `integer` | Có | — | `—` | Thứ hạng retrieval |
| `similarity` | `numeric(9,6)` | Có | — | `—` | Điểm tương đồng |
| `included` | `boolean` | Có | — | `—` | Có được đưa vào context |
| `created_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm tạo |

### Ràng buộc thực tế

- `retrieval_hits_chunk_id_fk`: `FOREIGN KEY (tenant_id, chunk_id) REFERENCES knowledge_chunks(tenant_id, id) ON DELETE RESTRICT`.
- `retrieval_hits_retrieval_run_id_fk`: `FOREIGN KEY (tenant_id, retrieval_run_id) REFERENCES retrieval_runs(tenant_id, id) ON DELETE RESTRICT`.
- `retrieval_hits_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `retrieval_hits_tenant_id_retrieval_run_id_chunk_id_pk`: `PRIMARY KEY (tenant_id, retrieval_run_id, chunk_id)`.
- `retrieval_hits_unique_0`: `UNIQUE (retrieval_run_id, rank)`.

### Chỉ mục

- `CREATE UNIQUE INDEX retrieval_hits_tenant_id_retrieval_run_id_chunk_id_pk ON public.retrieval_hits USING btree (tenant_id, retrieval_run_id, chunk_id)`.
- `CREATE UNIQUE INDEX retrieval_hits_unique_0 ON public.retrieval_hits USING btree (retrieval_run_id, rank)`.

### Trigger và chính sách tenant

Không có user trigger trong snapshot.

- Policy `retrieval_hits_tenant_policy` (ALL); USING `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`; WITH CHECK `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`.

## retrieval_runs

Nhật ký một lần tra cứu: người, principal, binding, agent run, query, quyền và độ trễ.

Số dòng trong snapshot: **0**. RLS: **bật**; FORCE RLS: **bật**.

| Cột | Kiểu PostgreSQL | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | Có | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | Có | FK | `—` | Tenant sở hữu dữ liệu |
| `agent_run_id` | `uuid` | Có | FK | `—` | Tham chiếu theo dõi thực thi xuyên framework |
| `actor_user_id` | `text` | Không | FK | `—` | Tham chiếu tài khoản người dùng chung của platform |
| `knowledge_base_id` | `uuid` | Có | FK | `—` | Tham chiếu bộ sưu tập tri thức |
| `model_id` | `uuid` | Có | FK | `—` | Tham chiếu không gian vector có định danh |
| `query_text_redacted` | `text` | Có | — | `—` | Câu truy vấn đã loại PII |
| `metadata_filter` | `jsonb` | Có | — | `—` | Bộ lọc metadata đã xác thực |
| `authorized_document_ids` | `jsonb` | Có | — | `—` | Tập tài liệu được phép truy hồi |
| `top_k` | `integer` | Có | — | `—` | Số kết quả tối đa |
| `policy_version` | `text` | Có | — | `—` | Phiên bản policy khi chọn dữ liệu |
| `latency_ms` | `integer` | Có | — | `—` | Độ trễ mili giây |
| `created_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm tạo |
| `principal_id` | `uuid` | Có | FK | `—` | Tham chiếu execution_principals |
| `binding_id` | `uuid` | Có | FK | `—` | Tham chiếu runtime_session_bindings |

### Ràng buộc thực tế

- `retrieval_runs_actor_user_id_fk`: `FOREIGN KEY (actor_user_id) REFERENCES users(id) ON DELETE RESTRICT`.
- `retrieval_runs_agent_run_id_fk`: `FOREIGN KEY (tenant_id, agent_run_id) REFERENCES agent_runs(tenant_id, id) ON DELETE RESTRICT`.
- `retrieval_runs_binding_id_fk`: `FOREIGN KEY (tenant_id, binding_id) REFERENCES runtime_session_bindings(tenant_id, id) ON DELETE RESTRICT`.
- `retrieval_runs_knowledge_base_id_fk`: `FOREIGN KEY (tenant_id, knowledge_base_id) REFERENCES knowledge_bases(tenant_id, id) ON DELETE RESTRICT`.
- `retrieval_runs_model_id_fk`: `FOREIGN KEY (model_id) REFERENCES embedding_models(id) ON DELETE RESTRICT`.
- `retrieval_runs_pkey`: `PRIMARY KEY (id)`.
- `retrieval_runs_principal_id_fk`: `FOREIGN KEY (tenant_id, principal_id) REFERENCES execution_principals(tenant_id, id) ON DELETE RESTRICT`.
- `retrieval_runs_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `retrieval_runs_tenant_key_uq`: `UNIQUE (tenant_id, id)`.

### Chỉ mục

- `CREATE UNIQUE INDEX retrieval_runs_pkey ON public.retrieval_runs USING btree (id)`.
- `CREATE UNIQUE INDEX retrieval_runs_tenant_key_uq ON public.retrieval_runs USING btree (tenant_id, id)`.

### Trigger và chính sách tenant

Không có user trigger trong snapshot.

- Policy `retrieval_runs_tenant_policy` (ALL); USING `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`; WITH CHECK `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`.

## run_memory_access

Ghi quyền đọc/ghi namespace của một agent run tại một authz_version.

Số dòng trong snapshot: **0**. RLS: **bật**; FORCE RLS: **bật**.

| Cột | Kiểu PostgreSQL | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | Có | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | Có | FK | `—` | Tenant sở hữu dữ liệu |
| `run_id` | `uuid` | Có | FK | `—` | Tham chiếu theo dõi thực thi xuyên framework |
| `namespace_id` | `uuid` | Có | FK | `—` | Tham chiếu memory_namespaces |
| `access_mode` | `text` | Có | — | `—` | Quyền đọc hoặc đề xuất memory cho run |
| `authz_version` | `bigint` | Có | — | `—` | Bộ đếm thay đổi quyền dùng để vô hiệu cache/capability |
| `policy_version` | `text` | Có | — | `—` | Phiên bản policy khi chọn dữ liệu |
| `created_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm tạo |

### Ràng buộc thực tế

- `run_memory_access_check_0`: `CHECK (access_mode = ANY (ARRAY['read'::text, 'propose'::text]))`.
- `run_memory_access_namespace_id_fk`: `FOREIGN KEY (tenant_id, namespace_id) REFERENCES memory_namespaces(tenant_id, id) ON DELETE RESTRICT`.
- `run_memory_access_pkey`: `PRIMARY KEY (id)`.
- `run_memory_access_run_id_fk`: `FOREIGN KEY (tenant_id, run_id) REFERENCES agent_runs(tenant_id, id) ON DELETE RESTRICT`.
- `run_memory_access_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `run_memory_access_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `run_memory_access_unique_0`: `UNIQUE (run_id, namespace_id, access_mode)`.

### Chỉ mục

- `CREATE INDEX run_memory_access_namespace_id_idx ON public.run_memory_access USING btree (tenant_id, namespace_id)`.
- `CREATE UNIQUE INDEX run_memory_access_pkey ON public.run_memory_access USING btree (id)`.
- `CREATE INDEX run_memory_access_run_id_idx ON public.run_memory_access USING btree (tenant_id, run_id)`.
- `CREATE UNIQUE INDEX run_memory_access_tenant_key_uq ON public.run_memory_access USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX run_memory_access_unique_0 ON public.run_memory_access USING btree (run_id, namespace_id, access_mode)`.

### Trigger và chính sách tenant

Không có user trigger trong snapshot.

- Policy `run_memory_access_tenant_policy` (ALL); USING `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`; WITH CHECK `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`.

## runtime_backends

Danh mục runtime backend có bật/tắt.

Số dòng trong snapshot: **1**. RLS: **tắt**; FORCE RLS: **tắt**.

| Cột | Kiểu PostgreSQL | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | Có | PK | `gen_random_uuid()` | Định danh bản ghi |
| `code` | `text` | Có | — | `—` | Mã định danh nghiệp vụ |
| `framework` | `text` | Có | — | `—` | Framework quản lý trạng thái thực thi |
| `sdk_language` | `text` | Có | — | `—` | Ngôn ngữ SDK được triển khai |
| `package_version` | `text` | Có | — | `—` | Phiên bản package đã khóa trong deployment |
| `backend_kind` | `text` | Có | — | `—` | Loại cơ chế persistence |
| `connection_secret_ref` | `text` | Có | — | `—` | Tham chiếu secret kết nối, không lưu DSN thô |
| `schema_name` | `text` | Có | — | `—` | Schema vật lý dành riêng cho backend |
| `enabled` | `boolean` | Có | — | `true` | Có được bật hay không |
| `created_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm cập nhật |

### Ràng buộc thực tế

- `runtime_backends_check_0`: `CHECK (framework = ANY (ARRAY['langgraph'::text, 'agentscope'::text]))`.
- `runtime_backends_check_1`: `CHECK (sdk_language = ANY (ARRAY['python'::text, 'javascript'::text, 'java'::text]))`.
- `runtime_backends_check_2`: `CHECK (backend_kind = ANY (ARRAY['postgres'::text, 'sqlalchemy'::text, 'custom'::text]))`.
- `runtime_backends_pkey`: `PRIMARY KEY (id)`.
- `runtime_backends_unique_0`: `UNIQUE (code)`.

### Chỉ mục

- `CREATE UNIQUE INDEX runtime_backends_pkey ON public.runtime_backends USING btree (id)`.
- `CREATE UNIQUE INDEX runtime_backends_unique_0 ON public.runtime_backends USING btree (code)`.

### Trigger và chính sách tenant

- `runtime_backends_touch` → `app_touch_updated_at`: `CREATE TRIGGER runtime_backends_touch BEFORE UPDATE ON runtime_backends FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at()`.

## runtime_identities

Ánh xạ execution principal sang định danh runtime.

Số dòng trong snapshot: **0**. RLS: **bật**; FORCE RLS: **bật**.

| Cột | Kiểu PostgreSQL | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | Có | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | Có | FK | `—` | Tenant sở hữu dữ liệu |
| `backend_id` | `uuid` | Có | FK | `—` | Tham chiếu runtime_backends |
| `principal_id` | `uuid` | Có | FK | `—` | Tham chiếu execution_principals |
| `runtime_user_key` | `text` | Có | — | `—` | User key opaque được adapter truyền cho framework |
| `status` | `text` | Có | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `created_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm cập nhật |

### Ràng buộc thực tế

- `runtime_identities_backend_id_fk`: `FOREIGN KEY (backend_id) REFERENCES runtime_backends(id) ON DELETE RESTRICT`.
- `runtime_identities_check_0`: `CHECK (status = ANY (ARRAY['active'::text, 'revoked'::text]))`.
- `runtime_identities_pkey`: `PRIMARY KEY (id)`.
- `runtime_identities_principal_id_fk`: `FOREIGN KEY (tenant_id, principal_id) REFERENCES execution_principals(tenant_id, id) ON DELETE RESTRICT`.
- `runtime_identities_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `runtime_identities_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `runtime_identities_unique_0`: `UNIQUE (backend_id, principal_id)`.
- `runtime_identities_unique_1`: `UNIQUE (backend_id, runtime_user_key)`.
- `runtime_identities_unique_2`: `UNIQUE (tenant_id, id, backend_id)`.

### Chỉ mục

- `CREATE UNIQUE INDEX runtime_identities_pkey ON public.runtime_identities USING btree (id)`.
- `CREATE UNIQUE INDEX runtime_identities_tenant_key_uq ON public.runtime_identities USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX runtime_identities_unique_0 ON public.runtime_identities USING btree (backend_id, principal_id)`.
- `CREATE UNIQUE INDEX runtime_identities_unique_1 ON public.runtime_identities USING btree (backend_id, runtime_user_key)`.
- `CREATE UNIQUE INDEX runtime_identities_unique_2 ON public.runtime_identities USING btree (tenant_id, id, backend_id)`.

### Trigger và chính sách tenant

Không có user trigger trong snapshot.

- Policy `runtime_identities_tenant_policy` (ALL); USING `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`; WITH CHECK `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`.

## runtime_memory_bindings

Ánh xạ namespace bộ nhớ của platform sang backend runtime.

Số dòng trong snapshot: **0**. RLS: **bật**; FORCE RLS: **bật**.

| Cột | Kiểu PostgreSQL | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | Có | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | Có | FK | `—` | Tenant sở hữu dữ liệu |
| `namespace_id` | `uuid` | Có | FK | `—` | Tham chiếu memory_namespaces |
| `backend_id` | `uuid` | Có | FK | `—` | Tham chiếu runtime_backends |
| `runtime_namespace` | `jsonb` | Có | — | `—` | Mảng thành phần namespace đúng định dạng adapter |
| `status` | `text` | Có | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `sync_generation` | `bigint` | Có | — | `1` | Thế hệ đồng bộ chống ghi lại memory đã thu hồi |
| `last_synced_at` | `timestamp with time zone` | Không | — | `—` | Thời điểm last synced |
| `created_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm cập nhật |

### Ràng buộc thực tế

- `runtime_memory_bindings_backend_id_fk`: `FOREIGN KEY (backend_id) REFERENCES runtime_backends(id) ON DELETE RESTRICT`.
- `runtime_memory_bindings_check_0`: `CHECK (status = ANY (ARRAY['disabled'::text, 'active'::text, 'revoked'::text]))`.
- `runtime_memory_bindings_namespace_id_fk`: `FOREIGN KEY (tenant_id, namespace_id) REFERENCES memory_namespaces(tenant_id, id) ON DELETE RESTRICT`.
- `runtime_memory_bindings_pkey`: `PRIMARY KEY (id)`.
- `runtime_memory_bindings_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `runtime_memory_bindings_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `runtime_memory_bindings_unique_0`: `UNIQUE (namespace_id, backend_id)`.
- `runtime_memory_bindings_unique_1`: `UNIQUE (backend_id, runtime_namespace)`.

### Chỉ mục

- `CREATE INDEX runtime_memory_bindings_namespace_id_idx ON public.runtime_memory_bindings USING btree (tenant_id, namespace_id)`.
- `CREATE UNIQUE INDEX runtime_memory_bindings_pkey ON public.runtime_memory_bindings USING btree (id)`.
- `CREATE UNIQUE INDEX runtime_memory_bindings_tenant_key_uq ON public.runtime_memory_bindings USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX runtime_memory_bindings_unique_0 ON public.runtime_memory_bindings USING btree (namespace_id, backend_id)`.
- `CREATE UNIQUE INDEX runtime_memory_bindings_unique_1 ON public.runtime_memory_bindings USING btree (backend_id, runtime_namespace)`.

### Trigger và chính sách tenant

- `runtime_memory_bindings_touch` → `app_touch_updated_at`: `CREATE TRIGGER runtime_memory_bindings_touch BEFORE UPDATE ON runtime_memory_bindings FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at()`.

- Policy `runtime_memory_bindings_tenant_policy` (ALL); USING `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`; WITH CHECK `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`.

## runtime_session_bindings

Ràng buộc agent, version, channel và audience; token phải phù hợp binding đang active.

Số dòng trong snapshot: **0**. RLS: **bật**; FORCE RLS: **bật**.

| Cột | Kiểu PostgreSQL | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | Có | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | Có | FK | `—` | Tenant sở hữu dữ liệu |
| `identity_id` | `uuid` | Có | FK | `—` | Tham chiếu runtime_identities |
| `channel_id` | `text` | Có | FK | `—` | Tham chiếu cửa sổ reception hoặc groupchat quản lý |
| `agent_id` | `text` | Có | FK | `—` | Tham chiếu danh mục agent của platform |
| `agent_version_id` | `uuid` | Có | FK | `—` | Tham chiếu snapshot cấu hình agent bất biến |
| `team_member_id` | `uuid` | Không | FK | `—` | Tham chiếu agent và context riêng của team |
| `audience_kind` | `text` | Có | — | `—` | Phiên cá nhân hay context agent của nhóm |
| `customer_user_id` | `text` | Không | FK | `—` | Tham chiếu tài khoản người dùng chung của platform |
| `started_by_user_id` | `text` | Không | FK | `—` | Tham chiếu tài khoản người dùng chung của platform |
| `runtime_session_key` | `text` | Có | — | `—` | Thread ID hoặc session ID thực sự của framework |
| `checkpoint_namespace` | `text` | Có | — | `''::text` | Namespace gốc của graph trong thread |
| `status` | `text` | Có | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `generation` | `integer` | Có | — | `1` | Thế hệ điểm chờ để chống resume cũ |
| `policy_version` | `text` | Có | — | `—` | Phiên bản policy khi chọn dữ liệu |
| `lock_version` | `bigint` | Có | — | `0` | Bộ đếm CAS và fencing chống worker cũ ghi tiếp |
| `lease_owner` | `text` | Không | — | `—` | Worker giữ lease |
| `lease_until` | `timestamp with time zone` | Không | — | `—` | Thời điểm hết lease |
| `last_access_at` | `timestamp with time zone` | Không | — | `—` | Thời điểm last access |
| `expires_at` | `timestamp with time zone` | Không | — | `—` | Thời điểm hết hạn |
| `purged_at` | `timestamp with time zone` | Không | — | `—` | Thời điểm purged |
| `created_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm cập nhật |
| `backend_id` | `uuid` | Có | FK | `—` | Tham chiếu runtime_backends |

### Ràng buộc thực tế

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

### Chỉ mục

- `CREATE UNIQUE INDEX runtime_session_bindings_partial_0 ON public.runtime_session_bindings USING btree (tenant_id, channel_id, agent_id) WHERE ((audience_kind = 'personal'::text) AND (status = ANY (ARRAY['active'::text, 'provisioning'::text, 'interrupted'::text])))`.
- `CREATE UNIQUE INDEX runtime_session_bindings_partial_1 ON public.runtime_session_bindings USING btree (team_member_id) WHERE ((audience_kind = 'team'::text) AND (status = ANY (ARRAY['active'::text, 'provisioning'::text, 'interrupted'::text])))`.
- `CREATE UNIQUE INDEX runtime_session_bindings_pkey ON public.runtime_session_bindings USING btree (id)`.
- `CREATE UNIQUE INDEX runtime_session_bindings_tenant_key_uq ON public.runtime_session_bindings USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX runtime_session_bindings_unique_2 ON public.runtime_session_bindings USING btree (backend_id, runtime_session_key)`.

### Trigger và chính sách tenant

- `runtime_binding_scope` → `app_validate_runtime_binding`: `CREATE TRIGGER runtime_binding_scope BEFORE INSERT OR UPDATE ON runtime_session_bindings FOR EACH ROW EXECUTE FUNCTION app_validate_runtime_binding()`.
- `runtime_session_bindings_touch` → `app_touch_updated_at`: `CREATE TRIGGER runtime_session_bindings_touch BEFORE UPDATE ON runtime_session_bindings FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at()`.

- Policy `runtime_session_bindings_tenant_policy` (ALL); USING `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`; WITH CHECK `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`.

## runtime_session_operations

Nhật ký các thao tác lên phiên runtime; hỗ trợ vòng đời binding.

Số dòng trong snapshot: **0**. RLS: **bật**; FORCE RLS: **bật**.

| Cột | Kiểu PostgreSQL | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | Có | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | Có | FK | `—` | Tenant sở hữu dữ liệu |
| `binding_id` | `uuid` | Có | FK | `—` | Tham chiếu runtime_session_bindings |
| `actor_principal_id` | `uuid` | Có | FK | `—` | Tham chiếu execution_principals |
| `initiated_by_user_id` | `text` | Không | FK | `—` | Tham chiếu tài khoản người dùng chung của platform |
| `operation` | `text` | Có | — | `—` | Lệnh runtime được cấp quyền và theo dõi |
| `idempotency_key` | `text` | Có | — | `—` | Khóa chống xử lý lặp |
| `expected_generation` | `integer` | Có | — | `—` | Thế hệ binding mà lệnh được phép tác động |
| `expected_lock_version` | `bigint` | Có | — | `—` | Fencing version lệnh phải đối chiếu khi thực thi |
| `trigger_event_id` | `uuid` | Không | FK | `—` | Tham chiếu lịch sử nghiệp vụ bất biến |
| `interrupt_id` | `text` | Không | — | `—` | ID điểm dừng của runtime |
| `status` | `text` | Có | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `result_run_id` | `uuid` | Không | FK | `—` | Tham chiếu theo dõi thực thi xuyên framework |
| `failure_code` | `text` | Không | — | `—` | Mã lỗi đã loại thông tin nhạy cảm |
| `finished_at` | `timestamp with time zone` | Không | — | `—` | Thời điểm kết thúc |
| `created_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm cập nhật |

### Ràng buộc thực tế

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

### Chỉ mục

- `CREATE UNIQUE INDEX runtime_session_operations_pkey ON public.runtime_session_operations USING btree (id)`.
- `CREATE UNIQUE INDEX runtime_session_operations_tenant_key_uq ON public.runtime_session_operations USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX runtime_session_operations_unique_0 ON public.runtime_session_operations USING btree (binding_id, idempotency_key)`.

### Trigger và chính sách tenant

- `runtime_session_operations_touch` → `app_touch_updated_at`: `CREATE TRIGGER runtime_session_operations_touch BEFORE UPDATE ON runtime_session_operations FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at()`.

- Policy `runtime_session_operations_tenant_policy` (ALL); USING `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`; WITH CHECK `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`.

## scoped_user_roles

Vai trò management/staff/... trong một phạm vi và thời gian hiệu lực.

Số dòng trong snapshot: **27**. RLS: **bật**; FORCE RLS: **bật**.

| Cột | Kiểu PostgreSQL | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | Có | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | Có | FK | `—` | Tenant sở hữu dữ liệu |
| `membership_id` | `uuid` | Có | FK | `—` | Tham chiếu người dùng thuộc tenant |
| `scope_id` | `uuid` | Có | FK | `—` | Tham chiếu phạm vi quyền có kiểu rõ ràng |
| `role_code` | `text` | Có | — | `—` | Mã vai trò nghiệp vụ trong scope |
| `granted_by` | `text` | Có | FK | `—` | Người cấp quyền |
| `valid_from` | `timestamp with time zone` | Có | — | `—` | Bắt đầu hiệu lực |
| `valid_to` | `timestamp with time zone` | Không | — | `—` | Kết thúc hiệu lực; NULL là chưa kết thúc |
| `created_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm cập nhật |

### Ràng buộc thực tế

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

### Chỉ mục

- `CREATE INDEX scoped_role_period_excl ON public.scoped_user_roles USING gist (membership_id, scope_id, role_code, tstzrange(valid_from, valid_to, '[)'::text))`.
- `CREATE UNIQUE INDEX scoped_user_roles_pkey ON public.scoped_user_roles USING btree (id)`.
- `CREATE UNIQUE INDEX scoped_user_roles_tenant_key_uq ON public.scoped_user_roles USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX scoped_user_roles_unique_0 ON public.scoped_user_roles USING btree (membership_id, scope_id, role_code, valid_from)`.

### Trigger và chính sách tenant

- `scoped_user_roles_touch` → `app_touch_updated_at`: `CREATE TRIGGER scoped_user_roles_touch BEFORE UPDATE ON scoped_user_roles FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at()`.

- Policy `scoped_user_roles_tenant_policy` (ALL); USING `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`; WITH CHECK `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`.

## sites

Đô thị/dự án.

Số dòng trong snapshot: **1**. RLS: **bật**; FORCE RLS: **bật**.

| Cột | Kiểu PostgreSQL | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | Có | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | Có | FK | `—` | Tenant sở hữu dữ liệu |
| `domain_id` | `uuid` | Có | FK | `—` | Tham chiếu miền nghiệp vụ có thể cấu hình |
| `code` | `text` | Có | — | `—` | Mã định danh nghiệp vụ |
| `name` | `text` | Có | — | `—` | Tên hiển thị |
| `address` | `text` | Có | — | `—` | Địa chỉ |
| `timezone` | `text` | Có | — | `'Asia/Ho_Chi_Minh'::text` | Múi giờ IANA |
| `status` | `text` | Có | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `created_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm cập nhật |

### Ràng buộc thực tế

- `sites_domain_id_fk`: `FOREIGN KEY (tenant_id, domain_id) REFERENCES domains(tenant_id, id) ON DELETE RESTRICT`.
- `sites_pkey`: `PRIMARY KEY (id)`.
- `sites_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `sites_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `sites_unique_0`: `UNIQUE (domain_id, code)`.

### Chỉ mục

- `CREATE UNIQUE INDEX sites_pkey ON public.sites USING btree (id)`.
- `CREATE UNIQUE INDEX sites_tenant_key_uq ON public.sites USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX sites_unique_0 ON public.sites USING btree (domain_id, code)`.

### Trigger và chính sách tenant

- `sites_touch` → `app_touch_updated_at`: `CREATE TRIGGER sites_touch BEFORE UPDATE ON sites FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at()`.

- Policy `sites_tenant_policy` (ALL); USING `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`; WITH CHECK `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`.

## storage_locations

Vị trí/bucket lưu trữ; không phải vector store.

Số dòng trong snapshot: **1**. RLS: **bật**; FORCE RLS: **bật**.

| Cột | Kiểu PostgreSQL | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | Có | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | Có | FK | `—` | Tenant sở hữu dữ liệu |
| `provider` | `text` | Có | — | `—` | Nhà cung cấp dịch vụ |
| `endpoint_ref` | `text` | Có | — | `—` | Mã endpoint được quản trị allowlist |
| `region` | `text` | Không | — | `—` | Region cấu hình của object store |
| `bucket_name` | `text` | Có | — | `—` | Tên bucket vật lý |
| `tenant_prefix` | `text` | Có | — | `—` | Prefix object riêng cho tenant |
| `credential_secret_ref` | `text` | Có | — | `—` | Tham chiếu bộ thông tin truy cập object store trong vault |
| `versioning_required` | `boolean` | Có | — | `true` | Yêu cầu bucket có versioning trước khi ghi |
| `encryption_mode` | `text` | Có | — | `—` | Chế độ mã hóa phía object store |
| `kms_key_ref` | `text` | Không | — | `—` | Tham chiếu khóa KMS, không chứa vật liệu khóa |
| `purpose` | `text` | Có | — | `—` | Vai trò chức năng agent hoặc mục đích file |
| `status` | `text` | Có | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `created_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm cập nhật |

### Ràng buộc thực tế

- `storage_locations_check_0`: `CHECK (purpose = ANY (ARRAY['staging'::text, 'evidence'::text, 'derived'::text, 'documents'::text, 'reports'::text]))`.
- `storage_locations_check_1`: `CHECK (status = ANY (ARRAY['active'::text, 'readonly'::text, 'disabled'::text]))`.
- `storage_locations_pkey`: `PRIMARY KEY (id)`.
- `storage_locations_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `storage_locations_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `storage_locations_unique_0`: `UNIQUE (endpoint_ref, bucket_name, tenant_prefix)`.

### Chỉ mục

- `CREATE UNIQUE INDEX storage_locations_pkey ON public.storage_locations USING btree (id)`.
- `CREATE UNIQUE INDEX storage_locations_tenant_key_uq ON public.storage_locations USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX storage_locations_unique_0 ON public.storage_locations USING btree (endpoint_ref, bucket_name, tenant_prefix)`.

### Trigger và chính sách tenant

- `storage_locations_touch` → `app_touch_updated_at`: `CREATE TRIGGER storage_locations_touch BEFORE UPDATE ON storage_locations FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at()`.

- Policy `storage_locations_tenant_policy` (ALL); USING `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`; WITH CHECK `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`.

## tenant_memberships

Thành viên đang có hiệu lực của tenant.

Số dòng trong snapshot: **26**. RLS: **bật**; FORCE RLS: **bật**.

| Cột | Kiểu PostgreSQL | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | Có | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | Có | FK | `—` | Tenant sở hữu dữ liệu |
| `user_id` | `text` | Có | FK | `—` | Tài khoản liên quan |
| `status` | `text` | Có | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `joined_at` | `timestamp with time zone` | Không | — | `—` | Thời điểm gia nhập |
| `ended_at` | `timestamp with time zone` | Không | — | `—` | Thời điểm chấm dứt |
| `created_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm cập nhật |

### Ràng buộc thực tế

- `tenant_memberships_check_0`: `CHECK (status = ANY (ARRAY['pending'::text, 'active'::text, 'suspended'::text, 'ended'::text]))`.
- `tenant_memberships_pkey`: `PRIMARY KEY (id)`.
- `tenant_memberships_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `tenant_memberships_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `tenant_memberships_unique_0`: `UNIQUE (tenant_id, user_id)`.
- `tenant_memberships_user_id_fk`: `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT`.

### Chỉ mục

- `CREATE UNIQUE INDEX tenant_memberships_pkey ON public.tenant_memberships USING btree (id)`.
- `CREATE UNIQUE INDEX tenant_memberships_tenant_key_uq ON public.tenant_memberships USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX tenant_memberships_unique_0 ON public.tenant_memberships USING btree (tenant_id, user_id)`.
- `CREATE INDEX tenant_memberships_user_id_idx ON public.tenant_memberships USING btree (tenant_id, user_id)`.

### Trigger và chính sách tenant

- `tenant_memberships_touch` → `app_touch_updated_at`: `CREATE TRIGGER tenant_memberships_touch BEFORE UPDATE ON tenant_memberships FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at()`.

- Policy `tenant_memberships_tenant_policy` (ALL); USING `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`; WITH CHECK `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`.

## tenants

Ranh giới tenant dùng chung cho dữ liệu và RLS.

Số dòng trong snapshot: **1**. RLS: **tắt**; FORCE RLS: **tắt**.

| Cột | Kiểu PostgreSQL | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | Có | PK | `gen_random_uuid()` | Định danh bản ghi |
| `code` | `text` | Có | — | `—` | Mã định danh nghiệp vụ |
| `name` | `text` | Có | — | `—` | Tên hiển thị |
| `status` | `text` | Có | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `timezone` | `text` | Có | — | `'Asia/Ho_Chi_Minh'::text` | Múi giờ IANA |
| `retention_policy` | `jsonb` | Có | — | `'{}'::jsonb` | Chính sách lưu và xóa dữ liệu của tenant |
| `created_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm cập nhật |

### Ràng buộc thực tế

- `tenants_check_0`: `CHECK (status = ANY (ARRAY['active'::text, 'suspended'::text, 'closed'::text]))`.
- `tenants_pkey`: `PRIMARY KEY (id)`.
- `tenants_unique_0`: `UNIQUE (code)`.

### Chỉ mục

- `CREATE UNIQUE INDEX tenants_pkey ON public.tenants USING btree (id)`.
- `CREATE UNIQUE INDEX tenants_unique_0 ON public.tenants USING btree (code)`.

### Trigger và chính sách tenant

- `tenants_touch` → `app_touch_updated_at`: `CREATE TRIGGER tenants_touch BEFORE UPDATE ON tenants FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at()`.

## tickets

Nguồn nghiệp vụ có thể sinh memory candidate.

Số dòng trong snapshot: **22**. RLS: **bật**; FORCE RLS: **bật**.

| Cột | Kiểu PostgreSQL | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | Có | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | Có | FK | `—` | Tenant sở hữu dữ liệu |
| `code` | `text` | Có | — | `—` | Mã định danh nghiệp vụ |
| `requester_user_id` | `text` | Có | FK | `—` | Tham chiếu tài khoản người dùng chung của platform |
| `channel_id` | `text` | Có | FK | `—` | Tham chiếu cửa sổ reception hoặc groupchat quản lý |
| `unit_id` | `uuid` | Không | FK | `—` | Tham chiếu căn hộ hoặc nhà liền kề |
| `site_id` | `uuid` | Không | FK | `—` | Tham chiếu khu đô thị |
| `zone_id` | `uuid` | Không | FK | `—` | Tham chiếu phân khu |
| `building_id` | `uuid` | Không | FK | `—` | Tham chiếu tòa nhà |
| `management_unit_id` | `uuid` | Không | FK | `—` | Tham chiếu ban quản lý như một tổ chức |
| `coverage_id` | `uuid` | Không | FK | `—` | Tham chiếu địa bàn phụ trách theo thời gian |
| `category_id` | `uuid` | Không | FK | `—` | Tham chiếu phân loại chuẩn cho routing và báo cáo |
| `incident_type_id` | `uuid` | Không | FK | `—` | Tham chiếu loại sự cố thống kê được |
| `title` | `text` | Có | — | `—` | Tiêu đề |
| `description` | `text` | Có | — | `—` | Mô tả |
| `priority` | `text` | Không | — | `—` | Mức ưu tiên hoặc trọng số xếp hàng |
| `status` | `text` | Có | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `resolution_mode` | `text` | Không | — | `—` | Hướng dẫn tự xử lý hoặc sửa tại hiện trường |
| `contact_name` | `text` | Có | — | `—` | Tên người liên hệ tại thời điểm tạo |
| `contact_phone` | `text` | Có | — | `—` | Số liên hệ được chụp tại thời điểm tạo |
| `address_snapshot` | `jsonb` | Có | — | `—` | Địa chỉ lịch sử đã chụp |
| `assigned_team_id` | `uuid` | Không | FK | `—` | Tham chiếu một phiên cộng tác |
| `sla_policy_id` | `uuid` | Không | FK | `—` | Tham chiếu thời hạn phục vụ theo phạm vi |
| `response_due_at` | `timestamp with time zone` | Không | — | `—` | Hạn phản hồi |
| `resolution_due_at` | `timestamp with time zone` | Không | — | `—` | Hạn giải quyết |
| `first_response_at` | `timestamp with time zone` | Không | — | `—` | Thời điểm phản hồi đầu |
| `resolved_at` | `timestamp with time zone` | Không | — | `—` | Thời điểm giải quyết kỹ thuật |
| `closed_at` | `timestamp with time zone` | Không | — | `—` | Thời điểm hoàn tất ticket |
| `version` | `bigint` | Có | — | `0` | Phiên bản cấu hình hoặc bộ đếm chống ghi đè |
| `last_event_seq` | `bigint` | Có | — | `0` | Event cuối đã được ghi hoặc xử lý theo phạm vi bảng |
| `reopen_count` | `integer` | Có | — | `0` | Số lần mở lại |
| `created_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm cập nhật |
| `domain_id` | `uuid` | Có | FK | `—` | Tham chiếu domains.id |
| `request_kind` | `text` | Có | — | `—` | incident/service_request |
| `severity` | `text` | Có | — | `'unknown'::text` | unknown/minor/moderate/major/critical/not_applicable |
| `triage_status` | `text` | Có | — | `'pending'::text` | pending/provisional/confirmed/review_required |
| `current_triage_decision_id` | `uuid` | Không | FK | `—` | Tham chiếu ticket_triage_decisions.id |
| `is_emergency` | `boolean` | Có | — | `false` | Projection từ current applied decision |
| `active_sla_cycle_id` | `uuid` | Không | FK | `—` | Tham chiếu ticket_sla_cycles.id |

### Ràng buộc thực tế

- `ticket_triage_projection`: `TRIGGER DEFERRABLE INITIALLY DEFERRED; DEFERRABLE INITIALLY DEFERRED`.
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

### Chỉ mục

- `CREATE UNIQUE INDEX tickets_pkey ON public.tickets USING btree (id)`.
- `CREATE UNIQUE INDEX tickets_tenant_key_uq ON public.tickets USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX tickets_unique_0 ON public.tickets USING btree (tenant_id, code)`.

### Trigger và chính sách tenant

- `ticket_triage_projection` → `app_check_ticket_projection`: `CREATE CONSTRAINT TRIGGER ticket_triage_projection AFTER INSERT OR UPDATE ON tickets DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION app_check_ticket_projection()`.
- `tickets_touch` → `app_touch_updated_at`: `CREATE TRIGGER tickets_touch BEFORE UPDATE ON tickets FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at()`.

- Policy `tickets_tenant_policy` (ALL); USING `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`; WITH CHECK `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`.

## unit_residents

Cư dân–căn hộ; verification_status và valid_from/to quyết định quyền nơi ở.

Số dòng trong snapshot: **20**. RLS: **bật**; FORCE RLS: **bật**.

| Cột | Kiểu PostgreSQL | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | Có | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | Có | FK | `—` | Tenant sở hữu dữ liệu |
| `unit_id` | `uuid` | Có | FK | `—` | Tham chiếu căn hộ hoặc nhà liền kề |
| `user_id` | `text` | Có | FK | `—` | Tài khoản liên quan |
| `relation` | `text` | Có | — | `—` | Quan hệ cư trú |
| `verification_status` | `text` | Có | — | `—` | Trạng thái xác minh cư trú |
| `valid_from` | `timestamp with time zone` | Có | — | `—` | Bắt đầu hiệu lực |
| `valid_to` | `timestamp with time zone` | Không | — | `—` | Kết thúc hiệu lực; NULL là chưa kết thúc |
| `verified_by` | `text` | Không | FK | `—` | Tham chiếu tài khoản người dùng chung của platform |
| `verified_at` | `timestamp with time zone` | Không | — | `—` | Thời điểm xác minh |
| `created_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm cập nhật |

### Ràng buộc thực tế

- `unit_residents_check_0`: `CHECK (relation = ANY (ARRAY['owner'::text, 'tenant'::text, 'household'::text]))`.
- `unit_residents_check_1`: `CHECK (verification_status = ANY (ARRAY['pending'::text, 'verified'::text, 'rejected'::text, 'expired'::text]))`.
- `unit_residents_pkey`: `PRIMARY KEY (id)`.
- `unit_residents_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `unit_residents_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `unit_residents_unit_id_fk`: `FOREIGN KEY (tenant_id, unit_id) REFERENCES units(tenant_id, id) ON DELETE RESTRICT`.
- `unit_residents_user_id_fk`: `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT`.
- `unit_residents_verified_by_fk`: `FOREIGN KEY (verified_by) REFERENCES users(id) ON DELETE RESTRICT`.

### Chỉ mục

- `CREATE UNIQUE INDEX unit_residents_pkey ON public.unit_residents USING btree (id)`.
- `CREATE UNIQUE INDEX unit_residents_tenant_key_uq ON public.unit_residents USING btree (tenant_id, id)`.
- `CREATE INDEX unit_residents_user_id_idx ON public.unit_residents USING btree (tenant_id, user_id)`.

### Trigger và chính sách tenant

- `unit_residents_touch` → `app_touch_updated_at`: `CREATE TRIGGER unit_residents_touch BEFORE UPDATE ON unit_residents FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at()`.

- Policy `unit_residents_tenant_policy` (ALL); USING `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`; WITH CHECK `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`.

## units

Căn hộ thuộc tòa.

Số dòng trong snapshot: **20**. RLS: **bật**; FORCE RLS: **bật**.

| Cột | Kiểu PostgreSQL | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | Có | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | Có | FK | `—` | Tenant sở hữu dữ liệu |
| `site_id` | `uuid` | Có | FK | `—` | Tham chiếu khu đô thị |
| `zone_id` | `uuid` | Không | FK | `—` | Tham chiếu phân khu |
| `building_id` | `uuid` | Không | FK | `—` | Tham chiếu tòa nhà |
| `code` | `text` | Có | — | `—` | Mã định danh nghiệp vụ |
| `unit_kind` | `text` | Có | — | `—` | Loại căn hộ hoặc nhà ở |
| `floor` | `text` | Không | — | `—` | Tầng |
| `status` | `text` | Có | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `created_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm cập nhật |

### Ràng buộc thực tế

- `units_building_id_fk`: `FOREIGN KEY (tenant_id, building_id) REFERENCES buildings(tenant_id, id) ON DELETE RESTRICT`.
- `units_check_0`: `CHECK (unit_kind = ANY (ARRAY['apartment'::text, 'townhouse'::text, 'villa'::text, 'other'::text]))`.
- `units_pkey`: `PRIMARY KEY (id)`.
- `units_site_id_fk`: `FOREIGN KEY (tenant_id, site_id) REFERENCES sites(tenant_id, id) ON DELETE RESTRICT`.
- `units_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `units_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `units_zone_id_fk`: `FOREIGN KEY (tenant_id, zone_id) REFERENCES zones(tenant_id, id) ON DELETE RESTRICT`.

### Chỉ mục

- `CREATE UNIQUE INDEX units_partial_0 ON public.units USING btree (building_id, code) WHERE (building_id IS NOT NULL)`.
- `CREATE UNIQUE INDEX units_partial_1 ON public.units USING btree (zone_id, code) WHERE (building_id IS NULL)`.
- `CREATE UNIQUE INDEX units_pkey ON public.units USING btree (id)`.
- `CREATE UNIQUE INDEX units_tenant_key_uq ON public.units USING btree (tenant_id, id)`.

### Trigger và chính sách tenant

- `units_touch` → `app_touch_updated_at`: `CREATE TRIGGER units_touch BEFORE UPDATE ON units FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at()`.

- Policy `units_tenant_policy` (ALL); USING `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`; WITH CHECK `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`.

## users

Tài khoản người dùng, người hỏi, người xuất bản và người duyệt.

Số dòng trong snapshot: **26**. RLS: **tắt**; FORCE RLS: **tắt**.

| Cột | Kiểu PostgreSQL | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `text` | Có | PK | `—` | Định danh bản ghi |
| `email` | `text` | Không | — | `—` | Địa chỉ email |
| `name` | `text` | Không | — | `—` | Tên hiển thị |
| `image` | `text` | Không | — | `—` | Ảnh đại diện |
| `email_verified` | `boolean` | Có | — | `false` | Email đã được xác minh |
| `groups` | `text[]` | Có | — | `'{}'::text[]` | Nhóm danh tính legacy; không dùng làm ACL mặc định |
| `onboarding_step` | `integer` | Có | — | `0` | Bước onboarding hiện tại |
| `onboarding_completed_at` | `timestamp with time zone` | Không | — | `—` | Thời điểm hoàn tất onboarding |
| `last_signed_in_at` | `timestamp with time zone` | Không | — | `—` | Lần đăng nhập gần nhất |
| `created_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm cập nhật |
| `phone_e164` | `text` | Không | — | `—` | Số điện thoại đã chuẩn hóa E.164 |
| `phone_verified_at` | `timestamp with time zone` | Không | — | `—` | Thời điểm xác minh số điện thoại |
| `status` | `text` | Có | — | `'pending'::text` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `disabled_at` | `timestamp with time zone` | Không | — | `—` | Thời điểm vô hiệu hóa |
| `deleted_at` | `timestamp with time zone` | Không | — | `—` | Thời điểm xóa mềm |

### Ràng buộc thực tế

- `users_check_0`: `CHECK (status = ANY (ARRAY['pending'::text, 'active'::text, 'suspended'::text, 'deleted'::text]))`.
- `users_check_1`: `CHECK (status = 'deleted'::text OR email IS NOT NULL OR phone_e164 IS NOT NULL)`.
- `users_pkey`: `PRIMARY KEY (id)`.

### Chỉ mục

- `CREATE UNIQUE INDEX users_partial_0 ON public.users USING btree (lower(email)) WHERE (email IS NOT NULL)`.
- `CREATE UNIQUE INDEX users_partial_1 ON public.users USING btree (phone_e164) WHERE (phone_e164 IS NOT NULL)`.
- `CREATE UNIQUE INDEX users_pkey ON public.users USING btree (id)`.

### Trigger và chính sách tenant

- `users_touch` → `app_touch_updated_at`: `CREATE TRIGGER users_touch BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at()`.

## workspace_members

Thành viên workspace; liên quan ACL/audience.

Số dòng trong snapshot: **1**. RLS: **bật**; FORCE RLS: **bật**.

| Cột | Kiểu PostgreSQL | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `tenant_id` | `uuid` | Có | PK/FK | `—` | Tenant sở hữu dữ liệu |
| `workspace_id` | `uuid` | Có | PK/FK | `—` | Workspace của ban quản lý |
| `user_id` | `text` | Có | PK/FK | `—` | Tài khoản liên quan |
| `status` | `text` | Có | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `joined_at` | `timestamp with time zone` | Có | — | `—` | Thời điểm gia nhập |
| `left_at` | `timestamp with time zone` | Không | — | `—` | Thời điểm rời workspace |
| `created_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm tạo |

### Ràng buộc thực tế

- `workspace_members_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `workspace_members_tenant_id_workspace_id_user_id_pk`: `PRIMARY KEY (tenant_id, workspace_id, user_id)`.
- `workspace_members_user_id_fk`: `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT`.
- `workspace_members_workspace_id_fk`: `FOREIGN KEY (tenant_id, workspace_id) REFERENCES workspaces(tenant_id, id) ON DELETE RESTRICT`.

### Chỉ mục

- `CREATE UNIQUE INDEX workspace_members_tenant_id_workspace_id_user_id_pk ON public.workspace_members USING btree (tenant_id, workspace_id, user_id)`.

### Trigger và chính sách tenant

Không có user trigger trong snapshot.

- Policy `workspace_members_tenant_policy` (ALL); USING `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`; WITH CHECK `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`.

## workspaces

Không gian hoạt động của agent/team.

Số dòng trong snapshot: **1**. RLS: **bật**; FORCE RLS: **bật**.

| Cột | Kiểu PostgreSQL | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | Có | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | Có | FK | `—` | Tenant sở hữu dữ liệu |
| `management_unit_id` | `uuid` | Có | FK | `—` | Tham chiếu ban quản lý như một tổ chức |
| `code` | `text` | Có | — | `—` | Mã định danh nghiệp vụ |
| `name` | `text` | Có | — | `—` | Tên hiển thị |
| `status` | `text` | Có | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `created_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm cập nhật |

### Ràng buộc thực tế

- `workspaces_management_unit_id_fk`: `FOREIGN KEY (tenant_id, management_unit_id) REFERENCES management_units(tenant_id, id) ON DELETE RESTRICT`.
- `workspaces_pkey`: `PRIMARY KEY (id)`.
- `workspaces_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `workspaces_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `workspaces_unique_0`: `UNIQUE (tenant_id, management_unit_id)`.

### Chỉ mục

- `CREATE UNIQUE INDEX workspaces_pkey ON public.workspaces USING btree (id)`.
- `CREATE UNIQUE INDEX workspaces_tenant_key_uq ON public.workspaces USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX workspaces_unique_0 ON public.workspaces USING btree (tenant_id, management_unit_id)`.

### Trigger và chính sách tenant

- `workspaces_touch` → `app_touch_updated_at`: `CREATE TRIGGER workspaces_touch BEFORE UPDATE ON workspaces FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at()`.

- Policy `workspaces_tenant_policy` (ALL); USING `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`; WITH CHECK `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`.

## zones

Phân khu thuộc site.

Số dòng trong snapshot: **8**. RLS: **bật**; FORCE RLS: **bật**.

| Cột | Kiểu PostgreSQL | NOT NULL | Khóa | Mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `uuid` | Có | PK | `gen_random_uuid()` | Định danh bản ghi |
| `tenant_id` | `uuid` | Có | FK | `—` | Tenant sở hữu dữ liệu |
| `site_id` | `uuid` | Có | FK | `—` | Tham chiếu khu đô thị |
| `code` | `text` | Có | — | `—` | Mã định danh nghiệp vụ |
| `name` | `text` | Có | — | `—` | Tên hiển thị |
| `status` | `text` | Có | — | `—` | Trạng thái; xem tập giá trị và quy tắc bên dưới |
| `created_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm tạo |
| `updated_at` | `timestamp with time zone` | Có | — | `now()` | Thời điểm cập nhật |

### Ràng buộc thực tế

- `zones_pkey`: `PRIMARY KEY (id)`.
- `zones_site_id_fk`: `FOREIGN KEY (tenant_id, site_id) REFERENCES sites(tenant_id, id) ON DELETE RESTRICT`.
- `zones_tenant_id_fk`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`.
- `zones_tenant_key_uq`: `UNIQUE (tenant_id, id)`.
- `zones_unique_0`: `UNIQUE (site_id, code)`.

### Chỉ mục

- `CREATE UNIQUE INDEX zones_pkey ON public.zones USING btree (id)`.
- `CREATE UNIQUE INDEX zones_tenant_key_uq ON public.zones USING btree (tenant_id, id)`.
- `CREATE UNIQUE INDEX zones_unique_0 ON public.zones USING btree (site_id, code)`.

### Trigger và chính sách tenant

- `zones_touch` → `app_touch_updated_at`: `CREATE TRIGGER zones_touch BEFORE UPDATE ON zones FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at()`.

- Policy `zones_tenant_policy` (ALL); USING `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`; WITH CHECK `(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)`.
