# HD-3: Tool và mã nguồn

Chủ: Team Quang. Team dùng: Đông, Chiến, Hoàng, Phái.
Trạng thái: **bản nháp v0, ngày 08/10/2026**. Chủ hợp đồng rà và chốt trước cuối ngày 12/10. Sau khi chốt, đổi theo quy trình ở mục 3 của `docs/PHAN_CONG_VA_BAN_GIAO_2026-10-08.md`.

Hợp đồng này quy định ba thứ: một tool khai báo thế nào, mọi tool trả kết quả theo dạng nào, và **mã nguồn** được viết thế nào trong toàn hệ thống.

## 1. Bản khai một tool (`manifest.schema.json`)

Mỗi tool có đúng một bản khai. Bảng đăng ký trong cơ sở dữ liệu, danh sách tool đưa cho model và tài liệu đều sinh ra từ bản khai này.

| Trường | Ý nghĩa |
|---|---|
| `name` | Dạng `nhóm.tên`, chữ thường, ví dụ `technical.get_active_outage`. Tên đưa cho model đổi dấu chấm thành hai gạch dưới; chỉ một hàm làm việc đổi này. |
| `side_effect` | `read`, `write` hoặc `request` (tạo yêu cầu chờ người duyệt). Trong phiên chỉ tool `read` được mở, như hiện nay. |
| `required_capability`, `timeout_ms`, `idempotent` | Giữ từ bản khai hiện có của tool kỹ thuật. |
| `input_schema`, `output_schema` | JSON Schema. |
| `data_origin` | Tool đang đọc dữ liệu loại nào (HD-7). Kết quả mang đúng nhãn này. |
| `owner_team`, `pack` | Team giữ và gói lĩnh vực chứa tool. |

## 2. Kết quả (`result.schema.json`)

Dựa trên lớp vỏ đang dùng ở `server/src/technical-tools/contracts/envelope.ts`, thêm ba trường `source_id`, `tool`, `data_origin`. Mọi bộ tool (kỹ thuật, vệ sinh, báo cáo, an ninh, kiến thức) trả đúng một lớp vỏ này; cổng gọi tool không bọc thêm lớp nào.

Mã trạng thái giữ nguyên chín mã hiện có:

| Mã | Agent phải làm gì |
|---|---|
| `OK` | Dùng `data`. Được phép trỏ nguồn tới `source_id`. |
| `NOT_FOUND` | Không được suy ra nội dung. Ghi một câu hỏi mở hoặc một giả định. |
| `NEEDS_INPUT` | Hỏi lại theo `missing_fields`. |
| `STALE_DATA` | Dữ liệu quá cũ; không dùng làm căn cứ. |
| `FORBIDDEN`, `INVALID_INPUT`, `CONFLICT`, `PENDING_APPROVAL`, `INTERNAL_ERROR` | Không dùng làm căn cứ; báo trong `summary` nếu ảnh hưởng tới việc. |

Kết quả `OK` có `data` rỗng (ví dụ "không có lịch cắt") **là một dữ kiện hợp lệ** chỉ khi bảng nguồn có dữ liệu được nạp. Tool đọc bảng chưa từng được nạp phải trả `NOT_FOUND`.

## 3. Mã nguồn

Một chuỗi duy nhất, có tiền tố cho biết loại. Dùng ở HD-1 và HD-2.

| Loại | Dạng | Ai cấp |
|---|---|---|
| Kết quả tool | `tool:<mã hex>` | **Cổng gọi tool**, mỗi lần gọi một mã mới. Cổng lưu nguyên kết quả theo mã này. |
| Đoạn tài liệu | `doc:<mã tài liệu>@<phiên bản>#<mục>` | Dịch vụ kiến thức. **Không dùng mã chunk**, vì mã chunk đổi khi nạp lại. |
| Tin nhắn | `msg:<mã>` | API nghiệp vụ |
| Tệp, ảnh | `file:<mã>` | API nghiệp vụ |
| Mục hồ sơ | `e-<số>` hoặc mã do máy chủ cấp | HD-2 |

`GET /internal/core/v1/sources/{source_id}` (HD-2) mở được mọi loại trên.

## Ví dụ

- `examples/manifest-get-active-outage.json`
- `examples/result-ok.json`, `examples/result-not-found.json`

## Còn mở

- Quy tắc chuẩn hóa `<mục>` của đoạn tài liệu (bản nháp: đường dẫn tiêu đề viết thường, không dấu, nối bằng gạch ngang).
- Bộ tool báo cáo đang trả `outcome: success|empty|failure`; cần bảng đổi sang chín mã trên.
