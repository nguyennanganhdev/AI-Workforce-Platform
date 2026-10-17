import { createContext, useContext, useSyncExternalStore } from 'react';

import type { StreamingAudioManager, StreamingAudioState } from '@/utils/streamingAudio';

export interface ReplayController {
	play: (el: HTMLAudioElement) => void;
	stop: () => void;
}

export const AudioContext = createContext<StreamingAudioManager | null>(null);

export const ReplayContext = createContext<ReplayController | null>(null);

/**
 * Access the streaming audio manager. Returns ``null`` outside of an
 * ``AudioProvider`` — callers must handle that, since audio handling is
 * an optional feature.
 */
export function useAudioManager(): StreamingAudioManager | null {
	return useContext(AudioContext);
}

/**
 * Access the replay controller that ensures only one audio element plays
 * at a time across all message bubbles.
 */
export function useReplayController(): ReplayController | null {
	return useContext(ReplayContext);
}

/**
 * Subscribe to the streaming state for a single audio DataBlock.
 * Re-renders when the block transitions from ``streaming`` to ``ready``.
 *
 * Returns ``null`` if the block isn't being tracked (e.g. a historical
 * message loaded from the server, where the bytes are already complete).
 */
export function useAudioBlock(blockId: string | undefined): StreamingAudioState | null {
	const manager = useAudioManager();
	return useSyncExternalStore(
		(fn) => {
			if (!manager || !blockId) return () => undefined;
			return manager.subscribe(blockId, fn);
		},
		() => (manager && blockId ? manager.getState(blockId) : null),
		() => null,
	);
}
