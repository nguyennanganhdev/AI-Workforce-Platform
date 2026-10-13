# API Area Platform: đăng ký, đối tác, ticket và memory có kiểm duyệt

## 1. Phạm vi triển khai

Phiên bản hiện tại chưa có admin. Mỗi người dùng tự đăng ký, chọn một domain và
một area, sau đó được tạo với role cố định `AREA_MANAGER`.

API key của đối tác thuộc **domain**, không thuộc tài khoản manager. Ticket thuộc
**area**, không thuộc riêng người tạo tài khoản. Vì vậy mọi `AREA_MANAGER` đang
active trong cùng area đều nhìn thấy hàng đợi ticket của area đó.

## 2. Chuẩn bị

Chạy migration:

```bash
python -m alembic \
  -c src/agentscope/app/storage/_sql/_alembic/alembic.ini upgrade head
```

Migration seed sẵn cho local:

```text
vinhomes
├── ocean-park-1
└── ocean-park-2

vinpearl
vinwonders
```

Đặt các biến bắt buộc:

```dotenv
AUTH_ENABLED=true
PARTNER_API_KEY_PEPPER=<random-secret-at-least-32-bytes>
PARTNER_API_PROVISIONING_SECRET=<random-secret-at-least-32-bytes>
```

Muốn duyệt và embedding memory cần cấu hình thêm:

```dotenv
MEMORY_EMBEDDING_API_KEY=<provider-key>
MEMORY_EMBEDDING_BASE_URL=
MEMORY_EMBEDDING_MODEL=text-embedding-3-small
MEMORY_EMBEDDING_DIMENSIONS=1536
```

## 3. Đăng ký Area Manager

Lấy domain và area hợp lệ:

```http
GET /directory/domains
GET /directory/domains/vinhomes/areas
```

Đăng ký:

```http
POST /auth/register
Content-Type: application/json

{
  "email": "manager.op1@example.com",
  "username": "manager_op1",
  "password": "a-long-random-password",
  "domain_id": "vinhomes",
  "area_id": "ocean-park-1"
}
```

Backend không chấp nhận `area_id` không thuộc `domain_id` đã chọn.

> Public self-registration vào role `AREA_MANAGER` chỉ phù hợp cho giai đoạn
> nội bộ/thử nghiệm. Trước khi public Internet cần invitation hoặc xác minh ban
> quản lý; nếu không, bất kỳ người nào cũng có thể tự nhận một area.

## 4. Cấp API key theo domain

Trong lúc chưa có admin, endpoint cấp key được bảo vệ bằng provisioning secret:

```http
POST /integrations/api-keys
X-Provisioning-Secret: <PARTNER_API_PROVISIONING_SECRET>
Content-Type: application/json

{
  "domain_id": "vinhomes",
  "name": "Vinhomes Mobile Production"
}
```

Plaintext API key chỉ xuất hiện trong response này. Database chỉ lưu HMAC hash.
Không nhúng key vào mobile/web client; key chỉ được giữ tại backend đối tác.

## 5. Đồng bộ căn nhà và area

Backend đối tác phải đồng bộ mapping trước khi chatbot tạo ticket:

```http
PUT /partner/residences/S1-0205
Authorization: ApiKey dp_<key-id>.<secret>
Content-Type: application/json

{
  "external_user_id": "resident-123",
  "area_id": "ocean-park-1",
  "status": "active"
}
```

Một cư dân có hai nhà sẽ có hai `residence_id`, mỗi bản ghi trỏ đến area tương
ứng. Platform kiểm tra area phải thuộc domain của API key.

## 6. Chatbot đối tác tạo ticket

```http
POST /partner/tickets
Authorization: ApiKey dp_<key-id>.<secret>
Content-Type: application/json

{
  "external_user_id": "resident-123",
  "residence_id": "S1-0205",
  "conversation_id": "conversation-789",
  "external_ticket_id": "vh-ticket-456",
  "title": "Thang máy gặp sự cố",
  "description": "Thang máy tòa S1 không hoạt động"
}
```

Platform không nhận `area_id` trong request tạo ticket. Backend tra mapping
`partner_app + external_user_id + residence_id`, suy ra `ocean-park-1`, kiểm tra
area có ít nhất một manager active rồi đưa ticket vào hàng đợi area đó.

## 7. Area Manager theo dõi tiến trình

Đăng nhập lấy JWT rồi gọi:

```http
GET /tickets?status=open
Authorization: Bearer <access-token>
```

Backend luôn lấy domain/area từ JWT, không lấy từ query hoặc header do client tự
khai báo.

Cập nhật trạng thái:

```http
PATCH /tickets/{ticket_id}/status
Authorization: Bearer <access-token>
Content-Type: application/json

{
  "status": "in_progress",
  "note": "Kỹ thuật viên đã tiếp nhận"
}
```

Đối tác xem tiến trình:

```http
GET /partner/tickets/{ticket_id}
Authorization: ApiKey dp_<key-id>.<secret>
```

## 8. Memory có kiểm duyệt

Tạo candidate chỉ lưu text, chưa embedding:

```http
POST /memories/candidates
Authorization: Bearer <access-token>
Content-Type: application/json

{
  "content": "Hotline kỹ thuật Ocean Park 1 là ...",
  "source_type": "ticket",
  "source_id": "<ticket-id>"
}
```

Xem hàng đợi:

```http
GET /memories/candidates?status=pending_review
Authorization: Bearer <access-token>
```

Chỉ khi duyệt endpoint sau mới gọi embedding provider và ghi pgvector:

```http
POST /memories/candidates/{candidate_id}/approve
Authorization: Bearer <access-token>
```

Từ chối không tạo vector:

```http
POST /memories/candidates/{candidate_id}/reject
Authorization: Bearer <access-token>
Content-Type: application/json

{
  "reason": "Thông tin chưa được xác minh"
}
```

Tìm kiếm chỉ đọc memory `active`, đã duyệt và đúng domain/area:

```http
GET /memories/search?query=hotline%20kỹ%20thuật
Authorization: Bearer <access-token>
```
