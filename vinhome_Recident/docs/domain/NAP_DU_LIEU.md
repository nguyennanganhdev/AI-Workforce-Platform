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

**Lịch sử xử lý.** Mỗi yêu cầu lịch sử có đủ những gì đã xảy ra với nó: cuộc trò chuyện (lời cư dân và biên nhận của lễ tân), sự kiện theo thứ tự thời gian, việc tiếp nhận của Ban quản lý, phương án đã được hai bên duyệt, phiếu việc và phân công, và hồ sơ cư dân kèm dòng thời gian công khai. Profile `standard`: 900 yêu cầu, 10.637 sự kiện, 656 phiếu việc, 1.800 tin nhắn, 859 hồ sơ cư dân (497 đã hoàn tất, 99 chờ cư dân xác nhận, 263 đang xử lý). Việc chỉ đi tới đâu nhân viên gánh được: không ai quá 3 việc đang làm, nên yêu cầu nào không còn ai rảnh thì nằm ở hàng chờ (`triaging`: 136 yêu cầu), 60 yêu cầu đang giao hoặc đang làm. Kỹ thuật viên chia ba ca nối nhau (06:00, 14:00, 22:00 giờ Việt Nam), mỗi ca năm người: ba người không dở tay việc nào và còn đúng một chỗ nhận việc mới, hai người đang làm dở và đã kín việc. Không mốc nào sau thời điểm chạy. Chưa có ảnh bằng chứng, hóa đơn sửa chữa và kết quả kiểm tra chất lượng cho các phiếu việc mẫu. Cùng `--seed` cho cùng nội dung. Chạy lại không thêm gì (đã đo: hai lần liên tiếp cùng số lượng, mỗi lần 13 đến 24 giây). Đổi cấu hình (`test` rồi `standard`) trên cùng một database không được hỗ trợ: dùng `reset` rồi dựng lại. Nhân vật cố định `mock-an`, `mock-chau`, `mock-binh`, `mock-dung`, `mock-em`, `mock-hoa`, `mock-khoa`, `mock-giang`, `mock-minh` được mô tả ở [KICH_BAN_VANG.md §3](KICH_BAN_VANG.md). Mọi nội dung là **dữ liệu mẫu**, không phải quy định thật.

## 2. Dữ liệu thật

```
python -m vinhomes_api.database import --dir ./du-lieu --dry-run     # xem lỗi, không ghi gì
python -m vinhomes_api.database import --dir ./du-lieu               # ghi
```

- Mỗi loại một tệp: `buildings.csv`, `units.csv`, … (hoặc `.json`: danh sách các đối tượng cùng tên cột). UTF-8, dòng đầu là tên cột. Tệp nào không có thì bỏ qua.
- Các dòng tham chiếu nhau **bằng mã**, không bằng id. Thứ tự nạp cố định (bảng dưới từ trên xuống) nên mã nào được dùng phải có ở tệp trên hoặc đã có sẵn trong database.
- **Một giao dịch.** Dòng nào sai (mã không tồn tại, giá trị lạ, thiếu cột) được báo kèm tên tệp và số dòng; có lỗi thì **không ghi gì**. `--dry-run` luôn không ghi.
- **Chạy lại cùng tệp không thêm gì.** Lệnh chỉ thêm dòng mới; không sửa dòng đã có (trừ `zone_settings`, là cấu hình nên nạp lại thì cập nhật). Muốn sửa dữ liệu đã nạp, sửa qua ứng dụng quản trị hoặc `reset` rồi nạp lại.
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
| `zone_settings` | | `zone_code` (để trống: cả khu), `visit_max_waiting`, `visit_max_days_ahead`, `visit_max_hours`, `visit_auto_approve_purposes` (cách nhau `\|`), `visit_auto_approve_max_guests`, `visit_early_minutes`, `card_limit_resident`, `card_limit_vehicle`, `amenity_payment_hold_minutes`, `note` | Hạn mức theo phân khu (xem dưới). **Dòng trong tệp thay cả dòng cấu hình của phân khu đó**; ô trống nghĩa là kế thừa. Khác các tệp còn lại, nạp lại với giá trị mới thì cập nhật |
| `amenities` | `code`, `name`, `category_code`, `zone_code` | `areas` (cách nhau `\|`), `price`, `slot_minutes`, `open_time`, `close_time`, `max_advance_days`, `cancel_before_hours`, `weekly_quota`, `max_guests`, `rules_note` | |
| `handbook` | `title`, `body_md` | `audience` (`resident`, `staff`, `management`, cách nhau `\|`; mặc định `resident`), `zone_code`, `seq`, `language` | Cẩm nang cho cư dân hoặc quy trình nội bộ |
| `policies` | `code`, `title`, `kind`, `version`, `effective_from` | `body_md`, `audience`, `zone_code`, `unit_kind`, `language`, `effective_to` | `kind`: `terms_of_use`, `privacy_policy`, `building_rules`, `construction_rules`, `amenity_rules`, `fee_table`, `faq` |
| `announcements` | `code`, `kind`, `title`, `body_md` | `summary`, `status` (`draft`/`published`), `building_codes` (cách nhau `\|`), `published_at` | `published` chỉ ghi nội dung và thời điểm phát hành, không gửi thông báo cho ai; muốn báo cho cư dân thì phát hành bằng ứng dụng |

