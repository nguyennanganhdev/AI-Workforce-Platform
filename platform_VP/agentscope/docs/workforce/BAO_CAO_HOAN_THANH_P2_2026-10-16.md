# Kết quả P2-A/B/C — 16/10/2026

> Cập nhật bản tích hợp: [bàn giao Docker/VPS P0–P2 16/10/2026](BAO_CAO_BAN_GIAO_DOCKER_VPS_P0_P2_2026-10-16.md). P1 đã triển khai cùng P0/P2; phần dưới giữ bằng chứng tại thời điểm viết. UAT model thật chưa nghiệm thu; phiếu cũ thiếu hợp đồng được giữ và chặn xử lý tiếp.

P2 đã được triển khai lên VPS Platform, có kiểm tra source/image, migration,
API, dashboard, backup mã hóa ngoài VPS và khôi phục bốn kho dữ liệu. Chi phí
hiển thị **Chưa xác định** theo lựa chọn của chủ dự án. Call provider thật bị
chặn bởi **hết credit**; chưa xác minh call thành công hoặc đối soát hóa đơn.

Checkout `E:\AI-Workforce-Platform`, nhánh `develop2`, commit nền
`2b9de30f7aff05a72716f480efd10429ea134fb6`. Source sửa chưa commit/push.
Gói phát hành dựng trên P0 đã xác minh, bổ sung P2 và các phụ thuộc CAS/immutable
agent version. Không triển khai toàn bộ recovery/contract/sandbox P1 đang được
làm đồng thời; [báo cáo P1](BAO_CAO_KET_QUA_P1_2026-10-16.md) có phạm vi riêng.

## 1. Kết quả theo yêu cầu

| Hạng mục | Đã triển khai | Kiểm chứng và giới hạn |
| --- | --- | --- |
| P2-A: ledger | Ghi từng adapter invocation, gồm retry/fallback và structured output. Owner/agent/session/team/workflow/purpose, provider/endpoint/model/tier, request/response ID khi có, input/cache/output/reasoning tokens, latency, trạng thái | Test qua public model API và structured output: số SDK attempt bằng số call, không đếm đôi; SQL/Redis owner isolation, terminal immutable, stream/hủy/thiếu usage. Provider thật mới kiểm được nhánh hết credit |
| P2-A: summary/learning/eval | Purpose riêng cho runtime, private/shared/Builder summary, session title, Builder/copilot/plan, learning/consolidation, eval/judge; spec hash cho eval | Decorator scope giữ attribution cả lazy stream; workflow metadata truyền từ session Leader sang worker. Call chưa phân loại vẫn hiện `unclassified`, không tự gán vào runtime |
| P2-A: giá | Catalog chính xác provider+endpoint+model+tier, version/source và thời gian hiệu lực; snapshot lưu theo call | Không còn giá cứng theo model cuối. Catalog production rỗng; giá/usage/tier chưa biết không thành 0 USD. Giá test chỉ là fixture, không phải giá endpoint thật |
| P2-A: dashboard | p50/p95, failure/cancel, token cache ratio, pending calls, missing usage, unpriced calls, backlog ticket, nhóm model/tier/purpose, export từng call | Browser trên HTTPS thật PASS; export đúng owner, không page error. Inject token ngắn hạn ở refresh để kiểm UI; không kiểm lại luồng đăng nhập bằng mật khẩu |
| P2-A: cost/success | Chỉ close `resident_confirmed`; không tính stop-tracking. Ticket trước mốc ledger hoặc thiếu call có cost unknown | Test confirmed vs stop-tracking, missing ledger, unknown price, trước thời điểm coverage. Production hiện chưa có phiếu confirmed để tính |
| P2-B: replay/concurrency | CAS Redis/SQL cho memory; mỗi memory+ticket chỉ ghi uses/outcome một lần; opposite outcome bị từ chối | Replay và nhiều task đồng thời qua SQLite file, Redis và PostgreSQL; deterministic ID chống duplicate consolidation/TTL reset |
| P2-B: evidence | Mọi lesson/fact/preference cần nguồn thật đúng task/scope; verifier fail thì không học; fact/preference phải trích nguyên giá trị nguồn | Chặn invented event, wrong agent, thiếu evidence, model verdict false, injection/private data, số liệu không có nguồn; không bỏ từ phủ định dù model duyệt sai. Không coi LLM verifier là bảo đảm tuyệt đối về sự thật nghiệp vụ |
| P2-B: lifecycle | Provenance, content/evidence hash, verifier, source ticket/events, revision, TTL, retire/supersede | Fact 14 ngày, preference 30 ngày, lesson 90 ngày; hết hạn/retire/legacy chưa verify không recall; không recall lại vào ticket nguồn |
| P2-B: offline eval | Script ablation trên SQLite tạm, dataset hash, có/không memory, scope contamination check | 8/8 có memory, baseline 5/8, contamination 0 trong bộ mẫu. Đây là hồi quy đã dùng điều chỉnh thuật toán, chưa phải nghiệm thu giữ kín hoặc cải thiện business outcome thực tế |
| P2-C: vận hành | SFTP user riêng trên Domain, age encryption, host key pin, checksum trước upload và read-back sau upload; không gửi backup plaintext | Đã chuyển ciphertext và receipt. Khóa giải mã ở máy recovery cục bộ, ngoài cả hai VPS; kiểm tra thư mục cấu hình/release không có age private identity |
| P2-C: restore | Tải ciphertext từ Domain, giải mã cục bộ, load image bundle, phục hồi PostgreSQL/Redis/MinIO/workspace vào container/volume tạm | Bản P2 migration 0019 PASS trong **270,008 giây** gồm download/decrypt/load/restore; không chạy restored app/model, không production cutover |
| P2-C: lịch/alert/docs | Backup 03:30 Việt Nam, monitor 5 phút, alert JSON+journal, RPO/RTO mục tiêu, config map/runbook/research/checklist | Đã bật timer và chạy monitor PASS. Chưa có email/chat trực ban, chưa tự nâng OS, chưa thử tải/HA |

