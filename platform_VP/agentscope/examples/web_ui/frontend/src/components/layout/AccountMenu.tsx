import { ChevronRight, ChevronsUpDown, Compass, Languages, LogOut, Settings } from 'lucide-react';
import { useOnborda } from 'onborda';
import { useNavigate } from 'react-router-dom';

import { authApi } from '@/api';
import { CHAT_TOUR_NAME } from '@/components/tour/chatTourSteps';
import { Button } from '@/components/ui/button';
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuSeparator,
	DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { useCurrentUser } from '@/context/CurrentUserContext';
import i18n from '@/i18n';
import { useTranslation } from '@/i18n/useI18n';

// In a sidebar folded to icons (`collapsible="icon"`) only the 32px circle is left.
const ROW =
	'h-12 w-full justify-start gap-3 rounded-xl px-2 text-[15px]/5 font-normal group-data-[collapsible=icon]:size-10 group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:px-0 group-data-[collapsible=icon]:[&>*:not(:first-child)]:hidden';

/**
 * The foot of a sidebar, after Cue's two-line footer: a 48px row into
 * Settings (a bordered 32px icon circle), then the account — a 32px letter
 * avatar and the name — whose menu holds language, tour and sign out.
 *
 * Shared by both shells so the account sits in the same place whichever one
 * is open. The chat shell shows the Settings row; the settings shell does not,
 * since it is already there.
 */
export function AccountMenu({
	showSettings = false,
	showTour = false,
}: {
	showSettings?: boolean;
	/** Only where the chat tour's targets are on screen. */
	showTour?: boolean;
}) {
	const navigate = useNavigate();
	const { t } = useTranslation();
	const { startOnborda } = useOnborda();
	const user = useCurrentUser();

	const displayName = user?.username || user?.email || t('shell.account');

	const handleLogout = async () => {
		try {
			await authApi.logout();
		} finally {
			window.location.assign('/');
		}
	};

	return (
		<div className="flex flex-col gap-px">
			{showSettings && (
				<Button variant="ghost" className={ROW} onClick={() => navigate('/settings')}>
					<span className="flex size-8 shrink-0 items-center justify-center rounded-full border border-[var(--cue-border,var(--border))]">
						<Settings className="size-4" />
					</span>
					<span className="min-w-0 flex-1 truncate text-left">
						{t('common.settings')}
					</span>
					<ChevronRight className="size-4 text-muted-foreground" />
				</Button>
			)}
			<DropdownMenu>
				<DropdownMenuTrigger asChild>
					<Button variant="ghost" className={ROW}>
						<span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-[var(--cue-avatar-user,#e5484d)] text-[15px] font-medium text-white">
							{displayName.charAt(0).toUpperCase()}
						</span>
						<span className="min-w-0 flex-1 truncate text-left">{displayName}</span>
						<ChevronsUpDown className="size-3.5 text-muted-foreground" />
					</Button>
				</DropdownMenuTrigger>
				{/* w-auto: the default pins the menu to the trigger's width,
				    which clips the longer labels. */}
				<DropdownMenuContent side="top" align="start" className="w-auto min-w-52">
					{[
						['vi', 'Tiếng Việt'],
						['en', 'English'],
						['zh', '中文'],
					].map(([code, label]) => (
						<DropdownMenuItem key={code} onClick={() => void i18n.changeLanguage(code)}>
							<Languages />
							{label}
							{i18n.resolvedLanguage === code ? ' ✓' : ''}
						</DropdownMenuItem>
					))}
					{showTour && (
						<DropdownMenuItem onClick={() => startOnborda(CHAT_TOUR_NAME)}>
							<Compass />
							{t('tour.trigger')}
						</DropdownMenuItem>
					)}
					<DropdownMenuSeparator />
					<DropdownMenuItem variant="destructive" onClick={handleLogout}>
						<LogOut />
						{t('auth.logout')}
					</DropdownMenuItem>
				</DropdownMenuContent>
			</DropdownMenu>
		</div>
	);
}
