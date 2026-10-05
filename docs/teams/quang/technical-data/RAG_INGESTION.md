# Hợp đồng dữ liệu A2 với RAG Q03/Q04/Q06

Cập nhật 2026-10-05. Bộ này là tri thức **triage tham khảo nội bộ**, chưa phải SOP kỹ thuật Vinhomes. Nội dung nguồn là diễn giải ngắn; chưa có bản lưu/hash nguồn gốc hoặc quyền tái phân phối toàn văn.

## 1. Cấu trúc và vai trò

| Đường dẫn | Vai trò | Có được ingest vào answer index? |
| --- | --- | --- |
| `rag/corpus/` | Một Markdown Q03 gồm 16 phần: YAML front matter, heading theo issue và mục `Nguồn` chứa URL/fact | Có, **chỉ** trong knowledge base `technical_reference_internal_poc` với grant nội bộ |
| `rag/RAG_DOCUMENTS.jsonl` | Manifest collection: `document_code`, `scope_key`, 16 issue code/section, fact/source refs, trạng thái | Không; ID `A2-DOC-*` không phải UUID `knowledge_documents.id` |
| `rag/RAG_EVAL.jsonl` | 24 test: các trường `id/scope/query/expect/contains/tags` theo Q06 và trường kiểm tra câu trả lời A2 | Không |
| `rag/eval/technical-a2.v1.json` | `EvalDataset` JSON đúng shape của `server/src/knowledge/eval-metrics.ts` | Không |
| `rag/mock-corpus/` | Một Markdown gồm 16 quy trình giả lập với `fixture_only=true`, `approval_status=not_published`, `sop_available=false` | Chỉ KB/test tenant cô lập; **không** ingest chung `rag/corpus` |
| `rag/mock/PROCEDURE_PROFILES.jsonl` | 16 profile `draft` gồm precondition/contraindication/stop condition và acceptance criteria có cấu trúc | Không; fixture thiết kế Q07 và A2 |
| `rag/mock/POC_LIFECYCLE.jsonl` | 5 chuỗi ticket → work order/evidence/result giả lập | Không; fixture adapter/test, không phải DB seed |
| `rag/mock/Q07_LEARNING_FLOW.jsonl` | Candidate `draft`/`rejected` và eligibility test tự xử lý/giá | Không; fixture Q07/Q08 nhánh từ chối |
| `rag/mock/TOOL_DATA_FIXTURES.jsonl` | 16 bản ghi mẫu cho sensor/history/outage/schedule/approval/vendor/cost draft | Không; fixture adapter A2/Q08, không phải DB seed |
| `rag/mock/SUPERVISION_CASES.jsonl` | 80 ca có nhãn train/dev/test cho intake, hazard, thiếu dữ kiện, mâu thuẫn, closeout | Không; dữ liệu thử agent/triage, không phải passage RAG |
| `rag/mock/MULTI_TURN_TRACES.jsonl` | 5 trace nhiều lượt có expected final gắn POC | Không; dữ liệu thử điều phối agent/tool, không phải passage RAG |
| `rag/mock/eval/technical-a2-mock.v1.json` | 18 câu Q06 riêng cho mock corpus | Không |
| `RAG_SOURCE_MANIFEST.jsonl` và `*_FACTS.jsonl` | Sổ URL, nguồn và fact gốc; không có snapshot nguồn | Không |
| `VN_PUBLIC_CASES.jsonl`, `SYNTHETIC_CASES.jsonl`, `EDGE_CASES.jsonl` | Ca công khai ngoài Vinhomes và fixture giả lập | Không |

Root ingest là **`rag/corpus`**, không phải cả `technical-data`: nếu chỉ định thư mục cha, Q03 sẽ index cả README, ma trận, gap list và tài liệu quản trị. Với root này, `source-directory.ts` đọc một Markdown tổng hợp dưới `01-vinhomes/`; chunker tách passage theo heading của 16 issue. `scopeKeyOf` trả `01-vinhomes`, `sourceMetadata` trả `don_vi=vinhomes`, `cap=don_vi`, `loai=faq`. Đây là tham khảo cấp đơn vị, không gắn nhầm một tòa cụ thể.

Mock corpus là root **khác**: `rag/mock-corpus`. Nếu preview/ingest riêng, một file tổng hợp chứa 16 phần có `loai=quy_trinh`, `trang_thai=du-lieu-gia-lap-khong-xuat-ban` và `unverified=true`. Từ “Vinhomes” trong scope chỉ mô phỏng nhánh metadata, **không** biểu thị Vinhomes đã ban hành/duyệt. Q03 vẫn tự publish bản đã ingest trong DB, nên phải dùng test tenant/KB có grant test và không trộn với nguồn thật. `sop_kb.retrieve` chỉ phục vụ SOP eligible; 16 profile mock đang `draft`, không phải đầu vào hợp lệ của tool đó. Việc chuyển procedure từ work order thành tài liệu published có review/ACL/version là công việc Q07 và backend, không thể thực hiện bằng đổi nhãn JSONL.

