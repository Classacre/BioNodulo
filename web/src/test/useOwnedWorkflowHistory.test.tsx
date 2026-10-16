import { act, renderHook } from '@testing-library/react';
import { useLayoutEffect, useState } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useOwnedWorkflowHistory, useOwnershipEpoch } from '../hooks/workflow/useOwnedWorkflowHistory';
import type { Workflow } from '../types';

function graph(id: string, label: string): Workflow {
  return { id, name: label, version: '2.0', app: 'bionodulo', description: '',
    nodes: [{ id: label, type: 'string', position: { x: 0, y: 0 }, params: { value: label } }],
    edges: [], groups: [], parameters: [], outputs: {} };
}

describe('workflow history ownership', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  function setup(initial = graph('doc-a', 'private A')) {
    const apply = vi.fn();
    const viewport = { x: 5, y: 6, scale: 1.5 };
    const props = { owner: 'user-a.team-a', documentId: initial.id!, workflow: initial };
    const hook = renderHook((value: typeof props) => useOwnedWorkflowHistory({ ...value, apply, getViewport: () => viewport }),
      { initialProps: props });
    return { ...hook, apply, viewport, props };
  }

  it('seeds the pre-edit graph and supports undo before the 350 ms flush, then redo', () => {
    const { result, rerender, apply, viewport, props } = setup();
    const edited = graph('doc-a', 'edited A');
    act(() => { expect(result.current.queuePatch({ nodes: edited.nodes })).toBe(true); });
    rerender({ ...props, workflow: edited });
    act(() => vi.advanceTimersByTime(349));
    act(() => result.current.undo());
    expect(apply).toHaveBeenLastCalledWith(expect.objectContaining({ nodes: props.workflow.nodes, viewport }));
    rerender({ ...props, workflow: { ...edited, ...apply.mock.lastCall![0] } });
    act(() => result.current.redo());
    expect(apply).toHaveBeenLastCalledWith(expect.objectContaining({ nodes: edited.nodes }));
  });

  it('commits a pending graph after 350 ms and deduplicates identical edits', () => {
    const { result, rerender, apply, props } = setup();
    const edited = graph('doc-a', 'edited A');
    act(() => { result.current.queuePatch({ nodes: edited.nodes }); });
    rerender({ ...props, workflow: edited });
    act(() => vi.advanceTimersByTime(350));
    act(() => { result.current.queuePatch({ nodes: edited.nodes }); result.current.pushHistory(); });
    act(() => result.current.undo());
    expect(apply).toHaveBeenLastCalledWith(expect.objectContaining({ nodes: props.workflow.nodes }));
    rerender({ ...props, workflow: { ...edited, ...apply.mock.lastCall![0] } });
    act(() => result.current.undo());
    expect(apply).toHaveBeenCalledTimes(1);
  });

  it('preserves post-insert fit and manual pan through real Undo/Redo without extra graph steps', () => {
    const initial = graph('doc-a', 'original');
    const originalView = { x: 10, y: 20, scale: 1 };
    const fittedView = { x: -300, y: 40, scale: 0.5 };
    const pannedView = { x: 90, y: -25, scale: 1.2 };
    let viewport = originalView;
    const getViewport = vi.fn(() => viewport);
    const applied = vi.fn();
    const { result, unmount } = renderHook(() => {
      const [workflow, setWorkflow] = useState(initial);
      const history = useOwnedWorkflowHistory({ owner: 'owner', documentId: 'doc-a', workflow, getViewport,
        apply: value => {
          applied(value);
          if (value.viewport) viewport = value.viewport;
          setWorkflow(previous => ({ ...previous, ...value }));
        } });
      return { workflow, history };
    });
    const inserted = graph('doc-a', 'inserted');
    act(() => { result.current.history.commitPatch({ nodes: [...initial.nodes, ...inserted.nodes] }); });
    viewport = fittedView; // Post-render fit does not create a graph edit.
    applied.mockClear();
    act(() => result.current.history.undo());
    expect(result.current.workflow.nodes).toEqual(initial.nodes);
    expect(viewport).toEqual(originalView);
    expect(applied).toHaveBeenCalledOnce();

    viewport = pannedView;
    getViewport.mockClear(); applied.mockClear();
    act(() => result.current.history.undo()); // Boundary remains a true no-op.
    expect(getViewport).not.toHaveBeenCalled();
    expect(applied).not.toHaveBeenCalled();
    expect(viewport).toEqual(pannedView);
    act(() => result.current.history.redo());
    expect(result.current.workflow.nodes).toHaveLength(2);
    expect(viewport).toEqual(fittedView);
    act(() => result.current.history.undo());
    expect(result.current.workflow.nodes).toEqual(initial.nodes);
    expect(viewport).toEqual(pannedView);
    unmount();
  });

  it('snapshots parameter-only edits, deduplicates equal values, and restores them through undo and redo', () => {
    const initial = graph('doc-a', 'unchanged nodes');
    initial.parameters = [{ name: 'threshold', type: 'number', default: 1 }];
    const { result, rerender, apply, viewport, props } = setup(initial);
    const edited = { ...initial, parameters: [{ name: 'threshold', type: 'number', default: 2 }] };
    act(() => { result.current.queuePatch({ parameters: edited.parameters }); });
    rerender({ ...props, workflow: edited });
    act(() => vi.advanceTimersByTime(350));

    const duplicate = { ...edited, parameters: edited.parameters.map(value => ({ ...value })) };
    act(() => { result.current.queuePatch({ parameters: duplicate.parameters }); });
    rerender({ ...props, workflow: duplicate });
    act(() => vi.advanceTimersByTime(350));
    act(() => result.current.undo());
    expect(apply).toHaveBeenLastCalledWith(expect.objectContaining({
      parameters: initial.parameters, nodes: initial.nodes, viewport,
    }));
    rerender({ ...props, workflow: { ...duplicate, ...apply.mock.lastCall![0] } });
    act(() => result.current.undo());
    expect(apply).toHaveBeenCalledTimes(1);
    act(() => result.current.redo());
    expect(apply).toHaveBeenLastCalledWith(expect.objectContaining({ parameters: edited.parameters }));
  });

  it('rejects old pending timers, undo, redo and node/edge callbacks after a same-index document replacement', () => {
    const { result, rerender, apply, props } = setup();
    const old = result.current;
    const bridge = vi.fn();
    const staleNodeCallback = () => { if (old.queuePatch({ nodes: graph('doc-a', 'leak A').nodes })) bridge('nodes'); };
    const staleEdgeCallback = () => { if (old.queuePatch({ edges: [] })) bridge('edges'); };
    act(() => { old.queuePatch({ nodes: graph('doc-a', 'pending A').nodes }); });
    rerender({ ...props, workflow: graph('doc-a', 'pending A') });
    rerender({ ...props, documentId: 'doc-b', workflow: graph('doc-b', 'private B') });
    act(() => { staleNodeCallback(); staleEdgeCallback(); old.pushHistory(); old.undo(); old.redo(); vi.advanceTimersByTime(500); });
    expect(old.isCurrent()).toBe(false);
    expect(bridge).not.toHaveBeenCalled();
    expect(apply).not.toHaveBeenCalled();
    act(() => { result.current.undo(); result.current.redo(); });
    expect(apply).not.toHaveBeenCalled();
  });

  it('does not revive stale A closures across A to B to A, even with the same document ID', () => {
    const { result, rerender, apply, props } = setup();
    const old = result.current;
    act(() => { old.queuePatch({ nodes: graph('doc-a', 'pending old A').nodes }); });
    rerender({ ...props, owner: 'user-b.team-a', workflow: graph('doc-a', 'private B') });
    rerender(props);
    act(() => { expect(old.queuePatch({ nodes: graph('doc-a', 'leak A').nodes })).toBe(false); old.pushHistory(); old.undo(); old.redo(); vi.advanceTimersByTime(500); });
    expect(old.isCurrent()).toBe(false);
    expect(result.current.isCurrent()).toBe(true);
    expect(apply).not.toHaveBeenCalled();
  });

  it('rejects an old callback during the new document layout, before passive cleanup can run', () => {
    const apply = vi.fn();
    const bridge = vi.fn();
    let old: ReturnType<typeof useOwnedWorkflowHistory> | undefined;
    const { result, rerender } = renderHook(({ id }) => {
      const history = useOwnedWorkflowHistory({ owner: 'same-owner', documentId: id,
        workflow: graph(id, id), apply, getViewport: () => undefined });
      useLayoutEffect(() => {
        if (id !== 'doc-b' || !old) return;
        if (old.queuePatch({ nodes: graph('doc-a', 'private A').nodes })) bridge();
        old.pushHistory(); old.undo(); old.redo();
      }, [id]);
      return history;
    }, { initialProps: { id: 'doc-a' } });
    old = result.current;
    act(() => { old!.queuePatch({ nodes: graph('doc-a', 'edited A').nodes }); old!.pushHistory(); });
    rerender({ id: 'doc-b' });
    expect(bridge).not.toHaveBeenCalled();
    expect(apply).not.toHaveBeenCalled();
  });

  it('still accepts within-document callbacks after a normal render and drops the redo branch after a fresh edit', () => {
    const { result, rerender, apply, props } = setup();
    const first = result.current;
    const one = graph('doc-a', 'one');
    act(() => { first.queuePatch({ nodes: one.nodes }); });
    rerender({ ...props, workflow: one });
    act(() => vi.advanceTimersByTime(350));
    act(() => result.current.undo());
    rerender({ ...props, workflow: { ...one, ...apply.mock.lastCall![0] } });
    const two = graph('doc-a', 'two');
    act(() => { expect(first.queuePatch({ nodes: two.nodes })).toBe(true); first.pushHistory(); });
    rerender({ ...props, workflow: two });
    apply.mockClear();
    act(() => result.current.redo());
    expect(apply).not.toHaveBeenCalled();
    act(() => result.current.undo());
    expect(apply).toHaveBeenLastCalledWith(expect.objectContaining({ nodes: props.workflow.nodes }));
  });

  it('invalidates callbacks after unmount', () => {
    const { result, unmount, apply } = setup();
    const old = result.current;
    unmount();
    act(() => { expect(old.queuePatch({ nodes: [] })).toBe(false); old.undo(); old.redo(); old.pushHistory(); });
    expect(apply).not.toHaveBeenCalled();
  });

  it('assigns a fresh owner epoch on account, team and invite transitions without serializing credentials', () => {
    const inviteA = { room: 'same-room' };
    const inviteB = { room: 'same-room' };
    const { result, rerender } = renderHook(({ identity, account, invite }) => useOwnershipEpoch(identity, account, invite),
      { initialProps: { identity: '.cloud.user.team-a', account: 'user', invite: inviteA } });
    const a = result.current;
    rerender({ identity: '.cloud.user.team-a', account: 'user', invite: inviteA });
    expect(result.current).toBe(a);
    rerender({ identity: '.cloud.user.team-b', account: 'user', invite: inviteA });
    expect(result.current).not.toBe(a);
    rerender({ identity: '.cloud.user.team-a', account: 'user', invite: inviteA });
    expect(result.current).not.toBe(a);
    const returned = result.current;
    rerender({ identity: '.cloud.user.team-a', account: 'other-user', invite: inviteA });
    expect(result.current).not.toBe(returned);
    const account = result.current;
    rerender({ identity: '.cloud.user.team-a', account: 'other-user', invite: inviteB });
    expect(result.current).not.toBe(account);
  });
});
