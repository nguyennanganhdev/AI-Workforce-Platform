# Tái cấu trúc AI Workforce Platform: thiết kế và định hướng

Ngày lập: 08/10/2026. Buổi báo cáo cuối: **22/10/2026, demo trực tiếp**.

**Trạng thái:** PM đã duyệt hướng đi ngày 08/10 (mục 2). Tài liệu này nói *làm gì và vì sao*. Hai tài liệu đi kèm nói *ai làm, khi nào* và *dữ liệu lấy ở đâu*:

| Bạn cần biết | Đọc |
|---|---|
| Nền tảng sẽ thành cái gì, vì sao | Tài liệu này |
| Team mình làm việc gì, hạn nào, giao cho ai | [PHAN_CONG_VA_BAN_GIAO_2026-10-08.md](PHAN_CONG_VA_BAN_GIAO_2026-10-08.md) |
| Cần dữ liệu gì, lấy ở đâu, ai làm | [KE_HOACH_DU_LIEU_2026-10-08.md](KE_HOACH_DU_LIEU_2026-10-08.md) |
| Bên ngoài đã có gì | [teams/chien/NGHIEN_CUU_DINH_VI_PLATFORM_2026-10-08.md](teams/chien/NGHIEN_CUU_DINH_VI_PLATFORM_2026-10-08.md) |

Tài liệu này thay [KE_HOACH_HOAN_THIEN_5_TEAM.md](KE_HOACH_HOAN_THIEN_5_TEAM.md) về mục tiêu, thứ tự ưu tiên và chia việc. Team thứ năm trong tài liệu cũ ("Team 5") là **Team Phái**.

## 1. Tóm tắt

**Dự án là gì.** Một nền tảng để doanh nghiệp vận hành dịch vụ đưa lĩnh vực của mình vào (kiến thức, tool, quy trình, nhân sự) và nhận về một đội gồm agent và con người cùng xử lý vụ việc của khách hàng. Vinhomes là lĩnh vực đầu tiên.

**Khác gì bên ngoài.** Mỗi vụ việc là một **hồ sơ có bằng chứng**. Agent và người cùng làm việc trên hồ sơ đó. Không điều gì được vào phương án nếu không chỉ ra nó lấy từ đâu. Mỗi hồ sơ biết nó tốn bao nhiêu và đúng bao nhiêu.

**Hai tuần tới làm gì.**

| Mốc | Ngày | Kết quả |
|---|---|---|
| M0 | Thứ Hai 12/10 | Bảy hợp đồng giữa các team được chốt. Nơi lưu hồ sơ và sổ chi phí có trên môi trường tích hợp. |
| M1 | Thứ Tư 14/10 | Lát cắt đầu tiên chạy thật: phiên hai agent ghi hồ sơ có nguồn, có số chi phí, màn hình mới đọc dữ liệu thật. |
| M2 | Thứ Sáu 16/10 | Đủ tính năng: rà soát chéo, ký ức, một danh mục tool, Vinhomes thành gói, màn hình hoàn chỉnh, bộ đánh giá nhiều agent. |
| Đóng băng | 19 đến 21/10 | Chỉ sửa lỗi, tập demo, đo số trước và sau. |
| Demo | Thứ Năm 22/10 | Demo trực tiếp tám bước (mục 9). |

**Cảnh báo của người lập kế hoạch.** PM đã chọn làm đầy đủ cả bốn hướng trong hai tuần. Từ nay tới M2 chỉ còn bảy ngày làm việc. Kế hoạch khả thi nếu ba điều kiện giữ được: hợp đồng chốt đúng 12/10, các team làm song song trên dữ liệu mẫu của hợp đồng thay vì chờ nhau, và không thêm việc ngoài danh sách. Thứ tự cắt khi trễ nằm ở mục 11.

## 2. Những gì đã chốt

PM chốt ngày 08/10:

1. Báo cáo cuối ngày 22/10, **chỉ demo trực tiếp**. Đóng băng tính năng ba ngày trước đó.
2. **Tái cấu trúc**, không viết lại. Luồng Vinhomes vẫn chạy suốt quá trình.
3. **Làm đầy đủ** cả bốn hướng: lõi agent, tách khỏi Vinhomes, điểm khác biệt, giao diện.
4. Phạm vi nền tảng: doanh nghiệp **vận hành dịch vụ**. Luồng vụ việc và công việc thuộc lõi.
5. Điểm khác biệt chính: **hồ sơ vụ việc gắn bằng chứng**.
6. Agent chuyên môn trong phiên **gọi model trực tiếp**, không đi qua OpenBot.
7. Khách hàng cuối dùng agent **trong app của doanh nghiệp** qua SDK hoặc API. Trước 22/10 chỉ nêu trong thiết kế, chưa làm SDK.
8. Chưa làm lĩnh vực thứ hai. Chứng minh việc tách bằng cách đóng Vinhomes thành gói.
9. Dữ liệu: nguồn công khai có ghi nguồn, cộng dữ liệu tổng hợp có gắn nhãn.
10. Mỗi team có 4 đến 5 người. Chia việc theo lớp nền tảng (mục 8).
11. PM cho phép sửa lõi điều phối.

Còn mở, không chặn việc trước 22/10: quan hệ với bản gốc OpenBot (đề xuất: coi là bản rẽ nhánh), và nhiều tenant trên một hệ thống (đề xuất: sau báo cáo).

## 3. Thuật ngữ

| Từ | Nghĩa |
|---|---|
| Vụ việc | Một yêu cầu của khách hàng, từ lúc tiếp nhận tới lúc đóng. |
| Hồ sơ vụ việc | Bản ghi có cấu trúc của một vụ việc. Gồm nhiều mục. |
| Mục | Một dòng trong hồ sơ: dữ kiện, nhận định, giả định, phản đối, câu hỏi, bước phương án, việc giao, kết quả. |
| Nguồn | Thứ một mục dựa vào: lời khách hàng, kết quả một lần gọi tool, một đoạn tài liệu, một ảnh, hoặc một mục khác. |
| Lượt agent | Một lần một agent được gọi: nhận ngữ cảnh, trả về các mục. |
| Lõi | Phần nền tảng dùng chung cho mọi lĩnh vực. Không chứa tên hay khái niệm riêng của Vinhomes. |
| Gói lĩnh vực | Mọi thứ riêng của một lĩnh vực: thương hiệu, từ vựng, agent, tool, tài liệu, quy trình. |
| Hợp đồng | Thỏa thuận bằng văn bản về dữ liệu trao đổi giữa hai team, có ví dụ. |
| Phiên | Một lần các agent cùng xử lý một vụ việc. |
| Supervisor | Agent điều phối của một phiên: giao việc cho agent chuyên môn và lập phương án. |
| Sổ việc | Bảng việc Supervisor giao cho từng agent trong một phiên. Đã có. Không liên quan chi phí. |
| Sổ chi phí | Bảng ghi mỗi lần gọi model: vụ nào, agent nào, bao nhiêu token, bao nhiêu tiền. |
| Số nền | Số đo của hệ thống hiện tại trước khi sửa, để so với số đo sau khi sửa. |
| Cổng phát hành | Bước bắt buộc: agent phải qua bộ đánh giá thì mới được phát hành. |
| Sandbox | Môi trường riêng để chạy đánh giá agent, tách khỏi dữ liệu đang dùng. |
| Tenant | Một khách hàng doanh nghiệp trên nền tảng, dữ liệu tách riêng. |
| Môi trường tích hợp | Máy chung chạy nhánh `develop`, nơi các team kiểm phần của mình chạy cùng nhau. |

## 4. Bài toán được xác định lại

**Vì sao có nhận xét của sếp.** Kế hoạch cũ ghi "Vinhomes là lĩnh vực kiểm chứng đầu tiên, không được hardcode", nhưng tiến độ lại được đo bằng "một yêu cầu của cư dân đi hết vòng đời". Thước đo đó đã đạt ngày 04/10, và để lại ba hệ quả:

- Năng lực nền tảng (tạo agent, đánh giá, model, kết nối ngoài, bộ nhớ, điều phối) được viết thành module của package `vinhomes_api`.
- Agent bị kiểm soát chặt: chỉ thấy việc của mình, trả lời Supervisor rồi dừng. An toàn nhưng không cộng tác.
- Giao diện đi theo luồng việc của Ban quản lý, nên trông như một ứng dụng nghiệp vụ có khung chat.

**Bài toán mới.**

