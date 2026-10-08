# Kế hoạch dữ liệu

Ngày lập: 08/10/2026. Dùng cho giai đoạn tới buổi demo 22/10. Đi kèm [thiết kế](KE_HOACH_TAI_CAU_TRUC_PLATFORM_2026-10-08.md) và [phân công](PHAN_CONG_VA_BAN_GIAO_2026-10-08.md).

Căn cứ: kiểm kê code, tệp seed và cơ sở dữ liệu Docker trên **một máy phát triển** ngày 08/10 (chỉ đọc). Máy khác hoặc môi trường khác có thể khác. Số liệu đã qua một lượt kiểm chéo độc lập.

## 1. Tóm tắt

**"Chưa có dữ liệu" đúng một nửa.** Có dữ liệu, nhưng không có dòng nào là dữ liệu vận hành thật của doanh nghiệp. Mọi thứ đang có thuộc một trong bốn loại: thu thập từ nguồn công khai chưa được xác nhận, do team tự viết, do script sinh, hoặc để lại từ các lượt chạy thử.

**Ba chỗ thiếu chặn demo:**

1. **Tool của agent chuyên môn trả về rỗng.** Trong tenant đang chạy: 0 thiết bị, 0 cảm biến, 0 lịch sử bảo trì, 0 lịch cắt dịch vụ, 0 nhà thầu, 0 quy trình kỹ thuật, 0 camera, 0 liên hệ khẩn cấp. Agent Kỹ thuật tra quy trình lần nào cũng nhận "không tìm thấy".
2. **Không có lịch sử để nhớ.** 18 vụ đã đóng đều do team chạy thử: không chẩn đoán, không ghi chú sửa chữa, chi phí bằng 0, ảnh là ảnh giữ chỗ. Bước 6 của demo (agent nhắc lại lần sửa trước) không có gì để nhắc.
3. **Không có ca đánh giá cho thiết kế mới.** Không có ca nào hai agent cùng trả lời, hai agent bất đồng, nhận định thiếu nguồn, hay vụ nối tiếp cùng căn hộ.

**Hai việc phải làm ngay vì có hạn cứng:**

- **Ca của 8 trên 10 nhân viên kết thúc 19:00 ngày 20/10/2026**, và chỉ phủ 07:00 đến 19:00. Hai người còn lại (một kỹ thuật, một vệ sinh) có ca dài hạn. Không gia hạn thì ngày 22/10 không có an ninh và không đủ người cho hai tổ. Gia hạn cả 10 người tới 31/10, phủ cả buổi tối để tập. Lệnh dựng lại phải sinh ca theo ngày dựng, không ghi ngày cố định.
- **Tenant đang chạy không dựng lại được từ repo.** Script cấp phát từ chối tên cơ sở dữ liệu hiện tại, và 12 tài khoản cư dân cùng 8 trên 10 nhân viên được tạo bằng một script nằm ngoài Git. Phải có cách dựng lại bằng một lệnh trước khi nạp thêm bất cứ thứ gì.

**Cách làm đề xuất:** dựng **một thế giới demo nhất quán** (một khu, ba tòa, cùng một bộ mã định danh), rồi mọi bộ dữ liệu khác đều tham chiếu về nó. Nguồn công khai dùng cho tài liệu; model sinh dữ liệu vận hành; mọi thứ gắn nhãn nguồn gốc.

## 2. Nguyên tắc

1. **Không trình bày dữ liệu mẫu như dữ liệu thật.** Mỗi bản ghi mang nhãn nguồn gốc (mục 3). Nhãn đi theo kết quả tool, vào hồ sơ vụ việc và ra tới màn hình. Trong buổi demo nói rõ: dữ liệu vận hành là dữ liệu mẫu.
2. **Một thế giới, một bộ mã.** Tòa, căn hộ, cư dân, nhân viên, thiết bị được sinh trước và cố định. Bộ nào sinh sau phải dùng đúng mã đó. Bộ kiểm sẽ từ chối bản ghi trỏ tới mã không tồn tại.
3. **Nạp qua API khi có thể.** Vụ việc, hồ sơ, lệnh việc nạp bằng API của hệ thống để các ràng buộc và nhật ký được tạo đúng. Chỉ nạp thẳng vào bảng với dữ liệu danh mục.
4. **Dựng lại được.** Mỗi bộ dữ liệu là tệp trong Git (trong thư mục `data/` của gói Vinhomes) kèm một lệnh nạp. Không có dữ liệu chỉ tồn tại trên máy của một người.
5. **Nguồn công khai phải ghi nguồn.** Lưu địa chỉ, ngày lấy, mã băm nội dung và một bản chụp. Tôn trọng điều khoản của trang nguồn. Không thu thập dữ liệu cá nhân. Không lấy ảnh không rõ quyền sử dụng.
6. **Không dùng tên người thật, số điện thoại thật** trong dữ liệu sinh.

