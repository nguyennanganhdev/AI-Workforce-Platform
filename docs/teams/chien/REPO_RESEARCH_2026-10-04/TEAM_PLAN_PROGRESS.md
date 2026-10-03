# Đối chiếu tiến độ team với kế hoạch — 04/10/2026

## Phạm vi và cách đọc bằng chứng

Baseline nghiên cứu **`a231575`** tại `E:\AI-Workforce-Platform`, đọc thêm refs đã fetch `origin/develop`, `origin/dev_TeamDong`, `origin/devTeamPhai`. Trong lúc audit có tác nhân khác commit `b2d3f37` bổ sung Coordination backend và tiếp tục sửa `agent-coordination/src/vinhomes/backend.py`, `ports.py`. Vì vậy các kết luận runtime dưới đây được **pin vào a231575**, không phủ nhận những WIP đang triển khai. Tests được chạy trước khi phát hiện các sửa runtime đó. Không checkout nhánh khác, không sửa source, không chạy migration hoặc gọi model có phí. Không tìm thấy `AGENTS.md` trong repo. Bảng nhánh/commit/author chi tiết nằm trong báo cáo Git riêng của đợt research này.

Nguồn kế hoạch chính: `docs/KE_HOACH_HOAN_THIEN_5_TEAM.md:154–275`; phân công chi tiết Hoàng: `docs/teams/hoang/PHAN_CONG_3_THANH_VIEN.md`; phân công Đông: `docs/teams/dong/PHAN_CONG_NOI_BO_COORDINATION.md`. Trạng thái READY/DONE trong tài liệu là trạng thái owner khai báo. Báo cáo này chỉ xác nhận phần có code/test hoặc giới hạn rõ ràng. Số test là số tại một snapshot và môi trường, không phải phần trăm hoàn thành sản phẩm.

## Kết luận về tiến độ sản phẩm

Repo đã vượt giai đoạn chỉ có ERD và mock UI: có backend nghiệp vụ Vinhomes FastAPI, UI cư dân/Operations, Reception runtime Python gọi backend, RAG, đăng nhập mật khẩu và quản lý agent theo phiên bản. Tuy nhiên, luồng Supervisor tự lập phương án và gọi specialist/tool thực vẫn chưa được nối trong composition Vinhomes hiện tại. Ban quản lý vẫn xử lý nghiệp vụ sau khi Supervisor nhận ticket và trả `accepted`.

Đây là một hệ thống phát triển có nhiều lát cắt chạy được. Chưa có đủ bằng chứng để nghiệm thu M1/M2/M3 toàn hệ thống hoặc tuyên bố production-ready. Không nên biến số bảng, số commit hoặc số test thành phần trăm tiến độ.

| Mốc kế hoạch gốc | Bằng chứng hiện có | Phần còn thiếu để nghiệm thu |
|---|---|---|
| M0 — nền, contract, ownership, schema, service health | Schema V3, phân công, tool contracts, Reception runtime, Coordination pinned AgentScope 2.0.9/entrypoint/Dockerfile; có service/session producer cho Vinhomes | Contract backend/framework thống nhất hết các capability; kho production của runtime; reproducible CI cho mọi gói; baseline toàn repo còn lỗi |
| M1 — cư dân → đúng BQL/group → tool → cập nhật → đúng cư dân; MinIO thật | Code và tài liệu demo/connected chạy intake tới BQL và xử lý bởi con người; Supervisor có lát cắt `ticket_submitted → accepted` | Specialist/room/model/tool thật trong Supervisor; chứng cứ đường file MinIO đúng yêu cầu; nghiệm thu liên team trên cùng môi trường |
| M2 — triage/SLA/dispatch thật; restart/retry/isolation; không mock trong đường nghiệm thu | Nhiều state machine, version check, scope check, QC gate; tests Coordination về lease/fencing/recovery; local SQLite | Multi-process/shared production storage; dispatcher tự vận hành với capacity/fairness/SLA; E2E thật xuyên Reception–Coordination–tools; quan sát lỗi/retry/revoke toàn hệ thống |
| M3 — Builder/Report/self-help/giá/UAT | Template Report, contribution/report consumer ports, learned-answer approval, agent version/release approval | Hai BQL tạo/chạy Report thật đúng scope, file render/provenance; self-help và price estimation đầy đủ; Factory và released specialist thực sự vào room |
| M4 — vận hành/domain thứ hai | Nhiều framework samples và cấu trúc domain | Domain thứ hai được nghiệm thu qua cấu hình; rollout/rollback/runbook/load/quota/cost và vận hành có bằng chứng |

