import { Link } from '@tanstack/react-router';
import {
  IconAlertTriangle,
  IconClipboardCheck,
  IconShieldCheck,
  IconGavel,
  IconClock,
  IconArrowUpRight,
  IconCheck,
  IconTrendingUp,
  IconBuildingSkyscraper,
  IconSparkles,
} from '@tabler/icons-react';
import { useOperationsData } from '../hooks/use-operations-data';

const STAGE_LABELS: Record<string, string> = {
  INTAKE: 'Tiếp nhận',
  TRIAGE: 'Phân loại',
  DIAGNOSING: 'Khảo sát',
  ACTION_PLANNING: 'Lên phương án',
  EXECUTION: 'Đang sửa chữa',
  QC_INSPECTION: 'Nghiệm thu',
  RESIDENT_CONFIRMATION: 'Cư dân duyệt',
};

const CATEGORY_LABELS: Record<string, string> = {
  MEP_PLUMBING: 'Kỹ thuật Cấp Thoát Nước',
  SANITATION_A5: 'Vệ sinh Môi trường A5',
  ELEVATOR: 'Hệ thống Thang máy',
  ELECTRICAL: 'Kỹ thuật Điện chiếu sáng',
  CIVIL: 'Xây dựng hoàn thiện',
  SECURITY: 'An ninh trật tự',
};

