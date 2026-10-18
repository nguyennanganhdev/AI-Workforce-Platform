import { Check, Copy, KeyRound, Loader2 } from 'lucide-react';
import { useState } from 'react';

import { channelApi } from '@/api';
import type { ChannelRecord } from '@/api';
import { getApiUrl } from '@/api/client';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

/** Setup details and token replacement for the two text connectors. */
export function ChannelConnection({ channel }: { channel: ChannelRecord }) {
	const [token, setToken] = useState('');
	const [busy, setBusy] = useState(false);
	const [message, setMessage] = useState('');
	const [failed, setFailed] = useState(false);
	const [copied, setCopied] = useState(false);
	const isZalo = channel.channel_type === 'zalo_oa';
	if (!isZalo && channel.channel_type !== 'telegram') return null;
	const webhook = getApiUrl(`/channels/${encodeURIComponent(channel.id)}/webhook`).href;

	const save = async () => {
		setBusy(true);
		setMessage('');
		try {
			await channelApi.rotateCredentials(channel.id, { [isZalo ? 'access_token' : 'bot_token']: token.trim() });
			setToken('');
			setFailed(false);
			setMessage('Đã lưu token mới. Kênh sẽ tự kết nối lại.');
		} catch {
			setFailed(true);
			setMessage('Chưa lưu được token. Kiểm tra quyền truy cập và token rồi thử lại.');
		} finally {
			setBusy(false);
		}
	};

	return (
		<section aria-label="Thiết lập kết nối" className="space-y-3 border-b pb-5">
			<h2 className="text-sm font-semibold">Kết nối {isZalo ? 'Zalo OA' : 'Telegram'}</h2>
			{isZalo ? <>
				<p className="text-xs leading-relaxed text-muted-foreground">Dán địa chỉ này vào Webhook URL của Zalo App và bật sự kiện tin nhắn người dùng. Địa chỉ công khai cần dùng HTTPS.</p>
				<div className="flex min-w-0 items-center gap-2">
					<Input aria-label="Webhook URL" readOnly value={webhook} className="min-w-0 flex-1 font-mono text-xs" />
					<Button variant="outline" size="icon" aria-label="Sao chép Webhook URL" onClick={async () => {
						try { await navigator.clipboard.writeText(webhook); setCopied(true); }
						catch { setFailed(true); setMessage('Không sao chép được. Bạn có thể chọn và chép địa chỉ trong ô.'); }
					}}>{copied ? <Check /> : <Copy />}</Button>
				</div>
				<p className="text-xs leading-relaxed text-muted-foreground">Yêu cầu duyệt được gửi bằng mã riêng: trả lời DUYET hoặc TUCHOI kèm mã trong tin nhắn. Token OA hết hạn có thể thay bên dưới để giữ nguyên lịch sử kênh.</p>
			</> : <p className="text-xs leading-relaxed text-muted-foreground">Mở bot trên Telegram và chọn Start để bắt đầu. Trong nhóm, gọi @tên_bot hoặc trả lời tin của bot. Khi cần duyệt công cụ, bot sẽ gửi nút Đồng ý và Từ chối.</p>}
			<details className="text-xs">
				<summary className="cursor-pointer py-1 font-medium focus-visible:outline-2 focus-visible:outline-ring">Thay token kết nối</summary>
				<form className="mt-3 space-y-2" onSubmit={(event) => { event.preventDefault(); void save(); }}>
					<label htmlFor={`channel-token-${channel.id}`} className="block font-medium">{isZalo ? 'OA access token mới' : 'Bot token mới'}</label>
					<Input id={`channel-token-${channel.id}`} type="password" autoComplete="new-password" value={token} onChange={(event) => setToken(event.target.value)} disabled={busy} />
					<Button type="submit" variant="outline" size="sm" disabled={busy || !token.trim()}>{busy ? <Loader2 className="animate-spin" /> : <KeyRound />}Lưu token mới</Button>
				</form>
			</details>
			{message && <p role={failed ? 'alert' : 'status'} className={failed ? 'text-xs text-destructive' : 'text-xs text-muted-foreground'}>{message}</p>}
		</section>
	);
}
