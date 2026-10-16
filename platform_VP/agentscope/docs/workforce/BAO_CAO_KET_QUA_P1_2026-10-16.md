# Kết quả triển khai P1 — 16/10/2026

> Cập nhật bản tích hợp: [bàn giao Docker/VPS P0–P2 16/10/2026](BAO_CAO_BAN_GIAO_DOCKER_VPS_P0_P2_2026-10-16.md). P1 đã triển khai cùng P0/P2; phần dưới giữ bằng chứng tại thời điểm viết. UAT model thật chưa nghiệm thu; phiếu cũ thiếu hợp đồng được giữ và chặn xử lý tiếp.

Phạm vi: checkout `E:\AI-Workforce-Platform`, nhánh `develop2`, HEAD nền `2b9de30f7aff05a72716f480efd10429ea134fb6`. Các sửa đổi nằm trong working tree, chưa commit/push hoặc triển khai lên VPS. Giữ nguyên các thay đổi P0 và những thay đổi ledger/memory/offsite có sẵn hoặc xuất hiện đồng thời trong workspace.

Không nạp `.env`, không dùng provider API key, không gọi model trả phí. Model/MCP trong test Platform là scripted peer. PostgreSQL kiểm thử được tạo riêng với tên `workforce-p1-test-pg`; không dùng database của các stack đang phục vụ.

## 1. Kết quả theo nhóm

| Nhóm | Thay đổi đã triển khai trong source | Kiểm chứng / giới hạn |
| --- | --- | --- |
| P1-A: hồi phục | Ghi intent và enqueue reconcile trong cùng transaction; retry cùng reference đọc receipt đã lưu; lookup `vh_operation_get` chỉ đọc; worker reprocess quarantine; expiry job giải quyết approval và resume với denied; chặn event cùng rank có version cũ; projection có stable event ID và durable replay; startup khôi phục job cho record pending cũ | Test crash sau intent, timeout sau side effect, duplicate call, lookup receipt, event trước operation, stale/unversioned event, lỗi projection, expiry và restart. Không gửi lại write chỉ vì kết quả chưa rõ |
| P1-B: version | Giữ toàn bộ immutable publication; không fallback về current khi thiếu pin; snapshot route/tools/input schema/policy/grant/schema cùng transaction tạo workflow; runtime và provider dùng snapshot; Leader truyền version pin sang AgentInvite; storage SQL/Redis CAS; rollback mang đúng report của spec đích | Test 52 publications giữ version 1, hai writer SQL/Redis chỉ một thắng, không sửa lịch sử, A→B→rollback A có hash/report A, đổi config/tool schema/event schema live không đổi ticket cũ |
| P1-C: sandbox | Generator Compose riêng cho Platform/PostgreSQL/Redis/MinIO và Domain/PostgreSQL; loopback ports, internal network, secrets sinh mới, volume/project riêng; manifest source/image/model/declaration/schema/seed; fixture tạo cư dân/staff và 24×3 ticket UUID thật; reset dùng project/database mới | Compose config hợp lệ; fixture PostgreSQL tạo 72 ticket và 72 `ticket.created`; chạy lại không sinh trùng; fresh run có ticket khác. Stack đôi mới ở mức chuẩn bị, chưa build/start/onboard hoặc nghiệm thu model thật |
| P1-D: nghiệm thu | Catalog 24 scenario ×3; driver chạy SQL/API/worker thật với scripted peers; đọc lại SQL/event evidence bằng judge deterministic riêng; gate critical 100%, business pass^k với threshold đặt trước; digest từng evidence; nhập verdict của judge độc lập và xuất human-review queue | Rehearsal offline và artifact ở mục 2. `business_accepted=false` khi chưa có model/judge thật; không dùng pass offline để chứng nhận UAT |

## 2. Bằng chứng kiểm thử

Thư mục bằng chứng: [`../../.artifacts/p1/`](../../.artifacts/p1/).

