# Tiến độ B1–B6: code, kiểm chứng và việc còn lại

Đối chiếu ngày 04/10/2026, nhánh `dev_teamChien_HuyDo`, HEAD `2288bed`. Các thay đổi được mô tả bên dưới đang ở working tree, chưa commit/push. Đây là bằng chứng chạy local với PostgreSQL và tài khoản đăng nhập thật, chưa phải nghiệm thu production. CI giữ tắt theo quyết định đã chốt.

## Kết quả hiện tại

| Mục | Đã triển khai | Bằng chứng và giới hạn |
| --- | --- | --- |
| B1: tool kỹ thuật | Gateway kiểm run, release đã ghim, grant đọc và coverage; lưu audit. Ba tool đọc của Quang đã nối. | Thiếu SOP/gián đoạn đủ phiên bản, hiệu lực, scope/ACL. Tool có thể trả rỗng đúng dữ liệu; không phải gateway chưa mở. [Bộ bàn giao cần yêu cầu](TEAM_QUANG_DATA_HANDOFF_2026-10-04.md). Tool ghi/tạo yêu cầu chưa mở. |
| B2: Supervisor và chat trong OpenBot | Nhóm BQL, các phiên theo ticket, hỏi agent trong phiên, phòng chung `@agent`, nút tạm dừng/chạy tiếp/dừng. API lệnh có version, idempotency và trạng thái chờ runtime xác nhận. | Chat phòng chung đã trả lời bằng model thật, gồm tool báo cáo và an ninh. Gõ tên agent tự do đã được kiểm chứng. Nút điều khiển có implementation/test; còn kiểm chứng đủ ba nút qua UI trên phiên thử. |
| B3: BQL custom agent/Factory | Tạo nháp, sửa chỉ dẫn, chọn danh mục/tool đọc, Factory tạo và backend xác minh artifact, đánh giá model thật, BQL phát hành/từ chối/thu hồi. Bản phát hành bất biến; phiên cũ giữ version đã ghim. Admin có API/màn review, quản lý tài khoản và quyền ghi đè. | Factory → 6 ca model thật → BQL phát hành qua UI đã đạt. Agent an ninh cấu hình thủ công → 6 ca → phát hành UI cũng đạt. Còn kiểm chứng vòng v1→v2, từ chối/thu hồi qua UI; UI admin cấp scope BQL chi tiết cần hoàn thiện. Không dùng kết quả đánh giá do trình duyệt tự khai để BQL phát hành. |
| B4: phương án và hai lần duyệt | Supervisor lập phương án, nhận quyết định BQL qua inbox, hỏi cư dân; cư dân bổ sung/đồng ý/từ chối/yêu cầu sửa bằng UI; tạo công việc sau hai lần duyệt. | Ticket thử `VH-8648E61BD489`: hỏi giờ có mặt → cư dân trả lời → phương án v1 → BQL từ chối → v2 → BQL duyệt → cư dân yêu cầu sau 18 giờ → v3 giữ đúng lịch mới → BQL duyệt → cư dân đồng ý → đúng 1 work order `queued`. Còn kiểm chứng cư dân từ chối bằng model thật và luồng tiếp nhận ban đầu hoàn toàn qua Reception UI. |
| B5: an ninh | Hai tool `security.camera.read`, `security.contact.read` qua gateway; agent phát hành được lọc theo danh mục để Supervisor mời. | Chat UI gọi thật cả hai tool, mỗi call audit `OK`; dữ liệu tại tòa thử hiện rỗng và agent nói rõ. Chưa chạy ticket an ninh trọn phiên Supervisor với model thật. Không có API camera/kiểm soát ra vào; không chứng minh thiết bị hoạt động. |
| B6: báo cáo | Facade báo cáo qua gateway và dữ liệu PostgreSQL; quyền workspace/actor/building, tool đọc và audit. | Agent chat UI gọi báo cáo tần suất sự cố trong Sapphire; truy vấn tòa ngoài workspace bị từ chối. Chưa nghiệm thu toàn bộ loại báo cáo, đối soát số liệu và export/action có duyệt. |

## Kiểm chứng đã chạy

