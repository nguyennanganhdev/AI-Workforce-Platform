# Khảo sát model ngoài OpenAI cho Reception và RAG

Ngày đối chiếu: **2026-10-04**, theo múi giờ Asia/Saigon. Nguồn là tài liệu chính thức được đọc trực tiếp trong phiên này. Đây là khảo sát nhà cung cấp, chưa phải kết quả benchmark tiếng Việt hoặc xác nhận các adapter trong repo đã chạy được. Không sửa `.env`, không gọi API có phí.

## Nên bổ sung trước

Đề xuất triển khai theo thứ tự: **Gemini cho luồng thường ngày và thử miễn phí; Claude Sonnet cho ca khó; DeepSeek làm phương án tiết kiệm/dự phòng; Gemini Embedding 2 làm embedding ngoài OpenAI đầu tiên**. Giữ embedding OpenAI đang có trong lúc thử một index riêng. Groq/Qwen, Voyage và local BGE là lựa chọn giai đoạn sau, không cần đăng ký tất cả ngay.

Vai trò đề xuất là suy luận kỹ thuật cho bài toán tiếp nhận cư dân; chưa có bằng chứng model nào thắng trên dữ liệu của dự án. Chất lượng tiếng Việt, tool call, trích dẫn đúng, độ trễ và tỷ lệ tạo ticket sai phải đo bằng cùng tập tình huống.

## Chat: danh sách ngắn

Giá USD cho **1 triệu token đầu vào / đầu ra**, Standard API; đầu vào chưa cache. Chưa gồm thuế, grounding/search, server tools hoặc các vòng gọi bổ sung. Không nhầm gói chat cá nhân với hạn mức API.