Tài liệu tri thức nạp ở `handbook`, `policies`, `announcements` chính là **gói tri thức** mà platform lấy qua `GET /integration/v1/knowledge/pack` ([HOP_DONG_TICH_HOP.md §7](HOP_DONG_TICH_HOP.md)). Tài liệu chỉ cho BQL chỉ được xếp vào gói của BQL.

### Hạn mức theo phân khu

Mỗi phân khu có thể đặt hạn mức riêng; ô nào để trống thì kế thừa: **phân khu, rồi dòng cho cả khu (`zone_code` trống), rồi giá trị mặc định** (cột "mặc định"). Không có dòng nào thì mọi nơi chạy theo mặc định.

| Cột | Ý nghĩa | Mặc định |
|---|---|---|
| `visit_max_waiting` | Số lượt khách đang chờ tối đa của một căn | 10 |
| `visit_max_days_ahead` | Báo khách trước tối đa bao nhiêu ngày | 30 |
| `visit_max_hours` | Một lượt khách kéo dài tối đa bao nhiêu giờ | 72 |
| `visit_auto_approve_purposes` | Mục đích được duyệt ngay (`family_visit`, `delivery`, `service_provider`, `business`, `other`) | `family_visit\|delivery` |
| `visit_auto_approve_max_guests` | Số khách tối đa để được duyệt ngay; 0 là luôn qua lễ tân | 5 |
| `visit_early_minutes` | Khách vào cổng sớm hơn giờ hẹn tối đa bao nhiêu phút | 15 |
| `card_limit_resident`, `card_limit_vehicle` | Số thẻ cư dân và thẻ xe tối đa của một căn | 6 và 4 |
| `amenity_payment_hold_minutes` | Giữ chỗ tiện ích có phí bao nhiêu phút chờ thanh toán | 15 |

Hạn mức áp dụng cho một căn đọc được ở `GET /resident/units/{unit_id}/rules`. Thế giới mẫu đặt riêng cho khu villa (Hải Âu): 20 lượt chờ, 96 giờ, tự duyệt tới 8 khách, 8 thẻ cư dân và 6 thẻ xe.

## 3. Việc cần làm sau khi nạp

