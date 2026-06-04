import type { TFunction } from 'i18next';
import type { DialogOptions } from '../state/dialogs';
import type { RunRecord } from '../types';

export interface ConsoleActionCopy {
  cancelRunDialog: (run: RunRecord) => DialogOptions;
  clearQueueDialog: () => DialogOptions;
  clearHistoryDialog: () => DialogOptions;
  loadedRunWorkflowName: (run: RunRecord) => string;
  retryWorkflowName: (run: RunRecord) => string;
  toast: {
    runCancelled: string;
    workflowLoadedFromRun: string;
    retryQueued: string;
    queueCleared: string;
    historyCleared: string;
  };
  error: {
    noRunWorkflowSnapshot: string;
    couldNotCancelRun: string;
    couldNotLoadWorkflow: string;
    couldNotRetryRun: string;
    couldNotReorderQueue: string;
    couldNotClearQueue: string;
    couldNotClearHistory: string;
    couldNotDeleteRun: string;
  };
}

export function makeConsoleActionCopy(t: TFunction): ConsoleActionCopy {
  const runName = (run: RunRecord) => run.workflow_name || run.run_id;
  return {
    cancelRunDialog: run => ({
      title: t('console.actions.cancelRunTitle'),
      message: t('console.actions.cancelRunMessage', { name: runName(run) }),
      confirmLabel: t('console.cancelRun'),
      tone: 'danger',
    }),
    clearQueueDialog: () => ({
      title: t('console.actions.clearQueueTitle'),
      message: t('console.actions.clearQueueMessage'),
      confirmLabel: t('console.clearQueue'),
      tone: 'warning',
    }),
    clearHistoryDialog: () => ({
      title: t('console.actions.clearHistoryTitle'),
      message: t('console.actions.clearHistoryMessage'),
      confirmLabel: t('console.clearHistory'),
      tone: 'warning',
    }),
    loadedRunWorkflowName: run => run.workflow_name
      ? `${run.workflow_name} ${run.run_id.slice(0, 8)}`
      : t('console.actions.loadedRunFallbackName', { runId: run.run_id.slice(0, 8) }),
    retryWorkflowName: run => t('console.actions.retryWorkflowName', {
      name: run.workflow_name || t('console.untitledWorkflow'),
    }),
    toast: {
      runCancelled: t('console.actions.runCancelled'),
      workflowLoadedFromRun: t('console.actions.workflowLoadedFromRun'),
      retryQueued: t('console.actions.retryQueued'),
      queueCleared: t('console.actions.queueCleared'),
      historyCleared: t('console.actions.historyCleared'),
    },
    error: {
      noRunWorkflowSnapshot: t('console.actions.noRunWorkflowSnapshot'),
      couldNotCancelRun: t('console.actions.couldNotCancelRun'),
      couldNotLoadWorkflow: t('console.actions.couldNotLoadWorkflow'),
      couldNotRetryRun: t('console.actions.couldNotRetryRun'),
      couldNotReorderQueue: t('console.actions.couldNotReorderQueue'),
      couldNotClearQueue: t('console.actions.couldNotClearQueue'),
      couldNotClearHistory: t('console.actions.couldNotClearHistory'),
      couldNotDeleteRun: t('console.actions.couldNotDeleteRun'),
    },
  };
}
