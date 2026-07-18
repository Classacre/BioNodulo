// Collect local workspace artifacts so Run-on-Cloud can upload them before
// submission. Prefer declared node input types over parameter-name guessing;
// the small input-node fallback preserves legacy template aliases.
import type { NodeMetadata, ObjectInfo, Workflow, WorkflowNode } from '../types';

const DIRECTORY_TYPES = new Set([
  'DIRECTORY', 'INDEX_DIR', 'BWA_MEM2_INDEX', 'BOWTIE2_INDEX',
  'QC_REPORT_DIR', 'CELL_RANGER_OUT', 'HUMANN_OUTPUT', 'BINS',
]);

const FILE_TYPES = new Set([
  'FILE', 'PATH', 'FASTA', 'FASTA_INDEX', 'SEQUENCE_DICTIONARY',
  'FASTQ', 'SAM', 'BAM', 'BAI', 'CRAM', 'CRAI', 'VCF', 'VCF_GZ',
  'BCF', 'VCF_INDEX', 'GFF', 'GTF', 'GFF_GTF', 'BED', 'BEDGRAPH',
  'BIGWIG', 'ASSEMBLY', 'CONTIGS', 'SCAFFOLDS', 'HAL', 'MAF', 'VG',
  'TAR', 'GFA', 'ODGI', 'GBZ', 'COUNTS', 'TPM_MATRIX', 'ABUNDANCE',
  'GENE_EXPRESSION', 'TX_EXPRESSION', 'MULTIQC_REPORT', 'HTML_REPORT',
  'PDF_REPORT', 'STATS_FILE', 'KRAKEN_REPORT', 'KRAKEN_OUTPUT',
  'METAPHLAN_PROFILE', 'ALIGNMENT', 'PHYLOGENY_TREE', 'PEAKS',
  'NARROW_PEAK', 'BROAD_PEAK', 'SAMPLE_SHEET', 'H5AD', 'LOOM',
  'SEURAT_OBJ', 'PAML_RESULTS', 'IMAGE', 'CSV', 'TSV', 'EMBEDDING',
  'TRANSCRIPTS', 'MZML', 'MZXML', 'MGF', 'POD5', 'PDB', 'MMCIF',
]);

const INPUT_SOURCE_KEYS = new Set([
  'path', 'file', 'filepath', 'file_path', 'input', 'input_file',
  'reference', 'reads', 'fastq', 'fasta', 'sam', 'bam', 'vcf',
  'annotation', 'sample_sheet', 'directory', 'dir_path',
]);

function normalizedTypes(value: string | undefined): string[] {
  return String(value || '')
    .trim()
    .toUpperCase()
    .split(/[|,+/]/)
    .map(type => type.trim())
    .filter(Boolean);
}

function isDirectoryType(value: string | undefined): boolean {
  return normalizedTypes(value).some(type => {
    const base = type.endsWith('_LIST') ? type.slice(0, -5) : type;
    return DIRECTORY_TYPES.has(base) || base.endsWith('_DIR');
  });
}

function isFileType(value: string | undefined): boolean {
  return normalizedTypes(value).some(type => {
    const base = type.endsWith('_LIST') ? type.slice(0, -5) : type;
    return FILE_TYPES.has(base) || base.endsWith('_FILE');
  });
}

function localPath(value: unknown, allowBare = false): string | null {
  if (typeof value !== 'string') return null;
  const path = value.trim();
  if (!path || path.length > 4096 || /\r|\n/.test(path)) return null;
  if (/\{\{\s*[A-Za-z_][A-Za-z0-9_.-]*\s*\}\}/.test(path)) return null;
  if (/^[a-z][a-z0-9+.-]*:\/\//i.test(path)) return null;
  if (/^uploads\//i.test(path)) return null;
  if (!allowBare && !/[./\\]/.test(path)) return null;
  return path;
}

function collectPathValues(value: unknown, out: Set<string>, allowBare = false): void {
  const path = localPath(value, allowBare);
  if (path) {
    out.add(path);
    return;
  }
  if (Array.isArray(value)) {
    for (const item of value) collectPathValues(item, out, allowBare);
  }
}

function hasLocalValue(value: unknown): boolean {
  if (localPath(value, true)) return true;
  return Array.isArray(value) && value.some(hasLocalValue);
}

function metadataForNode(node: WorkflowNode, objectInfo: ObjectInfo): NodeMetadata | undefined {
  return node.node_info?.input_types ? node.node_info : (objectInfo[node.type] ?? node.node_info);
}

function inputTypes(meta: NodeMetadata | undefined): { types: Map<string, string>; hidden: Set<string> } {
  const types = new Map<string, string>();
  const hidden = new Set<string>(Object.keys(meta?.input_types?.hidden ?? {}));
  for (const section of ['required', 'optional'] as const) {
    for (const [name, spec] of Object.entries(meta?.input_types?.[section] ?? {})) {
      types.set(name, String(spec.type || 'STRING'));
    }
  }
  return { types, hidden };
}

function isInputNode(node: WorkflowNode, meta: NodeMetadata | undefined): boolean {
  return node.type.startsWith('input_') || String(meta?.category || '').toLowerCase() === 'input';
}

/** Distinct local file paths referenced by node inputs or typed run parameters. */
export function collectLocalFilePaths(
  workflow: Workflow,
  runtimeParameters: Record<string, unknown> = {},
  objectInfo: ObjectInfo = {},
): string[] {
  const out = new Set<string>();
  for (const node of workflow.nodes || []) {
    const meta = metadataForNode(node, objectInfo);
    const { types: declaredTypes, hidden } = inputTypes(meta);
    const canonicalInputNode = isInputNode(node, meta);
    for (const [key, value] of Object.entries(node.params || {})) {
      const type = declaredTypes.get(key);
      const directory = isDirectoryType(type)
        || (canonicalInputNode && (key === 'directory' || key === 'dir_path'));
      if (directory) {
        if (hasLocalValue(value)) {
          throw new Error(
            `Cloud file staging does not support directory input '${key}' on node '${node.id}'.`,
          );
        }
        continue;
      }
      if (!isFileType(type) && !(canonicalInputNode && INPUT_SOURCE_KEYS.has(key) && !hidden.has(key))) continue;
      // Input-node source values and declared artifact ports are paths even when
      // an extension is absent; URLs and existing cloud keys remain untouched.
      collectPathValues(value, out, true);
    }
  }

  const definitions = new Map(
    (workflow.parameters || []).map(parameter => [
      parameter.name,
      String(parameter.type || '').trim().toUpperCase(),
    ]),
  );
  for (const [name, value] of Object.entries(runtimeParameters)) {
    const type = definitions.get(name);
    if (!type) continue;
    if (isDirectoryType(type)) {
      if (hasLocalValue(value)) {
        throw new Error(`Cloud file staging does not support directory workflow parameter '${name}'.`);
      }
      continue;
    }
    if (isFileType(type)) collectPathValues(value, out, true);
  }
  return [...out];
}

/** Basename for a workspace path (handles both `/` and `\`). */
export function baseName(path: string): string {
  return path.split(/[\\/]/).pop() || path;
}
