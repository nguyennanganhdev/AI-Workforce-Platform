# Telegram, Zalo OA và phiên thử của Leader

Ngày 18/10/2026. Thực hiện tại `E:\AI-Workforce-Platform-review`, nhánh `feat/review-plan-20261018`, tách từ `develop2@89c020c1`.

## Phạm vi và trạng thái

Đã triển khai code cho đợt I và phân tách phiên thử của Leader. Không push, merge, đổi cấu hình production hoặc deploy trong lần thực hiện này. Không dùng model/provider key, không gọi model/embedding thật và không gửi tin qua tài khoản Telegram/Zalo thật để kiểm thử.

Các thay đổi G/D/H được triển khai đồng thời trong worktree được giữ nguyên. Bản báo cáo này chỉ xác nhận hai hạng mục nêu trên; không thay thế nghiệm thu toàn bộ nhánh.

## Telegram

- Adapter `TelegramChannel`, nhận tin nhắn văn bản bằng Bot API long polling, trả lời qua `sendMessage`.
- Bot ID phải khớp phần số trong token; kiểm tra lại danh tính bằng `getMe` khi listener chạy.
- Hỗ trợ tin riêng, tin nhóm có gọi tên bot hoặc trả lời bot, allowlist người dùng và cuộc trò chuyện.
- Cursor được lưu trên message bus sau khi xử lý thành công từng update; lock phân tán bảo đảm một poller cho mỗi kênh.
- Lỗi kết nối tạm thời được thử lại với backoff. Lỗi webhook/poller cạnh tranh có thông báo hướng dẫn. Không tự xóa webhook Telegram đã có.
- Phê duyệt bằng nút Đồng ý/Từ chối. Nút chỉ chứa mã tham chiếu ngắn; dữ liệu công cụ, agent, session, chat và người yêu cầu được giữ ở server.
- Chỉ người yêu cầu hoặc approver cấu hình rõ ràng trong cùng chat được quyết định. Quyết định đi qua gate ASKING hiện có; pin session không được chuyển sang session khác khi yêu cầu đã hết hiệu lực.
- Token không xuất hiện trong phản hồi lỗi hoặc log request INFO của httpx.

## Zalo OA

- Adapter `ZaloOAChannel`, nhận webhook tại `POST /channels/{channel_id}/webhook` và gửi tin tư vấn văn bản qua OA API.
- Credential: OA ID, App ID, OA access token và OA Secret Key. Trường token/secret sử dụng cơ chế mã hóa credential hiện có khi deployment đã cấu hình khóa mã hóa.
- Webhook không dùng bearer token của người dùng; xác thực bằng `X-ZEvent-Signature` trên đúng raw body, timestamp, App ID và OA gửi/nhận tương ứng.
- Từ chối chữ ký sai, sai App/OA, timestamp lệch quá 5 phút, payload quá 256 KiB và kênh đã tắt. Đồng hồ server cần chính xác.
- `user_send_text` vào routing hiện có; sự kiện OA gửi ra và các loại nội dung chưa hỗ trợ được bỏ qua sau xác thực.
- Chống xử lý lặp theo message ID bằng lock/registry dùng chung. Chỉ ghi nhận đã xử lý sau khi chuyển thành công; lỗi chuyển nội bộ trả 503 để nhà cung cấp có thể thử lại.
- Phê duyệt bằng lệnh `DUYET <mã>` hoặc `TUCHOI <mã>`, áp dụng cùng ràng buộc người dùng/chat/session và thời hạn 24 giờ như Telegram.
- UI chi tiết kênh hiển thị Webhook URL đúng API base/proxy prefix, có nút sao chép.
- Mobile mở chi tiết toàn chiều rộng với nút quay lại danh sách; desktop giữ hai cột có thể kéo chỉnh.

Hai adapter công bố khả năng văn bản; chưa xử lý ảnh, âm thanh hoặc file đầu vào. Đây không phải bản tích hợp OAuth tự động của Zalo. Khi access token hết hạn, quản trị viên lấy token hợp lệ từ Zalo và thay trong UI hoặc API bên dưới.

## Thay token và ẩn kênh cũ

- `PATCH /channels/{channel_id}/credentials`: chỉ chủ kênh được cập nhật các trường bí mật được cho phép; không đổi danh tính bot, channel ID, routing hoặc session.
- Credential mới được kiểm tra trước khi lưu. Phiên bản cấu hình luôn tăng để client cache được làm mới, kể cả hai lần ghi rất sát nhau trên Windows.
- Response không trả credential. UI dùng ô password, xóa giá trị đã nhập sau khi lưu và hiển thị trạng thái thành công/lỗi.
- DingTalk/Feishu được ẩn khỏi catalog tạo kênh; đăng ký runtime và cấu hình đã có vẫn được giữ để tránh cắt kết nối ngoài phạm vi.
- Đã cập nhật mô tả kênh ở tiếng Việt/Anh/Trung; form mới lấy nhãn riêng từ schema để Zalo không còn dùng mô tả App ID của Feishu.

## Phiên thử của Leader