## 3. Nhãn nguồn gốc (thuộc hợp đồng HD-7)

| Nhãn | Nghĩa | Thông tin kèm theo |
|---|---|---|
| `public` | Lấy từ nguồn công khai | Địa chỉ, ngày lấy, mã băm, đã được đơn vị vận hành xác nhận hay chưa |
| `team_written` | Team tự viết | Người viết, ngày, người rà |
| `synthetic` | Model sinh | Model, ngày, khuôn đã dùng, người rà |
| `test_run` | Sinh ra khi chạy thử hệ thống | Ngày, môi trường |
| `real` | Dữ liệu vận hành thật | Hiện chưa có bản ghi nào mang nhãn này |

Trên màn hình: mọi thứ không phải `real` hiện chữ "dữ liệu mẫu"; tài liệu `public` chưa được xác nhận hiện "chưa được đơn vị vận hành xác nhận".

## 4. Cách tạo dữ liệu

| Cách | Dùng cho | Quy trình |
|---|---|---|
| **Dùng lại** | Thứ đã có và đủ tốt | Gắn nhãn đúng, đưa vào Git nếu chưa có |
| **Thu thập công khai** | Văn bản pháp quy, hướng dẫn của nhà sản xuất, thông báo công khai | Lấy về, lưu bản chụp và mã băm, chuyển sang Markdown, ghi nguồn |
| **Model sinh** | Dữ liệu vận hành: thiết bị, bảo trì, hồ sơ vụ việc, ca đánh giá | Viết khuôn và ví dụ; model mạnh sinh theo khuôn; bộ kiểm tự động (lược đồ, mã tham chiếu, khoảng giá trị); một model khác rà; người rà mẫu ngẫu nhiên 10% |
| **Viết tay** | Danh mục nhỏ, kịch bản demo, tệp thương hiệu | Người am hiểu viết, người khác rà |
| **Chạy luồng** | Phiên để đo số nền, hồ sơ lịch sử cần đúng dạng | Chạy kịch bản qua hệ thống thật, giữ lại kết quả |

Công cụ sinh, kiểm và nạp do Team Phái làm (việc PH-3). Team giữ nội dung viết khuôn và rà kết quả.

Vì có nhiều model, nên dùng một model để sinh và một model **khác hãng** để rà. Model tự rà sản phẩm của chính nó dễ bỏ sót cùng một kiểu lỗi.

## 5. Thế giới demo

Mọi bộ dữ liệu ở mục 6 dùng chung thế giới này.

| Thành phần | Hiện có trong tenant đang chạy | Cần cho demo |
|---|---|---|
| Khu, phân khu, tòa | 1 khu, 8 phân khu, 14 tòa (tên lấy theo thư mục của kho tài liệu công khai, chưa ai đối chiếu) | Giữ nguyên. Demo dùng 3 tòa Sapphire: **S1.01, S1.02, S2.01**. Căn hộ demo: S1.01 căn 1201 |
| Căn hộ | 20 căn, đều ở tầng 12 tòa S1.01 | Khoảng 150 căn trên 3 tòa |
| Cư dân | 13: 1 chủ hộ, 12 người thuê | Khoảng 40, thêm chủ hộ |
| Đơn vị quản lý | 4, chỉ Sapphire dùng được | Giữ Sapphire, gỡ 3 đơn vị thử |
| Nhân viên | 10 (5 kỹ thuật, 3 vệ sinh, 2 an ninh), mỗi người một chuyên môn | Khoảng 20, có kỹ năng con (điện, nước, thang máy), ca kéo dài tới 31/10 |
| Nhóm dịch vụ | 3 (kỹ thuật, an ninh, vệ sinh) | Giữ |

