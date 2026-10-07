---
trang_thai: du-lieu-gia-lap-khong-xuat-ban
cap_nhat: 2026-10-05
van_ban: MOCK-PROC-COLLECTION-v1
fixture_only: true
approval_status: not_published
sop_available: false
audience: technician_test_only
version: mock-v1
---
# MOCK-PROC-COLLECTION — 16 quy trình kỹ thuật giả lập

Bộ fixture phục vụ thử RAG và luồng A2. Đây không phải SOP Vinhomes, không được dùng để hướng dẫn cư dân thao tác hay vận hành thật. Mỗi phần có mã sự cố, nhánh xử lý, yêu cầu chứng cứ và hậu kiểm riêng.

## MOCK-PROC-01 — Quy trình mẫu: CB nhảy lặp

**Issue code:** `TECH.ELEC.BREAKER_TRIP`

MẪU GIẢ LẬP để thử RAG và luồng A2; không phải SOP Vinhomes, không được hướng dẫn cư dân thao tác điện. Chỉ mô tả điểm quyết định và hồ sơ mà kỹ thuật viên có thẩm quyền cần ghi.

### Tiếp nhận và điều kiện dừng
Ghi ticket, building đã xác minh, nhánh hay CB tổng, số lần và thời điểm nhảy, thiết bị đang dùng, phạm vi một căn hay nhiều căn. Hỏi rõ khói, tia lửa, mùi khét, vỏ nóng, điện giật và nước gần điện; giá trị chưa biết phải lưu `unknown`. Có bất kỳ dấu hiệu nguy hiểm nào thì chuyển người trực ngay, giữ nguyên hiện trạng và không yêu cầu cư dân đóng CB thử. Nếu chưa có người đủ quyền hoặc chưa xác định asset/ownership thì không mở work order thao tác.

### Kiểm tra có kiểm soát
Người điều phối đối chiếu outage và lịch sử nhánh cấp; `asset.read` xác định panel/CB thuộc căn hay phần chung và model thực tế. SOP/manual đúng asset còn hiệu lực là điều kiện trước khi kỹ thuật viên khảo sát. Kỹ thuật viên ghi nhận tình trạng tại hiện trường, xác nhận phạm vi cô lập qua quy trình phê duyệt riêng nếu cần; công cụ `utility_isolation.request` chỉ tạo yêu cầu chờ duyệt, không cắt điện. Chẩn đoán quá tải, lỗi thiết bị hay lỗi dây phải dựa trên phép đo và biên bản của người có chuyên môn, không suy từ lời kể.

### Work order và xác minh
Work order liên kết ticket, asset, assignment, checklist an toàn, kết quả đo có metric/unit/measured_at/by và evidence trước/sau đúng ticket. `technical.submit_executor_result` ghi việc thực hiện, vật tư và thử chức năng theo SOP đúng model; mọi kết quả thiếu hoặc mâu thuẫn trả `NEEDS_EVIDENCE` hoặc `HUMAN_REVIEW`. `technical.verify_resolution` chỉ khuyến nghị, người có quyền mới xác nhận hoàn tất; không tự đóng ticket. Không gán ngưỡng dòng điện hoặc thời gian thử từ mẫu này.

### Tình huống phân nhánh
- Một CB nhảy khi bật thiết bị: ghi số lần, vị trí CB, thiết bị liên quan và thời điểm; chưa kết luận quá tải hay hỏng dây. Không yêu cầu cư dân bật lại để tái hiện.
- Có mùi khét, tia lửa, vỏ nóng, điện giật hoặc nước gần điện: chuyển người trực ngay, không chờ ảnh và không hướng dẫn thao tác tủ điện.
- Nhiều căn cùng mất điện: đối chiếu outage đúng tòa và sơ đồ cấp điện theo quyền; dữ liệu outage cũ hoặc mâu thuẫn phải được xác minh bởi người trực.

### Hồ sơ tối thiểu và hậu kiểm
Ticket cần nguồn của từng dữ kiện, thời điểm, phạm vi, trạng thái nguy hiểm true/false/unknown. Work order cần asset, model, owner, người được giao và SOP còn hiệu lực. Kết quả khảo sát phải có phép đo kèm metric, unit, measured_at, measured_by, dụng cụ và điều kiện đo; ảnh trước/sau phải đúng ticket và là file đã kiểm tra. Thiếu quyền, SOP, phép đo hoặc kết quả mâu thuẫn thì không xác nhận đã sửa. Thử chức năng và tiêu chí đạt phải lấy từ SOP đúng model; mẫu này không đặt ngưỡng dòng điện hay số lần thử.

### Nguồn
- MOCK-PROC-01-v1: fixture thiết kế từ docs/teams/quang/general.md mục 10.1 và technical-data/POC_WORKFLOWS.md POC 1; không phải văn bản BQL.

---

## MOCK-PROC-02 — Quy trình mẫu: đèn, ổ cắm, công tắc không hoạt động

**Issue code:** `TECH.ELEC.FIXTURE_FAILURE`

MẪU GIẢ LẬP chỉ cho kiểm thử nội bộ; không phải SOP Vinhomes hay hướng dẫn cư dân sửa điện.

### Tiếp nhận và chặn nguy cơ
Ghi đúng vị trí điểm hỏng, trong căn hay khu chung, một điểm hay cả nhánh, thời điểm bắt đầu và thiết bị khác bị ảnh hưởng. Hỏi về nóng, cháy xém, tiếng nổ, tia lửa, nước/ẩm gần điểm điện và đèn thoát hiểm. Khi có dấu hiệu điện nguy hiểm hoặc lối thoát thiếu chiếu sáng, chuyển người trực và bảo đảm quy trình an toàn khu vực do nhân viên thực hiện; không bảo cư dân tháo mặt ổ hoặc thử dây.

### Khảo sát và quyết định
Đối chiếu outage, bản đồ mạch nếu được cấp quyền, asset fixture/panel và lịch sử sửa. Nếu nhiều điểm cùng mất thì mở incident phạm vi chung; nếu chỉ một fixture thì ghi asset riêng. Kỹ thuật viên được phân công kiểm tra theo SOP/manual đúng loại thiết bị, ghi phép đo hợp lệ nếu SOP đòi hỏi; kết quả đo không có người/thiết bị/đơn vị là không hợp lệ. Việc cô lập điện hoặc hạn chế lối đi phải qua yêu cầu phê duyệt, không suy rằng đã thực thi khi trạng thái còn pending.

### Kết quả và evidence
Executor result phải chỉ ra điểm lỗi đã xác nhận, bộ phận được sửa/thay, checklist an toàn, ảnh trước/sau có quyền đọc và thử chức năng sau xử lý. Nếu đèn thoát hiểm liên quan, cần người có quyền nghiệm thu khả năng sử dụng lối thoát; ảnh bóng sáng đơn lẻ không đủ. Thiếu bằng chứng trả `NEEDS_EVIDENCE`; nguyên nhân chưa khớp kết quả hoặc vùng ảnh hưởng chưa được xử lý trả `HUMAN_REVIEW`. Không đóng ticket tự động.

