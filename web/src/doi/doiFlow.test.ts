import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { Workflow } from '../types';
import { runDoiFlow, type DoiFlowDeps, type DoiUploadRequest } from './doiFlow';
import type { ObjectInfo } from '../types';

const objectInfo = {
  fastqc: {
    id: 'fastqc',
    display_name: 'FastQC',
    category: 'qc',
    search_aliases: ['fastqc'],
    input_types: { required: { reads: { type: 'FASTQ' } } },
    return_types: ['HTML'],
    return_names: ['report'],
  },
  trim_galore: {
    id: 'trim_galore',
    display_name: 'Trim Galore',
    category: 'qc',
    search_aliases: ['trimgalore'],
    input_types: { required: { reads: { type: 'FASTQ' } } },
    return_types: ['FASTQ'],
    return_names: ['trimmed'],
  },
  star_aligner: {
    id: 'star_aligner',
    display_name: 'STAR Aligner',
    category: 'alignment',
    search_aliases: ['star'],
    input_types: { required: { reads: { type: 'FASTQ' } } },
    return_types: ['BAM'],
    return_names: ['bam'],
  },
  note: {
    id: 'note',
    display_name: 'Notes',
    category: 'utility',
    search_aliases: ['note'],
    input_types: { required: { text: { type: 'STRING' } } },
    return_types: [],
    return_names: [],
  },
} as unknown as ObjectInfo;

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

const ANALYSIS_OK = {
  result: {
    summary: 'A paper about RNA-seq.',
    bioinformaticsRelevant: true,
    workflowSuggestion: {
      description: 'Build it',
      recommendedNodes: [
        { name: 'Trim Galore', category: 'qc', reason: 'trim reads' },
        { name: 'STAR Aligner', category: 'alignment', reason: 'align reads' },
      ],
      suggestedConnections: ['Trim Galore -> STAR Aligner'],
    },
    paper: { title: 'The Paper Title', doi: '10.1/x' },
  },
};

interface Harness {
  deps: DoiFlowDeps;
  getWf: () => Workflow;
  notices: { kind: string; title: string }[];
  uploadReq: DoiUploadRequest | null;
  setUpload: (r: DoiUploadRequest | null) => void;
  guestBanner: ReturnType<typeof vi.fn>;
}

function makeHarness(fetchImpl: typeof fetch, signedIn = false): Harness {
  let wf: Workflow = {
    id: '',
    version: '2.0',
    app: 'bionodulo',
    name: '',
    description: '',
    nodes: [],
    edges: [],
    groups: [],
    outputs: {},
    parameters: [],
  };
  const notices: { kind: string; title: string }[] = [];
  let uploadReq: DoiUploadRequest | null = null;
  const guestBanner = vi.fn();

  const deps: DoiFlowDeps = {
    objectInfo,
    signedIn,
    createCloudTab: async () => {
      throw new Error('not signed in');
    },
    addLocalTab: (name) => {
      wf = { ...wf, name };
    },
    renameActive: (name) => {
      wf = { ...wf, name };
    },
    getWorkflow: () => wf,
    setWorkflow: (updater) => {
      wf = updater(wf);
    },
    fitView: () => {},
    setUploadRequest: (r) => {
      uploadReq = r;
    },
    onProgress: () => {},
    notify: {
      loading: (title) => notices.push({ kind: 'loading', title }),
      success: (title) => notices.push({ kind: 'success', title }),
      info: (title) => notices.push({ kind: 'info', title }),
      error: (title) => notices.push({ kind: 'error', title }),
      dismiss: () => {},
      guestBanner,
    },
    t: ((key: string, opts?: Record<string, unknown>) => (opts?.defaultValue as string) || key) as DoiFlowDeps['t'],
    fetchImpl,
    stageDelayMs: 0,
  };

  return {
    deps,
    getWf: () => wf,
    notices,
    get uploadReq() {
      return uploadReq;
    },
    setUpload: (r) => {
      uploadReq = r;
    },
    guestBanner,
  };
}

