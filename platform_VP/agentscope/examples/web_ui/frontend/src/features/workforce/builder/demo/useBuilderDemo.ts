import { useEffect, useRef, useState } from 'react';

import { mockBuilderClient } from './mockBuilderClient';
import type { DemoAction } from './mockBuilderClient';
import { initialState } from './model';
import type { DemoAgent, DemoState } from './model';

const KEY = 'workforce.builder.demo.v1';
function restore(): DemoState {
	try {
		const value = JSON.parse(sessionStorage.getItem(KEY) ?? 'null');
		if (
			value?.version === 1 &&
			['start', 'clarify', 'outline', 'configure', 'done'].includes(value.stage) &&
			['knowledge', 'travel', 'missing'].includes(value.scenario) &&
			Array.isArray(value.messages) &&
			value.messages.every(
				(m: Record<string, unknown>) =>
					m &&
					typeof m.id === 'string' &&
					typeof m.text === 'string' &&
					['user', 'builder'].includes(String(m.role)),
			) &&
			Array.isArray(value.agents) &&
			value.agents.every(
				(a: Record<string, unknown>) =>
					a &&
					['id', 'name', 'objective', 'instructions'].every(
						(k) => typeof a[k] === 'string',
					) &&
					['tools', 'knowledge'].every(
						(k) =>
							Array.isArray(a[k]) &&
							a[k].every((s: unknown) => typeof s === 'string'),
					) &&
					(a.blocker === undefined || typeof a.blocker === 'string'),
			)
		)
			return value;
	} catch {
		/* Storage may be disabled or contain an older demo. */
	}
	return initialState();
}
export function useBuilderDemo() {
	const [state, setState] = useState(restore);
	const [busy, setBusy] = useState(false);
	const [error, setError] = useState('');
	const [failNext, setFailNext] = useState(false);
	const [storageWarning, setStorageWarning] = useState(false);
	const active = useRef<AbortController | null>(null);
	const retryAction = useRef<DemoAction | null>(null);
	useEffect(() => {
		try {
			sessionStorage.setItem(KEY, JSON.stringify(state));
			setStorageWarning(false);
		} catch {
			setStorageWarning(true);
		}
	}, [state]);
	useEffect(
		() => () => {
			active.current?.abort();
		},
		[],
	);
	async function run(action: DemoAction) {
		if (active.current) return false;
		const controller = new AbortController();
		active.current = controller;
		retryAction.current = action;
		setBusy(true);
		setError('');
		const fail = failNext;
		setFailNext(false);
		try {
			const result = await mockBuilderClient(state, action, controller.signal, fail);
			if (active.current !== controller || controller.signal.aborted) return false;
			setState(result);
			retryAction.current = null;
			return true;
		} catch (e) {
			if (!controller.signal.aborted && active.current === controller)
				setError(e instanceof Error ? e.message : 'Không thể xử lý yêu cầu.');
			return false;
		} finally {
			if (active.current === controller) {
				active.current = null;
				setBusy(false);
			}
		}
	}
	function reset() {
		active.current?.abort();
		active.current = null;
		retryAction.current = null;
		setState(initialState());
		setBusy(false);
		setError('');
		setFailNext(false);
	}
	function edit(id: string, patch: Partial<DemoAgent>) {
		if (active.current || state.stage !== 'configure') return;
		setState((s) => ({
			...s,
			agents: s.agents.map((a) => (a.id === id ? { ...a, ...patch } : a)),
		}));
	}
	return {
		state,
		busy,
		error,
		failNext,
		setFailNext,
		storageWarning,
		run,
		reset,
		edit,
		retry: () => (retryAction.current ? run(retryAction.current) : Promise.resolve(false)),
	};
}
