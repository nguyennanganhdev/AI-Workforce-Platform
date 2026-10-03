# Báo cáo toàn repo, thành viên, nhánh và tiến độ dự án — 04/10/2026

## Kết luận điều hành

**Dự án đã có nền tảng lớn và một luồng Vinhomes tích hợp trên môi trường phát triển. Chưa đủ bằng chứng nghiệm thu hệ thống AI Workforce tự điều phối và vận hành production.**

Không còn đúng khi mô tả toàn bộ dự án là ERD + mock UI. Resident và Operations mặc định sử dụng API, backend FastAPI có nghiệp vụ thực, Reception có graph và agent loop, RAG có ingestion/retrieval theo quyền, PostgreSQL local có schema và dữ liệu. Nhưng không được cộng những module này thành một hệ thống autonomous đã hoàn tất: specialist/model/tool của Supervisor, Factory, shared runtime storage, deployment và kiểm thử phát hành còn các điểm ghép chưa hoàn chỉnh.

Ba kết luận quan trọng:

1. **Luồng con người xử lý đã tiến xa hơn luồng agent tự xử lý.** Tài liệu ghi một luồng sửa chữa với ba tài khoản thật đạt 23/23 bước ngày 03/10. Đợt nghiên cứu này xác minh code, database catalog và tests; không chạy lại browser/model thật nên giữ 23/23 dưới nhãn bằng chứng lịch sử của người triển khai.
2. **`develop` là nền tích hợp thực tế; `main` còn rất cũ.** `origin/develop=d9b4e75`, `origin/main=a655710`; main thiếu 172 commit của develop. Team Phái chưa nằm trong develop. Các branch cá nhân cũ không đại diện toàn bộ tiến độ hiện tại của một người.
3. **Chưa có cổng phát hành đáng tin cậy.** CI tổng thể bị comment toàn bộ, run mới nhất của develop thất bại vì workflow file issue, release workflow vẫn tham chiếu CI sai. Tests chọn lọc đạt không thay được kiểm tra toàn repo và nghiệm thu staging.

## Phạm vi và mốc bằng chứng

- Repo: `E:\AI-Workforce-Platform`, remote `nguyennanganhdev/AI-Workforce-Platform`.
- Mốc chốt báo cáo: **03:00 ngày 04/10/2026, giờ Việt Nam (UTC+7)**. Kiểm kê **2.122 file tracked**, **35 nhánh remote**, **30 PR**, **188 commit không phải merge / 29 tên tác giả Git** trong cửa sổ 26/09–04/10. Các alias không tương đương số người thực tế.
- Fetch remote và đọc GitHub API cho PR/Actions; không chỉ dùng bản local develop đang tụt sau remote 161 commit.
- Đọc sâu các entrypoint, schema/migrations, backend, frontend, Reception, Coordination, knowledge/tools, deployment/CI; đối chiếu kế hoạch và handoff từng team. Kiểm kê toàn cây và lịch sử các nhánh được lưu riêng. Không khẳng định đã review thủ công từng dòng trong toàn bộ code kế thừa, lockfiles và generated schema.
- Audit chuyên môn bắt đầu ở `a231575`; HEAD tại mốc chốt là `b2d3f37`. Trong lúc nghiên cứu, tác nhân khác tiếp tục sửa và commit backend specialist admission, rồi thêm WIP runtime/ports/scripts/tests và `docs/teams/quang/agent/`; các thay đổi đó được ghi riêng trong snapshot. Các tests không tự nghiệm thu code xuất hiện sau khi test chạy. Không sửa source hoặc ghi đè công việc song song.
- Hai thư mục `DATABASE_MAP_2026-10-04/` và `RAG_DATABASE_MAP_2026-10-04/` có trước đợt này và chưa commit. Báo cáo này không commit/push/merge, không migrate hoặc thay đổi dữ liệu ứng dụng.

Nguồn Git có full SHA, timestamp và trạng thái ở [snapshot.json](snapshot.json), [snapshot_start.json](snapshot_start.json), [branches.json](branches.json), [pull_requests.json](pull_requests.json), [github_runs.json](github_runs.json). Đây là các lần lấy mẫu liên tiếp, không phải snapshot atomic của Git, source và database.

## Các báo cáo chi tiết

