import vagentsIcon from '@/assets/images/brand/vagents-app-icon.png';
import { cn } from '@/lib/utils';

/** The product's name, wherever it is spelled out next to the mark. */
export const BRAND_NAME = 'VAgents';

/**
 * The vAgents app icon: the white "V" with its orange spark on a black,
 * rounded tile. Size it with `className` (e.g. `size-7`); the tile carries its
 * own corners, so no wrapper background is needed.
 */
export function BrandMark({ className }: { className?: string }) {
	return (
		<img
			src={vagentsIcon}
			alt=""
			aria-hidden="true"
			draggable={false}
			className={cn('size-7 shrink-0 select-none', className)}
		/>
	);
}

/** The product mark and name, as the head of a sidebar. */
export function Brand({ className }: { className?: string }) {
	return (
		<div className={cn('flex min-w-0 items-center gap-2', className)}>
			<BrandMark />
			<span className="truncate text-[15px]/5 font-semibold">{BRAND_NAME}</span>
		</div>
	);
}
