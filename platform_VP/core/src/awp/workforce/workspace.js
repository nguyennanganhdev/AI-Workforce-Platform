"use strict";
const $ = (id) => document.getElementById(id);
const W = "/workforce/v1/admin",
  P = "/platform/v1";
let session = null,
  navigation = 0,
  refreshTimer = null;
const labels = {
  leader: "Supervisor",
  specialist: "Chuyên viên",
  worker: "Chuyên viên",
  draft: "Bản nháp",
  published: "Đã công bố",
  retired: "Ngừng sử dụng",
  accepted: "Đã tiếp nhận",
  active: "Đang xử lý",
  closed: "Đã kết thúc",
  awaiting_user: "Cần thông tin",
  awaiting_approval: "Chờ đồng ý",
  awaiting_confirmation: "Chờ xác nhận",
  waiting_external_event: "Chờ đối tác",
  needs_attention: "Cần can thiệp",
  blocked_authorization: "Quyền bị chặn",
  blocked_route_changed: "Route đã thay đổi",
  pending: "Chờ xác nhận",
  queued: "Trong hàng đợi",
  leased: "Đang chạy",
  done: "Hoàn tất",
  failed: "Thất bại",
  unknown: "Chưa rõ kết quả",
  confirmed: "Đã xác nhận",
  completed: "Hoàn tất",
  revoked: "Đã thu hồi",
  cancelled: "Đã dừng",
  evidence: "Bằng chứng",
  fact: "Sự kiện",
  question: "Câu hỏi",
  answer: "Trả lời",
  challenge: "Phản biện",
  gap: "Chưa biết",
  decision: "Quyết định",
  report: "Báo cáo",
  final: "Kết quả",
  note: "Ghi chú",
  cheap: "Tiết kiệm",
  standard: "Cân bằng",
  strong: "Chuyên sâu",
};
const text = (value) => (value == null ? "—" : String(value));
const money = (value) =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 4,
  }).format(value || 0);
const date = (value) =>
  value ? new Date(value * 1000).toLocaleString("vi-VN") : "—";
function el(tag, content, cls) {
  const n = document.createElement(tag);
  if (content != null) n.textContent = text(content);
  if (cls) n.className = cls;
  return n;
}
function box(cls, ...children) {
  const n = el("div", null, cls);
  n.append(...children.filter(Boolean));
  return n;
}
function link(label, hash, cls) {
  const n = el("a", label, cls);
  n.href = "#" + hash;
  return n;
}
function btn(label, action, cls = "", write = false) {
  const n = el("button", label, cls);
  n.type = "button";
  n.disabled = write && session?.role !== "admin";
  n.onclick = async () => {
    try {
      await action();
    } catch (e) {
      toast(e.message, true);
    }
  };
  return n;
}
function badge(value) {
  return el("span", labels[value] || value, "badge " + value);
}
function toast(message, error = false) {
  $("toast").textContent = message;
  $("toast").hidden = false;
  $("toast").style.background = error ? "#8b4537" : "";
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => ($("toast").hidden = true), 6000);
}
async function api(path, body, method) {
  const r = await fetch(path, {
    credentials: "same-origin",
    method: method || (body === undefined ? "GET" : "POST"),
    headers: {
      "Content-Type": "application/json",
      ...(session ? { "X-CSRF-Token": session.csrf } : {}),
    },
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
  });
  const data = await r.json();
  if (!r.ok) {
    const detail =
      data.error?.message ||
      data.detail ||
      data.error?.code ||
      `HTTP ${r.status}`;
    const e = Error(
      typeof detail === "string" ? detail : JSON.stringify(detail),
    );
    e.status = r.status;
    throw e;
  }
  return data;
}
function head(title, description, action, eyebrow = "WORKSPACE") {
  return box(
    "page-head",
    box(
      "",
      el("p", eyebrow, "eyebrow"),
      el("h1", title),
      el("p", description, "muted"),
    ),
    action,
  );
}
function panel(title, ...content) {
  const n = el("section", null, "panel");
  n.append(el("h2", title), ...content.filter(Boolean));
  return n;
}
function empty(title, description, action) {
  return box("empty", el("h3", title), el("p", description), action);
}
function technical(value, label = "Dữ liệu kỹ thuật") {
  const n = el("details", null, "technical");
  n.append(el("summary", label), el("pre", JSON.stringify(value, null, 2)));
  return n;
}
function definition(entries) {
  const n = el("dl", null, "definition");
  for (const [k, v] of entries)
    n.append(el("dt", k), v instanceof Node ? box("", v) : el("dd", v));
  return n;
}
function table(columns, rows) {
  const t = el("table"),
    h = el("thead"),
    tr = el("tr");
  columns.forEach((c) => tr.append(el("th", c)));
  h.append(tr);
  t.append(h);
  const b = el("tbody");
  for (const values of rows) {
    const row = el("tr");
    for (const value of values) {
      const td = el("td");
      td.append(
        value instanceof Node ? value : document.createTextNode(text(value)),
      );
      row.append(td);
    }
    b.append(row);
  }
  t.append(b);
  return box("table-wrap", t);
}
function stats(entries) {
  return box(
    "stats",
    ...entries.map(([label, value]) =>
      box("stat", el("strong", value), el("span", label)),
    ),
  );
}
function showDialog(title, body) {
  $("editor-title").textContent = title;
  $("editor-body").replaceChildren(body);
  if (!$("editor").open) $("editor").showModal();
}
function field(spec) {
  const label = el("label", spec.label, spec.full ? "full" : "");
  let input;
  if (spec.type === "checks") {
    input = box("selection-list");
    input.dataset.checks = spec.key;
    for (const option of spec.options || []) {
      const l = el("label", null, "check-label"),
        c = el("input");
      c.type = "checkbox";
      c.value = option.value;
      c.checked = (spec.value || []).includes(option.value);
      l.append(c, document.createTextNode(option.label));
      input.append(l);
    }
    if (!input.children.length)
      input.append(el("p", spec.empty || "Chưa có mục khả dụng."));
  } else {
    input = el(
      spec.type === "textarea"
        ? "textarea"
        : spec.type === "select"
          ? "select"
          : "input",
    );
    input.name = spec.key;
    if (spec.type === "select")
      for (const o of spec.options || []) {
        const opt = el("option", o.label);
        opt.value = o.value;
        input.append(opt);
      }
    else if (spec.type !== "textarea") input.type = spec.type || "text";
    input.value = spec.value ?? "";
    input.required = !!spec.required;
    if (spec.min !== undefined) input.min = spec.min;
    if (spec.max !== undefined) input.max = spec.max;
    if (spec.step) input.step = spec.step;
    if (spec.pattern) input.pattern = spec.pattern;
    if (spec.placeholder) input.placeholder = spec.placeholder;
    if (spec.readonly) input.readOnly = true;
  }
  label.append(input);
  if (spec.help) label.append(el("small", spec.help));
  return label;
}
function form(
  specs,
  submit,
  label = "Lưu",
  description,
  writable = session?.role === "admin",
) {
  const f = el("form"),
    grid = box("field-grid");
  if (description) f.append(el("p", description, "muted"));
  specs.forEach((s) => grid.append(field(s)));
  const error = el("p", null, "error");
  error.setAttribute("role", "alert");
  const save = el("button", label, "primary");
  save.type = "submit";
  save.disabled = !writable;
  f.append(
    grid,
    error,
    box(
      "form-actions",
      btn("Hủy", () => $("editor").close()),
      save,
    ),
  );
  f.onsubmit = async (e) => {
    e.preventDefault();
    const values = Object.fromEntries(new FormData(f));
    for (const s of specs) {
      if (s.type === "checks")
        values[s.key] = [
          ...f
            .querySelector(`[data-checks="${s.key}"]`)
            .querySelectorAll("input:checked"),
        ].map((c) => c.value);
      if (s.type === "number") values[s.key] = Number(values[s.key]);
    }
    error.textContent = "";
    save.disabled = true;
    try {
      await submit(values);
      $("editor").close();
      toast("Đã lưu thay đổi.");
      await render();
    } catch (e) {
      error.textContent = e.message;
    } finally {
      save.disabled = !writable;
    }
  };
  return f;
}
const lines = (value) =>
  (value || "")
    .split("\n")
    .map((x) => x.trim())
    .filter(Boolean);
