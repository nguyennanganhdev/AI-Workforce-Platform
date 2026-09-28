import { useState } from 'react';
import {
  IconColumns,
  IconCalendar,
  IconBuilding,
  IconPlus,
} from '@tabler/icons-react';
import { useOperationsData } from '../hooks/use-operations-data';

export function EvidenceGallery() {
  const { evidence, workOrders, incidents } = useOperationsData();
  const [filterPhase, setFilterPhase] = useState<string>('ALL');

  const filteredEvidence = filterPhase === 'ALL'
    ? evidence
    : evidence.filter((e) => e.capture_phase === filterPhase);

  return (
    <div className="space-y-6 font-sans">
      {/* Title Header with Blue Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="w-1.5 h-6 bg-blue-600 rounded-full shrink-0" />
          <div>
            <h1 className="text-xl font-bold text-slate-900 tracking-tight">
              Hình Ảnh & Bằng Chứng Hiện Trường
            </h1>
            <p className="text-xs text-slate-500 font-medium">
              Lưu trữ hình ảnh Trước - Sau thi công và Biên bản nghiệm thu phục vụ đối soát
            </p>
          </div>
        </div>

        {/* Phase Filter Tabs */}
        <div className="flex items-center gap-1.5 bg-white p-1 rounded-xl border border-slate-200 shadow-2xs">
          {[
            { id: 'ALL', label: 'Tất cả ảnh' },
            { id: 'BEFORE', label: 'Trước khi làm' },
            { id: 'AFTER', label: 'Sau hoàn thành' },
            { id: 'QC', label: 'Nghiệm thu' },
          ].map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setFilterPhase(tab.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-colors ${
                filterPhase === tab.id
                  ? 'bg-blue-600 text-white shadow-2xs'
                  : 'text-slate-600 hover:bg-slate-100'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Gallery Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
        {filteredEvidence.map((item) => {
          const wo = workOrders.find((w) => w.id === item.work_order_id);
          const inc = incidents.find((i) => i.id === item.incident_id);

          return (
            <div
              key={item.id}
              className="bg-white rounded-2xl border border-slate-200/80 overflow-hidden shadow-xs hover:shadow-md transition-shadow group"
            >
              <div className="relative aspect-video bg-slate-900 overflow-hidden">
                <img
                  src={item.file_url}
                  alt={item.metadata.caption || 'Evidence'}
                  className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                />
                <span
                  className={`absolute top-2.5 left-2.5 px-2.5 py-0.5 text-white font-extrabold text-[10px] rounded-full backdrop-blur-xs shadow-xs ${
                    item.capture_phase === 'BEFORE'
                      ? 'bg-rose-600/90'
                      : item.capture_phase === 'AFTER'
                        ? 'bg-emerald-600/90'
                        : 'bg-purple-600/90'
                  }`}
                >
                  {item.capture_phase === 'BEFORE'
                    ? 'Trước khi làm'
                    : item.capture_phase === 'AFTER'
                      ? 'Sau hoàn thành'
                      : 'Nghiệm thu'}
                </span>
                <span className="absolute bottom-2 right-2 px-1.5 py-0.5 bg-black/60 text-white font-mono text-[9px] rounded">
                  {item.id}
                </span>
              </div>

              <div className="p-4 space-y-2">
                <p className="font-bold text-xs text-slate-800 line-clamp-2 leading-snug">
                  {item.metadata.caption}
                </p>

                <div className="text-[11px] text-slate-500 space-y-1 pt-1 border-t border-slate-100">
                  <div className="flex items-center gap-1.5 truncate">
                    <IconBuilding className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                    <span className="truncate">{inc?.location_json.towerCode || 'Tòa nhà'} • Phiếu {wo?.id || '—'}</span>
                  </div>
                  <div className="flex items-center gap-1.5 text-slate-400">
                    <IconCalendar className="w-3.5 h-3.5 shrink-0" />
                    <span>{new Date(item.created_at).toLocaleTimeString('vi-VN')}</span>
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
