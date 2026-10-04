# Checklist Team Chiến nối hệ thống

Ngày 04/10/2026. Đọc [luồng tổng thể và hiện trạng](README.md) trước. Đây là backlog tích hợp đề xuất, **không phải giao việc đã được tất cả team xác nhận**. Tên API mới phải chốt tại shared contracts trước khi implement; ưu tiên reuse module/port đã có.

## 1. Hợp đồng tối thiểu cần chốt

| Hợp đồng | Producer → consumer | Những gì phải xác định |
|---|---|---|
| Danh tính và delegation | Chiến → Hoàng/Đông/Quang | Tenant/principal/actor, scope, binding/run, expiry/revocation, backend quyết định actor; service authentication khác business authorization |
| Reception ↔ Supervisor V2 | Chiến giữ chuẩn; Hoàng/Đông tích hợp | Enum đúng chiều, message ID/correlation, ticket/generation/version, source_message_id, retry/conflict, one pending request |
| Session/Room | Chiến ↔ Đông | Permanent room khác ticket session; pin group/agent version, members, task/message/run mirror, pause/resume/cancel và trạng thái |
| Publish/release | Chiến/Phái → Đông | Artifact/hash/prompt, agent_version/release ID, model/provider, catalogue/tool schema, readiness/revocation và evaluation |
| Tool execution | Đông → Chiến/Quang/Phái | Run/delegation/grant, operation ID, schema/effect, expected version, receipt/reconcile, result/error/cancel |
| Plan/approval/work/events | Chiến → Đông/Hoàng | Backend authoritative snapshot; payload version; nhận/lưu/sửa phương án; duyệt đúng người/bước; events có ID/version và dedupe |
| Runtime storage | Adapter được chỉ định → Đông/Hoàng | Checkpoint serialization version, CAS/transaction, inbox acceptance, lease/fence, receipts/ledger/records/cursor, retention/recovery |
| Report/knowledge | Chiến/Hoàng/Quang → Đông/Hoàng | Authorized dataset/retrieval; citations/lineage; published/revoked; file/artifact access và outcome |

Không đổi tên trường cơ học giữa các envelope khác nghĩa. Có wire fixture success + forbidden + duplicate + stale cho TS/Python và kiểm published schemas so với runtime models. API source chuẩn ở Chiến; consumer proposal phải được phân biệt với endpoint đang mount.

## 2. Trình tự và tiêu chí nghiệm thu

### M0 — Chốt nền triển khai và quyền

Owner đầu mối: Chiến; phối hợp tất cả team và owner vận hành.

- [ ] Pin baseline/ref và các thay đổi đang làm; nhập phần Factory/Security cần dùng từ nhánh Phái bằng quy trình review, không checkout đè workspace.
- [ ] Chọn backend route cho từng capability, gateway browser và identity/session giữa Hono–FastAPI. Connected UI không tự chuyển sang mock khi lỗi.
- [ ] Chốt workspace ownership/groupchat configuration/routing cho mỗi BQL; phân biệt account, management unit, channel và session.
- [ ] Reconcile 193 bảng live với migration/canonical catalog/ORM. Bảng SQL ngoài ORM vẫn có owner và migration source; không tái tạo baseline vào DB có dữ liệu.
- [ ] Có dữ liệu vận hành tối thiểu: cư dân/căn hộ đã xác minh, hai scope, coverage, category, policy published, staff ca/skill, file storage, agent release/grants.
- [ ] Chốt runtime PostgreSQL adapters và kế hoạch drain/migrate SQLite; bảo vệ serialization, role/credential, backup/restore.

**Đạt khi:** fresh bootstrap lên được những service được chọn; hai người khác scope không đọc/ghi được tài nguyên nhau; token dịch vụ không tự cấp business authority; gateway built UI gọi đúng backend. Không cần bật mọi module nghiệp vụ để đạt M0.

### M1 — Một ticket thật tới phân tích specialist

Owner: Chiến + Hoàng + Đông.

- [ ] Message commit → Reception turn → authorized draft/policy/routing/handoff → ticket_submitted.
- [ ] Coordination durable accept → verify → binding/run → checkpoint → accepted.
- [ ] Published specialist catalog → resolver → agent admission → pin release → model turn → task/result/room mirror.
- [ ] Hiển thị BQL đúng ticket/session/agent; đạt `analysis_ready` hoặc trạng thái cần xử lý rõ ràng.

**Đạt khi:** hai ticket chạy đồng thời không trộn context; retry handoff không tạo trùng; chưa có specialist/model thì giữ pending với lý do thật. M1 chưa được gọi là full autonomous flow.