export function OperationsDashboard() {
  const { incidents, workOrders, qcResults, approvals, currentPersona } = useOperationsData();

  const p1Incidents = incidents.filter((i) => i.severity === 'P1' && i.status !== 'CLOSED');
  const inProgressWo = workOrders.filter((w) => w.status === 'IN_PROGRESS');
  const completedWo = workOrders.filter((w) => w.status === 'COMPLETED');
  const pendingApprovals = approvals.filter((a) => a.status === 'PENDING');
  const failedQc = qcResults.filter((q) => q.outcome === 'FAIL');

  const totalPendingCost = pendingApprovals.reduce(
    (acc, curr) => acc + (curr.estimated_cost_vnd || 0),
    0,
  );

  return (
    <div className="space-y-6">
      {/* Title Header with BistroPulse Blue Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-1.5 h-6 bg-blue-600 rounded-full shrink-0" />
          <div>
            <h1 className="text-xl font-bold text-slate-900 tracking-tight">
              Trung Tâm Điều Hành & Giám Sát Đô Thị
            </h1>
            <p className="text-xs text-slate-500 font-medium">
              Vinhomes Smart City • Giám sát SLA thời gian thực & Điều phối nhân lực hiện trường
            </p>
          </div>
        </div>

        {/* Quick Filter / Persona banner */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-500 font-medium">Không gian làm việc:</span>
          <span className="px-3 py-1 bg-blue-50 text-blue-700 font-bold text-xs rounded-full border border-blue-200/60 shadow-2xs">
            {currentPersona === 'STAFF_TECHNICAL' && '👷 Kỹ sư Hiện trường MEP & PCCC'}
            {currentPersona === 'STAFF_SANITATION' && '🧹 Giám sát Vệ sinh A5 & Cảnh quan'}
            {currentPersona === 'MANAGER' && '🏢 Ban Quản Lý (BQL) Đô Thị'}
          </span>
        </div>
      </div>

      {/* 4 Primary KPI & SLA Cards — BistroPulse Clean Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: Sự cố P1 Khẩn */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs hover:shadow-md transition-shadow relative overflow-hidden group">
          <div className="absolute top-0 right-0 w-24 h-24 bg-rose-50 rounded-full -mr-8 -mt-8 group-hover:scale-110 transition-transform" />
          <div className="flex items-center justify-between mb-3 relative z-10">
            <span className="text-xs font-semibold uppercase tracking-wider text-rose-600 bg-rose-50 px-2 py-0.5 rounded-full">
              Khẩn cấp P1
            </span>
            <div className="w-9 h-9 rounded-xl bg-rose-100 text-rose-600 flex items-center justify-center">
              <IconAlertTriangle className="w-5 h-5" />
            </div>
          </div>
          <div className="relative z-10">
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-extrabold text-slate-900">{p1Incidents.length}</span>
              <span className="text-xs text-rose-600 font-bold flex items-center">
                <IconClock className="w-3.5 h-3.5 mr-0.5" /> SLA: 45p
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-1">Sự cố nước áp lực S2.01 & PCCC</p>
          </div>
          <Link
            to="/operations/work-orders"
            className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-xs font-semibold text-rose-600 hover:text-rose-700"
          >
            <span>Xử lý ngay</span>
            <IconArrowUpRight className="w-4 h-4" />
          </Link>
        </div>

        {/* Card 2: Việc đang thực hiện */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs hover:shadow-md transition-shadow relative overflow-hidden group">
          <div className="absolute top-0 right-0 w-24 h-24 bg-blue-50 rounded-full -mr-8 -mt-8 group-hover:scale-110 transition-transform" />
          <div className="flex items-center justify-between mb-3 relative z-10">
            <span className="text-xs font-semibold uppercase tracking-wider text-blue-600 bg-blue-50 px-2 py-0.5 rounded-full">
              Đang thực hiện
            </span>
            <div className="w-9 h-9 rounded-xl bg-blue-100 text-blue-600 flex items-center justify-center">
              <IconClipboardCheck className="w-5 h-5" />
            </div>
          </div>
          <div className="relative z-10">
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-extrabold text-slate-900">{inProgressWo.length}</span>
              <span className="text-xs text-slate-500 font-medium">/ {workOrders.length} phiếu</span>
            </div>
            <p className="text-xs text-slate-500 mt-1">4 nhân viên & 1 nhà thầu tại hiện trường</p>
          </div>
          <Link
            to="/operations/kanban"
            className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-xs font-semibold text-blue-600 hover:text-blue-700"
          >
            <span>Bảng phân công việc</span>
            <IconArrowUpRight className="w-4 h-4" />
          </Link>
        </div>

        {/* Card 3: Kiểm định QC */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs hover:shadow-md transition-shadow relative overflow-hidden group">
          <div className="absolute top-0 right-0 w-24 h-24 bg-purple-50 rounded-full -mr-8 -mt-8 group-hover:scale-110 transition-transform" />
          <div className="flex items-center justify-between mb-3 relative z-10">
            <span className="text-xs font-semibold uppercase tracking-wider text-purple-600 bg-purple-50 px-2 py-0.5 rounded-full">
              Nghiệm thu chất lượng
            </span>
            <div className="w-9 h-9 rounded-xl bg-purple-100 text-purple-600 flex items-center justify-center">
              <IconShieldCheck className="w-5 h-5" />
            </div>
          </div>
          <div className="relative z-10">
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-extrabold text-slate-900">{qcResults.length}</span>
              <span className="text-xs text-emerald-600 font-bold flex items-center">
                <IconCheck className="w-3.5 h-3.5 mr-0.5" /> 75% Đạt chuẩn
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-1">
              {failedQc.length > 0 ? `1 phiếu làm lại đã hoàn thành` : `Tất cả đều đạt chuẩn`}
            </p>
          </div>
          <Link
            to="/operations/qc"
            className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-xs font-semibold text-purple-600 hover:text-purple-700"
          >
            <span>Chi tiết nghiệm thu</span>
            <IconArrowUpRight className="w-4 h-4" />
          </Link>
        </div>

        {/* Card 4: Phê duyệt BQL */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs hover:shadow-md transition-shadow relative overflow-hidden group">
          <div className="absolute top-0 right-0 w-24 h-24 bg-amber-50 rounded-full -mr-8 -mt-8 group-hover:scale-110 transition-transform" />
          <div className="flex items-center justify-between mb-3 relative z-10">
            <span className="text-xs font-semibold uppercase tracking-wider text-amber-700 bg-amber-50 px-2 py-0.5 rounded-full">
              Chờ BQL duyệt
            </span>
            <div className="w-9 h-9 rounded-xl bg-amber-100 text-amber-700 flex items-center justify-center">
              <IconGavel className="w-5 h-5" />
            </div>
          </div>
          <div className="relative z-10">
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-extrabold text-slate-900">{pendingApprovals.length}</span>
              <span className="text-xs text-amber-700 font-bold">
                {(totalPendingCost / 1000000).toFixed(1)} tr đ
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-1">Đề xuất mua van DN50 khẩn cấp</p>
          </div>
          <Link
            to="/operations/approvals"
            className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-xs font-semibold text-amber-700 hover:text-amber-800"
          >
            <span>Vào hàng đợi duyệt</span>
            <IconArrowUpRight className="w-4 h-4" />
          </Link>
        </div>
      </div>

      {/* Two Column Layout: Active Incidents Table & AI Recommendations */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Active Critical Incidents — BistroPulse Table Card */}
        <div className="lg:col-span-2 bg-white rounded-2xl border border-slate-200/80 p-5 shadow-xs">
          <div className="flex items-center justify-between mb-4 pb-3 border-b border-slate-100">
            <div className="flex items-center gap-2.5">
              <div className="w-1 h-4 bg-blue-600 rounded-full" />
              <h2 className="font-bold text-slate-900 text-sm">
                Sự Cố Hiện Trường Cần Giám Sát
              </h2>
            </div>
            <Link
              to="/operations/work-orders"
              className="text-xs font-semibold text-blue-600 hover:text-blue-700 flex items-center gap-1"
            >
              <span>Xem tất cả phiếu</span>
              <IconArrowUpRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-100 text-slate-400 font-semibold uppercase tracking-wider">
                  <th className="pb-3 pl-2">Mã & Sự cố</th>
                  <th className="pb-3">Vị trí</th>
                  <th className="pb-3">Mức độ</th>
                  <th className="pb-3">Giai đoạn</th>
                  <th className="pb-3 text-right pr-2">Hạn chót SLA</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {incidents.slice(0, 4).map((inc) => (
                  <tr key={inc.id} className="hover:bg-slate-50/70 transition-colors">
                    <td className="py-3 pl-2">
                      <div className="font-bold text-slate-900">{inc.title}</div>
                      <div className="text-[11px] text-slate-400 font-mono">
                        {inc.id} • {CATEGORY_LABELS[inc.category] || inc.category}
                      </div>
                    </td>
                    <td className="py-3 text-slate-600">
                      <div className="font-medium text-slate-800">{inc.location_json.towerCode}</div>
                      <div className="text-[11px] text-slate-500 truncate max-w-[140px]">
                        {inc.location_json.areaCode || inc.location_json.description}
                      </div>
                    </td>
                    <td className="py-3">
                      <span
                        className={`px-2 py-0.5 rounded-full font-bold text-[10px] ${
                          inc.severity === 'P1'
                            ? 'bg-rose-100 text-rose-700'
                            : inc.severity === 'P2'
                              ? 'bg-amber-100 text-amber-700'
                              : 'bg-blue-100 text-blue-700'
                        }`}
                      >
                        {inc.severity}
                      </span>
                    </td>
                    <td className="py-3">
                      <span className="px-2 py-0.5 rounded font-medium text-[11px] bg-slate-100 text-slate-700">
                        {STAGE_LABELS[inc.stage] || inc.stage}
                      </span>
                    </td>
                    <td className="py-3 text-right pr-2 font-mono text-slate-600 font-semibold">
                      {inc.sla_due_at ? (
                        <span className="text-rose-600 font-bold flex items-center justify-end gap-1">
                          <IconClock className="w-3.5 h-3.5" /> 45 phút
                        </span>
                      ) : (
                        '—'
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Right 1 Col: AI Dispatcher & Smart City Live Status */}
        <div className="space-y-4">
          {/* Card: AI Recommendation */}
          <div className="bg-gradient-to-br from-slate-900 to-blue-950 text-white p-5 rounded-2xl shadow-sm relative overflow-hidden">
            <div className="flex items-center gap-2 mb-2 text-blue-400 font-semibold text-xs">
              <IconSparkles className="w-4 h-4 text-amber-300" />
              <span>Khuyến nghị từ AI Agent</span>
            </div>
            <h3 className="font-bold text-sm text-white mb-2 leading-snug">
              Phát hiện nguy cơ rò rỉ nước ngấm xuống thang máy S2.01
            </h3>
            <p className="text-xs text-slate-300 leading-relaxed mb-4">
              AI đề xuất khóa van trục C (Đã thực hiện) và kích hoạt gói vật tư thay van DN50 (12.5tr) đang chờ BQL duyệt.
            </p>
            <div className="flex items-center justify-between pt-3 border-t border-white/10">
              <span className="text-[11px] text-slate-400">Độ tin cậy: 98.4%</span>
              <Link
                to="/operations/approvals"
                className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-bold transition-colors"
              >
                Duyệt đề xuất
              </Link>
            </div>
          </div>

          {/* Card: Building Scope Summary */}
          <div className="bg-white rounded-2xl border border-slate-200/80 p-5 shadow-xs">
            <div className="flex items-center gap-2 mb-3">
              <IconBuildingSkyscraper className="w-4 h-4 text-blue-600" />
              <h4 className="font-bold text-xs text-slate-900">Phân khu đang theo dõi</h4>
            </div>
            <div className="space-y-2 text-xs">
              <div className="flex items-center justify-between p-2 rounded-lg bg-slate-50">
                <span className="font-semibold text-slate-800">Tòa S2.01</span>
                <span className="text-rose-600 font-bold">1 sự cố P1</span>
              </div>
              <div className="flex items-center justify-between p-2 rounded-lg bg-slate-50">
                <span className="font-semibold text-slate-800">Tòa S1.05</span>
                <span className="text-amber-600 font-bold">1 vệ sinh A5</span>
              </div>
              <div className="flex items-center justify-between p-2 rounded-lg bg-slate-50">
                <span className="font-semibold text-slate-800">Tòa S2.03</span>
                <span className="text-purple-600 font-bold">QC Thang máy</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
