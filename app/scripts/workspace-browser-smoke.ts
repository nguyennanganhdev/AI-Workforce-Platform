// Isolated Chrome debugging profile on 9333; existing FE servers on 3020 and 3011.
// Each fixture storage key is backed up and restored. No backend calls are made here.
import { seedWorkspace } from "../src/features/vinhomes-operations/workspace/model";
const target = await fetch(
  "http://127.0.0.1:9333/json/new?http://127.0.0.1:3020/operations/login",
  { method: "PUT" },
).then((r) => r.json());
const socket = new WebSocket(target.webSocketDebuggerUrl);
await new Promise<void>((resolve, reject) => {
  socket.onopen = () => resolve();
  socket.onerror = reject;
});
let seq = 0;
const pending = new Map<
  number,
  { resolve: (v: any) => void; reject: (e: Error) => void }
>();
const errors: string[] = [];
socket.onmessage = (event) => {
  const m = JSON.parse(String(event.data));
  if (m.id) {
    const p = pending.get(m.id);
    pending.delete(m.id);
    m.error
      ? p?.reject(new Error(JSON.stringify(m.error)))
      : p?.resolve(m.result);
  } else if (m.method === "Runtime.exceptionThrown")
    errors.push(JSON.stringify(m.params.exceptionDetails));
};
const cmd = (method: string, params: Record<string, unknown> = {}) =>
  new Promise<any>((resolve, reject) => {
    const id = ++seq;
    const t = setTimeout(() => reject(new Error(`Timeout ${method}`)), 20000);
    pending.set(id, {
      resolve: (v) => {
        clearTimeout(t);
        resolve(v);
      },
      reject: (e) => {
        clearTimeout(t);
        reject(e);
      },
    });
    socket.send(JSON.stringify({ id, method, params }));
  });
