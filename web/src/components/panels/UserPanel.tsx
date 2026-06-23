import { useEffect, useState } from 'react';
import { useAtomValue, useSetAtom } from 'jotai';
import { useTranslation } from 'react-i18next';
import Icon from '../ui/Icon';
import { cloudConfigAtom } from '../../state/appAtoms';
import { showInviteDialogAtom } from '../../state/uiAtoms';
import { getCloudCredits } from '../../api/website';
import { useClerkAuth } from '../../hooks/cloud/useClerkAuth';

interface UserPanelProps {
  onClose: () => void;
}

/**
 * Account menu embedded in the editor's left rail (shown only when signed in).
 * Surfaces the signed-in identity, plan, and live credit balance — the bits of
 * the website dashboard a user needs mid-edit — plus Invite, Manage account
 * (billing), and Sign out. Credit/plan data comes from /api/config (seeded on
 * boot) with a fresh /api/billing/credits read on mount.
 */
export default function UserPanel({ onClose }: UserPanelProps) {
  const { t } = useTranslation();
  const cloudConfig = useAtomValue(cloudConfigAtom);
  const openInvite = useSetAtom(showInviteDialogAtom);
  const { clerkEnabled, signOut } = useClerkAuth();

  const user = cloudConfig?.user ?? null;
  const plan = cloudConfig?.plan ?? null;
  const accountUrl = cloudConfig?.accountUrl ?? null;

  const [credits, setCredits] = useState<{ remaining: number; total: number } | null>(
    cloudConfig?.credits && cloudConfig.credits.remaining != null
      ? { remaining: cloudConfig.credits.remaining, total: cloudConfig.credits.total ?? 0 }
      : null,
  );

  useEffect(() => {
    let active = true;
    getCloudCredits()
      .then(c => {
        if (!active || !c) return;
        setCredits({ remaining: c.remaining, total: c.monthlyCredits });
      })
      .catch(() => { /* keep seeded value */ });
    return () => { active = false; };
  }, []);

  const planLabel = plan ? plan.charAt(0).toUpperCase() + plan.slice(1) : t('account.planFree', { defaultValue: 'Free' });
  const billingUrl = accountUrl ? `${accountUrl.replace(/\/+$/, '')}/dashboard/billing` : null;

  return (
    <div className="rail-panel">
      <div className="rail-panel-header">
        <span>{t('account.title', { defaultValue: 'Account' })}</span>
        <button className="btn btn-icon" onClick={onClose} title={t('common.close')} aria-label={t('common.close')}>
          <Icon name="close" size={14} />
        </button>
      </div>

      <div className="rail-panel-body" style={{ display: 'flex', flexDirection: 'column', gap: 16, padding: 16 }}>
        {/* Identity */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{
            width: 40, height: 40, borderRadius: '50%', background: 'var(--accent, #2dd4bf)',
            color: '#0b0e0f', display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontWeight: 700, fontSize: 16, flexShrink: 0,
          }}>
            {(user?.name || user?.email || '?').trim().charAt(0).toUpperCase()}
          </div>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {user?.name || t('account.signedIn', { defaultValue: 'Signed in' })}
            </div>
            {user?.email && (
              <div style={{ fontSize: 12, color: 'var(--muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {user.email}
              </div>
            )}
          </div>
        </div>

        {/* Plan + credits */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
            <span style={{ color: 'var(--muted)' }}>{t('account.plan', { defaultValue: 'Plan' })}</span>
            <span style={{ fontWeight: 600 }}>{planLabel}</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
            <span style={{ color: 'var(--muted)' }}>{t('account.credits', { defaultValue: 'Credits' })}</span>
            <span style={{ fontWeight: 600 }}>
              {credits
                ? `${credits.remaining.toLocaleString()} / ${credits.total.toLocaleString()}`
                : '—'}
            </span>
          </div>
        </div>

        {/* Actions */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <button className="btn" onClick={() => openInvite(true)}>
            <Icon name="users" size={14} /> {t('account.invite', { defaultValue: 'Invite collaborator' })}
          </button>
          {billingUrl && (
            <a className="btn" href={billingUrl} target="_blank" rel="noopener noreferrer">
              <Icon name="link" size={14} /> {t('account.manage', { defaultValue: 'Manage account & billing' })}
            </a>
          )}
          {clerkEnabled && (
            <button className="btn" onClick={signOut}>
              <Icon name="export" size={14} /> {t('account.signOut', { defaultValue: 'Sign out' })}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
