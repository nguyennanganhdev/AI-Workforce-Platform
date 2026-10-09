# Kịch bản vàng của domain Vinhomes

Trạng thái: **bản 0.2 (09/10/2026), đã làm; mỗi kịch bản có một test trong `services/vinhomes-api/tests/test_golden.py`**. Đi cùng [HOP_DONG_TICH_HOP.md](HOP_DONG_TICH_HOP.md) (cách platform nối vào) và [KE_HOACH_TRIEN_KHAI.md](KE_HOACH_TRIEN_KHAI.md) (thứ tự làm, phần nào của schema tham chiếu được dùng). Nghiệp vụ hiện có của gói: [NGHIEP_VU_VINHOMES.md](NGHIEP_VU_VINHOMES.md).

## 1. Vì sao có tài liệu này

Dữ liệu giả không có kịch bản chỉ là dữ liệu rác. Mỗi kịch bản dưới đây là một việc có thật mà cư dân hoặc nhân viên cần làm, kèm **điều kiện chấp nhận kiểm được bằng test**. Từ đó suy ra:

- dữ liệu giả phải có những gì (§3);
- domain phải có thao tác nào, platform được gọi thao tác nào (hợp đồng);
- thế nào là "xong" (mỗi kịch bản có một test mang đúng mã `G01`…`G13`).

## 2. Giả định (hãy sửa nếu sai)

1. Domain là **một đối tác độc lập**: có database, API, ứng dụng và dữ liệu riêng. Platform chỉ nối vào qua hợp đồng tích hợp, không đọc database.
2. Có hai nhóm người dùng của domain: **cư dân** và **nhân viên** (hiện trường, quản lý/BQL, an ninh, quản trị). Agent (Reception của domain, hoặc agent của platform) luôn **thay mặt một người** và không có quyền nào hơn người đó.
3. Việc **không thể đảo ngược hoặc có hiệu lực tiền bạc/pháp lý** luôn do người quyết định: duyệt phương án, đồng ý chi phí, thanh toán, hoàn tiền, nghiệm thu, đóng yêu cầu, đổi vai trò. Agent chỉ đọc, soạn nháp, đề xuất, hoặc làm việc nhỏ, thuộc phạm vi của chính người đó và hủy được.
4. Nghiệp vụ của các đối tượng **mới** (thẻ, khách, tiện ích, thi công, công nợ hằng tháng) lấy từ schema tham chiếu `schema.sql` / `domain_spec.json` của bạn: chỉ lấy phần kịch bản cần (xem kế hoạch §2). Nghiệp vụ của đối tượng **đã có** (yêu cầu, phương án, phiếu việc, an ninh) giữ nguyên mã trạng thái hiện tại của gói; chỗ hai bên khác nhau được ghi ở kế hoạch.
5. Thanh toán thật, gửi SMS/push thật, quét mã độc chưa làm. Kịch bản chỉ yêu cầu **ghi nhận trạng thái và tạo bản ghi thông báo** (`notification_deliveries`), không yêu cầu gửi ra ngoài.
6. Đơn vị tiền: đồng (VND), số nguyên hoặc `numeric(18,2)` như bảng hiện có.

## 3. Thế giới mẫu (dữ liệu giả cố định)

Nhân vật có mã cố định để test viết một lần, chạy mãi. Người sinh dữ liệu dùng seed ngẫu nhiên cố định, nên mỗi lần dựng ra cùng một thế giới.

| Mã | Ai | Vai trò trong dữ liệu |
|---|---|---|
| `an` | Nguyễn Văn An | Chủ sở hữu căn `S1.01-1201`; có xe máy, một thẻ cư dân, thẻ xe |
| `chau` | Lê Minh Châu | Thành viên hộ (`household`) của `S1.01-1201`, đã xác minh |
| `binh` | Trần Thị Bình | Người thuê (`tenant`) căn `S1.02-0803`, đã xác minh |
| `dung` | Phạm Quốc Dũng | Chủ **hai** căn: `S1.01-1502` và `HA2.05` (để thử tình huống phải chọn căn) |
| `em` | Hoàng Thị Em | Đã đăng ký tài khoản, liên kết căn **đang chờ xác minh** |
| `hoa` | Kỹ thuật viên Hoa | Chuyên môn điện nước, đang trong ca, rảnh |
| `khoa` | Kỹ thuật viên Khoa | Chuyên môn điện nước, đang nghỉ phép (không được giao việc) |
| `giang` | Bảo vệ Giang | An ninh, ca đêm |
| `minh` | Quản lý Minh | BQL phụ trách tòa `S1.01` và `S1.02` |
| `admin` | Quản trị viên | Quản trị toàn bộ |

