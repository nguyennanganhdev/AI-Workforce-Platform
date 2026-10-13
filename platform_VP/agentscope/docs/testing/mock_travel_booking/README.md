# Chạy và kết nối Mock Travel Booking MCP

Hướng dẫn cho môi trường Linux hiện tại: backend AgentScope chạy bằng Docker, MCP mock chạy trực tiếp trên máy. Ngày kiểm tra: 2026-10-13.

## 1. Trạng thái đã kiểm tra

- MCP đang chạy trên cổng `8010`, lắng nghe `0.0.0.0`.
- Health trên máy: <http://127.0.0.1:8010/health>.
- URL để nhập trong ứng dụng Docker: `http://172.17.0.1:8010/mcp`.
- Backend đã kết nối, xác thực và đọc được **23 tool** qua URL này.
- `host.docker.internal` chưa phân giải được trong container hiện tại; không dùng tên này trên máy này nếu chưa cấu hình thêm.
- Bộ test có sẵn của mock: **10 test pass**.
- Tất cả booking là giả lập trong RAM, không đặt dịch vụ thật. Restart MCP sẽ làm mất booking và khôi phục tồn kho.

## 2. Khởi động lại khi cần

MCP đã được chạy trong phiên hỗ trợ này. Chỉ chạy các lệnh sau khi instance cũ đã dừng, tránh lỗi cổng bị chiếm.

```bash
cd "/home/dongg/Bản tải về/AI-Workforce-Platform/mock_travel_booking_mcp"
uv sync --frozen
uv run --frozen mock-travel-mcp
```

Giữ terminal chạy server. Nếu chạy theo cách trên, nhấn `Ctrl+C` để dừng.

File `.env` trong thư mục MCP đã có `API_KEY`, `HOST=0.0.0.0`, `PORT=8010`. Không dùng `.env` của AgentScope thay cho file này. Không đưa API key vào prompt hoặc tài liệu KB.

Kiểm tra ở terminal khác:

```bash
curl http://127.0.0.1:8010/health
```

Kết quả phải có `status: ok`, `tool_count: 23`, `mcp_path: /mcp`.

## 3. Kết nối trong giao diện

1. Mở <http://localhost:5173/mcp>, chọn **Kết nối MCP đối tác**.
2. Điền **Mã MCP**: `mock_travel`.
3. Điền **Tên hiển thị**: `Mock Travel Booking`.
4. Điền **MCP URL**: `http://172.17.0.1:8010/mcp`.
5. Copy giá trị `API_KEY` từ `mock_travel_booking_mcp/.env` vào trường API Key.
6. Chọn **Authorization: Bearer**, rồi **Kiểm tra và cài đặt**.
7. Kiểm tra thông báo đã đăng ký 23 tool và MCP ở trạng thái bật. Nếu đã cài trước đó, dùng đồng bộ/Sync để cập nhật catalog.

URL `/mcp` là endpoint giao thức MCP, không phải trang web. Mở bằng trình duyệt có thể nhận 401/405/406; dùng `/health` để kiểm tra server còn chạy.

`127.0.0.1` bên trong container là chính container, không phải máy host. IP `172.17.0.1` đã được kiểm tra trong môi trường hiện tại; kiểm tra lại nếu đổi Docker network hoặc chuyển máy.

## 4. Nạp KB thử nghiệm

Tạo một KB tên **Travel Demo Policies**, mô tả: "Hồ sơ và quy tắc giả lập DL-FAM-04; giá và tồn kho lấy từ MCP".

Chỉ upload bốn file trong thư mục [kb](kb/):

- [01_customer_profile.md](kb/01_customer_profile.md)
- [02_booking_policy.md](kb/02_booking_policy.md)
- [03_hotel_and_transport.md](kb/03_hotel_and_transport.md)
- [04_dining_and_budget.md](kb/04_dining_and_budget.md)

Không upload README hoặc CASE_E2E.md: hai file này có lời giải mong đợi, làm mất ý nghĩa kiểm tra retrieval.

Ở màn hình Knowledge:

1. Tạo KB, chọn một **embedding model** mà credential được quyền gọi. Chat model `qwen3.5-flash` không phải embedding model. Nếu danh sách của credential có `text-embedding-v4`, có thể chọn model đó; việc chat chạy được chưa chứng minh embedding cũng được cấp quota/quyền.
2. Chọn dimension và chunker có sẵn trên form, giữ cấu hình mặc định cho lần test đầu.
3. Upload bốn file `.md` rồi đợi từng file có trạng thái **ready** và có chunk.
4. Dùng Knowledge Search hỏi "Hồ sơ DL-FAM-04 có những yêu cầu nào?". Phải tìm được dữ liệu từ file 01; nếu không, xử lý indexing/embedding trước khi test team.
5. Mở một chat/session, vào panel **Knowledge**, tick KB này. KB được gắn **theo session**, không tự áp dụng cho mọi agent.

Backend hiện dùng Qdrant trong RAM. Sau khi restart backend, cần kiểm tra search/index và reindex tài liệu nếu vector không còn; đừng chỉ dựa vào nhãn `ready` trong metadata.

## 5. Builder hiện đang làm gì?

Luồng giao diện hiện tại đi qua `src/agentscope/app/_router/_workforce_console.py`.