### M2 — Specialist có tool và RAG

Owner: Đông (adapter), Quang (tools/RAG), Chiến (authorization/data host); Phái cho Security.

- [ ] Thay `NoTools` bằng tool gateway adapter cho các capability được cấp; không bypass adapter guard để nhận agent có tool.
- [ ] Reuse `/api/technical/v1` và RAG host hiện có; kiểm dependency thực sự được inject/mount trong process chạy.
- [ ] Catalogue ref/version/schema/effect là thật. `defaultToolRefs` RAG cho Factory lấy từ cấu hình/canonical catalogue được backend kiểm quyền.
- [ ] Check grant/scope/release/generation trước từng tool call, receipt/idempotency cho mutation và reconcile outcome unknown.

**Đạt khi:** specialist trong chính session gọi được tool hợp lệ/RAG có citation; cùng lượt với grant thiếu/scope sai/release revoked bị chặn; không chỉ test host bằng tài khoản admin ngoài phòng. Tool physical-operation request không được ghi là đã thao tác thiết bị.

### M3 — Hỏi thêm, phương án và phê duyệt

Owner: Chiến (API/state/events), Đông (Supervisor), Hoàng (cư dân).

- [ ] Bind BackendActions, EventVerifier/EventIngress, draft/plan storage và reconcile ports thật; planner được phép dùng những operation backend đã hỗ trợ.
- [ ] Hỏi thêm → information_provided → resume đúng câu/version; một pending request mỗi ticket.
- [ ] Persist phương án → quản lý duyệt → cư dân duyệt khi cần → verified event → Supervisor tiếp tục.
- [ ] Decision có source_message_id/recipient/generation/version; bản sửa có version mới và duyệt lại.
- [ ] Decline/request_changes/expiry/cancel/conflict đều có UI và đường trả lời hợp lệ.

**Đạt khi:** hai phản hồi lặp chỉ áp dụng một quyết định; cùng ID khác nội dung conflict; cư dân B không duyệt ticket A; phản hồi cũ không mở quyền chạy tool; sự cố chung được miễn đúng policy. Restart lúc chờ vẫn trả lời được request cũ bằng cùng bản.

### M4 — Thi công, QC, cư dân xác nhận và đóng

Owner: Chiến + Đông + Hoàng + Quang/Phái theo loại việc.

- [ ] Assignment dùng backend, kiểm ca/skill/capacity; offer/accept/decline/timeout/reassign lưu version.
- [ ] Staff uploads trước/sau được finalize/scan/hash/quyền; completion có kết quả và actual cost được xác nhận nếu dùng.
- [ ] QC đạt/không đạt và redo: mọi work bắt buộc phải đạt trước khi thông báo hoàn tất.
- [ ] Completed chỉ sau backend acceptance; cư dân xác nhận/chưa hài lòng; backend đóng hoặc yêu cầu xử lý tiếp; BQL duyệt đóng nếu nghiệp vụ yêu cầu.
- [ ] SLA/escalation/notification có worker hoặc cơ chế chạy thật; fail/duplicate không mất thông báo/giao hai người.

**Đạt khi:** một work con xong không đóng ticket; QC fail không gửi xong; resident dissatisfaction có đường xử lý tiếp; generation mới từ chối checkpoint/decision cũ; hủy có kết quả backend. Có bằng chứng trace xuyên từ cư dân tới trạng thái cuối.

### M5 — BQL custom agent, Report và learned knowledge

Owner: Chiến (Builder/store/grants), Phái (Factory), Đông (runtime), Hoàng (Report), Quang (RAG/learning).

- [ ] BQL→scoped catalogue→Factory HTTP→integrity/fingerprint→atomic draft/version→evaluation/review→publish→Room resolver. Không tạo grant tự động.
- [ ] Factory down/hash sai/resource đổi/quyền thu hồi: không lưu/chạy artifact sai; duplicate construction-save không tạo agent trùng.
- [ ] Published version giữ prompt/spec/hash; sửa/rollback tạo version/release theo quy tắc; session đang chạy không nhận draft mới.
- [ ] Hai BQL dùng Report template riêng, dataset cùng định nghĩa metric nhưng scope khác; preview/export/download pin snapshot và kiểm lại quyền.
- [ ] Knowledge candidate→review→publication lineage→document version→retrieval, revoke/retention; không chỉ export Markdown thủ công.
- [ ] Nếu đưa procedure/price vào release: verified outcome/actual cost, đủ sample/phạm vi/currency/as_of, version algorithm/estimate và self-help eligibility tests.

