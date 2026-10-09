# Bằng chứng nghiệm thu local — 2026-10-09

## Đã kiểm tra

- `uv run ruff check vp tests`: pass.
- Backend PostgreSQL riêng `vp_platform_test`: **37 passed**, gồm 20 session hoạt động qua 8 worker, 60 task AgentScope và chặn phiên thứ 21; context tách phiên; dedupe, stale lease, ngân sách đồng thời, owner revocation, MCP approval/config drift/success recovery, private memory/KB, quote/expiry/revocation, retry an toàn, controlled rate delays, evaluation merge, session/wallet lock interleaving, workflow human gate, scheduler đồng thời và webhook payload dedupe.
- Provider constructor kiểm tra 6 adapter: output cap không bị bỏ qua, SDK retry tắt; OpenAI/Responses/Anthropic/DashScope transport retry tắt. Đây là constructor checks, chưa xác nhận provider nhận request thật.
- `pnpm build`: TypeScript và production Vite build pass.
- Playwright: tạo model → tạo agent → policy test → publish → session → AgentScope structured result needs_input → context inspector → KB upload/index/search → mobile navigation 375px. API/DB/SDK thật, riêng provider I/O được thay bằng fixture; không có lỗi JS trong luồng.
- Semantic index/query đi qua SDK embedding thật và persistent Qdrant local engine với provider I/O fixture: query không trùng keyword vẫn lấy được nguồn, query embedding có reservation/usage, document bị thu hồi không được lấy nữa. Qdrant HTTP container cũng đã qua synthetic create/upsert/query/delete riêng; client lock 1.14.3 tương thích server 1.13.6.
- Compose độc lập: PostgreSQL, Redis, Qdrant, API, worker và web. Không thay đổi source vendor AgentScope hoặc checkout Vinhomes đang có thay đổi.
- HTTP bytes của `index.html` khớp local production artifact; SHA-256 `06c471f4992c837f2f37d68d0b4adad7ebf2f48ee0a5ae0e36d45353e8f43e9d`. Source runtime trong container khớp host, `/api/health` trả OK. Không suy ra provider thật hoạt động từ health endpoint này.
- Browser trên stack Docker cổng 3080 đăng nhập bằng tài khoản local đã sinh, mở được màn hình vận hành; **0 lỗi JavaScript**. Worker heartbeat xác nhận một tiến trình có pool 8 worker; Qdrant HTTP probe với client/server đã khóa phiên bản không còn cảnh báo compatibility.

Chi phí paid API dùng để kiểm tra: **$0**. Không dùng khóa/provider của Vinhomes. Các fixture chỉ nằm trong tests, không seed vào DB chạy thật.

## Cần nghiệm thu khi có cấu hình thật

1. Khóa/model/provider đích: structured output, tools, tiếng Việt, fallback, quota và hóa đơn thực tế. Giá/capability catalog do admin khai báo, không được tự xác nhận bằng fixture.
2. Chất lượng coordinator/specialists với bộ bài toán và tài liệu chuẩn của tổ chức, bao gồm bất đồng, thông tin thiếu/sai, nguồn mâu thuẫn và injection. Kiểm tra nguồn có thật không thay thế xác minh tính đúng của nội dung.
3. Embedding provider + Qdrant với corpus thật: recall, dimension, model/version isolation, query cost và thu hồi quyền. Keyword indexing/retrieval đã có test; chưa benchmark semantic retrieval chất lượng thực.
4. MCP server thực với công cụ read-only và write sandbox; đối soát effects khi timeout, credential rotation, mạng và endpoint policy. Fake MCP test chứng minh broker invariant, không chứng minh server bên ngoài tuân thủ annotation.
5. 20 session với latency/quota provider thực và tài liệu thật. Test hiện tại chứng minh queue/context/concurrency trên PostgreSQL và actual SDK loop, không phải SLA 20 request LLM đồng thời hoặc soak test dài ngày.
6. HTTPS, secrets quản lý ngoài file local, backup/restore drill, retention/purge dữ liệu, nâng cấp schema, giám sát hạ tầng và security review trước khi mở public.
7. Jev shadow trên bộ dữ liệu giả/ẩn danh tiếng Việt có nhãn. Hiện tắt mặc định, chưa gọi API và chưa được dùng để quyết định runtime.

CI đã có workflow scoped nhưng chưa push/chạy GitHub Actions trong lần triển khai local này. Không đánh đồng local pass với nghiệm thu production.
