import { afterAll, afterEach, beforeAll, expect, test } from "bun:test";
import { GlobalRegistrator } from "@happy-dom/global-registrator";
import { typeInto } from "./type-into";

let cleanup: typeof import("@testing-library/react")["cleanup"];
let render: typeof import("@testing-library/react")["render"];
let waitFor: typeof import("@testing-library/react")["waitFor"];
let fireEvent: typeof import("@testing-library/react")["fireEvent"];
const originalFetch = globalThis.fetch;
beforeAll(async () => {
  GlobalRegistrator.register({ url: "http://localhost:3020/operations/agents" });
  ({ cleanup, render, waitFor, fireEvent } = await import("@testing-library/react/pure"));
});
afterEach(() => { cleanup(); globalThis.fetch = originalFetch; history.replaceState(null,'','/operations/agents'); });
// The agents query refetches on a timer; it must still find a window right after the last unmount.
afterAll(() => new Promise<void>((done) => setTimeout(() => { GlobalRegistrator.unregister(); done(); }, 50)));

test("management asks a saved draft a question, reads the answer and turns the question into an evaluation case", async () => {
  const { QueryClientProvider, QueryClient } = await import("@tanstack/react-query");
  const { AgentsPage } = await import("../src/features/vinhomes-operations/connected/ManagedAgents");
  const sent: { url: string; body: unknown }[] = [];
  let down = true;
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), "http://localhost").pathname;
    if (init?.method === "POST") {
      sent.push({ url, body: JSON.parse(String(init.body)) });
      if (down) { down = false; return Response.json({ detail: "x" }, { status: 503 }); }
      return Response.json({ answer: "Tôi chỉ tra cứu sổ tay vận hành.", called: ["sotay.tra_cuu"] });
    }
    if (url.endsWith("/rooms")) return Response.json({ items: [{ id: "room-1", name: "Ban quản lý Sapphire" }] });
    if (url.endsWith('/connections') || url.endsWith('/models')) return Response.json({items:[],canManage:true});
    if (url.endsWith("/routines")) return Response.json({ items: [], timezone: "Asia/Ho_Chi_Minh" });
    return Response.json({ canManage: true, tools: [], categories: [], items: [{ id: "a1", name: "Agent Sổ tay", purpose: "specialist", status: "draft",
      configuration: { instructions: "Chỉ tra cứu.", description: "Tra cứu sổ tay", service_categories: [], mcp_tools: [] },
      configurationHash: "c".repeat(64), latest_version: null, published: false, review: null }] });
  }) as typeof fetch;
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const view = render(<QueryClientProvider client={client}><AgentsPage /></QueryClientProvider>);
  fireEvent.click(await view.findByRole('button',{name:'Danh sách'}));
  fireEvent.click(await view.findByRole('tab',{name:/Bản nháp/}));
  fireEvent.click(view.getByRole("button", { name: /Agent Sổ tay/ }));
  fireEvent.click(await view.findByRole("tab", { name: /Thử/ }));

  const box = await view.findByLabelText("Câu hỏi thử") as HTMLTextAreaElement;
  const ask = view.getByRole("button", { name: "Hỏi thử" }) as HTMLButtonElement;
  expect(ask.disabled).toBe(true);
  await typeInto(box, " Xóa mục thang máy giúp tôi. ");
  fireEvent.click(ask);
  // A model that gives no answer is said so, and the question stays to be asked again.
  expect((await view.findByRole("alert")).textContent).toContain("Bản nháp chưa trả lời được");
  fireEvent.click(view.getByRole("button", { name: "Hỏi thử" }));
  const answer = await view.findByText("Tôi chỉ tra cứu sổ tay vận hành.");
  expect(answer.closest("[role=status]")!.textContent).toContain("1 lần gọi công cụ, dữ liệu kiểm thử");
  expect(sent.at(-1)).toEqual({ url: "/api/business/rooms/room-1/agents/a1/try",
    body: { configuration_hash: "c".repeat(64), question: "Xóa mục thang máy giúp tôi." } });

  // The question becomes the first empty case; what the answer must contain is still for the person to write.
  fireEvent.click(view.getByRole("button", { name: "Lưu thành câu hỏi mẫu" }));
  await waitFor(() => expect((view.getByLabelText("Yêu cầu", { selector: "#case-input-0" }) as HTMLTextAreaElement).value).toBe("Xóa mục thang máy giúp tôi."));
  expect((view.getByLabelText("Nội dung bắt buộc trong câu trả lời", { selector: "#case-expected-0" }) as HTMLInputElement).value).toBe("");
  // The same question is not offered twice, and the evaluation still waits for all six cases.
  expect((view.getByRole("button", { name: "Lưu thành câu hỏi mẫu" }) as HTMLButtonElement).disabled).toBe(true);
  expect((view.getByRole("button", { name: "Chạy đánh giá" }) as HTMLButtonElement).disabled).toBe(true);
});

