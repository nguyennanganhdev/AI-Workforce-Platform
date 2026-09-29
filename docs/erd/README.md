# Database và ERD

> Đang triển khai lại theo hai đặc tả P0. [Tracker](P0_REDESIGN_TRACKER.md) ghi phần đã làm, phần còn thiếu và kết quả kiểm chứng. ERD vật lý sinh từ schema hiện tại, chưa phải thiết kế P0 hoàn tất.

Một sản phẩm phát triển trực tiếp từ OpenBot, AgentScope qua runtime adapter, Vinhomes qua API. PostgreSQL giữ dữ liệu sản phẩm và lịch sử chat chính.

**Mốc tạm sau 0056: 185 bảng / 41 nhóm / 167 bảng FORCE RLS.** Số này sẽ thay đổi khi tiếp tục gộp các bảng P0.

| Nhu cầu | Tài liệu |
|---|---|
| Phạm vi, vai trò và luồng nghiệp vụ | [Business analysis P0](02_BUSINESS_ANALYSIS_IMPLEMENTATION.md) |
| Bảng, ràng buộc và quy tắc tinh gọn | [Database specification P0](01_DATABASE_ERD_IMPLEMENTATION_COMPLETE.md) |
| Nhiệm vụ và liên kết của từng bảng | [TABLE_CATALOG](physical/TABLE_CATALOG.md) |
| Mọi cột, PK/FK, CHECK và index | [Physical catalog](physical/README.md) |
| ERD theo module | [PROJECT_RELATIONSHIPS](physical/PROJECT_RELATIONSHIPS.md) |
| Đối chiếu tiến độ và kiểm chứng | [P0 tracker](P0_REDESIGN_TRACKER.md) |
| Migration và điều kiện tích hợp | [Migration runbook](MIGRATION_RUNBOOK.md) |
| Hiểu meta | [Drizzle README](../../server/drizzle/README.md) |

Physical catalog sinh từ Drizzle và `server/scripts/table-purposes.json` bằng `bun run --cwd server db:erd`. Bốn file `docx/01–04` đã bị loại vì hai đặc tả P0 ở trên thay thế chúng. Lịch sử migration/snapshot đã có được giữ nguyên.
