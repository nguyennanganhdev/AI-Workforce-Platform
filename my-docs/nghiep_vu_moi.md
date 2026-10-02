 Nghiệp vụ hệ thống

1.Đăng kí:
-Cư dân sẽ đăng kí tài khoản với số điện thoại,họ tên,mật khẩu
-Tài khoản của ban quản lý và nhân viên sẽ được admin cấp (admin sẽ tạo tài khoản trên trang của admin)
2.Đăng nhập:
-Người dùng chỉ cần đăng nhập bằng tài khoản của mình thì hệ thống sẽ tự ánh xạ theo role và điều hướng đến đúng trang được phép sử dụng.
** Admin có thể kích hoạt,tạm khóa hoặc xóa hẳn 1 tài khoản **
3.Trang cư dân:
-1 cư dân có thể tạo nhiều cửa sổ chat,mỗi cửa sổ chat sẽ được trao đổi để  giải quyết 1 vấn đề hoặc 1 ticket. (giống như giao diện ChatGPT hiện tại).
-Khi reception agent tạo ticket và gửi cho supervisor thì sẽ tự động hiển thị 1 thẻ ticket để cư dân có thể theo dõi trạng thái của ticket đó.
-Có thông báo mỗi khi có tin nhắn mới từ ticket
-Ở đây là cư dân chat trực tiếp với reception agent.
4.Reception agent (chạy bên trong).
-Tiếp nhận ý kiến hoặc câu hỏi từ phía cư dân.
-Trả lời ngay dựa trên kiến thức sẵn cho cho những câu hỏi liên quan đến FAQ,Quy định khu đô thị hay tòa nhà,Các dịch vụ của khu đô thị,...
-Nếu các vấn đề cần đến nhân viên hỗ trợ trục tiếp thì sẽ tạo ticket và ping đến Supervisor agent,khi supervisor agent đã phân tích xong ticket và gửi đến cho subagent thì cần phải có phản hồi ngay cho reception agent rằng đã gửi yêu cầu đến bên nhân viên để reception agent trả lời cư dân.Sau đó Reception agent sẽ tạm dừng bằng interrupt() để đợi trạng thái mới từ nhân viên,khi nhân viên có trạng thái mới sẽ gửi event lên cho reception agent để thông báo đến cho cư dân.
-Xác định rõ thông tin về sự cố như tên chủ nhà,số điện thoại,căn hộ số…,tòa….,thuộc khu đô thị…để gọi đến đúng group chat của domain và ban quản lý đó.(Nghĩa là mỗi ban quản lý sẽ quản lý 1 tòa nhà hoặc 1 phân khu riêng (ví dụ trong khu nhà liền kề của Vinhome Ocean park 2 có khu cọ xanh,hải âu,...) thì reception agent cần thu thập đủ thông tin để gọi đến đúng tài khoản của ban quản lý đó rồi mới truyền ticket cho supervisor của tài khoản ban quản lý đó.Nghĩa là mỗi ban quản lý sẽ có tài khoản riêng và trong mỗi tài khoản sẽ lập group chat riêng)

Lưu ý: cần các bảng quản lý ticket chặt chẽ,để dễ cho việc nhân viên cập nhật trạng thái và gửi event đúng ticket .(Mối quan hệ 1 user - n ticket ; 1 ticket - n event)

5.Supervisor agent(Chạy bên trong):
agent điều phối, điều phối các agent con để hoàn thiện 1 task
dùng hàm agent team của agentscope2.0
nguyên lí : Agent điều phối một nhóm agent chuyên môn để hoàn thành một task lớn. Supervisor phân rã task, tạo/assign subtask cho từng agent và theo dõi tiến độ thông qua **shared Task Board**. Các agent có state phối hợp chung của team nhưng vẫn giữ context thực thi riêng. Khi một agent cần thông tin/hỗ trợ từ agent khác, nó có thể **gửi message trực tiếp cho agent đó hoặc broadcast cho team**, không bắt buộc phải thông qua Supervisor. Supervisor chịu trách nhiệm điều phối tổng thể và tổng hợp kết quả cuối cùng.