Dựng bằng `python -m vinhomes_api.database mock --profile standard --seed 42` (chạy dưới 10 giây). Khối lượng đo được: 360 căn ở các tòa của Ocean Park đã có trong dữ liệu mẫu cộng một cụm villa và một dãy nhà phố; 669 tài khoản người; 25 nhân viên có ca 60 ngày; 6 tháng công nợ (1.920 thông báo phí, có quá hạn); 900 yêu cầu trong lịch sử ở đủ trạng thái; 933 thẻ; 291 lượt đăng ký khách; 219 lượt đặt tiện ích; 25 đơn thi công; 150 đơn lễ tân; 70 tài liệu tri thức. Hồ sơ `test` (130 căn) là thế giới mà các test dùng. Xem [NAP_DU_LIEU.md](NAP_DU_LIEU.md).

Một người **không bao giờ** thấy dữ liệu của căn mà họ không gắn (đó là điều kiện chấp nhận của mọi kịch bản cư dân, không lặp lại từng nơi).

## 4. Bảng tổng

Mức hỗ trợ: **Có** = mã hiện có đã làm; **Làm** = sẽ làm trong đợt này; **Đặc tả** = chỉ mô tả, làm sau.
Mức quyền của agent: `đọc`, `nháp` (cần người xác nhận), `việc nhỏ` (làm ngay, hủy được), `đề xuất` (nhân viên duyệt). Định nghĩa ở hợp đồng §3.

| Mã | Kịch bản | Người | Agent được làm | Hỗ trợ |
|---|---|---|---|---|
| G01 | Cư dân hỏi công nợ và hạn đóng | cư dân | đọc | Đã làm |
| G02 | Báo sự cố trong căn, có phương án, hoàn tất | cư dân, BQL, kỹ thuật | đề xuất | Đã làm (cổng đề xuất cho agent ngoài); các bước hiện trường đã có từ trước |
| G03 | Sự cố khẩn cấp (rò gas, ngập, cháy) | cư dân, bảo vệ, BQL | báo khẩn (việc nhỏ) | Đã làm (thêm đường báo khẩn cho cư dân) |
| G04 | Đăng ký khách đến thăm | cư dân, bảo vệ | việc nhỏ | Đã làm |
| G05 | Mất thẻ xe, xin cấp lại | cư dân, lễ tân | việc nhỏ (khóa), nháp (cấp lại) | Đã làm |
| G06 | Đặt tiện ích (BBQ, sân) và hủy | cư dân | việc nhỏ | Đã làm (thanh toán thật chưa có: lượt có phí giữ chỗ 15 phút rồi hết hạn) |
| G07 | Hỏi quy định thi công, xem đơn thi công | cư dân, BQL | đọc | Đã làm phần đọc; tạo đơn thi công chưa làm |
| G08 | Thông báo cắt nước theo kế hoạch | BQL, cư dân | nháp thông báo (BQL phát) | Đã làm |
| G09 | Phân quyền: chủ, người thuê, thành viên, chờ xác minh | cư dân | (giới hạn như người đó) | Đã làm |
| G10 | Nhân viên hiện trường nhận việc và hoàn thành | kỹ thuật | đọc | Đã có từ trước (test `test_staff_dispatch.py`); G10 kiểm thêm phạm vi và người nghỉ phép |
| G11 | Quản lý hỏi tổng hợp (sự cố theo tòa, quá hạn) | BQL | đọc | Đã làm |
| G12 | Yêu cầu quá hạn xử lý, cảnh báo chủ động | BQL | đề xuất | Đã làm (hạn do cơ sở dữ liệu gán, tác vụ quét, nguồn sự kiện) |
| G13 | Yêu cầu báo qua lễ tân hiện trong danh sách của cư dân | Cư dân | đọc | Đã làm |

## 5. Các kịch bản

