import { useLayoutEffect, useRef, type ReactNode } from 'react';

/** Suspend presentation without losing a panel's unsent work or open intent. */
export default function ConsolePanelSlot({ suspended, children }: { suspended: boolean; children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    const focused = document.activeElement;
    if (suspended && focused instanceof HTMLElement && ref.current?.contains(focused)) {
      focused.blur();
      document.querySelector<HTMLElement>('.bottom-console')?.focus();
    }
  }, [suspended]);
  return <div ref={ref} className={`console-panel-slot${suspended ? ' is-suspended' : ''}`}
    data-console-panel inert={suspended} aria-hidden={suspended || undefined}>{children}</div>;
}
