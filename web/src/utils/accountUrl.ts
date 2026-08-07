/**
 * Where the account/dashboard site lives.
 *
 * Every deep link in the account menu is built from this, and it used to come
 * only from `BIONODULO_ACCOUNT_URL` -- an environment variable set in no
 * environment. So it was null everywhere, and every control gated on it
 * rendered nothing at all: Billing, API keys, Cloud files, and the link
 * fallbacks for Sessions & security / Manage team / Edit profile. A destination
 * that depends on configuration nobody sets is not a destination, so this
 * derives one and treats the config value as an override.
 */

/** Where the dashboard actually is when nothing better can be worked out. */
const PRODUCTION_SITE = 'https://bionodulo.com';

/** The editor is served from `cloud.<domain>`; the dashboard is on the apex. */
const EDITOR_HOST_LABEL = 'cloud.';

export function resolveAccountUrl(
  configured: string | null | undefined,
  origin: string,
): string {
  const explicit = (configured ?? '').trim().replace(/\/+$/, '');
  if (explicit) return explicit;

  try {
    const url = new URL(origin);
    if (url.hostname.startsWith(EDITOR_HOST_LABEL)) {
      url.hostname = url.hostname.slice(EDITOR_HOST_LABEL.length);
      // Keeps the scheme and port, so a non-production split still resolves.
      return url.origin;
    }
  } catch {
    // Not a URL (the desktop app's origin, mainly). Fall through.
  }

  // Desktop, local dev and preview deployments all host no dashboard of their
  // own, so production is the only address that answers.
  return PRODUCTION_SITE;
}

/** Convenience for components: resolves against the current browser origin. */
export function accountUrlFrom(configured: string | null | undefined): string {
  const origin =
    typeof window !== 'undefined' && window.location ? window.location.origin : '';
  return resolveAccountUrl(configured, origin);
}
