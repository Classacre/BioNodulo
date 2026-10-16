import { act, fireEvent, render, screen, waitFor, cleanup } from '@testing-library/react';
import { Provider, createStore } from 'jotai';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import CloudOutputPreviewModal from '../components/modals/CloudOutputPreviewModal';
import { cloudConfigAtom, type CloudConfig } from '../state/appAtoms';
import { cloudPreviewSelectionAtom } from '../state/cloudPreview';
import { cloudLogStorageKey } from '../hooks/cloud/useCloudLogStorage';
import { getCloudOutputPreview } from '../api/website';
import { cloudInviteSessionAtom, type CloudInviteSession } from '../collab/cloudInvite';

vi.mock('../api/website', () => ({ getCloudOutputPreview: vi.fn(), call: vi.fn() }));
const config = (team: string) => ({ editorMode: true, user: { id: 'user' }, team: { id: team } }) as CloudConfig;
const selection = (name = 'plot.png', size = 4) => ({ runId: 'run', scope: cloudLogStorageKey('user', 'a')!, output: { key: `a/run/node/${name}`, name, size, sha256: 'a'.repeat(64) } });
function mount(name?: string, size?: number) {
  const store = createStore(); store.set(cloudConfigAtom, config('a')); store.set(cloudPreviewSelectionAtom, selection(name, size));
  render(<Provider store={store}><CloudOutputPreviewModal /></Provider>);
  return store;
}

describe('verified cloud output modal', () => {
  beforeEach(() => {
    vi.mocked(getCloudOutputPreview).mockReset();
    vi.stubGlobal('URL', class extends URL { static createObjectURL = vi.fn(() => 'blob:verified'); static revokeObjectURL = vi.fn(); });
  });
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
  it('uses verified transient bytes and revokes the object URL on close', async () => {
    vi.mocked(getCloudOutputPreview).mockResolvedValue(new Blob(['data'], { type: 'image/png' }));
    mount();
    expect(await screen.findByAltText('plot.png')).toHaveAttribute('src', 'blob:verified');
    expect(getCloudOutputPreview).toHaveBeenCalledWith('run', 'a/run/node/plot.png', expect.any(AbortSignal), 'a');
    fireEvent.click(screen.getByRole('button', { name: 'Close cloud preview' }));
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:verified');
  });
  it('removes content immediately on an in-page team switch and aborts pending bytes', async () => {
    let resolve!: (blob: Blob) => void;
    vi.mocked(getCloudOutputPreview).mockImplementation(() => new Promise(done => { resolve = done; }));
    const store = mount();
    const signal = vi.mocked(getCloudOutputPreview).mock.calls[0][2];
    act(() => store.set(cloudConfigAtom, config('b')));
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(signal.aborted).toBe(true);
    await act(async () => resolve(new Blob(['data'])));
    expect(URL.createObjectURL).not.toHaveBeenCalled();
    expect(store.get(cloudPreviewSelectionAtom)).toBeNull();
  });
  it('shows explicit Download fallback for oversized output without a byte request', () => {
    mount('large.html', 2 * 1024 * 1024 + 1);
    expect(screen.getByRole('alert')).toHaveTextContent('exceeds the 2 MiB preview limit');
    expect(screen.getByRole('button', { name: 'Download' })).toBeVisible();
    expect(getCloudOutputPreview).not.toHaveBeenCalled();
  });
  it('hides and revokes a loaded member preview when a guest invite becomes active', async () => {
    vi.mocked(getCloudOutputPreview).mockResolvedValue(new Blob(['data'], { type: 'image/png' }));
    const store = mount();
    await screen.findByAltText('plot.png');
    act(() => store.set(cloudInviteSessionAtom, { member: false } as CloudInviteSession));
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:verified');
  });
  it('sandboxes HTML without script or same-origin privileges and denies external assets', async () => {
    const text = '<h1>report</h1><script>parent.document.body.remove()</script>';
    vi.mocked(getCloudOutputPreview).mockResolvedValue({ size: text.length, text: async () => text } as Blob);
    mount('report.html', text.length);
    await waitFor(() => expect(document.querySelector('iframe[title="report.html"]')).toHaveAttribute('srcdoc'));
    expect(document.querySelector('iframe[title="report.html"]')).toHaveAttribute('sandbox', '');
    expect(document.querySelector('iframe[title="report.html"]')?.getAttribute('srcdoc')).toContain("default-src 'none'");
    expect(screen.getByText(/interactive scripts are disabled/)).toBeVisible();
  });
});
