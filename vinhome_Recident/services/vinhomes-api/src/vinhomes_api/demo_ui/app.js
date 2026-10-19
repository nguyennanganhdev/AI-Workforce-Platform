'use strict';

// This console uses the server contract; it never implements business transitions.
const $ = (id) => document.getElementById(id);
const state = { spec: null, operations: [], selected: null, values: {}, history: [], busy: false, downloadUrl: null };
const flows = [
  ['Cư dân → Ban quản lý', [
    ['resident', 'POST', '/resident/chats', '1. Tạo chat'],
    ['resident', 'POST', '/resident/chats/{channel_id}/messages', '2. Gửi tin nhắn'],
    ['resident', 'POST', '/resident/chats/{channel_id}/tickets', '3. Tạo ticket'],
    ['management', 'GET', '/management-units/resolve', '4. Tra ban quản lý'],
    ['management', 'POST', '/tickets/{ticket_id}/routing/ack', '5. Tiếp nhận'],
    ['management', 'GET', '/tickets/{ticket_id}', '6. Đọc ticket và version'],
  ]],
  ['Triage → Điều phối → Thực hiện', [
    ['management', 'POST', '/tickets/{ticket_id}/assessments', '1. Đánh giá'],
    ['management', 'POST', '/tickets/{ticket_id}/triage-decisions', '2. Đề xuất triage'],
    ['management', 'GET', '/triage-reviews', '3. Danh sách duyệt triage'],
    ['management', 'POST', '/triage-reviews/{review_id}/decision', '4. Duyệt triage'],
    ['management', 'POST', '/tickets/{ticket_id}/work-orders', '5. Tạo công việc'],
    ['management', 'GET', '/staff/available', '6. Tìm nhân sự'],
    ['management', 'POST', '/work-orders/{work_order_id}/assignments', '7. Mời nhận việc'],
    ['technical', 'POST', '/assignments/{assignment_id}/response', '8. Nhận / từ chối'],
    ['technical', 'PATCH', '/work-orders/{work_order_id}/status', '9. Cập nhật từng trạng thái'],
  ]],
  ['Khóa nước → Hoàn công', [
    ['technical', 'POST', '/work-orders/{work_order_id}/water-shutdown-request', '1. Xin khóa nước'],
    ['management', 'GET', '/approvals', '2. Lấy approval'],
    ['management', 'POST', '/approvals/{approval_id}/decision', '3. Duyệt / từ chối'],
    ['management', 'POST', '/water-interruptions/{interruption_id}/notify', '4. Thông báo'],
    ['technical', 'POST', '/water-interruptions/{interruption_id}/start', '5. Khóa nước'],
    ['technical', 'POST', '/water-interruptions/{interruption_id}/restore', '6. Mở lại nước'],
    ['technical', 'POST', '/tickets/{ticket_id}/files', '7. Tải ảnh'],
    ['technical', 'POST', '/tickets/{ticket_id}/evidence', '8. Gắn bằng chứng'],
    ['technical', 'PATCH', '/work-orders/{work_order_id}/status', '9. Hoàn thành công việc'],
    ['resident', 'GET', '/resident/approvals', '10. Lấy yêu cầu xác nhận'],
    ['resident', 'POST', '/resident/approvals/{approval_id}/decision', '11. Xác nhận / trả lại'],
  ]],
  ['QC / Vệ sinh / Nhà thầu / Ngân sách', [
    ['management', 'POST', '/work-orders/{work_order_id}/qc', '1. Ghi kết quả QC'],
    ['management', 'POST', '/work-orders/{work_order_id}/redo', '2. Tạo việc làm lại nếu QC lỗi'],
    ['management', 'PUT', '/work-orders/{work_order_id}/cleaning-plan', '3. Kế hoạch vệ sinh'],
    ['management', 'PUT', '/work-orders/{work_order_id}/contractor', '4. Cập nhật nhà thầu'],
    ['management', 'POST', '/work-orders/{work_order_id}/budget-approvals', '5. Đề nghị ngân sách'],
    ['management', 'GET', '/budget-approvals', '6. Danh sách chờ duyệt'],
    ['management', 'POST', '/budget-approvals/{approval_id}/decision', '7. Duyệt / từ chối ngân sách'],
  ]],
  ['An ninh', [
    ['security', 'GET', '/my-work-orders', '1. Công việc của bảo vệ'],
    ['security', 'GET', '/security/checkpoints', '2. Điểm kiểm tra'],
    ['admin', 'POST', '/security/checkpoints', '3. Tạo điểm kiểm tra'],
    ['security', 'PATCH', '/security/checkpoints/{checkpoint_id}', '4. Ghi nhận tuần tra'],
    ['security', 'POST', '/security/incidents', '5. Báo cáo sự cố'],
    ['security', 'GET', '/security/incidents', '6. Xem sự cố'],
    ['management', 'PATCH', '/security/incidents/{incident_id}', '7. Cập nhật sự cố'],
    ['security', 'POST', '/security/handovers', '8. Tạo bàn giao'],
    ['security', 'GET', '/security/handovers', '9. Xem bàn giao'],
    ['security', 'POST', '/security/handovers/{handover_id}/confirm', '10. Xác nhận bàn giao'],
  ]],
  ['Báo cáo / Thông báo', [
    ['management', 'GET', '/reports/incident-frequency', '1. Tần suất sự cố'],
    ['management', 'GET', '/reports/issued-revenue', '2. Doanh thu hóa đơn'],
    ['resident', 'GET', '/my/notifications', '3. Thông báo'],
  ]],
];

