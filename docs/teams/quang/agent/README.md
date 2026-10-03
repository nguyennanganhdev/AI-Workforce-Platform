# Agent Kỹ thuật A2 — định nghĩa để phát hành

Thư mục này là nội dung của agent kỹ thuật mà Supervisor mời vào phòng điều phối khi ticket thuộc danh mục
`technical`. Team Quang sở hữu nội dung. Bản đầu (04/10/2026) do Team Chiến soạn từ `../general.md` để luồng
chạy được; cần Team Quang rà lại.

| Tệp | Nội dung |
|---|---|
| `technical-agent.md` | Chỉ dẫn của agent, nguyên văn. Lấy từ `general.md`: phạm vi, ranh giới, ba mức, 16 mã vấn đề, cách trả lời |
| `technical-agent.json` | Tên, mô tả, danh mục phục vụ và các ca đánh giá |

## Phát hành

Backend, Bot (`agent-coordination/scripts/start_openbot.ps1`) phải đang chạy.

```powershell
agent-coordination\scripts\publish_agent.ps1 docs\teams\quang\agent\technical-agent.json -Room management-room -Approve
```

Công cụ làm đúng luồng của platform: Ban quản lý tạo agent nháp và lưu cấu hình, từng ca đánh giá được chạy thật
trên Bot như một lượt nói trong phòng, chỉ khi mọi ca đạt mới nộp cho admin, và `-Approve` ghi quyết định duyệt
của admin (duyệt là phát hành). Bỏ `-Approve` thì bản nộp chờ admin.

Sửa chỉ dẫn hoặc ca đánh giá là tạo một agent nháp mới: cấu hình của agent đã duyệt không sửa được.

## Ca đánh giá

Mỗi ca có `instruction` (việc Supervisor giao), `ticket` (dữ liệu ticket), `must` (mọi mẫu phải xuất hiện trong
câu trả lời) và `must_not` (không mẫu nào được xuất hiện). Mẫu là biểu thức chính quy, không phân biệt hoa thường.

Tám ca hiện có: cầu dao nhảy có tia lửa (Level 1), điều hòa chảy nước (Level 2), rò nước trong tường (Level 2),
trần nứt võng (Level 1), vòi bếp rò đầu nối (Level 3), nước thải trào ngược (Level 2), mô tả không đủ để phân
loại, và yêu cầu đọc cảm biến (agent phải nói chưa có công cụ, không đưa số đo).

## Việc cần Team Quang

- Rà `technical-agent.md` so với `general.md`.
- Thay tám ca bằng bộ dữ liệu chuẩn của 16 mã vấn đề và các ca Level 1 bắt buộc (mục 12 của `general.md`).
- Chốt cách phân biệt `TECH.ARCH.PAINT_MOISTURE` với `TECH.PLUMB.CONCEALED_LEAK`: với mô tả "tường giáp phòng
  tắm ố vàng, ẩm, lan dần", model chọn mã đầu ở Level 3. Bảng mã cũng ghi `PAINT_MOISTURE` nâng Level 1 khi
  "nguồn ẩm vẫn tiếp diễn", cần xác nhận lại.
- Phiên bản này chưa có công cụ: agent nói rõ điều chưa tra được. Khi cổng tool của platform có, chỉ dẫn cần
  thêm phần dùng tool và các ca đánh giá tương ứng.
