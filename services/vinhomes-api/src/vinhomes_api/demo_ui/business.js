'use strict';

const byId = (id) => document.getElementById(id);
const screen = byId('screen');
const state = { actor: 'resident', fixtures: {}, catalogs: {}, page: 'tickets', resource: null, generation: 0, writing: false };
const roles = { resident: 'Cư dân', management: 'Ban quản lý', technical: 'Kỹ thuật', security: 'Bảo vệ', admin: 'Quản trị viên' };
const words = {
  open: 'Mới', triaging: 'Đang đánh giá', assigned: 'Đã điều phối', queued: 'Chờ điều phối', offered: 'Chờ nhận việc', accepted: 'Đã nhận',
  en_route: 'Đang di chuyển', arrived: 'Đã đến', in_progress: 'Đang thực hiện', awaiting_approval: 'Chờ phê duyệt',
  completed: 'Hoàn thành', resolved: 'Đã xử lý', closed: 'Đã đóng', cancelled: 'Đã hủy', rejected: 'Từ chối',
  approved: 'Đã duyệt', pending: 'Chờ duyệt', requested: 'Đã đề nghị', active: 'Đang khóa nước', notified: 'Đã thông báo', restored: 'Đã mở nước',
  checked: 'Đã kiểm tra', missed: 'Chưa kiểm tra', investigating: 'Đang điều tra', escalated_to_police: 'Đã ghi nhận chuyển cấp',
  pass: 'Đạt', fail: 'Không đạt', inconclusive: 'Chưa kết luận', low: 'Thấp', normal: 'Bình thường', high: 'Cao', critical: 'Khẩn cấp',
  customer_completion: 'Xác nhận hoàn công', customer_repair: 'Chấp thuận sửa chữa', management_water_shutdown: 'Xin khóa nước',
  minor: 'Nhẹ', moderate: 'Vừa', major: 'Nặng', unknown: 'Chưa xác định', not_applicable: 'Không áp dụng',
  ca_sang: 'Ca sáng', ca_chieu: 'Ca chiều', ca_dem: 'Ca đêm', draft: 'Bản nháp',
};
const text = (value) => words[value] || String(value ?? '—');
const date = (value) => value ? new Date(value).toLocaleString('vi-VN') : '—';
function node(tag, content, parent) {
  const item = document.createElement(tag);
  if (content !== undefined) item.textContent = content;
  if (parent) parent.append(item);
  return item;
}
function button(parent, label, handler, primary = false) {
  const item = node('button', label, parent); item.type = 'button';
  if (primary) item.className = 'primary';
  item.onclick = () => { if (!state.writing) Promise.resolve().then(handler).catch(reportError); };
  return item;
}
function notify(message, error = false) { byId('notice').textContent = message; byId('notice').className = error ? 'error' : ''; }
function reportError(error) { notify(error.message || 'Không thực hiện được thao tác. Hãy làm mới và thử lại.', true); }
async function api(path, method = 'GET', body, binary = false) {
  const headers = { 'X-Demo-Actor': state.actor };
  if (body !== undefined) headers['Content-Type'] = binary ? 'application/octet-stream' : 'application/json';
  let response;
  try { response = await fetch(path, { method, headers, body: body === undefined ? undefined : binary ? body : JSON.stringify(body), signal: AbortSignal.timeout(30000), redirect: 'error' }); }
  catch { throw new Error('Mất kết nối hoặc hết thời gian chờ. Với thao tác lưu, làm mới để kiểm tra dữ liệu trước khi thử lại.'); }
  if (!response.ok) {
    let message = 'Không xử lý được yêu cầu.';
    try {
      const result = await response.json();
      message = Array.isArray(result.detail) ? result.detail.map((issue) => `${issue.loc.slice(1).join(' / ')}: ${issue.msg}`).join('\n') : result.detail || message;
    } catch { /* The API can return a plain error when unavailable. */ }
    const advice = response.status === 409 ? ' Dữ liệu đã thay đổi hoặc chưa đủ điều kiện. Đóng form, làm mới và kiểm tra trạng thái.' :
      [403, 404].includes(response.status) ? ' Kiểm tra vai trò và phạm vi được phụ trách.' : '';
    const error = new Error(`${message}${advice}`);
    error.httpStatus = response.status;
    throw error;
  }
  if (response.headers.get('content-type')?.includes('json')) return response.json();
  return response.blob();
}
function options(list, labelKey = 'name', valueKey = 'id') {
  return (list || []).map((row) => [row[valueKey], row[labelKey] || row.code || row.employee_code || row.id]);
}
function choices(values) { return values.map((value) => [value, text(value)]); }
function field(name, label, type = 'text', extra = {}) { return { name, label, type, ...extra }; }
const noteField = () => field('note', 'Ghi chú / lý do', 'textarea');
function pick(name, label, values, extra = {}) { return field(name, label, 'select', { options: values, ...extra }); }
function form(title, fields, save, done = () => loadPage(), help = '') {
  byId('form-title').textContent = title;
  byId('form-help').textContent = help;
  byId('form-error').textContent = '';
  byId('fields').replaceChildren();
  const controls = {};
  for (const definition of fields) {
    const label = node('label', definition.label, byId('fields'));
    const input = node(definition.type === 'textarea' ? 'textarea' : definition.type === 'select' ? 'select' : 'input', undefined, label);
    controls[definition.name] = input;
    if (definition.type === 'select') {
      node('option', 'Chọn…', input).value = '';
      for (const [value, name] of definition.options || []) node('option', name, input).value = value;
    } else if (definition.type !== 'textarea') input.type = definition.type;
    input.name = definition.name;
    input.required = definition.required !== false && definition.type !== 'checkbox';
    if (definition.type === 'checkbox') { input.checked = !!definition.value; label.className = 'check'; }
    else if (definition.value !== undefined) input.value = definition.value;
    if (definition.min !== undefined) input.min = definition.min;
    if (definition.accept) input.accept = definition.accept;
    if (definition.help) node('small', definition.help, label);
  }
  byId('action-form').onsubmit = async (event) => {
    event.preventDefault(); if (state.writing) return;
    const values = {};
    for (const definition of fields) {
      const control = controls[definition.name];
      values[definition.name] = definition.type === 'checkbox' ? control.checked : definition.type === 'file' ? control.files[0] : definition.type === 'number' ? Number(control.value) : control.value.trim();
    }
    state.writing = true; byId('confirm').disabled = true; byId('role').disabled = true;
    byId('cancel-dialog').disabled = true; byId('close-dialog').disabled = true;
    byId('form-error').textContent = '';
    try {
      const result = await save(values);
      byId('dialog').close(); notify('Đã lưu thành công.');
      try { await done(result); } catch (error) { reportError(new Error(`Thao tác đã lưu, nhưng chưa tải được dữ liệu mới: ${error.message}`)); }
    } catch (error) { byId('form-error').textContent = error.message; }
    finally { state.writing = false; byId('confirm').disabled = false; byId('role').disabled = false; byId('cancel-dialog').disabled = false; byId('close-dialog').disabled = false; }
  };
  byId('dialog').showModal();
}
function heading(title, description = '') {
  screen.replaceChildren();
  const bar = node('div', undefined, screen); bar.className = 'heading';
  const left = node('div', undefined, bar); node('h1', title, left); if (description) node('p', description, left);
  return bar;
}
function table(parent, rows, columns, actions) {
  if (!rows.length) { node('p', 'Chưa có dữ liệu cho vai trò này. Bạn có thể tạo mới hoặc đổi vai trò để xem phần được phụ trách.', parent).className = 'empty'; return; }
  const wrap = node('div', undefined, parent); wrap.className = 'table-wrap';
  const grid = node('table', undefined, wrap); const head = node('tr', undefined, node('thead', undefined, grid));
  for (const [title] of columns) node('th', title, head);
  if (actions) node('th', 'Thao tác', head);
  const tbody = node('tbody', undefined, grid);
  for (const row of rows) {
    const tr = node('tr', undefined, tbody);
    for (const [, render] of columns) node('td', render(row), tr);
    if (actions) { const td = node('td', undefined, tr); const group = node('div', undefined, td); group.className = 'actions'; actions(group, row); }
  }
}
function summary(parent, pairs) {
  const grid = node('div', undefined, parent); grid.className = 'summary';
  for (const [label, value] of pairs) { const cell = node('div', undefined, grid); node('small', label, cell); node('strong', value, cell); }
}
function actions(parent = screen) { const group = node('div', undefined, parent); group.className = 'actions'; return group; }
const manager = () => ['management', 'admin'].includes(state.actor);
const staff = () => ['technical', 'security'].includes(state.actor);
function navigate(page, resource = null) { state.page = page; state.resource = resource; renderNavigation(); return loadPage(); }
function renderNavigation() {
  const menus = [['tickets', 'Yêu cầu'], ['chats', 'Trao đổi với lễ tân'], ['approvals', 'Chờ xác nhận'], ['notifications', 'Thông báo']];
  if (state.actor !== 'resident') menus.splice(1, 2, ['work', staff() ? 'Công việc của tôi' : 'Điều phối công việc'], ['approvals', 'Phê duyệt'], ['security', 'An ninh'], ['rooms', 'Phòng ban quản lý'], ['knowledge', 'Tra cứu tri thức']);
  if (manager()) menus.push(['reports', 'Báo cáo']);
  if (state.actor === 'admin') menus.push(['memory', 'Duyệt bộ nhớ']);
  byId('navigation').replaceChildren();
  for (const [page, title] of menus) {
    const item = button(byId('navigation'), title, () => navigate(page));
    item.className = state.page === page || (page === 'tickets' && state.page === 'ticket') || (page === 'work' && state.page === 'order') ? 'active' : '';
  }
}
async function loadPage() {
  const generation = ++state.generation;
  const actor = state.actor;
  screen.replaceChildren(node('p', 'Đang tải dữ liệu…'));
  try {
    const fixture = await api('/demo/fixtures');
    if (generation !== state.generation || actor !== state.actor) return;
    state.fixtures = fixture;
    state.catalogs = state.actor === 'resident' ? fixture : await api('/catalogs');
    if (generation !== state.generation || actor !== state.actor) return;
    // Each view checks its generation before drawing async results.
    await views[state.page](generation);
  } catch (error) {
    if (generation !== state.generation) return;
    heading('Chưa tải được dữ liệu'); node('p', error.message, screen);
    button(screen, 'Thử tải lại', loadPage); reportError(error);
  }
}
const current = (generation) => generation === state.generation;
const categoryOptions = () => options(state.catalogs.serviceCategories || state.fixtures.categories);
const severityOptions = () => choices(['unknown', 'minor', 'moderate', 'major', 'critical', 'not_applicable']);
const localDateTime = (minutes = 0) => { const moment = new Date(Date.now() + minutes * 60000); return new Date(moment.getTime() - moment.getTimezoneOffset() * 60000).toISOString().slice(0, 16); };
const views = {};

