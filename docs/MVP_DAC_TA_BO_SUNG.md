# MVP platform: đặc tả bổ sung (8 hạng mục của chủ dự án)

Cập nhật: 11/10/2026. Bổ sung cho `docs/WORKFORCE_V1_DAC_TA_TRIEN_KHAI.md` (vẫn có hiệu lực; hợp đồng đối tác vẫn là chuẩn cho API `/workforce/v1`). Người dùng đã giao quyền quyết định; các lựa chọn dưới đây là của người điều phối và phải được ghi vào `docs/WORKFORCE_V1_QUYET_DINH.md` khi làm.

Luật chung như đặc tả chính (mục 0): đơn giản trước, mọi hành vi có test chạy bằng model giả, không mã Vinhomes, không sửa `platform_VP/agentscope/src`, không commit, báo cáo trung thực.

## 1. Tám hạng mục và trạng thái khi bắt đầu

| # | Hạng mục | Trước khi làm | Việc |
|---|---|---|---|
| M1 | Bật MCP thành kho tool, tự phát hiện, còn sau restart | Một phần: admin gõ từng tool | Mục 2 |
| M2 | Build agent qua chat, phát hiện trùng, dùng lại | Thiếu | Mục 3 |
| M3 | Eval rồi mới phát hành, version, rollback | Một phần: có version và publish | Mục 4 |
| M4 | Leader chọn agent khi có request | Có: leader gọi `AgentCreate` trong team và tenant | Mục 5 (kiểm tra và nhật ký) |
| M5 | Booking có kiểm soát | Có: cổng đồng ý, sổ chống trùng, phục hồi | Mục 5 (mặc định bắt buộc đồng ý), kill thật ở P5b |
| M6 | Đúng tài khoản ban quản lý | Một phần: chỉ cô lập theo route | Mục 6 (thực thể manager) |
| M7 | Ticket nhiều lượt, không mất event | Có trên một tiến trình | Test có tên ở P5b (Postgres, Redis, kill) |
| M8 | Bàn giao vận hành và tích hợp | Một phần | Mục 8 (console, Docker, tài liệu) |

## 2. M1: MCP là kho tool

- `wf_mcp_servers` thêm `enabled` (mặc định false khi tạo qua đường mới), `last_discovered_at`, `last_error`.
- `wf_tools` thêm `source` (manual|discovered), `status` (proposed|active|gone), `schema` (ảnh chụp input schema + mô tả đã làm sạch), `discovered_at`.
- `POST /platform/v1/wf/routes/{id}/mcp/{name}/enable`: gọi `tools/list` (đường `PartnerMCP.list_tools(refresh=True)` đã có), tạo/cập nhật một dòng `wf_tools` cho mỗi tool. Mặc định an toàn: tool có `readOnlyHint=true` → `kind=lookup`, `status=active`; mọi tool khác → `kind=action`, `requires_consent=true`, `status=proposed` và **không dùng được** cho tới khi admin kích hoạt (xác nhận `tracking`, `client_reference_arg`). Tên trùng tool của platform bị từ chối. `disable` tắt server (tool của nó biến mất khỏi agent, dòng giữ nguyên). `refresh` so lại: tool biến mất → `gone`, tool mới → như trên, schema đổi → cập nhật ảnh chụp và ghi nhận.
- `PATCH /platform/v1/wf/routes/{id}/tools/{name}`: kích hoạt/sửa một tool (thay cho phải PUT cả bộ). PUT cũ vẫn chạy.
- Tool factory chỉ đưa cho agent tool `active` của server `enabled`. Khi server MCP không trả lời lúc khởi động lại, dùng ảnh chụp schema đã lưu (tool vẫn hiện, lời gọi lỗi rõ ràng) thay vì âm thầm bỏ tool.
- Thay route (`replace`): chép cấu hình MCP và tool sang route mới (ở trạng thái như cũ) để không mất kho tool.
- Test: bật → phát hiện đúng danh sách; mặc định an toàn; khởi động lại app trên cùng DB → kho tool còn nguyên, kể cả khi server MCP đang tắt; refresh phát hiện thêm/bớt; tool `proposed` không tới tay agent.

## 3. M2: build agent qua chat

