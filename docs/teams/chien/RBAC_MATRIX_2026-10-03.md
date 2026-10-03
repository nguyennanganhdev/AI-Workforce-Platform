# Ma trận phân quyền: từ cư dân, nhân viên, agent tới platform

Ngày 03/10/2026. Phạm vi: business API (`services/vinhomes-api`), Lễ tân (`agent-reception`), dịch vụ tri thức
(`server/src/knowledge`). Mọi dòng dưới đây đều có test tương ứng, trừ mục "Chưa có".

## Ai là ai

| Chủ thể | Xác định bằng | Lưu ở |
|---|---|---|
| Người dùng | Phiên đăng nhập platform hoặc mật khẩu của business API | `users`, `tenant_memberships` |
| Cư dân | Thành viên tenant + căn hộ đã xác minh và còn hiệu lực | `unit_residents` |
| Ban quản lý, nhân viên | Vai trò `management` / `staff` gắn với một phạm vi | `scoped_user_roles` × `access_scopes` |
| Quản trị platform | Danh sách riêng | `platform_admins` |
| Lễ tân (agent) | Token ngắn hạn gắn với một lượt chat của một cư dân | `agent_runs`, `runtime_session_bindings` |
| Dịch vụ Lễ tân gọi backend | Không có danh tính riêng: luôn mang token của lượt chat | — |
| Backend gọi dịch vụ Lễ tân | Service token dùng chung | cấu hình |
| Supervisor (agent của phòng BQL) | Service token của dịch vụ Supervisor, rồi kiểm theo từng nhóm: workspace có danh tính dịch vụ, agent Supervisor là thành viên, ticket đúng generation | `agent_teams`, `team_members`, `execution_principals`, `runtime_session_bindings` (loại `team`), `agent_runs` |

Phạm vi (`access_scopes`): tenant, khu (site), phân khu (zone), tòa (building), đơn vị quản lý (management).
Mọi bảng nghiệp vụ có RLS theo tenant; business API chạy bằng role không phải superuser và không bỏ qua RLS.

## Ai làm được gì

| Việc | Cư dân | Nhân viên | Ban quản lý | Lễ tân (thay cư dân) |
|---|---|---|---|---|
| Đọc, viết hội thoại của mình | Có | — | — | Chỉ hội thoại của lượt chat đang chạy |
| Tạo yêu cầu | Cho căn hộ đã xác minh của mình | — | — | Qua nháp → bàn giao, cho đúng cư dân đó |
| Xem yêu cầu | Của mình | Chỉ yêu cầu được giao hoặc nhận cảnh báo | Trong phạm vi vai trò | Chỉ yêu cầu mở từ hội thoại đó |
| Tạo phiếu, phân công, nghiệm thu | — | — | Có | — |
| Nhận việc, báo giá, ảnh, hoàn thành | — | Phiếu được giao | — | — |
| Đồng ý phương án, xác nhận hoàn tất | Yêu cầu của mình | Ghi nhận hộ tại hiện trường | — | — |
| Duyệt đóng session | — | — | Có | — |
| Xem hội thoại của một yêu cầu | — | Nếu thấy yêu cầu đó | Có | — |
| Trả lời câu hỏi cư dân (session hỏi đáp) | — | — | Đơn vị quản lý sở hữu session, hoặc cấp tenant | Chỉ mở session |
| Duyệt tri thức học được | — | — | Đơn vị quản lý sở hữu, hoặc cấp tenant | — |
| Duyệt hướng dẫn an toàn gửi kèm khi khẩn cấp | — | — | Đơn vị quản lý sở hữu, hoặc cấp tenant | Chỉ gửi nguyên văn câu đã duyệt |
| Tìm tri thức | — | — | — | Tòa, phân khu, khu của cư dân; không thấy khu khác hay đơn vị vận hành khác |
| Quyết định khẩn cấp | — | — | — | Policy của backend; model chỉ được nâng, không hạ |