### Tình huống phân nhánh
- Một đèn không sáng: hỏi lỗi chỉ ở bóng, phòng hay nhiều ổ; ghi thời điểm và trạng thái CB. Không đoán bóng hỏng.
- Ổ nóng, sẫm màu, có tia lửa hoặc mùi khét: chuyển người trực ngay; không đề nghị chạm, tháo ổ hay cắm thiết bị khác để thử.
- Lỗi tái phát sau sửa: liên kết work order cũ để đối chiếu, nhưng hồ sơ cũ không thay thế chứng cứ của lần này.

### Hồ sơ tối thiểu và hậu kiểm
Ghi nhãn/vị trí asset, triệu chứng cụ thể, có người bị điện giật hay không, ảnh tự nguyện và thời điểm. Xác minh owner, quyền vào căn, manual/SOP và vật tư phù hợp trước công việc. Người được giao ghi nguyên nhân được kiểm chứng, kết quả đo, mã vật tư, ảnh trước/sau cùng ticket. Hậu kiểm phải tách triệu chứng ban đầu, thao tác thực hiện và kết quả thử theo SOP. Nếu vẫn nóng, vẫn mùi khét, thiếu đo hoặc cư dân báo tái phát thì chuyển đánh giá người, không đóng ticket.

### Nguồn
- MOCK-PROC-02-v1: fixture thiết kế từ docs/teams/quang/general.md mục 10 và technical-data/ISSUE_CATALOG.md mục 02; không phải văn bản BQL.

---

## MOCK-PROC-03 — Quy trình mẫu: máy nước nóng không nóng hoặc rò

**Issue code:** `TECH.PLUMB.WATER_HEATER`

MẪU GIẢ LẬP cho kỹ thuật viên kiểm thử; không phải SOP Vinhomes. Không hướng dẫn cư dân mở nắp, thử điện, thử gas hoặc tự sửa thiết bị.

### Intake và phân luồng
Ghi model, loại cấp năng lượng, vị trí rò, mã lỗi/đèn báo, không nóng hay nóng yếu, một vòi hay toàn căn, ngày lắp/bảo trì nếu có. Hỏi nước gần điện, mùi gas, khói, vỏ nóng, bỏng hoặc rò mạnh. Dấu hiệu nguy hiểm chuyển người trực và nhân viên có chuyên môn phù hợp; trường chưa rõ lưu `unknown`, không coi là an toàn.

### Xác định nguồn và quyền thao tác
`asset.read` trả đúng model, ownership, bảo hành và manual version; kiểm tra outage điện/nước, lịch sử và sự cố liên quan. Nếu không có manual/SOP đúng model, dừng hướng dẫn kỹ thuật chi tiết và yêu cầu chuyên gia. Kỹ thuật viên xác định điểm lỗi bằng phép kiểm tra được SOP cho phép, phân biệt nguồn cấp, bộ gia nhiệt, van/đường ống và nguồn nước chung. Bất kỳ cô lập nguồn nào phải theo approval thật; request pending không có nghĩa nguồn đã cô lập.

### Hồ sơ hoàn tất
Work order giữ assignment, checklist thao tác an toàn, vật tư đúng model, ảnh trước/sau và số đo nhiệt độ/lưu lượng nếu SOP yêu cầu với đơn vị, người đo và thời điểm. Thử chức năng sau sửa theo điều kiện được phê duyệt; theo dõi điểm rò thay vì chỉ ghi “đã nóng”. Evidence thiếu hoặc mâu thuẫn thì `NEEDS_EVIDENCE`/`HUMAN_REVIEW`; chỉ người được ủy quyền xác nhận kết quả cuối. Không dùng ngưỡng nhiệt độ từ fixture này.

### Tình huống phân nhánh
- Nước không nóng: hỏi model, nguồn cấp, thời điểm bắt đầu, một hay nhiều điểm dùng; không suy ngay bộ gia nhiệt hỏng.
- Rò nước, mùi khét hoặc cảm giác tê điện: chuyển người trực an toàn; không hướng dẫn mở vỏ, sửa điện hoặc vận hành thử.
- Thiết bị thuộc nhà cung cấp/bảo hành: xác minh owner và phạm vi can thiệp; work order có thể là khảo sát hoặc chuyển vendor, không mặc định được sửa.

### Hồ sơ tối thiểu và hậu kiểm
Lưu model/serial nếu có thể cung cấp an toàn, vị trí lắp đặt, dấu hiệu nước/điện, các điểm dùng bị ảnh hưởng. Asset record và hợp đồng xác nhận ai có quyền sửa. Kỹ thuật viên ghi SOP đúng model, quyền cô lập, phép đo hợp lệ, nguyên nhân đã kiểm chứng, vật tư và ảnh trước/sau. Booking vendor ở trạng thái pending không phải lịch đã xác nhận. Chỉ đề xuất hoàn tất khi thử chức năng theo SOP, evidence đúng ticket và người có quyền nghiệm thu; không đặt nhiệt độ hoặc thời gian thử giả định.

### Nguồn
- MOCK-PROC-03-v1: fixture thiết kế từ docs/teams/quang/general.md và technical-data/ISSUE_CATALOG.md mục 03; không phải văn bản BQL.

---

## MOCK-PROC-04 — Quy trình mẫu: máy lọc nước chảy yếu

**Issue code:** `TECH.PLUMB.WATER_FILTER_LOW_FLOW`

MẪU GIẢ LẬP cho kiểm thử nội bộ, không phải SOP Vinhomes hoặc khuyến nghị chất lượng nước uống.

### Thu thập dữ kiện
Ghi lưu lượng yếu tại vòi lọc hay mọi vòi, model máy/lõi, thời điểm thay lõi, tình trạng bơm/van theo lời báo và ảnh vị trí rò nếu có. Nước đổi màu, mùi bất thường hoặc nghi nhiễm bẩn là tín hiệu chuyển người kiểm tra chất lượng; không khẳng định nước uống an toàn. Nước gần điện hoặc rò lan phải ưu tiên an toàn trước chẩn đoán.

### Kiểm tra và xử lý có thẩm quyền
Tra outage nguồn nước, asset/model/manual đúng loại lõi, lịch sử thay và yêu cầu bảo hành. Kỹ thuật viên đo lưu lượng/áp lực trước xử lý nếu quy trình thiết bị quy định, ghi metric, unit, measured_at, thiết bị và người đo. Phân biệt nguồn cấp chung yếu, tắc lõi, van hoặc ống gập; không kết luận “phải thay lõi” từ triệu chứng đơn lẻ. Việc thay vật tư hay can thiệp bơm chỉ do người đủ quyền theo manual thực hiện, ghi mã vật tư và lý do.

### Kiểm chứng
Ghi phép đo sau xử lý cùng điều kiện so sánh, thử rò quanh đầu nối, nhật ký thay lõi và ảnh trước/sau. Nếu không có tiêu chí lưu lượng của đúng model, chỉ ghi kết quả quan sát và yêu cầu người có chuyên môn kết luận; không tự đặt ngưỡng. Cần bằng chứng chất lượng nước riêng khi có khiếu nại về nước uống. `technical.verify_resolution` không tự đóng ticket.