> Nền tảng lực lượng lao động AI cho doanh nghiệp vận hành dịch vụ: khách hàng nêu yêu cầu, một đội agent phân tích và lập phương án trên cùng một hồ sơ có bằng chứng, con người duyệt và thực hiện, hồ sơ đó trở thành kinh nghiệm cho vụ sau.

**Vì sao giới hạn ở vận hành dịch vụ.** Vinhomes (cư dân, căn hộ, kỹ thuật, vệ sinh, an ninh) và Vinpearl (khách lưu trú, phòng, buồng phòng, kỹ thuật) có cùng hình dạng. Phần dự án làm tốt nhất nằm đúng ở hình dạng đó. Một nền tảng agent "cho mọi việc" phải cạnh tranh với các công cụ dựng agent phổ thông, nơi dự án không có lợi thế.

## 5. Điểm khác biệt

### 5.1. Bên ngoài đã có gì

| Năng lực | Bên ngoài | Với dự án |
|---|---|---|
| Agent chia sẻ trạng thái, nhắn nhau, có vòng duyệt | Có sẵn ở các framework lớn | Dự án đang đi sau. Phải có. |
| Tóm tắt hội thoại, bộ nhớ dài hạn, cache prompt, đo token | Thư viện hoặc một tham số | Nợ phải trả. |
| Chấm bám nguồn cho một câu trả lời | Có dạng dịch vụ; một số chỉ tối ưu cho tiếng Anh | Phải có. |
| Sinh ca kiểm thử cho agent | Chuẩn chung | Dự án đã có. |
| Học từ vụ đã xử lý, có người duyệt | Phổ thông | Không nêu là độc đáo. |
| Gói lĩnh vực | Phổ thông | Phải có. Không nêu là độc đáo. |
| Agent và nhân viên hiện trường chung luồng | Có ở Salesforce và ServiceNow | Lợi thế với doanh nghiệp không dùng hai hệ đó. |

Nghiên cứu **không tìm thấy** ai làm thành đối tượng hạng nhất bốn thứ sau. "Không tìm thấy" là trong các trang đã đọc ngày 08/10, không phải bằng chứng là không tồn tại.

1. Hồ sơ vụ việc gắn bằng chứng.
2. Bắt buộc có nguồn ở bước hợp nhất kết quả nhiều agent, ngay lúc chạy.
3. Cổng phát hành chặn cứng cho agent do người nghiệp vụ tạo. Dự án đã có.
4. Chi phí và kết luận bám nguồn trên cùng một vụ, trình bày cho chủ doanh nghiệp.

### 5.2. Một hồ sơ, bốn năng lực

1. **Agent làm việc cùng nhau trên bằng chứng.** Agent đọc hồ sơ nên biết agent khác kết luận gì, dựa vào đâu. Phản biện là đối chiếu nguồn.
2. **Không nguồn thì không vào phương án.** Code thi hành luật này. Vì là luật theo cấu trúc, nó không phụ thuộc ngôn ngữ.
3. **Sổ chi phí và độ đúng theo từng vụ.** Token, tiền, thời gian, số nhận định có nguồn, số bị chặn, con người đã sửa gì.
4. **Hồ sơ đã đóng là kinh nghiệm và là bộ kiểm thử.** Vụ sau đọc lại hồ sơ cũ. Hồ sơ cũ cũng là ca để chạy lại khi đổi model hay prompt.

### 5.3. Ví dụ một hồ sơ

Cư dân căn 1201 báo rò nước trong căn hộ, nước tràn ra sàn, và cần dọn. (Sự cố đặt trong căn hộ vì danh mục loại sự cố kỹ thuật hiện chỉ có sự cố trong căn hộ.)

| # | Loại | Ai ghi | Nội dung | Nguồn |
|---|---|---|---|---|
| 1 | Dữ kiện | Tiếp nhận | "Ống nước dưới bồn rửa đang rò, nước tràn ra sàn bếp" | Tin nhắn của cư dân |
| 2 | Dữ kiện | Tool | Không có lịch cắt nước tòa S1.01 hôm nay | Lần gọi tool `get_active_outage` |
| 3 | Nhận định | Agent Kỹ thuật | Cần khóa van cấp nước của căn hộ trước khi sửa đầu nối | Mục 1, đoạn quy trình rò rỉ đường ống |
| 4 | Nhận định | Agent Vệ sinh | Đặt biển cảnh báo ngay, lau sau khi hết rò | Mục 1, đoạn quy trình vệ sinh khu vực ướt |
| 5 | Phản đối | Agent Vệ sinh | Bước lau của Kỹ thuật phải xếp sau bước xác nhận hết rò | Mục 3, mục 4 |
| 6 | Giả định | Agent Kỹ thuật | Có thể do gioăng lão hóa | Không có. Không được dùng làm căn cứ |
| 7 | Bước phương án | Supervisor | Khóa van, sửa đầu nối, xác nhận hết rò, rồi lau | Mục 3, 4, 5 |
| 8 | Kết quả | Kỹ thuật viên | Đã thay đầu nối, kèm 2 ảnh | Ảnh hiện trường |