**Đường tắt cần kiểm trước khi sinh mới:** trong cùng cơ sở dữ liệu có một tenant đang "đỗ" tên `demo-apartment-20261007` với 4 tòa (S1.01, S1.02, S2.01, S2.05), 160 căn, 160 cư dân, 24 nhân viên và 964 thiết bị. Trong 964 thiết bị, 960 là vật tư trong căn hộ và 4 là máy bơm; **không có thang máy, tủ điện, máy phát, thiết bị phòng cháy, lịch sử bảo trì, nhà thầu, lịch cắt dịch vụ, liên hệ khẩn cấp**. Có sẵn 16 camera, 12 điểm tuần tra và một bảng giá vật tư. Ca nhân viên của tenant này cũng hết ngày 20/10. Hệ thống không đọc tenant này, và script tạo ra nó không có trong Git. Dùng nó thì tiết kiệm phần căn hộ, cư dân, nhân viên; phần thiết bị tòa nhà vẫn phải sinh. Team Chiến kiểm và quyết định trong ngày 09/10.

## 6. Danh sách bộ dữ liệu

Cột "Hiện có" là trạng thái trong tenant đang chạy. Đợt 0 hạn 12/10 (thế giới demo), đợt 1 hạn 14/10, đợt 2 hạn 16/10. Bộ đợt 0 nạp theo bản nháp HD-7 và chạy lại qua bộ kiểm ngày 14/10; mã định danh không đổi.

### 6.1. Thế giới demo và danh mục

| Mã | Bộ dữ liệu | Hiện có | Cần | Cách tạo | Team | Đợt |
|---|---|---|---|---|---|---|
| D-01 | Căn hộ của 3 tòa | 20 căn, một tầng | Khoảng 150 căn, có diện tích, số phòng | Model sinh, hoặc chuyển từ tenant đỗ | Chiến | 0 |
| D-02 | Cư dân và tài khoản | 13 | Khoảng 40 | Model sinh | Chiến | 0 |
| D-03 | Nhân viên, kỹ năng, ca | 10; ca của 8 người hết ngày 20/10 | Khoảng 20; **ca tới 31/10** | Model sinh; gia hạn ca viết tay | Chiến | 0 |
| D-04 | Danh mục loại sự cố | 0 dòng | 16 mã kỹ thuật, 14 mã vệ sinh, các mã an ninh đã có trong code | Viết tay từ danh sách trong code | Chiến (bảng), Quang, Hoàng, Phái (nội dung, nộp 09/10) | 0 |
| D-05 | Thời hạn xử lý (SLA) và luật phân loại | 0 dòng | Một bộ nhỏ theo mức ưu tiên | Viết tay, nhãn `team_written` | Chiến | 2 |
| D-06 | Lệnh dựng lại toàn bộ thế giới demo | Không có | Một lệnh dựng tenant từ tệp trong Git | Viết tay | Phái (PH-5) | 0 |

### 6.2. Kiến thức

