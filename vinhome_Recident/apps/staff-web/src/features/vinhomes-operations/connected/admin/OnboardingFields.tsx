import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { accountOnboardingQuery, onboardingOptionsQuery, revokeResidencyMutation, type OnboardingInput } from "@/lib/admin/queries";
import { AdminConfirm, AdminSelect, AdminState } from "./AdminUI";

type Props = {
  userId?: string; role: string; units: {id: string; name: string}[]; value: OnboardingInput;
  onChange: (value: OnboardingInput) => void; onReady: (ready: boolean) => void; busy: boolean;
};

export function OnboardingFields({userId = "", role, units, onChange, onReady, busy}: Props) {
  const profile = useQuery(accountOnboardingQuery(userId));
  const [search, setSearch] = useState("");
  const options = useQuery(onboardingOptionsQuery(search));
  const revoke = useMutation(revokeResidencyMutation(useQueryClient()));
  const [revoking, setRevoking] = useState("");
  const loaded = useRef(false);
  const [link, setLink] = useState(!userId);
  const [apartment, setApartment] = useState("");
  const [relation, setRelation] = useState<"owner" | "tenant" | "household">("household");
  const [managementUnit, setManagementUnit] = useState("");
  const [employee, setEmployee] = useState("");
  const [categories, setCategories] = useState<string[]>([]);
  const [capacity, setCapacity] = useState(1);
  const [availability, setAvailability] = useState<"available" | "busy" | "offline" | "on_leave">("available");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  useEffect(() => {
    if (!profile.data || loaded.current) return;
    loaded.current = true;
    setLink(!profile.data.residencies.some(r => r.verification_status === "verified"));
    const staff = profile.data.staff_profile;
    if (staff) {
      setManagementUnit(staff.management_unit_id); setEmployee(staff.employee_code);
      setCategories(staff.category_ids); setCapacity(staff.max_concurrent_jobs); setAvailability(staff.availability);
    }
  }, [profile.data]);
  const intervalValid = !!start && !!end && Number.isFinite(Date.parse(start)) && Date.parse(end) > Date.parse(start);
  const profileHasShifts = (profile.data?.staff_profile?.shifts.length ?? 0) > 0;
  const ready = (role !== "customer" && role !== "staff") || (!options.isPending && !options.error && (!userId || (!profile.isPending && !profile.error)) &&
    (role !== "customer" || !link || !!apartment) &&
    (role !== "staff" || (!!managementUnit && !!employee.trim() && categories.length > 0 && capacity >= 1 && capacity <= 20 &&
      ((start || end) ? intervalValid : profileHasShifts))));
  const body = useMemo<OnboardingInput>(() => role === "customer" && link && apartment ? {residency: {unit_id: apartment, relation}} :
    role === "staff" ? {staff_profile: {management_unit_id: managementUnit, employee_code: employee.trim(), category_ids: categories,
      max_concurrent_jobs: capacity, availability, shifts: intervalValid ? [{starts_at: new Date(start).toISOString(), ends_at: new Date(end).toISOString()}] : []}} : {},
    [role, link, apartment, relation, managementUnit, employee, categories, capacity, availability, intervalValid, start, end]);
  useEffect(() => {onChange(body);}, [body, onChange]);
  useEffect(() => {onReady(ready);}, [ready, onReady]);
  if (role !== "customer" && role !== "staff") return null;
  if (options.error || (userId && profile.error)) return <AdminState error={options.error || profile.error} onRetry={() => {void options.refetch(); if (userId) void profile.refetch();}} />;
  return <section className="ops-admin-form" aria-label="Hoàn tất hồ sơ tài khoản">
    <h3>{role === "customer" ? "Căn hộ và xác minh cư trú" : "Hồ sơ nhân viên"}</h3>
    {(options.isPending || (userId && profile.isPending)) && <p role="status">Đang tải thông tin hồ sơ…</p>}
    {role === "customer" ? <>
      {profile.data?.residencies.map(r => <div key={r.id} className="ops-admin-actions">
        <span>Tòa {r.building_code || "—"}, căn {r.code} · {r.verification_status === "verified" ? "Đã xác minh" : "Chưa xác minh"}</span>
        <Button type="button" variant="outline" disabled={busy || revoke.isPending} onClick={() => setRevoking(r.id)}>Thu hồi liên kết</Button>
      </div>)}
      <label className="ops-admin-check-field"><input type="checkbox" checked={link} disabled={busy} onChange={e => setLink(e.target.checked)} /> Liên kết và xác minh thêm căn hộ khi lưu</label>
      {link ? <>
        <label>Tìm căn hộ theo tòa hoặc số căn<Input aria-label="Tìm căn hộ" value={search} maxLength={100} disabled={busy} onChange={e => setSearch(e.target.value)} /></label>
        <label>Căn hộ cần xác minh<AdminSelect label="Căn hộ cần xác minh" value={apartment} disabled={busy || options.isPending} onChange={setApartment}
          options={[{value: "", label: "Chọn đúng căn hộ"}, ...(options.data?.units || []).map(u => ({value: u.id, label: `${u.building_code || u.building_name || "Khu nhà"} · Căn ${u.code}`}))]} /></label>
        <small>Tối đa 100 kết quả; nhập tòa/số căn để tìm chính xác. Việc chọn căn là xác nhận của quản trị viên.</small>
        <label>Quan hệ cư trú<AdminSelect label="Quan hệ cư trú" value={relation} disabled={busy} onChange={v => setRelation(v as typeof relation)}
          options={[{value: "owner", label: "Chủ hộ"}, {value: "tenant", label: "Người thuê"}, {value: "household", label: "Thành viên trong hộ"}]} /></label>
      </> : <p className="ops-admin-muted">Lưu tài khoản không tự cấp căn hộ. Cư dân chưa có căn hộ đã xác minh vẫn ở màn chờ xác minh.</p>}
      {revoking && <AdminConfirm title="Thu hồi liên kết căn hộ?" consequence="Giữ lịch sử cư trú và kết thúc các phiên đăng nhập. Người dùng mất quyền căn hộ này." confirm="Thu hồi" busy={revoke.isPending} onCancel={() => setRevoking("")}
        onConfirm={async () => {try {await revoke.mutateAsync({user: userId, id: revoking}); setRevoking("");} catch {}}} />}
      {revoke.error && <p className="ops-admin-error" role="alert">{revoke.error.message}</p>}
    </> : <>
      <label>Đơn vị quản lý<AdminSelect label="Đơn vị của nhân viên" value={managementUnit} disabled={busy} onChange={setManagementUnit}
        options={[{value: "", label: "Chọn đơn vị quản lý"}, ...units.map(u => ({value: u.id, label: u.name}))]} /></label>
      <label>Mã nhân viên<Input aria-label="Mã nhân viên" value={employee} maxLength={80} disabled={busy} onChange={e => setEmployee(e.target.value)} /></label>
      <fieldset><legend>Chuyên môn</legend>{options.data?.categories.map(c => <label key={c.id} className="ops-admin-check-field"><input type="checkbox" checked={categories.includes(c.id)} disabled={busy}
        onChange={e => setCategories(e.target.checked ? [...categories, c.id] : categories.filter(id => id !== c.id))} /> {c.name}</label>)}</fieldset>
      <label>Số việc đồng thời tối đa<Input aria-label="Số việc đồng thời tối đa" type="number" min={1} max={20} value={capacity} disabled={busy} onChange={e => setCapacity(Number(e.target.value))} /></label>
      <AdminSelect label="Trạng thái nhận việc" value={availability} disabled={busy} onChange={v => setAvailability(v as typeof availability)}
        options={[{value: "available", label: "Sẵn sàng"}, {value: "busy", label: "Đang bận"}, {value: "offline", label: "Ngoại tuyến"}, {value: "on_leave", label: "Nghỉ phép"}]} />
      {profileHasShifts && <small>Đã có {profile.data?.staff_profile?.shifts.length} ca còn hiệu lực. Nhập giờ dưới đây để thêm ca; các ca đã có được giữ nguyên.</small>}
      <label>Ca làm: bắt đầu<Input aria-label="Ca làm bắt đầu" type="datetime-local" value={start} disabled={busy} onChange={e => setStart(e.target.value)} /></label>
      <label>Ca làm: kết thúc<Input aria-label="Ca làm kết thúc" type="datetime-local" value={end} disabled={busy} onChange={e => setEnd(e.target.value)} /></label>
      <small>Giờ theo múi giờ máy bạn. Nhân viên chỉ được giao việc khi đúng chuyên môn, đang trong ca và còn năng lực.</small>
      {(start || end) && !intervalValid && <p role="alert" className="ops-admin-error">Chọn đủ giờ bắt đầu và kết thúc; giờ kết thúc phải sau giờ bắt đầu.</p>}
    </>}
  </section>;
}
