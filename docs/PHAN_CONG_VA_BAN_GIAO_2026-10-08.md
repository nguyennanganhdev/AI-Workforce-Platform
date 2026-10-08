# Phân công, bàn giao và cách các team làm việc với nhau

Giai đoạn: 08/10 đến 22/10/2026. Buổi báo cáo cuối: thứ Năm 22/10, demo trực tiếp.

Thiết kế và lý do: [KE_HOACH_TAI_CAU_TRUC_PLATFORM_2026-10-08.md](KE_HOACH_TAI_CAU_TRUC_PLATFORM_2026-10-08.md). Dữ liệu: [KE_HOACH_DU_LIEU_2026-10-08.md](KE_HOACH_DU_LIEU_2026-10-08.md). Thuật ngữ nằm ở mục 3 của tài liệu thiết kế.

## 1. Cách đọc tài liệu này

- **Mọi người:** đọc mục 2 (lịch), mục 3 (hợp đồng) và mục 10 (cách làm việc).
- **Thành viên một team:** đọc thêm đúng mục của team mình (mục 4 đến 8).
- **Trưởng team:** đọc thêm mục 9 (điểm giao nhận) và mục 12 (bàn giao cuối).

Mỗi việc có một mã. Dùng mã đó trong tên nhánh, tiêu đề PR, tệp bàn giao và khi nhắn nhau.

| Tiền tố | Team | Lớp phụ trách |
|---|---|---|
| `DG` | Đông | Điều phối và hồ sơ vụ việc |
| `QG` | Quang | Tool, kiến thức, bộ nhớ, agent Kỹ thuật |
| `HG` | Hoàng | Tiếp nhận, luật kiểm nguồn, bộ đánh giá, số liệu chi phí, agent Vệ sinh và Báo cáo |
| `CN` | Chiến | Backend lõi, cơ sở dữ liệu, giao diện |
| `PH` | Phái | Ranh giới lõi, gói Vinhomes, kiểm thử đầu cuối, công cụ dữ liệu, xưởng agent, vận hành demo |
| `HD` | (hợp đồng) | Thỏa thuận dữ liệu giữa các team |

**Cách đọc bảng việc.** Mọi việc trong bảng của một team do team đó làm. Cột "Ai chờ kết quả" là team sẽ dùng thứ mình làm ra; khi xong, viết tệp bàn giao gửi họ (mục 11).

## 2. Lịch hai tuần

| Ngày | Việc chung | Mốc |
|---|---|---|
| Thứ Năm 08/10 | PM duyệt. Trưởng team đọc tài liệu, chia người. Chủ hợp đồng bắt đầu viết. | |
| Thứ Sáu 09/10 | Bảy hợp đồng có bản nháp kèm ví dụ. Team Chiến gộp `dev_TeamChien` vào `develop`; mỗi team tạo lại nhánh team từ `develop`. Môi trường tích hợp có địa chỉ. Package lõi rỗng được tạo. Kiểm tra ranh giới chạy trong CI. Gia hạn ca nhân viên. | |
| Thứ Bảy, Chủ nhật | Dự phòng. Chỉ làm khi PM yêu cầu. | |
| Thứ Hai 12/10 | Góp ý hợp đồng trước 12:00, chốt cuối ngày. Trước 12:00: các nhóm module kiến thức, bộ nhớ, tool, agent đã chuyển về lõi. Thế giới demo cố định. API hồ sơ, điểm nhận sự kiện và API ghi sổ chi phí có bản tối thiểu trên môi trường tích hợp. | **M0** |
| Thứ Ba 13/10 | Số nền và ngưỡng đề xuất gửi PM. Thư viện kiểm nguồn bản đầu. Agent Kỹ thuật và agent Vệ sinh trả đầu ra theo HD-1. Khung màn hình mới chạy trên một phiên đã ghi. | |
| Thứ Tư 14/10 | Trình diễn nội bộ lát cắt đầu tiên. PM chốt ngưỡng nghiệm thu. Dữ liệu đợt 1 đã nạp. Kiểm thử đầu cuối bắt đầu chạy hằng đêm. | **M1** |
| Thứ Năm 15/10 | API ký ức chạy thật. Rà soát chéo chạy lần đầu trên môi trường tích hợp. Sửa các bước hỏng trong kiểm thử đêm qua. | |
| Thứ Sáu 16/10 | Đủ tính năng. Dữ liệu đợt 2 đã nạp. Dừng chuyển module. Dừng nhận tính năng mới từ cuối ngày. | **M2** |
| Thứ Bảy, Chủ nhật | Dự phòng cho việc trễ, chỉ khi PM đồng ý. | |
| Thứ Hai 19/10 đến thứ Tư 21/10 | Đóng băng: chỉ sửa lỗi. Mỗi ngày hai lượt tập demo. Đo số sau. Không gộp code sau 12:00 ngày 21/10. | Đóng băng |
| Thứ Năm 22/10 | Demo trực tiếp. | Demo |

**M1 là gì.** Trên môi trường tích hợp: một phiên hai agent chạy thật, mỗi agent trả đầu ra có cấu trúc, các mục được ghi vào hồ sơ kèm nguồn, mục không nguồn bị hạ thành giả định, mỗi lần gọi model có bản ghi token, và màn hình mới hiện được hồ sơ cùng trạng thái agent.

**M2 là gì.** Thêm vào M1: rà soát chéo, hợp nhất có kiểm nguồn, ký ức cho vụ thứ hai, tóm tắt phiên, một danh mục tool, Vinhomes chạy như một gói với kiểm tra ranh giới xanh, màn hình hoàn chỉnh, xưởng agent, bộ đánh giá nhiều agent.

## 3. Bảy hợp đồng

Hợp đồng là thứ cho phép các team làm song song. Mỗi hợp đồng có **một chủ**. Chủ viết, các team dùng góp ý, PM phân xử khi không thống nhất.

