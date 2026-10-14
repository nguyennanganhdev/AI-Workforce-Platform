# Bàn giao dữ liệu vận hành OP1/2/3

Các CSV trong thư mục này chỉ có tiêu đề, **không có người, căn/lô hay ca giả**. Sao chép cả thư mục sang vị trí riêng ngoài Git, ví dụ `E:\Vinhomes-Deploy\owner-data-private`, rồi điền dữ liệu được đơn vị vận hành cho phép bàn giao. Không ghi mật khẩu, CCCD, số tài khoản hoặc ảnh giấy tờ vào CSV.

Nếu chưa có dữ liệu được xác nhận, bắt đầu từ [bộ 113 mục đề xuất chờ đơn vị vận hành đối soát](../owner-data-proposals/20261014/README.md). Bộ đề xuất có dữ liệu tham khảo và câu hỏi cần chốt; bộ CSV vận hành bên dưới chỉ dùng sau khi nhận được hồ sơ thật.

## Điền và kiểm tra

1. `manifest.json`: chọn `site_codes` thuộc `ocean-park-1`, `ocean-park-2`, `ocean-park-3`; điền đơn vị chủ dữ liệu, ngày xuất có múi giờ, phiên bản và mã biên bản bàn giao. Có thể kiểm tra từng khu trước bằng cách chỉ chọn khu đó.
2. `operators.csv`: mã đơn vị, tên pháp lý và mã đầu mối liên hệ. Tên dự án/chủ đầu tư trên website không tự xác nhận đơn vị vận hành từng tòa. Không dùng `Local Management` như pháp nhân thật.
3. `zones.csv`, `buildings.csv`, `units.csv`: mã chính thức, quan hệ site → phân khu → tòa/dãy → căn/lô, địa chỉ hiện hành, đơn vị phụ trách. Nhà thấp tầng không có tòa/dãy có thể để `building_code` trống; vẫn phải có phân khu. Loại căn/lô: `apartment`, `villa`, `shophouse`, `land`.
4. `coverage.csv`: tuyến Kỹ thuật/An ninh/Vệ sinh (`technical`, `security`, `sanitation`), địa bàn, đơn vị và route/revision đã chốt với Platform. Mẫu không tạo vai trò BQL tại Domain.
5. `residents.csv`: mã tài khoản chủ quản, tên, email đăng nhập, căn/lô, quan hệ `owner`/`tenant`/`household`, hiệu lực cư trú, mã hồ sơ đã xác minh. Chỉ dẫn tới hồ sơ do đơn vị giữ, không sao chép giấy tờ định danh. Không tự cấp mật khẩu từ dữ liệu import.
6. `staff.csv`: mã nhân viên, email, chuyên môn, đơn vị, phạm vi, năng lực đồng thời và mã nhân viên dự phòng. Phiên bản mẫu này mô tả một phạm vi/chuyên môn cho mỗi nhân viên trong mỗi khu; trường hợp nhiều phạm vi cần tổng hợp/xác nhận trước khi thiết kế import tương ứng. Nhân viên dự phòng phải khác người, cùng khu/phân khu/tòa, đơn vị và chuyên môn.
7. `shifts.csv`: từng ca bắt đầu/kết thúc có múi giờ; dùng `+07:00` hoặc `Z`. Mã nhân viên phải thống nhất giữa các khu; một người không có hai ca chồng nhau. Mẫu chưa biểu diễn lịch tuần lặp lại hoặc nghỉ phép; đơn vị phải xuất các ca thực tế trong khoảng bàn giao.
8. `services.csv`: tên/mã, phạm vi, đơn vị, điều kiện sử dụng, phí/VAT, giờ, bảo hành, đặt/hủy và mã liên hệ. `fee_policy`: `free` cần `fee_amount=0`, `fixed` cần số tiền, `quote` để số tiền trống và yêu cầu báo giá theo quy trình. `currency=VND`. Không suy ra miễn phí từ việc chưa có bảng giá. Nội dung `operating_hours`, `warranty_policy`, `booking_policy`, `cancellation_policy`, `eligibility` cần quy định thực tế hoặc văn bản xác nhận không áp dụng.
9. Mỗi dòng có `document_reference`, `approved_by`, `approved_at`, `effective_from`, `effective_until`; ngày/giờ dùng ISO 8601 có múi giờ. `effective_until`/`valid_until` có thể trống khi không ấn định kết thúc. Bộ kiểm tra này dành cho hồ sơ đang có hiệu lực; dữ liệu lịch sử/tương lai cần bàn giao riêng.

```powershell
python vinhome_Recident/deploy/validate-owner-data.py --folder E:\Vinhomes-Deploy\owner-data-private
```

Lệnh chỉ đọc file và báo số lượng/lỗi theo số dòng, không in tên/email, không gọi API/model và **không ghi DB**. Mẫu trống phải trả `valid=false`; chỉ có header không chứng minh đã bàn giao dữ liệu. Công cụ kiểm tra mã theo khu, liên kết địa bàn/đơn vị/route, quan hệ cư trú, thời hạn, ca chồng nhau, chuyên môn/phạm vi dự phòng và biểu phí.

Kết quả `valid=true` chỉ xác nhận hình thức và liên kết trong gói, **không chứng minh người duyệt hoặc hồ sơ là thật**. Chủ dữ liệu phải đối chiếu văn bản nguồn và danh sách trên hệ thống chủ quản. Sau đó mới viết/chạy import vào staging, kiểm tra quyền, nghiệm thu và publish. Importer legacy một site hiện **không dùng cho bộ mẫu này**; chưa có bước tự kích hoạt tài khoản, đặt mật khẩu, giao ca hoặc bật tuyến production.

## Dữ liệu công khai đã nghiên cứu

Danh mục nguồn tại `deploy/reference-data/owner-public-catalog-20261014.json` là tham khảo địa bàn/tiện ích có nguồn Vinhomes, không phải danh sách đầy đủ căn hộ hoặc dịch vụ vận hành. Mã `record_code` dùng nội bộ để quản lý tài liệu; chỉ `official_code` có giá trị khi nguồn thực sự ghi mã. Chưa xác nhận đơn vị quản lý, cư trú, nhân sự, quyền vào tiện ích, phí, giờ hoặc tình trạng mở cửa. Không copy tên tiện ích công khai vào bảng dịch vụ đã duyệt mà bỏ qua bước xác nhận.
