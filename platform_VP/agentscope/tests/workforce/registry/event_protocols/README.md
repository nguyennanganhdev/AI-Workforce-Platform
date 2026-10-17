# event_protocols — API/event/workflow v1.4

Phase B có tests cho `AsyncProtocolService` qua repository/context loader fake;
fake Phase A dùng chung normalizer production. Chạy thêm
`node tests/workforce/registry/event_protocols/test_event_channels.mjs` từ root
AgentScope để kiểm tra readiness và render UI qua Vite/React SSR sẵn có.
Chi tiết kết quả và giới hạn integration ở
[PHASE_B.md](../../../../docs/workforce/handoffs/nguyen-phuong-dong/PHASE_B.md).

Chủ sở hữu: **Nguyễn Phương Đông**. Branch: `feat/wf-registry`.
Task bổ sung của owner: **NPD-10–NPD-12**; chọn phần tương ứng phạm vi folder dưới đây.

Đọc [kế hoạch triển khai](../../../../docs/workforce/KE_HOACH_TRIEN_KHAI.md) và [bàn giao cá nhân](../../../../docs/workforce/handoffs/nguyen-phuong-dong/README.md) trước khi code. Đặc tả chung nằm ở mục 17; ranh giới ownership ở 5.3 và task chi tiết trong phần mang tên owner. Các đường dẫn link tính từ folder này.

Phạm vi: Protocol schema/ordering/drift/capability tests.

File dự kiến khi triển khai: `test_protocols.py`, `test_normalizer.py`. Đây chỉ là gợi ý chia file; chưa có code được tạo trong folder.

Nguyên tắc triển khai:

- Một role AREA_MANAGER, Scope đủ tenant/domain/area/manager và audience cư dân; không route theo payload tự khai.
- Dùng DTO/ports chung; không import private service hoặc ghi bảng module khác. uow đi xuyên inbox → workflow/public event → trigger khi cần atomicity.
- Customer request/reply POST ưu tiên `200`, chỉ `202/watch_request` khi hết thời gian chờ; response luôn có `workflow_state` và `next_action`. Response-only read-only có thể auto-close; interactive dùng reply/approval/explicit close; Provider Event/SSE tracking chỉ dùng khi operation thật sự pending.
- Tự viết test trong vùng test được giao, dùng fake port khi module khác chưa có. Chỉ đánh dấu live integration khi có bằng chứng thật.
- Cần đổi contract/migration/core/global frontend thì ghi INTEGRATION_REQUEST trong handoff; Chí Hoàng tích hợp file chung.

Phase A đã có `test_protocols.py` và `fakes.py`. Chạy từ `platform_VP/agentscope`:

```bash
python -m unittest discover -s tests/workforce/registry/event_protocols -p 'test_*.py' -v
```

Fake dùng nguyên DTO/signature `AsyncProtocolPort`; kiểm tra scope/namespace,
coverage, schema, deterministic normalization, order metadata và snapshot drift.
Fake không persist/apply event, không gọi MCP/HTTP và không dùng trong production.
Schema/samples/ordering rules:
[PHASE_A.md](../../../../docs/workforce/handoffs/nguyen-phuong-dong/PHASE_A.md).
