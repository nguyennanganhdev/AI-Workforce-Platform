# Workforce end-to-end tests

Chủ sở hữu lane: **Phan Hoàng Dũng**.

Các test tại đây kiểm chứng luồng toàn lát cắt, gồm Customer POST, ticket/group,
Leader, workflow, tool/external operation, Provider Event, event log/SSE và
customer close. D5 sử dụng production SQL repositories, ASGI router và durable
worker; chỉ model/provider boundary được thay bằng deterministic fake.

`async_tickets/test_full_platform.py` mặc định dùng
`tests.workforce.fixtures.release_candidate_factory:factory`. Có thể đặt
`WORKFORCE_E2E_FACTORY` sang factory của sandbox/deployment thật nếu factory đó
giữ cùng contract kiểm thử.

Không được gọi test fake là sandbox evidence. D7 chỉ ghi sandbox đã xác minh
khi có endpoint, credential và kết quả chạy thật tương ứng.
