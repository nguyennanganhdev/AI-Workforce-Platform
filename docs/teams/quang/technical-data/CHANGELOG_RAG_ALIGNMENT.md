# Nhật ký căn chỉnh technical-data với RAG Q03/Q04/Q06

Ngày thực hiện: 2026-10-05. Nhánh làm việc: `dev_TeamQuang_ddhung04`.

## Đã đối chiếu thiết kế

- Q03 (`source-directory.ts`, `markdown.ts`, `ingest.ts`, `source-metadata.ts`): đầu vào thực là cây Markdown, YAML front matter và mục `Nguồn`; DB tự sinh document/version/chunk ID, gắn scope theo đường dẫn và tự đặt document đã ingest ở trạng thái `published`.
- Q04 (`retrieve.ts`, `contract.ts`): tìm kiếm có tenant/ACL/scope trước ranking; citation chứa source và cờ `unverified`. Front matter **không** phải hàng rào phân quyền.
- Q06 (`eval-metrics.ts`, `eval.ts`): dataset gồm `version/cases`, mỗi case có `id/scope/query/expect/contains/tags`; `contains` là đoạn văn bản chứ không phải chunk ID. Runner hiện gắn với KB/fixture dev Ocean Park.
- Đã merge `origin/dev_TeamQuang` vào nhánh dữ liệu để đối chiếu với code RAG mới. Merge chỉ ở local, chưa push.

## Thay đổi dữ liệu

1. Tạo `rag/corpus/01-vinhomes/` với 16 Markdown, mỗi tài liệu ứng với một mã vấn đề trong `general.md`. Mỗi file có metadata `issue_code`, `approval_status=not_published`, `sop_available=false`, `audience=internal_poc`, yêu cầu snapshot nguồn trước production; thân bài chỉ là nhận diện/triage tham khảo, không được gọi là SOP Vinhomes. Mục `Nguồn` giữ URL, fact ID và vị trí nguồn để chunker đưa vào citation.
2. Thay `RAG_CHUNKS.jsonl` ở thư mục gốc bằng `rag/RAG_DOCUMENTS.jsonl` (16 bản ghi). Đây là manifest biên tập với `document_code` ổn định, đường dẫn Markdown, scope, issue, nội dung và provenance. Không dùng `A2-DOC-*` như ID DB hoặc nạp JSONL này thành bảng chunk.
3. Chuyển và sửa `RAG_EVAL.jsonl` thành `rag/RAG_EVAL.jsonl`: 23 case cũ đổi sang shape Q06; bỏ `expected_chunk_ids` không ổn định, thay bằng `expected_document_codes`, `contains` và các trường an toàn A2. Thêm 1 ca `trap` khác đơn vị vận hành; hiện có 16 `answer`, 5 `no_data`, 2 `off_topic`, 1 `trap`.
4. Tạo `rag/eval/technical-a2.v1.json` với 24 case theo `EvalDataset` để dùng cho runner Q06 khi có KB A2 riêng. Các trường an toàn mở rộng vẫn ở JSONL vì Q06 hiện chỉ chấm retrieval/ACL, chưa chấm câu trả lời của agent.
5. Giữ `*_FACTS.jsonl`, source register/manifest, 10 ca công khai và 32 ca giả lập ngoài corpus ingest. Không nâng fact tham khảo hoặc tình huống giả lập thành ticket/SOP thật.

## Thay đổi code và tài liệu

- `server/src/knowledge/source-metadata.ts`: tài liệu có `approval_status=not_published` nay mang `chua_xac_minh=true` dù thuộc nhánh Vinhomes; giữ nguyên quy tắc Masterise. Bổ sung test tương ứng trong `server/tests/knowledge/source-metadata.test.ts`.
- `server/src/knowledge/contract.ts`, schema handoff và handoff Q04: làm rõ cờ `unverified` gồm tài liệu tham khảo chưa xuất bản, không chỉ Masterise.
- Viết lại `RAG_INGESTION.md` theo hợp đồng Q03/Q04/Q06: root ingest chính xác, KB/grant nội bộ, citation, eval, hạn chế CLI `prune=true` và các điều kiện còn thiếu để production. Cập nhật `README.md` và `VN_COVERAGE_AND_GAPS.md` để không hướng dẫn ingest JSONL cũ.
- `validate_data.ps1`: kiểm tra JSONL, 16 mã sự cố, file Markdown và manifest khớp nhau, title/front matter/source ID/fact/location/URL, nhãn chưa xuất bản, nguồn, số lượng corpus và parity giữa JSONL eval với JSON Q06.

## Đã kiểm tra

