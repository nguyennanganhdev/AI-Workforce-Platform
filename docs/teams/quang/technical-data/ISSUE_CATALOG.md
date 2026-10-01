# Catalog 16 vấn đề kỹ thuật A2 — bản tham khảo v1

Mỗi mục là **mẫu dữ liệu để intake, retrieval và test**. `source_ids` tra ở `SOURCE_REGISTER.md`. Triệu chứng là lời kể/quan sát; nguyên nhân chỉ là giả thuyết. `emergency_signals` phải đưa vào assessment và cảnh báo người trực; mức ưu tiên chính thức do policy được publish quyết định. Không có mục nào ở đây là quy trình tự sửa đã được BQL phê duyệt.

## Các trường chung phải thu

`tenant/domain/building` đã xác minh, căn/khu vực nếu được phép, `reported_at`, `observed_at`, người/nguồn báo, mô tả nguyên văn, mã issue dự kiến, các facts còn thiếu, ảnh/video có consent và metadata, phạm vi ảnh hưởng (một căn/nhiều căn/khu chung), yếu tố điện/nước/khói/người bị thương, asset/model nếu biết, sự cố liên quan, tình trạng dịch vụ chung và lịch sử lặp. `unknown` là giá trị riêng; không biến thành `false`. Số đo chỉ ghi khi có thiết bị/người đo và đơn vị.

Kết quả kỹ thuật viên cần `work_order_id`, assignment hợp lệ, checklist, chẩn đoán xác nhận, việc làm, vật tư, số đo và evidence trước/sau, `started_at/completed_at`, nguồn và revision. `technical.verify_resolution` trả `VERIFIED`, `NEEDS_EVIDENCE` hoặc `HUMAN_REVIEW`; không tự đóng ticket.

## 01 — `TECH.ELEC.BREAKER_TRIP` · CB/aptomat nhảy lặp

- **Quan sát:** nhánh hay CB tổng nhảy, lần đầu/lặp lại, đang dùng thiết bị nào, một căn hay nhiều căn.
- **Hỏi thêm:** số lần và thời điểm; thiết bị mới/bị ướt; nóng, mùi khét, khói, tia lửa, điện giật; khu vực đang ngập; CB của căn hay tủ khu chung.
- **Giả thuyết cần kiểm:** quá tải, lỗi thiết bị, rò điện, lỗi đường dây hoặc nhánh cấp chung. Không chọn nguyên nhân khi chưa kiểm tra.
- **Tín hiệu khẩn:** khói/tia lửa, điện giật, nước gần điện, nóng/cháy xém. Chuyển người trực; không hướng dẫn cư dân mở tủ hoặc thử đóng CB lặp lại.
- **Dữ liệu/tool:** `asset.read`, lịch sử sự cố, `technical.get_active_outage`, SOP của hệ thống điện đúng tòa; `sensor.read` chỉ khi có metric và unit hợp lệ.
- **Bằng chứng nghiệm thu:** nguồn lỗi đã được người có chuyên môn xác nhận, checklist an toàn điện, số đo có đơn vị/người đo nếu cần, thử tải có giám sát, ảnh/biên bản đúng work order.
- **Nguồn:** ES-01, USFA-01, HUD-01, DV-01.

## 02 — `TECH.ELEC.FIXTURE_FAILURE` · ổ cắm/công tắc/đèn không hoạt động

- **Quan sát:** vị trí, một điểm hay cả nhánh, thiết bị có điện ở ổ khác không, ánh sáng hành lang/cửa thoát có bị ảnh hưởng không.
- **Hỏi thêm:** ổ/công tắc nóng, lỏng, đổi màu, có tiếng nổ/mùi khét không; trong căn hay khu chung; thiết bị nào đã được thử.
- **Giả thuyết:** bóng/thiết bị, ổ/công tắc, CB nhánh, đấu nối; chỉ kỹ thuật viên kiểm tra điện xác nhận.
- **Tín hiệu khẩn:** tia lửa, khói, điện giật, vỏ nóng hoặc mất đèn thoát hiểm. Không cho cư dân tháo mặt ổ hay kiểm tra dây.
- **Dữ liệu/tool:** asset của fixture/panel, lịch sử sửa, SOP điện, outage nếu nhiều điểm cùng mất.
- **Bằng chứng nghiệm thu:** chức năng được thử an toàn, điểm lỗi và vật tư thay, ảnh trước/sau, số đo nếu SOP yêu cầu.
- **Nguồn:** USFA-01, ES-01, HUD-01.

