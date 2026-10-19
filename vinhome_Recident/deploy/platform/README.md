# Nối Vinhomes với platform AI (Workforce v1)

Thư mục này là **thứ Vinhomes giao cho nhóm vận hành platform**. Thiết kế đã duyệt ở [docs/domain/NOI_WORKFORCE_V1.md](../../docs/domain/NOI_WORKFORCE_V1.md). Vinhomes chỉ là một đối tác của platform: không sửa gì bên platform, chỉ gọi API công khai của nó.

| Tệp | Là gì |
|---|---|
| `vinhomes-declaration.json` | Mọi thứ platform phải cấu hình cho Vinhomes, đúng dạng API quản trị của platform nhận. |
| `apply.py` | Đưa bộ khai báo đó vào một platform qua API quản trị. Tiện ích cho người vận hành platform; làm tay bằng `curl` theo hướng dẫn của platform cũng được. |
| `platform.env` | Do `apply.py` ghi ra: các khóa platform chỉ hiện **một lần**. Không commit. |
| `.applied.json` | Do `apply.py` ghi ra: id của những gì đã tạo (không có bí mật), để chạy lại không tạo trùng. Không commit. |

## Ai làm gì, theo thứ tự

**1. Vinhomes** tạo `deploy/deployment.env` như thường lệ (`deploy/new-env.ps1` hoặc `new-env.sh`). Lệnh này sinh luôn `VINHOMES_API_PLATFORM_MCP_TOKEN`. Gửi cho người vận hành platform, qua kênh an toàn:

- token đó;
- địa chỉ MCP của Vinhomes **như platform nhìn thấy**, ví dụ `https://vinhomes.example.com/mcp` (API của Vinhomes phục vụ đường `/mcp`);
- mã các Ban quản lý (`management_units.code`), mỗi mã thành một route. Xem bằng:

```powershell
dc exec postgres psql -U vinhomes_owner vinhomes -c "select code, name from management_units"
```

(`dc` là `docker compose --env-file deploy/deployment.env -f deploy/compose.yml`.)

MCP có thể onboarding trước khi Vinhomes gọi API platform: chỉ cần đặt token riêng `VINHOMES_API_PLATFORM_MCP_TOKEN` (tối thiểu 32 ký tự), giữ `VINHOMES_API_PLATFORM_URL` trống. API và gateway phục vụ `/mcp`, cho phép `initialize` và `tools/list` sau xác thực Bearer. Token rỗng thì endpoint API tắt; sai hoặc thiếu token thì trả 401. Công cụ nghiệp vụ vẫn yêu cầu `ticket_id` có link bàn giao hợp lệ, không cấp quyền truy cập chỉ bằng một ID tùy ý. Dùng HTTPS hoặc tunnel SSH/VPN khi truyền token; key này không phải customer/provider key do platform cấp ở bước sau.

**2. Người vận hành platform** chạy `apply.py` (cần Python 3.11 trở lên và gói `httpx`). Khóa quản trị và token đưa qua biến môi trường, không gõ trên dòng lệnh:

```powershell
$env:AWP_ADMIN_KEY = '...'          # một khóa trong AWP_ADMIN_KEYS của platform
$env:VINHOMES_MCP_TOKEN = '...'     # token Vinhomes gửi ở bước 1
python deploy/platform/apply.py --platform http://127.0.0.1:8800 --admin-key-env AWP_ADMIN_KEY `
  --mcp-url https://vinhomes.example.com/mcp --mcp-token-env VINHOMES_MCP_TOKEN `
  --management-refs local-management --environment sandbox
