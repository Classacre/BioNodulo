import { useState, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import type { TFunction } from 'i18next';
import Icon from '../ui/Icon';
import type { NodeMetadata, ObjectInfo } from '../../types';

interface HelpWikiPanelProps {
  onClose: () => void;
  /** Currently selected node — when set, the panel surfaces node-specific docs first. */
  selectedNode?: { id: string; type: string; meta?: NodeMetadata; title?: string } | null;
  /** Optional registry so search can look across node names + descriptions. */
  objectInfo?: ObjectInfo;
}

type HelpNode = { id: string; type: string; meta?: NodeMetadata; title?: string };

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function renderNodeHelp(node: HelpNode, t: TFunction): string {
  const meta = node.meta;
  const title = node.title || meta?.display_name || node.type;
  const description = meta?.description?.trim()
    ? escapeHtml(meta.description.trim())
    : `<em>${escapeHtml(t('helpWiki.nodeDocs.noDescription'))}</em>`;
  const category = meta?.category || t('helpWiki.nodeDocs.uncategorised');
  const tools = meta?.requires_external_tools || [];
  const required = meta?.input_types?.required || {};
  const optional = meta?.input_types?.optional || {};
  const outputs = meta?.return_types || [];
  const outputNames = meta?.return_names || [];

  const renderInputRow = (name: string, spec: { type?: string; tooltip?: string; description?: string; default?: unknown }) => `
    <tr>
      <td><code>${escapeHtml(name)}</code></td>
      <td><span class="help-port-type">${escapeHtml(String(spec.type || 'STRING'))}</span></td>
      <td>${spec.tooltip || spec.description ? escapeHtml(String(spec.tooltip || spec.description)) : ''}${spec.default !== undefined ? ` <span class="help-port-default">${escapeHtml(t('helpWiki.nodeDocs.defaultValue', { value: String(spec.default) }))}</span>` : ''}</td>
    </tr>`;

  const inputRows = [
    ...Object.entries(required).map(([name, spec]) => renderInputRow(name, spec as { type?: string; tooltip?: string; description?: string; default?: unknown })),
    ...Object.entries(optional).map(([name, spec]) => renderInputRow(name, spec as { type?: string; tooltip?: string; description?: string; default?: unknown })),
  ].join('');

  const outputRows = outputs.map((type, idx) => `
    <tr>
      <td><code>${escapeHtml(outputNames[idx] || `out_${idx}`)}</code></td>
      <td><span class="help-port-type">${escapeHtml(type)}</span></td>
    </tr>`).join('');

  return `
    <div class="help-node-doc">
      <h3>${escapeHtml(title)}</h3>
      <div class="help-node-meta">
        <span class="help-meta-pill">${escapeHtml(category)}</span>
        ${meta?.experimental ? `<span class="help-meta-pill help-meta-exp">${escapeHtml(t('helpWiki.nodeDocs.experimental'))}</span>` : ''}
        ${meta?.version ? `<span class="help-meta-pill">v${escapeHtml(meta.version)}</span>` : ''}
      </div>
      <p>${description}</p>
      ${tools.length > 0 ? `<p><strong>${escapeHtml(t('helpWiki.nodeDocs.requires'))}</strong> ${tools.map(tool => `<code>${escapeHtml(tool)}</code>`).join(', ')}</p>` : ''}
      ${inputRows ? `<h4>${escapeHtml(t('helpWiki.nodeDocs.inputs'))}</h4><table class="help-port-table"><thead><tr><th>${escapeHtml(t('helpWiki.nodeDocs.name'))}</th><th>${escapeHtml(t('helpWiki.nodeDocs.type'))}</th><th>${escapeHtml(t('helpWiki.nodeDocs.notes'))}</th></tr></thead><tbody>${inputRows}</tbody></table>` : ''}
      ${outputRows ? `<h4>${escapeHtml(t('helpWiki.nodeDocs.outputs'))}</h4><table class="help-port-table"><thead><tr><th>${escapeHtml(t('helpWiki.nodeDocs.name'))}</th><th>${escapeHtml(t('helpWiki.nodeDocs.type'))}</th></tr></thead><tbody>${outputRows}</tbody></table>` : ''}
      <p class="help-node-hint">${escapeHtml(t('helpWiki.nodeDocs.hint'))}</p>
    </div>
  `;
}

function nodeFromMeta(meta: NodeMetadata): HelpNode {
  return {
    id: meta.id,
    type: meta.id,
    meta,
    title: meta.display_name,
  };
}

type WikiPage = 'getting-started' | 'nodes-reference' | 'templates-guide' | 'custom-nodes' | 'hpc-integration' | 'workflow-converters' | 'keyboard-shortcuts' | 'canvas-features';

const PAGES: { id: WikiPage; titleKey: string; fallbackTitle: string }[] = [
  { id: 'getting-started', titleKey: 'helpWiki.pages.gettingStarted', fallbackTitle: 'Getting Started' },
  { id: 'canvas-features', titleKey: 'helpWiki.pages.canvasFeatures', fallbackTitle: 'Canvas & Nodes' },
  { id: 'nodes-reference', titleKey: 'helpWiki.pages.nodesReference', fallbackTitle: 'Node Reference' },
  { id: 'templates-guide', titleKey: 'helpWiki.pages.templatesGuide', fallbackTitle: 'Templates Guide' },
  { id: 'custom-nodes', titleKey: 'helpWiki.pages.customNodes', fallbackTitle: 'Custom Nodes' },
  { id: 'hpc-integration', titleKey: 'helpWiki.pages.hpcIntegration', fallbackTitle: 'HPC Integration' },
  { id: 'workflow-converters', titleKey: 'helpWiki.pages.workflowConverters', fallbackTitle: 'Workflow Converters' },
  { id: 'keyboard-shortcuts', titleKey: 'helpWiki.pages.keyboardShortcuts', fallbackTitle: 'Keyboard Shortcuts' },
];

const CONTENT: Partial<Record<WikiPage, string>> = {
  'custom-nodes': `
<h3>Custom Nodes</h3>
<p>BioNodulo supports custom nodes for tools not included in the built-in library.</p>

<h4>Creating a Custom Node</h4>
<p>Create a Python file in the <code>custom_nodes/</code> directory:</p>
<pre>
from bionodulo.nodes.command_node import CommandNode

class MyToolNode(CommandNode):
    NODE_ID = "my_tool"
    DISPLAY_NAME = "My Tool"
    CATEGORY = "Utility"
    DESCRIPTION = "Run my custom tool"
    SEARCH_ALIASES = ["mytool", "custom"]
    COMMAND = ["my_tool", "--input", "{inputs.input}", "--output", "{outputs.output}"]
    RETURN_TYPES = ["FILE"]
    RETURN_NAMES = ["output"]

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {"input": {"type": "FILE", "label": "Input file"}},
            "optional": {"threads": {"type": "INT", "default": 4, "min": 1, "max": 64}},
        }
</pre>

<h4>Node Registration</h4>
<p>Custom nodes are automatically discovered on startup. To reload without restarting, restart the backend server.</p>

<h4>Node Info & Documentation</h4>
<p>Set <code>DESCRIPTION</code> for a short summary. Set <code>DOCUMENTATION_URL</code> to link to external docs. Users can view full node info by right-clicking a node and selecting <strong>Node Info</strong>.</p>
`,

  'hpc-integration': `
<h3>HPC Integration</h3>
<p>BioNodulo can submit workflows to High Performance Computing clusters via job schedulers.</p>

<h4>Supported Schedulers</h4>
<table>
<tr><th>Scheduler</th><th>Commands</th><th>Status</th></tr>
<tr><td>SLURM</td><td>sbatch, squeue, scancel</td><td>Fully supported</td></tr>
<tr><td>PBS/Torque</td><td>qsub, qstat, qdel</td><td>Fully supported</td></tr>
<tr><td>SGE</td><td>qsub, qstat, qdel</td><td>Fully supported</td></tr>
</table>

<h4>Configuration</h4>
<ol>
<li>Enable HPC in Settings → HPC or click the HPC toggle in the top bar</li>
<li>Select your scheduler backend</li>
<li>Set partition/account if required</li>
<li>Configure modules to load before execution</li>
<li>Configure walltime, CPUs per task, and memory</li>
</ol>

<h4>Running on HPC</h4>
<p>When HPC mode is enabled, clicking Run will generate a batch job script and submit it to the scheduler. Monitor job status in the HPC panel.</p>

<h4>Environment Modules</h4>
<p>Specify modules to load (e.g., <code>bioinfo/BWA/0.7.17</code>) in the HPC settings. These are loaded via <code>module load</code> before your workflow runs.</p>
`,

  'workflow-converters': `
<h3>Workflow Converters</h3>
<p>Import and export workflows between BioNodulo and other workflow formats.</p>

<h4>Supported Formats</h4>
<table>
<tr><th>Format</th><th>Extension</th><th>Import</th><th>Export</th></tr>
<tr><td>SnakeMake</td><td>.smk / Snakefile</td><td>Yes</td><td>Yes</td></tr>
<tr><td>NextFlow</td><td>.nf / main.nf</td><td>Yes</td><td>Yes</td></tr>
<tr><td>CWL</td><td>.cwl</td><td>Yes</td><td>Yes</td></tr>
<tr><td>Galaxy</td><td>.ga</td><td>Yes</td><td>Yes</td></tr>
<tr><td>JSON</td><td>.json</td><td>Yes</td><td>Yes</td></tr>
</table>

<h4>Exporting</h4>
<p>Click the Export button in the top bar, select the target format, and download the generated file. For SnakeMake and NextFlow, BioNodulo generates rules/processes for each node with proper input/output connections.</p>

<h4>Importing</h4>
<p>Click the Import button, paste the workflow code or upload a file, and BioNodulo will convert it to a node graph. Recognized tools are mapped to built-in nodes; unrecognized steps become Generic Command nodes.</p>

<h4>Limitations</h4>
<ul>
<li>Complex control flow (loops, conditionals) may be simplified</li>
<li>Custom scripts may become Generic Command nodes</li>
<li>Container directives are converted to environment specs</li>
</ul>
`,

  'keyboard-shortcuts': `
<h3>Keyboard Shortcuts</h3>
<table>
<tr><th>Shortcut</th><th>Action</th></tr>
<tr><td><kbd>Ctrl</kbd> + <kbd>F</kbd></td><td>Open node palette / search</td></tr>
<tr><td><kbd>Ctrl</kbd> + <kbd>R</kbd></td><td>Run workflow</td></tr>
<tr><td><kbd>Ctrl</kbd> + <kbd>E</kbd></td><td>Export workflow</td></tr>
<tr><td><kbd>Ctrl</kbd> + <kbd>I</kbd></td><td>Import workflow</td></tr>
<tr><td><kbd>Ctrl</kbd> + <kbd>A</kbd></td><td>Select all nodes</td></tr>
<tr><td><kbd>Ctrl</kbd> + <kbd>C</kbd></td><td>Copy selected nodes</td></tr>
<tr><td><kbd>Ctrl</kbd> + <kbd>V</kbd></td><td>Paste nodes</td></tr>
<tr><td><kbd>Ctrl</kbd> + <kbd>X</kbd></td><td>Cut selected nodes</td></tr>
<tr><td><kbd>Ctrl</kbd> + <kbd>Z</kbd></td><td>Undo</td></tr>
<tr><td><kbd>Ctrl</kbd> + <kbd>Y</kbd></td><td>Redo</td></tr>
<tr><td><kbd>Ctrl</kbd> + <kbd>Shift</kbd> + <kbd>Z</kbd></td><td>Redo (alternative)</td></tr>
<tr><td><kbd>Ctrl</kbd> + <kbd>G</kbd></td><td>Group selected nodes</td></tr>
<tr><td><kbd>Alt</kbd> + <kbd>C</kbd></td><td>Collapse / expand selected nodes</td></tr>
<tr><td><kbd>Delete</kbd> / <kbd>Backspace</kbd></td><td>Delete selected nodes</td></tr>
<tr><td><kbd>Ctrl</kbd> + <kbd>1</kbd>–<kbd>7</kbd></td><td>Toggle left rail panels</td></tr>
<tr><td><kbd>Ctrl</kbd> + <kbd>,</kbd></td><td>Open Settings</td></tr>
<tr><td><kbd>Ctrl</kbd> + <kbd>\`</kbd></td><td>Toggle console</td></tr>
<tr><td><kbd>Alt</kbd> + Drag</td><td>Pan canvas</td></tr>
<tr><td><kbd>Shift</kbd> + Click</td><td>Toggle node selection</td></tr>
<tr><td>Double-click canvas</td><td>Open node palette</td></tr>
<tr><td>Double-click node</td><td>Edit node parameters</td></tr>
<tr><td>Right-click node</td><td>Node context menu</td></tr>
<tr><td>Right-click canvas</td><td>Canvas context menu</td></tr>
<tr><td>Right-click group</td><td>Group context menu</td></tr>
</table>
`,
};

const CONTENT_KEYS: Partial<Record<WikiPage, string>> = {
  'getting-started': 'helpWiki.content.gettingStarted',
  'canvas-features': 'helpWiki.content.canvasFeatures',
  'nodes-reference': 'helpWiki.content.nodesReference',
  'templates-guide': 'helpWiki.content.templatesGuide',
};

function stripHtml(html: string): string {
  const tmp = document.createElement('div');
  tmp.innerHTML = html;
  return tmp.textContent || tmp.innerText || '';
}

function highlightQuery(text: string, query: string): string {
  if (!query.trim()) return text;
  const re = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
  return text.replace(re, '<mark style="background:#fde047;color:#000;padding:0 2px;border-radius:2px;">$1</mark>');
}

function nodeSearchText(meta: NodeMetadata): string {
  const inputTexts = Object.values(meta.input_types || {}).flatMap(section =>
    Object.entries(section || {}).flatMap(([name, spec]) => [
      name,
      spec.type,
      spec.label,
      spec.tooltip,
      spec.description,
      spec.default === undefined ? undefined : String(spec.default),
    ]),
  );
  const values = [
    meta.display_name,
    meta.id,
    meta.description,
    meta.category,
    meta.documentation_url,
    meta.version,
    ...(meta.search_aliases || []),
    ...(meta.requires_external_tools || []),
    ...(meta.return_types || []),
    ...(meta.return_names || []),
    ...inputTexts,
  ];
  return values.filter(Boolean).join(' ');
}

function nodeSearchSnippet(meta: NodeMetadata, query: string): string {
  const q = query.trim().toLowerCase();
  const candidates = [
    meta.description,
    ...(meta.search_aliases || []),
    ...(meta.requires_external_tools || []),
    ...(meta.return_names || []),
    ...(meta.return_types || []),
    ...Object.values(meta.input_types || {}).flatMap(section =>
      Object.entries(section || {}).flatMap(([name, spec]) => [
        name,
        spec.tooltip,
        spec.description,
        spec.label,
        spec.type,
      ]),
    ),
  ].filter(Boolean).map(String);
  const source = candidates.find(value => value.toLowerCase().includes(q)) || candidates[0] || '';
  const idx = source.toLowerCase().indexOf(q);
  return idx >= 0
    ? source.slice(Math.max(0, idx - 40), idx + 120)
    : source.slice(0, 120);
}

function pageTitle(page: (typeof PAGES)[number], t: TFunction): string {
  return t(page.titleKey, { defaultValue: page.fallbackTitle });
}

function wikiContent(page: WikiPage, t: TFunction): string {
  const key = CONTENT_KEYS[page];
  return key ? t(key) : CONTENT[page] || '';
}

export default function HelpWikiPanel({ onClose, selectedNode, objectInfo }: HelpWikiPanelProps) {
  const { t } = useTranslation();
  const [page, setPage] = useState<WikiPage>('getting-started');
  const [query, setQuery] = useState('');
  const [searchedNode, setSearchedNode] = useState<HelpNode | null>(null);
  // Auto-switch to node docs whenever the canvas selection changes — but
  // honour an explicit page click so users can still navigate to wiki pages
  // while a node is selected.
  const [overridePage, setOverridePage] = useState(false);
  const activeNode = searchedNode || selectedNode || null;
  const showNodeHelp = !!activeNode && !query.trim() && !overridePage;
  const nodeHelpHtml = useMemo(() => (activeNode ? renderNodeHelp(activeNode, t) : ''), [activeNode, t]);

  const searchResults = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return [];
    return PAGES.filter(p => {
      const title = pageTitle(p, t);
      const text = wikiContent(p.id, t).toLowerCase();
      return title.toLowerCase().includes(q) || p.fallbackTitle.toLowerCase().includes(q) || text.includes(q);
    }).map(p => {
      const content = wikiContent(p.id, t);
      const plain = stripHtml(content);
      const idx = plain.toLowerCase().indexOf(q);
      const snippet = idx >= 0 ? plain.slice(Math.max(0, idx - 40), idx + 120) : plain.slice(0, 100);
      return { ...p, title: pageTitle(p, t), snippet: snippet + (snippet.length < plain.length ? '…' : '') };
    });
  }, [query, t]);

  // Search across registered node metadata so the help search field doubles
  // as a node lookup — typing a tool name surfaces both the wiki section and
  // any node whose name/description/category matches.
  const nodeSearchResults = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q || !objectInfo) return [];
    const hits: { meta: NodeMetadata; snippet: string }[] = [];
    for (const meta of Object.values(objectInfo)) {
      const haystack = nodeSearchText(meta).toLowerCase();
      if (!haystack.includes(q)) continue;
      hits.push({ meta, snippet: nodeSearchSnippet(meta, q) });
      if (hits.length >= 12) break;
    }
    return hits;
  }, [query, objectInfo]);

  const currentContent = wikiContent(page, t);

  return (
    <div className="rail-panel">
      <div className="rail-panel-header">
        <span>{t('helpWiki.title')}</span>
        <button className="btn btn-icon btn-sm" onClick={onClose} title={t('common.close')} aria-label={t('common.close')}><Icon name="close" size={14} /></button>
      </div>
      <div className="rail-panel-body">
        <div className="wiki-search" style={{ position: 'relative', marginBottom: 8 }}>
          <input
            className="palette-search"
            placeholder={t('helpWiki.searchPlaceholder')}
            value={query}
            onChange={e => setQuery(e.target.value)}
          />
          {query && (
            <button
              className="btn btn-icon btn-sm"
              style={{ position: 'absolute', right: 4, top: '50%', transform: 'translateY(-50%)', background: 'transparent', border: 'none' }}
              onClick={() => setQuery('')}
              title={t('common.clear')}
              aria-label={t('common.clear')}
            >
              <Icon name="close" size={12} />
            </button>
          )}
        </div>

        {query.trim() ? (
          <div className="wiki-search-results">
            {searchResults.length === 0 && nodeSearchResults.length === 0 ? (
              <div style={{ padding: 16, textAlign: 'center', color: 'var(--muted)', fontSize: 13 }}>
                {t('helpWiki.search.noResults', { query })}
              </div>
            ) : (
              <>
                {searchResults.length > 0 && (
                  <div style={{ fontSize: 10, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.04em', margin: '4px 0' }}>{t('helpWiki.search.wikiPages')}</div>
                )}
                {searchResults.map(r => (
                  <div
                    key={r.id}
                    className="wiki-result-item"
                    style={{ padding: '8px 12px', borderRadius: 6, cursor: 'pointer', marginBottom: 4, background: 'var(--surface-2)' }}
                    onClick={() => { setPage(r.id); setQuery(''); }}
                  >
                    <div style={{ fontWeight: 600, fontSize: 13, color: 'var(--text)' }} dangerouslySetInnerHTML={{ __html: highlightQuery(r.title, query) }} />
                    <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2, lineHeight: 1.4 }} dangerouslySetInnerHTML={{ __html: highlightQuery(r.snippet, query) }} />
                  </div>
                ))}
                {nodeSearchResults.length > 0 && (
                  <div style={{ fontSize: 10, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.04em', margin: '8px 0 4px' }}>{t('helpWiki.search.nodes')}</div>
                )}
                {nodeSearchResults.map(hit => (
                  <button
                    type="button"
                    key={`node-${hit.meta.id}`}
                    className="wiki-result-item"
                    style={{ display: 'block', width: '100%', textAlign: 'left', padding: '8px 12px', borderRadius: 6, cursor: 'pointer', marginBottom: 4, background: 'var(--surface-2)', border: 'none' }}
                    onClick={() => {
                      setSearchedNode(nodeFromMeta(hit.meta));
                      setOverridePage(false);
                      setQuery('');
                    }}
                  >
                    <div style={{ fontWeight: 600, fontSize: 13, color: 'var(--text)' }} dangerouslySetInnerHTML={{ __html: highlightQuery(hit.meta.display_name, query) }} />
                    <div style={{ fontSize: 10, color: 'var(--accent, #2dd4bf)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>{hit.meta.category || t('helpWiki.nodeDocs.otherCategory')}</div>
                    {hit.snippet && (
                      <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2, lineHeight: 1.4 }} dangerouslySetInnerHTML={{ __html: highlightQuery(hit.snippet, query) }} />
                    )}
                  </button>
                ))}
              </>
            )}
          </div>
        ) : (
          <>
            {activeNode && (
              <div className="wiki-node-tab-row">
                <button
                  className={`wiki-nav-btn ${showNodeHelp ? 'active' : ''}`}
                  onClick={() => setOverridePage(false)}
                  title={t('helpWiki.nodeTab.showDocsFor', { name: activeNode.title || activeNode.type })}
                >
                  <Icon name="nodes" size={12} /> {activeNode.title || activeNode.type}
                </button>
                <span className="wiki-node-tab-hint">{searchedNode ? t('helpWiki.nodeTab.fromSearch') : t('helpWiki.nodeTab.selectedOnCanvas')}</span>
              </div>
            )}
            <div className="wiki-nav">
              {PAGES.map(p => (
                <button
                  key={p.id}
                  className={`wiki-nav-btn ${page === p.id && !showNodeHelp ? 'active' : ''}`}
                  onClick={() => { setPage(p.id); setOverridePage(true); }}
                >
                  {pageTitle(p, t)}
                </button>
              ))}
            </div>
            <div
              className="wiki-content"
              dangerouslySetInnerHTML={{ __html: showNodeHelp ? nodeHelpHtml : currentContent }}
            />
          </>
        )}
      </div>
    </div>
  );
}
