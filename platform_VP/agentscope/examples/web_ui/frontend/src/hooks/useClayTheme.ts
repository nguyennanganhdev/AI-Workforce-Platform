import { useLayoutEffect } from 'react';

/**
 * Switches the clay design layer on (see `styles/clay.css`) for as long as the
 * calling component is mounted.
 *
 * The class goes on `<body>` rather than on a wrapper element, because
 * dialogs, menus and tooltips portal out to `<body>` and would otherwise stay
 * unthemed.
 */
export function useClayTheme() {
	useLayoutEffect(() => {
		document.body.classList.add('clay-theme');
		return () => document.body.classList.remove('clay-theme');
	}, []);
}
