# Chẩn đoán Builder/JEV và eval — 17/10/2026

## Kết luận từ dữ liệu đã lưu

JEV đã chạy thành công trong lượt `315492ea9fc4448385da3618b2423c66`. Không có dấu hiệu thiếu API key ở lượt này. Lượt đó có 2 request, 69 câu đánh giá, 40.758 input token và 1.394 output token. Đây là số liệu lịch sử do người dùng chạy, không phải lời gọi kiểm thử trong đợt sửa này.

Code cũ chuyển mọi điểm trùng nằm giữa 0,15 và 0,85 thành “Cần làm rõ”, kể cả giao nhau giữa vai trò chỉ đạt 0,18. Hai ứng viên gần khớp đạt 0,83/0,80 cũng bị dừng trước bước xem xét nâng cấp. Thông báo chung che mất ứng viên và thao tác cần phân biệt.

Đọc 14 báo cáo Builder đã lưu: 42 kết quả ca, 22 đạt, 5 lỗi môi trường `TICKET_GRANT_REQUIRED`, 15 kết quả chưa đạt còn lại. Mẫu có cả các lượt chạy lại, nhiều mục đích khác nhau và báo cáo cũ; không dùng tỷ lệ này làm benchmark chất lượng model hiện tại. Những nhóm thấy được:

- MCP cần ticket/grant nhưng eval dùng connector khám phá: lỗi môi trường, chưa kết luận agent tốt/xấu.
- Skill hướng dẫn tìm kiếm được gắn nhưng không có công cụ tìm kiếm tương ứng: thiếu năng lực thực thi; SKILL.md không tạo API.
- Kịch bản đòi tra cứu nhưng thiếu ngữ cảnh ticket; bộ chấm cũ coi yêu cầu ticket là agent không hoàn thành.
- Ca an toàn về ẩn danh dữ liệu bị đòi xác nhận thêm dù agent đã từ chối tiết lộ và chưa thực hiện hành động nhạy cảm.

## Bản sửa

1. Giữ vòng sàng lọc, thêm một vòng JEV đối chiếu có mục tiêu cho các quan hệ chưa kết luận. Hỏi riêng bằng chứng “cùng thao tác/đầu ra” và “khác thao tác/đầu ra”; chia sẻ ticket, chủ đề hoặc dữ liệu không đủ để coi là trùng. Code chỉ quyết định khi hai kết luận nhất quán và vượt ngưỡng. Không tự giảm ngưỡng hay mặc định tạo mới khi lỗi.
2. Kết luận cùng nghiệp vụ vẫn đi qua logic dùng lại / tiếp tục draft / nâng cấp cùng ID. Nhiều ứng viên thực sự cùng nghiệp vụ vẫn bị chặn; thông báo nêu tên agent, draft/published và vai trò có khả năng trùng. Checkpoint lưu cả vòng đối chiếu để dùng lại kết quả khi tiếp tục.
3. Eval kiểm tra trước catalog, binding, schema và tool bắt buộc của test. Tool bị thu hồi hoặc test đòi tool chưa cấp được báo trước khi gọi model cho ca đó.
4. Input tool phải là JSON object đúng schema trước khi tới connector hoặc bộ mô phỏng. Agent nhận phản hồi lỗi để sửa input và thử lại trong giới hạn bước; lỗi chưa khắc phục không được bộ chấm cho qua. Một lời gọi lỗi không thỏa `expect_tool`.
5. Tách lỗi môi trường, cấu hình, thiết kế test, chạy model và bộ chấm. Báo cáo/UI nêu rõ môi trường đang dùng, nguồn dữ liệu đọc thật và hành động mô phỏng.
6. Hướng dẫn sinh test/chấm test giới hạn kỳ vọng trong một lượt; phân biệt tiền điều kiện hạ tầng, skill và tool; không bắt agent xin xác nhận chỉ để đề nghị ẩn danh. Thay đổi prompt này chưa được đo chất lượng bằng model thật.

Ngưỡng phát hành giữ nguyên: ít nhất 3 ca, đạt >=80%, mọi ca an toàn đạt, không có lỗi chạy/chấm và báo cáo khớp đúng AgentSpec. Với đúng 3 ca, 2/3 = 66,7% nên vẫn bị chặn; không tự cho qua để tạo được agent.

## Sandbox hiện có và phần phải bổ sung

Eval hiện là vòng gọi model ở app với schema tool: MCP được server đánh dấu chỉ đọc/không cần consent có thể được gọi thật; thao tác ghi và TeamSay được mô phỏng. Nó **chưa tự cấp một sandbox nghiệp vụ riêng**, chưa tạo ticket/grant, chưa chạy toàn bộ RAG và nội dung skill thư viện như runtime. Docker workspace của agent là một thành phần khác. Không coi việc có Docker là đã có đầy đủ môi trường eval nghiệp vụ.

Để kiểm thử nghiệp vụ đủ điều kiện, cần nối eval tới sandbox Domain có dữ liệu tổng hợp, đúng owner/khu vực, ticket và grant thời hạn ngắn chỉ dành cho bộ ca đó. Grant khám phá MCP không thay thế grant theo ticket. Không đưa token vào prompt, test case hoặc AgentSpec. Nên cấp/hủy grant bằng backend, giới hạn tool được phép và tách credential sandbox khỏi production.

Mỗi tool cần fixture theo schema/version và các nhánh đủ dữ liệu, không có kết quả, bị từ chối, hết hạn grant và tài nguyên bị thu hồi. Knowledge cần tài liệu nguồn có quyền và retrieval; skill cần nội dung/package thực sự, dependency và tool phù hợp. Đây là phần tích hợp tiếp theo, **chưa được hoàn thiện bằng bản sửa này**. Không dựng kết quả nghiệp vụ giả để vượt cổng publish.

JEV phù hợp cho phân loại/kiểm tra trùng/chọn tài nguyên từ catalog. Nó không cấp quyền MCP, tạo tool còn thiếu, vận hành sandbox hoặc thay bộ eval thực thi. Không cần bổ sung API key khác để sửa nguyên nhân ở ảnh này.

## Kiểm chứng

Tái hiện trước sửa bằng classifier/model/connector lập trình sẵn: 2 ca quyết định danh tính và 5 ca preflight/schema đều đỏ đúng triệu chứng. Các bài mới kiểm tra thêm replay ba vai trò/11 ứng viên, bằng chứng mâu thuẫn, mất kết nối đối chiếu, ngưỡng xác suất và sửa input tool sau lỗi. Dùng runner `platform_VP/agentscope/scripts/workforce/check_builder_jev.py` trong Docker `--network none`, xóa biến credential và chặn socket ứng dụng.

Không gọi API model hoặc embedding thật, không dùng key để test. Kết quả offline xác minh logic và hợp đồng; chưa chứng minh chất lượng ngữ nghĩa, độ trễ/chi phí model thật hoặc nghiệm thu nghiệp vụ. Số test và chứng cứ đóng gói/deploy cuối cùng lưu trong release manifest/báo cáo bàn giao tương ứng.
