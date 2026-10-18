import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';

import { packsApi } from '@/api/packs';
import type { PackView } from '@/api/packs';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';

const split = (value: string) => [...new Set(value.split(/[\n,]+/).map((item) => item.trim()).filter(Boolean))];
const empty = { id: '', name: '', description: '', catalog: '', templates: '', link: '', active: true, revision: 0 };

/** Packs: catalog resources granted to a pack group plus the admin's published sample agents. */
export function PackEditor({ perform, busy }: { perform: (action: () => Promise<unknown>, message: string) => Promise<void>; busy: boolean }) {
	const packs = useQuery({ queryKey: ['vin-admin', 'packs'], queryFn: packsApi.adminList, retry: false });
	const [form, setForm] = useState(empty);
	const set = (key: keyof typeof empty) => (event: { target: { value: string } }) => setForm((value) => ({ ...value, [key]: event.target.value }));
	const load = (pack: PackView) => setForm({ id: pack.id, name: pack.name, description: pack.description,
		catalog: pack.catalog_ids.join('\n'), templates: pack.template_agent_ids.join('\n'), link: pack.link_provider_id ?? '',
		active: pack.active, revision: pack.revision });
	const save = () => perform(async () => {
		const result = await packsApi.adminSave(form.id.trim(), { name: form.name.trim(), description: form.description.trim(),
			catalog_ids: split(form.catalog), template_agent_ids: split(form.templates), link_provider_id: form.link.trim() || null,
			active: form.active }, form.revision);
		setForm((value) => ({ ...value, revision: result.revision }));
		await packs.refetch();
	}, 'Đã lưu gói. Tài nguyên của gói được cấp cho nhóm pack:' + form.id.trim() + '.');
	return <div className="max-w-3xl space-y-6">
		<section className="space-y-2">
			<h2 className="font-semibold">Gói trong thư viện</h2>
			<p className="text-sm text-muted-foreground">Người dùng bấm "Thêm gói" để vào nhóm của gói và nhận bản sao các agent mẫu đã phát hành của bạn.</p>
			{packs.isError && <p role="alert" className="text-sm">Chưa tải được danh sách gói.</p>}
			{packs.data?.map((pack) => <div key={pack.id} className="flex flex-wrap items-center justify-between gap-2 border-b py-2 text-sm">
				<span>{pack.name} · {pack.id} · v{pack.revision} · {pack.active ? 'Đang mở' : 'Đã ẩn'} · {pack.template_agent_ids.length} agent mẫu</span>
				<Button size="sm" variant="outline" onClick={() => load(pack)}>Sửa</Button>
			</div>)}
		</section>
		<form className="space-y-3" onSubmit={(event) => { event.preventDefault(); void save(); }}>
			<h2 className="font-semibold">{form.revision ? `Sửa gói ${form.id}` : 'Tạo gói mới'}</h2>
			<div className="grid gap-2 text-sm"><Label htmlFor="pack-id">Mã gói (chữ thường, số, gạch ngang)</Label><Input id="pack-id" required pattern="[a-z0-9][a-z0-9-]{1,62}" disabled={form.revision > 0} value={form.id} onChange={set('id')} /></div>
			<div className="grid gap-2 text-sm"><Label htmlFor="pack-name">Tên gói</Label><Input id="pack-name" required value={form.name} onChange={set('name')} /></div>
			<div className="grid gap-2 text-sm"><Label htmlFor="pack-description">Mô tả</Label><Textarea id="pack-description" value={form.description} onChange={set('description')} /></div>
			<div className="grid gap-2 text-sm"><Label htmlFor="pack-catalog">Catalog ID của MCP/KB/skill (mỗi dòng một mục)</Label><Textarea id="pack-catalog" value={form.catalog} onChange={set('catalog')} /></div>
			<div className="grid gap-2 text-sm"><Label htmlFor="pack-templates">ID agent mẫu đã phát hành của bạn (mỗi dòng một agent)</Label><Textarea id="pack-templates" value={form.templates} onChange={set('templates')} /></div>
			<div className="grid gap-2 text-sm"><Label htmlFor="pack-link">Nhà cung cấp cần liên kết tài khoản (ví dụ vinhomes; để trống nếu không cần)</Label><Input id="pack-link" value={form.link} onChange={set('link')} /></div>
			<label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={form.active} onChange={(event) => setForm((value) => ({ ...value, active: event.target.checked }))} />Hiện trong thư viện</label>
			<div className="flex gap-2"><Button type="submit" disabled={busy || !form.id.trim() || !form.name.trim()}>Lưu gói</Button>
				<Button type="button" variant="ghost" onClick={() => setForm(empty)}>Gói mới</Button></div>
		</form>
	</div>;
}