## 03 — `TECH.PLUMB.WATER_HEATER` · máy nước nóng không nóng hoặc rò

- **Quan sát:** không nóng/nóng yếu/rò, vị trí rò, thiết bị điện hay gas, model, tuổi/bảo hành, ảnh đèn báo/mã lỗi.
- **Hỏi thêm:** nước chảy gần ổ điện không; mùi gas/khói, nóng bất thường, CB nhảy; chỉ một vòi hay mọi vòi; nguồn nước chung có vấn đề không.
- **Giả thuyết:** mất nguồn, cài đặt, cảm biến/điện trở, van trộn, đường ống hoặc bồn; manual đúng model quyết định kiểm tra.
- **Tín hiệu khẩn:** nước chạm điện, mùi gas, khói, bỏng hoặc rò mạnh. Chuyển người trực, không hướng dẫn mở nắp thiết bị.
- **Dữ liệu/tool:** `asset.read` để xác định model, manual version, outage, bảo hành, maintenance history; ghi measurement chỉ từ kỹ thuật viên.
- **Bằng chứng nghiệm thu:** loại rò/nguyên nhân, checklist an toàn, thử chức năng sau sửa và ảnh/số đo hợp lệ.
- **Nguồn:** AO-01, HUD-01.

## 04 — `TECH.PLUMB.WATER_FILTER_LOW_FLOW` · máy lọc nước chảy yếu

- **Quan sát:** dòng yếu ở vòi lọc hay mọi vòi, model/lõi, ngày thay lõi, áp lực cấp, màu/mùi nước bất thường.
- **Hỏi thêm:** mới thay lõi không; có rò/ứ nước không; nước chưa lọc có cùng triệu chứng không; số đo lưu lượng có được kỹ thuật viên cung cấp không.
- **Giả thuyết:** lõi tắc do cặn, nguồn cấp yếu, van/ống gập, bơm hoặc áp lực; không suy từ ví dụ Brita sang mọi hệ RO.
- **Tín hiệu khẩn:** nước gần điện, rò lan, nước nghi nhiễm bẩn. Không bảo cư dân uống nước khi chất lượng chưa xác minh.
- **Dữ liệu/tool:** asset/model, manual lõi, lịch sử thay, outage nguồn nước, measurement `flow_rate` với đơn vị và phương pháp.
- **Bằng chứng nghiệm thu:** xác định nguyên nhân, vật tư/lõi đúng model, lưu lượng sau xử lý và thử rò.
- **Nguồn:** BR-01, EPA-01, HUD-01.

## 05 — `TECH.HVAC.CONDENSATION` · điều hòa đọng/chảy nước

- **Quan sát:** vị trí nước (dàn lạnh/trần/ống), thời điểm khi chạy, lượng/diện tích lan, model và ảnh gần–xa.
- **Hỏi thêm:** nước gần điện hoặc đèn trần không; trần võng không; ống thoát có nước ra không; bộ lọc/bảo trì gần nhất; căn dưới bị ảnh hưởng không.
- **Giả thuyết:** tắc/gập đường nước ngưng, bộ lọc bẩn, khay/ống rò, nguồn thấm khác; không mặc định là lỗi điều hòa khi nước ở trần.
- **Tín hiệu khẩn:** nước vào điện, trần có nguy cơ rơi, nước lan nhiều căn. Ngừng dùng thiết bị và chuyển người kiểm tra.
- **Dữ liệu/tool:** asset/model, SOP và manual, maintenance history, evidence độ ẩm/ảnh; measurement `drain_flow` chỉ do người đo xác thực.
- **Bằng chứng nghiệm thu:** nguồn rò được xác nhận, đường thoát và hoạt động sau sửa được thử, ảnh trước/sau, độ khô vùng ảnh hưởng theo SOP.
- **Nguồn:** DK-01, EPA-02, HUD-01.

## 06 — `TECH.PLUMB.CONCEALED_LEAK` · rò âm tường/thấm trần

