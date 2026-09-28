import { useState, useMemo, useRef } from 'react';
import {
  IconX,
  IconPhoto,
  IconPlus,
  IconCheck,
  IconBuilding,
  IconDeviceMobile,
  IconCalendar,
  IconColumns,
  IconUpload,
  IconMapPin,
  IconShieldCheck,
  IconCamera,
  IconFileCheck,
} from '@tabler/icons-react';
import type { VhWorkOrder } from '../types/work-order';
import type { CapturePhase } from '../types/evidence';
import { useOperationsData } from '../hooks/use-operations-data';

interface EvidenceModalProps {
  workOrder: VhWorkOrder;
  onClose: () => void;
}

const burnWatermarkOntoImage = (
  imgSrc: string,
  meta: {
    woId: string;
    phase: string;
    actor: string;
    role: string;
    gps: string;
    time: string;
  },
): Promise<string> => {
  return new Promise((resolve) => {
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => {
      const canvas = document.createElement('canvas');
      const maxDim = 1200;
      let w = img.width;
      let h = img.height;
      if (w > maxDim || h > maxDim) {
        if (w > h) {
          h = Math.round((h * maxDim) / w);
          w = maxDim;
        } else {
          w = Math.round((w * maxDim) / h);
          h = maxDim;
        }
      }
      canvas.width = w;
      canvas.height = h;
      const ctx = canvas.getContext('2d');
      if (!ctx) {
        resolve(imgSrc);
        return;
      }
      ctx.drawImage(img, 0, 0, w, h);

      // Dark gradient banner
      const bannerHeight = Math.max(85, Math.round(h * 0.16));
      const gradient = ctx.createLinearGradient(0, h - bannerHeight, 0, h);
      gradient.addColorStop(0, 'rgba(15, 23, 42, 0)');
      gradient.addColorStop(0.3, 'rgba(15, 23, 42, 0.88)');
      gradient.addColorStop(1, 'rgba(15, 23, 42, 0.98)');
      ctx.fillStyle = gradient;
      ctx.fillRect(0, h - bannerHeight, w, bannerHeight);

      // Text styling
      const fontSize = Math.max(13, Math.round(w / 48));
      const padX = Math.round(w * 0.03);
      const baseY = h - bannerHeight + Math.round(bannerHeight * 0.22);
      const lineGap = fontSize + 4;

      ctx.textBaseline = 'top';
      ctx.font = `bold ${fontSize}px sans-serif`;
      ctx.fillStyle = '#38bdf8';
      ctx.fillText(`[${meta.woId}] • GIAI ĐOẠN: ${meta.phase}`, padX, baseY);

      ctx.font = `500 ${Math.round(fontSize * 0.9)}px sans-serif`;
      ctx.fillStyle = '#f8fafc';
      ctx.fillText(`Người chụp: ${meta.actor} (${meta.role})`, padX, baseY + lineGap);

      ctx.font = `400 ${Math.round(fontSize * 0.82)}px monospace`;
      ctx.fillStyle = '#cbd5e1';
      ctx.fillText(`GPS: ${meta.gps} | Thời gian: ${meta.time}`, padX, baseY + lineGap * 2);

      // Top-right Security Watermark Seal
      const stampW = Math.round(w * 0.26);
      const stampH = Math.round(fontSize * 1.6);
      ctx.fillStyle = 'rgba(225, 29, 72, 0.9)';
      ctx.fillRect(w - stampW - padX, padX, stampW, stampH);
      ctx.fillStyle = '#ffffff';
      ctx.font = `bold ${Math.round(fontSize * 0.75)}px sans-serif`;
      ctx.fillText('BẰNG CHỨNG XÁC THỰC', w - stampW - padX + 8, padX + 4);

      resolve(canvas.toDataURL('image/jpeg', 0.82));
    };
    img.onerror = () => resolve(imgSrc);
    img.src = imgSrc;
  });
};