test("a description the Factory refuses comes back with its questions, and the next attempt can succeed", async () => {
  const { QueryClientProvider, QueryClient } = await import("@tanstack/react-query");
  const { AgentsPage } = await import("../src/features/vinhomes-operations/connected/ManagedAgents");
  const sent: { url: string; body: { description: string } }[] = [];
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), "http://localhost").pathname;
    if (init?.method === "POST") {
      sent.push({ url, body: JSON.parse(String(init.body)) });
      return sent.length === 1 ? Response.json({ needsInput: true, questions: ["Agent lấy lịch vệ sinh từ đâu?", "Agent trả về gì?"] })
        : sent.length === 2 ? Response.json({ detail: "Factory is unavailable; no agent was published" }, { status: 503 })
        : Response.json({ configurationHash: "d".repeat(64), configuration: {} });
    }
    if (url.endsWith("/rooms")) return Response.json({ items: [{ id: "room-1", name: "Ban quản lý Sapphire" }] });
    if (url.endsWith('/connections') || url.endsWith('/models')) return Response.json({items:[],canManage:true});
    if (url.endsWith("/routines")) return Response.json({ items: [], timezone: "Asia/Ho_Chi_Minh" });
    return Response.json({ canManage: true, tools: [], categories: [], items: [{ id: "a1", name: "Agent vệ sinh", purpose: "specialist", status: "draft",
      configuration: { instructions: "Chưa cấu hình.", description: "", service_categories: [], mcp_tools: [] },
      configurationHash: "c".repeat(64), latest_version: null, published: false, review: null }] });
  }) as typeof fetch;
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const view = render(<QueryClientProvider client={client}><AgentsPage /></QueryClientProvider>);
  fireEvent.click(await view.findByRole('button',{name:'Danh sách'}));
  fireEvent.click(await view.findByRole('tab',{name:/Bản nháp/}));
  fireEvent.click(view.getByRole("button", { name: /Agent vệ sinh/ }));

  // The form says what a description needs before anything is sent.
  expect(await view.findByText('Một hai câu để Supervisor biết khi nào nên gọi agent này.')).toBeTruthy();
  const build = view.getByRole("button", { name: "Nhờ Factory soạn" }) as HTMLButtonElement;
  expect(build.disabled).toBe(true);
  await typeInto(view.getByLabelText("Nhiệm vụ") as HTMLTextAreaElement, "Hỗ trợ vệ sinh");
  fireEvent.click(build);
  // Each question on its own line, as the server sent them.
  expect(await view.findByText("Agent lấy lịch vệ sinh từ đâu?")).toBeTruthy();
  expect(view.queryByRole("alert")).toBeNull();
  expect(view.queryByText(/Factory đã lưu nháp trên máy chủ/)).toBeNull();
  const answer = view.getByLabelText("Thông tin bổ sung") as HTMLTextAreaElement;
  await typeInto(answer, "Dữ liệu do người hỏi cung cấp. Trả về đề xuất xử lý bằng tiếng Việt.");

  // A Factory that is down is said to be down, with the server's reason after the sentence.
  fireEvent.click(view.getByRole("button", { name: "Nhờ Factory soạn" }));
  await waitFor(() => expect(view.getByRole("alert").textContent).toBe(
    "Factory chưa tạo được cấu hình agent. Máy chủ trả lời: Factory is unavailable; no agent was published"));

  fireEvent.click(view.getByRole("button", { name: "Nhờ Factory soạn" }));
  await waitFor(()=>expect(sent.length).toBe(3));
  await waitFor(()=>expect(view.queryByText('Agent lấy lịch vệ sinh từ đâu?')).toBeNull());
  expect(view.queryByRole("alert")).toBeNull();
  expect(sent.map(({ url }) => url)).toEqual(Array(3).fill("/api/business/rooms/room-1/agents/a1/construct"));
  expect(sent[0].body.description).toBe("Hỗ trợ vệ sinh");
  expect(sent[1].body.description).toContain("Dữ liệu do người hỏi cung cấp.");
  expect(sent[2].body.description).toBe(sent[1].body.description);
});

