import { useEffect, useMemo, useRef } from 'react';
import type { ReactNode } from 'react';

import { AudioContext, ReplayContext, type ReplayController } from './audio-context';
import { StreamingAudioManager } from '@/utils/streamingAudio';

/**
 * Provides a {@link StreamingAudioManager} to the component tree. The manager
 * collects DATA_BLOCK_* events for audio blocks and exposes per-block state
 * that ``MessageBubble`` consumes via ``useAudioBlock`` (see
 * ``./audio-context``).
 *
 * Mount this once around any subtree that renders assistant messages.
 */
export function AudioProvider({ children }: { children: ReactNode }) {
	const manager = useMemo(() => new StreamingAudioManager(), []);
	useEffect(() => () => manager.disposeAll(), [manager]);

	const currentRef = useRef<HTMLAudioElement | null>(null);
	const replay: ReplayController = useMemo(
		() => ({
			play(el: HTMLAudioElement) {
				manager.stopLivePlayback();
				if (currentRef.current && currentRef.current !== el) {
					currentRef.current.pause();
					currentRef.current.currentTime = 0;
				}
				currentRef.current = el;
			},
			stop() {
				currentRef.current = null;
			},
		}),
		[manager],
	);

	return (
		<AudioContext.Provider value={manager}>
			<ReplayContext.Provider value={replay}>{children}</ReplayContext.Provider>
		</AudioContext.Provider>
	);
}