- Lượt chạy lại toàn bộ trước smoke Docker: `agent-coordination` **443 passed** (một kỳ vọng test cũ về tên tool đã sửa theo tên catalogue), backend PostgreSQL **70 passed, 6 skipped**, Factory **44 passed**, typecheck app/resident/server sạch, schema check đạt, build app đạt.
- Toàn bộ bộ kiểm thử `agent-coordination`: **442 passed** trước lần sửa tên tool cuối. Sau sửa đã chạy lại nhóm BQL/runtime + PostgreSQL: **5 passed**, gồm kiểm tên tool nhiều đoạn, replay không gọi lại model và PostgreSQL CAS/fencing/quota.
- API coordination trên PostgreSQL đã migrate/seed: **12 passed** sau sửa, gồm cư dân đồng ý/từ chối/yêu cầu sửa, idempotency, quyền tool và thu hồi giữa lượt chạy.
- Factory: **44 passed** ở lượt kiểm tra trước; đã có lượt tạo bằng `gpt-5.5` thật qua UI.
- Typecheck OpenBot app và Resident app đạt ở lượt cuối. `git diff --check` đạt. Build app, typecheck server và schema check đã có lượt đạt trước đó; cần chạy lại các check áp dụng cho bản cuối trước commit.
- Checkpoint Supervisor đã chuyển sang database PostgreSQL riêng trên cùng cluster. Restart runtime vẫn đọc ticket thử ở `execution_ready`, checkpoint version **66**, cùng run, không có action đang bay. Hai kiểm thử PostgreSQL riêng cũng đã đạt.
- Playwright desktop/mobile không có page error trong các lượt đã đạt. Đã xem ảnh phòng BQL mobile và chi tiết cư dân; sửa dòng mô tả dữ liệu local sai khi đang dùng backend thật.

Bộ ca đánh giá agent có model thật nhưng tool trong đánh giá dùng fixture không tác động. Các lượt chat báo cáo/an ninh kể trên gọi gateway và PostgreSQL thật, được kiểm riêng. Không cộng các bộ test chồng lặp thành một tổng.

Ticket B4 được chuẩn bị bằng operation API có đăng nhập và một tin nhắn cư dân được đánh dấu fixture trong database local. Từ câu hỏi Supervisor, phản hồi cư dân, sửa/duyệt phương án đến tạo work order đều dùng UI/model thật. Không gọi đây là luồng Reception UI từ đầu đến cuối; công việc chưa được phân công, thi công, QC hay đóng ticket.

Bằng chứng máy local nằm trong `.codex-artifacts/` (được ignore): `bql-agent-ui-evidence.json`, `bql-room-ui-evidence.json`, `bql-plan-ui-evidence.json`, `bql-security-ui-evidence.json`, `bql-runtime-acceptance.json` và ảnh UI. Bằng chứng giữ cả lượt thất bại và lượt sửa đạt; không chứa khóa provider/tài khoản trong báo cáo.

## Kiểm chứng bổ sung trên giao diện (04/10, tối)

Chạy bằng Playwright với tài khoản thật và model thật trên stack local, sau commit `4ded116`:

- **Ba nút điều khiển phiên (B2):** tạm dừng → Supervisor xác nhận `management_pause`, nút đổi thành "Chạy tiếp";
  chạy tiếp → phiên về đúng `waiting_management`; dừng phiên → hỏi xác nhận trước, sau đó phiên `cancelled` và
  không còn nút. 6/6 bước.
- **Vòng phiên bản agent (B3):** tạo nháp → 6 ca → phát hành bản 1 → sửa và bị từ chối (bản 1 vẫn chạy) → sửa và
  phát hành bản 2 → phòng nhóm trả lời bằng bản 2 → thu hồi, agent biến khỏi ô `@Nhắc agent`. 15/15 bước.
- **Tiếp nhận từ giao diện Lễ tân và cư dân từ chối (B4):** cư dân gửi yêu cầu trong chat của ứng dụng cư dân → ticket
  → phương án → BQL duyệt → cư dân bấm "Từ chối phương án". Lần đầu lộ lỗi: Supervisor lập lại gần đúng phương án
  cũ. Đã sửa hướng dẫn lập phương án (`e454d32`): nay phiên dừng với lý do của cư dân để BQL quyết định; "Yêu cầu sửa
  phương án" vẫn cho phương án mới theo ý cư dân. 7/7 bước cho mỗi nhánh.
- **Ticket an ninh trọn phiên (B5):** Lễ tân phân loại an ninh, Supervisor mời agent an ninh, hai tool trả `OK` với
  dữ liệu rỗng và agent nói rõ, hai lần duyệt, đúng 1 phiếu thi công. 7/7 bước.
