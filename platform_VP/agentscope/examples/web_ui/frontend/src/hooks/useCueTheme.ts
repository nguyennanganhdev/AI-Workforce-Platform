import { useLayoutEffect } from 'react';

/**
 * Switches the Cue design layer on (see `styles/cue.css`) for as long as the
 * calling component is mounted.
 *
 * The class goes on `<body>` rather than on a wrapper element, because
 * dialogs, menus and tooltips portal out to `<body>` and would otherwise stay
 * unthemed.
 */
export function useCueTheme() {
	useLayoutEffect(() => {
		document.body.classList.add('cue-theme');
		return () => document.body.classList.remove('cue-theme');
	}, []);
}
