import { useState, type ReactNode } from 'react';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { EmptyState, Pagination, Panel, SearchField, normalizeSearch, paginate } from './ops-ui';

export interface OperationsRow {
  id: string;
  search: string;
  cells: ReactNode[];
}

/** Shared list controls; callers supply only records already allowed by their role. */
export function OperationsTable({ title, columns, rows, onSelect, actionLabel = 'Xem chi tiết', filters, titleColumn = 0 }: {
  title: string; columns: string[]; rows: OperationsRow[];
  onSelect: (id: string) => void; actionLabel?: string;
  filters?: ReactNode;
  /** Column whose cell opens the row (and heads the phone card). */
  titleColumn?: number;
}) {
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(1);
  const q = normalizeSearch(query.trim());
  const filtered = q ? rows.filter((row) => normalizeSearch(row.search).includes(q)) : rows;
  const { pages, current, slice } = paginate(filtered, page);

  const action = (row: OperationsRow) => (
    <Button variant="link" className="h-auto px-0" aria-label={`${actionLabel} ${row.id}`} onClick={() => onSelect(row.id)}>
      {actionLabel}
    </Button>
  );

  const titleLink = (row: OperationsRow) => (
    <button type="button" onClick={() => onSelect(row.id)} className="text-left text-foreground hover:text-primary hover:underline underline-offset-2">
      {row.cells[titleColumn]}
    </button>
  );

  return (
    <Panel
      title={title}
      titleAs="h2"
      meta={`${rows.length} mục`}
      toolbar={
        <>
          <div className="min-w-0">{filters}</div>
          <SearchField value={query} placeholder="Tìm theo mã, tên hoặc nội dung" onChange={(v) => { setQuery(v); setPage(1); }} />
        </>
      }
      footer={<Pagination page={current} pages={pages} total={filtered.length} unit="kết quả" onChange={setPage} />}
    >
      {slice.length === 0 ? (
        <EmptyState title={q ? 'Không tìm thấy kết quả phù hợp' : 'Chưa có dữ liệu'} hint={q ? 'Thử từ khóa khác hoặc xóa ô tìm kiếm.' : undefined} />
      ) : (
        <>
          {/* Tablet & desktop */}
          <div className="ops-list-table px-2 md:px-4">
            <Table>
              <TableHeader>
                <TableRow>
                  {columns.map((column) => <TableHead key={column}>{column}</TableHead>)}
                  <TableHead className="text-right">Thao tác</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {slice.map((row) => (
                  <TableRow key={row.id}>
                    {row.cells.map((cell, index) => (
                      <TableCell key={columns[index] || index} className="whitespace-normal">{index === titleColumn ? titleLink(row) : cell}</TableCell>
                    ))}
                    <TableCell className="text-right">{action(row)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          {/* Phone: stacked rows, the title column heads each card */}
          <ul className="ops-list-rows">
            {slice.map((row) => (
              <li key={row.id} className="flex flex-col gap-2">
                <div className="ops-title font-medium">{titleLink(row)}</div>
                <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-[13px]">
                  {row.cells.map((cell, i) => i === titleColumn ? null : (
                    <div key={columns[i] || i} className="contents">
                      <dt className="text-muted-foreground">{columns[i]}</dt>
                      <dd className="min-w-0 text-right text-slate-700">{cell}</dd>
                    </div>
                  ))}
                </dl>
                <div className="flex justify-end">{action(row)}</div>
              </li>
            ))}
          </ul>
        </>
      )}
    </Panel>
  );
}
