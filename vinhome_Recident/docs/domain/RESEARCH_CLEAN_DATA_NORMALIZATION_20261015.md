# Nghiên cứu chuẩn hóa dữ liệu và bổ sung CSKH OP1/OP2/OP3

Ngày đối chiếu: **15/10/2026**, giờ Việt Nam. Phạm vi: nguồn của đơn vị cung cấp dịch vụ, Vinhomes và tiêu chuẩn IANA/IETF. Đây là nghiên cứu nguồn và đề xuất nhập liệu; tài liệu này không thực hiện import, xác nhận cư trú hoặc thay cấu hình runtime.

## 1. Phân biệt chuẩn dữ liệu với xác nhận thực tế

Có thể chuẩn hóa tài khoản, tên hiển thị, địa bàn liên kết, lịch ca, catalog và SOP để trải nghiệm nhất quán. Việc đổi tên không tạo bằng chứng nhân sự/cư trú thật, không biến mức phí giả định thành biểu phí Vinhomes. Giữ nguồn gốc trong metadata và hồ sơ quản trị; giao diện nghiệp vụ có thể dùng tên rõ ràng, ngắn gọn và tránh lặp các nhãn kỹ thuật trong mọi dòng.

Nền tham khảo đã được nghiên cứu trong [báo cáo OP1](RESEARCH_DOMAIN_DATA_COMPLETION_20261015.md), [mở rộng địa bàn](RESEARCH_DOMAIN_REFERENCE_EXPANSION_20261015.md) và [thủ tục kỹ thuật](RESEARCH_TECHNICAL_PROCEDURES_20261015.md). Không nhập lại các PDF bàn giao OP1, mô tả ứng dụng và danh mục tiện ích đã có. Đặc biệt, tài liệu bàn giao OP1 không được sao chép thành SOP sửa chữa OP2/OP3.

## 2. Nội dung mới có thể bổ sung cho Reception

Các mã dưới đây là **mã nội bộ đề xuất**, không phải mã văn bản của nhà cung cấp. Mỗi bản nhập cần URL, ngày truy xuất, phạm vi và thời hạn/giới hạn trong chính nội dung truy xuất.