- Phiên builder theo tenant admin: `POST /platform/v1/builder/sessions`, `POST .../{id}/messages`, `GET .../{id}`, `POST .../{id}/apply`. Lưu ở bảng `awp_builder_sessions` (tin nhắn, đề xuất hiện tại).
- Mỗi tin nhắn: gọi model (tầng `strong` của catalog) với đầu ra có cấu trúc, trả **đề xuất** gồm một hoặc nhiều mục: `action` (create|reuse|revise|clarify), bản nháp `AgentProfile` đầy đủ (với create/revise), `overlap_with` (key agent đã có), `reason`, và câu hỏi làm rõ nếu thiếu thông tin. Model nhận danh sách hồ sơ hiện có của tenant (key, mission, handles, refuses, trạng thái) và danh sách tool đang `active` trong kho (để gợi ý `tools_allow` có thật).
- **Phát hiện trùng có hai lớp**: (1) điểm trùng tất định trên `handles` + `mission` đã chuẩn hóa (bỏ dấu, chữ thường, bỏ từ dừng, Jaccard theo token) với mọi hồ sơ nháp/đã phát hành của tenant; (2) nhận định của model. Lớp (1) là cổng cứng: `create` có điểm trùng ≥ ngưỡng (cấu hình) với một agent đã có thì platform đổi thành `reuse` (hoặc yêu cầu lý do ghi đè rõ ràng khi apply). Kết quả luôn nêu trùng với agent nào và vì sao.
- `apply` chỉ tạo **bản nháp** (không bao giờ phát hành), hoặc với `reuse` thì không tạo gì và trả key agent dùng lại; `revise` tạo version nháp mới của agent đã có. Một phiên tạo được nhiều agent độc lập.
- Nội dung chat là dữ liệu không tin cậy: không được đổi tenant, không được cấp tool ngoài kho, không được tự phát hành.
- Test (model giả): tạo một agent; tạo hai agent trong một phiên; yêu cầu trùng nghiệp vụ → `reuse` và không có nháp mới; ghi đè có lý do; tool không có trong kho bị loại khỏi `tools_allow`; cô lập tenant.

## 4. M3: đánh giá rồi mới phát hành, version, rollback

- Bảng `awp_eval_cases` (tenant, profile key, tên, đầu vào, kết quả tool giả lập, các kiểm tra) và `awp_eval_runs` (tenant, key, version, trạng thái, điểm, kết quả từng ca, chi phí, thời gian, người chạy).
- Ca đánh giá: `input` (tin nhắn/nhiệm vụ), `fixtures` (tool → kết quả giả lập; không gọi MCP đối tác thật), `checks` tất định: `must_call`, `must_not_call`, `must_contain`, `must_not_contain`, `must_record_gap`, `grounded` (không con số nào ngoài bằng chứng), `expected_state` (với leader), `max_cost_usd`. Có bộ ca mặc định của platform cho mọi agent (không bịa số; từ chối việc ngoài phạm vi `refuses`; nói "không biết" khi thiếu dữ liệu).
- Trình chạy: chạy **đúng version đang nháp** trong sandbox (client/route sandbox nội bộ của tenant, tool lấy từ fixtures qua `rt.tool_factories`), với chuyên viên thì chạy nó dưới một leader đánh giá tối giản của platform, với leader thì chạy một workflow sandbox. Không ghi vào dữ liệu đối tác thật, không lộ ra `/workforce/v1`.
- `POST /platform/v1/profiles/{key}/versions/{v}/evals` (chạy), `GET .../evals` (kết quả), CRUD ca dưới `/platform/v1/profiles/{key}/eval-cases`.
- **Cổng phát hành**: `publish` trả `409 EVAL_REQUIRED` nếu lần chạy gần nhất của **đúng version đó** chưa đạt. Cho phép ghi đè có chủ đích: `{"override_reason": "..."}` được ghi lại (ai, khi nào, vì sao). Phát hành luôn là hành động của người (API admin/manager, nút trên console); không tool nào của agent phát hành được. Thêm `published_at`, `published_by`.
- **Rollback**: `POST /platform/v1/profiles/{key}/rollback {to_version}` phát hành lại một version đã từng phát hành (đang `retired`), version hiện tại thành `retired`; ghi lịch sử. Không cần eval lại (version đó đã qua cổng), nhưng ghi nhận.
- Lịch sử: `GET /platform/v1/profiles/{key}/history` (tạo, eval, phát hành, ghi đè, rollback).
- Test: publish không có eval → 409; eval đạt → publish được; eval trượt → 409; ghi đè có lý do được ghi lại; rollback trả version cũ và chuyên viên kế tiếp chạy version đó; ca đánh giá bắt được agent bịa số; cô lập tenant.

## 5. M4 và M5: kiểm tra bổ sung

- M4: khi phát hành leader, mọi key trong `team` phải là hồ sơ chuyên viên cùng tenant (422 nếu không tồn tại; cảnh báo nếu chưa phát hành). Tạo route với `leader_profile` không tồn tại/không phải leader → 422. Mỗi lần leader tạo chuyên viên ghi một mục case file (`invite`: loại được chọn, nhiệm vụ, các ứng viên được phép) để xem lại được vì sao chọn. Bộ eval mặc định có ca "chọn đúng chuyên viên" và "việc đơn giản không cần team".
- M5: tool `kind=action` mặc định `requires_consent=true`; muốn tắt phải có `consent_waiver` (lý do) ghi lại. Khởi động: approval `pending` mà phiên không đỗ → hủy và báo leader (đặc tả chính mục 13.25). Kill thật kiểm ở P5b.

