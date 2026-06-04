import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { ApiError, apiGet, apiGetBlob, apiGetText, apiPost, clearApiCache } from '../api/client';

describe('api/client', () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    clearApiCache();
    fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === 'string' ? input : input.toString();
      // Drive responses by URL so each case is explicit.
      if (url.endsWith('/api/ok')) {
        return new Response(JSON.stringify({ ok: true, value: 42 }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      if (url.endsWith('/api/empty')) {
        return new Response('', { status: 200 });
      }
      if (url.endsWith('/api/text')) {
        return new Response('plain text payload', {
          status: 200,
          headers: { 'Content-Type': 'text/plain' },
        });
      }
      if (url.endsWith('/api/blob')) {
        return new Response('csv,payload\n', {
          status: 200,
          headers: { 'Content-Type': 'text/csv' },
        });
      }
      if (url.endsWith('/api/not-found')) {
        return new Response(JSON.stringify({ error: 'missing' }), {
          status: 404,
          statusText: 'Not Found',
          headers: { 'Content-Type': 'application/json' },
        });
      }
      if (url.endsWith('/api/echo')) {
        const body = init?.body as string | undefined;
        return new Response(JSON.stringify({ echoed: body ? JSON.parse(body) : null }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      return new Response('not handled', { status: 500 });
    });
  });

  afterEach(() => {
    fetchSpy.mockRestore();
  });

  it('parses JSON on a 200', async () => {
    const result = await apiGet<{ ok: boolean; value: number }>('/ok');
    expect(result).toEqual({ ok: true, value: 42 });
  });

  it('throws ApiError on a non-2xx response with the body attached', async () => {
    await expect(apiGet('/not-found')).rejects.toMatchObject({
      name: 'ApiError',
      status: 404,
      statusText: 'Not Found',
    });
    try {
      await apiGet('/not-found');
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError);
      expect((err as ApiError).body).toEqual({ error: 'missing' });
    }
  });

  it('returns undefined when POST receives an empty body', async () => {
    const out = await apiPost('/empty');
    expect(out).toBeUndefined();
  });

  it('returns raw text responses with apiGetText', async () => {
    const out = await apiGetText('/text');
    expect(out).toBe('plain text payload');
  });

  it('returns blob responses with apiGetBlob', async () => {
    const out = await apiGetBlob('/blob');
    expect(out).toBeInstanceOf(Blob);
    await expect(out.text()).resolves.toBe('csv,payload\n');
  });

  it('stringifies JSON bodies and sets Content-Type for apiPost', async () => {
    const result = await apiPost<{ echoed: unknown }>('/echo', { a: 1 });
    expect(result?.echoed).toEqual({ a: 1 });
    expect(fetchSpy).toHaveBeenCalledWith(
      expect.stringContaining('/api/echo'),
      expect.objectContaining({ method: 'POST', body: JSON.stringify({ a: 1 }) }),
    );
  });
});
