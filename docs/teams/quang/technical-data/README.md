# Bộ dữ liệu tham khảo cho Technical Agent A2

Ngày rà soát: 2026-10-01. Phạm vi: 16 mã vấn đề trong `../general.md`, 14 tool trong `../tools.md`, năm luồng POC và yêu cầu dữ liệu ở `../../../THIET_KE_HOC_KINH_NGHIEM_SELF_HELP_GIA.md`.

## Có gì trong thư mục

| File | Nội dung | Cách dùng |
| --- | --- | --- |
| `SOURCE_REGISTER.md` | Sổ nguồn công khai đã đọc và nguồn do người dùng cung cấp, phạm vi áp dụng, giới hạn | Tra provenance trước khi dùng một fact |
| `SOURCE_FACTS.jsonl` | 24 fact diễn giải từ nguồn, có `source_id`, phạm vi và trạng thái review | Fixture ingestion/citation; không tự publish SOP |
| `DEEP_SOURCE_REGISTER.md` | 25 nguồn bổ sung từ HUD, EPA, USFA, có link gốc và giới hạn | Tra nguồn cho ma trận kiểm tra chuyên sâu |
| `DEEP_SOURCE_FACTS.jsonl` | 30 fact kiểm tra đã diễn giải, ánh xạ mã sự cố và trang/section nguồn | Fixture retrieval có trace; không làm rule severity |
| `VN_SOURCE_REGISTER.md` | 30 nguồn Việt Nam: Vinhomes, đơn vị vận hành, hãng thiết bị, viện kiểm định, cơ quan nhà nước và phản ánh Huế | Tra provenance và giới hạn sử dụng theo từng nguồn |
| `VN_SOURCE_FACTS.jsonl` | 23 fact diễn giải từ nguồn Việt Nam | RAG POC có citation; không tự publish SOP |
| `VN_PUBLIC_CASES.jsonl` | 10 ca phản ánh công khai ở Huế với claim/phản hồi/bằng chứng tách riêng | Test triage, scope, uncertainty; không phải ticket Vinhomes |
| `RAG_SOURCE_MANIFEST.jsonl` | 74 source ID tham chiếu 72 URL riêng biệt, kèm trạng thái snapshot/quyền | Join citation; chưa có hash bản gốc nên chưa đủ production |
| `RAG_CHUNKS.jsonl` | 16 đoạn tri thức triage đã tuyển chọn, mỗi mã A2 một đoạn | Index riêng cho POC nội bộ, không là SOP/hướng dẫn cư dân |
| `RAG_EVAL.jsonl` | 23 truy vấn kiểm thử retrieval, abstention, safety và scope | Smoke/eval regression cho RAG POC |
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

Chưa có SOP chính thức của từng tòa, ticket/work order đã ẩn danh, hồ sơ thiết bị, sensor, ảnh evidence, kết quả sửa chữa, giá thực tế đã xác minh hoặc bản phê duyệt self-help. Tổng cộng có 77 fact có nguồn, 32 ca **giả lập** và 10 phản ánh công khai **không phải ticket Vinhomes**; không có ticket vận hành Vinhomes đã xác minh. 16 chunk triage là bản tuyển chọn/diễn giải lại các nguồn trên, **không cộng vào số fact**. Bộ này đủ để xây taxonomy, schema, mock và RAG POC nội bộ có trích nguồn/từ chối khi thiếu dữ liệu; chưa đủ để vận hành A2 với cư dân thật, tự tính SLA hoặc báo giá.

Mọi mức khẩn trong `ISSUE_CATALOG.md` chỉ là **tín hiệu cần đánh giá**. Quyết định `severity`/`priority` chính thức phải đến từ policy V3 đã publish và backend rule engine, không từ mô tả hoặc LLM. Kết quả `VERIFIED` của tool chỉ là khuyến nghị; người có quyền mới xác nhận hoàn tất.

## Quy tắc ingest

1. Lưu `source_id`, URL/tài liệu, publisher, ngày truy xuất, ngày hiệu lực nếu có, content hash và phạm vi tenant/domain/building.
2. Tách claim thành fact có nguồn; `unknown` không được chuyển thành `false` hoặc giá trị mặc định.
3. Tài liệu ngoài Vinhomes chỉ nằm trong namespace tham khảo; quy trình Vinhomes cần review, publish và version riêng.
4. Không đưa hotline, sơ đồ thoát nạn, số phòng, ảnh cư dân, địa chỉ căn hộ, credential hoặc chi phí riêng vào corpus công khai.
5. Khi nguồn bị thu hồi/hết hiệu lực, tombstone version và vô hiệu hóa cache/retrieval; citation phải còn trỏ được tới source version được phép đọc.
