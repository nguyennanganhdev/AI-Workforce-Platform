# Khôi phục Agent Builder không dùng JEV — 2026-10-17

Theo yêu cầu bỏ JEV, luồng lập dàn ý, sinh cấu hình và giao diện Builder được khôi phục từ mốc `d8baf86f` trước tích hợp. Không reset toàn bộ repository vì các thay đổi Leader, quyền BQL, eval và chuẩn bị tài nguyên khi publish vẫn cần được giữ.

Đã gỡ:

- Bộ đánh giá trùng nghiệp vụ, phân loại/chọn tài nguyên bằng JEV, catalog lock và checkpoint/retry riêng.
- Adapter JEV, credential TypeSafe, đăng ký provider, dependency SDK và cấu hình Compose/env mẫu.
- Trạng thái, nút thao tác, hợp đồng API và test chuyên dụng cho JEV; tài liệu hướng dẫn riêng không còn áp dụng.

Builder dùng model chat do người dùng chọn để lập dàn ý → người dùng duyệt → sinh AgentSpec và test case → eval → publish. Giữ kiểm tra tool/thư viện và điều kiện publish của luồng cũ. Không còn cổng JEV để chặn vì trùng nghiệp vụ hoặc catalog quá lớn. Model chat vẫn có thể hỏi lại khi yêu cầu chưa đủ; eval vẫn phải đạt trước publish.

Giữ các bản sửa độc lập về eval, bằng chứng Leader, truy cập tài nguyên và workspace chuẩn bị trước publish. Nếu gắn tài nguyên thất bại thì agent chưa được publish và proposal chưa bị claim. Các agent, phiên bản, session và lịch sử chat đã lưu không bị xóa. Proposal mang checkpoint JEV cũ không được dùng để publish qua luồng đã khôi phục; hãy gửi yêu cầu mới để lập lại dàn ý.

Kiểm chứng: 119 test offline đạt, 0 lỗi/skip, 0 kết nối mạng và 0 lần gọi model thật. Bộ test có kiểm tra hợp đồng đã bỏ classifier và tiêm lỗi cài tài nguyên khi publish. Frontend ESLint, TypeScript và production build đạt (còn cảnh báo kích thước bundle đã có).

Đóng gói/vận hành: release `E:/AWP-Releases/builder-no-jev-20261017`, bằng chứng deploy nằm trong `deployment.json` của release sau khi hoàn tất. Gỡ biến môi trường và credential TypeSafe đang hoạt động sau backup bốn kho dữ liệu; giữ backup riêng tư để phục hồi. Các ghi chú kế hoạch đang sửa ngoài phạm vi và archive release cũ được giữ nguyên.

Không sử dụng API model/embedding thật để kiểm tra. Chưa nghiệm thu chất lượng tạo agent bằng model thật sau rollback.
