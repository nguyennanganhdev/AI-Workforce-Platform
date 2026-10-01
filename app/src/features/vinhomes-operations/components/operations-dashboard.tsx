import { Link } from '@tanstack/react-router';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { cn } from '@/lib/utils';
import { useOperationsData } from '../hooks/use-operations-data';
import { PanelTitle } from './ops-ui';
import { severityLabel, slaText, useNow } from './technician/ui';

const STAGE_LABELS: Record<string, string> = {
  INTAKE: 'Tiếp nhận',
  TRIAGE: 'Phân loại',
  DIAGNOSING: 'Khảo sát',
  ACTION_PLANNING: 'Lên phương án',
  PLANNING: 'Lên phương án',
  EXECUTION: 'Đang sửa chữa',
  QC: 'Nghiệm thu',
  QC_INSPECTION: 'Nghiệm thu',
  RESIDENT_CONFIRMATION: 'Cư dân duyệt',
};

const CATEGORY_LABELS: Record<string, string> = {
  MEP_PLUMBING: 'Kỹ thuật cấp thoát nước',
  SANITATION_A5: 'Vệ sinh môi trường A5',
  ELEVATOR: 'Hệ thống thang máy',
  ELECTRICAL: 'Kỹ thuật điện chiếu sáng',
  CIVIL: 'Xây dựng hoàn thiện',
  SECURITY: 'An ninh trật tự',
};

type Kpi = { label: string; value: number; unit?: string; note: string; to: string; action: string; pressing?: boolean };

function KpiCard({ kpi }: { kpi: Kpi }) {
  return (
    <Card className="gap-3">
      <CardHeader className="gap-1.5 px-4 md:px-5">
        <CardDescription>{kpi.label}</CardDescription>
        <CardTitle className="flex items-baseline gap-2">
          <span className="text-3xl font-semibold tabular-nums text-foreground">{kpi.value}</span>
          {kpi.unit && <span className={cn('text-sm font-normal text-muted-foreground', kpi.pressing && 'font-medium text-foreground')}>{kpi.unit}</span>}
        </CardTitle>
      </CardHeader>
      <CardContent className="px-4 text-sm text-muted-foreground md:px-5">{kpi.note}</CardContent>
      <CardFooter className="mt-auto bg-transparent px-4 py-2.5 md:px-5">
        <Button variant="link" className="h-auto px-0" render={<Link to={kpi.to} />}>
          {kpi.action}
        </Button>
      </CardFooter>
    </Card>
  );
}