```

Lệnh tạo và công bố hồ sơ agent, tạo client, khóa khách hàng, bộ sự kiện kèm khóa nhà cung cấp và khóa ký, mỗi Ban quản lý một route ở trạng thái `pending`, rồi ghi máy chủ MCP và bảng công cụ cho từng route. Màn hình chỉ in id, số phiên bản và lệnh xác nhận route; các khóa nằm trong `deploy/platform/platform.env`. Gửi tệp đó cho Vinhomes qua kênh an toàn, cùng lệnh xác nhận route đã in.

Chạy lại lệnh là an toàn: không tạo client, khóa, route thứ hai; chỉ ghi lại máy chủ MCP và bảng công cụ (cũng là cách để platform đọc lại danh sách công cụ ngay khi Vinhomes đổi công cụ, thay vì chờ 5 phút).

**3. Vinhomes** dán các dòng của `platform.env` vào `deploy/deployment.env`. Riêng `VINHOMES_API_PLATFORM_URL` phải là địa chỉ platform **nhìn từ trong container của Vinhomes** (platform chạy trên cùng máy: `http://host.docker.internal:<cổng>`). Rồi khởi động lại và xác nhận route bằng khóa khách hàng (chép lệnh `apply.py` đã in):

```powershell
dc up -d --build api platform-sync
dc exec platform-sync python -m vinhomes_api.platform confirm-routes --route local-management=route_...:1
```

Route chưa xác nhận thì platform từ chối mọi yêu cầu của Ban quản lý đó (403 `ROUTE_NOT_AUTHORIZED`).

Kiểm tra nhanh: `dc exec platform-sync python -m vinhomes_api.platform status` cho biết cầu nối bật hay tắt, hai khóa có được platform nhận không, và số link, lệnh, sự kiện đang chờ theo trạng thái.

Địa chỉ MCP đưa cho platform là `/mcp` của API hoặc gateway (`…/mcp`). `/api/business/mcp` vẫn trả 404; giao diện web không dùng token này.

## Bảng bàn giao

| Hạng mục | Giá trị | Ở đâu |
|---|---|---|
| Client | tên `Vinhomes`, domain `vinhomes`, môi trường `sandbox` hoặc `production` (hai môi trường là hai client, khóa không dùng chéo) | `client` |
| Khóa khách hàng | đủ 8 quyền: gửi yêu cầu, trả lời, đọc kết quả, nhận sự kiện, gửi đồng ý, đóng workflow, xác nhận route, đồng bộ cư trú; phủ mọi route | `customer_key` → `VINHOMES_API_PLATFORM_CUSTOMER_KEY` |
| Khóa nhà cung cấp và khóa ký | gửi sự kiện tiến độ có chữ ký HMAC-SHA256, đọc biên nhận | `provider_key` → `…_PROVIDER_KEY`, `…_SIGNING_KEY_ID`, `…_SIGNING_SECRET` |
| Token MCP | Vinhomes sinh; platform gửi lại trong `Authorization: Bearer …` mỗi lần gọi công cụ; platform cất kín, không trả ra | `VINHOMES_API_PLATFORM_MCP_TOKEN` |
| Định danh | `external_management_ref` = mã Ban quản lý; `external_user_id` = id người dùng; `external_ticket_id` = id ticket; `external_conversation_id` = `<id hộp chat>:<id ticket>`; múi giờ `Asia/Ho_Chi_Minh` | mục 3 của thiết kế |
| Route | mỗi Ban quản lý một route; bắt buộc gắn ticket; không đòi `residence_id`; một lần gửi chờ tối đa 25 giây; trả lời chỉ tra cứu **không** tự đóng workflow (Vinhomes đóng sau khi cư dân xác nhận) | `route.config` |
| Quy tắc lời nói | câu trả lời an toàn; 4 nhóm cụm từ cấm: hứa khoảng thời gian, cam kết thay Ban quản lý, nói "miễn phí" khi tài liệu không ghi, hứa bồi thường hay hoàn tiền. Các quy tắc này thêm vào luật có sẵn của platform (không nói "đã xong" khi chưa có kết quả xác minh, không nói "đã đóng yêu cầu") | `route.config.rules` |
| Hồ sơ agent | một leader `vh_dieu_phoi`, được dùng mọi công cụ `vh_*`, mức model `standard` | `profiles` |
| Máy chủ MCP | tên `vinhomes`, streamable HTTP, không trạng thái; địa chỉ và token là tham số của `apply.py` | `mcp_server` |
| Công cụ | 3 tra cứu, 4 hành động (bảng dưới) | `tools` |
| Sự kiện tiến độ | 15 loại, kiểu phiên bản `snapshot` (bảng dưới) | `integration.event_schema` |