## 2. Bằng chứng phát hành

| Thành phần | Bản đang chạy |
| --- | --- |
| Môi trường | `production-platform`, `https://vagen-platform.duckdns.org` |
| App image | `agentscope-platform:2b9de30f-p2-20261016-2` |
| App image ID | `sha256:102273950ae6d1641ce1d487a4b38c09e71ce18150fa5c59c638d494c0fec806` |
| Web image | `agentscope-platform-web:p2-20261016-2` |
| Web image ID | `sha256:209d319c6ee481ba91da760462a809eef5d620529e23b661ed111293c5314e59` |
| App manifest SHA-256 | `967d007986d4eb6ad45bde822003a63efce8c2c4f8b0d903bf384ad96e08f6be` |
| Web manifest SHA-256 | `7096e2f9c734c813364258334030b1dbc4b2aae5242d789b1024ada7f07ea78e` |
| Ops manifest SHA-256 | `1460db686fd351bcd71a2845a7036526e7eaac23a2324bb737bd7d3b8e4d153b` |
| Đối chiếu trong container | **848** file ứng dụng/script, **0** mismatch |
| Đối chiếu host vận hành | **13** file, **0** mismatch |
| Migration PostgreSQL | `0019_model_call_ledger` |
| Mốc bật ledger | `2026-10-16T07:33:50.636888+00:00` = **14:33:50 Việt Nam** |
| Domain app | Giữ image `vinhomes-domain-api:p0-20261016-2b9de30f`; chỉ thêm vùng nhận offsite riêng |

Manifest nguồn gồm 864 file đóng gói; 848 file source/script được đối chiếu
trong app, phần Compose/ops có nguồn xác minh riêng. Ops và web cập nhật sau app
được ghi bằng manifest riêng; không dùng commit nền để giả định mọi file đã commit.
Canonical `app/release.json` đã được đồng bộ, thay metadata phát hành cũ.

## 3. Database/runtime trực tiếp

Snapshot sau deploy; chốt evidence ngày 16/10/2026 theo giờ Việt Nam:

| Dữ liệu | Số lượng/trạng thái |
| --- | --- |
| Auth users | 13 |
| Workflows | 1, `awaiting_user` |
| Partner requests | 2 |
| Unified operations | 0 |
| Unified approvals | 0 |
| Route active OP1/OP2/OP3 | 3, mỗi route readiness PASS với 4 agent |
| SQL `model_call_ledger` | 0, vì primary agent storage đang dùng Redis |
| Redis ledger | 1 attempt `eval`, thất bại, đúng owner OP2 |
| Confirmed successful ticket trong cửa sổ | 0 |

Call smoke dùng `gpt-5.4` theo cấu hình primary session, trả APIError hết credit
sau **3325,273 ms**. Ledger ghi `failed`, input/cache/output `null`, tier
`unknown`, không request/response ID từ provider, cost `null`. Lần gọi này không
thực hiện tool hoặc thay đổi ticket nghiệp vụ. Call được giữ sau restart/backup;
API và UI đọc lại cùng evidence. Failure 100% trên dashboard hiện chỉ là **mẫu
1 call smoke**, không phải thống kê lỗi ticket đã xử lý.