### Tình huống phân nhánh
- Lưu lượng giảm: hỏi mốc thay lõi, nguồn đầu vào, chỉ vòi sau lọc hay nhiều vòi; không suy lõi bẩn.
- Nước có mùi/màu lạ hoặc rò gần điện: ngừng dùng để uống và chuyển đánh giá phù hợp; không tuyên bố nước độc hay an toàn từ lời kể.
- Nhà cung cấp quản lý máy: kiểm tra bảo hành trước thay linh kiện, tạo yêu cầu phối hợp nếu cần.

### Hồ sơ tối thiểu và hậu kiểm
Ghi model/serial, điểm cấp nước, mùi/màu/vị, thời điểm và ảnh. Liên kết lịch bảo trì với ticket nhưng không dùng maintenance cũ như chẩn đoán. Kỹ thuật viên ghi phép đo lưu lượng/áp lực theo phương pháp đã duyệt, tình trạng lõi/đường nước, vật tư và ảnh. Phải tách nghiệm thu chức năng thiết bị khỏi đánh giá chất lượng nước. Nước chảy mạnh trở lại không chứng minh uống an toàn; thiếu xét nghiệm/phê duyệt khi có nghi ngờ thì vẫn cần người có chuyên môn đánh giá.

### Nguồn
- MOCK-PROC-04-v1: fixture thiết kế từ technical-data/ISSUE_CATALOG.md mục 04 và docs/teams/quang/general.md; không phải văn bản BQL.

---

## MOCK-PROC-05 — Quy trình mẫu: điều hòa chảy nước

**Issue code:** `TECH.HVAC.CONDENSATION`

MẪU GIẢ LẬP để chạy POC A2; không phải SOP Vinhomes hay hướng dẫn cư dân tự sửa.

### Tiếp nhận và dừng nguy cơ
Ghi asset/model dàn lạnh, nơi nước xuất hiện, thời điểm khi chạy máy, mức lan, ảnh trước và căn dưới nếu có. Hỏi nước gần ổ/đèn, trần võng/rơi, rò lan nhiều căn. Có nguy cơ điện hoặc trần rơi thì chuyển người trực, không chờ ảnh và không yêu cầu cư dân mở dàn lạnh. Trường điện chưa biết giữ `unknown`.

### Điều tra có kiểm soát
Đối chiếu asset, manual đúng model, bảo trì gần nhất, incident thấm trần và outage nước/điện nếu liên quan. Kỹ thuật viên phân biệt nước ngưng từ khay/ống với nguồn thấm khác; chỉ theo SOP hợp lệ mới kiểm tra đường thoát, khay và tình trạng thiết bị. Evidence ảnh trước phải có file/object ID, captured_at, ticket/work order và trạng thái scan/quyền phù hợp. Đo `drain_flow` nếu manual yêu cầu, gồm value, `L/min`, measured_at/by và nguồn thiết bị; LLM không tạo số đo.

### Work order và nghiệm thu
Executor result ghi chẩn đoán xác nhận, checklist, việc làm, vật tư, số đo và ảnh sau. Thử hoạt động theo manual/model và ghi quan sát tại thời điểm thử, bao gồm khu vực từng ướt và căn dưới nếu có quyền kiểm tra. Nước còn gần điện hoặc ảnh chưa sẵn sàng thì không xác minh. Thiếu ảnh/checklist trả `NEEDS_EVIDENCE`; nguồn nước chưa rõ hoặc mâu thuẫn trả `HUMAN_REVIEW`. `VERIFIED` là khuyến nghị, không đóng ticket.

### Tình huống phân nhánh
- Dàn lạnh nhỏ nước: hỏi thời điểm, chế độ vận hành, vị trí chảy và căn dưới có bị ảnh hưởng không; không kết luận tắc ống.
- Nước gần ổ điện hoặc trần võng: chuyển người trực khẩn; không yêu cầu cư dân mở dàn lạnh hoặc tháo trần.
- Rò tái phát sau vệ sinh: đối chiếu work order và model; xem đường thoát, lắp đặt, đọng sương là giả thuyết cần kiểm chứng.

### Hồ sơ tối thiểu và hậu kiểm
Ticket cần vị trí, phạm vi ướt, dấu hiệu điện/trần và ảnh; dữ kiện căn dưới để unknown nếu chưa xác minh. Asset xác định dàn lạnh, model, owner. Kỹ thuật viên ghi khảo sát theo SOP, phép đo có đơn vị/phương pháp và evidence trước/sau đúng ticket. Muốn vào căn khác phải có grant riêng. Hậu kiểm tại điểm rò cũ theo điều kiện/thời gian của SOP thật; số đo fixture không phải chuẩn an toàn. Thiếu ảnh sau, SOP hoặc nguồn nước chưa rõ thì giữ mở.

### Nguồn
- MOCK-PROC-05-v1: fixture thiết kế từ technical-data/POC_WORKFLOWS.md POC 2 và ISSUE_CATALOG.md mục 05; không phải văn bản BQL.

---

## MOCK-PROC-06 — Quy trình mẫu: rò âm tường hoặc thấm trần

**Issue code:** `TECH.PLUMB.CONCEALED_LEAK`

MẪU GIẢ LẬP cho POC A2, không phải SOP Vinhomes. Không quy trách nhiệm cho căn khác từ vị trí vết ố.

### Intake, phạm vi và nguy cơ
Ghi vị trí, lần quan sát đầu, ảnh theo thời gian, tốc độ lan, dấu trần mềm/võng/rơi, điện quanh vùng ẩm và căn/tầng có thể liên quan. Nước gần điện hoặc thấm nhanh nhiều căn phải chuyển người trực. Ticket chỉ ghi “nguồn chưa xác định” cho đến khi có kết quả kiểm tra; thông tin từ căn lân cận phải được kiểm tra quyền trước khi đọc. Nếu cần vào căn khác, `apartment_entry.request` chỉ trả `PENDING_APPROVAL`, không biểu thị đã được vào.

### Điều tra và quyết định
Đối chiếu incident cùng building, lịch sử ống/nước ngưng/chống thấm, outage, ảnh gốc và vị trí asset. Kỹ thuật viên được phân công ghi phép đo độ ẩm theo điểm đo, unit, thiết bị, measured_at và người đo; so sánh theo cùng phương pháp khi theo dõi. Mọi đề xuất cô lập nước hoặc mở kết cấu cần approval/work order và chuyên môn đúng phạm vi. Nếu hai nguồn thông tin mâu thuẫn, lưu cả provenance và chuyển `HUMAN_REVIEW`, không chọn một nguồn bằng độ giống RAG.

### Hồ sơ xử lý và hậu kiểm
Work order ghi chẩn đoán được xác nhận, ảnh trước, phạm vi can thiệp, vật tư, ảnh sau, số đo sau xử lý và lịch theo dõi tái ẩm. Nếu nguồn liên quan căn khác, evidence chỉ được liên kết khi đúng consent/ACL; quyền bị thu hồi thì không tiếp tục truy cập. Không nghiệm thu chỉ vì đã sơn/che vệt ố. `technical.verify_resolution` yêu cầu bằng chứng xử lý nguồn và không tái rò theo SOP thật; thiếu bằng chứng trả `NEEDS_EVIDENCE`, chưa rõ nguồn trả `HUMAN_REVIEW`.

