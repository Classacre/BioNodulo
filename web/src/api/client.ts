// Centralised typed wrapper around fetch for `/api/*` endpoints.
//
// Replaces hand-rolled `fetch('/api/foo', { method, headers, body })` calls so
// that:
//   - error handling is consistent (HTTP status -> `ApiError`, no silent JSON
//     parsing of error bodies)
//   - headers (Content-Type, Authorization) are set once
//   - the base URL can be overridden from a single place if the API ever moves
//
// This module deliberately stays small — no global cache, no automatic retry,
// no auto-toast. Add those in domain hooks if/when they actually become
// needed.

import { getToken } from '../collab/authStorage';
import { appPath } from '../utils/appBase';

export interface ApiRequestInit extends Omit<RequestInit, 'body' | 'headers'> {
  /** Plain JSON body — automatically stringified and Content-Type'd. */
  json?: unknown;
  /** Pre-serialised body for non-JSON payloads (FormData, Blob, etc.). */
  body?: BodyInit;
  /** Additional headers to merge with the defaults. */
  headers?: Record<string, string>;
  /** Skip the auth header even when a token is available. */
  anonymous?: boolean;
  /** Override the base path (defaults to `/api`). */
  basePath?: string;
}

export class ApiError extends Error {
  readonly status: number;
  readonly statusText: string;
  readonly body: unknown;

  constructor(message: string, status: number, statusText: string, body: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.statusText = statusText;
    this.body = body;
  }
}

const DEFAULT_BASE = 'api';

// Shared-editor (serverless) deployment: the static SPA calls a different
// origin/path for the editing-support API than for its own static assets.
// VITE_EDITOR_API_BASE (e.g. "/api/editor") reroutes the default `/api/*`
// editing calls to the shared editing backend. Unset (self-host / per-user
// container) => empty => calls stay relative to the app's own origin (current
// behaviour). Persistence/runs use the website root API directly (see
// api/website.ts), not this client.
const EDITOR_API_BASE = (import.meta.env.VITE_EDITOR_API_BASE || '').replace(/\/+$/, '');

async function readErrorBody(response: Response): Promise<unknown> {
  const contentType = response.headers.get('Content-Type') || '';
  try {
    if (contentType.includes('application/json')) return await response.json();
    const text = await response.text();
    return text || null;
  } catch {
    return null;
  }
}

