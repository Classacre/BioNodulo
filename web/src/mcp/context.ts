import { redactSecrets } from '../utils/redaction';

/** Context contains the draft, never run download URLs or upload responses.
 * Also strip credentials/query signatures from URLs a user pasted into nodes. */
export function contextDraft(value: unknown): unknown {
  const clean = (item: unknown): unknown => {
    if (typeof item === 'string')
      return item.replace(/https?:\/\/[^\s"'<>]+/g, (text) => {
        try {
          const url = new URL(text);
          const privateParts = Boolean(url.username || url.password || url.search || url.hash);
          url.username = '';
          url.password = '';
          url.search = '';
          url.hash = '';
          return privateParts ? `${url.href} [URL credentials/query omitted]` : text;
        } catch {
          return '[invalid URL omitted]';
        }
      });
    if (Array.isArray(item)) return item.map(clean);
    if (item && typeof item === 'object')
      return Object.fromEntries(Object.entries(item).map(([key, value]) => [key, clean(value)]));
    return item;
  };
  return clean(redactSecrets(value));
}