Nguồn tiêu chí mốc: `docs/KE_HOACH_HOAN_THIEN_5_TEAM.md:271–275`; tiêu chí kiểm thử bắt buộc: cùng file `:401–431`.

## Team Hoàng: Reception và Report

| Thành viên / owner theo kế hoạch | Đã thấy trong code | Việc còn lại / kết luận |
|---|---|---|
| **Phan Dũng** — graph/prompt/eval, nội dung Report | `agent-reception/src/graph/workflow.py`, validation/contracts, prompt và tests graph; xử lý ảnh pending, knowledge, tạo ticket, active ticket, self-help branch, interrupt/resume | PD11 typed facade/V2 chưa hoàn tất: graph generic invoke không gọi được PH16 BackendToolPort. PD09/PD12/PD13/PD14 vẫn READY trong tài liệu, chưa đủ bằng chứng nghiệm thu tất cả |
| **Phan Hoàng** — tools/persistence/runtime/transport | PH16 strict facade 14 operations, HTTP transport/reconcile, SQLite checkpoint/session recovery. Code retry hiện sửa mất-response; runtime Python đã có trên checkout do tích hợp Team Chiến | Không đánh PH16 DONE toàn bộ vì consumer graph còn fail. PostgreSQL checkpointer/lease nhiều replica, event producer thật, V2 trọn vòng và Report job/storage còn thiếu |
| **Dương Dũng** — Report tools/application/metrics | Có baseline HTTP adapter lịch sử; ownership Reception tools đã chuyển sang Phan Hoàng | DD12/DD13 READY, DD14 BLOCKED_API trong kế hoạch. `server/src/reporting` trên baseline checkout chủ yếu narrative/layout Python; nhánh Report PHH riêng đã có 8 wrappers (mục dưới), nhưng chưa về develop. Không quy tự động code nhánh PHH cho Dương Dũng chỉ vì kế hoạch gán ownership |

Nguồn phân công: `docs/teams/hoang/PHAN_CONG_3_THANH_VIEN.md:111–123`, backlog `:133–205`; file này ghi rõ ownership HTTP đã chuyển, tránh tính cùng phần việc cho hai người.

### Kiểm thử hiện tại và sự khác nhau giữa hai đường Reception

Đã chạy lại ngày 04/10:

```powershell
$env:PYTHONUTF8='1'
& .\agent-reception\.venv\Scripts\python.exe -m pytest -q agent-reception/tests
```

Kết quả **350 passed, 1 failed, 9 skipped** trong 6.19 giây. Failure: `agent-reception/tests/tools/test_adversarial.py:396–418`, `test_existing_graph_can_reach_http_with_new_backend_port`. Graph dừng ở `phase=waiting_operation`, pending `create_ticket_draft`, **HTTP calls=0**.

Rerun riêng adversarial: **49 passed, 1 failed**. Bốn ca retry AD01 từng fail đã qua; `agent-reception/src/tools/backend.py:88` hiện xóa `last_response` sau transport/timeout loss. Vì vậy con số “5 test Lễ tân hỏng” trong báo cáo 03/10 không còn đúng cho snapshot hiện tại. Một failure tích hợp typed tool vẫn còn thật, không phải chỉ do tài liệu chưa cập nhật.

Graph còn gửi budget/signal trong generic request (`agent-reception/src/graph/workflow.py:1198–1212`), trong khi PH16 strict envelope không nhận field đó. `agent-reception/README.md` phần PH16 cũng nói graph V1 chưa chuyển facade.

