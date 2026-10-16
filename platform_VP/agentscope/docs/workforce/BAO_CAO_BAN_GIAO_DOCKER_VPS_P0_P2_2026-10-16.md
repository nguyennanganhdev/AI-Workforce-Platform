# Bàn giao Docker/VPS tích hợp P0–P2 — 16/10/2026

Đã đóng gói và triển khai bản `p0p2-20261016` lên **cả VPS Platform và VPS Domain**. API hai phía healthy, giao diện mới hoạt động, ba route OP1/OP2/OP3 ready. Đã đối chiếu mã trong container, kiểm tra bridge/MCP/quyền truy cập, backup mã hóa ngoài VPS và khôi phục cô lập bản backup của đúng image mới.

Đây là nghiệm thu kỹ thuật của bản triển khai. **Chưa nghiệm thu chất lượng nghiệp vụ bằng model thật/người dùng**; không gọi model trả phí trong đợt đóng gói này. Các kết quả model/eval của P0 được giữ từ đợt trước, không chạy lại.

## 1. Phạm vi đã cập nhật

| Mục | Nội dung đang có trong bản triển khai | Bằng chứng/giới hạn |
| --- | --- | --- |
| P0-A: sandbox | Catalog server quyết định read-only; draft/model không được nâng quyền; kiểm tra lại trước connector; write tool dùng fixture/mock khi eval; phân loại không rõ bị chặn | Test chống giả `read_only`, safety/sandbox và MCP discovery thật cho cả ba owner; không gọi tool ghi nghiệp vụ để smoke |
| P0-B: publish | Builder chat và Studio dùng cùng publish gate; report gắn spec/test hash và seal; sửa draft làm report cũ mất hiệu lực; safety fail chặn publish; exemption chỉ dành cho provisioning có provenance | Test publish, invalidation, tampering, version pin, API owner scope; không publish agent mới chỉ để kiểm tra deployment |
| P0-C: đội nghiệp vụ | Giữ đội hiện có đã được người dùng chấp thuận: Điều phối, Kỹ thuật, Vệ sinh, An ninh; ba roster độc lập theo owner OP1/OP2/OP3; readiness kiểm tra published/version/owned/invitable/tool binding | Ba route đều ready, mỗi route 4 agent. Đợt này không sửa agent/version, không khôi phục preset đã xóa, không chạy lại eval trả phí |
| P0-D: hoàn tất | Close kiểm tra operation, approval và Domain acceptance; pending/unknown không được completion-close; stop-tracking tách khỏi hoàn tất nghiệp vụ | Regression SQL/API với terminal evidence, resident confirmation và trường hợp từ chối close |
| P1-A: recovery | Intent và durable reconcile job ghi cùng giao dịch; đối soát read-only; provider version/order, quarantine replay, projection idempotency; approval expiry và resume khi khởi động | 72/72 lượt scripted trên SQL/API/worker, gồm crash/timeout/replay/order/expiry; không suy ra acceptance với provider thật |
| P1-B: hợp đồng/version | Snapshot route/tool/schema/grant/agent version cho ticket mới; lịch sử version bất biến, CAS khi ghi AgentRecord; snapshot thiếu/hỏng bị chặn | Test không trôi cấu hình khi re-onboard và khi sửa version; phiếu cũ thiếu snapshot được giữ riêng để đối soát |
| P1-C: sandbox nghiệp vụ | Generator hai stack tách network/volume/credential, bind loopback; fixture tạo ticket qua API intake trên PostgreSQL sandbox có marker; dữ liệu synthetic, replay idempotent | Fixture 72 ticket, replay không nhân đôi; reset run có ticket mới. Chưa thực hiện UAT đầy đủ bằng model thật trên hai stack |
| P1-D: acceptance | 24 kịch bản × 3 lượt, evidence SQL/MCP/job/event và bộ kiểm tra độc lập theo quy tắc, hash nguồn/evidence, hàng đợi human review | 24/24 đạt cả 3 lượt; `automated_pass=true`, `business_accepted=false`, model judge chưa chạy |
| P2-A: quan sát/chi phí | Ledger từng invocation/model/endpoint/tier/workflow/purpose, retry/fallback, summary/learning/eval; usage completeness; giá versioned; latency p50/p95, failure/backlog/cache, export owner-scoped | SQL/Redis/adapter regression; dashboard thật hiển thị **Chưa xác định**, không tự tính giá hay coi usage thiếu là 0; chưa đối soát hóa đơn provider |
| P2-B: memory | Outcome idempotent, evidence gate cho mọi kind, provenance/TTL/retire, scope recall và chống contamination | SQLite/Redis/PostgreSQL regression; benchmark offline 8 case: 62,5% → 100%, contamination 0; đây là deterministic grounding benchmark, chưa phải cải thiện outcome thực tế |
| P2-C: vận hành/docs | Backup nhất quán bốn kho, image bundle và manifest; age + SFTP sang thư mục riêng trên VPS Domain; restore cô lập; backup/monitor timers, alert JSON+journal, RPO/RTO và runbook | Backup mới và restore PASS; khóa giải mã ở máy recovery cục bộ, ngoài cả hai VPS. Chưa có kênh email/chat trực ban hoặc production failover |

