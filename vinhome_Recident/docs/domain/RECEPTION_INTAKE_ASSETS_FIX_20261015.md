# Sửa Reception hỏi vòng và bàn giao ảnh cư dân — 15/10/2026

## Phạm vi

Hai lỗi phía Domain được báo: lễ tân hỏi lại vị trí/thiết bị/sự cố khi một tin có hai hạng mục; bridge chưa gửi ảnh cư dân qua Asset API mới. Sửa trên `dev_Vinhome`, không thay source Platform hoặc cấu hình provider. Chưa có đoạn chat lỗi nguyên văn, nên ca tái hiện dùng hội thoại giả lập cùng nhóm Kỹ thuật: “Nhà tôi rò nước và đèn chập chờn” → “Cả hai ở phòng bếp” → “Chân vòi lavabo, bóng đèn trên bàn bếp”.

## Nguyên nhân và thay đổi

### Intake

Mỗi lần kiểm tra trước đây chỉ có các claim model gửi trong lượt đó. Một câu trả lời ngắn có thể làm rơi symptom/area đã kiểm tra, khiến backend quay lại hỏi “sự cố gì”.

- Lưu `intake_facts` và `intake_kind` đã kiểm chứng trên metadata tin cư dân. Nội dung text và file IDs của cư dân vẫn được giữ nguyên.
- Mỗi lượt hợp nhất chi tiết cũ/mới theo key; chỉ giữ giá trị có trong tin được trích dẫn. Phủ định/correction ở tin sau loại bỏ chi tiết cũ tương ứng; chi tiết bịa không được ghi nhận.
- Context Reception có `pending_intake` với chi tiết đã ghi nhận và phần đang thiếu. Prompt hướng dẫn tiếp tục yêu cầu, chỉ hỏi phần còn thiếu; giữ nguyên toàn bộ tin có nhiều hạng mục cùng nhóm.
- Giới hạn intake đến đúng message đang xử lý; không lấy chi tiết/ảnh của tin gửi sau. Intake mới không mang dữ kiện của yêu cầu đã tạo trước đó sang; cập nhật draft dùng cùng ranh giới message. Có khóa transaction theo chat cho các lần ghi intake đồng thời.
- Bỏ sót một field khi gọi lại intake không xóa field đã xác thực. Backend vẫn giữ quy tắc hỏi tối đa hai lần về item rồi chuyển kiểm tra thủ công; lời “ok” không tự thành dữ kiện.

Một chat vẫn có một yêu cầu đang mở. Hai hạng mục cùng nhóm được giữ trong mô tả gốc của yêu cầu; thay đổi này không tự tạo hai ticket hoặc xác nhận đã xử lý cả hai. Chất lượng hội thoại của model thật cần người dùng thử riêng.

### Ảnh cư dân

Worker trước đây gửi `message={type,text}` và số ảnh. Hiện đi đúng contract Asset API 1.4:

1. Snapshot ảnh cư dân đã gắn với ticket vào command start/reply.
2. Kiểm tenant, ticket, uploader, purpose `issue`, file/object ready, scan sạch, storage và size/MIME; đọc bytes và đối chiếu SHA-256.
3. Xin `POST /workforce/v1/partner/assets/upload-sessions` bằng key backend, với route/user/ticket/conversation đúng của link.
4. PUT bytes tới URL ký với các header được cấp; client riêng không mang ApiKey/cookie và không theo redirect.
5. Finalize `/partner/assets/{asset_id}/complete`; phải trả đúng asset và trạng thái `active`.
6. Commit mapping và `asset_attachments` trong command trước khi gửi request. `message.attachments` chỉ chứa `asset_id`, không URL/base64/file cá nhân khác.

Migration **0023_platform_resident_assets.sql** tạo bảng mapping với tenant RLS bật và FORCE, FK ticket/file. Chỉ lưu asset ID/hash nguồn/hash đích; không lưu URL ký hoặc credential. Retry sau khi mất phản hồi request giữ nguyên attachment IDs/body. Upload/finalize lỗi giữ request để xử lý lỗi/retry, không gửi text-only rồi ghi thành công.