Nhưng runtime Vinhomes đang dùng **adapter khác**: `agent-reception/src/runtime/service.py:196–203` inject `BackendOperations` từ `runtime/backend.py`, không inject `BackendToolPort` strict PH16. Adapter này dịch handoff/follow-up sang backend V2 (`runtime/backend.py:316–365`). Vì vậy “demo intake chạy” và “test graph→PH16 fail” có thể đồng thời đúng. Không dùng demo thành công để phủ nhận lỗi PH16, cũng không dùng PH16 fail để kết luận mọi Reception đều không chạy.

`runtime/backend.py:408–410` hiện trả self-help `unavailable` vì chưa có quy trình đã duyệt; có nhánh graph không chứng minh self-help product đã đạt H07. H08–H10 Report template và narrative có, nhưng end-to-end create/publish/run/export/permission vẫn thiếu. Kế hoạch yêu cầu metrics tính bằng code, nguồn/as_of/timezone và DOCX render (`docs/KE_HOACH_HOAN_THIEN_5_TEAM.md:171–173,348–362`).

### Nhánh Report Agent PHH riêng: có triển khai mới chưa tích hợp

Đã đọc `origin/codex/report-agent-PHH`, head **`796f909`**, cùng `docs/teams/hoang/reports/report-agent-PHH/PROGRESS_REPORT.md` trên ref đó. `git merge-base --is-ancestor origin/codex/report-agent-PHH origin/develop` trả 1: nhánh này **chưa được merge vào develop**.

Nhánh có `server/src/reporting/tools/{contracts,catalog,facade}.py`, `application/client.py`, `metrics/normalize.py` và tests. Tám wrappers: filter options, employee performance, feedback details, repair revenue, incident frequency, supporting records, export và export status; fixed routes gọi API backend của Team Chiến. Report ngày 03/10 tự ghi **256 passed** (222 tool + 34 narrative), HTTP/SQL-result boundaries và receipts mô phỏng; chưa chạy lại branch suite trong research này. Báo cáo của owner nêu rõ chưa gateway/AgentScope, SSO/PostgreSQL live, snapshot provenance đầy đủ hoặc chuyển template/narrative mới. Có implementation wrappers, chưa Report Agent xuyên hệ thống. Đây là hoạt động nhánh **PHH**, cần Git author mapping để quy thành viên; không dùng bảng phân công DD12–DD14 thay commit evidence.

## Team Đông: Supervisor, Room, AgentScope

Tài liệu review 01/10 ghi **0/8 D01–D08 đủ bằng chứng nghiệm thu**, không phải “0% code”. Review đó ở `13b911f`, trước các commit runtime/lock/storage/adapters sau này; không được dùng để kết luận hiện tại vẫn thiếu entrypoint, Dockerfile, version pin hoặc loader.

Hiện checkout có `main.py`, `config.py`, `requirements.lock`, `Dockerfile`, `persistence/sqlite.py`, `agents/releases.py`, `runtime/composition.py`, model provider, contributions/report adapters, remote/OpenBot adapter. README vẫn nói rõ binding production và producer contracts phải do backend/platform cung cấp; unbound workflows fail closed (`agent-coordination/README.md:17–47`).

