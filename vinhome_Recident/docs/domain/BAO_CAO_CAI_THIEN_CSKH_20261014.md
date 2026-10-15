# Kết quả cải thiện Reception CSKH — 14/10/2026

## Kết quả chính

Đã triển khai source `334978ffe2adbe4616dddb2fdc127998fba7dea8` trên VPS103.238.235.156, nhánh `dev_Vinhome`, dự án chính. Website: https://vinhome-platform.duckdns.org/.

Câu “Các dịch vụ bên trong cư dân là gì” trước đây chỉ tìm ra nội quy giữ xe; bản mới tìm đúng “Dịch vụ cư dân Sapphire đang dùng” ở vị trí đầu, cả có dấu lẫn không dấu. Reception đã trả lời giới thiệu được dịch vụ và khả năng hỗ trợ; câu hỏi tiện ích/gym có thông tin cụ thể cùng nhãn nguồn tham khảo. Không tự mở rộng thành trợ lý du lịch toàn Hà Nội.

Kế hoạch: [KE_HOACH_CAI_THIEN_CSKH_20261014.md](KE_HOACH_CAI_THIEN_CSKH_20261014.md).

## Thay đổi đã hoàn thành

1. Chuẩn hóa phần từ khóa bằng cách bỏ từ đệm hội thoại; vẫn giữ nguyên câu hỏi cho embeddings và giữ nguyên ngưỡng lọc/tenant/audience/nơi ở. Khi embeddings gặp lỗi, tìm theo từ vẫn hoạt động.
2. Bật cấu hình `EMBEDDING_API_KEY` độc lập bằng key OpenAI chủ dự án đã cung cấp. Chat vẫn dùng `gpt-5.6-luna` và endpoint OpenAI trực tiếp; cấu hình chat/key dùng chung được giữ nguyên.
3. Giữ `text-embedding-3-large`,1536 chiều. Đối chiếu toàn bộ648 vector và đầu vào với bộ export đóng gói: khớp; exporter dùng cùng model/dimensions. Hai mẫu gọi embeddings thực tế trả200, cosine với vector cũ khoảng0.998856 và0.999975, phù hợp bộ hiện có nhưng không được mô tả là trùng bit với kết quả mới. Không đổi model/index hoặc tạo lại dữ liệu tri thức.
4. Bổ sung `provenance` trong kết quả knowledge và MCP: trạng thái, nguồn, mã văn bản, thời gian hiệu lực, người/ngày xác nhận và lý do thiếu bằng chứng. Hồ sơ duyệt/nguồn/hiệu lực không đủ được trả là reference, kể cả cờ unverified=false. Ngày hiệu lực tính theo múi giờ Việt Nam.
5. Reception giới thiệu chức năng từ context hệ thống và đúng nhóm đang bật. Tên hiển thị được chuẩn hóa thành Kỹ thuật/An ninh; dữ liệu catalog trong DB chưa bị tự đổi hoặc thêm nhóm không có route/nguồn lực.
6. Prompt phân biệt câu hỏi thông tin với yêu cầu thực hiện dịch vụ; không gán booking/thẻ/công nợ vào kỹ thuật hoặc an ninh để tạo được ticket. Khi thiếu nguồn, thử một truy vấn ngắn đúng chủ đề rồi hỏi rõ mục còn thiếu/hướng dẫn bước tiếp theo.
7. Câu trả lời dùng tài liệu reference có nhãn nguồn tham khảo và yêu cầu xác nhận thông tin hiện hành. Các lần tìm trong một lượt dùng số tham chiếu riêng, không ghi đè nguồn cũ.
8. Giữ5 công cụ Reception,7 công cụ MCP platform. MCP knowledge cũng mang provenance. Không có BQL duyệt yêu cầu đầu vào hoặc hàng đợi BQL mới.
9. Bổ sung regression knowledge và job CI offline CSKH/adapter; hướng dẫn operator nạp metadata duyệt thật tại [NAP_DU_LIEU.md](NAP_DU_LIEU.md).

