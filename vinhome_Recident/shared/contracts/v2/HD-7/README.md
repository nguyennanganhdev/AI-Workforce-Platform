# HD-7: Khuôn dữ liệu mẫu

Chủ: Team Phái. Team dùng: tất cả. Danh sách bộ dữ liệu: `docs/KE_HOACH_DU_LIEU_2026-10-08.md`.
Trạng thái: **bản nháp v0, ngày 08/10/2026**. Chủ hợp đồng rà và chốt trước cuối ngày 12/10. Sau khi chốt, đổi theo quy trình ở mục 3 của `docs/PHAN_CONG_VA_BAN_GIAO_2026-10-08.md`.

## 1. Nhãn nguồn gốc

| Nhãn | Nghĩa | Thông tin bắt buộc trong `origin_detail` |
|---|---|---|
| `real` | Dữ liệu vận hành thật | Hiện chưa có bộ nào |
| `public` | Lấy từ nguồn công khai | `source_url`, `retrieved_on`, `content_sha256`, `confirmed_by_operator` |
| `team_written` | Team tự viết | `written_by` |
| `synthetic` | Model sinh | `generator_model`, `reviewer_model` (khác hãng), `template` |
| `test_run` | Sinh ra khi chạy thử hệ thống | Không |

Nhãn đi theo dữ liệu: bản ghi, kết quả tool (HD-3), mục hồ sơ (HD-2), rồi màn hình. Mọi nhãn khác `real` hiện chữ "dữ liệu mẫu". Tài liệu `public` có `confirmed_by_operator` là sai hiện thêm "chưa được đơn vị vận hành xác nhận".

## 2. Một bộ dữ liệu

Mỗi bộ là một thư mục `data/D-xx/` trong gói, gồm:

- `manifest.json` theo `manifest.schema.json`.
- Tệp dữ liệu. Dữ liệu dạng bảng dùng JSONL, mỗi dòng một bản ghi, UTF-8, tiếng Việt có dấu.
- `record.schema.json`: lược đồ của một bản ghi.
- Với dữ liệu `synthetic`: tệp khuôn đã dùng để sinh.

## 3. Thế giới demo (`world.schema.json`)

Một tệp `data/world.json` cố định từ 12/10. Sau ngày đó không ai đổi mã định danh. Mọi bản ghi của mọi bộ chỉ được dùng mã có trong thế giới này.

## 4. Bốn bước kiểm trước khi nạp

1. **Đúng khuôn:** tệp kê và từng bản ghi qua lược đồ.
2. **Đúng tham chiếu:** mọi mã tòa, căn hộ, cư dân, nhân viên, thiết bị có trong thế giới demo.
3. **Hợp lý:** ngày tháng đúng thứ tự; số tiền và thời lượng trong khoảng ghi ở lược đồ bản ghi; không có tên người thật; số điện thoại dùng dải không có thật.
4. **Người rà:** đọc ngẫu nhiên 10%, tối thiểu 5 bản ghi, ghi `reviewed_by`, `reviewed_on`, `sample_checked`. Quy trình kỹ thuật và an ninh: đọc toàn bộ.

Bộ chưa có `reviewed_by` không được nạp vào môi trường demo.

## 5. Quy tắc nạp

- Mỗi bộ có một `load_command`. Chạy hai lần cho cùng kết quả.
- Vụ việc, hồ sơ, lệnh việc nạp qua API; danh mục nạp thẳng vào bảng.
- Ngày tháng trong dữ liệu tính tương đối theo ngày nạp khi có thể (ví dụ ca làm việc), để dựng lại môi trường không làm dữ liệu hết hạn.

## Ví dụ

- `examples/world.json`
- `examples/manifest-synthetic.json`, `examples/manifest-public.json`. Các ô ghi "ĐIỀN:" phải thay bằng giá trị thật; bộ kiểm từ chối tệp kê còn chữ "ĐIỀN:".

## Còn mở

- Tên lệnh nạp (`tools.data`) là giả định; Team Phái đặt trong việc PH-3.