| Lượt kiểm | Kết quả / artifact |
| --- | --- |
| Platform integration/console/P0 regressions liên quan P1 | **116 passed**, 7 subtests; 1 test quality được loại khỏi lượt tập trung. `combined-final.xml` |
| Nhóm test P1 mới ở source cuối | **18 passed**. `p1-final.xml`; có overlap với lượt trên, không cộng thành tổng độc lập |
| Quality ledger và sandbox kiểm tra bổ sung | **6 passed**. `quality-and-sandbox-final.xml`; gồm test quality riêng và 5 test sandbox chạy lại |
| Domain bridge trên PostgreSQL riêng | **86 passed**. `p1-domain-bridge-final.xml` |
| Domain tools, staff lifecycle, receipt lookup và MCP authentication | **18 passed**. `p1-domain-tools-final.xml` |
| Fixture sandbox, guard và intake idempotency trên PostgreSQL | **8 passed**, không skip. `p1-fixture.xml` |
| Migration PostgreSQL mới | Upgrade thành công; đủ 6 cột recovery của migration `0018_unified_recovery`. `migration-postgres.json` |
| Acceptance offline trên source cố định | **24/24 scenario ×3, 72/72 lượt pass**, critical 100%, `source_unchanged=true`. [`acceptance-frozen/report.json`](../../.artifacts/p1/acceptance-frozen/report.json); `business_accepted=false` vì chưa chạy model/judge thật |

Migration head của toàn working tree lúc kiểm là `0019_model_call_ledger`, vì workspace có thêm phần ledger ngoài P1. Migration mới thuộc P1 là `0018_unified_recovery`; không tự nhận phần ledger là kết quả của lượt này.

Lượt tập trung loại duy nhất test `test_quality_counts_outcomes_refusals_and_cost`; test này đã được chạy bổ sung và **pass** với fixture ledger hiện tại. Không tuyên bố toàn suite/CI đã xanh. Ruff cho các module P1 mới và `git diff --check` đạt.

`acceptance-final` có 72/72 lượt scenario pass nhưng gate provenance từ chối vì source thay đổi trong lúc chạy. Bằng chứng chốt dùng bản sao source cố định tại `E:\tmp\workforce-p1-source-20261016`, giữ thông tin checkout/branch/commit gốc và fingerprint working tree. Không lấy kết quả từ checkout hoặc image khác để gán cho HEAD.

## 3. Cách chạy lại không cần key

Từ `platform_VP/agentscope`, dùng Python có package và test dependencies đã cài. Môi trường kiểm thử của lượt này là `E:\tmp\workforce-p1-venv\Scripts\python.exe`.

```powershell
& 'E:\tmp\workforce-p1-venv\Scripts\python.exe' -m scripts.workforce.acceptance.run `
  --business-threshold 1.0 --repetitions 3 `
  --output .artifacts/p1/my-fresh-run
```

`1.0` là ngưỡng kỹ thuật bảo thủ dùng cho rehearsal này, chưa phải ngưỡng business đã được vận hành ký duyệt. Runner bắt buộc khai báo threshold trước khi chạy, không cho ít hơn ba repetitions, không bỏ qua case lỗi, không overwrite run cũ. Source thay đổi trong lúc chạy làm kết quả tự động không đạt.

Nếu working tree đang được chỉnh sửa song song, dùng snapshot source cố định:

```powershell
& 'E:\tmp\workforce-p1-venv\Scripts\python.exe' -m scripts.workforce.acceptance.freeze `
  --snapshot E:/private/p1-source-snapshot `
  --business-threshold 1.0 --repetitions 3 `
  --output E:/private/p1-acceptance-run
```

Lệnh sao chép source/test cần thiết, không sao chép `.env` hay credentials; từ chối nếu source đổi trong lúc copy, rồi thực thi trên copy bằng cùng Python environment. Fingerprint được tính lại trước/sau run.

Mỗi lượt có bảng workflow/operation/receipt/approval/checkpoint/public event/durable job, kết quả assertion và SHA256. `human-review.json` chứa case lỗi cần người review. Judge model độc lập có thể đọc evidence sau đó và cung cấp JSON gồm `report_sha256` bằng `evidence_index_sha256`, `model`, `independent=true`, cùng `verdicts` cho đủ mọi cặp scenario/repeat. Mỗi verdict cần `scenario`, `repeat`, `evidence_sha256`, `passed` boolean và `reason`.

```powershell
& 'E:\tmp\workforce-p1-venv\Scripts\python.exe' -m scripts.workforce.acceptance.review `
  --run .artifacts/p1/my-fresh-run `
  --judge-report E:/private/independent-judge.json `
  --output E:/private/review-result.json
```

