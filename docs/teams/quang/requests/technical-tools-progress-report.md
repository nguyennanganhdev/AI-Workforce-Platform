# Báo cáo tiến độ 7 technical tools đầu

**Ngày:** 30/09/2026  
**Phạm vi:** 7 tool đầu trong `docs/teams/quang/tools.md` (mục 3.1–3.6 và 4.1).  
**Trạng thái chung:** Đã có contract, handler và adapter để chạy kiểm thử module/POC. Chưa tích hợp end-to-end qua gateway hoặc xác nhận production.

## Công việc đã làm

| Tool | Trạng thái hiện tại |
| --- | --- |
| `sop_kb.retrieve` | Handler và mock POC; lọc tenant/building, issue code, ngôn ngữ, trạng thái published, active version, review/ingest, thời hạn và ACL fixture trước khi xếp hạng. Chưa nối retrieval/ACL từ DB thật. |
| `asset.read` | Handler và mock POC; tìm theo ID hoặc vị trí, lọc tenant/building; nhiều kết quả trả `NEEDS_INPUT`, không tự chọn asset. |
| `sensor.read` | Handler và mock POC; lọc sensor/asset, metric, khoảng thời gian; giữ timestamp/unit/quality và trả `STALE_DATA` kèm readings khi quá ngưỡng. |
| `maintenance_history.read` | Handler và mock POC; kiểm tra asset, lọc/sắp xếp sự kiện; asset có lịch sử rỗng trả `OK` với `events: []`. |
| `technical.get_active_outage` | Handler và adapter Drizzle đọc `service_interruptions` + `interruption_scopes`; lọc tenant, scope bao phủ building, utility, trạng thái và thời điểm thực tế. Chờ backend cấp tenant-scoped DB session và scope resolver. |
| `utility_schedule.read` | Dùng cùng adapter DB; lọc lịch giao với time range, bỏ `proposed`/`cancelled`. Chờ cùng hai port backend như trên. |
| `maintenance_history.append` | Handler và mock POC dạng append-only; kiểm tra fixture result `VERIFIED`, asset/work order/actor; retry cùng key và payload trả cùng ID, payload khác trả `CONFLICT`; hỗ trợ superseding revision. Chưa có persistence, audit/outbox và idempotency transaction production. |

Phần dùng chung trong `server/src/technical-tools/` gồm Zod input/output schema cho 7 tool, catalog tên/version/capability/effect/timeout/idempotency, execution context, building access port, response envelope, lỗi chuẩn và runner validate → authorize → invoke → validate output. `createSevenTechnicalTools` xuất đủ bảy handler để backend đăng ký.

## Kiểm thử đã chạy

- `bun run --cwd server typecheck` — đạt.
- `bunx biome check server/src/technical-tools server/tests/technical-tools` — đạt.
- `bun test server/tests/technical-tools` — **15 test đạt, 0 thất bại**. Có test contract, quyền/scope, SOP POC, asset nhiều kết quả, sensor stale, maintenance append/idempotency và adapter outage/schedule trên DB PGlite tối giản.

Test PGlite kiểm tra logic query; chưa thay thế test tích hợp trên PostgreSQL/RLS và gateway thật. Không sửa schema/migration hoặc server entrypoint.

## Việc còn cần phối hợp

Chi tiết port và yêu cầu tích hợp đã ghi tại `docs/teams/quang/requests/technical-tools-backend-ports.md`. Ưu tiên: backend xác thực và đăng ký `/internal/tools/*`; cấp `BuildingAccessPort`, `TenantReadSessionPort`, `CoveringScopesPort`; thay mock SOP/asset/sensor/maintenance bằng nguồn thật; triển khai maintenance append bền vững với transaction, audit/outbox và idempotency. Sau đó chạy acceptance end-to-end theo tenant/building và các trường hợp vượt quyền, dữ liệu stale, SOP thu hồi, retry write.

**Kết luận:** Phần code module/POC của 7 tool đã có và test đạt. Chưa đánh dấu 7 tool là hoàn thành production cho đến khi các port backend, nguồn dữ liệu thật và kiểm thử end-to-end được nối và nghiệm thu.
