# Người 2 — handoff các slice từ baseline PR #99

Phạm vi theo hai kế hoạch đã chốt ngày 18/10 và chỉ dẫn mới nhất của chủ dự án.
Không dashboard BQL, exception queue, operator grant/approval bridge hoặc bot Discord chung.
Khách hàng dùng cùng UI/các trang Platform, dữ liệu riêng; Provider/MCP/Skill được cấp chỉ xem/chọn/dùng.
Không chạy test bằng model key thật; không bật production/cutover bằng kết quả fixture.

**Trạng thái mới nhất:** các sửa review R01/R02 bên dưới đã được kiểm tra trên bản ghép hai branch.
S00–S06 là lịch sử kiểm thử trước review, không phải trạng thái hiện tại. S03 chưa nghiệm thu E2E;
contract gate offline hiện **PASS 24 / SKIP 0 / ERROR 0 / FAIL 0**. Không coi các test SKIP là PASS.

## S00 — Rebase

- WIP đã commit trước đó: `e6cb3495`, `88098c39`, `f64a07fc`; không còn file chưa commit trước rebase.
- Backup local: `backup/vin-user2-pre-rebase-20261018`.
- Rebase lên đúng `fe56707a966864ec7915be30421762d30cba4d15`, giữ eval sandbox/lịch/Discord của PR #99.
- Commit sau rebase: `45f02c27` (model resolver), `4b44dd3f` (shared KB), `3365b8c7` (UI consumer cũ).
- Một conflict tại `frontend/tests/client.test.mjs`: giữ bản upstream vì đã có origin mock và regression login.
- Kiểm tra: worktree sạch sau rebase; xem diff 50 file PR #99 và hướng dẫn eval/schedule/channel;
  test chức năng sẽ chạy lại theo từng slice tiếp theo, không tái dùng số test trước rebase làm proof.
- Chờ Người 1: commit C01/C02/C03 hoàn thiện để tích hợp. Hiện producer đang ở WIP `48e922bd`, cũng đã rebase.

## Yêu cầu cho owner Người 1 (không sửa file lane Người 1)

1. C01: capability view/bind/execute/manage cho catalog, agent, lịch và kênh; giữ BQL/admin cũ. Không dùng
   UI role làm authority. Chốt active workspace server; không cần một bộ chọn workspace mới để dùng AI cá nhân.
2. C02: resolver MCP/skill dùng chung callable có permission và owner/version. Public list/detail/schema
   chỉ trả allowlist, không secret. Credential alias phải có trong model picker mà không persist key user.
3. C05/C07: private customer session/Leader/case binding, self context và event/replay/consent receipt.
   `origin=platform` không phát `start_workflow` vào partner route hoặc Leader BQL; cần regression Domain.
4. C09: atomic logical-run claim, lease/fence, once-consumed trước dispatch, run outcome + delivery outbox
   độc lập; verified Discord user identity mặc định owner, bot credential reference và per-user sessions.
   Cấu hình allowlist trống phải deny; không suy owner từ người gửi đầu tiên.
5. N2-04 cần durable batch publish manifest/stable IDs/status/repair cursor + storage/CAS API. Boolean
   `claim_builder_publish` hiện tại không đủ phục hồi crash/partial activation; không dùng dict thay authority.

N2_CONTRACT_HANDOFF và N2_KET_QUA cũ là ảnh chụp trước rebase. Handoff này và các slice tiếp theo cập nhật
phạm vi mới; các đề xuất operator/BQL dashboard trong báo cáo cũ không còn thuộc phạm vi.

## S01 — Giữ UI hiện có, catalog chỉ đọc

- Khôi phục sidebar icon rail và nút quay về chat của baseline; bỏ bộ chọn scope trình bày
  chưa có API đổi workspace. Workspace/revision lấy từ C01; đổi revision xóa cache và remount consumer.
- Khách hàng vẫn vào Provider/MCP/Skill, Lịch và Kênh. Catalog không có quyền manage không có
  create/edit/install/import/review/sync/delete khả dụng; mutation callback của các hook cũng chặn.
  Chọn tài nguyên trong các picker hiện có được giữ. API/resolver Người 1 vẫn là authority.
- Hạn mức và liên kết Vinhomes nằm trong menu tài khoản hiện có. Admin giữ AdminPage cũ;
  không thay điều hướng của BQL, không thêm dashboard hoặc menu theo role.
- File mới `frontend/src/hooks/useCatalogManagement.ts` thuộc lane frontend Người 2.
- Kiểm tra sau rebase: TypeScript/build đạt; ESLint đạt; test consumer C01 8/8;
  browser Chromium với HTTP fixture 12/12 (375px/1280px, đăng ký, callback/revoke,
  fail-closed C01, shared catalog thấy được và không phát mutation). Không kết nối Domain/model.
- Browser dùng build với `VITE_VIN_EXPERIENCE_ENABLED=true`, `VITE_API_BASE_URL=/api`,
  preview `127.0.0.1:4182`; asset không lỗi, request ngoài origin bị abort.
  Ảnh local trong `P/.artifacts/vin-shell-browser/`, đã xem ảnh desktop.
- Chờ Người 1: C01 capability chi tiết và C02 list/resolver đã được sửa trong WIP nhưng chưa có
  commit handoff ổn định; usage chưa có limit/remaining. Catalog browser hiện là fixture đúng DTO,
  chưa chứng minh bind/execute xuyên hai branch hoặc API reject bằng integration.

## S02 — Lịch một lần không lặp khi lỗi (PR #99 extension)

- Lưu disabled + `DISPATCH_OUTCOME_PENDING` trước tạo session/dispatch đối với `once`;
  lỗi cũng giữ disabled và lưu loại lỗi. Trigger cũ đọc lại trạng thái nên không tự chạy lần nữa.
- Khi lưu trạng thái thất bại: không tạo session và không dispatch. Không đổi schema/storage lane Người 1.
- Test mới `tests/workforce/console/test_schedule_once_failure.py` thuộc Người 2 theo scheduler;
  kiểm dispatch lỗi, thành công, lỗi persistence và gọi lại cùng trigger bằng fakeredis.
- `scripts/workforce/check_builder.py --automation` thêm regression schedule/router/Discord PR #99
  vào cùng harness xóa credential và cấm network. Script kiểm thử/đóng gói thuộc Người 2.
- Kết quả: 181 passed, 13 skipped, 0 lỗi; 0 network attempt, 0 paid model call.
  Skip gồm browser cần preview riêng (đã chạy ở S01) và producer package chưa tích hợp vào branch.
- Gate chưa đạt: C09 atomic claim/lease/fence/run-ledger/outbox cho hai process/crash/unknown outcome.
  Upsert hiện tại chỉ hỗ trợ mô hình một scheduler owner của PR #99; chưa có chứng minh exactly-once
  nhiều worker hoặc delivery retry. Không bật automation cho cohort production bằng slice này.

## S03 — Consumer catalog MCP/Skill — CHỜ TÍCH HỢP, chưa xong

