# Nạp dữ liệu vào domain Vinhomes

Dành cho người cung cấp dữ liệu của Vinhomes. Có hai việc khác nhau:

1. **Dữ liệu thật** của khu đô thị (tòa, căn, cư dân, nhân viên, thẻ, công nợ, tri thức): nạp bằng lệnh `import` từ tệp CSV hoặc JSON.
2. **Thế giới mẫu** để phát triển và thử platform: dựng bằng lệnh `mock`, không cần tệp.

Mọi lệnh chạy ở thư mục `services/vinhomes-api` với `DATABASE_URL` trỏ tới database bằng **vai trò chủ sở hữu** (không phải vai trò của API), sau khi đã `create`, `migrate` và `seed` (xem [deploy/README.md](../../deploy/README.md)). Kiểm chứng: `tests/test_import.py`.

## 1. Thế giới mẫu

```
python -m vinhomes_api.database mock --profile standard --seed 42
```

| | `test` | `standard` |
|---|---|---|
| Căn | 130 (2 tòa chung cư, một cụm villa) | 360 (5 tòa, villa, nhà phố) |
| Tài khoản người | 243 | 669 |
| Nhân viên có ca 60 ngày | 7 | 25 |
| Thông báo phí (3 hoặc 6 tháng) | 348 | 1.920 |
| Thẻ | 339 | 933 |
| Lượt đăng ký khách | 119 | 291 |
| Lượt đặt tiện ích | 219 | 219 |
| Đơn thi công, đơn lễ tân | 25, 20 | 25, 150 |
| Tài liệu tri thức | 56 | 70 |
| Yêu cầu trong lịch sử | 40 | 900 |

Mỗi yêu cầu lịch sử không bị hủy có một hồ sơ cư dân đi kèm (profile `standard`: 855 hồ sơ, trong đó 592 đã hoàn tất), để ứng dụng cư dân có lịch sử để hiện. Cùng `--seed` cho cùng nội dung. Chạy lại không thêm gì (đã đo: hai lần liên tiếp cùng số lượng, mỗi lần khoảng 15 giây). Đổi cấu hình (`test` rồi `standard`) trên cùng một database không được hỗ trợ: dùng `reset` rồi dựng lại. Nhân vật cố định `mock-an`, `mock-chau`, `mock-binh`, `mock-dung`, `mock-em`, `mock-hoa`, `mock-khoa`, `mock-giang`, `mock-minh` được mô tả ở [KICH_BAN_VANG.md §3](KICH_BAN_VANG.md). Mọi nội dung là **dữ liệu mẫu**, không phải quy định thật.

## 2. Dữ liệu thật

```
python -m vinhomes_api.database import --dir ./du-lieu --dry-run     # xem lỗi, không ghi gì
python -m vinhomes_api.database import --dir ./du-lieu               # ghi
```

- Mỗi loại một tệp: `buildings.csv`, `units.csv`, … (hoặc `.json`: danh sách các đối tượng cùng tên cột). UTF-8, dòng đầu là tên cột. Tệp nào không có thì bỏ qua.
- Các dòng tham chiếu nhau **bằng mã**, không bằng id. Thứ tự nạp cố định (bảng dưới từ trên xuống) nên mã nào được dùng phải có ở tệp trên hoặc đã có sẵn trong database.
- **Một giao dịch.** Dòng nào sai (mã không tồn tại, giá trị lạ, thiếu cột) được báo kèm tên tệp và số dòng; có lỗi thì **không ghi gì**. `--dry-run` luôn không ghi.
- **Chạy lại cùng tệp không thêm gì.** Lệnh chỉ thêm dòng mới; không sửa dòng đã có. Muốn sửa dữ liệu đã nạp, sửa qua ứng dụng quản trị hoặc `reset` rồi nạp lại.
- Trạng thái (thẻ, thông báo phí) được đưa tới giá trị bạn ghi bằng các bước hợp lệ của chính cơ sở dữ liệu, nên dữ liệu nạp vào tuân theo mọi quy tắc nghiệp vụ.
- Thời điểm có giờ phải kèm múi giờ, ví dụ `2026-10-10T08:00:00+07:00`.

