// Cloud file transfer engine — BACKEND RELAY variant.
//
// Browser origins can't PUT/GET directly to S3 (the uploads bucket's CORS only
// allows the bionodulo.com origins, and the locally-run app is a loopback
// origin). So the local backend performs the S3 transfer server-side and we
// poll its progress registry. Uploads: presign against the cloud (Clerk-authed)
// -> hand the URL + local path to the backend -> it streams the file to S3.
// Downloads: hand the presigned GET URL to the backend -> it saves under
// workspace/cloud-downloads/. Both feed the transfers store / minimizable window.
import { presignCloudUpload, type CloudFile } from './website';
import { apiGet, apiPost, apiRequest } from './client';
import {
  addTransfer, updateTransfer, newTransferId, type Transfer,
} from '../state/transfers';

interface BackendTransfer {
  direction: 'upload' | 'download';
  name: string;
  loaded: number;
  total: number;
  status: 'active' | 'done' | 'error';
  error?: string | null;
}

interface BackendTransferStart {
  transfer_id: string;
  total: number;
  /** Shared-editor Lambdas complete uploads before returning. */
  status?: BackendTransfer['status'];
  error?: string | null;
}

function errMsg(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}
const sleep = (ms: number) => new Promise<void>(r => setTimeout(r, ms));

/** EMA-smoothed bytes/sec tracker for the polled progress. */
function makeSpeedMeter() {
  let lastLoaded = 0;
  let lastTime = performance.now();
  let ema = 0;
  return (loaded: number): number => {
    const now = performance.now();
    const dt = (now - lastTime) / 1000;
    if (dt >= 0.2) {
      const inst = (loaded - lastLoaded) / dt;
      ema = ema === 0 ? inst : ema * 0.7 + inst * 0.3;
      lastLoaded = loaded;
      lastTime = now;
    }
    return Math.max(0, ema);
  };
}

/** Poll the backend transfer registry, mirroring progress into the store. */
async function pollBackendTransfer(backendId: string, storeId: string, fallbackTotal: number): Promise<boolean> {
  const speed = makeSpeedMeter();
  for (;;) {
    let p: BackendTransfer;
    try {
      p = await apiGet<BackendTransfer>(`/workspace/cloud-transfer/${backendId}`);
    } catch (e) {
      updateTransfer(storeId, { status: 'error', error: errMsg(e) });
      return false;
    }
    const total = p.total || fallbackTotal;
    updateTransfer(storeId, { loaded: p.loaded, total, speedBps: speed(p.loaded) });
    if (p.status === 'done') { updateTransfer(storeId, { status: 'done', loaded: total || p.loaded }); return true; }
    if (p.status === 'error') { updateTransfer(storeId, { status: 'error', error: p.error || 'Transfer failed' }); return false; }
    await sleep(500);
  }
}

/** Handle a relay that already finished inside a serverless invocation. */
function completedBackendTransfer(
  start: BackendTransferStart,
  storeId: string,
  fallbackTotal: number,
): boolean | null {
  const total = start.total || fallbackTotal;
  if (start.status === 'done') {
    updateTransfer(storeId, { status: 'done', loaded: total, total });
    return true;
  }
  if (start.status === 'error') {
    updateTransfer(storeId, { status: 'error', error: start.error || 'Transfer failed' });
    return false;
  }
  return null;
}

/**
 * HEAD a local workspace file to get its size (for the presign size check and
 * the Run-on-Cloud >50 MB prompt) without downloading it.
 */
export async function localFileSize(path: string): Promise<number> {
  const res = await apiRequest(`/workspace/download?path=${encodeURIComponent(path)}`, { method: 'HEAD' });
  // The shared Next.js editor proxy cannot safely forward Content-Length after
  // response transformations, so it preserves Lambda's validated HEAD size in
  // a dedicated metadata header. Direct/local backends still use the standard
  // header.
  const raw = res.headers.get('x-bionodulo-file-size') ?? res.headers.get('content-length');
  const size = raw === null ? Number.NaN : Number(raw);
  if (!Number.isSafeInteger(size) || size < 0) {
    throw new Error(`Could not determine a trustworthy size for ${path}`);
  }
  return size;
}

