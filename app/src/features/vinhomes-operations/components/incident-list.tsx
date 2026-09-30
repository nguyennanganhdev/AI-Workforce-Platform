import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardFooter } from '@/components/ui/card';
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { cn } from '@/lib/utils';
import type { VhIncident } from '../types/incident';
import { PERSONA_PROFILES } from '../types/persona';
import { EmptyState, Pagination, SearchField, normalizeSearch, paginate } from './ops-ui';

const ALL = 'ALL';
const statuses: Record<string, string> = { NEW: 'Mới tiếp nhận', OPEN: 'Đang xử lý', RESOLVED: 'Chờ cư dân xác nhận', CLOSED: 'Đã đóng' };
const severities: Record<string, string> = { P1: 'Khẩn cấp', P2: 'Cao', P3: 'Bình thường', P4: 'Thấp' };

function FilterSelect({ label, value, items, onChange }: { label: string; value: string; items: Record<string, string>; onChange: (v: string) => void }) {
  return (
    <Select items={items} value={value} onValueChange={(v) => onChange((v as string | null) ?? ALL)}>
      <SelectTrigger aria-label={label} className="w-full bg-card md:w-44">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectGroup>
          {Object.entries(items).map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}
        </SelectGroup>
      </SelectContent>
    </Select>
  );
}

const ownerName = (item: VhIncident) =>
  Object.values(PERSONA_PROFILES).find((profile) => profile.id === item.owner_user_id)?.name || 'Chưa phân công';
const place = (item: VhIncident) =>
  `${item.location_json.towerCode ? `Tòa ${item.location_json.towerCode}` : 'Chưa xác định'}${item.location_json.floor != null ? ` · Tầng ${item.location_json.floor}` : ''}`;

export function IncidentList({ incidents, onSelect }: { incidents: VhIncident[]; onSelect: (id: string) => void }) {
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState(ALL);
  const [severity, setSeverity] = useState(ALL);
  const [tower, setTower] = useState(ALL);
  const [page, setPage] = useState(1);
  const towers = [...new Set(incidents.map((item) => item.location_json.towerCode).filter(Boolean))].sort() as string[];
  const q = normalizeSearch(search.trim());
  const filtered = incidents.filter((item) =>
    normalizeSearch(`${item.id} ${item.title}`).includes(q) &&
    (status === ALL || item.status === status) && (severity === ALL || item.severity === severity) &&
    (tower === ALL || item.location_json.towerCode === tower));
  const { pages, current, slice } = paginate(filtered, page);
  const hasFilter = !!search || status !== ALL || severity !== ALL || tower !== ALL;
  const reset = () => { setSearch(''); setStatus(ALL); setSeverity(ALL); setTower(ALL); setPage(1); };
  const withReset = (set: (v: string) => void) => (v: string) => { set(v); setPage(1); };

  return (
    <Card className="gap-4 pb-0" aria-label="Danh sách sự cố">
      <CardContent className="flex flex-col gap-3 px-4 md:flex-row md:flex-wrap md:items-center md:px-6">
        <div className="md:min-w-64 md:flex-1">
          <SearchField value={search} onChange={withReset(setSearch)} placeholder="Tìm theo mã hoặc tên sự cố" />
        </div>
        <div className="grid grid-cols-2 gap-2 md:flex md:flex-wrap md:items-center">
          <FilterSelect label="Trạng thái" value={status} onChange={withReset(setStatus)} items={{ [ALL]: 'Tất cả trạng thái', ...statuses }} />
          <FilterSelect label="Mức độ" value={severity} onChange={withReset(setSeverity)} items={{ [ALL]: 'Tất cả mức độ', ...severities }} />
          <FilterSelect
            label="Tòa nhà"
            value={tower}
            onChange={withReset(setTower)}
            items={{ [ALL]: 'Tất cả tòa nhà', ...Object.fromEntries(towers.map((t) => [t, `Tòa ${t}`])) }}
          />
          <Button variant="ghost" size="lg" disabled={!hasFilter} onClick={reset}>Xóa bộ lọc</Button>
        </div>
      </CardContent>

      {slice.length === 0 ? (
        <EmptyState title="Không tìm thấy sự cố phù hợp" hint={hasFilter ? 'Thử bỏ bớt bộ lọc.' : undefined} />
      ) : (
        <>
          <div className="ops-list-table px-2 md:px-4">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Sự cố</TableHead>
                  <TableHead>Vị trí</TableHead>
                  <TableHead>Mức độ</TableHead>
                  <TableHead className="hidden lg:table-cell">Người phụ trách</TableHead>
                  <TableHead>Trạng thái</TableHead>
                  <TableHead className="text-right">Thao tác</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {slice.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell className="min-w-64 whitespace-normal">
                      <p className="ops-title">{item.title}</p>
                      <p className="ops-subtle tabular-nums">{item.id}</p>
                    </TableCell>
                    <TableCell className="whitespace-nowrap">{place(item)}</TableCell>
                    <TableCell className={cn('whitespace-nowrap', (item.severity === 'P1' || item.severity === 'P2') && 'font-semibold text-foreground')}>
                      {severities[item.severity]}
                    </TableCell>
                    <TableCell className="hidden whitespace-normal lg:table-cell">{ownerName(item)}</TableCell>
                    <TableCell className="whitespace-nowrap">{statuses[item.status]}</TableCell>
                    <TableCell className="text-right">
                      <Button variant="link" className="h-auto px-0" aria-label={`Xem chi tiết sự cố ${item.id}`} onClick={() => onSelect(item.id)}>
                        Xem chi tiết
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          <ul className="ops-list-rows">
            {slice.map((item) => (
              <li key={item.id} className="flex flex-col gap-1.5">
                <div className="flex items-start justify-between gap-3">
                  <p className="ops-title font-medium">{item.title}</p>
                  <span className="shrink-0 text-[13px] text-slate-600">{statuses[item.status]}</span>
                </div>
                <p className="ops-subtle"><span className="tabular-nums">{item.id}</span> · {place(item)}</p>
                <p className="text-[13px] text-slate-600">
                  <span className={cn((item.severity === 'P1' || item.severity === 'P2') && 'font-semibold text-foreground')}>{severities[item.severity]}</span>
                  {' · '}{ownerName(item)}
                </p>
                <div className="flex justify-end">
                  <Button variant="link" className="h-9 px-0" aria-label={`Xem chi tiết sự cố ${item.id}`} onClick={() => onSelect(item.id)}>
                    Xem chi tiết
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        </>
      )}

      <CardFooter className="px-4 md:px-6">
        <Pagination page={current} pages={pages} total={filtered.length} unit="sự cố" onChange={setPage} />
      </CardFooter>
    </Card>
  );
}
