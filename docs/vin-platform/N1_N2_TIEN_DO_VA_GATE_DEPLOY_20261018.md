# Tiến độ ghép hai người và điều kiện lên staging/VPS — 18/10/2026

Owner tài liệu: Người 1, đối chiếu trực tiếp Git, handoff, log/XML và image local. Chủ dự án đã chọn **staging trước, rồi VPS**. Chưa dùng key model thật; chưa cập nhật stack đang phục vụ hay dữ liệu ứng dụng thật.

## Đã khớp đến đâu

Root `E:/AI-Workforce-Platform` vẫn là `dev_Chien@e7b80da6`, nên handoff mở ở root là snapshot cũ. Bản N1 hiện hành nằm `E:/AI-Workforce-Platform-user1`. N2 tại thời điểm kiểm tra là `e6fd5cb6`, đã nhập C07/C09 và cả N1 `bccbc8e7`/`6ef348ce`; consumer/RC còn WIP riêng, không sửa hoặc commit hộ N2.

| Phần | Producer N1 | Consumer/kiểm chứng N2 | Còn lại |
| --- | --- | --- | --- |
| Admin N2-08 | Read/write + CAS/revision, privacy KB, OpenAPI/fixture; migration 0024 | Admin journey và PG tests đã PASS | Chốt source RC cuối và kiểm image admin flow |
| C07 phương án riêng | `43897e9b`: safe plans, plan version riêng, signed decision/ACK hash | UI approve/reject plan đã có, hai ca journey PASS | Commit consumer và chạy đúng image RC cuối |
| C09 >100 jobs | `d4a25cd0`, bổ sung `bccbc8e7`: source filter trước LIMIT, direct get, saved/current revision | Đã merge; paged UI/history/repair có test mới | Nối get/source filters ở caller còn quét list; kiểm lại repair trên source cuối |
| Leader evidence | Receipt server-owned từ C05 là nguồn dữ liệu | `065c231e` đã sửa đúng owner/agent/session/reply, giữ team/Shared Context | Đã có source tests; chốt lại browser RC từ source cuối |
| Domain staff/case | Consent/link, case/ticket, progress/photo/decision/closure; 0 BQL commands | Browser-link/HTTP-link cùng vòng đời đã PASS | Whole Platform+Domain candidate image run và UAT nghiệp vụ |
| Lịch/Discord/Builder | Durable SQL queue, lease/fencing/checkpoint, quota/context | Journey Builder/eval/publish và once/Discord/saved delivery PASS bằng fixture | Không suy bot/OAuth/model thật từ fixture; UAT riêng |
| M2 chatbot | Guard/cohort API, compose flag wiring; mặc định false | Chưa cutover UI/cohort | Giữ off đến sau pilot/sign-off; staff Domain giữ nguyên |

## Bằng chứng mới trong lượt này

Không cộng các suite giao nhau thành tổng coverage:

- N1 C09 trên Python 3.11 Linux: **15 PASS / 0 SKIP / 0 FAIL / 0 ERROR**. Bao gồm SQLite + PostgreSQL migrate 0024, lọc 125 job nguồn B sau 125 job nguồn A, owner thứ hai, cursor sai filter, lookup sau 100 job, revoke/restore và delivery prefix escape.
- Nghiệm thu ghép trên Windows bắt lỗi **test expected theo enqueue**, không phải production keyset. Sửa riêng tại **`c1a8acd84dc0b04ba8b996528d3fa9ba98e69077`**: cố định timestamp trùng để tái hiện RED 1 FAIL, expected theo (created_at,job_id), giữ 125 ID duy nhất + lookup target + revoke. Chạy lại **Windows 15 PASS / 0 SKIP** và **Linux 15 PASS / 0 SKIP**, 0 FAIL/ERROR, gồm PG/SQLite. Đây là lượt kiểm lại suite C09, không cộng vào 15 PASS cũ.
- N2 S15 log đã đọc: **89 contract PASS**, **26 browser PASS**, **10 PostgreSQL PASS**, **7 browser/runtime journey PASS**, tất cả 0 SKIP/FAIL/ERROR. Journey gồm admin, Builder, automation, approve/reject plan và hai biến thể customer flow. Domain/IdP/model trong harness có fixture; chưa coi đây là whole production-image RC.
- N2 runtime tổng hợp gần nhất trước S15: **501 PASS / 25 SKIP**; 25 SKIP là 24 browser + 1 PG concurrency cần chạy riêng. Không sửa con số lịch sử thành PASS vì các suite riêng đã chạy.
- C10 chạy lại trên source **`2ce926e3`** và schema head hiện tại 0024: **4/4 store PASS, 0 store SKIP**. Kiểm fingerprint/semantics PostgreSQL, Redis values/TTL, MinIO bytes và workspace/Qdrant. Đây là restore dữ liệu giả isolated, không phải off-host restore hoặc restore production. Source/restore containers và volume fixture đã dọn.

## Docker đã đóng gói gì

**Domain candidate đã có:** `vinhomes-domain-api:vin-n1-6ef348ce-rc-20261018`.

