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
- [ ] T2.1 Lễ tân mở yêu cầu hỏi đáp khi không có nguồn (M)
- [ ] T2.2 Tin nhắn từ session về chat cư dân (M)
- [ ] T2.3 Màn tin nhắn session trong Operations (M)

## Giai đoạn 3 — Agent do model dẫn dắt
- [ ] T3.1 Model adapter gọi tool (S)
- [ ] T3.2 Bộ tool cho agent, có test bất biến (M)
- [ ] T3.3a Vòng agent + cổng policy (M)
- [ ] T3.3b Bước kiểm tra đầu ra (M)
- [ ] T3.4 Chạy song song, so điểm với graph cũ (S)

### Điểm dừng 2 — quyết định bật agent mới

## Giai đoạn 4 — Bộ nhớ dài hạn
- [ ] T4.1 Bộ nhớ cư dân từ ticket đã đóng (M)
- [ ] T4.2 Cư dân xem và xóa bộ nhớ của mình (S)

## Giai đoạn 5 — Tự thẩm định, tự cải thiện
- [ ] T5.1 Thu tín hiệu ngầm (S)
- [ ] T5.2 Agent thẩm định tri thức, phân mức A/B/C (M)
- [ ] T5.3 Điểm tin cậy vào thứ hạng; tự nâng/hạ hạng (M)
- [ ] T5.4 Ngân hàng ví dụ mẫu từ lần BQL sửa phân loại (S)
- [ ] T5.5 Nút duyệt một chạm cho mức C (S)

## Giai đoạn 6 — Tối ưu truy xuất (theo số đo)
- [ ] T6.1 Viết lại câu hỏi theo ngữ cảnh (S)
- [ ] T6.2 Tìm không dấu, sai chính tả (S)
- [ ] T6.3 Xếp hạng lại (S)
- [ ] T6.4 Thực thể và cạnh, mở rộng láng giềng (M)
- [ ] T6.5 Đo và quyết định Qdrant (XS)

## Giai đoạn 7 — Vận hành thật
- [ ] T7.1 Phiên Lễ tân trên PostgreSQL; dọn run treo (M)
- [ ] T7.2 Chi phí, độ trễ, giới hạn tần suất (S)
- [ ] T7.3 Ma trận phân quyền + test từ chối (M)
- [ ] T7.4 Một đường migration duy nhất (M)
- [ ] T7.5 Tắt đăng nhập demo ở bản chạy thật (S)
- [ ] T7.6 Nhập dữ liệu tổ chức thật qua Agent Factory (L, phụ thuộc Team Phái)
