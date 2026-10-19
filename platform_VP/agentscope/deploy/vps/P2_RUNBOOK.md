# Vận hành P2: usage, memory, backup ngoài VPS

Áp dụng cho `develop2`, Platform riêng `103.238.234.172`; Domain `103.238.235.156`.
Đọc cùng [runbook triển khai](README.md) và
[báo cáo P2](../../docs/workforce/BAO_CAO_HOAN_THANH_P2_2026-10-16.md).
Kết quả triển khai phải đối chiếu image ID và manifest; `2b9de30f-dirty` không
đủ phân biệt các lần sửa chưa commit. Không đưa env, JWT, key hoặc dump vào Git.

## 1. Nguồn cấu hình và dữ liệu

| Thành phần | Nơi lưu trên Platform |
| --- | --- |
| Compose, source đã triển khai | `/opt/awp-platform/app` |
| Env runtime, chỉ root đọc | `/opt/awp-platform/app/.env` |
| Release và manifest nguồn | `/opt/awp-platform/releases/p2-20261016`, `app/release.json` |
| Cấu hình offsite/monitor | `/etc/awp-platform/offsite.json`, `monitor.json` |
| SSH chỉ chuyển bản mã hóa | `/etc/awp-platform/backup_ssh`, `offsite_known_hosts` |
| Khóa age công khai | `/etc/awp-platform/recipients.txt` |
| Receipt, restore evidence, alert | `/var/lib/awp-platform/{offsite-receipt,offsite-restore,monitor}.json` |
| Bản gốc backup nhất quán | `/var/backups/awp-platform/<UTC>-awp-platform` |
| Bản mã hóa trên Domain | `/var/lib/awp-offsite/platform/*.tar.age`, `*.receipt.json` |

Agent/session/credential và ledger hiện dùng Redis; shared context, workflow,
route và auth dùng PostgreSQL. `model_call_ledger` cũng có implementation SQL,
được tạo bởi migration `0019_model_call_ledger`; không nhầm bảng SQL trống với
ledger Redis đang sử dụng. MinIO và workspace là hai kho còn lại cần khôi phục.

## 2. Ledger và giá chưa xác định

Mở trang Agent, chọn **Hoạt động và chi phí**. API cần token owner hiện tại:

- `GET /workforce/console/studio/observability?days=30`.
- `GET /workforce/console/studio/model-calls?since=<ISO UTC>&until=<ISO UTC>&limit=1000&offset=0`.
- Khi đi qua gateway web, thêm `/api` phía trước.

Export chứa từng attempt, request/response ID khi provider cung cấp, provider,
endpoint ID đã hash, model yêu cầu/model provider báo, tier thực tế nếu có,
purpose, owner/agent/session/team/workflow, token/cache, latency và trạng thái.
Không ghi prompt, output, API key hoặc raw HTTP header vào ledger.
Đối soát theo request/response ID với export provider; chưa có export hóa đơn
thì không ghi “đã đối soát hóa đơn”. Retry/fallback là những attempt riêng.

`started` chưa kết thúc vẫn hiện backlog; lỗi/hủy hoặc thiếu cache usage được
đánh dấu thiếu. Provider không báo tier thì `unknown`, không tự suy ra `standard`.
`cache_hit_ratio` là cached-input/input-token, không phải tỷ lệ request hit.
p50/p95 là thời gian attempt; chưa phải thời gian xử lý toàn phiếu.
Dashboard giới hạn 20.000 call và báo truncation; export API có phân trang.
Redis hiện đọc hash ledger của owner để lọc; khi tăng tải cần chuyển index/ledger
sang SQL hoặc kho phân tích trước khi lượng dữ liệu này lớn.

Theo quyết định của chủ dự án: chưa có giá endpoint thực tế, để
`deploy/vps/model-prices.example.json` là `{"prices":[]}`. UI ghi **Chưa xác định**,
API trả `null`, không mặc định giá model công khai hoặc coi call thiếu usage là 0 USD.

