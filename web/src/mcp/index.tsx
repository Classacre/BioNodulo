import { createRoot } from 'react-dom/client';
import { setSettingsEditorMode } from '../hooks/settings/useSettings';
import { createWorkbenchHost } from './host';
import { McpCloudRuntime, installMcpRuntime } from './runtime';
import { getDefaultStore } from 'jotai';
import { cloudConfigAtom, requestedWorkflowIdAtom } from '../state/appAtoms';
import { bootDone } from '../state/bootLoader';

// Mount the exact cloud application after the host verifies its account. Seed
// editor mode before any hook runs so no local settings/socket/Clerk bootstrap
// can start, even in a development build without the cloud Vite flags.
setSettingsEditorMode(true);
const host = createWorkbenchHost();
const runtime = new McpCloudRuntime(host);
installMcpRuntime(runtime);
// Shared cloud panels use ordinary HTTPS anchors. Open them through the host,
// which controls navigation from its sandbox, rather than relying on popups.
document.addEventListener('click', event => {
  const link = event.target instanceof Element ? event.target.closest('a[href]') : null;
  if (!(link instanceof HTMLAnchorElement) || !link.href.startsWith('https://') || link.hasAttribute('download')) return;
  event.preventDefault();
  void runtime.openLink(link.href).catch(async error => {
    const { toast } = await import('../components/ui');
    toast.error('Could not open link', { message: error instanceof Error ? error.message : String(error) });
  });
});
const root = createRoot(document.getElementById('root')!);
void runtime.connect().then(async config => {
  const store = getDefaultStore();
  store.set(cloudConfigAtom, config);
  store.set(requestedWorkflowIdAtom, runtime.initialContext?.workflow_id || null);
  const { default: App } = await import('../App');
  root.render(<App />);
}).catch(error => {
  bootDone();
  root.render(<main role="alert"><h1>BioNodulo could not connect</h1><p>{error instanceof Error ? error.message : 'Reconnect the cloud app and try again.'}</p><button onClick={() => window.location.reload()}>Reconnect</button></main>);
});
