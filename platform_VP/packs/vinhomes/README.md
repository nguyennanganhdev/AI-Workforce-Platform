# awp-vinhomes: gói domain Vinhomes cho platform lõi `awp`

Gói này nối platform với dịch vụ `vinhomes-api` qua `/integration/v1/*` (hợp đồng:
`vinhome_Recident/docs/domain/HOP_DONG_TICH_HOP.md`). Platform là một **client của domain**, không đọc database của domain
và không thay mặt cư dân.

## Nối thế nào

Phía domain, đăng ký client nhận hồ sơ (in bí mật một lần):

```
python -m vinhomes_api.database client --id platform --kind platform --accepts-cases
```

Phía platform:

```python
from awp.app import build_app
from awp_vinhomes import VinhomesPack

app = build_app(settings, packs=[VinhomesPack.from_env()])
```

`AWP_SERVICE_KEYS` phải có một khóa với domain `vinhomes` (`khoa:ten_tenant:vinhomes`); gói được cài cho tenant đó, một tenant cho mỗi gói.

| Biến môi trường | Mặc định | Ý nghĩa |
|---|---|---|
| `VINHOMES_API_URL` | bắt buộc | gốc của vinhomes-api, ví dụ `http://vinhomes-api:8000` |
| `VINHOMES_CLIENT_SECRET` | bắt buộc | bí mật `ics_...` của client |
| `VINHOMES_CLIENT_ID` | `platform` | gửi trong `X-Client-Id` |
| `VINHOMES_POLL_SECONDS` | `3` | chu kỳ đọc hộp thư khi không có thư mới |
| `VINHOMES_CURSOR_FILE` | `./vinhomes_inbox_cursor.json` | nơi lưu con trỏ hộp thư |
| `VINHOMES_KNOWLEDGE_TTL` | `300` | giây giữ gói tri thức trước khi hỏi lại (`since=<version>`) |
| `VINHOMES_START_DELAY` | `0` | giây chờ trước lần đọc đầu (lõi đã khởi động gói sau khi AgentScope sẵn sàng; chỉ cần khi chạy gói ngoài lõi) |
| `VINHOMES_TIMEOUT` | `15` | giây tối đa cho mỗi lệnh gọi |

## Luồng: nhận vé, xử lý, trả kết quả

1. Vòng đọc hộp thư (`GET /cases/inbox`) lấy từng thư theo thứ tự. `ticket_submitted` thành một case (`CaseIntake`,
   `external_ref` = mã vé; vé mở lại ở thế hệ n thì `mã#gn`). Năm loại thư còn lại thành `FollowUp` của case đang mở.
   Chống trùng nhờ `message_id` (core giữ). Con trỏ chỉ được lưu sau khi cả trang xử lý xong; lỗi tạm thời thì lùi 1s, 2s... tối đa 60s
   và đọc lại đúng trang đó. Thư hỏng hoặc dành cho case đã kết thúc thì ghi log và bỏ qua, không chặn thư sau.
   Mỗi vé mới được gửi thêm một thư `accepted` (biên nhận, thất bại thì thôi).
2. Trưởng nhóm `vinhomes_supervisor` (model `strong`) đọc vé bằng `get_ticket`, tra `search_knowledge`, có thể mời chuyên viên
   `ky_thuat`, `ve_sinh`, `an_ninh`, `chi_phi` (model `cheap`), gửi phương án bằng `propose_plan`, rồi chốt `CaseFinalize`. Guard của core
   chỉ cho nêu con số có trong bằng chứng; `rules.py` chặn thêm: từ nội bộ, "đã sửa xong/đã hủy" khi vé chưa `resolved/closed/cancelled`,
   "đã gửi/đã chuyển" khi chưa có công cụ nào làm, hứa giờ hoặc "miễn phí" không có nguồn.
3. Core đưa kết quả vào outbox; `deliver_result` đọc lại vé (`GET /cases/{id}`) để lấy đúng phiên bản hiện tại rồi `POST .../results`.

