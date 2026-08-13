// Drag-and-drop overlay shown when a DOI's full text is closed-access: the
// visitor drops the paper's PDF and the analysis continues with it.
import { useCallback, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { DoiUploadRequest } from '../doi/doiFlow';

export function DoiUploadOverlay({
  request,
}: {
  request: DoiUploadRequest;
}) {
  const { t } = useTranslation();
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFiles = useCallback(
    (files: FileList | null) => {
      const file = files?.[0];
      if (!file) return;
      request.onFile(file);
    },
    [request],
  );

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 40,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'rgba(0, 0, 0, 0.45)',
      }}
      onDragOver={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragOver(false);
        handleFiles(e.dataTransfer.files);
      }}
    >
      <div
        style={{
          maxWidth: 480,
          margin: 16,
          padding: 28,
          borderRadius: 12,
          background: 'var(--panel, #fff)',
          color: 'var(--fg, #0f172a)',
          boxShadow: '0 20px 60px rgba(0,0,0,0.35)',
          textAlign: 'center',
        }}
      >
        <h2 style={{ margin: '0 0 8px', fontSize: 20, fontWeight: 700 }}>
          {t('doiFlow.uploadTitle', { defaultValue: 'We need the PDF for this one' })}
        </h2>
        <p style={{ margin: '0 0 4px', fontSize: 14, color: 'var(--muted, #64748b)' }}>
          {request.paperTitle}
        </p>
        <p style={{ margin: '0 0 20px', fontSize: 14, color: 'var(--muted, #64748b)' }}>
          {t('doiFlow.uploadBody', {
            defaultValue:
              "This paper's full text isn't openly accessible. Drop the PDF here and the AI will build the workflow from it.",
          })}
        </p>
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          style={{
            display: 'block',
            width: '100%',
            padding: '28px 16px',
            borderRadius: 10,
            border: `2px dashed ${dragOver ? 'var(--primary, #6366f1)' : 'var(--border, #cbd5e1)'}`,
            background: dragOver ? 'var(--primary-soft, rgba(99,102,241,0.08))' : 'transparent',
            color: 'var(--fg, #0f172a)',
            fontSize: 14,
            cursor: 'pointer',
          }}
        >
          {t('doiFlow.uploadDropzone', { defaultValue: 'Drop the PDF here, or click to browse' })}
        </button>
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf,.pdf"
          style={{ display: 'none' }}
          onChange={(e) => handleFiles(e.target.files)}
        />
        <button
          type="button"
          onClick={request.onCancel}
          style={{
            marginTop: 14,
            background: 'none',
            border: 'none',
            color: 'var(--muted, #64748b)',
            fontSize: 13,
            cursor: 'pointer',
            textDecoration: 'underline',
          }}
        >
          {t('doiFlow.uploadCancel', { defaultValue: 'Cancel' })}
        </button>
      </div>
    </div>
  );
}
