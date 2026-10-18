/**
 * The office's colours. A box paints three faces: `top`, `left` for the faces
 * looking along y, `right` for those looking along x, so each side keeps its
 * colour whichever way the camera turns.
 */

export type Palette = { top: string; left: string; right: string; stroke?: string };

export const WOOD: Palette = { top: '#ecd8bb', left: '#d6b892', right: '#c4a079' };
export const WHITE: Palette = { top: '#ffffff', left: '#e9e9ee', right: '#dcdce4' };
export const SLATE: Palette = { top: '#4a4f5c', left: '#353945', right: '#2a2d36' };
export const MINT: Palette = { top: '#f7fffc', left: '#bfe8dc', right: '#a6d9cb' };
export const CHAIR: Palette = { top: '#9aa3b5', left: '#7d8699', right: '#6c7487' };
export const POT: Palette = { top: '#8c6b52', left: '#d98f6a', right: '#c47a57' };
export const GLASS: Palette = {
	top: 'rgba(140,170,230,0.55)',
	left: 'rgba(170,200,255,0.16)',
	right: 'rgba(150,185,250,0.22)',
	stroke: 'rgba(110,140,205,0.45)',
};
/** Outline for boxes whose palette names none. */
export const EDGE = 'rgba(0,0,0,0.06)';

export const LEAVES = { main: '#6fbf8a', light: '#8fd6a4', dark: '#5aab76' };
export const SCREEN = { off: '#30343f', on: '#5b8def', frame: '#1d2029', text: '#dce7ff' };
export const KEYBOARD = '#cfd3dc';

export const ROOM = {
	floor: '#faf7f2',
	grid: 'rgba(120,100,70,0.08)',
	/** The wall along x = 0, and the wall along y = 0. */
	wallLeft: '#ebe5da',
	wallBack: '#f5f0e8',
	wallRim: '#d8cfc0',
	/** The slab's cut faces: the x side, then the y side. */
	slabRight: '#e3dbcd',
	slabLeft: '#ece5d8',
	meeting: '#eef2ff',
	approval: '#fff4dc',
	reception: '#e9f7f1',
	background: '#f3f1ec',
};

export const BOARD = { fill: '#ffffff', stroke: '#c9ccd6' };
export const NOTES = [
	[1.7, 2.3, 66, '#ffd166'],
	[2.5, 3.1, 66, '#9ce3d5'],
	[3.3, 3.9, 66, '#aec4ff'],
	[1.7, 2.3, 48, '#ffc0a7'],
	[2.5, 3.1, 48, '#ffd166'],
] as const;
export const WINDOW = { fill: '#d9ecff', stroke: '#c4d3e6' };
export const DOOR = { fill: '#c9a27c', stroke: '#b08a66' };
