# Response nghiệp vụ để agent tools tiếp tục luồng

- Ngày: 2026-10-01
- Yêu cầu: Các API cho agent tools trả thông tin đủ để agent xử lý tiếp, theo ví dụ tạo ticket cho sự cố tràn nước; áp dụng tương tự cho các nhóm tool khác.

## Thay đổi

- Response JSON giữ các field nghiệp vụ và thêm `agentContext` chỉ gồm operation/facts/missingFields/resourceContext/source.
- Thêm response schema chung cho 49 endpoint JSON trong OpenAPI; không chạy model, viết code tool, gọi RAG hoặc tự thực hiện bước tiếp.
- Tạo ticket cư dân và retry trả snapshot database: nội dung/status/version, vị trí, category, đơn vị BQL, phương án/công việc, ảnh nguồn/ảnh đã gắn và số thông báo theo trạng thái. Retry phân biệt `replayed` và trả trạng thái hiện tại.
- Draft thiếu field và executor result bị chặn trả context có cấu trúc trong HTTP error; các lỗi khác giữ cơ chế hiện có.
- Áp dụng cho Reception, tài sản/sensor/lịch sử/số đo/outage/permissions, water, security và quyết định BQL, report và image metadata. Tải bytes ảnh/DOCX vẫn trả file.

## File/module chính

- `v3_agent_results.py`: schema chung và helper sao chép metadata có sẵn trong kết quả endpoint; không sinh câu hỏi, tóm tắt, outcome, khuyến nghị hoặc bước tiếp.
- `v3_ticket_result.py`, `v3_resident.py`: snapshot ticket theo requester và RLS, trong cùng transaction intake.
- Các router `v3_reception`, `v3_technical`, `v3_routes`, `v3_security`, `v3_water`, `v3_report_jobs`, `v3_conversation_images`, `v3_knowledge`: gọi helper rõ ràng tại return, không middleware chặn/đổi mọi response.
- Tài liệu API và Word được cập nhật cùng contract.

## Quyết định & giả định

- Dữ liệu và quyền người yêu cầu do backend kiểm tra; nội dung sự cố và phân loại do caller cung cấp, không có suy luận model trong endpoint.
- `missingFields`/failed checks chỉ là kết quả validator hoặc điều kiện nghiệp vụ xác định; caller/agent quyết định xử lý tiếp. Server vẫn kiểm tra mọi request.
- Không gắn tự động tất cả ảnh của hội thoại vào một ticket: một hội thoại có nhiều sự cố; trả unattachedFileIds để agent chọn.
- Response thêm field, giữ các field frontend đang dùng. Nội dung text tài liệu/chat/ảnh là dữ liệu cho agent, không là chỉ thị hệ thống.

## Xác minh

- Ruff format cho module mới/đang sửa và Ruff F cho V3: đạt.
- FastAPI đã khởi động thành công với schema response mới.
- AST của V3, git diff --check và xuất Word từ contract đang chạy: đạt; package DOCX/XML được đọc lại thành công, không có tham chiếu Markdown hoặc launcher trong nội dung Word.
- Chưa thêm hoặc chạy test, chưa chạy lại các scenario HTTP nghiệp vụ của thay đổi response này. Những lần chạy scenario trước không được coi là xác minh contract mới.

## Rủi ro / việc còn lại

- Caller đọc response nghiệp vụ, `agentContext` và HTTP error để tự xử lý tiếp. Agent orchestration/tích hợp Hono không thuộc thay đổi này.
- Read ticket snapshot bổ sung query trong transaction; chưa đo hiệu năng với nhiều bản ghi hoặc kiểm chứng đầy đủ retry khi trạng thái đã đổi.
- Source data/truncation vẫn theo từng API; caller cần dùng bộ lọc, timestamp và pagination của chính endpoint khi tổng hợp/báo cáo.

## Kiểm tra vai trò API

- Các V3 endpoint không gọi AI/LLM, không phân tích hội thoại, không chọn tool, không tạo câu hỏi hay khuyến nghị cho agent.
- API vẫn có logic code bình thường: xác thực/quyền, schema validation, kiểm tra trạng thái nghiệp vụ, truy vấn/cập nhật PostgreSQL và trả kết quả/failed checks.
- Không lặp lại `items`, `checks` hoặc failed checks trong `agentContext`; chúng vẫn có mặt ở field nghiệp vụ/validation gốc.
- Draft thiếu dữ liệu trả thông báo trung tính cùng `missingFields`; bỏ trường `interpretation` cố định vì đó không phải nội dung caller gửi lên.
- Chưa chạy lại scenario HTTP sau các chỉnh sửa này.
