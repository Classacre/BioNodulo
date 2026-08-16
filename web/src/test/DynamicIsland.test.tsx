import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { resolve } from 'node:path';
import { readFileSync } from 'node:fs';
import type { Workflow } from '../types';

const apiMocks = vi.hoisted(() => ({
  apiGet: vi.fn(),
}));

vi.mock('../api/client', () => apiMocks);

const storage = new Map<string, string>();
const localStorageStub: Storage = {
  get length() {
    return storage.size;
  },
  clear: () => storage.clear(),
  getItem: (key: string) => storage.get(key) ?? null,
  key: (index: number) => Array.from(storage.keys())[index] ?? null,
  removeItem: (key: string) => {
    storage.delete(key);
  },
  setItem: (key: string, value: string) => {
    storage.set(key, String(value));
  },
};

const workflow: Workflow = {
  version: '1.0',
  app: 'BioNodulo',
  name: 'Stats workflow',
  description: '',
  nodes: [
    {
      id: 'n1',
      type: 'input_file',
      position: [0, 0],
      params: {},
      node_info: { id: 'input_file', display_name: 'Input', category: 'Input' },
    } as Workflow['nodes'][number],
  ],
  edges: [],
  groups: [],
};

import { notify, dismissNotification } from '../state/notifications';
import DynamicIsland, { EMPTY_DOI_TELEMETRY } from '../components/canvas/DynamicIsland';

describe('DynamicIsland', () => {
  beforeEach(() => {
    vi.stubGlobal('localStorage', localStorageStub);
    apiMocks.apiGet.mockRejectedValue(new Error('no backend'));
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('renders the minimized pill with workflow shape and nothing else', () => {
    render(<DynamicIsland workflow={workflow} systemStats={false} />);
    const pill = screen.getByRole('button');
    expect(pill.className).toContain('island-pill');
    expect(pill.textContent).toContain('1');
    // No peek card, no full panel in the default state.
    expect(document.querySelector('.island-peek')).toBeNull();
    expect(document.querySelector('.island-full')).toBeNull();
  });

  it('renders nothing when the workflow is empty and there is nothing to show', () => {
    const empty = { ...workflow, nodes: [] };
    const { container } = render(<DynamicIsland workflow={empty} systemStats={false} />);
    expect(container.firstChild).toBeNull();
  });

  it('peeks (partial expand) when an AI build stage advances, and folds back after quiet', async () => {
    vi.useFakeTimers();
    try {
      const { rerender } = render(
        <DynamicIsland workflow={workflow} systemStats={false} doi={EMPTY_DOI_TELEMETRY} />,
      );
      expect(document.querySelector('.island-peek')).toBeNull();

      rerender(
        <DynamicIsland
          workflow={workflow}
          systemStats={false}
          doi={{ ...EMPTY_DOI_TELEMETRY, active: true, lines: ['Analyzing paper…'] }}
        />,
      );
      // The event-driven partial expansion — NOT the full panel.
      expect(document.querySelector('.island-peek')).not.toBeNull();
      expect(document.querySelector('.island-full')).toBeNull();
      expect(document.querySelector('.island-peek-line')?.textContent).toContain('Analyzing paper');

      // Quiet for longer than the peek window → back to the pill.
      act(() => { vi.advanceTimersByTime(6000); });
      expect(document.querySelector('.island-peek')).toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });

  it('fully expands on click and folds on the collapse button', () => {
    render(<DynamicIsland workflow={workflow} systemStats={false} />);
    fireEvent.click(screen.getByRole('button'));
    expect(document.querySelector('.island-full')).not.toBeNull();
    // Shape stats row with the node/edge counts renders in the full panel.
    expect(document.querySelector('.workflow-stats-row')?.textContent).toContain('1');

    fireEvent.click(screen.getByRole('button', { name: /collapse/i }));
    expect(document.querySelector('.island-full')).toBeNull();
    expect(screen.getByRole('button').className).toContain('island-pill');
  });

  it('keeps the user-pinned state: a click beats auto-peek/auto-fold', () => {
    vi.useFakeTimers();
    try {
      const { rerender } = render(
        <DynamicIsland workflow={workflow} systemStats={false} doi={EMPTY_DOI_TELEMETRY} />,
      );
      // User expands to the full panel…
      fireEvent.click(screen.getByRole('button'));
      // …then AI lines arrive. The island must NOT leave the full state.
      rerender(
        <DynamicIsland
          workflow={workflow}
          systemStats={false}
          doi={{ ...EMPTY_DOI_TELEMETRY, active: true, lines: ['stage 1'] }}
        />,
      );
      rerender(
        <DynamicIsland
          workflow={workflow}
          systemStats={false}
          doi={{ ...EMPTY_DOI_TELEMETRY, active: false, lines: ['stage 1'] }}
        />,
      );
      act(() => { vi.advanceTimersByTime(10000); });
      expect(document.querySelector('.island-full')).not.toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });

  it('shows an unread badge and peeks for new notifications', async () => {
    render(<DynamicIsland workflow={workflow} systemStats={false} />);
    expect(document.querySelector('.island-badge')).toBeNull();

    act(() => {
      notify({ title: 'Run finished', tone: 'success' });
    });
    await waitFor(() => expect(document.querySelector('.island-badge')).not.toBeNull());
    // A new toast peeks the island with its title.
    await waitFor(() =>
      expect(document.querySelector('.island-peek-title')?.textContent).toContain('Run finished'),
    );

    // Full panel lists it and dismissing removes it.
    fireEvent.click(document.querySelector('.island-pill') as HTMLElement);
    expect(screen.getByText('Run finished')).toBeTruthy();
    const dismiss = screen.getByRole('button', { name: /dismiss/i });
    fireEvent.click(dismiss);
    await waitFor(() => expect(screen.queryByText('Run finished')).toBeNull());
  });
});

describe('DynamicIsland i18n', () => {
  it('has island keys in both locales', () => {
    for (const locale of ['en', 'es']) {
      const source = readFileSync(
        resolve(__dirname, `../i18n/locales/${locale}.ts`),
        'utf-8',
      );
      expect(source, `${locale} locale`).toContain('island: {');
      expect(source, `${locale} locale`).toContain('notificationsTitle');
    }
  });
});