/** Recursively inspect one local directory using the backend's bounded scanner. */
export async function localDirectorySize(path: string): Promise<number> {
  const result = await apiPost<{ bytes: number; entries: number }>('/workspace/cloud-directory-info', { path });
  if (!Number.isSafeInteger(result.bytes) || result.bytes < 0) {
    throw new Error(`Could not determine a trustworthy size for ${path}`);
  }
  return result.bytes;
}

/**
 * Upload a LOCAL workspace file to cloud storage via the backend relay. Presigns
 * against the cloud, then the local backend streams the bytes to S3. Returns the
 * object key, or null on failure. Shared by "Send to cloud" + Run-on-Cloud.
 */
export async function uploadWorkspaceFileToCloud(path: string, name: string): Promise<string | null> {
  const id = newTransferId();
  const t: Transfer = { id, name, direction: 'upload', status: 'active', loaded: 0, total: 0, speedBps: 0 };
  addTransfer(t);
  try {
    const size = await localFileSize(path);
    updateTransfer(id, { total: size });
    const { url, key } = await presignCloudUpload(name, 'application/octet-stream', size);
    const start = await apiPost<BackendTransferStart>('/workspace/cloud-upload', {
      path, url, content_type: 'application/octet-stream', expected_size: size,
    });
    const completed = completedBackendTransfer(start, id, size);
    if (completed !== null) return completed ? key : null;
    const ok = await pollBackendTransfer(start.transfer_id, id, start.total || size);
    return ok ? key : null;
  } catch (e) {
    updateTransfer(id, { status: 'error', error: errMsg(e) });
    return null;
  }
}

interface PreparedDirectoryArchive {
  archive_id: string;
  size: number;
  entries: number;
  name: string;
}

/**
 * Archive a LOCAL workspace directory deterministically, then relay that tar to
 * cloud storage. The worker expands it only after validating every member.
 */
export async function uploadWorkspaceDirectoryToCloud(
  path: string,
  name: string,
): Promise<string | null> {
  const id = newTransferId();
  const t: Transfer = {
    id,
    name,
    direction: 'upload',
    status: 'active',
    loaded: 0,
    total: 0,
    speedBps: 0,
  };
  addTransfer(t);
  let prepared: PreparedDirectoryArchive | null = null;
  let uploadStarted = false;
  try {
    prepared = await apiPost<PreparedDirectoryArchive>('/workspace/cloud-directory-archive', { path });
    updateTransfer(id, { total: prepared.size });
    const { url, key } = await presignCloudUpload(
      prepared.name || `${name}.tar`,
      'application/x-tar',
      prepared.size,
    );
    const start = await apiPost<BackendTransferStart>('/workspace/cloud-upload-directory', {
      archive_id: prepared.archive_id,
      url,
      content_type: 'application/x-tar',
      expected_size: prepared.size,
    });
    uploadStarted = true;
    const completed = completedBackendTransfer(start, id, prepared.size);
    if (completed !== null) return completed ? key : null;
    const ok = await pollBackendTransfer(start.transfer_id, id, start.total || prepared.size);
    return ok ? key : null;
  } catch (e) {
    updateTransfer(id, { status: 'error', error: errMsg(e) });
    return null;
  } finally {
    if (prepared && !uploadStarted) {
      await apiPost('/workspace/cloud-directory-archive/discard', {
        archive_id: prepared.archive_id,
      }).catch(() => undefined);
    }
  }
}

/**
 * Download a cloud file to the local workspace (workspace/cloud-downloads/) via
 * the backend relay. Resolves when saved (or failed).
 */
export async function startCloudDownload(file: CloudFile): Promise<void> {
  const id = newTransferId();
  addTransfer({ id, name: file.name, direction: 'download', status: 'active', loaded: 0, total: file.size, speedBps: 0 });
  try {
    const start = await apiPost<{ transfer_id: string; save_path: string }>('/workspace/cloud-download', {
      url: file.url, name: file.name,
    });
    await pollBackendTransfer(start.transfer_id, id, file.size);
  } catch (e) {
    updateTransfer(id, { status: 'error', error: errMsg(e) });
  }
}
