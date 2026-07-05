// Cloud file transfer engine. Uploads go presign -> S3 PUT via XMLHttpRequest
// (fetch can't report upload progress); downloads stream the presigned GET url
// with progress. Both drive the transfers store so the minimizable window shows
// live progress + speed. Orchestrators return the object key (upload) or void.
import { presignCloudUpload, type CloudFile } from './website';
import { apiRequest } from './client';
import {
  addTransfer, updateTransfer, newTransferId, type Transfer,
} from '../state/transfers';

/** EMA-smoothed bytes/sec tracker for a single transfer. */
function makeSpeedMeter() {
  let lastLoaded = 0;
  let lastTime = performance.now();
  let ema = 0;
  return (loaded: number): number => {
    const now = performance.now();
    const dt = (now - lastTime) / 1000;
    if (dt >= 0.15) {
      const inst = (loaded - lastLoaded) / dt;
      ema = ema === 0 ? inst : ema * 0.7 + inst * 0.3;
      lastLoaded = loaded;
      lastTime = now;
    }
    return Math.max(0, ema);
  };
}

function errMsg(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}

/**
 * Upload a File to the team's cloud storage. Registers a transfer, presigns a
 * PUT, streams the bytes to S3 with progress, and returns the object key (or
 * null on failure/cancel — the transfer entry carries the error).
 */
export async function startCloudUpload(file: File): Promise<string | null> {
  const id = newTransferId();
  const contentType = file.type || 'application/octet-stream';
  const t: Transfer = { id, name: file.name, direction: 'upload', status: 'active', loaded: 0, total: file.size, speedBps: 0 };
  addTransfer(t);

  let presigned: { url: string; key: string };
  try {
    presigned = await presignCloudUpload(file.name, contentType, file.size);
  } catch (e) {
    updateTransfer(id, { status: 'error', error: errMsg(e) });
    return null;
  }

  const speed = makeSpeedMeter();
  return await new Promise<string | null>((resolve) => {
    const xhr = new XMLHttpRequest();
    updateTransfer(id, { abort: () => xhr.abort() });
    xhr.open('PUT', presigned.url, true);
    xhr.setRequestHeader('Content-Type', contentType);
    xhr.upload.onprogress = (ev) => {
      if (!ev.lengthComputable) return;
      updateTransfer(id, { loaded: ev.loaded, total: ev.total, speedBps: speed(ev.loaded) });
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        updateTransfer(id, { status: 'done', loaded: file.size, key: presigned.key, abort: undefined });
        resolve(presigned.key);
      } else {
        updateTransfer(id, { status: 'error', error: `Upload failed (${xhr.status})`, abort: undefined });
        resolve(null);
      }
    };
    xhr.onerror = () => { updateTransfer(id, { status: 'error', error: 'Network error', abort: undefined }); resolve(null); };
    xhr.onabort = () => { updateTransfer(id, { status: 'canceled', abort: undefined }); resolve(null); };
    xhr.send(file);
  });
}

/**
 * Read a LOCAL workspace file's raw bytes (via the local backend) and upload it
 * to cloud storage. Returns the object key, or null on failure. Shared by the
 * Workspace "Send to cloud" action and the Run-on-Cloud file pre-flight.
 */
export async function uploadWorkspaceFileToCloud(path: string, name: string): Promise<string | null> {
  const res = await apiRequest(`/workspace/download?path=${encodeURIComponent(path)}`);
  if (!res.ok) throw new Error(`local read failed (${res.status})`);
  const blob = await res.blob();
  const f = new File([blob], name, { type: blob.type || 'application/octet-stream' });
  return startCloudUpload(f);
}

/**
 * HEAD a local workspace file to get its size without downloading it — used by
 * the Run-on-Cloud pre-flight to decide whether to show the >50 MB prompt.
 */
export async function localFileSize(path: string): Promise<number> {
  try {
    const res = await apiRequest(`/workspace/download?path=${encodeURIComponent(path)}`, { method: 'HEAD' });
    return Number(res.headers.get('content-length') || 0);
  } catch {
    return 0;
  }
}

/**
 * Download a cloud file to the user's computer. Streams the presigned GET url
 * with progress, then triggers a browser save. Resolves when saved (or failed).
 */
export async function startCloudDownload(file: CloudFile): Promise<void> {
  const id = newTransferId();
  addTransfer({ id, name: file.name, direction: 'download', status: 'active', loaded: 0, total: file.size, speedBps: 0 });
  const speed = makeSpeedMeter();
  await new Promise<void>((resolve) => {
    const xhr = new XMLHttpRequest();
    updateTransfer(id, { abort: () => xhr.abort() });
    xhr.open('GET', file.url, true);
    xhr.responseType = 'blob';
    xhr.onprogress = (ev) => {
      if (!ev.lengthComputable) return;
      updateTransfer(id, { loaded: ev.loaded, total: ev.total || file.size, speedBps: speed(ev.loaded) });
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        const url = URL.createObjectURL(xhr.response as Blob);
        const a = document.createElement('a');
        a.href = url; a.download = file.name; a.click();
        setTimeout(() => URL.revokeObjectURL(url), 10_000);
        updateTransfer(id, { status: 'done', loaded: file.size, abort: undefined });
      } else {
        updateTransfer(id, { status: 'error', error: `Download failed (${xhr.status})`, abort: undefined });
      }
      resolve();
    };
    xhr.onerror = () => { updateTransfer(id, { status: 'error', error: 'Network error', abort: undefined }); resolve(); };
    xhr.onabort = () => { updateTransfer(id, { status: 'canceled', abort: undefined }); resolve(); };
    xhr.send();
  });
}
