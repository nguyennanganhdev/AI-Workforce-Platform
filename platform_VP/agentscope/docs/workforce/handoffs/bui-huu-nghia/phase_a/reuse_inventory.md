# Khảo sát code để tái sử dụng — 10/10/2026

Đường dẫn dưới đây tính từ `platform_VP/agentscope`. Đã đọc source tại baseline `6bc7d60d1bcf0d1bf49ad9214fad22791b29c274`; chưa chạy integration framework.

| Code hiện có | Đã xác minh trong source | Quyết định cho Builder |
|---|---|---|
| `src/agentscope/model/_base.py`, `ChatModelBase.generate_structured_output` | Nhận messages và Pydantic class/JSON Schema dict; validates bằng Pydantic/jsonschema; strategy forced → auto → no_think khi hỗ trợ → none; retry transient mỗi strategy tối đa max_retries+1 | Tái sử dụng method public cho extraction/generation. Không viết model client hoặc parser/repair loop mới. Foundation adapter quản lý ngân sách/deadline, không đổi model |
| `src/agentscope/agent/__init__.py`, `_agent.py` | Public class là Agent; reply/reply_stream nhận structured_schema kiểu Pydantic, sử dụng builtin structured-output tool | Nếu Builder cần vòng agent có tool, dùng Agent và toolkit hạn chế; không giả định có ReActAgent ở phiên bản repo này. Lát cắt extraction có thể dùng trực tiếp ChatModelBase |
| `src/agentscope/agent/_structured_output_tool.py` | Validate output, đưa vào reply state; test tại `tests/agent_structured_output_test.py` có MockModel | Học cách mock ở test Phase B; không copy private structured tool vào Workforce |
| `src/agentscope/app/storage/_model/_session.py`, ChatModelConfig | Shape type, credential_id, model, parameters; session chứa chat_model_config và fallback config riêng | Giữ shape model selection; credential ID legacy là string. Tách generation_model trong build session khỏi AgentSpec.model_config_ref (field canonical sau pull) |
| `src/agentscope/app/_service/_model.py`, get_model | Resolve credential qua ResourceAccessService, CredentialFactory tạo model class, validate Parameters, lookup card cập nhật context/input types | Yêu cầu Foundation bọc bằng port/adapter; không import private service trực tiếp từ Builder. Adapter phải kiểm tra manager Scope theo Workforce |
| `src/agentscope/app/_router/_model.py` | GET /model/ trả model cards theo credential provider type, không thử credential/live provider | Tận dụng catalog nhưng không coi list thành công là quyền hoặc khả dụng của model |
| `examples/web_ui/frontend/src/components/select/LlmSelect.tsx` | Nhận value/onChange ChatModelConfig, onAddCredential/refetchTrigger; emit type/credential_id/model/parameters | Dùng component này cho model sinh ở Phase B; không viết model picker mới |
| `examples/web_ui/frontend/src/hooks/useAvailableModels.ts` | Ghép credentialApi.list + modelApi.list, cache qua react-query; model-list lỗi tạo models rỗng | Tái sử dụng hook; Builder phải hiện lỗi/thiếu lựa chọn phù hợp. Không tự chọn model dựa thứ tự sort tên |
| `examples/web_ui/frontend/src/hooks/useModels.ts`, `api/model.ts` | Query model theo provider, loading/error và API client chung | Tận dụng khi cần metadata theo provider; không thêm fetch/auth transport riêng |
| `examples/web_ui/frontend/src/components/form/AgentFormFields.tsx`, `SchemaForm.tsx` | Form hiện tại dùng AgentData schema, tách identity/context/react/invite | Dùng primitive/SchemaForm để chỉnh đề xuất; adapter manifest cần xác minh. Không dùng nguyên form team invite như roster của Builder |
| `src/agentscope/app/storage/_model/_agent.py` | AgentData chứa name/system_prompt/context/react/invite; AgentRecord.source phân biệt user/team | AgentData không thay thế manifest Workforce đầy đủ. Identity/draft/publish đi qua Lifecycle, không tạo team-worker record |
| `src/agentscope/agent/_config.py` | ContextConfig/ReActConfig là Pydantic có mặc định/ràng buộc | Dùng schema và default thật khi generate manifest; tránh clone các định nghĩa cấu hình |
| `pyproject.toml` | jsonschema là dependency đã khai báo, Python >=3.11 | Dùng jsonschema sẵn trong thiết kế để kiểm tra proposal; môi trường máy hiện chưa có nên cài vào venv tạm, không thay dependency dự án |

KB/skill/tool sẽ dùng Registry/knowledge adapter đúng scope sau khi owner cung cấp. Chưa kiểm tra đủ API truy cập KB/skill để chốt một method mới; đây là điểm cần khảo sát tiếp ở BHN-06, không tuyên bố đã nối.

Các file private/shared phía trên chỉ đọc. Phần mới của Nghĩa là requirement/policy mapping, planner/selection logic và màn hình Builder trong owned paths; các public contracts/core adapter do owner hiện thực. Khi viết code tiếp, cập nhật inventory bằng call site thật và test tương ứng.