- Khai báo owner trước khi sửa: helper consumer mới `A/_service/_catalog_resources.py` và test
  `tests/workforce/console/test_shared_catalog_consumer.py` thuộc Người 2; không định nghĩa authority.
  Helper gọi C02 `VinPlatformService.resolve_catalog`/`catalog_records` của Người 1, chuyển lỗi sang HTTP,
  không fallback sang resource tự sở hữu khi Vin enabled nhưng authority thiếu.
- Call sites dự kiến: Builder/Studio catalog, bind/eval/readiness, workspace from-library và runtime preflight.
  Quyền tool/version/audience phải được resolver Người 1 kiểm tra; không suy từ prompt hoặc tên tool.
- Schema đọc workspace `A/_router/_schema/_workspace.py` thuộc consumer workspace Người 2 trong slice này:
  thêm DTO an toàn không kế thừa cấu hình MCP chứa header/secret; không sửa schema catalog của Người 1.
- Đã nối Builder/Studio catalog, stage binding, readiness, eval read runner, PR #99 sandbox,
  workspace from-library và toolkit. Runtime bỏ snapshot đã mất grant, dùng config hiện tại từ authority;
  grant được kiểm trước fixture/grant sandbox và từng tool call của sandbox.
- Workspace raw MCP config, skill path/upload đòi `catalog.manage`; picker from-library còn dùng được.
  Shared skill không ghi cache vào thư viện của cư dân. DTO workspace chỉ trả tên/tool/status, không URL/header.
  UI giữ panel cũ và hỗ trợ trạng thái kết nối chưa kiểm tra, không báo khỏe giả.
- Test kết hợp producer SQL tạm từ worktree Người 1 (chỉ overlay module `vin_platform`, không copy WIP):
  `check_builder.py --runtime --automation`: **390 passed, 13 skipped**, network attempts **0**, paid model calls **0**.
  13 skip: 12 browser chạy riêng + một legacy integration gate có môi trường riêng. Producer C01/C03/C02
  tests chạy trong kết quả này; không dùng kết quả skip của branch độc lập làm proof integration.
  ESLint/TypeScript đạt; Ruff F821/F811/F401 helper/test mới đạt (unused import MCPClient baseline ở console còn nguyên).
- Chờ Người 1 commit C02 ổn định và kiểm version/audience/tool allowlist nhất quán trong `resolve_catalog`.
  Catalog version/artifact manifest chưa được pin xuyên cả publish → runtime; C08 fixture theo customer
  và C05/C07 flow Domain chưa được producer giao. Chưa release hoặc công bố N2-02/N2-05 hoàn tất.

## S04 — Discord riêng: gate inbound/delivery

- Test mới `tests/workforce/console/test_private_discord_access.py` thuộc Người 2 theo Discord runtime.
  Mở rộng Config của adapter PR #99 để giới hạn Discord ID trước download attachment/emit/quota.
- Legacy khi flag Vin tắt và chưa cấu hình allowlist giữ hành vi cũ. Danh sách đã cấu hình trống luôn deny;
  Vin bật nhưng thiếu danh sách cũng deny. Kênh cá nhân chỉ nhận DM để không đưa dữ liệu riêng vào guild.
- Chờ C09 verified owner identity/secret ref/lease/outbox: chưa tự suy owner từ sender hoặc nhập ID.
  Default owner và mapping theo từng người phải được server cung cấp; slice này chưa hoàn tất N2-07.
- Đã kiểm tra cả approval clicker với allowlist hiện hành; requester/approver đã bị bỏ khỏi danh sách
  không còn được bấm. Delivery thiếu recipient được cấp hoặc metadata DM bị chặn trước Discord IO.
- 14 test mới: deny None/empty/ngoài list, trước attachment/emit, DM/guild, revoke quyền duyệt,
  tương thích legacy khi flag tắt, ID không hợp lệ, chặn delivery ra guild/người ngoài.
- Harness kết hợp C02 producer + runtime/automation: **404 passed, 13 skipped**, 0 network attempts,
  0 paid model calls; Ruff kiểm undefined/unused ở file sửa đạt. Không đăng nhập/gọi Discord thật.

## S05 — Hiển thị bằng chứng eval PR #99

- Helper frontend mới `src/features/workforce/evaluation/presentation.ts` và test
  `frontend/tests/evaluation-presentation.test.mjs` thuộc Người 2. Chỉ phân loại báo cáo hiện có,
  không viết eval engine/sandbox thứ hai hoặc tự cấp quyền production.
- `sandbox` và `consent_assumed` giữ đúng DTO backend: tool chạy sandbox có nhãn riêng,
  consent giả định được hiển thị rõ. Lỗi môi trường/model/judge là chưa kết luận;
  kể cả báo cáo cũ mâu thuẫn `passed=true` cũng không hiện ca đạt/đủ điều kiện phát hành.
- Node test 3/3 gồm render React report thật với fixture sandbox/consent và báo cáo lỗi mâu thuẫn.
  ESLint và Vin-enabled build/TypeScript đạt. Chưa chạy model hoặc business sandbox thật.
- Chờ C08 customer fixture/reset receipts, N1-07 sandbox và C03 integration hoàn thiện để
  nghiệm thu eval theo cư dân; giữ engine PR #99 và endpoint allowlist admin hiện có.

## S06 — Execution scope cho chat/job

- Theo handoff C03 của Người 1 tại `d6700de1`, dùng `vin_platform._context.execution_scope`
  ở `ChatService.run`, điểm chung HTTP/wakeup/lịch/kênh. Không tạo SDK client/model gateway mới.
- Test mới `tests/workforce/console/test_vin_runtime_attribution.py` thuộc Người 2 theo ChatService.
  Context được authority dựng lại từ user hiện hành; purpose lấy origin session server, không lấy body.
- Đã inject scope + usage attribution vào điểm chạy chung; context cha được khôi phục khi kết thúc/lỗi.
  Hai run song song khác user giữ billing subject riêng. Vin enabled thiếu authority không vào runtime.
- Harness có producer overlay: **409 passed, 13 skipped**, 0 network attempts, 0 paid model calls;
  Ruff test mới và diff whitespace đạt. Browser bản build mới nhất chạy riêng **12/12**;
  frontend C01 **8/8**, eval presentation/render **3/3**, client PR #99 **5/5**; ESLint/build đạt.
- Đây là consumer attribution, không thay reserve/settle C03 và không chứng minh job exactly-once.

## Yêu cầu tích hợp tiếp theo và gate còn mở

- S01 `d19388dd`; S02 `984d4e81`; S03 `042ce76b`; S04 `dbc894f4`; S05 `f9d9cb34`.
  S00/rebase `f650b325`; S06 xem commit đi kèm mục này. Tất cả local trên branch Người 2, chưa push/deploy.