Mục 6 hiện trên màn hình với nhãn "giả định". Nếu Supervisor định dựa một bước chỉ trên mục 6, code từ chối bước đó.

Hai đoạn quy trình mà mục 3 và mục 4 trỏ tới hiện chưa có trong kho. Chúng thuộc dữ liệu đợt 1 (bộ D-11 và D-12 trong kế hoạch dữ liệu).

### 5.4. Câu để nói với sếp

*"Ở nền tảng của mình, không agent nào được đưa một điều vào phương án nếu không chỉ ra nó lấy từ đâu, và mỗi vụ việc đều hiện rõ nó tốn bao nhiêu và đúng bao nhiêu."*

Không nên nói là độc đáo: nhiều agent có supervisor, học từ vụ việc, gói lĩnh vực, người duyệt trước khi ghi.

### 5.5. Mục tiêu dài hạn

- **Một năm:** hai lĩnh vực chạy thật trên cùng một lõi; gói mới dựng bằng cấu hình, tool và tài liệu.
- **Xa hơn:** một lực lượng lao động AI dùng chung cho nhiều công ty trong cùng hệ sinh thái. Agent có năng lực giống nhau được dùng lại giữa các lĩnh vực. Đây là suy luận của người lập kế hoạch, chưa có dữ liệu thị trường.

## 6. Ai dùng nền tảng

| Vòng | Là ai | Dùng gì | Đăng nhập |
|---|---|---|---|
| 1. Dựng và điều hành | Quản trị, quản lý, điều phối của doanh nghiệp | Console của nền tảng | Tài khoản nền tảng |
| 2. Thực hiện | Nhân viên hiện trường, nhà thầu | App công việc của nền tảng | Tài khoản nền tảng |
| 3. Khách hàng cuối | Cư dân, khách lưu trú | Agent tiếp nhận trong app của doanh nghiệp | Không đăng nhập nền tảng. Máy chủ doanh nghiệp ký danh tính. |

`resident-app` trở thành ứng dụng mẫu của gói Vinhomes. API hội thoại công khai, SDK nhúng và danh tính do doanh nghiệp ký làm sau 22/10.

## 7. Thiết kế

### 7.1. Một phiên chạy thế nào

1. **Mở hồ sơ.** Dữ kiện từ Tiếp nhận vào hồ sơ. Ký ức của đối tượng (căn hộ, cư dân) được nạp.
2. **Phân tích độc lập.** Mỗi agent trả lời việc của mình, chưa thấy kết luận của agent khác. Mục đích: tránh hùa theo.
3. **Rà soát chéo.** Chạy khi phiên có từ hai agent hoặc có mục rủi ro. Mỗi agent đọc hồ sơ, trả về đồng thuận, phản đối hoặc bổ sung. Đúng một vòng.
4. **Hợp nhất.** Supervisor lập phương án, mỗi bước trỏ về mục trong hồ sơ. Bất đồng chưa giải quyết chuyển cho người.
5. **Thực hiện.** Lệnh việc, báo giá, ảnh, kết quả kiểm tra do người ghi vào hồ sơ.
6. **Đóng.** Hồ sơ được chắt thành ứng viên ký ức, đi qua luồng duyệt sẵn có. Sổ chi phí được chốt.

### 7.2. Agent nhận gì, trả gì

**Nhận**, xếp từ ít đổi tới hay đổi để tận dụng cache của nhà cung cấp model:

