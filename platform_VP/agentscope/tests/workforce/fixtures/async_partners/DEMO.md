# Mock partners — chỉ dành cho test

`CustomerBackend` gọi API platform thật qua `httpx.AsyncClient` được inject; không dựng bản Orchestration giả thứ hai. Nó lưu mapping theo từng ticket/hộp chat và gửi request/reply/approval/close với ID riêng. `ProviderBackend` dùng credential purpose khác để gửi event và đọc receipt. `TicketEventClient` giữ cursor riêng từng conversation, dedupe message đã có trên POST, và chỉ advance cursor sau khi handler thành công.

Luồng dùng sau khi Chí Hoàng bàn giao app/worker factory:

1. Tạo CustomerBackend với client trỏ ASGI app hoặc sandbox được cấp, header credential test, user và management ref đã grant.
2. `await customer.start('TICKET-A', 'CHAT-A', text, 'A1')`; mở TICKET-B/CHAT-B cùng user với ID B1.
3. Dùng `customer.tickets[ticket]['next_action']`: submit_reply → `reply`; submit_approval → `approve`; confirm_close → `close`; none → dừng. Chỉ watch_request/watch_events cần polling/stream.
4. Với operation pending, lấy job/correlation từ mock provider fixture, `await provider.send(envelope)`. Gửi assigned → on_the_way → completed với external_event_id và provider_version tăng; fixture normalizer dùng `FAKE.progress`.
5. Tạo một TicketEventClient mỗi ticket; `read_stream(..., max_events=2)` để mô phỏng ngắt. Gửi thêm event; `catch_up` đọc DB history từ cursor cũ, rồi nối SSE cùng conversation. Mất notification không làm client regenerate message.
6. Đọc revision mới từ GET request/snapshot trước close. `close('TICKET-A')` không được đổi ticket B. Operation chưa xong dùng `stop_tracking_only=True`, không gọi cancel tool.

Chạy mock MCP stdio độc lập: `python tests/workforce/fixtures/mock_mcp.py`. Server chỉ phục vụ test protocol stdio, không mở giao dịch/provider thật.

Kiểm tra client và lát cắt Execution hiện có:

```powershell
python -m pytest tests/workforce/execution tests/workforce/e2e -q
```

Các test `test_full_platform.py` cần `WORKFORCE_E2E_FACTORY=module:function` do composition owner cung cấp, trả async context manager với client, customer_headers, management_ref và các observation hooks nêu trong file test. Chưa có factory thì skip với lý do rõ; không coi đó là nghiệm thu toàn hệ thống.

