# Bằng chứng đóng góp Git — 26/09 đến 04/10/2026

Phạm vi: commit không phải merge, reachable từ tất cả ref local/remote sau fetch. Đây là 29 tên tác giả Git, không phải 29 người đã xác minh danh tính. Một người có thể dùng nhiều alias; commit nhập snapshot cũng không chứng minh tác giả tự viết toàn bộ nội dung.

Số commit chỉ dùng tra cứu, không xếp hạng năng suất hoặc phần trăm hoàn thành. Các branch cũ và backup có thể giữ commit không còn trên develop.

| Tác giả Git | Commit | Commit gần nhất | Nội dung gần nhất |
|---|---:|---|---|
| ChienhocIT | 44 | `b2d3f37` | feat(coordination): the backend admits a published specialist to a Supervisor session |
| Pham Thanh Dat | 24 | `155de53` | docs(quang): record the merge of the two tool frameworks and one list of backend ports |
| Viet Anh Vu | 23 | `e775113` | fix(operations): restore own staff-screen edits lost with the merge revert |
| photienanh | 16 | `fb9d665` | refactor: refactor agent coordination codebase: remove unused runner, enhance groupchat models, and improve runtime service |
| NguyenHoang151216 | 10 | `0047bba` | update kế hoạch team 3 |
| Huy-Nguyen-Chualambo | 7 | `2b9230d` | feat(operations): unify work management and document backend integration |
| Anhkhji | 6 | `4cca44e` | Security MCP: nối worker P4 vào mock/faults, làm cũ cursor sau callback, format phần còn lại |
| Hank | 6 | `acf62d1` | Security MCP (P4): callback worker cho dispatch/escalation, ACK ủy quyền theo roster - mock-write: thêm WorkerCommands (interface Core nội bộ, spec §9) gồm   recordDispatchStatu… |
| Phaihoang | 5 | `c0caa8b` | test tạm chuyển sang deepseek |
| hoang1031 | 5 | `63c90c2` | test(security-tools): bỏ cổng chờ P3, test incident/audit chạy bắt buộc |
| huylc12343 | 5 | `6b8e166` | feat(api): add Technical A2 endpoints with PostgreSQL persistence |
| tiendo-pixel | 5 | `84771cd` | fix(ci): exclude docs and design jsons from biome format, fix adk test mock body |
| Vo Quoc Huy | 5 | `56ca8f3` | fix(ci): fix helm chart baseline fallback in check-new-values-keys.ts |
| NghiaBui1605 | 4 | `9077390` | Implement HMAC source proof authentication and reception ingress |
| Nguyen Phuong Dong | 3 | `a6d5cc7` | fix(coordination): separate recovery attempts and restore published contracts |
| Phuc Nguyen | 3 | `d68b9c7` | bỏ sung thêm hàm json tạo file |
| hoangphan101004-coder | 3 | `975565a` | docs(hoang): hand off PH16 follow-ups to PD11 and PH17 |
| DungPhanHoangg05 | 3 | `bb5a819` | Add access_request node and update system prompt for Reception |
| Duy | 1 | `cf9a663` | DEV5 base mock |
| PHH | 1 | `796f909` | feat(reporting): add PHH report tools and detailed test progress |
| VietCH57 | 1 | `8e79917` | fix(security-tools): add Incident and IncidentType definitions to unblock typecheck |
| YuiK08 | 1 | `b1f1684` | Base xong lien ket DEV 123 |
| ddhung04 | 1 | `20b7b46` | docs(quang): add technical issue data for RAG POC |
| Giáp Hoàng Thịnh | 1 | `17e5826` | feat(technical-tools): triển khai khung và adapter POC cho 7 tool đầu |
| kaiosz02 | 1 | `00cbc81` | thêm tài liệu cho dev code tools |
| outlook1227 | 1 | `1670811` | save: luu tam code dispatcher va ml |
| tonytony3003 | 1 | `179903d` | feat(vinhomes-operations): implement multi-agent coordination session and quotation workflow |
| Nguyễn Xuân Huy (VSF) | 1 | `889b541` | feat(resident): add independent mobile-first resident web app |
| nguyennanganhdev | 1 | `597c76e` | Initial commit |

## ChienhocIT