## Token của Lễ tân

- Backend ký bằng `RECEPTION_DELEGATION_KEY` (dịch vụ Lễ tân không giữ khóa này), hạn 10 phút.
- Mỗi lời gọi, backend đọc lại: run còn chạy, binding và danh tính còn hiệu lực, cư dân còn hoạt động, còn là
  thành viên và còn sở hữu hội thoại, agent còn hoạt động, runtime còn bật.
- Lượt chat kết thúc thì token chết. Run treo quá 15 phút bị đóng ở lượt kế tiếp.
- Token chỉ dùng được với hội thoại của nó và các yêu cầu mở từ hội thoại đó.
- Tắt toàn bộ Lễ tân: `update runtime_backends set enabled=false where code='reception-langgraph'`.

## Test từ chối đang có

| Test | Kiểm điều gì |
|---|---|
| `test_reception_delegation_is_bound_to_one_running_turn` | Sai chữ ký, sai hội thoại, sai ticket, run đã đóng đều bị từ chối |
| `test_reception_policy_and_reply_are_backend_decisions` | Phiên cư dân không thay được token Lễ tân |
| `test_knowledge_authorization_follows_the_residents_home` | Không có quyền kho thì 403; không xin được phạm vi khu khác |
| `test_a_question_without_a_source_becomes_a_session_that_management_answers` | Nhân viên không thấy và không trả lời được câu hỏi |
| `test_an_answer_becomes_knowledge_only_after_it_is_judged_or_approved` | Nhân viên không duyệt được tri thức |
| `test_management_reads_what_the_resident_said_about_a_ticket` | Nhân viên ngoài phạm vi không đọc được hội thoại |
| `test_emergency_guidance_reaches_a_resident_only_after_management_approves` | Câu chưa duyệt không tới cư dân; nhân viên không thấy danh sách chờ duyệt |
| `test_runs_record_usage_and_a_stale_run_is_closed` | Token của run bị bỏ rơi hết hiệu lực |
| `test_only_the_configured_runtime_reaches_the_coordination_api` | Phiên cư dân, token sai hoặc backend chưa cấu hình đều không vào được API của Supervisor |
| `test_a_supervisor_question_reaches_the_resident_and_a_stale_team_is_refused` | Nhóm của generation cũ bị từ chối ở mọi lời gọi; không hỏi cư dân hai câu cùng lúc |
| `test_a_resident_cannot_flood_the_assistant` | Quá 30 tin/phút thì 429 |
| `test_resident_integration.py` | Kỹ thuật viên không duyệt đóng session và không nghiệm thu; tạo yêu cầu cho căn hộ không phải của mình bị từ chối |

## Chưa có

1. **Ủy quyền cho subagent.** Supervisor đã có: backend cấp một binding loại `team` và một run cho mỗi session
   (`v3_coordination.py`), và chỉ nhận kết quả V2 từ nó. Agent chuyên môn trong phòng thì chưa: chưa có agent
   nào được xuất bản, và Supervisor chưa được phép làm gì ngoài gửi kết quả V2 (phòng, phương án, phân công đều
   bị từ chối).
2. **Gắn quyền khi tạo agent.** Agent Factory (Team Phái) chưa tạo agent, phòng, Supervisor kèm quyền cho BQL thật.
3. **Vai trò quản lý theo khu/tòa với session hỏi đáp và tri thức.** Hiện chỉ tính vai trò ở phạm vi tenant hoặc
   đúng đơn vị quản lý.
4. **Chế độ demo.** Chọn vai bằng header `X-Demo-Actor`; backend chỉ cho bật khi host là loopback. Không dùng
   ngoài máy phát triển.
5. **Service token giữa backend và Lễ tân** là một bí mật dùng chung, chưa xoay vòng tự động.
6. **Cư dân có nhà thuộc hai đơn vị quản lý**: chưa chuyển được câu hỏi; tìm tri thức yêu cầu chọn nơi ở.
