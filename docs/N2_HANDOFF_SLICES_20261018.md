# Người 2 — handoff các slice từ baseline PR #99

Phạm vi theo hai kế hoạch đã chốt ngày 18/10 và chỉ dẫn mới nhất của chủ dự án.
Không dashboard BQL, exception queue, operator grant/approval bridge hoặc bot Discord chung.
Khách hàng dùng cùng UI/các trang Platform, dữ liệu riêng; Provider/MCP/Skill được cấp chỉ xem/chọn/dùng.
Không chạy test bằng model key thật; không bật production/cutover bằng kết quả fixture.

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

## S03 — Consumer catalog MCP/Skill

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
