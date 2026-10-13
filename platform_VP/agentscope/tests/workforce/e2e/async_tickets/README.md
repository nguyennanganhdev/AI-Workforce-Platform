# Async ticket E2E

Chủ sở hữu lane: **Phan Hoàng Dũng**.

Thư mục đã triển khai các lớp kiểm thử cho response-only, interactive,
external-tracking, provider recovery và hai ticket/hộp chat của cùng một khách
hàng chạy xen kẽ nhưng không lẫn workflow/group/context/SSE.

`test_full_platform.py` là gate D5 toàn lát cắt. Factory mặc định nằm tại
`tests/workforce/fixtures/release_candidate_factory.py`; CI Phase D bắt buộc
chạy file này và không chấp nhận skip.

Các test phải giữ đủ Scope `(tenant_id, domain_id, area_id,
manager_account_id)`, ticket binding bất biến và correlation theo đúng ticket.
Ghép sai tuple phải bị từ chối trước Leader/tool call.
