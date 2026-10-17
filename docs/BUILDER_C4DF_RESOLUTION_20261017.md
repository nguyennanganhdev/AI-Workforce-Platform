# Sửa vòng lặp “Cần làm rõ” theo lượt JEV c4df — 17/10/2026

## Vì sao bản trước vẫn bị chặn

Lượt `c4df7ddd9bf34e459c64a71da93d0c26` đã chạy cả sàng lọc và đối chiếu, không lỗi credential hay kết nối JEV. Kết quả đã lưu xác nhận cùng nghiệp vụ: đánh giá ticket với agent kỹ thuật 0,87; điều phối với agent điều phối 0,91; đổi lịch/hủy với agent điều phối 0,91. Tuy nhiên code vẫn cho ứng viên yếu phủ quyết đích đã xác nhận, giữ hai phần việc cùng đích thành hai agent, và coi cả tool đọc ngữ cảnh dùng chung là xung đột.

Bản trước chỉ chứng minh logic khi vòng đối chiếu giả lập trả về các điểm rõ ràng. Nó không chứng minh dữ liệu thực tế trong lượt này sẽ được giải quyết. Đợt này dùng nguyên các điểm đã lưu làm fixture, không tự gọi JEV/model thật.

## Cách quyết định mới

- Có đúng một ứng viên được xác nhận cùng nghiệp vụ: dùng lại/tiếp tục draft/nâng cấp cùng ID; các quan hệ yếu hơn không chặn cập nhật đích đó. Không vì vậy cho phép tạo mới. Nếu có hai ứng viên cùng được xác nhận, vẫn cần chọn đúng đích.
- Hai phần việc cùng trỏ một agent được gộp thành một cấu hình chờ duyệt, giữ đủ mục tiêu, yêu cầu tool/KB và ràng buộc kiến thức. Không ghi agent hoặc publish tự động. Nếu cả hai đều đủ điều kiện dùng lại thì giữ dùng lại, không ép chạy eval lại chỉ do gộp.
- Tool được catalog xác nhận chỉ đọc và không cần consent có thể dùng chung. Thao tác ghi vẫn có một chuyên viên sở hữu. Nếu bản đang có đã sở hữu thao tác, vai trò khác đề xuất dùng cùng thao tác sẽ phối hợp qua TeamSay/Leader; không được cấp bản sao tool ghi. Hướng dẫn phối hợp được lưu trong AgentSpec và prompt kiểm thử.
- Nút “Kiểm tra lại dàn ý đã lưu” cho phép tiếp tục phương án JEV active nhưng còn clarify. Server vẫn kiểm tra owner/scope/revision, khóa hội thoại và catalog; không sinh lại dàn ý. Nếu catalog đổi hoặc còn bước chọn tài nguyên chưa chạy thì thao tác có thể gọi JEV, được UI thông báo rõ. Đợt sửa không tự bấm nút đó.
- Chưa xác nhận được ứng viên nào, có nhiều đích cùng xác nhận, thiếu tool hoặc quyền tài nguyên thật: vẫn chặn đúng nguyên nhân. Không hạ chuẩn eval/publish hoặc biến lỗi JEV thành tạo mới.

## Kiểm chứng

Hai bài phát lại trước sửa thất bại đúng triệu chứng; sau sửa qua. Fixture commit chỉ chứa mô tả nghiệp vụ tổng quát và điểm JEV đã lưu, không chứa account ID, token hay credential. Kiểm tra tích hợp dùng bộ chọn tài nguyên và model sinh cấu hình lập trình sẵn để đi qua plan → gộp → giao quyền tool → check_plan → sinh AgentSpec/diff; không dùng API model.

Suite Builder/classifier: 192 passed. Frontend: 6/6 bài kiểm tra review, ESLint, TypeScript và build đạt. Runner xóa biến credential, chặn socket và Docker `--network none`: external network attempts = 0, paid model test calls = 0.

Kiểm tra SQL mở rộng phát hiện `test_upsert_leased_document` không khớp fixture knowledge-document đã mở rộng; đã chạy lại nguyên source trước bản vá `f9ad66b6` và thấy cùng lỗi. Không sửa module knowledge/storage trong bản này, không báo toàn bộ SQL suite đạt.

## Giới hạn nghiệm thu

Đây là kết quả phát lại quyết định đã có và kiểm thử hợp đồng. Không đo lại chất lượng, giá hay độ trễ JEV/model thật; không chạy Builder/eval/chat production. Chọn tài nguyên của lượt trong ảnh chưa từng chạy vì bị chặn ở identity, nên không tuyên bố toàn bộ lượt đó đã tạo/publish agent. Môi trường ticket/grant sandbox và business UAT vẫn là các điều kiện riêng, không được vượt bằng báo cáo giả.
