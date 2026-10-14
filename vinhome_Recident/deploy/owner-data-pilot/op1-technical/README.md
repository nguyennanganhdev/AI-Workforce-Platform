# Pilot dữ liệu OP1 — Kỹ thuật

Phạm vi đã chốt với người dùng: **OP1, một phân khu, một tòa, Kỹ thuật**. Chưa có dữ liệu thật; mã phân khu/tòa trong manifest để trống. Không tự chọn tòa hoặc coi tên phân khu tham khảo là mã master chính thức. Các CSV chỉ có header, chưa có người/căn/ca/giá/SLA giả. Bộ trống phải báo `valid=false`.

Đây là **schema v2 dành riêng pilot**, không thay bộ v1 nhiều khu. Cần hoàn thiện và nghiệm thu pilot trước khi thiết kế mở rộng phạm vi v2 sang OP2/3. `data_mode=owner_candidate` nghĩa là dữ liệu đề nghị tiếp nhận, chưa phải chứng nhận của đơn vị vận hành.

## Chuỗi dữ liệu cần điền

| File | Nội dung cần đơn vị chủ dữ liệu cung cấp |
|---|---|
| `operators.csv` | Đơn vị phụ trách thật, mã nội bộ thống nhất, tên pháp lý, tham chiếu đầu mối |
| `zones.csv`, `buildings.csv`, `units.csv` | Một phân khu/tòa và các căn trong phạm vi pilot; mã chính thức, địa chỉ, đơn vị phụ trách |
| `residents.csv` | Tài khoản, căn, quan hệ cư trú, thời hạn, tham chiếu xác minh; không mật khẩu/CCCD/ảnh giấy tờ |
| `coverage.csv` | Tuyến `technical`, đơn vị, route Platform và revision dương đã thống nhất |
| `staff.csv` | Nhân viên chính và người dự phòng cùng phạm vi/chuyên môn, email và capacity |
| `shifts.csv` | Ca có múi giờ, chưa kết thúc, không chồng ca; ca người dự phòng phải phủ ca chính |
| `services.csv` | Dịch vụ Kỹ thuật, điều kiện, phí/VAT, giờ, bảo hành, đặt/hủy, đầu mối và tuyến tương ứng |
| `sops.csv` | Ít nhất một SOP cư dân và một SOP nhân viên cho mỗi dịch vụ; các trường bên dưới |

Mỗi dòng giữ các trường `document_reference`, `approved_by`, `approved_at`, `effective_from`, `effective_until`. Cùng một mã hồ sơ có thể xác nhận nhiều dòng nếu nội dung hồ sơ thực sự bao phủ chúng. Người và email trong cư dân/nhân viên phải tách riêng ở pilot này; đây không phải thiết kế tổng quát cho một người có nhiều vai trò.

`sops.csv`: mã/tên SOP, dịch vụ, audience `resident`/`staff`, loại yêu cầu `incident`/`service_request`, mức ưu tiên; SLA phản hồi/xử lý tính bằng phút; thông tin cần tiếp nhận; an toàn; chuyển cấp; bằng chứng; tiêu chí nghiệm thu; các bước thực hiện. `clock_policy=elapsed` dùng thời gian liên tục; chưa hỗ trợ tính SLA theo lịch làm việc. `approval_policy=resident_quote_and_completion` giữ bước cư dân đồng ý phương án/chi phí và kết quả, không thêm bước BQL duyệt ticket tại Domain.

`system-workflow.json` là mô tả luồng phần mềm để soạn SOP, **không phải SOP vận hành đã được xác nhận**. Không sao chép thành quy định hiện hành khi chưa được đối soát. Phí, giờ và SLA còn trống phải để người chủ dữ liệu quyết định.

## Hồ sơ nguồn và tính toàn vẹn

Điền manifest: mã bộ `bundle_code`, phiên bản, chủ dữ liệu, thời gian xuất có múi giờ, mã bàn giao; `pilot.zone_code`, `pilot.building_code` đúng mã trong CSV. Mọi dòng đều phải nằm trong đúng phạm vi này.

Đặt văn bản được phép bàn giao tại `evidence/` trong bản riêng ngoài Git. Ưu tiên quyết định/biên bản hoặc bản trích đã bỏ thông tin cá nhân không cần thiết; không đính kèm toàn bộ hồ sơ định danh cư dân. Thêm manifest:

```json
"source_documents": [
  {
    "document_reference": "MA_BIEN_BAN_THUC_TE",
    "file": "evidence/owner-approval.pdf",
    "sha256": "HASH_SHA256_CUA_FILE_THUC_TE"
  }
]
```

