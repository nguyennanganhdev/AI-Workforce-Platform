# Học kinh nghiệm từ ticket: quy trình tự xử lý và khoảng giá tham khảo

## 1. Phạm vi được người dùng xác nhận

Hai năng lực cần triển khai:

1. Nhân viên kỹ thuật ghi quy trình sau khi xử lý ticket. Hệ thống lưu kiến thức lâu dài để Reception dùng lại cho sự cố nhẹ phù hợp, đề nghị cư dân tự thực hiện. Cư dân từ chối thì chuyển nhân viên; cũng chuyển khi không đủ điều kiện tự xử lý, không có quy trình phù hợp, làm không thành công hoặc phát sinh dấu hiệu cần kỹ thuật viên.
2. Ghi nhận chi phí thực tế sau sửa chữa để Reception trả lời **khoảng giá tham khảo**, phù hợp loại hỏng, phạm vi sửa và địa bàn. Không biến kinh nghiệm cũ thành báo giá chính thức.

Đây là **học kinh nghiệm có xác nhận + long-term knowledge memory + RAG + thống kê có cấu trúc**. Không cần reward, policy-gradient, fine-tuning hoặc RL training. Không tự sửa trọng số model sau mỗi ticket. Trong kế hoạch, cụm “học tăng cường” của nghiệp vụ được hiểu theo phạm vi này.

Ví dụ 500.000–1.000.000 đồng là số minh họa của người dùng, **không phải mức giá seed/mặc định**. Chỉ trả khoảng này nếu kết quả từ dữ liệu hợp lệ hỗ trợ.

Tài liệu là **đề xuất thiết kế**, chưa sửa schema TypeScript, catalog, migration hoặc database thật. Sáu bảng mới dưới đây đều do ứng dụng quản lý; LangGraph/AgentScope không tự tạo chúng.

## 2. Đối chiếu schema hiện có

| Bảng/nhóm hiện có | Tái sử dụng | Khoảng trống |
|---|---|---|
| `work_orders` | `diagnosis`, `repair_notes`, ticket và thời điểm hoàn thành | Ghi chú tự do chưa phải hướng dẫn cư dân; chưa có chi phí thực tế được xác nhận |
| `memory_candidates` | Nguồn ticket/run, scope/namespace, PII redaction, revision/hash | Có agent đề xuất nhưng thiếu người kỹ thuật trực tiếp viết và work order nguồn |
| `knowledge_reviews` | Người duyệt, subject hash/sequence, quyết định theo candidate/version | Cần kiểm tra đúng quyền kỹ thuật/phạm vi và đúng phiên bản nội dung khi publish |
| `memory_publications` | Liên kết candidate, review, document và version đã công bố | Không tạo pipeline publication thứ hai; thu hồi phải ảnh hưởng retrieval/cache |
| `knowledge_documents`, `document_versions` | Định danh và nội dung có phiên bản | Thiếu metadata chuyên biệt về điều kiện được tự sửa; `document_versions.file_id` đang NOT NULL |
| Scopes/ACL/grants, chunks/embeddings/retrieval | Chia sẻ kiến thức đã khử định danh đúng phạm vi; tìm và trích nguồn | Độ giống vector không đủ để quyết định cư dân được tự sửa hoặc để tính giá |
| `tickets` | `resolution_mode` đã hỗ trợ `guided` và `onsite` | Thiếu lịch sử đề nghị, chấp nhận/từ chối, kết quả và phiên bản hướng dẫn đã dùng |
| `ticket_reviews` | Đánh giá nhân viên theo assignment | Không phù hợp case tự sửa vì `assignment_id` và `staff_id` bắt buộc; không ép tạo nhân viên giả |
| `invoices`, `invoice_lines` | Có thể là nguồn đối chiếu nếu tương lai thực sự dùng hóa đơn | Không bắt buộc làm hóa đơn/thanh toán để học giá; tổng một hóa đơn nhiều việc không đại diện một loại sửa |

Long-term memory ở đây là kho quy trình đã tổng quát hóa, có version và scope. Không đưa raw chat, tên cư dân, số căn hộ, ảnh nhận diện hoặc hóa đơn riêng vào memory chung. Thread checkpoint vẫn phục vụ tiếp tục hội thoại; không phải kho tri thức học từ mọi khách hàng.

