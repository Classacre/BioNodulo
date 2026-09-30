import { describe, expect, it } from 'vitest';
import {
  draftReducer,
  fromSaved,
  initialDraft,
  readWorkflow,
  uploadBindings,
  type CloudWorkflow,
} from './draft';
import { assertUploadOrigin, decodeToolResult, isMcpApp, listItems, safeHttpsUrl } from './host';
import { normalizeObjectInfo } from '../hooks/data/useObjectInfo';
import { defaultsFor } from '../utils';
import { contextDraft } from './context';

const saved = (revision = 1, name = 'Original'): CloudWorkflow => ({
  id: 'workflow-1',
  name,
  updatedAt: `2026-10-01T00:00:0${revision}.000Z`,
  definition: { nodes: [], edges: [] },
});
describe('MCP workbench drafts', () => {
  it('accepts external AI edits when the local workflow is clean', () => {
    const result = draftReducer(fromSaved(saved()), { type: 'remote', saved: saved(2, 'AI edit') });
    expect(result.draft.name).toBe('AI edit');
    expect(result.dirty).toBe(false);
  });
  it('retains unsaved edits and records a remote conflict', () => {
    const local = draftReducer(fromSaved(saved()), { type: 'edit', patch: { name: 'My draft' } });
    const result = draftReducer(local, { type: 'remote', saved: saved(2, 'AI edit') });
    expect(result.draft.name).toBe('My draft');
    expect(result.conflict?.name).toBe('AI edit');
    expect(result.saved?.updatedAt).toBe(saved().updatedAt);
  });
  it('preserves edits made while Save is in flight and advances the guarded revision', () => {
    const initial = fromSaved(saved());
    const edited = draftReducer(initial, { type: 'edit', patch: { name: 'Typed during save' } });
    const result = draftReducer(edited, {
      type: 'saved',
      saved: saved(2),
      submitted: initial.draft,
    });
    expect(result.draft.name).toBe('Typed during save');
    expect(result.dirty).toBe(true);
    expect(result.saved?.updatedAt).toBe(saved(2).updatedAt);
  });
  it('does not let an old poll regress a successful save', () => {
    const state = fromSaved(saved(3));
    expect(draftReducer(state, { type: 'remote', saved: saved(2) })).toBe(state);
    expect(draftReducer(state, { type: 'remote', saved: { ...saved(4), id: 'another' } })).toBe(
      state,
    );
  });
  it('keeps an explicit undo and redo history', () => {
    const edited = draftReducer(initialDraft(), { type: 'edit', patch: { name: 'A change' } });
    const undo = draftReducer(edited, { type: 'undo' });
    expect(undo.draft.name).toBe('Untitled workflow');
    expect(draftReducer(undo, { type: 'redo' }).draft.name).toBe('A change');
  });
  it('rejects malformed imports before the canvas sees them', () => {
    expect(() => readWorkflow({ nodes: [{}], edges: [] })).toThrow('Invalid');
    expect(() =>
      readWorkflow({
        nodes: [],
        edges: [{ id: 'e', from: { node: 'missing' }, to: { node: 'x' } }],
      }),
    ).toThrow('missing');
    expect(() => readWorkflow({})).toThrow('arrays');
  });
  it('stages only selected-team upload paths including nested values', () => {
    const workflow = readWorkflow({
      nodes: [
        {
          id: 'input',
          type: 'input_file',
          position: [0, 0],
          params: {
            file: 'uploads/team-a/id__reads.fastq',
            other: ['uploads/team-b/no', 'https://example.org/file'],
          },
        },
      ],
      edges: [],
    });
    expect(uploadBindings(workflow, 'team-a')).toEqual({
      'uploads/team-a/id__reads.fastq': {
        uploadKey: 'uploads/team-a/id__reads.fastq',
        kind: 'file',
      },
    });
    expect(uploadBindings(workflow)).toEqual({});
  });
});
describe('MCP host boundary', () => {
  it('omits secrets and signed URL credentials from host model context', () => {
    const result = JSON.stringify(
      contextDraft({
        api_key: 'private',
        file: 'https://user:private@files.test/input.tsv?X-Amz-Signature=private',
        command: 'curl https://files.test/x?token=private',
        public: 'https://doi.org/10.1000/example',
      }),
    );
    expect(result).not.toContain('private');
    expect(result).toContain('URL credentials/query omitted');
    expect(result).toContain('https://doi.org/10.1000/example');
  });
  it('prefers structured content and surfaces server errors without evaluating text', () => {
    expect(
      decodeToolResult({
        structuredContent: { name: '<script>bad()</script>' },
        content: [{ type: 'text', text: 'different' }],
      }),
    ).toEqual({ name: '<script>bad()</script>' });
    expect(() =>
      decodeToolResult({
        isError: true,
        content: [{ type: 'text', text: 'Workflow revision conflict (HTTP 409)' }],
      }),
    ).toThrow('revision conflict');
    expect(() =>
      decodeToolResult({ content: [{ type: 'text', text: '<html>failure</html>' }] }),
    ).toThrow('unreadable');
  });
  it('requires list records and supports legacy JSON text results', () => {
    expect(listItems({ items: [1, 2] })).toEqual([1, 2]);
    expect(() => listItems([])).toThrow('list response');
    expect(decodeToolResult({ content: [{ type: 'text', text: '{"id":"one"}' }] })).toEqual({
      id: 'one',
    });
  });
  it('selects MCP mode for opaque-resource markers and local fixtures', () => {
    expect(
      isMcpApp(
        { documentElement: { dataset: { mcpApp: 'true' } } } as Pick<Document, 'documentElement'>,
        '',
      ),
    ).toBe(true);
    expect(isMcpApp(document, '?mcp_app=1')).toBe(true);
    expect(isMcpApp(document, '?mcp_app=0')).toBe(false);
  });
  it('restricts PUTs to exact declared HTTPS origins', () => {
    expect(
      assertUploadOrigin('https://uploads.example.org/key?signature=temporary', [
        'https://uploads.example.org',
      ]),
    ).toContain('/key?');
    for (const url of [
      'http://uploads.example.org/key',
      'https://uploads.example.org.evil.test/key',
      'https://user:password@uploads.example.org/key',
      'javascript:alert(1)',
    ])
      expect(() => assertUploadOrigin(url, ['https://uploads.example.org'])).toThrow();
    expect(() => safeHttpsUrl('/api/me')).toThrow();
  });
  it('uses the real object_info normalizer for canvas ports and defaults', () => {
    const catalog = normalizeObjectInfo({
      input_file: {
        name: 'input_file',
        display_name: 'Input File',
        input: {
          required: { file: ['FILE', { default: '' }] },
          optional: { source: ['STRING', { default: 'auto' }] },
        },
        output: ['FILE'],
        output_name: ['file'],
      },
    });
    expect(catalog.input_file.return_names).toEqual(['file']);
    expect(catalog.input_file.input_types.required?.file.type).toBe('FILE');
    expect(defaultsFor(catalog.input_file)).toEqual({ file: '', source: 'auto' });
  });
});
