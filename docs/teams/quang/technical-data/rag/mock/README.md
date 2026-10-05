# Bộ fixture quy trình A2 — chỉ dùng để phát triển

Ngày tạo: 2026-10-05. Toàn bộ ID, model, số đo, event và kết quả ở đây là **giả lập**. Không có SOP Vinhomes, file ảnh đã scan, ticket/work order thật, số đo thực, SLA hoặc giá thật trong bộ này.

## Cách chia lớp dữ liệu

| Lớp | Đường dẫn | Dùng cho |
| --- | --- | --- |
| Passage RAG Q03/Q04 | `../mock-corpus/01-vinhomes/quy-trinh-gia-lap-a2.md` | Một Markdown với 16 phần theo issue; có ca phân nhánh, hồ sơ tối thiểu và hậu kiểm riêng từng lỗi; chunker đọc heading/front matter/`Nguồn` |
| Quy trình có cấu trúc Q07/A2 | `PROCEDURE_PROFILES.jsonl` | 16 profile `draft` với `preconditions`, `contraindications`, `stop_conditions`, `acceptance_criteria` theo `AcceptanceCriterion` của `server/src/technical-tools/domain/sop.ts` |
| Luồng tác nghiệp A2 | `POC_LIFECYCLE.jsonl` | 5 fixture về ticket → assessment → asset → work order/assignment → evidence/measurement → expected outcome/negative variants |
| Học procedure Q07 | `Q07_LEARNING_FLOW.jsonl` | 2 candidate từ work order mock (draft/rejected) và một eligibility test không tạo attempt, không bịa giá |
| Dữ liệu tool A2/Q08 | `TOOL_DATA_FIXTURES.jsonl` | 16 bản ghi bổ trợ: 3 sensor (fresh/stale/bad), 3 maintenance, 4 interruption/schedule (proposed/notified/cancelled/active khác building), 4 request pending, 1 vendor chưa booking, 1 cost draft |
| Tình huống có nhãn | `SUPERVISION_CASES.jsonl` và `SUPERVISION_DATASET.md` | 80 ca intake/triage: 5 biến thể × 16 issue, split 48/16/16; không index hoặc fine-tune production trực tiếp |
| Hội thoại nhiều lượt | `MULTI_TURN_TRACES.jsonl` | 5 trace cho 5 POC, có người báo/assistant/tool/nhân viên và expected final; dùng kiểm thử điều phối, không nạp RAG |
| Eval retrieval Q06 | `eval/technical-a2-mock.v1.json` | 18 ca theo `EvalDataset`; chạy độc lập khỏi eval nguồn tham khảo |

`document_code` của mọi profile cùng trỏ tới Markdown collection tương đối từ root `../mock-corpus`; section và `code` phân biệt từng quy trình. `source_work_order_id` của 5 profile POC trỏ tới `work_order.workorder_id` trong `POC_LIFECYCLE.jsonl`; 11 profile còn lại để `null` vì chưa có lifecycle chi tiết. Các UUID thuộc dải fixture, không phải ID trong DB dự án. `scope.building_key=SYN-B-01` chỉ là tòa giả lập; Markdown Q03 đang ở scope cấp đơn vị `01-vinhomes`, không mô phỏng ACL theo tòa. Khi cần test tòa cụ thể phải đưa tài liệu vào nhánh folder scope tòa và cấp grant tương ứng, không suy scope từ tên case.

`scan_status=simulated_clean` mô tả nhánh adapter test mong muốn, **không** chứng minh có bytes/file/hash đã được scan. Bộ này không có object storage hay seed DB; muốn test thực `technical.submit_executor_result` phải tạo file fixture qua storage adapter, liên kết đúng ticket/work order, scan và cấp ACL trong test tenant. Measurement số trong POC chỉ để kiểm thử kiểu/đơn vị/provenance; không phải ngưỡng nghiệm thu. Các `acceptance_criteria` dạng `manual` buộc người có chuyên môn quyết định; profile `draft` không thể dùng để trả `VERIFIED` thật.

`TOOL_DATA_FIXTURES.jsonl` là dữ liệu nguồn để viết adapter/seed test, không phải response envelope của tool. Dùng `test_now=2026-09-30T09:00:00Z` khi chấm freshness; sensor `quality=bad` dù fresh cũng không chứng minh an toàn. `proposed` và `cancelled` phải bị loại khỏi `technical.get_active_outage`/`utility_schedule.read`; `active` của building khác không lộ sang `SYN-B-01`. Bốn request pending chưa gây hành động ngoài hiện trường. Một cost observation `draft` có số tiền **hoàn toàn giả lập**, phải loại khỏi tập mẫu giá và trả `insufficient_data`.

## Quy tắc an toàn khi tích hợp

1. Không nạp `rag/mock-corpus` cùng `rag/corpus`, không nạp cả `technical-data`, không chạy CLI dev có `prune=true` lên KB chứa tài liệu khác. Nếu dùng RAG mock, tạo test tenant/KB riêng chỉ grant cho nhân viên/test và preview trước với `--dump-chunks`.
2. `fixture_only=true`, `approval_status=not_published`, `sop_available=false` và tiêu đề `MOCK-PROC-*` phải còn nguyên. Q03 hiện tự đặt DB document `published` sau ingest, nên metadata chỉ là cảnh báo; **KB/ACL là hàng rào thật**.
3. JSONL profile không phải DB seed trực tiếp và không thay thế `knowledge_reviews`, `memory_publications`, `repair_procedure_versions`. Q07 phải kiểm tra tác giả, source work order, phiên bản/hash nội dung, khử PII, review quyền và publish nguyên tử. Không đổi `publication_status` trong file để giả hoàn thành workflow.
4. `sop_kb.retrieve` chỉ trả SOP eligible từ DB theo tenant/building/ACL/version/effective time. Các profile `draft` ở đây không được tool trả về. Test nhánh published/`VERIFIED` dùng fixture test riêng có ACL và evidence mô phỏng hợp lệ, không dùng các profile này làm quyền vận hành.
5. Không dùng RAG để tính giá. Hiện không có `repair_cost_observations` verified; tool giá phải trả `insufficient_data` cho đến khi có mẫu đủ điều kiện và policy được duyệt.

`Q07_LEARNING_FLOW.jsonl` cố ý chỉ có nhánh draft/rejected: chưa có SOP cư dân đã duyệt, nên không thể mô phỏng một self-help success như kết quả thật. Để test nhánh accepted/succeeded của ứng dụng, tạo procedure published **chỉ trong test tenant**, cùng canonical file/hash, review, publication, ACL và attempt pin version theo thiết kế Q07; không đổi trạng thái fixture ở đây.

Chạy `powershell -NoProfile -ExecutionPolicy Bypass -File docs/teams/quang/technical-data/validate_data.ps1` để kiểm tra liên kết và schema cơ bản. Khi có Bun, có thể preview Markdown mà không ghi DB: từ `server/`, chạy `bun src/knowledge/cli.ts ../docs/teams/quang/technical-data/rag/mock-corpus --dump-chunks mock-chunks.json`. `eval.ts --dataset` hiện vẫn dùng KB dev Ocean Park; cần fixture/KB mock riêng trước khi chạy dataset này, nếu không kết quả không có ý nghĩa.
