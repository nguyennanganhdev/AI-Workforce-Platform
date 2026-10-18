import { useEffect, useState } from 'react';

import type { EvalProgress } from '@/api';

/** Polls persisted evidence only; never starts or retries a model call. */
export function useEvaluationProgress(key: string | null, load: () => Promise<EvalProgress | null>, active: boolean) {
	const [state, setState] = useState<{ key: string; value: EvalProgress | null } | null>(null);
	const [error, setError] = useState(false);
	useEffect(() => {
		if (!key) return;
		let cancelled = false;
		let timer: ReturnType<typeof setTimeout>;
		const poll = async () => {
			let value: EvalProgress | null = null;
			try {
				value = await load();
				if (cancelled) return;
				setState({ key, value }); setError(false);
			} catch { if (!cancelled) setError(true); }
			if (!cancelled && (active || value?.status === 'running')) timer = setTimeout(poll, 2000);
		};
		void poll();
		return () => { cancelled = true; clearTimeout(timer); };
	}, [key, load, active]);
	return { progress: state?.key === key ? state.value : null, progressError: error };
}
