import { useState } from 'react';
import {
  IconShield,
  IconCheck,
  IconClock,
  IconMapPin,
  IconAlertTriangle,
  IconPhoneCall,
  IconUser,
  IconCar,
  IconFileText,
  IconCamera,
  IconPlus,
  IconLock,
  IconFlame,
  IconHeartbeat,
  IconBuilding,
} from '@tabler/icons-react';
import { useOperationsData } from '../hooks/use-operations-data';
import type { SecurityIncidentReport } from '../types/security';

export function SecurityWorkspace() {
  const {
    securityCheckpoints,
    securityIncidents,
    securityHandovers,
    currentProfile,
    toggleSecurityCheckpoint,
    reportSecurityIncident,
    submitSecurityHandover,
  } = useOperationsData();

  const [activeTab, setActiveTab] = useState<'PATROL' | 'INCIDENTS' | 'HANDOVER' | 'EMERGENCY'>('PATROL');
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // New incident modal
  const [showIncidentModal, setShowIncidentModal] = useState(false);
  const [newTitle, setNewTitle] = useState('');
  const [newLocation, setNewLocation] = useState('Sảnh Tòa S2.01');
  const [newSeverity, setNewSeverity] = useState<'P1' | 'P2' | 'P3' | 'P4'>('P2');
  const [personName, setPersonName] = useState('');
  const [personRole, setPersonRole] = useState<'DELIVERY' | 'GUEST' | 'RESIDENT' | 'SUSPECT'>('DELIVERY');
  const [licensePlate, setLicensePlate] = useState('');
  const [areaIsolated, setAreaIsolated] = useState(false);
  const [actionTaken, setActionTaken] = useState('');

  // Checkpoint modal
  const [checkingCpId, setCheckingCpId] = useState<string | null>(null);
  const [cpNote, setCpNote] = useState('');

  const handleCheckin = (cpId: string) => {
    toggleSecurityCheckpoint(cpId, cpNote || 'Tình trạng an ninh bình thường, không có dấu hiệu bất thường.');
    setCheckingCpId(null);
    setCpNote('');
    setSuccessMsg('Đã check-in thành công tại điểm tuần tra!');
    setTimeout(() => setSuccessMsg(null), 3000);
  };

  const handleCreateIncident = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim()) return;

    reportSecurityIncident({
      title: newTitle,
      location: newLocation,
      severity: newSeverity,
      guard_id: currentProfile.id,
      guard_name: currentProfile.name,
      persons_involved: personName ? [{ name: personName, role: personRole }] : [],
      vehicles_involved: licensePlate ? [{ license_plate: licensePlate, vehicle_type: 'CAR' }] : [],
      area_isolated: areaIsolated,
      action_taken: actionTaken || 'Đã kiểm tra và xử lý lập biên bản tại chỗ.',
      evidence_urls: [
        'https://images.unsplash.com/photo-1541888946425-d0fbb18f15f7?w=800&auto=format&fit=crop&q=80',
      ],
      status: 'INVESTIGATING',
    });

    setShowIncidentModal(false);
    setNewTitle('');
    setPersonName('');
    setLicensePlate('');
    setActionTaken('');
    setSuccessMsg('Đã lập biên bản sự việc an ninh thành công!');
    setTimeout(() => setSuccessMsg(null), 3000);
  };

  return (
    <div className="space-y-6 font-sans">
      {/* Title Header with Blue Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-1.5 h-6 bg-blue-600 rounded-full shrink-0" />
          <div>
            <h1 className="text-xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
              <IconShield className="w-5 h-5 text-blue-600" />
              <span>Nghiệp Vụ An Ninh & Trật Tự Hiện Trường</span>
            </h1>
            <p className="text-xs text-slate-500 font-medium">
              Tuần tra theo tuyến, lập biên bản sự việc, kiểm soát ra vào và bàn giao ca trực an ninh
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="px-3 py-1 bg-blue-50 text-blue-700 font-semibold text-xs rounded-full border border-blue-200">
            Trực ca: {currentProfile.name} ({currentProfile.roleTitle})
          </span>
        </div>
      </div>

      {successMsg && (
        <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-xs font-semibold text-emerald-800 flex items-center justify-between shadow-2xs">
          <div className="flex items-center gap-2">
            <IconCheck className="w-4 h-4 text-emerald-600" />
            <span>{successMsg}</span>
          </div>
          <button type="button" onClick={() => setSuccessMsg(null)} className="text-emerald-500 text-xs">
            ✕
          </button>
        </div>
      )}

      {/* Navigation Tabs */}
      <div className="flex items-center gap-1.5 bg-white p-1 rounded-xl border border-slate-200 shadow-2xs overflow-x-auto">
        {[
          { id: 'PATROL', label: `Tuyến tuần tra (${securityCheckpoints.length})` },
          { id: 'INCIDENTS', label: `Biên bản sự việc (${securityIncidents.length})` },
          { id: 'HANDOVER', label: `Bàn giao ca trực` },
          { id: 'EMERGENCY', label: `Hỗ trợ khẩn cấp (SOS)` },
        ].map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setActiveTab(tab.id as any)}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-bold transition-colors shrink-0 ${
              activeTab === tab.id ? 'bg-blue-600 text-white shadow-2xs' : 'text-slate-600 hover:bg-slate-100'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab 1: Patrol Checkpoints */}
      {activeTab === 'PATROL' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-bold text-sm text-slate-900">Danh mục điểm kiểm soát theo tuyến</h3>
              <p className="text-xs text-slate-500">Nhân viên tuần tra bấm Check-in khi có mặt tại từng vị trí</p>
            </div>
            <span className="text-xs font-semibold text-emerald-700 bg-emerald-50 px-2.5 py-1 rounded-full border border-emerald-200">
              Đã check {securityCheckpoints.filter((c) => c.status === 'CHECKED').length}/{securityCheckpoints.length} điểm
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5">
            {securityCheckpoints.map((cp) => (
              <div
                key={cp.id}
                className={`bg-white rounded-2xl border p-4 shadow-2xs space-y-3 transition-all ${
                  cp.status === 'CHECKED' ? 'border-emerald-200 bg-emerald-50/20' : 'border-slate-200/80 hover:border-blue-300'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs font-bold text-slate-600 bg-slate-100 px-2 py-0.5 rounded">
                    Điểm #{cp.order} • {cp.id}
                  </span>
                  <span
                    className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                      cp.status === 'CHECKED' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'
                    }`}
                  >
                    {cp.status === 'CHECKED' ? '✓ Đã kiểm tra' : 'Chờ tuần tra'}
                  </span>
                </div>

                <div>
                  <h4 className="font-bold text-xs text-slate-900 leading-snug">{cp.name}</h4>
                  <p className="text-[11px] text-slate-500 flex items-center gap-1 mt-1">
                    <IconMapPin className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                    <span>{cp.location}</span>
                  </p>
                </div>

                {cp.notes && (
                  <p className="text-[11px] text-slate-600 bg-slate-50 p-2 rounded-xl border border-slate-100 italic">
                    "{cp.notes}"
                  </p>
                )}

                <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-[11px]">
                  <span className="text-slate-400">
                    {cp.checked_at
                      ? `${new Date(cp.checked_at).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })} • ${cp.guard_name}`
                      : 'Chưa có lượt check'}
                  </span>
                  {cp.status !== 'CHECKED' && (
                    <button
                      type="button"
                      onClick={() => setCheckingCpId(cp.id)}
                      className="px-3 py-1 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-bold transition-colors shadow-2xs"
                    >
                      Check-in ngay
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tab 2: Incident Reports */}
      {activeTab === 'INCIDENTS' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-bold text-sm text-slate-900">Biên bản sự việc & Vi phạm hiện trường</h3>
              <p className="text-xs text-slate-500">Lưu trữ thông tin người, phương tiện và biện pháp xử lý</p>
            </div>
            <button
              type="button"
              onClick={() => setShowIncidentModal(true)}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-xl flex items-center gap-1.5 shadow-2xs transition-colors"
            >
              <IconPlus className="w-4 h-4" />
              <span>Lập biên bản sự việc mới</span>
            </button>
          </div>

          <div className="space-y-3">
            {securityIncidents.map((inc) => (
              <div
                key={inc.id}
                className="bg-white rounded-2xl border border-slate-200/80 p-5 shadow-2xs space-y-3 hover:border-slate-300 transition-colors"
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-2 border-b border-slate-100">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-bold text-blue-600 bg-blue-50 px-2 py-0.5 rounded">
                      {inc.id}
                    </span>
                    <span className="text-slate-300">•</span>
                    <span className="text-xs font-bold text-slate-800">{inc.title}</span>
                  </div>

                  <div className="flex items-center gap-2">
                    <span
                      className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                        inc.severity === 'P1'
                          ? 'bg-rose-100 text-rose-700'
                          : inc.severity === 'P2'
                            ? 'bg-amber-100 text-amber-700'
                            : 'bg-blue-100 text-blue-700'
                      }`}
                    >
                      {inc.severity === 'P1' ? 'Khẩn cấp P1' : inc.severity === 'P2' ? 'Mức độ P2' : 'Bình thường'}
                    </span>
                    <span
                      className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${
                        inc.status === 'RESOLVED' ? 'bg-emerald-100 text-emerald-700' : 'bg-blue-100 text-blue-700'
                      }`}
                    >
                      {inc.status === 'RESOLVED' ? '✓ Đã xử lý xong' : 'Đang xử lý'}
                    </span>
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
                  <div>
                    <span className="text-slate-400 block text-[11px]">Vị trí:</span>
                    <strong className="text-slate-800">{inc.location}</strong>
                  </div>

                  <div>
                    <span className="text-slate-400 block text-[11px]">Người lập biên bản:</span>
                    <strong className="text-slate-800">{inc.guard_name}</strong>
                  </div>

                  <div>
                    <span className="text-slate-400 block text-[11px]">Thời gian:</span>
                    <span className="text-slate-600">{new Date(inc.reported_at).toLocaleString('vi-VN')}</span>
                  </div>
                </div>

                {/* Involved Persons / Vehicles */}
                {(inc.persons_involved.length > 0 || inc.vehicles_involved.length > 0) && (
                  <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 text-xs flex flex-wrap items-center gap-4">
                    {inc.persons_involved.map((p, idx) => (
                      <div key={idx} className="flex items-center gap-1.5">
                        <IconUser className="w-3.5 h-3.5 text-slate-500" />
                        <span>Đối tượng: <strong>{p.name}</strong> ({p.role})</span>
                      </div>
                    ))}
                    {inc.vehicles_involved.map((v, idx) => (
                      <div key={idx} className="flex items-center gap-1.5 font-mono text-blue-700 bg-blue-50 px-2 py-0.5 rounded">
                        <IconCar className="w-3.5 h-3.5" />
                        <span>{v.license_plate}</span>
                      </div>
                    ))}
                  </div>
                )}

                <p className="text-xs text-slate-700 leading-relaxed">
                  <strong>Biện pháp xử lý:</strong> {inc.action_taken}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tab 3: Shift Handover */}
      {activeTab === 'HANDOVER' && (
        <div className="space-y-4">
          <div className="bg-white rounded-2xl border border-slate-200/80 p-5 shadow-2xs space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <div>
                <h3 className="font-bold text-sm text-slate-900">Biên bản bàn giao ca trực an ninh</h3>
                <p className="text-xs text-slate-500">Kiểm kê công cụ hỗ trợ và các sự vụ an ninh còn tồn đọng</p>
              </div>
              <span className="px-3 py-1 bg-emerald-100 text-emerald-800 text-xs font-bold rounded-full">
                ✓ Ca hiện tại đã xác nhận
              </span>
            </div>

            {securityHandovers.map((sh) => (
              <div key={sh.id} className="space-y-3 text-xs">
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 p-3.5 bg-slate-50 rounded-xl border border-slate-200">
                  <div>
                    <span className="text-slate-400 block text-[11px]">Người bàn giao:</span>
                    <strong className="text-slate-800">{sh.handover_from_name}</strong>
                  </div>
                  <div>
                    <span className="text-slate-400 block text-[11px]">Người nhận ca:</span>
                    <strong className="text-slate-800">{sh.handover_to_name}</strong>
                  </div>
                  <div>
                    <span className="text-slate-400 block text-[11px]">Ca trực:</span>
                    <strong className="text-blue-700">{sh.shift_name}</strong>
                  </div>
                  <div>
                    <span className="text-slate-400 block text-[11px]">Thời gian bàn giao:</span>
                    <span className="text-slate-600">{new Date(sh.handover_at).toLocaleTimeString('vi-VN')}</span>
                  </div>
                </div>

                <div className="space-y-1.5">
                  <span className="font-bold text-slate-700">Kiểm kê công cụ hỗ trợ:</span>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                    <div className="p-2.5 bg-white border border-slate-200 rounded-xl flex items-center justify-between">
                      <span className="text-slate-500">Bộ đàm:</span>
                      <strong className="text-slate-800">{sh.equipment_status.walkie_talkie_count} chiếc</strong>
                    </div>
                    <div className="p-2.5 bg-white border border-slate-200 rounded-xl flex items-center justify-between">
                      <span className="text-slate-500">Dùi cui tuần tra:</span>
                      <strong className="text-slate-800">{sh.equipment_status.patrol_baton_count} chiếc</strong>
                    </div>
                    <div className="p-2.5 bg-white border border-slate-200 rounded-xl flex items-center justify-between">
                      <span className="text-slate-500">Đèn pin chiếu xa:</span>
                      <strong className="text-slate-800">{sh.equipment_status.flashlight_count} chiếc</strong>
                    </div>
                    <div className="p-2.5 bg-white border border-slate-200 rounded-xl flex items-center justify-between">
                      <span className="text-slate-500">Chìa khóa tổng:</span>
                      <strong className="text-emerald-700 font-bold">✓ Đủ 100%</strong>
                    </div>
                  </div>
                </div>

                <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl text-amber-900 space-y-1">
                  <span className="font-bold block">Vấn đề cần ca sau theo dõi:</span>
                  <p className="italic">"{sh.open_security_issues.join(', ')}"</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tab 4: Emergency SOS */}
      {activeTab === 'EMERGENCY' && (
        <div className="space-y-4">
          <div className="p-5 bg-rose-50 border border-rose-200 rounded-2xl space-y-3 text-rose-900">
            <div className="flex items-center gap-2">
              <IconAlertTriangle className="w-5 h-5 text-rose-600" />
              <h3 className="font-bold text-sm">Đường dây nóng Phản ứng Khẩn cấp (Hotline Hiện Trường)</h3>
            </div>
            <p className="text-xs text-rose-800 leading-relaxed">
              Khi xảy ra tình huống khẩn cấp vượt tầm kiểm soát (Cháy nổ, Cấp cứu y tế, Đột nhập nguy hiểm), nhân viên an ninh bấm kết nối trực tiếp đến các đơn vị hỗ trợ:
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3 pt-2">
              <div className="p-3.5 bg-white rounded-xl border border-rose-200 flex flex-col justify-between space-y-2 shadow-2xs">
                <div className="flex items-center gap-2 text-rose-700 font-bold text-xs">
                  <IconFlame className="w-4 h-4 text-rose-600" />
                  <span>Cứu Hỏa & PCCC</span>
                </div>
                <div className="font-mono text-lg font-bold text-rose-600">114</div>
                <button
                  type="button"
                  onClick={() => alert('Đang kết nối đến Đội PCCC cơ sở Vinhomes Smart City')}
                  className="px-3 py-1.5 bg-rose-600 text-white rounded-lg text-xs font-bold hover:bg-rose-700"
                >
                  Gọi khẩn cấp
                </button>
              </div>

              <div className="p-3.5 bg-white rounded-xl border border-rose-200 flex flex-col justify-between space-y-2 shadow-2xs">
                <div className="flex items-center gap-2 text-rose-700 font-bold text-xs">
                  <IconHeartbeat className="w-4 h-4 text-rose-600" />
                  <span>Y Tế Vinmec</span>
                </div>
                <div className="font-mono text-lg font-bold text-rose-600">115 / 024 3974</div>
                <button
                  type="button"
                  onClick={() => alert('Đang kết nối xe cấp cứu Vinmec Smart City')}
                  className="px-3 py-1.5 bg-rose-600 text-white rounded-lg text-xs font-bold hover:bg-rose-700"
                >
                  Gọi cấp cứu
                </button>
              </div>

              <div className="p-3.5 bg-white rounded-xl border border-rose-200 flex flex-col justify-between space-y-2 shadow-2xs">
                <div className="flex items-center gap-2 text-blue-700 font-bold text-xs">
                  <IconBuilding className="w-4 h-4 text-blue-600" />
                  <span>Trưởng Ca BQL</span>
                </div>
                <div className="font-mono text-lg font-bold text-slate-800">0903 888 999</div>
                <button
                  type="button"
                  onClick={() => alert('Đang kết nối Trưởng Ban Quản Lý Vũ Đức Thịnh')}
                  className="px-3 py-1.5 bg-blue-600 text-white rounded-lg text-xs font-bold hover:bg-blue-700"
                >
                  Báo cáo BQL
                </button>
              </div>

              <div className="p-3.5 bg-white rounded-xl border border-rose-200 flex flex-col justify-between space-y-2 shadow-2xs">
                <div className="flex items-center gap-2 text-purple-700 font-bold text-xs">
                  <IconLock className="w-4 h-4 text-purple-600" />
                  <span>Công An Phường</span>
                </div>
                <div className="font-mono text-lg font-bold text-slate-800">113 / 024 3837</div>
                <button
                  type="button"
                  onClick={() => alert('Đang kết nối Công an Phường Tây Mỗ')}
                  className="px-3 py-1.5 bg-purple-600 text-white rounded-lg text-xs font-bold hover:bg-purple-700"
                >
                  Báo Công an
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Modal Check-in */}
      {checkingCpId && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-5 space-y-4 shadow-xl">
            <h3 className="font-bold text-sm text-slate-900">Xác nhận có mặt tại điểm tuần tra {checkingCpId}</h3>
            <p className="text-xs text-slate-500">Ghi chú nhanh tình trạng khu vực:</p>
            <input
              value={cpNote}
              onChange={(e) => setCpNote(e.target.value)}
              placeholder="VD: Đèn sáng tốt, khóa an toàn, không có người lạ..."
              className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none focus:border-blue-500"
            />
            <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100">
              <button
                type="button"
                onClick={() => setCheckingCpId(null)}
                className="px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-xl"
              >
                Hủy
              </button>
              <button
                type="button"
                onClick={() => handleCheckin(checkingCpId)}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-xl shadow-2xs"
              >
                Xác nhận Check-in
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal Create Incident */}
      {showIncidentModal && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4">
          <form
            onSubmit={handleCreateIncident}
            className="bg-white rounded-2xl max-w-lg w-full p-5 space-y-3.5 shadow-xl max-h-[90vh] overflow-y-auto"
          >
            <h3 className="font-bold text-sm text-slate-900 pb-2 border-b border-slate-100">
              Lập biên bản sự việc an ninh mới
            </h3>

            <div className="space-y-1">
              <label className="text-xs font-bold text-slate-700">Tiêu đề sự việc:</label>
              <input
                required
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                placeholder="VD: Xe tải giao hàng đỗ chắn lối thoát hiểm..."
                className="w-full p-2 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none focus:border-blue-500"
              />
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1">
                <label className="text-xs font-bold text-slate-700">Vị trí xảy ra:</label>
                <input
                  required
                  value={newLocation}
                  onChange={(e) => setNewLocation(e.target.value)}
                  className="w-full p-2 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none focus:border-blue-500"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-bold text-slate-700">Mức độ ưu tiên:</label>
                <select
                  value={newSeverity}
                  onChange={(e) => setNewSeverity(e.target.value as any)}
                  className="w-full p-2 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none"
                >
                  <option value="P1">Khẩn cấp (P1)</option>
                  <option value="P2">Mức cao (P2)</option>
                  <option value="P3">Bình thường (P3)</option>
                </select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1">
                <label className="text-xs font-bold text-slate-700">Người liên quan (nếu có):</label>
                <input
                  value={personName}
                  onChange={(e) => setPersonName(e.target.value)}
                  placeholder="Họ tên người vi phạm/liên quan"
                  className="w-full p-2 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-bold text-slate-700">Biển số phương tiện:</label>
                <input
                  value={licensePlate}
                  onChange={(e) => setLicensePlate(e.target.value)}
                  placeholder="VD: 29A-123.45"
                  className="w-full p-2 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none font-mono"
                />
              </div>
            </div>

            <div className="space-y-1">
              <label className="text-xs font-bold text-slate-700">Biện pháp đã xử lý ban đầu:</label>
              <textarea
                rows={2}
                value={actionTaken}
                onChange={(e) => setActionTaken(e.target.value)}
                placeholder="VD: Đã nhắc nhở, yêu cầu di dời xe, lập biên bản ghi nhận..."
                className="w-full p-2 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none"
              />
            </div>

            <div className="flex items-center gap-2 pt-1">
              <input
                type="checkbox"
                id="areaIso"
                checked={areaIsolated}
                onChange={(e) => setAreaIsolated(e.target.checked)}
                className="rounded text-blue-600"
              />
              <label htmlFor="areaIso" className="text-xs text-slate-700 font-semibold">
                Đã căng dây phản quang / đặt biển cô lập khu vực hiện trường
              </label>
            </div>

            <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-100">
              <button
                type="button"
                onClick={() => setShowIncidentModal(false)}
                className="px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-xl"
              >
                Hủy bỏ
              </button>
              <button
                type="submit"
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-xl shadow-2xs"
              >
                Lưu biên bản sự việc
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
