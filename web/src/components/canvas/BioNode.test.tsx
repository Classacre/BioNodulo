import { render, screen } from '@testing-library/react';
import { ReactFlowProvider } from '@xyflow/react';
import type { ComponentProps } from 'react';
import { describe, expect, it } from 'vitest';
import BioNode from './BioNode';
import type { GraphNode } from './canvasModel';

function note(collapsed: boolean): GraphNode {
  return {
    id: 'paper-note', type: 'note', display_name: 'Note', category: 'Utility',
    x: 0, y: 0, width: 320, height: collapsed ? 32 : 180,
    inputs: [], outputs: [], params: { text: 'Long paper source text' },
    promotedInputs: [], meta: null, color: '#64748b', muted: false,
    bypassed: false, selected: false, collapsed, pinned: false, shape: 'card',
    title: 'Paper summary', visualOnly: true, isSubgraph: false,
    inlinePreview: false, previewCollapsed: false, showingPreview: false,
  };
}

function renderNote(collapsed: boolean) {
  const props = {
    id: 'paper-note', selected: false,
    data: { g: note(collapsed), categoryLabel: 'Utility', missingDependency: false, running: false },
  } as unknown as ComponentProps<typeof BioNode>;
  return render(<ReactFlowProvider><BioNode {...props} /></ReactFlowProvider>);
}

describe('note canvas rendering', () => {
  it('keeps long fixed-height note text in an interactive scroll body', () => {
    const { container } = renderNote(false);
    const body = screen.getByText('Long paper source text');
    expect(container.querySelector('.bio-node-note-fixed')).toBeInTheDocument();
    expect(body).toHaveClass('bio-node-note-body', 'nodrag', 'nowheel');
  });

  it('hides the note body when collapsed', () => {
    const { container } = renderNote(true);
    expect(container.querySelector('.bio-node-collapsed')).toBeInTheDocument();
    expect(container.querySelector('.bio-node-note-body')).not.toBeInTheDocument();
    expect(screen.queryByText('Long paper source text')).not.toBeInTheDocument();
  });
});