## 3. Luồng học và sử dụng quy trình

### 3.1. Kỹ thuật viên đóng góp

1. Nhân viên đang được phân công mở work order, ghi chẩn đoán, nguyên nhân/triệu chứng, bước thực hiện, điều kiện áp dụng, dấu hiệu phải dừng và kết quả kiểm tra sau xử lý. Quy trình có thể không phù hợp cho cư dân tự làm.
2. Hệ thống tự lưu bản nháp/candidate và nguồn ticket/work order, tác giả, revision/hash. Agent chỉ giúp biên tập; nhân viên xác nhận nội dung của mình.
3. Bộ kiểm tra dữ liệu yêu cầu đủ trường, khử PII và phát hiện quy trình tương tự. Bản sửa là revision mới; không ghi đè bản đã duyệt.
4. Người có thẩm quyền kỹ thuật theo scope xác nhận **có được dùng cho cư dân hay chỉ nội bộ**. Mặc định bản mới chưa được dùng tự động cho cư dân. Đây là kiểm soát chất lượng được đề xuất, không phải chờ duyệt mới được lưu.
5. Khi duyệt, backend publish nguyên tử vào document/version và memory publication; ghi outbox để ingestion tạo chunks/embeddings. Quy trình chỉ được phục vụ khi content và index đạt trạng thái sẵn sàng theo version được duyệt.

Quyền duyệt dựa trên permission và năng lực được tổ chức phân công, không mặc định mọi tài khoản management/admin đều có chuyên môn để duyệt hướng dẫn kỹ thuật. Chiến hiện thực permission; BQL cấu hình người phụ trách. Có thể cho tác giả đã được ủy quyền tự xác nhận theo policy của tổ chức; phải lưu rõ người và policy, không để LLM tự duyệt.

### 3.2. Reception hướng dẫn cư dân

1. Tiếp nhận và triage như bình thường; hỏi đủ dữ kiện để xác định loại sự cố và điều kiện áp dụng. “Severity thấp” không tự động có nghĩa được tự sửa.
2. Tool tìm quy trình published, đúng tenant/domain/scope/thiết bị, còn hiệu lực và cho phép resident self-help. Backend kiểm tra preconditions/contraindications/dấu hiệu dừng; trường quan trọng chưa biết thì hỏi tiếp hoặc chuyển người, không coi unknown là false.
3. Reception đề nghị cư dân có muốn được hướng dẫn không. Không ép cư dân chứng minh đã thử trước khi gọi kỹ thuật viên.
4. Cư dân đồng ý: tạo attempt pin version, ghi nhận facts và triage decision tại thời điểm bắt đầu; hướng dẫn theo các bước đã duyệt, không tự sáng tác thao tác chuyên môn ngoài tài liệu.
5. Cư dân từ chối: ghi declined, chuyển onsite/dispatch ngay theo workflow hiện hữu. Khi thất bại, timeout, xuất hiện dấu hiệu mới hoặc người dùng yêu cầu dừng cũng phải handoff.
6. Thành công do cư dân xác nhận: ghi outcome và event; backend xét điều kiện chuyển ticket resolved/closed. Không đánh dấu thành công chỉ vì agent đã gửi hết hướng dẫn.

Chờ cư dân không tự động dừng SLA. Nếu cần pause, dùng quy tắc và audit SLA V3; không kéo dài thời hạn ngầm để tăng tỷ lệ tự xử lý. Nếu quy trình bị thu hồi giữa phiên, dừng hướng dẫn và đánh giá lại/handoff.

## 4. Luồng học và trả lời giá