- Tab `Phiếu cư dân` dùng `GET /sessions/?scope=leader`; chỉ nhận session có workflow binding của server.
- Tab `Phiên thử` dùng `scope=leader_tests`; nhận phiên thủ công cũ chưa có workflow, bất kể tên đã đổi.
- Cả hai scope tiếp tục loại chat cá nhân, phiên BQL ẩn và session của người dùng khác.
- `POST /workforce/console/leader/tests` tạo workspace/session riêng, không tạo phiếu hay gắn workflow nghiệp vụ. Endpoint `/leader/tickets` cũ được giữ làm alias deprecated để tương thích.
- Bootstrap ưu tiên phiếu thật; nếu chỉ có phiên thử thì dùng lại phiên đó, không sinh thêm phiên mỗi lần mở trang.
- Cache danh sách và ChatViewport dùng cùng scope. Mỗi tab giữ lựa chọn riêng; sau tạo phiên mới sẽ chuyển đúng tab Phiên thử.
- Mobile có bộ chọn phiên; tab dùng Radix với điều hướng bàn phím. Có trạng thái tải, lỗi và danh sách rỗng, cùng nhãn rõ đây là phiên thử nội bộ.

## Kiểm chứng

- Backend: **177 passed, 3 subtests passed, 1 skipped**. Ca skip là `test_shutdown_signals_are_handled`: event loop Windows không hỗ trợ `add_signal_handler`; JUnit có 181 ca, 0 failure/error.
- Runner bỏ key model khỏi môi trường và chặn kết nối ra ngoài: **0 external network attempts**. HTTP provider dùng MockTransport, webhook dùng ASGI fixture.
- Bao phủ nhận/gửi tin, allowlist, cursor/retry, phê duyệt đúng người/chat/session, chống replay, chữ ký raw body, sai OA/App, lỗi môi trường webhook, payload lớn, credential encryption/rotation/owner scope và hồi quy kênh cũ.
- Fixture hồi quy delivery được cập nhật cho thuộc tính ledger và memory hiện tại; vẫn kiểm tra đầy đủ đích gửi và thứ tự vòng đời reply, không sửa runtime model để chiều fixture.
- TypeScript và ESLint các file giao diện thay đổi đạt. Vite production build với `VITE_API_BASE_URL=/api` đạt; còn cảnh báo bundle lớn có sẵn.
- **34/34 frontend tests đạt**, gồm kiểm tra trực tiếp artifact production nhúng `/api` và không nhúng loopback API mặc định.
- Browser **9/9 kiểm tra đạt**, không có page error: phân tách danh sách, bàn phím, tạo phiên thử, chọn phiên mobile, catalog kênh, URL/thay token, chi tiết mobile/quay lại, form Telegram và form Zalo. Toàn bộ API giả lập, chặn request ra ngoài và không gọi chat/model. Đã xem lại ảnh desktop/mobile; ảnh chỉ chứa dữ liệu giả.

Bằng chứng local trong `platform_VP/agentscope/.artifacts/channel-leader-20261018/`: `offline_check.py`, `offline.xml`, `browser_check.py`, `browser-summary.json`, `web-build.log` và các ảnh desktop/mobile.

Chưa xác minh kết nối với tài khoản bot/OA thật, webhook công khai trên VPS hoặc chất lượng trả lời model. Những mục đó cần cấu hình tài khoản và nghiệm thu riêng; kiểm thử offline không chứng minh chúng đã hoàn tất.

## Cách cấu hình sau khi bản này được phát hành

1. Mở Kênh kết nối, chọn Telegram hoặc Zalo OA, điền credential và chọn agent/model cùng routing. Dùng allowlist nếu chỉ muốn mở cho một nhóm người dùng.
2. Telegram: tạo bot qua BotFather, điền đúng Bot ID/token, bảo đảm bot không có webhook hoặc poller khác, rồi mở bot và chọn Start. Với nhóm, gọi tên bot hoặc trả lời tin của bot.
3. Zalo: chuẩn bị OA đã được cấp quyền cho App. Tạo kênh, mở chi tiết, sao chép Webhook URL HTTPS vào Zalo Developers, bật sự kiện tin nhắn và bảo đảm OA Secret Key trùng cấu hình.
4. Khi token thay đổi, dùng mục Thay token kết nối trong chi tiết kênh; không cần xóa kênh để tạo lại.
5. Leader: giữ phiếu thật ở tab mặc định; dùng dấu + để tạo phiên trong tab Phiên thử.

Hợp đồng API tham khảo: [Telegram Bot API](https://core.telegram.org/bots/api), [Zalo webhook tin nhắn](https://stc-developers.zdn.vn/docs/v2/official-account/webhook/tin-nhan/su-kien-nguoi-dung-gui-tin-nhan?lang=vi&ts=1783296000079), [Zalo OA API gửi tin tư vấn](https://stc-developers.zdn.vn/docs/v2/official-account/tin-nhan/tin-tu-van/gui-tin-tu-van-trich-dan?lang=vi&ts=1783296000075).