describe('runDoiFlow', () => {
  beforeEach(() => vi.restoreAllMocks());

  it('builds title, summary note, staged nodes and edges from an analysis', async () => {
    const h = makeHarness(async () => jsonResponse(200, ANALYSIS_OK));

    await runDoiFlow('10.1/x', h.deps);

    const wf = h.getWf();
    expect(wf.name).toBe('The Paper Title');
    expect(wf.nodes[0].type).toBe('note'); // summary note first
    expect(String(wf.nodes[0].params.text)).toContain('A paper about RNA-seq.');
    expect(wf.nodes.map((n) => n.type)).toEqual(['note', 'trim_galore', 'star_aligner']);
    expect(wf.edges).toEqual([
      { id: 'doi-e0', from: { node: 'trim-galore-0', output: 'trimmed' }, to: { node: 'star-aligner-1', input: 'reads' } },
    ]);
    expect(h.guestBanner).toHaveBeenCalledOnce();
    expect(h.notices.at(-1)?.kind).toBe('success');
  });

  it('asks for a PDF on closed access, then builds from the upload', async () => {
    let calls = 0;
    const h = makeHarness(async (url) => {
      calls += 1;
      if (String(url).includes('/ai/analyze')) {
        return jsonResponse(409, { error: 'closed', reason: 'closed_access', needsUpload: true, paper: { title: 'Closed Paper' } });
      }
      return jsonResponse(200, ANALYSIS_OK);
    });

    const flow = runDoiFlow('10.1/closed', h.deps);
    await vi.waitFor(() => {
      if (!h.uploadReq) throw new Error('overlay not requested yet');
    });
    expect(h.uploadReq?.paperTitle).toBe('Closed Paper');

    h.uploadReq!.onFile(new File(['pdf'], 'paper.pdf', { type: 'application/pdf' }));
    await flow;

    expect(calls).toBe(2);
    expect(h.getWf().nodes.map((n) => n.type)).toContain('trim_galore');
  });

  it('connects every pipeline node even when suggestions omit links', async () => {
    const h = makeHarness(async () =>
      jsonResponse(200, {
        result: {
          summary: 'A paper.',
          bioinformaticsRelevant: true,
          workflowSuggestion: {
            description: 'x',
            recommendedNodes: [
              { name: 'Trim Galore', category: 'qc', reason: 'trim' },
              { name: 'STAR Aligner', category: 'alignment', reason: 'align' },
              { name: 'FastQC', category: 'qc', reason: 'qc report' },
            ],
            suggestedConnections: [], // nothing suggested at all
          },
          paper: { title: 'T', doi: '10.1/y' },
        },
      }),
    );

    await runDoiFlow('10.1/y', h.deps);

    const wf = h.getWf();
    const pipeline = wf.nodes.filter((n) => n.type !== 'note');
    expect(pipeline).toHaveLength(3);
    // Every pipeline node is touched by at least one edge.
    for (const n of pipeline) {
      expect(
        wf.edges.some((e) => e.from.node === n.id || e.to.node === n.id),
      ).toBe(true);
    }
    expect(wf.edges.length).toBeGreaterThanOrEqual(2);
  });

  it('informs instead of building when the paper is not bioinformatics', async () => {
    const h = makeHarness(async () =>
      jsonResponse(200, {
        result: {
          summary: 'A clinical trial.',
          bioinformaticsRelevant: false,
          workflowSuggestion: { recommendedNodes: [], suggestedConnections: [] },
          paper: { title: 'Clinical Paper' },
        },
      }),
    );

    await runDoiFlow('10.1/clinical', h.deps);

    const wf = h.getWf();
    expect(wf.name).toBe('Clinical Paper');
    expect(wf.nodes).toHaveLength(1);
    expect(wf.nodes[0].type).toBe('note');
    expect(String(wf.nodes[0].params.text)).toContain('not about computational biology');
    expect(h.notices.some((n) => n.kind === 'info')).toBe(true);
  });

  it('informs on analysis failure and places an explanatory note', async () => {
    const h = makeHarness(async () => jsonResponse(404, { error: 'No Crossref record' }));

    await runDoiFlow('10.1/missing', h.deps);

    const wf = h.getWf();
    expect(wf.nodes).toHaveLength(1);
    expect(wf.nodes[0].type).toBe('note');
    expect(h.notices.at(-1)?.kind).toBe('error');
  });
});