1. Sau sửa chữa, nhân viên nhập chi phí đã xác nhận của **một work order/phạm vi sửa rõ ràng**: tiền công, vật tư, phụ phí, thuế và giảm giá; ghi tình trạng thiết bị, chẩn đoán, địa bàn, ngày thực hiện và căn cứ.
2. Backend kiểm tra số học, nguồn, quyền người nhập/xác nhận và chống trùng. Giá ước đoán, báo giá chưa thực hiện, số model sinh và ticket hủy không thành mẫu actual cost.
3. Job tổng hợp chọn mẫu cùng nhóm so sánh: domain/loại sự cố hoặc chẩn đoán, phạm vi sửa, nhóm thiết bị, scope địa bàn, tiền tệ, cách tính thuế/vật tư, khoảng thời gian. Không gộp thay cả thiết bị với thay một linh kiện chỉ vì cùng từ “bồn cầu”.
4. Tạo reference version với danh sách mẫu, số ca độc lập, thời gian, thuật toán và policy lọc/outlier đã pin. Loại outlier theo quy tắc có lý do, không để LLM tự loại giá không thích.
5. Quyền công bố bảng giá tham khảo do backend kiểm tra. Khi hỏi, Reception dùng tool structured estimate; tool trả khoảng, đơn vị, điều kiện bao gồm/không bao gồm, thời hạn dữ liệu và mức đủ dữ liệu. RAG có thể giải thích nguyên nhân, nhưng không được dùng phép đoán từ embedding để tự tính tiền.
6. Thiếu mẫu, mô tả chưa đủ phân biệt phạm vi sửa hoặc mẫu đã cũ: hỏi thêm hoặc nói chưa đủ dữ liệu để ước lượng; không tạo khoảng giá mặc định. Nếu có bảng giá được BQL xác nhận thì phải ghi đó là nguồn khác, không giả là thống kê ticket.

MVP có thể dùng phân vị hoặc min/max sau lọc với ngưỡng số mẫu; **không chốt một công thức/ngưỡng tùy ý cho mọi nhóm**. Quang đề xuất bằng dataset, Chiến lưu policy có version, người phụ trách nghiệp vụ chấp thuận. Khoảng lịch sử không phải confidence interval hay bảo đảm giá tương lai.

Câu trả lời mẫu có điều kiện: “Với nhóm sửa [phạm vi] tương tự tại [khu vực], mức tham khảo khoảng [lower]–[upper] [currency], [bao gồm/không bao gồm]. Giá thực tế cần kỹ thuật viên kiểm tra.” Chỉ dùng số do tool trả; không công khai chi phí/căn hộ của một cư dân cụ thể. Ngưỡng mẫu độc lập và quyền công bố tổng hợp cũng là điều kiện chống suy ngược dữ liệu cá nhân.

## 5. Thay đổi bảng hiện có

### 5.1. `memory_candidates` — bổ sung thông tin người đóng góp

| Cột đề xuất | Kiểu | Quy tắc |
|---|---|---|
| `candidate_kind` | TEXT | `general`/`repair_procedure`; default `general` cho dữ liệu cũ |
| `submitted_by_user_id` | TEXT NULL, FK users | Người xác nhận gửi candidate; bắt buộc với procedure do nhân viên đóng góp; user ID hiện là text |
| `source_work_order_id` | UUID NULL, FK work_orders | Bắt buộc với procedure rút từ sửa chữa thực tế; phải cùng ticket/tenant |
| `structured_content` | JSONB NULL | Payload quy trình theo schema_version; bắt buộc và validate với repair_procedure |
| `content_schema_version` | TEXT NULL | Version schema để đọc payload cũ |

Giữ `proposed_by_agent_id` nếu agent hỗ trợ soạn, nhưng không thay tác giả người thật. Hash duyệt phải bao phủ cả prose, structured content, nguồn và phạm vi áp dụng. Candidate được submit/duyệt không sửa nội dung; thay đổi tạo candidate revision mới. Dữ liệu ứng dụng đóng vai trò kiểm chứng nghiệp vụ, không gọi đây là framework memory table.

### 5.2. Những bảng chưa cần đổi

- Giữ `tickets.resolution_mode = guided/onsite`; không thêm giá trị `self_help` gây trùng nghĩa. Lịch sử và kết quả chi tiết nằm ở attempt/event.
- Giữ chain knowledge review/publication; không tạo thêm bảng “learned memory” chứa bản sao không có governance.
- `document_versions.file_id` giữ NOT NULL: khi publish nội dung nhân viên gõ, backend lưu canonical JSON/Markdown đã khử PII thành object nội bộ S3/MinIO qua file service rồi tạo document version. Cách này tái sử dụng pipeline hiện tại, không giả có file ID. Chỉ khi đổi mô hình inline content có chủ đích mới cần migration riêng.
- Không dùng `ticket_reviews` cho self-help, không bắt buộc invoice/payment/refund. Giữ schema các bảng tài chính đã có nhưng không triển khai chúng chỉ vì task này, và không tự drop bảng.

