# Quota ảnh trong chế độ Vin — gate trước pilot

Ngày 18/10/2026. Owner: Người 1 (upload, quyền, provider/quota), Người 2 (chat/Builder/runtime dùng cùng trang hiện có).

## Trạng thái hiện tại

- C03 chỉ có bound cho text. `_model_guard.text_payload` chặn image/audio/file; chưa thể nghiệm thu chat phân tích ảnh khi bật Vin. Không bỏ kiểm tra này chỉ để UI gửi được ảnh.
- Domain đã có kiểm tra ảnh sự cố và storage chuẩn; adapter khách hàng dùng photo ID thuộc chính hồ sơ. Ảnh nghiệp vụ không bắt buộc đưa vào model: agent có thể gửi hồ sơ cho staff theo mô tả của khách, đọc trạng thái và ảnh kết quả qua API có quyền.
- Đây là phương án triển khai tiếp theo, **chưa phải vision adapter đã chạy**. Gate pilot có phân tích ảnh còn PENDING; không dùng key thật để test khi chưa được chủ dự án cho phép riêng.

## Hai luồng phải hoàn tất

1. **Đính kèm ảnh hồ sơ:** tái dùng upload/scan của Domain. Thêm proxy upload Platform có streaming limit, verified link/residence, idempotency; trả photo ID an toàn, không bearer URL. Khi tạo request, Domain xác nhận từng photo ID thuộc cư dân/căn hộ và chưa gắn hồ sơ khác. Luồng này không tiêu model quota. Giữ staff nhận/xử lý/hoàn tất tại Domain.
2. **Phân tích ảnh bằng model:** chỉ mở cho model/profile được admin duyệt trong catalog. Mọi chat, Leader/worker, eval, lịch/kênh dùng cùng gateway, không tạo SDK riêng hoặc endpoint fallback.

## Bound và policy đề xuất

`VisionQuotaProfile` gồm version, provider/endpoint/model chính xác, environment, thuật toán bound đã kiểm chứng, detail được phép, trần số ảnh/kích thước/decoded pixels/tổng bytes và ngày hiệu lực. Admin công bố profile; người dùng không nhập số token/URL/provider để tự đổi bound.

Token ảnh phụ thuộc model và cách xử lý ảnh; không lấy số ký tự base64 làm token ảnh và không dùng một hằng số cho mọi model. Đối chiếu profile với [tài liệu vision chính thức](https://developers.openai.com/api/docs/guides/images-vision) và [công cụ tính input ảnh](https://developers.openai.com/api/docs/guides/image-cost-calculator); lưu nguồn và version khi duyệt.

Đề xuất giới hạn pilot ban đầu (chưa phải chính sách đã phê duyệt): tối đa 4 ảnh/request, 10 MiB/ảnh, 20 triệu decoded pixels/ảnh; chuẩn hóa phía server thành JPEG/PNG/WebP tĩnh, bỏ metadata, phát hiện file giả và decompression bomb. Giá trị này phải phù hợp cả Domain lẫn provider đang được chọn; server dùng trần nhỏ hơn.

Gateway resolve attachment ID đúng user/tenant/case, kiểm lại quyền tại lúc chạy. Chỉ nhận byte handle do server cấp; không fetch URL tùy ý. Pin checksum, kích thước ảnh sau chuẩn hóa và phiên bản profile vào manifest. Bound phải tính **toàn bộ ảnh thực sự gửi sau history/tool/RAG**, gồm ảnh lặp lại trong ngữ cảnh.

Reservation = text bound + tổng image bound theo profile + protocol margin + output cap. Tất cả tính vào quota token ngày/tháng và pool hiện có; bổ sung daily image count/bytes/rate limit để chống spam. Thiếu profile hoặc bound không tin cậy: trả `VISION_QUOTA_PROFILE_REQUIRED` trước SDK, giữ ảnh trong hồ sơ và cho nhập mô tả bằng text.

Sau provider trả usage, settle tổng token thực tế, không cộng token ảnh lần hai nếu usage đã gộp input. Lỗi 4xx/before-send settle 0; timeout/mất usage/cancel sau dispatch giữ token pending và trả concurrency slot theo C03. Usage vượt bound ghi nợ, chặn attempt tiếp và yêu cầu sửa profile; không hứa hard cap tiền chỉ từ estimator.

## Phân công và bằng chứng cần có

| Owner | Phần việc | Nghiệm thu bắt buộc |
| --- | --- | --- |
| Người 1 | Proxy upload, ACL/checksum/metadata; versioned profile + migration; adapter Chat/Responses và reserve/settle | Fake images/SDK, wrong owner, revoked link, file giả/quá hạn mức, history có nhiều ảnh, 4xx/cancel/unknown usage; 0 call khi không có quota/profile |
| Người 2 | Nối attachment hiện có vào photo ID/manifest; cùng UI chat; hiện lỗi/quota/nhãn eval đúng | Browser fixture upload → chat → hồ sơ → staff → timeline; không đưa raw URL/config vào prompt |
| Cả hai | Candidate tích hợp trên sandbox riêng | Schema/profile đúng model thật, receipt usage và business UAT khi có ủy quyền test; trước đó chỉ ghi offline đạt |

Không đưa OCR/vision qua tool ngoài gateway để né quota. Tạo ảnh mới, video, audio/TTS nằm ngoài adapter ảnh đầu vào này và tiếp tục bị chặn cho tới có bound riêng. Không thay staff UI, không gửi ticket ảnh vào route/Leader BQL.
