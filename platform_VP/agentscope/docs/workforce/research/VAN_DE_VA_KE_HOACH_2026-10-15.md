# Vấn đề còn lại và kế hoạch (15/10)

15/10/2026 · `develop2` (đã gồm #86) · nhánh `feat/wf-leader-orchestrates` · Người đọc: PM

## Quyết định của PM hôm nay

- **Leader của platform điều phối mọi phiếu từ domain.** Phiếu là một ticket ở
  trang Leader. Leader luôn lập phòng; `DieuPhoiVinhomes` là agent làm việc chính
  của đối tác; agent chuyên môn được mời khi cần. Các agent trao đổi trong phòng,
  Leader nói với người dùng.
- Người dùng cuối được gọi là "bạn".
- Key OpenAI do PM xử lý sau (đang hết tiền); trong lúc đó vẫn triển khai.

## Vấn đề, đo bằng số liệu thật (phiếu 15/10)

| # | Vấn đề | Bằng chứng | Mức | Trạng thái |
|---|---|---|---|---|
| 1 | Phiếu đối tác chạy trên agent của đối tác, không qua Leader; trang Leader không thấy phiếu; agent của đối tác vừa điều phối vừa làm việc | Ảnh trang Leader: "No team"; phiên nằm ở agent DieuPhoiVinhomes | Cao | Đã sửa (bước 1) |
| 2 | Chi phí: leader đối tác gọi `gpt-5.5` 9–15 lần mỗi phiếu, mỗi lần ~13–15k token (tự đọc phiếu, mỗi lần đọc ~2k token). Cache đã có (58–71% token input) | `provider_usage` của 2 phòng: 113.577 và 223.806 token input | Cao | Đã sửa phần thiết kế (bước 1–2); đo lại khi có key |
| 3 | Kết quả tool ghi nguyên văn vào Shared Context làm phòng vượt ngân sách 12.000 token | `SharedContextBudgetError` 12.996 > 12.000 | Cao | Đã sửa (#86 + bước 2) |
| 4 | Builder báo "đạt 0/3" khi model không gọi được (hết tiền) — người dùng tưởng agent sai | 53 lỗi `insufficient_quota` trong log; báo cáo 0/3 | Trung bình | Đã sửa (bước 3) |
| 5 | Thông báo hết tiền OpenAI hiện là "rate limit" | UI "Rate limit or quota exceeded" | Thấp | Đã sửa (bước 3) |
| 6 | Chưa có tab Hoạt động (token, chi phí, cache theo agent) | — | Trung bình | Đã làm (bước 4) |
| 7 | Phiếu không lập phòng không có nguồn để học | — | Trung bình | Hết: phiếu nào cũng có phòng |
| 8 | Phiếu lỗi lượt (hết tiền, lỗi model) nằm ở `needs_attention`, không tự chạy lại | 3 phiếu thử 15/10 | Trung bình | Còn mở |
| 9 | Phía Vinhome: Lễ tân hỏi vòng với yêu cầu nhiều hạng mục; chưa gửi ảnh qua API mới | Chat thử 15/10 | Phía Vinhome | Còn mở (phía Vinhome) |
| 10 | Triển khai: image chưa đánh phiên bản; chưa có server/tên miền/HTTPS cho platform | — | Khi có server | Còn mở |

## Kế hoạch và kết quả

| Bước | Việc | Xong khi | Kết quả |
|---|---|---|---|
| 1 | Leader điều phối: phiếu đối tác chạy trên phiên Leader; Leader chỉ có `CaseSay`/`CaseFinalize` + tool phòng; mời `DieuPhoiVinhomes` (tool `vh_*`) và agent chuyên môn; thành viên báo cáo kèm mã E và câu đề xuất; Leader gửi một tin | Trang Leader thấy phiếu; panel Team có thành viên; kịch bản offline đạt | Đạt. Kịch bản offline (model giả): Leader `gpt-5.5` chỉ có tool phòng + CaseSay; KyThuat đánh giá, DieuPhoi giao việc sau đánh giá (depends_on), cả hai chạy `gpt-5.4-mini`; Leader gửi một tin; sự kiện, mời xác nhận, đóng phiếu đạt; phiếu `Phiếu đối tác T-…` hiện ở trang Leader với 2 thành viên |
| 2 | Chi phí: Shared Context chỉ giữ tham chiếu gọn của kết quả tool đối tác (lời gọi + 1.200 ký tự đầu, có mã E), bản đầy đủ ở nhật ký case; Leader không chạy bộ chờ bằng chứng của console | Phòng không vượt ngân sách; Leader mỗi lần gọi nhỏ hơn | Đạt (test). `prompt_cache_key` theo agent bật ở `.env` local |
| 3 | Builder: lỗi model → báo rõ "không gọi được model" (không ghi 0/3); loại lỗi `quota` riêng cho `insufficient_quota` | Test | Đạt |
| 4 | Hoạt động: ticket, lượt trả lời, token vào/ra, phần cache theo agent (gồm Leader) | Nút "Hoạt động" ở trang Quản lý agent | Đạt (test API) |
| 5 | Khai báo Vinhome: `DieuPhoiVinhomes` về model tiêu chuẩn, báo Leader thay vì nói với cư dân; `route.config.leader_brief` cho Leader | PR Vinhome | Đạt; đã onboard lại local (DieuPhoi v6) |
| 6 | Chạy lại khi có key: một phiếu trọn luồng qua UI; đo token trước/sau | PM nạp tiền key | Chờ key |

## Ước tính chi phí sau thay đổi (cần đo lại ở bước 6)

Trước: leader đối tác `gpt-5.5` tự gọi tool, 9–15 lần/phiếu, ~13–15k token mỗi
lần. Sau: tra phiếu và giao việc chạy ở thành viên `gpt-5.4-mini`; Leader
`gpt-5.5` gọi khoảng 4 lần ở lượt đầu (lập phòng, mời, chờ, gửi tin), mỗi lần
không có kết quả tool thô (chỉ báo cáo và tham chiếu gọn). Học kinh nghiệm sau
phiếu: một lần gọi model mạnh cho mỗi thành viên có bộ nhớ.

## Còn mở

- Phiếu `needs_attention` do lỗi model chưa tự chạy lại (vấn đề 8).
- Phía Vinhome: Lễ tân hỏi vòng; gửi ảnh qua API mới (vấn đề 9).
- Phiếu đã mở trước thay đổi vẫn gắn với phiên của DieuPhoi; nên đóng các
  phiếu thử cũ trước khi chạy bước 6.
