# Việc cần làm — Lễ tân (chi tiết ở `tasks/plan.md`)

## Giai đoạn 0 — Nền để đo, dọn giao diện
- [x] T0.1 Danh sách hội thoại và thông báo dễ đọc (S) — commit b6db9a7
- [x] T0.2 Bộ đánh giá hội thoại tiếng Việt chạy tự động, có điểm gốc (M) — commit 33cdf61
- [x] T0.3 Dọn dữ liệu thử trong database demo (khôi phục bản sao lưu trước khi thử + nâng cấp lại)

## Giai đoạn 1 — Tri thức chạy thật
- [x] T1.1 Nạp Data-Vinhome, ánh xạ phạm vi ↔ tòa, cấp quyền cho Lễ tân (M) — 114 tài liệu; bộ 93 câu chưa đo được (đáp án lệch dữ liệu)
- [x] T1.2 Bật route tìm kiếm; Lễ tân trả lời có trích dẫn; test route cấp quyền (S)

### Điểm dừng 1 — duyệt bảng điểm gốc

## Giai đoạn 2 — Câu không có nguồn vào session của BQL
- [x] T2.1 Lễ tân mở yêu cầu hỏi đáp khi không có nguồn (M)
- [x] T2.2 Tin nhắn từ session về chat cư dân (M)
- [x] T2.3 Màn tin nhắn session trong Operations (M)

## Giai đoạn 3 — Agent do model dẫn dắt
- [x] T3.1 Model adapter gọi tool (S)
- [x] T3.2 Bộ tool cho agent (M) — luật trong tools.py; test đơn vị ở tests/agent
- [x] T3.3a Vòng agent + cổng policy (M)
- [x] T3.3b Bước kiểm tra đầu ra (M)
- [x] T3.4 So điểm với graph cũ bằng bộ đánh giá trên hai môi trường tạm (thay cho chạy ngầm): loop 94–100% / 96–100% / 4,75–4,88 so với graph 87% / 88% / 4,42

### Điểm dừng 2 — quyết định bật agent mới

## Giai đoạn 4 — Bộ nhớ dài hạn
- [x] T4.1 Bộ nhớ cư dân: 5 yêu cầu gần nhất của chính cư dân đưa vào ngữ cảnh agent (không cần kho mới; chỉ đọc dữ liệu của cư dân đó)
- [ ] T4.2 Hoãn: bộ nhớ hiện là lịch sử yêu cầu, cư dân đã xem được ở "Yêu cầu của tôi". Chỉ cần khi có bộ nhớ sở thích dạng tự do

## Giai đoạn 5 — Tự thẩm định, tự cải thiện
- [ ] T5.1 Thu tín hiệu ngầm (S) — hoãn: backend đã ghi sẵn xác nhận/từ chối, mở lại, retrieval_runs; chưa có dữ liệu thật để dùng
- [x] T5.2 Agent thẩm định tri thức, phân mức tự duyệt / chờ duyệt / loại (M)
- [ ] T5.3 Điểm tin cậy vào thứ hạng (M) — hoãn tới khi có tín hiệu thật
- [ ] T5.4 Ngân hàng ví dụ mẫu (S) — hoãn: ticket_triage_reviews chưa có dòng nào
- [x] T5.5 Nút duyệt một chạm trong Operations (S)

## Giai đoạn 6 — Tối ưu truy xuất (theo số đo)
- [x] T6.1 Viết lại câu hỏi theo ngữ cảnh — agent loop tự viết truy vấn đầy đủ khi gọi search_knowledge
- [x] T6.2 Không dấu, sai chính tả — agent loop viết lại truy vấn có dấu; nhóm no-accents đạt 80–100%
- [x] T6.3 Xếp hạng: đoạn khớp rõ nhất đứng đầu (leadClearMatch trong retrieve.ts)
- [ ] T6.4 Thực thể và cạnh (M) — hoãn: nhóm câu hỏi thông tin đã đạt 100%, chưa có số đo cho thấy cần
- [x] T6.5 Qdrant: không cần lúc này — 277 đoạn, tìm kiếm trung bình 486 ms (phần lớn là gọi embedding), chưa có index ANN và vẫn nhanh

