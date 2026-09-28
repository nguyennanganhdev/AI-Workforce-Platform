# Drizzle metadata: cách đọc và review

`meta/` là thư mục metadata của migration, **không phải package nghiệp vụ, database riêng hoặc nơi lưu dữ liệu cư dân**.

| Thành phần | Nhiệm vụ | Người review cần kiểm tra |
|---|---|---|
| `_journal.json` | Danh sách migration theo thứ tự: `idx`, format `version`, timestamp `when`, tên file `tag`, `breakpoints` | Một entry cho mỗi SQL; thứ tự và timestamp tăng, không đặt thời gian tương lai |
| `0000_snapshot.json` … `0050_snapshot.json` | Toàn bộ cấu trúc mà Drizzle biết tại từng mốc; dùng để tính thay đổi khi generate migration tiếp | `id/prevId` nối đúng lịch sử; bảng/cột/khóa/index tương ứng schema và SQL |
| `README.md` | Hướng dẫn này | Không được runner thực thi |

Snapshot chứa `dialect`, phiên bản format, `id`, `prevId`, `tables`, enums và các metadata khác mà Drizzle hỗ trợ. Mỗi bảng có columns, indexes, foreign keys, composite primary keys, unique/check constraints, policies và cờ RLS. `version: "7"` là phiên bản **định dạng snapshot**, không phải PostgreSQL 7 hay version nghiệp vụ.

## Quan hệ giữa bốn nơi

```text
server/src/db/schema/**/*.ts    Mô hình được lập trình viên chỉnh sửa
            │ drizzle-kit generate: so với snapshot mới nhất
            ▼
server/drizzle/NNNN_name.sql    DDL được runner thực thi
server/drizzle/meta/            Journal + snapshot lịch sử
            │ bun server/scripts/migrate.ts
            ▼
PostgreSQL                     Cấu trúc và ràng buộc thực tế
drizzle.__drizzle_migrations    Ledger các migration đã áp dụng

schema + table-purposes.json ── db:erd ── docs/erd/physical/
```

Runner đọc journal và SQL; không chạy snapshot JSON vào database. Drizzle generator dùng snapshot để phát hiện thay đổi; việc snapshot không đổi không chứng minh migration SQL không có tác dụng.

## Các mốc của đợt ERD

| Mốc | Nội dung SQL | Tổng bảng sau mốc | Snapshot |
|---|---|---:|---|
| 0045 | Baseline OpenBot đang có | 38 | Giữ nguyên |
| 0046 | Shared Kernel, Platform, Vinhomes: 127 bảng | 165 | Thêm bảng/cột/FK/index/CHECK/policy |
| 0047 | Trigger, exclusion, FORCE RLS | 165 | Cấu trúc được Drizzle biểu diễn gần như 0046 |
| 0048 | 25 bảng conversation, coordination, field, progress, SLA | 190 | Thêm bảng/cột và quan hệ mới |
| 0049 | Integrity cho coordination/field và FORCE RLS mới | 190 | Cấu trúc được Drizzle biểu diễn gần như 0048 |
| 0050 | Tám index phục vụ retry, lease và SLA deadline | 190 | Bổ sung index |

**Phải đọc SQL 0047 và 0049.** Drizzle không snapshot trigger, exclusion constraint và FORCE RLS. Chỉ đọc JSON sẽ bỏ sót luật chống lịch trùng, lịch sử bất biến, kiểm tra checkpoint và provenance của tiến độ.

## Quy tắc làm việc chung

1. Chỉnh schema TypeScript đúng module; thêm file vào config/barrel/exporter nếu tạo module mới.
2. Cập nhật nhánh trước khi sinh migration. Dùng một ledger chung, không tự đặt số migration riêng cho Platform và Vinhomes.
3. Generate migration bằng script của server. Quy tắc Drizzle chưa biểu diễn được dùng custom SQL migration riêng; giữ snapshot/journal do công cụ tạo.
4. Review SQL và kiểm tra tương ứng snapshot. Không sửa migration đã áp dụng ở môi trường dùng chung; thay đổi bằng migration mới.
5. Nếu hai nhánh sinh cùng số migration, đồng bộ base và sinh lại migration chưa triển khai của nhánh mình; không tự sửa UUID/timestamp để che xung đột. Nếu đã áp dụng, cần forward migration thống nhất với nhóm vận hành.
6. Chạy schema/journal/integration tests và `db:erd:check`. Commit schema, SQL, snapshot, journal và catalog cùng một thay đổi logic.

GitHub được cấu hình thu gọn snapshot và catalog tự sinh bằng `.gitattributes`; vẫn có thể mở từng file để review. `_journal.json`, SQL, schema và tài liệu viết tay luôn là phần cần xem trực tiếp.

Xem [review guide](../../../docs/erd/REVIEW_GUIDE.md) cho thứ tự đọc và [runbook](../../../docs/erd/MIGRATION_RUNBOOK.md) cho lệnh migration/test.
