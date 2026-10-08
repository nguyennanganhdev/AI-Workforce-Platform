# HD-2: Hồ sơ vụ việc

Chủ: Team Đông. Bên lưu: Team Chiến (CN-2). Team dùng: Hoàng, Quang, Phái.
Trạng thái: **bản nháp v0, ngày 08/10/2026**. Chủ hợp đồng rà và chốt trước cuối ngày 12/10. Sau khi chốt, đổi theo quy trình ở mục 3 của `docs/PHAN_CONG_VA_BAN_GIAO_2026-10-08.md`.

Hồ sơ vụ việc là danh sách **chỉ thêm** các mục. Agent, tool và con người đều ghi vào cùng một hồ sơ.

## Một mục (`entry.schema.json`)

| Trường | Ý nghĩa |
|---|---|
| `entry_id`, `seq` | Do máy chủ cấp. `seq` tăng dần trong một hồ sơ. |
| `kind` | Xem bảng dưới. |
| `statement` | Nội dung, một ý. |
| `author` | `agent`, `human`, `system` hoặc `tool`, kèm mã và tên hiển thị. |
| `sources[]` | Nguồn, theo định dạng mã nguồn ở HD-3. |
| `target_entry_id` | Bắt buộc với `objection` và `agreement`: mục bị phản đối hoặc được đồng thuận. |
| `supersedes_entry_id` | Mục này thay cho mục nào. Mục cũ vẫn còn, giao diện gạch đi. |
| `plan_version`, `step_index` | Bắt buộc với `plan_step`. Giao diện nối bước trên màn hình với mục theo hai số này. |
| `data_origin` | Nhãn nguồn gốc theo HD-7. Mục thừa hưởng nhãn "yếu nhất" trong các nguồn của nó. |
| `check` | Kết quả của thư viện kiểm nguồn: `accepted`, `demoted` (bị hạ thành giả định), `blocked` (bị từ chối), kèm lý do. Do máy chủ ghi. |

| `kind` | Ai ghi | Nguồn |
|---|---|---|
| `fact` | Tiếp nhận, tool, con người | Bắt buộc: tin nhắn, kết quả tool hoặc tệp |
| `finding` | Agent chuyên môn | Bắt buộc ít nhất một |
| `assumption` | Agent | Không cần. Không được là căn cứ duy nhất của `plan_step` |
| `objection`, `agreement` | Agent, con người | `objection` bắt buộc có nguồn |
| `question` | Agent, Supervisor | Không cần |
| `plan_step` | Supervisor | Bắt buộc: ít nhất một `fact` hoặc `finding` |
| `assignment`, `result` | Hệ thống, nhân viên, khách hàng | Lệnh việc, ảnh, tin nhắn |

## API (đề xuất; Team Chiến chốt đường dẫn)

| Việc | Lời gọi |
|---|---|
| Ghi một mục | `POST /internal/core/v1/cases/{case_id}/entries`, thân theo `write.schema.json` |
| Đọc hồ sơ | `GET /internal/core/v1/cases/{case_id}/entries?after_seq=` |
| Mở một nguồn | `GET /internal/core/v1/sources/{source_id}` trả kết quả tool, đoạn tài liệu, tin nhắn hoặc tệp |

## Quy tắc ghi

1. **Chống ghi trùng.** Bên ghi tự cấp `request_id` ổn định (ví dụ `mã lượt:mã việc:khóa nhận định`). Gửi lại cùng `request_id` với cùng nội dung: trả về mục đã ghi, mã 200. Cùng `request_id` khác nội dung: mã 409.
2. **Không sửa, không xóa.** Sửa bằng cách ghi mục mới có `supersedes_entry_id`.
3. **Máy chủ kiểm trước khi nhận.** Mỗi `sources[].id` phải mở được trong phạm vi vụ việc. Sai thì mục bị `demoted` hoặc `blocked` theo luật ở mục 7.3 của tài liệu thiết kế; mục vẫn được lưu để giao diện hiện ra.
4. **Ai ghi gì.** Dữ kiện của khách hàng: chỉ Tiếp nhận. Kết quả tool và mục của agent: bộ điều phối. Lệnh việc và kết quả thực hiện: API nghiệp vụ.
5. Mọi lời gọi tách theo tenant; bên ghi không gửi `tenant_id` trong thân.

## Ví dụ

- `examples/write-finding.json`: một yêu cầu ghi.
- `examples/closed-case.json`: **một hồ sơ đã đóng đầy đủ**. Đây là khuôn cho bộ dữ liệu D-30 (hồ sơ lịch sử) và cho mục ký ức.

## Còn mở

- Mức chi tiết của `subject` (căn hộ, thiết bị, khách hàng) để ký ức tra theo.
- Có tách chi phí, vật tư, thời lượng của `result` thành trường riêng hay để trong `statement` (bản nháp: trong `statement`; ký ức cần số thì nên tách).
