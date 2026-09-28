import { useState, useMemo } from 'react';
import {
  IconX,
  IconPhoto,
  IconPlus,
  IconCheck,
  IconBuilding,
  IconDeviceMobile,
  IconCalendar,
  IconColumns,
} from '@tabler/icons-react';
import type { VhWorkOrder } from '../types/work-order';
import type { CapturePhase } from '../types/evidence';
import { useOperationsData } from '../hooks/use-operations-data';

interface EvidenceModalProps {
  workOrder: VhWorkOrder;
  onClose: () => void;
}

export function EvidenceModal({ workOrder, onClose }: EvidenceModalProps) {
  const { evidence, addEvidence } = useOperationsData();

  const relatedEvidence = useMemo(() => {
    return evidence.filter((e) => e.work_order_id === workOrder.id);
  }, [evidence, workOrder.id]);

  const [activeTab, setActiveTab] = useState<'ALL' | 'BEFORE' | 'AFTER' | 'COMPARISON'>('COMPARISON');
  const [newCaption, setNewCaption] = useState('');
  const [newPhase, setNewPhase] = useState<CapturePhase>('AFTER');
  const [isUploading, setIsUploading] = useState(false);

  const beforeItems = relatedEvidence.filter((e) => e.capture_phase === 'BEFORE');
  const afterItems = relatedEvidence.filter((e) => e.capture_phase === 'AFTER');
  const qcItems = relatedEvidence.filter((e) => e.capture_phase === 'QC');

  const handleUpload = (e: React.FormEvent) => {
    e.preventDefault();
    addEvidence({
      incident_id: workOrder.incident_id,
      task_id: workOrder.task_id,
      work_order_id: workOrder.id,
      file_id: `FILE-${Date.now().toString().slice(-4)}`,
      kind: 'IMAGE',
      capture_phase: newPhase,
      metadata: {
        caption: newCaption || `Ảnh nghiệm thu ${newPhase} tại hiện trường`,
        locationNote: 'Khu vực làm việc thực tế',
        deviceInfo: 'Camera giám sát di động',
      },
      file_url:
        newPhase === 'BEFORE'
          ? 'https://images.unsplash.com/photo-1584992236310-6edddc08acff?w=800&auto=format&fit=crop&q=80'
          : 'https://images.unsplash.com/photo-1581578731548-c64695cc6952?w=800&auto=format&fit=crop&q=80',
      uploaded_by: workOrder.executor_id || 'usr-tech-01',
    });
    setNewCaption('');
    setIsUploading(false);
  };

  return (
    <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4 z-50 font-sans">
      <div className="bg-white rounded-2xl max-w-4xl w-full max-h-[92vh] overflow-y-auto shadow-2xl border border-slate-200">
        {/* Header */}
        <div className="p-5 border-b border-slate-100 flex items-center justify-between sticky top-0 bg-white z-10">
          <div className="flex items-center gap-2.5">
            <div className="w-1.5 h-6 bg-blue-600 rounded-full" />
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-bold text-slate-900 text-base">Kho Bằng Chứng Hiện Trường</h3>
                <span className="font-mono text-xs px-2 py-0.5 bg-blue-50 text-blue-700 font-bold rounded">
                  {workOrder.id}
                </span>
              </div>
              <p className="text-xs text-slate-500 mt-0.5">
                Đối chứng hình ảnh trước và sau khi hoàn thành • {relatedEvidence.length} ảnh ghi nhận
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setIsUploading(!isUploading)}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-bold transition-all shadow-xs"
            >
              <IconPlus className="w-4 h-4" />
              <span>Chụp / Tải ảnh</span>
            </button>
            <button
              type="button"
              onClick={onClose}
              className="w-8 h-8 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 flex items-center justify-center transition-colors"
            >
              <IconX className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Upload Form (Expandable) */}
        {isUploading && (
          <form onSubmit={handleUpload} className="p-4 bg-blue-50/60 border-b border-blue-100 flex flex-wrap items-center gap-3 text-xs">
            <div className="flex items-center gap-2">
              <span className="font-bold text-blue-900">Giai đoạn:</span>
              <select
                value={newPhase}
                onChange={(e) => setNewPhase(e.target.value as CapturePhase)}
                className="bg-white border border-slate-200 rounded-lg p-1.5 text-xs font-semibold"
              >
                <option value="BEFORE">Trước khi làm</option>
                <option value="AFTER">Sau khi hoàn thành</option>
                <option value="QC">Biên bản nghiệm thu</option>
              </select>
            </div>

            <input
              type="text"
              placeholder="Nhập mô tả hình ảnh hoặc kết quả đo..."
              value={newCaption}
              onChange={(e) => setNewCaption(e.target.value)}
              className="flex-1 min-w-[200px] p-2 bg-white border border-slate-200 rounded-lg text-xs"
            />

            <button
              type="submit"
              className="px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-lg"
            >
              Xác nhận tải lên
            </button>
          </form>
        )}

        {/* View Mode Tabs */}
        <div className="px-6 pt-4 border-b border-slate-100 flex items-center gap-2">
          <button
            type="button"
            onClick={() => setActiveTab('COMPARISON')}
            className={`pb-3 text-xs font-bold border-b-2 flex items-center gap-1.5 transition-colors ${
              activeTab === 'COMPARISON'
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            <IconColumns className="w-4 h-4" />
            <span>So sánh Trước ⟷ Sau</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('ALL')}
            className={`pb-3 text-xs font-bold border-b-2 flex items-center gap-1.5 transition-colors ${
              activeTab === 'ALL'
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            <IconPhoto className="w-4 h-4" />
            <span>Tất cả ({relatedEvidence.length})</span>
          </button>
        </div>

        {/* Gallery Content */}
        <div className="p-6">
          {activeTab === 'COMPARISON' ? (
            /* Comparison Mode: Side by Side Before & After */
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Left Column: BEFORE */}
              <div className="space-y-3">
                <div className="flex items-center justify-between pb-2 border-b border-rose-100">
                  <span className="text-xs font-extrabold uppercase tracking-wider text-rose-600 bg-rose-50 px-2.5 py-1 rounded-full">
                    Trước khi làm
                  </span>
                  <span className="text-[11px] text-slate-400 font-semibold">{beforeItems.length} ảnh</span>
                </div>

                {beforeItems.length === 0 ? (
                  <div className="p-8 border-2 border-dashed border-slate-200 rounded-2xl text-center text-slate-400 text-xs">
                    Chưa có hình ảnh trước thi công
                  </div>
                ) : (
                  beforeItems.map((item) => (
                    <div key={item.id} className="bg-slate-50 rounded-2xl border border-slate-200 overflow-hidden shadow-2xs group">
                      <div className="relative aspect-video bg-slate-900 overflow-hidden">
                        <img
                          src={item.file_url}
                          alt={item.metadata.caption || 'Evidence'}
                          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                        />
                        <span className="absolute top-2 left-2 px-2 py-0.5 bg-rose-600/90 text-white font-bold text-[10px] rounded backdrop-blur-xs">
                          Trước khi làm
                        </span>
                      </div>
                      <div className="p-3.5 space-y-1">
                        <p className="font-bold text-xs text-slate-800">{item.metadata.caption}</p>
                        <p className="text-[11px] text-slate-400 flex items-center gap-1">
                          <IconCalendar className="w-3 h-3" />
                          {new Date(item.created_at).toLocaleTimeString('vi-VN')} • {item.metadata.locationNote}
                        </p>
                      </div>
                    </div>
                  ))
                )}
              </div>

              {/* Right Column: AFTER */}
              <div className="space-y-3">
                <div className="flex items-center justify-between pb-2 border-b border-emerald-100">
                  <span className="text-xs font-extrabold uppercase tracking-wider text-emerald-600 bg-emerald-50 px-2.5 py-1 rounded-full">
                    Sau khi hoàn thành
                  </span>
                  <span className="text-[11px] text-slate-400 font-semibold">{afterItems.length} ảnh</span>
                </div>

                {afterItems.length === 0 ? (
                  <div className="p-8 border-2 border-dashed border-slate-200 rounded-2xl text-center text-slate-400 text-xs">
                    Chưa có hình ảnh sau hoàn thành
                  </div>
                ) : (
                  afterItems.map((item) => (
                    <div key={item.id} className="bg-slate-50 rounded-2xl border border-slate-200 overflow-hidden shadow-2xs group">
                      <div className="relative aspect-video bg-slate-900 overflow-hidden">
                        <img
                          src={item.file_url}
                          alt={item.metadata.caption || 'Evidence'}
                          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                        />
                        <span className="absolute top-2 left-2 px-2 py-0.5 bg-emerald-600/90 text-white font-bold text-[10px] rounded backdrop-blur-xs">
                          Đã hoàn thành
                        </span>
                      </div>
                      <div className="p-3.5 space-y-1">
                        <p className="font-bold text-xs text-slate-800">{item.metadata.caption}</p>
                        <p className="text-[11px] text-slate-400 flex items-center gap-1">
                          <IconCalendar className="w-3 h-3" />
                          {new Date(item.created_at).toLocaleTimeString('vi-VN')} • {item.metadata.locationNote}
                        </p>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          ) : (
            /* Grid View of all items */
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
              {relatedEvidence.map((item) => (
                <div key={item.id} className="bg-slate-50 rounded-2xl border border-slate-200 overflow-hidden shadow-2xs">
                  <div className="relative aspect-video bg-slate-900 overflow-hidden">
                    <img
                      src={item.file_url}
                      alt={item.metadata.caption}
                      className="w-full h-full object-cover"
                    />
                    <span
                      className={`absolute top-2 left-2 px-2 py-0.5 text-white font-bold text-[10px] rounded backdrop-blur-xs ${
                        item.capture_phase === 'BEFORE'
                          ? 'bg-rose-600/90'
                          : item.capture_phase === 'AFTER'
                            ? 'bg-emerald-600/90'
                            : 'bg-purple-600/90'
                      }`}
                    >
                      {item.capture_phase}
                    </span>
                  </div>
                  <div className="p-3 space-y-1">
                    <p className="font-bold text-xs text-slate-800 line-clamp-1">{item.metadata.caption}</p>
                    <p className="text-[11px] text-slate-400">
                      {new Date(item.created_at).toLocaleTimeString('vi-VN')}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-slate-100 flex items-center justify-end bg-slate-50/50">
          <button
            type="button"
            onClick={onClose}
            className="px-5 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-bold shadow-sm"
          >
            Đóng kho ảnh
          </button>
        </div>
      </div>
    </div>
  );
}