const listField = (key, label, value = [], help = "Mỗi dòng một mục") => ({
  key,
  label,
  type: "textarea",
  value: value.join("\n"),
  help,
  full: true,
});
async function profiles() {
  return (await api(P + "/profiles")).profiles;
}
function latest(records) {
  const map = new Map();
  for (const r of records)
    if (!map.has(r.key) || map.get(r.key).version < r.version)
      map.set(r.key, r);
  return [...map.values()];
}
async function overview() {
  const [flows, agents, models, setup] = await Promise.all([
    api(W + "/workspace/sessions"),
    profiles(),
    api(P + "/models"),
    api(W + "/workspace/setup"),
  ]);
  const published = agents.filter((x) => x.status === "published"),
    readyModels = models.models.filter((x) => x.available && x.priced);
  const root = box(
    "",
    head(
      "Không gian làm việc",
      "Quản lý đội ngũ agent và theo dõi công việc từ khi tiếp nhận đến khi có kết quả.",
      btn("＋ Giao việc", newWork, "primary", true),
    ),
  );
  root.append(
    stats([
      [
        "Công việc đang mở",
        flows.items.filter((x) => x.state !== "closed").length,
      ],
      [
        "Cần can thiệp",
        flows.items.filter((x) => x.state === "needs_attention").length,
      ],
      ["Agent đã công bố", published.length],
      ["Model sẵn sàng", readyModels.length],
    ]),
  );
  const steps = [
    [
      "Kết nối model",
      "Model cần credential và giá để kiểm soát ngân sách.",
      readyModels.length > 0,
      "models",
      "Xem model",
    ],
    [
      "Xây dựng đội ngũ",
      "Khai báo supervisor và các chuyên viên có thể được mời.",
      published.some((x) => x.profile.role === "leader"),
      "agents",
      "Quản lý agent",
    ],
    [
      "Chọn supervisor mặc định",
      "Thiết lập một lần cho công việc nội bộ.",
      setup.configured,
      "settings",
      "Thiết lập",
    ],
  ];
  const guide = panel(
    "Chuẩn bị workspace",
    ...steps.map(([title, desc, done, path, action], i) =>
      box(
        "setup-step",
        el("span", done ? "✓" : i + 1, "step-number"),
        box("", el("h3", title), el("p", desc)),
        link(done ? "Đã thiết lập" : action, path),
      ),
    ),
  );
  const info = panel(
    "Cách đội ngũ làm việc",
    el(
      "p",
      "Bạn gửi mục tiêu và thông tin có sẵn. Supervisor xác định phần việc, mời chuyên viên phù hợp và tổng hợp kết quả.",
    ),
    definition([
      [
        "Context chung",
        "Case file lưu bằng chứng, câu hỏi, phản biện và kết quả.",
      ],
      [
        "Memory riêng",
        "Ghi chú theo từng agent và workflow; luôn cần kiểm chứng.",
      ],
      [
        "Khi chưa đủ dữ liệu",
        "Agent ghi nhận điều chưa biết và hỏi thêm hoặc yêu cầu người can thiệp.",
      ],
    ]),
  );
  root.append(box("grid-2", guide, info));
  root.append(panel("Công việc gần đây", flowTable(flows.items.slice(0, 8))));
  return root;
}
function flowTable(rows) {
  return rows.length
    ? table(
        ["Công việc", "Nguồn", "Trạng thái", "Cập nhật"],
        rows.map((x) => [
          box(
            "",
            link(x.title, "work/" + x.id, "work-title"),
            el("p", `Supervisor · ${x.leader_profile}`),
          ),
          x.source === "internal" ? "Workspace" : "Đối tác · " + x.client_id,
          badge(x.state),
          date(x.updated),
        ]),
      )
    : empty(
        "Chưa có công việc",
        "Giao yêu cầu đầu tiên sau khi cấu hình supervisor. Đội ngũ tham gia do supervisor quyết định.",
        btn("Giao việc", newWork, "primary", true),
      );
}
async function newWork() {
  const setup = await api(W + "/workspace/setup");
  if (!setup.configured) {
    location.hash = "settings";
    toast("Chọn supervisor mặc định trước khi giao việc.");
    return;
  }
  const request_id = crypto.randomUUID();
  showDialog(
    "Giao việc cho supervisor",
    form(
      [
        {
          key: "text",
          label: "Bạn cần giải quyết việc gì?",
          type: "textarea",
          full: true,
          required: true,
          help: "Nêu mục tiêu, thông tin đã biết và kết quả mong muốn. Supervisor tự chọn chuyên viên khi cần.",
        },
      ],
      async (v) => {
        const r = await api(W + "/workspace/sessions", { ...v, request_id });
        location.hash = "work/" + r.workflow_id;
      },
      "Bắt đầu xử lý",
      "Yêu cầu sẽ vào hàng đợi Workforce. Model và ngân sách được kiểm tra trước khi tiếp nhận.",
    ),
  );
}
async function workList() {
  const { items } = await api(W + "/workspace/sessions");
  const root = box(
    "",
    head(
      "Công việc",
      "Theo dõi các yêu cầu nội bộ và công việc từ đối tác trên cùng một workspace.",
      btn("＋ Giao việc", newWork, "primary", true),
    ),
  );
  const search = el("input"),
    filter = el("select");
  search.placeholder = "Tìm theo yêu cầu hoặc supervisor";
  search.setAttribute("aria-label", "Tìm công việc");
  for (const [v, t] of [
    ["", "Tất cả trạng thái"],
    ["active", "Đang xử lý"],
    ["awaiting_user", "Cần thông tin"],
    ["awaiting_approval", "Chờ đồng ý"],
    ["needs_attention", "Cần can thiệp"],
    ["closed", "Đã kết thúc"],
  ]) {
    const o = el("option", t);
    o.value = v;
    filter.append(o);
  }
  filter.setAttribute("aria-label", "Trạng thái công việc");
  const results = box("");
  const update = () =>
    results.replaceChildren(
      flowTable(
        items.filter(
          (x) =>
            (!filter.value || x.state === filter.value) &&
            `${x.title} ${x.leader_profile}`
              .toLowerCase()
              .includes(search.value.toLowerCase()),
        ),
      ),
    );
  search.oninput = update;
  filter.onchange = update;
  update();
  root.append(
    box("toolbar", search, filter),
    panel("Danh sách công việc", results),
    el("p", "Hiển thị tối đa 200 công việc cập nhật gần nhất.", "hint"),
  );
  return root;
}
async function editProfile(rec) {
  const [all, catalog] = await Promise.all([profiles(), api(P + "/models")]);
  const p = rec?.profile || {
    key: "",
    name: "",
    role: "specialist",
    mission: "",
    handles: [],
    refuses: [],
    instructions: "",
    tools_allow: [],
    team: [],
    knowledge: { knowledge_base_ids: [], mcp_servers: [], skills: [] },
    memory: { enabled: false, scope: "private" },
    model_tier: "standard",
    model_id: null,
    max_iters: 12,
    invite_description: "",
    escalate_when: [],
  };
  const specs = [
    {
      key: "key",
      label: "Mã định danh",
      value: p.key,
      required: true,
      pattern: "[a-z][a-z0-9_]{1,40}",
      readonly: !!rec,
      help: "Chữ thường, số và dấu gạch dưới. Giữ nguyên qua các phiên bản.",
    },
    { key: "name", label: "Tên agent", value: p.name, required: true },
    {
      key: "role",
      label: "Vai trò",
      type: "select",
      value: p.role,
      options: [
        { value: "specialist", label: "Chuyên viên" },
        { value: "leader", label: "Supervisor" },
      ],
    },
    {
      key: "model_id",
      label: "Model",
      type: "select",
      value: p.model_id || "",
      options: [
        { value: "", label: "Tự chọn theo tầng" },
        ...catalog.models.map((x) => ({
          value: x.id,
          label: `${x.id} · ${x.available ? "Có credential" : "Thiếu credential"}${x.priced ? "" : " · Chưa có giá"}`,
        })),
      ],
    },
    {
      key: "mission",
      label: "Tôi là ai, chịu trách nhiệm gì?",
      type: "textarea",
      full: true,
      value: p.mission,
      required: true,
    },
    {
      key: "instructions",
      label: "Hướng dẫn làm việc và context cố định",
      type: "textarea",
      full: true,
      value: p.instructions,
    },
    listField("handles", "Phạm vi xử lý", p.handles),
    listField("refuses", "Việc không được thực hiện", p.refuses),
    {
      key: "invite_description",
      label: "Khi nào supervisor nên mời agent này?",
      type: "textarea",
      full: true,
      value: p.invite_description,
    },
    {
      key: "team",
      label: "Chuyên viên supervisor được phép mời",
      type: "checks",
      full: true,
      value: p.team,
      options: latest(all)
        .filter((x) => x.key !== p.key && x.profile.role === "specialist")
        .map((x) => ({ value: x.key, label: `${x.profile.name} · ${x.key}` })),
      help: "Đây là quyền mời theo hồ sơ. Supervisor tự quyết định agent nào thực sự tham gia từng công việc.",
    },
    listField(
      "tools_allow",
      "Quyền công cụ",
      p.tools_allow,
      "Tên tool hoặc mẫu quyền, ví dụ search_knowledge. Chỉ cấp quyền cần thiết.",
    ),
    listField(
      "knowledge_base_ids",
      "Kho tri thức được phép sử dụng",
      p.knowledge.knowledge_base_ids,
    ),
    listField("mcp_servers", "Kết nối MCP theo hồ sơ", p.knowledge.mcp_servers),
    listField("skills", "Kỹ năng theo hồ sơ", p.knowledge.skills),
    {
      key: "memory_enabled",
      label: "Memory riêng trong workflow",
      type: "select",
      value: p.memory.enabled ? "true" : "false",
      options: [
        { value: "false", label: "Tắt" },
        { value: "true", label: "Bật ghi chú riêng" },
      ],
      help: "Memory là ghi chú chưa kiểm chứng. Phạm vi hiện hỗ trợ: agent + workflow.",
    },
    {
      key: "model_tier",
      label: "Tầng model khi tự chọn",
      type: "select",
      value: p.model_tier,
      options: ["cheap", "standard", "strong"].map((v) => ({
        value: v,
        label: labels[v],
      })),
    },
    {
      key: "max_iters",
      label: "Số vòng suy luận tối đa",
      type: "number",
      min: 2,
      max: 40,
      value: p.max_iters,
    },
    listField(
      "escalate_when",
      "Khi nào phải hỏi người quản lý?",
      p.escalate_when,
    ),
  ];
  const f = form(
    specs,
    async (v) => {
      const value = {
        ...p,
        ...v,
        model_id: v.model_id || null,
        memory: { enabled: v.memory_enabled === "true", scope: "private" },
        knowledge: {
          knowledge_base_ids: lines(v.knowledge_base_ids),
          mcp_servers: lines(v.mcp_servers),
          skills: lines(v.skills),
        },
      };
      for (const k of ["handles", "refuses", "tools_allow", "escalate_when"])
        value[k] = lines(v[k]);
      for (const k of [
        "knowledge_base_ids",
        "mcp_servers",
        "skills",
        "memory_enabled",
      ])
        delete value[k];
      if (value.role === "specialist") value.team = [];
      const draft = rec?.status === "draft";
      await api(
        draft
          ? `${P}/profiles/${rec.key}/versions/${rec.version}`
          : P + "/profiles",
        value,
        draft ? "PUT" : "POST",
      );
    },
    rec?.status === "draft" ? "Lưu bản nháp" : "Tạo bản nháp",
    "Bản nháp chưa được runtime sử dụng. Công bố sau khi kiểm tra; công việc đang chạy giữ phiên bản đã chụp.",
  );
  const role = f.elements.role,
    team = f.querySelector('[data-checks="team"]').closest("label");
  const toggle = () => (team.hidden = role.value !== "leader");
  role.onchange = toggle;
  toggle();
  showDialog(rec ? "Chỉnh hồ sơ agent" : "Tạo agent", f);
}
async function agentList() {
  const records = await profiles(),
    items = latest(records);
  const root = box(
    "",
    head(
      "Đội ngũ agent",
      "Mỗi agent có danh tính, nhiệm vụ, context, tri thức và quyền hạn riêng.",
      btn("＋ Tạo agent", () => editProfile(), "primary", true),
    ),
  );
  if (!items.length) {
    root.append(
      empty(
        "Xây dựng đội ngũ đầu tiên",
        "Tạo các chuyên viên theo năng lực, sau đó cấu hình supervisor và quyền mời chuyên viên.",
        btn("Tạo agent", () => editProfile(), "primary", true),
      ),
    );
    return root;
  }
  const grid = box("agent-grid");
  for (const r of items) {
    const p = r.profile;
    grid.append(
      box(
        "agent-card",
        box(
          "inline",
          el("span", p.name.slice(0, 2).toUpperCase(), "avatar"),
          box("", el("h2", p.name), el("span", labels[p.role], "hint")),
        ),
        el("p", p.mission),
        box(
          "tags",
          badge(r.status),
          el("span", "v" + r.version, "badge"),
          el("span", p.model_id || labels[p.model_tier], "badge"),
        ),
        el(
          "p",
          `${p.knowledge.knowledge_base_ids.length} kho tri thức · Memory ${p.memory.enabled ? "bật" : "tắt"}`,
        ),
        box("actions", link("Mở hồ sơ →", "agent/" + r.key)),
      ),
    );
  }
  root.append(grid);
  return root;
}
async function agentDetail(key, version) {
  const records = (await profiles()).filter((x) => x.key === key);
  if (!records.length) throw Error("Không tìm thấy agent.");
  const r = version
    ? records.find((x) => x.version === Number(version))
    : records.at(-1);
  if (!r) throw Error("Không tìm thấy phiên bản agent.");
  const p = r.profile;
  const root = box(
    "",
    link("← Đội ngũ agent", "agents", "back-link"),
    head(
      p.name,
      p.mission,
      box(
        "actions",
        btn(
          r.status === "draft" ? "Sửa bản nháp" : "Tạo phiên bản mới",
          () => editProfile(r),
          "",
          true,
        ),
        r.status === "draft"
          ? btn(
              "Công bố",
              async () => {
                await api(
                  `${P}/profiles/${key}/versions/${r.version}/publish`,
                  {},
                );
                toast("Đã công bố agent.");
                await render();
              },
              "primary",
              true,
            )
          : null,
      ),
    ),
  );
  root.append(
    box(
      "version-list",
      ...records.map((x) =>
        box(
          "tags",
          link(`v${x.version}`, `agent/${key}/${x.version}`, "badge"),
          badge(x.status),
        ),
      ),
    ),
  );
  const main = box(
    "",
    panel(
      "Danh tính & phạm vi",
      definition([
        ["Vai trò", labels[p.role]],
        ["Nhiệm vụ", p.mission],
        ["Phạm vi xử lý", p.handles.join("\n") || "Chưa khai báo"],
        ["Giới hạn", p.refuses.join("\n") || "Chưa khai báo"],
        [
          "Khi nào cần can thiệp",
          p.escalate_when.join("\n") || "Chưa khai báo",
        ],
      ]),
      p.instructions ? el("p", p.instructions, "prose") : null,
    ),
    panel(
      "Tri thức & memory",
      definition([
        [
          "Kho tri thức",
          p.knowledge.knowledge_base_ids.join(", ") || "Chưa gắn kho",
        ],
        ["Memory riêng", p.memory.enabled ? "Bật · agent + workflow" : "Tắt"],
        [
          "Nguồn kiểm chứng",
          "Knowledge được duyệt là nguồn tra cứu; memory vẫn cần đối chiếu bằng chứng.",
        ],
      ]),
      link("Mở kho tri thức →", "knowledge"),
    ),
    panel(
      "Phối hợp & quyền công cụ",
      definition([
        ["Được phép mời", p.team.join(", ") || "Không có"],
        ["Khi nào được mời", p.invite_description || "Chưa khai báo"],
        [
          "Công cụ bổ sung",
          p.tools_allow.join(", ") || "Chỉ bộ công cụ mặc định theo vai",
        ],
        ["MCP", p.knowledge.mcp_servers.join(", ") || "Chưa gắn"],
        ["Kỹ năng khai báo", p.knowledge.skills.join(", ") || "Chưa khai báo"],
      ]),
    ),
  );
  const side = panel(
    "Cấu hình thực thi",
    definition([
      ["Mã agent", p.key],
      ["Phiên bản hiện xem", `v${r.version} · ${labels[r.status]}`],
      ["Model", p.model_id || "Tự chọn · " + labels[p.model_tier]],
      ["Vòng suy luận tối đa", p.max_iters],
      ["Ngày tạo", date(r.created_at)],
    ]),
    btn(
      "Ngừng sử dụng",
      async () => {
        if (confirm("Ngừng công bố agent " + p.name + "?")) {
          await api(`${P}/profiles/${key}/retire`, {});
          await render();
        }
      },
      "danger",
      true,
    ),
    technical(records, "Lịch sử hồ sơ"),
  );
  root.append(box("profile-layout", main, side));
  return root;
}
function itemCard(x) {
  const d = x.data || {},
    body =
      d.text ||
      d.answer ||
      d.summary ||
      d.description ||
      (d.type === "final_attempt"
        ? "Kết luận bị chặn: " + d.problems.join("; ")
        : null) ||
      JSON.stringify(d, null, 2);
  return box(
    "message",
    box(
      "message-header",
      el("strong", x.author),
      badge(x.kind),
      el("span", x.ref, "reference"),
    ),
    el("div", body, "message-body"),
    x.addressee ? el("p", "Gửi đến · " + x.addressee, "message-footer") : null,
    d.cites?.length
      ? el("div", "Nguồn: " + d.cites.join(", "), "message-footer")
      : null,
    technical(d, "Xem dữ liệu và tham chiếu"),
  );
}
async function workDetail(id) {
  let data = await api(W + "/workspace/sessions/" + id),
    tab = "conversation";
  const wf = data.workflow,
    origin = data.requests.find((x) => x.command === "start_workflow");
  const stateBadge = badge(wf.state);
  const closeActions = box("actions");
  const root = box(
    "",
    link("← Công việc", "work", "back-link"),
    head(
      (origin?.body.message.text || "Công việc").slice(0, 160),
      "Supervisor tổ chức đội; mọi trao đổi có cấu trúc và bằng chứng được lưu trong hồ sơ chung.",
      box(
        "actions",
        stateBadge,
        closeActions,
        btn("Cập nhật", async () => {
          data = await api(W + "/workspace/sessions/" + id);
          paint();
        }),
      ),
    ),
  );
  const tabs = box("tabs"),
    body = box(""),
    aside = el("aside", null, "detail-aside");
  const layout = box("detail-layout", box("", tabs, body), aside);
  root.append(layout);
  const names = [
    ["conversation", "Trao đổi"],
    ["room", "Phối hợp agent"],
    ["evidence", "Bằng chứng"],
    ["memory", "Memory riêng"],
    ["operations", "Thực thi"],
  ];
  for (const [k, label] of names) {
    const b = btn(
      label,
      () => {
        tab = k;
        paint();
      },
      "tab",
    );
    b.dataset.tab = k;
    tabs.append(b);
  }
  let draft = "",
    messageKey = crypto.randomUUID();
  function paint() {
    closeActions.replaceChildren();
    if (
      data.can_manage &&
      data.workflow.state !== "closed" &&
      session.role === "admin"
    ) {
      const close = async (action) => {
        if (
          !confirm(
            action === "stop"
              ? "Dừng theo dõi công việc này? Các lượt xử lý mới sẽ bị chặn."
              : "Xác nhận kết quả và kết thúc công việc?",
          )
        )
          return;
        await api(W + "/workspace/sessions/" + id + "/close", {
          request_id: crypto.randomUUID(),
          expected_revision: data.workflow.revision,
          action,
        });
        data = await api(W + "/workspace/sessions/" + id);
        paint();
      };
      if (data.workflow.state === "awaiting_confirmation")
        closeActions.append(
          btn("Xác nhận kết quả", () => close("confirm"), "primary"),
        );
      closeActions.append(btn("Dừng theo dõi", () => close("stop"), "danger"));
    }
    stateBadge.textContent = labels[data.workflow.state] || data.workflow.state;
    stateBadge.className = "badge " + data.workflow.state;
    const active = document.activeElement;
    if (active?.name === "reply-text") draft = active.value;
    for (const b of tabs.children)
      b.classList.toggle("active", b.dataset.tab === tab);
    body.replaceChildren();
    aside.replaceChildren();
    const members = new Map();
    for (const m of data.team) {
      const key = m.agent_id;
      members.set(key, { ...m, epochs: (members.get(key)?.epochs || 0) + 1 });
    }
    const roster = box("team-list");
    for (const m of members.values())
      roster.append(
        box(
          "member",
          box(
            "inline",
            el("span", m.agent_name.slice(0, 2), "avatar"),
            box(
              "",
              el("strong", m.agent_name),
              el("small", `${labels[m.role]} · ${m.epochs} phiên thực thi`),
            ),
          ),
        ),
      );
    aside.append(
      panel(
        "Đội đã tham gia",
        members.size
          ? roster
          : el(
              "p",
              "Supervisor chưa bắt đầu thực thi. Chuyên viên xuất hiện khi được mời.",
              "hint",
            ),
      ),
      panel(
        "Thông tin công việc",
        definition([
          ["Trạng thái", labels[data.workflow.state] || data.workflow.state],
          ["Nguồn", data.source === "internal" ? "Workspace" : "Đối tác"],
          ["Supervisor", data.workflow.snapshot.leader_profile],
          ["Ngân sách", money(data.workflow.snapshot.budget_micros / 1e6)],
          ["Chi phí đã ghi", money(data.cost?.totals.cost_usd)],
          ["Lượt gọi model", data.cost?.totals.calls || 0],
          ["Cập nhật", date(data.workflow.updated)],
        ]),
        technical(
          {
            workflow_id: id,
            profiles: data.workflow.snapshot.profiles,
            models: data.workflow.snapshot.models,
          },
          "Phiên bản đã chụp",
        ),
      ),
    );
    if (tab === "conversation") {
      const timeline = box("timeline"),
        entries = [];
      for (const req of data.requests.filter(
        (x) => x.command !== "system_continuation",
      ))
        if (req.body.message)
          entries.push([
            req.created,
            box(
              "message user",
              box(
                "message-header",
                el(
                  "strong",
                  data.source === "internal"
                    ? "Người giao việc"
                    : "Thông tin từ đối tác",
                ),
                el("span", date(req.created), "hint"),
              ),
              el("div", req.body.message.text, "message-body"),
              badge(req.status),
              req.error
                ? el("p", req.error.message || req.error.code, "error")
                : null,
            ),
          ]);
      for (const event of data.events)
        if (["assistant.message", "assistant.final"].includes(event.event_type))
          entries.push([
            event.recorded,
            box(
              "message",
              box(
                "message-header",
                el("strong", "Supervisor"),
                el("span", date(event.recorded), "hint"),
              ),
              el(
                "div",
                event.payload.text ||
                  event.payload.answer ||
                  event.payload.message ||
                  JSON.stringify(event.payload),
                "message-body",
              ),
            ),
          ]);
      // Final answers may be recorded as case items rather than a separate public event.
      for (const item of data.items.filter((x) => x.kind === "final"))
        if (!data.events.some((x) => x.payload.text === item.data.answer))
          entries.push([item.created, itemCard(item)]);
      entries.sort((a, b) => a[0] - b[0]);
      timeline.append(...entries.map((x) => x[1]));
      body.append(
        timeline.children.length
          ? timeline
          : empty(
              "Đã tiếp nhận yêu cầu",
              "Các tin nhắn được kiểm chứng sẽ xuất hiện khi supervisor bắt đầu xử lý.",
            ),
      );
      if (data.can_reply && session.role === "admin") {
        const f = el("form", null, "composer"),
          input = el("textarea");
        input.name = "reply-text";
        input.value = draft;
        input.required = true;
        input.placeholder = "Bổ sung thông tin cho supervisor…";
        input.setAttribute("aria-label", "Thông tin bổ sung");
        input.oninput = () => (draft = input.value);
        const error = el("p", null, "error"),
          send = el("button", "Gửi thông tin →", "primary");
        send.type = "submit";
        f.append(
          input,
          error,
          box(
            "actions",
            el(
              "small",
              "Thông tin được gửi vào cùng workflow; supervisor tiếp tục điều phối.",
            ),
            send,
          ),
        );
        f.onsubmit = async (e) => {
          e.preventDefault();
          send.disabled = true;
          try {
            await api(W + `/workspace/sessions/${id}/messages`, {
              request_id: messageKey,
              text: input.value,
            });
            draft = "";
            messageKey = crypto.randomUUID();
            data = await api(W + "/workspace/sessions/" + id);
            paint();
          } catch (e) {
            error.textContent = e.message;
            send.disabled = false;
          }
        };
        body.append(f);
      } else
        body.append(
          el(
            "p",
            data.source === "partner"
              ? "Thông tin bổ sung và phê duyệt của cư dân được gửi qua ứng dụng đối tác."
              : data.workflow.state === "closed"
                ? "Công việc đã kết thúc."
                : "Chỉ người giao việc có quyền bổ sung khi workflow cho phép.",
            "hint",
          ),
        );
    }
    if (tab === "room") {
      const entries = data.items.filter(
        (x) => !["evidence", "final"].includes(x.kind),
      );
      body.append(
        entries.length
          ? box("timeline", ...entries.map(itemCard))
          : empty(
              "Chưa có trao đổi trong case file",
              "Câu hỏi, phản biện, báo cáo và quyết định của agent sẽ xuất hiện tại đây.",
            ),
      );
    }
    if (tab === "evidence") {
      const entries = data.items.filter((x) =>
        ["evidence", "fact"].includes(x.kind),
      );
      body.append(
        entries.length
          ? box("timeline", ...entries.map(itemCard))
          : empty(
              "Chưa có bằng chứng",
              "Kết quả công cụ và thông tin đã ghi nhận được đánh số để agent trích dẫn.",
            ),
      );
    }
    if (tab === "memory") {
      body.append(
        box(
          "notice",
          el("strong", "Ghi chú chưa kiểm chứng"),
          el(
            "p",
            "Memory được tách theo agent và workflow. Các ghi chú này không tự động trở thành sự thật hoặc nguồn tri thức dùng chung.",
          ),
        ),
      );
      for (const m of data.memory)
        body.append(
          panel(
            m.profile_key + " · " + m.key,
            el("p", m.text, "prose"),
            el("small", date(m.updated)),
          ),
        );
      if (!data.memory.length)
        body.append(
          empty(
            "Chưa có memory",
            "Agent chỉ ghi nhớ khi hồ sơ bật memory và cần lưu ghi chú trong workflow.",
          ),
        );
    }
    if (tab === "operations") {
      body.append(
        panel(
          "Thao tác đối tác",
          data.operations.length
            ? table(
                [
                  "Tham chiếu",
                  "Trạng thái",
                  "Công việc bên đối tác",
                  "Thao tác",
                ],
                data.operations.map((o) => [
                  o.id,
                  badge(o.status),
                  o.external_job_id || "—",
                  ["unknown", "started"].includes(o.status)
                    ? btn("Đối soát", () => reconcile(o))
                    : "—",
                ]),
              )
            : el("p", "Chưa có thao tác đối tác.", "muted"),
        ),
        panel(
          "Yêu cầu đồng ý",
          data.approvals.length
            ? table(
                ["Nội dung", "Trạng thái", "Hết hạn"],
                data.approvals.map((a) => [
                  a.summary,
                  badge(a.status),
                  date(a.expires),
                ]),
              )
            : el("p", "Không có yêu cầu đồng ý.", "muted"),
        ),
        panel(
          "Chi phí theo agent",
          data.cost?.by_agent.length
            ? table(
                ["Agent", "Lượt gọi", "Input / output", "Chi phí"],
                data.cost.by_agent.map((a) => [
                  a.agent_name,
                  a.calls,
                  `${a.input_tokens} / ${a.output_tokens}`,
                  money(a.cost_usd),
                ]),
              )
            : el("p", "Chưa phát sinh lượt gọi model.", "muted"),
        ),
      );
    }
  }
  paint();
  root.refresh = async () => {
    data = await api(W + "/workspace/sessions/" + id);
    const focused = document.activeElement;
    if (
      !root.contains(focused) ||
      !["TEXTAREA", "INPUT"].includes(focused.tagName)
    )
      paint();
  };
  return root;
}
function reconcile(op) {
  showDialog(
    "Đối soát kết quả thực tế",
    form(
      [
        {
          key: "status",
          label: "Kết quả đã kiểm tra",
          type: "select",
          options: [
            "completed",
            "confirmed",
            "failed",
            "cancelled",
            "pending",
          ].map((v) => ({ value: v, label: labels[v] })),
        },
        {
          key: "external_job_id",
          label: "Mã công việc bên đối tác",
          value: op.external_job_id || "",
        },
        {
          key: "evidence",
          label: "Bằng chứng đối soát",
          type: "textarea",
          full: true,
          required: true,
          help: "Ghi kết quả đã kiểm tra bên đối tác. Thao tác này không gửi lại lệnh thực thi.",
        },
      ],
      (v) =>
        api(W + "/operations/" + op.id + "/reconcile", {
          ...v,
          external_job_id: v.external_job_id || null,
          expected_status: op.status,
        }),
      "Xác nhận kết quả",
      undefined,
      ["admin", "operator"].includes(session?.role),
    ),
  );
}
async function settings() {
  const [setup, all] = await Promise.all([
    api(W + "/workspace/setup"),
    profiles(),
  ]);
  const leaders = all.filter(
      (x) => x.status === "published" && x.profile.role === "leader",
    ),
    c = setup.settings || {};
  const root = box(
    "",
    head(
      "Thiết lập workspace",
      "Cấu hình điều phối cho công việc nội bộ. Các route đối tác có supervisor và quyền riêng.",
    ),
  );
  if (!leaders.length) {
    root.append(
      empty(
        "Cần công bố supervisor",
        "Tạo một agent có vai trò supervisor rồi công bố hồ sơ trước khi thiết lập.",
        link("Đến đội ngũ agent →", "agents"),
      ),
    );
    return root;
  }
  const f = form(
    [
      {
        key: "leader_profile",
        label: "Supervisor mặc định",
        type: "select",
        required: true,
        value: c.leader_profile || leaders[0].key,
        options: leaders.map((x) => ({ value: x.key, label: x.profile.name })),
      },
      {
        key: "budget_usd",
        label: "Ngân sách mỗi công việc (USD)",
        type: "number",
        min: 0.000001,
        step: "any",
        value: (c.budget_micros || 500000) / 1e6,
      },
      {
        key: "budget_tokens",
        label: "Trần token mỗi công việc",
        type: "number",
        min: 1,
        value: c.budget_tokens || 100000,
      },
    ],
    (v) =>
      api(
        W + "/workspace/setup",
        {
          leader_profile: v.leader_profile,
          budget_micros: Math.round(v.budget_usd * 1e6),
          budget_tokens: v.budget_tokens,
        },
        "PUT",
      ),
    "Lưu thiết lập",
  );
  f.querySelector(".form-actions button").remove();
  root.append(
    panel("Điều phối mặc định", f),
    panel(
      "Phạm vi cấu hình",
      el(
        "p",
        "Người giao việc chỉ nhập yêu cầu. Supervisor chọn chuyên viên trong quyền mời của hồ sơ; không phải tất cả agent được cấp đều tham gia.",
      ),
      el(
        "p",
        "Công việc đang chạy giữ snapshot của hồ sơ, model, tri thức và ngân sách. Thiết lập mới áp dụng cho công việc tạo sau.",
        "muted",
      ),
    ),
  );
  return root;
}
async function knowledge() {
  const { items } = await api(W + "/knowledge/documents");
  const create = () =>
    showDialog(
      "Công bố tài liệu đã duyệt",
      form(
        [
          {
            key: "knowledge_base_id",
            label: "Mã kho tri thức",
            required: true,
            pattern: "[a-zA-Z0-9_-]{1,80}",
          },
          { key: "document_key", label: "Mã tài liệu", required: true },
          { key: "title", label: "Tiêu đề", full: true, required: true },
          { key: "source", label: "Nguồn / đường dẫn tham chiếu", full: true },
          {
            key: "text",
            label: "Nội dung đã được duyệt",
            type: "textarea",
            full: true,
            required: true,
          },
        ],
        (v) => api(W + "/knowledge/documents", v),
        "Công bố",
      ),
    );
  const root = box(
    "",
    head(
      "Kho tri thức",
      "Tài liệu được duyệt, có phiên bản và nguồn gốc. Agent chỉ tra cứu trong quyền được cấp.",
      btn("＋ Công bố tài liệu", create, "primary", true),
    ),
  );
  if (!items.length) {
    root.append(
      empty(
        "Chưa có tài liệu",
        "Công bố nội dung đã được kiểm tra, sau đó gắn mã kho vào hồ sơ agent và route.",
      ),
    );
    return root;
  }
  const rows = items.map((d) => {
    const read = () =>
      showDialog(
        d.title,
        box(
          "",
          definition([
            ["Kho", d.knowledge_base_id],
            ["Nguồn", d.source || "—"],
            ["Phiên bản", d.version],
          ]),
          el("p", d.text, "prose document-text"),
        ),
      );
    const revoke = async () => {
      if (confirm("Thu hồi tài liệu " + d.title + "?")) {
        await api(W + "/knowledge/documents/" + d.id + "/revoke", {});
        await render();
      }
    };
    return [
      box(
        "",
        el("strong", d.title),
        el("p", d.source || "Chưa có nguồn tham chiếu"),
      ),
      d.knowledge_base_id,
      box("tags", el("span", "v" + d.version, "badge"), badge(d.status)),
      box(
        "actions",
        btn("Đọc", read),
        d.status === "published"
          ? btn("Thu hồi", revoke, "danger", true)
          : null,
      ),
    ];
  });
  root.append(
    panel(
      "Tài liệu",
      table(["Tài liệu", "Kho tri thức", "Phiên bản", "Thao tác"], rows),
    ),
  );
  return root;
}
async function modelPage() {
  const [{ models }, cost] = await Promise.all([
    api(P + "/models"),
    api(P + "/cost"),
  ]);
  const root = box(
    "",
    head(
      "Model & provider",
      "Xem model khả dụng, chọn model theo từng agent và theo dõi chi phí thực tế.",
    ),
  );
  root.append(
    stats([
      ["Model đã khai báo", models.length],
      ["Có credential", models.filter((x) => x.available).length],
      ["Có giá", models.filter((x) => x.priced).length],
      [
        "Chi phí 24 giờ",
        money(cost.models.reduce((sum, x) => sum + x.cost_usd, 0)),
      ],
    ]),
  );
  root.append(
    panel(
      "Danh mục model",
      models.length
        ? table(
            ["Model", "Provider", "Tầng", "Credential", "Giá"],
            models.map((m) => [
              m.id,
              m.provider,
              labels[m.tier],
              badge(m.available ? "ready" : "pending"),
              m.priced ? "Đã cấu hình" : "Chưa cấu hình",
            ]),
          )
        : empty(
            "Chưa cấu hình model",
            "Workspace đang hoạt động nhưng chưa thể gọi model. Cần cấu hình provider, credential và giá trước khi giao việc.",
          ),
    ),
  );
  root.append(
    panel(
      "Kết nối provider",
      el(
        "p",
        "Runtime hiện nạp catalog từ AWP_MODELS_FILE. Người vận hành khai báo model trong models.yaml, đặt API key qua biến môi trường của API và worker, sau đó khởi động lại hai dịch vụ.",
      ),
      el(
        "p",
        "Các provider được hỗ trợ: OpenAI, OpenAI-compatible, Anthropic, Gemini, DeepSeek, DashScope, Moonshot, MiniMax, Volcengine, xAI và Ollama.",
        "muted",
      ),
      el(
        "p",
        "Giá input/output là USD trên một triệu token. Không có credential hoặc chưa có giá thì workspace sẽ chặn tạo công việc; không coi model đó là miễn phí.",
        "hint",
      ),
    ),
  );
  if (cost.models.length)
    root.append(
      panel(
        "Chi phí 24 giờ theo model",
        table(
          ["Model", "Lượt gọi", "Input / output", "Chi phí"],
          cost.models.map((m) => [
            m.model,
            m.calls,
            `${m.input_tokens} / ${m.output_tokens}`,
            money(m.cost_usd),
          ]),
        ),
      ),
    );
  return root;
}
async function routeForm(record) {
  const [clients, all, integrations] = await Promise.all([
    api(W + "/clients"),
    profiles(),
    api(W + "/integrations"),
  ]);
  const c = record?.config || {};
  showDialog(
    record ? "Cập nhật route" : "Tạo route đối tác",
    form(
      [
        {
          key: "client_id",
          label: "Đối tác khách hàng",
          type: "select",
          value: c.client_id || "",
          required: true,
          options: clients.items
            .filter(
              (x) => x.purpose === "customer" && !x.id.startsWith("console_"),
            )
            .map((x) => ({ value: x.id, label: x.id })),
        },
        {
          key: "external_management_ref",
          label: "Mã đơn vị quản lý bên đối tác",
          value: c.external_management_ref || "",
          readonly: !!record,
          required: true,
        },
        {
          key: "workspace",
          label: "Workspace",
          value: c.workspace || "",
          required: true,
        },
        {
          key: "manager_ref",
          label: "Định danh đơn vị quản lý",
          value: c.manager_ref || "",
          required: true,
        },
        {
          key: "leader_profile",
          label: "Supervisor",
          type: "select",
          required: true,
          value: c.leader_profile || "",
          options: all
            .filter(
              (x) => x.status === "published" && x.profile.role === "leader",
            )
            .map((x) => ({ value: x.key, label: x.profile.name })),
        },
        {
          key: "ticket_binding_mode",
          label: "Ràng buộc ticket",
          type: "select",
          value: c.ticket_binding_mode || "required",
          options: [
            { value: "required", label: "Bắt buộc ticket" },
            { value: "optional", label: "Ticket tùy chọn" },
          ],
        },
        {
          key: "budget_usd",
          label: "Ngân sách mỗi workflow (USD)",
          type: "number",
          min: 0.000001,
          step: "any",
          value: (c.budget_micros || 500000) / 1e6,
        },
        {
          key: "budget_tokens",
          label: "Trần token",
          type: "number",
          min: 1,
          value: c.budget_tokens || 100000,
        },
        {
          key: "max_active_workflows",
          label: "Số workflow đồng thời",
          type: "number",
          min: 1,
          max: 1000,
          value: c.max_active_workflows || 20,
        },
        ...[
          "require_residence",
          "read_only_auto_close",
          "asset_capability",
        ].map((k, i) => ({
          key: k,
          label: [
            "Kiểm tra cư trú",
            "Tự đóng tác vụ chỉ đọc",
            "Cho phép ảnh MinIO",
          ][i],
          type: "select",
          value: String(c[k] ?? k !== "asset_capability"),
          options: [
            { value: "true", label: "Bật" },
            { value: "false", label: "Tắt" },
          ],
        })),
        {
          key: "integration_ids",
          label: "Kết nối MCP được phép",
          type: "checks",
          full: true,
          value: c.integration_ids || [],
          options: integrations.items
            .filter((x) => x.status === "active")
            .map((x) => ({ value: x.id, label: x.id })),
        },
        listField(
          "knowledge_base_ids",
          "Kho tri thức của route",
          c.knowledge_base_ids || [],
        ),
      ],
      async (v) => {
        const value = {
          ...v,
          budget_micros: Math.round(v.budget_usd * 1e6),
          knowledge_base_ids: lines(v.knowledge_base_ids),
        };
        delete value.budget_usd;
        for (const k of [
          "require_residence",
          "read_only_auto_close",
          "asset_capability",
        ])
          value[k] = v[k] === "true";
        if (record) value.expected_revision = record.revision;
        await api(
          W + "/routes" + (record ? "/" + record.id : ""),
          value,
          record ? "PUT" : "POST",
        );
      },
      "Lưu route",
      "Đối tác phải xác nhận route qua API. Thay đổi route đang dùng có thể chặn workflow cũ; kiểm tra trước khi lưu.",
    ),
  );
}
async function routes() {
  const { items } = await api(W + "/routes");
  const external = items.filter(
    (x) => !x.config.client_id.startsWith("console_"),
  );
  return box(
    "",
    head(
      "Định tuyến đối tác",
      "Mỗi đơn vị quản lý có supervisor, knowledge, ngân sách và công cụ được cấp riêng.",
      btn("＋ Tạo route", () => routeForm(), "primary", true),
    ),
    panel(
      "Route",
      external.length
        ? table(
            [
              "Đơn vị quản lý",
              "Supervisor / workspace",
              "Trạng thái",
              "Thao tác",
            ],
            external.map((x) => [
              x.external_ref,
              box(
                "",
                el("strong", x.config.leader_profile),
                el("p", x.config.workspace),
              ),
              box(
                "tags",
                badge(x.status),
                el("span", "rev " + x.revision, "badge"),
              ),
              box(
                "actions",
                btn("Cấu hình", () => routeForm(x), "", true),
                btn("Chi tiết", () => showDialog("Route", technical(x))),
              ),
            ]),
          )
        : empty(
            "Chưa có route đối tác",
            "Tạo credential khách hàng và công bố supervisor trước khi thiết lập route.",
          ),
    ),
  );
}
const customerOps = [
  "submit_request",
  "reply",
  "read_result",
  "receive_events",
  "submit_consent",
  "close_workflow",
  "confirm_route",
  "sync_residence",
  "upload_asset",
];
function clientForm() {
  const specs = [
    {
      key: "id",
      label: "Mã credential",
      required: true,
      pattern: "[a-zA-Z0-9_-]{1,80}",
    },
    {
      key: "purpose",
      label: "Mục đích",
      type: "select",
      value: "customer",
      options: [
        { value: "customer", label: "Khách hàng gửi yêu cầu" },
        { value: "provider", label: "Provider gửi trạng thái" },
      ],
    },
    {
      key: "operations",
      label: "Quyền khách hàng",
      type: "checks",
      full: true,
      value: customerOps,
      options: customerOps.map((x) => ({ value: x, label: x })),
    },
    {
      key: "provider_settings",
      label: "Schema sự kiện provider (cấu hình nâng cao)",
      type: "textarea",
      full: true,
      value: '{"event_map":{},"transitions":{}}',
      help: "Provider cần schema sự kiện đã thống nhất với đối tác. Không tự suy diễn trạng thái.",
    },
  ];
  const f = form(
    specs,
    async (v) => {
      const value = {
        id: v.id,
        purpose: v.purpose,
        operations:
          v.purpose === "customer"
            ? v.operations
            : ["publish_job_event", "read_event_receipt"],
        settings:
          v.purpose === "customer" ? {} : JSON.parse(v.provider_settings),
      };
      const result = await api(W + "/clients", value);
      setTimeout(
        () =>
          showDialog(
            "Lưu khóa — chỉ hiển thị một lần",
            box(
              "",
              el(
                "p",
                "Lưu khóa tại backend đối tác. Không đưa khóa vào trình duyệt cư dân.",
                "notice",
              ),
              el("pre", JSON.stringify(result, null, 2)),
            ),
          ),
        0,
      );
    },
    "Tạo credential",
  );
  showDialog("Kết nối đối tác", f);
}
async function clients() {
  const { items } = await api(W + "/clients");
  const list = items.filter((x) => !x.id.startsWith("console_"));
  return box(
    "",
    head(
      "Đối tác & quyền truy cập",
      "Credential khách hàng và provider được tách theo mục đích; khóa được hiển thị một lần.",
      btn("＋ Tạo credential", clientForm, "primary", true),
    ),
    panel(
      "Credential",
      list.length
        ? table(
            ["Định danh", "Mục đích", "Trạng thái", "Thao tác"],
            list.map((x) => [
              x.id,
              x.purpose === "customer" ? "Khách hàng" : "Provider",
              badge(x.status),
              box(
                "actions",
                btn("Quyền", () =>
                  showDialog(
                    "Quyền " + x.id,
                    box(
                      "tags",
                      ...x.operations.map((o) => el("span", o, "badge")),
                    ),
                  ),
                ),
                btn(
                  "Xoay khóa",
                  async () => {
                    if (
                      confirm(
                        "Xoay khóa " +
                          x.id +
                          "? Đối tác cần cập nhật khóa mới.",
                      )
                    )
                      showDialog(
                        "Khóa mới — lưu ngay",
                        el(
                          "pre",
                          JSON.stringify(
                            await api(W + "/clients/" + x.id + "/rotate", {}),
                            null,
                            2,
                          ),
                        ),
                      );
                  },
                  "",
                  true,
                ),
                btn(
                  "Thu hồi",
                  async () => {
                    if (confirm("Thu hồi credential " + x.id + "?")) {
                      await api(W + "/clients/" + x.id + "/revoke", {});
                      await render();
                    }
                  },
                  "danger",
                  true,
                ),
              ),
            ]),
          )
        : empty(
            "Chưa có đối tác",
            "Credential dùng tại backend để gửi yêu cầu hoặc sự kiện trạng thái.",
          ),
    ),
  );
}
function integrationForm() {
  const toolRows = box(""),
    addTool = () => {
      const row = box("field-grid");
      row.append(
        field({
          key: "tool_name",
          label: "Tên tool",
          required: true,
          pattern: "[A-Za-z0-9_-]{1,100}",
        }),
        field({
          key: "tool_kind",
          label: "Loại công cụ",
          type: "select",
          options: [
            { value: "read", label: "Tra cứu chỉ đọc" },
            { value: "write", label: "Thực thi, cần đồng ý" },
          ],
        }),
      );
      toolRows.append(row);
    };
  addTool();
  const f = form(
    [
      {
        key: "id",
        label: "Mã kết nối",
        required: true,
        pattern: "[a-zA-Z0-9_-]{1,50}",
      },
      { key: "url", label: "Địa chỉ MCP", type: "url", required: true },
      {
        key: "header_name",
        label: "Tên header xác thực (tùy chọn)",
        placeholder: "Authorization / X-API-Key",
      },
      {
        key: "header_value",
        label: "Giá trị header xác thực",
        type: "password",
        help: "Nhập cả tiền tố Bearer nếu đối tác yêu cầu. Giá trị được mã hóa.",
      },
      {
        key: "context_signing_key",
        label: "Khóa ký context",
        type: "password",
        required: true,
        full: true,
        help: "Ít nhất 32 ký tự. Platform mã hóa khóa; không hiển thị lại.",
      },
    ],
    async (v) => {
      const tools = {};
      for (const row of toolRows.children) {
        const name = row.querySelector("[name=tool_name]").value;
        if (tools[name]) throw Error("Tên tool bị trùng.");
        const read = row.querySelector("[name=tool_kind]").value === "read";
        tools[name] = {
          read_only: read,
          requires_consent: !read,
          tracks_events: false,
        };
      }
      if (Boolean(v.header_name) !== Boolean(v.header_value))
        throw Error("Cần điền đủ tên và giá trị header.");
      await api(W + "/integrations", {
        id: v.id,
        url: v.url,
        context_signing_key: v.context_signing_key,
        tools,
        headers: v.header_name ? { [v.header_name]: v.header_value } : {},
      });
    },
    "Thêm kết nối",
  );
  f.insertBefore(
    box(
      "",
      el("h3", "Công cụ được phép"),
      toolRows,
      btn("＋ Thêm tool", addTool),
      el(
        "p",
        "Công cụ ghi cần đồng ý. Cấu hình tracking sự kiện và header xác thực nâng cao vẫn thực hiện qua API admin.",
        "hint",
      ),
    ),
    f.querySelector(".form-actions"),
  );
  showDialog("Kết nối MCP", f);
}
async function integrations() {
  const { items } = await api(W + "/integrations");
  return box(
    "",
    head(
      "Công cụ MCP",
      "Kết nối công cụ đối tác và kiểm soát quyền đọc, ghi, yêu cầu đồng ý.",
      btn("＋ Thêm kết nối", integrationForm, "primary", true),
    ),
    items.length
      ? box(
          "agent-grid",
          ...items.map((x) =>
            box(
              "agent-card",
              box(
                "inline",
                el("span", "↗", "avatar"),
                box("", el("h2", x.id), badge(x.status)),
              ),
              el("p", x.url),
              ...Object.entries(x.tools).map(([name, p]) =>
                box(
                  "tool-note",
                  el("strong", name),
                  el(
                    "p",
                    `${p.read_only ? "Chỉ đọc" : "Thực thi"} · ${p.requires_consent ? "Cần đồng ý" : "Không yêu cầu đồng ý"} · ${p.tracks_events ? "Có tracking" : "Không tracking"}`,
                  ),
                ),
              ),
              btn(
                "Thu hồi kết nối",
                async () => {
                  if (confirm("Thu hồi MCP " + x.id + "?")) {
                    await api(W + "/integrations/" + x.id + "/revoke", {});
                    await render();
                  }
                },
                "danger",
                true,
              ),
            ),
          ),
        )
      : empty(
          "Chưa có kết nối MCP",
          "Kết nối công cụ trước, sau đó cấp quyền trong hồ sơ agent và route.",
        ),
  );
}
async function audit() {
  const { items } = await api(W + "/audit");
  return box(
    "",
    head(
      "Nhật ký quản trị",
      "Theo dõi người thực hiện, tài nguyên và thay đổi đã ghi nhận.",
    ),
    panel(
      "100 sự kiện gần nhất",
      items.length
        ? table(
            ["Thời điểm", "Người thực hiện", "Thao tác", "Tài nguyên"],
            items.map((x) => [date(x.created), x.actor, x.action, x.resource]),
          )
        : empty(
            "Chưa có nhật ký",
            "Các thay đổi quản trị và đối soát sẽ được ghi tại đây.",
          ),
    ),
  );
}
const pages = {
  overview: ["Tổng quan", "◫", overview],
  work: ["Công việc", "◷", workList],
  agents: ["Đội ngũ agent", "♧", agentList],
  knowledge: ["Kho tri thức", "▤", knowledge],
  models: ["Model & provider", "◇", modelPage],
  integrations: ["Công cụ MCP", "↗", integrations],
  routes: ["Định tuyến", "⑂", routes],
  clients: ["Đối tác & khóa", "⚿", clients],
  settings: ["Thiết lập", "⚙", settings],
  audit: ["Nhật ký", "≡", audit],
};
async function render() {
  if (!session) return;
  const token = ++navigation;
  clearInterval(refreshTimer);
  const [page, id, version] = (location.hash.slice(1) || "overview").split("/");
  $("sidebar").classList.remove("open");
  $("menu").setAttribute("aria-expanded", "false");
  for (const a of $("nav").querySelectorAll("a"))
    a.classList.toggle(
      "active",
      a.dataset.page === (page === "agent" ? "agents" : page),
    );
  $("breadcrumb").textContent =
    "Workspace / " +
    (pages[page]?.[0] ||
      (page === "agent" ? "Hồ sơ agent" : "Chi tiết công việc"));
  $("content").replaceChildren(el("p", "Đang tải workspace…", "loading"));
  try {
    const content =
      page === "agent"
        ? await agentDetail(id, version)
        : page === "work" && id
          ? await workDetail(id)
          : pages[page]
            ? await pages[page][2]()
            : empty(
                "Không tìm thấy trang",
                "Chọn một mục trong thanh điều hướng.",
                link("Về tổng quan", "overview"),
              );
    if (token !== navigation) return;
    $("content").replaceChildren(content);
    $("sync-status").textContent =
      "Cập nhật " + new Date().toLocaleTimeString("vi-VN");
    if (content.refresh) {
      const update = content.refresh;
      let busy = false;
      refreshTimer = setInterval(async () => {
        if (busy || document.hidden || $("editor").open) return;
        busy = true;
        try {
          await update();
          if (token === navigation)
            $("sync-status").textContent =
              "Cập nhật " + new Date().toLocaleTimeString("vi-VN");
        } catch (e) {
          if (token === navigation)
            $("sync-status").textContent = "Mất kết nối · đang thử lại";
        } finally {
          busy = false;
        }
      }, 5000);
    }
  } catch (e) {
    if (token !== navigation) return;
    $("content").replaceChildren(
      head("Không tải được dữ liệu", "Kiểm tra kết nối và quyền truy cập."),
      el("p", e.message, "error"),
      btn("Thử lại", render),
    );
    $("sync-status").textContent = "Không kết nối";
  }
}
async function ready(user) {
  session = user;
  $("login").hidden = true;
  $("app").hidden = false;
  $("identity").textContent =
    user.username +
    " · " +
    ({ admin: "Quản trị", operator: "Vận hành", viewer: "Chỉ xem" }[
      user.role
    ] || user.role);
  $("nav").replaceChildren();
  for (const [group, keys] of [
    ["LÀM VIỆC", ["overview", "work", "agents", "knowledge"]],
    ["KẾT NỐI", ["models", "integrations", "routes", "clients"]],
    ["QUẢN TRỊ", ["settings", "audit"]],
  ]) {
    $("nav").append(el("p", group, "nav-label"));
    for (const key of keys) {
      const [title, icon] = pages[key],
        a = link("", "#" + key, "nav-link");
      a.href = "#" + key;
      a.dataset.page = key;
      const symbol = el("span", icon, "nav-icon");
      symbol.setAttribute("aria-hidden", "true");
      a.append(symbol, document.createTextNode(title));
      $("nav").append(a);
    }
  }
  await render();
}
$("login-form").onsubmit = async (e) => {
  e.preventDefault();
  const f = e.currentTarget,
    save = f.querySelector("button");
  save.disabled = true;
  $("login-error").textContent = "";
  try {
    const values = Object.fromEntries(new FormData(f));
    await ready(await api("/console/login", values));
    f.reset();
  } catch (e) {
    $("login-error").textContent = e.message;
  } finally {
    save.disabled = false;
  }
};
$("logout").onclick = async () => {
  await api("/console/logout", {});
  location.reload();
};
$("close-editor").onclick = () => $("editor").close();
$("menu").onclick = () => {
  $("sidebar").classList.toggle("open");
  $("menu").setAttribute(
    "aria-expanded",
    String($("sidebar").classList.contains("open")),
  );
};
window.addEventListener("hashchange", render);
api("/console/session")
  .then(ready)
  .catch((e) => {
    if (e.status !== 401)
      $("login-error").textContent =
        "Không kết nối được máy chủ. Vui lòng thử đăng nhập lại.";
  });