Quy ước mỗi kịch bản: **Mục tiêu**, **Điều kiện** (dữ liệu có sẵn), **Diễn biến**, **Ràng buộc**, **Chấp nhận** (mỗi dòng là một khẳng định kiểm được; test `Gxx` kiểm đúng các dòng này).

### G01 Cư dân hỏi công nợ và hạn đóng

- **Mục tiêu.** "Tháng này nhà tôi phải đóng bao nhiêu, hạn khi nào, còn khoản nào quá hạn?"
- **Điều kiện.** `an` là chủ `S1.01-1201`; căn có thông báo phí tháng hiện tại (đã phát hành, chưa trả) và một thông báo tháng trước quá hạn. `dung` có hai căn.
- **Diễn biến.** Người dùng (qua app hoặc agent thay mặt) lấy danh sách căn của mình; chọn căn; lấy thông báo phí và tổng còn nợ; xem từng dòng phí (phí quản lý, gửi xe, nước, dịch vụ).
- **Ràng buộc.**
  - Chủ và người thuê đã xác minh thấy công nợ của căn. Thành viên hộ **không** thấy công nợ. Người chờ xác minh không thấy gì.
  - Người có nhiều căn phải chọn một căn: đường dẫn **bắt buộc** có mã căn; không có chế độ "gộp ngầm".
  - Agent chỉ đọc. Không có thao tác thanh toán qua agent.
  - Trạng thái `overdue` do hệ thống tính theo `due_date` khi đọc, không phụ thuộc việc ai đó đã chạy tác vụ.
- **Chấp nhận.**
  1. `an` đọc công nợ `S1.01-1201`: thấy đúng tổng còn nợ bằng tổng (`total_amount - paid_amount`) của các thông báo `issued`/`partially_paid`/`overdue`.
  2. Thông báo tháng trước hiển thị `overdue`, tháng này hiển thị `issued`.
  3. `chau` đọc cùng căn: 403.
  4. `em` đọc: 403.
  5. `dung` lấy danh sách căn của mình (`/resident/homes`) rồi gọi theo từng căn: đúng dữ liệu của căn đó; căn của `an`: 403. Đường dẫn luôn mang mã căn nên không có chế độ gộp ngầm.
  6. Mọi thao tác ghi công nợ bằng token của agent: 403.

### G02 Báo sự cố trong căn, có phương án, hoàn tất

- **Mục tiêu.** "Vòi bếp nhà tôi rò nước." Từ báo cáo đến nghiệm thu, người luôn quyết định các bước có tiền hoặc thay đổi lịch.
- **Điều kiện.** `an` đã xác minh; `hoa` rảnh và đúng chuyên môn; `minh` phụ trách tòa; không có phương án đang chờ.
- **Diễn biến.**
  1. Cư dân mô tả sự cố (app hoặc Reception); hệ thống tạo **nháp** yêu cầu; cư dân xác nhận gửi.
  2. Hệ thống xác định đơn vị quản lý; BQL tiếp nhận.
  3. **Agent (hoặc nhân viên) đề xuất phương án**: tóm tắt, 3 đến 4 bước, người làm, giờ hẹn, chi phí dự kiến, ai chịu chi phí.
  4. BQL duyệt (sửa được bước, người làm, giờ hẹn). Phương án sang chờ cư dân.
  5. Cư dân đồng ý giờ hẹn và chi phí. Hệ thống tạo phiếu việc và chào việc cho `hoa`.
  6. `hoa` nhận, di chuyển, đến, xử lý, đính kèm ảnh bằng chứng, hoàn thành.
  7. Cư dân xác nhận hoặc yêu cầu làm lại; BQL nghiệm thu; yêu cầu đóng.
- **Ràng buộc.**
  - Agent **đề xuất** phương án, không duyệt, không đồng ý thay cư dân, không giao việc ngoài phương án đã duyệt.
  - Mỗi lần ghi dùng khóa idempotency; gửi lại không tạo trùng.
  - Phương án mới khi còn phương án chờ: 409. Phiên bản lệch: 409.
  - Người làm phải đang trong ca, đúng chuyên môn, chưa đủ việc đồng thời (trigger sức chứa phân công hiện có).
  - Giờ hẹn phải có múi giờ và ở tương lai.
