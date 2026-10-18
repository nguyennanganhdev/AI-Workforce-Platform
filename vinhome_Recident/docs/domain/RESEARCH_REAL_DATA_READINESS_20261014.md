# Dữ liệu thật cho Domain Vinhomes: nguồn, mức sẵn sàng và phần cần bổ sung

Ngày khảo sát: **14/10/2026**. Phạm vi: kho dữ liệu đi kèm source của Domain và nguồn công khai chính thức. Đây là nghiên cứu dữ liệu, không phải xác nhận toàn bộ database/VPS đã sạch hoặc đã được Vinhomes nghiệm thu. Lượt này không import dữ liệu, gọi Agent/embedding, sửa database hay triển khai dịch vụ.

## 1. Kết luận cần chốt

1. **Chưa đủ cơ sở gọi database hiện tại là dữ liệu vận hành thật hoàn chỉnh của Vinhomes.** Source có schema nghiệp vụ và kho tri thức, nhưng các seed vẫn dựng tenant/tài khoản/căn hộ/giao dịch mẫu; danh mục tòa trong seed chỉ là một phần. Dữ liệu công khai không thay được sổ cư dân, danh sách nhân viên, ca trực và phân công thật. Bằng chứng nội bộ: [seed Ocean Park](../../services/vinhomes-api/src/vinhomes_api/schema/seed/0005_ocean_park.sql), [hướng dẫn import/mock](NAP_DU_LIEU.md).
2. **Bỏ role đăng nhập BQL tại Domain không đồng nghĩa xóa tổ chức, phạm vi quản lý hoặc tài liệu BQL.** Theo quyết định sản phẩm mới, BQL dùng Platform; Domain vẫn cần mã đơn vị/route, phạm vi khu/tòa, nhân viên hiện trường, quy tắc thực thi và kiến thức nghiệp vụ để xử lý công việc được giao. Đây là thiết kế áp dụng cho dự án, không phải sơ đồ tổ chức chính thức do Vinhomes công bố.
3. **Giữ dữ liệu nghiên cứu có giá trị, phân loại lại độ tin cậy.** Tài liệu công khai có thể là tham khảo; mức phí, lịch trực, quyền tiếp cận căn hộ, SLA, sơ đồ PCCC và SOP áp dụng thật cần bản hiện hành do đơn vị có thẩm quyền xác nhận. Không đổi cờ `unverified=false` thành bằng chứng đã duyệt.
4. **Phạm vi người dùng đã chốt là cả Ocean Park 1, 2 và 3.** Ba đô thị phải có `site_id`, phạm vi, đơn vị vận hành và route riêng; không trộn vì cùng thuộc Ocean City. Kho đi kèm mới có tài liệu gắn OP1, chưa phải bộ tri thức đầy đủ cho cả ba đô thị. Masteri Waterfront có nhà vận hành khác, cần phạm vi/hợp đồng riêng. Nguồn chính thức phân biệt các dự án và nhà vận hành Masteri ở mục 3.
5. **Người dùng đã xác nhận làm sạch toàn bộ dữ liệu người dùng/giao dịch hiện tại, chỉ giữ admin và cấu hình.** Việc thực hiện cần backup, manifest và kiểm tra quan hệ FK; không phân loại xóa chỉ bằng tên/email giống demo. Nghiên cứu này chỉ xác định bộ tri thức cần giữ và dữ liệu thật cần cấp lại, không thực hiện lệnh xóa.

## 2. Hiện có những tài liệu/dữ liệu nào

Đọc trực tiếp file [ocean-park-1.jsonl.gz](../../services/vinhomes-api/src/vinhomes_api/schema/knowledge/ocean-park-1.jsonl.gz), không gọi nhà cung cấp:

| Chỉ tiêu trong file đi kèm | Số lượng |
|---|---:|
| Tài liệu / đoạn văn | 164 / 648 |
| Dành cho cư dân / dành cho nhân viên | 115 / 49 |
| Nhóm chung toàn đô thị | 12 |
| Nhóm `01-vinhomes` | 50 |
| Nhóm `02-masterise` | 21 |
| Nhóm thấp tầng | 32 |
| Tham khảo kế toán / kỹ thuật / vệ sinh | 29 / 1 / 12 |
| SOP vệ sinh tự đóng gói | 7 |
| Đánh dấu `unverified=true` | 21, toàn bộ thuộc nhóm Masterise |
| Có `metadata.sources` | 15 |
| Có `metadata.frontMatter.source_url`, không có `metadata.sources` | 41 |
| Có URL HTTP/HTTPS ở một trong hai vị trí trên | 44: 2 cư dân, 42 nhân viên |
| Có trường nguồn nhưng chỉ mô tả/placeholder, không URL HTTP/HTTPS | 12 |
| Không có cả hai trường nguồn trên | 108 |
| Có `metadata.review` | 0 |

