# Bộ dữ liệu đề xuất OP1/2/3 — chờ đơn vị vận hành xác nhận

Ngày chuẩn bị: **14/10/2026**. Đây là hồ sơ đối soát, không phải dữ liệu đã được đơn vị vận hành duyệt. Không có tài khoản, người, căn/lô, ca trực, mức phí hoặc giờ phục vụ được tự tạo. Không nạp bộ này vào production.

## Mở file nào trước

Mở **`review-register.csv`** bằng Excel hoặc trình đọc CSV UTF-8. Lọc `site_code` để xem từng khu và `dataset` để xem từng nhóm. Bảng có **113 mục**; mọi `decision` đang là `pending`, người duyệt và ngày duyệt để trống.

| Khu | Địa bàn tham khảo | Dịch vụ/tiện ích đề xuất | Yêu cầu bố trí nhân sự | Yêu cầu cấp dữ liệu |
|---|---:|---:|---:|---:|
| OP1 | 39 | 11 | 3 | 5 |
| OP2 | 8 | 10 | 3 | 5 |
| OP3 | 8 | 13 | 3 | 5 |
| Tổng | 55 | 34 | 9 | 15 |

- **55 mục địa bàn:** 25 tên phân khu và 30 mã tòa công khai OP1. Đây là danh sách một phần; OP2/3 chưa có danh sách tòa/dãy/căn/lô đầy đủ. `official_code` chỉ có khi nguồn thực sự ghi mã; `proposal_code`/`proposal_id` là mã hồ sơ nội bộ, không được dùng thay mã master. `public_parent_name` chỉ là quan hệ được nguồn công khai mô tả, cần đối chiếu master hiện hành.
- **34 mục dịch vụ:** 25 tiện ích/địa điểm công khai và 9 đề xuất theo khả năng phần mềm (Kỹ thuật, An ninh, Vệ sinh × 3 khu). Trường học, đại học, phòng khám và tiện ích du khách cần xác nhận đơn vị sở hữu/quyền cư dân; không mặc định là dịch vụ do BQL cung cấp. Các nhóm phần mềm không phải cam kết dịch vụ của khu.
- **9 mục yêu cầu nhân sự:** xác định thông tin cần đơn vị vận hành chốt cho từng chuyên môn/khu. Đây không phải 9 nhân viên hoặc 9 vị trí đã được duyệt. Số người, ca, capacity và dự phòng còn trống.
- **15 yêu cầu cấp dữ liệu:** mỗi khu cần 5 bộ: pháp nhân/phạm vi vận hành, danh sách căn/lô, hồ sơ cư trú, danh sách nhân sự, lịch trực. Không có cư dân hoặc nhân viên giả để điền đầy file.

## Các file trong mỗi khu

Mỗi thư mục `ocean-park-1`, `ocean-park-2`, `ocean-park-3` có:

| File | Đơn vị/người cần xác nhận | Nội dung cần điền/đối soát |
|---|---|---|
| `geography.csv` | Người được ủy quyền quản lý master và bàn giao địa bàn | Tên/mã chuẩn, quan hệ cha-con, địa chỉ hiện hành, tình trạng hoạt động, đơn vị quản lý; thêm các địa bàn còn thiếu trong bản đối soát riêng |
| `services.csv` | Chủ dịch vụ và người phê duyệt quy định vận hành | Có cung cấp không, phạm vi, điều kiện/quyền sử dụng, đơn vị, phí/VAT, giờ, bảo hành, đặt/hủy, danh bạ, SOP/SLA, route và các bước cư dân đồng ý |
| `staffing_requirements.csv` | Đơn vị quản lý nhân sự và điều phối vận hành | Chuyên môn, phạm vi, số lượng cần bố trí, capacity, chứng chỉ/năng lực, dự phòng và văn bản lịch ca |
| `data_requests.csv` | Đơn vị sở hữu từng nguồn dữ liệu | Điền `data_owner`, đầu mối/hình thức bàn giao và `secure_handoff_reference` trỏ tới file/cổng được phép truy cập |

CSV dùng UTF-8 có BOM để đọc được tiếng Việt trong Excel. Ô trống nghĩa là **chưa biết/chưa xác nhận**; không hiểu thành miễn phí, không giới hạn, hoạt động 24/7 hay không cần duyệt. Có thể điền nội dung đối soát trong bản sao riêng; giữ nguyên `proposal_id` để nối với bảng duyệt.

## Cách ghi nhận xác nhận

