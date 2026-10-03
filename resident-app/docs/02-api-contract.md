# 02 — API cư dân: contract đề xuất v0.1

**Chưa triển khai.** File [OpenAPI](resident-api.openapi.yaml) là bản thiết kế cốt lõi
đi kèm tài liệu này. API chính thức cần được FE/BE thống nhất rồi đưa về contract domain chung.

## 1. Quy ước

- Base path đề xuất: **`/api/domains/vinhomes/resident`**, compose dưới router Vinhomes
  đang được mount ở `server/src/app.ts`. Không tạo thêm alias `/api/resident` song song.
- JSON camelCase cho API; mapping sang schema SQL snake_case nằm ở backend.
- ID là opaque string do server cấp; client không parse ID để suy ra tenant/quyền.
- Thời gian RFC 3339 có timezone; lưu UTC, hiển thị giờ địa phương tại FE.
- Mọi endpoint trong tài liệu yêu cầu đăng nhập. Public health không cấp quyền resident API.
- Tái sử dụng session/auth hiện có; không thêm một tài khoản hardcode hoặc cơ chế login riêng cho demo.
- Server tạo `RequestContext { tenantId, actor, correlationId, traceId }` từ nguồn tin cậy.
  `apartmentId` trong payload chỉ là lựa chọn cần kiểm quyền, không phải bằng chứng quyền.
- Với session cookie: FE dùng `credentials: 'include'`; cấu hình CORS origin cụ thể,
  credentialed requests và chống CSRF trên mutation. Triển khai cùng origin qua reverse proxy
  là lựa chọn đơn giản; local có thể dùng Vite proxy, hiện resident-app chưa cấu hình proxy.
- Tên cookie thực tế phải lấy từ cấu hình Better Auth/deployment. Tên trong OpenAPI là
  tên logic thông thường, không được hardcode token hay đọc HttpOnly cookie bằng JavaScript.

## 2. Endpoint P0

Tất cả path trong bảng tính từ base path ở trên.

| Method/path | Chức năng | Thành công |
|---|---|---|
| `GET /me` | Danh tính, các căn hộ có quyền, giới hạn upload | 200 |
| `POST /photos` | Upload một ảnh, trả file ID sẵn sàng | 201 |
| `GET /requests` | Danh sách hồ sơ của caller | 200 |
| `POST /requests` | Tiếp nhận một hồ sơ từ draft đã xác nhận | 201 |
| `GET /requests/{requestId}` | Chi tiết, public timeline, quyền thao tác hiện hành | 200 |
| `POST /requests/{requestId}/confirm` | Cư dân chấp nhận kết quả hiện hành | 200 |
| `POST /requests/{requestId}/reopen` | Yêu cầu kiểm tra lại từ bước chờ xác nhận | 200 |

`POST /requests`, `/confirm`, `/reopen` yêu cầu `Idempotency-Key`.
`POST /photos` cũng yêu cầu key để retry upload không tạo nhiều file orphan.

## 3. Hồ sơ hiện tại

`GET /me`:

```json
{
  "user": { "id": "usr-resident-01", "displayName": "Minh An" },
  "apartments": [
    {
      "id": "apt-s202-1208",
      "label": "S2.02 · 1208",
      "projectId": "prj-smart-city",
      "projectName": "Vinhomes Smart City",
      "towerId": "tower-s202"
    }
  ],
  "limits": {
    "maxPhotosPerRequest": 3,
    "maxPhotoBytes": 10485760,
    "allowedPhotoTypes": ["image/jpeg", "image/png", "image/webp"]
  }
}
```

Các ID/tên trong ví dụ chỉ minh họa, không dùng làm seed production.
`apartments: []` là trạng thái hợp lệ: FE thông báo chưa có căn hộ được liên kết và không
cho gửi phản ánh, không tự gán căn hộ mẫu. V1 chưa có API đổi căn hộ mặc định;
FE giữ lựa chọn UI trong số căn hộ server trả về, kiểm tra lại khi mutation.

## 4. Upload ảnh

### Request

`POST /photos`, `multipart/form-data`:

| Field/header | Bắt buộc | Mô tả |
|---|---|---|
| `file` | Có | Một file JPG/PNG/WebP, tối đa 10 MiB |
| `apartmentId` | Có | Căn hộ trong scope caller |
| `Idempotency-Key` header | Có | Một key mới cho mỗi file logic |

