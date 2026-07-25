import { beforeEach, describe, expect, it, vi } from 'vitest';

const websiteMocks = vi.hoisted(() => ({ presignCloudUpload: vi.fn() }));
const clientMocks = vi.hoisted(() => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  apiRequest: vi.fn(),
}));
const transferMocks = vi.hoisted(() => ({
  addTransfer: vi.fn(),
  updateTransfer: vi.fn(),
  newTransferId: vi.fn(() => 'transfer-1'),
}));

vi.mock('../api/website', () => websiteMocks);
vi.mock('../api/client', () => clientMocks);
vi.mock('../state/transfers', () => transferMocks);

import { uploadWorkspaceFileToCloud } from '../api/cloudFiles';

describe('serverless cloud file relay', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    clientMocks.apiRequest.mockResolvedValue(new Response(null, {
      headers: { 'content-length': '944' },
    }));
    websiteMocks.presignCloudUpload.mockResolvedValue({
      url: 'https://example.r2.cloudflarestorage.com/upload',
      key: 'uploads/team/fixture__paired_R1.fastq',
    });
  });

  it('accepts an upload completed inside the Lambda response without polling memory', async () => {
    clientMocks.apiPost.mockResolvedValue({
      transfer_id: 'backend-transfer',
      total: 944,
      status: 'done',
      error: null,
    });

    const key = await uploadWorkspaceFileToCloud(
      'templates/data/smoke/paired_R1.fastq',
      'paired_R1.fastq',
    );

    expect(key).toBe('uploads/team/fixture__paired_R1.fastq');
    expect(clientMocks.apiGet).not.toHaveBeenCalled();
    expect(transferMocks.updateTransfer).toHaveBeenCalledWith(
      'transfer-1',
      expect.objectContaining({ status: 'done', loaded: 944, total: 944 }),
    );
  });

  it('uses the trusted file-size header supplied by the shared editor proxy', async () => {
    clientMocks.apiRequest.mockResolvedValue(new Response(null, {
      headers: { 'x-bionodulo-file-size': '944' },
    }));
    clientMocks.apiPost.mockResolvedValue({
      transfer_id: 'backend-transfer',
      total: 944,
      status: 'done',
      error: null,
    });

    const key = await uploadWorkspaceFileToCloud(
      'templates/data/smoke/paired_R2.fastq',
      'paired_R2.fastq',
    );

    expect(key).toBe('uploads/team/fixture__paired_R1.fastq');
    expect(websiteMocks.presignCloudUpload).toHaveBeenCalledWith(
      'paired_R2.fastq',
      'application/octet-stream',
      944,
    );
  });
});
