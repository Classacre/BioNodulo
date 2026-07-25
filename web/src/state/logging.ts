// Structured error logging for the frontend.
//
// Replaces silent `catch { /* offline */ }` patterns with a single
// observable hook so we can see — both in DevTools and (later) in remote
// telemetry — *which* feature swallowed *which* error.
//
// Usage:
//   import { logError } from '../state/logging';
//   try { ... } catch (err) {
//     logError('run.cancel', err);
//     // existing fallback behavior
//   }
//
// Conventions
// -----------
// `scope` is a flat dotted string like `auth.refresh`, `panels.dock.persist`,
// `run.cancel`. Keep it short and stable so a future telemetry sink can
// aggregate. No central enum on purpose — that would require touching this
// file on every site.
//
// The logger is deliberately tiny. No buffering, no batching, no remote
// transport. Add those later in a dedicated telemetry module if/when we
// actually start collecting frontend errors centrally.

export interface LoggedError {
  scope: string;
  message: string;
  name?: string;
  stack?: string;
  timestamp: number;
}

type Listener = (entry: LoggedError) => void;

const listeners = new Set<Listener>();
const ringBuffer: LoggedError[] = [];
const RING_CAPACITY = 200;

function normaliseError(err: unknown): { message: string; name?: string; stack?: string } {
  if (err instanceof Error) {
    const out: { message: string; name?: string; stack?: string } = { message: err.message };
    if (err.name) out.name = err.name;
    if (err.stack) out.stack = err.stack;
    return out;
  }
  if (typeof err === 'string') return { message: err };
  try {
    return { message: JSON.stringify(err) };
  } catch {
    return { message: String(err) };
  }
}

/**
 * Record a swallowed error for later inspection.
 *
 * The error is written to `console.error` (visible in DevTools) and pushed
 * into the in-memory ring buffer that any subscriber can read.
 */
export function logError(scope: string, err: unknown): void {
  const { message, name, stack } = normaliseError(err);
  const entry: LoggedError = {
    scope,
    message,
    timestamp: Date.now(),
    ...(name ? { name } : {}),
    ...(stack ? { stack } : {}),
  };
  ringBuffer.push(entry);
  if (ringBuffer.length > RING_CAPACITY) ringBuffer.shift();
  // Always show in DevTools — silent failures hide real bugs.
  console.error(`[${scope}]`, err);
  for (const listener of listeners) {
    try {
      listener(entry);
    } catch {
      // Listener errors must not feed back into logError.
    }
  }
}

/** Subscribe to future error events. Returns an unsubscribe function. */
export function subscribeErrors(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** Snapshot the recent error ring buffer (most recent last). */
export function recentErrors(): readonly LoggedError[] {
  return ringBuffer.slice();
}

/** Drop the in-memory ring buffer. Mostly useful for tests. */
export function clearRecentErrors(): void {
  ringBuffer.length = 0;
}