- **Quan sát:** vị trí, diện tích/vệt ố, tốc độ lan, thời điểm xuất hiện, căn trên/cạnh dưới, ảnh theo thời gian.
- **Hỏi thêm:** điện ở vùng ẩm không; vòi/ống đứng hay sau tắm mới xuất hiện; đã báo căn liên quan chưa; có dấu trần võng không.
- **Giả thuyết:** ống nhánh, ống đứng, chống thấm, nước ngưng hoặc nguồn ngoài; không quy trách nhiệm cho căn khác khi chưa xác minh.
- **Tín hiệu khẩn:** nước gặp điện, thấm nhanh nhiều căn, trần bong/võng/rơi. Vào căn khác chỉ qua `apartment_entry.request` chờ phê duyệt.
- **Dữ liệu/tool:** ticket liên quan, outage, evidence gốc, lịch sử sửa, measurement độ ẩm có vị trí/thời điểm/người đo.
- **Bằng chứng nghiệm thu:** nguồn được xác định, xử lý nguồn nước, theo dõi không tái rò và tình trạng bề mặt/độ ẩm, evidence hai phía khi có quyền.
- **Nguồn:** EPA-02, EPA-03, HUD-03, DV-01.

## 07 — `TECH.PLUMB.SHOWER_SEAL` · vách tắm hở/rò

- **Quan sát:** nước thoát ở mép cửa, ngưỡng, mạch tường hay khe kính; chỉ khi tắm hay cả khi không dùng.
- **Hỏi thêm:** model vách, hướng vòi, vị trí nước, ron/silicone hở, sàn ngoài có trơn và nước lan sang ổ điện không.
- **Giả thuyết:** gioăng, khe tiếp giáp, lắp đặt/độ phẳng, thoát sàn; cần kiểm tra nguồn nước trước khi trám lại.
- **Tín hiệu khẩn:** kính/khung lỏng có nguy cơ rơi, trượt ngã, nước gần điện, thấm xuống căn dưới.
- **Dữ liệu/tool:** asset/model, hướng dẫn nhà sản xuất, lịch sử bảo trì, ảnh chi tiết khu mép/ngưỡng và test rò có kiểm soát.
- **Bằng chứng nghiệm thu:** vị trí rò trước sửa, vật tư đúng model, thử dùng nước sau sửa và xác nhận không thấm ra ngoài.
- **Nguồn:** KH-01, HUD-01, EPA-01.

## 08 — `TECH.PLUMB.TOILET_LEAK` · bồn cầu rỉ/chảy liên tục

- **Quan sát:** nước chảy trong lòng bồn hay rò ra sàn, tiếng nước liên tục, mức nước, vị trí van cấp.
- **Hỏi thêm:** nước sạch/nước thải; tràn không; sàn ướt gần điện không; bồn có nứt không; model bộ xả.
- **Giả thuyết:** van cấp, gioăng/bộ xả, ống cấp, chân bồn/đường thoát; dấu hiệu ngoài sàn khác rò trong lòng bồn.
- **Tín hiệu khẩn:** nước thải tràn, rò lớn, nước gần điện hoặc căn dưới bị ảnh hưởng.
- **Dữ liệu/tool:** asset/model, lịch sử sửa, water meter nếu nguồn đáng tin, evidence ảnh/video và test phân biệt trong/ngoài bồn.
- **Bằng chứng nghiệm thu:** điểm rò xác nhận, vật tư thay, thử xả nhiều lần, sàn khô và không rò tiếp.
- **Nguồn:** EPA-01, KH-02, HUD-01.

## 09 — `TECH.PLUMB.TRAP_ODOR` · mùi cống/bẫy nước

- **Quan sát:** vị trí mùi, thời điểm, có nhiều căn/tầng cùng mùi không, drain nào liên quan, nước thoát chậm hay trào không.
- **Hỏi thêm:** có mùi gas/khói không; drain ít sử dụng hay vừa bảo trì; thông gió; nước thải lộ ra; triệu chứng sức khỏe.
- **Giả thuyết:** bẫy nước khô, lỗi kín khí/thoát khí, tắc đường thoát hoặc nguồn khác; mùi đơn lẻ không đủ chẩn đoán.
- **Tín hiệu khẩn:** nghi gas, nhiều người khó chịu/chóng mặt, nước thải trào, mùi mạnh lan nhiều căn. Không hướng dẫn mở hố ga/tủ kỹ thuật.
- **Dữ liệu/tool:** outage/incident chung, sơ đồ đường thoát được phép đọc, maintenance history, quan sát từ kỹ thuật viên.
- **Bằng chứng nghiệm thu:** nguồn mùi được xác nhận, lỗi khắc phục, thử xả và theo dõi mùi theo thời gian; trường hợp không rõ trả `HUMAN_REVIEW`.
- **Nguồn:** HUD-03, CDC-01, EPA-03.

## 10 — `TECH.PLUMB.SUPPLY_DRAIN_JOINT` · nước yếu/thoát chậm/rò đầu nối