## 6. Sáu bảng mới đề xuất

Quy ước: tất cả có `tenant_id UUID NOT NULL`, FK tenant-composite cho tài nguyên tenant, UUID PK mặc định, timestamp TIMESTAMPTZ; user FK là TEXT. `created_at` bắt buộc. Bảng có trạng thái mutable thêm `updated_at`/`lock_version BIGINT`. Quyền theo scope/work order được enforce tại service cùng RLS. Không dùng float cho tiền; không hard-delete nguồn đang được tham chiếu.

### 6.1. `repair_procedure_versions` — profile có cấu trúc của document version

| Cột chính | Kiểu/ràng buộc | Ý nghĩa |
|---|---|---|
| `id`, `tenant_id` | UUID PK; tenant FK | Định danh |
| `document_version_id` | UUID NOT NULL, UNIQUE theo tenant, FK document_versions | Một profile cho một phiên bản hướng dẫn; không tạo version counter song song |
| `source_candidate_id` | UUID NOT NULL, FK memory_candidates | Candidate đã duyệt và nguồn tác giả/work order |
| `domain_id`, `category_id`, `incident_type_id` | UUID FK; incident_type nullable nếu có lý do chưa phân loại | Phân loại áp dụng |
| `equipment_class`, `diagnosis_code`, `repair_scope_code` | TEXT, mã từ taxonomy versioned | Phân biệt nhóm thiết bị, dạng hỏng và phạm vi xử lý |
| `audience` | TEXT: `resident`/`technician` | Ai được hướng dẫn thực hiện |
| `preconditions`, `contraindications`, `stop_conditions` | JSONB NOT NULL | Structured rule/facts schema, không phải chuỗi “an toàn” tùy ý |
| `steps`, `required_tools`, `success_checks` | JSONB NOT NULL, versioned schema | Bước có thứ tự, công cụ cần có, kiểm tra sau thực hiện |
| `content_schema_version`, `content_hash` | TEXT NOT NULL | Hash bao gồm instructions và điều kiện; khớp content được review |

Eligibility và hiệu lực lấy từ publication/document version/review và metadata trên; **không thêm `approved=true` riêng** làm nguồn trạng thái thứ hai. Profile bất biến; sửa steps/điều kiện/audience phải tạo document version và approval mới. Bản canonical file và profile phải cùng hash nội dung chuẩn hóa; không cho phép sửa hai bản độc lập. Source candidate, publication, review và document version phải khớp nhau.

### 6.2. `ticket_self_help_attempts` — mỗi lần đề nghị/hướng dẫn cư dân

| Cột chính | Kiểu/ràng buộc | Ý nghĩa |
|---|---|---|
| `id`, `tenant_id`, `ticket_id` | UUID FK | Ticket đã xác minh |
| `ticket_generation`, `attempt_no` | INT >= 0 / INT > 0 | Tách ticket mở lại; UQ tenant/ticket/generation/attempt_no |
| `customer_user_id` | TEXT FK NOT NULL | Khách yêu cầu; phải được phép xử lý ticket |
| `procedure_version_id` | UUID FK NOT NULL | Pin quy trình đã dùng |
| `runtime_binding_id`, `source_run_id` | UUID FK, nullable theo kênh | Correlation Reception; kiểm tra audience/customer khi có binding |
| `triage_decision_id` | UUID FK NOT NULL | Quyết định phù hợp tại thời điểm đề nghị, cùng ticket/generation |
| `eligibility_facts`, `eligibility_policy_version` | JSONB/TEXT NOT NULL | Snapshot dữ kiện tối thiểu và phiên bản bộ kiểm tra |
| `status` | TEXT | `offered`, `accepted`, `in_progress`, `declined`, `succeeded`, `failed`, `stopped`, `expired` |
| `offered_at`, `responded_at`, `finished_at` | Timestamp | Theo trạng thái; không suy luận im lặng = đồng ý |
| `outcome_reported_by`, `outcome_note` | TEXT user FK / TEXT nullable | Ai xác nhận và lý do; không coi agent là cư dân |
| `handoff_event_id` | UUID nullable FK ticket_events | Handoff nghiệp vụ; cùng ticket, không tạo thêm ticket để gọi kỹ thuật |
| `idempotency_key` | TEXT NOT NULL, UQ tenant/key | Chống trùng operation |