FE hiện thu nhỏ tối đa 1280 px và nén JPEG dưới 600 KiB. Đây là tối ưu client,
không thay thế validation server. P0 giữ 3 ảnh khi tạo một phản ánh.
Đề xuất giới hạn multipart envelope 12 MiB, giới hạn riêng phần file 10 MiB;
không áp dụng chung body limit JSON cho endpoint upload.

### Response 201

```json
{
  "id": "file-01",
  "name": "ro-nuoc.jpg",
  "url": "https://files.example.test/read/file-01?signature=example",
  "urlExpiresAt": "2026-10-01T03:15:00Z",
  "status": "ready"
}
```

- Server kiểm byte signature, decode ảnh, MIME, kích thước và giới hạn pixel; không tin
  extension/content-type client. Không nhận URL tùy ý rồi fetch vào hệ thống.
- Chỉ trả `ready` khi object và metadata đã ghi thành công, ảnh đáp ứng kiểm tra upload.
  Nếu chọn pipeline scan bất đồng bộ, cần bổ sung status/polling contract trước khi triển khai;
  không trả ready giả để giữ đúng shape.
- File metadata có tenant, owner, apartment/scope, kích thước, MIME, checksum thực tế,
  storage key nội bộ và thời hạn cleanup nếu chưa gắn hồ sơ.
- URL đọc ngắn hạn/private; gọi lại chi tiết yêu cầu để nhận URL mới. Không log query token.
- File ID người khác, tenant khác, sai căn hộ, đã bị xóa/quarantine hoặc đã bind không hợp lệ
  không được gắn vào hồ sơ.
- Tạo hồ sơ bind file ID trong transaction; client không gửi data URL/base64 vào JSON nghiệp vụ.
- Đề xuất cleanup file chưa bind sau 24 giờ; job không xóa file đã bind. Cần chốt thời hạn
  retention ảnh đã bind với owner vận hành trước production.
- Không ghép URL storage hoặc checksum giả như cơ chế demo nhân viên hiện tại.

## 5. Tạo hồ sơ

`POST /requests`, ví dụ header `Idempotency-Key: 74375a18-1327-4f25-a7e1-65ec14cd4d2a`:

```json
{
  "apartmentId": "apt-s202-1208",
  "description": "Vòi nước dưới bồn rửa bị rò, nước chảy ra sàn.",
  "location": { "description": "Bếp, dưới bồn rửa căn hộ 1208" },
  "photoIds": ["file-01"]
}
```

Validation đề xuất sau trim:

| Field | Rule |
|---|---|
| `description` | 8–5.000 ký tự; chat hiện giới hạn 2.000 mỗi tin, có thể bổ sung nhiều tin |
| `location.description` | 3–500 ký tự; chưa yêu cầu GPS |
| `apartmentId` | Tồn tại, active membership và đúng tenant; project/tower suy ra từ property |
| `photoIds` | 0–3 ID không trùng, ready và có quyền bind |

Không nhận `residentUserId`, `tenantId`, `status`, `assigneeId`, severity hoặc Incident ID
do cư dân tự gán. Title do server tạo từ mô tả, ngắn gọn, không phụ thuộc LLM.
Các field ngoài contract bị từ chối 422 để không vô tình cho phép mass assignment.

### Response chi tiết chuẩn

`POST /requests` trả 201 cùng DTO như `GET /requests/{id}`, header `Location` là path hồ sơ.

```json
{
  "id": "case-01",
  "code": "YC-2026-000123",
  "title": "Vòi nước dưới bồn rửa bị rò",
  "description": "Vòi nước dưới bồn rửa bị rò, nước chảy ra sàn.",
  "apartmentId": "apt-s202-1208",
  "location": "S2.02 · 1208 — Bếp, dưới bồn rửa căn hộ 1208",
  "status": "received",
  "createdAt": "2026-10-01T03:00:00Z",
  "updatedAt": "2026-10-01T03:00:00Z",
  "version": 1,
  "photos": [
    {
      "id": "file-01",
      "name": "ro-nuoc.jpg",
      "url": "https://files.example.test/read/file-01?signature=example",
      "urlExpiresAt": "2026-10-01T03:15:00Z"
    }
  ],
  "events": [
    { "id": "evt-01", "label": "Đã tiếp nhận phản ánh", "at": "2026-10-01T03:00:00Z" }
  ],
  "eventsNextCursor": null,
  "resolutionRevision": null,
  "resolution": null,
  "permissions": { "canConfirm": false, "canRequestRework": false }
}
```

