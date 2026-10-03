# API nghiệp vụ mới và database V3

Phạm vi: HTTP endpoint dùng chung cho frontend và agent tools. Không viết code tool, factory/evaluation agent, AgentScope runtime hoặc endpoint gọi RAG/`answer_or_escalate`.

## 1. Kiến trúc và cách chạy

```text
Frontend / agent runtime
  → Hono: user, phiên đăng nhập, quyền người yêu cầu
  → FastAPI :8000: kiểm tra scope, version, trạng thái; xử lý nghiệp vụ
  → PostgreSQL V3 Docker :5544: trạng thái, sự kiện, phê duyệt, dữ liệu demo
```

Chạy `services/CHAY_DEMO_API.cmd`. Giao diện demo: `http://localhost:8000/demo/ui`; contract Swagger: `http://localhost:8000/docs`. Launcher áp dụng migration và seed bổ sung trước khi chạy API; seed không reset các workflow đã thực hiện.

Database `vinhomes_v3` là PostgreSQL thật. Dữ liệu cư dân, nhân viên, camera, liên hệ, hóa đơn và sensor là dữ liệu giả. URL/credential nằm trong `.local-v3-faker`, được gitignore; không đưa vào frontend.

Demo dùng header `X-Demo-Actor`: `resident`, `management`, `technical`, `security`, `admin`. Ngoài demo, API xác minh cookie qua `VINHOMES_API_AUTH_URL`; agent gọi theo quyền người yêu cầu đã được Hono xác thực. Client không được tự khai role hay tenant để cấp quyền.

## 2. Mapping API cho agent tools

