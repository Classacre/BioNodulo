/// <reference types="vite/client" />

import type { TemplateInfo, Workflow } from './types';

type TemplateModule = { default: Workflow } | Workflow;

const modules = import.meta.glob<TemplateModule>('../../templates/*.json', { eager: true });

function templateData(module: TemplateModule): Workflow {
  const data = 'default' in module ? module.default : module;
  return JSON.parse(JSON.stringify(data)) as Workflow;
}

function filenameFromPath(path: string): string {
  return path.split('/').pop() || path;
}

function titleFromStem(stem: string): string {
  return stem.replace(/_/g, ' ').replace(/\b\w/g, char => char.toUpperCase());
}

function deriveCategory(name: string, description: string, tools: string[]): string {
  const text = `${name} ${description} ${tools.join(' ')}`.toLowerCase();
  if (text.includes('single cell') || text.includes('cellranger') || text.includes('10x')) return 'Single Cell';
  if (text.includes('rna') || text.includes('deseq') || text.includes('featurecounts') || text.includes('salmon')) return 'RNA-Seq';
  if (text.includes('variant') || text.includes('vcf') || text.includes('gatk') || text.includes('bcftools')) return 'Variant Calling';
  if (text.includes('assembly') || text.includes('spades') || text.includes('megahit')) return 'Assembly';
  if (text.includes('metagenomics') || text.includes('kraken') || text.includes('humann')) return 'Metagenomics';
  if (text.includes('chip') || text.includes('macs')) return 'ChIP-Seq';
  if (text.includes('phylo') || text.includes('tree') || text.includes('mafft')) return 'Phylogenetics';
  if (text.includes('plot') || text.includes('r ')) return 'Visualization';
  if (text.includes('qc') || text.includes('fastqc') || text.includes('multiqc')) return 'Quality Control';
  return 'Other';
}

function deriveTags(name: string, description: string, tools: string[]): string[] {
  const tags = new Set<string>();
  for (const tool of tools.slice(0, 6)) {
    if (tool) tags.add(tool);
  }
  for (const token of `${name} ${description}`.toLowerCase().match(/[a-z0-9]+/g) || []) {
    if (token.length > 3 && tags.size < 8) tags.add(token);
  }
  return Array.from(tags);
}

function derivePreviewSteps(nodes: Workflow['nodes']): string[] {
  return nodes
    .filter(node => node.type !== 'note')
    .slice(0, 5)
    .map(node => node.ui?.title || node.type.replace(/_/g, ' '))
    .filter(Boolean);
}

export function listLocalTemplates(): TemplateInfo[] {
  return Object.entries(modules).map(([path, module]) => {
    const filename = filenameFromPath(path);
    const stem = filename.replace(/\.json$/i, '');
    const workflow = templateData(module);
    const nodes = Array.isArray(workflow.nodes) ? workflow.nodes : [];
    const meta = workflow as Workflow & { category?: string; tags?: string[]; tools?: string[] };
    const tools = (meta.tools || Array.from(new Set(nodes.map(node => node.type).filter(Boolean)))).sort();
    const name = workflow.name || titleFromStem(stem);
    const description = workflow.description || '';
    return {
      id: stem,
      name,
      filename,
      description,
      category: meta.category || deriveCategory(name, description, tools),
      tags: meta.tags || deriveTags(name, description, tools),
      tools,
      preview_steps: derivePreviewSteps(nodes),
      node_count: nodes.filter(node => node.type !== 'note').length,
    };
  }).sort((a, b) => a.name.localeCompare(b.name));
}

export function getLocalTemplateWorkflow(filename: string): Workflow | null {
  const match = Object.entries(modules).find(([path]) => filenameFromPath(path) === filename);
  if (!match) return null;
  return templateData(match[1]);
}
