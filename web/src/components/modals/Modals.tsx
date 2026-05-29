import { lazy, Suspense } from 'react';
import { useAtom, useAtomValue, useSetAtom } from 'jotai';
import ExportModal from './ExportModal';
import ImportModal from './ImportModal';
import AIWorkflowModal from './AIWorkflowModal';
import BatchSampleSheetModal from './BatchSampleSheetModal';
import type { SampleSheetRun } from './BatchSampleSheetModal';
import ImageLightbox from './ImageLightbox';
import HtmlPreviewModal from './HtmlPreviewModal';
import GettingStartedModal from './GettingStartedModal';
import {
  ShareDialog,
  CommentsPanel,
  VersionHistory,
  AuditLog,
} from '../../collab';
import { Spinner } from '../ui';
import { toast } from '../ui';
import {
  showExportAtom,
  showImportAtom,
  showOutputDiffAtom,
  showBulkParamAtom,
  showDoctorAtom,
  showAIAtom,
  showBatchSheetAtom,
  showGettingStartedAtom,
  showShareDialogAtom,
  showCommentsAtom,
  showVersionsAtom,
  showAuditAtom,
  selectedNodeIdAtom,
} from '../../state/uiAtoms';
import { requestedWorkflowIdAtom, showAuthDialogAtom } from '../../state/appAtoms';
import {
  htmlPreviewStateAtom,
  lightboxImagesAtom,
  lightboxIndexAtom,
  lightboxOpenAtom,
} from '../../state/lightboxAtoms';
import type { Workflow, WorkflowNode, TemplateInfo, RunRecord, ObjectInfo } from '../../types';
import type { Comment } from '../../collab';
import { valuesFromUnknownRecord } from '../../utils';

const OutputDiffModal = lazy(() => import('./OutputDiffModal'));
const BulkParamModal = lazy(() => import('./BulkParamModal'));
const WorkflowDoctorModal = lazy(() => import('./WorkflowDoctorModal'));

export interface ModalWorkflowContext {
  activeWorkflow: Workflow;
  activeWorkflowId: string;
  activeIndex: number;
  updateWorkflow: (index: number, workflow: Workflow) => void;
  activeWorkflowRef: React.RefObject<Workflow>;
  bridgeRef: React.RefObject<import('../../collab').LiteGraphYjsBridge | null>;
  canvasRef: React.RefObject<import('../canvas/LiteGraphCanvas').LiteGraphCanvasRef | null>;
  runs: RunRecord[];
  objectInfo: ObjectInfo;
  currentUser: { id: string; name: string; color: string };
  collabEnabled: boolean;
  authUser: unknown;
  getBool: (key: string) => boolean;
  set: (key: string, value: unknown) => void;
  handleImport: (wf: Workflow) => void;
  handleApplyWorkflow: (wf: Workflow) => void;
  handleBatchSheetSubmit: (runs: SampleSheetRun[]) => void;
  handleLoadTemplate: (template: TemplateInfo) => Promise<void>;
  publishCollabWorkflowSnapshot: (wf: Workflow) => Promise<void>;
  setWorkflowComments: (comments: Comment[]) => void;
  setWorkflowNames: (names: Record<string, string>) => void;
}

