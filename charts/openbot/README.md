# OpenBot deployment integration

Owner: Data/DevOps. Thư mục dành cho Helm conventions từ OpenBot fork khi upstream được nhập.
Chưa có chart, Dockerfile hoặc Compose chạy được; không có lệnh deploy cho scaffold.

Khi triển khai, quản lý Hono/UI, Python runtime, MCP services, PostgreSQL, Qdrant và object storage
theo conventions upstream. Health/readiness, secret/service identity và network access được cấu hình theo service.