| Nhu cầu | Endpoint | Input chính / output |
| --- | --- | --- |
| load_resident_context | `GET /resident/context` | Danh tính hiện tại, các căn hộ đã xác minh, building/domain IDs |
| create_ticket_draft | `POST /resident/chats/{id}/ticket-drafts` | Mảng sự cố đã được bên gọi phân tích; trả draft và trường thiếu |
| Chốt một sự cố trong draft | `POST /resident/chats/{id}/ticket-drafts/{draft_id}/incidents/{index}/commit` | Chỉ tạo khi đủ field, trả ticket; chống trùng theo draft/index |
| resolve_management_destination | `GET /management-units/resolve` | `buildingId`, `domainId`, `serviceCategoryId`; trả BQL phụ trách |
| Theo dõi tiến độ cư dân | `GET /resident/tickets/{id}/progress` | Trạng thái, mốc sự kiện cho cư dân và tiến độ công việc |
| Đề xuất phương án | `POST /tickets/{id}/plans` | title, steps/category/description, estimated_amount, ticket_version, idempotency_key |
| BQL duyệt phương án | `POST /plans/{id}/management-decision` | decision, version, note; approve → resident_pending |
| Cư dân duyệt phương án | `POST /resident/plans/{id}/decision` | decision, version, note; approve → workOrderIds |
| asset.read | `GET /assets`, `GET /assets/{id}` | Lọc buildingId; hồ sơ thiết bị đúng scope |
| sensor.read | `GET /assets/{id}/sensor-readings` | Giá trị, đơn vị, thời điểm, nguồn đã ghi DB; không kết nối BMS trực tiếp |
| Nhập số liệu sensor | `POST /assets/{id}/sensor-readings` | parameter/value/unit/measured_at/source; BQL được phép ghi |
| maintenance_history.read | `GET /assets/{id}/maintenance-history` | Phân trang lịch sử đã xác nhận |
| technical.get_active_outage | `GET /technical/active-outages` | buildingId; gián đoạn chưa khôi phục |
| technical.record_measurement | `POST /work-orders/{id}/measurements` | parameter/value/unit/note/measured_at; người được phân công hoặc BQL |
| technical.submit_executor_result | `POST /work-orders/{id}/executor-results` | version, diagnosis, repair_notes; yêu cầu ảnh trước/sau và điều kiện hoàn tất |
| technical.verify_resolution | `GET /work-orders/{id}/resolution-check` | ready và checklist evidence/nước/quyền thao tác/QC |
| maintenance_history.append | `POST /assets/{id}/maintenance-history` | work_order_id, note; work đã hoàn thành và được xác minh |
| utility_isolation.request | `POST /work-orders/{id}/permission-requests` | kind=utility_isolation, details.utility=electricity; nước dùng API water hiện có |
| area_restriction.request | Cùng endpoint permission-requests | kind=area_restriction, reason, details, work_order_version, idempotency_key |
| apartment_entry.request | Cùng endpoint permission-requests | kind=apartment_entry; ghi yêu cầu và chờ quyết định BQL |
| vendor_dispatch.request | Cùng endpoint permission-requests | kind=vendor_dispatch; ghi yêu cầu và chờ quyết định BQL |
| Quyết định quyền thao tác | `POST /permission-requests/{id}/decision` | status, version, note; pending → approved/rejected; approved → completed/cancelled |
| Điều phối nhân viên | `GET /staff/available`, `POST /work-orders/{id}/assignments` | Scope/chuyên môn/ca trực/capacity; phân công có version và hạn nhận |
| Nhận/từ chối việc | `POST /assignments/{id}/response` | accepted + eta_at hoặc rejected + rejection_reason |
| Security camera/contact | `GET /security/cameras`, `GET /security/emergency-contacts` | buildingId, dữ liệu DB trong scope |
| Cảnh báo khẩn cấp | `POST /tickets/{id}/emergency-alerts` | message, ticket_version, key; snapshot danh sách nhận theo thứ tự |
| ACK/chuyển cấp | `POST /security/alerts/{id}/ack`, `/escalate` | version; ACK đúng người, chuyển cấp sau deadline |
| Đề nghị điều/hủy bảo vệ | `POST /work-orders/{id}/security/dispatch-request`, `/cancel-request` | version, reason, key; dispatch thêm staff_id; BQL quyết định qua approvals |
| Chi phí và bên chịu phí | `GET /tickets/{id}/financial-summary`, `POST /tickets/{id}/invoices` | Phương án dự toán; payer/issuer và line items do BQL xác định, tiền tính ở server |
| Phát hành hóa đơn | `POST /invoices/{id}/issue` | Chuyển draft → issued trong DB; không gọi nhà cung cấp hóa đơn |
| Ghi tiền thực thu demo | `POST /invoices/{id}/demo-payments` | amount/key; ghi intent/payment/allocation thật, chỉ bật ở local demo |
| get_report_filter_options | `GET /reports/filter-options` | building/category/employee IDs được phép |
| get_employee_performance_summary | `GET /reports/employee-performance` | buildingId/fromDate/toDate; số việc, đúng hạn, thời gian, redo, điểm |
| get_employee_feedback_details | `GET /reports/employee-feedback` | buildingId/staffId/limit/offset; phản hồi và tham chiếu công việc |
| get_repair_revenue_summary | `GET /reports/repair-revenue` | building/category/kỳ; billed/collected/outstanding; không bịa phân loại tiền công/vật tư |
| get_incident_frequency_summary | `GET /reports/incident-frequency-summary` | buildingId/fromDate/toDate/categoryId; interval=day/week/month; thống kê theo thời gian, loại và tỷ lệ |
| get_report_supporting_records | `GET /reports/supporting-records` | kind=tickets/work_orders/invoices, building và kỳ, phân trang |
| create_report_export | `POST /reports/exports` | kind/building/category/kỳ/format=docx/key; job/report ID |
| get_report_export_status | `GET /reports/exports/{id}` | ready/failed, downloadUrl theo quyền người tạo |
| initiate_image_upload | `POST /resident/chats/{id}/image-uploads` | filename/mime/size/SHA256/key; fileId/uploadId/uploadUrl |
| Upload bytes | `PUT /image-uploads/{id}/content` | Raw bytes, kiểm tra kích thước/checksum/signature |
| complete_image_upload | `POST /image-uploads/{id}/complete` | Backend kiểm tra object thực tế trước khi đánh dấu ready |
| get_conversation_images | `GET /resident/chats/{id}/images` | Ảnh ready đã gắn vào message; khôi phục theo conversation |
| attach_images_to_ticket | `POST /tickets/{id}/conversation-images` | file_ids; cùng chat nguồn, chống liên kết trùng |
| get_image_read_access | `GET /conversation-images/{id}/read-access` | Link có hạn, gắn người yêu cầu; vẫn cần xác thực |
| Factory output record | `POST /rooms/{id}/agents`, `PUT /rooms/{id}/agents/{agent_id}/configuration` | Agent draft; mô tả/prompt/tham chiếu MCP và namespace hợp lệ |
| Evaluation output record | `POST /rooms/{id}/agents/{agent_id}/review-submissions` | Config hash, round, evaluator, ít nhất 6 ca distinct đã pass; không chạy đánh giá |
| Admin duyệt agent | `GET /admin/agent-reviews`, `POST /admin/agent-reviews/{id}/decision` | approve → active + version; reject → giữ draft để sửa/gửi lại |
| Agent version | `GET /rooms/{id}/agents/{agent_id}/versions` | Snapshot cấu hình bất biến trong registry chung |
| Tạo team | `POST /rooms/{id}/teams` | ticket_id, supervisor_version_id, member_version_ids, key |
| Shared Task Board | `GET/POST /teams/{id}/tasks`, `PATCH /teams/{id}/tasks/{task_id}` | Task cha/con, member, status/result/version; không tự đổi work order |
| Shared Mailbox | `GET/POST /teams/{id}/mailbox` | Sender/recipient member, direct/broadcast/result, key; lưu actual requesting user |
| Shared team state | `PATCH /teams/{id}/state` | version/status/state; completed chỉ khi task đã xong/hủy |
| Context Builder input | `GET /rooms/{id}/context` | ticketId + bounded room messages/tasks; runtime chọn prompt |
| Đề xuất memory | `POST /tickets/{id}/memory-candidates` | namespace/text/evidence/reason/key; pending, admin review riêng |