SHA-256 file khảo sát: `10bc45eadcbd8b64ba4938f79df11fc46fda5cd4778b088dfb9ebc7220868da6`.

Các nhóm hàng trong bảng là những phép đếm khác nhau, không cộng tất cả thành một tổng. 157 tài liệu mang `knowledge_base=ocean-park-1`; 7 SOP mang `ocean-park-1-sop`. Một trường `sources` có thể là câu “chưa thu thập”, tên website hoặc nguồn bên thứ ba, nên **có trường nguồn chưa chứng minh đã xác minh nguồn**. 44 tài liệu có URL cũng chưa có nghĩa cả 44 đã được đơn vị vận hành duyệt.

Theo hàm [knowledge.provenance](../../services/vinhomes-api/src/vinhomes_api/knowledge.py), nếu import nguyên metadata của file này, **164 tài liệu đều được phân loại `reference`** vì thiếu hồ sơ duyệt `review`; 143 tài liệu có `unverified=false` vẫn không đủ điều kiện `approved`. Đây là kết quả đối chiếu file với code, **không phải số đếm metadata hiện tại trên VPS**; database có thể đã được cập nhật độc lập.

Những nội dung đang có gồm: liên hệ, phí, thẻ, xe và sạc điện, tiện ích, nội quy, an toàn và xử lý tình huống theo khu/tòa; trích đoạn văn bản quản lý chung cư/kế toán; tham khảo kỹ thuật từ cơ quan/nhà sản xuất; 7 SOP vệ sinh. Các tài liệu nội bộ vẫn cần giữ theo đúng người đọc, không biến thành tài liệu công khai cho cư dân.

Các template [data-templates](../../deploy/data-templates) đã có `staff.csv`, `shifts.csv`, `management_coverage.csv`, `service_categories.csv`, `resident-service-catalog.csv`. Chúng là **mẫu cấu trúc**, không phải danh sách nhân sự/dịch vụ đã được cấp. `resident-service-catalog.csv` hiện chỉ có header, chưa có dòng dịch vụ thật.

**Khoảng trống multi-site:** file tri thức hiện ghi `site=ocean-park-1`; [schema tri thức hiện hành](../../services/vinhomes-api/src/vinhomes_api/schema/migrations/0013_knowledge.sql) không có cột `site_id` riêng trên tài liệu. Tài liệu có `zone_id=NULL/building_ids=NULL` được hiểu là toàn tenant trong tra cứu. Khi một tenant chứa cả ba đô thị, phải thêm ràng buộc site và backfill đúng OP1 trước khi cho cư dân OP2/3 dùng; không nâng tài liệu “toàn OP1” thành “toàn Ocean City”. Đây là phát hiện source, chưa xác nhận migration mới đã triển khai.

## 3. Catalog nguồn chính thức đã kiểm tra

Ngày truy cập nguồn dưới đây: **14/10/2026**. Ngày bài viết/phiên bản chỉ ghi khi trang thể hiện rõ. Việc trang còn truy cập được không tự gia hạn hiệu lực thông báo cũ.

