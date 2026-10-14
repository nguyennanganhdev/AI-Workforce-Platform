# Nghiệm thu bộ dữ liệu pilot OP1/Kỹ thuật — 15/10/2026

## Phạm vi và kết quả

Người dùng chọn OP1/Kỹ thuật trước và xác nhận **chưa có dữ liệu thật**. Lượt này hoàn thiện bộ đầu vào, kiểm tra chất lượng và nhập staging riêng; kiểm thử bằng dữ liệu giả trong PostgreSQL tạm. Không nạp cư dân, căn, nhân viên, ca trực, biểu phí hoặc SOP giả vào VPS. Không chạy Agent/model hay gọi nhà cung cấp thật.

Đã bổ sung [bộ pilot schema v2](../../deploy/owner-data-pilot/op1-technical/README.md): 10 CSV, manifest phạm vi một phân khu/tòa và nguồn bằng chứng; khung luồng phần mềm để soạn SOP. Bản riêng để điền nằm tại `E:\Vinhomes-Deploy\owner-pilot-20261015\input`. Các CSV chỉ có header; mã tòa/phân khu, hồ sơ cá nhân, phí/giờ/SLA đều chưa được tự điền.

## Thay đổi đã thực hiện

- Đưa validator dùng chung vào `vinhomes_api.owner_bundle`; script deploy vẫn dùng được với bộ v1. Bộ v2 giới hạn OP1, một phân khu/tòa, category `technical`.
- Kiểm tra chuỗi đơn vị → địa bàn → căn → cư trú → tuyến → nhân viên/ca/dự phòng → dịch vụ → SOP cư dân/nhân viên. Giữ kiểm tra liên kết, thời hạn, email, capacity, ca chồng nhau và chính sách phí từ v1.
- Thêm SOP có audience, điều kiện tiếp nhận, an toàn, chuyển cấp, bằng chứng, tiêu chí nghiệm thu, SLA và sự đồng ý cư dân. Mỗi dịch vụ cần cả audience cư dân lẫn nhân viên. Chỉ chấp nhận đồng hồ SLA `elapsed`; chưa tính SLA theo lịch làm việc.
- Mỗi tham chiếu hồ sơ phải nối tới file trong `evidence/` có SHA-256 đúng. Snapshot gắn byte manifest/CSV/hash hồ sơ. Giá trị CSV/hash không tự chứng minh tính thật hoặc thẩm quyền người ký.
- Thêm `prepare-owner-pilot.py`: tạo bộ trống ngoài Git, kèm README/khung quy trình; từ chối ghi đè bản người dùng đã điền.
- Thêm migration `0022_owner_operational_staging.sql` với `owner_operational_batches` và `owner_operational_records`, tenant RLS bật và FORCE. Runtime bị `REVOKE ALL` trên cả hai bảng sau grant tổng quát.
- Thêm importer `owner_operational`: mặc định offline/dry-run; `--apply` cần owner DB và admin đang active thuộc tenant. Nhập atomic/idempotent, đổi nội dung cùng mã/phiên bản bị từ chối. Dữ liệu `synthetic_test` chỉ được ghi vào DB có tên test riêng theo mẫu UUID.
- Không xuất dữ liệu staging sang Platform hoặc đưa SOP staging vào kho trả lời. Không thay 14 tool MCP hiện có, không thêm role BQL, không tự kích hoạt tài khoản, cư trú, nhân sự hoặc route.
- Bổ sung dependency `tzdata` riêng Windows sau khi kiểm thử hồi quy phát hiện thiếu dữ liệu múi giờ cho kho tri thức.

## Kiểm thử

**73 kiểm thử đạt** trên PostgreSQL tạm và môi trường Python riêng: bộ pilot, bàn giao v1, đề xuất owner, MCP v2, knowledge và schema contract. Ruff đạt cho các Python file thay đổi. Có một cảnh báo Starlette về TestClient; không có lỗi còn lại trong bộ đã chạy.

Happy case dùng dữ liệu test được gắn nhãn rõ:

1. Một khu OP1, một phân khu, một tòa, một căn, một cư dân; một tuyến/dịch vụ Kỹ thuật; hai nhân viên chính/dự phòng, hai ca; hai SOP tương ứng audience cư dân/nhân viên. Tổng **13 dòng trong 10 dataset**.
2. Validator xác nhận đủ liên kết, ca dự phòng phủ ca chính, SLA hợp lệ, chính sách giữ sự đồng ý cư dân và file bằng chứng có hash đúng.
3. Tạo DB riêng từ toàn bộ migrations/bootstrap, chỉ thêm một admin test. Nhập staging thành công và nhập lại không nhân đôi.
4. Runtime API không đọc được cả hai bảng staging. Các bảng căn, cư trú, nhân viên, ca, coverage, account và command Platform vẫn trống; không tự kích hoạt vận hành.
5. Thay dữ liệu dưới cùng phiên bản hoặc dùng actor không phải admin bị từ chối. Một batch/13 dòng vẫn nguyên vẹn.
6. Các ca lỗi được kiểm tra: khác phạm vi/category, thiếu tuyến/SOP/bằng chứng, hash bị đổi, đường dẫn vượt thư mục, bỏ qua cư dân duyệt, SLA sai, ca hết hạn/thiếu dự phòng, tài khoản test trong gói owner và dữ liệu giả trỏ vào DB production.

Container PostgreSQL test và volume ẩn danh riêng đã được gỡ sau kiểm thử. Log riêng: `E:\Vinhomes-Deploy\owner-pilot-20261015\pytest.private.log`. Không sửa container hoặc dữ liệu production.

## Giới hạn và bước tiếp theo

**Đây là nghiệm thu chất lượng đầu vào và staging; chưa phải nghiệm thu dịch vụ thật hay kết nối Platform thật.** Migration/module mới ở source nhánh `dev_Vinhome`, chưa triển khai lên VPS trong lượt này.

Chưa có publisher từ staging sang master, tài khoản/quyền và knowledge vận hành. Cần thiết kế bước đối soát/publish trên bộ dữ liệu thật, xử lý mapping với địa bàn tham khảo hiện có, version/hiệu lực và thu hồi dữ liệu cũ; không dùng importer legacy một site để bỏ qua việc này.

Tiếp theo cần đơn vị chủ dữ liệu cung cấp một tòa đã chọn: mã master và căn, cư trú đã xác minh, nhân viên/ca/dự phòng, tuyến Platform, dịch vụ/phí/giờ/bảo hành/đặt-hủy, SOP/SLA và hồ sơ nguồn được phép bàn giao. Sau đó kiểm tra staging → đối soát/publish → quyền → luồng resident/staff → nối hai backend Platform/Domain. BQL sử dụng Platform; cư dân giữ quyền quyết định phương án/chi phí và kết quả.

Platform nhận ngữ cảnh ticket và MCP grant; không nhận gói CSV hoặc hồ sơ xác minh hàng loạt. Khi mở rộng OP2/3 cần nâng profile v2 và nghiệm thu từng phạm vi; không chỉ đổi `site_codes` để bỏ giới hạn pilot. Tài liệu/database nghiệm thu ngày 14/10 là snapshot lượt trước, chưa bao gồm hai bảng staging mới trên VPS.
