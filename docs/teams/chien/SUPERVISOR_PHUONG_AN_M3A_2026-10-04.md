# Supervisor đề xuất phương án, Ban quản lý duyệt (M3a) — 04/10/2026

Người đọc: Team Chiến (backend, Operations), Team Đông (lõi Supervisor và groupchat), Team Quang (agent kỹ thuật).

## Kết quả

Sau khi agent chuyên môn trả lời xong, Supervisor không còn dừng để Ban quản lý tự viết phương án. Nó lập một
phương án từ các câu trả lời đó, backend lưu phương án vào bảng phương án sẵn có với **tác giả là agent
Supervisor**, và phiên chờ Ban quản lý quyết định. Ban quản lý đọc phương án ngay trong ô "Phiên điều phối" của
ticket trên Operations và bấm "Duyệt phương án" hoặc "Từ chối phương án" (bắt buộc có ghi chú).

Phương án của Supervisor đi đúng vòng đời phương án đã có của backend (`v3_plans.py`): `management_pending` →
Ban quản lý duyệt → `resident_pending` → cư dân đồng ý → `approved` và sinh phiếu thi công. Không có vòng đời thứ hai.

## Luồng

1. Mọi việc trong phòng đã `completed` → Supervisor được hỏi riêng một câu chỉ để lập phương án
   (`PLAN_GUIDE`, schema chỉ còn `plan` và `pause`).
2. Runtime gửi `POST /internal/coordination/v1/teams/{team}/plans`. Backend khóa ticket, kiểm tra phiên bản
   ticket, ghi `vh_ticket_plans` (`proposed_by_agent_id` = Supervisor, `proposed_by` rỗng), ghi sự kiện
   `plan.proposed` với tác nhân là agent, tăng phiên bản ticket và báo vào phòng BQL.
3. Supervisor đọc lại `view`: thấy `plan_id` và phiên bản ticket mới thì ghi nhận phương án vào checkpoint.
4. Runtime gửi `POST .../plans/{plan}/approval-request`: backend xác nhận phương án còn chờ Ban quản lý.
   Phiên chuyển sang `waiting_management`.
5. Ban quản lý quyết định bằng `POST /plans/{id}/management-decision` (cổng đã có từ trước).

## Thay đổi

| Nơi | Thay đổi |
|---|---|
| `server/drizzle/0013_supervisor_plans.sql` | `vh_ticket_plans.proposed_by` cho phép rỗng; thêm `proposed_by_agent_id` (khóa ngoại tới `agents`), ràng buộc đúng một tác giả; thêm `proposal jsonb` |
| `v3_coordination.py` | `POST /teams/{id}/plans`, `POST /teams/{id}/plans/{plan}/approval-request`; `view` trả `plan` (id, trạng thái, người nhận duyệt, hạn); `authorize` mở `draft/plan` và `backend/approval.requested` |
| `v3_session.py` | `/tickets/{id}/session` trả `room.plan` |
| `agent-coordination/src/vinhomes` | `Plans` (nơi lưu phương án), `BackendActions` (yêu cầu BQL duyệt), `PLAN_GUIDE`, `Authority.inspect` đọc `plan` |
| Operations | Khối "Phương án Supervisor đề xuất" trong phiên của ticket, hai nút duyệt và từ chối |

Lõi của Team Đông không bị sửa. Phần ghép dùng đúng các cổng lõi đã định nghĩa: `publisher`
(`DraftPublisher`) và `backend.dispatch`.

## Các quyết định trong lát cắt này

- **Một phương án là một phiếu thi công.** Vòng đời sẵn có biến mỗi bước của phương án thành một phiếu thi
  công. Các bước Supervisor viết là các bước của một lần kỹ thuật viên tới căn hộ, nên backend lưu chúng thành
  một bước duy nhất (đánh số 1, 2, 3 trong mô tả), thuộc danh mục của ticket. Danh sách bước nguyên văn, vai trò
  người làm, thời gian, điều kiện và chi phí nằm trong `proposal`.
- **`result_refs` do runtime gắn.** Phương án dựa trên mọi câu trả lời mà Supervisor đã chấp nhận; id lấy từ
  checkpoint, không lấy từ chữ model viết. Model `gpt-5.4-mini` từng trả `complete_task` lặp lại khi được hỏi bằng
  hướng dẫn chung, nên bước lập phương án có hướng dẫn và schema riêng.
- **Hạn duyệt 30 ngày** (`PLAN_APPROVAL_WINDOW`). Lõi Supervisor cần một hạn; backend không tự hết hạn phương án.
- **Người nhận duyệt** là đơn vị quản lý của workspace (`management-unit:<id>`), không phải một người cụ thể:
  quyền duyệt thật vẫn do `management-decision` kiểm tra theo người đăng nhập.
- Một ticket chỉ có một phương án đang chờ (ràng buộc sẵn có). Ticket đã có phương án chờ thì phương án của
  Supervisor bị từ chối và phiên dừng với `backend_rejected:409`.

## Lỗi tìm thấy khi chạy thật và đã sửa

Lượt của agent chuyên môn bị cắt giữa chừng trong 3 trên 6 lần chạy thật với `gpt-5.5`: client HTTP dùng chung có
hạn đọc mặc định 5 giây, còn model suy luận có thể im lặng lâu hơn trước chữ đầu tiên. Phòng ghi lượt đó là "không
rõ kết quả" và phiên đứng lại. Đã bỏ hạn đọc cho luồng SSE (hạn 120 giây của adapter vẫn chặn cả lượt), có test,
và runtime nay ghi log nguyên nhân khi một lượt hỏng. Operations cũng hiện lý do khi phiên bị giữ vì một bước
chưa rõ kết quả, trước đây màn hình chỉ hiện "Đang điều phối".

## Kiểm chứng

| Việc | Kết quả |
|---|---|
| Backend pytest (PostgreSQL tạm) | 65 đạt, 6 bỏ qua; có test mới cho cả vòng: đề xuất → BQL duyệt → cư dân đồng ý → 1 phiếu thi công |
| `agent-coordination` | 431 đạt (phần ghép 24, thêm: mất biên nhận khi lưu, backend từ chối, model không lập phương án) |
| Operations | `tsc` sạch; `connected-operations-ui` 6, `agent-reviews-ui` 2 |
| Hồi quy stub (`e2e`) | 65 / 2 / 9 / 9 |
| Model thật trên PostgreSQL tạm | phiên tới `waiting_management` sau khoảng 18 giây, phương án được lưu |
| Trình duyệt, đăng nhập thật | 10/10 bước: cư dân gửi → Lễ tân tạo ticket → Supervisor lập phương án → BQL thấy và duyệt |

## Chưa làm

- **Sau khi Ban quản lý duyệt, phiên chưa đi tiếp.** Phương án ở `resident_pending` nhưng Supervisor chưa nhận
  được quyết định, nên chưa gửi `plan_approval_requested` cho Lễ tân và cư dân chưa được hỏi. Backend đã có sẵn
  hai đầu của đoạn này (`v3_reception_supervisor.py`); thiếu đường đưa quyết định của BQL về runtime (M3b).
- Ban quản lý từ chối: phương án thành `rejected`, Supervisor chưa lập lại.
- Phiên bị giữ vì "chưa rõ kết quả" chưa có nút chạy lại (M4).
- Model đôi khi viết lẫn một từ ngoại ngữ trong phương án (thấy một lần). Ban quản lý đọc trước khi duyệt; chưa
  có kiểm tra tự động.
- Danh sách bước trên Operations chưa có số thứ tự (CSS chung của trang bỏ số).
