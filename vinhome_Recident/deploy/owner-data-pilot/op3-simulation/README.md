# OP3: bộ mô phỏng đầy đủ quan hệ nghiệp vụ

Người dùng chọn bổ sung OP3 và kiểm tra ca OP1. Bộ này là **mô phỏng để test**, không phải hồ sơ cư trú, nhân sự hoặc chính sách được operator xác nhận.

Tái sử dụng [template đã loại credential của OP2](../op2-simulation/template.json), không sao chép password/hash/token hoặc tạo thêm admin. API builder giữ tương thích với OP2:

```python
bundle, credentials = build(template, existing_admin_id, site_code="ocean-park-3")
```

Lưu bundle và credential vào file riêng ignored; không in password hoặc tạo lại credential khi retry. Profile `op3-simulation-v1`, operator `SIM-OP3-OPERATOR`, email đuôi `@op3-sandbox.test`. ID/điện thoại mô phỏng dùng namespace/dải riêng, không đụng OP2.

| Nhóm | Số lượng mới |
|---|---:|
| Khu / tòa / căn / cư dân | 1 / 3 / 6 / 6 |
| Staff / chuyên môn / ca | 24 / 48 quan hệ / 336 |
| Dịch vụ / coverage / SLA | 10 / 8 / 15 |
| SOP / chunk | 20 / 20 |
| Xe / thẻ / khách / chứng từ công nợ | 6 / 12 / 6 / 12 |
| Tiện ích / booking | 2 / 6 |
| Hồ sơ cải tạo / yêu cầu dịch vụ | 6 / 6 |

Ba nhóm ca `c1/c2/c3` tương ứng 07:00–15:00, 15:00–23:00, 23:00–07:00 Asia/Saigon, mỗi ca hai kỹ thuật, hai an ninh, hai vệ sinh và hai hỗ trợ. Lịch 14 ngày phục vụ nghiệm thu; không thay ca nhân sự thật.

Mọi phí/VAT/giờ/bảo hành/SLA giữ nhãn mô phỏng. Tài liệu `unverified=true`, owner record `operational_verified=false`. Không sinh ticket, workflow, payment, grant, queue, session hoặc cấu hình bridge. Template OP3 không tự mở thêm tool MCP.

Nạp qua entry point hiện có để không phá script OP2:

```powershell
python -m vinhomes_api.synthetic_op2 <op3.bundle.secret.json> --allow-runtime-simulation
```

Cần `DATABASE_URL` owner trong env riêng; database phải nằm trong allowlist và có marker `vinhomes-synthetic-sandbox-v1`. Backup, thử database clone, kiểm tra đăng nhập/scope/retrieval, sau đó mới nạp runtime. Nạp lại cùng bundle không đổi tài khoản hoặc sinh bản ghi trùng. Builder/importer từ chối site ngoài OP2/OP3 hoặc row có site khác với bundle.

Chỉ mục tri thức dùng heading/nội dung và dạng bỏ dấu, giữ provenance tham khảo. Không gọi Agent/model/embedding để nghiệm thu bộ dữ liệu.
