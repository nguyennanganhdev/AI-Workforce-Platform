# Báo cáo cập nhật UI Platform BQL và Admin — 06/10/2026

Đã triển khai giao diện mới và backend mở rộng trên Docker local. Truy cập **http://localhost:3022/operations** bằng tài khoản BQL hoặc Admin hiện có. Mã nguồn nằm trên nhánh `dev_TeamChien` trong workspace; chưa commit hoặc push.

Thiết kế được đối chiếu với `C:\Users\Lenovo\Downloads\SKILL.md` và 10 ảnh tham chiếu đã gửi. Áp dụng karpathy-guidelines, ui-ux-pro-max, design-taste-frontend và shadcn-ui. Hai quyết định của người dùng được giữ: mở rộng backend và **Supervisor tiếp tục tự duyệt phương án**. Việc tự duyệt phương án không bỏ qua xác nhận từng thao tác ghi qua MCP.

## 1. Phạm vi đã triển khai

| Nhóm | Kết quả |
|---|---|
| Nền giao diện | Token màu/khoảng cách, Be Vietnam Pro tải tại local, shadcn/Base UI, trạng thái dùng chung, sidebar/topbar, tìm nhanh Ctrl/⌘ K, thông báo và số đếm dùng chung. |
| BQL — Yêu cầu | Danh sách và bảng sáu bước; ưu tiên việc cần xử lý; tiêu đề, vị trí, lý do và hạn xử lý; tìm/lọc theo dữ liệu thật. Trang phiên đầy đủ có hội thoại, phương án, người tham gia, thông tin cư dân/thiết bị/ảnh/lịch sử, chỉnh người thực hiện và giờ hẹn, thanh quyết định cố định. |
| BQL — Hỏi agent | Lịch sử riêng theo người dùng và đơn vị; chọn agent hoặc Supervisor tự định tuyến; tác giả từng câu trả lời; công cụ/nguồn đã dùng; nguồn ngoài bật riêng; xác nhận thao tác ghi và kết quả. Chuyển đơn vị xóa lựa chọn hội thoại cũ. |
| Agent — Sơ đồ | React Flow, bố trí tự động, bộ đếm từ database, cập nhật SSE và polling dự phòng, inspector, xem phiên, toàn màn hình. Loại phiên/yêu cầu đã kết thúc và thế hệ cũ khỏi dữ liệu live. |
| Agent — Danh sách/Thư viện | Phân biệt bản nháp và bản phát hành; hiển thị cấu hình đã ghim của bản đang phát hành; công cụ, kỹ năng, kết nối riêng/dùng chung và trạng thái sử dụng. |
| Agent — Trình soạn | Trang riêng với Soạn → Thử → Đánh giá → Phát hành; chọn model/kỹ năng; nhờ Factory sinh chỉ dẫn/công cụ; lưu nháp; câu hỏi mẫu; đánh giá sáu ca; phát hành rõ ràng. Model/kỹ năng vừa chọn được giữ khi Factory cập nhật bản nháp. Chỉ dẫn Factory có tóm tắt tiếng Việt từ nhiệm vụ, công cụ và kỹ năng đã lưu; trình soạn mở rộng giữ nguyên prompt đầy đủ. Khi sửa prompt, UI hiển thị nội dung sửa, không dùng tóm tắt cũ. |
| Báo cáo | Phạm vi, loại báo cáo, ngày bắt đầu/kết thúc, kết quả từ API hiện có và xuất tài liệu. |
| Admin — Tổng quan | Yêu cầu mở/quá hạn, tài khoản chờ duyệt, kết nối mới; việc cần xử lý, sức khỏe dịch vụ, yêu cầu theo ngày và nhật ký gần nhất. |
| Admin — Tài khoản/Đơn vị | Tìm/lọc/CSV, duyệt hoặc từ chối đăng ký, drawer sửa tài khoản, trạng thái truy cập, lựa chọn nhiều tài khoản; danh sách đơn vị và trang chi tiết theo tab. |
| Admin — Kết nối | Registry toàn hệ thống, chủ sở hữu/người thêm, công cụ đọc/ghi, số agent đang dùng, kết nối mới, kiểm tra/tạm ngưng, chính sách duyệt tùy chọn. Usage tính theo bản phát hành đã ghim; kết nối còn lịch sử được giữ và trả lý do rõ ràng khi yêu cầu xóa. |
| Admin — Model | Đăng ký model bằng tham chiếu biến môi trường, kiểm tra kết nối, cho phép BQL sử dụng, mặc định năm vai trò; trả về cấu hình triển khai khi xóa mặc định. Phân biệt model đã chọn với model dịch vụ tự báo cáo. |
| Admin — Nhật ký | Tác nhân, hành động, đối tượng, kết quả; lọc thời gian/tác nhân/loại/đối tượng/từ khóa, CSV và drawer. Có các sự kiện agent tham gia, định tuyến câu hỏi và dùng nguồn ngoài. Cursor gồm thời gian và ID để không bỏ sót các sự kiện cùng thời điểm. |
| Mobile | Sidebar/history/nguồn/chi tiết thành drawer hoặc sheet; sơ đồ chuyển sang danh sách; trình soạn agent yêu cầu desktop; composer và hành động chính giữ trong viewport. Header phiên tối đa 96px. |

