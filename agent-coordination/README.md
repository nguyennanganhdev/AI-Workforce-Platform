# Agent Coordination

Điều phối các Agent cho dự án Vinhomes BQL.

## Tiến độ DEV-5 (Integration Owner)

**Đã hoàn thành:**
- Thiết lập cấu trúc service cơ bản với **FastAPI** (`src/main.py`), bao gồm endpoint `/health`.
- Tích hợp quản lý cấu hình bằng `pydantic-settings` (`src/config.py`).
- Cấu hình đầy đủ file `requirements.txt`, cài đặt thành công `agentscope`, `fastapi`, `uvicorn`, `pydantic`.
- Dựng các thành phần Mock (giả lập) để thay thế tạm thời phần việc của DEV-1, DEV-2, DEV-3, DEV-4 (như `InMemoryStateStore`, `MockAuthority`, `MockParticipantResolver`, `FakeBackendBridge`...) nhằm chạy thử luồng mà không bị block.
- Khởi tạo kết nối Model qua `AgentScopeModelClient` với cơ chế fallback tự động về Mock khi thiếu API Key.
- Khai báo và chuẩn bị sẵn `Dockerfile`, `pyproject.toml`.

**Tình trạng phần việc của DEV 1, 2, 3, 4:**
- **DEV-1 (Điều phối/Supervisor)**: Đã tạo các file cốt lõi như `approval_flow.py`, `service.py`, `planner.py`, `reception_flow.py` trong thư mục `src/supervisor/`.
- **DEV-2 (Phòng họp/Groupchat)**: Đã phát triển cấu trúc `room.py`, `messaging.py`, `mailbox.py` trong `src/groupchat/`.
- **DEV-3 (Core API/Gateway)**: Đã xây dựng `agentscope_adapter.py`, cùng các thư mục `backend`, `reception` trong `src/adapters/`.
- **DEV-4 (Lưu/Phục hồi)**: Các file đang dần thành hình tại thư mục `src/persistence/`.
*(Nhìn chung, các DEV khác đã đẩy code cấu trúc và logic lên thư mục tương ứng. Tuy nhiên, DEV-5 vẫn đang dùng Mock trong `main.py` để cô lập lỗi, đảm bảo an toàn.)*

**Công việc tiếp theo của DEV-5 (Và giải đáp test nối luồng):**
1. **Chạy Endpoint qua Port để test nối các luồng**: **CÓ**, bạn chắc chắn cần chạy server để test API. 
   - *Cách chạy môi trường ảo & Server:* 
     Bật terminal tại thư mục `agent-coordination` và gõ:
     ```bash
     .venv\Scripts\activate
     cd src
     uvicorn main:app --host 0.0.0.0 --port 8000 --reload
     ```
   - *Mục đích:* Dùng Postman hoặc cURL gọi vào để đảm bảo framework chạy đúng, luồng tích hợp không bị crash.
2. **Viết Integration Test**: Chủ động tạo các test case xuyên suốt (từ Lễ tân -> DEV-3 -> DEV-1 -> DEV-2) ở thư mục `tests/integration/` dựa trên bộ Mock.
3. **Tháo Mock - Gắn Real Code**: Theo dõi tiến độ của DEV 1, 2, 3, 4. Khi họ hoàn tất, tiến hành thay thế các `FakeBridge` và `MockClass` trong `main.py` bằng code thật import từ các thư mục của họ. Tuyệt đối không tự sửa code bên trong thư mục của họ để tránh conflict.
