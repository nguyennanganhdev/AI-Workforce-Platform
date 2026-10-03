# Dùng thử Vinhomes API trong Swagger

## Demo mock đã sẵn sàng

Chạy `& ./services/vinhomes-api/scripts/setup_demo_database.ps1`, rồi `& ./services/vinhomes-api/scripts/start_demo.ps1` tại thư mục dự án, mở **http://localhost:8000/docs**. Chọn `X-Demo-Actor` để đổi vai trò. Demo dùng PostgreSQL V3 có dữ liệu faker. Xem [hướng dẫn đầy đủ](vinhomes-api/HUONG_DAN_DEMO_DATABASE_V3.md).

## Chạy service

Áp dụng migration trong `server/drizzle`, chuẩn bị database V3 và role có quyền
đọc/ghi các bảng nghiệp vụ. Không chạy Alembic `vh_*` cũ trên database V3.

Trong PowerShell, tại `services/vinhomes-api`:

```powershell
python -m pip install -e .
$env:VINHOMES_API_DATABASE_URL = "postgresql+asyncpg://USER:PASSWORD@HOST:PORT/DATABASE_V3"
$env:VINHOMES_API_TENANT_ID = "UUID_TENANT_V3"
$env:VINHOMES_API_AUTH_URL = "http://127.0.0.1:3001/api/me"
python -m vinhomes_api
```

Khi thử cục bộ trên `127.0.0.1`, có thể đặt
`VINHOMES_API_DEV_USER_ID` bằng ID của user V3 đang hoạt động thay cho
`VINHOMES_API_AUTH_URL`. Cấu hình này bị từ chối nếu service bind ra mạng.

Mở **http://localhost:8000/docs**. Bấm **Try it out** và **Execute** ở từng
endpoint. Kiểm tra `GET /health`, rồi `GET /ready` trước khi thử nghiệp vụ.

## Các nhóm API

| Nhóm | Endpoint chính |
|---|---|
| Danh mục và dashboard | `GET /catalogs`, `GET /dashboard` |
| Tòa nhà và ban quản lý | `GET /management-units/resolve?buildingId=...&domainId=...` |
| Ticket | `GET /tickets`, `POST /tickets`, `GET /tickets/{ticket_id}`, `PATCH /tickets/{ticket_id}/status`, `GET /tickets/{ticket_id}/timeline` |
| Triage | `GET /tickets/{ticket_id}/triage`, `POST /tickets/{ticket_id}/assessments`, `POST /tickets/{ticket_id}/triage-decisions`, `GET /triage-reviews`, `POST /triage-reviews/{review_id}/decision` |
| Công việc | `GET /tasks`, `GET /my-work-orders`, `GET /work-orders`, `POST /tickets/{ticket_id}/work-orders`, `PATCH /work-orders/{work_order_id}/status`, `POST /work-orders/{work_order_id}/assignments`, `POST /assignments/{assignment_id}/response` |
| Phê duyệt | `GET /approvals`, `POST /approvals/{approval_id}/decision`, `GET /budget-approvals`, `POST /work-orders/{work_order_id}/budget-approvals`, `POST /budget-approvals/{approval_id}/decision` |
| Chứng cứ | `GET /tickets/{ticket_id}/files`, `POST /tickets/{ticket_id}/files`, `GET /files/{file_id}/content`, `GET /tickets/{ticket_id}/evidence`, `POST /tickets/{ticket_id}/evidence` |
| Hiện trường | `GET/POST /work-orders/{work_order_id}/qc`, `POST /work-orders/{work_order_id}/redo`, `GET/PUT /work-orders/{work_order_id}/cleaning-plan`, `GET/PUT /work-orders/{work_order_id}/contractor`, các route `/security/*` |

Một số lệnh ghi yêu cầu `version` hoặc `ticketVersion` từ kết quả GET gần nhất.
HTTP 409 cho biết dữ liệu đã đổi hoặc trạng thái không còn hợp lệ; tải lại bản ghi
trước khi gửi tiếp. HTTP 403 cho biết user không có quyền ở phạm vi đó.

## Dữ liệu mẫu Docker V3

- `domainId`: `22222222-2222-5222-a222-222222222222`
- `buildingId`: `77777777-7777-5777-a777-777777777777`
- `managementUnitId` mong đợi: `88888888-8888-5888-a888-888888888888`
- Ticket mẫu: `44444444-4444-5444-a444-444444444444`
- Work order mẫu: `55555555-5555-5555-a555-555555555555`

`POST /tickets/{ticket_id}/files` dùng raw body là bytes ảnh. Route upload này chỉ
dành cho Docker local với `VINHOMES_API_DEV_USER_ID`, lưu ảnh trong thư mục
`.local-v3-files` đã được Git bỏ qua. Môi trường triển khai thật cần dịch vụ lưu
trữ đối tượng và quét tệp trước khi bật upload.