phần @agent
Khi người dùng @AgentB, hệ thống tự bắt @AgentB, lấy context của room hiện tại gồm các message gần nhất + ticket/task hiện tại + kết quả liên quan, rồi truyền cùng câu hỏi cho AgentB. Có thể tận dụng AgentScope Agent Team ở phần shared Mailbox/Task Board và message routing, nhưng AgentScope không tự hiểu toàn bộ lịch sử room để nhét đúng context cho AgentB; phần chọn đoạn chat nào cần gửi vẫn nên do hệ thống mình làm bằng một Context Builder. AgentB sau đó trả lời lại vào cùng room nên tiếp tục giữ được mạch hội thoại.

6.Subagent (Chạy bên trong):
	6.1: Technical Agent
Tiếp nhận yêu cầu của cư dân (sự cố về điện, nước, cơ sở vật chất, …)
Nếu là vấn đề đơn giản: Agent hướng dẫn cứ dân xử lý luôn (nếu không được gửi xử lý cho orchestrator)
Nếu phức táp: gửi orchestrator chọn sub-agent kỹ thuật (Điện, nước, cơ sở vật chất)
TH Điện: kiểm tra xem nhân viên kĩ thuật điện có rảnh không
-> rảnh: gửi thông báo đến nhân viên điện -> nhân viên đến xác nhận -> xác nhận sửa chữa với cư dân -> cư dân xác nhận -> nhân viên kĩ thuật sửa -> xong chụp ảnh gửi agent -> cư dân xác nhận sửa xong
-> không rảnh: xếp yêu cầu sửa chữa vào queue chờ xử lý khi nhân viên rảnh -> thông báo đã nhận ticket đã đươc vào trạng thái chờ
TH Nước: gửi thông báo đến nhân viên nước -> nhân viên đến xác nhận mức độ hỏng
-> Ít (không cần khóa van nước khu vực):  nhân viên kĩ thuật sửa -> xong chụp ảnh gửi agent -> cư dân xác nhận sửa xong
-> Lớn (Khóa van nước khu vực):  nhân viên gọi quản lý khóa van nước -> quản lý xác nhận -> gửi thông báo cắt nước tạm thời cho cư dân -> khóa nước -> nhân viên sửa chữa > xong chụp ảnh gửi agent -> gửi thông báo mở nước lại ->cư dân xác nhận sửa xong


6.2 :Sercurity Agent
- Tiếp nhận sự cố an ninh từ orchestrator (người lạ, trộm cắp, ẩu đả, ồn ào, ...)
- Nếu thiếu thông tin (vị trí, mức độ): hỏi lại cư dân qua Lễ tân, không tự suy đoán
- Nếu là vấn đề đơn giản (hỏi nội quy, đăng ký khách): Agent hướng dẫn cư dân luôn (nếu không được thì tạo sự cố để xử lý)
- Nếu cần xử lý tại chỗ: tạo sự cố, xác định mức độ (P0–P3)
  + TH Thông thường (P2/P3, ví dụ: ồn ào, đỗ xe sai chỗ): tra camera gần vị trí (chỉ xem camera nào, online/offline) -> kiểm tra bảo vệ gần đó có rảnh không
	-> rảnh: Agent đề xuất điều bảo vệ -> hệ thống duyệt -> gửi lệnh cho bảo vệ -> bảo vệ đến hiện trường xử lý -> xong chụp ảnh gửi agent -> cư dân xác nhận đã xử lý xong
	-> không rảnh: xếp vào queue chờ -> thông báo cư dân đã nhận ticket, đang chờ -> quá thời gian chưa có người thì báo trưởng ca
	-> đến nơi thấy nghiêm trọng hơn: nâng mức độ -> chuyển sang TH Khẩn cấp
	-> không cần nữa (cư dân báo đã ổn): Agent đề xuất hủy điều động -> hệ thống duyệt -> hủy, ghi lý do
  + TH Khẩn cấp (P0/P1, ví dụ: đột nhập, ẩu đả có người bị thương): lấy quy trình khẩn cấp + danh sách người cần báo -> đồng thời điều bảo vệ gần nhất tới
	-> gửi cảnh báo cho người trực -> người trực xác nhận đã nhận -> chỉ đạo xử lý theo quy trình -> bảo vệ báo tình hình -> sự cố được kiểm soát -> ghi lại bằng chứng -> BQL xác nhận xong
	-> gửi cảnh báo lỗi hoặc không ai xác nhận: báo người tiếp theo trong danh sách -> sự cố vẫn đang xử lý, không coi là xong




