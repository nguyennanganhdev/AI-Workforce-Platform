export type Row = Record<string, any>;
export async function api<T = Row>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch('/api' + path, {
    credentials: 'same-origin',
    ...init,
    headers: { 'Content-Type': 'application/json', ...init.headers },
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({ detail: `HTTP ${response.status}` }));
    throw new Error(typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail));
  }
  return response.json();
}
export const post = <T = Row>(path: string, body: unknown = {}) =>
  api<T>(path, { method: 'POST', body: JSON.stringify(body) });
export const put = <T = Row>(path: string, body: unknown) =>
  api<T>(path, { method: 'PUT', body: JSON.stringify(body) });
export const money = (micros: number = 0) =>
  new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 4,
  }).format(micros / 1000000);
export const labels: Row = {
  idle: 'Sẵn sàng',
  running: 'Đang xử lý',
  indexing: 'Đang lập chỉ mục',
  needs_input: 'Cần thông tin',
  needs_review: 'Cần kiểm tra',
  blocked: 'Bị chặn',
  awaiting_approval: 'Chờ duyệt',
  cancelled: 'Đã dừng',
  budget_exhausted: 'Hết ngân sách',
  queued: 'Trong hàng đợi',
  done: 'Hoàn tất',
  failed: 'Thất bại',
  draft: 'Bản nháp',
  published: 'Đã công bố',
  retired: 'Ngừng sử dụng',
  complete: 'Đủ điều kiện',
  candidate: 'Chờ xác minh',
  verified: 'Đã xác minh',
};
