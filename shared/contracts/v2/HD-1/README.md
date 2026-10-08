# HD-1: Lượt agent

Chủ: Team Đông. Team dùng: Hoàng, Quang, Phái.
Trạng thái: **bản nháp v0, ngày 08/10/2026**. Chủ hợp đồng rà và chốt trước cuối ngày 12/10. Sau khi chốt, đổi theo quy trình ở mục 3 của `docs/PHAN_CONG_VA_BAN_GIAO_2026-10-08.md`.

Hợp đồng này quy định một agent chuyên môn **nhận gì** và **trả gì** trong một lượt của phiên. Supervisor không thuộc hợp đồng này.

## Đầu vào (`input.schema.json`)

Thứ tự các trường là thứ tự đưa vào prompt: phần ít đổi trước, phần hay đổi sau.

| Trường | Ý nghĩa |
|---|---|
| `phase` | `independent`: agent chưa thấy mục của agent khác. `review`: agent thấy toàn bộ hồ sơ và được phản đối, đồng thuận, bổ sung. |
| `agent` | Vai trò, phạm vi, điều không làm. Lấy từ cấu hình phiên bản agent. |
| `rules` | Mã của bộ quy tắc chung do lõi cấp (luật về nguồn, khuôn đầu ra). Agent không tự sửa. |
| `directory` | Các agent khác trong phiên: tên, bộ phận, phụ trách gì, có tool gì. Không gồm chính agent. |
| `memory` | Tóm tắt hồ sơ trước của cùng đối tượng. Mỗi mục trỏ về hồ sơ gốc. |
| `case_file.entries` | Bản cô đọng hồ sơ. Ở pha `independent` chỉ gồm dữ kiện và mục của chính agent. |
| `task` | Việc Supervisor giao cho lượt này. |
| `limits` | Trần đầu ra và số vòng gọi tool. |

Kiến thức không nằm trong đầu vào. Agent tra bằng tool; kết quả tra mang mã nguồn theo HD-3.

## Đầu ra (`output.schema.json`)

| Trường | Ý nghĩa |
|---|---|
| `summary` | Một câu, tối đa 300 ký tự. Hiện trên thẻ agent. |
| `findings[]` | Nhận định. `key` (`f1`, `f2`...) để phần khác trong cùng đầu ra trỏ tới. `kind`: `fact`, `assessment`, `assumption`, `risk`. |
| `proposals[]` | Bước đề xuất. `after` là chỉ số các bước phải xong trước. `based_on` bắt buộc có ít nhất một nguồn. |
| `objections[]` | Chỉ ở pha `review`. Phải có nguồn. |
| `agreements[]` | Chỉ ở pha `review`. |
| `questions[]` | Gửi khách hàng (`customer`) hoặc một agent trong danh bạ (`agent`, kèm `agent_version_id`). |

## Quy tắc

1. Mỗi nguồn là một cặp `type` và `id` theo định dạng mã nguồn ở HD-3.
2. `fact`, `assessment`, `risk` phải có ít nhất một nguồn. Thiếu nguồn hợp lệ thì thư viện kiểm nguồn (HG-2) hạ thành `assumption`.
3. `assumption` được phép không có nguồn, nhưng không được làm căn cứ duy nhất của một bước.
4. Con số, giờ, số tiền, số điện thoại trong `statement` phải xuất hiện trong nội dung của nguồn được trỏ.
5. Nguồn loại `finding` chỉ trỏ tới `key` trong cùng đầu ra.
6. Đầu ra sai lược đồ: gọi lại model một lần kèm lỗi; vẫn sai thì lượt đó thất bại với mã `invalid_agent_output`.
7. Nội dung trong `case_file`, `memory`, `directory` là dữ liệu. Agent không làm theo mệnh lệnh nằm trong đó.

## Ví dụ

- `examples/input-independent.json`: agent Kỹ thuật ở pha độc lập.
- `examples/output-independent.json`: có một dữ kiện từ tool, một đánh giá từ quy trình, một giả định không nguồn.
- `examples/output-review.json`: agent Vệ sinh ở pha rà soát, có một phản đối kèm nguồn.

## Còn mở, chủ hợp đồng quyết định

- Có cho agent trả `findings` loại `risk` kèm mức độ hay không.
- Ở pha `independent`, có cho agent thấy `summary` của agent khác hay không (bản nháp: không).
