# Tài liệu AI Workforce / Vinhomes — bắt đầu ở đây

Không cần đọc hết folder. Chọn tài liệu theo việc cần làm; các báo cáo có ngày là snapshot, không phải trạng thái cập nhật tự động.

## Đọc trước

1. **Hiểu hệ thống và các team nối với nhau:** [Luồng tổng thể](teams/chien/SYSTEM_FLOW_AND_MAINTENANCE_2026-10-04/README.md).
2. **Biết dự án làm tới đâu:** [Báo cáo repo ngày 04/10](teams/chien/REPO_RESEARCH_2026-10-04/README.md).
3. **Biết việc cần nối tiếp:** [Checklist tích hợp](teams/chien/SYSTEM_FLOW_AND_MAINTENANCE_2026-10-04/INTEGRATION_CHECKLIST.md).

## Tra cứu theo nhu cầu

| Cần tìm | Đọc |
|---|---|
| Thành viên, team, milestone | [Tiến độ theo kế hoạch](teams/chien/REPO_RESEARCH_2026-10-04/TEAM_PLAN_PROGRESS.md) |
| Nhánh Git / PR | [Danh sách nhánh](teams/chien/REPO_RESEARCH_2026-10-04/BRANCHES.md) |
| Database và ERD thực tế | [Database map](teams/chien/DATABASE_MAP_2026-10-04/README.md) — 193 bảng ở snapshot local |
| RAG, scope, embeddings và tri thức học được | [RAG map](teams/chien/RAG_DATABASE_MAP_2026-10-04/README.md) |
| Chạy với đăng nhập thật | [Hướng dẫn chạy](teams/chien/CHAY_DANG_NHAP_THAT.md) |
| Quyền theo vai trò | [Ma trận RBAC](teams/chien/RBAC_MATRIX_2026-10-03.md) |
| API đang triển khai | [Backend V3](../services/vinhomes-api/README.md); khi backend chạy, xem `/docs` và `/openapi.json` |
| Contract HTTP của 14 tool kỹ thuật | [Technical API](teams/quang/TECHNICAL_API.md) |
| Yêu cầu nghiệp vụ gốc đã gộp | [Yêu cầu Vinhomes](VINHOMES_BUSINESS_REQUIREMENTS.md) — yêu cầu sản phẩm, không phải tiến độ |
| Hợp đồng Reception ↔ Supervisor | [Schema dùng chung](SCHEMA_RECEPTION_SUPERVISOR_V1.md) — file giữ tên V1 nhưng có nội dung V2 |
| Backlog toàn dự án | [Kế hoạch các team](KE_HOACH_HOAN_THIEN_5_TEAM.md) |

## Khi làm phần việc của một team

- Hoàng: [Phân công](teams/hoang/PHAN_CONG_3_THANH_VIEN.md); graph baseline gộp ở [PD_ALL_VERIFICATION](teams/hoang/handoffs/phan-dung/PD_ALL_VERIFICATION.md), còn [PH16](teams/hoang/handoffs/phan-hoang/PH16.md) là handoff tích hợp đang cần xử lý.
- Đông: [Phân công Coordination](teams/dong/PHAN_CONG_NOI_BO_COORDINATION.md) và [README runtime](../agent-coordination/README.md).
- Quang: [Nghiệp vụ](teams/quang/general.md), [catalog tool](teams/quang/tools.md), [bàn giao bộ 14 tool](teams/quang/handoffs/Q02-merge-dev-teamquang.md).
- Chiến: xem checklist tích hợp phía trên. [Kế hoạch 03/10](teams/chien/TIEN_DO_VA_KE_HOACH_2026-10-03.md) còn tiêu chí/backlog, nhưng phần trạng thái cũ không thay báo cáo 04/10.

Các `requests/` và `handoffs/` còn lại là contract/ghi chú cho người triển khai, không phải thứ tự đọc chung. Một proposal hoặc nhãn DONE local không chứng minh production đã nghiệm thu.

## Tài liệu nền OpenBot

Chỉ đọc khi làm nền platform: [architecture](architecture.md), [configuration](configuration.md), [development](development.md), [coworkers](coworkers.md), [routines](routines.md), [deployment](deployment.md), [Kubernetes](../charts/openbot/README.md), [releasing](releasing.md), [Windows signing](windows-signing.md).

Plugins: [Composio](plugins/composio.md), [Google Drive](plugins/google-drive.md), [Notion](plugins/notion.md). Desktop: [OAuth](../desktop/PROVIDER_OAUTH.md), [telemetry](../desktop/TELEMETRY.md).

Đợt dọn ngày 04/10 bỏ các kế hoạch/báo cáo cũ đã có bản thay thế và gộp handoff PD01–PD08. Lịch sử tracked vẫn tra được trong Git; bản sao trước dọn ở `.codex-artifacts/docs-cleanup-20261004/backup.zip` ngoài cây tài liệu.

Thư mục `my-docs` đã được bỏ: giữ yêu cầu nghiệp vụ và Technical API ở các đường dẫn trên, gộp hướng dẫn demo vào Backend V3. Bản sao đầy đủ 14 file trước dọn ở `.codex-artifacts/my-docs-cleanup-20261004/backup.zip`.
