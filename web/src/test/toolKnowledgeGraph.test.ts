import { describe, expect, it } from 'vitest';
import rawMetadata from '../../../bionodulo/nodes/node_metadata.json';
import type { NodeMetadata, ObjectInfo } from '../types';
import { normalizeNodeKnowledge, safeKnowledgeUrl } from '../utils/nodeKnowledge';
import {
  buildToolGraphIndex, graphCoverage, graphPortType, graphPortTypes, neighborId, normalizeDoi, relatedTools,
} from '../utils/toolKnowledgeGraph';

function meta(id: string, overrides: Partial<NodeMetadata> = {}): NodeMetadata {
  return { id, display_name: id, category: 'Sequence', builtin: true, ...overrides };
}

function edge(source: string, target: string, kind: string, value?: string) {
  return expect.objectContaining({ source, target, kind, ...(value ? { value } : {}) });
}

const evidence = { url: 'https://example.org/manual', checked_at: '2026-09-25', note: 'Authors document this relationship.' };

describe('tool knowledge graph', () => {
  it('indexes the complete shipped builtin metadata by the registry key', () => {
    // Build from the actual raw object-info manifest, using the hook's input/output
    // normalization contract. This catches schema drift across the entire catalog.
    const converted = Object.fromEntries(Object.entries(rawMetadata).map(([key, raw]) => {
      const input = raw.input as Record<string, Record<string, [string, Record<string, unknown>]>>;
      const input_types = Object.fromEntries(['required', 'optional', 'hidden'].map(group => [
        group,
        Object.fromEntries(Object.entries(input[group] || {}).map(([port, [type]]) => [port, { type }])),
      ])) as NodeMetadata['input_types'];
      return [key, meta(raw.name, {
        display_name: raw.display_name, category: raw.category, builtin: raw.builtin,
        input_types, return_types: raw.output, return_names: raw.output_name,
        citation_dois: raw.citation_dois,
      })];
    })) as ObjectInfo;
    const index = buildToolGraphIndex(converted);
    expect(graphCoverage(index).nodes).toBe(Object.keys(rawMetadata).length);
    expect(new Set(Object.keys(index.nodes))).toEqual(new Set(Object.keys(rawMetadata)));
    expect(index.inputs.size).toBeGreaterThan(0);
    expect(index.outputs.size).toBeGreaterThan(0);
  });

  it('uses object-info keys as identities and excludes reference-only and custom nodes', () => {
    const index = buildToolGraphIndex({
      canonical_id: meta('wrong-alias', { display_name: 'Same name' }),
      second: meta('second', { display_name: 'Same name' }),
      reference: meta('reference', { registry_origin: { accession: 'example', execution_status: 'definition_only', blockers: [] } }),
      custom: meta('custom', { builtin: false }),
      declarative: meta('declarative', { declarative_runtime: { kind: 'biotools-reference' } }),
    });
    expect(Object.keys(index.nodes)).toEqual(['canonical_id', 'second']);
    expect(index.nodes.canonical_id.id).toBe('canonical_id');
    expect(relatedTools(index, 'canonical_id')).toContainEqual(edge('canonical_id', 'second', 'category'));
    expect(relatedTools(index, 'reference')).toEqual([]);
  });

  it('suppresses generic ports and links typed ports in their precise direction', () => {
    const index = buildToolGraphIndex({
      producer: meta('producer', { return_types: ['FASTQ', 'FILE', 'JSON'], return_names: ['reads', 'path', 'blob'] }),
      consumer: meta('consumer', { input_types: { required: { reads: { type: 'FASTQ' }, file: { type: 'FILE' } }, optional: { fastq_again: { type: 'FASTQ' } } } }),
      unrelated: meta('unrelated', { input_types: { required: { text: { type: 'STRING' } } }, return_types: ['ANY'] }),
    });
    expect(graphPortType('  fastq  ')).toBe('FASTQ');
    for (const generic of ['*', 'ANY', 'FILE', 'FILE_LIST', 'TXT', 'DIRECTORY', 'STRING', 'INT', 'JSON']) {
      expect(graphPortType(generic)).toBeUndefined();
    }
    const producerRelations = relatedTools(index, 'producer');
    expect(producerRelations).toContainEqual(expect.objectContaining({
      source: 'producer', target: 'consumer', kind: 'format', value: 'FASTQ',
      sourcePort: 'reads', targetPort: 'reads',
    }));
    expect(producerRelations).toContainEqual(expect.objectContaining({
      source: 'producer', target: 'consumer', kind: 'format', value: 'FASTQ',
      sourcePort: 'reads', targetPort: 'fastq_again',
    }));
    expect(producerRelations.filter(r => r.kind === 'format')).toHaveLength(2);
    expect(relatedTools(index, 'consumer').filter(r => r.kind === 'format')).toEqual(
      producerRelations.filter(r => r.kind === 'format'),
    );
    expect(neighborId(producerRelations[0], 'producer')).toBe('consumer');
    expect(neighborId(producerRelations[0], 'consumer')).toBe('producer');
    expect(producerRelations.filter(r => r.kind === 'format').every(r => !r.evidence)).toBe(true);
  });

  it('expands declared union ports while keeping list and compressed formats distinct', () => {
    expect(graphPortTypes('SAM|BAM')).toEqual(['SAM', 'BAM']);
    expect(graphPortTypes('FILE_LIST|BAM')).toEqual(['BAM']);
    const index = buildToolGraphIndex({
      union_source: meta('union_source', { return_types: ['SAM|BAM'], return_names: ['alignment'] }),
      bam_source: meta('bam_source', { return_types: ['BAM'], return_names: ['aligned'] }),
      bam_input: meta('bam_input', { input_types: { required: { alignment: { type: 'BAM' } } } }),
      union_input: meta('union_input', { input_types: { required: { alignment: { type: 'SAM|BAM' } } } }),
      list_source: meta('list_source', { return_types: ['BAM_LIST'], return_names: ['alignments'] }),
      list_input: meta('list_input', { input_types: { required: { alignments: { type: 'BAM_LIST' } } } }),
      compressed_source: meta('compressed_source', { return_types: ['BAM_GZ'], return_names: ['compressed'] }),
      file_source: meta('file_source', { return_types: ['FILE_LIST', 'TXT'], return_names: ['files', 'text'] }),
      file_input: meta('file_input', { input_types: { required: { files: { type: 'FILE_LIST' }, text: { type: 'TXT' } } } }),
    });
    expect(relatedTools(index, 'union_source')).toContainEqual(expect.objectContaining({
      source: 'union_source', target: 'bam_input', kind: 'format', value: 'BAM',
      sourcePort: 'alignment', targetPort: 'alignment',
    }));
    expect(relatedTools(index, 'bam_source')).toContainEqual(expect.objectContaining({
      source: 'bam_source', target: 'union_input', kind: 'format', value: 'BAM',
    }));
    expect(relatedTools(index, 'list_source').filter(r => r.kind === 'format')).toEqual([
      expect.objectContaining({ source: 'list_source', target: 'list_input', value: 'BAM_LIST' }),
    ]);
    expect(relatedTools(index, 'compressed_source').filter(r => r.kind === 'format')).toEqual([]);
    expect(relatedTools(index, 'file_source').filter(r => r.kind === 'format')).toEqual([]);
  });

  it('shows shared metadata symmetrically without upgrading it to a compatibility claim', () => {
    const knowledge = {
      schema_version: 1 as const,
      tool_id: 'https://bio.tools/seqtk',
      topics: [{ uri: 'http://edamontology.org/topic_0091', label: 'Bioinformatics' }],
      operations: [{ uri: 'http://edamontology.org/operation_2428', label: 'Validation' }],
    };
    const index = buildToolGraphIndex({
      a: meta('a', { citation_dois: ['https://doi.org/10.1234/EXAMPLE'], knowledge }),
      b: meta('b', { citation_dois: ['doi:10.1234/example'], knowledge }),
    });
    for (const [focus, other] of [['a', 'b'], ['b', 'a']]) {
      const found = relatedTools(index, focus);
      for (const kind of ['category', 'citation', 'tool', 'topic', 'operation']) {
        expect(found).toContainEqual(edge(focus, other, kind));
      }
      expect(found.every(r => r.kind !== 'format' && !r.evidence)).toBe(true);
    }
    expect(graphCoverage(index)).toEqual({ nodes: 2, categories: 1, withReferences: 2, withSourceChecks: 0, withKnowledge: 2 });
  });

  it('retains checked documented relations and ignores missing targets', () => {
    const index = buildToolGraphIndex({
      previous: meta('previous', { knowledge: {
        schema_version: 1, relations: [
          { target_node_id: 'next', kind: 'documented_successor', source_port: 'aligned', target_port: 'reads', evidence },
          { target_node_id: 'removed', kind: 'superseded_by', evidence },
        ],
      } }),
      next: meta('next'),
    });
    const found = relatedTools(index, 'previous').filter(r => r.kind === 'documented_successor');
    expect(found).toEqual([expect.objectContaining({
      source: 'previous', target: 'next', sourcePort: 'aligned', targetPort: 'reads', evidence,
    })]);
    expect(relatedTools(index, 'next')).toContainEqual(found[0]);
    expect(relatedTools(index, 'previous').some(r => r.target === 'removed')).toBe(false);
  });

  it('ignores malformed optional schema while preserving the builtin node', () => {
    const index = buildToolGraphIndex({
      good: meta('good', { knowledge: { schema_version: 1, tool_id: 'https://bio.tools/seqtk' } }),
      bad: meta('bad', { knowledge: { schema_version: 2, tool_id: 'javascript:alert(1)' } as never }),
    });
    expect(index.nodes.bad).toBeDefined();
    expect(index.nodes.bad.knowledge).toBeUndefined();
    expect(index.tools.get('https://bio.tools/seqtk')).toEqual(['good']);
    expect(index.tools.size).toBe(1);
  });

  it('canonicalizes DOI URL and prefix variants for stable shared-citation matching', () => {
    expect(normalizeDoi(' HTTPS://DX.DOI.ORG/10.1234/ABC ')).toBe('10.1234/abc');
    expect(normalizeDoi('doi: 10.1234/ABC')).toBe('10.1234/abc');
    const index = buildToolGraphIndex({
      a: meta('a', { citation_dois: ['https://doi.org/10.1234/ABC', 'doi:10.1234/abc'] }),
      b: meta('b', { citation_dois: ['10.1234/abc'] }),
    });
    expect(index.citations.get('10.1234/abc')).toEqual(['a', 'b']);
    expect(relatedTools(index, 'a').filter(r => r.kind === 'citation')).toHaveLength(1);
  });

  it('rejects malformed knowledge evidence on the client rather than rendering it', () => {
    expect(normalizeNodeKnowledge({ schema_version: 1, relations: [{
      target_node_id: 'next', kind: 'complements', evidence: { ...evidence, checked_at: '2026-02-30' },
    }] })).toBeUndefined();
    expect(safeKnowledgeUrl('https://bio.tools/seqtk')).toBe('https://bio.tools/seqtk');
    expect(safeKnowledgeUrl('https://8.8.8.8/tool')).toBeUndefined();
    expect(safeKnowledgeUrl('http://127.0.0.1/tool')).toBeUndefined();
  });
});
