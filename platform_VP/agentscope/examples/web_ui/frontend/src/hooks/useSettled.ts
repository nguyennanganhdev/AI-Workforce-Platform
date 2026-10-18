import { useEffect, useRef, useState } from 'react';

/**
 * Whether a fetch that reports `loading` has come back at least once.
 *
 * The list hooks here start with an empty list and `loading: false`, then
 * flip to `true` in an effect — so on the first render "empty" and "not asked
 * yet" look the same. This turns true only after `loading` has been seen
 * going up and coming back down.
 */
export function useSettled(loading: boolean): boolean {
	const [settled, setSettled] = useState(false);
	const sawLoading = useRef(false);
	useEffect(() => {
		if (loading) sawLoading.current = true;
		else if (sawLoading.current) setSettled(true);
	}, [loading]);
	return settled;
}
