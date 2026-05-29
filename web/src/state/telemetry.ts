// Lightweight opt-in telemetry hooks.
//
// This is *local-only* — no network calls, no third party — designed to give
// power users (and our own dev/debug sessions) a structured event trail so
// they can answer "what happened in the last 5 minutes before that bug?".
//
// Events live in a ring buffer (default 200 entries) and only enter the
// buffer when the `bionodulo.telemetry.enabled` setting is on. Disable is
// the default. Toggling on writes a `telemetry.enabled` event so a future
// log dump shows when the user opted in.
//
// Consumers should call `logTelemetry(event, detail?)` instead of ad-hoc
// console.log so the events can be exported / reviewed coherently.

const STORAGE_ENABLED_KEY = 'bionodulo.telemetry.enabled';
const STORAGE_BUFFER_KEY = 'bionodulo.telemetry.buffer';
const MAX_EVENTS = 200;

export interface TelemetryEvent {
  ts: number;
  event: string;
  detail?: Record<string, unknown>;
}

type Listener = (events: readonly TelemetryEvent[]) => void;
const listeners = new Set<Listener>();
let cachedEnabled: boolean | undefined;
let buffer: TelemetryEvent[] = [];
let bufferLoaded = false;

function loadEnabled(): boolean {
  if (cachedEnabled !== undefined) return cachedEnabled;
  if (typeof localStorage === 'undefined') return false;
  try {
    const raw = localStorage.getItem(STORAGE_ENABLED_KEY);
    cachedEnabled = raw === '1' || raw === 'true';
  } catch {
    cachedEnabled = false;
  }
  return cachedEnabled;
}

function loadBuffer(): void {
  if (bufferLoaded) return;
  bufferLoaded = true;
  if (typeof localStorage === 'undefined') return;
  try {
    const raw = localStorage.getItem(STORAGE_BUFFER_KEY);
    if (!raw) return;
    const parsed = JSON.parse(raw) as unknown;
    if (Array.isArray(parsed)) buffer = parsed.slice(-MAX_EVENTS) as TelemetryEvent[];
  } catch {
    /* corrupted buffer — start fresh */
  }
}

function persistBuffer(): void {
  if (typeof localStorage === 'undefined') return;
  try {
    localStorage.setItem(STORAGE_BUFFER_KEY, JSON.stringify(buffer));
  } catch {
    /* quota — drop the oldest half and try again */
    buffer = buffer.slice(Math.floor(buffer.length / 2));
    try { localStorage.setItem(STORAGE_BUFFER_KEY, JSON.stringify(buffer)); } catch { /* give up */ }
  }
}

export function isTelemetryEnabled(): boolean {
  return loadEnabled();
}

export function setTelemetryEnabled(value: boolean): void {
  cachedEnabled = value;
  if (typeof localStorage !== 'undefined') {
    try { localStorage.setItem(STORAGE_ENABLED_KEY, value ? '1' : '0'); } catch { /* ignore */ }
  }
  // Record the toggle itself so the audit trail is self-documenting.
  loadBuffer();
  buffer.push({ ts: Date.now(), event: 'telemetry.toggle', detail: { enabled: value } });
  if (buffer.length > MAX_EVENTS) buffer = buffer.slice(-MAX_EVENTS);
  persistBuffer();
  listeners.forEach(listener => listener(buffer));
}

export function logTelemetry(event: string, detail?: Record<string, unknown>): void {
  if (!loadEnabled()) return;
  loadBuffer();
  buffer.push({ ts: Date.now(), event, detail });
  if (buffer.length > MAX_EVENTS) buffer = buffer.slice(-MAX_EVENTS);
  persistBuffer();
  listeners.forEach(listener => listener(buffer));
}

export function getTelemetryEvents(): readonly TelemetryEvent[] {
  loadBuffer();
  return buffer.slice();
}

export function clearTelemetry(): void {
  buffer = [];
  if (typeof localStorage !== 'undefined') {
    try { localStorage.removeItem(STORAGE_BUFFER_KEY); } catch { /* ignore */ }
  }
  listeners.forEach(listener => listener(buffer));
}

export function exportTelemetryAsText(): string {
  loadBuffer();
  return buffer.map(event => {
    const detail = event.detail ? ' ' + JSON.stringify(event.detail) : '';
    return `${new Date(event.ts).toISOString()} ${event.event}${detail}`;
  }).join('\n');
}

export function subscribeTelemetry(listener: Listener): () => void {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}