- `b2d3f37` (2026-10-04T02:50:19+07:00): feat(coordination): the backend admits a published specialist to a Supervisor session
- `a231575` (2026-10-04T02:45:22+07:00): feat(agents): admin approval publishes a specialist, offered to the Supervisor by ticket category
- `a24ecd7` (2026-10-03T23:51:12+07:00): docs(coordination): the Vinhomes composition needs the package installed, as the README already says
- `034e41b` (2026-10-03T23:48:35+07:00): feat(coordination): the Supervisor receives the ticket Reception hands over
- `89cbcc0` (2026-10-03T23:30:14+07:00): feat(coordination): the backend API the Supervisor runtime works through
- `db32a6a` (2026-10-03T18:47:58+07:00): feat(auth): a real organisation and first accounts for the password-login deployment
- `36b56a1` (2026-10-03T18:47:57+07:00): fix(reception-tools): a lost reply after a retry is unknown, not "not applied"
- `2c88375` (2026-10-03T12:50:03+07:00): docs: team progress and the plan for the next phase (03/10/2026)
- `d7ff712` (2026-10-03T12:42:20+07:00): feat(reception): an emergency reply carries the safety guidance management approved
- `9ecd143` (2026-10-03T11:14:38+07:00): fix(operations): an emergency request is shown as an emergency
- `3728fba` (2026-10-03T03:54:48+07:00): feat(learning): publish_learned.ps1 can keep running next to the demo
- `725bb3e` (2026-10-03T03:53:00+07:00): feat(knowledge): an operator's own documents go to the one area it runs
- `b2a652d` (2026-10-03T03:51:11+07:00): test(reception): end-to-end tests run against the model-led agent too
- `13164aa` (2026-10-03T03:22:13+07:00): fix(reception): show at most three source titles under an answer
- `5f73ecd` (2026-10-03T03:19:22+07:00): docs+fix: RBAC matrix, migration verification without a fixed table count
- `fdb7b41` (2026-10-03T03:17:45+07:00): feat(ops): per-turn usage on agent runs, stale runs closed, resident message rate limit
- `67bae8f` (2026-10-03T03:10:39+07:00): feat(learning): answers from management become knowledge, judged before they are reused
- `fd0d3a6` (2026-10-03T03:00:14+07:00): feat(reception): the agent remembers the resident's earlier requests
- `b48238c` (2026-10-03T02:58:31+07:00): feat(reception): model-led agent beside the fixed graph (RECEPTION_AGENT=loop)
- `4bea88f` (2026-10-03T02:44:41+07:00): feat(operations): management answers resident questions and reads the ticket conversation
- `63266d1` (2026-10-03T02:40:14+07:00): feat(session): unanswered questions become a management session and the answer comes back
- `8f4c55a` (2026-10-03T02:34:38+07:00): feat(knowledge): resident knowledge published to real scopes and served to Reception
- `6eaab5f` (2026-10-03T02:19:49+07:00): fix(reception): a model's inferred fact no longer loses the request
- `408d5b4` (2026-10-03T02:15:18+07:00): docs: plan and task list for the Reception agent (approved 03/10/2026)
- `33cdf61` (2026-10-03T02:04:08+07:00): test(reception): live conversation eval with a real model
- `b6db9a7` (2026-10-03T01:56:39+07:00): feat(resident): conversations are named by what they are about
- `5fcff7d` (2026-10-03T01:16:22+07:00): fix(reception): the model may raise an emergency the keyword list misses
- `475d44c` (2026-10-03T01:13:42+07:00): feat(reception): natural wording for replies; fix resident notification layout
- `499967a` (2026-10-03T00:48:30+07:00): fix(operations): complete the request flow in the browser
- `482b4b3` (2026-10-03T00:24:58+07:00): feat(resident): show that the assistant is replying; plain-language replies
- `71814bd` (2026-10-03T00:02:43+07:00): fix(reception): make the resident chat work with a real model
- `2324e74` (2026-10-02T23:45:18+07:00): feat: connect Reception agent to resident chat and complete the repair flow
- `e1b1c4d` (2026-10-01T16:24:14+07:00): author accept admintrator
- `c72e8a8` (2026-10-01T16:18:16+07:00): feat(auth): implement password authentication and related settings
- `ca48f46` (2026-10-01T10:58:20+07:00): feat(resident): connect core resident and operations workflow to PostgreSQL V3
- `8510515` (2026-09-30T23:45:51+07:00): feat(vinhomes): show scoped database tickets in BQL operations
- `926eae3` (2026-09-29T16:31:39+07:00): feat(db): consolidate P0 database schema and documentation
- `2eb5dfb` (2026-09-28T14:23:50+07:00): feat(db): implement workforce ERD and coordination persistence
- `6e76518` (2026-09-28T14:23:50+07:00): feat(db): implement workforce ERD and coordination persistence
- `e587e60` (2026-09-27T00:38:50+07:00): index on chore/import-openbot: 27f7077 docs: record validation limits for imported upstream suite
- `27f7077` (2026-09-26T18:29:59+07:00): docs: record validation limits for imported upstream suite
- `79d6a42` (2026-09-26T18:29:17+07:00): feat: integrate OpenBot foundation with Workforce module boundaries
- `bcb8e56` (2026-09-26T18:13:56+07:00): docs: document package ownership and pin OpenBot source
- `a655710` (2026-09-26T17:49:00+07:00): feat: initialize server structure with Hono framework and domain routes