6.3:Report agent
		-Khi ban quản lý có request ví dụ “hãy lập báo cáo doanh thu của đội kĩ thuật đã xử lý sự cố trong 6 tháng gần đây” thì report agent sẽ truy xuất và tổng hợp tất cả hóa đơn của riêng phần kĩ thuật và lập báo cáo.Hay request khác như “hãy lập báo cáo cho tôi về tần suất xuất hiện các sự cố trong tòa S2.01” thì report agent sẽ chỉ truy xuất và tổng hợp thông tin về sự cố riêng trong tòa S2.01.(Như vậy trong mỗi ticket cần có rõ và chi tiết các field)
	-Khi đã truy xuất xong thì sẽ lập báo cáo dưới dạng docx.
…
7.Nghiệp vụ của nhân viên trong các lĩnh vực con:
	7.1:Trang của Tecnical
7.2: Trang của sercurity

7.3:
8.Trang của admin:
-Ở đây admin sẽ có thể quản lý tài khoản của toàn bộ hệ thống:tạo tài khoản cho ban quản lý,duyệt tài khoản của cư dân và nhân viên,kích hoạt/tạm khóa/xóa vĩnh viễn 1 tài khoản.
-Khi có data cần được thêm vào long-term memory khi học tăng cường thì admin sẽ được xem và duyệt data đó.


9.Trang của Ban Quản Lý:
-Được phép tạo agent trên UI.
-Các agent được tạo sẽ tự động được thêm vào group chat.
-Được phép xem các ticket đang được xử lý.
-Được phép ping đến từng con agent.(Ví dụ: @báo cáo hãy lập báo cáo doanh thu về xử lý các sự cố kỹ thuật trong thời gian 6 tháng trở lại đây)


Với dự án hiện tại, tôi nghiêng về tiếp tục phát triển từ OpenBot, nhưng tái sử dụng có chọn lọc. Phần nghiệp vụ Vinhomes, quyền truy cập và trạng thái công việc phải do sản phẩm của mình kiểm soát; AgentScope đảm nhiệm phần thực thi agent.
Tuy nhiên, sau khi kiểm tra mã nguồn và tài liệu hiện tại, có một điều cần nói rõ hơn so với tư vấn trước: OpenBot không phải nền tảng hoàn chỉnh chỉ cần bổ sung bảng Vinhomes là xong. Có những phụ thuộc và chi phí sửa nền cần kiểm chứng trước khi đầu tư tiếp.
1. Hai hướng thực sự khác nhau ở đâu?
Việc cả hai hướng đều dùng AgentScope không làm chúng tương đương. Agent framework chỉ giải quyết một phần của sản phẩm.
Tiêu chí
Phát triển từ OpenBot
Tự xây platform bằng các thư viện/framework
Giao diện chat, quản lý agent, công cụ
Có nền để sử dụng và sửa
Phải xây, kết nối và kiểm thử
Đăng nhập, credential, lịch chạy, audit
Có các cơ chế để kế thừa
Tự lựa chọn và tích hợp
Nghiệp vụ Vinhomes
Vẫn phải xây
Vẫn phải xây
Điều phối công việc kéo dài, SLA, nghiệm thu
Phải bổ sung và kiểm chứng
Chủ động thiết kế từ đầu
Database
Có schema cũ và chi phí chuyển đổi
Thiết kế gọn theo phạm vi ban đầu
Tự do kiến trúc
Bị ảnh hưởng bởi cấu trúc đã có
Cao hơn, nhưng đội mình chịu toàn bộ quyết định
Bảo trì
Hiểu cả mã kế thừa và mã mình sửa
Hiểu ít mã thừa hơn, nhưng tự chịu trách nhiệm nhiều hơn
Thời gian ban đầu
Có lợi nếu tận dụng được phần lớn nền
Thường tốn công hơn để đạt cùng mức chức năng
Rủi ro chính
Sửa quá sâu khiến lợi ích kế thừa giảm
Đánh giá thấp những chức năng hạ tầng tưởng đơn giản

