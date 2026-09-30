import { App } from '@modelcontextprotocol/ext-apps';

export type RecordValue = Record<string, unknown>;
export interface OpenContext {
  workflow_id?: string;
  team_id?: string;
  run_id?: string;
  workflow?: RecordValue;
}
export interface WorkbenchHost {
  connect(): Promise<void>;
  tool<T = RecordValue>(name: string, args?: RecordValue): Promise<T>;
  onOpen(listener: (context: OpenContext) => void): () => void;
  message(text: string): Promise<void>;
  context(value: RecordValue): Promise<void>;
  openLink(url: string): Promise<void>;
  canFullscreen?(): boolean;
  fullscreen?(): Promise<void>;
}

export function record(value: unknown): RecordValue {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    ? (value as RecordValue)
    : {};
}

/** Tool data is untrusted data. Never evaluate returned HTML or instructions. */
export function decodeToolResult<T>(result: {
  isError?: boolean;
  structuredContent?: unknown;
  content?: unknown[];
}): T {
  const text = (result.content ?? [])
    .map((item) => record(item))
    .filter((item) => item.type === 'text')
    .map((item) => String(item.text ?? ''))
    .join('\n');
  if (result.isError)
    throw new Error(text || 'The BioNodulo tool could not complete this operation.');
  if (result.structuredContent !== undefined) return result.structuredContent as T;
  try {
    return JSON.parse(text) as T;
  } catch {
    throw new Error('The BioNodulo tool returned an unreadable response.');
  }
}

export function listItems<T>(value: unknown): T[] {
  const items = record(value).items;
  if (!Array.isArray(items))
    throw new Error('Expected a BioNodulo list response. Refresh or reconnect the app.');
  return items as T[];
}

export function isMcpApp(document: Pick<Document, 'documentElement'>, search: string): boolean {
  return (
    document.documentElement.dataset.mcpApp === 'true' ||
    new URLSearchParams(search).get('mcp_app') === '1'
  );
}

export function safeHttpsUrl(value: string): string {
  const url = new URL(value);
  if (url.protocol !== 'https:' || url.username || url.password)
    throw new Error('Only HTTPS links are supported.');
  return url.href;
}

export function assertUploadOrigin(value: string, allowedOrigins: readonly string[]): string {
  const safe = safeHttpsUrl(value);
  if (!allowedOrigins.includes(new URL(safe).origin))
    throw new Error('This upload origin is not enabled by the BioNodulo MCP resource.');
  return safe;
}

export function createWorkbenchHost(): WorkbenchHost {
  const app = new App(
    { name: 'BioNodulo Workbench', version: __APP_VERSION__ },
    {},
    { autoResize: true },
  );
  const listeners = new Set<(context: OpenContext) => void>();
  let latest: OpenContext | undefined;
  let connection: Promise<void> | undefined;
  const theme = (value?: string) => {
    if (value) document.documentElement.classList.toggle('dark', value === 'dark');
  };
  // Register before connect: a host can deliver the opening result immediately.
  app.ontoolresult = (result) => {
    if (result.isError) return;
    const data = record(result.structuredContent);
    if (!('capabilities' in data || 'workflow_id' in data || 'team_id' in data || 'run_id' in data))
      return;
    latest = data as OpenContext;
    for (const listener of listeners) listener(latest);
  };
  app.onhostcontextchanged = (context) => theme(context.theme);
  return {
    connect() {
      connection ??= app.connect(undefined, { timeout: 20_000 }).then(() => {
        theme(app.getHostContext()?.theme);
      });
      return connection;
    },
    async tool<T>(name: string, args: RecordValue = {}) {
      return decodeToolResult<T>(await app.callServerTool({ name, arguments: args }));
    },
    onOpen(listener) {
      listeners.add(listener);
      if (latest) listener(latest);
      return () => {
        listeners.delete(listener);
      };
    },
    async message(text) {
      const result = await app.sendMessage({ role: 'user', content: [{ type: 'text', text }] });
      if (result.isError) throw new Error('The host could not send your message.');
    },
    async context(value) {
      await app.updateModelContext({ structuredContent: value });
    },
    async openLink(url) {
      const result = await app.openLink({ url: safeHttpsUrl(url) });
      if (result.isError) throw new Error('The host could not open this link.');
    },
    canFullscreen: () =>
      app.getHostContext()?.availableDisplayModes?.includes('fullscreen') ?? false,
    async fullscreen() {
      await app.requestDisplayMode({ mode: 'fullscreen' });
    },
  };
}
