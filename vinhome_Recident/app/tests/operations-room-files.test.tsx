import { afterAll, afterEach, beforeAll, expect, test } from "bun:test";
import { GlobalRegistrator } from "@happy-dom/global-registrator";
import { typeInto } from "./type-into";
import type { RoomMessage } from "../src/lib/rooms/queries";

let cleanup: typeof import("@testing-library/react")["cleanup"];
let render: typeof import("@testing-library/react")["render"];
let waitFor: typeof import("@testing-library/react")["waitFor"];
let fireEvent: typeof import("@testing-library/react")["fireEvent"];
const originalFetch = globalThis.fetch;
beforeAll(async () => {
  GlobalRegistrator.register({ url: "http://localhost:3020/operations/team" });
  ({ cleanup, render, waitFor, fireEvent } = await import("@testing-library/react/pure"));
});
afterEach(() => { cleanup(); globalThis.fetch = originalFetch; });
afterAll(() => new Promise<void>((done) => setTimeout(() => { GlobalRegistrator.unregister(); done(); }, 50)));

test("what may be attached follows the platform's limits, and a file is named by its extension when the browser names no type", async () => {
  const { roomFileType, roomFilesRefusal } = await import("../src/lib/rooms/mutations");
  expect(roomFileType({ name: "anh.PNG", type: "image/png" })).toBe("image/png");
  expect(roomFileType({ name: "ghi-chu.md", type: "" })).toBe("text/markdown");
  // Excel's claim for a .csv is not a type the platform takes; the name is.
  expect(roomFileType({ name: "thong-ke.csv", type: "application/vnd.ms-excel" })).toBe("text/csv");
  expect(roomFileType({ name: "hop-dong.pdf", type: "application/pdf" })).toBeNull();
  const file = (name: string, type: string, size: number) => ({ name, type, size });
  expect(roomFilesRefusal([file("a.png", "image/png", 8 * 1024 * 1024)])).toBeNull();
  expect(roomFilesRefusal([file("a.png", "image/png", 8 * 1024 * 1024 + 1)])).toContain("ảnh tối đa 8 MB");
  expect(roomFilesRefusal([file("a.csv", "text/csv", 1024 * 1024 + 1)])).toContain("tệp văn bản tối đa 1 MB");
  expect(roomFilesRefusal([file("hop-dong.pdf", "application/pdf", 10)])).toContain("hop-dong.pdf: chỉ đính kèm được ảnh");
  expect(roomFilesRefusal(Array.from({ length: 9 }, (_, i) => file(`${i}.png`, "image/png", 10)))).toBe("Mỗi tin nhắn tối đa 8 tệp.");
});

