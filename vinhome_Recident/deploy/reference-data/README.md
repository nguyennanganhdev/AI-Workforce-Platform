# Catalog nguồn công khai cho Domain

Các file tại đây chỉ chứa tri thức tham khảo có nguồn, không chứa hồ sơ cư dân, nhân viên, căn hoặc ca tự sinh. Compiler `prepare-reference-pack.py` luôn tạo `unverified=true`, `operational_approval=pending`, không tạo owner approval, phí/giờ vận hành hoặc đơn vị quản lý.

| File | Số bản ghi nguồn | Mục đích |
|---|---:|---|
| `ocean-city-public-20261014.json` | 3 | Giới thiệu tiện ích theo OP1/2/3 |
| `owner-public-catalog-20261014.json` | 80 | Tên địa bàn/tiện ích: 25 phân khu, 30 tòa OP1, 25 tiện ích |
| `op1-technical-public-20261015.json` | 4 | Ba tiêu chuẩn bàn giao OP1 và kênh ứng dụng Vinhomes Resident |
| `resident-support-public-20261015.json` | 6 | Kênh liên hệ, phân loại chuyên môn và hoạt động; 2 bản ghi mỗi khu |

**93 bản ghi nguồn không phải tổng số tài liệu database**: database còn các bộ knowledge khác, tài liệu quarantined và travel mock. Có hai bản kênh liên hệ OP1/OP2 cùng dùng tổng đài thương hiệu; không phải hai tổng đài vận hành độc lập. Các mô tả tiện ích mới không tạo master trùng tên.

Mỗi bản mới phải có site, URL nguồn, ngày tra cứu, phạm vi/giới hạn trong nội dung và snapshot SHA-256. Không suy ngày hiệu lực từ thư mục URL, hạn tuyển dụng hoặc ngày cập nhật ứng dụng. Snapshot HTML/PDF lưu ngoài Git; hash chỉ chứng minh tính toàn vẹn, không chứng minh xác nhận vận hành.

Không nạp FAQ bị tắt/chưa xuất bản trong script nhúng dù search engine có lập chỉ mục; không suy đoán email bị che, số trực, giờ, giá, SLA, nhân sự hay quyền cư dân từ marketing. Mô tả CSKH tuyển dụng hết hạn chỉ giữ ở tài liệu nghiên cứu. Kết quả kiểm chứng nguồn nằm trong [nghiên cứu vòng 2](../../docs/domain/RESEARCH_DOMAIN_REFERENCE_EXPANSION_20261015.md).

Tạo gói offline từ gốc repo:

```powershell
python vinhome_Recident/deploy/prepare-reference-pack.py --input vinhome_Recident/deploy/reference-data/resident-support-public-20261015.json --output E:\Vinhomes-Deploy\reviewed-reference.jsonl.gz
```

Compile không ghi DB hoặc gọi model. Import cần backup, xác định đúng tenant/database/site đang chạy, kiểm tra ID không đè nội dung đã duyệt, nhập lặp không trùng và tìm kiếm bằng quyền runtime. Site chưa có được bỏ qua, không tự tạo. Tắt embedding trong tiến trình kiểm thử/import khi chưa có yêu cầu thử provider. Không chạy seed/bootstrap để bổ sung reference.

Nghiệm thu mới nhất: [báo cáo dữ liệu Domain](../../docs/domain/DOMAIN_DATA_COMPLETION_ACCEPTANCE_20261015.md). Dữ liệu owner còn thiếu nằm trong [bộ pilot OP1/Kỹ thuật](../owner-data-pilot/op1-technical/README.md); không dùng các catalog công khai này thay hồ sơ vận hành.