API observability và export trả 401 khi chưa xác thực. Với từng token BQL,
export chỉ chứa owner đó; hai BQL còn lại chưa có call ledger và tổng cost vẫn
unknown. Cả ba đội vẫn readiness PASS; không dựng lại preset hoặc đổi roster.

## 4. Test và UI

| Bộ kiểm tra | Kết quả |
| --- | --- |
| Snapshot P2 cuối: memory/ledger/ops, Studio/sandbox/publish, tools, OpenAI Chat/Responses | **190 passed**, 2 subtests; `final-tests.xml` |
| Phụ thuộc agent version/CAS trên snapshot P2 | **3 passed**; `agent-cas-tests.xml` |
| Migration từ DB trống với pgvector/PostgreSQL | PASS đến `0019_model_call_ledger` |
| TypeScript/Vite và ESLint của web phát hành | PASS |
| Browser dashboard/export trên VPS | PASS; `browser.json`, `dashboard.png` |
| Mô hình thật thành công, invoice reconciliation | **Chưa đạt: provider hết credit; chưa có giá/export hóa đơn** |

Suite 190 có parametrization chạy memory/ledger trên PostgreSQL thực, Redis
và SQLite; không cộng các lượt chạy lại để tăng số test. Các kiểm tra trước đó
trên workspace rộng có 207 pass nhưng không thay bằng chứng snapshot P2 cuối.
Không tuyên bố toàn repo/CI, E2E ticket thật hoặc P1 production đã nghiệm thu.

## 5. Backup offsite và restore

| Bằng chứng | Kết quả |
| --- | --- |
| Đích được chủ dự án chọn | Domain VPS `103.238.235.156:/var/lib/awp-offsite/platform` |
| User/permission | `awp-offsite`, forced internal SFTP, thư mục 700, ciphertext/receipt 600 |
| Bản đã restore | `20261016T081104Z-awp-platform` |
| Artifact đã restore | `20261016T081104Z-awp-platform-21860f63.tar.age` |
| Ciphertext SHA-256 | `fa9700015bb528fa1ec0369114552aea2a6aecd8da5eb8f0b4a4db5c2e1bedf4` |
| Dung lượng ciphertext | **602.761.080 byte** |
| Backup nhất quán, cache image đã có | **10,671 giây**; không gồm thời gian ứng dụng khởi động lại/health |
| Mã hóa/upload/read-back | **39,157 giây** |
| Tổng download/decrypt/image load/restore | **270,008 giây** |
| Restore phase gồm image load và dữ liệu | **201,694 giây** |
| PostgreSQL | Migration 0019 và count users/workflows/requests khớp |
| Redis | Khởi động được, DBSIZE khớp |
| MinIO | Khởi động được, bucket hiện hữu |
| Workspace | Archive checksum khớp, giải nén vào volume riêng |
| Production cutover | **Chưa thực hiện**, không gửi lại workflow cũ |

Image bundle chứa năm image app/web/PostgreSQL/Redis/MinIO chính xác; backup
còn giữ env runtime/giá, Compose, TLS khi có, release metadata và ba manifest,
cấu hình offsite/monitor/public recipients/known_hosts, script và runbook.
Test restore dùng Docker SSH tới host có engine và tài nguyên tạm, load bundle
từ backup; chưa phải thử mất toàn bộ VPS rồi chuyển DNS sang host mới.

RPO đặt **26 giờ**, backup mỗi ngày **03:30 Việt Nam**. RTO diễn tập đặt **3600
giây**, restore evidence không quá **7 ngày**, disk free ít nhất **20%**. Lần
diễn tập này nằm trong ngưỡng; không suy ra SLA hoặc production cutover RTO.
Monitor đã PASS, không alert ở lần kiểm; timer hoạt động. Chạy cả unit backup
thực tế đạt `Result=success`, `ExecMainStatus=0`, upload tự động PASS. Alert chỉ có JSON và
systemd journal, chưa có notification trực ban. Retention không tự xóa backup;
mỗi bản kèm image khoảng 603 MB, cần ngân sách dung lượng/retention riêng.

Khóa giải mã nằm tại `.artifacts/p2-20261016/recovery.secret.agekey` trên máy
Windows, bị Git ignore, ACL chỉ user hiện tại và SYSTEM. Không in nội dung khóa.
Owner cần lưu thêm bản khóa ngoài máy này; hiện chưa chứng minh có bản custody
thứ hai. SSH transport key trên Platform chỉ dùng SFTP, không giải mã được.

