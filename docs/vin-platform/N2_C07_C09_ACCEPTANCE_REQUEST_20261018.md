# N2 → N1: hai contract cần để đóng nghiệm thu

Đối chiếu producer `2edf060a` ngày 18/10/2026. N2 giữ ownership theo bảng 0.2, không sửa authority/Domain/storage N1. Đây là yêu cầu cụ thể, chưa phải API đã giao hoặc test PASS.

**Cập nhật:** N1 đã giao C07 `43897e9b`, C09 `d4a25cd0` và source-filter/direct lookup `bccbc8e7`. N2 đã ghép và nối consumer. Nội dung bên dưới giữ làm tiêu chí truy vết; kết quả chạy thật xem S15 trong N2_HANDOFF, không dùng trạng thái yêu cầu ban đầu thay trạng thái mới.

## C07 — phương án riêng

Domain đã nhận `SourceIntent.action=plan-decision` nhưng projection hiện không có phương án để UI đọc và không có revision riêng cho nó. Cần projection canonical đã ACK chứa phương án được phép cho đúng cư dân: ID, revision/version chính xác mà `ResidentPlanDecision` dùng, trạng thái, nội dung review (title/summary, items/steps, amount/currency nếu có), quyền quyết định và payload/schema quyết định. N1 xác nhận tên trường/shape và cung cấp fixture cùng test stale revision. Không suy quyền từ pending work approval hoặc case version.

Nghiệm thu: đúng owner đọc được nội dung; wrong owner/revoked link bị từ chối; sửa phương án sau khi UI mở review thì lần click cũ bị 409, reload mới quyết định được; replay cùng key trả cùng receipt, không thực hiện hai lần; xem/hủy review không ký intent; model không được gọi quyết định. Giữ riêng outer case canonical version và revision của đối tượng quyết định.

## C09 — lịch sử, lookup và repair sau 100 job

`PersonalJobs.list(context,kind)` hiện lấy 100 bản ghi cũ nhất. N2 đang phải lọc sau list tại `_personal_jobs.run_views/recover_delivery`, `_publish_batch.repair_batch` và `_workforce_console` publication status; job thứ 101 trở đi không có trong ledger/repair dù persistence tồn tại.

Cần API owner-scoped đọc phân trang có thứ tự ổn định `(created_at,job_id)`, limit bounded, cursor opaque, has_more/next_cursor; lọc source schedule/channel/conversation trước limit. Cần lookup theo job ID có kiểm kind, tenant, owner/revision để repair không quét trang hoặc query SQL authority trong consumer. Không bỏ wrapper `jobs.context_for`/fencing/lease hoặc cho query theo owner do client gửi. Giữ list cũ tương thích cho legacy nếu cần.

Nghiệm thu: ít nhất 125 job cùng loại, hai nguồn và hai owner; đọc đủ không trùng/mất, job thứ 125 xuất hiện đúng ledger, repair được khi đã có 100 job trước; cursor giả/sai owner/kind/filter bị từ chối; revoke chặn lookup/repair; delivery retry không gọi model. Gửi SHA + public helper/DTO + fixture sau khi N1 commit; N2 nối và chạy browser/runtime/PG gate trên bản ghép.

## Production và UAT

Chủ dự án cần xác định URL/stack mục tiêu và người ký UAT nghiệp vụ. N2 đang dựng RC cách ly và kiểm thử bằng provider scripted; không dùng key model thật, không tự bật cohort hoặc tắt intake cũ. PASS RC/fixture không phải xác nhận cư dân/Domain thật hoặc production cutover.