- Producer mới nhất đã thấy: `d6700de1` C03. Các sửa C02/C05/C07/C09 vẫn có WIP trong worktree Người 1;
  test overlay chỉ lấy package `vin_platform`, **không** tích hợp storage/foundation/bootstrap WIP của Người 1.
- **C02/N2-02**: chốt schema/version/artifact/tool allowlist, MCP/skill shared public projection và resolver;
  kiểm tra alias model picker và KB upload/index/citation qua outbound guard sau khi tích hợp đầy đủ hai lane.
- **C05/C06/C07/N2-03**: giao fixture/schema event có version, sequence/cursor/receipt, customer Leader session
  binding và proof Domain `origin=platform` không start route/Leader BQL. Phần UI case/consent/timeline chưa hoàn tất.
- **C09/N2-04/06/07**: `_jobs.py` mới của Người 1 đang phụ thuộc foundation/storage/migration WIP
  (personal job owner). Cần commit DTO/method lifecycle, schema migration và bootstrap hook trước khi
  consumer worker được mount. Chưa có batch stage/activate/repair cursor, logical-run worker, lease/heartbeat,
  outbox delivery retry, verified Discord owner mặc định và secret-reference binding chạy end-to-end.
- **N2-08**: catalog read-only UI đã có; quota admin theo nhóm/người, thư viện KB Vin và usage limit/remaining
  còn chờ API/fixture producer hoàn thiện và chưa nghiệm thu.
- **C08/N2-05**: nhãn UI/revalidation có; customer sandbox fixture/grant/reset/cleanup receipts còn chờ.
- **C10/N2-09A/N2-10/N2-09B**: chưa có migration/config manifest đã ký; chưa RC rehearsal/restore,
  load/security UAT/pilot/cutover. Giữ feature flag mặc định off, không rollout bằng kết quả offline.
- U01–U30 **chưa được đánh dấu đạt tổng thể**. Các số test trên là offline/scripted hoặc browser fixture.
  Skip SQL concurrent runtime trong harness là gate PostgreSQL, không phải coverage SQL đã đạt.

## R01 — Sửa review Người 2 ngày 18/10 — ĐÃ SỬA, kiểm thử offline

- Worktree sạch trước rebase; backup `backup/vin-user2-before-review-rebase-20261018`.
- Đã fetch/rebase lên `origin/dev_Chien@83e3e6d3`, không conflict; không sửa WIP Người 1.
- Owner bổ sung: `channel/_registry.py`, `_clients.py`, `_dispatcher.py` theo lane channel runtime Người 2;
  cập nhật nơi dựng instance để role chủ bot do server quyết định, không đọc flag toàn cục trong Discord.
- C02/fixture chung và `vin_platform.enabled()` chưa có commit ở lần kiểm tra đầu (N1 HEAD `d6700de1`);
  sẽ tích hợp commit đã chốt, không coi module overlay WIP là bản ghép hai branch đã đạt.
- Đã sửa: Discord private theo role chủ bot do authority resolve hoặc allowlist explicit, không đọc env;
  BQL không list vẫn nhận guild mention kể cả Vin bật. Khách tạo bot bắt buộc owner Discord ID,
  mặc định allowlist/approver là owner; form giải thích danh sách đã lưu rỗng chặn hết. ID nhập chưa là verified identity.
- `_model_config`: Vin tắt giữ compatibility key chung cũ cho BQL, không tạo thêm credential ở lần hai;
  Vin bật bắt buộc resolver, thiếu authority không seed/fallback. Test chỉ dùng sentinel giả và không dựng SDK.
- Eval disabled/revoked MCP dùng `EvalToolError(TOOL_UNAVAILABLE)` và report environment, không RuntimeError/HTTP fail;
  bỏ kiểm tra None/disabled đã chết sau revalidate. Skill from-library kiểm enabled/approved trước decode archive.
- Test độc lập Người 2 sau sửa: `--automation` **PASS 237 / SKIP 16 / FAIL 0 / ERROR 0**,
  network attempt 0, paid model call 0. Các skip gồm browser chạy riêng và contract cần bản ghép;
  kết quả này **không** đóng S03. Node form **PASS 2 / SKIP 0 / FAIL 0**; TypeScript/ESLint đạt.
- Owner test mới `test_vin_review_regressions.py` theo eval/workspace lane Người 2.

## R02 — Tích hợp C01/C02/C03 và fixture chung — CONTRACT GATE PASS

- Đã nhận commit Người 1: C01 `e67a56d9`, C02 `f5126e4b`, C03 `bb485b92`, fixture `dded5f66`.
- Chuyển consumer từ auth DDL rút gọn sang `vin_fixtures.authority` + `seed_policy_catalog`;
  không copy WIP của Người 1. Harness `--contracts-only` coi bất kỳ SKIP nào là gate fail.
- `vin_platform.enabled()` chưa có trong các commit đã nhận; đã gửi yêu cầu bổ sung helper đúng owner,
  không sửa package authority từ lane Người 2.
- Đã nhận thêm helper tại `2e2caa00`; console/catalog consumer dùng `vin_platform.enabled()` thay parser riêng.
  N2 cần package N1 trong bản tích hợp để chạy; không tạo parser/fallback package giả trong production.
- Lượt ghép đầu `9caf36ed`: **PASS 14 / SKIP 0 / ERROR 10 / FAIL 0**, lỗi đăng ký dependency fixture
  ở test consumer (đã sửa); chưa đóng S03 bằng lượt này. Browser đầu **PASS 12 / FAIL 1** do favicon từ
  schema Discord trong fixture bị outbound guard chặn; fixture đổi icon rỗng, giữ chặn outbound.
- Commit sửa Người 2: `ccb6e303` (R01), `c70f91cf` (fixture chung/harness), `30f26f11`
  (helper flag/đăng ký fixture). Đã rebase nhánh lên `origin/dev_Chien@83e3e6d3`; SHA S00–S06 cũ
  là mốc trước rebase, xem lịch sử Git cho SHA mới tương ứng. Worktree Người 1 và WIP không bị sửa.
- Bản ghép kiểm thử **`13e4605a403fd6b7b21efa7a2b938a25f6364596`**, branch
  `integration/vin-n1-n2-review-20261018`, worktree `E:/AI-Workforce-Platform-vin-integration-20261018`.
  Gồm Người 1 đến `2e2caa00` và Người 2 đến `30f26f11`; merge commit đã chốt, không module overlay.

### Kết quả chạy lại trên bản ghép

| Gate | PASS | SKIP | FAIL | ERROR | Ghi chú |
| --- | ---: | ---: | ---: | ---: | --- |
| `check_builder.py --contracts-only` | 24 | 0 | 0 | 0 | N1 fixture thật theo auth migrations + consumer C01/C02/C03, catalog/KB/workspace |
| `check_builder.py --runtime --automation` | 451 | 14 | 0 | 0 | Browser không nằm trong harness cấm socket; một gate SQL concurrent cần PostgreSQL |
| Browser Chromium bản build ghép | 13 | 0 | 0 | 0 | 375/1280px; catalog, link, auth; Discord owner bắt buộc, auto-fill allowlist và hướng dẫn rỗng=chặn hết |
| Frontend C01 / form / eval render / client PR #99 | 18 | 0 | 0 | 0 | Lần lượt 8 + 2 + 3 + 5 |

