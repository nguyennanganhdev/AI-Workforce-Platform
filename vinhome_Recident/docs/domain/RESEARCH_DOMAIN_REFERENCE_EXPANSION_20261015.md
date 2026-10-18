# Nghiên cứu mở rộng dữ liệu tham khảo Domain — vòng 2

Ngày kiểm tra nguồn: **15/10/2026**. Phạm vi: OP1/Kỹ thuật trước; bổ sung tri thức có phạm vi rõ cho OP2/OP3. Đây là nghiên cứu nguồn công khai, không phải chứng nhận vận hành, kết quả import database hay nghiệm thu Agent.

Đã đối chiếu ba file hiện có trong `deploy/reference-data`: catalog địa bàn/tiện ích 80 bản ghi, ba bản giới thiệu tiện ích theo khu, và bốn tài liệu bổ sung về bàn giao OP1/ứng dụng chính thức. Không đề xuất nhân đôi các bản ghi địa bàn hoặc ba PDF bàn giao. Các mô tả hoạt động dưới đây bổ sung chi tiết cho Reception, không tạo tiện ích master trùng tên.

## 1. Sáu nội dung có thể bổ sung

Các mã dưới đây do dự án đề xuất. Tất cả giữ `authority=reference`, `operational_approval=pending`, `source_published_at=null`, `retrieved_at=2026-10-15`. Ngày hết hạn tuyển dụng là thông tin nguồn riêng, không phải ngày ban hành SOP hay ngày bắt đầu ca trực. Những giới hạn áp dụng phải nằm trong nội dung truy xuất, không chỉ nằm trong tài liệu này.

### 1. `resident/public-project-contact` — OP1, kênh công khai

