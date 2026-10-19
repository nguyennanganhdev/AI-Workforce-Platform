import type { ReactNode } from 'react';
import { IconChevronLeft, IconChevronRight, IconSearch } from '@tabler/icons-react';
import { Button } from '@/components/ui/button';
import { Card, CardAction, CardContent, CardFooter, CardHeader } from '@/components/ui/card';
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from '@/components/ui/empty';
import { InputGroup, InputGroupAddon, InputGroupInput } from '@/components/ui/input-group';
import { Pagination as PaginationRoot, PaginationContent, PaginationEllipsis, PaginationItem } from '@/components/ui/pagination';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import { cn } from '@/lib/utils';

/** Accent-insensitive search key so "toa s2" matches "Tòa S2.01". */
export function normalizeSearch(text: string) {
  return text.normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/đ/gi, 'd').toLowerCase();
}

export const PAGE_SIZE = 10;

export function paginate<T>(items: T[], page: number, size = PAGE_SIZE) {
  const pages = Math.max(1, Math.ceil(items.length / size));
  const current = Math.min(Math.max(1, page), pages);
  return { pages, current, slice: items.slice((current - 1) * size, current * size) };
}

/** Page title with the short accent bar used across the operations area. */
export function PanelTitle({ as: Tag = 'h1', className, children }: { as?: 'h1' | 'h2'; className?: string; children: ReactNode }) {
  return (
    <Tag
      className={cn(
        'relative min-w-0 pl-3.5 font-semibold leading-snug text-foreground before:absolute before:left-0 before:top-[0.2em] before:h-[1.1em] before:w-1 before:rounded-full before:bg-primary',
        Tag === 'h1' ? 'text-lg md:text-xl' : 'text-base md:text-[17px]',
        className,
      )}
    >
      {children}
    </Tag>
  );
}

/** White working surface: title row, optional toolbar row, content, optional footer. */
export function Panel({
  title,
  titleAs,
  meta,
  toolbar,
  footer,
  children,
}: {
  title: ReactNode;
  titleAs?: 'h1' | 'h2';
  meta?: ReactNode;
  toolbar?: ReactNode;
  footer?: ReactNode;
  children: ReactNode;
}) {
  return (
    <Card className="gap-4 pt-4 md:pt-5 pb-0">
      <CardHeader className="items-center px-4 md:px-6">
        <PanelTitle as={titleAs}>{title}</PanelTitle>
        {meta && <CardAction className="row-span-1 self-center text-sm text-muted-foreground">{meta}</CardAction>}
      </CardHeader>
      {toolbar && (
        <CardContent className="flex flex-col gap-3 px-4 md:flex-row md:items-center md:justify-between md:px-6">{toolbar}</CardContent>
      )}
      <div className="min-w-0">{children}</div>
      {footer ? <CardFooter className="px-4 md:px-6">{footer}</CardFooter> : <div className="h-1" />}
    </Card>
  );
}

/** Filter chips ("All / This week" in the reference). Scrolls sideways on phones. */
export function Segmented<T extends string>({
  value,
  options,
  onChange,
  label,
}: {
  value: T;
  options: Array<{ id: T; label: string; count?: number }>;
  onChange: (id: T) => void;
  label: string;
}) {
  return (
    <ToggleGroup
      aria-label={label}
      variant="outline"
      spacing={2}
      value={[value]}
      onValueChange={(next) => {
        const picked = next[0] as T | undefined;
        if (picked) onChange(picked);
      }}
      className="ops-scroll-tabs max-w-full min-w-0"
    >
      {options.map((o) => (
        <ToggleGroupItem
          key={o.id}
          value={o.id}
          size="lg"
          className="px-3.5 data-pressed:border-primary data-pressed:bg-primary data-pressed:text-primary-foreground"
        >
          {o.label}
          {o.count !== undefined && o.count > 0 && (
            <span className="text-xs tabular-nums text-muted-foreground group-data-pressed/toggle:text-primary-foreground/80">{o.count}</span>
          )}
        </ToggleGroupItem>
      ))}
    </ToggleGroup>
  );
}

export function SearchField({
  value,
  onChange,
  placeholder,
  label = 'Tìm kiếm',
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
  label?: string;
}) {
  return (
    <InputGroup className="w-full bg-card md:w-72">
      <InputGroupAddon>
        <IconSearch />
      </InputGroupAddon>
      <InputGroupInput
        type="search"
        aria-label={label}
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        className="max-md:text-base"
      />
    </InputGroup>
  );
}

/** Windowed page numbers: 1 … 4 5 6 … 12 */
function pageWindow(current: number, pages: number): Array<number | 'gap'> {
  if (pages <= 7) return Array.from({ length: pages }, (_, i) => i + 1);
  const out: Array<number | 'gap'> = [1];
  const start = Math.max(2, current - 1);
  const end = Math.min(pages - 1, current + 1);
  if (start > 2) out.push('gap');
  for (let p = start; p <= end; p++) out.push(p);
  if (end < pages - 1) out.push('gap');
  out.push(pages);
  return out;
}

export function Pagination({
  page,
  pages,
  total,
  unit,
  onChange,
}: {
  page: number;
  pages: number;
  total: number;
  unit: string;
  onChange: (p: number) => void;
}) {
  return (
    <div className="flex w-full flex-wrap items-center justify-center gap-3 sm:justify-between">
      <p role="status" className="flex items-center gap-2.5 text-sm">
        <span className="rounded-md border bg-card px-2.5 py-1 font-medium text-foreground">Trang {page} / {pages}</span>
        <span className="text-muted-foreground">{total} {unit}</span>
      </p>
      <PaginationRoot aria-label="Phân trang" className="mx-0 w-auto">
        <PaginationContent>
          <PaginationItem>
            <Button variant="ghost" size="icon-lg" aria-label="Trang trước" disabled={page <= 1} onClick={() => onChange(page - 1)}>
              <IconChevronLeft />
            </Button>
          </PaginationItem>
          {pageWindow(page, pages).map((p, i) => (
            <PaginationItem key={p === 'gap' ? `gap-${i}` : p}>
              {p === 'gap' ? (
                <PaginationEllipsis />
              ) : (
                <Button
                  variant={p === page ? 'outline' : 'ghost'}
                  size="icon-lg"
                  aria-current={p === page ? 'page' : undefined}
                  onClick={() => onChange(p)}
                  className="tabular-nums"
                >
                  {p}
                </Button>
              )}
            </PaginationItem>
          ))}
          <PaginationItem>
            <Button variant="ghost" size="icon-lg" aria-label="Trang sau" disabled={page >= pages} onClick={() => onChange(page + 1)}>
              <IconChevronRight />
            </Button>
          </PaginationItem>
        </PaginationContent>
      </PaginationRoot>
    </div>
  );
}

export function EmptyState({ title, hint }: { title: string; hint?: ReactNode }) {
  return (
    <Empty className="py-12">
      <EmptyHeader>
        <EmptyTitle>{title}</EmptyTitle>
        {hint && <EmptyDescription>{hint}</EmptyDescription>}
      </EmptyHeader>
    </Empty>
  );
}
