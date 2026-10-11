/**
 * What a selected row looks like, written once, for lists that are not built
 * on `SidebarMenuButton` (which draws the same slab from its own
 * `data-active` state).
 *
 * A peach slab with a near-white border, an inner highlight, an inner shadow
 * and a solid lip underneath. The lip is what separates it from hover rather
 * than the hue: hover is flat, selection sits ON the panel — so colour is
 * never the only signal.
 *
 * `hover:` is repeated because hovering the selected row would otherwise
 * repaint it with the hover colour and flatten the slab under the pointer.
 *
 * The border is a colour change, not an addition: every surface using this
 * must reserve `border border-transparent` at rest (`Button` already does),
 * so selection costs no layout.
 */
export const SELECTED_ROW =
	'bg-[var(--selected)] border-[var(--selected-line)] shadow-[var(--clay-selected)] hover:bg-[var(--selected)]';
