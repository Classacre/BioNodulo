import { useEffect, useState } from 'react';
import { useAtom } from 'jotai';
import { useTranslation } from 'react-i18next';
import Dialog from '../ui/Dialog';
import Icon from '../ui/Icon';
import { showOpenWorkflowAtom } from '../../state/uiAtoms';
import { listCloudWorkflows, type CloudWorkflowSummary } from '../../api/website';
import { logError } from '../../state/logging';

interface OpenWorkflowModalProps {
  /** Open an existing cloud workflow as a tab (focus if already open). */
  onOpen: (id: string) => void;
  /** Create a fresh cloud workflow and open it. */
  onNew: () => void;
}

/**
 * Cloud editor "open workflow" picker. Lists the team's saved workflows so the
 * user can open any as a tab, or create a new one. Workflows live in the app now
 * (tabs + runs), so this replaces the dashboard's workflow list as the way to
 * switch between them.
 */
export default function OpenWorkflowModal({ onOpen, onNew }: OpenWorkflowModalProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useAtom(showOpenWorkflowAtom);
  const [items, setItems] = useState<CloudWorkflowSummary[] | null>(null);

  useEffect(() => {
    if (!open) return;
    setItems(null);
    listCloudWorkflows()
      .then(setItems)
      .catch(err => { logError('cloud.workflows.list', err); setItems([]); });
  }, [open]);

  if (!open) return null;

  const close = () => setOpen(false);

  return (
    <Dialog
      title={t('openWorkflow.title', { defaultValue: 'Open workflow' })}
      width={460}
      onClose={close}
      footer={
        <>
          <button className="btn" onClick={close}>{t('common.close', { defaultValue: 'Close' })}</button>
          <button
            className="btn btn-primary"
            onClick={() => { onNew(); close(); }}
          >
            <Icon name="plus" size={14} /> {t('openWorkflow.new', { defaultValue: 'New workflow' })}
          </button>
        </>
      }
    >
      <div style={{ maxHeight: 360, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 4 }}>
        {items === null && (
          <div style={{ padding: 16, color: 'var(--muted)' }}>{t('common.loading', { defaultValue: 'Loading…' })}</div>
        )}
        {items !== null && items.length === 0 && (
          <div style={{ padding: 16, color: 'var(--muted)' }}>
            {t('openWorkflow.empty', { defaultValue: 'No saved workflows yet. Create your first one.' })}
          </div>
        )}
        {items?.map(wf => (
          <button
            key={wf.id}
            className="btn"
            style={{ justifyContent: 'flex-start', textAlign: 'left' }}
            onClick={() => { onOpen(wf.id); close(); }}
          >
            <Icon name="template" size={14} />
            <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {wf.name || t('common.untitled', { defaultValue: 'Untitled' })}
            </span>
          </button>
        ))}
      </div>
    </Dialog>
  );
}
