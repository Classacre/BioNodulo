import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import './i18n';
import './index.css';
import { bootProgress } from './state/bootLoader';

// The bundle has parsed and i18n/styles are loaded; advance the boot loader so
// the user sees motion even before the app finishes its first data fetches.
bootProgress(35, 'Loading interface…');

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
