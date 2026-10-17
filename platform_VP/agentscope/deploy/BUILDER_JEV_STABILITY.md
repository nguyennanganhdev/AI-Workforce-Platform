# Builder–JEV: ổn định luồng kiểm tra và phục hồi

## Vấn đề đã xử lý

Giới hạn token đã ngăn request quá lớn, nhưng chưa đủ để phục hồi một lượt Builder: nút thử lại trước đây gọi lại LLM lập dàn ý, batch thành công chưa được lưu, và lỗi chọn tài nguyên có thể gọi thêm LLM dự phòng. Vì vậy một lỗi dịch vụ có thể làm lặp công việc, đổi phương án và tăng chi phí.

## Hành vi sau thay đổi

1. Builder LLM chỉ lập dàn ý khi người dùng gửi yêu cầu mới. Dàn ý được lưu trước khi JEV bắt đầu. JEV nhận yêu cầu của người dùng, không nhận các phương án do assistant viết như yêu cầu nghiệp vụ.
2. Hồ sơ so sánh giữ cấu hình published/draft, quyền, ràng buộc và nội dung tùy chỉnh. Prompt runtime sinh chính xác từ spec, draft giống published, binding trùng và skill giống extra_instructions được thay bằng tham chiếu rõ ràng. Không dùng LLM tóm tắt, không bỏ ứng viên và không cắt văn bản riêng.
3. Chia cả catalog và nhóm câu hỏi theo ngân sách token. Chỉ chia thêm khi nhà cung cấp báo rõ max_tokens_exceeded. Một phần tử không thể chia mà vẫn quá lớn bị chặn; không suy đoán kết quả.
4. Mỗi batch thành công được lưu bền trong trạng thái phiên. Batch cha đã bị từ chối do context cũng được ghi nhận, để lần sau tiếp tục từ các phần con. Không coi kết quả một phần là đủ để tạo agent.
5. Nút **Thử lại bước kiểm tra** gọi `/workforce/console/builder/retry-verification`. API giữ nguyên dàn ý, không gọi LLM lập dàn ý, không tóm tắt lại hội thoại và chỉ gọi JEV cho phần thiếu. Đề xuất lỗi cũ cũng dùng được; nếu yêu cầu KB bắt buộc chưa được lưu ở schema cũ thì dùng mục tiêu đã lưu để kiểm tra độ bao phủ, không bỏ yêu cầu KB.
6. Khóa Redis hiện có được dùng theo owner/conversation, tự gia hạn trong khi xử lý. Revision/proposal/scope được kiểm tra lại sau khi lấy khóa. Hai lần bấm đồng thời hoặc request cũ không gây hai lượt kiểm tra cùng phương án. Người khác không đọc được checkpoint.
7. Cache gắn với snapshot catalog và scope, request/câu hỏi chính xác, phiên bản model và fingerprint credential đã được kiểm tra quyền hiện tại. Catalog đổi thì bỏ cache của lượt cũ. Credential/model đổi không dùng lại điểm cũ. Không tái sử dụng điểm giữa hai lượt Builder khác nhau.
8. Lỗi chọn tài nguyên giữ kết luận kiểm tra trùng, lưu lỗi riêng và tạm dừng. Không tự chuyển sang LLM dự phòng. Bước xác nhận/sinh cấu hình vẫn bị chặn khi JEV chưa hoàn tất.

## Truy vết và giới hạn

- UI hiển thị trạng thái kiểm tra trùng/chọn tài nguyên, số batch dùng lại và mã lượt kiểm tra.
- Ledger lưu mã lượt/call, revision nguồn build, digest request, số câu hỏi, số ký tự, token ước tính, HTTP status và mã lỗi thuộc danh sách an toàn. Không lưu response body tùy ý của nhà cung cấp.
- Tách thông báo lỗi credential/quyền, HTTP 400, giới hạn lưu lượng, lỗi dịch vụ và lỗi context cục bộ.
- Không tự retry lỗi xác thực/schema hoặc timeout chưa biết kết quả. Người dùng chủ động chạy tiếp; giới hạn 128 lần gọi JEV trong mỗi lần xử lý. SDK retry mặc định bị tắt.
- Pin typesafe-sdk 0.7.5 theo phiên bản đã kiểm tra trong runtime, tránh thay đổi contract do dependency tự nâng.
- Không có migration database; checkpoint dùng trạng thái phiên và cơ chế khóa hiện có.

## Kiểm thử và nghiệm thu

Các kiểm thử offline đi qua adapter/SDK hoặc provider được lập trình sẵn và storage thật. Ca bao gồm: một agent/14 câu, ba agent/45 câu, catalog lớn, nhiều câu hỏi trên một tài nguyên, lỗi giữa batch, lỗi giữa các phần con, khởi tạo worker mới, thay catalog/credential, thu hồi quyền, ngắt worker sau khi lưu dàn ý, khôi phục đề xuất cũ, hai HTTP request cùng revision và hai worker tranh khóa Redis.

Kiểm thử frontend kiểm tra nút xác nhận bị khóa khi chưa có kết luận. Kiểm tra trình duyệt sau deploy chỉ dùng auth/GET dữ liệu đã lưu; thao tác retry được chặn tại browser và trả fixture. Không dùng model key, không gọi model thật để tự test.

Số test, commit, image, checksum và kết quả health/backup/restore cụ thể được ghi trong gói release. Gói lấy source từ Git commit, không đưa các thay đổi chưa commit khác của workspace vào image.

**Chưa nghiệm thu chất lượng phán đoán thực tế của JEV.** Điểm provider giả dùng để kiểm tra quyết định của chương trình, không chứng minh độ chính xác ngữ nghĩa của model. Kết quả nghiệp vụ cần đối chiếu từ những lượt người dùng chủ động thực hiện. Nếu lượt mới còn lỗi, dùng mã lượt kiểm tra để đối chiếu đúng bước và batch; không kết luận từ lỗi lịch sử trước release.

Giới hạn context của nhà cung cấp: https://docs.typesafe.ai/models#context-length . Token cục bộ là ước tính; phản hồi max_tokens_exceeded vẫn được xử lý bằng chia nhỏ có lưu tiến độ.