Lấy hash bằng `Get-FileHash -Algorithm SHA256`. Mỗi `document_reference` trong CSV phải có hồ sơ tương ứng. Hash đúng chỉ chứng minh file không đổi, không chứng minh tính thật hoặc thẩm quyền người ký. Người tiếp nhận vẫn phải đối chiếu văn bản nguồn.

## Tạo và kiểm tra bản riêng

Bản sẵn để điền trên máy: `E:\Vinhomes-Deploy\owner-pilot-20261015\input`. Để tạo bản khác, chạy từ gốc repo:

```powershell
python vinhome_Recident/deploy/prepare-owner-pilot.py --output E:\Vinhomes-Deploy\op1-owner-private
python vinhome_Recident/deploy/validate-owner-data.py --folder E:\Vinhomes-Deploy\op1-owner-private
```

Lệnh tạo từ chối thư mục không trống, giữ nhận xét của người điền. Validator chỉ in số lượng, lỗi theo bảng/dòng và hash; không in tên/email hoặc ghi DB. Bộ v1 vẫn kiểm tra được như cũ, nhưng **không được nhập bằng importer staging v2**.

Sau khi bộ dữ liệu thật qua kiểm tra và được đối chiếu hồ sơ, dùng package API đã cài:

```powershell
python -m vinhomes_api.owner_operational --folder E:\Vinhomes-Deploy\op1-owner-private
# DATABASE_URL được nạp từ cấu hình riêng; không đưa URL chứa mật khẩu lên command line.
python -m vinhomes_api.owner_operational --folder E:\Vinhomes-Deploy\op1-owner-private --apply --actor ID_ADMIN_THUC_TE
```

Phải migrate database trước khi apply. Importer ghi trọn bộ vào `owner_operational_batches`/`owner_operational_records` trong một transaction. Cùng mã/phiên bản/hash thì idempotent; nội dung đổi phải tăng phiên bản. Tài khoản runtime bị thu hồi mọi quyền trên hai bảng; không có MCP export hồ sơ này.

**Staging chưa publish:** importer không tạo tài khoản đăng nhập, gán quyền cư trú, kích hoạt nhân viên, mở tuyến, đưa SOP vào kho trả lời hoặc gửi dữ liệu sang Platform. Chưa có publisher tự động từ staging sang bảng vận hành. Bước chuyển sang master/quyền/knowledge cần thiết kế và nghiệm thu trên bộ dữ liệu thật đã chọn; không dùng importer legacy một site để bỏ qua bước này.

## Nghiệm thu và mở rộng

1. Kiểm tra đủ chuỗi một tòa → căn → cư dân → tuyến Kỹ thuật → nhân viên/ca/dự phòng → dịch vụ → hai audience SOP; hồ sơ nguồn và thời hạn hợp lệ.
2. Nhập staging, nhập lại không nhân đôi; thay dữ liệu cùng phiên bản bị từ chối; lỗi không ghi dở dang; runtime không đọc hồ sơ staging.
3. Khi có master thật, đối soát và publish có kiểm soát; cấp tài khoản qua luồng tài khoản hiện có. Kiểm tra cư dân chỉ thấy căn mình, nhân viên chỉ thấy việc được giao, SOP/giá chỉ đúng khu/tòa/thời hạn.
4. Nối Platform: ticket → grant → giao việc → nhận/ETA → di chuyển/đến nơi → phương án/chi phí → cư dân đồng ý → bằng chứng → Platform cập nhật → cư dân nghiệm thu/xử lý lại. Kiểm thử hai backend thật riêng; không coi staging hoặc kiểm thử giả là luồng thật.
5. Chỉ sau nghiệm thu mới mở thêm dịch vụ/tòa/OP2/3; mỗi phạm vi mới phải có bộ dữ liệu và tuyến/nhân sự riêng.

## Dữ liệu được cung cấp cho Platform

Platform nhận ngữ cảnh ticket và mã tham chiếu, không nhận CSV cư dân/nhân sự/ca trực hay hồ sơ xác minh. Tên hiển thị và quan hệ cư trú hiện có trong snapshot ticket phục vụ hội thoại; không kèm giấy tờ, email, danh sách hộ hoặc thông tin các căn khác. Mô tả do cư dân nhập có thể chứa thông tin cá nhân; cần hạn chế ghi log/chia sẻ theo phạm vi ticket.

Staff được tìm qua MCP trong phạm vi ticket và quyền tương ứng; Platform quản lý session, giao việc, tiến độ và phản hồi. Domain giữ dữ liệu nguồn, quyền truy cập, ảnh và quyết định của cư dân. BQL sử dụng Platform, không thêm role BQL ở Domain. Travel mock tiếp tục tách khỏi pilot Kỹ thuật.