Các màn chính dùng dữ liệu backend. Khi dữ liệu chưa có, UI dùng trạng thái trống hoặc ẩn trường tương ứng; không đưa số liệu mẫu từ ảnh tham chiếu vào database.

## 2. Backend và quyền thực thi

- Hội thoại riêng kiểm tra chủ sở hữu; Admin không có quyền đọc thay người dùng. Gửi lại cùng khóa yêu cầu không tạo câu hỏi trùng; thay payload trên cùng khóa bị từ chối.
- Kỹ năng của đơn vị và kỹ năng dùng chung được lưu; bản phát hành ghim nội dung kỹ năng, model và công cụ. Admin không sửa chỉ dẫn của agent thuộc BQL.
- Kết nối MCP thuộc đơn vị, mặc định không cần Admin duyệt. Kết nối mới chưa tự bật trên agent, hội thoại hoặc phiên. Công cụ ghi phải được chọn rõ ràng; công cụ không có khai báo chỉ đọc không được tự coi là an toàn để đọc.
- Ghi qua MCP luôn dừng tại xác nhận có người yêu cầu, agent, bản phát hành, công cụ, dữ liệu và hạn hiệu lực. Xác nhận được tiêu thụ trước khi gọi bên ngoài; kết quả không rõ được ghi `uncertain` và không tự gọi lại. Tắt nguồn, thu hồi agent hoặc tạm ngưng kết nối được kiểm tra lại lúc thực thi.
- Nguồn trong phiên được bật theo **BQL + phiên**. Câu hỏi explicit tạo run gắn đúng người hỏi, thành viên và bản phát hành; các lượt tự động vẫn không có quyền ghi ngoài thay người dùng.
- Reception, Supervisor, specialist, Factory và truy vấn embedding đọc mặc định đã đăng ký ở backend. Khóa model chỉ đi trong đường dịch vụ; UI/database đăng ký chứa tên biến môi trường, không chứa khóa thô.
- Giữ không gian embedding hiện có: `text-embedding-3-large`, 1536 chiều. Đổi sang không gian khác bị chặn; cần nhập lại kho riêng và đánh giá retrieval trước khi kích hoạt.

## 3. Database và triển khai local

Đã chạy migration `0015_private_agent_chats`, `0016_ops_connections`, `0017_admin_model_registry` và `0018_session_external_sources`, cập nhật journal và quyền của các role giới hạn. Database đang chạy là **`vinhomes_docker_complete`**, có **20 mục migration** và đủ **8 bảng mới**.

Đã tạo backup trước các đợt migration trong volume `vinhomes_backups`:

- `20261006T123309Z` — trước đợt hội thoại riêng/kết nối/model.
- `20261006T133843Z` — trước migration nguồn ngoài trong phiên.

Đã build và khởi động lại các dịch vụ liên quan bằng Compose hiện có. Snapshot cuối xác nhận **15 container đang chạy**, trong đó **14 có healthcheck và đều healthy**; `agents-net` là container mạng không có healthcheck. `VINHOMES_API_SUPERVISOR_APPROVES_PLANS=1` vẫn được giữ.