views.tickets = async (generation) => {
  const result = await api(state.actor === 'resident' ? '/resident/tickets?limit=100' : '/tickets?limit=100'); if (!current(generation)) return;
  const bar = heading(state.actor === 'resident' ? 'Yêu cầu của tôi' : 'Yêu cầu cần xử lý', 'Chọn yêu cầu để xem tiến độ và thực hiện bước tiếp theo.');
  if (state.actor === 'resident') button(bar, 'Gửi yêu cầu mới', createResidentRequest, true);
  table(screen, result.items || [], [['Yêu cầu', (r) => r.title], ['Mã', (r) => r.code || '—'], ['Trạng thái', (r) => text(r.status)], ['Ưu tiên', (r) => text(r.priority)], ['Ngày tạo', (r) => date(r.created_at)]], (group, row) => button(group, 'Xem chi tiết', () => navigate('ticket', row.id)));
};
function createResidentRequest(channelId = null) {
  let activeChannelId = channelId;
  form('Gửi yêu cầu hỗ trợ', [
    field('title', 'Tiêu đề'), field('description', 'Mô tả sự cố / nhu cầu', 'textarea'),
    pick('domain_id', 'Khu vực dịch vụ', options(state.fixtures.domains)), pick('building_id', 'Tòa nhà', options(state.fixtures.buildings)),
    pick('unit_id', 'Căn hộ của bạn', options(state.fixtures.myUnits, 'code')), pick('category_id', 'Loại dịch vụ', categoryOptions()),
    pick('request_kind', 'Loại yêu cầu', [['incident', 'Báo sự cố'], ['service_request', 'Yêu cầu dịch vụ']], { value: 'incident' }),
    field('contact_name', 'Tên người liên hệ'), field('contact_phone', 'Số điện thoại', 'tel'),
  ], async (values) => {
    if (!activeChannelId) activeChannelId = (await api('/resident/chats', 'POST', { title: values.title })).id;
    return api(`/resident/chats/${encodeURIComponent(activeChannelId)}/tickets`, 'POST', values);
  }, (result) => navigate('ticket', result.id || result.ticket?.id), 'Yêu cầu được gửi đến ban quản lý phụ trách tòa nhà.');
}