Nơi đặt: `shared/contracts/v2/<mã>/`, gồm `README.md`, lược đồ JSON và ít nhất hai tệp ví dụ. Từ 09/10 các team viết code và test dựa trên các tệp ví dụ này, không chờ nhau. Nháp: 09/10. Chốt: 12/10.

| Mã | Nội dung | Chủ | Team dùng |
|---|---|---|---|
| HD-1 | Lượt agent: ngữ cảnh agent nhận và đầu ra agent trả (`findings`, `proposals`, `objections`, `questions`, `summary`) | Đông | Hoàng, Quang, Phái |
| HD-2 | Hồ sơ vụ việc: các loại mục, trường của một mục, cách trỏ nguồn, API ghi và đọc. Mỗi lần ghi mang một khóa do bên ghi cấp; gửi lại cùng khóa cùng nội dung trả về mục đã ghi. Mục "bước phương án" có số phiên bản phương án và số thứ tự bước. Kèm một ví dụ hồ sơ đã đóng đầy đủ | Đông | Chiến, Hoàng, Quang, Phái |
| HD-3 | Tool: bản khai một tool, dạng kết quả chung, mã lỗi, nhãn dữ liệu mẫu. Mã nguồn (`source_id`) do cổng gọi tool cấp, không do từng bộ tool tự cấp; mã của đoạn tài liệu phải giữ nguyên khi dựng lại môi trường | Quang | Đông, Chiến, Hoàng, Phái |
| HD-4 | Sự kiện sống cho giao diện: agent bắt đầu, đang gọi tool, có mục mới, mục bị chặn, xong; số liệu cập nhật. Đường đi: bộ điều phối gửi từng sự kiện tới API; API lưu vào bảng chỉ thêm và đẩy tới trình duyệt | Chiến | Đông (bên phát) |
| HD-5 | Sổ chi phí: một bản ghi cho mỗi lần gọi model; định nghĩa các số liệu của một vụ | Hoàng | Đông, Quang (bên ghi), Chiến (bên lưu) |
| HD-6 | Ranh giới lõi và gói: luật import, danh sách từ cấm trong lõi, định dạng `domain.yaml` và `tools/`. Ngoại lệ tới sau 22/10: tên biến `VINHOMES_*`, tên bảng `vh_*`, tên dịch vụ và tên package `vinhomes_api` không tính là vi phạm | Phái | Tất cả |
| HD-7 | Khuôn dữ liệu mẫu: định dạng tệp, trường bắt buộc, nhãn nguồn gốc | Phái | Tất cả |

**Đổi hợp đồng sau khi chốt:** chủ hợp đồng viết một tệp yêu cầu (mục 11), các trưởng team dùng hợp đồng đó đồng ý, PM duyệt. Không ai tự sửa lược đồ rồi báo sau.

## 4. Team Đông: điều phối và hồ sơ vụ việc

**Mục tiêu:** các agent trong một phiên đọc được kết luận của nhau, rà soát nhau, và mọi thứ họ nói đều thành mục có nguồn trong hồ sơ.

Vùng code: `agent-coordination/**`, trừ `src/agent_eval/**` (Team Hoàng giữ từ 09/10).

| Mã | Việc | Hạn | Ai chờ kết quả | Xong khi |
|---|---|---|---|---|
| DG-0 | Trên bản hiện tại, ghi ra log mỗi lần gọi model của Supervisor và của agent chuyên môn: mã vụ, vai trò, token vào, token ra | 09/10 | Hoàng (đo số nền) | Log của một phiên cho ra số token của từng lần gọi |
| DG-1 | Viết HD-1 và HD-2 kèm ví dụ. Ví dụ hồ sơ đã đóng dùng làm khuôn cho dữ liệu D-30 | Nháp 09/10, chốt 12/10 | Tất cả | Các team dùng đã góp ý; mỗi hợp đồng có hai ví dụ đầy đủ |
| DG-2 | Agent chuyên môn gọi model trực tiếp, trả đầu ra theo HD-1, gọi được tool. Sai lược đồ thì thử lại một lần rồi báo lỗi. Khi backend không trả cấu hình model cho agent thì báo lỗi rõ, **không tự rơi về OpenBot**. Nơi sửa: `src/vinhomes/registered_model.py`, `src/vinhomes/ports.py`, `src/vinhomes/runtime.py`, `src/agents/releases.py` | 14/10 | Hoàng, Chiến | Agent Kỹ thuật và agent Vệ sinh trả `findings[]` hợp lệ trên phiên thật khi không có dịch vụ OpenBot; mỗi lần gọi có bản ghi theo HD-5 |
| DG-3 | Bộ dựng ngữ cảnh sáu lớp. Danh bạ, ký ức và bản cô đọng hồ sơ được Supervisor đưa vào phòng trước khi chạy lượt; không gọi API bên trong `context_builder.build`. Thêm trường "pha" cho việc để bộ lọc biết lượt độc lập hay lượt rà soát. Nơi sửa: `src/groupchat/context_builder.py`, `src/groupchat/models.py`, `src/groupchat/ports.py`, `src/vinhomes/ports.py` | 14/10 | Không ai ngoài team | Test: agent B nhận danh bạ có agent A; ở pha độc lập không thấy mục của A; ở pha rà soát thì thấy |
| DG-4 | Ghi hồ sơ qua API của CN-2: kết quả tool và mục của agent sau khi qua thư viện HG-2. Dữ kiện của cư dân do Tiếp nhận ghi (HG-4a), bộ điều phối không ghi lại. Mỗi lần ghi mang khóa theo HD-2. Thêm `shared/python` vào ảnh Docker của bộ điều phối | 14/10 | Chiến, Hoàng | Phiên thật hai agent tạo mục trong hồ sơ; mục không nguồn thành giả định; chạy lại một lượt không tạo mục trùng |
| DG-5 | Gửi sự kiện sống tới điểm nhận của CN-1b theo HD-4 | 14/10 | Chiến | Màn hình CN-5 hiện trạng thái agent trong lúc phiên chạy |
| DG-6 | Pha rà soát chéo và hợp nhất có kiểm nguồn. Mỗi agent rà soát bằng một việc mới giao cho chính agent đó. Với mỗi bước phương án, Supervisor ghi một mục "bước phương án" vào hồ sơ kèm danh sách mục nguồn; dạng phương án gửi backend giữ nguyên. Luật từ chối bước chỉ dựa trên giả định. Nâng trần số lượt ngay trong việc này. Nơi sửa: `src/vinhomes/ports.py` (phần Supervisor: chỗ đang ép lập phương án khi mọi việc đã xong), `src/supervisor/turn_policy.py`, `models.py`, `service.py`, `planner.py`, `src/vinhomes/runtime.py` | 16/10 sáng | Hoàng (chạy bộ đánh giá), Chiến | Kịch bản demo sinh ít nhất một phản đối hoặc bổ sung; test: bước chỉ dựa trên giả định bị từ chối; mục giả định trong kịch bản hiện qua sự kiện "bị chặn" |
| DG-7 | Supervisor đọc hồ sơ và sổ việc thay cho toàn bộ trạng thái phiên; tóm tắt phiên dài | 16/10 | Hoàng (số liệu) | Token đầu vào mỗi quyết định của Supervisor giảm so với số nền, có số kèm theo |
| DG-8 | Nạp ký ức từ QG-6 vào ngữ cảnh; câu hỏi agent gửi agent qua hộp thư đã có | 16/10 | Không ai ngoài team | Vụ thứ hai của cùng căn hộ có mục ký ức trỏ về hồ sơ trước |
| DG-9 | Chuyển prompt và từ ngữ riêng của Vinhomes ra khỏi `src/vinhomes/` vào gói, đọc bằng bộ đọc gói của PH-2 | 16/10 | Phái | Kiểm tra ranh giới xanh cho `agent-coordination` |

