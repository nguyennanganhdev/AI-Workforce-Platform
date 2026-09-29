# Nhà — Resident app

Ứng dụng cư dân độc lập với `app/` (nhân viên). React/Vite, ưu tiên điện thoại,
hai tab Trợ lý và Tiện ích. Không import mã từ app nhân viên hoặc backend.

## Bàn giao cho đội backend

Bắt đầu tại **[docs/README.md](docs/README.md)**. Bộ tài liệu gồm nghiệp vụ,
mapping ERD, API đề xuất có ví dụ payload, OpenAPI cho flow cốt lõi và checklist
tích hợp/nghiệm thu. Đây là thiết kế đề xuất để FE/BE thống nhất; không phải API
đã triển khai. Router Vinhomes hiện vẫn là scaffold.

## Chạy

Tại repo root: `bun install --frozen-lockfile`, sau đó `bun run dev:resident`.
Mở http://localhost:3011. App nhân viên dùng `bun run dev:operations` ở cổng 3020;
OpenBot dùng `bun run dev:openbot` ở cổng 3010.

- `bun run build:resident`: typecheck và build vào `resident-app/dist`.
- `bun run test:resident`: kiểm tra luồng dữ liệu cư dân.
- `bun run --cwd resident-app typecheck`: kiểm tra TypeScript riêng.

`scripts/browser-smoke.ts` kiểm thử qua Chrome DevTools Protocol, không thêm dependency.
Chạy Chrome với profile tạm riêng, `--headless=new --remote-debugging-port=9333`,
mở `http://127.0.0.1:3011`, rồi từ repo root chạy `bun resident-app/scripts/browser-smoke.ts`.
Script đặt lại key dữ liệu demo trong profile kiểm thử; không chạy trên profile cá nhân.
Ảnh kiểm chứng nằm ở `.logs/resident-*.png` (không commit).

## Phạm vi hiện tại

- Giao diện [đăng nhập, đăng ký và quên mật khẩu](src/features/auth/README.md) riêng cho cư dân:
  `/#/login`, `/#/register`, `/#/forgot-password`. Validation có sẵn, auth backend chưa kết nối.
- Chat theo kịch bản: hỏi thông tin, lập phản ánh, hỏi vị trí, ảnh, xác nhận trước khi gửi.
- Danh sách, tìm kiếm, lọc và chi tiết yêu cầu; timeline, xác nhận hoàn tất hoặc yêu cầu xử lý lại.
- Thông báo phát sinh từ cùng nguồn dữ liệu yêu cầu.
- Trang tiện ích, tài khoản/căn hộ, thông tin tòa nhà và danh mục tiện ích minh họa.
- Hash routing hỗ trợ deep link và nút Back của trình duyệt trên static hosting.
- Giao diện mobile có safe areas, chiều cao visual viewport khi mở bàn phím, hai tab cố định.

Chưa kết nối AI/backend/BQL. Hồ sơ là dữ liệu mẫu. Adapter lưu browser localStorage
theo key `nha.resident.demo.v1`. Ảnh JPG/PNG/WebP tối đa 10 MB đầu vào và 3 ảnh/phản ánh;
tự thu nhỏ tối đa 1280 px và nén JPEG dưới 600 KB trước khi lưu.
Quota error được hiển thị, không thông báo gửi thành công khi chưa lưu được.
Không dùng localStorage làm persistence/authorization production. Không nhập thông tin nhạy cảm vào demo.

## Ranh giới tích hợp

- `src/services/resident-service.ts`: thay bằng API authenticated khi tích hợp BE.
- `src/services/types.ts`: view model cư dân; không đồng nhất ResidentRequest với Incident.
- `src/features/assistant`: hội thoại và composer; không trực tiếp ghi dữ liệu.
- `src/features/requests`: danh sách, chi tiết và xác nhận kết quả.
- `src/features/utilities`: trang tổng hợp và các mục còn lại.
- `src/app/App.tsx`: điều hướng, state và commit qua adapter.

Khi nối BE, danh tính/căn hộ/quyền truy cập do server xác thực; bot chỉ hỗ trợ
soạn phản ánh. Endpoint tạo yêu cầu cần idempotency, kết quả tiếp nhận có ID chính thức,
ảnh tải lên storage và kiểm tra quyền theo cư dân/căn hộ. Danh mục, nội quy,
danh bạ và tiến độ phải đến từ dữ liệu được BQL công bố.

## Thiết kế

Coral `#FF9A7A → #FF7777` chỉ cho hero/brand; nền `#F5F5F5`, card trắng,
blue `#4169F5`, teal `#45C5C5`, orange `#FF8A3D` dùng có tiết chế.
`#8796AD` dành cho icon/trạng thái phụ; chữ phụ dùng màu đậm hơn để dễ đọc.
Không thêm tab điều hướng khi thêm trang tiện ích.