- **Chấp nhận.**
  1. Nháp chưa thành yêu cầu cho tới khi cư dân xác nhận.
  2. Client tích hợp có quyền `propose` gửi phương án cho một yêu cầu của căn: 201, trạng thái `management_pending`, `proposed_by_agent_id` là client, sự kiện `plan.proposed` trong nhật ký.
  3. Cùng khóa idempotency, cùng nội dung: trả bản ghi cũ, không tạo thêm. Khác nội dung: 409.
  4. Client đó gọi `management-decision` hoặc `resident/plans/.../decision`: 403.
  5. BQL duyệt, rồi cư dân đồng ý: có đúng một phiếu việc, `hoa` có phân công `offered`.
  6. Giao cho `khoa` (đang nghỉ): bị từ chối.
  7. Hoàn tất tới `closed` qua đủ các bước, mỗi bước đúng người.
  8. Bản ghi kiểm toán có `initiator_kind='agent'` cho các bước agent làm, kèm mã ủy quyền.

### G03 Sự cố khẩn cấp

- **Mục tiêu.** Cư dân nói "có mùi gas" hoặc "nước tràn ra hành lang". Phải có người nhìn thấy ngay, không chờ quy trình thường.
- **Điều kiện.** `giang` đang trong ca; `minh` có thể nhận thông báo; căn của `an`.
- **Diễn biến.** Yêu cầu được đánh dấu khẩn (`is_emergency`, ưu tiên `critical`); BQL phụ trách nhận thông báo trong app; cảnh báo an ninh cho `giang`; `giang` xác nhận; có thể leo thang.
- **Ràng buộc.**
  - Agent **được báo khẩn** (đó là việc nhỏ, hủy được bằng cách BQL hạ mức), **không** được tự điều động bảo vệ hay hủy điều động; điều động/hủy cần BQL (đã có phê duyệt trong mã).
  - Báo khẩn bằng tin nhắn không phải của chính cư dân: từ chối.
  - Báo khẩn cho yêu cầu đã ở trạng thái cuối: 409.
- **Chấp nhận.**
  1. Báo khẩn tạo `is_emergency=true`, `priority='critical'`, một thông báo cho mỗi BQL trong phạm vi, khóa chống trùng; gọi lại không tạo thêm.
  2. `giang` xác nhận cảnh báo: trạng thái cảnh báo đổi, có dấu vết.
  3. Agent gọi điều động an ninh: 403. BQL gọi: tạo yêu cầu chờ phê duyệt.
  4. Nếu không có BQL phù hợp, kết quả báo `no_matching_bql_recipient` thay vì im lặng.

### G04 Đăng ký khách đến thăm

- **Mục tiêu.** "Ngày mai 19:00 bạn tôi tới chơi, đi ô tô."
- **Điều kiện.** `an` đã xác minh; phân khu có cấu hình tự duyệt hoặc cần duyệt; `giang` ở cổng.
- **Diễn biến.** Cư dân tạo đăng ký khách (tên, số người, mục đích, biển số, khung giờ). Nếu không cần duyệt: `approved` ngay và có mã QR. Nếu cần duyệt: `pending_approval`, lễ tân duyệt. Tại cổng quét QR trong khung giờ: `checked_in`; khách ra: `checked_out`. Quá giờ chưa vào: `expired`.
- **Ràng buộc.**
  - Khung giờ phải ở tương lai, tối đa một số ngày cấu hình, `visit_to > visit_from`.
  - Giới hạn số đăng ký đang hiệu lực của một căn, số ngày báo trước, độ dài một lượt, và việc khách nào được duyệt ngay: theo cấu hình của phân khu (bảng `zone_settings`; mặc định 10 lượt, 30 ngày, 72 giờ, khách gia đình hoặc giao hàng tới 5 người).
  - Hủy được khi chưa vào. Quét QR ngoài khung giờ hoặc đã hết hạn: từ chối, ghi lượt từ chối.
  - Thành viên hộ **được** đăng ký khách; người chờ xác minh không.
