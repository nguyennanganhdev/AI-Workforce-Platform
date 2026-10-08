# HD-4: Sự kiện sống cho giao diện

Chủ: Team Chiến. Bên phát: Team Đông.
Trạng thái: **bản nháp v0, ngày 08/10/2026**. Chủ hợp đồng rà và chốt trước cuối ngày 12/10. Sau khi chốt, đổi theo quy trình ở mục 3 của `docs/PHAN_CONG_VA_BAN_GIAO_2026-10-08.md`.

Màn hình phòng điều hành vẽ từ một dòng sự kiện, không hỏi lại trạng thái. Cùng dòng sự kiện đó, khi đã lưu, dùng để phát lại một phiên.

## Đường đi

1. Bộ điều phối gửi sự kiện tới API: `POST /internal/coordination/v1/case-events`, thân là mảng sự kiện theo `event.schema.json` (không có `seq`). Xác thực bằng token dịch vụ như các lời gọi nội bộ khác.
2. API cấp `seq`, lưu vào một bảng chỉ thêm, rồi đẩy tới trình duyệt.
3. Trình duyệt nhận qua `GET /cases/{case_id}/events?after_seq=` dạng `text/event-stream`, theo kiểu `graph_events` đang có trong `v3_agent_library.py`. Mất kết nối thì nối lại với `after_seq` cuối cùng đã nhận.
4. Phát lại: đọc cùng bảng từ `seq` 1, phát theo khoảng cách thời gian đã ghi. Giao diện hiện chữ "Đang phát lại".

Các bước đường dẫn là đề xuất; Team Chiến chốt.

## Loại sự kiện và `payload`

| `type` | Khi nào | `payload` |
|---|---|---|
| `session.started` | Phiên mở | `agents[]`, `subject` |
| `phase.changed` | Đổi pha | `phase`: `independent`, `review`, `merge`, `execution`, `closed` |
| `agent.started` | Agent bắt đầu một lượt | `task_id`, `activity` (một câu để hiện trên thẻ) |
| `agent.tool_call` | Sau mỗi lần gọi tool | `tool`, `status`, `source_id` |
| `agent.finished` | Agent xong lượt | `task_id`, `summary`, `duration_ms`, `tokens` |
| `agent.failed` | Lượt thất bại | `task_id`, `code`, `message` |
| `entry.added` | Một mục được nhận vào hồ sơ | `entry_id`, `kind`, `statement`; có `target_entry_id` với phản đối, có `plan_version` và `step_index` với bước phương án |
| `entry.blocked` | Một mục bị hạ hoặc bị từ chối | `entry_id`, `status` (`demoted` hoặc `blocked`), `reasons[]`, `statement` |
| `metrics.updated` | Sổ chi phí đổi | Các số của một vụ theo HD-5 |
| `human.action` | Người duyệt, từ chối, giao việc, nộp kết quả | `action`, `note` |
| `session.waiting` | Phiên chờ người | `waiting_for`: `customer`, `management`, `staff`; `reason` |
| `session.closed` | Phiên đóng | `outcome` |

## Quy tắc

1. `event_id` do bên phát cấp và ổn định. Gửi lại cùng `event_id` không tạo sự kiện thứ hai.
2. Sự kiện chỉ mang đủ để vẽ. Nội dung đầy đủ của một mục đọc qua HD-2.
3. Không đưa khóa, token, nội dung prompt hay dữ liệu cá nhân ngoài tên hiển thị vào sự kiện.
4. Bên phát gửi không chặn: gửi lỗi thì ghi log và đi tiếp, phiên không dừng vì giao diện.

## Ví dụ

- `examples/recorded-session.json`: 15 sự kiện của một phiên hai agent. **Team Chiến dựng khung màn hình từ tệp này** (hạn 13/10).
- `examples/event-entry-blocked.json`: sự kiện cho bước 3 của kịch bản demo.

## Còn mở

- Có phát sự kiện chữ đang gõ của agent hay không (bản nháp: không; chỉ `activity` một câu).
