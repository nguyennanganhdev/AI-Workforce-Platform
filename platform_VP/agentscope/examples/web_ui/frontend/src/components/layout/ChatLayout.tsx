import { Outlet } from 'react-router-dom';

import { useClayTheme } from '@/hooks/useClayTheme';

/**
 * The chat shell: the conversation and nothing else. Its sidebar — the
 * agents and their sessions, with the way into Settings at the foot — is
 * drawn by the chat page itself, which owns that data.
 *
 * The sign-in page renders outside both shells and is left as it was.
 */
export function ChatLayout() {
	useClayTheme();

	return (
		<div className="h-screen bg-canvas">
			<Outlet />
		</div>
	);
}
