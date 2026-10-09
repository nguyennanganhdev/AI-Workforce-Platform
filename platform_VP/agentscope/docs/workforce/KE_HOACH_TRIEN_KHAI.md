# Kế hoạch triển khai AI Workforce Platform và phân công cho 6 thành viên

Ngày lập: 09/10/2026. Cập nhật: 10/10/2026. Phiên bản kế hoạch: 1.4.3.

Hiệu chỉnh 1.4.3 chốt định danh nhiều ticket/hộp chat của cùng một khách hàng. Backend đối tác cấp `external_ticket_id` và một `external_conversation_id` riêng cho từng hộp chat; platform bind bất biến mỗi ticket ngoài vào đúng workflow, conversation và group runtime nội bộ. Mọi reply, close, approval, SSE/history và event projection đều kiểm tra binding này trước khi dispatch; Leader không dùng nội dung tự nhiên để đoán ticket/group. Hai ticket có thể dùng cùng AgentDefinition đã phát hành nhưng bắt buộc có group/session/context/approval/operation riêng, nên xử lý xen kẽ không làm lẫn trạng thái.

Hiệu chỉnh 1.4.2 làm cho lifecycle độc lập lĩnh vực. POST khách hàng chờ kết quả của lượt agent hiện tại trong giới hạn thời gian rồi trả `200` cùng nội dung và IDs; `202` chỉ là fallback khi lượt đó chưa xong, không phải dấu hiệu workflow thuộc loại bất đồng bộ. Sau mỗi lượt, platform trả `workflow_state` và `next_action` để backend biết cần reply/approval/close, theo dõi bằng SSE hay polling, hoặc không làm gì. Tracking chỉ cần khi request/operation còn pending; Provider Event chỉ dùng nếu protocol hỗ trợ, SSE luôn có thể thay bằng GET request/history. Lập kế hoạch, tra cứu, chọn phương án và booking trả kết quả ngay không bị ép qua luồng nhân viên/gọi thợ.

Bản 1.4.3 giữ nguyên quy tắc HTTP và ba pattern lifecycle của 1.4.2, đồng thời làm rõ một ticket ngoài tương ứng một workflow/group runtime; tạo ticket mới mới tạo group mới, còn message tiếp theo của ticket cũ tiếp tục group cũ. Pattern vẫn được chọn từ manifest/policy, loại side effect và kết quả tool đã xác minh, không hardcode theo tên domain. Giữ nguyên task ID, owner, branch và các thư mục của sáu thành viên; các README mang nhãn v1.4 phải áp dụng hiệu chỉnh này. Giữ nguyên nghiệp vụ MCP/Builder/eval/publish/reuse, agent độc lập và mapping v1.2–1.3. Đây là kế hoạch/scaffold, chưa triển khai API/runtime. Mục 2.6–2.7 và 17 quy định luồng chính; mục 6, 7–12 và 15 quy định contract nội bộ, phân công và nghiệm thu.

Quyết định ở bản 1.3: chỉ có role tài khoản `AREA_MANAGER`; đăng ký vẫn chọn domain và area. Request đối tác phải được mapping tới đúng domain, area và **tài khoản ban quản lý đích**, không phát chung cho mọi manager cùng area. Mục 2.6 là đặc tả mapping/filter; scope và phân công mục 6–12 đã cập nhật tương ứng. Mọi chỉ dẫn ở bản 1.2 về bỏ domain/area/AREA_MANAGER đều bị thay thế, không được triển khai theo chỉ dẫn cũ.

Quyết định ở bản 1.2: “tạo team agent” trong Builder nghĩa là tạo nhiều agent độc lập trong một lần chat (batch build). Mọi agent sau phát hành nằm trong thư viện chung của người dùng. Leader chỉ chọn thành viên group khi có yêu cầu thực tế, dựa trên toàn bộ thư viện khả dụng. Lịch sử batch không quy định thành viên group hay giới hạn khả năng dùng agent.

Bản này thay thế các mô tả team template/manifest/version/deployment riêng ở bản 1.0–1.1. Vẫn giữ kiểm tra trùng nghiệp vụ và tái sử dụng agent ở mục 2.5; các task ID và thư mục sở hữu giữ nguyên, nội dung được cập nhật để sáu người code cùng một mô hình.

Repository gốc: `D:\AI-Workforce-Platform\platform_VP\agentscope`.
Trong tài liệu, mọi đường dẫn tương đối đều tính từ repository này, trừ khi ghi rõ khác.
Khi clone sang máy khác, dùng thư mục chứa `pyproject.toml`, `src/agentscope` và `examples/web_ui` làm gốc.

Đây là kế hoạch triển khai và hợp đồng phối hợp. Các thư mục đi kèm mới được tạo để phân vùng công việc; chưa có tính năng Workforce nào được triển khai bởi việc tạo tài liệu này.
Các kết luận hiện trạng bên dưới dựa trên đọc mã nguồn tại thời điểm lập kế hoạch, không phải xác nhận đã chạy toàn bộ test hay triển khai production.

Contract gửi cho đối tác nằm tại `docs/workforce/CONTRACT_TICH_HOP_DOI_TAC.md`. File đó là tài liệu sử dụng API độc lập để gửi ra ngoài: chỉ mô tả endpoint do platform host, field đối tác phải gửi/nhận, lỗi/retry, `next_action` và SSE/history tùy chọn. File contract không phân công thành viên, không chỉ dẫn cấu trúc code nội bộ, không mô tả API do đối tác phải host và không mô tả cách họ tổ chức tool trong MCP. Mọi quyết định kiến trúc, persistence, owner module, folder code, thứ tự triển khai và tiêu chuẩn nghiệm thu chỉ nằm trong kế hoạch này; sửa contract không mặc nhiên thay đổi kế hoạch.

## 1. Cách giao tài liệu này cho AI

Thành viên gửi toàn bộ file này cho AI có quyền truy cập repository, kèm câu:

> Tôi là **[họ tên đầy đủ]**. Hãy đọc kế hoạch này, kiểm tra repository hiện tại, xác định đúng module tôi sở hữu và triển khai các đầu việc chưa hoàn thành của tôi theo thứ tự trong kế hoạch. Đọc phần hợp đồng chung trước khi code. Tự chạy kiểm tra phù hợp, ghi bàn giao vào thư mục của tôi. Nếu module khác chưa có, dùng port và fake trong test theo hợp đồng để tiếp tục; không tự sửa module của người khác.

AI phải thực hiện:

1. Đọc `AGENTS.md` nếu có, đọc tài liệu này và các README trong vùng công việc; kiểm tra `git status` và code hiện hữu trước khi sửa.
2. Xác định thành viên bằng họ tên đầy đủ hoặc slug trong bảng mục 5. Không nhầm Nguyễn Chí Hoàng với Phan Huy Hoàng.
3. Đối chiếu code và bàn giao đã có để tiếp tục phần còn thiếu, không viết lại phần đã hoàn thành.
4. Chỉ sửa các thư mục được giao. Đọc module khác được phép; sửa phải chuyển yêu cầu sang chủ sở hữu bằng file bàn giao.
5. Nếu hợp đồng chung chưa được hiện thực hóa, triển khai logic độc lập, adapter và test double trong vùng riêng theo bản hợp đồng trong file này. Không tự tạo bản contracts dùng chung thứ hai.
6. Ưu tiên code chạy được, nối API thật và kiểm tra hành vi. Fake phải nằm trong test/demo được đánh dấu; không trả dữ liệu giả thành công trong production.
7. Giữ đúng một role tài khoản `AREA_MANAGER`, giữ chọn domain/area; không thêm role admin, partner-user hoặc evaluator-user. Credential máy của đối tác không phải role đăng nhập mới. Không tự đổi yêu cầu thành bật MCP là cấp mọi tool cho agent.
8. Không đọc/in secret từ `.env` để đưa vào tài liệu, fixture, prompt hay log. Không xóa thay đổi đang có, không tự commit/push/deploy nếu chưa được yêu cầu.
9. Sau mỗi phần có thể bàn giao, cập nhật `STATUS.md` trong thư mục bàn giao cá nhân: file đã sửa, API/export, test đã chạy và kết quả, phần còn thiếu, yêu cầu tích hợp.
10. Nếu thiếu credential hoặc dịch vụ thật, hoàn thành unit/contract tests với fake, ghi rõ live verification còn thiếu. Không coi test với fake là đã xác minh booking thật.
11. Trước khi sinh agent mới, kiểm tra agent đã build cho cùng nghiệp vụ theo mục 2.5. Agent phù hợp được tham chiếu để tái sử dụng; không copy prompt/config sang agent ID mới rồi gọi đó là reuse.
12. Builder tạo một hoặc nhiều agent độc lập. Không tạo team template, team deployment hoặc group production khi build/phát hành. Chỉ runtime xử lý request mới tập hợp agent vào group; bài eval phối hợp dùng group thử nghiệm riêng.
13. Đọc mục 2.6 trước khi code identity, query, inbound API hoặc runtime. Không dùng area làm thay thế tài khoản đích, không dùng `external_user_id` làm owner platform, không để LLM quyết định mapping/authorization.
14. Đọc mục 2.7 và toàn bộ mục 17 trước khi làm phần API/event/workflow. Hoàn thành cả task bổ sung v1.4 mang prefix của mình; README folder con và handoff nêu ranh giới, không tạo outbound webhook/receiver ngoài contract. Agent ngủ nghĩa là checkpoint vào DB và giải phóng lượt chạy; không giữ HTTP POST/model loop để chờ thợ.
15. Backend/app thật của đối tác không có trong repo: triển khai API platform, guide và mock hai phía; ghi rõ phần cần đối tác làm. Không báo tích hợp production hoàn thành chỉ vì mock hoặc folder đã tồn tại.

Khi chưa có thông tin chuyên môn từng người, việc phân công dưới đây dựa trên ranh giới module để tối đa hóa làm song song, không phải đánh giá năng lực cá nhân.

## 2. Nghiệp vụ đã chốt

### 2.1. Một role AREA_MANAGER, nhiều tài khoản ban quản lý

- Chỉ có một role tài khoản sản phẩm: `AREA_MANAGER`. Nhiều người đăng ký/đăng nhập đều nhận role này; mỗi tài khoản tạo agent cho khu vực mình quản lý. Role trả lời được làm gì, còn domain/area/tài khoản trả lời quản lý dữ liệu nào.
- Giữ bước chọn domain và area khi đăng ký, backend kiểm tra area thuộc domain. V1 theo cấu trúc hiện tại: một tài khoản có một domain/area đang quản lý; không tự mở rộng sang nhiều membership. Việc xác minh quyền quản lý là trạng thái onboarding, không phải role mới. Chỉ tự chọn tên area không đủ để được nhận request production; cần xác minh/invitation hoặc provisioning có audit theo mục 2.6.
- `manager_account_id` là ID ổn định của tài khoản ban quản lý (`auth_users.id`), không phải tên hiển thị, role hay mã cư dân. V1 chưa tách tài khoản tổ chức và tài khoản nhân viên; không suy ra mọi người cùng area dùng chung platform logic.
- Đối tác có thể cung cấp MCP và gửi request từ backend đã xác thực. Hai tích hợp này độc lập: bật MCP không cấp quyền gửi request tới manager; credential inbound không tự cấp tool hoặc quyền sửa agent. Không xây role hay portal đăng nhập riêng cho đối tác.
- Danh sách MCP đối tác được đưa vào hệ thống bằng tệp cấu hình catalog và lệnh import của đội phát triển/vận hành. Đây là quy trình triển khai phần mềm, không phải role admin trong ứng dụng.
- Mọi tài nguyên Workforce thuộc scope `(tenant_id, domain_id, area_id, manager_account_id)`. Hạ tầng platform có thể dùng chung nhưng MCP connection/credential, agent, build, request, hội thoại/group và approval phải truy cập đúng scope. Thư viện chung là chung cho agent của **một tài khoản ban quản lý**, không phải chung cho mọi manager cùng domain/area.
- Request từ đối tác tới đúng tài khoản qua mapping đã cấp quyền; không broadcast tới tất cả manager cùng area. Ngoài scope owner còn có ranh giới người gửi/hội thoại bên đối tác để không trộn dữ liệu của hai khách hàng cùng được một ban quản lý phục vụ.
- Nếu sau này có chia sẻ giữa các tài khoản ban quản lý, phải có grant riêng; không tự suy ra tính năng này ở v1. Dữ liệu area dùng chung có sẵn chỉ được đưa vào Workforce qua policy riêng được duyệt, không coi cùng area là đủ quyền.

### 2.2. Bật MCP và build agent

```text
Đối tác cung cấp MCP → MCP có trong danh sách tích hợp
→ Người dùng bật MCP, nhập thông tin kết nối nếu cần
→ Platform discovery và đăng ký toàn bộ tool MCP công bố cho kết nối đó
→ Kho tool khả dụng của người dùng
→ Người dùng chat yêu cầu tạo một agent hoặc tạo nhiều agent một lần
→ Builder xác định năng lực cần có và kiểm tra agent đã có cho từng nghiệp vụ
→ Báo agent tái sử dụng được; người dùng xem đề xuất có phần dùng lại/phần còn thiếu
→ Agent đã đủ năng lực: tham chiếu agent/version cũ; agent cần mới/nâng cấp: tự chọn tool
→ Chỉ sinh cấu hình, prompt, model, KB/skill và binding cho phần cần mới/nâng cấp
→ Validate/Evaluate từng agent → Người dùng xem kết quả và bấm Phát hành
→ Các agent độc lập xuất hiện trong cùng thư viện platform

Sau đó, khi có yêu cầu thực tế:
Request nội bộ có manager scope / request đối tác qua mapping mục 2.6
→ Leader chọn agent từ toàn bộ thư viện khả dụng của đúng tài khoản ban quản lý
→ Thêm các agent cần thiết vào group của yêu cầu → phối hợp xử lý
```

Đăng ký tool là lưu descriptor, schema, nguồn MCP và phiên bản vào catalog để tìm kiếm; phần thực thi vẫn gọi MCP từ xa hoặc qua transport đã cấu hình. Không tải toàn bộ code tool về để chạy tùy tiện.

Một agent có thể chọn tool từ nhiều MCP; một MCP có thể phục vụ nhiều agent. Bật MCP không tự thêm tool vào agent đã phát hành.

Nếu thiếu năng lực bắt buộc, Builder trả chẩn đoán cụ thể và chặn phát hành với yêu cầu đó. Có thể đề xuất phương án giảm phạm vi nhưng phải được người dùng đồng ý.
Agent chỉ lập kế hoạch/điều phối không bắt buộc có tool đối tác nếu năng lực của nó được đáp ứng bằng suy luận, KB và công cụ nội bộ như `TeamSay`. Agent cam kết booking thì bắt buộc có tool booking thật hoặc adapter hợp lệ; prompt không thay thế được tool.

### 2.3. Tạo lẻ/tạo hàng loạt và tập hợp group lúc thực thi

| Thời điểm | Đối tượng được tạo/quản lý | Kết quả |
|---|---|---|
| Build một agent | Một draft và cấu hình agent | Sau eval/publish có một agent độc lập trong thư viện |
| “Build team agent” bằng một lần chat | Một batch theo dõi tiến độ, nhiều draft agent độc lập | Sau eval/publish có nhiều agent độc lập trong cùng thư viện |
| Nhận request thực tế | Run, group, thành viên/session và trạng thái xử lý | Leader chọn subset agent phù hợp, có thể từ nhiều batch khác nhau hoặc tạo lẻ |

- UI ưu tiên gọi thao tác Builder là **Tạo một agent / Tạo nhiều agent**. Nếu vẫn dùng nhãn “Tạo team agent”, giải thích đây là tạo hàng loạt; không yêu cầu user thiết kế nhóm xử lý hay gắn sẵn request.
- Xác nhận đề xuất build chỉ xác nhận danh sách agent cần tạo/nâng cấp và agent đã có. Mỗi agent có ID, manifest, evaluation, version, deployment và Settings riêng.
- `batch_id` phục vụ tiến độ/lịch sử build. Nó không là team ID, không có leader/member roster dùng cho production, không chứa workflow cố định và không là bộ lọc candidate của Leader.
- Builder không tự phát hành. Người dùng xem báo cáo từng agent, có thể bấm phát hành nhiều agent đạt cùng lúc. Agent không đạt giữ draft/lỗi riêng; nếu chọn phát hành một phần thì UI phải thể hiện rõ phần được chọn. Không buộc các agent cùng batch phải luôn phát hành/nâng cấp cùng nhau.
- Sau phát hành, tất cả agent nằm trong thư viện chung của người dùng, bất kể tạo lẻ hay tạo hàng loạt. Chat/Settings trực tiếp với mỗi agent không cần mở batch gốc.
- Leader là bộ điều phối runtime của platform. Nó đọc request, tìm các agent published/khả dụng theo nghiệp vụ và thêm vào group; không cần tạo thêm một Leader cho mỗi batch.
- Chỉ lúc có request mới tạo các session xử lý và xác định ai tham gia. Agent Plan có thể chủ trì ca du lịch sau khi Leader chọn nó; agent không được hardcode danh sách “đồng đội cùng batch” trong prompt.
- Group/run giữ version pin và state phục vụ hội thoại. Request mới có thể cần tập agent khác; trong hội thoại đang chạy, thêm/bớt agent theo nhu cầu nhưng không làm mất pending question, approval hoặc tác vụ đang chạy. Lưu lịch sử membership để giải thích routing.
- Giữ thao tác thêm agent thủ công lúc hội thoại, chat riêng với agent và `@agent` trong group. Xóa/đóng group hoặc xóa lịch sử batch không xóa các agent trong thư viện.

Ví dụ: một lần chat tạo Plan/Hotel/Car/Calculator, một lần khác tạo Technical. Sau đó request “tìm khách sạn” có thể chỉ dùng Hotel; “lên kế hoạch và đặt chuyến đi” dùng Plan/Hotel/Car/Calculator; “phòng bị hỏng điều hòa” dùng Technical, thêm Hotel nếu cần tra booking. Các group không phụ thuộc lần build nào đã tạo những agent đó.

### 2.4. Case nghiệm thu du lịch

Kho agent gồm Planner, Hotel, Car, Calculator, Technical. Người dùng yêu cầu đi Bãi Cháy cuối tuần, ngân sách 10 triệu.

1. Leader chọn Planner, Hotel, Car, Calculator theo năng lực; không kéo Technical vào nếu chưa có yêu cầu kỹ thuật.
2. Planner hỏi các thông tin thiếu: số người, điểm đi, ngày/giờ, số đêm và ưu tiên chi tiêu; không hỏi lại dữ kiện đã có.
3. Planner nhận ưu tiên dành nhiều tiền cho hotel, phối hợp Hotel tìm phòng và Car tìm chuyến phù hợp địa điểm/thời gian.
4. Calculator tính bằng công cụ xác định, giữ 2 triệu ăn uống theo yêu cầu, tính cả phí/thuế đã biết và chỉ ra chi phí chưa xác minh.
5. Planner trình bày phương án, tổng tiền, nguồn báo giá và hạn hiệu lực. Người dùng chọn trước khi booking.
6. Người dùng có thể `@hotel` hỏi tiện ích khách sạn đang được tư vấn. Hotel nhận đúng context và trả lời trong group.
7. Booking chỉ chạy sau xác nhận cụ thể của người dùng cho phương án/giá. Nếu một phần thành công, một phần lỗi, báo trạng thái thực tế và phương án xử lý.

Chuẩn hóa thời gian tương đối từ thời điểm gửi message và timezone người dùng; hiển thị ngày cụ thể để kiểm tra. Không hardcode “cuối tuần” trong prompt. Ví dụ fixture đóng băng tại 09/10/2026, timezone `Asia/Ho_Chi_Minh`, thì thứ Bảy/Chủ nhật là 10–11/10/2026; số đêm vẫn phải xác định từ nhu cầu.

### 2.5. Phát hiện trùng nghiệp vụ và tái sử dụng agent đã build

#### Nguyên tắc sản phẩm

Trước mỗi lần tạo agent đơn hoặc từng agent trong batch, Builder phải tìm agent cùng nghiệp vụ trong thư viện của người dùng. Áp dụng cho mọi agent đã tạo lẻ hoặc hàng loạt. Một agent nghiệp vụ có ID ổn định và nhiều phiên bản, có thể được nhiều run/group chọn sau này; không tạo bản sao vì user yêu cầu một batch mới.

Khi đã xác định agent cũ đáp ứng đầy đủ, platform báo rõ tên, phiên bản và năng lực phù hợp. Với batch, đây là một phần trong bước xác nhận đề xuất đang có: đánh dấu “Đã có — không cần tạo lại”. Nếu người dùng chỉ yêu cầu agent đơn đã có, trả trạng thái `completed_reused` với liên kết mở agent/chat/settings, không tạo thêm draft, agent, version hoặc deployment chỉ để đổi tên.

Ví dụ: đã có **Hotel Agent** tìm và đặt khách sạn. Khi người dùng yêu cầu “tạo team agent du lịch” với ý nghĩa tạo hàng loạt Plan, Hotel, Car, Calculator, Builder thông báo:

> Đã có Hotel Agent v3 đáp ứng phần tìm và đặt khách sạn trong thư viện. Chỉ cần tạo thêm Plan, Car và Calculator. Sau khi phát hành, Leader có thể chọn các agent phù hợp khi bạn gửi yêu cầu.

Số agent mới trong ví dụ là 3, không phải 4. Nếu cả bốn đã tồn tại và tương thích, báo đã có đủ và trả link tới bốn agent; không tạo thêm agent/version/deployment, không sinh team artifact hay group production. Có thể lưu build session/batch kết quả để người dùng xem lại yêu cầu.

#### Cách xác định cùng nghiệp vụ

So sánh theo mục tiêu, trách nhiệm, hành động nghiệp vụ, input/output, phạm vi dữ liệu/đối tượng phục vụ, ràng buộc bắt buộc, KB/skill liên quan và policy được phép thực thi. Tên, câu chữ prompt hay việc chọn model khác nhau không đủ để kết luận là nghiệp vụ mới. Tool giống nhau cũng không đủ để kết luận hai agent giống nghiệp vụ.

Phân biệt cấu hình năng lực với dữ liệu một lần chạy: ngày đi, ngân sách, tên khách sạn được chọn, số người của một chuyến đi là input của run; chúng không làm phát sinh agent nghiệp vụ mới. Giới hạn cố định như chỉ phục vụ một hệ thống khách sạn hoặc chỉ tư vấn, không booking, có thể là khác biệt đáng kể cần kiểm tra.

Tách hai kết luận: `match_type` trả lời mức độ trùng nghiệp vụ; `reuse_status` trả lời agent có dùng được ngay không. Có cùng nghiệp vụ nhưng MCP bị tắt vẫn là agent cũ cần khôi phục, không phải lý do tạo agent khác.

| Kết quả | Hành vi bắt buộc |
|---|---|
| Cùng nghiệp vụ, đáp ứng đầy đủ, published và khả dụng | Báo đã có, giữ nguyên agent ID; version được ghi nhận để giải thích kết quả build. Runtime chọn/pin version lúc nhận request, không theo batch |
| Cùng nghiệp vụ nhưng agent còn draft/đang eval | Báo bản đang xây, dẫn tới tiếp tục draft/job đó; chưa được đưa draft vào runtime production |
| Cùng nghiệp vụ, MCP tắt/credential lỗi/agent tạm ngưng | Báo điều kiện cần khôi phục, không âm thầm clone hoặc coi agent là khả dụng |
| Chỉ đáp ứng một phần, ví dụ tìm hotel nhưng chưa booking | Nêu phần thiếu; đề xuất tạo version nâng cấp của cùng agent khi người dùng đồng ý. Nếu có phần nghiệp vụ độc lập thật sự thì chỉ build phần đó |
| Tên giống nhưng nghiệp vụ khác, ví dụ booking hotel và bảo trì hotel | Cho tạo agent riêng khi mục tiêu/phạm vi khác đã được mô tả rõ |
| Có vài ứng viên tương tự, chưa đủ căn cứ | Hiển thị khác biệt, hỏi làm rõ; không tự gộp theo tên hoặc một điểm similarity |
| Không có agent phù hợp trong scope | Tiếp tục build mới với tool capability validation như bình thường |

Trường hợp nâng cấp vẫn đi qua draft/eval/publish và giữ `agent_id`, không sửa bản đang chạy. Nếu user muốn agent chỉ đọc nhưng agent cũ có policy hành động vượt yêu cầu, phải xử lý compatibility hoặc nâng cấp cấu hình; không tự tái sử dụng với quyền rộng hơn yêu cầu. Agent của user khác không xuất hiện trong kết quả tìm kiếm.

#### Luồng xử lý và kiểm tra lại

```text
Yêu cầu → phân rã nghiệp vụ từng agent → tìm agent/draft đã có trong scope
→ so sánh capability + phạm vi + input/output + policy + availability
→ đề xuất cho từng vị trí: reuse / resume / revise / create / clarify / repair
→ người dùng xác nhận danh sách agent hoặc chọn cách xử lý phần chưa rõ
→ backend kiểm tra lại decision và catalog revision
→ báo agent đã có; chỉ generate draft riêng cho từng agent mới/nâng cấp
→ validate/evaluate từng agent thay đổi → phát hành vào thư viện chung
```

Reuse nguyên trạng không cần chạy lại Builder để sinh prompt và không phát hành lại agent cũ. Mỗi agent mới/nâng cấp phải có eval của nó, bao gồm khả năng giao tiếp/handoff bằng đồng đội giả lập khi cần. Bộ kiểm thử tích hợp runtime có case phối hợp nhiều agent trong group thử nghiệm; đây không phải phát hành một team sản phẩm. Không chạy toàn bộ eval mỗi khi user gửi một request thường; runtime kiểm tra khả dụng/policy và chọn agent theo request.

Thông báo phải chỉ rõ: agent/phiên bản dùng lại, phần mới sẽ tạo, phần cần nâng cấp, lý do khớp/không khớp và blocker nếu có. Khi reject đề xuất reuse vì cho rằng nghiệp vụ khác, Builder hỏi điểm khác và cập nhật yêu cầu; không có nút tạo bản sao cùng nghiệp vụ chỉ để vượt kiểm tra.

Kiểm tra trùng ở ba điểm: khi lập đề xuất, trước tạo draft/identity mới, và trước publish. Hai tab build đồng thời có thể nhìn cùng một catalog cũ; backend phải recheck và giữ một identity chuẩn cho cùng `business_key` trong scope. Request sau nhận `AGENT_ALREADY_EXISTS` hoặc `AGENT_BUILD_IN_PROGRESS` cùng reference hợp lệ trong scope; không chỉ chặn bằng frontend.

`business_key` chuẩn hóa từ hồ sơ nghiệp vụ và có phiên bản quy tắc; không hash nguyên prompt hay tin key do client gửi. Semantic search/LLM chỉ đề xuất ứng viên, hard checks và bước làm rõ quyết định khả năng reuse. Khóa DB bảo đảm duy nhất cho nghiệp vụ đã chuẩn hóa; không tuyên bố có thể nhận diện tuyệt đối mọi cách diễn đạt ngôn ngữ tự nhiên. Trường hợp mơ hồ cần được làm rõ trước khi cấp identity mới.

Nếu đã có dữ liệu trùng từ trước, báo các ứng viên và chọn một để tham chiếu; không tự xóa/gộp agent làm mất lịch sử. Reuse định nghĩa/version không có nghĩa dùng chung session/memory/approval: mỗi group/run vẫn có session và state riêng. Xóa group hoặc lịch sử batch không xóa agent. Agent/version còn được run hoặc lịch sử cần giữ tham chiếu không được hard-delete làm đứt liên kết; archive áp dụng cho khả năng được chọn ở request mới.

#### Phân công bổ sung, giữ nguyên các thư mục sở hữu

| Thành viên | Trách nhiệm |
|---|---|
| Nguyễn Chí Hoàng | Contracts reuse/reference, migration uniqueness và nối các port |
| Nguyễn Phương Đông | Kiểm tra tool binding/availability của agent ứng viên để tránh reuse agent không chạy được |
| Bùi Hữu Nghĩa | Phát hiện trùng trước generate, so sánh nghiệp vụ, thông báo và đề xuất dùng lại/nâng cấp |
| Phó Tiến Anh | Thư viện agent chuẩn theo identity/version, batch theo dõi nhiều draft độc lập, dedupe khi ghi DB/publish |
| Phan Huy Hoàng | Khi có request mới chọn agent từ thư viện và materialize vào group/run với session riêng, pin version và bảo toàn lifecycle agent |
| Phan Hoàng Dũng | Kiểm tra runtime/approval không dùng chéo khi reuse và E2E chống tạo trùng |

### 2.6. Mapping và filter request tới đúng tài khoản ban quản lý

Đây là thiết kế cần triển khai, không phải mô tả API đã có. Quy tắc chốt: **đúng domain chưa đủ; đúng area cũng chưa đủ; phải xác định duy nhất tài khoản ban quản lý đích trước khi đọc kho agent hoặc khởi chạy Leader.**

#### 2.6.1. Các định danh không được dùng lẫn nhau

| Trường | Ý nghĩa và nguồn tin cậy |
|---|---|
| `tenant_id`, `domain_id` | Suy ra từ credential đối tác đã xác thực đối với inbound; từ tài khoản/membership đã xác thực đối với manager UI. Không lấy quyền từ body/header tự khai |
| `partner_client_id` | Định danh backend tích hợp của đối tác, giữ ổn định khi rotate API key. Không phải tài khoản ban quản lý |
| `external_management_ref` | Mã ban quản lý do đối tác sử dụng, ví dụ `BQL-OP1-A`; chỉ là khóa tra mapping trong namespace của partner client, không phải bằng chứng quyền |
| `area_id` | Khu vực thuộc domain, lấy từ mapping được duyệt và kiểm tra với membership hiện hành của tài khoản đích |
| `manager_account_id` | `auth_users.id` của tài khoản nhận request và sở hữu kho agent; không lấy từ người gửi bên đối tác |
| `external_user_id` | Khách/cư dân gửi yêu cầu qua backend đối tác; chỉ duy nhất trong namespace partner client. Backend đối tác phải xác thực người này, không nhận payload trực tiếp từ browser chưa xác thực |
| `external_conversation_id`, `external_request_id` | Mã hội thoại và mã message/request để giữ context và chống gửi trùng; không tạo quyền sở hữu platform |
| `route_id`, `route_revision` | ID và phiên bản mapping do platform quản lý; lưu cùng request để giải thích đích đã chọn, không là secret/bearer credential |

Trong code AgentScope cũ, `user_id` dùng để lưu tài nguyên phải được adapter ánh xạ thành **`manager_account_id`** đã resolve. Không dùng `partner_client_id` hoặc `external_user_id` vào vị trí đó. Audit lưu actor thực tế riêng, không giả rằng manager đã trực tiếp gửi một yêu cầu do đối tác gửi.

