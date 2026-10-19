# Thông số agent và context

Cấu hình dưới đây được đọc trực tiếp từ container Platform trên VPS ngày 19/10/2026. Đây là cấu hình runtime; giá trị mặc định trong mã nguồn có thể khác. Không thay đổi giới hạn khi triển khai bản sửa team cá nhân.

## Context và memory

| Thành phần | Giá trị đang dùng | Phạm vi và cách xử lý |
| --- | --- | --- |
| Gói context chung | Tối đa 48.000 token | Gói nạp cho một lần suy luận; gồm trạng thái nhiệm vụ, ràng buộc, kết quả và trao đổi có nguồn. Không đồng nghĩa với toàn bộ cửa sổ model. |
| Lịch sử chung | Ngân sách 4.000 token | Tóm tắt ở ngưỡng 80% ngân sách lịch sử. Giữ phần gần nhất và liên kết nguồn để đọc lại. |
| Tóm tắt chung | Tối đa 40% ngân sách lịch sử; tối đa 2 lần thử | Bản tóm tắt không thay thế dữ liệu trạng thái có thẩm quyền. Lỗi tóm tắt không được coi là thành công. |
| Lịch sử riêng | Trần kích hoạt nén 8.000 token | Runtime chọn ngưỡng nhỏ hơn giữa cấu hình riêng, trần token và phần còn lại của cửa sổ model. Mỗi agent/session có trạng thái riêng. |
| Dự phòng đầu ra | 10% cửa sổ model | Preflight đo cả system prompt, tool schema, lịch sử, memory recall và context chung; chừa thêm 256 token. |
| Khi nén riêng thất bại | Giữ context, báo lỗi | Team runtime tắt cơ chế tự bỏ tin nhắn cũ để tiếp tục bằng dữ liệu thiếu. |
| Memory dài hạn | Theo tài khoản và agent | Chỉ recall mục còn hiệu lực, có nguồn đã kiểm chứng; tối đa 5 mục và 2.400 ký tự mỗi lượt theo mặc định của dịch vụ. |
| Hạn memory | Fact 14 ngày; preference 30 ngày; lesson 90 ngày | Không dùng memory làm bằng chứng cho giá/khả dụng hiện tại hoặc quyền thực hiện giao dịch. |

Các agent đọc context chung để biết mục tiêu, trạng thái, kết quả và câu hỏi của nhau. Lịch sử suy luận riêng không được đưa nguyên văn cho agent khác hoặc khách hàng. Nguồn gốc sự kiện, revision và dữ liệu gốc được giữ để tiếp tục sau khi nén hoặc khởi động lại.

Memory recall đã có; việc công bố kết quả trực tiếp của team cá nhân không tự động biến mọi báo cáo thành bài học đã được kiểm chứng. Luồng ghi memory dài hạn vẫn yêu cầu nguồn và trạng thái xác minh/chấp nhận phù hợp.

## Model và vòng chạy

| Thông số | Cấu hình đang dùng |
| --- | --- |
| Chính sách model triển khai | `WORKFORCE_MODEL_NAME=gpt-6-luna` |
| Trần đầu ra | `WORKFORCE_MAX_OUTPUT_TOKENS=16384`; cấu hình model thấp hơn vẫn được giữ |
| Reasoning effort | Leader/Builder/Judge: `medium`; agent nghiệp vụ: `low`, áp dụng cho model reasoning dùng Responses API được hỗ trợ |
| Tác vụ nền | `flex`, có cơ chế thử lại tier tiêu chuẩn khi tier này không khả dụng |
| ReAct iterations | Lấy từ `agent.data.react_config.max_iters`; mặc định schema là 50, không phải khẳng định mọi agent hiện dùng 50 |
| Retry tầng Agent | Mặc định 0 lần gọi lại; fallback chỉ dùng khi đã cấu hình. Adapter/provider có chính sách riêng. |

Model reasoning theo chính sách triển khai bỏ `temperature`/`top_p` khi không tương thích. Không tự tăng temperature, retry, số vòng hay ngân sách để che lỗi logic.

## Giới hạn cộng tác

Các giới hạn được theo dõi theo nhánh session/nhiệm vụ và phiên bản yêu cầu khách hàng, không phải ngân sách cộng chung cho mọi thành viên của team.

| Biến cấu hình | Giá trị VPS |
| --- | --- |
| `COLLABORATION_MAX_EXCHANGES` | 60 |
| `COLLABORATION_MAX_MODEL_CALLS` | 40 |
| `COLLABORATION_MAX_TOKENS` | 1.000.000 token đo được |
| `COLLABORATION_MAX_ACTIVE_SECONDS` | 600 giây chạy chủ động |
| `COLLABORATION_MAX_VERIFICATIONS` | 2 |

Thời gian chờ khách hàng, ngủ hoặc kết nối lại không bị tính thành thời gian xử lý chủ động. Hết giới hạn phải giữ kết quả từng phần và báo công việc chưa hoàn tất. Lượt đọc thêm nguồn phục vụ phân trang được theo dõi riêng với giới hạn gọi model để không cắt đứt việc đọc bằng chứng hợp lệ.

## Chỉ số quan sát

- Giao diện có trạng thái, nhiệm vụ, chờ agent nào, lý do bị chặn và mục **Mức sử dụng từng agent**: số lần gọi, token vào/ra, tỷ lệ token cache.
- API phòng trả thêm tên model, kích thước gói context gần nhất/cao nhất và ngân sách gói context.
- Backend giữ số lần nén/thất bại, token tóm tắt vào/ra, token prompt/tool schema/lịch sử, số lần vượt ngân sách và bộ đếm từng nhánh cộng tác. Chưa hiển thị toàn bộ các chỉ số này trên giao diện.
- Token do provider trả về và token đo để bảo vệ cửa sổ context là hai nhóm số liệu khác nhau. Không suy ra chi phí tiền chính xác từ số token nếu chưa có bảng giá và dữ liệu billing tương ứng.

## Kiểm chứng

Giá trị runtime được thu thập bằng allowlist biến cấu hình, không xuất key/token. Kiểm thử team/context/memory dùng model giả và dữ liệu offline. Health check và các bài kiểm thử này không thay thế nghiệm thu bằng yêu cầu thực tế trên model/provider; chưa dùng key thật cho bước nghiệm thu đó.

Nguồn mã: `_shared_context.py`, `_service/_chat.py`, `_service/_model.py`, `middleware/_shared_context_middleware.py`, `_agent_memory.py`, `storage/_model/_team_context.py`, `_router/_workforce_console.py` và `components/panel/RoomActivity.tsx`.