Response bổ sung so với FE hiện tại: `code`, `apartmentId`, `updatedAt`, `version`,
event ID, `eventsNextCursor`, expiry ảnh, `resolutionRevision`, `resolution`, `permissions`.
FE cần cập nhật type/adapter và không bỏ mất version trước khi submit mutation.
`id` dùng điều hướng/API; `code` để hiển thị, không thay ID trong path bằng code.

## 6. Danh sách, chi tiết và timeline

`GET /requests?filter=open&q=ro%20nuoc&limit=20&cursor=...&apartmentId=apt-s202-1208`

- `filter`: `all` (mặc định), `open` (khác completed), `completed`.
- `q`: tùy chọn, tối đa 100 ký tự; tìm mã/nội dung trong scope caller.
- `limit`: mặc định 20, tối đa 50.
- `cursor`: opaque; sắp theo `(createdAt DESC, id DESC)`, không lấy cursor từ client làm SQL.
- `apartmentId`: lọc trong phạm vi được phép; không phải cách vượt quyền.

```json
{
  "items": [
    {
      "id": "case-01",
      "code": "YC-2026-000123",
      "title": "Vòi nước dưới bồn rửa bị rò",
      "status": "received",
      "createdAt": "2026-10-01T03:00:00Z",
      "updatedAt": "2026-10-01T03:00:00Z",
      "version": 1
    }
  ],
  "nextCursor": null
}
```

List dùng summary DTO để không tải ảnh/timeline của mọi hồ sơ. FE hiện dùng một type
cho cả list/detail nên cần tách `ResidentRequestSummary` và `ResidentRequestView`.
Không có `total` trong v0.1; số đếm từ trang đầu không được quảng bá là tổng toàn bộ.

`GET /requests/{id}` trả detail. Timeline chỉ gồm public event, thứ tự `(at ASC, id ASC)`.
P0 trả trang đầu tối đa 50 event và `eventsNextCursor`; tải tiếp bằng cùng endpoint
với `eventsCursor`. Các field khác vẫn là snapshot hiện hành; client append/de-duplicate
event theo ID, reset timeline nếu phát hiện hồ sơ version thay đổi giữa các trang.
Không trả raw audit, prompt hoặc ghi chú nội bộ làm timeline.

Polling P0: khi đang xem detail, refresh khoảng 15 giây lúc tab đang hiển thị và khi focus lại;
backoff khi lỗi/429, dừng khi logout. API chưa cam kết realtime. Sau command thành công,
dùng response mới và invalidate detail/list thay vì đợi poll.

## 7. Xác nhận và yêu cầu xử lý lại

Khi trả status `confirmation`, response phải có `resolutionRevision`, `resolution`
và permissions phù hợp. Ví dụ fragment:

```json
{
  "status": "confirmation",
  "version": 8,
  "resolutionRevision": "res-02",
  "resolution": {
    "summary": "Đã thay gioăng và kiểm tra, không còn rò nước.",
    "publishedAt": "2026-10-01T08:00:00Z",
    "photos": []
  },
  "permissions": { "canConfirm": true, "canRequestRework": true }
}
```

`POST /requests/case-01/confirm`:

```json
{ "expectedVersion": 8, "resolutionRevision": "res-02" }
```

`POST /requests/case-01/reopen`:

```json
{
  "expectedVersion": 8,
  "resolutionRevision": "res-02",
  "reason": "Sau khi mở vòi, nước vẫn bị rò ở khớp nối."
}
```

Cả hai trả 200 detail mới. Server kiểm quyền và trạng thái trong transaction.
`permissions` giúp FE hiển thị nút đúng; không thay thế authorization khi nhận command.
Reopen chỉ từ `confirmation` ở P0, đúng rule trong [tài liệu nghiệp vụ](01-business-and-data.md).

## 8. Retry, concurrency và tính nhất quán

- Key dài 8–128 ký tự; UUID là gợi ý cho FE. Một key đại diện một ý định/payload cố định.
- Unique scope idempotency: `(tenant, actor, operation, resource, key)`. Tạo hồ sơ/upload
  dùng resource scope tương ứng; key không dùng chung giữa hai actor.
- Hash payload canonical sau chuẩn hóa; upload hash bytes + apartmentId + tên file chuẩn hóa.
  Cùng key/cùng payload trả cùng status và body nghiệp vụ đã lưu; payload khác trả 409.
- Check auth và quyền đọc lại kết quả trước khi replay để không lộ dữ liệu khi bị thu hồi quyền.
- Với mutation đã replay được, trả response cũ trước khi áp dụng expectedVersion/state guard
  lần nữa; nếu không thì retry của một confirm thành công sẽ bị conflict sai.