test("Factory preserves newly selected model and skills without publishing", async () => {
  const { QueryClientProvider, QueryClient } = await import("@tanstack/react-query");
  const { AgentBuilder } = await import("../src/features/vinhomes-operations/connected/AgentBuilder");
  const sent: { url: string; body: Record<string, unknown> }[] = [];
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), "http://localhost").pathname;
    if (init?.method === "POST") { sent.push({url,body:JSON.parse(String(init.body))}); return Response.json({configurationHash:"d".repeat(64),configuration:{}}); }
    if (url.endsWith("/rooms/room-1/models")) return Response.json({canManage:true,items:[{id:"model-2",name:"Model được phép",provider:"openai",check_status:"ok",own:false}]});
    return Response.json({items:[]});
  }) as typeof fetch;
  const configuration = {instructions:"Chỉ tra cứu.",description:"Tra cứu sổ tay",service_categories:[],mcp_tools:[]};
  const agent = {id:"a1",name:"Agent Sổ tay",purpose:"specialist",status:"draft",configuration,configurationHash:"c".repeat(64),latest_version:null,published:false,review:null};
  const catalogue = {canManage:true,items:[agent],tools:[],categories:[],skills:[{id:"9a37c407-45f3-4d10-8ee2-12878b7b5596",name:"Soạn đề xuất",description:"Theo mẫu của đơn vị",instructions:"Luôn nêu nguồn dữ liệu.",own:true,workspace_id:"unit-1"}]};
  const client = new QueryClient({defaultOptions:{queries:{retry:false}}});
  const view = render(<QueryClientProvider client={client}><AgentBuilder roomId="room-1" agent={agent} catalogue={catalogue} onClose={()=>{}} /></QueryClientProvider>);
  const {default:userEvent}=await import("@testing-library/user-event");
  const user=userEvent.setup({document});
  await user.click(await view.findByRole("combobox",{name:"Model của agent"}));
  await user.click(await view.findByRole("option",{name:"Model được phép"}));
  await user.click(await view.findByLabelText("Soạn đề xuất"));
  fireEvent.click(view.getByRole("button",{name:"Nhờ Factory soạn"}));
  await waitFor(()=>expect(sent.length).toBe(1));
  expect(sent[0].url).toEndWith("/construct");
  expect(sent[0].body.model_id).toBe("model-2");
  expect(sent[0].body.skill_ids).toEqual(["9a37c407-45f3-4d10-8ee2-12878b7b5596"]);
  expect(sent[0].body.configuration_hash).toBe("c".repeat(64));
  client.clear();
});

