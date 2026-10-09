# Phân tích nghiệp vụ Multi-tenant, phân vùng dữ liệu và phân quyền

## 1. Mục tiêu

Platform được vận hành như một dịch vụ dùng chung cho nhiều đơn vị. Các hệ
thống bên ngoài gọi API của platform để sử dụng agent, knowledge base, MCP và
các tài nguyên liên quan.

Mọi request phải được xác định chính xác theo thứ tự:

```text
Bên gọi API
  └── Tổ chức/khách hàng
        └── Domain nghiệp vụ
              └── Khu vực quản lý
                    └── Tài khoản ban quản lý
                          └── Agent, dữ liệu và MCP được phép sử dụng
```

Ví dụ:

```text
Vingroup                         organization
├── Vinhomes                     business domain
│   ├── Ocean Park 1             area
│   └── Ocean Park 2             area
├── Vinpearl                     business domain
└── VinWonders                   business domain
```

Trong tài liệu này, “domain” là miền nghiệp vụ như Vinhomes, Vinpearl hoặc
VinWonders; không phải tên miền Internet.

## 2. Nguyên tắc quan trọng nhất

Backend không được tin `domain_id`, `area_id` hoặc `user_id` do client tự gửi
trong request body/header.

Danh tính và phạm vi phải được suy ra từ credential đã xác thực:

```text
API key/JWT hợp lệ
  → principal
  → organization_id
  → domain/area được cấp
  → role cố định của tài khoản
  → truy vấn dữ liệu có scope bắt buộc
```

Client có thể gửi domain hoặc area trên URL để chọn tài nguyên, nhưng backend
phải đối chiếu giá trị đó với scope của principal. Nếu không khớp, trả về `403
Forbidden` và ghi audit log.

Không được tiếp tục sử dụng `X-User-ID` như cơ chế xác thực khi triển khai SaaS,
vì caller có thể tự thay giá trị header này.

## 3. Tài khoản người dùng và bên gọi API

### 3.1 Human user

Hệ thống chỉ có hai loại human user:

- `VINGROUP_ADMIN`: tài khoản quản trị cao nhất của Vingroup;
- `AREA_MANAGER`: tài khoản đại diện cho một ban quản lý khu vực, ví dụ Ban
  quản lý Ocean Park 1 hoặc Ban quản lý Ocean Park 2.

`VINGROUP_ADMIN` tạo và quản lý các tài khoản `AREA_MANAGER`.
`AREA_MANAGER` không được tạo hoặc quản lý tài khoản khác.

```text
VINGROUP_ADMIN
├── tạo/quản lý AREA_MANAGER của Ocean Park 1
├── tạo/quản lý AREA_MANAGER của Ocean Park 2
└── gán MCP cho từng tài khoản

AREA_MANAGER Ocean Park 1 ── chỉ vận hành dữ liệu Ocean Park 1
AREA_MANAGER Ocean Park 2 ── chỉ vận hành dữ liệu Ocean Park 2
```

Human user sử dụng access token ngắn hạn và refresh token có rotation.

### 3.2 API credential cho tích hợp hệ thống

Ứng dụng của đối tác có thể gọi API server-to-server bằng API credential. API
credential không phải là một user hoặc role mới. Với ứng dụng dùng chung như
Vinhomes App, credential thuộc một domain; request được định tuyến tới area từ
mapping cư dân/căn nhà đã đồng bộ và được Platform xác minh. Không
sử dụng refresh token của human user cho tích hợp máy-máy.

Mỗi API client cần có:

- `client_id` công khai;
- API secret hoặc private key;
- secret chỉ hiển thị một lần, database chỉ lưu hash;
- `domain_id` cố định;
- area được xác định và kiểm tra trên từng request;
- ngày hết hạn;
- trạng thái active/suspended/revoked;
- rate limit riêng;
- tùy chọn IP allowlist;
- `last_used_at` và audit log.

Khuyến nghị format API key:

```text
dp_<key_id>.<random_secret>
```