**Nhận từ team khác:** môi trường tích hợp (PH-5, 09/10); API hồ sơ, điểm nhận sự kiện, API ghi sổ chi phí bản tối thiểu (CN-2, CN-1b, CN-3, 12/10); thư viện kiểm nguồn (HG-2, 13/10); agent Kỹ thuật và agent Vệ sinh theo HD-1 (QG-9, HG-7a, 13/10); kết quả tool có mã nguồn (QG-2, ví dụ 13/10, chạy thật 14/10); API ký ức (QG-6, mẫu 13/10, thật 15/10); bộ đọc gói (PH-2, khung 14/10).

**Gợi ý chia người:** (1) DG-1 rồi DG-6; (2) DG-0 rồi DG-2; (3) DG-3 rồi DG-8; (4) DG-4 và DG-5; (5) DG-7 rồi DG-9.

## 5. Team Quang: tool, kiến thức, bộ nhớ, agent Kỹ thuật

**Mục tiêu:** mọi thứ agent đọc được (kết quả tool, đoạn tài liệu, ký ức) đều có mã nguồn ổn định, và tool chỉ khai báo ở một nơi.

Vùng code: `server/src/technical-tools/**`, `server/src/knowledge/**`, cùng các tệp ghi ở "nơi sửa" dưới đây.

| Mã | Việc | Hạn | Ai chờ kết quả | Xong khi |
|---|---|---|---|---|
| QG-1 | Viết HD-3 kèm ví dụ | Nháp 09/10, chốt 12/10 | Tất cả | Ba tool kỹ thuật mô tả được bằng bản khai mà không mất trường nào |
| QG-2 | Mã nguồn ổn định và nhãn dữ liệu mẫu. Cổng gọi tool lưu nguyên kết quả mỗi lần gọi kèm `source_id`, lượt chạy, vụ việc và tool (bảng do CN-2 tạo). Đoạn tài liệu có mã tính từ mã tài liệu, phiên bản và mục, không dùng mã chunk. API tra một đoạn tài liệu theo mã. Nơi sửa: `services/vinhomes-api/src/vinhomes_api/v3_tool_gateway.py`, `v3_agent_knowledge.py`, `server/src/knowledge/retrieve.ts` | Ví dụ 13/10, chạy thật 14/10 | Đông, Chiến | Bấm mã trên màn hình mở đúng kết quả tool hoặc đúng đoạn; dựng lại môi trường thì mã đoạn tài liệu không đổi |
| QG-3 | Một bản khai, một job đăng ký cho tool kỹ thuật và vệ sinh. Nơi sửa: `server/src/technical-tools/catalog.ts`, `server/src/cleaning-tools/catalog.ts`, `deploy/vinhomes/upgrade.ts`, `tool_catalogue.py`, `services/vinhomes-api/scripts/setup_session_tools.py` | 16/10 | Phái | Môi trường local và môi trường tích hợp cho cùng danh sách tool; tool đã bỏ được gỡ |
| QG-4 | Mọi bộ tool trả cùng dạng kết quả; bỏ lớp vỏ lồng nhau ở cổng | 16/10 | Đông | Agent nhận đúng một lớp vỏ theo HD-3 cho tool kỹ thuật, vệ sinh, báo cáo, kiến thức |
| QG-5 | Truy hồi cho agent chuyên môn: "không đủ nguồn" thành trạng thái agent không vượt qua được; tham số truy hồi lấy từ cấu hình agent; dataset riêng theo agent | 16/10 | Đông | Test: câu hỏi ngoài kho cho ra câu hỏi mở, không cho ra nhận định |
| QG-6 | Ký ức: hồ sơ đã đóng thành mục ký ức theo căn hộ và theo loại sự cố, qua luồng ứng viên có duyệt; API đọc; bước xuất bản thành job trong triển khai. **Trước khi bật job: từ chối câu trả lời đã học đang ở trạng thái duyệt, vì đó là một câu đùa gõ lúc chạy thử** | API mẫu 13/10, thật 15/10 | Đông, Phái | Đóng một hồ sơ, duyệt, rồi API trả mục ký ức cho căn hộ đó |
| QG-7 | Nạp tài liệu theo kế hoạch dữ liệu; đưa tài liệu nguồn vào Git; kho kiến thức và quy trình cho sandbox đánh giá | Đợt 1: 14/10. Đợt 2: 16/10 | Hoàng, Phái | Bộ câu hỏi truy hồi chạy lại, có số so với lần trước |
| QG-8 | Dữ liệu sau tool kỹ thuật: thiết bị, bảo trì, lịch cắt dịch vụ, nhà thầu (bộ D-20 đến D-24) | Tòa S1.01: 14/10. Còn lại: 16/10 | Phái | Tool trả dữ liệu khớp với tòa và căn hộ trong kịch bản demo |
| QG-9 | Agent Kỹ thuật viết lại theo HD-1: định nghĩa, prompt, ca đánh giá. Nộp danh sách mã loại sự cố kỹ thuật cho CN-9 ngày 09/10 | Chạy được với DG-2: 13/10. Qua cổng đánh giá: 16/10 | Đông, Phái | Agent Kỹ thuật qua cổng đánh giá với định nghĩa mới |

