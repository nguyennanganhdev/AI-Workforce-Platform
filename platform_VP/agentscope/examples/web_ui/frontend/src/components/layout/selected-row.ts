/**
 * What a selected row looks like, written once, for lists that are not built
 * on `SidebarMenuButton` (which draws the same state from its own
 * `data-active`).
 *
 * Cue draws selection flat: a grey `--bg-subtle` fill, no accent bar and no
 * change of text colour. Hover uses a lighter grey, so the two stay distinct.
 *
 * `hover:` is repeated because hovering the selected row would otherwise
 * repaint it with the hover colour.
 */
export const SELECTED_ROW =
	'bg-[var(--selected)] border-[var(--selected-line)] hover:bg-[var(--selected)]';
