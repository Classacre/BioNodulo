import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './i18n';
import './index.css';
import { bootProgress } from './state/bootLoader';

// The bundle has parsed and i18n/styles are loaded; advance the boot loader so
// the user sees motion even before the app finishes its first data fetches.
bootProgress(35, 'Loading interface…');

// Resources use an opaque host URL, so accept the server-injected marker too.
const mcpApp = document.documentElement.dataset.mcpApp === 'true'
  || new URLSearchParams(window.location.search).get('mcp_app') === '1';
if (mcpApp) {
  document.documentElement.dataset.mcpApp = 'true';
  void import('./mcp');
} else {
  void import('./App').then(({ default: App }) => {
    createRoot(document.getElementById('root')!).render(<StrictMode><App /></StrictMode>);
  });
}