### Tình huống phân nhánh
- Vệt ố lan theo ngày: lưu ảnh theo thời gian, vị trí, mốc mưa/sử dụng nước; không quy trách nhiệm cho căn trên chỉ từ tương quan.
- Trần võng, nước gần điện hoặc rơi vật liệu: chuyển người trực trước khi đo đạc.
- Cần vào căn liền kề: tạo request đúng căn; pending không phải được phép. Nếu grant bị thu hồi, dừng mọi truy cập liên căn.

### Hồ sơ tối thiểu và hậu kiểm
Ghi sơ đồ vệt, hướng lan, ảnh từng thời điểm và người quan sát. Mỗi phép đo ẩm cần vị trí điểm đo, dụng cụ, đơn vị, thời gian, người đo, điều kiện bề mặt; một phần trăm đơn lẻ không chỉ ra nguồn rò. Tách giả thuyết khỏi facts, giữ cả hai nguồn nếu mâu thuẫn. Work order khảo sát không phải đã sửa. Sau khi nguồn được chuyên môn xác nhận, tách biên bản xử lý nguồn với phục hồi trần/tường và theo dõi tái ẩm; không nghiệm thu sơn khi vẫn thấm.

### Nguồn
- MOCK-PROC-06-v1: fixture thiết kế từ technical-data/POC_WORKFLOWS.md POC 3 và ISSUE_CATALOG.md mục 06; không phải văn bản BQL.

---

## MOCK-PROC-07 — Quy trình mẫu: vách tắm hở hoặc rò

**Issue code:** `TECH.PLUMB.SHOWER_SEAL`

MẪU GIẢ LẬP để thử luồng kỹ thuật; không phải SOP Vinhomes hay hướng dẫn cư dân tự trám khe.

### Nhận diện và điều kiện dừng
Ghi vị trí mép vách, ngưỡng, chân kính, mạch tường và thời điểm nước xuất hiện; ảnh toàn cảnh và cận cảnh cùng mã ticket. Hỏi khung/kính lỏng, nguy cơ trượt ngã, nước gần điện hoặc thấm xuống căn dưới. Kính có nguy cơ rơi hoặc nước lan phải chuyển người đánh giá khu vực, không tiến hành thử nước tùy tiện.

### Khảo sát và thực hiện
Xác định model vách/phụ kiện, loại gioăng hoặc vật liệu theo manual và bảo hành. Kỹ thuật viên kiểm tra đường nước thực sự: mép vách, độ kín, thoát sàn và nguồn rò khác. Chỉ sau khi định vị nguồn mới lập work order vật tư và phạm vi xử lý; không mặc định mọi rò do silicone. Nếu cần vào khu vực khác, dùng approval và scope tương ứng. Ghi nguyên trạng, nguyên nhân xác nhận, vật tư và người thực hiện.

### Kiểm tra kết quả
Thử nước có kiểm soát theo SOP/manufacturer, ghi điều kiện thử, vị trí quan sát và ảnh sau; kiểm tra cả sàn ngoài vách và khu vực dưới nếu có quyền. Tiêu chí khô/không rò phải do SOP đúng model quy định. Nếu rò vẫn xuất hiện hoặc ảnh không đúng ticket, trả `NEEDS_EVIDENCE`/`HUMAN_REVIEW`; không kết luận chỉ từ một góc ảnh.

### Tình huống phân nhánh
- Nước tràn khi tắm: ghi mép/khe, điểm xuất hiện giọt đầu, thời điểm, sàn trơn và kính có nứt không; không mặc định keo silicone hỏng.
- Kính nứt hoặc phụ kiện lung lay: chuyển người trực, hạn chế sử dụng; không hướng dẫn tự tháo/siết kính.
- Đã trám nhưng rò tái phát: phân biệt vách, ống cấp/thoát và sàn bằng khảo sát phù hợp, không sao chép chẩn đoán cũ.

### Hồ sơ tối thiểu và hậu kiểm
Ghi model/cấu tạo, vị trí cửa, khe nghi rò, ảnh, phạm vi ướt và bảo hành. Kỹ thuật viên dùng phương pháp được SOP/manual cho phép, ghi điểm rò quan sát được, vật tư tương thích và người thực hiện. Không tự đặt thời gian khô keo hoặc cách thử ngâm cho mọi model. Hậu kiểm phải quan sát điểm rò cũ trong điều kiện được phê duyệt; thiếu kết quả thử hoặc nguồn chưa xác định thì không hoàn tất.

### Nguồn
- MOCK-PROC-07-v1: fixture thiết kế từ technical-data/ISSUE_CATALOG.md mục 07 và docs/teams/quang/general.md; không phải văn bản BQL.

---

## MOCK-PROC-08 — Quy trình mẫu: bồn cầu rỉ hoặc chảy liên tục

**Issue code:** `TECH.PLUMB.TOILET_LEAK`

MẪU GIẢ LẬP cho kiểm thử A2, không phải SOP Vinhomes.

### Thu thập và phân biệt triệu chứng
Ghi nước rò ra sàn hay chảy trong lòng bồn, có tràn/nước bẩn không, tiếng nước liên tục, vị trí cấp/thoát và model nếu biết. Hỏi nước gần điện, sàn trơn, căn dưới bị ảnh hưởng và vật liệu bồn có nứt hay không. Nước thải tràn thì chuyển sang luồng `TECH.PLUMB.SEWAGE_BACKFLOW`; nước rò mạnh hoặc gần điện thì chuyển người trực.

### Khảo sát đúng asset
Kỹ thuật viên đối chiếu model và manual, ảnh vị trí cấp/thoát, lịch sử thay linh kiện. Phân biệt van cấp, bộ xả, đầu nối, chân bồn và đường thoát bằng quan sát/kiểm tra được phép; không thay gioăng chỉ vì sàn ướt. Work order ghi chẩn đoán, nguồn nước sạch hay thải, vật tư tương thích và tình trạng trước xử lý. Nếu cần cô lập nước chung, request chỉ pending cho tới khi có phê duyệt.

### Nghiệm thu và theo dõi
Executor result có checklist, thử xả có giám sát theo SOP, ảnh/số đo nếu yêu cầu, ghi sàn và điểm nối sau thử. Cần tách tiêu chí “nước ngừng chảy trong lòng bồn” và “không còn rò ra sàn”; đạt một tiêu chí không chứng minh tiêu chí kia. Bằng chứng sai ticket hoặc thiếu thử lại dẫn tới `NEEDS_EVIDENCE`; nguồn rò chưa rõ dẫn tới `HUMAN_REVIEW`.

### Tình huống phân nhánh
- Nước rỉ liên tục trong lòng bồn: hỏi âm thanh cấp nước, rò sau xả hay liên tục; phân biệt với nước rò ra sàn.
- Rò tại chân bồn hoặc nước thải ra nền: đánh dấu nguy cơ vệ sinh, tránh tiếp xúc và chuyển kỹ thuật viên. Trào nhiều điểm cần xét nhánh thoát chung.
- Nhiều căn cùng báo: đối chiếu đường thoát và sự cố chung theo quyền; không thay linh kiện từng bồn trước khi xác định phạm vi.

