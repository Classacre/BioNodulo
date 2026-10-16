import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { apiGet } from '../api/client';
import { OBJECT_INFO_TIMEOUT_MS, useObjectInfo } from '../hooks/data/useObjectInfo';

const apiMocks = vi.hoisted(() => ({
  apiGet: vi.fn(),
}));

vi.mock('../api/client', () => apiMocks);

describe('useObjectInfo', () => {
  beforeEach(() => {
    vi.mocked(apiGet).mockReset();
  });
  afterEach(() => { vi.useRealTimers(); });

  it('bounds a stalled registry, aborts it, and restores native port metadata on explicit retry', async () => {
    vi.useFakeTimers();
    let finishOld!: (value: unknown) => void;
    vi.mocked(apiGet).mockImplementationOnce(() => new Promise(resolve => { finishOld = resolve; }));
    const { result } = renderHook(() => useObjectInfo());
    const signal = vi.mocked(apiGet).mock.calls[0][1]?.signal;
    await act(async () => { await vi.advanceTimersByTimeAsync(OBJECT_INFO_TIMEOUT_MS); });
    expect(signal?.aborted).toBe(true);
    expect(result.current.loading).toBe(false);
    expect(result.current.error?.message).toContain('timed out');
    vi.mocked(apiGet).mockResolvedValueOnce({ input_fastq: {
      name: 'input_fastq', display_name: 'Input FASTQ', category: 'Input',
      input: { required: { file_path: ['STRING', {}] } }, output: ['FASTQ_LIST'], output_name: ['reads'],
    } });
    await act(async () => { await result.current.refresh(); });
    expect(result.current.error).toBeNull();
    expect(result.current.objectInfo.input_fastq.return_names).toEqual(['reads']);
    expect(result.current.objectInfo.input_fastq.input_types?.required?.file_path.type).toBe('STRING');
    // A transport which ignored AbortSignal must not replace the retried map.
    await act(async () => { finishOld({ stale: { name: 'stale', output: [], output_name: [] } }); });
    expect(Object.keys(result.current.objectInfo)).toEqual(['input_fastq']);
  });

  it('retains good ports on refresh failure and ignores superseded A/B/A completion', async () => {
    vi.mocked(apiGet).mockResolvedValueOnce({ first: { name: 'first', output: ['FILE'], output_name: ['file'] } });
    const { result } = renderHook(() => useObjectInfo());
    await waitFor(() => expect(result.current.loading).toBe(false));
    vi.mocked(apiGet).mockRejectedValueOnce(new Error('offline'));
    await act(async () => { await result.current.refresh(); });
    expect(result.current.objectInfo.first.return_names).toEqual(['file']);
    vi.mocked(apiGet).mockResolvedValueOnce(null);
    await act(async () => { await result.current.refresh(); });
    expect(result.current.error).not.toBeNull();
    expect(result.current.objectInfo.first.return_names).toEqual(['file']);
    let finishOld!: (value: unknown) => void;
    vi.mocked(apiGet).mockImplementationOnce(() => new Promise(resolve => { finishOld = resolve; }));
    let oldRequest!: Promise<void>;
    act(() => { oldRequest = result.current.refresh(); });
    const oldSignal = vi.mocked(apiGet).mock.calls[3][1]?.signal;
    vi.mocked(apiGet).mockResolvedValueOnce({ first: { name: 'first', output: ['FILE'], output_name: ['new_file'] } });
    await act(async () => { await result.current.refresh(); await oldRequest; });
    expect(oldSignal?.aborted).toBe(true);
    await act(async () => { finishOld({ first: { name: 'first', output: [], output_name: [] } }); });
    expect(result.current.objectInfo.first.return_names).toEqual(['new_file']);
    expect(result.current.error).toBeNull();
  });

  it('aborts on unmount and rejects retained refresh callbacks without another request', async () => {
    let finish!: (value: unknown) => void;
    vi.mocked(apiGet).mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }));
    const { result, unmount } = renderHook(() => useObjectInfo());
    const retry = result.current.refresh;
    const signal = vi.mocked(apiGet).mock.calls[0][1]?.signal;
    unmount();
    expect(signal?.aborted).toBe(true);
    await act(async () => { finish({ ignored: {} }); await retry(); });
    expect(apiGet).toHaveBeenCalledTimes(1);
  });

  it.each(['raw', 'normalized'] as const)('preserves validated knowledge from %s object info', async shape => {
    const knowledge = {
      schema_version: 1,
      tool_id: 'https://bio.tools/seqtk',
      operations: [{ uri: 'http://edamontology.org/operation_2428', label: 'Validation' }],
      citation_evidence: [{
        identifier: '10.1234/example', source_url: 'https://doi.org/10.1234/example',
        checked_at: '2026-09-25', note: 'Publisher page lists this paper.',
      }],
    };
    const raw = {
      name: 'knowledge_node', display_name: 'Knowledge Node', category: 'tests', builtin: true,
      input: { required: {} }, output: ['BAM'], output_name: ['bam'], knowledge,
    };
    const normalized = {
      id: 'knowledge_node', display_name: 'Knowledge Node', category: 'tests', builtin: true,
      input_types: { required: {} }, return_types: ['BAM'], return_names: ['bam'], knowledge,
    };
    vi.mocked(apiGet).mockResolvedValueOnce({ knowledge_node: shape === 'raw' ? raw : normalized });
    const { result } = renderHook(() => useObjectInfo());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.objectInfo.knowledge_node.knowledge).toEqual(knowledge);
    expect(result.current.objectInfo.knowledge_node.return_types).toEqual(['BAM']);
  });

  it('preserves node lifecycle and versioning metadata from object_info', async () => {
    vi.mocked(apiGet).mockResolvedValueOnce({
      versioned_legacy: {
        name: 'versioned_legacy',
        display_name: 'Versioned Legacy',
        category: 'tests',
        version: '2.1.0',
        citation_dois: ['10.1093/bioinformatics/btx000'],
        citation_urls: ['https://doi.org/10.1093/bioinformatics/btx000'],
        citation_text: 'Example Bioinformatics methods paper.',
        deprecated: true,
        deprecation_message: 'Use versioned_modern for new workflows.',
        replaced_by: 'versioned_modern',
        lifecycle: {
          status: 'deprecated',
          deprecated: true,
          deprecation_message: 'Use versioned_modern for new workflows.',
          replaced_by: 'versioned_modern',
        },
        versioning: {
          current: '2.1.0',
          previous: ['1.0.0', '2.0.0'],
          migrations: [
            {
              from_version: '1.x',
              to_version: '2.0.0',
              description: 'Rename old_value to value.',
            },
          ],
        },
        input: { required: {} },
        output: ['STRING'],
        output_name: ['value'],
      },
    });

    const { result } = renderHook(() => useObjectInfo());

    await waitFor(() => expect(result.current.loading).toBe(false));

    const meta = result.current.objectInfo.versioned_legacy;
    expect(meta.deprecated).toBe(true);
    expect(meta.deprecation_message).toBe('Use versioned_modern for new workflows.');
    expect(meta.replaced_by).toBe('versioned_modern');
    expect(meta.lifecycle?.status).toBe('deprecated');
    expect(meta.lifecycle?.replaced_by).toBe('versioned_modern');
    expect(meta.versioning?.current).toBe('2.1.0');
    expect(meta.versioning?.previous).toEqual(['1.0.0', '2.0.0']);
    expect(meta.versioning?.migrations[0]).toMatchObject({
      from_version: '1.x',
      to_version: '2.0.0',
    });
    expect(meta.citation_dois).toEqual(['10.1093/bioinformatics/btx000']);
    expect(meta.citation_urls).toEqual(['https://doi.org/10.1093/bioinformatics/btx000']);
    expect(meta.citation_text).toBe('Example Bioinformatics methods paper.');
  });

  it('preserves custom node source and dependency metadata from object_info', async () => {
    vi.mocked(apiGet).mockResolvedValueOnce({
      custom_qc: {
        name: 'custom_qc',
        display_name: 'Custom QC',
        category: 'custom',
        builtin: false,
        git_url: 'https://github.com/example/custom-qc.git',
        git_commit: 'abc123',
        custom_node_package: {
          name: 'manifest-pkg',
          version: '0.1.0',
          repository: 'https://github.com/example/custom-qc.git',
          directory: 'manifest_pkg',
          entrypoint: 'nodes',
          manifest_present: true,
        },
        required_executables: ['custom-qc'],
        required_conda_packages: ['custom-qc=1.0'],
        required_r_packages: ['BiocManager'],
        input: { required: {} },
        output: ['STRING'],
        output_name: ['report'],
      },
    });

    const { result } = renderHook(() => useObjectInfo());

    await waitFor(() => expect(result.current.loading).toBe(false));

    const meta = result.current.objectInfo.custom_qc;
    expect(meta.builtin).toBe(false);
    expect(meta.git_url).toBe('https://github.com/example/custom-qc.git');
    expect(meta.git_commit).toBe('abc123');
    expect(meta.custom_node_package).toEqual({
      name: 'manifest-pkg',
      version: '0.1.0',
      repository: 'https://github.com/example/custom-qc.git',
      directory: 'manifest_pkg',
      entrypoint: 'nodes',
      manifest_present: true,
    });
    expect(meta.requires_external_tools).toEqual(['custom-qc']);
    expect(meta.required_conda_packages).toEqual(['custom-qc=1.0']);
    expect(meta.required_r_packages).toEqual(['BiocManager']);
  });
});
