import { useCallback, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import type { FitViewOptions } from '@xyflow/react';
import { promptDialog } from '../../state/dialogs';
import { toast } from '../../state/notifications';
import type { ObjectInfo, Workflow, WorkflowNode } from '../../types';
import type { BrowserStorageScope } from '../../utils/browserStorageScope';
import { findSnippetPlacement, placementBounds, snippetNodeSize, snippetRevealOptions, type PlacementSize } from '../../utils/snippetPlacement';
import type { WorkflowHistorySnapshot } from './useOwnedWorkflowHistory';

function measureCanvasArea() {
  const canvas = document.querySelector<HTMLElement>('.main-canvas .react-flow');
  const rect = canvas?.getBoundingClientRect();
  const width = Math.max(1, rect?.width || window.innerWidth);
  const height = Math.max(1, rect?.height || window.innerHeight);
  const shell = canvas?.closest<HTMLElement>('.app-shell');
  const style = shell && !shell.classList.contains('focus-mode') ? getComputedStyle(shell) : null;
  const inset = (key: string) => {
    const value = parseFloat(style?.getPropertyValue(key) ?? '');
    return Number.isFinite(value) ? Math.max(0, value) : 0;
  };
  const leftInset = Math.min(width - 1, inset('--left-panel-inset'));
  const rightInset = Math.min(width - leftInset - 1, inset('--right-panel-inset'));
  const top = rect?.top ?? 0;
  const left = rect?.left ?? 0;
  const main = canvas?.closest('.main-canvas');
  const overlays = [...(main?.querySelectorAll<HTMLElement>('.react-flow__minimap, .react-flow__controls, .island') ?? [])];
  const consoleElement = style ? shell?.querySelector<HTMLElement>('.bottom-console') : null;
  if (consoleElement) overlays.push(consoleElement);
  let usableBottom = top + height;
  for (const element of overlays) {
    const visibility = getComputedStyle(element).visibility;
    if (visibility === 'hidden' || visibility === 'collapse') continue;
    const bounds = element.getBoundingClientRect();
    if (![bounds.top, bounds.bottom, bounds.left, bounds.right, bounds.width, bounds.height].every(Number.isFinite)
      || bounds.width <= 0 || bounds.height <= 0) continue;
    if (bounds.left < left + width - rightInset && bounds.right > left + leftInset
      && bounds.top < top + height && bounds.bottom > top) usableBottom = Math.min(usableBottom, bounds.top);
  }
  // Bottom chrome can sit above the console (notably MiniMap). Reserve its
  // actual upper edge across the usable strip so a fitted node stays readable.
  const bottomInset = Math.min(height - 1, Math.max(0, top + height - usableBottom));
  return { canvas, width, height, leftInset, rightInset, bottomInset };
}

/** Insert into the current document as one owner-bound undo transaction. */
export function useInsertWorkflowSnippet({ storageScope, workflow, objectInfo = {}, isCurrent, commitPatch, getViewport, onInserted }: {
  storageScope: BrowserStorageScope;
  workflow: Workflow;
  objectInfo?: ObjectInfo;
  isCurrent: () => boolean;
  commitPatch: (patch: Partial<Pick<Workflow, 'nodes' | 'edges' | 'groups' | 'parameters'>>) => boolean;
  getViewport: () => WorkflowHistorySnapshot['viewport'];
  onInserted?: (options: FitViewOptions) => void;
}) {
  const { t } = useTranslation();
  const currentWorkflow = useRef(workflow);
  currentWorkflow.current = workflow;
  const latest = useRef({ objectInfo, onInserted });
  latest.current = { objectInfo, onInserted };

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
    if (!snippet.nodes.length) return;
    const viewport = getViewport();
    const current = currentWorkflow.current;
    // Drawers/console overlay Flow; its full DOM size includes obscured space.
    const area = measureCanvasArea();
    const measured = new Map<string, PlacementSize>();
    area.canvas?.querySelectorAll<HTMLElement>('.react-flow__node[data-id]').forEach(element => {
      if (element.dataset.id && element.offsetWidth > 0 && element.offsetHeight > 0) {
        measured.set(element.dataset.id, { width: element.offsetWidth, height: element.offsetHeight });
      }
    });
    const sizeFor = (node: WorkflowNode, live: boolean) => snippetNodeSize(node,
      latest.current.objectInfo[node.type] ?? node.node_info, live ? measured.get(node.id) : undefined);
    const existing = current.nodes.map(node => ({ x: node.position[0], y: node.position[1], ...sizeFor(node, true) }));
    const snippetBounds = placementBounds(snippet.nodes.map(node => ({ x: node.position[0], y: node.position[1], ...sizeFor(node, false) })));
    const scale = viewport && Number.isFinite(viewport.scale) && viewport.scale > 0 ? viewport.scale : 1;
    const placement = findSnippetPlacement(existing, { width: snippetBounds.width, height: snippetBounds.height }, {
      x: (area.leftInset - (viewport?.x ?? 0)) / scale, y: -(viewport?.y ?? 0) / scale,
      width: (area.width - area.leftInset - area.rightInset) / scale,
      height: (area.height - area.bottomInset) / scale,
    });
    const { nodes, edges } = instantiateSnippet(snippet, placement);
    if (!commitPatch({ nodes: [...current.nodes, ...nodes], edges: [...current.edges, ...edges] })) return;
    if (placement.needsReveal && latest.current.onInserted) {
      requestAnimationFrame(() => requestAnimationFrame(() => {
        if (isCurrent() && nodes.every(node => currentWorkflow.current.nodes.some(currentNode => currentNode.id === node.id))) {
          latest.current.onInserted?.(snippetRevealOptions(measureCanvasArea(), nodes.map(node => node.id)));
        }
      }));
    }
    toast.success(t('snippets.insertedTitle'), { message: snippet.name });
  }, [storageScope, isCurrent, commitPatch, getViewport, t]);
}