**Nhận từ team khác:** HD-2 (cách hồ sơ trỏ nguồn); bảng lưu kết quả tool và API ghi sổ chi phí (CN-2, CN-3, 12/10); đường dẫn mới của các module đã chuyển (CN-7, 12/10 trưa); công cụ kiểm và nạp dữ liệu (PH-3); job triển khai (PH-5).

**Gợi ý chia người:** (1) QG-1 rồi QG-4; (2) QG-2; (3) QG-3 rồi QG-5; (4) QG-6; (5) QG-9, QG-7, QG-8.

## 6. Team Hoàng: Tiếp nhận, kiểm nguồn, đánh giá, số liệu chi phí

**Mục tiêu:** có thước đo. Luật kiểm nguồn dùng chung cho mọi agent, bộ đánh giá bắt được lỗi của phiên nhiều agent, và mỗi vụ việc có số chi phí và độ đúng.

Vùng code: `agent-reception/**`, `agent-report/**`, `server/src/reporting/**`, `server/src/cleaning-tools/**` (riêng `catalog.ts` do Team Quang sửa trong QG-3), `shared/python/grounding/**` (mới), và `agent-coordination/src/agent_eval/**`. Bộ đánh giá `agent_eval` do Team Chiến viết; Team Chiến bàn giao cách chạy cho Team Hoàng ngày 09/10. Phần còn lại của `agent-coordination/**` thuộc Team Đông, không sửa.

| Mã | Việc | Hạn | Ai chờ kết quả | Xong khi |
|---|---|---|---|---|
| HG-1 | Viết HD-5 kèm ví dụ | Nháp 09/10, chốt 12/10 | Đông, Quang, Chiến | Định nghĩa rõ từng số liệu: chi phí một vụ, tỉ lệ nhận định có nguồn, số mục bị chặn, số lần người sửa |
| HG-2 | Thư viện kiểm nguồn dùng chung, viết bằng Python, chỉ dùng thư viện chuẩn, đặt tại `shared/python/grounding/`. Hàm chính nhận một mục (câu, loại, danh sách mã nguồn) cùng bảng "mã nguồn, nội dung nguồn", trả về mục đã phân loại kèm lý do. Kiểm: nguồn có thật, con số có trong nguồn. Tiếp nhận chuyển sang dùng thư viện này | Chữ ký hàm và hai ví dụ: 09/10. Bản dùng được: 13/10 | Đông | Tiếp nhận dùng thư viện mới mà bộ kiểm thử cũ vẫn qua; có test cho mục hồ sơ |
| HG-3 | Đo số nền (số đo của hệ thống hiện tại, để so với sau khi sửa). Bước 1, 09/10: viết 10 kịch bản (5 kỹ thuật, 3 vệ sinh, 2 có cả hai) vào `docs/teams/hoang/reports/2026-10-09-HG-3-kich-ban-so-nen.md`, PM duyệt. Bước 2, 12/10: chạy 10 kịch bản trên `develop`, lấy token từng lần gọi từ log của DG-0 và từ số Tiếp nhận đã lưu. Bước 3, 13/10: hai người chấm tay độc lập từng nhận định theo mục 7.3 của tài liệu thiết kế, ghi cả chỗ hai người lệch nhau | 13/10 | PM, Đông | Bảng số nền và ngưỡng đề xuất gửi PM trong `docs/teams/hoang/reports/2026-10-13-HG-3-so-nen.md` |
| HG-4a | Tiếp nhận ghi dữ kiện của cư dân vào hồ sơ, kèm mã tin nhắn làm nguồn. Tiếp nhận là bên duy nhất ghi dữ kiện của cư dân | 14/10 | Đông, Chiến | Dữ kiện của cư dân hiện trong hồ sơ, bấm nguồn mở đúng tin nhắn |
| HG-4b | Tóm tắt hội thoại dài thay cửa sổ 30 tin; ghi số token được cache | 16/10 | Không ai ngoài team | Hội thoại 40 tin vẫn trả lời đúng điều nói ở tin thứ 5 |
| HG-5 | Bộ đánh giá cho phiên nhiều agent. Luật nguồn là nhóm kiểm thứ mười: sửa `agent_eval/contracts.py` và `checks.py`, chép lại bản sao ở `services/vinhomes-api/src/vinhomes_api/_vendor/agent_eval/` và đổi số phiên bản bộ kiểm **trong cùng một PR** (thiếu bước này thì mọi ca báo lỗi và cổng phát hành đóng với mọi agent). Ca nhiều agent chia thành các bộ sáu ca theo từng agent. Ca nối tiếp cùng căn hộ chạy bằng một script riêng, ngoài cổng phát hành | 16/10 | PM, Phái | Bộ ca chạy trên sandbox và cho kết quả; kết quả lưu lại |
| HG-6 | Số liệu theo vụ: tool báo cáo đọc sổ chi phí từ CN-3; bảng trước và sau cho buổi demo | 16/10, cập nhật 21/10 | PM | Agent Báo cáo trả lời được "vụ này tốn bao nhiêu"; bảng trước và sau có số thật |
| HG-7a | Agent Vệ sinh trả đầu ra theo HD-1. Nộp danh sách mã loại sự cố vệ sinh cho CN-9 ngày 09/10 | 13/10 | Đông | Agent Vệ sinh trả `findings[]` hợp lệ khi được gọi trong phiên hai agent |
| HG-7b | Agent Vệ sinh và agent Báo cáo qua cổng đánh giá với định nghĩa mới. Tool vệ sinh hiện chưa tạo được lệnh việc thật: hoặc làm phần đó trong `server/src/cleaning-tools/ports/backend.ts`, hoặc ghi rõ "tool này chưa tạo lệnh việc" trong bản khai tool và tệp bàn giao | 16/10 | Đông, Phái | Hai agent qua cổng đánh giá |
| HG-8 | Dữ liệu Team Hoàng giữ theo kế hoạch dữ liệu. Đợt 1: quy trình vệ sinh có thêm đoạn xử lý sàn ướt do rò nước (D-12), bảng giá model (D-50), bốn ca hai agent đầu tiên (D-40). Đợt 2: D-14, D-15, D-41 đến D-44, D-52 | Đợt 1: 14/10. Đợt 2: 16/10 | Phái, Quang | Mỗi bộ qua bốn bước kiểm ở mục 9 của kế hoạch dữ liệu |