function element(tag, text, parent) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (parent) parent.append(node);
  return node;
}

function dereference(schema) {
  if (!schema?.$ref) return schema || {};
  return schema.$ref.split('/').slice(1).reduce((value, key) => value?.[key], state.spec) || {};
}

function sample(raw, name = '', depth = 0) {
  if (depth > 8) return null;
  const schema = dereference(raw);
  if (schema.example !== undefined) return schema.example;
  if (schema.default !== undefined) return schema.default;
  if (state.values[name]) return schema.type === 'integer' ? Number(state.values[name]) : state.values[name];
  if (schema.enum) return schema.enum[0];
  if (schema.const !== undefined) return schema.const;
  const alternative = schema.anyOf || schema.oneOf;
  if (alternative) return sample(alternative.find((item) => item.type !== 'null') || alternative[0], name, depth + 1);
  if (schema.allOf) return Object.assign({}, ...schema.allOf.map((item) => sample(item, name, depth + 1)));
  if (schema.type === 'object' || schema.properties) {
    return Object.fromEntries(Object.entries(schema.properties || {})
      .filter(([key]) => (schema.required || []).includes(key) || state.values[key] !== undefined)
      .map(([key, value]) => [key, sample(value, key, depth + 1)]));
  }
  if (schema.type === 'array') return [];
  if (schema.type === 'boolean') return false;
  if (schema.type === 'integer' || schema.type === 'number') return schema.minimum ?? 1;
  if (schema.type === 'null') return null;
  if (schema.format === 'uuid') return '';
  if (schema.format === 'date-time') return new Date(Date.now() + 3600000).toISOString();
  if (schema.format === 'date') return new Date().toISOString().slice(0, 10);
  if (/client_message_id|idempotency_key/.test(name)) return crypto.randomUUID();
  return '';
}

function renderList() {
  const query = $('search').value.toLowerCase();
  const group = $('group').value;
  const operations = state.operations.filter((op) => (!group || op.tags?.includes(group)) &&
    `${op.method} ${op.path} ${op.summary || ''}`.toLowerCase().includes(query));
  $('count').textContent = `${operations.length} / ${state.operations.length} endpoint`;
  $('endpoints').replaceChildren();
  for (const op of operations) {
    const button = element('button', undefined, $('endpoints'));
    button.type = 'button';
    button.setAttribute('aria-current', String(op === state.selected));
    element('span', op.method, button).className = 'method';
    element('span', op.path, button);
    element('small', op.summary || '', button);
    button.onclick = () => selectOperation(op);
  }
}