Partial UQ một attempt active (`offered/accepted/in_progress`) mỗi ticket/generation; check timestamp và transition ở service/DB. Ghi event cho mọi thay đổi state; outcome terminal bất biến, sửa sai bằng event/attempt mới. Không cần tracking từng click/bước ở MVP.

### 6.3. `repair_cost_observations` — chi phí thực tế của một phạm vi sửa

| Cột chính | Kiểu/ràng buộc | Ý nghĩa |
|---|---|---|
| `id`, `tenant_id`, `work_order_id` | UUID FK NOT NULL | Nguồn thực tế; ticket suy ra qua work order, không lưu ticket_id trùng |
| `revision_no`, `supersedes_observation_id` | INT > 0; UUID FK nullable | Correction tạo revision; UQ tenant/work_order/revision |
| `domain_id`, `scope_id`, `category_id`, `incident_type_id` | UUID FK | Nhóm so sánh; khớp nguồn ticket/location |
| `equipment_class`, `diagnosis_code`, `repair_scope_code`, `taxonomy_version` | TEXT NOT NULL | Chuẩn hóa điều kiện sửa; category/incident chưa chắc thì không đưa vào nhóm giá cụ thể |
| `performed_at`, `currency` | Timestamp; CHAR(3) | Thời điểm thực hiện và tiền tệ |
| `labor_amount`, `materials_amount`, `other_amount`, `tax_amount`, `discount_amount`, `total_amount` | NUMERIC(18,2) NOT NULL >= 0 | Total = labor + materials + other + tax - discount, total >= 0 |
| `cost_basis` | TEXT | MVP dùng `customer_charge_after_discount`; không trộn giá vốn với số tiền tính cho khách |
| `price_context`, `is_exceptional`, `exception_reason` | JSONB; BOOL; TEXT | Vật tư/quantity, bảo hành, miễn phí, phụ phí khẩn, ưu đãi; không gộp vào mẫu thường thiếu phân biệt |
| `recorded_by`, `verified_by`, `verified_at` | User FK; user FK/timestamp nullable | Người ghi và người đủ quyền xác nhận; xác nhận không đồng nghĩa khách đã thanh toán |
| `evidence_file_id` | UUID nullable FK files | Căn cứ chi phí, cùng quyền ticket; không bắt buộc hóa đơn tài chính |
| `status` | TEXT | `draft`, `submitted`, `verified`, `rejected`, `superseded`, `withdrawn` |
| `idempotency_key` | TEXT NOT NULL, UQ tenant/key | Chống nhập lặp |

Một work order chỉ có một observation `verified` hiện hành. Khi correction được verify, supersede bản trước trong cùng transaction. Không sửa amount/nguồn của bản verified; chỉ thay lifecycle có audit. Nếu work order chứa nhiều phạm vi khác nhau, tách work order hoặc không dùng mẫu đó để ước lượng cho một phạm vi nhỏ; không tự phân bổ tổng tiền bằng LLM. Đếm một nguồn work order độc lập một lần, không đếm các revision thành nhiều mẫu.

### 6.4. `repair_price_reference_versions` — khoảng giá được công bố