| Thành viên / owner trong phân công | Phần code hiện có | Kết luận tiến độ |
|---|---|---|
| **Tiến** — Supervisor/planner/duyệt/tổng hợp | `src/supervisor/planner.py`, `service.py`, `turn_policy.py`, `approval_flow.py`, reception/room/backend bridges | Lõi orchestration có và test qua; model/tool/backend thật chưa bind vào Vinhomes composition. Chưa nghiệm thu D03/D05 trọn luồng |
| **Tiến Anh** — Room/Task Board/Mailbox/context/@agent | `src/groupchat/room.py`, `task_board.py`, `mailbox.py`, `context_builder.py`; AgentScope local/remote adapters và published models/schema | Room engine đã có nhiều hơn review 01/10; chưa chạy room specialist Vinhomes thật. Việc này đang bị unbound resolver/invocation chặn |
| **Nghĩa** — Reception/backend gateway, approvals/assignment/tools | `src/adapters/backend/*`, `adapters/reception/*`, `runtime/backend.py`, `runtime/contracts.py`, tools client | Có consumer/mapping/HTTP validation; không thay bằng chứng producer endpoints được mount/bind và service authority đúng cho mọi operation |
| **Huy** — durable state/recovery/lease/fencing | `src/persistence/sqlite.py`, budget, action journal/inbox/worker recovery tests | Development store có thật, không còn “chỉ RAM”; production/shared-store adapter và hai process thật vẫn chưa có bằng chứng. SQLite từ chối production |
| **Khánh Duy** — entrypoint/config/provider/deploy/contracts/E2E | `src/main.py`, config, runtime composition/service/model/ingress, lock/Dockerfile/tests/evaluation | Service assembly/module kiểm thử tốt hơn bản 01/10; readiness phụ thuộc production bindings, offline evaluation không chứng minh live business model quality |

Đây là **mapping ownership theo kế hoạch**, không phải quy kết mọi file do đúng thành viên đó viết; author/commit cần xem báo cáo Git. Phân công gốc: `docs/teams/dong/PHAN_CONG_NOI_BO_COORDINATION.md:50,80,112,144,174`.

### Kết quả chạy lại Coordination

```powershell
$env:PYTHONUTF8='1'
& .\agent-coordination\.venv\Scripts\python.exe -m pytest -q agent-coordination
```

Kết quả **418 passed** trong 23.73 giây. Riêng `tests/vinhomes`: **11 passed** trong 1.16 giây. Các tests Vinhomes inject `FakeBackend` (`tests/vinhomes/test_runtime.py:26`) và `httpx.MockTransport` (`:236`); restart là mở lại development-store file. Đây là kiểm chứng safety/state behavior, không phải bằng chứng PostgreSQL/backend live/model live/specialist business chạy thật.

### Điểm chặn quan trọng của integration hiện tại

`agent-coordination/src/vinhomes/runtime.py:116` inject **`Planner(NoSpecialists())`**. `NoSpecialists.generate` luôn trả `pause/no_specialist_available` (`src/vinhomes/ports.py:88–97`). `Authority.inspect` không đưa specialist catalogue từ response backend vào AuthorityView (`:58–65`), còn Room resolver/invocation/backend actions/events đều là Unbound ports (`:103–142`).

Trên backend hiện đã có `v3_coordination.py:155–177` đọc **active specialist + published non-revoked release + category phù hợp**, và `v3_agent_reviews.py:251–280` approve tạo `agent_versions`/`agent_releases`. Nhưng runtime chưa sử dụng catalogue đó. **Chỉ xuất bản specialist ở backend chưa đủ để Supervisor tự lập phương án.** Đây là wiring gap cụ thể cần xử lý, mạnh hơn câu giải thích cũ “vì chưa có specialist”.

`docs/teams/chien/SUPERVISOR_SESSION_V2_M0_M1_2026-10-03.md:8–21` xác nhận lát cắt chỉ `ticket_submitted → accepted`, không model decision; `:94–107` liệt kê tests chưa có: hai worker, phương án cũ/lặp, restart chờ duyệt, QC/reopen/rollback, model errors/budget.

Vinhomes composition là phần Team Chiến bổ sung sau baseline Đông. `origin/dev_TeamDong` README không có đoạn composition này; diff với checkout có 10 file/~792 dòng của Vinhomes integration chỉ tồn tại về phía checkout. Không quy tiến độ Team Chiến cho Team Đông hoặc ngược lại.

## Team Chiến: backend, UI, database và tích hợp

Backend nghiệp vụ hiện ở **`services/vinhomes-api` (FastAPI/Python)**; server Hono/TypeScript và Vinhomes gateway là một đường khác. Không kết luận `server/src/platform`/`runtime` trống đồng nghĩa toàn bộ business backend chưa có: nhiều chức năng đã nằm ở FastAPI. Nhưng phần generic platform assembly và common producer contracts vẫn là dependency liên team.

