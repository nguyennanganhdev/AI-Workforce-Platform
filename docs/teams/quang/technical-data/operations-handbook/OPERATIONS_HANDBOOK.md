---
title: "Sổ tay dữ liệu vận hành kỹ thuật A2 — nguồn công khai và mock phát triển"
version: "research-mock-v3"
scope: "16 issue code A2 và các yêu cầu vận hành tòa nhà liên quan"
content_status: "mixed_source_summary_and_synthetic_workflow"
approval_status: "not_published"
sop_available: false
fixture_only_for_workflows: true
direct_production_rag_ingest: false
mock_rulebook: "HB-RULES-V2"
mock_site: "SYN-B-01"
mock_case_pairs: 16
additional_cases: 10
extended_workflows: 10
---

# Sổ tay dữ liệu vận hành kỹ thuật A2

**Bản v3 — Nguồn công khai · Quy trình giả lập · Dữ liệu xây dựng dự án**

16 quy trình A2 · 32 ca A/B · 10 luồng mở rộng · 10 ca bổ sung.

27 mục nguồn tham chiếu · 20 tài sản mẫu · 23 mã giá mock.

**Phân biệt phiên bản:** tài liệu này là `research-mock-v3`, cùng phiên bản nội dung với `SO_TAY_VAN_HANH_KY_THUAT.docx`. `HB-RULES-V2` là mã phiên bản riêng của bộ quy tắc/bảng giá mock được giữ nguyên, không phải phiên bản của sổ tay. Mục 12 lưu nhật ký phát triển v2; số liệu hiện tại nằm ở mục 0 và mục 14.

**Mục tiêu:** một tài liệu Markdown để đội build tạo intake, triage, work order, yêu cầu cô lập dịch vụ, kiểm chứng hoàn tất và cây quyết định chi phí. Đây **không phải** sổ tay do Vinhomes/BQL ban hành. Mục có nhãn **[NGUỒN]** là diễn giải ngắn từ tài liệu công khai; mục **[MOCK]** là thiết kế giả lập để test; **[CẦN BQL]** là chỗ chưa có dữ liệu/ủy quyền. Không đổi nhãn mock thành SOP đã duyệt.

Tài liệu này nằm **ngoài** `rag/corpus` và `rag/mock-corpus`. Không ingest nguyên file vào KB cư dân: một chunk có thể trộn dữ kiện có nguồn với quy trình/nhánh phí mock. Nếu cần retrieval thử nghiệm, lọc section theo nhãn, review thủ công, version và đưa vào KB test riêng. Mã issue khớp `docs/teams/quang/general.md`; 10 nhóm mở rộng ở mục 10 **chưa có** mã A2 chính thức.

**Cách đọc bản v3:** mục 3 có quy trình chi tiết, mỗi quy trình gồm nhánh chẩn đoán, phiếu công việc, cách nghiệm thu và hai hồ sơ mô phỏng A/B. Mục 9 cung cấp tòa nhà, nhân sự, quy tắc bảo hành và bảng giá **hoàn toàn giả lập** để các hồ sơ chạy nhất quán. Mục 10 có mười luồng ngoài A2; mục 11 chứa biểu mẫu, hội thoại và sự kiện; mục 12 và 14 ghi lịch sử thay đổi; mục 13 có mười ca bổ sung. Các ca `HB-01-A` đến `HB-16-B` là 32 kịch bản chính, khác bốn ví dụ M01–M04 ở mục 5 và khác các fixture JSONL cũ.

Để dựng demo có kết quả cụ thể, bản v3 tiếp tục sử dụng **nhân vật kỹ thuật viên/BQL/tài chính giả lập** xác nhận nguyên nhân, báo giá và nghiệm thu trong câu chuyện. Các xác nhận ấy mang `synthetic=true`, `test_only=true`; không phải bằng chứng thật. Giá tại mục 9 dùng cho báo giá demo tách biệt; công cụ ước tính giá từ dữ liệu vận hành thật vẫn phải trả `insufficient_data` khi thiếu mẫu verified. Agent không tự viết thêm một kết quả đo/biên bản rồi coi đó là kết quả hiện trường.

## 0. Tổng kết bản v3 và kết quả rà soát

**Đã có để build demo:** 16 quy trình đúng mã A2; 32 ca A/B; 10 luồng mở rộng; 10 ca bổ sung về ngoại lệ và bàn giao; tòa mẫu với 20 asset; 23 mã giá sáng tác và 16 bảng tính; biểu mẫu, hội thoại, chuỗi sự kiện và checklist hồ sơ. Bản v3 bổ sung ma trận Level theo `general.md`, tách bảo hành công trình/thiết bị, chỉnh cách hiểu van an toàn máy nóng, đồng thời đóng gói cùng nội dung thành Word.

**Phần có nguồn:** 27 mục tham chiếu công khai, gồm nguồn Vinhomes, cơ quan quản lý, đơn vị vận hành/cấp nước và hãng. Nguồn mới R23–R27 bổ sung văn bản hợp nhất bổ sung, hai manual Ariston, diễn tập chất lượng nước chung cư ở Việt Nam và phạm vi lỗi điều hòa từ Daikin. Diễn tập công khai là hoạt động có thật với tình huống giả định, không phải sự cố đã xảy ra tại Vinhomes. Các luồng xử lý và giá của tòa mẫu vẫn là mock.

**Còn thiếu để dùng thực tế:** SOP và manual khớp asset từng tòa; bản vẽ/van/nhánh điện; quyền phê duyệt; hợp đồng và warranty thực; bảng giá/quy tắc tài chính đã duyệt; ticket, ảnh, số đo, kết quả nghiệm thu được cấp quyền. Những mục này không thể được xác minh bằng cách viết thêm mock. File dùng làm tài liệu thiết kế, KB demo và fixture; chưa phải SOP cư dân hay dữ liệu chi phí thực tế.

| Thiếu sót phát hiện khi rà v2 | Đã xử lý trong v3 | Còn phụ thuộc bên ngoài |
| --- | --- | --- |
| Chưa có bảng mức ưu tiên đầy đủ theo repo | Mục 2.3 chép lại mapping 16 mã và dấu nâng Level 1 | Policy/binding đang triển khai và thời hạn SLA phải lấy từ backend. |
| Một mẫu warranty dễ lẫn công trình với thiết bị | Tách hai hồ sơ mock ở mục 9.1 | Hợp đồng/phiếu warranty đúng căn, model và điều kiện hiệu lực. |
| Máy nóng rỉ nước chưa phân biệt van an toàn | Bổ sung nhánh HB-P03 và ca ADD-01, có manual R24/R25 | Xác nhận đúng loại máy và vị trí nước tại hiện trường. |
| Thiếu chất lượng nước, AC kém lạnh, nước mưa | Thêm EXT-08 đến EXT-10 | Quy chuẩn/model, kết quả thử và scope tài sản. |
| Chưa đủ hủy việc, hoàn tiền, đổi scope, bàn giao ca | 10 ca ADD, sổ quyết định và checkpoint ở mục 13 | Quyền actor và policy nghiệp vụ thực. |
| Nguồn pháp lý mới chỉ gồm bản hợp nhất R02 | Ghi thêm nguồn 17/VBHN-BXD, chỉ rõ mức truy cập | Chưa thẩm định toàn bộ chuỗi sửa đổi/pháp lý của từng quyết định. |
| Chưa có bản Word thống nhất | Xuất `SO_TAY_VAN_HANH_KY_THUAT.docx` từ Markdown | Chỉ cần một DOCX để đọc/chia sẻ; Markdown giữ làm bản nguồn. |

## 1. Những gì thực sự tìm được

