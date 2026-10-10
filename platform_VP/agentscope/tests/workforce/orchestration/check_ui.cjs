/* Local PHH React behavioral tests. Dependencies live in a temp directory.
 * No global app/package/transport changes, no mocked success in production.
 */
const path = require("node:path");
const fs = require("node:fs");
const assert = require("node:assert/strict");
const { createRequire } = require("node:module");
const tempRoot = process.argv[2];
if (!tempRoot) throw new Error("Supply the temporary UI dependency directory");
const tempRequire = createRequire(path.join(tempRoot, "package.json"));
const ts = tempRequire("typescript");
const repoRoot = path.resolve(__dirname, "../../..");
const chatRoot = path.join(repoRoot, "examples/web_ui/frontend/src/features/workforce/chat");
const sources = [path.join(chatRoot, "WorkforceChat.tsx"), path.join(chatRoot, "ticket_timeline/TicketTimeline.tsx")];
const options = {
  noEmit: true, strict: true, skipLibCheck: true,
  target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext,
  moduleResolution: ts.ModuleResolutionKind.Bundler, jsx: ts.JsxEmit.ReactJSX,
  paths: {
    "react": [path.join(tempRoot, "node_modules/@types/react/index.d.ts")],
    "react/*": [path.join(tempRoot, "node_modules/@types/react/*")],
  },
  typeRoots: [path.join(tempRoot, "node_modules/@types")],
};
const program = ts.createProgram(sources, options);
const diagnostics = ts.getPreEmitDiagnostics(program);
if (diagnostics.length) {
  console.error(ts.formatDiagnosticsWithColorAndContext(diagnostics, {
    getCurrentDirectory: () => repoRoot, getCanonicalFileName: x => x, getNewLine: () => "\n",
  }));
  process.exit(1);
}
function compile(file) {
  const output = ts.transpileModule(fs.readFileSync(file, "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  const compiledPath = path.join(tempRoot, path.basename(file, ".tsx") + ".cjs");
  fs.writeFileSync(compiledPath, output);
  return tempRequire(compiledPath);
}
const { JSDOM } = tempRequire("jsdom");
const dom = new JSDOM("<!doctype html><html><body></body></html>", { url: "http://localhost" });
global.window = dom.window;
global.document = dom.window.document;
Object.defineProperty(global, "navigator", { value: dom.window.navigator, configurable: true });
global.HTMLElement = dom.window.HTMLElement;
global.MutationObserver = dom.window.MutationObserver;
global.IS_REACT_ACT_ENVIRONMENT = true;
const React = tempRequire("react");
const { render, screen, cleanup, waitFor } = tempRequire("@testing-library/react");
const user = tempRequire("@testing-library/user-event").default.setup({ document: dom.window.document });
const { WorkforceChat } = compile(sources[0]);
const { TicketTimeline } = compile(sources[1]);
let count = 0;
async function test(name, fn) {
  try { await fn(); console.log("PASS " + name); count++; }
  finally { cleanup(); }
}
const member = { agent_id: "Hotel", name: "Hotel", version_id: "v3" };
const view = {
  title: "Chuyến đi", mode: "group", loading: false, status_label: "Đang xử lý",
  members: [member], available_members: [member, { agent_id: "Car", name: "Car", version_id: "v3" }],
  messages: [{ message_id: "m1", speaker: "Hotel", content: "hello" }, { message_id: "m1", speaker: "Hotel", content: "hello" }],
  quotes: [{ id: "quote", label: "Khách sạn", amount_minor: 10_000_000, currency: "VND", expired: false }],
  can_cancel: true, can_resume: true, pending_question: "Bạn muốn đi ngày nào?",
};
function props(overrides = {}) {
  const noOp = async () => {};
  return { view, onSend: noOp, onAddMember: noOp, onOpenDirect: noOp,
    onSelectQuote: noOp, onCancel: noOp, onResume: noOp, ...overrides };
}
(async () => {
  await test("G2-T09 message dedupe, pending question, approval slot", async () => {
    render(React.createElement(WorkforceChat, props({ approvalCard: React.createElement("p", null, "Approval supplied by Execution") })));
    assert.equal(screen.getAllByText("hello").length, 1);
    assert.ok(screen.getByText("Bạn muốn đi ngày nào?"));
    assert.ok(screen.getByText("Approval supplied by Execution"));
  });
  await test("G2-T09 loading blocks send", async () => {
    render(React.createElement(WorkforceChat, props({ view: { ...view, loading: true } })));
    await user.type(screen.getByRole("textbox"), "hello");
    assert.equal(screen.getByRole("button", { name: "Gửi" }).disabled, true);
  });
  await test("G2-T01 mention uses ID; retry preserves message ID", async () => {
    const commands = [];
    render(React.createElement(WorkforceChat, props({ onSend: async command => {
      commands.push(command); if (commands.length === 1) throw new Error("network loss");
    } })));
    await user.selectOptions(screen.getByRole("combobox"), "Hotel");
    await user.type(screen.getByRole("textbox"), "amenities?");
    await user.click(screen.getByRole("button", { name: "Gửi" }));
    await screen.findByRole("alert");
    await user.click(screen.getByRole("button", { name: "Gửi" }));
    await waitFor(() => assert.equal(commands.length, 2));
    assert.equal(commands[0].client_message_id, commands[1].client_message_id);
    assert.equal(commands[0].target_agent_id, "Hotel");
    await waitFor(() => assert.equal(screen.getByRole("textbox").value, ""));
  });
  await test("G2-T09 add/direct/quote/cancel/resume dispatch actual callbacks", async () => {
    const calls = [];
    render(React.createElement(WorkforceChat, props({
      onAddMember: async id => calls.push("add:" + id), onOpenDirect: async id => calls.push("direct:" + id),
      onSelectQuote: async id => calls.push("quote:" + id), onCancel: async () => calls.push("cancel"),
      onResume: async () => calls.push("resume"),
    })));
    assert.equal(screen.queryByRole("button", { name: "Thêm Hotel" }), null);
    for (const name of ["Thêm Car", "Chat riêng", "Chọn", "Dừng lượt xử lý", "Tiếp tục"]) {
      await user.click(screen.getByRole("button", { name }));
    }
    assert.deepEqual(calls, ["add:Car", "direct:Hotel", "quote:quote", "cancel", "resume"]);
  });
  await test("G2-T09 expired quote is not selectable", async () => {
    render(React.createElement(WorkforceChat, props({ view: { ...view, quotes: [{ ...view.quotes[0], expired: true }] } })));
    assert.equal(screen.queryByRole("button", { name: "Chọn" }), null);
  });
  const ticket = { workflow_id: "workflow-A", external_ticket_id: "ticket-A", title: "Sửa điều hòa",
    state: "awaiting_confirmation", revision: 7, next_action: "confirm_close", status_label: "Chờ xác nhận",
    reconnecting: true, messages: view.messages };
  await test("G3-T11 timeline dedupe and close exact workflow/revision", async () => {
    const calls = [];
    render(React.createElement(TicketTimeline, { ticket, onClose: async (...args) => calls.push(args) }));
    assert.equal(screen.getAllByText("hello").length, 1);
    assert.ok(screen.getByText("Đang kết nối lại…"));
    await user.click(screen.getByRole("button", { name: "Xác nhận hoàn tất" }));
    assert.deepEqual(calls, [["workflow-A", 7]]);
  });
  await test("G3-T13 closed ticket cannot close again; error shown on failure", async () => {
    const result = render(React.createElement(TicketTimeline, { ticket: { ...ticket, state: "closed" }, onClose: async () => {} }));
    assert.equal(screen.queryByRole("button", { name: "Xác nhận hoàn tất" }), null);
    result.rerender(React.createElement(TicketTimeline, { ticket, onClose: async () => { throw new Error("conflict"); } }));
    await user.click(screen.getByRole("button", { name: "Xác nhận hoàn tất" }));
    await screen.findByRole("alert");
  });
  console.log(`TypeScript strict PASS; ${count} React behavior tests PASS`);
})().catch(error => { console.error(error); process.exitCode = 1; });
