# Đối chiếu nguồn Vinhomes Ocean Park 1 do người dùng cung cấp

Nguồn: [Data-Vinhome tại commit 8ebe9d4](https://github.com/leduc1707/Data-Vinhome/tree/8ebe9d42c396f82023507a8662d8323f09367654), rà soát ngày 2026-10-01. Đây là đánh giá **độ sẵn sàng dữ liệu kỹ thuật**, không phải xác nhận nội dung của BQL. Các file Masterise thuộc đơn vị vận hành khác và phải ở namespace khác.

## Những gì có thể trích làm mẫu

| Phạm vi | File nguồn | Nội dung kỹ thuật có thể dùng làm vocabulary/test | Độ tin cậy/việc cần làm |
| --- | --- | --- | --- |
| Sapphire | [Hướng dẫn tình huống](https://github.com/leduc1707/Data-Vinhome/blob/8ebe9d42c396f82023507a8662d8323f09367654/01-vinhomes/sapphire/huong-dan-xu-ly-tinh-huong.md) | Có ví dụ kẹt thang, rò giữa hai căn, mất điện một căn, mùi gas; mô tả câu hỏi intake và đầu mối. | `da-thu-thap-mot-phan`; P1 và thời gian có mặt là quy ước/ghi nhận team, cần BQL xác nhận. |
| Sapphire | [Quy trình vận hành](https://github.com/leduc1707/Data-Vinhome/blob/8ebe9d42c396f82023507a8662d8323f09367654/01-vinhomes/sapphire/quy-trinh-van-hanh.md) | Nêu các kênh cư dân báo việc và phân biệt lỗi khu chung với lỗi trong căn; có bảng P1–P4. | File tự nói SOP gốc không công khai; bảng P1–P4 không được tự chuyển thành policy V3. |
| Sapphire | [An toàn](https://github.com/leduc1707/Data-Vinhome/blob/8ebe9d42c396f82023507a8662d8323f09367654/01-vinhomes/sapphire/huong-dan-an-toan.md) | Có chủ đề cháy, điện/nước trong căn và pin xe. | Chưa có scan phương án PCCC của tòa; không dùng để chỉ đường thoát nạn cụ thể. |
| Pavilion | [Hướng dẫn tình huống](https://github.com/leduc1707/Data-Vinhome/blob/8ebe9d42c396f82023507a8662d8323f09367654/01-vinhomes/pavilion/huong-dan-xu-ly-tinh-huong.md) | Có mô tả ngắn về kẹt thang, rò nước, mất điện, gas và khóa cửa. | Chỉ một đoạn tóm tắt, thiếu SOP/checklist/evidence; thông số tòa cần kiểm tra bản niêm yết. |
| Pavilion | [Quy trình vận hành](https://github.com/leduc1707/Data-Vinhome/blob/8ebe9d42c396f82023507a8662d8323f09367654/01-vinhomes/pavilion/quy-trinh-van-hanh.md) | Gợi ý field khi tạo phiếu và phân tuyến đến bảo vệ/BQL. | Thời gian có mặt nêu trong file chưa kèm bản chứng cứ hiệu lực; không làm SLA. |
| Zenpark | [Danh mục dữ liệu](https://github.com/leduc1707/Data-Vinhome/blob/8ebe9d42c396f82023507a8662d8323f09367654/01-vinhomes/zenpark/DANH-MUC-DU-LIEU.md) | Có danh sách tòa và danh mục văn bản/tài liệu cần lấy; một số thông số từ trang giới thiệu chính thức. | File tự ghi thiếu nội quy, SOP, đầu mối, SLA và thông tin vận hành đã xác nhận. |
| Zenpark | [Hướng dẫn tình huống](https://github.com/leduc1707/Data-Vinhome/blob/8ebe9d42c396f82023507a8662d8323f09367654/01-vinhomes/zenpark/huong-dan-xu-ly-tinh-huong.md) | Bảng câu hỏi cần thu cho kẹt thang, rò/ngập, mất điện, khóa và khói/cháy. | `chua-thu-thap`; không ingest các ô yêu cầu thu thập như fact. |
| Bốn khu thấp tầng | [Ví dụ Hải Âu](https://github.com/leduc1707/Data-Vinhome/blob/8ebe9d42c396f82023507a8662d8323f09367654/04-thap-tang/hai-au/huong-dan-xu-ly-tinh-huong.md) | Có tình huống mất điện căn, ngập cống, cổng hỏng, cháy, khóa cửa. | Nội dung rất ngắn và lặp ở Ngọc Trai/San Hô/Sao Biển; chưa có quy trình theo từng khu. |
| Masteri Waterfront | [Báo cáo tự rà soát](https://github.com/leduc1707/Data-Vinhome/blob/8ebe9d42c396f82023507a8662d8323f09367654/02-masterise/RA-SOAT-DU-LIEU.md) | Nêu các lỗi chất lượng nguồn: SLA tự quy ước, hotline/sơ đồ PCCC thiếu chứng cứ, hướng dẫn cứu hộ rủi ro. | Dùng làm test data quality/injection, không coi là SOP Vinhomes hoặc Masterise đã duyệt. |

## Mapping sang A2

| Nhóm A2 | Dấu hiệu trong Data-Vinhome | Còn thiếu để build |
| --- | --- | --- |
| `TECH.ELEC.BREAKER_TRIP`, `TECH.ELEC.FIXTURE_FAILURE` | Mất điện căn, aptomat, đèn hành lang | Incident thật, asset CB/fixture, SOP điện, measurements và nghiệm thu |
| `TECH.PLUMB.CONCEALED_LEAK`, `TECH.PLUMB.SEWAGE_BACKFLOW` | Rò trần/giữa căn, ngập cống chung | Nguồn rò, phạm vi ảnh hưởng, evidence và checklist vệ sinh nước thải |
| `TECH.HVAC.CONDENSATION` | Hầu như không có case cụ thể | Asset điều hòa, manual, lịch sử bảo trì, số đo/ảnh trước sau |
| 11 mã A2 còn lại | Chỉ có các nhắc chung hoặc chưa có | Mỗi mã cần ticket và SOP/acceptance criteria riêng |

Không có dữ liệu được xác minh cho **14 tool** chạy end-to-end: asset/sensor/maintenance, measurement, executor result, approval request, giá actual, procedure publication đều cần nguồn nghiệp vụ riêng. File ảnh mặt bằng tòa trong Data-Vinhome không phải ảnh hiện trường của ticket và không được dùng làm evidence sửa chữa.

## Quy tắc tránh nhầm nguồn

Một fact phải mang `operator`, `project`, `subdivision`, `building`, `source_document_version`, `effective_at`, `review_status` và quyền đọc. Nếu source chỉ nói “khung nội bộ” hoặc “team ghi nhận”, giữ `unverified`; không tạo `sla_policy`, `triage_rule` hay SOP `published`. Nếu văn bản chính thức sau này khác repo công khai, lưu bản cập nhật có version và liên kết nguồn cũ để audit, không sửa âm thầm lịch sử.