- Source revision `6ef348ce1ef51c5f1002218ccff4e7be43f8e273`.
- Image ID `sha256:37573253b6bb2a52b47a922fb42e6858d8a2b97be80efc392beff990b63a41e0`.
- Package PASS: pip check, 128 file Python/SQL match source, UID 10001, production CMD; 0 .env/secret/artifact files trong app image.
- Runtime **1 scenario PASS** bằng chính production CMD, không mount source app: ready → resident password → consent/PKCE/token/grant → owner profile; legacy intake vẫn mở, M2 off. Helper chỉ migrate DB UUID fixture, không DB ứng dụng, 0 model call; API/DB smoke đã dọn.
- Compose Domain nay truyền cờ customer/M2 từ env operator, defaults false/false/[]; không sửa deployment.env thật. Test config customer false/true giữ M2 off PASS.

**Platform app/web:** N2 đã build candidate từ `9a5bc750`, pip check và hash 716 file Python đạt. RC1 chạy customer/image/receipt/zero-BQL đạt nhưng whole runner **FAIL** ở xác minh JWT admin/cleanup fixture. N2 đã sửa fixture; chưa thấy whole RC mới PASS trên source chứa consumer C07/C09 cuối, nên image cũ không phải bundle release cuối.

## Công việc tiếp theo, theo thứ tự

1. **N2:** commit WIP consumer/RC và nhập helper runtime N1 nếu dùng; chuyển source-filter/get vào ledger/repair/publish caller, chạy lại tests với contract thật. **N1:** hỗ trợ mismatch producer, giữ một owner mỗi file.
2. **Hai người:** pin integration SHA sạch chứa hai lane; build Platform app/web production từ SHA đó, giữ Domain candidate đã có bằng image ID và source revision riêng. Manifest phải ghi source/image ID, build args Vin/API, migration order và flags; không đóng gói .env/secret/artifact.
3. **N2 chủ trì, N1 Domain/data:** chạy RC trên image thật, normal CMD, không bind app source: signup → Domain password/consent → Leader → staff Domain → ảnh/tiến độ → explicit resident decisions → canonical close, thêm admin/plan/125-job repair/Builder/lịch/kênh. Lỗi của runner cũng phải sửa/rerun; chỉ ghi whole RC PASS khi mọi scenario đạt.
4. **Staging Docker local cách ly:** dùng fixture/provider scripted, DB/volume riêng, callback/link allowlist riêng, cờ Vin bật có chủ đích, **M2 off**. Mở để chủ dự án review; giữ nguyên stack/VPS đang phục vụ. Ghi image manifest, health/browser smoke và rollback về image/flag cũ.
5. **Trước VPS:** xác minh URL/compose project mục tiêu, schema đang chạy, backup hiện hành đủ kho + Domain DB/files, exact consent redirect/issuer, secrets/quotas/catalog/eligibility của pilot, auth/proxy/cookie và phương án rollback. Sau staging đạt và UAT ký nhận mới cập nhật VPS từng bước; kiểm staff/legacy, case mới và khả năng rollback. Không tắt chatbot theo cohort cùng lúc deploy lần đầu.

Việc cần làm riêng trước pilot có ảnh đầu vào: proxy upload ảnh thuộc đúng cư dân, quota/profile vision và consumer attachment. **Ảnh kết quả staff đã kiểm được; phân tích ảnh đầu vào chưa hoàn tất.** Tài liệu Vin thật/indexing và model/business UAT cũng chưa được chứng nhận từ fixture. Có thể kiểm staging phạm vi text + ảnh kết quả hiện tại; không công bố full pilot có vision trước khi các phần này đạt.

## Khi nào có thể đưa lên

**Đóng gói đang thực hiện ngay:** Domain đã build và kiểm xong; Platform cần rebuild sau khi N2 commit consumer cuối. **Mở staging chung sau whole RC cuối PASS và manifest chốt.** Không cần đợi mở Vinpearl/VinWonders để nghiệm thu staging Vinhomes.

**VPS sau staging/UAT và preflight đích đạt**, theo lựa chọn của chủ dự án. Chưa chốt một giờ deploy vì RC image cuối chưa PASS và URL/stack VPS chưa được xác minh trong lượt này. PASS health/offline/restore fixture không thay chữ ký nghiệm thu nghiệp vụ.

## Chạy lại và vị trí bằng chứng

- [C07/C09 contract + caller examples](N1_C05_C07_C09_CONSUMER_HANDOFF.md).
- [Migration/config và Domain package/runtime commands](N1_MIGRATION_CONFIG_RUNBOOK.md).
- [Docker E2E](N1_DOCKER_E2E_RUNBOOK_20261018.md), [M2 off/cohort runbook](N1_M2_DOMAIN_COHORT_RUNBOOK.md).
- N1 artifact `P/.artifacts/n1-r05/`: `c09.xml`, `domain-image-final/domain-package.json`, `domain-runtime-final3/domain-runtime.json`, `c10-head-0024/deep-restore.json`. Các lần smoke fixture sai surface/path trước đó vẫn là FAIL; đã sửa helper, không nới auth production.
- N2 log: `n2-s15-{contracts-final,browser-final,postgres,journeys}.log`; source S15 đang WIP ở lúc đọc, không suy provenance RC clean SHA từ các log này.
- [Evidence sanitized R05](evidence/n1-r05-20261018.json). Không chứa DSN/key/cookie/intent raw hoặc dữ liệu khách thật.
