# JEV trong Agent Builder

Builder giữ AgentSpec, draft, immutable versions và publish gate hiện có.
JEV chỉ đề xuất quyết định nghiệp vụ/tài nguyên; không cấp quyền hoặc thực thi tool.

## Cấu hình

- Image backend cài extra `classifier-jev` cùng các extra hiện có.
- Thêm TypeSafe credential qua trang credential bằng tài khoản được phép. Không có fallback đọc API key từ môi trường.
- `WORKFORCE_JEV_MODEL=jev-1.13.0` mặc định là phiên bản cụ thể. Không dùng alias `latest`.
- Khi có nhiều credential TypeSafe, chọn ID bằng `WORKFORCE_JEV_CREDENTIAL_ID`.
- Credential JEV không xuất hiện như chat model. Chat model của Builder vẫn được chọn riêng.
- Chưa cấu hình JEV: nếu catalog có ứng viên hoặc nhiều agent cần phân biệt, kiểm tra trùng dừng ở `clarify`. Lỗi JEV không đồng nghĩa được tạo mới.
- Chọn tài nguyên có thể fallback sang chat model; UI hiển thị nguồn và nguyên nhân. Fallback này không được phép thay quyết định identity chưa rõ thành `create`.

## Luồng sử dụng

1. Nhập yêu cầu. LLM tách ranh giới nghiệp vụ, nhu cầu tool và tri thức.
2. Server lọc catalog theo owner được xác thực và scope tenant/domain/area. Agent cũ chưa có scope thuộc catalog của chính tài khoản đó; scope tường minh phải khớp. Không tái sử dụng/mutate agent của owner khác. Chỉ AREA_MANAGER được thiết kế agent.
3. JEV so sánh nghiệp vụ và năng lực với cả published/draft. Cùng nghiệp vụ: reuse nếu đủ năng lực và đã có eval hợp lệ; resume draft; revise cùng ID nếu cần nâng cấp; repair nếu withdrawn/tài nguyên cũ bị thu hồi. Nhiều ứng viên, phạm vi giao nhau hoặc lỗi phân loại: clarify.
4. JEV đề xuất tool/KB/skill từ thư viện được phép. Server phân tool cho một agent trong proposal, kiểm ID/schema/quyền xác nhận. Skill không thay thế tool và không cấp thêm quyền.
5. Duyệt phương án để sinh cấu hình và xem diff. Chưa ghi agent ở bước này. Skill thư viện đủ dùng thì bỏ skill do LLM tự sinh.
6. Chọn **Lưu nháp và chạy eval**. Server kiểm tra lại scope, revision và catalog; lưu draft vào cùng agent ID, giữ bản published đang phục vụ. Eval chạy đúng spec vừa duyệt.
7. Chỉ phát hành khi đủ bộ test, mọi ca an toàn đạt, report khớp spec và catalog/agent chưa thay đổi. Phiên bản mới append vào history; reuse trả ID cũ mà không sửa agent.

Thiếu tool cho hành động bắt buộc chặn xác nhận. Thiếu tri thức tùy chọn hiện cảnh báo; tri thức được yêu cầu bắt buộc thì chặn. Prompt phải yêu cầu bổ sung dữ kiện thiếu, không bịa chính sách hoặc dữ liệu sống.

Ngưỡng hiện tại là policy khởi điểm: same-business/covers ≥0,85; ≤0,15 được coi là khác; vùng giữa cần làm rõ. Tool/KB/skill cần ≥0,8. Đây không phải độ chính xác đã đo của model tiếng Việt.

## Đồng thời và khôi phục

SQL và Redis có reservation theo owner dùng chung giữa worker. Catalog agent được đóng dấu hash ở phương án; hội thoại dùng catalog cũ bị 409 trước khi ghi draft/publish. Ghi agent tiếp tục dùng storage CAS và immutable version checks.

Reservation không có TTL: nếu process chết giữa chừng, operator kiểm tra draft, version, workspace và claim trước khi giải phóng. Không tự retry publication khi chưa biết side effect đã chạy hay chưa.

- SQL: reservation ở bảng `messages`, `session_id='builder-catalog:' + sha256(owner_id)`, `msg_id='reservation'`; payload chứa owner/token. Chỉ xóa đúng reservation sau khi xác minh worker đã dừng và trạng thái ghi dở đã được xử lý.
- Redis: key qua `RedisStorage.key_config.builder_publish`, với `session_id='catalog'`, `proposal_id='reservation'`. Token phải khớp để release.
- Claim publish theo proposal được giữ vĩnh viễn như trước. CAS publication diễn ra trước khi đổi derived workspace bindings; lỗi sau CAS cần đối chiếu và sửa bindings, không append phiên bản lặp một cách mù quáng.
- Agent Studio vẫn có CAS riêng. Thay đổi Studio làm catalog cũ hết hiệu lực; draft có thể tiếp tục chỉnh/eval/publish tại Studio.

## Số liệu và kiểm chứng

Proposal lưu action/reason/candidates, nguồn chọn tài nguyên, model pin, số call/question, token và latency JEV. Ledger dùng purpose `builder_reuse`/`builder_resources`, không lưu prompt, skill body hoặc credential. Chi phí lấy từ price catalog đúng provider/endpoint/model/tier; thiếu giá hoặc usage thì `null`, không báo miễn phí.

Các ca tiếng Việt ở `tests/workforce/console/test_builder_jev_flow.py` dùng classifier/generator giả lập. Chúng kiểm chứng quyết định ứng dụng, chống bản sao, resource drift và version lifecycle. Chúng không đo độ chính xác, độ trễ hoặc giá thực của nhà cung cấp. UI có test review/gating riêng tại `frontend/tests/builder-review.test.mjs`.

Chạy kiểm tra offline từ thư mục `platform_VP/agentscope`:

```powershell
uv run --no-project --with-editable '.[service,classifier-jev,storage-sql,auth]' --with pytest --with pytest-asyncio --with aiosqlite --with fakeredis python scripts/workforce/check_builder_jev.py --storage
```

Bộ chạy loại biến credential khỏi chính process kiểm thử và chặn mọi kết nối ứng dụng. Socketpair đánh thức nội bộ của Windows asyncio được tạo riêng. Kết quả ở `.artifacts/jev/pytest.xml` và `summary.json` (Git-ignored); có kết nối ứng dụng bị thử gọi thì bộ chạy trả lỗi. Nó không đổi biến môi trường hệ thống hoặc file `.env`.

Chưa gọi model thật khi triển khai. Đánh giá chất lượng thật cần tập yêu cầu tiếng Việt có nhãn độc lập: đúng identity/action, đúng tập tool/KB/skill; đo false-create, false-reuse, resource precision/recall, latency p50/p95, token và cost. Chỉ chạy khi chủ dự án cho phép dùng credential cụ thể.
