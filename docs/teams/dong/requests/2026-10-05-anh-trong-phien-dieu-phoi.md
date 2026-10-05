# Đề nghị gửi Team Đông: cho chuyên viên trong phiên điều phối xem ảnh đính kèm

Ngày 05/10/2026. Người đề nghị: Team Chiến. Trạng thái: chờ Team Đông trả lời. Team Chiến chưa sửa gì trong mã lõi.

## Việc cần

BQL đính kèm được ảnh vào câu hỏi gửi chuyên viên trong một phiên điều phối. Hiện chuyên viên chỉ được báo tên ảnh và
câu "Bạn chưa xem được nội dung ảnh", vì bộ chuyển của lõi gửi sang Bot một tin nhắn dạng chữ. Team Chiến đề nghị
bộ chuyển gửi kèm ảnh dưới dạng phần ảnh, để model của chuyên viên xem được.

## Đã có sẵn ở các phần khác

- **Bot (`agent-bot`) đã nhận phần ảnh.** Nội dung tin nhắn người dùng có thể là một mảng: `{"type":"text","text":…}`
  và `{"type":"image","source":{"type":"data","value":"<base64>","mimeType":"image/png"}}`. Bot đổi phần ảnh thành
  `image_url` cho nhà cung cấp và chỉ nhận PNG, JPEG, GIF, WebP (`shared/user-content.ts`, `agent-bot/src/history.ts:62`).
- **Phòng nhóm (không qua lõi) đã chạy theo cách này.** Lượt trả lời trong phòng nhóm đi qua lớp bọc của Team Chiến
  (`agent-coordination/src/vinhomes/publish.py`, hàm `answer`). Đã kiểm bằng một tiến trình Bot thật nối với nhà cung
  cấp giả: phần ảnh tới nhà cung cấp đúng dạng `image_url`.
- **API đã có ảnh để đưa.** `for_agent` trong `services/vinhomes-api/src/vinhomes_api/v3_room_files.py` trả phần chữ và
  danh sách ảnh (`name`, `mimeType`, `data` base64), tối đa 10 MB ảnh mỗi lượt. Với câu hỏi trong phiên, API hiện chỉ
  dùng phần chữ (`GET /internal/coordination/v1/mentions`, trường `text`).

## Chỗ cần Team Đông quyết và sửa

`agent-coordination/src/adapters/openbot.py`, khoảng dòng 143 đến 147: `messages` được dựng thành một tin nhắn có
`content` là chuỗi JSON. Để gửi ảnh, `content` phải thành mảng gồm một phần chữ (chuỗi JSON hiện có) và các phần ảnh.
Việc này kéo theo ba điều thuộc về lõi, nên Team Chiến không tự làm:

1. **Dữ liệu ảnh đi đường nào tới bộ chuyển.** `invocation` hiện không có trường cho ảnh. Cần thêm trường vào mô hình
   của lượt gọi (ví dụ danh sách `{mimeType, data}`), và lớp bọc của Team Chiến sẽ điền từ câu trả lời của API.
2. **Dự trữ ngân sách.** Dòng `reserve = len(json.dumps(wire…).encode()) + release.output_tokens` tính theo số byte
   của gói gửi. Ảnh base64 làm số này tăng hàng triệu, trong khi chi phí thật của ảnh do nhà cung cấp tính theo kích
   thước ảnh. Cần một cách tính riêng cho phần ảnh, nếu không lượt nào có ảnh cũng chạm trần ngân sách.
3. **Ghi lại và phát lại.** `remote_intent` và các bản ghi của lượt gọi không nên chứa byte ảnh. Lượt chạy tiếp
   (`max_continuations`) gửi lại `messages`, tức gửi lại ảnh; cần xác nhận đó là hành vi mong muốn.

## Điều Team Chiến sẽ làm sau khi có trả lời

- Trả thêm `images` trong `GET /internal/coordination/v1/mentions` cho câu hỏi có ảnh, cùng dạng đã dùng ở phòng nhóm.
- Điền trường ảnh của lượt gọi trong lớp bọc (`agent-coordination/src/vinhomes`).
- Thêm ca kiểm: câu hỏi trong phiên có ảnh tới Bot với phần ảnh, và câu hỏi không có ảnh vẫn gửi đúng một chuỗi như hiện nay.

## Lưu ý vận hành

Model của chuyên viên phải đọc được ảnh. Triển khai dùng model chỉ đọc chữ đặt `SPECIALIST_SEES_IMAGES=0`; khi đó API
không đưa ảnh và chuyên viên chỉ được báo tên ảnh, như hiện nay.