- 13/14 SKIP ở runtime là 13 browser đã chạy riêng và PASS; SKIP còn lại là
  `personal_chat_test::test_group_runs_real_agents_and_dispatcher_with_deterministic_provider[sql]`
  (SQLite không thay kiểm thử concurrency PostgreSQL). Không cộng trùng hai suite thành coverage tổng.
- Build ghép (`VITE_VIN_EXPERIENCE_ENABLED=true`, `VITE_API_BASE_URL=/api`), TypeScript, ESLint,
  Ruff F821/F811/F401 các module/test sửa: **PASS**. Build còn cảnh báo chunk size, không phải lỗi.
- Logs tại `P/.artifacts/n2-review-contracts.log`, `n2-review-integrated-runtime.log`,
  `n2-review-browser.log`, `n2-review-integrated-build.log` trong worktree ghép. Không commit log/artifact.
- Harness: **external network attempts 0, paid model calls 0**; browser chặn mọi request ngoài origin.
  Không đọc .env hoặc dùng key model thật, không đăng nhập Discord/Domain thật, không push/deploy.
- Đã đáp ứng 8 điểm review trong phạm vi sửa code/contract offline. S03 vẫn **CHỜ E2E** cho
  pin resource/artifact xuyên publish→runtime, KB upload/index/citation thật và gate còn mở ở kế hoạch;
  không đánh dấu task N2-02/N2-05/N2-07 hay U01–U30 hoàn tất chỉ từ các số PASS này.

### Đối chiếu SHA helper sau rebase của Người 1

- Chủ dự án xác nhận SHA mới `95021844c1d2adda20f1ab342c38de13395d94b5` tương ứng SHA cũ `2e2caa00`.
  Đã kiểm tra Git: nội dung `vin_platform/__init__.py` giữa hai SHA giống nhau (diff rỗng).
- Console/catalog consumer đã gọi helper này từ `30f26f11`; không còn chờ helper.
  Kết quả test R02 vẫn gắn với bản ghép `13e4605a` nêu trên, không tự áp sang các commit N1 mới hơn.
- Lần cập nhật này chỉ sửa handoff/đối chiếu source; không chạy lại runtime hoặc dùng model key.

## S07 — N2-03 trên bản ghép 18/10 — ĐANG TRIỂN KHAI

- Local dev_Chien đã merge N1 b27f0c9c và N2 69e869f1: e7b80da6; nhánh Người 2 rebase lên mốc này. Chưa push/deploy.
- Owner bổ sung theo lane console/runtime: `_service/_customer_cases.py`, `_tool/_customer_service.py`, test `test_vin_customer_cases.py`; frontend API/component/test customer cases. Không sửa package authority/storage/Domain của Người 1.
- Dùng C05/C06/C07 qua adapter/contract hiện có, lưu liên kết session-case bằng automation CAS của authority. Tool Leader chỉ đọc/tạo/materialize; quyết định ký intent chỉ do nút UI gọi endpoint C06, không có tool quyết định hoặc ticket-grant.
- Test dùng fixture chung + fake transport; chưa ghi PASS khi chưa chạy.

### S07 — Kết quả slice C05/C07 + xác nhận kết quả

- Leader VIN_USER có tool `CustomerService` (context/create/progress); recheck owner/role/session mỗi lần. C05 tạo case trước IO, consumer gắn session bằng authority automation CAS; retry giữ nguyên case key và ticket command/version. Không gọi ticket-grants hoặc partner/BQL workflow.
- Trang Leader giữ shell/chat hiện có, thêm mục thu gọn yêu cầu dịch vụ. C07 hiển thị sync_status/as_of/next_action, timeline có phân trang, tiến độ staff, kết quả và ảnh qua authenticated proxy. Link bị thu hồi/lỗi/gap không được hiện là dữ liệu hiện hành hoặc mở xác nhận.
- Tool không có operation quyết định. UI mở thẻ review rồi cú bấm xác nhận cuối mới POST C06; server ký exact payload/version. Retry UI giữ key và note; stale revision bị Domain từ chối. Prompt riêng theo server role cho biết phải xác nhận trên thẻ, không route sang BQL.
- Contract harness: **31 PASS / 0 SKIP / 0 FAIL / 0 ERROR** (7 ca consumer mới + 24 baseline). Real shared authority/migrations, actual C05/C06/C07 adapters + in-process fake Domain HTTP; không model IO.
- Runtime + automation harness: **456 PASS / 17 SKIP / 0 FAIL / 0 ERROR**. 16 SKIP browser đã chạy riêng trên build mới: **16 PASS / 0 SKIP / 0 FAIL / 0 ERROR**, gồm 3 ca customer card mới (375/1280px, không ký khi xem/mở/hủy thẻ; sync pending khóa nút). Một SKIP còn lại là concurrency PostgreSQL của personal_chat_test, chưa nghiệm thu gate đó.
- TypeScript, ESLint, Ruff F401/F811/F821, Vin-enabled frontend build: PASS; build chỉ còn cảnh báo chunk size. Log `.artifacts/n2-customer-{contracts,runtime,all-browser,build}.log`, không commit artifact.
- External network attempts trong harness: 0; browser chặn ngoài origin; paid model calls: 0. Không đọc key/.env, không dùng Domain/Discord thật, không push/deploy.
- **N2-03 chưa nghiệm thu toàn task**: cần N1 bổ sung C07 `pending_decisions[].version` (revision work approval, không phải ticket_version), projection phương án (`plan_id`, own revision, title/amount/steps/canDecide) và route đọc phương án nếu cần. Consumer không đoán revision hoặc bật duyệt khi thiếu. Test mong đợi: quote/plan cập nhật giữa review/click bị từ chối; đúng owner + đúng revision có receipt, replay không duyệt lần hai. Các consumer decision này sẽ nối khi owner giao contract; chưa sửa Domain/authority của N1.
- Đính chính phạm vi lint: Ruff F401 cho console còn 1 import MCPClient không dùng đã có ở baseline; không xóa dead code ngoài slice. Ruff F821/F811 toàn file sửa và F401 các module/test mới đạt. Không tính lỗi nền này là PASS.

## S08 — N2-06/07 C09 và danh tính Discord — ĐANG TRIỂN KHAI

