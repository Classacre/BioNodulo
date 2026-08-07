import { describe, expect, it } from 'vitest';
import { resolveAccountUrl } from '../utils/accountUrl';

/**
 * Every deep link in the account menu is built from this, and it was always
 * empty.
 *
 * `accountUrl` came from `BIONODULO_ACCOUNT_URL`, which is set in no
 * environment -- not the editor Lambda, not the desktop backend, nowhere. So
 * `cloudConfig.accountUrl` was null everywhere and every control gated on it
 * rendered nothing: Billing, API keys, Cloud files, and the link fallbacks for
 * Sessions & security / Manage team / Edit profile. Confirmed against the
 * deployed editor: `/api/config` returns `accountUrl: null`.
 *
 * A destination that depends on an environment variable nobody sets is not a
 * destination, so this derives one.
 */
describe('resolving the account site', () => {
  it('uses the configured value when there is one', () => {
    expect(resolveAccountUrl('https://staging.example.com', 'https://cloud.bionodulo.com'))
      .toBe('https://staging.example.com');
  });

  it('trims a trailing slash so links do not double up', () => {
    expect(resolveAccountUrl('https://example.com/', 'https://cloud.bionodulo.com'))
      .toBe('https://example.com');
  });

  it('ignores a blank configured value rather than building "/dashboard/account"', () => {
    expect(resolveAccountUrl('   ', 'https://cloud.bionodulo.com'))
      .toBe('https://bionodulo.com');
  });

  it('derives the site from the editor host', () => {
    // The editor is served from cloud.<domain>; the dashboard lives on the
    // apex. Deriving it means no configuration to forget.
    expect(resolveAccountUrl(null, 'https://cloud.bionodulo.com'))
      .toBe('https://bionodulo.com');
  });

  it('keeps the scheme and port of the host it derived from', () => {
    expect(resolveAccountUrl(null, 'http://cloud.localhost:3000'))
      .toBe('http://localhost:3000');
  });

  it('falls back to production for the desktop app', () => {
    // Desktop runs on tauri://localhost or 127.0.0.1; neither hosts a
    // dashboard, so the real site is the only sensible destination.
    for (const origin of ['tauri://localhost', 'http://127.0.0.1:8000', 'http://localhost:5173']) {
      expect(resolveAccountUrl(null, origin), origin).toBe('https://bionodulo.com');
    }
  });

  it('falls back for a preview deployment that has no cloud. split', () => {
    expect(resolveAccountUrl(null, 'https://bionodulo-abc123.vercel.app'))
      .toBe('https://bionodulo.com');
  });

  it('never returns an empty string', () => {
    // An empty base silently produces relative links to the editor's own
    // origin, which 404 — the failure this whole module exists to prevent.
    for (const origin of ['', 'not a url', 'https://cloud.bionodulo.com']) {
      expect(resolveAccountUrl(null, origin), origin).toMatch(/^https?:\/\/.+/);
    }
  });

  it('only strips a leading cloud. label, not a substring', () => {
    expect(resolveAccountUrl(null, 'https://mycloud.example.com'))
      .toBe('https://bionodulo.com');
  });
});