**Nhận từ team khác:** bàn giao bộ đánh giá (Chiến, 09/10); log token của bản hiện tại (DG-0, 09/10); HD-1, HD-2 (Đông); API số liệu (CN-3, 14/10); sandbox trả các mục hồ sơ cho bộ đánh giá (CN-10, 15/10); phiên nhiều agent chạy ổn (DG-6, 16/10 sáng); công cụ kiểm và nạp dữ liệu (PH-3).

**Gợi ý chia người:** (1) HG-1 rồi HG-6; (2) HG-2 rồi HG-4b; (3) HG-3 rồi HG-5; (4) HG-4a rồi HG-8; (5) HG-7a rồi HG-7b.

## 7. Team Chiến: backend lõi, cơ sở dữ liệu, giao diện

**Mục tiêu:** hồ sơ và sổ chi phí có nơi lưu, có API, và người xem nhìn thấy agent làm việc trên hồ sơ.

Vùng code: `services/vinhomes-api/**`, `server/src/db/**`, `server/drizzle/**`, `app/**`.

| Mã | Việc | Hạn | Ai chờ kết quả | Xong khi |
|---|---|---|---|---|
| CN-0 | Tạo package lõi rỗng trong `services/vinhomes-api/src/` và thư mục giao diện lõi trong `app/src/features/`; báo tên cho Team Phái. Nêu tên một người giữ migration. Quyết định số phận của migration chưa commit `0021_retire_unused_schema`: gộp hoặc bỏ, trước khi ai viết migration tiếp theo. Bàn giao bộ đánh giá `agent_eval` cho Team Hoàng | 09/10 | Phái, Hoàng, tất cả | Phái trỏ được kiểm tra ranh giới vào package lõi; chuỗi migration không còn lỗ |
| CN-1 | Viết HD-4 kèm ví dụ: một phiên đã ghi dưới dạng chuỗi sự kiện | Nháp 09/10, chốt 12/10 | Đông | Dựng được giao diện từ tệp ví dụ |
| CN-1b | Điểm nhận sự kiện từ bộ điều phối, bảng lưu chỉ thêm, luồng đẩy tới trình duyệt (theo kiểu `graph_events` đang có) | 12/10 | Đông | Gửi một sự kiện thử thì trình duyệt nhận được, trên môi trường tích hợp |
| CN-2 | Bảng và API hồ sơ vụ việc: chỉ thêm, tách theo tenant, ghi có khóa chống trùng, đặt trong package lõi. Bảng lưu kết quả tool theo `source_id`. API mở nguồn: từ mã nguồn trả về kết quả tool hoặc đoạn tài liệu | Tối thiểu 12/10, đủ 14/10 | Đông, Hoàng, Quang | Ghi và đọc mục qua API trên môi trường tích hợp; sửa một mục đã ghi bị từ chối; ghi hai lần cùng khóa chỉ tạo một mục |
| CN-3 | Sổ chi phí: bản ghi mỗi lần gọi model (vụ, agent, model, token vào, ra, cache, tiền), bảng giá model, API số liệu. Thông số agent đặt trong cấu hình phiên bản agent | API ghi một bản ghi: 12/10. Đủ: 14/10 | Hoàng, Đông, Quang | Tổng token của một vụ khớp nhật ký gọi model |
| CN-4 | Việc của người vào hồ sơ: lệnh việc, báo giá, ảnh, kiểm tra chất lượng, xác nhận của cư dân | 16/10 | Không ai ngoài team | Một vụ đi hết vòng đời để lại các mục do người ghi trong hồ sơ |
| CN-5 | Màn hình vụ việc: danh sách ba nhóm, sàn làm việc, hồ sơ có nguồn bấm được (nối bước phương án với mục theo số thứ tự bước), thanh số liệu, ngăn hỏi agent. Đặt trong thư mục giao diện lõi | Khung trên phiên đã ghi: 13/10. Chạy sống: 14/10. Đủ: 16/10 | PM | PM duyệt trên ảnh chụp màn hình thật ở từng mốc |
| CN-6 | Bản sắc: API trả thương hiệu của gói lúc chạy; giao diện đặt màu khi tải trang, không phải build lại. Màu riêng cho agent, màu trạng thái, chuyển động cho trạng thái sống | API thương hiệu: 14/10. Đủ: 16/10 | Phái | Đổi `brand.yaml` rồi tải lại trang là đổi màu |
| CN-7 | Chuyển module về package lõi theo bảng ở mục 7.7 của tài liệu thiết kế. Trước khi chuyển: phân loại các module chưa có trong bảng, tách phần dùng chung khỏi các module riêng của Vinhomes mà module lõi đang import. Tệp chuyển tiếp ở đường import cũ phải giữ được các lệnh `python -m` trong tệp compose. Giữ một tệp danh sách module đã chuyển và chưa chuyển | Nhóm kiến thức, bộ nhớ, tool, agent: trước 12:00 ngày 12/10, mỗi nhóm một PR, báo trước hai giờ. Nhóm điều phối và nền: 14/10. Nhóm vụ việc và công việc: 16/10 | Quang, Phái, Hoàng | Sau mỗi nhóm: bộ kiểm thử cũ qua, một yêu cầu đi hết vòng đời. Dừng chuyển sau 16/10 |
| CN-8 | Chế độ phát lại một phiên đã ghi trên màn hình mới, đọc từ bảng sự kiện của CN-1b, có ghi rõ là phát lại | 16/10 | Phái | Phát lại được phiên demo khi không có model |
| CN-9 | Thế giới demo (bộ D-01 đến D-04 và D-31 trong kế hoạch dữ liệu). Ba tòa dùng cho demo: S1.01, S1.02, S2.01. **Gia hạn ca của cả 10 nhân viên tới 31/10, phủ cả buổi tối để tập** (ca của 8 trên 10 người hiện hết ngày 20/10). Quyết định dùng tenant đỗ hay sinh mới | Gia hạn ca và quyết định: 09/10. Thế giới cố định: 12/10. D-05 và D-31: 16/10 | Tất cả | Ngày 22/10 giao việc được cho cả ba nhóm dịch vụ; không ai đổi mã định danh sau 12/10 |
| CN-10 | Sandbox đánh giá trả các mục hồ sơ trong dấu vết của một ca (`v3_agent_eval_sandbox.py`) | 15/10 | Hoàng | Bộ kiểm của HG-5 đọc được mục hồ sơ của ca |