Registry local đã kiểm tra thành công `gpt-6-luna`, `gpt-5.5` và `text-embedding-3-large`. Mặc định hiện tại: Reception/Supervisor dùng `gpt-6-luna`, specialist/Factory dùng `gpt-5.5`; agent có thể chọn riêng model được cho phép.

Chuyển giao diện khung cũ bằng `?ui=legacy` hoặc lựa chọn giao diện trong menu. Đây là rollback **khung điều hướng**, không phải rollback database hay toàn bộ màn nghiệp vụ. Khi cần khôi phục dữ liệu, dùng quy trình backup/restore trong [README triển khai](../deploy/vinhomes/README.md).

## 4. Kiểm chứng

| Kiểm tra | Kết quả |
|---|---|
| API đầy đủ | 129 đạt, 11 bỏ qua; warning deprecation của thư viện test. |
| Graph/kết nối sau sửa cuối | 4 đạt riêng, gồm regression graph mới với 8 trạng thái lifecycle. Không gọi đây là một lượt chạy đầy đủ 130 bài. |
| Supervisor/coordination | 52 đạt. |
| Factory | 54 đạt, 291 assertions. |
| Reception model runtime | 12 đạt, 12 bỏ qua; không tính bài bỏ qua là đã nghiệm thu. |
| Knowledge authority/embedder | 11 đạt; kiểm tra quyền, tham số và từ chối vector sai chiều. |
| Giao diện | 79 đạt qua 17 file, chạy mỗi file trong một tiến trình Bun riêng. Có kiểm tra tóm tắt chỉ dẫn, prompt đầy đủ và sửa prompt mà không thay đổi cấu hình trước khi lưu. |
| Typecheck/build | App, server, Factory đạt; build Docker Operations/API và các runtime liên quan thành công. |
| Browser trên bản Docker | 53 màn/trạng thái desktop và mobile; không lỗi JavaScript, không tràn ngang. Có viewport 1366×768 và 390×800, kiểm tra vị trí hành động chính và header phiên. |

Nghiệm thu dùng dịch vụ/model thật trên stack local:

1. **Hỏi agent riêng:** gửi thủ công và Supervisor tự định tuyến; agent trả lời qua `knowledge.search`; attribution và công cụ đã dùng được lưu. Admin đọc hai hội thoại này nhận **404**.
2. **Hỏi trong phiên:** Agent Kỹ thuật A2 trả lời đúng nội dung yêu cầu; run và câu trả lời lưu đúng người hỏi, phiên, bản phát hành. Nguồn ngoài giữ tắt; không tạo thao tác ghi.
3. **Factory:** sinh và lưu bản nháp cho nhiệm vụ báo cáo tòa nhà hoặc phân khu. Giữ model `gpt-6-luna` và kỹ năng đã chọn; sinh **9.318 ký tự chỉ dẫn** và đúng hai công cụ báo cáo. Trial bằng provider thật hỏi lại phạm vi và ngày bắt đầu/kết thúc, `called=[]`; hash cấu hình không đổi sau trial. Agent chưa phát hành.
4. **Factory từ chối an toàn:** bản sinh mở rộng nhiệm vụ “chỉ một tòa nhà” sang phân khu bị chặn; bản nháp cũ không thay đổi và không được phát hành. Chưa chạy lại riêng mô tả này sau lần bổ sung hướng dẫn giữ phạm vi; không coi trường hợp đó là construction đã thành công.

Bằng chứng nằm trong [thư mục nghiệm thu](../.codex-artifacts/operations-ui-2026-10-06/):

- [Browser và ảnh chụp](../.codex-artifacts/operations-ui-2026-10-06/verification.json)
- [Trạng thái Docker/database/backup](../.codex-artifacts/operations-ui-2026-10-06/deployment.json)
- [Hội thoại riêng và quyền riêng tư](../.codex-artifacts/operations-ui-2026-10-06/runtime-acceptance.json)
- [Câu hỏi trong phiên và SQL provenance](../.codex-artifacts/operations-ui-2026-10-06/session-runtime-acceptance.json)
- [Factory thành công](../.codex-artifacts/operations-ui-2026-10-06/factory-acceptance.json), [Factory từ chối phạm vi mở rộng](../.codex-artifacts/operations-ui-2026-10-06/factory-building-only-refusal.json)
- [Kết quả UI](../.codex-artifacts/operations-ui-2026-10-06/ui-test-results.json), [API](../.codex-artifacts/operations-ui-2026-10-06/api-final.log), [graph/kết nối](../.codex-artifacts/operations-ui-2026-10-06/api-graph-connections.log), [coordination](../.codex-artifacts/operations-ui-2026-10-06/coordination-final.log), [Factory](../.codex-artifacts/operations-ui-2026-10-06/factory-final.log)

