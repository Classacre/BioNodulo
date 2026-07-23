import { describe, expect, it } from 'vitest';
import fixture from '../../../tests/fixtures/samtools_first_wave/workflow.json';
import type { Workflow } from '../types';
import {
  catalogCanaryForWorkflow,
  isSamtoolsFirstWaveCanaryWorkflow,
  SAMTOOLS_FIRST_WAVE_CATALOG_DIGEST,
  SAMTOOLS_FIRST_WAVE_INPUT_SHA256,
} from '../utils/catalogCanary';

function canary(): Workflow {
  return structuredClone(fixture) as unknown as Workflow;
}

describe('Samtools catalog canary selector', () => {
  it('selects the exact committed semantic workflow', () => {
    expect(catalogCanaryForWorkflow(canary())).toEqual({
      profile: 'samtools-first-wave',
      catalog_digest: SAMTOOLS_FIRST_WAVE_CATALOG_DIGEST,
    });
    expect(SAMTOOLS_FIRST_WAVE_INPUT_SHA256).toBe(
      'sha256:0b621dee8e14e8ebf5e52772c3c6695b47c312e5190b52591644ce872ee422c7',
    );
  });

  it('permits only a consistent template instance-ID remap', () => {
    const workflow = canary();
    const remap = new Map<string, string>();
    workflow.nodes = workflow.nodes.map((node, index) => {
      const id = `${node.type}_instance_${index}`;
      remap.set(node.id, id);
      return { ...node, id };
    });
    workflow.edges = workflow.edges.map((edge, index) => ({
      ...edge,
      id: `edge_instance_${index}`,
      from: { ...edge.from, node: remap.get(edge.from.node) ?? edge.from.node },
      to: { ...edge.to, node: remap.get(edge.to.node) ?? edge.to.node },
    }));
    workflow.outputs = Object.fromEntries(
      Object.entries(workflow.outputs).map(([name, nodeId]) => [name, remap.get(nodeId) ?? nodeId]),
    );

    expect(isSamtoolsFirstWaveCanaryWorkflow(workflow)).toBe(true);
    workflow.outputs.bai = 'index_001';
    expect(isSamtoolsFirstWaveCanaryWorkflow(workflow)).toBe(false);
  });

  it.each([
    [
      'pinned URL',
      (workflow: Workflow) => {
        workflow.nodes[0].params.file = 'https://example.invalid/tiny.sam';
      },
    ],
    [
      'node parameter',
      (workflow: Workflow) => {
        workflow.nodes[3].params.add_markdup_tags = false;
      },
    ],
    [
      'edge port',
      (workflow: Workflow) => {
        workflow.edges[4].from.output = 'bam';
      },
    ],
    [
      'execution modifier',
      (workflow: Workflow) => {
        workflow.nodes[4].ui = { ...workflow.nodes[4].ui, muted: true };
      },
    ],
    [
      'extra node',
      (workflow: Workflow) => {
        workflow.nodes.push(structuredClone(workflow.nodes[7]));
      },
    ],
  ])('rejects a changed %s', (_label, mutate) => {
    const workflow = canary();
    mutate(workflow);
    expect(catalogCanaryForWorkflow(workflow)).toBeUndefined();
  });
});
