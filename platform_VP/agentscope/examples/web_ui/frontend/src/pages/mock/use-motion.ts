import { useEffect, useState } from 'react';

/** Milliseconds since `running` last turned true; holds still once it turns false. */
export function useElapsed(running: boolean): number {
	const [elapsed, setElapsed] = useState(0);
	useEffect(() => {
		if (!running) return;
		const start = performance.now();
		setElapsed(0);
		const timer = setInterval(() => setElapsed(performance.now() - start), 50);
		return () => clearInterval(timer);
	}, [running]);
	return elapsed;
}

/**
 * Whether this event finished while on screen, as opposed to being drawn
 * already finished (an earlier turn, another conversation reopened). Only a
 * live finish gets the check stroke, the pop and the unfold; history just sits
 * there.
 */
export function useLive(running: boolean): boolean {
	const [startedRunning] = useState(running);
	return startedRunning;
}
