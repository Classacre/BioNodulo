import { render, screen } from '@testing-library/react';
import { Provider, createStore } from 'jotai';
import { describe, expect, it, vi } from 'vitest';
import NodeLogsPopover from '../components/canvas/NodeLogsPopover';
import { logsAtom } from '../state/runAtoms';
import type { LogEntry } from '../types';

const entry = (node_id: string, message: string, level: LogEntry['level'] = 'info'): LogEntry => ({
  run_id: 'r1',
  node_id,
  level,
  message,
  timestamp: '2026-08-02T11:22:33.000Z',
});

function renderWith(logs: LogEntry[], nodeId = 'node-a') {
  const store = createStore();
  store.set(logsAtom, logs);
  return render(
    <Provider store={store}>
      <NodeLogsPopover nodeId={nodeId} title="Align reads" x={100} y={100} onClose={vi.fn()} />
    </Provider>
  );
}

describe('NodeLogsPopover', () => {
  it('shows only the lines belonging to that node', () => {
    // The console already shows everything; the point of this panel is the
    // narrowing, so a leaked line from another node defeats it entirely.
    renderWith([
      entry('node-a', 'alpha started'),
      entry('node-b', 'beta started'),
      entry('node-a', 'alpha finished'),
    ]);

    expect(screen.getByText('alpha started')).toBeInTheDocument();
    expect(screen.getByText('alpha finished')).toBeInTheDocument();
    expect(screen.queryByText('beta started')).not.toBeInTheDocument();
  });

  it('says so when a node has produced nothing yet', () => {
    renderWith([entry('node-b', 'unrelated')]);

    expect(screen.getByText(/no logs for this node yet/i)).toBeInTheDocument();
  });

  it('renders the node title rather than the raw id', () => {
    renderWith([entry('node-a', 'alpha')]);

    expect(screen.getByText('Align reads')).toBeInTheDocument();
  });

  it('marks error lines so a failure is visible without reading', () => {
    const { container } = renderWith([entry('node-a', 'it broke', 'error')]);

    expect(container.querySelector('.node-logs-popover-line.is-error')).not.toBeNull();
  });

  it('closes on Escape', () => {
    const onClose = vi.fn();
    const store = createStore();
    store.set(logsAtom, [entry('node-a', 'alpha')]);
    render(
      <Provider store={store}>
        <NodeLogsPopover nodeId="node-a" x={10} y={10} onClose={onClose} />
      </Provider>
    );

    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));

    expect(onClose).toHaveBeenCalled();
  });

  it('stays inside the viewport when opened near an edge', () => {
    // A node at the right/bottom edge would otherwise open a panel half
    // off-screen, which is where you most want to read the logs.
    const store = createStore();
    store.set(logsAtom, [entry('node-a', 'alpha')]);
    const { container } = render(
      <Provider store={store}>
        <NodeLogsPopover nodeId="node-a" x={99999} y={99999} onClose={vi.fn()} />
      </Provider>
    );

    const panel = container.querySelector('.node-logs-popover') as HTMLElement;
    expect(parseInt(panel.style.left, 10)).toBeLessThan(window.innerWidth);
    expect(parseInt(panel.style.top, 10)).toBeLessThan(window.innerHeight);
  });
});