**Đạt khi:** agent BQL tự tạo được dùng trong đúng phòng/ticket, gọi đúng tool, bị chặn ngoài quyền; Report số khớp snapshot; tri thức chưa duyệt/đã thu hồi không bị truy xuất. Các capability chưa chọn cho release được ghi rõ deferred, không gọi đã hoàn thành.

### M6 — Chịu lỗi và triển khai giới hạn

Owner: owner Platform/QA/DevOps được giao; Chiến giữ acceptance nghiệp vụ.

- [ ] Production ingress `/api/business` và Hono routes; Resident/Operations artifacts; private service discovery; secrets riêng, database roles giới hạn.
- [ ] Test restart ở từng điểm gửi intent/remote commit/chưa nhận response/chờ duyệt; reconcile cùng operation identity, không retry mù bằng ID mới.
- [ ] Hai runtime worker tranh cùng message: lease/fence/CAS chỉ cho một owner apply; owner cũ sau expiry không được ghi state.
- [ ] Retry hữu hạn, dead-letter/blocked queue, backoff, timeout/budget/rate limit, graceful shutdown; readiness kiểm dependencies theo capability.
- [ ] Kiểm thu hồi account/grant/release lúc đang chạy, lỗi model, context injection và phạm vi dữ liệu trong logs/artifacts.
- [ ] Đo throughput/p95/budget và polling load theo quy mô thực; không đặt con số SLA sản phẩm khi chưa đo và chốt.
- [ ] Backup/restore PostgreSQL + object store + runtime state; chạy restore drill, đối chiếu phiên đang dở và files/citations.
- [ ] Staging có data/config thật hợp lệ, E2E roles, deployment manifest, alert/runbook/operator recovery và rollback.

**Đạt khi:** evidence đã chạy cho commit/config/data xác định; các gate dưới đây qua đủ cho capability phát hành. Unit test xanh hoặc `/health` 200 không thay các kiểm tra này.

## 3. Ma trận kiểm tra xuyên hệ thống

| Kịch bản | Kết quả bắt buộc |
|---|---|
| Hai cư dân, hai tòa/tenant | Không đọc/duyệt/đính kèm file/session/tri thức của nhau |
| Hai ticket chung phòng BQL | Task/mail/context/run/results tách theo ticket/generation |
| Duplicate message | Replay đúng kết quả; ID giống payload khác conflict |
| Decision đã nhận, gửi lại ID khác | Không áp dụng phê duyệt/hành động lần hai |
| Model timeout sau backend mutation | Receipt lookup/reconcile ID cũ, không tạo lại công việc |
| Hết lease, worker cũ quay lại | Fence từ chối ghi; worker mới tiếp tục đúng checkpoint |
| Restart chờ duyệt | Cùng câu/phương án/pending version; backend quyền vẫn được kiểm |
| Plan đổi / ticket reopen | Bản cũ bị vô hiệu, không auto-upgrade phản hồi |
| Agent revoked / grant revoked | Không tiếp tục lượt/tool trái quyền; state có lý do/operator path |
| Không có coverage/agent/nguồn | Hàng chờ/hỏi thêm/handoff rõ; không random fallback hoặc bịa |
| QC fail / một việc con xong | Tiếp tục xử lý; không completed/closed sớm |
| BQL Factory agent / Report agent | Hash/release pin, scoped tool/data, download reauthorization |
| Built UI thay Vite | API đúng route và auth; không 404 do proxy chỉ tồn tại ở dev |

## 4. Gói bàn giao ngắn cho từng team

Mỗi team gửi cho Chiến **một gói**: entrypoint/service hoặc factory export; contract/version và fixtures; env **tên biến** không secret; storage/migration/data dependencies; grants/auth cần; health/readiness semantics; test commands/kết quả đã chạy; error/retry/reconcile; known gaps; commit/ref pin.

Chiến giữ một integration matrix capability×producer×consumer×version×status×evidence. Khi schema/port đổi, update producer và consumer cùng rollout; pending V1 phải drain/reconcile trước V2, không đổi câu “đồng ý” cũ thành approval mới.

Một nơi giữ definition/schema chuẩn, một nơi giữ quy tắc nghiệp vụ chính thức, một nơi giữ mỗi loại state. Projection/cache có thể có nhiều nhưng phải ghi rõ nguồn và cách rebuild. Đó là điểm giúp maintain dễ hơn; không phải gom tất cả code hoặc tất cả bảng vào một service.