Chỉ có một leader, không có chuyên viên: mỗi ticket là một việc điều phối, leader tự gọi công cụ. Platform không cần thêm hồ sơ nào cho luồng này.

### Công cụ

MCP discovery hiện công bố 16 tool. Declaration trong thư mục này chủ động chỉ cấp 7 tool điều phối cơ bản bên dưới, không tự mở quyền Travel hoặc ngữ cảnh dịch vụ trên route đang chạy. Hai tool ngữ cảnh/availability và 7 tool Travel cần cấu hình quyền riêng đúng nghiệp vụ; xem [Travel contract](../../docs/domain/TRAVEL_MOCK_PLATFORM_CONTRACT_20261014.md). Không coi số lượng discovery là số quyền của một ticket.

Chỉ xử lý ticket đã bàn giao. Identity/căn hộ có sẵn; Reception giữ tiếp nhận/dịch vụ cư dân. Platform quản lý session và ngoại lệ, không có bước BQL duyệt yêu cầu ở domain. Xem [MCP_PLATFORM_V2.md](../../docs/domain/MCP_PLATFORM_V2.md): backend platform dùng control-plane token để tự lấy grant theo ticket/workflow, gắn vào transport riêng, refresh catalog/grants và parser v2. Không tự áp declaration vào platform chưa xác nhận adapter.

Mọi công cụ nhận ticket_id từ bàn giao và phải dùng grant đúng ticket/workflow/tool còn hiệu lực. Backend cấp client_reference; lệnh mới có expected_ticket_version, hủy/đổi lịch có nguồn lời cư dân. Bootstrap token chỉ discovery/control-plane. Các thẻ đồng ý báo giá/xác nhận hoàn thành vẫn do cư dân tự bấm tại domain; requires_consent:false không bỏ qua quyền này. Tool timeout7s, declaration timeout8s; retry giữ reference/nội dung.

| Công cụ | Loại | Theo dõi |
|---|---|---|
| `vh_ticket_get`, `vh_knowledge_search`, `vh_staff_available` | tra cứu, chỉ đọc | |
| `vh_work_order_dispatch` | hành động | `events`: trả `pending` kèm `external_job_id`, tiến độ về bằng sự kiện |
| `vh_work_order_reschedule`, `vh_ticket_cancel`, `vh_ticket_add_note` | hành động | không: trả confirmed hoặc failed ngay |

Không có công cụ nào ghi câu trả lời báo giá. Báo giá hiện thành một thẻ trong hộp chat do chính Vinhomes ghi; cư dân tự bấm Đồng ý hoặc Không đồng ý trên thẻ. Leader chỉ giải thích khi cư dân hỏi.

### Sự kiện tiến độ

Mọi sự kiện mang `client_reference` của lần giao việc. "Tin mẫu" là câu platform gửi thẳng cho cư dân, không qua model; trường nằm trong tin mẫu là **bắt buộc** (thiếu thì platform từ chối sự kiện, 422). "Đánh thức" là leader được gọi dậy để xử lý.

