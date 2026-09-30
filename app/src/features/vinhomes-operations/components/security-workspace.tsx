import { useState } from 'react';
import { OperationsTable } from './operations-table';
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
  const [selectedCheckpoint, setSelectedCheckpoint] = useState('');
  const [selectedReport, setSelectedReport] = useState('');
  const {
    securityCheckpoints,
    securityIncidents,
    securityHandovers,
    currentProfile,
    workOrders,
    transitionWorkOrderStatus,
    toggleSecurityCheckpoint,
    reportSecurityIncident,
    submitSecurityHandover,
    escalateSecurityIncident,
  } = useOperationsData();

  const securityWo = workOrders.find(
    (w) => (w.id === 'WO-2026-090' || w.task_id === 'TSK-2026-111') && w.status !== 'CANCELLED',
  );
  const checkedCheckpointsCount = securityCheckpoints.filter((cp) => cp.status === 'CHECKED').length;
  const allCheckpointsChecked = securityCheckpoints.length > 0 && checkedCheckpointsCount === securityCheckpoints.length;

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
  const [incidentPhotoUrl, setIncidentPhotoUrl] = useState<string | null>(null);

  // Handover modal
  const [showHandoverModal, setShowHandoverModal] = useState(false);
  const [handoverToName, setHandoverToName] = useState('Đỗ Tuấn Kiệt (Ca 2 - 14h-22h)');
  const [handoverShiftName, setHandoverShiftName] = useState<'CA_SANG' | 'CA_CHIEU' | 'CA_DEM'>('CA_CHIEU');
  const [handoverWalkieCount, setHandoverWalkieCount] = useState(4);
  const [handoverBatonCount, setHandoverBatonCount] = useState(4);
  const [handoverFlashlightCount, setHandoverFlashlightCount] = useState(4);
  const [handoverIssuesNote, setHandoverIssuesNote] = useState('');

  // Emergency Call Modal
  const [callingEmergency, setCallingEmergency] = useState<{ number: string; title: string } | null>(null);

  // Checkpoint modal
  const [checkingCpId, setCheckingCpId] = useState<string | null>(null);
  const [cpNote, setCpNote] = useState('');

  const handleCheckin = (cpId: string) => {
    toggleSecurityCheckpoint(cpId, cpNote || 'Tình trạng an ninh bình thường, không có dấu hiệu bất thường.');
    setCheckingCpId(null);
    setCpNote('');
    setSuccessMsg('Đã xác nhận có mặt thành công tại điểm tuần tra!');
    setTimeout(() => setSuccessMsg(null), 3000);
  };

  const handlePhotoSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (event) => {
      setIncidentPhotoUrl(event.target?.result as string);
    };
    reader.readAsDataURL(file);
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
      evidence_urls: incidentPhotoUrl
        ? [incidentPhotoUrl]
        : ['https://images.unsplash.com/photo-1541888946425-d0fbb18f15f7?w=800&auto=format&fit=crop&q=80'],
      status: 'INVESTIGATING',
    });

    setShowIncidentModal(false);
    setNewTitle('');
    setPersonName('');
    setLicensePlate('');
    setActionTaken('');
    setIncidentPhotoUrl(null);
    setSuccessMsg('Đã lập biên bản sự việc an ninh thành công!');
    setTimeout(() => setSuccessMsg(null), 3000);
  };

  const handleCreateHandover = (e: React.FormEvent) => {
    e.preventDefault();
    submitSecurityHandover({
      shift_name: handoverShiftName,
      date: new Date().toISOString().split('T')[0],
      handover_from_id: currentProfile.id,
      handover_from_name: currentProfile.name,
      handover_to_id: 'usr-sec-02',
      handover_to_name: handoverToName,
      equipment_status: {
        walkie_talkie_count: handoverWalkieCount,
        patrol_baton_count: handoverBatonCount,
        flashlight_count: handoverFlashlightCount,
        master_keys_intact: true,
      },
      open_security_issues: handoverIssuesNote
        ? [handoverIssuesNote]
        : ['Khu vực trật tự ổn định, không có sự cố tồn đọng'],
      notes: 'Bàn giao đầy đủ trang thiết bị và công cụ hỗ trợ',
      confirmed: true,
    });
    setShowHandoverModal(false);
    setSuccessMsg('Đã lập và ký xác nhận biên bản bàn giao ca trực thành công!');
    setTimeout(() => setSuccessMsg(null), 3000);
  };

  return (
    <div className="operations-worker-view operations-plain-list operations-work-orders space-y-5">
      {/* Title Header with Blue Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">

          <div>
            <h1 className="text-xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
              <IconShield className="w-5 h-5 text-blue-600" />
              <span>An ninh hiện trường</span>
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
      <div className="ops-scroll-tabs flex items-center gap-1.5 bg-white p-1 rounded-xl border border-slate-200 shadow-2xs">
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
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div>
              <h3 className="font-bold text-sm text-slate-900">Danh mục điểm kiểm soát theo tuyến</h3>
              <p className="text-xs text-slate-500">Nhân viên tuần tra xác nhận kiểm tra khi có mặt tại từng vị trí</p>
            </div>
            <span className="text-xs font-semibold text-emerald-700 bg-emerald-50 px-2.5 py-1 rounded-full border border-emerald-200">
              Đã kiểm tra {checkedCheckpointsCount}/{securityCheckpoints.length} điểm
            </span>
          </div>

          {/* Active Security Work Order Direct Status & Action */}
          {securityWo && (
            <div
              className={`p-4 rounded-2xl border flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-2xs ${
                securityWo.status === 'COMPLETED'
                  ? 'bg-emerald-50/70 border-emerald-200'
                  : allCheckpointsChecked
                    ? 'bg-blue-50/80 border-blue-200'
                    : 'bg-slate-50 border-slate-200'
              }`}
            >
              <div className="space-y-0.5">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs font-bold text-slate-700 bg-white px-2 py-0.5 rounded border border-slate-200">
                    {securityWo.id}
                  </span>
                  <span className="text-xs font-bold text-slate-900">
                    Phiếu tuần tra hiện trường (TSK-2026-111)
                  </span>
                  <span
                    className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                      securityWo.status === 'COMPLETED'
                        ? 'bg-emerald-100 text-emerald-800'
                        : 'bg-blue-100 text-blue-800'
                    }`}
                  >
                    {securityWo.status === 'COMPLETED' ? '✓ ĐÃ HOÀN THÀNH' : 'ĐANG THỰC HIỆN'}
                  </span>
                </div>
                <p className="text-xs text-slate-600">
                  {allCheckpointsChecked
                    ? '✓ Đã hoàn thành 100% trạm kiểm soát! Sẵn sàng báo hoàn tất ca tuần tra.'
                    : `Tiến độ tuyến tuần tra: Đã xác nhận có mặt ${checkedCheckpointsCount}/${securityCheckpoints.length} trạm bắt buộc.`}
                </p>
              </div>

              {securityWo.status !== 'COMPLETED' && (
                <button
                  type="button"
                  disabled={!allCheckpointsChecked}
                  onClick={() => {
                    try {
                      transitionWorkOrderStatus(securityWo.id, 'COMPLETED', {
                        note: 'Hoàn tất ca tuần tra an ninh trạm kỹ thuật B2, đã kiểm tra 100% các trạm chốt theo quy định.',
                      });
                      setSuccessMsg('Đã hoàn thành phiếu tuần tra an ninh (WO-2026-090)!');
                      setTimeout(() => setSuccessMsg(null), 3500);
                    } catch (err: any) {
                      alert(err.message);
                    }
                  }}
                  className={`px-4 py-2 rounded-xl text-xs font-bold transition-all shadow-2xs ${
                    allCheckpointsChecked
                      ? 'bg-emerald-600 hover:bg-emerald-700 text-white cursor-pointer'
                      : 'bg-slate-200 text-slate-400 cursor-not-allowed'
                  }`}
                >
                  {allCheckpointsChecked ? '✓ Hoàn thành phiếu tuần tra ' : 'Cần xác nhận có mặt đủ trạm để hoàn thành'}
                </button>
              )}
            </div>
          )}

          <div className="operations-plain-list" hidden={Boolean(selectedCheckpoint)}>
            <OperationsTable title="Điểm tuần tra" columns={['Thứ tự', 'Điểm kiểm tra', 'Vị trí', 'Trạng thái', 'Người kiểm tra']}
              rows={securityCheckpoints.map((point) => ({id: point.id, search: `${point.id} ${point.name} ${point.location}`, cells: [
                point.order, point.name, point.location, point.status === 'CHECKED' ? 'Đã kiểm tra' : 'Chờ kiểm tra', point.guard_name || 'Chưa có',
              ]}))} onSelect={setSelectedCheckpoint} />
          </div>
          {selectedCheckpoint && <button type="button" className="operations-back" onClick={() => setSelectedCheckpoint('')}>Quay lại danh sách điểm tuần tra</button>}
          <div className="space-y-4">
            {securityCheckpoints.filter((point) => point.id === selectedCheckpoint).map((cp) => (
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
                      : 'Chưa kiểm tra'}
                  </span>
                  {cp.status !== 'CHECKED' && (
                    <button
                      type="button"
                      onClick={() => setCheckingCpId(cp.id)}
                      className="px-3 py-1 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-bold transition-colors shadow-2xs"
                    >
                      Xác nhận kiểm tra
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
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5">
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

          <div className="operations-plain-list" hidden={Boolean(selectedReport)}>
            <OperationsTable title="Biên bản sự việc" columns={['Mã biên bản', 'Nội dung', 'Vị trí', 'Trạng thái']}
              rows={securityIncidents.map((report) => ({id: report.id, search: `${report.id} ${report.title} ${report.location}`, cells: [
                report.id, report.title, report.location, report.status === 'RESOLVED' ? 'Đã xử lý' : 'Đang xử lý',
              ]}))} onSelect={setSelectedReport} />
          </div>
          {selectedReport && <button type="button" className="operations-back" onClick={() => setSelectedReport('')}>Quay lại danh sách biên bản</button>}
          <div className="space-y-3">
            {securityIncidents.filter((report) => report.id === selectedReport).map((inc) => (
              <div
                key={inc.id}
                className="bg-white rounded-2xl border border-slate-200/80 p-3.5 sm:p-5 shadow-2xs space-y-3 hover:border-slate-300 transition-colors"
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

                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pt-2.5 border-t border-slate-100">
                  <p className="text-xs text-slate-700 leading-relaxed">
                    <strong>Biện pháp xử lý:</strong> {inc.action_taken}
                  </p>
                  <button
                    type="button"
                    onClick={() => {
                      const newOfficialInc = escalateSecurityIncident(inc.id);
                      setSuccessMsg(`Đã nâng cấp sự việc an ninh thành Sự Cố Chính Thức (${newOfficialInc.id}) trên hệ thống BQL!`);
                      setTimeout(() => setSuccessMsg(null), 4000);
                    }}
                    className="px-3 py-1.5 bg-rose-600 hover:bg-rose-700 text-white rounded-xl text-xs font-bold transition-colors flex items-center gap-1.5 shadow-2xs shrink-0 self-end sm:self-auto"
                  >
                    <IconAlertTriangle className="w-3.5 h-3.5" />
                    <span>Nâng cấp thành Sự Cố BQL</span>
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tab 3: Shift Handover */}
      {activeTab === 'HANDOVER' && (
        <div className="space-y-4">
          <div className="bg-white rounded-2xl border border-slate-200/80 p-3.5 sm:p-5 shadow-2xs space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-100">
              <div>
                <h3 className="font-bold text-sm text-slate-900">Biên bản bàn giao ca trực an ninh</h3>
                <p className="text-xs text-slate-500">Kiểm kê công cụ hỗ trợ và các sự vụ an ninh còn tồn đọng</p>
              </div>
              <div className="flex items-center gap-2">
                <span className="px-3 py-1 bg-emerald-100 text-emerald-800 text-xs font-bold rounded-full">
                  {securityHandovers.length} Biên bản ca
                </span>
                <button
                  type="button"
                  onClick={() => setShowHandoverModal(true)}
                  className="px-3.5 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-xl flex items-center gap-1 shadow-2xs transition-colors"
                >
                  <IconPlus className="w-4 h-4" />
                  <span>Lập biên bản bàn giao mới</span>
                </button>
              </div>
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
          <div className="p-3.5 sm:p-5 bg-rose-50 border border-rose-200 rounded-2xl space-y-3 text-rose-900">
            <div className="flex items-center gap-2">
              <IconAlertTriangle className="w-5 h-5 text-rose-600" />
              <h3 className="font-bold text-sm">Đường dây nóng Phản ứng Khẩn cấp (Liên hệ khẩn cấp)</h3>
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
                  onClick={() => setCallingEmergency({ number: '114', title: 'Cứu Hỏa & PCCC Cơ Sở Smart City' })}
                  className="px-3 py-1.5 bg-rose-600 text-white rounded-lg text-xs font-bold hover:bg-rose-700 transition-colors"
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
                  onClick={() => setCallingEmergency({ number: '115 / 024 3974', title: 'Cấp Cứu Y Tế Vinmec Smart City' })}
                  className="px-3 py-1.5 bg-rose-600 text-white rounded-lg text-xs font-bold hover:bg-rose-700 transition-colors"
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
                  onClick={() => setCallingEmergency({ number: '0903 888 999', title: 'Trưởng Ban Quản Lý (Hotline 24/7)' })}
                  className="px-3 py-1.5 bg-blue-600 text-white rounded-lg text-xs font-bold hover:bg-blue-700 transition-colors"
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
                  onClick={() => setCallingEmergency({ number: '113 / 024 3837', title: 'Công An Phường Tây Mỗ' })}
                  className="px-3 py-1.5 bg-purple-600 text-white rounded-lg text-xs font-bold hover:bg-purple-700 transition-colors"
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
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="checkin-title"
          className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-2 sm:p-4"
        >
          <div className="bg-white rounded-2xl max-w-md w-full p-5 space-y-4 shadow-xl">
            <h3 id="checkin-title" className="font-bold text-sm text-slate-900">Xác nhận có mặt tại điểm tuần tra {checkingCpId}</h3>
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
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="sec-incident-title"
          className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-2 sm:p-4"
        >
          <form
            onSubmit={handleCreateIncident}
            className="bg-white rounded-2xl max-w-lg w-full p-5 space-y-3.5 shadow-xl max-h-[90vh] overflow-y-auto"
          >
            <h3 id="sec-incident-title" className="font-bold text-sm text-slate-900 pb-2 border-b border-slate-100">
              Lập biên bản sự việc an ninh mới
            </h3>

            <div className="space-y-1">
              <label htmlFor="sec-incident-name" className="text-xs font-bold text-slate-700 block">Tiêu đề sự việc:</label>
              <input
                id="sec-incident-name"
                required
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                placeholder="VD: Xe tải giao hàng đỗ chắn lối thoát hiểm..."
                className="w-full p-2 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none focus:border-blue-500"
              />
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1">
                <label htmlFor="sec-incident-loc" className="text-xs font-bold text-slate-700 block">Vị trí xảy ra:</label>
                <input
                  id="sec-incident-loc"
                  required
                  value={newLocation}
                  onChange={(e) => setNewLocation(e.target.value)}
                  className="w-full p-2 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none focus:border-blue-500"
                />
              </div>

              <div className="space-y-1">
                <label htmlFor="sec-incident-sev" className="text-xs font-bold text-slate-700 block">Mức độ ưu tiên:</label>
                <select
                  id="sec-incident-sev"
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
                <label htmlFor="sec-person" className="text-xs font-bold text-slate-700 block">Người liên quan (nếu có):</label>
                <input
                  id="sec-person"
                  value={personName}
                  onChange={(e) => setPersonName(e.target.value)}
                  placeholder="Họ tên người vi phạm/liên quan"
                  className="w-full p-2 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none"
                />
              </div>

              <div className="space-y-1">
                <label htmlFor="sec-plate" className="text-xs font-bold text-slate-700 block">Biển số phương tiện:</label>
                <input
                  id="sec-plate"
                  value={licensePlate}
                  onChange={(e) => setLicensePlate(e.target.value)}
                  placeholder="VD: 29A-123.45"
                  className="w-full p-2 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none font-mono"
                />
              </div>
            </div>

            <div className="space-y-1">
              <label htmlFor="sec-action" className="text-xs font-bold text-slate-700 block">Biện pháp đã xử lý ban đầu:</label>
              <textarea
                id="sec-action"
                rows={2}
                value={actionTaken}
                onChange={(e) => setActionTaken(e.target.value)}
                placeholder="VD: Đã nhắc nhở, yêu cầu di dời xe, lập biên bản ghi nhận..."
                className="w-full p-2 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none"
              />
            </div>

            <div className="space-y-1">
              <label htmlFor="sec-incident-photo" className="text-xs font-bold text-slate-700 block">
                Chụp ảnh hiện trường / Biên bản giấy:
              </label>
              <input
                id="sec-incident-photo"
                type="file"
                accept="image/*"
                capture="environment"
                onChange={handlePhotoSelect}
                className="w-full text-xs text-slate-500 file:mr-2 file:py-1.5 file:px-3 file:rounded-xl file:border-0 file:text-xs file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100 cursor-pointer"
              />
              {incidentPhotoUrl && (
                <div className="mt-2 relative w-28 h-20 rounded-lg overflow-hidden border border-slate-200 shadow-2xs">
                  <img src={incidentPhotoUrl} alt="Ảnh sự cố" className="w-full h-full object-cover" />
                  <span className="absolute bottom-0 inset-x-0 bg-black/60 text-white text-[9px] text-center py-0.5">
                    Đã đính kèm ảnh
                  </span>
                </div>
              )}
            </div>

            <div className="flex items-center gap-2 pt-1">
              <input
                type="checkbox"
                id="areaIso"
                checked={areaIsolated}
                onChange={(e) => setAreaIsolated(e.target.checked)}
                className="rounded text-blue-600"
              />
              <label htmlFor="areaIso" className="text-xs text-slate-700 font-semibold cursor-pointer">
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

      {/* Modal Shift Handover */}
      {showHandoverModal && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="handover-modal-title"
          className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-2 sm:p-4"
        >
          <form
            onSubmit={handleCreateHandover}
            className="bg-white rounded-2xl max-w-lg w-full p-5 space-y-4 shadow-xl max-h-[90vh] overflow-y-auto"
          >
            <h3 id="handover-modal-title" className="font-bold text-sm text-slate-900 pb-2 border-b border-slate-100">
              Lập Biên Bản Bàn Giao Ca Trực An Ninh
            </h3>

            <div className="grid grid-cols-2 gap-3 text-xs">
              <div className="space-y-1">
                <label className="text-slate-500 font-medium block">Người bàn giao (Hiện tại):</label>
                <div className="p-2 bg-slate-100 rounded-xl font-bold text-slate-800">
                  {currentProfile.name}
                </div>
              </div>
              <div className="space-y-1">
                <label htmlFor="handover-to" className="text-slate-500 font-medium block">Người nhận ca:</label>
                <input
                  id="handover-to"
                  required
                  value={handoverToName}
                  onChange={(e) => setHandoverToName(e.target.value)}
                  className="w-full p-2 bg-slate-50 border border-slate-200 rounded-xl font-bold text-slate-800 text-xs focus:outline-none focus:border-blue-500"
                />
              </div>
            </div>

            <div className="space-y-1 text-xs">
              <label htmlFor="shift-name" className="text-slate-500 font-medium block">Tên ca bàn giao:</label>
              <select
                id="shift-name"
                value={handoverShiftName}
                onChange={(e) => setHandoverShiftName(e.target.value as 'CA_SANG' | 'CA_CHIEU' | 'CA_DEM')}
                className="w-full p-2 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none focus:border-blue-500"
              >
                <option value="CA_SANG">Ca Sáng (06:00 - 14:00)</option>
                <option value="CA_CHIEU">Ca Chiều (14:00 - 22:00)</option>
                <option value="CA_DEM">Ca Đêm (22:00 - 06:00)</option>
              </select>
            </div>

            <div className="space-y-2 text-xs">
              <label className="font-bold text-slate-800 block">Kiểm kê công cụ hỗ trợ giao ca:</label>
              <div className="grid grid-cols-3 gap-2">
                <div className="space-y-1">
                  <label htmlFor="walkie-count" className="text-[11px] text-slate-500 block">Bộ đàm (chiếc):</label>
                  <input
                    id="walkie-count"
                    type="number"
                    min="0"
                    value={handoverWalkieCount}
                    onChange={(e) => setHandoverWalkieCount(Number(e.target.value))}
                    className="w-full p-2 bg-slate-50 border border-slate-200 rounded-xl text-xs"
                  />
                </div>
                <div className="space-y-1">
                  <label htmlFor="baton-count" className="text-[11px] text-slate-500 block">Dùi cui (chiếc):</label>
                  <input
                    id="baton-count"
                    type="number"
                    min="0"
                    value={handoverBatonCount}
                    onChange={(e) => setHandoverBatonCount(Number(e.target.value))}
                    className="w-full p-2 bg-slate-50 border border-slate-200 rounded-xl text-xs"
                  />
                </div>
                <div className="space-y-1">
                  <label htmlFor="flashlight-count" className="text-[11px] text-slate-500 block">Đèn pin (chiếc):</label>
                  <input
                    id="flashlight-count"
                    type="number"
                    min="0"
                    value={handoverFlashlightCount}
                    onChange={(e) => setHandoverFlashlightCount(Number(e.target.value))}
                    className="w-full p-2 bg-slate-50 border border-slate-200 rounded-xl text-xs"
                  />
                </div>
              </div>
            </div>

            <div className="space-y-1 text-xs">
              <label htmlFor="handover-issues" className="font-bold text-slate-800 block">
                Sự vụ cần ca sau tiếp tục theo dõi:
              </label>
              <textarea
                id="handover-issues"
                rows={2}
                value={handoverIssuesNote}
                onChange={(e) => setHandoverIssuesNote(e.target.value)}
                placeholder="VD: Xe máy đỗ sai vị trí tại sảnh S2.01 đang theo dõi..."
                className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none"
              />
            </div>

            <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-100">
              <button
                type="button"
                onClick={() => setShowHandoverModal(false)}
                className="px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-xl"
              >
                Hủy bỏ
              </button>
              <button
                type="submit"
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-xl shadow-2xs"
              >
                Ký xác nhận bàn giao
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Emergency Dialing Simulator Modal */}
      {callingEmergency && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 bg-slate-900/70 backdrop-blur-xs flex items-center justify-center p-2 sm:p-4 font-sans"
        >
          <div className="bg-white rounded-2xl max-w-sm w-full p-6 text-center space-y-4 shadow-2xl border border-rose-200">
            <div className="w-16 h-16 rounded-full bg-rose-100 text-rose-600 mx-auto flex items-center justify-center animate-pulse">
              <IconPhoneCall className="w-8 h-8" />
            </div>

            <div>
              <h3 className="font-extrabold text-base text-slate-900">{callingEmergency.title}</h3>
              <p className="text-xl font-mono font-bold text-rose-600 mt-1">{callingEmergency.number}</p>
              <p className="text-xs text-slate-500 mt-1">Đang thiết lập kênh thoại khẩn cấp hiện trường...</p>
            </div>

            <div className="pt-2 flex justify-center gap-2">
              <button
                type="button"
                onClick={() => {
                  window.open(`tel:${callingEmergency.number.split('/')[0].trim()}`);
                  setCallingEmergency(null);
                }}
                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold rounded-xl shadow-2xs flex items-center gap-1.5"
              >
                <IconPhoneCall className="w-4 h-4" />
                <span>Gọi trên thiết bị</span>
              </button>
              <button
                type="button"
                onClick={() => setCallingEmergency(null)}
                className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-xl"
              >
                Đóng
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
