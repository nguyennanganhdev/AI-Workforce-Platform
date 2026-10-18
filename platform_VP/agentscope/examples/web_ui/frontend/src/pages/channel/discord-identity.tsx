import { useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';

import { client } from '@/api/client';
import { Button } from '@/components/ui/button';
import { useCurrentUser } from '@/context/CurrentUserContext';
import { useDiscordIdentity } from '@/hooks/useDiscordIdentity';

export function DiscordIdentityPanel() {
	const user = useCurrentUser()!;
	const query = useDiscordIdentity();
	const queryClient = useQueryClient();
	const [busy, setBusy] = useState(false);
	const [message, setMessage] = useState('');
	const storageKey = `discord-oauth:${user.tenant_id}:${user.id}`;
	useEffect(() => {
		const params = new URLSearchParams(window.location.search);
		if (!params.has('state') || (!params.has('code') && !params.has('error'))) return;
		const state = params.get('state');
		const expected = sessionStorage.getItem(storageKey);
		const code = params.get('code');
		const issuer = params.get('iss');
		sessionStorage.removeItem(storageKey);
		window.history.replaceState(null, '', window.location.pathname);
		if (!code || !state || state !== expected || issuer !== 'https://discord.com') {
			setMessage('Không xác minh được phiên Discord. Hãy bắt đầu liên kết lại.');
			return;
		}
		setBusy(true);
		void client.post('/channels/discord/identity/complete', { state, code, issuer }, undefined, { silent: true })
			.then(() => { setMessage('Đã xác minh tài khoản Discord.'); return queryClient.invalidateQueries({ queryKey: ['discord-identity'] }); })
			.catch(() => setMessage('Xác minh chưa thành công. Hãy thử liên kết lại.'))
			.finally(() => setBusy(false));
	}, [queryClient, storageKey]);
	const start = async () => {
		setBusy(true); setMessage('');
		try {
			const result = await client.post<{ authorization_url: string; state: string }>('/channels/discord/identity/start', undefined, undefined, { silent: true });
			const url = new URL(result.authorization_url);
			if (url.origin !== 'https://discord.com' || url.pathname !== '/oauth2/authorize') throw new Error('Invalid authorization URL');
			sessionStorage.setItem(storageKey, result.state);
			window.location.assign(url.href);
		} catch { setMessage('Liên kết Discord chưa sẵn sàng. Vui lòng liên hệ quản trị.'); setBusy(false); }
	};
	return <section className="space-y-2 border-b px-4 py-3 text-sm" aria-label="Danh tính Discord">
		<p className="font-medium">{query.data?.verified ? `Discord đã xác minh: ${query.data.discord_user_id}` : 'Xác minh tài khoản Discord để dùng bot cá nhân'}</p>
		<p className="text-xs text-muted-foreground">Chủ bot được lấy từ tài khoản Discord bạn cho phép liên kết. Bot chỉ trả lời qua tin nhắn riêng; danh sách ID rỗng chặn mọi người.</p>
		{message && <p role="status">{message}</p>}
		<Button size="sm" variant="outline" disabled={busy} onClick={() => void start()}>{busy ? 'Đang xác minh…' : 'Liên kết danh tính Discord'}</Button>
		{query.data?.verified && <Button size="sm" variant="ghost" disabled={busy} onClick={async () => {
			setBusy(true);
			try { await client.delete('/channels/discord/identity'); await queryClient.invalidateQueries({ queryKey: ['discord-identity'] }); }
			catch { setMessage('Chưa hủy được liên kết. Vui lòng thử lại.'); }
			finally { setBusy(false); }
		}}>Hủy liên kết danh tính</Button>}
	</section>;
}
