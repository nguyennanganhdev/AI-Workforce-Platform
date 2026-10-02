# PH01 — Kế hoạch reuse agent-langgraph

Owner: Phan Hoàng. Ngày: 30/09/2026.
Reception duy nhất tại `agent-reception/`; sample giữ nguyên vai trò tham khảo.

| Nguồn đã đọc | Quyết định | Task tiếp nhận / kiểm tra |
|---|---|---|
| `agent-langgraph/package.json`, `bun.lock` | Pin cùng phiên bản trực tiếp LangChain/LangGraph tại PH01; Reception có lockfile riêng. Bổ sung dependency checkpointer trực tiếp vì import type đó. Không import package bằng đường dẫn vòng sang sample. | PH01: frozen install, typecheck, capability spike với fake ports. |
| `agent-langgraph/src/index.ts` — `buildModel` | Reuse cách tạo ba provider, tách thành `src/adapters/model/factory.ts`; config và credentials riêng. Không import entrypoint sample vì tự mở server. | PH01: kiểm tra provider/model/streaming; PH04 nối model vào graph. OAuth/base URL/reasoning options chưa được đưa sang; yêu cầu riêng nếu deployment cần. |
| `src/deltas.ts` — `textOfChunk` | Ứng viên reuse logic thuần để lấy text từ string/content block và bỏ reasoning blocks; chưa cần copy trong PH01. | PH02: adapter streaming cùng test string/block/empty/tool-only. Nếu copy/adapt, ghi nguồn và mang theo tình huống test. |
| `src/stream.ts` — `streamRun` | Tham khảo lifecycle mở/đóng message và terminal error. Chưa reuse nguyên hàm vì shape event, interrupt và context của Reception khác sample. | PH02 + PD01: map graph event nội bộ sang AG-UI, kiểm tra lỗi đầu/giữa stream, cancel/disconnect và không lộ state. |
| `src/history.ts` | Chỉ tham khảo mapping message. Không mang `COMPUTER_GUIDANCE`, system/context tùy ý từ browser hoặc lịch sử chưa xác minh vào Reception. | PD01/PD02 sở hữu prompt/state; PH02 chỉ chuyển input đã validate/authorize. |
| Graph `.compile()` và tool HTTP trong `src/index.ts` | Không dùng nguyên runtime/tool loop sample: chưa có durable checkpointer/binding C06 của Reception. Inject qua contracts của PH01. | PD01 graph, DD01/DD02 backend/tools, PH03 checkpoint và PH04 composition. |

Capability spike dùng `StateGraph` thật, `FakeListChatModel`, tool giả và
`MemorySaver` trong `tests/` để kiểm chứng API phiên bản đã pin. Spike không phải
business graph của Phan Dũng, không chứng minh persistence sau restart và không
được mount production. Credential DB framework, lease/fencing và event dedup
thuộc PH03 với dependency C06/P02.

PH01 chưa thêm AG-UI dependency, Dockerfile hoặc root workspace. PH02 thêm package
AG-UI đã chọn và test wire contract; Team 5 chốt deployment/CI theo request P01.