| Tài liệu | Nội dung |
|---|---|
| [INVENTORY.md](INVENTORY.md) | Mọi nhóm folder/file tracked, kích thước và số dòng text |
| [BRANCHES.md](BRANCHES.md) | Toàn bộ 35 nhánh, tip, ahead/behind và 4 PR mở |
| [CONTRIBUTORS.md](CONTRIBUTORS.md) | Toàn bộ 29 tên tác giả và từng commit trong cửa sổ nghiên cứu |
| [TEAM_PLAN_PROGRESS.md](TEAM_PLAN_PROGRESS.md) | Mapping owner/backlog/milestones → code/tests, chi tiết Hoàng/Đông/Chiến/Quang/Phái |
| [BACKEND_DATABASE.md](BACKEND_DATABASE.md) | API, auth, schema, migrations, DB live read-only, RAG và giới hạn kiểm chứng |
| [FRONTEND_RUNTIME.md](FRONTEND_RUNTIME.md) | Resident/Operations/Desktop, mock vs connected, container/runtime, deployment và test |
| [DATABASE_MAP](../DATABASE_MAP_2026-10-04/README.md) | Danh mục 193 bảng và 682 FK; full ERD đang mở trong IDE |
| [RAG_DATABASE_MAP](../RAG_DATABASE_MAP_2026-10-04/README.md) | Phân hệ RAG, quyền, citations, learned knowledge và snapshot dữ liệu |

## Repo thực sự chứa những gì

| Khu vực | Trách nhiệm thực tế | Mức bằng chứng |
|---|---|---|
| `server/` — 583 file | Hono/OpenBot: auth, channel, agents, plugins/tools, policy/audit, computer gateway, routines/work; Drizzle DB; knowledge/RAG; technical host | Có implementation lớn; nhiều code kế thừa OpenBot, không tính là từng tính năng Vinhomes do nhóm tự hoàn tất |
| `services/` — 194 file | FastAPI Vinhomes: identity/session, resident intake/chat, tickets, triage, plans, work, QC, photos/files, Operations, reporting, Reception/Supervisor producer API | Đường backend nghiệp vụ chính của connected UI; khác Hono server |
| `app/` — 493 file | OpenBot web + Operations; connected BQL/staff UI và các preview workflows | Có API integration; còn màn chuyên biệt chưa nối đầy đủ |
| `resident-app/` — 41 file | App cư dân riêng: auth, assistant, requests, attachments, consent/confirmation, account | Default connected; preview riêng; tiện ích và reset password chưa hoàn chỉnh |
| `agent-reception/` — 89 file | Lễ tân Python: graph, agent loop, model adapter, tools, backend runtime, checkpoint/evals | Có runtime tích hợp; một đường typed PH16 còn lỗi consumer |
| `agent-coordination/` — 143 file | Supervisor nghiệp vụ, planner, approvals, rooms, tasks/mailbox, published agent adapter, authority, durable workflow | Core + development persistence có; composition Vinhomes chưa được nghiệm thu full model/tool flow |
| `supervisor/` — 19 file | Quản lý Docker computer theo Bot: ensure/stop/reset, ownership, profile/workspace | Đây là container supervisor, khác Supervisor lập phương án ticket |
| `agent-computer/` — 45 file | Browser/screen/files/shell computer, authentication, human take-wheel, egress | Có runtime thực; chưa chạy lifecycle/load/live screen trong đợt audit |
| `worker/` — 9 file | Routines/work queue dispatch, culling | Không tự chứng minh mọi business worker/knowledge ingestion đã được deploy chung |
| `desktop/` — 114 file | Tauri/Rust/OpenBot launcher, provider/OAuth, installer và release integration | Nền native kế thừa; chưa build/accept installer trong đợt này |
| `agent-report/`, `server/src/reporting/` | Template/config/prompt/narrative/layout; nhánh PHH thêm Python report tools | Report tool branch chưa merged develop; chưa có Report Agent E2E hoàn chỉnh |
| Các `agent-*` framework khác | ADK, AG2, Agno, Claude SDK, CrewAI, LangGraph, Langroid, LlamaIndex, Mastra, Microsoft, PydanticAI, Strands | Harness/sample lựa chọn framework; không phải số agent nghiệp vụ đã nghiệm thu |
| `examples/`, `shared/`, `charts/`, `docker/`, `spire/` | Samples, contracts, Helm/container/network/workload identity | Có cấu hình, chưa có acceptance từng provider/cloud/cluster |
| `docs/`, `my-docs/`, `tasks/`, `docx/` | Thiết kế, ownership, kế hoạch, API/handoff, UI spec, backlog | Phải đối chiếu code: DONE/READY trong docs không tự thành sản phẩm chạy thật |
| `agent-factory/`, `server/src/security-tools/` trên nhánh Phái | Construction/spec/generated skill và Security MCP | Có trên branch riêng, chưa vào cây develop/current checkout |

