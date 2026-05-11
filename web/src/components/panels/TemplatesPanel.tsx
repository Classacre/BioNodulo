import { useState } from 'react';
import type { TemplateInfo } from '../../types';


interface TemplatesPanelProps {
  onClose: () => void;
  onLoadTemplate: (template: TemplateInfo) => void;
}

const TEMPLATES: TemplateInfo[] = [
  { id: 'fastq-qc', name: 'FASTQ QC Pipeline', description: 'Quality control pipeline for sequencing reads using FastQC and MultiQC', category: 'QC', tags: ['qc', 'fastq'], tools: ['FastQC', 'MultiQC'], node_count: 3, filename: 'fastq_qc_pipeline.json' },
  { id: 'rna-seq', name: 'RNA-Seq Pipeline', description: 'Complete RNA sequencing analysis from reads to counts', category: 'RNA-Seq', tags: ['rna', 'expression'], tools: ['HISAT2', 'featureCounts', 'MultiQC'], node_count: 5, filename: 'rna_seq_pipeline.json' },
  { id: 'variant-calling', name: 'Variant Calling Pipeline', description: 'GATK-based germline variant calling from FASTQ to VCF', category: 'Variant', tags: ['variant', 'gatk'], tools: ['BWA', 'GATK', 'bcftools'], node_count: 7, filename: 'variant_calling_pipeline.json' },
  { id: 'metagenomics', name: 'Metagenomics Pipeline', description: 'Taxonomic profiling of microbial communities', category: 'Metagenomics', tags: ['meta', 'taxonomy'], tools: ['Kraken2', 'Bracken', 'MetaPhlAn'], node_count: 4, filename: 'metagenomics_pipeline.json' },
  { id: 'assembly', name: 'Genome Assembly', description: 'De novo assembly and quality assessment', category: 'Assembly', tags: ['assembly', 'genome'], tools: ['SPAdes', 'Quast'], node_count: 3, filename: 'assembly_pipeline.json' },
  { id: 'phylogenetics', name: 'Phylogenetics Pipeline', description: 'Multiple sequence alignment and phylogenetic tree construction', category: 'Phylogenetics', tags: ['phylo', 'msa'], tools: ['MAFFT', 'IQ-TREE'], node_count: 3, filename: 'phylogenetics_pipeline.json' },
  { id: 'chip-seq', name: 'ChIP-Seq Pipeline', description: 'Chromatin immunoprecipitation sequencing analysis', category: 'ChIP-Seq', tags: ['chip', 'epigenetics'], tools: ['Bowtie2', 'MACS2'], node_count: 4, filename: 'chip_seq_pipeline.json' },
  { id: 'diff-expression', name: 'Differential Expression', description: 'Differential gene expression analysis pipeline', category: 'RNA-Seq', tags: ['de', 'deseq2'], tools: ['Salmon', 'DESeq2'], node_count: 4, filename: 'differential_expression.json' },
  { id: 'wgs-variant', name: 'WGS Variant Pipeline', description: 'Whole genome sequencing variant calling with BWA and FreeBayes', category: 'Variant', tags: ['wgs', 'variant'], tools: ['BWA', 'FreeBayes', 'bcftools'], node_count: 6, filename: 'wgs_variant_pipeline.json' },
  { id: 'sc-rna', name: 'Single Cell RNA-Seq', description: 'Single cell RNA sequencing with Cell Ranger', category: 'Single Cell', tags: ['sc', '10x'], tools: ['Cell Ranger'], node_count: 3, filename: 'single_cell_pipeline.json' },
];

export default function TemplatesPanel({ onClose, onLoadTemplate }: TemplatesPanelProps) {
  const [filter, setFilter] = useState('');
  const [catFilter, setCatFilter] = useState<string>('All');

  const categories = ['All', ...Array.from(new Set(TEMPLATES.map(t => t.category)))];
  const filtered = TEMPLATES.filter(t => {
    const matchCat = catFilter === 'All' || t.category === catFilter;
    const q = filter.toLowerCase();
    const matchFilter = !q || t.name.toLowerCase().includes(q) || t.tags.some(tag => tag.includes(q)) || t.tools.some(tool => tool.toLowerCase().includes(q));
    return matchCat && matchFilter;
  });

  return (
    <div className="rail-panel">
      <div className="rail-panel-header">
        <span>Templates</span>
        <button className="btn btn-icon btn-sm" onClick={onClose}><Icon name="close" size={14} /></button>
      </div>
      <div className="rail-panel-body">
        <input className="palette-search" placeholder="Search templates..." value={filter} onChange={e => setFilter(e.target.value)} style={{ marginBottom: 8 }} />
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginBottom: 12 }}>
          {categories.map(c => (
            <button key={c} className={`env-type-tab ${catFilter === c ? 'active' : ''}`} onClick={() => setCatFilter(c)} style={{ padding: '3px 10px', fontSize: 11 }}>
              {c}
            </button>
          ))}
        </div>
        <div className="template-grid">
          {filtered.map(t => (
            <div key={t.id} className="template-card" onClick={() => onLoadTemplate(t)}>
              <h4>{t.name}</h4>
              <p>{t.description}</p>
              <div className="tags">
                {t.tools.map(tool => <span key={tool} className="template-tag">{tool}</span>)}
                <span className="template-tag" style={{ background: 'var(--surface-2)', color: 'var(--muted)' }}>{t.node_count} nodes</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

import Icon from '../ui/Icon';
