import type { TFunction } from 'i18next';
import type { DialogOptions, PromptDialogOptions } from '../state/dialogs';
import type { CollabRole } from './types';

export interface AppCollabCopy {
  createLinkCopiedMessage: (hasPublicBaseUrl: boolean) => string;
  createLinkReadyMessage: (hasPublicBaseUrl: boolean) => string;
  joinPrompt: () => PromptDialogOptions;
  saveTemplateUnavailableDialog: () => DialogOptions;
  connectedAsRole: (role: string) => string;
  /** Cloud share-link minted + copied (guests join with edit + run). */
  cloudShareLinkCopied: () => string;
  /** Fallback when share-link creation fails — collab still works for the team. */
  cloudCollabOn: () => string;
  /** Guest joined a share link as a read-only viewer. */
  joinedAsViewer: () => string;
  /** Guest joined a share link with edit + run powers. */
  joinedAsEditor: () => string;
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
    cloudShareLinkCopied: () => t('collab.cloudShareLinkReady', {
      defaultValue: 'Share link copied — anyone who opens it joins this workflow (edit + run).',
    }),
    cloudCollabOn: () => t('collab.cloudCollabOn', {
      defaultValue: 'Live collaboration is on. Invite teammates to edit together.',
    }),
    joinedAsViewer: () => t('collab.joinedAsViewer', {
      defaultValue: 'Joined as viewer (read-only).',
    }),
    joinedAsEditor: () => t('collab.joinedAsEditor', {
      defaultValue: 'Joined — you can edit and run this workflow.',
    }),
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