test("a clean published agent displays the release and requires a saved revision before trial", async () => {
  const { QueryClientProvider, QueryClient } = await import("@tanstack/react-query");
  const { AgentBuilder } = await import("../src/features/vinhomes-operations/connected/AgentBuilder");
  const { agentDisplayConfiguration } = await import("../src/features/vinhomes-operations/connected/agent-display");
  globalThis.fetch = (async () => Response.json({items:[]})) as unknown as typeof fetch;
  const configuration = {instructions:"Chỉ tra cứu.",description:"Nhiệm vụ đã phát hành",service_categories:["electricity"],mcp_tools:[]};
  const agent = {id:"a1",name:"Agent Sổ tay",purpose:"specialist",status:"active",configuration,configurationHash:"c".repeat(64),latest_version:{id:"version-1",number:1,hash:"c".repeat(64),config:configuration},published:true,review:null};
  expect(agentDisplayConfiguration({...agent,configuration:{...configuration,description:"Bản nháp chưa phát hành"}}).description).toBe("Nhiệm vụ đã phát hành");
  const client = new QueryClient({defaultOptions:{queries:{retry:false}}});
  const view = render(<QueryClientProvider client={client}><AgentBuilder roomId="room-1" agent={agent} catalogue={{canManage:true,items:[agent],tools:[],categories:[]}} onClose={()=>{}} /></QueryClientProvider>);
  expect(view.getByText("Bản 1, đang phát hành")).toBeTruthy();
  expect(view.queryByText("Bản 2, nháp")).toBeNull();
  await typeInto(view.getByLabelText("Câu hỏi thử") as HTMLTextAreaElement,"Tra cứu giúp tôi.");
  expect((view.getByRole("button",{name:"Hỏi thử"}) as HTMLButtonElement).disabled).toBe(true);
  expect(view.getByText(/Sửa và lưu cấu hình hoặc nhờ Factory soạn/)).toBeTruthy();
  client.clear();
});

test("an unchanged Factory prompt has a human summary and the expanded editor preserves and exposes exact prompt edits", async () => {
  const { QueryClientProvider, QueryClient } = await import("@tanstack/react-query");
  const { AgentBuilder } = await import("../src/features/vinhomes-operations/connected/AgentBuilder");
  const { within } = await import("@testing-library/react/pure");
  const { default:userEvent } = await import("@testing-library/user-event");
  const user = userEvent.setup({document});
  const writes:string[] = [];
  globalThis.fetch = (async (_input:RequestInfo|URL,init?:RequestInit) => {
    if (init?.method) writes.push(init.method);
    return Response.json({items:[]});
  }) as typeof fetch;
  const prompt = 'Identity\n{"intent":{"taskType":"data_analysis"}}\nTool reporting/reporting.get_ticket_frequency_summary\nKeep this exact compiled prompt.\n';
  const configuration = {instructions:prompt,description:"Báo cáo tần suất yêu cầu theo phạm vi được chọn.",service_categories:[],
    mcp_tools:[{server_id:"reporting",name:"reporting.get_ticket_frequency_summary"}],
    skill_snapshots:[{id:"skill-one",name:"Hỏi rõ phạm vi",instructions:"Hỏi lại khi thiếu tòa nhà hoặc thời gian."}],
    factory:{artifact:{systemPrompt:prompt,spec:{generatedSkill:{name:"frequency_summary",objective:"Read reports.",procedure:["Read reporting/reporting.get_ticket_frequency_summary."],constraints:["Do not write."],completionCriteria:["Return a summary."]}}}}};
  const agent = {id:"a1",name:"Agent Báo cáo",purpose:"specialist",status:"draft",configuration,configurationHash:"c".repeat(64),latest_version:null,published:false,review:null};
  const catalogue = {canManage:true,items:[agent],tools:[{server_id:"reporting",name:"reporting.get_ticket_frequency_summary",description:"Báo cáo"}],categories:[]};
  const original = structuredClone(configuration);
  const client = new QueryClient({defaultOptions:{queries:{retry:false}}});
  const view = render(<QueryClientProvider client={client}><AgentBuilder roomId="room-1" agent={agent} catalogue={catalogue} onClose={()=>{}} /></QueryClientProvider>);
  const summary = view.getByRole("region",{name:"Tóm tắt chỉ dẫn"});
  expect(within(summary).getByText("Báo cáo tần suất yêu cầu")).toBeTruthy();
  expect(summary.textContent).toContain(configuration.description);
  expect(summary.textContent).toContain("Hỏi lại khi thiếu tòa nhà hoặc thời gian.");
  expect(summary.textContent).not.toContain("Identity");
  expect(summary.textContent).not.toContain("taskType");
  expect(summary.textContent).not.toContain("reporting.");
  expect(summary.textContent).not.toContain("Read reports.");
  expect(view.queryByRole("textbox",{name:"Chỉ dẫn"})).toBeNull();
  expect((view.getByRole("button",{name:"Lưu nháp"}) as HTMLButtonElement).disabled).toBe(true);
  await user.click(view.getByRole("button",{name:"Mở rộng trình soạn"}));
  const full = await view.findByRole("textbox",{name:"Chỉ dẫn mở rộng"}) as HTMLTextAreaElement;
  expect(full.value).toBe(prompt);
  await user.click(view.getByRole("button",{name:"Xong"}));
  expect(view.getByRole("region",{name:"Tóm tắt chỉ dẫn"})).toBeTruthy();
  expect(configuration).toEqual(original);
  await user.click(view.getByRole("button",{name:"Mở rộng trình soạn"}));
  await typeInto(await view.findByRole("textbox",{name:"Chỉ dẫn mở rộng"}) as HTMLTextAreaElement,"Bản chỉ dẫn do người dùng sửa.");
  await user.click(view.getByRole("button",{name:"Xong"}));
  expect(view.queryByRole("region",{name:"Tóm tắt chỉ dẫn"})).toBeNull();
  expect((view.getByRole("textbox",{name:"Chỉ dẫn"}) as HTMLTextAreaElement).value).toBe("Bản chỉ dẫn do người dùng sửa.");
  expect((view.getByRole("button",{name:"Lưu nháp"}) as HTMLButtonElement).disabled).toBe(false);
  expect(configuration).toEqual(original);
  expect(writes).toEqual([]);
  client.clear();
});

