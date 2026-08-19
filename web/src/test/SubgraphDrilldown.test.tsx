import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { useState } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { WorkflowEdge, WorkflowNode } from '../types';
import WorkflowCanvas from '../components/canvas/WorkflowCanvas';
import { resetSubgraphNavAtom } from '../state/subgraphNav';
import { getDefaultStore } from 'jotai';

// Keep the canvas off the network: settings fall back to localStorage
// defaults, preview/table fetches never fire for this fixture.
vi.mock('../api/client', () => ({
  apiGet: vi.fn().mockRejectedValue(new Error('offline')),
  apiGetText: vi.fn().mockRejectedValue(new Error('offline')),
  apiPost: vi.fn().mockRejectedValue(new Error('offline')),
}));

const store = getDefaultStore();

function innerNode(id: string): WorkflowNode {
  return { id, type: 'python_code', position: [0, 0], params: {} };
}

function makeWorkflow() {
  const sub: WorkflowNode = {
    id: 'sub1',
    type: 'subgraph',
    position: [300, 100],
    params: {
      workflow: {
        version: '2.0',
        app: 'bionodulo',
        name: 'Sub',
        description: '',
        nodes: [innerNode('innerX'), innerNode('innerY')],
        edges: [
          { id: 'e-xy', from: { node: 'innerX', output: 'result' }, to: { node: 'innerY', input: 'data' } },
        ],
        groups: [],
        outputs: {},
      },
      input_ports: [{ name: 'in__innerX__data', type: 'ANY', innerNodeId: 'innerX', innerSlot: 'data' }],
      output_ports: [{ name: 'out__innerY__result', type: 'ANY', innerNodeId: 'innerY', innerSlot: 'result' }],
    },
    ui: { title: 'My Sub' },
  };
  const nodes: WorkflowNode[] = [
    { id: 'inputA', type: 'python_code', position: [0, 100], params: {} },
    sub,
  ];
  const edges: WorkflowEdge[] = [
    { id: 'e1', from: { node: 'inputA', output: 'out' }, to: { node: 'sub1', input: 'in__innerX__data' } },
  ];
  return { nodes, edges };
}

function CanvasHarness() {
  const [wf, setWf] = useState(makeWorkflow);
  return (
    <WorkflowCanvas
      nodes={wf.nodes}
      edges={wf.edges}
      objectInfo={{}}
      workflowId="wf-test"
      workflowName="Root Workflow"
      onNodesChange={(nodes) => setWf(prev => ({ ...prev, nodes }))}
      onEdgesChange={(edges) => setWf(prev => ({ ...prev, edges }))}
      onPushHistory={() => {}}
      onUndo={() => {}}
      onRedo={() => {}}
      snapToGrid={false}
      showMinimap={false}
    />
  );
}

describe('subgraph drill-down (canvas)', () => {
  beforeEach(() => {
    store.set(resetSubgraphNavAtom);
  });

  it('renders subgraph ports from params, enters on double-click, shows inner graph + IO panels, exits on Esc', async () => {
    render(<CanvasHarness />);

    // Parent view: the subgraph node's handles come from its port entries.
    const subNode = await screen.findByText('My Sub');
    expect(subNode).toBeInTheDocument();
    expect(screen.getByText('in__innerX__data')).toBeInTheDocument();
    expect(screen.getByText('out__innerY__result')).toBeInTheDocument();

    // Double-click the subgraph node body to enter it.
    fireEvent.doubleClick(subNode);

    // Breadcrumb shows the path; IO panels and inner nodes render.
    await screen.findByText('Root Workflow');
    expect(screen.getByText('My Sub')).toBeInTheDocument();
    expect(screen.getByText('Subgraph inputs')).toBeInTheDocument();
    expect(screen.getByText('Subgraph outputs')).toBeInTheDocument();
    await waitFor(() => {
      expect(document.querySelector('.bio-node[data-node-id="sub1.innerX"]')).not.toBeNull();
      expect(document.querySelector('.bio-node[data-node-id="sub1.innerY"]')).not.toBeNull();
    });
    // The parent-level node is gone from the inside view.
    expect(document.querySelector('.bio-node[data-node-id="inputA"]')).toBeNull();

    // Esc returns to the root workflow.
    fireEvent.keyDown(document.body, { key: 'Escape' });
    await waitFor(() => {
      expect(document.querySelector('.bio-node[data-node-id="sub1"]')).not.toBeNull();
      expect(document.querySelector('.bio-node[data-node-id="inputA"]')).not.toBeNull();
    });
    expect(screen.queryByText('Subgraph inputs')).not.toBeInTheDocument();
  });
});
