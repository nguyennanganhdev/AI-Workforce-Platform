# App cư dân — tài liệu cần đọc

App hiện có chế độ kết nối backend và chế độ preview riêng. Các bộ đề xuất API/FE trước tích hợp đã được bỏ để tránh dùng nhầm endpoint và trạng thái mock cũ.

1. [Chạy Resident / Operations](07-connected-runtime.md).
2. [Luồng hệ thống](../../docs/teams/chien/SYSTEM_FLOW_AND_MAINTENANCE_2026-10-04/README.md).
3. [Giới hạn và trạng thái frontend đã kiểm](../../docs/teams/chien/REPO_RESEARCH_2026-10-04/FRONTEND_RUNTIME.md).
4. [Checklist nối backend/agent](../../docs/teams/chien/SYSTEM_FLOW_AND_MAINTENANCE_2026-10-04/INTEGRATION_CHECKLIST.md).

API chuẩn của runtime V3 lấy từ FastAPI `/openapi.json` và [backend README](../../services/vinhomes-api/README.md). `resident-api.openapi.yaml` còn là proposal cũ, không phải OpenAPI đang phục vụ. Không dùng ID, endpoint hoặc quyền trong dữ liệu preview làm contract production.