- **Tool kỹ thuật (B1):** cổng tool báo `INTERNAL_ERROR` cho agent mỗi khi tool host trả "không có SOP hiệu lực" (HTTP
  404). Đã sửa (`2093608`): agent nhận đúng `NOT_FOUND` kèm thông báo của tool host; có test.
- **Triển khai:** compose thêm Operations, ứng dụng cư dân và job `upgrade`; luồng hai lần duyệt đã chạy qua hai giao
  diện trong container.

Chưa làm trong đợt này: admin ghi đè và màn admin cấp phạm vi BQL; đối soát các loại báo cáo còn lại (B6); phân công,
thi công, QC và đóng ticket sau khi có phiếu thi công; dữ liệu team Quang.

Sau đợt này nhánh đã merge `develop` (`a01ae3a`: Agent Factory của Team Phái và tool báo cáo của Team Hoàng), PR #31
hết xung đột. Ghi nhận từ lần merge:

- `jose` được ghim `6.2.10` trong `server/package.json`. Với `^6.2.12` như trên `develop`, server không qua typecheck
  (`src/auth/index.ts`) vì cài thêm một bản `@better-auth/core`.
- Nguồn của `_vendor/reporting` trong API là `server/src/reporting` của Team Hoàng. Bản vendor là bản cũ hơn: 5 file
  khác bản trên `develop` (`application/client.py`, `metrics/normalize.py`, `tools/catalog.py`, `tools/contracts.py`,
  `tools/facade.py`). Cần đồng bộ lại trước khi đối soát báo cáo B6.
- Test server cần cơ sở dữ liệu (`TEST_DATABASE_URL`) chưa chạy lại sau merge; các test kỹ thuật, tri thức, Factory,
  giao diện và typecheck đã chạy lại và đạt.

## Luồng trọn vẹn và phần quản trị (04/10, đêm; chạy local)

Chạy bằng trình duyệt với ba tài khoản thật (cư dân, BQL, kỹ thuật viên) và model thật, không dùng Docker:

- **Một yêu cầu đi hết vòng đời:** cư dân gửi trong chat → Lễ tân tạo ticket → Supervisor mời agent, hỏi lại cư dân
  hai lần, lập phương án → BQL duyệt → cư dân đồng ý → đúng 1 phiếu thi công → BQL phân công → kỹ thuật viên nhận
  việc, tới nơi, gửi báo giá → cư dân đồng ý báo giá → thi công, ảnh trước/sau, gửi kết quả → BQL nghiệm thu → cư dân
  xác nhận → BQL duyệt đóng. Kết quả: ticket `closed`, phiên `completed` (ticket `VH-3B8AB506EABE`, 19 bước).
- **Phòng nhóm BQL** (`/operations/team`) là một màn: agent của nhóm, danh sách phiên kèm nút điều khiển, chat nhóm
  có `@agent`, bảng công việc. Mỗi phiên nay ghi rõ đang chờ ai (BQL duyệt phương án, cư dân trả lời, cư dân đồng ý,
  phân công và thi công) và mã ticket mở thẳng chi tiết ticket.
- **Admin gắn BQL vào đơn vị quản lý:** màn tài khoản có ô "Đơn vị quản lý" cho vai trò Ban quản lý. Tài khoản tạo ra
  chỉ có quyền trong đơn vị đó và tự vào phòng nhóm của đơn vị; đổi vai trò hoặc khóa thì rời phòng. Không chọn đơn vị
  thì giữ quyền toàn khu như cũ. Kiểm bằng trình duyệt 6/6 bước và test đăng nhập thật 4/4.
- **Admin ghi đè:** quản trị viên đọc được mọi phòng quản lý và thu hồi agent của bất kỳ phòng nào (test API và test
  đăng nhập thật đã cập nhật theo hành vi này).
- Sửa nhỏ: kỹ thuật viên mở ticket không còn thấy lỗi 404 của nút điều khiển phiên (nút chỉ dành cho BQL).

Giới hạn ghi nhận:

- Sau khi BQL đóng phiên, checkpoint của Supervisor vẫn ở `execution_ready`; trạng thái đúng nằm ở backend
  (`completed`) và đó là cái giao diện hiển thị. Phần phân công, thi công, QC do BQL và kỹ thuật viên làm trên
  Operations, Supervisor không điều phối.
- Cơ sở dữ liệu local chỉ có một kỹ thuật viên; khi người này đang bận một phiếu thì ô "Nhân viên nhận việc" trống.
  Màn admin chưa tạo được hồ sơ nhân viên (chuyên môn, ca làm) cho tài khoản nhân viên mới.
