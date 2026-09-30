import { createRoot } from 'react-dom/client';
import { setSettingsEditorMode } from '../hooks/settings/useSettings';
import { createWorkbenchHost } from './host';
import Workbench from './Workbench';

// Do not import App: this surface has no Clerk bootstrap, backend settings,
// Yjs session, local execution socket, or token/cookie transport.
setSettingsEditorMode(true);
const host = createWorkbenchHost();
createRoot(document.getElementById('root')!).render(<Workbench host={host} />);