| ID | Nguồn công khai đã đọc | Dữ kiện rút ra cho thiết kế | Giới hạn |
| --- | --- | --- | --- |
| R01 | [Luật Nhà ở, Điều 129–130 và 142](https://vbpl.vn/thanhtrachinhphu/Pages/vbpq-toanvan.aspx?ItemID=169032) | Chủ sở hữu bảo trì phần riêng và đóng góp cho phần chung; phần riêng/chung phụ thuộc hạng mục, hệ thống và hợp đồng; có nhánh bảo hành nhà ở. | Không kết luận một cư dân/người thuê cụ thể phải trả tiền từ triệu chứng. Cần kiểm tra văn bản sửa đổi hiện hành khi áp dụng. |
| R02 | [Bộ Xây dựng, văn bản hợp nhất 08/VBHN-BXD](https://www.moc.gov.vn/Images/FileVanBan/BXD_08-VBHN-BXD_09072025.pdf) | Nguyên tắc bảo trì riêng/chung và kế hoạch bảo trì phần chung; căn cứ để yêu cầu hồ sơ, thẩm quyền, phê duyệt. | Văn bản đã có các sửa đổi; pháp chế/BQL phải xác minh phiên bản hiệu lực áp dụng cho quyết định. |
| R03 | [Mẫu hợp đồng căn hộ Vinhomes công khai, Điều 9](https://gcp-cdn.vinhomes.vn/cms-data/VHSC_HDMB%20CHCC_Vn_1725965817.pdf) | Ví dụ phạm vi bảo hành, thời hạn trong mẫu, loại trừ hao mòn/lỗi người dùng/tự lắp hoặc tự sửa và phí ngoài phí quản lý. | **Chỉ là một mẫu hợp đồng**, không tự áp cho Ocean Park hoặc mọi tòa; phải đọc hợp đồng/phụ lục đã ký của căn thực tế. |
| R04 | [Vinhomes: kênh hỗ trợ cư dân](https://vinhomes.vn/vi/nhung-la-thu-cam-on-tu-cu-dan-va-dich-vu-tu-trai-tim-vinhomes) | Có ví dụ cư dân báo kỹ thuật qua lễ tân/điện thoại và tương tác app với BQL. | Bài truyền thông không cung cấp SOP, SLA, bảng giá hay quyền cô lập dịch vụ. |
| R05 | [Bộ Công Thương: an toàn điện mùa mưa](https://moit.gov.vn/tin-tuc/su-dung-nang-luong-tiet-kiem-va-hieu-qua/khuyen-cao-su-dung-dien-an-toan-trong-mua-dong.html) và [EVN: an toàn điện](https://www.evn.com.vn/vi-VN/an-toan-dien/An-toan-dien-60-3550) | Nước/ngập gần điện là nguy cơ cần tránh tiếp xúc và xử lý an toàn; thiết bị điện cần nhân sự chuyên môn. | Không suy ra người/điểm cắt điện tại tòa từ bài phổ biến an toàn. |
| R06 | [PMC: thiết bị điện](https://pmcweb.vn/cong-tac-quan-ly/sua-chua-bao-tri-chung-cu/thiet-bi-dien/) | Đơn vị quản lý khác nhấn mạnh sửa/bảo trì điện bởi người có chuyên môn. | Không phải SOP Vinhomes hoặc quy định pháp lý cho mọi dự án. |
| R07 | [PMC: cấp–thoát nước chung cư](https://pmcweb.vn/cong-tac-quan-ly/sua-chua-bao-tri-chung-cu/he-thong-cap-thoat-nuoc/) | Phân biệt bơm/bồn/trục đứng/nhánh cấp, thoát nước mưa–thải, bẫy nước và các điểm cần kiểm tra. | Không áp sơ đồ đường ống hoặc trách nhiệm thanh toán của PMC cho một tòa khác. |
| R08 | [PMC: bảo trì cửa sổ](https://pmcweb.vn/cong-tac-quan-ly/sua-chua-bao-tri-chung-cu/bao-tri-cua-so/) | Cấu kiện cửa/kính có thể tạo nguy cơ rơi, cần kiểm tra theo cấu hình thực. | Không biết model và quyền sửa cửa mặt ngoài Vinhomes. |
| R09 | [Daikin Việt Nam: dàn lạnh chảy nước](https://www.daikin.com.vn/truyen-thong/kinh-nghiem-hay/nguyen-nhan-va-cach-khac-phuc-tinh-trang-dieu-hoa-bi-chay-nuoc-dan-lanh) | Bộ lọc, đường thoát nước ngưng, lắp đặt là các khả năng cần phân biệt. | Không chẩn đoán đúng model bằng một bài tổng quát; không giao thao tác cho cư dân. |
| R10 | [Panasonic Việt Nam: bảo dưỡng máy lọc RO](https://www.panasonic.com/vn/consumer/customer-service-learn/all/dich-vu-bao-duong-may-loc-nuoc-ro.html) | Ví dụ quy trình dịch vụ hãng: kiểm tra tình trạng, thông báo linh kiện, chạy thử và bàn giao/nghiệm thu. | Dịch vụ của Panasonic, không phải quy trình của máy khác hoặc Vinhomes. |
| R11 | [INAX Việt Nam: FAQ bàn cầu](https://www.inax.com.vn/vi/product-support/ban-cau/) | Tách nước cấp két yếu, nước chảy liên tục, xả yếu và mùi; có nhiều bộ phận/triệu chứng khác nhau. | Cấu tạo theo model; không suy mọi bàn cầu dùng linh kiện INAX. |
| R12 | [Blum Việt Nam: bản lề CLIP top](https://www.blum.com/vn/vi/products/hingesystems/clip-top/overview/) | Cánh tủ lệch có thể liên quan hệ bản lề/đế; phải xác định model trước khi can thiệp. | Không xác nhận tủ căn hộ dùng Blum hoặc đủ điều kiện bảo hành. |
| R13 | [Weber Việt Nam: khu vực ẩm ướt](https://www.vn.weber/vi/cong-tac-op-lat-khu-vuc-am-uot) | Khi thấm phòng tắm cần phân biệt ron/keo/lớp chống thấm bên dưới. | Hệ vật liệu Weber không chứng minh cấu tạo căn cụ thể. |
| R14 | [US EPA: ẩm và nấm mốc](https://www.epa.gov/mold/brief-guide-mold-moisture-and-your-home) | Xử lý nguồn ẩm trước bề mặt; vết mốc là tín hiệu kiểm tra, không đủ định danh nguyên nhân. | Hướng dẫn Hoa Kỳ, không thay đánh giá sức khỏe/kết cấu tại Việt Nam. |
| R15 | [US HUD: NSPIRE Standards](https://www.hud.gov/reac/nspire-standards) | Bộ phân loại khiếm khuyết điện, nước, cửa, sàn, tường, trần, kết cấu, lối thoát; hữu ích làm checklist quan sát. | **Không nhập ngưỡng, thời hạn hoặc điểm vi phạm HUD** thành policy/SLA Vinhomes. |
| R16 | [Cổng phản ánh Huế: ví dụ nước thải trào chung cư](https://tuongtac.hue.gov.vn/phan-anh/su-co-nuoc-thai-sinh-hoat-tran-ngap-len-nha-de-xe-nhieu-lan-o-khu-e-chung-cu-xuan-phu-a18939.html) | Mẫu phân biệt lời phản ánh cư dân và phản hồi cơ quan; có thể ảnh hưởng khu chung/nhiều căn. | Không phải ticket, chẩn đoán, biên bản sửa hoặc kết quả nghiệm thu Vinhomes. |
| R17 | [A. O. Smith: cân nhắc sửa máy nước nóng](https://www.hotwater.com/info-center/water-heater-repair-things-to-consider.html) | Loại máy, tuổi/bảo hành, loại hư hỏng và kỹ thuật viên là dữ kiện lựa chọn nhánh xử lý. | Hãng/thiết bị khác nhau; không dùng làm lệnh sửa tại hiện trường. |
| R18 | [Savills Việt Nam: cơ sở lập kế hoạch bảo trì chung cư](https://vn.savills.com.vn/blog/article/212722/vietnam-viet/co-so-xay-dung-ke-hoach-bao-tri-cho-toa-nha-chung-cu.aspx) | Phân biệt bảo trì thường xuyên, ngăn ngừa và sửa chữa; kế hoạch cần dựa trên hiện trạng, hệ thống kỹ thuật và hướng dẫn thiết bị. Hạng mục phức tạp như thang máy, trạm điện, PCCC có thể cần đơn vị chuyên biệt. | Bài tư vấn viện dẫn cả văn bản cũ; không dùng phần trích luật của bài làm căn cứ pháp lý hiện hành, không suy lịch bảo trì hay năng lực nhà thầu cụ thể của Vinhomes. |
| R19 | [Vinhomes: Báo cáo thường niên, trang 36–37](https://gcp-cdn.vinhomes.vn/cms-data/Vinhomes-2023-AR-vF_1712109407.pdf) | Công bố Vinhomes Resident và các công cụ vận hành V-PMS, SmartHub, CSM; đây là chứng cứ về kênh/hệ thống ở mức giới thiệu. | Báo cáo không công bố API, trường ticket, quyền duyệt, SLA, SOP cô lập hoặc biểu phí; không coi schema ở mục 6 là schema V-PMS. |
| R20 | [Cục Cảnh sát PCCC và CNCH: thoát nạn nhà cao tầng](https://www.canhsatpccc.gov.vn/vi/news/huong-dan-cong-dong/ky-nang-thoat-nan-can-luu-y-khi-xay-ra-chay-no-nha-cao-tang-2301) | Bản chỉ mục nêu khi cháy/nổ dùng lối thoát nạn an toàn, không dùng thang máy để thoát nạn. | Lần kiểm tra này tải toàn văn bị timeout; chỉ dùng điểm an toàn ngắn từ bản chỉ mục. Không phải phương án ứng cứu của một tòa. |
| R21 | [Cục Cảnh sát PCCC và CNCH: sự cố thang máy](https://cspccc.canhsatpccc.gov.vn/vi/news/nghien-cuu-trao-doi/mot-so-tinh-huong-va-phuong-phap-cnch-su-co-thang-may-co-ban-846) | Bản chỉ mục nêu tình huống cần liên hệ đơn vị cung cấp thang/lực lượng CNCH; thông tin cabin/tầng, liên lạc và người kẹt cần cho chuyển giao. | Lần kiểm tra này tải toàn văn bị timeout; **không** chuyển các bước cứu hộ chuyên môn vào hướng dẫn cho agent/cư dân. |
| R22 | [Cục Cảnh sát PCCC và CNCH: an toàn khi rò khí gas](https://canhsatpccc.gov.vn/vi/news/huong-dan-cong-dong/bien-phap-bao-dam-an-toan-pccc-viec-su-dung-khi-gas-tai-cac-ho-gia-dinh-1722) | Bản chỉ mục nêu tránh nguồn lửa/nhiệt và thao tác bật–tắt thiết bị điện khi nghi rò gas. | Lần kiểm tra này tải toàn văn bị timeout; không chứng minh tòa dùng hệ gas nào và không thay phương án ứng cứu/sơ đồ van. |
| R23 | [Bộ Xây dựng: 17/VBHN-BXD](https://moc.gov.vn/vn/pages/ChiTietVanBan.aspx?TypeVB=2&vID=4897) | Có bản hợp nhất mới hơn R02 về Thông tư quy định chi tiết Luật Nhà ở. | Xác minh thông tin phát hành qua chỉ mục chính thức; PDF tải lỗi 502 trong đợt này. Không tuyên bố đã thẩm định toàn văn hoặc áp mọi thay đổi cho sửa chữa căn hộ. |
| R24 | [Ariston: manual ANDRIS3 R/RS/B, phần tiếng Việt trang 10–11](https://www.ariston.com/content/dam/ariston/vn/products/indirect-water-heater/andris/andris3-rs-mt-15-30/420011413000_USER_ANDRIS3_R_RS_B_VN.pdf) | Phân biệt nước nhỏ tại bộ phận an toàn quá áp khi đun với lỗi rò cần kiểm tra; phải xác định model và vị trí. | Đã đọc PDF; chỉ cho dòng máy nêu trong manual, không áp sang máy trực tiếp hoặc mọi máy nước nóng. |
| R25 | [Ariston: manual AURES TOP, phần tiếng Việt từ trang 10](https://www.ariston.com/content/dam/ariston/vn/products/direct-water-heater/aures-2-0/aures-top/420011260503_AURES%20TOP%204.5P.pdf) | Có hướng dẫn theo model, yêu cầu nhân sự đủ chuyên môn và các dấu bất thường cần dịch vụ kiểm tra. | Đã đọc PDF; manual công khai không chứng minh tòa mẫu có thiết bị này hoặc là SOP BQL. Không nhập thông số của máy này vào asset chưa rõ model. |
| R26 | [SAWACO/Trung An: diễn tập tại chung cư OSIMI](https://sawaco.com.vn/post-detail/cong-ty-co-phan-cap-nuoc-trung-an-dien-tap-cap-nuoc-an-toan-nam-2026-260929163543) | Ví dụ Việt Nam về phối hợp tiếp nhận, khảo sát, lấy mẫu và công bố kết quả theo phạm vi hệ cấp nước. | Đã đọc bài đầy đủ; các kết quả kiểm nghiệm trong bài thuộc kịch bản diễn tập, không phải dữ liệu sự cố thật. |
| R27 | [Daikin Việt Nam: hỗ trợ xử lý sự cố máy điều hòa dân dụng](https://www.daikin.com.vn/truyen-thong/tin-tuc/chatbot-daikin-vietnam-he-thong-ho-tro-xu-ly-su-co) | Các nhóm báo lỗi, chảy nước, kém lạnh và mã lỗi cần dữ liệu tiếp nhận riêng. | Đã đọc bài; không có bảng mã lỗi/SOP cho mọi model trong bài, không suy nguyên nhân hoặc phí từ tên nhóm lỗi. |

**Trạng thái crawl:** đã trích xuất/diễn giải nội dung công khai; R20–R22 chỉ xác minh qua chỉ mục do timeout, R23 mới xác minh thông tin phát hành do PDF lỗi 502. R05 được đối chiếu lại qua bản chỉ mục có nội dung bài; R24–R27 đã đọc nội dung nguồn. Không chép lại toàn văn HTML/PDF và chưa có snapshot/hash/giấy phép tái phân phối. Sổ 74 ID nguồn/72 URL và 77 fact cũ vẫn ở `../RAG_SOURCE_MANIFEST.jsonl` và ba file `*_FACTS.jsonl`; bảng này là phần nghiên cứu riêng cho sổ tay, không cộng URL trùng thành nguồn độc lập. `Data-Vinhome` từng được repo kiểm kê nhưng chưa có chuỗi ticket–chẩn đoán–sửa chữa–nghiệm thu đủ xác minh để thay SOP. Chưa tìm thấy SOP kỹ thuật Vinhomes đúng tòa/model, biểu phí theo lỗi, ma trận cắt dịch vụ hoặc ticket thật được phép dùng.

## 2. Hợp đồng dữ liệu và nguyên tắc chung [MOCK]

Mỗi yêu cầu phải có `ticket_id`, `building_id`, `unit_id` hoặc `common_area_id`, `source_channel`, lời báo nguyên văn, `issue_code` dự kiến, ảnh có quyền sử dụng, `unknown_fields`, `asset_id/model`, chủ sở hữu asset, phiên bản SOP/policy nếu tồn tại, người nhận và trace. Dữ kiện do cư dân nói là `reported`, không tự biến thành `confirmed`; mọi giả thuyết chẩn đoán bắt đầu ở `unconfirmed`. R19 cho thấy Vinhomes có công cụ vận hành, nhưng không công khai hợp đồng dữ liệu của chúng; các tên trường bên dưới hoàn toàn là thiết kế thử nghiệm, không giả định đồng bộ được với V-PMS.

Luồng đề xuất dùng chung cho 16 playbook:

1. **Tiếp nhận:** tạo ticket, xác minh tòa/căn và quyền xem; lưu lời báo và liên kết sự kiện, phát hiện trùng/sự cố liên quan.
2. **Sàng lọc nguy cơ:** người bị thương, khói/tia lửa, điện–nước, kính/vật rơi, trần võng, nước thải lan, nghi khí nguy hiểm. Có tín hiệu thì chuyển trực ngay, không chờ đủ ảnh và không cho LLM hạ mức nguy hiểm.
3. **Khoanh phạm vi:** một thiết bị, cả căn, nhiều căn, trục/khu chung; tra outage, lịch sử và asset đúng building. Thiếu vị trí/owner thì hỏi hoặc chuyển người, không đoán.
4. **Chẩn đoán phân nhánh:** ghi tối thiểu hai giả thuyết cạnh tranh; chỉ kỹ thuật viên/đơn vị có quyền xác nhận sau kiểm tra đúng manual/SOP. Không thử hạng mục điện, kết cấu, PCCC hoặc hệ chung bằng hướng dẫn tự làm.
5. **Quyết định cô lập:** chỉ tạo `utility_isolation.request`/`area_restriction.request` khi có lý do, phạm vi và người phê duyệt. Agent không cắt điện/khóa van, không phát thông báo “đã cắt” khi request còn `PENDING_APPROVAL`.
6. **Work order:** tạo nháp, định chuyên môn/asset, checklist, cửa vào căn, vật tư dự kiến, ảnh trước; kiểm tra assignment và quyền trước thi công.
7. **Thực hiện:** kỹ thuật viên ghi nguyên nhân được chứng minh, việc đã làm, linh kiện, số đo có unit/thiết bị/người đo, ảnh trước/sau; giữ revision và audit.
8. **Khôi phục/kiểm thử:** thử chức năng theo SOP đúng model, kiểm tra rò/tái phát/ảnh hưởng căn khác, xác nhận service scope đã phục hồi nếu từng cô lập.
9. **Chi phí:** chỉ đánh giá sau khi biết phần riêng/chung, bảo hành, nguyên nhân, hợp đồng và báo giá được duyệt; an toàn cấp bách không bị trì hoãn chỉ vì chưa biết người trả.
10. **Nghiệm thu:** `technical.verify_resolution` chỉ khuyến nghị `VERIFIED`/`NEEDS_EVIDENCE`/`HUMAN_REVIEW`; người có thẩm quyền mới xác nhận hoàn tất. Không tự đóng ticket hay xuất hóa đơn.

### 2.1 Yêu cầu cô lập điện/nước [MOCK]

`none → proposed → approved → notified → active → restored` hoặc `cancelled`. Đây là **trạng thái nghiệp vụ mẫu**, không chứng minh thiết bị vật lý đã đổi trạng thái. Trước `approved`: phải có ticket/work order, hazard hoặc lý do bảo trì, asset/van/nhánh điện đúng sơ đồ, phạm vi ảnh hưởng, người phê duyệt, phương án an toàn, phương án thay thế cho tải/nguồn thiết yếu và kế hoạch thông báo. `active` chỉ do người thực hiện xác nhận với log hiện trường; `restored` cần kiểm tra không rò/chập, dịch vụ hoạt động và thông báo khôi phục. Cắt dịch vụ diện rộng đòi BQL và đơn vị cung cấp dịch vụ liên quan; không có thời lượng báo trước hay thứ tự phê duyệt Vinhomes công khai để điền vào đây. Nhánh điện trong `tools.md` hiện chưa có approval kind riêng, nên phải dùng adapter phê duyệt được thiết kế đúng, không dùng sai `customer_repair`.

**Gợi ý trình phê duyệt, không phải lệnh thao tác:**

| Tình huống | Request có thể đề xuất | Điều kiện dừng/chuyển người |
| --- | --- | --- |
| Nước gần thiết bị/dây điện, khói, tia lửa | Hạn chế tiếp cận và đánh giá cô lập điện vùng liên quan | Người trực/kỹ thuật điện quyết định; không chạm vùng ướt/thiết bị; nếu ảnh hưởng hệ chung phải bảo vệ tải thiết yếu. |
| Rò ống cấp chảy liên tục, ngập lan | Đánh giá cô lập van **hẹp nhất có thể** | Chưa biết van/nhánh phục vụ bao nhiêu căn hoặc ảnh hưởng PCCC thì không tự khóa. |
| Thay van/ống hoặc bảo trì định kỳ có gián đoạn | Lập lịch, phê duyệt và thông báo phạm vi dự kiến | Không ghi `active` khi mới thông báo; phải có kế hoạch khôi phục/kiểm thử. |
| Nước thải trào/khí nghi nguy hiểm | Hạn chế khu vực, điều phối đơn vị chuyên trách; xem xét dừng dùng nhánh thoát liên quan | Không coi việc tắt cấp nước là biện pháp duy nhất; không tự kết luận loại khí hoặc an toàn vệ sinh. |
| Đèn lối thoát/PCCC/thang máy ảnh hưởng | Chuyển trực BQL/PCCC/đơn vị bảo trì chuyên trách | Không cắt nguồn hệ an toàn vì một ticket thường; dùng quy trình khẩn cấp đã phê duyệt của tòa. |

### 2.2 Ai có thể chịu phí? [NGUỒN + MOCK]

**[NGUỒN]** Điều 130 Luật Nhà ở phân biệt bảo trì phần riêng và phần chung; Điều 142 mô tả các phần này. Mẫu hợp đồng Vinhomes R03 cho thấy bảo hành có điều kiện và có trường hợp loại trừ; nó không chứng minh nghĩa vụ của bất cứ căn/tòa khác. Phí quản lý vận hành, kinh phí bảo trì chung, tiền điện/nước và yêu cầu sửa riêng là các loại khoản thu khác nhau. **[MOCK]** Hệ thống chỉ trả *ứng viên nguồn chi*, tuyệt đối không trả `resident_must_pay=true` chỉ từ `issue_code`.

| Kết quả kiểm tra hồ sơ | `cost_route_candidate` | Việc bắt buộc trước khi báo phí |
| --- | --- | --- |
| Hạng mục thuộc phạm vi bảo hành, còn hiệu lực, không thấy loại trừ | `WARRANTY_REVIEW` | Đối chiếu biên bản nghiệm thu, hợp đồng căn, manual/phiếu bảo hành, nguyên nhân xác nhận; bên bảo hành quyết định. |
| Hệ chung/trục/thiết bị dùng chung | `COMMON_MAINTENANCE_REVIEW` | Xác minh bản vẽ sở hữu, kế hoạch/quỹ bảo trì hoặc ngân sách vận hành, quyền duyệt; không thu riêng một cư dân theo triệu chứng. |
| Thiết bị/nội thất thuộc sở hữu riêng, hết bảo hành | `PRIVATE_OWNER_REVIEW` | Xác định chủ sở hữu, báo giá vật tư/nhân công, phê duyệt trước khi làm; nếu người báo là người thuê thì đọc hợp đồng thuê/ủy quyền. |
| Có chứng cứ hư hỏng do người dùng/nhà thầu gây ra | `DAMAGE_LIABILITY_REVIEW` | Biên bản, ảnh trước/sau, nhân quả, đối chiếu hợp đồng/nội quy và cơ hội phản hồi; người có quyền xử lý tranh chấp. |
| Nguồn rò đi qua nhiều căn hoặc chưa rõ phần chung/riêng | `UNDETERMINED` | Ưu tiên an toàn, khảo sát hai phía có quyền, chưa chốt người trả hoặc xuất hóa đơn. |
| Chỉ có lời báo, thiếu asset/contract/bảo hành/báo giá | `INSUFFICIENT_DATA` | Yêu cầu dữ liệu; không dùng giá mẫu, phí quản lý hay mức HUD để suy giá. |

**Cổng phê duyệt phí sửa chữa giả lập:** `ownership_confirmed && cause_confirmed && warranty_checked && contract_version_present && quote_approved && payer_authorized && evidence_linked`. Nếu thiếu điều kiện áp dụng: `fee_decision=PENDING_HUMAN_REVIEW`, `amount=null`, `currency=null`, `invoice_id=null`. Khoản khảo sát riêng có thỏa thuận dùng nhánh ADD-04: xét việc khảo sát đã thực hiện và đồng ý khoản phí, không yêu cầu biết trước nguyên nhân hỏng mới được lập báo giá khảo sát. Thông báo cho người báo: “Đang kiểm tra phạm vi sở hữu/bảo hành và sẽ báo phương án chi phí bằng văn bản trước khi thực hiện phần có thu phí.” Không cam kết miễn phí chỉ vì đang trong tòa, cũng không kết luận người thuê phải trả vì họ là người gửi ticket.

### 2.3 Mức xử lý theo thiết kế A2 của repo

Nguồn của bảng là `docs/teams/quang/general.md`, mục 3–4, không phải một SLA công bố của Vinhomes. Khi build adapter, backend áp policy/binding thực; bảng giúp fixture không vô tình hạ mức so với thiết kế. `L1` cần chuyển người trực ngay, `L2` là sự cố lan/ảnh hưởng đáng kể, `L3` là thông thường; chưa có thời lượng phản hồi chính thức để gán vào các mức này.

| Issue code | Mức mặc định trong repo | Dấu nâng L1 theo repo |
| --- | --- | --- |
| TECH.ELEC.BREAKER_TRIP | L2 | Khói, tia lửa, điện giật hoặc nước gần điện. |
| TECH.ELEC.FIXTURE_FAILURE | L3 | Nóng, cháy xém hoặc tóe lửa. |
| TECH.PLUMB.WATER_HEATER | L3 | Nguy cơ điện hoặc rò nước lớn. |
| TECH.PLUMB.WATER_FILTER_LOW_FLOW | L3 | Có rò hoặc chất lượng nước bất thường. |
| TECH.HVAC.CONDENSATION | L2 | Nước gần điện hoặc trần có nguy cơ rơi. |
| TECH.PLUMB.CONCEALED_LEAK | L2 | Ngập nhanh hoặc nước gặp điện. |
| TECH.PLUMB.SHOWER_SEAL | L3 | Thấm lan hoặc rò lớn. |
| TECH.PLUMB.TOILET_LEAK | L3 | Tràn nước thải. |
| TECH.PLUMB.TRAP_ODOR | L3 | Có dấu hiệu khí nguy hiểm. |
| TECH.PLUMB.SUPPLY_DRAIN_JOINT | L3 | Tràn hoặc rò liên tục. |
| TECH.ARCH.DOOR_WINDOW | L3 | Kính hoặc cánh có nguy cơ rơi. |
| TECH.ARCH.CABINET_SAG | L3 | Có nguy cơ rơi. |
| TECH.ARCH.CRACK | L3 | Võng, rơi vật liệu hoặc nứt nhanh. |
| TECH.ARCH.PAINT_MOISTURE | L3 | Nguồn ẩm vẫn tiếp diễn. |
| TECH.ARCH.FLOOR_DAMAGE | L3 | Có nguy cơ vấp ngã. |
| TECH.PLUMB.SEWAGE_BACKFLOW | L2 | Lan rộng, gần điện hoặc ảnh hưởng sức khỏe. |

Đặc biệt, thiết kế repo hiện nâng L1 khi nguồn ẩm còn tiếp diễn hoặc có nguy cơ vấp, dù một bài hướng dẫn bên ngoài có thể phân loại khác. Fixture bám mapping này; nếu Domain Owner muốn đổi thì cập nhật policy có version thay vì lặng lẽ sửa mức trong ca. `unknown` cần câu hỏi bổ sung, không tự thành `false`. Dấu nguy hiểm phát sinh sau lịch hẹn phải tạo assessment mới và chuyển người, không giữ L3 chỉ vì ticket ban đầu là L3.

## 3. Playbook cho 16 loại yêu cầu hiện có [MOCK, có căn cứ tham khảo]

Các bước là **state/checklist cho nhân viên và adapter test**, không phải chỉ dẫn cư dân tự sửa. `isolation` nói khi nào cần **đánh giá/yêu cầu** cô lập, không cho phép agent điều khiển thiết bị. Mọi `fee` là `cost_route_candidate`, không phải quyết định thanh toán. Ngưỡng điện, áp lực, độ ẩm, tải, nồng độ hoặc thời gian nghiệm thu phải lấy từ SOP/model/policy thật, không đặt số mock.

### 01 · `TECH.ELEC.BREAKER_TRIP` — CB nhảy lặp

- **Intake/chẩn đoán:** hỏi CB nhánh hay tổng; số lần và lúc xảy ra; thiết bị vừa dùng; một căn hay nhiều căn; khói, mùi khét, nóng, tia lửa, giật điện, nước gần điện. Phân biệt quá tải, thiết bị hỏng, rò điện và sự cố nguồn chung; không kết luận từ tần suất nhảy.
- **Luồng xử lý:** (1) đánh dấu nguy cơ và chuyển trực nếu có dấu cháy/điện–nước; (2) tra outage, asset tủ/CB, lịch sử lặp và sơ đồ nhánh; (3) kỹ thuật điện có quyền kiểm tra theo SOP hiện hành, ghi nguồn lỗi và số đo với thiết bị/người đo; (4) tạo work order, lưu biên bản thao tác, thử chức năng có giám sát; (5) theo dõi tái diễn trước nghiệm thu.
- **Isolation:** nguy cơ chập/cháy/điện giật hoặc cần kiểm tra sửa nhánh có điện → đề nghị cô lập **nhánh liên quan**, đánh giá tải thiết yếu và số căn ảnh hưởng; không hướng dẫn đóng CB lặp lại, không tuyên bố an toàn từ trạng thái CB đã lên.
- **Phí:** tủ/đường cấp chung → `COMMON_MAINTENANCE_REVIEW`; dây/thiết bị dùng riêng hoặc do cư dân lắp → `PRIVATE_OWNER_REVIEW`/`DAMAGE_LIABILITY_REVIEW` nếu chứng minh được; còn bảo hành → `WARRANTY_REVIEW`.
- **Evidence/đóng:** mã asset, nhánh nguồn, hazard check, số đo/checklist đúng SOP, ảnh trước/sau, kết quả thử, người cho phép cấp điện lại, xác nhận không tái nhảy. **Nguồn:** R01, R03, R05, R06, R15.

#### HB-P01 · Nhánh chẩn đoán và phiếu thực hiện chi tiết [MOCK]

Hỏi theo thứ tự: “Anh/chị đang ở căn nào?”, “Có khói, tia lửa, giật điện hoặc nước gần tủ/ổ không?”, “Mất điện toàn căn hay một nhóm thiết bị?”, “Hiện tượng xuất hiện trong điều kiện nào?”, “Trước đó có lắp/sửa/thay thiết bị gì?”, “Có thể bố trí người mở cửa cho kỹ thuật không?”. Chỉ đề nghị ảnh nếu người báo có thể chụp từ vị trí đang an toàn; không yêu cầu tiến lại gần thiết bị để đọc mã.

| Kết quả nhận được | Giả thuyết cần xét | Bước tiếp theo trong phiếu |
| --- | --- | --- |
| Nhiều căn cùng mất nguồn, có outage đúng scope | Nguồn chung hoặc sự cố đã biết | Liên kết incident chung; kiểm tra ticket riêng có dấu nguy hiểm khác hay không. |
| Chỉ xuất hiện khi một máy riêng hoạt động | Máy riêng hoặc nhánh cấp cho máy | Kỹ thuật điện đối chiếu hồ sơ nhánh và kết quả khảo sát; tương quan thời gian chưa là nguyên nhân cuối. |
| CB nhảy dù cư dân nói “không bật gì” | Dây/thiết bị chạy nền, CB, rò hoặc nguồn | Kiểm kê tải thực tế bằng nhân sự, không dùng câu nói làm bằng chứng không còn tải. |
| Có mùi khét/nóng/nước | Tình huống cần xử lý trực | Chuyển người ngay; phiếu ghi vị trí và người bị ảnh hưởng, chẩn đoán chi tiết làm sau. |

Phiếu `WO-HB01`: (1) `SYN-TECH-E` nhận vị trí và nhật ký xảy ra; (2) kiểm tra quyền vào, sơ đồ nhánh, asset và manual; (3) trình phạm vi cô lập nếu công việc yêu cầu, lưu các tải cần duy trì; (4) người có quyền thực hiện/ghi nhận cô lập; (5) khảo sát và ghi kết luận tách lỗi máy với lỗi mạng cấp; (6) đề xuất sửa theo kết luận, linh kiện và báo giá/claim; (7) thực hiện phương án được duyệt theo manual; (8) thử lại điều kiện sử dụng liên quan, ghi người cho phép khôi phục và bàn giao. Nếu bước 5 chưa phân biệt được hai nguồn lỗi, giữ `diagnosis_pending`, không thay CB chỉ để hết biểu hiện.

Nghiệm thu mock cần biên bản nguyên nhân, checklist điện của nhân sự, kết quả thử chức năng và scope phục hồi. “CB đang lên” hoặc “cư dân hết nhắn” không đủ kết thúc. Nếu tái nhảy sau bàn giao, mở lại work order và đối chiếu tình huống thử trước đó với tải thực tế.

- **Ca `HB-01-A` — lỗi nhánh bàn giao, bảo hành:** người thuê báo nhảy CB bếp, không ghi nhận khói/nước; chủ căn xác nhận lịch; actor điện khảo sát, fixture kết luận lỗi điểm đấu nối của nhánh bàn giao. Quản lý chấp thuận cô lập nhánh bếp, đơn vị bảo hành nhận claim `SYN-CL-01`; actor điện hoàn thành sửa theo phương án, thử chức năng và ghi phục hồi. Dự toán nội bộ `F-DIAG + L-ELEC = 300000`; `mock_resident_share_vnd=0`. Kết thúc câu chuyện: người có quyền nghiệm thu sau kiểm tra, không phát hóa đơn cư dân. Các khoản nội bộ không tự thu của người thuê.
- **Ca `HB-01-B` — thiết bị riêng nhưng chưa xác định lỗi:** lời báo nhắc một lò nướng mới lắp, chưa có model và biên bản nhánh. Cư dân muốn trả tiền ngay để “đổi CB lớn hơn”. Kết quả mong đợi: giữ chẩn đoán mở, không đề xuất tăng định mức theo yêu cầu này, hẹn người chuyên môn và vendor thiết bị; `mock_resident_share_vnd=null`. Nếu sau đó có khói, chuyển trực ngay dù lịch khảo sát chưa đến.

### 02 · `TECH.ELEC.FIXTURE_FAILURE` — ổ cắm, công tắc, đèn không hoạt động

- **Intake/chẩn đoán:** xác định điểm hỏng, trong căn/hành lang/lối thoát, một điểm hay cả dãy; có đổi màu, nóng, lỏng, tiếng nổ, nước, khói không. Phân biệt bóng/fixture, thiết bị cắm, ổ/công tắc, nhánh điện, outage và đèn khẩn cấp.
- **Luồng xử lý:** (1) tách đèn lối thoát hoặc điện nguy hiểm để chuyển trực; (2) kiểm tra asset, lịch sử và outage cùng scope; (3) kỹ thuật viên điện kiểm tra theo manual/SOP, ghi hạng mục hỏng thay vì thay thử; (4) phê duyệt vật tư/việc làm; (5) thử chức năng và ảnh hưởng nhánh liên quan.
- **Isolation:** chỉ đề nghị khi cần can thiệp mạch/ổ/fixture có điện hoặc hazard; lối thoát phải có phương án an toàn tạm và người có quyền phê duyệt, không để hệ an toàn không được giám sát.
- **Phí:** fixture hành lang/hệ chung → `COMMON_MAINTENANCE_REVIEW`; ổ/đèn dùng riêng trong căn → `PRIVATE_OWNER_REVIEW` sau kiểm tra bảo hành; đồ do cư dân tự lắp không tự được coi là tài sản BQL.
- **Evidence/đóng:** ảnh vị trí, asset/model, kết quả kiểm tra nguồn, linh kiện, thử sáng/đóng cắt, xác nhận chức năng chiếu sáng lối thoát nếu liên quan. **Nguồn:** R01, R03, R05, R06, R15.

#### HB-P02 · Phân biệt bóng, bộ đèn, ổ cắm và nhánh nguồn [MOCK]

Thu thập loại điểm điện, phòng/khu vực, biểu hiện hỏng, số điểm cùng hỏng, thiết bị trước đó vẫn dùng được hay không, có nước/nóng/cháy xém, và công việc sửa gần nhất. Mô tả “đèn hỏng” phải tách đèn trong căn, đèn hành lang và đèn thoát hiểm vì người thực hiện và điều kiện duy trì chiếu sáng khác nhau.

| Dấu hiệu mô phỏng | Cách phân nhánh | Không được kết luận sớm |
| --- | --- | --- |
| Một bóng không sáng, các điểm khác bình thường | Bộ đèn/bóng/điều khiển tại chỗ | Không coi chắc chắn chỉ cần thay bóng. |
| Một dãy ổ cùng mất nguồn | Nhánh cấp, bảo vệ hoặc mối nối chung | Không thu tiền thay từng ổ trước khảo sát. |
| Điểm điện nóng/cháy xém | Chuyển trực điện, đề nghị cô lập liên quan | Không yêu cầu người báo cắm thiết bị khác để thử. |
| Đèn chỉ dẫn thoát nạn không sáng | Chuyển BQL kiểm tra hệ an toàn và phương án tạm | Không hẹn như sửa đèn trang trí bình thường. |

Phiếu `WO-HB02`: (1) xác định asset bằng sơ đồ/nhãn an toàn; (2) nhân sự kiểm tra nguồn và bộ phận hỏng theo manual; (3) ghi phạm vi sửa và điểm cô lập; (4) kiểm tra tính tương thích vật tư và nguồn chi; (5) thay/sửa phần được duyệt, lưu bộ phận cũ theo quy trình tòa; (6) thử chức năng tại điểm sửa và kiểm tra các điểm liên quan; (7) ghi khôi phục, ảnh hoàn thiện và phản hồi người dùng. Thiếu đúng model thì `waiting_parts`, không dùng linh kiện khác cấu hình chỉ vì lắp vừa.

Biên bản bàn giao ghi rõ điểm nào đã sửa, điểm nào chưa sửa, trạng thái khu vực và hạn chế còn lại. Tách số lần bật thử trong storyboard khỏi một chứng nhận an toàn điện; kỹ thuật viên phải có checklist phù hợp tài sản.

- **Ca `HB-02-A` — ổ cắm riêng hết bảo hành:** người thuê báo một ổ bàn làm việc mất nguồn; actor điện xác nhận cụm ổ riêng hỏng, nhánh cấp không thuộc phạm vi sửa trong ca. Chủ căn đồng ý `SYN-Q-02@r1`: `L-ELEC + M-SOCKET = 290000`; actor điện được phép cô lập nhánh, thay đúng bộ mẫu, kiểm tra và khôi phục. Quản lý nhận biên bản; `mock_resident_share_vnd=290000`, người thanh toán là `SYN-OWNER-12`.
- **Ca `HB-02-B` — đèn thoát hiểm và hết vật tư:** lễ tân báo đèn tại sảnh tối, kho hết bộ tương thích. Quản lý bố trí phương án tạm và chuyển vendor; ticket giữ `waiting_parts`, không ghi “đã xong” vì đã treo thông báo. Nguồn chi dự kiến hệ chung, `mock_resident_share_vnd=null` cho tới quyết định tài chính; không có khoản thu người báo.

### 03 · `TECH.PLUMB.WATER_HEATER` — máy nước nóng không nóng/rò

- **Intake/chẩn đoán:** hỏi loại điện/gas, model/serial, vị trí nước rò, mức nóng, mã lỗi, bảo hành, một vòi hay tất cả; khói, mùi gas, nước gần điện, bỏng hoặc CB nhảy. Phân biệt nguồn cấp điện/nước, van trộn, rò đường nối, bình/thiết bị và lỗi model.
- **Luồng xử lý:** (1) có điện–nước/gas/bỏng → chuyển trực, không cho mở máy; (2) tra asset/manual hãng, bảo hành và outage; (3) kỹ thuật viên/hãng có quyền xác định điểm rò/lỗi, ghi số đo nếu SOP yêu cầu; (4) duyệt thay thế/sửa và kiểm soát hậu quả nước; (5) thử cấp nước nóng và kiểm rò theo manual trước bàn giao.
- **Isolation:** đề nghị cô lập nguồn điện/nước **của thiết bị/nhánh hẹp nhất** khi rò liên tục hoặc can thiệp; mùi gas đi nhánh ứng cứu chuyên trách, không dùng playbook điện–nước thông thường và không bật/tắt công tắc gần vùng nghi rò.
- **Phí:** thiết bị riêng → `PRIVATE_OWNER_REVIEW` hoặc `WARRANTY_REVIEW`; rò từ ống cấp chung đi qua vị trí máy → `UNDETERMINED` tới khi xác định ranh giới asset. Không áp thời hạn bảo hành công trình cho mọi máy riêng.
- **Evidence/đóng:** nhãn máy, phiếu bảo hành, điểm rò, ảnh/vật tư, phép thử chức năng/rò, người nghiệm thu và cảnh báo còn tồn tại. **Nguồn:** R01, R03, R05, R17, R22.

#### HB-P03 · Hồ sơ máy nóng và phạm vi sửa [MOCK]

Intake cần loại máy điện/gas, model nếu đã có trong hồ sơ, vị trí rò, hiện tượng ở một hay nhiều vòi, khi xuất hiện, mã lỗi người báo nhìn thấy, hồ sơ lắp và đơn vị lắp. Không dùng “không nóng” để mặc định linh kiện gia nhiệt hỏng; một vòi không nóng có thể cần nhánh kiểm tra van trộn/đường cấp của vòi.

| Nhánh | Kiểm tra cần có trong work order | Kết quả để chuyển bước |
| --- | --- | --- |
| Tất cả vòi không nóng | Nguồn cấp, điều khiển, cấu hình và máy theo manual | Actor xác định máy hay nguồn trước duyệt linh kiện. |
| Chỉ một vòi bất thường | Vòi/van trộn, nhánh cấp và đối chiếu các đầu dùng khác | Tách work order vòi khỏi thay máy. |
| Có nước tại vỏ/đầu nối | Điểm xuất phát, phần điện liên quan, loại nước | Xác nhận phạm vi cần dừng thiết bị và người thực hiện. |
| Nước nhỏ từ bộ phận an toàn quá áp của bình gián tiếp | Đúng loại máy, đúng vị trí xả, diễn biến lúc đun, manual của máy | Chưa coi là van hỏng; để kỹ thuật đánh giá. Không bịt hoặc vô hiệu hóa bộ phận an toàn. Tham khảo R24; không áp sang AURES trực tiếp R25. |
| Máy gas hoặc có mùi nghi gas | Chuyển nhánh khí nguy hiểm/chuyên trách | Không tiếp tục quy trình thử điện/nước thông thường. |

Phiếu `WO-HB03`: (1) kiểm tra nguy cơ và lịch sử asset; (2) người chuyên môn xác định loại hỏng; (3) kiểm tra claim bảo hành trước tháo/sửa có thể ảnh hưởng claim; (4) duyệt phương án, vật tư tương thích và phạm vi dừng máy; (5) actor đủ quyền xác nhận máy/nhánh đã ở điều kiện làm việc theo SOP; (6) hãng/kỹ thuật thực hiện; (7) thử kín, chức năng cấp nóng và các cơ cấu liên quan theo manual; (8) bàn giao hạn chế sử dụng nếu chưa hoàn tất. Không ghi một nhiệt độ mock thành ngưỡng an toàn tắm.

- **Ca `HB-03-A` — máy riêng được hãng nhận bảo hành:** toàn bộ vòi không nóng; vendor mẫu nhận model từ asset và kết luận cụm điều khiển thuộc phạm vi bảo hành. Claim `SYN-CL-03` được nhận; actor kỹ thuật ghi dừng máy, thay cụm tương thích và thử chức năng. Dự toán `L-ELEC + M-HEATER = 550000`, cư dân trả `0` trong demo. Ticket chuyển chờ nghiệm thu cho đến có biên bản hãng và xác nhận chức năng, không kết thúc ngay khi linh kiện giao tới.
- **Ca `HB-03-B` — chỉ một vòi lạnh, người thuê muốn thay bình:** hồ sơ có nước nóng ở vòi khác; kỹ thuật chưa xác định van trộn hay nhánh. Không tạo đề nghị thay bình, không báo chắc 550000; giữ số phải thu `null`, khảo sát đúng nhánh. Nếu phát hiện nước gần nguồn điện, chuyển trực và tạm dừng lịch sửa thường.

### 04 · `TECH.PLUMB.WATER_FILTER_LOW_FLOW` — máy lọc nước chảy yếu

- **Intake/chẩn đoán:** chỉ vòi lọc hay cả căn; model, tuổi lõi, lần thay, máy bơm, áp lực nước cấp, rò, màu/mùi/vị lạ. Lưu lượng yếu **không chứng minh** chất lượng nước đạt hoặc không đạt.
- **Luồng xử lý:** (1) nếu nước nghi nhiễm bẩn/rò gần điện thì ngừng dùng nguồn liên quan và chuyển người; (2) so với nước cấp chưa lọc và outage chung; (3) đối chiếu lịch sử lõi/manual đúng model; (4) dịch vụ hãng/kỹ thuật viên kiểm tra và thông báo trước linh kiện cần thay; (5) thử lưu lượng và chất lượng theo quy trình/thiết bị được duyệt, bàn giao.
- **Isolation:** rò tại máy hoặc can thiệp đường cấp → đề nghị khóa nhánh cấp thiết bị; mất nước diện rộng không đổ lỗi lõi lọc trước khi loại trừ outage.
- **Phí:** máy/lõi dùng riêng → `PRIVATE_OWNER_REVIEW`, nhưng kiểm tra bảo hành và hợp đồng dịch vụ trước; nguồn cấp chung → `COMMON_MAINTENANCE_REVIEW` nếu đã xác định ở hệ chung.
- **Evidence/đóng:** model/lõi, hồ sơ thay, tình trạng đầu vào/đầu ra, phép đo có unit/người đo, vật tư, test rò và biên bản bàn giao. **Nguồn:** R01, R03, R07, R10.

#### HB-P04 · Kiểm tra đầu vào, lõi và dịch vụ máy lọc [MOCK]

Hỏi vòi thường trong căn có yếu không; máy lọc bắt đầu yếu từ lúc nào; tên/model; lần thay lõi gần nhất có chứng từ không; có tiếng bơm khác thường, rò, mã lỗi hoặc màu/mùi nước thay đổi không. Nhận thông tin lần thay theo ba trạng thái `resident_recalled`, `service_recorded`, `unknown`, không biến lời nhớ thành lịch bảo trì đã xác minh.

| Phát hiện | Hướng khảo sát | Quyết định mẫu |
| --- | --- | --- |
| Vòi thường và vòi lọc đều yếu | Nguồn cấp căn/tòa trước máy | Tra outage và nguồn, chưa duyệt thay lõi. |
| Vòi thường bình thường, hồ sơ lõi đã đến kỳ theo manual | Cụm lọc/van/bơm theo model | Hãng xác nhận hạng mục và báo giá trước thay. |
| Thay lõi gần đây nhưng vẫn yếu | Tương thích lõi, lắp đặt, nguồn, bơm | Liên kết lần dịch vụ trước để xem trách nhiệm khắc phục. |
| Màu/mùi khác thường | Đánh giá chất lượng nguồn bởi đơn vị phù hợp | Không chứng nhận uống được qua ảnh hoặc lưu lượng. |

Phiếu `WO-HB04`: (1) ghi baseline đầu vào và triệu chứng; (2) đối chiếu model/lõi; (3) dịch vụ kiểm tra thành phần liên quan theo manual; (4) lập danh sách thay và vật tư được cư dân/chủ căn đồng ý; (5) cô lập nhánh thiết bị nếu công việc cần; (6) thực hiện bảo dưỡng/thay, ghi mã và số lượng; (7) chạy thử theo hướng dẫn model, kiểm rò và bàn giao lịch nhắc dựa trên manual. Nếu chưa có manual, không tự đặt chu kỳ thay cố định cho mọi lõi.

- **Ca `HB-04-A` — lõi tiêu hao máy riêng:** người thuê báo máy yếu, nguồn vòi thường ổn định trong khảo sát; actor hãng xác nhận lõi mẫu thuộc diện thay tiêu hao. Chủ căn nhận báo giá `L-WATER + M-FILTER = 360000` và chấp thuận. Dịch vụ thay đúng lõi, ghi kiểm rò/lưu lượng và bàn giao; `mock_resident_share_vnd=360000`. Biên bản không tự thêm kết luận “nước đạt chuẩn uống trực tiếp”.
- **Ca `HB-04-B` — cả tầng yếu nước:** đồng thời có incident nguồn chung đúng phạm vi. Liên kết incident, hoãn quyết định thay lõi, cập nhật khi nguồn phục hồi; sau phục hồi nếu máy vẫn yếu mới khảo sát riêng. Giá `null`; nếu có thông báo nước bất thường thì chuyển xử lý chất lượng nguồn, không áp ca A.

### 05 · `TECH.HVAC.CONDENSATION` — điều hòa đọng/chảy nước

- **Intake/chẩn đoán:** vị trí nước (dàn lạnh, ống ngưng, trần/tường), khi máy chạy hay sau mưa, diện tích lan, căn dưới, model, lần bảo trì. Phân biệt nước ngưng, ống/khay thoát, bẩn lọc, thấm từ ngoài và rò ống cấp khác.
- **Luồng xử lý:** (1) nước gần điện/trần võng → chuyển trực và hạn chế vùng nguy hiểm; (2) tra asset, lịch sử, ảnh hiện trường và ticket căn liền kề; (3) kỹ thuật viên xác định nguồn bằng quan sát/đo đúng SOP; (4) xử lý nguồn trước phần hoàn thiện, không chỉ sơn che vết; (5) thử máy/thoát ngưng và theo dõi vùng ẩm theo thời gian.
- **Isolation:** đề nghị dừng dùng máy liên quan khi đang rò; nếu nước chạm điện hoặc trần nguy hiểm, đánh giá cô lập điện khu vực và hạn chế đi lại. Không tự cắt điều hòa trung tâm/hệ chung từ một lời báo.
- **Phí:** AC riêng → `PRIVATE_OWNER_REVIEW`/`WARRANTY_REVIEW`; ống ngưng/hệ chung hoặc nguồn thấm ngoài → `UNDETERMINED` cho tới khi kiểm tra bản vẽ và ownership.
- **Evidence/đóng:** ảnh trước/sau, điểm nước đầu–cuối, lịch sử, vật tư, test chạy/thoát ngưng, chứng cứ vùng ẩm không lan; số đo chỉ có giá trị khi có phương pháp và người đo. **Nguồn:** R01, R03, R09, R14, R15.

#### HB-P05 · Xác định nguồn nước trước khi sửa điều hòa [MOCK]

Intake ghi phòng, vị trí giọt nước, có chạy máy khi xuất hiện hay không, có mưa, dấu ẩm trước đó, người/căn phía dưới bị ảnh hưởng, lần bảo dưỡng và lịch sử thay ống. Tách `reported_origin=air_conditioner_area` khỏi `confirmed_origin=condensate_drain`: nước cạnh dàn lạnh chưa chứng minh máy lạnh là nguồn.

| Điều kiện quan sát mẫu | Hai khả năng cần phân biệt | Công việc khảo sát |
| --- | --- | --- |
| Chảy khi máy chạy, dừng sau đó | Khay/thoát ngưng hoặc ngưng tụ tại phần khác | Actor HVAC kiểm tra đường đi của nước theo manual. |
| Vẫn thấm khi máy không chạy, liên quan mưa | Rò ngoài máy, mặt ngoài hoặc nước tồn | Phối hợp nước/hoàn thiện, chưa chỉ định vệ sinh máy là giải pháp đủ. |
| Trần mềm/võng hoặc ướt gần đèn | Nước gây nguy cơ vùng trần/điện | Hạn chế khu vực và chuyển trực trước khảo sát thường. |
| Mới sửa thoát ngưng rồi tái diễn | Sửa chưa hết nguyên nhân, lỗi khác hoặc sai phạm vi | Đối chiếu biên bản cũ, xem trách nhiệm tái bảo hành. |

Phiếu `WO-HB05`: (1) xác định machine/đường ngưng và vùng ảnh hưởng; (2) kỹ thuật xác định nguồn rò; (3) ghi dừng riêng máy nào, có cần phối hợp điện/khu vực không; (4) báo phương án vệ sinh/sửa ống hoặc chuyển chuyên môn khác; (5) được duyệt rồi xử lý phần nguồn; (6) thử chạy và kiểm tra tuyến thoát theo manual; (7) theo dõi vùng ẩm và lập work order hoàn thiện nếu cần; (8) khôi phục sử dụng máy khi nhân sự xác nhận, giữ hạn chế vùng trần riêng nếu chưa đạt. Hết chảy nước tại máy không tự chứng minh trần đã khô/ổn định.

- **Ca `HB-05-A` — đường ngưng máy riêng:** actor HVAC xác nhận điểm tắc và phụ kiện thoát hỏng của máy `SYN-AC-12`. Chủ căn duyệt `L-HVAC + M-AC-DRAIN = 330000`; actor dừng máy liên quan, xử lý, thử theo manual mẫu và xác nhận không tái chảy trong lần kiểm tra. Cư dân trả demo `330000`. Vết ố cũ được ghi là hạng mục hoàn thiện chưa đặt làm, không bị giấu khỏi biên bản.
- **Ca `HB-05-B` — vừa thu phí vệ sinh nhưng vẫn rò:** nước tiếp tục xuất hiện sau lần xử lý dù máy tắt; mở lại liên kết ca cũ, lấy ảnh đối chiếu và chuyển khảo sát nguồn nước khác. Chưa báo thêm phí vệ sinh, `mock_resident_share_vnd=null` cho phần phát sinh. Nếu trần võng, chuyển trực/hạn chế vùng, không để việc tranh luận phí làm chậm xử lý nguy cơ.

### 06 · `TECH.PLUMB.CONCEALED_LEAK` — rò âm tường/thấm trần

- **Intake/chẩn đoán:** vị trí/vệt ố theo thời gian, tốc độ lan, có căn trên/bên cạnh, sau dùng vòi/tắm/mưa/AC, mùi nước sạch/nước thải, nước gần điện, trần bong/võng. Giữ các khả năng: ống nhánh, trục chung, chống thấm, nước ngưng, mặt ngoài.
- **Luồng xử lý:** (1) xử lý nguy cơ điện/trần trước; (2) đối chiếu sơ đồ ống, các ticket liên quan, outage và ảnh hai phía; (3) tạo `apartment_entry.request` nếu phải khảo sát căn khác; (4) kỹ thuật viên chuyên trách chứng minh nguồn bằng phương pháp được duyệt, ghi vị trí/độ ẩm; (5) xử lý nguồn, thử kín và theo dõi tái ẩm trước sửa hoàn thiện.
- **Isolation:** nước lan nhanh hoặc phải can thiệp ống → đề nghị khóa van ở phạm vi **đã xác định**, thông báo căn chịu ảnh hưởng; chưa biết van/ống là chung hay riêng thì không khóa theo suy đoán của agent.
- **Phí:** mặc định `UNDETERMINED`; chỉ chuyển sang phần chung/riêng/bảo hành/trách nhiệm gây hư hỏng khi có chứng cứ nguồn rò và bản vẽ ownership. Không quy lỗi căn trên chỉ vì vị trí thấm.
- **Evidence/đóng:** chuỗi ảnh có nguồn, bản đồ vị trí, phép đo có provenance, biên bản vào căn, ảnh trước/sau và kiểm tra tái phát; lưu cả căn bị ảnh hưởng. **Nguồn:** R01, R03, R07, R14, R15.

#### HB-P06 · Điều phối hai căn và sửa nguồn trước hoàn thiện [MOCK]

Hỏi vệt ẩm ở đâu, khi nào tăng, đang nhỏ giọt hay chỉ đổi màu, có đèn/ổ gần đó, căn trên có thay đổi sử dụng/sửa chữa được biết đến không, ai có thể cho vào kiểm tra. Chỉ ghi thông tin căn khác khi có quyền; người báo không phải tự vào hoặc kiểm tra hộp kỹ thuật của hàng xóm.

| Dữ kiện | Chưa đủ để kết luận | Kiểm tra cần giao |
| --- | --- | --- |
| Vệt ố nằm dưới WC căn trên | Chưa chứng minh chủ căn trên làm hỏng | Đối chiếu bản vẽ, ống nhánh, trục chung, khu ướt và diễn biến. |
| Căn trên nói không dùng nước vẫn thấm | Chưa loại trừ ống cấp liên tục, nước tồn, nguồn khác | Khảo sát nguồn theo chuyên môn, giữ nhiều giả thuyết. |
| Nhiều căn cùng trục báo ẩm | Gợi ý nguồn chung, chưa là ownership xác nhận | Liên kết incident, quản lý kỹ thuật xác định phạm vi. |
| Nước gặp điện hoặc trần có nguy cơ rơi | Không chờ có quyền vào đủ cả hai căn mới chuyển trực | Điều phối người có thẩm quyền và biện pháp hạn chế ảnh hưởng. |

Phiếu `WO-HB06-PIPE`: (1) nhận ảnh/vị trí ở căn bị ảnh hưởng; (2) xác minh hồ sơ tuyến ống và hai quyền vào độc lập; (3) actor nước khảo sát nguồn, ghi vùng cần mở kiểm tra và phương án bảo vệ tài sản; (4) quản lý duyệt phạm vi cô lập hẹp nhất đã xác định; (5) nếu phải mở lớp hoàn thiện, ghi diện tích/phạm vi và sự đồng ý phù hợp trước thực hiện; (6) sửa điểm nguồn theo vật liệu, manual/biện pháp; (7) thử kín/khả năng cấp và kiểm tra vùng ảnh hưởng; (8) phục hồi nguồn và lập hồ sơ hoàn thiện `WO-HB06-FINISH` riêng. Khi nguồn chưa rõ, bước 6 chưa được thay bằng “sơn lại trần”.

Tiêu chí bàn giao chia hai: phần ống có kết quả thử và người ghi phục hồi; phần hoàn thiện có đánh giá điều kiện thi công, vật liệu và kiểm tra sau sửa. Xử lý yêu cầu bồi thường đồ đạc là hồ sơ khác có chứng cứ, không tự cộng vào hóa đơn sửa nguồn.

- **Ca `HB-06-A` — trục chung được xác định:** căn `SYN-U-12` báo ố trần; hai căn đồng ý lịch; actor xác định rò tại asset chung `SYN-RISER-02` theo bản vẽ fixture. Quản lý duyệt gián đoạn các căn đã được xác định, actor thực hiện và sửa. Dự toán sửa nguồn `L-WATER + M-PIPE = 340000`; nguồn chi common được duyệt, cư dân trả `0`. Phần sơn có work order và dự toán riêng `500000`, đang chờ điều kiện thi công; ticket tổng chưa hoàn tất.
- **Ca `HB-06-B` — căn trên không cho vào, chưa rõ nguồn:** lưu quyền vào ở trạng thái chờ và nhật ký liên hệ; quản lý đánh giá ảnh hưởng và phương án tiếp cận theo quyền thực tế. Không ghi căn trên “có lỗi” vì từ chối lịch, không tự mở cửa. Dự toán có thể còn trống; phí phải thu `null`, thông báo mốc cập nhật tiếp theo và việc bảo vệ căn bị ảnh hưởng.

### 07 · `TECH.PLUMB.SHOWER_SEAL` — vách tắm/khu ướt rò

- **Intake/chẩn đoán:** nước lọt qua mép vách, ray/cửa, mạch gạch, chân tường hay sàn bên ngoài; có kính lỏng/nứt, bản lề kẹt, rò chỉ khi tắm hay cả khi không dùng. Phân biệt ron/gioăng, mạch ốp lát, chống thấm nền và ống âm.
- **Luồng xử lý:** (1) kính có nguy cơ rơi → hạn chế dùng và chuyển người; (2) chụp vị trí trước khi làm khô, xác định model vách/cấu tạo; (3) kỹ thuật viên có quyền kiểm tra đường nước theo phương pháp không làm lan hư hại; (4) phê duyệt vật liệu đúng hệ, xử lý điểm hở và nguồn thấm nếu có; (5) thử kín có kiểm soát, kiểm tra căn dưới/vùng liền kề.
- **Isolation:** thường không cần ngừng nước cả tòa; chỉ đề nghị khóa nhánh nếu có rò ống cấp hoặc công việc phải can thiệp ống. Vùng kính lỏng cần hạn chế tiếp cận, không nhất thiết cắt nước.
- **Phí:** vách tự lắp/thiết bị riêng → `PRIVATE_OWNER_REVIEW`; lỗi chống thấm/kết cấu trong bảo hành → `WARRANTY_REVIEW`; nguồn từ hệ chung → `COMMON_MAINTENANCE_REVIEW` sau xác minh.
- **Evidence/đóng:** bản đồ điểm rò, ảnh trong–ngoài, vật liệu/model, test sau xử lý và kết quả theo dõi thấm. **Nguồn:** R01, R03, R13, R15.

#### HB-P07 · Tách gioăng vách, đường ron và chống thấm [MOCK]

Intake: nước ra từ mép cửa, chân kính, mạch sàn hay phía ngoài tường; chỉ khi tắm hay cả khi không dùng; có chảy xuống tầng dưới; kính/cánh có rung/lỏng; vách bàn giao hay lắp sau; đã tự bơm keo lần nào. Ghi người lắp và lịch sử xử lý để vendor xác định phương án, không dùng việc từng tự sửa làm kết luận tự động mất mọi quyền bảo hành.

| Nhánh khảo sát | Công việc cần xác minh | Hướng công việc mẫu |
| --- | --- | --- |
| Nước qua khe cánh/gioăng | Tình trạng gioăng, vị trí cánh, thoát nước thiết kế | Chỉnh/phục hồi phụ kiện và kín nước theo model. |
| Vách khô nhưng mép sàn/thấp tầng dưới ẩm | Ron, chống thấm hoặc đường ống khác | Tách khảo sát nước/hoàn thiện; không chỉ bơm keo quanh kính. |
| Kính/cánh mất ổn định | Phụ kiện giữ kính và nguy cơ rơi | Hạn chế khu vực, đơn vị kính chuyên trách. |
| Mới làm keo chưa đủ điều kiện sử dụng theo vật liệu | Hồ sơ thi công, hướng dẫn vật liệu | Lập lịch kiểm tra theo thông số sản phẩm, không tự đặt số giờ chung. |

Phiếu `WO-HB07`: (1) xác định cấu tạo/model và nguồn nước; (2) ghi ảnh đường nước và tình trạng phụ kiện; (3) duyệt sửa gioăng/keo hoặc chuyển khảo sát chống thấm; (4) thông báo khu tắm cần tạm ngưng sử dụng và phần khác còn dùng được; (5) kỹ thuật tháo phần vật liệu hỏng, chuẩn bị bề mặt và thi công theo hệ vật liệu đã duyệt; (6) chờ điều kiện đóng rắn/hoàn thiện theo hướng dẫn vật liệu; (7) thử kín có kiểm soát và kiểm tra ngoài vách/căn bị ảnh hưởng; (8) bàn giao điều kiện dùng lại. Không mặc định cắt nước cả căn nếu chỉ cần tạm ngừng dùng khu tắm.

- **Ca `HB-07-A` — gioăng bàn giao được bảo hành:** `SYN-CL-07` được actor bảo hành nhận; `WO-HB07` ghi lỗi gioăng và không có lỗi giữ kính trong khảo sát giả lập. Giá nội bộ `L-WATER + M-SHOWER = 320000`, cư dân trả `0`. Sau thi công giữ khu tắm hạn chế cho tới khi đáp ứng hướng dẫn vật liệu và thử kín; mới bơm keo xong chưa nghiệm thu.
- **Ca `HB-07-B` — còn thấm căn dưới sau sửa vách:** mở lại case, giữ giả thuyết chống thấm/ống; phát sinh khảo sát cần quote revision và quyền vào căn dưới. Phí phần mới `null`, không thu lặp 320000 tự động; bảo lưu hồ sơ lần sửa vách để đánh giá phạm vi khắc phục của nhà thầu.

### 08 · `TECH.PLUMB.TOILET_LEAK` — bồn cầu chảy/rò

- **Intake/chẩn đoán:** tách nước chảy **trong lòng bồn** khi không xả, nước rò **ra sàn**, cấp két yếu và nước thải trào; hỏi model, lần thay phụ kiện, mùi, diện tích nước, căn dưới bị ảnh hưởng. Phân biệt van cấp/bộ xả, dây cấp, chân bồn/gioăng, ống thoát và trào ngược hệ chung.
- **Luồng xử lý:** (1) nước thải trào hoặc gần điện → nhánh khẩn; (2) xác định nước sạch hay nước thải và vị trí xuất hiện; (3) tra model, manual, tài sản và bảo hành; (4) nhân sự có quyền kiểm tra/lập đề xuất phụ kiện đúng model; (5) thử nạp–xả–ngừng chảy và kiểm tra khô vùng sàn/căn dưới.
- **Isolation:** rò nước cấp liên tục → đề nghị khóa van thiết bị/nhánh nhỏ nhất; trào nước thải → hạn chế sử dụng nhánh liên quan và điều phối thoát nước, không chỉ khóa cấp nước để tuyên bố đã an toàn.
- **Phí:** phụ kiện thiết bị riêng hết bảo hành → `PRIVATE_OWNER_REVIEW`; ống thoát chung/bể phốt → `COMMON_MAINTENANCE_REVIEW`; nguồn chưa rõ → `UNDETERMINED`.
- **Evidence/đóng:** ảnh chỗ rò, model và vật tư, phép thử nhiều chu kỳ theo SOP, sàn khô, không còn chảy liên tục, phản hồi cư dân. **Nguồn:** R01, R03, R07, R11, R15.

#### HB-P08 · Phân biệt cấp két, xả liên tục và rò chân bồn [MOCK]

Intake dùng câu dễ trả lời: “Nước chảy vào lòng bồn liên tục hay chảy ra sàn?”, “Có trào chất thải không?”, “Két có nạp nước được không?”, “Lỗi xảy ra khi xả hay cả lúc không dùng?”, “Nhà có một hay nhiều WC?”, “Model và lần sửa gần nhất đã có trong hồ sơ chưa?”. Nếu nước thải trào, đổi nhánh xử lý sang backflow thay vì giữ mã rò két thông thường.

| Triệu chứng | Thành phần cần phân biệt | Nội dung kết quả khảo sát |
| --- | --- | --- |
| Nước vào lòng bồn liên tục | Cấp két, bộ xả, phần kín nước | Ghi đúng bộ phận hỏng theo model, không thay cả cụm theo phỏng đoán. |
| Nước sạch ở dây/van đầu vào | Đầu nối hoặc cấp cục bộ | Ghi vị trí rò và khả năng cô lập riêng thiết bị. |
| Rò chân bồn khi xả | Liên kết thoát, phần kín hoặc tắc liên quan | Ghi loại nước và kiểm tra nhánh thoát. |
| Dâng/trào nước thải | Tắc nhánh hoặc hệ thoát chung | Chuyển HB-P16, đánh giá vùng cần hạn chế. |

Phiếu `WO-HB08`: (1) xác định loại nước và điểm phát sinh; (2) tra model, phụ kiện, warranty; (3) thông báo WC nào tạm dừng, không khóa nguồn cả căn nếu không cần; (4) actor cô lập nhánh cấp khi phải tháo phần cấp/két; (5) thay/căn chỉnh bộ phận đúng manual được duyệt; (6) thử chu trình nạp–giữ–xả theo model, quan sát các điểm nối và sàn; (7) xác nhận WC dùng lại được và không còn tiếng/nước chảy bất thường; (8) lưu vật tư và ảnh trước/sau.

- **Ca `HB-08-A` — bộ kín nước két hết bảo hành:** fixture actor xác định bộ kín hỏng tại `SYN-WC-12`; chủ căn duyệt `L-WATER + M-TOILET = 310000`. Kỹ thuật cô lập riêng bồn cầu, thay phần đúng model, thử và trả lại sử dụng; cư dân trả demo `310000`. Không áp thêm phí khảo sát khi quote không có dòng đó.
- **Ca `HB-08-B` — người báo gọi “rò” nhưng thực tế trào nước thải:** câu trả lời tiếp theo cho biết nước bẩn dâng từ lòng bồn và thoát sàn; assessment mới liên kết HB-P16 và chuyển trực. Quote thay phụ kiện két ở bản nháp bị hủy với lý do chẩn đoán đổi; số phải thu `null`. Lưu cả lời báo đầu và lý do đổi mã, không sửa mất lịch sử.

### 09 · `TECH.PLUMB.TRAP_ODOR` — mùi cống/bẫy nước

- **Intake/chẩn đoán:** vị trí mùi, điều kiện phát sinh, một căn hay nhiều căn, sau mưa/xả nước, có tiếng rít hoặc nghi mùi gas/khí khác không. Phân biệt bẫy nước khô/hở, ống thông hơi/thoát, bồn cầu hở tráp, nguồn rác hoặc nguồn ngoài hệ thoát.
- **Luồng xử lý:** (1) nghi gas, khó thở hoặc mùi lan nhiều căn → chuyển trực/đơn vị chuyên trách, không thử bằng nguồn lửa; (2) đối chiếu vị trí thoát và ticket cùng tầng/trục; (3) kỹ thuật viên kiểm tra bẫy/tráp/ống theo sơ đồ; (4) xác nhận nguyên nhân trước khi thay vật tư hoặc vệ sinh; (5) theo dõi mùi ở các thời điểm sử dụng khác nhau.
- **Isolation:** không mặc định cắt cấp nước; khi phải can thiệp hệ thoát chung thì đề nghị hạn chế sử dụng nhánh/khu vực và thông báo các căn liên quan. Nghi khí nguy hiểm không xử lý như lỗi bẫy nước thường.
- **Phí:** bẫy/tráp thiết bị riêng → `PRIVATE_OWNER_REVIEW` sau bảo hành; ống thông hơi/trục chung → `COMMON_MAINTENANCE_REVIEW`; chưa xác định nguồn mùi → `UNDETERMINED`.
- **Evidence/đóng:** sơ đồ điểm mùi, quan sát các thiết bị, nguyên nhân xác nhận, ảnh/biên bản và phản hồi sau theo dõi. **Nguồn:** R01, R03, R07, R11, R15.

#### HB-P09 · Khảo sát mùi theo vị trí và điều kiện phát sinh [MOCK]

Hỏi mùi xuất hiện ở thoát sàn, chậu, bồn cầu, hộp kỹ thuật hay cả phòng; khi xả nước, bật thông gió, sau vắng nhà hoặc trong điều kiện nào khác; có nước trào, vật liệu ẩm, công việc sửa gần đây; người trong phòng có dấu hiệu bất thường hay nghi gas không. Mô tả mùi là thông tin chủ quan; không gán tên khí hoặc mức an toàn từ lời mô tả.

| Nhánh mẫu | Dữ liệu cần bổ sung | Cách giao việc |
| --- | --- | --- |
| Mùi ở điểm ít sử dụng lâu ngày | Cấu tạo bẫy nước, trạng thái quan sát, lịch sử sử dụng | Kỹ thuật kiểm tra bẫy và điểm kín theo cấu hình. |
| Mùi xuất hiện khi nhiều thiết bị xả | Tuyến thoát, thông khí, liên quan căn khác | Mở khảo sát hệ thống, không chỉ xử lý một miệng thoát. |
| Mùi sau sửa chậu/bồn cầu | Phụ kiện đã thay và liên kết kín | Kiểm tra phạm vi lần sửa và warranty dịch vụ. |
| Nghi gas hoặc người bị ảnh hưởng | Vị trí, tình trạng người, kênh liên hệ an toàn | Chuyển đơn vị khẩn/chuyên trách, không chạy thử bằng thiết bị điện. |

Phiếu `WO-HB09`: (1) xác định vị trí và loại phản ánh; (2) kiểm tra cấu hình bẫy nước, mối nối và tuyến thông khí trong quyền tiếp cận; (3) nếu bẫy mất chức năng, xác định nguyên nhân thay vì chỉ che mùi; (4) duyệt vệ sinh/phục hồi/thay đúng phụ kiện; (5) nhân sự xử lý và thử thoát theo SOP; (6) kiểm tra lại tại điều kiện từng phát sinh; (7) hẹn phản hồi theo thời điểm mùi hay xuất hiện; (8) mở lại nếu còn mùi và chuyển khảo sát phạm vi lớn hơn. Dùng chất tạo mùi không phải tiêu chí nghiệm thu.

- **Ca `HB-09-A` — bẫy chậu riêng không kín:** actor nước xác nhận phụ kiện bẫy của chậu riêng hỏng, nhánh thoát không trào trong khảo sát; chủ căn duyệt `L-WATER + M-TRAP = 270000`. Sau thay đúng cấu hình, thử thoát và kiểm tra điểm kín; lời phản hồi sau sử dụng được ghi cùng kết quả kỹ thuật. Cư dân trả demo `270000`; biên bản chỉ nêu phạm vi đã kiểm, không chứng nhận toàn bộ không khí căn hộ.
- **Ca `HB-09-B` — khử mùi xong nhưng mùi tái xuất hiện:** cư dân gửi phản hồi, hai căn cùng trục có hiện tượng. Liên kết incident chung, khảo sát thông khí/tuyến thoát; không tự thêm hóa chất hoặc tính lại phí vệ sinh. Kết quả giữ `awaiting_diagnosis`, số phải thu `null`; nghi khí nguy hiểm thì chuyển trực ngay.

### 10 · `TECH.PLUMB.SUPPLY_DRAIN_JOINT` — nước yếu, thoát chậm, rò đầu nối

- **Intake/chẩn đoán:** **ba nhánh phải tách**: (A) nước cấp yếu — một vòi/cả căn/nhiều căn; (B) thoát chậm — một chậu/phòng/cả trục; (C) rò đầu nối — điểm nối nào, nước sạch/thải, liên tục/chỉ khi sử dụng. Hỏi điều kiện phát sinh và ảnh, áp lực/lưu lượng chỉ khi được đo đúng cách.
- **Luồng xử lý:** (1) sàng lọc tràn/điện–nước; (2) tra lịch cấp nước, bơm/bồn, outage và ticket lân cận; (3) kỹ thuật viên xác định nhánh A/B/C, asset và ranh giới ống chung/riêng; (4) lập work order/vật tư khác nhau cho từng nhánh; (5) thử lại cấp, thoát và rò sau xử lý; nếu còn chậm/ướt thì chưa nghiệm thu.
- **Isolation:** nhánh C rò liên tục hoặc cần tháo đường cấp → đề nghị khóa van hẹp nhất; nhánh B có trào → hạn chế dùng đường thoát; nhánh A yếu không tự đồng nghĩa cần cắt nước.
- **Phí:** bơm/bồn/trục chung → `COMMON_MAINTENANCE_REVIEW`; van/dây/chậu riêng → `PRIVATE_OWNER_REVIEW`; lỗi liên quan nhiều nhánh → `UNDETERMINED` tới khi khoanh nguồn.
- **Evidence/đóng:** ảnh vị trí, phạm vi căn, phép đo có provenance, vật tư, thử nước cấp/thoát/rò và lịch theo dõi. **Nguồn:** R01, R03, R07, R15.

#### HB-P10 · Ba nhánh khác nhau trong cùng nhóm mã [MOCK]

Không dùng một checklist duy nhất cho mã này: đặt `subtype=low_supply`, `slow_drain` hoặc `joint_leak`; nếu có nhiều biểu hiện, lưu nhiều observation và xác định quan hệ sau khảo sát. Intake hỏi vị trí, nước sạch/thải, chỉ một đầu dùng hay cả căn, lúc mở vòi hay lúc xả, mức lan, hồ sơ sửa gần nhất và outage hiện hành.

| Subtype | Khảo sát cần giao | Phạm vi gián đoạn mẫu |
| --- | --- | --- |
| `low_supply` | Đầu dùng, nguồn cấp căn, van/nhánh, hệ chung | Chưa cần cắt dịch vụ nếu chỉ đang kiểm tra hồ sơ; khi can thiệp do kỹ thuật đề xuất. |
| `slow_drain` | Điểm thu, đoạn thoát cục bộ và tình trạng nhánh chung | Tạm ngừng dùng thiết bị/nhánh có ảnh hưởng; không mặc định khóa nước cả tầng. |
| `joint_leak` | Đầu nối cấp hay thoát, cấu hình, bộ phận thực sự hỏng | Cấp rò liên tục có thể cần cô lập nhánh; thoát rò cần dừng dùng đầu xả liên quan. |

Phiếu `WO-HB10`: (1) xác định subtype; (2) chụp vị trí/ghi lượng lan theo quan sát thực; (3) kỹ thuật phân biệt điểm đầu dùng với nguồn/nhánh; (4) duyệt sửa tại đầu nối hoặc chuyển work order hệ chung; (5) trước tháo/sửa ghi scope cô lập và bảo vệ vùng xung quanh; (6) thay bộ nối đúng vật liệu/cấu hình hoặc xử lý đoạn thoát được duyệt; (7) thử cấp/thoát tương ứng, kiểm tất cả điểm nối đã can thiệp; (8) bàn giao chức năng và phần còn hạn chế. Nếu ống mục hỏng vượt điểm nối, tạo phát sinh thay phạm vi, không giấu trong ghi chú “siết lại”.

- **Ca `HB-10-A` — đầu nối chậu riêng rò:** actor nước xác nhận cần thay bộ nối, chủ căn duyệt `L-WATER + M-JOINT = 250000`; cô lập nhánh chậu, sửa và thử cả cấp/thoát tại vùng can thiệp. Sau actor quản lý nghiệm thu, cư dân trả demo `250000`.
- **Ca `HB-10-B` — báo nước yếu nhưng chỉ thiếu khi có outage:** xác nhận trùng lịch gián đoạn đã được phê duyệt đúng tòa. Cập nhật incident và trạng thái xử lý có điều kiện; không lập quote thay van. Khi nước phục hồi mà một vòi vẫn yếu, mở khảo sát subtype mới, giữ liên kết sự kiện chung; số phải thu `null` cho đến có chẩn đoán và báo giá riêng.

### 11 · `TECH.ARCH.DOOR_WINDOW` — cửa/cửa sổ lỏng, hở, kẹt

- **Intake/chẩn đoán:** cửa chính/cửa phòng/cửa sổ mặt ngoài; cánh, kính, bản lề, khóa, tay co, ray hay gioăng; khó đóng/khóa, kẹt người, rơi vật xuống dưới, ảnh hưởng lối thoát/chống cháy. Phân biệt sai chỉnh, hỏng phụ kiện, biến dạng khung, thấm mép và lỗi kết cấu neo.
- **Luồng xử lý:** (1) kính/cánh có nguy cơ rơi hoặc lối thoát bị chặn → hạn chế vùng và chuyển trực; (2) tra bản vẽ mặt ngoài, asset, loại cửa và quyền can thiệp; (3) kỹ thuật viên/nhà thầu chuyên môn khảo sát điểm neo, cấu kiện, test đóng mở an toàn; (4) duyệt vật tư/biện pháp phù hợp; (5) nghiệm thu khóa/đóng/mở, độ ổn định và khu vực bên dưới.
- **Isolation:** không cắt điện/nước trừ khi hệ điều khiển cửa tự động liên quan; có thể đề nghị `area_restriction.request` cho vùng kính/cánh rơi. Cửa chống cháy/lối thoát phải dùng quy trình chuyên trách.
- **Phí:** cửa mặt ngoài/chung, cửa căn riêng, phụ kiện tự thay có ranh giới khác nhau → `UNDETERMINED` đến khi đối chiếu hồ sơ sở hữu/bảo hành; không tính phí theo vị trí “bên trong căn” một cách máy móc.
- **Evidence/đóng:** ảnh toàn cảnh–điểm neo, model phụ kiện, kết quả thử chức năng, xác nhận không còn nguy cơ rơi/lối thoát bị cản. **Nguồn:** R01, R03, R08, R15.

#### HB-P11 · Phân loại cửa cơ khí, mặt ngoài và lối thoát [MOCK]

Intake hỏi cửa phòng/cửa chính/cửa sổ/cửa chung; kẹt ở vị trí nào; có người bị kẹt, kính nứt, cánh có thể rơi, lối thoát bị cản; lỗi xuất hiện sau va chạm/mưa gió/sửa khóa; phụ kiện bàn giao hay thay sau. Cửa từ/cửa tự động cần kiểm tra cả quyền truy cập và phần điện, không xử lý mở khóa như sửa bản lề thông thường.

| Quan sát | Nhánh công việc | Điều cần giữ trong hồ sơ |
| --- | --- | --- |
| Cửa phòng cọ nền, thân/khung ổn định | Bản lề/căn chỉnh/phụ kiện | Ghi khe/cạ ở đâu và kết quả đóng mở. |
| Cửa chính không khóa được | Phụ kiện và an ninh căn hộ | Xác minh chủ thể có quyền và phương án bảo vệ tạm. |
| Kính/cánh ngoài lỏng | Nguy cơ rơi, khu vực dưới bị ảnh hưởng | Hạn chế khu vực, vendor có chuyên môn, quyền can thiệp mặt ngoài. |
| Cửa chống cháy/thoát nạn kẹt | Hệ an toàn và vận hành tòa | Handoff BQL/PCCC; không chèn mở cửa như sửa tạm mặc định. |

Phiếu `WO-HB11`: (1) phân loại cửa và quyền tiếp cận; (2) actor kiểm tra khung, neo, cánh, bản lề, khóa/gioăng trong phạm vi; (3) xác định cần hạn chế vùng hay thay đổi lối đi tạm; (4) duyệt vật tư/phương án, bao gồm bảo vệ tài sản; (5) thợ sửa/thay/căn chỉnh đúng model; (6) thử đóng, mở, khóa, khả năng giữ cánh và các chức năng được yêu cầu; (7) quản lý xác nhận bỏ hạn chế khu vực; (8) bàn giao chìa/quyền truy cập qua quy trình an ninh nếu liên quan. Không ghi mã mở khóa/mật khẩu vào corpus dùng chung.

- **Ca `HB-11-A` — cửa phòng bàn giao còn bảo hành:** actor hoàn thiện xác định phụ kiện bản lề hỏng thuộc claim `SYN-CL-11`; dự toán `L-JOINERY + M-DOOR = 340000`. Nhà thầu sửa và thử chức năng, chủ căn xác nhận nhận bàn giao; cư dân trả demo `0`. Không cần cắt điện/nước trong phạm vi ca này.
- **Ca `HB-11-B` — kính cửa sổ lỏng và chưa rõ ownership:** agent tạo yêu cầu hạn chế vùng, chuyển quản lý/vendor; căn dưới và khu vực công cộng có thể liên quan nên scope được người trực xác định. Chưa có hồ sơ phân định mặt ngoài, số phải thu `null`; không cho người báo tự tháo kính hoặc khẳng định họ phải trả vì kính nằm sát căn.

### 12 · `TECH.ARCH.CABINET_SAG` — tủ bếp xệ/cánh lệch

- **Intake/chẩn đoán:** cánh tủ hay cả thân tủ nghiêng; vị trí neo, tải đang chứa, ẩm ở lưng/chân tủ, phụ kiện/model, tủ bàn giao hay cư dân lắp sau. Phân biệt bản lề/đế, vít neo, ván hỏng, tường neo yếu và thấm nền.
- **Luồng xử lý:** (1) nguy cơ rơi → không sử dụng và chuyển người; (2) xác định asset/ownership, ảnh tải và điểm neo trước can thiệp; (3) thợ có quyền đánh giá tủ/bản lề/tường và ẩm; (4) đề xuất sửa phụ kiện hoặc xử lý nguyên nhân nền/tường, không chỉ căn chỉnh cánh nếu thân tủ xệ; (5) thử đóng mở và ổn định khi tải trong giới hạn manual.
- **Isolation:** thường không cắt dịch vụ; nếu tủ che ổ điện/ống nước đang rò thì tách thành ticket hazard và cân nhắc cô lập nhánh liên quan. Hạn chế dùng vùng dưới tủ có nguy cơ rơi.
- **Phí:** tủ cư dân tự lắp → `PRIVATE_OWNER_REVIEW`; tủ bàn giao còn bảo hành → `WARRANTY_REVIEW`; tường/kết cấu/nguồn thấm chung → `UNDETERMINED` tới khi xác minh.
- **Evidence/đóng:** ảnh trước/sau, nhãn phụ kiện, điểm neo, vật tư, thử đóng mở, xác nhận không xệ tiếp. **Nguồn:** R01, R03, R12, R15.

#### HB-P12 · Tách cánh xệ khỏi thân tủ/neo mất ổn định [MOCK]

Intake xác định tủ trên hay dưới, một cánh hay cả thân bị xệ, có khe hở với tường/tiếng bất thường, vùng ẩm, tải đang chứa và lịch sử lắp/sửa. Khi có nguy cơ rơi, hướng dẫn giữ khoảng cách và chuyển người; không yêu cầu cư dân trèo lên tháo đồ/đỡ tủ để chụp ảnh.

| Dấu hiệu | Nhánh khảo sát | Kết luận chưa được phép suy |
| --- | --- | --- |
| Một cánh lệch, thân tủ được thợ xác nhận ổn định | Bản lề/đế/cánh | Không mặc định cả hệ neo tốt chỉ từ ảnh một cánh. |
| Toàn thân tách tường/nghiêng | Neo, nền tường, thân tủ và tải | Không giải quyết chỉ bằng chỉnh bản lề. |
| Ván phồng/ẩm | Nguồn ẩm và chất lượng vật liệu | Không thay ván rồi bỏ qua nguồn rò phía sau. |
| Tủ mới được cư dân lắp | Hồ sơ thợ lắp và warranty riêng | Không mặc định BQL có trách nhiệm bảo hành. |

Phiếu `WO-HB12`: (1) đánh giá vùng cần hạn chế; (2) lấy hồ sơ lắp, model phụ kiện và trạng thái tải từ nguồn có quyền; (3) thợ kiểm tra cánh/thân/neo/tường theo chuyên môn; (4) nếu ẩm thì mở liên kết xử lý nước trước; (5) duyệt phụ kiện hoặc phương án tái lắp, ghi phạm vi tháo dỡ; (6) thực hiện và kiểm tra theo cấu hình được duyệt; (7) thử đóng mở, độ ổn định và khả năng sử dụng theo manual; (8) bàn giao giới hạn sử dụng do nhà sản xuất/đơn vị chuyên môn xác nhận. Không đặt tải mock thành thử chịu lực thực tế.

- **Ca `HB-12-A` — hai bản lề tủ riêng hỏng:** actor thợ xác nhận chỉ phạm vi hai bản lề, thân/neo không cần sửa trong ca; chủ căn duyệt `L-JOINERY + 2 × M-CABINET = 440000`. Sau thay phụ kiện đúng loại và nghiệm thu chức năng, cư dân trả demo `440000`; không cần cắt dịch vụ.
- **Ca `HB-12-B` — thân tủ xệ do vùng tường đang ẩm:** giới hạn vùng dùng, liên kết ticket rò nước; chưa duyệt phương án siết lại hoặc báo giá hai bản lề. `waiting_dependency` là nhãn storyboard, nguyên nhân và phí còn mở. Sau khi nguồn ẩm được xử lý, thợ đánh giá lại trước lập quote mới; người báo nhận rõ hai đầu việc và người điều phối.

### 13 · `TECH.ARCH.CRACK` — nứt tường/trần

- **Intake/chẩn đoán:** vị trí, hướng/dài/rộng theo ảnh có mốc đo, xuất hiện/tăng theo thời gian, trần võng/rơi vật liệu, cửa kẹt, nước thấm, rung hoặc sửa chữa gần đây. Phân biệt nứt lớp sơn/trát, nứt vách ngăn, kết cấu, co ngót/ẩm — **không chẩn đoán kết cấu từ ảnh**.
- **Luồng xử lý:** (1) dấu rơi/võng/nứt tăng nhanh → hạn chế khu vực và gọi kỹ sư có thẩm quyền; (2) đối chiếu bản vẽ kết cấu, lịch sử và ảnh theo thời gian; (3) khảo sát/đo có phương pháp, quyết định cần kiểm định hay theo dõi; (4) chỉ xử lý bề mặt sau khi nguyên nhân và phương án kết cấu được duyệt; (5) nghiệm thu với kết quả theo dõi/kiểm định phù hợp.
- **Isolation:** không mặc định cắt điện/nước; nếu nứt ảnh hưởng ống, dây hoặc lối thoát thì đề nghị cô lập/hạn chế theo rủi ro cụ thể. Không cho phép sửa che vết khi chưa đánh giá nguy cơ.
- **Phí:** kết cấu/hạng mục bảo hành/phần chung/hoàn thiện riêng → `UNDETERMINED` tới khi có kết luận kỹ thuật, hợp đồng và ranh giới sở hữu. Không gán lỗi cư dân vì đã treo đồ nếu chưa chứng minh nhân quả.
- **Evidence/đóng:** ảnh có liên kết sự kiện, sơ đồ vị trí, phép đo/kết quả kỹ sư, work order, biên bản xử lý và theo dõi tái nứt. **Nguồn:** R01, R03, R15.

#### HB-P13 · Hồ sơ theo dõi nứt và quyết định chuyển kỹ sư [MOCK]

Hỏi vị trí chính xác, xuất hiện lần đầu khi nào, ảnh cũ nếu có, thay đổi nhanh hay không, có rơi vật liệu/võng/kẹt cửa/rung, có công trình sửa gần đây, người/vật bên dưới và lối đi bị ảnh hưởng. Một ảnh không đủ xác nhận nứt chỉ thẩm mỹ; không dùng chiều rộng do cư dân ước lượng để tự phân loại an toàn kết cấu.

| Diễn biến | Work order phù hợp | Điều kiện tiếp tục |
| --- | --- | --- |
| Nứt lớp hoàn thiện đã được chuyên môn xác nhận | Sửa lớp hoàn thiện | Có kết luận/phạm vi được phép sửa và kế hoạch theo dõi. |
| Nứt mới, tăng hoặc kèm võng/rơi vật liệu | Đánh giá chuyên trách và hạn chế vùng | Chờ người đủ chuyên môn quyết định phương án, không chỉ trám phủ. |
| Tái nứt tại vị trí vừa sửa | Mở lại, so sánh ảnh và biện pháp cũ | Đánh giá lại nguyên nhân trước sửa bề mặt lần nữa. |
| Có nghi liên quan cải tạo căn | Khảo sát hồ sơ cải tạo và kết cấu | Nhân quả do chuyên gia xác nhận, không gán trách nhiệm từ thời điểm trùng nhau. |

Phiếu `WO-HB13`: (1) quản lý kỹ thuật xem tín hiệu nguy hiểm và phạm vi ảnh hưởng; (2) yêu cầu kỹ sư/vendor phù hợp nếu cần; (3) lập bản đồ vị trí, ảnh có mốc, hồ sơ đo/quan sát do người đủ chuyên môn ghi; (4) chuyên gia quyết định khảo sát bổ sung, theo dõi hay sửa; (5) duyệt biện pháp và nguồn chi theo kết luận; (6) nhà thầu xử lý đúng lớp/phạm vi cho phép; (7) nghiệm thu bề mặt và điều kiện theo dõi theo kết luận; (8) kiểm tra lại theo lịch được phê duyệt. Trạng thái “sơn đẹp” không thay một kết luận kỹ thuật.

- **Ca `HB-13-A` — lớp trát/hoàn thiện được xác định:** actor `SYN-ENG-S` trong storyboard kết luận phạm vi sửa chỉ lớp hoàn thiện và lập biên bản `SYN-RPT-13`; bên bảo hành đồng ý. Dự toán `L-FINISH + M-CRACK = 460000`, cư dân trả `0`. Nhà thầu sửa, quản lý nghiệm thu và mở công việc theo dõi giả lập. Điều kiện theo dõi an toàn phải lấy từ phương án chuyên môn được duyệt.
- **Ca `HB-13-B` — vết mới kèm võng và tiếng bất thường:** chuyển trực/hạn chế khu vực, đề nghị khảo sát chuyên trách `S-STRUCT = 1500000` chỉ là dự toán demo chưa duyệt. `mock_resident_share_vnd=null`, kết luận `pending_specialist`; không xuất hướng dẫn tự trám và không trả “vết nứt nhỏ nên an toàn”.

### 14 · `TECH.ARCH.PAINT_MOISTURE` — sơn bong, vết ố, ẩm mốc

- **Intake/chẩn đoán:** vị trí/diện tích, mùi, sau mưa/tắm/điều hòa, lớp sơn mới hay cũ, có nước đang chảy, người nhạy cảm sức khỏe, trần mềm/rơi. Phân biệt nguồn ống, chống thấm, ngưng tụ, rò AC, mặt ngoài và thông gió.
- **Luồng xử lý:** (1) nước gần điện/trần mất ổn định → chuyển trực; (2) ghi ảnh theo thời gian và vùng ẩm, đối chiếu ticket rò; (3) xác định **nguồn ẩm trước** bằng kỹ thuật viên, không sơn phủ để coi là xong; (4) xử lý nguồn và vật liệu hỏng theo SOP/đánh giá sức khỏe; (5) xác minh khô/không lan trước phục hồi hoàn thiện.
- **Isolation:** chỉ đề nghị khóa nước/dừng thiết bị nếu đã khoanh nhánh rò hoặc nguy cơ điện–nước; nấm mốc nhìn thấy không tự đồng nghĩa phải cắt dịch vụ. Hạn chế sử dụng vùng trần/vật liệu có thể rơi.
- **Phí:** theo **nguồn ẩm đã chứng minh**, không theo bề mặt sơn: ống chung → `COMMON_MAINTENANCE_REVIEW`; máy riêng → `PRIVATE_OWNER_REVIEW`; lỗi hoàn thiện còn bảo hành → `WARRANTY_REVIEW`.
- **Evidence/đóng:** ảnh vùng ẩm, nguồn rò xác nhận, phép đo có phương pháp, ảnh sau làm khô/sửa, theo dõi tái phát. **Nguồn:** R01, R03, R09, R14, R15.

#### HB-P14 · Work order nguồn ẩm và work order hoàn thiện [MOCK]

Intake ghi phòng/vị trí, dấu nước đang hoạt động hay vết cũ, thay đổi theo mưa/tắm/chạy máy lạnh, có ticket nguồn rò liên quan, loại bề mặt, mùi và vật liệu rơi/điện gần đó. Thông tin người có nhu cầu sức khỏe đặc biệt chỉ lưu tối thiểu phục vụ điều phối có quyền, không suy chẩn đoán hoặc đưa vào passage dùng chung.

| Tình huống | Việc trước khi sơn sửa | Kết quả phải lưu |
| --- | --- | --- |
| Nguồn rò chưa xử lý | Work order nguồn và bảo vệ vùng ảnh hưởng | ID nguồn, người phụ trách, trạng thái phụ thuộc. |
| Nguồn đã sửa nhưng bề mặt chưa đáp ứng điều kiện thi công | Đánh giá làm khô/vật liệu bởi thợ theo hệ sản phẩm | Kết quả kiểm tra và lý do chưa thi công. |
| Nguồn đã ổn, đủ điều kiện hoàn thiện | Duyệt phạm vi/màu/vật liệu và phương án | Xác nhận phạm vi cư dân nhận, quote revision. |
| Xuất hiện lại sau sơn | Mở lại nguồn và hoàn thiện | Giữ ảnh cũ, điều kiện thời tiết/sử dụng, biên bản lần trước. |

Phiếu `WO-HB14`: (1) xác minh source ticket thay vì chỉ nhận câu “đã sửa rồi”; (2) thợ đánh giá bề mặt và điều kiện làm việc; (3) ghi vùng cần bóc/sửa, bảo vệ đồ đạc và phương án vệ sinh; (4) tài chính phân biệt chi sửa nguồn với chi khôi phục phần riêng; (5) duyệt vật liệu/màu và quote; (6) thi công theo hệ vật liệu sau điều kiện đầu vào đạt; (7) kiểm tra độ phủ/hoàn thiện, vùng tiếp giáp và dấu ẩm tái phát; (8) cư dân nhận phạm vi bàn giao, quản lý quyết định hoàn tất hoặc giữ theo dõi. Không đặt số đo độ ẩm giả vào biên bản.

- **Ca `HB-14-A` — khôi phục sơn sau sự cố nguồn chung:** liên kết HB-06-A; actor kiểm tra mô phỏng xác nhận đủ điều kiện hoàn thiện và nguồn chi phục hồi đã được tài chính duyệt riêng. Báo giá `L-FINISH + M-PAINT = 500000`, cư dân trả `0`. Thợ hoàn thiện, người dùng xác nhận phạm vi/màu, quản lý đóng work order con; ticket tổng chỉ hoàn tất khi cả sửa nguồn và hoàn thiện được nghiệm thu.
- **Ca `HB-14-B` — chủ căn chỉ muốn sơn che để bàn giao thuê:** nguồn ẩm chưa rõ và chưa có kết quả khảo sát. Hệ thống giữ `waiting_dependency`, giải thích cần giải quyết nguồn và điều kiện thi công; không đổi `source_fixed=true` theo mong muốn. Giá hoàn thiện là dự toán chưa được chấp thuận, số phải thu `null`; không dùng ảnh mới sơn làm bằng chứng nguồn hết rò.

### 15 · `TECH.ARCH.FLOOR_DAMAGE` — sàn trầy, phồng, bong

- **Intake/chẩn đoán:** vật liệu sàn, vị trí và diện tích, mép sắc/cao độ gây vấp, ẩm/nước bên dưới, mới lắp/đã sử dụng lâu, có sửa/đổ nước gần đây. Phân biệt trầy thẩm mỹ, hỏng liên kết, phồng do ẩm, nền lún và lỗi thi công.
- **Luồng xử lý:** (1) nguy cơ vấp/cạnh sắc → hạn chế vùng và chuyển người; (2) xác định vật liệu, hồ sơ bàn giao, vùng ẩm và ảnh trước; (3) nhân sự có quyền kiểm tra nguyên nhân nền/nguồn nước trước thay tấm; (4) duyệt vật tư đúng loại và phạm vi sửa; (5) nghiệm thu mặt phẳng, liên kết, khô và an toàn đi lại.
- **Isolation:** không cần cắt tiện ích nếu chỉ trầy/bong khô; có nước đang rò bên dưới hoặc điện sàn liên quan → tách nhánh cô lập tương ứng. Khu vực đi lại nguy hiểm có thể cần hạn chế tạm.
- **Phí:** hao mòn/va đập phần riêng → `PRIVATE_OWNER_REVIEW` sau chứng minh; lỗi thi công/bảo hành → `WARRANTY_REVIEW`; nền/kết cấu hoặc nguồn ẩm chung → `UNDETERMINED` đến khi kiểm định.
- **Evidence/đóng:** ảnh có mốc đo, vật liệu/model, độ ẩm nếu đo, nguồn hư hỏng, ảnh sau và kiểm tra sử dụng. **Nguồn:** R01, R03, R14, R15.

#### HB-P15 · Xác định vật liệu, phạm vi và nguyên nhân dưới sàn [MOCK]

Intake hỏi vật liệu sàn, số tấm/vùng bị ảnh hưởng, mép cao/sắc gây vấp, có nước/ẩm, tiếng rỗng/lún, lịch cải tạo và ảnh trước sự cố. Phân biệt người báo nói “phồng” với kết luận vật liệu; nếu chưa biết loại sàn, lưu `material=unknown` để tránh tạo quote sai vật tư.

| Nhánh | Công việc xác minh | Phương án mô phỏng |
| --- | --- | --- |
| Trầy bề mặt, nền được xác nhận ổn định | Mã vật liệu và yêu cầu thẩm mỹ | Sửa/thay cục bộ khi vật liệu phù hợp. |
| Phồng có ẩm | Nguồn nước, tình trạng nền và tấm | Xử lý nguồn/đánh giá điều kiện nền trước lát lại. |
| Bung/bong hoặc chênh gây vấp | Vùng đi lại, liên kết, phạm vi vật liệu hỏng | Hạn chế vùng tạm và thợ khảo sát. |
| Có dấu lún/biến dạng nền | Chuyên môn nền/kết cấu | Chuyển chuyên trách, không chốt số tấm thay từ ảnh. |

Phiếu `WO-HB15`: (1) đánh dấu vùng ảnh hưởng trong sơ đồ căn; (2) kiểm tra nguồn ẩm và loại vật liệu; (3) đối chiếu mẫu/mã tồn kho, lập phạm vi tháo thay; (4) trình quote gồm số lượng và phần cần di chuyển bảo vệ; (5) thợ kiểm tra nền khi được phép mở; (6) nếu khác chẩn đoán ban đầu thì tạm dừng phần phát sinh và trình lại; (7) sửa/thay theo hệ vật liệu, kiểm tra liên kết/mặt bằng và điều kiện dùng lại; (8) bàn giao và ghi phần thẩm mỹ khác màu nếu tồn tại. Không tự coi cư dân chấp nhận lệch màu chỉ vì đã đồng ý lịch.

- **Ca `HB-15-A` — ba tấm sàn riêng được chấp thuận thay:** actor thợ kết luận nền khô/ổn định trong ca mẫu và hỏng cục bộ ba tấm; chủ căn chọn vật liệu cùng mã. Quote `L-FINISH + 3 × M-FLOOR = 1260000` được chấp thuận; thi công, kiểm tra và bàn giao. Cư dân trả demo `1260000`, không tăng số lượng nếu chưa có quote mới.
- **Ca `HB-15-B` — tháo tấm đầu phát hiện ẩm lan:** thợ ghi phát sinh và liên kết khảo sát nước, giữ an toàn vùng đang mở; số lượng/phương án cũ chưa đủ. Tạo `SYN-Q-15@r2` đang nháp; chưa có tổng mới được chấp thuận, số phải thu phần phát sinh `null`. Ticket không được đánh “completed” vì đã tháo xong lớp sàn hỏng.

### 16 · `TECH.PLUMB.SEWAGE_BACKFLOW` — nước thải trào ngược

- **Intake/chẩn đoán:** nước trào ở miệng thoát/bồn cầu/khu chung, số căn/tầng, mức lan, thời điểm mưa/xả, mùi, điện gần nước, người tiếp xúc, nghi tắc trục/hố ga/bể. Phân biệt tắc cục bộ nhánh căn, tắc trục, dội từ cống ngoài và ngập mưa.
- **Luồng xử lý:** (1) chuyển trực ngay khi nước thải lan, điện gần nước hoặc ảnh hưởng sức khỏe; hạn chế tiếp xúc; (2) xác định phạm vi và thông báo căn liên quan không dùng nhánh thoát theo hướng dẫn BQL; (3) tra bản vẽ trục, lịch sử, thời tiết và ticket khác; (4) đơn vị chuyên trách xác nhận điểm nghẽn/nguồn rồi xử lý theo SOP vệ sinh–an toàn; (5) thử thoát, làm sạch và kiểm tra căn/khu vực bị ảnh hưởng trước khôi phục.
- **Isolation:** có thể cần hạn chế dùng **nhánh thoát liên quan**, đánh giá khóa cấp nước ở phạm vi thích hợp nếu cần bảo trì; điện vùng ngập phải do người đủ quyền đánh giá. Không tự tuyên bố hết nguy cơ chỉ vì nước rút.
- **Phí:** nhánh riêng/trục chung, dị vật do người dùng, hư hỏng do mưa/cống ngoài là các khả năng **chưa xác nhận** → `UNDETERMINED` cho tới khi có biên bản nguồn và ownership; ưu tiên ứng cứu trước tranh chấp phí.
- **Evidence/đóng:** phạm vi ảnh hưởng, ảnh/video có quyền, biên bản đơn vị chuyên trách, nguyên nhân, thử thoát, làm sạch/khử nhiễm theo SOP và xác nhận không tái trào. **Nguồn:** R01, R03, R07, R15, R16.

#### HB-P16 · Kiểm soát phạm vi trào và điều phối vệ sinh [MOCK]

Intake ưu tiên vị trí, loại nước quan sát, phạm vi lan, người bị ảnh hưởng, điện/tải thiết yếu gần vùng ngập, điểm trào và số căn liên quan. Hỏi thêm thời điểm mưa/xả và các lần trước sau khi đã chuyển trực. Không yêu cầu cư dân lội vào vùng ngập, mở hố ga hoặc tự pha hóa chất để xử lý.

| Phạm vi mẫu | Giả thuyết | Việc kỹ thuật cần xác minh |
| --- | --- | --- |
| Một thiết bị, các điểm khác bình thường | Nghẽn nhánh cục bộ | Vị trí và quan hệ nhánh theo bản vẽ. |
| Nhiều điểm/căn cùng trục | Trục thoát, hố thu hoặc nguồn chung | Xác định phạm vi, nhà thầu và thiết bị cần xử lý. |
| Tương quan mưa/ngập ngoài tòa | Hệ thoát ngoài hoặc mưa xâm nhập | Phối hợp đơn vị hạ tầng; không quy lỗi người dùng. |
| Đã thông nhưng tái trào | Chưa hết nguồn/điểm nghẽn khác | Mở lại khảo sát toàn tuyến liên quan, giữ biên bản cũ. |

Phiếu `WO-HB16`: (1) chuyển trực và hạn chế vùng ảnh hưởng; (2) người có quyền đánh giá nguồn điện/vùng ngập và nhu cầu cô lập; (3) BQL thông báo các đầu dùng cần tạm ngưng sau khi xác định nhánh; (4) vendor khảo sát, ghi điểm nghẽn/nguồn và phương án; (5) duyệt phạm vi xử lý, thu gom và vệ sinh; (6) nhân sự chuyên trách xử lý theo SOP; (7) thử thoát ở phạm vi liên quan và kiểm tra có tái trào; (8) hoàn thành vệ sinh, ghi vùng chưa được bàn giao; (9) quản lý cho phép dùng lại và quyết định closeout. Làm nước rút, làm sạch và phục hồi sử dụng là ba kết quả riêng.

Hồ sơ cần biên bản nguồn, phạm vi người/căn bị ảnh hưởng, vật tư/dịch vụ, việc vệ sinh đã thực hiện và actor chấp thuận khôi phục. Nếu cần điều tra dị vật, ghi bằng chứng và người lưu giữ; việc tìm thấy một vật không tự xác định được căn/người đã đưa vào hệ thống.

- **Ca `HB-16-A` — nghẽn tuyến chung được xác nhận:** ba căn cùng trục báo trào; actor vendor xác nhận điểm nghẽn ở tài sản chung `SYN-DRAIN-R2`. Quản lý duyệt ngừng dùng nhánh liên quan và xử lý; quote demo `S-DRAIN + L-CLEAN = 750000`, tài chính duyệt common funding, cư dân trả `0`. Sau xử lý có kết quả thử thoát, biên bản vệ sinh và xác nhận dùng lại; quản lý mới nghiệm thu ticket tổng.
- **Ca `HB-16-B` — hết trào nhưng thiếu biên bản vệ sinh:** actor chỉ gửi “đã thông” và ảnh một miệng thoát; hệ thống trả yêu cầu bổ sung phạm vi vệ sinh/các căn bị ảnh hưởng, giữ `awaiting_review`. Không tự gán toàn bộ chi phí cho căn đầu tiên báo hoặc đổi kết quả sang VERIFIED; `mock_resident_share_vnd=null` khi chưa có quyết định nguồn chi.

## 4. Yêu cầu liên quan nên có trong sản phẩm nhưng chưa có mã A2 [MOCK]

Đây là **đề xuất taxonomy**, không tự thêm mã vào `general.md` hoặc ghi thành khả năng tool hiện hữu. Các ca sau dùng để thử router/handoff; mỗi ca cần Domain Owner quyết định thuộc A2, BQL, an ninh, PCCC, nhà cung cấp hay domain khác.

| Mã tạm | Yêu cầu/điều cần hỏi | Luồng mock, cô lập và phí |
| --- | --- | --- |
| `EXT.WATER.BUILDING_OUTAGE` | Nhiều căn mất nước/nước yếu: phạm vi tầng–trục, bơm/bồn/nguồn cấp, nước có màu/mùi lạ? | Tra thông báo/outage và BMS được quyền đọc, chuyển BQL/nước sạch. Có kế hoạch sửa bơm/ống thì đề nghị gián đoạn theo phạm vi được duyệt, thông báo–khôi phục; không để agent cam kết giờ có nước. Chi phí là ngân sách hệ chung/nhà cung cấp **cần xét**, không thu riêng một người báo. Tham khảo R07 và ca Huế ở `../VN_PUBLIC_CASES.jsonl`. |
| `EXT.POWER.COMMON_OUTAGE` | Mất điện nhiều căn/khu chung, đèn lối thoát hay tải thiết yếu? Có khói/nước? | Chuyển trực điện, tra outage đúng building, bảo vệ lối thoát và thiết bị thiết yếu. Không tự ra lệnh cắt toàn tòa; điện lực/BQL quyết định. Funding `UNDETERMINED` giữa lưới ngoài/hệ chung/nhánh riêng. Tham khảo R05, R06, R15. |
| `EXT.LIFT.STOP_TRAPPED` | Thang dừng, cửa kẹt, có người bên trong, số cabin/tầng, liên lạc được không? | Nếu có người kẹt → trực/BQL và đơn vị cứu hộ/bảo trì thang theo quy trình khẩn cấp; agent không hướng dẫn cạy cửa hay cứu hộ. Có thể ngừng dùng cabin, đặt biển và cập nhật trạng thái; khôi phục chỉ sau kiểm tra chuyên trách. Chi phí theo hợp đồng bảo trì/hư hỏng xác nhận, không quy cho người báo. Tham khảo R18, R21; không phải SOP Vinhomes. |
| `EXT.FIRE.ALARM_OR_EGRESS` | Báo cháy, đầu báo lỗi, cửa chống cháy/đèn thoát hiểm hỏng, người có nguy cơ? | Tuân thủ chỉ dẫn khẩn cấp chính thức của tòa/cơ quan có thẩm quyền; khi có cháy không hướng dẫn dùng thang máy thoát nạn. Không tắt hệ PCCC/cửa chống cháy chỉ để loại báo động; cần BQL/PCCC/vendor duyệt, log test/khôi phục. Không gán phí cho cư dân trước điều tra. Tham khảo R15, R20. |
| `EXT.GAS.ODOR` | Mùi gas/khí nghi nguy hiểm, vị trí, người bị ảnh hưởng, nguồn cấp riêng/chung? | Chuyển khẩn cho đơn vị có thẩm quyền; tránh mọi bước thử bằng lửa/công tắc, không coi là `TRAP_ODOR` mặc định. Cô lập nguồn chỉ bởi người đủ quyền theo sơ đồ/SOP. Chi phí không quyết định trước khi biết nguồn và hợp đồng. Tham khảo R22. |
| `EXT.ACCESS.DOOR_INTERCOM` | Khóa từ, intercom, thẻ cư dân hoặc cửa tự động hỏng; có kẹt người/lối thoát? | Tách vấn đề an ninh/quyền truy cập khỏi lỗi cửa cơ khí; kiểm tra scope/ACL, vendor và log sự kiện. Không tự mở khóa cấp quyền; cửa thoát hiểm lỗi phải chuyển trực. Phí theo thiết bị chung/riêng và hợp đồng, chưa có bảng giá. |
| `EXT.MAINT.PLANNED_INTERRUPTION` | Bảo trì định kỳ bơm, điện, nước, HVAC có dừng dịch vụ? | Tạo kế hoạch, đánh giá tải/căn ảnh hưởng, lịch phê duyệt, thông báo trước theo policy tòa, phương án thay thế và rollback, xác nhận dừng/khôi phục bằng nhân sự. Không biến `proposed` thành `active` và không lấy thời lượng từ ví dụ nhà cung cấp ngoài. Chi phí theo kế hoạch vận hành/bảo trì được duyệt, không báo thu riêng. Tham khảo R18 cho phân loại bảo trì; lịch, tần suất và dự toán phải lấy từ kế hoạch tòa đã duyệt. |
| `EXT.WATER.QUALITY` | Nước có màu, mùi hoặc cặn khác thường ở một/nhiều điểm? | Điều phối đơn vị cấp nước/BQL, kiểm dữ liệu và kết quả theo phạm vi; không kết luận chất lượng từ ảnh hoặc một sensor cũ. Chi tiết EXT-08, nguồn R26. |
| `EXT.HVAC.NO_COOL_NOISE` | Điều hòa kém lạnh, không chạy, báo lỗi hoặc tiếng ồn? | Tra model/manual và chuyển kỹ thuật, chưa quy thành chảy nước hoặc thiếu môi chất. Phí theo khảo sát/warranty. Chi tiết EXT-09, nguồn R27. |
| `EXT.ENVELOPE.RAIN_INGRESS` | Nước mưa vào ban công/cửa ngoài/nghi thấm mặt đứng? | Khảo sát nguồn và quyền can thiệp mặt ngoài, duyệt vendor/phạm vi; tách sửa nguồn với hoàn thiện. Chi tiết EXT-10. |

## 5. Bốn ca end-to-end giả lập để build và kiểm thử [MOCK]

**Mọi ID và diễn biến trong mục này là fixture, không phải lịch sử Vinhomes.** Không có file ảnh thật, số đo thật, bảng giá thật hoặc hành động cô lập vật lý. Dùng `tenant_id=TEST-ONLY`, building `SYN-B-01`, `fixture_only=true`; adapter phải tạo UUID/ACL, file giả qua storage test và review riêng trước khi gọi tool. Không nạp các ca này vào RAG trả lời cư dân.

### M01 — Rò âm tường lan sang căn dưới, nguồn/chủ chi chưa rõ

1. ticket `HB-SYN-001` từ căn `SYN-U-12`: vệt ố trần bếp đang tăng; ảnh do cư dân gửi ở trạng thái `unscanned`; `reported_fact=water_stain`, `confirmed_cause=null`.
2. assessment hỏi thêm có nước nhỏ giọt/nước gần đèn, kích thước vệt, căn trên có dùng nước không; nếu câu trả lời là “nước chạm đèn” → `escalate_now`, không chờ ảnh đủ đẹp. Tách hai giả thuyết: ống nhánh căn trên và trục cấp chung.
3. `asset.read` được phép tra ống/trục theo building; nếu chỉ ra hai asset có thể liên quan, không chọn asset đầu tiên. `apartment_entry.request` cho căn trên ở `PENDING_APPROVAL`; chưa được vào căn.
4. nếu kỹ thuật viên xác nhận nước đang lan, tạo `utility_isolation.request` cho **van được xác định trên sơ đồ**, `status=proposed`, lưu danh sách căn bị ảnh hưởng và người duyệt. Không ghi nước đã cắt. BQL có thể quyết định khẩn cấp theo SOP thật ngoài mock.
5. sau khi có quyền vào và khảo sát, kỹ thuật viên ghi ảnh/số đo kèm người đo. Nếu nguồn vẫn chưa rõ, `diagnosis_status=unconfirmed`, `payer_candidate=UNDETERMINED`, `amount=null`; vẫn tiếp tục ngăn hại theo quyết định của người trực.
6. Chỉ khi có biên bản nguồn rò, sửa nguồn, thử kín, theo dõi trần căn dưới, khôi phục dịch vụ và phê duyệt tài chính mới ra quyết định chi phí. **Test âm:** agent kết luận căn trên phải trả từ vị trí vệt ố → fail.

### M02 — CB nhảy và thiết bị cư dân mới lắp

1. `HB-SYN-002`: cư dân báo CB nhảy hai lần khi dùng máy riêng; chưa rõ mùi khét/nước. `hazard_unknown=true`, nên agent hỏi trước, không hướng dẫn bật lại nhiều lần.
2. Tra asset nhánh căn và outage building; lịch sử không có bản ghi không chứng minh hệ thống an toàn. Ghi `resident_installed_device=reported`, chưa có hóa đơn, model hoặc xác nhận lỗi.
3. Nếu có khói/nóng → chuyển trực ngay, đề nghị đánh giá cô lập điện vùng liên quan; `physical_action_done=false` trong request. Nếu không có hazard, lập work order kỹ thuật điện và yêu cầu manual/model.
4. Kỹ thuật viên xác nhận **bằng chứng** lỗi thiết bị riêng hay nhánh bàn giao; nếu do thiết bị riêng, `PRIVATE_OWNER_REVIEW`, nhưng vẫn kiểm tra hợp đồng thuê/bảo hành/ủy quyền và báo giá. Nếu lỗi nhánh bàn giao còn bảo hành, `WARRANTY_REVIEW`.
5. Kết quả cuối chỉ có thể `HUMAN_REVIEW`/`NEEDS_EVIDENCE` cho tới khi có checklist an toàn, phép thử hợp lệ, review phí. **Test âm:** route `RESIDENT_CHARGED` chỉ vì cư dân mới lắp máy → fail.

### M03 — Bảo trì ống cấp chung theo lịch, cần tạm ngừng nước

1. `HB-SYN-003`: work order kế hoạch `draft`; asset `SYN-RISER-02`, phạm vi dự kiến tầng 8–12 nhưng chưa xác minh van/căn. `outage.status=proposed`, không hiển thị như outage đang diễn ra.
2. Người quản lý kỹ thuật xác định van, phương án nước dự phòng, danh sách căn, vendor và rollback; kế hoạch được phê duyệt rồi mới có thể thông báo theo policy của tòa. `notified` chưa đồng nghĩa đã khóa van.
3. Nhân sự hiện trường được phân công xác nhận bắt đầu/cắt thực tế; log `actor`, `affected_scope`, `approval_id`; đổi `active` bởi backend có quyền, không bởi LLM.
4. Sau sửa, kiểm tra rò/chất lượng cấp/áp lực theo SOP đúng asset, ghi số đo có nguồn; BQL xác nhận `restored` và thông báo khôi phục. Nếu thử thất bại, giữ `active` hoặc phương án thay thế; không gửi “đã có nước” theo giờ dự kiến.
5. `cost_route_candidate=COMMON_MAINTENANCE_REVIEW`, không chia hóa đơn cho từng căn. **Test âm:** biến `proposed` thành `active`, báo ETA chắc chắn hoặc thu riêng người gửi yêu cầu → fail.

### M04 — Yêu cầu bảo hành vách tắm nhưng hợp đồng/model chưa đủ

1. `HB-SYN-004`: căn báo nước qua chân vách khi tắm; ảnh có, không có model, hồ sơ nghiệm thu/bàn giao, hợp đồng hoặc thông tin ai lắp vách. `warranty_status=unknown`, `fee_decision=PENDING_HUMAN_REVIEW`.
2. Phân biệt nước qua gioăng/cửa, đường ron–chống thấm và rò ống âm; một ảnh sàn ướt không đủ quyết định. Nếu kính lỏng hoặc nước chảy xuống căn dưới → hạn chế vùng/chuyển trực.
3. BQL tra hợp đồng căn thực tế, hồ sơ bàn giao, warranty claim và tài liệu vật liệu; kỹ thuật viên kiểm tra nguồn. Mẫu hợp đồng R03 chỉ là **ví dụ** và không được gán tự động cho căn này.
4. Nếu vách là hạng mục bàn giao còn bảo hành và không thuộc loại trừ theo hợp đồng → `WARRANTY_REVIEW`; nếu do cư dân lắp sau → `PRIVATE_OWNER_REVIEW`; nếu nguồn từ chống thấm/ống chung → `UNDETERMINED` cho tới khi xác minh.
5. Phương án và chi phí phải được duyệt trước phần có thu phí; sau sửa cần thử kín, kiểm tra vùng lân cận, ảnh và nghiệm thu. **Test âm:** “miễn phí mọi vách tắm mà không xét điều kiện bảo hành” hoặc “cư dân luôn trả vì lỗi trong phòng tắm” → fail.

## 6. Schema tối thiểu để hiện thực hóa [MOCK]

Không dùng các trường sau như DB seed trực tiếp; đây là bản trình bày rút gọn để BA/backend đối chiếu với schema thật trong `server/src/technical-tools`. Các trường ngày giờ đã được lược khỏi tài liệu theo yêu cầu, không phải đề xuất bỏ cơ chế audit, kiểm tra hiệu lực hoặc SLA của hệ thống thật. Giá trị `unknown`/`null` là hợp lệ và phải giữ nguyên cho tới khi có chứng cứ.

| Object | Trường bắt buộc | Quy tắc kiểm tra |
| --- | --- | --- |
| `technical_request` | `ticket_id`, `tenant_id`, `building_id`, `unit_id/common_area_id`, `issue_code`, `reported_text`, `reporter_role`, `facts[]`, `unknown_fields[]`, `hazard_signals[]` | Mọi fact có `source`, `verification_status`; không dùng `null` thay `false`; scope do backend xác thực. |
| `asset_context` | `asset_id`, `model`, `location`, `ownership_scope`, `warranty_reference`, `manual_version`, `source_refs[]` | Nếu nhiều asset có thể liên quan, trả danh sách và yêu cầu xác nhận; không tự chọn. |
| `diagnostic_assessment` | `hypotheses[]`, `confirmed_cause`, `assessor`, `method_ref`, `confidence_limit` | `confirmed_cause` chỉ được điền từ biên bản/người có quyền, không từ nội dung RAG hoặc câu trả lời LLM. |
| `service_isolation` | `request_id`, `utility`, `asset_or_valve_id`, `scope_ids[]`, `reason`, `approval_id`, `status`, `actor`, `notice_refs[]` | `proposed`/`notified` không được hiển thị như `active`; `active`/`restored` yêu cầu log actor thực địa. |
| `work_order` | `workorder_id`, `ticket_id`, `assignee`, `assignment_status`, `sop_version`, `checklist`, `parts[]`, `measurements[]`, `evidence_ids[]`, `result_status` | Kết quả `submitted` phải có assignment đúng scope, evidence đã kiểm tra và version; không giả ảnh hoặc phép đo. |
| `cost_review` | `ownership_basis`, `warranty_basis`, `cause_evidence_id`, `contract_version_id`, `cost_route_candidate`, `quote_id`, `quote_approved_by`, `payer_authorization`, `fee_decision`, `amount`, `currency`, `invoice_id` | Không có chứng cứ/báo giá/quyền duyệt thì các trường tiền vẫn `null`; báo giá không là hóa đơn, người báo không mặc nhiên là người trả. |
| `resolution_review` | `sop_version`, `acceptance_criteria`, `check_results[]`, `evidence_refs[]`, `verification_recommendation`, `reviewer`, `ticket_closed` | `VERIFIED` của tool chỉ là khuyến nghị; `ticket_closed` đổi bởi workflow có quyền riêng. |

### Ví dụ payload trạng thái an toàn cho M01 [MOCK]

```json
{
  "fixture_only": true,
  "ticket_id": "HB-SYN-001",
  "tenant_id": "TEST-ONLY",
  "building_id": "SYN-B-01",
  "unit_id": "SYN-U-12",
  "issue_code": "TECH.PLUMB.CONCEALED_LEAK",
  "facts": [{"name": "ceiling_stain", "value": true, "source": "resident_report", "verification_status": "reported"}],
  "unknown_fields": ["water_near_electricity", "source_unit", "pipe_ownership"],
  "hypotheses": [
    {"name": "private_branch_above", "status": "unconfirmed"},
    {"name": "common_riser", "status": "unconfirmed"}
  ],
  "confirmed_cause": null,
  "service_isolation": {"status": "proposed", "utility": "water", "asset_or_valve_id": null, "approval_id": null},
  "work_order": {"status": "draft", "assignment_status": "not_assigned", "executor_result": "not_submitted"},
  "cost_review": {"cost_route_candidate": "UNDETERMINED", "fee_decision": "PENDING_HUMAN_REVIEW", "amount": null, "currency": null, "invoice_id": null},
  "resolution_review": {"verification_recommendation": "NOT_RUN_MISSING_RESULT", "ticket_closed": false}
}
```

## 7. Dữ liệu chưa tìm được và việc phải xin [CẦN BQL]

| Thiếu | Vì sao không thể suy từ web | Chủ thể/hồ sơ cần xin | Hành vi hệ thống trong lúc thiếu |
| --- | --- | --- | --- |
| SOP xử lý sự cố **đúng tòa–thiết bị–model** và version/hiệu lực | Bài hãng, PMC, HUD không mô tả cấu hình từng tòa Vinhomes | BQL kỹ thuật, chủ đầu tư, hãng, hồ sơ bàn giao/manual | Chỉ triage/handoff; `sop_kb.retrieve` không trả profile mock. |
| Sơ đồ điện/nước, van, tải thiết yếu, ranh giới ảnh hưởng | Không công khai vì an toàn và tính đặc thù tòa | BQL/CMMS/as-built được cấp quyền | Không tự chọn điểm cắt; giữ isolation `proposed`/`requires_human`. |
| Ma trận quyền cô lập và thông báo khẩn/có kế hoạch | Không thấy quy trình Vinhomes công khai theo tòa | BQL, an toàn/PCCC, pháp chế, nhà cung cấp điện/nước | Không suy người phê duyệt, thời lượng báo trước hay ETA. |
| Bảng phân định sở hữu chung/riêng theo hạng mục | Tên vị trí “trong căn” chưa chứng minh ownership của ống/trục/kết cấu | Hợp đồng căn, phụ lục, bản vẽ bàn giao, quy chế chung cư | `cost_route_candidate=UNDETERMINED` khi có tranh chấp. |
| Hợp đồng/phiếu bảo hành **của căn và thiết bị cụ thể** | Mẫu R03 không đại diện mọi dự án; thời hạn mỗi thiết bị khác nhau | Chủ sở hữu/BQL/chủ đầu tư/hãng với consent | Chỉ `WARRANTY_REVIEW`, không hứa miễn phí. |
| Biểu phí sửa chữa, đơn giá vật tư, hợp đồng vendor và chính sách báo giá | Không tìm thấy bảng giá vận hành kỹ thuật Vinhomes đủ phạm vi/phiên bản | BQL tài chính, procurement, vendor, hóa đơn thực tế verified | `amount=null`, `insufficient_data`; không tính từ giá web hoặc fixture. |
| Ticket/work order và nguyên nhân–outcome thật đã ẩn danh | Phản ánh Huế không có chuỗi sửa chữa Vinhomes; repo Data-Vinhome nhiều mục còn thiếu | Work Order/CRM Vinhomes với quyền xử lý dữ liệu | Dùng M01–M04 để test pipeline, không train như sự thật. |
| Ảnh/evidence/đo đạc thật với provenance và quyền sử dụng | Ảnh web không chứng minh tình trạng asset của tòa | Kỹ thuật viên, storage/scan, consent cư dân | Không chạy verify hoặc trả `NEEDS_EVIDENCE`/`HUMAN_REVIEW`. |
| Tiêu chí nghiệm thu và ngưỡng kỹ thuật được duyệt | HUD/hãng có phạm vi khác nhau; một ngưỡng có thể nguy hiểm nếu chuyển nguyên | Domain Owner và chuyên gia kỹ thuật đúng model | Không tạo số đo pass/fail tự động từ văn bản tham khảo. |
| Policy phân cấp mức độ/ưu tiên/SLA | Mức P1–P4 hoặc thời gian từ nguồn khác không phải policy V3 | Policy Owner V3 và hợp đồng dịch vụ tòa | Chỉ phát hiện tín hiệu cần đánh giá, không hứa SLA hoặc tự gán priority chính thức. |

## 8. Checklist kiểm thử và điều kiện publish

**Tối thiểu cho POC cô lập:** 16 issue playbook đều có intake, giả thuyết, hazard, work order, điều kiện đề nghị cô lập, phí ứng viên và evidence; thêm 7 yêu cầu liên quan để test router. Case `water_near_electricity=true` phải chuyển trực; `unknown` không tự thành `false`; request cô lập chưa duyệt không thành outage active; outage tòa khác không lọt vào scope; khôi phục cần actor và thử chức năng. Case giá thiếu contract/báo giá phải trả `INSUFFICIENT_DATA`/`PENDING_HUMAN_REVIEW`, không phát sinh amount/invoice. M01–M04 phải giữ `ticket_closed=false` nếu chưa có người nghiệm thu.

**Gate lên vận hành:** người có thẩm quyền duyệt SOP, version và scope; pháp chế kiểm tra văn bản/hợp đồng hiệu lực; BQL cung cấp phân quyền, sơ đồ asset, policy cô lập và thông báo; finance cung cấp bảng giá hợp lệ; có thử nghiệm retrieval không lẫn mock; có test bảo vệ PII, tenant/building ACL, idempotency, audit, evidence scan và rollback. Thiếu một gate thì file này vẫn là tài liệu phát triển, không phải câu trả lời chuẩn cho cư dân.

**Thay đổi so với `technical-data` trước:** gom nghiên cứu nguồn công khai và toàn bộ 16 luồng xử lý vào **một Markdown** trong thư mục mới; bổ sung nhánh bảo hành/chi phí có điều kiện, workflow cô lập điện–nước, 7 yêu cầu ngoài taxonomy và 4 ca end-to-end. Không sửa hai corpus embedding cũ, không thay 16 profile `draft`, không ghi dữ liệu mock vào manifest nguồn như fact đã xác minh.

## 9. Bối cảnh và quy tắc để chạy trọn demo [MOCK — HB-RULES-V2]

Toàn bộ mục 9 là dữ liệu sáng tác cho phần mềm thử nghiệm. Giá, người, hợp đồng, tài sản và kết quả ở đây không thuộc một khu Vinhomes thật. Đối với các diễn biến ghi là “đã xác nhận”, hiểu là **actor giả lập đã xác nhận trong kịch bản**, không phải file này đã được kỹ thuật viên kiểm định.

### 9.1 Tòa nhà, người dùng và hồ sơ căn hộ

| Đối tượng | Giá trị mock | Cách sử dụng |
| --- | --- | --- |
| Tenant / tòa | `TEST-ONLY` / `SYN-B-01`, tên hiển thị “TÒA MÔ PHỎNG B1” | Tất cả ca trong sổ tay dùng scope này; ID dạng chữ là alias tài liệu, adapter test tự map UUID. |
| Căn báo chính | `SYN-U-12`, tên hiển thị “Căn mẫu 1201” | Chủ căn `SYN-OWNER-12`; người thuê/người báo `SYN-RES-12`; hai vai trò có quyền khác nhau. |
| Căn liên quan | `SYN-U-13`, tên hiển thị “Căn mẫu 1301” | Chủ căn `SYN-OWNER-13`; dùng khi cần kiểm tra căn trên. Người ở căn 1201 không được xem thông tin cá nhân/hồ sơ tài chính căn 1301. |
| Hợp đồng mô phỏng | `SYN-CONTRACT-01@v2` | Phụ lục mock quy định ống nhánh sau điểm phân định, thiết bị và hoàn thiện trong căn là riêng; trục đứng, bơm chung là chung. Đây là giả định được gán trong môi trường test, không suy từ địa chỉ. |
| Bảo hành hạng mục bàn giao mô phỏng | `SYN-WARRANTY-01@v2` | Chỉ các hạng mục được ca gắn claim này; điều kiện đủ bảo hành là giả định trong từng ca, không xác định quyền theo hợp đồng thật. |
| Bảo hành thiết bị mô phỏng | `SYN-WARRANTY-DEVICE-01@v1` | Dùng cho máy của HB-03-A trong storyboard. Các asset khác có eligibility riêng. Thời hạn thiết bị phải tra hãng/model, không lấy thời hạn công trình áp sang. |
| Quan hệ hồ sơ | `ticket → assessment → work_order → result → verification → human_acceptance` | Một ticket có thể có nhiều work order; ví dụ sửa ống và khôi phục sơn cần hai phạm vi công việc. |
| Tài liệu kỹ thuật | `manual_ref=null` nếu chưa có manual thực; `test_rule_ref=HB-RULES-V2` | Rulebook chỉ cho chạy storyboard/stub. Nó không làm SOP trở thành eligible trong `sop_kb.retrieve`. |

### 9.2 Vai trò và quyền của nhân vật mô phỏng

| Vai trò/ID | Công việc trong câu chuyện | Kết quả được ghi |
| --- | --- | --- |
| Lễ tân `SYN-DESK-01` | Xác minh địa điểm, nhận tin, liên hệ cư dân, điều phối lịch | Ticket/intake, lịch hẹn dự kiến và nhật ký liên hệ. |
| Kỹ thuật điện `SYN-TECH-E` | Khảo sát điện và thiết bị điện theo chuyên môn | Kết quả kiểm tra, đề xuất phạm vi cô lập, báo cáo thực hiện/khôi phục do mình làm. |
| Kỹ thuật nước `SYN-TECH-W` | Khảo sát cấp/thoát nước, nguồn rò, thiết bị vệ sinh | Điểm hỏng, phương án thay vật tư, kết quả thử chức năng. |
| Kỹ thuật HVAC `SYN-TECH-H` | Kiểm tra máy lạnh và đường thoát ngưng | Nguồn nước, vật tư, biên bản chạy thử theo model. |
| Nhà thầu hoàn thiện `SYN-VENDOR-F` | Cửa, tủ, sàn, sơn theo phạm vi được duyệt | Hồ sơ vật tư, biện pháp và kết quả thi công. |
| Kỹ sư chuyên trách `SYN-ENG-S` | Đánh giá các ca nghi kết cấu | Kết luận chuyên môn mô phỏng; agent không thay vai trò này. |
| Quản lý kỹ thuật `SYN-MGR-01` | Duyệt kế hoạch kỹ thuật, phạm vi gián đoạn, chuyển vendor, review kết quả | Quyết định có actor/revision; chưa có actor thì giữ trạng thái chờ. |
| Tài chính `SYN-FIN-01` | Xét nguồn chi, báo giá, hạng mục được bảo hành | `mock_cost_decision`, tách người phê duyệt chi và người chịu tiền. |
| Chủ căn `SYN-OWNER-12` | Đồng ý báo giá phần riêng hoặc ủy quyền cho người thuê | Đồng ý một quote revision và phạm vi cụ thể; im lặng không là đồng ý. |
| Người thuê `SYN-RES-12` | Báo sự cố, cho phép lịch vào căn theo quyền đang có, phản hồi sử dụng | Đồng ý lịch không đồng nghĩa nhận trách nhiệm tài chính. |

### 9.3 Cấu trúc phiếu công việc sử dụng trong 32 ca

Một phiếu phải mô tả: lời báo; vị trí; câu trả lời sàng lọc; giả thuyết; hạng mục cần kiểm tra; người phụ trách; quyền vào; yêu cầu cô lập nếu có; vật tư dự kiến; kết quả cần chứng minh; việc ngoài phạm vi; lịch dự kiến; quy tắc báo phát sinh. Trạng thái storyboard sử dụng `received`, `assessing`, `awaiting_diagnosis`, `waiting_access`, `waiting_approval`, `scheduled`, `in_progress`, `waiting_parts`, `waiting_dependency`, `awaiting_review`, `completed_by_human`, `reopened`. **Đây là nhãn UI mock, không phải danh sách enum DB đang có.**

Khi thiếu vật tư: kỹ thuật viên ghi `part_code`, số lượng, cấu hình tương thích, lựa chọn tạm thời được quản lý đồng ý và đầu mối cập nhật; người báo nhận thông tin phần nào dùng được/phần nào còn hạn chế. Khi cư dân vắng: lễ tân đề xuất hai khung hẹn, ghi từng lần liên hệ và vẫn chuyển trực nếu nguy cơ lan sang căn khác. Khi phát sinh công việc ngoài báo giá: đóng băng phần phát sinh, tạo quote revision, chỉ tiếp tục sau người đúng quyền đồng ý; không sửa quote cũ đã được chấp thuận.

Một ticket được tách thành các work order con khi chuyên môn hoặc đối tượng chi khác nhau. Ví dụ `WO-PIPE` sửa nguồn rò và `WO-PAINT` xử lý vệt ố liên kết cùng `parent_ticket`; hoàn tất ống không tự hoàn tất phần sơn. Khi tái phát, tạo sự kiện `reopened` liên kết lần sửa trước, giữ ảnh/biên bản và kiểm tra bảo hành lần sửa; không ghi đè kết quả cũ hoặc mặc định thu một lần phí mới.

### 9.4 Quy tắc mock về gián đoạn dịch vụ

Trong demo, mỗi yêu cầu gián đoạn có `reason`, `utility`, `asset_alias`, `affected_units`, `approval_actor`, `execution_actor`, `notice_log`, `remaining_restrictions`. Chọn nhánh theo **phạm vi đã được nhân vật kỹ thuật xác nhận**, không theo căn người báo. Nguồn cấp căn 1201 và nhánh 1201–1301 là hai scope khác nhau; đổi scope cần revision và thông báo cập nhật.

Với việc có kế hoạch, fixture yêu cầu phê duyệt và thông báo trước khi thực hiện. Khi chưa đạt điều kiện phục hồi, quản lý cập nhật tình trạng và phương án hỗ trợ; hệ thống chỉ ghi khôi phục khi có xác nhận thực địa. Các thông số điều phối phải lấy từ policy đã được duyệt, không suy từ storyboard.

Với tình huống khẩn, actor trực xử lý theo quyền/phương án ứng cứu của môi trường triển khai. Storyboard có thể nhận sự kiện thực địa đã thực hiện trước khi lễ tân hoàn tất nhập liệu: giữ phân biệt sự kiện thực địa và sự kiện tiếp nhận, đánh dấu `emergency_action_reported`, chuyển quản lý rà soát; không bịa hoặc chèn ngược phê duyệt vào chuỗi sự kiện. Agent luôn chỉ ghi nhận/chuyển giao. Các vấn đề PCCC, tải thiết yếu, cứu hộ thang và khí nguy hiểm do đơn vị chuyên trách điều phối.

Điều kiện khôi phục trong demo: actor kỹ thuật đã gửi kết quả công việc; các bước kiểm tra cần thiết cho tài sản đều có kết quả; phạm vi ảnh hưởng đã được xác nhận; quản lý không còn yêu cầu hạn chế; người thực hiện ghi xác nhận phục hồi; thông báo sau phục hồi được ghi nhận. Nếu mới sửa nguồn nhưng chưa đánh giá khu vực ướt, trạng thái dịch vụ và trạng thái an toàn khu vực phải hiển thị riêng.

### 9.5 Bảng giá sáng tác để dựng màn hình báo giá

Đơn vị `VND`; mọi con số dưới đây là **giá giả lập tự đặt**, không thu thập từ thị trường. Mỗi dòng dùng số lượng nguyên, làm tròn 0 đồng trong demo. `demo_tax=0` và `demo_discount=0` chỉ là cấu hình phép tính, không thể hiện chế độ thuế thực tế. Không nhập bảng này vào actual-cost observations hoặc công cụ estimate của dữ liệu thật.

| Mã giá mock | Diễn giải mẫu | Đơn vị | Đơn giá demo |
| --- | --- | --- | ---: |
| `F-DIAG` | Khảo sát đã được đồng ý riêng | lượt | 100000 |
| `L-ELEC` | Công sửa hạng mục điện đã khoanh phạm vi | công việc | 200000 |
| `L-WATER` | Công sửa hạng mục nước trong căn | công việc | 180000 |
| `L-HVAC` | Công xử lý hệ thoát ngưng của máy căn hộ | công việc | 250000 |
| `L-JOINERY` | Công sửa cửa/tủ trong căn | công việc | 220000 |
| `L-FINISH` | Công hoàn thiện vùng đã xác định | công việc | 300000 |
| `L-CLEAN` | Công vệ sinh sau sự cố theo phạm vi được duyệt | công việc | 300000 |
| `M-SOCKET` | Bộ ổ cắm tương thích giả lập | bộ | 90000 |
| `M-HEATER` | Cụm linh kiện máy nóng tương thích giả lập | bộ | 350000 |
| `M-FILTER` | Lõi lọc đúng model giả lập | lõi | 180000 |
| `M-AC-DRAIN` | Phụ kiện thoát nước ngưng | bộ | 80000 |
| `M-PIPE` | Đoạn ống/phụ kiện sửa điểm rò | bộ | 160000 |
| `M-SHOWER` | Bộ gioăng/keo vách tắm | bộ | 140000 |
| `M-TOILET` | Bộ phận kín nước két bồn cầu | bộ | 130000 |
| `M-TRAP` | Bẫy nước phù hợp cấu hình mẫu | bộ | 90000 |
| `M-JOINT` | Bộ nối cấp/thoát tương thích | bộ | 70000 |
| `M-DOOR` | Phụ kiện bản lề cửa mẫu | bộ | 120000 |
| `M-CABINET` | Bộ bản lề tủ mẫu | bộ | 110000 |
| `M-CRACK` | Vật liệu sửa lớp hoàn thiện | bộ | 160000 |
| `M-PAINT` | Vật liệu hoàn thiện sơn vùng mẫu | bộ | 200000 |
| `M-FLOOR` | Tấm sàn cùng mã mẫu | tấm | 320000 |
| `S-DRAIN` | Dịch vụ xử lý nghẽn nhánh đã xác định | công việc | 450000 |
| `S-STRUCT` | Khảo sát chuyên môn kết cấu giả lập | lượt | 1500000 |

Quy tắc báo giá demo: tổng dòng = số lượng × đơn giá; `mock_quote_total_vnd` = tổng các dòng + thuế demo − giảm giá demo. `mock_resident_share_vnd` chỉ có số sau quyết định nguồn chi trong câu chuyện; có thể là `0`, tổng báo giá hoặc `null` khi còn tranh chấp. Bảo hành/common funding vẫn có chi phí thực hiện giả lập nhưng số cư dân bị thu bằng 0 trong ca đã duyệt. Không tự cộng `F-DIAG` vào mọi công việc: chỉ có khi bên chịu chi đã chấp thuận khoản khảo sát riêng. Trong HB-01-A đây là chi nội bộ được bên bảo hành nhận; nếu dự kiến thu chủ căn thì phải có đồng ý riêng của chủ căn/người được ủy quyền.

### 9.6 Sáu quyết định tài chính mẫu

| Quyết định của actor mock | Hồ sơ đủ để dựng ca | Kết quả UI |
| --- | --- | --- |
| Bảo hành được chấp nhận | Asset thuộc hồ sơ bảo hành bàn giao hoặc thiết bị phù hợp, nguyên nhân thuộc phạm vi, bên bảo hành chấp nhận claim | Hiển thị “Bảo hành đã chấp nhận trong demo”; `mock_resident_share_vnd=0`, lưu claim và đơn vị thực hiện. |
| Bảo trì hệ chung được duyệt | Bản phân định mock, nguyên nhân và phạm vi hệ chung, quản lý/tài chính duyệt nguồn chi | `mock_resident_share_vnd=0`; không chia tổng tiền cho số căn bị ảnh hưởng. |
| Chủ căn chấp thuận sửa riêng | Asset riêng, bảo hành không áp dụng, quote revision và chủ căn đồng ý | `mock_resident_share_vnd=mock_quote_total_vnd`; người chịu tiền là chủ căn hoặc người có ủy quyền được ghi rõ. |
| Người thuê mới đồng ý lịch | Có lịch vào căn nhưng không có quyền duyệt tiền | Báo giá vẫn `pending_payer_consent`, số phải thu `null`. |
| Nguồn hỏng chưa rõ/đang tranh chấp | Biên bản hai bên khác nhau hoặc chưa xác định điểm rò | `disputed`, số phải thu `null`; có thể có dự toán công việc nhưng chưa có nghĩa vụ thanh toán. |
| Phát sinh sau khi mở kiểm tra | Phạm vi mới không có trong quote đã duyệt | Tạo revision, trình lại phần thêm; không sửa tổng của bản cũ hoặc coi đồng ý lịch là đồng ý phát sinh. |

Các quyết định trên dùng cho workflow tài chính **mô phỏng ngoài quyền A2**. Không thêm tool tự thu phí, tự xuất hóa đơn hoặc tự đóng ticket vào technical agent.

### 9.7 Inventory tối thiểu để liên kết ticket và asset

Mỗi hàng là một tài sản sáng tác tại tòa mẫu. `model` khi adapter cần có thể dùng `MOCK-MODEL-<alias>`; đó không phải model thương mại. `manual_ref=null`, `ownership_source=SYN-CONTRACT-01@v2`, `inventory_source=synthetic_author`. Người viết không tạo bản vẽ điện/nước dùng cho thao tác thực tế.

| Asset alias | Vị trí/phạm vi mock | Sở hữu trong hợp đồng giả lập | Ca A sử dụng |
| --- | --- | --- | --- |
| `SYN-CIRCUIT-12` | Nhánh điện bếp căn 1201 | Riêng, thuộc hạng mục bàn giao được nhận bảo hành trong ca | HB-01-A |
| `SYN-SOCKET-12` | Ổ bàn làm việc căn 1201 | Riêng, hết bảo hành trong ca | HB-02-A |
| `SYN-HEATER-12` | Máy nóng căn 1201 | Riêng, có claim hãng được nhận trong ca | HB-03-A |
| `SYN-FILTER-12` | Máy lọc căn 1201 | Riêng; lõi là vật tư tiêu hao trong ca | HB-04-A |
| `SYN-AC-12` | Máy lạnh phòng khách và tuyến ngưng riêng | Riêng, sửa dịch vụ có phí trong ca | HB-05-A |
| `SYN-RISER-02` | Trục cấp mẫu, scope cần actor xác nhận | Chung; bản vẽ fixture phân định điểm rò trong ca | HB-06-A |
| `SYN-SHOWER-12` | Vách tắm WC căn 1201 | Riêng, claim bàn giao được nhận trong ca | HB-07-A |
| `SYN-WC-12` | Bồn cầu WC căn 1201 | Riêng, phụ kiện hết bảo hành trong ca | HB-08-A |
| `SYN-TRAP-12` | Bẫy chậu căn 1201 | Riêng, thay dịch vụ trong ca | HB-09-A |
| `SYN-JOINT-12` | Đầu nối chậu căn 1201 | Riêng, thay dịch vụ trong ca | HB-10-A |
| `SYN-DOOR-12` | Cửa phòng căn 1201 | Riêng, claim bàn giao được nhận trong ca | HB-11-A |
| `SYN-CABINET-12` | Tủ bếp căn 1201 | Riêng, phụ kiện dịch vụ trong ca | HB-12-A |
| `SYN-WALL-12` | Vùng lớp hoàn thiện có nứt trong căn 1201 | Riêng, nhận bảo hành lớp hoàn thiện trong ca | HB-13-A |
| `SYN-PAINT-12` | Vùng sơn trần bị ảnh hưởng tại căn 1201 | Riêng; nguồn chi khôi phục được duyệt riêng vì sự cố chung | HB-14-A |
| `SYN-FLOOR-12` | Vùng sàn phòng khách căn 1201 | Riêng, sửa dịch vụ trong ca | HB-15-A |
| `SYN-DRAIN-R2` | Tuyến thoát chung mẫu | Chung, theo quyết định nguồn chi giả lập | HB-16-A |
| `SYN-PUMP-01` | Bơm cấp chung mẫu | Chung | EXT nước |
| `SYN-LIFT-01` | Cabin thang máy mẫu | Chung, có hợp đồng vendor mock | EXT thang |
| `SYN-FIRE-01` | Asset hệ báo cháy mẫu | Chung, do chuyên trách quản lý | EXT PCCC |
| `SYN-ACCESS-01` | Intercom/cửa sảnh mẫu | Chung, dữ liệu quyền truy cập do an ninh giữ | EXT access |

Mỗi ca bắt đầu từ snapshot độc lập với `case_run_id`; không cộng 16 tình huống thành một lịch sử căn hộ thật. Ca B tái phát có thể dùng `parent_case_id` trỏ ca A, nhưng sự kiện được tái dựng riêng trong test. Người sửa/lỗi/bảo hành trong ca này không làm thay dữ liệu của ca khác.

### 9.8 Kết quả kỳ vọng của 16 nhánh thành công

Đây là bảng để đối chiếu storyboard và phép tính, không phải bảng giá đề xuất bán dịch vụ. `WARRANTY_ACCEPTED`, `COMMON_FUNDED`, `OWNER_ACCEPTED` là nhãn kết quả tài chính mock, không phải enum backend hiện hành.

| Ca A | Dòng dự toán | Tổng demo VND | Cư dân trả demo VND | Kết quả nguồn chi | Điều kiện cuối còn phải có |
| --- | --- | ---: | ---: | --- | --- |
| HB-01-A | F-DIAG × 1; L-ELEC × 1 | 300000 | 0 | WARRANTY_ACCEPTED | Checklist điện và quản lý nghiệm thu. |
| HB-02-A | L-ELEC × 1; M-SOCKET × 1 | 290000 | 290000 | OWNER_ACCEPTED | Quote r1 được chủ căn đồng ý, kết quả điện. |
| HB-03-A | L-ELEC × 1; M-HEATER × 1 | 550000 | 0 | WARRANTY_ACCEPTED | Biên bản hãng và phục hồi chức năng. |
| HB-04-A | L-WATER × 1; M-FILTER × 1 | 360000 | 360000 | OWNER_ACCEPTED | Mã lõi, kiểm rò/lưu lượng, bàn giao. |
| HB-05-A | L-HVAC × 1; M-AC-DRAIN × 1 | 330000 | 330000 | OWNER_ACCEPTED | Kiểm nguồn/thoát ngưng; ghi rõ phần ố còn lại. |
| HB-06-A | L-WATER × 1; M-PIPE × 1 | 340000 | 0 | COMMON_FUNDED | Nghiệm thu sửa nguồn; ticket tổng còn chờ hoàn thiện. |
| HB-07-A | L-WATER × 1; M-SHOWER × 1 | 320000 | 0 | WARRANTY_ACCEPTED | Điều kiện vật liệu và thử kín. |
| HB-08-A | L-WATER × 1; M-TOILET × 1 | 310000 | 310000 | OWNER_ACCEPTED | Thử nạp/giữ/xả theo model. |
| HB-09-A | L-WATER × 1; M-TRAP × 1 | 270000 | 270000 | OWNER_ACCEPTED | Điểm kín/thoát và phản hồi sử dụng. |
| HB-10-A | L-WATER × 1; M-JOINT × 1 | 250000 | 250000 | OWNER_ACCEPTED | Kiểm cấp/thoát tại vùng đã can thiệp. |
| HB-11-A | L-JOINERY × 1; M-DOOR × 1 | 340000 | 0 | WARRANTY_ACCEPTED | Chức năng cửa và bàn giao. |
| HB-12-A | L-JOINERY × 1; M-CABINET × 2 | 440000 | 440000 | OWNER_ACCEPTED | Thợ xác nhận phạm vi và chức năng. |
| HB-13-A | L-FINISH × 1; M-CRACK × 1 | 460000 | 0 | WARRANTY_ACCEPTED | Biên bản chuyên môn, nghiệm thu, lịch theo dõi. |
| HB-14-A | L-FINISH × 1; M-PAINT × 1 | 500000 | 0 | COMMON_FUNDED | Điều kiện bề mặt, nguồn chi phục hồi riêng được duyệt. |
| HB-15-A | L-FINISH × 1; M-FLOOR × 3 | 1260000 | 1260000 | OWNER_ACCEPTED | Đúng số tấm/phạm vi, kiểm nền và bàn giao. |
| HB-16-A | S-DRAIN × 1; L-CLEAN × 1 | 750000 | 0 | COMMON_FUNDED | Thử thoát, vệ sinh và quyền dùng lại. |

Các tên ảnh/biên bản kiểu `SIM-EV-*`, `SYN-RPT-*` trong câu chuyện là **artifact được mô tả**, chưa có file vật lý hay kết quả scan. Nếu chạy với tool thật mà chưa seed file/evidence/SOP test hợp lệ, kết quả phải là thiếu evidence hoặc human review theo contract. Chỉ harness mock mới có thể cung cấp kết quả giả lập tương ứng; không đổi các alias này thành bằng chứng verified để làm test pass.

## 10. Mười luồng mở rộng có diễn biến cụ thể [MOCK]

Các luồng sau dùng cùng tòa và actor mẫu tại mục 9, thêm actor chuyên trách khi cần. Chúng chưa mở rộng mã issue/API A2 của repo.

### EXT-01 · Mất nước nhiều căn hoặc cả tòa

**Nhận tin:** ghi căn/tầng, vòi nào mất, còn nước tại đầu dùng nào, có thông báo gián đoạn không, có màu/mùi bất thường hoặc rò. Gom tin theo sự kiện và scope nhưng giữ các hazard riêng của từng căn. **Chẩn đoán mock:** kỹ thuật phân biệt nguồn ngoài, bơm/bồn, trục/van chung và nhánh căn; agent tra dữ liệu được phép, không điều khiển BMS.

**Thực hiện:** BQL nhận incident tổng; actor kỹ thuật xác minh thiết bị và phạm vi; lập phương án tạm/nguồn hỗ trợ phù hợp; nếu cần sửa có gián đoạn thì ghi approval và thông báo; nhân sự thực hiện; kiểm tra phục hồi theo hệ thống trước cập nhật `restored`. Một sensor báo bình thường không thay việc xác nhận nguồn đã tới các scope ảnh hưởng. **Phí:** kế hoạch/vendor/common funding do actor tài chính quyết định, không thu từng người đã báo.

**Ca `HB-EXT-01`:** ba căn thuộc scope `SYN-RISER-02` báo mất nước; BQL tạo incident tổng; actor kiểm tra xác định lỗi tại cụm bơm chung trong fixture. Cư dân được cập nhật “đang xử lý, chưa xác nhận khôi phục”. Actor gửi kết quả và xác nhận các điểm kiểm tra theo scope; BQL thông báo phục hồi. Một căn vẫn mất nước được tạo work order nhánh riêng; incident tổng không được xóa lời báo còn tồn tại của căn đó.

### EXT-02 · Mất điện khu chung hoặc nhiều căn

**Nhận tin:** phân biệt một căn, nhóm tầng hay khu chung; xác định có người bị kẹt thang, đèn lối thoát/tải thiết yếu bị ảnh hưởng hoặc dấu khói/nước. **Chẩn đoán mock:** đối chiếu outage nguồn ngoài, sự kiện nội bộ và asset; thiết bị dự phòng do nhân sự điện phụ trách, không coi có máy phát đồng nghĩa mọi căn có điện.

**Thực hiện:** người trực điện/BQL lập scope và phối hợp nhà cung cấp nếu liên quan; ghi thông tin các hệ phụ thuộc để chuyển thang/PCCC/an ninh; nhân sự xác nhận diễn biến nguồn và từng phạm vi khôi phục. Có thể trả điện theo vùng nên `partially_restored` chỉ là nhãn UI mock với danh sách scope, không tự thay enum DB. **Phí:** giữ nguồn chi chờ xác minh khi chưa rõ lưới ngoài hay hệ nội bộ.

**Ca `HB-EXT-02`:** sảnh có điện lại nhưng căn 1201 vẫn mất; hệ thống hiển thị “khu sảnh đã phục hồi; căn 1201 đang kiểm tra”, không gửi một thông báo toàn tòa “đã có điện”. Khi actor báo xong scope riêng, mới cập nhật căn. Phản ánh thang đang có người kẹt tạo handoff khẩn độc lập, không chờ xử lý ticket điện hoàn tất.

### EXT-03 · Thang máy dừng hoặc có người kẹt

**Nhận tin:** xác định tòa/cabin, vị trí hiển thị nếu biết, số người và khả năng liên lạc; ghi nhu cầu hỗ trợ khẩn ở mức cần thiết. Không trì hoãn chuyển người để hỏi đủ biểu mẫu. **Thực hiện:** trực tòa liên hệ đơn vị cứu hộ/bảo trì theo phương án; ghi ai tiếp nhận và cập nhật liên lạc; thiết lập không sử dụng cabin theo người có quyền; đơn vị chuyên trách thực hiện cứu hộ và kiểm tra thang. Agent không tạo hướng dẫn mở cửa, di chuyển cabin hay can thiệp cơ cấu thang.

**Điều kiện kết thúc:** tách `occupants_released` khỏi `lift_returned_to_service`; giải thoát người chưa đồng nghĩa cho thang hoạt động lại. Hồ sơ có biên bản sự cố, tình trạng người được bàn giao qua kênh phù hợp, kết quả kiểm tra nhà thầu và quản lý cho dùng lại. **Phí:** hợp đồng bảo trì/lỗi được xác nhận; không gán tiền cứu hộ cho người báo.

**Ca `HB-EXT-03`:** fixture có hai người trong cabin `SYN-LIFT-01`. Actor cứu hộ báo đã đưa người ra; UI cabin vẫn “tạm ngừng sử dụng”. Vendor còn chờ linh kiện, BQL duy trì thông báo cabin nghỉ. Chỉ khi vendor nộp biên bản hoàn tất và người có quyền chấp thuận, trạng thái cabin mới đổi; ticket có thể chờ phần sửa dù sự kiện cứu người đã hoàn thành.

### EXT-04 · Báo cháy, thiết bị báo cháy lỗi hoặc lối thoát bị ảnh hưởng

**Nhận tin:** lời báo cháy/khói và cảnh báo hệ thống phải chuyển trực theo phương án tòa; ghi vị trí, người ảnh hưởng, thiết bị nếu biết. Chưa xác minh nguyên nhân không đồng nghĩa báo giả. **Nhánh bảo trì:** chỉ sau người chuyên trách xác định đây là công việc bảo trì, mới lập phương án thiết bị/phạm vi tạm mất chức năng, phương án bù đắp, người giám sát và điều kiện khôi phục.

**Thực hiện:** BQL/PCCC/vendor phối hợp; mọi diễn biến test, gián đoạn, khôi phục do actor đủ quyền ghi; agent chỉ nhận trạng thái và điều phối thông tin. Cửa thoát/lối thoát lỗi được đưa vào cùng đánh giá ảnh hưởng. **Phí:** chi hệ chung, bảo hành hoặc thiệt hại được xác minh; nội dung tin báo không quyết định người trả.

**Ca `HB-EXT-04`:** có tin đầu báo thường xuyên phát cảnh báo; người báo yêu cầu tắt hẳn. Agent chuyển trực, không lập lệnh vô hiệu hóa. Sau chuyên trách xác nhận nhánh bảo trì, vendor kiểm tra/thay theo kế hoạch được duyệt. “Đã hết tiếng còi” chưa đủ closeout; phải có xác nhận hệ thống đã phục hồi chức năng và biên bản test của chuyên trách.

### EXT-05 · Mùi gas hoặc khí nghi nguy hiểm

**Nhận tin:** ghi vị trí, người bị ảnh hưởng và kênh liên hệ; ưu tiên chuyển đơn vị chuyên trách. Không bắt người báo quay lại để xác định loại khí, thử công tắc hoặc tìm điểm rò. **Chẩn đoán:** chỉ nhân sự đủ chuyên môn xác nhận loại nguồn/hệ cấp và điều kiện tiếp cận. Mùi mất đi không tự chứng minh vùng đã an toàn.

**Thực hiện:** actor trực phối hợp phương án ứng cứu, hạn chế vùng và nhà cung cấp; cô lập/đánh giá/khôi phục là hành động chuyên môn theo hệ thực tế. Ghi scope, kết quả tiếp nhận, actor quyết định sử dụng lại và thông báo liên quan. **Phí:** bình/hệ riêng, hệ chung, vendor và trách nhiệm chưa rõ là các nhánh điều tra, không thu trước từ người báo.

**Ca `HB-EXT-05`:** người thuê báo mùi gần bếp rồi nói “không còn mùi nữa”. Ticket vẫn chờ xác nhận chuyên trách, không tự hạ thành mùi cống. Trong fixture, đơn vị chuyên môn tiếp nhận và quyết định phạm vi kiểm tra; chưa có biên bản kết thúc thì không gửi “đã an toàn”. Số phải thu vẫn `null`.

### EXT-06 · Intercom, cửa tự động và quyền ra vào

**Nhận tin:** tách nút gọi không hoạt động, màn hình không lên, lỗi cánh/cảm biến, thẻ không được nhận hoặc tài khoản không có quyền. Xác minh người yêu cầu qua kênh an ninh; không nhận mật khẩu, mã khóa hoặc ảnh giấy tờ vào sổ tay RAG. **Chẩn đoán:** thiết bị, mạng/nguồn, cấu hình và quyền truy cập là các nhánh khác nhau, vendor phần cứng không mặc nhiên được duyệt cấp quyền.

**Thực hiện:** BQL giao kiểm tra phần thiết bị; an ninh kiểm tra phần quyền; duyệt gián đoạn nếu ảnh hưởng cửa chung; giữ phương án ra/vào và lối thoát theo quyền của tòa; vendor xử lý; an ninh cùng kỹ thuật test chức năng cần thiết. Không kết thúc vì “cửa mở được” khi cửa không đóng/khóa theo cấu hình.

**Ca `HB-EXT-06`:** cư dân không vào được sảnh nhưng thẻ khác được; nhân sự an ninh xác minh quyền đã hết hạn trong fixture. Chuyển luồng quản lý cư dân, không báo giá thay đầu đọc. Nếu sau đó xác định phần cứng hỏng, tạo work order mới đúng asset `SYN-ACCESS-01`; bảo lưu nhật ký quyền nhưng chỉ hiển thị thông tin cần thiết cho technical agent.

### EXT-07 · Bảo trì có kế hoạch và cắt dịch vụ

**Đầu vào:** hạng mục, lý do, checklist bảo trì, vendor, nguồn chi, tài sản, phạm vi căn/tiện ích, sơ đồ và phương án khi thử phục hồi thất bại. **Thực hiện:** khảo sát phạm vi; quản lý duyệt kế hoạch; thông báo; xác nhận readiness; actor ghi bắt đầu; làm việc theo phương án; thử nghiệm; phục hồi từng scope; thông báo và nghiệm thu. Nếu lịch đổi, tạo revision và lưu người nhận thông báo bản mới.

**Ca `HB-EXT-07`:** fixture có kế hoạch sửa nước và thông báo đã được duyệt. Trước khi bắt đầu, vendor báo sai vật tư: quản lý quyết định hoãn, chưa ghi `active`; gửi phương án điều chỉnh. Biến thể thứ hai: đã bắt đầu nhưng test phục hồi chưa đạt, quản lý cập nhật trạng thái và phương án hỗ trợ; UI giữ “đang gián đoạn” cho đến log phục hồi thực tế, không tự chuyển theo kế hoạch dự kiến. Chi phí theo kế hoạch được duyệt, không tự chia cho căn bị cắt nước.

### EXT-08 · Chất lượng nước bất thường

Mã tạm `EXT.WATER.QUALITY`. **[NGUỒN R26]** Một diễn tập tại chung cư Việt Nam đã mô phỏng phối hợp giữa đơn vị cấp nước, BQL và cư dân, có mẫu nước theo vị trí và thông tin kết quả trong khi chờ xác minh. Đây là ví dụ tổ chức công việc, không chứng minh tình trạng nước của tòa khác.

**[MOCK] Tiếp nhận:** màu/mùi/cặn là lời báo; ghi vòi, nước nóng/lạnh, sau lọc/trước lọc, một căn hay nhiều căn và thông báo trước đó. Không yêu cầu cư dân nếm nước để thử. Nếu lỗi máy lọc đã có mã A2 và chất lượng bất thường thì áp trigger L1 trong mục 2.3; với sự kiện toàn tòa cần chuyển BQL/chuyên trách ngay để áp policy tương ứng.

**Phiếu công việc:** (1) mở incident tổng khi scope chung được xác nhận; (2) điều phối đơn vị có chuyên môn xác định vị trí cần kiểm tra; (3) ghi mã mẫu/đơn vị kiểm tra và quyền truy xuất nếu có lấy mẫu; (4) giữ trạng thái chờ kết luận trong lúc dữ liệu chưa đủ; (5) quản lý quyết định hạn chế nguồn hoặc phương án hỗ trợ theo thẩm quyền; (6) nhân sự xử lý nguồn đã được xác định; (7) nhận kết quả xác nhận phù hợp phạm vi/mục đích sử dụng; (8) công bố tình trạng từng scope và điều kiện dùng lại. Sổ tay không đặt ngưỡng chất lượng nước hoặc tự xác nhận an toàn uống.

**Ca `HB-EXT-08`:** UI đã hiển thị “nguồn bình thường” do kết quả sensor cũ chưa được xác minh lại, nhưng hai căn vừa báo cặn. Agent lưu phản ánh mới, đánh dấu sensor cũ và chuyển incident; không xóa báo cáo vì màn hình xanh. Actor kiểm tra tạo hồ sơ kết quả mới; chưa có kết luận thì `water_use_clearance=pending`. Chi phí mẫu xét nghiệm chưa có trong bảng giá demo, nên dự toán mới cần người phụ trách ghi và phê duyệt; không lấy giá sửa ống 340000 thay thế.

### EXT-09 · Điều hòa kém lạnh, không chạy hoặc tiếng ồn

Mã tạm `EXT.HVAC.NO_COOL_NOISE`. R27 xác nhận đây là nhóm triệu chứng cần hỗ trợ riêng; chưa có mã trong 16 issue A2 hiện tại. Không ép tất cả về `TECH.HVAC.CONDENSATION` nếu không có dấu nước.

**Tiếp nhận mock:** model, phòng, biểu hiện có gió hay mất nguồn, mã lỗi nhìn thấy, điều kiện phát sinh và diễn biến tiếng bất thường, từng sửa gì, có khói/nước/mùi khét không. Phân nhánh cấu hình vận hành, nguồn điện, trao đổi nhiệt/quạt, điều khiển và hệ làm lạnh do kỹ thuật xác minh; một ảnh remote không đủ kết luận thiếu môi chất.

**Phiếu công việc:** (1) kiểm hazard; (2) đối chiếu hồ sơ máy và mã lỗi theo manual đúng model; (3) khảo sát nguyên nhân, lưu điều kiện quan sát; (4) lập phương án bảo dưỡng/sửa và bộ phận phải dừng; (5) duyệt vật tư/chi phí; (6) actor chuyên môn thực hiện; (7) thử chức năng trong điều kiện đã ghi; (8) bàn giao kết quả, hạn chế và lịch theo dõi nếu còn triệu chứng. Thao tác môi chất/điện theo nhân sự có chuyên môn, không tạo hướng dẫn tự nạp gas.

**Ca `HB-EXT-09`:** người thuê hỏi “máy không lạnh, báo giá bơm gas luôn”. Agent nhận intake và chuyển khảo sát, chưa báo giá. Actor xác nhận lỗi thuộc quạt trong fixture và warranty thiết bị cần hãng xét; quote nạp gas không được tạo từ phỏng đoán. Nếu máy phát tiếng bất thường trở lại sau sửa, liên kết lần trước và ghi điều kiện tái phát. Phí `null` đến khi có phương án đúng và quyết định warranty.

### EXT-10 · Nước mưa vào ban công/cửa ngoài hoặc nghi thấm mặt đứng

Mã tạm `EXT.ENVELOPE.RAIN_INGRESS`. Nhóm này có thể liên quan `DOOR_WINDOW`, `PAINT_MOISTURE`, `CONCEALED_LEAK` nhưng cần khảo sát nguồn ngoài và phạm vi sở hữu trước khi chọn mã chính.

**Tiếp nhận mock:** vị trí nước đầu tiên, thời điểm mưa/gió theo người báo, cửa đang đóng hay mở, miệng thoát ban công, vùng ẩm phía trong và căn dưới. Câu nói “mưa vào” không đủ phân biệt khe cửa, thoát mưa, chống thấm, nứt mặt ngoài hoặc ống cấp khác. Có kính/vật rơi, nước gặp điện hoặc nguồn ẩm tiếp diễn thì chuyển theo điều kiện tương ứng mục 2.3.

**Phiếu công việc:** (1) ghi ảnh từ vị trí an toàn và liên kết các căn liên quan có quyền; (2) quản lý phân công khảo sát cửa/thoát/chống thấm; (3) xác minh bản vẽ, ownership và quyền làm mặt ngoài; (4) duyệt biện pháp tiếp cận/vendor và phạm vi gián đoạn/khu vực; (5) xử lý đúng nguồn được xác nhận; (6) kiểm tra theo biện pháp đã được chuyên môn duyệt; (7) theo dõi trong điều kiện phù hợp và sửa hoàn thiện sau nguồn; (8) nghiệm thu theo phạm vi. Không yêu cầu cư dân trèo ra mặt đứng hoặc tự thử phun nước lên hệ điện.

**Ca `HB-EXT-10`:** cửa kính đã thay gioăng nhưng sau mưa trần ban công vẫn ẩm. Mở khảo sát mặt ngoài, giữ hồ sơ warranty lần sửa cửa; actor tìm được thêm nguyên nhân ở cấu kiện chung trong câu chuyện. Lập nguồn chi cho sửa nguồn và khôi phục riêng; không tự gán cho người thay cửa hoặc thu cả hai lần sửa. Khi mới hết mưa chưa có kết quả kiểm tra, ticket giữ theo dõi, không nghiệm thu chỉ vì bề mặt tạm khô.

## 11. Biểu mẫu, hội thoại và dữ liệu thao tác mẫu [MOCK]

### 11.1 Phiếu tiếp nhận điền sẵn — HB-08-A

```json
{
  "record_kind": "handbook_intake_fixture",
  "synthetic": true,
  "test_only": true,
  "case_run_id": "HB-08-A-RUN-01",
  "tenant_alias": "TEST-ONLY",
  "building_alias": "SYN-B-01",
  "unit_alias": "SYN-U-12",
  "ticket_alias": "SYN-TICKET-08",
  "issue_code": "TECH.PLUMB.TOILET_LEAK",
  "reporter_alias": "SYN-RES-12",
  "reporter_role": "tenant",
  "reported_text": "Bồn cầu WC phụ có tiếng nước chảy suốt, nước vào lòng bồn cả khi không dùng.",
  "observations": [
    {"key": "water_into_bowl_continuous", "value": true, "status": "reported", "source": "synthetic_resident_turn_1"},
    {"key": "wastewater_overflow", "value": false, "status": "reported", "source": "synthetic_resident_turn_2"},
    {"key": "floor_wet", "value": false, "status": "reported", "source": "synthetic_resident_turn_2"}
  ],
  "unknown_fields": ["confirmed_cause", "exact_part_model", "warranty_eligibility", "payer_consent"],
  "asset_candidates": ["SYN-WC-12"],
  "access": {"status": "requested"},
  "cost": {"mock_quote_total_vnd": null, "mock_resident_share_vnd": null, "status": "not_assessed"},
  "evidence_files_created": false,
  "approval_status": "not_published"
}
```

Alias phải được chuyển sang ID và scope thật của sandbox khi viết adapter. Fact `false` ở trên vẫn là lời báo, không tự thành xác nhận của kỹ thuật viên; nếu câu trả lời mới mâu thuẫn, thêm observation/revision và review.

### 11.2 Báo giá có revision — HB-12-A

```json
{
  "record_kind": "handbook_quote_fixture",
  "synthetic": true,
  "test_only": true,
  "quote_alias": "SYN-Q-12",
  "revision": 1,
  "case_id": "HB-12-A",
  "work_order_alias": "WO-HB12",
  "price_book": "HB-RULES-V2",
  "currency": "VND",
  "items": [
    {"code": "L-JOINERY", "quantity": 1, "unit_price_demo_vnd": 220000, "line_total_demo_vnd": 220000},
    {"code": "M-CABINET", "quantity": 2, "unit_price_demo_vnd": 110000, "line_total_demo_vnd": 220000}
  ],
  "demo_tax_vnd": 0,
  "demo_discount_vnd": 0,
  "mock_quote_total_vnd": 440000,
  "scope_included": ["Hai bộ bản lề đúng cấu hình mẫu", "Công thay và kiểm tra chức năng cánh"],
  "scope_excluded": ["Tháo và neo lại toàn bộ thân tủ", "Xử lý ẩm tường", "Thay ván tủ"],
  "cost_route_candidate": "PRIVATE_OWNER_REVIEW",
  "mock_payer_alias": "SYN-OWNER-12",
  "mock_payer_consent": {"status": "accepted", "quote_revision": 1, "actor_alias": "SYN-OWNER-12"},
  "mock_resident_share_vnd": 440000,
  "actual_invoice_id": null,
  "actual_payment_collected": false,
  "approval_status": "not_published"
}
```

Biến thể revision: khi thợ phát hiện thân tủ cần xử lý thêm, r1 vẫn là bản đã chấp thuận; tạo r2 với phạm vi/tổng mới và `consent=pending`. Đồng ý r1 không áp cho r2. Biến thể giảm số lượng: nếu thực tế chỉ thay một bộ, thợ ghi lượng dùng, tài chính mock lập điều chỉnh được người có quyền xác nhận; không thu hai bộ rồi chỉ giao một bộ mà thiếu giải thích.

### 11.3 Nhật ký đầu-cuối — HB-02-A

Mỗi sự kiện có số thứ tự bước, `event_id`, `case_run_id`, actor và object revision. Số thứ tự chỉ thể hiện trình tự storyboard, không thay thế cơ chế audit của hệ thống thật. Bảng thể hiện giá trị mới sau sự kiện, không phải lệnh để agent tự thực hiện.

| Bước | Actor mock | Sự kiện và dữ liệu mới | Trạng thái UI / điều chưa hoàn tất |
| --- | --- | --- | --- |
| 1 | Người thuê | Báo ổ bàn làm việc không có nguồn, xác định căn | `received`; chưa biết nguyên nhân. |
| 2 | Agent | Hỏi nguy cơ, vị trí, các điểm khác và lịch vào | `assessing`; câu trả lời lưu reported. |
| 3 | Lễ tân | Xác nhận liên hệ và khung hẹn với người được phép | `waiting_access`; chưa duyệt tiền. |
| 4 | Người cho phép vào | Đồng ý kế hoạch vào căn theo quyền trong fixture | `scheduled`; lưu phạm vi khảo sát. |
| 5 | Quản lý kỹ thuật | Giao `SYN-TECH-E`, tạo work order khảo sát | Có assignment; chưa có kết quả thực hiện. |
| 6 | Kỹ thuật điện | Có mặt, nhận quyền vào và xác minh asset | `in_progress`; chưa kết luận thay linh kiện. |
| 7 | Kỹ thuật điện | Biên bản fixture xác định cụm ổ riêng hỏng | Tạo phương án thay `M-SOCKET`, kiểm tra warranty. |
| 8 | Tài chính mock | Quote r1 `290000`, nguồn chi chủ căn | `waiting_approval`; số cư dân phải trả chưa chốt. |
| 9 | Chủ căn | Đồng ý quote r1, đúng phạm vi | Nguồn chi `OWNER_ACCEPTED`; chưa thực hiện sửa. |
| 10 | Agent/adapter | Tạo yêu cầu cô lập phạm vi nhánh đã xác định | Tool chỉ trả `PENDING_APPROVAL`; nguồn chưa được ghi đã cắt. |
| 11 | Quản lý kỹ thuật | Chấp thuận yêu cầu và phương án trong fixture | Đã duyệt; chưa có log thao tác thực địa. |
| 12 | Nhân sự có quyền | Xác nhận cô lập thực tế theo phương án | Log `active` cho phạm vi được xác nhận. |
| 13 | Kỹ thuật điện | Hoàn thành thay bộ tương thích, ghi kết quả/checklist | Work order vẫn đang xử lý/kiểm tra. |
| 14 | Kỹ thuật điện | Ghi kiểm tra và khôi phục nhánh theo quyền | Log phục hồi; chưa có quyết định đóng ticket. |
| 15 | Kỹ thuật điện | Gửi result, vật tư, artifact mô phỏng | `awaiting_review`; kiểm tra đủ evidence của môi trường test. |
| 16 | Verifier test | Đối chiếu kết quả và SOP/evidence seed riêng | Khuyến nghị có thể VERIFIED chỉ khi test đã seed đủ; không tự đóng. |
| 17 | Quản lý kỹ thuật | Chấp nhận bàn giao trong storyboard | `completed_by_human`; có actor/revision. |
| 18 | Tài chính mock | Xác nhận phần thanh toán theo quote r1 | Hiển thị 290000 trong demo; không phát hành hóa đơn/thu tiền thật. |

Nếu replay sự kiện ở bước 13 trùng `event_id`, adapter không tăng số lượng vật tư lần hai. Nếu sự kiện khôi phục được tiếp nhận sai thứ tự do mất mạng, UI đối chiếu liên kết sự kiện và revision; không tự thay trạng thái thực địa chỉ theo thứ tự nhận.

### 11.4 Phiếu kết quả kỹ thuật và kiểm tra thiếu hồ sơ

Mẫu điền sẵn cho HB-08-A: `work_order=WO-HB08`, asset `SYN-WC-12`, người thực hiện `SYN-TECH-W`, lý do gọi “nước vào lòng bồn liên tục”; kết luận của actor mock “phần kín nước của bộ xả hỏng”; vật tư `M-TOILET × 1`; công việc “thay phần đúng model theo phương án”; gián đoạn “nhánh cấp riêng WC phụ”; thử “nạp, giữ, xả và kiểm điểm nối theo manual”; phần tồn đọng “không có trong phạm vi ca”; đề nghị “chuyển quản lý nghiệm thu”. Không ghi số đo nếu ca không cung cấp một kết quả đo có nguồn.

| Thành phần hồ sơ | Có trong fixture đầy đủ | Thiếu thì xử lý |
| --- | --- | --- |
| Assignment và scope | Actor đúng work order/tòa | Chặn nộp hoặc trả lỗi theo contract backend, không hợp thức hóa bằng lời kể. |
| Kết luận nguyên nhân | Biên bản actor có revision | Yêu cầu bổ sung, không dùng câu trả lời LLM làm kết luận. |
| Phụ kiện thực dùng | Mã, số lượng, cấu hình đúng phương án | Chờ làm rõ chênh lệch quote/result. |
| Checklist | Từng mục có kết quả và ghi chú | `NEEDS_EVIDENCE` nếu thiếu phần bắt buộc. |
| SOP phù hợp | Test harness seed riêng tài liệu đủ điều kiện nếu muốn thử success | Thiếu/hết hiệu lực hoặc mâu thuẫn → `HUMAN_REVIEW`, không đổi nhãn sổ tay này để bypass. |
| Ảnh/biên bản | Artifact đã tồn tại, quyền đọc và scan hợp lệ trong test | Alias `SIM-EV-*` đứng một mình chưa đủ. |
| Cô lập/khôi phục | Actor, scope và kết quả | Không tự báo đã phục hồi từ thời gian dự kiến. |
| Người nghiệm thu | Quyết định quản lý có quyền | Chờ review; verifier không tự đóng ticket. |

### 11.5 Mẫu thông báo có thể dựng vào UI demo

**Tiếp nhận:** “Đã ghi nhận phản ánh {triệu_chứng} tại {vị_trí}, mã {ticket}. Cần bổ sung {dữ_kiện_còn_thiếu}. Kỹ thuật/BQL sẽ cập nhật sau khi xác nhận người phụ trách.” Nếu đã phát hiện dấu khẩn, dùng kịch bản chuyển trực của tòa, không để câu hẹn thường che đi nguy cơ.

**Hẹn vào căn:** “Dự kiến khảo sát {phạm_vi}. Người thực hiện: {nhân_sự_được_phân_công}. Vui lòng xác nhận người có thể hỗ trợ vào căn. Lịch khảo sát này chưa bao gồm đồng ý chi phí sửa chữa.”

**Xin duyệt báo giá:** “Sau khảo sát, phương án đề xuất: {phạm_vi}. Báo giá {quote}@{revision}: {tổng_demo} VND, gồm {dòng_chi_phí}; chưa gồm {ngoài_phạm_vi}. Người chịu phí dự kiến: {chủ_thể}. Phần có thu phí sẽ chờ người đúng quyền chấp thuận. Đây là báo giá mô phỏng của bản demo.”

**Bảo hành được nhận:** “Hạng mục {hạng_mục} đã được bên bảo hành chấp nhận trong hồ sơ mô phỏng {claim}. Phần công việc được nhận có số cư dân phải trả trong demo là 0 VND. Hạng mục ngoài phạm vi nếu có sẽ được báo riêng.”

**Gián đoạn có kế hoạch:** “Dự kiến tạm ngừng {dịch_vụ} tại {scope} để {lý_do}. BQL sẽ cập nhật nếu kế hoạch thay đổi. Kênh hỗ trợ: {kênh_đã_cấu_hình}. Thông báo được phát sau quyết định {approval}.”

**Gián đoạn kéo dài:** “Công việc tại {scope} đang được kiểm tra trước khi khôi phục. Chưa có xác nhận dùng lại {dịch_vụ}. Phương án hỗ trợ: {hỗ_trợ_tạm_được_duyệt}.” Chỉ thông báo khôi phục khi có xác nhận thực địa.

**Phục hồi một phần:** “Đã nhận xác nhận phục hồi {scope_đã_xong} từ {actor}. {scope_còn_lại} vẫn đang xử lý. {hạn_chế_còn_lại}.” Không dùng toàn bộ danh sách căn khác khi người nhận không có quyền xem.

**Chờ vật tư:** “Phần {phạm_vi} đang chờ {vật_tư_tương_thích}. Trạng thái hiện tại: {phần_dùng_được}, {phần_chưa_dùng_được}. BQL đang xác nhận phương án cung ứng và sẽ thông báo khi có kết quả.”

**Tranh chấp phí:** “Hiện chưa thống nhất {nguồn_hỏng/phạm_vi_sở_hữu/phạm_vi_bảo_hành}. Hồ sơ đã chuyển {người_review}; chưa có khoản phải thu được xác nhận. Việc xử lý ảnh hưởng đang theo {phương_án_đã_duyệt}.”

**Bàn giao:** “Công việc đã thực hiện: {việc_làm}; kết quả được kỹ thuật ghi nhận: {kết_quả}; phần còn chờ: {tồn_đọng}. Hồ sơ đang {trạng_thái_review}. Nếu hiện tượng xuất hiện lại, phản hồi theo mã {ticket} để liên kết lần xử lý này.”

### 11.6 Hội thoại mô phỏng các chỗ dễ xây sai

**Hội thoại A — người thuê đồng ý lịch nhưng không đồng ý tiền:**

1. Cư dân: “Tôi đồng ý cho thợ vào căn để khảo sát.”
2. Agent: “Đã ghi nhận khung hẹn khảo sát. Khi có phương án và báo giá, người có quyền thanh toán sẽ được yêu cầu xác nhận riêng.”
3. Kỹ thuật viên mock: “Hai bản lề cần thay, quote r1 tổng 440000 VND theo bảng demo.”
4. Cư dân: “Tôi thuê nhà, anh gửi chủ nhà nhé.”
5. Kết quả: `access=confirmed`, `payer_consent=pending`; chuyển quote qua kênh chủ căn đã xác minh. Không đánh quote accepted chỉ vì lịch vào đã được đồng ý.

**Hội thoại B — thay đổi scope khi đang làm:**

1. Kỹ thuật viên mock: “Phần sàn mở ra còn ẩm ở vùng kế bên, phạm vi ba tấm không đủ.”
2. Agent: “Đã ghi phát sinh. Cần kết quả xác định nguồn ẩm, phạm vi mới và dự toán revision mới trước phần thi công phát sinh.”
3. Chủ căn: “Tôi mới đồng ý ba tấm, đừng tự thay thêm.”
4. Kết quả: giữ quote r1, r2 ở trạng thái chờ; work order có phần tạm dừng và tình trạng khu vực. Phần bảo vệ vùng đang mở được actor có quyền điều phối riêng.

**Hội thoại C — phí nguồn chung và sơn trong căn:**

1. Cư dân: “Ống chung rò, vậy BQL phải sơn toàn bộ căn cho tôi?”
2. Agent: “Biên bản mock đã xác định nguồn rò chung. Phạm vi khôi phục sơn cần khảo sát phần bị ảnh hưởng và quyết định riêng; hồ sơ hiện mới ghi vùng trần liên quan.”
3. Tài chính mock: “Duyệt vùng trần trong WO-HB14, quote 500000 VND từ nguồn chi chung; ngoài vùng này chưa được duyệt.”
4. Kết quả: cư dân trả 0 cho **phạm vi đã duyệt** trong demo; không suy rộng toàn căn hoặc quyết định bồi thường tài sản khác.

**Hội thoại D — người dùng yêu cầu đóng trước khi đủ kết quả:**

1. Kỹ thuật viên mock: “Em đã thông thoát, đóng giúp ticket nhé.”
2. Agent: “Hồ sơ đang thiếu kết quả kiểm tra các khu vực bị ảnh hưởng và biên bản vệ sinh. Mình đã tạo yêu cầu bổ sung để quản lý review.”
3. Cư dân: “Nước đã rút nhưng sàn còn bẩn.”
4. Kết quả: `awaiting_review`, ghi observation mới và công việc vệ sinh còn lại; không biến lời báo “đã thông” thành xác nhận hoàn tất toàn sự cố.

### 11.7 Đối chiếu với tool hiện có của repo

| Việc trong sổ tay | Chỗ kết nối của repo | Phần cần adapter/môi trường thử nghiệm |
| --- | --- | --- |
| Đọc tài sản và lịch sử | `asset.read`, `maintenance_history.read` | Map alias sang ID đúng scope, seed inventory/historical fixture riêng. |
| Đối chiếu outage/lịch | `technical.get_active_outage`, `utility_schedule.read` | Đọc trạng thái thực của record; UI mock không tự thay enum DB. |
| Xin cô lập nước/điện | `utility_isolation.request` | Input dùng `utility_type=water` hoặc `power`, UUID scope, evidence, idempotency; chỉ trả `PENDING_APPROVAL`. |
| Xin vào căn/hạn chế khu vực/vendor | `apartment_entry.request`, `area_restriction.request`, `vendor_dispatch.request` | Request không đồng nghĩa đã vào căn, phong tỏa hay vendor đã được điều động. |
| Ghi phép đo/kết quả | `technical.record_measurement`, `technical.submit_executor_result` | Chỉ actor/harness được quyền cung cấp dữ liệu; prose không tự tạo measurement/evidence thật. |
| Đề nghị nghiệm thu | `technical.verify_resolution` | Đúng ba kết quả `VERIFIED`, `NEEDS_EVIDENCE`, `HUMAN_REVIEW`; không tự đóng hồ sơ. |
| Quote, tài chính, nhắc hẹn, thông báo và hoàn tất | Workflow dùng chung/adapter demo cần đối chiếu thiết kế | Đây không phải capability mới tự thêm vào A2 chỉ vì sổ tay có mẫu. |

### 11.8 Cách dùng phần mock để build RAG thử nghiệm

Đơn vị nội dung thích hợp là **một playbook và các nhánh của nó**, gắn `issue_code`, `synthetic=true`, `source_kind=synthetic_fixture`, `scope=TEST-ONLY`, `rulebook=HB-RULES-V2`, `approval_status=not_published`. Giữ các trường này qua mọi chunk; đừng cắt mất nhãn mock ở đầu chunk. Các passage như “khi nào tạo yêu cầu cô lập”, “cần thông tin gì để xét phí” phù hợp KB demo; mẫu quote, kết quả case và event log phù hợp fixture của workflow.

Nếu dùng 32 ca A/B để đánh giá agent, tách passage quy trình khỏi ca chứa đáp án. Các biến thể cùng gia đình `HB-xx-A/B` hoặc cùng root cause phải nằm cùng nhóm chia train/dev/test để tránh lộ đáp án. Bộ mới dùng thử luồng; nó chưa tạo ra dữ liệu sự cố thật và không đủ để đo hiệu quả ngoài thực tế. Hiện file chưa được tự đưa vào pipeline embedding nào.

## 12. Nhật ký mở rộng mock v2 [LỊCH SỬ]

Phần này lưu kết quả của bản v2, không mô tả trạng thái hiện tại của tài liệu. Bản v3 đã có 27 nguồn tham chiếu, 10 luồng mở rộng, 10 ca bổ sung và bản Word tương ứng; xem mục 0 và mục 14. Các số 22 nguồn, 7 luồng và trạng thái chưa xuất DOCX bên dưới chỉ thuộc bản v2.

Yêu cầu khi mở rộng v2: “Chi tiết hơn nữa. hãy mock đi”.

| Phần thay đổi | Kết quả cụ thể |
| --- | --- |
| Mục 3 | Mở rộng đủ 16 issue hiện có: câu hỏi tiếp nhận, bảng phân nhánh chẩn đoán, phiếu thực hiện nhiều bước, tiêu chí bàn giao và xử lý tái phát. |
| Ca `HB-01-A` → `HB-16-B` | 32 ca giả lập, gồm 16 nhánh có thể hoàn tất và 16 ngoại lệ/chờ/đổi chẩn đoán/tái phát; bổ sung vào cùng file, không thay ca JSONL cũ. |
| Mục 9 | Một tòa mẫu, hai căn, actor, hợp đồng/warranty fixture, 20 asset, quy tắc gián đoạn và bảng 23 mã giá tự đặt. |
| Kết quả phí | 16 phép tính đối chiếu, ba nhánh bảo hành/nguồn chung/chủ căn nhận phí và các nhánh chờ chưa chốt. |
| Mục 10 | Bảy luồng mở rộng có tình huống cụ thể, điều phối, khôi phục và nguồn chi. |
| Mục 11 | Intake/quote JSON, chuỗi 18 sự kiện, phiếu kết quả, 10 mẫu thông báo, 4 hội thoại và mapping tool/KB demo. |
| Phạm vi nguồn | Giữ nguyên 22 nguồn tham chiếu ở mục 1; đợt v2 bổ sung sáng tác mock, không tuyên bố có thêm SOP/biểu phí Vinhomes thật. |
| Phạm vi file ở bản v2 | Tiếp tục một file Markdown trong `operations-handbook`; khi đó chưa xuất DOCX, chưa ingest, chưa commit/push. |

**Kiểm tra bản v2:** đủ 16 mã issue khớp `general.md`; 16 phần HB-P; 32 ca A/B không thiếu/trùng; 7 ca EXT; 23 mã giá và 16 tổng dự toán/số cư dân trả khớp bảng giá; cả 3 block JSON parse hợp lệ; các ID nguồn đều có định nghĩa; file UTF-8 đọc hợp lệ. Kiểm tra này xác nhận cấu trúc và tính nhất quán của dữ liệu mock, không phải kiểm định quy trình kỹ thuật hoặc chạy tích hợp backend.

**Trạng thái bản v3:** đã có `SO_TAY_VAN_HANH_KY_THUAT.docx` với mục lục từ heading. Nếu tách tài liệu để dùng ở từng màn hình, giữ tiêu đề case, mã bộ quy tắc `HB-RULES-V2`, đơn vị VND demo, actor thực hiện và nhãn synthetic để người đọc không mất bối cảnh.

## 13. Mười ca bổ sung để khép các nhánh còn thiếu [MOCK]

Mọi ca dưới đây là fixture độc lập, dùng `case_run_id` riêng và actor tại mục 9. Quy tắc demo về số tiền giữ nguyên HB-RULES-V2. Các nhãn nghiệp vụ mới như `credit_pending` hay `handover_pending` chỉ là mô tả màn hình, không thêm enum vào backend.

### HB-ADD-01 · Máy nóng nhỏ nước: chưa đủ căn cứ thay van

**Đầu vào:** cư dân báo “bình rò”, ảnh chưa thấy điểm nước; chưa biết bình gián tiếp hay máy trực tiếp. **Đường xử lý:** hỏi vị trí/loại máy, thời điểm liên quan đun, dấu nguy hiểm; kỹ thuật xác nhận model và đối chiếu manual. Nếu đúng cơ chế xả an toàn theo manual, không lập yêu cầu bịt đầu xả hoặc tự thay van chỉ vì có giọt; nếu rò từ vỏ/đầu nối hoặc chưa xác định, tiếp tục khảo sát nhánh phù hợp. Tham khảo R24/R25 để tránh áp nhầm hai dòng máy.

**Kết quả mock:** hãng ghi nhận cần kiểm tra đường thoát của thiết bị trước khi quyết định thay linh kiện; chưa có kết luận hỏng van và chưa có báo giá. `confirmed_cause=null`, `mock_resident_share_vnd=null`. **Điểm kiểm:** lời gọi “rò” được giữ nguyên như reported symptom, không tự thành component_failure.

### HB-ADD-02 · Van được xác định lại có scope lớn hơn

**Đầu vào:** đề nghị dừng nước căn 1201 đã được duyệt, nhưng tại hiện trường actor phát hiện van dự kiến còn cấp cho căn 1301. **Diễn biến:** actor dừng bước không phù hợp; quản lý sửa scope/request revision, kiểm tra dịch vụ phụ thuộc, quyền và phương án hỗ trợ; gửi thông báo phù hợp scope mới. Request cũ có lịch sử `superseded` ở UI demo, không xóa.

**Kết quả mock:** lần cô lập đầu chưa thực hiện nên chưa có xác nhận `active`. Chỉ sau phê duyệt mới, actor mới được xác nhận thực hiện. Nếu đã phát sinh ảnh hưởng ngoài dự kiến, phải ghi sự kiện và chuyển trực; không sửa ngược scope trong hồ sơ để trông như đã được duyệt từ đầu. **Phí:** không thay đổi trách nhiệm tiền chỉ vì hai căn bị gián đoạn.

### HB-ADD-03 · Vật tư thực dùng ít hơn báo giá, cần điều chỉnh

**Đầu vào:** quote HB-12-A r1 là 440000 VND cho công 220000 và hai bộ bản lề 110000/bộ. **Diễn biến:** thợ xác nhận chỉ cần thay một bộ và chủ căn chấp nhận phạm vi sửa đã thay đổi; tài chính lập bản điều chỉnh, giữ r1 để đối chiếu. **Kết quả mock:** tổng mới `220000 + 110000 = 330000`; chênh lệch `110000` được ghi giảm phải thu nếu chưa thu, hoặc yêu cầu hoàn/đối trừ nếu trước đó đã thu trong sandbox.

Hai số `amount_due_demo` và `amount_collected_demo` phải tách biệt. Trạng thái `refund_requested` chưa là `refund_completed`; chỉ actor tài chính xác nhận giao dịch mô phỏng theo đúng thẩm quyền. **Điểm kiểm:** replay báo cáo của thợ không tạo hai lần hoàn 110000; giảm số lượng không xóa lịch sử quote được chấp thuận.

### HB-ADD-04 · Hủy sửa sau khảo sát có phí đã thỏa thuận

**Đầu vào:** chủ căn đã đồng ý riêng `F-DIAG=100000` để khảo sát ngoài bảo hành; sau kết quả, họ không đồng ý sửa. **Diễn biến:** đóng phạm vi sửa ở trạng thái hủy theo actor có quyền, ghi biên bản khảo sát đã bàn giao và đối chiếu thỏa thuận khoản khảo sát. **Kết quả mock:** chỉ 100000 là khoản xem xét thu theo thỏa thuận fixture, không cộng linh kiện/công chưa thực hiện. Nếu không có bằng chứng đã đồng ý khảo sát có phí, giữ số phải thu `null` và chuyển review.

Hủy yêu cầu sửa không tự gỡ hạn chế khu vực/nguồn nếu hiện trường chưa được người có quyền bàn giao. Cư dân đổi ý không thay thế quyết định kỹ thuật khôi phục. Không thêm phí phạt hủy mà không có policy/hợp đồng tương ứng.

### HB-ADD-05 · Nhiều ticket chung nguồn nhưng có một căn nguy hiểm hơn

**Đầu vào:** bốn lời báo cùng trục nước; một căn có nước gần đèn, ba căn chỉ mất nước. **Diễn biến:** tạo incident liên kết và chọn đầu mối thông tin; giữ bốn ticket cùng quyền xem riêng. Assessment nguy hiểm của căn thứ nhất vẫn được chuyển trực theo L1; gom nguồn không làm mất hazard hoặc đồng ý của từng căn.

**Kết quả mock:** common incident có work order nguồn, căn nguy hiểm có công việc kiểm tra/hạn chế riêng, các phần thiệt hại được theo dõi theo quyền. **Điểm kiểm:** không nhân bốn lần phí sửa trục, không dùng nghiệm thu của một căn đóng tự động cả bốn, không gửi ảnh trong căn này cho ba căn kia.

### HB-ADD-06 · Bàn giao ca khi nguồn vẫn đang cô lập

**Đầu vào:** cuối ca, work order rò nước chờ vật tư; nhánh `SYN-RISER-02` đang `active`. **Phiếu bàn giao mock:** ca đi ghi actor tiếp nhận, scope, trạng thái cô lập, lý do, approval, tình trạng thiết bị, khu vực hạn chế, vật tư còn thiếu, liên hệ vendor, thông báo gần nhất và đầu mối cập nhật tiếp. Ca đến xác nhận đã đọc/nhận; nếu chưa nhận, quản lý trực tiếp tục điều phối, không coi hết ca là hết trách nhiệm.

**Kết quả:** dịch vụ vẫn hiển thị gián đoạn, assignment được giao lại có revision. Một task “nhắc cập nhật” đến hạn không được tự đặt `restored`. Nếu ca đến phát hiện scope/hiện trường khác phiếu, tạo observation mâu thuẫn và yêu cầu xác minh trước các bước tiếp theo.

### HB-ADD-07 · Sensor cũ hoặc phép đo không có đơn vị

**Đầu vào:** dashboard có giá trị áp lực nhưng dữ liệu cũ chưa được xác minh còn phù hợp hiện trường; thợ gửi “đo được 2” không ghi đơn vị/phương pháp. **Diễn biến:** đánh dấu dữ liệu không đủ điều kiện làm bằng chứng; hỏi metric, unit, thiết bị đo, người đo và asset. Không tự chuyển 2 thành bar, kPa hay L/min và không bịa một giới hạn an toàn.

**Kết quả mock:** `measurement_usable=false`, `missing_fields=[unit, instrument_reference]` theo ca; giữ trạng thái nghiệm thu chờ. Nếu đã có đầy đủ giá trị nhưng SOP không có tiêu chí model tương ứng, chuyển `HUMAN_REVIEW`. Bản cũ được giữ để audit, bản bổ sung có revision và nguồn rõ.

### HB-ADD-08 · Vật tư thay thế không khớp model

**Đầu vào:** vendor mang một linh kiện “lắp vừa” nhưng mã khác phương án đã duyệt, không có tài liệu tương thích. **Diễn biến:** thợ ghi khác biệt, quản lý/vendor kiểm tra tài liệu; phần lắp chưa được chấp thuận giữ `waiting_parts`. Không diễn giải “cùng hãng” là tương thích hoặc tự cho rằng bảo hành còn nguyên.

**Kết quả mock:** phương án tạm và trạng thái dùng thiết bị được người phụ trách ghi riêng. Nếu vật tư mới được chuyên môn chấp thuận và làm thay đổi giá, lập quote revision/consent trước phạm vi có phí. Hồ sơ vật tư thực dùng phải khớp kết quả cuối, không sửa tên part cũ để tránh thể hiện thay đổi.

### HB-ADD-09 · Đã sửa nguồn nhưng cư dân chưa nhận phần hoàn thiện

**Đầu vào:** work order ống đã được nghiệm thu; work order sơn còn chờ màu, cư dân không đồng ý đóng ticket tổng. **Diễn biến:** backend/điều phối giữ kết quả ống ở trạng thái đã hoàn tất theo người có quyền, phần sơn vẫn mở; thể hiện lý do và lịch cập nhật. Có thể giải quyết khiếu nại thẩm mỹ bằng hồ sơ riêng nhưng liên kết parent ticket.

**Kết quả mock:** `source_repaired=true`, `finish_restoration_pending=true`, `parent_ticket_closed=false`. Không báo “chưa sửa gì” vì phần ống đã xong; cũng không báo “xử lý xong toàn bộ” khi phần sơn còn tồn. Quyết định tiền từng work order được giữ riêng theo phạm vi đã duyệt.

### HB-ADD-10 · Thông báo thất bại và chưa liên hệ được cư dân

**Đầu vào:** đã có kế hoạch cắt nước; gửi app trả lỗi, số liên hệ trong fixture không nhận máy. **Diễn biến:** lưu trạng thái từng kênh và lần gửi, retry có idempotency, chuyển lễ tân/BQL quyết định kênh thay thế theo policy; không gán `resident_notified=true` chỉ vì đã gọi hàm gửi. Với sự kiện khẩn, việc điều phối khẩn theo phương án vẫn do người trực phụ trách, không để lỗi ứng dụng tự quyết định ngừng ứng cứu.

**Kết quả mock:** `notice_delivery=failed`, `acknowledged=false`, `manual_followup_required=true`; xác nhận phục hồi vẫn chỉ từ actor thực địa. Người có quyền ghi quyết định triển khai/hoãn và căn cứ. Tin nhắn trùng không tạo incident hay khoản phí mới.

### 13.1 Sổ quyết định và hồ sơ bàn giao tối thiểu

| Quyết định | Actor ghi trong mock | Bằng chứng/đầu vào cần liên kết | Dữ liệu hiển thị |
| --- | --- | --- | --- |
| Đổi issue hoặc mức độ | Backend policy và người review khi cần | Assessment trước/sau, fact mới, policy version | Lý do thay đổi; không ghi đè phân loại cũ. |
| Đổi scope cô lập | Quản lý kỹ thuật | Sơ đồ/asset đã xác định, approval revision, notice | Phạm vi mới, hiệu lực, phạm vi đã thao tác thực tế. |
| Thay nhân sự/ca trực | Điều phối có quyền | Assignment và phiếu bàn giao | Người chịu trách nhiệm hiện tại, người tiếp nhận. |
| Thay vật tư | Chuyên môn/vendor và người duyệt | Part spec, tương thích, warranty, quote nếu đổi giá | Vật tư dự kiến/thực dùng và lý do chênh. |
| Điều chỉnh tiền | Tài chính và bên có quyền chấp thuận | Quote/result/quantity, consent, ledger sandbox | Dự toán, được duyệt, phải thu, đã thu, hoàn/đối trừ tách riêng. |
| Nghiệm thu hoặc mở lại | Người có thẩm quyền | Result, kiểm tra, bằng chứng và phần còn tồn | Quyết định theo từng work order và parent ticket. |

Không có phone/email người thật trong bộ mock. Các kênh liên hệ là alias cấu hình test; trước khi triển khai phải cung cấp danh bạ trực theo tòa và thứ tự thay thế, không dùng số điện thoại từ một dự án khác.

## 14. Kết luận dữ liệu và nhật ký v3

**Độ đầy đủ:** đủ nội dung mẫu để dựng tiếp nhận, phân loại, lập công việc, yêu cầu gián đoạn, báo giá demo, bàn giao và review theo các ca đã nêu. Chưa đủ dữ liệu thực để xác nhận SOP an toàn, giá thị trường, SLA, nghĩa vụ cư dân hoặc chất lượng vận hành của RAG. Các thiết bị/nhánh mới nằm ngoài 16 mã cần Domain Owner duyệt taxonomy nếu đưa vào sản phẩm.

**Bổ sung v3:** rà nguồn và thêm R23–R27; thêm bảng mức xử lý 16 issue; tách hai loại warranty; thêm chẩn đoán van an toàn; thêm EXT-08/09/10 và 10 ca ADD; thêm sổ quyết định; tổng kết mức sẵn sàng; xuất bản Word từ cùng Markdown. Bảng giá vẫn là 23 mã mock, không phải dữ liệu giá được crawl. Các số kiểm kê của mục 12 là lịch sử bản v2, không phải tổng cuối của v3.

**Tài liệu bàn giao:** `OPERATIONS_HANDBOOK.md` là bản nguồn; `SO_TAY_VAN_HANH_KY_THUAT.docx` là một tài liệu Word chứa toàn bộ nội dung, bảng, liên kết và mục lục. Quá trình xuất không tự nhúng tài liệu này vào RAG, không thay schema/tool và không phát sinh thông báo, phí hoặc thao tác thiết bị thật.

**Log kiểm tra và xuất bản:** kiểm kê đủ 16 mã issue và mapping Level so với `general.md`; 32 ca A/B, 10 ca ADD, 10 luồng EXT; 27 ID nguồn không có tham chiếu thiếu; 23 mã giá, 16 tổng dự toán và tỷ lệ cư dân trả khớp; ba khối JSON parse hợp lệ. Tiện ích `scripts/export_operations_handbook.py` kiểm tra các điều kiện này trước khi xuất, đối chiếu toàn bộ khối nội dung Markdown với XML của DOCX, giữ bảng và liên kết, rồi dùng Word ẩn để cập nhật mục lục/số trang. Bản PDF tạm được dùng kiểm tra bố cục, trang trống và chữ vượt biên trang; không phải tệp dữ liệu mới cần ingest. Đây là kiểm tra dữ liệu/tài liệu, chưa phải kiểm thử tích hợp ứng dụng hoặc thẩm định chuyên môn kỹ thuật. Các thay đổi đang ở workspace, chưa commit/push.

**Điều chỉnh bản trình bày:** loại bỏ mốc ngày/giờ, ngày biên soạn/rà soát, mốc bảo hành và thời lượng giả lập; bỏ các trường timestamp khỏi schema minh họa và JSON; đổi bảng diễn biến sang 18 bước đánh số; giữ nguyên URL nguồn để bảo toàn truy xuất. Bản Word được xuất lại từ Markdown, loại metadata ngày tạo/sửa/in và cập nhật mục lục. Nội dung kỹ thuật, phân biệt nguồn/mock, quyền phê duyệt và phép tính báo giá vẫn được giữ; không thay schema, dữ liệu hoặc hành vi ứng dụng.

**Đồng bộ riêng Markdown với bản Word v3:** bổ sung nhãn phiên bản và tóm tắt đầu tài liệu theo trang bìa Word; sửa cách diễn đạt còn gọi tài liệu hiện tại là v2; đánh dấu mục 12 là nhật ký lịch sử. Không đổi mã `HB-RULES-V2`, quy trình, tình huống, JSON mẫu, bảng giá hoặc nguồn tham chiếu. Lần điều chỉnh này chỉ sửa Markdown, không xuất lại hay sửa file Word và không đưa ngày/giờ trở lại tài liệu.
