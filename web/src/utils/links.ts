/**
 * External site links. Centralised so product copy and deep links stay in
 * sync with the docs site structure.
 */
export const DOCS_URL = 'https://docs.bionodulo.com';

/**
 * In-app help used to be a panel with fixed wiki page ids. Those ids now
 * deep-link into the equivalent docs.bionodulo.com pages so old entry points
 * (Getting Started modal, custom events) land on the right content.
 */
const HELP_PAGE_DOC_PATHS: Record<string, string> = {
  'getting-started': '/getting-started/introduction',
  'canvas-features': '/core-concepts/canvas-features',
  'nodes-reference': '/node-reference',
  'templates-guide': '/getting-started/templates',
  'custom-nodes': '/getting-started/custom-nodes',
  'hpc-integration': '/desktop/hpc-mode',
  'workflow-converters': '/desktop/importing-workflows',
  'keyboard-shortcuts': '/desktop/keyboard-shortcuts',
};

/** Open docs.bionodulo.com in a new tab; `helpPage` is an old in-app page id. */
export function openDocs(helpPage?: string | null): void {
  const path = (helpPage && HELP_PAGE_DOC_PATHS[helpPage]) || '/';
  window.open(`${DOCS_URL}${path}`, '_blank', 'noopener,noreferrer');
}