| Mã / phạm vi | Nội dung tóm tắt có căn cứ | Giới hạn khi trả lời và thực thi |
|---|---|---|
| `resident-care/vinbus-ocp1-hospital-20260407` — OP1/OP2/OP3 | VinBus thông báo điều chỉnh OCT1/OCP1 từ **07/04/2026**, bổ sung kết nối Bệnh viện Vinmec Ocean Park 2. Các điểm bổ sung gồm Center Point Đại Lộ Ngọc Trai, bệnh viện và khu Ngọc Trai/Công viên Ngọc Trai 3. | Đây là thông báo của đơn vị vận tải, không phải cam kết thời gian xe đến hoặc quyền đặt xe qua dự án. Dẫn cư dân tra cứu chuyến hiện tại; không biến lộ trình thành tuyến xử lý ticket. [Thông báo VinBus](https://vinbus.vn/thong-bao-dieu-chinh-lo-trinh-mo-rong-ket-noi-toi-benh-vien-vinmec-ocean-park-2) |
| `resident-care/vinbus-live-route-lookup` — OP1/OP2/OP3 | Kênh tra cứu của nhà vận hành liệt kê **OCP1** cho nội liên khu OP1/2/3 và **OCP2** cho OP2/3. Có thể trả lời câu hỏi đi lại bằng liên kết bản đồ. | Kết quả trang động phụ thuộc thời điểm; không lưu ETA xe, biển số, giá/giờ như dữ kiện vĩnh viễn. Bộ đọc trang lần này không trích xuất được đầy đủ giao diện động; tên tuyến có trong kết quả chỉ mục. [Tra cứu VinBus](https://maps.vinbus.vn/) |
| `resident-care/vinmec-op23-benefit-eligibility` — OP2/OP3 | Bài Vinmec cập nhật **07/08/2026** công bố chương trình cho cư dân OP2/3, nhóm ưu đãi đến **30/05/2027**; quyền lợi Ngọc Trai OP2 có mốc riêng đến **30/06/2031**. Điều kiện yêu cầu nằm trong danh sách ứng dụng cư dân; tình trạng về ở, công nợ và loại căn ảnh hưởng quyền lợi. | Chỉ hướng dẫn nơi kiểm tra điều kiện. Không tự gắn `eligible=true` từ tài khoản Domain, không suy rộng điều kiện sang mọi dịch vụ. Không tạo quy tắc tính tiền y tế hay hứa giảm giá trong ticket. Không nhập tên/số cá nhân của đầu mối thành staff dự án. [Chương trình Vinmec OP2/OP3](https://www.vinmec.com/vie/bai-viet/uu-dai-den-50-danh-rieng-cho-cu-dan-vinhomes-ocean-park-2-va-3) |
| `resident-care/vinwonders-venue-distinction` — OP2/OP3 | Trang bảng giá/quy định của đơn vị khai thác phân biệt **Wave Park tại OP2** và **Water Park tại OP3**, cùng vé từng công viên và combo. | Có thể giúp Reception phân biệt điểm đến và dẫn tới nguồn mua vé chính thức. Chưa có API inventory/booking hay hợp đồng tích hợp, nên không hứa giữ chỗ/xác nhận vé và không nhập bảng giá thành dịch vụ nội khu được duyệt. [VinWonders: giá và quy định](https://vinwonders.com/en/vinwonders-wave-park-water-park-price-regulations/?lang=en) |

Trang giới thiệu OP3 và brochure vẫn là nguồn mô tả dự án/tiện ích, không cung cấp hồ sơ hoạt động từng ngày. Vì nội dung cơ bản đã có trong nghiên cứu trước, không đề xuất nhập trùng hoặc dùng để mở booking. [Brochure OP3](https://oceanpark3.vinhomes.vn/brochure/)

### Câu trả lời ngắn có thể biên tập thành FAQ

- **Đi từ OP2/OP3 đến bệnh viện:** Có nguồn tuyến VinBus nối đến Vinmec Ocean Park 2; mở bản đồ nhà vận hành để chọn điểm dừng và chuyến đang chạy. Nguồn và ngày của thông báo phải đi kèm kết quả. [VinBus](https://vinbus.vn/thong-bao-dieu-chinh-lo-trinh-mo-rong-ket-noi-toi-benh-vien-vinmec-ocean-park-2)
- **Tài khoản Domain đã đủ nhận ưu đãi y tế chưa:** Chưa thể kết luận từ đăng nhập Domain; cần đối chiếu điều kiện của nhà cung cấp và danh sách ứng dụng cư dân. Đây là điều kiện chương trình y tế, không dùng làm xác minh cư trú tổng quát. [Vinmec](https://www.vinmec.com/vie/bai-viet/uu-dai-den-50-danh-rieng-cho-cu-dan-vinhomes-ocean-park-2-va-3)
- **Wave Park và Water Park ở đâu:** Hướng dẫn phân biệt OP2/OP3 theo trang nhà cung cấp; liên kết nguồn để xem điều kiện và mua vé, không xác nhận giao dịch thay nhà cung cấp. [VinWonders](https://vinwonders.com/en/vinwonders-wave-park-water-park-price-regulations/?lang=en)

## 3. Tài khoản đăng nhập sạch và địa chỉ email

IANA liệt kê `test.` là tên miền sử dụng đặc biệt; phạm vi áp dụng bao gồm các tên miền con. RFC 6761 mục 6.2 quy định tên `.test` dùng trong mạng riêng và không được cấp đăng ký như tên Internet thông thường. [IANA](https://www.iana.org/assignments/special-use-domain-names), [RFC 6761 §6.2](https://www.rfc-editor.org/rfc/rfc6761#section-6.2)

**Đề xuất kỹ thuật của dự án:** bỏ chuỗi `demo`/`sandbox` khỏi login nếu cần trải nghiệm chuyên nghiệp, dùng quy tắc ổn định như `resident.001@op1.vinhomes.test`, `technical.001@op2.vinhomes.test`, `security.001@op3.vinhomes.test`. Không dùng `@vinhomes.vn` hoặc địa chỉ người thật chưa được phép. `.test` là định danh login, không phải hộp thư nhận email Internet; quên mật khẩu phải dùng mail sink hoặc địa chỉ liên hệ thật đã xác minh riêng.

Đổi email bằng ID người dùng và giao dịch database; giữ nguyên liên kết căn, quyền, lịch sử, password hash và route. Không đổi login của Platform từ script Domain. Manifest account riêng cần phân biệt môi trường, site, phân khu/tòa/dãy, role, nhóm chuyên môn, ca và URL đăng nhập; không ghi mật khẩu vào tài liệu research hoặc Git.

## 4. Nguồn gốc và dữ liệu cá nhân

Chính sách Vinhomes công bố nguyên tắc chia sẻ dữ liệu trong phạm vi cần thiết theo mục đích và yêu cầu bên nhận bảo vệ dữ liệu (mục 5.1). Mục 10 nêu các quyền biết, đồng ý/rút lại, truy cập/chỉnh sửa và yêu cầu xóa/hạn chế; việc xử lý yêu cầu cần xác minh và có ngoại lệ. Đây là chính sách của Vinhomes, không phải giấy phép cho dự án này nhập hồ sơ bất kỳ. [Chính sách Vinhomes, mục 5 và 10](https://gcp-cdn.vinhomes.vn/cms-data/chinh-sach-bao-ve-du-lieu-ca-nhan.pdf)

**Suy luận thiết kế:** Domain giữ hồ sơ gốc; Platform nhận ngữ cảnh tối thiểu theo ticket/grant. Không đưa giấy tờ cá nhân, danh sách cư dân hoặc roster đầy đủ vào knowledge của Agent. Lưu `data_origin`, `source_url`, `retrieved_at`, `authority`, `review_status`, `effective_from/to` và phiên bản để phân biệt dữ liệu công khai, dữ liệu do dự án tạo và hồ sơ được operator xác nhận. Việc ẩn nhãn kỹ thuật trên UI không được xóa provenance hoặc tự đặt `verified_by`/`approved_at` giả.

## 5. Những khoảng trống chưa có nguồn xác nhận

| Dataset | Có thể hoàn thiện trong bộ dữ liệu dự án | Bằng chứng cần để nhận là vận hành Vinhomes thật |
|---|---|---|
| Địa bàn, căn/lô, đơn vị | Quan hệ cha-con, mã định danh ổn định, timezone, địa chỉ trình bày | Master và phạm vi quản lý theo thời gian từ đơn vị phụ trách |
| Cư trú | Quan hệ chủ sở hữu/người thuê, thời hạn, trạng thái kiểm thử quyền | Hồ sơ được phép xử lý, tham chiếu người xác minh và căn thật |
| Nhân sự, ca, nghỉ, dự phòng | Lịch phủ ca, chuyên môn, capacity, người thay thế và kiểm tra xung đột | Danh sách nhân sự/đơn vị, chứng nhận cần thiết, phân công và ca được duyệt |
| Dịch vụ | Cấu trúc phí/đơn vị tiền/VAT, giờ, đặt-hủy, bảo hành và điều kiện | Quyết định/bảng giá có hiệu lực, hợp đồng nhà cung cấp và phạm vi |
| SOP/SLA | Workflow theo đúng sản phẩm, bước chi phí/đồng ý/ảnh/nghiệm thu, version owner | Quy trình và mức SLA được người có thẩm quyền ký duyệt |
| Platform VPS | Kiểm tra cấu hình URL, DNS/TLS, grant, mapping, retry/idempotency | Endpoint thực tế truy cập được và kiểm thử hai chiều; nghiên cứu web không tạo key/route |
| Embedding | Thống kê thiếu theo model/dimension/hash và đánh giá retrieval | Cấu hình provider/cost được phép, re-embed đúng không gian và kiểm thử; không nối/trộn vector |

Không tìm được trong các nguồn được xác minh lần này bộ master căn, hồ sơ cư trú, roster, ca trực, mức phí kỹ thuật, SLA hoặc SOP vận hành hiện hành đủ điều kiện để tự nhận là đã được OP1/OP2/OP3 phê duyệt. Đây là giới hạn kết quả tra cứu, không kết luận các hồ sơ đó không tồn tại trong hệ thống nội bộ.

Không dùng bài báo sao chép chương trình HomeCare làm nguồn xác nhận mức phí/ưu đãi trong đợt này vì chưa đối chiếu được công bố gốc của nhà cung cấp. Các nguồn liên quan `.vin` gần giống thương hiệu hoặc hostname UAT cũng không dùng nhập dữ liệu vận hành.

## 6. Tiêu chí nhập và nghiệm thu đề xuất

1. Tái sử dụng ID/reference đã có, không nhập trùng tiện ích và không đổi phạm vi OP1 thành OP2/OP3.
2. Bốn chủ đề mới có thể biên tập thành FAQ, giữ nguồn và ngày; các giá trị thay đổi như giờ, giá, ETA dẫn tới nhà cung cấp.
3. Tài khoản login sạch nhưng metadata nguồn vẫn nguyên; email `.test` không được gửi qua SMTP thật.
4. Kiểm thử site filtering, cư dân chỉ đọc căn của mình, staff chỉ thấy việc/phạm vi phù hợp, quên mật khẩu không tiết lộ account và Platform chỉ nhận trường theo grant.
5. Không ghi nhận người duyệt/chứng nhận giả; dữ liệu do dự án tạo không được trình bày thành bằng chứng operator xác nhận.
6. Báo cáo tách số record nhập, FAQ được tìm thấy, ca có người, tool được cấp quyền và giao dịch hoàn thành. Một import thành công không thay nghiệm thu Agent hoặc nghiệp vụ hai hệ thống.