Tự xây cũng không đồng nghĩa tự viết mọi thứ. Vẫn có thể dùng thư viện auth, UI, hàng đợi, AgentScope, MCP và PostgreSQL.
2. Những bất cập cụ thể nếu dùng OpenBot
Thứ nhất: OpenBot vẫn là nền mẫu ở giai đoạn alpha. Upstream mô tả rõ đây là template để clone và tùy biến, còn thay đổi tích cực. Vì vậy đội mình vẫn phải chịu trách nhiệm kiểm thử, vận hành và xử lý lỗi của sản phẩm cuối. README chính thức
Thứ hai: có phụ thuộc CopilotKit Intelligence. Trong repo hiện tại, [config.ts (line 881)](E:/AI-Workforce-Platform/server/src/config.ts:881) và [intelligence-client.ts](E:/AI-Workforce-Platform/server/src/intelligence-client.ts) cho thấy phần này tham gia trực tiếp vào runtime/hội thoại. Tài liệu chính thức có lựa chọn cloud và self-hosted; self-hosted vẫn có cơ chế license. Vì vậy không thể suy ra “clone mã nguồn về là hoàn toàn độc lập với mọi dịch vụ và điều kiện sử dụng”. Tài liệu Intelligence
Mã OpenBot có giấy phép MIT, cho phép sửa và phân phối theo các điều kiện của giấy phép. Nhưng giấy phép đó không tự đại diện cho mọi dịch vụ phụ thuộc. LICENSE
Thứ ba: trọng tâm sản phẩm chưa trùng hoàn toàn. OpenBot có nhiều chức năng coworker, chat và máy tính/browser cho bot. Dự án của mình tập trung thêm vào:
Phản ánh cư dân và sự cố.
Phân công người thật, lịch hẹn, ca trực.
Chờ vật tư hoặc phê duyệt nhiều giờ/ngày.
SLA, bằng chứng, nghiệm thu và thông báo.
Những phần đó vẫn phải tự xây. Chức năng browser/computer cũng chỉ nên triển khai khi nghiệp vụ cần.
Thứ tư: chi phí duy trì bản tùy biến. Khi sửa sâu auth, channel, registry và runtime, việc nhận bản sửa lỗi từ upstream có thể phát sinh xung đột. Cần ghim phiên bản nền, theo dõi bản sửa lỗi và cập nhật có kiểm thử; không nên mặc định luôn đồng bộ toàn bộ upstream.
3. AgentScope nên tham gia như thế nào?
Có một cập nhật đáng chú ý: tài liệu hiện tại của AgentScope 2.0 đã bao gồm agent service, team orchestration, persistence và nhiều chức năng vận hành. Repo agentscope-runtime cũ thông báo các khả năng của nó đã được tích hợp vào 2.0 và khuyến nghị chuyển sang đó. AgentScope 2.0, thông báo chuyển đổi
Điều này tạo ra nguy cơ mới: nếu lấy toàn bộ OpenBot rồi lấy toàn bộ AgentScope service, mình có thể lại có hai bộ quản lý user, session, tài nguyên và quyền.
Đề xuất của tôi là chọn rõ nơi sở hữu từng loại dữ liệu:
Thành phần
Nơi chịu trách nhiệm
User, tenant, quyền nghiệp vụ
Backend của sản phẩm
Danh tính agent, phiên bản được phát hành
Registry duy nhất của sản phẩm, phát triển từ OpenBot
Hội thoại cư dân
Một hệ thống lưu lịch sử được chọn rõ
Suy luận, phối hợp agent, gọi model
AgentScope
Trạng thái thực thi, checkpoint của framework
AgentScope/runtime, liên kết với workflow của sản phẩm
Sự cố, task, phân công, tiến độ
Module Vinhomes
Quyết định cho phép thay đổi nghiệp vụ
Backend Vinhomes kiểm tra quyền và điều kiện