- **Đăng nhập.** Lệnh nạp tạo người và tư cách thành viên nhưng **chưa tạo mật khẩu**. Cấp mật khẩu đầu tiên bằng `python -m vinhomes_api.database accounts --users MÃ_HOẶC_EMAIL,… --password-env TÊN_BIẾN` (người đã có mật khẩu được giữ nguyên); quản trị viên đầu tiên tạo bằng `accounts --create-admin EMAIL --password-env TÊN_BIẾN`. Xem [deploy/README.md](../../deploy/README.md). Màn hình quản trị chỉ đặt lại được mật khẩu đã có.
- **Tìm người rảnh** cần ca (`shifts`) và chuyên môn (`specialties`).
- **Hạn xử lý** (SLA) lấy từ bảng `sla_policies`; dữ liệu mẫu có sẵn chính sách cho Ban quản lý mẫu. Với Ban quản lý khác cần thêm chính sách.
- **Đăng ký platform** làm client: `python -m vinhomes_api.database client --id platform --kind platform --accepts-cases`; in bí mật một lần.
- **Tác vụ hạn** `python -m vinhomes_api.jobs sweep` cần chạy định kỳ (compose có sẵn dịch vụ `scheduler`).

## 4. Đặt lại

```
python -m vinhomes_api.database reset --confirm TEN_DATABASE
```

Xóa mọi thứ trong schema và dựng lại trống (migration chạy lại). Phải nhắc đúng tên database. Sau đó chạy lại `role` để cấp quyền cho vai trò của API, rồi `seed`, rồi nạp lại tri thức (mục 5).

Lệnh này xóa cả extension `vector` (nó nằm trong schema bị xóa). Trong gói, chủ database là superuser nên migration tự tạo lại. Với PostgreSQL ở nơi khác mà chủ database không phải superuser, `reset` sẽ dừng ở `0013_knowledge.sql` và để database trống: người quản trị ở đó chạy lại `create extension vector`, rồi chạy `migrate`.

## 5. Tri thức để trợ lý trả lời

Khi cư dân hỏi thông tin (số điện thoại, giờ mở cửa, nội quy, chỗ gửi xe…), lễ tân tìm trong kho tri thức rồi mới trả lời, và chỉ trả lời theo những đoạn tìm được. Kho này là hai bảng `vh_knowledge_documents` (tài liệu) và `vh_knowledge_chunks` (từng đoạn của tài liệu, kèm từ khóa và vector để tìm theo nghĩa). Vector nằm ngay trong PostgreSQL của gói, ở cột `embedding` kiểu `vector(1536)` của **pgvector**; không có database vector riêng. Đây là kho riêng cho việc tìm kiếm, khác với `handbook`, `policies`, `announcements` ở mục 2.

**Tệp đi kèm.** Gói có sẵn `src/vinhomes_api/schema/knowledge/ocean-park-1.jsonl.gz` (khoảng 3 MB): 164 tài liệu, 648 đoạn của Vinhomes Ocean Park 1, đã có vector. Trong đó 115 tài liệu cho cư dân (12 cho cả khu, 59 theo phân khu, 44 theo tòa) và 49 tài liệu nội bộ cho nhân viên (quy trình, tài liệu tham khảo của Ban quản lý). 21 tài liệu cư dân được đánh dấu **chưa xác minh**; trợ lý phải nói rõ điều đó khi dùng.

**Nạp.**

```
python -m vinhomes_api.knowledge load                         # tệp đi kèm, vào khu mẫu
python -m vinhomes_api.knowledge load --file F --tenant T     # tệp khác, khu khác
```

Lệnh đọc `DATABASE_URL` (vai trò chủ sở hữu), chạy sau `migrate` và `seed`, và in một dòng, ví dụ `documents=164 chunks=648 embedded=0 skipped=0 changed=812`. Chạy lại cùng tệp không ghi gì (`changed=0`). Sửa nội dung một đoạn rồi nạp lại thì chỉ đoạn đó được ghi; đoạn không còn trong tài liệu thì bị xóa; tài liệu không có trong tệp thì giữ nguyên.

