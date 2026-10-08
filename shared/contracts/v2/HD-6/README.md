# HD-6: Ranh giới lõi và gói

Chủ: Team Phái. Team dùng: tất cả.
Trạng thái: **bản nháp v0, ngày 08/10/2026**. Chủ hợp đồng rà và chốt trước cuối ngày 12/10. Sau khi chốt, đổi theo quy trình ở mục 3 của `docs/PHAN_CONG_VA_BAN_GIAO_2026-10-08.md`.

## 1. Luật

1. **Gói biết lõi; lõi không biết gói.** Code trong đường dẫn lõi không import từ đường dẫn gói.
2. **Lõi không chứa từ của lĩnh vực.** Trong mã nguồn và chuỗi hiển thị của lõi không có các từ trong `banned_terms`. Lõi lấy từ ngữ từ `vocabulary` của gói.
3. **Ngoại lệ tới sau 22/10.** Tên biến môi trường `VINHOMES_*`, tên bảng `vh_*`, tên package và tên dịch vụ `vinhomes_api`, `vinhomes-api` không tính là vi phạm. Đổi tên trước buổi demo trực tiếp là rủi ro không đáng.
4. **Vi phạm đã biết.** Kiểm tra trong CI có danh sách `known_violations`. CI chỉ đỏ khi xuất hiện vi phạm **mới**. Mỗi lần chuyển xong một module thì xóa dòng tương ứng; danh sách chỉ được ngắn đi.
5. Chú thích trong code và tệp test không bị kiểm từ cấm; lệnh import thì có.

## 2. Cấu hình kiểm tra (`boundary.schema.json`)

`examples/boundary.json` là bản khởi đầu. Hai đường dẫn lõi còn để trống tên vì Team Chiến đặt tên trong việc CN-0 (hạn 09/10).

## 3. Gói lĩnh vực

Một gói là một thư mục. Bộ đọc gói bằng Python (việc PH-2) nằm trong lõi và là nơi duy nhất đọc các tệp này.

| Tệp | Nội dung | Bắt buộc |
|---|---|---|
| `domain.yaml` | Từ vựng, cấp địa điểm, nhóm dịch vụ, các bước của vụ việc. Theo `domain.schema.json` | Có |
| `brand.yaml` | Tên sản phẩm, màu, logo. API trả lúc chạy để giao diện đổi màu không cần build lại | Có |
| `agents/<mã>.yaml` | Định nghĩa agent: vai trò, phạm vi, prompt, tool được cấp, thông số, ca đánh giá | Có |
| `prompts/` | Prompt của Supervisor và Tiếp nhận có từ ngữ của lĩnh vực | Có |
| `tools/<tên>.json` | Bản khai tool theo HD-3 | Nếu gói có tool riêng |
| `knowledge/` | Tài liệu nguồn và tệp kê | Nếu có |
| `data/` | Dữ liệu mẫu theo HD-7 | Nếu có |

`service_categories[].code` phải khớp mã nhóm dịch vụ trong cơ sở dữ liệu. `case_stages` là các bước hiện trên thanh tiến trình của một vụ.

## Ví dụ

- `examples/domain.vinhomes.yaml` và bản JSON tương đương dùng để kiểm lược đồ.
- `examples/boundary.json`

## Còn mở

- Vị trí thư mục gói trong repo (PH-2 quyết định; bố cục đích là `packs/vinhomes/`).
- Danh sách từ cấm đầy đủ: bản nháp có 8 từ, Team Phái bổ sung sau lần chạy đầu.
- Lược đồ của `brand.yaml` và `agents/<mã>.yaml` chưa có trong bản nháp này; Team Phái viết cùng PH-2, dựa trên định dạng gói của OpenBot ở `server/src/tenant-package.ts`.