- Chạy `powershell -NoProfile -ExecutionPolicy Bypass -File docs/teams/quang/technical-data/validate_data.ps1`: **Validation OK**; 16 issue, 74 source, 77 fact, 16 RAG document, 10 ca công khai, 32 ca giả lập, 24 eval.
- Kiểm tra không còn tham chiếu `RAG_CHUNKS.jsonl` hoặc `expected_chunk_ids` trong code/tài liệu hiện tại; `git diff --check` không báo lỗi khoảng trắng.
- Chưa chạy Bun unit test, preview chunker hay eval retrieval vì môi trường hiện không có Bun và dependencies. Chưa ingest vào DB, chưa đo recall/MRR/độ rò dữ liệu A2; không dùng chỉ số Ocean Park thay thế. Không push/triển khai.

## Rủi ro và việc còn thiếu

- Q03 tự publish tài liệu sau ingest, nên nhãn `not_published`/`unverified` chỉ cảnh báo, **không khóa truy cập**. Chỉ ingest vào knowledge base riêng có grant nhân viên/test; tuyệt đối chưa cho Reception/cư dân hay `sop_kb.retrieve` dùng.
- 16 tài liệu chỉ đủ thử retrieval triage, không có quy trình xử lý sự cố đã được BQL Vinhomes phê duyệt, không có SLA/giá, mapping tòa/asset/model, ticket → work order → evidence → outcome đã xác minh. `source_snapshot`/hash/quyền toàn văn của nhiều nguồn ngoài vẫn chưa hoàn chỉnh.
- Cần fixture/KB A2 riêng để chạy Q06; cần test riêng cho `expected_human_escalation` và `forbidden_claims`. Sau đó hiệu chỉnh threshold trên câu hỏi A2 thật trước khi đưa vào sử dụng.

## Bổ sung 2026-10-05: quy trình và lifecycle giả lập

Theo yêu cầu hoàn thiện dữ liệu để xây POC, đã rà lại Q03/Q04/Q06, `general.md`, `tools.md`, `POC_WORKFLOWS.md`, `COLLECTION_SPEC.md`, thiết kế Q07/Q08 và các contract/fixture trong `server/src/technical-tools`. Không có SOP hay ticket Vinhomes đã xác minh trong các nguồn hiện có, vì vậy **không giả mạo nguồn thật**.

1. Tạo 16 file `rag/mock-corpus/01-vinhomes/quy-trinh-gia-lap-a2-*.md`. Mỗi file chứa intake, dấu hiệu phải dừng/chuyển người, dữ liệu và quyền cần kiểm, luồng work order, evidence và kiểm chứng riêng cho một issue. Tất cả có `fixture_only=true`, `approval_status=not_published`, `sop_available=false`, `trang_thai=du-lieu-gia-lap-khong-xuat-ban`, `van_ban=MOCK-PROC-*`. Folder này tách hẳn khỏi root ingest tham khảo `rag/corpus`.
2. Tạo `rag/mock/PROCEDURE_PROFILES.jsonl`: 16 profile `draft` cùng `document_code`, issue, version, audience kỹ thuật viên, điều kiện áp dụng/chống chỉ định/dừng và tiêu chí `checklist/evidence/manual` theo kiểu `AcceptanceCriterion`. Năm profile POC liên kết work order giả lập; 11 profile khác để `source_work_order_id=null`, chưa đủ cho pipeline học từ ticket Q07.
3. Tạo `rag/mock/POC_LIFECYCLE.jsonl`: 5 chuỗi giả lập theo đúng năm POC, có scope/UUID fixture, ticket và fact provenance, assessment, asset, work order/assignment, evidence, measurement khi phù hợp, trạng thái submit/verify kỳ vọng và tối thiểu ba biến thể lỗi mỗi ca. Không đưa số đo mẫu thành ngưỡng an toàn, không dựng giá/SLA hoặc kết quả sửa chữa Vinhomes.
4. Tạo `rag/mock/eval/technical-a2-mock.v1.json`: 16 câu `answer`, một `off_topic`, một `trap` để thử retrieval riêng. Câu hỏi về an toàn/forbidden claims nằm ở expected của POC JSONL, không ép vào loại `off_topic` của Q06 vì Q06 chỉ chấm retrieval.
5. `source-metadata.ts` giờ đánh dấu `unverified` cả khi `fixture_only=true`; cập nhật test, mô tả contract, schema bàn giao và handoff. Không thêm trường API mới; `collectionStatus` và tiêu đề MOCK cho biết tính giả lập, nhưng ACL/KB vẫn phải cô lập.
6. Mở rộng `validate_data.ps1` kiểm tra 16 Markdown/profile, nhãn không xuất bản, citation fixture, điều kiện/tiêu chí, liên kết năm work order/POC, provenance measurement/evidence và 18 eval `contains`. Cập nhật `README.md`, `RAG_INGESTION.md`, `POC_WORKFLOWS.md`, `COLLECTION_SPEC.md`, `TOOL_DATA_MATRIX.md`; tạo `rag/mock/README.md` hướng dẫn tích hợp.
7. Tạo `rag/mock/Q07_LEARNING_FLOW.jsonl`: hai candidate procedure từ work order giả lập (một draft chỉ cho kỹ thuật viên, một đề xuất resident bị từ chối) và một eligibility test không tạo self-help attempt/không bịa giá khi không có procedure published hoặc cost observation verified. Validator kiểm tra các liên kết và trạng thái an toàn này.
8. Tạo `rag/mock/TOOL_DATA_FIXTURES.jsonl` với 16 bản ghi giả lập bổ trợ cho các adapter: sensor fresh/stale/bad, maintenance scheduled/pending/correction, interruption proposed/notified/cancelled/active khác tòa, approval request pending, vendor chưa booking và một cost observation draft phải loại khỏi tính giá. Validator kiểm tra freshness, scope, liên kết asset/work order/ticket, trạng thái và phép cộng tiền. Cập nhật ma trận 14 tool để phân biệt fixture đã có với dữ liệu vận hành còn thiếu.

