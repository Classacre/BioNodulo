import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { CloudRunOutput } from '../types';
import { openVerifiedCloudDownload } from '../utils/cloudOutputDownload';

const runtime = vi.hoisted(() => ({ current: null as { openLink: ReturnType<typeof vi.fn> } | null }));
vi.mock('../mcp/runtime', () => ({ getMcpRuntime: () => runtime.current }));
const output: CloudRunOutput = { key: 'team/run/report.html', name: 'report.html', size: 3 * 1024 * 1024, sha256: 'a'.repeat(64), url: 'https://storage.example/report?signature=fresh' };

describe('verified cloud attachment navigation', () => {
  beforeEach(() => { runtime.current = null; });
  afterEach(() => { vi.restoreAllMocks(); });
  it('opens a body-attached download link for the whole file without fetching or buffering bytes', async () => {
    const fetch = vi.spyOn(globalThis, 'fetch');
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
      expect(this.isConnected).toBe(true);
      expect(this.href).toBe(output.url);
      expect(this.download).toBe('report.html');
      expect(this.rel).toBe('noopener noreferrer');
      expect(this.referrerPolicy).toBe('no-referrer');
    });
    await openVerifiedCloudDownload(output);
    expect(click).toHaveBeenCalledOnce();
    expect(document.querySelector('a[href*="storage.example"]')).toBeNull();
    expect(fetch).not.toHaveBeenCalled();
  });
  it('uses the host link capability for an embedded app', async () => {
    const openLink = vi.fn().mockResolvedValue(undefined); runtime.current = { openLink };
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click');
    await openVerifiedCloudDownload(output);
    expect(openLink).toHaveBeenCalledWith(output.url);
    expect(click).not.toHaveBeenCalled();
  });
  it('uses a filename rather than a path and removes control characters', async () => {
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
      expect(this.download).toBe('résumé.html');
    });
    await openVerifiedCloudDownload({ ...output, name: `folder/résumé${String.fromCharCode(10)}.html` });
  });
  it.each(['javascript:alert(1)', 'http://storage.example/file', 'https://user:secret@storage.example/file'])('rejects an unsafe link: %s', async url => {
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click');
    await expect(openVerifiedCloudDownload({ ...output, url })).rejects.toThrow('Only HTTPS');
    expect(click).not.toHaveBeenCalled();
  });
  it('removes the temporary link even if the browser rejects activation', async () => {
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => { throw new Error('Blocked'); });
    await expect(openVerifiedCloudDownload(output)).rejects.toThrow('Blocked');
    expect(document.querySelector('a[href*="storage.example"]')).toBeNull();
  });
});
