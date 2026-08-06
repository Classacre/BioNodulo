import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

/**
 * "Sessions and security does nothing, manage team does nothing and edit
 * profile does nothing" — first user report.
 *
 * All three called Clerk, which renders those screens as modals whose UI it
 * fetches at click time. The desktop app's content security policy allows
 * scripts from the app bundle only (`script-src 'self'`), so the fetch is
 * blocked and the click silently does nothing. Widening that policy to admit a
 * remote script host into an app that also launches local processes is a poor
 * trade, so where the modal cannot run the buttons link to the same screens on
 * the website.
 *
 * Asserted against the source because the panel needs Clerk, jotai, i18n and a
 * cloud config to render; what matters is that no branch leaves a control that
 * cannot act.
 */
const source = readFileSync(
  resolve(__dirname, '../components/panels/UserPanel.tsx'),
  'utf8',
);

describe('account actions', () => {
  it('only opens a Clerk modal where Clerk can actually run', () => {
    expect(source).toContain('const modalsAvailable = clerkEnabled && !isDesktopApp()');
  });

  it('offers every action through a link when modals are unavailable', () => {
    for (const link of ['/dashboard/account', '/dashboard/team']) {
      expect(source).toContain(link);
    }
  });

  it('never renders a control with no destination', () => {
    // Each of the three actions must resolve to a modal, a link, or nothing —
    // never a button whose handler cannot fire.
    const actions = ['account.sessions', 'account.manageTeam', 'account.editProfile'];
    for (const action of actions) {
      const at = source.indexOf(action);
      expect(at, action).toBeGreaterThan(-1);
      // Each action sits inside one ternary: modal branch, link branch, null.
      // Take the whole block so both branches are checked, not just the first.
      const guard = source.lastIndexOf('modalsAvailable ?', at);
      expect(guard, `${action} is not guarded by modalsAvailable`).toBeGreaterThan(-1);
      const end = source.indexOf(') : null}', guard);
      expect(end, `${action} has no null branch`).toBeGreaterThan(guard);
      const block = source.slice(guard, end);
      expect(block, `${action} has no link fallback`).toContain('accountLinks');
      expect(block, `${action} label missing from block`).toContain(action);
    }
  });

  it('does not offer account links to a signed-out user', () => {
    // The dashboard would just bounce them to sign-in.
    expect(source).toContain('accountLinks && hasCloudAccount');
  });

  it('keeps the modal path for the browser', () => {
    // The web app can run Clerk's modals and should: they are the better UX.
    expect(source).toContain('onClick={openProfile}');
    expect(source).toContain('onClick={openOrganization}');
  });
});
