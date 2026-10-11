import { ChevronsUpDown, CircleUserRound, Compass, Languages, LogOut, Settings } from 'lucide-react';
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

const ROW = 'h-10 w-full justify-start gap-3 px-2.5 font-normal';

/**
 * The foot of a sidebar: the way into Settings, and the account's own menu
 * (language, tour, sign out).
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

	const inVietnamese = i18n.language.startsWith('vi');

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
					<Settings />
					{t('common.settings')}
				</Button>
			)}
			<DropdownMenu>
				<DropdownMenuTrigger asChild>
					<Button variant="ghost" className={ROW}>
						<CircleUserRound />
						<span className="min-w-0 flex-1 truncate text-left">
							{user?.username || user?.email || t('shell.account')}
						</span>
						<ChevronsUpDown className="size-3.5 text-muted-foreground" />
					</Button>
				</DropdownMenuTrigger>
				{/* w-auto: the default pins the menu to the trigger's width,
				    which clips the longer labels. */}
				<DropdownMenuContent side="top" align="start" className="w-auto min-w-52">
					<DropdownMenuItem
						onClick={() => i18n.changeLanguage(inVietnamese ? 'en' : 'vi')}
					>
						<Languages />
						{inVietnamese ? t('common.switchToEn') : t('common.switchToVi')}
					</DropdownMenuItem>
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