| Nhóm task | Evidence code/tài liệu | Kết luận |
|---|---|---|
| C01/C02/C03 — schema, scope, ownership/auth | V3 database, request context, auth/session/accounts/agent reviews; connected provisioning docs | Code đăng nhập/quyền và setup mẫu có; multi-tenant/mọi khu/production acceptance chưa đủ |
| C04/C05 — intake/ticket/version/triage | `v3_reception_operations.py`, `v3_reception.py`, `v3_mutations.py:137–251`, V3 routing/triage modules | Có business commands và optimistic version/gates; cần tách manual operations với autonomous dispatch/agent effects |
| C06 — binding/session/authority | `v3_coordination.py:107–154` cấp team binding/run; verify/view/authorize/result/status endpoints `:202–315`; Reception delegation | Lát cắt identity/session thật đã triển khai; backend actions/room/draft chưa mở, production checkpoint còn thiếu |
| C07/C08 — files/work/assignment/QC/completion | files/evidence APIs; `v3_operations.py:94–176` work queue/staff; `v3_mutations.py:219–251` close gates; `v3_completion.py:7–21` completed + QC pass | Manual/human flow đã có code. Không đồng nhất available_staff/manual assignment với dispatcher tự vận hành đã đạt fairness/race/SLA |
| C09/C10 — Builder/UI | Room agent config/review/version/release; cư dân/Operations connected login | Publish specialist code có; Factory và released runtime chưa bind. UI reachability cần current browser QA riêng |
| C13 — learned knowledge/self-help/giá | `v3_learning.py:85–187` candidate/review; runtime knowledge/curator/inquiry | Learned Q&A và safety guidance khác procedure-learning lifecycle + actual-cost aggregate + published price references. Chưa chứng minh toàn C13 |
| C14 — Reporting backend | V3 reports/jobs và Report module/consumer contracts | Cần E2E hai BQL/template/snapshot/export/revoke, không chỉ thấy reporting tables/routes |

Tài liệu connected login 03/10 ghi API negative checks và browser **23/23 bước**, ba vai đăng nhập thật (`docs/teams/chien/CHAY_DANG_NHAP_THAT.md:42–49`). Đây là **bằng chứng owner lưu trong repo, chưa chạy lại browser tại đợt này**. Tài liệu cũng nêu mới có 20 căn mẫu S1.01, khu ngoài Sapphire thiếu management unit, forgot-password chưa nối và rate-limit chỉ một process (`:51–59`). Không gọi seed demo là dữ liệu vận hành đầy đủ.

Tài liệu `TIEN_DO_VA_KE_HOACH_2026-10-03.md` đã bị một số thay đổi sau đó vượt qua: đăng nhập thật đã được thêm và retry Reception đã sửa; lịch sử PR/ahead/behind trong file đó phải đối chiếu refs hiện tại, không chép sang làm tình trạng ngày 04/10.

## Team Quang: Technical tools và RAG

Team Quang có hai mảng độc lập: 14 technical tools (catalog/handlers/ports/adapters) và knowledge ingestion/retrieval/evaluation. Team Chiến đã bổ sung host dữ liệu thật cho bộ technical tools; cần tách trạng thái module ban đầu với trạng thái host hiện tại, và tách tool host hoạt động với Supervisor tự gọi tool trong room.

| Người được tài liệu nêu | Phần việc chứng cứ | Trạng thái có thể kết luận |
|---|---|---|
| **Phạm Thành Đạt** | Handoff merge bộ 14 tool, `docs/teams/quang/handoffs/Q02-merge-dev-teamquang.md:3–28` | Tích hợp contract/port/scope model, giữ bộ 14 tool, nhận ý access/session của Thịnh. Handoff ghi 882 tests qua PGlite và PostgreSQL 17; chưa rerun bộ này trong nhánh research này |
| **Thịnh** | Bản 7 tools `17e5826`, PR12, tenant session + building access (`Q02-merge-dev-teamquang.md:12–25`) | Code gốc đã gộp/khử trùng vào bộ 14; không kết luận không làm gì vì file gốc đã xóa, không cộng 7+14 thành 21 tool |
| **Quang / owner RAG** | `server/src/knowledge`, search_knowledge v1 contract, ingestion/retrieval requests và data eval | Code pipeline/retrieval có; ownership author cụ thể cần Git. 115 tài liệu và 93 câu eval là dữ liệu snapshot trong docs, không tự động bằng trạng thái DB hôm nay |