`key_id` dùng để tìm record; phần secret được kiểm tra với HMAC/hash. Không quét
toàn bộ bảng API key để tìm token.

## 4. Mô hình phạm vi dữ liệu

### 4.1 Organization

Khách hàng cao nhất về mặt dữ liệu. Một organization có thể có nhiều domain.

Ví dụ hiện tại có thể là `Vingroup`. Khi platform bán cho khách hàng khác, mỗi
khách hàng có một organization riêng.

### 4.2 Business domain

Nhóm nghiệp vụ hoặc thương hiệu thuộc organization:

- Vinhomes;
- Vinpearl;
- VinWonders.

Nên dùng tên bảng `business_domains`, tránh dùng `domains` nếu hệ thống còn quản
lý domain Internet.

### 4.3 Area

Đơn vị vận hành nhỏ hơn domain. Với Vinhomes, area có thể là một khu đô thị:

- Ocean Park 1;
- Ocean Park 2.

Với Vinpearl/VinWonders, cùng mô hình có thể đại diện cho resort, cơ sở hoặc địa
điểm vận hành. Tên kỹ thuật nên là `areas` hoặc `operating_scopes` để không bị
gắn cứng với khái niệm khu đô thị.

### 4.4 Quy tắc gán user

Theo yêu cầu đã chốt, mỗi tài khoản `AREA_MANAGER` đại diện cho đúng một ban
quản lý và quản lý đúng một area. `domain_id` và `area_id` được gắn trực tiếp
vào tài khoản khi đăng ký. Giai đoạn hiện tại chưa bật admin; người dùng tự đăng
ký và chọn domain/area. Trước khi public Internet cần bổ sung invitation hoặc
xác minh ban quản lý để tránh người lạ tự nhận một area.

Một area có thể có nhiều tài khoản `AREA_MANAGER` nếu ban quản lý cần nhiều
người đăng nhập. Nếu nghiệp vụ chỉ cho phép đúng một tài khoản trên một area,
cần thêm unique constraint trên `area_id`.

## 5. Mô hình hai role cố định

Hệ thống chỉ có hai role cố định. Không cần thiết kế role động, bảng role hay
permission phức tạp ở giai đoạn này.

### 5.1 `VINGROUP_ADMIN`

Đây là role quản trị tài khoản cao nhất của Vingroup. Admin chỉ quản lý các ban
quản lý khu vực, gồm:

- tạo tài khoản ban quản lý;
- gắn tài khoản vào đúng domain và area;
- sửa thông tin tài khoản;
- tạm khóa và mở khóa tài khoản;
- soft-delete và xóa vĩnh viễn tài khoản;
- tạo, rotate và revoke API key của ban quản lý;
- gán hoặc gỡ MCP cho từng tài khoản ban quản lý;
- xem audit log liên quan đến tài khoản, API key và việc gán MCP.

`VINGROUP_ADMIN` không mặc nhiên được gọi agent, đọc/ghi dữ liệu nghiệp vụ hoặc
chạy MCP thay cho một `AREA_MANAGER`. Cách tách này giữ tài khoản quản trị ở đúng
vai trò quản lý tài khoản và giảm rủi ro truy cập dữ liệu vận hành.

Không cho phép tạo `VINGROUP_ADMIN` qua API đăng ký công khai. Tài khoản admin
đầu tiên phải được bootstrap bằng migration/CLI an toàn.

### 5.2 `AREA_MANAGER`

Đây là tài khoản của một ban quản lý khu vực. Mỗi tài khoản được gắn cố định
với một `domain_id` và một `area_id`.

Area Manager có quyền:

- đăng nhập và sử dụng platform;
- gọi agent API trong area của mình;
- đọc/ghi dữ liệu nghiệp vụ thuộc area của mình;
- sử dụng đúng các MCP mà admin đã gán;
- không được xem hoặc sửa dữ liệu của area khác;
- không được tạo, khóa, xóa tài khoản khác;
- không được tự gán MCP hoặc thay đổi domain/area của mình.

### 5.3 Ma trận quyền