### Hồ sơ tối thiểu và hậu kiểm
Ticket lưu vị trí rò, màu/mùi nước, thời điểm và ảnh. Xác minh asset và owner. Kỹ thuật viên ghi chẩn đoán, vật tư, phép thử và evidence đúng ticket theo SOP. Nếu nghi nước thải, phương án vệ sinh/khử nhiễm cần được người có quyền duyệt; không trộn với rò nước sạch. Đối chiếu vị trí rò cũ trong điều kiện thử được duyệt và ghi nhận tái phát; một ảnh sàn khô không đủ để xác minh.

### Nguồn
- MOCK-PROC-08-v1: fixture thiết kế từ technical-data/ISSUE_CATALOG.md mục 08 và docs/teams/quang/general.md; không phải văn bản BQL.

---

## MOCK-PROC-09 — Quy trình mẫu: mùi cống hoặc bẫy nước

**Issue code:** `TECH.PLUMB.TRAP_ODOR`

MẪU GIẢ LẬP cho kiểm thử nội bộ; không phải SOP Vinhomes. Mùi chưa rõ nguồn không được mặc định là cống.

### Tiếp nhận và an toàn
Ghi vị trí/mốc giờ mùi, drain liên quan, phạm vi một căn hay nhiều căn, thoát chậm/trào nước thải, triệu chứng sức khỏe và điều kiện thông gió. Hỏi tách biệt mùi gas, khói và mùi nước thải; nghi gas hoặc nhiều người khó chịu thì chuyển người trực theo quy trình khẩn có thẩm quyền. Không bảo cư dân mở hố ga, trục kỹ thuật hoặc tiếp xúc nước bẩn.

### Kiểm tra và xác minh nguồn
Đối chiếu incident/outage cùng building, sơ đồ hệ thoát được cấp quyền, lịch sử sửa và ảnh/ghi nhận hiện trường. Kỹ thuật viên phân biệt bẫy nước, ống thông hơi, tắc đường thoát hoặc nguồn ngoài khu vệ sinh; nếu không có bằng chứng thì giữ diagnosis `unknown`. Work order ghi điểm kiểm tra, phép thử được SOP cho phép, kết quả và tình trạng trước xử lý. Không dùng kết quả RAG để khẳng định nồng độ khí hoặc an toàn sức khỏe.

### Hậu kiểm
Ghi việc đã làm, thử thoát và quan sát mùi theo thời gian do SOP phê duyệt, thời điểm và người xác nhận. Nếu mùi tái xuất hiện, ảnh hưởng nhiều căn hoặc nguồn chưa chắc, mở review/điều tra mở rộng; không đóng sự cố chỉ vì lúc kiểm tra không còn mùi. Thiếu evidence thì `NEEDS_EVIDENCE`, chẩn đoán xung đột thì `HUMAN_REVIEW`.

### Tình huống phân nhánh
- Mùi thoát nước từng lúc: hỏi vị trí, thời gian, điểm thoát ít sử dụng, nhiều căn cùng bị hay không; không suy ngay bẫy nước khô hoặc tắc ống.
- Mùi nghi khí gas, chóng mặt, khó thở hoặc trào nước thải: không gộp vào ca mùi cống thông thường; chuyển người trực khẩn theo quy trình an toàn phù hợp.
- Mùi quay lại sau vệ sinh: so khớp ticket cũ, lịch sự cố hệ thống chung và điều kiện xuất hiện; không lấy kết luận cũ thay khảo sát mới.

### Hồ sơ tối thiểu và hậu kiểm
Ghi khu vực phát mùi, thời điểm, tần suất, ảnh/ghi chú nếu có, triệu chứng sức khỏe và phạm vi nhiều căn. Asset có thể là siphon, điểm thoát hoặc tuyến chung nhưng phải xác định trước khi tác nghiệp. Kỹ thuật viên ghi kết quả khảo sát, nguyên nhân được xác minh, hạng mục đã xử lý, điều kiện thử theo SOP, chứng cứ trước/sau và kế hoạch theo dõi. Mùi không cảm nhận được tại một thời điểm không chứng minh nguồn đã xử lý. Không khuyên cư dân đổ hóa chất hoặc tự mở đường cống.

### Nguồn
- MOCK-PROC-09-v1: fixture thiết kế từ technical-data/ISSUE_CATALOG.md mục 09 và docs/teams/quang/general.md; không phải văn bản BQL.

---

## MOCK-PROC-10 — Quy trình mẫu: nước yếu, thoát chậm hoặc rò đầu nối

**Issue code:** `TECH.PLUMB.SUPPLY_DRAIN_JOINT`

MẪU GIẢ LẬP cho POC; không phải SOP Vinhomes. Ba nhóm triệu chứng này phải được tách trong assessment dù cùng một issue code.

### Intake và phạm vi
Ghi nhánh `low_supply`, `slow_drain` hoặc `joint_leak`, điểm xuất hiện, thời điểm, một thiết bị hay nhiều căn, mức nước lan và ảnh. Hỏi nước bẩn/trào, nước gần điện, rò liên tục hay mất nước diện rộng; có nguy cơ thì chuyển người trực. Không gộp “nước yếu” vào chẩn đoán tắc cống, hoặc coi “rò đầu nối” là cùng nguyên nhân với outage.

### Đối chiếu dữ liệu
`technical.get_active_outage` kiểm tra nước cấp chung đúng thời điểm; `asset.read` xác định vòi/ống/đầu nối, ownership và lịch sử. Kỹ thuật viên đo áp lực/lưu lượng nếu SOP yêu cầu, có metric, unit, measured_at/by và thiết bị; phép thử thoát phải được ghi riêng. Kiểm tra điểm nối và nguồn rò theo manual; nếu nhiều asset khớp, hỏi thêm location/model thay vì tự chọn. Cô lập nguồn dùng request và approval phù hợp.

### Work order và kết quả
Work order phải có diagnosis cụ thể và repair scope đúng nhánh triệu chứng. Executor result ghi bộ phận/vật tư, phép thử trước/sau tương ứng và evidence đúng ticket. Nước cấp đạt không chứng minh thoát tốt; nước thoát tốt không chứng minh đầu nối khô. `technical.verify_resolution` kiểm tra từng tiêu chí, thiếu một nhánh trả `NEEDS_EVIDENCE`; nguồn chung/riêng mâu thuẫn trả `HUMAN_REVIEW`.

### Tình huống phân nhánh
- Nước cấp yếu: hỏi một vòi, cả căn hay nhiều căn; đối chiếu lịch cấp nước và cảm biến hợp lệ đúng tòa, không suy lỗi vòi.
- Thoát chậm: ghi điểm thoát, thời điểm, có trào ngược và mùi nước thải không; trào ngược chuyển nhánh nguy cơ vệ sinh.
- Đầu nối rò: ghi vị trí ướt, gần điện không, phần cấp hay thoát; không đề nghị siết thử khi chưa xác định vật tư và quyền.