**Nhận từ team khác:** HD-2, HD-5 (để dựng bảng); danh sách mã loại sự cố (QG-9, HG-7a, PH-7, 09/10); sự kiện sống (DG-5); mã nguồn và API tra đoạn tài liệu (QG-2); luật ranh giới (PH-1); môi trường tích hợp (PH-5, 09/10).

**Gợi ý chia người:** (1) CN-0, CN-2 rồi CN-4; (2) CN-3, CN-9, CN-10; (3) CN-1, CN-1b rồi CN-5; (4) CN-5 cùng người thứ ba, rồi CN-6 và CN-8; (5) CN-7.

## 8. Team Phái: ranh giới, gói, kiểm thử, dữ liệu, xưởng agent, demo

**Mục tiêu:** lõi không còn chứa Vinhomes, có dữ liệu để chạy, và buổi demo trực tiếp không gãy.

Vùng code: `.github/**`, `deploy/**`, `tests/**`, `agent-factory/**`, `server/src/security-tools/**`, thư mục gói mới.

| Mã | Việc | Hạn | Ai chờ kết quả | Xong khi |
|---|---|---|---|---|
| PH-1 | Viết HD-6 và HD-7. Kiểm tra ranh giới trong CI, có danh sách vi phạm đã biết; CI chỉ đỏ khi có vi phạm mới. Thêm vào CI các bộ test hiện chưa được chạy (`server/tests/cleaning-tools`, test của bộ nạp gói, test chuỗi migration). Mọi thay đổi vào nhánh team đi qua PR để CI chạy | CI: 09/10. Hợp đồng chốt: 12/10 | Tất cả | CI đỏ khi một tệp trong lõi import từ gói |
| PH-2 | Gói Vinhomes: `brand.yaml`, `domain.yaml`, định nghĩa agent kèm ca đánh giá, nguồn kiến thức, bản khai tool. **Bộ đọc gói bằng Python đặt trong package lõi, dùng chung cho API và bộ điều phối**; thư mục gói được gắn vào các container trong tệp compose. Bộ nạp `server/src/tenant-package.ts` hiện không nằm trên đường chạy của hệ thống Vinhomes, chỉ dùng để kiểm định dạng | Bộ đọc và khung gói: 14/10. Đủ: 16/10 | Đông, Quang, Hoàng, Chiến | Hệ thống đọc prompt, từ vựng và thương hiệu từ gói; một yêu cầu đi hết vòng đời |
| PH-3 | Công cụ sinh, kiểm và nạp dữ liệu theo kế hoạch dữ liệu. Ba hồ sơ lịch sử của căn hộ demo (D-30) nạp qua API CN-2 | Bộ kiểm: 12/10. Ba hồ sơ: 12:00 ngày 14/10. Đợt 2: 16/10 | Quang, Hoàng, Chiến | Mỗi bộ dữ liệu qua bộ kiểm, có nhãn nguồn gốc, nạp bằng một lệnh |
| PH-4 | Kiểm thử đầu cuối theo tám bước demo, chạy hằng đêm; thêm một ca yêu cầu đi hết vòng đời theo luồng cũ. Kiểm rằng bước 3 cho đúng một mục bị hạ thành giả định | Từ 14/10 | Tất cả | Mỗi sáng có báo cáo bước nào qua, bước nào hỏng |
| PH-5 | Môi trường tích hợp chạy `develop` bằng `deploy/vinhomes/compose.yml`, có địa chỉ, cách đưa bản mới lên và người trực, ghi trong `docs/teams/platform/handoffs/2026-10-09-PH-5-moi-truong-tich-hop.md`. **Lệnh dựng lại tenant từ tệp trong Git**: đăng ký model cho vai trò agent chuyên môn và Supervisor, sinh ca nhân viên theo ngày dựng. Môi trường demo riêng; script đặt lại dữ liệu; job xuất bản kiến thức đã học | Môi trường tích hợp: 09/10. Lệnh dựng lại: 12/10. Còn lại: 14/10 | Tất cả | Một máy mới dựng được môi trường demo bằng một lệnh; đặt lại dưới 10 phút |
| PH-6 | Xưởng agent: màn hình đường ống tạo, đánh giá, phát hành; Factory sinh định nghĩa agent theo HD-1 kèm thông số | 16/10 | PM | Tạo một agent mới, chạy đánh giá, thấy cổng mở khóa phát hành |
| PH-7 | An ninh: nạp camera và liên hệ khẩn cấp (D-25) cho hai tool an ninh agent thật gọi được; định nghĩa agent An ninh theo HD-1 đưa vào Git. Nộp danh sách mã loại sự cố an ninh cho CN-9 ngày 09/10 | 16/10 | Đông, Quang | Agent An ninh được mời vào phiên có yêu cầu an ninh và trả mục có nhãn dữ liệu mẫu |
| PH-8 | Sổ tay demo: kịch bản từng bước, người thao tác, phương án khi model hoặc mạng lỗi, lịch tổng duyệt | Nháp 16/10, chốt 20/10 | PM | Kịch bản chạy 5 lần liên tiếp không lỗi |

