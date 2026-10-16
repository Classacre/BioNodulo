import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { useAtom, useAtomValue } from 'jotai';
import { call, getCloudOutputPreview } from '../../api/website';
import { cloudConfigAtom } from '../../state/appAtoms';
import { cloudInviteSessionAtom } from '../../collab/cloudInvite';
import { cloudPreviewSelectionAtom } from '../../state/cloudPreview';
import { cloudLogStorageKey } from '../../hooks/cloud/useCloudLogStorage';
import { CLOUD_PREVIEW_MAX_BYTES, cloudHtmlPreviewFallback, cloudPreviewKind, sandboxedCloudHtml } from '../../utils/cloudPreview';
import { openVerifiedCloudDownload } from '../../utils/cloudOutputDownload';
import { useOwnershipEpoch } from '../../hooks/workflow/useOwnedWorkflowHistory';
import { useFocusTrap } from '../../hooks/ui/useFocusTrap';
import type { CloudRunOutput } from '../../types';

export default function CloudOutputPreviewModal() {
  const [selection, setSelection] = useAtom(cloudPreviewSelectionAtom);
  const config = useAtomValue(cloudConfigAtom);
  const teamId = config?.team?.id;
  const invite = useAtomValue(cloudInviteSessionAtom);
  const scope = !invite || invite.member ? cloudLogStorageKey(config?.user?.id, config?.team?.id) : null;
  const [loaded, setLoaded] = useState<{ selection: typeof selection; url?: string; text?: string; error?: string } | null>(null);
  const [downloadError, setDownloadError] = useState<{ selection: typeof selection; message: string } | null>(null);
  const downloadEpoch = useOwnershipEpoch(JSON.stringify([scope, selection?.runId, selection?.output.key]), config?.user?.id ?? null, invite);
  const currentDownloadOwner = useRef<object | null>(downloadEpoch);
  currentDownloadOwner.current = downloadEpoch;
  const currentSelection = useRef(selection);
  currentSelection.current = selection?.scope === scope ? selection : null;
  useLayoutEffect(() => {
    currentSelection.current = selection?.scope === scope ? selection : null;
    currentDownloadOwner.current = downloadEpoch;
    return () => { currentSelection.current = null; currentDownloadOwner.current = null; };
  }, [downloadEpoch, scope, selection]);
  const active = selection !== null && selection.scope === scope;
  const dialogRef = useRef<HTMLElement | null>(null);
  useFocusTrap(dialogRef, active, () => setSelection(null));

  useEffect(() => {
    if (!active || !selection || !teamId) { setSelection(null); return; }
    const controller = new AbortController();
    let cancelled = false;
    let objectUrl: string | undefined;
    setLoaded(null);
    setDownloadError(null);
    if (selection.output.size > CLOUD_PREVIEW_MAX_BYTES) {
      setLoaded({ selection, error: 'This output exceeds the 2 MiB preview limit. Download it to view the complete file.' });
      return () => controller.abort();
    }
    void getCloudOutputPreview(selection.runId, selection.output.key, controller.signal, teamId).then(async blob => {
      if (cancelled) return;
      if (blob.size !== selection.output.size) throw new Error('The preview does not match the verified output size.');
      if (cloudPreviewKind(selection.output) === 'image') {
        objectUrl = URL.createObjectURL(blob);
        setLoaded({ selection, url: objectUrl });
      } else {
        const text = await blob.text();
        if (!cancelled) {
          const fallback = cloudPreviewKind(selection.output) === 'html' ? cloudHtmlPreviewFallback(text) : null;
          setLoaded(fallback ? { selection, error: fallback } : { selection, text });
        }
      }
    }).catch(error => {
      if (!cancelled) setLoaded({ selection, error: error instanceof Error ? error.message : 'Could not preview this output. Download it instead.' });
    });
    return () => { cancelled = true; controller.abort(); if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [active, selection, setSelection, teamId]);

  useEffect(() => {
    if (!active) return;
    const onKey = (event: KeyboardEvent) => { if (event.key === 'Escape') setSelection(null); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [active, setSelection]);

  if (!active || !selection) return null;
  const content = loaded?.selection === selection ? loaded : null;
  const kind = cloudPreviewKind(selection.output);
  const download = async () => {
    setDownloadError(null);
    try {
      const { outputs } = await call<{ outputs: CloudRunOutput[] }>(`/runs/${encodeURIComponent(selection.runId)}/outputs`);
      if (currentSelection.current !== selection || currentDownloadOwner.current !== downloadEpoch) return;
      const output = outputs.find(item => item.key === selection.output.key);
      if (!output?.url) throw new Error('This verified output is no longer available.');
      if (output.size !== selection.output.size || output.sha256 !== selection.output.sha256) throw new Error('This output changed. Refresh the run before downloading.');
      await openVerifiedCloudDownload(output);
    } catch (error) {
      if (currentSelection.current === selection && currentDownloadOwner.current === downloadEpoch) setDownloadError({ selection, message: error instanceof Error ? error.message : 'Download unavailable.' });
    }
  };
  return <div className="lightbox-overlay" onClick={event => { if (event.target === event.currentTarget) setSelection(null); }}>
    <section ref={dialogRef} role="dialog" aria-modal="true" aria-label="Verified cloud output preview" style={{ position: 'absolute', inset: '24px', display: 'flex', flexDirection: 'column', overflow: 'hidden', borderRadius: 8, background: 'var(--surface)', color: 'var(--text)' }}>
      <header style={{ display: 'flex', alignItems: 'center', gap: 8, padding: 12, minWidth: 0, flexWrap: 'wrap', borderBottom: '1px solid var(--border)' }}>
        <strong title={selection.output.name} style={{ flex: '1 1 180px', minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{selection.output.name}</strong>
        <span style={{ fontSize: 12 }}>Run {selection.runId.slice(0, 8)}</span>
        <button className="btn btn-sm" onClick={() => { void download(); }}>Download</button>
        <button className="btn btn-sm" aria-label="Close cloud preview" onClick={() => setSelection(null)}>Close</button>
      </header>
      {downloadError?.selection === selection && <p role="alert" style={{ padding: 12 }}>{downloadError.message}</p>}
      {!content && <p role="status" style={{ padding: 16 }}>Loading verified output…</p>}
      {content?.error && <p role="alert" style={{ padding: 16 }}>{content.error}</p>}
      {content?.url && <div style={{ flex: 1, minHeight: 0, overflow: 'auto', display: 'grid', placeItems: 'center' }}><img src={content.url} alt={selection.output.name} style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }} /></div>}
      {content?.text !== undefined && kind === 'html' && <>
        <p style={{ margin: 0, padding: '6px 12px', fontSize: 12 }}>External assets and interactive scripts are disabled in this preview. Download the complete report when needed.</p>
        <iframe title={selection.output.name} sandbox="" referrerPolicy="no-referrer" srcDoc={sandboxedCloudHtml(content.text)} style={{ flex: 1, minHeight: 0, width: '100%', border: 0, background: '#fff' }} />
      </>}
      {content?.text !== undefined && kind === 'text' && <pre style={{ flex: 1, minHeight: 0, margin: 0, padding: 16, overflow: 'auto', whiteSpace: 'pre' }}>{content.text}</pre>}
    </section>
  </div>;
}