- Owner bổ sung theo lane schedule/channel/runtime: `_service/_discord_identity.py`, `_service/_personal_jobs.py`, `_manager/_wakeup_dispatcher.py` (mount consumer personal jobs vào dispatcher hiện có), test `test_vin_personal_automation.py` và `test_vin_discord_identity.py`; frontend identity/run-ledger component/API/test. Không sửa lifecycle/bootstrap hoặc C09 persistence của N1.
- Dùng C09 claim/lease/fence/checkpoint, một run không tự lặp sau crash; delivery outbox lưu body riêng, retry không gọi lại model. Chủ bot phải từ OAuth identify server, không tin ID nhập tay.
- WIP checkpoint trước tích hợp N1 f52420d9: OAuth suite 262 PASS / 16 browser SKIP / 0 FAIL / 0 ERROR. Lượt đầu consumer C09 mới: 263 PASS / 16 SKIP / 0 FAIL / 6 ERROR (fixture thiếu required AgentData/ChatModelConfig; đang sửa); chưa ghi S08 xong. Cần 0023 và jobs.context_for(job) mới của N1 trước worker acceptance.

### S08 — C09 context/migration và consumer đã tích hợp

- WIP `34402a59`, merge N1 `f52420d9` vào nhánh N2 tại `0b68fc95`. Không sửa file N1 ngoài nội dung commit producer đã giao. Worker/Chat dùng `jobs.context_for(job)`; worker gọi check_schema trước claim để từ chối schema chưa nâng cấp 0023.
- Lịch VIN_USER enqueue theo logical slot, once chỉ tắt sau queue durable; worker C09 claim/heartbeat/fence, kiểm lại owner/agent/config và lưu run ledger. Discord dedup channel/message ID trước model, server recheck DM/allowlist/verified owner. BQL đi luồng cũ.
- Run lưu reply theo personal_job_id; outbox body/recipient/identity revision/nonce bất biến, retry chỉ gửi body đã lưu. Checkpoint có endpoint/UI phục hồi cửa sổ mất outbox sau run, không chạy lại model. Mất lease hủy worker; crash run giữ OUTCOME_UNKNOWN. Discord nonce chỉ bảo đảm trong vài phút nên consumer chặn retry sau 120 giây và báo unknown, không hứa exactly-once vô thời hạn.
- Chủ bot lấy qua OAuth code + PKCE/state/issuer, server gọi identify rồi revoke token; không persist access/refresh token. Form chỉ đọc ID đã xác minh, tự điền owner/allowlist; revoke/relink được kiểm lại ở input/delivery. Cần cấu hình DISCORD_OAUTH_CLIENT_ID/CLIENT_SECRET/REDIRECT_URI (URI trang /channel); chưa cấu hình thì không cho tạo bot khách. Không dùng bot chung.
- Owner test/UI bổ sung: `vin_personal_consumer_postgres_test.py`, `test_vin_discord_identity_browser.py`, `hooks/useDiscordIdentity.ts`, `components/PersonalRuns.tsx` theo lane Người 2.
- Strict contract gate trên bản ghép N1 mới: **46 PASS / 0 SKIP / 0 FAIL / 0 ERROR**, gồm shared authority, C09 producer và consumer, OAuth fake transport. External network attempts 0, paid model calls 0.
- PostgreSQL disposable loopback với pgvector, migrations thật đến 0023: **8 PASS / 0 SKIP / 0 FAIL / 0 ERROR** (5 migration/storage + 3 consumer PG). Nâng 0022→0023 giữ 2 job legacy, upgrade head hai lần, check_schema và personal enqueue/claim/complete đạt; consumer hai timer/once, delivery retry, stale fence đạt. DB test tự xóa đúng namespace sau test. Lượt fixture plain postgres ban đầu **4 PASS / 0 SKIP / 1 FAIL** vì thiếu extension vector; đã thay riêng container fixture, không sửa DB ứng dụng.
- Browser build mới: **18 PASS / 0 SKIP / 0 FAIL / 0 ERROR**, gồm shell/catalog/link, customer card, readonly Discord identity/default allowlist và callback đúng/giả mạo. Callback chỉ complete một lần, xóa query/state. Hai lượt trước **15 PASS / 1 FAIL** do effect reset form đè ID; đã sửa và chạy lại. Không đổi test để bỏ kiểm owner.
- TypeScript, ESLint, Ruff F401/F821/F841 các module/test S08 và frontend build: PASS; build còn cảnh báo chunk size. Log `.artifacts/n2-personal-{contracts,runtime,browser,jobs-build}.log`, `.artifacts/n2-0023-migration.log` + XML. Runtime mở rộng đang chạy lại sau 2 ca heartbeat/repair và 2 browser mới, sẽ ghi số cuối trước commit.
- Tham chiếu protocol: https://docs.discord.com/developers/topics/oauth2 và https://docs.discord.com/developers/resources/message (identify/code/state/PKCE; enforce_nonce có cửa sổ ngắn). Chỉ đọc tài liệu; test dùng fake HTTP/fixture, không Discord/Domain/model thật.
- Gate còn mở: chưa thử Discord account/bot thật hoặc deploy/migrate DB ứng dụng; OAuth app cần operator provision. Queue reader C09 list hiện giới hạn 100 job đầu, N2 cần N1 giao pagination/filter mới cho lịch sử dài và repair sau hơn 100 run; consumer không query SQL authority riêng.
- Runtime mở rộng cuối S08: **470 PASS / 19 SKIP / 0 FAIL / 0 ERROR**. 18 browser SKIP đã chạy riêng **18 PASS**, 1 SKIP là gate concurrency PostgreSQL personal_chat baseline (không được coi PASS bởi 3 consumer PG khác). Không cộng trùng coverage giữa suite. Không push/deploy, chưa upgrade DB ứng dụng.

### S08 — Bổ sung execution scope theo handoff C09

- Đối chiếu `N1_C05_C07_C09_CONSUMER_HANDOFF.md`: bọc toàn bộ handler schedule/channel/delivery/publish trong `execution_scope(jobs.context_for(job))`, không chỉ ChatService. Danh tính initiator/billing không lấy từ payload hoặc Discord sender. ContextVar được reset trong finally, heartbeat/fencing giữ nguyên.
- Test fake Chat kiểm context thực tế đúng owner/billing. Chạy lại migration/storage + consumer trên PostgreSQL disposable đến 0023: **8 PASS / 0 SKIP / 0 FAIL / 0 ERROR** (`.artifacts/n2-final-postgres.log`). Ruff F401/F811/F821/F841 hai file worker/test: PASS. Không model IO hoặc upgrade DB ứng dụng.

## S09 — N2-04 batch publish — ĐANG TRIỂN KHAI

- Owner bổ sung `_service/_publish_batch.py`, test `test_vin_publish_batch.py` và frontend polling/repair UI theo lane Builder/publish Người 2. Dùng C09 jobs + checkpoint và storage.activate_agents_batch từ N1; không sửa persistence.
- Manifest định danh agent/workspace ổn định theo proposal, stage riêng, chỉ activate toàn batch sau kiểm HEAD/revision/resource; crash không sinh agent/phiên bản thứ hai. Repair là thao tác có trạng thái, không dùng boolean claim cũ cho Vin customer.

### S09 — Kết quả slice batch publish