#### 2.6.2. Hai lớp mapping, mỗi lớp có một nhiệm vụ

1. **Credential → partner/domain:** tái sử dụng `partner_api_clients`, `partner_api_credentials`, `authenticate_partner_api_key` và `PartnerPrincipal`. Một client hiện thuộc một domain; key đã hết hạn/thu hồi hoặc client/domain inactive bị chặn. Không coi API key của domain là quyền truy cập mọi tài khoản trong domain.
2. **Partner reference → manager scope:** thêm `PartnerManagerRoute` chứa `route_id`, `tenant_id`, `partner_client_id`, `domain_id`, `external_management_ref`, `area_id`, `manager_account_id`, `status`, `revision`, quyền inbound và audit. Unique active route trên `(tenant_id, partner_client_id, external_management_ref)`; một ref không được trỏ đồng thời tới hai manager. Nhiều ref có thể tới cùng manager nếu được cấp quyền rõ.

Ví dụ dữ liệu giả:

| Partner client / domain đã xác thực | External ref | Area | Tài khoản đích |
|---|---|---|---|
| `client-vh` / `vinhomes` | `BQL-OP1-A` | `ocean-park-1` | `manager-A` |
| `client-vh` / `vinhomes` | `BQL-OP1-B` | `ocean-park-1` | `manager-B` |
| `client-vh` / `vinhomes` | `BQL-OP2-C` | `ocean-park-2` | `manager-C` |

Request `BQL-OP1-A` chỉ tới A, không tới B dù cùng domain/area. Một partner client khác không được dùng ref của `client-vh`; ref trùng chữ giữa các client không đồng nghĩa cùng đích. Không áp uniqueness một manager cho mỗi area, vì nhiều tài khoản có thể quản lý cùng area nhưng vẫn là các đích riêng biệt.

Với luồng nhà/cư dân hiện có, giữ `partner_residences` và bổ sung liên kết `route_id`: `(partner_client_id, residence_id, external_user_id)` xác minh người gửi và suy ra route/area. Khi đồng bộ mapping residence phải kiểm tra route thuộc client/domain, area khớp và còn được grant. Đây là liên kết đối tượng nghiệp vụ, không thay thế route tới manager. Nếu ref trong request và route của residence không khớp, từ chối; không ưu tiên một trường rồi bỏ qua trường còn lại.

#### 2.6.3. Ai tạo và thay đổi mapping khi không có role admin?

- Tài khoản đăng ký vẫn chọn domain/area. Trước khi kích hoạt nhận request thật, quyền quản lý phải được xác minh qua invitation/provisioning có audit; có thể dùng công cụ vận hành do Chí Hoàng sở hữu, không thêm role admin vào sản phẩm. Chưa xác minh thì không được tự nhận request chỉ bằng cách chọn đúng tên area.
- Manager đã xác minh tạo grant trong phạm vi **tài khoản mình** cho một partner client đã được cấp credential. Backend điền manager/domain/area từ membership, không cho form/body chỉ định một manager khác. Đối tác xác nhận external ref bằng credential của chính client đó; chỉ khi hai bên khớp mới chuyển `pending_confirmation` thành `active`.
- UI quản lý grant nằm ở `shell/` của Chí Hoàng để không tranh sửa trang MCP của Đông. Đối tác xác nhận bằng API, không cần tài khoản đăng nhập/portal/role mới. Công cụ vận hành có thể import mapping theo hồ sơ đã xác minh với audit và cùng validation; không tự kích hoạt mapping chỉ vì có dòng CSV.
- State tối thiểu: `pending_confirmation → active → disabled/revoked`. Bên manager chỉ xem/sửa/thu hồi grant của mình; đối tác chỉ xác nhận/xem public projection grant cho client mình, không sửa owner. API key provisioning hiện có chỉ cấp machine credential, không thay thế bước cấp quyền route.
- Thay external ref, area hoặc tài khoản đích là thay đổi có kiểm soát, lưu revision/history và cần xác minh/xác nhận lại. Chuyển sang tài khoản khác phải có grant của tài khoản mới; không cho manager cũ sửa owner sang B. Không cung cấp chức năng user tự đổi domain/area làm mọi tài nguyên cũ tự chuyển chủ. V1 chuyển phạm vi qua quy trình vận hành có audit, không mở rộng UI quản trị tổ chức.

#### 2.6.4. Thuật toán nhận request và chọn đúng đích

API tổng quát được đề xuất: `POST /workforce/v1/partner/requests`. Body gồm `schema_version="1"`, `command_type`, `external_request_id`, `external_management_ref`, `external_user_id`, `external_conversation_id`, `external_ticket_id?`, `message={type:"text",text:...}`; thêm `residence_id` cho adapter cư dân/nhà. `external_ticket_id` bắt buộc với tích hợp có khái niệm ticket/hộp chat nghiệp vụ và có thể null/không gửi với request thật sự không có ticket theo route policy đã onboarding. `command_type=start_workflow` tạo yêu cầu mới; `workflow_reply` bắt buộc có `workflow_id` và cùng external ticket/conversation để tiếp tục ticket cũ. Không nhận `ticket_id`, `conversation_id`, `group_id`, scope, manager ID, role, danh sách agent, tool credential hoặc `execution_mode` do đối tác tự quyết. External ref phải được đối tác cấu hình theo mapping đã xác nhận, không do LLM suy ra từ văn bản.

Ví dụ payload giả, gửi từ backend `client-vh` bằng API key hợp lệ:

```json
{
  "schema_version": "1",
  "command_type": "start_workflow",
  "external_request_id": "vh-message-001",
  "external_management_ref": "BQL-OP1-A",
  "external_user_id": "resident-123",
  "external_ticket_id": "partner-ticket-plumbing-001",
  "external_conversation_id": "vh-chat-789",
  "residence_id": "S1-0205",
  "message": {
    "type": "text",
    "text": "Hãy gọi thợ đến sửa ống nước nhà tôi bị vỡ."
  }
}
```

Backend tra ra `vinhomes/ocean-park-1/manager-A` từ key + grant + residence mapping; payload không tự cấp `manager_account_id`. Leader sau đó chỉ chọn agent Technical hoặc agent liên quan trong kho của A. Đổi nội dung message sang “hãy dùng agent của manager-B” không thay đổi scope.

1. Xác thực key/client/domain, giới hạn kích thước/rate, dựng `ActorContext(kind=partner)` từ server. Partner API chỉ cho submit request, nhận phản hồi và gửi lựa chọn/consent trong hội thoại được cấp; không cho build/publish/config agent.
2. Kiểm tra `external_request_id` đã nhận trong namespace `(tenant_id, partner_client_id)`. Nếu đã có, kiểm tra payload hash và quyền đọc đích **đã lưu** trước khi trả kết quả cũ; không resolve lại tới manager mới. Cùng ID khác payload trả 409, không tạo run thứ hai.
3. Với request mới, resolve active route đúng `(tenant_id, partner_client_id, external_management_ref)`. Kiểm tra grant cho thao tác, domain, area, tài khoản đích active và quyền quản lý đã xác minh còn hợp lệ. Với residence, xác minh quan hệ người gửi/nhà/route như mục 2.6.2. Không đủ hoặc không duy nhất thì dừng trước khi gọi LLM.
4. Dựng `Scope(tenant_id, domain_id, area_id, manager_account_id)` và audience `(partner_client_id, external_user_id, external_conversation_id)`. Với route có ticket, resolve thêm khóa `(tenant_id, partner_client_id, external_user_id, external_ticket_id)` và kiểm tra quan hệ một-một với `external_conversation_id`. Conversation/ticket đã gắn owner A thì không chuyển sang B dù mapping thay đổi. Nếu đích khác trả `CONVERSATION_SCOPE_MISMATCH`; nếu ticket và conversation trỏ hai binding khác nhau trả `WORKFLOW_BINDING_MISMATCH` trước khi gọi Leader.
5. Trong transaction, kiểm tra lại route revision/grant/membership, ghi request + scope + actor/audience + payload hash + route snapshot + ticket/conversation binding và outbox/job. Với `start_workflow` của external ticket mới, tạo đúng một `WorkflowRecord`, một conversation nội bộ và một group runtime rồi persist binding tới cả ba; retry không tạo lại. External ticket đã bind mà gửi `start_workflow` mới trả `TICKET_ALREADY_BOUND`, client phải dùng `workflow_reply`. Một `external_conversation_id` không được bind sang external ticket thứ hai; muốn có hộp chat thứ hai phải dùng ID mới. Commit trước khi chạy; HTTP adapter chờ kết quả lượt này có thời hạn theo mục 17.2, không giữ transaction trong khi chờ.
6. Worker đọc binding đã lưu để lấy chính xác workflow/conversation/group rồi mới gọi Leader bằng scope đã pin. PublishedCatalogPort chỉ trả agent của tài khoản đích. Leader chọn subset AgentDefinition đã phát hành và materialize member session trong **group đã resolve**; Leader không tạo group dựa trên nội dung message, không tìm group gần giống và không lấy agent của manager khác khi thiếu năng lực.
7. Kết quả lượt đầu trả qua response POST nếu đã sẵn sàng trong thời hạn, đồng thời lưu public event log. Cập nhật tiếp theo được đọc bằng SSE hoặc GET history/snapshot theo mục 17; cùng câu trả lời trên POST/SSE dùng chung message_id để dedupe. Credential đối tác không được xem raw trace, prompt nội bộ hay secret; không nhận callback URL tùy ý từ request.

Request nội bộ từ manager UI không cần partner route: Scope lấy từ tài khoản/membership hiện hành của người đang đăng nhập. Cả hai đường đều dùng cùng PublishedCatalog/Orchestration/Execution ports, nhưng giữ actor/audience khác nhau.

Với `workflow_reply`, sau chống trùng phải tải workflow/binding đã lưu và kiểm tra quyền hiện hành trên đích gốc; không resolve lại ref để tạo owner mới. `external_management_ref`/người gửi/`external_ticket_id`/hội thoại phải khớp binding, sau đó dispatch thẳng vào group_id đã persist. Workflow không tồn tại, đã đóng hoặc không thuộc audience thì trả lỗi; không tự fallback sang tạo workflow/group mới.

#### 2.6.4.1. Hai ticket/hai hộp chat của cùng một khách hàng

Giả sử cùng `partner_client_id=client-vh` và `external_user_id=resident-123` đang mở đồng thời:

| Hộp chat phía đối tác | Khóa do đối tác gửi | Binding platform phải lưu | Runtime được phép dùng |
|---|---|---|---|
| Hộp A: sửa ống nước | `external_ticket_id=TICKET-A`, `external_conversation_id=CHAT-A` | `TICKET-A/CHAT-A → workflow-A/conversation-A/group-A` | Chỉ session, context, pending waits, approval và operation của group-A |
| Hộp B: đặt khách sạn | `external_ticket_id=TICKET-B`, `external_conversation_id=CHAT-B` | `TICKET-B/CHAT-B → workflow-B/conversation-B/group-B` | Chỉ session, context, pending waits, approval và operation của group-B |

Luồng bắt buộc:

1. POST `start_workflow` đầu tiên của TICKET-A tạo binding/group-A; POST `start_workflow` đầu tiên của TICKET-B tạo binding/group-B. Hai transaction độc lập và có unique constraints để request đồng thời không tạo hai group cho một ticket.
2. Backend đối tác lưu các ID platform trả về theo từng hộp chat. Tin nhắn mới ở hộp A gửi `workflow_reply` với external_request_id mới nhưng giữ `external_user_id`, `external_ticket_id=TICKET-A`, `external_conversation_id=CHAT-A` và `workflow_id=workflow-A`; hộp B làm tương tự với bộ B.
3. Ingress so khớp toàn bộ tuple với binding đã persist rồi resolve `group_id`; chỉ sau đó mới enqueue run. Không truyền `group_id` từ đối tác và không nhờ Leader/LLM chọn group. Mismatch trả lỗi, không dispatch một phần.
4. Hai group có thể tham chiếu cùng agent/version đã publish; đây là reuse định nghĩa agent, không phải dùng chung session. Shared state, lịch sử message, entity đang chọn, ngân sách, approval, idempotency tool call và external operation phải partition theo workflow/group.
5. SSE/history của mỗi hộp dùng `conversation_id` platform riêng. Stream A chỉ project event có binding A; stream B chỉ project event có binding B. Đóng workflow-A không đóng, đánh thức hoặc đổi context workflow-B.

`external_ticket_id` là ID ngoài để đối tác tương quan; `ticket_id` là ID nội bộ platform trả ra nếu nghiệp vụ tạo ticket. Hai trường không thay thế nhau. Đối tác không gửi `ticket_id`, `conversation_id` hoặc `group_id` để định tuyến command.

#### 2.6.5. Filter bắt buộc ở mọi tầng

- Query owner phải so khớp cả `tenant_id`, `domain_id`, `area_id`, `manager_account_id`. Các bảng con có thể kế thừa qua parent/FK đã kiểm tra; không cần nhân bản cột vô điều kiện, nhưng không được truy vấn chỉ theo resource ID, role hoặc area. Vector search phải filter quyền trước top-k; không tìm toàn kho rồi bỏ kết quả trái quyền sau khi đã đưa vào prompt.
- Áp dụng cho MCP/tool/credential, Builder/reuse, draft/eval/publish, conversation/message, ticket/memory, group/session, approval/booking, file/blob/download và result API. `created_by` là audit, không đủ thay cho owner scope. Legacy storage dùng `user_id=manager_account_id` nhưng adapter phải kiểm tra domain/area và mapping runtime trước khi gọi.
- Cùng manager có thể phục vụ nhiều khách hàng: thêm audience/subject filter cho lịch sử, memory cá nhân, booking và consent. Knowledge/memory nghiệp vụ dùng chung trong scope chỉ được chọn nếu được đánh dấu cho phép; không tự đưa chat/booking của cư dân X sang Y.
- Cache key, vector metadata, Redis topic, SSE subscription và worker job phải chứa scope hoặc opaque ID mà server kiểm tra lại với owner. Worker không tin scope trong message broker; đọc bản ghi DB. Không coi UI ẩn dữ liệu là authorization.
- Tool execution kiểm tra lại scope, grant còn hiệu lực, pinned binding và quyền theo audience ngay trước call. Route inbound không cấp toàn quyền manager: cư dân chỉ xác nhận giao dịch thuộc mình theo policy; không thể dùng API key đối tác gọi endpoint approval/build/publish của manager. Consent phải gắn actor/audience, run/call, arguments và quote.
- Mọi read/poll/result/reply từ partner phải kiểm tra client/domain và audience binding của request/conversation, không chỉ biết `request_id`. Backend đối tác chịu trách nhiệm xác thực end user; API v1 tin assertion end user từ backend đó, không hứa cô lập chống lại chính một partner backend đã bị chiếm credential.

#### 2.6.6. Khi mapping sai, thay đổi hoặc request gửi lại

| Tình huống | Hành vi bắt buộc |
|---|---|
| Key sai/hết hạn/thu hồi | 401; không gọi Leader hoặc tiết lộ mapping |
| Không có grant hợp lệ, sai domain/area/client/manager hoặc sai residence | 403 `ROUTE_NOT_AUTHORIZED` với thông báo không liệt kê manager khác; audit lý do chi tiết nội bộ |
| Dữ liệu import có nhiều route active cho một ref | 409 `ROUTE_AMBIGUOUS`, zero dispatch; không chọn manager đầu tiên hoặc broadcast |
| Manager inactive/quyền quản lý bị thu hồi | Chặn request/call mới; không chuyển tự động sang manager khác cùng area |
| Route/grant đổi sau khi enqueue hoặc trong phiên | `blocked_route_changed` hoặc `blocked_authorization`; kiểm tra lại trước resume, không sửa owner/history sang manager mới |
| Request gửi lại sau đổi mapping | Đọc bản gốc theo idempotency key; trả bản gốc chỉ khi còn quyền, nếu không trả lỗi. Không tạo run mới cho tài khoản mới |
| Cùng request ID nhưng khác payload/ref/người gửi | 409 `IDEMPOTENCY_CONFLICT` |
| Cùng external conversation nhưng đổi manager hoặc người gửi không khớp binding | Từ chối sử dụng binding cũ; không trộn context. Namespace của người gửi khác tạo hội thoại riêng |
| Mapping đúng nhưng kho agent không đáp ứng nghiệp vụ | Báo thiếu năng lực trong scope, không mượn agent của tài khoản khác hoặc tự build agent production |

Request/conversation đã nhận giữ owner và route revision gốc. Các request mới sau khi mapping được chuyển hợp lệ có thể đến owner mới, nhưng hội thoại cũ không tự đi theo. Thu hồi grant dừng các tác vụ chưa gọi provider; tác vụ đã ra ngoài phải lưu trạng thái thật/unknown và reconciliation, không báo đã rollback giao dịch. Rotation key cùng partner client không làm mất idempotency namespace; khóa cũ bị thu hồi không được dùng để poll.

#### 2.6.7. Tích hợp với code hiện tại và bàn giao song song

- Tái sử dụng auth, API key và residence mapping; không viết lại hệ identity. Bổ sung grant/route và kiểm tra owner, không xóa domain/area.
- `POST /partner/tickets` hiện chỉ lưu ticket, chưa chạy agent. Khi nâng cấp, phải resolve tới cùng Scope, lưu `manager_account_id`/route snapshot và filter GET/PATCH tương ứng. Chỉ ticket có action dispatch được cấu hình mới enqueue runtime qua cùng ingress service; không âm thầm biến mọi ticket thành lệnh booking. Adapter dispatch yêu cầu ID sự kiện ổn định: thống nhất `external_request_id` của ingress bằng `external_ticket_id` của sự kiện tạo ticket đó và chuẩn hóa cùng payload trước hash; nếu dùng cả hai API thì đối tác phải gửi cùng ID sự kiện. Ticket chưa có ID bên ngoài không tự dispatch. Hai endpoint không tự tạo hai run cho cùng sự kiện; mỗi message tiếp theo có ID mới.
- Ticket/memory cũ chỉ có area, chưa rõ tài khoản sở hữu: đánh dấu cần backfill và giới hạn truy cập, không gán cho manager đầu tiên, không clone cho mọi manager. Chỉ migrate owner khi có bằng chứng mapping; dữ liệu thiếu căn cứ chờ đối soát. Chí Hoàng nối legacy business routes và cập nhật tài liệu API cũ khi implementation thực sự thay đổi.
- Foundation/Chí Hoàng: `Scope`, `ActorContext`, membership verification, route/grant service, API quản lý/xác nhận route, migrations và legacy bridge. Huy Hoàng: ingress request/conversation binding, outbox/idempotency, dispatch và partner result projection. Các module khác nhận Scope đã xác minh qua port; không tự xây mapping thứ hai.
- Trong khi provider thật chưa xong, dùng fake Identity/PartnerRoutingPort và ma trận A/B/C ở trên. Không cần chờ toàn bộ Foundation để làm filter, UI hoặc E2E; các ownership folder hiện có vẫn giữ nguyên.

### 2.7. Lifecycle nghiệp vụ độc lập lĩnh vực

- API khách hàng là một bộ endpoint dùng chung: POST gửi request/reply/consent/close; GET đọc request/snapshot/history hoặc mở SSE. Không tạo endpoint riêng cho du lịch, khách sạn, xe, sửa chữa, y tế, giáo dục hoặc từng domain khác.
- Mỗi lượt POST đều áp dụng cùng quy tắc HTTP: platform lưu request trước, xử lý trong thời hạn rồi trả một `200` với kết quả đã lưu; nếu hết thời hạn mà còn pending thì trả duy nhất `202`. Mã `202` chỉ phản ánh độ trễ của lượt hiện tại, không quyết định lifecycle và không có response thứ hai trên cùng POST.
- Platform phân loại bước tiếp theo bằng capability/policy đã publish, loại side effect và kết quả tool đã xác minh; không để đối tác tự gửi execution mode và không để LLM tùy ý gắn một lĩnh vực vào lifecycle cố định.

| Pattern | Khi dùng | Sau lượt hiện tại | Kênh tiếp tục |
|---|---|---|---|
| Response-only | Tra cứu/giải đáp chỉ đọc đã đủ kết quả và policy cho phép kết thúc | `closed`, `next_action=none` | Không cần SSE hoặc close |
| Interactive | Cần khách chọn phương án, bổ sung dữ kiện, duyệt giao dịch hoặc xác nhận kết quả | `awaiting_user`, `awaiting_approval` hoặc `awaiting_confirmation` | POST reply/approval/close; SSE tùy chọn |
| External-tracking | Tool trả operation/job còn tiếp diễn và protocol có Provider Event API hoặc status-query | `waiting_external_event` | SSE/history để nhận cập nhật; Provider Event/status-query đánh thức workflow |

- Một workflow có thể chuyển pattern: ví dụ lập kế hoạch du lịch trả phương án ở `awaiting_user`; khách chọn thì sang approval; booking được xác nhận ngay thì sang `awaiting_confirmation`; chỉ khi provider trả pending mới sang `waiting_external_event`. Tên lĩnh vực không quyết định đường đi.
- Chat tiếp dùng `command_type=workflow_reply`, `workflow_id` cũ, cùng `external_conversation_id`/người dùng và external_request_id mới. Giữ conversation/ticket/group/session/context; run_id mới chỉ là lượt xử lý mới, không tạo phiên trắng hoặc ticket khác.
- Response luôn có `next_action`: `none`, `submit_reply`, `submit_approval`, `watch_request`, `watch_events`, `confirm_close` hoặc `resolve_attention`. Backend hành động theo field này thay vì suy luận từ nội dung tự nhiên hoặc bắt buộc mở SSE sau mọi POST.
- Provider Event API là capability tùy chọn của operation bất đồng bộ. Event phải được xác thực, lưu bền vững, chống trùng/sai thứ tự rồi resolve từ operation đã lưu tới đúng scope/workflow/audience; payload không được tự chọn manager, agent hoặc hội thoại.
- Khi chờ người dùng hoặc sự kiện ngoài, platform checkpoint và giải phóng model/worker. Event/reply mới chỉ tiếp tục Leader/agent cần thiết; không build agent hay tạo group mới.
- Workflow có side effect hoặc cần xác nhận kết quả chỉ đóng bằng close hợp lệ. Workflow read-only một lượt có thể auto-close theo policy đã publish và phải trả `workflow_state=closed`, `next_action=none`; đối tác không được tự yêu cầu auto-close bằng payload.
- Giữ một role AREA_MANAGER. Người dùng cuối, nhân viên, tài xế, kỹ thuật viên hoặc actor nghiệp vụ khác là actor bên đối tác qua machine integration; không thêm portal role theo từng lĩnh vực.

## 3. Tài nguyên hiện có phải tận dụng

| Tài nguyên trong repo | Tái sử dụng vào việc gì | Phần cần bổ sung |
|---|---|---|
| `src/agentscope/agent/`, `model/`, `formatter/` | Agent loop, structured output và gọi model | Builder và evaluator dùng adapter trên các abstraction này |
| `src/agentscope/mcp/_mcp_client.py` | Kết nối, discovery, gọi tool, lọc tên tool | Catalog bền vững, version/schema hash, credential reference |
| `src/agentscope/app/storage/_model/_mcp.py` và `_router/_mcp.py` | MCP library, metadata, enabled state | Mapping catalog đối tác → connection riêng của user; tránh hai nguồn enabled state mâu thuẫn |
| `src/agentscope/app/hub/` | Cách biểu diễn card và cấu hình MCP | Adapter import catalog đối tác; không phải xây marketplace công cộng mới |
| `src/agentscope/tool/`, `permission/` | Toolkit, ToolBase, permission và HITL | Binding theo version, gateway kiểm tra từng call, approval cho giao dịch |
| `src/agentscope/app/_types.py` | `AgentToolFactory`, `AgentMiddlewareFactory`, `EventProjector` | Adapter Workforce qua điểm mở rộng hiện có |
| `src/agentscope/app/_service/_toolkit.py` | Nơi tập hợp tool, MCP, skill của runtime | Lọc tập tool đúng manifest trên đường chạy Workforce |
| `src/agentscope/app/_tool/` | TeamCreate, AgentInvite, TeamSay, TeamDelete | Mời đúng published version, chuẩn hóa task/context và routing |
| `src/agentscope/app/storage/_model/_agent.py` | Agent identity, prompt, context/react config | Manifest tổng hợp và version bất biến ở module mới |
| `src/agentscope/app/storage/_model/_session.py` | Model, KB, workspace và state theo session | Materialize session từ manifest/version đã ghim |
| `src/agentscope/app/message_bus/`, `_bus_ops.py`, `_service/_chat.py` | Inbox, wakeup, locking, SSE, interrupt/resume | Group event projection, routing, durable job state |
| `src/agentscope/app/_service/_projectors/_subagent_hitl.py` | Đưa yêu cầu xác nhận của member lên phiên leader | Nối approval giao dịch và group UI, tránh hai card trùng nhau |
| `src/agentscope/app/rag/`, `src/agentscope/skill/`, `middleware/_longterm_memory/` | KB, skill, memory | Chọn binding và context theo scope; không lấy memory làm nguồn giá/booking |
| `src/agentscope/app/storage/_sql/`, `compose.yaml` | SQLAlchemy/Alembic, PostgreSQL/pgvector, Redis, MinIO | Bảng Workforce, migration, jobs và cấu hình theo tính năng |
| `src/agentscope/app/auth/`, `_router/_auth.py`, `deps.py` | Password hash, JWT, refresh token, AREA_MANAGER và domain/area | Giữ một role, xác minh membership, phân biệt actor với scope tài khoản đích |
| `src/agentscope/app/business/`, `_router/_business.py`, migration `0008_area_platform` | Domain API key, residence → area, ticket/memory theo area | Thêm mapping có grant tới tài khoản đích, filter theo owner, audit và adapter request runtime; không coi ticket area là đã dispatch agent |
| `src/agentscope/middleware/_tracing/`, `_budget.py` | Trace và kiểm soát ngân sách model | Correlation ID, chi phí theo build/eval/run |
| `examples/web_ui/frontend/src/components/`, `hooks/`, `api/` | UI primitives, forms, chat, panels, API conventions | Các màn hình Workforce riêng và cơ chế auth tương thích |
| `tests/service_team_tools_test.py`, `service_toolkit_test.py`, `mcp_runtime_headers_test.py`, các test HITL/storage/auth | Regression baseline | Test hành vi Workforce và test nối vào framework |

Những điểm đã đọc trong code cần xử lý có chủ đích:

1. `AgentData` chưa chứa toàn bộ model/tool/KB. Các thông tin này phân tán giữa agent, session và workspace. Manifest mới phải là nguồn cấu hình của Workforce; runtime records chỉ là bản materialize.
2. `_toolkit.py` nạp tool và MCP từ workspace. Chỉ thêm tool bằng `extra_agent_tools` không loại bỏ các tool workspace đã nạp. Cần một hook lọc/assembly riêng cho Workforce và test chống rò tool.
3. `MCPClient.enable_tools` hỗ trợ lọc discovery, nhưng `get_tool()` có thể resolve từ cache đầy đủ. Lọc tên để đưa vào prompt không đủ làm kiểm soát thực thi.
4. `AgentInvite` hiện chọn model/workspace từ session sẵn có hoặc leader. Cần adapter dùng đúng version đã phát hành, không âm thầm chọn session đầu tiên làm cấu hình chuẩn.
5. Auth hiện yêu cầu `AREA_MANAGER`, domain và area; đây là hướng nghiệp vụ đúng và phải giữ. Frontend hiện đã dùng Bearer/refresh, không còn kết luận cũ rằng client chỉ gửi `X-User-ID`. Cần kiểm tra membership hiện hành, hỗ trợ tài khoản cũ thiếu scope và truyền đủ scope qua mọi tầng; không để legacy header giả danh manager trên đường Workforce.
6. `MCPRecord` có thể lưu credential trong config/values. Bổ sung encrypted credential store/reference; không nhân đôi secret sang catalog, manifest hay frontend response.
7. Message bus có queue drain dạng lấy ra khỏi hàng đợi khi đọc. Job eval/booking cần job record, lease và khôi phục từ DB; không dựa riêng vào một message Redis để bảo đảm không mất việc.
8. Team role `leader/worker` là vai trò thực thi của agent, không phải role tài khoản người dùng. Vẫn giữ chúng.
9. Nhiều thay đổi auth/business/compose đang chưa commit tại thời điểm lập kế hoạch. Khi bắt đầu chia nhánh cần cùng một baseline gồm các thay đổi đã được team chọn; không reset để lấy cây sạch.
10. `AgentCreate` hiện sinh worker thuộc team với vòng đời gắn team. Builder tạo agent lâu dài trong thư viện phải dùng luồng identity/draft/publish của Workforce, không dùng công cụ này để tạo batch. `TeamCreate`/`AgentInvite` chỉ dùng khi có run/group thực tế hoặc sandbox eval; mọi cleanup phải giữ các agent thư viện độc lập.
11. `BusinessService.create_ticket` hiện chỉ tra area rồi đếm manager active; `list_tickets_for_manager` và memory queries lọc theo area. Chưa có manager đích, grant inbound hoặc dispatch tới Leader. Tài liệu `docs/area_platform_api_vi.md` mô tả hành vi code cũ này; khi triển khai Workforce phải áp dụng mục 2.6, không sao chép giả định hàng đợi chung của area.
12. Với ticket dài hạn, `_router/_session.py` hiện chỉ replay bus log giới hạn theo run và chưa có SSE event ID/cursor bền vững; `examples/agent_service/main.py` dùng InMemoryMessageBus. `update_ticket_status` ghi ticket_events nhưng chưa nối tới workflow/public event log. `_skip_parked_wakeup` không đánh thức session đang chờ HITL bằng wake thường. Phải bổ sung adapter/DB event pipeline mục 17.7, không coi những primitive này là đã hoàn thành tính năng.

## 4. Kiến trúc và ranh giới trách nhiệm

Triển khai dưới dạng các module trong cùng ứng dụng Python/FastAPI và Web UI hiện có. Chưa cần tách thành sáu microservice.

```text
Frontend Workforce (shell + 5 feature areas)
                  |
API /workforce/v1 + authenticated Scope
                  |
Registry ----> Builder single/batch ----> Lifecycle / Evaluation
    |                                         |
    |                              Thư viện agent độc lập
    |                                         |
    |                            User request → Leader chọn agent
    |                                         |
    +---------------------- Execution <--- Orchestration / group
                                 |                           |
                           MCP / HITL              Team / Session / SSE
                                 +------------+--------------+
                                  AgentScope hiện có

Contracts: DTO, enums, ports, errors, events — tất cả module cùng đọc
Foundation: identity, DB/session, jobs, credentials, audit
Integrations: nối module với AgentScope, FastAPI, lifespan và runtime
```

