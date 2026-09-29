# Danh mục nhiệm vụ từng bảng

Sinh từ schema và `server/scripts/table-purposes.json`. Nhấn tên bảng để xem mọi trường, kiểu dữ liệu, khóa và ràng buộc.

[Luồng toàn hệ thống](../02_BUSINESS_ANALYSIS_IMPLEMENTATION.md) · [ERD quan hệ toàn dự án](PROJECT_RELATIONSHIPS.md)

## authorization

| Bảng | Nhiệm vụ | Liên kết tới |
|---|---|---|
| [auth_external_identity](authorization.md#auth_external_identity) | Ánh xạ issuer và subject từ IAM/SSO tới user local; không lưu mật khẩu cư dân. | `platform_tenant`, `users` |
| [auth_permission](authorization.md#auth_permission) | Danh mục quyền nguyên tử theo domain, tài nguyên, thao tác và mức rủi ro. | — |
| [auth_role](authorization.md#auth_role) | Vai trò hệ thống hoặc vai trò tùy chỉnh theo tenant; độc lập vai trò BQL và quản trị agent. | `platform_tenant` |
| [auth_role_assignment](authorization.md#auth_role_assignment) | Gán role cho thành viên tenant theo scope và thời hạn; thu hồi không sửa lịch sử định danh. | `platform_tenant`, `auth_role`, `platform_tenant_membership` |
| [auth_role_permission](authorization.md#auth_role_permission) | Các permission thuộc một role; role hệ thống do deployment quản lý. | `auth_role`, `auth_permission` |

## foundation-core

| Bảng | Nhiệm vụ | Liên kết tới |
|---|---|---|
| [accounts](foundation-core.md#accounts) | Liên kết người dùng với tài khoản nhà cung cấp đăng nhập, issuer và thông tin xác thực do Better Auth quản lý. | `users` |
| [agents](foundation-core.md#agents) | Danh tính agent duy nhất của sản phẩm; lễ tân, điều phối, kỹ thuật dùng chung registry này. Cấu hình transport tách khỏi phiên bản được phát hành. | `platform_tenant`, `deployment_packages` |
| [attachments](foundation-core.md#attachments) | File đính kèm trong hội thoại với vòng đời staged/sent; không thay evidence nghiệp vụ Vinhomes. | `platform_tenant`, `channels`, `users` |
| [audit_events](foundation-core.md#audit_events) | Audit append-only của nền OpenBot; tách với audit quản trị platform và business events Vinhomes. | `platform_tenant` |
| [channel_agents](foundation-core.md#channel_agents) | Danh sách agent được gắn vào một kênh; không thay roster có phiên bản của workflow. | `platform_tenant`, `channels`, `agents` |
| [channel_memberships](foundation-core.md#channel_memberships) | Quyền thành viên và dấu đã đọc của người dùng trên từng kênh OpenBot. | `platform_tenant`, `channels`, `users`, `platform_tenant_membership` |
| [channels](foundation-core.md#channels) | Hội thoại chuẩn của sản phẩm: cư dân, nhân viên hoặc nội bộ; membership quyết định quyền tham gia. | `users`, `platform_tenant`, `deployment_packages`, `agents` |
| [credentials](foundation-core.md#credentials) | Hạ tầng credential của nền sản phẩm cho model, connector, agent và MCP; không đưa secret vào AgentSpec hoặc message. | `platform_tenant` |
| [deployment_packages](foundation-core.md#deployment_packages) | Metadata gói cấu hình tenant mà OpenBot đã nạp, kèm đường dẫn/checksum; tenant_id text cũ không mặc nhiên là workforce tenant UUID. | — |
| [intelligence_channel_mappings](foundation-core.md#intelligence_channel_mappings) | Ánh xạ channel sang tài nguyên hội thoại của integration intelligence. | `platform_tenant`, `users`, `channels` |
| [revoked_access](foundation-core.md#revoked_access) | Ghi nhận quyền truy cập đã thu hồi để hệ thống từ chối các phiên hoặc chủ thể tương ứng. | — |
| [sessions](foundation-core.md#sessions) | Phiên đăng nhập của người dùng; khác workflow session xử lý nghiệp vụ của agent. | `users` |
| [sso_providers](foundation-core.md#sso_providers) | Cấu hình nhà cung cấp SSO và miền tổ chức; thuộc hạ tầng đăng nhập. | `users` |
| [user_instructions](foundation-core.md#user_instructions) | Hướng dẫn cá nhân do người dùng cấu hình cho trợ lý trong ứng dụng. | `users` |
| [user_roles](foundation-core.md#user_roles) | Vai trò quản trị/người dùng của nền OpenBot; không thay quyền tenant/property của workforce. | `users` |
| [users](foundation-core.md#users) | Danh tính người dùng dùng chung của OpenBot/Better Auth; Vinhomes và platform tham chiếu ID text này, không tạo tài khoản song song. | — |
| [verifications](foundation-core.md#verifications) | Dữ liệu xác minh có thời hạn phục vụ các luồng xác thực. | — |

## foundation-computer

| Bảng | Nhiệm vụ | Liên kết tới |
|---|---|---|
| [action_policy](foundation-computer.md#action_policy) | Chính sách thao tác computer/shell theo mô hình upstream; không phải quy tắc phê duyệt ActionRequest Vinhomes. | — |
| [computer_page_frame](foundation-computer.md#computer_page_frame) | Metadata frame/trang chụp trong phiên computer; quản lý retention riêng. | — |
| [computer_snapshot](foundation-computer.md#computer_snapshot) | Snapshot phiên computer phục vụ khôi phục hoặc điều tra tương tác desktop/browser. | — |

## foundation-coworker

| Bảng | Nhiệm vụ | Liên kết tới |
|---|---|---|
| [agent_preferences](foundation-coworker.md#agent_preferences) | Tùy chọn riêng của người dùng đối với agent, như ẩn agent khỏi danh sách. | `platform_tenant`, `users`, `agents` |
| [agent_profiles](foundation-coworker.md#agent_profiles) | Hồ sơ hiển thị, ownership, visibility và callback credential hash của agent. | `platform_tenant`, `agents`, `users` |
| [routine_runs](foundation-coworker.md#routine_runs) | Lịch sử kết quả mỗi lần thực hiện routine, gồm thành công/thất bại/bỏ qua. | `platform_tenant`, `routines` |
| [routine_sweeps](foundation-coworker.md#routine_sweeps) | Dấu xử lý lượt quét lịch routine giúp scheduler tránh chạy trùng hoặc bỏ sót. | — |
| [routines](foundation-coworker.md#routines) | Tác vụ định kỳ của nền sản phẩm: cấu hình lịch chạy và chủ sở hữu. | `platform_tenant`, `users`, `agents` |

## foundation-components

| Bảng | Nhiệm vụ | Liên kết tới |
|---|---|---|
| [component_exclusions](foundation-components.md#component_exclusions) | Cấu hình loại trừ component theo scope của nền sản phẩm. | `components`, `agents` |
| [component_functions](foundation-components.md#component_functions) | Các function được khai báo cho component để phục vụ gọi và kiểm soát chức năng. | `components` |
| [components](foundation-components.md#components) | Metadata component được quản lý bởi shell/plugin infrastructure. | — |

## foundation-plugins

| Bảng | Nhiệm vụ | Liên kết tới |
|---|---|---|
| [composio_connections](foundation-plugins.md#composio_connections) | Kết nối Composio đã thiết lập, trạng thái và tham chiếu tài khoản/credential liên quan. | `platform_tenant` |
| [mcp_servers](foundation-plugins.md#mcp_servers) | Kết nối MCP duy nhất theo tenant; giữ endpoint, provider và tham chiếu credential. | `platform_tenant`, `credentials` |
| [mcp_tools](foundation-plugins.md#mcp_tools) | Cache công cụ do MCP server quảng bá; có thể làm mới. Không phải lịch sử phiên bản hoặc bằng chứng được phép gọi. | `platform_tenant`, `mcp_servers` |
| [mcp_user_credentials](foundation-plugins.md#mcp_user_credentials) | Liên kết người dùng/MCP server/credential cho truy cập thay mặt từng người. | `platform_tenant`, `mcp_servers`, `users`, `credentials` |
| [plugin_grants](foundation-plugins.md#plugin_grants) | Các grant sử dụng plugin/resource trong ứng dụng theo ownership upstream. | `platform_tenant`, `agents` |
| [sandboxed_components](foundation-plugins.md#sandboxed_components) | Component thực thi trong sandbox cùng cấu hình và metadata an toàn. | `platform_tenant` |
| [skill_tools](foundation-plugins.md#skill_tools) | Ánh xạ skill của nền sản phẩm sang tool mà skill cung cấp. | `platform_tenant`, `skills` |
| [skills](foundation-plugins.md#skills) | Skill chuẩn của sản phẩm: chủ sở hữu, nội dung nháp và tên lệnh; lịch sử bất biến ở platform_skill_version. | `platform_tenant`, `users` |

## foundation-work

| Bảng | Nhiệm vụ | Liên kết tới |
|---|---|---|
| [work_items](foundation-work.md#work_items) | Hàng công việc bền vững của worker chung; không phải business Task hay workflow RunStep. | — |

## foundation-voice

| Bảng | Nhiệm vụ | Liên kết tới |
|---|---|---|
| [voice_sessions](foundation-voice.md#voice_sessions) | Metadata phiên thoại của người dùng/agent trong ứng dụng. | `platform_tenant`, `channels`, `users` |

## platform-identity

| Bảng | Nhiệm vụ | Liên kết tới |
|---|---|---|
| [platform_tenant](platform-identity.md#platform_tenant) | Đơn vị sở hữu và cô lập dữ liệu workforce; một tenant có thể quản lý nhiều dự án. | — |
| [platform_tenant_membership](platform-identity.md#platform_tenant_membership) | Quan hệ có thời hạn giữa user và tenant, là điều kiện nền trước khi cấp scope nghiệp vụ. | `platform_tenant`, `users` |

## platform-domains

| Bảng | Nhiệm vụ | Liên kết tới |
|---|---|---|
| [platform_domain_installation](platform-domains.md#platform_domain_installation) | Cài đặt một domain package vào tenant/environment với cấu hình và trạng thái bật/tắt. | `platform_tenant`, `platform_domain_package` |
| [platform_domain_package](platform-domains.md#platform_domain_package) | Danh mục toàn cục các phiên bản package nghiệp vụ và phiên bản contract hỗ trợ. | — |

## platform-agents

| Bảng | Nhiệm vụ | Liên kết tới |
|---|---|---|
| [platform_agent_change_request](platform-agents.md#platform_agent_change_request) | Yêu cầu thay đổi agent để theo dõi đề nghị, người yêu cầu và kết quả xử lý. | `platform_tenant`, `agents`, `users` |
| [platform_agent_spec](platform-agents.md#platform_agent_spec) | Mục tiêu, hướng dẫn, input/output schema và cấu hình hành vi của đúng một AgentVersion. | `platform_tenant`, `platform_agent_version` |
| [platform_agent_version](platform-agents.md#platform_agent_version) | Một phiên bản agent có spec hash và lifecycle đánh giá/publish/suspend/retire. | `platform_tenant`, `agents`, `users` |

## platform-capabilities

| Bảng | Nhiệm vụ | Liên kết tới |
|---|---|---|
| [platform_capability](platform-capabilities.md#platform_capability) | Danh mục năng lực được quản trị trong tenant, kèm loại và mức rủi ro. | `platform_tenant`, `users` |
| [platform_mcp_server_version](platform-capabilities.md#platform_mcp_server_version) | Snapshot schema/fingerprint của MCP server và trạng thái kiểm duyệt bảo mật. | `platform_tenant`, `mcp_servers` |
| [platform_model_profile](platform-capabilities.md#platform_model_profile) | Cấu hình model/provider được phép dùng, không chứa API key. | `platform_tenant` |
| [platform_skill_version](platform-capabilities.md#platform_skill_version) | Nội dung skill bất biến qua content reference và checksum. | `platform_tenant`, `skills` |
| [platform_tool](platform-capabilities.md#platform_tool) | Định danh thao tác được quản trị: MCP gắn server+tên tool; DOMAIN/BUILTIN gắn handler. Một danh tính cho mỗi đích thực thi. | `mcp_servers`, `platform_tenant` |
| [platform_tool_version](platform-capabilities.md#platform_tool_version) | Phiên bản tool với input/output schema và fingerprint để agent ghim chính xác. | `platform_tenant`, `platform_tool`, `platform_mcp_server_version` |

## platform-bindings

| Bảng | Nhiệm vụ | Liên kết tới |
|---|---|---|
| [platform_agent_capability_binding](platform-bindings.md#platform_agent_capability_binding) | Năng lực và giới hạn scope được cấp cho một AgentVersion. | `platform_tenant`, `platform_agent_version`, `platform_capability` |
| [platform_agent_knowledge_binding](platform-bindings.md#platform_agent_knowledge_binding) | Knowledge base và retrieval policy mà AgentVersion được truy cập. | `platform_tenant`, `platform_agent_version`, `platform_knowledge_base` |
| [platform_agent_model_binding](platform-bindings.md#platform_agent_model_binding) | Model profile và constraints mà AgentVersion dùng để thực thi. | `platform_tenant`, `platform_agent_version`, `platform_model_profile` |
| [platform_agent_policy_binding](platform-bindings.md#platform_agent_policy_binding) | PolicyVersion áp dụng cho AgentVersion ở các pha trước/sau chạy tool hoặc đầu ra. | `platform_tenant`, `platform_agent_version`, `platform_policy_version` |
| [platform_agent_skill_binding](platform-bindings.md#platform_agent_skill_binding) | SkillVersion cụ thể và cấu hình được ghim trong AgentVersion. | `platform_tenant`, `platform_agent_version`, `platform_skill_version` |
| [platform_agent_tool_binding](platform-bindings.md#platform_agent_tool_binding) | ToolVersion cụ thể được AgentVersion gọi, cùng phạm vi và chính sách approval. | `platform_tenant`, `platform_agent_version`, `platform_tool_version` |

## platform-knowledge

| Bảng | Nhiệm vụ | Liên kết tới |
|---|---|---|
| [platform_knowledge_base](platform-knowledge.md#platform_knowledge_base) | Kho tri thức có chủ sở hữu, phân loại bảo mật và trạng thái truy cập. | `platform_tenant`, `users` |
| [platform_knowledge_revision](platform-knowledge.md#platform_knowledge_revision) | Bản nội dung tài liệu có hash, storage reference và quyết định phê duyệt. | `platform_tenant`, `platform_knowledge_source`, `users` |
| [platform_knowledge_source](platform-knowledge.md#platform_knowledge_source) | Nguồn tài liệu/URI thuộc một knowledge base, chưa phải một bản revision cụ thể. | `platform_tenant`, `platform_knowledge_base`, `users` |

## platform-policies

| Bảng | Nhiệm vụ | Liên kết tới |
|---|---|---|
| [platform_policy](platform-policies.md#platform_policy) | Danh tính chính sách quản trị theo tenant và loại policy. | `platform_tenant`, `users` |
| [platform_policy_version](platform-policies.md#platform_policy_version) | Phiên bản nội dung policy có ngôn ngữ biểu diễn, hash và lifecycle publish. | `platform_tenant`, `platform_policy` |

## platform-evaluation

| Bảng | Nhiệm vụ | Liên kết tới |
|---|---|---|
| [platform_eval_assertion](platform-evaluation.md#platform_eval_assertion) | Kết quả bất biến của một tiêu chí kiểm tra trên eval case/run. | `platform_tenant`, `platform_eval_run`, `platform_eval_case` |
| [platform_eval_case](platform-evaluation.md#platform_eval_case) | Một tình huống đánh giá gồm input, expected output, severity và tags. | `platform_tenant`, `platform_eval_suite` |
| [platform_eval_evidence](platform-evaluation.md#platform_eval_evidence) | Tham chiếu bằng chứng/artifact/trace hỗ trợ một kết quả đánh giá. | `platform_tenant`, `platform_eval_run`, `platform_eval_assertion` |
| [platform_eval_run](platform-evaluation.md#platform_eval_run) | Lần đánh giá AgentVersion bằng suite được ghim, lưu môi trường/model và kết quả. | `platform_tenant`, `platform_agent_version`, `platform_eval_suite` |
| [platform_eval_suite](platform-evaluation.md#platform_eval_suite) | Bộ kiểm thử đánh giá có version, loại và owner; các case đóng băng khi suite đã được chạy. | `platform_tenant`, `users` |
| [platform_publish_approval](platform-evaluation.md#platform_publish_approval) | Quyết định reviewer theo vai trò DOMAIN/EVALUATION/SECURITY/PLATFORM, độc lập với tác giả. | `platform_tenant`, `platform_publish_gate`, `users` |
| [platform_publish_gate](platform-evaluation.md#platform_publish_gate) | Một đợt xét điều kiện publish AgentVersion, tập hợp kết quả gate và approvals. | `platform_tenant`, `platform_agent_version` |
| [platform_publish_gate_result](platform-evaluation.md#platform_publish_gate_result) | Kết quả CONTRACT/QUALITY/SAFETY/REGRESSION của một đợt xét publish. | `platform_tenant`, `platform_publish_gate` |
| [platform_regression_baseline](platform-evaluation.md#platform_regression_baseline) | Phiên bản agent được chấp thuận làm mốc so sánh regression cho suite. | `platform_tenant`, `agents`, `platform_agent_version`, `platform_eval_suite`, `users` |

## platform-deployments

| Bảng | Nhiệm vụ | Liên kết tới |
|---|---|---|
| [platform_agent_deployment](platform-deployments.md#platform_agent_deployment) | Triển khai AgentVersion vào environment/scope; rollback dùng deployment/version cũ, không sửa lịch sử spec. | `platform_tenant`, `platform_agent_version`, `platform_domain_installation`, `platform_agent_deployment` |

## platform-runtime

| Bảng | Nhiệm vụ | Liên kết tới |
|---|---|---|
| [platform_action_proposal](platform-runtime.md#platform_action_proposal) | Đề xuất hành động từ runtime gửi tới domain; không tự cấp quyền thực thi nghiệp vụ. | `platform_tenant`, `platform_runtime_decision`, `platform_workflow_session`, `platform_agent_run` |
| [platform_agent_run](platform-runtime.md#platform_agent_run) | Một lần gọi AgentVersion trong step/session, lưu input/output snapshot và trace. | `platform_tenant`, `platform_workflow_session`, `platform_run_step`, `agents`, `platform_agent_version` |
| [platform_execution_grant_ref](platform-runtime.md#platform_execution_grant_ref) | Soft reference tới grant của domain, với payload hash và hạn hiệu lực; không chứa secret thực thi. | `platform_tenant`, `platform_action_proposal` |
| [platform_run_step](platform-runtime.md#platform_run_step) | Bước thực thi trong workflow, kèm input/output, lần thử và trạng thái. | `platform_tenant`, `platform_workflow_session` |
| [platform_run_step_dependency](platform-runtime.md#platform_run_step_dependency) | Quan hệ tiền nhiệm giữa các bước trong cùng session; graph không được có chu trình. | `platform_tenant`, `platform_workflow_session`, `platform_run_step` |
| [platform_runtime_artifact](platform-runtime.md#platform_runtime_artifact) | Artifact có cấu trúc hoặc external storage reference do agent run tạo ra. | `platform_tenant`, `platform_agent_run` |
| [platform_runtime_decision](platform-runtime.md#platform_runtime_decision) | Quyết định vận hành được công bố trong workflow và run đã tạo quyết định đó. | `platform_tenant`, `platform_workflow_session`, `platform_agent_run` |
| [platform_tool_call](platform-runtime.md#platform_tool_call) | Lần gọi ToolVersion của agent run, kết quả policy, request/response và trạng thái. | `platform_tenant`, `platform_agent_run`, `platform_tool_version` |
| [platform_workflow_session](platform-runtime.md#platform_workflow_session) | Một đợt phối hợp xử lý subject nghiệp vụ qua soft reference, tách khỏi conversation và vòng đời ticket. | `platform_tenant` |

## platform-memory

| Bảng | Nhiệm vụ | Liên kết tới |
|---|---|---|
| [platform_memory_item](platform-memory.md#platform_memory_item) | Danh tính một mục memory với loại, nguồn và trạng thái. | `platform_tenant`, `platform_memory_namespace` |
| [platform_memory_namespace](platform-memory.md#platform_memory_namespace) | Phạm vi semantic memory theo tenant/domain/user/agent và retention policy. | `platform_tenant` |
| [platform_memory_review](platform-memory.md#platform_memory_review) | Lịch sử phê duyệt/từ chối/thu hồi memory revision; append-only. | `platform_tenant`, `platform_memory_revision`, `users` |
| [platform_memory_revision](platform-memory.md#platform_memory_revision) | Revision nội dung memory có hash/storage reference và trạng thái redaction. | `platform_tenant`, `platform_memory_item` |
| [platform_memory_vector_ref](platform-memory.md#platform_memory_vector_ref) | Metadata liên kết revision đã được duyệt với điểm Qdrant và trạng thái đồng bộ/xóa. | `platform_tenant`, `platform_memory_revision` |

## platform-audit

| Bảng | Nhiệm vụ | Liên kết tới |
|---|---|---|
| [platform_audit_event](platform-audit.md#platform_audit_event) | Audit append-only của quản trị/runtime platform, có actor/correlation/trace. | `platform_tenant` |
| [platform_idempotency_record](platform-audit.md#platform_idempotency_record) | Chống lặp command platform bằng tenant/key/request hash và response đã lưu. | `platform_tenant` |
| [platform_outbox_event](platform-audit.md#platform_outbox_event) | Sự kiện platform chờ phát ra ngoài transaction, kèm retry và lease metadata. | `platform_tenant` |

## vinhomes-property

| Bảng | Nhiệm vụ | Liên kết tới |
|---|---|---|
| [vh_apartment](vinhomes-property.md#vh_apartment) | Căn hộ thuộc đúng tòa/dự án, với mã, tầng và trạng thái sử dụng. | `platform_tenant`, `vh_project`, `vh_tower` |
| [vh_membership_application](vinhomes-property.md#vh_membership_application) | Hồ sơ xin quyền cư dân, căn hộ yêu cầu và quyết định xét duyệt; hồ sơ không tự cấp quyền. | `platform_tenant`, `vh_project`, `vh_apartment`, `users` |
| [vh_project](vinhomes-property.md#vh_project) | Dự án/khu đô thị thuộc tenant, gốc phạm vi nghiệp vụ Vinhomes. | `platform_tenant` |
| [vh_property_membership](vinhomes-property.md#vh_property_membership) | Quyền cư dân/nhân viên/quản lý/nhà thầu theo project/tower/apartment và khoảng hiệu lực. | `platform_tenant`, `vh_project`, `users`, `vh_tower`, `vh_apartment`, `platform_tenant_membership` |
| [vh_tower](vinhomes-property.md#vh_tower) | Tòa nhà thuộc một dự án, có code unique trong dự án. | `platform_tenant`, `vh_project` |

## vinhomes-intake

| Bảng | Nhiệm vụ | Liên kết tới |
|---|---|---|
| [vh_case](vinhomes-intake.md#vh_case) | H? s? ti?p nh?n c? d?n, tr?ng th?i l?m r? v? danh s?ch IssueCandidate P0 trong intake_state_json. | `platform_tenant`, `vh_project`, `users`, `vh_apartment`, `vh_property_membership` |
| [vh_feedback](vinhomes-intake.md#vh_feedback) | Đánh giá của cư dân về phản ánh, độc lập với lệnh thay đổi trạng thái incident. | `platform_tenant`, `vh_project`, `vh_resident_report`, `users` |
| [vh_resident_confirmation](vinhomes-intake.md#vh_resident_confirmation) | Ý kiến chấp nhận/yêu cầu mở lại của reporter theo đúng vòng resolution hiện tại. | `platform_tenant`, `vh_project`, `vh_resident_report`, `vh_incident`, `users` |
| [vh_resident_report](vinhomes-intake.md#vh_resident_report) | Phản ánh chính thức của một cư dân; có thể được gắn vào incident chung với nhiều phản ánh. | `platform_tenant`, `vh_project`, `vh_case`, `vh_incident`, `users`, `vh_property_membership`, `vh_apartment` |
| [vh_resident_request](vinhomes-intake.md#vh_resident_request) | Một thông điệp/đầu vào đã làm sạch của cư dân trong Case, có idempotency key. | `platform_tenant`, `vh_project`, `vh_case`, `users` |

## vinhomes-operations

| Bảng | Nhiệm vụ | Liên kết tới |
|---|---|---|
| [vh_action_approval](vinhomes-operations.md#vh_action_approval) | Quyết định phê duyệt có thời hạn, ghim đúng payload hash và policy version. | `platform_tenant`, `vh_project`, `vh_action_request`, `users` |
| [vh_action_request](vinhomes-operations.md#vh_action_request) | Yêu cầu hành động nghiệp vụ được domain tiếp nhận, ghim payload/hash/policy và expected version. | `platform_tenant`, `vh_project`, `vh_incident`, `vh_task` |
| [vh_checklist](vinhomes-operations.md#vh_checklist) | Danh tính bộ tiêu chí nghiệm thu/công việc theo tenant và category. | `platform_tenant` |
| [vh_checklist_version](vinhomes-operations.md#vh_checklist_version) | Phiên bản tiêu chí được work order ghim; bản đã publish không sửa nội dung. | `platform_tenant`, `vh_checklist`, `users` |
| [vh_execution_grant](vinhomes-operations.md#vh_execution_grant) | Quyền thực thi do domain phát hành, lưu token hash, hạn và trạng thái tiêu thụ/thu hồi. | `platform_tenant`, `vh_project`, `vh_action_request` |
| [vh_incident](vinhomes-operations.md#vh_incident) | Sự cố vận hành chuẩn; UI có thể gọi Ticket. Trạng thái sự cố là nguồn thật, không lấy từ agent run. | `platform_tenant`, `vh_project`, `vh_tower`, `users` |
| [vh_incident_relation](vinhomes-operations.md#vh_incident_relation) | Liên kết các sự cố trùng/lặp/nguyên nhân/chặn/liên quan để hỗ trợ triage và recurrence. | `platform_tenant`, `vh_project`, `vh_incident`, `users` |
| [vh_rule_evaluation](vinhomes-operations.md#vh_rule_evaluation) | Kết quả ALLOW/REQUIRE_APPROVAL/DENY bất biến đối với đúng action payload. | `platform_tenant`, `vh_project`, `vh_action_request` |
| [vh_task](vinhomes-operations.md#vh_task) | C?ng vi?c thu?c Incident, ti?n ?? v? ph? thu?c P0 l?u ? depends_on_json; kh?ng d?ng b?ng Task c?a runtime. | `platform_tenant`, `vh_project`, `vh_incident` |
| [vh_work_order](vinhomes-operations.md#vh_work_order) | Một lần thực hiện task được ActionRequest cho phép; redo tạo attempt mới thay vì reset lần cũ. | `platform_tenant`, `vh_project`, `vh_incident`, `vh_task`, `vh_action_request`, `vh_work_order`, `vh_checklist_version` |

## vinhomes-files

| Bảng | Nhiệm vụ | Liên kết tới |
|---|---|---|
| [vh_file_object](vinhomes-files.md#vh_file_object) | Metadata file trong object storage, checksum, người tải, quét an toàn và visibility. | `platform_tenant`, `users` |

## vinhomes-evidence

| Bảng | Nhiệm vụ | Liên kết tới |
|---|---|---|
| [vh_evidence_ref](vinhomes-evidence.md#vh_evidence_ref) | Bằng chứng file gắn vào incident/task/work order và giai đoạn BEFORE/AFTER/QC. | `platform_tenant`, `vh_project`, `vh_incident`, `vh_task`, `vh_work_order`, `vh_file_object`, `users` |
| [vh_qc_result](vinhomes-evidence.md#vh_qc_result) | Quyết định kiểm tra chất lượng bất biến cho một work order, gồm tiêu chí không đạt và yêu cầu redo. | `platform_tenant`, `vh_project`, `vh_incident`, `vh_task`, `vh_work_order`, `users` |
| [vh_qc_result_evidence](vinhomes-evidence.md#vh_qc_result_evidence) | Liên kết quyết định QC với bằng chứng hỗ trợ. | `platform_tenant`, `vh_project`, `vh_incident`, `vh_qc_result`, `vh_evidence_ref` |
| [vh_root_cause_evidence](vinhomes-evidence.md#vh_root_cause_evidence) | Bằng chứng hỗ trợ nhận định nguyên nhân gốc. | `platform_tenant`, `vh_project`, `vh_root_cause_finding`, `vh_evidence_ref` |
| [vh_root_cause_finding](vinhomes-evidence.md#vh_root_cause_finding) | Nhận định nguyên nhân gốc của sự cố, có trạng thái xác nhận và chủ thể tạo. | `platform_tenant`, `vh_project`, `vh_incident` |
| [vh_root_cause_incident](vinhomes-evidence.md#vh_root_cause_incident) | Những incident liên quan tới một nhận định nguyên nhân gốc. | `platform_tenant`, `vh_project`, `vh_root_cause_finding`, `vh_incident` |

## vinhomes-attachments

| Bảng | Nhiệm vụ | Liên kết tới |
|---|---|---|
| [vh_membership_application_file](vinhomes-attachments.md#vh_membership_application_file) | Liên kết bằng chứng riêng tư với hồ sơ xin membership. | `platform_tenant`, `vh_project`, `vh_membership_application`, `vh_file_object` |
| [vh_pet_document](vinhomes-attachments.md#vh_pet_document) | Tài liệu chứng minh cho hồ sơ vật nuôi, tham chiếu file object. | `platform_tenant`, `vh_project`, `vh_pet_profile`, `vh_file_object` |
| [vh_report_attachment](vinhomes-attachments.md#vh_report_attachment) | Liên kết file với phản ánh chính thức, dùng lại file object thay vì sao chép binary. | `platform_tenant`, `vh_project`, `vh_resident_report`, `vh_file_object` |
| [vh_request_attachment](vinhomes-attachments.md#vh_request_attachment) | Giữ file của request ngay khi chưa có incident, không làm mất bằng chứng trong intake. | `platform_tenant`, `vh_project`, `vh_resident_request`, `vh_file_object` |
| [vh_service_request_file](vinhomes-attachments.md#vh_service_request_file) | Các hồ sơ/file kèm đăng ký dịch vụ hoặc thi công. | `platform_tenant`, `vh_project`, `vh_service_request`, `vh_file_object` |

## vinhomes-communication

| Bảng | Nhiệm vụ | Liên kết tới |
|---|---|---|
| [vh_business_event](vinhomes-communication.md#vh_business_event) | Sự kiện nghiệp vụ append-only, lưu actor và subject version để tạo timeline/outbox/projection. | `platform_tenant`, `vh_project`, `vh_incident` |
| [vh_message](vinhomes-communication.md#vh_message) | Trao đổi nghiệp vụ gắn incident/report, phân biệt nội bộ và cư dân được xem; không phải command. | `platform_tenant`, `vh_project`, `vh_incident`, `vh_resident_report` |
| [vh_notification](vinhomes-communication.md#vh_notification) | Thông báo đã lọc cho một recipient, có dedupe key và read state; không phải toàn bộ timeline nội bộ. | `platform_tenant`, `vh_project`, `vh_business_event`, `users` |

## vinhomes-services

| Bảng | Nhiệm vụ | Liên kết tới |
|---|---|---|
| [vh_access_card](vinhomes-services.md#vh_access_card) | Đăng ký/cấp/thu hồi thẻ ra vào, lưu provider token reference thay raw access secret. | `platform_tenant`, `vh_project`, `vh_property_membership` |
| [vh_camera_request](vinhomes-services.md#vh_camera_request) | Yêu cầu xem camera theo vị trí/khoảng thời gian/mục đích, có reviewer và hạn truy cập. | `platform_tenant`, `vh_project`, `vh_apartment`, `vh_property_membership`, `vh_map_place`, `users` |
| [vh_charging_session](vinhomes-services.md#vh_charging_session) | Phiên sạc xe có thiết bị/connector, năng lượng, phí và provider reference; trạng thái cần receipt thực tế. | `platform_tenant`, `vh_project`, `vh_apartment`, `vh_property_membership`, `vh_map_place` |
| [vh_construction_permit](vinhomes-services.md#vh_construction_permit) | Giấy phép thi công theo service request, nhà thầu, ngày và giờ được phép. | `platform_tenant`, `vh_project`, `vh_service_request` |
| [vh_face_enrollment](vinhomes-services.md#vh_face_enrollment) | Đồng ý và trạng thái đăng ký nhận diện, chỉ lưu provider reference và dấu yêu cầu/xác nhận xóa. | `platform_tenant`, `vh_project`, `vh_property_membership` |
| [vh_handover](vinhomes-services.md#vh_handover) | Lịch bàn giao căn hộ cho membership cư dân, checklist và kết quả hoàn thành. | `platform_tenant`, `vh_project`, `vh_apartment`, `vh_property_membership`, `vh_checklist_version` |
| [vh_intercom_event](vinhomes-services.md#vh_intercom_event) | Receipt sự kiện intercom từ provider, append-only và dedupe provider event. | `platform_tenant`, `vh_project`, `vh_apartment`, `vh_visitor_pass` |
| [vh_parking_permit](vinhomes-services.md#vh_parking_permit) | Quyền đỗ xe theo căn hộ/membership và biển số; unique biển số active trong dự án. | `platform_tenant`, `vh_project`, `vh_apartment`, `vh_property_membership` |
| [vh_pet_profile](vinhomes-services.md#vh_pet_profile) | Đăng ký vật nuôi thuộc căn hộ/membership, thông tin tiêm phòng và trạng thái xét duyệt. | `platform_tenant`, `vh_project`, `vh_apartment`, `vh_property_membership` |
| [vh_service_request](vinhomes-services.md#vh_service_request) | Đăng ký dịch vụ cư dân có loại và payload có schema version; không tạo ticket giả cho mọi dịch vụ. | `platform_tenant`, `vh_project`, `vh_apartment`, `vh_property_membership` |
| [vh_visitor_pass](vinhomes-services.md#vh_visitor_pass) | Giấy phép khách thăm có khoảng hiệu lực gắn với service request đã xét duyệt. | `platform_tenant`, `vh_project`, `vh_service_request` |

## vinhomes-booking

| Bảng | Nhiệm vụ | Liên kết tới |
|---|---|---|
| [vh_booking](vinhomes-booking.md#vh_booking) | Đặt/giữ chỗ tiện ích cho membership/căn hộ với snapshot giá và vòng đời hủy/hết hạn/hoàn thành. | `platform_tenant`, `vh_project`, `vh_time_slot`, `vh_apartment`, `vh_property_membership` |
| [vh_facility](vinhomes-booking.md#vh_facility) | Tiện ích có capacity, biểu phí và booking policy của dự án. | `platform_tenant`, `vh_project`, `vh_map_place` |
| [vh_time_slot](vinhomes-booking.md#vh_time_slot) | Khung giờ của tiện ích; không chồng thời gian cùng facility và có capacity riêng. | `platform_tenant`, `vh_project`, `vh_facility` |

## vinhomes-billing

| Bảng | Nhiệm vụ | Liên kết tới |
|---|---|---|
| [vh_fee_schedule](vinhomes-billing.md#vh_fee_schedule) | Phiên bản biểu phí và hiệu lực áp dụng; nội dung bản đã publish được giữ bất biến. | `platform_tenant`, `vh_project` |
| [vh_invoice](vinhomes-billing.md#vh_invoice) | Hóa đơn của căn hộ/người nhận với kỳ, hạn, tiền tệ và tổng tiền đối chiếu các dòng/phân bổ. | `platform_tenant`, `vh_project`, `vh_apartment`, `users` |
| [vh_invoice_line](vinhomes-billing.md#vh_invoice_line) | Dòng hóa đơn có quantity/đơn giá/tổng làm tròn; không sửa sau khi hóa đơn issue. | `platform_tenant`, `vh_project`, `vh_invoice`, `vh_fee_schedule` |
| [vh_loyalty_balance](vinhomes-billing.md#vh_loyalty_balance) | S? d? v? h?ng ?i?m theo ch??ng tr?nh c? d?n; snapshot t? nh? cung c?p, kh?ng ph?i s? c?i thanh to?n. | `platform_tenant`, `users` |
| [vh_payment_allocation](vinhomes-billing.md#vh_payment_allocation) | Sổ phân bổ thanh toán thành công vào hóa đơn, bất biến và không cho vượt dư nợ/giá trị payment. | `platform_tenant`, `vh_project`, `vh_payment_attempt`, `vh_invoice` |
| [vh_payment_attempt](vinhomes-billing.md#vh_payment_attempt) | Một lần thử thanh toán có idempotency/provider ref; SIMULATED không được quyết toán hóa đơn. | `platform_tenant`, `vh_project`, `vh_invoice`, `users` |

## vinhomes-content

| Bảng | Nhiệm vụ | Liên kết tới |
|---|---|---|
| [vh_community_event](vinhomes-content.md#vh_community_event) | Sự kiện cộng đồng có lịch, nơi tổ chức, hạn đăng ký và capacity. | `platform_tenant`, `vh_project`, `vh_map_place` |
| [vh_content_item](vinhomes-content.md#vh_content_item) | Tin tức/sổ tay/thông báo của dự án với lịch publish/hết hạn. | `platform_tenant`, `vh_project` |
| [vh_event_registration](vinhomes-content.md#vh_event_registration) | Đăng ký sự kiện theo membership, số khách và trạng thái tham dự/hủy. | `platform_tenant`, `vh_project`, `vh_community_event`, `vh_property_membership` |
| [vh_map_place](vinhomes-content.md#vh_map_place) | Địa điểm/điểm dịch vụ trên bản đồ, có thể gắn tòa và tọa độ. | `platform_tenant`, `vh_project`, `vh_tower` |
| [vh_miniapp_catalog](vinhomes-content.md#vh_miniapp_catalog) | Danh mục ứng dụng/dịch vụ liên kết được phép hiển thị trong dự án. | `platform_tenant`, `vh_project` |
| [vh_offer](vinhomes-content.md#vh_offer) | Ưu đãi đối tác có điều kiện, thời hạn và URL đích cần được kiểm duyệt. | `platform_tenant`, `vh_project` |
| [vh_sensor_reading](vinhomes-content.md#vh_sensor_reading) | Quan trắc cảm biến bất biến theo vị trí/thời gian và chất lượng dữ liệu. | `platform_tenant`, `vh_project`, `vh_map_place` |
| [vh_transit_route](vinhomes-content.md#vh_transit_route) | Tuyến xe và phiên bản lịch chạy; không mặc nhiên là thời gian đến realtime. | `platform_tenant`, `vh_project` |
| [vh_transit_route_stop](vinhomes-content.md#vh_transit_route_stop) | Thứ tự các điểm dừng trên một tuyến, bảo đảm cùng project. | `platform_tenant`, `vh_project`, `vh_transit_route`, `vh_transit_stop` |
| [vh_transit_stop](vinhomes-content.md#vh_transit_stop) | Điểm dừng trong dự án với tọa độ đã kiểm tra miền giá trị. | `platform_tenant`, `vh_project` |

## vinhomes-delivery

| Bảng | Nhiệm vụ | Liên kết tới |
|---|---|---|
| [vh_command_receipt](vinhomes-delivery.md#vh_command_receipt) | Kết quả command theo tenant/user/loại/key, ghim payload hash; retry trả kết quả đã commit. | `platform_tenant`, `users` |
| [vh_outbox](vinhomes-delivery.md#vh_outbox) | Hàng gửi business event tới đích, có retry/lease/delivery state và unique event/destination. | `platform_tenant`, `vh_project`, `vh_business_event` |

## platform-conversations

| Bảng | Nhiệm vụ | Liên kết tới |
|---|---|---|
| [channel_messages](platform-conversations.md#channel_messages) | Lịch sử chat chính trong PostgreSQL: người/agent gửi, nội dung, thứ tự, phiên bản và nguồn; ghi nối tiếp, chống trùng và phát outbox. | `agents`, `platform_agent_version`, `platform_tenant`, `channels`, `users`, `channel_messages` |
| [channel_subjects](platform-conversations.md#channel_subjects) | Liên kết hội thoại với hồ sơ nghiệp vụ để lễ tân tìm đúng phản ánh/sự cố; tham chiếu mềm được service xác thực. | `platform_tenant`, `channels` |

## platform-collaboration

| Bảng | Nhiệm vụ | Liên kết tới |
|---|---|---|
| [platform_handoff](platform-collaboration.md#platform_handoff) | Bàn giao bền vững từ conversation/session tới agent đích và session nhận, có idempotency/hash/ack/retry/expiry. | `platform_tenant`, `channels`, `platform_workflow_session`, `platform_agent_version` |
| [platform_runtime_checkpoint](platform-collaboration.md#platform_runtime_checkpoint) | Mốc khôi phục bất biến của session gồm provider/version/schema/hash/object reference, cursor tin nhắn và fencing token. | `platform_tenant`, `platform_workflow_session`, `platform_agent_run` |
| [platform_runtime_message](platform-collaboration.md#platform_runtime_message) | Trao đổi tác nghiệp nội bộ giữa các participant có thứ tự/reply/run provenance; không phải dữ liệu cư dân được xem hoặc chain-of-thought. | `platform_tenant`, `platform_workflow_session`, `platform_session_participant`, `platform_agent_run`, `platform_runtime_message` |
| [platform_session_control](platform-collaboration.md#platform_session_control) | Thông tin điều khiển session: mục đích, phiên cha, coordinator, initiation key, lease/fencing, budget số lượt/tool và deadline. | `platform_tenant`, `platform_workflow_session`, `platform_session_participant` |
| [platform_session_participant](platform-collaboration.md#platform_session_participant) | Roster group chat trong một workflow, ghim AgentVersion, vai trò điều phối/chuyên gia/reviewer và snapshot quyền. | `platform_tenant`, `platform_workflow_session`, `platform_agent_version` |
| [platform_session_wait](platform-collaboration.md#platform_session_wait) | Điểm chờ agent/con người/domain event/timer, có deadline và receipt đánh thức; tránh coi chờ là lỗi runtime. | `platform_tenant`, `platform_workflow_session`, `platform_run_step`, `platform_session_participant` |

## platform-event-delivery

| Bảng | Nhiệm vụ | Liên kết tới |
|---|---|---|
| [platform_event_receipt](platform-event-delivery.md#platform_event_receipt) | Inbox dedupe từng event/consumer, lưu trạng thái xử lý, lease/retry và hash chống nhận cùng ID khác nội dung. | `platform_tenant` |

## vinhomes-workforce

| Bảng | Nhiệm vụ | Liên kết tới |
|---|---|---|
| [vh_staff_shift](vinhomes-workforce.md#vh_staff_shift) | Ca làm việc của thành viên đội, thời gian và trạng thái; không cho ca đang áp dụng chồng nhau của cùng người. | `platform_tenant`, `vh_project`, `vh_team_member` |
| [vh_staff_skill](vinhomes-workforce.md#vh_staff_skill) | Năng lực/chứng nhận đã xác minh của nhân viên, cấp độ và hạn hiệu lực. | `platform_tenant`, `vh_project`, `vh_property_membership`, `users` |
| [vh_team](vinhomes-workforce.md#vh_team) | Đội nghiệp vụ theo dự án/chuyên môn, độc lập với nhóm agent AI. | `platform_tenant`, `vh_project` |
| [vh_team_member](vinhomes-workforce.md#vh_team_member) | Nhân viên/nhà thầu tham gia đội qua property membership, vai trò và khoảng hiệu lực. | `platform_tenant`, `vh_project`, `vh_team`, `vh_property_membership` |

## vinhomes-assets

| Bảng | Nhiệm vụ | Liên kết tới |
|---|---|---|
| [vh_asset](vinhomes-assets.md#vh_asset) | Thiết bị/tài sản cần bảo trì trong dự án/tòa/căn hộ, model/serial/bảo hành và metadata. | `platform_tenant`, `vh_project`, `vh_tower`, `vh_apartment` |
| [vh_incident_asset](vinhomes-assets.md#vh_incident_asset) | Liên kết sự cố với tài sản ảnh hưởng/nghi ngờ/nguyên nhân, tránh nhét asset IDs tự do trong mô tả. | `platform_tenant`, `vh_project`, `vh_incident`, `vh_asset` |

## vinhomes-dispatch

| Bảng | Nhiệm vụ | Liên kết tới |
|---|---|---|
| [vh_work_appointment](vinhomes-dispatch.md#vh_work_appointment) | Lịch hẹn thực hiện work order và xác nhận với cư dân nếu cần, lưu lịch sử đổi lịch bằng bản ghi mới. | `platform_tenant`, `vh_project`, `vh_incident`, `vh_task`, `vh_work_order`, `vh_resident_report`, `users` |
| [vh_work_assignment](vinhomes-dispatch.md#vh_work_assignment) | Lịch sử giao/nhận/từ chối/thu hồi/hoàn tất work order cho đội hoặc nhân viên; mỗi work order tối đa một assignment đang hiệu lực. | `platform_tenant`, `vh_project`, `vh_incident`, `vh_task`, `vh_work_order`, `vh_team`, `vh_team_member`, `users` |
| [vh_work_progress](vinhomes-dispatch.md#vh_work_progress) | Cập nhật hiện trường bất biến của kỹ thuật, giai đoạn/ETA có người xác nhận và business event nguồn; là nguồn tiến độ thực tế. | `platform_tenant`, `vh_project`, `vh_incident`, `vh_task`, `vh_work_order`, `vh_work_assignment`, `vh_business_event`, `users` |

## vinhomes-resident-updates

| Bảng | Nhiệm vụ | Liên kết tới |
|---|---|---|
| [vh_notification_delivery](vinhomes-resident-updates.md#vh_notification_delivery) | Mỗi lần gửi thông báo qua một channel/provider, có idempotency và receipt giao nhận để theo dõi retry. | `platform_tenant`, `vh_project`, `vh_notification`, `vh_report_update` |
| [vh_report_update](vinhomes-resident-updates.md#vh_report_update) | Bản tiến độ đã biên soạn riêng cho đúng reporter, ghim event/incident version; lễ tân đọc bản này thay vì đọc toàn group chat. | `platform_tenant`, `vh_project`, `vh_incident`, `vh_resident_report`, `users`, `vh_business_event`, `vh_work_progress` |

## vinhomes-provider-events

| Bảng | Nhiệm vụ | Liên kết tới |
|---|---|---|
| [vh_provider_event](vinhomes-provider-events.md#vh_provider_event) | Inbox callback nhà cung cấp đã xác minh chữ ký, hash/dedupe và kết quả xử lý; không tự chứng minh thanh toán nếu chưa qua adapter tin cậy. | `platform_tenant` |

## vinhomes-sla

| Bảng | Nhiệm vụ | Liên kết tới |
|---|---|---|
| [vh_escalation](vinhomes-sla.md#vh_escalation) | Hồ sơ chuyển cấp khi vi phạm SLA/an toàn/yêu cầu thủ công, người tiếp nhận và kết quả xử lý. | `platform_tenant`, `vh_project`, `vh_incident`, `vh_incident_sla`, `vh_team`, `users` |
| [vh_incident_sla](vinhomes-sla.md#vh_incident_sla) | Snapshot áp dụng SLA cho một incident, deadline và thời điểm phản hồi/giải quyết thực tế. | `platform_tenant`, `vh_project`, `vh_incident`, `vh_sla_policy` |
| [vh_sla_policy](vinhomes-sla.md#vh_sla_policy) | Phiên bản SLA theo dự án/category/severity với thời hạn phản hồi/giải quyết tính theo thời gian liên tục. | `platform_tenant`, `vh_project` |
