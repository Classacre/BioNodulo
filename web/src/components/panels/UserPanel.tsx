import { useEffect, useState } from 'react';
import { useAtomValue, useSetAtom } from 'jotai';
import { useTranslation } from 'react-i18next';
import { accountUrlFrom } from '../../utils/accountUrl';
import Icon from '../ui/Icon';
import { authUserAtom, cloudConfigAtom, showAuthDialogAtom } from '../../state/appAtoms';
import { showInviteDialogAtom } from '../../state/uiAtoms';
import { getCloudCredits, getCurrentUser, type CloudUser } from '../../api/website';
import { useClerkAuth } from '../../hooks/cloud/useClerkAuth';
import { useDesktopAuth } from '../../hooks/cloud/useDesktopAuth';
import { signOutOAuth } from '../../hooks/cloud/desktopOAuth';
import { isGuestUser } from '../../collab/authStorage';

interface UserPanelProps {
  onClose: () => void;
}

/**
 * Account menu in the editor's left rail. It is the local sign-in entry point
 * AND the signed-in account hub. It deliberately reuses what already exists:
 *   - identity/plan/credits from /api/config + /api/me + /api/billing/credits
 *   - profile edit + session/device management via Clerk's hosted UserProfile
 *   - team members/roles via Clerk's hosted OrganizationProfile
 *   - billing + API keys deep-link into the managed cloud dashboard
 * so no bespoke account/session/billing UI is reinvented here.
 */
