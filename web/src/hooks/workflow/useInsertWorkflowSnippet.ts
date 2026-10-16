import { useCallback, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { promptDialog } from '../../state/dialogs';
import { toast } from '../../state/notifications';
import type { Workflow } from '../../types';
import type { BrowserStorageScope } from '../../utils/browserStorageScope';
import type { WorkflowHistorySnapshot } from './useOwnedWorkflowHistory';

/** Insert into the current document as one owner-bound undo transaction. */
export function useInsertWorkflowSnippet({ storageScope, workflow, isCurrent, commitPatch, getViewport }: {
  storageScope: BrowserStorageScope;
  workflow: Workflow;
  isCurrent: () => boolean;
  commitPatch: (patch: Partial<Pick<Workflow, 'nodes' | 'edges' | 'groups' | 'parameters'>>) => boolean;
  getViewport: () => WorkflowHistorySnapshot['viewport'];
}) {
  const { t } = useTranslation();
  const currentWorkflow = useRef(workflow);
  currentWorkflow.current = workflow;

  return useCallback(async () => {
    if (storageScope.mode === 'blocked' || !isCurrent()) return;
    const { listWorkflowSnippets, instantiateSnippet } = await import('../../state/workflowSnippets');
    if (!isCurrent()) return;
    const snippets = listWorkflowSnippets(storageScope);
    if (snippets.length === 0) {
      toast.info(t('snippets.emptyLibrary'));
      return;
    }
    const labels = snippets.map((snippet, i) => `${i + 1}. ${snippet.name} (${snippet.nodes.length}n)`).join('\n');
    const choice = await promptDialog({
      title: t('snippets.insertPromptTitle'),
      message: t('snippets.insertPromptMessage', { labels }),
      inputLabel: t('snippets.insertPromptInputLabel'),
      defaultValue: '1',
    });
    if (!choice || !isCurrent()) return;
    const index = Math.max(1, Math.min(snippets.length, parseInt(choice, 10))) - 1;
    if (Number.isNaN(index)) return;
    const snippet = snippets[index];
    const viewport = getViewport();
    const centreWorld = viewport
      ? { x: (-viewport.x + window.innerWidth / 2) / viewport.scale, y: (-viewport.y + window.innerHeight / 2) / viewport.scale }
      : { x: 100, y: 100 };
    const { nodes, edges } = instantiateSnippet(snippet, centreWorld);
    const current = currentWorkflow.current;
    if (!commitPatch({ nodes: [...current.nodes, ...nodes], edges: [...current.edges, ...edges] })) return;
    toast.success(t('snippets.insertedTitle'), { message: snippet.name });
  }, [storageScope, isCurrent, commitPatch, getViewport, t]);
}
