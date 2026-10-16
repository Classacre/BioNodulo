import type { CloudRunOutput } from '../types';
import { safeHttpsUrl } from '../mcp/host';
import { getMcpRuntime } from '../mcp/runtime';

/** Open a fresh, manifest-verified attachment URL without buffering file bytes.
 * The server signs Content-Disposition: attachment so cross-origin files also
 * download when browsers ignore the anchor's download attribute.
 */
export async function openVerifiedCloudDownload(output: CloudRunOutput): Promise<void> {
  const url = safeHttpsUrl(output.url);
  const runtime = getMcpRuntime();
  if (runtime) {
    await runtime.openLink(url);
    return;
  }
  const basename = output.name.split(/[\\/]/).pop() || 'download';
  const filename = Array.from(basename).filter(character => character.charCodeAt(0) >= 32 && character.charCodeAt(0) !== 127).join('').trim() || 'download';
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.rel = 'noopener noreferrer';
  link.referrerPolicy = 'no-referrer';
  link.style.display = 'none';
  document.body.appendChild(link);
  try {
    link.click();
  } finally {
    link.remove();
  }
}