Các endpoint có version trả 409 khi dữ liệu thay đổi; tải lại trước khi quyết định. Giữ nguyên idempotency key khi retry cùng request, dùng key mới cho hành động mới.

## 3. Luồng chính

Các API JSON cho agent tools bổ sung `agentContext` chỉ gồm operation, facts, missingFields, resourceContext và source. API là code nghiệp vụ: xác thực, kiểm tra quyền/input/điều kiện nghiệp vụ, đọc/ghi database và trả dữ liệu. Không gọi AI/LLM, không phân tích hội thoại, không sinh câu hỏi/khuyến nghị và không quyết định bước tiếp thay agent.

Schema response chung hiện được khai báo cho 49 endpoint JSON, gồm các API tool và bước hỗ trợ; con số này không phải số tool runtime. Response giữ dữ liệu nghiệp vụ hiện có (ví dụ ticket snapshot, items, status, version, validation checks). Caller/agent tự diễn giải response và chọn bước tiếp; mọi endpoint tiếp theo vẫn kiểm tra quyền và trạng thái. Endpoint tải bytes vẫn trả file.

Tạo ticket và retry trả snapshot: ticket có nội dung/status/version, location/category/managementDestination, plans/workOrders, linkedImages/conversationImages, managementNotification. `creationOutcome=created/replayed` phân biệt tạo mới với retry; trạng thái retry lấy từ database hiện tại. Không tự gắn toàn bộ ảnh của một chat vào một ticket.

### Ticket và HITL

1. Cư dân tạo chat; upload ảnh, complete rồi gửi message có `file_ids`.
2. Agent đọc context; nếu thiếu thông tin, giữ draft và hỏi lại. API không tự diễn giải câu nói.
3. Đủ thông tin → commit từng sự cố trong draft. Một chat có thể tạo nhiều ticket, từng ticket có timeline riêng.
4. Đề xuất phương án → BQL duyệt → cư dân duyệt. Chỉ sau bước cư dân, API tạo work order theo các step.
5. BQL/phần điều phối gọi availability và assignment. Nhân viên nhận việc, ảnh trước/sau, cập nhật kết quả.
6. API kiểm tra evidence, quyền thao tác và nước; tạo yêu cầu nghiệm thu. Cư dân đồng ý hoặc yêu cầu làm lại.
7. Ticket có nhiều công việc được đóng khi các công việc bắt buộc và nghiệm thu đã đạt; trạng thái team không thay thế các quyết định này.