Safe OpenAPI generation ở FastAPI cho 206 paths/232 operations. Đây là độ rộng contract, không phải 232 luồng đã nghiệm thu. Có duplicate GET room-agents/operation ID cần reconcile. Backend còn chứa legacy SQLAlchemy/Alembic trong một số folder; entrypoint V3 dùng `v3_*`, không chạy migration legacy vào database V3 chỉ vì chúng tồn tại.

Root Bun workspace chỉ bao phủ `app`, `server`, `worker`, `resident-app`. Root typecheck/build không tự bao phủ Python runtimes, desktop, computer, supervisor và Factory. README vẫn là README OpenBot upstream và tự mô tả template/alpha; CODEOWNERS cũng còn các tài khoản upstream. Cần tài liệu/ownership phù hợp dự án trước phát hành; audit không suy đoán branch protection đang cấu hình trên GitHub từ nội dung CODEOWNERS.

## Database: 148, 154 hay 193 bảng?

**Cả ba con số đúng cho ba lớp khác nhau.**

| Lớp | Số lượng | Ý nghĩa |
|---|---:|---|
| `server/src/db/design/merged.json` | 148 | Baseline model thiết kế V2/V3 |
| Drizzle registry | 154 | Bảng ORM hiện khai báo; chưa bao phủ hết custom SQL extensions |
| Migration SQL `0000–0012` và live PostgreSQL public | 193 | Bảng ứng dụng hiện triển khai |
| Live foreign keys | 682 | Quan hệ thực trong PostgreSQL |
| RLS / FORCE RLS | 175 / 175 | Catalog trạng thái bật, không tự chứng minh mọi policy đều đúng |
| Các SQLite runtime trong database map | 9 | Storage nội bộ Reception/Coordination; không cộng thành số bảng PostgreSQL |

Đợt này đã kiểm lại catalog **read-only** ở cả `vinhomes_v3` và `vinhomes_connected`: cùng 193 bảng, 682 FK, 175 RLS/FORCE RLS. Không chỉ sao chép con số từ sơ đồ chưa commit.

Có **39 bảng live/migration chưa có `pgTable` trong registry**. Nhiều bảng `vh_*` là extensions được FastAPI truy vấn SQL trực tiếp; không được gọi chúng là không dùng/legacy chỉ vì tiền tố. Các lớp design/ORM/migration cần reconcile. Test migration journal còn lỗi snapshot; connected DB có một journal row dư không khớp migration SQL hiện tại, xem báo cáo backend để xử lý ở task riêng. Không sửa journal trong đợt research.

Trục nghiệp vụ hiện tại là `tickets`, không lấy mô hình `vh_incident` lịch sử làm canonical. Flow tổng quát: resident → ticket/triage → team/session → plan/approvals → work orders/assignments → evidence/QC → resident confirmation → BQL closure. `work_items` OpenBot là work queue có lease, không đồng nghĩa công việc hiện trường.

Schema cũng có authority/runtime identity, knowledge/memory, files/storage, costs/payment, security/technical/reporting và automation/audit. **Có bảng cho một năng lực không đủ để xác nhận UI/API/runtime/production của năng lực đó đã hoàn tất.**

## Tiến độ từng team

| Team | Đã triển khai/đã chia sẻ | Chưa đủ để nghiệm thu |
|---|---|---|
| **Chiến** | DB và FastAPI V3; connected Resident/Operations; password login; Reception chat/repair/emergency/inquiry; learned knowledge; API/session cho Supervisor; PR25 đã merged develop | Full autonomous dispatch, common runtime/tool assembly, Factory reconnection, deployment chung, CI/migration gaps, seed đủ mọi khu |
| **Hoàng** | Reception graph/tools/checkpoint/runtime baseline; template/narrative Report; PR21 merged develop | PH16 graph consumer còn 1 lỗi; shared checkpoint/concurrency thật; Report agent trọn vòng; self-help/price flow đủ tiêu chí |
| **Quang** | RAG ingestion/retrieval/citations; 14 technical tools; PR18 merged develop | Tool host đã có code PostgreSQL nhưng cần đúng entrypoint/authority/runtime binding; Q05/Q07/Q08 learning/procedure/price acceptance; dataset/eval đủ |
| **Đông** | Core Supervisor/Room/AgentScope, durable SQLite workflow, ports/schema/entrypoint/lock/Dockerfile; PR23/27/30 merged develop | Specialist/model/tool flow thật, shared production store/two-process recovery, 4 PR nội bộ chưa quyết, E2E trọn vòng |
| **Phái** | Factory độc lập + Security MCP trên nhánh riêng; PR29 đã về devTeamPhai | Chưa về develop, branch lệch nền lớn; Factory backend detached; real Security WRITE chưa bật |
| **Platform/QA/DevOps theo kế hoạch** | Nhiều nền OpenBot/Compose/Helm/scripts/tests | Không có bằng chứng toàn bộ P01–P07 hoàn tất: CI, fresh-clone full stack, staging, MinIO/files, load, restore, alerts/runbooks |