## 2. Image và nguồn phát hành

Nhánh `develop2`, commit nền `2b9de30f7aff05a72716f480efd10429ea134fb6`. Image được dựng từ snapshot WIP đã chốt, sau đó đối chiếu các file runtime với nội dung commit bàn giao. Commit/push được ghi ở `release.json` trên hai VPS và trong phản hồi bàn giao; không đổi nhãn OCI cũ thành SHA mới để giả lập một lần build khác.

| Thành phần | Image | Image ID |
| --- | --- | --- |
| Platform app | `agentscope-platform:2b9de30f-p0p2-20261016` | `sha256:3198eee14e11a4975818286de8155e8dcf334f66e99cc84716145057b709444f` |
| Platform web | `agentscope-platform-web:p0p2-20261016` | `sha256:c93b0df4b1a6a815fd3e4005d8b14fec477ceb11afb4196355a565cfb2879ca6` |
| Domain API / platform-sync / scheduler | `vinhomes-domain-api:p0p2-20261016-2b9de30f` | `sha256:2119c8cd4852c0bde76ec6750fc904a3a96162a70839b73990eac1c91cd7fea1` |

| Dấu vết | Giá trị |
| --- | --- |
| Snapshot manifest SHA-256 | `e1c936a2b0077f32227298b97e652b00e15b4b0dd576812fe5c1123fe7c45abc` |
| Platform archive manifest SHA-256 | `35ea550321c8c1fce0a673aa438469a26d2d8e40c46ce8677719cde71269b561` |
| Domain archive manifest SHA-256 | `a9a0eaec4b8eecb6c3631a69254a132db4f4849f69469646a216f6d9d928dc99` |
| Đối chiếu Platform trong container | 889 file runtime, 0 mismatch |
| Đối chiếu Domain trong container | 132 file package runtime, 0 mismatch; metadata egg-info của build nằm ngoài phép đối chiếu runtime |
| PostgreSQL Platform | Migration `0019_model_call_ledger`; xác minh trực tiếp 6 cột recovery của 0018 và bảng ledger |

Docker web được build cục bộ rồi chuyển lên VPS; hai backend build trên VPS từ tar nguồn đã xác minh hash và base image hiện có. Không recreate các stack Docker phát triển không thuộc đợt phát hành. Dependencies không thay đổi so với base; snapshot và image ID là bằng chứng nội dung chạy thật.

## 3. Kết quả kiểm tra

- **405 test riêng biệt** đã qua: 190 console/integrations, 103 ledger/memory/team/shared-context, 112 Domain bridge/tools/fixture. Một số test ban đầu thiếu fixture docs hoặc dependency Lua trong môi trường QA; đã bổ sung môi trường và chạy lại các phần lỗi, không sửa logic để né test.
- Image QA kế thừa đúng runtime phát hành: các test ứng dụng đã qua; bộ encryption/ops 6/6 qua trong container `--network none`, gồm age round-trip, sai khóa, corruption, checksum và alert.
- Acceptance offline **72/72 lượt**, threshold pass^3 = 1,0. MCP và model là scripted peers; không dùng kết quả này để đánh dấu UAT/provider acceptance.
- Bridge production: enabled, config version **8**, worker version **8**, **3** active routes, **0** pending commands, **0** pending events. Đọc được conversation snapshot; provider request đã xác thực trả 404 cho receipt không tồn tại.
- Cập nhật catalog cả ba owner và thêm **`vh_operation_get`** read-only làm recovery reader nội bộ; route gồm 8 tool. Giữ roster, published agent version và quyền tool nghiệp vụ hiện có.
- Dashboard HTTPS mới mở được, export đúng owner, cost unknown, không có page error. UI harness chỉ cấp JWT ngắn hạn tại refresh; không thay API dữ liệu và không coi đây là test đăng nhập tương tác.
- Smoke không tạo ticket/operation/approval mới, không gọi model: 13 auth users, 1 workflow, 2 partner requests, 0 unified operations, 0 approvals. Ledger vẫn là 1 call lịch sử của OP2, OP1/OP3 là 0.

## 4. Phiếu cũ được giữ để đối soát

