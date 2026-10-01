# Hợp đồng dùng bộ dữ liệu cho RAG kỹ thuật A2

Phiên bản POC 2026-10-01. Corpus hiện là các **diễn giải ngắn** từ nguồn công khai; không có SOP Vinhomes được publish, bản sao nguồn có hash, ticket nội bộ hay quyền tái phân phối toàn văn. Vì vậy chỉ bật ở môi trường **nội bộ/test**, không dùng trực tiếp trả lời cư dân.

## 1. File và namespace

| Dữ liệu | Index? | Namespace | Ý nghĩa |
| --- | --- | --- | --- |
| `RAG_CHUNKS.jsonl` | Có, POC nội bộ | `triage_reference_internal_poc` | 16 đoạn triage được tuyển chọn, không là SOP hoặc chẩn đoán |
| `RAG_SOURCE_MANIFEST.jsonl` | Join theo `source_id`, không embedding toàn bộ | `source_registry` | URL, publisher, loại nguồn, tình trạng snapshot/quyền; `content_sha256=null` có nghĩa chưa lưu bytes gốc |
| `VN_PUBLIC_CASES.jsonl` | Không vào answer index mặc định; chỉ eval/case sandbox | `case_example_vn` | Phản ánh và phản hồi công khai, nhãn bằng chứng ba trạng thái |
| `SOURCE_FACTS`, `DEEP_SOURCE_FACTS`, `VN_SOURCE_FACTS` | Chưa index trực tiếp | `research_archive` | Fact gốc nhiều schema khác nhau, có trùng ý và thiếu snapshot; dùng đối soát nguồn |
| `SYNTHETIC_CASES`, `EDGE_CASES`, `RAG_EVAL` | Không | `test_fixtures` | Fixture kiểm thử, tuyệt đối không xem là sự cố thật |

`chunk_id` ổn định trong phiên bản POC; `citation_source_ids` phải join ra ít nhất một URL trong manifest. `citation_fact_refs` chỉ tới fact và vị trí nguồn đã ghi nhận; không phải hash/snapshot. Bản ghi không join được thì bỏ khỏi index. Không gộp các namespace trên vào `sop_kb.retrieve`: tool đó chỉ nhận SOP Vinhomes đúng scope, đã review/publish, còn hiệu lực và có ACL.

## 2. Trường tối thiểu cho retrieval và câu trả lời

- Query context do backend xác thực: `tenant_id`, `domain_id`, `building_id`, `actor_role`, `issue_code_candidate`, `observed_at`. Không lấy các ID/quyền này từ lời chat.
- Kết quả retrieval: `chunk_id`, `text_vi`, `citation_source_ids`, URL từ manifest, `knowledge_type`, `policy_status`, `source_kind`, `content_sha256`, `scope`, `retrieved_at`, `answer_use`.
- Mặc định `answer_use=internal_reference_only`, `resident_instruction_allowed=false`. Khi `content_sha256=null`, không được tuyên bố nội dung nguồn đã được snapshot/version hóa; dùng link công khai như dẫn chứng POC và kiểm tra lại khi cần.
- `unknown`, `unverified`, `not_observed_at_inspection`, `agency_reports_restored_no_work_order` và `verified_by_technician` là các trạng thái khác nhau. Không ép thành boolean `resolved`.
- Citation phải trỏ **fact/claim**, không chỉ dẫn link chung rồi gắn một kết luận mạnh hơn nguồn. Với nguồn Huế, tách `resident_claim` và `agency_response`; không dùng `Ngày xử lý` của cổng như ngày sửa xong hoặc SLA Vinhomes.

## 3. Gate trả lời

1. Trước retrieval, backend kiểm tra scope và phát hiện tín hiệu an toàn theo policy V3; RAG không tự áp `severity`/`priority` hoặc thời hạn. Có nước gần điện, khói/tia lửa, kính/vật liệu có nguy cơ rơi, nước thải lan/phơi nhiễm: chuyển người trực theo quy định dự án.
2. Nếu câu hỏi là triage tham khảo, truy vấn `triage_reference_internal_poc`; trả triệu chứng cần phân biệt, câu hỏi còn thiếu và nguồn. Không đưa thao tác tháo tủ điện, tháo máy nước nóng, xử lý hóa chất, vào căn khác hoặc điều khiển thiết bị.
3. Nếu câu hỏi đòi SOP đúng tòa/model, trách nhiệm chi phí, bảo hành, ETA/SLA, kết luận nguyên nhân, xác nhận an toàn hoặc đã sửa: chỉ dùng nguồn BQL/asset/work order được phép và còn hiệu lực. Vì hiện chưa có, trả `insufficient_authorized_data` và tạo handoff theo flow A2.
4. Ca từ chung cư khác chỉ có vai trò **case example**, không chứng minh Vinhomes có lỗi tương tự; ca giả lập không có vai trò chứng cứ. Khi nhiều khả năng/nguồn mâu thuẫn, giữ chúng là giả thuyết và trả `HUMAN_REVIEW` nếu cần.
5. Trước khi đưa dữ liệu của căn/ticket thật vào index, phải khử PII, kiểm tra ACL theo tenant/building/ticket, kiểm tra quyền dùng tài liệu và lưu phiên bản nguồn. Có revocation thì tombstone và invalidation index/cache.

## 4. Kiểm định POC

`RAG_EVAL.jsonl` gồm 16 truy vấn theo mã A2 và 7 truy vấn abstain/safety/scope. `expected_chunk_ids=[]` ở truy vấn âm nghĩa là **không bắt buộc một chunk cụ thể**, không có nghĩa cấm trích nguồn liên quan. Kiểm thử cần chấm riêng: đúng mã/scope, nguồn trích dẫn, không bịa nguyên nhân/SLA/giá, không hướng dẫn nguy hiểm, và chuyển người khi có tín hiệu khẩn. Những bài test này không chứng minh hệ thống đủ an toàn production.

## 5. Việc còn thiếu để đạt production

| Ưu tiên | Dữ liệu phải xin | Điều kiện nghiệm thu tối thiểu |
| --- | --- | --- |
| P0 | SOP kỹ thuật và an toàn do BQL/Domain Owner ban hành cho từng tòa/asset | Document ID/version, hiệu lực, building/asset scope, audience, quyền, người duyệt, tiêu chí nghiệm thu và hash |
| P0 | Ticket + work order + kết quả kỹ thuật viên đã khử PII | Khóa liên kết, timeline, issue/symptom, chẩn đoán xác nhận, việc làm, evidence trước/sau, người xác minh và outcome; không lấy ca công khai thay thế |
| P0 | Asset/CMMS theo tòa và model | Asset ID, model/serial nếu được phép, vị trí, ownership, manual đúng model, warranty, trạng thái cập nhật |
| P1 | Policy V3, outage, BMS/IoT và quyền/handoff | Rule/version, nguồn timestamp/unit/quality, ngưỡng stale, phê duyệt hành động rủi ro |
| P1 | Quyền sử dụng nguồn và snapshot | Điều khoản/licence được kiểm tra, bytes nguồn lưu có quyền, SHA-256, thời điểm truy xuất, source span, quy trình thu hồi |
| P2 | Giá thực và self-help đã được publish nếu sản phẩm cần | Dữ liệu cost được xác minh theo work order; hướng dẫn theo model/audience với precondition, stop condition và người duyệt |

Không có các mục P0 thì trạng thái chính xác là **RAG POC tham khảo**, không phải “RAG Vinhomes hoàn chỉnh”. Độ phủ 16 mã của corpus là độ phủ **taxonomy/triage**, không phải 16 SOP hoặc 16 ca sửa thật.