| Lớp | Nội dung | Hiện có |
|---|---|---|
| 1. Hồ sơ agent | Vai trò, phạm vi, điều không làm | Có |
| 2. Quy tắc chung | Luật về nguồn, khuôn đầu ra | Một phần |
| 3. Danh bạ phiên | Các agent khác: tên, bộ phận, phụ trách gì | Có, nhưng chỉ Supervisor nhận |
| 4. Ký ức | Tóm tắt hồ sơ trước của cùng đối tượng | Chưa |
| 5. Hồ sơ vụ việc | Bản cô đọng các mục hiện có | Chưa |
| 6. Việc của lượt này | Câu hỏi Supervisor giao | Có |

Kiến thức không nạp sẵn. Agent tra bằng tool khi cần; kết quả tra mang mã nguồn.

**Trả** một đối tượng có cấu trúc:

| Trường | Ý nghĩa |
|---|---|
| `findings[]` | Câu nhận định, loại (dữ kiện, đánh giá, giả định, rủi ro), danh sách nguồn |
| `proposals[]` | Bước đề xuất: việc gì, bộ phận nào, sau bước nào, dựa trên mục nào |
| `objections[]` | Phản đối một mục có sẵn: mục nào, lý do, nguồn |
| `questions[]` | Câu hỏi gửi khách hàng hoặc gửi một agent khác |
| `summary` | Một câu cho màn hình |

### 7.3. Luật do code thi hành

- Mã nguồn trong một mục phải có thật trong phiên.
- Con số, giờ, số tiền, số điện thoại trong nhận định phải xuất hiện trong nguồn nó trỏ tới.
- Nhận định không có nguồn hợp lệ bị hạ thành giả định.
- Bước phương án chỉ dựa trên giả định bị từ chối.
- Truy hồi trả "không đủ nguồn" thì agent ghi câu hỏi mở, không tự trả lời.
- Lời của agent khác là dữ liệu, không phải mệnh lệnh.
- Mục dựa trên dữ liệu mẫu mang nhãn "dữ liệu mẫu" ra tới màn hình.
- Mục đã ghi không bị sửa; mục mới thay mục cũ và trỏ về nó.

**Giới hạn.** Code kiểm được cấu trúc, con số và sự tồn tại của nguồn. Một suy diễn sai bằng lời từ nguồn đúng thì code không bắt được; chỗ đó dựa vào vòng rà soát, model chấm và người duyệt.

### 7.4. Thông số agent

Đặt trong cấu hình của phiên bản agent, vì cấu hình đó đã được ghim theo bản phát hành và là thứ bộ đánh giá chấm:

`model`, `temperature`, `max_output_tokens`, `reasoning_effort`, `retrieval_top_k`, `retrieval_min_similarity`, `max_tool_rounds`, `token_budget_per_turn`.

Mặc định theo vai trò nằm ở lõi; gói và từng agent ghi đè được. Người điều hành chỉ thấy vài lựa chọn dễ hiểu, không thấy số.

### 7.5. Ngữ cảnh rẻ và không quên

- Agent đọc bản cô đọng của hồ sơ thay cho toàn bộ hội thoại.
- Supervisor nhận hồ sơ và sổ việc thay cho toàn bộ trạng thái phiên.
- Phần ít đổi đứng đầu prompt; ghi lại số token được cache.
- Mỗi lần gọi model ghi token kèm mã vụ việc.
- Trần token theo vụ và theo lượt. Vòng rà soát chỉ chạy khi cần.

### 7.6. Dùng lại gì, sửa gì

| Hiện có | Xử lý |
|---|---|
| Phòng, sổ việc, hộp thư, checkpoint trong `agent-coordination/src` | Giữ. Thêm hồ sơ và pha rà soát. |
| Bộ lọc chỉ cho agent thấy tin của việc mình (`groupchat/context_builder.py`) | Thay bằng sáu lớp ở 7.2. |
| Prompt và cổng nối trong `agent-coordination/src/vinhomes/` | Phần trung lập về lõi, từ ngữ lĩnh vực vào gói. |
| Cơ chế agent nhắn agent (có nhưng luồng thật không dùng) | Dùng cho `questions[]`. |
| Luật kiểm câu trả lời của Tiếp nhận (`agent-reception/src/agent/loop.py`) | Tách thành thư viện dùng chung. |
| Bộ đánh giá và cổng phát hành | Giữ. Thêm ca nhiều agent và luật kiểm nguồn. |
| Luồng ứng viên kiến thức có người duyệt | Giữ. Thêm đầu vào là hồ sơ đã đóng. |
| Kiểm quyền mỗi lần gọi tool, ghi ra ngoài chờ người xác nhận | Giữ nguyên. |

