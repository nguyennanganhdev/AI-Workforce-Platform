# async_capabilities — API/event/workflow v1.4

Chủ sở hữu: **Bùi Hữu Nghĩa**. Branch: `feat/wf-builder`.
Task bổ sung của owner: **BHN-12–BHN-14**; chọn phần tương ứng phạm vi folder dưới đây.

Đọc [kế hoạch triển khai](../../../../docs/workforce/KE_HOACH_TRIEN_KHAI.md) và [bàn giao cá nhân](../../../../docs/workforce/handoffs/bui-huu-nghia/README.md) trước khi code. Đặc tả chung nằm ở mục 17; ranh giới ownership ở 5.3 và task chi tiết trong phần mang tên owner. Các đường dẫn link tính từ folder này.

Phạm vi: Create-only vs tracking, fake ports và chống sinh workflow lúc build.

File dự kiến khi triển khai: `test_requirements.py`, `test_reuse.py`. Đây chỉ là gợi ý chia file; chưa có code được tạo trong folder.

Nguyên tắc triển khai:

- Một role AREA_MANAGER, Scope đủ tenant/domain/area/manager và audience cư dân; không route theo payload tự khai.
- Dùng DTO/ports chung; không import private service hoặc ghi bảng module khác. uow đi xuyên inbox → workflow/event → job/delivery khi cần atomicity.
- POST/ACK kết thúc request mạng; workflow tiếp tục qua nhiều event. Checkpoint/chờ không giữ model chạy; callback không tự đóng ticket hoặc thay approval.
- Tự viết test trong vùng test được giao, dùng fake port khi module khác chưa có. Chỉ đánh dấu live integration khi có bằng chứng thật.
- Cần đổi contract/migration/core/global frontend thì ghi INTEGRATION_REQUEST trong handoff; Chí Hoàng tích hợp file chung.

Thư mục được giữ trong Git bằng README này để thành viên bắt đầu code song song. Chưa triển khai API, worker, migration hay test; không tạo stub thành công trong production.
