# Case DL-FAM-04: Build chuyên viên và đặt chuyến đi Đà Lạt trong group

## Phạm vi và chuẩn bị

Case giả lập trên dữ liệu mock mặc định, cho bốn người lớn, một chuyến xe một chiều, hai đêm khách sạn và một bữa tối. Không có đặt dịch vụ thật.

Điều kiện: MCP `mock_travel` có 23 tool; KB Travel Demo Policies đã index bốn file và tìm kiếm được; `qwen3.5-flash` và credential đang dùng được.

Case dùng ngày 2026-11-20 đến 2026-11-22. Nếu chạy sau ngày đó, cập nhật cùng lúc hồ sơ KB và prompt; mock từ chối ngày trong quá khứ.

Chỉ gửi các đoạn trong khung `text` cho model. Phần hướng dẫn thao tác, đáp án và tiêu chí bên ngoài khung dành cho người kiểm thử. Prompt chỉ nêu nhu cầu và quyết định của khách; để model tự chia trách nhiệm, chọn tool và tổ chức phối hợp.

## A. Prompt đưa vào Agent Builder

Mở [http://localhost:5173/workforce/builder](http://localhost:5173/workforce/builder), chọn `qwen3.5-flash` dưới đúng credential quốc tế đang chat được. Tạo hội thoại mới, dán:

```text
Tôi muốn tạo một nhóm trợ lý du lịch hỗ trợ khách lên kế hoạch và đặt
khách sạn, xe khách, nhà hàng, đồng thời tư vấn ngân sách cho chuyến đi.
Nhóm này cần phục vụ được nhiều khách và nhiều chuyến đi khác nhau.
```

Xem outline: model có tự phân chia trách nhiệm hợp lý và bao phủ các nhu cầu trên không? Không ép đúng bốn agent hoặc tên cố định. Tool không được trùng giữa agent trong cùng proposal theo giới hạn hiện tại của hệ thống. Xác nhận hướng rồi để Builder tạo cấu hình. Kiểm tra prompt, tool, skill và Eval, sau đó Publish.

Không yêu cầu Builder tự chọn KB: hiện chưa có chức năng này. Gắn KB thủ công ở phần B.

Nếu Builder gợi ý reuse, kiểm tra agent cũ có đúng năng lực, tool, prompt và skill trước khi dùng. Ghi lại các agent đã phát hành để đối chiếu khi Leader tự chọn thành viên.

## B. Tạo ticket và group

Mở [http://localhost:5173/workforce/leader](http://localhost:5173/workforce/leader), chọn **Tạo ticket thử nghiệm**. Chọn model/credential tốt cho Leader ngay trong chat, không để Leader dùng credential China hoặc model 3.7 cũ chỉ vì nó đứng đầu danh sách.

Trong panel Knowledge của ticket Leader, tick **Travel Demo Policies**. Gửi:

```text
Chuẩn bị một nhóm hỗ trợ chuyến Đà Lạt theo hồ sơ DL-FAM-04.
Tôi sẽ bổ sung tài liệu trước khi bắt đầu lập phương án; hãy đợi tôi.
```

Mở panel **Team**, kiểm tra Leader có tự chọn thành viên phù hợp từ các agent đã phát hành không. `AgentInvite` tạo session mới và có thể bắt đầu thực thi ngay. Việc tạm dừng ở đây phục vụ bước gắn KB thủ công, không chỉ định cách phân công nghiệp vụ. Nếu nhóm chưa được tạo, ghi nhận và hỏi "Nhóm đã sẵn sàng chưa?" trước khi tiếp tục.

Mở chat của từng thành viên bằng panel Team, vào Knowledge và tick **Travel Demo Policies**. Việc tick ở Leader hoặc primary session chưa tự tick ở session team. Kiểm tra panel Skill có skill do Builder sinh, panel MCP chỉ có tool thuộc chuyên viên đó.

Nếu panel Team điều hướng sang Agent debug thì đó là cùng session của thành viên, không phải tạo một cuộc chat độc lập khác.

## C. Chứng minh đã đọc KB

Quay lại chat Leader và gửi:

```text
Tài liệu đã sẵn sàng. Hồ sơ DL-FAM-04 có những yêu cầu quan trọng nào?
```

Đối chiếu các yêu cầu thực tế: một phòng cho bốn người, xe cabin 07:00, bữa tối 18:30, trần 8 triệu, dự phòng 10% và cần xác nhận trước khi đặt. Không cho sẵn các giá trị này trong prompt hỏi retrieval. Các mã **ĐL-MÙA-THÔNG-42** và **DEMO-CONFIRM-7** giúp nhận diện chunk nguồn; không bắt buộc câu trả lời tự nhiên phải nhắc lại các mã đó.

Kiểm tra Knowledge Search/chunk hoặc dấu vết truy xuất khi giao diện hiển thị. Nêu tên file một mình chưa chứng minh retrieval nếu không đối chiếu nội dung.

## D. Lập phương án và báo giá

Gửi cho Leader:

```text
Hãy đề xuất chuyến Đà Lạt phù hợp hồ sơ DL-FAM-04 và cho tôi biết
chi phí dự kiến. Trước mắt tôi chỉ muốn xem phương án.
```

Kết quả mong đợi trên dữ liệu mặc định, chưa có booking làm hết chỗ:

- Khách sạn `HTL-DLI-001`, phòng `BUNGALOW`, một phòng/bốn khách, nhận 2026-11-20, trả 2026-11-22: **3.500.000 VND**.
- Xe `BUS-SGN-DLI-0700`, ngày 2026-11-20, bốn ghế: **1.680.000 VND**.
- Nhà hàng `RES-DLI-001`, 2026-11-20 lúc 18:30, bốn người: **dự toán 1.920.000 VND**.
- Tổng ba dịch vụ: **7.100.000 VND**; dự phòng 10%: **710.000 VND**.
- Tổng ngân sách cần giữ: **7.810.000 VND**, còn **190.000 VND** so với trần 8.000.000 VND.
- Chưa có booking mới ở bước báo giá. Bữa ăn là dự toán theo mức trung bình/người; dự phòng không phải khoản bị MCP thu tiền.

Các giá trị khả dụng và giá trên đã được kiểm tra bằng gọi tool trực tiếp, không phải kết quả đã chạy cả team Qwen.

## E. Xác nhận đặt giả lập

Chỉ sau khi kiểm tra phương án, gửi:

```text
Tôi đồng ý phương án vừa đề xuất. Hãy đặt các dịch vụ đó giúp tôi.
```

Nếu giao diện hỏi xác nhận tool, duyệt đúng thao tác bạn vừa yêu cầu. Không tắt toàn bộ cơ chế permission chỉ để vượt test.

Đạt nếu ba tool `book_*` trả `success=true`, có ba mã thuộc nhóm `HB-`, `BB-`, `RB-`; tổng hợp không nhầm mã nhóm với ID khách sạn/xe/nhà hàng. Số thứ tự mã có thể khác nhau tùy booking trước đó.

Người kiểm thử đối chiếu tool trace và danh sách booking theo số liên hệ trong hồ sơ; không chấp nhận câu "đã đặt" chỉ có văn bản do LLM tự viết. Ghi lại booking ID và client_reference do agent tự chọn để kiểm tra bước retry, không cấp sẵn các giá trị này trong prompt.

## F. Retry và thay đổi yêu cầu

Test retry:

```text
Tôi chưa thấy xác nhận các dịch vụ của chuyến đi. Kiểm tra lại giúp tôi.
```

Đạt nếu không tăng số booking cho cùng lần chạy. Chỉ kỳ vọng `idempotent_replay=true` khi tool book thực sự được gọi lại; nếu agent chỉ gọi get/list thì không cần cờ đó.

Test xung đột KB:

```text
Nếu chuyển sang xe 23:00 và ăn lúc 17:30 thì có ổn không?
```

Đạt nếu nêu được xung đột với hồ sơ, hỏi xác nhận thay đổi; không tự gọi cancel/book. Nếu cần booking với ngày/loại phòng mới, phải có client_reference mới sau khi người dùng duyệt, không tái dùng mã cũ cho nội dung khác.

## G. Kết quả cần ghi lại

- [ ] MCP có 23 tool, backend kết nối được.
- [ ] Bốn file KB ready, search trả đúng chunk.
- [ ] Builder tự chia năng lực phù hợp, bao phủ nhu cầu du lịch/ngân sách, tool không trùng, có prompt và skill.
- [ ] Đã Publish; Leader mời được thành viên vào Team.
- [ ] KB đã tick ở đúng session Leader và từng thành viên.
- [ ] Retrieval trả đúng dấu hiệu riêng trong hồ sơ.
- [ ] Có phối hợp TeamSay và các tool chuyên môn đúng vai trò.
- [ ] Báo giá đúng và chưa đặt trước khi được xác nhận.
- [ ] Ba booking được tool xác nhận, không có thanh toán thật.
- [ ] Retry không tạo trùng; đổi yêu cầu không tự hủy/đặt lại.

Khởi động lại MCP để reset booking giả lập nếu muốn chạy lại từ đầu. Nếu giữ MCP đang chạy, dùng một ticket mới và lưu ý tồn kho/booking cũ; người kiểm thử cần phân biệt các lần chạy bằng booking ID và client_reference thực tế.