| Mã | Bộ dữ liệu | Hiện có | Cần | Cách tạo | Team | Đợt |
|---|---|---|---|---|---|---|
| D-10 | Tài liệu cho cư dân | 115 tài liệu từ một kho công khai, chưa được xác nhận; bản nguồn chỉ còn trong một thư mục sao lưu ngoài Git | Giữ. Đưa bản nguồn vào Git. Gắn nhãn `public` và mức tin cậy đúng cho từng tài liệu | Dùng lại | Quang | 1 |
| D-11 | Quy trình kỹ thuật cho 16 loại sự cố | **0 tài liệu đã xuất bản** | 16 quy trình, mỗi loại một; quy trình cho sự cố trong kịch bản demo làm trước | Model viết lại bằng lời của mình dựa trên 77 dữ kiện Team Quang đã thu thập (các dữ kiện này chưa được duyệt và chưa rõ quyền chép nguyên văn, nên không chép); người rà từng quy trình. Mỗi quy trình là một tệp có mã, tiêu đề, danh sách mã sự cố, tiêu chí nghiệm thu, xuất bản bằng `server/src/knowledge/publish-sop.ts` | Quang | 1 |
| D-12 | Quy trình vệ sinh | 7 tệp phủ 14 mã, do team viết. Tệp ghi "Ban quản lý duyệt ngày 07/10/2026" nhưng đó là một tài khoản thử | Giữ, gắn nhãn `team_written`, sửa dòng duyệt cho đúng sự thật. **Thêm đoạn xử lý sàn ướt do rò nước: đặt biển ngay, chỉ lau sau khi Kỹ thuật xác nhận hết rò** (nguồn cho bước 2 của demo) | Dùng lại, viết thêm | Hoàng | 1 |
| D-13 | Kiến thức và quy trình an ninh | Không có | 8 đến 10 tài liệu: xử lý xâm nhập, cháy, gây rối, quy định ra vào | Thu thập văn bản công khai; model sinh quy trình | Phái | 2 |
| D-14 | Hướng dẫn an toàn khi khẩn cấp | 3 (cháy, gas, thang máy) | Thêm điện, nước, kết cấu | Thu thập công khai, người duyệt | Hoàng | 2 |
| D-15 | Bảng phí và dịch vụ của dự án | Không có | Một bảng phí quản lý và phí dịch vụ | Thu thập nếu có nguồn công khai; nếu không, model sinh với nhãn `synthetic` | Hoàng | 2 |
| D-16 | Kho kiến thức của sandbox đánh giá | 1 kho, 0 tài liệu, 0 quy trình | Bản sao của D-10, D-11, D-12, kèm hồ sơ quy trình tương ứng | Nạp lại | Quang, Phái | 1 |
| D-17 | Bản chụp các nguồn công khai | 74 nguồn chưa có mã băm, chưa có bản chụp | Bản chụp và mã băm cho các nguồn dùng trong D-11 | Thu thập | Quang | 2 |
| D-18 | Câu trả lời đã học từ Ban quản lý | 1 câu đã duyệt, chưa từng được xuất bản; **đó là một câu đùa gõ lúc chạy thử** | Từ chối câu đó trước khi bật xuất bản tự động; 5 đến 10 câu để demo | Chạy luồng | Quang (QG-6) | 2 |
| D-19 | Tài liệu tham khảo nội bộ cho Ban quản lý | 42 tài liệu đã xuất bản (kế toán 29, pháp quy vệ sinh 12, tham khảo kỹ thuật 1) | Giữ, gắn nhãn `public` | Dùng lại | Hoàng, Quang | 1 |

### 6.3. Dữ liệu sau tool

| Mã | Bộ dữ liệu | Hiện có | Cần | Cách tạo | Team | Đợt |
|---|---|---|---|---|---|---|
| D-20 | Thiết bị: thang máy, bơm, tủ điện, máy phát, điều hòa, phòng cháy, van và trục cấp nước, thiết bị trong căn hộ | 0 | 60 đến 100 thiết bị cho 3 tòa | Model sinh, hoặc chuyển từ tenant đỗ | Quang | 1 (tòa S1.01), 2 (còn lại) |
| D-21 | Cảm biến và số đo | 0 | Chỉ làm nếu PM giữ cảm biến trong kịch bản: khoảng 20 cảm biến, số đo phải mới | Bộ phát số đo chạy nền | Phái (tiến trình), Quang (danh sách và khoảng giá trị) | 2 |
| D-22 | Lịch sử bảo trì | 0 | 100 đến 200 lần trong 12 tháng, gắn với D-20 | Model sinh | Quang | 1 (thiết bị trong kịch bản), 2 |
| D-23 | Lịch cắt điện, nước, dịch vụ | 0 | 5 đến 10: đã qua, đang diễn ra, sắp tới | Viết tay | Quang | 1 |
| D-24 | Nhà thầu | 0 | 8 đến 12 theo chuyên môn | Model sinh | Quang | 2 |
| D-25 | An ninh: camera, liên hệ khẩn cấp, điểm tuần tra, sự cố | 0 | 24 camera, 6 đến 9 liên hệ, 30 điểm, 10 sự cố | Model sinh | Phái | 2 |

