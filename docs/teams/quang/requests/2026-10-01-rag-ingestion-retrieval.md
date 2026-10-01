# Yêu cầu tích hợp: RAG ingestion và retrieval (Q03, Q04)

Gửi: Chiến (schema, authz, storage, mount), Team 5 (worker, seed)
Từ: Quang / Phúc
Code: `server/src/knowledge/**`, `worker/src/jobs/knowledge/ingest-directory-job.ts`

## Đã có

- Ingestion Markdown: front matter, chunk theo heading, embedding `text-embedding-3-large` rút xuống 1536 chiều (cosine), version theo `content_hash`, job idempotent, tombstone.
- Retrieval: lọc quyền trong cùng câu SQL trước khi xếp hạng vector, ghi `retrieval_runs`/`retrieval_hits`, trả `retrieval_run_id`.
- Đã chạy thật trên DB thử với bộ Ocean Park: 118 tài liệu, 348 chunk, ingest lần hai không đổi gì.

## Cần Chiến

1. **Seed `embedding_models`**: không cần, code tự upsert `openai / text-embedding-3-large / v1 / 1536 / cosine`. Chỉ cần xác nhận không có seed khác mâu thuẫn.
2. **Cây `access_scopes` cho Ocean Park.** Scope của `00-do-thi` phải là tổ tiên của mọi scope khác (cấp tenant), vì tài liệu đô thị áp dụng cho mọi phân khu. Tài liệu gộp nhiều tòa (M1/M2/M3) được gắn vào scope của từng tòa. `access_scopes` không có cột cha, nên code nhận `targetScopeId` và `ancestorScopeIds` đã tính sẵn từ authz service. Cần: (a) cách dựng scope đô thị → phân khu → tòa (b) hàm trả ancestors của một scope.
3. **`AuthorizedContext`** (xem `types.ts`): cần service cấp `userId`, `roleCodes`, `workspaceId`, `agentRunId`, `principalId`, `bindingId`. `retrieval_runs` bắt buộc các id này.
4. **Quy tắc `document_acl` đang giả định**: không có dòng ACL = mở cho mọi người thuộc scope; có `deny` khớp = ẩn; có dòng `allow` = chỉ principal khớp mới thấy. Xin xác nhận.
5. **`files`**: `document_versions.file_id` NOT NULL. Cần hàm đăng ký file nguồn (`registerFile`) qua storage adapter.
6. **`knowledge_categories`, `knowledge_bases`, `domains`**: cần id cho Ocean Park.
7. **Mount route** trong `server/src/app.ts`, một dòng:
   ```ts
   app.route("/internal/knowledge", createKnowledgeRoutes({ authorize, retrieval: { store: createRetrievalStore(database), embedder: createOpenAIEmbedder({ apiKey, baseUrl }) } }));
   ```
   `authorize` là port `AuthorizeKnowledgeSearch` (xem `server/src/knowledge/routes.ts`): nhận `Request` và `scopeId` cư dân chọn, trả `AuthorizedContext` + `knowledgeBaseId`, hoặc 401/403/409 `scope_required` kèm danh sách scope của cư dân. Cần Chiến chốt cách agent runtime xác thực khi gọi `/internal/*`. Hợp đồng gửi Hoàng: `docs/teams/quang/handoffs/2026-10-01-search-knowledge-cho-hoang.md`.
8. **Index vector** (HNSW) trên `knowledge_embeddings` khi dữ liệu lớn; hiện chưa cần.

## Cần Team 5

1. Nối `createIngestDirectoryJob` vào `worker/src/index.ts` (factory, không tự chạy lúc import). Cần `OPENAI_API_KEY` (và `OPENAI_BASE_URL` nếu có) trong môi trường worker.
2. Runtime DB role không được là superuser/BYPASSRLS (hiện `openbot` là cả hai), để RLS theo tenant có tác dụng.
3. Chạy test tích hợp: `TEST_DATABASE_URL=... bun test tests/knowledge/pg-store.integration.test.ts` (cần DB migrate riêng, role được `set session_replication_role`).

## Cập nhật 2026-10-01 (chunker `md-scope-3`, retrieval `acl-first-hybrid-2`)

- Đường dẫn phạm vi (`Vinhomes > sapphire > sapphire-1 > S1.01`) đứng đầu mỗi chunk khi embed và có trong `search_tsv`.
- Tìm kiếm hybrid: vector + từ khóa (`search_tsv`, có bản không dấu), gộp RRF, cả hai đều trong tập tài liệu được phép.
- Metadata (`don_vi`, `phan_khu`, `cum`, `toa`, `cap`, `loai`, `trang_thai`, `cap_nhat`, `chua_xac_minh`) và danh sách nguồn lưu trong `document_versions.extraction_config`, trả kèm mỗi kết quả. Không cần cột mới.
- `upsertDocument` chỉ thêm `document_scopes`, chưa gỡ scope cũ khi tài liệu đổi phạm vi. Cần Chiến xác nhận có cho phép module knowledge xóa dòng `document_scopes` không.
- `ingestDirectory({ prune: true })` lưu trữ (archive) tài liệu không còn trong thư mục. Chỉ bật cho knowledge base mà thư mục đó sở hữu.

## Dữ liệu dev trong `openbot` local (cập nhật 2026-10-01)

Mỗi người chạy Docker riêng, nên dữ liệu RAG được nạp vào `openbot` local của từng máy bằng `server/src/knowledge/cli.ts`. CLI dùng tenant có sẵn và tạo các dòng mã `rag-dev-…`: domain, category, knowledge base `rag-dev-ocean-park`, một scope `management` cho mỗi thư mục dữ liệu (thư mục `00-do-thi` dùng scope `tenant` có sẵn), một principal cho user có sẵn, một file record. Riêng một `runtime_session_bindings` và một `agent_runs` (cần cho audit `retrieval_runs`) được ghi khi tắt kiểm tra khóa ngoại, vì agent/runtime/channel cha chưa có. Khi Chiến tạo domain/kho/scope thật, cần thống nhất cách thay các dòng `rag-dev-…`.

Test tích hợp vẫn chạy trên DB test riêng (`TEST_DATABASE_URL`), theo quy tắc trong `server/tests/support/database.ts`.

## Cập nhật 2026-10-01: model `text-embedding-3-large`, ngưỡng 0.35 (retrieval `acl-first-hybrid-3`)

So trên bộ eval ocean-park-v1 (93 câu) với cùng dữ liệu:

| Chỉ số | 3-small, ngưỡng 0.25 | 3-large, ngưỡng 0.35 |
|---|---|---|
| recall@1 câu có đáp án | 73,5% | 82,4% |
| Câu gõ không dấu tìm được | 3/5 | 5/5 |
| Từ chối đúng câu lạc đề | 0/14 | 13/14 |
| Từ chối nhầm câu có đáp án | 0/68 | 2/68 |
| Lấy nhầm phạm vi | 0 | 0 |

Vẫn 1536 chiều, schema và trigger không đổi. Mỗi model có dòng `embedding_models` và vector riêng, không trộn. Chạy lại: `bun --env-file=../.env src/knowledge/eval.ts`.

## Còn mở

- Ngưỡng `minSimilarity` đã chốt 0.35 bằng bộ eval Q06 (`server/tests/knowledge/eval/ocean-park.v1.json`, 93 câu). Đo lại khi bộ câu hỏi lớn hơn hoặc khi đổi model.
- Q07/Q08 chờ C13 (6 bảng mới).
