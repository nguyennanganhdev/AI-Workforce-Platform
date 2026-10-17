import { Bot, Plus, UserRoundPlus } from 'lucide-react';

import { Button } from '@/components/ui/button';
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { useTranslation } from '@/i18n/useI18n';

/** Cue's "+": one menu for the two things a conversation can be. */
export function NewChatMenu({
	onCreateAgent,
	onCreateGroup,
}: {
	onCreateAgent: () => void;
	onCreateGroup: () => void;
}) {
	const { t } = useTranslation();
	return (
		<DropdownMenu>
			<DropdownMenuTrigger asChild>
				<Button
					id="tour-create-agent"
					variant="ghost"
					size="icon"
					aria-label={t('chat.session.newMenu')}
					title={t('chat.session.newMenu')}
					className="aria-expanded:bg-[var(--cue-bg-subtle,var(--accent))]"
				>
					<Plus className="size-5" />
				</Button>
			</DropdownMenuTrigger>
			<DropdownMenuContent align="start" sideOffset={6} className="w-60 p-1.5">
				<DropdownMenuItem
					className="h-11 gap-3 rounded-xl px-3 text-[15px]"
					onClick={onCreateAgent}
				>
					<Bot className="size-5" />
					{t('groupChat.menuAgent')}
				</DropdownMenuItem>
				<DropdownMenuItem
					className="h-11 gap-3 rounded-xl px-3 text-[15px]"
					onClick={onCreateGroup}
				>
					<UserRoundPlus className="size-5" />
					{t('groupChat.menuGroup')}
				</DropdownMenuItem>
			</DropdownMenuContent>
		</DropdownMenu>
	);
}