Workflow `65f2243fe6624d15b2cdf193c7fef20c` vẫn **`awaiting_user`, revision 4**, không có operation/approval mở. Theo lựa chọn của chủ dự án, giữ dữ liệu và chặn xử lý tiếp bằng `WORKFLOW_CONTRACT_NOT_PINNED`; không tự dựng snapshot từ route hiện tại, không stop-tracking, không đánh dấu hoàn tất.

Vì vậy preflight dữ liệu tổng thể vẫn báo ngoại lệ này. Đây là ngoại lệ triển khai đã được chấp thuận, **không được sửa báo cáo thành data-preflight PASS**. Ticket mới dùng snapshot được ghi trong giao dịch tạo workflow. Muốn tiếp tục phiếu cũ cần khôi phục được bằng chứng hợp đồng lịch sử hoặc chủ dự án phê duyệt cách chuyển tiếp riêng.

## 5. Backup và khôi phục

| Mục | Kết quả |
| --- | --- |
| Platform trước deploy | `20261016T090948Z-awp-platform`; checksum và chuyển mã hóa ngoài VPS đã xác minh |
| Domain trước deploy | `/opt/vinhomes/releases/p0p2-20261016/predeploy`; dump database active `vinhomes_release_20261015_6884e1b1`, archive đọc được, 8.036.212 byte |
| Platform đúng bản mới | `20261016T092739Z-awp-platform` |
| Ciphertext SHA-256 | `d9c33b689ef565e785fa04763320769a15ad7802573ccc98a43eb395a8ccff72` |
| Ciphertext size | 604748120 byte |
| Restore tổng thời gian | **270.698 giây**, PASS |
| Image nguồn restore | `sha256:3198eee14e11a4975818286de8155e8dcf334f66e99cc84716145057b709444f` |
| Kiểm tra khôi phục | PostgreSQL migration/counts, Redis key count, MinIO bucket, workspace archive, image bundle |
| RPO/RTO mục tiêu | RPO ≤26 giờ; restore rehearsal ≤3.600 giây; evidence tối đa 7 ngày |
| Lịch | Backup 03:30 giờ Việt Nam; monitor mỗi 5 phút |

Offsite `source_revision` của đợt này là **SHA-256 snapshot manifest**, không phải Git SHA. Receipt/checksum và image/manifest của backup khớp bản mới. Restore tải ciphertext từ Domain, giải mã trên recovery cục bộ rồi phục hồi vào container/volume tạm `--network none`; không chạy restored app/model, không thay production database. Chưa thử production cutover/failover.

Đã sửa cấu hình metadata source revision khi bộ kiểm tra từ chối nhãn phát hành không phải hex SHA; tạo lại backup nhất quán và xác minh offsite/restore thành công. Backup có khoảng dừng ghi ngắn và app khởi động lại; health/monitor đã kiểm tra sau khi hồi phục.

## 6. Vận hành, rollback và phần còn lại

Platform: `/opt/awp-platform/app`, release `/opt/awp-platform/releases/p0p2-20261016`; Domain: `/opt/vinhomes/deploy`, release `/opt/vinhomes/releases/p0p2-20261016`. Canonical `release.json`, manifests và evidence đặt trong các thư mục này. Env, JWT, API key, tài khoản, SSH key, dump và private recovery key không vào Git.

Rollback image dùng `runtime-before.secret.env` của đúng host/release; Platform recreate `app web`, Domain recreate `api platform-sync scheduler` với Compose hiện có. Trước khi quay về P0/P2 phải kiểm tra các job/operation/approval được tạo từ P1; không hạ code khi job mới còn cần handler/recovery mới. Không tự downgrade SQL 0018/0019 hay phục hồi đè database khi hệ thống đã nhận dữ liệu mới. Xem [runbook vận hành](../../deploy/vps/P2_RUNBOOK.md) và [triển khai VPS](TRIEN_KHAI_VPS_CUNG_VINHOME.md).

Phần còn lại cần đầu vào/nghiệm thu riêng: UAT model thật với ngân sách và giới hạn call được chấp thuận; bảng giá provider để tính USD và đối soát hóa đơn; xử lý hợp đồng lịch sử phiếu cũ; kênh cảnh báo trực ban; thử tải, failover và kế hoạch nâng Ubuntu 20.04/scale khi có nhu cầu. Không tự nâng OS hoặc gọi lại eval trả phí trong đợt này.

Evidence riêng tư cục bộ: `.artifacts/release-p0p2-20261016/` chứa manifest, JUnit, acceptance evidence, smoke, dashboard, receipt và restore report; thư mục này được Git ignore. Các báo cáo P0/P1/P2 trước đây giữ nguyên nội dung lịch sử và trỏ tới bản bàn giao tích hợp này.
