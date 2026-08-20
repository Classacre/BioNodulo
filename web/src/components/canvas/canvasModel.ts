// Pure (JSX-free, i18n-free) canvas model helpers shared by the React Flow
// WorkflowCanvas and the inspector/editor panels. Holds the node geometry /
// colour / layout logic as a single source of truth.
import type { NodeMetadata, NodeStatus } from '../../types';

export const NODE_WIDTH = 220;
export const NODE_NOTE_WIDTH = 260;

export interface GraphNode {
  id: string;
  type: string;
  display_name: string;
  category: string;
  x: number;
  y: number;
  width: number;
  height: number;
  inputs: { name: string; type: string; connected: boolean }[];
  outputs: { name: string; type: string; connected: boolean }[];
  params: Record<string, unknown>;
  // Param keys promoted from widgets to input ports (see WorkflowNode.ui).
  promotedInputs: string[];
  meta: NodeMetadata | null;
  color: string;
  muted: boolean;
  bypassed: boolean;
  selected: boolean;
  collapsed: boolean;
  pinned: boolean;
  shape: 'round' | 'box' | 'card';
  title: string;
  status?: NodeStatus['status'];
  visualOnly: boolean;
  /** Engine subgraph node (wn.type === 'subgraph'): gets a distinct stacked
   *  card look + a SUBGRAPH chip in the header (see BioNode / index.css). */
  isSubgraph: boolean;
  inlinePreview: boolean;
  previewCollapsed: boolean;
  // Run-reactive: true while this node is showing an inline preview band
  // (a live preview exists for it and the inlinePreviews setting is on).
  showingPreview: boolean;
}

export interface WorkflowCanvasRef {
  fitView: () => void;
  focusNode: (nodeId: string) => void;
  setViewport: (viewport: { x: number; y: number; scale: number }) => void;
  getViewport: () => { x: number; y: number; scale: number };
  getSelectedNodeIds: () => string[];
  executeSelected: () => void;
  /** Project a screen (client) coordinate to flow/world coordinates — native
   *  React Flow projection, used e.g. by file-drop to place a node under the
   *  cursor. */
  screenToFlowPosition: (clientX: number, clientY: number) => { x: number; y: number };
  /** Wrap the current selection in a native group node. */
  createGroupFromSelection: () => void;
  /** Topological auto-layout: lays out all nodes in horizontal columns based
   *  on dependency depth. */
  autoLayout: () => void;
}

const COLORS: Record<string, string> = {
  Input: '#0d9488', 'Quality Control': '#ec4899', 'Read Preprocessing': '#f59e0b',
  Alignment: '#3b82f6', 'SAM/BAM Processing': '#60a5fa', 'Variant Calling': '#ef4444',
  Assembly: '#22c55e', Annotation: '#a855f7', Phylogenetics: '#14b8a6',
  'RNA-Seq': '#f97316', Metagenomics: '#8b5cf6', 'ChIP-Seq': '#06b6d4',
  'Single Cell': '#d946ef', HPC: '#6366f1', Utility: '#64748b',
};

// The Python registry emits lowercase categories like 'trimming', 'samtools',
// 'metagenomics' — these don't match the COLORS keys above, so before falling
// back to slate gray we run a substring search on category + id + display name.
// Order matters: first match wins, so put more specific keywords earlier.
const COLOR_KEYWORD_RULES: Array<[string, string]> = [
  ['input', '#0d9488'],
  ['qc', '#ec4899'],
  ['quality', '#ec4899'],
  ['preprocess', '#f59e0b'],
  ['trim', '#f59e0b'],
  ['cutadapt', '#f59e0b'],
  ['fastp', '#f59e0b'],
  ['samtools', '#60a5fa'],
  ['sam/bam', '#60a5fa'],
  ['align', '#3b82f6'],
  ['hisat', '#3b82f6'],
  ['bowtie', '#3b82f6'],
  ['bwa', '#3b82f6'],
  ['minimap', '#3b82f6'],
  ['star', '#3b82f6'],
  ['variant', '#ef4444'],
  ['gatk', '#ef4444'],
  ['bcftools', '#ef4444'],
  ['freebayes', '#ef4444'],
  ['vcftools', '#ef4444'],
  ['assembly', '#22c55e'],
  ['spades', '#22c55e'],
  ['canu', '#22c55e'],
  ['flye', '#22c55e'],
  ['unicycler', '#22c55e'],
  ['megahit', '#22c55e'],
  ['quast', '#22c55e'],
  ['annotation', '#a855f7'],
  ['prokka', '#a855f7'],
  ['bakta', '#a855f7'],
  ['eggnog', '#a855f7'],
  ['phylo', '#14b8a6'],
  ['mafft', '#14b8a6'],
  ['iqtree', '#14b8a6'],
  ['fasttree', '#14b8a6'],
  ['raxml', '#14b8a6'],
  ['clustalo', '#14b8a6'],
  ['single', '#d946ef'],
  ['cellranger', '#d946ef'],
  ['metag', '#8b5cf6'],
  ['kraken', '#8b5cf6'],
  ['bracken', '#8b5cf6'],
  ['metaphlan', '#8b5cf6'],
  ['humann', '#8b5cf6'],
  ['checkm', '#8b5cf6'],
  ['maxbin', '#8b5cf6'],
  ['quantif', '#a855f7'],
  ['count', '#a855f7'],
  ['featurecounts', '#a855f7'],
  ['kallisto', '#a855f7'],
  ['salmon', '#a855f7'],
  ['stringtie', '#a855f7'],
  ['differential', '#ef4444'],
  ['deseq', '#ef4444'],
  ['expression', '#a855f7'],
  ['peak', '#06b6d4'],
  ['macs', '#06b6d4'],
  ['chip', '#06b6d4'],
  ['deeptools', '#3b82f6'],
  ['bedtools', '#60a5fa'],
  ['hpc', '#6366f1'],
  ['biopython', '#a855f7'],
  ['biostrings', '#a855f7'],
  ['blast', '#a855f7'],
  ['plot', '#ec4899'],
  ['heatmap', '#ec4899'],
  ['viz', '#ec4899'],
  ['note', '#f59e0b'],
];

export function nodeColor(meta: NodeMetadata | null): string {
  if (!meta) return '#64748b';
  const category = meta.category || '';
  if (COLORS[category]) return COLORS[category];
  const haystack = `${category} ${meta.id || ''} ${meta.display_name || ''}`.toLowerCase();
  for (const [keyword, color] of COLOR_KEYWORD_RULES) {
    if (haystack.includes(keyword)) return color;
  }
  return '#64748b';
}