## 6. M6: tài khoản ban quản lý

- Bảng `wf_managers` (id, tenant, client_id, tên, trạng thái). `wf_routes.manager_id` bắt buộc khi tạo route (route cũ trong DB dev không cần chuyển đổi: chưa có dữ liệu thật). Một khu có thể có nhiều manager; mỗi `external_management_ref` thuộc đúng một manager.
- Khóa vận hành theo manager: khóa `Bearer` loại `manager` (lưu băm như khóa đối tác) chỉ thấy và thao tác được workflow, operation, approval, receipt, `resolve`, hồ sơ agent và kho tool thuộc route của manager đó; admin tenant là quyền cao nhất. Khóa đối tác không đổi (hợp đồng cấm gửi id nội bộ).
- Yêu cầu của đối tác với ref của manager B không bao giờ tạo gì trên route của manager A (đã có ở mức route; thêm test với hai manager cùng khu, cùng client).
- Test: hai manager, hai ref, mỗi bên một workflow; khóa A nhận 404 với workflow của B và với `resolve`; danh sách chỉ thấy của mình; admin thấy cả hai.

## 7. Console quản trị tối giản

- Một trang tĩnh do chính `awp` phục vụ tại `/console` (HTML + một file JS + một file CSS, không cần bước build, không phụ thuộc CDN). Đăng nhập bằng khóa admin hoặc khóa manager (giữ trong `sessionStorage`, gửi bằng `Authorization: Bearer`); không cookie, không lưu khóa lâu dài.
- Màn hình: (1) Kho tool: server MCP bật/tắt, tool phát hiện được, kích hoạt; (2) Agent: danh sách, version, chat builder, ca đánh giá, chạy eval, kết quả, phát hành, rollback, lịch sử; (3) Route và manager; (4) Vận hành: workflow, trạng thái, operation, approval, receipt, `resolve`; (5) Chi phí. Giao diện tiếng Việt, nội dung do người dùng/đối tác nhập luôn được escape (không XSS).
- Console chỉ gọi API admin đã có; không có logic nghiệp vụ riêng. Test: trang được phục vụ, không có script ngoài, mọi lời gọi API cần khóa; một test trình duyệt ngắn nếu khả thi (không bắt buộc).

## 8. M8: đóng gói Docker và bàn giao

- `platform_VP/Dockerfile` (ảnh nền `python:3.12-slim` có sẵn cục bộ), cài `awp` và AgentScope vendored từ nguồn trong repo, chạy bằng user không phải root, không secret trong ảnh, `PYTHONUNBUFFERED`, `AWP_HOST=0.0.0.0`, healthcheck gọi `/platform/v1/health`, tắt êm khi nhận SIGTERM.
- `platform_VP/deploy/compose.yml`: dịch vụ `postgres`, `redis`, `minio` (ảnh có sẵn), job một lần `migrate` (cả bảng `awp` và storage của AgentScope), `api` phụ thuộc migrate thành công; volume có tên; cổng chỉ bind `127.0.0.1`; secret qua `env_file` (`deploy/.env.example`, kèm script sinh `AWP_SECRET_KEY` và khóa admin); tên project và cổng không đụng các stack khác của người dùng (`vp-platform-*`, `vinhomes-*`).
- Script khói `deploy/smoke.py`: trên stack compose đang chạy, đi hết các bước trong `docs/WORKFORCE_V1_HUONG_DAN_KET_NOI.md` với một MCP giả và model giả (hoặc model thật nếu có khóa): tạo client, key, manager, route, bật MCP, xác nhận route, `start_workflow`, đọc SSE, approval, provider event, close.
- Tài liệu bàn giao `docs/WORKFORCE_V1_BAN_GIAO.md`: chạy gì, khởi động thế nào, kết nối đối tác (liên kết), vận hành (bảng `attention_reason` → cách xử lý, xoay khóa, sao lưu), cái đã chứng minh và cái chưa; `openapi.json` xuất từ container.

## 9. Thứ tự xây

1. P5a (Postgres, Alembic, retention) — đang chạy.
2. B1: M1 + M4/M5 bổ sung + M6 (mặt điều khiển).
3. B2: M2 builder + M3 eval/cổng phát hành/rollback.
4. B3: console.
5. P5b: Redis, nhiều tiến trình, kill thật, test có tên cho M5 và M7.
6. P5c: MinIO (ảnh) và tải 20 workflow.
7. B4: Docker, script khói trên compose, tài liệu bàn giao.
8. Rà soát toàn hệ thống, sửa, chạy lại toàn bộ trên SQLite và Postgres.

Mỗi bước: xây → rà soát độc lập → sửa. Migration Alembic mới cho mọi thay đổi bảng.