| Nghiệp vụ | `VINGROUP_ADMIN` | `AREA_MANAGER` |
|---|:---:|:---:|
| Tạo tài khoản ban quản lý | Có | Không |
| Tạm khóa/mở khóa tài khoản | Có | Không |
| Xóa tài khoản | Có | Không |
| Gắn tài khoản vào domain/area | Có | Không |
| Gán/gỡ MCP cho tài khoản | Có | Không |
| Xem audit quản trị tài khoản/API key/MCP | Có | Không |
| Gọi agent API | Không | Chỉ area được gán |
| Đọc/ghi dữ liệu nghiệp vụ | Không | Chỉ area được gán |
| Chạy MCP nghiệp vụ | Không | Chỉ MCP được admin gán |
| Quản lý API key domain | Qua vận hành nội bộ | Không |

API client không phải role thứ ba. Nó là credential máy-máy thuộc một domain và
không đăng nhập thay cho `AREA_MANAGER`.

## 6. Quy trình xử lý một API request

```text
1. Nhận request
2. Xác thực Bearer JWT hoặc API key
3. Kiểm tra actor đang active và credential chưa hết hạn/revoke
4. Tạo RequestPrincipal
   - user_id
   - role
   - organization_id
   - domain_id/area_id của tài khoản
   - key_id nếu request dùng API key
5. Xác định resource/action mà request yêu cầu
6. Kiểm tra quyền cố định theo role
7. Kiểm tra requested scope thuộc allowed scope
8. Truy vấn database với scope bắt buộc
9. Chỉ nạp MCP được gán và đang active
10. Thực thi
11. Ghi audit log và usage/metering
```

Ví dụ request đến endpoint:

```text
POST /v1/domains/vinhomes/areas/ocean-park-1/agents/{agent_id}/chat
Authorization: Bearer <partner-token>
```

Nếu token thuộc Ocean Park 2, backend phải trả `403`; không được chỉ dựa vào
`area_id` trong URL để truy vấn.

## 7. RequestPrincipal và PolicyContext

Mỗi request sau khi xác thực nên tạo một object bất biến:

```text
RequestPrincipal
├── user_id
├── role: VINGROUP_ADMIN | AREA_MANAGER
├── organization_id
├── domain_id (nullable với VINGROUP_ADMIN)
├── area_id (nullable với VINGROUP_ADMIN)
├── session_id (nullable nếu dùng API key)
└── key_id (nullable nếu dùng JWT)
```

Scope thực thi không nên truyền dưới dạng các string rời rạc. Nên dùng:

```text
PolicyContext
├── principal
├── requested_domain_id
├── requested_area_id
├── resource_type
├── resource_id
└── action
```

Mọi service/repository nhạy cảm phải nhận `PolicyContext` hoặc scope đã được
policy engine xác minh. Không cung cấp hàm `get_agent(agent_id)` không có scope.

## 8. Mô hình database đề xuất

### 8.1 Cấu trúc tổ chức

```text
organizations
  id, code, name, status, created_at, updated_at

business_domains
  id, organization_id, code, name, status, created_at, updated_at

areas
  id, domain_id, code, name, status, created_at, updated_at
```

Unique constraint cần có:

```text
organizations(code)
business_domains(organization_id, code)
areas(domain_id, code)
```

### 8.2 User và role cố định

```text
auth_users
  id
  organization_id
  domain_id nullable
  area_id nullable
  role: VINGROUP_ADMIN | AREA_MANAGER
  email
  username
  password_hash
  status
  token_version
  created_by nullable
  created_at
  updated_at
```

Với nghiệp vụ hiện tại, một cột `role` là đủ vì mỗi tài khoản chỉ có một role và
`AREA_MANAGER` chỉ thuộc một area. Không cần các bảng `roles`, `permissions`,
`role_permissions` hoặc `role_bindings`.

Các constraint bắt buộc:

- `role` chỉ nhận `VINGROUP_ADMIN` hoặc `AREA_MANAGER`;
- `AREA_MANAGER` bắt buộc có `domain_id` và `area_id` hợp lệ;
- `area_id` phải thuộc đúng `domain_id`;
- `VINGROUP_ADMIN` có phạm vi quản trị tài khoản toàn Vingroup, vì vậy
  `domain_id` và `area_id` để `NULL`; điều này không cấp quyền đọc dữ liệu nghiệp
  vụ;
- email và username phải unique trong organization;
- chỉ `VINGROUP_ADMIN` đang active mới được tạo/sửa trạng thái tài khoản khác.

### 8.3 API clients

```text
api_clients
  id
  organization_id
  domain_id
  name
  status
  rate_limit_policy_id
  created_by
  expires_at

api_client_credentials
  id/key_id
  api_client_id
  secret_hash
  created_at
  expires_at
  revoked_at
  last_used_at

```

Khi xác thực, backend lấy domain từ API client. Area đến từ ngữ cảnh cư dân/căn
nhà và bắt buộc thuộc domain đó. Một client có thể có nhiều credential để rotate
secret không gián đoạn.

### 8.4 MCP assignments

```text
mcp_catalog
  id, code, name, status, risk_level, configuration_schema

mcp_assignments
  id
  mcp_id
  user_id
  status
  credential_binding_id nullable
  assigned_by
  created_at
  expires_at nullable
```

Quy tắc tính MCP hiệu lực:

```text
MCP đang active trong catalog
∩ MCP được VINGROUP_ADMIN gán trực tiếp cho AREA_MANAGER
= danh sách MCP tài khoản được phép sử dụng
```

Mặc định là deny. Có record MCP không đồng nghĩa với được phép thực thi.

Secret của MCP không lưu plaintext trong assignment. Secret cần nằm trong
credential store được mã hóa hoặc secret manager; assignment chỉ giữ reference.

### 8.5 Audit log

```text
audit_events
  id
  occurred_at
  request_id
  actor_id
  authentication_method: jwt | api_key
  organization_id
  domain_id nullable
  area_id nullable
  action
  resource_type
  resource_id nullable
  outcome: success | denied | failed
  reason nullable
  ip_address
  user_agent
  metadata JSONB
```

Các hành động bắt buộc audit:

- đăng nhập thất bại/thành công;
- tạo, khóa, mở khóa, xóa user;
- thay đổi domain/area của tài khoản;
- tạo/rotate/revoke API key;
- gán/gỡ MCP;
- từ chối request do sai domain/area;
- chạy MCP/tool có thay đổi dữ liệu;
- xóa hoặc export dữ liệu.

## 9. Trạng thái tài khoản và nghiệp vụ xóa

### 9.1 Trạng thái

```text
pending       chưa kích hoạt
active        được phép đăng nhập/gọi API
suspended     tạm khóa; không cấp token mới
deleting      đang chờ xóa
deleted       đã soft-delete
```

Khi admin tạm khóa user:

1. đổi trạng thái sang `suspended`;
2. revoke toàn bộ refresh session;
3. revoke hoặc disable API credential thuộc user nếu có;
4. access token cũ cần bị chặn bằng `account_status/token_version` lookup hoặc
   chấp nhận sống tối đa đến khi access token hết hạn;
5. ghi audit log.

### 9.2 Xóa vĩnh viễn

Không nên hard delete ngay khi bấm nút. Khuyến nghị quy trình hai bước:

```text
Admin yêu cầu xóa
  → status=deleting
  → revoke credential
  → khóa mọi hoạt động
  → kiểm tra/reassign tài nguyên sở hữu
  → chờ retention period
  → background purge
  → audit kết quả
```

Chỉ `VINGROUP_ADMIN` được yêu cầu purge tài khoản `AREA_MANAGER`. Không có role
quản trị trung gian.

Trước khi purge phải xác định chính sách cho:

- chat history;
- long-term memory;
- workspace;
- ảnh/tài liệu trên MinIO/S3;
- knowledge base/vector;
- schedule;
- agent/team do user sở hữu;
- MCP credential;
- audit log (thường không xóa, mà pseudonymize actor).

