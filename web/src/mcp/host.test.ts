import { describe, expect, it } from 'vitest';
import { assertUploadOrigin, decodeToolResult, isMcpApp, listItems, safeHttpsUrl } from './host';
import { normalizeObjectInfo } from '../hooks/data/useObjectInfo';
import { defaultsFor } from '../utils';
import { contextDraft } from './context';
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
