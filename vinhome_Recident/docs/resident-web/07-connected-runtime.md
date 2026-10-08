# Chạy Resident và Operations với backend V3

## Chế độ kết nối

Đọc [hướng dẫn đăng nhập thật](../../docs/teams/chien/CHAY_DANG_NHAP_THAT.md) để chuẩn bị database, tổ chức, tài khoản, backend và dịch vụ agent. Có launcher [CHAY_KET_NOI_THAT.cmd](../../services/CHAY_KET_NOI_THAT.cmd). Tài khoản local nằm trong cấu hình ignored, không đưa mật khẩu vào tài liệu/Git.

Từ repository root, sau khi cài dependencies:

```powershell
npm run dev:resident
npm run dev:operations
```

Chạy mỗi frontend trong một terminal. Chế độ đăng nhập thật dùng `VITE_ALLOW_DEMO_BACKEND=false`; không chọn tài khoản preview để xác thực.

| Bề mặt | Địa chỉ development |
|---|---|
| Resident | `http://127.0.0.1:3011/` |
| Operations | `http://127.0.0.1:3020/operations` |
| FastAPI / Swagger | `http://127.0.0.1:8000/docs` |

Hai Vite frontend proxy `/api/business/*` tới FastAPI8000 và bỏ prefix. Production cần gateway cùng origin cho cookie/session; Vite proxy không tự tồn tại trong built app. Xem [giới hạn triển khai](../../docs/teams/chien/REPO_RESEARCH_2026-10-04/FRONTEND_RUNTIME.md).

## Nguồn contract và cách kiểm

API đang chạy được sinh từ FastAPI tại `/openapi.json`; source ở `services/vinhomes-api/src/vinhomes_api/v3_*` và các module auth/runtime liên quan. Resident gọi `/resident/chats`, `/resident/tickets`, `/resident/approvals`; Operations gọi `/operations/me`, `/tickets`, `/work-orders` qua prefix proxy. Các URL trong proposal YAML cũ không được coi là endpoint đã mount.

Đăng nhập bằng tài khoản thật, thử một ticket từ cư dân tới BQL/nhân viên, phương án/đồng ý, bằng chứng/QC, cư dân xác nhận và BQL đóng. Kiểm ID, quyền và trạng thái từ backend, không dùng thành công của preview làm bằng chứng database. Tiêu chí agent/tool/retry/storage đầy đủ ở [checklist tích hợp](../../docs/teams/chien/SYSTEM_FLOW_AND_MAINTENANCE_2026-10-04/INTEGRATION_CHECKLIST.md).

Demo fixture chỉ dành cho development, xem [backend README](../../services/vinhomes-api/README.md). Không chạy setup/seed hoặc write-integration tests lên DB đang có dữ liệu vận hành. Preview và backend demo là hai chế độ khác nhau.
