# Báo cáo tình trạng Platform ngày 20/10/2026

Phạm vi: bản đang chạy trên VPS Platform (`vagen-platform.duckdns.org`) và các
sửa đổi trong báo cáo này. Số liệu đọc trực tiếp từ Redis/Postgres trên VPS
bằng truy vấn chỉ đọc, khoảng 01:00 đến 01:40 ngày 20/10 (giờ VN). Không gọi
model thật.

## Tóm tắt

| Hạng mục | Tình trạng |
| --- | --- |
| Chat agent peer to peer | Code đã chạy trên VPS từ 19/10; **chưa có phòng nào chạy sau deploy**, nên chưa có bằng chứng thật |
| Cài đặt Leader | **Đã sửa và deploy**: hướng dẫn thêm + số bước suy luận |
| Eval | **Đã sửa và deploy**: hết fail do công cụ tra cứu không có dữ liệu, thử lại lỗi model tạm thời |
| Review code | 4 lỗi tìm được, đã sửa cả 4 trước deploy |
| Vận hành | Đã xử lý 20/10: hết 401 lặp lại, ổ đĩa 79% xuống 52%, sao lưu ngoài máy chạy và đã gửi bản mới nhất |

## Bản đang chạy

| Thành phần | Ảnh | Gồm |
| --- | --- | --- |
| App | `agentscope-platform:9e9a0802-leadersettings-20261020` | develop2 (#112, #113, #114) + bản sửa này |
| Web | `agentscope-platform-web:09de9570-leadersettings-20261020` | develop2 #113 + hộp thoại cài đặt Leader |

Trong lúc chuẩn bị, hai phiên khác deploy phase 1 (`386d545b`) và gói
Vinhomes test (`df0349b3`). Bản này được merge cả hai rồi mới dựng, nên
không ghi đè phần nào. Biến `VINHOMES_TEST_BINDING` vẫn còn sau deploy.

Kiểm tra sau deploy: app/web healthy; `/`, `/login`, `/workforce/leader`,
`/api/health` trả 200; `/api/workforce/console/leader/settings` trả 401 khi
chưa đăng nhập; không có lỗi trong log 10 phút đầu.

Quay lui: thư mục `/opt/awp-platform/releases/leadersettings-09de9570-20261020`
có `private/env.before`; tag `awp-rollback/{app,web}:before-leadersettings-20261020`;
sao lưu `/var/backups/awp-platform/leadersettings-09de9570-20261020`. Bản cũ
đọc được dữ liệu mới (các trường mới bị bỏ qua).

## 1. Chat agent peer to peer

Code cho phép thành viên chuyển việc (`handoff`) và gửi kết quả thẳng cho nhau
trong phòng phiếu và kênh tạo mới; Leader vẫn là người trả lời khách.

**Chưa xác nhận được trên VPS:** từ deploy 19/10 đến lúc kiểm tra, không có
phòng nào được tạo hoặc hoạt động. Lần cập nhật phòng cuối là 10:55 UTC ngày
19/10. Cả 28 team hiện có là team cũ, giữ định tuyến cũ.

Lịch sử 47 phòng trước deploy:

| Loại tin | Người gửi | Người nhận | Số lượng |
| --- | --- | --- | ---: |
| Giao việc | Leader | Thành viên | 184 |
| Kết quả | Thành viên | Leader | 118 |
| Lỗi | Thành viên | (runtime ghi) | 30 |
| Lỗi | Thành viên | Leader | 12 |
| Kết quả | Leader | Thành viên | 12 |
| Giao việc | Thành viên | Leader | 9 |
| Câu hỏi | Thành viên | Thành viên | 8 |
| Trả lời | Thành viên | Thành viên | 5 |
| Kết quả, lỗi, giao việc | Thành viên | Thành viên | 3 |

Hơn 95% trao đổi đi qua Leader; chỉ 8 trong 44 phòng có câu hỏi giữa thành viên.

Sự kiện lỗi trong phòng (47, tất cả từ 16 đến 18/10):

| Nguyên nhân | Số lượng | Tình trạng |
| --- | ---: | --- |
| Chạm giới hạn xử lý nội bộ | 12 | Giới hạn trao đổi nâng lên 60 ngày 19/10 |
| Vượt ngân sách context của thành viên | 11 | Giới hạn packet nâng lên 48k ngày 19/10 |
| Evidence gate từ chối hai lần | 9 | Gate đã gỡ khỏi luồng team ngày 19/10 |
| Phiếu vượt ngân sách context của Leader | 6 | Như dòng context ở trên |
| Khác, lỗi công cụ, sửa claim, huỷ giữa chừng | 9 | |

Chưa có phòng nào chạy sau các bản sửa ngày 19/10, nên chưa xác nhận được các
lỗi này đã hết.

**Lỗi tìm thấy khi review và đã sửa:** thành viên vừa có việc Leader giao vừa
nhận phần việc đồng đội chuyển sang. Khi trả lại phần việc đó, runtime đã tính
luôn việc riêng của thành viên là xong, và Leader có thể tổng hợp thiếu phần
đó. Giờ việc riêng vẫn mở và Leader vẫn chờ.

**Cách xác nhận:** mở một phiếu mới hoặc nhắn vào kênh để Leader lập phòng
mới, với yêu cầu cần hai thành viên dùng kết quả của nhau. Trong dòng thời gian
phòng, xem tin "Giao việc" hoặc kết quả đi thẳng giữa hai thành viên.

## 2. Cài đặt Leader

**Nguyên nhân không chỉnh được:**

- Trang Leader không truyền nút cài đặt vào khung chat, nên tên Leader ở đầu
  khung chat bị vô hiệu.
- API chỉnh agent luôn trả 409 với Leader; Agent Studio chỉ nhận agent nghiệp vụ.
- Mỗi lần mở trang, hàm khởi tạo ghi lại prompt cố định của Leader.

**Đã sửa:** bấm tên Leader ở đầu khung chat để mở "Cài đặt Leader":

- Hướng dẫn thêm cho Leader (tối đa 4.000 ký tự), đặt sau chính sách cố định
  của nền tảng; khi mâu thuẫn, chính sách nền tảng thắng.
- Số bước suy luận tối đa mỗi lượt (5 đến 100).
- Chỉ lưu được khi đã tải xong cài đặt hiện tại; tải lỗi thì có nút tải lại,
  không ghi đè hướng dẫn cũ bằng ô trống.

Tên, model và chính sách vận hành vẫn cố định: thành viên gửi tin cho Leader
theo tên, và chính sách vận hành là luật an toàn của phiếu. Muốn mở thêm trường
nào thì cần quyết định riêng.

## 3. Eval

Dữ liệu eval đang lưu trên VPS (62 ca): 45 đạt, 12 không đạt, 5 lỗi model.

- 9 ca không đạt vì agent không làm xong việc; cả 11 lần gọi công cụ trong các
  ca này trả `SIMULATED`, tức agent không có dữ liệu. Nguyên nhân: MCP du lịch
  không khai báo `readOnlyHint`, eval coi mọi công cụ là thao tác ghi.
- 3 ca trượt vì so khớp nguyên văn câu dài; quy tắc hiện tại đã chuyển câu dài
  cho bộ chấm, nên đây là kết quả của phiên bản cũ.
- 5 lỗi model là lỗi gọi model không được thử lại.

**Đã sửa (giữ nguyên cách sinh case và kỳ vọng):**

- Công cụ chưa khai báo `readOnlyHint` nhận dữ liệu giả do eval sinh nếu tên
  rõ là tra cứu (get, list, search, find, check, view, calculate…), không có
  động từ ghi (create, update, add, assign, dispatch, reschedule, prepare,
  commit…) và không bị runtime coi là nhạy cảm (đặt, huỷ, thanh toán, gửi, dữ
  liệu cá nhân). Mọi công cụ khác vẫn mô phỏng, nên một thao tác ghi không bao
  giờ trông như đã thành công.
- Lỗi model tạm thời (giới hạn tốc độ, kết nối, 5xx) được thử lại sau 2 giây
  và 6 giây. Lỗi khoá API hoặc hết credit không thử lại.
- So khớp số bỏ qua dấu phân cách hàng nghìn.
- Không sinh được dữ liệu giả là lỗi môi trường, không tính là agent sai.

Không làm: không hạ ngưỡng đạt, không bỏ ca an toàn, không đánh "đạt" khi bộ
chấm chưa chấm. Agent đã eval trước đây cần chạy eval lại để có kết quả mới.

## 4. Kiểm thử

Chỉ model và storage giả lập.

| Bộ test | Kết quả |
| --- | --- |
| Team, chat, toolkit, shared context, admin | 379 đạt, 2 lỗi có sẵn trên develop2 |
| `tests/workforce/integrations` | 105 đạt |
| `tests/workforce/console` | 272 đạt, 28 bỏ qua |
| `tests/workforce/orchestration` | 269 đạt |
| Frontend (node test) | 53 đạt, 1 bỏ qua |
| TypeScript, ESLint các file sửa | Đạt |

Test mới: cài đặt Leader (3), eval công bằng (17), định tuyến phần việc được
chuyển (2). Hai lỗi có sẵn: `service_chat_locking_test` (waiter) và
`workspace_daytona_test` (gỡ rồi thêm lại MCP).

## 5. Vấn đề vận hành còn mở

| Vấn đề | Mức | Ghi chú |
| --- | --- | --- |
| Domain gọi API đối tác của Platform, nhận 401 | Đã xử lý | Khoá của Domain vẫn đúng và còn hiệu lực. Platform từ chối vì API đối tác bị tắt: lớp đăng nhập của bản open platform (19/10 00:10 UTC) chặn trước, rồi phase 1 đặt `WORKFORCE_PARTNER_API=false` theo quyết định bỏ cư dân/BQL. Đã dừng `platform-sync` trên VPS Domain (restart=no); `api` của Domain giữ nguyên. Bật lại: `docker update --restart=unless-stopped vinhomes-domain-platform-sync-1 && docker start vinhomes-domain-platform-sync-1`, và chỉ có tác dụng khi Platform bật lại API đối tác |
| Ổ đĩa VPS Platform | Đã xử lý | 79% xuống 52%: xoá 11 bản sao lưu cũ, 30 ảnh Docker cũ, 23 file nén ảnh ở release cũ; giữ 3 bản sao lưu gần nhất (đã kiểm mã băm) và ảnh/tag để quay lui 3 lần deploy gần nhất. Nhật ký: `/opt/awp-platform/cleanup-20261020.log` |
| Sao lưu ngoài máy | Đang chạy | Báo cáo trước ghi "không chạy" là sai: không có timer riêng, việc gửi chạy sau bản sao lưu hằng ngày 03:30 giờ VN, mã hoá bằng age, gửi sang VPS Domain và kiểm lại khi truyền. Bản mới nhất (sau phase 1 và Leader settings) đã gửi thủ công 20/10. Bản sao lưu lúc deploy không tự gửi |
| Bên nhận sao lưu không tự xoá bản cũ | Trung bình | VPS Domain đang giữ 8,5 GB, tăng ~700 MB mỗi ngày, còn ~14 GB trống: khoảng 3 tuần là đầy. Cần chọn giữ bao nhiêu ngày |
| Phiên thử của Leader chạy peer, phiếu thật chạy collaborative | Thấp | Phiên thử không phản ánh đúng phiếu thật |
| Mục còn mở ghi nhận 19/10, chưa kiểm lại hôm nay | | DNS rebinding chưa chặn; tài khoản bị đình chỉ có khoá riêng không bị quota chặn; `/workspace/mcp` lỗi 500 với playwright; peer mode chưa có learning hook |