Một Python service chạy AgentScope trong cùng sản phẩm không có nghĩa có thêm một platform độc lập.
OpenBot có đường kết nối agent từ xa qua AG-UI, nhưng không nên mặc định AgentScope phiên bản mình chọn sẽ tích hợp đầy đủ ngay. Cần kiểm tra streaming, hủy chạy, tiếp tục, tool approval và ánh xạ session. Repo của mình hiện cũng ghi rõ [agent-runtime](E:/AI-Workforce-Platform/agent-runtime/README.md) mới là khung contract, chưa có AgentScope execution.
4. Kiến trúc tôi đề xuất cho dự án

Đây là một sản phẩm. OpenBot là nguồn mã nền, AgentScope là thành phần thực thi, Vinhomes là nghiệp vụ.
Ví dụ, AgentScope có thể điều phối agent kỹ thuật phân tích nguyên nhân. Nhưng việc một kỹ thuật viên đã nhận việc hay một sự cố đã đóng phải được ghi nhận bởi nghiệp vụ Vinhomes. Không lấy câu “đã xong” trong groupchat làm trạng thái chính thức.
Ranh giới này giúp sau này thay AgentScope hoặc bổ sung framework khác mà không phải viết lại database sự cố, phân công và nghiệm thu.
5. Khi nào nên chọn tự xây từ đầu?
Tôi sẽ nghiêng sang tự xây backend/platform gọn hơn nếu xác nhận được các điều kiện sau:
Sản phẩm chủ yếu là màn hình nghiệp vụ; dùng rất ít chức năng có sẵn của OpenBot.
Yêu cầu triển khai không phù hợp với lựa chọn Intelligence hiện có.
Muốn bỏ hoặc thay phần lớn channel, runtime, registry và cơ chế quyền của OpenBot.
Đội ngũ có năng lực vận hành nền tảng và chấp nhận đầu tư ban đầu lớn hơn.
Nếu phải thay gần hết phần nền, lợi ích giữ OpenBot có thể không bù được chi phí hiểu và duy trì mã cũ.
Ngược lại, nếu cần chat, quản lý agent, MCP, credential, skills và công cụ quản trị sớm, tái sử dụng OpenBot có giá trị rõ ràng.
6. Quyết định nên làm ở thời điểm này
Tôi chưa đề xuất bỏ repo để viết lại, cũng chưa đề xuất tiếp tục mở rộng ERD hàng loạt. Nên chứng minh một luồng nhỏ chạy thật trước:
Cư dân báo sự cố → lễ tân → điều phối bằng AgentScope → giao kỹ thuật → cập nhật tiến độ → lễ tân phản hồi.
Luồng đó cần chứng minh được:
Một user/tenant và một danh tính agent xuyên suốt.
Runtime khởi động lại vẫn tiếp tục được công việc.
Thử lại không tạo trùng phân công hoặc thông báo.
Cư dân chỉ đọc được thông tin được phép.
Lịch sử hội thoại và nghiệp vụ có nơi lưu rõ ràng.
Phương án triển khai Intelligence đáp ứng yêu cầu vận hành và chi phí.

Nghiệp vụ hệ thống

1.Đăng kí:
-Cư dân đăng kí tài khoản với số họ tên,số điện thoại,mật khẩu, số căn hộ và quyền người dùng.