- **Báo cáo (B6):** lúc ghi mục này bản nhúng còn là bộ 8 tool cũ. Đã chốt theo bản mới nhất trên `develop` và làm
  xong, xem mục "Agent báo cáo" bên dưới.

- **Test server cần cơ sở dữ liệu:** chạy trên PostgreSQL riêng đã migrate thì không xong trong 9 phút. Các test tích
  hợp gốc của OpenBot (`agent-profile-store`, `agent-handoff`, `agent-factory*`) chèn vào `agents`/`mcp_servers` mà
  không có `tenant_id`, trong khi schema V2 bắt buộc cột này; mỗi hook lỗi chờ 5 giây. File test và migration gốc
  giống hệt trên `develop`, nên đây là lệch có sẵn giữa test gốc và schema V2, không do nhánh này. 3921 test không
  cần bảng dữ liệu vẫn đạt.

## Agent báo cáo, dữ liệu Team Quang và chạy lại các luồng (04/10, khuya; chạy local)

### Agent báo cáo (B6)

Chốt theo bản Team Hoàng trên `develop` (`48ea913`, bộ tool 2.0.0). Bốn tool: `filter_report_scope`,
`get_repair_bill_summary`, `get_ticket_frequency_summary`, `get_employee_star_summary`.

- `services/vinhomes-api/src/vinhomes_api/_vendor/reporting` nay là bản sao nguyên văn của `server/src/reporting`.
  Không sửa file nào trong đó; khi Team Hoàng cập nhật thì chép lại rồi chạy test cổng tool.
- Bộ tool đọc các route sẵn có của API (`/catalogs`, `/reports/filter-options`, `/reports/supporting-records`,
  `/reports/incident-frequency-summary`, `/reports/employee-feedback`, `/invoices/{id}`). Cổng tool
  (`v3_tool_gateway.py`) chạy chính các hàm route đó trong transaction đã kiểm quyền, không giả cookie, và trả kết
  quả đúng dạng JSON mà route gửi (tiền là chuỗi số thập phân chính xác). Mỗi lần đọc tòa hoặc hóa đơn đều kiểm với
  phạm vi tòa của workspace.
- Nhóm dịch vụ nào tính là "sửa chữa" là cấu hình của nơi triển khai: `VINHOMES_API_REPAIR_CATEGORY_CODES` (mã nhóm,
  cách nhau bằng dấu phẩy; local đặt `technical`). Chưa đặt thì tool hóa đơn trả
  `REPORT_REPAIR_CATEGORIES_REQUIRED` và không báo tổng.
- `scripts/setup_session_tools.py` đăng ký 4 tool với phiên bản của chính tool và xóa các tool cổng không còn phục
  vụ. Bảy tool cũ đã bị xóa khỏi danh mục; agent còn cầm tool cũ sẽ bị từ chối khi gọi và phải ra phiên bản mới.

Kiểm chứng: test cổng tool so số ticket, số sự cố và tổng hóa đơn với SQL (20 hóa đơn, 4.100.000,00 VND), có ca thiếu
cấu hình và ca ngoài phạm vi; cả bộ backend 71 đạt, 7 bỏ qua. Trên giao diện, BQL tạo "Agent Báo cáo" trong phòng
nhóm, chọn 4 tool, đánh giá 6 ca bằng model thật, phát hành, rồi hỏi bằng `@Agent Báo cáo`: danh sách tòa và phân khu
được xem (4 tòa Sapphire và phân khu Sapphire), thống kê ticket tòa S1.01 (14 ticket, 14 sự cố; khớp SQL), hóa đơn sửa
chữa và sao đánh giá (cơ sở dữ liệu local chưa có hóa đơn và đánh giá nào; agent trả "không có dữ liệu", không ghi số
0 thay cho lỗi).

Ghi nhận khi chạy thật: schema của `filter_report_scope` không thể hiện ràng buộc "có `name` hoặc `scope_id` thì phải
có `scope_type`, và không gửi cả hai". Bản 1 của agent gửi sai và nhận `REPORT_INPUT_INVALID`; bản 2 sửa chỉ dẫn (gọi
với `{}` rồi tự tìm trong danh sách) thì chạy đúng. Nên nhờ Team Hoàng ghi ràng buộc này vào mô tả tool.

Còn lại: "Agent kiểm chứng BQL 1791096816" (agent thử của phiên làm việc trước) vẫn phát hành với tool cũ
`reporting.get_incident_frequency_summary`; gọi tool sẽ bị từ chối. Thu hồi hoặc ra bản mới. Tất cả ticket local
chưa có loại sự cố nên báo cáo ghi "Không phân loại".

