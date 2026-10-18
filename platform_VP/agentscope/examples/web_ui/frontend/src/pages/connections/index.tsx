import { useQuery } from '@tanstack/react-query';
import { useEffect, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';

import { personalApi } from '@/api/personal';
import { Button } from '@/components/ui/button';
import { useCurrentUser } from '@/context/CurrentUserContext';

const statusLabels: Record<string, string> = { active: 'Đã liên kết', revoked: 'Đã thu hồi', revoke_pending: 'Đang đồng bộ thu hồi' };

export function ConnectionsPage() {
	const user = useCurrentUser()!;
	const location = useLocation();
	const links = useQuery({ queryKey: ['domain-links', user.tenant_id, user.id], queryFn: personalApi.links, retry: false });
	const [busy, setBusy] = useState(false);
	const busyRef = useRef(false);
	const [error, setError] = useState('');
	const [confirmation, setConfirmation] = useState<string | null>(null);
	const [callback] = useState(() => {
		if (location.pathname !== '/connections/callback/vinhomes') return null;
		const params = new URLSearchParams(location.search);
		return { state: params.get('state') ?? '', code: params.get('code') ?? '', failed: params.has('error') };
	});
	const [callbackHandled, setCallbackHandled] = useState(false);
	const storageKey = (state: string) => `vin-link:${user.tenant_id}:${user.id}:vinhomes:${state}`;

	useEffect(() => {
		if (callback) window.history.replaceState(window.history.state, '', window.location.pathname);
	}, [callback]);

	const act = async (work: () => Promise<void>) => {
		if (busyRef.current) return;
		busyRef.current = true;
		setBusy(true);
		setError('');
		try { await work(); } catch { setError('Chưa hoàn tất thao tác. Hãy cập nhật trạng thái trước khi thử lại; bạn có thể bắt đầu liên kết mới nếu phiên xác nhận đã hết hạn.'); }
		finally { busyRef.current = false; setBusy(false); }
	};

	return (
		<main className="mx-auto h-full max-w-4xl space-y-8 overflow-y-auto p-5 sm:p-8">
			<header className="space-y-2"><h1 className="text-2xl font-semibold tracking-tight">Kết nối</h1><p className="text-sm text-muted-foreground">Liên kết danh tính tại Vinhomes để sử dụng dịch vụ được cấp cho bạn.</p></header>
			{callback && !callbackHandled && <section className="space-y-3 rounded-xl border bg-background p-5" aria-labelledby="link-callback">
				<h2 id="link-callback" className="font-semibold">Xác nhận liên kết Vinhomes</h2>
				<p className="text-sm text-muted-foreground">{callback.failed ? 'Bạn chưa cho phép liên kết. Có thể bắt đầu lại khi sẵn sàng.' : 'Hoàn tất liên kết bằng phiên xác nhận vừa trở về từ Vinhomes.'}</p>
				{!callback.failed && <Button className="min-h-11" disabled={busy || !callback.code || !callback.state} onClick={() => void act(async () => {
					const transactionId = sessionStorage.getItem(storageKey(callback.state));
					if (!transactionId) throw new Error('LINK_TRANSACTION_INVALID');
					// Consume locally before the request: a lost response must be reconciled
					// through the link list, never by replaying an authorization code.
					sessionStorage.removeItem(storageKey(callback.state));
					setCallbackHandled(true);
					try { await personalApi.completeLink('vinhomes', { transaction_id: transactionId, state: callback.state, code: callback.code }); }
					finally { await links.refetch(); }
				})}>Hoàn tất liên kết</Button>}
			</section>}
			{error && <p role="alert" className="rounded-lg border border-destructive p-4 text-sm">{error}</p>}
			<section className="space-y-5 rounded-xl border bg-background p-5" aria-labelledby="domain-links">
				<div className="flex flex-wrap items-center justify-between gap-3"><h2 id="domain-links" className="text-lg font-semibold">Vinhomes</h2><Button variant="outline" className="min-h-11" disabled={busy || links.isFetching} onClick={() => void links.refetch()}>Cập nhật trạng thái</Button></div>
				{links.isPending ? <p role="status" className="text-sm">Đang tải liên kết…</p> : links.isError ? <p role="alert" className="text-sm">Chưa tải được liên kết. Vui lòng thử lại.</p> : links.data.length === 0 ? <p className="text-sm text-muted-foreground">Chưa liên kết domain nào.</p> : <ul className="divide-y">
					{links.data.map((link) => <li className="space-y-3 py-4 first:pt-0" key={link.id}>
						<div className="flex flex-wrap items-center justify-between gap-3"><div><p className="font-medium">{link.provider_id}</p><p className="text-sm text-muted-foreground">{statusLabels[link.status] ?? 'Cần kiểm tra trạng thái'}</p></div>
							{['active', 'revoke_pending'].includes(link.status) && <Button variant="outline" className="min-h-11" disabled={busy} onClick={() => setConfirmation(link.id)}>Thu hồi liên kết</Button>}</div>
						<p className="text-sm text-muted-foreground">Phạm vi đã cấp: {link.scopes.join(', ') || 'Chưa có phạm vi'}.</p>
						{confirmation === link.id && <div className="space-y-3 rounded-lg border p-4" role="group" aria-label="Xác nhận thu hồi"><p className="text-sm">Thu hồi sẽ chặn tác vụ mới qua liên kết này. Bạn có thể liên kết lại sau.</p><div className="flex flex-wrap gap-3"><Button className="min-h-11" variant="destructive" disabled={busy} onClick={() => void act(async () => {
							try { await personalApi.unlink(link.id); setConfirmation(null); } finally { await links.refetch(); }
						})}>Xác nhận thu hồi</Button><Button className="min-h-11" variant="outline" disabled={busy} onClick={() => setConfirmation(null)}>Giữ liên kết</Button></div></div>}
					</li>)}
				</ul>}
				<Button className="min-h-11" disabled={busy || links.isPending || links.isError || links.data?.some((link) => link.provider_id === 'vinhomes' && ['active', 'revoke_pending'].includes(link.status))} onClick={() => void act(async () => {
					const start = await personalApi.startLink('vinhomes');
					sessionStorage.setItem(storageKey(start.state), start.transaction_id);
					window.location.assign(start.authorization_url);
				})}>Liên kết Vinhomes</Button>
				<p className="text-sm leading-6 text-muted-foreground">Bạn đăng nhập và cho phép chia sẻ tại Vinhomes. Platform không thu mật khẩu Vinhomes.</p>
			</section>
			<section className="space-y-2"><h2 className="font-semibold">Kênh cá nhân</h2><p className="text-sm text-muted-foreground">Discord sẽ khả dụng sau khi hoàn tất xác minh danh tính và kiểm tra quyền riêng tư.</p></section>
		</main>
	);
}
