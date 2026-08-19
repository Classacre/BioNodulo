import { createStore } from 'jotai';
import { describe, expect, it } from 'vitest';
import {
  subgraphNavAtom,
  enterSubgraphAtom,
  exitSubgraphAtom,
  jumpToDepthAtom,
  resetSubgraphNavAtom,
  navStackFor,
  MAX_NAV_DEPTH,
} from '../state/subgraphNav';

describe('subgraph navigation stack', () => {
  it('starts empty and reports no stack for any workflow', () => {
    const store = createStore();
    expect(store.get(subgraphNavAtom).stack).toEqual([]);
    expect(navStackFor(store.get(subgraphNavAtom), 'wf-1')).toEqual([]);
  });

  it('pushes a level on enter and pops one on exit', () => {
    const store = createStore();
    store.set(enterSubgraphAtom, { owner: 'wf-1', level: { nodeId: 'sub1', title: 'Sub 1' } });
    expect(navStackFor(store.get(subgraphNavAtom), 'wf-1')).toEqual([{ nodeId: 'sub1', title: 'Sub 1' }]);

    store.set(exitSubgraphAtom, 'wf-1');
    expect(navStackFor(store.get(subgraphNavAtom), 'wf-1')).toEqual([]);
  });

  it('supports nesting: the stack grows one entry per level', () => {
    const store = createStore();
    store.set(enterSubgraphAtom, { owner: 'wf-1', level: { nodeId: 'sub1', title: 'Outer' } });
    store.set(enterSubgraphAtom, { owner: 'wf-1', level: { nodeId: 'sub2', title: 'Inner' } });
    expect(navStackFor(store.get(subgraphNavAtom), 'wf-1').map(l => l.nodeId)).toEqual(['sub1', 'sub2']);

    // Breadcrumb jump straight to the root, then a partial jump.
    store.set(jumpToDepthAtom, { owner: 'wf-1', depth: 0 });
    expect(navStackFor(store.get(subgraphNavAtom), 'wf-1')).toEqual([]);
    store.set(enterSubgraphAtom, { owner: 'wf-1', level: { nodeId: 'sub1', title: 'Outer' } });
    store.set(enterSubgraphAtom, { owner: 'wf-1', level: { nodeId: 'sub2', title: 'Inner' } });
    store.set(jumpToDepthAtom, { owner: 'wf-1', depth: 1 });
    expect(navStackFor(store.get(subgraphNavAtom), 'wf-1').map(l => l.nodeId)).toEqual(['sub1']);
  });

  it('scopes the stack to its owning workflow — other tabs see an empty stack', () => {
    const store = createStore();
    store.set(enterSubgraphAtom, { owner: 'wf-1', level: { nodeId: 'sub1', title: 'Sub 1' } });
    // Switching tabs must never leave the canvas inside another workflow's
    // subgraph.
    expect(navStackFor(store.get(subgraphNavAtom), 'wf-2')).toEqual([]);
    // Entering from a different owner starts a fresh stack rather than
    // appending to the old owner's.
    store.set(enterSubgraphAtom, { owner: 'wf-2', level: { nodeId: 'other', title: 'Other' } });
    expect(navStackFor(store.get(subgraphNavAtom), 'wf-2').map(l => l.nodeId)).toEqual(['other']);
    expect(navStackFor(store.get(subgraphNavAtom), 'wf-1')).toEqual([]);
  });

  it('guards the recursion depth', () => {
    const store = createStore();
    for (let i = 0; i < MAX_NAV_DEPTH + 20; i += 1) {
      store.set(enterSubgraphAtom, { owner: 'wf-1', level: { nodeId: `sub${i}`, title: `${i}` } });
    }
    expect(navStackFor(store.get(subgraphNavAtom), 'wf-1')).toHaveLength(MAX_NAV_DEPTH);
  });

  it('reset clears owner and stack', () => {
    const store = createStore();
    store.set(enterSubgraphAtom, { owner: 'wf-1', level: { nodeId: 'sub1', title: 'Sub 1' } });
    store.set(resetSubgraphNavAtom);
    expect(store.get(subgraphNavAtom)).toEqual({ owner: null, stack: [] });
  });
});
