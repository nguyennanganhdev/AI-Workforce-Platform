import { Outlet } from 'react-router-dom';

import { usePlatformAccess } from '@/context/platform-access';
import { useCueTheme } from '@/hooks/useCueTheme';

/**
 * The chat shell: the conversation and nothing else. Its sidebar — the
 * agents and their sessions, with the way into Settings at the foot — is
 * drawn by the chat page itself, which owns that data.
 *
 * The sign-in page renders outside both shells and is left as it was.
 */
export function ChatLayout() {
	useCueTheme();
	const access = usePlatformAccess();

	return (
		<div className={access ? 'h-full min-h-0 bg-canvas' : 'h-screen bg-canvas'}>
			<Outlet />
		</div>
	);
}