## Giai đoạn 7 — Vận hành thật
- [x] T7.1 Agent loop không giữ trạng thái (đọc hội thoại từ backend) nên chạy được nhiều bản; run treo quá 15 phút tự đóng. Chế độ graph vẫn dùng SQLite
- [x] T7.2 Token và độ trễ mỗi lượt ghi vào agent_runs và log; giới hạn 30 tin/phút mỗi cư dân
- [x] T7.3 Ma trận phân quyền + test từ chối — docs/teams/chien/RBAC_MATRIX_2026-10-03.md
- [ ] T7.4 Một phần: db:verify đã đạt (đếm bảng từ schema thay vì số cứng). Còn lại: migration 0001, 0002, 0007–0011 viết tay nên thiếu snapshot; cần đưa các bảng vh_* vào schema TS rồi sinh lại — việc của cả các team đã thêm migration
- [x] T7.5 Đã có sẵn: backend từ chối khởi động chế độ demo khi host không phải loopback
- [ ] T7.6 Nhập dữ liệu tổ chức thật qua Agent Factory (L, phụ thuộc Team Phái)

## Bổ sung ngày 03/10
- [x] Test đầu-cuối với model giả chạy cho cả `graph` và `loop` (8 test mỗi chế độ)
- [x] File chung của Masterise nạp vào phân khu duy nhất mà đơn vị đó vận hành
- [x] `publish_learned.ps1 -EveryMinutes` tự lặp, không còn bước chạy tay
- [x] Operations hiện đúng yêu cầu khẩn cấp (backend trả `critical`, giao diện từng so với `P0`)
- [x] Câu trả lời khẩn cấp kèm hướng dẫn an toàn do Ban quản lý duyệt (cháy, mùi gas, kẹt thang máy)
- [x] Database demo dựng lại sạch; bản chuẩn để khôi phục: `.local-v3-faker/backups/vinhomes_v3-clean-baseline-*.dump`

## Đợt tiếp theo — cả platform
Tiến độ từng team, các quyết định cần chốt và kế hoạch A (nền chung), B (Supervisor chạy thật), C (Vinhomes vận
hành thật): `docs/teams/chien/TIEN_DO_VA_KE_HOACH_2026-10-03.md`.

- [x] A1 Gộp PR #25 vào `develop` (03/10)
- [ ] A2 Team Phái đưa `agent-factory/` và `security-tools/` vào `develop` (hai PR)
- [ ] A3 Team Đông dọn 5 PR nội bộ
- [ ] A4 Sửa nền kiểm thử: 48 test `app`, 5 test Lễ tân, snapshot migration
- [ ] A5 Chốt 5 quyết định liên team
- [ ] B1 Một phần: Supervisor có binding, run và API riêng (`/internal/coordination/v1`); subagent chưa
- [x] B2 Supervisor thật nhận yêu cầu từ Lễ tân, lưu phiên bền, trả `accepted` (`agent-coordination/src/vinhomes`)
- [ ] B3 Supervisor lập phương án bằng model thật (model thật đã giao việc và nhận phân tích; phương án thuộc M3)
- [ ] B4 Phát hành phiên bản agent; nối lại Agent Factory
- [ ] B5 Cổng tool với 3 port và 2 tool đọc database thật
- [ ] B6 Sub-agent kỹ thuật dùng tool trong một yêu cầu thật
- [x] C1 Đăng nhập thật cho cư dân và nhân viên; luồng 23 bước đạt (`docs/teams/chien/CHAY_DANG_NHAP_THAT.md`)
- [ ] C2 Đóng gói và môi trường chung
- [ ] C3 Một phần: 3 hướng dẫn an toàn của Sapphire đã duyệt; danh sách từ khóa và các phân khu khác chưa
- [ ] C4 Job định kỳ nạp tri thức
- [ ] C5 Giám sát và xoay vòng token
- [ ] C6 Bổ sung dữ liệu, cập nhật bộ 93 câu

## Supervisor và session V2 (kế hoạch `KE_HOACH_SUPERVISOR_GROUPCHAT_SESSION_V2_2026-10-03.md`)
Chi tiết: `docs/teams/chien/SUPERVISOR_SESSION_V2_M0_M1_2026-10-03.md`.

- [x] M0 Baseline, kiểm kê, session và bảng contract
- [x] M1a Runtime nối backend thật cho `ticket_submitted → accepted`, có đối soát khi mất phản hồi
- [ ] M1b Kho PostgreSQL cho checkpoint, inbox, journal; test hai tiến trình
- [x] M2 Một specialist và model thật: admin duyệt là phát hành, agent được mời theo danh mục ticket, agent kỹ
  thuật trả lời trong phòng, Operations hiện phân tích (`docs/teams/chien/SUPERVISOR_SESSION_V2_M2_2026-10-04.md`)
- [ ] M2b Cổng tool cho agent chuyên môn (bắt đầu bằng ba tool đọc của Team Quang)
- [ ] M3 Hỏi lại cư dân, phương án, hai lần duyệt, hoàn tất, hủy
- [ ] M4 Pause, resume, stop và màn quản lý session trên Operations
- [ ] M5 Nghiệm thu lỗi và triển khai giới hạn
