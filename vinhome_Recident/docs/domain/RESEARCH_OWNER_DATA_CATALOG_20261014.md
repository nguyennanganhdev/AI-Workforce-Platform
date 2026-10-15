# Catalog dữ liệu công khai của chủ đầu tư và dữ liệu cần đơn vị vận hành cấp

Ngày nghiên cứu: **14/10/2026**. Phạm vi đã chốt: **Vinhomes Ocean Park 1, 2, 3**. Nguồn ưu tiên: website dự án thuộc Vinhomes và Vinhomes Market. Chỉ tạo file nghiên cứu này; không sửa source/template, không SSH, không nhập database, không gọi Agent/provider.

## 1. Kết quả có thể bàn giao ngay

Đã đối chiếu **80 bản ghi tham khảo công khai**: 25 tên phân khu, 30 mã tòa được nguồn ghi rõ, 25 tiện ích/địa điểm dịch vụ. Đây là catalog **một phần**, không phải xác nhận đủ toàn bộ địa bàn hoặc dữ liệu vận hành của ba đô thị.

| Phạm vi | Phân khu | Tòa công khai | Tiện ích/địa điểm dịch vụ |
|---|---:|---:|---:|
| Ocean Park 1 | 9 | 30 | 8 |
| Ocean Park 2 | 8 | 0 | 7 |
| Ocean Park 3 | 8 | 0 | 10 |

Danh sách thực thể và URL cấp từng bản ghi nằm trong JSON ở mục 4. `code=null` nghĩa là nguồn không cấp mã phân khu/tiện ích; nếu ứng dụng tạo slug thì phải ghi đó là mã nội bộ. Mã tòa như `S1.01`, `P1`, `R1.01`, `BE1` được lấy nguyên mã nguồn công khai; không tự sinh mã căn/phòng từ cấu trúc tòa.

**Không gắn `verified_resident`, tạo tài khoản nhân viên, ca trực, coverage hoặc cấp quyền booking từ các dòng này.** Tài liệu xác nhận tên thực thể trong giới thiệu công khai; không xác nhận cư dân đang sống ở đâu, nhân viên nào đang làm việc, lịch vận hành/giá hay quyền từng hộ hôm nay.

## 2. Catalog nguồn và ngày

Tất cả bản ghi đã đọc/đối chiếu vào **14/10/2026**. Ngày crawl không được dùng thay ngày xuất bản. `source_published_at=null` nghĩa là chưa xác định được ngày, không phải tài liệu có hiệu lực vô thời hạn.

