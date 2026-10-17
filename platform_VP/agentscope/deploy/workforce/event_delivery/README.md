# Event delivery operations — Phase D

Chủ sở hữu: **Nguyễn Chí Hoàng**.

Thư mục này chứa tài liệu vận hành và cấu hình mẫu cho Customer API, SSE,
durable worker và Provider Event. Platform không chủ động gọi HTTP sang backend
đối tác; đối tác POST vào platform và theo dõi sự kiện qua SSE.

Các artifact hiện có:

- `proxy.example.conf`: cấu hình Nginx giữ kết nối SSE, không buffer/cache và
  truyền `Last-Event-ID`.
- `alerts.example.yml`: quy ước alert cho worker restart, durable job,
  provider quarantine và worker không tiến triển.
- `RUNBOOK.md`: migration, backup/restore, restart/recovery, replay SSE,
  rotation key và rollback.
- `RELEASE_CHECKLIST.md`: điều kiện bắt buộc để chốt D7 Release Candidate.

Giá trị trong các file là mẫu triển khai, không chứa credential thật. Khi đưa
lên môi trường cụ thể phải thay host, TLS, retention và ngưỡng alert theo SLO.