- **Chấp nhận.**
  1. Tạo trong khung giờ hợp lệ: 201; có `qr_token` khi `approved`.
  2. Khung giờ quá khứ hoặc đảo ngược: 422.
  3. Vượt giới hạn đăng ký đang hiệu lực: 409.
  4. Quét QR đúng giờ: `checked_in`; quét lần hai khi đã `checked_in`: không nhập lại; quét ngoài giờ: từ chối.
  5. Cư dân hủy khi `approved`: `cancelled`; hủy khi `checked_in`: 409.
  6. Chuyển trạng thái ngoài từ điển (ví dụ `expired` về `approved`): bị cơ sở dữ liệu chặn.
  7. Cùng một đăng ký 8 khách gia đình: chờ lễ tân duyệt ở khu tháp, duyệt ngay ở khu villa; lượt kéo dài 80 giờ bị từ chối ở tháp, nhận ở villa (`test_zone_rules.py`).

### G05 Mất thẻ xe, xin cấp lại

- **Mục tiêu.** "Tôi mất thẻ xe máy." Khóa ngay, rồi xin thẻ mới.
- **Điều kiện.** `an` có xe máy và thẻ xe `active`; còn hạn mức thẻ.
- **Diễn biến.** Cư dân báo mất: thẻ `lost` ngay, các lượt quẹt sau đó bị từ chối. Cư dân tạo đơn dịch vụ **cấp lại** (nháp), tự gửi; lễ tân xem xét, duyệt, cấp thẻ mới (`pending_issue`→`active`); thẻ cũ `lost`→`revoked`.
- **Ràng buộc.**
  - Báo mất là việc nhỏ của agent (khóa thẻ là hướng an toàn); cấp lại chỉ là nháp, cư dân gửi.
  - Thẻ không phải của người đó hoặc căn đó: 403. Thẻ đã `lost`/`revoked`: 409.
  - Cấp lại tạo khoản phí nếu cấu hình có phí; phí vào công nợ khi `fulfilled`.
  - Không hiện số giấy tờ tùy thân hay ảnh khuôn mặt cho agent.
- **Chấp nhận.**
  1. Báo mất thẻ `active` của chính mình: thẻ `lost`, có dấu vết.
  2. Báo mất thẻ của người căn khác: 403.
  3. Lượt quẹt bằng thẻ `lost`: `denied` với lý do.
  4. Đơn cấp lại: `draft` → cư dân gửi → `submitted` → lễ tân duyệt → `fulfilled`; thẻ mới `active`, thẻ cũ `revoked`.
  5. Agent đổi đơn từ `draft` sang `submitted`: 403 (chuyển này chỉ cư dân).
  6. Vượt hạn mức thẻ của căn khi cấp: 409.

### G06 Đặt tiện ích và hủy

- **Mục tiêu.** "Đặt khu BBQ 18:00 thứ bảy cho 6 người."
- **Điều kiện.** Tiện ích có lịch mở theo thứ, khung giờ, hạn mức mỗi tuần mỗi căn, giá (có thể 0); có một lịch đóng bảo trì.
- **Diễn biến.** Xem khung giờ trống; đặt; nếu miễn phí → `confirmed`; nếu có phí → `pending_payment` (thanh toán thật ngoài phạm vi, giữ chỗ tối đa 15 phút). Hủy trước hạn `cancel_before_hours`.
- **Ràng buộc.**
  - Không đặt trùng khung giờ cùng khu; không đặt vào lịch đóng; không vượt hạn mức tuần; không vượt số ngày đặt trước.
  - Hủy sát giờ (trong `cancel_before_hours`): từ chối. Lịch đóng được tạo sau: các lượt `confirmed` bị hủy bởi hệ thống, thông báo cho chủ lượt.
  - Hai người cùng đặt một khung giờ cùng lúc: đúng một người thành công.
- **Chấp nhận.**
  1. Khung giờ trống: đặt `confirmed` (miễn phí) hoặc `pending_payment` (có phí).
  2. Đặt trùng: 409. Đặt vào lịch đóng: 409. Vượt hạn mức tuần: 409.
  3. Hai yêu cầu đồng thời cho cùng khung giờ: một 201, một 409.
  4. Hủy trước hạn: `cancelled`; hủy sát giờ: 409.
  5. `pending_payment` quá 15 phút: `expired` khi đọc hoặc khi chạy tác vụ dọn.
  6. Agent hủy lượt của người khác: 403.

### G07 Hỏi quy định thi công, xem đơn thi công