**Ai thấy gì.** Mỗi tài liệu ghi rõ dành cho ai (`resident` hoặc `staff`) và cho nơi nào: cả khu, một phân khu, hoặc một vài tòa trong phân khu. Cư dân chỉ nhận tài liệu cho cư dân của cả khu, của phân khu mình ở và của tòa mình ở. Người có nhà ở hai phân khu chỉ nhận tài liệu của cả khu, cho tới khi cuộc trò chuyện đó có một yêu cầu gắn với một căn; từ đó nhận thêm tài liệu của phân khu và tòa của căn ấy. Tài liệu ghi một phân khu hay tòa **không có trong database** thì bị bỏ qua và in ra dòng `SKIPPED …` (không bao giờ tự nới thành "cả khu"); nạp tòa, phân khu trước rồi nạp lại.

**Thêm tài liệu thật sau này.** Viết một tệp cùng dạng rồi nạp bằng `--file`. Tệp là JSON nén gzip, mỗi dòng một tài liệu:

```
{"id": "<uuid>", "version_id": "<uuid>", "code": "sapphire/noi-quy.md", "title": "Nội quy Sapphire",
 "category": "resident-care", "audience": "resident", "site": "ocean-park-1", "zone": "sapphire", "buildings": ["S1.01"],
 "unverified": false, "metadata": {},
 "chunks": [{"id": "<uuid>", "ordinal": 0, "heading_path": "Nội quy Sapphire > Giờ yên tĩnh", "text": "…", "token_count": 120}]}
```

- `id` của tài liệu và của từng đoạn do người soạn đặt và **giữ nguyên qua các lần nạp**: câu trả lời của trợ lý dẫn nguồn bằng các mã này. Đổi nội dung thì đổi `version_id`. Mã là duy nhất trong cả database: một tệp đã nạp cho khu này thì không nạp lại được cho khu khác (lệnh dừng và không ghi gì); bản của khu khác phải mang mã riêng.
- `zone` để `null` và `buildings` để `[]` là cả khu; chỉ có `zone` là cả phân khu; có `buildings` thì chỉ các tòa đó (phải thuộc `zone`).
- Đoạn không có `embedding` vẫn nạp được và vẫn tìm được theo từ (có dấu hay không dấu đều được). Nếu đặt `VINHOMES_API_EMBEDDING_API_KEY` khi nạp, lệnh tự tạo vector cho các đoạn còn thiếu (`embedded=…`), nhờ đó tìm được cả theo nghĩa.
- Nên cắt mỗi đoạn khoảng 100 đến 400 từ, mỗi đoạn một ý, `heading_path` là đường dẫn tiêu đề tới đoạn đó.

**Khi chạy.** API tìm ở `POST /internal/knowledge/search` (lễ tân gọi; đặt `RECEPTION_KNOWLEDGE_URL` trỏ về API). Agent điều phối của platform tìm qua công cụ `vh_knowledge_search`, dùng cùng một hàm tìm và cùng kho này. Mỗi lần tìm là một câu SQL: lọc theo khu, theo người đọc (cư dân hay nhân viên) và theo nơi ở trước, rồi chấm điểm **mọi** đoạn còn lại bằng khoảng cách cosine của pgvector (toán tử `<=>`) trộn với điểm trùng từ (0,8 nghĩa và 0,2 từ), và trả về các đoạn điểm cao nhất. Đã đo với tệp đi kèm: một cư dân tòa S1.01 có 76 đoạn trong phạm vi, câu SQL mất khoảng 15 mili giây; phần lớn thời gian của một lần tìm là gọi nhà cung cấp để tạo vector cho câu hỏi (khoảng 0,6 giây). Có `VINHOMES_API_EMBEDDING_API_KEY` (khóa OpenAI) thì câu hỏi được so theo nghĩa; không có khóa hoặc nhà cung cấp lỗi thì API vẫn trả lời bằng cách so từ. Câu hỏi không liên quan ("giá vàng hôm nay") nhận về "không đủ nguồn" và trợ lý nói là chưa có thông tin, không đoán. Kiểm chứng: `tests/test_knowledge.py`.

