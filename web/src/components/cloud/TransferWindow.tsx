// Minimizable cloud-transfer window. Fixed bottom-right, above panels, so it
// survives rail/panel switches. Shows per-file progress + speed for uploads and
// downloads; collapses to a compact pill that keeps a live aggregate bar.
// Rendered once at the app root; renders nothing when there are no transfers.
import { useAtom, useAtomValue } from 'jotai';
import { useTranslation } from 'react-i18next';
import Icon from '../ui/Icon';
import {
  transfersAtom, transferMinimizedAtom, clearFinishedTransfers, removeTransfer,
  type Transfer,
} from '../../state/transfers';

function fmtBytes(n: number): string {
  if (!n || n < 0) return '0 B';
  const u = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.min(u.length - 1, Math.floor(Math.log(n) / Math.log(1024)));
  return `${(n / Math.pow(1024, i)).toFixed(i === 0 ? 0 : 1)} ${u[i]}`;
}
function fmtSpeed(bps: number): string {
  return bps > 0 ? `${fmtBytes(bps)}/s` : '—';
}
function pct(t: Transfer): number {
  if (t.status === 'done') return 100;
  if (!t.total) return 0;
  return Math.min(100, Math.round((t.loaded / t.total) * 100));
}

function TransferRow({ t }: { t: Transfer }) {
  const { t: tr } = useTranslation();
  const p = pct(t);
  return (
    <div className={`bio-xfer-row bio-xfer-${t.status}`}>
      <span className="bio-xfer-dir" aria-hidden><Icon name={t.direction === 'upload' ? 'export' : 'download'} size={13} /></span>
      <div className="bio-xfer-main">
        <div className="bio-xfer-name" title={t.name}>{t.name}</div>
        <div className="bio-xfer-bar"><div className="bio-xfer-fill" style={{ width: `${p}%` }} /></div>
        <div className="bio-xfer-meta">
          {t.status === 'active' && <span>{fmtBytes(t.loaded)} / {fmtBytes(t.total)} · {fmtSpeed(t.speedBps)}</span>}
          {t.status === 'done' && <span>{tr('transfers.done', { defaultValue: 'Done' })} · {fmtBytes(t.total)}</span>}
          {t.status === 'error' && <span className="bio-xfer-err">{t.error || tr('transfers.failed', { defaultValue: 'Failed' })}</span>}
          {t.status === 'canceled' && <span>{tr('transfers.canceled', { defaultValue: 'Canceled' })}</span>}
        </div>
      </div>
      {t.status === 'active' && t.abort ? (
        <button className="bio-xfer-x" title={tr('transfers.cancel', { defaultValue: 'Cancel' })} onClick={() => t.abort?.()}><Icon name="close" size={12} /></button>
      ) : (
        <button className="bio-xfer-x" title={tr('common.close')} onClick={() => removeTransfer(t.id)}><Icon name="close" size={12} /></button>
      )}
    </div>
  );
}

export default function TransferWindow() {
  const { t } = useTranslation();
  const transfers = useAtomValue(transfersAtom);
  const [minimized, setMinimized] = useAtom(transferMinimizedAtom);
  if (transfers.length === 0) return null;

  const active = transfers.filter(x => x.status === 'active');
  const totalLoaded = transfers.reduce((s, x) => s + x.loaded, 0);
  const totalBytes = transfers.reduce((s, x) => s + (x.total || 0), 0);
  const aggPct = totalBytes ? Math.min(100, Math.round((totalLoaded / totalBytes) * 100)) : (active.length ? 0 : 100);

  if (minimized) {
    return (
      <button className="bio-xfer-pill" onClick={() => setMinimized(false)} title={t('transfers.title', { defaultValue: 'Transfers' })}>
        <Icon name={active.length ? 'activity' : 'check'} size={14} />
        <span>{active.length ? t('transfers.activeCount', { count: active.length, defaultValue: '{{count}} transferring' }) : t('transfers.title', { defaultValue: 'Transfers' })}</span>
        <span className="bio-xfer-pill-bar"><span className="bio-xfer-pill-fill" style={{ width: `${aggPct}%` }} /></span>
      </button>
    );
  }

  return (
    <div className="bio-xfer-window" role="dialog" aria-label={t('transfers.title', { defaultValue: 'Transfers' })}>
      <header className="bio-xfer-head">
        <span className="bio-xfer-title">
          <Icon name="server" size={13} /> {t('transfers.title', { defaultValue: 'Transfers' })}
          {active.length > 0 && <span className="bio-xfer-count">{active.length}</span>}
        </span>
        <span className="bio-xfer-head-actions">
          <button title={t('transfers.clear', { defaultValue: 'Clear finished' })} onClick={clearFinishedTransfers}><Icon name="trash" size={13} /></button>
          <button title={t('transfers.minimize', { defaultValue: 'Minimize' })} onClick={() => setMinimized(true)}><Icon name="minus" size={14} /></button>
        </span>
      </header>
      <div className="bio-xfer-list">
        {transfers.slice().reverse().map(x => <TransferRow key={x.id} t={x} />)}
      </div>
    </div>
  );
}