- Registry quản lý MCP connection và tool descriptor; không phát hành agent, không sở hữu booking.
- Builder kiểm tra agent đã có, tạo đề xuất reuse/revise/create cho một hoặc nhiều agent, rồi sinh manifest riêng từng agent; không tạo group/roster thực thi và không ghi trực tiếp bảng agent version/deployment.
- Lifecycle sở hữu identity/hồ sơ nghiệp vụ, draft/manifest/version/evaluation/deployment của từng agent, cùng batch để theo dõi phát hành nhiều agent. Đây là nơi kiểm tra trùng lần cuối. Evaluation dùng runtime thông qua port, không import orchestration service trực tiếp.
- Orchestration nhận request, chọn published agent từ toàn bộ thư viện trong scope, tạo run/group, quản lý context và group message; không lọc theo batch và không gọi MCP trực tiếp.
- Execution là cửa gọi tool, kiểm tra binding, approval và transaction. Code tạo booking chỉ có một đường thực thi qua module này.
- Foundation sở hữu identity, xác thực đối tác và mapping/grant tới manager; Orchestration sở hữu nhận request, idempotency, conversation binding và dispatch. Integrations nối business/auth/router cũ với các port; không để module nhập private service của nhau.
- Bổ sung v1.4: Registry sở hữu protocol/normalization, Execution sở hữu external operation và provider inbox, Orchestration sở hữu workflow/checkpoint/public event log, Foundation sở hữu durable job/trigger worker, event-stream transport và auth. Builder/Lifecycle kiểm tra/eval capability theo dõi; các điểm nối dùng ports mục 17.4.
- Một role `AREA_MANAGER` vẫn có kiểm tra domain/area, ownership, trạng thái tài khoản và consent theo thao tác. Không có bước xin admin cấp MCP; mapping inbound là quyền của đối tác gửi tới tài khoản, không phải quyền bật MCP.

## 5. Bảng phân công và thư mục sở hữu

Tên thư mục phản ánh chức năng; slug cá nhân chỉ dùng cho branch và bàn giao để dễ chuyển người sau này.

| Thành viên | Slug/branch | Backend sở hữu | Frontend sở hữu | Test sở hữu |
|---|---|---|---|---|
| Nguyễn Chí Hoàng | `nguyen-chi-hoang` / `feat/wf-foundation` | `src/agentscope/app/workforce/contracts/`, `foundation/`, `integrations/` | `examples/web_ui/frontend/src/features/workforce/shared/`, `shell/` | `tests/workforce/foundation/` |
| Nguyễn Phương Đông | `nguyen-phuong-dong` / `feat/wf-registry` | `src/agentscope/app/workforce/registry/` | `examples/web_ui/frontend/src/features/workforce/integrations/` | `tests/workforce/registry/` |
| Bùi Hữu Nghĩa | `bui-huu-nghia` / `feat/wf-builder` | `src/agentscope/app/workforce/builder/` | `examples/web_ui/frontend/src/features/workforce/builder/` | `tests/workforce/builder/` |
| Phó Tiến Anh | `pho-tien-anh` / `feat/wf-lifecycle` | `src/agentscope/app/workforce/lifecycle/` | `examples/web_ui/frontend/src/features/workforce/agents/` | `tests/workforce/lifecycle/` |
| Phan Huy Hoàng | `phan-huy-hoang` / `feat/wf-orchestration` | `src/agentscope/app/workforce/orchestration/` | `examples/web_ui/frontend/src/features/workforce/chat/` | `tests/workforce/orchestration/` |
| Phan Hoàng Dũng | `phan-hoang-dung` / `feat/wf-execution` | `src/agentscope/app/workforce/execution/` | `examples/web_ui/frontend/src/features/workforce/approvals/` | `tests/workforce/execution/`, `e2e/`, `fixtures/` |

Quyền sở hữu bổ sung:

- Nguyễn Chí Hoàng: tài liệu kế hoạch này, README gốc Workforce, package `__init__.py` gốc, migration thật, CI, cấu hình dependency, `scripts/workforce/`, `deploy/workforce/`.
- Mỗi người sở hữu `docs/workforce/handoffs/<slug>/` của mình. Các yêu cầu đổi contract/integration ghi ở đây; không cùng sửa một bảng STATUS chung.
- Phan Hoàng Dũng sở hữu mock MCP server, dataset nghiệm thu và e2e runner trong `tests/workforce/fixtures/` và `e2e/`. Các thành viên vẫn tự viết unit/contract tests của module mình.
- Các thư mục dùng dấu `/` trong bảng là đường dẫn con của cùng backend/frontend root ở đầu ô, không phải đường dẫn độc lập ở repo root.

### 5.1. Các file chung chỉ Nguyễn Chí Hoàng được sửa trong kế hoạch

```text
src/agentscope/app/_app.py
src/agentscope/app/_lifespan.py
src/agentscope/app/_types.py
src/agentscope/app/deps.py
src/agentscope/app/__init__.py
src/agentscope/app/_router/**
src/agentscope/app/_service/**
src/agentscope/app/_tool/**
src/agentscope/app/auth/**
src/agentscope/app/business/**
src/agentscope/app/storage/**
examples/agent_service/main.py
examples/web_ui/frontend/src/App.tsx
examples/web_ui/frontend/src/api/**
examples/web_ui/frontend/src/components/layout/**
examples/web_ui/frontend/src/i18n/**
pyproject.toml
examples/web_ui/package.json
examples/web_ui/frontend/package.json
examples/web_ui/pnpm-lock.yaml
examples/web_ui/frontend/tsconfig*.json
compose.yaml
Dockerfile
.env.example
.github/workflows/**
```

Không có nghĩa phải sửa tất cả file trên. Đây là danh sách chốt chủ sở hữu khi cần sửa. File cũ chưa liệt kê cũng không mặc định là vùng tự do: gửi yêu cầu tích hợp cho Nguyễn Chí Hoàng.

Ví dụ Phan Huy Hoàng cần hook cho TeamSay: viết adapter trong `orchestration/`, test ở `tests/workforce/orchestration/`, rồi ghi chữ ký hook và điểm gọi cần thêm vào bàn giao. Nguyễn Chí Hoàng thực hiện patch tối thiểu ở core.

### 5.2. Cấu trúc đã tạo

```text
docs/workforce/
  KE_HOACH_TRIEN_KHAI.md
  handoffs/
    nguyen-chi-hoang/
    nguyen-phuong-dong/
    bui-huu-nghia/
    pho-tien-anh/
    phan-huy-hoang/
    phan-hoang-dung/
src/agentscope/app/workforce/
  contracts/
  foundation/
  integrations/
  registry/
  builder/
  lifecycle/
  orchestration/
  execution/
examples/web_ui/frontend/src/features/workforce/
  shared/
  shell/
  integrations/
  builder/
  agents/
  chat/
  approvals/
tests/workforce/
  foundation/
  registry/
  builder/
  lifecycle/
  orchestration/
  execution/
  fixtures/
  e2e/
scripts/workforce/
deploy/workforce/
```

Mỗi thư mục có README ghi owner để Git lưu được cấu trúc. Các file code nêu ở phần công việc phía dưới là file cần tạo khi triển khai, không được hiểu là đã có.
Các package Python thêm `__init__.py` khi bắt đầu code; root do Nguyễn Chí Hoàng sở hữu, module con do chủ module sở hữu.

### 5.3. Thư mục bổ sung cho API/event/workflow (đã tạo khung v1.4)

Các đường dẫn dưới đây đầy đủ từ repository gốc; chỉ owner được ghi code. README giữ thư mục trong Git và nêu file dự kiến, không có stub production. Mỗi người tiếp tục dùng branch ở mục 5; không tạo outbound webhook/receiver vì contract v1 không có chiều platform gọi HTTP sang đối tác.

| Owner | Thư mục | Phạm vi |
|---|---|---|
| Nguyễn Chí Hoàng | `src/agentscope/app/workforce/contracts/async_api/` | DTO/ports/events/schema dùng chung mục 17.4; chỉ chủ folder được sửa. |
| Nguyễn Chí Hoàng | `src/agentscope/app/workforce/foundation/event_delivery/` | Tên scaffold cũ được giữ để tránh xáo trộn nhánh; phạm vi thực là provider credential guard, durable jobs/triggers, SSE signal/recovery và retention; không có HTTP sender outbound, không lưu workflow của Huy Hoàng. |
| Nguyễn Chí Hoàng | `src/agentscope/app/workforce/integrations/async_runtime/` | Composition và adapter AgentScope/business; core hook/migration chỉ Chí Hoàng tích hợp. |
| Nguyễn Chí Hoàng | `examples/web_ui/frontend/src/features/workforce/shared/event_transport/` | Transport fetch-SSE/token refresh/cursor; không chứa quy tắc ticket. |
| Nguyễn Chí Hoàng | `examples/web_ui/frontend/src/features/workforce/shell/delivery_monitor/` | Tên scaffold cũ; UI thực theo dõi SSE/replay/cursor và event backlog theo manager scope, không cấu hình endpoint đối tác. |
| Nguyễn Chí Hoàng | `tests/workforce/foundation/async_api/` | Kiểm tra auth/UOW/lease/fence/retry nội bộ, SSE ownership/replay và migration. |
| Nguyễn Chí Hoàng | `scripts/workforce/event_delivery/` | Tên scaffold cũ; công cụ event replay/retention có dry-run và scope; không gửi HTTP sang đối tác và không tự chạy xóa dữ liệu. |
| Nguyễn Chí Hoàng | `deploy/workforce/event_delivery/` | Tên scaffold cũ; runbook SSE/proxy/recovery/rotation/restore; giá trị thật cấu hình khi triển khai. |
| Nguyễn Chí Hoàng | `docs/workforce/handoffs/nguyen-chi-hoang/async_api/` | OpenAPI/guide cho các API platform host: customer POST/GET/SSE/history/close và Provider Event API. |
| Nguyễn Phương Đông | `src/agentscope/app/workforce/registry/event_protocols/` | Protocol snapshots/capabilities và deterministic normalization; không nhận HTTP Provider Event request hoặc ghi inbox. |
| Nguyễn Phương Đông | `examples/web_ui/frontend/src/features/workforce/integrations/event_channels/` | UI theo dõi readiness của Provider Event API/correlation và status-query qua MCP nếu có; không quản lý SSE transport của Chí Hoàng. |
| Nguyễn Phương Đông | `tests/workforce/registry/event_protocols/` | Protocol schema/ordering/drift/capability tests. |
| Bùi Hữu Nghĩa | `src/agentscope/app/workforce/builder/async_capabilities/` | Requirements và sinh policy theo dõi; reuse/revise, missing capability. |
| Bùi Hữu Nghĩa | `examples/web_ui/frontend/src/features/workforce/builder/async_capabilities/` | Hiển thị phạm vi theo dõi và blocker trong đề xuất build. |
| Bùi Hữu Nghĩa | `tests/workforce/builder/async_capabilities/` | Create-only vs tracking, fake ports và chống sinh workflow lúc build. |
| Phó Tiến Anh | `src/agentscope/app/workforce/lifecycle/async_evaluation/` | Async snapshot/policy validation và multi-event eval; runtime workflow thuộc Huy Hoàng. |
| Phó Tiến Anh | `examples/web_ui/frontend/src/features/workforce/agents/async_evaluation/` | Report nhiều event/turn và hard gates. |
| Phó Tiến Anh | `tests/workforce/lifecycle/async_evaluation/` | Fake clock/runner, pin version qua chờ và stale evaluation. |
| Phan Huy Hoàng | `src/agentscope/app/workforce/orchestration/workflows/` | Workflow state/trigger/checkpoint/close/continuation; không lưu provider inbox. |
| Phan Huy Hoàng | `src/agentscope/app/workforce/orchestration/partner_events/` | Public event log, SSE/history/snapshot và notification signal sau commit; không sender outbound. |
| Phan Huy Hoàng | `examples/web_ui/frontend/src/features/workforce/chat/ticket_timeline/` | Timeline/close nhiều ticket/workflow nhưng mỗi hộp chat giữ đúng binding, reconnect và event/message dedupe. |
| Phan Huy Hoàng | `tests/workforce/orchestration/async_workflows/` | Workflow transitions/checkpoint/HITL/cursor/isolation/crash windows. |
| Phan Hoàng Dũng | `src/agentscope/app/workforce/execution/provider_events/` | Provider Event API tùy chọn cho backend nghiệp vụ/provider, receipt/inbox/dedupe/ordering; không private workflow writes. |
| Phan Hoàng Dũng | `src/agentscope/app/workforce/execution/external_operations/` | Intent/correlation/job binding/progress/unknown/status-query; tạo intent trước tool call. |
| Phan Hoàng Dũng | `examples/web_ui/frontend/src/features/workforce/approvals/external_operations/` | Component job progress/unknown/creation result để Chat UI import. |
| Phan Hoàng Dũng | `tests/workforce/execution/provider_events/` | Signature dependency, provider event đến sớm, unknown, integration isolation và races. |
| Phan Hoàng Dũng | `tests/workforce/fixtures/async_partners/` | Mock backend khách hàng cho ba lifecycle pattern và mock provider chỉ ở ca external-tracking; dữ liệu giả, inject faults và fake clock. |
| Phan Hoàng Dũng | `tests/workforce/e2e/async_tickets/` | E2E cases 56–88; đủ response-only, interactive, external-tracking và hai ticket/hộp chat chạy xen kẽ với database/worker/mock transport thật. |

Các folder con export qua __init__.py/index.ts của module do chính owner phụ trách; root wiring/generated contracts/migration/lockfile vẫn chỉ Chí Hoàng sửa. Test cấp module có thể tự làm fake ports trong folder của mình; fixtures dùng chung async_partners chỉ Dũng sửa. Không tạo sẵn một file code rỗng cho mọi tên dự kiến rồi coi là tính năng đã có.

## 6. Hợp đồng chung v1 để làm song song

Phần này là baseline cho cả sáu người. Nguyễn Chí Hoàng hiện thực bằng Pydantic models/Protocols và xuất JSON Schema/TypeScript. Thay đổi breaking phải có contract v2 hoặc kế hoạch chuyển đổi được ghi trong bàn giao; không âm thầm đổi tên trường.

### 6.1. Quy ước dữ liệu

- Public API: `/workforce/v1`. Python và JSON dùng `snake_case`; ID do platform cấp dùng UUID dạng string, ID bên đối tác là opaque string theo hợp đồng; timestamp RFC 3339 UTC, có trường timezone cho nghiệp vụ. Các nhãn `manager-A`/`client-vh` trong ví dụ là dữ liệu minh họa, không áp đặt format ID production.
- `Scope`: `{tenant_id, domain_id, area_id, manager_account_id}` bắt buộc. Với manager UI, backend dựng từ principal và membership hiện hành; với partner API, dựng từ route/grant đã xác minh theo mục 2.6. V1 giữ tenant hiện có, không hardcode `default` trong frontend khi backend cấu hình tenant khác. Không nhận Scope tùy ý từ body và không bỏ domain/area khỏi contract.
- `ManagerPrincipal` có role cố định `AREA_MANAGER`; `ActorContext.kind=manager/partner/system` chỉ phân biệt nguồn hành động cho authorization/audit, không tạo thêm role sản phẩm. `ActorContext` không thay thế Scope owner; `external_user_id` không là tài khoản platform. Runtime cần mang cả Scope, actor và audience. Legacy `user_id` là alias qua adapter cho `manager_account_id`, không tạo thêm một owner song song.
- Mọi port truy cập tài nguyên riêng nhận `scope` làm tham số đầu. Tài nguyên không thuộc scope trả lỗi không tiết lộ nội dung.
- Tiền dùng `Money {amount_minor: int, currency: string}`. VND không có phần lẻ trong các fixture; ngân sách 10 triệu là `10000000`. Tổng tiền tính bằng integer/Decimal, không để LLM tự tính số cuối.
- `revision` để optimistic concurrency cho draft/state/config. Update yêu cầu `expected_revision`; xung đột trả 409, không ghi đè ngầm.
- Danh sách trả `{items, next_cursor}`. Job build/eval chạy lâu và Provider Event API trả `202` sau persist. Riêng POST Customer request/reply chờ lượt hiện tại có thời hạn: `200` khi kết quả đã lưu, `202` khi còn pending; luôn có request_id/conversation_id/workflow_id và ticket_id nếu đã tạo. Receipt provider dùng receipt_id. Close hợp lệ trả `200` sau commit trạng thái đóng; accepted của request không đồng nghĩa công việc bên ngoài đã hoàn tất.
- Error shape: `{error: {code, message, details, request_id, retryable}}`. `details` không chứa secret hoặc raw provider response chưa lọc.
- Event: `{event_id, sequence, event_type, occurred_at, scope_ref, actor_ref, audience_ref?, external_ticket_id?, conversation_id?, run_id?, agent_id?, payload}`. Backend xác định owner/actor/audience; SSE manager và SSE partner có projection/authorization riêng, loại bỏ trường nội bộ/secret. V1.4 bổ sung workflow_id/ticket_id/causation_id/schema_version/recorded_at theo mục 17.4; sequence là thứ tự commit per conversation, không phải timestamp provider. Public event của workflow có ticket ngoài phải project `external_ticket_id` từ binding đã lưu, không tin giá trị từ event caller.
- Event giao lại được phép; consumer dedupe theo `event_id`. DB là nguồn trạng thái lâu dài, Redis dùng điều phối và fan-out.

### 6.2. DTO bắt buộc

| DTO | Các trường tối thiểu |
|---|---|
| `Scope` / `ActorContext` | Scope đủ bốn trường mục 6.1; actor có `kind`, `actor_id`, `partner_client_id?`, `credential_id?`, `external_user_id?`, nguồn xác thực; backend dựng, không bind từ body |
| `PartnerManagerRoute` | `route_id`, `tenant_id`, `domain_id`, `area_id`, `manager_account_id`, `partner_client_id`, `external_management_ref`, `status`, `revision`, `allowed_operations[]`, `granted_by`, `confirmed_by_client_id?`, timestamps; manager scope đã xác minh |
| `ResolvedPartnerRoute` | `scope`, `route_id`, `route_revision`, `grant_operations[]`, `membership_revision`, `resolved_at`; kết quả nội bộ từ PartnerRoutingPort, không dùng dữ liệu này từ client làm bằng chứng |
| `PartnerAudience` | `partner_client_id`, `external_user_id`, `external_conversation_id`, `external_ticket_id?`, `residence_id?`; cô lập khách hàng và giữ binding lịch sử; route ticketed bắt buộc external_ticket_id |
| `InboundRequest` | `request_id`, scope, actor, audience, `external_request_id`, `external_management_ref`, `external_ticket_id?`, `payload_hash`, `route_id`, `route_revision`, `conversation_id`, `workflow_id`, `group_id`, `run_id?`, `status`, timestamps; unique request từ client, owner/binding immutable |
| `TicketConversationBinding` | scope, partner_client_id, external_user_id, external_ticket_id, external_conversation_id, workflow_id, conversation_id, group_id, route_id/revision, status, timestamps; một external ticket ↔ một external conversation ↔ một workflow/conversation/group đang phục vụ |
| `PartnerRequestEnvelope` / `InboundReceipt` | Envelope mục 2.6.4: schema_version, command_type=start_workflow/workflow_reply, external_request_id, external_management_ref, external_user_id, external_ticket_id?, external_conversation_id, workflow_id?, message; workflow_reply bắt buộc workflow_id và tuple binding khớp. Receipt {request_id, request_status, external_ticket_id?, conversation_id, workflow_id, ticket_id?, workflow_state, next_action, workflow_revision, result?, error?, accepted_at, completed_at?, status_url, conversation_url, event_stream_url}; result.messages[] dùng cùng message_id như public event. HTTP 200/202 theo mục 17.2, không lộ group_id/owner khác |
| `PartnerMcpDefinition` | `mcp_id`, `partner_id`, `name`, `description`, `catalog_version`, `transport`, `connection_schema`, `endpoint_template`, `status` |
| `McpConnection` | `connection_id`, `mcp_id`, scope, `desired_enabled`, `status`, `credential_ref`, `catalog_revision`, `last_sync_at`, `last_error_code` |
| `ToolDescriptor` | `tool_id`, `tool_version_id`, `connection_id?`, `source_kind=mcp/builtin`, `provider_tool_name`, `llm_alias`, `description`, `input_schema`, `output_schema?`, `schema_hash`, `capabilities[]`, `effect`, `available` |
| `ToolBinding` | `tool_id`, `tool_version_id`, `schema_hash`, `required_capability`, `selection_reason` |
| `BusinessProfile` | `profile_schema_version`, `objective`, `responsibilities[]`, `capabilities[]`, `input_contract`, `output_contract`, `business_scope`, `required_constraints`, `execution_policy`, `knowledge_requirements[]` |
| `AgentDefinition` | `agent_id`, scope, `name`, `business_key`, `business_profile`, `status`, `active_version_id?`, `draft_id?`, `revision` |
| `AgentReuseRef` | `agent_id`, `version_id`, `manifest_hash`; version thuộc đúng identity và scope |
| `BuildItem` | `item_id`, `agent_key`, `source=create/reuse/revise`, `spec?`, `reuse_ref?`, `target_agent_id?`, `source_version_id?`, `draft_id?`, `evaluation_id?`, `status`, `error?` |
| `AgentBuildBatch` | `batch_id`, scope, `build_session_id`, `revision`, `items: BuildItem[]`, `status`, `created_at`, `updated_at`; chỉ theo dõi tiến độ và lịch sử tạo hàng loạt |
| `ReuseCandidate` | `agent_id`, `version_id?`, `draft_id?`, `match_type=same_business/partial_overlap/different/uncertain`, `reuse_status=ready/draft/blocked/inactive`, `covered_requirements[]`, `missing_requirements[]`, `differences[]`, `blockers[]`, `reason` |
| `ReuseCheck` | `reuse_check_id`, scope, `requirement_hash`, `agent_catalog_revision`, `candidates[]`, `recommended_action`, `created_at` |
| `ReuseDecision` | `agent_key`, `action=reuse/resume/revise/create/clarify/repair`, `reuse_check_id`, `agent_id?`, `version_id?`, `draft_id?`, `reason`, `expected_catalog_revision` |
| `AgentSpec` | `agent_key`, `name`, `description`, `capabilities[]`, `system_prompt`, `model_config`, `context_config`, `react_config`, `tool_bindings[]`, `knowledge_bindings[]`, `skill_bindings[]`, `collaboration_policy`, `execution_policy` |
| `AgentManifest` | `schema_version`, `agent: AgentSpec`, `business_profile`, `requirements[]`, `catalog_revision`, `runtime_profile`; chỉ cấu hình một agent |
| `AgentDraft` | `draft_id`, `agent_id`, scope, `revision`, `manifest`, `manifest_hash`, `validation_report`, `source_version_id?`, `reuse_decision`, `batch_id?`, `created_at`, `updated_at` |
| `PublishedVersion` | `version_id`, `agent_id`, scope, `manifest`, `manifest_hash`, `source_draft_hash`, `evaluation_id`, `published_by`, `published_at`; luôn là phiên bản của một agent |
| `Deployment` | `deployment_id`, `agent_id`, scope, `active_version_id`, `revision`, `status`; cấu hình phát hành của từng agent |
| `EvaluationSnapshot` | `snapshot_id`, scope, `agent_id`, `draft_id`, `draft_revision`, `source_draft_hash`, `candidate_version_id`, `manifest`, `tool_snapshot_hash`, `test_context_hash`; đóng băng đầu vào đánh giá một agent |
| `EvaluationReport` | `evaluation_id`, `agent_id`, `draft_id`, `draft_revision`, `manifest_hash`, `snapshot_id`, `suite_version`, `runtime_profile_hash`, `tool_snapshot_hash`, `test_context_hash`, `status`, `metrics`, `hard_gate_failures[]`, `cases[]`, `started_at`, `finished_at` |
| `Conversation` | `conversation_id`, scope, `origin=manager/partner`, `partner_audience?`, `route_id?`, `route_revision?`, `mode=group/direct`, `timezone`, `state_revision`, `active_run_id?`; owner/audience binding không đổi ngầm |
| `RunGroup` | `group_id`, scope, `conversation_id`, `run_id`, `leader_session_id`, `members[]` gồm agent ID/version ID/session ID, `selection_reason`, `status`; chỉ được tập hợp lúc xử lý request hoặc eval sandbox; v1.4 thêm workflow_id?, created_run_id/active_run_id theo mục 17.2; group của workflow giữ qua các lượt chờ |
| `RunContext` | `run_id`, scope, actor, `partner_audience?`, `inbound_request_id?`, `route_id?`, `route_revision?`, `conversation_id`, `group_id?`, `mode=evaluation/production`, `version_pins[]`, `catalog_revision`, `deadline`, `budget`, `max_handoffs`, `status` |
| `ConversationMessage` | `message_id`, `client_message_id`, `conversation_id`, `sender`, `content`, `target_agent_id?`, `reply_to_message_id?`, `created_at` |
| `SharedState` | `revision`, `facts`, `entities`, `constraints`, `proposals`, `selected_refs`, `pending_questions`, `provenance` |
| `ToolCallRequest` | `call_id`, `run_id`, `agent_id`, `version_id`, `tool_version_id`, `arguments`, `arguments_hash`, `idempotency_key?`, `approval_id?` |
| `Approval` | `approval_id`, scope, `run_id`, `call_id`, `arguments_hash`, `quote_ref`, `amount?`, `expires_at`, `status`, `allowed_decider`, `audience_ref?`, `decision_actor?`; không coi inbound API key là quyền consent mọi giao dịch |
| `ExecutionResult` | `call_id`, `status`, `output`, `external_transaction_id?`, `error?`, `started_at`, `finished_at?` |

Catalog global chứa descriptor đối tác không có secret. Tool khả dụng thuộc connection của manager scope; grant nhận request đối tác không phải MCP connection hay tool binding. `llm_alias` phải ổn định, duy nhất trong toolkit và phù hợp giới hạn tên tool của model adapter; ID nghiệp vụ không phải tên hiển thị.
`schema_hash` là hash nội dung schema chuẩn hóa, không phải bằng chứng provider giữ nguyên hành vi. Với MCP không có version phía server, lưu observed snapshot và phát hiện drift; không hứa tái tạo hoàn toàn dịch vụ ngoài.
Model config tái sử dụng cấu trúc hiện tại, giữ credential ID thay cho secret. Skill/KB lưu ID và revision/content hash nếu có; không copy toàn bộ nội dung vào manifest.

`BuildItem` là discriminated union trong lịch sử batch: `create` có spec cho identity mới; `reuse` chỉ có reference tới agent đã có, không có spec sao chép để chỉnh ngầm; `revise` có target agent ID, source version và spec mới cho cùng identity. Chỉ create/revise tạo AgentDraft và EvaluationSnapshot riêng. Reference reuse trong batch ghi nhận kết quả kiểm tra lúc build, không ghim roster hay version cho request tương lai.

Mọi agent được sinh từ batch có AgentDefinition, hiển thị độc lập và tìm thấy trong cùng thư viện như agent tạo lẻ. Manifest không chứa danh sách agent cố định phải đi cùng, group ID, request ID hay workflow đội nhóm. `collaboration_policy` mô tả cách giao tiếp/handoff theo capability và giới hạn của agent; tên đồng đội hoặc agent ID được cung cấp từ group context khi runtime cần.

Lifecycle đóng băng snapshot từng agent trước eval; PublishedVersion phải giữ nguyên candidate version ID và manifest/hash đã được đánh giá. Các mock collaborator hoặc peer version dùng cho bài test nằm trong test context có hash, không trở thành thành viên bắt buộc trong cấu hình agent. Snapshot chưa publish chỉ eval runner đọc được, không xuất hiện trong catalog production. Publish hàng loạt kiểm tra từng snapshot/revision/hash và chỉ phát hành các agent được user chọn; không tạo snapshot/version/deployment cấp batch.

### 6.3. Port giao tiếp giữa các module

Các chữ ký sau mô tả interface cần hiện thực, không phải API đã tồn tại. Kết quả là DTO trong contracts, phương thức nghiệp vụ là async.

| Port / bên cung cấp | Phương thức tối thiểu | Bên dùng |
|---|---|---|
| `IdentityPort` / Chí Hoàng | `resolve_manager(authenticated_principal) -> Scope`, `check_scope_active(scope, uow?)`; kiểm tra role/membership hiện hành, không cấp quyền từ JWT stale hoặc body | Tất cả module qua dependency/worker guard |
| `PartnerRoutingPort` / Chí Hoàng | `resolve(partner_actor, routing_input) -> ResolvedPartnerRoute`, `revalidate(scope, route_id, expected_revision, actor, audience, operation, uow?)`; auth/grant/residence validation, errors mục 2.6 | Orchestration, Execution |
| `RegistryPort` / Đông | `list_available_tools(scope, query, capabilities, cursor)`, `get_tool_snapshot(scope, tool_version_id)`, `check_bindings(scope, bindings)`, `resolve_connection(scope, connection_id)` | Builder, Lifecycle, Execution |
| `DraftPort` / Tiến Anh | `create_draft(scope, manifest, reuse_decision, batch_id?)`, `get_draft(scope, draft_id)`, `update_draft(scope, draft_id, expected_revision, manifest, reuse_decision)`, `validate_draft(scope, draft_id)` | Builder, UI |
| `BuildBatchPort` / Tiến Anh | `create_batch(scope, build_session_id, items)`, `get_batch(scope, batch_id)`, `attach_draft(scope, batch_id, item_id, draft_id, expected_revision)`, `publish_selected(scope, batch_id, expected_revision, selections)` | Builder, UI; selections chứa draft ID/revision, evaluation ID và manifest hash của từng agent |
| `AgentReusePort` / Tiến Anh | `find_candidates(scope, business_profile, include_drafts)`, `get_candidate(scope, agent_id, version_id?)`, `validate_decisions(scope, requirements, reuse_decisions, expected_catalog_revision)` | Builder; Lifecycle dùng cùng logic khi tạo draft và publish |
| `PublishedCatalogPort` / Tiến Anh | `list_candidates(scope, capabilities)`, `get_version(scope, version_id)`, `get_deployment(scope, deployment_id)` | Orchestration, Execution |
| `EvaluationRunnerPort` / Huy Hoàng | `run_case(scope, version_snapshot, test_case, execution_mode)`, `cancel_case(scope, case_run_id)` | Lifecycle |
| `ExecutionPort` / Hoàng Dũng | `prepare_toolkit(scope, run_context, agent_spec)`, `execute(scope, request)`, `decide_approval(scope, approval_id, decision, actor, audience?)`, `get_call(scope, call_id)` | Orchestration, framework adapter, UI; execution đọc persisted run/audience để revalidate, không nhận quyết định từ actor tùy ý |
| `ConversationPort` / Huy Hoàng | `create(scope, mode, direct_agent_id?)`, `send_message(scope, message)`, `read_state(scope, conversation_id)`, `patch_state(scope, conversation_id, expected_revision, patch)` | Manager UI và adapter nội bộ đã kiểm tra actor/audience; partner không được gọi trực tiếp bằng Scope tự khai |
| `PartnerIngressPort` / Huy Hoàng | `accept(partner_actor, envelope) -> InboundReceipt`, `wait_for_result(partner_actor, request_id, external_user_id, deadline)`, `read_result(partner_actor, request_id, external_user_id)`, `stream_events(partner_actor, conversation_id, external_user_id, cursor?)`; accept commit trước wait; result wait không giữ transaction hoặc gọi lại runtime | Partner HTTP adapter và legacy ticket bridge của Chí Hoàng; auth/audience recheck trước response, không trả raw RunContext/secret |
| `SecretStorePort` / Chí Hoàng | `put(scope, secret_input) -> credential_ref`, `resolve(scope, credential_ref)`, `revoke(scope, credential_ref)` | Registry, Execution; không export `resolve` ra browser |
| `JobPort` / Chí Hoàng | `enqueue(scope, job_type, payload, idempotency_key, uow?)`, `claim(worker_id, lease)`, `heartbeat(job_id)`, `complete(job_id, result)`, `fail(job_id, error)`; enqueue ghi job/outbox cùng transaction khi có uow | Registry sync, ingress/dispatch, evaluation, reconciliation |
| `AuditPort` / Chí Hoàng | `record(scope, event_type, resource_ref, outcome, redacted_metadata, uow?)`; lưu actor/audience từ context đã xác minh | Tất cả module |