Không đổi framework điều phối trước buổi báo cáo.

### 7.7. Lõi và gói

```
Bề mặt        Console điều hành | App công việc | (sau 22/10) SDK và API cho khách hàng cuối
Lõi           Điều phối và hồ sơ vụ việc | Kiến thức, bộ nhớ, sổ chi phí
              Agent: tạo, đánh giá, phát hành | Danh mục tool và cổng gọi tool
              Vụ việc và công việc: phương án, duyệt, lệnh việc, nghiệm thu
              Tài khoản, phạm vi, tenant, nhật ký, lưu trữ
Gói           Vinhomes (đầu tiên) | các gói sau
```

Quy tắc: gói biết lõi; lõi không biết gói.

Gói lĩnh vực mở rộng định dạng gói tenant mà OpenBot đã có (`server/src/tenant-package.ts`):

| Tệp | Nội dung | OpenBot đã có |
|---|---|---|
| `brand.yaml` | Tên, màu, logo | Một phần: mới có tên sản phẩm |
| `agents.yaml`, `agents/` | Định nghĩa agent, ca đánh giá | Có (chưa có ca đánh giá) |
| `knowledge.yaml` | Nguồn kiến thức | Có |
| `model.yaml`, `skills.yaml`, `channels.yaml` | Model, kỹ năng, kênh | Có |
| `domain.yaml` | Từ vựng, cây địa điểm, nhóm dịch vụ, các bước của vụ việc | Chưa |
| `tools/` | Bộ tool của lĩnh vực và bản khai | Chưa |

Phân loại sơ bộ module trong `services/vinhomes-api/src/vinhomes_api/`. **Dựa trên tên và vai trò đã biết; người chuyển phải rà từng module.**

| Nhóm | Module | Về đâu |
|---|---|---|
| Agent | `v3_agent_builder`, `v3_agent_evals`, `v3_agent_eval_sandbox`, `v3_agent_reviews`, `v3_agent_library`, `v3_agent_results`, `v3_room_agents` | Lõi |
| Điều phối | `v3_coordination`, `v3_session`, `v3_session_sources`, `v3_rooms`, `v3_room_runtime`, `v3_room_files`, `v3_team_board`, `v3_private_chats` | Lõi |
| Kiến thức, bộ nhớ, model | `v3_knowledge`, `v3_agent_knowledge`, `v3_memory`, `v3_learning`, `v3_models` | Lõi |
| Tool và kết nối | `v3_tool_gateway`, `tool_catalogue`, `v3_connections` | Lõi |
| Nền | `v3_auth`, `password_auth`, `v3_accounts`, `v3_admin`, `v3_audit`, `v3_files`, `storage`, `v3_routines`, `v3_config` | Lõi |
| Vụ việc và công việc | `v3_plans`, `v3_operations`, `v3_mutations`, `v3_completion`, `v3_triage`, `supervised_flow` | Lõi, từ ngữ và bước lấy từ `domain.yaml` |
| Riêng Vinhomes | `resident_*`, `v3_resident*`, `v3_reception*`, `reception_*`, `v3_security`, `v3_technical`, `v3_water`, `v3_specialized`, `v3_billing`, `v3_request_presentation`, `demo_*` | Gói Vinhomes |

Cách tách không làm gãy luồng đang chạy:

1. Tạo package lõi và kiểm tra ranh giới trong CI: lõi không import từ gói, không chứa danh sách từ của lĩnh vực.
2. Lớp mới (hồ sơ, lượt agent, sổ chi phí) viết thẳng vào lõi.
3. Lớp cũ chuyển theo từng nhóm ở bảng trên, giữ đường import cũ bằng tệp chuyển tiếp.
4. Mỗi bước chuyển phải qua bộ kiểm thử hiện có và một lượt chạy luồng thật.
5. Đổi tên biến môi trường `VINHOMES_*`, tên dịch vụ và bảng `vh_*`: **sau 22/10**. Đổi tên trước demo trực tiếp là rủi ro không đáng.

### 7.8. Tool

Hiện một tool phải khai báo ở tới chín nơi qua ba job đăng ký, có bảy dạng kết quả. Đích:

