# Kế hoạch Platform mở cho mọi người dùng (19/10/2026)

Nhánh làm việc: `feat/open-platform-20261019` (worktree `E:\AI-Workforce-Platform-open`).

## Mục tiêu

Ai cũng đăng ký được và có một không gian riêng. Trong đó, người dùng tự gắn gói (Travelling, Vinhomes) hoặc MCP của riêng mình, tự dựng đội agent bằng Builder, rồi chat với Leader. Các agent tự phối hợp, tự hỏi và tự phản biện nhau.

Vinhomes là **một gói có liên kết tài khoản**. Domain Vinhomes, app nhân viên và database của Domain giữ nguyên.

## Quyết định của PM ngày 19/10

| # | Quyết định |
|---|---|
| Q1 | Nền code: `dev_Chien` (vai trò VIN_USER, đăng ký cá nhân, hạn mức, admin, liên kết Vinhomes) gộp với develop2 và PR #103 (đang chạy trên VPS), rồi đưa runtime phối hợp của `Dongg_dev` vào. |
| Q2 | `Dongg_dev` và `dev_Chien` tạm dừng nhận commit cho tới khi nhánh gộp xong. |
| Q3 | Tool tìm kiếm và đọc dữ liệu tự chạy. Đặt chỗ, hủy và thanh toán hiện thẻ xác nhận cho người dùng. |
| Q4 | Tài khoản tự đăng ký dùng được ngay, với hạn mức token mặc định do admin đặt. Admin có thể khóa hoặc chỉnh sau. |

## Các bước

| Bước | Nội dung | Nguồn | Kiểm chứng |
|---|---|---|---|
| 0 | Gộp `fix/eval-gate-20261019` vào `dev_Chien` (13 file xung đột) | develop2, PR #103 | Bộ test console, workforce, frontend |
| 1 | Runtime phối hợp nhóm: Leader khởi động một agent; các agent tự hỏi nhau, câu trả lời về đúng người hỏi; agent tự hỏi khách khi thiếu thông tin; Leader chỉ khép việc và tổng hợp. Đưa sang cả UI hoạt động nhóm. Bỏ phần JEV. | `Dongg_dev` (khoảng 25 file lõi) | Test của Đông cùng test hiện có; phiếu đối tác Vinhomes vẫn chạy |
| 2 | Chính sách xác nhận Q3: tool có tên hoặc tham số nhạy cảm (book, cancel, pay…) hiện thẻ; tool khác tự chạy. Không còn ép xác nhận chỉ vì thiếu `readOnlyHint`. | Sửa trên nền | Test chính sách quyền |
| 3 | Đăng ký chung: bỏ hai mục khu và domain khỏi trang đăng ký. Tài khoản mới là người dùng cá nhân, dùng ngay, nhận hạn mức mặc định. Admin quản lý người dùng và hạn mức. | `dev_Chien` (`register_personal`, C03, trang admin) | Test auth, quota, admin |
| 4 | MCP riêng: người dùng thêm, đồng bộ và xóa MCP của mình (chỉ chủ sở hữu thấy). MCP của gói và của domain vẫn chỉ được xem và dùng. | Mở lại hành vi gốc, giới hạn theo chủ sở hữu | Test cách ly giữa người dùng |
| 5 | Thư viện gói. Travelling gồm MCP, đội agent mẫu (điều phối, chuyến bay, lưu trú, ăn uống, tham quan) và bộ eval. Vinhomes gồm MCP Domain, liên kết tài khoản và đội mẫu. Người dùng bấm "Thêm gói" để cài vào không gian của mình. | Mới, dựa trên catalog của `dev_Chien` | Test cài gói, dựng đội mẫu |
| 6 | Dọn giao diện: bỏ chữ "cư dân" và "ban quản lý" khỏi các màn hình chung; giữ ở những màn hình riêng của gói Vinhomes. | Frontend | Rà chuỗi i18n, chụp ảnh màn hình |
| 7 | Deploy lên VPS: sao lưu trước, migration và cờ tính năng, kiểm tra trên UI | Script release | Bản ghi phát hành |

## Ràng buộc

- Không dùng key model để test; PM tự test trên UI.
- Phiếu đối tác Vinhomes (Leader của ban quản lý) phải tiếp tục chạy trong suốt quá trình.
- Không động vào các worktree `-user1` và `-user2` của phiên khác.