Rà file dư: `RAG_CHUNKS.jsonl` cũ đã bị loại vì Q03 tự sinh chunk/UUID; eval JSONL và JSON còn được giữ vì JSONL có expected an toàn A2 mà runner Q06 không hiểu, JSON là input Q06. Ba nhóm fact/source register, public cases và synthetic/edge cases được giữ **ngoài corpus ingest** vì chúng có mục đích provenance hoặc regression riêng, không phải duplicate SOP. Không xóa dữ liệu nguồn chỉ để giảm số file.

Validator sau bổ sung: **Validation OK**, 16 issue, 74 nguồn, 77 fact, 16 tài liệu tham khảo, 16 quy trình mock, 5 POC lifecycle, 5 trace nhiều lượt, 3 fixture Q07, 16 tool-data fixture, 80 ca có nhãn, 18 mock eval, 24 eval tham khảo. Chưa chạy Bun/DB/embedding/retrieval vì môi trường không có Bun/dependencies; chưa push.

## Bổ sung 2026-10-05: tình huống có nhãn để thử huấn luyện

Theo phản hồi rằng bộ mock quá ít/ngắn, đã thêm `rag/mock/SUPERVISION_CASES.jsonl` với 80 ca (mỗi mã sự cố có ca thường, nguy hiểm, thiếu thông tin, mâu thuẫn và hồ sơ nghiệm thu). Mỗi ca có lời báo giả lập, facts/unknown, route, câu cần hỏi, kế hoạch tool, câu trả lời mục tiêu, forbidden claims và source fixture. Split cố định: 48 train, 16 dev, 16 test. `validate_data.ps1` kiểm tra phủ đủ 16×5, ID không trùng, split, route hazard/unknown/conflict/closeout, tool allowlist và source ref.

Thêm `rag/mock/SUPERVISION_DATASET.md` giải thích cách dùng và rủi ro: 80 ca phục vụ thử pipeline/agent, **không đủ để fine-tune production**; Q03/Q04 là retrieval, không huấn luyện model trên Markdown. Chưa có ticket thật được phép dùng, nhãn chuyên gia, policy V3/SOP đã duyệt hoặc kết quả eval mô hình. Không ingest file supervision vào RAG và không trộn train với Q06 eval.

Theo yêu cầu tăng độ chi tiết, mở rộng cả 16 Markdown mock với ba ca phân nhánh cho mỗi issue và hồ sơ/hậu kiểm cụ thể; vẫn giữ nguyên nhãn `fixture_only`, `not_published`, không biến ví dụ thành chỉ dẫn sửa chữa cho cư dân. Thêm `rag/mock/MULTI_TURN_TRACES.jsonl` với 5 hội thoại nhiều lượt, mỗi trace gắn một POC và expected final. Đồng bộ `POC_LIFECYCLE.jsonl`: bốn ca chưa có executor result được đánh dấu `NOT_RUN_MISSING_RESULT`, không gọi `technical.verify_resolution`; ca có result giả lập vẫn cần `HUMAN_REVIEW`. Validator kiểm tra tính nhất quán trace ↔ POC, thứ tự lượt và không tự đóng ticket.

Rà lại 80 ca supervision: 15 ca closeout trước đó liệt kê `technical.verify_resolution` dù đầu vào chỉ là lời báo và chưa có executor result hợp lệ. Đã bỏ lệnh này khỏi kế hoạch tool; supervision chỉ cho phép tra cứu read-only, còn submit/verify thuộc luồng POC riêng. Validator nay chặn tool verify xuất hiện lại trong tập này. Kiểm tra cuối: **Validation OK**; các file mới chưa được commit/push.
