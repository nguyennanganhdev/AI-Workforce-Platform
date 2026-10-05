---
trang_thai: du-lieu-gia-lap-khong-xuat-ban
cap_nhat: 2026-10-05
van_ban: MOCK-PROC-07-v1
issue_code: TECH.PLUMB.SHOWER_SEAL
fixture_only: true
approval_status: not_published
sop_available: false
audience: technician_test_only
version: mock-v1
---
# MOCK-PROC-07 — Quy trình mẫu: vách tắm hở hoặc rò

MẪU GIẢ LẬP để thử luồng kỹ thuật; không phải SOP Vinhomes hay hướng dẫn cư dân tự trám khe.

## Nhận diện và điều kiện dừng
Ghi vị trí mép vách, ngưỡng, chân kính, mạch tường và thời điểm nước xuất hiện; ảnh toàn cảnh và cận cảnh cùng mã ticket. Hỏi khung/kính lỏng, nguy cơ trượt ngã, nước gần điện hoặc thấm xuống căn dưới. Kính có nguy cơ rơi hoặc nước lan phải chuyển người đánh giá khu vực, không tiến hành thử nước tùy tiện.

## Khảo sát và thực hiện
Xác định model vách/phụ kiện, loại gioăng hoặc vật liệu theo manual và bảo hành. Kỹ thuật viên kiểm tra đường nước thực sự: mép vách, độ kín, thoát sàn và nguồn rò khác. Chỉ sau khi định vị nguồn mới lập work order vật tư và phạm vi xử lý; không mặc định mọi rò do silicone. Nếu cần vào khu vực khác, dùng approval và scope tương ứng. Ghi nguyên trạng, nguyên nhân xác nhận, vật tư và người thực hiện.

## Kiểm tra kết quả
Thử nước có kiểm soát theo SOP/manufacturer, ghi điều kiện thử, vị trí quan sát và ảnh sau; kiểm tra cả sàn ngoài vách và khu vực dưới nếu có quyền. Tiêu chí khô/không rò phải do SOP đúng model quy định. Nếu rò vẫn xuất hiện hoặc ảnh không đúng ticket, trả `NEEDS_EVIDENCE`/`HUMAN_REVIEW`; không kết luận chỉ từ một góc ảnh.

## Tình huống phân nhánh
- Nước tràn khi tắm: ghi mép/khe, điểm xuất hiện giọt đầu, thời điểm, sàn trơn và kính có nứt không; không mặc định keo silicone hỏng.
- Kính nứt hoặc phụ kiện lung lay: chuyển người trực, hạn chế sử dụng; không hướng dẫn tự tháo/siết kính.
- Đã trám nhưng rò tái phát: phân biệt vách, ống cấp/thoát và sàn bằng khảo sát phù hợp, không sao chép chẩn đoán cũ.

## Hồ sơ tối thiểu và hậu kiểm
Ghi model/cấu tạo, vị trí cửa, khe nghi rò, ảnh, phạm vi ướt và bảo hành. Kỹ thuật viên dùng phương pháp được SOP/manual cho phép, ghi điểm rò quan sát được, vật tư tương thích và người thực hiện. Không tự đặt thời gian khô keo hoặc cách thử ngâm cho mọi model. Hậu kiểm phải quan sát điểm rò cũ trong điều kiện được phê duyệt; thiếu kết quả thử hoặc nguồn chưa xác định thì không hoàn tất.

## Nguồn
- MOCK-PROC-07-v1: fixture thiết kế từ technical-data/ISSUE_CATALOG.md mục 07 và docs/teams/quang/general.md; không phải văn bản BQL.
