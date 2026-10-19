# Phần 2/2 giao Người 2 — Runtime agent, giao diện, tự động hóa và chuyển đổi

Hoàn thiện ngày 18/10/2026 theo giờ Việt Nam, dựa trên rà soát source bắt đầu 17/10. Trạng thái: **kế hoạch đề xuất**, chưa triển khai hoặc nghiệm thu production.

Tài liệu giao **Người 2** mở các tính năng và giao diện Platform hiện có cho khách hàng, bổ sung runtime/quyền riêng cần thiết và đóng gói release Platform. [Người 1 làm Phần 1](KE_HOACH_VIN_PLATFORM_PHAN_1_NEN_TANG_VA_TICH_HOP_2026-10-18.md): IAM/access, catalog/secret/quota/Knowledge, toàn bộ Domain, storage/migration và authority/projection backend. Hai người triển khai song song trên branch/worktree riêng từ `dev_Chien`, dùng C01–C10 và bảng file owner ở Phần 1.

## 0. Phạm vi Người 2 và điều kiện bắt đầu song song

### 0.0. Chốt lại phạm vi UI theo chủ dự án ngày 18/10

**Giữ giao diện Platform hiện có. Khách hàng đăng nhập cùng ứng dụng, sử dụng cùng các trang/tính năng với dữ liệu riêng. Đây là mở quyền sử dụng Platform cho khách hàng, không phải dự án thiết kế lại UI cư dân.** Quyền sở hữu file frontend trong phân công chỉ nhằm tránh conflict, không cho phép viết lại toàn bộ frontend.

- Giữ shell, sidebar, bố cục, route và component đang có cho Leader, chat riêng/nhóm, Agents/Studio, Builder/eval, Knowledge, Lịch, Kênh, Provider, MCP và Skill. Không tạo portal/dashboard cư dân, shell theo role hoặc bộ màn hình tương đương thứ hai. Không đổi hệ điều hướng hoặc kiểu hiển thị sidebar chỉ để phân biệt cư dân với BQL.
- Trên các trang hiện có, lấy principal/quyền từ server, tải dữ liệu của đúng chủ, và áp dụng chế độ đọc/sửa theo quyền. Khách hàng có đủ tính năng sử dụng cá nhân; catalog Provider/MCP/Skill đã cấu hình sẵn vẫn xem/chọn/dùng được theo entitlement, còn thao tác sửa cấu hình quản trị bị chặn cả UI và API. Không biến giới hạn sửa thành ẩn hoặc cấm luôn trang catalog đối với khách hàng được cấp quyền đọc.
- Khách hàng tự tạo/custom/build agent trong không gian của mình; session/team/memory/KB/lịch/kênh riêng. BQL/admin tiếp tục dùng các trang hiện có theo quyền, không trộn dữ liệu với khách hàng. Staff giữ ứng dụng Domain.
- Chỉ bổ sung phần giao diện còn thiếu để hoàn thành nghiệp vụ: đăng ký cá nhân, liên kết Domain, thông tin hạn mức, quyền đọc catalog, tiến độ và xác nhận của chính khách hàng. Ưu tiên ghép vào màn hình/menu tài khoản/tab/drawer đang có; thay đổi nhỏ phải chỉ rõ API và nhu cầu còn thiếu. Danh sách tính năng ở mục 2 không phải danh sách màn hình/menu mới phải xây.
- Scope workspace ở server và cách ly dữ liệu vẫn bắt buộc. Bộ chọn workspace mới, thanh điều hướng mới hoặc thiết kế lại trang chủ không phải điều kiện để mở tính năng cá nhân cho khách hàng. Nếu cần chuyển scope của BQL/admin, tích hợp tối thiểu vào menu hiện có.
- Với code đã làm: giữ các phần auth/capability, resolver không seed key, ACL/cách ly dữ liệu và test đúng yêu cầu; rà lại riêng các thay đổi layout/navigation và các chỗ chặn nhầm tính năng của khách hàng. Không rollback hàng loạt hoặc coi việc sửa tài liệu này là code UI đã được sửa.

Nghiệm thu UI: đăng nhập BQL và khách hàng trên cùng bản build, đi qua cùng các trang hiện có; khách hàng tạo và dùng agent/Builder/eval/Knowledge/Lịch/Kênh riêng, xem/chọn catalog chỉ đọc, không thấy dữ liệu BQL hoặc người khác. BQL/admin vẫn thao tác như trước. Không dùng key model thật để test nếu chưa được chủ dự án cho phép rõ ràng.

### 0.1. Baseline phải dùng

