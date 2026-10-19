# Kết quả sửa session, chi phí và UI — 16/10/2026

Đã đóng gói và cập nhật Platform tại **https://vagen-platform.duckdns.org**. Bản UI cuối triển khai lúc **18:57:27, ngày 16/10/2026 (Asia/Saigon)**. Đã đối chiếu file trong container với manifest và JavaScript được phục vụ qua tên miền.

**Không sử dụng API key model để tự chạy thử.** Kiểm thử model dùng fake/local HTTP mock; kiểm tra production chỉ đọc API, dữ liệu đã có và giao diện. Chưa nghiệm thu một ticket mới qua model thật từ đầu đến cuối.

## Những vấn đề đã sửa

| Vấn đề | Thay đổi đã triển khai | Bằng chứng / giới hạn |
| --- | --- | --- |
| UI lộ ID, JSON, text dài | Giao diện phiếu ẩn UUID, mã event, nội dung tool thô, chọn model/quyền/thư mục. Hiện trạng thái nghiệp vụ, kết quả gửi cư dân và nhãn trao đổi BQL. Giữ thinking dạng mở rộng, thời gian thinking/recall/tool và thời gian/token từng lượt. Không biến lần gửi thất bại thành thông báo thành công. | Khôi phục telemetry theo yêu cầu chỉnh ngày 16/10; chỉ hiển thị thinking/recall khi có dữ liệu thật. Nút nghe lại âm thanh vẫn được giữ. |
| Trang chi phí quá nhiều thông số | Hiện phiếu hoàn tất, cần kiểm tra, latency p50/p95, chi phí ghi nhận và bảng model/token/latency. Chi tiết đối soát nằm trong mục mở rộng, không lộ endpoint ID. | Giá/usage thiếu vẫn ghi rõ chưa xác định; không tự bịa giá hoặc xóa usage lịch sử. |
| Model thực gọi khác model hiển thị | Policy tập trung áp dụng `gpt-6-luna` cho runtime, summary, builder, evaluation, learning và title qua `get_model`; giới hạn output 4.096 token, reasoning `none`, bỏ fallback model khác. Bổ sung model card cho hai adapter. | Fake HTTP kiểm tra payload tool calling. Đọc ledger production sau bản backend đầu thấy 98 lượt builder/eval/eval_judge đã hoàn tất đều dùng `gpt-6-luna`; đây là dữ liệu sẵn có, không phải lượt do bài kiểm tra này tạo. |
| Input bị lặp và vượt ngân sách | Phiếu dùng shared packet + lượt hiện tại; bỏ việc nạp thêm toàn bộ transcript riêng trùng lặp. Gộp snapshot trùng, dùng snapshot version mới nhất, giảm metadata kỹ thuật và task đã đóng trong input. | Shared packet tối đa 6.000 token, history 4.000; private context 8.000; output tối đa 4.096. Những giới hạn này không phải tổng token của cả case. |
| Summary vẫn không cứu được context | Lập chỉ mục summary xác định từ bằng chứng đã lưu; khi cần, chuyển bằng chứng dài sang tham chiếu có thể đọc lại bằng `CaseEvidence`. Giữ nguyên transcript/event gốc và phạm vi workflow. | Replay offline context phiên lỗi: 5.728 token/giới hạn 6.000, 9 tham chiếu lưu trữ, giữ 36 event nguồn, không gọi provider. Không suy ra mức tiết kiệm tổng case từ phép đo này. |
| Agent báo lỗi khi phản biện/tool | Sửa evidence gate nhận nhầm tên vai trò agent là tên nhân viên nghiệp vụ; vẫn kiểm tra tên nhân viên thật. Bằng chứng tool được lưu có cấu trúc đầy đủ thay vì cắt 1.200 ký tự. Thêm tool đọc bằng chứng theo workflow. Bỏ lượt gọi model thừa khi Leader bị đánh thức sau khi lượt cư dân đã kết thúc. | Regression tests kiểm tra role/staff evidence, quyền tool, kết quả muộn và wire tool calling. Chất lượng tranh luận qua model thật còn cần người dùng test. |
| BQL @mention bị hiểu là cư dân | Request từ console được xác định là BQL phía server, tách khỏi lượt cư dân. @mention chạy trong session nội bộ theo agent/version của workflow; trả lời chiếu về khung đang xem. Trao đổi này chỉ đọc, không tự gửi cư dân hoặc duyệt thay cư dân. | Test cả @agent và Leader; chặn write, resident consent và giả mạo tool bằng permission gate. Không thay ownership của team. |
| Cư dân gửi sang phải reload | Publish `message_upserted` cho tin nhận vào và reply đã lưu. Frontend upsert theo ID, reconnect SSE và đồng bộ lịch sử sau mất kết nối; có kiểm tra định kỳ khi idle và cập nhật danh sách phiên. | Offline browser kiểm tra event lặp, reconnect, phục hồi reply và phase idle. Production GET kiểm tra SSE; chưa tự tạo tin cư dân mới trên production. |