### Dữ liệu Team Quang (`dev_TeamQuang_ddhung04`, `docs/teams/quang/technical-data`, commit `20b7b46`)

Đã đọc và kiểm, chưa nhập vào hệ thống. Nhánh chỉ thêm 23 file tài liệu, không đổi code.

- Đúng như mô tả: 16 hồ sơ sự cố, 77 fact có nguồn (24 + 30 + 23), 16 đoạn tri thức, 10 phản ánh công khai ở Huế,
  32 ca giả lập, 23 câu kiểm thử, 74 mã nguồn trỏ 72 URL. Script `validate_data.ps1` của họ chạy đạt.
- 16 mã sự cố khớp đúng 16 mã trong `server/src/technical-tools/reference/issue-codes.ts`. Mọi trích dẫn của 16 đoạn
  tri thức nối được về fact và nguồn. Không thấy số điện thoại hay email trong các ca.
- Chưa dùng được cho `sop_kb.retrieve`, và chính tài liệu của họ nói vậy: đây là diễn giải ngắn từ nguồn công khai
  (182–337 ký tự mỗi đoạn), mọi bản ghi ở trạng thái `not_published`, 74/74 nguồn chưa lưu bản gốc và chưa có hash,
  quyền dùng toàn văn chưa rõ, 22 fact chưa ghi vị trí trong nguồn. Không có SOP đã duyệt, dữ liệu gián đoạn, thiết
  bị, mapping UUID hay script nhập, tức các mục trong `TEAM_QUANG_DATA_HANDOFF_2026-10-04.md` vẫn còn nguyên.
- Kiểm 72 URL từ máy local: 39 mở được, 32 trả 403 với truy cập tự động (hud.gov, cdc.gov, vinhomes.vn,
  panasonic.com), 1 không kết nối được (moit.gov.vn). Chưa kết luận link hỏng; cần người mở tay khi duyệt nguồn.
- Dùng được ngay mà không cần duyệt SOP: (1) 16 mã sự cố làm danh mục `incident_types` để ticket hết "Không phân
  loại"; (2) 23 câu kiểm thử và 32 ca giả lập làm ca đánh giá agent kỹ thuật; (3) 16 đoạn tri thức làm kho tham khảo
  nội bộ riêng cho agent kỹ thuật, không trả lời cư dân. Cả ba đều chưa làm.

### Chạy lại các luồng sau thay đổi trong ngày

- Test: backend 71 đạt, 7 bỏ qua; tích hợp HTTP 2; Lễ tân đầu-cuối 9 + 9 (model giả lập); Supervisor 443; typecheck
  Operations và ứng dụng cư dân đạt.
- Trình duyệt, tài khoản thật, model thật: một yêu cầu đi hết vòng đời (ticket `VH-17DF1C67A8EC` `closed`, phiên
  `completed`). Cư dân không còn thấy mã `VH-…` trong chat và danh sách yêu cầu.
- Phiên của ticket `VH-B8F1E299CE24` (tạo sáng 04/10): backend ghi BQL đã duyệt, chờ cư dân, nhưng Supervisor vẫn ở
  `waiting_management`. Các phiên tạo từ chiều 04/10 không bị; chưa tìm nguyên nhân của độ lệch. Màn Điều phối mới
  đọc trạng thái phương án từ backend nên đã ghi đúng "Chờ cư dân đồng ý phương án".
- Ảnh chụp màn hình BQL và admin: `.codex-artifacts/bql-ui-2026-10-04/` (thư mục không đưa vào git).

## Giao diện Ban quản lý làm lại theo kiểu OpenBot (04/10, đêm muộn; chạy local)

Menu của BQL trước đó có 9 mục, trong đó 6 mục là cùng một danh sách công việc với bộ lọc khác nhau, và phòng nhóm
là một trang dài ghép agent, phiên, chat và bảng công việc. Nay:

- **Menu 4 mục:** Điều phối, Công việc, Agent, Báo cáo (admin thêm Quản lý tài khoản). Đăng nhập BQL vào thẳng
  Điều phối. Các trang cũ (`/operations/triage`, `incidents`, `work-orders`, `qc`, `completed-tasks`, trang tổng
  quan) vẫn mở được bằng địa chỉ nhưng không còn trong menu. Câu hỏi của cư dân cần BQL trả lời và câu trả lời chờ
  duyệt đưa vào tri thức, trước chỉ có ở "Tiếp nhận phản ánh", nay hiện ở Công việc.
