# Agent Kỹ thuật A2 — định nghĩa để phát hành

Thư mục này là nội dung của agent kỹ thuật mà Supervisor mời vào phòng điều phối khi ticket thuộc danh mục
`technical`. Team Quang sở hữu nội dung. Bản đầu (04/10/2026) do Team Chiến soạn từ `../general.md` để luồng
chạy được; cần Team Quang rà lại.

| Tệp | Nội dung |
|---|---|
| `technical-agent.md` | Chỉ dẫn của agent, nguyên văn. Lấy từ `general.md`: phạm vi, ranh giới, ba mức, 16 mã vấn đề, ba tool đọc và quy trình dùng tool, cách trả lời |
| `technical-agent.json` | Tên, mô tả, danh mục phục vụ, tool được cấp (`tools`) và các ca đánh giá |

## Phát hành

Backend, Bot (`agent-coordination/scripts/start_openbot.ps1`) và dịch vụ tool
(`services/vinhomes-api/scripts/start_technical_tools.ps1`) phải đang chạy. Từ 04/10/2026 tool host này còn phục vụ
`/internal/technical/v1/connections` cho kết nối MCP ngoài của agent BQL (Team Chiến; cần `TECHNICAL_CONNECTIONS_KEY`);
các tool kỹ thuật và `/call` không đổi.

```powershell
agent-coordination\scripts\publish_agent.ps1 docs\teams\quang\agent\technical-agent.json -Room management-room -Approve
```

Công cụ làm đúng luồng của platform: Ban quản lý tạo agent nháp và lưu cấu hình, từng ca đánh giá được chạy thật
trên Bot như một lượt nói trong phòng, chỉ khi mọi ca đạt mới nộp cho admin, và `-Approve` ghi quyết định duyệt
của admin (duyệt là phát hành). Bỏ `-Approve` thì bản nộp chờ admin.

Sửa chỉ dẫn hoặc ca đánh giá là tạo một agent nháp mới: cấu hình của agent đã duyệt không sửa được. Khi bản mới
được duyệt, công cụ thu hồi agent cùng tên đã phát hành trước đó, để phòng chỉ còn một agent kỹ thuật.

## Ca đánh giá

Mỗi ca có `instruction` (việc Supervisor giao), `ticket` (dữ liệu ticket), `must` (mọi mẫu phải xuất hiện trong
câu trả lời) và `must_not` (không mẫu nào được xuất hiện). Mẫu là biểu thức chính quy, không phân biệt hoa thường.

Với tool: `tool_results` là điều tool trả lời trong ca đó (tool không được nêu thì trả theo `tool_defaults`, tức
là không tìm thấy gì), `must_call` là tool bắt buộc phải gọi, `must_not_call` là tool không được gọi. Nhờ vậy một
ca nói rõ tool trả gì và agent phải nói gì sau đó, mà không cần dữ liệu thật trong database.

Một ca có thể có `messages`: những gì phòng đã có cho agent (ví dụ câu trả lời trước của nó), dùng cho ca câu hỏi
tiếp theo. Chạy bộ đánh giá mà không lưu gì: `python -m vinhomes.publish <định nghĩa> --check`.

Mười một ca hiện có: cầu dao nhảy có tia lửa (Level 1), điều hòa chảy nước (Level 2), rò nước trong tường (Level 2),
trần nứt võng (Level 1), vòi bếp rò đầu nối (Level 3, phải dẫn mã SOP mà tool trả về), nước thải trào ngược
(Level 2), mô tả không đủ để phân loại (không được gọi tool), yêu cầu đọc cảm biến (phải nói chưa có công cụ, không
đưa số đo), nước yếu khi đang có gián đoạn chung (phải nêu đúng giờ khôi phục đã công bố), tool báo lỗi (phải
ghi chưa tra được, không kết luận là không có gián đoạn), và câu hỏi tiếp theo của BQL (phải trả lời thẳng, không
chép lại bản phân tích trước).

Độ ổn định đo được với `gpt-5.4-mini`: 7 lần chạy cả bộ thì 4 lần đạt 10/10, 3 lần hỏng đúng một ca.

## Việc cần Team Quang

- Rà `technical-agent.md` so với `general.md`.
- Thay tám ca bằng bộ dữ liệu chuẩn của 16 mã vấn đề và các ca Level 1 bắt buộc (mục 12 của `general.md`).
- Chốt cách phân biệt `TECH.ARCH.PAINT_MOISTURE` với `TECH.PLUMB.CONCEALED_LEAK`: với mô tả "tường giáp phòng
  tắm ố vàng, ẩm, lan dần", model chọn mã đầu ở Level 3. Bảng mã cũng ghi `PAINT_MOISTURE` nâng Level 1 khi
  "nguồn ẩm vẫn tiếp diễn", cần xác nhận lại.
- Agent hiện có ba tool đọc. Tool đọc tài sản, cảm biến, lịch sử bảo trì chưa cấp vì chưa có ca đánh giá; tool
  ghi và tool tạo yêu cầu chưa mở cho phiên điều phối.
- Nạp SOP thật: database local chưa có SOP nào, nên `sop_kb.retrieve` luôn trả `NOT_FOUND`. Tài liệu SOP phải
  được cấp cho workspace của BQL (`document_acl`, loại `workspace`) thì agent mới đọc được.
- Quy trình dùng tool trong chỉ dẫn (mục QUY TRÌNH) là đề xuất của Team Chiến; cần Team Quang xác nhận, nhất là
  việc Level 1 không chờ tra cứu.
