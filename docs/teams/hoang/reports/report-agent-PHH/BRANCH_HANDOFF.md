# Bàn giao nhánh dev_TeamHoang-HuyHoang

Ngày 04/10/2026. Nhánh riêng được tạo theo yêu cầu trực tiếp của Hoàng.

- Base: `dev_TeamHoang` tại `975565a1f5a3ff6ee168a801a912edd44cd6f0a5`.
- Nguồn Report tools 2.0.0: `518178afd4be92effd564b0d5609714b4113313b`.
- Chỉ đưa sang tools/application/metrics, test tương ứng, README/dependencies và docs Report.
- Không đưa sang các thay đổi development khác hoặc lịch sử hai commit Report cũ. Nhánh mới có một commit Report trên base Hoàng.
- Không sửa Reception, backend, DB, template, schema, prompt, examples hoặc narrative/layout có sẵn.

## Dependency API

Base Hoàng chưa có `services/vinhomes-api`. Tool gọi API của backend deployment qua `base_url`.
Source API đã kiểm tra: `dev_TeamChien` tại `9ecd1437b8c9629f51e68886e6dc17bc3da7e77e`.
Nhánh này không chứa backend đó và chưa wiring AgentScope.

Để chạy đủ test, `REPORT_SOURCE_REPO` trỏ tới checkout backend tương ứng, chứa `services/vinhomes-api/src`.
173 test tool PASS trên code nhánh mới: 169 HTTP fake và 4 FastAPI router thật lấy từ checkout backend bên ngoài, SQL/auth fake.
34 narrative regression PASS trên source Hoàng. Ruff/check format PASS. Không PostgreSQL/SSO/RLS hoặc end-to-end thật.

## Phạm vi folder

Theo `docs/teams/hoang/PHAN_CONG_3_THANH_VIEN.md`, tools/application/metrics và test tương ứng thuộc Dương Dũng.
Lần này Hoàng trực tiếp yêu cầu viết Report tools và tạo nhánh riêng. Không sửa bảng phân công thành ownership mới cho cả dự án.
Các thành viên cần phối hợp owner trước khi nhập thay đổi hoặc nối runtime. Không tự đánh dấu DD14 hoặc PH15 hoàn tất.

Danh sách descriptor chỉ có `filter_report_scope`, `get_repair_bill_summary`, `get_ticket_frequency_summary`, `get_employee_star_summary`.
README nêu API, input/output, giới hạn; PROGRESS_REPORT và DOCX có review, fail và cách sửa.