### Agent được tạo từ UI

Tạo draft → bên tích hợp cung cấp configuration → cung cấp bản ghi evaluation → admin approve/reject. Reject giữ draft để sửa và gửi lại; approve tạo version và cho phép mention/add vào team. Dữ liệu evaluation giả phải ghi rõ là synthetic; API không chứng nhận đã chạy sandbox hay LLM.

### Billing/report

Dự toán trong phương án → BQL xác định payer và line items → invoice draft → issued → demo payment/allocation → báo cáo đọc tổng hợp từ các bảng này. Doanh thu vẫn dùng hóa đơn issued; thực thu tách riêng. Export hiện hỗ trợ DOCX đồng bộ, không quảng cáo PDF/XLSX hay worker nền.

## 4. Ranh giới còn lại

- Hono tiếp tục sở hữu đăng nhập/đăng ký/credential/user toàn platform. API `/admin/accounts` hiện quản lý membership V3; tạo synthetic identity chỉ ở demo. Không bổ sung auth thứ hai trong FastAPI.
- Camera/sensor là metadata/số liệu seed, không gọi camera/BMS ngoài. Quyền thao tác là bản ghi yêu cầu, không điều khiển van, điện hay mở cửa thật.
- Storage ảnh hiện là local demo với checksum; S3/MinIO cần adapter của bên triển khai. Link đọc vẫn yêu cầu xác thực và hết hiệu lực sau restart.
- Không triển khai API gọi RAG theo yêu cầu. Tra cứu knowledge đã tồn tại không đồng nghĩa có pipeline RAG/LLM mới.
- Giao diện demo cũ được chỉnh tối thiểu để đi qua HITL; những API mới khác có contract trên Swagger để FE/runtime tích hợp.

## 5. Tiến độ kiểm chứng

**Response mới:** đã kiểm tra cú pháp/lint, khởi động FastAPI và xuất tài liệu từ OpenAPI có `AgentBusinessResponse`. Chưa chạy lại toàn bộ scenario HTTP nghiệp vụ sau khi bổ sung `agentContext`. Các kết quả dưới đây thuộc những lần chạy trước thay đổi response này.

Đã áp dụng migration 0003/0004/0005 và seed bổ sung trên PostgreSQL thật. Migration 0005 đồng bộ capacity: công việc đã hoàn thành/hủy/từ chối không chiếm tải hiện tại của nhân viên.

Đã chạy thủ công qua HTTP:

- Draft → ticket → BQL/cư dân duyệt phương án → phân công → nhân viên nhận/di chuyển/thực hiện → ảnh trước/sau → executor result → cư dân nghiệm thu → đánh giá và lịch sử bảo trì.
- Agent draft → cấu hình → 6 ca evaluation synthetic → admin approve → version → team → task → mailbox → completed. Không chạy agent runtime.
- Hóa đơn 50.000, thanh toán giả 25.000, retry không trùng, còn phải thu 25.000.
- Link đọc ảnh trả đúng bytes, đổi người dùng bị từ chối. Export DOCX tải được và có document.xml.
- Sai quyền admin/room và version task cũ bị từ chối. Trong demo, thiếu header mặc định resident; đây không phải kiểm tra đăng nhập production.
- Sau restart FastAPI, ticket closed và team completed vẫn đọc lại được.

Cú pháp Python, Ruff F cho module V3, migration JSON và cú pháp JavaScript đạt. Chưa kiểm chứng toàn bộ nhánh từ chối/redo, đồng thời hoặc tích hợp Hono production. Xem `changes/2026-10-01-v3-database-business-apis.md` để biết giới hạn xác minh.