export function Modals({ ctx }: { ctx: ModalWorkflowContext }) {
  const [showExport, setShowExport] = useAtom(showExportAtom);
  const [showImport, setShowImport] = useAtom(showImportAtom);
  const [showOutputDiff, setShowOutputDiff] = useAtom(showOutputDiffAtom);
  const [showBulkParam, setShowBulkParam] = useAtom(showBulkParamAtom);
  const [showDoctor, setShowDoctor] = useAtom(showDoctorAtom);
  const [showAI, setShowAI] = useAtom(showAIAtom);
  const [showBatchSheet, setShowBatchSheet] = useAtom(showBatchSheetAtom);
  const [showGettingStarted, setShowGettingStarted] = useAtom(showGettingStartedAtom);
  const [showShareDialog, setShowShareDialog] = useAtom(showShareDialogAtom);
  const [showComments, setShowComments] = useAtom(showCommentsAtom);
  const [showVersions, setShowVersions] = useAtom(showVersionsAtom);
  const [showAudit, setShowAudit] = useAtom(showAuditAtom);
  const setSelectedNodeId = useSetAtom(selectedNodeIdAtom);
  const setRequestedWorkflowId = useSetAtom(requestedWorkflowIdAtom);
  const setShowAuthDialog = useSetAtom(showAuthDialogAtom);
  const lightboxOpen = useAtomValue(lightboxOpenAtom);
  const lightboxImages = useAtomValue(lightboxImagesAtom);
  const lightboxIndex = useAtomValue(lightboxIndexAtom);
  const setLightboxOpen = useSetAtom(lightboxOpenAtom);
  const htmlPreviewState = useAtomValue(htmlPreviewStateAtom);
  const setHtmlPreviewState = useSetAtom(htmlPreviewStateAtom);

  const {
    activeWorkflow,
    activeWorkflowId,
    activeIndex,
    updateWorkflow,
    activeWorkflowRef,
    bridgeRef,
    canvasRef,
    runs,
    objectInfo,
    currentUser,
    collabEnabled,
    authUser,
    getBool,
    set,
    handleImport,
    handleApplyWorkflow,
    handleBatchSheetSubmit,
    handleLoadTemplate,
    publishCollabWorkflowSnapshot,
    setWorkflowComments,
    setWorkflowNames,
  } = ctx;

  return (
    <>
      <ShareDialog
        workflowId={activeWorkflowId}
        isOpen={showShareDialog}
        onClose={() => setShowShareDialog(false)}
      />

      <CommentsPanel
        workflowId={activeWorkflowId}
        currentUser={currentUser}
        isOpen={showComments}
        onClose={() => setShowComments(false)}
        onFocusNode={(nodeId) => {
          setSelectedNodeId(nodeId);
          canvasRef.current?.focusNode(nodeId);
        }}
        onCommentsChange={setWorkflowComments}
        onWorkflowNamesChange={setWorkflowNames}
      />
      <VersionHistory
        workflowId={activeWorkflowId}
        isOpen={showVersions}
        onClose={() => setShowVersions(false)}
        onRestore={(versionJson) => {
          if (versionJson && typeof versionJson === 'object') {
            const v = versionJson as Record<string, unknown>;
            const nextWorkflow = {
              ...activeWorkflowRef.current,
              id: activeWorkflowId,
              nodes: valuesFromUnknownRecord<WorkflowNode>(v.nodes),
              edges: valuesFromUnknownRecord<Workflow['edges'][number]>(v.edges),
              groups: valuesFromUnknownRecord<Workflow['groups'][number]>(v.groups),
            };
            if (bridgeRef.current) {
              bridgeRef.current.onNodesChanged(nextWorkflow.nodes);
              bridgeRef.current.onEdgesChanged(nextWorkflow.edges);
              bridgeRef.current.onGroupsChanged(nextWorkflow.groups);
            }
            updateWorkflow(activeIndex, nextWorkflow);
            void publishCollabWorkflowSnapshot(nextWorkflow);
          }
        }}
      />
      <AuditLog
        workflowId={activeWorkflowId}
        isOpen={showAudit}
        onClose={() => setShowAudit(false)}
      />

      {showExport && <ExportModal workflow={activeWorkflow} onClose={() => setShowExport(false)} />}
      {showImport && <ImportModal onImport={handleImport} onClose={() => setShowImport(false)} />}
      {showOutputDiff && (
        <Suspense fallback={<div className="modal-overlay"><Spinner size="lg" label="Loading run diff" /></div>}>
          <OutputDiffModal runs={runs} onClose={() => setShowOutputDiff(false)} />
        </Suspense>
      )}
      {showDoctor && (
        <Suspense fallback={<div className="modal-overlay"><Spinner size="lg" label="Loading doctor" /></div>}>
          <WorkflowDoctorModal
            workflow={activeWorkflow}
            objectInfo={objectInfo}
            onClose={() => setShowDoctor(false)}
            onJumpToNode={(id) => { canvasRef.current?.focusNode(id); setShowDoctor(false); }}
          />
        </Suspense>
      )}
      {showBulkParam && (() => {
        const selectedIds = canvasRef.current?.getSelectedNodeIds() ?? [];
        const selectedNodes = activeWorkflow.nodes.filter(n => selectedIds.includes(n.id));
        return (
          <Suspense fallback={<div className="modal-overlay"><Spinner size="lg" label="Loading bulk editor" /></div>}>
            <BulkParamModal
              nodes={selectedNodes}
              onClose={() => setShowBulkParam(false)}
              onApply={(changes) => {
                if (changes.length === 0) return;
                const idSet = new Set(selectedIds);
                const nextNodes = activeWorkflow.nodes.map(n => {
                  if (!idSet.has(n.id)) return n;
                  const nextParams = { ...n.params };
                  for (const { key, value } of changes) {
                    if (!Object.prototype.hasOwnProperty.call(nextParams, key)) continue;
                    nextParams[key] = value;
                  }
                  return { ...n, params: nextParams };
                });
                updateWorkflow(activeIndex, { ...activeWorkflow, nodes: nextNodes });
                toast.success('Bulk edit applied', { message: `${changes.length} param${changes.length === 1 ? '' : 's'} → ${selectedNodes.length} node${selectedNodes.length === 1 ? '' : 's'}` });
              }}
            />
          </Suspense>
        );
      })()}
      {showAI && (
        <AIWorkflowModal
          workflow={activeWorkflow}
          onClose={() => setShowAI(false)}
          onApplyWorkflow={handleApplyWorkflow}
        />
      )}
      {showBatchSheet && (
        <BatchSampleSheetModal
          workflow={activeWorkflow}
          onClose={() => setShowBatchSheet(false)}
          onSubmit={handleBatchSheetSubmit}
        />
      )}
      {showGettingStarted && (
        <GettingStartedModal
          onClose={() => {
            set('bionodulo.getting_started.dismissed', true);
            setShowGettingStarted(false);
          }}
          onDontShowAgain={(hide) => {
            set('bionodulo.getting_started.show_on_startup', !hide);
          }}
          collabEnabled={collabEnabled}
          onSetCollabEnabled={(enabled) => {
            set('bionodulo.collab.enabled', enabled);
            if (!enabled) {
              setShowAuthDialog(false);
            } else if (!authUser) {
              setShowAuthDialog(true);
            }
          }}
          showOnStartup={getBool('bionodulo.getting_started.show_on_startup')}
          onOpenRecent={async (entry) => {
            if (entry.source === 'template' && entry.filename) {
              const template = {
                id: entry.id,
                name: entry.name,
                filename: entry.filename,
                description: '',
                node_count: entry.nodeCount ?? 0,
              } as TemplateInfo;
              await handleLoadTemplate(template);
            } else if (collabEnabled) {
              setRequestedWorkflowId(entry.id);
            }
          }}
        />
      )}
      <ImageLightbox
        images={lightboxImages}
        initialIndex={lightboxIndex}
        isOpen={lightboxOpen}
        onClose={() => setLightboxOpen(false)}
      />
      <HtmlPreviewModal
        src={htmlPreviewState?.src ?? ''}
        filename={htmlPreviewState?.filename ?? ''}
        isOpen={htmlPreviewState !== null}
        onClose={() => setHtmlPreviewState(null)}
      />
    </>
  );
}