- VIN_USER chuyển publish sang job C09, UI poll trạng thái theo đúng proposal và khôi phục sau reload. Chỉ hiển thị published khi worker activate + receipt hoàn tất; BQL giữ luồng cũ.
- Manifest giữ ID agent/session/resource workspace ổn định, cursor/record/spec/resource hash; stage riêng, activate_agents_batch CAS toàn batch. Conversation guard bằng authority automation lease chặn ghi đề xuất trong lúc publish; worker stage bị giới hạn 240s dưới lease 300s. Trước activate kiểm lại HEAD/revision và resource pins; package skill chưa cache thì fail rõ, không download không kiểm soát trong worker.
- Repair job dùng checkpoint cũ, đọc lại agent pointers. Crash sau activate trước receipt nhận diện đúng data/versions, không gọi activate lần hai. UI recovery không gọi prepare/evaluate hoặc model.
- Strict contracts **56 PASS / 0 SKIP / 0 FAIL / 0 ERROR**: thêm 10 ca fault injection SQL/Redis (thành công/idempotency, chết giữa stage, chết sau activate, guard/HEAD, revoke), dùng 5 ca eval trên fake model/judge cho mỗi spec; không real SDK/key.
- Runtime + automation trước khi nhân đôi fixture SQL: **475 PASS / 19 SKIP / 0 FAIL / 0 ERROR**; 18 browser đã PASS ở S08, 1 PostgreSQL concurrency baseline còn SKIP. Browser mới phục hồi batch **1 PASS / 0 SKIP / 0 FAIL / 0 ERROR**. TypeScript/ESLint/Ruff module/test mới/build PASS; chunk-size warning như trước.
- Log `.artifacts/n2-batch-{contracts,runtime,browser,build}.log`. External network attempts trong harness 0; paid model calls 0. Không push/deploy, không thay UI shell và không sửa storage/Domain/authority N1.
- Không đóng S03 chỉ từ batch gate: resource pins trong manifest publish đã có; tài nguyên KB/skill runtime business thực, model chất lượng thật và UAT vẫn chưa nghiệm thu. C09 pagination >100 job đang chờ producer như S08.

## S10 — N2-05 linked-customer sandbox C08 — ĐANG TRIỂN KHAI

- Owner bổ sung `_service/_customer_eval_sandbox.py`, `test_vin_customer_eval.py`, phần environment/cleanup report và component presentation theo lane eval Người 2. Mở rộng EvalSandbox PR #99, không tạo engine eval thứ hai.
- Chọn sandbox profile do server cấu hình, resolve catalog sandbox đúng entitlement, tìm link thuộc cư dân, C08 seed/cleanup theo run; grant chỉ ở backend. Không fallback về production fixture hoặc quyền quản lý.

### S10 — Kết quả slice C08

- CustomerEvalSandbox mở rộng EvalSandbox PR #99; C08 prepare/cleanup qua DomainAdapter với context sandbox của đúng cư dân. Profile server cần source_mcp_id, sandbox_mcp_id, domain_provider_id, mcp_url và grant_path; mcp_url cùng trust origin provider sandbox. Catalog sandbox phải cấp execute; schema/classification tool hai bên khớp. Recheck link/provider/catalog trước từng ca/tool; không fallback production hoặc link người khác.
- C08 tạo fixture theo run; backend giữ ticket grant, không đưa bearer/bootstrap vào model/UI. Cleanup sau run (kể cả seed mất phản hồi/cancel), report lưu receipt synthetic_test/retired/audit_retained. Cleanup pending chặn publish, vẫn giữ đúng kết quả từng ca đã PASS; UI nói rõ dữ liệu mô phỏng, giả định consent và cleanup.
- Strict contracts **59 PASS / 0 SKIP / 0 FAIL / 0 ERROR**. Có ca dương tính C08: 5/5 kịch bản fake model/judge PASS, 5 grants riêng/10 tool calls sandbox trên in-process fake Domain/MCP transport, receipt cleanup 5 ticket. Đây là consumer integration offline dùng schema/adapter thật; chưa phải Domain sandbox business UAT thật. Ca cleanup lỗi giữ 5 PASS nhưng run không publishable; wrong resident/revoked sandbox không seed/gọi production.
- Runtime+automation **483 PASS / 20 SKIP / 0 FAIL / 0 ERROR**. 19 browser SKIP đã có 18 PASS S08 + 1 PASS S09 trên build; 1 concurrency PostgreSQL personal_chat baseline còn SKIP, không đánh dấu S03 xong.
- Frontend eval presentation **4 PASS / 0 SKIP / 0 FAIL**; TypeScript/ESLint/Ruff module mới và build PASS (chunk-size warning). Log `.artifacts/n2-customer-eval-{contracts,runtime,build}.log`.
- External network attempts 0, paid model calls 0 trong harness. Không model key thật, không request tới production, không sửa Domain/authority N1, không push/deploy.
- Gate còn: operator provision sandbox profile/entitlements và linked synthetic resident; chạy nghiệm thu Domain sandbox thật bằng fake provider sau khi môi trường được bàn giao. Chưa đo chất lượng/latency/cost model thật và chưa đóng S03/business UAT.

## S11 — N2-08 quota/catalog/KB Vin UI — ĐANG TRIỂN KHAI

- Owner bổ sung frontend API `vinAdmin.ts`, component admin `VinAdministration.tsx`, test UI/DTO tương ứng; mở rộng trang admin hiện có theo capability quota.manage/catalog.manage. Consumer chỉ gọi API N1 đã giao, không thêm SQL hoặc sửa authority.
- Nối effective_limits/remaining/policy_revision vào trang Tài khoản. Khi backend chưa có read policy/grant/membership, UI không tự coi giá trị mặc định là cấu hình đã lưu; ghi rõ giới hạn API và yêu cầu producer cho quản trị đầy đủ.

### S11 — Kết quả slice UI theo API đã giao