Lưu ý tên nhóm: kế hoạch “5 team” gốc dùng Team 5 = Platform/QA/DevOps; không tự coi Team Phái hiện tại đã sở hữu/hoàn thành tất cả các nhiệm vụ đó.

## Tiến độ thành viên và giới hạn quy trách nhiệm

Phân công xác định người chịu trách nhiệm; Git xác định commit đã đưa vào lịch sử. Không dùng số commit để xếp hạng năng suất. Một commit merge hoặc snapshot có thể chứa code của nhiều người. Bảng dưới tách hai loại bằng chứng.

| Thành viên / tên Git | Bằng chứng và phần việc | Đánh giá tiến độ |
|---|---|---|
| **Chiến — ChienhocIT** | DB/platform integration, FE/API auth, RAG/Reception/learning/session, coordination API; `ca48f46`, `2324e74`, `db32a6a`, `034e41b`, `a231575`, `b2d3f37` | Đã đưa tích hợp lớn vào develop qua PR25; thêm ủy quyền/room specialist phía backend sau develop; chưa đồng nghĩa autonomous Supervisor hoàn tất |
| **Huy backend — huylc12343** | `6266af0`, `6db13c4`, `6b8e166`: V3 agent/Reception persistence và Technical A2 PostgreSQL endpoints | Code branch đã nằm trong develop; branch cá nhân cũ không phải tiến độ tích hợp mới nhất |
| **Huy-Nguyen-Chualambo** | Auth/resident conversations/Operations work management; `d9cad41`, `2b9230d` | Có code frontend/workflows được tích hợp; không tự gộp với huylc12343 hoặc Nguyễn Xuân Huy |
| **Nguyễn Xuân Huy (VSF)** | `889b541`: app cư dân độc lập và bootstrap/tests | Đã có nền resident app; cải tiến connected sau đó cần tách author |
| **Việt Anh — Viet Anh Vu** | Role-based Operations, responsive/staff UI, A5/history/QC/inbox/coordination preview; `1b480ad`, `e775113`, `c400a45` | Các nhánh FE đã nằm trong develop theo lịch sử; nhiều commit mang tên này cả trên nhánh tên Ngô Đình Khánh |
| **Ngô Đình Khánh** | Có branch `frontendNgoDinhKhanh` và publish branch liên quan | Tên branch không đủ xác nhận tác giả; các commit chính quan sát được ghi Viet Anh Vu. Không kết luận Khánh chưa làm hoặc gán tất cả code cho Khánh |
| **tonytony3003** | `179903d`: Operations multi-agent session/quotation workflow | Có đóng góp UI/demo; không phải bằng chứng agent runtime thật |
| **Nguyễn Hoàng — NguyenHoang151216** | `df8b4aa`: thay snapshot DB V3; các commit schema/plan/learning/team allocation sau đó | Nền thiết kế/schema và kế hoạch lớn; tách khỏi Phan Hoàng và không quy mọi dòng snapshot là tự viết |
| **Phan Dũng — DungPhanHoangg05** | Graph/prompt/eval/report templates/narrative, `bb5a819`, `0e48cd9`; owner PD tasks | Baseline đã có; typed graph/V2, Report nội dung mới và eval còn backlog |
| **Phan Hoàng — hoangphan101004-coder / PHH** | PH16 typed facade/validators/checkpoint/runtime; `df5eccd`; nhánh PHH `796f909` thêm 8 Report tools | Baseline tools có; graph integration chưa DONE. Report wrapper branch có riêng, chưa vào develop; tài liệu ghi 256 test đạt, chưa rerun branch đó trong đợt này |
| **Dương Dũng** | Owner Report tools theo phân công; HTTP Reception baseline đã chuyển ownership sang Phan Hoàng | DD12/DD13 READY, DD14 BLOCKED_API theo docs; chưa xác minh một Git identity riêng đủ để chấm tiến độ cá nhân |
| **Đông — Nguyen Phuong Dong / NguyenPhuongDng** | Integration/PRs Team Đông, recovery contracts `a6d5cc7`, merge PR30 | Đã tích hợp core vào develop; PR backlog và acceptance flow còn mở |
| **Tiến — tiendo-pixel** | Dispatcher/classification/ML `84771cd`; owner DEV1 Supervisor trong phân công | Lõi/ML branch có; 10 commit riêng chưa nằm develop, PR9 còn mở; planner code trong baseline cũng có commits từ người khác |
| **Tiến Anh — photienanh** | Room/tasks/mailbox/AgentScope + planner/runtime/service; `55f5e00`, `40d37fc`, `fb9d665` | Code room/durable core đã merged; không chỉ phòng họp, có đóng góp orchestration lớn; specialist live chưa acceptance |
| **Nghĩa — NghiaBui1605** | Backend/Reception gateway V2 và HMAC proof ingress `9077390` | Gateway baseline merged; HMAC follow-up PR24 còn mở |
| **Huy — Vo Quoc Huy** | Checkpoint/recovery/lease/fencing branch `56ca8f3`, DEV4 | Có development persistence code; 6 commit riêng, PR10 còn mở; không đồng nhất với backend Huy |
| **Khánh Duy — Duy / YuiK08** | DEV5 assembly/provider/contracts/integration, `b1f1684`, `cf9a663` | Branch có 3 commit riêng, PR22 mở; full-stack fixture assembly chưa live-model acceptance |
| **outlook1227** | `1670811`: dispatcher/ML source/model artifacts | Git có một contribution riêng; chưa đủ xác minh danh tính hay production ML quality |
| **Quang — kaiosz02** | `00cbc81`: nghiệp vụ/tool docs; PR18 đưa Team Quang vào develop | Có nguồn nghiệp vụ/handoff và integration evidence; không đánh giá bằng việc chỉ có 1 nonmerge commit |
| **Phạm Thành Đạt — Pham Thanh Dat** | 14 technical tools/framework/tenant session/capability/ports; `155de53`, `eda63a0` | Bộ tool đã merged, nhiều tests pass; live host và Supervisor call phải nghiệm thu riêng |
| **Giáp Hoàng Thịnh** | `17e5826`, PR12: 7 tool đầu + adapter/session/building access | Đã gộp vào framework 14 tool; không cộng thành 21 tool hoặc đánh giá mất đóng góp vì file gốc được thay |
| **Phúc — Phuc Nguyen / phucvan101** | RAG/chunk/vector/query/CLI/export, `d68b9c7`, PR16/19/20 | Pipeline merged; dữ liệu local đang có; quality/scopes/publication/live audit còn tiêu chí riêng |
| **ddhung04** | `20b7b46`: dữ liệu technical issues cho RAG POC | 1 commit riêng chưa nằm develop; chưa suy ra đã đủ corpus vận hành |
| **Phái Hoàng — Phaihoang** | Standalone Agent Factory, generated skill/spec/integration docs; `23748fa`, `c0caa8b` | Có service construction độc lập; chưa merged develop hoặc reconnect business backend |
| **Đức Anh — Anhkhji / AnhDc2004** | Security MCP P1/P2, write guard/faults/mock và integration `4cca44e`, PR29 | Đã merged team branch, chưa develop; không coi mock WRITE là real Core WRITE |
| **Huy Anh — Hank** | P4 dispatch/escalation callbacks/ACK/delegation/evidence/idempotency `acf62d1` | Callback/write behavior có trên nhánh Phái; live command provider còn thiếu |
| **Lê Hoàng — hoang1031** | Incident/Evidence/Timeline P3, mandatory P5 test gates `da67323`, `63c90c2` | Module/test đã trong nhánh Phái; chưa acceptance trên common backend |
| **Hoàng Việt — VietCH57** | Security types/guard/camera, `8e79917` sửa typecheck | Có contribution trên branch Phái; production bindings và integration chưa đủ |
| **nguyennanganhdev** | `597c76e` Initial commit, repository origin | Không có đủ nonmerge evidence trong cửa sổ này để đánh giá toàn bộ vai trò quản lý/đóng góp ngoài Git |