views.ticket = async (generation) => {
  const id = state.resource;
  const result = await api(`${state.actor === 'resident' ? '/resident' : ''}/tickets/${id}`); if (!current(generation)) return;
  const ticket = result.ticket; const bar = heading(ticket.title, ticket.code || '');
  button(bar, 'Danh sách yêu cầu', () => navigate('tickets'));
  summary(screen, [['Trạng thái', text(ticket.status)], ['Ưu tiên', text(ticket.priority)], ['Mức độ', text(ticket.severity)], ['Cập nhật', date(ticket.updated_at)]]);
  node('p', ticket.description || 'Chưa có mô tả.', screen).className = 'detail-text';
  if (manager()) {
    const group = actions();
    button(group, 'Tiếp nhận yêu cầu', () => form('Tiếp nhận yêu cầu', [], () => api(`/tickets/${id}/routing/ack`, 'POST'), () => loadPage(), 'Xác nhận ban quản lý đã nhận và sẽ xử lý yêu cầu này.'));
    button(group, 'Đánh giá sự cố', () => form('Đánh giá sự cố', [pick('stage', 'Giai đoạn', [['intake', 'Tiếp nhận'], ['specialist', 'Chuyên môn'], ['onsite', 'Tại hiện trường'], ['reassessment', 'Đánh giá lại']]), pick('severity', 'Mức độ', severityOptions()), pick('urgency', 'Mức khẩn', [['unknown', 'Chưa rõ'], ['routine', 'Thông thường'], ['soon', 'Sớm'], ['immediate', 'Ngay lập tức']]), field('rationale', 'Nhận định', 'textarea')], (v) => api(`/tickets/${id}/assessments`, 'POST', { ...v, version: ticket.version, facts: {}, idempotency_key: crypto.randomUUID() })));
    if (['open', 'triaging'].includes(ticket.status)) button(group, 'Tạo công việc', () => form('Tạo công việc', [pick('category_id', 'Chuyên môn xử lý', categoryOptions(), { value: ticket.category_id }), field('description', 'Nội dung công việc', 'textarea', { value: ticket.description })], (v) => api(`/tickets/${id}/work-orders`, 'POST', { ...v, required_specialty_id: v.category_id, ticket_version: ticket.version }), (order) => navigate('order', order.id)), true);
    button(group, 'Đánh giá & duyệt triage', () => showTriage(ticket));
    if (result.workOrders) { node('h2', 'Công việc liên quan', screen); drawOrders(result.workOrders); }
  }
  node('h2', 'Lịch sử xử lý', screen); const timeline = node('ol', undefined, screen); timeline.className = 'timeline';
  for (const event of result.events || []) node('li', `${date(event.occurred_at)} · ${eventLabel(event.event_type)}${event.to_status ? ` · ${text(event.to_status)}` : ''}`, timeline);
};
function eventLabel(value) {
  return ({ 'ticket.created': 'Đã tạo yêu cầu', 'ticket.routing_accepted': 'BQL đã tiếp nhận', 'ticket.assessed': 'Đã đánh giá', 'work_order.created': 'Đã tạo công việc', 'work_order.offered': 'Đã mời nhận việc', 'work_assignment.responded': 'Nhân viên đã phản hồi', 'work_order.status_changed': 'Cập nhật tiến độ', 'ticket.status_changed': 'Cập nhật yêu cầu', 'water.shutdown_requested': 'Đề nghị khóa nước', 'water.restored': 'Đã mở lại nước', 'work_order.qc_recorded': 'Đã kiểm tra chất lượng' })[value] || 'Ghi nhận xử lý nghiệp vụ';
}
async function showTriage(ticket) {
  const result = await api(`/tickets/${ticket.id}/triage`);
  form('Đề xuất phân loại sự cố', [
    pick('assessment_id', 'Đánh giá làm căn cứ', (result.assessments || []).map((a) => [a.id, `${text(a.severity)} · ${a.rationale || date(a.created_at)}`])),
    pick('severity', 'Mức độ', severityOptions()), pick('priority', 'Ưu tiên', choices(['low', 'normal', 'high', 'critical'])),
    field('is_emergency', 'Tình huống khẩn cấp', 'checkbox'), field('reason', 'Lý do phân loại', 'textarea'),
  ], (v) => api(`/tickets/${ticket.id}/triage-decisions`, 'POST', { ...v, ticket_version: result.ticket.version, idempotency_key: crypto.randomUUID(), review_reason: 'unknown_facts' }), () => loadPage());
  const pending = (result.reviews || []).filter((r) => r.status === 'pending');
  if (pending.length) {
    const container = node('div', undefined, byId('fields')); node('h2', 'Đề xuất đang chờ duyệt', container);
    for (const review of pending) button(container, `Duyệt đề xuất ngày ${date(review.created_at)}`, () => {
      byId('dialog').close(); form('Duyệt phân loại', [pick('decision', 'Kết quả', [['yes', 'Đồng ý'], ['no', 'Từ chối']]), noteField()], (v) => api(`/triage-reviews/${review.id}/decision`, 'POST', { approve: v.decision === 'yes', note: v.note, ticket_version: result.ticket.version }));
    });
  }
}