function buildHeaders(init: ApiRequestInit): Headers {
  const headers = new Headers(init.headers ?? {});
  if (init.json !== undefined && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  if (!init.anonymous) {
    const token = getToken();
    if (token && !headers.has('Authorization')) {
      headers.set('Authorization', `Bearer ${token}`);
    }
  }
  return headers;
}

function buildUrl(path: string, basePath = DEFAULT_BASE): string {
  if (path.startsWith('http://') || path.startsWith('https://')) return path;
  const cleanPath = path.replace(/^\/+/, '');
  const cleanBase = basePath.replace(/^\/+|\/+$/g, '');

  // Shared editor: reroute the default `/api/*` editing calls to the editing
  // backend base (absolute from origin root, NOT prefixed by appBasePath, since
  // the static SPA's base path is unrelated to where the API lives). The editing
  // backend serves its routes UNDER /api, and the proxy forwards
  // /api/editor/<subpath> -> backend /<subpath>, so we must KEEP the api prefix:
  //   apiGet('/object_info') -> /api/editor/api/object_info -> backend /api/object_info
  // WebSocket paths are excluded (collab is disabled in editor mode anyway).
  if (EDITOR_API_BASE && cleanBase === DEFAULT_BASE && !cleanPath.startsWith('ws/')) {
    const apiPrefixed =
      cleanPath === cleanBase || cleanPath.startsWith(`${cleanBase}/`)
        ? cleanPath
        : `${cleanBase}/${cleanPath}`;
    return `${EDITOR_API_BASE}/${apiPrefixed}`;
  }

  if (cleanPath.startsWith(`${cleanBase}/`) || cleanPath === cleanBase || cleanPath.startsWith('ws/')) {
    return appPath(cleanPath);
  }
  return appPath(`${cleanBase}/${cleanPath}`);
}

/** Low-level: returns the raw Response after an HTTP-status check. */
export async function apiRequest(path: string, init: ApiRequestInit = {}): Promise<Response> {
  const url = buildUrl(path, init.basePath);
  const headers = buildHeaders(init);
  const { json, body, anonymous: _a, basePath: _b, ...rest } = init;
  const response = await fetch(url, {
    ...rest,
    headers,
    body: json !== undefined ? JSON.stringify(json) : body,
  });
  if (!response.ok) {
    const errorBody = await readErrorBody(response);
    throw new ApiError(
      `HTTP ${response.status} ${response.statusText} (${url})`,
      response.status,
      response.statusText,
      errorBody,
    );
  }
  return response;
}

/** GET <path>, parse JSON response as `T`. */
export async function apiGet<T = unknown>(path: string, init: ApiRequestInit = {}): Promise<T> {
  const response = await apiRequest(path, { ...init, method: 'GET' });
  return response.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Lightweight in-memory cache for read-heavy endpoints. Use sparingly: the
// cache lives for the lifetime of the page, has no eviction beyond TTL, and
// doesn't follow auth changes. Suitable for things like /object_info or
// /environments which barely change during a session.
// ---------------------------------------------------------------------------

interface CacheEntry<T> {
  /** Present only once a fetch has RESOLVED. Absent for an in-flight-only entry
   *  with no prior cached value, so a stale read can never surface `undefined`. */
  value?: T;
  hasValue: boolean;
  expiresAt: number;
  inFlight?: Promise<T>;
}

const responseCache = new Map<string, CacheEntry<unknown>>();

export interface CachedGetOptions extends ApiRequestInit {
  /** Cache TTL in ms. Defaults to 30s. */
  ttl?: number;
  /** Custom cache key (defaults to `<METHOD> <path>`). */
  cacheKey?: string;
  /** Force a fresh fetch and overwrite the cache entry. */
  force?: boolean;
}

export async function apiGetCached<T = unknown>(path: string, options: CachedGetOptions = {}): Promise<T> {
  const { ttl = 30_000, cacheKey, force, ...init } = options;
  const key = cacheKey || `GET ${path}`;
  const now = Date.now();
  const cached = responseCache.get(key) as CacheEntry<T> | undefined;
  if (!force && cached) {
    // If a request is already in flight, deduplicate concurrent callers.
    if (cached.inFlight) return cached.inFlight;
    // Only return a genuinely resolved, unexpired value.
    if (cached.hasValue && cached.expiresAt > now) return cached.value as T;
  }
  const inFlight = apiGet<T>(path, init).then(value => {
    responseCache.set(key, { value, hasValue: true, expiresAt: Date.now() + ttl });
    return value;
  }).catch(err => {
    // Failed fetches should not poison the cache.
    responseCache.delete(key);
    throw err;
  });
  // Preserve any prior resolved value for stale-while-revalidate reads, but do
  // NOT invent a value when there was none — keep hasValue false so a concurrent
  // reader can't be handed `undefined` as if it were data.
  responseCache.set(key, {
    value: cached?.value,
    hasValue: cached?.hasValue ?? false,
    expiresAt: cached?.expiresAt ?? 0,
    inFlight,
  });
  return inFlight;
}

export function clearApiCache(predicate?: (key: string) => boolean): void {
  if (!predicate) {
    responseCache.clear();
    return;
  }
  for (const key of Array.from(responseCache.keys())) {
    if (predicate(key)) responseCache.delete(key);
  }
}

/** POST <path>, optionally with JSON body, parse JSON response as `T`. */
export async function apiPost<T = unknown>(
  path: string,
  json?: unknown,
  init: ApiRequestInit = {},
): Promise<T> {
  const response = await apiRequest(path, { ...init, method: 'POST', json });
  // Some POSTs (e.g. /history/clear) intentionally return no body — guard
  // against parse errors on empty responses.
  const text = await response.text();
  if (!text) return undefined as T;
  try {
    return JSON.parse(text) as T;
  } catch {
    return undefined as T;
  }
}

/** PUT <path>, parse JSON response as `T`. */
export async function apiPut<T = unknown>(
  path: string,
  json?: unknown,
  init: ApiRequestInit = {},
): Promise<T> {
  const response = await apiRequest(path, { ...init, method: 'PUT', json });
  const text = await response.text();
  if (!text) return undefined as T;
  // Guard non-JSON 2xx bodies (e.g. "OK") like apiPost, rather than throwing a
  // raw SyntaxError.
  try {
    return JSON.parse(text) as T;
  } catch {
    return undefined as T;
  }
}

/** DELETE <path>, parse JSON response as `T` (or void if empty). */
export async function apiDelete<T = unknown>(path: string, init: ApiRequestInit = {}): Promise<T> {
  const response = await apiRequest(path, { ...init, method: 'DELETE' });
  const text = await response.text();
  if (!text) return undefined as T;
  try {
    return JSON.parse(text) as T;
  } catch {
    return undefined as T;
  }
}

/** Fetch raw text response (e.g. exported pipeline scripts). */
export async function apiGetText(path: string, init: ApiRequestInit = {}): Promise<string> {
  const response = await apiRequest(path, { ...init, method: 'GET' });
  return response.text();
}

/** Fetch raw Blob response (e.g. downloadable exports). */
export async function apiGetBlob(path: string, init: ApiRequestInit = {}): Promise<Blob> {
  const response = await apiRequest(path, { ...init, method: 'GET' });
  return response.blob();
}
