import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import Icon from '../ui/Icon';

interface HtmlPreviewModalProps {
  src: string;
  filename: string;
  isOpen: boolean;
  onClose: () => void;
}

/**
 * Full-screen HTML report viewer.
 *
 * The report is rendered in a sandboxed iframe **without** allow-same-origin,
 * which puts it on an opaque origin. That means the page cannot reach the
 * parent DOM, cookies, or localStorage even if a node generates malicious
 * markup. allow-scripts is kept on because most bioinformatics reports
 * (MultiQC, FastQC, plotly-based dashboards) need JS for tabs and interactive
 * plots; if you ever need to display untrusted HTML and don't want scripts,
 * remove allow-scripts entirely.
 */
export default function HtmlPreviewModal({ src, filename, isOpen, onClose }: HtmlPreviewModalProps) {
  const { t } = useTranslation();

  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const openExternal = () => {
    window.open(src, '_blank', 'noopener,noreferrer');
  };

  const download = () => {
    const a = document.createElement('a');
    a.href = src;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  return (
    <div className="lightbox-overlay" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div
        style={{
          position: 'absolute',
          inset: '40px 40px 60px 40px',
          background: '#ffffff',
          borderRadius: 8,
          boxShadow: '0 16px 48px rgba(0,0,0,0.6)',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
      >
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          padding: '8px 12px',
          background: 'var(--surface)',
          borderBottom: '1px solid var(--border)',
          color: 'var(--text)',
        }}>
          <Icon name="file" size={14} />
          <strong style={{ fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {filename}
          </strong>
          <div style={{ flex: 1 }} />
          <button className="btn btn-sm btn-ghost" onClick={download} title={t('htmlPreview.downloadHtml')}>
            <Icon name="download" size={14} /> {t('common.save')}
          </button>
          <button className="btn btn-sm btn-ghost" onClick={openExternal} title={t('htmlPreview.openInNewTab')}>
            <Icon name="link" size={14} /> {t('common.open')}
          </button>
          <button className="btn btn-icon btn-sm" onClick={onClose} title={t('htmlPreview.closeEsc')} aria-label={t('htmlPreview.closeEsc')}>
            <Icon name="close" size={14} />
          </button>
        </div>
        <iframe
          src={src}
          title={filename}
          sandbox="allow-scripts"
          referrerPolicy="no-referrer"
          style={{ flex: 1, width: '100%', border: 'none', background: '#ffffff' }}
        />
      </div>
    </div>
  );
}