Port được inject vào constructor/service factory. Chỉ composition root trong `integrations/` biết concrete implementation của mọi module. Không làm `registry -> execution -> registry` bằng import vòng.
Lúc chạy eval, `execution_mode` do backend gán và chỉ dùng mock/sandbox; người dùng không thể đổi production thành eval để bỏ policy.

`uow` là unit-of-work/transaction do Foundation cung cấp trong cùng database. Ingress tạo transaction rồi gọi PartnerRoutingPort.revalidate với cùng uow, ghi request/conversation và gọi JobPort.enqueue để ghi job/outbox trong transaction đó; các port không tự commit khi có uow. Khi không truyền uow, check riêng không thay thế recheck lúc commit. Huy Hoàng không ghi trực tiếp bảng route/job/outbox; Chí Hoàng không ghi bảng conversation/run bằng SQL riêng. `allowed_operations` tối thiểu phân biệt `submit_request`, `read_result`, `reply`, `submit_consent`; grant không bao giờ cho `build`, `publish`, `configure_agent`. Mỗi thao tác vẫn kiểm tra audience và ownership, không chỉ có tên operation trong grant. V1.4 thêm close_workflow/receive_events và provider publish_job_event theo purpose/grant tương ứng; cùng uow áp dụng cả inbox → workflow/public event → trigger, xem mục 17.4–17.5.

`find_candidates` trả cả metadata draft/published, hồ sơ nghiệp vụ và các điều kiện so sánh, không biến draft thành ứng viên runtime. Builder so yêu cầu cụ thể với candidates và trình bày decision; Lifecycle revalidate decision trước ghi dữ liệu. `validate_decisions` không đồng nghĩa giữ chỗ: tạo identity/draft thực tế phải recheck trong transaction. Scope và version check không tin kết quả UI hoặc score LLM.

### 6.4. State machines và sự kiện

```text
Partner route: pending_confirmation → active → disabled / revoked
Inbound: authenticate → resolve unique route + audience → persist accepted
     → queued → running → completed / failed
     route/membership/grant đổi → blocked_route_changed / blocked_authorization
     resume chỉ sau revalidation, không đổi owner của request cũ

MCP: disabled → connecting → syncing → ready
                         ↘ error/auth_required
     ready → syncing / disabled / degraded

Build: analyzing → checking_existing → proposal_ready / needs_clarification
     mọi agent cần tạo đã có, không đổi cấu hình → completed_reused
     single/batch proposal confirmed → generate draft riêng cho create/revise
     agent còn draft → resume existing draft; agent lỗi kết nối → repair_required

Batch: building → ready / partially_ready → partially_published / completed
     theo dõi từng item độc lập; không sinh group production hoặc team deployment

Draft/evaluation: draft → validating → invalid | evaluable
     evaluable → evaluating → failed | passed
     passed + explicit user publish → immutable version + active deployment
     chỉnh draft → revision mới; evaluation cũ không còn đủ điều kiện publish

Run: request có Scope đã xác minh → created → planning (Leader chọn từ thư viện tài khoản đích)
     → group/session được tạo hoặc bổ sung → running ↔ awaiting_user / awaiting_approval
     → completed | failed | cancelled
     v1.4: một lượt kết thúc không đóng workflow/ticket; checkpoint + durable trigger nối lượt sau
Workflow: accepted → active
     → awaiting_user / awaiting_approval / awaiting_confirmation / waiting_external_event
     → active khi có reply/approval/event hợp lệ
     → closed bằng explicit close, hoặc auto-close chỉ với policy read-only đã publish
     → blocked/needs_attention khi cần xử lý (chi tiết mục 17.2)

Tool call: proposed → awaiting_approval → approved → executing
     → succeeded | failed | unknown
     rejected / expired dừng trước execution
```

Các event chính: `partner.route_activated`, `partner.route_changed`, `partner.route_revoked`, `partner.request_accepted`, `partner.request_blocked`, `mcp.tools_synced`, `mcp.disabled`, `mcp.schema_changed`, `build.reuse_proposed`, `build.completed_reused`, `batch.item_updated`, `batch.published`, `agent.catalog_changed`, `draft.updated`, `evaluation.completed`, `deployment.changed`, `group.member_added`, `conversation.message`, `state.updated`, `approval.required`, `approval.resolved`, `execution.completed`, `execution.unknown`, `run.completed`.
Bổ sung v1.4: workflow.accepted, workflow.status_changed, workflow.awaiting_user, workflow.awaiting_confirmation, workflow.blocked, workflow.closed, provider.event_received, provider.event_quarantined, operation.status_changed, ticket.status_changed, assistant.message, event.cursor_expired. Provider/infrastructure events là nội bộ; chỉ public projection có audience rõ được đọc qua API/SSE. Event/status domain-specific nằm trong protocol versioned của integration và được map vào envelope chung; không thêm state máy lõi cho từng ngành. Gắn causation ID để event provider không bị áp dụng lặp hoặc nhầm với public event.
Event công bố sau DB commit bằng outbox hoặc cơ chế tương đương có replay. Không để DB đã publish nhưng mất event làm client/candidate catalog sai vĩnh viễn.

### 6.5. Phân chia persistence và migration

| Owner module | Nhóm bảng mới, prefix `wf_` |
|---|---|
| Foundation | `wf_credentials`, `wf_jobs`, `wf_outbox`, `wf_audit_events`, `wf_management_verifications`, `wf_partner_routes`, `wf_partner_route_revisions`; reuse auth_users/domain/area/partner client tables, không tạo hệ account thứ hai |
| Registry | `wf_mcp_definitions`, `wf_mcp_connections`, `wf_tool_versions`, `wf_catalog_revisions` |
| Builder | `wf_build_sessions`, `wf_build_messages`, `wf_build_proposals` |
| Lifecycle | `wf_agent_definitions`, `wf_agent_catalog_revisions`, `wf_agent_reuse_checks`, `wf_build_batches`, `wf_build_batch_items`, `wf_drafts`, `wf_versions`, `wf_deployments`, `wf_evaluation_snapshots`, `wf_evaluation_suites`, `wf_evaluations`, `wf_evaluation_cases`, `wf_release_events` |
| Orchestration | `wf_inbound_requests`, `wf_partner_conversation_bindings` (gồm ticket/workflow/group binding), `wf_conversations`, `wf_messages`, `wf_runs`, `wf_run_members`, `wf_shared_states`, `wf_runtime_bindings` |
| Execution | `wf_tool_calls`, `wf_approvals`, `wf_booking_operations`, `wf_execution_events` |

Mỗi module viết `_tables.py`, `_repository.py` và mô tả schema của mình; không thêm method vào `StorageBase` cho mọi nghiệp vụ Workforce. Reuse SQL engine/session qua Foundation.
Nguyễn Chí Hoàng gom metadata và tạo revision thật trong chuỗi Alembic hiện hữu `src/agentscope/app/storage/_sql/_alembic/versions/`. Không tạo nhánh migration thứ hai và không cho sáu người cùng tạo revision “0009”.
Tên revision mới quyết định từ head thực tế lúc merge; không giả định `0008` luôn là head.
Foreign key giữa module tham chiếu tên bảng/ID đã chốt; không import ORM model của nhau. Mỗi module chỉ ghi bảng mình sở hữu, gọi port để thay đổi bảng module khác.
Các thao tác publish, activate/rollback, approval consume và dedupe execution phải có transaction/unique constraint/CAS phù hợp. Migration phải kiểm tra cả DB mới lẫn DB đã có dữ liệu; không xóa bảng role/domain/area cũ để đơn giản hóa.

Unique constraint `(tenant_id, domain_id, area_id, manager_account_id, business_key)` bảo vệ canonical agent identity, không đặt uniqueness lên tên hay nguyên system prompt. Cùng nghiệp vụ ở hai tài khoản ban quản lý là hai tài nguyên độc lập hợp lệ, không gộp/reuse chéo. Revision nâng cấp dùng cùng identity; duplicate build đang chạy trả draft reference đang có. Bản ghi pending có liên kết draft/job, trạng thái và recovery để không chặn vĩnh viễn sau crash. Catalog index có thể cập nhật bất đồng bộ nhưng bước tạo identity/publish kiểm tra DB và các bản pending để chống stale index. Catalog revision/CAS được kiểm tra trong transaction; không giữ transaction mở trong suốt lời gọi LLM. Khi revision đổi, rerun matching trước thử lại.

Route active có partial unique index `(tenant_id, partner_client_id, external_management_ref)` và lịch sử revision; việc kích hoạt/chuyển grant phải khóa khóa-tra-route để tránh hai đích active. `wf_inbound_requests` unique `(tenant_id, partner_client_id, external_request_id)` với payload hash và scope immutable: không thêm manager vào unique key để replay sau remap không thành request mới. Conversation binding unique `(tenant_id, partner_client_id, external_user_id, external_conversation_id)`; với route ticketed còn có unique `(tenant_id, partner_client_id, external_user_id, external_ticket_id)` và check/unique bảo đảm một external ticket không trỏ hai conversation/workflow/group, một external conversation không trỏ hai external ticket. Binding giữ domain/area/manager/route revision/workflow/conversation/group đã pin. FK/check/transaction phải bảo đảm client/domain/area/account nhất quán; không dùng uniqueness trên role hoặc area thay cho manager owner. Các ID ngoài là chuỗi opaque có giới hạn độ dài; không tự lowercase/trim làm hai mã đối tác khác nhau nhập thành một nếu hợp đồng chưa quy định.

Migration backfill tài nguyên legacy từ `user_id` sang manager scope khi membership có căn cứ. Tài khoản cũ thiếu domain/area cần trạng thái chờ xác minh/bổ sung với đường onboarding rõ, không cấp bừa area và không báo login thành công rồi vòng 401 vô hạn. Ticket/memory chỉ có area phải đối soát owner như mục 2.6.7 trước khi mở cho Workforce. Không thay thế dữ liệu/auth schema đang có bằng reset DB.

`wf_build_batch_items` chỉ liên kết lịch sử thao tác tạo hàng loạt tới draft/agent tương ứng. Membership production chỉ thuộc run: dùng TeamRecord hiện có cùng `wf_run_members`/`wf_runtime_bindings` do Orchestration sở hữu. Không tạo bảng team template/version; không dùng `wf_team_agent_refs` của thiết kế cũ. Không cascade xóa agent khi xóa batch/group và không tạo một AgentDefinition mới cho mỗi runtime reference. Reuse không ghi thêm agent/version cũ. Candidate và identity tạm của draft không đủ điều kiện chạy production. Với legacy AgentRecord có sẵn, adapter index/mapping giữ liên kết agent ID cũ; dữ liệu thiếu profile cần bổ sung để matching, không tự kết luận là agent hoàn toàn mới.

### 6.6. API và export frontend

Tất cả đường dẫn dưới đây nằm sau `/workforce/v1`:

| Owner | Endpoint cần cung cấp |
|---|---|
| Chí Hoàng | `/auth/register`, `/auth/login`, `/auth/refresh`, `/auth/logout`, `/me`; `GET /directory/domains`, `GET /directory/domains/{id}/areas`; `GET/POST /partner-routes`, `PATCH /partner-routes/{id}`; `POST /partner/routes/{id}/confirm`; `PUT /partner/residences/{id}` qua residence adapter; `/jobs/{id}`; health/readiness Workforce |
| Đông | `GET /mcps`; `POST /mcps/{id}/connections`; `GET /connections`; `PATCH /connections/{id}`; `POST /connections/{id}/sync`; `GET /tools`; `GET /tools/{tool_version_id}` |
| Hữu Nghĩa | `POST /builds`; `GET /builds/{id}`; `POST /builds/{id}/messages`; `POST /builds/{id}/confirm-proposal`; `GET /builds/{id}/events`; `POST /builds/{id}/cancel`; `POST /builds/{id}/resume` |
| Tiến Anh | `POST /drafts`; `GET/PATCH /drafts/{id}`; `POST /drafts/{id}/validate`; `POST /drafts/{id}/evaluations`; `GET /evaluations/{id}`; `POST /evaluations/{id}/cancel`; `POST /drafts/{id}/publish`; `GET /batches/{id}`; `POST /batches/{id}/publish`; `POST /agents/reuse-check`; `GET /agents`; `GET /versions/{id}`; `POST /versions/{id}/fork`; `GET /deployments`; `POST /deployments/{id}/rollback` |
| Huy Hoàng | `POST /conversations`; `GET /conversations/{id}`; `GET/POST /conversations/{id}/messages`; `GET /conversations/{id}/events`; `GET /conversations/{id}/group`; `POST /conversations/{id}/members`; `GET /conversations/{id}/state`; `GET /agents/{id}/usage`; `POST /runs/{id}/cancel`; `POST /partner/requests`, `GET /partner/requests/{id}`, `GET /partner/conversations/{id}/events` |
| Hoàng Dũng | `GET /conversations/{id}/approvals`; `POST /approvals/{id}/decision`; `GET /executions/{id}`; `GET /booking-operations/{id}`; `POST /partner/approvals/{id}/decision` với route/audience/allowed_decider guard riêng |

`ExecutionPort.execute` là đường nội bộ; không mở API công khai cho phép client gửi tùy ý tool/version/credential và gọi thẳng MCP.
Auth/directory endpoints có thể adapter tới service hiện tại, không tạo password/token store thứ hai. Register nhận domain/area, role do backend cố định; `/me` trả manager ID, domain/area và trạng thái xác minh. `GET/POST/PATCH /partner-routes` chỉ dùng JWT manager, owner luôn lấy từ principal. `POST /partner/routes/{id}/confirm` chỉ dùng credential của đúng partner client; route_id không cấp quyền. Pending route/ref được trao đổi khi onboarding qua kênh cấu hình đã xác minh, không mở directory toàn bộ manager cho partner duyệt.

Các `/partner/requests`, partner SSE và partner approval chỉ dùng machine principal. Customer POST lấy external_user_id từ body; GET request/snapshot/history/SSE bắt buộc query external_user_id do backend đã xác thực người dùng cung cấp, đối chiếu audience đã lưu cùng client/grant. Query không tự cấp quyền. Reply là request mới với command_type=workflow_reply và workflow_id cũ, trong cùng external_conversation_id, external_request_id mới. Manager JWT không bị giả lập để phục vụ partner; partner key không truy cập endpoint build/settings/publish.
Khi publish, request bắt buộc chỉ ra `expected_revision`, `evaluation_id`, `manifest_hash` đã xem. Rollback chỉ đổi active pointer tới version thuộc user, qua kiểm tra compatibility hiện tại; không sửa run đang chạy hoặc đảo ngược booking đã thực hiện.

`POST /batches/{id}/publish` nhận revision batch và selections với draft ID/revision, evaluation ID/hash từng agent được chọn. Kiểm tra và commit toàn bộ selections hợp lệ trong một transaction; nếu một selection stale thì trả lỗi, không publish dở danh sách đó. User có thể chọn riêng các agent đã đạt mà chưa cần chờ agent khác trong batch; phần không chọn giữ nguyên trạng thái. Batch publish chỉ là thao tác thuận tiện trên nhiều agent, không tạo một sản phẩm team. `GET /agents/{id}/usage` do Orchestration cung cấp, hiển thị các group/run đã dùng agent và phiên bản liên quan theo scope.

Endpoint cancel/resume và worker recovery phải đọc trạng thái DB để quyết định bước tiếp theo; không chạy lại tool có side effect chỉ vì người dùng refresh trang. Các endpoint bắt đầu build, eval, publish và gửi message nhận idempotency key/client ID tương ứng.

`POST /agents/reuse-check` nhận hồ sơ nghiệp vụ/yêu cầu, trả ReuseCheck trong scope. Build proposal/confirm mang các ReuseDecision; response phân biệt `reused_agents`, `created_agents`, `revised_agents`, `blockers`. Lỗi 409 cho quyết định cũ hoặc tạo trùng: `REUSE_DECISION_STALE`, `AGENT_ALREADY_EXISTS`, `AGENT_BUILD_IN_PROGRESS`. Khi mọi agent yêu cầu đã có và không thay đổi, build result trả các `agent_id`/`version_id` sẵn có và `status=completed_reused`, không gọi publish lần nữa. API build/confirm/publish không gọi ConversationPort hoặc TeamCreate để tạo group production.

Mỗi module backend export `create_router(...)` từ `__init__.py` của module khi triển khai. Nguyễn Chí Hoàng include routers tại composition root.
Frontend có API client riêng trong feature (`api.ts`), chỉ dùng transport/token provider từ `shared/`; không tranh sửa `src/api/index.ts` hoặc `types.ts` cũ.

Frontend export tối thiểu:

| Thư mục | Export/page |
|---|---|
| `shell/` | `WorkforceLayout`, `WorkforceLoginPage`, route composition |
| `integrations/` | `WorkforceIntegrationsPage` |
| `builder/` | `WorkforceBuilderPage` |
| `agents/` | `WorkforceAgentsPage`, `WorkforceAgentSettingsPage`, `WorkforceEvaluationPage` |
| `chat/` | `WorkforceChatPage` |
| `approvals/` | `WorkforceApprovalCard`, `WorkforceExecutionStatus` |

Module frontend export qua `index.ts` riêng. Feature locale nằm trong feature; shared UI và global locale chỉ Chí Hoàng sửa. UI tái sử dụng component hiện có, không thay design system hay thêm dependency song song.

### 6.7. Hợp đồng bổ sung API/event/workflow v1.4

Mục 17.3 là bộ API chính thức trong kế hoạch; 17.4 chốt DTO/ports/schema/ownership; 17.5–17.6 quy định transaction, continuation, retry, cursor, ACK và retention. Tất cả sáu owner phải đọc cùng phần này trước khi code. Các DTO có workflow_id là bổ sung cho luồng dài hạn, không đổi một agent thành team artifact hoặc bỏ Scope. Phần bảng persistence mục 6.5 được mở rộng bằng bảng tại 17.4.

## 7. Nguyễn Chí Hoàng — Foundation, contracts và tích hợp

### Mục tiêu

Cho năm module còn lại một hợp đồng chạy chung, một identity một role, một đường tích hợp với AgentScope và một môi trường có thể kiểm thử. Đây là người tích hợp kỹ thuật; không phải role admin sản phẩm.

### Công việc theo thứ tự

- [ ] **NCH-01 — Baseline:** ghi nhận worktree và migration head; thống nhất baseline để team tạo nhánh. Giữ các thay đổi đã có, không tự commit/reset. Kiểm tra dependency/test runner hiện hữu.
- [ ] **NCH-02 — Contracts sớm:** tạo `contracts/_identity.py`, `_partner_routing.py`, `_catalog.py`, `_manifest.py`, `_batch.py`, `_evaluation.py`, `_conversation.py`, `_execution.py`, `_ports.py`, `_events.py`, `_errors.py`. Xuất JSON Schema và TypeScript vào `shared/contracts/`; cung cấp manager Scope, ActorContext, route/request fixtures, agent đơn, batch và group runtime, cùng error fixtures không chứa secret. Bản tối thiểu cần bàn giao trong nhịp khởi động để giải phóng các nhánh.
- [ ] **NCH-03 — Identity một role:** giữ `AREA_MANAGER`, domain/area và hashing/JWT/refresh hiện có. Viết `foundation/_identity.py`, `_auth.py`, `_management_verification.py`; xác minh quyền quản lý, kiểm tra membership hiện hành, triển khai IdentityPort/Scope bốn trường. Không tin `X-User-ID` hoặc Scope trong body; hỗ trợ onboarding tài khoản cũ thiếu domain/area, không giả danh manager để nhận request đối tác.
- [ ] **NCH-04 — Đăng nhập UI:** `shell/` có register/login/logout và session restore; register chọn domain/area từ directory và role tự cố định. Hiện tài khoản/khu vực đang quản lý, trạng thái xác minh và lỗi mapping rõ; không có dropdown chọn role. `shared/http.ts` có auth, refresh, lỗi chuẩn và SSE transport; cookie/CORS theo origin cấu hình, không hardcode tenant khác backend.
- [ ] **NCH-05 — Foundation services:** `_database.py`, `_jobs.py`, `_credentials.py`, `_audit.py`, `_outbox.py`, `_clock.py`, `_config.py`. Durable job record/lease, secret mã hóa bằng key ngoài DB, audit đã redact, clock inject được cho test.
- [ ] **NCH-06 — Composition:** `integrations/_bootstrap.py`, `_routers.py`, `_runtime_hooks.py`, `_workers.py`. Reuse `create_app`, storage, bus, workspace manager và các factory; bật Workforce có cấu hình rõ ràng. Import AgentScope cơ bản không tự kéo service dependency chưa cài.
- [ ] **NCH-07 — Runtime hook:** phối hợp Huy Hoàng/Hoàng Dũng tạo đường đọc pinned manifest, session mapping và toolkit assembly được lọc trước khi agent chạy. Cài execution guard cho mọi tool call Workforce, kể cả khi permission mode cũ là bypass. Chặn legacy CRUD/chat/config endpoint sửa hoặc chạy vòng qua managed Workforce resources.
- [ ] **NCH-08 — Migration tập trung:** thu schema module, tạo một chuỗi migration có thứ tự và tests upgrade. Giữ auth/domain/area/partner key/residence hiện có; bổ sung owner/route/grant và backfill có căn cứ theo mục 2.6/6.5. Area/business cũ không được trở thành đường vượt manager/audience filter. Reuse key provisioning hiện tại nếu phù hợp nhưng secret vận hành không cấp grant tới mọi manager; không đổi/xóa dữ liệu để né migration.
- [ ] **NCH-09 — Frontend composition:** nối các page vào `/workforce/...` và sidebar; dùng export từng feature, chưa merge module nào thì không import file chưa tồn tại làm vỡ build. Khi tất cả có, bật feature đầy đủ và xóa placeholder staging.
- [ ] **NCH-10 — Dev/CI:** `scripts/workforce/` chứa schema generation/contract validation/migration smoke tooling; `deploy/workforce/` chứa cấu hình dev/test và runbook. Chỉnh compose/.env.example theo yêu cầu tích hợp; không sửa `.env` cá nhân. Add CI chạy module tests, migration, frontend build và e2e suite đã đủ điều kiện.
- [ ] **NCH-11 — Contracts tái sử dụng và batch:** bổ sung `contracts/_reuse.py`, DTO/ports/errors và TypeScript ở mục 6. Nối AgentReusePort/BuildBatchPort cho Builder, index legacy agent, migration canonical identity/batch/uniqueness do Anh đề xuất. Kiểm tra không có team template/version/deployment phát sinh từ Builder; runtime mới sở hữu membership. Không để năm module tự xây các cách xác định agent trùng khác nhau.
- [ ] **NCH-12 — Partner mapping và filter nền:** `foundation/_partner_routing.py`, `_route_grants.py`, `_route_repository.py`, `_tables.py`, `_router.py`; triển khai PartnerRoutingPort, route grant/xác nhận/thu hồi, atomic revision checks với uow, scope/audience guard dùng chung. `shell/partner-routes/` quản lý grant của tài khoản hiện tại; `scripts/workforce/` import/validate mapping có audit và dry-run. `integrations/_business_adapter.py` nối auth/partner credential/residence/ticket/memory cũ, filter GET/PATCH/search/result/download đầy đủ và cập nhật tài liệu API cũ khi code thay đổi. Không tự viết dispatch/run của Huy Hoàng; bàn giao verified route và errors/transaction contract trước.
- [ ] **NCH-13 — Contracts API/lifecycle:** Chốt DTO/ports/schema theo mục 17.3–17.4, gồm `external_ticket_id?`, `TicketConversationBinding`, lỗi binding và public event projection. Mọi request result có `workflow_state` + `next_action`; persisted-result/`wait_for_result` trả `200` khi xong và `202/watch_request` khi pending. Contract biểu diễn response-only, interactive và external-tracking không có field domain cố định; Provider Event là capability tùy chọn. Close trả `200/none`; read-only auto-close theo policy không gọi close. Xuất types/fake hai ticket/hai hộp chat sớm; protocol chi tiết thuộc Đông, persistence/dispatch thuộc Huy Hoàng.
- [ ] **NCH-14 — Durable transport và xác thực:** triển khai scoped completion signal cho bounded-wait và SSE notification/recovery; ProviderAuth/event worker chỉ kích hoạt cho integration có external-tracking. Tín hiệu chỉ đánh thức waiter/stream, kết quả chuẩn đọc DB. Response-only/interactive không được tạo queue/timer/Event dependency giả. Dùng wf_outbox/JobPort, không giữ transaction khi chờ và không viết HTTP sender tới đối tác.
- [ ] **NCH-15 — Nối runtime và migration:** integrations/async_runtime/ nối worker handlers, RuntimeContinuationPort, AgentScope wake/session/parked HITL và business ticket bridge. Chỉ người này sửa core/lifespan/business/migration thật. Giữ owner/audience, scope revalidation và state qua restart, thống nhất metadata export của các folder con; không ghi trực tiếp bảng inbox/operation/workflow module khác.
- [ ] **NCH-16 — Bàn giao tích hợp và vận hành:** test cả ba pattern, mọi next_action, `200/202`, retry, SSE optional/reconnect và Provider signature chỉ ở ca tracking. OpenAPI/sample phải có read-only, plan/booking sync, async operation và cùng một external user mở hai external ticket/conversation chạy xen kẽ; schema không nhận internal ticket/conversation/group làm routing input. Proxy timeout lớn hơn `PARTNER_TURN_WAIT_SECONDS`. Runbook replay/retention chỉ áp dụng event log có dữ liệu; không yêu cầu đối tác dựng receiver.

### Đầu vào và bàn giao

Nhận schema/hook/dependency requests từ năm người. Bàn giao ports và fake mẫu trước, runtime hook nhỏ sau; review integration hàng ngày theo các PR nhỏ để không thành điểm nghẽn cuối sprint.
Test trong `tests/workforce/foundation/`: account role cố định và chọn domain/area hợp lệ; quyền quản lý cần xác minh; fake user header/manager ID không vượt JWT/route grant; A không đọc B kể cả cùng area; route chỉ active sau xác nhận đúng client, race kích hoạt và thu hồi; secret không lộ, job lease recovery, migration/backfill/quarantine, filtered toolkit và pinned version không đổi theo legacy settings.

### Hoàn thành khi

Một AREA_MANAGER đăng ký/chọn domain-area/đăng nhập được, mapping đối tác resolve đúng tài khoản với bằng chứng authorization; năm module mount được, DB upgrade được, frontend hoạt động và run đi qua scope/tool guard. Các regression liên quan vẫn qua. Ghi hướng dẫn chạy chính xác vào `docs/workforce/handoffs/nguyen-chi-hoang/STATUS.md`.

## 8. Nguyễn Phương Đông — MCP Registry và kho tool

### Mục tiêu

Người dùng thấy MCP đối tác, bật MCP và có toàn bộ tool được đăng ký để Builder lựa chọn. Không cần admin cấp quyền.

### Công việc theo thứ tự

