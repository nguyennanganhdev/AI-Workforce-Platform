import type { MockEvent } from './chat-mock-data';

/** How long an answer shows the typing dots before its first word lands. */
export const TYPING_MS = 500;

/**
 * How fast an answer streams in: 40ms a word, quicker for a long answer so
 * none takes more than about two and a half seconds to arrive.
 */
export function streamPlan(text: string): { words: number; wordMs: number } {
	const words = text.split(/\s+/).filter(Boolean).length;
	return { words, wordMs: Math.min(40, 2500 / Math.max(1, words)) };
}

/** How long a thinking event stays "under way"; the live counter runs over this. */
export function thinkingMs(seconds: number): number {
	return Math.min(2600, seconds * 650);
}

/** How long an event stays "under way" before the next one appears. */
export function durationOf(event: MockEvent): number {
	switch (event.kind) {
		case 'user':
			return 600;
		case 'step':
			return 900;
		case 'thinking':
			return thinkingMs(event.seconds);
		case 'tool':
			return 1100;
		case 'agent': {
			const { words, wordMs } = streamPlan(event.text);
			return TYPING_MS + words * wordMs + 250;
		}
		case 'state':
			return 350;
		case 'gate':
			return 0;
	}
}