Các script `verify-operations-ui.py`, `verify-operations-tests.py`, `verify-operations-runtime.py`, `verify-session-runtime.py`, `verify-operations-factory.py` và `snapshot-operations-deployment.py` trong `scripts/` giúp chạy lại kiểm chứng. Các script runtime có thể tạo câu hỏi hoặc bản nháp nghiệm thu được đặt tên rõ; không tự phát hành agent. Tài khoản đọc từ file local đã bỏ qua Git, không ghi thông tin đăng nhập vào báo cáo.

## 5. Giới hạn nghiệm thu và bàn giao

Gói bàn giao theo yêu cầu nằm tại [`.codex-artifacts/packages/operations-ui-2026-10-06`](../.codex-artifacts/packages/operations-ui-2026-10-06/README.md), kèm [bản ZIP](../.codex-artifacts/packages/operations-ui-2026-10-06.zip). Gói gồm báo cáo, ảnh chụp cuối, log và dữ liệu kiểm chứng, cùng manifest SHA-256; không đóng gói file cấu hình bí mật hoặc thông tin đăng nhập. Các file này được lưu trong workspace, không commit/push.

- Đã triển khai **local Docker**. Chưa triển khai host/domain/TLS bên ngoài, chưa nghiệm thu production hoặc restore off-host cho đợt này.
- Rà soát database bổ sung lúc 21:48 ngày 06/10 phát hiện role API thực tế `vinhomes_connected_api` chưa có `DELETE` trên `admin_role_models`. Endpoint bỏ model mặc định cần quyền này; các bài fixture đã đạt không chứng minh quyền thực tế của deployment. Cần bổ sung grant cho role runtime trong luồng upgrade. Đợt xuất backup chỉ thống kê và giữ nguyên quyền nguồn, chưa áp dụng grant này.
- Cơ chế MCP đọc/ghi và chống thực thi trùng được kiểm tra bằng PostgreSQL thật với endpoint host được kiểm soát trong test. Chưa có thông tin kết nối thực tế của Google Drive/Lịch Google/kho vật tư để nghiệm thu các hệ thống bên ngoài đó. Các tên trong ảnh không được coi là kết nối đã hoạt động.
- Bài kiểm tra UI có fixture cho các trạng thái cần quyết định; lượt nghiệm thu live không duyệt tài khoản, không đổi phương án/giao việc của người dùng và không phát hành agent thử nghiệm. Các bản nháp và hội thoại nghiệm thu vẫn ở local để kiểm tra lại.
- Không khẳng định tất cả mô tả Factory đều sinh thành công. Mô tả chưa rõ hoặc artifact không đạt kiểm chứng được trả lỗi/câu hỏi làm rõ và giữ bản nháp hiện tại.
- Build còn cảnh báo kích thước chunk của ứng dụng hiện có. Chưa thực hiện đo hiệu năng trên thiết bị thực hoặc chứng nhận WCAG đầy đủ; kiểm thử browser và kiểm tra bố cục không thay thế các hoạt động đó.
- Độ trễ model đăng ký là số đo của lần kiểm tra gần nhất. Số trên sơ đồ là trung bình các lượt chạy thành công trong 7 ngày, có thể bao gồm thời gian dùng công cụ; không coi đó là benchmark riêng của model.
- Chưa commit/push hoặc thay đổi CI. Khi chuẩn bị phát hành bên ngoài, cần đưa thay đổi vào quy trình review của repository và cấu hình môi trường đích.

Các ghi chú ngày cũ trong README triển khai là bằng chứng của những đợt trước. Kết quả runtime/UI của đợt này được ghi trong báo cáo và artifact ở trên.
