import { useState, useMemo } from 'react';
import Icon from '../ui/Icon';
import type { NodeMetadata, ObjectInfo } from '../../types';

interface HelpWikiPanelProps {
  onClose: () => void;
  /** Currently selected node — when set, the panel surfaces node-specific docs first. */
  selectedNode?: { id: string; type: string; meta?: NodeMetadata; title?: string } | null;
  /** Optional registry so search can look across node names + descriptions. */
  objectInfo?: ObjectInfo;
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function renderNodeHelp(node: { id: string; type: string; meta?: NodeMetadata; title?: string }): string {
  const meta = node.meta;
  const title = node.title || meta?.display_name || node.type;
  const description = meta?.description?.trim() || '<em>No description provided by the node author.</em>';
  const category = meta?.category || 'Uncategorised';
  const tools = meta?.requires_external_tools || [];
  const required = meta?.input_types?.required || {};
  const optional = meta?.input_types?.optional || {};
  const outputs = meta?.return_types || [];
  const outputNames = meta?.return_names || [];

  const renderInputRow = (name: string, spec: { type?: string; tooltip?: string; default?: unknown }) => `
    <tr>
      <td><code>${escapeHtml(name)}</code></td>
      <td><span class="help-port-type">${escapeHtml(String(spec.type || 'STRING'))}</span></td>
      <td>${spec.tooltip ? escapeHtml(String(spec.tooltip)) : ''}${spec.default !== undefined ? ` <span class="help-port-default">default: ${escapeHtml(String(spec.default))}</span>` : ''}</td>
    </tr>`;

  const inputRows = [
    ...Object.entries(required).map(([name, spec]) => renderInputRow(name, spec as { type?: string; tooltip?: string; default?: unknown })),
    ...Object.entries(optional).map(([name, spec]) => renderInputRow(name, spec as { type?: string; tooltip?: string; default?: unknown })),
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
        ${meta?.experimental ? '<span class="help-meta-pill help-meta-exp">experimental</span>' : ''}
        ${meta?.version ? `<span class="help-meta-pill">v${escapeHtml(meta.version)}</span>` : ''}
      </div>
      <p>${description}</p>
      ${tools.length > 0 ? `<p><strong>Requires:</strong> ${tools.map(t => `<code>${escapeHtml(t)}</code>`).join(', ')}</p>` : ''}
      ${inputRows ? `<h4>Inputs</h4><table class="help-port-table"><thead><tr><th>Name</th><th>Type</th><th>Notes</th></tr></thead><tbody>${inputRows}</tbody></table>` : ''}
      ${outputRows ? `<h4>Outputs</h4><table class="help-port-table"><thead><tr><th>Name</th><th>Type</th></tr></thead><tbody>${outputRows}</tbody></table>` : ''}
      <p class="help-node-hint">Tip: select another node on the canvas to view its docs here.</p>
    </div>
  `;
}

type WikiPage = 'getting-started' | 'nodes-reference' | 'templates-guide' | 'custom-nodes' | 'hpc-integration' | 'workflow-converters' | 'keyboard-shortcuts' | 'canvas-features';

const PAGES: { id: WikiPage; title: string }[] = [
  { id: 'getting-started', title: 'Getting Started' },
  { id: 'canvas-features', title: 'Canvas & Nodes' },
  { id: 'nodes-reference', title: 'Node Reference' },
  { id: 'templates-guide', title: 'Templates Guide' },
  { id: 'custom-nodes', title: 'Custom Nodes' },
  { id: 'hpc-integration', title: 'HPC Integration' },
  { id: 'workflow-converters', title: 'Workflow Converters' },
  { id: 'keyboard-shortcuts', title: 'Keyboard Shortcuts' },
];

const CONTENT: Record<WikiPage, string> = {
  'getting-started': `
<h3>Welcome to BioNodulo v2</h3>
<p>BioNodulo is a visual bioinformatics workflow workbench. Build pipelines by connecting nodes on an infinite canvas.</p>

<h4>Quick Start</h4>
<ol>
<li><strong>Add nodes:</strong> Double-click empty canvas or press <kbd>Ctrl+F</kbd> to open the node palette.</li>
<li><strong>Connect nodes:</strong> Drag from an output slot (right side) to an input slot (left side).</li>
<li><strong>Configure:</strong> Double-click a node to edit its parameters.</li>
<li><strong>Run:</strong> Click the <strong>Run</strong> button in the top bar to execute your workflow.</li>
<li><strong>Note nodes:</strong> Add yellow Note nodes to document your workflow.</li>
</ol>

<h4>Node Categories</h4>
<table>
<tr><th>Category</th><th>Description</th><th>Example Tools</th></tr>
<tr><td>Input</td><td>Load data files</td><td>FASTQ, FASTA, VCF, GFF, Sample Sheet</td></tr>
<tr><td>Quality Control</td><td>Assess data quality</td><td>FastQC, MultiQC</td></tr>
<tr><td>Read Preprocessing</td><td>Trim and filter reads</td><td>fastp, Trimmomatic</td></tr>
<tr><td>Alignment</td><td>Map reads to reference</td><td>BWA, Bowtie2, STAR, HISAT2, Minimap2</td></tr>
<tr><td>SAM/BAM Processing</td><td>Manipulate alignments</td><td>samtools sort, index, flagstat, merge</td></tr>
<tr><td>Variant Calling</td><td>Identify variants</td><td>GATK, bcftools, FreeBayes</td></tr>
<tr><td>Assembly</td><td>Assemble genomes</td><td>SPAdes, MEGAHIT</td></tr>
<tr><td>Annotation</td><td>Annotate genomes</td><td>Prokka</td></tr>
<tr><td>RNA-Seq</td><td>Transcriptomics</td><td>Salmon, Kallisto, featureCounts</td></tr>
<tr><td>Metagenomics</td><td>Microbial communities</td><td>Kraken2, Bracken, MetaPhlAn, HUMAnN</td></tr>
<tr><td>ChIP-Seq</td><td>Peak calling</td><td>MACS2</td></tr>
<tr><td>Single Cell</td><td>10x Genomics</td><td>Cell Ranger</td></tr>
<tr><td>Phylogenetics</td><td>Tree building</td><td>MAFFT, IQ-TREE</td></tr>
<tr><td>Utility</td><td>General tools</td><td>Shell Command, Note, Collect Files</td></tr>
<tr><td>R / Plotting</td><td>Visualization</td><td>R DataFrame, R Plot, R Script</td></tr>
<tr><td>BioPython</td><td>Python bioinformatics</td><td>SeqIO, Translate, BLAST</td></tr>
</table>
`,

  'canvas-features': `
<h3>Canvas Features</h3>
<p>The canvas is an infinite 2D workspace where you build workflows by placing and connecting nodes.</p>

<h4>Navigation</h4>
<table>
<tr><th>Action</th><th>How</th></tr>
<tr><td>Pan</td><td>Middle-click drag or <kbd>Alt</kbd> + left-click drag</td></tr>
<tr><td>Zoom</td><td>Mouse wheel or toolbar buttons</td></tr>
<tr><td>Fit view</td><td>Click the Fit View button or right-click canvas → Fit View</td></tr>
</table>

<h4>Nodes</h4>
<table>
<tr><th>Action</th><th>How</th></tr>
<tr><td>Add node</td><td>Double-click canvas or <kbd>Ctrl+F</kbd></td></tr>
<tr><td>Move node</td><td>Drag the node body</td></tr>
<tr><td>Select multiple</td><td>Shift+click or drag selection box</td></tr>
<tr><td>Collapse</td><td>Click the ▾/▸ arrow on the header or <kbd>Alt+C</kbd></td></tr>
<tr><td>Edit params</td><td>Double-click node or right-click → Edit</td></tr>
<tr><td>Node info</td><td>Right-click → Node Info</td></tr>
<tr><td>Duplicate</td><td>Right-click → Duplicate or <kbd>Ctrl+D</kbd></td></tr>
<tr><td>Delete</td><td><kbd>Delete</kbd> key or right-click → Delete</td></tr>
<tr><td>Mute / Bypass</td><td>Right-click → Mute / Bypass</td></tr>
<tr><td>Change color</td><td>Right-click → Set Color</td></tr>
</table>

<h4>Links & Connections</h4>
<table>
<tr><th>Action</th><th>How</th></tr>
<tr><td>Create link</td><td>Drag from output slot to input slot</td></tr>
<tr><td>Cancel link drag</td><td>Right-click or Esc</td></tr>
<tr><td>Slot hover</td><td>Slots glow teal when hovered</td></tr>
</table>

<h4>Groups</h4>
<p>Organize related nodes into colored bounding boxes:</p>
<ul>
<li><strong>Create group:</strong> Select nodes → right-click canvas → Group Selected or <kbd>Ctrl+G</kbd></li>
<li><strong>Move group:</strong> Drag the group header — all contained nodes move together</li>
<li><strong>Resize group:</strong> Drag the bottom-right handle</li>
<li><strong>Rename / Color:</strong> Right-click on the group</li>
</ul>

<h4>Note Nodes</h4>
<p>Yellow Note nodes let you add text descriptions to your workflow. They have no inputs or outputs and auto-size to fit their text content.</p>

<h4>Undo / Redo</h4>
<p>Use <kbd>Ctrl+Z</kbd> and <kbd>Ctrl+Y</kbd> (or <kbd>Ctrl+Shift+Z</kbd>) to undo and redo actions. The history tracks up to 50 states.</p>
`,

  'nodes-reference': `
<h3>Node Reference</h3>
<p>BioNodulo provides 80+ built-in nodes covering major bioinformatics tools and utilities.</p>

<h4>Node Structure</h4>
<p>Each node has:</p>
<ul>
<li><strong>Inputs:</strong> Required and optional parameters (colored circles on the left)</li>
<li><strong>Outputs:</strong> Generated files or data (colored circles on the right)</li>
<li><strong>Parameters:</strong> Configurable settings visible when you double-click the node</li>
</ul>

<h4>Input / Output Types</h4>
<table>
<tr><th>Type</th><th>Description</th><th>Color</th></tr>
<tr><td>FASTQ / FASTQ_LIST</td><td>Sequencing reads</td><td>Orange</td></tr>
<tr><td>FASTA</td><td>Reference genome or sequences</td><td>Purple</td></tr>
<tr><td>BAM / SAM</td><td>Aligned reads</td><td>Blue</td></tr>
<tr><td>VCF</td><td>Variant calls</td><td>Red</td></tr>
<tr><td>GFF</td><td>Gene annotations</td><td>Green</td></tr>
<tr><td>FILE</td><td>Generic file</td><td>Gray</td></tr>
<tr><td>DIRECTORY</td><td>Folder path</td><td>Gray</td></tr>
<tr><td>STRING</td><td>Text</td><td>Dark gray</td></tr>
<tr><td>INT / FLOAT</td><td>Numbers</td><td>Indigo / Rose</td></tr>
<tr><td>BOOLEAN</td><td>True / False</td><td>Yellow</td></tr>
</table>

<h4>Common Parameters</h4>
<table>
<tr><th>Parameter</th><th>Description</th><th>Default</th></tr>
<tr><td>threads</td><td>Number of CPU threads</td><td>4</td></tr>
<tr><td>memory</td><td>Memory limit</td><td>8G</td></tr>
<tr><td>output</td><td>Output directory</td><td>Auto-generated</td></tr>
</table>
`,

  'templates-guide': `
<h3>Workflow Templates</h3>
<p>Templates are pre-built workflows for common bioinformatics analyses. Load a template as a starting point and customize it.</p>

<h4>Available Templates</h4>
<ul>
<li><strong>FASTQ QC Pipeline:</strong> FastQC → MultiQC quality assessment</li>
<li><strong>RNA-Seq Pipeline:</strong> HISAT2 → samtools sort → featureCounts → QC</li>
<li><strong>Variant Calling:</strong> BWA-MEM → samtools → GATK → bcftools filter</li>
<li><strong>WGS Variant Pipeline:</strong> Complete germline variant discovery</li>
<li><strong>Metagenomics:</strong> Kraken2 → Bracken profiling</li>
<li><strong>Genome Assembly:</strong> SPAdes → Quast evaluation</li>
<li><strong>Phylogenetics:</strong> MAFFT → IQ-TREE tree building</li>
<li><strong>ChIP-Seq:</strong> Bowtie2 → MACS2 peak calling</li>
<li><strong>Single Cell:</strong> Cell Ranger count pipeline</li>
<li><strong>Differential Expression:</strong> DESeq2 / edgeR analysis</li>
</ul>

<h4>Loading Templates</h4>
<p>Click the Templates icon in the left rail to browse available templates. Click a template card to load it onto the canvas. Each template includes a yellow <strong>Note</strong> node at the top describing the pipeline.</p>

<h4>Creating Custom Templates</h4>
<p>Save any workflow as a template by exporting it to JSON and placing it in the <code>templates/</code> directory. Templates must include <code>version</code>, <code>app</code>, <code>name</code>, <code>description</code>, <code>nodes</code>, <code>edges</code>, and <code>groups</code> fields.</p>
`,

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

export default function HelpWikiPanel({ onClose, selectedNode, objectInfo }: HelpWikiPanelProps) {
  const [page, setPage] = useState<WikiPage>('getting-started');
  const [query, setQuery] = useState('');
  // Auto-switch to node docs whenever the canvas selection changes — but
  // honour an explicit page click so users can still navigate to wiki pages
  // while a node is selected.
  const [overridePage, setOverridePage] = useState(false);
  const showNodeHelp = !!selectedNode && !query.trim() && !overridePage;
  const nodeHelpHtml = useMemo(() => (selectedNode ? renderNodeHelp(selectedNode) : ''), [selectedNode]);

  const searchResults = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return [];
    return PAGES.filter(p => {
      const text = (CONTENT[p.id] || '').toLowerCase();
      return p.title.toLowerCase().includes(q) || text.includes(q);
    }).map(p => {
      const content = CONTENT[p.id];
      const plain = stripHtml(content);
      const idx = plain.toLowerCase().indexOf(q);
      const snippet = idx >= 0 ? plain.slice(Math.max(0, idx - 40), idx + 120) : plain.slice(0, 100);
      return { ...p, snippet: snippet + (snippet.length < plain.length ? '…' : '') };
    });
  }, [query]);

  // Search across registered node metadata so the help search field doubles
  // as a node lookup — typing a tool name surfaces both the wiki section and
  // any node whose name/description/category matches.
  const nodeSearchResults = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q || !objectInfo) return [];
    const hits: { meta: NodeMetadata; snippet: string }[] = [];
    for (const meta of Object.values(objectInfo)) {
      const haystack = [meta.display_name, meta.id, meta.description, meta.category].filter(Boolean).join(' ').toLowerCase();
      if (!haystack.includes(q)) continue;
      const source = meta.description || meta.category || '';
      const idx = source.toLowerCase().indexOf(q);
      const snippet = idx >= 0
        ? source.slice(Math.max(0, idx - 40), idx + 120)
        : source.slice(0, 120);
      hits.push({ meta, snippet });
      if (hits.length >= 12) break;
    }
    return hits;
  }, [query, objectInfo]);

  const currentContent = CONTENT[page] || '';

  return (
    <div className="rail-panel">
      <div className="rail-panel-header">
        <span>Help / Wiki</span>
        <button className="btn btn-icon btn-sm" onClick={onClose}><Icon name="close" size={14} /></button>
      </div>
      <div className="rail-panel-body">
        <div className="wiki-search" style={{ position: 'relative', marginBottom: 8 }}>
          <input
            className="palette-search"
            placeholder="Search help..."
            value={query}
            onChange={e => setQuery(e.target.value)}
          />
          {query && (
            <button
              className="btn btn-icon btn-sm"
              style={{ position: 'absolute', right: 4, top: '50%', transform: 'translateY(-50%)', background: 'transparent', border: 'none' }}
              onClick={() => setQuery('')}
            >
              <Icon name="close" size={12} />
            </button>
          )}
        </div>

        {query.trim() ? (
          <div className="wiki-search-results">
            {searchResults.length === 0 && nodeSearchResults.length === 0 ? (
              <div style={{ padding: 16, textAlign: 'center', color: 'var(--muted)', fontSize: 13 }}>
                No results for "{query}"
              </div>
            ) : (
              <>
                {searchResults.length > 0 && (
                  <div style={{ fontSize: 10, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.04em', margin: '4px 0' }}>Wiki pages</div>
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
                  <div style={{ fontSize: 10, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.04em', margin: '8px 0 4px' }}>Nodes</div>
                )}
                {nodeSearchResults.map(hit => (
                  <div
                    key={`node-${hit.meta.id}`}
                    className="wiki-result-item"
                    style={{ padding: '8px 12px', borderRadius: 6, cursor: 'default', marginBottom: 4, background: 'var(--surface-2)' }}
                  >
                    <div style={{ fontWeight: 600, fontSize: 13, color: 'var(--text)' }} dangerouslySetInnerHTML={{ __html: highlightQuery(hit.meta.display_name, query) }} />
                    <div style={{ fontSize: 10, color: 'var(--accent, #2dd4bf)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>{hit.meta.category || 'Other'}</div>
                    {hit.snippet && (
                      <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2, lineHeight: 1.4 }} dangerouslySetInnerHTML={{ __html: highlightQuery(hit.snippet, query) }} />
                    )}
                  </div>
                ))}
              </>
            )}
          </div>
        ) : (
          <>
            {selectedNode && (
              <div className="wiki-node-tab-row">
                <button
                  className={`wiki-nav-btn ${showNodeHelp ? 'active' : ''}`}
                  onClick={() => setOverridePage(false)}
                  title={`Show docs for ${selectedNode.title || selectedNode.type}`}
                >
                  <Icon name="nodes" size={12} /> {selectedNode.title || selectedNode.type}
                </button>
                <span className="wiki-node-tab-hint">selected on canvas</span>
              </div>
            )}
            <div className="wiki-nav">
              {PAGES.map(p => (
                <button
                  key={p.id}
                  className={`wiki-nav-btn ${page === p.id && !showNodeHelp ? 'active' : ''}`}
                  onClick={() => { setPage(p.id); setOverridePage(true); }}
                >
                  {p.title}
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
