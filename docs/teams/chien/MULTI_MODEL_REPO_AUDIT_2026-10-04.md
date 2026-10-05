# Multi-provider LLM và embedding: kiểm tra repo ngày 04/10/2026

## Kết luận

Nên bổ sung Google Gemini trước, Anthropic Claude cho tác vụ cần chất lượng cao, DeepSeek để đối chiếu chi phí. Giữ embedding OpenAI đang dùng làm baseline; thử Google embedding trong một model space riêng trước khi chuyển retrieval. Model/chat và embedding không cần cùng nhà cung cấp.

Danh sách ID, giá và điều kiện free được kiểm chứng riêng trong [MODEL_PROVIDER_RESEARCH_2026-10-04.md](MODEL_PROVIDER_RESEARCH_2026-10-04.md). Đây là đề xuất tích hợp, chưa phải cấu hình đã chạy với các nhà cung cấp mới.

## Phạm vi và Git

Đã kiểm kê toàn bộ cây Git, khảo sát cấu trúc workspace, README, tài liệu runtime/RAG, các adapter model, cấu hình mẫu, launcher, schema và code ingestion/retrieval. Đọc sâu các đường gọi model liên quan tới luồng Vinhomes kết nối thật. Không khẳng định đã review thủ công từng dòng của tất cả file; dependency, file binary và secret không thuộc phạm vi review nội dung.

Sau `git fetch origin --prune`:

| Ref | Commit | File được Git theo dõi | Quan hệ |
|---|---|---:|---|
| Nhánh hiện tại `dev_teamChien_HuyDo` | `bdc3f70` | 2410 | HEAD tại thời điểm audit |
| Local `develop` | `6fa4aa0` | 1185 | Thiếu 193 commit so với `origin/develop` |
| Local `dev_TeamChien` | `9cc6126` | 2404 | Thiếu 7 commit so với `origin/dev_TeamChien` |
| `origin/develop` | `b391952` | 2258 | HEAD chứa toàn bộ ref này; HEAD có thêm 46 commit |
| `origin/dev_TeamChien` | `bdc3f70` | 2410 | Trùng HEAD |

Tên ref thực tế là `dev_TeamChien`, khác cách viết `dev_teamChien` trong câu hỏi. Không checkout, merge, reset hoặc chỉnh hai nhánh local trong audit này. Chênh lệch HEAD với remote develop: 304 file, 172549 dòng thêm / 5339 dòng xóa; nhiều dòng thuộc snapshot schema, tài liệu và báo cáo, không phải tất cả là code runtime.

Các đường model Python Reception và embedding ở HEAD, local `dev_TeamChien`, remote `dev_TeamChien` và remote develop có cùng ràng buộc chính. Remote develop chưa có phần `agent-coordination/src/vinhomes` mà nhánh hiện tại bổ sung. Local develop quá cũ để suy ra khả năng runtime hiện tại.

## Env đang được chọn

Chỉ đọc tên biến và trạng thái có/không có giá trị; không sao chép secret vào báo cáo.

- `agent-reception/.env`: `RECEPTION_MODEL=gpt-5.4-mini`, `RECEPTION_AGENT=loop`; OpenAI key và knowledge URL đã được điền; `OPENAI_BASE_URL` trống nên code chọn OpenAI mặc định.
- `agent-coordination/.env`: `COORDINATION_MODEL=gpt-5.4-mini`.
- Root `.env`: OpenAI key trống. Root env và Reception env là các nguồn cấu hình khác nhau; không dùng root env để kết luận Reception thiếu key.
- File `.local-connected/knowledge.env` được kiểm tra không đặt `KNOWLEDGE_EMBEDDING_MODEL`; code mặc định `text-embedding-3-large`.
- Báo cáo database có sẵn ghi model active `text-embedding-3-large`, 1536 chiều: [DATABASE_BACKUP_AND_ENV_2026-10-04.md](DATABASE_BACKUP_AND_ENV_2026-10-04.md). Audit này không truy vấn lại DB, không kiểm tra giá trị biến của process đang chạy.

## Khả năng thực tế từng thành phần