- Mở mục Quota & thư viện Vin trong trang admin hiện có theo capability server. Form quota yêu cầu đủ trường thay thế, hỗ trợ role/user/group/pool, models và enabled; kiểm tra usage/hạn mức hiệu lực của user qua endpoint console mới, dùng authority.admin + cùng tenant và quota.usage, không SQL riêng. Eligibility bật/tắt theo API N1.
- Catalog ghi phiên bản tăng dần, tắt/bật tài nguyên, grant view/bind/execute theo user/group/role, thu hồi grant, thêm/thu hồi membership. Thư viện KB nối Knowledge hiện có, xem số tài liệu ready/error, chuẩn bị entry catalog rồi cấp quyền; không đoán owner từ DTO Knowledge không có owner_id. Khách không có quyền sửa catalog.
- Admin khi bật Vin đi qua CurrentUser/Query/PlatformAccess provider và router hiện có để capability có hiệu lực. Khi tắt Vin giữ entry admin cũ. Thẻ case riêng trên Leader chỉ render cho VIN_USER, không dựa vào workspace.kind chung của public capability projection.
- Trang Tài khoản hiện policy_revision, effective limit/used/reserved/remaining và pending reconciliation; parser từ chối số âm/counter sai nhưng chấp nhận quota giảm thấp hơn usage, remaining = 0. Giữ nguyên shell và các trang Platform đang dùng.
- Strict contract cuối trên bản ghép N1 f52420d9 + N2: **63 PASS / 0 SKIP / 0 FAIL / 0 ERROR**. Runtime + automation: **487 PASS / 25 SKIP / 0 FAIL / 0 ERROR**. Trong 25 SKIP: 24 browser không có URL trong harness đã chạy riêng trên build Vin: **24 PASS / 0 SKIP / 0 FAIL / 0 ERROR**; 1 concurrency PostgreSQL personal_chat baseline chưa chạy ở lane N2 và vẫn là gate mở. PostgreSQL migration/consumer chạy riêng **8 PASS / 0 SKIP**, không thay thế ca concurrency đó. Không cộng các suite thành tổng coverage duy nhất.
- Frontend Node: **20 PASS / 0 SKIP / 0 FAIL** (vin-shell 9, eval presentation 4, channel form 2, client auth 5). TypeScript, ESLint và build Vin-enabled PASS; build còn cảnh báo chunk size >500 kB. Ruff F401/F811/F821/F841 module/test mới PASS; console F811/F821/F841 PASS, F401 MCPClient cũ vẫn để nguyên như S07.
- Browser S11 riêng **5 PASS / 0 SKIP / 0 FAIL / 0 ERROR**, kiểm quota không gửi ô trống thành zero, payload đầy đủ, KB→catalog→grant, thiếu capability không có UI quản trị và account 375/1280px không tràn ngang. Lượt đầu **3 PASS / 2 FAIL** do entry admin thiếu provider capability; đã sửa App và chạy lại, không bỏ assertion.
- Logs: `.artifacts/n2-final-{contracts,runtime,postgres}.log`, `n2-all-vin-browser.log`, `n2-vin-admin-build.log`. Harness **external network attempts 0, paid model calls 0**; browser abort request ngoài localhost. Test dùng fixture chung, fake HTTP/model/judge; không đọc .env/key thật, không gọi Domain/Discord/model thật, không push/deploy hoặc migrate DB ứng dụng.
- **Chưa nghiệm thu toàn N2-08**: N1 cần GET quota policies (subject/revision), admin catalog toàn bộ gồm inactive, grants và memberships có filter/pagination/revision. API hiện có chỉ ghi và đọc catalog đang active được cấp cho chính caller; UI ghi đúng phạm vi đó, không giả lập danh sách quản trị đầy đủ. Yêu cầu producer đã gửi, không sửa authority/router N1. N2-03 còn chờ own revision của approval/phương án C07; C09 còn chờ get/filter/pagination để đọc/repair sau hơn 100 jobs. S03 và business UAT vẫn mở.

## Mốc bàn giao tiếp theo sau S07–S11

- N2 base: local `dev_Chien@e7b80da6` (bản merge b27f0c9c + 69e869f1); N1 `f52420d9` đã merge tại `0b68fc95`. Các slice: S07 `4af918fb`, S08 `7e81db51` + scope fix `de08e8f1`, S09 `3a796341`, S10 `69c50ae5`; S11 nằm ở commit chứa phần handoff này.
- Đã triển khai consumer/UI và kiểm chứng offline như trên; chưa tuyên bố hoàn tất mọi task N2, U01–U30, RC/pilot hoặc nghiệm thu nghiệp vụ. Worker chỉ được bật trên DB ứng dụng sau khi operator nâng **0023_personal_job_constraint**. N2 không chạy migration trên DB ứng dụng trong phiên này.
- Chờ N1 giao ba nhóm read/revision contract nêu trên và môi trường sandbox/OAuth được provision. Sau khi có SHA, ghép nhánh rồi chạy lại gate tương ứng bằng fixture/provider giả; không yêu cầu hoặc dùng key model thật.
- Lệnh gate đã chạy từ `platform_VP/agentscope`: `.venv/Scripts/python.exe scripts/workforce/check_builder.py --contracts-only`; cùng harness `--runtime --automation`; `.venv/Scripts/python.exe .artifacts/n2_migration_check.py` (guard chỉ cho DB fixture loopback 55441). Browser chạy pytest 5 module `test_vin_{customer,shell,discord_identity,batch,admin}_browser.py` với `VIN_UI_TEST_URL=http://127.0.0.1:4174`, PYTHONPATH src/tests/console. Frontend chạy `pnpm exec tsc -b`, `pnpm lint`, `pnpm build` với Vin enabled và API `/api`, Node test 4 file đã nêu. Script migration tạm nằm trong artifact ignored; test fixture PG có source tại `tests/vin_personal_consumer_postgres_test.py`, test migration dùng `tests/vin_migration_storage_test.py` của N1.
- Đã xem ảnh quota/KB admin 1280px từ build bằng Playwright fixture, không chỉ kiểm source. Ảnh `.artifacts/vin-admin-browser/{quota,knowledge}-1280.png` không commit. Lượt chụp ad-hoc đầu lỗi selector vì PowerShell pipe mã hóa dấu thành `?`; chạy lại với UTF8 thành công. Kết quả suite browser 24 PASS ở trên không thay đổi bởi lỗi công cụ chụp này.
- Sau commit S11 `137984b5`, đã fetch `origin/dev_Chien` và rebase với `--rebase-merges` để giữ nguyên các merge producer. Remote hiện vẫn ở `83e3e6d3`, chưa có bản merge local `e7b80da6`; nội dung cây và SHA S11 không đổi, `f52420d9` vẫn là ancestor. Bản rebase mặc định ban đầu làm phẳng merge dù tree không đổi; đã lưu backup rồi khôi phục bằng `reset --keep` trên worktree sạch và thực hiện lại với merge preservation. Không force-push hoặc đổi nhánh Người 1/main.

## S12 — Theo yêu cầu tiếp tục trên N1 902bf056 — ĐANG TRIỂN KHAI

- Rebase merge-preserving lên `902bf056` hoàn tất, HEAD ngay sau rebase `98e2e669`; backup `backup/vin-n2-before-902bf056-20261018`. Chỉ nhập file N1 qua commit producer; không sửa file N1. API admin GET mới chưa có trên SHA này; tiếp tục phần không phụ thuộc API trong lúc chờ.
- Owner bổ sung lane N2: `scripts/workforce/check_personal_postgres.py` (runner concurrency), test/browser fixture mới cho hành trình Platform/UI/runtime và `scripts/workforce/` + `docs/vin-platform/N2_*` cho gói test model thật. Test Domain/helper hiện có chỉ import/read, không sửa. Mỗi slice sẽ ghi lệnh, PASS/SKIP/FAIL/ERROR và commit riêng.
- Chủ dự án đã xác nhận E2E bao gồm cư dân link → Leader/case → staff/progress/photo → consent, cộng Builder/eval/publish và lịch/Discord. Model/provider/HTTP ngoài localhost dùng giả; gói model thật chỉ chuẩn bị lệnh/dữ liệu/ngân sách, không chạy.

