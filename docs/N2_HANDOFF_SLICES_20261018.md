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
