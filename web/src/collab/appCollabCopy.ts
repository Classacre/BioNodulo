import type { TFunction } from 'i18next';
import type { DialogOptions, PromptDialogOptions } from '../state/dialogs';
import type { CollabRole } from './types';

export interface AppCollabCopy {
  createLinkCopiedMessage: (hasPublicBaseUrl: boolean) => string;
  createLinkReadyMessage: (hasPublicBaseUrl: boolean) => string;
  joinPrompt: () => PromptDialogOptions;
  saveTemplateUnavailableDialog: () => DialogOptions;
  connectedAsRole: (role: string) => string;
  workflowFallback: (workflowId: string) => string;
  anonymousUserName: string;
  toast: {
    linkCopied: string;
    linkReady: string;
    joined: string;
    stopped: string;
    offlineModeRestored: string;
    templateSaved: string;
  };
  error: {
    createLinkFailed: string;
    invalidLinkTitle: string;
    invalidLinkMessage: string;
    joinFailed: string;
    saveTemplateFailed: string;
  };
}

function roleLabel(t: TFunction, role: string): string {
  const knownRole = role as CollabRole;
  const translated = t(`collab.role.${knownRole}`);
  return translated === `collab.role.${knownRole}` ? role : translated;
}

export function makeAppCollabCopy(t: TFunction): AppCollabCopy {
  return {
    createLinkCopiedMessage: hasPublicBaseUrl => hasPublicBaseUrl
      ? t('collab.appCreateLinkCopiedPublic')
      : t('collab.appCreateLinkCopiedLocal'),
    createLinkReadyMessage: hasPublicBaseUrl => hasPublicBaseUrl
      ? t('collab.appCreateLinkReadyPublic')
      : t('collab.appCreateLinkReadyLocal'),
    joinPrompt: () => ({
      title: t('collab.appJoinPromptTitle'),
      message: t('collab.appJoinPromptMessage'),
      inputLabel: t('collab.appJoinPromptInputLabel'),
      placeholder: t('collab.appJoinPromptPlaceholder'),
      confirmLabel: t('collab.appJoinPromptConfirm'),
    }),
    saveTemplateUnavailableDialog: () => ({
      title: t('collab.appSaveTemplateUnavailableTitle'),
      message: t('collab.appSaveTemplateUnavailableMessage'),
    }),
    connectedAsRole: role => t('collab.appConnectedAsRole', { role: roleLabel(t, role) }),
    workflowFallback: workflowId => t('collab.badgeWorkflowFallback', { id: workflowId.slice(0, 12) }),
    anonymousUserName: t('collab.anonymousUserName'),
    toast: {
      linkCopied: t('collab.linkCopied'),
      linkReady: t('collab.badgeLinkReady'),
      joined: t('collab.appJoinedCollaboration'),
      stopped: t('collab.appCollaborationStopped'),
      offlineModeRestored: t('collab.appOfflineModeRestored'),
      templateSaved: t('collab.appTemplateSaved'),
    },
    error: {
      createLinkFailed: t('collab.appCreateLinkError'),
      invalidLinkTitle: t('collab.appInvalidLinkTitle'),
      invalidLinkMessage: t('collab.appInvalidLinkMessage'),
      joinFailed: t('collab.appJoinError'),
      saveTemplateFailed: t('collab.appSaveTemplateError'),
    },
  };
}