### S12a — Đóng gate concurrency PostgreSQL tại lane N2

- Runner mới `P/scripts/workforce/check_personal_postgres.py` xóa model credentials kế thừa, không load .env, chỉ cho kết nối loopback PostgreSQL đúng port. Tạo database `vin_n2_concurrency_<uuid>` mới, cài extension vector và FORCE DROP đúng DB do runner tạo trong finally; không dùng bảng/DB ứng dụng. Test giữ nguyên source personal_chat và deterministic provider.
- Lệnh: `.venv/Scripts/python.exe scripts/workforce/check_personal_postgres.py --admin-url postgresql://postgres:offline-n2-fixture-password@127.0.0.1:55441/postgres` từ P, container fixture `vin-n2-pg-fixture-20261018` (pgvector:pg16). **PASS 1 / SKIP 0 / FAIL 0 / ERROR 0**, Python 3.11.9 Windows, 7.21s; lượt đầu trước sửa cleanup-on-extension-error cũng 1/0/0/0. Ruff F401/F811/F821/F841 PASS.
- Test chạy thật coordinator + hai peer, TeamSay handoff/question/answer/result/customer_reply, dispatcher và concurrent connections PostgreSQL. Provider chỉ scripted; network attempts ngoài PG 0, paid model calls 0. XML/summary/log nằm `.artifacts/personal-postgres/` và `.artifacts/n2-s12-personal-postgres.log`.
- Gate SQL trước đây SKIP nay có bằng chứng riêng PASS trên N2 sau rebase 902bf056. Không sửa số SKIP lịch sử của runtime suite 487/25 và không coi ca concurrency là business UAT hoặc model chất lượng thật.

### S12b — E2E WIP trước ghép API admin mới

- N1 vừa giao `e562059b` (admin read/CAS + migration 0024). Checkpoint WIP browser fixture trước ghép commit; chưa coi E2E PASS. Owner file mới cụ thể: `P/tests/vin_journey_fixture.py`, `vin_journey_browser_test.py`, `P/scripts/workforce/check_vin_journey.py`.
- Fixture chạy browser thật trên local Uvicorn cùng loop runtime, phục vụ bundle frontend và API cùng origin; Domain qua ASGI transport với PostgreSQL role hạn chế. Chỉ mock identity provider Domain và model IO, không tạo response nghiệp vụ giả cho browser. E2E đầu **0 PASS / 0 SKIP / 0 FAIL / 1 ERROR** (purpose secret fixture sai, đã sửa); lượt sau **0 PASS / 0 SKIP / 1 FAIL / 0 ERROR** vì SQLite không hỗ trợ khóa refresh auth. Đang chuyển Platform fixture sang PostgreSQL, không sửa auth production để né lỗi. Sẽ mô phỏng đúng proxy_cookie_path của nginx.

### S12c — Gói model thật đã chuẩn bị, không thực thi

- Dữ liệu `docs/vin-platform/N2_MODEL_OWNER_TEST_20261018.json` có M01 Leader/create, M02 progress/consent, M03 Builder/eval/publish, M04 schedule/Discord, tiêu chí và stop conditions. Runbook `N2_MODEL_OWNER_TEST_RUNBOOK_20261018.md` có lệnh chuẩn bị/đọc trạng thái và bước UI chủ dự án tự chạy; không SDK/provider trực tiếp.
- Ngân sách dự kiến input 90k/output 15k = 105k; biên 150k, hard cap user test 200k token ngày/tháng qua quota C03; max output 512, concurrency 1, không retry tự động. Chưa chọn model nên không bịa chi phí tiền; giá thực tế do chủ dự án tính theo model/hóa đơn và gồm judge/summary. Quota là override user tổng hợp, không sửa role toàn khách.
- `.venv/Scripts/python.exe scripts/workforce/prepare_owner_model_test.py --output .artifacts/owner-model-20261018`: **PASS (kiểm dữ liệu/lập phiếu, không phải model test)**; Ruff F401/F811/F821/F841 PASS. Lượt đầu stdout cp1252 lỗi khi in prompt tiếng Việt, đã đặt UTF8 và chạy lại thành công. Phiếu toàn bộ **NOT_RUN**, `executed=false`. Không đọc key/credential/env thật, không mạng, không tạo model/client. Model thật: **0 lượt chạy**, không được ghi PASS/SKIP chất lượng model.

### S12d — Checkpoint tích hợp admin và browser/runtime trước fix producer mới

- API `e562059b` đã merge tại `7797d2fd`, gồm migration 0024. UI đã nối admin page/filter/pagination, policy read + CAS/remove override, inactive catalog, revoke grant/membership theo revision, eligibility và review tài liệu KB bằng token revision. Browser E2E qua JWT/auth thật + PG authority + real SQL storage: admin **1 PASS / 0 SKIP** trước bổ sung conflict/pagination; Builder eval/publish/reload **1 PASS / 0 SKIP**; schedule/Discord runtime+saved REST fake transport+ledger **1 PASS / 0 SKIP**, paid model calls 0.
- Regression browser admin fixture riêng **5 PASS / 0 SKIP**. Strict contracts sau sửa opaque link **64 PASS / 0 SKIP / 0 FAIL / 0 ERROR**. Migration+consumer PG trên head **0024: 8 PASS / 0 SKIP**. Build/typecheck/ESLint admin PASS; build còn chunk-size warning.
- E2E tìm lỗi consumer thật: Params UUID đổi Platform link hex thành ID có gạch, tool trả DOMAIN_LINK_REQUIRED. Đã giữ link_id opaque str và fixture chung dùng đúng hex, thêm regression tool create. Owner `_tool/_customer_service.py` thuộc lane N2.
- Lỗi fixture được ghi đúng: browser admin label select chứa option text, đã gắn htmlFor/id rõ; test pagination selector trùng label/button, đang chỉnh selector. Customer test đầu đọc case pending quá sớm, đã chờ canonical tickets; staff scope dùng management thật và cần repair approval trước in_progress, đang nối cú bấm Platform. Chưa đánh dấu customer E2E PASS.
- Một lượt Discord fixture quên mock chat_kind/chat_name của SDK, outbound guard bắt **1 external network attempt**, test FAIL, **paid calls 0** và không key thật. Đã mock đúng metadata IO, giữ code gửi saved-message REST thực với fake HTTP; lượt cuối automation nêu trên 0 external attempts. Không giả lập business response cho browser.
- N1 vừa commit `fb70de9e` (CSP redirect/Origin, link normalization, C07 explicit version = ticket version của Domain approval, canonical close). Sẽ ghép producer đã commit rồi chạy lại customer browser; giữ consumer signature/owner riêng. R04 clarification thay yêu cầu "own approval revision" cũ: Domain không có integer revision approval, consumer dùng field version explicit đã nằm trong canonical hash và Domain kiểm ticket version.