| Kết quả của core | Thư gửi domain | Lý do |
|---|---|---|
| vé đã `cancelled` (bất kể kết quả) | `cancelled` | domain chỉ nhận khi vé thật sự đã hủy |
| `resolved`, vé `resolved`/`closed` | `completed` | domain tự kiểm phiếu việc; bị từ chối thì giữ lại trong outbox của core kèm lý do |
| `resolved`, vé còn mở | `in_progress` | platform đã trả lời hoặc gửi phương án, nhưng đóng vé là việc của nhân viên (hợp đồng 3.3) |
| `needs_human` / `cannot_resolve` | `failed`, `NEEDS_HUMAN_REVIEW` / `CANNOT_RESOLVE`, `retryable=false` | một người tiếp quản |
| `failed` (lỗi của platform) | `failed`, `PLATFORM_ERROR`, `retryable=true` | |

`message_id` sinh từ nội dung, nên gửi lại là cùng thư (domain trả bản cũ). 409: đọc lại vé; nếu phiên bản đã đổi thì dựng và gửi lại **một** lần,
nếu không đổi thì dừng (`DeliveryRejected`), không gửi mù. Kết quả của vòng vé cũ (đã mở lại) bị bỏ.

## Quyền riêng tư

Thư vào mang tên và số điện thoại cư dân; gói chỉ giữ `resident_id` (`requester_ref`). Tên và số điện thoại gõ trong tiêu đề, mô tả, dữ kiện
hay tin nhắn được che (`[tên cư dân]`, `[số điện thoại]`). Công cụ không đọc và không trả dữ liệu cá nhân.

## Giới hạn đã biết

- **Chưa có dữ liệu thật để kiểm.** Test dùng máy chủ giả chép đúng hợp đồng và ràng buộc 409/422 trong mã backend; chưa chạy với vinhomes-api và Postgres thật.
  Model thật chưa được thử (test dùng model kịch bản).
- **Không có chính sách, giá, hạn nào trong gói.** Profile chỉ được dặn tra `get_ticket` và `search_knowledge`. Nếu gói tri thức của domain trống, agent phải nói chưa có thông tin.
  Chưa lọc tài liệu theo khu (`scope.zone_codes`), chỉ hiển thị cho agent.
- **Case của core kết thúc một lần.** Thư `plan_approved`, `plan_rejected`... đến sau khi case đã chốt thì bị bỏ (log). Cư dân đồng ý phương án thì domain tự tạo phiếu việc, nên không mất việc, nhưng platform không phản hồi thêm.
- **Chưa hỏi lại cư dân được.** Kết quả không có loại `information_requested` và `plan_approval_requested`; thiếu thông tin thì chốt `needs_human` (thành `failed`).
- **Chưa đọc nguồn sự kiện** (`/events`, ví dụ `ticket.sla_breached`), nên chưa có case chủ động.
- **Công nợ, đặt tiện ích, khách, thẻ** cần lượt ủy quyền do chính cư dân cấp; hồ sơ không mang lượt đó nên không có công cụ cho chúng. Vai `chi_phi` chỉ tra biểu phí trong tri thức.
- `propose_plan` không điền người thực hiện hay giờ hẹn (agent không có công cụ xem ca); Ban quản lý sắp xếp khi duyệt.
- Một tenant cho mỗi `VinhomesPack`; con trỏ lưu trong tệp cục bộ (mất tệp thì đọc lại từ đầu, core loại trùng).
- Nếu `submit` của lõi hỏng giữa chừng, lõi đóng vụ ở trạng thái `failed` và gửi kết quả `failed` về Vinhomes (lỗi tạm, thử lại được); gói không tự tạo lại vụ.
- Thư đến sau khi vụ đã đóng (ví dụ `plan_approved` muộn) bị lõi từ chối 409 và gói bỏ qua; lõi chưa có cách mở lại vụ.

## Chạy test

```
set PYTHONPATH=platform_VP\core\src;platform_VP\packs\vinhomes\src;platform_VP\core\tests
platform_VP\agentscope\.venv\Scripts\python.exe -m pytest platform_VP\packs\vinhomes\tests
```

(`pyproject.toml` đã khai `pythonpath`, nên chạy `pytest` trong thư mục gói cũng được.)