- Một bản khai cho mỗi tool. Mọi nơi khác sinh ra từ bản khai đó.
- Một dạng kết quả: trạng thái, dữ liệu, lỗi, nguồn. Trường nguồn là thứ hồ sơ trỏ tới.
- Một bộ mã lỗi. Một job đăng ký, có gỡ tool đã bỏ.
- Mỗi tool khai rõ nó đọc dữ liệu thật hay dữ liệu mẫu.

Việc bớt chặng mạng làm sau 22/10.

### 7.9. Giao diện: phòng điều hành

Mục tiêu: người xem thấy **agent đang làm việc trên một hồ sơ**, không thấy một cuộc trò chuyện.

| Vùng | Hiện gì |
|---|---|
| Danh sách vụ việc | Ba nhóm: cần bạn, đang chạy, đã xong. Mỗi dòng một câu tóm tắt. |
| Sàn làm việc | Mỗi agent và mỗi nhân viên là một thẻ sống: đang làm gì, thời gian, token. Đường nối hiện khi một agent phản đối hoặc hỏi agent khác. |
| Hồ sơ vụ việc | Các mục theo loại. Mỗi mục có nhãn nguồn bấm được. Bất đồng và mục bị chặn được làm nổi. |
| Thanh số liệu | Chi phí, thời gian, số nhận định có nguồn trên tổng số, số mục bị chặn. |
| Hỏi agent | Khung chat chỉ còn là một ngăn kéo. |

Thêm: **xưởng agent** hiện đường ống tạo, đánh giá, phát hành, để cổng chặn cứng được nhìn thấy. **Bản sắc**: màu thương hiệu lấy từ `brand.yaml` của gói, màu riêng cho từng agent, màu theo trạng thái. Bảng màu hiện tại trong `app/src/styles.css` gần như chỉ có xám.

Khung điều hướng gọn đã chọn ngày 04–05/10 vẫn giữ. Phần thay đổi là vùng nội dung của một vụ việc.

## 8. Ai giữ lớp nào

| Team | Lớp |
|---|---|
| Đông | Điều phối và hồ sơ vụ việc: lượt agent, các pha của phiên, Supervisor |
| Quang | Tool và kết nối; kiến thức, truy hồi, bộ nhớ |
| Hoàng | Tiếp nhận; luật kiểm nguồn; bộ đánh giá; sổ chi phí và báo cáo số liệu |
| Chiến | Backend lõi và cơ sở dữ liệu; giao diện phòng điều hành |
| Phái | Ranh giới lõi và CI; gói Vinhomes; kiểm thử đầu cuối; công cụ sinh dữ liệu; xưởng agent; vận hành demo |

Việc cụ thể của từng team: [PHAN_CONG_VA_BAN_GIAO_2026-10-08.md](PHAN_CONG_VA_BAN_GIAO_2026-10-08.md).

## 9. Kịch bản demo ngày 22/10

1. Một cư dân báo rò nước trong căn hộ và cần dọn. Trên phòng điều hành, hai agent cùng phân tích.
2. Agent Vệ sinh phản đối thứ tự công việc của agent Kỹ thuật, kèm nguồn. Supervisor hợp nhất.
3. Một nhận định không có nguồn bị chặn, thấy được trên màn hình. Kịch bản có sẵn một câu hỏi mà kho không có nguồn (nguyên nhân rò rỉ), để bước này xảy ra ở mọi lần chạy.
4. Bấm vào một bước của phương án, thấy nó dựa trên kết quả tool nào.
5. Thanh số liệu: vụ này tốn bao nhiêu, bao nhiêu nhận định có nguồn.
6. Vụ thứ hai của cùng căn hộ: agent nhắc lại lần sửa trước.
7. Đổi tệp thương hiệu của gói rồi tải lại trang: cùng nền tảng, diện mạo khác. Thương hiệu thứ hai là một tên tự đặt, không dùng tên một công ty có thật.
8. Bảng số trước và sau, trình bày đúng mức: đo trên khoảng 10 kịch bản mẫu do team viết, không phải số tiết kiệm trong vận hành thật.

**Hai điều nói rõ trong buổi demo.** Dữ liệu vận hành là dữ liệu mẫu. Luật "không nguồn thì không vào phương án" chứng minh mọi kết luận truy được về nguồn; nó không chứng minh nguồn đó đúng.

