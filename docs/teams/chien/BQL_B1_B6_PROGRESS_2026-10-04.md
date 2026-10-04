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
- **Báo cáo (B6) chưa đồng bộ được với Team Hoàng.** Bản trên `develop` không phải bản cập nhật của bản đang nhúng:
  bộ tool khác hẳn (`filter_report_scope`, `get_repair_bill_summary`, `get_ticket_frequency_summary`,
  `get_employee_star_summary` thay cho 8 tool cũ như `get_incident_frequency_summary`) và cách gọi backend cũng
  khác. Chép đè làm cổng tool không khởi động. Cần Team Hoàng chốt bộ tool nào là chuẩn; khi đổi phải viết lại lớp
  nối trong `v3_tool_gateway.py`, đăng ký lại catalogue và phát hành lại agent báo cáo vì tên tool đã cấp thay đổi.

- **Test server cần cơ sở dữ liệu:** chạy trên PostgreSQL riêng đã migrate thì không xong trong 9 phút. Các test tích
  hợp gốc của OpenBot (`agent-profile-store`, `agent-handoff`, `agent-factory*`) chèn vào `agents`/`mcp_servers` mà
  không có `tenant_id`, trong khi schema V2 bắt buộc cột này; mỗi hook lỗi chờ 5 giây. File test và migration gốc
  giống hệt trên `develop`, nên đây là lệch có sẵn giữa test gốc và schema V2, không do nhánh này. 3921 test không
  cần bảng dữ liệu vẫn đạt.

## Thứ tự hoàn thiện tiếp

1. Kiểm UI các nút điều khiển phiên; vòng agent v1→v2, BQL từ chối/thu hồi và admin ghi đè. Hoàn thiện cấp scope/workspace BQL trên màn admin.
2. Chạy ticket an ninh thật qua Supervisor; kiểm cư dân từ chối và luồng tiếp nhận Reception UI từ đầu. Đối soát các báo cáo còn lại trên dữ liệu có số liệu.
3. Team Quang bàn giao SOP/gián đoạn, file nguồn, manifest, mapping UUID, scope/ACL và script import; nhập và kiểm truy vấn có dữ liệu/hết hiệu lực/ngoài quyền. An ninh cần danh mục camera/đầu mối nghiệp vụ; thiết bị cần API/dataset được phép riêng.
4. **Đã làm ngày 04/10 (chiều):** build lại 7 image từ working tree, smoke stack trên bản sao database đăng nhập thật với model thật, khởi động lại riêng `openbot` và `coordination`, đăng nhập qua `app/serve.ts` bằng cookie thật. Smoke tìm ra và đã sửa hai lỗi chặn trong compose: thiếu `VINHOMES_API_ALLOWED_ORIGINS` (đăng nhập bị từ chối) và địa chỉ `http://openbot:4200` bị lõi Supervisor từ chối vì không phải HTTPS/loopback (lượt agent dừng với `VALIDATION_ERROR`); nay `coordination` và `openbot` dùng chung không gian mạng qua `agents-net`. Hướng dẫn và giới hạn: [deploy/vinhomes/README.md](../../../deploy/vinhomes/README.md). Còn lại: đóng gói hai frontend, TLS/reverse proxy, SSO thống nhất giữa OpenBot và tài khoản nghiệp vụ, Factory mới qua health trong container.
5. Ghi provenance Factory/report vendor và reconcile tài liệu triển khai; rà soát diff, chạy check phù hợp rồi commit. Chưa merge toàn bộ nhánh Phái và chưa push.

Không chốt production-ready trước khi hoàn tất các bước áp dụng ở trên. Supervisor seed cũ chưa có release là một ngoại lệ bootstrap cần chuẩn hóa trước production; agent mới ở phòng chung bắt buộc có published release.