| Nhà cung cấp | Model ID được đối chiếu | Giá in / out | Miễn phí và vai trò đề xuất |
|---|---|---:|---|
| Google | `gemini-3.5-flash-lite` | $0.30 / $2.50 | Có free tier; thử phân loại, trích thông tin, câu trả lời đơn giản. [Giá](https://ai.google.dev/gemini-api/docs/pricing), [model stable](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite). |
| Google | `gemini-3.8-flash` | $0.75 / $3.75 tới 2026-12-31; $1.50 / $7.50 từ 2027-01-01 | Có free tier; thử làm model chính cho Reception/RAG. [Giá](https://ai.google.dev/gemini-api/docs/pricing), [model stable](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash). |
| Anthropic | `claude-sonnet-5-5` | $2 / $10 | API trả phí; thử ca khó, nhiều điều kiện/quy trình. [Model IDs](https://platform.claude.com/docs/en/models/overview), [giá](https://platform.claude.com/docs/en/about-claude/pricing). |
| Anthropic | `claude-haiku-4-5-20251001` | $1 / $5 | Lựa chọn rẻ hơn trong họ Claude; chưa cần thêm nếu đã dùng Gemini cho việc đơn giản. [Model IDs](https://platform.claude.com/docs/en/models/overview), [giá](https://platform.claude.com/docs/en/about-claude/pricing). |
| DeepSeek | `deepseek-flash` | Off-peak $0.15 / $0.60; peak $0.30 / $1.20 | API tính phí; thử dự phòng và tác vụ tiết kiệm. Đây là alias hiện tại của DeepSeek-V4.1-Flash. [Model và giá](https://api-docs.deepseek.com/quick_start/pricing/). |
| Groq | `qwen/qwen3.8-27b` | Paid $0.80 / $4 | Có Free Plan; thích hợp thử tốc độ và Qwen. Được đánh dấu **Preview**, chưa ưu tiên làm đường production chính. [Model](https://console.groq.com/docs/model/qwen/qwen3.8-27b), [giá](https://console.groq.com/docs/models), [limits](https://console.groq.com/docs/rate-limits). |

Google công bố hai model trên là stable, đều có function calling và structured outputs. Không cần mặc định chọn ID preview khi đã có stable. Trang giá Google ghi cập nhật 2026-10-01. [Flash-Lite capabilities](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite), [Flash capabilities](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash), [pricing](https://ai.google.dev/gemini-api/docs/pricing).

DeepSeek hỗ trợ JSON output, tool calls, OpenAI/Anthropic format và thinking/non-thinking. Tài liệu hiện tại hướng dẫn `deepseek-flash`; không lấy `deepseek-chat`/`deepseek-reasoner` trong hướng dẫn cũ làm mặc định mới. Peak là 01:00–04:00 và 06:00–10:00 UTC, thứ Hai–thứ Sáu, trừ ngày nghỉ công Trung Quốc; tương ứng **08:00–11:00 và 13:00–17:00 ở Việt Nam**. [Pricing](https://api-docs.deepseek.com/quick_start/pricing/), [API entrypoint](https://api-docs.deepseek.com/).

Groq hiện công bố free Qwen 30 RPM, 1.000 RPD, 8.000 TPM, 200.000 TPD; quota thực tế xem trong console của tổ chức. RAG prompt dài có thể chạm TPM sớm. Qwen có tool use/JSON, nhưng Groq ghi structured outputs hiện chưa kết hợp streaming hoặc tool use: phải kiểm tra tổ hợp request, không chỉ tên model. [Rate limits](https://console.groq.com/docs/rate-limits), [model](https://console.groq.com/docs/model/qwen/qwen3.8-27b), [structured outputs](https://console.groq.com/docs/structured-outputs).

## Embedding và reranker

Chat model không thay thế embedding model. Embedding quyết định tài liệu được tìm thấy; chat model tạo câu trả lời từ tài liệu. Reranker sắp xếp lại ứng viên sau retrieval, không thay vector đang lưu. [Voyage reranker guide](https://docs.voyageai.com/docs/reranker).

| Lựa chọn | Kích thước vector | Chi phí | Đề xuất |
|---|---|---|---|
| `gemini-embedding-2` | Default 3072; hỗ trợ 128–3072, khuyến nghị 768/1536/3072 | Free tier; paid text $0.20 / 1M input tokens | Ưu tiên thử **1536** nếu contract DB của repo đang cố định 1536. Stable, có cả multimodal. [Embedding docs](https://ai.google.dev/gemini-api/docs/embeddings), [giá](https://ai.google.dev/gemini-api/docs/pricing). |
| `voyage-4` / `voyage-4-lite` | 1024 mặc định; chỉ 256/512/1024/2048 | $0.06 / $0.02 mỗi 1M tokens; 200M token đầu tiên/account miễn phí | Thử chuyên biệt multilingual RAG ở giai đoạn sau. **Không có output 1536** trong danh sách chính thức. [Models](https://docs.voyageai.com/docs/embeddings), [giá](https://docs.voyageai.com/docs/pricing). |
| `BAAI/bge-m3` local | 1024; input tối đa 8192 | Không phí token của API bên ngoài; vẫn tốn máy, điện, vận hành | Chọn khi cần tự host; cần contract/index 1024 và benchmark CPU/GPU thực tế. Model multilingual, dense/sparse/ColBERT. [Model card của BAAI](https://huggingface.co/BAAI/bge-m3). |

`gemini-embedding-2` tự normalize cả vector 1536. Với `gemini-embedding-001` (text-only, stable cũ), vector giảm từ 3072 phải normalize thủ công; dùng `task_type=RETRIEVAL_QUERY` / `RETRIEVAL_DOCUMENT`. Model 2 không nhận `task_type`, cần instruction query/document trong prompt. **Embedding 001 và 2 không cùng không gian vector** và Google yêu cầu re-embed khi chuyển. [Google embeddings](https://ai.google.dev/gemini-api/docs/embeddings).

Nếu thêm reranking: `rerank-3-lite` của Voyage ($0.02 / 1M processed tokens; trang giá ghi 200M free tokens) hoặc `BAAI/bge-reranker-v2-m3` chạy local và hỗ trợ multilingual. Voyage tính token query lặp lại theo số tài liệu, không chỉ query một lần. [Reranker models](https://docs.voyageai.com/docs/reranker), [giá](https://docs.voyageai.com/docs/pricing), [BAAI model card](https://huggingface.co/BAAI/bge-reranker-v2-m3).

## Free tier, trial, local và dữ liệu cư dân

- **Gemini free tier** là quota API miễn phí, không vô hạn. Với Unpaid Services, Google dùng input/output để cải thiện sản phẩm, có thể có người review; điều khoản yêu cầu không gửi thông tin cá nhân, nhạy cảm hoặc bí mật. Cho Việt Nam, nên dùng dữ liệu giả/đã loại thông tin cá nhân để thử free; dùng project có active billing cho dữ liệu thật theo điều khoản Paid Services. Paid không dùng prompts/responses để cải thiện sản phẩm, nhưng điều này không đồng nghĩa zero retention. [Điều khoản Google](https://ai.google.dev/gemini-api/terms).
- **Groq Free Plan** có quota theo phút/ngày; giới hạn tổ chức cần đọc trực tiếp trong console. [Limits](https://console.groq.com/docs/rate-limits).
- **Voyage 200M free tokens/account** là số token miễn phí đầu tiên, không phải quota hàng tháng được reset. Free credits không áp dụng cho Batch. [Pricing](https://docs.voyageai.com/docs/pricing).
- **Local BGE** không trả tiền token cho nhà cung cấp; không phải hạ tầng miễn phí. Model card có hướng dẫn chạy bằng FlagEmbedding; chi phí máy và tốc độ phải tự đo. [BGE-M3](https://huggingface.co/BAAI/bge-m3).

## Các điểm phải xử lý khi nối vào repo

Đây là kết luận tích hợp suy ra từ API docs và contract 1536 mà phiên audit repo đang xác minh, không phải thay đổi code đã thực hiện:

1. Tách cấu hình chat và embedding: provider/key/base URL/model/dimension cho từng đường. Không thay một `OPENAI_BASE_URL` dùng chung rồi kỳ vọng embedding OpenAI vẫn hoạt động.
2. Gemini có OpenAI-compatible base URL `https://generativelanguage.googleapis.com/v1beta/openai/`, hỗ trợ function calling và structured output. Tuy nhiên ví dụ embedding compatibility còn dùng ID `gemini-embedding-2-preview` trong khi embedding guide đã ghi stable `gemini-embedding-2`: ưu tiên native embedding API hoặc smoke-test stable ID và `dimensions=1536` trước khi chọn adapter. [Compatibility docs](https://ai.google.dev/gemini-api/docs/openai), [stable embedding contract](https://ai.google.dev/gemini-api/docs/embeddings).
3. Claude nên dùng native API/adapter cho production. Anthropic nói lớp tương thích OpenAI chủ yếu để thử; `response_format` và tool `strict` bị bỏ qua. Chỉ thay base URL có thể làm mất đảm bảo JSON schema. [Anthropic compatibility limitations](https://platform.claude.com/docs/en/cli-sdks-libraries/libraries/openai-sdk).
4. Vector cùng chiều **không đảm bảo cùng không gian embedding**. Không trộn vector OpenAI/Gemini/BGE vào một index rồi query chéo model. Dùng collection/index hoặc phiên bản embedding riêng và re-embed tài liệu bằng model mới; không coi việc pad BGE 1024 lên 1536 là migration chất lượng hợp lệ. Google xác nhận trực tiếp tính không tương thích giữa hai đời embedding của chính họ. [Google migration notes](https://ai.google.dev/gemini-api/docs/embeddings).
5. Đo trên một tập câu hỏi tiếng Việt đã có đáp án/tài liệu đúng: retrieval recall, citation correctness, hallucination/refusal, JSON/tool validity, latency, cost. Đề xuất shortlist chưa thay thế kết quả kiểm chứng này.

Không xác nhận tài khoản người dùng đã có quyền truy cập model hoặc quota trên; chưa thực hiện authenticated smoke test.