### Hồ sơ tối thiểu và hậu kiểm
Ba triệu chứng phải là ba nhánh chẩn đoán riêng trong ticket dù cùng mã issue; ghi nguồn cấp, vị trí thoát và asset/ownership của đầu nối. Dữ liệu cảm biến stale hoặc quality bad không chứng minh áp lực hiện tại. Kỹ thuật viên ghi phép đo áp lực/lưu lượng, thời gian thoát hoặc điểm rò theo phương pháp được duyệt, đơn vị, người đo và hình ảnh. Hậu kiểm đối chiếu từng triệu chứng ban đầu; xử lý một nhánh không tự hoàn tất hai nhánh còn lại. Thiếu xác nhận nguồn hoặc phạm vi building thì chuyển đánh giá người.

### Nguồn
- MOCK-PROC-10-v1: fixture thiết kế từ technical-data/ISSUE_CATALOG.md mục 10 và docs/teams/quang/general.md; không phải văn bản BQL.

---

## MOCK-PROC-11 — Quy trình mẫu: cửa hoặc cửa sổ lỏng, hở

**Issue code:** `TECH.ARCH.DOOR_WINDOW`

MẪU GIẢ LẬP cho kiểm thử nội bộ; không phải SOP Vinhomes.

### Intake và chặn nguy cơ
Ghi loại cửa, vị trí, bản lề/khóa/khung/kính liên quan, tình trạng mở đóng, gió/nước lọt, ảnh toàn cảnh và cận cảnh. Hỏi cánh/kính có nguy cơ rơi, người bị kẹt, cửa thoát hiểm/an ninh không sử dụng được. Những trường hợp này cần người trực và đánh giá hạn chế khu vực; `area_restriction.request` chỉ tạo yêu cầu chờ duyệt.

### Khảo sát theo asset
Tra model/phụ kiện, lịch sử sửa, ownership và manual. Kỹ thuật viên xác định điểm lỏng/lệch thật, phân biệt lỗi chốt, bản lề, gioăng, khung hay kính; không siết/chỉnh bộ phận khi chưa rõ tải và liên kết. Work order ghi phạm vi tác động, vật tư đúng loại, tình trạng cấu kiện xung quanh và bằng chứng trước. Nếu cửa là tuyến thoát hiểm, cần quy trình và người nghiệm thu phù hợp, không áp dụng tiêu chí cửa thông thường.

### Kiểm chứng
Ghi thử mở/đóng/khóa theo SOP, kiểm tra liên kết ổn định và độ kín khi có yêu cầu. Evidence sau phải thể hiện đúng cửa và vị trí đã sửa; số đo khe hở chỉ hợp lệ nếu manual quy định phương pháp/giới hạn. Cánh vẫn có nguy cơ rơi hoặc lối thoát chưa dùng được thì `HUMAN_REVIEW`, không tuyên bố an toàn từ một ảnh.

### Tình huống phân nhánh
- Cửa kẹt hoặc khó khóa: hỏi loại cửa, vị trí, thời điểm, có người bị kẹt và lối thoát khác không; không đoán lệch bản lề.
- Cửa sổ lỏng, kính nứt hoặc nguy cơ rơi từ cao: ưu tiên cô lập khu vực và chuyển người trực; không hướng dẫn cư dân tự giữ/kéo thử cánh.
- Nước hắt qua cửa: ghi mưa/gió, điểm xâm nhập, ảnh theo thời điểm và dấu hiệu thấm khác; không tự kết luận ron hỏng.

### Hồ sơ tối thiểu và hậu kiểm
Asset record cần model, cấu hình, tầng/vị trí và owner, đặc biệt nếu thuộc mặt ngoài/tài sản chung. Ghi ảnh khung, cánh, khóa, kính, vị trí ướt và quyền tiếp cận. Kỹ thuật viên theo SOP/manual và quy định làm việc trên cao nếu có, ghi nguyên nhân, vật tư, thử đóng mở/khóa hoặc kín nước theo phương pháp được duyệt. Việc cửa mở được một lần không đủ xác minh nếu vẫn có nguy cơ rơi, kẹt hoặc hở nước. Hậu kiểm bởi người được ủy quyền.

### Nguồn
- MOCK-PROC-11-v1: fixture thiết kế từ technical-data/ISSUE_CATALOG.md mục 11 và docs/teams/quang/general.md; không phải văn bản BQL.

---

## MOCK-PROC-12 — Quy trình mẫu: tủ bếp xệ hoặc cánh lệch

**Issue code:** `TECH.ARCH.CABINET_SAG`

MẪU GIẢ LẬP cho kiểm thử A2; không phải SOP Vinhomes hoặc hướng dẫn cư dân tháo tủ.

### Tiếp nhận và an toàn
Ghi tủ treo/đứng, cánh hay toàn thân xệ, vị trí lắp, đồ bên trong, tiếng rạn, liên kết tường và ảnh toàn cảnh/điểm neo. Tủ hoặc cánh có nguy cơ rơi, cạnh sắc hoặc trẻ nhỏ ở gần cần người kiểm tra ngay và giữ người khỏi vùng nguy hiểm; hạn chế khu vực là request chờ duyệt chứ không phải hành động của agent.

### Phân biệt nguyên nhân
Tra bản vẽ/model hoặc hướng dẫn lắp đặt, lịch sử sửa và dấu ẩm/rò quanh tủ. Kỹ thuật viên phân biệt bản lề lệch với cả thân tủ mất neo, nền tường yếu hoặc quá tải. Nếu là hư hỏng điểm neo, không nghiệm thu bằng việc chỉ chỉnh cánh. Work order ghi phạm vi sửa, vật tư/điểm liên kết và người có chuyên môn thực hiện; không dùng số tải giả lập để khẳng định an toàn.

### Kết quả
Executor result lưu checklist điểm neo, thử mở/đóng theo tải và điều kiện được duyệt, ảnh trước/sau. Tiêu chí chịu tải thuộc thiết kế/manual thật; nếu không có, yêu cầu người có thẩm quyền xác nhận. Tủ còn rung/lệch hoặc thiếu ảnh điểm neo thì `NEEDS_EVIDENCE`/`HUMAN_REVIEW`; `VERIFIED` không tự đóng ticket.

### Tình huống phân nhánh
- Cánh tủ xệ: hỏi cánh nào, độ lệch quan sát được, bản lề/ốc rơi chưa, có trẻ nhỏ hoặc đồ nặng bên dưới không; không chỉ định tự siết.
- Tủ treo tách tường hoặc có nguy cơ rơi: chuyển người trực và tránh khu vực; không yêu cầu cư dân đỡ tủ hay tháo đồ trong vùng nguy hiểm.
- Hỏng sau sửa: liên kết work order cũ và xác minh tường/nền neo, model phụ kiện, tải sử dụng bằng chuyên môn; không mặc định lỗi lắp đặt.

### Hồ sơ tối thiểu và hậu kiểm
Ghi vị trí, dạng tủ, ảnh mối nối/cánh/khung, mốc phát hiện và phạm vi nguy hiểm. Asset/owner, điều kiện bảo hành và quyền tiếp cận cần xác minh. Kỹ thuật viên ghi vật liệu nền, loại phụ kiện theo manual, hạng mục xử lý và thử chức năng theo SOP. Không đặt tải trọng thử hoặc loại neo từ fixture. Hậu kiểm gồm ổn định, đóng mở, không còn bộ phận lỏng và evidence sau đúng ticket; thiếu xác nhận nền neo hoặc còn nguy cơ rơi thì giữ mở.