- Đọc MCP đang bật và `discovered_tools` để lập catalog; chọn đúng ID tool đã đăng ký.
- Bước đầu sinh outline: tên agent, mục tiêu và danh sách tool gợi ý.
- Sau khi người dùng xác nhận outline, backend giữ nguyên tên, mục tiêu và toàn bộ tool đã duyệt. Model chỉ viết system prompt, tên skill và nội dung một `SKILL.md` mới cho từng agent trong plan.
- Kiểm tra đủ agent, độ dài prompt/skill và tool theo plan còn khả dụng, không trùng giữa các agent. Chỉ gợi ý tái sử dụng agent cũ khi nghiệp vụ tương đồng và bộ tool khớp hoàn toàn; tương đồng không bỏ qua Eval.
- Khi Publish: đối chiếu lại plan, catalog và tool của agent tái sử dụng trước khi lưu. Agent mới được đánh dấu published/invitable, tạo primary session, gắn MCP với allowlist đầy đủ và cài skill mới vào workspace. Agent được tái sử dụng không đi qua nhánh tạo/cài mới.

System prompt hiển thị là phần vai trò nghiệp vụ do Builder viết, ngắn gọn và cùng ngôn ngữ với yêu cầu. Chính sách runtime được hệ thống bổ sung khi chat. Với cấu hình cũ không lưu kèm plan, cần lập/chốt lại plan rồi sinh cấu hình mới.

**Chưa có trong luồng này:** tự tìm/gắn KB, đọc/chọn skill có sẵn trong library, sinh nội dung KB, hoặc thực thi một bài test booking end-to-end để chứng minh agent hoạt động. Nhãn Eval đạt hiện là kết quả kiểm tra cấu hình, không phải xác nhận đã chạy thành công dịch vụ.

Model được chọn trên form Builder được lưu vào primary session của agent mới. Context/ReAct/permission do cấu hình hệ thống cố định, không để LLM tự chỉnh.

Build "team" ở đây tạo một loạt agent độc lập. Nhóm làm việc thực tế được Leader tạo/mời khi xử lý ticket; Builder không tạo sẵn một team cố định.

Skill có sẵn có thể được thêm thủ công qua panel **Skill → Add from library** của agent. Skill mới do Builder tạo đã được cài tự động. Đừng nhầm việc thêm skill vào library với việc gắn skill vào workspace của agent.

KB của primary session **không được copy tự động** vào session mới do `AgentInvite` tạo. Muốn test retrieval ở từng thành viên, mở đúng session của thành viên trong Team và tick KB tại đó. Skill của cùng agent/cùng workspace được dùng lại; danh sách MCP/tool được copy vào session team.

## 6. Bài test từ Builder đến chat nhóm

Làm theo [CASE_E2E.md](CASE_E2E.md): prompt chỉ mô tả nhu cầu du lịch và quyết định của khách. Builder tự chia agent; Leader tự chọn thành viên, tool và cách phối hợp. Bước gắn KB vẫn làm thủ công. Đáp án và tiêu chí kiểm tra đặt riêng ngoài prompt, không gửi cho model.

## 7. Các lỗi thường gặp

- **Connection refused/timeout**: MCP đã dừng, sai port, hoặc URL từ Docker không tới host. Kiểm tra `/health` trước và giữ `HOST=0.0.0.0`.
- **401**: sai API key/kiểu xác thực. Key phải lấy từ `.env` của MCP, không phải key Qwen.
- **406 khi tự curl /mcp**: client chưa gửi đúng header Accept/giao thức MCP. Kết nối bằng client MCP hoặc form đối tác, không coi curl GET thông thường là bài test MCP.
- **Address already in use**: đã có instance chạy ở cổng 8010; không chạy thêm instance thứ hai.
- **Builder thấy 0 tool**: chưa cài MCP ở cấp library, MCP đang tắt hoặc discovery lỗi. Chạy Sync và kiểm tra 23 tool trước khi Build.
- **Builder Not Found/404**: backend chưa có route Builder; cần rebuild backend gốc trước lớp Ollama. Chỉ rebuild lớp Ollama trên image gốc cũ không cập nhật source.
- **Plan có tool nhưng cấu hình vẫn thiếu, prompt vẫn có đoạn chính sách tiếng Anh**: kiểm tra container có chạy source mới không. Kết quả đã lưu trong hội thoại cũ không tự sinh lại khi cập nhật backend; cần chốt/sinh cấu hình mới.
- **KB không có kết quả**: kiểm tra model embedding, trạng thái document, chunk, search và KB được tick ở đúng session. Restart backend có thể mất vector do Qdrant in-memory.
- **Agent không vào nhóm**: kiểm tra đã Publish và invitable, dùng cùng tài khoản tạo agent; hướng dẫn Leader mời đúng tên agent đã phát hành.
- **Ngày trong quá khứ**: thay toàn bộ ngày trong hồ sơ và case cùng nhau thành ngày tương lai trước khi upload lại KB.

Log MCP của phiên đang chạy: `/tmp/mock-travel-booking-mcp.log`.

Khi sửa source backend và đang dùng `compose.override.yaml` cho Ollama, chạy từ thư mục `platform_VP/agentscope` theo thứ tự:

```bash
docker compose -f compose.yaml build app
docker compose -f compose.yaml -f compose.override.yaml build app
docker compose -f compose.yaml -f compose.override.yaml up -d --no-deps app
```
