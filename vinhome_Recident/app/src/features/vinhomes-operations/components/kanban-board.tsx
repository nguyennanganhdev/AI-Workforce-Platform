import { useState } from 'react';
import { IconCheck, IconUser } from '@tabler/icons-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { cn } from '@/lib/utils';
import { OperationsTable } from './operations-table';
import { PanelTitle, Segmented } from './ops-ui';
import { useOperationsData } from '../hooks/use-operations-data';
import type { TaskStatus, VhTask } from '../types/task';

const ALL = 'ALL';
type View = 'LIST' | 'BOARD';

const COLUMNS: Array<{ id: TaskStatus; label: string }> = [
  { id: 'OPEN', label: 'Chờ thực hiện' },
  { id: 'IN_PROGRESS', label: 'Đang làm' },
  { id: 'BLOCKED', label: 'Tạm hoãn / Chờ việc khác' },
  { id: 'DONE', label: 'Đã hoàn thành' },
];

const DOMAINS: Array<{ id: string; label: string }> = [
  { id: ALL, label: 'Tất cả bộ phận' },
  { id: 'MEP', label: 'Điện nước' },
  { id: 'SANITATION', label: 'Vệ sinh A5' },
  { id: 'LANDSCAPE', label: 'Cảnh quan' },
];

const domainLabel = (d: string) => (d === 'SANITATION' ? 'Vệ sinh' : DOMAINS.find((x) => x.id === d)?.label || d);

const PRIORITY_LABEL: Record<string, string> = { URGENT: 'Khẩn cấp', HIGH: 'Ưu tiên', MEDIUM: 'Bình thường', LOW: 'Thấp' };
const priorityLabel = (p: string) => PRIORITY_LABEL[p] || 'Bình thường';
const statusLabel = (s: TaskStatus) => COLUMNS.find((c) => c.id === s)?.label || 'Chưa xác định';

/** Urgency is carried by weight, not colour — same rule as SeverityBadge. */
function PriorityText({ priority }: { priority: string }) {
  const urgent = priority === 'URGENT' || priority === 'HIGH';
  return <span className={cn('text-xs', urgent ? 'font-semibold text-foreground' : 'text-muted-foreground')}>{priorityLabel(priority)}</span>;
}

