# Kiểm tra tính năng cá nhân cho nền tảng Vin

Ngày kiểm tra: 17/10/2026. Nguồn: working tree `dev_Chien`, HEAD `1ec4465d7f2928f9610b02b0126d39b1443f4163`.

Đây là kiểm tra mã nguồn đọc tĩnh, phục vụ kế hoạch triển khai. Chưa xác nhận container đang chạy, chưa gọi model/Discord/MCP nghiệp vụ, chưa nghiệm thu người dùng thật. Không sửa mã nguồn, tài liệu đang có hoặc cấu hình triển khai.

## 1. Kết luận theo mã nguồn

Nền tảng có sẵn phần lớn công cụ cần dùng: chat riêng, nhóm agent cá nhân, Workforce Leader, Builder/AgentSpec, eval, lịch chạy, Discord/DingTalk/Feishu. Tuy nhiên hệ thống vẫn được thiết kế quanh BQL theo khu và ticket từ Reception. Mở giao diện cho cư dân sẽ chưa đủ: cần quyền người dùng cá nhân, danh mục được phê duyệt, liên kết danh tính, grant theo người/ticket, hạn mức, cách đưa yêu cầu trực tiếp thành hồ sơ nghiệp vụ và chính sách chia sẻ dữ liệu.

| Tính năng | Hiện có trong mã nguồn | Khoảng trống với đích đến Vin |
|---|---|---|
| Chat riêng agent | Session cá nhân có context riêng; API chat kiểm tra quyền truy cập agent và trạng thái phát hành. | Cần chính sách người dùng Vin và danh mục agent được dùng; không dùng quyền BQL làm quyền cư dân. |
| Nhóm agent cá nhân | Tạo nhóm 2–20 agent, phân vai điều phối, team engine và Shared Context, không nhập lịch sử chat riêng. | Cần UX cho người dùng phổ thông; tách rõ dữ liệu cá nhân và dữ liệu nghiệp vụ. |
| Workforce Leader | Leader do server sở hữu, được khởi tạo theo người; có API tạo session mới với workspace riêng. | Session mới chưa tự đồng nghĩa với ticket Vinhomes có quyền nghiệp vụ. Cần khâu tiếp nhận trực tiếp từ cư dân và liên kết danh tính. |
| Builder và custom agent | AgentSpec, draft, clone, copilot, tests, version, publish, rollback. | Hiện agent người dùng vẫn mang `system_role=business`; cần phân biệt agent cá nhân với agent vận hành bằng mục đích/phạm vi/quyền, tránh tự cấp quyền nghiệp vụ. |
| Eval sandbox | Đọc MCP được server phân loại an toàn; mô phỏng ghi; báo cáo được gắn hash của spec, kiểm tra an toàn trước phát hành. | Chưa là môi trường nghiệp vụ sandbox độc lập. Chưa chứng minh RAG và nội dung skill hoạt động trong chat thực. |
| Lịch | Cron, timezone, bật/tắt, session lịch sử, stateful/non-stateful. | “Một lần” là cron theo ngày/tháng; thiếu luồng gửi kết quả và sổ lần chạy, recheck grant/quota, chính sách consent, giới hạn lịch. |
| Kênh bên ngoài | Discord, DingTalk, Feishu được đăng ký; CRUD theo chủ kênh, routing theo chat/user. | Thiếu kiểm tra người bấm duyệt, liên kết user bên ngoài với chủ tài khoản Vin, kiểm tra quyền agent khi gắn kênh, mã hóa secret. |
| Admin/BQL | Admin có trang quản trị; BQL có các công cụ agent. | Admin đang bị chuyển hẳn sang AdminPage; cần vào được workspace cá nhân và chuyển phạm vi quản trị rõ ràng. |

## 2. Bằng chứng nguồn

### 2.1 Chat riêng, nhóm cá nhân và Leader