- Command mới kiểm `expectedVersion`, revision kết quả và trạng thái trong cùng transaction;
  dùng conditional update/row lock. Tăng version khi có thay đổi business/public projection.
- Hai thiết bị confirm/reopen cùng version: chỉ một command có hiệu lực; bên còn lại nhận 409,
  tải snapshot mới và yêu cầu người dùng xem lại, không tự retry với version mới.
- Business state + public event + outbox + idempotency receipt commit nguyên tử.
- Object storage không chung transaction PostgreSQL: upload ở trạng thái chưa bind trước,
  bind metadata khi tạo Case; cleanup orphan bù cho lỗi. Không gọi vendor trong transaction dài.
- Consumer outbox deduplicate bằng event ID; retry không tạo nhiều notification hoặc Case.
- Đề xuất giữ idempotency receipt ít nhất 7 ngày. Cần chốt retention; không retry mù một
  command đã quá cửa sổ lưu receipt, phải đối soát hồ sơ trước khi tạo ý định mới.
- Replay có signed URL đã hết hạn: FE lấy lại detail để refresh URL; không coi URL là ID file.

## 9. Lỗi chuẩn

```json
{
  "error": {
    "code": "VERSION_CONFLICT",
    "message": "Yêu cầu đã được cập nhật. Vui lòng tải lại trước khi xác nhận.",
    "correlationId": "corr-01",
    "fieldErrors": {}
  }
}
```

| HTTP | Code gợi ý | FE xử lý |
|---|---|---|
| 400 | `BAD_REQUEST` | JSON hỏng/header bắt buộc thiếu; giữ draft |
| 401 | `UNAUTHENTICATED` | Đăng nhập lại; tránh vòng retry tự động |
| 403 | `APARTMENT_ACCESS_DENIED` | Không cho gửi theo căn hộ đó; refresh profile |
| 404 | `REQUEST_NOT_FOUND`, `PHOTO_NOT_FOUND` | Không tồn tại hoặc caller không được biết tài nguyên tồn tại |
| 409 | `VERSION_CONFLICT`, `INVALID_STATE`, `RESOLUTION_CHANGED` | Tải lại detail, giữ lý do đang gõ; người dùng quyết định lại |
| 409 | `IDEMPOTENCY_CONFLICT` | Không gửi lại payload mới bằng key cũ |
| 413 | `PAYLOAD_TOO_LARGE` | Giảm ảnh/dung lượng; không mất nội dung draft |
| 415 | `UNSUPPORTED_MEDIA_TYPE` | Yêu cầu đổi định dạng |
| 422 | `VALIDATION_ERROR`, `PHOTO_NOT_READY` | Hiển thị field errors; giữ dữ liệu form |
| 429 | `RATE_LIMITED` | Tôn trọng `Retry-After` |
| 503 | `SERVICE_UNAVAILABLE` | Hiển thị chưa hoàn tất; retry cùng key khi phù hợp |

Không trả 200 kèm success giả khi backend/storage hỏng. Message không chứa stack trace,
SQL, secret, membership của người khác. Phân quyền không dựa vào ID khó đoán.

## 10. API P1 — cần thiết kế thêm, chưa nằm trong OpenAPI cốt lõi

| Endpoint dự kiến | Mục đích và lưu ý |
|---|---|
| `GET/POST /requests/{id}/messages` | Trao đổi công khai sau khi gửi; message actor do server gán, phân trang, ảnh có quyền, POST có key |
| `GET /notifications`, `POST /notifications/{id}/read` | Feed durable/read state theo người nhận; không lấy toàn bộ event nội bộ |
| `GET /building-info?apartmentId=...` | Danh bạ/nội quy/giờ làm việc do BQL công bố |
| `GET /amenities?apartmentId=...` | Danh mục; chưa bao gồm booking/payment |
| Conversation/message transport cho chatbot | Chốt reuse channel/AG-UI hay adapter khác, thread ownership, lưu lịch sử, timeout, cancellation |

API chat không được biến mọi lời nói thành mutation. Tool tạo phản ánh phải đi qua
review/explicit submit và cùng service/domain guard như giao diện form.
Kết quả tool/knowledge là dữ liệu không tin cậy; không được dùng để thay actor/scope.
Không đặt provider key trên trình duyệt. P0 có thể giao được mà chưa cần tích hợp LLM.