| Thành phần | Code và cấu hình hiện tại | Ý nghĩa khi thêm provider |
|---|---|---|
| Reception TypeScript | `agent-reception/src/config.ts`, `src/adapters/model/factory.ts`: `openai`, `anthropic`, `google`; dùng các key riêng | Đã có adapter native; model mặc định trong code chưa đồng bộ với catalog hiện tại |
| Reception Python kết nối thật | `scripts/start_runtime.ps1` chạy `src.runtime.service`; `service.py:65-80` đọc `RECEPTION_MODEL`, `OPENAI_API_KEY`, `OPENAI_BASE_URL` | Không đọc `RECEPTION_MODEL_PROVIDER`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`; thêm key vào env chưa kích hoạt provider mới |
| Python graph/loop | `src/runtime/model.py` gọi `/chat/completions`; graph yêu cầu JSON; loop gửi `tools` cùng `response_format=json_object` | Cần kiểm chứng tools, JSON và follow-up với chính model được chọn; trả text được chưa đủ |
| Supervisor Vinhomes | `agent-coordination/src/vinhomes/runtime.py`, `ports.py`: `COORDINATION_MODEL`, `COORDINATION_MODEL_BASE_URL`, nhưng key vẫn từ `OPENAI_API_KEY` | Có endpoint riêng, chưa có credential riêng; dùng `max_completion_tokens`, kiểm model response prefix, yêu cầu usage để tính budget |
| Coordination runtime tổng quát | `src/config.py`, `src/runtime/model.py`: provider `openai-compatible`, `key_env` có thể cấu hình | Khác entrypoint Vinhomes; kiểm model response bằng equality nên alias/snapshot cần kiểm chứng riêng |
| Specialists trong luồng thật | `scripts/start_openbot.ps1` chạy `agent-bot`; nhận `COORDINATION_OPENBOT_MODEL`, kế thừa OpenAI key/base từ Reception | Chưa tự chọn native Claude chỉ bằng đổi model; không nhầm với adapter LangGraph có nhiều provider |
| Agent Factory | `agent-factory/src/model.ts`: `openai` hoặc `openai-compatible`; URL, key, model riêng | Dễ chọn endpoint tương thích; `max_tokens`/`max_completion_tokens` khác theo provider, không được gửi reasoning option không hỗ trợ |
| OpenBot/Hono built-in | `server/src/copilot.ts`, `routing/model.ts`: native OpenAI/Anthropic và custom endpoint | Provider selector của desktop không phải cấu hình chung cho runtime Python Vinhomes |
| Các harness khác | LangGraph native OpenAI/Anthropic/Google; ADK/Agno/CrewAI/LlamaIndex/Langroid/Strands dùng LiteLLM; AG2/Microsoft có native Anthropic; Pydantic AI có provider model string | Repo đã có khả năng đa provider ở nhiều nơi, nhưng không tự nối chúng vào đường Reception/Supervisor đang chạy |
| Report tools | `agent-report`, reporting tool gateway của business API | Tổng hợp số liệu qua tool; lời trả lời của specialist dùng model của OpenBot. Không cần thêm một embedding model cho mỗi report tool |

`CHAY_KET_NOI_THAT.cmd` gọi `launch_connected.ps1`; launcher này khởi động business API và hai frontend. Không phải launcher tự cấu hình/chạy đầy đủ Reception, Knowledge, Supervisor và OpenBot.

## Vấn đề cần sửa trước khi dùng nhiều provider đồng thời

1. **Tách cấu hình chat khỏi embedding.** `services/vinhomes-api/scripts/start_knowledge.ps1` đang đọc key và base URL từ Reception; `server/src/knowledge/runtime.ts` cũng dùng `OPENAI_API_KEY`/`OPENAI_BASE_URL`. Đổi Reception sang endpoint chỉ có chat sẽ khiến Knowledge gọi embedding vào endpoint sai.
2. **Tách credential từng vai trò.** Supervisor có base URL riêng nhưng key vẫn chung; OpenBot specialist cũng kế thừa Reception. Cần cho từng vai trò chọn provider, model, base URL và key reference riêng. Không gửi OpenAI key tới endpoint một hãng khác.
3. **Hoàn thiện adapter Python cho provider đã chọn.** Gemini/DeepSeek có thể đi qua giao thức tương thích nếu request hiện tại được hỗ trợ; Claude cần adapter Messages/tool protocol hoặc một gateway chuyển đổi đã kiểm chứng. Kiểm cả JSON + tools trong Reception loop, không chỉ request chat đơn giản.
4. **Đồng bộ launcher, Compose và eval.** Compose đang truyền cùng OpenAI key vào nhiều service; bổ sung key/base riêng ở code mà launcher không truyền vào thì runtime vẫn chưa dùng được. Eval judge hiện cũng dùng chung Reception model/key/base, nên cần giữ judge cố định khi so sánh model.

Tên env bổ sung nên có phạm vi theo vai trò, ví dụ `RECEPTION_*`, `COORDINATION_*`, `COORDINATION_OPENBOT_*`, `KNOWLEDGE_EMBEDDING_*`. Đây là tên đề xuất cần triển khai; không phải biến hiện đã được tất cả entrypoint hỗ trợ. Có thể dùng một resolver nhỏ cho runtime đang kết nối, không cần refactor mọi harness để bắt đầu.

## Embedding và RAG

- Schema: `server/src/db/schema/tables.ts:5178` đặt `vector(1536)`; baseline migration còn có trigger kiểm model dimension=1536 và cosine.
- `server/src/knowledge/types.ts:31` chỉ cho `text-embedding-3-small` và `text-embedding-3-large`; provider metadata mặc định `openai`. `embedder.ts` gửi `dimensions:1536` và kiểm vector trả về.
- Một endpoint tương thích `/embeddings` chưa đủ để thêm model Google/Voyage: phải mở rộng model spec, provider metadata, config validation và adapter.
- Cùng 1536 chiều **không** có nghĩa là cùng embedding space. Document và query phải dùng cùng provider/model/revision/preprocessing; giữ vector khác model trong các dòng `embedding_models` khác nhau. Không trộn hoặc fallback query sang model khác trên vectors cũ.
- `pg-store.ts:333` yêu cầu active model đã tồn tại, không tự tạo/activate khi search. Ingestion/activation phải hoàn tất trước khi đổi retrieval.
- `retrieve.ts:26` dùng ngưỡng similarity 0.35 đã chọn theo OpenAI large; model mới cần calibration lại. Code đã có hybrid keyword/vector retrieval và scope/ACL trước ranking.
- Theo report Q06 trong repo (không đo lại trong audit này), 93 câu: large recall@1 82.4%, small 73.5%; câu không dấu 5/5 so với 3/5. Nguồn: [báo cáo Team Quang](../quang/requests/2026-10-01-rag-ingestion-retrieval.md).
- Google embedding ở 1536 có thể giữ chiều/schema hiện tại nếu adapter cấu hình đúng; vẫn phải tạo embeddings mới và đánh giá lại. Voyage/BGE-M3 với chiều khác phải có kế hoạch schema/index tương ứng. Không zero-pad/truncate thủ công để lách constraint.
- Reranker là bước xếp lại candidate đã được ACL lọc; không thay embedding model và không bypass quyền truy cập.

## Bộ cấu hình đề xuất và thứ tự triển khai

1. Giữ `gpt-5.4-mini` và OpenAI large/1536 làm baseline, tách key/base của Knowledge trước.
2. Thêm Gemini cho Reception và tác vụ nhẹ; so sánh với baseline qua các hội thoại follow-up, gọi tool, hỏi RAG và câu không đủ dữ liệu.
3. Thêm Claude Sonnet cho Supervisor/Factory hoặc specialist cần lập kế hoạch và tổng hợp phức tạp; đây là lựa chọn để benchmark, không có bằng chứng model này thắng baseline của repo.
4. Thêm DeepSeek cho specialist để đo chi phí/latency và độ đúng tool/JSON; giữ tổng hợp số liệu từ backend tools.
5. Thử Google embedding với 1536 trong model space riêng, ingest lại từ chunks đã có, chạy Q06 và calibrate threshold trước khi activation. Giữ OpenAI baseline để quay lại.
6. Chỉ thêm Voyage/local BGE và reranker nếu evaluation cho thấy retrieval cần cải thiện hoặc cần chạy nội bộ. Local model không thu phí token API nhưng có chi phí CPU/GPU/vận hành.

## Tiêu chí chấp nhận khi triển khai

- Unit/contract checks cho đúng key/base URL theo từng role, provider mapping và request options.
- Provider smoke: JSON hợp lệ; tool call → tool result → final JSON; timeout/429; usage; phản hồi model alias/snapshot của Supervisor.
- End-to-end trên DB thử: follow-up, tình huống khẩn cấp, không tự bịa phí/giờ/đã hoàn tất, không lộ từ nội bộ; không tạo ticket trùng khi thử lại.
- RAG: Q06/corpus tiếng Việt có dấu và không dấu, recall@k, citation, off-topic refusal, scope/ACL leakage, ingestion và retrieval cùng model.
- So sánh p50/p95 latency, số lần gọi và chi phí trên toàn bộ turn/session. Reception loop có thể gọi nhiều lần trong một lượt; giá per-token không phải chi phí một hội thoại.
- Judge cố định cho so sánh; ghi raw usage và model version. Không dùng một model mới tự chấm chính nó rồi kết luận tốt hơn.

Audit này không gọi model trả phí, không ingest hoặc sửa DB, không đổi `.env`, không chạy lại live eval, không tuyên bố các provider mới đã hoạt động. Có thay đổi của công việc khác trong working tree trong lúc đọc; giữ nguyên chúng. Chỉ bổ sung tài liệu audit/research.