- **Mục tiêu.** "Nhà tôi cải tạo thì làm giờ nào, đặt cọc bao nhiêu, đơn của tôi tới đâu rồi?"
- **Điều kiện.** Quy định thi công của phân khu (giờ làm, giờ ồn, ngày nghỉ, mức cọc, số thợ tối đa); `an` có một đơn `approved`/`in_progress`.
- **Diễn biến.** Cư dân hỏi quy định (đọc từ tri thức hoặc công cụ đọc quy định); xem danh sách đơn thi công của căn và dòng thời gian trạng thái.
- **Ràng buộc.** Quy định đúng phân khu và loại căn của người hỏi; chỉ đọc. Tạo đơn thi công là Đặc tả (làm sau).
- **Chấp nhận.**
  1. Quy định trả về đúng phân khu và loại căn; căn biệt thự có thể có quy định khác căn hộ.
  2. `an` thấy đơn của căn mình với trạng thái và các mốc thời gian; không thấy đơn căn khác.
  3. Trạng thái nằm trong từ điển; chuyển trạng thái ngoài từ điển bị cơ sở dữ liệu chặn.

### G08 Thông báo cắt nước theo kế hoạch

- **Mục tiêu.** BQL báo trước 24 giờ cho đúng các tòa bị ảnh hưởng; cư dân hỏi "khi nào cắt nước?".
- **Điều kiện.** Một lịch cắt nước cho tòa `S1.01`; cư dân `an`, `chau` ở `S1.01`, `binh` ở `S1.02`.
- **Diễn biến.** Nhân viên (hoặc agent soạn nháp) tạo thông báo loại cắt dịch vụ với khung giờ và tòa; BQL phát hành; hệ thống tạo thông báo cho cư dân **đã xác minh** của các tòa đó, một lần mỗi người; cư dân hỏi và được trả lời từ thông báo.
- **Ràng buộc.** Agent chỉ soạn nháp; **phát hành là việc của BQL**. Không gửi cho tòa không bị ảnh hưởng, không gửi cho người chưa xác minh, không gửi trùng.
- **Chấp nhận.**
  1. Nháp do agent soạn có `drafted_by='agent'`, trạng thái `draft`, chưa có thông báo nào gửi.
  2. BQL phát hành: đúng số người nhận (`an`, `chau`, các cư dân xác minh của `S1.01`); `binh` và `em` không nhận.
  3. Phát hành lại: không tạo thông báo trùng.
  4. Cư dân `S1.01` hỏi lịch cắt nước thấy khung giờ; cư dân `S1.02` không thấy thông báo này.

### G09 Phân quyền theo vai trò cư trú

- **Mục tiêu.** Cùng một thao tác, người khác nhau được phép khác nhau.
- **Điều kiện.** `an` (chủ), `chau` (thành viên), `binh` (người thuê, căn khác), `em` (chờ xác minh), `dung` (hai căn).

| Thao tác | chủ | người thuê | thành viên hộ | chờ xác minh |
|---|---|---|---|---|
| Xem công nợ căn | được | được | không | không |
| Báo sự cố trong căn | được | được | được | không |
| Đồng ý phương án có chi phí | được | được | không | không |
| Đăng ký khách | được | được | được | không |
| Báo mất thẻ của mình | được | được | được | không |
| Xem đơn thi công | được | được | không | không |

- **Ràng buộc.** Quyền tính ở máy chủ từ liên kết cư trú, không tin ID người dùng do máy khách gửi. Liên kết hết hạn (`valid_to`) hoặc bị thu hồi thì mất quyền ngay, kể cả với token ủy quyền còn hạn.
- **Chấp nhận.**
  1. Mỗi ô của bảng trên được kiểm (được: 2xx; không: 403).
  2. Thu hồi liên kết của `chau`: token ủy quyền đang có của `chau` mất hiệu lực ở lần gọi kế tiếp.
  3. `dung` chọn căn: dữ liệu chỉ của căn đó.

### G10 Nhân viên hiện trường nhận việc và hoàn thành