- [ ] **NPD-01 — Schema và catalog import:** `registry/_models.py`, `_tables.py`, `_repository.py`, `_catalog_import.py`. Partner catalog versioned, mô tả connection fields; import idempotent không trùng MCP. Cung cấp thư viện import để Chí Hoàng nối script vận hành; không tạo portal role mới.
- [ ] **NPD-02 — Connection lifecycle:** `_connections.py`, `_discovery.py`; tạo connection theo manager Scope đủ domain/area/account, validate config, nhận secret qua SecretStorePort, connect/discover/close có timeout. Cùng area không dùng chung credential hoặc tool catalog nếu khác tài khoản; grant inbound không thay thế MCP connection. Support transports repo đã có qua MCPClient; STDIO cần workspace phù hợp, không chạy command đối tác trực tiếp trên host production.
- [ ] **NPD-03 — Đăng ký đầy đủ:** lấy toàn bộ trang discovery nếu server phân trang; nếu MCPClient hiện tại thiếu pagination/refresh cần adapter trong module hoặc yêu cầu core patch. Discovery không áp bộ lọc agent. Tạo `tool_version_id`, hash và alias; giữ `output_schema` nullable khi server không cung cấp.
- [ ] **NPD-04 — Đồng bộ atomic:** đăng ký snapshot toàn bộ hoặc báo lỗi rõ, không hiển thị “ready đầy đủ” khi discovery chưa xong. Retry không trùng tool. Unique identity gắn connection/source và tên gốc, không chỉ display name.
- [ ] **NPD-05 — Availability/drift:** `_availability.py`; tắt MCP giữ binding/history, chặn tool mới ngay khi check server-side; mất credential/endpoint lỗi đánh dấu trạng thái. Tool bị xóa hoặc đổi schema tạo snapshot mới và impact report cho agent liên quan, không tự sửa published version.
- [ ] **NPD-06 — Tìm kiếm cho Builder:** `_search.py`; filter ownership, enabled/ready, capabilities và schema; text search trước, bổ sung embedding qua adapter hiện có nếu cần. Không bắt buộc vector search cho bộ tool nhỏ; index version phải khớp catalog revision.
- [ ] **NPD-07 — RegistryPort/API:** `_service.py`, `_router.py`; list tools và check binding. Resolve connection trả credential reference ở interface nội bộ, không trả secret ra browser. Một nguồn trạng thái Workforce connection; nếu bridge MCPRecord thì có mapping rõ và sync một chiều.
- [ ] **NPD-08 — UI:** `integrations/` có danh sách MCP, bật/tắt, form credential, trạng thái connecting/syncing/ready/error, số tool, bảng schema/nguồn, resync, lỗi và agent bị ảnh hưởng. Có loading/empty/error/retry, không chỉ card tĩnh.
- [ ] **NPD-09 — Kiểm tra agent ứng viên:** `check_bindings` trả blocker cụ thể cho version dự kiến reuse: MCP tắt, schema drift, credential hết hạn hoặc tool bị xóa. Phân biệt lỗi tạm thời với thiếu capability; thông báo cho Lifecycle/Builder theo port, không đề nghị tự clone agent để xử lý lỗi kết nối. Test recheck khi catalog đổi sau đề xuất reuse.
- [ ] **NPD-10 — Registry protocol và continuation capability:** registry/event_protocols/ lưu version/hash gắn tool snapshot: effect read/write, kết quả terminal hay pending, mapping operation/job ID/client_reference, Provider Event API/status-query nếu có, event schema, ordering/transition/timeout và completion policy. Protocol phải biểu diễn được tool đồng bộ không tracking, interactive approval và async tracking; không gắn capability vào tên lĩnh vực. Metadata do integration cấu hình/validate, không giả định MCP discovery tự cung cấp đủ và không nhận arbitrary callback URL trong prompt.
- [ ] **NPD-11 — Chuẩn hóa event và kiểm tra năng lực:** Triển khai AsyncProtocolPort, adapter deterministic normalize event, version/snapshot-vs-delta rules và capability coverage cho Builder/Lifecycle/Execution. Protocol drift hoặc MCP bị tắt không sửa snapshot của job đang theo dõi; tách khả năng nhận Provider Event API hợp lệ cho job cũ với quyền gọi tool mới. Không sở hữu HTTP provider ingress, inbox, credentials hoặc workflow state.
- [ ] **NPD-12 — UI và contract tests protocol:** integrations/event_channels/ hiển thị hỗ trợ tạo job/nhận Provider Event API/status-query MCP, trạng thái cấu hình và blocker; không hiển thị secret. tests/workforce/registry/event_protocols/ kiểm tra create-only, provider-event-ready, query-only, schema drift, namespace và normalization/order cases. Bàn giao fake protocol cho Nghĩa/Anh/Dũng ngay nhịp A.

### Test và hoàn thành

- [ ] MCP có 6 tool → bật thành công catalog có đủ 6; Builder chưa chạy thì chưa có agent binding nào.
- [ ] Hai MCP trùng tên tool không va chạm; hai user bật cùng MCP không dùng chung credential/state.
- [ ] Discovery nhiều trang, lỗi giữa chừng, retry, credential hết hạn, tắt trong phiên đang chạy.
- [ ] Output schema vắng vẫn đăng ký hợp lệ; input schema sai bị báo cụ thể.
- [ ] Tool mới không tự xuất hiện trong toolkit agent đã publish; schema drift được phát hiện.

Có thể làm ngay bằng MCP fake và SecretStore fake; không chờ Builder. Đầu ra cho Nghĩa/Anh/Dũng là RegistryPort và sample tool snapshots. Bàn giao ở `docs/workforce/handoffs/nguyen-phuong-dong/`.

## 9. Bùi Hữu Nghĩa — Builder tạo một/nhiều agent qua chat

### Mục tiêu

Từ mô tả tiếng Việt, tạo đề xuất rồi sinh một hoặc nhiều draft agent độc lập, có tool binding đúng, lý do chọn và chẩn đoán thiếu năng lực. Mọi kết quả phát hành đi vào cùng thư viện; không tạo group hoặc roster production ở bước build.

### Công việc theo thứ tự

- [ ] **BHN-01 — Build session:** `builder/_models.py`, `_tables.py`, `_repository.py`, `_service.py`; lưu hội thoại build, đề xuất, lựa chọn và trạng thái. Idempotency theo client message/build request để retry không sinh nhiều draft.
- [ ] **BHN-02 — Requirement extraction:** `_requirements.py`, `_planner.py`; phân biệt `single`/`batch`, mục tiêu, nhiệm vụ, input/output, bắt buộc/tùy chọn, công cụ và câu hỏi thiếu. “Tạo team agent” được hiểu là batch nhiều agent độc lập; “hãy đặt chuyến đi” là request runtime, không tự biến thành yêu cầu build. Structured output có schema; xử lý output lỗi/retry có giới hạn.
- [ ] **BHN-03 — Tool selection:** `_tool_selector.py`; query RegistryPort, filter capability/schema/availability, rerank phù hợp. Lưu selection reason và capability coverage cho mỗi agent. Không đưa mọi tool catalog vào prompt một lần khi catalog lớn.
- [ ] **BHN-04 — Đề xuất và xác nhận:** `_proposal.py`; người dùng thấy số agent, nghiệp vụ mỗi agent, khả năng phối hợp theo capability, tool dự kiến và phần thiếu. Sửa đề xuất bằng chat; confirm rồi tạo batch và các draft độc lập qua port Lifecycle. Không bắt user chọn leader/roster cho batch. Builder có ngân sách token/số vòng và cancel/resume từng item.
- [ ] **BHN-05 — Generate manifest:** `_generator.py`; sinh manifest riêng từng agent: system prompt, model qua credential hiện có, context/react config, collaboration policy, tool binding, KB/skill binding. Generate các item độc lập song song trong giới hạn concurrency/cost; item lỗi giữ trạng thái riêng và retry không tạo lại item đã xong. Không viết prompt phụ thuộc tên đồng đội cùng batch hoặc request du lịch cụ thể.
- [ ] **BHN-06 — KB và skill:** `_knowledge_selector.py`, `_skill_generator.py`; chọn KB/skill thuộc user; có thể sinh skill dạng hướng dẫn có version/hash. Skill không được cấp thêm tool ngoài binding hay tự cài/chạy code tùy ý. Artifact skill cần được validate/eval cùng manifest.
- [ ] **BHN-07 — Validate bước build:** `_validator.py`; missing capability có code và gợi ý bật MCP tương ứng. Không bịa tool ID; recheck catalog revision trước tạo draft. Dùng DraftPort của Anh, không tự ghi `wf_drafts`/`wf_versions`.
- [ ] **BHN-08 — UI:** `builder/` có chat, câu hỏi làm rõ, danh sách agent đề xuất, tool/selection reason, panel thiếu capability, confirm và tiến độ/eval riêng từng agent. Hiển thị rõ “Tạo nhiều agent” là thao tác hàng loạt; sau publish dẫn tới từng agent trong thư viện hoặc kết quả batch, không sang một team template.
- [ ] **BHN-09 — So nghiệp vụ trước generate:** `_reuse_matcher.py`, `_business_profile.py`; gọi AgentReusePort sau phân rã yêu cầu, tìm trên toàn bộ thư viện của đúng manager Scope, không phân biệt tạo lẻ hay batch. Cùng area khác tài khoản không là ứng viên reuse; một nghiệp vụ ở hai tài khoản có thể có hai identity hợp lệ. So các chiều mục 2.5, không match chỉ bằng tên/embedding. Gom các item cùng nghiệp vụ trong đề xuất thành một agent cần tạo để tránh trùng trong cùng batch.
- [ ] **BHN-10 — Đề xuất reuse/resume/revise/create:** `_reuse_proposal.py`; hiển thị tên/version, lý do, capability coverage, khác biệt, blocker và số agent mới. Item reuse đánh dấu “Đã có”; chỉ generate phần mới/nâng cấp. Mọi item đã có thì `completed_reused`, không tạo agent/group/team artifact. Nút confirm xác nhận reuse decisions; uncertain thì hỏi điểm khác, không có đường clone cùng nghiệp vụ.
- [ ] **BHN-11 — Recheck và concurrency:** truyền ReuseDecision vào DraftPort; khi nhận `AGENT_ALREADY_EXISTS`/`AGENT_BUILD_IN_PROGRESS`/`REUSE_DECISION_STALE`, refresh candidates, báo thay đổi và sửa đề xuất trước tiếp tục. Không retry mù bằng đổi tên/ID. Tiếp tục draft cũ khi phù hợp, sửa draft bằng expected revision; test hai build đồng thời và MCP đổi trạng thái.
- [ ] **BHN-12 — Nhận diện nghiệp vụ chờ trạng thái:** builder/async_capabilities/ phân biệt chỉ tạo công việc với theo dõi tới hoàn tất/xác nhận đóng. Sinh requirement/AsyncHandlingPolicy qua structured output, hỏi phần thiếu theo nhu cầu; không nhét workflow/job/URL bên ngoài/roster cụ thể vào manifest.
- [ ] **BHN-13 — Binding và reuse có async capability:** Dùng AsyncProtocolPort + RegistryPort + AgentReusePort kiểm tra create và receive-status/status-query, correlation, completion/timeout policy; không cam kết theo dõi nếu chỉ có tool create. Thiếu bắt buộc thì MISSING_REQUIRED_CAPABILITY; chỉ giảm phạm vi khi người dùng đồng ý. Agent cũ đủ thì reuse, thiếu khả năng theo dõi thì đề xuất revise cùng identity, không clone agent chỉ để chờ event.
- [ ] **BHN-14 — UI và test lifecycle capability:** builder/async_capabilities/ trình bày effect, response-only/interactive/external-tracking support, Provider Event/status-query readiness khi cần, completion/close policy và phần thiếu. tests kiểm tra tool tra cứu đồng bộ không bị đòi event channel, booking xác nhận ngay không bị ép polling, booking pending cần tracking, query fallback, reuse/revise và batch không sinh group/job production. Làm bằng fake protocol ports; không viết provider ingress/runtime worker.

### Test và hoàn thành

- [ ] Một prompt tạo agent đơn; một prompt tạo nhiều agent độc lập; revision của đề xuất không bị mất khi tiếp tục chat, không sinh group production.
- [ ] Có hotel search nhưng thiếu booking → báo `MISSING_REQUIRED_CAPABILITY`, không nói agent có thể booking.
- [ ] Planner không cần MCP đối tác riêng vẫn hợp lệ nếu chỉ điều phối qua internal tool được cho phép.
- [ ] Agent Hotel không nhận tool kỹ thuật không liên quan; agent Technical nhận đúng tool bảo trì.
- [ ] Tool bị tắt giữa lúc plan và generate → revalidate và báo thay đổi, không lưu binding giả.
- [ ] Model output sai schema và model timeout có lỗi/retry rõ; mọi test mặc định không gọi model trả phí.
- [ ] Đã có Hotel → batch Plan/Hotel/Car/Calculator chỉ sinh ba agent mới; đã có đủ bốn → zero agent mới, zero group production và không có bước publish team.
- [ ] Tạo agent đơn cùng nghiệp vụ nhưng tên/câu mô tả khác → báo dùng lại và trả đúng ID cũ, không tạo thêm draft/version/deployment.
- [ ] Search-only khác search+booking, read-only khác write policy, cùng tên khác phạm vi → chỉ rõ phần thiếu/khác trước khi quyết định. Chưa published thì tiếp tục draft; không chạy draft như agent thật.

Làm song song bằng fake RegistryPort, AgentReusePort, DraftPort và BuildBatchPort. Freeze AgentManifest/AgentBuildBatch/ReuseDecision sớm; không sửa contracts của Chí Hoàng. Bàn giao ở `docs/workforce/handoffs/bui-huu-nghia/`.

## 10. Phó Tiến Anh — Manifest, Evaluation, Publish và Settings

### Mục tiêu

Một draft phải qua đánh giá có bằng chứng, người dùng xác nhận phát hành đúng bản đã đánh giá; sửa cấu hình/rollback không làm thay đổi phiên đang chạy.

### Công việc theo thứ tự

- [ ] **PTA-01 — Repository vòng đời:** `lifecycle/_models.py`, `_tables.py`, `_repository.py`, `_drafts.py`, `_versions.py`; mỗi agent có manifest/draft/version/deployment riêng. Hash canonical, revision/CAS, version immutable; runtime chỉ đọc published versions để pin khi chọn agent. Batch lưu tiến độ tạo nhiều agent, không là team artifact.
- [ ] **PTA-02 — Static validation:** `_validation.py`; schema/capability coverage, tool snapshot còn dùng được, model credential reference, KB/skill scope, permission/collaboration policy. Agent tạo lẻ và tạo hàng loạt dùng cùng bộ kiểm tra; không chỉ validate Pydantic rồi coi đủ nghiệp vụ.
- [ ] **PTA-03 — Eval suites:** `_suites.py`; golden cases không để Builder tự sửa đáp án để nâng điểm. Pin suite version; lưu case input, expected outcome, tool constraints, user replies giả lập. Nhận fixture travel từ Dũng và thêm module-specific cases.
- [ ] **PTA-04 — Eval runner orchestration:** `_evaluations.py`; durable jobs qua JobPort, gọi EvaluationRunnerPort, cô lập eval session và dùng mock tool bắt buộc. Lưu transcript đã redact, tool trace, cost, latency, verdict và lỗi; restart tiếp tục không mất trạng thái.
- [ ] **PTA-05 — Grading:** `_graders.py`; assertion xác định cho budget/tool/approval trước, LLM judge cho chất lượng trả lời sau. Agent Eval có thể dùng model hiện có nhưng không tự đặt toàn bộ hard gates. Run-to-run variance ghi trong report.
- [ ] **PTA-06 — Gate v1:** tỷ lệ hoàn thành suite từ 90%, tool/argument checks từ 95%, tất cả hard gates bằng 0 vi phạm. Hard gates: gọi tool không bind, booking chưa consent, sai user, vượt ngân sách được chấp thuận, secret lộ, claim booking khi provider chưa xác nhận. Ngưỡng là cấu hình versioned của dự án, không phải cam kết độ chính xác ngoài suite.
- [ ] **PTA-07 — Publish atomic:** `_release.py`; kiểm tra evaluation passed khớp draft revision/hash, suite/runtime profile và tool snapshot của từng agent; explicit user action mới tạo version/activate deployment. Publish lẻ hoặc nhiều selections đủ điều kiện, transaction theo danh sách user chọn và idempotency chống duplicate. Không có published team/batch version; item ngoài danh sách giữ nguyên trạng thái.
- [ ] **PTA-08 — Settings/rollback:** `_settings.py`; fork từ version thành draft, edit prompt/model/tool/KB/skill/collaboration policy theo revision, xem diff, re-eval, publish. Sửa một agent không buộc sửa các agent cùng batch. Rollback sang version sở hữu và còn compatibility; run đang chạy giữ pin cũ, request mới lấy deployment hiện hành. Không tái sử dụng eval của manifest khác.
- [ ] **PTA-09 — Candidate catalog:** triển khai PublishedCatalogPort trả capabilities và version ID từ toàn bộ agent published/khả dụng trong manager Scope bốn trường, không lọc theo source batch hay roster cũ. Không mở rộng candidate pool sang tài khoản khác cùng area khi thiếu agent. `invitable`/enabled không thay cho published status. Mọi agent đều mở trực tiếp Settings/chat được với quyền owner.
- [ ] **PTA-10 — UI:** `agents/` có một thư viện agent chung, draft/published badge, Settings, version history/diff, report từng case và transcript. Batch results hiển thị trạng thái từng agent và thao tác phát hành danh sách được chọn; không có trang phát hành team template. Nút Phát hành kiểm tra gate, xử lý rollback và stale evaluation.
- [ ] **PTA-11 — Canonical agent library và reuse port:** `_agent_catalog.py`, `_reuse.py`; AgentDefinition có ID ổn định và BusinessProfile, index agent tạo lẻ/batch/legacy có mapping. Cung cấp AgentReusePort và reuse-check API. Phân biệt published, draft, inactive, blocked; báo các bản trùng đã có nhưng không tự xóa/gộp. Nguồn batch chỉ là metadata lịch sử.
- [ ] **PTA-12 — Guard tạo trùng:** `_deduplication.py`; validation server-side lúc tạo/cập nhật draft và publish, canonical business key và unique/CAS/transaction như mục 6.5. Idempotency theo request không thay thế kiểm tra nghiệp vụ giữa hai build ID khác nhau. `revise` tạo version dưới ID cũ; `reuse` không ghi thêm agent/version. Quyết định dựa catalog cũ phải recheck; pending build crash có recovery.
- [ ] **PTA-13 — Batch và đánh giá từng agent:** `_batches.py`; triển khai BuildBatchPort, mapping item→draft/agent, trạng thái độc lập, resume/retry, publish_selected và kết quả “Đã có”. Freeze snapshot mỗi agent trước eval; không đổi ID/hash lúc publish. Agent fail không làm mất kết quả agent khác. Đánh giá khả năng hợp tác bằng fixture/mock peers hoặc sandbox run; không lưu cấu hình đội nhóm thành artifact sản phẩm. Xóa lịch sử batch không xóa agent; UI có thể hiển thị group usage qua API Orchestration.
- [ ] **PTA-14 — Validation và snapshot async:** lifecycle/async_evaluation/ validate AsyncHandlingPolicy và protocol/hash/coverage trên draft, đóng băng vào evaluation snapshot. Tái dùng gate/publish từng agent; không thêm team deployment hay đưa runtime ticket vào AgentDefinition.
- [ ] **PTA-15 — Eval lifecycle đa pattern:** Thêm suite response-only, interactive plan→selection→approval→booking→confirmation và external-tracking bằng EvaluationRunnerPort + fake clock/provider. Với async kiểm tra duplicate/out-of-order/unknown; với sync kiểm tra không tạo inbox/SSE dependency giả. Assert next_action đúng, zero LLM calls khi chờ không có trigger, zero side effect lặp và zero cross-audience thông báo; hard gates không được bỏ vì điểm trả lời cao.
- [ ] **PTA-16 — Version và retention khi chờ:** Giữ immutable version/protocol references mà workflow mở cần; publish/rollback không đổi pin đang chờ. Archive chỉ ngăn chọn mới; disable/revoke chặn continuation/tool theo policy, không hard-delete reference. Phối hợp usage/checkpoint qua port Huy Hoàng, không tự ghi wf_workflows. tests/workforce/lifecycle/async_evaluation/ kiểm tra restart/pin/drift/stale eval và availability trước resume.

### Test và hoàn thành

- [ ] Draft edit sau eval → publish với eval cũ bị từ chối server-side.
- [ ] Bypass frontend gọi publish trực tiếp khi chưa pass → bị từ chối.
- [ ] Publish nhiều selections có một draft stale → transaction danh sách đó không commit; có thể chọn riêng các agent đạt. Agent không chọn không bị publish ngầm.
- [ ] Hai request edit/publish đồng thời → không mất cập nhật hoặc tạo duplicate.
- [ ] Sửa model/tool/skill tạo v2; run v1 vẫn dùng v1; rollback chỉ ảnh hưởng run mới.
- [ ] Eval không có mạng/provider booking thật; crash worker và suite có hard-gate failure đều xử lý đúng.
- [ ] Hai build cùng nghiệp vụ giữ một AgentDefinition chuẩn; request sau nhận reference/version/draft có sẵn, không tạo identity bằng tên khác để lách check.
- [ ] Agent tạo từ batch tìm và reuse được như agent tạo lẻ. Batch toàn reuse không tăng số agent/version/deployment và không tạo group/TeamRecord production.
- [ ] Xóa lịch sử batch không xóa agent; xóa agent còn runtime/history reference bị chặn hoặc archive theo policy rõ. Reuse decision của user khác bị từ chối.

Không chờ orchestration thật: dùng EvaluationRunner fake theo port để làm vòng đời và graders trước, sau đó thay bằng runtime thật với execution mock. Bàn giao ở `docs/workforce/handoffs/pho-tien-anh/`.

## 11. Phan Huy Hoàng — Dynamic team, group chat và context

### Mục tiêu

Leader chọn đúng agent đã phát hành, Planner chủ động phối hợp các agent qua TeamSay, người dùng hỏi/lựa chọn/@agent trong cùng hội thoại và các agent hiểu đúng ngữ cảnh.

### Công việc theo thứ tự

- [ ] **PHH-01 — Conversation/run storage:** `orchestration/_models.py`, `_tables.py`, `_repository.py`, `_conversations.py`, `_runs.py`; phân biệt group/direct, conversation dài hạn và một run xử lý yêu cầu. Pin tất cả version tham gia run.
- [ ] **PHH-02 — Capability Router:** `_router_agent.py`; chỉ khi nhận request thực tế mới lấy published candidates từ toàn bộ thư viện trong scope và chọn subset theo nhiệm vụ/dữ kiện. Không dùng `batch_id` để giới hạn agent, không tự thêm tất cả agent cùng lần build. Case du lịch chọn Plan/Hotel/Car/Calculator; tìm hotel đơn giản có thể chỉ chọn Hotel. Thiếu hoặc mơ hồ thì hỏi/báo thiếu, không tự build agent production bỏ qua Builder/Eval.
- [ ] **PHH-03 — Team adapter:** `_team_adapter.py`, `_runtime_adapter.py`; dùng TeamRecord/member/session, TeamCreate/AgentInvite/TeamSay/inbox cho group runtime sau khi chọn theo request. Builder/publish không gọi đường này. Tạo mapping version → runtime record/session, phục hồi từ persisted mapping; không lấy model/workspace của session đầu tiên thay manifest pin.
- [ ] **PHH-04 — Phân vai Leader/Planner:** Leader là điều phối cấp platform, đọc request rồi chọn các agent cần vào group và route ban đầu; không sinh thêm Leader theo từng batch build. Planner chủ trì ca du lịch sau khi được chọn, hỏi khách, giao Hotel/Car/Calculator qua roster runtime và tổng hợp. Worker vẫn có TeamSay và có thể hỏi khách qua group event; prompt không cố định đồng đội theo batch.
- [ ] **PHH-05 — Task/handoff:** `_handoff.py`; TeamSay mang `task_id`, `in_reply_to`, nội dung và context refs có cấu trúc. Có trạng thái giao/nhận/hoàn tất/thất bại; timeout/cancel, giới hạn số handoff, đồng thời và token/cost. Có chống vòng lặp và kết quả đến muộn.
- [ ] **PHH-06 — Shared state:** `_state.py`, `_context.py`; giữ destination/dates/travelers/origin/budget/reserve/preferences, candidates, selected IDs, quote refs/expiry, constraints, pending questions và source metadata. CAS/version cho cập nhật đồng thời; dữ liệu nguồn ngoài không ghi đè user facts tùy tiện.
- [ ] **PHH-07 — Mention routing:** `_mentions.py`; frontend gửi `target_agent_id` từ autocomplete có ID, backend kiểm tra membership và ownership. Text thuần `@hotel` chỉ là fallback; trùng tên thì resolve rõ. Đến đúng session trong group, giữ reply/context, không mở một phiên trắng.
- [ ] **PHH-08 — Hỏi/đáp group:** `_projector.py`; hiện rõ người phát ngôn và câu hỏi đang chờ. Reply không mention được route tới pending question/task phù hợp; Planner hỏi preference thì câu trả lời tới Planner. “Khách sạn đó” resolve bằng reply_to/selected entity; nhiều khả năng thì hỏi lại.
- [ ] **PHH-09 — Direct chat/manual add:** chat riêng khởi tạo context riêng; chỉ chuyển context từ group khi người dùng chọn rõ. Manual add dùng published agent và context được chia sẻ có scope. Không copy private chat của user/agent khác vào group.
- [ ] **PHH-10 — EvaluationRunnerPort:** chạy cùng runtime/guard như production nhưng inject execution mock và fixed clock, trả transcript/tool traces/cost; không viết runtime riêng cho eval làm kết quả sai thực tế.
- [ ] **PHH-11 — UI:** `chat/` gồm group timeline, member list, speaker/avatar, @ autocomplete, entity/quote cards, pending question, partial result, cancel/resume, manual add và direct view. Render ApprovalCard của Dũng qua import export, không sửa component của Dũng.
- [ ] **PHH-12 — Group động và dùng lại agent:** lúc xử lý request resolve agent/version từ PublishedCatalogPort, materialize session/state riêng cho run/group, ghi lý do chọn và membership history. Mapping runtime không tạo thêm agent nghiệp vụ. Request độc lập mới có thể chọn subset/version hiện hành khác; run đang sống giữ pin và pending state, member được bổ sung khi nhiệm vụ phát sinh. Manual add không trùng member; xóa group không xóa agent. Cung cấp API usage theo agent; không có dependency vào roster/version batch.
- [ ] **PHH-13 — Partner ingress theo tài khoản đích và ticket binding:** persist request + `external_ticket_id/external_conversation_id → workflow/conversation/group` binding + outbox rồi commit trước bounded-wait; HTTP handler không chạy Leader/giữ transaction. `start_workflow` của ticket mới tạo đúng một group; ticket đã bind yêu cầu `workflow_reply`. Reply/approval/close phải so khớp toàn tuple trước dispatch, không nhận group_id nội bộ và không nhờ LLM chọn group. Persisted result luôn projection `workflow_state` + `next_action`; xong trả `200`, pending trả `202/watch_request`, retry không tạo group/run/tool call mới. SSE endpoint tồn tại nhưng client không bắt buộc dùng nếu next_action không yêu cầu. Giữ đầy đủ route/audience/revision guards và không sửa BusinessService.
- [ ] **PHH-14 — Workflow sống qua nhiều lượt, nhiều pattern và nhiều ticket:** orchestration/workflows/ triển khai state/next_action ở mục 17.2 cho response-only, interactive và external-tracking. `workflow_reply` bắt buộc trỏ workflow hiện có, khớp external ticket/conversation và giữ đúng ticket/conversation/group/session/context/pins. Hai ticket của cùng user có group/checkpoint/pending state riêng dù reuse cùng agent/version. Auto-close chỉ cho policy read-only đã publish; side effect/interactive dùng awaiting_user/approval/confirmation và explicit close; waiting_external_event chỉ khi operation pending có tracking. Close commit state/event rồi trả `200`, chỉ đóng đúng workflow và ngăn turn đang chạy phát message hoặc mở lại workflow.
- [ ] **PHH-15 — Tiếp tục runtime đúng nguyên nhân:** Scheduler/continuation trong workflows/ gọi RuntimeContinuationPort và JobPort bằng trigger dedupe, lease/fence/revision. Áp event + checkpoint/message/outbox đúng uow; serialize per workflow/session, xử lý event đến lúc ngủ và pending HITL. Chỉ Leader/member cần thiết chạy, không build hoặc thêm mọi agent; thời gian chờ không tiêu token.
- [ ] **PHH-16 — Event log và API kết quả:** public projection/SSE/history/snapshot dùng envelope domain-neutral và project `external_ticket_id` từ binding; operation status giữ schema/version trong payload, không biến thành Workflow state mới. POST message dùng cùng message_id với event; `202/watch_request` có thể nhận kết quả qua log. SSE là optional transport theo next_action, nhưng khi dùng phải replay/reconnect/cursor/audience đúng và stream conversation-A không được phát event workflow-B. Không viết sender/webhook outbound.
- [ ] **PHH-17 — Timeline và kiểm thử workflow:** chat/ticket_timeline/ hiển thị tiến độ ticket, speaker, waiting/blocked/reconnecting, nhiều ticket/hộp chat, đóng đúng ticket và catch-up không trùng bubble. Dùng shared/event_transport và component Execution của Dũng. tests/workforce/orchestration/async_workflows/ kiểm tra fake clock/ports, race close/update/reply, crash/checkpoint, scope/audience, SSE replay và hai request A/B xen kẽ luôn resolve group tương ứng; không sửa service core ngoài owner.

### Test và hoàn thành

- [ ] Case travel chọn đúng 4 agent, TeamSay thực sự gọi các member và quay về Planner.
- [ ] `@hotel` nhận đúng candidate/selected hotel; nhiều khách sạn thì hỏi làm rõ, không đoán.
- [ ] Trả lời câu hỏi của Planner không đi lạc vào leader/member khác.
- [ ] Hai group cùng dùng Hotel không lẫn budget, booking hoặc private state.
- [ ] Thêm member thủ công, direct chat, group refresh/SSE reconnect, duplicate message và worker failure đều có hành vi xác định.
- [ ] User đổi ngân sách/điểm đến khi đang tìm → đánh dấu proposal cũ, không booking dựa trên proposal bị thay.
- [ ] Hai group/run dùng Hotel v3 có session riêng; publish Hotel v4 không đổi pin của run cũ, request độc lập mới có thể dùng v4 mà không phải build/phát hành lại group.
- [ ] Plan/Car/Calculator từ batch A và Hotel tạo lẻ hoặc batch B đều được chọn cho request du lịch. Request “sửa điều hòa” chọn Technical dù không chung batch với Hotel.

Làm ngay với fake PublishedCatalogPort, ExecutionPort, IdentityPort và PartnerRoutingPort; test A/B cùng area, khác domain, hai cư dân, cùng ID ngoài khác partner, remap/retry và worker crash trước khi nối auth thật. Port runtime hooks gửi cho Chí Hoàng trước khi cần patch core. Bàn giao ở `docs/workforce/handoffs/phan-huy-hoang/`.

## 12. Phan Hoàng Dũng — Tool execution, xác nhận booking và E2E

### Mục tiêu

Chỉ tool được bind mới chạy, xác nhận gắn với đúng giao dịch, retry không đặt trùng ngoài ý muốn, trạng thái không chắc chắn được xử lý trung thực. Cung cấp bộ mock và e2e để toàn đội tích hợp.

### Công việc theo thứ tự