**Nhận từ team khác:** tên package lõi (CN-0, 09/10); khuôn hồ sơ đã đóng (DG-1, 12/10); prompt và từ ngữ Vinhomes (DG-9); bản khai tool (QG-3); định nghĩa agent (QG-9, HG-7b); API thương hiệu (CN-6); chế độ phát lại (CN-8).

**Gợi ý chia người:** (1) PH-1 rồi PH-2; (2) PH-3; (3) PH-4 rồi PH-8; (4) PH-5; (5) PH-6 và PH-7.

## 9. Các điểm giao nhận giữa các team

Đây là những lúc một team không thể đi tiếp nếu team khác chưa giao. Trưởng team theo dõi bảng này mỗi ngày.

| Ngày | Ai giao | Giao gì | Ai nhận |
|---|---|---|---|
| 09/10 | Chủ hợp đồng | Bảy bản nháp hợp đồng kèm ví dụ | Tất cả |
| 09/10 | Phái | Môi trường tích hợp có địa chỉ; kiểm tra ranh giới trong CI | Tất cả |
| 09/10 | Chiến | Package lõi rỗng; người giữ migration; bàn giao bộ đánh giá; gia hạn ca nhân viên | Phái, Hoàng, tất cả |
| 09/10 | Đông | Log token của bản hiện tại | Hoàng |
| 09/10 | Hoàng | Chữ ký hàm của thư viện kiểm nguồn | Đông |
| 09/10 | Quang, Hoàng, Phái | Danh sách mã loại sự cố | Chiến |
| 12/10 trưa | Chiến | Các nhóm kiến thức, bộ nhớ, tool, agent đã ở đường dẫn mới | Quang, Phái, Hoàng |
| 12/10 | Chủ hợp đồng | Bảy hợp đồng đã chốt | Tất cả |
| 12/10 | Chiến | API hồ sơ, điểm nhận sự kiện, API ghi sổ chi phí, bản tối thiểu; thế giới demo cố định | Đông, Hoàng, Quang |
| 12/10 | Phái | Lệnh dựng lại tenant; bộ kiểm dữ liệu | Tất cả |
| 12/10 | Đông | Khuôn hồ sơ đã đóng | Phái |
| 13/10 | Hoàng | Thư viện kiểm nguồn; agent Vệ sinh theo HD-1; số nền và ngưỡng đề xuất | Đông; PM |
| 13/10 | Quang | Agent Kỹ thuật theo HD-1; ví dụ kết quả tool có mã nguồn; API ký ức mẫu | Đông, Chiến |
| 13/10 | Chiến | Khung màn hình trên một phiên đã ghi | PM |
| 14/10 | Đông | Phiên hai agent ghi hồ sơ, gửi sự kiện sống | Chiến, Hoàng |
| 14/10 | Phái | Dữ liệu đợt 1; môi trường demo; bộ đọc gói | Tất cả |
| 14/10 | Tất cả | Trình diễn nội bộ M1; PM chốt ngưỡng | PM |
| 15/10 | Quang | API ký ức chạy thật | Đông |
| 15/10 | Chiến | Sandbox trả mục hồ sơ cho bộ đánh giá | Hoàng |
| 16/10 sáng | Đông | Rà soát chéo và hợp nhất chạy ổn | Hoàng |
| 16/10 | Tất cả | Đủ tính năng; dữ liệu đợt 2; ranh giới xanh | PM |
| 20/10 | Phái | Sổ tay demo đã chốt | PM |
| 21/10 12:00 | Tất cả | Bản cuối. Không gộp code sau giờ này | PM |

## 10. Cách làm việc với nhau

**Nhánh và gộp code**
- Mỗi việc một nhánh, tên có mã việc, ví dụ `dg-3-context-builder`.
- PR vào nhánh của team, trưởng team duyệt. Mọi thay đổi đi qua PR để CI chạy. Nhánh của team gộp vào `develop` **ít nhất một lần mỗi ngày**.
- Chỉ sửa trong vùng code của team mình. Ngoại lệ: tệp ghi ở "nơi sửa" của một việc thì team giữ việc đó được sửa mà không cần viết yêu cầu; chủ vùng code duyệt PR.
- Cần sửa chỗ khác thuộc team khác thì viết yêu cầu (mục 11).

**Tệp dùng chung**
- `shared/contracts/**`: chỉ chủ hợp đồng sửa.
- Migration: chỉ Team Chiến viết, do một người được nêu tên. Dùng SQL viết tay trong `server/drizzle/`. Team khác cần bảng hoặc cột thì gửi yêu cầu trước 12:00 ngày 12/10.
- Tệp compose và `server/src/index.ts`: Team Phái và Team Chiến.