export default function UserPanel({ onClose }: UserPanelProps) {
  const { t } = useTranslation();
  const cloudConfig = useAtomValue(cloudConfigAtom);
  const authUser = useAtomValue(authUserAtom);
  const openInvite = useSetAtom(showInviteDialogAtom);
  const { clerkEnabled, clerkSignedIn, openSignIn, signOut } = useClerkAuth();
  const { pending: desktopPending, available: oauthAvailable, signInViaBrowser, cancel: cancelDesktopSignIn } = useDesktopAuth();

  const setShowAuthDialog = useSetAtom(showAuthDialogAtom);
  const configUser = cloudConfig?.user ?? null;
  const guest = isGuestUser(authUser) && !configUser && !clerkSignedIn;

  // Every account action links to the website. Clerk's modal has never worked
  // in either environment: the desktop CSP is `script-src 'self'`, so its UI
  // fetch is blocked and the click silently does nothing, and in the browser
  // the SPA bundles clerk-js without the UI chunks, so `openUserProfile()`
  // throws "Clerk was not loaded with Ui components". The website renders these
  // exact screens properly, which is also how billing, API keys and cloud files
  // already work.
  //
  // The destination is derived, not configured: it used to come only from
  // `BIONODULO_ACCOUNT_URL`, set in no environment, so it was null everywhere
  // and every control gated on it rendered nothing at all.
  const accountUrl = accountUrlFrom(cloudConfig?.accountUrl);
  const accountLinks = {
    account: `${accountUrl}/dashboard/account`,
    team: `${accountUrl}/dashboard/team`,
  };
  const hasCloudAccount = Boolean(configUser) || clerkSignedIn || (Boolean(authUser) && !isGuestUser(authUser));

  // /api/me fills in email + team for a local Clerk sign-in (where /api/config
  // has no injected identity). Best-effort; the panel renders without it.
  const [me, setMe] = useState<CloudUser | null>(null);
  useEffect(() => {
    if (!hasCloudAccount) { setMe(null); return; }
    let active = true;
    getCurrentUser().then(u => { if (active) setMe(u); }).catch(() => { /* degrade */ });
    return () => { active = false; };
  }, [hasCloudAccount]);

  const [credits, setCredits] = useState<{ remaining: number; total: number } | null>(
    cloudConfig?.credits && cloudConfig.credits.remaining != null
      ? { remaining: cloudConfig.credits.remaining, total: cloudConfig.credits.total ?? 0 }
      : null,
  );
  useEffect(() => {
    if (!hasCloudAccount) { setCredits(null); return; }
    let active = true;
    getCloudCredits().then(c => { if (active && c) setCredits({ remaining: c.remaining, total: c.monthlyCredits }); }).catch(() => { /* keep seeded */ });
    return () => { active = false; };
  }, [hasCloudAccount]);

  const name = configUser?.name || me?.name || authUser?.name || null;
  const email = configUser?.email || me?.email || null;
  const teamName = me?.team?.name || cloudConfig?.team?.name || null;
  const plan = cloudConfig?.plan ?? null;
  const planLabel = plan ? plan.charAt(0).toUpperCase() + plan.slice(1) : t('account.planFree', { defaultValue: 'Free' });

  const header = (
    <div className="rail-panel-header">
      <span>{t('account.title', { defaultValue: 'Account' })}</span>
      <button className="btn btn-icon" onClick={onClose} title={t('common.close')} aria-label={t('common.close')}>
        <Icon name="close" size={14} />
      </button>
    </div>
  );

  // ---- Signed-out ---------------------------------------------------------
  if (!hasCloudAccount && !guest) {
    return (
      <div className="rail-panel">
        {header}
        <div className="rail-panel-body" style={{ display: 'flex', flexDirection: 'column', gap: 14, padding: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div className="account-avatar account-avatar-empty"><Icon name="user" size={20} /></div>
            <div style={{ minWidth: 0 }}>
              <div style={{ fontWeight: 600 }}>{t('account.signedOutTitle', { defaultValue: 'Not signed in' })}</div>
              <div style={{ fontSize: 12, color: 'var(--muted)' }}>{t('account.signedOutHint', { defaultValue: 'Sign in to run on the cloud and sync files.' })}</div>
            </div>
          </div>
          <button className="btn btn-primary" onClick={() => setShowAuthDialog(true)}>
            <Icon name="user" size={14} /> {t('account.setNameAction', { defaultValue: 'Set a display name' })}
          </button>
          {clerkEnabled ? (
            <button className="btn btn-primary" onClick={openSignIn}>
              <Icon name="user" size={14} /> {t('account.signIn', { defaultValue: 'Sign in to BioNodulo Cloud' })}
            </button>
          ) : oauthAvailable ? (
            desktopPending ? (
              <>
                <div style={{ fontSize: 12, color: 'var(--muted)' }}>
                  {t('account.waitingBrowser', { defaultValue: 'Waiting for sign-in in your browser…' })}
                </div>
                <button className="btn" onClick={cancelDesktopSignIn}>
                  <Icon name="close" size={14} /> {t('common.cancel', { defaultValue: 'Cancel' })}
                </button>
              </>
            ) : (
              <>
                <button className="btn btn-primary" onClick={signInViaBrowser}>
                  <Icon name="link" size={14} /> {t('account.signInBrowser', { defaultValue: 'Sign in with browser' })}
                </button>
                <div style={{ fontSize: 12, color: 'var(--muted)' }}>
                  {t('account.signInBrowserHint', { defaultValue: 'Opens BioNodulo Cloud to sign in, then returns here.' })}
                </div>
              </>
            )
          ) : (
            <div style={{ fontSize: 12, color: 'var(--muted)' }}>
              {t('account.cloudUnavailable', { defaultValue: 'BioNodulo Cloud is not available in this build.' })}
            </div>
          )}
        </div>
      </div>
    );
  }

  // ---- Guest --------------------------------------------------------------
  if (guest) {
    return (
      <div className="rail-panel">
        {header}
        <div className="rail-panel-body" style={{ display: 'flex', flexDirection: 'column', gap: 14, padding: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div className="account-avatar">{(authUser?.name || '?').charAt(0).toUpperCase()}</div>
            <div style={{ minWidth: 0 }}>
              <div style={{ fontWeight: 600 }}>{t('account.guestTitle', { defaultValue: 'Signed in as guest' })}</div>
              <div style={{ fontSize: 12, color: 'var(--muted)' }}>{authUser?.name}</div>
            </div>
          </div>
          {clerkEnabled ? (
            <button className="btn btn-primary" onClick={openSignIn}>
              <Icon name="user" size={14} /> {t('account.signIn', { defaultValue: 'Sign in to BioNodulo Cloud' })}
            </button>
          ) : oauthAvailable ? (
            <button className="btn btn-primary" onClick={signInViaBrowser}>
              <Icon name="link" size={14} /> {t('account.signInBrowser', { defaultValue: 'Sign in with browser' })}
            </button>
          ) : null}
          <button className="btn" onClick={() => setShowAuthDialog(true)}>
            <Icon name="edit" size={14} /> {t('account.changeName', { defaultValue: 'Change name' })}
          </button>
          <button className="btn account-signout" onClick={() => signOutOAuth()}>
            <Icon name="export" size={14} /> {t('account.signOut', { defaultValue: 'Sign out' })}
          </button>
        </div>
      </div>
    );
  }

  // ---- Signed-in ----------------------------------------------------------
  const initial = (name || email || '?').trim().charAt(0).toUpperCase();
  return (
    <div className="rail-panel">
      {header}
      <div className="rail-panel-body account-body">
        {/* User info */}
        <section className="account-section">
          <div className="account-identity">
            <div className="account-avatar">{initial}</div>
            <div style={{ minWidth: 0 }}>
              <div className="account-name">{name || t('account.signedIn', { defaultValue: 'Signed in' })}</div>
              {email && <div className="account-sub">{email}</div>}
              {teamName && <div className="account-sub">{t('account.team', { defaultValue: 'Team' })}: {teamName}</div>}
            </div>
          </div>
        </section>

        {/* Cloud info + plan/credits */}
        <section className="account-section">
          <h4 className="account-heading">{t('account.cloud', { defaultValue: 'Cloud' })}</h4>
          <div className="account-row"><span>{t('account.plan', { defaultValue: 'Plan' })}</span><span className="account-strong">{planLabel}</span></div>
          <div className="account-row"><span>{t('account.credits', { defaultValue: 'Credits' })}</span><span className="account-strong">{credits ? `${credits.remaining.toLocaleString()} / ${credits.total.toLocaleString()}` : '—'}</span></div>
          {hasCloudAccount && (
            <a className="btn btn-sm account-action" href={accountLinks.account} target="_blank" rel="noopener noreferrer">
              <Icon name="lock" size={13} /> {t('account.sessions', { defaultValue: 'Sessions & security' })} <Icon name="link" size={11} />
            </a>
          )}
        </section>

        {/* Team */}
        <section className="account-section">
          <h4 className="account-heading">{t('account.teamHeading', { defaultValue: 'Team' })}</h4>
          {hasCloudAccount && (
            <a className="btn btn-sm account-action" href={accountLinks.team} target="_blank" rel="noopener noreferrer">
              <Icon name="users" size={13} /> {t('account.manageTeam', { defaultValue: 'Manage team' })} <Icon name="link" size={11} />
            </a>
          )}
          <button className="btn btn-sm account-action" onClick={() => openInvite(true)}>
            <Icon name="users" size={13} /> {t('account.invite', { defaultValue: 'Invite collaborator' })}
          </button>
        </section>

        {/* Billing + API keys + files (managed in the dashboard) */}
        <section className="account-section">
          <h4 className="account-heading">{t('account.manageHeading', { defaultValue: 'Manage' })}</h4>
          {/* Was gated on the same null accountUrl, so this whole section was
              empty in production. */}
          {hasCloudAccount && (
            <>
              <a className="btn btn-sm account-action" href={`${accountUrl}/dashboard/billing`} target="_blank" rel="noopener noreferrer">
                <Icon name="activity" size={13} /> {t('account.billing', { defaultValue: 'Billing & usage' })} <Icon name="link" size={11} />
              </a>
              <a className="btn btn-sm account-action" href={`${accountUrl}/dashboard/settings`} target="_blank" rel="noopener noreferrer">
                <Icon name="lock" size={13} /> {t('account.apiKeys', { defaultValue: 'API keys' })} <Icon name="link" size={11} />
              </a>
              <a className="btn btn-sm account-action" href={`${accountUrl}/dashboard/files`} target="_blank" rel="noopener noreferrer">
                <Icon name="folder" size={13} /> {t('account.cloudFiles', { defaultValue: 'Cloud files' })} <Icon name="link" size={11} />
              </a>
            </>
          )}
        </section>

        {/* Profile + sign out */}
        <section className="account-section">
          {hasCloudAccount && (
            <a className="btn btn-sm account-action" href={accountLinks.account} target="_blank" rel="noopener noreferrer">
              <Icon name="user" size={13} /> {t('account.editProfile', { defaultValue: 'Edit profile' })} <Icon name="link" size={11} />
            </a>
          )}
          <button
            className="btn btn-sm account-action account-signout"
            onClick={() => { if (clerkEnabled) signOut(); else signOutOAuth(); }}
          >
            <Icon name="export" size={13} /> {t('account.signOut', { defaultValue: 'Sign out' })}
          </button>
        </section>
      </div>
    </div>
  );
}