OpenAI hỗ trợ tham số dimensions cho model embedding thế hệ3; cấu hình1536 ở đây theo schema hiện hữu của dự án: [tài liệu chính thức](https://developers.openai.com/api/docs/guides/embeddings).

## Kiểm chứng

| Nhóm | Kết quả | Giới hạn/phạm vi |
|---|---|---|
| API/PostgreSQL/MCP | 26 passed,45.69 giây | Knowledge scope/RLS, fallback và semantic bằng embedding giả, provenance, MCP grants/CAS và7-tool contract |
| Reception adapter/CSKH | 11 passed,2.02 giây | HTTP/model giả; giới thiệu chức năng, provenance, rank sau retry và Luna tool compatibility |
| Embeddings thực tế |200;1536 chiều | Kiểm quyền key/model với mẫu tài liệu, không dùng thông tin riêng của cư dân |
| Retrieval trên VPS |4/4 lời gọi embeddings thành công | Câu dịch vụ có dấu/không dấu đứng đầu đúng tài liệu; gym đúng tài liệu; giá vàng trả0 hit |
| Chat CSKH qua HTTPS |5/5 tình huống đạt | Ngoài phạm vi, dịch vụ, khả năng hỗ trợ, gym Sapphire, tổng quan tiện ích; dùng account test riêng |
| Auth/public routes/MCP | Đạt | Root/login/forgot-password/operations/ready200; HTTP308 sang HTTPS; login/session/logout Secure;7 tool, outputSchema, bootstrap không gọi nghiệp vụ; SSH tunnel cũ hoạt động |

Hai regression được chạy trong container/PostgreSQL test riêng, không gọi provider thật. Các kiểm tra thật chỉ thuộc CSKH/embeddings đã được yêu cầu trong đợt này; không chạy full Agent/evals/specialists hoặc luồng giao việc hiện trường. Các câu hỏi CSKH không tạo hoặc sửa ticket của account test.

Trước sửa, test câu truy vấn tự nhiên chọn sai tài liệu và chưa có provenance; sau sửa đạt. Test tìm lại trong cùng lượt ban đầu tái hiện rank1 bị ghi đè; sau sửa nguồn cũ/mới được giữ riêng.

## Docker và dữ liệu

- API: `vinhomes-domain-api:cskh-20261014-334978ff`.
- API image ID: `sha256:4992cf9d2ecb7f81f31a96c5919efefe4ac96b27a847088018591906491a5272`.
- Reception: `vinhomes-domain-reception:cskh-20261014-334978ff`.
- Reception image ID: `sha256:e78ca96ad9e70446061575a83243227b8ca0d895e7317a43ee04bc9834636bb7`.
- API/Reception healthy; scheduler/platform-sync chạy cùng image API mới. Không có migration DB mới. Sourcehash5 file chức năng trong container khớp source commit.
- Gateway, frontend, PostgreSQL, MinIO và backup không bị recreate. Served frontend entrypoint vẫn khớp bytes container.
- Backup domain và PostgreSQL custom dump được lưu trước release. Env riêng, manifest image/sourcehash và đường rollback nằm trong `/opt/vinhomes/releases/cskh-20261014-334978ff/` với thư mục private.
- Cấu hình deploy trên máy phát triển đã đồng bộ tags/embedding setting, các secret vẫn ignored.

| Dữ liệu | Trước | Sau deploy |
|---|---:|---:|
| users |721|721|
| accounts |16|16|
| tenant_memberships |721|721|
| unit_residents |690|690|
| tickets |939|939|
| work_orders |677|677|
| files |33|33|
| knowledge documents |164|164|
| knowledge chunks |648|648|

Các lượt nghiệm thu tạo hội thoại/tin nhắn test và session đăng nhập theo nghiệp vụ; bảng trên là các số lượng nghiệp vụ đã đối chiếu, không phải tuyên bố mọi byte DB bất biến.

## Dữ liệu chính thức và việc tiếp theo

- Kho vẫn có115 tài liệu cư dân/279 đoạn và49 tài liệu nhân viên/369 đoạn;21 tài liệu cư dân bật cờ chưa xác minh. Cờ cũ không được sửa để giả lập phê duyệt. Bản mới phân loại độ tin cậy khi trả kết quả.
- Metadata cư dân hiện có101/115 tài liệu thiếu trường nguồn,112/115 thiếu ngày hiệu lực và109/115 thiếu mã văn bản. Cần chủ dự án/BQL cung cấp văn bản và xác nhận thật; hệ thống đã có cách nạp review metadata, nhưng bản này không tự tạo bằng chứng duyệt.
- Danh mục yêu cầu đang bật vẫn2 nhóm. Muốn mở thêm vệ sinh, tiện ích, thẻ, khách, công nợ… phải chốt nhóm việc, route, quyền, nhân sự/công cụ và dữ liệu tương ứng; không chỉ thêm một tên dịch vụ vào prompt.
- Tư vấn ngoài khu ở/toàn Hà Nội chưa mở. Có thể bổ sung sau khi chốt phạm vi và nguồn nội dung.
- Outbound bridge platform vẫn tắt; cần endpoint/version và adapter grant theo workflow của phía platform trước khi nghiệm thu ticket→session thật. Đợt này không tự sửa platform.

Evidence có credential/account/nội dung test được lưu tại folder audit ignored, không vào Git. Tài liệu kế hoạch, code, test và hướng dẫn được commit; các chỉnh sửa riêng bên platform và Caddyfile của người dùng được giữ nguyên ngoài commit.