Xem [CONTRIBUTORS.md](CONTRIBUTORS.md) cho toàn bộ commit, không chỉ các ví dụ trong bảng. Không thấy commit mới không có nghĩa người đó không làm: có thể đang WIP, pair-work, merge/squash hoặc chưa push. Những việc ngoài repo không nằm trong phạm vi xác minh.

## Nhánh và trạng thái hợp nhất

| Nhóm | Trạng thái tại mốc fetch |
|---|---|
| `develop` | `d9b4e75`: có Hoàng PR21, Quang PR18, Chiến PR25 và Đông PR23/27/30 |
| `main` | `a655710`, thiếu 172 commit; không đại diện bản Vinhomes mới nhất |
| `dev_TeamChien` | `d463f1a`, ahead 6 / behind 0; vẫn có follow-up chưa về develop |
| `dev_teamChien_HuyDo` | Remote đã nhận `a231575`, ahead 7 / behind 0; workspace `b2d3f37` còn thêm một commit lúc refresh |
| `devTeamPhai` | `e994722`, ahead 27 / behind 161; chưa có PR đưa team branch vào develop |
| `codex/report-agent-PHH` | `796f909`, ahead 1 / behind 7; report tools ở branch riêng, không nhầm với feature đã merged |
| `dev_TeamDong`, `dev_TeamQuang`, `dev_TeamHoang`, các FE/Huy BE | Không còn commit riêng so với develop, nhưng cần cập nhật develop vào nhánh nếu tiếp tục làm để tránh dùng nền cũ |
| Đông ML/checkpoint/DEV3/DEV5 | Vẫn có commit riêng; tương ứng PR9/10/24/22 đang mở |
| `source`, `backup/*` | Snapshot/backup lịch sử; không dùng như baseline triển khai V3 mới nhất |

