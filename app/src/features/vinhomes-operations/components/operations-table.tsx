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
        <label className="flex flex-col gap-1 text-xs text-slate-600">Tìm kiếm
          <input value={query} placeholder="Nhập mã, tên hoặc nội dung" onChange={(event) => { setQuery(event.target.value); setPage(1); }} />
        </label>
      </div>
      <div className="overflow-x-auto">
        <table>
          <thead><tr>{columns.map((column) => <th scope="col" key={column}>{column}</th>)}<th scope="col">Thao tác</th></tr></thead>
          <tbody>
            {filtered.slice((currentPage - 1) * 10, currentPage * 10).map((row) => <tr key={row.id}>
              {row.cells.map((cell, index) => <td key={columns[index]}>{cell}</td>)}
              <td><button type="button" className="operations-text-action" aria-label={`${actionLabel} ${row.id}`} onClick={() => onSelect(row.id)}>{actionLabel}</button></td>
            </tr>)}
            {!filtered.length && <tr><td colSpan={columns.length + 1} className="text-center py-12">Không có dữ liệu phù hợp.</td></tr>}
          </tbody>
        </table>
      </div>
      <div className="operations-table-toolbar">
        <span role="status">{filtered.length} kết quả · Trang {currentPage}/{pages}</span>
        <div className="flex gap-2">
          <button type="button" disabled={currentPage === 1} onClick={() => setPage(currentPage - 1)}>Trang trước</button>
          <button type="button" disabled={currentPage === pages} onClick={() => setPage(currentPage + 1)}>Trang sau</button>
        </div>
      </div>
    </section>
  );
}