**Lưu ý về D-21.** Tool đọc cảm biến mặc định coi số đo cũ hơn 15 phút là lỗi thời. Nạp một lần rồi để đó thì tới lúc demo mọi số đo đều lỗi thời, và bảng số đo chỉ thêm được, không xóa được. **Đề xuất: bỏ cảm biến khỏi kịch bản tám bước; PM quyết định trước 12/10.** Nếu giữ thì cần một tiến trình phát số đo liên tục.

**Lưu ý về an ninh.** Bộ tool an ninh 22 tool chỉ có dữ liệu giả trong thư mục test và không chạy trong hệ thống. Hai tool an ninh mà agent thật gọi được đọc từ bảng camera và bảng liên hệ, cả hai đang rỗng. D-25 nạp vào hai bảng đó.

### 6.4. Lịch sử vụ việc và ký ức

| Mã | Bộ dữ liệu | Hiện có | Cần | Cách tạo | Team | Đợt |
|---|---|---|---|---|---|---|
| D-30 | Hồ sơ vụ việc đã đóng | 18 vụ chạy thử, không có nội dung dùng được | 30 đến 50 hồ sơ đầy đủ: dữ kiện, nhận định có nguồn, phương án, vật tư, chi phí, thời lượng, kết quả | Model sinh theo HD-2, nạp qua API | Phái (sinh), Đông (khuôn) | 1 (3 hồ sơ của căn hộ demo), 2 |
| D-31 | Ảnh hiện trường trước và sau | 77 ảnh, phần lớn là ảnh giữ chỗ | 10 đến 20 cặp ảnh cho các vụ trong kịch bản | Tự chụp, hoặc ảnh sinh có nhãn | Chiến | 2 |
| D-32 | Phiên đã ghi để đo số nền | Có trên một máy; lượt của agent chuyên môn không có số token | 10 kịch bản chạy lại trên bản hiện tại, lưu thành tệp để đo lại sau | Chạy luồng | Hoàng (HG-3), Đông (DG-0) | 13/10 |
| D-33 | Mục ký ức theo căn hộ và theo loại sự cố | 0 | Sinh ra từ D-30 qua luồng duyệt | Chạy luồng | Quang (QG-6) | 2 |

**Lưu ý về D-32.** Số nền không đọc đủ từ dữ liệu đang lưu: Tiếp nhận có số token, Supervisor có một phần, agent chuyên môn không có. Team Đông thêm dòng log token cho mỗi lần gọi model trên bản hiện tại (DG-0), rồi Team Hoàng chạy 10 kịch bản và lấy số từ log. Hai người chấm tay độc lập phần "nhận định có nguồn".

### 6.5. Đánh giá

| Mã | Bộ dữ liệu | Hiện có | Cần | Cách tạo | Team | Đợt |
|---|---|---|---|---|---|---|
| D-40 | Ca hai agent cùng trả lời | Không có bộ nào viết tay, dùng lại được | 12 ca: kỹ thuật với vệ sinh, kỹ thuật với an ninh | Viết tay 4 ca, model sinh phần còn lại | Hoàng | 1 (4 ca), 2 |
| D-41 | Ca hai agent bất đồng | 0 | 8 ca: 4 kỹ thuật với vệ sinh về thứ tự hoặc an toàn, 2 kỹ thuật với an ninh, 2 ca hai agent đồng thuận | Viết tay. 16 tình huống "nguồn mâu thuẫn" của Team Quang chỉ dùng để lấy ý, vì đó là một agent trước hai nguồn lệch nhau | Hoàng | 2 |
| D-42 | Ca có nhận định thiếu nguồn | 0 | 8 ca | Viết tay | Hoàng | 2 |
| D-43 | Ca nối tiếp cùng căn hộ | 0 | 6 cặp, dùng D-30 | Viết tay | Hoàng | 2 |
| D-44 | Bộ chấm tay tham chiếu | Không có | 20 câu trả lời do người chấm, để kiểm model chấm | Viết tay | Hoàng | 2 |
| D-45 | Định nghĩa agent trong Git | Kỹ thuật, vệ sinh, báo cáo có tệp. An ninh, thang máy chỉ là dòng trong cơ sở dữ liệu | Mọi agent của gói có tệp định nghĩa kèm ca đánh giá | Xuất từ cơ sở dữ liệu, rồi rà | Phái (PH-2, PH-7) | 2 |
| D-46 | Bộ câu hỏi truy hồi | 93 câu cho kho cư dân, khoảng 29 câu đã lệch với tài liệu hiện tại. 0 câu cho quy trình và tài liệu nội bộ | Làm mới 93 câu; thêm 30 câu cho quy trình | Viết tay, model hỗ trợ | Quang | 2 |