| Sự kiện | Hạng | Trường | Tin mẫu | Cờ |
|---|---|---|---|---|
| `job.offered`, `job.declined`, `job.offer_expired` | 10 | | | |
| `job.unassigned` | 10 | | | đánh thức |
| `job.accepted` | 20 | `staff_name`, `eta` | Nhân viên {staff_name} đã nhận yêu cầu của bạn, dự kiến đến lúc {eta}. | |
| `job.rescheduled` | 20 | `appointment` | Lịch hẹn của bạn đã được đổi sang {appointment}. | |
| `job.en_route` | 30 | `staff_name` | Nhân viên {staff_name} đang trên đường đến nhà bạn. | |
| `job.arrived` | 40 | `staff_name` | Nhân viên {staff_name} đã đến nơi. | |
| `job.quote_ready` | 50 | `items`, `total` (số nguyên), `warranty_months` (số nguyên) | | bằng chứng |
| `job.quote_approved` | 50 | | Đã ghi nhận bạn đồng ý với báo giá. | bằng chứng |
| `job.quote_rejected` | 50 | | Đã ghi nhận bạn không đồng ý với báo giá. | đánh thức |
| `job.started` | 60 | | Nhân viên đã bắt đầu làm việc. | |
| `job.completed` | 70 | | Nhân viên báo đã làm xong phần việc và sẽ gửi kết quả nghiệm thu để bạn xem. | |
| `job.result_published` | 90 | `summary`, `photo_count` (số ảnh của nhân viên mà cư dân xem được: trước, sau, nghiệm thu), `reported_by` | | kết thúc `completed`, đánh thức, bằng chứng |
| `job.cancelled` | 90 | `reason` | | kết thúc `cancelled`, đánh thức |

`items` là danh sách `{label, amount}`, `total` bằng tổng các `amount`. `job.quote_ready` không đánh thức leader và không có tin mẫu: cư dân đã có thẻ báo giá; sự kiện chỉ để leader có số liệu khi cư dân hỏi. Cư dân trả lời báo giá thành hai loại sự kiện vì tin mẫu của platform không rẽ nhánh được; chỉ lần từ chối đánh thức leader. `job.result_published` là kết quả nghiệm thu do nhân viên gửi (`reported_by` là tên nhân viên, hoặc "Ban quản lý" khi Ban quản lý tự nghiệm thu); cư dân xác nhận sau đó, trên chat. `photo_count` là số ảnh kết quả (ảnh sau và ảnh nghiệm thu). Vinhomes tự ghi một tin nêu kết quả vào hộp chat; leader chỉ cần mời cư dân xác nhận. Giờ (`eta`, `appointment`) là chữ dạng `HH:MM dd/MM/yyyy`, giờ Việt Nam. `job.completed` mang trạng thái `work_done` chứ không phải `completed`: việc chỉ được coi là xong khi có `job.result_published`.

Platform bỏ qua sự kiện có hạng thấp hơn hạng đã nhận của cùng lần giao việc (biên nhận ghi `STALE_EVENT`). Ví dụ: đổi lịch sau khi nhân viên đã lên đường thì cư dân không nhận tin mẫu đổi lịch.

## Kiểm tra đã nối được

1. Phía platform, bằng khóa quản trị: `GET /platform/v1/wf/routes?client_id=<client>` cho route active; `GET /platform/v1/wf/routes/<route>/tools` đúng 7 công cụ; integration giữ 15 loại sự kiện và một khóa ký active. Trước khi bật route, phải nghiệm thu adapter control-plane → grant theo workflow; đây là yêu cầu chuyển đổi v2, không phải bằng chứng platform draft đã hỗ trợ sẵn.
2. Phía Vinhomes: `dc logs platform-sync` không có lỗi xác thực. Đăng nhập một cư dân mẫu, nhắn một yêu cầu sửa chữa đủ thông tin: Lễ tân tạo ticket, vài giây sau trong hộp chat có lời của agent điều phối, và nhân viên đúng chuyên môn thấy lời mời việc trong app nhân viên.
3. Khi có trục trặc, người vận hành platform xem `GET /platform/v1/wf/workflows?client_id=<client>` (trạng thái, `attention_reason`), `GET /platform/v1/wf/operations?workflow_id=<workflow>` (từng lời gọi công cụ: `client_reference`, `external_job_id`, lỗi) và `GET /platform/v1/wf/receipts?integration_id=<integration>` (từng sự kiện tiến độ). Workflow ở `needs_attention` thì `POST /platform/v1/wf/workflows/<workflow>/resolve` với `{"action": "resume"}` hoặc `{"action": "close"}`.