**Môi trường tích hợp** là máy chung chạy nhánh `develop`. Địa chỉ và cách dùng nằm trong tệp bàn giao của PH-5.

**Họp ngắn hằng ngày, 15 phút, năm trưởng team và PM**
1. Điểm giao nhận hôm nay (mục 9): đã giao chưa.
2. Ai đang bị chặn, bởi ai.
3. Kiểm thử đầu cuối đêm qua: bước nào hỏng, ai nhận sửa.

**Khi bị chặn:** báo trưởng team mình và trưởng team kia trong vòng hai giờ. Trong lúc chờ, làm tiếp trên ví dụ của hợp đồng.

**Một việc được coi là xong khi đủ năm điều**
1. Code đã gộp vào `develop`.
2. Có test tự động cho phần mới và bộ test cũ vẫn qua.
3. Chạy được trên môi trường tích hợp, không chỉ trên máy mình.
4. Có tệp bàn giao (mục 11).
5. Với giao diện: có ảnh chụp màn hình thật.

**Bảng tiến độ:** Team Phái giữ tệp `docs/teams/platform/TIEN_DO.md`, mỗi dòng một mã việc với trạng thái (chưa làm, đang làm, bị chặn, xong). Trưởng team cập nhật trước giờ họp.

**Dữ liệu mẫu:** mọi dữ liệu không phải dữ liệu thật phải mang nhãn theo HD-7. Không ai được bỏ nhãn để màn hình "trông thật hơn".

**Khóa và bí mật:** không đưa khóa model, mật khẩu hay token vào Git, vào tệp bàn giao hay vào ảnh chụp màn hình.

## 11. Mẫu yêu cầu và mẫu bàn giao

Dùng đúng hai loại thư mục đã có trong repo. Thư mục của Team Phái là `docs/teams/platform/`.

**Yêu cầu** là khi mình cần team khác làm hoặc đổi một thứ. Đặt tại thư mục của **team nhận**: `docs/teams/<team nhận>/requests/2026-10-DD-<mã việc>-<tên ngắn>.md`

```markdown
# Yêu cầu: <một câu>

Từ: Team <tên>, việc <mã>. Gửi: Team <tên>. Ngày: DD/10/2026. Cần trước: DD/10.

## Cần gì
<điều cụ thể, kèm ví dụ dữ liệu vào và ra>

## Vì sao
<việc nào của mình bị chặn nếu thiếu>

## Đề xuất
<cách mình nghĩ là đơn giản nhất; team nhận có thể chọn cách khác>

## Trả lời của team nhận
<nhận / nhận có điều chỉnh / không nhận, kèm hạn>
```

**Bàn giao** là khi mình xong một việc mà team khác sẽ dùng. Đặt tại thư mục của **team giao**: `docs/teams/<team giao>/handoffs/2026-10-DD-<mã việc>-<tên ngắn>.md`

```markdown
# Bàn giao <mã việc>: <một câu>

Từ: Team <tên>. Gửi: Team <tên>. Ngày: DD/10/2026.

## Đã làm được gì
<hành vi mới, nói bằng lời thường>

## Dùng thế nào
<lệnh, đường dẫn API, ví dụ gọi và kết quả>

## Đã kiểm thế nào
<test nào đã chạy và kết quả; cái gì chạy trên môi trường tích hợp>

## Chưa kiểm
<những gì chưa chạy thử, nói thẳng>

## Giới hạn và việc còn lại
<điều người nhận cần biết để không dẫm phải>

## Tệp đã sửa
<danh sách>
```

Tệp bàn giao phân biệt rõ "đã chạy thử" và "chưa chạy thử". Một bảng trong cơ sở dữ liệu hay một API trả mã 200 chưa phải là xong.

## 12. Bàn giao cuối cùng của mỗi team

Hạn: 12:00 thứ Tư 21/10. Mỗi team nộp một tệp `docs/teams/<team>/handoffs/2026-10-21-BAN_GIAO_CUOI.md` gồm:

1. **Danh sách việc** theo mã: xong, xong một phần, chưa làm. Với việc xong một phần, ghi rõ phần nào chạy.
2. **Cách chạy và kiểm** phần của team: lệnh khởi động, lệnh test, biến môi trường mới (chỉ tên biến).
3. **Số liệu** của team nếu có: token trước và sau, kết quả bộ đánh giá, số tool trong danh mục, số module đã chuyển về lõi.
4. **Lỗi đã biết** và cách né trong buổi demo.
5. **Việc sau 22/10** mà team đề xuất, theo thứ tự.
6. **Dữ liệu** team đã tạo: bộ nào, ở đâu, nhãn gì.

PM gộp năm tệp này thành phần phụ lục của báo cáo cuối.

## 13. Ba ngày đóng băng và ngày demo

- **Từ 19/10:** chỉ gộp bản sửa lỗi. Mỗi bản sửa phải được trưởng team và Team Phái đồng ý, vì mỗi thay đổi có thể làm hỏng bước khác của kịch bản.
- **Mỗi ngày hai lượt tập** trên môi trường demo, đúng kịch bản tám bước, đặt lại dữ liệu trước mỗi lượt. Team Phái ghi lại bước nào hỏng.
- **20/10:** chốt sổ tay demo, chốt người thao tác và người dự phòng cho từng bước.
- **21/10:** tổng duyệt cuối. Sau 12:00 không gộp code. Chụp lại trạng thái môi trường demo để khôi phục được.
- **22/10:** trước giờ demo một tiếng, đặt lại dữ liệu và chạy thử một lượt. Trong lúc demo, mỗi team có một người trực.

**Khi có sự cố trong lúc demo** (theo thứ tự): chuyển sang nhà cung cấp model dự phòng; nếu vẫn lỗi, dùng chế độ phát lại phiên đã ghi và nói rõ với người xem là đang phát lại.
