import { Cable, MessageCircle, MessagesSquare, Send, Webhook } from 'lucide-react';

import type { ChannelTypeSchema } from '@/api';
import { cn } from '@/lib/utils';

/** Brand colour and mark per channel type, drawn locally (no remote favicon). */
const BRAND: Record<string, { color: string; Icon: typeof Send }> = {
	telegram: { color: '#229ED9', Icon: Send },
	discord: { color: '#5865F2', Icon: MessagesSquare },
	dingtalk: { color: '#3296FA', Icon: MessageCircle },
	feishu: { color: '#3370FF', Icon: MessageCircle },
	custom: { color: '#52525b', Icon: Webhook },
};

/** Brand tile for a channel type; unknown types get a neutral cable mark. */
export function TypeAvatar({ type, className }: { type?: ChannelTypeSchema; className?: string }) {
	const brand = BRAND[type?.channel_type ?? ''] ?? { color: '#71717a', Icon: Cable };
	const { Icon } = brand;
	return (
		<span
			aria-hidden="true"
			className={cn('flex shrink-0 items-center justify-center rounded-xl text-white', className)}
			style={{ background: brand.color }}
		>
			<Icon className="size-[55%]" strokeWidth={2.2} />
		</span>
	);
}