function renderFlows() {
  for (const [title, steps] of flows) {
    const section = element('section', undefined, $('flows'));
    element('h2', title, section);
    for (const [actor, method, path, label] of steps) {
      const op = state.operations.find((item) => item.method === method && item.path === path);
      const button = element('button', `${label} · ${actor}${op ? '' : ' — chưa có endpoint này'}`, section);
      button.type = 'button';
      button.disabled = !op;
      button.onclick = () => { $('actor').value = actor; selectOperation(op); $('operation-title').scrollIntoView({ behavior: 'smooth', block: 'start' }); };
    }
  }
}

function bodyContent(op) {
  return dereference(op.requestBody).content || {};
}

function fillTemplate() {
  const content = bodyContent(state.selected);
  $('body').value = JSON.stringify(sample(content['application/json']?.schema), null, 2);
}

function selectOperation(op) {
  if (state.busy) return;
  state.selected = op;
  $('operation-title').textContent = `${op.method} ${op.path}`;
  $('description').textContent = op.summary || '';
  $('parameters').replaceChildren();
  for (const param of op.parameters || []) {
    if (!['path', 'query'].includes(param.in)) continue;
    const label = element('label', `${param.name} · ${param.in}${param.required ? ' *' : ''}`, $('parameters'));
    const schema = dereference(param.schema);
    const input = element(schema.enum ? 'select' : 'input', undefined, label);
    if (schema.enum) {
      if (!param.required) element('option', '', input).value = '';
      for (const value of schema.enum) element('option', String(value), input).value = String(value);
    } else {
      input.type = 'text';
      input.placeholder = schema.format || schema.type || '';
    }
    input.dataset.name = param.name;
    input.dataset.location = param.in;
    input.required = !!param.required;
    input.value = state.values[param.name] ?? (schema.default === undefined ? '' : String(schema.default));
    if (param.description) element('small', param.description, label);
  }
  const content = bodyContent(op);
  $('json-body').hidden = !content['application/json'];
  $('file-body').hidden = !content['application/octet-stream'];
  $('body-note').textContent = content['application/octet-stream'] ? 'Gửi bytes ảnh trực tiếp. Chọn ảnh để điền filename và mimeType.' :
    op.method === 'GET' ? 'Thao tác đọc dữ liệu.' : 'Thao tác ghi dữ liệu. Mẫu JSON không đảm bảo hợp lệ nghiệp vụ; điền ID, enum, version và các trường bắt buộc theo schema.';
  const definitions = {};
  function includeReferences(value) {
    if (!value || typeof value !== 'object') return;
    if (value.$ref && !(value.$ref in definitions)) {
      definitions[value.$ref] = dereference(value);
      includeReferences(definitions[value.$ref]);
    }
    for (const child of Object.values(value)) includeReferences(child);
  }
  includeReferences(op.parameters);
  includeReferences(op.requestBody);
  $('schema').textContent = JSON.stringify({ parameters: op.parameters || [], requestBody: dereference(op.requestBody), definitions }, null, 2);
  if (content['application/json']) fillTemplate();
  $('send').disabled = false;
  renderList();
}

function renderVariables() {
  $('variables').replaceChildren();
  for (const [key, value] of Object.entries(state.values)) {
    const label = element('label', key, $('variables'));
    const input = element('input', undefined, label);
    input.value = value;
    input.oninput = () => { state.values[key] = input.value; };
  }
  const add = element('button', 'Thêm ID / version', $('variables'));
  add.type = 'button';
  add.onclick = () => {
    const name = window.prompt('Tên trường: ticket_id, work_order_id, ticket_version…');
    if (!name || !/^[a-zA-Z][a-zA-Z0-9_]*$/.test(name)) return;
    const value = window.prompt('Giá trị');
    if (value !== null) useValue(name, value);
  };
}

