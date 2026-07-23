import type { Workflow } from '../types';

export const SAMTOOLS_FIRST_WAVE_CANARY_PROFILE = 'samtools-first-wave' as const;
export const SAMTOOLS_FIRST_WAVE_CATALOG_DIGEST =
  'sha256:bee248d86257ab760c9492f0774ab5195d82f0743f46412ed81726ecba50ce52' as const;
export const SAMTOOLS_FIRST_WAVE_INPUT_URL =
  'https://raw.githubusercontent.com/Classacre/BioNodulo/2316c3ca54326229fe0aa236868369cfd442bfbd/tests/fixtures/samtools_first_wave/tiny.sam' as const;
export const SAMTOOLS_FIRST_WAVE_INPUT_SHA256 =
  'sha256:0b621dee8e14e8ebf5e52772c3c6695b47c312e5190b52591644ce872ee422c7' as const;

export interface CatalogCanarySelector {
  profile: typeof SAMTOOLS_FIRST_WAVE_CANARY_PROFILE;
  catalog_digest: typeof SAMTOOLS_FIRST_WAVE_CATALOG_DIGEST;
}

const SAMTOOLS_FIRST_WAVE_SELECTOR: CatalogCanarySelector = Object.freeze({
  profile: SAMTOOLS_FIRST_WAVE_CANARY_PROFILE,
  catalog_digest: SAMTOOLS_FIRST_WAVE_CATALOG_DIGEST,
});

const EXPECTED_NODES = [
  {
    type: 'input_file',
    params: { file: SAMTOOLS_FIRST_WAVE_INPUT_URL, source: 'url' },
    title: 'Pinned tiny.sam',
  },
  { type: 'samtools_view', params: {}, title: 'Samtools View' },
  { type: 'samtools_collate', params: {}, title: 'Samtools Collate' },
  {
    type: 'samtools_fixmate',
    params: { add_markdup_tags: true },
    title: 'Samtools Fixmate',
  },
  { type: 'samtools_sort', params: {}, title: 'Samtools Sort' },
  { type: 'samtools_markdup', params: {}, title: 'Samtools Markdup' },
  { type: 'samtools_index', params: {}, title: 'Samtools Index' },
  { type: 'samtools_flagstat', params: {}, title: 'Samtools Flagstat' },
] as const;

const EXPECTED_EDGES = [
  [0, 'file', 1, 'alignment'],
  [1, 'bam', 2, 'bam'],
  [2, 'name_collated_bam', 3, 'bam'],
  [3, 'fixmate_bam', 4, 'alignment'],
  [4, 'sorted_bam', 5, 'bam'],
  [5, 'marked_bam', 6, 'bam'],
  [6, 'indexed_bam', 7, 'bam'],
] as const;

const EXPECTED_OUTPUTS = {
  indexed_bam: 6,
  bai: 6,
  flagstat: 7,
  duplicate_stats: 5,
} as const;

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function jsonEqual(left: unknown, right: unknown): boolean {
  if (left === right) return true;
  if (Array.isArray(left) || Array.isArray(right)) {
    return (
      Array.isArray(left) &&
      Array.isArray(right) &&
      left.length === right.length &&
      left.every((item, index) => jsonEqual(item, right[index]))
    );
  }
  if (!isRecord(left) || !isRecord(right)) return false;
  const leftKeys = Object.keys(left).sort();
  const rightKeys = Object.keys(right).sort();
  return (
    leftKeys.length === rightKeys.length &&
    leftKeys.every((key, index) => key === rightKeys[index] && jsonEqual(left[key], right[key]))
  );
}

function emptyOrMissing(value: unknown): boolean {
  return value === undefined || (Array.isArray(value) && value.length === 0);
}

function hasExecutionModifier(node: Record<string, unknown>): boolean {
  const containers = [node, node.meta, node.ui].filter(isRecord);
  return containers.some((container) =>
    ['muted', 'bypassed', 'continueOnFail', 'continue_on_fail'].some(
      (key) => container[key] === true,
    ),
  );
}

/**
 * Recognize only the committed Samtools promotion canary graph.
 *
 * Template loading is allowed to replace node and edge instance IDs, but the
 * replacement must be internally consistent. Execution-significant content is
 * otherwise exact: node order/types/params, pinned input URL, edge ports and
 * topology, workflow outputs, and the absence of runtime modifiers.
 */
export function isSamtoolsFirstWaveCanaryWorkflow(workflow: unknown): workflow is Workflow {
  if (!isRecord(workflow)) return false;
  if (
    workflow.version !== '2.0' ||
    workflow.app !== 'bionodulo' ||
    workflow.name !== 'Samtools First-Wave Catalog Canary' ||
    workflow.description !==
      'Pinned HTTPS input followed by the seven Samtools promotion-candidate nodes' ||
    workflow.environment !== undefined ||
    workflow.dependencies !== undefined ||
    !emptyOrMissing(workflow.parameters) ||
    !emptyOrMissing(workflow.comments)
  ) {
    return false;
  }

  const groups = workflow.groups;
  const nodes = workflow.nodes;
  const edges = workflow.edges;
  const outputs = workflow.outputs;
  if (
    !Array.isArray(groups) ||
    groups.length !== 0 ||
    !Array.isArray(nodes) ||
    nodes.length !== EXPECTED_NODES.length ||
    !Array.isArray(edges) ||
    edges.length !== EXPECTED_EDGES.length ||
    !isRecord(outputs)
  ) {
    return false;
  }

  const nodeIndexes = new Map<string, number>();
  for (let index = 0; index < nodes.length; index += 1) {
    const node = nodes[index];
    const expected = EXPECTED_NODES[index];
    if (!isRecord(node) || typeof node.id !== 'string' || !node.id || nodeIndexes.has(node.id)) {
      return false;
    }
    if (
      node.type !== expected.type ||
      !jsonEqual(node.params, expected.params) ||
      hasExecutionModifier(node)
    ) {
      return false;
    }
    if (
      !Array.isArray(node.position) ||
      node.position.length !== 2 ||
      node.position.some((value) => typeof value !== 'number' || !Number.isFinite(value))
    ) {
      return false;
    }
    if (!isRecord(node.ui) || node.ui.title !== expected.title) return false;
    nodeIndexes.set(node.id, index);
  }

  for (let index = 0; index < edges.length; index += 1) {
    const edge = edges[index];
    const expected = EXPECTED_EDGES[index];
    if (!isRecord(edge) || !isRecord(edge.from) || !isRecord(edge.to)) return false;
    if (
      nodeIndexes.get(String(edge.from.node)) !== expected[0] ||
      edge.from.output !== expected[1] ||
      nodeIndexes.get(String(edge.to.node)) !== expected[2] ||
      edge.to.input !== expected[3]
    ) {
      return false;
    }
  }

  const outputKeys = Object.keys(outputs).sort();
  const expectedOutputKeys = Object.keys(EXPECTED_OUTPUTS).sort();
  if (!jsonEqual(outputKeys, expectedOutputKeys)) return false;
  return expectedOutputKeys.every((key) => {
    const nodeId = outputs[key];
    return (
      typeof nodeId === 'string' &&
      nodeIndexes.get(nodeId) === EXPECTED_OUTPUTS[key as keyof typeof EXPECTED_OUTPUTS]
    );
  });
}

export function catalogCanaryForWorkflow(workflow: unknown): CatalogCanarySelector | undefined {
  return isSamtoolsFirstWaveCanaryWorkflow(workflow)
    ? { ...SAMTOOLS_FIRST_WAVE_SELECTOR }
    : undefined;
}