1. Người có thẩm quyền đối chiếu dữ liệu với hồ sơ chủ quản hiện hành, không chỉ với bài giới thiệu dự án. URL, ngày nguồn và trường `requires_confirmation` có trong từng file theo khu.
2. Trong `review-register.csv`, chọn `decision` là `confirmed`, `rejected` hoặc `needs_change`. Nếu chưa đủ căn cứ, giữ `pending`/`needs_change`; ghi trường còn thiếu trong `notes`.
3. Nếu xác nhận, điền `reviewer`, `reviewed_at` có múi giờ, `document_reference`, `effective_from` và `effective_until` nếu có. `correction` ghi thay đổi mã/tên/phạm vi hoặc đường dẫn bản đối soát riêng. Hồ sơ nguồn phải chứng minh thẩm quyền và nội dung được duyệt; tự điền tên người duyệt không thay thế bằng chứng.
4. Một tên phân khu/tòa được xác nhận không đồng nghĩa mọi căn/lô bên trong hoặc mọi dịch vụ đều được xác nhận. Duyệt theo từng mục, từng khu và từng trường còn thiếu.
5. Danh sách người/cư trú/ca trực thật bàn giao riêng bằng [bộ 9 CSV vận hành](../../owner-data-templates/README.md), lưu ngoài Git. Chỉ điền các trường cá nhân cần thiết; không gửi mật khẩu, CCCD, ảnh giấy tờ hoặc danh sách cá nhân vào chat/Git.

**Chỉnh `decision` trong bảng không tự nâng quyền, đổi trạng thái JSON hay nhập database.** Bộ hồ sơ luôn có `review_status=pending_owner_review`, `operational_import_allowed=false`. Bước tiếp theo là kiểm tra bằng chứng, chuyển phần được xác nhận sang bộ dữ liệu vận hành, chạy kiểm tra offline/staging, kiểm tra quyền rồi nghiệm thu trước khi publish. Importer legacy một site không dùng cho bộ đề xuất này.

## Điều kiện để mở vận hành từng khu

- Có master địa bàn và đơn vị quản lý thực tế; không dùng placeholder `Local Management` như pháp nhân đã được xác nhận.
- Cư dân có tài khoản và quan hệ cư trú hiệu lực, được người có thẩm quyền xác minh.
- Có nhân sự thật, chuyên môn, phạm vi, ca trực, capacity và dự phòng phù hợp.
- Dịch vụ có quy định/biểu phí/giờ/SOP/SLA và bước đồng ý của cư dân rõ ràng. Trường không áp dụng phải được xác nhận, không tự suy luận từ ô trống.
- Route, grant và revision được chốt với Platform. Platform quản lý session, giao việc và tiến độ; staff phản hồi tại Domain, cư dân quyết định tại các bước cần đồng ý. Bộ hồ sơ không cấp lại vai trò đăng nhập BQL cho Domain và không mở thêm MCP.

## Nguồn, kiểm tra và tái tạo

Nguồn nền: [catalog tham khảo có nguồn từng mục](../../reference-data/owner-public-catalog-20261014.json), [nghiên cứu nguồn](../../../docs/domain/RESEARCH_OWNER_DATA_CATALOG_20261014.md), và khả năng phần mềm trong `services/vinhomes-api/src/vinhomes_api/bootstrap.py`. Không nghiên cứu thêm hay coi thông tin marketing là chính sách hiện hành trong lượt chuẩn bị này.

`proposals.jsonl` là snapshot máy đọc, một mục mỗi dòng; `manifest.json` ghi số lượng và SHA-256 từng file dữ liệu lúc tạo. Sau khi reviewer sửa file, hash sẽ thay đổi; giữ snapshot gốc và bàn giao bản đối soát riêng kèm phiên bản, không sửa manifest để giả thành bản gốc.

```powershell
python vinhome_Recident/deploy/prepare-owner-proposals.py --catalog vinhome_Recident/deploy/reference-data/owner-public-catalog-20261014.json --output E:\Vinhomes-Deploy\owner-proposals-new
```

Lệnh không gọi mạng, API/model hoặc database. Thư mục đầu ra phải trống để tránh ghi đè nhận xét đã có. **20 kiểm thử offline đạt** cho bộ đề xuất và bộ tiếp nhận vận hành, bao gồm kiểm tra gói đề xuất bị từ chối bởi validator vận hành, tính tái tạo và bảo toàn file người duyệt.