**Vì sao không tìm qua chỉ mục gần đúng.** Bảng có chỉ mục HNSW của pgvector (`vh_knowledge_chunks_embedding_idx`), nhưng câu tìm ở trên không đi qua nó mà so chính xác từng đoạn trong phạm vi. Lý do đã đo trên 99 lượt hỏi thật: đi qua chỉ mục rồi mới lọc theo nơi ở thì 62 lượt trả về ít hơn 5 đoạn (có lượt không trả về đoạn nào) và chỉ tìm lại được 261 trên 495 đoạn đúng; bật chế độ quét lặp của pgvector thì đủ 5 đoạn nhưng vẫn chỉ đúng 428 trên 495. Với vài trăm đoạn, so chính xác vừa đúng vừa nhanh như nhau. Khi kho lớn tới hàng chục nghìn đoạn mới cần đổi sang lấy ứng viên qua chỉ mục.

**PostgreSQL ở nơi khác.** `migrate` chạy `create extension if not exists vector`. Trong gói, vai trò chủ database là superuser nên tự tạo được. Với PostgreSQL có sẵn ở nơi khác, người quản trị ở đó phải cài pgvector và chạy `create extension vector` trong database này **trước** khi `migrate` (dịch vụ PostgreSQL thuê ngoài gọi extension này là `vector`); thiếu thì `migrate` dừng ở `0013_knowledge.sql` và không ghi gì của tệp đó.

Tệp đi kèm được xuất một lần từ kho tri thức cũ bằng `scripts/export_legacy_knowledge.py` (chỉ đọc kho cũ). Văn bản các đoạn giữ nguyên, mã tài liệu và mã đoạn giữ nguyên; vector được tạo lại bằng mô hình `text-embedding-3-large` (1536 chiều) vì không dựng lại được đúng đầu vào mà kho cũ đã dùng.

## Đồng bộ theo lịch

Dùng khi một hệ thống khác (hoặc người vận hành) xuất dữ liệu ra tệp đều đặn. Lệnh `python -m vinhomes_api.database sync --dir <thư mục> --every <giây>` (trong gói Docker là dịch vụ `data-sync`, bật bằng `--profile sync`) làm đúng việc của `import` mỗi khi các tệp trong thư mục thay đổi.

- **Tệp:** cùng tên và cùng cột như mục nạp một lần ở trên.
- **Tệp `READY`:** bên xuất dữ liệu ghi các tệp trước, rồi tạo tệp rỗng tên `READY` sau cùng. Chưa có `READY` thì không tệp nào được đọc, nên một lần xuất đang ghi dở không bao giờ bị nạp. Lần xuất sau chỉ cần ghi đè các tệp.
- **Không đổi thì không làm gì:** mỗi lượt chỉ tính mã băm các tệp; giống lần trước thì không ghi gì vào database.
- **Tệp lỗi:** cả lượt bị từ chối, không dòng nào được ghi, nhật ký nêu tệp và dòng. Bộ tệp đó không được thử lại cho tới khi nội dung thay đổi.
- **Dòng mới:** được thêm. **Dòng đã có:** giữ nguyên như lệnh `import` (không ghi đè tên, số điện thoại đã có).
- **Cư dân không còn trong `residents`:** người từng có trong lần nạp trước mà lần này vắng thì thôi là cư dân của căn đó từ lúc ấy (quan hệ với căn được ghi ngày kết thúc). Tài khoản, yêu cầu và hộp chat cũ của họ còn nguyên. Có lại trong tệp thì là cư dân trở lại. Việc này chỉ áp dụng cho những dòng do chính bộ đồng bộ nạp, không đụng tới cư dân đăng ký trong ứng dụng.
- **Xem lượt gần nhất:** tệp `.sync-state.json` trong thư mục (thời điểm, đạt hay không, lỗi nếu có) và `docker compose logs data-sync`.

Bộ đồng bộ không gọi hệ thống nào ở ngoài. Nối với hệ thống quản lý cư dân thật nghĩa là viết thêm bước lấy dữ liệu từ hệ thống đó ra các tệp này.
