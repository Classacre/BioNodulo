// Start screen for an empty tab.
//
// A new tab used to be a bare canvas with no indication of what to do next,
// while the editor's answer to "where is my work" was to open every recent
// workflow as a tab on load -- slow for anyone with many, and it buried the one
// they wanted. Opening is now a deliberate act, offered here.
//
// Only the few most recent are listed. A long list is a directory, not a
// shortcut; the full picker is one click away.
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import Icon from '../ui/Icon';
import { listCloudWorkflows, type CloudWorkflowSummary } from '../../api/website';

/** Recent workflows shown inline. The rest live behind "Open workflow". */
export const RECENT_LIMIT = 7;

export interface EmptyCanvasMenuProps {
  /** Cloud editor: recent workflows can be listed and opened by id. */
  cloudMode: boolean;
  onCreateNew: () => void;
  onOpenRecent: (id: string) => void;
  /** Show the full picker (cloud) — more than the few listed here. */
  onBrowseAll: () => void;
  onImport: () => void;
}

export default function EmptyCanvasMenu({
  cloudMode,
  onCreateNew,
  onOpenRecent,
  onBrowseAll,
  onImport,
}: EmptyCanvasMenuProps) {
  const { t } = useTranslation();
  const [recent, setRecent] = useState<CloudWorkflowSummary[]>([]);

  useEffect(() => {
    if (!cloudMode) return;
    let active = true;
    // Failing to list recents must not blank the menu: New and Import still
    // work without it.
    listCloudWorkflows()
      .then(list => { if (active) setRecent(list.slice(0, RECENT_LIMIT)); })
      .catch(() => { if (active) setRecent([]); });
    return () => { active = false; };
  }, [cloudMode]);

  return (
    <div className="empty-canvas-menu" role="region" aria-label={t('canvas.empty.title', { defaultValue: 'Start a workflow' })}>
      <h2 className="empty-canvas-title">
        {t('canvas.empty.title', { defaultValue: 'Start a workflow' })}
      </h2>

      <div className="empty-canvas-actions">
        <button type="button" className="btn empty-canvas-action" onClick={onCreateNew}>
          <Icon name="plus" size={15} />
          {t('canvas.empty.createNew', { defaultValue: 'New workflow' })}
        </button>
        <button type="button" className="btn empty-canvas-action" onClick={onImport}>
          <Icon name="import" size={15} />
          {t('canvas.empty.import', { defaultValue: 'Import…' })}
        </button>
      </div>

      {cloudMode && recent.length > 0 && (
        <div className="empty-canvas-recent">
          <div className="empty-canvas-recent-head">
            <span>{t('canvas.empty.recent', { defaultValue: 'Recent' })}</span>
            <button type="button" className="btn btn-sm btn-ghost" onClick={onBrowseAll}>
              {t('canvas.empty.browseAll', { defaultValue: 'All workflows' })}
            </button>
          </div>
          <ul className="empty-canvas-recent-list">
            {recent.map(summary => (
              <li key={summary.id}>
                <button
                  type="button"
                  className="empty-canvas-recent-item"
                  onClick={() => onOpenRecent(summary.id)}
                  title={summary.name}
                >
                  <Icon name="template" size={13} />
                  <span className="empty-canvas-recent-name">{summary.name}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
