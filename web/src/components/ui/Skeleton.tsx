import { useEffect } from 'react';
import type { CSSProperties, JSX } from 'react';

const STYLE_ID = 'bionodulo-ui-skeleton-styles';

const SKELETON_CSS = `
.bn-ui-skeleton {
  position: relative;
  display: inline-block;
  background: var(--surface-2, rgba(148, 163, 184, 0.18));
  border-radius: 4px;
  overflow: hidden;
  vertical-align: middle;
}
.bn-ui-skeleton::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(
    90deg,
    transparent 0%,
    rgba(255, 255, 255, 0.18) 50%,
    transparent 100%
  );
  transform: translateX(-100%);
  animation: bnUiSkeletonShimmer 1.4s ease-in-out infinite;
}
.dark .bn-ui-skeleton::after {
  background: linear-gradient(
    90deg,
    transparent 0%,
    rgba(148, 163, 184, 0.18) 50%,
    transparent 100%
  );
}
@keyframes bnUiSkeletonShimmer {
  100% { transform: translateX(100%); }
}
.bn-ui-skeleton[data-variant="text"] {
  border-radius: 3px;
  height: 0.9em;
}
.bn-ui-skeleton[data-variant="circle"] {
  border-radius: 50%;
}
.bn-ui-skeleton[data-variant="rect"] {
  border-radius: 6px;
}
.bn-ui-skeleton-stack {
  display: flex;
  flex-direction: column;
  gap: 6px;
  width: 100%;
}
@media (prefers-reduced-motion: reduce) {
  .bn-ui-skeleton::after { animation: none; }
}
`;

function ensureSkeletonStyles(): void {
  if (typeof document === 'undefined') return;
  if (document.getElementById(STYLE_ID)) return;
  const style = document.createElement('style');
  style.id = STYLE_ID;
  style.textContent = SKELETON_CSS;
  document.head.appendChild(style);
}

export interface SkeletonProps {
  variant?: 'text' | 'rect' | 'circle';
  width?: number | string;
  height?: number | string;
  className?: string;
  style?: CSSProperties;
}

export function Skeleton({ variant = 'rect', width, height, className, style }: SkeletonProps): JSX.Element {
  useEffect(() => { ensureSkeletonStyles(); }, []);
  const resolved: CSSProperties = {
    width: typeof width === 'number' ? `${width}px` : width,
    height: typeof height === 'number' ? `${height}px` : height,
    ...style,
  };
  return (
    <span
      className={`bn-ui-skeleton ${className ?? ''}`.trim()}
      data-variant={variant}
      style={resolved}
      aria-hidden="true"
    />
  );
}

export interface SkeletonListProps {
  count?: number;
  rowHeight?: number;
  gap?: number;
  widths?: (number | string)[];
  className?: string;
}

export function SkeletonList({ count = 4, rowHeight = 14, gap = 8, widths, className }: SkeletonListProps): JSX.Element {
  useEffect(() => { ensureSkeletonStyles(); }, []);
  return (
    <div className={`bn-ui-skeleton-stack ${className ?? ''}`.trim()} style={{ gap }}>
      {Array.from({ length: count }).map((_, i) => (
        <Skeleton key={i} variant="text" width={widths?.[i] ?? '100%'} height={rowHeight} />
      ))}
    </div>
  );
}

export interface SkeletonCardProps {
  className?: string;
  style?: CSSProperties;
}

export function SkeletonCard({ className, style }: SkeletonCardProps): JSX.Element {
  return (
    <div
      className={className}
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
        padding: 12,
        border: '1px solid var(--border)',
        borderRadius: 8,
        background: 'var(--surface)',
        ...style,
      }}
    >
      <Skeleton variant="rect" width="100%" height={80} />
      <Skeleton variant="text" width="60%" height={12} />
      <Skeleton variant="text" width="90%" height={10} />
      <Skeleton variant="text" width="40%" height={10} />
    </div>
  );
}
