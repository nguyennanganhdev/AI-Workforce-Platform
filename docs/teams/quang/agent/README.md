# Agent Kỹ thuật A2 — định nghĩa để phát hành

Thư mục này là nội dung của agent kỹ thuật mà Supervisor mời vào phòng điều phối khi ticket thuộc danh mục
`technical`. Team Quang sở hữu nội dung. Bản đầu (04/10/2026) do Team Chiến soạn từ `../general.md` để luồng
chạy được; cần Team Quang rà lại.

| Tệp | Nội dung |
|---|---|
| `technical-agent.md` | Chỉ dẫn của agent, nguyên văn. Lấy từ `general.md`: phạm vi, ranh giới, ba mức, 16 mã vấn đề, ba tool đọc và quy trình dùng tool, cách trả lời |
| `technical-agent.json` | Tên, mô tả, danh mục phục vụ, tool được cấp (`tools`) và các ca đánh giá |

## Phát hành

Backend, Bot (`agent-coordination/scripts/start_openbot.ps1`) và dịch vụ tool
(`services/vinhomes-api/scripts/start_technical_tools.ps1`) phải đang chạy. Từ 04/10/2026 tool host này còn phục vụ
`/internal/technical/v1/connections` cho kết nối MCP ngoài của agent BQL (Team Chiến; cần `TECHNICAL_CONNECTIONS_KEY`);
các tool kỹ thuật và `/call` không đổi.

```powershell
agent-coordination\scripts\publish_agent.ps1 docs\teams\quang\agent\technical-agent.json -Room management-room -Approve
```

Công cụ làm đúng luồng của platform: Ban quản lý tạo agent nháp và lưu cấu hình, từng ca đánh giá được chạy thật
trên Bot như một lượt nói trong phòng, chỉ khi mọi ca đạt mới nộp cho admin, và `-Approve` ghi quyết định duyệt
của admin (duyệt là phát hành). Bỏ `-Approve` thì bản nộp chờ admin.

Sửa chỉ dẫn hoặc ca đánh giá là tạo một agent nháp mới: cấu hình của agent đã duyệt không sửa được. Khi bản mới
được duyệt, công cụ thu hồi agent cùng tên đã phát hành trước đó, để phòng chỉ còn một agent kỹ thuật.

## Ca đánh giá

Mỗi ca có `instruction` (việc Supervisor giao), `ticket` (dữ liệu ticket), `must` (mọi mẫu phải xuất hiện trong
câu trả lời) và `must_not` (không mẫu nào được xuất hiện). Mẫu là biểu thức chính quy, không phân biệt hoa thường.

Với tool: `tool_results` là điều tool trả lời trong ca đó (tool không được nêu thì trả theo `tool_defaults`, tức
là không tìm thấy gì), `must_call` là tool bắt buộc phải gọi, `must_not_call` là tool không được gọi. Nhờ vậy một
ca nói rõ tool trả gì và agent phải nói gì sau đó, mà không cần dữ liệu thật trong database.

Một ca có thể có `messages`: những gì phòng đã có cho agent (ví dụ câu trả lời trước của nó), dùng cho ca câu hỏi
tiếp theo. Chạy bộ đánh giá mà không lưu gì: `python -m vinhomes.publish <định nghĩa> --check`.

Mười một ca hiện có: cầu dao nhảy có tia lửa (Level 1), điều hòa chảy nước (Level 2), rò nước trong tường (Level 2),
trần nứt võng (Level 1), vòi bếp rò đầu nối (Level 3, phải dẫn mã SOP mà tool trả về), nước thải trào ngược
(Level 2), mô tả không đủ để phân loại (không được gọi tool), yêu cầu đọc cảm biến (phải nói chưa có công cụ, không
đưa số đo), nước yếu khi đang có gián đoạn chung (phải nêu đúng giờ khôi phục đã công bố), tool báo lỗi (phải
ghi chưa tra được, không kết luận là không có gián đoạn), và câu hỏi tiếp theo của BQL (phải trả lời thẳng, không
chép lại bản phân tích trước).

Độ ổn định đo được với `gpt-5.4-mini`: 7 lần chạy cả bộ thì 4 lần đạt 10/10, 3 lần hỏng đúng một ca.

## Việc cần Team Quang

- Rà `technical-agent.md` so với `general.md`.
- Thay tám ca bằng bộ dữ liệu chuẩn của 16 mã vấn đề và các ca Level 1 bắt buộc (mục 12 của `general.md`).
- Chốt cách phân biệt `TECH.ARCH.PAINT_MOISTURE` với `TECH.PLUMB.CONCEALED_LEAK`: với mô tả "tường giáp phòng
  tắm ố vàng, ẩm, lan dần", model chọn mã đầu ở Level 3. Bảng mã cũng ghi `PAINT_MOISTURE` nâng Level 1 khi
  "nguồn ẩm vẫn tiếp diễn", cần xác nhận lại.
- Agent hiện có ba tool đọc. Tool đọc tài sản, cảm biến, lịch sử bảo trì chưa cấp vì chưa có ca đánh giá; tool
  ghi và tool tạo yêu cầu chưa mở cho phiên điều phối.
