# 6 hạng mục PM yêu cầu (14/10): hiện trạng và kế hoạch

14/10/2026 · `develop2@619f1932` · Người đọc: PM

Mọi điểm "hiện trạng" đã kiểm trong code, không dựa vào báo cáo cũ.

## Tóm tắt

| # | Yêu cầu | Hiện trạng | Việc cần làm |
|---|---|---|---|
| 1 | Phiếu từ domain → leader lập nhóm, mời agent, trao đổi, tổng hợp; tool giao việc cho staff domain và cập nhật tiến độ cho cả nhóm | Lập phòng, mời agent, chờ báo cáo, tổng hợp: **có** (PR #83, kiểm offline đạt). Giao việc cho staff: **có** (`vh_work_order_dispatch` của Vinhome). Tiến độ staff: **chỉ leader biết**, không vào Shared Context của phòng. Model thật chưa lần nào chọn lập phòng | Đưa sự kiện tiến độ vào Shared Context của phòng; kiểm lại với model thật |
| 2 | Context, memory, Shared Context, chi phí, chống bịa, tự cập nhật kiến thức | Phiếu console: đủ (xem `DOI_CHIEU_4_VAN_DE_2026-10-14.md`). Phiếu đối tác: chống bịa mạnh (bộ kiểm câu, nhãn E), nhưng **không ghi token** vào sổ workflow và agent đối tác **tắt bộ nhớ, tự cải tiến** | Ghi token phiếu đối tác; bật bộ nhớ có nguồn cho agent đối tác; tab Hoạt động |
| 3 | Builder xem cả kho kiến thức, skill; tự chọn một agent hay một nhóm | Builder chỉ thấy **tool MCP**. Tham số kho kiến thức có trong code nhưng không được truyền. Spec không có skill. Mỗi lần mô tả chỉ tạo **một** agent | Truyền kho kiến thức và skill vào Builder; thêm skill vào spec; Builder đề xuất một agent hoặc một nhóm |
| 4 | Gỡ agent; mô tả → agent hoàn chỉnh → eval | **Không có nút gỡ agent.** Mô tả → bản nháp có 3–5 kịch bản; phải tự bấm chạy kiểm thử | Gỡ agent (có chặn khi đang dùng); "Tạo và kiểm thử" một bước |
| 5 | MinIO, ảnh cho agent | MinIO chỉ dùng cho tài liệu kho kiến thức. API tải ảnh của đối tác (`/partner/assets`) chỉ có ở chế độ cũ, **chế độ unified không có**; ảnh đính kèm trong tin bị bỏ qua | Gắn API tải ảnh vào unified, lưu MinIO, đưa ảnh vào lượt của leader (model đọc ảnh); Vinhome gửi ảnh của cư dân |
| 6 | Vai trò và đăng ký | Một vai trò `AREA_MANAGER`; ai cũng tự đăng ký được; không có admin | Theo quyết định PM, xem dưới |

## Quyết định của PM cho hạng mục 6

- Ba vai trò: `PLATFORM_ADMIN` (một người, quản lý cả platform), `DOMAIN_ADMIN` (quản lý một domain tích hợp), BQL (`AREA_MANAGER`).
- Một domain có nhiều khu; **mỗi khu đúng một tài khoản BQL**, làm được mọi việc của khu. Các BQL ngang quyền nhau.
- Đăng ký BQL chọn domain và khu, chờ duyệt.

## Kế hoạch

| Thứ tự | Việc | Xong khi |
|---|---|---|
| 1 | Gỡ agent; "Tạo và kiểm thử" | Gỡ được agent không dùng; agent đang làm leader/thành viên tuyến đối tác bị chặn với lý do rõ. Mô tả → bản nháp → kiểm thử chạy ngay |
| 2 | Builder: kho kiến thức, skill, một agent hay một nhóm | Builder gắn đúng kho kiến thức/skill có liên quan; mô tả cần nhiều vai thì tạo một nhóm agent có phân vai |
| 3 | Tiến độ staff vào Shared Context của phòng | Thành viên trong phòng đọc được trạng thái việc mới nhất |
| 4 | Token phiếu đối tác; bộ nhớ agent đối tác | Sổ workflow có token; agent đối tác ghi nhớ có nguồn |
| 5 | Ảnh: API tải lên + MinIO + model đọc ảnh | Đối tác tải ảnh, leader mô tả được ảnh |
| 6 | Vai trò, duyệt đăng ký, một BQL mỗi khu | Đăng ký mới chờ duyệt; admin duyệt trên màn hình; khu đã có BQL thì từ chối đăng ký thứ hai |

Mỗi bước có test tự động; bước nào dùng model thật thì PM chạy.

## Kết quả (nhánh `feat/wf-studio-roles`)

| # | Đã làm | Kiểm chứng | Còn lại |
|---|---|---|---|
| 1 | Sự kiện tiến độ staff (có chữ ký) ghi vào Shared Context của phòng, thành viên đọc được | Test tích hợp; offline E2E phòng xử lý đạt | Model thật chưa chọn lập phòng ở 2 phiếu thử; chờ PM quyết cách thúc (model mạnh / luật bắt buộc) |
| 2 | Token phiếu đối tác vào sổ workflow (leader + thành viên); agent đối tác bật bộ nhớ có nguồn; phiếu có phòng học khi leader mời xác nhận | Test tích hợp | Phiếu không có phòng chưa có nguồn học; tab Hoạt động chưa làm |
| 3 | Builder thấy kho kiến thức và thư viện skill, chỉ gắn id có thật; spec có `skills` (cài khi phát hành); "Mô tả bằng lời" lập kế hoạch một agent hay một nhóm 2–5 | Test API Studio | Chất lượng với model thật do PM kiểm |
| 4 | Nút "Gỡ agent" (chặn khi tuyến đối tác dùng); mỗi agent tạo từ mô tả có ≥ 3 kịch bản, tuỳ chọn chạy kiểm thử ngay | Test API Studio; ảnh UI | — |
| 5 | API tải ảnh của đối tác trong unified (MinIO); ảnh của người dùng vào lượt của leader (≤ 4 ảnh, ≤ 5 MB) | Test tích hợp | Vinhome chưa gửi ảnh qua API này; `S3_PUBLIC_ENDPOINT` phải là địa chỉ đối tác tới được |
| 6 | Ba vai trò; đăng ký BQL chờ duyệt, mỗi khu một BQL; trang Quản trị; CLI tạo quản trị platform | Test vai trò trên DB đã migrate; ảnh UI | Tài khoản cũ cùng khu được giữ và gắn cờ trên trang Quản trị |