| Cột chính | Kiểu/ràng buộc | Ý nghĩa |
|---|---|---|
| `id`, `tenant_id`, `reference_key`, `version_no` | UUID; TEXT; INT > 0 | UQ tenant/key/version; key định danh nhóm, không do client tự gán |
| `domain_id`, `scope_id`, `category_id`, `incident_type_id` | UUID FK | Phạm vi tham chiếu |
| `equipment_class`, `diagnosis_code`, `repair_scope_code`, `taxonomy_version`, `currency`, `cost_basis` | TEXT/CHAR(3) | Dimension chuẩn hóa, phải đồng nhất với mẫu được chọn |
| `window_from`, `window_to`, `generated_at`, `expires_at` | Timestamp | Cửa sổ dữ liệu và hết hạn công bố; từ < đến |
| `algorithm_version`, `policy_snapshot`, `policy_hash` | TEXT; JSONB; TEXT | Quy tắc tương đồng, freshness, min independent samples, outlier và làm tròn |
| `lower_amount`, `upper_amount` | NUMERIC(18,2) | 0 <= lower <= upper; chỉ có khi đủ điều kiện công bố |
| `sample_count`, `independent_ticket_count` | INT >= 0 | Số mẫu sau lọc và số ticket độc lập; tính từ membership dưới đây |
| `inclusions`, `exclusions` | JSONB NOT NULL | Ví dụ có/không vật tư, phụ phí; không để model tự đoán |
| `status` | TEXT | `draft`, `published`, `insufficient_data`, `revoked`, `expired` |
| `published_by`, `published_at`, `revoked_at`, `revocation_reason` | User FK/timestamp/text | Xác nhận người được quyền công bố giá tham khảo |

Content và sample set bất biến sau publish. Partial UQ một published version mỗi tenant/reference_key; khi thay version phải retire bản cũ trong transaction. Hết hạn kiểm tra bằng thời gian thực khi query, không chỉ chờ job đổi status. Tính khoảng giá trước publish trong service xác định, không tính bằng prompt.

### 6.5. `repair_price_reference_samples` — truy vết mẫu tạo khoảng giá

| Cột chính | Kiểu/ràng buộc | Ý nghĩa |
|---|---|---|
| `tenant_id`, `reference_version_id`, `observation_id` | Composite PK/FK | Observation version cụ thể trong một lần tổng hợp |
| `selection` | TEXT `included`/`excluded` | Lưu cả mẫu ứng viên bị lọc để giải thích |
| `reason_code` | TEXT NOT NULL | Lý do chọn/loại theo policy |
| `created_at` | Timestamp | Audit |

Số mẫu được lấy từ included rows hợp lệ; policy mới tạo reference version mới. Mẫu chi phí riêng không được trả cho cư dân qua API reference. Nếu mẫu bị rút/sửa sau publish, invalidate reference/cache bị ảnh hưởng qua outbox và kiểm tra validity lúc phục vụ để tránh khoảng trễ job.

### 6.6. `repair_price_estimates` — lưu lần Reception trả lời giá

| Cột chính | Kiểu/ràng buộc | Ý nghĩa |
|---|---|---|
| `id`, `tenant_id`, `requester_user_id`, `channel_id` | UUID; user TEXT FK; channel TEXT FK | Người hỏi và hội thoại đã authorize |
| `ticket_id`, `ticket_generation` | UUID/INT nullable cùng nhau | Có thể chỉ hỏi giá, chưa tạo ticket; nếu có phải khớp ticket |
| `reference_version_id` | UUID FK nullable | Bắt buộc khi status estimated; NULL khi thiếu dữ liệu |
| `source_run_id`, `runtime_binding_id` | UUID FK nullable | Pin context nếu agent thực hiện |
| `query_facts`, `assumptions` | JSONB | Dữ kiện và giới hạn, không lưu PII thừa |
| `status`, `reason_code` | TEXT | `estimated`, `needs_clarification`, `insufficient_data`, `out_of_scope` |
| `lower_amount`, `upper_amount`, `currency` | NUMERIC/CHAR nullable | Bắt buộc khi estimated; là snapshot khoảng tool đã trả |
| `inclusions`, `exclusions`, `valid_until` | JSONB/timestamp | Không cho phép dài hơn expiry của reference |
| `response_template_version`, `idempotency_key`, `created_at` | TEXT; UQ tenant/key; timestamp | Tái dựng lời giải thích và chống lặp |

Estimate append-only. Snapshot số tiền phải được backend kiểm tra khớp reference và quy tắc rounding, không nhận số agent tự nhập. Đây không phải quote/order/invoice, không sinh nghĩa vụ thanh toán. API chỉ cho khách xem estimate của mình, kỹ thuật/BQL xem trong scope được giao.