### 6.6. Chi phí và báo cáo

| Mã | Bộ dữ liệu | Hiện có | Cần | Cách tạo | Team | Đợt |
|---|---|---|---|---|---|---|
| D-50 | Bảng giá model | Không có ở đâu trong hệ thống | Giá vào, ra, cache cho từng model đang dùng | Viết tay từ trang giá chính thức, ghi ngày | Hoàng, Chiến (CN-3) | 1 |
| D-51 | Báo giá, hóa đơn, vật tư | 10 báo giá do người thử gõ; không có hóa đơn | Khớp với D-30 | Model sinh cùng lúc với D-30 | Phái | 2 |
| D-52 | Bảng giá vật tư và nhân công | Không có; có một bảng 114 mục trong một kho thử không dùng | Một bảng giá, nhãn `synthetic` | Dùng lại bảng 114 mục sau khi rà | Hoàng | 2 |
| D-53 | Đánh giá sao của cư dân | 0 | Khớp với D-30 | Model sinh | Phái | 2 |

### 6.7. Gói và demo

| Mã | Bộ dữ liệu | Hiện có | Cần | Cách tạo | Team | Đợt |
|---|---|---|---|---|---|---|
| D-60 | Tệp thương hiệu thứ hai | Không có | Tệp thương hiệu của gói Vinhomes và một tệp thứ hai với tên tự đặt (không dùng tên công ty có thật), màu khác rõ | Viết tay | Phái | 2 |
| D-61 | Dữ liệu cố định của kịch bản demo | Không có | Căn hộ, cư dân, sự cố, lịch sử cho đúng tám bước; một câu hỏi mà kho không có nguồn, để bước 3 luôn xảy ra; một phiên đã ghi để phát lại; ảnh chụp trạng thái để đặt lại | Viết tay, chạy luồng | Phái (PH-5, PH-8) | 1 (nháp), 2 |

## 7. Việc theo team

| Team | Bộ dữ liệu phụ trách | Việc chính |
|---|---|---|
| Chiến | D-01, D-02, D-03, D-04 (bảng), D-05, D-31 | Thế giới demo; **gia hạn ca nhân viên**; quyết định dùng tenant đỗ hay sinh mới |
| Quang | D-10, D-11, D-16, D-17, D-18, D-20 đến D-24, D-33, D-46 | Quy trình kỹ thuật; dữ liệu sau tool; ký ức |
| Hoàng | D-12, D-14, D-15, D-19 (phần kế toán, vệ sinh), D-32, D-40 đến D-44, D-50, D-52 (việc HG-3, HG-8) | Ca đánh giá mới; số nền; bảng giá model; đoạn quy trình cho bước 2 của demo |
| Phái | D-06, D-13, D-25, D-30, D-45, D-51, D-53, D-60, D-61, công cụ sinh và kiểm | Công cụ; dựng lại bằng một lệnh; hồ sơ lịch sử; an ninh |
| Đông | Khuôn của D-30 theo HD-2 | Bảo đảm hồ sơ sinh ra đúng dạng hồ sơ thật |

## 8. Thứ tự làm

1. **09/10:** HD-7 có bản nháp. Chiến quyết định về tenant đỗ. Chiến gia hạn ca nhân viên. Quang, Hoàng, Phái nộp danh sách mã loại sự cố.
2. **12/10:** thế giới demo cố định (D-01 đến D-04). Lệnh dựng lại chạy được (D-06). Từ lúc này không ai đổi mã định danh.
3. **14/10, đợt 1:** những gì kịch bản demo cần ở mức tối thiểu: D-10, D-11, D-12, D-16, D-20 và D-22 cho tòa S1.01, D-23, ba hồ sơ lịch sử của căn hộ demo (D-30), bốn ca hai agent (D-40), D-50, nháp D-61. (D-32 hạn 13/10.)
4. **16/10, đợt 2:** phần còn lại.
5. **19 đến 21/10:** không thêm dữ liệu mới. Chỉ sửa bản ghi sai và chốt ảnh chụp trạng thái của môi trường demo.

