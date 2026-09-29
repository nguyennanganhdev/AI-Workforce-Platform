# Theo dõi triển khai lại P0

Nguồn chuẩn của đợt này:

- [Database specification](01_DATABASE_ERD_IMPLEMENTATION_COMPLETE.md)
- [Business analysis](02_BUSINESS_ANALYSIS_IMPLEMENTATION.md)

Hai file này thay thế phạm vi thiết kế 186 bảng trước đó. Các báo cáo kiểm chứng ngày 28/09/2026 chỉ chứng minh baseline cũ, không chứng minh P0 mới đã hoàn tất.

## Quyết định triển khai

1. Giữ OpenBot là nền mã nguồn của một sản phẩm. `platform_agent` trong đặc tả mới là hồ sơ quản trị/lifecycle mở rộng, có mapping duy nhất tới agent OpenBot khi sử dụng; không phải platform độc lập.
2. Giữ user local để ánh xạ SSO; không xây kho mật khẩu cư dân riêng. Bổ sung external identity, permission, role và assignment theo scope/thời hạn.
3. Gộp model/tool/skill/knowledge/policy version vào capability P0. AgentVersion giữ AgentSpec đã ghim. Không để hai catalog quản trị chạy song song.
4. Gộp evaluation suite/case/assertion/evidence vào EvalRun JSON; vẫn phải bảo vệ publish gate, approval và version bất biến.
5. Case giữ IssueCandidate JSON; Task giữ dependency JSON; ActionRequest giữ RuleDecision; WorkOrder giữ checklist snapshot. Loại bỏ bảng thay thế cùng FK/trigger và cập nhật test.
6. WorkflowSession giữ plan/context; AgentRun ghi execution. Chỉ giữ cấu trúc hỗ trợ retry/checkpoint/handoff có nhu cầu và giải thích rõ, không giữ RunStep chỉ vì schema cũ đã có.
7. Giữ đủ resident services theo nguồn mới: booking, finance, Smart City, community, discovery. Không cắt các nhóm này để giảm số bảng.
8. Transcript PostgreSQL vẫn là quyết định của người dùng: channels/channel_messages dùng chung; không tái tạo conversation registry.
9. Giữ idempotency/outbox và các ràng buộc tenant/payload/redo/QC. JSON thay bảng phải có kiểm tra hình dạng và invariant phù hợp.
10. Lịch sử migration đã commit giữ nguyên; thay đổi P0 phải có migration local-only có guard. Không áp dụng lên database ứng dụng trong tác vụ này.

## Các bước và bằng chứng hoàn tất

| Bước | Điều kiện hoàn tất | Trạng thái |
|---|---|---|
| Đối chiếu phạm vi | Mọi bảng hiện tại có quyết định giữ/gộp/bỏ và nguồn đích | Đang làm; các nhóm phải gộp tiếp nêu bên dưới |
| Auth | Schema, scope integrity, roles/permissions seed và kiểm thử | 0053 đã có 5 bảng, bỏ 2 bảng role cũ; 13 role / 32 permission; 4 test authorization đạt |
| Platform P0 | Catalog/spec/evaluation/runtime hợp nhất, loại bảng thừa | Chưa xong |
| Vinhomes P0 | Cột/JSON/quan hệ khớp nguồn mới; giữ đủ dịch vụ cư dân | 0054 gộp issue vào Case; 0055 hợp nhất loyalty; 0056 gộp dependency vào Task; còn Rule/Checklist và nhóm mở rộng |
| Migration | Database rỗng và nâng cấp local đều chạy được; không làm mất dữ liệu ngoài phạm vi | Chưa xong |
| ERD và catalog | Sinh từ schema mới, nhiệm vụ từng bảng, đối chiếu cũ/mới | Chưa xong |
| Kiểm chứng | Typecheck, drift, integrity, tenant isolation, publish, QC/redo, idempotency/outbox | Chưa xong |

Các mục `/me/context`, API authorization, AgentScope execution và UI trong tài liệu nguồn là yêu cầu tích hợp ứng dụng. Đợt database phải cung cấp persistence/contract hỗ trợ và ghi rõ trạng thái; không coi migration là đã triển khai các endpoint hay runtime này.

## Kiểm chứng bước authorization — 29/09/2026

- Đã chạy 0000–0053 trên PostgreSQL 16/pgvector test riêng; không dùng database ứng dụng.
- 25 tests / 5 file đạt, 5.713 assertions: authorization, schema/catalog, migration upgrade, chat/tenant và journal.
- Auth mapping unique issuer/subject; không cho đổi mapping sang user/tenant khác bằng UPDATE.
- Custom role không gán xuyên tenant/domain; assignment gắn thành viên tenant, có khoảng hiệu lực và scope bất biến.
- Role hệ thống và permission đọc được nhưng không sửa được bằng role database ứng dụng trong test RLS.
- BQL không tự có quyền publish agent; seed không tự gán quyền cho user.
- Scope PROJECT/TOWER/APARTMENT/RESOURCE là tham chiếu mềm: API/domain phải xác thực đối tượng tồn tại và người dùng được phép cấp quyền. RLS không tự thực hiện kiểm tra nghiệp vụ này.
- Schema sau 0056: 185 bảng / 41 nhóm / 167 FORCE RLS. Đây chưa phải số bảng cuối cùng của P0.

## Dọn tài liệu và bảng — 29/09/2026

- Đã xóa bốn file thiết kế cũ `docx/01–04_*.md` và sáu trang ERD mô tả baseline 0052 trùng/lỗi thời; chuyển liên kết về hai đặc tả P0 và tracker. Các trang ERD vật lý được sinh lại theo schema hiện tại.
- `0054`: xóa `vh_issue_candidate`, `vh_issue_relation`, `vh_resident_report.issue_candidate_id`; `vh_case.intake_state_json` lưu danh sách IssueCandidate với CHECK hình dạng cơ bản. Migration từ chối xóa nếu còn dữ liệu candidate cũ.
- `0055`: xóa `vh_loyalty_account`, `vh_loyalty_entry`; thêm `vh_loyalty_balance` theo P0. Migration từ chối khi còn dữ liệu loyalty cũ.
- `0056`: xóa `vh_task_dependency`; thêm `vh_task.depends_on_json`. Trigger kiểm tra UUID, cùng Incident, trùng lặp và chu trình kể cả khi cập nhật cạnh; migration từ chối dữ liệu dependency cũ chưa được map.
- Kiểm chứng hiện tại: 79 tests trên 10 file đạt, 0 lỗi, 5.780 assertions; typecheck server, ERD check, liên kết tài liệu và 88 sơ đồ Mermaid đạt. Drizzle không phát hiện schema drift sau 0056; migration đã chạy trên PostgreSQL test và đối chiếu bằng schema/migration integration. Đợt P0 đầy đủ chưa kiểm chứng hoàn tất.
- Bảng còn cần quyết định/gộp: `platform_agent_spec`, nhóm binding/capability version, eval suite/case/assertion/evidence, RunStep; `vh_rule_evaluation`, checklist/version và các bảng mở rộng chưa được P0 yêu cầu tách. Không xóa đơn lẻ nếu bảng khác còn FK/trigger đến chúng.
