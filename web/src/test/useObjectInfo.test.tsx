import { renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { apiGet } from '../api/client';
import { useObjectInfo } from '../hooks/data/useObjectInfo';

const apiMocks = vi.hoisted(() => ({
  apiGet: vi.fn(),
}));

vi.mock('../api/client', () => apiMocks);

describe('useObjectInfo', () => {
  beforeEach(() => {
    vi.mocked(apiGet).mockReset();
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
