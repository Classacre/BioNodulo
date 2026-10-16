import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { getDefaultStore } from 'jotai';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import WorkflowCanvas from '../components/canvas/WorkflowCanvas';
import { resetSubgraphNavAtom } from '../state/subgraphNav';
import type { ObjectInfo, WorkflowEdge, WorkflowNode } from '../types';

vi.mock('../api/client', () => ({
  apiGet: vi.fn().mockRejectedValue(new Error('offline')),
  apiGetText: vi.fn().mockRejectedValue(new Error('offline')),
  apiPost: vi.fn().mockRejectedValue(new Error('offline')),
}));

const objectInfo: ObjectInfo = {
  while_loop: { id: 'while_loop', display_name: 'Loop', category: 'Control',
    input_types: { required: { value: { type: 'ANY' } }, hidden: { _body_result: { type: 'ANY' } } },
    return_names: ['results'], return_types: ['LIST'] },
  foreach: { id: 'foreach', display_name: 'Each', category: 'Control',
    input_types: { required: { items: { type: 'LIST' } }, hidden: { body_result: { type: 'ANY' } } },
    return_names: ['results'], return_types: ['LIST'] },
};
const nodes: WorkflowNode[] = [
  { id: 'sub', type: 'subgraph', position: [0, 0], params: {
    workflow: { nodes: [], edges: [] }, input_ports: [], output_ports: [],
  }, ui: { title: 'Subgraph' } },
  { id: 'loop', type: 'while_loop', position: [300, 0], params: {} },
  { id: 'each', type: 'foreach', position: [600, 0], params: {} },
];
const edges: WorkflowEdge[] = [
  { id: 'directory', from: { node: 'sub', output: 'subgraph_dir' }, to: { node: 'loop', input: 'value' } },
  { id: 'feedback-loop', from: { node: 'each', output: 'results' }, to: { node: 'loop', input: '_body_result' } },
  { id: 'feedback-each', from: { node: 'loop', output: 'results' }, to: { node: 'each', input: 'body_result' } },
];

function canvas(graphNodes: WorkflowNode[], graphEdges: WorkflowEdge[], onEdgesChange = vi.fn()) {
  return <WorkflowCanvas nodes={graphNodes} edges={graphEdges} objectInfo={objectInfo}
    workflowId="implicit-ports" workflowName="Root" onNodesChange={vi.fn()} onEdgesChange={onEdgesChange}
    onPushHistory={vi.fn()} onUndo={vi.fn()} onRedo={vi.fn()} snapToGrid={false} showMinimap={false} />;
}

describe('actual React Flow implicit handles', () => {
  beforeEach(() => { getDefaultStore().set(resetSubgraphNavAtom); });

  it('adds/removes fixed header handles as edges change without adding body rows or dropping edges', async () => {
    const changed = vi.fn();
    const before = JSON.stringify(edges);
    const view = render(canvas(nodes, [], changed));
    await screen.findByText('Loop');
    const rows = view.container.querySelectorAll('.bio-node-port').length;
    expect(view.container.querySelectorAll('[data-implicit-port]')).toHaveLength(0);

    view.rerender(canvas(nodes, edges, changed));
    await waitFor(() => expect(view.container.querySelectorAll('[data-implicit-port]')).toHaveLength(3));
    for (const [id, name, direction] of [['sub', 'subgraph_dir', 'source'], ['loop', '_body_result', 'target'], ['each', 'body_result', 'target']]) {
      const handle = view.container.querySelector(`.bio-node[data-node-id="${id}"] [data-handleid="${name}"]`);
      expect(handle).toHaveClass('react-flow__handle', direction);
      expect(handle).toHaveStyle({ top: '16px' });
      expect(handle?.closest('.bio-node-io')).toBeNull();
    }
    expect(view.container.querySelectorAll('.bio-node-port')).toHaveLength(rows);
    expect(changed).not.toHaveBeenCalled();
    expect(JSON.stringify(edges)).toBe(before);

    view.rerender(canvas(nodes.map(node => ({ ...node, ui: { ...node.ui, collapsed: true } })), edges, changed));
    await waitFor(() => expect(view.container.querySelectorAll('.bio-node-collapsed')).toHaveLength(3));
    expect(view.container.querySelectorAll('[data-implicit-port]')).toHaveLength(3);
    view.rerender(canvas(nodes, [], changed));
    await waitFor(() => expect(view.container.querySelectorAll('[data-implicit-port]')).toHaveLength(0));
  });

  it('renders namespaced implicit handles after drilling into an embedded subgraph', async () => {
    const parent: WorkflowNode = { id: 'parent', type: 'subgraph', position: [0, 0],
      params: { workflow: { nodes, edges }, input_ports: [], output_ports: [] }, ui: { title: 'Outer group' } };
    const view = render(canvas([parent], []));
    fireEvent.doubleClick(await screen.findByText('Outer group'));
    await waitFor(() => expect(view.container.querySelectorAll('[data-implicit-port]')).toHaveLength(3));
    for (const [id, name] of [['sub', 'subgraph_dir'], ['loop', '_body_result'], ['each', 'body_result']]) {
      expect(view.container.querySelector(`.bio-node[data-node-id="parent.${id}"] [data-handleid="${name}"]`)).toBeInTheDocument();
    }
  });

  it('keeps hidden feedback handles with stale promotion flags and deduplicates them when collapsed', async () => {
    const promoted = nodes.map(node => ({ ...node, ui: { ...node.ui,
      promotedInputs: node.type === 'while_loop' ? ['_body_result'] : node.type === 'foreach' ? ['body_result'] : [],
    } }));
    const view = render(canvas(promoted, edges));
    await waitFor(() => expect(view.container.querySelectorAll('[data-implicit-port]')).toHaveLength(3));
    view.rerender(canvas(promoted.map(node => ({ ...node, ui: { ...node.ui, collapsed: true } })), edges));
    await waitFor(() => expect(view.container.querySelectorAll('.bio-node-collapsed')).toHaveLength(3));
    for (const [id, name] of [['loop', '_body_result'], ['each', 'body_result']]) {
      const handles = view.container.querySelectorAll(`.bio-node[data-node-id="${id}"] [data-handleid="${name}"]`);
      expect(handles).toHaveLength(1);
      expect(handles[0]).toHaveStyle({ top: '16px' });
    }
  });
});