`docs/teams/quang/requests/technical-tools-progress-report.md:8–21` ghi rõ module/POC chưa E2E/production ở thời điểm report. Outage/schedule có Drizzle adapter; framework vẫn giữ nhiều nguồn POC để kiểm thử. **Tình trạng host hiện tại đã tiến xa hơn báo cáo đó:** `server/src/technical-api/runtime.ts:27–48` chạy restricted-role tenant transaction; `:121–125` ghi audit; `:161–246` inject toàn bộ ports và transactional idempotency receipts. `server/src/technical-api/database.ts:70` cấp PostgreSQL ports; đọc SOP/maintenance/sensor và ghi measurement/executor/approval vào các bảng `vh_technical_*` (`:97–349`). `server/src/app.ts:337` có mount `/api/technical/v1` **khi được cấp `technicalApi` dependencies**. `server/src/index.ts:1333–1341` thực sự inject dependencies đó **chỉ khi cả `TECHNICAL_API_DATABASE_URL` và `TECHNICAL_API_TENANT_ID` được cấu hình**, nếu không thì undefined/routes không mount. Research này chưa kiểm live env/mount của Hono process. Vì vậy **không gọi tất cả 14 tools hiện tại là mock/POC**, nhưng cũng không khẳng định endpoint đang live chỉ từ source. Phần còn thiếu trong baseline audit là đường Supervisor Vinhomes → room specialist → signed/granted technical host và nghiệm thu model/business flow; evidence host/integration sâu xem báo cáo backend riêng.

RAG contract tìm kiếm đã có nguồn/version/chunk, insufficientSources/minSimilarity, context/scope và delegation. Nhưng docs 01/10 `handoffs/2026-10-01-search-knowledge-cho-hoang.md:115–140` nói endpoint tạm/local và audit parent dùng seed `rag-dev-*`, một số parent được tạo khi tắt FK. Đó là **giới hạn dev-data lịch sử**, không phải dữ liệu production đủ invariant. Backend Vinhomes hiện có knowledge permission bridge và runtime Reception gọi RAG; phải dùng evidence hiện tại của DB/ACL/live retrieval để kết luận, không giữ nguyên “endpoint chưa có” sau khi đã có đường tích hợp mới.

Phần còn thiếu theo kế hoạch Q05/Q07/Q08: production memory publication/revocation/retention; procedure eligibility theo reviewed version; price aggregation từ verified actual costs, versioned algorithm và provenance. Learned-answer approval không tự hoàn thành toàn bộ những yêu cầu này.

## Team Phái: Agent Factory và Security tools

Đọc `origin/devTeamPhai` qua `git show`, không checkout. **Agent Factory chạy như service độc lập**, `POST /v1/constructions`, default port 4010; kết quả là verified artifact/specHash/systemPrompt, không phải persisted agent, grant hoặc runtime-ready verdict. README trên ref hiện tại nói **production BE wiring đã tháo theo yêu cầu**, `/api/agent-factory/*` chưa mount; backend team sở hữu reconnection. Adapter seams và test còn lại không có nghĩa production đã nối.

Factory có compiler/spec schemas/resource fingerprinting, bounded construction/review/repair, model HTTP adapter, authenticated HTTP route, package lock, Dockerfile; “generated skill” là procedure theo tools của spec, không tự cấp quyền. Security tools có guards/cameras/incidents/evidence/emergency/dispatch/audits và mock provider dưới `server/src/security-tools/providers/`.

