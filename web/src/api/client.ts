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

import { getToken } from '../collab/auth';

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

const DEFAULT_BASE = '/api';

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
  if (path.startsWith('/api/') || path.startsWith('/ws/')) return path;
  const normalised = path.startsWith('/') ? path : `/${path}`;
  return `${basePath}${normalised}`;
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
  return JSON.parse(text) as T;
}

/** DELETE <path>, parse JSON response as `T` (or void if empty). */
export async function apiDelete<T = unknown>(path: string, init: ApiRequestInit = {}): Promise<T> {
  const response = await apiRequest(path, { ...init, method: 'DELETE' });
  const text = await response.text();
  if (!text) return undefined as T;
  return JSON.parse(text) as T;
}

/** Fetch raw text response (e.g. exported pipeline scripts). */
export async function apiGetText(path: string, init: ApiRequestInit = {}): Promise<string> {
  const response = await apiRequest(path, { ...init, method: 'GET' });
  return response.text();
}