### Nguồn
- MOCK-PROC-12-v1: fixture thiết kế từ technical-data/ISSUE_CATALOG.md mục 12 và docs/teams/quang/general.md; không phải văn bản BQL.

---

## MOCK-PROC-13 — Quy trình mẫu: nứt tường hoặc trần

**Issue code:** `TECH.ARCH.CRACK`

MẪU GIẢ LẬP cho POC A2; không phải SOP Vinhomes và không chứng nhận an toàn kết cấu.

### Intake và đánh giá khẩn
Ghi vị trí, chiều/hướng vết nứt, ảnh có thước và captured_at, thời điểm đầu/tái phát, dấu rò/ẩm và ảnh hưởng cửa. Phân biệt số cư dân ước lượng với số kỹ thuật viên đo. Trần võng, vật liệu rơi hoặc vết phát triển nhanh thì chuyển người có chuyên môn; `area_restriction.request` và `vendor_dispatch.request` chỉ ở trạng thái `PENDING_APPROVAL`, không phải đã phong tỏa/đặt thợ.

### Thu thập chứng cứ
Kỹ thuật viên ghi width/length theo vị trí, unit, thiết bị, measured_at/by và ảnh cùng mốc; có thể lặp ở thời điểm sau để theo dõi. Tra hồ sơ cấu kiện/hoàn thiện đúng building, lịch sử và SOP có hiệu lực. Không kết luận nứt kết cấu hay chỉ thẩm mỹ từ ảnh hoặc ngưỡng đo tự đặt. Khi thiếu hồ sơ cấu kiện hoặc các nguồn đo mâu thuẫn, yêu cầu chuyên gia xác nhận bằng văn bản.

### Xử lý và nghiệm thu
Work order/assignment chỉ định phạm vi đánh giá trước phạm vi sửa; kết quả ghi chẩn đoán đã được chuyên gia/nhân viên phù hợp xác nhận, biện pháp đã duyệt, số đo trước/sau và theo dõi. Ảnh vá/sơn không chứng minh cấu kiện an toàn. Nếu thiếu đánh giá chuyên môn bắt buộc, `technical.verify_resolution` trả `HUMAN_REVIEW`; thiếu ảnh/số đo trả `NEEDS_EVIDENCE`. Không tự hạ mức khẩn hay đóng ticket.

### Tình huống phân nhánh
- Vết nứt nhỏ được phát hiện: ghi vị trí, chiều/đường đi và ảnh có mốc thời gian; không chẩn đoán nứt kết cấu chỉ từ ảnh.
- Nứt mở rộng nhanh, trần võng, rơi vật liệu hoặc cửa bị biến dạng cùng lúc: chuyển người trực/đơn vị chuyên môn công trình ngay, hạn chế tiếp cận; không chờ đủ ảnh.
- Nứt gần vệt ẩm: liên kết ca thấm, giữ hai giả thuyết tách biệt cho tới khi khảo sát.

### Hồ sơ tối thiểu và hậu kiểm
Ghi sơ đồ vị trí, tầng, các mốc ảnh, biến đổi theo thời gian, điều kiện xung quanh và người quan sát. Cần chuyên gia có quyền xác định hạng mục kết cấu hay hoàn thiện trước khi ra phương án; kỹ thuật viên thông thường không tự tuyên bố an toàn kết cấu. Phép đo nếu có cần phương pháp, đơn vị, dụng cụ, thời điểm và người đo. Hồ sơ sửa lớp phủ không thay thế đánh giá nguyên nhân. Hậu kiểm yêu cầu quyết định của người có thẩm quyền và lịch theo dõi phù hợp; không dùng kích thước nứt giả lập làm ngưỡng an toàn.

### Nguồn
- MOCK-PROC-13-v1: fixture thiết kế từ technical-data/POC_WORKFLOWS.md POC 4 và ISSUE_CATALOG.md mục 13; không phải văn bản BQL.

---

## MOCK-PROC-14 — Quy trình mẫu: sơn bong, vết ố hoặc ẩm mốc

**Issue code:** `TECH.ARCH.PAINT_MOISTURE`

MẪU GIẢ LẬP, không phải SOP Vinhomes hoặc lời khuyên y tế. Không sơn che vết ố khi nguồn ẩm chưa được xử lý.

### Thu thập và phân luồng
Ghi diện tích/vị trí, thời điểm, ảnh theo mốc thời gian, mùi, nước đang rò, vật liệu mềm và người báo triệu chứng sức khỏe. Nước gần điện, trần võng hoặc ẩm lan nhanh phải chuyển người trực; ảnh hưởng sức khỏe cần người phù hợp đánh giá. Không gán nguyên nhân “thấm từ căn trên” chỉ vì vị trí vết ố.

### Điều tra nguồn ẩm
Đối chiếu incident rò nước/điều hòa, outage, lịch sử sửa và bề mặt quanh khu vực. Kỹ thuật viên ghi độ ẩm theo điểm đo với metric/unit/phương pháp/measured_at/by; manual vật liệu và SOP thật quyết định điều kiện thi công. Nếu có mốc/ẩm ở nhiều vị trí, lập phạm vi khảo sát và khắc phục nguồn; không dùng ảnh sau sơn làm bằng chứng đã hết ẩm. Việc tiếp cận căn liên quan phải qua quyền/approval.

### Kết quả
Work order ghi nguồn ẩm đã xác nhận, biện pháp xử lý nguồn, vật liệu thay, số đo và ảnh trước/sau. Sau xử lý phải có mốc theo dõi tái ẩm theo SOP đã duyệt; không bịa thời gian khô hay nồng độ an toàn. Thiếu chứng cứ xử lý nguồn hoặc vẫn có dấu ẩm trả `NEEDS_EVIDENCE`/`HUMAN_REVIEW`, không tự tuyên bố khu vực an toàn.

### Tình huống phân nhánh
- Sơn bong/ố cục bộ: hỏi mốc bắt đầu, vùng mở rộng, ảnh và gần khu vực ẩm/đường ống không; không coi sơn là nguyên nhân.
- Có mùi mốc mạnh, vật liệu rơi hoặc nước gần điện: chuyển nhánh an toàn/sức khỏe, hạn chế tiếp xúc; không đề nghị cạo sơn hoặc phun hóa chất.
- Sơn vừa làm lại đã bong: đối chiếu lịch công việc, điều kiện nền và biên bản nghiệm thu cũ; không tự quy trách nhiệm nhà thầu.

### Hồ sơ tối thiểu và hậu kiểm
Ticket phân biệt triệu chứng bề mặt với nguồn ẩm tiềm ẩn, có ảnh mốc thời gian và diện tích/vị trí. Kỹ thuật viên ghi kết quả khảo sát nền, phép đo ẩm có phương pháp/đơn vị, nguồn nước được kiểm chứng và hạng mục xử lý. Nếu nguồn ẩm chưa xử lý, chỉ ghi can thiệp tạm, không nghiệm thu sơn cuối. Hồ sơ sau phải có ảnh đúng ticket, vật tư/phạm vi sửa, tiêu chí khô nền và quan sát tái ẩm từ SOP được duyệt; không tự đặt thời gian khô từ mẫu này.

