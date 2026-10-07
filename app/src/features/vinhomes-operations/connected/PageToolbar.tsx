import { useEffect, useState, type ReactNode } from 'react';
import { createPortal } from 'react-dom';

/** Page controls share the layout header; the legacy layout keeps its inline toolbar. */
export function PageToolbar({children}: {children: ReactNode}) {
  const [host,setHost] = useState<HTMLElement|null>(null);
  useEffect(() => {setHost(document.getElementById('ops-page-controls'));},[]);
  return host ? createPortal(children,host) : children;
}
