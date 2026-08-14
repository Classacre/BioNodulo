// Translucent, non-blocking overlay that narrates the DOI→workflow build:
// each line is one thing the AI just did, so the visitor watches progress
// instead of waiting for nodes to appear.
import type { CSSProperties } from 'react';

const panel: CSSProperties = {
  position: 'fixed',
  right: 20,
  bottom: 20,
  zIndex: 50,
  maxWidth: 340,
  padding: '14px 18px',
  borderRadius: 12,
  background: 'rgba(15, 23, 42, 0.55)',
  backdropFilter: 'blur(10px)',
  WebkitBackdropFilter: 'blur(10px)',
  border: '1px solid rgba(148, 163, 184, 0.25)',
  boxShadow: '0 12px 40px rgba(0,0,0,0.35)',
  color: '#e2e8f0',
  fontSize: 13,
  lineHeight: 1.5,
  pointerEvents: 'none', // never block the canvas
};

const spinner: CSSProperties = {
  display: 'inline-block',
  width: 10,
  height: 10,
  marginRight: 8,
  borderRadius: '50%',
  border: '2px solid rgba(226, 232, 240, 0.35)',
  borderTopColor: '#e2e8f0',
  animation: 'doi-spin 0.8s linear infinite',
};

export function DoiProgressOverlay({ lines }: { lines: string[] }) {
  if (lines.length === 0) return null;
  return (
    <div style={panel} aria-live="polite">
      <style>{'@keyframes doi-spin { to { transform: rotate(360deg); } }'}</style>
      {lines.map((line, i) => {
        const isLast = i === lines.length - 1;
        return (
          <div
            key={`${i}-${line}`}
            style={{ opacity: isLast ? 1 : 0.55, display: 'flex', alignItems: 'center' }}
          >
            {isLast ? <span style={spinner} /> : <span style={{ marginRight: 8 }}>✓</span>}
            <span>{line}</span>
          </div>
        );
      })}
    </div>
  );
}
