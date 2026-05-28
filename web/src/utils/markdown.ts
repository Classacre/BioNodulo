/**
 * Minimal escape-then-format markdown renderer for AI assistant replies.
 *
 * Why hand-rolled and not `marked`/`react-markdown`: this app already ships
 * 800+ kB of JS, and a third dependency for one rendering surface is hard to
 * justify. The grammar we need from LLM output is a small fixed set:
 *   - inline code: `code`
 *   - code fences: ```lang\n...\n```
 *   - bold: **text**
 *   - italics: *text* or _text_
 *   - headings: # H1, ## H2, ### H3
 *   - bullet lists: lines starting with `- ` or `* `
 *   - numbered lists: lines starting with `1. `
 *   - links: [label](url) — only http(s) URLs are rendered, others are inlined as plain text
 *
 * Security: every input character is HTML-escaped first, then we replace
 * markdown markers with safe `<span>` / `<a>` etc. The result is mounted via
 * `dangerouslySetInnerHTML` but the only HTML present is what this function
 * itself emitted, so there is no path for user/LLM content to inject script
 * tags or attributes.
 */

const ESCAPE: Record<string, string> = {
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;',
};

function escapeHtml(text: string): string {
  return text.replace(/[&<>"']/g, ch => ESCAPE[ch] ?? ch);
}

function safeHref(url: string): string | null {
  const lower = url.trim().toLowerCase();
  if (lower.startsWith('http://') || lower.startsWith('https://')) return url;
  return null;
}

function renderInline(text: string): string {
  // Inline code first so `` *foo* `` inside backticks isn't bolded.
  let out = text.replace(/`([^`]+)`/g, (_m, code) => `<code class="md-inline-code">${escapeHtml(code)}</code>`);
  // Links — only safe http(s) get a real <a>, others render as label (url).
  out = out.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (m, label, url) => {
    const href = safeHref(url);
    const safeLabel = escapeHtml(label);
    if (!href) return `${safeLabel} (${escapeHtml(url)})`;
    return `<a href="${escapeHtml(href)}" target="_blank" rel="noopener noreferrer">${safeLabel}</a>`;
  });
  out = out.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  out = out.replace(/(^|[^*])\*([^*\n]+)\*(?!\*)/g, '$1<em>$2</em>');
  out = out.replace(/(^|[^_])_([^_\n]+)_/g, '$1<em>$2</em>');
  return out;
}

export function renderMarkdownToHtml(input: string): string {
  if (!input) return '';
  const escaped = escapeHtml(input);
  const lines = escaped.split(/\r?\n/);
  const out: string[] = [];
  let inFence = false;
  let fenceLines: string[] = [];
  let inUL = false;
  let inOL = false;

  const closeLists = () => {
    if (inUL) { out.push('</ul>'); inUL = false; }
    if (inOL) { out.push('</ol>'); inOL = false; }
  };

  for (const line of lines) {
    const fenceMatch = line.match(/^```(\w+)?\s*$/);
    if (fenceMatch) {
      if (inFence) {
        out.push(`<pre class="md-fence"><code>${fenceLines.join('\n')}</code></pre>`);
        fenceLines = [];
        inFence = false;
      } else {
        closeLists();
        inFence = true;
      }
      continue;
    }
    if (inFence) {
      fenceLines.push(line);
      continue;
    }
    const heading = line.match(/^(#{1,3})\s+(.+)$/);
    if (heading) {
      closeLists();
      const level = heading[1].length;
      out.push(`<h${level + 2} class="md-heading">${renderInline(heading[2])}</h${level + 2}>`);
      continue;
    }
    const ul = line.match(/^[-*]\s+(.+)$/);
    if (ul) {
      if (inOL) { out.push('</ol>'); inOL = false; }
      if (!inUL) { out.push('<ul class="md-list">'); inUL = true; }
      out.push(`<li>${renderInline(ul[1])}</li>`);
      continue;
    }
    const ol = line.match(/^\d+\.\s+(.+)$/);
    if (ol) {
      if (inUL) { out.push('</ul>'); inUL = false; }
      if (!inOL) { out.push('<ol class="md-list">'); inOL = true; }
      out.push(`<li>${renderInline(ol[1])}</li>`);
      continue;
    }
    if (line.trim() === '') {
      closeLists();
      out.push('');
      continue;
    }
    closeLists();
    out.push(`<p class="md-para">${renderInline(line)}</p>`);
  }
  if (inFence) {
    out.push(`<pre class="md-fence"><code>${fenceLines.join('\n')}</code></pre>`);
  }
  closeLists();
  return out.join('\n');
}