- Nạp SOP thật: database local chưa có SOP nào, nên `sop_kb.retrieve` luôn trả `NOT_FOUND`. Tài liệu SOP phải
  được cấp cho workspace của BQL (`document_acl`, loại `workspace`) thì agent mới đọc được.
- Quy trình dùng tool trong chỉ dẫn (mục QUY TRÌNH) là đề xuất của Team Chiến; cần Team Quang xác nhận, nhất là
  việc Level 1 không chờ tra cứu.

## Thay đổi ngày 05/10/2026 chạm tới phần của Team Quang

- **Tool host giữ nguyên ràng buộc role chỉ đọc và thêm.** Lịch chạy agent cần sửa, xóa dữ liệu nên chạy ở dịch vụ
  riêng (`server/src/room-routines`, role riêng), không dùng role của tool host. Không có gì thay đổi trong
  `technical-api/runtime.ts` hay quyền của `vinhomes_technical_api`.
- **Kết nối MCP ngoài (`technical-api/connection-routes.ts`).** Trước khi gọi máy chủ ngoài, tham số được kiểm bằng
  `plugins/content-governance.ts`; tham số chứa thông tin xác thực bị trả 400 và không rời hệ thống.
- **Module tri thức (`server/src/knowledge`).** `AuthorizedContext.userId` có thể là `null`: agent chuyên môn trong
  phiên Supervisor tra cứu thay cho đơn vị, không thay cho một người. Luật theo người (`document_acl` loại `user`)
  không khớp với `null`; nhật ký tra cứu ghi không có người. Agent chuyên môn đọc kho tri thức qua tool
  `knowledge.search` của cổng tool API, với vai trò `management`. Tài liệu SOP muốn agent kỹ thuật đọc được qua tool
  này thì phát hành vào kho tri thức với phạm vi tòa nhà hoặc phạm vi của đơn vị quản lý.

## Dữ liệu của Team Quang đưa vào dùng (07/10/2026)

Thư mục `../technical-data` lấy nguyên từ nhánh `dev_TeamQuang_ddhung04` (commit `186e121`). Hai cách dùng, theo
đúng giới hạn trong README của bộ dữ liệu (tham khảo nội bộ, chưa phát hành, không dùng cho cư dân):

- **Bộ đánh giá thêm cho agent kỹ thuật.** `build_quang_cases.py` chuyển 16 ca giả lập (`SYNTHETIC_CASES.jsonl`) và
  16 ca biên (`EDGE_CASES.jsonl`) thành `technical-agent-quang.json` (cùng chỉ dẫn và tool với
  `technical-agent.json`). Chỉ những gì nhãn nói được kiểm bằng mẫu: nhãn chuyển ngay (escalate_now…, kính hoặc vật
  rơi, safety_escalation…) phải có Level 1 và dòng `LEVEL 1 - CHUYỂN NGƯỜI TRỰC NGAY`; nhãn hỏi trước (ask_,
  request_, check_, clarify_, split_, differentiate_) không được Level 1 và phải có câu hỏi bổ sung; còn lại kiểm mã
  vấn đề. Điều cấm diễn đạt bằng lời nằm trong `expected` để người đọc xét. Chạy không lưu gì:
  `python -m vinhomes.publish docs/teams/quang/agent/technical-agent-quang.json --check`.
  Lần chạy 07/10 (gpt-5.5, Docker local): **30/32 đạt**. Hai ca trượt cần Team Quang xem:
  - `quang-a2-007` (khung kính vách tắm có vẻ lỏng): agent xếp Level 3, nhãn là nguy cơ kính rơi (Level 1). Chỉ dẫn
    có nêu kính có nguy cơ rơi là điều kiện nâng Level 1, nhưng agent không áp cho "khung kính có vẻ lỏng".
  - `quang-e-007` (thoát chậm rồi tràn qua cửa kính, ron còn nguyên): agent chọn `TECH.PLUMB.SUPPLY_DRAIN_JOINT` và
    nâng Level 1, nhãn là `TECH.PLUMB.SHOWER_SEAL` và cần phân biệt thoát nước với ron trước. Có thể là chỉ dẫn
    thiếu ví dụ, có thể là nhãn cần xem lại.
  Bộ này không thay 11 ca của `technical-agent.json` khi phát hành: đánh giá trên máy chủ nhận tối đa 12 ca một lượt.
- **Kho tham khảo nội bộ của BQL.** `bql-knowledge/ky-thuat/tham-khao-triage-a2.md` là bản của
  `technical-data/rag/corpus/01-vinhomes/cau-hoi-thuong-gap-a2.md` có thêm `title` (tiêu đề nói rõ chưa được duyệt,
  không phải SOP). Phát hành bằng `server/src/knowledge/publish-bql.ts ../docs/teams/quang/agent/bql-knowledge
  --site ocean-park-1 --user <quản trị viên>` vào phạm vi các đơn vị quản lý: agent của BQL có `knowledge.search`
  đọc được, Lễ tân và cư dân không. Agent kỹ thuật hiện chưa có `knowledge.search`; thêm tool này là một phiên bản
  mới, cần chạy lại đánh giá.
