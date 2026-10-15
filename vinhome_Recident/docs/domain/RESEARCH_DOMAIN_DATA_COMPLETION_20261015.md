# Nghiên cứu bổ sung dữ liệu Domain — OP1/Kỹ thuật

Ngày tra cứu: **15/10/2026**, múi giờ Asia/Saigon. Phạm vi: nguồn công khai chính thức của Vinhomes, ưu tiên OP1/Kỹ thuật. Tài liệu này là kết quả nghiên cứu; không chứng nhận dữ liệu đã nhập database, đã được BQL phê duyệt hoặc đã nghiệm thu dịch vụ thực tế.

## 1. Kết luận và phần bổ sung có căn cứ

Catalog đang có trong `deploy/reference-data/owner-public-catalog-20261014.json` gồm **80 bản ghi**: OP1 **47**, OP2 **15**, OP3 **18**; theo loại gồm **25 phân khu, 30 tòa, 25 tiện ích**. Đây là số liệu kiểm tra file nguồn trong repository, không phải số liệu database đang chạy. Catalog chưa có tài liệu bàn giao kỹ thuật, hướng dẫn kênh hỗ trợ hay cơ cấu chuyên môn kỹ thuật từ nguồn công khai.

Có thể bổ sung **4 nội dung tham khảo**: ba PDF bàn giao OP1 và mô tả kênh ứng dụng chính thức. Hai nguồn bổ sung về chuyên môn M&E và tổng đài toàn thương hiệu chỉ phục vụ nghiên cứu, không nhập thành roster/hotline OP1. Ba tài liệu bàn giao OP1 hữu ích để Reception phân biệt nhóm hạng mục, nhưng không đủ để xác định thiết bị thực tế, đơn vị chịu trách nhiệm hoặc quyền bảo hành của một căn cụ thể. Thư viện công khai đặt tài liệu trong nhóm bán hàng/bàn giao, đồng thời nêu rằng quản lý vận hành tuân theo quy định BQL. Vì vậy phải giữ `authority=reference`, không đổi thành SOP hoặc catalog dịch vụ vận hành đã duyệt. [Thư viện tài liệu OP1](https://oceanpark.vinhomes.vn/thu-vien-tai-lieu/)

Không có nguồn công khai nào được xác minh trong lượt này cung cấp bộ dữ liệu cư dân, quan hệ cư trú, người thực hiện công việc, ca trực hoặc phạm vi phân công thực tế. **Không thể hoàn tất chuỗi địa bàn → cư dân → nhân sự → dịch vụ → SOP bằng cách tự sinh những dữ kiện đó.**

## 2. Nguồn và dữ kiện có thể nhập làm reference

Các đoạn dưới đây là tóm tắt, không sao chép nguyên tài liệu. Mã bản ghi là mã đề xuất nội bộ; không phải mã tài liệu chính thức do Vinhomes cấp. Mỗi bản ghi cần `retrieved_at=2026-10-15`, lưu URL nguồn và giới hạn áp dụng ngay trong nội dung truy xuất cho Reception.

| Mã đề xuất / phạm vi | Nội dung tự tóm tắt để nhập | Ngày/phiên bản và giới hạn | Nguồn chính thức |
|---|---|---|---|
| `technical-reference/sapphire-basic-handover` — OP1/Sapphire | Tài liệu bàn giao hoàn thiện cơ bản phân nhóm sàn, tường, trần, cửa, bếp, phòng tắm, nước nóng, điện, điều hòa và intercom. Bản này liệt kê bếp từ, chậu rửa, hút mùi, bình nước nóng; intercom kết nối tầng 1 và tầng hầm. | PDF 2 trang, chưa thấy ngày ban hành/hiệu lực hoặc số phiên bản trong nội dung; `source_published_at=null`. Đường dẫn chứa `2019/08` chỉ là thư mục lưu file. Có điều khoản vật liệu/thiết bị tương đương và điều chỉnh thiết kế. Cần phụ lục bàn giao của từng căn để xác định thực tế. | [Tiêu chuẩn cơ bản căn hộ Sapphire](https://oceanpark.vinhomes.vn/wp-content/uploads/2019/08/Tieu-chuan-co-ban-Can-ho-Sapphire.pdf) |
| `technical-reference/sapphire-minimum-handover` — OP1/Sapphire | Tài liệu bàn giao tối thiểu liệt kê hoàn thiện sàn/tường/trần/cửa, phòng tắm, điện, intercom và điều hòa. Khác danh mục cơ bản: bản tối thiểu không liệt kê nhóm bếp và bình nước nóng như bản cơ bản. | PDF 2 trang, chưa thấy ngày/phiên bản; `source_published_at=null`. Sự khác nhau giữa hai bảng là dữ kiện của tài liệu, không kết luận rằng một căn cụ thể không có thiết bị. Cần đối chiếu loại hợp đồng/phụ lục thực tế. | [Tiêu chuẩn tối thiểu căn hộ Sapphire](https://oceanpark.vinhomes.vn/wp-content/uploads/2019/08/Tieu-chuan-toi-thieu-Can-ho-Sapphire.pdf) |
| `technical-reference/shophouse-rough-handover` — OP1/căn thương mại dịch vụ | Tài liệu bàn giao thô mô tả đầu chờ điện và cấp/thoát nước, PCCC theo thiết kế; bên mua hoàn thiện nhiều phần bên trong. Điều hòa và hệ thống lọc không khí của ngành nghề có mùi cần tuân theo thiết kế/công suất được chủ đầu tư phê duyệt. | PDF 1 trang, tiêu đề ghi đính kèm HĐMB, chưa thấy ngày/phiên bản; `source_published_at=null`. Không mở quyền thi công, không thay nội quy thi công hiện hành. | [Tiêu chuẩn bàn giao thô shophouse](https://oceanpark.vinhomes.vn/wp-content/uploads/2019/08/Tieu-chuan-ban-giao-tho-shophouse.pdf) |
| `resident-reference/official-app-support-channels` — thông tin thương hiệu, không riêng OP1 | Trang ứng dụng Vinhomes Resident do Vingroup công bố mô tả đặt tiện ích, thanh toán hóa đơn, gửi yêu cầu dịch vụ tòa nhà/góp ý BQL và nhận thông tin PCCC/intercom. Ghi chú cập nhật có tính năng xem biểu phí. Có thể hướng dẫn cư dân tham khảo kênh ứng dụng chính thức khi cần thông tin chưa có trong hệ thống. | Metadata hiển thị cập nhật **02/09/2026**, không phải ngày hiệu lực bảng phí hay ngày triển khai từng khu. Không có API public, mức phí, SLA, sơ đồ màn hình cụ thể hoặc xác nhận quyền tích hợp trong mô tả này. | [Vinhomes Resident trên Google Play](https://play.google.com/store/apps/details?hl=vi&id=com.vinhomes.resident) |
| `technical-reference/me-role-capabilities` — mô tả chuyên môn Vinhomes nói chung | Tin tuyển dụng M&E nêu nhóm sửa điện, nước, điều hòa trong căn hộ/khu công cộng, bảo trì khu vực được giao, tuân thủ an toàn/PCCC, tiếp nhận phản ánh và báo cáo sự cố/tiến trình cho tổ trưởng. Đây là cơ sở tham khảo để thiết kế taxonomy chuyên môn và dữ liệu báo cáo công việc. | Trang hiển thị hạn nộp **31/12/2026**, không phải ngày bắt đầu làm việc. Tuyển ở nhiều tỉnh; không chứng minh đã có đội M&E OP1, năng lực hay ca trực của bất kỳ người nào. Không nhập email/số điện thoại tuyển dụng làm đầu mối phục vụ cư dân. | [Nhân viên Kỹ thuật M&E — Vinhomes Careers](https://careers.vinhomes.vn/job/nhan-vien-ky-thuat-me-6877) |
| `resident-reference/corporate-customer-care` — tổng đài chung thương hiệu | Trang chủ Vinhomes công bố tổng đài CSKH **1900 2323 89**. Có thể dùng làm thông tin liên hệ công khai chung, ghi rõ phạm vi thương hiệu. | Không thấy ngày hiệu lực hoặc giờ phục vụ được xác minh cho tổng đài CSKH. Không gán làm hotline khẩn cấp, số trực kỹ thuật hay văn phòng BQL OP1/OP2/OP3; không dùng số của phòng bán hàng/tuyển dụng thay thế. | [Trang chủ Vinhomes — mục Tổng đài CSKH](https://vinhomes.vn/vi) |

Hai hàng `me-role-capabilities` và `corporate-customer-care` là đề xuất nghiên cứu, **không nhập** thành nhân sự, ca hoặc đầu mối vận hành OP1. Phạm vi thương hiệu của bản ghi ứng dụng phải được thể hiện trong nội dung ngay cả khi hệ thống hiện chỉ lưu tài liệu dưới từng site. Không diễn giải một bản ghi gắn site OP1 thành bằng chứng đơn vị quản lý hoặc quyền dịch vụ của OP1. OP2/OP3 vẫn dùng catalog địa bàn/tiện ích đã có; không sao chép tiêu chuẩn Sapphire OP1 sang hai khu này.

### Địa bàn candidate cho pilot

Bài hỏi đáp chính thức ngày **05/07/2024 09:30** xác định OP1 có khu Sapphire 1 và liệt kê **S1.01** trong nhóm tòa 27 tầng. Có thể tái sử dụng record tham khảo đã có để prefill **OP1 → Sapphire 1 → S1.01**, không tạo bản ghi địa bàn trùng. Không tự sinh mã căn theo số tầng; chưa xác nhận đơn vị quản lý, trạng thái bàn giao, phạm vi dịch vụ hay cư trú. Đây là candidate cần duyệt, không kích hoạt master vận hành. [Tòa nhà tại khu Sapphire 1 — Vinhomes Market](https://market.vinhomes.vn/blog/toa-nha-tai-phan-khu-sapphire-1-vinhomes-ocean-park-gia-lam-co-bao-nhieu-tang)

## 3. Không nạp làm quy định vận hành

| Nguồn đã rà soát | Lý do không dùng làm dữ liệu thực thi |
|---|---|
| [Hướng dẫn trợ lý ảo Vinhomes](https://market.vinhomes.vn/blog/tro-ly-ao-vinhomes) | Trang mang ngày **26/12/2021** nhưng nội dung nói ra mắt **15/07/2022**. Có mô tả tra cứu/đặt-hủy tiện ích/yêu cầu dịch vụ, nhưng mốc thời gian không nhất quán và hướng dẫn giao diện cũ; không dùng để chốt UI hiện hành hoặc khả năng sản phẩm của dự án này. |
| [Mẫu HĐMB tìm thấy trên kho Vinhomes](https://market-files.vinhomes.vn/public-mngt/d/d7adf03e-0b77-43bd-8a8c-d8d5d51a13d3) | Nội dung xác định dự án Vinhomes New Center/Hàm Nghi tại Hà Tĩnh. Cùng thương hiệu hoặc cùng máy chủ lưu file không làm điều khoản đó áp dụng OP1. Không nạp bảo hành, quyền vào căn, mức phí hay thời hạn từ hợp đồng này. |
| [Bài giới thiệu phí quản lý chung cư 2026](https://market.vinhomes.vn/blog/phi-quan-ly-chung-cu-bao-gom-nhung-gi-quy-dinh-moi-nhat-2026) | Bảng so sánh thị trường đưa khoảng phí, không phải quyết định thu hiện hành của tòa/khu và không có căn cứ áp dụng cho từng cư dân. Không nạp thành giá dịch vụ đang hiệu lực. |
| [Thư viện tài liệu OP1](https://oceanpark.vinhomes.vn/thu-vien-tai-lieu/) | Nhiều chính sách bán hàng mang mốc 2019–2021. Không dùng ưu đãi/quyền lợi hoặc phí cũ như quy định đang có hiệu lực. |

Không tìm được SOP công khai hiện hành cho OP1 xác định đầy đủ người chịu trách nhiệm, phiên bản, ngưỡng khẩn cấp, thao tác được phép, cô lập nguồn nguy hiểm, SLA, phí/duyệt chi phí và tiêu chí nghiệm thu. Kết luận là **chưa có nguồn xác minh trong lượt nghiên cứu**, không phải khẳng định các SOP không tồn tại trong hệ thống nội bộ Vinhomes.

## 4. Dữ liệu còn thiếu để chạy pilot có người dùng thật

Đây là bộ trường đề xuất cho triển khai phần mềm, không phải nội dung tuyên bố của nguồn Vinhomes.

| Dataset | Dữ kiện cần được người sở hữu cung cấp | Hành vi hệ thống khi thiếu |
|---|---|---|
| Địa bàn pilot | Một tòa/dãy OP1 được chọn, mã chính thức; căn/lô đủ phạm vi; đơn vị quản lý thực tế; trạng thái bàn giao; quan hệ cha-con; ngày hiệu lực; nguồn xác nhận | Không dựng mã căn từ số tầng/mặt bằng marketing; không dùng reference làm xác minh cư trú. |
| Cư trú | Resident ID; tài khoản liên hệ tối thiểu; căn/lô; loại quan hệ; hiệu lực; trạng thái và người xác minh | Không tạo danh tính hay cư trú giả lên production; giữ quy trình đăng ký/xác minh. |
| Nhân sự | Employee/team ID; chuyên môn; phân công tòa/căn/khu; ca bắt đầu/kết thúc có timezone; capacity; người dự phòng; trạng thái khả dụng; owner | Không suy ra roster từ tin tuyển dụng; không tự giao việc khi chưa có người/ca hợp lệ. |
| Dịch vụ kỹ thuật | Phân biệt phần chung/riêng, bảo hành/sửa tính phí; nhóm điện/nước/điều hòa; đối tượng được phục vụ; route; đơn vị thực hiện; ngưỡng phê duyệt | Có thể tiếp nhận thông tin; chỉ kích hoạt tuyến thực thi khi cấu hình và nguồn lực được xác nhận. |
| SOP/an toàn | Quy trình theo loại sự cố; quyền truy cập căn; thao tác nhân viên đủ điều kiện; escalation; trường cần ghi; tiêu chí nghiệm thu/tái xử lý; phiên bản/hiệu lực/owner | Tài liệu đề xuất giữ pending review; không giả danh SOP Vinhomes đã phê duyệt. |
| Tài sản/bảo hành | Danh mục thiết bị của căn/tòa; model/serial khi cần; bàn giao; nhà bảo hành; thời hạn; loại trừ; bằng chứng hợp đồng | PDF bàn giao chỉ gợi ý nhóm hạng mục; không tự hứa sửa miễn phí hoặc còn bảo hành. |
| Giá, giờ và đầu mối | Quyết định thu/biểu phí hiện hành theo phạm vi, VAT/đơn vị tính; giờ/ngày nghỉ; người trực/tổng đài vận hành; thời gian áp dụng | Không báo giá/SLA/giờ mở cửa cụ thể khi thiếu quyết định và phạm vi. |

## 5. Cách nhập và nghiệm thu đề xuất

1. Nhập bốn nội dung có phạm vi phù hợp vào lớp tài liệu tham khảo, có URL, ngày truy xuất, phạm vi và caveat; hai nguồn thương hiệu còn lại giữ trong nghiên cứu. Không thêm account, residency, ca hay giá mẫu.
2. Giữ dữ liệu người dùng thật riêng với reference. Các mẫu CSV pending không được nâng thành approved chỉ vì đã điền đủ cột.
3. Chỉ đưa thông tin ticket cần thiết và nguồn nghiệp vụ được phép sang Platform; không xuất toàn bộ danh sách cư dân/nhân sự để làm tri thức cho Agent.
4. Nghiệm thu tĩnh: URL/source tồn tại trong bản ghi, nội dung đúng phạm vi, không có claim phí/SLA/bảo hành không được nguồn hỗ trợ, không trộn OP1/OP2/OP3, import lặp không nhân đôi.
5. Nghiệm thu vận hành thật vẫn cần dữ kiện owner trong mục 4. Bộ reference nghiên cứu này không thay happy case cư dân thật → staff thật → Platform → nghiệm thu.

Trong lượt nghiên cứu này không gọi Agent/provider, không đăng nhập hệ thống chính thức Vinhomes, không tạo/sửa database, không sửa cấu hình triển khai. Các đường dẫn công khai được đọc chỉ để kiểm chứng nguồn; thông tin marketing có thể thay đổi và phải được đối chiếu với hồ sơ áp dụng thực tế.