export function OperationsDashboard() {
  const { incidents, workOrders, qcResults, approvals, currentProfile } = useOperationsData();
  const now = useNow();

  const p1Incidents = incidents.filter((i) => i.severity === 'P0' && i.status !== 'CLOSED');
  const inProgressWo = workOrders.filter((w) => w.status === 'IN_PROGRESS');
  const pendingApprovals = approvals.filter((a) => a.status === 'PENDING');
  const failedQc = qcResults.filter((q) => q.outcome === 'FAIL');
  const passRate = qcResults.length ? Math.round(((qcResults.length - failedQc.length) / qcResults.length) * 100) : 0;
  const totalPendingCost = pendingApprovals.reduce((acc, curr) => acc + (curr.estimated_cost_vnd || 0), 0);
  const watched = incidents.filter((i) => i.status !== 'CLOSED').slice(0, 6);

  const kpis: Kpi[] = [
    { label: 'Khẩn cấp P0', value: p1Incidents.length, unit: 'đang mở', note: 'Sự cố nước áp lực S2.01 và PCCC', to: '/operations/incidents', action: 'Xử lý ngay', pressing: p1Incidents.length > 0 },
    { label: 'Đang thực hiện', value: inProgressWo.length, unit: `/ ${workOrders.length} phiếu`, note: '4 nhân viên và 1 nhà thầu tại hiện trường', to: '/operations/kanban', action: 'Bảng phân công việc' },
    { label: 'Nghiệm thu chất lượng', value: qcResults.length, unit: `${passRate}% đạt chuẩn`, note: failedQc.length > 0 ? `${failedQc.length} phiếu cần làm lại` : 'Tất cả đều đạt chuẩn', to: '/operations/qc', action: 'Chi tiết nghiệm thu' },
    { label: 'Chờ BQL duyệt', value: pendingApprovals.length, unit: `${(totalPendingCost / 1_000_000).toFixed(1)} tr đ`, note: 'Đề xuất mua van DN50 khẩn cấp', to: '/operations/approvals', action: 'Vào hàng đợi duyệt' },
  ];

  const deadline = (dueAt: string | null) => slaText(dueAt, now) || { text: '-', pressing: false };

  return (
    <div className="flex flex-col gap-4 md:gap-6">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between sm:gap-6">
        <div className="flex min-w-0 flex-col gap-1">
          <PanelTitle>Trung tâm điều hành và giám sát đô thị</PanelTitle>
          <p className="pl-3.5 text-sm text-muted-foreground">Vinhomes Smart City · Giám sát SLA và điều phối nhân lực hiện trường</p>
        </div>
        <p className="shrink-0 pl-3.5 text-sm text-muted-foreground sm:pl-0">
          Không gian làm việc: <span className="text-foreground">{currentProfile?.roleTitle || 'Ban Quản Lý Đô Thị'}</span>
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {kpis.map((k) => <KpiCard key={k.label} kpi={k} />)}
      </div>

      <div className="grid grid-cols-1 gap-4 md:gap-6 xl:grid-cols-[minmax(0,1fr)_360px] xl:items-start">
        <Card className="gap-0 pb-0">
          <CardHeader className="items-center px-4 pb-3 md:px-6">
            <PanelTitle as="h2">Sự cố hiện trường cần giám sát</PanelTitle>
            <Button variant="link" className="col-start-2 row-start-1 h-auto justify-self-end px-0" render={<Link to="/operations/incidents" />}>
              Xem tất cả
            </Button>
          </CardHeader>

          <div className="ops-list-table px-2 md:px-4">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Sự cố</TableHead>
                  <TableHead>Vị trí</TableHead>
                  <TableHead>Mức độ</TableHead>
                  <TableHead className="hidden 2xl:table-cell">Giai đoạn</TableHead>
                  <TableHead className="text-right">Thời hạn</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {watched.map((inc) => {
                  const d = deadline(inc.sla_due_at);
                  const urgent = inc.severity === 'P0' || inc.severity === 'P1';
                  return (
                    <TableRow key={inc.id}>
                      <TableCell className="min-w-64 whitespace-normal">
                        <Link to="/operations/incidents" className="ops-title hover:text-primary hover:underline underline-offset-2">{inc.title}</Link>
                        <p className="ops-subtle tabular-nums">{inc.id} · {CATEGORY_LABELS[inc.category] || inc.category}</p>
                      </TableCell>
                      <TableCell className="whitespace-nowrap">
                        <p>Tòa {inc.location_json.towerCode}</p>
                        <p className="ops-subtle max-w-40 truncate">{inc.location_json.areaCode || inc.location_json.description}</p>
                      </TableCell>
                      <TableCell className={cn('whitespace-nowrap', urgent && 'font-semibold text-foreground')}>{severityLabel(inc.severity)}</TableCell>
                      <TableCell className="hidden whitespace-nowrap 2xl:table-cell">{STAGE_LABELS[inc.stage] || inc.stage}</TableCell>
                      <TableCell className={cn('whitespace-nowrap text-right tabular-nums', d.pressing && 'font-semibold text-foreground')}>{d.text}</TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>

          <ul className="ops-list-rows">
            {watched.map((inc) => {
              const d = deadline(inc.sla_due_at);
              const urgent = inc.severity === 'P0' || inc.severity === 'P1';
              return (
                <li key={inc.id} className="flex flex-col gap-1.5">
                  <div className="flex items-start justify-between gap-3">
                    <Link to="/operations/incidents" className="ops-title font-medium hover:text-primary hover:underline underline-offset-2">{inc.title}</Link>
                    <span className="shrink-0 text-[13px] text-slate-600">{STAGE_LABELS[inc.stage] || inc.stage}</span>
                  </div>
                  <p className="ops-subtle"><span className="tabular-nums">{inc.id}</span> · Tòa {inc.location_json.towerCode}</p>
                  <p className="text-[13px] text-slate-600">
                    <span className={cn(urgent && 'font-semibold text-foreground')}>{severityLabel(inc.severity)}</span>
                    {' · '}
                    <span className={cn(d.pressing && 'font-semibold text-foreground')}>{d.text}</span>
                  </p>
                </li>
              );
            })}
          </ul>
          <div className="h-2" />
        </Card>

        <div className="flex flex-col gap-4">
          <Card>
            <CardHeader className="gap-1 px-4 md:px-5">
              <CardDescription>Đề xuất xử lý</CardDescription>
              <CardTitle className="text-[15px] font-semibold leading-snug">Phát hiện nguy cơ rò rỉ nước ngấm xuống thang máy S2.01</CardTitle>
            </CardHeader>
            <CardContent className="px-4 text-sm leading-relaxed text-muted-foreground md:px-5">
              AI đề xuất khóa van trục C (đã thực hiện) và kích hoạt gói vật tư thay van DN50 (12,5 tr đ) đang chờ BQL duyệt.
            </CardContent>
            <CardFooter className="justify-between gap-3 bg-transparent px-4 pt-3 md:px-5">
              <span className="text-xs text-muted-foreground">Độ tin cậy: 98,4%</span>
              <Button render={<Link to="/operations/approvals" />}>Duyệt đề xuất</Button>
            </CardFooter>
          </Card>

          <Card>
            <CardHeader className="px-4 md:px-5">
              <CardTitle className="text-[15px] font-semibold">Phân khu đang theo dõi</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col px-4 text-sm md:px-5">
              {[
                { tower: 'Tòa S2.01', note: '1 sự cố P0', pressing: true },
                { tower: 'Tòa S1.05', note: '1 vệ sinh A5' },
                { tower: 'Tòa S2.03', note: 'Nghiệm thu thang máy' },
              ].map((z, i) => (
                <div key={z.tower}>
                  {i > 0 && <Separator />}
                  <div className="flex items-center justify-between gap-3 py-2.5">
                    <span className="text-foreground">{z.tower}</span>
                    <span className={cn('text-muted-foreground', z.pressing && 'font-medium text-foreground')}>{z.note}</span>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
