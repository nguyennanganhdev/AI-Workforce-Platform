# Người 1 — migration/config và gate tích hợp

Ngày 18/10/2026. Source delivery; chưa phát hành production. Không dùng key model thật để test.

## Thứ tự nâng cấp

1. Chụp SHA/image/config manifest; sao lưu PostgreSQL, Redis, MinIO và workspace/Qdrant theo runbook release hiện có. Không in secret vào manifest. Rehearsal trên bản sao disposable, không dùng DSN production trong test.
2. Giữ `VIN_PLATFORM_ENABLED=false`, `VINHOMES_CUSTOMER_PLATFORM_ENABLED=false` và frontend flag Người 2 tắt. Backup trước expand schema.
3. Platform: dùng cùng SQL authority với AuthService. Chạy Alembic từ base hiện tại qua `0021_vin_platform_authority`, `0022_personal_job_owner`, `0023_personal_job_constraint`, **`0024_vin_admin_revisions`**. Migration 0021 đóng băng 17 bảng Vin; 0022 thêm personal owner, 0023 sửa CHECK queue; 0024 backfill revision grant/membership và cờ active cho quota override. `create_app` không tự tạo bảng; khi bật Vin, lifespan kiểm schema/constraint và dừng startup nếu thiếu migration.

   Từ `P`, với `AGENTSCOPE_SQL_URL` là DSN đích đã xác minh:

   ```powershell
   python -m alembic -c src/agentscope/app/storage/_sql/_alembic/alembic.ini upgrade head
   python -m alembic -c src/agentscope/app/storage/_sql/_alembic/alembic.ini current
   ```

4. Domain: áp schema migration hiện có qua `0026_platform_customers.sql`, rồi cập nhật runtime role bằng `schema/roles.sql` qua công cụ DB của Domain. Runtime role không superuser/BYPASSRLS, không được ghi client registry. Backfill event sequence trong cùng migration; origin cũ mặc định `domain`, không đổi workflow lịch sử.
5. Provision registered Domain client bằng `python -m vinhomes_api.platform_customers --help`; dùng secret env riêng của operator và URI chính xác. API runtime chỉ đọc registry. Không chạy provision vào production trong lượt phát triển này.
6. Khởi động code mới khi flag còn tắt. Tích hợp commit Người 2 bỏ console key seeding trước bật cohort. Chạy `/admin/vin/credential-migration` với `dry_run=true`; xét counts/unmapped/conflicts, rồi apply bằng CAS. Giữ ID credential đang được agent/session/KB embedding tham chiếu. Bản không xác định không được tự xóa hoặc coi là an toàn.
7. Admin cấu hình secret/provider/capability, cấp eligibility, quota và catalog grants cho pilot. Test riêng từng user/role, khôi phục và canary; chỉ bật sau khi các consumer/runtime tương ứng được nghiệm thu. Chưa tắt chatbot cũ/cutover cohort bằng chứng offline.

## Config manifest

| Thành phần | Cấu hình | Quy tắc |
| --- | --- | --- |
| Platform | `VIN_PLATFORM_ENABLED` | Helper chung chỉ nhận `true`, mặc định tắt |
| Platform | SQL DSN AuthService + storage | IAM/quota/link/case dùng engine AuthService; Redis không là nguồn quota thứ hai |
| Platform | `VIN_PLATFORM_ENCRYPTION_KEY` | Fernet key server; backup/rotation theo version triển khai, không vào public DTO |
| Platform | `WORKFORCE_PLATFORM_OPENAI_API_KEY` | Chỉ server hydrate alias; không gọi provider trong test, không seed vào user |
| Platform | catalog/model/policy | Admin cấp đúng environment, role/group/user/pool; thiếu policy/grant thì deny |
| Domain | `VINHOMES_CUSTOMER_PLATFORM_ENABLED` | Mặc định tắt, độc lập luồng legacy/staff |
| Domain | `VINHOMES_CHATBOT_COHORT_CUTOVER_ENABLED`, `VINHOMES_CHATBOT_PLATFORM_COHORTS` | Mặc định false/[]; compose truyền vào api/platform-sync. Không bật M2 cùng lúc bật liên kết; chỉ cutover sau cohort sign-off |
| Domain | registered client + issuer/redirect | Operator provision; secret hash, exact redirect, HTTPS hoặc loopback test |
| Sandbox | `VINHOMES_API_EVAL_FIXTURES=enabled` + DB marker | Cần cả hai và synthetic linked subject; không bật/reset production |
| Người 2 | `VITE_VIN_EXPERIENCE_ENABLED` | Giữ cùng UI; N1 không đổi frontend/deploy file lane Người 2 |

## Vận hành quota và rollback

Worker mỗi 30 giây đọc attempt/receipt cục bộ theo batch; không retry model để tìm usage. Timeout/cancel sau dispatch giữ token pending, trả slot đồng thời. Có receipt xác minh thì settle qua worker hoặc API admin `POST /admin/vin/attempts/{id}/reconcile` với `actual_tokens`, `receipt_ref`; thao tác có audit. Không tự refund theo TTL. Reserved crash chưa có terminal receipt vẫn giữ, cần đối soát trước điều chỉnh.

Rollback bằng feature flags/candidate image tương thích, giữ bảng/ledger/link/job audit. VIN_USER bị chặn khi Vin flag tắt, không rơi về auth header legacy. Không downgrade xóa bảng để chữa lỗi runtime. Staff Domain và ticket `origin=domain` tiếp tục worker cũ; `origin=platform` không được chuyển sang BQL. Chỉ restore snapshot khi có kế hoạch đối soát operation Domain đã được chấp nhận sau thời điểm backup; restore DB không đảo ngược công việc staff đã thực hiện.

## Bằng chứng hiện có và gate còn mở

- Kiểm gói Domain không đọc deployment.env: từ `vinhome_Recident/services/vinhomes-api`, chạy `python tests/vin_domain_rc_check.py --output <ignored-dir> [--image <candidate-tag>]`. Config chỉ dùng fixture giả, không start service; khi có image thì kiểm production CMD, non-root UID, pip check, hash Python/SQL khớp source và loại trừ .env/secret/artifact files. Image phải có OCI revision label bằng HEAD đang kiểm. Đây là package proof, không thay browser/RLS/business UAT.
- Đã chạy migration từ DB PostgreSQL trống lên head hai lần, kiểm quota race/settle/revoke/session thật; CAS credential + batch agent activation SQL/Redis qua fake Redis.
- Shared auth fixture dùng DDL production 0007/0008. Integration Domain dùng runtime role hạn chế và RLS; không dùng model key thật.
- Python 3.11 Linux đã chạy authority/consumer/runtime bằng fixture; số PASS/SKIP thật ghi ở N1 handoff. N1/N2 đã merge vào dev_Chien local e7b80da6 và N1 rebase lên đó.
- Helper rehearsal: `python tests/vin_release_rehearsal.py --output .artifacts/<thu-muc-moi>` từ P; cần các image QA/infra và docker:27-cli. Tạo source stack dữ liệu giả, dùng script backup/verify-restore hiện có, rồi restore lần hai để so fingerprint SQL, Redis value/TTL, MinIO bytes, Qdrant point và private manifest. Không khởi động restored app/model. Artifact chứa config/secret **giả** của fixture, không commit archive/env.
- Còn PENDING: restore/canary trên release candidate thật và off-host; runtime/browser C09 consumer sau nối; positive linked-customer sandbox business; vision adapter; U01–U30/live business UAT. Rehearsal disposable không thay production cutover.