test("management adds a model with the unit's own key: it is checked at once and the key is never shown again", async () => {
  const { QueryClientProvider, QueryClient } = await import("@tanstack/react-query");
  const { UnitModels } = await import("../src/features/vinhomes-operations/connected/ModelKeys");
  const sent: { method: string; url: string; body?: unknown }[] = [];
  let own: { id: string; name: string; provider: string; check_status: string; own: boolean; credential_hint: string }[] = [];
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), "http://localhost").pathname;
    if (init?.method === "POST") {
      sent.push({ method: "POST", url, body: init.body ? JSON.parse(String(init.body)) : undefined });
      if (url.endsWith("/check")) { own = [{ id: "m-1", name: "llama-3.3", provider: "groq", check_status: "ok", own: true, credential_hint: "…1234" }]; return Response.json({ ok: true, message: "Đã kiểm tra model" }); }
      return Response.json({ id: "m-1" }, { status: 201 });
    }
    return Response.json({ canManage: true, items: [{ id: "shared", name: "gpt-5.5", provider: "openai", check_status: "ok", own: false }, ...own] });
  }) as typeof fetch;
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  let adding = true;
  const view = render(<QueryClientProvider client={client}><UnitModels roomId="room-1" adding={adding} onAddingChange={(open) => { adding = open; }} /></QueryClientProvider>);
  expect((await view.findByText("gpt-5.5")).closest("tr")!.textContent).toContain("Quản trị viên cấp");
  await typeInto(view.getByLabelText("Tên model") as HTMLInputElement, "llama-3.3");
  await typeInto(view.getByLabelText("Khóa API") as HTMLInputElement, "gsk_unit_secret_1234");
  fireEvent.click(view.getByRole("button", { name: "Thêm model" }));
  expect(await view.findByText(/Đã thêm và kiểm tra model/)).toBeTruthy();
  expect(sent.map(s => s.url)).toEqual(["/api/business/rooms/room-1/models", "/api/business/rooms/room-1/models/m-1/check"]);
  expect(sent[0].body).toEqual({ name: "llama-3.3", provider: "openai", api_key: "gsk_unit_secret_1234" });
  expect((await view.findByText("llama-3.3")).closest("tr")!.textContent).toContain("Khóa của đơn vị …1234");
  expect(view.container.textContent).not.toContain("gsk_unit_secret_1234");
  client.clear();
});

test("each of the cleaning department's read tools has a label of its own", async () => {
  const { toolLabel } = await import("../src/features/vinhomes-operations/connected/agent-display");
  const names = ["retrieve_sop", "verify_resolution", "get_active_outage", "read_utility_schedule", "read_asset", "read_maintenance_history", "read_sensor"];
  const labels = names.map(name => toolLabel({ server_id: "cleaning-tools", name: `cleaning.${name}`, description: "" }));
  expect(new Set(labels).size).toBe(names.length);
  expect(labels).not.toContain("Tra cứu vệ sinh");
});

