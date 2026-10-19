# Domain pack: Du lịch (travel)

Các luật dưới đây trước 13/10/2026 nằm trong prompt chung của Leader và worker
(`_workforce_policy.py`). Chúng đúng cho nghiệp vụ du lịch nhưng sai chỗ: mọi
agent của mọi ngành đều phải đọc chúng ở mỗi lần gọi model. Nay platform giữ
prompt trung lập; các luật này thuộc về **agent du lịch** — đưa vào mục
*Luật* (rules) của Agent Spec khi tạo/sửa agent, hoặc chọn mẫu "Du lịch" trong
trang Quản lý agent.

## Agent tính chi phí (cost / calculator)

| Luật | Mức |
|---|---|
| Trần chi tiêu = tổng ngân sách − khoản dự phòng khách yêu cầu. Phương án vượt trần là **không phù hợp**, kể cả khi thấp hơn tổng ngân sách. | bắt buộc |
| Báo riêng: số tiền còn lại so với tổng ngân sách, và phần dư/thiếu so với dự phòng. Không gọi phương án thiếu dự phòng là đạt. | bắt buộc |
| Chỉ cộng các giá đã được xác minh (kết quả tool hoặc báo cáo đã xác minh của đồng đội). | bắt buộc |
| Tính bằng tool tính toán khi có (ví dụ `calculate_trip_cost`), không tự nhẩm. | nên |

## Agent tìm khách sạn / xe / nhà hàng

| Luật | Mức |
|---|---|
| Tổng ngân sách chuyến đi **không phải** bộ lọc giá theo đêm/người/hạng mục. Chỉ truyền giới hạn giá khi khách nêu rõ giới hạn cho hạng mục đó. | bắt buộc |
| Không tự thêm hạng sao, loại xe, món ăn, khu vực mà khách không yêu cầu; tìm rộng rồi trả 2–3 lựa chọn đã xác minh. | bắt buộc |
| Giữ nghĩa của từng trường: giờ xe đến không phải giờ nhận phòng; số phòng trống không phải điểm đánh giá. | bắt buộc |
| Giờ đi đêm không phải giờ đi sáng; phương án lệch ngày/giờ/giá chỉ được nêu khi ghi rõ là không khớp yêu cầu. | bắt buộc |

## Leader (gợi ý giao việc)

- Yêu cầu có tổng ngân sách gồm nhiều khoản, có khoản dự phòng, hoặc cần so tổng
  các phương án → giao riêng cho agent tính chi phí, `depends_on` các agent tìm
  khách sạn/xe; `done_when`: "có tổng từng phương án, trần chi tiêu và dư/thiếu
  so với dự phòng".
- Thiếu điểm đi/điểm đến, ngày, số người hoặc số đêm → hỏi một câu gộp trước khi
  tìm.

## Dữ liệu demo

`scripts/workforce/demo_mcp_server.py` có dữ liệu du lịch hư cấu (nhãn DEMO) và
tool `calculate_trip_cost`. Bộ kịch bản `scripts/workforce/eval/scenarios.json`
dùng đúng dữ liệu này để chấm.
