import { useCallback, useEffect, useState } from 'react';
import { toast } from 'sonner';

import { client } from '@/api/client';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';

export function CreateReferenceBase({ onCreated }: { onCreated: (id: string) => Promise<void> }) {
	const [open, setOpen] = useState(false);
	const [busy, setBusy] = useState(false);
	return <div>
		<Button variant="outline" size="sm" onClick={() => setOpen(!open)}>Kho văn bản không dùng model</Button>
		{open && <form className="mt-3 space-y-2" onSubmit={async event => {
			event.preventDefault(); const form = event.currentTarget; setBusy(true);
			try { const name = String(new FormData(form).get('name')); const result = await client.post<{ knowledge_base_id: string }>('/knowledge_bases/lexical', { name }); await onCreated(result.knowledge_base_id); setOpen(false); }
			catch (error) { toast.error(error instanceof Error ? error.message : 'Không tạo được kho'); }
			finally { setBusy(false); }
		}}>
			<label className="block text-sm">Tên kho<Input name="name" required maxLength={100} /></label>
			<p className="text-xs text-muted-foreground">Tìm theo nội dung văn bản. Tài liệu mới cần được duyệt trước khi agent sử dụng.</p>
			<Button size="sm" disabled={busy}>Tạo kho</Button>
		</form>}
	</div>;
}

interface ReferenceDocument { id: string; filename: string; review_status: string; source_ref: string; version: string; }

export function ReferenceDocuments({ knowledgeBaseId }: { knowledgeBaseId: string }) {
	const [documents, setDocuments] = useState<ReferenceDocument[]>([]);
	const [busy, setBusy] = useState(false);
	const [error, setError] = useState('');
	const load = useCallback(async () => {
		try { const result = await client.get<{ documents: ReferenceDocument[] }>(`/knowledge_bases/${knowledgeBaseId}/documents`, { page_size: '200' }); setDocuments(result.documents); setError(''); }
		catch (e) { setError(e instanceof Error ? e.message : 'Không tải được tài liệu'); }
	}, [knowledgeBaseId]);
	useEffect(() => { void load(); }, [load]);
	const review = async (id: string, status: 'approved' | 'retired') => {
		setBusy(true);
		try { await client.post(`/knowledge_bases/${knowledgeBaseId}/references/${id}/review`, { status }); await load(); }
		catch (e) { toast.error(e instanceof Error ? e.message : 'Không cập nhật được tài liệu'); }
		finally { setBusy(false); }
	};
	return <section className="space-y-4">
		<h3 className="font-medium">Tài liệu tham chiếu</h3>
		<p className="text-sm text-muted-foreground">Chỉ duyệt nội dung và nguồn bạn đã kiểm tra. Tài liệu đang chờ duyệt hoặc đã ngừng dùng không xuất hiện trong kết quả của agent.</p>
		{error && <p role="alert" className="text-sm text-destructive">{error}</p>}
		<ul className="divide-y rounded-lg border">{documents.map(doc => <li key={doc.id} className="space-y-2 p-3">
			<p className="text-sm font-medium">{doc.filename} · {doc.review_status === 'candidate' ? 'Chờ duyệt' : doc.review_status === 'retired' ? 'Đã ngừng dùng' : 'Đã duyệt'}</p>
			<p className="break-all text-xs text-muted-foreground">Nguồn: {doc.source_ref} · Bản {doc.version?.slice(0, 12)}</p>
			<div className="flex gap-2">{doc.review_status !== 'approved' && <Button size="sm" variant="outline" disabled={busy} onClick={() => void review(doc.id, 'approved')}>Duyệt sử dụng</Button>}{doc.review_status === 'approved' && <Button size="sm" variant="outline" disabled={busy} onClick={() => void review(doc.id, 'retired')}>Ngừng dùng</Button>}</div>
		</li>)}</ul>
		<details className="rounded-lg border p-3"><summary className="cursor-pointer text-sm font-medium">Thêm tài liệu mới</summary>
			<form className="mt-3 space-y-3" onSubmit={async event => {
				event.preventDefault(); const form = event.currentTarget; const data = new FormData(form); setBusy(true);
				try { await client.post(`/knowledge_bases/${knowledgeBaseId}/references`, { filename: data.get('filename'), source_ref: data.get('source_ref'), text: data.get('text'), effective_from: data.get('effective_from') || null, effective_until: data.get('effective_until') || null }); form.reset(); await load(); }
				catch (e) { toast.error(e instanceof Error ? e.message : 'Không thêm được tài liệu'); }
				finally { setBusy(false); }
			}}>
				<label className="block text-sm">Tên tài liệu<Input name="filename" required maxLength={200} /></label>
				<label className="block text-sm">Nguồn / mã tài liệu<Input name="source_ref" required maxLength={1000} /></label>
				<label className="block text-sm">Nội dung<Textarea name="text" required minLength={20} maxLength={100000} rows={10} /></label>
				<div className="grid gap-3 sm:grid-cols-2"><label className="text-sm">Hiệu lực từ<Input name="effective_from" type="date" /></label><label className="text-sm">Hết hiệu lực<Input name="effective_until" type="date" /></label></div>
				<Button size="sm" disabled={busy}>Lưu bản chờ duyệt</Button>
			</form>
		</details>
	</section>;
}