test("the room shows a photo as a picture and a text file as a download, and sends what was attached", async () => {
  const { QueryClientProvider } = await import("@tanstack/react-query");
  const { queryClient } = await import("../src/query-client");
  const { RoomThread } = await import("../src/features/vinhomes-operations/connected/coordination/RoomThread");
  const messages: RoomMessage[] = [
    { id: "m1", seq: 1, sender_user_id: "me", sender_agent_id: null, created_at: "2026-10-05T01:00:00Z", body: { text: "" },
      files: [{ id: "f1", name: "thang-may.png", mime_type: "image/png", size_bytes: 204800 }, { id: "f2", name: "thong-ke.csv", mime_type: "text/csv", size_bytes: 2048 }] },
    { id: "m2", seq: 2, sender_user_id: "me", sender_agent_id: null, created_at: "2026-10-05T01:01:00Z", mention_status: "done",
      body: { text: "Tóm tắt yêu cầu hôm qua.", mentionAgentId: "report", routineRunId: "routine_run_1" }, files: [] },
  ];
  const sent: { url: string; type: string | null; body: unknown }[] = [];
  let failNext = true;
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), "http://localhost");
    const type = new Headers(init?.headers).get("content-type");
    sent.push({ url: url.pathname + url.search, type, body: type === "application/json" ? JSON.parse(String(init!.body)) : (init!.body as File).name });
    if (url.pathname.endsWith("/files")) return Response.json({ fileId: `stored-${(init!.body as File).name}` }, { status: 201 });
    if (failNext) { failNext = false; return Response.json({ detail: "x" }, { status: 503 }); }
    return Response.json({ id: "m3" }, { status: 201 });
  }) as typeof fetch;
  const view = render(<QueryClientProvider client={queryClient}>
    <RoomThread roomId="room-1" name="Ban quản lý Sapphire" messages={messages} userId="me"
      agents={[{ id: "report", name: "Agent Báo cáo", published: true, status: "active" }]} />
  </QueryClientProvider>);

  const picture = view.getByRole("img", { name: "thang-may.png" }) as HTMLImageElement;
  expect(picture.getAttribute("src")).toBe("/api/business/rooms/room-1/files/f1/content?inline=true");
  const download = view.getByRole("link", { name: /thong-ke\.csv/ });
  expect(download.getAttribute("href")).toBe("/api/business/rooms/room-1/files/f2/content");
  expect(download.getAttribute("download")).toBe("thong-ke.csv");
  expect(download.textContent).toContain("2 KB");
  expect(view.getByText(/Theo lịch · Hỏi @Agent Báo cáo/)).toBeTruthy();

  const picker = view.getByLabelText("Chọn ảnh hoặc tệp") as HTMLInputElement;
  const send = view.getByRole("button", { name: "Gửi tin nhắn" }) as HTMLButtonElement;
  expect(send.disabled).toBe(true);
  // A file the platform does not take is refused in words, before anything is uploaded.
  fireEvent.change(picker, { target: { files: [new File(["%PDF"], "hop-dong.pdf", { type: "application/pdf" })] } });
  expect(view.getByRole("alert").textContent).toContain("hop-dong.pdf: chỉ đính kèm được ảnh");
  expect(view.queryByRole("list", { name: "Tệp sẽ gửi" })).toBeNull();
  fireEvent.change(picker, { target: { files: [new File(["png"], "bien-ban.png", { type: "image/png" }), new File(["# Ghi chú"], "ghi-chu.md", { type: "" })] } });
  expect(view.queryByRole("alert")).toBeNull();
  expect(view.getByRole("list", { name: "Tệp sẽ gửi" }).textContent).toContain("bien-ban.png");
  // A message may be only its files.
  expect(send.disabled).toBe(false);
  const {default:userEvent} = await import('@testing-library/user-event');
  const user = userEvent.setup({document});
  await user.click(send);
  // The send failed after the files were stored: they are still on the composer, and sending again stores nothing twice.
  expect((await view.findByRole("alert")).textContent).toContain("Không gửi được tin nhắn nhóm");
  expect(view.getByRole("list", { name: "Tệp sẽ gửi" }).textContent).toContain("ghi-chu.md");
  await user.click(view.getByRole("button", { name: "Gửi tin nhắn" }));
  await waitFor(() => expect(view.queryByRole("list", { name: "Tệp sẽ gửi" })).toBeNull());
  expect(sent.filter((s) => s.url.includes("/files?")).map((s) => [s.url, s.type, s.body])).toEqual([
    ["/api/business/rooms/room-1/files?filename=bien-ban.png&mimeType=image%2Fpng", "application/octet-stream", "bien-ban.png"],
    ["/api/business/rooms/room-1/files?filename=ghi-chu.md&mimeType=text%2Fmarkdown", "application/octet-stream", "ghi-chu.md"]]);
  const posts = sent.filter((s) => s.url.endsWith("/messages")).map((s) => s.body as { text: string; file_ids: string[]; client_message_id: string });
  expect(posts.map((p) => [p.text, p.file_ids])).toEqual([["", ["stored-bien-ban.png", "stored-ghi-chu.md"]], ["", ["stored-bien-ban.png", "stored-ghi-chu.md"]]]);
  // The same message, sent again under the same id.
  expect(posts[0]!.client_message_id).toBe(posts[1]!.client_message_id);
});

