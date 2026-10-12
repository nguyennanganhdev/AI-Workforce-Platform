/* The admin console of the platform (served at /console).
 *
 * One file, no framework, no build step, nothing loaded from another origin. The page holds no data and no rules of
 * its own: every screen is a reading of the admin API, called with the key the operator typed, and the API decides
 * what that key sees and may do. The key lives in sessionStorage (gone with the tab or on logout) and is only ever
 * sent in the Authorization header, never in a URL.
 *
 * Everything that comes from the API or from a person goes into the page as text (textContent / text nodes) through
 * `h`; this file never parses a string as HTML.
 */
'use strict';
(() => {
  // ---- the endpoints this page calls: [method, path]; {} is a path argument, always percent-encoded --------------------
  const EP = {
    me: ['GET', '/platform/v1/wf/me'],
    routes: ['GET', '/platform/v1/wf/routes'],
    mcpList: ['GET', '/platform/v1/wf/routes/{}/mcp'],
    mcpAdd: ['POST', '/platform/v1/wf/routes/{}/mcp'],
    mcpEnable: ['POST', '/platform/v1/wf/routes/{}/mcp/{}/enable'],
    mcpRefresh: ['POST', '/platform/v1/wf/routes/{}/mcp/{}/refresh'],
    mcpDisable: ['POST', '/platform/v1/wf/routes/{}/mcp/{}/disable'],
    toolList: ['GET', '/platform/v1/wf/routes/{}/tools'],
    toolPatch: ['PATCH', '/platform/v1/wf/routes/{}/tools/{}'],
    profiles: ['GET', '/platform/v1/profiles'],
    gate: ['GET', '/platform/v1/profiles/{}/versions/{}/gate'],
    evalCases: ['GET', '/platform/v1/profiles/{}/eval-cases'],
    evalCaseAdd: ['POST', '/platform/v1/profiles/{}/eval-cases'],
    evalCaseSet: ['PUT', '/platform/v1/profiles/{}/eval-cases/{}'],
    evalCaseDrop: ['DELETE', '/platform/v1/profiles/{}/eval-cases/{}'],
    evalRun: ['POST', '/platform/v1/profiles/{}/versions/{}/evals'],
    evalRuns: ['GET', '/platform/v1/profiles/{}/versions/{}/evals'],
    publish: ['POST', '/platform/v1/profiles/{}/versions/{}/publish'],
    rollback: ['POST', '/platform/v1/profiles/{}/rollback'],
    history: ['GET', '/platform/v1/profiles/{}/history'],
    builderNew: ['POST', '/platform/v1/builder/sessions'],
    builderGet: ['GET', '/platform/v1/builder/sessions/{}'],
    builderSay: ['POST', '/platform/v1/builder/sessions/{}/messages'],
    builderApply: ['POST', '/platform/v1/builder/sessions/{}/apply'],
    clients: ['GET', '/platform/v1/wf/clients'],
    clientAdd: ['POST', '/platform/v1/wf/clients'],
    keys: ['GET', '/platform/v1/wf/clients/{}/keys'],
    keyAdd: ['POST', '/platform/v1/wf/clients/{}/keys'],
    keyRevoke: ['POST', '/platform/v1/wf/keys/{}/revoke'],
    keyRotate: ['POST', '/platform/v1/wf/keys/{}/rotate'],
    managers: ['GET', '/platform/v1/wf/managers'],
    managerAdd: ['POST', '/platform/v1/wf/clients/{}/managers'],
    managerDisable: ['POST', '/platform/v1/wf/managers/{}/disable'],
    managerEnable: ['POST', '/platform/v1/wf/managers/{}/enable'],
    managerKeys: ['GET', '/platform/v1/wf/managers/{}/keys'],
    managerKeyAdd: ['POST', '/platform/v1/wf/managers/{}/keys'],
    managerKeyRevoke: ['POST', '/platform/v1/wf/managers/{}/keys/{}/revoke'],
    routeAdd: ['POST', '/platform/v1/wf/clients/{}/routes'],
    routeSuspend: ['POST', '/platform/v1/wf/routes/{}/suspend'],
    routeReplace: ['POST', '/platform/v1/wf/routes/{}/replace'],
    integrations: ['GET', '/platform/v1/wf/integrations'],
    integrationAdd: ['POST', '/platform/v1/wf/clients/{}/integrations'],
    integration: ['GET', '/platform/v1/wf/integrations/{}'],
    providerKeys: ['GET', '/platform/v1/wf/integrations/{}/keys'],
    providerKeyAdd: ['POST', '/platform/v1/wf/integrations/{}/keys'],
    signingKeyAdd: ['POST', '/platform/v1/wf/integrations/{}/signing-keys'],
    signingKeyRevoke: ['POST', '/platform/v1/wf/integrations/{}/signing-keys/{}/revoke'],
    workflows: ['GET', '/platform/v1/wf/workflows'],
    workflow: ['GET', '/platform/v1/wf/workflows/{}'],
    operations: ['GET', '/platform/v1/wf/operations'],
    approvals: ['GET', '/platform/v1/wf/approvals'],
    receipts: ['GET', '/platform/v1/wf/receipts'],
    resolve: ['POST', '/platform/v1/wf/workflows/{}/resolve'],
    cost: ['GET', '/platform/v1/cost'],
    cases: ['GET', '/platform/v1/cases'],
    caseCost: ['GET', '/platform/v1/cases/{}/cost'],
  };

  const KEY = 'awp.console.key';
  const BUILDER = 'awp.console.builder';
  const state = { key: '', me: null, seq: 0, keep: {} };
  const root = document.getElementById('app');
  const store = {
    get(k) { try { return window.sessionStorage.getItem(k) || ''; } catch (e) { return ''; } },
    set(k, v) { try { window.sessionStorage.setItem(k, v); } catch (e) { /* a private window: the key lives in memory only */ } },
    drop(k) { try { window.sessionStorage.removeItem(k); } catch (e) { /* nothing to drop */ } },
  };

  // ---- the DOM, as text only -------------------------------------------------------------------------------------------
  function add(el, kids) {
    for (const kid of kids) {
      if (kid == null || kid === false) continue;
      if (Array.isArray(kid)) add(el, kid);
      else el.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
    }
    return el;
  }

  /** An element. Properties are set as properties, listeners are functions, a link only ever points inside the page. */
  function h(tag, props, ...kids) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(props || {})) {
      if (v == null || v === false) continue;
      if (k === 'class') el.className = v;
      else if (k === 'text') el.textContent = String(v);
      else if (k.startsWith('on')) {
        if (typeof v !== 'function') throw new Error('a listener must be a function');
        el.addEventListener(k.slice(2), v);
      } else if (k === 'href') {
        if (!String(v).startsWith('#/')) throw new Error('links stay inside the console');
        el.setAttribute('href', v);
      } else if (k.startsWith('aria-') || k === 'role' || k === 'for' || k === 'colspan') el.setAttribute(k, String(v));
      else el[k] = v;
    }
    return add(el, kids);
  }

  const link = (parts, text, cls) => h('a', { href: '#/' + parts.map(encodeURIComponent).join('/'), class: cls }, text);
  const mono = (text) => h('span', { class: 'mono', text: text == null ? '' : text });
  const dash = (v) => (v == null || v === '' ? '—' : v);
  const chips = (list) => (list && list.length ? h('div', { class: 'chips' }, list.map((x) => h('span', { class: 'chip', text: x }))) : '—');
  const json = (v) => JSON.stringify(v, null, 2);

  function when(v) {
    if (v == null || v === '') return '—';
    const d = new Date(typeof v === 'number' ? v * 1000 : v);
    return isNaN(d) ? String(v) : d.toLocaleString('vi-VN', { hour12: false });
  }
  const usd = (n) => (n == null ? '—' : '$' + Number(n).toFixed(Number(n) !== 0 && Math.abs(n) < 0.01 ? 6 : 4));
  const num = (n) => (n == null ? '—' : Number(n).toLocaleString('vi-VN'));

  const TONES = {
    ok: ['active', 'published', 'passed', 'applied', 'approved', 'confirmed', 'completed', 'done', 'succeeded'],
    warn: ['pending', 'proposed', 'draft', 'running', 'awaiting_user', 'awaiting_approval', 'awaiting_confirmation',
      'waiting_external_event', 'quarantined', 'processing', 'intent', 'sent', 'accepted'],
    bad: ['needs_attention', 'failed', 'error', 'revoked', 'suspended', 'rejected', 'blocked_authorization',
      'blocked_route_changed', 'gone', 'unknown', 'expired', 'cancelled'],
  };
  function badge(text, tone) {
    const t = tone || Object.keys(TONES).find((k) => TONES[k].includes(text)) || '';
    return h('span', { class: 'badge ' + t, text: dash(text) });
  }

  function table(cols, rows, empty, rowClass) {
    if (!rows.length) return h('div', { class: 'empty', text: empty });
    return h('div', { class: 'table-wrap' }, h('table', null,
      h('thead', null, h('tr', null, cols.map((c) => h('th', { class: c.cls, text: c.title })))),
      h('tbody', null, rows.map((row) => h('tr', { class: rowClass ? rowClass(row) : null },
        cols.map((c) => add(h('td', { class: c.cls }), [c.cell(row)])))))));
  }

  function panel(title, hint, actions, body, flush) {
    return h('section', { class: 'panel' },
      h('div', { class: 'panel-head' }, h('h2', null, title, hint ? h('span', { class: 'hint', text: '  ' + hint }) : null),
        h('div', { class: 'row' }, actions || [])),
      h('div', { class: 'panel-body' + (flush === false ? '' : ' flush') }, body));
  }
  const kv = (pairs) => h('dl', { class: 'kv' }, pairs.map(([k, v]) => [h('dt', { text: k }), add(h('dd'), [v])]));
  const note = (tone, title, ...kids) => h('div', { class: 'box ' + tone }, title ? h('div', { class: 'title', text: title }) : null, kids);

  // ---- errors of the API, shown as they are ----------------------------------------------------------------------------
  class ApiError extends Error {
    constructor(status, body) { super('HTTP ' + status); this.status = status; this.body = body; }
  }
  const HINTS = {
    0: 'Không kết nối được máy chủ.',
    400: 'Yêu cầu không hợp lệ.',
    401: 'Khóa không đúng, đã bị thu hồi hoặc đã hết hạn.',
    403: 'Khóa này không có quyền làm việc này.',
    404: 'Không tìm thấy, hoặc không thuộc phạm vi của khóa này.',
    409: 'Xung đột: trạng thái hiện tại không cho phép thao tác này.',
    422: 'Dữ liệu gửi lên chưa hợp lệ.',
    429: 'Gọi quá nhanh, hãy thử lại sau.',
    502: 'Hệ thống bên ngoài (MCP server hoặc model) không trả lời đúng.',
    503: 'Dịch vụ chưa sẵn sàng (thiếu cấu hình hoặc chưa có model).',
  };
  function details(body) {
    const d = body && typeof body === 'object' && 'detail' in body ? body.detail : body;
    if (d == null) return [];
    if (typeof d === 'string') return [d];
    if (Array.isArray(d)) return d.map((x) => (x && x.msg ? (Array.isArray(x.loc) ? x.loc.join('.') + ': ' : '') + x.msg : JSON.stringify(x)));
    if (d.message) return [(d.code ? d.code + ': ' : '') + d.message];
    return [JSON.stringify(d)];
  }
  function errorBox(e, retry) {
    if (!(e instanceof ApiError)) {
      return note('error', 'Lỗi của trang', h('div', { text: String(e && e.message ? e.message : e) }));
    }
    const lines = details(e.body);
    return note('error', (e.status ? 'Lỗi ' + e.status + '. ' : '') + (HINTS[e.status] || 'Máy chủ từ chối yêu cầu.'),
      lines.length ? h('ul', null, lines.map((x) => h('li', { text: x }))) : null,
      e.body != null ? h('details', null, h('summary', { text: 'Nội dung máy chủ trả về' }),
        h('pre', { text: typeof e.body === 'string' ? e.body : json(e.body) })) : null,
      retry ? h('div', { class: 'row' }, h('button', { class: 'sm', type: 'button', onclick: retry, text: 'Thử lại' })) : null);
  }

  // ---- the one way out of the page: same origin, the key in a header --------------------------------------------------
  async function call(name, args, opts) {
    const [method, template] = EP[name];
    const given = args || [];
    let i = 0;
    let path = template.replace(/\{\}/g, () => encodeURIComponent(String(given[i++])));
    const query = new URLSearchParams();
    for (const [k, v] of Object.entries((opts && opts.query) || {})) if (v != null && v !== '') query.set(k, v);
    if ([...query].length) path += '?' + query.toString();
    const headers = { Authorization: 'Bearer ' + state.key, Accept: 'application/json' };
    const init = { method, headers, cache: 'no-store', credentials: 'omit', referrerPolicy: 'no-referrer' };
    if (opts && opts.body !== undefined) {
      headers['Content-Type'] = 'application/json';
      init.body = JSON.stringify(opts.body);
    }
    let res;
    try { res = await fetch(path, init); } catch (e) { throw new ApiError(0, null); }
    const text = await res.text();
    let data = null;
    try { data = text ? JSON.parse(text) : null; } catch (e) { data = text; }
    if (!res.ok) {
      if (res.status === 401 && state.me) logout('Khóa không còn hiệu lực. Hãy đăng nhập lại.');
      throw new ApiError(res.status, data);
    }
    return data;
  }

  /** Fill `box` with what `fn` resolves to; meanwhile a loading line, on failure the error and a retry. */
  async function load(box, fn) {
    const mine = box.loadSeq = (box.loadSeq || 0) + 1;
    const seq = state.seq;
    box.replaceChildren(h('div', { class: 'loading', text: 'Đang tải…' }));
    try {
      const made = await fn();
      if (box.loadSeq === mine && state.seq === seq) add(box, [made]).firstChild.remove();
    } catch (e) {
      if (box.loadSeq === mine && state.seq === seq) box.replaceChildren(errorBox(e, () => load(box, fn)));
    }
  }

  // ---- flash, toast, dialogs ----------------------------------------------------------------------------------------
  let flash = h('div', { class: 'flash' });
  const toasts = h('div', { class: 'toasts', 'aria-live': 'polite' });
  function toast(text) {
    const t = h('div', { class: 'toast', text });
    while (toasts.children.length >= 3) toasts.firstChild.remove();  // the newest three: a busy minute does not cover the screen
    toasts.append(t);
    setTimeout(() => t.remove(), 4500);
  }
  function fail(e) {
    flash.replaceChildren(errorBox(e), h('div', { class: 'row' },
      h('button', { class: 'sm', type: 'button', text: 'Đóng thông báo', onclick: () => flash.replaceChildren() })));
    flash.scrollIntoView({ block: 'nearest' });
  }
  /** A button that runs an action once at a time; a failure is shown where the operator looks. */
  function act(label, fn, cls) {
    const b = h('button', { type: 'button', class: cls || 'sm', text: label });
    b.addEventListener('click', async () => {
      b.disabled = true;
      b.textContent = label + '…';
      try { await fn(); } catch (e) { fail(e); } finally {
        b.disabled = false;
        b.textContent = label;
      }
    });
    return b;
  }

  function dialog(title, body, wide) {
    const d = h('dialog', { class: wide ? 'wide' : '' });
    add(d, [h('div', { class: 'dlg-head' }, h('h2', { text: title }),
      h('button', { type: 'button', class: 'sm', text: 'Đóng', onclick: () => d.close() })),
    h('div', { class: 'dlg-body' }, body)]);
    d.addEventListener('close', () => d.remove());
    document.body.append(d);
    d.showModal();
    return d;
  }
  const closeDialogs = () => document.querySelectorAll('dialog').forEach((d) => d.close());

  async function copy(text, button) {
    try {
      await navigator.clipboard.writeText(text);
      button.textContent = 'Đã chép';
    } catch (e) {
      button.textContent = 'Hãy chọn và chép tay';
    }
  }
  function copyField(label, value) {
    const input = h('input', { type: 'text', readOnly: true, value, onfocus: (e) => e.target.select() });
    const b = h('button', { type: 'button', text: 'Chép' });
    b.addEventListener('click', () => copy(value, b));
    return h('div', { class: 'field' }, h('label', { text: label }), h('div', { class: 'secret' }, input, b));
  }
  /** A secret the API returns exactly once: shown in a dialog, kept nowhere, gone when the dialog closes. */
  function showSecret(title, fields) {
    dialog(title, [
      note('warn', 'Chỉ hiện đúng một lần', h('div', { text: 'Platform chỉ lưu bản băm. Hãy chép và cất ngay; đóng hộp này là không xem lại được.' })),
      h('div', { class: 'stack' }, fields.filter(([, v]) => v).map(([label, value]) => copyField(label, value))),
    ]);
  }

  // ---- forms ------------------------------------------------------------------------------------------------------------
  let uid = 0;
  const lines = (text) => String(text || '').split(/[\n,]/).map((x) => x.trim()).filter(Boolean);
  const rows = (text) => String(text || '').split('\n').map((x) => x.trim()).filter(Boolean);

  /** fields: {name, label, type, required, value, options, hint, placeholder, maxLength, pattern, patternMsg, rows,
   *  object}. `check(values)` may return {name: message}. `onSubmit(values)` is awaited; what it throws is shown. */
  function form(fields, opts) {
    const controls = {};
    const msg = h('div', { class: 'form-msg' });
    const body = fields.map((f) => {
      const id = 'f' + (++uid);
      let input;
      if (f.type === 'select') {
        input = h('select', { id }, f.options.map(([v, label]) => h('option', { value: v, text: label })));
        input.value = f.value == null ? f.options[0][0] : f.value;
      } else if (f.type === 'textarea' || f.type === 'json' || f.type === 'calls') {
        input = h('textarea', { id, rows: f.rows || 4, class: f.type === 'textarea' ? '' : 'code', placeholder: f.placeholder,
          maxLength: f.maxLength, value: f.value == null ? '' : f.value });
      } else if (f.type === 'checkbox') {
        input = h('input', { id, type: 'checkbox', checked: !!f.value });
      } else if (f.type === 'checks') {
        input = h('div', { class: 'checks', id }, f.options.map(([v, label]) => h('label', null,
          h('input', { type: 'checkbox', value: v, checked: (f.value || []).includes(v) }), label)));
      } else {
        input = h('input', { id, type: f.type || 'text', placeholder: f.placeholder, maxLength: f.maxLength,
          autocomplete: 'off', value: f.value == null ? '' : String(f.value) });
        if (f.type === 'number') input.step = 'any';
      }
      const err = h('div', { class: 'err', role: 'alert' });
      controls[f.name] = { f, input, err };
      const label = h('label', { for: id }, f.label, f.required ? h('span', { class: 'req', text: ' *' }) : null);
      if (f.type === 'checkbox') {
        return h('div', { class: 'field' }, h('label', { class: 'inline', for: id }, input, f.label), f.hint ? h('div', { class: 'hint', text: f.hint }) : null, err);
      }
      return h('div', { class: 'field' }, label, input, f.hint ? h('div', { class: 'hint', text: f.hint }) : null, err);
    });

    function read() {
      const values = {};
      const errors = {};
      for (const [name, { f, input }] of Object.entries(controls)) {
        if (f.type === 'checkbox') { values[name] = input.checked; continue; }
        if (f.type === 'checks') {
          values[name] = [...input.querySelectorAll('input')].filter((x) => x.checked).map((x) => x.value);
          if (f.required && !values[name].length) errors[name] = 'Chọn ít nhất một mục.';
          continue;
        }
        const raw = input.value.trim();
        values[name] = raw;
        if (!raw) {
          if (f.required) errors[name] = 'Bắt buộc nhập.';
          if (f.type === 'number' || f.type === 'json') values[name] = null;
          if (f.type === 'calls') values[name] = [];
          continue;
        }
        if (f.pattern && !f.pattern.test(raw)) errors[name] = f.patternMsg || 'Sai định dạng.';
        if (f.type === 'number') {
          values[name] = Number(raw);
          if (isNaN(values[name])) errors[name] = 'Phải là một số.';
          else if (f.min != null && values[name] < f.min) errors[name] = 'Không được nhỏ hơn ' + f.min + '.';
          else if (f.max != null && values[name] > f.max) errors[name] = 'Không được lớn hơn ' + f.max + '.';
        }
        if (f.type === 'json') {
          try {
            values[name] = JSON.parse(raw);
            if (f.object && (typeof values[name] !== 'object' || values[name] === null || Array.isArray(values[name]))) {
              errors[name] = 'Phải là một đối tượng JSON {…}.';
            }
          } catch (e) { errors[name] = 'JSON không hợp lệ: ' + e.message; }
        }
        if (f.type === 'calls') {  // a tool name per line, or a JSON object {"tool": ..., "args": {...}}
          try {
            values[name] = rows(raw).map((x) => (x.startsWith('{') ? JSON.parse(x) : x));
          } catch (e) { errors[name] = 'Dòng JSON không hợp lệ: ' + e.message; }
        }
      }
      if (!Object.keys(errors).length && opts.check) Object.assign(errors, opts.check(values) || {});
      let first = null;
      for (const [name, { input, err }] of Object.entries(controls)) {
        err.textContent = errors[name] || '';
        if (input.setAttribute) input.setAttribute('aria-invalid', errors[name] ? 'true' : 'false');
        if (errors[name] && !first) first = input;
      }
      if (first && first.focus) first.focus();
      return first ? null : values;
    }

    const submit = h('button', { type: 'submit', class: 'primary' + (opts.danger ? ' danger' : ''), text: opts.submit || 'Lưu' });
    const el = h('form', { noValidate: true }, body, msg, h('div', { class: 'form-foot' },
      opts.cancel ? h('button', { type: 'button', text: 'Hủy', onclick: opts.cancel }) : null, submit));
    el.addEventListener('submit', async (ev) => {
      ev.preventDefault();
      const values = read();
      if (!values) return;
      const label = submit.textContent;
      submit.disabled = true;
      submit.textContent = 'Đang gửi…';
      msg.replaceChildren();
      try { await opts.onSubmit(values); } catch (e) { msg.replaceChildren(errorBox(e)); } finally {
        submit.disabled = false;
        submit.textContent = label;
      }
    });
    return el;
  }

  /** A dialog with a form in it; it closes when the submit succeeded. */
  function formDialog(title, fields, opts, intro, wide) {
    const d = dialog(title, [], wide);
    const f = form(fields, { ...opts, cancel: () => d.close(), onSubmit: async (v) => { await opts.onSubmit(v); d.close(); } });
    add(d.querySelector('.dlg-body'), [intro, f]);
    return d;
  }
  function confirm(title, text, label, fn, danger) {
    formDialog(title, [], { submit: label, danger, onSubmit: fn }, h('p', { class: 'field', text }));
  }

  const again = () => render();

  // =====================================================================================================================
  // 1. Kho tool
  // =====================================================================================================================
  const TRACKING = [['none', 'none: kết quả có ngay trong câu trả lời'], ['events', 'events: tiến độ về qua Provider Event API'],
    ['status_query', 'status_query: platform tự hỏi lại bằng một tool trạng thái']];

  async function toolsScreen(parts) {
    const { routes } = await call('routes');
    const head = pageHead('Kho tool', 'MCP server của từng route, tool phát hiện được và việc kích hoạt chúng.');
    if (!routes.length) {
      return [head, h('div', { class: 'panel' }, h('div', { class: 'empty', text: state.me.role === 'admin'
        ? 'Chưa có route nào. Tạo client, manager và route ở màn hình Đối tác trước.'
        : 'Tài khoản ban quản lý này chưa có route nào.' }))];
    }
    const live = routes.filter((r) => r.status !== 'replaced');
    const route = routes.find((r) => r.route_id === parts[0]) || live[live.length - 1] || routes[routes.length - 1];
    const pick = h('select', { class: 'auto', 'aria-label': 'Route' }, routes.map((r) => h('option', { value: r.route_id,
      text: r.external_management_ref + '  ·  ' + r.status + '  ·  ' + r.route_id })));
    pick.value = route.route_id;
    pick.addEventListener('change', () => { location.hash = '#/tools/' + encodeURIComponent(pick.value); });
    const body = h('div');
    load(body, () => toolStore(route));
    return [head, h('div', { class: 'panel' }, h('div', { class: 'panel-body row' }, h('strong', { text: 'Route' }), pick,
      badge(route.status), h('span', { class: 'muted small', text: 'Leader: ' + route.leader_profile }))), body];
  }

  async function toolStore(route) {
    const rid = route.route_id;
    const admin = state.me.role === 'admin';
    const [{ servers }, { tools }, integ] = await Promise.all([call('mcpList', [rid]), call('toolList', [rid]),
      admin ? call('integrations', [], { query: { client_id: route.client_id } }) : { integrations: [] }]);
    const frozen = route.status === 'replaced';
    const report = state.keep.report && state.keep.report.route === rid ? state.keep.report : null;

    const discover = (name, what) => async () => {
      const out = await call(what, [rid, name]);
      state.keep.report = { ...out, route: rid, server: name };  // `out.server` is the server's row: the name is what is shown
      toast(what === 'mcpEnable' ? 'Đã bật server ' + name : 'Đã làm mới server ' + name);
      again();
    };
    const serverTable = table([
      { title: 'Server', cell: (s) => [h('strong', { text: s.name }), h('div', { class: 'mono muted', text: s.url })] },
      { title: 'Trạng thái', cell: (s) => badge(s.enabled ? 'đang bật' : 'đang tắt', s.enabled ? 'ok' : '') },
      { title: 'Header', cell: (s) => chips(s.header_names) },
      { title: 'Lần phát hiện gần nhất', cell: (s) => when(s.last_discovered_at) },
      { title: 'Lỗi gần nhất', cls: 'wrap', cell: (s) => (s.last_error ? h('span', { class: 'err', text: s.last_error }) : '—') },
      { title: '', cls: 'actions', cell: (s) => (frozen ? '' : [
        s.enabled ? act('Làm mới', discover(s.name, 'mcpRefresh')) : act('Bật', discover(s.name, 'mcpEnable'), 'sm primary'),
        s.enabled ? act('Tắt', async () => { await call('mcpDisable', [rid, s.name]); toast('Đã tắt server ' + s.name); again(); }, 'sm danger') : null]) },
    ], servers, 'Route này chưa có MCP server nào. Thêm một server, rồi bật nó để platform đọc danh sách tool.');

    const addServer = () => formDialog('Thêm MCP server', [
      { name: 'name', label: 'Tên server', required: true, pattern: /^[A-Za-z0-9_-]{1,64}$/, patternMsg: 'Chỉ chữ, số, gạch dưới, gạch nối (tối đa 64).' },
      { name: 'url', label: 'URL (streamable HTTP)', required: true, hint: 'Địa chỉ đầy đủ của MCP server, bắt đầu bằng https.', pattern: /^https?:\/\/\S+$/, patternMsg: 'Phải là một URL http(s).' },
      { name: 'header', label: 'Tên header xác thực', placeholder: 'Authorization', pattern: /^[A-Za-z][A-Za-z0-9-]{0,63}$/, patternMsg: 'Tên header không hợp lệ.' },
      { name: 'value', label: 'Giá trị header', type: 'password', hint: 'Được niêm phong khi lưu; về sau chỉ hiện tên header.' },
      { name: 'timeout', label: 'Thời gian chờ (giây)', type: 'number', value: 8, min: 1, max: 10, required: true },
    ], {
      submit: 'Thêm server',
      check: (v) => (!!v.header !== !!v.value ? { [v.header ? 'value' : 'header']: 'Header cần cả tên và giá trị.' } : null),
      onSubmit: async (v) => {
        await call('mcpAdd', [rid], { body: { name: v.name, url: v.url, timeout: v.timeout, headers: v.header ? { [v.header]: v.value } : {} } });
        toast('Đã thêm server ' + v.name + ' (đang tắt). Bấm Bật để đọc danh sách tool.');
        again();
      },
    }, h('p', { class: 'field muted', text: 'Server mới ở trạng thái tắt. Khi bật, platform gọi tools/list và ghi lại từng tool.' }));

    const groups = [
      ['proposed', 'Tool chờ kích hoạt', 'Chưa agent nào dùng được cho tới khi một người kích hoạt.', 'Không có tool nào đang chờ kích hoạt.'],
      ['active', 'Tool đang dùng', 'Agent thấy các tool này khi server của chúng đang bật.', 'Chưa có tool nào đang dùng.'],
      ['gone', 'Tool đã mất', 'Server không còn liệt kê các tool này.', 'Không có tool nào đã mất.'],
    ];
    const toolPanel = ([status, title, hint, empty]) => panel(title, hint, null, table([
      { title: 'Tool', cell: (t) => [h('strong', { text: t.name }), t.mcp_tool !== t.name ? h('div', { class: 'mono muted', text: t.mcp_tool }) : null,
        h('div', { class: 'muted small', text: (t.description_override || (t.schema && t.schema.description) || '') })] },
      { title: 'Server', cell: (t) => t.server },
      { title: 'Loại', cell: (t) => badge(t.kind === 'lookup' ? 'tra cứu' : 'hành động', t.kind === 'lookup' ? 'info' : 'warn') },
      { title: 'Đồng ý của cư dân', cls: 'wrap', cell: (t) => (t.kind === 'lookup' ? (t.consent_waiver ? 'Tra cứu theo lời người: ' + t.consent_waiver : 'Không cần')
        : (t.requires_consent ? 'Hỏi trước khi chạy' : 'Miễn hỏi: ' + dash(t.consent_waiver))) },
      { title: 'Theo dõi', cell: (t) => (t.kind === 'lookup' ? '—' : [mono(t.tracking), t.client_reference_arg ? h('div', { class: 'muted small', text: 'ref: ' + t.client_reference_arg }) : null]) },
      { title: 'Nguồn', cls: 'nw', cell: (t) => [t.source === 'discovered' ? 'phát hiện' : 'khai tay', t.schema_changed_at ? h('div', { class: 'small', text: 'schema đổi ' + when(t.schema_changed_at) }) : null] },
      { title: '', cls: 'actions', cell: (t) => [
        t.schema ? h('button', { class: 'sm', type: 'button', text: 'Schema', onclick: () => dialog('Schema của ' + t.name, [
          h('p', { class: 'field', text: t.schema.description || 'Server không mô tả tool này.' }),
          note(t.schema.read_only ? 'ok' : 'warn', t.schema.read_only ? 'Server đánh dấu tool này là chỉ đọc (readOnlyHint).' : 'Server không đánh dấu tool này là chỉ đọc.'),
          h('pre', { text: json(t.schema.input_schema) })], true) }) : null,
        frozen || status === 'gone' ? null : h('button', { class: 'sm' + (status === 'proposed' ? ' primary' : ''), type: 'button',
          text: status === 'proposed' ? 'Kích hoạt' : 'Sửa', onclick: () => toolForm(rid, t, integ.integrations, status === 'proposed') }),
        frozen || status !== 'active' ? null : act('Ngưng dùng', async () => {
          await call('toolPatch', [rid, t.name], { body: { status: 'proposed' } });
          toast('Tool ' + t.name + ' đã về trạng thái chờ kích hoạt.');
          again();
        }, 'sm danger')] },
    ], tools.filter((t) => t.status === status), empty));

    return [
      frozen ? note('warn', 'Route này đã được thay thế', h('div', { text: 'Kho tool của nó chỉ còn để xem; route mới mang theo bản sao.' })) : null,
      panel('MCP server', servers.length + ' server', frozen ? null : [h('button', { class: 'primary', type: 'button', text: 'Thêm MCP server', onclick: addServer })], serverTable),
      report ? reportBox(report) : null,
      groups.map(toolPanel),
    ];
  }

  function reportBox(r) {
    const line = (label, list) => h('li', null, h('strong', { text: label + ': ' }), list.length ? list.join(', ') : 'không có');
    return h('div', { class: 'panel' }, h('div', { class: 'panel-body' }, note('info', 'Kết quả phát hiện của server ' + r.server,
      h('ul', null, line('Tool mới', r.added || []), line('Schema thay đổi', r.changed || []), line('Tool đã mất', r.gone || []),
        h('li', null, h('strong', { text: 'Bị từ chối: ' }), (r.rejected || []).length
          ? h('ul', null, r.rejected.map((x) => h('li', { text: x.mcp_tool + ': ' + x.reason }))) : 'không có')),
      h('div', { class: 'row' }, h('button', { class: 'sm', type: 'button', text: 'Ẩn', onclick: () => { state.keep.report = null; again(); } })))));
  }

  function toolForm(rid, t, integrations, activate) {
    const args = Object.keys((t.schema && t.schema.input_schema && t.schema.input_schema.properties) || {});
    const argHint = args.length ? 'Tham số của tool: ' + args.join(', ') : null;
    const vouched = !t.schema || t.schema.read_only || t.source !== 'discovered';
    const integ = integrations.length
      ? { type: 'select', options: [['', '(không gắn)'], ...integrations.map((x) => [x.integration_id, x.integration_id])] } : {};
    formDialog((activate ? 'Kích hoạt tool ' : 'Sửa tool ') + t.name, [
      { name: 'kind', label: 'Loại', type: 'select', value: t.kind, options: [['action', 'Hành động: có tác dụng phụ ở phía đối tác'], ['lookup', 'Tra cứu: chỉ đọc']] },
      { name: 'tracking', label: 'Theo dõi kết quả (với hành động)', type: 'select', value: t.tracking, options: TRACKING },
      { name: 'client_reference_arg', label: 'Tham số nhận mã tham chiếu (client_reference_arg)', value: t.client_reference_arg, hint: argHint },
      { name: 'idempotency_arg', label: 'Tham số nhận khóa idempotency (idempotency_arg)', value: t.idempotency_arg },
      { name: 'status_tool', label: 'Tool hỏi trạng thái (với status_query)', value: t.status_tool },
      { name: 'integration_id', label: 'Integration gửi sự kiện (với events)', value: t.integration_id || '', ...integ },
      { name: 'consent', label: 'Đồng ý của cư dân (với hành động)', type: 'select', value: t.kind === 'action' && !t.requires_consent ? 'waive' : 'ask',
        options: [['ask', 'Hỏi cư dân trước khi chạy (mặc định)'], ['waive', 'Không hỏi: phải ghi lý do']] },
      { name: 'consent_waiver', label: 'Lý do miễn hỏi, hoặc lý do coi là tra cứu', type: 'textarea', rows: 2, maxLength: 300, value: t.consent_waiver,
        hint: 'Lý do được lưu lại cùng tool.' },
      { name: 'consent_summary', label: 'Câu hỏi đồng ý hiện cho cư dân', maxLength: 300, value: t.consent_summary, hint: 'Ví dụ: Đặt lịch sửa chữa lúc {slot}' },
    ], {
      submit: activate ? 'Kích hoạt' : 'Lưu',
      check: (v) => {
        if (v.kind === 'lookup') return !vouched && !v.consent_waiver ? { consent_waiver: 'Server không đánh dấu tool này là chỉ đọc: phải ghi lý do.' } : null;
        if (v.consent === 'waive' && !v.consent_waiver) return { consent_waiver: 'Phải ghi lý do khi không hỏi cư dân.' };
        if (v.tracking === 'events' && !v.client_reference_arg && !v.idempotency_arg) return { client_reference_arg: 'Theo dõi bằng events cần tham số nhận mã tham chiếu hoặc khóa idempotency.' };
        if (v.tracking === 'status_query' && !(v.status_tool && v.client_reference_arg)) return { status_tool: 'status_query cần tool hỏi trạng thái và tham số nhận mã tham chiếu.' };
        return null;
      },
      onSubmit: async (v) => {
        await call('toolPatch', [rid, t.name], { body: toolBody(v, activate) });
        toast(activate ? 'Đã kích hoạt tool ' + t.name : 'Đã lưu tool ' + t.name);
        again();
      },
    }, activate ? note('info', null, h('div', { text: 'Sau khi kích hoạt, agent nào được cấp tên tool này sẽ dùng được nó. Hãy nói rõ kết quả của hành động được theo dõi thế nào.' })) : null, true);
  }

  /** What the form says, as the PATCH the API takes: everything the form shows is sent, so the row ends as shown. */
  function toolBody(v, activate) {
    const b = activate ? { status: 'active', kind: v.kind } : { kind: v.kind };
    if (v.kind === 'lookup') {
      return Object.assign(b, { read_only: true, requires_consent: false, tracking: 'none', client_reference_arg: null,
        idempotency_arg: null, status_tool: null, integration_id: null, consent_summary: null, consent_waiver: v.consent_waiver || null });
    }
    const asks = v.consent === 'ask';
    return Object.assign(b, { read_only: false, tracking: v.tracking, requires_consent: asks,
      consent_waiver: asks ? null : v.consent_waiver, consent_summary: asks ? v.consent_summary || null : null,
      client_reference_arg: v.client_reference_arg || null, idempotency_arg: v.idempotency_arg || null,
      status_tool: v.status_tool || null, integration_id: v.integration_id || null });
  }

  // =====================================================================================================================
  // 2. Agent
  // =====================================================================================================================
  const ROLE = { leader: 'Trưởng nhóm (leader)', specialist: 'Chuyên viên (specialist)' };
  const PSTATUS = { draft: ['bản nháp', 'warn'], published: ['đang phát hành', 'ok'], retired: ['đã thay thế', ''] };
  const pbadge = (s) => badge((PSTATUS[s] || [s])[0], (PSTATUS[s] || [])[1]);

  async function agentsScreen(parts) {
    if (parts[0]) return agentDetail(parts[0], parts[1]);
    const { profiles } = await call('profiles');
    const byKey = new Map();
    for (const p of profiles) byKey.set(p.key, [...(byKey.get(p.key) || []), p]);
    const agents = [...byKey.entries()].map(([key, versions]) => {
      const newest = versions.reduce((a, b) => (b.version > a.version ? b : a));
      return { key, newest, live: versions.find((v) => v.status === 'published'), count: versions.length };
    });
    const admin = state.me.role === 'admin';
    return [
      pageHead('Agent', admin ? 'Hồ sơ agent của tenant: phiên bản, đánh giá, phát hành.' : 'Các agent mà route của ban quản lý này dùng.',
        admin ? [link(['builder'], 'Tạo agent qua chat', 'btn')] : null),
      panel('Danh sách agent', agents.length + ' agent', null, table([
        { title: 'Agent', cell: (a) => [link(['agents', a.key], a.newest.profile.name), h('div', { class: 'mono muted', text: a.key })] },
        { title: 'Vai trò', cell: (a) => ROLE[a.newest.profile.role] || a.newest.profile.role },
        { title: 'Đang phát hành', cell: (a) => (a.live ? 'v' + a.live.version : h('span', { class: 'muted', text: 'chưa có' })) },
        { title: 'Bản mới nhất', cell: (a) => ['v' + a.newest.version + ' ', pbadge(a.newest.status)] },
        { title: 'Số phiên bản', cls: 'num', cell: (a) => a.count },
        { title: '', cls: 'actions', cell: (a) => link(['agents', a.key], 'Mở', 'btn sm') },
      ], agents, admin ? 'Chưa có agent nào. Bấm “Tạo agent qua chat” để bắt đầu.' : 'Route của ban quản lý này chưa dùng agent nào.')),
    ];
  }

  async function agentDetail(key, picked) {
    const { profiles } = await call('profiles');
    const versions = profiles.filter((p) => p.key === key).sort((a, b) => b.version - a.version);
    if (!versions.length) throw new ApiError(404, { detail: 'no such profile' });
    const rec = versions.find((v) => String(v.version) === picked) || versions[0];
    const p = rec.profile;
    const admin = state.me.role === 'admin';
    const gateBox = h('div');
    const runsBox = h('div');
    const casesBox = h('div');
    const historyBox = h('div');
    const publishBtn = h('button', { type: 'button', class: 'primary', text: 'Phát hành v' + rec.version, disabled: true });

    const publish = async (reason) => {
      const out = await call('publish', [key, rec.version], reason ? { body: { override_reason: reason } } : undefined);
      toast('Đã phát hành ' + key + ' v' + out.version);
      if (out.warnings && out.warnings.length) state.keep.warnings = out.warnings;
      again();
    };
    publishBtn.addEventListener('click', async () => {
      publishBtn.disabled = true;
      try { await publish(); } catch (e) { fail(e); load(gateBox, gate); }
    });
    async function gate() {
      if (rec.status !== 'draft') return null;
      const g = await call('gate', [key, rec.version]);
      publishBtn.disabled = !g.publishable;
      publishBtn.title = g.publishable ? '' : g.refusal.message;
      return g.publishable
        ? note('ok', 'Bản nháp này đã qua cổng đánh giá: có thể phát hành.')
        : note('warn', 'Chưa phát hành được (cổng đánh giá từ chối)', h('div', { text: g.refusal.code + ': ' + g.refusal.message }),
          g.refusal.latest_run ? h('div', { class: 'small', text: 'Lần đánh giá gần nhất: ' + g.refusal.latest_run.status + ' lúc ' + when(g.refusal.latest_run.created_at) }) : null);
    }

    const runEval = act('Chạy đánh giá', async () => {
      await call('evalRun', [key, rec.version], { body: { wait_seconds: 20 } });
      load(runsBox, runs);
      load(gateBox, gate);
      load(historyBox, history);
    }, '');
    async function runs() {
      const { runs: list } = await call('evalRuns', [key, rec.version]);
      if (!list.length) return h('div', { class: 'empty', text: 'Phiên bản này chưa được đánh giá lần nào.' });
      const latest = list[0];
      if (latest.status === 'running') {
        const seq = state.seq;
        setTimeout(() => { if (state.seq === seq) { load(runsBox, runs); load(gateBox, gate); } }, 3000);
      }
      const passed = latest.results.filter((r) => r.passed).length;
      return [
        h('div', { class: 'panel-body' }, kv([
          ['Lần chạy gần nhất', [mono(latest.run_id), ' ', badge(latest.status)]],
          ['Kết quả', latest.status === 'running' ? 'Đang chạy: ' + latest.results.length + ' ca đã xong…' : passed + ' / ' + latest.results.length + ' ca đạt'],
          ['Chi phí', usd(latest.cost_usd)], ['Thời gian', latest.duration_s == null ? '—' : latest.duration_s.toFixed(1) + ' giây'],
          ['Người chạy', latest.started_by], ['Bắt đầu', when(latest.created_at)],
          latest.error ? ['Lỗi', h('span', { class: 'err', text: latest.error })] : null].filter(Boolean))),
        table([
          { title: 'Ca', cell: (r) => [h('strong', { text: r.name }), r.platform ? h('div', { class: 'muted small', text: 'ca của platform' }) : null] },
          { title: 'Kết quả', cell: (r) => badge(r.passed ? 'đạt' : 'trượt', r.passed ? 'ok' : 'bad') },
          { title: 'Từng kiểm tra', cls: 'wrap', cell: (r) => (r.error ? h('span', { class: 'err', text: r.error })
            : (r.checks || []).map((c) => h('div', null, badge(c.ok ? 'đạt' : 'trượt', c.ok ? 'ok' : 'bad'), ' ', mono(c.check), c.detail ? ' — ' + c.detail : ''))) },
          { title: 'Trạng thái cuối', cell: (r) => dash(r.state) },
          { title: 'Chi phí', cls: 'num', cell: (r) => usd(r.cost_usd) },
        ], latest.results, latest.status === 'running' ? 'Chưa ca nào chạy xong.' : 'Lần chạy này không có ca nào.'),
        list.length > 1 ? h('div', { class: 'panel-body' }, h('details', null, h('summary', { text: 'Các lần chạy trước (' + (list.length - 1) + ')' }),
          table([
            { title: 'Lần chạy', cell: (r) => mono(r.run_id) }, { title: 'Trạng thái', cell: (r) => badge(r.status) },
            { title: 'Điểm', cls: 'num', cell: (r) => (r.score == null ? '—' : Math.round(r.score * 100) + '%') },
            { title: 'Chi phí', cls: 'num', cell: (r) => usd(r.cost_usd) }, { title: 'Bắt đầu', cell: (r) => when(r.created_at) },
          ], list.slice(1), ''))) : null,
      ];
    }

    const caseFields = (c) => [
      { name: 'name', label: 'Tên ca', required: true, maxLength: 120, value: c && c.name },
      { name: 'input', label: 'Đầu vào (tin nhắn của cư dân, hoặc nhiệm vụ leader giao)', type: 'textarea', required: true, rows: 3, value: c && c.input },
      { name: 'fixtures', label: 'Kết quả tool giả lập (JSON: tên tool → câu trả lời)', type: 'json', object: true, rows: 4,
        value: c && Object.keys(c.fixtures || {}).length ? json(c.fixtures) : '', placeholder: '{"lookup_ticket": "T-1001: đang chờ thợ"}',
        hint: 'Không gọi MCP thật của đối tác. Tool không có ở đây thì agent không có tool đó trong sandbox.' },
      { name: 'must_call', label: 'Phải gọi tool (mỗi dòng một tool)', type: 'calls', rows: 2, value: callsText(c, 'must_call'),
        hint: 'Mỗi dòng là tên tool, hoặc JSON {"tool": "...", "args": {...}}.' },
      { name: 'must_not_call', label: 'Không được gọi tool', type: 'calls', rows: 2, value: callsText(c, 'must_not_call') },
      { name: 'must_contain', label: 'Câu trả lời phải chứa (mỗi dòng một cụm)', type: 'textarea', rows: 2, value: c && (c.checks.must_contain || []).join('\n') },
      { name: 'must_not_contain', label: 'Câu trả lời không được chứa', type: 'textarea', rows: 2, value: c && (c.checks.must_not_contain || []).join('\n') },
      { name: 'grounded', label: 'Không con số nào ngoài bằng chứng (grounded)', type: 'checkbox', value: c && c.checks.grounded },
      { name: 'must_record_gap', label: 'Phải nói rõ điều chưa biết (must_record_gap)', type: 'checkbox', value: c && c.checks.must_record_gap },
      { name: 'expected_state', label: 'Trạng thái workflow mong đợi (với leader)', value: c && (c.checks.expected_state || []).join(', '), placeholder: 'awaiting_user, closed' },
      { name: 'max_cost_usd', label: 'Chi phí tối đa (USD)', type: 'number', min: 0, value: c && c.checks.max_cost_usd },
    ];
    const caseBody = (v) => ({ name: v.name, input: v.input, fixtures: v.fixtures || {}, checks: {
      must_call: v.must_call, must_not_call: v.must_not_call, must_contain: rows(v.must_contain), must_not_contain: rows(v.must_not_contain),
      grounded: v.grounded, must_record_gap: v.must_record_gap, expected_state: lines(v.expected_state),
      ...(v.max_cost_usd == null ? {} : { max_cost_usd: v.max_cost_usd }) } });
    const afterCase = (text) => { toast(text); load(casesBox, cases); load(gateBox, gate); };
    const editCase = (c) => formDialog(c ? 'Sửa ca đánh giá' : 'Thêm ca đánh giá', caseFields(c), {
      submit: c ? 'Lưu ca' : 'Thêm ca',
      onSubmit: async (v) => {
        await (c ? call('evalCaseSet', [key, c.id], { body: caseBody(v) }) : call('evalCaseAdd', [key], { body: caseBody(v) }));
        afterCase(c ? 'Đã lưu ca đánh giá.' : 'Đã thêm ca đánh giá. Phải chạy lại đánh giá trước khi phát hành.');
      },
    }, null, true);
    async function cases() {
      const { cases: list } = await call('evalCases', [key]);
      return table([
        { title: 'Ca', cell: (c) => [h('strong', { text: c.name }), h('div', { class: 'muted small', text: c.platform ? 'của platform (chỉ đọc)' : 'của tenant' })] },
        { title: 'Đầu vào', cls: 'wrap', cell: (c) => c.input },
        { title: 'Tool giả lập', cell: (c) => chips(Object.keys(c.fixtures || {})) },
        { title: 'Kiểm tra', cls: 'wrap', cell: (c) => chips(checkNames(c.checks)) },
        { title: '', cls: 'actions', cell: (c) => (c.platform ? '' : [
          h('button', { class: 'sm', type: 'button', text: 'Sửa', onclick: () => editCase(c) }),
          h('button', { class: 'sm danger', type: 'button', text: 'Xóa', onclick: () => confirm('Xóa ca đánh giá', 'Xóa ca “' + c.name + '”? Kết quả đánh giá cũ không còn dùng để phát hành được.', 'Xóa ca',
            async () => { await call('evalCaseDrop', [key, c.id]); afterCase('Đã xóa ca đánh giá.'); }, true) })]) },
      ], list, 'Chưa có ca nào.');
    }
    async function history() {
      const { events } = await call('history', [key]);
      return table([
        { title: 'Khi nào', cell: (e) => when(e.at) }, { title: 'Việc', cell: (e) => badge(e.kind, e.kind === 'override' ? 'warn' : 'info') },
        { title: 'Phiên bản', cell: (e) => (e.version == null ? '—' : 'v' + e.version) }, { title: 'Ai', cell: (e) => mono(e.actor) },
        { title: 'Chi tiết', cls: 'wrap', cell: (e) => (e.detail && Object.keys(e.detail).length ? mono(JSON.stringify(e.detail)) : '—') },
      ], [...events].reverse(), 'Chưa có lịch sử.');
    }

    const override = () => formDialog('Phát hành không qua đánh giá', [
      { name: 'reason', label: 'Lý do ghi đè', type: 'textarea', required: true, maxLength: 300, rows: 3, hint: 'Được ghi vào lịch sử cùng khóa admin đã dùng.' },
    ], { submit: 'Phát hành v' + rec.version, danger: true, onSubmit: (v) => publish(v.reason) },
    note('warn', 'Bỏ qua cổng đánh giá', h('div', { text: 'Phiên bản này sẽ phục vụ cư dân mà chưa có lần đánh giá đạt. Chỉ dùng khi có lý do rõ ràng.' })));
    const rollback = () => confirm('Rollback về v' + rec.version, 'Đưa v' + rec.version + ' của ' + key + ' trở lại làm bản đang phát hành? Bản hiện tại sẽ thành đã thay thế. Workflow đang chạy giữ leader nó đã bắt đầu.',
      'Rollback về v' + rec.version, async () => { await call('rollback', [key], { body: { to_version: rec.version } }); toast('Đã rollback ' + key + ' về v' + rec.version); again(); });

    const warnings = state.keep.warnings;
    state.keep.warnings = null;
    load(gateBox, gate);
    load(runsBox, runs);
    load(casesBox, cases);
    load(historyBox, history);
    return [
      h('div', { class: 'crumb' }, link(['agents'], 'Agent'), ' / ', key),
      pageHead(p.name, key + ' · ' + (ROLE[p.role] || p.role)),
      warnings ? note('warn', 'Đã phát hành, có cảnh báo', h('ul', null, warnings.map((w) => h('li', { text: w })))) : null,
      panel('Phiên bản', versions.length + ' phiên bản', null, table([
        { title: 'Phiên bản', cell: (v) => link(['agents', key, String(v.version)], 'v' + v.version) },
        { title: 'Trạng thái', cell: (v) => pbadge(v.status) }, { title: 'Tạo lúc', cell: (v) => when(v.created_at) },
        { title: 'Phát hành lúc', cell: (v) => when(v.published_at) }, { title: 'Người phát hành', cell: (v) => mono(dash(v.published_by)) },
        { title: '', cls: 'actions', cell: (v) => (v.version === rec.version ? h('span', { class: 'muted', text: 'đang xem' }) : link(['agents', key, String(v.version)], 'Xem', 'btn sm')) },
      ], versions, '', (v) => (v.version === rec.version ? 'picked' : ''))),
      h('div', { class: 'grid2' },
        panel('Hồ sơ v' + rec.version, null, [pbadge(rec.status)], kv([
          ['Nhiệm vụ', p.mission], ['Nhận việc', chips(p.handles)], ['Từ chối', chips(p.refuses)], ['Tool được cấp', chips(p.tools_allow)],
          ['Nhóm (team)', chips(p.team)], ['Tầng model', mono(p.model_tier)], ['Khi nào chuyển cho người', chips(p.escalate_when)],
          ['Chỉ dẫn', p.instructions ? h('details', null, h('summary', { text: 'Xem chỉ dẫn' }), h('pre', { text: p.instructions })) : '—'],
        ]), false),
        panel('Đánh giá và phát hành v' + rec.version, null, null, h('div', { class: 'stack' },
          rec.status === 'retired' ? note('info', 'Phiên bản đã thay thế', h('div', { text: 'Bản này từng được phát hành. Rollback đưa nó trở lại mà không cần đánh giá lại.' })) : null,
          rec.status === 'published' ? note('ok', 'Đang phát hành', h('div', { text: 'Đây là bản đang phục vụ. Có thể chạy đánh giá lại để kiểm tra.' })) : null,
          gateBox,
          h('div', { class: 'row' },
            rec.status !== 'retired' ? runEval : null,
            rec.status === 'draft' ? publishBtn : null,
            rec.status === 'draft' && admin ? h('button', { type: 'button', class: 'danger', text: 'Phát hành không qua đánh giá…', onclick: override }) : null,
            rec.status === 'retired' ? h('button', { type: 'button', class: 'primary', text: 'Rollback về v' + rec.version, onclick: rollback }) : null)), false)),
      panel('Kết quả đánh giá của v' + rec.version, 'từng ca, từng kiểm tra', null, runsBox),
      panel('Ca đánh giá', 'ca của platform và ca riêng của agent này', [h('button', { type: 'button', text: 'Thêm ca', onclick: () => editCase(null) })], casesBox),
      panel('Lịch sử', 'tạo, đánh giá, phát hành, ghi đè, rollback', null, historyBox),
    ];
  }
  const callsText = (c, name) => (c ? (c.checks[name] || []).map((x) => (typeof x === 'string' ? x : JSON.stringify(x))).join('\n') : '');
  const checkNames = (checks) => Object.entries(checks || {}).filter(([, v]) => (Array.isArray(v) ? v.length : v !== false && v != null)).map(([k]) => k);

  // ---- the builder: a chat that ends in drafts ---------------------------------------------------------------------------
  const ACTION = { create: ['Tạo mới', 'ok'], reuse: ['Dùng lại agent đã có', 'info'], revise: ['Sửa agent đã có', 'warn'], clarify: ['Cần làm rõ', ''] };

  async function builderScreen() {
    let session = null;
    const sid = store.get(BUILDER);
    if (sid) {
      try { session = await call('builderGet', [sid]); } catch (e) {
        if (e.status !== 404) throw e;
        store.drop(BUILDER);
      }
    }
    const chat = h('div', { class: 'chat' });
    const proposals = h('div', { class: 'panel-body' });
    let outcome = {};  // proposal index -> what the last apply said of it; a new message brings new proposals

    const apply = async (p, reason) => {
      const out = await call('builderApply', [session.session_id], { body: { items: [reason ? { index: p.index, override_reason: reason } : { index: p.index }] } });
      outcome[p.index] = out.results[0];
      if (out.results[0].created) toast('Đã tạo bản nháp ' + out.results[0].key + ' v' + out.results[0].version);
      session = await call('builderGet', [session.session_id]);
      draw();
    };
    function card(p) {
      const [label, tone] = ACTION[p.action] || [p.action, ''];
      const done = p.applied || (outcome[p.index] && outcome[p.index].created ? outcome[p.index] : null);
      const said = outcome[p.index];
      const prof = p.profile;
      const reason = h('input', { type: 'text', maxLength: 300, placeholder: 'Lý do vẫn tạo agent mới', 'aria-label': 'Lý do vẫn tạo agent mới' });
      const reasonErr = h('div', { class: 'err', role: 'alert' });
      return h('div', { class: 'proposal' },
        h('h3', null, badge(label, tone), prof ? [prof.name, ' ', mono(prof.key)] : null),
        h('div', { class: 'stack' },
          p.gated ? note('warn', 'Platform đã đổi đề xuất này thành “dùng lại”', h('div', { text: 'Agent được đề xuất trùng nghiệp vụ với agent đã có. Muốn vẫn tạo thì phải ghi lý do.' })) : null,
          (p.overlap || []).length ? note('warn', 'Cảnh báo trùng nghiệp vụ', h('ul', null, p.overlap.map((o) => h('li', null,
            'Trùng với ', link(['agents', o.key], o.key), ': điểm ' + o.score, (o.shared || []).length ? ' (từ chung: ' + o.shared.join(', ') + ')' : '')))) : null,
          (p.advised_overlap || []).length ? h('div', { class: 'small muted', text: 'Model cho rằng có trùng với: ' + p.advised_overlap.join(', ') }) : null,
          (p.overlap_with || []).length ? h('div', null, 'Dùng lại: ', p.overlap_with.map((k) => [link(['agents', k], k), ' '])) : null,
          p.question ? note('info', 'Builder hỏi lại', h('div', { text: p.question })) : null,
          prof ? kv([['Vai trò', ROLE[prof.role] || prof.role], ['Nhiệm vụ', prof.mission], ['Nhận việc', chips(prof.handles)], ['Từ chối', chips(prof.refuses)],
            ['Tool được cấp', chips(prof.tools_allow)], ['Nhóm (team)', chips(prof.team)], ['Tầng model', mono(prof.model_tier)]]) : null,
          p.reason ? h('div', null, h('strong', { text: 'Lý do: ' }), p.reason) : null,
          (p.notes || []).length ? note('info', 'Ghi chú của platform', h('ul', null, p.notes.map((n) => h('li', { text: n })))) : null,
          said && said.error ? note('error', 'Không áp dụng được', h('div', { text: said.error })) : null,
          said && !said.created && !said.error && said.action === 'reuse' ? note('info', 'Không tạo gì mới', h('div', { text: 'Dùng lại agent ' + said.key + '.' })) : null,
          done ? note('ok', 'Đã tạo bản nháp', h('div', null, link(['agents', done.key, String(done.version)], done.key + ' v' + done.version),
            '. Bản nháp chưa phục vụ ai: phải đánh giá rồi phát hành.')) : null,
          done || p.action === 'clarify' ? null : (p.action === 'reuse'
            ? (prof ? h('div', { class: 'stack' }, reason, reasonErr, act('Vẫn tạo bản nháp (ghi lý do)', async () => {
              reasonErr.textContent = reason.value.trim() ? '' : 'Phải ghi lý do.';
              if (reason.value.trim()) await apply(p, reason.value.trim());
            }, 'danger')) : null)
            : act('Áp dụng: tạo bản nháp', () => apply(p), 'primary'))));
    }
    function draw() {
      const messages = session ? session.messages : [];
      chat.replaceChildren(...(messages.length ? messages.map((m) => h('div', { class: 'msg ' + (m.role === 'admin' ? 'admin' : 'builder') },
        m.text || (m.role === 'admin' ? '' : '(không có lời nào, xem đề xuất bên cạnh)'), h('span', { class: 'when', text: when(m.at) })))
        : [h('div', { class: 'empty', text: 'Hãy tả công việc cần một agent làm, ví dụ: “Cần một agent đặt chỗ gửi xe cho khách của cư dân”.' })]));
      chat.scrollTop = chat.scrollHeight;
      const list = session ? session.proposals : [];
      proposals.replaceChildren(...(list.length ? list.map(card) : [h('div', { class: 'empty', text: 'Chưa có đề xuất nào.' })]));
    }
    const say = form([{ name: 'text', label: 'Tin nhắn cho builder', type: 'textarea', required: true, rows: 3, maxLength: 4000 }], {
      submit: 'Gửi',
      onSubmit: async (v) => {
        if (!session) {
          session = await call('builderNew');
          store.set(BUILDER, session.session_id);
        }
        chat.append(h('div', { class: 'msg admin', text: v.text }), h('div', { class: 'loading', text: 'Builder đang soạn đề xuất…' }));
        chat.scrollTop = chat.scrollHeight;
        try {
          session = await call('builderSay', [session.session_id], { body: { text: v.text } });
          outcome = {};
        } finally { draw(); }
        say.querySelector('textarea').value = '';
      },
    });
    draw();
    return [
      h('div', { class: 'crumb' }, link(['agents'], 'Agent'), ' / Tạo agent qua chat'),
      pageHead('Tạo agent qua chat', 'Builder chỉ đề xuất. Áp dụng chỉ tạo bản nháp; phát hành luôn là việc của người, sau khi đánh giá.',
        [h('button', { type: 'button', text: 'Phiên mới', onclick: () => { store.drop(BUILDER); again(); } })]),
      h('div', { class: 'grid2' },
        panel('Trò chuyện', session ? session.session_id : 'phiên mới', null, [chat, h('div', { class: 'panel-body' }, say)]),
        panel('Đề xuất hiện tại', 'kèm cảnh báo trùng với agent đã có', null, proposals, false)),
    ];
  }

  // =====================================================================================================================
  // 3. Đối tác
  // =====================================================================================================================
  const CUSTOMER_OPS = ['submit_request', 'reply', 'read_result', 'receive_events', 'submit_consent', 'close_workflow', 'confirm_route', 'sync_residence'];
  const SCHEMA_SAMPLE = {
    version: '1', version_mode: 'snapshot',
    events: {
      'job.assigned': { status: 'assigned', rank: 10, public_status: 'assigned', public_fields: ['worker_name'], message: 'Nhân viên {worker_name} đang trên đường tới.' },
      'job.completed': { status: 'completed', rank: 90, terminal: true, outcome: 'completed', public_status: 'completed', wake: true, evidence: true },
    },
  };
  const expiry = (v) => (v ? new Date(v).toISOString() : undefined);
  const future = (v) => (v && !(new Date(v) > new Date()) ? 'Phải là một thời điểm trong tương lai.' : null);

  async function partnersScreen(parts) {
    const { clients } = await call('clients');
    const client = clients.find((c) => c.client_id === parts[0]);
    const body = h('div');
    if (client) load(body, () => clientDetail(client));
    const addClient = () => formDialog('Thêm client (đối tác)', [
      { name: 'name', label: 'Tên đối tác', required: true, maxLength: 120 },
      { name: 'domain', label: 'Lĩnh vực (domain)', required: true, placeholder: 'homes', pattern: /^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$/, patternMsg: 'Chữ, số, gạch dưới, chấm, gạch nối; bắt đầu bằng chữ hoặc số.' },
      { name: 'environment', label: 'Môi trường', type: 'select', options: [['sandbox', 'sandbox'], ['production', 'production']],
        hint: 'Hai môi trường là hai client khác nhau; khóa không dùng chéo.' },
    ], { submit: 'Tạo client', onSubmit: async (v) => {
      const made = await call('clientAdd', [], { body: v });
      toast('Đã tạo client ' + made.name);
      location.hash = '#/partners/' + encodeURIComponent(made.client_id);  // the new client opens (hashchange renders)
    } });
    return [
      pageHead('Đối tác', 'Client, khóa, tài khoản ban quản lý, route và tích hợp sự kiện.',
        [h('button', { class: 'primary', type: 'button', text: 'Thêm client', onclick: addClient })]),
      panel('Client', clients.length + ' client', null, table([
        { title: 'Đối tác', cell: (c) => [link(['partners', c.client_id], c.name), h('div', { class: 'mono muted', text: c.client_id })] },
        { title: 'Lĩnh vực', cell: (c) => c.domain }, { title: 'Môi trường', cell: (c) => badge(c.environment, c.environment === 'production' ? 'info' : '') },
        { title: 'Trạng thái', cell: (c) => badge(c.status) }, { title: 'Tạo lúc', cell: (c) => when(c.created_at) },
        { title: '', cls: 'actions', cell: (c) => (client && c.client_id === client.client_id ? h('span', { class: 'muted', text: 'đang xem' }) : link(['partners', c.client_id], 'Mở', 'btn sm')) },
      ], clients, 'Chưa có client nào. Mỗi đối tác (và mỗi môi trường của họ) là một client.', (c) => (client && c.client_id === client.client_id ? 'picked' : ''))),
      parts[0] && !client ? note('error', 'Không tìm thấy client ' + parts[0]) : null,
      client ? body : h('div', { class: 'panel' }, h('div', { class: 'empty', text: 'Chọn một client để xem khóa, manager, route và integration của nó.' })),
    ];
  }

  function confirmText(route) {
    return 'POST ' + location.origin + '/workforce/v1/partner/routes/' + route.route_id + '/confirm\n'
      + 'Authorization: ApiKey <khóa dp_... của đối tác>\nContent-Type: application/json\n\n'
      + JSON.stringify({ schema_version: '1', expected_revision: route.revision, external_management_ref: route.external_management_ref }, null, 2);
  }
  function sendToPartner(route) {
    const text = confirmText(route);
    const b = h('button', { type: 'button', text: 'Chép nội dung' });
    b.addEventListener('click', () => copy(text, b));
    dialog('Gửi đối tác để xác nhận route', [
      note('info', 'Route đang chờ xác nhận (pending) và chưa nhận tin nhắn', h('div', { text: 'Đối tác gọi lệnh dưới đây bằng chính khóa của họ. Lệnh này chứng minh khóa và route khớp nhau; sau đó route thành active.' })),
      kv([['route_id', mono(route.route_id)], ['external_management_ref', mono(route.external_management_ref)], ['expected_revision', mono(route.revision)]]),
      h('pre', { text }), h('div', { class: 'form-foot' }, b)], true);
  }

  async function clientDetail(client) {
    const cid = client.client_id;
    const q = { query: { client_id: cid } };
    const [{ keys }, { managers }, { routes }, { integrations }, { profiles }] = await Promise.all([
      call('keys', [cid]), call('managers', [], q), call('routes', [], q), call('integrations', [], q), call('profiles')]);
    const leaders = [...new Set(profiles.filter((p) => p.profile.role === 'leader').map((p) => p.key))];
    const managerName = (id) => (managers.find((m) => m.manager_id === id) || {}).name || id;
    const secretOf = (title, k) => showSecret(title, [['Khóa API (api_key)', k.api_key],
      ['Mã khóa ký (key_id)', k.signing_key && k.signing_key.key_id], ['Bí mật ký (secret)', k.signing_key && k.signing_key.secret]]);

    // ---- partner keys
    const addKey = () => formDialog('Tạo khóa đối tác', [
      { name: 'operations', label: 'Quyền (operations)', type: 'checks', required: true, value: CUSTOMER_OPS, options: CUSTOMER_OPS.map((o) => [o, o]) },
      { name: 'routes', label: 'Route được dùng', value: '*', required: true, hint: '* là mọi route của client; hoặc danh sách route_id cách nhau bằng dấu phẩy.' },
      { name: 'expires_at', label: 'Hết hạn (để trống: không hết hạn)', type: 'datetime-local' },
    ], { submit: 'Tạo khóa', check: (v) => (future(v.expires_at) ? { expires_at: future(v.expires_at) } : null), onSubmit: async (v) => {
      const made = await call('keyAdd', [cid], { body: { operations: v.operations, routes: lines(v.routes), expires_at: expiry(v.expires_at) } });
      again();
      secretOf('Khóa đối tác mới', made);
    } });
    const keyTable = (list, empty) => table([
      { title: 'Khóa', cell: (k) => mono(k.key_id) }, { title: 'Loại', cell: (k) => k.kind },
      { title: 'Quyền', cls: 'wrap', cell: (k) => chips(k.operations) }, { title: 'Route', cell: (k) => chips(k.routes) },
      { title: 'Trạng thái', cell: (k) => badge(k.status) }, { title: 'Hết hạn', cell: (k) => when(k.expires_at) }, { title: 'Tạo lúc', cell: (k) => when(k.created_at) },
      { title: '', cls: 'actions', cell: (k) => (k.status !== 'active' ? '' : [
        h('button', { class: 'sm', type: 'button', text: 'Xoay khóa', onclick: () => confirm('Xoay khóa', 'Khóa ' + k.key_id + ' bị thu hồi ngay và một khóa mới cùng quyền được cấp. Đối tác phải đổi sang khóa mới.', 'Xoay khóa',
          async () => { const made = await call('keyRotate', [k.key_id]); again(); secretOf('Khóa mới thay cho ' + k.key_id, made); }) }),
        h('button', { class: 'sm danger', type: 'button', text: 'Thu hồi', onclick: () => confirm('Thu hồi khóa', 'Khóa ' + k.key_id + ' ngừng hoạt động ngay và không khôi phục được.', 'Thu hồi',
          async () => { await call('keyRevoke', [k.key_id]); toast('Đã thu hồi khóa ' + k.key_id); again(); }, true) })]) },
    ], list, empty);

    // ---- managers
    const addManager = () => formDialog('Thêm tài khoản ban quản lý', [{ name: 'name', label: 'Tên ban quản lý', required: true, maxLength: 120 }],
      { submit: 'Tạo manager', onSubmit: async (v) => { await call('managerAdd', [cid], { body: v }); toast('Đã tạo manager ' + v.name); again(); } });
    const managerKeys = async (m) => {
      const box = h('div');
      const d = dialog('Khóa vận hành của ' + m.name, box, true);
      const draw = () => load(box, async () => {
        const { keys: list } = await call('managerKeys', [m.manager_id]);
        return table([
          { title: 'Khóa', cell: (k) => mono(k.key_id) }, { title: 'Trạng thái', cell: (k) => badge(k.status) },
          { title: 'Hết hạn', cell: (k) => when(k.expires_at) }, { title: 'Tạo lúc', cell: (k) => when(k.created_at) }, { title: 'Thu hồi lúc', cell: (k) => when(k.revoked_at) },
          { title: '', cls: 'actions', cell: (k) => (k.status !== 'active' ? '' : h('button', { class: 'sm danger', type: 'button', text: 'Thu hồi', onclick: async (ev) => {
            ev.target.disabled = true;
            try { await call('managerKeyRevoke', [m.manager_id, k.key_id]); draw(); } catch (e) { d.close(); fail(e); }
          } })) },
        ], list, 'Manager này chưa có khóa vận hành nào.');
      });
      draw();
    };
    const managerTable = table([
      { title: 'Ban quản lý', cell: (m) => [h('strong', { text: m.name }), h('div', { class: 'mono muted', text: m.manager_id })] },
      { title: 'Trạng thái', cell: (m) => badge(m.status) }, { title: 'Số route', cls: 'num', cell: (m) => routes.filter((r) => r.manager_id === m.manager_id && r.status !== 'replaced').length },
      { title: 'Tạo lúc', cell: (m) => when(m.created_at) },
      { title: '', cls: 'actions', cell: (m) => [
        m.status === 'active' ? act('Cấp khóa vận hành', async () => { const made = await call('managerKeyAdd', [m.manager_id]); secretOf('Khóa vận hành của ' + m.name, made); }) : null,
        h('button', { class: 'sm', type: 'button', text: 'Xem khóa', onclick: () => managerKeys(m) }),
        m.status === 'active'
          ? h('button', { class: 'sm danger', type: 'button', text: 'Tắt', onclick: () => confirm('Tắt tài khoản ban quản lý', 'Mọi khóa của ' + m.name + ' ngừng hoạt động ngay. Route và workflow của họ vẫn chạy; admin vẫn vận hành được.', 'Tắt tài khoản',
            async () => { await call('managerDisable', [m.manager_id]); toast('Đã tắt ' + m.name); again(); }, true) })
          : act('Bật lại', async () => { await call('managerEnable', [m.manager_id]); toast('Đã bật ' + m.name); again(); })] },
    ], managers, 'Chưa có tài khoản ban quản lý nào. Mỗi route thuộc đúng một manager.');

    // ---- routes
    const leaderOptions = (first) => [...first, ...leaders.map((k) => [k, k])];
    const addRoute = () => formDialog('Tạo route', [
      { name: 'external_management_ref', label: 'Mã văn phòng phía đối tác (external_management_ref)', required: true, maxLength: 128, placeholder: 'BQL-OP1-A' },
      { name: 'manager_id', label: 'Thuộc ban quản lý', type: 'select', options: managers.filter((m) => m.status === 'active').map((m) => [m.manager_id, m.name]) },
      { name: 'leader_profile', label: 'Agent leader', type: 'select', options: leaderOptions([]) },
      { name: 'ticket_binding_mode', label: 'Gắn ticket', type: 'select', options: [['required', 'required: mỗi workflow gắn một ticket'], ['none', 'none: không cần ticket']] },
      { name: 'residence_required', label: 'Bắt buộc đồng bộ cư dân trước (residence_required)', type: 'checkbox' },
      { name: 'timezone', label: 'Múi giờ (IANA)', value: 'Asia/Ho_Chi_Minh', required: true },
      { name: 'safe_reply', label: 'Câu trả lời an toàn', maxLength: 1000, value: 'Ban quản lý sẽ liên hệ lại với bạn.', hint: 'Gửi cư dân khi leader không nói được điều có căn cứ.' },
    ], { submit: 'Tạo route', onSubmit: async (v) => {
      const made = await call('routeAdd', [cid], { body: { external_management_ref: v.external_management_ref, manager_id: v.manager_id, leader_profile: v.leader_profile,
        config: { ticket_binding_mode: v.ticket_binding_mode, residence_required: v.residence_required, timezone: v.timezone, rules: { safe_reply: v.safe_reply } } } });
      again();
      sendToPartner(made);
    } }, null, true);
    const needs = !managers.some((m) => m.status === 'active') ? 'Cần một manager đang hoạt động trước khi tạo route.'
      : (!leaders.length ? 'Cần một hồ sơ agent leader trước khi tạo route (màn hình Agent).' : null);
    const replace = (r) => formDialog('Thay route ' + r.external_management_ref, [
      { name: 'external_management_ref', label: 'Mã văn phòng mới (để trống: giữ nguyên)', maxLength: 128 },
      { name: 'leader_profile', label: 'Agent leader', type: 'select', options: leaderOptions([['', '(giữ nguyên: ' + r.leader_profile + ')']]) },
    ], { submit: 'Thay route', danger: true, onSubmit: async (v) => {
      const body = {};
      if (v.external_management_ref) body.external_management_ref = v.external_management_ref;
      if (v.leader_profile) body.leader_profile = v.leader_profile;
      const out = await call('routeReplace', [r.route_id], { body });
      again();
      sendToPartner(out.route);
    } }, note('warn', 'Route cũ thành replaced', h('div', { text: 'Workflow cũ giữ route cũ và chuyển sang blocked_route_changed. Route mới ở trạng thái pending, thuộc cùng manager, mang theo bản sao kho tool, và phải được đối tác xác nhận lại.' })));
    const routeTable = table([
      { title: 'Văn phòng', cell: (r) => [h('strong', { text: r.external_management_ref }), h('div', { class: 'mono muted', text: r.route_id })] },
      { title: 'Trạng thái', cell: (r) => badge(r.status) }, { title: 'Revision', cls: 'num', cell: (r) => r.revision },
      { title: 'Leader', cell: (r) => link(['agents', r.leader_profile], r.leader_profile) }, { title: 'Ban quản lý', cell: (r) => managerName(r.manager_id) },
      { title: '', cls: 'actions', cell: (r) => [
        r.status === 'pending' ? h('button', { class: 'sm primary', type: 'button', text: 'Gửi đối tác', onclick: () => sendToPartner(r) }) : null,
        link(['tools', r.route_id], 'Kho tool', 'btn sm'),
        r.status === 'replaced' || r.status === 'suspended' ? null : h('button', { class: 'sm danger', type: 'button', text: 'Tạm dừng', onclick: () => confirm('Tạm dừng route',
          'Route ' + r.external_management_ref + ' ngừng nhận yêu cầu của đối tác cho tới khi được thay bằng route mới.', 'Tạm dừng',
          async () => { await call('routeSuspend', [r.route_id]); toast('Đã tạm dừng route ' + r.external_management_ref); again(); }, true) }),
        r.status === 'replaced' ? null : h('button', { class: 'sm', type: 'button', text: 'Thay route', onclick: () => replace(r) })] },
    ], routes, 'Chưa có route nào. Một route nối một văn phòng của đối tác với một agent leader.');

    // ---- integrations
    const addIntegration = () => formDialog('Thêm integration', [
      { name: 'event_schema', label: 'Schema sự kiện (JSON)', type: 'json', object: true, required: true, rows: 14, value: json(SCHEMA_SAMPLE),
        hint: 'Mỗi loại sự kiện: status, rank (cao hơn là tiến xa hơn), terminal + outcome, public_fields, message, wake.' },
    ], { submit: 'Tạo integration', onSubmit: async (v) => { const made = await call('integrationAdd', [cid], { body: v }); toast('Đã tạo ' + made.integration_id); again(); } },
    h('p', { class: 'field muted', text: 'Chỉ cần khi đối tác có tool theo dõi bằng events. Schema nói với platform mỗi loại sự kiện nghĩa là gì.' }), true);
    const integrationKeys = (g) => {
      const box = h('div');
      const d = dialog('Khóa của integration ' + g.integration_id, box, true);
      const guard = (fn) => async (ev) => {
        ev.target.disabled = true;
        try { await fn(); } catch (e) { d.close(); fail(e); }
      };
      const draw = () => load(box, async () => {
        const [full, { keys: list }] = await Promise.all([call('integration', [g.integration_id]), call('providerKeys', [g.integration_id])]);
        return [
          h('div', { class: 'row field' },
            h('button', { class: 'primary', type: 'button', text: 'Tạo khóa provider', onclick: guard(async () => {
              const made = await call('providerKeyAdd', [g.integration_id], { body: {} });
              d.close();
              secretOf('Khóa provider mới', made);
            }) }),
            h('button', { type: 'button', text: 'Thêm khóa ký', onclick: guard(async () => {
              const made = await call('signingKeyAdd', [g.integration_id]);
              d.close();
              secretOf('Khóa ký mới', made);
            }) })),
          h('h3', { class: 'field', text: 'Khóa API của provider' }), keyTable(list, 'Chưa có khóa provider nào.'),
          h('h3', { class: 'field', text: 'Khóa ký (HMAC)' }), table([
            { title: 'Khóa ký', cell: (s) => mono(s.key_id) }, { title: 'Trạng thái', cell: (s) => badge(s.status) }, { title: 'Tạo lúc', cell: (s) => when(s.created_at) },
            { title: '', cls: 'actions', cell: (s) => (s.status !== 'active' ? '' : h('button', { class: 'sm danger', type: 'button', text: 'Thu hồi',
              onclick: guard(async () => { await call('signingKeyRevoke', [g.integration_id, s.key_id]); draw(); }) })) },
          ], full.signing_keys || [], 'Chưa có khóa ký nào.')];
      });
      draw();
    };
    const integrationTable = table([
      { title: 'Integration', cell: (g) => mono(g.integration_id) }, { title: 'Trạng thái', cell: (g) => badge(g.status) },
      { title: 'Schema', cell: (g) => 'v' + g.event_schema.version + ' · ' + g.event_schema.version_mode },
      { title: 'Loại sự kiện', cls: 'wrap', cell: (g) => chips(Object.keys(g.event_schema.events || {})) }, { title: 'Tạo lúc', cell: (g) => when(g.created_at) },
      { title: '', cls: 'actions', cell: (g) => [
        h('button', { class: 'sm', type: 'button', text: 'Xem schema', onclick: () => dialog('Schema sự kiện của ' + g.integration_id, h('pre', { text: json(g.event_schema) }), true) }),
        h('button', { class: 'sm', type: 'button', text: 'Khóa provider', onclick: () => integrationKeys(g) })] },
    ], integrations, 'Chưa có integration nào.');

    return [
      h('div', { class: 'page-head' }, h('div', null, h('h1', { text: client.name }), h('div', { class: 'lead mono', text: client.client_id + ' · ' + client.domain + ' · ' + client.environment }))),
      panel('Khóa đối tác', 'dùng với Authorization: ApiKey trên /workforce/v1', [h('button', { type: 'button', text: 'Tạo khóa', onclick: addKey })], keyTable(keys, 'Chưa có khóa nào.')),
      panel('Tài khoản ban quản lý (manager)', 'khóa vận hành chỉ thấy route của chính manager', [h('button', { type: 'button', text: 'Thêm manager', onclick: addManager })], managerTable),
      panel('Route', needs || 'tạo ở trạng thái pending, đối tác xác nhận', [h('button', { type: 'button', text: 'Tạo route', disabled: !!needs, title: needs || '', onclick: addRoute })], routeTable),
      panel('Integration và khóa provider', 'backend nghiệp vụ gửi tiến độ qua Provider Event API', [h('button', { type: 'button', text: 'Thêm integration', onclick: addIntegration })], integrationTable),
    ];
  }

  // =====================================================================================================================
  // 4. Vận hành
  // =====================================================================================================================
  const STATES = ['needs_attention', 'accepted', 'active', 'awaiting_user', 'awaiting_approval', 'awaiting_confirmation', 'waiting_external_event',
    'blocked_authorization', 'blocked_route_changed', 'closed'];
  const ATTENTION = {
    leader_silent: 'Leader chạy xong lượt mà không nói gì với cư dân.',
    engine_error: 'Lượt chạy của agent bị lỗi.',
    operation_unknown: 'Một hành động ở phía đối tác chưa rõ kết quả: hãy kiểm tra với đối tác trước khi cho chạy tiếp.',
    external_timeout: 'Chờ sự kiện bên ngoài quá hạn.',
    stalled: 'Workflow đứng yên quá lâu.',
    provider_gap: 'Sự kiện của provider bị thiếu hoặc không nối được.',
  };
  const OPS_TABS = [['workflows', 'Workflow'], ['operations', 'Operation'], ['approvals', 'Approval'], ['receipts', 'Biên nhận sự kiện']];
  const wfLink = (id) => (id ? link(['ops', 'workflows', id], id, 'mono') : '—');
  const OP_COLS = [
    { title: 'Operation', cell: (o) => mono(o.operation_id) }, { title: 'Workflow', cell: (o) => wfLink(o.workflow_id) }, { title: 'Tool', cell: (o) => o.tool },
    { title: 'Trạng thái', cell: (o) => [badge(o.status), o.reviewed ? h('div', { class: 'small muted', text: 'đã có người xem' }) : null] },
    { title: 'Phía đối tác', cell: (o) => dash(o.partner_status) },
    { title: 'Tham chiếu', cell: (o) => [mono(dash(o.client_reference)), o.external_job_id ? h('div', { class: 'mono muted', text: o.external_job_id }) : null] },
    { title: 'Kết quả', cls: 'wrap', cell: (o) => (o.error ? h('span', { class: 'err', text: o.error }) : dash(o.outcome || o.text)) },
    { title: 'Cập nhật', cell: (o) => when(o.updated_at) }];
  const APPROVAL_COLS = [
    { title: 'Approval', cell: (a) => mono(a.approval_id) }, { title: 'Workflow', cell: (a) => wfLink(a.workflow_id) }, { title: 'Tool', cell: (a) => a.tool },
    { title: 'Trạng thái', cell: (a) => badge(a.status) },
    { title: 'Nội dung hỏi cư dân', cls: 'wrap', cell: (a) => (a.summary == null ? '—' : typeof a.summary === 'string' ? a.summary : JSON.stringify(a.summary)) },
    { title: 'Hết hạn', cell: (a) => when(a.expires_at) }, { title: 'Quyết định lúc', cell: (a) => when(a.decided_at) }, { title: 'Tạo lúc', cell: (a) => when(a.created_at) }];
  const RECEIPT_COLS = [
    { title: 'Biên nhận', cell: (x) => mono(x.receipt_id) }, { title: 'Loại sự kiện', cell: (x) => mono(x.event_type) }, { title: 'Tiếp nhận', cell: (x) => badge(x.ingestion_status) },
    { title: 'Trạng thái chuẩn hóa', cell: (x) => dash(x.normalized_status) }, { title: 'Workflow', cell: (x) => wfLink(x.workflow_id) },
    { title: 'Operation', cell: (x) => mono(dash(x.operation_id)) }, { title: 'Ghi chú', cls: 'wrap', cell: (x) => (x.error ? h('span', { class: 'err', text: x.error }) : dash(x.note)) },
    { title: 'Nhận lúc', cell: (x) => when(x.received_at) }, { title: 'Áp dụng lúc', cell: (x) => when(x.applied_at) }];

  async function opsScreen(parts) {
    const tab = OPS_TABS.some(([id]) => id === parts[0]) ? parts[0] : 'workflows';
    const head = [pageHead('Vận hành', 'Những gì platform đang làm cho các đối tác, và workflow cần người xử lý.'),
      h('nav', { class: 'tabs' }, OPS_TABS.map(([id, label]) => link(['ops', id], label, id === tab ? 'on' : '')))];
    if (tab === 'workflows' && parts[1]) return [head, await workflowDetail(parts[1])];
    const filter = state.keep['f.' + tab] || '';
    const choose = (options, label) => {
      const s = h('select', { class: 'auto', 'aria-label': label }, [['', 'Tất cả ' + label], ...options.map((x) => [x, x])].map(([v, text]) => h('option', { value: v, text })));
      s.value = filter;
      s.addEventListener('change', () => { state.keep['f.' + tab] = s.value; again(); });
      return s;
    };
    if (tab === 'workflows') {
      const { workflows } = await call('workflows', [], { query: { state: filter, limit: 200 } });
      return [head, panel('Workflow', workflows.length + ' workflow, mới nhất trước', [choose(STATES, 'trạng thái')], table([
        { title: 'Workflow', cell: (w) => wfLink(w.workflow_id) },
        { title: 'Ticket / cư dân', cell: (w) => [dash(w.external_ticket_id), h('div', { class: 'muted small', text: w.external_user_id })] },
        { title: 'Trạng thái', cell: (w) => badge(w.state) }, { title: 'Bước tiếp theo', cell: (w) => mono(w.next_action) },
        { title: 'Lý do cần chú ý', cls: 'wrap', cell: (w) => (w.attention_reason ? [mono(w.attention_reason), h('div', { class: 'small muted', text: ATTENTION[w.attention_reason] || '' })] : '—') },
        { title: 'Hoạt động gần nhất', cell: (w) => when(w.last_activity_at) },
        { title: '', cls: 'actions', cell: (w) => link(['ops', 'workflows', w.workflow_id], w.state === 'needs_attention' ? 'Xử lý' : 'Chi tiết', 'btn sm') },
      ], workflows, filter ? 'Không có workflow nào ở trạng thái ' + filter + '.' : 'Chưa có workflow nào.', (w) => (w.state === 'needs_attention' ? 'attn' : '')))];
    }
    if (tab === 'operations') {
      const { operations } = await call('operations', [], { query: { status: filter, limit: 200 } });
      return [head, panel('Operation', 'hành động platform đã gửi sang đối tác', [choose(['intent', 'sent', 'pending', 'unknown', 'completed', 'failed'], 'trạng thái')],
        table(OP_COLS, operations, 'Chưa có operation nào.'))];
    }
    if (tab === 'approvals') {
      const { approvals } = await call('approvals', [], { query: { status: filter, limit: 200 } });
      return [head, panel('Approval', 'những lần hỏi cư dân đồng ý trước một hành động', [choose(['pending', 'approved', 'rejected', 'expired', 'cancelled'], 'trạng thái')],
        table(APPROVAL_COLS, approvals, 'Chưa có approval nào.'))];
    }
    const { receipts } = await call('receipts', [], { query: { status: filter, limit: 200 } });
    return [head, panel('Biên nhận sự kiện của provider', 'mỗi sự kiện đã nhận và kết cục của nó',
      [choose(['accepted', 'processing', 'applied', 'duplicate', 'quarantined', 'rejected', 'needs_attention'], 'trạng thái')],
      table(RECEIPT_COLS, receipts, 'Chưa có biên nhận nào.'))];
  }

  async function workflowDetail(id) {
    const q = { query: { workflow_id: id, limit: 200 } };
    const [w, { operations }, { approvals }, { receipts }] = await Promise.all([
      call('workflow', [id]), call('operations', [], q), call('approvals', [], q), call('receipts', [], q)]);
    const resolve = (action, title, text, label, danger) => () => confirm(title, text, label, async () => {
      const out = await call('resolve', [id], { body: { action } });
      toast('Workflow hiện ở trạng thái ' + out.state);
      again();
    }, danger);
    return [
      h('div', { class: 'crumb' }, link(['ops', 'workflows'], 'Workflow'), ' / ', id),
      panel('Workflow ' + id, null, [badge(w.state)], h('div', { class: 'stack' },
        w.state === 'needs_attention' ? note('warn', 'Workflow này cần người xử lý',
          h('div', { text: (w.attention_reason || 'không rõ lý do') + (ATTENTION[w.attention_reason] ? ': ' + ATTENTION[w.attention_reason] : '') }),
          h('div', { class: 'row' },
            h('button', { type: 'button', class: 'primary', text: 'Cho leader chạy tiếp (resume)', onclick: resolve('resume', 'Cho leader chạy tiếp',
              'Leader được báo tiếp tục. Các operation chưa rõ kết quả được đánh dấu là đã có người xem và không còn giữ workflow lại.', 'Chạy tiếp') }),
            h('button', { type: 'button', class: 'danger', text: 'Đóng workflow (close)', onclick: resolve('close', 'Đóng workflow',
              'Workflow kết thúc và ngừng theo dõi mọi việc đang mở. Không có gì được gọi sang đối tác.', 'Đóng workflow', true) }))) : null,
        kv([['Trạng thái', badge(w.state)], ['Bước tiếp theo', mono(w.next_action)], ['Lý do cần chú ý', dash(w.attention_reason)], ['Lý do đóng', dash(w.close_reason)],
          ['Route', link(['tools', w.route_id], w.route_id, 'mono')], ['Client', mono(w.client_id)], ['Hội thoại', mono(w.conversation_id)],
          ['Cư dân', dash(w.external_user_id)], ['Ticket', dash(w.external_ticket_id)], ['Revision', w.revision],
          ['Tạo lúc', when(w.created_at)], ['Hoạt động gần nhất', when(w.last_activity_at)], ['Đóng lúc', when(w.closed_at)]])), false),
      panel('Operation', operations.length + ' dòng', null, table(OP_COLS.filter((c) => c.title !== 'Workflow'), operations, 'Workflow này chưa gửi hành động nào sang đối tác.')),
      panel('Approval', approvals.length + ' dòng', null, table(APPROVAL_COLS.filter((c) => c.title !== 'Workflow'), approvals, 'Workflow này chưa hỏi cư dân đồng ý lần nào.')),
      panel('Biên nhận sự kiện', receipts.length + ' dòng', null, table(RECEIPT_COLS.filter((c) => c.title !== 'Workflow'), receipts, 'Chưa có sự kiện nào của provider cho workflow này.')),
    ];
  }

  // =====================================================================================================================
  // 5. Chi phí
  // =====================================================================================================================
  const PERIODS = [['24', '24 giờ qua'], ['168', '7 ngày qua'], ['720', '30 ngày qua']];
  const COST_COLS = (first, field) => [
    { title: first, cell: (r) => mono(dash(r[field])) }, { title: 'Số lời gọi', cls: 'num', cell: (r) => num(r.calls) },
    { title: 'Token vào', cls: 'num', cell: (r) => num(r.input_tokens) }, { title: 'Token ra', cls: 'num', cell: (r) => num(r.output_tokens) },
    { title: 'Chi phí', cls: 'num', cell: (r) => usd(r.cost_usd) }];

  async function costScreen(parts) {
    const hours = PERIODS.some(([v]) => v === state.keep.hours) ? state.keep.hours : '24';
    const [{ models }, { cases }] = await Promise.all([call('cost', [], { query: { since_hours: hours } }), call('cases', [], { query: { limit: 100 } })]);
    const period = h('select', { class: 'auto', 'aria-label': 'Khoảng thời gian' }, PERIODS.map(([v, text]) => h('option', { value: v, text })));
    period.value = hours;
    period.addEventListener('change', () => { state.keep.hours = period.value; again(); });
    const total = models.reduce((s, m) => s + m.cost_usd, 0);
    const detail = h('div');
    if (parts[0]) {
      load(detail, async () => {
        const c = await call('caseCost', [parts[0]]);
        return panel('Chi phí của vụ ' + parts[0], num(c.totals.calls) + ' lời gọi model' + (c.totals.unpriced_calls ? ', ' + c.totals.unpriced_calls + ' lời gọi chưa có giá' : ''), null, [
          h('div', { class: 'panel-body' }, kv([['Tổng chi phí', h('strong', { text: usd(c.totals.cost_usd) })], ['Token vào', num(c.totals.input_tokens)],
            ['Token ra', num(c.totals.output_tokens)], ['Token đọc từ cache', num(c.totals.cache_read_tokens)]])),
          h('div', { class: 'grid2 panel-body' },
            h('div', null, h('h3', { class: 'field', text: 'Theo agent' }), table(COST_COLS('Agent', 'agent_name'), c.by_agent, 'Vụ này chưa gọi model nào.')),
            h('div', null, h('h3', { class: 'field', text: 'Theo model' }), table(COST_COLS('Model', 'model'), c.by_model, 'Vụ này chưa gọi model nào.')))]);
      });
    }
    return [
      pageHead('Chi phí', 'Chi phí model của tenant: theo model, và theo từng vụ (case) với agent và model của nó.'),
      panel('Theo model', 'tổng ' + usd(total), [period], table(COST_COLS('Model', 'model'), models, 'Chưa có lời gọi model nào trong khoảng thời gian này.')),
      parts[0] ? detail : null,
      panel('Theo vụ (case)', cases.length + ' vụ gần nhất; mỗi workflow là một vụ', null, table([
        { title: 'Vụ', cell: (c) => link(['cost', c.id], c.id, 'mono') }, { title: 'Lĩnh vực', cell: (c) => c.domain },
        { title: 'Tham chiếu ngoài', cell: (c) => dash(c.external_ref) }, { title: 'Trạng thái', cell: (c) => badge(c.status) }, { title: 'Tạo lúc', cell: (c) => when(c.created_at) },
        { title: '', cls: 'actions', cell: (c) => (c.id === parts[0] ? h('span', { class: 'muted', text: 'đang xem' }) : link(['cost', c.id], 'Xem chi phí', 'btn sm')) },
      ], cases, 'Chưa có vụ nào.', (c) => (c.id === parts[0] ? 'picked' : ''))),
    ];
  }

  // =====================================================================================================================
  // the shell: login, navigation, routing
  // =====================================================================================================================
  const NAV = [
    { id: 'tools', label: 'Kho tool', screen: toolsScreen },
    { id: 'agents', label: 'Agent', screen: agentsScreen },
    { id: 'builder', nav: 'agents', admin: true, screen: builderScreen },
    { id: 'partners', label: 'Đối tác', admin: true, screen: partnersScreen },
    { id: 'ops', label: 'Vận hành', screen: opsScreen },
    { id: 'cost', label: 'Chi phí', admin: true, screen: costScreen },
  ];

  function pageHead(title, lead, actions) {
    return h('div', { class: 'page-head' }, h('div', null, h('h1', { text: title }), lead ? h('div', { class: 'lead', text: lead }) : null),
      h('div', { class: 'row' }, actions || []));
  }

  function logout(message) {
    store.drop(KEY);
    store.drop(BUILDER);
    state.key = '';
    state.me = null;
    state.keep = {};
    state.notice = message || '';
    render();
  }

  function loginView() {
    const f = form([{ name: 'key', label: 'Khóa admin hoặc khóa manager', type: 'password', required: true, placeholder: 'Dán khóa vào đây' }], {
      submit: 'Đăng nhập',
      onSubmit: async (v) => {
        state.key = v.key;
        try {
          state.me = await call('me');
        } catch (e) {
          state.key = '';
          throw e;
        }
        store.set(KEY, v.key);
        state.notice = '';
        render();
      },
    });
    return h('div', { class: 'login' }, h('div', { class: 'login-card' },
      h('h1', { text: 'Bảng điều khiển' }), h('div', { class: 'sub', text: 'AI Workforce Platform' }),
      state.notice ? note('warn', state.notice) : null, h('div', { class: 'field' }), f,
      h('div', { class: 'note', text: 'Khóa chỉ được giữ trong phiên của tab này và mất khi đăng xuất hoặc đóng tab. Khóa chỉ được gửi trong header Authorization, không bao giờ nằm trong địa chỉ trang.' })));
  }

  function render() {
    state.seq += 1;
    closeDialogs();
    if (!state.me) {
      root.replaceChildren(loginView(), toasts);
      const input = root.querySelector('input');
      if (input) input.focus();
      return;
    }
    const parts = location.hash.replace(/^#\/?/, '').split('/').filter(Boolean).map((x) => { try { return decodeURIComponent(x); } catch (e) { return x; } });
    const admin = state.me.role === 'admin';
    const item = NAV.find((n) => n.id === parts[0]) || NAV[0];
    const on = item.nav || item.id;
    flash = h('div', { class: 'flash' });
    const content = h('div');
    root.replaceChildren(h('div', { class: 'layout' },
      h('aside', { class: 'side' },
        h('div', { class: 'brand' }, 'Bảng điều khiển', h('small', { text: 'AI Workforce Platform' })),
        h('nav', { class: 'nav' }, NAV.filter((n) => n.label && (admin || !n.admin)).map((n) => link([n.id], n.label, n.id === on ? 'on' : ''))),
        h('div', { class: 'who' },
          h('div', { class: 'role', text: admin ? 'Quản trị tenant' : 'Ban quản lý: ' + (state.me.manager_name || state.me.manager_id) }),
          h('div', { class: 'tenant', text: 'Tenant: ' + state.me.tenant }),
          h('button', { type: 'button', class: 'ghost', text: 'Tải lại dữ liệu', onclick: again }),
          h('button', { type: 'button', class: 'ghost', text: 'Đăng xuất', onclick: () => logout('') }))),
      h('main', { class: 'main' }, flash, content)), toasts);
    if (item.admin && !admin) {
      content.replaceChildren(note('warn', 'Khóa manager không mở được màn hình này', h('div', { text: 'Màn hình này chỉ dành cho khóa admin của tenant.' })));
      return;
    }
    load(content, () => item.screen(parts.slice(1)));
  }

  async function start() {
    window.addEventListener('hashchange', render);
    state.key = store.get(KEY);
    if (state.key) {
      root.replaceChildren(h('div', { class: 'login' }, h('div', { class: 'loading', text: 'Đang kiểm tra khóa…' })));
      try { state.me = await call('me'); } catch (e) {
        state.key = '';
        store.drop(KEY);
        state.notice = e.status === 401 ? 'Khóa đã lưu không còn hiệu lực. Hãy đăng nhập lại.' : 'Không kiểm tra được khóa (' + (HINTS[e.status] || 'lỗi ' + e.status) + ')';
      }
    }
    render();
  }
  start();
})();
