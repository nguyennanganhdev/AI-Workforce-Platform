import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Package, Plus, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';

import { packsApi } from '@/api/packs';
import type { PackView } from '@/api/packs';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Spinner } from '@/components/ui/spinner';

/** The pack library: each pack brings its MCP, documents and a ready team of agents. */
export function PacksPage() {
	const queryClient = useQueryClient();
	const packs = useQuery({ queryKey: ['packs'], queryFn: packsApi.list, retry: false });
	const [busy, setBusy] = useState<string | null>(null);

	const change = async (pack: PackView, install: boolean) => {
		setBusy(pack.id);
		try {
			const result = install ? await packsApi.install(pack.id) : await packsApi.remove(pack.id);
			await queryClient.invalidateQueries({ queryKey: ['packs'] });
			await queryClient.invalidateQueries({ queryKey: ['studio'] });
			if (!install) toast.success(`Đã gỡ gói ${pack.name}.`);
			else toast.success(`Đã thêm gói ${pack.name} với ${result.agents.length} agent. Hỏi Leader để bắt đầu.`);
		} catch (error) {
			toast.error(error instanceof Error ? error.message : 'Chưa thay đổi được gói.');
		} finally {
			setBusy(null);
		}
	};

	return (
		<div className="mx-auto flex w-full max-w-5xl flex-col gap-4 p-4 md:p-6">
			<header className="space-y-1">
				<h1 className="text-xl font-semibold">Thư viện gói</h1>
				<p className="text-sm text-muted-foreground">
					Mỗi gói mang theo MCP, tài liệu và một đội agent đã kiểm thử. Thêm gói rồi hỏi Leader; đội của gói sẽ tham gia.
				</p>
			</header>
			{packs.isPending ? (
				<div className="flex justify-center py-10"><Spinner /></div>
			) : packs.isError ? (
				<p role="alert" className="text-sm">Chưa tải được thư viện gói. <Button variant="link" onClick={() => void packs.refetch()}>Thử lại</Button></p>
			) : packs.data.length === 0 ? (
				<p className="py-10 text-center text-sm text-muted-foreground">Chưa có gói nào được đăng.</p>
			) : (
				<ul className="grid gap-3 sm:grid-cols-2">
					{packs.data.map((pack) => (
						<li key={pack.id} className="flex flex-col gap-3 rounded-2xl border bg-card p-4">
							<div className="flex items-start gap-3">
								<span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-muted"><Package className="size-5" /></span>
								<div className="min-w-0 flex-1 space-y-1">
									<div className="flex flex-wrap items-center gap-2">
										<h2 className="font-medium">{pack.name}</h2>
										{pack.installed && <Badge variant="secondary">Đã thêm</Badge>}
									</div>
									<p className="text-sm text-muted-foreground">{pack.description || 'Không có mô tả.'}</p>
									<p className="text-xs text-muted-foreground">{pack.template_agent_ids.length} agent mẫu · {pack.catalog_ids.length} tài nguyên</p>
								</div>
							</div>
							<div className="flex flex-wrap gap-2">
								{pack.installed ? (
									<Button variant="outline" size="sm" disabled={busy !== null} onClick={() => void change(pack, false)}>
										{busy === pack.id ? <Spinner className="size-4" /> : <Trash2 />} Gỡ gói
									</Button>
								) : (
									<Button size="sm" disabled={busy !== null} onClick={() => void change(pack, true)}>
										{busy === pack.id ? <Spinner className="size-4" /> : <Plus />} Thêm gói
									</Button>
								)}
							</div>
						</li>
					))}
				</ul>
			)}
		</div>
	);
}
