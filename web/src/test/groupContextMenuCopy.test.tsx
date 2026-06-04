import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import type { WorkflowGroup, WorkflowNode } from '../types';

vi.mock('../components/ui', () => ({
  promptDialog: vi.fn(),
}));

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

const groups: WorkflowGroup[] = [{
  id: 'group-1',
  name: 'QC group',
  position: [0, 0],
  width: 300,
  height: 220,
  color: '#3b82f6',
  collapsed: false,
}];

const nodes: WorkflowNode[] = [{
  id: 'fastqc-1',
  type: 'fastqc',
  position: [40, 40],
  params: {},
  ui: { title: 'FastQC' },
}];

describe('GroupContextMenu copy i18n', () => {
  beforeEach(() => {
    storage.clear();
    vi.stubGlobal('localStorage', localStorageStub);
  });

  afterEach(async () => {
    const { setLanguage } = await import('../i18n');
    const { promptDialog } = await import('../components/ui');
    await setLanguage('en');
    vi.mocked(promptDialog).mockReset();
    storage.clear();
    vi.unstubAllGlobals();
  });

  it('renders group menu actions and rename prompt from the active locale', async () => {
    const { default: GroupContextMenu } = await import('../components/canvas/GroupContextMenu');
    const { promptDialog } = await import('../components/ui');
    const { setLanguage } = await import('../i18n');
    const onGroupsChange = vi.fn();
    const onNodesChange = vi.fn();
    const onClose = vi.fn();

    vi.mocked(promptDialog).mockResolvedValue('QC renamed');
    await setLanguage('es');

    const { unmount } = render(
      <GroupContextMenu
        x={12}
        y={24}
        groupId="group-1"
        groups={groups}
        nodes={nodes}
        onGroupsChange={onGroupsChange}
        onNodesChange={onNodesChange}
        onClose={onClose}
      />,
    );

    [
      'Cambiar nombre',
      'Definir color',
      'Ajustar a nodos',
      'Silenciar todo',
      'Activar sonido en todo',
      'Omitir todo',
      'Habilitar todo',
      'Fijar todo',
      'Desfijar todo',
      'Eliminar grupo',
    ].forEach(label => expect(screen.getByText(label)).toBeInTheDocument());

    await act(async () => {
      fireEvent.click(screen.getByText('Cambiar nombre'));
    });

    await waitFor(() => expect(promptDialog).toHaveBeenCalledWith({
      title: 'Renombrar grupo',
      message: 'Elige un nombre de grupo.',
      inputLabel: 'Nombre del grupo',
      defaultValue: 'QC group',
    }));
    expect(onGroupsChange).toHaveBeenCalledWith([{ ...groups[0], name: 'QC renamed' }]);

    unmount();
    onClose.mockClear();
    render(
      <GroupContextMenu
        x={12}
        y={24}
        groupId="group-1"
        groups={groups}
        nodes={nodes}
        onGroupsChange={onGroupsChange}
        onNodesChange={onNodesChange}
        onClose={onClose}
      />,
    );

    fireEvent.click(screen.getByText('Definir color'));
    expect(screen.getByText('← Atras')).toBeInTheDocument();
  });

  it('keeps group context menu copy behind i18n keys', () => {
    const source = readFileSync(resolve(__dirname, '../components/canvas/GroupContextMenu.tsx'), 'utf8');

    expect(source).toContain('canvas.renameGroup');
    [
      '← Back',
      'Rename group',
      'Choose a group name.',
      'Group name',
      'Set Color',
      'Fit to Nodes',
      'Mute All',
      'Unmute All',
      'Bypass All',
      'Enable All',
      'Pin All',
      'Unpin All',
      'Delete Group',
    ].forEach(text => expect(source).not.toContain(text));
  });
});
