import { useState, type ReactNode } from 'react';

export interface OperationsRow {
  id: string;
  search: string;
  cells: ReactNode[];
}

/** Shared list controls; callers supply only records already allowed by their role. */
export function OperationsTable({ title, columns, rows, onSelect, actionLabel = 'Xem chi tiết', filters }: {
  title: string; columns: string[]; rows: OperationsRow[];
  onSelect: (id: string) => void; actionLabel?: string;
  filters?: ReactNode;
}) {
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(1);
  const normalize = (text: string) => text.normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/đ/gi, 'd').toLowerCase();
  const filtered = rows.filter((row) => normalize(row.search).includes(normalize(query.trim())));
  const pages = Math.max(1, Math.ceil(filtered.length / 10));
  const currentPage = Math.min(page, pages);
  return (
    <section className="operations-table" aria-label={title}>
      <div className="operations-table-toolbar">
        <h2>{title} <span className="text-slate-500 font-normal">({rows.length})</span></h2>
        {filters}
        <label className="flex flex-col gap-1 text-xs text-slate-600 w-full sm:w-auto">Tìm kiếm
          <input value={query} placeholder="Nhập mã, tên hoặc nội dung" onChange={(event) => { setQuery(event.target.value); setPage(1); }} />
        </label>
      </div>
      {/* Mobile Card View (< 768px): KHÔNG CẦN VUỐT NGANG */}
      <div className="md:hidden divide-y divide-slate-100 bg-white">
        {filtered.slice((currentPage - 1) * 10, currentPage * 10).map((row) => (
          <div key={row.id} className="p-3.5 space-y-2 bg-white">
            <div className="space-y-1.5">
              {row.cells.map((cell, index) => {
                const colName = columns[index] || `Cột ${index + 1}`;
                if (index === 0) {
                  return (
                    <div key={colName} className="font-bold text-xs text-slate-800">
                      {cell}
                    </div>
                  );
                }
                return (
                  <div key={colName} className="flex items-start justify-between gap-2 text-xs">
                    <span className="text-slate-400 font-medium shrink-0">{colName}:</span>
                    <span className="text-slate-700 text-right">{cell}</span>
                  </div>
                );
              })}
            </div>
            <div className="flex items-center justify-end pt-2 border-t border-slate-100">
              <button
                type="button"
                className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-[11px] font-bold"
                aria-label={`${actionLabel} ${row.id}`}
                onClick={() => onSelect(row.id)}
              >
                {actionLabel}
              </button>
            </div>
          </div>
        ))}
        {!filtered.length && (
          <div className="text-center py-12 text-slate-500 text-xs">
            Không có dữ liệu phù hợp.
          </div>
        )}
      </div>

      {/* Desktop Table View (>= 768px) */}
      <div className="hidden md:block overflow-x-auto">
        <table>
          <thead>
            <tr>
              {columns.map((column) => (
                <th scope="col" key={column}>
                  {column}
                </th>
              ))}
              <th scope="col">Thao tác</th>
            </tr>
          </thead>
          <tbody>
            {filtered.slice((currentPage - 1) * 10, currentPage * 10).map((row) => (
              <tr key={row.id}>
                {row.cells.map((cell, index) => (
                  <td key={columns[index]}>{cell}</td>
                ))}
                <td>
                  <button
                    type="button"
                    className="operations-text-action"
                    aria-label={`${actionLabel} ${row.id}`}
                    onClick={() => onSelect(row.id)}
                  >
                    {actionLabel}
                  </button>
                </td>
              </tr>
            ))}
            {!filtered.length && (
              <tr>
                <td colSpan={columns.length + 1} className="text-center py-12">
                  Không có dữ liệu phù hợp.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <div className="operations-table-toolbar flex-col sm:flex-row items-stretch sm:items-center gap-2.5">
        <span role="status" className="text-xs text-slate-500">{filtered.length} kết quả · Trang {currentPage}/{pages}</span>
        <div className="flex gap-2 justify-between sm:justify-end">
          <button type="button" disabled={currentPage === 1} onClick={() => setPage(currentPage - 1)}>Trang trước</button>
          <button type="button" disabled={currentPage === pages} onClick={() => setPage(currentPage + 1)}>Trang sau</button>
        </div>
      </div>
    </section>
  );
}
