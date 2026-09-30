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
  notices: { kind: string; title: string; message?: string }[];
  uploadReq: DoiUploadRequest | null;
  setUpload: (r: DoiUploadRequest | null) => void;
  guestBanner: ReturnType<typeof vi.fn>;
  progress: string[];
  metrics: Array<{ model?: string; inputTokens?: number; outputTokens?: number }>;
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
  const notices: Harness['notices'] = [];
  let uploadReq: DoiUploadRequest | null = null;
  const guestBanner = vi.fn();
  const progress: string[] = [];
  const metrics: Harness['metrics'] = [];

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
    onProgress: (line) => progress.push(line),
    onAnalysisMetrics: (value) => metrics.push(value),
    notify: {
      loading: (title) => notices.push({ kind: 'loading', title }),
      success: (title) => notices.push({ kind: 'success', title }),
      info: (title) => notices.push({ kind: 'info', title }),
      error: (title, _id, message) => notices.push({ kind: 'error', title, message }),
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
    progress,
    metrics,
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

  it('handles a closed-access final SSE event and requests the PDF', async () => {
    const encoder = new TextEncoder();
    let calls = 0;
    const h = makeHarness(async () => {
      calls++;
      if (calls === 1) return new Response(new ReadableStream({
        start(controller) {
          controller.enqueue(encoder.encode('data: {"type":"final","status":409,"payload":{"needsUpload":true,"paper":{"title":"Closed Paper"}}}\n\n'));
          controller.close();
        },
      }), { headers: { 'content-type': 'text/event-stream' } });
      return jsonResponse(200, ANALYSIS_OK);
    });
    const flow = runDoiFlow('10.1/closed', h.deps);
    await vi.waitFor(() => {
      if (!h.uploadReq) throw new Error('overlay not requested yet');
    });
    expect(h.uploadReq?.paperTitle).toBe('Closed Paper');
    h.uploadReq!.onFile(new File(['pdf'], 'paper.pdf', { type: 'application/pdf' }));
    await flow;
    expect(h.getWf().nodes.map(node => node.type)).toContain('trim_galore');
  });

  it('surfaces a readable PDF extraction error without showing control characters', async () => {
    const h = makeHarness(async url => String(url).includes('/ai/analyze')
      ? jsonResponse(409, { needsUpload: true, paper: { title: 'Closed Paper' } })
      : jsonResponse(422, { error: 'Could not extract enough text\nfrom the PDF (it may be a scan).' }));
    const flow = runDoiFlow('10.1/closed', h.deps);
    await vi.waitFor(() => expect(h.uploadReq).not.toBeNull());
    h.uploadReq!.onFile(new File(['pdf'], 'paper.pdf', { type: 'application/pdf' }));
    await flow;
    expect(h.notices.at(-1)?.message).toContain('Could not extract enough text from the PDF');
    expect(h.notices.at(-1)?.message).not.toContain('\n');
  });

  it('bounds a stalled PDF upload request', async () => {
    const h = makeHarness((async (url: RequestInfo | URL, init?: RequestInit) => {
      if (String(url).includes('/ai/analyze')) return jsonResponse(409, { needsUpload: true, paper: { title: 'Closed Paper' } });
      return new Promise<Response>((_resolve, reject) => {
        init?.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')), { once: true });
      });
    }) as typeof fetch);
    const flow = runDoiFlow('10.1/closed', h.deps);
    await vi.waitFor(() => expect(h.uploadReq).not.toBeNull());
    vi.useFakeTimers();
    try {
      h.uploadReq!.onFile(new File(['pdf'], 'paper.pdf', { type: 'application/pdf' }));
      await vi.advanceTimersByTimeAsync(270_001);
      await flow;
      expect(h.notices.at(-1)?.message).toContain('timed out');
    } finally {
      vi.useRealTimers();
    }
  });

  it('does not infer connections from matching port types alone', async () => {
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
    expect(wf.edges).toEqual([]);
    expect(String(wf.nodes[0].params.text)).toContain('Unconnected steps');
    expect(String(wf.nodes[0].params.text)).toContain('no valid suggested connection');
  });

  it('leaves incompatible steps unconnected and explains the gap', async () => {
    const h = makeHarness(async () => jsonResponse(200, {
      result: {
        summary: 'A paper.', bioinformaticsRelevant: true,
        workflowSuggestion: {
          recommendedNodes: [
            { name: 'FastQC', category: 'qc', reason: 'inspect quality' },
            { name: 'STAR Aligner', category: 'alignment', reason: 'align reads' },
          ],
          suggestedConnections: ['FastQC -> STAR Aligner'],
        },
        paper: { title: 'QC paper', doi: '10.1/qc' },
      },
    }));
    await runDoiFlow('10.1/qc', h.deps);
    expect(h.getWf().edges).toEqual([]);
    expect(String(h.getWf().nodes[0].params.text)).toContain('Unconnected steps');
  });

  it('builds catalog-validated DESeq2 steps with two explicit file inputs', async () => {
    const h = makeHarness(async () => jsonResponse(200, { result: {
      bioinformaticsRelevant: true,
      workflowSuggestion: {
        recommendedNodes: [
          { name: 'Counts', category: 'input', reason: 'raw counts', nodeType: 'input_file' },
          { name: 'Samples', category: 'input', reason: 'sample metadata', nodeType: 'input_file' },
          { name: 'DESeq2 analysis', category: 'differential_expression', reason: 'test expression', nodeType: 'deseq2' },
        ],
        suggestedConnections: [
          { from: 'Counts', to: 'DESeq2 analysis', output: 'file', input: 'count_matrix' },
          { from: 'Samples', to: 'DESeq2 analysis', output: 'file', input: 'sample_info' },
        ],
      },
      paper: { title: 'DESeq2 paper' },
    } }));
    h.deps.objectInfo = {
      ...objectInfo,
      input_file: { id: 'input_file', display_name: 'Input File', category: 'input', return_types: ['FILE'], return_names: ['file'] },
      deseq2: { id: 'deseq2', display_name: 'DESeq2', category: 'differential_expression', input_types: { required: {
        count_matrix: { type: 'FILE' }, sample_info: { type: 'FILE' },
      } } },
    } as ObjectInfo;
    await runDoiFlow('10.1/deseq2', h.deps);
    expect(h.getWf().nodes.map(node => node.type)).toEqual(['note', 'input_file', 'input_file', 'deseq2']);
    expect(h.getWf().edges.map(edge => edge.to.input)).toEqual(['count_matrix', 'sample_info']);
  });

  it('does not replace an unknown explicit nodeType with a name match', async () => {
    const h = makeHarness(async () => jsonResponse(200, { result: {
      bioinformaticsRelevant: true,
      workflowSuggestion: { recommendedNodes: [
        { name: 'FastQC', category: 'qc', reason: 'suggested by model', nodeType: 'not_registered' },
      ] },
      paper: { title: 'Paper' },
    } }));
    await runDoiFlow('10.1/unknown', h.deps);
    expect(h.getWf().nodes.map(node => node.type)).toEqual(['note', 'note']);
  });

  it('preserves evidence limits and suggested reasons without guessing parameters', async () => {
    const h = makeHarness(async () => jsonResponse(200, {
      result: {
        ...ANALYSIS_OK.result,
        paper: {
          ...ANALYSIS_OK.result.paper,
          textSource: 'abstract',
          limitations: ['Parameters not reported'],
          evidenceVersion: 'paper-evidence-v1',
        },
        methodology: { pipeline: ['Trim reads', 'Align to reference'] },
      },
    }));
    await runDoiFlow('10.1/x', h.deps);
    const wf = h.getWf();
    const note = String(wf.nodes[0].params.text);
    expect(note).toContain('abstract only');
    expect(note).toContain('Parameters not reported');
    expect(note).toContain('Trim reads');
    expect(note).toContain('Trim Galore: trim reads');
    expect(wf.nodes[1].params).toEqual({});
  });

  it('consumes live website events and ignores raw reasoning deltas', async () => {
    const encoder = new TextEncoder();
    const events = [
      { type: 'stage', stage: 'resolve' },
      { type: 'model', model: 'test-model' },
      { type: 'thinking', delta: 'private reasoning' },
      { type: 'tokens', inputTokens: 10, outputTokens: 5 },
      { type: 'final', status: 200, payload: ANALYSIS_OK },
    ];
    const fetchImpl = vi.fn(async (_url: RequestInfo | URL, init?: RequestInit) => {
      expect((init?.headers as Record<string, string>).accept).toBe('text/event-stream');
      return new Response(new ReadableStream({
        start(controller) {
          for (const event of events) controller.enqueue(encoder.encode(`data: ${JSON.stringify(event)}\n\n`));
          controller.close();
        },
      }), { headers: { 'content-type': 'text/event-stream' } });
    }) as typeof fetch;
    const h = makeHarness(fetchImpl);
    await runDoiFlow('10.1/x', h.deps);
    expect(h.getWf().nodes.map(node => node.type)).toContain('star_aligner');
    expect(h.progress.join(' ')).toContain('Resolving the DOI');
    expect(h.progress.join(' ')).not.toContain('private reasoning');
    expect(h.metrics).toContainEqual({ model: 'test-model' });
    expect(h.metrics).toContainEqual({ inputTokens: 10, outputTokens: 5 });
  });

  it('assembles fragmented CRLF events and rejects a stream without a final result', async () => {
    const final = `data: ${JSON.stringify({ type: 'final', status: 200, payload: ANALYSIS_OK })}\r\n\r\n`;
    const chunks = ['\r', '\n', 'data: {"type":"stage","stage":"resolve"}\r', '\n\r', '\n', ...final.split('')];
    const response = (parts: string[]) => new Response(new ReadableStream({
      start(controller) {
        for (const part of parts) controller.enqueue(new TextEncoder().encode(part));
        controller.close();
      },
    }), { headers: { 'content-type': 'text/event-stream' } });
    const ok = makeHarness((async () => response(chunks)) as typeof fetch);
    await runDoiFlow('10.1/x', ok.deps);
    expect(ok.progress.join(' ')).toContain('Resolving the DOI');
    expect(ok.notices.at(-1)?.kind).toBe('success');

    const unfinished = makeHarness((async () => response(['data: {"type":"stage","stage":"resolve"}\n\n'])) as typeof fetch);
    await runDoiFlow('10.1/x', unfinished.deps);
    expect(unfinished.notices.at(-1)?.kind).toBe('error');
    expect(unfinished.getWf().nodes.some(node => node.type !== 'note')).toBe(false);
  });

  it('finishes on the final SSE event without waiting for the socket to close', async () => {
    let cancelled = false;
    const response = new Response(new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(`data: ${JSON.stringify({ type: 'final', status: 200, payload: ANALYSIS_OK })}\n\n`));
        // Keep the stream open to simulate a server/socket that has not closed yet.
      },
      cancel() { cancelled = true; },
    }), { headers: { 'content-type': 'text/event-stream' } });
    const h = makeHarness((async () => response) as typeof fetch);
    await runDoiFlow('10.1/x', h.deps);
    expect(h.notices.at(-1)?.kind).toBe('success');
    expect(cancelled).toBe(true);
  });

  it('reports a failed explicit save instead of claiming the workflow persisted', async () => {
    const h = makeHarness(async () => jsonResponse(200, ANALYSIS_OK), true);
    h.deps.createCloudTab = async () => {};
    h.deps.persistWorkflow = async () => { throw new Error('save failed'); };
    await runDoiFlow('10.1/x', h.deps);
    expect(h.getWf().nodes.length).toBeGreaterThan(0);
    expect(h.notices.at(-1)?.kind).toBe('error');
  });

  it('does not report success if its target tab disappears before completion', async () => {
    const h = makeHarness(async () => jsonResponse(200, ANALYSIS_OK));
    h.deps.getWorkflow = () => { throw new Error('DOI workflow tab was closed'); };
    await expect(runDoiFlow('10.1/x', h.deps)).rejects.toThrow('DOI workflow tab was closed');
    expect(h.notices.some(notice => notice.kind === 'success')).toBe(false);
  });

  it('reports a stalled initial analysis instead of waiting forever', async () => {
    vi.useFakeTimers();
    try {
      const fetchImpl = vi.fn((_url: RequestInfo | URL, init?: RequestInit) => new Promise<Response>((_resolve, reject) => {
        init?.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')), { once: true });
      })) as typeof fetch;
      const h = makeHarness(fetchImpl);
      const flow = runDoiFlow('10.1/stalled', h.deps);
      await vi.advanceTimersByTimeAsync(90_001);
      await flow;
      expect(h.notices.at(-1)?.kind).toBe('error');
      expect(h.getWf().nodes.at(-1)?.type).toBe('note');
    } finally {
      vi.useRealTimers();
    }
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
