import { useState } from 'react';
import { OperationsTable } from './operations-table';
import {
  IconCheck,
  IconBuilding,
  IconUser,
  IconLink,
  IconClock,
  IconSparkles,
} from '@tabler/icons-react';
import { useOperationsData } from '../hooks/use-operations-data';
import type { TaskStatus, VhTaskDependency } from '../types/task';
import { MOCK_TASK_DEPENDENCIES } from '../mock/tasks';

interface TaskColumnDef {
  id: TaskStatus;
  label: string;
  badgeColor: string;
}

const COLUMNS: TaskColumnDef[] = [
  { id: 'OPEN', label: 'Chờ thực hiện', badgeColor: 'bg-slate-100 text-slate-700' },
  { id: 'IN_PROGRESS', label: 'Đang làm', badgeColor: 'bg-blue-100 text-blue-700' },
  { id: 'BLOCKED', label: 'Tạm hoãn / Chờ việc khác', badgeColor: 'bg-amber-100 text-amber-800' },
  { id: 'DONE', label: 'Đã hoàn thành', badgeColor: 'bg-emerald-100 text-emerald-700' },
];

export function KanbanBoard() {
  const { tasks, workOrders, incidents, updateTaskStatus } = useOperationsData();
  const [view, setView] = useState<'LIST' | 'BOARD'>('LIST');
  const [selectedDomain, setSelectedDomain] = useState<string>('ALL');
  const [selectedIncidentFilter, setSelectedIncidentFilter] = useState<string>('ALL');

  const filteredTasks = tasks.filter((t) => {
    if (selectedDomain !== 'ALL' && t.domain_type !== selectedDomain) return false;
    if (selectedIncidentFilter !== 'ALL' && t.incident_id !== selectedIncidentFilter) return false;
    return true;
  });

  return (
    <div className="space-y-4 font-sans">
      {/* Title Header with Blue Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="w-1.5 h-6 bg-blue-600 rounded-full shrink-0" />
          <div>
            <h1 className="text-lg font-bold text-slate-900 tracking-tight">
              Phân công công việc
            </h1>
            <p className="text-xs text-slate-500">
              Điều phối tiến độ công việc giữa các đội ngũ kỹ thuật và giám sát
            </p>
          </div>
        </div>

        {/* Filter Toolbar */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Domain Filter */}
          <div className="flex items-center gap-1 bg-white p-1 rounded-xl border border-slate-200/80 shadow-2xs">
            {[
              { id: 'ALL', label: 'Tất cả bộ phận' },
              { id: 'MEP', label: 'Điện Nước' },
              { id: 'SANITATION', label: 'Vệ sinh A5' },
              { id: 'LANDSCAPE', label: 'Cảnh quan' },
            ].map((d) => (
              <button
                key={d.id}
                type="button"
                onClick={() => setSelectedDomain(d.id)}
                className={`px-2.5 py-1 rounded-lg text-xs font-semibold transition-colors ${
                  selectedDomain === d.id
                    ? 'bg-blue-600 text-white shadow-2xs'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
                }`}
              >
                {d.label}
              </button>
            ))}
          </div>

          {/* Incident Filter */}
          <select
            value={selectedIncidentFilter}
            onChange={(e) => setSelectedIncidentFilter(e.target.value)}
            className="text-xs font-semibold bg-white border border-slate-200/80 rounded-xl px-2.5 py-1.5 focus:outline-none focus:border-blue-500 shadow-2xs"
          >
            <option value="ALL">Tất cả sự cố ({incidents.length})</option>
            {incidents.map((inc) => (
              <option key={inc.id} value={inc.id}>
                {inc.id} — {inc.title.slice(0, 30)}...
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="flex gap-5 border-b border-slate-200">
        <button type="button" aria-pressed={view === 'LIST'} className={`pb-3 text-sm ${view === 'LIST' ? 'border-b-2 border-blue-600 text-blue-600' : 'text-slate-500'}`} onClick={() => setView('LIST')}>Danh sách công việc</button>
        <button type="button" aria-pressed={view === 'BOARD'} className={`pb-3 text-sm ${view === 'BOARD' ? 'border-b-2 border-blue-600 text-blue-600' : 'text-slate-500'}`} onClick={() => setView('BOARD')}>Theo tiến độ</button>
      </div>
      <div hidden={view !== 'LIST'}>
        <OperationsTable title="Phân công công việc" columns={['Mã công việc', 'Nội dung', 'Sự cố', 'Người phụ trách', 'Trạng thái']}
          actionLabel="Xem tiến độ"
          rows={filteredTasks.map((task) => ({id: task.id, search: `${task.id} ${task.title} ${task.assignee_name || ''}`, cells: [
            task.id, task.title, task.incident_id, task.assignee_name || 'Chưa phân công',
            COLUMNS.find((column) => column.id === task.status)?.label || 'Chưa xác định',
          ]}))}
          onSelect={(id) => { setSelectedIncidentFilter(tasks.find((task) => task.id === id)?.incident_id || 'ALL'); setView('BOARD'); }} />
      </div>
      {/* 4-Column Board */}
      <div className={view === 'BOARD' ? "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3.5 items-start" : "hidden"}>
        {COLUMNS.map((col) => {
          const colTasks = filteredTasks.filter((t) => t.status === col.id);

          return (
            <div
              key={col.id}
              className="bg-slate-100/70 rounded-2xl p-3 border border-slate-200/80 flex flex-col min-h-[560px]"
            >
              {/* Column Header */}
              <div className="flex items-center justify-between mb-2.5 px-1">
                <span className="font-bold text-xs text-slate-800">{col.label}</span>
                <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${col.badgeColor}`}>
                  {colTasks.length}
                </span>
              </div>

              {/* Tasks List */}
              <div className="space-y-2.5 flex-1 overflow-y-auto">
                {colTasks.map((task) => {
                  const taskWos = workOrders.filter((w) => w.task_id === task.id);
                  const redoCount = taskWos.filter((w) => w.redo_of_work_order_id !== null).length;

                  // Find dependency
                  const dep = MOCK_TASK_DEPENDENCIES.find((d: VhTaskDependency) => d.task_id === task.id);
                  const prerequisiteTask = dep ? tasks.find((t) => t.id === dep.depends_on_task_id) : null;
                  const isPrerequisiteDone = prerequisiteTask?.status === 'DONE';

                  return (
                    <div
                      key={task.id}
                      className="bg-white rounded-xl p-3 border border-slate-200/80 hover:border-blue-300 transition-all space-y-2 shadow-2xs"
                    >
                      {/* Top Badges */}
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-1.5">
                          <span className="font-mono text-xs font-bold text-blue-600">{task.id}</span>
                          <span className="text-[10px] font-semibold px-1.5 py-0.2 bg-slate-100 text-slate-600 rounded">
                            {task.domain_type === 'MEP'
                              ? 'Điện Nước'
                              : task.domain_type === 'SANITATION'
                                ? 'Vệ sinh'
                                : task.domain_type === 'LANDSCAPE'
                                  ? 'Cảnh quan'
                                  : task.domain_type}
                          </span>
                        </div>
                        <span
                          className={`text-[10px] font-bold px-1.5 py-0.2 rounded ${
                            task.priority === 'URGENT'
                              ? 'bg-rose-100 text-rose-700'
                              : task.priority === 'HIGH'
                                ? 'bg-amber-100 text-amber-700'
                                : 'bg-slate-100 text-slate-600'
                          }`}
                        >
                          {task.priority === 'URGENT' ? 'Khẩn' : task.priority === 'HIGH' ? 'Ưu tiên' : 'Thường'}
                        </span>
                      </div>

                      {/* Title */}
                      <p className="font-bold text-xs text-slate-900 leading-snug">
                        {task.title}
                      </p>

                      {/* Parent Incident Tag */}
                      <div className="text-[11px] text-slate-400">
                        Sự cố: <span className="font-semibold text-slate-600">{task.incident_id}</span>
                      </div>

                      {/* Dependency Badge if exists */}
                      {dep && prerequisiteTask && (
                        <div
                          className={`p-1.5 rounded-lg text-[10px] flex items-center justify-between ${
                            isPrerequisiteDone
                              ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                              : 'bg-amber-50 text-amber-800 border border-amber-200 font-medium'
                          }`}
                        >
                          <span className="truncate">
                            Cần làm sau: <strong>{dep.depends_on_task_id}</strong>
                          </span>
                          <span className="font-bold">
                            {isPrerequisiteDone ? '✓ Đã xong' : 'Chờ hoàn thành'}
                          </span>
                        </div>
                      )}

                      {/* Footer Info */}
                      <div className="pt-1.5 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-500">
                        <div className="flex items-center gap-1 font-medium truncate max-w-[130px]">
                          <IconUser className="w-3 h-3 text-slate-400 shrink-0" />
                          <span className="truncate">{task.assignee_name || 'Chưa giao'}</span>
                        </div>

                        <span className="text-[10px] text-slate-400">
                          {taskWos.length} lần làm {redoCount > 0 && `(${redoCount} làm lại)`}
                        </span>
                      </div>

                      {/* Action buttons */}
                      <div className="pt-1 flex items-center justify-end gap-1">
                        {task.status === 'OPEN' && (
                          <button
                            type="button"
                            onClick={() => updateTaskStatus(task.id, 'IN_PROGRESS')}
                            className="px-2 py-0.5 bg-blue-50 text-blue-600 hover:bg-blue-600 hover:text-white rounded text-[11px] font-bold transition-colors"
                          >
                            Bắt đầu ➔
                          </button>
                        )}
                        {task.status === 'IN_PROGRESS' && (
                          <>
                            <button
                              type="button"
                              onClick={() => updateTaskStatus(task.id, 'BLOCKED')}
                              className="px-2 py-0.5 bg-slate-100 text-slate-600 hover:bg-slate-200 rounded text-[11px] font-medium transition-colors"
                            >
                              Tạm hoãn
                            </button>
                            <button
                              type="button"
                              onClick={() => updateTaskStatus(task.id, 'DONE')}
                              className="px-2 py-0.5 bg-emerald-50 text-emerald-700 hover:bg-emerald-600 hover:text-white rounded text-[11px] font-bold transition-colors"
                            >
                              Hoàn thành
                            </button>
                          </>
                        )}
                        {task.status === 'BLOCKED' && (
                          <button
                            type="button"
                            onClick={() => updateTaskStatus(task.id, 'IN_PROGRESS')}
                            className="px-2 py-0.5 bg-blue-50 text-blue-600 hover:bg-blue-600 hover:text-white rounded text-[11px] font-bold transition-colors"
                          >
                            Tiếp tục làm
                          </button>
                        )}
                        {task.status === 'DONE' && (
                          <span className="text-[10px] font-bold text-emerald-600 flex items-center gap-0.5">
                            <IconCheck className="w-3 h-3" /> Hoàn thành
                          </span>
                        )}
                      </div>
                    </div>
                  );
                })}

                {colTasks.length === 0 && (
                  <div className="p-6 text-center text-slate-400 text-xs border border-dashed border-slate-200 rounded-xl">
                    Chưa có việc nào
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
