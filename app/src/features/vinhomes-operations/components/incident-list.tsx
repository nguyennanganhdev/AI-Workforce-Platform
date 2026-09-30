import { useState } from 'react';
import type { VhIncident } from '../types/incident';
import { PERSONA_PROFILES } from '../types/persona';

const statuses = { NEW: 'Mới tiếp nhận', OPEN: 'Đang xử lý', RESOLVED: 'Chờ cư dân xác nhận', CLOSED: 'Đã đóng' };
const severities = { P1: 'Khẩn cấp', P2: 'Cao', P3: 'Bình thường', P4: 'Thấp' };
const fieldClass = 'rounded border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 focus:outline-blue-600';
const normalize = (value: string) => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/đ/g, 'd').replace(/Đ/g, 'D').toLowerCase();

export function IncidentList({ incidents, onSelect }: { incidents: VhIncident[]; onSelect: (id: string) => void }) {
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('');
  const [severity, setSeverity] = useState('');
  const [tower, setTower] = useState('');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const towers = [...new Set(incidents.map((item) => item.location_json.towerCode).filter(Boolean))].sort();
  const filtered = incidents.filter((item) =>
    normalize(`${item.id} ${item.title}`).includes(normalize(search.trim())) &&
    (!status || item.status === status) && (!severity || item.severity === severity) &&
    (!tower || item.location_json.towerCode === tower));
  const pageCount = Math.max(1, Math.ceil(filtered.length / pageSize));
  const currentPage = Math.min(page, pageCount);
  const start = (currentPage - 1) * pageSize;

  return (
    <section className="rounded-lg border border-slate-200 bg-white" aria-label="Danh sách sự cố">
      <div className="flex flex-col sm:flex-row sm:flex-wrap items-stretch sm:items-end gap-2.5 sm:gap-3 border-b border-slate-200 p-3 sm:p-5">
        <label className="flex w-full sm:min-w-56 sm:flex-1 flex-col gap-1.5 text-xs font-medium text-slate-600">
          Tìm kiếm sự cố
          <input className={fieldClass} placeholder="Nhập mã hoặc tên sự cố" value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} />
        </label>
        <div className="grid grid-cols-2 sm:flex sm:flex-wrap items-center gap-2 sm:gap-3">
        <label className="flex flex-col gap-1.5 text-xs font-medium text-slate-600">Trạng thái
          <select className={fieldClass} value={status} onChange={(event) => { setStatus(event.target.value); setPage(1); }}>
            <option value="">Tất cả trạng thái</option>
            {Object.entries(statuses).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>
        <label className="flex flex-col gap-1.5 text-xs font-medium text-slate-600">Mức độ
          <select className={fieldClass} value={severity} onChange={(event) => { setSeverity(event.target.value); setPage(1); }}>
            <option value="">Tất cả mức độ</option>
            {Object.entries(severities).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>
        <label className="flex flex-col gap-1.5 text-xs font-medium text-slate-600">Tòa nhà
          <select className={fieldClass} value={tower} onChange={(event) => { setTower(event.target.value); setPage(1); }}>
            <option value="">Tất cả tòa nhà</option>
            {towers.map((value) => <option key={value} value={value}>Tòa {value}</option>)}
          </select>
        </label>
          <button type="button" className={`${fieldClass} col-span-2 sm:col-span-1`} onClick={() => { setSearch(''); setStatus(''); setSeverity(''); setTower(''); setPage(1); }}>Xóa bộ lọc</button>
        </div>
      </div>
      {/* Mobile Card View (< 768px): KHÔNG CẦN VUỐT NGANG */}
      <div className="md:hidden divide-y divide-slate-100 bg-white">
        {filtered.slice(start, start + pageSize).map((item) => {
          const ownerName = Object.values(PERSONA_PROFILES).find((profile) => profile.id === item.owner_user_id)?.name || 'Chưa phân công';
          return (
            <div key={item.id} className="p-3.5 space-y-2.5 bg-white">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1.5 mb-1">
                    <button
                      type="button"
                      className="font-mono font-bold text-xs text-blue-600 hover:underline"
                      onClick={() => onSelect(item.id)}
                    >
                      {item.id}
                    </button>
                    <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full ${
                      item.severity === 'P1'
                        ? 'bg-rose-100 text-rose-700'
                        : item.severity === 'P2'
                          ? 'bg-amber-100 text-amber-800'
                          : 'bg-blue-100 text-blue-700'
                    }`}>
                      {severities[item.severity]}
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={() => onSelect(item.id)}
                    className="font-semibold text-xs text-slate-900 hover:text-blue-700 text-left line-clamp-2"
                  >
                    {item.title}
                  </button>
                </div>
                <span className="shrink-0 text-[10px] font-medium px-2 py-0.5 rounded bg-slate-100 text-slate-700">
                  {statuses[item.status]}
                </span>
              </div>

              <div className="flex items-center justify-between text-[11px] text-slate-500 bg-slate-50/70 rounded-lg px-2.5 py-1.5">
                <div>
                  <span className="text-slate-400">Vị trí: </span>
                  <span className="font-medium text-slate-700">
                    {item.location_json.towerCode ? `Tòa ${item.location_json.towerCode}` : 'Chưa rõ'}
                    {item.location_json.floor != null ? ` · Tầng ${item.location_json.floor}` : ''}
                  </span>
                </div>
                <div className="truncate max-w-[150px] text-right">
                  <span className="text-slate-400">Phụ trách: </span>
                  <span className="font-medium text-slate-700">{ownerName}</span>
                </div>
              </div>

              <div className="flex items-center justify-end pt-1 border-t border-slate-100">
                <button
                  type="button"
                  aria-label={`Xem chi tiết sự cố ${item.id}`}
                  className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-[11px] font-bold"
                  onClick={() => onSelect(item.id)}
                >
                  Chi tiết
                </button>
              </div>
            </div>
          );
        })}
        {!filtered.length && (
          <div className="px-4 py-12 text-center text-slate-500 text-xs">
            Không tìm thấy sự cố phù hợp.
          </div>
        )}
      </div>

      {/* Desktop Table View (>= 768px) */}
      <div className="hidden md:block overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-slate-200 bg-slate-50 text-xs text-slate-600">
            <tr>
              <th scope="col" className="px-3 sm:px-4 py-3 font-semibold">Mã sự cố</th>
              <th scope="col" className="px-3 sm:px-4 py-3 font-semibold">Nội dung</th>
              <th scope="col" className="px-3 sm:px-4 py-3 font-semibold ops-hide-mobile">Vị trí</th>
              <th scope="col" className="px-3 sm:px-4 py-3 font-semibold">Mức độ</th>
              <th scope="col" className="px-3 sm:px-4 py-3 font-semibold ops-hide-mobile">Người phụ trách</th>
              <th scope="col" className="px-3 sm:px-4 py-3 font-semibold">Trạng thái</th>
              <th scope="col" className="px-3 sm:px-4 py-3 font-semibold text-right">Thao tác</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {filtered.slice(start, start + pageSize).map((item) => (
              <tr key={item.id} className="hover:bg-slate-50">
                <td className="whitespace-nowrap px-3 sm:px-4 py-3 sm:py-4"><button type="button" className="font-medium text-blue-600 hover:underline" onClick={() => onSelect(item.id)}>{item.id}</button></td>
                <td className="min-w-44 max-w-sm px-3 sm:px-4 py-3 sm:py-4 text-slate-900">{item.title}</td>
                <td className="whitespace-nowrap px-3 sm:px-4 py-3 sm:py-4 text-slate-600 ops-hide-mobile">{item.location_json.towerCode ? `Tòa ${item.location_json.towerCode}` : 'Chưa xác định'}<br /><span className="text-xs">{item.location_json.floor != null ? `Tầng ${item.location_json.floor}` : ''}</span></td>
                <td className={`whitespace-nowrap px-3 sm:px-4 py-3 sm:py-4 ${item.severity === 'P1' ? 'text-red-700 font-semibold' : 'text-slate-700'}`}>{severities[item.severity]}</td>
                <td className="px-3 sm:px-4 py-3 sm:py-4 text-slate-600 ops-hide-mobile">{Object.values(PERSONA_PROFILES).find((profile) => profile.id === item.owner_user_id)?.name || 'Chưa phân công'}</td>
                <td className="px-3 sm:px-4 py-3 sm:py-4 text-slate-700">{statuses[item.status]}</td>
                <td className="whitespace-nowrap px-3 sm:px-4 py-3 sm:py-4 text-right"><button type="button" aria-label={`Xem chi tiết sự cố ${item.id}`} className="text-blue-600 hover:underline font-medium text-xs sm:text-sm" onClick={() => onSelect(item.id)}>Chi tiết</button></td>
              </tr>
            ))}
            {!filtered.length && <tr><td colSpan={7} className="px-4 py-16 text-center text-slate-500">Không tìm thấy sự cố phù hợp.</td></tr>}
          </tbody>
        </table>
      </div>
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 border-t border-slate-200 p-3 sm:p-4 text-xs sm:text-sm text-slate-600">
        <span role="status">{filtered.length ? `${start + 1}–${Math.min(start + pageSize, filtered.length)} trong ${filtered.length} sự cố` : '0 sự cố'}</span>
        <div className="flex flex-wrap items-center justify-center gap-2 sm:gap-3">
          <label className="hidden sm:inline-flex items-center gap-1">Số dòng <select className={fieldClass} value={pageSize} onChange={(event) => { setPageSize(Number(event.target.value)); setPage(1); }}>{[5, 10, 20].map((value) => <option key={value} value={value}>{value}</option>)}</select></label>
          <button type="button" className={`${fieldClass} disabled:opacity-40`} disabled={currentPage === 1} onClick={() => setPage(currentPage - 1)}>Trang trước</button>
          <span>Trang {currentPage}/{pageCount}</span>
          <button type="button" className={`${fieldClass} disabled:opacity-40`} disabled={currentPage === pageCount} onClick={() => setPage(currentPage + 1)}>Trang sau</button>
        </div>
      </div>
    </section>
  );
}