test("inside a session a question carries its files, and files alone are not a question", async () => {
  const { QueryClientProvider, QueryClient } = await import("@tanstack/react-query");
  const { SessionThread } = await import("../src/features/vinhomes-operations/connected/coordination/SessionThread");
  const messages: RoomMessage[] = [{ id: "q1", seq: 3, sender_user_id: "me", sender_agent_id: null, created_at: "2026-10-05T02:00:00Z", mention_status: "done",
    body: { text: "VH-AAAAAAAAAAAA: Ảnh này là rò ở đâu?", sessionId: "s1", kind: "session_question", mentionAgentId: "tech" },
    files: [{ id: "f9", name: "vet-ro.png", mime_type: "image/png", size_bytes: 1024 }] }];
  const sent: { url: string; body: unknown }[] = [];
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), "http://localhost");
    if ((init?.method || "GET") === "GET") {
      if (url.pathname.endsWith("/session")) return Response.json({ session: { id: "s1", status: "running", state_version: 1, supervisor_name: "Supervisor" },
        room: { members: ["Agent Kỹ thuật"], tasks: [], plan: null }, awaitingManagementApproval: false });
      return Response.json({ items: [], allowed: [], pending: null });
    }
    const json = new Headers(init?.headers).get("content-type") === "application/json";
    sent.push({ url: url.pathname + url.search, body: json ? JSON.parse(String(init!.body)) : (init!.body as File).name });
    return Response.json(url.pathname.endsWith("/files") ? { fileId: "stored-1" } : { id: "q2", status: "queued" }, { status: 201 });
  }) as typeof fetch;
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const view = render(<QueryClientProvider client={client}>
    <SessionThread roomId="room-1" userId="me" messages={messages}
      session={{ id: "s1", ticket_id: "t1", ticket_code: "VH-AAAAAAAAAAAA", ticket_title: "Vòi bếp rò nước", status: "running",
        created_at: "2026-10-05T01:00:00Z", updated_at: "2026-10-05T02:00:00Z", ticket_status: "open", plan_status: null, runtime: { phase: "planning" } }}
      agents={[{ id: "tech", name: "Agent Kỹ thuật", published: true, status: "active" }]} />
  </QueryClientProvider>);

  // What was asked before shows its photo, read through the session's room.
  expect((view.getByRole("img", { name: "vet-ro.png" }) as HTMLImageElement).getAttribute("src")).toBe("/api/business/rooms/room-1/files/f9/content?inline=true");
  const send = view.getByRole("button", { name: "Gửi tin nhắn" }) as HTMLButtonElement;
  await waitFor(() => expect((view.getByLabelText("Nội dung") as HTMLTextAreaElement).disabled).toBe(false));
  fireEvent.change(view.getByLabelText("Chọn ảnh hoặc tệp"), { target: { files: [new File(["a,b"], "so-lieu.csv", { type: "text/csv" })] } });
  expect(view.getByRole("list", { name: "Tệp sẽ gửi" }).textContent).toContain("so-lieu.csv");
  expect(send.disabled).toBe(true);
  await typeInto(view.getByLabelText("Nội dung"), "Số liệu này có bất thường không?");
  expect(send.disabled).toBe(false);
  fireEvent.click(send);
  await waitFor(() => expect(sent.length).toBe(2));
  expect(sent[0]).toEqual({ url: "/api/business/rooms/room-1/files?filename=so-lieu.csv&mimeType=text%2Fcsv", body: "so-lieu.csv" });
  expect(sent[1]!.url).toBe("/api/business/tickets/t1/session/questions");
  expect(sent[1]!.body).toMatchObject({ text: "Số liệu này có bất thường không?", file_ids: ["stored-1"] });
});