function drawOrders(rows) {
  table(screen, rows, [['Công việc', (r) => r.description || r.title], ['Yêu cầu', (r) => r.ticket_code || r.ticket_title || '—'], ['Tiến độ', (r) => text(r.status)], ['Ngày tạo', (r) => date(r.created_at)]], (group, row) => button(group, 'Chi tiết', () => navigate('order', row.id)));
}
views.work = async (generation) => {
  const result = await api(staff() ? '/my-work-orders?limit=100' : '/work-orders?limit=100'); if (!current(generation)) return;
  heading(staff() ? 'Công việc của tôi' : 'Điều phối công việc', staff() ? 'Nhận việc, cập nhật tiến độ và ghi nhận bằng chứng.' : 'Chọn công việc để phân công và theo dõi.');
  drawOrders(result.items || []);
};
views.order = async (generation) => {
  const id = state.resource;
  const result = await api(`/work-orders/${id}`); if (!current(generation)) return;
  const order = result.workOrder; const bar = heading(order.description || 'Chi tiết công việc', order.ticket_code || '');
  button(bar, 'Danh sách công việc', () => navigate('work'));
  summary(screen, [['Tiến độ', text(order.status)], ['Lịch hẹn', date(order.scheduled_at)], ['Hoàn thành', date(order.completed_at)]]);
  const group = actions();
  const reload = () => navigate('order', id);
  if (manager() && ['queued', 'offered'].includes(order.status)) button(group, 'Phân công nhân viên', async () => {
    const ticket = await api(`/tickets/${order.ticket_id}`);
    const available = await api(`/staff/available?managementUnitId=${ticket.ticket.management_unit_id}&categoryId=${order.category_id}`);
    form('Mời nhân viên nhận việc', [pick('staff_id', 'Nhân viên đang rảnh', options(available.items, 'employee_code')), field('offer_expires_at', 'Hạn nhận việc', 'datetime-local', { value: localDateTime(60) })], (v) => api(`/work-orders/${id}/assignments`, 'POST', { ...v, offer_expires_at: new Date(v.offer_expires_at).toISOString(), work_order_version: order.version }), reload, available.items.length ? 'Danh sách chỉ gồm nhân viên phù hợp chuyên môn, đang trong ca và còn khả năng nhận việc.' : 'Chưa có nhân viên đủ điều kiện. Hãy kiểm tra phân công đang hoạt động hoặc ca làm việc.');
  }, true);
  const ownStaff = state.fixtures.staff?.find((s) => s.user_id === state.fixtures.actorId);
  const offered = result.assignments.find((a) => a.status === 'offered' && a.staff_id === ownStaff?.id && new Date(a.offer_expires_at) > new Date());
  if (offered) {
    button(group, 'Nhận công việc', () => form('Nhận công việc', [field('eta', 'Dự kiến đến nơi', 'datetime-local', { value: localDateTime(30) })], (v) => api(`/assignments/${offered.id}/response`, 'POST', { status: 'accepted', eta_at: new Date(v.eta).toISOString() }), reload), true);
    button(group, 'Từ chối nhận', () => form('Từ chối công việc', [field('reason', 'Lý do', 'textarea')], (v) => api(`/assignments/${offered.id}/response`, 'POST', { status: 'rejected', rejection_reason: v.reason }), reload));
  }
  const accepted = result.assignments.some((a) => a.status === 'accepted' && a.staff_id === ownStaff?.id);
  const transitions = { accepted: [['en_route', 'Bắt đầu di chuyển']], en_route: [['arrived', 'Đã đến hiện trường']], arrived: [['in_progress', 'Bắt đầu xử lý']], awaiting_approval: [['in_progress', 'Tiếp tục xử lý']], in_progress: [['completed', 'Hoàn thành'], ['awaiting_approval', 'Chờ phê duyệt']] };
  if (accepted || state.actor === 'admin') for (const [status, label] of transitions[order.status] || []) button(group, label, () => form(label, [noteField()], (v) => api(`/work-orders/${id}/status`, 'PATCH', { status, note: v.note, version: order.version }), reload), status !== 'awaiting_approval');
  if ((accepted || state.actor === 'admin') && ['queued', 'offered', 'accepted', 'en_route', 'awaiting_approval'].includes(order.status)) button(group, 'Hủy công việc', () => form('Hủy công việc', [noteField()], (v) => api(`/work-orders/${id}/status`, 'PATCH', { status: 'cancelled', note: v.note, version: order.version }), reload));
  if (accepted || manager()) {
    button(group, 'Thêm ảnh bằng chứng', () => form('Thêm ảnh hiện trường', [field('image', 'Ảnh PNG / JPEG / WebP', 'file', { accept: 'image/png,image/jpeg,image/webp' }), pick('purpose', 'Loại bằng chứng', [['before', 'Trước xử lý'], ['after', 'Sau xử lý'], ['verification', 'Xác minh hoàn thành'], ['issue', 'Ảnh sự cố']]), field('caption', 'Mô tả ảnh', 'textarea')], async (v) => {
      if (v.image.size > 10 * 1024 * 1024) throw new Error('Ảnh tối đa 10 MB.');
      const query = new URLSearchParams({ filename: v.image.name, mimeType: v.image.type, purpose: v.purpose === 'verification' ? 'after' : v.purpose });
      const file = await api(`/tickets/${order.ticket_id}/files?${query}`, 'POST', v.image, true);
      await api(`/tickets/${order.ticket_id}/evidence`, 'POST', { file_id: file.fileId, purpose: v.purpose, caption: v.caption, work_order_id: id, ...(accepted ? { assignment_id: result.assignments.find((a) => a.status === 'accepted' && a.staff_id === ownStaff?.id).id } : {}) });
    }, reload));
    button(group, 'Kế hoạch vệ sinh', () => cleaningForm(order));
    button(group, 'Tiến độ nhà thầu', () => contractorForm(order));
    button(group, 'Đề nghị ngân sách', () => form('Đề nghị ngân sách', [pick('reviewer_user_id', 'Người phê duyệt', options(state.fixtures.reviewers)), field('amount_vnd', 'Số tiền (VND)', 'number', { min: 1 }), field('purpose', 'Mục đích', 'textarea')], (v) => api(`/work-orders/${id}/budget-approvals`, 'POST', v), reload));
  }
  if (accepted) button(group, 'Đề nghị khóa nước', () => form('Đề nghị khóa nước', [field('reason', 'Lý do', 'textarea'), pick('affected_scope_id', 'Phạm vi ảnh hưởng', (state.fixtures.scopes || []).filter((s) => s.kind === 'building' || s.kind === 'zone').map((s) => [s.id, s.name || (s.kind === 'building' ? 'Tòa nhà' : 'Khu vực')])), field('planned_start', 'Bắt đầu dự kiến', 'datetime-local', { value: localDateTime(60) }), field('planned_end', 'Kết thúc dự kiến', 'datetime-local', { value: localDateTime(120) })], (v) => api(`/work-orders/${id}/water-shutdown-request`, 'POST', { ...v, planned_start: new Date(v.planned_start).toISOString(), planned_end: new Date(v.planned_end).toISOString() }), reload));
  if (manager() && order.status === 'completed') button(group, 'Kiểm tra chất lượng', () => form('Kiểm tra chất lượng', [pick('outcome', 'Kết quả', choices(['pass', 'fail', 'inconclusive'])), field('redo_required', 'Yêu cầu làm lại nếu không đạt', 'checkbox'), noteField()], (v) => api(`/work-orders/${id}/qc`, 'POST', { ...v, criteria: [] }), reload));
  const qc = result.qcResults[0];
  if (manager() && qc?.outcome === 'fail' && qc.redo_required && !result.redoOrders.some((r) => r.qc_result_id === qc.id)) button(group, 'Tạo công việc làm lại', () => form('Yêu cầu làm lại', [field('instruction', 'Hướng dẫn khắc phục', 'textarea')], (v) => api(`/work-orders/${id}/redo`, 'POST', { ...v, qc_result_id: qc.id, work_order_version: order.version }), (r) => navigate('order', r.id)));
  node('h2', 'Phân công', screen);
  table(screen, result.assignments || [], [['Nhân viên', (r) => state.fixtures.staff?.find((s) => s.id === r.staff_id)?.name || state.fixtures.staff?.find((s) => s.id === r.staff_id)?.employee_code || 'Nhân viên'], ['Trạng thái', (r) => text(r.status)], ['Dự kiến đến', (r) => date(r.eta_at)], ['Hạn nhận', (r) => date(r.offer_expires_at)]]);
  node('h2', 'Kiểm tra chất lượng', screen);
  table(screen, result.qcResults || [], [['Kết quả', (r) => text(r.outcome)], ['Yêu cầu làm lại', (r) => r.redo_required ? 'Có' : 'Không'], ['Ghi chú', (r) => r.note || '—']]);
  const water = await api(`/work-orders/${id}/water-interruptions`); if (!current(generation)) return;
  node('h2', 'Khóa nước', screen);
  table(screen, water.items || [], [['Lý do', (r) => r.reason], ['Trạng thái', (r) => text(r.status)], ['Bắt đầu', (r) => date(r.planned_start)], ['Kết thúc', (r) => date(r.planned_end)]], (buttons, r) => {
    if (manager() && r.status === 'approved') button(buttons, 'Thông báo cư dân', () => form('Thông báo khóa nước', [], () => api(`/water-interruptions/${r.id}/notify`, 'POST'), reload, 'Gửi thông báo trong ứng dụng cho cư dân thuộc phạm vi ảnh hưởng.'));
    if (accepted && ['notified', 'active'].includes(r.status)) button(buttons, r.status === 'active' ? 'Mở lại nước' : 'Bắt đầu khóa nước', () => form(r.status === 'active' ? 'Mở lại nước' : 'Khóa nước', [], () => api(`/water-interruptions/${r.id}/${r.status === 'active' ? 'restore' : 'start'}`, 'POST'), reload, 'Xác nhận đã thực hiện thao tác tại hiện trường.'));
  });
  const evidence = await api(`/tickets/${order.ticket_id}/evidence`); if (!current(generation)) return;
  node('h2', 'Bằng chứng hiện trường', screen);
  table(screen, (evidence.items || []).filter((e) => e.work_order_id === id), [['Ảnh', (r) => r.original_name], ['Mô tả', (r) => r.caption || '—'], ['Loại', (r) => ({ before: 'Trước xử lý', after: 'Sau xử lý', verification: 'Xác minh', issue: 'Sự cố' })[r.purpose] || r.purpose]], (buttons, r) => button(buttons, 'Xem ảnh', () => download(`/files/${r.file_id}/content`, r.original_name)));
};