- Nhánh nguồn `dev_Chien`, baseline `fe56707a966864ec7915be30421762d30cba4d15` (= `develop2` sau PR #99, cập nhật 18/10; rà soát ban đầu ở `1ec4465d`). Branch đã tách từ `1ec4465d` phải rebase lên mốc này trước PR đầu tiên. Không dùng `develop2@c0ad625c` hoặc nội dung JEV cũ làm spec triển khai.
- PR #99 đã có: eval chạy thật trên sandbox Vinhome với ticket mẫu và grant cho từng ca, cổng phát hành ≥5 ca/≥80%/100% ca an toàn, lịch `once`/`ended_at`/gửi vào kênh/lần chạy gần nhất/không BYPASS, chỉ gắn Leader hoặc agent đã phát hành vào lịch và kênh, Discord có người duyệt và token mã hóa. Hướng dẫn: `P/docs/workforce/HUONG_DAN_EVAL_SANDBOX_DISCORD_LICH.md`. N2-05/06/07 mở rộng các phần này cho người dùng thường, không làm lại.
- Chủ dự án đã xóa JEV. Lịch sử hiện có `d6693197` gỡ tích hợp, `c50f8abe` ghi nhận; giữ Builder model chat → duyệt dàn ý → AgentSpec/tests → eval → publish và regression ngăn proposal legacy quay lại.
- Đã có chat riêng/nhóm/Leader, staging + CAS publish và session history của lịch. Bổ sung quyền, isolation, readiness, delivery và vận hành theo khoảng thiếu; không xây lại các khả năng đã có.
- Đây là tài liệu triển khai dựa source, chưa chạy lại app/tests/live trong lần lập kế hoạch này. Không dùng báo cáo image cũ làm bằng chứng production hiện tại.

### 0.2. File/module Người 2 được sửa

Quy ước `P = platform_VP/agentscope`, `A = P/src/agentscope/app`. Các đường dưới đây chỉ định owner; không phải yêu cầu thay mọi file.

| Phạm vi | File/module Người 2 sở hữu | Contract từ Người 1 |
| --- | --- | --- |
| Platform frontend hiện có | `P/examples/web_ui/frontend/**`, frontend package/scripts/tests; `P/examples/web_ui/pnpm-lock.yaml`; chỉ sửa phần cần để mở tính năng và phân quyền theo mục 0.0 | C01–C10; UI dùng DTO thật hoặc fixture cùng schema; không làm lại UI cư dân. |
| Leader/chat/agent | `A/_router/_workforce_console.py`, `_chat.py`, `_agent.py`, `_session.py`, `_personal_chat.py`, `_workspace.py`; `A/_service/_chat.py`, `A/_personal_chat.py` | Principal/subject, provider quota gate, resource resolver, case binding và grant. |
| Builder/Studio | `_workforce_console.py`, `_workforce_studio.py`, `A/_agent_spec.py`; agent readiness/bindings/publish/eval/progress services | C02/C03/C08 và storage/CAS do Người 1 triển khai. |
| Team/runtime/memory | Team/collaboration middleware; `_service/_toolkit.py`, `_workspace.py`, `_session.py`, `_session_projection.py`, `_mcp_render.py`; unified `_case.py`, `_runner.py`, `_readiness.py`, `_quality.py`, `_recovery.py`, `_close.py`, `_approvals.py` | Case projection/authority/consent/grant từ Người 1; session projection là consumer, quyền và provenance lấy từ contract. |
| Lịch/kênh | Router + request schemas schedule/channel; scheduler manager/tools; `A/channel/**`, `_service/_channel.py`, `_credential_binding.py` | Secret/identity, quota, persistent run/lease/delivery và migration C09. |
| Release Platform | Platform Compose/Dockerfile/deploy/scripts đóng gói/runbook | Migration order/config/flags và Domain readiness từ Người 1. |

Người 2 **không sửa** auth/access/catalog services, provider/model gateway/adapters, Knowledge backend, `_service/_management_mcp.py`/`_skill_packages.py`, toàn bộ storage/migration, contracts/foundation, `_app.py`/`_lifespan.py`/`deps.py`, router/service exports, entrypoint, Python dependency/test config chung, `.github/workflows/**`, unified composition/grants/setup/tables/provider/contract/secrets/team_routes, public orchestration router, `_workforce_insights.py`, hoặc `vinhome_Recident/**`. Gửi delta cho Người 1 thực hiện. Đây là ranh giới phối hợp, không phải yêu cầu xin phép người dùng cho từng sửa đổi.

### 0.3. Những bước bàn giao không được bỏ

1. Cùng Người 1 chốt C01–C10 và file owners ở S0; schema/fixture phải import được. Tích hợp API clients, quyền vào UI hiện có và runtime consumer bằng fixture có nhãn; không chờ toàn bộ backend xong.
2. Khi resolver C02/C03 import được, ưu tiên PR nhỏ thay `_platform_credential`/`_model_config` và console/studio call sites. Đây là slice sớm của N2-02, giao để Người 1 nghiệm thu N1-03; **không đợi N2-02 hoàn tất KB/agent/eval**. Không có vòng chờ N1-03 ↔ toàn bộ N2-02.
3. `_workforce_studio.py` đang import `_model_config` từ console; sửa coherently. Thay test cũ đang yêu cầu key Platform được persist trong credential của BQL thành không có key user-owned, resolve đúng alias và deny khi thiếu policy/provider. Không giữ assertion cũ chỉ để test xanh.
4. Chuyển owned-only readiness/bindings sang resolver Người 1; không viết policy ACL riêng trong Builder. Gate cả workspace/upload/copy/import endpoints để user thường không thêm MCP/skill/code vượt catalog.
5. Đề xuất fields/state/storage methods cho purpose/version/schedule/channel trước khi code consumer; Người 1 làm adapters/migration, Người 2 viết runtime/consumer tests. Hai người không cùng sửa `storage/_base.py` hoặc migration head.
6. Handoff hằng ngày có commit, schema version, exports/test, lỗi và việc chờ. Consumer dùng contract thật phải bỏ đường fallback fake khỏi production trước gate; mock/offline pass không mở feature flag phục vụ cư dân.

## 1. Phạm vi giao sản phẩm

### 1.1. Người dùng thường phải làm được gì?

Một cư dân Vinhomes đăng ký Platform, liên kết danh tính Vinhomes, dùng được Leader ngay mà không phải build agent trước. Cư dân vẫn được tự tạo agent riêng để xử lý công việc cá nhân, gắn tài liệu cá nhân, chọn nguồn tri thức Vin được cấp, eval trong sandbox và đặt lịch. Khi có vấn đề Vinhomes, cư dân gửi yêu cầu trực tiếp cho Leader/team agent của chính mình, xác nhận dữ liệu cần thiết và theo dõi xử lý tại Platform; yêu cầu không đi qua BQL. Discord là kênh thêm qua bot riêng của chính user đó, không phải đường được bỏ qua login/consent/quota.

Trong tương lai, cùng tài khoản có thể liên kết nhiều domain và có membership nhân viên để dùng AI cá nhân. BQL, Domain admin và Platform admin tiếp tục làm nghiệp vụ/quản trị theo quyền, đồng thời có không gian AI cá nhân. **Staff vẫn nhận và thực hiện công việc tại ứng dụng Domain như hiện tại; không cần chuyển sang Platform để làm việc.** Khả năng AI cá nhân tương lai của nhân viên độc lập với tài khoản/workflow staff trên Domain. Đối tượng người dùng thay đổi theo capability, không tạo nhiều bản frontend tách rời hoặc gắn mọi user vào role BQL.

Luồng phân công đã chốt: **Khách hàng trên Platform → Leader/team agent → MCP/API Domain → staff nhận và xử lý trên Domain → Domain phát tiến độ/bằng chứng → agent Platform cập nhật cho khách hàng**. BQL/admin vẫn dùng Platform theo quyền hiện có.

### 1.2. Hai phần phải bàn giao thế nào?

| Phần | Chủ trì | Đầu ra |
| --- | --- | --- |
| Phần 1 | **Người 1** | Backend IAM/quyền/secret/quota/KB, Domain adapter và toàn bộ Domain, storage/migrations, customer authority/projection. |
| Phần 2 | **Người 2** | Platform frontend/runtime, agent/Leader/Builder/eval, lịch/kênh, UI quản trị, RC Platform và điều phối kiểm thử/pilot/cutover cùng Người 1. |

Đây là hai phần giao cho hai người cùng triển khai, không phải hai giai đoạn tuần tự. Mỗi người code và test lane của mình, người kia review; cả hai chạy integration/browser/canary. Chủ sản phẩm/nghiệp vụ cung cấp policy/tài liệu/đầu mối và ký UAT, không thay phần việc lập trình hoặc kiểm thử của hai người. Các task dùng ID `N1-*` và `N2-*`; phụ thuộc là gate tích hợp, không cấm làm consumer bằng contract/fixture sớm.

## 2. Tái sử dụng các màn hình Platform hiện có

### 2.1. Không gian cá nhân

Các dòng dưới đây là khả năng phải dùng được trong UI đang có, không phải yêu cầu thiết kế một bộ màn hình cư dân mới.

| Tính năng trên Platform hiện có | Nội dung và hành vi cần bổ sung |
| --- | --- |
| Trang bắt đầu/Leader hiện có | Dùng điểm vào hiện có; bổ sung trạng thái link, quota và việc chờ xác nhận tại vị trí phù hợp. Không dựng dashboard cư dân hoặc bắt người mới chọn MCP/provider/key. |
| Workforce Leader | Hội thoại trực tiếp, kế hoạch/team phù hợp, hỏi bổ sung, consent, tiến độ, follow-up và tổng hợp có nguồn. |
| Agent của tôi | Tạo agent, chat riêng, sửa mục tiêu/prompt, chọn tài nguyên được cấp, version/test/readiness; agent cá nhân không tự trở thành agent chính thức Vin. |
| Hội thoại/chi tiết công việc trong Leader | Case/ticket của chính mình; timeline, tệp được phép, thao tác tiếp theo, phản hồi và xác nhận kết quả. Tích hợp vào luồng hiện có. |
| Knowledge | Hai tab “Thư viện Vin” chỉ đọc và “Kho của tôi” có quota/upload/xóa/index status. |
| Kiểm thử | Eval agent/version, kết quả từng ca, môi trường, lỗi agent/test/hạ tầng, token đã dùng; chạy lại có kiểm soát. |
| Lịch trình | Một lần hoặc lặp lại, timezone, tác vụ/agent, nơi nhận, lịch sử từng lần chạy và trạng thái bị chặn. |
| Tài khoản/Kênh hiện có | Bổ sung link Domain và kênh cá nhân; xem phạm vi, thu hồi/gỡ; giữ trang Kênh để cấu hình bot riêng theo quyền. |
| Các trang Provider, MCP, Skill hiện có | Xem/chọn provider/model alias, skill và MCP được cấp bằng safe DTO; cấu hình quản trị chỉ đọc đối với khách hàng. |
| Menu/trang tài khoản hiện có | Bổ sung usage/quota và quản lý phiên/link; dữ liệu riêng và yêu cầu xóa/xuất theo policy. |

Giữ layout và navigation hiện có; bổ sung tab/drawer/action nhỏ tại đúng chỗ còn thiếu. Route guard phân biệt quyền đọc và quyền sửa, kể cả truy cập URL trực tiếp. Admin/BQL tiếp tục dùng các trang đang dùng; nếu mở không gian cá nhân cho họ thì dùng menu hiện có và scope server xác minh, không lấy đó làm lý do dựng shell mới.

### 2.2. Không gian vận hành và quản trị

BQL dùng Platform như hiện tại (quyết định 18/10). Yêu cầu của cư dân không vào partner route, Leader hay danh sách của BQL; cư dân và BQL không thấy dữ liệu của nhau. Khi case cần nhân sự, agent của cư dân gọi MCP/API để giao việc vào hàng đợi/workflow Domain hiện có, kèm dữ liệu tối thiểu được phép. Staff đăng nhập Domain, nhận và cập nhật công việc tại đó; yêu cầu phê duyệt chỉ xuất hiện nếu rule Domain bắt buộc.

Không xây màn hình nhận việc mới cho staff trên Platform trong phạm vi này. Giữ ứng dụng staff, đăng nhập/phân quyền, thông báo công việc, hàng đợi, thao tác nhận/bắt đầu/cập nhật/nộp bằng chứng và QC theo vai trò tại Domain. Platform theo dõi ticket/work order và tổng hợp tiến độ cho khách hàng; trạng thái nghiệp vụ chính thức vẫn do Domain xác nhận.

Admin quản trị thành viên/capability, provider/key/catalog, quota theo nhóm/user, link/connector health, nội dung theo thẩm quyền, audit và rollout. Dashboard phân biệt usage cá nhân với nghiệp vụ, người khởi tạo với service thực thi, lỗi model với lỗi Domain. Admin không dùng đường này để đọc KB riêng hoặc chat riêng mặc định.

### 2.3. BQL: không thêm màn hình trong đợt này

Quyết định 18/10: không xây dashboard sáu nhóm việc, hàng đợi ngoại lệ hay giao diện phê duyệt mới cho BQL. BQL giữ nguyên các trang đang dùng. Trường hợp agent của cư dân không xử lý được thì đi vào hàng đợi vận hành có sẵn trên Domain. Phần admin (quota, catalog, thư viện KB) vẫn thuộc N2-08.

## 3. Agent cá nhân, chat riêng và Workforce Leader

### 3.1. Giữ engine đã có, tách purpose và quyền

Source đã có chat riêng và nhóm cá nhân với cách ly session/roster, Leader/team/invite, Shared Context và trao đổi giữa thành viên. Cần mở đúng khả năng cho `VIN_USER` và hoàn thiện luồng nghiệp vụ trực tiếp, không viết lại những cơ chế này.

Đề xuất thêm `purpose = personal | domain_service | system` và `visibility = private | entitled_catalog` hoặc trường tương đương vào lifecycle/manifest. Giữ `system_role` phục vụ runtime; không dùng việc agent có `system_role=business` để suy ra quyền BQL. Studio hiện khởi tạo custom agent theo business role; mọi đường create/copy/import phải gán purpose/owner từ server và không chấp nhận user tự khai là system/service.

Agent cá nhân chỉnh được tên, mục tiêu/prompt, hướng dẫn dùng tài nguyên, model trong alias được cấp, memory riêng và test. Không chỉnh governance của Leader hệ thống, không đổi chủ sở hữu catalog, không tự tăng quyền tool hoặc tải gói code/skill tùy ý qua workspace endpoint. Pin resource version, hiển thị tài nguyên có hiệu lực và xử lý khi resource bị thu hồi.

### 3.2. Luồng sử dụng

1. Chat riêng với agent là session cá nhân, không tự chia sẻ với nhóm khác.
2. Tạo nhóm hoặc yêu cầu Leader phối hợp: server resolve quyền mọi thành viên/tài nguyên trước khi ghi nhóm; giữ compensation đang có khi tạo thất bại.
3. Với việc nhiều chuyên môn, Leader chọn đội, giao đầu việc, nhận báo cáo, cho trao đổi/phản biện khi cần và tổng hợp. Không ép mọi agent nói trong mọi câu hỏi đơn giản.
4. Shared Context chỉ chứa nội dung được phép của tác vụ; không tự sao chép toàn bộ lịch sử/KB riêng vào nhóm hoặc agent service do người khác sở hữu.
5. Khi cần nghiệp vụ Domain, runtime dùng acting subject, grant và case binding của Phần 1. Agent cá nhân có thể giúp soạn/khởi tạo yêu cầu; hành động chính thức đi qua cổng Domain với bằng chứng và consent.
6. User theo dõi plan, người phụ trách, báo cáo, kết quả xác minh và next action. Không hiển thị chain of thought, secret, log riêng của BQL hoặc dữ liệu người khác.

Draft chỉ chạy thử trong đường authoring/sandbox có nhãn rõ và quyền hạn phù hợp; không đi qua channel/schedule/route production. Agent “sẵn sàng dùng riêng” phải qua cổng test hiện hành. Được phép dùng riêng không có nghĩa được công bố vào catalog Vin; muốn chia sẻ rộng cần review riêng của người có quyền.

Mỗi khách hàng tự build và sở hữu agent xử lý yêu cầu của mình; đợt này không có agent dịch vụ dùng chung giữa nhiều khách hàng. Starter template (nếu có) chỉ là bản copy vào không gian của khách, không mang theo secret/grant của ai khác. Không tái dùng nguyên manager-owned session của `_case`/`_runner`/provider projection cho cư dân; chỉ customer-safe projection mới đi vào UI/Shared Context của họ.

## 4. Builder và phát hành agent

### 4.1. Builder hiện tại

HEAD đã bỏ luồng JEV trong kế hoạch cũ. Triển khai dựa code hiện hành: phân tích mục tiêu, xem agent người dùng có quyền tái sử dụng, đề xuất tạo/sửa, chọn tài nguyên được cấp, tạo bản nháp, eval rồi phát hành. Không triển khai lại các task “deploy c0ad625c/chạy JEV” từ tài liệu cũ.

Các yêu cầu tránh vòng lặp vẫn cần giữ:

- Dàn ý biết agent hiện có trong workspace được phép; không lộ danh sách agent của user khác.
- User chọn tạo mới/sửa/tái sử dụng bằng lựa chọn có cấu trúc; lưu quyết định theo proposal revision. Không sinh lại toàn bộ chỉ vì trả lời một câu làm rõ.
- Server kiểm tra revision, quyền owner và catalog tại thời điểm áp dụng; conflict trả lỗi có hành động khôi phục.
- Không tự sửa agent nghiệp vụ Vin khi user chỉ có quyền dùng. Tạo agent riêng không mặc nhiên clone secret, KB hay grant của agent nguồn.
- Preview cho biết mục tiêu, tool/skill/KB sẽ dùng, read/write, link/consent cần có và budget dự kiến trước eval. Token/chi tiết kỹ thuật thu gọn.

### 4.2. Publish và rollback

Studio hiện đã clone record, stage workspace/bindings rồi kích hoạt qua lưu có kiểm soát revision. Giữ bản sửa đó. Nghiệm thu thêm lỗi KB/skill/MCP bị thu hồi, workspace write lỗi, race hai worker, worker crash giữa stage và activate, rollback và orphan cleanup.

Builder nhiều agent đang có đoạn commit prepared agents theo thứ tự; cần chọn và ghi contract rõ. Đề xuất: không công bố team/proposal usable cho tới khi tất cả agent cần thiết đã active; partial success được lưu trạng thái có thể repair/retry, không báo hoàn tất hoặc invite phần chưa sẵn sàng. Retry cùng proposal không tạo version/agent trùng. Không hứa transaction nguyên khối xuyên nhiều record Redis và filesystem.

Eval report phải khớp `spec_hash`, catalog/resource manifest và policy version cần thiết; draft/tài nguyên đổi thì báo cáo cũ không mở cổng. Rollback chỉ kích hoạt version còn đủ tài nguyên và quyền, không hồi sinh tool/KB đã thu hồi. Agent/version đang được workflow pin không bị xóa vật lý cho tới khi hết tham chiếu hoặc có migration được kiểm soát.

## 5. Eval và sandbox dành cho người dùng

### 5.1. Ba lớp bằng chứng

| Lớp | Chạy gì | Chứng minh được gì |
| --- | --- | --- |
| Tĩnh/offline | Schema, policy, fixture/provider giả, quyền, state machine | Hồi quy và thiết kế; không chứng minh model thật hay đối tác thật. |
| Business sandbox | Domain sandbox, user/ticket/fixture riêng theo run, grant sandbox; model test khi được cấu hình | Luồng đọc/ghi trên môi trường thử và chất lượng agent theo bộ test. |
| Live UAT | Tài khoản/link, tài liệu, model và nghiệp vụ thật trong phạm vi được chấp thuận | Kết quả phục vụ người dùng thực và chấp thuận của chủ nghiệp vụ. |

Trên baseline, MCP có trong `WORKFORCE_EVAL_SANDBOXES` đã chạy thật trên sandbox Vinhome: mỗi ca lấy một ticket mẫu mới qua `eval-fixtures` và grant theo ticket, tool cần đồng ý được chạy với nhãn `consent_assumed`. MCP không khai sandbox vẫn đọc thật, ghi mô phỏng. Bộ fixture hiện chỉ có một loại ticket sự cố kỹ thuật cho agent của BQL; chưa có fixture theo cư dân đã link (self-context, tạo yêu cầu trước ticket) và profile vẫn nằm trong env thay vì do admin quản lý. Báo cáo/UI giữ nhãn sandbox/mô phỏng/`consent_assumed`; không cho người dùng hiểu “tool ghi pass” là đã thực hiện nghiệp vụ thật.

### 5.2. Môi trường và fixture

Admin cấu hình environment profile, endpoint allowlist, trust/identity, grant exchange, fixture factory và tool được ghi. User chỉ chọn profile đã được cấp. Kiểm tra environment ở cả Platform và Domain; body `mode=sandbox` hoặc đổi URL của user không thể cấp quyền ghi production. Network/secret/account sandbox tách khỏi production; không cho tool fixture seed/reset chạy trên production.

Mỗi run có namespace user/run, dữ liệu giả hoặc đã ẩn danh, ticket/subject/expected state tương ứng. Trước-ticket có ca self-context/intake; sau-ticket có ca theo dõi/đổi lịch/hủy/consent. Test gắn fixture, không bắt agent đoán ticket ID. Thao tác ghi sandbox trả receipt/state thật của sandbox hoặc structured simulated receipt có nhãn rõ; không chỉ một câu “SIMULATED”.

Dùng lại seam grant/scoped client và `business_sandbox_fixture` nếu phù hợp; không dùng discovery token gọi nghiệp vụ. Fixture được tạo lại cho mỗi run/mutation, có cleanup/idempotency, tránh ca trước ảnh hưởng ca sau. Tool third-party không có sandbox thì chỉ mock và hiển thị chưa nghiệm thu nhà cung cấp thật.

Eval nhiều lượt phải có bước hỏi/đáp và consent mô phỏng rõ actor; các ca thành công, thiếu dữ liệu, từ chối, mất quyền và outcome chưa rõ. Runtime, solver, judge/verifier cùng qua quota, giới hạn bước/time/cost; cancel giữ báo cáo phần đã chạy và xử lý operation pending đúng cách.

### 5.3. Cổng chất lượng

Baseline đã áp dụng (`_publish_gate.py`, PR #99): tối thiểu 5 ca, đạt ≥80% (tức ≥4/5), **100% ca an toàn bắt buộc đạt**, báo cáo khớp `spec_hash`, mọi lỗi môi trường/model/judge chặn phát hành và không tính là agent trượt; judge không trả kết quả thì thử lại 1 lần. Giữ cổng này cho agent cá nhân; không hạ ngưỡng cho người dùng thường. Phần còn thiếu: lưu policy version trong báo cáo và hiển thị trạng thái `inconclusive` rõ trên UI người dùng.

Người 1/Người 2 review safety/contract và chủ sản phẩm chốt policy này trong release config; trong lúc chưa chốt giữ gate hiện hành. UI phải cho biết “chưa kiểm thử được”, “agent làm sai”, “test/fixture không hợp lệ” hoặc “đạt trên mô phỏng”; không gom mọi lỗi thành agent fail. Bổ sung kiểm tra retrieval/citation thật và skill content thật, vì chỉ eval chat pass chưa chứng minh RAG/binding đang hoạt động.

## 6. Lịch trình cá nhân và nghiệp vụ

### 6.1. Sửa phần hiện có

Baseline (PR #99) đã có: cờ `once` (chạy ở lần khớp cron kế tiếp rồi tự tắt), `ended_at` truyền qua API và trigger, `deliver_channel_id`, `last_fired_at`/`last_session_id`/`last_error`, ba mẫu lịch chỉ đọc, chỉ chọn Leader hoặc agent đã phát hành, không BYPASS (mặc định `DONT_ASK`). Khoảng thiếu còn lại: `once` chỉ tự tắt khi chạy thành công, chạy lỗi thì vẫn bật và sẽ chạy lại ở lần khớp sau; chỉ lưu lần chạy gần nhất, chưa có run ledger từng lần; form tự chọn kênh Discord của khu, chưa có nơi nhận riêng từng người; chưa qua quota; chưa có claim chống chạy trùng giữa nhiều replica.

Hợp đồng lịch đề xuất:

| Nhóm trường | Nội dung |
| --- | --- |
| Chủ thể | Owner/workspace/billing subject server resolve; scope và revision quyền |
| Trigger | `once` với `run_at` có timezone hoặc `cron` với timezone, `started_at`, `ended_at` |
| Tác vụ | Agent/version sẵn sàng hoặc system Leader được cấp, prompt, context/resources tối thiểu |
| Delivery | Mặc định inbox/session của user; tùy chọn DM hoặc channel riêng đã xác minh |
| Policy | Read-only mặc định, approval rule, timeout/step/output cap, concurrency/misfire policy |
| Run record | Schedule/run ID, scheduled time, state, attempt, session/receipt, token/quota, delivery status |

Một lần dùng DateTrigger hoặc cơ chế tương đương, chạy xong thành completed và không lặp năm sau; lịch lặp có end date được backend enforce. Timezone mặc định `Asia/Ho_Chi_Minh`, hiển thị giờ người dùng và lưu UTC. Lịch quá hạn/misfire phải có hành vi rõ, không tự chạy dồn toàn bộ sau downtime.

### 6.2. Khi chạy

Claim duy nhất theo `(schedule_id, scheduled_for)`; recheck user active, link/grant/catalog/agent version, quota và nơi nhận trước mỗi run. Dùng lease/fencing và idempotency Domain cho crash/two workers; không tuyên bố exactly-once side effect nếu chỉ có scheduler lock. Pin version hoặc chính sách theo bản mới phải được user biết; đổi version quan trọng yêu cầu kiểm thử lại.

Không cho `BYPASS` với user thường và nghiệp vụ. Tác vụ cần ghi đưa vào chờ chấp thuận có TTL/expected version, không tự thực hiện bằng một consent mơ hồ khi tạo lịch. Có thể thêm standing authorization sau nếu Domain hỗ trợ scope/hạn mức/thu hồi rõ; chưa đưa vào pilot.

Kết quả mặc định ở inbox/Leader riêng, Discord chỉ gửi khi user chọn. Lưu `blocked_quota`, `blocked_auth`, `waiting_approval`, `running`, `succeeded`, `failed`, `unknown_outcome`, `delivery_failed`, kèm next action. Retry delivery không chạy lại model/tool; retry business không tạo lệnh trùng. “Chạy thử ngay” cũng qua quota/authorization như run thật.

## 7. Discord và các kênh ngoài

### 7.1. Phạm vi pilot

Adapter Discord đã có; baseline (PR #99) thêm danh sách `approver_user_ids` (người gửi tự duyệt được thao tác của mình, người khác bấm thì bị từ chối), chỉ gắn Leader/agent đã phát hành, token bot mã hóa bằng `CHANNEL_CREDENTIALS_KEY`, DM luôn trả lời, trong server chỉ trả lời khi @mention. Như vậy vẫn chưa đủ để kết luận cư dân dùng nghiệp vụ an toàn: danh tính Discord chưa liên kết với user Platform, mỗi người vẫn tự nhập token bot, người duyệt là Discord ID nhập tay. Pilot triển khai DM/private conversation được liên kết user; chỉ gửi dữ liệu dịch vụ nhạy cảm trong Platform hoặc đích riêng đã được kiểm chứng. Kênh server chung chỉ dùng nội dung được phép công khai cho đúng audience; không tự trả hồ sơ/KB riêng vào đó.

Theo quyết định 18/10 (khách hàng có đủ tính năng Platform), khách hàng dùng trang Kênh hiện có với **bot Discord của chính mình**, giống tài khoản BQL: token mã hóa khi lưu, chỉ gắn Leader/agent đã phát hành. Vì agent của khách giữ liên kết Vinhomes, bổ sung một điều kiện bắt buộc: danh sách Discord user ID được nói chuyện với bot (mặc định chỉ ID của chủ tài khoản); tin của người ngoài danh sách bị bỏ qua và không gọi model. Người duyệt mặc định là chủ tài khoản. Bot dùng chung do Platform vận hành chưa thuộc đợt này; nếu làm sau thì áp dụng bước 1–2 ở mục 7.2.

### 7.2. Identity và approval

Với bot riêng của khách (đợt này), bước 1–2 được thay bằng danh sách Discord ID ở mục 7.1; bước 3–6 vẫn áp dụng. Bước 1–2 chỉ bắt buộc nếu sau này có bot dùng chung do Platform vận hành.

1. Từ Platform đã đăng nhập, tạo challenge một lần gắn phiên hoặc OAuth `identify` rồi xác minh qua `/users/@me`; kiểm tra external user ID, namespace/provider/app, state/expiry và chống replay. Cài/invite bot vào server không chứng minh danh tính user; không dùng `guild_id`, display name, email giống nhau hoặc biết room ID làm bằng chứng liên kết.
2. Mapping external identity → Platform user/workspace; mỗi event resolve lại membership/link/quota. Default session per-user hoặc per-user-per-chat; không dùng mặc định per-chat để trộn nhiều cư dân.
3. Chọn agent chỉ từ resource user được chạy; agent phải sẵn sàng đúng version. Server kiểm tra khi lưu route và khi nhận message; không gắn draft, agent user khác hoặc workspace quản trị bằng ID đoán.
4. Nút chấp thuận ràng buộc request/user/action/resource/payload hash/version/expiry/nonce. Người bấm phải là chủ thể hoặc approver do Domain xác nhận. Thành viên cùng channel không tự trở thành người duyệt.
5. Với hành động nhạy cảm hoặc không thể bảo đảm riêng tư/danh tính ở Discord, nút dẫn về Platform tái xác thực; không gửi secret/grant trong URL.
6. Verify webhook/interaction theo cơ chế adapter, chống replay/duplicate; gateway event dedup theo provider event ID. Tệp đính kèm có kiểm tra và download policy như web.

Theo tài liệu Discord chính thức, dùng quyền/intents tối thiểu cho chức năng đã chọn; không mặc định yêu cầu quyền Administrator. Nếu đọc nội dung message cần privileged Message Content Intent thì kiểm tra điều kiện enable/approval của ứng dụng; không hứa bot quy mô lớn đọc được ngay. Không dùng user token/self-bot. Hướng dẫn cài đặt phải đi cùng test token revoked, reconnect, rate limit, duplicate, user rời server và quyền gửi bị mất.

Với interaction/button/slash command, adapter phải ack/defer trong 3 giây; follow-up interaction token có thời hạn 15 phút. Job lâu hơn dùng delivery/inbox phù hợp, không lưu token đó làm credential lâu dài. Các mốc này không áp cho mọi Gateway chat message. Pilot dùng DM với bot hoặc phòng riêng đã kiểm soát; bot không tham gia Group DM. Kiểm tra ngoại lệ DM trước khi yêu cầu privileged Message Content Intent không cần thiết.

### 7.3. Mở rộng kênh

DingTalk/Feishu đã có adapter; mỗi kênh vẫn phải qua cùng identity/approval/privacy/quota contract. Thêm kênh khác bằng adapter và capability registry, không bypass gateway. Kênh chưa tích hợp hiển thị theo trạng thái kế hoạch, không dựng nút “đã kết nối” bằng dữ liệu giả.

Channel worker có owner/lease rõ để nhiều app replica không cùng giữ gateway connection hoặc gửi trùng. Giữ rate limit, outbox/delivery retry và trạng thái delivery độc lập model run; tắt kênh không xóa case/ticket hoặc transcript gốc của user.

## 8. Danh sách triển khai và phụ thuộc

### 8.1. Backlog Người 2

| ID | Đầu việc và seam chính | Phụ thuộc | Nghiệm thu đầu ra |
| --- | --- | --- | --- |
| N2-01 | Giữ UI/shell/navigation hiện có; bổ sung đăng ký khách hàng, capability, dữ liệu riêng và quota/link tại các component hiện có | N1-01, N1-02 | Khách hàng dùng cùng Platform và đủ tính năng cá nhân; BQL/admin giữ luồng cũ; chỉ chặn thao tác/route thực sự thiếu quyền, không dựng portal cư dân. |
| N2-02 | Agent purpose/private lifecycle, chuyển console/model/readiness sang resolver chung | C02/C03 callable; N1-06 cho KB, N1-03/N1-04 là release gate | Giao seed-removal slice sớm cho N1-03; agent riêng đi trọn chat/test/publish với KB Vin/riêng, không sao chép key hoặc sửa catalog. |
| N2-03 | Leader/team cá nhân và service-case UX, consent/timeline/staff progress/follow-up | N1-07, N1-08, N2-02 | Cư dân gửi/theo dõi yêu cầu trên Platform; staff xử lý ở Domain cũ, agent cập nhật tiến độ/bằng chứng về đúng cư dân. |
| N2-04 | Builder theo HEAD, quyết định có cấu trúc, stage/activate và repair batch | N2-02 | Không làm rõ lặp; lỗi giữa batch không báo xong/không tạo trùng; giữ bản đang dùng. |
| N2-05 | Mở rộng eval sandbox PR #99 cho agent cá nhân: fixture theo cư dân/run, profile admin quản lý, nhãn `consent_assumed`/`inconclusive` trên UI | N1-04, N1-07 sandbox, N2-02 | Không ghi production; có báo cáo phân loại, safety gate và test RAG thực. |
| N2-06 | Bổ sung trên lịch PR #99: `once` lỗi không chạy lại, run ledger, nơi nhận riêng từng người, authorization/quota, claim chống trùng | N1-04, N2-02; N2-07 nếu gửi Discord | Một lần không lặp lại kể cả khi lỗi, restart không nhân đôi operation, có kết quả riêng và lịch sử. |
| N2-07 | Bổ sung trên Discord PR #99 cho khách hàng: bot riêng qua trang Kênh, danh sách Discord ID được nói chuyện (mặc định chỉ chủ tài khoản), người duyệt mặc định là chủ, quota | N1-02…N1-05, N2-02 | Message đúng owner; người ngoài danh sách không dùng được agent, không tiêu quota, không duyệt được; revoke và retry an toàn. |
| N2-08 | Bổ sung quota theo nhóm/người, catalog chỉ đọc cho khách hàng và thư viện KB Vin vào UI hiện có | N1-03, N1-04, N1-06 | Admin đặt quota/catalog/KB đúng quyền; khách hàng xem/chọn/dùng catalog được cấp, không sửa cấu hình; giữ trang Kênh và các tính năng cá nhân, không có màn hình BQL mới. |
| N2-09A | Chuẩn bị RC Platform, feature flags và điều phối rehearsal migration/reconciliation/restore | N1-09, N2-01…N2-08 | Người 1 thực hiện DB/Domain, Người 2 build/smoke Platform; dữ liệu/route/event đúng, rollback sẵn, chưa tắt chatbot. |
| N2-10 | Load/privacy/security/UAT, pilot và runbook | N2-01…N2-08, N2-09A | Các gate mục 9–11 và pilot đạt với evidence; chủ nghiệp vụ ký, còn thiếu ghi rõ. |
| N2-09B | Cutover chatbot theo cohort | N2-10 | Chỉ một intake mới mỗi cohort; ticket cũ/progress còn cập nhật; quyết định bỏ chatbot có sign-off. |

Tất cả N2-* do **Người 2** chủ trì; N1-* do **Người 1**. Các task chung có split rõ: Người 1 làm DB/Domain/migration/authority, Người 2 làm runtime/UI/RC Platform, cả hai review và ký kết quả kỹ thuật. Backlog ở repo, chưa đăng tracker. Thứ tự N2-09A → N2-10 → N2-09B giữ nguyên, không để UAT phụ thuộc việc đã tắt chatbot. PR chỉ commit allowlist của lane, có contract/API/migration version và evidence gắn SHA; không push WIP khác. Worktree của hai người tách từ `dev_Chien` baseline, không mặc định đã đồng nhất image VPS.

### 8.2. Trình tự và ước lượng

| Chặng | Việc chủ yếu | Có thể làm song song | Gate ra |
| --- | --- | --- | --- |
| A — Chốt hợp đồng và chặn P0 | N1-01/02/03/04; contract Domain; baseline source/runtime | N2-01 ghép capability/schema vào UI hiện có, chuẩn bị tài liệu Vin thật | Không còn key lộ/user giả BQL; quota gate có bằng chứng. |
| B — Dùng AI cá nhân có kiểm soát | N1-06, N2-02/04, phần eval offline/mô phỏng của N2-05 và admin policy | Link Domain N1-05; sửa lịch/kênh bằng fixture | Chat + build + KB + eval mô phỏng có owner/ACL/quota đúng; chưa nhận là business sandbox hoàn chỉnh. |
| C — Vinhomes trực tiếp | N1-07/08, N2-03/08 và business sandbox N2-05 sau N1-07 sandbox; consent và migration ticket | N2-06/07, tài liệu/help | Cư dân link thật → tạo ticket → tiến độ → xác nhận có receipt; test business sandbox hoàn tất. |
| D — Pilot đầy đủ và chuyển kênh | N1-09, N2-09A → N2-10 → N2-09B, bật lịch/Discord cho cohort | Đo tải, restore, đào tạo BQL/support | Full acceptance; chuyển cohort; sau ổn định mới bỏ chatbot. |
| E — Mở thêm người dùng/domain | Lặp onboarding/adapter, audience KB và quota riêng | Nâng capacity theo số đo | Từng domain đạt contract/UAT riêng, không suy từ Vinhomes. |

Nguồn lực triển khai là **hai người full-stack**, tự test lane, review chéo và cùng làm DevOps/QA theo phân công; không dựa vào đội sáu người như ước lượng cũ. Khung lập kế hoạch ban đầu cho đủ phạm vi pilot là **16–24 tuần làm việc song song**, chưa phải cam kết. S0 mất khoảng 2–3 ngày làm việc để chốt contract, sau 1–2 tuần spike phải ước lượng lại theo số migration, mức sẵn sàng IdP/API thật và dữ liệu/UAT. Không cộng thời gian hai phần thành 32–48 tuần và không giữ mốc 8–12 tuần của nguồn lực cũ. Nếu thiếu năng lực ở một lane thì giảm độ rộng cohort/kênh hoặc điều chỉnh tiến độ, không bỏ quyền/quota/an toàn.

### 8.3. Lịch giao slice giữa đúng hai người

| Mốc | Người 1 làm song song | Người 2 làm song song | Bằng chứng tích hợp |
| --- | --- | --- | --- |
| S0 — 2–3 ngày đầu | C01–C10, storage methods/schema, policy và fixture; tạo interface sớm | Review DTO/state, client typed, route layout, fixture consumers và scopes runtime | Schema/version + file owners chốt; không có method/persistence “để người kia tự làm”. |
| S1 — AI cá nhân | Auth/capability, resolver/quota, shared/private KB, storage stage/CAS | UI login/catalog/KB, seed-removal slice, chat/agent/Builder/readiness/eval offline | User thường login → chọn resource → chat/build → publish có quota và không lộ key. |
| S2 — Vinhomes | Link/subject adapter, request→ticket binding/grant/intent, progress/replay | Leader intake/customer timeline/consent; ticket `origin=platform` không vào route BQL | Cư dân Platform → staff Domain → tiến độ/bằng chứng về đúng cư dân; BQL không phải xem case. |
| S3 — Tự động hóa/admin | Sandbox fixture theo cư dân, run/delivery persistence | Business eval, once/cron, Discord bot riêng/allowlist/approval/delivery, admin quota/catalog/KB UI | Sandbox không ghi production; lịch/kênh không vượt quyền/quota hoặc tạo lệnh trùng. |
| S4 — RC/pilot | Migration/backfill/dry-run/Domain compatibility/restore | RC Platform, browser/load/role checks, consolidated runbook | Cả hai review evidence rồi canary/UAT; chưa đạt không cutover. |
| S5 — Cutover/mở rộng | Thực hiện Domain resident redirect và giữ staff/progress worker | Thực hiện Platform cohort flags, theo dõi canary/support và rollback orchestration | Pilot ký chấp thuận, một intake/cohort, staff Domain hoạt động; mở thêm domain theo onboarding/UAT riêng. |

## 9. Ma trận nghiệm thu bắt buộc

### 9.1. Chức năng và phân quyền

| ID | Kịch bản | Điều kiện đạt |
| --- | --- | --- |
| U01 | Cư dân đăng ký và login | Không có membership BQL, không sửa role bằng body/token/header. |
| U02 | Link Vinhomes thật | Consent đúng người; code replay/sai state/subject/redirect bị chặn; không thu mật khẩu tại Platform. |
| U03 | Hai cư dân cùng/khác căn hộ | Domain quyết định quyền; A không đọc ticket/file/session/KB của B bằng ID đoán. |
| U04 | BQL/admin và khách hàng cùng dùng Platform | BQL dùng các trang như trước, không thấy case/agent/KB/hội thoại của cư dân; cư dân không thấy dữ liệu BQL hay cư dân khác; ticket `origin=platform` không vào route BQL. |
| U05 | Provider/skill/MCP chỉ đọc | Không CRUD/import/install qua UI/API/Builder/agent tool/upload; chọn được resource đã cấp. |
| U06 | Key chung và migrate provider | Sentinel không xuất hiện response/log/export/bundle; legacy không tạo lại key; KB riêng upload/index/search còn chạy qua provider resolver mới. |
| U07 | Catalog Vin KB → readiness → publish → runtime | Shared KB được resolve nhất quán, đọc/citation thật đúng nguồn và audience. |
| U08 | KB riêng | Upload/index/xóa đúng quota; user khác, BQL và admin thường không đọc được. |
| U09 | Prompt injection trong tài liệu/skill | Không đổi quyền, không lấy secret, không gọi tool ngoài allowlist; tool output là dữ liệu không phải chính sách. |
| U10 | Thu hồi tài liệu/link/user | Call, retrieval, download và job mới bị chặn; source refs ngăn recall/cache legacy trái quyền; pending operation có đường đối soát. |
| U11 | Chat riêng/nhóm/Leader | Session, roster, Shared Context và memory không lộ chéo; giữ phần evidence hợp lệ khi cần sửa câu trả lời. |
| U12 | Agent cá nhân tạo/sửa/test/publish/rollback | Spec/version/resource manifest khớp; không thành agent chính thức hoặc tăng quyền. |
| U13 | Publish lỗi/race/crash/batch partial | Version cũ còn usable, bản chưa sẵn không invitable; retry không tạo trùng; orphan cleanup an toàn. |

### 9.2. Chi phí, sandbox và tự động hóa

| ID | Kịch bản | Điều kiện đạt |
| --- | --- | --- |
| U14 | Fan-out web + team + eval + lịch + kênh | Reserve atomic đúng billing subject/group trên final payload; thiếu budget/policy hoặc quota store hỏng thì không có provider call. |
| U15 | Retry/fallback/summary/judge/embedding | Usage không bị bỏ sót; input cached không cộng đôi; phần thiếu usage không coi là 0. |
| U16 | Crash/hủy/quota rollover | Không hoàn tiền giả, không settle hai lần; reservation cũ không biến mất qua ngày/tháng. |
| U17 | Sandbox và fixture | Cách ly user/run, grant đúng subject/ticket, ghi thật chỉ vào sandbox; seed/reset production bị từ chối. |
| U18 | Eval lỗi môi trường/safety | Inconclusive không được pass; test an toàn fail chặn publish, report cũ/hash sai bị chặn. |
| U19 | Lịch once/end date/timezone | Chạy đúng thời điểm, không lặp năm sau; downtime/misfire không tạo lệnh dồn trái policy. |
| U20 | Hai worker/duplicate event | Không tạo hai business operation hoặc delivery do cùng logical run/event; unknown outcome được đối soát. |
| U21 | Discord owner/approval | Người trong room khác không thể duyệt hộ; binding đúng payload/version/expiry, replay bị chặn. |
| U22 | Discord privacy/revoke/rate limit | Không trả KB/ticket riêng vào room chung; revoke ngăn call mới; retry delivery không gọi lại model. |

### 9.3. Nghiệp vụ, vận hành và chuyển đổi

| ID | Kịch bản | Điều kiện đạt |
| --- | --- | --- |
| U23 | Cư dân chưa có ticket gửi yêu cầu | Link → self context → xác nhận → tạo ticket/bind existing workflow có receipt; không giả ticket/BQL owner, không auto-start workflow thứ hai. |
| U24 | Theo dõi/hủy/đổi lịch và quyết định từ Platform | Subject/intent/expected version hợp lệ; quote/completion card và ảnh mở đúng gate `applied`; mất event/ack được đối soát, không dựa HTTP 202. |
| U25 | Thiếu dữ liệu, khẩn cấp hoặc Domain lỗi/timeout | Không bịa thành công; tạo lại không trùng; có next action/handoff. Khẩn cấp có kênh hỗ trợ xác định không chờ model/quota, giữ restriction Domain. |
| U26 | Agent theo dõi, staff xử lý trên Domain | Khách hàng gửi Platform → agent giao việc qua Domain → staff login/nhận/bắt đầu/cập nhật/nộp bằng chứng tại Domain cũ → tiến độ/kết quả về đúng khách hàng qua agent. Giữ queue/quyền/QC hiện có; event trễ/mất/trùng được đối soát, không báo hoàn thành từ accepted. |
| U27 | Kết thúc case | Không dùng “đã trả lời” thay “đã hoàn thành”; resident confirmation/ngoại lệ theo rule Domain, không auto-close sai. |
| U28 | Ticket/hội thoại cũ | User thấy đúng lịch sử/case được migrate; group BQL/private chat không gộp; ticket đang chờ quote/completion và mất ack vẫn tiếp tục đúng trạng thái. |
| U29 | Rollout/rollback/restore | Tắt chatbot cư dân không ảnh hưởng login/nhận việc/xử lý/thông báo của staff Domain hoặc mất pending operation; restore cả SQL/Redis/MinIO/workspace và replay đạt. |
| U30 | Capacity/abuse | Load đại diện đạt SLO đã chốt; fairness user, queue/backpressure, upload/index/model rate limit hoạt động. |

Test ở đúng tầng: unit/contract với provider giả; integration hai process trên PostgreSQL/Redis và MCP sandbox; browser theo role; canary model/RAG/Discord thật; cuối cùng UAT nghiệp vụ có người ký. Không thay PostgreSQL race test bằng SQLite, không thay UAT bằng health/discovery hoặc kết quả CI.

Mỗi evidence ghi SHA/image/migration/config version đã che secret, môi trường, tài khoản thử được định danh an toàn, fixture/test ID, thời gian, kết quả, log/receipt và người kiểm tra. Phân biệt **đã triển khai**, **đã test offline**, **đã test live**, **được nghiệp vụ nghiệm thu**. Lập kế hoạch này không cấp phép tự động chạy những ca có chi phí hoặc tác động production trong đợt rà soát hiện tại.

## 10. Migration và bỏ chatbot Vinhomes

### 10.1. Chuẩn bị dữ liệu và compatibility

1. Chốt baseline source/runtime/migration và backup có restore evidence; tách dữ liệu thật, fixture và tài liệu unverified. Không lấy số tài liệu trong báo cáo cũ làm danh sách được duyệt.
2. Expand schema trước: role/membership mới, domain links, entitlement, reservation, case audience/projection và run records. Giữ route/API cũ cho flow đang dùng; không rename/xóa cột trước khi consumer cũ dừng.
3. Backfill scope cho account/agent/KB/session cũ theo provenance. Bản chưa chắc vào quarantine/needs-review; không mặc định mọi agent/KB cũ là public Vin.
4. Link cư dân bằng xác thực thật hoặc quy trình mời có xác minh. Không auto-link chỉ bằng tên/email/căn hộ, không sao chép mật khẩu Vinhomes, không chuyển tất cả residents thành managers.
5. Ticket cũ map bằng tenant + domain subject + ticket/correlation; giữ external ID và state history. Chỉ migrate transcript/tệp được phép theo policy, không mở manager conversation cho cư dân. Với intake mới `origin=platform`, bind existing case/workflow có chứng thực, không để helper cũ queue thêm `start_workflow`.
6. Migrate credential hệ thống theo N1-03 trước khi user thường có quyền đọc API; counters quota mới có opening window và log rõ, không giả định ledger cũ đầy đủ hoặc tự quy usage cũ thành 0.
7. Contract/API version và route activation kiểm tra trước khi chạy canary; manager route cũ còn dùng cho ticket cũ, không bị chuyển owner sang cư dân. Giữ `platform-sync`/outbox/provider events, accepted/applied acknowledgement và reconciliation; chỉ retire mirror chat cũ sau khi consumer mới thay đủ. Không tắt worker chỉ vì gỡ chatbot.
8. Giữ tài khoản, role, ứng dụng staff và các ticket/work order đã giao trên Domain; không migrate staff sang Platform hoặc bắt liên kết tài khoản Platform để tiếp tục nhận việc. Trước/sau cutover kiểm tra đăng nhập, thông báo, queue, nhận/bắt đầu/kết thúc công việc, bằng chứng và luồng cập nhật về Platform bằng cùng giao diện staff hiện tại.

### 10.2. Chuyển theo cohort

| Bước | Hành động | Điều kiện đi tiếp |
| --- | --- | --- |
| M0 — Chưa mở cư dân | Internal QA với fixture, nhân sự thử đúng vai trò và canary nhỏ | U01–U30 có coverage, các gate bảo mật và dữ liệu đạt. |
| M1 — Pilot cư dân được mời | Một khu/cohort có account/link thật; Platform là điểm chat mới cho nhóm đó | Ticket đi trọn vòng, quota/citation/consent đúng; support và rollback trực được. |
| M2 — Chuyển điểm tiếp nhận | Với cohort đã chuyển, app Vinhomes dẫn cư dân sang Platform; chatbot cũ không nhận yêu cầu mới cho cohort đó | Không phát sinh hai intake; ticket cũ vẫn đồng bộ; staff tiếp tục nhận/xử lý trên Domain; hỗ trợ khẩn cấp trước-ticket/quota 0 đã UAT. |
| M3 — Mở rộng Vinhomes | Tăng cohort từng bước theo tải và lỗi thực; người mới onboarding trực tiếp Platform | Nghiệp vụ ký chấp thuận; không còn lỗi P0/P1; ổn định qua cả kỳ lịch và quota rollover đại diện. |
| M4 — Bỏ chatbot cũ | Gỡ UI chatbot cư dân khi tất cả cohort mục tiêu đã chuyển; giữ ứng dụng và workflow staff Domain | Không còn consumer phụ thuộc chatbot; staff login/nhận việc/cập nhật kết quả và progress về Platform đạt; hướng dẫn/redirect/lịch sử/replay/emergency fallback thay đầy đủ. |

Khoảng ổn định đề xuất để quyết định M3/M4: tối thiểu hai tuần pilot có ca thực đại diện, bài kiểm tra tăng tốc rollover tháng và lịch once/recurring, cộng số lượng ca đủ cho chủ nghiệp vụ đánh giá. Đây là tiêu chí đề xuất; không phải cứ hết hai tuần là tự động đạt. Không cần đợi một tháng chỉ để test rollover nếu có kiểm thử thời gian và đối soát canary phù hợp.

Feature flags riêng cho `vin_user_access`, Domain self-intake, customer case projection, personal KB, schedule, channel, và legacy chatbot intake theo cohort. Khi sự cố: ngừng nhận yêu cầu mới ở capability bị lỗi, giữ đọc lịch sử/receipt nếu còn an toàn; không rollback schema phá dữ liệu đã phát sinh. Nếu phải trở về chatbot cũ, chỉ bật lại sau kiểm tra compatibility/route và dedup, chuyển điểm vào một lần cho cohort; không để hai intake đồng thời.

### 10.3. BQL và staff sau chuyển đổi

BQL không xem/duyệt case của cư dân trên Platform và tiếp tục dùng Platform như hiện tại. Case agent không xử lý được đi vào hàng đợi vận hành có sẵn trên Domain.

Staff chỉ nhận và thực hiện công việc trên ứng dụng/workflow Domain hiện có, cập nhật tiến độ và nộp bằng chứng tại Domain; QC/phê duyệt vẫn theo vai trò được cấp. Agent Platform điều phối qua MCP/API, nắm bắt tiến độ/kết quả từ Domain và cập nhật cho khách hàng tại Platform. Không yêu cầu staff mở Leader, chat với agent hoặc dùng màn hình tác nghiệp Platform. Dashboard đo chất lượng xử lý và độ đầy đủ/kịp thời của tiến độ từ Domain, không đo “ít BQL xem chat” làm bằng chứng công việc hoàn tất.

## 11. Vận hành, tải và mở rộng nhiều domain

### 11.1. Release và khả năng phục hồi

Mỗi release có immutable app/web tags, source manifest/checksum, migration manifest, config diff đã che secret và rollback artifact. Backup/restore đủ PostgreSQL, Redis, MinIO và workspace/Qdrant theo runbook hiện có; khôi phục thử tách biệt trước migration lớn. Env/key đổi phải recreate service và xác minh effective config kín, không dùng restart làm bằng chứng đã đổi cấu hình.

Đặt queue/concurrency và fairness cho model, eval, ingestion, scheduler, channel, Domain calls; long job trả trạng thái/cancel và không chiếm hết capacity chat. Tách worker khi số đo cho thấy cần, tránh scale app làm nhiều scheduler/channel owner hoặc migration chạy đua. Dung lượng/RAM trong báo cáo dọn Docker là snapshot, không chứng minh đủ cho tất cả cư dân/người dùng Vin.

Trước pilot chốt workload giả định: số user active, concurrent chats, team fan-out, token/run, file/embedding/ngày, schedules và channel events. Đo latency end-to-end, time-to-first-response, queue age, model/provider rate limit, DB connections, Redis/workspace growth, disk/backup headroom. Chốt SLO có số và alert receiver thực dựa baseline; không tự công bố năng lực hàng nghìn user từ health 200. Mục tiêu RPO/RTO phải được chủ vận hành chấp thuận và diễn tập, không tự nâng cam kết từ runbook cũ.

Dashboard/alert ít nhất: quota refused/pending reconciliation, secret access anomaly, link revoke failures, permission denies bất thường, KB parse/index/delete backlog, grant/intent failures, ticket/event sequence lag, unknown operations, schedule misfire, channel delivery retry, publish partial/orphan, model usage/cost unknown và backup restore age. Không log prompt/file/token thô chỉ để điều tra metric.

### 11.2. Bổ sung Vinpearl, VinWonders và các bên khác

Onboarding một domain cần chủ hệ thống và chủ nghiệp vụ, endpoint/trust/IdP, account-link subject mapping, catalog tool có read/write và audience, sandbox/fixtures, grant/consent, idempotency/receipt/events, dữ liệu KB được duyệt, quota, support và UAT riêng. Có compatibility suite dùng chung nhưng kết quả Vinhomes không thay chứng nhận của domain mới.

Không coi các travel mock trong Domain hiện có là tích hợp Vinpearl/VinWonders thật. Năng lực đặt dịch vụ có phí chỉ mở sau hợp đồng API, giá/availability nguồn, quote expiry, prepare/confirm, thanh toán/hủy/hoàn và đối soát được nghiệm thu. Giao diện người dùng chỉ hứa chức năng được catalog/environment đánh dấu đang hoạt động.

Mở AI cá nhân cho nhân viên/người dùng Vin mới bằng membership/audience và mẫu agent phù hợp; đây là quyền sử dụng tùy chọn trong tương lai, độc lập với việc staff nhận và thực hiện công việc tại Domain. Không nhân bản toàn bộ stack cho từng nhóm nếu chưa có yêu cầu cô lập hoặc capacity. Nếu tích hợp tổ chức ngoài Vin, đánh giá tenant/data boundary và quyền chia sẻ riêng; cùng một protocol MCP không đồng nghĩa cùng mức tin cậy.

## 12. Các quyết định vận hành phải chốt trước release

Định hướng sản phẩm, kiểu liên kết, quyền Knowledge, catalog chỉ đọc và hạn mức theo người đã được chủ dự án xác nhận. Không hỏi lại các nội dung đó. Những tham số dưới đây phải có người phê duyệt trong checklist release; không cản việc triển khai schema, policy và test bằng fixture:

| Cần chốt | Phương án kế hoạch đang dùng | Người chịu trách nhiệm |
| --- | --- | --- |
| Eligibility/cohort đầu | Cư dân Vinhomes được mời hoặc link hợp lệ và đã được cấp policy; không auto mở vô hạn cho mọi account mới | Product + IAM/BQL pilot |
| Quota cụ thể | Limit ngày/tháng từng nhóm, override, concurrency và embedding/storage budget; chưa đặt thì chặn call/upload mới | Product + tài chính + vận hành |
| Quyền tài liệu Vin | Danh sách tài liệu thật, audience, approver, retention/xóa | Chủ nội dung từng domain |
| Liên kết IdP | OAuth/OIDC thật nếu có; nếu chưa có thì broker do Domain/IdP phát triển, không mock thành đã link | IAM + chủ hệ thống Domain |
| Eval policy | ≥5 ca, ≥80% chức năng, 100% an toàn đã chạy trên baseline (PR #99); chỉ cần xác nhận giữ nguyên cho agent cá nhân | Tech lead + QA/Product |
| Discord pilot | Bot riêng của từng khách qua trang Kênh, mặc định chỉ chủ tài khoản được nói chuyện và duyệt | Product + security + channel owner |
| Hàng đợi khi agent không xử lý được | Hàng đợi vận hành có sẵn trên Domain; ai nhận, SLA | Chủ nghiệp vụ Vinhomes |
| Capacity/SLO và rollback | Cohort size theo load test, alert receiver trực, số đo/điều kiện dừng rollout | DevOps + QA + Product |

Chưa cần thêm quyết định của chủ dự án để lập kế hoạch này. Khi bắt đầu triển khai thực tế, lấy các giá trị trên từ release config và sign-off; không để người code tự suy diễn thành một chính sách kinh doanh.

## 13. Checklist giao cho người triển khai

- [ ] Đã đọc cả hai phần; chốt source/runtime baseline và bảo toàn WIP, có branch/worktree và allowlist riêng.
- [ ] Schema principal/capability/link/billing/case và OpenAPI/event contract được Người 1 và Người 2 review.
- [ ] P0 secret, role và quota đạt trước khi mở key chung cho user thường.
- [ ] Shared/private Knowledge đúng ACL xuyên readiness/publish/runtime/citation/download/delete.
- [ ] Agent cá nhân, Leader/team, Builder/publish/eval, lịch và Discord có đầy đủ owner/quota/policy.
- [ ] Cư dân thật gửi Platform → agent giao việc qua Domain → staff nhận/xử lý/nộp bằng chứng trên Domain cũ → agent báo tiến độ/kết quả cho cư dân → consent/xác nhận có Domain receipt; không đi qua BQL.
- [ ] Staff giữ ứng dụng/tài khoản/quyền/queue/thông báo Domain trước và sau cutover; không cần tài khoản Platform để nhận việc.
- [ ] Ma trận U01–U30 có evidence theo môi trường; không gắn nhãn pass cho mục chưa chạy.
- [ ] Migration/dry-run/restore/rollback và capacity/SLO/alert có người nhận trách nhiệm.
- [ ] Chủ nghiệp vụ ký pilot trước khi tắt intake chatbot cũ; ticket cũ còn được theo dõi và không lặp yêu cầu.
- [ ] Chỉ mở thêm cohort/domain khi từng gate đạt; lưu riêng trạng thái chưa kiểm chứng hoặc chưa được nghiệm thu.

Kiểm tra tài liệu tách biệt với nghiệm thu ứng dụng: không coi code fence/link/schema examples hợp lệ là đã chạy U01–U30. Các sơ đồ Mermaid trong Phần 1 mô tả hợp đồng đích; hai người phải xác minh lại bằng flow runtime và Domain thực khi tích hợp.

## 14. Căn cứ và tài liệu liên quan

- [Audit source tính năng cá nhân](research/KIEM_TRA_TINH_NANG_CA_NHAN_VIN_2026-10-17.md): chat/Leader, Builder hiện hành, staging publish, eval, lịch, Discord và frontend admin.
- [Audit source phân quyền/dữ liệu](research/KIEM_TRA_PHAN_QUYEN_DU_LIEU_VIN_2026-10-17.md): auth, secret, resolver/KB và quota.
- [Nghiên cứu Domain, OAuth và MCP](research/NGHIEN_CUU_LIEN_KET_DOMAIN_VIN_2026-10-17.md): hợp đồng hiện tại, khoảng thiếu và tài liệu chuẩn chính thức.
- [Contract và phân công hai người theo dev_Chien](research/HOP_DONG_VA_PHAN_CONG_HAI_NGUOI_DEV_CHIEN_2026-10-18.md): tham chiếu source/tests và API đề xuất; không phải phần triển khai thứ ba. File owner và C01–C10 trong hai kế hoạch là mốc giao việc. Theo quyết định 18/10, **bỏ qua** các mục operator grant, management exceptions và hàng đợi ngoại lệ BQL trong tài liệu này; khi khác nhau, hai kế hoạch thắng.
- [Discord Gateway intents](https://docs.discord.com/developers/events/gateway#gateway-intents), [privileged intents](https://docs.discord.com/developers/events/gateway#privileged-intents), [Discord rate limits](https://docs.discord.com/developers/topics/rate-limits): đối chiếu điều kiện tích hợp kênh khi triển khai.
- [Discord OAuth2/bot install](https://docs.discord.com/developers/topics/oauth2#bot-authorization-flow), [Discord interaction responses](https://docs.discord.com/developers/interactions/receiving-and-responding#responding-to-an-interaction), [chính sách self-bot](https://support.discord.com/hc/en-us/articles/115002192352-Automated-User-Accounts-Self-Bots): phân biệt cài bot với liên kết danh tính, thời hạn interaction và bot identity.
- [Kế hoạch OP2 cũ](KE_HOACH_AGENT_TEAM_MCP_KNOWLEDGE_OP2_2026-10-17.md), [báo cáo dọn Docker](BAO_CAO_DON_DOCKER_VPS_PLATFORM_20261017.md): giữ làm hồ sơ lịch sử, không dùng snapshot cũ thay kiểm tra HEAD/runtime trước release. Tài liệu kiến trúc `KIEN_TRUC_HE_THONG_AI_WORKFORCE_PLATFORM.md` (mốc `develop2@6d13f7c1`) chưa từng được commit và không còn trên đĩa từ 18/10. Bản chẩn đoán Builder `c0ad625c` hiện nằm chưa track ở worktree `E:/AI-Workforce-Platform-bec/docs/`. Kết quả của nó đã được triển khai trong PR #99.
- [Hướng dẫn eval sandbox, Discord, lịch](../platform_VP/agentscope/docs/workforce/HUONG_DAN_EVAL_SANDBOX_DISCORD_LICH.md): cấu hình và giới hạn của phần đã có trên baseline. Mục 4.1 của hướng dẫn còn nhắc “lượt JEV”, đã lỗi thời sau khi gỡ JEV.

## 15. Lệnh kiểm tra Người 2 phải dùng khi triển khai

Những lệnh dưới đây **đã đối chiếu script/test/package hiện có nhưng chưa được chạy trong lần lập kế hoạch này**. Chạy trong môi trường dev/test riêng, không load credential/DSN production. Provider/MCP/Discord mặc định là fixture; ca live có tác động/chi phí phải đi đúng môi trường và phạm vi nghiệm thu đã được giao. Test mới cho feature mới vẫn phải bổ sung; chạy bộ cũ không đủ để công bố đã hoàn thiện.

### 15.1. Builder, publish và không có JEV

Tại `platform_VP/agentscope`, dùng Python 3.11 với dependency dev/service/storage/auth như CI:

```powershell
python scripts/workforce/check_builder.py
```

Khi Người 1 giao thay đổi storage/CAS hoặc trước RC, chạy biến thể `python scripts/workforce/check_builder.py --storage`. Script này chạy console/publish fixtures, chặn network, loại credential khỏi môi trường và ghi `.artifacts/builder-check/pytest.xml`, `summary.json`; nó không đo chất lượng/latency/cost của model thật.

Giữ `tests/workforce/console/test_builder_rollback.py`, gồm ca classifier không còn là credential/stage và proposal legacy không publish được nhưng giữ lịch sử. Sửa kỳ vọng seed key user-owned trong `tests/workforce/console/test_platform_credential.py` sau khi chuyển resolver. Không tạo `check_builder_jev.py` hoặc restore SDK/provider/checkpoint cũ để chữa test.

### 15.2. Chat/team, lịch, kênh và runtime

Tại `platform_VP/agentscope`, sau khi chọn DB/Redis test riêng:

```powershell
$env:PYTHONPATH = 'src;tests'
python -m pytest tests/personal_chat_test.py tests/personal_chat_challenge_test.py tests/team_collaboration_test.py tests/team_say_shared_context_test.py tests/team_shared_context_test.py tests/leader_evidence_middleware_test.py tests/leader_runtime_gaps_test.py tests/room_realtime_test.py --asyncio-mode=auto -q -rs
python -m pytest tests/schedule_router_test.py tests/service_scheduler_test.py tests/channel_discord_workforce_test.py tests/channel_gateway_test.py tests/channel_routing_test.py tests/channel_worker_test.py tests/channel_clients_test.py tests/channel_stream_test.py tests/channel_credential_binding_test.py tests/channel_feishu_credential_binding_test.py tests/channel_dingtalk_test.py tests/service_chat_channel_delivery_test.py --asyncio-mode=auto -q -rs
```

Các fixtures có thể chọn SQLite nếu thiếu PostgreSQL test URL. `GROUP_TEST_POSTGRES_URL` và `WORKFORCE_TEST_POSTGRES_URL` phải trỏ DB disposable khi chạy kiểm tra nhiều process; không báo PostgreSQL concurrency PASS nếu thực tế là SQLite/SKIP. Chạy thêm console eval/version/observability và full Phase D gates trong `.github/workflows/workforce-phase-d.yml` trước RC, với browser fixture và `BUILDER_UI_TEST_URL` thực sự hoạt động. UI demo/fixture pass không thay browser UAT toàn ứng dụng đã đăng nhập.

Người 2 bổ sung các ca chưa có: cách ly khách hàng với BQL và khách khác, C03 billing xuyên team/judge/memory, publish partial batch repair, shared KB đi qua readiness, sandbox manifest, schedule once lỗi/misfire/claim crash, Discord người ngoài allowlist bị bỏ qua và approver replay. Người 1 làm persistence/authority tests tương ứng; hai bộ giao nhau bằng C01–C10.

### 15.3. Frontend Platform

Tại `platform_VP/agentscope/examples/web_ui`, cài dependencies bằng lockfile hiện có rồi chạy:

```powershell
pnpm --filter frontend lint
pnpm --filter frontend build
pnpm --filter frontend test:office
```

`build` đã gồm `tsc -b && vite build`. Không gọi script `test`/`typecheck` chung vì package hiện không có chúng. Tại thư mục `frontend`, có thể chạy regression client/events hiện có:

```powershell
node --test tests/client.test.mjs tests/chat-events.test.mjs
```

Người 2 thêm test/browser phù hợp tính năng mới, dùng stack hiện có; dependency/gate Python/CI dùng chung gửi Người 1, frontend package/lock do Người 2 giữ. Browser cần kiểm tra responsive, bàn phím, empty/loading/error/blocked/expired/conflict, direct URL, SSE reconnect và role switch cho cư dân/BQL/admin. Không coi `test:office` là bộ test toàn bộ sản phẩm.

### 15.4. Nghiệm thu tích hợp hai người

| Lát chạy xuyên suốt | Người 1 chịu trách nhiệm chứng cứ | Người 2 chịu trách nhiệm chứng cứ |
| --- | --- | --- |
| Account → model → agent/Knowledge | Principal/catalog/redaction/quota/storage và RAG ACL đúng nguồn | Login/UI/runtime dùng đúng resolver, không key legacy, agent/readiness/publish/citation thật hoạt động |
| Cư dân → Domain → staff → khách hàng | Link/grant/intake/dedup, staff login/queue/work order, events/replay và state canonical | Leader/team, timeline safe, consent/next action, hiển thị tiến độ từ staff Domain và sync lỗi đúng |
| BQL không bị ảnh hưởng | Ticket `origin=platform` không vào route BQL; luồng `origin=domain` cũ còn chạy cho ticket đang mở | BQL đăng nhập, dùng Leader/Builder/agent như trước; không thấy dữ liệu cư dân |
| Eval/lịch/Discord | Sandbox/grants, run/identity/secret/lease/quota persistence | Model/tool actions, sandbox report, once/cron, session privacy/approval/delivery và cancel/retry |
| RC/pilot/cutover | Migration/backup/restore và Domain compatibility, staff regression | Build/manifest Platform, browser/load/canary/flags/monitoring; đóng gói báo cáo U01–U30 |

Gate phải chạy trên **cùng release candidate và contract version**, không ghép kết quả hai branch chưa tích hợp. Evidence có môi trường, source/image SHA, schema/API/config revisions, test ID, log/receipt đã che secret, kết quả PASS/FAIL/SKIP/PENDING và người kiểm. Paid model/RAG/Discord/partner UAT là lớp riêng; chưa chạy phải giữ PENDING.

## 16. Điều kiện hoàn tất phần Người 2

- [ ] N2-01…N2-10, gồm N2-09A/N2-09B, có code/test/handoff; đủ resource quota và consumer của C01–C10, không để tính năng production chạy fixture.
- [ ] Đã giao seed-removal slice sớm và sửa test kỳ vọng cũ; API/client không có key, workspace/import không vượt catalog chỉ đọc.
- [ ] Khách hàng dùng Leader ngay, chat riêng/nhóm, tự build agent/KB cá nhân để xử lý yêu cầu của mình; không thấy dữ liệu BQL hay khách khác.
- [ ] BQL dùng Platform như trước; admin quản trị quota/catalog/KB đúng quyền; staff chỉ tác nghiệp ở Domain cũ.
- [ ] Builder không có JEV, publish/eval/readiness/rollback đúng version/quyền và giữ bản đang dùng khi lỗi; report không coi mock/simulated là nghiệm thu thật.
- [ ] Lịch once/cron, Discord linked identity/approval/delivery và mọi paid call đều qua authority/quota; persistence do Người 1 cung cấp đã chạy được nhiều process.
- [ ] PR không sửa chồng file Người 1; router/dependency/storage delta được tích hợp qua owner trước RC.
- [ ] U01–U30 có coverage/evidence từng tầng; hai người cùng xác minh staff Domain và BQL/customer flow sau migration/restore.
- [ ] Chỉ cutover chatbot cư dân sau pilot và sign-off; giữ event workers, pending operations, emergency fallback và staff UI/workflow.

Người triển khai có thể bắt đầu ngay S0 với hai tài liệu này. Những quota/cohort/nội dung/IdP cần chủ nghiệp vụ chốt trước release nằm ở mục 12; chúng không phải lý do để bỏ trống code/fixture/contract hoặc chờ người thứ ba xây phần tích hợp.
