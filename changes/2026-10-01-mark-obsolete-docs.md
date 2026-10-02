# Đánh dấu tài liệu đã được thay thế

- Ngày: 2026-10-01
- Yêu cầu: rà soát tài liệu và thêm `no_need_` trước tên các file có thể bỏ khỏi bộ tài liệu đang sử dụng.

## Thay đổi

Đổi tên bốn file, giữ bản gốc để có thể tra cứu hoặc hoàn tác:

| File sau đổi tên | Lý do | Nguồn nên dùng |
| --- | --- | --- |
| `my-docs/no_need_read-this.md` | Toàn bộ nội dung là phần đầu nguyên vẹn của bản nghiệp vụ mới. | `my-docs/nghiep_vu_moi.md` |
| `my-docs/no_need_TONG_HOP_AGENT_RULES.md` | Bản tóm tắt từ bộ quy tắc và nghiệp vụ cũ; còn ghi những quyết định đã chốt là chưa chốt. | Bộ `Agent-rules/`, `nghiep_vu_moi.md`, tài liệu API/Reception hiện có |
| `my-docs/no_need_HUONG_DAN_GIAO_DIEN_DEMO_API_V3.md` | Mô tả console cũ, tự chỉ rõ đã được thay thế; route `/demo/ui` thực tế trả `business.html`. | `my-docs/HUONG_DAN_GIAO_DIEN_NGUOI_DUNG_DEMO.md` |
| `docs/no_need_VINHOMES_API_FE_INTEGRATION_PLAN.md` | Kế hoạch ban đầu đề xuất API `/api/vinhomes` trên Hono và thiếu lệnh ghi; đã có FastAPI V3 và tài liệu contract/tích hợp mới. | `my-docs/API_ENDPOINTS_AGENT_TOOLS.md`; tài liệu tích hợp và trạng thái legacy trong `docs/` |

Cập nhật các tham chiếu đến tên cũ trong `docs/` và `my-docs/`, gồm danh sách endpoint và nguồn của bản tổng hợp cũ. Các đường dẫn trong nhật ký `/changes` trước đây giữ nguyên để phản ánh lịch sử.

## Tài liệu giữ lại

- Nghiệp vụ mới; file schema tên V1 nhưng chứa bản chốt `schema_v2`; yêu cầu/luồng Reception.
- Giải thích code và luồng API; danh mục/mapping API, Word bàn giao và báo cáo test PostgreSQL.
- Backlog API và các kế hoạch còn tiêu chí chưa hoàn tất; không coi việc API đã tồn tại là mọi đầu việc đã xong.
- Báo cáo FE legacy và audit dữ liệu: còn thông tin riêng về nguồn, backup, contract và giới hạn nên chưa đánh dấu bỏ.
- Tài liệu nền tảng, database, triển khai, cấu hình, plugin và phân công team: phục vụ các phạm vi riêng.

## Xác minh

- Trước/sau mỗi thao tác đổi tên: SHA256 trùng khớp; không ghi đè file đích.
- Sau cập nhật liên kết: kiểm tra bốn tên mới tồn tại, tên cũ không còn, không còn tham chiếu tên cũ chưa được đổi trong `docs/` và `my-docs/`.
- Không chạy test API vì thay đổi chỉ gồm tên tài liệu và tham chiếu văn bản.

## Rủi ro / việc còn lại

- Liên kết hoặc bookmark nằm ngoài workspace cần đổi sang tên mới.
- Một số tài liệu được giữ còn phần mô tả lịch sử; đánh dấu file không đồng nghĩa cập nhật toàn bộ nội dung của các file đó.
- Chưa commit/push.