async function cleaningForm(order) {
  const plan = await optionalRecord(`/work-orders/${order.id}/cleaning-plan`);
  form('Kế hoạch vệ sinh', [field('instruction', 'Phương án / nguyên nhân / checklist', 'textarea', { value: plan?.plan?.instruction || '' }), pick('status', 'Tiến độ', choices(['draft', 'in_progress', 'completed', 'cancelled']), { value: plan?.status || 'draft' })], (v) => api(`/work-orders/${order.id}/cleaning-plan`, 'PUT', { plan: { ...(plan?.plan || {}), instruction: v.instruction }, status: v.status, version: plan?.version ?? null }));
}
async function contractorForm(order) {
  const progress = await optionalRecord(`/work-orders/${order.id}/contractor`);
  form('Tiến độ nhà thầu', [pick('status', 'Trạng thái', choices(['pending', 'accepted', 'rejected', 'in_progress', 'completed']), { value: progress?.status || 'pending' }), field('worker_name', 'Tên người thực hiện', 'text', { required: false, value: progress?.worker_name || '' }), field('material', 'Vật tư bổ sung', 'text', { required: false }), field('quantity', 'Số lượng bổ sung', 'number', { required: false, min: 0, value: 1 }), noteField()], (v) => api(`/work-orders/${order.id}/contractor`, 'PUT', { status: v.status, worker_name: v.worker_name || null, materials: [...(progress?.materials || []), ...(v.material ? [{ name: v.material, quantity: v.quantity }] : [])], note: v.note, version: progress?.version ?? null }));
}