export function EvidenceModal({ workOrder, onClose }: EvidenceModalProps) {
  const { evidence, addEvidence, currentProfile } = useOperationsData();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const relatedEvidence = useMemo(() => {
    return evidence.filter((e) => e.work_order_id === workOrder.id);
  }, [evidence, workOrder.id]);

  const [activeTab, setActiveTab] = useState<'COMPARISON' | 'ALL'>('COMPARISON');
  const [newCaption, setNewCaption] = useState('');
  const [newPhase, setNewPhase] = useState<CapturePhase>('BEFORE');
  const [isUploading, setIsUploading] = useState(false);

  // File Upload State
  const [selectedFileUrl, setSelectedFileUrl] = useState<string | null>(null);
  const [selectedFileName, setSelectedFileName] = useState<string>('');
  const [selectedFileSize, setSelectedFileSize] = useState<number>(0);
  const [showWatermark, setShowWatermark] = useState(true);
  const [burnStatus, setBurnStatus] = useState<string | null>(null);

  // Real GPS State
  const [gpsData, setGpsData] = useState<{
    lat: number;
    lng: number;
    accuracy: number;
    status: 'ACQUIRED' | 'FETCHING' | 'DENIED' | 'UNAVAILABLE';
    timestamp: string;
  }>({
    lat: 21.0031,
    lng: 105.7489,
    accuracy: 8,
    status: 'FETCHING',
    timestamp: new Date().toISOString(),
  });

  const beforeItems = relatedEvidence.filter((e) => e.capture_phase === 'BEFORE');
  const afterItems = relatedEvidence.filter((e) => e.capture_phase === 'AFTER');
  const qcItems = relatedEvidence.filter((e) => e.capture_phase === 'QC');

  // Fetch real device geolocation
  const fetchDeviceGps = () => {
    if (typeof window !== 'undefined' && 'geolocation' in navigator) {
      setGpsData((prev) => ({ ...prev, status: 'FETCHING' }));
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          setGpsData({
            lat: Number(pos.coords.latitude.toFixed(6)),
            lng: Number(pos.coords.longitude.toFixed(6)),
            accuracy: Math.round(pos.coords.accuracy),
            status: 'ACQUIRED',
            timestamp: new Date().toISOString(),
          });
        },
        (err) => {
          setGpsData((prev) => ({
            ...prev,
            status: err.code === 1 ? 'DENIED' : 'UNAVAILABLE',
          }));
        },
        { enableHighAccuracy: true, timeout: 6000 },
      );
    } else {
      setGpsData((prev) => ({ ...prev, status: 'UNAVAILABLE' }));
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setSelectedFileName(file.name);
      setSelectedFileSize(file.size);

      const reader = new FileReader();
      reader.onload = (event) => {
        setSelectedFileUrl(event.target?.result as string);
      };
      reader.readAsDataURL(file);
    }
  };

  const handleUseSamplePhoto = (phase: CapturePhase) => {
    setSelectedFileName(`sample_${phase.toLowerCase()}_camera.jpg`);
    setSelectedFileSize(1024 * 480);
    if (phase === 'BEFORE') {
      setSelectedFileUrl('https://images.unsplash.com/photo-1584992236310-6edddc08acff?w=1000&auto=format&fit=crop&q=80');
      setNewCaption('Hiện trạng rò rỉ nước tại van áp suất trục cấp tầng 12 trước thi công');
    } else if (phase === 'AFTER') {
      setSelectedFileUrl('https://images.unsplash.com/photo-1581578731548-c64695cc6952?w=1000&auto=format&fit=crop&q=80');
      setNewCaption('Đã thay thế gioăng cao su chịu áp và siết chặt co nối, khu vực khô ráo');
    } else {
      setSelectedFileUrl('https://images.unsplash.com/photo-1541888946425-d0fbb18f15f7?w=1000&auto=format&fit=crop&q=80');
      setNewCaption('Biên bản đo kiểm định áp suất nước đạt 3.8 bar an toàn');
    }
  };

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    const rawUrl =
      selectedFileUrl ||
      (newPhase === 'BEFORE'
        ? 'https://images.unsplash.com/photo-1584992236310-6edddc08acff?w=1000&auto=format&fit=crop&q=80'
        : 'https://images.unsplash.com/photo-1581578731548-c64695cc6952?w=1000&auto=format&fit=crop&q=80');

    const gpsString = `${gpsData.lat}° N, ${gpsData.lng}° E (Sai số ±${gpsData.accuracy}m)`;
    const timeString = new Date().toLocaleString('vi-VN');

    setBurnStatus('Đang đóng dấu Watermark trực tiếp vào điểm ảnh...');
    try {
      const finalBurnedUrl = showWatermark
        ? await burnWatermarkOntoImage(rawUrl, {
            woId: workOrder.id,
            phase: newPhase,
            actor: currentProfile.name,
            role: currentProfile.roleTitle,
            gps: gpsString,
            time: timeString,
          })
        : rawUrl;

      addEvidence({
        incident_id: workOrder.incident_id,
        task_id: workOrder.task_id,
        work_order_id: workOrder.id,
        capture_phase: newPhase,
        file_url: finalBurnedUrl,
        caption: newCaption || `Ảnh nghiệm thu ${newPhase === 'BEFORE' ? 'Trước' : newPhase === 'AFTER' ? 'Sau' : 'QC'} tại hiện trường`,
        fileMetadata: {
          fileName: selectedFileName || `evidence_${newPhase.toLowerCase()}.jpg`,
          sizeBytes: selectedFileSize || 320000,
          gpsCoordinates: gpsString,
        },
      });

      // Reset Form
      setSelectedFileUrl(null);
      setSelectedFileName('');
      setSelectedFileSize(0);
      setNewCaption('');
      setIsUploading(false);
      setBurnStatus(null);
    } catch (err: any) {
      alert(`⚠️ Không thể lưu bằng chứng: ${err.message}`);
      setBurnStatus(null);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="evidence-modal-title"
      onKeyDown={(e) => {
        if (e.key === 'Escape') onClose();
      }}
      className="fixed inset-0 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4 z-50 font-sans"
    >
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
                <span className="text-xs text-slate-400">•</span>
                <span className="text-xs text-slate-600 font-medium">Lần thi công #{workOrder.attempt_no}</span>
              </div>
              <p className="text-xs text-slate-500 mt-0.5">
                Chụp ảnh Before/After có đóng dấu Watermark toạ độ, thời gian & danh tính người thao tác
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setIsUploading(!isUploading)}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-bold transition-all shadow-xs"
            >
              <IconCamera className="w-4 h-4" />
              <span>{isUploading ? 'Đóng form chụp' : 'Chụp / Tải ảnh mới'}</span>
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

        {/* Upload Form with Real File Input & Preview */}
        {isUploading && (
          <form onSubmit={handleUpload} className="p-5 bg-blue-50/70 border-b border-blue-200 space-y-4">
            <div className="flex items-center justify-between">
              <span className="font-bold text-xs text-blue-900 flex items-center gap-1.5">
                <IconCamera className="w-4 h-4 text-blue-600" />
                <span>Thao tác máy ảnh & Tải tệp thực tế</span>
              </span>
              <span className="text-[11px] text-slate-500 font-medium">
                Người tải: <strong>{currentProfile.name}</strong> ({currentProfile.roleTitle})
              </span>
            </div>

            {/* Hidden HTML File Input with capture="environment" for Mobile Cameras */}
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              capture="environment"
              onChange={handleFileChange}
              className="hidden"
            />

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* File Selection Controls */}
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <label htmlFor="evidence-phase-select" className="font-bold text-xs text-slate-700 w-24 shrink-0">
                    Giai đoạn:
                  </label>
                  <select
                    id="evidence-phase-select"
                    value={newPhase}
                    onChange={(e) => setNewPhase(e.target.value as CapturePhase)}
                    className="flex-1 bg-white border border-slate-300 rounded-lg p-2 text-xs font-semibold focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
                  >
                    <option value="BEFORE">1. Trước khi làm (BEFORE - Bắt buộc)</option>
                    <option value="AFTER">2. Sau khi hoàn thành (AFTER - Bắt buộc)</option>
                    <option value="QC" disabled={!currentProfile.canQC}>
                      3. Nghiệm thu độc lập (QC {!currentProfile.canQC ? '• Chỉ dành cho QC' : ''})
                    </option>
                  </select>
                </div>

                <div className="space-y-1">
                  <label htmlFor="evidence-caption-input" className="font-bold text-xs text-slate-700 block">
                    Mô tả chi tiết ảnh / Kết quả đo:
                  </label>
                  <input
                    id="evidence-caption-input"
                    type="text"
                    required
                    placeholder="VD: Van áp suất trục C tầng 12 đã siết chặt co nối..."
                    value={newCaption}
                    onChange={(e) => setNewCaption(e.target.value)}
                    className="w-full p-2 bg-white border border-slate-300 rounded-lg text-xs focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
                  />
                </div>

                {/* Real GPS Info & Refresh button */}
                <div className="p-2.5 bg-white border border-slate-200 rounded-xl text-[11px] flex items-center justify-between text-slate-600">
                  <div className="flex items-center gap-1.5 truncate">
                    <IconMapPin className="w-3.5 h-3.5 text-rose-500 shrink-0" />
                    <span>
                      GPS: <strong>{gpsData.lat}° N, {gpsData.lng}° E</strong> (±{gpsData.accuracy}m)
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={fetchDeviceGps}
                    className="text-[10px] text-blue-600 font-bold hover:underline shrink-0"
                  >
                    Lấy lại GPS
                  </button>
                </div>

                {/* File picker buttons */}
                <div className="pt-1 flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    className="px-3.5 py-2 bg-white hover:bg-slate-100 text-slate-800 rounded-xl text-xs font-bold border border-slate-300 flex items-center gap-1.5 transition-colors shadow-2xs focus-visible:ring-2 focus-visible:ring-blue-500"
                  >
                    <IconUpload className="w-4 h-4 text-blue-600" />
                    <span>Mở Camera / Chọn ảnh từ máy</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => handleUseSamplePhoto(newPhase)}
                    className="px-3 py-2 bg-blue-100/80 hover:bg-blue-200 text-blue-800 rounded-xl text-xs font-semibold transition-colors"
                  >
                    ⚡ Dùng ảnh mẫu ({newPhase})
                  </button>
                </div>

                {selectedFileName && (
                  <div className="p-2.5 bg-white border border-slate-200 rounded-xl text-xs flex items-center justify-between text-slate-600">
                    <span className="truncate max-w-[200px]">Tệp: <strong>{selectedFileName}</strong></span>
                    <span className="font-mono text-slate-400">{Math.round(selectedFileSize / 1024)} KB</span>
                  </div>
                )}
              </div>

              {/* Live Preview with Realtime Watermark Overlay */}
              <div className="space-y-2">
                <span className="font-bold text-xs text-slate-700 block">Xem trước ảnh & Dấu Watermark:</span>
                <div className="relative aspect-video bg-slate-900 rounded-xl overflow-hidden border border-slate-300 shadow-inner">
                  {selectedFileUrl ? (
                    <>
                      <img
                        src={selectedFileUrl}
                        alt="Preview bằng chứng"
                        width={640}
                        height={360}
                        className="w-full h-full object-cover"
                      />
                      {showWatermark && (
                        <div className="absolute inset-x-0 bottom-0 p-2.5 bg-gradient-to-t from-black/85 via-black/45 to-transparent text-white font-mono text-[9px] leading-relaxed backdrop-blur-2xs">
                          <div className="flex items-center justify-between">
                            <span className="font-bold text-sky-400">VINHOMES OPERATIONS • {workOrder.id}</span>
                            <span className="bg-rose-600/90 text-white font-bold px-1 rounded text-[8px]">BẰNG CHỨNG XÁC THỰC</span>
                          </div>
                          <div>Toạ độ GPS: {gpsData.lat}° N, {gpsData.lng}° E (±{gpsData.accuracy}m)</div>
                          <div>Thời gian: {new Date().toLocaleString('vi-VN')}</div>
                          <div>Người chụp: {currentProfile.name} ({currentProfile.roleTitle})</div>
                        </div>
                      )}
                    </>
                  ) : (
                    <div className="w-full h-full flex flex-col items-center justify-center text-slate-400 text-xs p-4 text-center">
                      <IconCamera className="w-8 h-8 text-slate-500 mb-1" />
                      <span>Chưa có ảnh được chọn. Bấm "Mở Camera" hoặc "Dùng ảnh mẫu".</span>
                    </div>
                  )}
                </div>
              </div>
            </div>

            <div className="flex items-center justify-between pt-2 border-t border-blue-200/60">
              <div>
                {burnStatus && <span className="text-xs text-blue-700 font-bold animate-pulse">{burnStatus}</span>}
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => {
                    setIsUploading(false);
                    setSelectedFileUrl(null);
                  }}
                  className="px-4 py-2 border border-slate-200 rounded-xl text-xs font-semibold text-slate-600 hover:bg-slate-50"
                >
                  Hủy
                </button>
                <button
                  type="submit"
                  disabled={!selectedFileUrl || !!burnStatus}
                  className="px-5 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-xl text-xs font-bold transition-all shadow-sm flex items-center gap-1.5"
                >
                  <IconFileCheck className="w-4 h-4" />
                  <span>Đóng dấu & Lưu bằng chứng</span>
                </button>
              </div>
            </div>
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
            <span>Đối chứng Trước ⟷ Sau ({beforeItems.length} Trước / {afterItems.length} Sau)</span>
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
            <span>Tất cả bằng chứng ({relatedEvidence.length})</span>
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
                    Ảnh trước khi thi công (BEFORE)
                  </span>
                  <span className="text-[11px] text-slate-400 font-semibold">{beforeItems.length} ảnh</span>
                </div>

                {beforeItems.length === 0 ? (
                  <div className="p-8 border-2 border-dashed border-rose-200 rounded-2xl text-center text-rose-600 text-xs bg-rose-50/30">
                    ✕ Chưa có hình ảnh trước thi công. Bắt buộc phải có trước khi báo hoàn thành!
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
                        <div className="absolute inset-x-0 bottom-0 p-2 bg-black/60 text-white font-mono text-[8px] leading-tight">
                          <div>Toạ độ: {String(item.metadata.gpsCoordinates || '21.0031° N, 105.7489° E')}</div>
                          <div>Người chụp: {String(item.metadata.uploadedByName || item.uploaded_by)}</div>
                        </div>
                      </div>
                      <div className="p-3.5 space-y-1">
                        <p className="font-bold text-xs text-slate-800">{item.metadata.caption}</p>
                        <p className="text-[11px] text-slate-400 flex items-center gap-1">
                          <IconCalendar className="w-3 h-3" />
                          <span>{new Date(item.created_at).toLocaleTimeString('vi-VN')}</span>
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
                    Ảnh sau khi hoàn thành (AFTER)
                  </span>
                  <span className="text-[11px] text-slate-400 font-semibold">{afterItems.length} ảnh</span>
                </div>

                {afterItems.length === 0 ? (
                  <div className="p-8 border-2 border-dashed border-emerald-200 rounded-2xl text-center text-emerald-600 text-xs bg-emerald-50/30">
                    ✕ Chưa có hình ảnh sau hoàn thành. Bắt buộc phải có để tiến hành nghiệm thu QC!
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
                        <div className="absolute inset-x-0 bottom-0 p-2 bg-black/60 text-white font-mono text-[8px] leading-tight">
                          <div>Toạ độ: {String(item.metadata.gpsCoordinates || '21.0031° N, 105.7489° E')}</div>
                          <div>Người chụp: {String(item.metadata.uploadedByName || item.uploaded_by)}</div>
                        </div>
                      </div>
                      <div className="p-3.5 space-y-1">
                        <p className="font-bold text-xs text-slate-800">{item.metadata.caption}</p>
                        <p className="text-[11px] text-slate-400 flex items-center gap-1">
                          <IconCalendar className="w-3 h-3" />
                          <span>{new Date(item.created_at).toLocaleTimeString('vi-VN')}</span>
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
                      className={`absolute top-2 left-2 px-2 py-0.5 text-white font-bold text-[10px] rounded ${
                        item.capture_phase === 'BEFORE'
                          ? 'bg-rose-600'
                          : item.capture_phase === 'AFTER'
                            ? 'bg-emerald-600'
                            : 'bg-purple-600'
                      }`}
                    >
                      {item.capture_phase === 'BEFORE' ? 'Trước khi làm' : item.capture_phase === 'AFTER' ? 'Sau khi làm' : 'QC'}
                    </span>
                  </div>
                  <div className="p-3 space-y-1">
                    <p className="font-bold text-xs text-slate-800 line-clamp-1">{item.metadata.caption}</p>
                    <p className="text-[10px] text-slate-400">
                      Người chụp: {String(item.metadata.uploadedByName || item.uploaded_by)}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