- Chat cá nhân và nhóm đã tồn tại, không phải hạng mục cần xây từ đầu: [`_router/_session.py:291`](../../platform_VP/agentscope/src/agentscope/app/_router/_session.py#L291), [`_router/_session.py:360`](../../platform_VP/agentscope/src/agentscope/app/_router/_session.py#L360).
- API nhóm xác thực quyền với từng agent trước khi ghi; tạo root sau cùng và dọn session/team khi lỗi: [`_router/_personal_chat.py:81`](../../platform_VP/agentscope/src/agentscope/app/_router/_personal_chat.py#L81).
- Khóa context có cả user và root session; membership xác thực chủ sở hữu và roster: [`_personal_chat.py:83`](../../platform_VP/agentscope/src/agentscope/app/_personal_chat.py#L83), [`_personal_chat.py:90`](../../platform_VP/agentscope/src/agentscope/app/_personal_chat.py#L90).
- Kích hoạt nhóm không nhập lịch sử riêng: [`_personal_chat.py:113`](../../platform_VP/agentscope/src/agentscope/app/_personal_chat.py#L113), [`_personal_chat.py:142`](../../platform_VP/agentscope/src/agentscope/app/_personal_chat.py#L142).
- Đường gửi chat có kiểm tra publication/readiness của các agent được chọn: [`_router/_chat.py:155`](../../platform_VP/agentscope/src/agentscope/app/_router/_chat.py#L155).
- Leader theo người, `system_role=leader`, prompt và provenance do server cấp, loại bỏ MCP mặc định: [`_workforce_console.py:2006`](../../platform_VP/agentscope/src/agentscope/app/_router/_workforce_console.py#L2006), [`_workforce_console.py:2034`](../../platform_VP/agentscope/src/agentscope/app/_router/_workforce_console.py#L2034), [`_workforce_console.py:2061`](../../platform_VP/agentscope/src/agentscope/app/_router/_workforce_console.py#L2061).
- API tạo session Leader mới cố ý tạo workspace riêng, tránh nhập vào ticket cũ: [`_workforce_console.py:2091`](../../platform_VP/agentscope/src/agentscope/app/_router/_workforce_console.py#L2091).
- Giao diện Leader còn mô tả Reception, “Tạo session thử” và “Ticket từ khách hàng”: [`leader/index.tsx:36`](../../platform_VP/agentscope/examples/web_ui/frontend/src/pages/workforce/leader/index.tsx#L36), [`leader/index.tsx:117`](../../platform_VP/agentscope/examples/web_ui/frontend/src/pages/workforce/leader/index.tsx#L117), [`leader/index.tsx:128`](../../platform_VP/agentscope/examples/web_ui/frontend/src/pages/workforce/leader/index.tsx#L128).
- Prompt nhóm còn câu “This group is visible to BQL”; phải quyết định và sửa đúng chính sách riêng tư khi mở cho cư dân: [`_personal_chat.py:34`](../../platform_VP/agentscope/src/agentscope/app/_personal_chat.py#L34). Câu prompt này không phải bằng chứng rằng backend hiện cho BQL đọc mọi nhóm.

### 2.2 Builder, AgentSpec và phát hành

- AgentSpec đã chứa scope, rules, tools, knowledge, skills, tests, model tier, memory và self-improve: [`_agent_spec.py:90`](../../platform_VP/agentscope/src/agentscope/app/_agent_spec.py#L90).
- Tạo custom agent hiện cố định `system_role=business`, trạng thái draft, ban đầu không mời được vào team: [`_workforce_studio.py:241`](../../platform_VP/agentscope/src/agentscope/app/_router/_workforce_studio.py#L241).
- Studio chỉ sửa agent do chính user sở hữu, source=user và role=business: [`_workforce_studio.py:214`](../../platform_VP/agentscope/src/agentscope/app/_router/_workforce_studio.py#L214).
- Công bố phiên bản tạo bản sao record, chuẩn bị tài nguyên ở workspace mới rồi CAS lưu agent. Đây là cải thiện so với lỗi công bố trước khi cài skill trong ghi chú lịch sử: [`_workforce_studio.py:636`](../../platform_VP/agentscope/src/agentscope/app/_router/_workforce_studio.py#L636).
- `apply_bindings` chuẩn bị MCP/skill/knowledge; kiểm tra lại catalog tool, không cho draft bỏ consent server, xác thực KB hiện có: [`_agent_studio.py:208`](../../platform_VP/agentscope/src/agentscope/app/_service/_agent_studio.py#L208), [`_agent_studio.py:260`](../../platform_VP/agentscope/src/agentscope/app/_service/_agent_studio.py#L260), [`_agent_studio.py:287`](../../platform_VP/agentscope/src/agentscope/app/_service/_agent_studio.py#L287).
- Builder chuẩn bị tài nguyên trước, claim proposal, sau đó lưu các agent tuần tự: [`_workforce_console.py:1863`](../../platform_VP/agentscope/src/agentscope/app/_router/_workforce_console.py#L1863), [`_workforce_console.py:1882`](../../platform_VP/agentscope/src/agentscope/app/_router/_workforce_console.py#L1882), [`_workforce_console.py:1901`](../../platform_VP/agentscope/src/agentscope/app/_router/_workforce_console.py#L1901). Cần kiểm chứng lỗi tại agent thứ N và retry sau claim; không khẳng định toàn bộ batch đã atomic.
- Catalog Builder và binding còn đọc storage theo user (`list_mcps`, `list_skills`, `list_knowledge_bases`). Shared credential/agent/KB đã có ResourceAccessService, nhưng cần đưa quyền “xem và dùng catalog đã duyệt” xuyên suốt Builder, publish, clone, runtime, eval: [`_agent_studio.py:319`](../../platform_VP/agentscope/src/agentscope/app/_service/_agent_studio.py#L319), [`_agent_studio.py:348`](../../platform_VP/agentscope/src/agentscope/app/_service/_agent_studio.py#L348), [`_service/_access.py:194`](../../platform_VP/agentscope/src/agentscope/app/_service/_access.py#L194).

### 2.3 Eval

- Cổng phát hành hiện là ít nhất 3 ca, đạt 80%, có ca an toàn bắt buộc; lỗi môi trường/model vẫn chặn phát hành cho tới khi có báo cáo sạch: [`_publish_gate.py:13`](../../platform_VP/agentscope/src/agentscope/app/_service/_publish_gate.py#L13), [`_publish_gate.py:23`](../../platform_VP/agentscope/src/agentscope/app/_service/_publish_gate.py#L23).
- Công bố phải dùng đúng hash spec và báo cáo đã seal, không nhận một cờ passed tùy ý: [`_publish_gate.py:59`](../../platform_VP/agentscope/src/agentscope/app/_service/_publish_gate.py#L59), [`_publish_gate.py:67`](../../platform_VP/agentscope/src/agentscope/app/_service/_publish_gate.py#L67).
- Eval chỉ thực thi read đã được catalog server cho phép; tool ghi/consent chỉ mô phỏng: [`_agent_eval.py:208`](../../platform_VP/agentscope/src/agentscope/app/_service/_agent_eval.py#L208), [`_agent_eval.py:227`](../../platform_VP/agentscope/src/agentscope/app/_service/_agent_eval.py#L227).
- Report xác nhận `environment.mode=catalog_reads_simulated_writes` và `isolated_business_sandbox=False`: [`_agent_eval.py:475`](../../platform_VP/agentscope/src/agentscope/app/_service/_agent_eval.py#L475).
- Tool runner kiểm tra catalog hiện tại và descriptor tool trước khi chạy read; điều này vẫn không thay thế grant theo người/ticket: [`_agent_studio.py:371`](../../platform_VP/agentscope/src/agentscope/app/_service/_agent_studio.py#L371).

### 2.4 Lịch chạy

- Tạo lịch kiểm tra agent và credential có nhìn thấy được, nhưng đoạn này không áp cổng publication riêng hoặc giới hạn permission theo người dùng: [`_router/_schedule.py:97`](../../platform_VP/agentscope/src/agentscope/app/_router/_schedule.py#L97).
- Schema nhận cron và PermissionMode đầy đủ, mặc định DONT_ASK: [`_schema/_schedule.py:20`](../../platform_VP/agentscope/src/agentscope/app/_router/_schema/_schedule.py#L20), [`_schema/_schedule.py:48`](../../platform_VP/agentscope/src/agentscope/app/_router/_schema/_schedule.py#L48). BYPASS bỏ qua ASK/safety theo thiết kế engine, nên phải cấm ở API đối với user nghiệp vụ: [`permission/_engine.py:395`](../../platform_VP/agentscope/src/agentscope/permission/_engine.py#L395).
- Scheduler dùng quyền chủ lịch và tạo session hoặc dùng lại session stateful: [`_scheduler_manager.py:197`](../../platform_VP/agentscope/src/agentscope/app/_manager/_scheduler/_scheduler_manager.py#L197).
- Chế độ “once” sinh cron theo ngày/tháng, không kèm năm: [`create-schedule-dialog.tsx:156`](../../platform_VP/agentscope/examples/web_ui/frontend/src/pages/schedule/create-schedule-dialog.tsx#L156).
- UI có endDate nhưng payload tạo lịch không gửi endDate; schema API tạo cũng không có ended_at. Storage có ended_at và scheduler nội bộ có dùng nó: [`create-schedule-dialog.tsx:163`](../../platform_VP/agentscope/examples/web_ui/frontend/src/pages/schedule/create-schedule-dialog.tsx#L163), [`_model/_schedule.py:72`](../../platform_VP/agentscope/src/agentscope/app/storage/_model/_schedule.py#L72), [`_scheduler_manager.py:399`](../../platform_VP/agentscope/src/agentscope/app/_manager/_scheduler/_scheduler_manager.py#L399).
- Đã có danh sách session lịch sử và link mở chat; không nên ghi “không có nơi xem kết quả”: [`_router/_schedule.py:245`](../../platform_VP/agentscope/src/agentscope/app/_router/_schedule.py#L245), [`schedule-detail-drawer.tsx:171`](../../platform_VP/agentscope/examples/web_ui/frontend/src/pages/schedule/schedule-detail-drawer.tsx#L171).

### 2.5 Discord và kênh khác

- Main đăng ký Discord/DingTalk/Feishu: [`main.py:284`](../../platform_VP/agentscope/examples/agent_service/main.py#L284). Chưa có bằng chứng từ kiểm tra này rằng các kênh khác như Zalo/Teams/Slack đã được triển khai.
- Tạo kênh hiện kiểm tra bot duy nhất rồi lưu cấu hình routing; chưa thấy kiểm tra quyền agent hoặc readiness trong đường tạo này: [`_service/_channel.py:69`](../../platform_VP/agentscope/src/agentscope/app/_service/_channel.py#L69).
- UI lấy agent từ `useAgents` chung, chưa lọc published trong dialog: [`create-channel-dialog.tsx:35`](../../platform_VP/agentscope/examples/web_ui/frontend/src/pages/channel/create-channel-dialog.tsx#L35), [`edit-channel-dialog.tsx:35`](../../platform_VP/agentscope/examples/web_ui/frontend/src/pages/channel/edit-channel-dialog.tsx#L35).
- Duyệt tool truyền user chủ kênh, agent/session/tool_call và approved, không truyền danh tính người bấm để kiểm tra quyền: [`_gateway.py:171`](../../platform_VP/agentscope/src/agentscope/app/channel/_gateway.py#L171). Resume chỉ kiểm tra tool đang ASKING: [`_decision.py:80`](../../platform_VP/agentscope/src/agentscope/app/channel/_decision.py#L80).
- Secret kênh được che ở API nhưng mô hình ghi rõ mã hóa at-rest vẫn là future hook: [`_model/_channel.py:162`](../../platform_VP/agentscope/src/agentscope/app/storage/_model/_channel.py#L162).
- Mặc định scope là per_chat, nhóm người dùng có thể chung session; per_chat_user chỉ tách session, không xác thực danh tính Vin: [`_model/_channel.py:22`](../../platform_VP/agentscope/src/agentscope/app/storage/_model/_channel.py#L22), [`_routing.py:61`](../../platform_VP/agentscope/src/agentscope/app/channel/_routing.py#L61).

### 2.6 Giao diện và vai trò

- Route công cụ có sẵn trong shell: [`App.tsx:63`](../../platform_VP/agentscope/examples/web_ui/frontend/src/App.tsx#L63).
- Admin được đưa thẳng vào AdminPage, không vào RouterProvider của workspace: [`App.tsx:142`](../../platform_VP/agentscope/examples/web_ui/frontend/src/App.tsx#L142).
- Menu thường hiện đầy đủ credential/MCP/skill/knowledge: [`SettingsSidebar.tsx:47`](../../platform_VP/agentscope/examples/web_ui/frontend/src/components/layout/SettingsSidebar.tsx#L47), [`AppSidebar.tsx:150`](../../platform_VP/agentscope/examples/web_ui/frontend/src/components/layout/AppSidebar.tsx#L150).
- AuthService hiện chỉ khai báo PLATFORM_ADMIN, DOMAIN_ADMIN, AREA_MANAGER; đăng ký mới là AREA_MANAGER: [`auth/_service.py:53`](../../platform_VP/agentscope/src/agentscope/app/auth/_service.py#L53), [`auth/_service.py:298`](../../platform_VP/agentscope/src/agentscope/app/auth/_service.py#L298).

## 3. Phụ thuộc và điều kiện nghiệm thu đưa vào kế hoạch hai phần

### Phần nền tảng và tích hợp nghiệp vụ

1. Bổ sung identity người dùng Vin độc lập với domain/khu BQL; một tài khoản có thể vừa là cá nhân vừa có membership vận hành. Giữ phạm vi quản trị hiện có.
2. Tạo catalog được phê duyệt cho provider/skill/MCP, gồm quyền xem/use, model tier, scope đối tượng; không sao chép key vào credential cá nhân. Kiểm tra quyền tại mọi entry point và thời điểm thực thi.
3. Liên kết Vinhomes theo consent; tạo principal + quyền theo cư dân, không dùng external_user_id do trình duyệt tự khai. Với ghi nghiệp vụ phải có operation scope, ticket grant và consent đúng người.
4. Cần định nghĩa luồng intake trực tiếp: cư dân chọn Vinhomes, Leader tiếp nhận, domain tạo ticket thật bằng identity đã liên kết, lưu mapping request/session/ticket/idempotency. Session thử hiện có không thay cho luồng này.
5. Quota ngày/tháng và concurrency dùng chung cho chat, team, Builder, judge/eval, lịch, kênh và các tác vụ nền. Reserve trước khi chạy, settle usage thực, xử lý model timeout/stream đứt; thu hồi membership hoặc hết quota phải chặn cả job đã tạo.
6. Giữ BQL/admin và tuyến vận hành trong giai đoạn chuyển đổi; bỏ Reception khỏi hành trình cư dân sau pilot và UAT đầy đủ, không tắt tuyến ticket đang chạy hoặc khả năng can thiệp vận hành sớm.

### Phần trải nghiệm cá nhân và độ ổn định

1. Workspace cá nhân dùng Leader, direct chat và nhóm đang có; UX thông báo rõ nhóm là phạm vi chia sẻ giữa các agent của chính người đó. Các câu “visible to BQL”, “session thử”, “Reception gửi ticket” cần được thay theo đúng nghiệp vụ mới.
2. Agent cá nhân luôn private mặc định; tạo/clone/chỉnh không thay system policy hoặc grant. Lưu purpose, owner, visibility và version để không đưa nhầm agent cá nhân vào tuyến vận hành. Không cần tạo một engine agent khác.
3. Tách “lưu draft”, “thử trong môi trường cô lập”, “kích hoạt để dùng riêng”, “đề nghị vào catalog tổ chức”. Việc vào catalog hoặc tuyến vận hành cần phê duyệt và kiểm thử nghiệp vụ. Quy tắc activation riêng cần được chốt thay vì nới cổng publish hiện có cho mọi agent.
4. Hoàn thiện sandbox có fixtures theo run, dữ liệu riêng, sandbox grant và endpoint do admin đánh dấu; eval không bao giờ cho user tự khai host production là sandbox. Ghi rõ mode của từng tool. Nghiệm thu KB/skill phải có chat với retrieval/citation và nội dung skill thật.
5. Kiểm tra thất bại publish: skill hub lỗi, catalog bị thu hồi, CAS thua, process chết sau claim hoặc sau agent thứ N. Giữ bản đang chạy, retry idempotent, dọn workspace staging; xác nhận batch Builder có kết quả cuối cùng nhất quán.
6. Hoàn thiện lịch một lần thật, timezone, end date, ledger lần chạy, lỗi/misfire/retry/dedup và nơi nhận kết quả. Chỉ cho agent hợp lệ, kiểm tra lại quota/grant tại fire, không chạy nghiệp vụ cần consent bằng BYPASS. Có trạng thái chờ xác nhận nếu không có người trực.
7. Kênh cá nhân mặc định chỉ DM/người đã liên kết; identity bên ngoài phải map tới tài khoản Vin. Guild/channel công cộng không mang dữ liệu riêng. Chỉ chủ yêu cầu hoặc người có grant cụ thể được duyệt tool; kiểm tra chat/session/owner và payload tại server. Mã hóa bot token, rotate/revoke, không lộ trong API/log/export.
8. Cho admin chuyển giữa workspace cá nhân và vùng quản trị. Dùng capability ở frontend để hiển thị catalog read-only; backend vẫn trả 403 khi thử POST/PATCH/DELETE credential/skill/MCP không được phép.

### Bộ nghiệm thu tối thiểu

| Ca | Kết quả bắt buộc |
|---|---|
| Hai cư dân khác nhau cùng tạo agent/KB/nhóm | Không đọc chéo session, memory, group context, file, KB hoặc phiếu nghiệp vụ. |
| Cư dân xem catalog chung và chọn vào agent | Dùng được nguồn đã phê duyệt, không thấy key và không sửa bản ghi nguồn. |
| Catalog/consent/membership bị thu hồi sau khi tạo agent/lịch/kênh | Run kế tiếp bị chặn đúng lý do; không dùng bản sao quyền cũ. |
| Cư dân tạo ticket trực tiếp từ Leader | Ticket domain thuộc chính cư dân; retry không tạo đôi; trạng thái và kết quả trở lại cùng hồ sơ. |
| Cư dân chat riêng rồi tạo nhóm | Nhóm không nhận lịch sử riêng; chỉ nội dung chủ động chia sẻ xuất hiện trong Shared Context. |
| Eval chạy read/write sandbox | Có fixtures và grant thật của sandbox; report tách rõ mô phỏng và thực thi, production không đổi. |
| Publish lỗi cài skill hoặc lỗi tại agent thứ N | Agent đang chạy không đổi; kết quả batch rõ ràng, retry không tạo agent trùng. |
| Lịch một lần qua năm sau, quota hết, grant thu hồi | Không lặp hằng năm; không vượt quota; không gọi domain bằng quyền cũ. |
| Discord người B bấm duyệt yêu cầu người A | Bị từ chối; A chỉ duyệt được đúng payload, không duyệt lại sau khi đổi dữ liệu. |
| Discord nhóm công cộng | Không trả dữ liệu riêng/ticket riêng vào phòng; chuyển xác nhận và kết quả nhạy cảm về kênh đã xác thực. |
| Admin/BQL đăng nhập sau migration | Dùng được công cụ cá nhân và nhiệm vụ quản trị theo phạm vi; dữ liệu và ticket cũ giữ nguyên. |

## 4. Nội dung cần kế thừa và thay thế từ kế hoạch cũ

Đã đọc `KE_HOACH_BUILDER_EVAL_CHANNEL_LICH_2026-10-17.md` đầu phiên. Tài liệu đó tự xác định snapshot `develop2@c0ad625c`; không được xem là trạng thái hiện tại của `dev_Chien@1ec4465d`. Khi kiểm tra cuối phiên file này không còn tại đường dẫn ban đầu, nên không giữ liên kết tới file thiếu và không tự khôi phục WIP.

- Giữ các yêu cầu sandbox ticket/fixtures/grant, ghi rõ simulated vs real, bảo vệ consent, công bố agent hợp lệ trước gắn kênh/lịch, mã hóa token, giới hạn người duyệt và lịch một lần thật.
- Không khôi phục JEV hoặc đề xuất deploy lại `c0ad625c`: đường Builder hiện tại không còn JEV. Các bước B0–B2 cũ phải được thay bằng phạm vi Builder hiện tại đã kiểm tra.
- Không khẳng định publish vẫn mắc đúng lỗi lưu published trước cài skill: Studio hiện đã staging + CAS. Cần nghiệm thu lại và kiểm chứng publish nhiều agent, thay vì bê nguyên lỗi lịch sử.
- Sửa mô tả “không có nơi xem kết quả lịch” vì hiện có lịch sử session; khoảng trống còn lại là delivery, trạng thái lần chạy và vận hành job.
- Mở Discord cho cư dân là mục tiêu đã được người dùng xác nhận. Không giữ hạn chế “chỉ BQL/nhân viên” làm phạm vi cuối; phải triển khai liên kết danh tính, bảo vệ dữ liệu và duyệt tool trước nghiệm thu cư dân.
- Ngưỡng eval 5 ca/80% trong tài liệu cũ là đề xuất, chưa là cấu hình HEAD. Kế hoạch mới phải chọn chính sách rõ theo personal activation và organizational publication; mọi ca an toàn bắt buộc vẫn phải đạt.
