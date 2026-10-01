# Giao diện tạm để chạy thử API V3

> Đã chuyển `/demo/ui` sang giao diện người dùng nghiệp vụ. Hướng dẫn hiện tại ở [HUONG_DAN_GIAO_DIEN_NGUOI_DUNG_DEMO.md](HUONG_DAN_GIAO_DIEN_NGUOI_DUNG_DEMO.md). Nội dung bên dưới mô tả console kỹ thuật trước đây; file chạy nay nằm tại `services/CHAY_DEMO_API.cmd`.

## Mở giao diện

**Cách nhanh:** mở file **`CHAY_DEMO_API.cmd`** tại gốc dự án bằng double-click.
File tự mở Docker Desktop nếu cần, chạy PostgreSQL V3 và FastAPI, rồi mở trình duyệt tại **http://localhost:8000/demo/ui**.

- Mở lần nữa sẽ dùng lại API demo đang chạy, không tạo service thứ hai.
- Khởi động thường không seed lại hoặc xóa dữ liệu demo.
- Lần đầu chưa có cấu hình database: cần Docker Desktop, Python >=3.11, Bun và dependency server; launcher cài dependency Python rồi chạy setup/migration/seed.
- Có thể đóng cửa sổ CMD sau khi báo sẵn sàng; API và database vẫn chạy.
- API chạy ẩn, log tại `services/vinhomes-api/.local-v3-faker/demo-api.stdout.log` và `demo-api.stderr.log` nếu launcher tạo process mới.
- Nếu có lỗi, CMD giữ cửa sổ để đọc. Nếu cổng 8000 đang chạy service khác hoặc API cũ chưa có trang demo, dừng service đó rồi mở lại CMD.

Tại thư mục gốc dự án, chạy trong PowerShell:

```powershell
# Chỉ cần khi chưa tạo database demo; cần Docker đang chạy.
& ./services/vinhomes-api/scripts/setup_demo_database.ps1

# Chạy API với database demo đã có.
& ./services/vinhomes-api/scripts/start_demo.ps1
```

Mở **http://localhost:8000/demo/ui**. Nếu API đang chạy từ trước khi thêm giao diện, dừng bằng Ctrl+C rồi chạy lại. Swagger vẫn ở http://localhost:8000/docs.

Giao diện được FastAPI phục vụ cùng cổng 8000, không cần chạy frontend hoặc Hono riêng cho trang này. Chỉ được bật khi `VINHOMES_API_DEMO_MODE` đang bật; quyền của từng request vẫn được backend kiểm tra qua `X-Demo-Actor`. Cơ chế chọn vai trò này chỉ dành cho demo cục bộ.

## Cách chạy một luồng

1. Bấm **Lấy dữ liệu mẫu / ID** để xem các site, building, domain, category, scope, staff và căn hộ của vai trò hiện tại.
2. Chọn bước trong phần **Thứ tự chạy các luồng**. Trang mở endpoint và chọn vai trò gợi ý. Vai trò gợi ý cần phù hợp với tài nguyên cụ thể; backend là nơi quyết định quyền thực tế.
3. Điền các tham số đường dẫn và query. Trường có dấu `*` là bắt buộc.
4. Với thao tác ghi, sửa mẫu JSON: ID phải lấy từ dữ liệu thật, enum và cấu trúc xem ở **Schema request**. Mẫu được sinh từ schema, không phải dữ liệu nghiệp vụ đảm bảo hợp lệ.
5. Bấm **Gửi request**, đọc HTTP status và phản hồi.
6. Bấm **Dùng giá trị** cạnh ID/version trong phản hồi, đặt tên đúng với trường cần dùng: `channel_id`, `ticket_id`, `work_order_id`, `assignment_id`, `approval_id`, `ticket_version`, `work_order_version`…
7. ID đã lưu tự điền vào tham số khi mở endpoint tiếp theo. Với JSON, bấm **Điền lại mẫu theo schema** để áp dụng những giá trị đã lưu; nút này thay nội dung JSON đang nhập.
8. Đọc lại chi tiết ticket/work order sau mỗi thao tác để lấy version mới. Khi gặp `409`, không gửi lại với version cũ.

Ví dụ cơ bản: cư dân tạo chat → lưu `channel_id` → gửi tin nhắn → tạo ticket → lưu `ticket_id` → BQL tiếp nhận → đọc ticket → tạo work order → mời nhân sự → kỹ thuật nhận việc → cập nhật trạng thái theo quy tắc backend → tải ảnh và gắn evidence → hoàn thành → cư dân xác nhận.

## Các luồng trên trang

- Cư dân, chat, tạo ticket, tìm BQL và tiếp nhận.
- Assessment, triage, review, công việc, nhân sự và nhận/từ chối phân công.
- Xin khóa nước, phê duyệt, thông báo, khóa và mở lại nước.
- Upload ảnh, evidence, hoàn công và xác nhận của cư dân.
- QC, làm lại, vệ sinh, nhà thầu và ngân sách.
- Checkpoint, sự cố an ninh và bàn giao ca.
- Phòng BQL, tin nhắn, mention, tìm tri thức, duyệt memory.
- Báo cáo tần suất sự cố, doanh thu hóa đơn, xuất DOCX và thông báo.

Thanh bên lấy **toàn bộ endpoint đang có trong OpenAPI**, gồm cả các endpoint đọc dữ liệu không nằm trong hướng dẫn từng bước. Dùng tìm kiếm và lọc nhóm để mở chúng. Khi backend bổ sung endpoint, tải lại trang để thấy endpoint mới.

## Ảnh và báo cáo

- Endpoint upload dùng bytes trực tiếp: chọn ảnh PNG/JPEG/WebP; trang tự điền `filename` và `mimeType`. Điền ticket ID và purpose trước khi gửi. Tối đa 10 MB theo API hiện có.
- Upload tạo file; phải gọi endpoint evidence để gắn file vào công việc nếu luồng yêu cầu.
- Chọn endpoint kết thúc bằng `.docx`, điền query và gửi. Bấm **Tải file phản hồi**.

## Phân biệt kết quả

- `2xx`: server đã trả thành công; kiểm tra trạng thái mới trong phản hồi hoặc đọc lại tài nguyên.
- `403/404`: kiểm tra vai trò và phạm vi tài nguyên.
- `409`: version/trạng thái hoặc quy tắc nghiệp vụ không cho phép thao tác; đọc chi tiết lỗi và dữ liệu mới.
- `422`: payload hoặc tham số chưa đúng schema.
- `503`: kiểm tra database/config/service.
- Timeout/mất kết nối: thao tác ghi có thể đã được server xử lý. Đọc lại dữ liệu trước khi thử lại; trang không tự retry.

## Giới hạn

Đây là bảng điều khiển thử API, chưa phải giao diện sản phẩm. Người thử chủ động điền dữ liệu và chuyển bước; trang không tự chạy một chuỗi ghi dữ liệu. ID và tối đa 50 phản hồi gần nhất chỉ giữ trong bộ nhớ trang; tải lại sẽ mất, còn dữ liệu nghiệp vụ đã ghi vẫn ở PostgreSQL. Không có nút reset database.

Trang giúp gọi các API đã có; không thay thế việc hoàn thiện endpoint/seed còn thiếu trong kế hoạch V3. Các luồng chưa có endpoint vẫn cần triển khai backend. Chưa có kiểm chứng trực quan trên trình duyệt trong task này.
