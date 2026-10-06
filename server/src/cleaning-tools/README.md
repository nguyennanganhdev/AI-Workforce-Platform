# Bộ tool cho agent vệ sinh

Module `server/src/cleaning-tools/` ngang hàng với `server/src/technical-tools/`. Nghiệp vụ giống bộ kỹ thuật, đổi đội phụ trách sang vệ sinh.

- Đủ 14 đối ứng dùng trực tiếp implementation/schema của kỹ thuật; mapping tại `tools/technical-counterparts.ts`.
- Năm tool bọc API V3 hiện có: tìm nhân viên vệ sinh, đọc/tạo việc, phân công và cập nhật trạng thái. Catalogue có 19 entry.
- Adapter scope chỉ đổi đối tượng work/assignment, SOP và specialty sang vệ sinh. Không tự thêm policy VERIFIED khi completed, result contract mới hoặc storage riêng.

`index.ts` xuất catalogue, host/caller, adapter và contracts. Context, grants, các port kỹ thuật và backend bridge do deployment cung cấp. Chưa mount vào groupchat, cấp grant hoặc phát hành agent. Không sửa module kỹ thuật, backend, UI/gateway, schema database hoặc file hiện hữu; không thêm migration/bảng.

Xem [TOOLS.md](../../../docs/teams/hoang/cleaning/TOOLS.md), [PLAN.md](../../../docs/teams/hoang/cleaning/PLAN.md), [IMPLEMENTATION.md](../../../docs/teams/hoang/cleaning/IMPLEMENTATION.md).
