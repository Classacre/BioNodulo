import { Component, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
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

  override componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('[ErrorBoundary]', error, errorInfo);
  }

  override render() {
    if (this.state.hasError) {
      return this.props.fallback || (
        <div style={{ padding: 12, color: '#dc2626', fontSize: 12 }}>
          <div style={{ fontWeight: 600 }}>Something went wrong:</div>
          <pre style={{ marginTop: 8, whiteSpace: 'pre-wrap' }}>
            {this.state.error?.message}
          </pre>
          <button
            style={{ marginTop: 8, padding: '4px 12px', cursor: 'pointer' }}
            onClick={() => this.setState({ hasError: false })}
          >
            Try again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