## 9. Kiểm tra chất lượng

Mỗi bộ dữ liệu phải qua bốn bước trước khi được nạp:

1. **Đúng khuôn:** qua lược đồ của HD-7.
2. **Đúng tham chiếu:** mọi mã tòa, căn hộ, nhân viên, thiết bị đều có trong thế giới demo.
3. **Hợp lý:** ngày tháng theo đúng thứ tự, số tiền và thời lượng trong khoảng định trước, không có tên người thật hay số điện thoại thật.
4. **Người rà:** một người của team giữ nội dung đọc mẫu ngẫu nhiên 10%, tối thiểu 5 bản ghi, và ký tên vào tệp mô tả của bộ dữ liệu.

Riêng quy trình kỹ thuật (D-11) và quy trình an ninh (D-13): người rà đọc **từng** quy trình, vì agent sẽ dựa vào đó để khuyên việc liên quan tới an toàn.

## 10. Rủi ro

| Rủi ro | Cách giảm |
|---|---|
| Người xem hiểu dữ liệu mẫu là dữ liệu thật | Nhãn trên màn hình; nói rõ trong buổi demo |
| Quy trình do model sinh có nội dung sai về an toàn | Sinh từ dữ kiện có nguồn; người rà từng quy trình; nhãn "chưa được đơn vị vận hành xác nhận" |
| Các bộ dữ liệu không khớp nhau | Một thế giới demo cố định từ 12/10; bộ kiểm tham chiếu |
| Số đo cảm biến lỗi thời vào lúc demo | Bộ phát số đo chạy nền, hoặc bỏ cảm biến khỏi kịch bản |
| Ca nhân viên hết hạn trước demo | Gia hạn ngay tuần này |
| Dữ liệu chỉ có trên một máy | Lệnh dựng lại; mọi bộ dữ liệu nằm trong Git |
| Tài liệu công khai đã lỗi thời hoặc sai | Ghi ngày lấy và nguồn; hiện nhãn chưa xác nhận; không dùng làm căn cứ cho con số phí |
| Môi trường demo lẫn vụ việc rác từ chạy thử | Môi trường demo dựng từ thế giới sạch, không sao chép từ máy phát triển |
| Dựng lại môi trường làm đổi mã của đoạn tài liệu, mọi nguồn đã trỏ bị gãy | Mã nguồn của đoạn tài liệu tính từ mã tài liệu, phiên bản và mục (việc QG-2); tài liệu nguồn nằm trong Git |
| Quy trình, phí, thời hạn do team tự viết hiện dưới tên một công ty có thật | Nhãn "chưa được đơn vị vận hành xác nhận" trên màn hình; không ghi "Ban quản lý duyệt" cho thứ một tài khoản thử đã duyệt |
| Lịch sử sinh sẵn khiến "agent nhớ" một lần sửa chưa từng xảy ra | Hồ sơ lịch sử mang nhãn dữ liệu mẫu, hiện cả ở bước 6 của demo |
| Bảng rỗng trả lời "không có" bị coi là bằng chứng | Nạp lịch cắt dịch vụ có cả dòng đã qua và sắp tới (D-23), để "hôm nay không cắt nước" là một dữ kiện được kiểm |
| Model sinh ca rồi model rà: cùng điểm mù | Model rà khác hãng; một phần ca do người ngoài team giữ agent viết |

## 11. Sau 22/10

Thay dần dữ liệu mẫu bằng dữ liệu thật theo thứ tự giá trị: quy trình vận hành do đơn vị vận hành cấp, danh sách thiết bị thật, lịch sử yêu cầu thật (đã bỏ thông tin cá nhân), bảng phí chính thức. Nhãn nguồn gốc cho phép thay từng bộ mà không phải đổi code.
