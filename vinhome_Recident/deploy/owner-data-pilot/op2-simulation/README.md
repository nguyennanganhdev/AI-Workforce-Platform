# OP2: bộ dữ liệu mô phỏng để test nghiệp vụ

Người dùng đã chọn mở rộng OP2 trước, dùng dữ liệu mô phỏng có nhãn. `template.json` được rút gọn từ bộ OP1 mô phỏng đã kiểm thử; loại tài khoản admin, password/hash/token, session, ticket, grant, queue và cấu hình tích hợp. Đây không phải master căn, cư trú, nhân sự hay chính sách được Vinhomes/đơn vị vận hành xác nhận.

`vinhomes_api.synthetic_op2.build(template, existing_admin_id)` tạo:

- Một khu `SIM-OP2-ZONE`, ba tòa `SIM-OP2-TOWER-1/2/3`, sáu căn và sáu cư dân.
- 24 staff: ba nhóm ca, mỗi ca hai kỹ thuật, hai an ninh, hai vệ sinh và hai hỗ trợ dịch vụ. Mỗi người tối đa một việc đồng thời, phạm vi chỉ khu OP2 mô phỏng.
- 336 ca tám giờ trong 14 ngày. Nhóm `c1`: 07:00–15:00, `c2`: 15:00–23:00, `c3`: 23:00–07:00 theo Asia/Saigon. Có hai người cùng chuyên môn mỗi ca để lựa chọn dự phòng; đây không phải sơ đồ trực chính thức.
- 10 dịch vụ, tám nhóm coverage, 15 chính sách SLA giả lập và 20 tài liệu SOP cư dân/staff. Phí, VAT, giờ, bảo hành, đặt/hủy giữ nhãn mô phỏng; `operational_verified=false` và tài liệu `unverified=true`.
- Sáu xe, 12 thẻ, sáu khách, 12 chứng từ công nợ, hai tiện ích/sáu booking, sáu hồ sơ cải tạo và sáu yêu cầu dịch vụ mẫu. Không tạo ticket/assignment/workflow, thanh toán hoặc lịch sử nghiệm thu giả.

Builder trả `(bundle, credentials)`. Lưu cả hai vào file riêng ngoài Git; không in credentials. Mật khẩu được sinh ngẫu nhiên và hash trước khi nhập database. Không chạy builder lại để thay credential của tài khoản đã nhập; giữ bundle/manifest đã phát hành khi retry.

## Nạp và kiểm tra

Module `synthetic_op2` chỉ nhận database release mô phỏng được cho phép hoặc database kiểm thử `op2_expansion_test_<uuid>`, có marker `vinhomes-synthetic-sandbox-v1`, cùng `--allow-runtime-simulation`. Không mở guard để dùng trên database vận hành thật.

1. Sao lưu và kiểm tra dump; thử trên database clone, áp quyền runtime hạn chế.
2. Sinh bundle riêng từ template. Kiểm tra natural key category được ánh xạ đúng ở đích.
3. Nạp bằng `DATABASE_URL` owner trong env riêng:

```powershell
python -m vinhomes_api.synthetic_op2 <private-bundle.json> --allow-runtime-simulation
```

4. Nạp lại cùng bundle phải không sinh bản ghi mới; không đổi password/admin/cấu hình bridge. FK/RLS/state transition được giữ nguyên.
5. Kiểm tra đăng nhập, scope, ca trực, service/knowledge và truy cập chéo căn. Dừng API/container kiểm tra sau nghiệm thu.

Importer cập nhật full-text index của đúng các chunk trong bundle nếu text hash khớp, dùng heading/body và dạng bỏ dấu của pipeline tri thức chính. Retry chỉ sửa index khi có khác biệt; không gọi provider embedding hoặc nâng `unverified` thành approved.

Không đặt flag tự seed bộ này khi khởi động Docker. Không bật bridge VPS bằng URL `localhost` hoặc alias chỉ tồn tại ở Docker local. Endpoint Platform, key và route của từng môi trường phải được cấu hình riêng.

Kết quả đợt nạp và tài khoản nhận OP2: [OP2_RUNTIME_DATA_ACCEPTANCE_20261015.md](../../../docs/domain/OP2_RUNTIME_DATA_ACCEPTANCE_20261015.md).
