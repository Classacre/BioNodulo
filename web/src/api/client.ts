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

import { getToken, refreshToken } from '../collab/authStorage';
import { appPath } from '../utils/appBase';
import { resolveCollabUrl } from '../collab/remoteBase';

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

  // When no shared-editor override is active, collab paths may target a remote
  // Cloudflare tunnel host (cross-machine rooms). Non-collab paths stay local.
  if (!EDITOR_API_BASE && cleanPath.startsWith('api/collab/')) {
    return resolveCollabUrl(`/${cleanPath}`);
  }

  if (cleanPath.startsWith(`${cleanBase}/`) || cleanPath === cleanBase || cleanPath.startsWith('ws/')) {
    return appPath(cleanPath);
  }
  return appPath(`${cleanBase}/${cleanPath}`);
}

/** Low-level: returns the raw Response after an HTTP-status check. */
export async function apiRequest(path: string, init: ApiRequestInit = {}): Promise<Response> {
  const url = buildUrl(path, init.basePath);
  const { json, body, anonymous, basePath: _b, ...rest } = init;
  const send = () => fetch(url, {
    ...rest,
    headers: buildHeaders(init),
    body: json !== undefined ? JSON.stringify(json) : body,
  });

  let response = await send();

  // Retry a 401 exactly once, after forcing a token refresh.
  //
  // getToken() clears an expired token and returns null, so a request made a
  // second past the ~60s Clerk TTL is sent with NO Authorization header and is
  // rejected. The refresh runs on a 45s interval, which browsers throttle in
  // background tabs, so this window is missed routinely. Without this retry the
  // user is told "Run failed: Unauthorized" for a run that is perfectly fine --
  // observed on run 71c48448, which went on to complete normally.
  //
  // Strictly once, and never for an explicitly anonymous call: a genuine 401
  // must still surface rather than loop.
  if (response.status === 401 && !anonymous) {
    const refreshed = await refreshToken();
    if (refreshed) response = await send();
  }

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