Lỗi hay gặp: platform từ chối địa chỉ MCP nội bộ (`localhost`, `host.docker.internal`, tên dịch vụ docker, IP riêng) trừ khi nó chạy với `AWP_MCP_ALLOW_PRIVATE=1`; công cụ không tới agent nếu hồ sơ thiếu `vh_*` trong `tools_allow`; tên hồ sơ (`profiles[].name`) có khoảng trắng thì mọi lượt của agent hỏng (model từ chối tên đó, workflow sang `needs_attention`), nên tên viết liền, không dấu cách.

Lời dặn leader nằm ở ba chỗ của bộ khai báo: `profiles[].instructions`, `route.config.rules` và `description_override` của hai công cụ `vh_ticket_get`, `vh_work_order_dispatch` (thay mô tả công cụ mà máy chủ MCP đưa ra). Sửa xong chạy lại `apply.py`. Hồ sơ đổi thì workflow mới dùng phiên bản mới, workflow đang mở giữ phiên bản nó bắt đầu.

## Đổi khóa

- **Khóa khách hàng, khóa nhà cung cấp, khóa ký:** người vận hành platform chạy lại đúng lệnh ở bước 2 thêm `--new-keys`. Lệnh cấp khóa mới, thu hồi khóa cũ **ngay** và ghi lại `platform.env`. Vinhomes dán các dòng mới vào `deployment.env` rồi `dc up -d api platform-sync`. Làm hai việc liền nhau, vào lúc vắng: trong khoảng giữa, platform từ chối khóa cũ nên lệnh và sự kiện Vinhomes gửi đi bị hỏng.
- **Token MCP:** Vinhomes sinh giá trị mới (32 ký tự trở lên), sửa `VINHOMES_API_PLATFORM_MCP_TOKEN` trong `deployment.env`, `dc up -d api platform-sync`, gửi token cho người vận hành platform; người đó chạy lại lệnh ở bước 2 với token mới (không cần `--new-keys`).
- **Mất `platform.env` trước khi dán:** platform không cho xem lại khóa. Chạy lại với `--new-keys`.

## Đổi cấu hình về sau

- **Hồ sơ agent:** sửa `profiles` trong bộ khai báo rồi chạy lại `apply.py`; lệnh công bố một phiên bản mới.
- **Công cụ, địa chỉ MCP:** sửa rồi chạy lại `apply.py`.
- **Thêm Ban quản lý:** chạy lại với `--management-refs` có thêm mã mới, rồi xác nhận route mới.
- **Quy tắc của route** (câu an toàn, cụm từ cấm, thời gian chờ): platform chỉ đổi được bằng cách thay route (`POST /platform/v1/wf/routes/<route>/replace`), việc này chặn các workflow đang mở của route cũ. `apply.py` không tự làm; nó chỉ cảnh báo khi route đang lưu khác bộ khai báo.
- **Bảng sự kiện:** platform không sửa được bảng đã lưu. `apply.py` dừng và nêu cách tạo một integration mới (kèm khóa nhà cung cấp và khóa ký mới). Sau đó Vinhomes phải dán ba dòng khóa mới của `platform.env` vào `deployment.env` rồi `dc up -d api platform-sync`; chưa làm thì sự kiện tiến độ gửi bằng khóa cũ không khớp với việc mới giao.
- **Platform khác hoặc môi trường khác:** cất `.applied.json` và `platform.env` đi nơi khác rồi chạy lại.

## Ngoài phạm vi

- Ảnh không đi qua platform (platform chỉ nhận chữ): ảnh ở kho của Vinhomes, platform chỉ biết số ảnh.
- Đồng bộ danh sách căn hộ (`residences`), luồng SSE, khóa riêng cho từng Ban quản lý, thanh toán.
- Xử lý khẩn cấp tại chỗ (leo thang, báo Ban quản lý, điều bảo vệ) vẫn là của Vinhomes. Ticket khẩn cấp có gửi sang platform kèm mức khẩn cấp Lễ tân đánh giá, để leader nói cư dân cần làm gì và giao việc ngay; việc an ninh thì leader chỉ báo tin, không giao.
- Chạy platform (database, model, sao lưu) là việc của nhóm platform; `apply.py` chỉ gọi API quản trị công khai của nó.