- **Quan sát:** nước cấp yếu hay thoát chậm hay rò, một thiết bị/một căn/nhiều căn, điểm rò, nhiệt độ/nước bẩn.
- **Hỏi thêm:** sự cố đang lan không; thiết bị mới lắp hay vừa sửa; áp lực/lưu lượng có phép đo thật không; nước chạm điện không.
- **Giả thuyết:** cặn ở vòi/lọc, van, khớp nối, tắc cục bộ hoặc vấn đề nguồn chung; không gộp ba symptom thành một diagnosis.
- **Tín hiệu khẩn:** rò liên tục gây ngập, nước gần điện, nước thải trào hoặc mất nước diện rộng.
- **Dữ liệu/tool:** asset, outage, sensor nếu có metric thật, maintenance history; vị trí và ảnh mối nối/miệng thoát.
- **Bằng chứng nghiệm thu:** ghi chính xác triệu chứng và vị trí trước sửa, test lưu lượng/thoát/rò sau sửa với đơn vị nếu có đo.
- **Nguồn:** EPA-01, HUD-01, HUD-03.

## 11 — `TECH.ARCH.DOOR_WINDOW` · cửa/cửa sổ lỏng, hở

- **Quan sát:** loại cửa, vị trí, bản lề/khóa/khung/kính, mức mở đóng, gió/nước lọt, liên quan cửa thoát hiểm không.
- **Hỏi thêm:** cánh hoặc kính có nguy cơ rơi; người có bị kẹt; cửa an ninh/thoát nạn có bị khóa; đã có sửa trước không.
- **Giả thuyết:** bản lề, chốt, khung lệch, gioăng, kính; kiểm tra đúng loại cửa trước sửa.
- **Tín hiệu khẩn:** kính/cánh sắp rơi, cửa thoát hiểm không dùng được, người bị kẹt; hạn chế khu vực cần approval.
- **Dữ liệu/tool:** asset cửa, thiết kế/lịch sử sửa, ảnh liên kết bản lề/khung và độ hở đo bởi kỹ thuật viên.
- **Bằng chứng nghiệm thu:** vận hành mở/đóng/khóa an toàn, phụ kiện cố định, không còn nguy cơ rơi và bằng chứng đúng cửa.
- **Nguồn:** HUD-01.

## 12 — `TECH.ARCH.CABINET_SAG` · tủ bếp xệ/cánh lệch

- **Quan sát:** tủ treo hay tủ đứng, cánh hay cả thân bị xệ, bản lề/giá treo, mức tải và đồ bên dưới.
- **Hỏi thêm:** có tiếng rạn, liên kết tường bong, cánh/tủ rung lắc, nước làm hỏng gỗ, trẻ em ở gần không.
- **Giả thuyết:** bản lề/chốt lỏng, tủ quá tải, nền gắn hỏng, ẩm; không chỉ chỉnh cánh nếu cả thân tủ mất neo.
- **Tín hiệu khẩn:** tủ/cánh có nguy cơ rơi hoặc cạnh sắc trong lối đi; chuyển người và cô lập khu vực khi cần.
- **Dữ liệu/tool:** loại tủ, vị trí, lịch sử sửa, ảnh toàn cảnh và điểm neo, tài liệu lắp đặt nếu có.
- **Bằng chứng nghiệm thu:** liên kết được người có chuyên môn kiểm tra, cánh mở đóng ổn định, tải phù hợp và ảnh sau sửa.
- **Nguồn:** HUD-01.

## 13 — `TECH.ARCH.CRACK` · nứt tường/trần

- **Quan sát:** vị trí, chiều dài/rộng ước lượng, hướng vết nứt, thời điểm xuất hiện, ảnh có thước mốc thời gian.
- **Hỏi thêm:** nứt tăng nhanh, trần võng/rơi vật liệu, cửa kẹt bất thường, có rò/ẩm, có công trình gần đó không.
- **Giả thuyết:** lớp hoàn thiện, co ngót, ẩm hoặc cấu kiện; ảnh không đủ để phân biệt kết cấu với hoàn thiện.
- **Tín hiệu khẩn:** phát triển nhanh, trần võng, vật liệu rơi, dấu hiệu cấu kiện hỏng. `area_restriction.request` và `vendor_dispatch.request` chỉ tạo pending approval.
- **Dữ liệu/tool:** ảnh có scale, số đo chính thức của kỹ thuật viên, hồ sơ cấu kiện/thi công nếu được cấp, lịch sử theo dõi.
- **Bằng chứng nghiệm thu:** đánh giá chuyên môn bằng văn bản khi cần, nguyên nhân, cách xử lý, phép đo theo dõi và xác nhận an toàn bởi người có thẩm quyền.
- **Nguồn:** HUD-01, HUD-02.

