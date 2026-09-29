# Một nền OpenBot, một nguồn danh tính và transcript PostgreSQL

Status: accepted for database design and migration; application integration pending.

## Quyết định

Phát triển trực tiếp từ OpenBot. agents, channels, mcp_servers và skills là registry chuẩn. Bỏ platform_agent/platform_conversation/platform_mcp_server/platform_skill; version/governance liên kết tới ID text nền.

PostgreSQL giữ channel_messages. Intelligence là tích hợp có mapping/outbox, không là nguồn lịch sử thứ hai. AgentScope là execution framework sau RuntimeAdapter, không được sửa business tables.

platform_tool vẫn cần: một danh tính thao tác có provider MCP/DOMAIN/BUILTIN. mcp_tools là discovery cache; refresh không tác động lịch sử version. Nguồn đích có CHECK/unique và không được đổi sau khi tạo.

21 bảng nền được bổ sung tenant/FK/RLS. Global login không dùng cùng tenant policy; job infrastructure có quyền vận hành riêng. RLS tenant không thay quyền đọc cư dân/channel.

## Thay thế

Thay quyết định registry song song/adapter đồng bộ trong ADR 0011 và conversation parent độc lập trong ADR 0012. Giữ các invariant domain, version, coordination, QC và tiến độ còn phù hợp.

## Hệ quả

Người dùng xác nhận local không có dữ liệu cần giữ. Forward migration 0051/0052 chặn dữ liệu không rỗng; giữ lịch sử migration cũ. Writer/reader tenant, deployed-version loader, chat và Intelligence/AgentScope integration phải hoàn tất trước rollout. Không tuyên bố end-to-end chỉ từ DDL.

Xem [database design](../../erd/01_DATABASE_ERD_IMPLEMENTATION_COMPLETE.md), [đối chiếu](../../erd/P0_REDESIGN_TRACKER.md), [runbook](../../erd/MIGRATION_RUNBOOK.md).
