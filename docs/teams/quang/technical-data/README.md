# Bộ dữ liệu tham khảo cho Technical Agent A2

Ngày rà soát: 2026-10-05. Phạm vi: 16 mã vấn đề trong `../general.md`, 14 tool trong `../tools.md`, năm luồng POC và yêu cầu dữ liệu ở `../../../THIET_KE_HOC_KINH_NGHIEM_SELF_HELP_GIA.md`. Cách dùng với RAG Q03/Q04/Q06 nằm trong `RAG_INGESTION.md`.

## Có gì trong thư mục

| File | Nội dung | Cách dùng |
| --- | --- | --- |
| `SOURCE_REGISTER.md` | Sổ nguồn công khai đã đọc và nguồn do người dùng cung cấp, phạm vi áp dụng, giới hạn | Tra provenance trước khi dùng một fact |
| `SOURCE_FACTS.jsonl` | 24 fact diễn giải từ nguồn, có `source_id`, phạm vi và trạng thái review | Provenance/đối soát citation; Q03 không ingest JSONL trực tiếp |
| `DEEP_SOURCE_REGISTER.md` | 25 nguồn bổ sung từ HUD, EPA, USFA, có link gốc và giới hạn | Tra nguồn cho ma trận kiểm tra chuyên sâu |
| `DEEP_SOURCE_FACTS.jsonl` | 30 fact kiểm tra đã diễn giải, ánh xạ mã sự cố và trang/section nguồn | Provenance và test trace; không ingest trực tiếp hoặc làm rule severity |
| `VN_SOURCE_REGISTER.md` | 30 nguồn Việt Nam: Vinhomes, đơn vị vận hành, hãng thiết bị, viện kiểm định, cơ quan nhà nước và phản ánh Huế | Tra provenance và giới hạn sử dụng theo từng nguồn |
| `VN_SOURCE_FACTS.jsonl` | 23 fact diễn giải từ nguồn Việt Nam | Đối soát tài liệu RAG POC và citation; không ingest trực tiếp hoặc tự publish SOP |
| `VN_PUBLIC_CASES.jsonl` | 10 ca phản ánh công khai ở Huế với claim/phản hồi/bằng chứng tách riêng | Test triage, scope, uncertainty; không phải ticket Vinhomes |
| `RAG_SOURCE_MANIFEST.jsonl` | 74 source ID tham chiếu 72 URL riêng biệt, kèm trạng thái snapshot/quyền | Join citation; chưa có hash bản gốc nên chưa đủ production |
| `rag/corpus/01-vinhomes/cau-hoi-thuong-gap-a2.md` | Một Markdown tổng hợp 16 phần triage, có YAML front matter và mục nguồn trong từng phần | Root ingest Q03 là `rag/corpus`; chỉ vào KB tham khảo nội bộ |
| `rag/RAG_DOCUMENTS.jsonl` | Một manifest collection, giữ 16 section/issue code, fact và source refs | Đối soát Markdown; không phải bảng `knowledge_chunks` của DB |
| `rag/RAG_EVAL.jsonl` | 24 truy vấn theo shape Q06, kèm kỳ vọng an toàn A2 | Fixture nguồn để kiểm tra retrieval và câu trả lời |
| `rag/eval/technical-a2.v1.json` | Cùng 24 truy vấn ở định dạng `EvalDataset` JSON | Đầu vào định dạng cho runner Q06 khi có KB A2 riêng |
| `rag/mock-corpus/01-vinhomes/quy-trinh-gia-lap-a2.md` | Một Markdown tổng hợp 16 quy trình xử lý **giả lập**, mỗi phần có intake, 3 ca phân nhánh, điểm dừng, hồ sơ chứng cứ và hậu kiểm riêng | Chỉ nạp vào KB/test tenant cô lập nếu cần thử Q03/Q04; không trộn corpus tham khảo hoặc SOP thật |
| `rag/mock/PROCEDURE_PROFILES.jsonl` | 16 profile có điều kiện áp dụng, chống chỉ định, stop condition, tiêu chí kiểm tra có cấu trúc | Fixture cho thiết kế Q07/`technical.verify_resolution`; đều `draft`, không đủ quyền làm SOP thật |
| `rag/mock/POC_LIFECYCLE.jsonl` | 5 chuỗi ticket → assessment → asset → work order → evidence/measurement → expected result, cùng biến thể lỗi | Fixture cho adapter/tool A2 và test quyền/idempotency; ID/file/scan là giả lập |
| `rag/mock/Q07_LEARNING_FLOW.jsonl` | 2 candidate procedure giả lập (draft/rejected) và 1 ca kiểm tra eligibility self-help/giá thiếu dữ liệu | Test nhánh không được publish/hướng dẫn hoặc bịa giá; không phải attempt thật |
| `rag/mock/TOOL_DATA_FIXTURES.jsonl` | 16 bản ghi sensor, maintenance, interruption/schedule, approval, vendor và cost draft | Seed tham khảo cho adapter test, gồm nhánh stale/bad/cancelled/pending; không ingest RAG |
| `rag/mock/SUPERVISION_CASES.jsonl` | 80 tình huống có nhãn cho 16 mã × 5 biến thể, chia 48 train/16 dev/16 test | Thử triage/agent trong môi trường cô lập; không index vào RAG hoặc fine-tune production trực tiếp |
| `rag/mock/MULTI_TURN_TRACES.jsonl` | 5 hội thoại nhiều lượt gắn với 5 POC, gồm tool observation và expected final | Thử điều phối trạng thái, quyền và handoff; không nạp vào RAG |
| `rag/mock/SUPERVISION_DATASET.md` | Schema, cách dùng split, kiểm tra rò dữ liệu và giới hạn huấn luyện | Hướng dẫn xây eval/annotation tiếp theo |
| `rag/mock/eval/technical-a2-mock.v1.json` | 18 câu Q06 cho corpus mock: 16 `answer`, 1 `off_topic`, 1 `trap` | Chỉ chạy với KB mock cô lập; không tính là chất lượng trên data vận hành |
| `RAG_INGESTION.md` | Schema, bộ lọc retrieval, quy tắc trả lời và gate lên production | Hướng dẫn tích hợp và xác định dữ liệu còn thiếu |
| `validate_data.ps1` | Kiểm tra JSONL, nguồn, mã sự cố, trích dẫn và nhãn an toàn | Chạy trước khi ingest POC: `powershell -NoProfile -ExecutionPolicy Bypass -File docs/teams/quang/technical-data/validate_data.ps1` |
| `VN_COVERAGE_AND_GAPS.md` | Ma trận 16 issue code với độ phủ VN và điều kiện RAG | Xác định dữ liệu nội bộ còn phải xin |
| `VINHOMES_SOURCE_AUDIT.md` | Đối chiếu từng vùng/tài liệu kỹ thuật trong Data-Vinhome | Chọn dữ liệu Vinhomes còn phải xác minh với BQL |
| `ISSUE_CATALOG.md` | 16 hồ sơ sự cố: dấu hiệu, câu hỏi, giả thuyết, tín hiệu khẩn, dữ liệu cần thu, kiểm chứng kết quả | Seed taxonomy, retrieval fixture, câu hỏi Reception/A2 |
| `SYNTHETIC_CASES.jsonl` | 16 ca giả lập, mỗi issue code một ca; có expected routing và các trường thiếu | Test phân loại và yêu cầu làm rõ; tuyệt đối không coi là ticket thật |
| `EDGE_CASES.jsonl` | 16 ca giả lập thêm: thiếu dữ kiện, đa triệu chứng, tái phát, nguy cơ chéo | Regression test không đoán nguyên nhân/không tự thao tác nguy hiểm |
| `INSPECTION_MATRIX.md` | Ma trận 16 mã: phân biệt triệu chứng, chứng cứ, trang nguồn, điều không được kết luận | Thiết kế checklist hiện trường và evidence schema |
| `PUBLIC_DATASET_AUDIT.md` | Kiểm tra NYC HPD/311 ở mức metadata, quyền sử dụng và khoảng trống dữ liệu thực | Quyết định có nên nhập dữ liệu mở và thứ tự xin dữ liệu BQL |
| `POC_WORKFLOWS.md` | Năm luồng POC và các biến thể lỗi cần test | Chốt fixture end-to-end và expected result |
| `TOOL_DATA_MATRIX.md` | Nguồn dữ liệu cần cho từng tool A2 | Biết tool nào còn thiếu adapter/dữ liệu thật |
| `COLLECTION_SPEC.md` | Hợp đồng thu thập dữ liệu thật, độ đầy đủ, lộ trình và các ca lỗi cần test | Giao việc thu thập và đánh giá readiness |

