# Physical database và identity dùng chung

Status: accepted for the database implementation.

Giữ `public.users.id` text làm identity chung; thêm tenant UUID và 127 bảng có prefix
`platform_` / `vh_` trong cùng public schema và migration ledger. Không tạo credential
store mới hoặc di chuyển bảng shell vì sẽ làm lệch auth/runner đang chạy. Ownership
vẫn chia module và kiểm tra import/FK; Vinhomes chỉ FK sang Shared Kernel.

TENANT_DOMAIN và DOMAIN_INSTALLATION được hợp nhất thành installation theo tenant/
package/environment. Catalog tài nguyên bắt buộc tenant để composite FK và RLS nhất
quán; global sharing cho capability/model/tool cần thiết kế grants riêng khi có nhu cầu.

RLS/FORCE RLS không thay authorization theo user/membership. API cần role không bypass
và transaction-local context đã xác thực. Trigger/exclusion quản lý bằng SQL migration
riêng vì snapshot Drizzle không biểu diễn đầy đủ. Resource shell và registry mới chưa
tự đồng bộ; adapter thuộc bước API, không được hiểu là đã hợp nhất chỉ vì cùng DB.