function useValue(name, value) {
  state.values[name] = String(value);
  renderVariables();
  for (const input of $('parameters').querySelectorAll('[data-name]')) {
    if (input.dataset.name === name) input.value = String(value);
  }
}

function collectValues(value, path = '', result = []) {
  if (result.length >= 150 || path.split('.').length > 12) return result;
  if (value && typeof value === 'object') {
    for (const [key, child] of Object.entries(value)) collectValues(child, path ? `${path}.${key}` : key, result);
  } else if (typeof value === 'string' || typeof value === 'number') {
    const key = path.split('.').pop();
    if (/id$|version$|seq$/.test(key)) result.push([path, key, value]);
  }
  return result;
}

function showResult(entry) {
  $('result-status').className = entry.ok ? 'success' : 'error';
  $('result-status').textContent = `${entry.status} · ${entry.actor} · ${entry.method} ${entry.path} · ${entry.duration} ms${entry.status === 409 ? ' — đọc lại tài nguyên và cập nhật version trước khi thử lại.' : ''}`;
  $('response').textContent = typeof entry.response === 'string' ? entry.response : JSON.stringify(entry.response, null, 2);
  $('save-values').replaceChildren();
  for (const [path, key, value] of collectValues(entry.response)) {
    const button = element('button', `Dùng giá trị ${path}: ${value}`, $('save-values'));
    button.type = 'button';
    button.onclick = () => {
      const inferred = path.split('.').slice(-2, -1)[0];
      const defaultName = key === 'id' && inferred && !/^\d+$/.test(inferred) ? `${inferred.replace(/s$/, '')}_id` : key;
      const name = window.prompt('Lưu vào tên trường nào? Ví dụ ticket_id, channel_id, work_order_id, ticket_version, work_order_version', defaultName);
      if (name && /^[a-zA-Z][a-zA-Z0-9_]*$/.test(name)) useValue(name, value);
    };
  }
}

async function sendRequest(event) {
  event.preventDefault();
  if (state.busy || !state.selected) return;
  const op = state.selected;
  const actor = $('actor').value;
  const url = new URL(op.path, location.origin);
  let pathname = op.path;
  const headers = { 'X-Demo-Actor': actor };
  let body;
  try {
    for (const input of $('parameters').querySelectorAll('[data-name]')) {
      if (input.dataset.location === 'path') pathname = pathname.replace(`{${input.dataset.name}}`, encodeURIComponent(input.value));
      else if (input.value !== '') url.searchParams.set(input.dataset.name, input.value);
    }
    if (pathname.includes('{')) throw new Error('Điền đầy đủ các ID trong đường dẫn.');
    url.pathname = pathname;
    if (!url.pathname.startsWith('/') || url.origin !== location.origin) throw new Error('Chỉ gọi API cùng máy chủ.');
    if (!$('json-body').hidden) { body = JSON.stringify(JSON.parse($('body').value)); headers['Content-Type'] = 'application/json'; }
    if (!$('file-body').hidden) {
      body = $('file').files[0];
      if (!body) throw new Error('Chọn ảnh trước khi gửi.');
      if (body.size > 10 * 1024 * 1024) throw new Error('Ảnh tối đa 10 MB.');
      headers['Content-Type'] = 'application/octet-stream';
    }
  } catch (error) { $('result-status').className = 'error'; $('result-status').textContent = error.message; return; }
  state.busy = true;
  $('send').disabled = true;
  $('fixtures').disabled = true;
  $('result-status').className = '';
  $('result-status').textContent = 'Đang gửi request…';
  $('download').replaceChildren();
  if (state.downloadUrl) { URL.revokeObjectURL(state.downloadUrl); state.downloadUrl = null; }
  const start = performance.now();
  try {
    const response = await fetch(url, { method: op.method, headers, body, credentials: 'same-origin', signal: AbortSignal.timeout(30000), redirect: 'error' });
    const contentType = response.headers.get('content-type') || '';
    let result;
    if (contentType.includes('json')) result = await response.json();
    else if (contentType.startsWith('text/')) result = await response.text();
    else {
      const blob = await response.blob();
      state.downloadUrl = URL.createObjectURL(blob);
      const link = element('a', 'Tải file phản hồi', $('download'));
      link.href = state.downloadUrl;
      link.download = url.pathname.endsWith('.docx') ? 'bao-cao.docx' : 'api-response';
      result = `File ${contentType}, ${blob.size} bytes. Dùng liên kết tải bên trên.`;
    }
    const entry = { method: op.method, path: url.pathname + url.search, actor, status: response.status, ok: response.ok, response: result, duration: Math.round(performance.now() - start) };
    state.history.unshift(entry);
    if (state.history.length > 50) state.history.pop();
    $('history').replaceChildren();
    for (const item of state.history) {
      const li = element('li', undefined, $('history'));
      const button = element('button', `${item.status} · ${item.actor} · ${item.method} ${item.path}`, li);
      button.type = 'button';
      button.onclick = () => { $('download').replaceChildren(); showResult(item); };
    }
    showResult(entry);
  } catch (error) {
    $('result-status').className = 'error';
    $('result-status').textContent = `Không nhận được phản hồi: ${error.message}. Kiểm tra service; với thao tác ghi, đọc lại dữ liệu trước khi gửi lại vì server có thể đã xử lý.`;
  } finally { state.busy = false; $('send').disabled = false; $('fixtures').disabled = false; }
}

