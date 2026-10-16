import { act, fireEvent, render, screen, waitFor, cleanup } from '@testing-library/react';
import { Provider, createStore } from 'jotai';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import CloudOutputPreviewModal from '../components/modals/CloudOutputPreviewModal';
import { cloudConfigAtom, type CloudConfig } from '../state/appAtoms';
import { cloudPreviewSelectionAtom } from '../state/cloudPreview';
import { cloudLogStorageKey } from '../hooks/cloud/useCloudLogStorage';
import { call, getCloudOutputPreview } from '../api/website';
import { cloudInviteSessionAtom, type CloudInviteSession } from '../collab/cloudInvite';

vi.mock('../api/website', () => ({ getCloudOutputPreview: vi.fn(), call: vi.fn() }));
vi.mock('../mcp/runtime', () => ({ getMcpRuntime: () => null }));
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
    vi.mocked(call).mockReset();
    vi.stubGlobal('URL', class extends URL { static createObjectURL = vi.fn(() => 'blob:verified'); static revokeObjectURL = vi.fn(); });
  });
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });
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
  it('explains script-dependent reports instead of showing an empty iframe', async () => {
    const text = '<div class="plotly-graph-div"></div><script>Plotly.newPlot("chart",[])</script>';
    vi.mocked(getCloudOutputPreview).mockResolvedValue({ size: text.length, text: async () => text } as Blob);
    mount('coverage.html', text.length);
    expect(await screen.findByRole('alert')).toHaveTextContent('needs JavaScript');
    expect(screen.getByRole('button', { name: 'Download' })).toBeVisible();
    expect(document.querySelector('iframe')).toBeNull();
  });
  it('downloads the full oversized file using a fresh verified attachment URL', async () => {
    const chosen = selection('large.html', 3 * 1024 * 1024);
    vi.mocked(call).mockResolvedValue({ outputs: [{ ...chosen.output, url: 'https://files.example/fresh' }] });
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
      expect(this.isConnected).toBe(true);
      expect(this.href).toBe('https://files.example/fresh');
    });
    mount('large.html', chosen.output.size);
    fireEvent.click(screen.getByRole('button', { name: 'Download' }));
    await waitFor(() => expect(click).toHaveBeenCalledOnce());
    expect(call).toHaveBeenCalledWith('/runs/run/outputs');
    expect(getCloudOutputPreview).not.toHaveBeenCalled();
  });
  it.each(['close', 'team switch', 'unmount'])('does not open a late download after %s', async change => {
    let resolve!: (value: unknown) => void;
    vi.mocked(call).mockImplementation(() => new Promise(done => { resolve = done; }));
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined);
    const store = mount('large.html', 3 * 1024 * 1024);
    fireEvent.click(screen.getByRole('button', { name: 'Download' }));
    if (change === 'close') fireEvent.click(screen.getByRole('button', { name: 'Close cloud preview' }));
    else if (change === 'team switch') act(() => store.set(cloudConfigAtom, config('b')));
    else cleanup();
    await act(async () => resolve({ outputs: [{ ...selection('large.html', 3 * 1024 * 1024).output, url: 'https://files.example/fresh' }] }));
    expect(click).not.toHaveBeenCalled();
  });
  it('rejects a changed artifact instead of opening a different file under the same key', async () => {
    vi.mocked(call).mockResolvedValue({ outputs: [{ ...selection('large.html', 3 * 1024 * 1024).output, sha256: 'b'.repeat(64), url: 'https://files.example/fresh' }] });
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined);
    mount('large.html', 3 * 1024 * 1024);
    fireEvent.click(screen.getByRole('button', { name: 'Download' }));
    expect(await screen.findByText('This output changed. Refresh the run before downloading.')).toBeVisible();
    expect(click).not.toHaveBeenCalled();
  });
  it('does not revive a late download when the same selection object returns after another owner', async () => {
    let resolve!: (value: unknown) => void;
    vi.mocked(call).mockImplementation(() => new Promise(done => { resolve = done; }));
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined);
    const store = mount('large.html', 3 * 1024 * 1024);
    const original = store.get(cloudPreviewSelectionAtom);
    fireEvent.click(screen.getByRole('button', { name: 'Download' }));
    act(() => store.set(cloudConfigAtom, config('b')));
    act(() => { store.set(cloudConfigAtom, config('a')); store.set(cloudPreviewSelectionAtom, original); });
    await act(async () => resolve({ outputs: [{ ...original!.output, url: 'https://files.example/fresh' }] }));
    expect(click).not.toHaveBeenCalled();
  });
});