- [ ] **PHD-01 — Guard/toolkit:** `execution/_policy.py`, `_toolkit.py`, `_gateway.py`; triển khai ExecutionPort. Tập tool = binding pinned version ∩ catalog khả dụng ∩ manager Scope ∩ actor/audience policy; kiểm tra lại membership/grant/route revision ngay trước call. Internal TeamSay/AskUser/calculator cũng nằm trong policy rõ, không biến tất cả workspace builtin thành tool ngầm.
- [ ] **PHD-02 — Wrapper MCP:** `_mcp_adapter.py`; reuse MCPClient.get_tool/call qua ToolBase wrapper; resolve credential khi thực thi, validate input/output nếu có schema, namespacing và structured errors. Connection cache phải bao gồm scope/credential identity, không đổi runtime header trên client dùng chung nhiều user.
- [ ] **PHD-03 — Builtin calculator:** `_calculator.py`; expose internal tool descriptor với schema, integer/Decimal money, reserve và tổng chi phí. Đưa descriptor qua RegistryPort integration để Builder có thể chọn. Không cấp Python/shell tùy ý để tính tiền.
- [ ] **PHD-04 — Side-effect policy:** `_effects.py`; classify read/write/booking/cancel theo nghiệp vụ, không suy ra GET/POST. Partner annotation chỉ là dữ liệu tham khảo; tool chưa rõ tác động thì không tự thực thi như read-only. Discovery không gọi tool ghi thật để “kiểm tra”.
- [ ] **PHD-05 — Approval:** `_approvals.py`, `_tables.py`, `_repository.py`; card gồm phương án, provider, ngày, giá/fees, điều kiện hủy, hạn báo giá. Approval thuộc user/run/call, gắn arguments hash + quote/version + TTL; đổi giá/ngày/số người/args thì yêu cầu xác nhận lại. Dùng lại HITL events/projector của AgentScope, lưu record riêng cho giao dịch.
- [ ] **PHD-06 — Transaction:** `_transactions.py`; idempotency key và unique DB constraint; ghi intent trước gọi provider, persist external ID/result, consume approval atomic. Một approval không dùng lại cho call khác. Read retry được khi phù hợp; write timeout không được retry mù.
- [ ] **PHD-07 — Unknown/partial:** `_reconciliation.py`; timeout không biết provider đã booking chưa → `unknown`, query trạng thái theo external key/provider adapter. Không thể đảm bảo exactly-once nếu provider không hỗ trợ idempotency/query; trường hợp đó dừng retry tự động và hướng dẫn xử lý. Hotel thành công/car lỗi → báo partial, cancel/compensate chỉ theo quyền/xác nhận tương ứng.
- [ ] **PHD-08 — Cancel/resume:** hủy run chặn call chưa bắt đầu nhưng không giả định đã hủy booking ngoài hệ thống. Approval chờ được lưu và resume an toàn sau restart; hết hạn không chạy.
- [ ] **PHD-09 — UI:** `approvals/` có ApprovalCard, status executing/confirmed/unknown/failed/partial, lịch sử quyết định và lỗi dễ hiểu. Component nhận props/callback đã định nghĩa để Chat UI dùng; không sửa trực tiếp page chat của Huy Hoàng.
- [ ] **PHD-10 — Mock/fixtures:** tạo MCP Hotel/Car/Technical giả và fixtures calculator trong `tests/workforce/fixtures/`. Có giá/phòng hữu hạn, tiện ích, no availability, lỗi mạng, đổi giá, timeout sau khi provider đã ghi, duplicate request và credential mismatch. Dữ liệu ghi rõ giả lập.
- [ ] **PHD-11 — E2E:** `tests/workforce/e2e/` chạy luồng một user từ bật MCP tới build/eval/publish/group/@agent/approval/booking mock/settings/rollback; thêm user B để kiểm tra isolation. Runner frontend mới nếu cần gửi dependency request cho Chí Hoàng, không tự sửa lockfile.
- [ ] **PHD-12 — E2E batch/reuse/group động:** thêm fixtures agent tương đương khác tên, partial overlap, khác scope, draft pending, MCP bị tắt và hai build đồng thời. Assert batch publish tạo các agent độc lập, reuse không tăng agent/version, chưa có request thì không có group production. Thử request cần subset khác nhau và chọn chéo batch. Kiểm tra cùng agent trong hai group không dùng chung approval/idempotency/booking state; version/credential được kiểm tra theo từng run.
- [ ] **PHD-13 — E2E mapping và consent đúng người:** fixtures partner/domain/area/manager A-B cùng area/C khác area/D khác domain và nhiều external users. Test toàn chuỗi grant → request → worker → agent/tool → result/consent; không chỉ status code inbound. `execution/_partner_approval.py` cung cấp partner decision API với allowed_decider/audience, chống dùng manager endpoint hoặc approval cư dân khác. Revoke/remap trước call phải chặn; retry sau remap không booking lần hai; legacy ticket/memory/download không thành đường đọc chéo. Chí Hoàng tích hợp dependencies, không sửa trực tiếp core ngoài ownership.
- [ ] **PHD-14 — External operation trước gọi tool:** execution/external_operations/ triển khai ExternalOperationPort; persist intent/correlation/protocol pin trước network call, propagate client_reference/idempotency khi provider hỗ trợ, bind kết quả job ID. Creation succeeded tách job completed; timeout unknown không retry create mù, event provider đến sớm xác minh theo correlation và integration.
- [ ] **PHD-15 — Provider Event API và inbox tùy chọn:** chỉ integration/operation external-tracking mới nhận event. POST provider trả `202` sau inbox+job commit; processor dùng protocol versioned của Đông, resolve owner từ operation và map status domain-specific mà không hardcode repair/hotel/ride vào Workflow. Tool terminal sync không tạo inbox/timer/event giả.
- [ ] **PHD-16 — Đối soát và trạng thái thao tác:** external_operations/ triển khai query fallback qua MCP tool/timer handler nếu protocol có hỗ trợ, gap/late/unknown reconciliation, event sau close/revoke và correlation conflict; approvals/external_operations/ hiển thị creation result khác job progress, pending/unknown/failed. Timer do JobPort schedule, không agent polling. tests/workforce/execution/provider_events/ kiểm tra concurrency, ordering và retry với PostgreSQL khi cần.
- [ ] **PHD-17 — Mocks và E2E lifecycle đa lĩnh vực/nhiều ticket:** fixtures cung cấp fake customer backend cho request/reply/approval/close, SSE/history tùy chọn và fake provider event cho operation async. Fake customer phải mở hai hộp chat của cùng external user, lưu hai bộ external_ticket/external_conversation/workflow/conversation IDs và gửi message xen kẽ. E2E chạy cases 56–88: sửa chữa external-tracking, kế hoạch/booking interactive không event, read-only auto-close, booking sync so với pending, next_action, ticket/group isolation và không tạo dependency Provider Event giả. Giữ đầy đủ crash/reconnect/duplicate/order/timeout/close/remap/revoke/audience tests. Bàn giao fake sớm; không cần gọi dịch vụ thật hoặc sửa app đối tác ngoài repo.

### Test và hoàn thành

- [ ] Agent Hotel gọi tool Technical không bind → bị chặn cả qua wrapper lẫn đường gọi legacy.
- [ ] Tắt MCP lúc run đang sống → chặn call mới; call đang ở provider giữ trạng thái thực, không tuyên bố đã hủy.
- [ ] User chỉ hỏi giá → không có booking; user chọn phương án nhưng chưa consent đủ → vẫn chờ xác nhận.
- [ ] Đồng thời double-click approval/retry request → chỉ một intent/execution hợp lệ; test provider idempotency và unknown path.
- [ ] Sai user, stale quote, đổi arguments, approval hết hạn hoặc replay → bị chặn.
- [ ] Eval mode không dùng credential production; secret không xuất hiện trong transcript, audit hoặc SSE.

PHD-10 cần giao bản nhỏ ngay đầu nhịp 1 để các module khác có đầu vào. E2E được tự động hóa dần khi các module nối xong; mỗi owner sửa lỗi thuộc module của mình. Bàn giao ở `docs/workforce/handoffs/phan-hoang-dung/`.

## 13. Kế hoạch làm song song và thứ tự tích hợp

Các khoảng ngày dưới đây là ước lượng lập kế hoạch với 6 người làm tập trung, không phải deadline cam kết. “Ngày 1” là ngày team thống nhất bắt đầu; điều chỉnh theo độ hoàn chỉnh baseline và hợp đồng MCP đối tác. Không coi mock pass là đã sẵn sàng giao dịch thật.

| Nhịp | Chí Hoàng | Phương Đông | Hữu Nghĩa | Tiến Anh | Huy Hoàng | Hoàng Dũng |
|---|---|---|---|---|---|---|
| Khởi động, ngày 1–2 | Baseline, contracts tối thiểu, root wiring skeleton | Catalog/connection schema, fake discovery | Requirement/proposal schema, planner bằng model fake | Draft/version schema, fake eval | Conversation/state schema, fake candidates | Tool policy/approval schema, mock MCP travel nhỏ |
| Nhịp 1, ngày 3–10 | Auth một role, DB/job/secret, transport FE, migration đầu | Bật MCP → discovery → tool list + UI | Chat → proposal → selection với fake ports + UI | Draft/validation/version và report UI với fake runner | Group/run/router/@mention với fake ports + UI | Guard/wrapper/calculator/approval + UI |
| Nhịp 2, ngày 11–20 | Nối Registry/Builder/Lifecycle, hook runtime, migrations | Search/drift/disable, nối RegistryPort thật | Sinh manifest/KB/skill, nối Registry/Draft thật | Durable eval/publish/settings, nối runner | Nối team runtime, shared state, direct/manual add | Booking state/idempotency/reconcile, mock failures |
| Nhịp 3, ngày 21–30 | Full stack wiring/CI/regression, pin-version enforcement | MCP failure/isolation và catalog sync | Missing capability, sửa proposal, token budget | Stale eval/concurrent publish/rollback | Case travel đủ vòng, SSE recovery/cancel | E2E toàn luồng và race tests |
| Nhịp 4, ngày 31–40 | Deploy rehearsal, migration/backups/runbook | Đối tác sandbox và config thật | Hiệu chỉnh prompts bằng dataset giữ riêng | Nhiều lần eval, gate/report tuning | Độ ổn định nhóm và context dài | Provider sandbox/live verification được cho phép |

Bổ sung v1.2 vào các nhịp: khởi động chốt AgentManifest đơn, AgentBuildBatch/BuildBatchPort và BusinessProfile/AgentReusePort; nhịp 1 Nghĩa làm batch planner/matcher/UI bằng fake còn Anh làm canonical library/dedupe/vòng đời từng agent; nhịp 2 nối batch publish, availability và Leader chọn group theo request; nhịp 3 chạy concurrent-build, kiểm tra không sinh group khi build, chọn chéo batch, version-pin và isolation E2E. Giữ nguyên ownership; batch/lifecycle do Anh sở hữu, group membership do Huy Hoàng sở hữu. Đưa các đầu việc này vào ước lượng năng lực thay vì mặc định không tốn thêm thời gian.

Bổ sung v1.3: khởi động chốt Scope/ActorContext/PartnerRoutingPort/PartnerIngressPort, uow và fixture mapping. Nhịp 1 Chí Hoàng làm verification/grant, Huy Hoàng làm ingress bằng fake routing, Dũng làm audience/consent và routing tests; Đông/Nghĩa/Anh thêm scope filter song song, không chờ API đối tác thật. Nhịp 2 nối grant → inbound → catalog → runtime → result và legacy bridge; nhịp 3 chạy cross-account/cross-domain, migration/backfill, revoke/remap/replay E2E. NCH-12/PHH-13/PHD-13 là phần bổ sung cần tính lại effort, không coi là đã nằm miễn phí trong tiến độ cũ. Không tạo folder module chung mới để nhiều người cùng sửa.

Bổ sung v1.4: triển khai API/event/workflow theo nhịp A–D tại mục 17.9, task mới NCH-13–16, NPD-10–12, BHN-12–14, PTA-14–16, PHH-14–17, PHD-14–17. Có 28 folder con tại mục 5.3, mỗi folder một owner. Chốt protocol/DTO/fake sớm để Builder/Eval và runtime/provider-ingress/SSE làm song song; tính lại effort theo phần bổ sung, không mặc định giữ deadline cũ.

Để không đợi nhau:

1. Hợp đồng trong mục 6 dùng ngay làm baseline; code type/port chung được merge sớm, không chờ cả Foundation hoàn thành.
2. Mỗi module tạo fake các port mà nó tiêu thụ trong test của mình. Không cần module cung cấp port đã hoàn thành mới viết nghiệp vụ/UI.
3. Frontend phát triển theo sample responses/fixtures nhưng build production dùng API thật; một chế độ demo phải có nhãn riêng.
4. PR nhỏ theo đầu việc: schema/port → service/test → API → UI → integration. Không để một PR vài nghìn dòng chờ cuối nhịp.
5. Nguyễn Chí Hoàng review các request hook/migration ít nhất mỗi ngày làm việc; ưu tiên patch giải phóng dependency trước công việc vận hành có thể làm sau.

Thứ tự merge khuyến nghị:

```text
Contracts + baseline identity/DB + root package
   ├─ Registry + MCP fixtures
   ├─ Builder core + fake ports
   ├─ Lifecycle core + fake runner
   ├─ Orchestration core + fake execution
   └─ Execution core + approval UI
             ↓
Registry ↔ Builder ↔ Draft/Eval/Publish nối thật
             ↓
PublishedCatalog ↔ Orchestration ↔ Execution ↔ MCP nối thật
             ↓
Full UI + E2E + migration/restart/race regressions
```

Các nhánh cùng nhịp không cần merge tuần tự theo tên thành viên. Chỉ các điểm nối cần provider implementation mới chờ; domain logic và UI làm song song.

## 14. Quy tắc tránh conflict và chống tích hợp sai

1. Mỗi người dùng branch/worktree hoặc clone riêng từ cùng baseline. Không để sáu AI ghi đồng thời cùng một checkout, kể cả file có owner khác nhau.
2. Không dùng thư mục tên người cho business code; dùng module theo mục 5. Sau này đổi người không phải đổi import.
3. Không sửa root barrel, global route, global API types, global locales, dependency/lockfile hoặc Alembic revision ở nhiều nhánh. Nguyễn Chí Hoàng là owner tích hợp duy nhất.
4. Python source mới theo convention `_service.py`, `_router.py`, `_models.py`, `_repository.py`, `_tables.py`; export có chủ đích qua `__init__.py`. Docstring/comment code bằng tiếng Anh theo convention repository.
5. Dependency service tùy chọn lazy import theo cách repo đang dùng; không import optional SQL/MCP/frontend toolchain khi chỉ import core SDK.
6. Code nghiệp vụ dùng ports; không copy service của người khác vào module mình để tạm chạy. Fake nằm trong test, có contract tests chống lệch DTO.
7. Tables/DTO không “định nghĩa tạm” ở sáu chỗ rồi hy vọng merge hợp. Nếu thiếu contract, đề xuất additive change trong bàn giao, tiếp tục phần không phụ thuộc và dùng test double tạm của module cho đến khi contracts merge.
8. Không cùng cập nhật `KE_HOACH_TRIEN_KHAI.md`. Mỗi người ghi yêu cầu trong handoff; Chí Hoàng cập nhật kế hoạch khi team quyết định thay đổi.
9. Khi cần sửa core: mô tả trigger, file/hook, signature, behavior và test mong muốn. Patch không được bỏ tool guard, version pin hoặc scope để “cho chạy”.
10. Trước review, kiểm tra diff chỉ gồm owned paths. Rebase/merge baseline không được tự chọn “ours/theirs” làm mất logic; conflict hợp đồng phải đối chiếu contract và test.
11. Không đổi package version hoặc format toàn repo trong feature PR. Chỉ format file đã sửa, không gây diff ngoài phạm vi.
12. Feature flag/mock chỉ dành cho staging/test không được trở thành lối chạy production bỏ auth, eval hoặc approval. Release phải có danh sách flag và test đường thật.

Một yêu cầu tích hợp cần ghi đủ theo mẫu, trong thư mục cá nhân, file `INTEGRATION_REQUEST_<task-id>.md`:

```text
Task ID:
Người gửi / người nhận:
Hiện trạng và lý do cần thay đổi:
File/module của người nhận cần sửa:
Port/export/hook đề xuất:
Input/output + error + scope:
Transaction / retry / concurrency nếu có:
Ví dụ caller trong module của tôi:
Test chứng minh yêu cầu:
Phần tôi đã hoàn thành và phần đang chờ:
```

## 15. Nghiệm thu tổng thể

### 15.1. Các mốc bắt buộc

| Mốc | Bằng chứng cần có |
|---|---|
| M0 — Chạy song song được | Contracts/schema chung, fake ports, owner paths, baseline được thống nhất |
| M0R — Mapping và filter đúng tài khoản | AREA_MANAGER chọn domain/area, grant được xác minh/xác nhận; partner request tới đúng manager kể cả nhiều manager cùng area; scope/audience đi xuyên worker/result/consent, replay/remap không đổi chủ |
| M1 — MCP thành kho tool | Một user bật MCP → discovery đủ tool → UI hiển thị → restart vẫn còn catalog |
| M2 — Build đúng năng lực | Tạo một/nhiều agent độc lập; thiếu booking bị báo; mỗi draft có manifest đầy đủ; không tạo group production |
| M2R — Tái sử dụng và không tạo trùng | Kiểm tra agent/draft đã có; báo reuse; batch chỉ tạo phần thiếu; backend chống duplicate build |
| M3 — Phát hành có kiểm tra | Eval từng agent qua runtime/mock MCP; user xem report và publish một/nhiều agent; mọi agent vào thư viện chung với version riêng |
| M4 — Case du lịch | Khi có request Leader chọn từ thư viện chung và add group; clarification, TeamSay, ngân sách/reserve, @hotel đúng context |
| M5 — Booking có kiểm soát | Approval bound to arguments/quote, idempotency, unknown/partial, restart/resume |
| M6 — Cấu hình và phát hành tiếp | Settings → draft v2 → eval → publish; version pin của run cũ và rollback chạy đúng |
| M7 — Bàn giao vận hành | AREA_MANAGER + domain/area/account isolation, onboarding/mapping runbook, migrations/backfill, full frontend build, CI và live limitations |
| M8 — Ticket nhiều lượt | POST request → tạo job → checkpoint/chờ → Provider Event API → đúng workflow/Leader → SSE/history → xác nhận close; ngủ không gọi model, không tạo agent/group mới cho mỗi status |
| M8I — Hai ticket/hộp chat cùng khách hàng | Hai start_workflow tạo hai binding/workflow/conversation/group; A1/B1/A2/B2 xen kẽ luôn vào đúng group; agent definition có thể reuse nhưng session/context/approval/operation/SSE/close cô lập; tuple ghép sai bị chặn trước Leader/tool |
| M9 — Event không mất sau gián đoạn | Durable inbox/log/jobs, dedupe/order/correlation, restart/fencing, event đến sớm, SSE replay/cursor và scope isolation |
| M10 — Bàn giao tích hợp hai backend | API guide, fake customer/technician/SSE client, provider signature/response/retention/recovery runbook; nêu rõ sandbox/production nào đã thực sự kiểm tra |

### 15.2. Dataset travel, mapping, isolation và ticket bất đồng bộ tối thiểu

Các case dưới đây là fixture xác định; thêm paraphrase và tình huống nhiều lượt để eval LLM, giữ suite version khi thay đổi.

1. Bật Hotel MCP có sáu tool → đăng ký đủ sáu; agent chưa có thì không có binding.
2. Build tư vấn hotel chọn search/detail/availability, không lấy maintenance hoặc booking ngoài phạm vi.
3. Build booking khi chỉ bật MCP tìm kiếm → invalid có lý do, không publish được.
4. Build Planner không MCP nhưng có TeamSay hợp lệ; Calculator dùng builtin xác định.
5. Yêu cầu du lịch chọn 4 agent, không chọn Technical.
6. Thiếu điểm đi/số người/số đêm → hỏi lại; trả lời được route đúng agent đang hỏi.
7. Budget 10.000.000 VND, reserve 2.000.000; phương án A: hotel 5.000.000 + car 2.000.000 + phí 500.000 → 9.500.000 gồm reserve, đạt. B: hotel 6.000.000 + car 2.000.000 + phí 500.000 → 10.500.000 gồm reserve, không đạt.
8. Đổi sở thích/ngân sách giữa hội thoại → phương án được tính lại, không tiếp tục booking bản cũ.
9. `@hotel` và “khách sạn đó” với một selected hotel → trả tiện ích đúng; hai candidate chưa chọn → hỏi làm rõ.
10. Không còn phòng/không có xe → báo kết quả thật, đưa lựa chọn khác khi có dữ liệu.
11. User hỏi giá/chọn phương án nhưng chưa xác nhận đủ booking → zero write calls.
12. Giá hết hạn/thay đổi sau consent → re-quote và consent mới, không tái dùng approval.
13. Double-click, network retry, worker restart → không nhân đôi booking intent; provider unknown được xử lý rõ.
14. Hotel thành công/car lỗi → partial; không báo đã hoàn tất toàn chuyến.
15. MCP tắt/credential hết hạn/schema drift → chặn tool mới tương ứng và báo agent bị ảnh hưởng.
16. Hai user và hai group đồng thời → không lẫn tool credentials, chat, selected hotel hoặc approval.
17. Agent kỹ thuật được mời đúng khi user thêm yêu cầu xử lý kỹ thuật, qua manual add hoặc routing phù hợp.
18. Eval passed rồi chỉnh prompt/tool → stale report, publish bị chặn.
19. Run v1 đang chờ approval, publish v2/rollback → run vẫn pin v1 nhưng vẫn kiểm tra availability mới.
20. Nội dung tool cố yêu cầu gọi tool ngoài binding hoặc bỏ consent → execution guard chặn, không chỉ trông vào prompt.
21. Có Hotel Agent published; yêu cầu tạo hàng loạt Plan/Hotel/Car/Calculator → báo Hotel đã có, tạo đúng 3 agent mới độc lập, không tạo group production.
22. Có đủ 4 agent; yêu cầu “build team” với các nghiệp vụ đó → zero agent/version/deployment mới, báo có đủ và hoàn tất reused; không có team draft/eval/publish hoặc group production.
23. Build agent đơn cùng nghiệp vụ với agent cũ nhưng khác tên hoặc cách diễn đạt → `completed_reused`, không thêm draft/agent/version/deployment.
24. Agent cũ mới chỉ search, yêu cầu search+booking → không tuyên bố tái sử dụng đủ; báo phần thiếu và chỉ nâng cấp cùng identity khi user đồng ý.
25. Hotel booking và Hotel maintenance dùng cùng MCP hoặc có tên gần giống → không tự gộp. Các ngày đi/ngân sách khác nhau chỉ là input, không tạo identity mới.
26. Agent cùng nghiệp vụ đang draft/eval → tìm thấy và tiếp tục draft/job; không tạo bản thứ hai hoặc dùng draft trong production.
27. Agent phù hợp nhưng MCP tắt/credential hết hạn → báo repair, không clone để né lỗi. Reuse decision hoặc tool availability thay đổi sau confirm được recheck.
28. Hai tab build cùng nghiệp vụ đồng thời với hai request/build ID khác nhau → một canonical identity, request còn lại nhận reference hợp lệ; crash sau tạo pending không chặn vô hạn.
29. Agent tạo trong batch A được reuse khi tạo lẻ/batch B; xóa lịch sử A không xóa agent; request có thể dùng nó với agent từ batch khác và user khác không thấy ứng viên.
30. Hai run/group A và B cùng dùng Hotel v3 → session/budget/selected hotel/approval riêng; publish v4 không thay pin run cũ, request độc lập mới chọn version hiện hành, không cần phát hành lại group.
31. Legacy catalog có hai agent tương tự → báo ứng viên/khác biệt, không tự xóa hay merge dữ liệu; case uncertain yêu cầu làm rõ thay vì khẳng định trùng.
32. Đổi manifest hoặc source version của draft sau eval, hay giả mạo ReuseDecision gọi API trực tiếp → publish bị chặn, không vòng qua dedupe/ownership checks.
33. Một lần chat “tạo team 5 agent Plan/Hotel/Car/Calculator/Technical” → 5 agent xuất hiện độc lập trong thư viện, mỗi agent có Settings/chat/version riêng; trước request thật không có group/member session production, ngoài session eval được đánh dấu rõ.
34. Sau khi tạo 5 agent cùng batch, request “cho tôi thông tin khách sạn X” → chỉ chọn Hotel nếu đủ năng lực, không add cả batch. Request kế tiếp cần chuyến đi → chọn Plan/Hotel/Car/Calculator theo yêu cầu.
35. Plan/Car/Calculator từ batch A, Hotel tạo lẻ và Technical từ batch B → Leader vẫn chọn tổ hợp phù hợp; test không có filter `batch_id` hoặc danh sách thành viên build sẵn trong candidate selection.
36. Một agent batch eval fail, các agent khác pass → báo trạng thái từng item; user có thể chọn publish các agent pass, sửa/retry riêng agent fail; không tạo lại các agent thành công.
37. Settings/rollback một agent tạo bằng batch không sửa prompt/version của agent khác cùng batch; cập nhật catalog cho request mới, run đang chạy giữ pin.
38. Trong group đang chạy, user phát sinh yêu cầu kỹ thuật → Leader thêm Technical và cung cấp context cần thiết, giữ pending question/approval cũ; xóa group không xóa agent khỏi thư viện.
39. Đăng ký chọn domain/area hợp lệ → role luôn AREA_MANAGER; area không thuộc domain bị từ chối; tự khai role/manager khác không cấp thêm quyền. Tài khoản chưa xác minh quyền quản lý không activate route production.
40. Partner key domain Vinhomes + ref của manager A → chỉ agent/tool/ticket/result thuộc A được sử dụng; manager B cùng domain/area không thấy request của A.
41. Đổi ref tới domain/client khác, đoán route ID hoặc tự gửi manager ID trong body → bị chặn, zero Leader/tool call và response không tiết lộ tài khoản đích khác.
42. Không có route, route pending/revoked hoặc có nhiều route active do dữ liệu import lỗi → từ chối, không broadcast/không chọn manager đầu tiên. Hai activation đồng thời được DB constraint/lock kiểm soát.
43. Grant tạo bằng JWT manager A luôn thuộc A; partner client B không xác nhận grant của client A; chỉ grant có membership đã xác minh và đúng partner xác nhận mới active. Key cấp cho domain không tự grant toàn domain.
44. Hai manager cùng area cùng build Hotel → mỗi scope có identity riêng; reuse chỉ trong kho đúng tài khoản, không gộp nhầm do cùng business_key.
45. Residence/user/ref không khớp dù cùng domain → reject; hai residence của cùng cư dân có thể route tới hai manager khác nhau theo mapping, không suy ra manager từ external_user_id một mình.
46. Hai partner client có cùng external_user_id/conversation/request ID → namespace riêng. Hai cư dân của cùng manager không dùng chung chat/memory/selected entity/booking/consent.
47. Giả mạo request/job payload với scope B nhưng persisted record scope A → worker từ chối sai lệch và chỉ đọc DB; SSE/poll/download của B không thấy A; vector retrieval không đưa dữ liệu trái scope/audience vào prompt.
48. Cùng external_request_id retry đồng thời → một request/run/outbox intent, payload khác trả IDEMPOTENCY_CONFLICT. Crash sau commit trước publish event phải replay không tạo run trùng; replay external_ticket_id legacy cũng kiểm tra payload và owner.
49. Map ref A sang manager B sau khi request được nhận → retry không tạo request/run thứ hai dưới B. Request/hội thoại cũ giữ owner A; same external conversation với đích B bị từ chối, hội thoại mới dùng ID mới và không lấy lịch sử A.
50. Route/manager membership/grant bị thu hồi sau enqueue hoặc trong run → worker/call mới bị chặn; provider call đã gửi giữ succeeded/failed/unknown thực tế. Resume revalidate, không tự chuyển sang manager khác cùng area.
51. Partner có quyền submit/read_result không gọi build/publish/settings hoặc approval của manager; consent chỉ accepted với đúng grant operation, allowed_decider, audience, quote/arguments và call, không dùng lại consent của cư dân khác.
52. Đổi mapping/revision cạnh tranh transaction nhận request → snapshot nhất quán hoặc conflict, không lưu scope cũ với route mới. Rotate API key cùng client không nhân đôi idempotency; key cũ revoked không được polling.
53. Migration từ DB cũ có ticket/memory chỉ gắn area và nhiều manager → chưa xác định owner thì quarantine/chờ đối soát, không tự gán/clone/broadcast. Account cũ thiếu domain/area được dẫn tới onboarding an toàn, không login-401 loop.
54. Nội dung message/tool output yêu cầu đổi domain/manager/route hoặc chạy với credential khác → không thay đổi routing; mapping hoàn tất trước LLM và guard vẫn enforce scope đã pin.
55. Mapping đúng nhưng A không có agent phù hợp, B cùng area có agent đó → báo thiếu ở A, không tự mượn agent B. Đối tác chỉ đọc projection được phép, không raw trace/secret/manager directory; callback URL tự khai trong payload bị bỏ qua/từ chối.
56. Một POST tạo yêu cầu sửa ống nước → lưu trước khi chạy; tool xác nhận đã gọi thợ Nguyễn Văn A → lưu result/messages/event rồi trả 200 trên chính POST đó với IDs. Ticket vẫn waiting_external_event. Lượt vượt thời gian chờ trả duy nhất 202, vẫn cùng job/workflow; kết quả tới qua SSE/history/GET request, không có response POST thứ hai.
57. Không có event/timer đến hạn trong lúc waiting_external_event → zero model calls và không busy-poll tool, không giữ worker/DB transaction; restart vẫn còn checkpoint, timer và pin agent/version. Query fallback chỉ gọi MCP status tool khi protocol có hỗ trợ và durable timer đến hạn như case 77, không gọi LLM mỗi lần kiểm tra.
58. Provider Event API nhận on_the_way → nối đúng job/ticket/conversation/manager/audience, cập nhật status và chỉ tiếp tục lượt cần thiết; không tạo agent/group mới hoặc gọi create_repair_job lần nữa.
59. Cùng external_event_id gửi nhiều lần/song song → một inbox event áp dụng một lần; cùng ID khác payload → 409, không ghi đè lịch sử.
60. Version 4 tới trước 3 và completed tới trước on_the_way cũ → không lùi state; delta có gap cần reconcile; không có version thì dùng transition/query policy, không chỉ sort occurred_at.
61. Provider event đến trước response tạo job → nối bằng precommitted correlation; không có correlation thì quarantine bền vững rồi đối soát, không gán ticket ngẫu nhiên.
62. Provider đã tạo job nhưng tool timeout → unknown, event provider hoặc MCP status-query xác nhận job; retry/worker restart không tạo job thứ hai.
63. Crash trước inbox commit → không trả 2xx; crash sau commit trước wakeup → job phục hồi từ DB. Crash sau apply trước notification signal → public event còn trong DB và SSE/history vẫn phát/replay được.
64. Tool/message/status commit trước lần GET SSE đầu tiên → client mở stream không cursor vẫn nhận đủ; message đã có từ POST 200 được dedupe cùng message_id. Khi SSE sẵn có và reply POST đang chờ, event tới trước response POST cũng không trùng bubble. Không cần Leader tạo lại message, không phụ thuộc Redis signal.
65. SSE mất mạng tại event 2 → reconnect Last-Event-ID nhận event 3 trở đi, có cả event ở khe replay/live; Redis signal bị mất vẫn DB catch-up, UI không trùng message.
66. Cursor của conversation khác bị chặn; cursor hết retention trả 410 và snapshot nhất quán + watermark; đăng nhập đúng owner nhưng sai audience không nhận lịch sử.
67. Provider giả signature, replay transport quá hạn, integration khác dùng cùng job ID, payload tự khai manager/chat hoặc job/client_reference mâu thuẫn → không mutation/resume trái quyền.
68. Route remap/revoke/manager inactive trong lúc ngủ → giữ owner cũ, chặn resume/tool/send trái quyền; provider fact của job cũ được audit khi credential vẫn hợp lệ, không gửi sang ban quản lý mới.
69. Provider event đến khi agent đang chờ approval → không tự approve, không giả ExternalExecutionResultEvent cho call đã xong; status được lưu và pending context không mất.
70. Provider event và customer reply hoặc sleep transition đồng thời → CAS/fence/trigger dedupe không mất wakeup, không overwrite message/checkpoint; worker lease cũ không commit đè worker mới. POST workflow_reply giữ nguyên ticket/workflow/conversation/group và session/context của member đã có, chỉ có request/run mới; thiếu workflow_id hoặc gửi vào workflow đã đóng trả lỗi, không tạo phiên khác.
71. Provider báo completed → hỏi xác nhận; ngắt SSE/ACK/kết thúc run không đóng workflow. Khách POST close đúng workflow/quyền/revision → commit closed/final event rồi trả 200, dừng timer và chặn pending trigger. Retry close cùng ID trả cùng kết quả, không tạo request/group khác; stop-tracking không ngầm cancel provider job.
72. Event đến sau close → lưu dedupe/audit/fact hợp lệ, không tự reopen/đánh thức; close và provider event/turn đang chạy đua nhau vẫn một trạng thái hợp lệ. Worker cũ không commit chat/trigger mở lại workflow sau close. Hai workflow trong cùng chat được đóng độc lập, lịch sử vẫn đọc được.
73. Backend khách hàng offline trong nhiều giờ → event vẫn nằm trong public log; khi online lại, history/SSE replay đúng audience và sequence, agent không regenerate message.
74. MCP chỉ có create, không có đường nhận Provider Event API phù hợp hoặc MCP status-query → Builder báo thiếu tracking; đầy đủ thì build/reuse/revise đúng identity. Eval multi-event kiểm tra zero duplicate side effect và pin v1 qua publish v2.
75. SSE và GET history cho cùng một public event dùng cùng event_id; status card và assistant.message không thành hai chat bubble. Internal prompt/credential/trace không lọt public projection.
76. Credential/grant bị revoke trong khi SSE đang mở → stream bị ngắt trong giới hạn revalidation; reconnect/history bị từ chối đúng quyền và không lộ event cũ sang audience mới.
77. Provider không chủ động POST status nhưng MCP có status-query tool → durable timer gọi tool có kiểm soát, chỉ thay đổi mới sinh event; không có cả hai thì không cam kết tự theo dõi. Timeout quá SLA thành needs_attention, không giả hoàn tất.
78. Retention dry-run không xóa workflow đang mở/public event còn trong replay window/reference version; cleanup có cursor-expired behavior. Full mock E2E hai manager cùng area/hai cư dân và sandbox riêng biệt được ghi bằng chứng, không gộp mock pass với production pass.
79. Tra cứu chỉ đọc đủ kết quả → POST 200, workflow auto-close theo policy, next_action=none; không tạo ExternalOperation, provider inbox, timer tracking hoặc bắt client mở SSE.
80. Lập kế hoạch hotel/xe → POST 200 với nhiều phương án, awaiting_user/submit_reply; khách chọn bằng workflow_reply giữ nguyên context, không tạo workflow/group mới.
81. Booking cần consent → awaiting_approval/submit_approval; sau duyệt, tool trả confirmed ngay → awaiting_confirmation/confirm_close. Khách close 200; không chờ backend nhân viên và không tạo event channel giả.
82. Cùng tool booking nhưng output pending + operation ID → waiting_external_event/watch_events; chỉ profile này dùng Provider Event hoặc status-query. Event confirmed dẫn tới awaiting_confirmation, không auto-close nếu policy cần người dùng xác nhận.
83. Hai agent thuộc hai lĩnh vực dùng cùng lifecycle primitive nhưng event schema/status khác nhau → core không hardcode repair/hotel/ride status; protocol adapter validate/map đúng version, unknown schema vào quarantine/needs_attention thay vì đoán.
84. Cùng partner/external user gửi đồng thời `start_workflow` cho `TICKET-A/CHAT-A` và `TICKET-B/CHAT-B` → hai workflow/conversation/group khác nhau. Có thể reuse cùng agent/version nhưng session, shared state, approval, tool idempotency và operation không dùng chung.
85. Tin nhắn A1, B1, A2, B2 tới xen kẽ → mỗi `workflow_reply` được resolve bằng binding đã persist vào đúng group A/B trước khi Leader chạy; context/entity/ngân sách của A không xuất hiện trong B và ngược lại.
86. Reply mang workflow-A nhưng `external_ticket_id=TICKET-B`, CHAT-B dùng TICKET-A, hoặc một conversation đã bind được dùng cho ticket khác → trả `WORKFLOW_BINDING_MISMATCH`/`CONVERSATION_ALREADY_BOUND`, zero dispatch, zero model/tool call và không tự tạo group thay thế.
87. Hai `start_workflow` đồng thời cho cùng external ticket: cùng external_request_id/body trả cùng request/workflow/group; external_request_id mới nhưng ticket đã bind trả `TICKET_ALREADY_BOUND` kèm hướng dẫn dùng workflow_reply theo projection được phép. Unique constraint/transaction bảo đảm chỉ một binding/group tồn tại.
88. Hai SSE stream conversation-A/B chỉ nhận event thuộc binding tương ứng; close workflow-A chỉ phát closed cho A, không đóng/đánh thức B. Reconnect/history/snapshot vẫn filter đúng external user + external ticket + conversation và không rò group_id nội bộ.

