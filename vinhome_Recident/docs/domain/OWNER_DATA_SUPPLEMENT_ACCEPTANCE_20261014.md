# Bổ sung dữ liệu OP1/2/3 — kết quả 14/10/2026

## Dữ liệu đã bổ sung

Đã nghiên cứu và nạp **80 bản ghi tham khảo có nguồn** vào kho tri thức của Domain trên VPS `103.238.235.156`. Danh mục có khóa riêng theo site, URL cấp từng mục, ngày đối chiếu và ngày xuất bản khi nguồn ghi rõ. Đây là danh mục **một phần**, không phải hồ sơ địa chính hoặc danh mục vận hành đầy đủ.

| Khu | Phân khu công khai | Mã tòa công khai | Tiện ích/địa điểm dịch vụ |
|---|---:|---:|---:|
| Ocean Park 1 | 9 | 30 | 8 |
| Ocean Park 2 | 8 | 0 | 7 |
| Ocean Park 3 | 8 | 0 | 10 |
| Tổng | 25 | 30 | 25 |

Nguồn và dữ kiện: [nghiên cứu từng mục](RESEARCH_OWNER_DATA_CATALOG_20261014.md), [JSON catalog](../../deploy/reference-data/owner-public-catalog-20261014.json). Nguồn chính gồm [Vinhomes Ocean Park 1](https://oceanpark.vinhomes.vn/gioi-thieu-diem-nhan/), [danh sách phân khu OP2](https://market.vinhomes.vn/phan-khu/cha-la-vinhomes-ocean-park-2), [Ocean Park 3](https://oceanpark3.vinhomes.vn/brochure/). Một số thông tin tòa xuất bản năm 2021/2024; ngày đối chiếu 2026 không biến chúng thành hồ sơ vận hành hiện hành.

**80 dòng được nạp thành tài liệu tham khảo, không ghi vào bảng zones/buildings/units hoặc coverage.** Không tạo mã căn/lô từ số tầng, không tự nhận đơn vị quản lý từ tên chủ đầu tư. `official_code` chỉ có khi nguồn ghi mã tòa; `record_code` là khóa tài liệu nội bộ. Các trường đơn vị vận hành, phí, giờ, quyền sử dụng, bảo hành, đặt/hủy chưa xác nhận giữ trống/pending. Toàn bộ mới có `unverified=true`, không có tài liệu catalog mới được nâng thành approved.

## Bốn nhóm dữ liệu được yêu cầu

| Nhóm | Đã làm | Chưa thể điền thật |
|---|---|---|
| Địa bàn | Catalog tên phân khu và một số mã tòa để đối soát, có nguồn theo site | Danh sách đầy đủ căn/lô, mã master, địa chỉ hiện hành, pháp nhân/đội vận hành và phạm vi bàn giao |
| Cư dân | Mẫu site/căn/tài khoản/quan hệ/hiệu lực/hồ sơ xác minh, kiểm tra liên kết và định danh nhất quán | Không có danh sách người được phép nhập; chưa tạo cư trú verified hoặc tài khoản |
| Nhân sự | Mẫu chuyên môn/phạm vi/capacity/dự phòng/ca, kiểm tra route và ca chồng | Chưa có roster, ca hoặc hồ sơ nhân sự từ đơn vị vận hành |
| Dịch vụ | 25 địa điểm/tiện ích tham khảo, mẫu catalog vận hành có điều kiện/phí/VAT/giờ/bảo hành/đặt/hủy | Chưa có biểu phí, giờ, đầu mối hoặc quy định hiện hành được xác nhận |

[Bộ mẫu bàn giao](../../deploy/owner-data-templates/README.md) gồm 9 CSV chỉ có header và manifest còn trống; không có demo. Công cụ `deploy/validate-owner-data.py` chỉ kiểm tra offline, không ghi DB. Mẫu trống bị từ chối. `valid=true` không chứng minh tính xác thực của người duyệt; chủ dữ liệu phải đối chiếu hồ sơ. Importer legacy không dùng cho gói nhiều site này; bước import/publish vận hành sẽ triển khai khi nhận cấu trúc và dữ liệu thật đã xác nhận.

## Kiểm thử và triển khai

- **16 kiểm thử offline đạt:** 3 site trùng mã cục bộ, liên kết phạm vi, cư trú hết hạn, nhân viên dự phòng, ca chồng, email/ID không nhất quán, biểu phí, tài liệu reference không được nâng approved, catalog đủ nguồn/khóa/UTF-8.
- **14 kiểm thử PostgreSQL đạt:** bộ knowledge và production readiness trong DB dùng một lần, bao gồm hai site cùng mã phân khu/tòa; không sửa DB production bằng fixture.
- **VPS:** import `documents=80 chunks=80 embedded=0 skipped=0 changed=160`. API + scheduler + platform-sync dùng image mới `owner-catalog-20261014-745e6f6c2a70`; resident/staff/Reception giữ nguyên image.
- API image ID: `sha256:04a739a4ed02da2501d29ec4072796f61ac4f104f970c44cf0bdd0ebd6572ca9`.
- Runtime `knowledge.py` khớp SHA-256 source local: `bdb08c70f465bb5853b70a361cc1a398b30c01885ece3829ded8fa30dad15ad0`.
- Tra cứu read-only theo OP1 `S1.01`, OP2 `Chà Là`, OP3 `Tropical Lagoon`: có nguồn đúng site, 0 kết quả chéo site. Thiếu site: 0 kết quả. Không gọi Agent hoặc embeddings.
- HTTPS `/`, `/login`, `/operations/`: HTTP 200; đăng nhập admin thành công, chỉ có admin. Platform vẫn tắt, MCP giữ 7 tool, không thêm quyền đọc toàn bộ cư dân/roster.
- Ruff đạt trên công cụ/mẫu kiểm thử mới. Có một cảnh báo deprecation từ FastAPI/Starlette test client, không phải lỗi kiểm thử.

Trạng thái sau nạp: **250 tài liệu / 734 đoạn**, 3 site; users=1 admin, units=0, staff=0, residencies=0, tickets=0, work_orders=0, zones=0, buildings=0. Dữ liệu công khai giúp tra cứu/đối soát, không mở luồng vận hành thật khi chưa có master/people/route được cấp.

## Sao lưu và bằng chứng

Database đang hoạt động giữ nguyên `vinhomes_clean_20261014_a08369c0`. Đã sao lưu chính DB này trước import, cùng env/Compose/image IDs; không dump nhầm DB cũ `vinhomes`.

Release: `/opt/vinhomes/releases/owner-catalog-20261014-745e6f6c2a70/`. Backup `backup/database.dump` 6.132.587 byte, SHA-256 `3e49bc8d260edf471f4e28d3ebc570d68e0520d8109e2129ed86e6ecfe4dfe6f`; kiểm tra header PGDMP và `pg_restore --list`, chưa thực hiện full restore. Pack SHA-256 `21787925e766fb8ffcdf48d3482a537229cbb017224b1ebf9972459e086a2789`.

Bằng chứng riêng ngoài Git: `E:\Vinhomes-Deploy\owner-catalog-20261014\runtime-acceptance.json`, manifest và log triển khai; trên VPS có `acceptance.json`, log import/build và backup riêng. Không đưa env/password/token vào commit.