| Tệp | Cột bắt buộc | Cột tùy chọn | Ghi chú |
|---|---|---|---|
| `buildings` | `code`, `name`, `zone_code` | | Phân khu (`zone_code`) phải có sẵn. Tạo luôn phạm vi truy cập và cho Ban quản lý phụ trách kỹ thuật và an ninh |
| `units` | `code`, `building_code`, `unit_kind` (`apartment`/`townhouse`/`villa`/`other`) | `floor` | |
| `residents` | `name`, `unit_code`, `relation` (`owner`/`tenant`/`household`) | `phone`, `email`, `user_id`, `status` (`verified` mặc định/`pending`), `valid_from` | Một người nhiều căn: nhiều dòng cùng `user_id` hoặc cùng số điện thoại |
| `staff` | `employee_code`, `name`, `role` (`staff`/`management`) | `phone`, `email`, `user_id`, `specialties` (`technical`, `security`, cách nhau `\|`), `availability` | Được quyền trên mọi tòa đã có |
| `shifts` | `employee_code`, `starts_at`, `ends_at` | | Người rảnh được tìm theo ca |
| `vehicles` | `unit_code`, `kind`, `plate_no`, `owner_name` | | `kind`: `car`, `electric_car`, `motorbike`, `electric_motorbike`, `bicycle` |
| `cards` | `card_no`, `kind`, `unit_code` | `plate_no` (xe đã nạp), `holder_name`, `status` (`active` mặc định, `pending_issue`, `lost`, `suspended`, `expired`, `revoked`), `valid_from`, `valid_to`, `monthly_fee` | |
| `debit_notes` | `doc_no`, `unit_code`, `issue_date`, `due_date` | `period_month`, `subtotal`, `vat_amount`, `status` (`issued` mặc định, `paid`, `partially_paid`, `overdue`, `cancelled`), `paid_amount` | Tổng các dòng phí phải bằng `subtotal` |
| `debit_note_lines` | `doc_no`, `line_no`, `fee_kind`, `description`, `amount` | `quantity`, `unit_price` | `fee_kind`: `management`, `parking`, `water`, `electricity`, `service`, `deposit`, `penalty`, `other` |
| `amenities` | `code`, `name`, `category_code`, `zone_code` | `areas` (cách nhau `\|`), `price`, `slot_minutes`, `open_time`, `close_time`, `max_advance_days`, `cancel_before_hours`, `weekly_quota`, `max_guests`, `rules_note` | |
| `handbook` | `title`, `body_md` | `audience` (`resident`, `staff`, `management`, cách nhau `\|`; mặc định `resident`), `zone_code`, `seq`, `language` | Cẩm nang cho cư dân hoặc quy trình nội bộ |
| `policies` | `code`, `title`, `kind`, `version`, `effective_from` | `body_md`, `audience`, `zone_code`, `unit_kind`, `language`, `effective_to` | `kind`: `terms_of_use`, `privacy_policy`, `building_rules`, `construction_rules`, `amenity_rules`, `fee_table`, `faq` |
| `announcements` | `code`, `kind`, `title`, `body_md` | `summary`, `status` (`draft`/`published`), `building_codes` (cách nhau `\|`), `published_at` | `published` chỉ ghi nội dung và thời điểm phát hành, không gửi thông báo cho ai; muốn báo cho cư dân thì phát hành bằng ứng dụng |

Tài liệu tri thức nạp ở `handbook`, `policies`, `announcements` chính là **gói tri thức** mà platform lấy qua `GET /integration/v1/knowledge/pack` ([HOP_DONG_TICH_HOP.md §7](HOP_DONG_TICH_HOP.md)). Tài liệu chỉ cho BQL chỉ được xếp vào gói của BQL.

## 3. Việc cần làm sau khi nạp

- **Đăng nhập.** Lệnh nạp tạo người và tư cách thành viên nhưng **chưa tạo mật khẩu**. Quản trị viên đặt mật khẩu qua `POST /auth/accounts/{user_id}/password`, hoặc để người đó tự đăng ký.
- **Tìm người rảnh** cần ca (`shifts`) và chuyên môn (`specialties`).
- **Hạn xử lý** (SLA) lấy từ bảng `sla_policies`; dữ liệu mẫu có sẵn chính sách cho Ban quản lý mẫu. Với Ban quản lý khác cần thêm chính sách.
- **Đăng ký platform** làm client: `python -m vinhomes_api.database client --id platform --kind platform --accepts-cases`; in bí mật một lần.
- **Tác vụ hạn** `python -m vinhomes_api.jobs sweep` cần chạy định kỳ (compose có sẵn dịch vụ `scheduler`).

## 4. Đặt lại

```
python -m vinhomes_api.database reset --confirm TEN_DATABASE
```

Xóa mọi thứ trong schema và dựng lại trống (migration chạy lại). Phải nhắc đúng tên database. Sau đó chạy lại `role` để cấp quyền cho vai trò của API, rồi `seed`.
