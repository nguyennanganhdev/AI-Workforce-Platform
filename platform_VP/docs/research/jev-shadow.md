# Jev: thí nghiệm shadow, không làm bộ điều khiển quyền

Tra cứu nguồn chính thức ngày 2026-10-09. Jev có trong SDK vendored dưới classifier API; đây là model phân loại quyết định, không phải sản phẩm tự quản lý toàn bộ team agent. [SDK classifier](../../agentscope/src/agentscope/classifier/), [tài liệu TypeSafe](https://docs.typesafe.ai/).

Danh mục chính thức tại thời điểm tra cứu ghi model pinned `jev-1.13.0`, context text 64k và giá input $0.042/triệu token; output không tính phí. Alias có thể thay đổi, nên không dùng alias để kết luận một thử nghiệm có thể tái lập. Giới hạn và giá cần kiểm tra lại trước thí nghiệm có phí. [Models](https://docs.typesafe.ai/models).

Confidence mô tả phân bố quyết định của classifier, không tự là xác suất quyết định đúng. Cần bộ state có nhãn, calibration và ngưỡng theo nghiệp vụ; tiếng Việt phải đo riêng. Không dùng confidence để bỏ qua evidence, quyền tool hay phê duyệt con người. [Confidence](https://docs.typesafe.ai/confidence).

Platform triển khai `/api/experiments/jev`, admin-only, tắt mặc định; caller phải khai synthetic_only, state giới hạn và expected action. Baseline deterministic chọn clarify khi thiếu field, tool khi thiếu evidence, answer khi có evidence; Jev trả quyết định và phân bố để đối chiếu. Job, budget reservation và usage vẫn đi qua platform. Kết quả chỉ là artifact shadow, không thay đổi routing/permission/memory/session chính. Xem [implementation](../../services/platform-api/vp/evaluations.py).

Chưa gọi Jev API thật, chưa có số đo accuracy/latency/calibration hoặc kết luận Jev tiết kiệm tiền cho dữ liệu dự án. Chỉ cân nhắc bật trong luồng thật sau khi có số đo tốt hơn baseline, kiểm tra tiếng Việt và xác định rõ lỗi có thể chấp nhận.
