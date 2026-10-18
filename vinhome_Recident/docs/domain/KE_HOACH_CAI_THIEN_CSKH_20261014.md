# Cải thiện Reception CSKH — 14/10/2026

## Phạm vi và tiêu chí nghiệm thu

Làm trên `dev_Vinhome`, dự án chính. Không sửa platform, không mở tư vấn du lịch toàn Hà Nội và không thêm quyền tạo ticket vào MCP platform. Giữ 5 công cụ Reception và 7 công cụ MCP platform.

1. Tra cứu đúng dịch vụ/tiện ích với câu tự nhiên và không dấu, kể cả khi embeddings lỗi; giữ tenant/audience/zone/building scope.
2. Bật tìm kiếm ngữ nghĩa bằng cấu hình embeddings riêng, giữ `text-embedding-3-large`,1536 chiều; đối chiếu vector hiện hữu trước khi dùng, không đổi mô hình hoặc trộn vector.
3. Giới thiệu được chức năng ứng dụng và đúng nhóm yêu cầu đang bật; không hứa thực thi booking/thẻ/khách bằng một công cụ không có.
4. Tài liệu thiếu phê duyệt/nguồn/hiệu lực được trình bày là tham khảo; không biến cờ `unverified=false` thành bằng chứng đã được BQL duyệt.
5. Khi thiếu chi tiết, hỏi làm rõ hoặc hướng dẫn bước tiếp theo cụ thể; không liên tục đẩy cư dân về BQL bằng một câu mẫu chung.

## Triển khai

| Bước | Công việc | Kiểm chứng |
|---|---|---|
| 1 | Thêm regression cho câu trong ảnh, biến thể không dấu, phạm vi cư trú và độ tin cậy nguồn | PostgreSQL riêng, embeddings giả; không gọi Agent/provider ngoài phạm vi CSKH |
| 2 | Chuẩn hóa từ truy vấn, bổ sung thông tin provenance, giữ ngưỡng an toàn và fallback | Kiểm tài liệu đứng đầu và trường nguồn/hiệu lực, không lộ tài liệu nơi khác |
| 3 | Chỉnh prompt/context và cách dẫn nguồn Reception | Kiểm adapter/prompt bằng dữ liệu giả; kiểm lời giới thiệu đúng 2 nhóm đang bật |
| 4 | Xác minh key embeddings/quyền model và vector đang dùng, bật env riêng | Lời gọi embeddings tối thiểu, không đổi key/model chat hoặc cấu hình toàn cục |
| 5 | Build image API/Reception, backup và deploy có rollback | Image/source hash, health, dữ liệu nghiệp vụ, CSKH qua HTTPS |
| 6 | Báo cáo bằng evidence hiện tại | Tách kết quả đã deploy, test đạt và dữ liệu thật còn chờ chủ dự án |

## Dữ liệu cần chủ dự án/BQL cung cấp

Danh mục dịch vụ/tiện ích chính thức theo phân khu/tòa; bảng phí, giờ hoạt động, điều kiện sử dụng; đầu mối liên hệ; mã văn bản/nguồn và người xác nhận; ngày hiệu lực/hết hiệu lực. Chưa có thì không tự điền hoặc tự gắn nhãn đã duyệt. Bổ sung dữ liệu chính thức là phần bàn giao tiếp theo, không chặn sửa hệ thống tra cứu hiện tại.

Kết quả cuối được ghi tại `BAO_CAO_CAI_THIEN_CSKH_20261014.md`; credential, account và output riêng giữ ngoài Git.
