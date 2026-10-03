# Reception Agent operation API flow

- Ngày: 2026-10-01
- Yêu cầu: Hoàn thiện các operation API theo luồng Reception trong tài liệu, để API xác thực/lưu nghiệp vụ rồi trả dữ liệu cho Reception Agent tự chọn bước tiếp theo.

## Thay đổi
- Thêm `execute` và `reconcile` có session cư dân, tenant scope, kiểm tra quyền tài nguyên và idempotency trong PostgreSQL.
- Nối draft, assessment, phân giải BQL, handoff tạo ticket/team và message schema_v2, polling kết quả Supervisor, cập nhật/hủy ticket và escalation vào các nghiệp vụ V3 hiện có.
- Trong workspace có proxy Hono chỉ mở hai endpoint Reception, chỉ nhận POST, yêu cầu same-origin và chuyển tiếp cookie phiên; proxy FE–BE này được loại khỏi commit API-only. Cập nhật hướng dẫn để phân biệt contract FastAPI với proxy chưa phát hành.
- `process_self_help` trả `501` nếu chưa cấu hình nguồn knowledge/RAG; API không gọi model hoặc tự chọn hướng xử lý.

## File/module chính
- `services/vinhomes-api/src/vinhomes_api/v3_reception_operations.py` — dispatcher và transaction cho các operation Reception.
- `services/vinhomes-api/src/vinhomes_api/v3_reception.py`, `v3_resident.py` — lưu draft và assessment, tạo ticket cùng snapshot kết quả.
- `services/vinhomes-api/src/vinhomes_api/main.py` — đăng ký router Reception.
- `services/vinhomes-api/scripts/grant_v3_api_role.sql`, `seed_v3_faker.sql` — quyền receipt và Supervisor version cho demo.
- `server/src/app.ts`, `server/src/vinhomes/resident-proxy.ts`, `server/src/vinhomes-demo-gateway.ts` — proxy same-origin qua Hono.
- `my-docs/Endpoint cần có của reception agent.md` — request, operation, kết quả và URL Hono.
- `my-docs/API_CHO_AGENT_TOOLS.md`, `API_ENDPOINTS_AGENT_TOOLS.md` và `API_CHO_AGENT_TOOLS_DAY_DU.docx` — cập nhật danh mục và bản bàn giao input/output cho operation Reception.

## Quyết định & giả định
- Dùng danh tính và quyền của cư dân trong session; `context` chỉ để truy vết và đối chiếu, không cấp quyền.
- Handoff kiểm tra dữ liệu cư dân, coverage và Supervisor destination rồi mới tạo ticket/team/message trong cùng transaction.
- Agent runtime nhận kết quả nghiệp vụ và tự tiếp tục; API không chạy agent, không phân loại hội thoại, không sinh câu trả lời.
- Bản đẩy API-only gồm backend FastAPI, schema/migration PostgreSQL và docs liên quan; loại FE và proxy Hono để phát hành riêng.

## Xác minh
- `python -m compileall` cho các module FastAPI liên quan: đạt.
- Ruff check cho `v3_reception_operations.py`, `v3_reception.py`, `v3_resident.py`, `main.py`: đạt.
- Ruff format check cho hai module Reception mới/sửa: đạt. Format check mở rộng có báo `main.py` và `v3_resident.py` chưa theo formatter toàn file; không format lại để tránh thay đổi lớn ngoài luồng này.
- FastAPI OpenAPI import xác nhận có `/internal/reception/operations/execute` và `/internal/reception/operations/reconcile`.
- `bun run typecheck` trong `server`: đạt; `git diff --check`: đạt.
- Không chạy test suite hoặc gọi API nghiệp vụ với database trong lượt này.

## Rủi ro / việc còn lại
- `process_self_help` chưa dùng được cho đến khi có nguồn knowledge/RAG cư dân.
- Chưa xác minh handoff end-to-end trên database đang chạy; cần chạy migrations/seed demo tương ứng và gọi luồng với session/actor có dữ liệu cư dân, coverage, channel và Supervisor.
