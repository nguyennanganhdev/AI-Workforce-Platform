# Gửi Team Đông: chuyên viên trong phiên điều phối đã xem được ảnh đính kèm, không sửa mã lõi

Ngày 05/10/2026. Người gửi: Team Chiến. Trạng thái: đã làm ở lớp bọc; ba điểm dưới đây cần Team Đông biết và cho ý
kiến. Không có dòng nào trong `agent-coordination/src/adapters` hay các gói lõi khác bị sửa.

## Đã làm gì

BQL đính kèm ảnh vào câu hỏi gửi chuyên viên trong một phiên điều phối; ảnh tới model của chuyên viên dưới dạng hình.

- API trả ảnh cùng câu hỏi: `GET /internal/coordination/v1/mentions` có thêm `images` (`name`, `mimeType`, `data`
  base64), tối đa 10 MB ảnh mỗi câu hỏi.
- Lớp bọc giữ ảnh cho đúng một lượt: `Runtime.answer` (`agent-coordination/src/vinhomes/runtime.py`) đặt ảnh vào
  `Releases.attached` trước khi gọi `MentionAgent` và gỡ ra ngay sau đó; `Releases.resolve_released_session` gắn ảnh
  với thread của lượt gọi.
- Ảnh được thêm ở lớp HTTP mà bộ chuyển gửi qua: `InstructedClient.stream` (`agent-coordination/src/vinhomes/ports.py`)
  đổi `content` của tin nhắn đầu từ chuỗi thành mảng gồm phần chữ (nguyên chuỗi JSON của bộ chuyển) và các phần ảnh
  `{"type":"image","source":{"type":"data","value":…,"mimeType":…}}`. Bot đổi phần ảnh thành `image_url` cho nhà cung
  cấp (`shared/user-content.ts`). Câu hỏi không có ảnh vẫn gửi đúng một chuỗi như trước.

Đây là cùng chỗ lớp bọc đã thêm chỉ dẫn của agent vào `context`, nên bộ chuyển `OpenbotAdapter` không biết và không
cần biết về ảnh.

## Ba điểm cần Team Đông biết

1. **Ngân sách không tính ảnh.** `reserve = len(json.dumps(wire…).encode()) + release.output_tokens` trong
   `adapters/openbot.py` tính trên gói của bộ chuyển, tức chưa có ảnh. Chi phí ảnh do nhà cung cấp tính thêm và hiện
   không nằm trong số dự trữ. Nếu lõi cần tính, đề nghị thêm một cách khai chi phí phụ cho lượt gọi.
2. **Bản ghi của lượt gọi không chứa ảnh.** `remote_intent` và các bản ghi khác vẫn như cũ. Lượt chạy tiếp
   (`max_continuations`) gửi lại ảnh cùng tin nhắn đầu, vì lớp bọc thêm ảnh ở mỗi lần gửi của thread đó.
3. **Mới áp dụng cho câu hỏi BQL hỏi trong phiên.** Việc Supervisor giao (task) chưa mang ảnh của yêu cầu (ảnh cư dân
   gửi). Muốn chuyên viên xem ảnh của yêu cầu khi phân tích thì nên có trường ảnh trong dữ liệu của lượt gọi; phần đó
   thuộc mô hình của lõi và Team Chiến chưa làm.

## Lưu ý vận hành

Model của chuyên viên phải đọc được ảnh. Triển khai dùng model chỉ đọc chữ đặt `SPECIALIST_SEES_IMAGES=0`; khi đó API
không đưa ảnh và chuyên viên chỉ được báo tên ảnh.

## Đã kiểm

- Test của lớp bọc: câu hỏi có ảnh tới Bot gồm phần chữ và phần ảnh; sau lượt đó không còn ảnh nào được giữ; câu hỏi
  kế tiếp không có ảnh là một chuỗi (`tests/vinhomes/test_runtime.py`).
- Test của API: câu hỏi trong phiên kèm tệp văn bản và ảnh trả đúng `text` và `images`.