Mục `## Nguồn` dùng bullet để chunker Q03 đưa URL vào `sources` của mỗi kết quả mà không nhúng URL vào văn bản embedding. Một tài liệu hiện tạo một chunk triage; `documentId/versionId/chunkId` thực tế do DB sinh. Khi sửa Markdown, Q03 tạo version mới theo content hash; manifest JSONL giữ khóa biên tập ổn định và validator đối chiếu nội dung.

## 2. Điều kiện ingest và retrieval

1. Backend phải cấp **knowledge base riêng và grant chỉ cho nhân viên/test**, `scopeId` cho `01-vinhomes`, và `files.id` qua storage adapter. Q03 tự đặt document DB là `published` sau ingest; front matter `approval_status=not_published` **không tự chặn truy cập**. Không đưa knowledge base này vào grant của Reception/cư dân hoặc `sop_kb.retrieve`.
2. Front matter giữ `trang_thai=tham-khao-noi-bo-chua-duyet`, `approval_status=not_published`, `sop_available=false`. `source-metadata.ts` đánh dấu `unverified=true` khi `approval_status=not_published`; passage chứa chữ “web” nên `reliability=web`. Cả hai nhãn phải được giữ trong câu trả lời nội bộ.
3. Không chạy `cli.ts <rag/corpus>` trên DB dev Ocean Park đã nạp dữ liệu khác: CLI dùng chung KB `rag-dev-ocean-park` và `prune=true`, có thể archive tài liệu không còn trong thư mục. Chỉ dùng `--dump-chunks` để preview không cần DB/API key; để ingest thật cần job Q03 với KB riêng và `prune` chỉ khi job sở hữu toàn KB đó.
4. Q04 nhận `query/topK/scopeId`; quyền, tenant và danh sách scope do backend xác thực. ACL/scope phải được lọc trong SQL trước khi xếp hạng. Không cho agent tự khai `tenantId`, `userId` hoặc document IDs.
5. Công cụ `search_knowledge` trả passage và citation, không trả chẩn đoán. Yêu cầu SOP đúng tòa/model, thao tác sửa, giá, SLA, trách nhiệm, xác nhận an toàn hoặc “đã sửa” phải dùng nguồn BQL/asset/work order có thẩm quyền; bộ này chưa có nên trả thiếu dữ liệu và chuyển người.

## 3. Kiểm thử

Có 16 câu `answer` cho 16 mã A2, 5 `no_data`, 2 `off_topic` và 1 `trap` khác đơn vị vận hành. Trường `contains` trỏ tới đoạn Markdown, không trỏ `chunkId` vì ID DB không ổn định. `EvalDataset` Q06 đo recall/MRR, từ chối và rò phạm vi; nó **không** chấm `expected_human_escalation`, `forbidden_claims` hay độ an toàn câu trả lời, nên các trường mở rộng trong JSONL cần test A2 riêng.

Dataset `rag/mock/eval/technical-a2-mock.v1.json` đo riêng 16 quy trình mock, gồm 16 `answer`, 1 `off_topic`, 1 `trap`; không được gộp với chỉ số nguồn tham khảo. 5 POC JSONL chứa thêm các biến thể hazard, thiếu evidence, ACL và approval để test A2, không dùng Q06 để tuyên bố agent trả lời an toàn.

`rag/mock/SUPERVISION_CASES.jsonl` là tập có nhãn riêng cho agent/triage (80 ca), **không** nạp vào RAG để tránh lộ đáp án. RAG dùng retrieval/eval, không cần “train” mô hình trên các passage. Nếu muốn fine-tune classifier/agent thì cần dữ liệu thật được cấp quyền và gán nhãn độc lập; 80 mock chỉ thử pipeline. Chi tiết split và rủi ro leakage nằm ở `rag/mock/SUPERVISION_DATASET.md`.

Ngưỡng cosine 0.35 được chọn trên bộ Ocean Park 93 câu. Chưa có kết quả đo recall hoặc ngưỡng phù hợp cho corpus A2; không dùng số 82,4% của Ocean Park làm chất lượng bộ này. Bộ `technical-a2.v1.json` đúng định dạng Q06, nhưng `eval.ts` hiện dùng dev fixture và KB Ocean Park; cần fixture/KB riêng để chạy đánh giá thực.

Kiểm tra cấu trúc và nguồn bằng `powershell -NoProfile -ExecutionPolicy Bypass -File docs/teams/quang/technical-data/validate_data.ps1`. Trên máy có Bun, có thể xem chính xác chunker đọc gì bằng `cd server` rồi `bun src/knowledge/cli.ts ../docs/teams/quang/technical-data/rag/corpus --dump-chunks chunks.json`; lệnh này không ingest.

## 4. Dữ liệu còn thiếu cho vận hành

Cần SOP BQL có version/hiệu lực/ACL theo tòa và asset; ticket → work order → số đo/evidence → outcome được kỹ thuật viên xác minh; inventory/model/manual đúng thiết bị; policy V3 và dữ liệu outage/sensor khi sản phẩm dùng chúng; quyền dùng bản nguồn, snapshot/hash và quy trình thu hồi. `RAG_SOURCE_MANIFEST.jsonl` vẫn ghi `content_sha256=null`, `snapshot_status=not_archived`, `rights_status=not_cleared_for_fulltext` cho nguồn ngoài. Không suy các mục còn thiếu từ web hoặc tình huống giả lập.
