# Generic Python runtime

Owner: Runtime / Platform. Python 3.11+.

Đã có TypedDict và `RuntimeAdapter` Protocol; chưa có runtime service hoặc AgentScope execution.
Chạy syntax/import smoke từ repo root: `npm run check:runtime`.

Team Runtime thêm `src/main.py` làm composition/transport root, chọn service framework và
lock dependency AgentScope **2.0** tương thích sau kiểm tra SDK. Chỉ
`src/runtime/agentscope_adapter.py` import SDK; không để SDK type lọt vào shared contract.
Các operation trong Protocol là create_session, execute_step, checkpoint, resume, cancel, stream_events.

Transport phải xác thực service và tenant/session scope; domain prompt/context mapper được inject
từ `src/domain_adapters/vinhomes.py` khi triển khai. Không truy cập business tables để sửa Incident/Task.
Runtime chỉ READ/ANALYZE/PROPOSE; domain thực thi WRITE sau grant.

Thêm Dockerfile và deployment sau khi có executable service. Không có fake AgentScope adapter trong scaffold.