Trang liên hệ dự án hiển thị số **1900 2323 89** trong nội dung chính. Có thể giới thiệu đây là kênh liên hệ công khai trên website dự án khi Reception thiếu thông tin. Không xác minh đây là số trực kỹ thuật, an ninh, khẩn cấp hoặc văn phòng BQL một tòa; nguồn không nêu nhánh hay giờ phục vụ trong phần liên hệ chính. Email bị che trong kết quả đọc nên không suy đoán. Không dùng địa chỉ hành chính trên trang làm địa chỉ hiện hành của master. [Trang liên hệ OP1](https://oceanpark.vinhomes.vn/lien-he/)

### 2. `technical/me-capability-reference` — chuyên môn thương hiệu, không phải roster OP1

Tin tuyển dụng M&E mô tả sửa điện/nước/điều hòa trong căn hộ và khu công cộng; bảo trì phần được phân công; tuân thủ an toàn/PCCC; báo cáo sự cố và tiến trình cho tổ trưởng. Reception có thể dùng để phân loại nhu cầu kỹ thuật. Tin áp dụng nhiều địa phương, hạn nộp **31/12/2026**; không chứng minh OP1 có người, lịch trực, capacity hay SLA tương ứng. Không nạp số/email tuyển dụng làm đầu mối cư dân. [Vinhomes Careers — Nhân viên Kỹ thuật M&E](https://careers.vinhomes.vn/job/nhan-vien-ky-thuat-me-6877)

Nếu schema buộc gắn một site để lưu, nội dung phải ghi rõ phạm vi thương hiệu tham khảo; việc gắn OP1 không làm tin tuyển dụng trở thành phân công tại OP1.

### 3. `resident/customer-care-workflow-reference` — OP2, mô tả công việc lịch sử

Tin CSKH có địa điểm làm việc OP2, mô tả tiếp nhận yêu cầu/khiếu nại; kiểm tra theo checklist; nghiệm thu/bàn giao căn theo tiêu chuẩn được duyệt; cập nhật hệ thống, báo cáo và chuyển vấn đề bất thường lên cấp trên. Hạn nộp **01/05/2025** nên phải ghi rõ nguồn lịch sử. Dùng tham khảo taxonomy và các trường báo cáo; không thay SOP hiện hành, sơ đồ phê duyệt, nhân sự hoặc quyền thực thi. [Vinhomes Careers — Chuyên viên CSKH](https://careers.vinhomes.vn/job/chuyen-vien-cham-soc-khach-hang-khong-truc-quay-8033)

Không chuyển các yêu cầu tuyển dụng, mức thu nhập hiển thị hay thông tin liên hệ ứng tuyển thành dữ liệu vận hành Domain.

### 4. `amenity/parks-activity-reference` — OP2, hoạt động cảnh quan

Trang The Empire mô tả Empire Park gồm ba công viên Khải Hoàn, Ánh sáng và Tình yêu; Silk Park là công viên ven kênh; Kingdom Avenue có Empire Square và tháp điêu khắc ánh sáng. Chi tiết này giúp Reception phân biệt nhu cầu đi dạo/cảnh quan với vui chơi nước. Trang có nội dung quy hoạch cũ, không xác minh trạng thái mở cửa, quyền dùng, phí, lịch sự kiện hay booking hiện tại. [Trang dự án OP2 — mục đại tiện ích](https://theempire.vinhomes.vn/)

Tên các tiện ích đã có trong catalog; bổ sung tri thức mô tả, không tạo thêm master hoặc đổi Royal Wave Park thành VinWonders Wave Park chỉ bằng suy luận tên.

### 5. `amenity/aquatic-activity-reference` — OP3, phân biệt loại hình

Trang OP3 giới thiệu Tropical Lagoon là hồ nước mặn, Four Seasons là hồ bơi trong nhà, Olympics Swimming Pool có hai hồ 50/100 m và 14 làn; Aqua Bay là khu trượt nước. Reception có thể phân biệt nhu cầu bơi trong nhà, luyện bơi và trượt nước. Đây là mô tả quảng bá, không bảo đảm mở cửa hôm nay, điều kiện an toàn, quyền cư dân, phí hay chỗ còn trống. [Trang dự án OP3 — mục tiện ích](https://oceanpark3.vinhomes.vn/)

### 6. `amenity/family-activity-reference` — OP3, trẻ em/gia đình/sự kiện

Nguồn OP3 mô tả Aquarium là cụm ba sân chơi trẻ em theo chủ đề; BBQ Garden dành cho hoạt động tiệc nướng gia đình; Marina Square là quảng trường tổ chức sự kiện. Không suy ra độ tuổi, chiều cao tối thiểu, quyền sử dụng bếp, lịch sự kiện hay lịch đặt. [Trang dự án OP3 — mục tiện ích](https://oceanpark3.vinhomes.vn/)

Tên chủ đề giữa trong Aquarium được nguồn viết là `Sửa Biển`; tránh tự sửa thành tên khác hoặc sử dụng tên đó làm mã chuẩn khi chưa có xác nhận. Hai bản ghi OP3 chỉ bổ sung phân loại hoạt động cho các tên đã có, không lặp master tiện ích.

## 2. Phát hiện quan trọng: FAQ nhúng chưa được kích hoạt

Đã kiểm tra trực tiếp HTML tải từ [trang Market OP2](https://market.vinhomes.vn/du-an/vinhomes-ocean-park-2) và [trang Market OP3](https://market.vinhomes.vn/du-an/vinhomes-ocean-park-3). Web reader không tải được trang quá lớn; kiểm tra tiếp bằng HTTP GET và giải nội dung script của Next.js. Phần trang nhìn thấy chủ yếu có câu hỏi; các đối tượng câu trả lời liên quan trong dữ liệu nhúng mang **`is_active:false`**. Không thấy meta ngày xuất bản/cập nhật cho các câu trả lời.

Vì vậy **không dùng những câu trả lời nhúng đó làm knowledge truy xuất cho cư dân hoặc cấu hình master** trong lượt này, dù hostname thuộc Vinhomes. Chúng chứa dữ kiện cụ thể về văn phòng, giờ, an ninh, phí dịch vụ và gửi xe nhưng trạng thái xuất bản/hiệu lực chưa được chứng minh. Không đưa các giá trị đó vào pilot, bảng phí, lịch làm việc hoặc tuyến escalation. Cần tài liệu đang hiệu lực hoặc trang công khai đã kích hoạt và người vận hành xác nhận trước khi sử dụng. Đây là quyết định chất lượng dữ liệu của dự án, không diễn giải `is_active:false` thành bằng chứng dịch vụ thực tế đã ngừng hoạt động.

Trang Market OP1 không cung cấp được bộ câu trả lời tương đương trong phần đã kiểm tra. Không suy số điện thoại/giờ/chi phí của OP2 hoặc OP3 sang OP1.

## 3. Các nguồn chưa đủ điều kiện nhập

| Nguồn | Kết luận |
|---|---|
| Bài báo/đại lý về HomeCare OP2/OP3 năm 2026 | Tìm thấy thông tin về mở rộng vệ sinh, chăm sóc sân vườn, kỹ thuật và ưu đãi nhưng chưa truy được tài liệu chương trình do bên cung cấp trực tiếp công bố trong vòng này. Không lấy báo chí/đại lý thay quyết định dịch vụ hay điều kiện hưởng của từng hộ. |
| Website có tên gần giống Vinhomes nhưng không dưới tên miền xác minh | Không dùng làm primary source chỉ dựa vào tên/nhận diện. |
| Chính sách bán hàng OP2 2024 | Có phiên bản và điều kiện giao dịch lịch sử, không thay biểu phí/SOP hoặc quyền dịch vụ hiện hành. Không import giá trị ưu đãi. |
| Các trang `vinhomes.vn/vi/...` trả 403 | Search snippet không đủ làm snapshot đầy đủ. Không suy nội dung không đọc được; dùng trang dự án chính thức đọc được cho những dữ kiện giới hạn nêu trên. |
| Tiêu chuẩn bàn giao OP2/OP3 từ đại lý | Chưa xác minh được tài liệu kỹ thuật chính thức đúng sản phẩm và phiên bản. Không sao chép ba PDF Sapphire OP1 sang OP2/OP3. |

## 4. Phần thiếu không giải quyết được bằng nguồn công khai

Không tìm được bộ hồ sơ vận hành có đủ phạm vi, phiên bản và xác nhận để điền 108 trường/hạng mục còn thiếu của pilot. Sáu nội dung trên cải thiện khả năng giới thiệu và phân loại nhu cầu, **không làm giảm số hồ sơ owner bắt buộc** nếu chưa bổ sung bản xác nhận thích hợp.

Những phần cần dữ liệu của đơn vị vận hành gồm:

- Đơn vị pháp lý và người chịu trách nhiệm đúng tòa; quan hệ quản lý và thời gian hiệu lực.
- Master căn/lô và tình trạng bàn giao; cư dân có quan hệ cư trú đã xác minh. Không sinh hồ sơ người/căn từ bài marketing.
- Nhân sự thực tế, chuyên môn, phạm vi, ca trực có timezone, capacity và dự phòng. Tin tuyển dụng không thay roster.
- Quy định dịch vụ đang hiệu lực: phần chung/riêng, điều kiện tiếp cận căn, phí/VAT, giờ, bảo hành, đặt/hủy và quyền phê duyệt.
- SOP sự cố/an toàn, escalation, SLA và tiêu chí hoàn thành/tái xử lý được duyệt.
- Contract/endpoint/grant Platform, quyền công cụ và thông tin tối thiểu theo ticket. Không xuất toàn bộ dữ liệu cư dân để làm knowledge.

Đề xuất nhập sáu mục dưới lớp reference với URL, snapshot hash và caveat; kiểm tra import lặp, tách site, không kích hoạt route/giá/nhân sự và không ghi đè bản đã duyệt. Bản mô tả CSKH lịch sử có thể giữ chỉ để thiết kế nếu muốn hạn chế knowledge cư dân ở hiện tại. Lượt nghiên cứu này không gọi Agent/provider, không đăng nhập hệ thống Vinhomes, không import database và không sửa cấu hình triển khai.

## 5. Chốt nội dung nhập sau rà soát

Bộ [resident-support-public-20261015.json](../../deploy/reference-data/resident-support-public-20261015.json) chọn **6 bản ghi, mỗi khu 2 bản ghi**. Mục CSKH lịch sử ở trên chỉ giữ trong nghiên cứu, không nhập kho trả lời cư dân. Thay vào đó, thêm kênh liên hệ công khai OP2: trang [The Empire](https://theempire.vinhomes.vn/) hiển thị `1900 23 23 89`, không xác nhận nhánh, giờ hoặc số trực kỹ thuật/an ninh. Hai bản liên hệ OP1/OP2 cùng dùng số công khai của thương hiệu nhưng có nguồn và giới hạn theo khu; không tính là hai tổng đài vận hành độc lập.

Các tên tiện ích đã có không được tạo master mới. Những bản ghi mới bổ sung mô tả loại hình hoạt động. Toàn bộ mức phí, giờ và đầu mối cụ thể từ FAQ nhúng chưa kích hoạt bị loại; số liệu hoặc trạng thái import phải đọc báo cáo triển khai riêng, không suy từ tài liệu nghiên cứu này.