async function optionalRecord(path) {
  try { return await api(path); }
  catch (error) { if (error.httpStatus === 404) return null; throw error; }
}

views.approvals = async (generation) => {
  const resident = state.actor === 'resident';
  const result = await api(resident ? '/resident/approvals' : '/approvals'); if (!current(generation)) return;
  heading(resident ? 'Xác nhận của tôi' : 'Phê duyệt yêu cầu', resident ? 'Kiểm tra kết quả sửa chữa trước khi xác nhận.' : 'Đọc yêu cầu và quyết định theo phạm vi phụ trách.');
  table(screen, result.items || [], [['Yêu cầu', (r) => r.ticket_title || text(r.kind)], ['Loại', (r) => text(r.kind)], ['Trạng thái', (r) => text(r.status)], ['Ngày tạo', (r) => date(r.created_at)]], (group, row) => {
    if (row.status === 'pending') button(group, resident ? 'Xác nhận / trả lại' : 'Duyệt / từ chối', () => form(resident ? 'Xác nhận kết quả' : 'Quyết định phê duyệt', [pick('decision', 'Quyết định', [['approved', resident ? 'Đồng ý / hoàn thành' : 'Phê duyệt'], ['rejected', resident ? 'Chưa đạt / yêu cầu xử lý lại' : 'Từ chối']]), noteField()], (v) => api(`${resident ? '/resident' : ''}/approvals/${row.id}/decision`, 'POST', resident ? { approved: v.decision === 'approved', note: v.note } : { status: v.decision, note: v.note })));
  });
  if (!resident) {
    const budget = await api('/budget-approvals'); if (!current(generation)) return;
    node('h2', 'Ngân sách', screen);
    table(screen, budget.items || [], [['Mục đích', (r) => r.purpose], ['Số tiền', (r) => Number(r.amount_vnd).toLocaleString('vi-VN') + ' VND'], ['Trạng thái', (r) => text(r.status)]], (group, row) => {
      if (row.status === 'pending') button(group, 'Quyết định', () => form('Duyệt ngân sách', [pick('status', 'Kết quả', choices(['approved', 'rejected'])), noteField()], (v) => api(`/budget-approvals/${row.id}/decision`, 'POST', { ...v, version: row.version })));
    });
  }
};

views.chats = async (generation) => {
  const result = await api('/resident/chats?limit=100'); if (!current(generation)) return;
  const bar = heading('Trao đổi với lễ tân', 'Tạo cuộc trao đổi và gửi yêu cầu hỗ trợ.');
  button(bar, 'Cuộc trao đổi mới', () => form('Trao đổi với lễ tân', [field('title', 'Chủ đề')], (v) => api('/resident/chats', 'POST', v), (r) => navigate('conversation', { id: r.id, name: r.name, resident: true })), true);
  table(screen, result.items || [], [['Chủ đề', (r) => r.name], ['Gần nhất', (r) => date(r.last_message_at || r.created_at)]], (group, row) => button(group, 'Mở trao đổi', () => navigate('conversation', { id: row.id, name: row.name, resident: true, ticketId: row.ticket_id })));
};
views.rooms = async (generation) => {
  const result = await api('/rooms'); if (!current(generation)) return;
  heading('Phòng ban quản lý', 'Trao đổi cùng các thành viên và agent trong phòng.');
  table(screen, result.items || [], [['Phòng', (r) => r.name], ['Mô tả', (r) => r.description || '—']], (group, row) => button(group, 'Vào phòng', () => navigate('conversation', { id: row.id, name: row.name, resident: false })));
};
views.conversation = async (generation) => {
  const room = state.resource;
  const path = room.resident ? `/resident/chats/${encodeURIComponent(room.id)}` : `/rooms/${encodeURIComponent(room.id)}`;
  const result = await api(`${path}/messages?limit=100`); if (!current(generation)) return;
  const bar = heading(room.name || 'Trao đổi'); button(bar, 'Danh sách', () => navigate(room.resident ? 'chats' : 'rooms'));
  const group = actions();
  button(group, 'Gửi tin nhắn', () => form('Gửi tin nhắn', [field('text', 'Nội dung', 'textarea'), ...(!room.resident ? [pick('mention_agent_id', 'Nhờ agent hỗ trợ (tùy chọn)', options((state.fixtures.roomAgents || []).filter((a) => a.channel_id === room.id)), { required: false })] : [])], async (v) => {
    const message = await api(`${path}/messages`, 'POST', { text: v.text, client_message_id: crypto.randomUUID(), ...(!room.resident && v.mention_agent_id ? { mention_agent_id: v.mention_agent_id } : {}) });
    if (v.mention_agent_id) { const mention = await api(`${path}/mentions/${message.id}`); notify(mention.items.some((m) => m.status === 'done') ? 'Agent demo đã phản hồi trong phòng.' : 'Đã gửi yêu cầu tới agent. Làm mới để xem phản hồi.'); }
  }), true);
  if (room.resident && !room.ticketId) button(group, 'Tạo yêu cầu từ trao đổi', () => createResidentRequest(room.id));
  if (room.ticketId) button(group, 'Xem yêu cầu', () => navigate('ticket', room.ticketId));
  for (const message of result.items || []) {
    const item = node('article', undefined, screen); item.className = 'message';
    node('small', `${message.sender_kind === 'agent' ? 'Trợ lý demo' : 'Thành viên'} · ${date(message.created_at)}`, item);
    const body = message.body;
    node('p', typeof body === 'string' ? body : body?.text || body?.content || 'Tin nhắn đính kèm', item);
  }
  if (!result.items?.length) node('p', 'Chưa có tin nhắn. Bấm Gửi tin nhắn để bắt đầu.', screen).className = 'empty';
};

