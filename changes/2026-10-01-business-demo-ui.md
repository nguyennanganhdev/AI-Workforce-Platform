# Giao diện nghiệp vụ demo V3

- Ngày: 2026-10-01
- Yêu cầu: giao diện người dùng thay console endpoint/JSON; file CMD nằm trong `services`.

## Thay đổi

- `/demo/ui` phục vụ màn hình nghiệp vụ với chọn vai trò, điều hướng, bảng, form và dialog.
- Cư dân: chat, gửi yêu cầu, theo dõi và xác nhận; BQL: tiếp nhận, assessment/triage, tạo việc/phân công/phê duyệt; nhân viên: nhận/từ chối, tiến độ, ảnh, khóa nước.
- Có QC/redo, vệ sinh, nhà thầu, ngân sách, an ninh, phòng/mention, tri thức, thông báo, báo cáo Word và duyệt memory qua API hiện có.
- ID/version lấy từ dữ liệu server, không nhập thủ công; không có business mock/localStorage, không tự retry ghi.
- CMD được chuyển từ gốc vào `services/CHAY_DEMO_API.cmd`, sửa đường dẫn tương đối. Launcher kiểm tra trang nghiệp vụ trước khi mở browser.

## File/module chính

- `services/vinhomes-api/src/vinhomes_api/demo_ui/business.*`: giao diện người dùng.
- `services/vinhomes-api/src/vinhomes_api/main.py`: phục vụ trang mới.
- `services/vinhomes-api/src/vinhomes_api/v3_demo.py`: bổ sung tên nhân viên, người duyệt và agent trong phòng cho dropdown demo.
- `services/CHAY_DEMO_API.cmd`, `services/vinhomes-api/scripts/launch_demo.ps1`: khởi động.
- `services/vinhomes-api/scripts/seed_v3_demo_ui.sql`, `prepare_demo_database.py`: bổ sung scope site cho BQL/bảo vệ tại site faker duy nhất; mode `ui` chỉ thêm fixture quyền, không seed lại nghiệp vụ. Launcher áp dụng idempotent cho database demo cũ.
- `my-docs/HUONG_DAN_GIAO_DIEN_NGUOI_DUNG_DEMO.md`: hướng dẫn nghiệp vụ.

## Quyết định & giả định

- Giữ URL/cổng và database demo; không đổi luật quyền hoặc schema nghiệp vụ.
- UI độc lập để mở bằng CMD; frontend sản phẩm chưa bị thay thế.
- Không thêm dependency hoặc test. Chức năng chưa có endpoint trong kế hoạch V3 vẫn chưa khả dụng.

## Xác minh

- Đọc contract route hiện có để ánh xạ form, kiểm tra syntax JS bằng `node --check`.
- `git diff --check` và PowerShell parser của launcher: thành công.
- Đã chạy lại FastAPI: `/demo/ui` trả 200 và phục vụ trang business; `/ready` trả ready/v3; fixtures vai trò BQL trả 1 người duyệt và 2 agent trong phòng.
- Đã áp dụng fixture scope site cho database cục bộ bằng mode `ui`, giữ nguyên dữ liệu nghiệp vụ; GET checkpoints với vai trò bảo vệ truy cập được site demo.
- Chưa kiểm chứng trực quan trên browser hoặc chạy lại các luồng ghi nghiệp vụ.

## Rủi ro / việc còn lại

- Các danh sách tối đa 100 bản ghi, phạm vi demo cục bộ.
- Cần seed đầy đủ nếu muốn demo các dữ liệu hiện chưa có như tri thức/memory.
