# Kế hoạch nối Vinhomes Operations với database V3

## Trạng thái ngày 30/09/2026

- `dev_TeamHoang` đã được hợp nhất vào `frondendVuVietAnh`. Chênh lệch mã nguồn chỉ là tài liệu phân công; schema V3 đã có trên cả hai nhánh qua `develop`.
- API OpenBot hiện tại đã biên dịch với schema V3 (`bun run --cwd server typecheck`). Chưa có API nghiệp vụ Vinhomes Operations trong `server/src`.
- Backend đã có API đọc V3 tại `GET /api/vinhomes/tickets`, `GET /api/vinhomes/tickets/:id`, `GET /api/vinhomes/tickets/:id/triage`, `GET /api/vinhomes/work-orders`, `GET /api/vinhomes/work-orders/:id`. Các API dùng phiên đăng nhập, tenant context và quyền theo scope; chỉ dành cho admin, management và staff. Chưa có lệnh ghi nghiệp vụ.
- `app/src/features/vinhomes-operations/hooks/use-operations-data.ts` vẫn dùng mock và `localStorage`. `use-incident-detail.ts` lấy timeline và message từ mock.
- Schema V3 dùng `tickets` làm hồ sơ chính. Các khái niệm `Incident`, `Task`, `ActionRequest`, `Approval`, `WorkOrder`, `Evidence`, `QC` của giao diện hiện tại không thể ánh xạ một đối một bằng cách đổi tên bảng. Không ghi dữ liệu mock trực tiếp vào bảng V3.

## Hợp đồng dữ liệu cần chốt trước khi nối giao diện

| Luồng FE | Nguồn V3 dự kiến | API cần có |
|---|---|---|
| Danh sách và chi tiết sự cố | `tickets`, `ticket_events`, `ticket_files` | `GET /api/vinhomes/tickets`, `GET /api/vinhomes/tickets/:id` |
| Tiếp nhận, phân loại | `ticket_assessments`, `ticket_triage_decisions`, `ticket_triage_reviews` | `GET /api/vinhomes/tickets/:id/triage`, `POST /api/vinhomes/tickets/:id/assessments`, `POST /api/vinhomes/tickets/:id/triage-decisions` |
| Công việc và phân công | `work_orders`, `work_assignments`, `team_tasks`, `task_dependencies` | `GET /api/vinhomes/work-orders`, `GET /api/vinhomes/work-orders/:id`, lệnh phân công và chuyển trạng thái |
| Phê duyệt | `work_approvals`, `work_approval_evidence` | `GET /api/vinhomes/approvals`, lệnh duyệt/từ chối |
| Ảnh và chứng cứ | `files`, `file_objects`, `file_uploads`, `evidence_items`, `ticket_files` | Khởi tạo upload, hoàn tất upload, gắn chứng cứ, URL đọc có thời hạn |
| QC, làm lại | Cần chốt bảng/contract QC trong V3; `ticket_reviews` là đánh giá của người dùng về nhân viên, không phải QC hiện trường | Đọc kết quả QC và lệnh ghi nhận QC/làm lại |

Tên endpoint ở đây là đề xuất hợp đồng; cần xác nhận trường và trạng thái theo `server/src/db/design/merged.json` trước khi viết handler. FE nên dùng ID UUID từ API và mã hiển thị riêng, không dùng ID mock như `INC-2026-001` làm khóa.

## Thứ tự triển khai

1. **Nền API:** tạo router `/api/vinhomes` trong server, xác thực phiên, lấy tenant/user từ server và dùng `withDatabaseScope` cho mọi truy vấn. Quyền theo vai trò và scope nghiệp vụ phải được kiểm tra ở service, vì RLS V3 chỉ giới hạn tenant. Chốt OpenAPI request/response/error, pagination và idempotency cho lệnh ghi.
2. **Đọc ticket:** trả danh sách, chi tiết, timeline, triage và các liên kết work order/evidence. Map kiểu API sang kiểu FE bằng adapter riêng; giữ nguyên trạng thái loading, empty và error.
3. **Đọc công việc:** thêm danh sách theo người phụ trách, kanban, work order, approval và QC. Chuyển các hook FE từ mock sang query client theo từng màn hình; bỏ lưu trạng thái nghiệp vụ trong `localStorage` sau khi luồng tương ứng chạy qua API.
4. **Lệnh ghi:** tiếp nhận, phân loại, phân công, chuyển trạng thái, phê duyệt, upload chứng cứ, QC và redo. Mỗi lệnh phải ghi event/audit cùng transaction, kiểm tra version để tránh ghi đè và trả lỗi có mã ổn định cho FE.
5. **Đối soát:** xác minh luồng Ticket → WorkOrder → Evidence → QC → redo/đóng ticket theo từng vai trò. Dùng dữ liệu seed hợp lệ của V3; bộ mock hiện có chứa liên kết sai đã ghi trong `docs/vinhomes-operations-role-flow-data-audit.md`.

## Điều kiện hoàn thành

- Không còn đường ghi nghiệp vụ Vinhomes vào `localStorage`; mock chỉ dùng cho preview/story.
- Mọi màn hình operations đọc cùng một ticket/work order từ API, có loading/error/empty state và quyền phù hợp.
- API chạy trên database V3 đã migrate; các lệnh ghi bảo toàn tenant, quan hệ, audit và idempotency.
# Cập nhật API ngày 30/09/2026

FastAPI trên cổng 8000 hiện có các route đọc/ghi V3 cho ticket, assessment,
review triage, work order, phân công, phê duyệt, file/chứng cứ, QC, vệ sinh,
an ninh, nhà thầu và duyệt chi phí. Danh sách và contract cụ thể nằm trong
`services/HUONG_DAN_SWAGGER_8000.md` và `/docs`. Các route QC, vệ sinh,
an ninh, nhà thầu, duyệt chi phí dùng migration
`server/drizzle/0001_vinhomes_operations.sql`.

Frontend `use-operations-data.ts` vẫn dùng mock/localStorage; việc chuyển từng
hook sang API và adapter kiểu dữ liệu vẫn là bước tích hợp FE riêng. Hono cổng
3001 vẫn chỉ có các route đọc V3 cũ. Upload ảnh hiện chỉ hỗ trợ local loopback;
production cần kết nối object store và quét tệp.