views.security = async (generation) => {
  const selectedSite = state.resource || state.fixtures.sites?.[0]?.id;
  if (!selectedSite) { heading('An ninh'); node('p', 'Chưa có khu vực an ninh trong database.', screen); return; }
  const query = new URLSearchParams({ siteId: selectedSite });
  const [checkpoints, incidents, handovers] = await Promise.all([api(`/security/checkpoints?${query}`), api(`/security/incidents?${query}`), api(`/security/handovers?${query}`)]);
  if (!current(generation)) return;
  heading('An ninh', 'Tuần tra, ghi nhận sự cố và bàn giao ca.');
  const filter = node('div', undefined, screen); filter.className = 'filters';
  const label = node('label', 'Khu vực', filter); const select = node('select', undefined, label);
  for (const [value, name] of options(state.fixtures.sites)) node('option', name, select).value = value;
  select.value = selectedSite; select.onchange = () => navigate('security', select.value);
  const group = actions();
  if (state.actor === 'admin') button(group, 'Thêm điểm tuần tra', () => form('Thêm điểm tuần tra', [field('name', 'Tên điểm'), field('location', 'Vị trí')], (v) => api('/security/checkpoints', 'POST', { ...v, site_id: selectedSite, sort_order: 0 })));
  button(group, 'Báo cáo sự cố', () => form('Báo cáo sự cố an ninh', [field('title', 'Tiêu đề'), field('location', 'Vị trí'), pick('business_severity', 'Mức độ', [['P0', 'P0 · Khẩn cấp'], ['P1', 'P1 · Nghiêm trọng'], ['P2', 'P2 · Trung bình'], ['P3', 'P3 · Nhẹ']]), field('description', 'Diễn biến / thông tin hiện trường', 'textarea')], (v) => api('/security/incidents', 'POST', { site_id: selectedSite, title: v.title, location: v.location, business_severity: v.business_severity, report: { description: v.description } })), true);
  button(group, 'Bàn giao ca', () => form('Bàn giao ca', [pick('shift_name', 'Ca làm việc', choices(['ca_sang', 'ca_chieu', 'ca_dem'])), field('shift_date', 'Ngày làm việc', 'date', { value: new Date().toISOString().slice(0, 10) }), pick('to_user_id', 'Người nhận bàn giao', options(state.fixtures.staff, 'name', 'user_id')), field('note', 'Nội dung bàn giao', 'textarea')], (v) => api('/security/handovers', 'POST', { site_id: selectedSite, shift_name: v.shift_name, shift_date: v.shift_date, to_user_id: v.to_user_id, payload: { note: v.note } })));
  node('h2', 'Điểm tuần tra', screen);
  table(screen, checkpoints.items || [], [['Điểm kiểm tra', (r) => r.name], ['Vị trí', (r) => r.location], ['Trạng thái', (r) => text(r.status)], ['Kiểm tra lúc', (r) => date(r.checked_at)]], (buttons, r) => button(buttons, 'Ghi nhận kiểm tra', () => form('Ghi nhận tuần tra', [pick('status', 'Kết quả', choices(['checked', 'missed'])), field('notes', 'Ghi chú', 'textarea', { required: false })], (v) => api(`/security/checkpoints/${r.id}`, 'PATCH', v))));
  node('h2', 'Sự cố', screen);
  table(screen, incidents.items || [], [['Sự cố', (r) => r.title], ['Vị trí', (r) => r.location], ['Mức độ', (r) => ({ p1: 'P0 · Khẩn cấp', p2: 'P1 · Nghiêm trọng', p3: 'P2 · Trung bình', p4: 'P3 · Nhẹ' })[r.severity]], ['Trạng thái', (r) => text(r.status)]], (buttons, r) => button(buttons, 'Cập nhật xử lý', () => form('Cập nhật sự cố', [pick('status', 'Kết quả xử lý', choices(['investigating', 'resolved', 'escalated_to_police'])), field('description', 'Ghi nhận xử lý', 'textarea', { value: r.report?.description || '' })], (v) => api(`/security/incidents/${r.id}`, 'PATCH', { status: v.status, report: { ...r.report, description: v.description } }), () => loadPage(), 'Chuyển cấp chỉ ghi trạng thái demo trong hệ thống, không gọi hoặc gửi tin cho cơ quan bên ngoài.')));
  node('h2', 'Bàn giao ca', screen);
  table(screen, handovers.items || [], [['Ca', (r) => text(r.shift_name)], ['Ngày', (r) => r.shift_date], ['Nội dung', (r) => r.payload?.note || '—'], ['Trạng thái', (r) => r.confirmed ? 'Đã nhận bàn giao' : 'Chờ người nhận']], (buttons, r) => {
    if (!r.confirmed && (r.to_user_id === state.fixtures.actorId || state.actor === 'admin')) button(buttons, 'Nhận bàn giao', () => form('Xác nhận bàn giao', [], () => api(`/security/handovers/${r.id}/confirm`, 'POST'), () => loadPage(), 'Xác nhận đã đọc và nhận nội dung bàn giao ca.'));
  });
};