### Nguồn
- MOCK-PROC-14-v1: fixture thiết kế từ technical-data/ISSUE_CATALOG.md mục 14 và docs/teams/quang/general.md; không phải văn bản BQL.

---

## MOCK-PROC-15 — Quy trình mẫu: sàn trầy, phồng hoặc bong

**Issue code:** `TECH.ARCH.FLOOR_DAMAGE`

MẪU GIẢ LẬP cho kiểm thử; không phải SOP Vinhomes.

### Intake và an toàn lối đi
Ghi loại sàn, diện tích, cạnh vênh/cạnh sắc, nước dưới lớp sàn, tình trạng lún, vị trí trên lối đi và ảnh có mốc. Hỏi người vấp ngã, nước gần điện, rò gần đây; có nguy cơ đi lại hoặc vật liệu rơi thì chuyển người, đề nghị hạn chế khu vực qua approval chứ không tự tuyên bố đã chặn lối đi.

### Chẩn đoán theo vật liệu
Tra asset/vật liệu, bảo hành, lịch sử thấm/rò và manual thi công. Kỹ thuật viên xác định chỉ trầy bề mặt hay mất ổn định/nền ẩm; đo độ phẳng/ẩm theo SOP đúng vật liệu khi cần. Không kết luận “chỉ thẩm mỹ” từ ảnh. Work order ghi điểm lỗi, nguồn ẩm nếu có, phạm vi tháo/sửa đã duyệt, vật tư và evidence trước.

### Nghiệm thu
Executor result có ảnh sau, checklist bề mặt ổn định và không còn cạnh/nguy cơ vấp, số đo theo phương pháp đã duyệt, bằng chứng nguồn ẩm đã xử lý nếu có. Thiếu tiêu chuẩn vật liệu hoặc còn sàn phồng/rò thì `HUMAN_REVIEW`; thiếu ảnh/số đo bắt buộc thì `NEEDS_EVIDENCE`. Người có quyền xác nhận trả lại lối đi, không để agent tự quyết.

### Tình huống phân nhánh
- Gạch lỏng hoặc sàn phồng: hỏi vị trí lối đi, diện tích quan sát, mốc xuất hiện, có tiếng rỗng/ướt không; không kết luận do keo hay nền.
- Mép sắc, gạch vỡ, sàn trơn hoặc nguy cơ vấp ngã: cảnh báo tránh khu vực và chuyển người trực; không yêu cầu cư dân bóc gạch để chụp ảnh.
- Sàn hỏng cùng rò nước: liên kết ticket nguồn nước và quyền khảo sát; sửa bề mặt trước khi xử lý nguồn ẩm có thể tái hỏng.

### Hồ sơ tối thiểu và hậu kiểm
Ghi vật liệu hoàn thiện, vị trí, diện tích, mức cản lối đi, ảnh và owner/bảo hành. Kỹ thuật viên kiểm tra nền, ẩm, vật tư tương thích và phương án theo SOP; công việc có bụi/ồn hoặc ảnh hưởng lối đi phải có phối hợp phù hợp. Ghi vật tư, phạm vi xử lý, evidence trước/sau và thời điểm bàn giao. Hậu kiểm gồm an toàn đi lại, bề mặt ổn định và nguyên nhân ẩm đã được xử lý hoặc theo dõi; không nghiệm thu chỉ vì ảnh trông phẳng.

### Nguồn
- MOCK-PROC-15-v1: fixture thiết kế từ technical-data/ISSUE_CATALOG.md mục 15 và docs/teams/quang/general.md; không phải văn bản BQL.

---

## MOCK-PROC-16 — Quy trình mẫu: nước thải trào ngược

**Issue code:** `TECH.PLUMB.SEWAGE_BACKFLOW`

MẪU GIẢ LẬP cho POC A2; không phải SOP Vinhomes hay hướng dẫn cư dân xử lý nước thải.

### Tiếp nhận và chuyển người
Ghi vị trí thoát, loại nước nghi là thải, mức/tốc độ lan, căn/khu chung ảnh hưởng, nước gần điện, người tiếp xúc và triệu chứng sức khỏe. Trào rộng, gần điện hoặc có phơi nhiễm thì chuyển người trực ngay; không chờ ảnh. Giữ nước thải tách khỏi luồng “rò nước sạch”; không yêu cầu cư dân thông tắc, dùng hóa chất hoặc vệ sinh vùng nhiễm bẩn. `area_restriction.request` chỉ tạo yêu cầu chờ duyệt.

### Xác định nguồn và xử lý có kiểm soát
Tra incident/outage cùng building và lịch sử tắc; kỹ thuật viên đúng chuyên môn xác định cục bộ hay tuyến chung, ghi vị trí và bằng chứng trước. Work order bao gồm phương án xử lý nguồn, kiểm soát tiếp xúc và phối hợp vệ sinh theo quy trình được phê duyệt; không mặc định thông tuyến xong là khu vực sạch. Nếu cần cô lập nước/giới hạn khu vực, trạng thái request pending chưa phải hành động thực địa.

### Điều kiện kiểm chứng
Executor result cần evidence sau xử lý đúng ticket, thử thoát theo SOP, checklist vệ sinh/khử nhiễm do người được giao xác nhận, thời điểm và phạm vi. Nếu chỉ có ảnh miệng thoát sạch hoặc nước ngừng trào nhưng thiếu checklist vệ sinh, trả `NEEDS_EVIDENCE`. Nếu còn nguồn trào, nguy cơ sức khỏe hoặc lời báo mâu thuẫn, trả `HUMAN_REVIEW`; người có quyền mới xác nhận an toàn và hoàn tất.

### Tình huống phân nhánh
- Nước thải trào tại một điểm: ghi vị trí, thời điểm, diện tích và có tiếp xúc với người/điện không; chuyển người trực ưu tiên vệ sinh và an toàn.
- Nhiều căn hoặc nhiều điểm thoát cùng trào: đối chiếu mạng thoát chung và outage/sự kiện building đúng quyền, phối hợp điều phối; không khẳng định do hành vi một căn.
- Có nước thải gần nguồn điện hoặc người có triệu chứng sức khỏe: nhánh khẩn, không chờ thu đủ ảnh hoặc hướng dẫn cư dân tự xử lý đường ống.

### Hồ sơ tối thiểu và hậu kiểm
Ticket ghi phạm vi nhiễm bẩn, nguồn từng nhận định, căn/khu vực ảnh hưởng và các yêu cầu vào căn; không xem dữ liệu căn khác khi chưa có grant. Asset và work order xác định tuyến thoát, owner, người thực hiện, biện pháp an toàn và SOP được duyệt. Kỹ thuật viên ghi vị trí tắc/rò đã kiểm chứng, công việc, evidence, biên bản vệ sinh/khử nhiễm và thử thoát nước theo quy trình. Chỉ hết trào trong một lần quan sát chưa đủ nghiệm thu; cần xác nhận nguồn, chức năng, vệ sinh và người có quyền chấp nhận. Không tự khẳng định môi trường đã an toàn.

### Nguồn
- MOCK-PROC-16-v1: fixture thiết kế từ technical-data/POC_WORKFLOWS.md POC 5 và ISSUE_CATALOG.md mục 16; không phải văn bản BQL.

---