- **Điều phối** (`/operations/team`, mã ở `app/src/features/vinhomes-operations/connected/coordination/`): bên trái là
  danh sách phiên xếp theo người phải làm ("Cần bạn xử lý", "Đang điều phối", "Đã xong"); bên phải là một hội thoại.
  Hội thoại của phòng chỉ gồm trao đổi chung và câu hỏi cho agent (`@agent`). Hội thoại của một phiên gồm lời cư dân,
  việc Supervisor và agent đã làm, thẻ phương án có nút Duyệt/Từ chối, ô hỏi agent trong phiên, nút tạm dừng/chạy
  tiếp/dừng, và thẻ "Duyệt đóng phiên" khi cư dân đã xác nhận. Không hiện mã `VH-…`.
- **Thông báo:** số phiên chờ BQL hiện ở mục Điều phối, ở chuông (mỗi dòng mở thẳng phiên đó) và trên tiêu đề tab.
- **Agent** (`/operations/agents`): thẻ cho agent đang làm việc; bản nháp và agent đã thu hồi gập lại bên dưới. Hộp
  cấu hình chia 4 thẻ: Cấu hình, Phạm vi và công cụ (tool gom theo Báo cáo/An ninh/Kỹ thuật), Đánh giá, Phát hành.
  Nút "Chạy đánh giá" khóa khi còn sửa đổi chưa lưu, vì đánh giá chạy trên bản đã lưu ở máy chủ.
- **API:** `GET /rooms/{room}/teams` trả thêm `plan_status`, `ticket_status`, `updated_at`. Trạng thái phiên trên màn
  hình lấy từ trạng thái phương án do backend ghi, không lấy từ pha Supervisor báo lần cuối; nhờ đó hết kiểu phiên đã
  duyệt mà vẫn ghi "chờ BQL duyệt" (ticket `VH-B8F1E299CE24`).

Kiểm chứng:

- Test giao diện mới `app/tests/operations-coordination.test.tsx` 4/4 (mỗi file test giao diện chạy riêng một tiến
  trình, như các file cũ); typecheck đạt; backend 71 đạt, 7 bỏ qua.
- Trình duyệt, tài khoản thật: BQL mở phiên từ chuông, duyệt phương án trong Điều phối (phương án sang
  `resident_pending`, Supervisor sang `waiting_resident_plan`, chuông giảm 7 → 6); một yêu cầu đi từ phân công tới thi
  công, nghiệm thu, cư dân xác nhận, rồi BQL duyệt đóng phiên trong Điều phối (14/14 bước, ticket `VH-8B066AD249B4`
  `closed`, phiên `completed`). Đã chụp cả bản màn hình điện thoại (390px).
- **Chưa kiểm bằng model thật trên màn mới:** hỏi agent trong phiên, và phiên mới do Supervisor lập phương án. Khóa
  model của stack local trả `429 insufficient_quota` (hết số dư) từ khoảng 20:29 ngày 04/10; phiên tạo lúc đó dừng
  với lý do `model_unavailable` và màn Điều phối ghi rõ lý do này. Chạy lại `flow_full.py` sau khi nạp lại.

Giữ nguyên, chưa đổi: trang chi tiết công việc vẫn có khối "Phiên điều phối" kiểu cũ (kỹ thuật viên cũng đọc khối
này) kèm liên kết sang Điều phối; danh sách Công việc vẫn hiện mã `VH-…` cho nhân viên đối chiếu; menu của kỹ thuật
viên không đổi; đăng nhập OpenBot và tài khoản nghiệp vụ vẫn là hai hệ thống.

Ảnh chụp: `.codex-artifacts/bql-ui-v2/` (không đưa vào git).

## Đóng gói Docker sau các thay đổi trong ngày (04/10, đêm muộn)

Build lại cả 9 image và chạy stack trên bản sao cơ sở dữ liệu. Ba thiếu sót lộ ra khi chạy và đã sửa:

- **Ảnh không lưu được trong container** (tải ảnh trả 503 nên kỹ thuật viên không gửi được kết quả): API chỉ lưu ra
  đĩa khi nghe trên loopback. Chủ dự án chọn lưu vào volume: thêm cài đặt riêng `VINHOMES_API_VOLUME_FILE_STORAGE`,
  volume `api-files`. Quy tắc loopback cho chạy local giữ nguyên.
