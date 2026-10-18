# Platform local cho chủ dự án tự dùng model

Địa chỉ: `http://127.0.0.1:18104`. Cấu hình S18 thay provider scripted bằng provider đã được chủ dự án chỉ định tại `awp-develop2-app-1`; không thay stack nguồn. App hiện dùng `vin-n2-platform-owner:bfe38022`, web giữ `vin-n2-web-rc:9876d94e`, Domain giữ candidate N1 `vin-n1-6ef348ce-rc-20261018`. Đây là môi trường local với dữ liệu nghiệp vụ tổng hợp; chưa deploy VPS.

## Model và tài nguyên đã cấp

- Chat/Leader/team/Builder/eval/lịch/kênh đều đi qua runtime model policy **`gpt-6-luna`**. `WORKFORCE_MODEL_NAME` và `WORKFORCE_LEADER_MODEL_NAME` cùng giá trị; quota/catalog cũng cho phép model này. Phiên Leader đã lưu được cập nhật bằng API session, không còn nhãn `scripted-vin` trong cấu hình của phiên.
- Endpoint **`https://api.openai.com/v1`**, server key được chuyển nội bộ từ container nguồn đã được chủ dự án cho phép. Không đưa key vào chat, Git, catalog hoặc record của khách. Không gọi `/models` upstream, chat, Responses hay embedding upstream để xác minh key/model. Chỉ chủ dự án tự gửi prompt; chưa có chứng nhận chất lượng hoặc khả năng provider chấp nhận model/key từ lượt cấu hình này.
- Provider, MCP, skill khách được xem/chọn/dùng, không sửa. MCP **Vinhomes · Dịch vụ của bạn** có 8 tool được Domain ủy quyền cho cư dân; không có tool BQL hoặc phê duyệt/đóng ticket thay cư dân. Header discovery được xóa khỏi record trước khi cấp catalog; mỗi lần chạy lấy grant riêng theo owner/link/case/ticket. Không trả bearer cho model/browser. `ticket_ids` từ receipt CustomerService giúp Leader giao đúng ID cho worker.
- Ba skill đã được admin duyệt: `vin-service-intake`, `vin-service-progress`, `platform-source-citations`. Chọn trong Builder để gắn vào agent; không tự phát hành business agent bỏ qua eval.
- Một kho **Hướng dẫn sử dụng Platform**, tìm kiếm lexical, tài liệu có nguồn `platform://user-guide/2026-10-18`, đã review. Tìm `Platform` trả một kết quả. Đây là hướng dẫn ứng dụng, **chưa phải nội quy/biểu phí/SOP Vin**; cần tài liệu nghiệp vụ thật đúng audience trước khi trả lời dựa trên chúng.
- Chat model không phải embedding model. Knowledge có thể chọn **`text-embedding-3-small`** với cùng provider, hạn mức embedding 10000 token/ngày; không gọi embedding thật để test. Kho hướng dẫn lexical hiện tại không dùng embedding.
- Hạn mức role tại local: 200000 token/ngày và tháng, max output 4096, concurrency 2, storage 100 MB, file 10 MB. Dữ liệu usage 420 token cũ là lượt scripted S16, không chứng minh call thật. Token thật chỉ phát sinh khi chủ dự án sử dụng; không tự retry vượt quota.

## Phần chưa thể tuyên bố sẵn sàng toàn bộ

- Lịch: reader/UI và worker C09 đã kiểm bằng provider giả, danh sách hiện chưa có lịch. Chủ dự án tạo agent đã publish rồi tạo lịch; khi enable lịch, đó là model thật chạy theo lựa chọn của chủ dự án. Không tạo lịch trả phí tự chạy để test.
- Discord: trang/API mở được nhưng **chưa có OAuth Client ID/secret/redirect URI**, chưa xác minh Discord ID và chưa có bot cá nhân. Không lấy bot BQL dùng chung. Cần operator cấu hình ứng dụng OAuth rồi người dùng tự xác minh/chọn bot.
- Eval text-only có model policy mới. Eval MCP Domain cần **provider/link/MCP sandbox C08 riêng**; profile sandbox chưa được provision tại local owner-use này. Không bật fixture trong Domain đang phục vụ hoặc dùng ticket thật để thay sandbox. Test C08 positive trên fixture có bằng chứng ở suite strict; không đồng nhất với cấu hình sandbox đã sẵn cho owner.
- Agent tự phân công staff bằng model thật, nội dung Vin thật/indexing, ảnh đầu vào/vision và UAT nghiệp vụ chưa chứng nhận. Consumer grant MCP đã kiểm read thật trên ticket tổng hợp; không suy agent đã tự dispatch từ lần đọc đó.
- Trang provider vẫn liệt kê các model card SDK; đây là catalog khả năng của SDK. Model thực thi bị runtime policy cố định gpt-6-luna và quota/catalog kiểm tại outbound boundary; không xem mọi card là quyền chạy mọi model. Yêu cầu producer N1 bổ sung projection model card theo entitlement nếu cần đổi danh sách API, giữ owner file.

## Cấu hình lại và bằng chứng

Hai script thuộc N2, chạy từ `P=platform_VP/agentscope`. Không chạy script RC fixture trên thư mục owner-use hiện tại. `configure_vin_owner.py` chỉ cho stack mang label namespace fixture N2, từ chối khi có job chưa terminal, giữ workspace, env trong `.artifacts` ignored và container cũ để rollback. Chỉ chạy một lần; lần sau cần review state/container trước khi thay.

```powershell
.venv/Scripts/python.exe scripts/workforce/configure_vin_owner.py --fixture .artifacts/n2-s16-staging-r4 --source-container awp-develop2-app-1 --image vin-n2-platform-owner:bfe38022 --model gpt-6-luna
.venv/Scripts/python.exe scripts/workforce/provision_vin_owner_resources.py --fixture .artifacts/n2-s16-staging-r4 --model gpt-6-luna --embedding-model text-embedding-3-small
```

Provision script dùng admin APIs cho policy/catalog/grants/skill review/KB review và session API của chính tài khoản fixture; MCP snapshot dùng public storage adapter. Chạy lại không tạo thêm record MCP/skill/KB/document; policy/catalog có revision mới và audit. Source API/authority N1 không bị sửa.

Evidence local: `P/.artifacts/n2-s16-staging-r4/owner-use/configuration.json`, `owner-resources.json`, `owner-readiness.json`, `owner-*.png`; log `n2-s18-{contracts-receipt,runtime,domain-mcp-final,owner-readiness-final2}.log`. Manifest đã bỏ bí mật: [S18 owner use](evidence/n2-s18-owner-use-20261018.json). Test strict 98 PASS/0 SKIP; generic runtime 513 PASS/27 SKIP; MCP Domain read 1 PASS; API/6 trang tài nguyên mở được, 0 JS error. Browser chặn 5 request ảnh icon công khai; không gửi request model từ browser test. Đã dừng container model scripted không còn dùng.

Container cũ `vin-n1-r04-e2e-8a0ba5ce-platform-rc-before-owner` được giữ stopped để rollback cấu hình; nó dùng fixture provider cũ đã dừng. Rollback phải phối hợp bật lại fixture model, đổi app name về địa chỉ nginx đang proxy và kiểm flags/DB; không chạy hai app cùng cổng trong namespace. Dọn toàn bộ local theo ownership state bằng `check_vin_rc.py --output .artifacts/n2-s16-staging-r4 --cleanup-only` khi không còn cần dữ liệu. Không đưa `owner-use/runtime.env` vào archive hoặc commit.
