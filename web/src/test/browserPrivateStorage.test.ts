import { beforeEach, describe, expect, it } from 'vitest';
import { browserStorageKey, resolveBrowserStorageScope } from '../utils/browserStorageScope';
import { clearRecentWorkflows, getRecentWorkflows, refreshRecentThumbnail, rememberRecentWorkflow, setRecentTags } from '../state/recentWorkflows';
import { deleteWorkflowSnippet, listWorkflowSnippets, saveWorkflowSnippet } from '../state/workflowSnippets';

const local = resolveBrowserStorageScope({ editorMode: false, cloudMode: false });
const cloud = (user = 'user-a', team = 'team-a') => resolveBrowserStorageScope({ editorMode: true, user: { id: user }, team: { id: team } });

describe('private browser storage ownership', () => {
  beforeEach(() => localStorage.clear());

  it('requires an explicit desktop or authenticated cloud member and encodes delimiters', () => {
    expect(local.storageSuffix).toBe('');
    expect(resolveBrowserStorageScope(null).storageSuffix).toBeNull();
    expect(resolveBrowserStorageScope({ editorMode: true }).storageSuffix).toBeNull();
    expect(resolveBrowserStorageScope({ editorMode: true, user: { id: 'a' }, team: { id: 'b' } }, true).storageSuffix).toBeNull();
    expect(cloud('a.b', 'c').identity).not.toBe(cloud('a', 'b.c').identity);
    expect(browserStorageKey('private', cloud('a.b', 'c'))).toBe('private.cloud.a%2Eb.c');
  });

  it('keeps legacy desktop snippets and recents local instead of adopting an unknown owner', () => {
    saveWorkflowSnippet({ name: 'Desktop graph', nodes: [], edges: [] });
    rememberRecentWorkflow({ id: 'desktop', name: 'Desktop name', source: 'import' });
    expect(listWorkflowSnippets(local)[0].name).toBe('Desktop graph');
    expect(getRecentWorkflows(local)[0].name).toBe('Desktop name');
    expect(listWorkflowSnippets(cloud())).toEqual([]);
    expect(getRecentWorkflows(cloud())).toEqual([]);
    const blocked = resolveBrowserStorageScope(null);
    saveWorkflowSnippet({ name: 'Blocked', nodes: [], edges: [] }, blocked);
    rememberRecentWorkflow({ id: 'blocked', name: 'Blocked', source: 'import' }, blocked);
    expect(localStorage.length).toBe(2);
    expect(listWorkflowSnippets(blocked)).toEqual([]);
    expect(getRecentWorkflows(blocked)).toEqual([]);
  });

  it('isolates complete snippet content and all recent mutations across accounts and teams', () => {
    const a = cloud(); const b = cloud('user-a', 'team-b'); const c = cloud('user-b');
    const node = { id: 'n', type: 'input_file', position: [0, 0] as [number, number], params: { path: 'private-name.fastq' } };
    const saved = saveWorkflowSnippet({ name: 'A graph', nodes: [node], edges: [] }, a);
    rememberRecentWorkflow({ id: 'same-id', name: 'A name', source: 'import', thumbnailUrl: 'A graph preview' }, a);
    rememberRecentWorkflow({ id: 'same-id', name: 'B name', source: 'import' }, b);
    setRecentTags('same-id', ['B tag'], b);
    refreshRecentThumbnail('same-id', 'B preview', { name: 'B edit' }, b);
    deleteWorkflowSnippet(saved.id, b);
    expect(listWorkflowSnippets(a)[0].nodes[0].params.path).toBe('private-name.fastq');
    expect(listWorkflowSnippets(b)).toEqual([]);
    expect(listWorkflowSnippets(c)).toEqual([]);
    expect(getRecentWorkflows(a)[0]).toMatchObject({ name: 'A name', thumbnailUrl: 'A graph preview' });
    expect(getRecentWorkflows(b)[0]).toMatchObject({ name: 'B edit', tags: ['B tag'], thumbnailUrl: 'B preview' });
    expect(getRecentWorkflows(c)).toEqual([]);
    clearRecentWorkflows(b);
    expect(getRecentWorkflows(a)).toHaveLength(1);
    expect(getRecentWorkflows(b)).toEqual([]);
  });
});
