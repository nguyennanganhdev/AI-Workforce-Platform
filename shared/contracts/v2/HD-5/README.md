# HD-5: Sổ chi phí và số liệu của một vụ

Chủ: Team Hoàng. Bên ghi: Đông, Quang, Hoàng (Tiếp nhận). Bên lưu: Team Chiến (CN-3).
Trạng thái: **bản nháp v0, ngày 08/10/2026**. Chủ hợp đồng rà và chốt trước cuối ngày 12/10. Sau khi chốt, đổi theo quy trình ở mục 3 của `docs/PHAN_CONG_VA_BAN_GIAO_2026-10-08.md`.

## 1. Bản ghi sử dụng (`usage.schema.json`)

**Mỗi lần gọi model ghi một bản ghi**, kể cả lần gọi lỗi và lần gọi lại. Gọi `POST /internal/core/v1/usage` (đề xuất).

| Trường | Ý nghĩa |
|---|---|
| `usage_id` | Do bên ghi cấp, ổn định. Gửi lại không tạo bản ghi thứ hai. |
| `case_id`, `run_id` | Vụ việc và lượt chạy. Lần gọi không thuộc vụ nào (ví dụ đánh giá) dùng mã vụ của ca đánh giá. |
| `role` | `reception`, `supervisor`, `specialist`, `judge` (model chấm), `summarizer` (tóm tắt), `other`. |
| `phase` | Pha của phiên lúc gọi. |
| `input_tokens` | Tổng token đầu vào, **đã gồm** phần được cache. |
| `cached_input_tokens` | Phần đầu vào được nhà cung cấp tính giá cache. Không biết thì ghi 0. |
| `output_tokens` | Token đầu ra, gồm cả token suy luận nếu nhà cung cấp tính tiền. |

Bên ghi **không** gửi số tiền. Máy chủ tính tiền từ bảng giá, để đổi giá không phải sửa bên ghi.

## 2. Bảng giá (`price.schema.json`)

Một dòng cho mỗi model đang dùng. Giá gõ tay từ trang giá chính thức của nhà cung cấp, kèm địa chỉ trang và ngày kiểm. **Tệp ví dụ để giá bằng 0 có chủ ý**: Team Hoàng điền số thật khi làm bộ dữ liệu D-50; không ai được điền theo trí nhớ.

Tiền của một lần gọi = (đầu vào không cache × giá đầu vào + đầu vào cache × giá cache + đầu ra × giá đầu ra) ÷ 1.000.000.

## 3. Số liệu của một vụ (`case-metrics.schema.json`)

| Số liệu | Định nghĩa |
|---|---|
| `model_calls`, các số token, `cost` | Cộng mọi bản ghi sử dụng của vụ. |
| `duration_seconds` | Từ sự kiện `session.started` tới lúc phiên chờ người lần đầu. |
| `findings_total` | Số mục loại `finding` cộng số mục `assumption` có nguồn gốc là nhận định bị hạ. |
| `findings_sourced` | Số mục `finding` có `check.status` là `accepted`. |
| `entries_demoted` | Số mục có `check.status` là `demoted`. |
| `plan_steps_blocked` | Số bước phương án bị từ chối vì thiếu căn cứ. |
| `human_edits` | Số lần người từ chối hoặc yêu cầu sửa phương án, cộng số mục do người ghi thay cho mục của agent. |
| `uses_sample_data` | Đúng nếu có ít nhất một mục mang nhãn khác `real`. |

"Tỉ lệ nhận định có nguồn" hiện trên màn hình = `findings_sourced` ÷ `findings_total`.

**Giới hạn phải nói rõ khi trình bày:** tỉ lệ này đo việc có nguồn hợp lệ, không đo nguồn đó đúng hay sai.

## Ví dụ

- `examples/usage-specialist.json`, `examples/price-placeholder.json`, `examples/case-metrics.json`

## Còn mở

- Đơn vị tiền hiện trên màn hình (bản nháp: lưu theo đơn vị của bảng giá, đổi sang đồng khi hiển thị với một tỉ giá cố định ghi trong cấu hình).
- Có tính chi phí truy hồi và embedding vào vụ hay không (bản nháp: chưa).
