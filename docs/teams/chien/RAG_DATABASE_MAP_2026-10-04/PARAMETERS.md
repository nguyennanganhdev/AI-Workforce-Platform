# Thông số nạp và truy xuất RAG

Thông số dưới đây được đối chiếu code ở checkout hiện tại và code trong `reference-code.zip` của backup. Các hằng số chính về model, parser/chunker/policy, giới hạn chunk và retrieval trùng nhau. Đây là cấu hình/code, không phải phép đo độ chính xác mới.

| Thông số | Giá trị | Ý nghĩa / nguồn |
|---|---|---|
| Provider / model / revision | openai / text-embedding-3-large / v1 | `embedding_models` trong snapshot |
| Kích thước vector | 1536 | Mỗi embedding có 1536 số; cột DB `vector(1536)` |
| Metric | cosine | SQL dùng `<=>`; similarity = 1 − cosine distance |
| Active | true | Retrieval chỉ dùng model đã active; không tự tạo/kích hoạt model |
| UNIQUE vector | chunk_id + model_id | Một chunk có tối đa một vector cho mỗi model; có thể nhiều model |
| Parser | md-frontmatter-1 | `types.ts` |
| Chunker | md-scope-3 | `types.ts` |
| Chunk tối đa mặc định | 1200 ký tự mục tiêu | `markdown.ts`; đóng gói theo đoạn/dòng, không phải cửa sổ token cố định |
| Ngưỡng gộp section ngắn | 150 ký tự | Gộp vào chunk trước nếu không vượt kích thước mục tiêu |
| Token count | ceil(text.length / 3), tối thiểu 1 | Ước lượng trong code, không phải số token nhà cung cấp tính phí |
| Embedding input | [scopePath · title · heading] + text | Hash vector dựa trên chuỗi này, không chỉ text_content |
| Không nạp | section todo, placeholder rỗng | Bullet trong mục nguồn trở thành citations; đoạn nguồn có fact được giữ |
| Batch embedding | 96 inputs | `embedder.ts`, có thể override |
| Max attempts embedding | 4 | retry ở adapter; khác retry HTTP bên Reception |
| topK mặc định / tối đa | 5 / 20 | `retrieve.ts`, request schema |
| Candidate mỗi danh sách | 20 | Vector và keyword riêng, rồi hợp nhất |
| Ngưỡng similarity | 0.35 | Hit dưới ngưỡng có thể ghi audit nhưng không đưa vào passages |
| RRF k | 60 | score = 1/(60+vectorRank) + 1/(60+keywordRank), thiếu nhánh thì 0 |
| Ưu tiên match rõ ràng | chênh similarity ≥ 0.15 | Đưa passage gần nghĩa vượt trội lên đầu |
| Scope weights | toa 1.03; cum 1.02; phan_khu 1.01; don_vi/do_thi 1 | `retrieve.ts` |
| Reliability weights | van_ban_bql 1.02; ghi_nhan_team/khong_ro 1; web 0.98 | Xếp hạng, không phải xác suất đúng |
| Chưa thu thập | ×0.9 | metadata.trang_thai = chua-thu-thap |
| Recency | ≤180 ngày: ×1.01 | `metadata.cap_nhat` |
| Retrieval policy | acl-first-hybrid-3 | Ghi trong audit/response |
| Query API RAG | 1..1000 ký tự | `/internal/knowledge/search` |
| Knowledge service local | 127.0.0.1:8787 | `serve.ts`, port có thể cấu hình |
| Authority timeout | 5 giây | `runtime.ts` |
| Reception graph | topK 5, timeout 15 giây; retry 502 tối đa 1 lần | `agent-reception/src/runtime/knowledge.py` |
| Reception loop | topK 5, timeout 15 giây; search không có vòng retry 502 | `agent-reception/src/agent/tools.py`; kết quả được model tổng hợp qua `loop.py` |
| Delegation | 600 giây; kiểm tra run/binding mỗi request | `reception_delegation.py`, token kết thúc hiệu lực khi run kết thúc |
| Operations keyword search | query 2..300 ký tự, limit mặc định 10/max 30 | `v3_knowledge.py`; không chạy vector retrieval |

Similarity không phải phần trăm độ tin cậy. `unverified`/reliability là thông tin nguồn; Lễ tân chỉ dùng passages và phải nêu chưa xác minh khi cần.

## Chính sách khác nhau giữa hai API

| Điều kiện | RAG Quang → Reception | Keyword API Chiến → Operations |
|---|---|---|
| Caller | Delegation agent được backend xác minh | Actor management/staff theo scoped_connection |
| Agent grant | Phải có agent_knowledge_grants | Không kiểm agent grant trong endpoint này |
| Địa bàn | Target scope + ancestors khi applies_to_descendants | Scoped role ở scope tài liệu trong truy vấn hiện tại |
| ACL deny khớp | Chặn | Chặn |
| Không có allow ACL | Cho nếu đủ scope và không bị deny | Yêu cầu có allow khớp; có thể không trả kết quả |
| Ranking | Vector + keyword + RRF + weights | search_tsv + ts_rank |
| Audit RAG | retrieval_runs và retrieval_hits | Không ghi hai bảng này trong endpoint |

`document_acl` có 0 dòng trong backup: không đồng nghĩa tài liệu public toàn hệ thống; RAG vẫn kiểm tenant, grant, residence, scope và version. Nhưng API Operations yêu cầu allow, nên không thể suy ra hai API có kết quả tương đương.

## Index và trigger

Các index thực tế được liệt kê riêng từng bảng trong `TABLE_DICTIONARY.md`. Snapshot có GIN index `knowledge_chunks_search_idx` trên search_tsv. `knowledge_embeddings` chỉ có B-tree PK/UNIQUE, không có HNSW/IVFFlat index. Truy vấn hiện tại lọc candidate rồi sắp xếp bằng cosine distance. Trigger `embedding_dimension` đối chiếu model 1536/cosine trước khi ghi embedding. Các trigger khác về immutability, version, namespace và audience được trích nguyên định nghĩa/function trong `schema-snapshot.json`.

`query_text_redacted` là tên cột. `retrieve.ts` hiện ghi query sau normalize/trim; việc loại PII thuộc policy caller. Tên cột không chứng minh đã thực hiện redaction.