-Tài khoản của ban quản lý và nhân viên sẽ được admin cấp (admin sẽ tạo tài khoản trên trang của admin)
-Cư dân và nhân viên đăng kí xong thì cần admin chấp nhận thì mới có quyền vào sử dụng hệ thống.
2.Đăng nhập:
-Người dùng chỉ cần đăng nhập bằng tài khoản của mình thì hệ thống sẽ tự ánh xạ theo role và điều hướng đến đúng trang được phép sử dụng.
** Admin có thể kích hoạt,tạm khóa hoặc xóa hẳn 1 tài khoản **
3.Trang cư dân:
-1 cư dân có thể tạo nhiều cửa sổ chat,mỗi cửa sổ chat sẽ được trao đổi để  giải quyết 1 vấn đề hoặc 1 ticket. (giống như giao diện ChatGPT hiện tại).
-Có thông báo mỗi khi có tin nhắn mới từ reception agent.
-Ở đây là cư dân chat trực tiếp với reception agent.
4.Reception agent (chạy bên trong)t.
-Tiếp nhận ý kiến hoặc câu hỏi từ phía cư dân.
-Trả lời ngay dựa trên kiến thức sẵn cho cho những câu hỏi liên quan đến FAQ,Quy định khu đô thị hay tòa nhà,Các dịch vụ của khu đô thị,...
-Nếu các vấn đề cần đến nhân viên hỗ trợ trục tiếp thì sẽ tạo ticket và ping đến Supervisor agent,khi supervisor agent đã phân tích xong ticket và gửi đến cho subagent thì cần phải có phản hồi ngay cho reception agent rằng đã gửi yêu cầu đến bên nhân viên để reception agent trả lời cư dân.Sau đó Reception agent sẽ tạm dừng bằng interrupt() để đợi trạng thái mới từ nhân viên,khi nhân viên có trạng thái mới sẽ gửi event lên cho reception agent để thông báo đến cho cư dân.
-Có thể trong 1 tin nhắn của người dùng sẽ chứa 2 sự cố hoặc bị mơ hồ thì cần reception xác định rõ xem có cần tách làm 2 ticket để sử lý tuần tự trong 1 cửa sổ chat hay không.

Lưu ý: cần các bảng quản lý ticket chặt chẽ,để dễ cho việc nhân viên cập nhật trạng thái và gửi event đúng ticket .(Mối quan hệ 1 user - n ticket ; 1 ticket - n event)

