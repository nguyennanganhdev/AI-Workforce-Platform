# Bộ tình huống có nhãn A2 — v1

`SUPERVISION_CASES.jsonl` có **80 ca giả lập**: 16 issue code × 5 biến thể. Đây là dữ liệu để kiểm thử luồng intake/triage và huấn luyện thử một bộ phân loại hoặc agent trong môi trường cô lập; **không** phải ticket Vinhomes, SOP được duyệt hay tập fine-tune production.

`MULTI_TURN_TRACES.jsonl` bổ sung 5 hội thoại nhiều lượt cho 5 POC, có lượt của người báo, assistant, tool và nhân viên. Dùng trace để thử chuyển trạng thái/handoff và phát hiện lời khẳng định vượt chứng cứ; đây là bản demo, không phải hội thoại thực hoặc định dạng fine-tune sẵn dùng.

| Biến thể | Số ca | Split | Nhãn chính |
| --- | ---: | --- | --- |
| `routine` | 16 | train | `staff_assessment`: cần asset, nguồn và SOP thật trước can thiệp |
| `hazard` | 16 | train | `escalate_now`: nguy cơ điện/nước thải/kết cấu/va chạm, không trì hoãn để hỏi ảnh |
| `missing` | 16 | train | `ask_clarification`: `unknown` không phải `false` |
| `conflict` | 16 | dev | `human_review`: giữ provenance, không chọn nguồn bằng độ giống |
| `closeout` | 16 | test | `needs_evidence` hoặc `human_review`: không tự ghi `VERIFIED`/đóng ticket |

Mỗi record có `input.message` là lời báo giả lập, `input.facts` là dữ kiện đã nêu, `input.unknown` là điểm chưa xác minh. `target.route` là nhãn điều hướng, `target.ask` là câu cần hỏi, `target.tools` chỉ là kế hoạch **tra cứu read-only** có điều kiện (không phải lệnh gọi đã được cấp quyền), `target.reply` là câu trả lời mục tiêu để review, `target.avoid` là claim không được phát ra. Các ca closeout chỉ có lời báo, chưa có executor result hợp lệ nên không gọi `technical.verify_resolution`; việc submit/verify thực tế được mô phỏng tách biệt trong `POC_LIFECYCLE.jsonl` và `MULTI_TURN_TRACES.jsonl`. `source_ref` trỏ đến tài liệu `MOCK-PROC-XX-v1`, **không** trỏ SOP BQL. Tất cả có `fixture_only=true`. Tool host phải tự xác thực tenant/scope/capability; không lấy quyền từ record hay model.

## Dùng đúng mục đích

1. **RAG Q03/Q04:** index chỉ `rag/mock-corpus` vào KB/test tenant riêng. `SUPERVISION_CASES.jsonl` ở ngoài corpus, không được index làm kiến thức. Dùng `rag/mock/eval/technical-a2-mock.v1.json` cho Q06 retrieval; không trộn target response vào passage.
2. **Agent/triage:** dùng `train` để thử mapping input → route/ask/tool plan/reply sau khi đã có policy V3, dùng `dev` để chỉnh policy/prompt và giữ `test` cho đánh giá cuối. Kiểm tra riêng precision/recall từng route, nhất là miss nguy hiểm và leak scope; không lấy accuracy chung che lỗi Level 1.
3. **Fine-tune:** 80 ca không đủ về lượng, đa dạng người viết, ngôn ngữ, tòa/model và ground truth. Nhiều ca dùng cùng cấu trúc và cùng tài liệu nguồn; model có thể học thuộc cụm từ. Không upload trực tiếp làm tập fine-tune production. Cần ticket thực được phép dùng, khử PII, người có chuyên môn gán nhãn, SOP/policy đã pin version, phản ví dụ và eval giữ ngoài train. Không tự gắn nhãn `VERIFIED` hoặc giá từ fixture.
4. **Split/leakage:** split theo biến thể giúp kiểm tra nhánh logic, nhưng cùng issue và `MOCK-PROC` xuất hiện ở cả train/dev/test, nên **không phải** phép đo tổng quát hóa độc lập. Khi có ticket thật, chia theo ticket/work order và thời gian (không cho revision/cùng sự cố rơi sang split khác), deduplicate paraphrase và kiểm tra cross-building/tenant.

## Tiêu chí chấp nhận khi đổi sang dữ liệu thật

- Mỗi record phải có `ticket_id`, `tenant/building` đã xác minh, `reported_at`, nguồn từng fact, policy/version quyết định, outcome do người có quyền xác nhận và quyền dùng dữ liệu để huấn luyện. Không có trường nào được suy mặc định từ văn bản chat.
- Ca hazard cần kiểm tra có chuyển người kịp thời; ca thiếu dữ liệu phải hỏi tiếp; ca mâu thuẫn phải giữ cả nguồn; ca closeout không được biến `technical.verify_resolution` thành quyền đóng ticket.
- Kết quả retrieval phải gắn document/version/chunk ID thật từ DB và ACL hợp lệ; `MOCK-PROC-*` chỉ là khóa fixture.

Chạy `validate_data.ps1` để kiểm tra đủ 5 biến thể cho từng issue, split 48/16/16, nhãn route, tool được phép và liên kết source. Validator kiểm tra cấu trúc, **không** chứng minh nhãn an toàn đúng trên sự cố thực hay chất lượng mô hình.