async function js(expression: string) {
  const r = await cmd("Runtime.evaluate", {
    expression,
    returnByValue: true,
    awaitPromise: true,
  });
  if (r.exceptionDetails) throw new Error(JSON.stringify(r.exceptionDetails));
  return r.result.value;
}
async function until(expression: string) {
  for (let i = 0; i < 100; i++) {
    try {
      if (await js(expression)) return;
    } catch {}
    await Bun.sleep(150);
  }
  throw new Error(
    `Not reached: ${expression}\n${await js("document.body.innerText")}`,
  );
}
async function go(path: string) {
  path = path.replace(
    "/operations/dispatch",
    activeRole.startsWith("demo-manager")
      ? "/operations/kanban"
      : "/operations/my-tasks",
  );
  await cmd("Page.navigate", { url: `http://127.0.0.1:3020${path}` });
  await until(
    `location.pathname===${JSON.stringify(path.split("?")[0])} && !!document.querySelector('.ops-workspace')`,
  );
}
async function click(label: string, root = "document") {
  await js(
    `(()=>{const el=[...${root}.querySelectorAll('button,a')].find(e=>e.textContent.trim()===${JSON.stringify(label)});if(!el||el.disabled)throw Error('Missing or disabled: '+${JSON.stringify(label)});el.click()})()`,
  );
  await Bun.sleep(180);
}
async function field(label: string, value: string) {
  await js(
    `(()=>{const label=[...document.querySelectorAll('.ops-workspace label')].find(l=>l.firstChild?.textContent.trim().startsWith(${JSON.stringify(label)}));const el=label?.querySelector('input,select,textarea');if(!el)throw Error('Missing field '+${JSON.stringify(label)});const proto=el.tagName==='SELECT'?HTMLSelectElement.prototype:el.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;Object.getOwnPropertyDescriptor(proto,'value').set.call(el,${JSON.stringify(value)});el.dispatchEvent(new Event(el.tagName==='SELECT'?'change':'input',{bubbles:true}))})()`,
  );
  await Bun.sleep(120);
}
async function assert(expression: string, message: string) {
  if (!(await js(expression))) throw new Error(message);
}
let activeRole = "demo-tech";
async function role(id: string) {
  activeRole = id;
  await cmd("Page.navigate", { url: "http://127.0.0.1:3020/operations/login" });
  await until(`!!document.querySelector('#preview-account')`);
  await js(
    `(()=>{const el=document.querySelector('#preview-account');Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'value').set.call(el,${JSON.stringify(id)});el.dispatchEvent(new Event('change',{bubbles:true}))})()`,
  );
  await click("Xem bản trải nghiệm");
  await until(`!!document.querySelector('.operations-app')`);
}
async function responsive(name: string) {
  for (const width of [320, 390, 768, 1440]) {
    await cmd("Emulation.setDeviceMetricsOverride", {
      width,
      height: 900,
      deviceScaleFactor: 1,
      mobile: width < 761,
    });
    await Bun.sleep(150);
    await assert(
      "document.documentElement.scrollWidth<=innerWidth",
      `${name}: viewport overflow ${width}`,
    );
    await assert(
      `(()=>{const e=document.querySelector('.ops-workspace');return !e || e.scrollWidth<=e.clientWidth+1})()`,
      `${name}: workspace overflow ${width}`,
    );
    if (width === 390) await screenshot(`${name.toLowerCase()}-mobile`);
  }
}
async function screenshot(name: string) {
  const r = await cmd("Page.captureScreenshot", { format: "png" });
  await Bun.write(
    `.codex-artifacts/${name}.png`,
    Buffer.from(r.data, "base64"),
  );
}
async function evidence() {
  await js(
    `(()=>{const canvas=document.createElement('canvas');canvas.width=20;canvas.height=20;canvas.getContext('2d').fillRect(0,0,20,20);return new Promise(resolve=>canvas.toBlob(blob=>{const dt=new DataTransfer();dt.items.add(new File([blob],'bang-chung.png',{type:'image/png'}));const input=document.querySelector('.ops-workspace input[type=file]');input.files=dt.files;input.dispatchEvent(new Event('change',{bubbles:true}));resolve(true)}))})()`,
  );
  await until(`document.querySelectorAll('.ws-photo-grid img').length>0`);
}
const key = "vinhomes.frontend-workspace.v1";
let backup: string | null = null;
try {
  await cmd("Runtime.enable");
  await cmd("Page.enable");
  await until(`!!document.querySelector('#preview-account')`);
  backup = await js(`localStorage.getItem(${JSON.stringify(key)})`);
  await js(
    `localStorage.setItem(${JSON.stringify(key)},${JSON.stringify(JSON.stringify(seedWorkspace()))})`,
  );
  await role("demo-admin");
  await until(`!!document.querySelector('.ops-workspace')`);
  await responsive("Accounts");
  await click("+ Cấp tài khoản");
  await field("Họ tên", "Nhân viên thử nghiệm");
  await field("Mã nhân viên", "KT-BROWSER");
  await click("Tạo hồ sơ mẫu");
  await until(
    `document.querySelector('.ops-workspace').innerText.includes('KT-BROWSER')`,
  );
  await click("Duyệt cư dân");
  await assert(
    `JSON.parse(localStorage.getItem('${key}')).accounts.find(a=>a.id==='demo-resident').status==='active'`,
    "Resident approval failed",
  );
  await js(
    `(()=>{const row=[...document.querySelectorAll('.ws-account')].find(e=>e.innerText.includes('KT-BROWSER'));[...row.querySelectorAll('button')].find(e=>e.textContent==='Khóa').click()})()`,
  );
  await until(
    `JSON.parse(localStorage.getItem('${key}')).accounts.find(a=>a.identifier==='KT-BROWSER').status==='suspended'`,
  );
  await js(
    `(()=>{const row=[...document.querySelectorAll('.ws-account')].find(e=>e.innerText.includes('KT-BROWSER'));[...row.querySelectorAll('button')].find(e=>e.textContent==='Xóa').click()})()`,
  );
  await until(`!!document.querySelector('dialog[open]')`);
  await field("Định danh xác nhận", "KT-BROWSER");
  await click("Xóa hồ sơ");
  await until(`!document.querySelector('dialog[open]')`);
  await screenshot("accounts-desktop");
  await role("demo-manager");
  await until(`location.pathname==='/operations/team'`);
  await responsive("Team");
  await field("Tên agent", "An ninh mới");
  await click("Thêm vào nhóm");
  const agent = await js(
    `JSON.parse(localStorage.getItem('${key}')).agents.find(a=>a.name==='An ninh mới').id`,
  );
  await field("@Nhắc agent", agent);
  await field("Ticket liên quan", "DEMO-1003");
  await field("Nội dung", "Tổng hợp tình trạng ticket này");
  await click("Gửi tin nhắn");
  await until(
    `document.querySelector('.ws-transcript').innerText.includes('An ninh mới · mô phỏng')`,
  );
  await screenshot("team-desktop");
  await go("/operations/dispatch?ticket=DEMO-1002");
  await responsive("Dispatch");
  await field("Phân công nhân viên", "demo-tech");
  await click("Xác nhận phân công");
  await role("demo-tech");
  await until(`!!document.querySelector('.work-list')`);
  await assert(
    `!document.querySelector('.operations-sidebar').innerText.includes('Ticket & hiện trường')`,
    "Duplicate navigation still visible",
  );
  await assert(
    `document.querySelectorAll('[data-work-key="ticket:DEMO-1002"]').length===1`,
    "Assigned ticket missing or duplicated in my tasks",
  );
  await assert(
    `!!document.querySelector('[data-work-key^="job:"]')`,
    "Existing work orders disappeared from my tasks",
  );
  await responsive("my-tasks-unified");
  await js(`document.querySelector('[data-work-key^="job:"]').click()`);
  await until(
    `new URLSearchParams(location.search).has('job') && document.querySelector('main').innerText.includes('Việc của tôi')`,
  );
  await assert(
    `!document.querySelector('main').innerText.includes('Không tìm thấy')`,
    "Existing work detail no longer opens",
  );
  await cmd("Page.navigate", {
    url: "http://127.0.0.1:3020/operations/my-tasks?ticket=DEMO-1003",
  });
  await until(
    `document.querySelector('main').innerText.includes('Không tìm thấy công việc')`,
  );
  await cmd("Page.navigate", {
    url: "http://127.0.0.1:3020/operations/dispatch?ticket=DEMO-1002",
  });
  await until(
    `location.pathname==='/operations/my-tasks' && new URLSearchParams(location.search).get('ticket')==='DEMO-1002' && document.querySelector('main').innerText.includes('Vỡ đường ống')`,
  );
  await go("/operations/dispatch?ticket=DEMO-1002");
  await assert(
    `!document.querySelector('.ops-workspace').innerText.includes('DEMO-1003')`,
    "Unassigned ticket leaked",
  );
  await click("Đã đến hiện trường");
  await click("Đề nghị cư dân đồng ý sửa chữa");
  await click("Mô phỏng cư dân đồng ý");
  await click("Đề nghị BQL duyệt khóa nước");
  await assert(
    `![...document.querySelectorAll('button')].some(e=>e.textContent==='BQL duyệt khóa nước')`,
    "Staff sees manager approval",
  );
  await role("demo-manager");
  await go("/operations/dispatch?ticket=DEMO-1002");
  await click("BQL duyệt khóa nước");
  await click("Tạo thông báo cắt nước mẫu");
  await role("demo-tech");
  await go("/operations/dispatch?ticket=DEMO-1002");
  await click("Xác nhận đã khóa van");
  await click("Bắt đầu xử lý");
  await evidence();
  await click("Mở nước và thông báo khôi phục");
  await click("Gửi kết quả cho cư dân");
  await click("Mô phỏng cư dân xác nhận hoàn tất");
  await until(
    `JSON.parse(localStorage.getItem('${key}')).cases.find(c=>c.id==='DEMO-1002').stage==='completed'`,
  );
  await go("/operations/my-tasks");
  await assert(
    `!document.querySelector('[data-work-key="ticket:DEMO-1002"]')`,
    "Completed ticket remains in active list",
  );
  await cmd("Page.navigate", {
    url: "http://127.0.0.1:3020/operations/completed-tasks",
  });
  await until(
    `location.pathname==='/operations/my-tasks' && location.search.includes('view=history') && !!document.querySelector('[data-work-key="ticket:DEMO-1002"]')`,
  );
  await js(
    `document.querySelector('[data-work-key="ticket:DEMO-1002"]').click()`,
  );
  await until(
    `new URLSearchParams(location.search).get('ticket')==='DEMO-1002'`,
  );
  await cmd("Runtime.evaluate", { expression: "history.back()" });
  await until(
    `location.search==='?view=history' && !!document.querySelector('.work-list')`,
  );
  await role("demo-manager");
  await go("/operations/kanban");
  await responsive("assignment-unified");
  await assert(
    `!!document.querySelector('[data-work-key^="task:"]')`,
    "Existing tasks disappeared from management",
  );
  await click("Xem theo tiến độ");
  await assert(
    `!!document.querySelector('.ws-board [data-work-key="ticket:DEMO-1003"]')`,
    "Unified board does not include new ticket",
  );
  await go("/operations/dispatch?ticket=DEMO-1003");
  await field("Phân công nhân viên", "demo-security");
  await click("Xác nhận phân công");
  await role("demo-security");
  await go("/operations/dispatch?ticket=DEMO-1003");
  await click("Đã đến hiện trường");
  await js(`document.querySelector('.ops-workspace details').open=true`);
  await field("Lý do", "Có dấu hiệu gây nguy hiểm");
  await click("Nâng lên P0, cảnh báo người trực");
  await click("Báo trưởng ca / người tiếp theo");
  await click("Người trực xác nhận cảnh báo");
  await click("Bắt đầu xử lý");
  await evidence();
  await click("Báo đã kiểm soát sự cố");
  await role("demo-manager");
  await go("/operations/dispatch?ticket=DEMO-1003");
  await click("BQL xác nhận hoàn tất");
  await go("/operations/reports");
  await field("Loại báo cáo", "revenue");
  await click("Tạo báo cáo mẫu");
  await click("Mô phỏng lỗi");
  await click("Thử tạo lại bản mẫu");
  await responsive("Reports");
  await assert(
    `document.querySelector('.ops-workspace').innerText.includes('530.000')`,
    "Completed water revenue missing",
  );
  await js(
    `window.__docxBlob=null;window.__originalCreateObjectURL=URL.createObjectURL;URL.createObjectURL=(blob)=>{window.__docxBlob=blob;return window.__originalCreateObjectURL(blob)}`,
  );
  await click("Tải DOCX mẫu");
  await assert(
    `window.__docxBlob?.type==='application/vnd.openxmlformats-officedocument.wordprocessingml.document'`,
    "Missing DOCX download",
  );
  const bytes: number[] = await js(
    `window.__docxBlob.arrayBuffer().then(b=>Array.from(new Uint8Array(b)))`,
  );
  await Bun.write(
    ".codex-artifacts/workspace-report.docx",
    new Uint8Array(bytes),
  );
  await screenshot("reports-desktop");
  await role("demo-manager2");
  await until(
    `document.querySelector('.ops-workspace')?.innerText.includes('Điều phối S2.02')`,
  );
  await assert(
    `!document.querySelector('.ops-workspace').innerText.includes('DEMO-1003')`,
    "Other building ticket leaked",
  );
  await role("demo-tech");
  await cmd("Page.navigate", {
    url: "http://127.0.0.1:3020/operations/accounts",
  });
  await until(
    `location.pathname==='/operations/my-tasks' && !!document.querySelector('.operations-app')`,
  );
  if (errors.length) throw new Error(errors.join("\n"));
  console.log(
    "PASS: mobile/desktop, admin provisioning/approval/suspension/deletion, scoped BQL group/mentions, staff isolation, major water, urgent security, report failure/retry and DOCX download, direct-route guard.",
  );
} finally {
  try {
    await js(
      backup === null
        ? `localStorage.removeItem('${key}')`
        : `localStorage.setItem('${key}',${JSON.stringify(backup)})`,
    );
  } finally {
    socket.close();
    await fetch(`http://127.0.0.1:9333/json/close/${target.id}`);
  }
}