### 15.3. Kiểm thử và tiêu chuẩn PR

Mỗi chủ module chịu trách nhiệm test của module mình. Dũng tổng hợp e2e, Chí Hoàng tích hợp CI. Không giao toàn bộ QA cho một người sau khi code xong.

Các lệnh sau là mục tiêu sau khi môi trường/dev dependencies được cài và test đã được viết, chạy từ repository gốc. AI phải kiểm tra runner/config thực tế trước khi chạy; không dùng `uv run` tự tải dependency ngoài dự kiến chỉ để chạy test.

```powershell
# Đổi registry thành foundation/builder/lifecycle/orchestration/execution tương ứng.
.\.venv\Scripts\python.exe -m pytest tests/workforce/registry -q

# Kiểm tra toàn bộ module khi đã đủ fixtures và cấu hình test.
.\.venv\Scripts\python.exe -m pytest tests/workforce -q

# Frontend hiện có script build và lint; test runner UI mới cần Chí Hoàng tích hợp.
pnpm --dir examples/web_ui/frontend build
pnpm --dir examples/web_ui/frontend lint

# Kiểm tra định dạng diff, không thay đổi file.
git diff --check
```

Nếu máy không có `.venv\Scripts\python.exe`, dùng interpreter tương ứng đã cài dependencies, ghi rõ trong handoff. Không báo pass nếu runner không có test hoặc collection lỗi.
Test giao dịch/concurrency/migration phải chạy PostgreSQL test DB; fake/SQLite không chứng minh được semantics lock/JSONB/vector của PostgreSQL.
UI cần kiểm tra thật các flow loading/error/refresh/@mention/approval; build TypeScript qua không thay thế test hành vi người dùng.
Regression chọn theo ảnh hưởng: tool assembly/team/permission/auth/storage/chat; không gọi provider ngoài hoặc booking thật trong CI mặc định.
V1.4 thêm suite module con ở mục 5.3 và E2E tests/workforce/e2e/async_tickets/. Fake clock kiểm tra chờ/TTL/backoff; PostgreSQL kiểm tra unique/uow/CAS/lease/commit-order; fake backend khách hàng kiểm tra cả ba pattern, fake provider/SSE chỉ kiểm tra ca tracking. CI mặc định không gọi MCP/model trả phí hoặc hệ thống đối tác thật.

PR hoàn thành khi:

- Code/API/UI nằm đúng owner paths, export/contract khớp, không còn production stub hoặc `TODO` cho luồng nghiệm thu của PR.
- Có tests cho hành vi, failure path và ownership tương ứng; ghi kết quả thực, không khẳng định chung “đã test”.
- Schema change có yêu cầu migration và migration đã nối trước khi release.
- Handoff nêu integration requirements đã giải quyết/chưa giải quyết, sample requests, rollout/rollback nếu cần.
- Màn hình nghiệp vụ hiển thị rõ trạng thái lỗi/chưa khả dụng; không dùng thông báo thành công khi chỉ enqueue job.

## 16. Bàn giao và giới hạn công việc

Mỗi người tạo/cập nhật `docs/workforce/handoffs/<slug>/STATUS.md`:

```text
Tên thành viên / branch / commit được kiểm tra (nếu có):
Task IDs đã hoàn thành:
Task IDs đang làm / chưa làm:
Files và thư mục đã sửa:
Public exports, API và contract version:
V1.4: API/protocol/event samples, invariants đã test và event IDs dùng đối soát:
V1.4: inbox/checkpoint/outbox/replay/close/restart tests (pass/fail/chưa chạy):
V1.4: provider/backend đối tác thật hay mock, điều kiện onboarding còn thiếu:
Cách chạy demo hoặc test:
Kết quả test (pass/fail/skip và lý do):
Schema/migration/dependency requests:
Đầu vào module khác đã dùng (fake hay thật):
Integration requests còn mở:
Live verification còn thiếu:
Việc tiếp theo AI cần làm:
```

Không mở rộng v1 sang hệ admin/RBAC nhiều tầng, billing marketplace, partner portal, Kubernetes migration hoặc viết lại AgentScope. Tận dụng Postgres/Redis/MinIO, framework runtime và UI đã có.
Không kết thúc sản phẩm ở bản demo trả dữ liệu giả: đầy đủ ý tưởng bao gồm AREA_MANAGER với domain/area, mapping partner request tới đúng tài khoản ban quản lý, filter owner/audience xuyên suốt, kết nối MCP thật, Builder tạo một/nhiều agent độc lập, eval/publish/version từng agent, thư viện chung trong scope, Leader tập hợp group khi có request và Settings. Mock là phương tiện làm song song và kiểm thử. V1.4 còn bao gồm ticket dài hạn, correlation công việc ngoài, Customer API + Provider Event API do platform host, durable public event/SSE replay và xác nhận đóng đúng quyền theo mục 17.
Booking thật phụ thuộc endpoint sandbox/production, credential và semantics của từng đối tác. Khi chưa có, báo cụ thể adapter nào đã kiểm tra với mock, adapter nào đã kiểm tra sandbox, điều kiện nào còn thiếu; không tự gọi giao dịch thật để hoàn thành checklist.

Việc cập nhật tài liệu lên v1.4 chỉ tạo/cập nhật kế hoạch và README scaffold. Chưa thực hiện migration, chưa triển khai customer API/Provider Event API/SSE/workflow worker và chưa thay đổi auth/business/runtime/UI thật. Sáu thành viên triển khai theo ownership/hợp đồng, bàn giao bằng chứng test; không đánh dấu hoàn thành từ việc có tài liệu.

## 17. Kết nối API, lifecycle đa lĩnh vực và routing nhiều ticket — hiệu chỉnh v1.4.3

Đây là phạm vi bắt buộc bổ sung vào phân công, chưa phải tính năng đã chạy. Mục này cụ thể hóa mục 2.7 và mở rộng contracts mục 6. V1 chỉ triển khai endpoint do platform host; không triển khai outbound webhook/REST call tới backend đối tác. Giữ nguyên mapping mục 2.6, agent độc lập/batch/reuse và một role AREA_MANAGER. Endpoint minh họa trong trao đổi chat trước đây được chuẩn hóa về đúng prefix dưới đây; không triển khai thêm các API customer/provider trùng chức năng dưới prefix khác.

### 17.1. Các bên và chiều kết nối

| Chiều | Cơ chế v1 | Trách nhiệm |
|---|---|---|
| App người dùng cuối → backend khách hàng của đối tác | API của đối tác | Đối tác xác thực người dùng, giữ ID tin nhắn/hội thoại và chọn external management ref đã cấu hình |
| Backend khách hàng → platform | POST request/reply/consent/close | Platform xác thực, lưu; request/reply chờ kết quả lượt hiện tại có thời hạn rồi trả 200 hoặc 202 fallback |
| Platform → MCP/backend nghiệp vụ | Tool qua ExecutionPort | Tra cứu, lập phương án hoặc tạo giao dịch/operation; kết quả tool quyết định bước tiếp theo theo protocol/policy |
| App nhân viên/provider → backend nghiệp vụ của đối tác | API của đối tác | Khi có operation dài hạn: xác thực actor cập nhật, lưu trạng thái và outbox để gửi lại khi lỗi |
| Backend nghiệp vụ/provider → platform | POST Provider Event API, chỉ khi integration có capability | Báo tiến độ operation cũ; không chọn agent, manager hoặc phiên chat tùy ý |
| Backend khách hàng → platform | GET SSE hoặc GET history/snapshot | Nhận/đọc nhiều status và message đúng audience; reconnect bằng cursor khi mất mạng |
| Backend khách hàng → app người dùng | SSE/WebSocket/push do đối tác quản lý | Tùy UX của đối tác; không thuộc source app đối tác trong repository này |

Backend khách hàng và backend nghiệp vụ/provider có thể cùng hệ thống hoặc khác công ty. Khi có Provider Event vẫn tách credential purpose/allowed operations và namespace; không giả định cùng một API key cho mọi chiều. Đây là machine integration, không thêm role đăng nhập theo từng loại nhân viên/provider.

SSE là kênh tùy chọn để nhận cập nhật gần thời gian thực; GET history/snapshot là đường catch-up và recovery. Backend chỉ bắt buộc theo dõi khi response trả `next_action=watch_request` hoặc `watch_events`; các lượt `submit_reply`, `submit_approval`, `confirm_close` có thể hoàn toàn dùng POST. Cùng một sự kiện đọc qua SSE và history phải có cùng event_id để client dedupe. Platform không cần biết API nội bộ mà backend khách hàng dùng để đẩy dữ liệu xuống app. V1 không bắt buộc WebSocket hay Temporal; dùng PostgreSQL + durable jobs/outbox nội bộ + Redis notification + runtime AgentScope đang có.

Ba lát cắt bắt buộc team phải triển khai; không lát cắt nào được coi là mặc định cho mọi lĩnh vực:

**A. Response-only**

```text
POST start_workflow: câu hỏi/tra cứu chỉ đọc
→ Platform lưu request, Leader/agent xử lý
→ HTTP 200 + workflow_state=closed + next_action=none
→ Không Provider Event, không bắt buộc SSE, không cần POST close
```

**B. Interactive transaction — ví dụ du lịch/booking**

```text
POST start_workflow: lập kế hoạch khách sạn và xe
→ HTTP 200 + các phương án + awaiting_user + next_action=submit_reply
→ POST workflow_reply cùng workflow_id: chọn phương án
→ Nếu có side effect: approval/consent; sau đó gọi tool booking
→ Tool xác nhận booking ngay: HTTP 200 + awaiting_confirmation + next_action=confirm_close
→ Khách xác nhận: POST close → HTTP 200 closed
→ Không cần Provider Event hoặc SSE nếu tool không trả operation pending
```

**C. External-tracking — ví dụ sửa chữa hoặc booking pending**

```text
Backend khách hàng POST start_workflow: “Gọi thợ sửa ống nước bị vỡ”
→ Platform lưu request, Leader chọn agent và gọi MCP tool
→ Platform lưu kết quả lượt đầu và trả HTTP 200: “Đã gọi thợ Nguyễn Văn A” + IDs
→ POST kết thúc; ticket/workflow vẫn mở và agent lưu checkpoint để chờ
→ Backend khách hàng GET SSE theo conversation_id để nhận event hiện có và cập nhật mới
→ Backend nhân viên POST job-event → platform nối đúng ticket → tiếp tục lượt Leader → SSE
→ Khách chat thêm: POST workflow_reply + workflow_id cũ → tiếp tục cùng phiên/context
→ Khách xác nhận hoàn tất: POST /partner/workflows/{id}/close → commit closed → HTTP 200
```

SSE là response kéo dài của GET do backend khách hàng mở; platform không gọi API backend khách hàng để gửi từng trạng thái. Chỉ mở/duy trì khi UX muốn realtime hoặc `next_action` yêu cầu theo dõi. Khi chat thêm trong **cùng ticket**, giữ SSE/conversation/group đó thay vì mở mới cho từng POST; khi người dùng tạo ticket/hộp chat khác, platform tạo binding/group/conversation riêng và backend mở stream riêng nếu cần. Tool MCP vẫn được platform gọi bình thường; contract gửi đối tác không quy định cấu trúc code/tool nội bộ MCP.

Một POST có một response rồi kết thúc. Workflow interactive/external-tracking vẫn tồn tại trong DB; response-only có thể auto-close nếu policy read-only cho phép. Mất SSE, tắt app, hết hạn token, nhận ACK hoặc hoàn thành một run không tự đóng workflow đang mở. Không đặt machine secret vào mobile/browser; browser quản lý platform dùng JWT manager hiện có. Nếu sau này có browser người dùng cuối nối thẳng platform, phải thiết kế token ngắn hạn đúng audience; không nằm trong v1 này.

### 17.2. Vòng đời workflow, lượt chạy và cách chọn continuation

Phân biệt các định danh:

| Định danh | Vòng đời / ý nghĩa |
|---|---|
| request_id / external_request_id | Một message/command được nhận; retry cùng ID không tạo việc mới |
| external_ticket_id / external_conversation_id | ID ticket và hộp chat do đối tác cấp; với route ticketed, một cặp ổn định bind một-một tới workflow/conversation/group và không được dùng chéo |
| workflow_id | Một yêu cầu nghiệp vụ kéo dài, gồm nhiều lượt xử lý và cập nhật; owner/audience cố định |
| ticket_id | Mã ticket nghiệp vụ tùy chọn; nullable với workflow không dùng ticket và không mang semantics cố định của một lĩnh vực |
| conversation_id | ID hội thoại platform. Với route ticketed v1, mỗi external ticket/hộp chat có conversation riêng gắn workflow/group tương ứng; route không có ticket có thể dùng conversation theo policy đã onboarding |
| run_id | Một lượt xử lý ngắn của Leader/agents; kết thúc lượt không đóng workflow |
| group_id / session_id / version_pins | Context và agent đã chọn cho workflow, được lưu qua các lượt chờ; không tạo bản sao agent hay build team mới |
| operation_id / correlation_id | Ý định gọi dịch vụ ngoài, được platform tạo và commit trước call |
| provider_integration_id + external_job_id | Định danh công việc trong namespace nhà cung cấp đã xác thực; trỏ duy nhất operation/workflow |
| event_id / external_event_id | ID sự kiện platform / ID sự kiện đối tác; không dùng hai loại này thay nhau |
| sequence | Thứ tự commit sự kiện trong một conversation, không phải thời gian xảy ra ở hệ thống provider |

Sau mỗi lượt, Orchestration chọn continuation theo dữ kiện đã xác minh:

1. Không còn bước nghiệp vụ và policy read-only cho phép auto-close → `closed/none`.
2. Cần thêm dữ kiện hoặc lựa chọn → `awaiting_user/submit_reply`.
3. Cần consent cho side effect → `awaiting_approval/submit_approval`.
4. Giao dịch đã xác nhận và cần người dùng chốt vòng đời → `awaiting_confirmation/confirm_close`.
5. Operation còn pending và có protocol tracking → `waiting_external_event/watch_events`.
6. Lượt hiện tại chưa xong trước HTTP deadline → giữ state hiện hành, response `202/watch_request`.
7. Không thể tiếp tục an toàn → `needs_attention/resolve_attention`.

Quy tắc trên dựa trên effect metadata, manifest/policy và output schema của tool. Không suy ra chỉ từ từ khóa lĩnh vực, tên agent hoặc câu trả lời tự nhiên. Ca external-tracking dưới đây chỉ là một lát cắt minh họa:

1. Nhận POST đầu tiên, mapping đúng manager và audience; transaction ghi request/conversation/workflow mới và job rồi commit. Chưa gửi response nhận việc ngay trong luồng bình thường: HTTP adapter bắt đầu chờ kết quả lượt xử lý hiện tại có thời hạn. ticket_id có thể được bổ sung khi xác định nghiệp vụ; nếu đã có ticket từ legacy adapter thì liên kết cùng ticket, không tạo bản thứ hai.
2. Worker chọn agent từ thư viện của manager, tạo group/runtime sessions và pin version. Khi quyết định tạo công việc, Execution ghi ExternalOperation + correlation_id/idempotency key trước network call, rồi adapter gửi client_reference tương ứng nếu provider hỗ trợ.
3. Tool trả external_job_id và trạng thái pending/assigned cùng dữ kiện đã xác minh. Execution bind job; Orchestration commit checkpoint/context, request result, public event và workflow waiting_external_event. Khi lượt đầu đã hoàn tất, HTTP adapter trả `200` với result.messages[], IDs, workflow_state/revision và `next_action=watch_events`. Nếu còn thiếu dữ kiện/consent thì kết quả lượt này là câu hỏi/approval và state/next_action tương ứng, không hứa operation đã thành công.
4. POST kết thúc, backend khách hàng có thể mở GET SSE theo conversation_id và external_user_id để nhận event. Worker kết thúc lượt, giải phóng lease/tài nguyên model. Trong lúc chờ provider chỉ còn dữ liệu bền vững và transport; không giữ coroutine LLM/transaction/worker lock nhiều giờ. Timer nghiệp vụ nếu có được lưu thành job có not_before. HTTP disconnect không hủy operation đã nhận.
5. Backend nghiệp vụ/provider gửi event. Platform xác thực, ghi inbox bền vững trước ACK; worker normalize, kiểm tra transition/version và resolve operation → workflow/ticket/conversation/owner/audience đã lưu. Không route lại bằng external_management_ref hiện tại.
6. Trong transaction, áp dụng trạng thái hợp lệ, append public status event và enqueue workflow trigger. Bộ điều phối tải checkpoint và tạo lượt Leader cần thiết với cause_event_id; giữ group/context và pin của workflow. Lượt mới không tự gọi lại tool tạo operation.
7. Leader đưa câu trả lời dựa trên sự kiện đã xác minh. Lưu message và public event atomic; phát notification signal sau commit để SSE reader catch-up từ cùng event log. Backend khách hàng đang offline đọc lại bằng history/snapshot. Xử lý xong quay lại waiting_external_event, awaiting_user hoặc awaiting_confirmation theo protocol/policy.
8. Provider báo terminal success → workflow `awaiting_confirmation/confirm_close` nếu policy cần người dùng xác nhận; backend khách hàng POST close vào workflow_id cũ. Transaction CAS/revalidate/ghi closed, event và dừng timer rồi trả `200`. Policy read-only auto-close không đi qua bước này. Đóng theo dõi sớm không hủy operation bên ngoài; API yêu cầu stop_tracking_only=true khi operation còn mở.

Quy tắc response của POST request/reply:

- HTTP adapter chờ kết quả của đúng request_id, không chạy một runtime riêng trong HTTP handler. Giới hạn đề xuất `PARTNER_TURN_WAIT_SECONDS=25`, cấu hình thấp hơn timeout proxy/client; owner xác minh giá trị khi triển khai. Trong lúc chờ không giữ transaction/lock DB.
- Lượt xử lý đã xong hoặc dừng ở một continuation point: trả `200` với kết quả đã lưu, request_status=completed, workflow_state và next_action tương ứng. Kết quả tool thất bại/unknown phải được phản ánh đúng, không biến HTTP 200 thành cam kết side effect đã thành công.
- Hết thời gian chờ, request còn accepted/queued/running: recheck DB rồi trả duy nhất `202` với IDs, URL tra cứu và `next_action=watch_request`. Backend có thể mở SSE hoặc polling GET request/history; không gửi một response khác trên POST đã kết thúc.
- Request failed/blocked đã có kết luận: trả `200` representation của request với request_status và lỗi nghiệp vụ public; lỗi validation/auth/conflict trước khi nhận request trả HTTP 4xx theo contract. GET request luôn cho tra trạng thái/kết quả đã lưu.
- Retry cùng external_request_id/body không tạo lượt thứ hai. Còn pending có thể trả 202; đã hoàn tất trả 200 với cùng persisted result. Timeout/mất mạng không tự hủy ticket hoặc gọi create tool lại. Public message trên POST/SSE/history giữ cùng message_id; SSE có thể tới trước response POST khi chat tiếp, client vẫn dedupe.

Reply gửi command_type=workflow_reply, external_request_id mới kèm workflow_id hiện có, giữ external_user_id, external_ticket_id và external_conversation_id. Ingress tải binding để resolve group trước dispatch; không tạo conversation/ticket/group khác hoặc thay phiên đang có bằng session trắng. Run_id mới chỉ ghi nhận lượt xử lý trên context/session đã pin. Leader vẫn có thể thêm agent khi phát sinh năng lực mới vào cùng group, với session riêng cho member mới. Thiếu workflow_id trả 422 WORKFLOW_REFERENCE_REQUIRED; thiếu external_ticket_id trên route ticketed trả 422 EXTERNAL_TICKET_REQUIRED; workflow đã đóng trả 409 WORKFLOW_CLOSED; tuple ticket/conversation/workflow sai trả 409 WORKFLOW_BINDING_MISMATCH. Tạo ticket mới phải chủ động gửi command_type=start_workflow với external_ticket_id và external_conversation_id mới, không có workflow_id; không dùng cờ create_new_workflow. LLM không tự chọn ticket/group theo nội dung chat khi request thiếu hoặc sai định danh.

RunGroup bổ sung workflow_id, created_run_id và active_run_id; field run_id cũ chỉ dùng cho run gốc khi cần tương thích, không dùng nó để xác định toàn bộ vòng đời ticket. wf_runs giữ lịch sử mọi lượt và liên kết group/workflow. Session của các workflow độc lập vẫn riêng; trong cùng workflow có thể tiếp tục session đã pin. Thành viên được thêm theo capability mới khi cần và lưu lịch sử; không rút agent đang giữ approval/task chưa kết thúc.

State tối thiểu của workflow:

```text
accepted → active
active → closed                                  (read-only auto-close policy)
active ↔ awaiting_user                           (reply/selection)
active ↔ awaiting_approval                       (consent trước side effect)
active → awaiting_confirmation → closed          (explicit confirmation)
active → waiting_external_event → active         (provider event/status-query)
waiting_external_event → awaiting_confirmation   (operation terminal, cần xác nhận)
any open state + authorized stop_tracking_only close → closed
active/waiting_* + exhausted failure → needs_attention
any open state + permission/revision change → blocked_authorization / blocked_route_changed
blocked + explicit authorized recovery + revalidation → trạng thái chờ/xử lý phù hợp
```

Operation state tách riêng và thuộc protocol versioned của integration. Ví dụ sửa chữa có thể là pending → assigned → on_the_way → in_progress → completed; hotel booking có quoted → confirmation_required → confirmed/cancelled; vận chuyển có searching → assigned → arriving → completed/cancelled. Core chỉ lưu state chuẩn hóa + schema/version và kiểm tra transition adapter, không hardcode các chuỗi này vào Workflow. Ticket legacy vẫn giữ state machine nghiệp vụ hiện có; progress nằm trên ExternalOperation/public projection và được bridge có kiểm soát khi cần.

### 17.3. Bộ API thống nhất để sáu người triển khai

Tất cả endpoint platform dưới prefix /workforce/v1; đây là hợp đồng cần viết, không phải danh sách endpoint đã tồn tại.

| API | Caller / quyền | Owner implementation | Kết quả |
|---|---|---|---|
| POST /partner/routes/{id}/confirm | Đúng partner client, confirm_route | Chí Hoàng | Xác nhận pending route/ref đã trao đổi; 200, không trả manager directory |
| PUT /partner/residences/{id} | Đúng partner client, sync_residence và route được cấp | Chí Hoàng | 201 tạo/200 cập nhật quan hệ residence/user/route qua adapter hiện có; không tạo workflow |
| POST /partner/requests | Backend khách hàng, submit_request với start_workflow hoặc reply với workflow_reply, đúng route/audience | Huy Hoàng | 200 có kết quả lượt này; 202 chỉ khi chờ hết hạn; luôn trả workflow_state + next_action |
| GET /partner/requests/{id} | Cùng client/audience, read_result | Huy Hoàng | Trạng thái request, workflow_state + next_action; tách request status với workflow status |
| GET /partner/conversations/{id} | Cùng client/audience, read_result | Huy Hoàng | Snapshot messages/workflows được phép xem + snapshot_cursor nhất quán |
| GET /partner/conversations/{id}/events | Cùng client/audience, read_result + receive_events | Huy Hoàng | SSE replay + live; lần đầu đọc từ đầu log, reconnect dùng Last-Event-ID hoặc after_cursor |
| GET /partner/conversations/{id}/event-history | Cùng client/audience, read_result + receive_events | Huy Hoàng | JSON {items, next_cursor, has_more}; after_cursor + limit có giới hạn |
| POST /partner/workflows/{id}/close | Backend khách hàng đại diện người dùng, close_workflow | Huy Hoàng | 200 sau CAS/commit closed + final event; dùng cho explicit-confirmation/tracking, không cần với read-only đã auto-close |
| POST /partner/approvals/{id}/decision | Backend khách hàng, submit_consent và allowed_decider | Dũng | Giữ hợp đồng approval hiện có, không dùng event cập nhật để thay consent |
| POST /provider/job-events | Backend nghiệp vụ/provider, publish_job_event cho integration có capability | Dũng | 202 accepted/quarantined sau persist; optional per integration, zero double apply |
| GET /provider/event-receipts/{id} | Chính integration đã gửi, read_event_receipt | Dũng | Chỉ ingestion status/error đã lọc; không trả lịch sử người dùng/manager |
| GET /workflows/{id}; POST /workflows/{id}/close | Manager JWT đúng scope | Huy Hoàng | Xem/quản lý workflow; close có actor audit và gửi event đúng audience |

Mọi endpoint trong bảng do platform host. Backend đối tác không phải cung cấp receiver cho platform gọi vào. Máy khách GET/POST không giữ ticket bằng kết nối mạng: POST nhận việc, GET SSE mở một connection riêng có thể ngắt/nối lại; GET history/snapshot dùng để catch-up và không phải vòng gọi LLM.