- **Bản triển khai mới không cấp được tool cho agent:** danh mục tool chỉ được đăng ký bằng script chạy từ mã nguồn.
  Nay job `upgrade` đăng ký tool kỹ thuật và job mới `catalogue` đăng ký tool của cổng tool API
  (`python -m vinhomes_api.tool_catalogue`, dùng chung với `scripts/setup_session_tools.py`).
- **Cư dân nhận 502 sau mỗi lần thay container API:** nginx của ứng dụng cư dân giữ địa chỉ cũ. Nay nó hỏi lại DNS
  của Docker.

Kết quả kiểm và phần chưa kiểm: [deploy/vinhomes/README.md](../../../deploy/vinhomes/README.md). Các bước cần model
chưa chạy lại trên image mới vì khóa model hết số dư.

Hạng mục kết nối ngoài cho agent của BQL: chủ dự án chốt làm MCP theo URL trước, dùng tài khoản dùng chung của đơn
vị; kế hoạch K1–K6 ở `tasks/todo.md`, chưa bắt đầu code.

## Kết nối ngoài (MCP) cho agent của BQL và BQL tự phát hành agent (04/10, đêm; chạy local)

Chủ dự án chốt thêm: BQL tự phát hành agent, không cần quản trị viên duyệt; quản trị viên là người cấu hình nền tảng.

- **Kết nối MCP theo URL.** Quản trị viên thêm kết nối ở màn "Kết nối ngoài" (tên, địa chỉ https, khóa truy cập, nhóm
  được dùng), mở kết nối để xem máy chủ đang có công cụ nào và chọn công cụ được phép. BQL thấy các công cụ đó trong
  hộp cấu hình agent, gom theo tên kết nối. Không thêm bảng: dùng `mcp_servers`, `mcp_tools`, `credentials` sẵn có.
- **Ai giữ gì.** Tool host (`server/src/technical-api/connection-routes.ts`) giữ khóa mã hóa và gọi máy chủ MCP bằng
  mã của OpenBot. API (`v3_connections.py`, cổng tool) kiểm quyền, nhóm, bản agent đã ghim và ghi audit; API chỉ lưu
  khóa ở dạng đã mã hóa và không trả lại.
- **Quy tắc an toàn.** Nhãn "chỉ đọc" do máy chủ MCP tự khai không được tin; quản trị viên chọn từng công cụ. Công cụ
  máy chủ tự đánh dấu phá hủy không chọn được. Địa chỉ phải là https tới tên miền công khai. Gỡ công cụ hoặc xóa kết
  nối bị từ chối khi agent đã phát hành còn dùng, kèm tên agent. Nội dung agent gửi cho công cụ đi ra máy chủ ngoài, và
  câu trả lời của máy chủ ngoài được model đọc: chỉ nối tới máy chủ tin được.
- **BQL tự phát hành.** API vốn đã cho BQL phát hành sau khi đánh giá trên máy chủ đạt; nay giao diện bỏ danh sách
  "Agent chờ duyệt" của quản trị viên, nút Phát hành không bắt ghi chú. Quản trị viên vẫn thu hồi được ở trang Agent.
- **Sửa lỗi nhân viên kỹ thuật:** mục "Công việc đã hoàn thành" đưa về trang đăng nhập; nay mở đúng lịch sử.

Đã kiểm: test backend 72 đạt, 7 bỏ qua (có test mới cho kết nối); test giao diện kết nối 1, điều phối 4; typecheck app
và server; trên trình duyệt với máy chủ MCP thử: quản trị viên thêm kết nối và cho phép công cụ 6/6 bước, BQL cấp công
cụ cho agent mới 3/3 bước; image `technical-tools` build lại và trả lời các route kết nối.

Chưa kiểm: đánh giá, phát hành và câu trả lời của agent dùng công cụ ngoài, vì khóa model mới bị `api.openai.com` trả
401 `invalid_api_key`. Chưa chạy kết nối trong cả stack container.

Kế hoạch và việc còn lại (kết nối, MinIO/S3, giao diện nhân viên và quản trị viên): `tasks/todo.md`.

## Model theo vai trò, giao diện quản trị viên và lưu ảnh trên MinIO/S3 (05/10; chạy local và container)

- **Model theo vai trò.** Lễ tân, Supervisor, agent chuyên môn và embedding có nhà cung cấp, khóa, địa chỉ riêng
  (`openai`, `google`, `deepseek`, `groq`, `anthropic`, `custom`). Khóa OpenAI chỉ gửi tới OpenAI; vai trò dùng nhà cung
  cấp khác mà thiếu khóa riêng thì không khởi động. Chưa chạy với khóa thật của nhà cung cấp nào ngoài OpenAI.