Nhóm đường dẫn thay đổi: `server` (694 lượt file), `app` (448 lượt file), `docs` (253 lượt file), `services` (113 lượt file), `desktop` (113 lượt file), `agent-reception` (67 lượt file), `resident-app` (45 lượt file), `agent-computer` (45 lượt file), `charts` (34 lượt file), `shared` (31 lượt file), `docker` (27 lượt file), `examples` (27 lượt file), `supervisor` (19 lượt file), `scripts` (18 lượt file), `agent-langgraph` (17 lượt file), `tests` (13 lượt file), `agent-coordination` (11 lượt file), `tasks` (11 lượt file), `agent-runtime` (11 lượt file), `agent-langgraph-agui` (11 lượt file), `docx` (10 lượt file), `domain-tools` (9 lượt file), `agent-bot` (8 lượt file), `agent-claude-sdk` (8 lượt file), `agent-langroid` (7 lượt file), `worker` (7 lượt file), `agent-crewai` (6 lượt file), `README.md` (5 lượt file), `.github` (5 lượt file), `agent-adk` (5 lượt file), `agent-ag2` (5 lượt file), `agent-agno` (5 lượt file), `agent-llamaindex` (5 lượt file), `agent-microsoft` (5 lượt file), `agent-pydantic-ai` (5 lượt file), `agent-strands` (5 lượt file), `.gitignore` (4 lượt file), `agent-mastra` (4 lượt file), `.gitattributes` (3 lượt file), `assets` (2 lượt file), `package-lock.json` (2 lượt file), `package.json` (2 lượt file), `spire` (2 lượt file), `tsconfig.json` (2 lượt file), `research` (2 lượt file), `.dockerignore` (1 lượt file), `.env.example` (1 lượt file), `CHANGELOG.md` (1 lượt file), `Dockerfile` (1 lượt file), `LICENSE` (1 lượt file), `OPENBOT_README.md` (1 lượt file), `Tauri-signing-SKILL.md` (1 lượt file), `biome.json` (1 lượt file), `bun.lock` (1 lượt file), `bunfig.toml` (1 lượt file), `docker-compose.yml` (1 lượt file), `prompt.txt` (1 lượt file), `renovate.json` (1 lượt file), `tsconfig.base.json` (1 lượt file), `.editorconfig` (1 lượt file).

## Pham Thanh Dat

- `155de53` (2026-10-01T14:03:25+07:00): docs(quang): record the merge of the two tool frameworks and one list of backend ports
- `eda63a0` (2026-10-01T14:01:09+07:00): feat(technical-tools)!: grant capabilities over access scopes, checked per capability
- `a16de00` (2026-10-01T13:50:14+07:00): refactor(technical-tools): run database adapters in a tenant session the backend supplies
- `e132a40` (2026-10-01T11:49:14+07:00): docs(quang): report on entry and vendor requests and summarise all fourteen tools
- `7d5e246` (2026-10-01T11:49:14+07:00): test(technical-tools): cover entry and vendor requests, 852 tests in all
- `7b678fe` (2026-10-01T11:49:13+07:00): feat(technical-tools): add apartment entry and vendor dispatch requests
- `68f67d1` (2026-10-01T11:17:51+07:00): docs(quang): report on isolation and restriction requests and their integration requests
- `aaddbd7` (2026-10-01T11:17:50+07:00): test(technical-tools): cover isolation and restriction requests, 748 tests in all
- `ae68eac` (2026-10-01T11:17:50+07:00): feat(technical-tools): add utility isolation and area restriction requests
- `270c745` (2026-10-01T10:44:47+07:00): docs(quang): report on verification and history tools and their integration requests
- `78b386c` (2026-10-01T10:44:46+07:00): test(technical-tools): cover verification and history append, 651 tests in all
- `afbf341` (2026-10-01T10:44:45+07:00): feat(technical-tools): add resolution verification and maintenance history append
- `f829583` (2026-10-01T10:13:54+07:00): docs(quang): report on measurement and result tools and their integration requests
- `56bd8e3` (2026-10-01T10:13:52+07:00): test(technical-tools): cover measurement and result tools, 561 tests in all
- `56c86c0` (2026-10-01T10:13:50+07:00): feat(technical-tools): add measurement and executor result write tools
- `b3dafc4` (2026-10-01T00:39:33+07:00): docs(quang): report on sensor and history tools and their integration requests
- `a4f7876` (2026-10-01T00:39:33+07:00): test(technical-tools): cover sensor and history tools, 388 tests in all
- `3215dc7` (2026-10-01T00:39:31+07:00): feat(technical-tools): add sensor and maintenance history lookup tools
- `d8a379c` (2026-10-01T00:14:12+07:00): docs(quang): report on SOP and asset tools and their integration requests
- `40afec5` (2026-10-01T00:14:11+07:00): test(technical-tools): cover SOP and asset tools, 284 tests in all
- `35c6535` (2026-10-01T00:14:10+07:00): feat(technical-tools): add SOP retrieval and asset lookup tools
- `c9b15eb` (2026-09-30T21:58:30+07:00): docs(quang): report on outage and schedule tools and integration requests
- `efdb956` (2026-09-30T21:58:29+07:00): test(technical-tools): cover outage and schedule tools on the real schema
- `47c3637` (2026-09-30T21:58:29+07:00): feat(technical-tools): add outage and utility schedule read tools