| Mã | Nguồn trực tiếp và phiên bản quan sát | Có thể lấy để làm gì | Giới hạn áp dụng |
|---|---|---|---|
| S01 | [Ocean Park: giới thiệu điểm nhấn](https://oceanpark.vinhomes.vn/gioi-thieu-diem-nhan/) — trang dự án, không thấy ngày cập nhật nội dung | Tên dự án, các nhóm tiện ích như hồ, biển hồ, gym ngoài trời, BBQ; nhận diện địa điểm | Trang giới thiệu có lưu ý thông tin/tiện ích có thể điều chỉnh; không phải danh mục booking, phí hoặc lịch phục vụ hiện hành |
| S02 | [Vinhomes Market: Ocean Park 1](https://market.vinhomes.vn/du-an/vinhomes-ocean-park) | Đối chiếu tên dự án/địa điểm công khai; phân biệt với OP2/3 | Nội dung bán hàng không thay sổ địa bàn/căn hộ và phạm vi vận hành đã ký |
| S03 | [Vinhomes: Ocean Park 2](https://vinhomes.vn/en/oceanpark2) | Đối chiếu dự án OP2 và nhóm Royal Wave Park | Search index đọc được nội dung; mở trang trực tiếp lỗi trong lượt khảo sát. Không coi là dữ liệu OP1, không nạp lịch/giá từ trang này |
| S04 | [Ocean Park 3: trang dự án](https://oceanpark3.vinhomes.vn/) | Đối chiếu dự án OP3 và nhóm Paradise Bay | Dự án riêng; không dùng tiện ích/địa chỉ OP3 trả lời cho hộ OP1 |
| S05 | [Vinhomes Market: liên hệ BQL Ocean Park](https://market.vinhomes.vn/en/blog/lien-he-ban-quan-ly-du-an-vinhomes-ocean-park-nhu-the-nao-2) — **28/06/2024** | Danh bạ tham khảo có ngày nguồn, xem mục 4 | Không phải xác nhận danh bạ hiện hành tháng 10/2026; không lấy hotline bán hàng ở footer làm số trực tòa |
| S06 | [Vinhomes Market: tòa BE2, The Beverly](https://market.vinhomes.vn/toa-nha/be2-vinhomes-ocean-park) — không thấy ngày cập nhật từng trường | Cho thấy dữ liệu công khai có nhóm/tòa khác ngoài danh mục seed đang dùng | Không suy trạng thái bàn giao, phòng/căn đang ở từ thông số marketing; biểu phí FAQ không có quyết định hiệu lực kèm theo |
| S07 | [Vinhomes: ra mắt trợ lý ảo Resident/Online](https://vinhomes.vn/vi/ra-mat-tro-ly-ao-tren-ung-dung-vinhomes-resident-va-vinhomes-online) — bài mô tả **tháng 7/2022** | Nghiên cứu nhu cầu CSKH: thông tin khu, hóa đơn, tiện ích, tin tức | Khả năng app chính thức không chứng minh hệ thống dự án này đã tích hợp API/hóa đơn/booking thật |
| S08 | [Vinhomes: hướng dẫn V-App thanh toán](https://vinhomes.vn/vi/mo-v-app-san-uu-dai-cung-vinhomes-thanh-toan-ngay-nhan-qua-lien-tay) — chương trình **01–17/02/2026** | Có thể lưu hướng dẫn tham khảo có thời hạn; nguồn mô tả liên kết mã căn theo số điện thoại Resident | Khuyến mại đã hết kỳ tại ngày nghiên cứu; không import ưu đãi vào policy hiện hành, không suy ra API liên thông |
| S09 | [Vinhomes Market: các khoản chi phí chung cư](https://market.vinhomes.vn/blog/chi-phi-o-chung-cu-moi-thang-bao-gom-nhung-gi) — **24/04/2026** | Phân loại chủ đề phí, câu hỏi cần tài liệu | Bài cẩm nang có bảng “tham khảo/dự kiến”, không phải bảng phí áp dụng cho OP1 hoặc chứng từ tính tiền từng hộ |
| S10 | [Masteri Waterfront factsheet](https://masterisehomes.com/masteri-waterfront/wp-content/uploads/2023/08/Masteri-Waterfront-Factsheet-VIE-26.10.2022-.pdf) — tên file phiên bản **26/10/2022**, PDF 9 trang | Tài liệu chủ đầu tư mô tả dịch vụ và nhà quản lý Masterise Property Management | Đơn vị khác; không cấp thẩm quyền cho route Vinhomes. Giữ reference riêng, không gắn phí/ca của họ sang OP1 Vinhomes |
| S11 | [Masterise: bàn giao Masteri Waterfront](https://masterisehomes.com/masteri-waterfront/2023/10/17/du-an-cua-masterise-homes-tai-mien-bac-chinh-thuc-ban-giao-cho-cu-dan/) — **17/10/2023** | Đối chiếu đơn vị quản lý và ranh giới tiện ích chung/riêng | Bài bàn giao/khuyến mại lịch sử không quyết định quyền sử dụng hoặc phí của mọi cư dân hôm nay |
| S12 | [Chính phủ: TT09/2025/TT-BXD](https://vanban.chinhphu.vn/?docid=214346&pageid=27160) — hiệu lực **01/07/2025** | Đối chiếu thay đổi thẩm quyền/quy định liên quan | Phải đối chiếu điều/mẫu cụ thể, không thay toàn bộ SOP bằng một trích dẫn chung |
| S13 | [Chính phủ: TT32/2025/TT-BXD](https://vanban.chinhphu.vn/?classid=1&docid=215947&orggroupid=4&pageid=27160) — hiệu lực **10/11/2025** | Đối chiếu sửa đổi TT05/2024 | Không được trình bày bản TT05 năm 2024 chưa hợp nhất như toàn bộ quy định hiện hành |
| S14 | [Bộ Xây dựng: TT08/2026 và các sửa đổi](https://moc.gov.vn/vn/_layouts/15/NCS.Webpart.MOC/mt_poup/Intrangweb.aspx?IdNews=91853), [trang văn bản Chính phủ](https://vanban.chinhphu.vn/?docid=216996&pageid=27160) — hiệu lực **15/02/2026** | Nguồn xác nhận TT05 đã được sửa đổi bởi TT09, TT32 và TT08 | Phần mô tả TT08 chủ yếu liên quan đối tượng/mẫu nhà ở xã hội; không kết luận mọi điều về quản lý chung cư trong kho đều bị sửa |
| S15 | [Vinhomes Market: địa chỉ OP1](https://market.vinhomes.vn/en/blog/dia-chi-chinh-xac-cua-vinhomes-ocean-park-1-o-dau) — **28/06/2024** | Xác định đô thị OP1 ở Hà Nội; địa danh theo nguồn thời điểm 2024 | Không coi cấp huyện/xã trong bài cũ là địa giới hiện hành 2026 |
| S16 | [Vinhomes Market: địa chỉ OP2](https://market.vinhomes.vn/blog/dia-chi-chinh-xac-cua-vinhomes-ocean-park-2-o-dau) — **22/07/2024** | Xác định OP2 ở Hưng Yên, tên địa bàn lịch sử Nghĩa Trụ/Long Hưng | Địa giới cần bản xác nhận hiện hành |
| S17 | [Vinhomes công bố thông tin chi nhánh Hưng Yên](https://gcp-cdn.vinhomes.vn/cms-data/20221103_Disclosure%20Information_1667895456.pdf) — văn bản **04/11/2022** | Xác nhận tên thương mại Ocean Park 2 – The Empire, Dream City và địa chỉ theo thời điểm văn bản | Không tự tạo đội/nhân viên/coverage hiện tại từ việc có chi nhánh |
| S18 | [Vinhomes Market: địa chỉ OP3](https://market.vinhomes.vn/en/blog/dia-chi-chinh-xac-cua-vinhomes-ocean-park-3-o-dau-2) — **23/08/2024** | Nguồn so sánh địa chỉ với homepage OP3 | Địa chỉ chi tiết không khớp hoàn toàn homepage S04; giữ provenance, chờ xác nhận, không tự chọn một bản làm chuẩn |

Không sử dụng môi giới, diễn đàn, bài đăng không đối chiếu được chủ thể để biến nội dung thành quy định Vinhomes. Một số nguồn trong bundle là nhà sản xuất hoặc cơ quan kỹ thuật khác: giữ giá trị chuyên môn đúng phạm vi, không đổi nhãn thành “SOP chính thức Vinhomes”.

## 4. Dữ liệu công khai có thể sử dụng ngay và phần phải xác nhận

### 4.0. Ba site công khai tối thiểu, chưa phải master vận hành

| Site code đề xuất | Tên | Địa bàn có thể xác nhận ở mức rộng | Nguồn chính thức |
|---|---|---|---|
| `ocean-park-1` | Vinhomes Ocean Park 1 | Hà Nội; nguồn 2024 ghi Gia Lâm | [Trang dự án OP1](https://market.vinhomes.vn/du-an/vinhomes-ocean-park), [FAQ địa chỉ 28/06/2024](https://market.vinhomes.vn/en/blog/dia-chi-chinh-xac-cua-vinhomes-ocean-park-1-o-dau) |
| `ocean-park-2` | Vinhomes Ocean Park 2 – The Empire | Hưng Yên | [FAQ địa chỉ 22/07/2024](https://market.vinhomes.vn/blog/dia-chi-chinh-xac-cua-vinhomes-ocean-park-2-o-dau), [công bố thông tin 04/11/2022](https://gcp-cdn.vinhomes.vn/cms-data/20221103_Disclosure%20Information_1667895456.pdf) |
| `ocean-park-3` | Vinhomes Ocean Park 3 – The Crown | Hưng Yên | [Trang dự án OP3](https://oceanpark3.vinhomes.vn/), [FAQ địa chỉ 23/08/2024](https://market.vinhomes.vn/en/blog/dia-chi-chinh-xac-cua-vinhomes-ocean-park-3-o-dau-2) |

`site code` là mã nội bộ đề xuất cho dự án; không phải mã bất động sản chính thức do Vinhomes cấp. Không sinh `zones/buildings/units/residents/staff` dựa trên ba dòng này.

**Mâu thuẫn cần giữ nguyên bằng chứng:** homepage OP3 phần liên hệ ghi Nghĩa Trụ/Văn Giang và Tân Quang/Văn Lâm; FAQ OP3 2024 ghi Long Hưng và Nghĩa Trụ/Văn Giang. Chỉ mức tỉnh Hưng Yên nhất quán giữa hai nguồn. Cả nguồn cũ và thông tin homepage không đủ chứng minh địa giới hành chính hiện hành năm 2026. Nên lưu địa bàn rộng, bản địa chỉ theo nguồn và trạng thái `pending_confirmation`; nhận master địa chỉ từ đơn vị vận hành trước khi xuất giấy tờ/phân tuyến chi tiết. [Homepage OP3](https://oceanpark3.vinhomes.vn/), [FAQ OP3](https://market.vinhomes.vn/en/blog/dia-chi-chinh-xac-cua-vinhomes-ocean-park-3-o-dau-2).

### 4.1. Có thể chuẩn bị làm tham khảo có trích dẫn

- **Danh mục tiện ích công khai OP1:** biển hồ, hồ Ngọc Trai, thể thao ngoài trời, BBQ, mua sắm, giáo dục/y tế trong hệ sinh thái. Chỉ mô tả sự hiện diện/nhóm nhu cầu theo nguồn; không tự cấp quyền booking, chốt giá, hứa còn slot hoặc đảm bảo giờ mở cửa. [S01](https://oceanpark.vinhomes.vn/gioi-thieu-diem-nhan/), [S06](https://market.vinhomes.vn/toa-nha/be2-vinhomes-ocean-park).
- **Tham khảo tiện ích OP2/3:** OP2 có Royal Wave Park; OP3 có Paradise Bay trong giới thiệu chính thức. Nạp theo site riêng với `reference`, không dùng vé/quyền cư dân của một khu cho khu khác. Các brand/giờ/giá và điều kiện vào khu có thể thay đổi, cần bảng hiện hành của chủ dịch vụ. [OP2](https://vinhomes.vn/en/oceanpark2), [OP3](https://oceanpark3.vinhomes.vn/).
- **Danh bạ lịch sử OP1:** bài S05 ngày 28/06/2024 ghi văn phòng tầng 1 tòa S2.18; giờ 8h30–17h30 trừ Lễ/Tết; hotline trực `0247 109 5555`; dịch vụ Vinhomes `1900 232 389`, nhánh 4. Có thể giữ dưới nhãn **“nguồn công khai 2024, chờ xác nhận còn hiệu lực”**; chưa thay danh bạ vận hành 2026. Email bị che trong kết quả đọc nên không điền. [Nguồn S05](https://market.vinhomes.vn/en/blog/lien-he-ban-quan-ly-du-an-vinhomes-ocean-park-nhu-the-nao-2).
- **Hướng dẫn sử dụng kênh chính thức:** có thể trỏ cư dân tới app/kênh chính thức cho những nghiệp vụ Domain chưa tích hợp, ghi ngày phiên bản. Nội dung V-App chương trình tháng 2/2026 phải tách phần hướng dẫn khỏi ưu đãi đã hết thời gian. [S07](https://vinhomes.vn/vi/ra-mat-tro-ly-ao-tren-ung-dung-vinhomes-resident-va-vinhomes-online), [S08](https://vinhomes.vn/vi/mo-v-app-san-uu-dai-cung-vinhomes-thanh-toan-ngay-nhan-qua-lien-tay).
- **Tài liệu nền nghiệp vụ:** giữ văn bản gốc, tham khảo kỹ thuật/nhà sản xuất và nguồn đã nghiên cứu cùng hash/phiên bản. Không dùng bảng giá chung cư tham khảo S09 để tính công nợ thật cho cư dân. [S09](https://market.vinhomes.vn/blog/chi-phi-o-chung-cu-moi-thang-bao-gom-nhung-gi).

Các mục trên là **đề xuất gói nhập dữ liệu**, chưa được import trong nghiên cứu này. Không cần tạo cư dân/nhân viên giả để nhập tài liệu tham khảo.

### 4.2. Cần rà soát lại phiên bản văn bản pháp lý đang có

Bundle có **18 tài liệu** ghi `source_id=moc_condominium_regulation`, nhiều front matter tự nêu bản TT05/2024 gốc, chưa hợp nhất sửa đổi. Nguồn Chính phủ/Bộ Xây dựng đã xác nhận các sửa đổi S12–S14. Do đó cần:

1. Giữ bản 2024 làm nguồn lưu trữ, không xóa vì là bản cũ.
2. Đối chiếu **từng điều/mẫu được trích** với các sửa đổi; lưu điều nào còn nguyên, điều nào bị thay/bãi bỏ.
3. Tạo phiên bản tri thức hiện hành có lịch sử thay thế và người rà soát. Chỉ chuyển thành kiến thức vận hành khi đúng điều, đúng thời điểm, đúng đối tượng.

Tìm thấy bản hợp nhất [17/VBHN-BXD ngày 24/03/2026](https://moc.gov.vn/Images/FileVanBan/BXD_17-VBHN-BXD_24032026.pdf) trên chỉ mục nguồn Bộ Xây dựng; tải trực tiếp trả **502** trong lượt này. **Chưa tải/hash/đối chiếu trọn văn bản này**, nên chưa dùng để tuyên bố 18 tài liệu đã được cập nhật. Việc TT08 sửa mẫu nhà ở xã hội không tự chứng minh các điều vận hành chung cư đang trích đều hết hiệu lực. [Bộ Xây dựng mô tả phạm vi sửa đổi](https://moc.gov.vn/vn/_layouts/15/NCS.Webpart.MOC/mt_poup/Intrangweb.aspx?IdNews=91853).

## 5. Các dataset thật còn cần cấp

“Cấp” dưới đây có thể là export CSV/Excel, PDF/scan có số văn bản, hoặc API chính thức được cho phép. Chỉ lấy trường cần thiết; không yêu cầu gửi mật khẩu, private key, toàn bộ hồ sơ giấy tờ cá nhân vào chat.

| Ưu tiên | Bộ dữ liệu cần | Trường tối thiểu / tài liệu cần đối chiếu | Ai xác nhận |
|---|---|---|---|
| P0 | Master địa bàn đủ cho cả OP1/2/3 | Mã/tên đô thị, phân khu/tòa/khối thấp tầng/căn, địa chỉ hiện hành, trạng thái bàn giao, đơn vị vận hành, phạm vi được tích hợp; đánh dấu Masterise/đơn vị khác | Đơn vị vận hành/chủ dự án |
| P0 | Cư dân và quan hệ cư trú | External ID, tài khoản liên hệ cần thiết, mã căn, owner/tenant/household, thời gian hiệu lực, xác minh/thu hồi quan hệ; quy tắc onboarding | Đơn vị được phép cung cấp sổ cư dân |
| P0 | Nhân viên hiện trường thật | Mã nhân viên, tên, tài khoản, chuyên môn Kỹ thuật/An ninh/Vệ sinh, đội/nhà thầu, khu/tòa được phép, chứng chỉ khi công việc yêu cầu, trạng thái hoạt động | Quản lý nhân sự/nhà thầu |
| P0 | Ca trực và năng lực nhận việc | Nhân viên/đội, ca có timezone, ngày nghỉ, capacity, on-call, người thay thế, ưu tiên tuyến | Quản lý vận hành |
| P0 | Route và ma trận trách nhiệm | Mã đơn vị ở Domain ↔ route ở Platform; category/issue, phạm vi, đội nhận, trường hợp không phục vụ, người quyết định/phê duyệt, quy tắc ngoài giờ | BQL dùng Platform/chủ dự án |
| P0 | SOP/SLA ba nhóm đang mở | Quy trình kỹ thuật, an ninh, vệ sinh; triage/khẩn cấp, tác vụ cấm, quyền vào căn, PPE, checklist, ảnh/bằng chứng và tiêu chí nghiệm thu, thời hạn phản hồi/xử lý, escalation | Đơn vị vận hành phê duyệt |
| P0 | Danh bạ vận hành | Số trực theo tòa/đội/ca, hotline khẩn cấp đúng mục đích, email/hours, ngày hiệu lực, người sở hữu và kênh cập nhật | Đơn vị vận hành |
| P1 | Danh mục dịch vụ cho cư dân | Mã/tên, mô tả, khu/tòa, đối tượng được dùng, phí hay miễn phí, giờ, đăng ký trước, hủy/hoàn phí, nguồn quyết định | Chủ dịch vụ/đơn vị vận hành |
| P1 | Biểu phí và miễn giảm | Service/fee code, đơn vị tính, số tiền/tiền tệ, VAT, căn/đối tượng áp dụng, thời gian hiệu lực, căn cứ, miễn giảm và phiên bản thay thế | Kế toán/đơn vị có thẩm quyền |
| P1 | Sổ tay/quy định hiện hành | Thẻ, khách, chuyển đồ, thi công, thú cưng/tiếng ồn/rác, đỗ xe/sạc, hồ bơi/BBQ; mẫu hồ sơ và người quyết định | Đơn vị vận hành |
| P1 | Knowledge pack riêng OP2 và OP3 | Sổ tay, quy định, dịch vụ, danh bạ, phí, tiện ích và SOP theo site/zone/building; xác định phần nào dùng chung toàn Ocean City bằng văn bản | Đơn vị vận hành từng site/chủ dịch vụ chung |
| P1 | Hồ sơ an toàn theo tòa | Sơ đồ thoát hiểm/điểm tập kết, phương án PCCC, bản nghiệm thu và ngày/phiên bản; phân loại bản công khai và bản chỉ nhân viên | Chủ sở hữu hồ sơ/an toàn |
| P1 | Tài sản và bảo hành | Mã/vị trí thiết bị, hãng/model/manual, bên sở hữu, bảo hành/nhà thầu, lịch bảo trì, phụ tùng nếu cần báo giá | Kỹ thuật/chủ tài sản |
| P2 | Nguồn sống cho tiện ích/khách/thẻ | API/export đặt chỗ, slot/capacity, trạng thái thẻ, lịch khách, consent; chỉ nối khi chốt module và quyền riêng | Chủ hệ thống tương ứng |
| P2 | Công nợ/thanh toán | Invoice/debit ID, phí theo căn/kỳ, số tiền, trạng thái, đối soát/refund từ hệ thống được phép | Kế toán/chủ hệ thống thu tiền |

Không lấy danh sách căn từ trang bán hàng để sinh owner/tenant. Không coi nhân viên thử và ca trực sinh tự động là nhân sự Vinhomes. Không nhập biểu phí “dự kiến/tham khảo” vào bảng thu tiền production. Tài liệu của Masterise cần owner/scope riêng dù cùng không gian đô thị. [S09](https://market.vinhomes.vn/blog/chi-phi-o-chung-cu-moi-thang-bao-gom-nhung-gi), [S10](https://masterisehomes.com/masteri-waterfront/wp-content/uploads/2023/08/Masteri-Waterfront-Factsheet-VIE-26.10.2022-.pdf).

## 6. Phân lớp dữ liệu và cách nạp đề xuất

| Lớp | Giữ / chuẩn hóa | Không được làm |
|---|---|---|
| Schema và danh mục hệ thống | Migration, constraints, role hệ thống còn dùng, issue/service codes theo hợp đồng, trạng thái và enum | Xóa cấu trúc chỉ vì có chữ `management`/`bql` |
| Master vận hành | Khu/tòa/căn, đơn vị/coverage, staff/shift, policy được xác nhận | Tự hợp thức hóa seed hoặc giả định mọi tòa thuộc cùng nhà vận hành |
| Tri thức nguồn | Văn bản/URL/file gốc, bản cắt đoạn, hash, audience/scope, nguồn/phiên bản/hiệu lực | Trộn marketing, SOP dự án và chính sách đã duyệt vào một nhãn “thật” |
| Dữ liệu người dùng/giao dịch hiện tại | Theo chỉ đạo mới: backup/manifest rồi làm sạch có kiểm soát, chỉ giữ admin và cấu hình; nạp lại bằng nguồn thật được cấp | Xóa thiếu backup, sót blob/outbox hoặc giữ một phần khiến FK/lịch sử không nhất quán; phân loại chỉ bằng tên/email |
| Demo/test | Bản ghi có lineage seed/mock/provision/test được chứng minh, chạy ở DB test riêng | `TRUNCATE`, reset hoặc xóa toàn tenant khi chưa phân loại FK và dữ liệu thật |

Quy trình nhập đề xuất:

1. Lập inventory từng bảng/file và nguồn gốc; backup có kiểm tra restore; thực hiện phạm vi làm sạch đã được người dùng xác nhận. Giữ admin/cấu hình và tri thức tham khảo, không giữ tài khoản staff/cư dân hoặc giao dịch mẫu để giả đủ dữ liệu thật.
2. Chốt owner từng dataset cho cả OP1/2/3 và site scope cho tri thức. Nhập master trước, resident/staff/ca sau, tài liệu và route/SLA sau cùng. Bộ chưa được cấp giữ trống/chưa xác nhận, không lấp bằng demo. Tạo ba site tham khảo không chứng minh đã hoàn tất master toàn bộ ba đô thị.
3. Mỗi tài liệu lưu `sources` đối chiếu được; `review.approved_by`, `approved_at`, `document_reference`, `effective_from`, tùy chọn `effective_until`; audience, scope, version và hash. Đây là tiêu chí nhập do dự án đề xuất, khớp [cơ chế provenance hiện có](../../services/vinhomes-api/src/vinhomes_api/knowledge.py).
4. Giữ reference/archived riêng với operational approved; thông tin phí/giờ/hotline thiếu hiệu lực chỉ trả nguồn và tình trạng thiếu xác nhận. Tài liệu nội bộ staff không lộ cho cư dân.
5. Dry-run import, kiểm tra FK/scope/đối tượng/hiệu lực, đối chiếu số lượng trước/sau; chỉ publish các dataset owner đã ký nhận. Thay đổi text phải version hóa, không trộn embedding model hoặc tự gọi embedding trong audit.
6. Bàn giao Platform gói nghiệp vụ đúng route gồm catalog/schema/state/SOP đã duyệt và nguồn giới hạn scope; credentials qua file riêng. Quyền BQL nằm ở Platform, không cần giữ role người dùng `management` ở Domain.

## 7. Tiêu chí xác nhận “đã dùng dữ liệu thật”

- Mỗi master/tài khoản thật có nguồn nhập và owner; không còn ca/tài khoản/giao dịch demo trong tenant vận hành. Chưa có staff/ca thật thì không tự giao việc cho demo, để hàng đợi/báo thiếu nguồn lực.
- Mỗi phí/giờ/hotline/SLA được dùng như cam kết có đúng văn bản, phiên bản, scope và thời hạn. Bản tham khảo luôn có nhãn, không được dùng thay quyết định thu phí/cho phép vào căn.
- Tài liệu 2024 giữ archive nhưng phần trả lời hiện hành đã đối chiếu sửa đổi từng điều. Hồ sơ PCCC/sơ đồ theo tòa đã được kiểm chứng; không suy sơ đồ từ số tầng marketing.
- Công cụ tìm kiếm chỉ trả đúng audience/khu/tòa/ticket được phép; có test chéo scope giữa OP1, OP2/3 và Masterise. Việc bỏ role BQL Domain không làm mất lịch sử/audit/tài liệu nghiệp vụ.
- Có báo cáo nhập dữ liệu nêu accepted/rejected/pending_review/archived và số lượng theo bảng; thống kê test/fallback tách khỏi giao dịch thật. Kết quả source test không được thay bằng chứng live production.

## 8. Giới hạn của lượt nghiên cứu

Chưa nhận được export cư dân/nhân sự/ca trực thật, bộ SOP/biểu phí/danh bạ hiện hành được đơn vị vận hành xác nhận. Không truy cập app cư dân hoặc tài liệu nội bộ yêu cầu đăng nhập. Nguồn marketing được dùng đúng mức tham khảo; không chứng minh thỏa thuận sử dụng dữ liệu thương hiệu hay quyền kết nối API chính thức. Chưa rà soát toàn bộ bản gốc cho từng đoạn trong bundle, chưa tải được bản hợp nhất PDF nêu trên, chưa chứng nhận tư cách pháp lý/ngày hiệu lực của mọi văn bản kế toán hoặc tiêu chuẩn kỹ thuật trong kho. Những phần này phải được đánh dấu còn thiếu thay vì tạo số liệu hoặc nâng cờ tin cậy tự động.

## 9. Ba trích lược tiện ích công khai để nhập dưới nhãn tham khảo

Đối chiếu thêm ngày 14/10/2026. Các trang dưới đây không thể hiện rõ ngày cập nhật từng tiện ích, nên `source_published_at=null`, `retrieved_at=2026-10-14`, `authority=reference`. Mỗi trích lược phải gắn đúng `site_id`; không tạo booking/giá/đội phục vụ từ tên tiện ích. Không chứa hotline bán hàng.

| Site | Trích lược đề xuất | Nguồn trực tiếp |
|---|---|---|
| OP1 | Trang dự án giới thiệu biển hồ nước mặn, hồ trung tâm, công viên gym ngoài trời và khu BBQ. Đây là các nhóm lựa chọn tham khảo cho nhu cầu đi dạo, vận động và sinh hoạt gia đình. Chưa xác nhận tình trạng phục vụ, giờ, phí hay quyền sử dụng của từng hộ; cần đối chiếu thông báo đơn vị vận hành trước khi đăng ký. | [Giới thiệu điểm nhấn Ocean Park](https://oceanpark.vinhomes.vn/gioi-thieu-diem-nhan/) |
| OP2 | Trang dự án giới thiệu Royal Wave Park, Empire Park, công viên ven kênh Silk Park và đại lộ Kingdom Avenue. Cư dân có thể dùng danh sách này để tìm hiểu các nhóm vui chơi, cảnh quan và đi dạo tại OP2. Chưa xác nhận tình trạng phục vụ, giờ, phí hay điều kiện áp dụng cho cư dân; cần kiểm tra kênh vận hành chính thức. | [The Empire: trang dự án](https://theempire.vinhomes.vn/), [Vinhomes: Ocean Park 2](https://vinhomes.vn/en/oceanpark2) |
| OP3 | Trang dự án giới thiệu Paradise Bay, hồ Tropical Lagoon, hồ bơi bốn mùa Four Seasons, vịnh trượt nước Aqua Bay, BBQ Garden và sân chơi trẻ em Aquarium. Đây là thông tin tham khảo theo dự án OP3. Chưa xác nhận tình trạng phục vụ, giờ, phí, điều kiện vào khu hoặc quyền sử dụng của từng hộ; cần đối chiếu đơn vị vận hành trước khi đến hay đăng ký. | [Ocean Park 3: e-brochure HTML](https://oceanpark3.vinhomes.vn/brochure/) |

Nguồn thêm [The Empire](https://theempire.vinhomes.vn/) là website dự án thuộc tên miền Vinhomes, đọc được tên tiện ích trên trang; trong cùng trang vẫn có nội dung quy hoạch/dự kiến lịch sử. Không lấy các mục y tế/trường học được giới thiệu ở đó làm bằng chứng đã khai trương hiện tại. Root sẽ quyết định nhập dữ liệu; nghiên cứu này không tự ghi database.