## 7. Ràng buộc chung và index

- Mọi FK tenant-composite có referenced UNIQUE tương ứng; nguồn cùng tenant chưa đủ, còn phải cùng ticket/work order/domain/scope. Service kiểm tra ownership tại thời điểm submit, approve, retrieve, resume và estimate.
- Index procedure theo tenant/domain/category/incident + version; lọc published/ACL rồi mới xếp độ tương đồng. Index cost theo tenant/domain/scope/diagnosis/repair_scope/performed_at với status verified; index reverse samples(observation_id) để invalidate; index attempts(ticket_id,generation,status), estimates(requester_user_id,created_at).
- Idempotency và optimistic lock dùng cho mutation; outbox nối publish/ingestion/reference refresh/handoff. Job retry không nhân đôi observation, version hay assignment.
- Nội dung có PII phải được khử trước publication. Dữ liệu chi phí gốc chỉ nội bộ có quyền; công bố reference tổng hợp là permission riêng. Không chia sẻ chéo tenant mặc định; phạm vi dùng chung rộng hơn cần quy trình publish được cấp quyền.
- Registry của framework/checkpoint không thay đổi cho hai chức năng này. Không nhét giá tổng hợp vào checkpoint rồi coi đó là long-term memory.
- Sáu bảng mới cộng với 148 bảng hiện tại là 154 **nếu chỉ thêm phần này**. Tổng cuối có thể khác do các bổ sung groupchat/routing C02; không hardcode 154 vào test trước khi merge thiết kế. Cập nhật catalog/generator/schema/tests và migration tăng dần cùng nhau.

## 8. Phân công và nghiệm thu

**Quang phụ trách chính pipeline học kinh nghiệm/truy xuất và tổng hợp giá; Chiến phụ trách database, API, quyền, UI và transaction.** Hoàng sử dụng kiến thức trong Reception; Đông tổ chức yêu cầu ghi kinh nghiệm sau xử lý; Team 5 vận hành và kiểm thử. Không giao “RL training” cho Team 5 vì không có bài toán training trong phạm vi này.

Task bổ sung: C13 (schema/service/UI), Q07 (procedure learning), Q08 (price aggregation/tool), H07 (self-help/price dialogue), D07 (technical closeout contribution), P07 (E2E/recovery/evaluation). Chi tiết và dependency ở kế hoạch 5 team.

Điều kiện nghiệm thu bắt buộc:

1. Nhân viên ghi procedure từ work order thật, tự lưu draft; chưa xác nhận/published không được Reception hướng dẫn khách. Người không được phân công hoặc không có quyền không được gửi/duyệt thay.
2. Hai sự cố tương tự nhưng khác điều kiện áp dụng không bị gộp; sự cố cần người chuyên môn không đi vào self-help dù severity thấp hoặc retrieval score cao.
3. Khách từ chối lập tức đi đường onsite; khách thử không được, dừng giữa chừng hoặc quy trình bị thu hồi đều handoff đúng ticket. Không tạo assignment trùng khi event lặp.
4. Khách xác nhận thành công có event/outcome; không cần tạo staff/assignment giả. SLA không bị pause ngầm.
5. Giá từ work order đã xác nhận, đúng cost basis và nhóm sửa; revision/outlier/miễn phí/khuyến mại không làm sai số mẫu. Không gộp tiền tệ hoặc hai domain tự động.
6. Không đủ số mẫu độc lập, reference hết hạn, mẫu bị rút hoặc mô tả mơ hồ thì hỏi thêm/từ chối ước lượng; không hardcode khoảng 500.000–1.000.000.
7. Mọi khoảng đã trả truy ngược được version/policy/mẫu, nhưng cư dân không xem được nguồn chi phí riêng của người khác. Cache thu hồi đúng quyền.
8. Feedback self-help và sai lệch estimated-vs-actual được báo cáo để người phụ trách cải tiến procedure/policy; không tự nới điều kiện an toàn chỉ để tăng tỷ lệ không gọi nhân viên.

Không sửa/drop bảng refund trong task thiết kế này. Payment/refund không thuộc phạm vi triển khai đã xác nhận; dữ liệu actual cost không yêu cầu chúng.