| Mã nguồn trong nghiên cứu | Trang sở hữu nội dung | Ngày xuất bản xác định | Ngày đối chiếu |
|---|---|---|---|
| `s1` | [Nguồn trực tiếp](https://market.vinhomes.vn/blog/toa-nha-tai-phan-khu-sapphire-1-vinhomes-ocean-park-gia-lam-co-bao-nhieu-tang) | 05/07/2024 | 14/10/2026 |
| `s1zone` | [Nguồn trực tiếp](https://market.vinhomes.vn/phan-khu/the-sapphire-1-vinhomes-ocean-park) | Không xác định trên phần đã đọc | 14/10/2026 |
| `s2` | [Nguồn trực tiếp](https://market.vinhomes.vn/phan-khu/the-sapphire-2-vinhomes-ocean-park) | Không xác định trên phần đã đọc | 14/10/2026 |
| `pavilion` | [Nguồn trực tiếp](https://market.vinhomes.vn/en/blog/toa-nha-tai-phan-khu-the-pavilion-vinhomes-ocean-park-1-co-bao-nhieu-tang) | 18/07/2024 | 14/10/2026 |
| `zenpark` | [Nguồn trực tiếp](https://vinhomes.vn/vi/tong-quan-mat-bang-the-zenpark-vinhomes-ocean-park) | Không xác định trên phần đã đọc | 14/10/2026 |
| `beverly` | [Nguồn trực tiếp](https://market.vinhomes.vn/phan-khu/the-beverly-vinhomes-ocean-park) | Không xác định trên phần đã đọc | 14/10/2026 |
| `low1` | [Nguồn trực tiếp](https://market.vinhomes.vn/blog/ban-do-vinhomes-ocean-park) | Không xác định trên phần đã đọc | 14/10/2026 |
| `s203` | [Nguồn trực tiếp](https://market.vinhomes.vn/blog/toa-s203-vinhomes-ocean-park) | 26/12/2021 | 14/10/2026 |
| `s207` | [Nguồn trực tiếp](https://market.vinhomes.vn/blog/s207-vinhomes-ocean-park) | 26/12/2021 | 14/10/2026 |
| `s208` | [Nguồn trực tiếp](https://market.vinhomes.vn/thu-cap/2-pn-1-1-toilet-toa-s2-08-phan-khu-the-sapphire-2-vinhomes-ocean-park) | Không xác định trên phần đã đọc | 14/10/2026 |
| `op1amenities` | [Nguồn trực tiếp](https://oceanpark.vinhomes.vn/gioi-thieu-diem-nhan/) | Không xác định trên phần đã đọc | 14/10/2026 |
| `op2zones` | [Nguồn trực tiếp](https://market.vinhomes.vn/phan-khu/cha-la-vinhomes-ocean-park-2) | Không xác định trên phần đã đọc | 14/10/2026 |
| `op2amenities` | [Nguồn trực tiếp](https://theempire.vinhomes.vn/) | Không xác định trên phần đã đọc | 14/10/2026 |
| `wave` | [Nguồn trực tiếp](https://market.vinhomes.vn/phan-khu/san-ho-vinhomes-ocean-park-2) | Không xác định trên phần đã đọc | 14/10/2026 |
| `op3zones` | [Nguồn trực tiếp](https://oceanpark3.vinhomes.vn/) | Không xác định trên phần đã đọc | 14/10/2026 |
| `op3amenities` | [Nguồn trực tiếp](https://oceanpark3.vinhomes.vn/brochure/) | Không xác định trên phần đã đọc | 14/10/2026 |

Các trang Vinhomes Market nêu thông tin có thể được điều chỉnh và vận hành theo quy định BQL. Vì vậy catalog chỉ đặt `authority=reference`; không nhập thành biểu phí hay policy đã duyệt. [Ví dụ lưu ý của nguồn Vinhomes Market](https://market.vinhomes.vn/blog/toa-nha-tai-phan-khu-sapphire-1-vinhomes-ocean-park-gia-lam-co-bao-nhieu-tang).

## 3. Các điểm cần giữ nguyên sự không chắc chắn

- **Phân khu OP2:** trang Chà Là liệt kê tám phân khu cư trú; trang tổng dự án còn hiển thị các khu thương mại như The K-town/The Center Point. Không tự coi các nhãn thương mại đó là phân khu cư trú bổ sung cùng cấp. [Nguồn Chà Là](https://market.vinhomes.vn/phan-khu/cha-la-vinhomes-ocean-park-2), [tổng dự án OP2](https://market.vinhomes.vn/du-an/vinhomes-ocean-park-2).
- **Sapphire 2 OP1:** trang nguồn nói 16 tòa trong dải S2.01–S2.19 nhưng phần danh sách đọc được chỉ nêu một số mã. Nghiên cứu chỉ lấy mã được nêu rõ ở trang dự án/tòa/giao dịch liên quan; không sinh mọi số trong khoảng. [Nguồn phân khu](https://market.vinhomes.vn/phan-khu/the-sapphire-2-vinhomes-ocean-park).
- **Beverly:** tên/codes cũng tồn tại ở Grand Park. Catalog này chỉ lấy các trang có đường dẫn/nội dung **Ocean Park**. Tên phân khu hoặc mã tòa không phải khóa duy nhất toàn hệ thống. [Beverly tại Ocean Park](https://market.vinhomes.vn/phan-khu/the-beverly-vinhomes-ocean-park).
- **Royal Wave Park / VinWonders Wave Park:** các trang giới thiệu dùng tên khác nhau cho nhóm công viên sóng OP2. Mảng JSON chọn tên VinWonders Wave Park từ trang San Hô; giữ nguồn lịch sử Royal Wave Park để operator xác nhận alias, không tạo hai tài sản/booking độc lập chỉ bằng hai tên. [Trang San Hô](https://market.vinhomes.vn/phan-khu/san-ho-vinhomes-ocean-park-2), [trang The Empire](https://theempire.vinhomes.vn/).
- **Dịch vụ y tế/giáo dục:** Vinschool, Vin University, phòng khám Vinmec trong mảng là các địa điểm/dịch vụ được trang giới thiệu liệt kê. Không suy hoạt động y tế cụ thể, điều kiện tiếp nhận, tuyến công việc hay tích hợp chuyên môn từ tên này. [Nguồn liệt kê](https://market.vinhomes.vn/phan-khu/the-beverly-vinhomes-ocean-park).
- **Masteri Waterfront:** không tự thêm vào coverage Vinhomes. Tài liệu chủ đầu tư xác định nhà quản lý Masterise Property Management; cần operator/route riêng nếu dự án quyết định tích hợp. [Factsheet Masteri Waterfront, phiên bản tên file 26/10/2022](https://masterisehomes.com/masteri-waterfront/wp-content/uploads/2023/08/Masteri-Waterfront-Factsheet-VIE-26.10.2022-.pdf).
- **Địa chỉ:** không bổ sung tọa độ, địa chỉ căn hoặc đơn vị hành chính hiện hành chỉ từ marketing cũ. Đặc biệt tên phân khu Ngọc Trai/Hải Âu/San Hô/Sao Biển lặp giữa OP1 và OP2; bắt buộc dùng site scope.

## 4. Mảng máy đọc được

Quy tắc: mọi dòng là **public reference**; ngày đọc ở `retrieved_at`; ngày nguồn xác định ở `source_published_at`. `parent_name` chỉ xuất hiện khi trang nguồn nêu tòa/tiện ích thuộc phân khu tương ứng; không chứa ID database, mapping đơn vị vận hành, cư dân, nhân viên, phí, giờ hoặc trạng thái active. Không tự chuyển `reference` thành `approved` sau khi import.

```json
[
  {
    "site_code": "ocean-park-1",
    "kind": "subdivision",
    "code": null,
    "name": "The Sapphire 1",
    "sources": [
      "https://market.vinhomes.vn/phan-khu/the-sapphire-1-vinhomes-ocean-park"
    ],
    "body": "Phân khu công khai thuộc OP1.",
    "source_published_at": null,
    "retrieved_at": "2026-10-14",
    "authority": "reference"
  },
  {
    "site_code": "ocean-park-1",
    "kind": "subdivision",
    "code": null,
    "name": "The Sapphire 2",
    "sources": [
      "https://market.vinhomes.vn/phan-khu/the-sapphire-2-vinhomes-ocean-park"
    ],
    "body": "Phân khu công khai thuộc OP1.",
    "source_published_at": null,
    "retrieved_at": "2026-10-14",
    "authority": "reference"
  },
  {
    "site_code": "ocean-park-1",
    "kind": "subdivision",
    "code": null,
    "name": "The Pavilion",
    "sources": [
      "https://market.vinhomes.vn/en/blog/toa-nha-tai-phan-khu-the-pavilion-vinhomes-ocean-park-1-co-bao-nhieu-tang"
    ],
    "body": "Phân khu công khai thuộc OP1.",
    "source_published_at": "2024-07-18",
    "retrieved_at": "2026-10-14",
    "authority": "reference"
  },
  {
    "site_code": "ocean-park-1",
    "kind": "subdivision",
    "code": null,
    "name": "The Zenpark",
    "sources": [
      "https://vinhomes.vn/vi/tong-quan-mat-bang-the-zenpark-vinhomes-ocean-park"
    ],
    "body": "Phân khu công khai thuộc OP1.",
    "source_published_at": null,
    "retrieved_at": "2026-10-14",
    "authority": "reference"
  },
  {
    "site_code": "ocean-park-1",
    "kind": "subdivision",
    "code": null,
    "name": "The Beverly",
    "sources": [
      "https://market.vinhomes.vn/phan-khu/the-beverly-vinhomes-ocean-park"
    ],
    "body": "Phân khu công khai thuộc OP1.",
    "source_published_at": null,
    "retrieved_at": "2026-10-14",
    "authority": "reference"
  },
  {
    "site_code": "ocean-park-1",
    "kind": "subdivision",
    "code": null,
    "name": "Ngọc Trai",
    "sources": [
      "https://market.vinhomes.vn/blog/ban-do-vinhomes-ocean-park"
    ],
    "body": "Phân khu thấp tầng công khai của OP1.",
    "source_published_at": null,
    "retrieved_at": "2026-10-14",
    "authority": "reference"
  },
  {
    "site_code": "ocean-park-1",
    "kind": "subdivision",
    "code": null,
    "name": "Hải Âu",
    "sources": [
      "https://market.vinhomes.vn/blog/ban-do-vinhomes-ocean-park"
    ],
    "body": "Phân khu thấp tầng công khai của OP1.",
    "source_published_at": null,
    "retrieved_at": "2026-10-14",
    "authority": "reference"
  },
  {
    "site_code": "ocean-park-1",
    "kind": "subdivision",
    "code": null,
    "name": "San Hô",
    "sources": [
      "https://market.vinhomes.vn/blog/ban-do-vinhomes-ocean-park"
    ],
    "body": "Phân khu thấp tầng công khai của OP1.",
    "source_published_at": null,
    "retrieved_at": "2026-10-14",
    "authority": "reference"
  },
  {
    "site_code": "ocean-park-1",
    "kind": "subdivision",
    "code": null,
    "name": "Sao Biển",
    "sources": [
      "https://market.vinhomes.vn/blog/ban-do-vinhomes-ocean-park"
    ],
    "body": "Phân khu thấp tầng công khai của OP1.",
    "source_published_at": null,
    "retrieved_at": "2026-10-14",
    "authority": "reference"
  },
  {
    "site_code": "ocean-park-1",
    "kind": "building",
    "code": "S1.01",
    "name": "Tòa S1.01",
    "sources": [
      "https://market.vinhomes.vn/blog/toa-nha-tai-phan-khu-sapphire-1-vinhomes-ocean-park-gia-lam-co-bao-nhieu-tang"
    ],
    "body": "Mã tòa công khai trong The Sapphire 1.",
    "source_published_at": "2024-07-05",
    "retrieved_at": "2026-10-14",
    "authority": "reference",
    "parent_name": "The Sapphire 1"
  },
  {
    "site_code": "ocean-park-1",
    "kind": "building",
    "code": "S1.02",
    "name": "Tòa S1.02",
    "sources": [
      "https://market.vinhomes.vn/blog/toa-nha-tai-phan-khu-sapphire-1-vinhomes-ocean-park-gia-lam-co-bao-nhieu-tang"
    ],
    "body": "Mã tòa công khai trong The Sapphire 1.",
    "source_published_at": "2024-07-05",
    "retrieved_at": "2026-10-14",
    "authority": "reference",
    "parent_name": "The Sapphire 1"
  },
  {
    "site_code": "ocean-park-1",
    "kind": "building",
    "code": "S1.03",
    "name": "Tòa S1.03",
    "sources": [
      "https://market.vinhomes.vn/blog/toa-nha-tai-phan-khu-sapphire-1-vinhomes-ocean-park-gia-lam-co-bao-nhieu-tang"
    ],
    "body": "Mã tòa công khai trong The Sapphire 1.",
    "source_published_at": "2024-07-05",
    "retrieved_at": "2026-10-14",
    "authority": "reference",
    "parent_name": "The Sapphire 1"
  },
  {
    "site_code": "ocean-park-1",
    "kind": "building",
    "code": "S1.05",
    "name": "Tòa S1.05",
    "sources": [
      "https://market.vinhomes.vn/blog/toa-nha-tai-phan-khu-sapphire-1-vinhomes-ocean-park-gia-lam-co-bao-nhieu-tang"
    ],
    "body": "Mã tòa công khai trong The Sapphire 1.",
    "source_published_at": "2024-07-05",
    "retrieved_at": "2026-10-14",
    "authority": "reference",
    "parent_name": "The Sapphire 1"
  },
  {
    "site_code": "ocean-park-1",
    "kind": "building",
    "code": "S1.06",
    "name": "Tòa S1.06",
    "sources": [
      "https://market.vinhomes.vn/blog/toa-nha-tai-phan-khu-sapphire-1-vinhomes-ocean-park-gia-lam-co-bao-nhieu-tang"
    ],
    "body": "Mã tòa công khai trong The Sapphire 1.",
    "source_published_at": "2024-07-05",
    "retrieved_at": "2026-10-14",
    "authority": "reference",
    "parent_name": "The Sapphire 1"
  },
  {
    "site_code": "ocean-park-1",
    "kind": "building",
    "code": "S1.07",
    "name": "Tòa S1.07",
    "sources": [
      "https://market.vinhomes.vn/blog/toa-nha-tai-phan-khu-sapphire-1-vinhomes-ocean-park-gia-lam-co-bao-nhieu-tang"
    ],
    "body": "Mã tòa công khai trong The Sapphire 1.",
    "source_published_at": "2024-07-05",
    "retrieved_at": "2026-10-14",
    "authority": "reference",
    "parent_name": "The Sapphire 1"
  },
  {
    "site_code": "ocean-park-1",
    "kind": "building",
    "code": "S1.08",
    "name": "Tòa S1.08",
    "sources": [
      "https://market.vinhomes.vn/blog/toa-nha-tai-phan-khu-sapphire-1-vinhomes-ocean-park-gia-lam-co-bao-nhieu-tang"
    ],
    "body": "Mã tòa công khai trong The Sapphire 1.",
    "source_published_at": "2024-07-05",
    "retrieved_at": "2026-10-14",
    "authority": "reference",
    "parent_name": "The Sapphire 1"
  },
  {
    "site_code": "ocean-park-1",
    "kind": "building",
    "code": "S1.09",
    "name": "Tòa S1.09",
    "sources": [
      "https://market.vinhomes.vn/blog/toa-nha-tai-phan-khu-sapphire-1-vinhomes-ocean-park-gia-lam-co-bao-nhieu-tang"
    ],
    "body": "Mã tòa công khai trong The Sapphire 1.",
    "source_published_at": "2024-07-05",
    "retrieved_at": "2026-10-14",
    "authority": "reference",
    "parent_name": "The Sapphire 1"
  },
  {
    "site_code": "ocean-park-1",
    "kind": "building",
    "code": "S1.10",
    "name": "Tòa S1.10",
    "sources": [
      "https://market.vinhomes.vn/blog/toa-nha-tai-phan-khu-sapphire-1-vinhomes-ocean-park-gia-lam-co-bao-nhieu-tang"
    ],
    "body": "Mã tòa công khai trong The Sapphire 1.",
    "source_published_at": "2024-07-05",
    "retrieved_at": "2026-10-14",
    "authority": "reference",
    "parent_name": "The Sapphire 1"
  },
  {
    "site_code": "ocean-park-1",
    "kind": "building",
    "code": "S1.11",
    "name": "Tòa S1.11",
    "sources": [
      "https://market.vinhomes.vn/blog/toa-nha-tai-phan-khu-sapphire-1-vinhomes-ocean-park-gia-lam-co-bao-nhieu-tang"
    ],
    "body": "Mã tòa công khai trong The Sapphire 1.",
    "source_published_at": "2024-07-05",
    "retrieved_at": "2026-10-14",
    "authority": "reference",
    "parent_name": "The Sapphire 1"
  },
  {
    "site_code": "ocean-park-1",
    "kind": "building",
    "code": "S1.12",
    "name": "Tòa S1.12",
    "sources": [
      "https://market.vinhomes.vn/blog/toa-nha-tai-phan-khu-sapphire-1-vinhomes-ocean-park-gia-lam-co-bao-nhieu-tang"
    ],
    "body": "Mã tòa công khai trong The Sapphire 1.",
    "source_published_at": "2024-07-05",
    "retrieved_at": "2026-10-14",
    "authority": "reference",
    "parent_name": "The Sapphire 1"
  },
  {
    "site_code": "ocean-park-1",
    "kind": "building",
    "code": "P1",
    "name": "Tòa P1",
    "sources": [
      "https://market.vinhomes.vn/en/blog/toa-nha-tai-phan-khu-the-pavilion-vinhomes-ocean-park-1-co-bao-nhieu-tang"
    ],
    "body": "Mã tòa công khai trong The Pavilion.",
    "source_published_at": "2024-07-18",
    "retrieved_at": "2026-10-14",
    "authority": "reference",
    "parent_name": "The Pavilion"
  },
  {
    "site_code": "ocean-park-1",
    "kind": "building",
    "code": "P2",
    "name": "Tòa P2",
    "sources": [
      "https://market.vinhomes.vn/en/blog/toa-nha-tai-phan-khu-the-pavilion-vinhomes-ocean-park-1-co-bao-nhieu-tang"
    ],
    "body": "Mã tòa công khai trong The Pavilion.",
    "source_published_at": "2024-07-18",
    "retrieved_at": "2026-10-14",
    "authority": "reference",
    "parent_name": "The Pavilion"
  },
  {
    "site_code": "ocean-park-1",
    "kind": "building",
    "code": "P3",
    "name": "Tòa P3",
    "sources": [
      "https://market.vinhomes.vn/en/blog/toa-nha-tai-phan-khu-the-pavilion-vinhomes-ocean-park-1-co-bao-nhieu-tang"
    ],
    "body": "Mã tòa công khai trong The Pavilion.",
    "source_published_at": "2024-07-18",
    "retrieved_at": "2026-10-14",
    "authority": "reference",
    "parent_name": "The Pavilion"
  },
  {
    "site_code": "ocean-park-1",
    "kind": "building",
    "code": "P4",
    "name": "Tòa P4",
    "sources": [
      "https://market.vinhomes.vn/en/blog/toa-nha-tai-phan-khu-the-pavilion-vinhomes-ocean-park-1-co-bao-nhieu-tang"
    ],
    "body": "Mã tòa công khai trong The Pavilion.",
    "source_published_at": "2024-07-18",
    "retrieved_at": "2026-10-14",
    "authority": "reference",
    "parent_name": "The Pavilion"
  },
  {
    "site_code": "ocean-park-1",
    "kind": "building",
    "code": "R1.01",
    "name": "Tòa R1.01",
    "sources": [
      "https://vinhomes.vn/vi/tong-quan-mat-bang-the-zenpark-vinhomes-ocean-park"
    ],
    "body": "Mã tòa công khai trong The Zenpark.",
    "source_published_at": null,
    "retrieved_at": "2026-10-14",
    "authority": "reference",
    "parent_name": "The Zenpark"
  },
  {
    "site_code": "ocean-park-1",
    "kind": "building",
    "code": "R1.02",
    "name": "Tòa R1.02",
    "sources": [
      "https://vinhomes.vn/vi/tong-quan-mat-bang-the-zenpark-vinhomes-ocean-park"
    ],
    "body": "Mã tòa công khai trong The Zenpark.",
    "source_published_at": null,
    "retrieved_at": "2026-10-14",
    "authority": "reference",
    "parent_name": "The Zenpark"
  },
  {
    "site_code": "ocean-park-1",
    "kind": "building",
    "code": "R1.03",
    "name": "Tòa R1.03",
    "sources": [
      "https://vinhomes.vn/vi/tong-quan-mat-bang-the-zenpark-vinhomes-ocean-park"
    ],
    "body": "Mã tòa công khai trong The Zenpark.",
    "source_published_at": null,
    "retrieved_at": "2026-10-14",
    "authority": "reference",
    "parent_name": "The Zenpark"
  },
  {
    "site_code": "ocean-park-1",
    "kind": "building",
    "code": "R1.05",
    "name": "Tòa R1.05",
    "sources": [
      "https://vinhomes.vn/vi/tong-quan-mat-bang-the-zenpark-vinhomes-ocean-park"
    ],
    "body": "Mã tòa công khai trong The Zenpark.",
    "source_published_at": null,
    "retrieved_at": "2026-10-14",
    "authority": "reference",
    "parent_name": "The Zenpark"
  },
  {
    "site_code": "ocean-park-1",
    "kind": "building",
    "code": "BE1",
    "name": "Tòa BE1",
    "sources": [
      "https://market.vinhomes.vn/phan-khu/the-beverly-vinhomes-ocean-park"
    ],
    "body": "Mã tòa công khai trong The Beverly.",
    "source_published_at": null,
    "retrieved_at": "2026-10-14",
    "authority": "reference",
    "parent_name": "The Beverly"
  },
  {
    "site_code": "ocean-park-1",
    "kind": "building",
    "code": "BE2",
    "name": "Tòa BE2",
    "sources": [
      "https://market.vinhomes.vn/phan-khu/the-beverly-vinhomes-ocean-park"
    ],
    "body": "Mã tòa công khai trong The Beverly.",
    "source_published_at": null,
    "retrieved_at": "2026-10-14",
    "authority": "reference",
    "parent_name": "The Beverly"
  },
  {
    "site_code": "ocean-park-1",
    "kind": "building",
    "code": "BE3",
    "name": "Tòa BE3",
    "sources": [
      "https://market.vinhomes.vn/phan-khu/the-beverly-vinhomes-ocean-park"
    ],
    "body": "Mã tòa công khai trong The Beverly.",
    "source_published_at": null,
    "retrieved_at": "2026-10-14",
    "authority": "reference",
    "parent_name": "The Beverly"
  },
  {
    "site_code": "ocean-park-1",
    "kind": "building",
    "code": "BE4",
    "name": "Tòa BE4",
    "sources": [
      "https://market.vinhomes.vn/phan-khu/the-beverly-vinhomes-ocean-park"
    ],
    "body": "Mã tòa công khai trong The Beverly.",
    "source_published_at": null,
    "retrieved_at": "2026-10-14",
    "authority": "reference",
    "parent_name": "The Beverly"
  },
  {
    "site_code": "ocean-park-1",
    "kind": "building",
    "code": "S2.01",
    "name": "Tòa S2.01",
    "sources": [
      "https://market.vinhomes.vn/phan-khu/the-sapphire-2-vinhomes-ocean-park"
    ],
    "body": "Mã tòa công khai trong The Sapphire 2.",
    "source_published_at": null,
    "retrieved_at": "2026-10-14",
    "authority": "reference",
    "parent_name": "The Sapphire 2"
  },
  {
    "site_code": "ocean-park-1",
    "kind": "building",
    "code": "S2.02",
    "name": "Tòa S2.02",
    "sources": [
      "https://market.vinhomes.vn/phan-khu/the-sapphire-2-vinhomes-ocean-park"
    ],
    "body": "Mã tòa công khai trong The Sapphire 2.",
    "source_published_at": null,
    "retrieved_at": "2026-10-14",
    "authority": "reference",
    "parent_name": "The Sapphire 2"
  },
  {
    "site_code": "ocean-park-1",
    "kind": "building",
    "code": "S2.10",
    "name": "Tòa S2.10",
    "sources": [
      "https://market.vinhomes.vn/phan-khu/the-sapphire-2-vinhomes-ocean-park"
    ],
    "body": "Mã tòa công khai trong The Sapphire 2.",
    "source_published_at": null,
    "retrieved_at": "2026-10-14",
    "authority": "reference",
    "parent_name": "The Sapphire 2"
  },
  {
    "site_code": "ocean-park-1",
    "kind": "building",
    "code": "S2.17",
    "name": "Tòa S2.17",
    "sources": [
      "https://market.vinhomes.vn/phan-khu/the-sapphire-2-vinhomes-ocean-park"
    ],
    "body": "Mã tòa công khai trong The Sapphire 2.",
    "source_published_at": null,
    "retrieved_at": "2026-10-14",
    "authority": "reference",
    "parent_name": "The Sapphire 2"
  },
  {
    "site_code": "ocean-park-1",
    "kind": "building",
    "code": "S2.03",
    "name": "Tòa S2.03",
    "sources": [
      "https://market.vinhomes.vn/blog/toa-s203-vinhomes-ocean-park"
    ],
    "body": "Nguồn lịch sử nêu tòa thuộc The Sapphire 2.",
    "source_published_at": "2021-12-26",
    "retrieved_at": "2026-10-14",
    "authority": "reference",
    "parent_name": "The Sapphire 2"
  },
  {
    "site_code": "ocean-park-1",
    "kind": "building",
    "code": "S2.07",
    "name": "Tòa S2.07",
    "sources": [
      "https://market.vinhomes.vn/blog/s207-vinhomes-ocean-park"
    ],
    "body": "Nguồn lịch sử nêu tòa thuộc The Sapphire 2.",
    "source_published_at": "2021-12-26",
    "retrieved_at": "2026-10-14",
    "authority": "reference",
    "parent_name": "The Sapphire 2"
  },
  {
    "site_code": "ocean-park-1",
    "kind": "building",
    "code": "S2.08",
    "name": "Tòa S2.08",
    "sources": [
      "https://market.vinhomes.vn/thu-cap/2-pn-1-1-toilet-toa-s2-08-phan-khu-the-sapphire-2-vinhomes-ocean-park"
    ],
    "body": "Trang giao dịch công khai nêu The Sapphire 2.",
    "source_published_at": null,
    "retrieved_at": "2026-10-14",
    "authority": "reference",
    "parent_name": "The Sapphire 2"
  },
  {
    "site_code": "ocean-park-2",
    "kind": "subdivision",
    "code": null,
    "name": "Ngọc Trai",
    "sources": [
      "https://market.vinhomes.vn/phan-khu/cha-la-vinhomes-ocean-park-2"
    ],
    "body": "Phân khu công khai thuộc OP2.",
    "source_published_at": null,
    "retrieved_at": "2026-10-14",
    "authority": "reference"
  },
  {
    "site_code": "ocean-park-2",
    "kind": "subdivision",
    "code": null,
    "name": "Chà Là",
    "sources": [
      "https://market.vinhomes.vn/phan-khu/cha-la-vinhomes-ocean-park-2"
    ],
    "body": "Phân khu công khai thuộc OP2.",
    "source_published_at": null,
    "retrieved_at": "2026-10-14",
    "authority": "reference"
  },
  {
    "site_code": "ocean-park-2",
    "kind": "subdivision",
    "code": null,
    "name": "Sao Biển",
    "sources": [
      "https://market.vinhomes.vn/phan-khu/cha-la-vinhomes-ocean-park-2"
    ],
    "body": "Phân khu công khai thuộc OP2.",
    "source_published_at": null,
    "retrieved_at": "2026-10-14",
    "authority": "reference"
  },
  {
    "site_code": "ocean-park-2",
    "kind": "subdivision",
    "code": null,
    "name": "Kinh Đô Ánh Sáng",
    "sources": [
      "https://market.vinhomes.vn/phan-khu/cha-la-vinhomes-ocean-park-2"
    ],
    "body": "Phân khu công khai thuộc OP2.",
    "source_published_at": null,
    "retrieved_at": "2026-10-14",
    "authority": "reference"
  },
  {
    "site_code": "ocean-park-2",
    "kind": "subdivision",
    "code": null,
    "name": "San Hô",
    "sources": [
      "https://market.vinhomes.vn/phan-khu/cha-la-vinhomes-ocean-park-2"
    ],
    "body": "Phân khu công khai thuộc OP2.",
    "source_published_at": null,
    "retrieved_at": "2026-10-14",
    "authority": "reference"
  },
  {
    "site_code": "ocean-park-2",
    "kind": "subdivision",
    "code": null,
    "name": "Cọ Xanh",
    "sources": [
      "https://market.vinhomes.vn/phan-khu/cha-la-vinhomes-ocean-park-2"
    ],
    "body": "Phân khu công khai thuộc OP2.",
    "source_published_at": null,
    "retrieved_at": "2026-10-14",
    "authority": "reference"
  },
  {
    "site_code": "ocean-park-2",
    "kind": "subdivision",
    "code": null,
    "name": "Hải Âu",
    "sources": [
      "https://market.vinhomes.vn/phan-khu/cha-la-vinhomes-ocean-park-2"
    ],
    "body": "Phân khu công khai thuộc OP2.",
    "source_published_at": null,
    "retrieved_at": "2026-10-14",
    "authority": "reference"
  },
  {
    "site_code": "ocean-park-2",
    "kind": "subdivision",
    "code": null,
    "name": "Đảo Dừa",
    "sources": [
      "https://market.vinhomes.vn/phan-khu/cha-la-vinhomes-ocean-park-2"
    ],
    "body": "Phân khu công khai thuộc OP2.",
    "source_published_at": null,
    "retrieved_at": "2026-10-14",
    "authority": "reference"
  },
  {
    "site_code": "ocean-park-3",
    "kind": "subdivision",
    "code": null,
    "name": "Thời Đại",
    "sources": [
      "https://oceanpark3.vinhomes.vn/"
    ],
    "body": "Phân khu công khai thuộc OP3.",
    "source_published_at": null,
    "retrieved_at": "2026-10-14",
    "authority": "reference"
  },
  {
    "site_code": "ocean-park-3",
    "kind": "subdivision",
    "code": null,
    "name": "Vịnh Tây",
    "sources": [
      "https://oceanpark3.vinhomes.vn/"
    ],
    "body": "Phân khu công khai thuộc OP3.",
    "source_published_at": null,
    "retrieved_at": "2026-10-14",
    "authority": "reference"
  },
  {
    "site_code": "ocean-park-3",
    "kind": "subdivision",
    "code": null,
    "name": "Phố Biển",
    "sources": [
      "https://oceanpark3.vinhomes.vn/"
    ],
    "body": "Phân khu công khai thuộc OP3.",
    "source_published_at": null,
    "retrieved_at": "2026-10-14",
    "authority": "reference"
  },
  {
    "site_code": "ocean-park-3",
    "kind": "subdivision",
    "code": null,
    "name": "Ánh Dương",
    "sources": [
      "https://oceanpark3.vinhomes.vn/"
    ],
    "body": "Phân khu công khai thuộc OP3.",
    "source_published_at": null,
    "retrieved_at": "2026-10-14",
    "authority": "reference"
  },
  {
    "site_code": "ocean-park-3",
    "kind": "subdivision",
    "code": null,
    "name": "Vịnh Thiên Đường",
    "sources": [
      "https://oceanpark3.vinhomes.vn/"
    ],
    "body": "Phân khu công khai thuộc OP3.",
    "source_published_at": null,
    "retrieved_at": "2026-10-14",
    "authority": "reference"
  },
  {
    "site_code": "ocean-park-3",
    "kind": "subdivision",
    "code": null,
    "name": "Đảo Ngọc",
    "sources": [
      "https://oceanpark3.vinhomes.vn/"
    ],
    "body": "Phân khu công khai thuộc OP3.",
    "source_published_at": null,
    "retrieved_at": "2026-10-14",
    "authority": "reference"
  },
  {
    "site_code": "ocean-park-3",
    "kind": "subdivision",
    "code": null,
    "name": "Vịnh Xanh",
    "sources": [
      "https://oceanpark3.vinhomes.vn/"
    ],
    "body": "Phân khu công khai thuộc OP3.",
    "source_published_at": null,
    "retrieved_at": "2026-10-14",
    "authority": "reference"
  },
  {
    "site_code": "ocean-park-3",
    "kind": "subdivision",
    "code": null,
    "name": "Hải Đăng",
    "sources": [
      "https://oceanpark3.vinhomes.vn/"
    ],
    "body": "Phân khu công khai thuộc OP3.",
    "source_published_at": null,
    "retrieved_at": "2026-10-14",
    "authority": "reference"
  },
  {
    "site_code": "ocean-park-1",
    "kind": "amenity",
    "code": null,
    "name": "Biển hồ nước mặn",
    "sources": [
      "https://oceanpark.vinhomes.vn/gioi-thieu-diem-nhan/"
    ],
    "body": "Tiện ích công khai được giới thiệu tại OP1.",
    "source_published_at": null,
    "retrieved_at": "2026-10-14",
    "authority": "reference"
  },
  {
    "site_code": "ocean-park-1",
    "kind": "amenity",
    "code": null,
    "name": "Công viên gym ngoài trời",
    "sources": [
      "https://oceanpark.vinhomes.vn/gioi-thieu-diem-nhan/"
    ],
    "body": "Tiện ích công khai được giới thiệu tại OP1.",
    "source_published_at": null,
    "retrieved_at": "2026-10-14",
    "authority": "reference"
  },
  {
    "site_code": "ocean-park-1",
    "kind": "amenity",
    "code": null,
    "name": "Công viên BBQ",
    "sources": [
      "https://oceanpark.vinhomes.vn/gioi-thieu-diem-nhan/"
    ],
    "body": "Tiện ích công khai được giới thiệu tại OP1.",
    "source_published_at": null,
    "retrieved_at": "2026-10-14",
    "authority": "reference"
  },
  {
    "site_code": "ocean-park-1",
    "kind": "amenity",
    "code": null,
    "name": "Hồ Ngọc Trai",
    "sources": [
      "https://market.vinhomes.vn/phan-khu/the-beverly-vinhomes-ocean-park"
    ],
    "body": "Địa điểm/dịch vụ được liệt kê cho dự án OP1.",
    "source_published_at": null,
    "retrieved_at": "2026-10-14",
    "authority": "reference"
  },
  {
    "site_code": "ocean-park-1",
    "kind": "amenity",
    "code": null,
    "name": "Vincom Mega Mall Ocean Park",
    "sources": [
      "https://market.vinhomes.vn/phan-khu/the-beverly-vinhomes-ocean-park"
    ],
    "body": "Địa điểm/dịch vụ được liệt kê cho dự án OP1.",
    "source_published_at": null,
    "retrieved_at": "2026-10-14",
    "authority": "reference"
  },
  {
    "site_code": "ocean-park-1",
    "kind": "amenity",
    "code": null,
    "name": "Vinschool",
    "sources": [
      "https://market.vinhomes.vn/phan-khu/the-beverly-vinhomes-ocean-park"
    ],
    "body": "Địa điểm/dịch vụ được liệt kê cho dự án OP1.",
    "source_published_at": null,
    "retrieved_at": "2026-10-14",
    "authority": "reference"
  },
  {
    "site_code": "ocean-park-1",
    "kind": "amenity",
    "code": null,
    "name": "Vin University",
    "sources": [
      "https://market.vinhomes.vn/phan-khu/the-beverly-vinhomes-ocean-park"
    ],
    "body": "Địa điểm/dịch vụ được liệt kê cho dự án OP1.",
    "source_published_at": null,
    "retrieved_at": "2026-10-14",
    "authority": "reference"
  },
  {
    "site_code": "ocean-park-1",
    "kind": "amenity",
    "code": null,
    "name": "Phòng khám quốc tế Vinmec Ocean Park",
    "sources": [
      "https://market.vinhomes.vn/phan-khu/the-beverly-vinhomes-ocean-park"
    ],
    "body": "Địa điểm/dịch vụ được liệt kê cho dự án OP1.",
    "source_published_at": null,
    "retrieved_at": "2026-10-14",
    "authority": "reference"
  },
  {
    "site_code": "ocean-park-2",
    "kind": "amenity",
    "code": null,
    "name": "Empire Park",
    "sources": [
      "https://theempire.vinhomes.vn/"
    ],
    "body": "Tiện ích công khai được giới thiệu tại OP2.",
    "source_published_at": null,
    "retrieved_at": "2026-10-14",
    "authority": "reference"
  },
  {
    "site_code": "ocean-park-2",
    "kind": "amenity",
    "code": null,
    "name": "Silk Park",
    "sources": [
      "https://theempire.vinhomes.vn/"
    ],
    "body": "Tiện ích công khai được giới thiệu tại OP2.",
    "source_published_at": null,
    "retrieved_at": "2026-10-14",
    "authority": "reference"
  },
  {
    "site_code": "ocean-park-2",
    "kind": "amenity",
    "code": null,
    "name": "Kingdom Avenue",
    "sources": [
      "https://theempire.vinhomes.vn/"
    ],
    "body": "Tiện ích công khai được giới thiệu tại OP2.",
    "source_published_at": null,
    "retrieved_at": "2026-10-14",
    "authority": "reference"
  },
  {
    "site_code": "ocean-park-2",
    "kind": "amenity",
    "code": null,
    "name": "VinWonders Wave Park",
    "sources": [
      "https://market.vinhomes.vn/phan-khu/san-ho-vinhomes-ocean-park-2"
    ],
    "body": "Nguồn Vinhomes Market giới thiệu công viên sóng tại OP2.",
    "source_published_at": null,
    "retrieved_at": "2026-10-14",
    "authority": "reference"
  },
  {
    "site_code": "ocean-park-2",
    "kind": "amenity",
    "code": null,
    "name": "Công viên Lễ Hội",
    "sources": [
      "https://market.vinhomes.vn/phan-khu/cha-la-vinhomes-ocean-park-2"
    ],
    "body": "Công viên được giới thiệu tại khu Chà Là.",
    "source_published_at": null,
    "retrieved_at": "2026-10-14",
    "authority": "reference",
    "parent_name": "Chà Là"
  },
  {
    "site_code": "ocean-park-2",
    "kind": "amenity",
    "code": null,
    "name": "Công viên Nghệ Thuật",
    "sources": [
      "https://market.vinhomes.vn/phan-khu/cha-la-vinhomes-ocean-park-2"
    ],
    "body": "Công viên được giới thiệu tại khu Chà Là.",
    "source_published_at": null,
    "retrieved_at": "2026-10-14",
    "authority": "reference",
    "parent_name": "Chà Là"
  },
  {
    "site_code": "ocean-park-2",
    "kind": "amenity",
    "code": null,
    "name": "Công viên Âm Nhạc",
    "sources": [
      "https://market.vinhomes.vn/phan-khu/cha-la-vinhomes-ocean-park-2"
    ],
    "body": "Công viên được giới thiệu tại khu Chà Là.",
    "source_published_at": null,
    "retrieved_at": "2026-10-14",
    "authority": "reference",
    "parent_name": "Chà Là"
  },
  {
    "site_code": "ocean-park-3",
    "kind": "amenity",
    "code": null,
    "name": "Paradise Bay",
    "sources": [
      "https://oceanpark3.vinhomes.vn/brochure/"
    ],
    "body": "Tiện ích được giới thiệu trong tài liệu OP3.",
    "source_published_at": null,
    "retrieved_at": "2026-10-14",
    "authority": "reference"
  },
  {
    "site_code": "ocean-park-3",
    "kind": "amenity",
    "code": null,
    "name": "Tropical Lagoon",
    "sources": [
      "https://oceanpark3.vinhomes.vn/brochure/"
    ],
    "body": "Tiện ích được giới thiệu trong tài liệu OP3.",
    "source_published_at": null,
    "retrieved_at": "2026-10-14",
    "authority": "reference"
  },
  {
    "site_code": "ocean-park-3",
    "kind": "amenity",
    "code": null,
    "name": "Four Seasons",
    "sources": [
      "https://oceanpark3.vinhomes.vn/brochure/"
    ],
    "body": "Tiện ích được giới thiệu trong tài liệu OP3.",
    "source_published_at": null,
    "retrieved_at": "2026-10-14",
    "authority": "reference"
  },
  {
    "site_code": "ocean-park-3",
    "kind": "amenity",
    "code": null,
    "name": "Olympics Swimming Pool",
    "sources": [
      "https://oceanpark3.vinhomes.vn/brochure/"
    ],
    "body": "Tiện ích được giới thiệu trong tài liệu OP3.",
    "source_published_at": null,
    "retrieved_at": "2026-10-14",
    "authority": "reference"
  },
  {
    "site_code": "ocean-park-3",
    "kind": "amenity",
    "code": null,
    "name": "Aqua Bay",
    "sources": [
      "https://oceanpark3.vinhomes.vn/brochure/"
    ],
    "body": "Tiện ích được giới thiệu trong tài liệu OP3.",
    "source_published_at": null,
    "retrieved_at": "2026-10-14",
    "authority": "reference"
  },
  {
    "site_code": "ocean-park-3",
    "kind": "amenity",
    "code": null,
    "name": "Aquarium",
    "sources": [
      "https://oceanpark3.vinhomes.vn/brochure/"
    ],
    "body": "Tiện ích được giới thiệu trong tài liệu OP3.",
    "source_published_at": null,
    "retrieved_at": "2026-10-14",
    "authority": "reference"
  },
  {
    "site_code": "ocean-park-3",
    "kind": "amenity",
    "code": null,
    "name": "Marina Square",
    "sources": [
      "https://oceanpark3.vinhomes.vn/brochure/"
    ],
    "body": "Tiện ích được giới thiệu trong tài liệu OP3.",
    "source_published_at": null,
    "retrieved_at": "2026-10-14",
    "authority": "reference"
  },
  {
    "site_code": "ocean-park-3",
    "kind": "amenity",
    "code": null,
    "name": "BBQ Garden",
    "sources": [
      "https://oceanpark3.vinhomes.vn/brochure/"
    ],
    "body": "Tiện ích được giới thiệu trong tài liệu OP3.",
    "source_published_at": null,
    "retrieved_at": "2026-10-14",
    "authority": "reference"
  },
  {
    "site_code": "ocean-park-3",
    "kind": "amenity",
    "code": null,
    "name": "Gym Park",
    "sources": [
      "https://oceanpark3.vinhomes.vn/brochure/"
    ],
    "body": "Tiện ích được giới thiệu trong tài liệu OP3.",
    "source_published_at": null,
    "retrieved_at": "2026-10-14",
    "authority": "reference"
  },
  {
    "site_code": "ocean-park-3",
    "kind": "amenity",
    "code": null,
    "name": "Coral",
    "sources": [
      "https://oceanpark3.vinhomes.vn/brochure/"
    ],
    "body": "Tiện ích được giới thiệu trong tài liệu OP3.",
    "source_published_at": null,
    "retrieved_at": "2026-10-14",
    "authority": "reference"
  }
]
```

## 5. Dữ liệu không thể lấy thật từ các nguồn này

| Dataset còn cần | Bộ trường/tài liệu tối thiểu | Điều kiện nạp |
|---|---|---|
| Master chuẩn của cả ba đô thị | Site/zone/building/unit code chính thức, quan hệ cha-con, địa chỉ hiện hành, bàn giao/hoạt động, nguồn/hồ sơ chủ sở hữu | Đơn vị vận hành đối chiếu và cấp; catalog công khai chỉ làm danh sách đối soát |
| Cư dân/cư trú xác thực | External resident ID, tài khoản liên hệ cần thiết, site/building/unit, owner/tenant/household, hiệu lực, bằng chứng hoặc trạng thái xác minh, người xác nhận | Export/API được phép từ đơn vị quản lý hồ sơ; không lấy nhân vật phỏng vấn/bình luận bán hàng làm cư dân hệ thống |
| Nhân sự thực tế | Employee ID, tên, tài khoản, đội/nhà thầu, chuyên môn, phạm vi, trạng thái, người xác nhận | Danh sách do đơn vị quản lý nhân sự cấp; không dùng ảnh/tên sale trên website |
| Ca trực/capacity/on-call | Employee/team, bắt đầu/kết thúc có timezone, ngày nghỉ, capacity, người dự phòng, thời hạn áp dụng | Quản lý vận hành xác nhận; không sinh lịch mẫu rồi gọi ca thật |
| Catalog dịch vụ vận hành | Mã dịch vụ, loại yêu cầu, site/zone/building, điều kiện được phục vụ, intake/route, đội phụ trách, approval, SLA/escalation, SOP/checklist/ảnh/tiêu chí nghiệm thu | Chốt owner từng dịch vụ; chỉ mở thực thi khi có route và nguồn lực thật |
| Phí/giờ/danh bạ | Quyết định số/phiên bản, đối tượng/site áp dụng, phí/đơn vị/VAT, giờ nghỉ/lễ, điều kiện booking/hủy, số trực và người sở hữu, hiệu lực | Bản hiện hành từ đơn vị vận hành/chủ dịch vụ; không biến giá trên bài bán hàng thành phí production |
| Tài liệu nghiệp vụ chính thức | Sổ tay, nội quy, SOP kỹ thuật/an ninh/vệ sinh, an toàn theo tòa, tài sản/bảo hành, mẫu/biểu, owner và phiên bản | Giữ archive/reference; chỉ approved khi đủ nguồn và hồ sơ xác nhận |

Ba site có catalog công khai không chứng minh đã có dataset vận hành thật. Những chỗ chưa được cấp phải giữ trống/pending, không tạo người, cư trú, ca hoặc tuyến giả để làm đầy database. Bộ tiếp nhận có thể hỗ trợ chuẩn hóa/dry-run và báo lỗi; người sở hữu dữ liệu vẫn phải cung cấp dữ kiện private và xác nhận tính hiện hành.

## 6. Cách nghiệm thu sau khi đơn vị vận hành cấp dữ liệu

1. Đối soát mã chính thức với catalog tham khảo theo site, báo mismatch/alias/duplicate; không tự merge khác site vì cùng tên.
2. Kiểm tra FK cư trú, thời gian hiệu lực, nhân viên/ca/phạm vi, SOP/route và nguồn duyệt trước khi cấp quyền thực thi.
3. Báo số dòng accepted/rejected/pending_review theo dataset/site, ngày nguồn và owner; không gộp reference với verified/approved.
4. Test import bằng fixture riêng không Agent; kiểm tra cách ly OP1/2/3 và không mở quyền qua một tên marketing. Theo dõi dữ liệu sống từ API chính thức nếu được cấp, thay vì hứa đồng bộ bằng crawl website.

Không có xác nhận cư dân/nhân sự thật hoặc giá/giờ hiện hành mới được nhận trong lượt nghiên cứu này. Không gọi hệ thống nghiệp vụ chính thức có đăng nhập. Nghiên cứu không chứng nhận catalog đầy đủ, quyền sử dụng API chính thức hay SOP của toàn thương hiệu.