`origin/devTeamPhai:agent-factory/docs/verification.md` ghi historical **359 PASS / 0 FAIL** cho focused root/core/BE set, và **10 PASS** thời điểm split standalone, model responses đều fixtures/mocks. Không lấy số 359/44 từ tài liệu làm test current hoặc live-model acceptance. README current có giá trị hơn phần đầu verification cũ nói BE wiring “completed afterward”: README nêu wiring sau đó bị detach. Cần reconcile `backend-integration-spec.md`, coordination Q1–Q6 và shared release/catalog/tool grants trước nghiệm thu B4.

Trên checkout nghiên cứu không có `agent-factory/`/security-tools của nhánh Phái; phần này được đọc trên remote ref và phải được tích hợp vào baseline chung trước nghiệm thu toàn repo. Git report xác định mức lệch baseline, số commits và thành viên author cụ thể.

## Platform/QA/DevOps

Kế hoạch có **Team 5 — Platform/QA/DevOps**, không được tự đổi tên thành Team Phái: scope P01–P07 là reproducible toolchain/CI, DB/MinIO, workers, staging, E2E/security/load, alerts/backup/canary/runbook và learning jobs (`docs/KE_HOACH_HOAN_THIEN_5_TEAM.md:238–248`). Phái hiện đang làm Factory/Security và không có đủ căn cứ nói đã hoàn thành tất cả P tasks.

Có root/server/worker toolchain, docker/CI, test harnesses, local provisioning và Coordination Dockerfile. Thiếu bằng chứng nghiệm thu P01–P07 như fresh-clone bootstrap toàn stack, load/p95/budget/quota, real-worker failure/recovery nhiều replica, restore drill môi trường chung, alert/on-call/rollout/canary. File/compose/health không thay bằng chứng đó.

## Những việc nên ưu tiên tiếp theo

1. Hợp nhất baseline/ref và current contract ownership. Rerun CI/tests đúng các gói trong baseline; sửa failure graph PH16 và báo skipped coverage rõ ràng.
2. Nối `specialists` backend → AuthorityView → published resolver → Room invocation; thay `NoSpecialists` bằng model provider thật có budget. Chạy một ticket kỹ thuật từ cư dân đến phương án Operations, BQL duyệt và staff thực hiện.
3. Tái sử dụng host technical PostgreSQL đã có, nối room specialist vào signed run/granted tool calls; chứng minh allowed call thành công và forbidden call bị chặn trong chính luồng Supervisor. Không làm lại host vì report POC cũ, không đưa POC provider vào đường nghiệm thu.
4. Chốt production runtime storage, action-journal/inbox/outbox/reconcile semantics; chạy restart giữa pending mutation, double worker, expired lease, duplicate callback, authority revoke và reopened generation.
5. Nối Factory tới backend save/version/grants/release và Coordination theo contract đã thống nhất. Một published no-tool agent vào room trước, rồi agent có authorized tools.
6. Chạy current browser/UAT với password sessions và dữ liệu test hai BQL/hai cư dân; audit cross-user/file/thread/revocation. Hoàn thiện deployment/env/runbook/monitoring theo tiêu chí P tasks.
7. Nghiệm thu Report và learning/price riêng bằng nguồn/thời kỳ/quyền/versions; không tính learned-answer UI hoặc Report template là kết thúc M3.

## Các giới hạn của research này

Đã đọc code, plans, handoff và remote branch artifacts; đã chạy Reception Python + Coordination full tests. Chưa chạy model có phí, migrate DB, launch process hoặc browser/MinIO/load/backup drills trong phần audit này. Các kết quả owner ghi từ 01–03/10 được giữ có nhãn lịch sử/tự báo cáo. Không suy tác giả thực của mọi file từ bảng phân công; commit inventory riêng mới là căn cứ contributor activity. Commit/WIP đồng thời cuối audit chưa được gộp vào các kết luận pin baseline hoặc test counts; cần đọc phần follow-up snapshot trong báo cáo tổng để biết thay đổi mới hơn.