- **Mục tiêu.** `hoa` thấy việc được giao, nhận, làm, gửi bằng chứng.
- **Điều kiện.** Phiếu việc đã chào cho `hoa`.
- **Diễn biến.** Xem việc của mình; nhận kèm giờ dự kiến đến; `accepted→en_route→arrived→in_progress→completed`; ảnh bằng chứng; có thể xin khóa nước hoặc đề xuất sửa chữa có giá.
- **Ràng buộc.** Mỗi bước kiểm phiên bản (409 khi lệch). Hoàn thành cần bằng chứng phù hợp. Nhân viên chỉ thấy việc của mình. Agent đọc việc của nhân viên thay mặt, không đổi trạng thái.
- **Chấp nhận.**
  1. `hoa` thấy đúng các phiếu của mình, không thấy của người khác.
  2. Chuỗi trạng thái đi đúng thứ tự; nhảy bước: 409.
  3. Hoàn thành thiếu bằng chứng: bị từ chối.
  4. `khoa` (nghỉ phép) không nhận được việc mới.
  5. Mỗi lần việc được chào cho một nhân viên (giao tay, phương án được duyệt hay việc trong hàng đợi) có đúng một thông báo chưa đọc cho người đó, đọc qua `GET /my/notifications`; người khác không có. Chào lại sau khi bị từ chối thì thông báo lại (`test_staff_notifications.py`, migration `0010`).
  6. App nhân viên hỏi lại danh sách việc mỗi 5 giây khi hiện và mỗi 30 giây khi tab bị ẩn, và số việc mới hiện ở tiêu đề tab. Chưa có đẩy thông báo (push, SMS, email) khi không mở app: cần nhà cung cấp dịch vụ.

### G11 Quản lý hỏi tổng hợp

- **Mục tiêu.** "Tòa nào nhiều sự cố nhất tháng này? Việc nào đang quá hạn?"
- **Điều kiện.** Lịch sử yêu cầu 6 tháng; hạn xử lý theo chính sách.
- **Diễn biến.** `minh` xem tần suất sự cố theo tòa/tháng, danh sách yêu cầu quá hạn xử lý theo ưu tiên, hiệu suất theo nhân viên.
- **Ràng buộc.** Chỉ trong phạm vi quản lý của người hỏi. Báo cáo không tiết lộ thông tin cá nhân cư dân ngoài cần thiết.
- **Chấp nhận.**
  1. Tần suất theo tòa khớp số đếm trực tiếp trên dữ liệu.
  2. Danh sách quá hạn gồm đúng các yêu cầu chưa đóng có hạn xử lý đã qua; không có yêu cầu ngoài phạm vi của `minh`.
  3. Cư dân gọi các báo cáo này: 403.

### G12 Yêu cầu quá hạn, cảnh báo chủ động

- **Mục tiêu.** Hệ thống tự phát hiện yêu cầu sắp hoặc đã quá hạn, phát sự kiện; agent đề xuất cách xử lý (giao lại, nhắc, leo thang); BQL quyết định.
- **Điều kiện.** Chính sách hạn theo nhóm dịch vụ và ưu tiên; một yêu cầu đã quá hạn.
- **Diễn biến.** Khi yêu cầu được tạo, hệ thống gán hạn phản hồi và hạn xử lý theo chính sách (chưa làm trong gói). Một tác vụ định kỳ quét các yêu cầu chưa đóng và phát `ticket.sla_warning`/`ticket.sla_breached`. Platform nhận sự kiện qua nguồn sự kiện, gửi đề xuất qua cổng hồ sơ; BQL xem và quyết định.
- **Ràng buộc.** Mỗi yêu cầu chỉ phát cảnh báo cùng loại một lần. Agent không tự đổi người phụ trách.
- **Chấp nhận.**
  1. Yêu cầu tạo mới có hạn phản hồi và hạn xử lý theo chính sách.
  2. Yêu cầu quá hạn phát đúng một sự kiện `ticket.sla_breached`; chạy lại tác vụ không phát thêm.
  3. Nguồn sự kiện trả sự kiện theo thứ tự, theo con trỏ, không mất không trùng khi đọc tiếp từ con trỏ.
  4. Đề xuất của agent hiển thị cho BQL ở dạng chờ duyệt, không đổi dữ liệu nào trước khi BQL quyết định.

### G13 Yêu cầu báo qua lễ tân hiện trong danh sách của cư dân