export function KanbanBoard() {
  const { tasks, workOrders, incidents, updateTaskStatus } = useOperationsData();
  const [view, setView] = useState<View>('LIST');
  const [domain, setDomain] = useState<string>(ALL);
  const [incidentId, setIncidentId] = useState<string>(ALL);

  const filteredTasks = tasks.filter(
    (t) => (domain === ALL || t.domain_type === domain) && (incidentId === ALL || t.incident_id === incidentId),
  );
  const hasFilter = domain !== ALL || incidentId !== ALL;
  const incidentTitle = (id: string) => incidents.find((i) => i.id === id)?.title || 'Chưa gắn sự cố';
  const incidentItems = { [ALL]: 'Tất cả sự cố', ...Object.fromEntries(incidents.map((i) => [i.id, i.title])) };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between sm:gap-6">
        <div className="flex min-w-0 flex-col gap-1">
          <PanelTitle>Phân công công việc</PanelTitle>
          <p className="pl-3.5 text-sm text-muted-foreground">Điều phối tiến độ công việc giữa các đội kỹ thuật và giám sát.</p>
        </div>
        <p className="shrink-0 pl-3.5 text-sm tabular-nums text-muted-foreground sm:pl-0">{tasks.length} công việc</p>
      </div>

      <Tabs value={view} onValueChange={(v) => setView(v as View)} className="gap-4">
        <TabsList variant="line" aria-label="Cách xem" className="ops-scroll-tabs h-auto w-full justify-start border-b pb-1">
          <TabsTrigger value="LIST" className="h-9 flex-none px-3 data-active:text-primary after:bg-primary">Danh sách</TabsTrigger>
          <TabsTrigger value="BOARD" className="h-9 flex-none px-3 data-active:text-primary after:bg-primary">Theo tiến độ</TabsTrigger>
        </TabsList>

        {/* Filters apply to both views */}
        <Card aria-label="Bộ lọc">
          <CardContent className="flex flex-col gap-3 px-4 md:flex-row md:flex-wrap md:items-center md:px-6">
            <Segmented label="Bộ phận" value={domain} onChange={setDomain} options={DOMAINS} />
            <div className="flex gap-2 md:ml-auto">
              <Select items={incidentItems} value={incidentId} onValueChange={(v) => setIncidentId((v as string | null) ?? ALL)}>
                <SelectTrigger aria-label="Sự cố" className="min-w-0 flex-1 bg-card data-[size=default]:h-10 md:w-80 md:flex-none">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    {Object.entries(incidentItems).map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}
                  </SelectGroup>
                </SelectContent>
              </Select>
              <Button variant="ghost" size="lg" disabled={!hasFilter} onClick={() => { setDomain(ALL); setIncidentId(ALL); }}>
                Xóa bộ lọc
              </Button>
            </div>
          </CardContent>
        </Card>

        <TabsContent value="LIST">
          <OperationsTable
            title="Danh sách công việc"
            columns={['Công việc', 'Bộ phận', 'Người phụ trách', 'Mức ưu tiên', 'Trạng thái']}
            actionLabel="Xem tiến độ"
            rows={filteredTasks.map((task) => ({
              id: task.id,
              search: `${task.title} ${task.assignee_name || ''} ${incidentTitle(task.incident_id)}`,
              cells: [
                task.title,
                domainLabel(task.domain_type),
                task.assignee_name || 'Chưa phân công',
                <PriorityText key="p" priority={task.priority} />,
                statusLabel(task.status),
              ],
            }))}
            onSelect={(id) => {
              setIncidentId(tasks.find((t) => t.id === id)?.incident_id || ALL);
              setView('BOARD');
            }}
          />
        </TabsContent>

        <TabsContent value="BOARD">
          <div className="grid grid-cols-1 items-start gap-3 md:grid-cols-2 xl:grid-cols-4">
            {COLUMNS.map((col) => {
              const colTasks = filteredTasks.filter((t) => t.status === col.id);
              return (
                <section key={col.id} aria-label={col.label} className="flex flex-col gap-2.5 rounded-xl border bg-muted/40 p-2.5 xl:min-h-[520px]">
                  <header className="flex items-center justify-between gap-2 px-1.5 pt-0.5">
                    <h2 className="text-sm font-medium text-foreground">{col.label}</h2>
                    <Badge variant="secondary" className="tabular-nums">{colTasks.length}</Badge>
                  </header>
                  {colTasks.length === 0 ? (
                    <p className="rounded-lg border border-dashed px-3 py-6 text-center text-sm text-muted-foreground">Chưa có việc nào</p>
                  ) : (
                    colTasks.map((task) => (
                      <TaskCard
                        key={task.id}
                        task={task}
                        incidentTitle={incidentTitle(task.incident_id)}
                        attempts={workOrders.filter((w) => w.task_id === task.id)}
                        onMove={(s) => updateTaskStatus(task.id, s)}
                      />
                    ))
                  )}
                </section>
              );
            })}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}

function TaskCard({
  task,
  incidentTitle,
  attempts,
  onMove,
}: {
  task: VhTask;
  incidentTitle: string;
  attempts: Array<{ redo_of_work_order_id: string | null }>;
  onMove: (status: TaskStatus) => void;
}) {
  const redoCount = attempts.filter((w) => w.redo_of_work_order_id !== null).length;

  return (
    <Card size="sm" className="gap-3">
      <CardContent className="flex flex-col gap-2">
        <div className="flex items-center justify-between gap-2">
          <Badge variant="outline">{domainLabel(task.domain_type)}</Badge>
          <PriorityText priority={task.priority} />
        </div>
        <p className="text-sm font-medium leading-snug text-foreground">{task.title}</p>
        <p className="line-clamp-1 text-xs text-muted-foreground">Sự cố: {incidentTitle}</p>

        <div className="flex items-center justify-between gap-2 border-t pt-2 text-xs text-muted-foreground">
          <span className="flex min-w-0 items-center gap-1">
            <IconUser className="size-3.5 shrink-0" aria-hidden />
            <span className="truncate">{task.assignee_name || 'Chưa giao'}</span>
          </span>
          <span className="shrink-0 tabular-nums">
            {attempts.length} lần làm{redoCount > 0 && ` · ${redoCount} làm lại`}
          </span>
        </div>

        <div className="flex justify-end gap-2">
          {task.status === 'OPEN' && <Button size="sm" onClick={() => onMove('IN_PROGRESS')}>Bắt đầu</Button>}
          {task.status === 'IN_PROGRESS' && (
            <>
              <Button size="sm" variant="outline" onClick={() => onMove('BLOCKED')}>Tạm hoãn</Button>
              <Button size="sm" onClick={() => onMove('DONE')}>Hoàn thành</Button>
            </>
          )}
          {task.status === 'BLOCKED' && <Button size="sm" onClick={() => onMove('IN_PROGRESS')}>Tiếp tục làm</Button>}
          {task.status === 'DONE' && (
            <span className="flex items-center gap-1 text-xs text-muted-foreground">
              <IconCheck className="size-3.5" aria-hidden /> Đã hoàn thành
            </span>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
