# Cập nhật UX/UI domain Vinhomes, 14/10/2026

## Phạm vi và hướng thiết kế

Làm tại dự án chính, nhánh dev_Vinhome. Giữ logo Vinhomes và ảnh khu dân cư đã có; thống nhất landing, tài khoản, ứng dụng cư dân và nhận diện cổng vận hành. Nền sáng #faf9f6, chữ #293b46, màu thao tác #a34d35, font Manrope; chuyển động thấp, ưu tiên dễ đọc và dùng trên điện thoại. Giữ URL, phân quyền, nội dung pháp lý và các bước duyệt nghiệp vụ.

Audit trước sửa: landing dùng xanh đậm/Manrope; auth còn nhãn nhà./Inter; app cư dân pha màu coral và xanh. Thông báo frontend tự dựng từ ticket/chat, chưa đọc bảng delivery; chat không có thao tác xóa. Trạng thái chờ trả lời là một dòng chung, nguồn nằm trong footer văn bản, chưa có latency từng câu trả lời.

## Đã triển khai trong source

- Logo chuẩn trên đăng nhập, đăng ký, khôi phục mật khẩu, trạng thái tài khoản, chọn không gian và các shell cư dân/vận hành. Đồng bộ font, màu CTA/nền, focus và favicon; tăng vùng bấm trên mobile cổng vận hành. Chọn không gian cư dân đi đúng /resident.
- Chat có trạng thái từ backend: chờ xử lý, xem context, tra tài liệu, kiểm tra yêu cầu/tiến độ, chuẩn bị phản hồi, chờ bộ phận xử lý, phản hồi chậm hoặc chưa hoàn tất. Đồng hồ chờ dựa timestamp thật; latency phản hồi do runtime đo. Hoạt động chỉ gồm nhãn được cho phép, không lộ prompt, suy luận nội bộ, tham số công cụ hay credential.
- Trích dẫn có tiêu đề, đoạn nguồn, trạng thái tham khảo/đã xác nhận, mã văn bản và ngày hiệu lực khi có. Nguồn được chọn từ đúng lượt tra cứu; lịch sử cũ vẫn giữ footer. Có giờ gửi, trạng thái đã gửi/đã phản hồi và sao chép câu trả lời; không giả lập BQL đã đọc.
- Khi đọc lịch sử cũ, tin mới không kéo mất vị trí đọc; có nút đi tới tin mới. Giữ bản nháp khi gửi thất bại và khi polling.
- Trung tâm thông báo đọc delivery thật, lọc tất cả/chưa đọc, badge tổng số chưa đọc, đánh dấu một hoặc các mục hiển thị, tải thông báo cũ và mở đúng hội thoại/ticket. Trạng thái đọc lưu server; chỉ đánh dấu chat khi tab đang hiển thị và có focus. Reception tạo delivery chống trùng cho phản hồi mới.
- Xóa hội thoại có xác nhận, chuyển vào mục Đã xóa và khôi phục được; không xóa channel, ticket, tin nhắn hay bằng chứng. Archive chỉ áp dụng membership của chủ hội thoại, thao tác lặp an toàn. Ticket vẫn theo dõi được và có thể mở lại hội thoại liên quan.
- Poll nhanh chỉ tải phần tin nhắn mới và trạng thái lượt xử lý; overview được tái sử dụng tối đa 5 giây, tránh poll chồng nhau. Chat có card thay đổi trạng thái vẫn đọc lại để không giữ báo giá/booking cũ. Các lần đọc context/catalog/policy độc lập được chạy đồng thời; cập nhật hoạt động có timeout riêng để không làm mất phản hồi.
- Migration 0019_resident_experience thêm archived_at vào membership và resident_progress vào delegation; không thay dữ liệu ticket. API được kiểm tra bằng role không superuser/không bypass RLS.
- CI bổ sung contract UX; test DOM của từng ứng dụng chạy theo file riêng. GitHub Actions trên source triển khai3e7deed2 đã đạt cả3 job business-api/reception-cskh/frontend: [run38504852619](https://github.com/nguyennanganhdev/AI-Workforce-Platform/actions/runs/38504852619).

## Kiểm chứng trước deploy

| Kiểm tra | Kết quả |
|---|---|
| PostgreSQL/API, không provider | 40 passed; gồm archive/restore, ticket được bảo toàn, quyền, activity, citation, read receipt, idempotency và Reception contract cũ |
| Runtime adapter/CSKH offline | 12 passed; thêm kiểm tra HTTP turn lưu citations/latency, không gọi model thật |
| Resident UI | 41 passed / 10 file |
| Staff UI | 114 passed / 19 file |
| Hai frontend | Typecheck/build đạt |
| Trình duyệt tự động | 63 kiểm tra đạt; 320/375/390/768/1024/1440 px, logo, không tràn ngang, nguồn, latency, xóa/khôi phục, trạng thái đọc; không lỗi JavaScript |

Kiểm tra trình duyệt chat dùng API fixture, kiểm tra backend dùng PostgreSQL riêng. Không chạy full Agent/evals/provider hoặc gửi yêu cầu điều phối thật. Đây không phải benchmark latency model production; đã giảm công việc đọc lặp và bổ sung phép đo, chưa tuyên bố p50/p95 giảm bao nhiêu.

## Docker/VPS

Đã triển khai source `3e7deed2b4d6c05b27a1e5641f08810a63dce924` lên VPS103.238.235.156. Website: https://vinhome-platform.duckdns.org/.

- Bốn image API, Reception, resident và operations dùng tag `uxui-20261014-3e7deed2`; scheduler/platform-sync dùng API image mới. Bốn dịch vụ chính healthy. Đã áp migration0019; nguồn API/Reception và migration trong container khớp hash source commit.
- Hai HTML entrypoint cùng toàn bộ61 asset JS/CSS của hai bản build đã so byte qua HTTPS public: khớp. Đây là kiểm tra bản đang phục vụ từ Docker, không chỉ build local.
- Login cư dân, API thông báo, trạng thái lượt chat trống, xóa/khôi phục hội thoại trống do kiểm thử tạo: đạt. Chat test được đưa vào mục Đã xóa khi kết thúc; ticket của tài khoản test không thay đổi. Không gửi tin nhắn gọi Agent.
- Trình duyệt thật qua HTTPS kiểm tra landing/login/register và chat test ở390px: logo tải được, không tràn ngang, không lỗi JavaScript. Cổng vận hành đăng nhập bằng account test được kiểm tra ở320/375/768/1440px: không tràn ngang, không lỗi JavaScript. Screenshot có tên/email chỉ nằm trong folder audit ignored.
- Backup domain và PostgreSQL custom dump đã lưu trước release. Manifest image/hash/env trước release và rollback nằm ở `/opt/vinhomes/releases/uxui-20261014-3e7deed2/`, quyền private.
- Gateway, PostgreSQL, MinIO và backup không bị recreate; cấu hình provider/credential/bridge/HTTPS giữ nguyên. Các tag trong deployment.env local đã đồng bộ, secret vẫn ignored.
- Trước/sau release: users721,accounts16,memberships721,unit_residents690,tickets939,work_orders677,files33,knowledge_documents164,knowledge_chunks648. Login/test chat tạo session/channel theo nghiệp vụ; không tuyên bố mọi byte DB bất biến.
- PostgreSQL test riêng đã gỡ sau khi xác minh volume tách biệt production. Các thay đổi platform và việc xóa Caddyfile riêng của chủ dự án được giữ ngoài commit.


## Cần bổ sung sau

1. Stream nội dung trả lời nếu contract runtime được mở rộng; hiện nhận trạng thái qua polling, không giả gõ chữ hoặc hiển thị token stream không tồn tại.
2. Web Push/email/SMS cần kênh gửi và đăng ký thiết bị; bản này hoàn thiện thông báo trong ứng dụng, không hứa thông báo khi đóng trình duyệt.
3. Đổi tên hội thoại, tìm toàn văn lịch sử và phân trang/lazy-load các hội thoại rất dài nếu dữ liệu sử dụng tăng. Hiện tìm theo tiêu đề/preview.
4. Thu thập latency p50/p95, tỷ lệ fallback và chất lượng CSKH sau khi chủ dự án test Agent; chưa tự chạy eval/provider.
5. Dữ liệu dịch vụ chính thức, SMTP, adapter Platform thật và gia hạn HTTPS tự động là các phần riêng còn chờ như báo cáo MCP/CSKH trước; không được tính là hoàn tất bởi lần đổi UI này.