## Kiểm chứng

- Backend liên quan: **191 passed, 7 subtests passed**, 110 warnings; sau thay đổi giới hạn private context cuối, chạy lại nhóm liên quan: **46 passed, 7 subtests passed**.
- Frontend: TypeScript và production Vite build thành công; còn cảnh báo kích thước bundle lớn.
- Offline browser: event realtime, chống trùng, reconnect/history recovery, nhãn BQL, ẩn ID/CaseSay/runtime hint, giữ lời phàn nàn có tên trạng thái và nút nghe âm thanh. Regression cho bản khôi phục kiểm tra thinking, recall/tool time và footer thời gian/token; không có API POST hoặc model call.
- Production: health, route readiness, SSE headers và đọc lịch sử đạt; migration `0019_model_call_ledger`. Browser dùng token đăng nhập ngắn hạn, chỉ GET, không kiểm tra luồng đăng nhập đầy đủ.
- Đối chiếu **891 file backend, 470 file web**, public index và public JavaScript: không sai khác với manifest.
- `git diff --check` đạt; Ruff kiểm tra lỗi undefined/unused cho phần thay đổi đạt. Không coi đây là toàn bộ lint của repository.

Evidence cục bộ nằm trong `.artifacts/session-fix-20261016/`: `offline-tests.log`, `web-build.log`, `ui-offline.json`, `post-verify.json`, `host-verification.json`, `browser-live.json`, `live-ticket.png`, `live-activity.png`. Thư mục này có cả dữ liệu private phục vụ kiểm tra; không stage hoặc chia sẻ nguyên thư mục.

## Snapshot bản triển khai đầu lúc 18:57 và khả năng quay lại

| Thành phần | Giá trị |
| --- | --- |
| Checkout | `E:\AI-Workforce-Platform`, branch `develop2` |
| Commit nền | `e0d4a532824429e4327aa02397f0c9d9634c3e26` |
| Trạng thái Git lúc 18:57 | Các sửa đổi lúc này chưa commit/push; đã triển khai bằng artifact có manifest. Tag image ở snapshot này dùng SHA nền, không đại diện một commit chứa toàn bộ sửa đổi. Bản phát hành sau khi commit/push lấy SHA thực từ `release.json` trên host. |
| App image | `agentscope-platform:e0d4a532-sessionfix-20261016-2` |
| App image ID | `sha256:e751aa3e2ec0396a5567d02f0581f95320f7f0bc446a335361712b25f26144ac` |
| Web image | `agentscope-platform-web:e0d4a532-sessionfix-20261016-4` |
| Web image ID | `sha256:dd961094f2ad169764e4fdd27e861179506d5e2719fe1eafde753b4a90b61520` |
| Source manifest SHA256 | `59a6e423558127ae0e4639c7adfedf679482415b63accc3af6ccc64d5fbb8100` |
| Release trên host | `/opt/awp-platform/releases/sessionfix-20261016` |
| Backup trước cập nhật | `/var/backups/awp-platform/20261016T114025Z-awp-platform` |

Đã giữ image cũ, cấu hình trước rollout và backup dữ liệu. Lần đổi web đầu bị reset kết nối trong lúc khởi động đã tự quay lại bản trước; sửa readiness retry rồi triển khai lại thành công. Không thay agent version/contract bất biến hoặc xóa lịch sử phiếu. Cấu hình model lưu trong một agent/session có thể vẫn ghi tên cũ; policy tại runtime quyết định model thực gọi. Usage cũ của model khác vẫn là lịch sử đối soát.

## Phần người dùng cần nghiệm thu

Mở lại tên miền và nhấn **Ctrl+Shift+R một lần** để tab cũ nạp JavaScript mới. Sau đó thử ticket mới: cư dân gửi bổ sung, BQL @mention hỏi nội bộ, agent tra tool/phản biện, dispatch, nhân viên xử lý, cư dân xác nhận rồi đóng. Kiểm tra tin đến không cần reload, trao đổi BQL không gửi nhầm cư dân và không tạo dispatch trùng.

Chưa kết luận tổng token/chi phí một case, chất lượng xử lý qua model thật hoặc toàn bộ E2E đã đạt. Context được thu gọn trong đường xử lý đã kiểm tra; nếu chính policy/tool schema hoặc dữ liệu bắt buộc đã vượt ngân sách, hệ thống vẫn cần báo giới hạn thay vì bỏ bằng chứng. Báo cáo này xác nhận phạm vi các bug session/UI/chi phí nêu trên, không thay thế nghiệm thu toàn bộ P0/P1/P2.