Nhóm đường dẫn thay đổi: `server` (250 lượt file), `docs` (20 lượt file).

## Viet Anh Vu

- `e775113` (2026-10-01T01:04:47+07:00): fix(operations): restore own staff-screen edits lost with the merge revert
- `ba862e8` (2026-10-01T01:02:50+07:00): Revert "feat(vinhomes): resident app, resident-staff bridge, landing page and role-based login"
- `09fb9a1` (2026-10-01T00:47:45+07:00): feat(vinhomes): resident app, resident-staff bridge, landing page and role-based login
- `a5ff8e4` (2026-10-01T00:47:45+07:00): feat(operations): technician job history view and kanban board refresh
- `c400a45` (2026-09-30T22:00:24+07:00): feat(operations): neutral shadcn redesign for staff screens, incidents and dashboard
- `a9ffb24` (2026-09-30T19:23:28+07:00): feat(operations): responsive mobile layouts for operations screens
- `623eb78` (2026-09-30T17:40:24+07:00): feat(operations): field staff flows, BQL role merge and incident inbox
- `f93964b` (2026-09-30T08:58:23+07:00): feat(operations): add incident coordination chat
- `741d3d4` (2026-09-30T08:58:23+07:00): feat(operations): add incident coordination chat
- `c420607` (2026-09-29T22:34:10+07:00): feat(vinhomes-operations): simplify role-based operations interfaces
- `1b480ad` (2026-09-29T10:57:51+07:00): feat(operations): integrate A5 workflow and task history
- `1e07aff` (2026-09-29T10:08:37+07:00): feat(operations): refine role-based execution workflows
- `c5aad28` (2026-09-28T21:43:37+07:00): docs: add comprehensive Vinhomes Operations UI and workflow specification
- `29b55aa` (2026-09-28T21:23:31+07:00): fix(vite): bind host 0.0.0.0 on Windows for reliable loopback connectivity
- `dee2a10` (2026-09-28T19:40:10+07:00): feat(architecture): decouple OpenBot and Vinhomes Operations into dedicated platform ports and entrypoints
- `69352af` (2026-09-28T16:55:17+07:00): feat(operations): enforce operational scenario lifecycle, sync task-workorder states, and resolve QC inconclusive transitions
- `0ad5b80` (2026-09-28T15:25:16+07:00): feat(operations): resolve data audit invariants, normalize mock workflows, and enforce domain business guards
- `a284029` (2026-09-28T14:14:36+07:00): refactor(operations): hide redundant WO ID and checklist column from my-tasks table, moving them to detail dialog
- `546ede4` (2026-09-28T13:56:47+07:00): fix(operations): add OperationsProvider context for real-time persona switching across sidebar, header, and my-tasks table
- `9df757d` (2026-09-28T13:29:33+07:00): feat(operations): redesign my-tasks workspace with compact table view and streamlined stats bar
- `3f4e6fc` (2026-09-28T12:38:22+07:00): feat(vinhomes-operations): enforce P0 RBAC route guards, state transitions, evidence integrity, and domain rules
- `9ee415e` (2026-09-28T11:15:39+07:00): feat(operations): implement 7 RBAC roles, my-tasks, security, contractor, and real evidence capture
- `bd22dc2` (2026-09-28T09:59:02+07:00): feat(operations): consolidate Vinhomes Operations feature into features/vinhomes-operations

