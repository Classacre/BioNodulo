import React, { useState } from 'react';
import { useAtom } from 'jotai';
import { useTranslation } from 'react-i18next';
import Dialog from '../components/ui/Dialog';
import { toast } from '../components/ui';
import { inviteCollaborator } from '../api/website';
import { showInviteDialogAtom } from '../state/uiAtoms';
import { logError } from '../state/logging';

/**
 * Invite a collaborator to the team by email. The website calls Clerk
 * Organizations, which sends the branded invitation email; on acceptance the
 * invitee joins the team (handled by the website's Clerk webhook). Available in
 * both the cloud editor and the locally-run app when signed into a BioNodulo
 * account (the invite call is bearer/cookie-authed by website.ts).
 */
const InviteDialog: React.FC = () => {
  const { t } = useTranslation();
  const [open, setOpen] = useAtom(showInviteDialogAtom);
  const [email, setEmail] = useState('');
  const [role, setRole] = useState<'member' | 'admin'>('member');
  const [submitting, setSubmitting] = useState(false);

  if (!open) return null;

  const close = () => { setOpen(false); setEmail(''); setRole('member'); };

  const submit = async () => {
    const value = email.trim();
    if (!value) return;
    setSubmitting(true);
    try {
      await inviteCollaborator(value, role);
      toast.success(t('collab.inviteSent', { defaultValue: 'Invitation sent', email: value }), {
        message: t('collab.inviteSentMessage', { defaultValue: `${value} will get an email to join your team.`, email: value }),
      });
      close();
    } catch (err) {
      logError('collab.invite', err);
      const msg = err instanceof Error ? err.message : String(err);
      toast.error(t('collab.inviteFailed', { defaultValue: 'Could not send invitation' }), { message: msg });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog
      title={t('collab.inviteTitle', { defaultValue: 'Invite collaborator' })}
      width={420}
      onClose={close}
      footer={
        <>
          <button className="btn" onClick={close} disabled={submitting}>
            {t('common.cancel', { defaultValue: 'Cancel' })}
          </button>
          <button className="btn btn-primary" onClick={() => void submit()} disabled={submitting || !email.trim()}>
            {submitting ? t('collab.inviteSending', { defaultValue: 'Sending…' }) : t('collab.inviteSend', { defaultValue: 'Send invite' })}
          </button>
        </>
      }
    >
      <div style={{ display: 'grid', gap: 12 }}>
        <p style={{ fontSize: 13, color: 'var(--muted)', margin: 0 }}>
          {t('collab.inviteDescription', { defaultValue: 'They get an email to join your team and collaborate on workflows.' })}
        </p>
        <label style={{ display: 'grid', gap: 4, fontSize: 12, fontWeight: 600 }}>
          {t('collab.inviteEmailLabel', { defaultValue: 'Email address' })}
          <input
            type="email"
            value={email}
            autoFocus
            placeholder="name@example.com"
            onChange={e => setEmail(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') void submit(); }}
            style={{ padding: '8px 10px', borderRadius: 6, border: '1px solid var(--border)', background: 'var(--surface)', color: 'var(--text)' }}
          />
        </label>
        <label style={{ display: 'grid', gap: 4, fontSize: 12, fontWeight: 600 }}>
          {t('collab.inviteRoleLabel', { defaultValue: 'Role' })}
          <select
            value={role}
            onChange={e => setRole(e.target.value as 'member' | 'admin')}
            style={{ padding: '8px 10px', borderRadius: 6, border: '1px solid var(--border)', background: 'var(--surface)', color: 'var(--text)' }}
          >
            <option value="member">{t('collab.inviteRoleMember', { defaultValue: 'Member' })}</option>
            <option value="admin">{t('collab.inviteRoleAdmin', { defaultValue: 'Admin' })}</option>
          </select>
        </label>
      </div>
    </Dialog>
  );
};

export default InviteDialog;