- **Quản trị viên** có menu riêng: Tài khoản (làm lại), Đơn vị quản lý, Kết nối ngoài, Model, Nhật ký. Ba màn sau chỉ đọc.
- **Ảnh và tệp** lưu trong bucket riêng tư trên MinIO/S3 khi đặt `VINHOMES_API_S3_ENDPOINT`; dùng nguyên các bảng
  `storage_locations` và `file_objects` đã có. Ảnh vẫn đi qua API. Job `storage` chuyển ảnh cũ từ đĩa sang bucket.
  Image `minio/minio` không còn kéo được từ Docker Hub; compose dùng `cgr.dev/chainguard/minio`.
- **Agent báo cáo:** 4 tool đã đóng gói; agent là dữ liệu của phòng nhóm, bản triển khai mới phải tạo qua trang Agent
  (cấu hình ở `docs/teams/hoang/agent/`). Agent không được mời vào phiên vì không khai danh mục.

Đã kiểm: test backend 76 đạt, 7 bỏ qua (có test admin và 3 test lưu trữ chạy với MinIO thật); test Supervisor 36, Lễ tân
18; test giao diện quản trị 3, kết nối 1; typecheck app và server. Trong container trên bản sao cơ sở dữ liệu: build lại
9 image, 9 dịch vụ `healthy` với Lễ tân đặt `deepseek` và Supervisor đặt `google`, màn Model báo đúng; job `storage`
chuyển 6 ảnh cũ sang bucket và chạy lại không chuyển gì thêm; ảnh cũ tải được, ảnh mới tải lên rồi tải về đúng nội dung;
năm màn quản trị mở được.

Chưa kiểm: mọi bước cần model (khóa hiện tại bị từ chối 401), nên chưa có hội thoại thật với Gemini, DeepSeek hay
Claude và chưa nghiệm thu agent dùng công cụ MCP. Chưa thử ảnh hội thoại và ảnh cư dân trên bucket qua giao diện (đã
kiểm lớp lưu trữ bằng test).

## Thứ tự hoàn thiện tiếp

1. Kiểm UI các nút điều khiển phiên; vòng agent v1→v2, BQL từ chối/thu hồi và admin ghi đè. Hoàn thiện cấp scope/workspace BQL trên màn admin.
2. Chạy ticket an ninh thật qua Supervisor; kiểm cư dân từ chối và luồng tiếp nhận Reception UI từ đầu. Đối soát các báo cáo còn lại trên dữ liệu có số liệu.
3. Team Quang bàn giao SOP/gián đoạn, file nguồn, manifest, mapping UUID, scope/ACL và script import; nhập và kiểm truy vấn có dữ liệu/hết hiệu lực/ngoài quyền. An ninh cần danh mục camera/đầu mối nghiệp vụ; thiết bị cần API/dataset được phép riêng.
4. **Đã làm ngày 04/10 (chiều):** build lại 7 image từ working tree, smoke stack trên bản sao database đăng nhập thật với model thật, khởi động lại riêng `openbot` và `coordination`, đăng nhập qua `app/serve.ts` bằng cookie thật. Smoke tìm ra và đã sửa hai lỗi chặn trong compose: thiếu `VINHOMES_API_ALLOWED_ORIGINS` (đăng nhập bị từ chối) và địa chỉ `http://openbot:4200` bị lõi Supervisor từ chối vì không phải HTTPS/loopback (lượt agent dừng với `VALIDATION_ERROR`); nay `coordination` và `openbot` dùng chung không gian mạng qua `agents-net`. Hướng dẫn và giới hạn: [deploy/vinhomes/README.md](../../../deploy/vinhomes/README.md). Còn lại: đóng gói hai frontend, TLS/reverse proxy, SSO thống nhất giữa OpenBot và tài khoản nghiệp vụ, Factory mới qua health trong container.
5. Ghi provenance Factory/report vendor và reconcile tài liệu triển khai; rà soát diff, chạy check phù hợp rồi commit. Chưa merge toàn bộ nhánh Phái và chưa push.

Không chốt production-ready trước khi hoàn tất các bước áp dụng ở trên. Supervisor seed cũ chưa có release là một ngoại lệ bootstrap cần chuẩn hóa trước production; agent mới ở phòng chung bắt buộc có published release.
