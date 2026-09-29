# Phòng họp DEV-2

Module async quản lý một room cho tenant/ticket/generation, thi hành đúng một lượt do Điều phối chọn. Không chọn speaker, tự retry, auto-trigger từ tin nhắn, ghi nghiệp vụ hoặc tạo agent sản phẩm.

- `models.py`: payload v2, result phân biệt success/error, message, state snapshot.
- `ports.py`: resolver quyền/pin, invocation và state transaction nguyên tử.
- `room.py`: façade `RoomService.execute(Command)` / `query(Query)`; callback nội bộ `complete` có fencing.
- `participants.py`, `messaging.py`: kiểm member/version, shared transcript và reply correlation.
- `compat.py`: normalize v1 với authorized context/group/version mapping được truyền rõ.
- `../adapters/agentscope_adapter.py`: public primitive AgentScope 2.0.9; cần provider đã resolve Agent riêng theo binding, profile no-tools.

Production không có global dict, database connection hay fallback fake. DEV-3 xác minh quyền/binding; DEV-4 triển khai transaction/lease/dedup/checkpoint/provider bền vững; DEV-5 nội bộ Đông nối bootstrap/dependency. Fakes chỉ nằm trong `tests/groupchat/`.

Ví dụ gọi module và JSON Schema: [contract v2](../../../docs/teams/dong/agent-room-contract-v2.md). Lệnh kiểm thử: [README test](../../tests/groupchat/README.md). Quyền trước replay/history là trách nhiệm bắt buộc của resolver, không phải tin Context JSON là đã xác thực.