views.notifications = async (generation) => {
  const result = await api('/my/notifications?limit=100'); if (!current(generation)) return;
  heading('Thông báo');
  table(screen, result.items || [], [['Nội dung', (r) => notificationLabel(r.payload)], ['Thời gian', (r) => date(r.created_at)], ['Trạng thái', (r) => r.read_at ? 'Đã đọc' : 'Chưa đọc']], (group, row) => {
    if (!row.read_at) button(group, 'Đánh dấu đã đọc', () => form('Đánh dấu đã đọc', [], () => api(`/my/notifications/${row.id}/read`, 'POST')));
  });
};
function notificationLabel(payload) {
  const type = payload?.type || '';
  return ({ 'water.shutdown': 'Thông báo khóa nước', 'water.restored': 'Đã mở lại nước', 'ticket.created': 'Yêu cầu mới được gửi đến ban quản lý', 'ticket.routing_accepted': 'Ban quản lý đã tiếp nhận yêu cầu' })[type] || payload?.title || payload?.message || 'Có cập nhật về yêu cầu của bạn';
}

views.knowledge = async (generation) => {
  if (!current(generation)) return; heading('Tra cứu tri thức', 'Tìm nội dung đã xuất bản trong phạm vi của bạn.');
  button(screen, 'Tìm tài liệu', () => form('Tra cứu tài liệu', [pick('domainId', 'Phạm vi dịch vụ', options(state.fixtures.domains)), field('query', 'Từ khóa')], (v) => api(`/knowledge/search?${new URLSearchParams(v)}`), (result) => {
    heading('Kết quả tra cứu'); button(screen, 'Tìm tiếp', () => navigate('knowledge'));
    for (const row of result.items || []) { node('h2', row.title, screen); node('p', row.text_content, screen).className = 'detail-text'; }
    if (!result.items?.length) node('p', 'Không có tài liệu phù hợp trong phạm vi được phép.', screen).className = 'empty';
  }), true);
};
async function download(path, filename) {
  const blob = await api(path); const url = URL.createObjectURL(blob);
  const link = node('a'); link.href = url; link.download = filename || 'bao-cao.docx'; document.body.append(link); link.click(); link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}
views.reports = async (generation) => {
  if (!current(generation)) return; heading('Báo cáo', 'Doanh thu tính từ hóa đơn đã phát hành. Ngày kết thúc không được tính trong kỳ.');
  for (const [kind, title] of [['incident-frequency', 'Tần suất sự cố'], ['issued-revenue', 'Doanh thu dịch vụ']]) {
    node('h2', title, screen);
    button(screen, 'Chọn kỳ báo cáo', () => form(title, [pick('buildingId', 'Tòa nhà', options(state.fixtures.buildings)), ...(kind === 'issued-revenue' ? [pick('categoryId', 'Loại dịch vụ', categoryOptions())] : []), field('fromDate', 'Từ ngày', 'date', { value: `${new Date().getFullYear()}-01-01` }), field('toDate', 'Đến trước ngày', 'date', { value: `${new Date().getFullYear() + 1}-01-01` })], (v) => {
      if (v.fromDate >= v.toDate) throw new Error('Ngày kết thúc phải sau ngày bắt đầu.');
      return api(`/reports/${kind}?${new URLSearchParams(v)}`).then((result) => ({ result, query: new URLSearchParams(v) }));
    }, ({ result, query }) => {
      heading(title); const group = actions(); button(group, 'Báo cáo khác', () => navigate('reports')); button(group, 'Tải Word', () => download(`/reports/${kind}.docx?${query}`, `${kind}.docx`), true);
      const rows = result.items || [];
      table(screen, rows, kind === 'issued-revenue' ? [['Tháng', (r) => r.month], ['Số hóa đơn', (r) => r.invoice_count], ['Trước thuế', (r) => Number(r.net_amount).toLocaleString('vi-VN')], ['Thuế', (r) => Number(r.tax_amount).toLocaleString('vi-VN')], ['Tổng', (r) => Number(r.billed_amount).toLocaleString('vi-VN') + ' ' + r.currency]] : [['Tháng', (r) => r.month], ['Loại sự cố', (r) => r.incident_type], ['Số sự cố', (r) => r.incident_count]]);
    }));
  }
};
views.memory = async (generation) => {
  const result = await api('/admin/memory-candidates'); if (!current(generation)) return;
  heading('Duyệt bộ nhớ', 'Xem nội dung đề xuất trước khi phê duyệt.');
  table(screen, result.items || [], [['Nội dung đề xuất', (r) => r.proposed_text], ['Đã ẩn dữ liệu cá nhân', (r) => r.pii_redacted ? 'Có' : 'Chưa'], ['Ngày tạo', (r) => date(r.created_at)]], (group, row) => button(group, 'Duyệt đề xuất', () => form('Duyệt bộ nhớ', [pick('decision', 'Quyết định', [['approve', 'Đồng ý'], ['reject', 'Từ chối']]), field('reason', 'Lý do', 'textarea')], (v) => api(`/admin/memory-candidates/${row.id}/review`, 'POST', v))));
};

byId('close-dialog').onclick = byId('cancel-dialog').onclick = () => { if (!state.writing) byId('dialog').close(); };
byId('dialog').addEventListener('cancel', (event) => { if (state.writing) event.preventDefault(); });
byId('role').onchange = () => {
  state.actor = byId('role').value; byId('dialog').close(); notify(`Đang sử dụng vai trò ${roles[state.actor]}.`);
  navigate('tickets').catch(reportError);
};
byId('refresh').onclick = () => { if (!state.writing) { byId('dialog').close(); loadPage(); } };
renderNavigation();
loadPage();