Nhóm đường dẫn thay đổi: `app` (392 lượt file), `bun.lock` (2 lượt file), `docs` (2 lượt file), `docx` (1 lượt file), `package.json` (1 lượt file), `.gitignore` (1 lượt file).

## photienanh

- `fb9d665` (2026-10-03T02:14:32+07:00): refactor: refactor agent coordination codebase: remove unused runner, enhance groupchat models, and improve runtime service
- `40d37fc` (2026-10-02T21:52:00+07:00): tests(agent-coordination): add comprehensive tests for runtime components and workflows
- `55f5e00` (2026-10-02T21:51:01+07:00): feat(coordination): add durable agent workflow runtime
- `fec1746` (2026-10-02T15:38:32+07:00): docs: add review documentation for team Dong's 01/10/2026
- `fbca7d3` (2026-10-01T03:47:50Z): feat(agent-coordination): add Reception–Supervisor schema V2 flow
- `27903db` (2026-10-01T03:02:31Z): refactor: update type hints using typing instead of | for clarity and consistency
- `32ca17a` (2026-09-30T18:11:46Z): tests(supervisor): add comprehensive tests for Supervisor functionality and integration
- `4b0c291` (2026-09-30T18:11:15Z): feat(supervisor): Implement planner, ports, room bridge, and service for decision-making orchestration
- `223ccc0` (2026-09-30T10:28:40Z): tests(agent-room): Add comprehensive tests for group chat functionality
- `7a31c67` (2026-09-30T10:26:51Z): refactor: add schemas, update comments and docstrings
- `2e79a0b` (2026-09-30T04:40:19Z): docs(schemas): enhance command and result schemas with task and context management features
- `b1a00d2` (2026-09-30T04:39:51Z): feat(groupchat): implement task and context management with mailbox support
- `2ef27c9` (2026-09-30T01:51:58Z): docs: Add JSON schemas for agent room queries, results, and state management
- `e460783` (2026-09-29T16:20:49Z): feat(groupchat): implement AgentScope adapter and related modules for room management
- `2641f7a` (2026-09-30T01:51:58Z): docs: Add JSON schemas for agent room queries, results, and state management
- `917aa8d` (2026-09-29T16:20:49Z): feat(groupchat): implement AgentScope adapter and related modules for room management

Nhóm đường dẫn thay đổi: `agent-coordination` (185 lượt file), `docs` (16 lượt file).

## NguyenHoang151216

- `0047bba` (2026-10-01T13:04:08+07:00): update kế hoạch team 3
- `ddd1f18` (2026-10-01T00:11:29+07:00): update thêm ảnh sự cố
- `8f9b457` (2026-09-30T16:24:44+07:00): Update schema
- `a82a1b5` (2026-09-30T16:12:02+07:00): Update kế hoạch team 3
- `3f17760` (2026-09-30T11:33:42+07:00): Update kế hoạch team 3
- `6fa4aa0` (2026-09-29T21:32:47+07:00): Cập nhật kế hoạch cho team Hoàng
- `80cc269` (2026-09-29T21:13:57+07:00): Update tài liệu triển khai học tăng cường
- `1afd61e` (2026-09-29T20:26:52+07:00): Cập nhật kế hoạch cho toàn team
- `376b6cb` (2026-09-29T20:24:58+07:00): Cập nhật kế hoạch cho toàn team
- `df8b4aa` (2026-09-29T19:13:54+07:00): Replace develop project snapshot with current local database V3 implementation

Nhóm đường dẫn thay đổi: `server` (291 lượt file), `docs` (100 lượt file), `app` (79 lượt file), `agent-reception` (24 lượt file), `shared` (13 lượt file), `.github` (12 lượt file), `agent-runtime` (10 lượt file), `desktop` (9 lượt file), `domain-tools` (9 lượt file), `docker` (7 lượt file), `agent-coordination` (6 lượt file), `scripts` (5 lượt file), `docx` (4 lượt file), `tests` (3 lượt file), `worker` (3 lượt file), `.claude` (2 lượt file), `research` (2 lượt file), `examples` (1 lượt file), `.editorconfig` (1 lượt file), `.env.example` (1 lượt file), `.gitattributes` (1 lượt file), `.gitignore` (1 lượt file), `CHANGELOG.md` (1 lượt file), `OPENBOT_README.md` (1 lượt file), `README.md` (1 lượt file), `bun.lock` (1 lượt file), `package.json` (1 lượt file), `tsconfig.json` (1 lượt file).

## Huy-Nguyen-Chualambo

