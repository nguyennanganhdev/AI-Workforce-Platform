# Kiểm tra và kế hoạch hoàn thiện Agent, Team, MCP, Knowledge cho BQL Ocean Park 2

Ngày kiểm tra: 17/10/2026. Phạm vi tài khoản: `vinhome.op2.bql`, khu `ocean-park-2`.

Cập nhật triển khai: xem [bản sửa và bằng chứng release](OP2_CAPABILITIES_RELEASE_20261017.md). Các số liệu và lỗi trong báo cáo dưới đây là mốc audit trước bản sửa, không phải kết luận rằng lỗi vẫn còn sau deploy.

Chốt bản kỹ thuật: Platform chạy `90ad2c90`, Domain chạy `9dd7504f`; CI 1.580 test đạt. Tài khoản OP2 đã có thêm 12 tài liệu kỹ thuật có nguồn, 8 skill chờ duyệt và catalog 23 tool với 6 tool quản trị chỉ đọc đã kiểm tra trên VPS. Ba agent/nhóm audit hiện hành vẫn draft; không chạy model thật. SOP/biểu phí chính thức, các adapter ghi M03 và business UAT vẫn là phần cần dữ liệu/nghiệm thu, không được coi là đã hoàn tất từ health hay test offline. ID tài nguyên mới và bằng chứng cụ thể nằm trong bản release được liên kết ở trên.

## 1. Kết luận và giới hạn bằng chứng

Hệ thống đã có agent nghiệp vụ, hội thoại cá nhân và nhóm có điều phối, trao đổi ngang hàng, review và tổng hợp. Chưa đủ bằng chứng để kết luận toàn bộ đã hoàn thiện cho vận hành BQL. Điểm thiếu lớn là năng lực quản trị ngoài một ticket, nguồn tri thức được xét duyệt, thư viện skill dùng lại và tính nhất quán khi phát hành tài nguyên.

Đợt này không gửi chat production, không chạy Builder/copilot/evaluation production, không gọi model hoặc embedding thật. Các bài kiểm tra runtime dùng provider giả và Docker `--network none`. Không thay đổi agent/team cũ, không gắn tuyến nghiệp vụ mới, không sửa công việc đang làm của người khác.

Không có phiên trình duyệt khả dụng để thao tác giao diện. Việc tạo mới dùng API cấu hình thủ công của ứng dụng, dưới quyền BQL OP2 đã đối chiếu với cơ sở dữ liệu. Đây là bằng chứng API/cấu hình; chưa phải nghiệm thu thao tác UI hay chất lượng trả lời bằng ngôn ngữ tự nhiên.

Mốc mã nguồn kiểm tra: `develop2@a507b7b0bdb0dae5e7b50afd2f07e2f9222c0b52`. Các bài kiểm tra chạy trên bản trích xuất từ commit này, tránh các file đang có thay đổi chưa commit trong workspace.

| Thành phần | Bản đang chạy lúc kiểm tra |
| --- | --- |
| Platform app | `agentscope-platform:a507b7b0-jev-fix-20261017` |
| Platform web | `agentscope-platform-web:a507b7b0-jev-fix-20261017` |
| Domain API / platform-sync | `vinhomes-domain-api:p0p2-20261016-2b9de30f` |
| Domain database đang dùng | `vinhomes_release_20261015_6884e1b1` |

Image Domain cũ hơn Platform không đồng nghĩa catalog bị thiếu: discovery trực tiếp `/mcp` đã trả HTTP 200 và đủ 17 tool, khớp catalog OP2 đã lưu.

## 2. Những gì đã tạo mới trong OP2

Tạo ba agent **draft v0**, đều không được mời vào tuyến nghiệp vụ. Agent tiếp nhận được dùng cho cả phiên cá nhân và vai trò điều phối của nhóm mới.

| Vai trò | Tên hiển thị | Agent ID |
| --- | --- | --- |
| Tiếp nhận / điều phối | `AUDIT OP2 17-10 - Tiep nhan` | `d2e50b7218414b0ca6bf546b0298847a` |
| Chuyên viên | `AUDIT OP2 17-10 - Chuyen vien` | `6e979f2345ca43878fa25b03746f2425` |
| Rà soát / phản biện | `AUDIT OP2 17-10 - Phan bien` | `7b5a2fbf927c4e778a38ee1b0181864b` |