## 6. Những việc cần dữ liệu/điều kiện tiếp theo

| Ưu tiên | Công việc | Điều kiện hoàn tất |
| --- | --- | --- |
| Ngay khi có credit | Chạy lại eval/summary/learning/judge bằng provider thật, export IDs+usage, kiểm cache thực | Provider không còn quota error; đối chiếu token và request/response ID, không tạo side effect nghiệp vụ |
| Khi có hợp đồng giá | Nạp catalog versioned theo endpoint/tier/ngày hiệu lực; đối chiếu export provider | Có giá được chủ dự án cung cấp và hóa đơn/export; không hồi tố sửa terminal call |
| Sau sandbox/UAT | Tập memory giữ kín và ablation cùng model trên ticket được chấp thuận | Đo correctness, contamination, cost, latency và outcome; có đối chứng không memory |
| Vận hành tuần | Người giữ khóa diễn tập offsite restore mỗi tối đa 7 ngày, lưu receipt+evidence độc lập | Đúng SHA/môi trường, đủ bốn kho, giải mã được; diễn tập cutover riêng khi có host dự phòng |
| Vận hành trước tăng dung lượng | Chốt retention/ngân sách và kênh trực ban; thêm bản bất biến nếu cần chống xóa/ransomware | Không để đầy disk; cảnh báo đến người trực; backup ngoài hai host khi yêu cầu độc lập failure domain |
| OS | Chuyển sang host Ubuntu LTS còn hỗ trợ, restore/canary trước DNS cutover | Backup đã kiểm, app/Domain acceptance, cửa sổ rollback; không nâng trực tiếp VPS đang phục vụ |
| Scale | Đo p95 end-to-end/backlog/CPU/RAM/IO, index ledger hoặc chuyển SQL trước khi owner hash lớn | Chốt SLO và load gate; distributed concurrency/migration/lease kiểm được trước nhiều replica |

Host Platform kiểm trực tiếp: **Ubuntu 20.04**, kernel `5.4.0-29-generic`,
4 CPU, khoảng 3,84 GiB RAM, Ubuntu Pro `attached=false`. Ubuntu 20.04 hết
standard security maintenance tháng 5/2025; cần ưu tiên xử lý vòng đời host.
[Nguồn Ubuntu](https://ubuntu.com/about/release-cycle).
Ubuntu 24.04 nằm trong danh sách Docker Engine hỗ trợ hiện tại; đề xuất dựng
host 24.04 mới và restore/canary, chưa thực hiện mua host hoặc nâng OS.
[Nguồn Docker](https://docs.docker.com/engine/install/ubuntu/).

Các giới hạn kỹ thuật còn công khai: Redis ledger đọc toàn hash owner để lọc,
dashboard cap 20.000 call; chưa có retention/index phân tích. Recording-failure
counter là chẩn đoán process-local, không phải chứng minh ledger không mất sự
kiện qua mọi sự cố. Historical usage không backfill. LLM verifier và lexical
recall có thể false negative/false positive ngoài bộ mẫu; background learning
hiện chưa được biến thành hàng đợi durable bởi P2. Hai VPS chưa chứng minh khác
region/provider; forced SFTP chưa phải chroot hoặc immutable object lock.

## 7. Handoff

Quy trình cấu hình, chạy, export, giá, TTL, khóa, restore, alert và OS/scale tại
[P2_RUNBOOK.md](../../deploy/vps/P2_RUNBOOK.md). Các research/checklist/runbook cũ
đã thêm liên kết phân biệt snapshot lịch sử và trạng thái P2.

Bằng chứng cục bộ: `platform_VP/agentscope/.artifacts/p2-20261016/` gồm
`final-tests.xml`, `agent-cas-tests.xml`, `source-manifest.json`,
`web-source-manifest.json`, `ops-manifest.json`, `release.json`,
`p2-live-verification.json`, `browser.json`, `dashboard.png`,
`memory-recall-result.json`, `offsite-receipt.json`, `offsite-restore-current.json`,
`final-verification.json`, `closeout.json`.
Thư mục này cũng có secrets: chỉ chia sẻ file evidence đã chọn, không đóng gói
nguyên thư mục. Remote evidence tại `/opt/awp-platform/releases/p2-20261016`
và `/var/lib/awp-platform`. Source P2 chưa commit/push; giữ nguyên WIP P1/Domain.