Review kiểm lại digest và assertion trước khi nhập verdict; judge sai run, thiếu repetition hoặc evidence bị sửa đều bị từ chối. Verdict model trên rehearsal scripted vẫn không biến thành nghiệm thu model thật.

## 4. Chuẩn bị sandbox nghiệp vụ để kiểm tra tiếp

```powershell
& 'E:\tmp\workforce-p1-venv\Scripts\python.exe' -m scripts.workforce.business_sandbox prepare `
  --run-id p1-my-run --seed 42 `
  --output E:/private/workforce-sandbox-p1

docker compose -f E:/private/workforce-sandbox-p1/compose.json config --quiet
docker compose -f E:/private/workforce-sandbox-p1/compose.json up --build -d

& 'E:\tmp\workforce-p1-venv\Scripts\python.exe' -m scripts.workforce.business_sandbox record-runtime `
  --output E:/private/workforce-sandbox-p1
```

Generator chỉ ghi thư mục mới ngoài Git; Compose chứa credentials local sinh mới nên không đưa folder này lên PR hoặc gửi công khai. Default ports: Platform `127.0.0.1:18100`, Domain `127.0.0.1:18098`. Domain init xuất `domain-private/fixture.json` cùng tài khoản synthetic riêng; 72 ticket được tạo qua hàm intake thật.

`manifest.json` phân biệt `prepared_only`, image reference và image ID thực sau startup. `record-runtime` kiểm source, topology, container labels, run ID và fixture trước khi ghi bằng chứng. Reset: chạy `prepare` với output mới; project, database, secrets và volumes mới, giữ dữ liệu run cũ.

Sau startup cần onboarding route tới MCP nội bộ `http://domain-api:8000/mcp` và cấu hình bridge nội bộ `http://platform:8000` bằng các API onboarding/connection hiện có. Việc này chưa được thực hiện trong lượt no-key này: không có model credential để tạo/eval đội business. Không bật lại preset hoặc dùng trusted provisioning thay cho business evaluation. Network mặc định không có egress; model chạy trong sandbox hoặc qua proxy provider do operator cấu hình riêng khi test thật. Không gỡ isolation toàn stack để chạy test.

Partner checker nhận `--ticket-id` là UUID từ fixture; external_request_id cũng là UUID. Business mode bắt buộc đạt close có terminal work và resident acceptance; không còn tính request completed/skip close là nghiệm thu. `--stop-tracking-only` được ghi rõ là transport check.

## 5. Điều kiện trước rollout và giới hạn còn lại

- Backup rồi migrate schema trước khi chạy source mới. Chưa migrate hoặc recreate image của stack hiện tại/VPS trong lượt này.
- Workflow mới có contract snapshot; workflow unified cũ thiếu snapshot bị chặn bằng `WORKFLOW_CONTRACT_NOT_PINNED`, không tự ghép contract hiện tại vào ticket cũ. Cần đối chiếu lịch sử để phục hồi có kiểm soát.
- Version đã bị xóa bởi cửa sổ 50 của code cũ không thể tự tái tạo; thiếu pin báo lỗi rõ. Code mới giữ mọi publication.
- Quarantine cũ không lưu raw envelope không đủ bằng chứng để tự replay; cần operator khôi phục từ outbox gốc. Receipt mới lưu envelope và schema, tự phục hồi qua worker.
- Hai nửa Platform/Domain đã kiểm thử riêng với peer mô phỏng; chưa có bằng chứng hai stack mới cùng chạy qua full business closure với model/provider thật.
- Chưa chạy model judge độc lập, human UAT, paid-provider test, load/HA hoặc production acceptance. Đây là phần người dùng giữ lại để tự test với key sau khi review source.

## 6. Kiểm tra lại điều kiện commit và rollout