async function loadFixtures() {
  if (state.busy) return;
  const op = state.operations.find((item) => item.path === '/demo/fixtures' && item.method === 'GET');
  if (!op) return;
  selectOperation(op);
  await sendRequest(new Event('submit'));
}

$('search').oninput = renderList;
$('group').onchange = renderList;
$('template').onclick = fillTemplate;
$('fixtures').onclick = loadFixtures;
$('request-form').onsubmit = sendRequest;
$('file').onchange = () => {
  const file = $('file').files[0];
  if (!file) return;
  for (const input of $('parameters').querySelectorAll('[data-name]')) {
    if (input.dataset.name === 'filename') input.value = file.name;
    if (input.dataset.name === 'mimeType') input.value = file.type;
  }
};

async function initialize() {
  try {
    const [schemaResponse, healthResponse] = await Promise.all([fetch('/openapi.json'), fetch('/health')]);
    if (!schemaResponse.ok || !healthResponse.ok) throw new Error('Không tải được OpenAPI hoặc health.');
    const health = await healthResponse.json();
    if (health.dataMode !== 'faker-database') throw new Error('Giao diện yêu cầu chế độ demo database.');
    state.spec = await schemaResponse.json();
    for (const [path, methods] of Object.entries(state.spec.paths)) {
      for (const [method, op] of Object.entries(methods)) {
        if (['get', 'post', 'put', 'patch', 'delete'].includes(method)) state.operations.push({ ...op, path, method: method.toUpperCase(), parameters: [...(methods.parameters || []), ...(op.parameters || [])] });
      }
    }
    for (const tag of [...new Set(state.operations.flatMap((op) => op.tags || []))].sort()) element('option', tag, $('group')).value = tag;
    $('connection').textContent = `V3 · ${state.operations.length} endpoint · đang kiểm tra database…`;
    renderList();
    renderFlows();
    renderVariables();
    try {
      const ready = await fetch('/ready', { signal: AbortSignal.timeout(10000) });
      if (!ready.ok) throw new Error('Database chưa sẵn sàng');
      $('connection').textContent = `V3 · ${state.operations.length} endpoint · database sẵn sàng`;
    } catch {
      $('connection').className = 'error';
      $('connection').textContent = `V3 · ${state.operations.length} endpoint · database chưa sẵn sàng; khởi động Docker/database và tải lại trang.`;
    }
  } catch (error) { $('connection').className = 'error'; $('connection').textContent = `${error.message} Tải lại trang khi API đã chạy.`; }
}
initialize();