**4 PR đang mở đều là của Team Đông:** [#9](https://github.com/nguyennanganhdev/AI-Workforce-Platform/pull/9), [#10](https://github.com/nguyennanganhdev/AI-Workforce-Platform/pull/10), [#22](https://github.com/nguyennanganhdev/AI-Workforce-Platform/pull/22), [#24](https://github.com/nguyennanganhdev/AI-Workforce-Platform/pull/24). PR25 và PR28 không còn mở. PR29 chỉ merged vào `devTeamPhai`, chưa phải develop.

Các local backup/worktree trong `.codex-artifacts` là môi trường kiểm tra lịch sử. Bản local `develop=6fa4aa0` cũ không được dùng để kết luận thiếu code trên remote. Bảng **mọi** nhánh và số ahead/behind ở [BRANCHES.md](BRANCHES.md).

## Những điểm kỹ thuật quyết định tiến độ thật

### 1. Connected UI đã có, phạm vi sản phẩm chưa đủ

Resident/Operations có cookie session, API adapters và backend error handling, không tự fallback sang mock khi API lỗi. Preview vẫn giữ localStorage để diễn tập. Operations còn dedicated security/sanitation/contractor/approvals/evidence chưa nối đủ; resident amenities và forgot-password chưa hoạt động. Một chức năng có trong ticket detail không có nghĩa mọi màn chuyên biệt đã hoàn chỉnh.

### 2. Có hai backend, chưa có packaging thống nhất

Business UI gọi `/api/business` được Vite proxy tới FastAPI8000. Production `app/serve.ts` lại chuyển `/api/*` sang Hono3001, chưa thấy gateway tương ứng. Images chính đóng gói `app/dist`, chưa có resident site và full business-agent stack. Có thể deployment ngoài repo bổ sung reverse proxy; đợt này không có evidence đó.

### 3. Supervisor core khác Supervisor chạy tự động xuyên hệ thống

Ở baseline audit `a231575`, composition Vinhomes dùng `Planner(NoSpecialists())`, unbound resolver/invocation/backend actions/events. Nó nhận ticket, lưu phiên và trả accepted, nhưng không tự gọi specialist/model để hoàn tất phương án. Backend publish/catalog specialist có trước; consumer runtime chưa sử dụng.

Commit mới `b2d3f37` bổ sung admission thành viên, binding theo specialist, run mỗi lượt, attestation release và room mirror. Đây là tiến bộ **phía backend**, cần consumer/runtime và acceptance tương ứng. Trong lúc audit runtime backend/ports đang được sửa bởi tác nhân khác; không lấy WIP này làm bằng chứng đã chạy thành công. Tests418 nói về baseline/core, không chứng minh feature đang viết.

### 4. Technical tools đã tiến hơn POC, host bật theo cấu hình

`server/src/technical-api/runtime.ts` và `database.ts` có PostgreSQL adapters, token/grants/scope, audit và replay receipts cho 14 tool. `createApp` mount `/api/technical/v1` **nếu có** `technicalApi` dependency (`app.ts:332–337`); `server/src/index.ts:1333–1341` cấp dependency khi có đủ `TECHNICAL_API_DATABASE_URL` và `TECHNICAL_API_TENANT_ID`. Vì vậy không gọi toàn bộ tool là mock: host có production entrypoint wiring thật, bật theo env. Đợt này chưa xác minh deployment nào đã bật route và chưa chạy live Supervisor→technical host→PostgreSQL E2E. FastAPI Technical A2 APIs là một đường riêng, không tự nối tool host/Supervisor.

### 5. RAG có dữ liệu và pipeline, chưa đủ quality/learning acceptance

Live local: **115 published documents, 279 chunks, 279 embeddings**, model1536 chiều. Retrieval theo authority/tenant/scopes và audit code có. Catalog live cũng có 0 `retrieval_runs` và 0 `memory_publications` tại lần lấy mẫu; không tự kết luận mọi đường hỏi đáp chưa chạy vì service có thể dùng cấu hình DB khác hoặc audit mode khác. Cần chứng minh request→authorized retrieval→citation/audit trên đúng DB phục vụ.

Learned Q&A hiện có candidate/review và script export Markdown/nạp lại. Đó không tự hoàn tất normalized procedure publication, revocation/retention hay price estimate từ verified actual cost. `process_self_help` vẫn HTTP501, policy không cho self-help. Corpus và benchmark93 câu cần reconcile trước chấm quality toàn hệ thống.

### 6. Agent Factory và Security vẫn là integration gap

Factory tạo spec/prompt/generated skill qua HTTP service riêng; không tự persist agent, cấp grant hoặc bảo đảm runtime-ready. Docs nhánh Phái nói BE integration đã detached có chủ đích; cần reconnect theo contract. Security có RealSecurityProvider đọc Core API; phương thức write hiện trả AUTH_ERROR vì chưa bật real WRITE. Các mock callbacks/ACK tests không chứng minh Core/provider thật đã được nối.

### 7. Vận hành và an toàn còn cần kiểm chứng

RLS enabled không thay tests cross-tenant/user trên runtime roles. SQLite store phát triển không thay shared production checkpoints và kiểm thử hai tiến trình. Login rate-limit một process không tự thành shared rate-limit. Container runtime có ownership/sandbox controls nhưng memory cap mặc định chưa được truyền qua Compose, supervisor health có thể HTTP200 khi Docker unreachable. Không có live lifecycle/load/restore/staging acceptance mới trong audit.

## Kiểm chứng đã thực hiện

| Phạm vi | Kết quả | Điều chứng minh / giới hạn |
|---|---|---|
| Git fetch + GitHub PR/Actions API | 35 branches, 30PR; 4 OPEN | Current remote history, không suy từ docs cũ |
| PostgreSQL catalog read-only | Hai DB:193tables/682FK/175RLS | Catalog và sampled row counts; không chạy migration hoặc destructive tests |
| Reception toàn Python suite | 350PASS,1FAIL,9SKIP | Retry4 lỗi đã sửa; graph→PH16 vẫn fail; không phải mọi live conversation |
| Coordination toàn Python suite UTF-8 | 418PASS | Core/development persistence/contracts; Vinhomes fake backend, chưa live specialist E2E |
| Technical tools | 882PASS,0FAIL,1933assertions | Handler/contract/state/adapters; không substitute default production host/live provider |
| Technical host transport/rules selected | 104PASS | API token/host/catalog/idempotency/verification rules; không live deployment acceptance |
| Focused frontend/computer/supervisor | 90PASS,0FAIL | Contract/UI fake fetch/happy-dom và policy helpers; không browser/live Docker |
| App và resident typecheck | PASS | Type safety ở phạm vi kiểm; không deployment acceptance |
| App toàn suite trên Windows | 894PASS,33FAIL / 927tests | 28 serve failures có lỗi đường dẫn Windows; 5 connected UI failures khi chạy chung, xem log/frontend report |
| Database generated schema check | PASS:154tables,1089SQL statements | Generated ORM/SQL consistency, không full live193-schema equivalence |
| Baseline WASM verifier | 18 checks PASS | Baseline/invariants isolated, không đầy đủ mọi incremental migration |
| RAG/Vinhomes/migration focused | 66PASS,1FAIL | Failure migration journal snapshots; xem BACKEND_DATABASE |
| FastAPI selected safe tests | 8PASS | Auth/origin/image/local-storage checks; không production auth E2E |
| Develop latest CI | FAILURE,0 jobs | GitHub báo workflow file issue; không kết luận là unit-test failure |

Không cộng các số test thành một tổng vì các selection có thể overlap. App full-suite ở `b2d3f37` có [log](app-tests-full.log), exit1; số48/993 trong tài liệu cũ không tái hiện đúng. Các failure Windows harness/isolation không tự chứng minh 33 lỗi nghiệp vụ, nhưng suite chưa xanh vẫn phải xử lý. Bộ test ở branch PHH/Phái chưa được chạy lại, kết quả ghi trong tài liệu branch là self-reported/historical.

Run CI của develop: [37126413864](https://github.com/nguyennanganhdev/AI-Workforce-Platform/actions/runs/37126413864); evidence raw ở [develop_ci_run.json](develop_ci_run.json), [develop_ci_jobs.json](develop_ci_jobs.json), [develop_ci_diagnosis.txt](develop_ci_diagnosis.txt). `ci.yml` không có dòng active; `publish-release.yml` dùng `uses: $/.github/workflows/ci.yml`. Không publish hoặc sửa workflow trong đợt này.

## Dự án đang ở mốc nào?

| Mốc kế hoạch gốc | Đánh giá có căn cứ |
|---|---|
| **M0 nền/contract/schema/health** | Có phần lớn nền và modules; chưa đóng sạch CI/contracts/shared storage/ownership |
| **M1 một luồng xuyên hệ thống** | Luồng human-assisted có code và browser evidence lịch sử; AI Supervisor→specialist→tool và MinIO acceptance chưa đủ |
| **M2 triage/SLA/dispatch/restart/isolation** | Có nhiều business gates/core recovery tests; chưa nghiệm thu autonomous dispatch/shared-store/multi-process/load thật |
| **M3 Builder/Report/self-help/giá/UAT** | Nhiều nền/candidate/templates/wrappers; chưa đủ end-to-end create→publish→run→report/source/file, self-help và price grounding |
| **M4 production/domain thứ hai** | Chưa có evidence nghiệm thu |

Không đưa một phần trăm hoàn thành duy nhất: DB, UI, agent runtime và production acceptance có mức tiến độ khác nhau. Câu mô tả thực tế là **“bản phát triển tích hợp, có luồng nghiệp vụ do con người xử lý; đang hoàn thiện AI orchestration và chuẩn hóa vận hành”**.

## Thứ tự nên làm tiếp

1. **Khôi phục CI và baseline release:** workflow hợp lệ, root + Python/runtime gates, sửa typed graphPH16 và migration snapshots; các failure phải có owner và không bị che bởi skip.
2. **Hợp nhất nền:** cập nhật/PR Team Phái, quyết4PR Đông, phân biệt branch đã merged với follow-up còn riêng. Đồng bộ source contract/version, không chỉ merge kế hoạch.
3. **Một specialist chạy thật:** published version→AuthorityView→resolver/binding→model call→room/task/result→Operations; budget/revoke/current ticket version phải giữ qua từng hop. Sau đó bind2tool đọc thật với positive/negative authority tests.
4. **Một flow AI có nghiệm thu:** resident ticket→Supervisor proposal→BQL approve→resident consent→work/evidence/QC→resident confirmation→closure. Giữ trace IDs, DB rows/audit và ảnh; không dùng mock trong đường acceptance.
5. **Đóng gói môi trường chung:** built resident+Operations, same-origin business gateway, FastAPI/Reception/Coordination/RAG, scoped roles/secrets/storage và bootstrap một lệnh.
6. **Shared storage và failure acceptance:** PostgreSQL runtime store, multi-process/kill/retry/stale/revoke/reopen; backup restore, load/cost/latency/alerts và rollout runbook.
7. **Nghiệm thu riêng Report và learning/self-help/price:** đúng kỳ/scope/nguồn/version, measured dataset, real export/render và publication/revoke; không dùng sự tồn tại tables/templates làm dấu DONE.

Các owner/dependency/Definition of Done chi tiết được đối chiếu ở TEAM_PLAN_PROGRESS. Báo cáo là tài liệu research, không sửa backlog hoặc tự đổi trạng thái task của từng owner.