## 14 — `TECH.ARCH.PAINT_MOISTURE` · sơn bong/vết ố/ẩm mốc

- **Quan sát:** diện tích, màu/vị trí, mùi, độ ẩm, thời điểm theo mùa hoặc sau mưa/tắm/chạy điều hòa.
- **Hỏi thêm:** nguồn nước còn hoạt động không; có rò từ trần/tường; người có triệu chứng sức khỏe; vật liệu xốp bị ẩm không.
- **Giả thuyết:** rò đường ống, ngưng tụ, chống thấm, thông gió hoặc hỏng lớp sơn; không sơn che khi nguồn ẩm chưa xử lý.
- **Tín hiệu khẩn:** nước gần điện, trần mềm/võng, ẩm lan nhanh hoặc ảnh hưởng sức khỏe rõ rệt.
- **Dữ liệu/tool:** evidence trước/sau, nguồn rò liên quan, measurement độ ẩm có thiết bị/đơn vị, SOP vật liệu.
- **Bằng chứng nghiệm thu:** nguồn ẩm đã xử lý, bề mặt đạt điều kiện khô theo SOP, không tái ẩm trong thời gian theo dõi và ảnh có thời điểm.
- **Nguồn:** EPA-02, EPA-03, HUD-01.

## 15 — `TECH.ARCH.FLOOR_DAMAGE` · sàn trầy/phồng/bong

- **Quan sát:** loại sàn, diện tích, mép vênh/bong, nước bên dưới, vị trí trên lối đi, ảnh có thước.
- **Hỏi thêm:** có người vấp ngã; nước/rò gần đây; cạnh sắc; nền có tiếng rỗng/lún; vật liệu gì và bảo hành còn không.
- **Giả thuyết:** va đập, ẩm, lắp đặt/keo, nền biến dạng; không tự khẳng định chỉ là thẩm mỹ.
- **Tín hiệu khẩn:** nguy cơ vấp ngã, cạnh sắc, lún/rơi vật liệu hoặc nước gần điện; cần đánh giá và hạn chế lối đi.
- **Dữ liệu/tool:** asset/vật liệu sàn, incident nước liên quan, ảnh và measurement bởi kỹ thuật viên, lịch sử sửa.
- **Bằng chứng nghiệm thu:** bề mặt ổn định/phẳng theo tiêu chí đã duyệt, không còn cạnh/nguy cơ vấp, nguồn ẩm nếu có đã xử lý.
- **Nguồn:** HUD-01, EPA-02.

## 16 — `TECH.PLUMB.SEWAGE_BACKFLOW` · nước thải trào ngược

- **Quan sát:** vị trí thoát sàn/bồn cầu, loại nước, mùi, diện tích/độ sâu, tốc độ lan, số căn/khu chung ảnh hưởng.
- **Hỏi thêm:** nước gần điện không; cư dân tiếp xúc/chấn thương/triệu chứng; sự cố cùng thời điểm ở căn khác; drain tắc trước đó không.
- **Giả thuyết:** tắc cục bộ/đường chung, sự cố bơm/ống đứng hoặc nguồn ngoài; chỉ đội kỹ thuật xác nhận.
- **Tín hiệu khẩn:** lan rộng, gần điện, phơi nhiễm nước bẩn hoặc ảnh hưởng sức khỏe. Chuyển người trực; yêu cầu hạn chế khu vực qua approval nếu cần.
- **Dữ liệu/tool:** outage và incident cùng building, evidence trước/sau, vệ sinh/khử nhiễm, history, người thực hiện có quyền.
- **Bằng chứng nghiệm thu:** nguồn trào được khắc phục, thử thoát, khu vực được vệ sinh phù hợp, không còn nước bẩn; kết quả thiếu checklist vệ sinh trả `NEEDS_EVIDENCE`.
- **Nguồn:** CDC-01, CDC-02, HUD-03.

## Chuyển catalog thành dữ liệu có hiệu lực

Mỗi issue phải được Domain Owner duyệt taxonomy và tín hiệu nguy hiểm; từng SOP phải có `document_version_id`, `effective_from/to`, phạm vi, audience, nội dung và hash. Mapping policy V3 phải được publish riêng theo domain/scope/category. Kết quả retrieval cần citation document/version/chunk và ACL trước khi tìm. Không lấy các `source_ids` trên làm `sop_document_ids` vì phần lớn là tài liệu tham khảo ngoài Vinhomes.