**Kết luận:** có thể chốt code thành release candidate sau khi tách đúng phụ thuộc; chưa đủ bằng chứng để gọi P1 hoàn tất nghiệm thu hoặc thay ngay image production. Không cần chờ toàn bộ P2 để phát hành P1. P0 là nền bắt buộc; báo cáo P0 ghi đã deploy hai VPS nhưng code vẫn chưa commit. Không lấy trạng thái Docker local làm bằng chứng VPS hiện tại.

Working tree hiện chứa cả P0/P1/P2 trên cùng HEAD `2b9de30f`. Những file như Studio router, storage, AgentInvite, runner và quality chứa thay đổi của nhiều nhóm; source quality hiện gọi ledger P2, migration `0019_model_call_ledger` nối sau `0018_unified_recovery`. Không stage toàn bộ file trộn rồi đặt tên commit là P1 độc lập. Chốt P0 trước, sau đó commit P1 theo hunk/dependency; nếu phát hành chung thì kiểm thử và ghi đúng phạm vi P0+P1+phần P2 đi kèm.

Kiểm tra không dùng model key trên source hiện tại: **59 passed** cho các nhóm P1/P0 liên quan (`readiness-current.xml`); **3 passed** cho công cụ kiểm tra cutover mới (`rollout-check-tests.xml`), Ruff và diff whitespace đạt. Đây là kiểm tra tập trung, không thay cho CI toàn release hoặc test image cuối.

Đã bổ sung `scripts/workforce/p1_rollout_check.py`. Công cụ chỉ đọc SQL/Redis, chạy được trên schema trước `0018`, không tự pin contract hoặc sửa lịch sử. Nó chặn workflow active thiếu/corrupt snapshot, version pin thiếu hoặc không còn trong storage, quarantine thiếu envelope, schema không đủ để kiểm tra. Kết quả xanh chỉ là `data_preflight_pass`, không chứng nhận production acceptance.

Preflight thực tế của **local `awp-develop2-app-1`**, không phải VPS:

| Kiểm tra | Kết quả |
| --- | --- |
| Schema đang phục vụ | `0017_unified_partner_case` |
| Workflow unified active thiếu contract snapshot | **3**, preflight không đạt |
| Operation còn mở | **4**, cần đối soát; không tự hủy/đóng |
| Pending approval / quarantine | 0 / 0 |
| Image Platform local có trường agent CAS | Chưa có |
| Image Domain local có `operation_get` | Chưa có |

Artifact: [`rollout-local-inventory.json`](../../.artifacts/p1/rollout-local-inventory.json). Cần chạy lại cùng công cụ trong môi trường VPS đích và lưu evidence riêng trước rollout; không suy số lượng local sang VPS. Dùng Python của app với biến SQL/Redis runtime và `--output <đường-dẫn-mới>`; công cụ không tự nạp `.env`, không ghi DB, không gọi model và không đưa connection string vào report.

Thứ tự còn lại để được deploy:

1. Chốt source P0 và phạm vi commit P1; giữ phần P2 chưa chọn ngoài release hoặc khai báo/phê duyệt đúng phần đi kèm.
2. Build image Platform **và Domain** từ release source cố định; chạy migration `0018` trên bản restore cô lập, thêm `0019` nếu release có ledger P2. Kiểm chứng backup/rollback và xử lý queue job P1 trước khi quay về worker cũ.
3. Chạy preflight trên dữ liệu đích; xử lý từng workflow legacy theo lịch sử đã xác minh. Version/envelope đã mất cần phục hồi từ nguồn gốc, không sinh bằng chứng thay thế.
4. Start/onboard cặp sandbox bằng đúng image; xác nhận Domain reader, ticket grants, worker recovery và chu trình dispatch→staff→QC→resident acceptance→close. Sau đó record image ID/source/schema/seed.
5. Chạy model thật, judge độc lập và human UAT theo yêu cầu; giữ chính sách không gọi provider key trong lượt hiện tại. Chỉ sau acceptance mới mở production cho ticket nghiệp vụ.

P2 quan sát/chi phí/memory không phải điều kiện bắt buộc phải hoàn thành toàn bộ trước bước 1–4. Backup/restore, cảnh báo cơ bản và kiểm soát dữ liệu cũ là điều kiện vận hành của release, dù công việc đó nằm trong tài liệu P2.