- **Mục tiêu.** Mọi yêu cầu do cư dân khởi đầu, báo qua trò chuyện với lễ tân hay gửi bằng biểu mẫu của ứng dụng, đều có **hồ sơ cư dân**: cư dân thấy nó trong danh sách, theo dõi dòng thời gian công khai, xác nhận hoặc yêu cầu làm lại khi có kết quả.
- **Điều kiện.** Cư dân đã xác minh, có một căn.
- **Diễn biến.** Cư dân báo sự cố cho lễ tân; lễ tân bàn giao. Khi yêu cầu được tạo, cơ sở dữ liệu tạo kèm hồ sơ và nối với yêu cầu (hàm `app_ensure_case`). Một cuộc trò chuyện có tối đa một hồ sơ; yêu cầu thứ hai của cùng cuộc trò chuyện được thêm vào hồ sơ đó, và hồ sơ đã hoàn tất sẽ mở lại. Yêu cầu đã có từ trước được tạo hồ sơ khi nâng cấp (migration `0009`); yêu cầu đã hủy hoặc không có căn thì không có hồ sơ.
- **Ràng buộc.** Cư dân không thấy mã nội bộ (`VH-…`). Yêu cầu nhân viên tạo từ hồ sơ có sẵn (biểu mẫu) không tạo hồ sơ thứ hai.
- **Chấp nhận.**
  1. Sau bàn giao, yêu cầu có đúng một hồ sơ, trạng thái đang xử lý.
  2. `GET /resident/requests?filter=open` của cư dân có hồ sơ đó.
  3. Dòng thời gian bắt đầu bằng "Đã tiếp nhận phản ánh" và "Đã chuyển phản ánh đến bộ phận xử lý".
  4. Không mã nội bộ nào xuất hiện trong danh sách hay chi tiết.
  5. Gọi lại `app_ensure_case` không tạo thêm hồ sơ.

## 6. Đã làm đến đâu và kiểm bằng gì

| Kịch bản | Test (`services/vinhomes-api/tests/test_golden.py`) | Phần chưa làm |
|---|---|---|
| G01 | `test_G01_a_resident_asks_what_the_home_owes` | thanh toán thật |
| G02 | `test_G02_a_leak_from_report_to_an_approved_plan…` (và `test_request_presentation.py`) | nháp yêu cầu sự cố do agent ngoài tạo: hiện chỉ Reception của domain làm |
| G03 | `test_G03_an_emergency_reaches_management_once…` | |
| G04 | `test_G04_a_visitor_is_announced_checked_at_the_gate…` | khách không cần duyệt theo cấu hình phân khu (đang là quy tắc mặc định cố định) |
| G05 | `test_G05_a_lost_card_is_locked_at_once…` | phí cấp lại vào công nợ |
| G06 | `test_G06_booking_an_amenity_never_double_books…` | thanh toán thật; hoàn tiền khi hủy |
| G07 | `test_G07_renovation_rules_and_permits` | tạo và xử lý đơn thi công |
| G08 | `test_G08_a_planned_outage_is_drafted_by_an_agent…` | |
| G09 | `test_G09_what_each_kind_of_resident_may_do` | |
| G10 | `test_G10_field_staff_see_only_their_jobs…` (+ `test_staff_dispatch.py`, `test_staff_notifications.py`) | thông báo ngoài app (push, SMS, email) |
| G11 | `test_G11_a_manager_asks_what_is_overdue…` | |
| G12 | `test_G12_a_late_request_warns_once…` | nhắc nợ chủ động, nhắc người phụ trách |
| G13 | `test_G13_a_request_reported_to_reception_shows_in_the_residents_list` | chưa có test cho bước nhân viên công bố kết quả và cư dân xác nhận trên hồ sơ tạo từ lễ tân (cùng bảng và cùng luồng với hồ sơ tạo từ biểu mẫu, nhưng chưa thử) |
| tri thức | `test_the_knowledge_pack_keeps_management_documents_out…` | |

Ghi chú về mã lỗi: một thao tác agent không có trong danh mục luôn trả **404**; thao tác có trong danh mục nhưng sai persona hoặc mức trả **403**. Chỗ nào bản đặc tả trên ghi "403" cho agent gọi thao tác cấm, thực tế là 404 (không lộ rằng nó tồn tại), theo hợp đồng §3.3.
