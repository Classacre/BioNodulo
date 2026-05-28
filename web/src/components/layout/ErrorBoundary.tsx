import { Component, type ReactNode } from 'react';
import { logError } from '../../state/logging';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
  // Optional label that becomes the logging scope ('panel.<name>') and is
  // shown in the default fallback so the user knows which surface failed.
  // Top-level boundaries should always pass a name; the fallback is much
  // more useful when it identifies the surface.
  name?: string;
  // Render a compact fallback that fits inside a panel slot. Defaults to
  // the larger fallback used for the App-root boundary.
  variant?: 'inline' | 'panel';
  // Resets the boundary when one of these values changes — handy when the
  // user navigates away from the broken surface; without this, "Try again"
  // is the only escape hatch.
  resetKeys?: ReadonlyArray<unknown>;
}

interface State {
  hasError: boolean;
  error?: Error;
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  override componentDidUpdate(prev: Props) {
    if (!this.state.hasError) return;
    const prevKeys = prev.resetKeys ?? [];
    const nextKeys = this.props.resetKeys ?? [];
    if (prevKeys.length !== nextKeys.length) {
      this.setState({ hasError: false });
      return;
    }
    for (let i = 0; i < nextKeys.length; i += 1) {
      if (!Object.is(prevKeys[i], nextKeys[i])) {
        this.setState({ hasError: false });
        return;
      }
    }
  }

  override componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    const scope = this.props.name ? `panel.${this.props.name}` : 'panel.unknown';
    logError(scope, error);
    // componentStack lives on errorInfo, not error — keep it visible in
    // DevTools without folding it into the structured log payload.
    // eslint-disable-next-line no-console
    console.error(`[${scope}] componentStack`, errorInfo.componentStack);
  }

  override render() {
    if (!this.state.hasError) return this.props.children;
    if (this.props.fallback !== undefined) return this.props.fallback;

    const variant = this.props.variant ?? 'panel';
    const tryAgain = () => this.setState({ hasError: false });

    if (variant === 'inline') {
      return (
        <div
          role="alert"
          style={{ padding: '6px 10px', fontSize: 12, color: '#b91c1c', background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 4 }}
        >
          <span style={{ fontWeight: 600 }}>{this.props.name ?? 'panel'}</span> crashed:{' '}
          <span>{this.state.error?.message ?? 'unknown error'}</span>{' '}
          <button onClick={tryAgain} style={{ marginLeft: 6, fontSize: 11 }}>retry</button>
        </div>
      );
    }

    return (
      <div role="alert" style={{ padding: 12, color: '#dc2626', fontSize: 12 }}>
        <div style={{ fontWeight: 600 }}>
          {this.props.name ? `${this.props.name} panel crashed` : 'Something went wrong'}
        </div>
        <pre style={{ marginTop: 8, whiteSpace: 'pre-wrap' }}>
          {this.state.error?.message}
        </pre>
        <button
          style={{ marginTop: 8, padding: '4px 12px', cursor: 'pointer' }}
          onClick={tryAgain}
        >
          Try again
        </button>
      </div>
    );
  }
}