Khi có hợp đồng giá, tạo catalog riêng, chmod 600 và đặt
`WORKFORCE_PRICE_CATALOG_FILE=/absolute/path/catalog.json` trong `.env`, recreate
app. Compose mount read-only tại `/run/workforce/model-prices.json`.
Mỗi phần tử `prices` cần các trường:

| Trường | Yêu cầu |
| --- | --- |
| `provider`, `endpoint_id`, `model`, `service_tier` | Khớp chính xác ledger |
| `version`, `source`, `currency` | Phiên bản, nguồn hợp đồng, `USD` |
| `effective_from`, `effective_until` | ISO có timezone; không chồng khoảng; until tùy chọn |
| `input_per_million`, `cached_input_per_million`, `output_per_million` | Giá hợp đồng, số không âm |

Snapshot giá được lưu cùng terminal call, không đổi ngược call cũ khi sửa catalog.
Cache-creation có token nhưng chưa có cách tính tương ứng thì cost vẫn unknown.
`WORKFORCE_LEDGER_STARTED_AT` là thời điểm bật ledger lần đầu; giữ nguyên qua
deploy. Ticket có trước mốc đó hoặc thiếu call không được coi có tổng chi phí đầy đủ.
Chi phí trên successful ticket chỉ dùng close `resident_confirmed`; dừng theo dõi
không tính thành công. Tổng phần đã biết được ghi riêng với tổng đầy đủ.

## 3. Kiểm tra memory

TTL mặc định: fact 14 ngày, preference 30 ngày, lesson 90 ngày. Recall chỉ dùng
memory đúng owner/agent, còn hạn, active, provenance đạt policy v2 và content hash
khớp. Memory legacy chưa xác minh, ticket nguồn và record đã retire không được recall.
Mọi kind cần event thật thuộc task hiện tại; fact/lesson cần tool event của đúng
agent/session đã được xác minh. Preference cần customer message và kiểm tra khả
năng dùng cho ticket khác; thông tin riêng tư không được học vào bộ nhớ dùng chung.
Fact/preference cần nội dung trích được từ nguồn; lesson còn qua verifier ngữ nghĩa.
Verifier lỗi hoặc không có model thì không học. Model không có quyền sửa evidence ID.

Recall/outcome dùng CAS. `(memory, ticket)` chỉ tăng uses/outcome một lần; replay
không đổi TTL, không phục hồi record bị retire, outcome mâu thuẫn bị từ chối.
Một item xuất hiện trong ít nhất hai phiếu thất bại, nhiều hơn thành công, sẽ bị gỡ.
Provenance lưu source ticket/event IDs, evidence hash, verifier, TTL và supersession.

Chạy trên DB tạm, không trỏ DB thật:

```bash
PYTHONPATH=src:tests pytest tests/workforce_memory_safety_test.py tests/workforce_model_ledger_test.py --asyncio-mode=auto
PYTHONPATH=src python scripts/workforce/evaluate_memory.py \
  --cases tests/fixtures/memory_recall_heldout.json --output /tmp/memory-eval.json
```

Benchmark là ablation hồi quy có solver xác định: cùng câu hỏi, có/không recall
với gold evidence. Dataset đã dùng để điều chỉnh thuật toán, không coi là tập
nghiệm thu độc lập. Cần bổ sung tập giữ kín, câu hỏi paraphrase và ticket thực tế
được chấp thuận để đo outcome/cost/latency với cùng model, không memory vs có memory.
LLM verifier không thay việc kiểm chứng tri thức nghiệp vụ bởi người có trách nhiệm.

## 4. Tạo khóa và đích SFTP

Thực hiện trên máy recovery do người giữ khóa quản lý:

```bash
umask 077
age-keygen -o recovery.agekey
age-keygen -y recovery.agekey > recipients.txt
ssh-keygen -t ed25519 -N '' -f backup_ssh
```