## 10. Tiêu chí nghiệm thu

| Tiêu chí | Cách đo |
|---|---|
| Agent đọc được kết luận của nhau | Đầu vào lượt rà soát của agent B chứa mục của agent A |
| Có phản biện | Trên bộ ca có mâu thuẫn: tỉ lệ ca mà mâu thuẫn được ghi thành phản đối |
| Không nguồn thì không vào phương án | Test: bước chỉ dựa trên giả định bị từ chối. Phiên thật: số bước không nguồn bằng 0 |
| Con số có nguồn | Tỉ lệ nhận định có con số mà con số nằm trong nguồn, trước và sau |
| Đo được chi phí | Mỗi vụ có token và tiền; tổng khớp nhật ký gọi model |
| Không quên | Vụ thứ hai của cùng đối tượng có mục ký ức trỏ về hồ sơ trước |
| Lõi không chứa Vinhomes | Kiểm tra ranh giới trong CI xanh; có danh sách module đã chuyển và chưa chuyển |
| Luồng cũ không gãy | Một yêu cầu đi hết vòng đời trên bản mới |
| Demo ổn định | Kịch bản tám bước chạy 5 lần liên tiếp không lỗi trong ba ngày đóng băng |
| Giao diện | PM duyệt trên ảnh chụp màn hình thật |

Team Hoàng đề xuất ngưỡng kèm bảng số nền ngày 13/10. PM chốt ngưỡng ngày 14/10 tại buổi trình diễn M1. Đặt ngưỡng trước khi đo là đoán.

## 11. Rủi ro và thứ tự cắt

| Rủi ro | Cách giảm |
|---|---|
| Bảy ngày làm việc cho cả bốn hướng | Hợp đồng chốt 12/10; làm song song trên ví dụ của hợp đồng; không thêm việc |
| Chỉ demo trực tiếp, không có video | Môi trường demo riêng; script đặt lại dữ liệu; nhà cung cấp model dự phòng; chế độ phát lại một phiên đã ghi, có ghi rõ là phát lại |
| Vòng rà soát làm chi phí tăng | Chỉ chạy khi cần; đọc bản cô đọng; trần token; đo từ ngày đầu |
| Đầu ra có cấu trúc làm agent trả lời kém hơn | So trên bộ đánh giá hiện có trước khi bật mặc định |
| Chuyển module làm gãy luồng | Chuyển từng nhóm, giữ tệp chuyển tiếp, chạy luồng thật sau mỗi bước; dừng chuyển từ 16/10 |
| Dữ liệu mẫu bị hiểu là dữ liệu thật | Gắn nhãn ở dữ liệu, ở kết quả tool và trên màn hình |
| Quy trình, phí, thời hạn do team tự viết hiện dưới tên một công ty có thật | Màn hình ghi "dữ liệu mẫu, chưa được đơn vị vận hành xác nhận"; PM cân nhắc dùng tên khu tự đặt cho buổi demo |
| Hai mươi người sửa cùng một chỗ | Mỗi hợp đồng một chủ; mỗi vùng code một team; gộp nhánh hằng ngày |

**Thứ tự cắt khi trễ** (cắt từ trên xuống, PM quyết định):

1. Chuyển nhóm "vụ việc và công việc" về lõi (đợt 2).
2. Xưởng agent dạng đường ống.
3. Dataset riêng theo agent.
4. Bản sắc màu theo gói (giữ màu mặc định mới).
5. Tóm tắt phiên dài.

**Không cắt:** hồ sơ vụ việc, luật kiểm nguồn, rà soát chéo, sổ chi phí, màn hình vụ việc, ký ức cho vụ thứ hai, kiểm tra ranh giới.

## 12. Sau 22/10

| Khi | Việc |
|---|---|
| Tháng tiếp theo | API hội thoại, SDK nhúng, danh tính do doanh nghiệp ký. Đổi tên biến môi trường, dịch vụ. Chạy lại hồ sơ cũ khi đổi model. |
| Sau đó | Lĩnh vực thứ hai (Vinpearl) dựng bằng gói. Nhiều tenant trên một hệ thống. Dữ liệu thật thay dữ liệu mẫu. Bớt chặng gọi tool. |
| Dài hạn | Kho gói và agent dùng lại giữa các lĩnh vực. Cắm agent bên ngoài qua chuẩn A2A. |
