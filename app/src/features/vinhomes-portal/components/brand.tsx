import '@fontsource/be-vietnam-pro/vietnamese-400.css';
import '@fontsource/be-vietnam-pro/vietnamese-500.css';
import '@fontsource/be-vietnam-pro/vietnamese-600.css';
import '@fontsource/be-vietnam-pro/vietnamese-700.css';
import '@fontsource/be-vietnam-pro/latin-400.css';
import '@fontsource/be-vietnam-pro/latin-500.css';
import '@fontsource/be-vietnam-pro/latin-600.css';
import '@fontsource/be-vietnam-pro/latin-700.css';
import { Link } from '@tanstack/react-router';
import { IconBuildingCommunity } from '@tabler/icons-react';
import { cn } from '@/lib/utils';

/*
 * Portal design tokens.
 * Type: Be Vietnam Pro (drawn for Vietnamese diacritics) for the whole portal.
 * Shape: interactive = full pill, surfaces/images = rounded-2xl (16px), inputs = rounded-xl (12px).
 * Accent: one teal, taken from the river in the hero photo; neutrals are cool zinc.
 */
export const PORTAL_FONT = "font-['Be_Vietnam_Pro',ui-sans-serif,system-ui,sans-serif]";

const PRESS = 'transition-[background-color,color,transform,box-shadow] duration-200 active:scale-[0.98] disabled:pointer-events-none disabled:opacity-60';

/** Primary action: teal on light, light teal on dark (both pass WCAG AA with their text color). */
export const accentButton = cn(
  'inline-flex h-11 items-center justify-center gap-2 rounded-full bg-teal-700 px-6 text-[15px] font-medium whitespace-nowrap text-white hover:bg-teal-800 focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-teal-600/40 dark:bg-teal-300 dark:text-teal-950 dark:hover:bg-teal-200',
  PRESS,
);

/** Secondary action on the hero photo. */
export const glassButton = cn(
  'inline-flex h-11 items-center justify-center gap-2 rounded-full border border-white/35 bg-white/10 px-6 text-[15px] font-medium whitespace-nowrap text-white backdrop-blur-md hover:bg-white/20 focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-white/40',
  PRESS,
);

/** Secondary action on page surfaces. */
export const outlineButton = cn(
  'inline-flex h-11 items-center justify-center gap-2 rounded-full border border-border bg-background px-6 text-[15px] font-medium whitespace-nowrap text-foreground hover:bg-muted focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/40',
  PRESS,
);

export const accentText = 'text-teal-700 dark:text-teal-300';

export function Wordmark({ onPhoto = false, className }: { onPhoto?: boolean; className?: string }) {
  return (
    <Link to="/vinhomes" className={cn('inline-flex items-center gap-2.5 rounded-full focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-teal-600/40', className)}>
      <span
        className={cn(
          'flex size-9 items-center justify-center rounded-xl',
          onPhoto ? 'bg-white/15 text-white backdrop-blur-md' : 'bg-teal-700 text-white dark:bg-teal-300 dark:text-teal-950',
        )}
      >
        <IconBuildingCommunity className="size-5" stroke={1.75} />
      </span>
      <span className="flex flex-col leading-tight">
        <span className={cn('text-[15px] font-semibold tracking-tight', onPhoto ? 'text-white' : 'text-foreground')}>Vinhomes</span>
        <span className={cn('text-xs', onPhoto ? 'text-white/70' : 'text-muted-foreground')}>Cư dân và Vận hành</span>
      </span>
    </Link>
  );
}