Chỉ copy `recipients.txt` và SSH transport key lên Platform. **Không copy
`recovery.agekey` lên Platform hoặc Domain.** Giữ thêm một bản khóa tại nơi lưu
trữ độc lập có kiểm soát quyền truy cập; mất khóa thì không giải mã được backup.
Transport key không phải khóa giải mã. Source đang dùng age v1.1.1 từ
[release chính thức](https://github.com/FiloSottile/age/releases/tag/v1.1.1);
ghi hash binary/archive của bản cài, không coi HTTPS download là xác minh chữ ký.

Trên Domain tạo user `awp-offsite`, home `/var/lib/awp-offsite`, mật khẩu không
đăng nhập được; home, `.ssh` và `platform` quyền 700, authorized_keys quyền 600.
Dòng key công khai có ràng buộc:

```text
restrict,command="internal-sftp -d /var/lib/awp-offsite/platform" <transport public key>
```

User chỉ phục vụ SFTP, không cấp quyền ghi DB/volume/domain app. Cấu hình này
không phải chroot/immutable storage; root hoặc transport key bị chiếm có thể xóa
bản mã hóa. Cần bản sao thứ ba bất biến nếu yêu cầu chống ransomware hoặc mất cả
hai VPS. Hai VPS là hai host, chưa chứng minh hai vùng/provider độc lập.

Pin host key từ nguồn đã xác minh vào `offsite_known_hosts`; không tắt
StrictHostKeyChecking, không tin `ssh-keyscan` chưa đối chiếu. Tách hai object
trong [operations.example.json](operations.example.json) thành hai file config
đúng đường dẫn ở bảng trên, cập nhật environment và source revision.

## 5. Backup và upload

Không chạy cùng migration/onboarding hoặc tiến trình khác ghi trực tiếp DB.
Backup mặc định đóng gói thêm năm image chính xác, cache cục bộ theo bộ image ID
để tránh `docker save` lặp lại. Archive image vẫn được mã hóa trong mỗi backup;
dung lượng đích tăng hằng ngày, cần theo dõi và thống nhất retention trước khi đầy.
Không có lệnh tự xóa backup. `INCLUDE_IMAGES=false` bỏ phần image và cần có
release image độc lập đã kiểm chứng trước khi phục hồi mất toàn bộ source VPS.

```bash
cd /opt/awp-platform/app
DEPLOY_ENVIRONMENT=production-platform SOURCE_REVISION=<sha-or-sha-dirty> \
  bash deploy/vps/backup.sh awp-platform /var/backups/awp-platform
python3 deploy/vps/offsite.py upload-latest /var/backups/awp-platform \
  --config /etc/awp-platform/offsite.json \
  --evidence /var/lib/awp-platform/offsite-receipt.json
```

`COMPLETE` chỉ được tạo sau checksum manifest. Upload validate manifest trước
network, mã hóa age qua stream, chỉ gửi ciphertext+receipt qua SFTP, rename từ
`.part`, tải lại ciphertext để so SHA-256. Receipt `transfer_verified` chứng minh
truyền file; chỉ evidence restore PASS mới chứng minh giải mã và phục hồi được.

## 6. Khôi phục diễn tập từ offsite

Dùng máy recovery có age, Python 3.8+, Bash, SFTP và Docker CLI. Giữ receipt
tin cậy ngoài Domain để đối chiếu ciphertext; không chỉ tải cả backup lẫn receipt
mới từ một đích không tin cậy. Chuẩn bị config recovery trỏ transport key,
known_hosts và recipients vào đường dẫn cục bộ; cùng host/user/directory đích.

```bash
umask 077
mkdir -p /private/restore-work
python3 deploy/vps/offsite.py restore /private/offsite-receipt.json \
  --config /private/recovery-config.json --identity /private/recovery.agekey \
  --work-root /private/restore-work --evidence /private/offsite-restore.json
```

Có thể dùng `DOCKER_HOST=ssh://root@<isolated-recovery-host>` với root SSH key
và known_hosts cục bộ. Khóa age không đi lên Docker host; archive được giải mã ở
máy recovery, tar stream qua Docker SSH tới volume tạm. Script load image bundle
nếu có, khởi động PostgreSQL/Redis/MinIO trong container `awp-restorecheck-*`
không publish cổng, network none; không chạy app/model, không gửi lại ticket cũ.
Đối chiếu migration, số user/workflow/request, Redis key count, MinIO bucket,
workspace và checksum toàn bộ archive. Trap chỉ xóa container/volume tạm vừa tạo.
Xóa bản giải mã tạm tự động sau chạy; giữ evidence không chứa secret.

Khi phục hồi sự cố thật: dựng host mới, khôi phục bốn kho vào stack mới, restore
env/price catalog/TLS và image theo manifest, **chặn egress/job replay** tới Domain
trong lúc kiểm tra; kiểm tra auth, owner, route, pending operation trước khi mở
worker. Chỉ chuyển DNS sau smoke/UAT và có cửa sổ rollback. Script hiện tại là
diễn tập dữ liệu, chưa tự thực hiện production cutover hoặc chứng minh end-to-end
RTO từ lúc báo sự cố đến khi người dùng dùng lại được.

## 7. Lịch và cảnh báo

Sau khi upload và restore PASS, copy evidence restore về Platform, cài các unit
`awp-platform-{backup,offsite,monitor}.service`, `backup.timer`, `monitor.timer`
vào `/etc/systemd/system`. Tạo `/etc/awp-platform-backup.env` (600) có
`DEPLOY_ENVIRONMENT` và `SOURCE_REVISION` tương ứng. Sau đó:

```bash
systemctl daemon-reload
systemctl enable --now awp-platform-backup.timer awp-platform-monitor.timer
systemctl start awp-platform-monitor.service
systemctl list-timers 'awp-platform-*'
journalctl -u awp-platform-monitor.service -u awp-platform-backup.service --since today
cat /var/lib/awp-platform/monitor.json
```

Backup 03:30 Việt Nam hằng ngày, sau health check tự upload; monitor mỗi 5 phút.
Mục tiêu RPO 26 giờ, diễn tập restore <=3600 giây, evidence restore không quá 7
ngày, disk free >=20%. Đây là mục tiêu cấu hình, không phải SLA đã chứng nhận.
Alert gồm thiếu/quá hạn backup/offsite, checksum transfer không verified, restore
fail/quá hạn/chậm, disk low, health HTTP lỗi hoặc component báo lỗi trong HTTP200.
ALERT làm service exit 1 và ghi JSON+journal. **Chưa có kênh gửi email/chat trực
ban**; người vận hành phải đọc journal/giám sát unit hoặc gắn alert receiver được
phê duyệt. Diễn tập recovery cần người giữ khóa ít nhất mỗi 7 ngày.

## 8. OS và scale theo bằng chứng

Host Platform hiện báo Ubuntu 20.04; chưa nâng OS trong đợt P2. Trước lần chuyển
host cần kiểm tra tình trạng cập nhật/Ubuntu Pro thực tế và yêu cầu hỗ trợ của
Docker, Python, PostgreSQL. Ưu tiên host mới với bản Ubuntu LTS được đội vận hành
chấp thuận, restore rehearsal, canary, chuyển DNS, giữ host cũ để rollback;
không nâng OS trực tiếp khi chưa có cửa sổ và bản khôi phục đã kiểm chứng.

Đo CPU/RAM/disk/IO và p95 end-to-end khi load tăng; đặt ngưỡng từ baseline thực.
Tách worker/DB khi backlog tăng liên tục hoặc vượt SLO đã chốt. Trước scale app
nhiều replica: migration chạy một lần, dùng lock/CAS trên DB, kiểm tra outbox,
job lease và publish concurrency; các lock trong process không phải distributed
lock. Chuyển ledger Redis hash sang SQL có index/export theo lô trước khi cần
truy vấn lượng call lớn. Chưa có thử tải chứng minh năng lực/HA sau P2.