- `2b9230d` (2026-10-01T09:47:12+07:00): feat(operations): unify work management and document backend integration
- `d9cad41` (2026-10-01T08:20:18+07:00): feat(resident,operations): add resident conversations and role-based operations workflows
- `f1b97b9` (2026-09-29T18:25:43+07:00): add auth page
- `ed78599` (2026-09-29T18:17:44+07:00): add auth page
- `97e5863` (2026-09-29T17:01:30+07:00): fix
- `31c1395` (2026-09-29T16:24:10+07:00): add docs for resident-app
- `31743c9` (2026-09-29T15:47:14+07:00): done

Nhóm đường dẫn thay đổi: `app` (75 lượt file), `resident-app` (49 lượt file), `.gitattributes` (1 lượt file), `.gitignore` (1 lượt file).

## Anhkhji

- `4cca44e` (2026-10-03T03:23:54+07:00): Security MCP: nối worker P4 vào mock/faults, làm cũ cursor sau callback, format phần còn lại
- `ed345a2` (2026-10-02T23:10:28+07:00): Security MCP: format Biome và sửa lint phần P1/P2, mock READ dùng chung luật P4
- `2a8e992` (2026-10-01T17:13:23+07:00): Security MCP: sửa cờ replayed, thêm POST /faults và test WRITE đầu-cuối
- `0df33e4` (2026-10-01T15:58:55+07:00): Security MCP: đăng ký tool P4, nối writeGuard, chuyển fixture, siết HTTP
- `6a58b3a` (2026-10-01T12:53:39+07:00): Security MCP: khung P1 và tool Guard/Camera (P2)
- `701e44f` (2026-10-01T11:14:08+07:00): tạo các thư mục cần thiết trong security-tools

Nhóm đường dẫn thay đổi: `server` (121 lượt file), `bun.lock` (1 lượt file).

## Hank

- `acf62d1` (2026-10-02T23:28:55+07:00): Security MCP (P4): callback worker cho dispatch/escalation, ACK ủy quyền theo roster - mock-write: thêm WorkerCommands (interface Core nội bộ, spec §9) gồm   recordDispatchStatus, luồng gửi tin → NOTIFIED → ACK và expireEscalation.   Mỗi callback ghi event + evidence; trùng event_id thì trả replayed,   không ghi thêm hay tăng version. - delivery_failed của dispatch_guard/escalate_emergency ghi event + evidence   như một callback thật, guard được nhả. - emergency: ACK chấp nhận người được ủy quyền trong roster (§6.2);   ủy quyền cho contact khác, grant ký cho actor khác hoặc roster đã hết   ủy quyền → ACK_NOT_AUTHORIZED. Deadline vẫn thắng: từ ack_deadline_at   trở đi là ACK_TIMEOUT. - dispatch/emergency types: khai báo ToolIO cho provider bằng declaration   merging. - mock-provider: thêm liveScope() để lệnh worker tác động lên dữ liệu sống;   scope nhận thêm delegations. - Test: security-mcp-callbacks.test.ts (19 case) và fixture delegations.json. - Format Biome cho dispatch/ và emergency/.
- `99c8ad0` (2026-10-01T17:03:03+07:00): fix lỗi
- `1fba1a4` (2026-10-01T16:00:16+07:00): sua co replayed va Post / failure
- `81b694b` (2026-10-01T15:27:41+07:00): sua doi bo sung
- `fb58422` (2026-10-01T11:36:25+07:00): hoan thanh phần việc P4 được giao
- `c08321d` (2026-10-01T10:14:20+07:00): Tạo security tools

Nhóm đường dẫn thay đổi: `server` (33 lượt file).

## Phaihoang

- `c0caa8b` (2026-10-03T19:28:51+07:00): test tạm chuyển sang deepseek
- `371851c` (2026-10-02T19:36:17+07:00): docs(agent-factory): propose the Coordination integration spec (v0)
- `649d3f0` (2026-10-02T17:51:46+07:00): docs(agent-factory): correct the BE integration spec and add the orchestrator boundary
- `842fb89` (2026-10-02T17:20:42+07:00): test(agent-factory): use the team's role names after merging devTeamPhai
- `23748fa` (2026-10-02T17:18:05+07:00): feat(agent-factory): standalone Agent Factory with generated skills, BE detached

Nhóm đường dẫn thay đổi: `agent-factory` (43 lượt file), `server` (41 lượt file), `app` (12 lượt file), `shared` (7 lượt file), `docs` (4 lượt file), `tests` (2 lượt file), `.env.example` (1 lượt file), `.github` (1 lượt file), `Dockerfile` (1 lượt file), `examples` (1 lượt file), `package.json` (1 lượt file), `scripts` (1 lượt file), `tsconfig.json` (1 lượt file).

