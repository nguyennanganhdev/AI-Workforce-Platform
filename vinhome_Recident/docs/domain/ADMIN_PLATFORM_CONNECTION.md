# Kết nối Platform từ quản trị Domain

Trang `/operations/platform-connection` dành riêng cho quản trị viên hệ thống. BQL, staff và cư dân không được đọc, sửa hoặc xuất khóa kết nối.

## Thao tác của quản trị viên

1. **Bàn giao MCP:** tải bộ kết nối riêng tư, cung cấp cho người vận hành Platform. ZIP có endpoint Streamable HTTP, danh sách 7 tool, token khởi tạo và cấu hình endpoint cấp grant. Người vận hành Platform đăng ký MCP và cấu hình Agent theo `deploy/platform/vinhomes-declaration.json`. Biến `${VINHOMES_MCP_TOKEN}` trong JSON là tham chiếu: client phải nạp giá trị từ file secret, không gửi nguyên chuỗi đó như token.
2. Platform cấp lại URL gốc, Customer key, Provider key, Signing key ID/secret và tuyến chờ xác nhận cho từng mã đơn vị quản lý.
3. **Cấu hình kết nối:** nhập và lưu thông tin. Để trống ô key giữ nguyên giá trị cũ. GET chỉ trả cờ đã cấu hình; dữ liệu secret được mã hóa bằng Fernet trong PostgreSQL.
4. **Kiểm tra kết nối:** chỉ đọc hai API bằng Customer/Provider key, không gọi Agent, tạo session hoặc gửi sự kiện giả. `404 RESOURCE_NOT_FOUND` cho một mã ngẫu nhiên chứng minh API đã đi qua xác thực; HTML/404 không đúng contract, 401/403 hoặc lỗi mạng đều không được coi là đạt. Signing secret mới được kiểm tra có cấu hình; chữ ký HMAC và luồng nghiệp vụ vẫn cần nghiệm thu thực tế.
5. **Tuyến đơn vị:** nhập Route ID và revision chờ xác nhận Platform cấp. Domain gọi API confirm; Platform tăng revision sau xác nhận và UI lưu revision trả về. API này dùng tuyến đang chờ xác nhận, không phải chức năng nhập lại một tuyến đã active từ hệ thống cũ. Với tuyến cũ, người vận hành Platform cần cấp tuyến chờ xác nhận phù hợp trước khi chuyển sang cấu hình UI.
6. **Bật kết nối:** chỉ bật khi có ít nhất một tuyến xác nhận, MCP sẵn sàng và kiểm tra hai khóa đạt. Chỉ các đơn vị đã xác nhận tuyến được bàn giao ticket mới. Không thêm bước BQL duyệt tiếp nhận.

API áp dụng cấu hình UI theo tenant ngay trong transaction. Worker đọc lại cấu hình mỗi vòng, không cần khởi động lại. Trạng thái worker xác nhận phiên bản đã nạp, không phải chứng minh một workflow đã nghiệm thu. Khi còn workflow mở, hệ thống chặn tắt, đổi URL hoặc đổi khóa để giữ đúng hệ thống đang xử lý. Thay URL hoặc Customer key khi không có workflow mở sẽ yêu cầu xác nhận lại tuyến.

## Thiết lập máy chủ một lần

- Migration `0019_platform_connection.sql` và cấp lại quyền bằng `python -m vinhomes_api.database role --role vinhomes_api`.
- API và worker dùng cùng `VINHOMES_API_CONFIG_ENCRYPTION_KEY`: 32 byte ngẫu nhiên dạng hex (64 ký tự). `new-env.ps1` / `new-env.sh` sinh khóa cho triển khai mới. Giữ khóa ổn định và sao lưu riêng cùng cấu hình; mất khóa không khôi phục được credentials trong DB. Không dùng token MCP làm khóa mã hóa.
- URL công khai dùng HTTPS; endpoint gốc không kèm `/workforce/v1`. Chỉ host nội bộ khai báo trong `VINHOMES_PLATFORM_ALLOWED_HOSTS` được phép dùng HTTP/mạng riêng. Mặc định có `awp-platform` và `host.docker.internal`. Loopback, địa chỉ metadata và DNS công khai trỏ về mạng riêng chưa được cho phép bị từ chối. Không theo redirect khi gửi khóa.
- Compose phải chạy `python -m vinhomes_api.platform_sync` cả khi URL env trống; worker chờ cấu hình UI thay vì `sleep infinity`.
- Khi chưa có bản ghi UI, cấu hình env cũ vẫn được dùng. Sau lần lưu UI đầu tiên, DB là nguồn cấu hình của tenant, kể cả khi tắt kết nối. CLI `platform status` đọc cùng cấu hình DB khi có `DATABASE_URL`.
- MCP bootstrap vẫn là secret của máy chủ (`VINHOMES_API_PLATFORM_MCP_TOKEN`), không bị đổi khi sửa URL/khóa Platform. Việc xuất bộ MCP ghi audit riêng, trả `Cache-Control: no-store`.

## Tổ chức UI

Không gian làm việc: Tổng quan, Yêu cầu, Báo cáo. Nhóm Quản trị: Tài khoản, Đơn vị quản lý, Kết nối Platform, Nhật ký. Giao diện cũ cũng có đường vào Tổng quan và Kết nối Platform. Trang kết nối chia ba tab, có trạng thái tải/lỗi, kiểm tra khóa, cảnh báo thay đổi chưa lưu, version conflict và nút tải cấu hình riêng tư. Không hiển thị secret đã lưu hoặc nhầm trạng thái bật cấu hình với thành công nghiệp vụ.

Kiểm thử tự động dùng database cô lập và HTTP Platform giả. Kiểm tra UI production chỉ dùng tài khoản admin, giữ kết nối tắt; không chạy Agent thật.

## Nghiệm thu ngày 14/10/2026

- PostgreSQL cô lập: **116 pass**, gồm cấu hình admin, bridge, MCP v2 và hồi quy admin. Frontend: **11 pass** (4 bài mới, 7 bài admin hiện có), typecheck và build đạt theo package-lock của dự án.
- VPS: **15 kiểm tra UI** tại 375/1440 px, gồm ba tab kết nối, Tổng quan, Tài khoản, Đơn vị quản lý, Nhật ký và điều hướng giao diện cũ. Không tràn ngang, không có JavaScript exception. BQL bị chặn trang cấu hình; staff được đưa về Việc của tôi; API đều từ chối quyền đọc cấu hình.
- Đã lưu cấu hình đang tắt qua UI, giữ nguyên khóa hiện có; worker xác nhận phiên bản đã nạp. Nút xuất bộ MCP tải được ZIP; MCP công khai trả 200 và đủ 7 tool. Không gọi Agent hoặc tạo ticket thật trong đợt này.
- Docker API/worker/scheduler và staff/admin: tag `admin-platform-20261014-290b3cb9929d`. Đã đối chiếu 105 file source API đang chạy và bytes HTML frontend được phục vụ với artifact. Database/config được sao lưu trước cập nhật; có bản cấu hình sau cập nhật giữ khóa mã hóa mới. Container database kiểm thử riêng đã được gỡ, volume production giữ nguyên.
- Bằng chứng riêng: `deploy/test-accounts-20261013/domain-audit/platform-admin-ui/summary.json` và ảnh cùng thư mục (ignored). Release/backup trên VPS: `/opt/vinhomes/releases/admin-platform-20261014-290b3cb9929d/`. Bản khôi phục khóa mã hóa nằm ngoài Git ở `E:\Vinhomes-Deploy\admin-platform-20261014\config-recovery.secret.env`.