## 10. Data isolation xuyên suốt hệ thống

Mọi dữ liệu nghiệp vụ cần mang tối thiểu:

```text
organization_id
domain_id
area_id
owner_user_id
```

Không phải bảng nào cũng cần cả bốn cột, nhưng phải truy ngược được scope bằng
foreign key và mọi query phải filter scope.

Các vị trí dễ rò rỉ chéo cần kiểm tra riêng:

- PostgreSQL queries;
- pgvector semantic search;
- Redis cache key và pub/sub channel;
- MinIO/S3 object key và presigned URL;
- ReMe/long-term memory;
- workspace path;
- background jobs và scheduler;
- MCP runtime/credential;
- logs, tracing và analytics.

Ví dụ cache key không được chỉ là:

```text
agent:{agent_id}
```

Nên chứa scope:

```text
org:{org_id}:domain:{domain_id}:area:{area_id}:agent:{agent_id}
```

Vector search phải filter scope trước hoặc đồng thời với similarity search;
không tìm toàn cục rồi mới lọc top-k sau, vì có thể làm mất kết quả đúng và tạo
rủi ro side-channel.

## 11. Quản lý MCP theo tài khoản ban quản lý

`VINGROUP_ADMIN` cần các use case:

1. xem MCP có sẵn trong catalog;
2. gán MCP trực tiếp cho một tài khoản `AREA_MANAGER`;
3. đặt ngày hết hạn assignment;
4. gỡ/revoke ngay lập tức;
5. xem tài khoản nào đã chạy MCP nào, lúc nào, trên resource nào;
6. quản lý credential binding tách biệt với quyền sử dụng.

Khi bắt đầu một agent run, backend phải chụp `effective MCP set`. Mỗi tool call
vẫn nên kiểm tra assignment còn hiệu lực, đặc biệt với tool rủi ro cao, để việc
admin revoke có hiệu lực trong phiên đang chạy.

MCP nên có `risk_level`:

```text
read_only
write
privileged
external_side_effect
```

MCP có tác động bên ngoài có thể yêu cầu approval/HITL ngay cả khi actor đã được
gán quyền.

## 12. Khoảng cách giữa source hiện tại và nghiệp vụ mục tiêu

Source hiện tại đã có một số nền tảng:

- access JWT và rotating refresh token ở backend;
- `tenant_id` trong auth principal;
- PostgreSQL migrations;
- user-level filtering ở nhiều service;
- MCP record/credential;
- long-term memory và image metadata có tenant/user scope.

Những phần chưa đủ cho mô hình này:

- đã có domain/area seed cho môi trường local;
- đã có `role`, `domain_id` và `area_id` trực tiếp trên user;
- đã có API client credential theo domain và ticket queue theo area;
- đã có memory candidate; chỉ sau khi Area Manager duyệt mới embedding;
- chưa có API-key rotation/rate-limit/IP allowlist;
- chưa có admin APIs cho khóa/xóa tài khoản;
- chưa có MCP assignment trực tiếp theo user;
- nhiều query hiện mới filter theo `user_id`, chưa filter đầy đủ organization,
  domain và area;
- frontend đã có đăng ký/đăng nhập cho `AREA_MANAGER`, nhưng chưa có admin UI;
- chưa có audit log tập trung;
- `X-User-ID` legacy vẫn tồn tại khi auth bị tắt.

Do đó không nên public platform trước khi hoàn thành scope enforcement. Chỉ có
JWT authentication là chưa đủ; lỗi nghiêm trọng thường nằm ở authorization và
object-level access control.

## 13. Lộ trình triển khai đề xuất

### Giai đoạn 1 — Scope model

- tạo organization, business domain và area;
- bổ sung `organization_id/domain_id/area_id` cho resource quan trọng;
- migration dữ liệu hiện có vào default organization/domain/area;
- tạo `RequestPrincipal` và `PolicyContext`.

### Giai đoạn 2 — Phân quyền hai role và cô lập area