## hoang1031

- `63c90c2` (2026-10-02T20:17:18+07:00): test(security-tools): bỏ cổng chờ P3, test incident/audit chạy bắt buộc
- `dcfdfd5` (2026-10-02T20:09:03+07:00): test(security-tools): test P3 tính kỳ vọng từ fixture, thêm luật bằng chứng giải quyết
- `da67323` (2026-10-02T20:06:43+07:00): feat(security-tools): P3 Incident, Evidence, Timeline
- `cf5b2bd` (2026-10-02T19:45:26+07:00): test(security-tools): test P3 incident/audit viết trước, tự bật khi code P3 vào
- `d8769fd` (2026-10-01T18:01:36+07:00): test(security-tools): test P5 cho gate R2–R6, R8 trên mock có điều khiển

Nhóm đường dẫn thay đổi: `server` (24 lượt file).

## huylc12343

- `6b8e166` (2026-10-02T13:04:38+07:00): feat(api): add Technical A2 endpoints with PostgreSQL persistence
- `6db13c4` (2026-10-02T10:46:37+07:00): fix(api): repair V3 Reception persistence and add database flow tests
- `6266af0` (2026-10-01T14:30:15+07:00): feat(api): add V3 agent APIs and Reception operations
- `1980b30` (2026-10-01T08:42:09+07:00): feat(api): add V3 database demo and business UI launcher
- `c63e90a` (2026-09-30T22:02:42+07:00): WIP: add Vinhomes API implementation and migrations

Nhóm đường dẫn thay đổi: `server` (198 lượt file), `services` (198 lượt file), `my-docs` (16 lượt file), `changes` (12 lượt file), `docs` (5 lượt file), `.gitignore` (2 lượt file), `.env.example` (1 lượt file), `"my-docs` (1 lượt file), `scripts` (1 lượt file).

## tiendo-pixel

- `84771cd` (2026-09-30T23:16:32+07:00): fix(ci): exclude docs and design jsons from biome format, fix adk test mock body
- `bc910a7` (2026-09-30T23:01:17+07:00): fix(ci): handle missing helm baseline values and keep DEV-2 code intact
- `fd15d27` (2026-09-30T22:42:18+07:00): fix(ci): fix biome docs exclude, helm baseline values and resolve groupchat conflict
- `1b67d64` (2026-09-30T21:24:27+07:00): ci: them automated test workflow cho agent-runtime
- `4bd53c9` (2026-09-30T17:57:22+07:00): feat(dispatcher): tich hop groupchat adapter, ml predictor va hoan thien pipeline

Nhóm đường dẫn thay đổi: `agent-runtime` (13 lượt file), `agent-coordination` (3 lượt file), `biome.json` (2 lượt file), `scripts` (2 lượt file), `agent-adk` (1 lượt file), `.gitignore` (1 lượt file).

## Vo Quoc Huy

- `56ca8f3` (2026-09-30T23:11:44+07:00): fix(ci): fix helm chart baseline fallback in check-new-values-keys.ts
- `d79450d` (2026-09-30T23:10:12+07:00): test(persistence): add comprehensive edge-case tests for retry, idempotency, and concurrency
- `ad3a94f` (2026-09-30T22:32:50+07:00): feat(persistence): sync checkpointing with DEV-2 ScopeState and Snapshot models
- `390983b` (2026-09-30T22:05:47+07:00): feat(persistence): implement DEV-4 checkpointing, resumption, retry idempotency, and recovery
- `6759773` (2026-09-30T21:34:06+07:00): feat(checkpointing): implement DEV-4 session checkpointing, resumption, retry idempotency, and failure recovery

Nhóm đường dẫn thay đổi: `agent-coordination` (17 lượt file), `agent-vinhomes` (9 lượt file), `scripts` (1 lượt file).

## NghiaBui1605

- `9077390` (2026-10-02T17:16:49+07:00): Implement HMAC source proof authentication and reception ingress
- `2300826` (2026-10-01T14:04:36+07:00): feat(reception): update Reception V2 gateway and approval client for enhanced message handling and validation
- `9b9673e` (2026-10-01T12:53:07+07:00): Implement Reception Gateway V2 with enhanced validation and backend integration
- `c931e0e` (2026-09-30T11:40:21+07:00): feat: Implement backend operations and reception gateway

Nhóm đường dẫn thay đổi: `agent-coordination` (67 lượt file).

## Nguyen Phuong Dong

