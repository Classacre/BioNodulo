import type { TFunction } from 'i18next';

export interface AppFileActionCopy {
  fileTypeFallback: string;
  toast: {
    pastedFileAdded: string;
    fileDropped: string;
  };
  error: {
    missingInputFileForPaste: string;
    couldNotUploadPastedFile: string;
    missingInputFileForDrop: string;
  };
}

export function makeAppFileActionCopy(t: TFunction): AppFileActionCopy {
  return {
    fileTypeFallback: t('workspace.fileTypeFallback'),
    toast: {
      pastedFileAdded: t('workspace.pastedFileAdded'),
      fileDropped: t('workspace.fileDropped'),
    },
    error: {
      missingInputFileForPaste: t('workspace.missingInputFileForPaste'),
      couldNotUploadPastedFile: t('workspace.couldNotUploadPastedFile'),
      missingInputFileForDrop: t('workspace.missingInputFileForDrop'),
    },
  };
}
