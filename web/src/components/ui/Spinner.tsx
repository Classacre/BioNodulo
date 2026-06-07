import { useEffect } from 'react';
import type { CSSProperties, ReactElement } from 'react';
import i18n from '../../i18n';

const STYLE_ID = 'bionodulo-ui-spinner-styles';

const SPINNER_CSS = `
.bn-ui-spinner {
  display: inline-block;
  vertical-align: middle;
  border-radius: 50%;
  border-style: solid;
  border-color: currentColor;
  border-top-color: transparent;
  animation: bnUiSpinnerSpin 0.7s linear infinite;
  flex-shrink: 0;
}
@keyframes bnUiSpinnerSpin {
  to { transform: rotate(360deg); }
}
@media (prefers-reduced-motion: reduce) {
  .bn-ui-spinner { animation-duration: 1.4s; }
}
`;

function ensureSpinnerStyles(): void {
  if (typeof document === 'undefined') return;
  if (document.getElementById(STYLE_ID)) return;
  const style = document.createElement('style');
  style.id = STYLE_ID;
  style.textContent = SPINNER_CSS;
  document.head.appendChild(style);
}

const SIZES = { sm: 12, md: 16, lg: 22, xl: 32 } as const;
const STROKES = { sm: 2, md: 2, lg: 2.5, xl: 3 } as const;

export interface SpinnerProps {
  size?: keyof typeof SIZES | number;
  /** Override the inherited colour (rare). */
  color?: string;
  className?: string;
  style?: CSSProperties;
  /** Accessible label; defaults to the active locale's generic loading label. */
  label?: string;
}

export function Spinner({ size = 'md', color, className, style, label }: SpinnerProps): ReactElement {
  useEffect(() => { ensureSpinnerStyles(); }, []);
  const dimension = typeof size === 'number' ? size : SIZES[size];
  const stroke = typeof size === 'number' ? Math.max(1.5, dimension / 8) : STROKES[size];
  return (
    <span
      role="status"
      aria-live="polite"
      aria-label={label ?? i18n.t('common.loading')}
      className={`bn-ui-spinner ${className ?? ''}`.trim()}
      style={{
        width: dimension,
        height: dimension,
        borderWidth: stroke,
        color: color ?? 'currentColor',
        ...style,
      }}
    />
  );
}
