# Hướng dẫn cấu hình: eval trên sandbox, kênh Discord, lịch chạy

Tài liệu này dành cho người vận hành platform (admin) và BQL. Phạm vi gồm cấu hình và các bước thử. Mọi bước có gọi model thật đều do người có quyền dùng key tự chạy.

## 1. Eval trên sandbox Vinhome

### Cách hoạt động

Khi một agent dùng tool của MCP được khai báo là sandbox, mỗi ca eval chạy như sau:

1. Platform gọi `POST /api/business/platform/eval-fixtures` để tạo một ticket mẫu mới. Ticket được tạo qua luồng tiếp nhận cư dân bình thường, nên có bàn giao giống lúc chạy thật.
2. Platform xin grant theo ticket qua `POST /api/business/platform/mcp-grants`, giống như runtime.
3. Agent nhận message bàn giao (có dòng `ticket_id`) trước lời của khách.
4. Mọi tool của MCP sandbox chạy thật trên dữ liệu mô phỏng, kể cả tool ghi.
   - Tool cần đồng ý được chạy như thể cư dân đã đồng ý khi được hỏi, và được đánh dấu `consent_assumed` để bộ chấm biết.
5. TeamSay vẫn là mô phỏng.

Ticket mẫu không bao giờ được gửi sang platform. Phía Vinhome đánh dấu lệnh `start_workflow` là đã xong và đóng liên kết bàn giao trong cùng giao dịch tạo ticket.

MCP không được khai báo là sandbox giữ cách cũ: chỉ đọc tool mà server phân loại là chỉ-đọc, mọi thao tác ghi đều mô phỏng.

### Cấu hình phía Vinhome sandbox

Trong env của container API sandbox:

```
VINHOMES_API_EVAL_FIXTURES=enabled
```

API này còn bị chặn bởi 2 điều kiện khác:
- DB phải mang marker sandbox tổng hợp (`vinhomes-synthetic-sandbox-v1`). Trên DB production, API luôn trả 409.
- Lời gọi phải mang Bearer control-plane (`VINHOMES_API_PLATFORM_MCP_TOKEN`).

### Cấu hình phía platform

Trong env của container `app`:

```
WORKFORCE_EVAL_SANDBOXES=[{"mcp_url":"http://host.docker.internal:8087/mcp","fixture_path":"/api/business/platform/eval-fixtures","grant_path":"/api/business/platform/mcp-grants","ttl_seconds":900,"case_context":"Mỗi ca có một ticket sự cố kỹ thuật mới: vòi bếp rò nước, chưa giao thợ."}]
```

- `mcp_url` phải trùng **chính xác** URL của MCP đã đăng ký. Chỉ admin được thêm URL vào danh sách này. Không bao giờ thêm URL MCP production.
- `case_context` giúp Builder sinh test đúng với ticket mẫu.

Chỉ một trong hai phía thiếu cấu hình, hoặc sandbox không phản hồi, thì mọi ca sẽ báo **lỗi môi trường** kèm lý do. Kết quả đó không được tính là agent trượt, và chưa phát hành được cho tới khi chạy lại sạch.

### Cổng phát hành

- Tối thiểu 5 kịch bản.
- Đạt từ 80%, nghĩa là cần ít nhất 4/5.
- Mọi ca an toàn phải đạt.
- Không ca nào được có lỗi môi trường, lỗi model hoặc lỗi bộ chấm.

Nếu bộ chấm không trả kết quả, hệ thống tự thử lại 1 lần.

## 2. Kênh Discord

### Tạo bot

1. Vào https://discord.com/developers/applications, chọn **New Application**, rồi vào mục **Bot**.
2. Bật **Message Content Intent**. Thiếu bước này thì bot không đọc được nội dung tin nhắn.
3. Chép **Bot Token** và **Application ID**.
4. Vào OAuth2 → URL Generator, chọn scope `bot`. Chọn các quyền: Send Messages, Read Message History, Attach Files, View Channels. Mở URL đó để mời bot vào server.

### Gắn vào platform

1. Mở **Kênh kết nối**, chọn **Discord**, rồi nhập Bot Token và Application ID.
2. Gắn kênh vào **Leader**, hoặc một agent **đã phát hành**. Agent nháp không gắn được.
3. **Người duyệt**: điền Discord user ID của những người được duyệt thao tác thay người khác, ví dụ trưởng BQL.
   - Người đã gửi yêu cầu luôn tự duyệt được thao tác của chính mình.
   - Người khác trong kênh bấm duyệt sẽ nhận một lời nhắn riêng, và thao tác không chạy.
4. Mặc định trong server bot chỉ trả lời khi được @mention. Trong tin nhắn riêng (DM) bot luôn trả lời.

### Lưu token an toàn

Token bot được mã hoá khi lưu nếu deployment có `CHANNEL_CREDENTIALS_KEY`, hoặc `PARTNER_API_KEY_PEPPER`. Khoá phải dài tối thiểu 32 ký tự. Nếu sau này đổi khoá, phải tạo lại kênh.

### Danh sách tự kiểm

1. DM bot một câu hỏi; bot trả lời.
2. Trong kênh server: không @mention thì bot im lặng; có @mention thì bot trả lời.
3. Gửi một câu trả lời dài hơn 2000 ký tự; bot tự chia thành nhiều tin.
4. Kích hoạt một tool cần duyệt:
   - Một người khác bấm Approve: nhận lời nhắn riêng, thao tác không chạy.
   - Chính người yêu cầu bấm: thao tác chạy.

## 3. Lịch chạy

- Chỉ chọn được Leader hoặc agent đã phát hành.
- Không có chế độ BYPASS: lịch chạy không có người trực, nên thao tác cần đồng ý vẫn phải có người duyệt.
- **Một lần**: lịch chạy đúng một lần vào lần khớp kế tiếp, rồi tự tắt.
- **Gửi kết quả vào**: nếu khu có kênh Discord đang bật, form tự chọn kênh đó và cuộc trò chuyện đầu tiên mà bot thấy. Chọn "Chỉ lưu trong phiên của agent" để giữ kết quả trong phiên của agent. Với Leader, phiên đó nằm trong danh sách phiên của Leader.
- Có 3 mẫu sẵn: báo cáo ticket 8:00 hằng ngày, rà soát quá hạn 14:00, tổng kết tuần thứ Hai 8:30. Cả ba chỉ đọc và báo cáo.
- Chi tiết lịch hiển thị lần chạy gần nhất và lỗi nếu có. Mỗi lần chạy là một phiên mở xem được.

## 4. Kiểm thử bằng model thật (người có quyền dùng key tự chạy)

1. Builder: mở lại hội thoại có thẻ "Cần bạn chọn", bấm một lựa chọn.
   - Mong đợi: không lập lại dàn ý, chỉ một lượt JEV chọn tài nguyên, rồi tới được "Duyệt phương án".
2. Eval: nâng cấp agent Điều Phối thêm chức năng đổi lịch/hủy, rồi chạy eval.
   - Mong đợi: 5 ca, mỗi ca một ticket mẫu, 0 lỗi môi trường.
   - Bảng ca hiển thị chế độ `sandbox` cho tool Vinhome.
3. Discord và lịch chạy: thực hiện theo danh sách ở mục 2 và mục 3.
