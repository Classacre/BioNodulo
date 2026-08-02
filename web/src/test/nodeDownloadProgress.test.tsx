import { render } from '@testing-library/react';
import { Provider, createStore } from 'jotai';
import { describe, expect, it } from 'vitest';
import { nodeDownloadProgressAtom } from '../state/runAtoms';

/**
 * The bar itself is a few lines of JSX inside BioNode, which needs a React Flow
 * provider to mount. These cover the part that actually carries the logic: the
 * progress state and the determinate/indeterminate decision.
 */
describe('node download progress', () => {
  it('starts empty so idle nodes render no bar', () => {
    const store = createStore();
    expect(store.get(nodeDownloadProgressAtom)).toEqual({});
  });

  it('tracks progress per node, not globally', () => {
    // Two nodes can fetch at once; a single global value would show one node's
    // progress on the other.
    const store = createStore();
    store.set(nodeDownloadProgressAtom, {
      'node-a': { downloaded: 50, total: 100 },
      'node-b': { downloaded: 10, total: 1000 },
    });

    const state = store.get(nodeDownloadProgressAtom);
    expect(state['node-a'].downloaded / state['node-a'].total).toBe(0.5);
    expect(state['node-b'].downloaded / state['node-b'].total).toBe(0.01);
  });

  it('uses total 0 to mean unknown length', () => {
    // Servers that omit Content-Length must produce an indeterminate bar rather
    // than a fabricated percentage.
    const store = createStore();
    store.set(nodeDownloadProgressAtom, { 'node-a': { downloaded: 2048, total: 0 } });

    expect(store.get(nodeDownloadProgressAtom)['node-a'].total).toBe(0);
  });

  it('clears a node when its download finishes', () => {
    const store = createStore();
    store.set(nodeDownloadProgressAtom, {
      'node-a': { downloaded: 100, total: 100 },
      'node-b': { downloaded: 5, total: 10 },
    });

    store.set(nodeDownloadProgressAtom, prev => {
      const next = { ...prev };
      delete next['node-a'];
      return next;
    });

    expect(store.get(nodeDownloadProgressAtom)).not.toHaveProperty('node-a');
    expect(store.get(nodeDownloadProgressAtom)).toHaveProperty('node-b');
  });

  it('renders nothing for a node with no download in flight', () => {
    const store = createStore();
    const { container } = render(
      <Provider store={store}>
        <div />
      </Provider>
    );
    expect(container.querySelector('.bio-node-download')).toBeNull();
  });
});