- bổ sung role cố định `VINGROUP_ADMIN` và `AREA_MANAGER` trên user;
- triển khai policy service với ma trận quyền cố định;
- repository bắt buộc nhận scope;
- test chống IDOR/cross-tenant cho từng resource.

### Giai đoạn 3 — Admin account lifecycle

- API tạo, sửa, suspend, restore, soft-delete và purge user;
- revoke sessions khi khóa;
- audit log;
- Web UI quản trị.

### Giai đoạn 4 — API credential theo domain

- API client thuộc domain, không thuộc tài khoản `AREA_MANAGER`;
- API key hashing, rotation, expiry và revoke;
- rate limiting và quota/metering;
- IP allowlist tùy chọn;
- usage report/billing dimensions theo organization/domain/area/client.

### Giai đoạn 5 — Gán MCP theo tài khoản

- MCP catalog và assignment trực tiếp tới `AREA_MANAGER`;
- MCP của partner request được chọn từ Agent deployment đúng area;
- credential binding mã hóa;
- runtime re-check và audit tool calls.

## 14. Tiêu chí nghiệm thu bảo mật

Hệ thống chỉ được coi là đạt khi có test tự động chứng minh:

1. token Ocean Park 1 không đọc/sửa tài nguyên Ocean Park 2;
2. token Vinhomes không truy cập Vinpearl/VinWonders;
3. thay `user_id/domain_id/area_id` trong body hoặc URL không vượt scope;
4. user suspended không login/refresh và session bị revoke;
5. API key revoked không thể gọi request mới;
6. API client không thể gửi ticket sang domain khác và area request phải thuộc
   domain của key;
7. user không chạy được MCP chưa gán;
8. gỡ MCP có hiệu lực với phiên đang chạy theo chính sách;
9. pgvector, Redis, S3 và workspace không trả dữ liệu scope khác;
10. mọi thao tác admin và mọi request bị deny đều có audit event;
11. hard delete không để lại credential/object/vector mồ côi ngoài chính sách;
12. `AREA_MANAGER` không thể tạo, sửa, khóa, xóa tài khoản hoặc thay đổi role.

## 15. Các quyết định nghiệp vụ đã chốt

1. Chỉ có hai role: `VINGROUP_ADMIN` và `AREA_MANAGER`.
2. `VINGROUP_ADMIN` là cấp quản trị duy nhất, có quyền quản lý mọi ban quản lý.
3. Mỗi tài khoản `AREA_MANAGER` thuộc đúng một domain và một area.
4. `AREA_MANAGER` không được quản lý tài khoản, thay đổi scope hoặc tự gán MCP.
5. API credential không phải role; nó thuộc một domain và không đăng nhập thay
   cho `AREA_MANAGER`.
6. MCP được `VINGROUP_ADMIN` gán trực tiếp cho từng tài khoản `AREA_MANAGER`.

Các thông số kỹ thuật vẫn cần cấu hình khi triển khai:

- một area được phép có một hay nhiều tài khoản `AREA_MANAGER`;
- thời gian retention trước khi purge vĩnh viễn;
- hạn dùng, rate limit và IP allowlist của API key;
- credential MCP dùng riêng cho từng tài khoản hay dùng chung theo area;
- quota/metering theo area hoặc theo API client.

## 16. Khuyến nghị mặc định

Nếu chưa có quyết định khác, nên bắt đầu bằng:

```text
Organization: Vingroup
Business domains: Vinhomes, Vinpearl, VinWonders
VINGROUP_ADMIN: quản trị toàn bộ tài khoản ban quản lý
AREA_MANAGER: một tài khoản chỉ thuộc một area
API client: thuộc domain; mỗi request phải resolve và kiểm tra area
Role storage: một cột role cố định trên auth_users
Default authorization: deny
Hard-delete retention: 30 ngày
Access token: 15 phút
Refresh token: 30 ngày, rotation bắt buộc
API key: có expiry và rotation, chỉ lưu hash
MCP: explicit assignment, runtime re-check, audit bắt buộc
```