Giới hạn 10 ảnh/lệnh Platform; nhiều ảnh được chia các command cùng ticket. Ảnh gửi bổ sung khi ticket đang chờ nghiệm thu cũng đi cùng luồng. Một lỗi khác được phát hiện và sửa: commit draft chat dùng giới hạn 3 ảnh của form làm handoff nhiều ảnh lỗi 500; kiểu nội bộ `ReceptionTicketCreate` nay theo giới hạn 100 ảnh của draft, form cư dân vẫn giữ giới hạn riêng.

Upload session lỗi trước finalize có thể để lại session/object chưa dùng bên Platform; chỉ tham chiếu đã active mới được dùng trong request. Lượt này không thêm provider upload cho ảnh riêng của staff hoặc tool MCP nhận bytes ảnh. Reception vẫn không tự đọc/suy đoán ảnh; Platform nhận ảnh và quyết định cách xử lý theo khả năng model/route của mình.

## Nghiệm thu

**145 kiểm thử đạt:** 130 API/PostgreSQL (intake, follow-up, bridge, Asset API, MCP v2, schema) và 15 Reception với model/scripted backend. Không gọi OpenAI/Agent thật, embeddings hoặc nhà cung cấp ngoài. PostgreSQL test và volume riêng đã được gỡ.

- Hai hạng mục qua ba câu ngắn giữ symptom/area/item, nguyên văn cả hai hạng mục và ảnh; không quay lại missing=symptom.
- Context/claim không đọc tin tương lai; phủ định loại chi tiết cũ, chi tiết bịa bị từ chối.
- Ảnh ban đầu và tin chỉ có ảnh: đúng bytes đã xác minh → upload → finalize → request có attachments.
- Mất acknowledgement: hai lần gửi cùng request/body, chỉ một asset đã upload.
- Storage lỗi: chưa gửi request text-only; sau retry có attachments.
- Ảnh ticket khác: từ chối trước upload/request.
- 11 ảnh: gửi đủ 10 + 1 qua hai command, không bỏ ảnh.
- Toàn bộ hồi quy bridge/MCP/schema trong bộ đã chạy đạt. Fixture ảnh cũng được sửa để mọi đường upload trong kiểm thử dùng cùng thư mục tạm.

Ruff đạt trên module/test Asset mới; Python thay đổi qua syntax/import và kiểm thử. Cảnh báo duy nhất của bộ API là Starlette TestClient deprecation.

## Docker và triển khai

Đã build offline từ image Domain tin cậy đang có, không đổi dependencies Linux:

- Tag: `fix-reception-assets-20261015-24b13b5847f0`.
- API: `sha256:a9a2818df77cf3fedcd5b9cdc6528e91aeed27f086b7cf646847aa1d46ce7d47`.
- Reception: `sha256:e128cd7230e2ccab0f890ddc1ed0c608292f150847e69799aaac23e558ed775c`.
- Compile/pip check và API import smoke đạt, network bị tắt trong build/smoke. Log/manifest riêng: `E:\Vinhomes-Deploy\reception-assets-20261015`.

**Chưa recreate container hoặc cập nhật VPS trong lượt này.** Local đang chạy `dev-5b634502` với Compose từ `E:\AI-Workforce-Platform-vinhome-dev\vinhome_Recident\deploy\compose.yml`; mã sửa ở checkout `E:\AI-Workforce-Platform`. Cần xác định đúng URL/môi trường người dùng đang kiểm thử để cập nhật image mà giữ DB/cấu hình của môi trường đó.

Khi triển khai: sao lưu DB/cấu hình; migrate đầy đủ (bao gồm 0022 nếu chưa có) và áp lại runtime roles; đổi API/Reception image rồi recreate API/scheduler/platform-sync/Reception; giữ frontend, provider key, dữ liệu vận hành và cấu hình bridge. Nghiệm thu runtime source hash, health, login và một luồng ảnh trên hai backend thật khi Platform đã bật Asset API/storage. Kiểm thử transport giả không chứng minh đã nối môi trường Platform thật.
