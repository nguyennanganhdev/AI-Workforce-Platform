# Kết quả Người 2 — N2-01 và hai slice N2-02

Ngày 18/10/2026 theo giờ Việt Nam. Baseline `dev_Chien@1ec4465d7f2928f9610b02b0126d39b1443f4163`.
Worktree `E:/AI-Workforce-Platform-user2`, branch `feat/vin-user2-experience-20261018`.

Các slice runtime: `e6cb3495` (bỏ seed key), `88098c39` (shared Knowledge).
Trong lúc làm việc, worktree gốc `dev_Chien` đã tiến lên `fe56707a` bởi luồng khác;
lane Người 2 vẫn giữ baseline đã chốt, chưa merge/rebase hoặc đẩy remote. Cần chọn cùng RC khi tích hợp.

## Trạng thái thực tế

| Phạm vi | Kết quả | Gate còn lại |
| --- | --- | --- |
| N2-01 consumer UI | Đã triển khai và kiểm tra offline/browser | Chưa nghiệm thu workspace authority/remaining quota/Domain link thật trên cùng RC Người 1. |
| N2-02 bỏ seed key | Hoàn tất slice sớm, commit `e6cb3495` | Người 1 tích hợp cùng authority/provider/quota/migration của N1-03. |
| N2-02 shared KB | Catalog/readiness/binding/stage/rollback/runtime dùng resolver chung, đã kiểm tra offline | RAG/citation thật, resource version/recall, MCP/skill resolver và purpose/visibility chưa hoàn tất. |
| N2-03…N2-10, N2-09A/B | Chưa hoàn tất | Không đánh dấu xong bằng kết quả của các slice trên. Cutover/pilot/live UAT vẫn PENDING. |

Không có deploy, push, bật flag cư dân, gọi model/embedding API, sử dụng model key thật, Discord hoặc mutation Domain thật.
Các tài liệu/WIP trong worktree gốc và code lane Người 1 được giữ nguyên.

## Giao diện thống nhất

Cư dân/khách hàng dùng cùng Platform như BQL: cùng shell/sidebar, Leader, chat riêng/nhóm, agent, Builder và
Knowledge. Chức năng hiện theo capability và phạm vi dữ liệu; quyền cư dân không thành quyền BQL.
Không tạo một portal cư dân rút gọn. Leader là trang mặc định, kể cả tài khoản đang chờ policy.

Đã bỏ thanh điều hướng hai dropdown gây khó hiểu trong prototype đầu. Sidebar có nhãn rõ trên desktop,
drawer trên mobile; tài khoản/hạn mức và liên kết Domain là các mục trong shell hiện có.
Chuyển Cá nhân/Vận hành/Quản trị nằm trong menu tài khoản, chỉ hiện không gian server cấp capability.

Đăng ký cá nhân chỉ gửi email, username và password qua `/auth/register-personal`.
URL trực tiếp qua cùng bảng capability với navigation. C01 sai version/user/tenant/boolean map hoặc
không tải được sẽ chặn mounting page. Đổi scope hoặc authorization revision sẽ hủy request, xóa cache và
mount lại consumers. Không dùng role hoặc browser preference làm nguồn quyền.

Usage phân biệt used/reserved/pending reconciliation; số liệu thiếu không trở thành zero.
Link callback gắn transaction với user/tenant/state, xóa code khỏi URL, không replay code khi mất response.
Unlink cần xác nhận và tải lại trạng thái canonical, không dùng kết quả optimistic làm bằng chứng thành công.

## Runtime

`_platform_credential` và đường persist shared key vào credential user đã bị gỡ.
Console và Studio dùng callable C03 `platform_model_config`, lấy alias/reference service-owned.
Vin mode thiếu authority/policy/grant bị chặn. Model config được resolve trước khi tạo record/session để
không sinh agent mồ côi chỉ vì thiếu provider policy.

Shared KB dùng `ResourceAccessService` tại authoring catalog, stage/publish/rollback và readiness runtime.
Readiness đọc documents trong namespace owner thật. Revoke chặn run mới; lỗi policy store không trở
thành manifest ready. Đây là bằng chứng consumer offline, chưa phải retrieval/citation bằng model thật.

## Bằng chứng kiểm tra

Python 3.11.9, Node 24.15.0. Dependencies theo workflow; không load `.env` hay DSN production.

| Kiểm tra | Kết quả |
| --- | --- |
| `check_builder.py --runtime` + producer C01–C03 thật bằng package overlay chỉ dành test | **301 passed, 1 skipped**, 0 lỗi; gồm **11 ca browser** chạy với frontend build/preview, kiểm cả tải font/code assets. |
| Skip concurrency SQL trong `personal_chat_test` | SQLite chỉ kiểm persistence/API; PostgreSQL concurrency chưa chạy. |
| `pnpm --filter frontend test:vin-shell` | **8 passed**: contract/principal/capability/direct URL/revoke/redaction/usage/redirect. |
| `pnpm --filter frontend test:office` | **26 passed**. |
| Client/chat events Node tests | **5 passed**. Đã sửa fixture thiếu `window.location.origin`, xác nhận cùng lỗi trên baseline. |
| Frontend lint/build (gồm TypeScript) | **PASS**. Build còn cảnh báo chunk lớn của bundle hiện có. |
| Ruff F401/F811/F821/F841 trên file Python sửa | Còn **1 F401 có sẵn**: import `MCPClient` ở console; cùng lỗi tại baseline, giữ ngoài scope cleanup. |
| Network/model | Runner chặn outbound; **external_network_attempts=0, paid_model_calls=0**. Browser chỉ cho origin Vite local và HTTP fixture. |

Producer test lấy `vin_platform` từ worktree Người 1, còn console/Studio/runtime lấy từ Người 2; DB SQLite
tạm dùng identity và model alias giả. Điều này chứng minh callable giao nhau, không phải hai branch đã
merge/deploy hoặc thành một RC. C01 fixture do producer thật xuất đã qua parser frontend.

Evidence local (ignored): `platform_VP/agentscope/.artifacts/builder-check/summary.json`, `pytest.xml`,
`run-runtime-integration.log`; `.artifacts/vin-shell-browser/account-375.png` và `account-1280.png`.

## Gate và bàn giao

`VITE_VIN_EXPERIENCE_ENABLED` mặc định tắt. Backend phải có `VIN_PLATFORM_ENABLED` cùng migration/policy/catalog
phù hợp trước khi tích hợp. Không mở cư dân khi C01–C09 tương ứng chưa nghiệm thu.

C01 hiện chỉ trả một workspace cá nhân; đổi không gian UI chưa đổi authority workspace ở server.
C03 chưa trả effective limit/remaining. Producer chưa có capability quản trị account/provider/schedule/channel
đủ để mở tất cả màn hình; UI không tự suy quyền từ role. Delta được ghi tại
[N2_CONTRACT_HANDOFF_20261018.md](N2_CONTRACT_HANDOFF_20261018.md).

N2-04 cần manifest/lease/fence/batch activation/repair bền vững từ C09; claim boolean hiện có chưa đủ
nghiệm thu crash/race. N2-03/08 cần self context, event/replay, publication/intent và operator projection.
N2-05/06/07 cần sandbox và identity/run/delivery contracts đã chốt. Không dùng in-memory authority hoặc fake
response để vượt gate. Model/RAG/Discord/Domain/staff/pilot/UAT/cutover đều giữ **PENDING**.