- `a6d5cc7` (2026-10-03T20:25:38+07:00): fix(coordination): separate recovery attempts and restore published contracts
- `c1bec9d` (2026-10-01T10:17:57+07:00): docs(team-dong): add reception supervisor schema v2 migration plan
- `1025dcf` (2026-09-30T10:30:12+07:00): docs: clarify coordination team ownership and approval flow

Nhóm đường dẫn thay đổi: `agent-coordination` (15 lượt file), `docs` (5 lượt file).

## Phuc Nguyen

- `d68b9c7` (2026-10-01T15:48:57+07:00): bỏ sung thêm hàm json tạo file
- `0859ac9` (2026-10-01T14:54:58+07:00): doc phuc
- `9d65f9f` (2026-10-01T13:47:55+07:00): rag from data letan

Nhóm đường dẫn thay đổi: `server` (29 lượt file), `docs` (5 lượt file), `.gitignore` (2 lượt file), `worker` (2 lượt file).

## hoangphan101004-coder

- `975565a` (2026-10-01T14:04:49+07:00): docs(hoang): hand off PH16 follow-ups to PD11 and PH17
- `df5eccd` (2026-10-01T13:58:23+07:00): feat(reception): add PH16 typed tools and adversarial tests
- `5ac0382` (2026-09-30T14:57:34+07:00): PH01

Nhóm đường dẫn thay đổi: `agent-reception` (32 lượt file), `docs` (9 lượt file).

## DungPhanHoangg05

- `bb5a819` (2026-09-30T22:28:18+07:00): Add access_request node and update system prompt for Reception
- `0e48cd9` (2026-09-30T18:21:04+07:00): Update PD task
- `a72ea27` (2026-09-30T15:32:38+07:00): Update PD01 task

Nhóm đường dẫn thay đổi: `agent-reception` (40 lượt file), `docs` (32 lượt file), `agent-report` (13 lượt file), `server` (5 lượt file), `.github` (1 lượt file).

## Duy

- `cf9a663` (2026-10-04T01:09:53+07:00): DEV5 base mock

Nhóm đường dẫn thay đổi: `agent-coordination` (8 lượt file).

## PHH

- `796f909` (2026-10-03T13:32:17+07:00): feat(reporting): add PHH report tools and detailed test progress

Nhóm đường dẫn thay đổi: `server` (14 lượt file), `docs` (7 lượt file), `agent-report` (3 lượt file).

## VietCH57

- `8e79917` (2026-10-02T12:57:36+07:00): fix(security-tools): add Incident and IncidentType definitions to unblock typecheck

Nhóm đường dẫn thay đổi: `server` (1 lượt file).

## YuiK08

- `b1f1684` (2026-10-01T17:45:28+07:00): Base xong lien ket DEV 123

Nhóm đường dẫn thay đổi: `agent-coordination` (6 lượt file).

## ddhung04

- `20b7b46` (2026-10-01T17:17:56+07:00): docs(quang): add technical issue data for RAG POC

Nhóm đường dẫn thay đổi: `docs` (23 lượt file).

## Giáp Hoàng Thịnh

- `17e5826` (2026-10-01T09:58:27+07:00): feat(technical-tools): triển khai khung và adapter POC cho 7 tool đầu

Nhóm đường dẫn thay đổi: `server` (19 lượt file), `docs` (2 lượt file).

## kaiosz02

- `00cbc81` (2026-09-30T17:36:33+07:00): thêm tài liệu cho dev code tools

Nhóm đường dẫn thay đổi: `docs` (2 lượt file).

## outlook1227

- `1670811` (2026-09-30T10:20:15+07:00): save: luu tam code dispatcher va ml

Nhóm đường dẫn thay đổi: `agent-runtime` (21 lượt file), `research` (1 lượt file).

## tonytony3003

- `179903d` (2026-09-29T16:39:12+07:00): feat(vinhomes-operations): implement multi-agent coordination session and quotation workflow

Nhóm đường dẫn thay đổi: `app` (15 lượt file).

## Nguyễn Xuân Huy (VSF)

- `889b541` (2026-09-29T15:27:21+07:00): feat(resident): add independent mobile-first resident web app

Nhóm đường dẫn thay đổi: `resident-app` (18 lượt file), `tests` (2 lượt file), `Dockerfile` (1 lượt file), `bun.lock` (1 lượt file), `package.json` (1 lượt file), `scripts` (1 lượt file), `server` (1 lượt file).

## nguyennanganhdev

- `597c76e` (2026-09-26T08:56:24+07:00): Initial commit

Nhóm đường dẫn thay đổi: .