- [Mở phiên cá nhân mới](https://vagen-platform.duckdns.org/chat/d2e50b7218414b0ca6bf546b0298847a/4d7ccef330d346da99634e014814f080).
- [Mở nhóm xử lý và phản biện mới](https://vagen-platform.duckdns.org/chat/d2e50b7218414b0ca6bf546b0298847a/bc62447f8b1c493887632ff9c6df2fdf).

Spec mới có phạm vi BQL OP2, quy tắc dẫn nguồn/phân biệt đề xuất với dữ liệu đã xác minh, khai báo KB Vinhome và bốn kịch bản kiểm thử chưa chạy. Không gắn MCP ghi dữ liệu hoặc skill không phù hợp. Tắt memory/self-improve cho ba bản nháp audit.

Đã xác minh nhóm được lưu với ba session riêng và điều phối đúng agent tiếp nhận; nhóm chưa có trao đổi. Sổ gọi model của ba agent mới: **0**. Hash bản ghi của các agent có sẵn trước thao tác giữ nguyên.

Thử phát hành ba bản nháp bằng endpoint publish đều nhận **409 yêu cầu kiểm thử bản nháp hiện tại**. Không tạo báo cáo đánh giá giả hoặc dùng quyền provisioning để vượt cổng. Vì yêu cầu cấm model thật, các bản này được giữ là cấu hình nháp, **chưa triển khai nghiệp vụ**. Khi lệnh cấm còn hiệu lực, chỉ tiếp tục kiểm thử bằng fixture/provider giả; không tự chạy đánh giá thật về sau.

## 3. Hiện trạng tổ chức agent/team

Trước khi tạo mới, OP2 có tám agent: sáu agent nghiệp vụ published, một agent nghiệp vụ draft và một Workforce Leader hệ thống. Có 11 team đã lưu: mười team vận hành và một nhóm cá nhân BQL; số team đã lưu không phải số team đang chạy.

| Agent có sẵn | Công cụ khai báo | Đánh giá cấu hình và việc cần hoàn thiện |
| --- | --- | --- |
| Tư vấn nội quy & bàn giao | `vh_knowledge_search`; có KB Platform | Có nền tảng tư vấn tài liệu. Tool Domain yêu cầu ticket nên chưa phục vụ tốt hỏi đáp BQL không có ticket. Cần kiểm chứng nguồn được trích thực tế. |
| Kỹ thuật | `vh_knowledge_search`, `vh_ticket_get`; có KB Platform | Tra cứu theo ticket; chưa được cấp trực tiếp tool điều phối. Cần quy trình chuyển sang điều phối và bằng chứng kết quả. |
| An ninh | `vh_knowledge_search`, `vh_ticket_get`; chưa có KB Platform/skill | Chưa có tài liệu và workflow riêng cho khách, thẻ, sự cố an ninh. |
| Vệ sinh | `vh_knowledge_search`, `vh_ticket_get`; chưa có KB Platform/skill | Chưa có SOP/checklist, định mức và luồng lịch–phân công–nghiệm thu riêng. |
| Báo cáo tình trạng ticket hằng ngày | Chỉ `vh_ticket_get` | Tool đọc một ticket không cung cấp trực tiếp danh sách/phân trang, tổng hợp theo khu, thời gian, SLA. Chưa đủ cơ sở để coi chức năng báo cáo đã hoàn chỉnh. |
| Điều phối | Knowledge, nhân sự, đọc ticket, ghi chú, dispatch, đổi lịch, hủy | Có công cụ điều phối cơ bản; cần kiểm chứng grant/consent/version/idempotency và bàn giao trạng thái cuối. Đợt này không thực hiện lệnh nghiệp vụ. |
| Thống kê báo cáo | Draft v0, không tool/KB/skill | Chưa phát hành nhưng đang là coordinator của nhóm BQL có sẵn. Cần readiness và lựa chọn coordinator minh bạch; không tự thay nhóm này. |
| Workforce Leader | Agent hệ thống | Giữ nhiệm vụ hệ thống, không tự đổi quyền hoặc cấu hình. |

### Hội thoại cá nhân và tài nguyên

Các test offline xác nhận chat cá nhân giữ giới hạn vai trò, không tự giao việc, không đọc hội thoại người khác. Nhóm được cách ly theo owner và room; tạo/xóa nhóm không sửa định nghĩa agent hoặc hội thoại riêng khác.

Đối chiếu dữ liệu ban đầu thấy bốn session cá nhân/nhóm không lưu `knowledge_config` dù AgentSpec khai báo KB. **Không coi đây là lỗi mất RAG:** mã runtime đang chạy có fallback từ AgentSpec khi session chưa khai báo KB. Cần hiển thị tài nguyên có hiệu lực và kiểm thử truy xuất thật bằng embedding giả để tránh kết luận từ cấu hình lưu riêng lẻ. Chưa xác minh retrieval/citation của tất cả agent production.

### Team có thảo luận và phản biện chưa?

Có cơ chế và bằng chứng thực thi offline:

`BQL → điều phối handoff → chuyên viên question → đồng đội answer → chuyên viên result → review → tổng hợp`.

Đã chạy thêm chu trình `result → review(challenge) → result sửa lại → review(accept)` trên Redis giả và SQL SQLite, đều đạt. Một bài runtime chạy agent và dispatcher thật với provider giả xác nhận thành viên trao đổi và coordinator tổng hợp; phần runtime đồng thời trên PostgreSQL chưa chạy trong đợt này.

Điều đó chứng minh engine hỗ trợ cộng tác, chưa chứng minh model thật sẽ luôn chọn đúng người, phản biện đúng nội dung hoặc mọi nhóm hiện tại đều đủ tài nguyên. Không cần ép tất cả thành viên phát biểu với lời chào/câu hỏi đơn giản. Với yêu cầu nhiều chuyên môn hoặc có tác động nghiệp vụ, cần kiểm tra kế hoạch, người chịu trách nhiệm, báo cáo, review và điều kiện kết thúc.

## 4. Lỗi phát hành đã tái hiện: ưu tiên P0

Test offline đi qua route publish thật và chỉ thay bước gắn tài nguyên bằng lỗi 409. Kết quả: API báo thất bại nhưng bản ghi vẫn là **`published`, version 1, invitable true**. Đây là lỗi nhất quán có thể khiến agent được sử dụng khi skill/tool/KB chưa hoàn tất.

Nguyên nhân ở bản kiểm tra: publish lưu phiên bản và trạng thái trước `apply_bindings`; lỗi ở bước sau chưa khôi phục trạng thái trước đó. Không thử gây lỗi này trên production.

Hướng sửa: chuẩn bị/kiểm tra tài nguyên trước khi kích hoạt, giữ phiên bản đang dùng khi bước chuẩn bị lỗi; chỉ chuyển phiên bản mới sang trạng thái dùng được khi tài nguyên của phiên bản đó sẵn sàng. Cần giữ kiểm soát revision và cạnh tranh nhiều worker hiện có, không chỉ đơn giản đổi thứ tự hai lệnh lưu. Có thể dùng trạng thái phát hành chờ và manifest tài nguyên theo version nếu cần, nhưng triển khai tối thiểu theo seam hiện tại.

Nghiệm thu: lỗi MCP bị thu hồi, KB mất quyền, hub skill mất kết nối, lỗi ghi workspace, xung đột revision đều không làm draft mới trở thành invitable, không làm mất tài nguyên của version cũ; retry không tạo version/skill trùng. Test tái hiện hiện tại phải chuyển từ fail sang pass trước release.

## 5. Phân tích MCP Vinhomes

### Năng lực hiện có

Discovery trực tiếp xác nhận **17 tool**, gồm 11 tool khai báo read-only và sáu tool còn lại phải được xử lý như thao tác cần kiểm soát ghi/chấp thuận. Trong 17 tool có bảy tool du lịch **MOCK ONLY**, chưa kết nối nhà cung cấp thật.

| Nhóm | Tool hiện có | Giới hạn |
| --- | --- | --- |
| Ticket và điều phối | `vh_ticket_get`, `vh_staff_available`, `vh_work_order_dispatch`, `vh_operation_get`, `vh_work_order_reschedule`, `vh_ticket_cancel`, `vh_ticket_add_note` | Tập trung xử lý một ticket; không thay thế báo cáo quản trị toàn khu. |
| Tri thức và ngữ cảnh | `vh_knowledge_search`, `vh_service_context`, `vh_amenity_availability` | Service context đọc thẻ, khách, hóa đơn, tiện ích, sửa chữa và yêu cầu dịch vụ theo ticket. Đọc được ngữ cảnh không đồng nghĩa đã thực hiện được toàn bộ giao dịch trong các miền này. |
| Du lịch mô phỏng | `vh_travel_catalog/search/details/availability/prepare/commit/bookings` | Chỉ dùng dữ liệu/provider mock; không quảng bá là booking thật. |

Tất cả 17 tool yêu cầu `ticket_id`; quyền nghiệp vụ còn phải có grant đúng ticket/workflow/tool/TTL. Bootstrap token chỉ phục vụ discovery và luồng cấp grant. Không mở rộng token này thành quyền xem toàn khu để giải quyết nhu cầu BQL.

### Cách mở rộng để xử lý nhiều vấn đề

Chia hai loại quyền theo nghiệp vụ: (1) grant giải quyết một ticket; (2) quyền BQL quản trị theo domain/khu/vai trò và thời hạn. Kết quả truy vấn BQL phải lọc ở server, phân trang, giới hạn khoảng thời gian và có audit. `area_id` trong input không tự cấp quyền.

Tên tool dưới đây là **đề xuất**, chưa được triển khai:

| Ưu tiên | Nhóm vấn đề | Năng lực đề xuất | Điều kiện nghiệm thu |
| --- | --- | --- | --- |
| P1 | Quản lý BQL | `vh_management_ticket_list`, `vh_management_ticket_summary`, `vh_management_sla_report`, `vh_management_workload` | Lọc OP2 theo principal, không lộ khu khác; phân trang; tổng số đối chiếu SQL; thời điểm dữ liệu rõ ràng. |
| P1 | Tra cứu tài liệu không có ticket | `vh_management_knowledge_search` hoặc endpoint KB được phân quyền tương đương | Phân biệt tài liệu BQL/cư dân; áp dụng phạm vi khu/tòa; nguồn, version, trạng thái xét duyệt và ngày hiệu lực đi cùng đoạn trích. |
| P1 | Kỹ thuật/an ninh/vệ sinh | Tra cứu phân loại sự cố/SLA, lịch và năng lực nhân sự, kế hoạch/phân công, bàn giao và nghiệm thu có bằng chứng | Ưu tiên bọc nghiệp vụ Domain đã có thay vì tạo dữ liệu song song; không tự đánh dấu hoàn tất nếu thiếu chứng cứ. |
| P2 | Thẻ và khách | Đọc yêu cầu, chuẩn bị cấp/khóa thẻ hoặc đăng ký khách, xác nhận và xem kết quả | Đúng căn hộ/người có quyền, chấp thuận cụ thể, chống thực hiện lặp. Không đưa danh sách cư dân rộng cho model. |
| P2 | Tiện ích | Availability hiện có; bổ sung prepare/confirm/cancel booking và receipt | Kiểm tra sức chứa/slot ở lúc commit; xung đột lịch trả lỗi rõ; tác vụ có thể đối soát. |
| P2 | Phí/hóa đơn | Tra cứu hóa đơn/hạng mục, hướng dẫn kênh thanh toán và trạng thái đối soát | Phân quyền chủ thể; không tự ghi đã thanh toán; không tự tạo giá/biểu phí. Chỉ tích hợp thanh toán thật khi có hệ thống nguồn. |
| P2 | Sửa chữa/bàn giao/dịch vụ | Danh mục, hồ sơ yêu cầu, tài liệu bắt buộc, chuẩn bị/duyệt/đổi lịch/hủy | Giữ trạng thái/phê duyệt Domain; truy ngược ticket/operation và người chấp thuận. |
| P3 | Du lịch/đối tác ngoài | Giữ mock được đánh dấu; adapter nhà cung cấp chỉ khi có hợp đồng API và cấu hình hợp lệ | Tách môi trường; hết hạn báo giá, thanh toán/hoàn hủy, idempotency, receipt và xử lý thất bại từng bước. |

Không hứa xử lý mọi vấn đề bằng cách tăng số tool. Mỗi loại yêu cầu phải có chuỗi hoàn chỉnh: nhận diện phạm vi → hỏi đủ dữ liệu → tra cứu đúng nguồn → đề xuất → xin chấp thuận khi cần → thực hiện → đối soát → bằng chứng hoặc chuyển người phụ trách.

Tool đọc cần có schema lỗi, pagination và provenance ổn định. Tool ghi cần expected version, idempotency key, quyền cụ thể, thời hạn chấp thuận, operation ID và truy vấn trạng thái. Dùng `prepare/commit` cho giao dịch có chi phí, giữ chỗ hoặc ảnh hưởng bên thứ ba; không ép mọi thao tác ghi chú nhỏ vào hai bước.

## 6. Kế hoạch Knowledge

### Dữ liệu thực tế

- Platform của BQL OP2: một KB `Vinhome`, một document trạng thái `ready`.
- Domain: 384 document, 868 chunk; không có document thiếu chunk; 865 chunk có embedding đã lưu. Chỉ đọc số liệu, không sinh embedding mới.
- **384/384 document Domain có `unverified=true`.** Có nhóm tài liệu tham khảo, SOP tổng hợp và 48 tài liệu travel-mock. Số lượng không thay thế xét duyệt tính đúng và khả năng áp dụng tại OP2.
- Knowledge Platform và Knowledge Domain là hai kho/đường truy cập khác nhau; chưa có bằng chứng toàn bộ corpus Domain hiện xuất hiện trong thư viện KB Platform của BQL.

### Bộ tài liệu ưu tiên

| Đợt | Bộ tài liệu cần có | Người xác nhận nội dung |
| --- | --- | --- |
| K1 | Nội quy OP2, sơ đồ tổ chức/đầu mối theo chức danh, danh mục dịch vụ, giờ tiếp nhận, quy trình tiếp nhận và SLA | BQL và chủ sở hữu quy trình |
| K1 | Checklist kỹ thuật, an ninh, vệ sinh; phân loại khẩn cấp; điều kiện chuyển tuyến; bằng chứng bàn giao/nghiệm thu | Trưởng bộ phận tương ứng |
| K2 | Hướng dẫn thẻ/khách, tiện ích, sửa chữa và bàn giao căn hộ; hồ sơ bắt buộc, thẩm quyền và biểu mẫu | Bộ phận dịch vụ cư dân |
| K2 | Biểu phí đã ban hành, cách đọc hóa đơn, kênh thanh toán chính thức, xử lý khiếu nại/đối soát | Tài chính và BQL |
| K3 | Bộ ca đã ẩn danh có kết quả xác minh, FAQ từ câu hỏi thiếu nguồn, bài học được duyệt | BQL và người quản trị tri thức |

Đợt K1 nên bắt đầu bằng 12–20 tài liệu thật được duyệt, cùng bộ câu hỏi chuẩn tương ứng. Đây là mục tiêu đề xuất, chưa phải tài liệu đã có. Không sinh nội quy, giá, chính sách hoặc đầu mối liên hệ rồi gắn nhãn chính thức.

Mỗi tài liệu cần: ID, tiêu đề, chủ sở hữu, nguồn/file gốc và checksum, version, phạm vi domain/khu/tòa, audience, mức bảo mật, trạng thái draft/review/approved/retired, ngày hiệu lực/hết hiệu lực, ngày xét duyệt, người phê duyệt và tài liệu bị thay thế. Dữ liệu vận hành thay đổi liên tục như ticket/nhân sự/hóa đơn lấy qua tool từ hệ thống nguồn; không sao chép thành tài liệu tĩnh để trả trạng thái hiện tại.

Luồng nhập: giữ file gốc → parse/chunk theo mục → rà soát nội dung và phạm vi → lập chỉ mục → kiểm tra truy xuất/citation → công bố cho agent được cấp quyền. Cập nhật version mới phải thu hồi đoạn cũ đúng cách và có khả năng quay lại. Với tài liệu unverified, trả rõ tính chất tham khảo; các quyết định vận hành cần nguồn đã được duyệt.

Không tải lại toàn bộ 384 tài liệu vào OP2 một cách mù quáng. Ưu tiên lập bảng đối chiếu nguồn, xét duyệt và quyền, sau đó chọn tích hợp tìm kiếm Domain theo quyền BQL hoặc đồng bộ các phiên bản đã duyệt. Tránh hai bản cùng tên không biết bản nào mới hơn.

## 7. Skill và tool dùng lại giữa các agent

OP2 hiện có hai skill thư viện `speedbot`, `openinvest`; các AgentSpec nghiệp vụ có sẵn chưa gắn skill. Không đủ căn cứ coi hai skill này phù hợp Vinhomes.

Builder có thể đóng gói SKILL.md vào workspace của agent. Điều đó chưa đồng nghĩa skill đã trở thành package có version trong thư viện chung để agent sau tìm và tái sử dụng. Skill thư viện lấy từ hub hiện lưu metadata/tham chiếu; mã nguồn còn ghi việc lưu archive bền vững là phần cần hoàn thiện.

Thiết kế đề xuất:

1. Khi tạo agent, cho chọn skill/tool/KB đã được duyệt trong phạm vi tài khoản; hiển thị mô tả và điều kiện dùng. Việc chọn chưa cấp thêm quyền nghiệp vụ.
2. Skill mới sinh ra lưu thành **candidate riêng**, có tác giả, source agent/version, nội dung, checksum, test fixture, tools/permissions cần dùng và license nếu lấy ngoài. Người quản trị xét duyệt rồi công bố phạm vi phù hợp.
3. Lưu archive nội bộ có version; agent pin version đã dùng. Hub mất kết nối không làm agent đã phát hành mất skill. Thu hồi skill và nâng version phải có kiểm soát.
4. Agent sau tìm theo capability/tag và xem yêu cầu tài nguyên; đề xuất dùng lại. Runtime chỉ cài package đã được cấp quyền và kiểm tra dependency. Không tự đọc workspace/hội thoại riêng của agent khác.
5. Tool do agent đề xuất cần manifest schema, tên connector/service sở hữu, quyền, read/write, consent, timeout, version và fixture. Chỉ đưa vào catalog thực thi khi adapter đã triển khai và được kiểm thử. SKILL.md mô tả một thao tác không tự tạo ra API có khả năng thực hiện thao tác đó.

Bộ skill đầu tiên: tiếp nhận/phân loại; tra cứu có dẫn nguồn; báo cáo ticket/SLA; điều phối có chấp thuận; kiểm tra bằng chứng; phản biện phương án; bàn giao/nghiệm thu; bảo vệ dữ liệu. Các skill tham chiếu tool được phép và tài liệu đã duyệt, không nhúng credential hoặc dữ liệu cư dân.

## 8. Backlog triển khai và thứ tự phụ thuộc

| Mã | Ưu tiên | Công việc | Phụ thuộc | Bằng chứng hoàn thành |
| --- | --- | --- | --- | --- |
| A01 | P0 | Sửa publish thất bại vẫn published/invitable | Không | Test fault injection đạt; version cũ giữ nguyên; cạnh tranh/retry an toàn. |
| A02 | P0 | Readiness cho agent/team và coordinator draft | A01 | UI/API phân biệt cấu hình nháp với nhóm sẵn sàng; publish không bị vượt qua từ chat/team. |
| A03 | P0 | Manifest tài nguyên có hiệu lực theo agent/version/session | A01 | Direct/group/ticket cho thấy KB/MCP/skill thực dùng; mất quyền hoặc lỗi tài nguyên được báo rõ. Không kết luận sai từ KB fallback. |
| A04 | P0 | Khóa bộ test cộng tác và cách ly | Không | handoff/question/answer/result/challenge/revise/accept, timeout, giới hạn vòng, khởi động lại; PostgreSQL runtime; không lẫn owner/khu/nhóm. |
| M01 | P1 | Quyền và grant BQL theo khu; API đọc quản trị | A02 | Wrong area/role/expired grant đều bị chặn; bootstrap không dùng để đọc nghiệp vụ. |
| M02 | P1 | Tool danh sách ticket, SLA, workload, báo cáo | M01 | Kết quả khớp fixture/SQL, pagination và số liệu thời gian rõ ràng; agent báo cáo dùng được dữ liệu tổng hợp. |
| K01 | P1 | Inventory, phân loại và xét duyệt K1 | Không | Nguồn thật, người duyệt, version, scope, hiệu lực; không nâng nhãn verified hàng loạt. |
| K02 | P1 | Nối KB được duyệt tới các vai trò và kiểm tra retrieval | A03, K01 | Câu hỏi có nguồn đúng, từ chối ngoài khu, báo thiếu tài liệu; embedding giả cho kiểm thử đợt này. |
| S01 | P1 | Kho package skill bền vững và quyền dùng lại | A01 | Skill không mất khi hub offline; version pinning, candidate/review, revoke, archive validation đạt. |
| T01 | P1 | Gắn SOP và tiêu chí review cho team OP2 | A04, M02, K02 | Có trách nhiệm từng vai trò và trace thảo luận; không biến đề xuất thành trạng thái đã thực hiện. |
| M03 | P2 | Mở rộng workflow kỹ thuật, an ninh, vệ sinh, thẻ, tiện ích, phí | M01, M02, K01 | Mỗi workflow có quyền, consent, retry, receipt và chuyển người xử lý khi thiếu tích hợp. |
| R01 | P2 | UI nghiệm thu, release có rollback và tài liệu vận hành | Các hạng mục liên quan | Build/CI, browser smoke khi có browser, backup/rollback, cấu hình OP2 và trạng thái chưa nghiệm thu rõ ràng. |

Thứ tự nên làm: **A01–A04 → M01/M02 + K01/K02 + S01 → T01 → M03 → R01**. Chỉ cập nhật tài nguyên/nhóm hiện hữu sau khi có danh sách thay đổi cụ thể và test cách ly. Các file đang được người khác sửa không thuộc phạm vi thay đổi của đợt audit này.

## 9. Cổng kiểm thử trong thời gian cấm model thật

| Mức | Cách làm | Kết quả có thể kết luận |
| --- | --- | --- |
| Contract và quyền | Fixture DB, HTTP test, MCP giả, grant sai/đúng/hết hạn | Schema, quyền, version, idempotency đúng ở tình huống đã kiểm tra. |
| Runtime nhiều agent | Provider theo kịch bản, dispatcher thật, network none | Thực thi phối hợp, review, tạm dừng, cách ly và khôi phục có thể hoạt động. |
| Knowledge/skill | Embedding giả, tập tài liệu fixture, archive nội bộ, hub lỗi | Truy xuất đúng nguồn/quyền và cài package đúng version; không cần API model. |
| UI cấu hình | Chọn/tạo/sửa/xem tài nguyên; chặn gửi chat thật | Luồng cấu hình và thông báo readiness; chưa chứng minh chất lượng tư vấn. |
| Nghiệm thu nghiệp vụ | Chủ quy trình kiểm tra tài liệu, quyền, phương án và kết quả fixture | Chấp nhận phạm vi/quy trình. Chất lượng model thật vẫn chưa kiểm chứng khi lệnh cấm còn hiệu lực. |

Kết quả đã chạy: 20 test API/policy/cách ly chat đạt; bài runtime provider giả đạt trên Redis, nhánh đồng thời SQL được skip vì cần PostgreSQL; hai test challenge→sửa→accept đạt; 37 test Studio/publish gate/skill archive có sẵn đạt. Một test fault injection bổ sung **fail đúng lỗi publish nêu ở mục 4**. Lần chạy ban đầu của runtime thiếu import path `utils`; đã chạy lại phần bị ảnh hưởng với đường dẫn tests đúng. Không dùng lỗi import đó để kết luận lỗi sản phẩm.

## 10. Bằng chứng và điểm chưa nghiệm thu

Các artifact riêng tư cục bộ nằm tại `platform_VP/agentscope/.artifacts/op2-capability-audit-20261017/`, được Git ignore: inventory trước thao tác; cấu hình mới và ledger; discovery Domain; số liệu tri thức; xác minh fallback KB trên VPS; log và test fault injection. Inventory có metadata phiên hội thoại nên không công bố hoặc đưa vào commit chung.

Code chính cần chỉnh theo backlog: `_router/_workforce_studio.py`, `_service/_agent_studio.py`, `_router/_personal_chat.py`, `_service/_chat.py`, `_shared_context.py`, `_tool/_team_say.py`, `storage/_model/_skill.py`; phía Domain: `platform_mcp.py`, `platform_access.py`, `platform.py` và các service nghiệp vụ tương ứng. Đây là phạm vi đề xuất, không phải danh sách file đã sửa.

Chưa nghiệm thu: thao tác UI bằng trình duyệt, natural-language chat bằng model thật, truy xuất RAG production từng agent, giao dịch ghi Domain/nhà cung cấp thật, runtime cộng tác đồng thời trên PostgreSQL, cấu hình tuyến đối tác và business UAT. Không dùng health/discovery hoặc test offline để thay thế các mục này.