Request/reply/approval/close có namespace idempotency thống nhất (tenant_id, partner_client_id, external_request_id). Hash gồm loại command chuẩn hóa (từ command_type hoặc endpoint), resource đích, audience và body; unique key không thêm loại command để không dùng một ID cho hai hành động. Auth/audience kiểm tra trước đọc bản cũ; retry đúng command đã nhận trả cùng resource/kết quả, không kiểm tra revision cũ trước idempotency rồi từ chối retry hợp lệ. Close giữ original owner/audience, không resolve remap thành workflow mới. Foundation cung cấp idempotency/UOW contract; Orchestration và Execution dùng chung qua port cho endpoint mình, không ghi bảng riêng né namespace. Thêm close_workflow/receive_events, provider publish_job_event/read_event_receipt và onboarding confirm_route/sync_residence có chủ đích; không tự cấp quyền mới cho mọi credential cũ.

Các GET customer bắt buộc query external_user_id; middleware xác thực client rồi kiểm tra audience/grant trên resource gốc. Không truyền API key trong URL. Provider receipt chỉ dùng integration identity, không nhận query cư dân để mở rộng quyền.

Payload dưới đây chỉ minh họa một protocol sửa chữa; integration khác dùng event_type/data theo schema versioned đã onboarding, vẫn giữ envelope chung:

```json
{
  "schema_version": "1",
  "external_event_id": "technician-event-009",
  "external_job_id": "JOB-123",
  "client_reference": "platform-correlation-001",
  "event_type": "repair.technician_on_the_way",
  "provider_version": 3,
  "occurred_at": "2026-10-09T02:30:00Z",
  "data": { "estimated_arrival_minutes": 20 }
}
```

Không nhận manager/domain/area/conversation/agent ID hay callback_url tùy ý từ payload trên. provider_integration_id lấy từ credential đã xác thực; client_reference chỉ là khóa correlation, không phải bearer token. Nếu cả external_job_id và client_reference có mặt phải cùng trỏ một operation, nếu khác thì conflict/quarantine và không áp dụng.

Public event đọc qua SSE hoặc GET history dùng chung envelope. Ví dụ projection domain-neutral:

```json
{
  "schema_version": "1",
  "event_id": "platform-event-017",
  "sequence": 17,
  "event_type": "operation.status_changed",
  "occurred_at": "2026-10-09T02:30:00Z",
  "recorded_at": "2026-10-09T02:30:01Z",
  "conversation_id": "conversation-001",
  "external_ticket_id": "partner-ticket-booking-001",
  "external_conversation_id": "partner-chat-456",
  "external_user_id": "resident-123",
  "workflow_id": "workflow-001",
  "ticket_id": null,
  "payload": {
    "operation_type": "hotel_booking",
    "status_schema": "hotel_booking.v1",
    "status": "confirmed",
    "external_reference": "BOOKING-123"
  }
}
```

assistant.message là event riêng có message_id và text do Leader/template tạo từ facts. Client cập nhật status card bằng operation.status_changed/ticket.status_changed và append chat bằng assistant.message, không biến status thành chat bubble trùng. Raw provider notes chỉ là dữ liệu không tin cậy, không phải instruction cho agent.

Public event types dùng đúng bảng mục 9.7 của contract đối tác. Các event nội bộ ở mục 6.4 như workflow.waiting/provider.event_received được project sang public event phù hợp, không phát nguyên tên/payload nội bộ. SSE data và JSON history dùng cùng envelope đầy đủ; job_status nội bộ `on_the_way` có thể map thành public status `technician_on_the_way` theo schema sửa chữa. Response POST trả message đã lưu với cùng message_id như assistant.message.

Receipt của Provider Event API trả {receipt_id, ingestion_status}; việc nhận thành công không hứa status transition đã áp dụng hay cư dân đã đọc. Lỗi: 401 credential/signature sai; 403 operation không được grant; 409 EVENT_ID_CONFLICT/correlation conflict; 422 schema/type không hợp lệ; 429 giới hạn tải; 5xx khi chưa persist được để đối tác retry. Event hợp lệ nhưng chưa có binding được durable quarantine và trả 202, không vứt đi hoặc gọi Leader đoán owner.

### 17.4. Contract liên module và quyền sở hữu dữ liệu

Chí Hoàng bổ sung contracts/async_api/ và TypeScript tương ứng. Interface mới version additive; không định nghĩa DTO production riêng trong sáu module. schema_version của event payload độc lập với phiên bản tài liệu 1.4.

| DTO mới / mở rộng | Nội dung tối thiểu |
|---|---|
| WorkflowRecord | workflow_id, scope, audience gồm external_ticket_id?, conversation_id, ticket_id?, route_id/revision, state, revision, group_id bắt buộc sau accept, checkpoint_ref?, version_pins, pending_waits, last_applied_event_id?, timestamps |
| TicketConversationBinding | scope, partner_client_id, external_user_id, external_ticket_id, external_conversation_id, workflow_id, conversation_id, group_id, route_id/revision, status, timestamps; immutable routing identity của ticket đã nhận |
| WorkflowTrigger | trigger_id, workflow_id, cause_event_id hoặc request_id/timer_id, kind, expected_state_revision?; scope đọc lại DB |
| WorkflowCheckpoint | workflow_id, state_revision, session refs, agent/version pins, shared state ref, pending task/question/approval IDs, operation refs, last processed causes, budget đã dùng |
| AsyncToolProtocol | protocol_id/version, schema_hash, tool_version_id, provider integration ref, capability, create/result field mapping, client_reference support, Provider Event API/MCP status-query mode, event schemas, ordering policy, transition map, timeout policy |
| ExternalOperation | operation_id, scope/audience refs, workflow_id, ticket_id?, conversation_id, call_id, provider_integration_id, protocol snapshot/hash, correlation_id, external_job_id?, creation_status, job_status, last_provider_version?, revision |
| ProviderEventEnvelope / Receipt | schema_version, external_event_id, external_job_id?, client_reference?, event_type, provider_version?, occurred_at, data; receipt_id, ingestion_status, duplicate?; external_job_id hoặc client_reference bắt buộc có ít nhất một |
| NormalizedJobEvent | immutable inbox_event_id, provider identity, correlation refs, normalized status/facts, provider version/order mode, source hash, received_at; chưa có scope cho tới resolve binding |
| ConversationEvent | envelope mục 6.1 + external_ticket_id?, workflow_id?, ticket_id?, causation_id, schema_version, recorded_at; external_ticket lấy từ binding, public projection không lộ scope/actor/credential/group nội bộ |
| AsyncHandlingPolicy | capabilities/event types agent xử lý, facts bắt buộc, completion condition, human confirmation/timeout behavior; không chứa ticket/job/endpoint/roster cố định |

Provider identity là machine principal kind=partner với purpose=provider_events, không thêm role sản phẩm. Foundation quản lý identity/credential và grant publish_job_event, Registry mô tả protocol, Execution sở hữu operation correlation; không đồng nhất provider_integration_id với MCP tool name hoặc tài khoản ban quản lý.

| Port / provider | Interface cần chốt sớm | Consumer |
|---|---|---|
| ProviderAuthPort / Chí Hoàng | authenticate(raw_body, headers) → verified provider principal; authorize_integration(principal, operation, uow?) | Provider HTTP adapter của Dũng |
| AsyncProtocolPort / Đông | get_snapshot(scope, tool_version_id); normalize_verified_event(provider_context, protocol_snapshot, envelope) → NormalizedJobEvent; validate capability coverage | Builder, Lifecycle, Execution |
| ExternalOperationPort / Dũng | prepare(scope, run_context, call, protocol, uow); bind_result(scope, operation_id, result, uow); get_for_workflow(scope, workflow_id) | Execution gateway, Orchestration; không lộ lookup ngoài scope |
| ProviderEventIngressPort / Dũng | accept(verified_principal, envelope, payload_hash) → Receipt; read_receipt(principal, receipt_id); process(receipt_id) | HTTP provider router, worker |
| PartnerCommandPort / Huy Hoàng | claim_or_read(actor, external_request_id, command_kind, target_ref, payload_hash, uow); resolve_ticket_binding(scope, audience, external_ticket_id, external_conversation_id, workflow_id?, uow); record_result(request_id, result, uow) | Request/reply/close của Huy Hoàng và approval của Dũng; chung namespace wf_inbound_requests, không tự commit hoặc bỏ qua audience/binding check |
| WorkflowPort / Huy Hoàng | start_with_binding(scope, actor, audience, message, uow); accept_reply(scope, actor, audience, workflow_id, message, uow); apply_external_event(scope, operation_ref, normalized_event, uow); enqueue_trigger(scope, trigger, uow); close(scope, actor, audience, command, uow) | Partner ingress, Execution event processor, timer handlers; mọi reply/close dùng group từ binding, không từ body/LLM |
| ConversationEventPort / Huy Hoàng | append(scope, audience, event, uow); list_after(actor, conversation_id, cursor, limit); snapshot(actor, conversation_id); subscribe(actor, conversation_id, cursor) | Orchestration, public projection, manager/partner API |
| PublicEventSignalPort / Chí Hoàng | notify_after_commit(scope, conversation_id, committed_sequence); wait_for_signal(scope, conversation_id, timeout); health() | SSE/result waiter dùng context đã kiểm tra quyền; chỉ đánh thức reader, DB event/result là nguồn bền vững |
| RuntimeContinuationPort / Chí Hoàng | load_pinned_context(scope, checkpoint); invoke_turn(scope, trigger, checkpoint, execution_guard); persist_checkpoint(...) | Huy Hoàng; concrete adapter bọc AgentScope hiện hữu |

Lookup provider correlation trước khi có scope là ngoại lệ hẹp của quy tắc scope-first: chỉ repository nội bộ Execution nhận verified provider principal và tìm trong đúng integration namespace. Sau lookup, tất cả mutation dùng scope/audience trên operation. Không mở API nhận arbitrary scope hoặc query theo external_job_id toàn database.

WorkflowPort.apply_external_event kiểm tra FK operation/workflow/scope đã pin; không tin scope trong broker payload. Registry normalization là hàm xác định/adapter, không gọi LLM và không trực tiếp cập nhật ticket. Composition root inject các port; Execution có thể gọi WorkflowPort qua injection nhưng không import private Orchestration service.

Phân chia bảng bổ sung, dùng cùng PostgreSQL và uow mục 6.3:

| Owner | Bảng / phần mở rộng |
|---|---|
| Foundation | Mở rộng wf_jobs.not_before/lease/fencing và wf_outbox cho internal wakeup/signal; credential/provider purpose và grant trong hệ identity hiện có; không tạo bảng subscription/delivery tới endpoint đối tác |
| Registry | wf_async_tool_protocols và snapshot/hash gắn tool version; không lưu secret hoặc raw ticket |
| Builder | Mở rộng proposal/requirements/manifest generation đã sở hữu; không tạo bảng workflow |
| Lifecycle | Manifest/evaluation snapshot thêm async policy + protocol hash; suite/case hiện hữu mở rộng, không lưu runtime ticket vào agent definition |
| Orchestration | wf_workflows, wf_workflow_waits, wf_workflow_triggers, wf_conversation_events; mở rộng wf_partner_conversation_bindings bằng external_ticket/workflow/group keys và wf_runs/checkpoint/runtime bindings; workflow ↔ legacy ticket liên kết qua adapter |
| Execution | wf_external_operations, wf_provider_event_inbox; liên kết wf_tool_calls và lịch sử normalized execution event hiện có |

Unique bắt buộc: `(tenant_id, partner_client_id, external_user_id, external_ticket_id)` và `(tenant_id, partner_client_id, external_user_id, external_conversation_id)` cho binding ticketed; (tenant_id, provider_integration_id, external_event_id) kèm canonical payload hash; (tenant_id, provider_integration_id, external_job_id) khi job ID không null; correlation_id unique server-generated; (workflow_id, cause_kind, cause_id) cho trigger; (conversation_id, sequence). Nếu provider tái sử dụng job ID giữa tài khoản của họ, onboarding phải cấp provider integration namespace riêng cho từng tài khoản; không “khắc phục” bằng chọn record mới nhất.

wf_conversation_events là log semantic public events và là nguồn để SSE/history replay. wf_outbox chỉ mang job/signal nội bộ sau commit, không đại diện một HTTP delivery tới đối tác. Public projection được đóng băng theo event; mọi lần đọc vẫn revalidate actor/audience hiện hành. Không đưa từng token stream vào log nghiệp vụ bắt buộc.

Mỗi owner viết schema/repository trong folder con riêng và export metadata qua module mình. Chỉ Chí Hoàng tạo Alembic revision thật. Không tự đánh số migration ở sáu nhánh, không thay bảng tickets/ticket_events bằng bảng mới gây hai nguồn trạng thái nghiệp vụ.

### 17.5. Nhận event, đánh thức runtime và phục hồi sau crash

Quy trình nhận/áp dụng hai giai đoạn để ACK nhanh và có thể retry:

1. Xác thực credential/signature trên raw body trước parse; validate schema, giới hạn payload và event types. Tạo hash canonical nội dung nghiệp vụ, không đưa timestamp/chữ ký transport của lần retry vào hash. Transaction ghi inbox với unique event key và job xử lý. Chỉ trả 2xx sau commit; transaction lỗi trả 5xx. Event ID cũ cùng hash trả receipt cũ; cùng ID khác hash trả 409.
2. Worker claim inbox bằng lease. Dùng integration + job ID/client_reference resolve operation; recheck quyền và protocol snapshot đã pin. Provider event đến trước kết quả create tool được nối bằng correlation intent có trước call. Chưa nối được thì quarantine có TTL/reconciliation, không đoán ticket theo tên cư dân/nội dung.
3. Trong cùng uow, Execution cập nhật job progress/inbox outcome; WorkflowPort cập nhật workflow state và ConversationEventPort append status event + JobPort enqueue trigger. Commit toàn bộ hoặc rollback; các port không tự commit. Sau commit, PublicEventSignalPort đánh thức SSE reader; nếu tín hiệu mất, reader vẫn catch-up từ DB. Provider event không hoàn thành một tool call đã succeeded lần thứ hai.
4. Worker workflow claim trigger; serialize theo workflow và session, dùng lease có fencing token để worker hết hạn không ghi đè worker mới. Không giữ DB transaction qua lời gọi model/provider. Context/checkpoint + message + event/outbox + trigger completion được commit nhất quán bằng revision/fence.
5. Crash có thể làm model được gọi lại; chỉ một kết quả message được commit theo cause/message key. Side-effect calls đi qua Execution idempotency/approval, không gọi lại provider create chỉ vì checkpoint cũ. Sau restart, scanner tìm inbox/trigger/job còn pending hoặc lease hết hạn từ DB; Redis notification chỉ giúp chạy nhanh.
6. Provider event đến đúng lúc workflow chuẩn bị ngủ: enqueue trigger và chuyển state phải cùng revision/transaction; worker drain/recheck pending causes trước relinquish. Không mất wakeup do check-then-sleep race.
7. User reply và staff event đồng thời được serialize theo workflow, vẫn append sự kiện trong conversation theo thứ tự commit. Không tự dùng status event trả lời câu hỏi đang hỏi cư dân hoặc thay approval. Nếu runtime session đang ASKING/SUBMITTED, lưu pending event và public status trước; chỉ resume session bằng event đúng loại khi điều kiện chờ được giải quyết. Không giả UserConfirmResultEvent/ExternalExecutionResultEvent để phá parked state.
8. Nếu agent bị block/revoked, lưu trạng thái thật của công việc ngoài và tình trạng blocked nhưng không cho tool call/LLM resume trái policy. Sự kiện status đã đủ quyền có thể thông báo theo template xác định; không giả rằng Leader đã chạy. Chọn mode template/leader_turn trong workflow policy, mặc định leader_turn cho ca cần hội thoại; notification cơ bản không phụ thuộc LLM luôn sẵn sàng.
9. Revalidate route revision, manager membership, credential/binding và audience trước turn/tool/send. Revoked machine credential bị từ chối ngay ingress; provider credential còn hợp lệ có thể báo sự thật của job cũ khi route cư dân đã revoked: lưu audit/job progress nhưng chặn gửi ra audience không còn quyền và chặn resume. Không chuyển ticket/history sang manager mới.

Ordering phải được nêu trong AsyncToolProtocol của từng nhà cung cấp:

- Có provider_version tăng theo job: bỏ qua version cũ/duplicate để không lùi status. Nếu cùng version khác nội dung thì quarantine conflict. Adapter khai báo event là snapshot hay delta: snapshot mới có thể dùng khi validation cho phép; delta thiếu version trung gian phải buffer/reconcile qua query trước khi áp dụng.
- Không có version: occurred_at không đủ bảo đảm thứ tự. Chỉ áp transition đã xác nhận và không lùi state; event mơ hồ/terminal conflict phải query trạng thái provider hoặc needs_attention, không nhờ LLM đoán trình tự.
- Một terminal completed không bị event on_the_way đến muộn đẩy lùi. Correction/reopen phải là event/command được protocol khai báo, không lấy “timestamp lớn hơn” làm quyền sửa trạng thái đã hoàn tất.
- provider_version/occurred_at khác sequence platform. Sequence được cấp dưới transaction khóa conversation/cursor row để thứ tự visibility/commit nhất quán; không chỉ dùng global auto-increment rồi giả định transaction có ID thấp luôn commit trước.

Tool provider tạo operation timeout: giữ creation_status=unknown, đối soát theo correlation/idempotency key nếu có. Provider event hợp lệ có thể xác nhận operation tồn tại; không gọi create lần nữa. Nếu không có MCP status-query/correlation và event không đủ xác minh, đưa needs_attention. Nếu backend provider không chủ động POST status nhưng MCP có status-query tool, scheduled worker gọi tool đó bằng protocol/credential đúng scope; chỉ khi thấy thay đổi mới sinh normalized event. Logic này chỉ áp dụng operation pending; tool terminal đồng bộ không tạo timer/tracking giả.

### 17.6. SSE, history và retention

SSE/history:

- GET events trả text/event-stream UTF-8, mỗi semantic event có id=event_id, event=event_type, data=public projection; heartbeat comment mặc định 15 giây (cấu hình được), không có business event ID. Bổ sung cache/proxy headers phù hợp và kiểm thử proxy không buffer. Giới hạn connection và queue cho slow consumer; ngắt để reconnect thay vì giữ RAM tăng vô hạn.
- Lần mở SSE đầu tiên không có cursor: đọc mọi public event từ đầu hội thoại theo thứ tự, kể cả event commit trước khi GET tới. Nếu đầu log đã hết retention, trả 410 để lấy snapshot; không âm thầm bỏ qua. Khi đã hiển thị message từ POST 200 thì replay cùng message_id chỉ dedupe, không thêm bubble thứ hai. Khi đã có SSE thì dùng lại khi gửi reply, không mỗi POST mở một stream mới.
- Last-Event-ID hoặc after_cursor trỏ event đã commit thuộc conversation/audience hiện tại; nếu có cả hai phải khớp. Không so thứ tự UUID theo chữ; resolve sang sequence trong DB. Cursor của hội thoại khác hoặc chưa từng tồn tại bị từ chối, không tiết lộ dữ liệu. Đây là ID cuối client đã xử lý, không lấy last_event_id trong GET request làm cursor nếu chưa xử lý các event trước đó.
- Reader giữ last delivered sequence, đọc DB theo trang, subscribe notification và recheck DB để không mất event ở khe giữa replay/live. Định kỳ catch-up DB ngay cả khi Redis signal bị mất. Event giao lặp được chấp nhận; client dedupe event_id/message_id và chỉ advance cursor sau xử lý.
- Event đã ẩn bởi audience filter không được đưa vào prompt/UI; sequence có thể có khoảng trống ở projection, không coi mọi gap là mất event. Snapshot và snapshot_cursor phải đọc cùng một consistent DB snapshot, kèm status/workflow/messages/approval được phép xem; catch-up bắt đầu sau cursor đó. Khi chưa từng có public event, snapshot_cursor=null và client mở SSE không cursor. Giữ cursor anchor/watermark đủ để dùng snapshot khi event cũ đã purge; snapshot phục hồi trạng thái hiện tại, không hứa lấy lại lịch sử đã hết retention.
- Cursor đã hết retention trả 410 EVENT_CURSOR_EXPIRED với hướng dẫn GET snapshot rồi mở stream từ snapshot_cursor; không âm thầm trả 200 với lịch sử thiếu. History hỗ trợ cùng cursor semantics và phân trang.
- Manager UI dùng fetch streaming với Bearer/token provider hiện có; EventSource native không có tùy chọn arbitrary Authorization header. Nếu dùng cookie-based SSE cần thiết kế auth/CORS/CSRF tương ứng, không gắn secret lâu dài vào query URL.
- Token/grant hết hạn/thu hồi trong khi stream mở phải ngắt hoặc revalidate theo khoảng thời gian hữu hạn; client refresh/reconnect qua transport chung. Giới hạn trễ thu hồi mục tiêu v1 là tối đa 60 giây, kiểm thử bằng clock. ID cursor không cấp quyền.

Retention và đóng workflow:

- Giá trị khởi đầu cần cấu hình: giữ public event history toàn bộ khi workflow mở và tối thiểu 90 ngày sau đóng; giữ provider inbox dedupe tối thiểu 180 ngày và không ngắn hơn replay window đã cam kết với đối tác. Dữ liệu hội thoại cần lưu lâu hơn do policy khác phải được tính riêng. Đây là default đề xuất của dự án, không phải thời hạn pháp lý.
- Không purge public event còn trong replay window, pending inbox, operation unknown, workflow đang chờ hoặc references cần audit/version pin. Purge theo scope, dry-run, batch limit, có watermark và metrics; không xóa active agent/version để giải phóng ticket history.
- Close command dùng expected_revision/CAS để không đua với status update. Ghi workflow.closed và final public event cùng transaction, hủy timer/chặn pending trigger chưa chạy rồi trả 200 với state=closed/revision. Lượt đang chạy phải recheck revision/state trước commit/tool tiếp theo; provider call đã gửi vẫn cần lưu kết quả thật qua Execution nhưng không phát chat thường hoặc mở lại workflow. Legacy ticket đồng bộ qua bridge owner-filtered theo state machine hiện hữu, không dual-write rời rạc hoặc báo đã đóng cả hai nơi trước khi bridge hoàn tất. Chat vẫn đọc lịch sử và có workflow khác; close một ticket không đóng toàn bộ conversation.
- Provider event đến sau close vẫn được dedupe/lưu audit/job fact khi còn retention/quyền, nhưng không mở lại workflow hoặc chạy agent/gửi chat thường. Muốn reopen là nghiệp vụ riêng, chưa tự thêm trong v1. Public event đã commit trước close vẫn được đọc theo sequence, bao gồm close event.
- Waiting quá lâu tạo timer status-query/escalation/needs_attention, không tự giả công việc hoàn tất. Job/timer đã ghi vẫn sống qua restart, retry tạo một trigger theo timer ID.

Các giá trị timeout/retry/retention trên do Chí Hoàng đưa vào cấu hình và .env.example khi triển khai; không yêu cầu sửa .env cá nhân trong công việc lập kế hoạch.

### 17.7. Tận dụng code hiện hữu và giới hạn đã kiểm tra

| Code hiện có | Cách dùng / bổ sung |
|---|---|
| _bus_ops.deliver_to_inbox, _manager/_wakeup_dispatcher.py | Dùng làm tín hiệu dispatch ngắn tới runtime; DB workflow/inbox/jobs mới bảo đảm không mất việc, không lấy queue drain làm ACK nghiệp vụ |
| _service/_chat.py và _skip_parked_wakeup | Tái sử dụng ChatService/session context; adapter phải giữ pending HITL và phân biệt event tiến độ với kết quả tool còn SUBMITTED |
| _router/_session.py: stream_session_events | Có streaming qua nhiều run và heartbeat, nhưng replay log giới hạn theo run, hiện chưa có SSE id/Last-Event-ID theo toàn lịch sử ticket; Huy Hoàng xây public event projection/log, Chí Hoàng nối core hook nếu cần |
| examples/agent_service/main.py | Hiện dùng InMemoryMessageBus; khi chạy nhiều worker phải cấu hình bus tương thích. Chỉ đổi sang RedisMessageBus không thay thế durable workflow/event log |
| business/_service.py: update_ticket_status, tickets/ticket_events | Giữ ticket business service; hiện update chỉ ghi ticket/event, chưa có workflow correlation/public event projection. Chí Hoàng viết bridge owner-filtered, Dũng/Huy Hoàng không sửa trực tiếp service cũ |
| PostgreSQL/SQLAlchemy/Alembic hiện có | Lưu nguồn trạng thái, unique keys, uow, leases và event log; test race/crash trên PostgreSQL thật |
| Redis 7 trong compose.yaml | Điều phối/fan-out, có thể dùng Streams nếu adapter cần nhưng DB vẫn có recovery; không dựa API Redis đời mới chưa có trong bản repo |
| Registry, Builder, Lifecycle ports theo kế hoạch | Async protocol trở thành capability thật để validate/eval/publish; không chỉ thêm prompt “hãy chờ cập nhật” |

Không giữ nguyên một HTTP POST nhiều giờ, không triển khai runtime mới thay AgentScope. Temporal là lựa chọn đánh giá sau khi có nhu cầu workflow phức tạp hơn; v1 không tự thêm cluster/dependency này.

### 17.8. Bàn giao phía đối tác, triển khai và quan sát

Trong repo này xây API platform, adapters, mẫu payload và backend đối tác giả lập; không đánh dấu app đối tác thật đã tích hợp khi chỉ mock pass. Onboarding luôn chốt external management ref/auth/retry; chỉ integration external-tracking mới cần provider operation namespace, schema/version/transition, correlation/idempotency và Provider Event hoặc MCP status-query. Không yêu cầu đối tác cung cấp endpoint receiver cho platform.

Chí Hoàng xuất OpenAPI/JSON Schema và hướng dẫn tích hợp trong docs/workforce/handoffs/nguyen-chi-hoang/async_api/. Đông ghi protocol mapping/provider requirements trong handoff riêng. Dũng cung cấp fake resident backend gọi Customer API, fake technician backend gọi Provider Event API và SSE client ở tests/workforce/fixtures/async_partners/; có script/hướng dẫn gửi một yêu cầu, phát nhiều status, mất kết nối rồi catch-up, đóng ticket. Người khác dùng fixture contract đã xuất hoặc fake nội bộ, không cùng sửa fixture chung.

Metrics tối thiểu: inbox accepted/applied/duplicate/quarantined, trigger backlog/lease recovery, workflow waiting age, provider unknown, public-event lag, SSE connections/reconnect/cursor expired và auth blocked. Trace/audit dùng request_id/workflow_id/operation_id/event_id/receipt_id; không log credential/raw private payload. UI của manager chỉ thấy lỗi trong scope của mình.

Rollout: migration additive → contract tests → mock end-to-end → restart/race/proxy tests → một integration sandbox → mở từng integration có cấu hình. Không enable Provider Event API/SSE production trước khi DB/inbox/event log/worker/proxy đã sẵn sàng. Rollback tắt tính năng cho request mới nhưng giữ provider ingress, persistence và history/SSE cho workflow đang mở; không downgrade schema xóa pending event. Runbook ghi cách restore DB, reclaim leases, reconcile unknown, rotate provider signing key, xử lý expired cursor và không tự chuyển chủ khi route thay đổi.

### 17.9. Nhịp triển khai bổ sung và điểm bàn giao

Đây là effort bổ sung cho kế hoạch ngày 1–40, cần team ước lượng lại khi chốt baseline; không coi các task mới là miễn phí. Có thể lồng vào các nhịp cũ nếu chưa bắt đầu code.

| Nhịp bổ sung | Chí Hoàng | Phương Đông | Hữu Nghĩa | Tiến Anh | Huy Hoàng | Hoàng Dũng |
|---|---|---|---|---|---|---|
| A — Chốt hợp đồng, 1–2 ngày làm việc dự kiến | DTO/ports/uow/auth purpose + schema samples | Protocol fields/ordering mapping | Async requirement/policy schema | Validation/eval snapshot schema | Workflow/checkpoint/event schema | Operation/inbox schema + provider-event fixtures |
| B — Làm độc lập, khoảng 4–6 ngày dự kiến | Jobs/SSE signal/transport + fake event refs | Protocol registry/normalizer/UI | Build capability checks/UI với fake ports | Async validation/suites với fake runner | Workflow/replay/SSE/UI với fake operation/signal | Provider ingress/correlation/reconciliation/fake technician backend |
| C — Nối lát cắt, khoảng 3–5 ngày dự kiến | Migrations + bootstrap + provider signature contracts | Nối protocol thật với Execution | Nối validation protocol vào build | Nối eval multi-turn vào runtime | POST → wait → event → Leader → event log | Create mock job → Provider Event API → status → SSE client E2E |
| D — Chịu lỗi và bàn giao, khoảng 3–5 ngày dự kiến | Worker restart/proxy/runbook/metrics | Schema drift/disable protocol | Missing-capability/reuse regressions | Publish pin/long wait regressions | Reconnect/replay/close race | Duplicate/out-of-order/crash/unknown/scope + sandbox được cấp |

Merge ports/schemas sớm; sáu nhánh làm business logic/UI/test bằng fake trước. Chí Hoàng chỉ giữ file dùng chung/migration/hook, không viết hộ inbox/workflow/normalizer của ba module khác. Trước mỗi nhịp, từng người bàn giao schema và public exports nhỏ để migration/composition không dồn cuối đợt.

Gate bổ sung: MA hợp đồng/fake dùng chung; MB chạy ca request → assigned → on_the_way → arrived → completed → user close; MC qua restart/replay/duplicate/race/isolation; MD có integration guide và bằng chứng sandbox hoặc nêu chính xác điều kiện đối tác còn thiếu. Không tuyên bố MD production pass khi chỉ có mock.

### 17.10. Nguồn kỹ thuật tham khảo

Các quyết định ownership, schema và default vận hành ở trên là thiết kế của dự án. Tham khảo giao thức và đặc tính liên quan, kiểm tra ngày 09/10/2026:

- [RFC 9110 — 202 Accepted](https://www.rfc-editor.org/rfc/rfc9110.html#section-15.3.3): 202 xác nhận đã nhận nhưng xử lý chưa hoàn tất; kết quả sau đó cần được tra/nhận qua cơ chế khác. Thiết kế dự án dùng 200 cho kết quả lượt POST đã xong và 202 cho fallback có thời hạn.
- [WHATWG — Server-sent events](https://html.spec.whatwg.org/dev/server-sent-events.html): event id, Last-Event-ID, định dạng stream và reconnect. Lưu/replay lịch sử vẫn là trách nhiệm backend.
- [Redis — Pub/Sub delivery semantics](https://redis.io/docs/latest/develop/pubsub/): Pub/Sub có thể mất message khi subscriber không nhận được; không dùng làm kho sự kiện bền vững.
