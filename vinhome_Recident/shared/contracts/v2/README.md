# Hợp đồng giữa các team, bản 2

Trạng thái: **bản nháp v0, ngày 08/10/2026**. Chủ hợp đồng rà và chốt trước cuối ngày 12/10. Sau khi chốt, đổi theo quy trình ở mục 3 của `docs/PHAN_CONG_VA_BAN_GIAO_2026-10-08.md`.

| Mã | Nội dung | Chủ | Tệp chính |
|---|---|---|---|
| [HD-1](HD-1/README.md) | Lượt agent: đầu vào và đầu ra | Đông | `input.schema.json`, `output.schema.json` |
| [HD-2](HD-2/README.md) | Hồ sơ vụ việc | Đông | `entry.schema.json`, `write.schema.json`, `case.schema.json` |
| [HD-3](HD-3/README.md) | Tool và mã nguồn | Quang | `manifest.schema.json`, `result.schema.json` |
| [HD-4](HD-4/README.md) | Sự kiện sống cho giao diện | Chiến | `event.schema.json`, `session.schema.json` |
| [HD-5](HD-5/README.md) | Sổ chi phí và số liệu của một vụ | Hoàng | `usage.schema.json`, `price.schema.json`, `case-metrics.schema.json` |
| [HD-6](HD-6/README.md) | Ranh giới lõi và gói | Phái | `domain.schema.json`, `boundary.schema.json` |
| [HD-7](HD-7/README.md) | Khuôn dữ liệu mẫu | Phái | `manifest.schema.json`, `world.schema.json` |

## Cách dùng

- Viết code và test dựa trên các tệp trong `examples/`. Mọi tệp ví dụ đều đã qua lược đồ tương ứng.
- Các lược đồ đều cấm trường lạ. Cần thêm trường thì đề nghị chủ hợp đồng, không tự thêm.
- Mục "Còn mở" ở cuối mỗi hợp đồng là những điểm chủ hợp đồng phải quyết định trước khi chốt.

## Điều các hợp đồng này chưa làm

Đây là bản nháp do người lập kế hoạch viết từ thiết kế và từ code hiện có, **chưa được team nào chạy thử**. Đường dẫn API là đề xuất. Tên trường có thể đổi tới hết ngày 12/10.
