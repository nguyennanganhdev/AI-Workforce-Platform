# Đánh giá data ticket công khai để làm mẫu

Rà soát 2026-10-01. Đây là **catalog dữ liệu** chứ chưa phải bản sao ticket đã tải. Không có dòng dữ liệu thực từ NYC/Vinhomes được thêm vào repo này. Truy cập API NYC từ môi trường hiện tại không thành công; đồng thời trang dataset HPD ghi `License: unspecified`, nên không tự ý nhập hàng loạt bản ghi. Thông tin dưới đây chỉ dùng để thiết kế schema/đầu mối xin dữ liệu.

| Dataset chính thức | Độ hữu ích | Giới hạn / quyết định |
| --- | --- | --- |
| [NYC HPD Housing Maintenance Code Complaints and Problems](https://data.cityofnewyork.us/Housing-Development/Housing-Maintenance-Code-Complaints-and-Problems/ygpa-z7cr) | Trang metadata công bố 33 cột, khoảng 16,3 triệu hàng, mỗi hàng là một vấn đề và có `problem_id`, `complaint_id`, `building_id`, thời điểm, loại/trạng thái; minh họa đúng quan hệ complaint → nhiều problem. | Không có ảnh trước/sau, thao tác sửa, asset model, SOP từng tòa hoặc chi phí Vinhomes; license không xác định tại thời điểm rà soát. Chưa ingest record. |
| [NYC HPD Open Data](https://www.nyc.gov/site/hpd/about/open-data.page) | Mô tả khiếu nại có thể gắn nhiều vấn đề; hỗ trợ data model giữa ticket và issue. | Quy định, trạng thái và đóng khiếu nại theo NYC không phải workflow/SLA BQL Vinhomes. |
| [NYC 311 Service Requests 2020–Present](https://data.cityofnewyork.us/Social-Services/311-Service-Requests-from-2020-to-Present/erm2-nwe9/about_data) | Có vấn đề, chi tiết, cơ quan xử lý, thời điểm, trạng thái và mô tả giải quyết; có thể làm đối chứng mô hình event nếu được phép dùng. | Có địa chỉ/vị trí địa lý nên phải tối thiểu hóa; trạng thái kết thúc không chứng minh kỹ thuật đã sửa; taxonomy rất rộng. Chưa ingest record. |

## Kết luận readiness

- **Có thể build ngay:** bảng `issue_taxonomy`, schema `source/fact/evidence`, retrieval có citation, intake hỏi thiếu dữ kiện, mock 14 tool, 32 ca synthetic, regression an toàn. Dữ liệu công khai hỗ trợ thiết kế nhưng phải có nhãn `external_reference`.
- **Chưa thể build để dùng thật:** routing theo tòa, SLA, safety policy, tự trợ giúp, chẩn đoán xác nhận, nghiệm thu, giá, quyền vào căn/khóa van/cô lập vùng. Những thứ này phải đến từ dữ liệu nội bộ được chủ sở hữu phê duyệt, không suy từ HUD/NYC hay repo cộng đồng.
- **Dữ liệu cần xin đầu tiên, theo thứ tự:** (1) danh mục tòa–asset–model và chủ quản; (2) SOP, ngưỡng/safety/routing có version và người duyệt; (3) ticket/work order ẩn danh gắn nguyên nhân–việc làm–kết quả–evidence; (4) lịch sử outage/sensor có đơn vị và nguồn đo; (5) cost thực và điều kiện áp dụng. Tối thiểu lấy mẫu đủ cả 16 mã và biến thể nhiều căn/khu chung/tái phát/thiếu thông tin.

## Quy tắc nếu sau này nhập dữ liệu mở

Xác minh giấy phép/điều khoản trước; chỉ tải trường cần cho POC, bỏ địa chỉ/căn và định danh cá nhân, lưu tên dataset–version–query–thời điểm–hash; không ghép vị trí để tái định danh. Trường NYC phải map sang taxonomy A2 bằng mapping có review, không thay mã A2 hoặc quy tắc severity. Luôn tách `complaint_created`, `problem_reported`, `inspection_verified`, `work_completed`, `resolution_confirmed` thay vì coi `closed` là đã khắc phục.
