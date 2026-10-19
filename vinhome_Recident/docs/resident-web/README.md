# App cư dân — tài liệu cần đọc

App hiện có chế độ kết nối backend và chế độ preview riêng. Các bộ đề xuất API/FE trước tích hợp đã được bỏ để tránh dùng nhầm endpoint và trạng thái mock cũ.

1. [Chạy Resident / Operations](07-connected-runtime.md).
2. [Nghiệp vụ Vinhomes](../domain/NGHIEP_VU_VINHOMES.md).
3. [Database của domain](../domain/SPEC_DATABASE_DOMAIN.md).

API chuẩn của runtime V3 lấy từ FastAPI `/openapi.json` và [backend README](../../services/vinhomes-api/README.md). Không dùng ID, endpoint hoặc quyền trong dữ liệu preview làm contract production.