Nghiệp vụ hệ thống(bản hiện tại
3.Trang cư dân:
-1 cư dân có thể tạo nhiều cửa sổ chat,mỗi cửa sổ chat sẽ được trao đổi để  giải quyết 1 vấn đề hoặc 1 ticket. (giống như giao diện ChatGPT hiện tại).
-Có thông báo mỗi khi có tin nhắn mới từ reception agent.
Có giao diện hiển thị quá trình xử lí như là đang xử lí, cập nhật theo tiến độ như kiểu phần cập nhật giao hàng của shoppe
-Ở đây là cư dân chat trực tiếp với reception agent.
4.Reception agent (chạy bên trong).
input : text + image người dùng
output :
 nghiệp vụ :
-Tiếp nhận ý kiến hoặc câu hỏi từ phía cư dân.
-Trả lời ngay dựa trên kiến thức sẵn cho cho những câu hỏi liên quan đến FAQ,Quy định khu đô thị hay tòa nhà,Các dịch vụ của khu đô thị,...
-Nếu các vấn đề cần đến nhân viên hỗ trợ trục tiếp thì sẽ tạo ticket và ping đến Supervisor agent,khi supervisor agent đã phân tích xong ticket và gửi đến cho subagent thì cần phải có phản hồi ngay cho reception agent rằng đã gửi yêu cầu đến bên nhân viên để reception agent trả lời cư dân, thươngf với 3 trường hợp chính, đã tiếp nhận ticket, đưa phương án cho cư dân để cư dân duyệt, khi phương án đó thực hiện xong.
-Có cơ chế hỏi lại người dungf nếu sự sô thiếu thông tin hoặc chưa rõ ràng

Lưu ý: cần các bảng quản lý ticket chặt chẽ,để dễ cho việc nhân viên cập nhật trạng thái và gửi event đúng ticket .(Mối quan hệ 1 user - n ticket ; 1 ticket - n event)

5.Supervisor agent(Chạy bên trong):
agent điều phối, điều phối các agent con để hoàn thiện 1 task
dùng hàm agent team của agentscope2.0
nguyên lí : Agent điều phối một nhóm agent chuyên môn để hoàn thành một task lớn. Supervisor phân rã task, tạo/assign subtask cho từng agent và theo dõi tiến độ thông qua **shared Task Board**. Các agent có state phối hợp chung của team nhưng vẫn giữ context thực thi riêng. Khi một agent cần thông tin/hỗ trợ từ agent khác, nó có thể **gửi message trực tiếp cho agent đó hoặc broadcast cho team**, không bắt buộc phải thông qua Supervisor. Supervisor chịu trách nhiệm điều phối tổng thể và tổng hợp kết quả cuối cùng.

phần @agent
Khi người dùng @AgentB, hệ thống tự bắt @AgentB, lấy context của room hiện tại gồm các message gần nhất + ticket/task hiện tại + kết quả liên quan, rồi truyền cùng câu hỏi cho AgentB. Có thể tận dụng AgentScope Agent Team ở phần shared Mailbox/Task Board và message routing, nhưng AgentScope không tự hiểu toàn bộ lịch sử room để nhét đúng context cho AgentB; phần chọn đoạn chat nào cần gửi vẫn nên do hệ thống mình làm bằng một Context Builder. AgentB sau đó trả lời lại vào cùng room nên tiếp tục giữ được mạch hội thoại.

factory agent: để tạo agent con
input : text mô tả về agent đó
output : mô tả agent giúp con điều phối hiểu agent con đó làm gì, system prompt, tool (chọn từ bộ tool build sẵn, nối qua MCP), cơ sở tri thức(vectorDB - đang theo 2 hướng mỗi agent 1 vectorDB hoặc vectorDB theo domain)
evaluation agent : tạo test case khoảng 6 cái, chạy agent trong standbox, đánh giá dựa trên code base, và LLM as judge(model thường khác provider với factory agent)
có 1 vòng lặp tự phản biện tự sửa giữa 2 agent cho đến khi pass hoặc đủ số vòng
7: các agent con dự kiến được tạo từ 2 agent trên

7.1: Technical Agent
tool : điều phối kỹ thuật viên, kiểm tra ảnh trước và sau khi sửa
7.2 :Sercurity Agent
tool : điều phối bảo vệ
7.3 : Sanitary agent
tool : điều phối nhân viên vệ sinh, kiểm tra ảnh trước và sau khi vệ sinh
7.4 : accountant agent
tool : kiểm tra nghiệp vụ, bên nào chịu trách nghiệm, đưa ra số tiền dự kiến, nhận số tiền thực tế, quản lí số tiền
Hãy bổ sung thêm tool, làm rõ hơn input và output các tool
Luồng HITL
lễ tân tạo ticket -> điều phối -> tạo phương án (HITL quản lí duyệt) -> lễ tân chốt lại phương án cho người dân (HITL nguời dân duyệt) -> chốt phương án -> điều phối -> chia việc cho agent con làm,
 nếu agent con điều nhân viên -> nhân viên duyệt xác nhận nhận việc -> nhân viên chụp ảnh trước sau hiện trường -> nhân viên duyệt hoàn thành -> lễ tân báo cư dân đã hoàn thành -> cư dân duyệt hoàn thành hoặc không.
phần tạo agent : ban quản lí tạo agent, nếu pass hết hoặc gì đó thì đẩy agent lên admin duyệt
với trường hợp không duyệt thì như nào ??


Reception agent:
-create_ticket_draft :gọi tool tạo ticket
-load_resident_context :lấy tên, điện thoại, căn hộ, tòa và domain.
-resolve_management_destination : filter tài khoản ban quản lý qua domain và tòa nhà để reception agent gửi đúng ban quản lý.


Các tool kỹ thuật:
sop_kb.retrieve — Tra SOP kỹ thuật và tiêu chí nghiệm thu.
asset.read — Đọc hồ sơ tài sản, thiết bị.
sensor.read — Đọc dữ liệu BMS hoặc IoT.
maintenance_history.read — Đọc lịch sử bảo trì và lỗi lặp.
technical.get_active_outage — Kiểm tra sự cố hoặc gián đoạn đang diễn ra.
technical.record_measurement — Ghi số đo kỹ thuật.
technical.submit_executor_result — Nhận kết quả từ kỹ thuật viên.
maintenance_history.append — Ghi kết quả đã xác nhận vào lịch sử bảo trì.
technical.verify_resolution — Kiểm tra checklist, evidence và điều kiện hoàn tất.
utility_isolation.request — Đề nghị khóa van hoặc ngắt điện.
area_restriction.request — Đề nghị rào chắn hoặc hạn chế khu vực.
apartment_entry.request — Xin quyền vào căn hộ vắng chủ.
vendor_dispatch.request — Đề nghị điều động nhà thầu ngoài.

Các tool bảo vệ

Tool cho RAG:
-Reception agent: answer_or_escalate: trả lời bằng kiến thức
Các tool dùng cho Report Agent:


Tool
Chức năng
Kết quả cần trả
get_report_filter_options
Lấy danh sách tòa/phân khu, nhóm sự cố, nhân viên mà BQL được xem.
ID và tên hợp lệ để tạo bộ lọc.
get_employee_performance_summary
Tổng hợp hiệu quả và đánh giá nhân viên.
Số công việc được giao/hoàn thành, tỷ lệ đúng hạn, thời gian xử lý, số việc phải sửa lại, điểm đánh giá trung bình và số lượt đánh giá.
get_employee_feedback_details
Xem chi tiết phản hồi để giải thích kết quả đánh giá.
Điểm, nội dung phản hồi, ngày đánh giá và tham chiếu ticket/công việc; có phân trang.
get_repair_revenue_summary
Tổng hợp doanh thu sửa chữa theo kỳ, tòa, nhóm sự cố hoặc dịch vụ.
Tổng tiền tính phí, số tiền thực thu, số tiền còn phải thu, số công việc có tính phí; phân biệt tiền công và vật tư nếu có dữ liệu.
get_incident_frequency_summary
Thống kê tần suất sự cố theo nhóm điện, nước… và loại chi tiết.
Số ticket, tỷ trọng, xu hướng theo ngày/tuần/tháng, phân bố theo tòa và các loại sự cố thường gặp.
get_report_supporting_records
Truy xuất các bản ghi nguồn đứng sau một chỉ số để kiểm tra.
Danh sách ticket, công việc hoặc giao dịch liên quan; có phân trang và giới hạn trường được xem.
create_report_export
Xuất báo cáo đã tổng hợp thành file.
report_id, job_id, trạng thái tạo file; hỗ trợ định dạng thực tế của hệ thống như DOCX/PDF/XLSX.






get_report_export_status
Kiểm tra kết quả xuất báo cáo.
Trạng thái, lỗi nếu có và đường tải file được kiểm soát quyền.


Tool bổ sung cho việc cư dân gửi ảnh sự cố vào đoạn chat với reception agent cần được lưu ngay tránh tình trạng bị mất ảnh sau khi reception hỏi bổ sung thông tin ticket:


API/tool đề xuất
Bên gọi
Chức năng
initiate_image_upload
Frontend
Backend kiểm tra quyền, loại/kích thước file; tạo file_id và cấp URL upload lên S3/MinIO.
complete_image_upload
Frontend
Backend kiểm tra object đã tồn tại, kích thước/checksum phù hợp; đánh dấu file sẵn sàng. Không chỉ tin thông báo “upload thành công” từ client.
get_conversation_images
Reception/runtime
Lấy các ảnh đã upload và gắn với tin nhắn trong cuộc hội thoại để phục hồi tham chiếu khi cần.
attach_images_to_ticket
Reception qua backend
Liên kết danh sách file_ids với ticket sau khi kiểm tra quyền và trạng thái file. Gọi lại không tạo liên kết trùng.
get_image_read_access
Reception/runtime hoặc giao diện
Cấp quyền đọc ảnh tạm thời khi cần xem hoặc gửi ảnh cho model phân tích.