## Ý nghĩa nhãn

- `vinhomes_public`: chỉ fact được trang Vinhomes công khai xác nhận; không suy ra quy trình, SLA hoặc cấu hình của một tòa cụ thể.
- `external_reference`: kiến thức chuyên môn tham khảo từ cơ quan quản lý, nhà sản xuất hoặc dữ liệu mở ở nơi khác. Cần người phụ trách kỹ thuật Vinhomes duyệt trước khi dùng làm SOP hay hướng dẫn cư dân.
- `user_supplied_unverified`: dữ liệu từ [Data-Vinhome](https://github.com/leduc1707/Data-Vinhome/tree/8ebe9d42c396f82023507a8662d8323f09367654). Một số file tự đánh dấu `chua-thu-thap`/`da-thu-thap-mot-phan`; không mặc định là văn bản BQL có hiệu lực.
- `synthetic`: bản ghi do bộ dữ liệu này tạo để test, không phải cư dân, tòa, ticket, thiết bị, ảnh, chi phí hoặc số đo thật.
- `external_reference_vn`: diễn giải ngắn từ đơn vị vận hành/nhà sản xuất/cơ quan tại Việt Nam; chưa được Vinhomes duyệt để xuất bản.
- `case_example_vn`: phản ánh công khai và lời cơ quan phản hồi đã khử PII, không phải work order hay kết quả kỹ thuật đã xác minh.

Các nhận định và checklist ở đây là bản tóm tắt mới, không chép nguyên văn tài liệu nguồn. URL trong sổ nguồn là nơi đọc bản gốc và kiểm tra phiên bản. Không ingest cả repo Data-Vinhome như một khối: cần kiểm tra trạng thái, đơn vị vận hành, phạm vi tòa và nguồn của từng fact.

Ba file `*_FACTS.jsonl` đều có `approval_status=not_published`. `source_location=null` ở 22 fact cũ nghĩa là chưa ghi được đoạn/trang nguồn; không được coi đó là trích dẫn đủ chặt để xuất bản. Hai URL được dùng lặp có chủ ý: bài Vinhomes (`VH-01`/`VN-VH-01`) và hai tài liệu HUD nằm trong ID tổng hợp `HUD-03` đồng thời có ID riêng `HUD-08`/`HUD-09`. Số ID nguồn không phải số tài liệu độc lập.

## Giới hạn hiện tại

Chưa có SOP chính thức của từng tòa, ticket/work order đã ẩn danh, hồ sơ thiết bị, sensor, ảnh evidence, kết quả sửa chữa, giá thực tế đã xác minh hoặc bản phê duyệt self-help. Tổng cộng có 77 fact có nguồn, 32 ca **giả lập** và 10 phản ánh công khai **không phải ticket Vinhomes**; không có ticket vận hành Vinhomes đã xác minh. 16 phần triage trong một Markdown tổng hợp là bản tuyển chọn/diễn giải lại các nguồn trên, **không cộng vào số fact**. Bộ này đủ để xây taxonomy, schema, mock và RAG POC nội bộ có trích nguồn/từ chối khi thiếu dữ liệu; chưa đủ để vận hành A2 với cư dân thật, tự tính SLA hoặc báo giá. Chưa chạy eval retrieval A2 trên DB/model; các chỉ số của bộ Ocean Park không áp sang đây.

16 quy trình, 5 lifecycle và 80 tình huống có nhãn trong `rag/mock*` là **fixture do dự án tự viết** để phát triển/kiểm thử, không làm tăng số fact có nguồn hoặc số ticket thực. `simulated_clean` trong JSONL chỉ là trạng thái giả lập cho adapter test, không chứng minh có file đã scan. Không được dùng số đo mock làm ngưỡng an toàn, kết quả `VERIFIED` thật hoặc giá tham khảo. Profile `draft` không được `sop_kb.retrieve` phục vụ; muốn thử nhánh published phải seed bản test riêng vào tenant/KB cô lập với ACL test và tuyệt đối không grant cho cư dân. 80 ca vẫn chưa đủ để fine-tune production; xem `rag/mock/SUPERVISION_DATASET.md`.

Mọi mức khẩn trong `ISSUE_CATALOG.md` chỉ là **tín hiệu cần đánh giá**. Quyết định `severity`/`priority` chính thức phải đến từ policy V3 đã publish và backend rule engine, không từ mô tả hoặc LLM. Kết quả `VERIFIED` của tool chỉ là khuyến nghị; người có quyền mới xác nhận hoàn tất.

## Quy tắc ingest

1. Ingest chỉ thư mục `rag/corpus` vào knowledge base `technical_reference_internal_poc` có grant nội bộ. `rag/mock-corpus` là root khác, chỉ dành cho KB/test tenant cô lập. Không ingest thư mục gốc hoặc chạy CLI dev trên KB Ocean Park đã có dữ liệu vì CLI dùng `prune=true`.
2. Lưu `source_id`, URL/tài liệu, publisher, ngày truy xuất, ngày hiệu lực nếu có, content hash và phạm vi tenant/domain/building.
3. Tách claim thành fact có nguồn; `unknown` không được chuyển thành `false` hoặc giá trị mặc định.
4. Tài liệu ngoài Vinhomes chỉ nằm trong namespace tham khảo; quy trình Vinhomes cần review, publish và version riêng.
5. Không đưa hotline, sơ đồ thoát nạn, số phòng, ảnh cư dân, địa chỉ căn hộ, credential hoặc chi phí riêng vào corpus công khai.
6. Khi nguồn bị thu hồi/hết hiệu lực, tombstone version và vô hiệu hóa cache/retrieval; citation phải còn trỏ được tới source version được phép đọc.
