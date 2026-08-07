import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

/**
 * "Sessions and security does nothing, manage team does nothing and edit
 * profile does nothing." Reported twice, because the first fix addressed only
 * half of it.
 *
 * Clerk's modal has never worked in EITHER place it can run:
 *   - desktop: the Tauri CSP is `script-src 'self'`, so Clerk's UI fetch is
 *     blocked and the click silently does nothing.
 *   - browser: the SPA bundles @clerk/clerk-js itself and the UI chunks are
 *     not there, so `openUserProfile()` throws "Clerk was not loaded with Ui
 *     components". Observed on the deployed editor.
 *
 * The first fix added a link fallback for desktop, but gated it on
 * `accountUrl`, which comes from `BIONODULO_ACCOUNT_URL` -- set in no
 * environment. So the fallback rendered nothing and the browser kept throwing.
 *
 * There is now one path: link to the website, which renders these exact screens
 * correctly (verified live), with a destination that is derived rather than
 * configured. Asserted against the source because the panel needs Clerk, jotai,
 * i18n and a cloud config to render; what matters is that no branch leaves a
 * control that cannot act.
 */
const source = readFileSync(
  resolve(__dirname, '../components/panels/UserPanel.tsx'),
  'utf8',
);

const ACTIONS = ['account.sessions', 'account.manageTeam', 'account.editProfile'];

describe('account actions', () => {
  it('does not open a Clerk modal anywhere', () => {
    // It throws in the browser and is CSP-blocked in desktop. One working path
    // beats two broken ones.
    expect(source).not.toContain('onClick={openProfile}');
    expect(source).not.toContain('onClick={openOrganization}');
    expect(source).not.toContain('modalsAvailable');
  });

  it('sends every action to a real page', () => {
    for (const link of ['/dashboard/account', '/dashboard/team']) {
      expect(source).toContain(link);
    }
  });

  it('renders each action as a link, not a button', () => {
    // A button whose handler cannot fire is exactly what was reported. An
    // anchor with an href either navigates or is visibly broken.
    for (const action of ACTIONS) {
      const at = source.indexOf(action);
      expect(at, action).toBeGreaterThan(-1);

      // The enclosing element is whichever of <a / <button opens last before
      // the label. (<Icon …> sits between them, so "the previous tag" is not it.)
      const anchor = source.lastIndexOf('<a ', at);
      const button = source.lastIndexOf('<button', at);
      expect(anchor, `${action} is not inside an anchor`).toBeGreaterThan(button);
    }
  });

  it('gives every action an href', () => {
    for (const action of ACTIONS) {
      const at = source.indexOf(action);
      const anchor = source.lastIndexOf('<a ', at);
      expect(source.slice(anchor, at), action).toContain('href={');
    }
  });

  it('does not offer account links to a signed-out user', () => {
    // The dashboard would just bounce them to sign-in.
    expect(source).toContain('hasCloudAccount');
  });

  it('never depends on an unset environment variable for a destination', () => {
    // `accountUrl` was null in every environment. The panel must resolve one.
    expect(source).toContain('accountUrlFrom');
  });

  it('still shows the dashboard deep links', () => {
    // Billing, API keys and Cloud files were gated on the same null value, so
    // that whole section was empty in production too.
    for (const link of ['/dashboard/billing', '/dashboard/settings', '/dashboard/files']) {
      expect(source).toContain(link);
    }
  });

  it('opens the website in a new tab without leaking the opener', () => {
    for (const [i, block] of source.split('<a ').entries()) {
      if (i === 0 || !block.includes('accountUrl')) continue;
      expect(block).toContain('target="_blank"');
      expect(block).toContain('rel="noopener noreferrer"');
    }
  });
});
