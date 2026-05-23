import { useState, useCallback, useEffect, useRef, useMemo } from 'react';
import TopBar from './components/layout/TopBar';
import LeftRail, { type RailTab } from './components/layout/LeftRail';
import WorkflowTabs from './components/layout/WorkflowTabs';
import BottomConsole from './components/layout/BottomConsole';
import ErrorBoundary from './components/layout/ErrorBoundary';
import LiteGraphCanvas, { type LiteGraphCanvasRef } from './components/canvas/LiteGraphCanvas';
import HardwareMonitor from './components/canvas/HardwareMonitor';
import SettingsPanel from './components/panels/SettingsPanel';
import HelpWikiPanel from './components/panels/HelpWikiPanel';
import TemplatesPanel from './components/panels/TemplatesPanel';
import EnvironmentPanel from './components/panels/EnvironmentPanel';
import HPCPanel from './components/panels/HPCPanel';
import NodeLibraryPanel from './components/panels/NodeLibraryPanel';
import WorkspacePanel from './components/panels/WorkspacePanel';
import ExportModal from './components/modals/ExportModal';
import ImportModal from './components/modals/ImportModal';
import AIWorkflowModal from './components/modals/AIWorkflowModal';
import ImageLightbox from './components/modals/ImageLightbox';
import GettingStartedModal from './components/modals/GettingStartedModal';
import MissingDependenciesBanner from './components/layout/MissingDependenciesBanner';
import HostPrerequisitesBanner from './components/layout/HostPrerequisitesBanner';
import { useSettings } from './hooks/useSettings';
import { useWorkflow } from './hooks/useWorkflow';
import { useTheme } from './hooks/useTheme';
import { useWebSocket } from './hooks/useWebSocket';
import {
  LiteGraphYjsBridge, useCollab, workflowToDoc, docToWorkflow,
  ForeignCursors, CollabBadge, ShareDialog,
  getUserColor, getAuthUser, getToken, initAuth, AuthDialog,
  CommentsPanel, VersionHistory, AuditLog,
} from './collab';
import { defaultsFor } from './utils';
import { getLocalTemplateWorkflow } from './localTemplates';
import type { Workflow, WorkflowNode, NodeMetadata, HPCConfig, TemplateInfo, LogEntry, ResolveReport, HostStatus, RunRecord, NodeStatus } from './types';
import type { Comment, LivePresenceUser } from './collab';
import type { HPCStatus } from './components/layout/TopBar';

// Built-in node definitions for offline use
const BUILTIN_NODES: Record<string, NodeMetadata> = {
  'input_fastq': { id: 'input_fastq', display_name: 'Input FASTQ', category: 'Input', description: 'Load FASTQ sequencing reads', return_types: ['FASTQ_LIST'], return_names: ['reads'], input_types: { required: { sample_name: { type: 'STRING', default: 'sample1', label: 'Sample Name' }, paired_end: { type: 'BOOLEAN', default: true, label: 'Paired End' } } } },
  'input_fasta': { id: 'input_fasta', display_name: 'Input FASTA', category: 'Input', description: 'Load reference FASTA sequence', return_types: ['FASTA'], return_names: ['reference'], input_types: { required: { file_path: { type: 'STRING', default: '', label: 'File Path' } } } },
  'input_file': { id: 'input_file', display_name: 'Input File', category: 'Input', description: 'Load any file', return_types: ['FILE'], return_names: ['file'], input_types: { required: { file_path: { type: 'STRING', default: '', label: 'File Path' } } } },
  'input_directory': { id: 'input_directory', display_name: 'Input Directory', category: 'Input', description: 'Specify a directory', return_types: ['DIRECTORY'], return_names: ['directory'], input_types: { required: { path: { type: 'STRING', default: '', label: 'Directory Path' } } } },
  'input_vcf': { id: 'input_vcf', display_name: 'Input VCF', category: 'Input', description: 'Load VCF variant file', return_types: ['VCF'], return_names: ['variants'], input_types: { required: { file_path: { type: 'STRING', default: '', label: 'File Path' } } } },
  'input_gff': { id: 'input_gff', display_name: 'Input GFF', category: 'Input', description: 'Load GFF annotation', return_types: ['GFF'], return_names: ['annotations'], input_types: { required: { file_path: { type: 'STRING', default: '', label: 'File Path' } } } },
  'sample_sheet': { id: 'sample_sheet', display_name: 'Sample Sheet', category: 'Input', description: 'Define sample metadata', return_types: ['SAMPLE_SHEET'], return_names: ['samples'], input_types: { required: { csv_path: { type: 'STRING', default: 'samples.csv', label: 'CSV Path' } } } },
  'fastqc': { id: 'fastqc', display_name: 'FastQC', category: 'Quality Control', description: 'Quality control analysis for FASTQ files', search_aliases: ['qc', 'quality'], return_types: ['QC_REPORT_DIR'], return_names: ['report_dir'], input_types: { required: { reads: { type: 'FASTQ_LIST', label: 'Reads' } }, optional: { threads: { type: 'INT', default: 4, min: 1, max: 64, display: 'slider', label: 'Threads' } } }, requires_external_tools: ['fastqc'] },
  'multiqc': { id: 'multiqc', display_name: 'MultiQC', category: 'Quality Control', description: 'Aggregate QC reports into a single report', search_aliases: ['qc', 'summary'], return_types: ['MULTIQC_REPORT'], return_names: ['report'], input_types: { required: { reports: { type: 'QC_REPORT_DIR', label: 'QC Reports' } }, optional: { title: { type: 'STRING', default: 'QC Report', label: 'Report Title' } } }, requires_external_tools: ['multiqc'] },
  'fastp': { id: 'fastp', display_name: 'fastp', category: 'Read Preprocessing', description: 'FASTQ preprocessing and quality trimming', search_aliases: ['trim', 'adapter'], return_types: ['FASTQ_LIST'], return_names: ['trimmed_reads'], input_types: { required: { reads: { type: 'FASTQ_LIST', label: 'Reads' } }, optional: { threads: { type: 'INT', default: 4, min: 1, max: 64, display: 'slider', label: 'Threads' }, adapter_sequence: { type: 'STRING', default: 'auto', label: 'Adapter' } } }, requires_external_tools: ['fastp'] },
  'trimmomatic': { id: 'trimmomatic', display_name: 'Trimmomatic', category: 'Read Preprocessing', description: 'Flexible read trimming tool', return_types: ['FASTQ_LIST'], return_names: ['trimmed_reads'], input_types: { required: { reads: { type: 'FASTQ_LIST', label: 'Reads' } }, optional: { threads: { type: 'INT', default: 4, min: 1, max: 64, display: 'slider', label: 'Threads' }, illuminaclip: { type: 'STRING', default: 'TruSeq3-PE.fa:2:30:10', label: 'IlluminaClip' } } }, requires_external_tools: ['trimmomatic'] },
  'bwa_mem': { id: 'bwa_mem', display_name: 'BWA-MEM', category: 'Alignment', description: 'Align reads to reference with BWA-MEM', search_aliases: ['align', 'map'], return_types: ['SAM'], return_names: ['alignment'], input_types: { required: { reads: { type: 'FASTQ_LIST', label: 'Reads' }, reference: { type: 'FASTA', label: 'Reference' } }, optional: { threads: { type: 'INT', default: 8, min: 1, max: 64, display: 'slider', label: 'Threads' }, mark_shorter_splits: { type: 'BOOLEAN', default: true, label: 'Mark Shorter Splits' } } }, requires_external_tools: ['bwa'] },
  'bwa_index': { id: 'bwa_index', display_name: 'BWA Index', category: 'Alignment', description: 'Build BWA index for reference genome', return_types: ['INDEX_DIR'], return_names: ['index'], input_types: { required: { reference: { type: 'FASTA', label: 'Reference FASTA' } } }, requires_external_tools: ['bwa'] },
  'bowtie2_align': { id: 'bowtie2_align', display_name: 'Bowtie2', category: 'Alignment', description: 'Align reads with Bowtie2', return_types: ['SAM'], return_names: ['alignment'], input_types: { required: { reads: { type: 'FASTQ_LIST', label: 'Reads' }, index: { type: 'INDEX_DIR', label: 'Index' } }, optional: { threads: { type: 'INT', default: 8, min: 1, max: 64, display: 'slider', label: 'Threads' } } }, requires_external_tools: ['bowtie2'] },
  'bowtie2_build': { id: 'bowtie2_build', display_name: 'Bowtie2 Build', category: 'Alignment', description: 'Build Bowtie2 index', return_types: ['INDEX_DIR'], return_names: ['index'], input_types: { required: { reference: { type: 'FASTA', label: 'Reference' } } }, requires_external_tools: ['bowtie2-build'] },
  'minimap2_align': { id: 'minimap2_align', display_name: 'Minimap2', category: 'Alignment', description: 'Long-read and accurate short-read alignment', return_types: ['SAM'], return_names: ['alignment'], input_types: { required: { reads: { type: 'FASTQ_LIST', label: 'Reads' }, reference: { type: 'FASTA', label: 'Reference' } }, optional: { preset: { type: 'STRING', default: 'sr', options: ['sr', 'map-pb', 'map-ont', 'map-hifi', 'ava-pb', 'ava-ont'], label: 'Preset' }, threads: { type: 'INT', default: 8, min: 1, max: 64, display: 'slider', label: 'Threads' } } }, requires_external_tools: ['minimap2'] },
  'star_align': { id: 'star_align', display_name: 'STAR', category: 'Alignment', description: 'Spliced alignment for RNA-Seq', return_types: ['BAM'], return_names: ['alignment'], input_types: { required: { reads: { type: 'FASTQ_LIST', label: 'Reads' }, genome_dir: { type: 'INDEX_DIR', label: 'Genome Dir' } }, optional: { threads: { type: 'INT', default: 8, min: 1, max: 64, display: 'slider', label: 'Threads' } } }, requires_external_tools: ['STAR'] },
  'hisat2_align': { id: 'hisat2_align', display_name: 'HISAT2', category: 'Alignment', description: 'Hierarchical indexing for spliced alignment', return_types: ['SAM'], return_names: ['alignment'], input_types: { required: { reads: { type: 'FASTQ_LIST', label: 'Reads' }, index: { type: 'INDEX_DIR', label: 'Index' } }, optional: { threads: { type: 'INT', default: 8, min: 1, max: 64, display: 'slider', label: 'Threads' } } }, requires_external_tools: ['hisat2'] },
  'samtools_sort': { id: 'samtools_sort', display_name: 'samtools sort', category: 'SAM/BAM Processing', description: 'Sort SAM/BAM by coordinate', return_types: ['BAM'], return_names: ['sorted_bam'], input_types: { required: { input: { type: 'SAM', label: 'Input SAM/BAM' } }, optional: { threads: { type: 'INT', default: 4, min: 1, max: 64, display: 'slider', label: 'Threads' } } }, requires_external_tools: ['samtools'] },
  'samtools_index': { id: 'samtools_index', display_name: 'samtools index', category: 'SAM/BAM Processing', description: 'Index BAM file', return_types: ['BAM'], return_names: ['indexed_bam'], input_types: { required: { bam: { type: 'BAM', label: 'BAM File' } } }, requires_external_tools: ['samtools'] },
  'samtools_flagstat': { id: 'samtools_flagstat', display_name: 'samtools flagstat', category: 'SAM/BAM Processing', description: 'Statistics for BAM file', return_types: ['FILE'], return_names: ['stats'], input_types: { required: { bam: { type: 'BAM', label: 'BAM File' } } }, requires_external_tools: ['samtools'] },
  'samtools_view': { id: 'samtools_view', display_name: 'samtools view', category: 'SAM/BAM Processing', description: 'Convert/filter SAM/BAM', return_types: ['BAM'], return_names: ['bam'], input_types: { required: { sam: { type: 'SAM', label: 'SAM File' } }, optional: { flags: { type: 'STRING', default: '-b', label: 'Flags' } } }, requires_external_tools: ['samtools'] },
  'samtools_merge': { id: 'samtools_merge', display_name: 'samtools merge', category: 'SAM/BAM Processing', description: 'Merge multiple BAM files', return_types: ['BAM'], return_names: ['merged_bam'], input_types: { required: { inputs: { type: 'BAM', label: 'Input BAMs' } }, optional: { threads: { type: 'INT', default: 4, min: 1, max: 64, display: 'slider', label: 'Threads' } } }, requires_external_tools: ['samtools'] },
  'gatk_haplotypecaller': { id: 'gatk_haplotypecaller', display_name: 'GATK HaplotypeCaller', category: 'Variant Calling', description: 'Call germline SNPs and indels', search_aliases: ['variant', 'snp', 'indel', 'vcf'], return_types: ['VCF'], return_names: ['variants'], input_types: { required: { bam: { type: 'BAM', label: 'BAM File' }, reference: { type: 'FASTA', label: 'Reference' } }, optional: { emit_conf: { type: 'INT', default: 30, min: 0, max: 100, display: 'slider', label: 'Emit Conf' }, call_conf: { type: 'INT', default: 30, min: 0, max: 100, display: 'slider', label: 'Call Conf' } } }, requires_external_tools: ['gatk'] },
  'gatk_bqsr': { id: 'gatk_bqsr', display_name: 'GATK BaseRecalibrator', category: 'Variant Calling', description: 'Recalibrate base quality scores', return_types: ['BAM'], return_names: ['recalibrated_bam'], input_types: { required: { bam: { type: 'BAM', label: 'BAM' }, reference: { type: 'FASTA', label: 'Reference' }, known_sites: { type: 'VCF', label: 'Known Sites' } } }, requires_external_tools: ['gatk'] },
  'bcftools_mpileup': { id: 'bcftools_mpileup', display_name: 'bcftools mpileup+call', category: 'Variant Calling', description: 'Variant calling with bcftools', return_types: ['VCF'], return_names: ['variants'], input_types: { required: { bam: { type: 'BAM', label: 'BAM File' }, reference: { type: 'FASTA', label: 'Reference' } }, optional: { ploidy: { type: 'INT', default: 2, min: 1, max: 8, display: 'slider', label: 'Ploidy' } } }, requires_external_tools: ['bcftools'] },
  'bcftools_filter': { id: 'bcftools_filter', display_name: 'bcftools filter', category: 'Variant Calling', description: 'Filter VCF variants', return_types: ['VCF'], return_names: ['filtered'], input_types: { required: { vcf: { type: 'VCF', label: 'VCF' } }, optional: { expr: { type: 'STRING', default: 'QUAL>30 && DP>10', label: 'Filter Expression' } } }, requires_external_tools: ['bcftools'] },
  'freebayes': { id: 'freebayes', display_name: 'FreeBayes', category: 'Variant Calling', description: 'Haplotype-based variant detector', return_types: ['VCF'], return_names: ['variants'], input_types: { required: { bam: { type: 'BAM', label: 'BAM' }, reference: { type: 'FASTA', label: 'Reference' } }, optional: { ploidy: { type: 'INT', default: 2, min: 1, max: 8, display: 'slider', label: 'Ploidy' } } }, requires_external_tools: ['freebayes'] },
  'spades': { id: 'spades', display_name: 'SPAdes', category: 'Assembly', description: 'Genome assembler for small genomes', return_types: ['ASSEMBLY'], return_names: ['assembly'], input_types: { required: { reads: { type: 'FASTQ_LIST', label: 'Reads' } }, optional: { threads: { type: 'INT', default: 8, min: 1, max: 64, display: 'slider', label: 'Threads' }, mode: { type: 'STRING', default: '--isolate', options: ['--isolate', '--sc', '--meta', '--rna', '--plasmid'], label: 'Mode' } } }, requires_external_tools: ['spades.py'] },
  'megahit': { id: 'megahit', display_name: 'MEGAHIT', category: 'Assembly', description: 'Ultra-fast metagenomic assembler', return_types: ['ASSEMBLY'], return_names: ['assembly'], input_types: { required: { reads: { type: 'FASTQ_LIST', label: 'Reads' } }, optional: { threads: { type: 'INT', default: 8, min: 1, max: 64, display: 'slider', label: 'Threads' }, min_count: { type: 'INT', default: 2, min: 1, max: 10, display: 'slider', label: 'Min Count' } } }, requires_external_tools: ['megahit'] },
  'quast': { id: 'quast', display_name: 'Quast', category: 'Assembly', description: 'Quality assessment for assemblies', return_types: ['HTML_REPORT'], return_names: ['report'], input_types: { required: { assembly: { type: 'ASSEMBLY', label: 'Assembly' } }, optional: { reference: { type: 'FASTA', label: 'Reference (optional)' }, threads: { type: 'INT', default: 4, min: 1, max: 64, display: 'slider', label: 'Threads' } } }, requires_external_tools: ['quast.py'] },
  'prokka': { id: 'prokka', display_name: 'Prokka', category: 'Annotation', description: 'Rapid prokaryotic genome annotation', return_types: ['DIRECTORY'], return_names: ['annotation'], input_types: { required: { assembly: { type: 'ASSEMBLY', label: 'Assembly' } }, optional: { kingdom: { type: 'STRING', default: 'Bacteria', options: ['Bacteria', 'Archaea', 'Mitochondria', 'Viruses'], label: 'Kingdom' } } }, requires_external_tools: ['prokka'] },
  'mafft': { id: 'mafft', display_name: 'MAFFT', category: 'Phylogenetics', description: 'Multiple sequence alignment', return_types: ['FILE'], return_names: ['alignment'], input_types: { required: { sequences: { type: 'FASTA', label: 'Sequences' } }, optional: { threads: { type: 'INT', default: 4, min: 1, max: 64, display: 'slider', label: 'Threads' }, strategy: { type: 'STRING', default: 'auto', options: ['auto', 'FFT-NS-1', 'FFT-NS-2', 'G-INS-i', 'L-INS-i', 'E-INS-i'], label: 'Strategy' } } }, requires_external_tools: ['mafft'] },
  'iqtree': { id: 'iqtree', display_name: 'IQ-TREE', category: 'Phylogenetics', description: 'Efficient phylogenomic inference', return_types: ['FILE'], return_names: ['tree'], input_types: { required: { alignment: { type: 'FILE', label: 'Alignment' } }, optional: { threads: { type: 'INT', default: 4, min: 1, max: 64, display: 'slider', label: 'Threads' }, model: { type: 'STRING', default: 'MFP', label: 'Model' }, bootstrap: { type: 'INT', default: 1000, min: 0, max: 10000, step: 100, display: 'slider', label: 'UFBoot Reps' } } }, requires_external_tools: ['iqtree'] },
  'salmon_index': { id: 'salmon_index', display_name: 'Salmon Index', category: 'RNA-Seq', description: 'Build Salmon transcriptome index', return_types: ['INDEX_DIR'], return_names: ['index'], input_types: { required: { transcripts: { type: 'FASTA', label: 'Transcripts' } } }, requires_external_tools: ['salmon'] },
  'salmon_quant': { id: 'salmon_quant', display_name: 'Salmon Quant', category: 'RNA-Seq', description: 'Transcript-level quantification', return_types: ['DIRECTORY'], return_names: ['quant'], input_types: { required: { reads: { type: 'FASTQ_LIST', label: 'Reads' }, index: { type: 'INDEX_DIR', label: 'Index' } }, optional: { threads: { type: 'INT', default: 8, min: 1, max: 64, display: 'slider', label: 'Threads' } } }, requires_external_tools: ['salmon'] },
  'kallisto_quant': { id: 'kallisto_quant', display_name: 'Kallisto Quant', category: 'RNA-Seq', description: 'Pseudoalignment quantification', return_types: ['DIRECTORY'], return_names: ['quant'], input_types: { required: { reads: { type: 'FASTQ_LIST', label: 'Reads' }, index: { type: 'INDEX_DIR', label: 'Index' } }, optional: { threads: { type: 'INT', default: 8, min: 1, max: 64, display: 'slider', label: 'Threads' }, bootstrap: { type: 'INT', default: 100, min: 0, max: 1000, step: 10, display: 'slider', label: 'Bootstrap' } } }, requires_external_tools: ['kallisto'] },
  'featurecounts': { id: 'featurecounts', display_name: 'featureCounts', category: 'RNA-Seq', description: 'Count reads in genomic features', return_types: ['FILE'], return_names: ['counts'], input_types: { required: { bam: { type: 'BAM', label: 'BAM File' }, annotation: { type: 'GFF', label: 'Annotation' } }, optional: { feature_type: { type: 'STRING', default: 'gene', label: 'Feature Type' }, attribute: { type: 'STRING', default: 'gene_id', label: 'Attribute' } } }, requires_external_tools: ['featureCounts'] },
  'kraken2': { id: 'kraken2', display_name: 'Kraken2', category: 'Metagenomics', description: 'Taxonomic classification with k-mers', return_types: ['FILE'], return_names: ['report'], input_types: { required: { reads: { type: 'FASTQ_LIST', label: 'Reads' }, db: { type: 'DIRECTORY', label: 'Database' } }, optional: { threads: { type: 'INT', default: 8, min: 1, max: 64, display: 'slider', label: 'Threads' } } }, requires_external_tools: ['kraken2'] },
  'bracken': { id: 'bracken', display_name: 'Bracken', category: 'Metagenomics', description: 'Abundance estimation from Kraken2', return_types: ['FILE'], return_names: ['abundance'], input_types: { required: { report: { type: 'FILE', label: 'Kraken Report' }, db: { type: 'DIRECTORY', label: 'Database' } }, optional: { level: { type: 'STRING', default: 'S', options: ['D', 'P', 'C', 'O', 'F', 'G', 'S'], label: 'Taxonomic Level' } } }, requires_external_tools: ['bracken'] },
  'metaphlan': { id: 'metaphlan', display_name: 'MetaPhlAn', category: 'Metagenomics', description: 'Metagenomic phylogenetic analysis', return_types: ['FILE'], return_names: ['profile'], input_types: { required: { reads: { type: 'FASTQ_LIST', label: 'Reads' } }, optional: { threads: { type: 'INT', default: 8, min: 1, max: 64, display: 'slider', label: 'Threads' } } }, requires_external_tools: ['metaphlan'] },
  'humann': { id: 'humann', display_name: 'HUMAnN', category: 'Metagenomics', description: 'Functional profiling of metagenomes', return_types: ['DIRECTORY'], return_names: ['pathways'], input_types: { required: { reads: { type: 'FASTQ_LIST', label: 'Reads' } }, optional: { threads: { type: 'INT', default: 8, min: 1, max: 64, display: 'slider', label: 'Threads' } } }, requires_external_tools: ['humann'] },
  'macs2_callpeak': { id: 'macs2_callpeak', display_name: 'MACS2 CallPeak', category: 'ChIP-Seq', description: 'Model-based Analysis of ChIP-Seq', return_types: ['DIRECTORY'], return_names: ['peaks'], input_types: { required: { treatment: { type: 'BAM', label: 'Treatment BAM' } }, optional: { control: { type: 'BAM', label: 'Control BAM' }, format: { type: 'STRING', default: 'AUTO', options: ['AUTO', 'BAM', 'BED'], label: 'Format' } } }, requires_external_tools: ['macs2'] },
  'cellranger_count': { id: 'cellranger_count', display_name: 'Cell Ranger Count', category: 'Single Cell', description: '10x Genomics single cell analysis', return_types: ['DIRECTORY'], return_names: ['counts'], input_types: { required: { fastq_dir: { type: 'DIRECTORY', label: 'FASTQ Directory' }, transcriptome: { type: 'DIRECTORY', label: 'Transcriptome' }, sample: { type: 'STRING', default: '', label: 'Sample' } }, optional: { expect_cells: { type: 'INT', default: 3000, min: 100, max: 50000, step: 100, display: 'slider', label: 'Expected Cells' } } }, requires_external_tools: ['cellranger'] },
  'generic_command': { id: 'generic_command', display_name: 'Generic Command', category: 'Utility', description: 'Run any shell command', return_types: ['FILE'], return_names: ['output'], input_types: { required: { command: { type: 'STRING', default: 'echo "Hello"', label: 'Command' } }, optional: { output_name: { type: 'STRING', default: 'output.txt', label: 'Output Name' } } } },
  'note': { id: 'note', display_name: 'Note', category: 'Utility', description: 'Add a text note or description to the workflow', visual_only: true, search_aliases: ['note', 'text', 'comment', 'description'], input_types: { required: { text: { type: 'STRING', default: '', multiline: true, label: 'Text' } } } },
  'reroute': { id: 'reroute', display_name: 'Reroute', category: 'Utility', description: 'Pass a connection through a routing point', search_aliases: ['reroute', 'pass', 'junction', 'connection'], input_types: { required: { input: { type: 'STRING', label: 'Input' } } }, return_types: ['STRING'], return_names: ['output'] },
  'view_text': { id: 'view_text', display_name: 'View Text', category: 'Utility', description: 'View text file contents', output_node: true, return_types: ['STRING'], return_names: ['text'], input_types: { required: { file: { type: 'FILE', label: 'File' } } } },
  'image_preview': { id: 'image_preview', display_name: 'Image Preview', category: 'Utility', description: 'Preview an image file in the canvas', output_node: true, return_types: [], return_names: [], input_types: { required: { file: { type: 'FILE', label: 'Image File' } } } },
  'collect_files': { id: 'collect_files', display_name: 'Collect Files', category: 'Utility', description: 'Collect multiple files into a list', return_types: ['FILE'], return_names: ['files'], input_types: { required: { directory: { type: 'DIRECTORY', label: 'Directory' } }, optional: { pattern: { type: 'STRING', default: '*', label: 'Pattern' } } } },
  'merge_vcf': { id: 'merge_vcf', display_name: 'Merge VCF', category: 'Utility', description: 'Merge multiple VCF files', return_types: ['VCF'], return_names: ['merged'], input_types: { required: { vcfs: { type: 'VCF', label: 'VCF Files' } } }, requires_external_tools: ['bcftools'] },
  'hpc_submit': { id: 'hpc_submit', display_name: 'HPC Submit', category: 'HPC', description: 'Submit job to HPC cluster', return_types: ['FILE'], return_names: ['job_status'], input_types: { required: { workflow_json: { type: 'STRING', label: 'Workflow JSON' } }, optional: { partition: { type: 'STRING', default: '', label: 'Partition' }, walltime: { type: 'STRING', default: '01:00:00', label: 'Walltime' } } } },
  // R nodes
  'r_dataframe_builder': { id: 'r_dataframe_builder', display_name: 'R DataFrame Builder', category: 'R / Plotting', description: 'Build a CSV data frame for R plotting', return_types: ['FILE'], return_names: ['csv'], input_types: { required: { x_column: { type: 'STRING', default: 'x', label: 'X Column Name' }, x_values: { type: 'STRING', default: '1,2,3,4,5', multiline: true, label: 'X Values' }, y_column: { type: 'STRING', default: 'y', label: 'Y Column Name' }, y_values: { type: 'STRING', default: '2,4,6,8,10', multiline: true, label: 'Y Values' } }, optional: { group_column: { type: 'STRING', default: '', label: 'Group Column', advanced: true }, group_values: { type: 'STRING', default: '', multiline: true, label: 'Group Values', advanced: true } } } },
  'r_plot': { id: 'r_plot', display_name: 'R Plot', category: 'R / Plotting', description: 'Generate plots in R with live preview', output_node: true, return_types: ['FILE'], return_names: ['plot_png'], requires_external_tools: ['Rscript'], input_types: { required: { data_csv: { type: 'FILE', label: 'Data CSV' }, plot_type: { type: 'STRING', default: 'scatter', options: ['scatter', 'line', 'bar', 'histogram', 'boxplot', 'density', 'heatmap', 'custom'], label: 'Plot Type' }, x_axis: { type: 'STRING', default: 'x', label: 'X Axis Column' }, y_axis: { type: 'STRING', default: 'y', label: 'Y Axis Column' } }, optional: { color_column: { type: 'STRING', default: '', label: 'Color Column', advanced: true }, title: { type: 'STRING', default: '', label: 'Plot Title', advanced: true }, width: { type: 'INT', default: 800, min: 200, max: 4000, step: 50, display: 'slider', label: 'Width', advanced: true }, height: { type: 'INT', default: 600, min: 200, max: 4000, step: 50, display: 'slider', label: 'Height', advanced: true }, custom_script: { type: 'STRING', default: '', multiline: true, label: 'Custom R Script', advanced: true } } } },
  'r_script': { id: 'r_script', display_name: 'R Script', category: 'R / Plotting', description: 'Execute an arbitrary R script', return_types: ['FILE'], return_names: ['output_dir'], requires_external_tools: ['Rscript'], input_types: { required: { script: { type: 'FILE', label: 'R Script File' } }, optional: { args: { type: 'STRING', default: '', label: 'Arguments', advanced: true } } } },
  // BioPython nodes
  'bp_seqio_read': { id: 'bp_seqio_read', display_name: 'SeqIO Read', category: 'BioPython', description: 'Read sequences from FASTA, GenBank, etc.', return_types: ['FILE', 'FILE'], return_names: ['sequences_json', 'stats_json'], input_types: { required: { input_file: { type: 'FILE', label: 'Sequence File' }, format: { type: 'STRING', default: 'fasta', options: ['fasta', 'fastq', 'genbank', 'embl', 'swiss', 'stockholm', 'clustal', 'phylip', 'nexus'], label: 'Format' } }, optional: { alphabet: { type: 'STRING', default: '', options: ['', 'dna', 'rna', 'protein'], label: 'Alphabet', advanced: true } } } },
  'bp_translate': { id: 'bp_translate', display_name: 'Translate DNA', category: 'BioPython', description: 'Translate nucleotide sequences to protein', return_types: ['FILE'], return_names: ['protein_fasta'], input_types: { required: { input_file: { type: 'FILE', label: 'DNA FASTA' } }, optional: { table: { type: 'STRING', default: 'Standard', options: ['Standard', 'Vertebrate Mitochondrial', 'Bacterial', 'Alternative Yeast Nuclear', 'Ciliate Nuclear'], label: 'Translation Table', advanced: true }, to_stop: { type: 'BOOLEAN', default: true, label: 'Stop at STOP codon', advanced: true } } } },
  'bp_seq_stats': { id: 'bp_seq_stats', display_name: 'Sequence Stats', category: 'BioPython', description: 'Compute GC content, length, molecular weight', return_types: ['FILE'], return_names: ['stats_json'], input_types: { required: { input_file: { type: 'FILE', label: 'Sequence File' } }, optional: { format: { type: 'STRING', default: 'fasta', options: ['fasta', 'fastq', 'genbank'], label: 'Format', advanced: true } } } },
  'bp_blast': { id: 'bp_blast', display_name: 'BLAST Search', category: 'BioPython', description: 'Run local BLAST (requires blast+)', return_types: ['FILE'], return_names: ['blast_xml'], requires_external_tools: ['blastn'], input_types: { required: { query: { type: 'FILE', label: 'Query FASTA' }, subject: { type: 'FILE', label: 'Subject FASTA' }, program: { type: 'STRING', default: 'blastn', options: ['blastn', 'blastp', 'blastx', 'tblastn', 'tblastx'], label: 'BLAST Program' } }, optional: { evalue: { type: 'FLOAT', default: 0.001, min: 0, max: 100, step: 0.001, label: 'E-value', advanced: true }, max_hits: { type: 'INT', default: 10, min: 1, max: 500, label: 'Max Hits', advanced: true }, outfmt: { type: 'STRING', default: '5', options: ['5', '6', '7'], label: 'Output Format', advanced: true } } } },
};

function createWorkflowId(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return `wf-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function getRequestedWorkflowId(): string | null {
  const id = new URLSearchParams(window.location.search).get('workflow');
  if (!id || !/^[a-zA-Z0-9._:-]{1,160}$/.test(id)) return null;
  return id;
}

function withWorkflowId(workflow: Workflow, id = workflow.id || createWorkflowId()): Workflow {
  return { ...workflow, id };
}

function emptySharedWorkflow(id: string, name = 'Shared workflow'): Workflow {
  return {
    id,
    version: 'Alpha 1.2',
    app: 'bionodulo',
    name,
    description: '',
    nodes: [],
    edges: [],
    groups: [],
    outputs: {},
  };
}

function workflowFromCollabSnapshot(workflowId: string, snapshot: Record<string, unknown>, fallbackName: string): Workflow {
  const meta = (snapshot.meta && typeof snapshot.meta === 'object' ? snapshot.meta : {}) as Record<string, unknown>;
  const values = <T,>(value: unknown): T[] => (
    value && typeof value === 'object' && !Array.isArray(value)
      ? Object.values(value as Record<string, T>)
      : []
  );
  return {
    id: workflowId,
    version: String(meta.version || 'Alpha 1.2'),
    app: 'bionodulo',
    name: String(meta.name || fallbackName),
    description: '',
    nodes: values<WorkflowNode>(snapshot.nodes),
    edges: values<Workflow['edges'][number]>(snapshot.edges),
    groups: values<Workflow['groups'][number]>(snapshot.groups),
    outputs: {},
  };
}

function remapTemplateWorkflow(data: Workflow): Workflow {
  const oldToNew = new Map<string, string>();
  data.nodes = data.nodes.map((n, i) => {
    const newId = `${n.type}_${Date.now()}_${i}`;
    oldToNew.set(n.id, newId);
    return { ...n, id: newId };
  });
  data.edges = data.edges.map(e => ({
    ...e,
    from: { ...e.from, node: oldToNew.get(e.from.node) || e.from.node },
    to: { ...e.to, node: oldToNew.get(e.to.node) || e.to.node },
  }));
  return data;
}

async function fetchTemplateWorkflow(template: TemplateInfo): Promise<Workflow | null> {
  try {
    const r = await fetch(`/api/workflow_templates/${template.filename}`);
    const data = r.ok ? await r.json() as Workflow : getLocalTemplateWorkflow(template.filename);
    return data ? remapTemplateWorkflow(data) : null;
  } catch {
    const data = getLocalTemplateWorkflow(template.filename);
    return data ? remapTemplateWorkflow(data) : null;
  }
}

export default function App() {
  const { get, getBool, set } = useSettings();
  const {
    workflows, activeIndex, activeWorkflow, validation, resolveReport, runs,
    setWorkflow, updateWorkflow, addTab, addWorkflow, closeTab, reorderWorkflows, setActiveIndex,
    validate, resolve, clearResolveReport, submitRun, addRun, updateRun, setRuns,
  } = useWorkflow();
  useTheme();

  // Authentication state
  const collabEnabled = getBool('bionodulo.collab.enabled');
  const [requestedWorkflowId, setRequestedWorkflowId] = useState(getRequestedWorkflowId);
  const [authUser, setAuthUser] = useState<ReturnType<typeof getAuthUser>>(getAuthUser());
  const [showAuthDialog, setShowAuthDialog] = useState(false);

  // Initialize auth on mount
  useEffect(() => {
    if (!collabEnabled) {
      setShowAuthDialog(false);
      return;
    }
    initAuth().then(valid => {
      if (valid) {
        setAuthUser(getAuthUser());
      } else {
        setShowAuthDialog(true);
      }
    });
  }, [collabEnabled]);

  // Handle login from AuthDialog
  const handleAuthLogin = useCallback((name: string) => {
    setAuthUser(getAuthUser());
    setShowAuthDialog(false);
  }, []);

  // Handle auth dialog close (without login)
  const handleAuthClose = useCallback(() => {
    // If user closes without logging in, keep current state
    // They can still use the app; collaboration just won't connect
    setShowAuthDialog(false);
  }, []);

  // Collaboration setup
  const currentUser = authUser
    ? { id: authUser.id, name: authUser.name, color: authUser.color }
    : { id: 'anonymous', name: 'You', color: getUserColor('anonymous') };
  const pendingWorkflowIdsRef = useRef<WeakMap<Workflow, string>>(new WeakMap());
  const activeWorkflowId = useMemo(() => {
    if (activeWorkflow.id) return activeWorkflow.id;
    const existing = pendingWorkflowIdsRef.current.get(activeWorkflow);
    if (existing) return existing;
    const id = createWorkflowId();
    pendingWorkflowIdsRef.current.set(activeWorkflow, id);
    return id;
  }, [activeWorkflow]);

  useEffect(() => {
    if (!activeWorkflow.id) {
      updateWorkflow(activeIndex, { id: activeWorkflowId });
    }
  }, [activeWorkflow.id, activeWorkflowId, activeIndex, updateWorkflow]);

  // Colab and copied room links pin each browser to the same Yjs room.
  useEffect(() => {
    if (!requestedWorkflowId) return;
    if (activeWorkflow.id !== requestedWorkflowId) {
      updateWorkflow(activeIndex, { id: requestedWorkflowId });
    }
    if (!collabEnabled) {
      set('bionodulo.collab.enabled', true);
    }
  }, [activeWorkflow.id, activeIndex, collabEnabled, requestedWorkflowId, set, updateWorkflow]);

  const {
    doc: collabDoc,
    localSessionId: collabSessionId,
    connected: collabConnected,
    connecting: collabConnecting,
    activeUsers: collabActiveUsers,
    setCursor: setCollabCursor,
    setSelection: setCollabSelection,
    claimDrag: claimCollabDrag,
    releaseDrag: releaseCollabDrag,
    shareWorkflow,
    isShared: collabIsShared,
    error: collabError,
    reconnectAttempt: collabReconnectAttempt,
    offline: collabOffline,
  } = useCollab(collabEnabled ? activeWorkflowId : null, currentUser);

  const bridgeRef = useRef<LiteGraphYjsBridge | null>(null);
  const suppressLocalSeedForWorkflowRef = useRef<string | null>(null);
  const activeWorkflowRef = useRef(activeWorkflow);
  const updateWorkflowRef = useRef(updateWorkflow);

  useEffect(() => { activeWorkflowRef.current = activeWorkflow; }, [activeWorkflow]);
  useEffect(() => { updateWorkflowRef.current = updateWorkflow; }, [updateWorkflow]);

  useEffect(() => {
    if (!collabDoc || collabConnecting) {
      bridgeRef.current?.unbind();
      bridgeRef.current = null;
      return;
    }
    const yNodes = collabDoc.getMap('nodes');
    const yEdges = collabDoc.getMap('edges');
    const yGroups = collabDoc.getMap('groups');
    const remoteHasWorkflow = yNodes.size > 0 || yEdges.size > 0 || yGroups.size > 0;
    if (remoteHasWorkflow) {
      const remoteWorkflow = docToWorkflow(collabDoc);
      updateWorkflowRef.current(activeIndex, {
        id: activeWorkflowId,
        name: remoteWorkflow.name || activeWorkflowRef.current.name,
        nodes: remoteWorkflow.nodes,
        edges: remoteWorkflow.edges,
        groups: remoteWorkflow.groups,
      });
    } else if (
      suppressLocalSeedForWorkflowRef.current !== activeWorkflowId
      && activeWorkflowRef.current.nodes.length > 0
    ) {
      workflowToDoc(activeWorkflowRef.current, collabDoc);
    }
    if (suppressLocalSeedForWorkflowRef.current === activeWorkflowId) {
      suppressLocalSeedForWorkflowRef.current = null;
    }
    const bridge = new LiteGraphYjsBridge(collabDoc, {
      onNodesChange: (nodes) => updateWorkflowRef.current(activeIndex, { nodes }),
      onEdgesChange: (edges) => updateWorkflowRef.current(activeIndex, { edges }),
      onGroupsChange: (groups) => updateWorkflowRef.current(activeIndex, { groups }),
      getNodes: () => activeWorkflowRef.current.nodes,
      getEdges: () => activeWorkflowRef.current.edges,
      getGroups: () => activeWorkflowRef.current.groups,
      onDragStart: claimCollabDrag,
      onDragEnd: releaseCollabDrag,
    });
    bridge.bind();
    bridgeRef.current = bridge;
    return () => {
      bridge.unbind();
      bridgeRef.current = null;
    };
  }, [activeWorkflowId, collabDoc, collabConnecting, activeIndex, claimCollabDrag, releaseCollabDrag]);

  const [showShareDialog, setShowShareDialog] = useState(false);
  // Phase 3 collaboration panels
  const [showComments, setShowComments] = useState(false);
  const [showVersions, setShowVersions] = useState(false);
  const [showAudit, setShowAudit] = useState(false);
  const [followingUserId, setFollowingUserId] = useState<string | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [workflowComments, setWorkflowComments] = useState<Comment[]>([]);
  const [livePresenceUsers, setLivePresenceUsers] = useState<LivePresenceUser[]>([]);
  const [workflowNames, setWorkflowNames] = useState<Record<string, string>>({});

  const fetchWorkflowComments = useCallback(async () => {
    if (!collabEnabled || !activeWorkflowId) return;
    const token = getToken();
    if (!token) return;
    try {
      const response = await fetch(`/api/collab/workflows/${activeWorkflowId}/comments`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) return;
      const data = await response.json() as { comments?: Comment[] };
      setWorkflowComments(data.comments ?? []);
    } catch {
      // Node comment pins are optional when collaboration is unavailable.
    }
  }, [activeWorkflowId, collabEnabled]);

  useEffect(() => {
    setWorkflowComments([]);
    void fetchWorkflowComments();
    if (!collabEnabled) return;
    const interval = setInterval(fetchWorkflowComments, 5000);
    return () => clearInterval(interval);
  }, [collabEnabled, fetchWorkflowComments]);

  const fetchLivePresence = useCallback(async () => {
    if (!collabEnabled) return;
    const token = getToken();
    if (!token) return;
    try {
      const response = await fetch('/api/collab/presence', {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) return;
      const data = await response.json() as { users?: LivePresenceUser[] };
      setLivePresenceUsers(data.users ?? []);
    } catch {
      // Room-local awareness still drives collaborative cursor rendering.
    }
  }, [collabEnabled]);

  useEffect(() => {
    void fetchLivePresence();
    if (!collabEnabled) return;
    const interval = setInterval(fetchLivePresence, 3000);
    return () => clearInterval(interval);
  }, [collabEnabled, fetchLivePresence]);

  useEffect(() => {
    if (!followingUserId) return;
    const user = collabActiveUsers.find(candidate => (
      candidate.user.sessionId === followingUserId || candidate.user.id === followingUserId
    ));
    if (user?.viewport) {
      canvasRef.current?.setViewport(user.viewport);
    }
  }, [collabActiveUsers, followingUserId]);

  const fetchCollabSnapshot = useCallback(async (workflowId: string, fallbackName: string): Promise<Workflow | null> => {
    const token = getToken();
    if (!token) return null;
    const response = await fetch(`/api/collab/workflows/${encodeURIComponent(workflowId)}/snapshot`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) return null;
    const data = await response.json() as { snapshot?: Record<string, unknown> };
    if (!data.snapshot) return null;
    return workflowFromCollabSnapshot(workflowId, data.snapshot, fallbackName);
  }, []);

  const followPresenceUser = useCallback(async (sessionId: string | null) => {
    if (!sessionId) {
      setFollowingUserId(null);
      return;
    }
    const presence = livePresenceUsers.find(user => user.session_id === sessionId)
      ?? livePresenceUsers.find(user => user.user_id === sessionId);
    if (presence?.workflow_id && presence.workflow_id !== activeWorkflowId) {
      const workflowName = workflowNames[presence.workflow_id] || `Workflow ${presence.workflow_id.slice(0, 12)}`;
      suppressLocalSeedForWorkflowRef.current = presence.workflow_id;
      setWorkflow(activeIndex, () => emptySharedWorkflow(presence.workflow_id, workflowName));
      const url = new URL(window.location.href);
      url.searchParams.set('workflow', presence.workflow_id);
      window.history.replaceState({}, '', url);
      setRequestedWorkflowId(presence.workflow_id);
      try {
        const snapshotWorkflow = await fetchCollabSnapshot(presence.workflow_id, workflowName);
        if (snapshotWorkflow) {
          setWorkflow(activeIndex, () => snapshotWorkflow);
          requestAnimationFrame(() => {
            requestAnimationFrame(() => canvasRef.current?.fitView());
          });
        }
      } catch {
        // Realtime sync remains the source of truth if the snapshot endpoint is unavailable.
      }
    }
    setFollowingUserId(presence?.session_id ?? sessionId);
  }, [activeIndex, activeWorkflowId, fetchCollabSnapshot, livePresenceUsers, setWorkflow, workflowNames]);

  // Host prerequisite status
  const [hostStatus, setHostStatus] = useState<HostStatus | null>(null);
  const [dismissedHostStatus, setDismissedHostStatus] = useState<HostStatus | null>(null);

  useEffect(() => {
    fetch('/api/host_status')
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data) setHostStatus(data as HostStatus);
      })
      .catch(() => { /* offline */ });
  }, []);

  const [logs, setLogs] = useState<LogEntry[]>([]);
  const MAX_LOGS = 5000;
  const addLog = useCallback((entry: LogEntry) => {
    setLogs(prev => {
      const next = [...prev, entry];
      if (next.length > MAX_LOGS) next.splice(0, next.length - MAX_LOGS);
      return next;
    });
  }, []);
  const clearLogs = useCallback(() => {
    setLogs([]);
  }, []);

  const updateNodeRunStatus = useCallback((runId: string, nodeId: string, status: NodeStatus['status'], error?: string) => {
    setRuns(prev => prev.map(run => {
      if (run.run_id !== runId) return run;
      const existing = run.node_statuses.find(node => node.node_id === nodeId);
      const nodeStatus = { ...existing, node_id: nodeId, status, ...(error ? { error } : {}) };
      return {
        ...run,
        node_statuses: existing
          ? run.node_statuses.map(node => node.node_id === nodeId ? nodeStatus : node)
          : [...run.node_statuses, nodeStatus],
      };
    }));
  }, [setRuns]);

  // Load queue and execution history from backend on startup
  useEffect(() => {
    Promise.all([
      fetch('/api/queue').then(r => r.ok ? r.json() : null),
      fetch('/api/history').then(r => r.ok ? r.json() : null),
    ]).then(([queueData, historyData]) => {
      const allRuns: RunRecord[] = [];
      const seen = new Set<string>();

      // Queue items first (active runs)
      if (queueData) {
        const items = [...(queueData.pending || []), ...(queueData.running || [])];
        for (const h of items) {
          const run: RunRecord = {
            run_id: String(h.run_id),
            status: String(h.status) as RunRecord['status'],
            workflow_name: String(h.workflow_name || 'Untitled'),
            node_statuses: Array.isArray(h.node_statuses) ? h.node_statuses as NodeStatus[] : [],
            node_outputs: {},
            execution_plan: [],
            previews: (h.previews as Record<string, string>) || {},
            artifacts: (h.artifacts as Record<string, string>) || {},
            start_time: h.started_at ? new Date(Number(h.started_at) * 1000).toISOString() : undefined,
            end_time: h.finished_at ? new Date(Number(h.finished_at) * 1000).toISOString() : undefined,
          };
          allRuns.push(run);
          seen.add(run.run_id);
        }
      }

      // History items (completed runs)
      if (historyData && Array.isArray(historyData.history)) {
        for (const h of historyData.history) {
          const runId = String(h.run_id);
          if (seen.has(runId)) continue;
          allRuns.push({
            run_id: runId,
            status: String(h.status) as RunRecord['status'],
            workflow_name: String(h.workflow_name || 'Untitled'),
            node_statuses: Array.isArray(h.node_statuses) ? h.node_statuses as NodeStatus[] : [],
            node_outputs: {},
            execution_plan: [],
            previews: (h.previews as Record<string, string>) || {},
            artifacts: (h.artifacts as Record<string, string>) || {},
            start_time: h.started_at ? new Date(Number(h.started_at) * 1000).toISOString() : undefined,
            end_time: h.finished_at ? new Date(Number(h.finished_at) * 1000).toISOString() : undefined,
          });
          seen.add(runId);
        }
      }

      setRuns(allRuns);

      // Fetch logs for the most recent runs (queue + recent history)
      const runsToFetch = allRuns.slice(0, 10);
      for (const run of runsToFetch) {
        fetch(`/api/runs/${run.run_id}/logs`)
          .then(r => r.ok ? r.json() : null)
          .then((logData: { logs?: Array<Record<string, unknown>>; run_id?: string } | null) => {
            if (!logData || !Array.isArray(logData.logs)) return;
            const newLogs: LogEntry[] = logData.logs.map(l => ({
              run_id: String(l.run_id || run.run_id),
              node_id: String(l.node_id || 'engine'),
              level: (l.level as LogEntry['level']) || 'info',
              message: String(l.message || ''),
              timestamp: String(l.timestamp || new Date().toISOString()),
            }));
            setLogs(prev => [...prev, ...newLogs]);
          })
          .catch(() => { /* ignore */ });
      }
    }).catch(() => { /* offline */ });
  }, [setRuns, addLog, setLogs]);

  // History stack for undo/redo
  const canvasRef = useRef<LiteGraphCanvasRef>(null);
  const historyRef = useRef<{ nodes: WorkflowNode[]; edges: Workflow['edges']; groups: Workflow['groups'] }[]>([]);
  const historyIndexRef = useRef(-1);
  const pendingStateRef = useRef<Partial<Workflow>>({});

  useEffect(() => {
    historyRef.current = [];
    historyIndexRef.current = -1;
  }, [activeIndex]);

  const pushHistory = useCallback(() => {
    const pending = pendingStateRef.current;
    if (Object.keys(pending).length === 0) return;
    pendingStateRef.current = {};
    const wf = { ...activeWorkflow, ...pending };
    const snapshot = {
      nodes: wf.nodes,
      edges: wf.edges,
      groups: wf.groups,
    };
    const next = historyRef.current.slice(0, historyIndexRef.current + 1);
    next.push({ ...snapshot });
    if (next.length > 50) next.shift();
    historyRef.current = next;
    historyIndexRef.current = next.length - 1;
  }, [activeWorkflow]);

  const undo = useCallback(() => {
    if (historyIndexRef.current <= 0) return;
    historyIndexRef.current -= 1;
    const state = historyRef.current[historyIndexRef.current];
    updateWorkflow(activeIndex, {
      nodes: state.nodes,
      edges: state.edges,
      groups: state.groups,
    });
  }, [activeIndex, updateWorkflow]);

  const redo = useCallback(() => {
    if (historyIndexRef.current >= historyRef.current.length - 1) return;
    historyIndexRef.current += 1;
    const state = historyRef.current[historyIndexRef.current];
    updateWorkflow(activeIndex, {
      nodes: state.nodes,
      edges: state.edges,
      groups: state.groups,
    });
  }, [activeIndex, updateWorkflow]);

  const [railTab, setRailTab] = useState<RailTab>(null);
  const [consoleVisible, setConsoleVisible] = useState(false);
  const [showExport, setShowExport] = useState(false);
  const [showImport, setShowImport] = useState(false);

  const [showAI, setShowAI] = useState(false);
  const [showGettingStarted, setShowGettingStarted] = useState(false);

  // Image lightbox state
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const [lightboxImages, setLightboxImages] = useState<{ src: string; alt: string; filename: string }[]>([]);
  const [lightboxIndex, setLightboxIndex] = useState(0);

  const openLightbox = useCallback((images: { src: string; alt: string; filename: string }[], index: number) => {
    setLightboxImages(images);
    setLightboxIndex(index);
    setLightboxOpen(true);
  }, []);
  const [isRunning, setIsRunning] = useState(false);
  const [dismissedReport, setDismissedReport] = useState<ResolveReport | null>(null);

  // WebSocket connection for real-time logs
  const wsUrl = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws`;
  const { onMessage } = useWebSocket(wsUrl);

  useEffect(() => {
    const unsub = onMessage((msg: unknown) => {
      const data = msg as Record<string, unknown>;
      const payload = (typeof data.data === 'object' && data.data !== null) ? data.data as Record<string, unknown> : {};
      const ts = String(payload.timestamp || new Date().toISOString());

      // --- Install events (pixi + dependency installer) ---
      if (data.type === 'install.log') {
        addLog({
          run_id: 'install-pixi',
          node_id: 'host',
          level: (payload.level as LogEntry['level']) || 'info',
          message: String(payload.message || ''),
          timestamp: ts,
        });
        return;
      }
      if (data.type === 'install.progress') {
        addLog({
          run_id: String(payload.job_id || 'dependency-install'),
          node_id: 'host',
          level: (payload.level as LogEntry['level']) || 'info',
          message: String(payload.message || ''),
          timestamp: ts,
        });
        return;
      }

      // --- Workflow execution logs ---
      if (data.type === 'log' && payload.message) {
        addLog({
          run_id: String(payload.run_id || data.source || 'workflow'),
          node_id: String(payload.node_id || 'engine'),
          level: (payload.level as LogEntry['level']) || 'info',
          message: String(payload.message),
          timestamp: ts,
        });
        return;
      }

      // --- Execution lifecycle events ---
      const runId = String(payload.run_id || data.source || 'workflow');
      if (data.type === 'start') {
        addLog({ run_id: runId, node_id: 'engine', level: 'info', message: `Workflow started (${payload.total_nodes} nodes)`, timestamp: ts });
      } else if (data.type === 'node_start') {
        updateNodeRunStatus(runId, String(payload.node_id), 'running');
        addLog({ run_id: runId, node_id: String(payload.node_id), level: 'info', message: `Node start [${payload.progress}] ${payload.node_type}`, timestamp: ts });
      } else if (data.type === 'node_complete') {
        updateNodeRunStatus(runId, String(payload.node_id), 'completed');
        addLog({ run_id: runId, node_id: String(payload.node_id), level: 'success', message: `Node completed`, timestamp: ts });
      } else if (data.type === 'node_error') {
        updateNodeRunStatus(runId, String(payload.node_id), 'error', String(payload.error || 'Node error'));
        addLog({ run_id: runId, node_id: String(payload.node_id), level: 'error', message: `Node error: ${payload.error}`, timestamp: ts });
      } else if (data.type === 'node_skip') {
        updateNodeRunStatus(runId, String(payload.node_id), 'skipped');
        addLog({ run_id: runId, node_id: String(payload.node_id), level: 'warn', message: `Node skipped (${payload.reason})`, timestamp: ts });
      } else if (data.type === 'node_bypass') {
        updateNodeRunStatus(runId, String(payload.node_id), 'skipped');
        addLog({ run_id: runId, node_id: String(payload.node_id), level: 'warn', message: `Node bypassed`, timestamp: ts });
      } else if (data.type === 'node_cache_hit') {
        updateNodeRunStatus(runId, String(payload.node_id), 'cached');
        addLog({ run_id: runId, node_id: String(payload.node_id), level: 'info', message: `Cache hit — skipping execution`, timestamp: ts });
      } else if (data.type === 'complete') {
        addLog({ run_id: runId, node_id: 'engine', level: payload.status === 'completed' ? 'success' : 'error', message: `Workflow ${payload.status}`, timestamp: ts });
      } else if (data.type === 'error') {
        addLog({ run_id: runId, node_id: 'engine', level: 'error', message: `Workflow error: ${payload.message}`, timestamp: ts });
      } else if (data.type === 'cancelled') {
        addLog({ run_id: runId, node_id: String(payload.node_id || 'engine'), level: 'warn', message: `Workflow cancelled`, timestamp: ts });
      }

      // --- Preview events ---
      else if (data.type === 'preview') {
        const previewRunId = String(payload.run_id || data.source || '');
        const nodeId = String(payload.node_id || '');
        const path = String(payload.path || '');
        if (previewRunId && nodeId && path) {
          updateRun(previewRunId, {
            previews: {
              ...(runs.find(r => r.run_id === previewRunId)?.previews || {}),
              [nodeId]: path,
            },
          });
        }
      }

      // --- Queue events ---
      else if (data.type === 'queue_submit') {
        addLog({ run_id: String(payload.run_id), node_id: 'queue', level: 'info', message: `Run submitted`, timestamp: ts });
      } else if (data.type === 'queue_start') {
        addLog({ run_id: String(payload.run_id), node_id: 'queue', level: 'info', message: `Run started`, timestamp: ts });
        updateRun(String(payload.run_id), { status: 'running', start_time: ts });
      } else if (data.type === 'queue_finish') {
        addLog({ run_id: String(payload.run_id), node_id: 'queue', level: 'success', message: `Run finished (${payload.status})`, timestamp: ts });
        const finalStatus = payload.status === 'completed' ? 'completed' : payload.status === 'failed' ? 'error' : 'cancelled';
        const finishedRunId = String(payload.run_id);
        updateRun(finishedRunId, { status: finalStatus, end_time: ts });
        // Fetch full run details to populate previews/artifacts
        fetch(`/api/runs/${finishedRunId}`)
          .then(r => r.ok ? r.json() : null)
          .then((runData: Record<string, unknown> | null) => {
            if (!runData) return;
            const result = runData.result as Record<string, unknown> | undefined;
            if (!result) return;
            const previews: Record<string, string> = {};
            const previewList = result.previews as Array<{ node_id?: string; path?: string }> | undefined;
            if (previewList) {
              for (const p of previewList) {
                if (p.node_id && p.path) previews[p.node_id] = p.path;
              }
            }
            const artifacts: Record<string, string> = {};
            const artifactList = result.artifacts as Array<{ node_id?: string; path?: string }> | undefined;
            if (artifactList) {
              for (const a of artifactList) {
                if (a.node_id && a.path) artifacts[a.node_id] = a.path;
              }
            }
            updateRun(finishedRunId, { previews, artifacts });
          })
          .catch(() => { /* ignore */ });
      } else if (data.type === 'queue_error') {
        addLog({ run_id: String(payload.run_id), node_id: 'queue', level: 'error', message: `Run error: ${payload.error}`, timestamp: ts });
        updateRun(String(payload.run_id), { status: 'error', end_time: ts });
      } else if (data.type === 'queue_interrupt') {
        addLog({ run_id: String(payload.run_id), node_id: 'queue', level: 'warn', message: `Run interrupted`, timestamp: ts });
        updateRun(String(payload.run_id), { status: 'cancelled', end_time: ts });
      }
    });
    return unsub;
  }, [onMessage, addLog, runs, updateRun, updateNodeRunStatus]);
  const [hpcStatus, setHpcStatus] = useState<HPCStatus>('off');

  // Getting Started modal visibility
  useEffect(() => {
    const dismissed = getBool('bionodulo.getting_started.dismissed');
    const showOnStartup = getBool('bionodulo.getting_started.show_on_startup');
    if (!dismissed && showOnStartup) {
      // Small delay so the app shell renders first
      const t = setTimeout(() => setShowGettingStarted(true), 400);
      return () => clearTimeout(t);
    }
  }, [getBool]);

  // Listen for custom event from Getting Started modal to open help
  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      setRailTab('help');
      // Store preferred help page in session if needed
      if (detail) {
        sessionStorage.setItem('bionodulo.help_page', detail);
      }
    };
    window.addEventListener('bionodulo:open-help', handler);
    return () => window.removeEventListener('bionodulo:open-help', handler);
  }, []);

  const queueCount = runs.filter(r => r.status === 'pending' || r.status === 'running').length;

  const cacheEnabled = getBool('bionodulo.cacheEnabled');
  const collabPresenceEnabled = getBool('bionodulo.collab.presence');
  const hpcEnabled = getBool('bionodulo.hpc.enabled');
  const hpcConfig: HPCConfig = {
    enabled: hpcEnabled,
    backend: ((get('bionodulo.hpc.backend') as string) || 'slurm') as HPCConfig['backend'],
    partition: (get('bionodulo.hpc.partition') as string) || '',
    account: (get('bionodulo.hpc.account') as string) || '',
    modules: (get('bionodulo.hpc.modules') as string[]) || [],
    container: (get('bionodulo.hpc.container') as string) || '',
    walltime: (get('bionodulo.hpc.walltime') as string) || '01:00:00',
    cpus_per_task: (get('bionodulo.hpc.cpus_per_task') as number) || 4,
    mem_per_cpu: (get('bionodulo.hpc.mem_per_cpu') as string) || '4G',
  };

  // Fetch HPC status from backend
  useEffect(() => {
    const checkHpcStatus = async () => {
      try {
        const r = await fetch('/api/hpc/status');
        if (r.ok) {
          const data = await r.json() as { status?: HPCStatus; connected?: boolean };
          setHpcStatus(data.status || (data.connected ? 'on' : 'off'));
        } else {
          setHpcStatus('off');
        }
      } catch {
        setHpcStatus('off');
      }
    };
    checkHpcStatus();
    // Poll every 30 seconds
    const interval = setInterval(checkHpcStatus, 30000);
    return () => clearInterval(interval);
  }, [hpcEnabled, hpcConfig.backend, hpcConfig.partition]);

  const updateActive = useCallback((partial: Partial<Workflow>) => {
    updateWorkflow(activeIndex, partial);
  }, [activeIndex, updateWorkflow]);

  const handleNodesChange = useCallback((nodes: WorkflowNode[]) => {
    if (bridgeRef.current) {
      bridgeRef.current.onNodesChanged(nodes);
    }
    pendingStateRef.current = { ...pendingStateRef.current, nodes };
    updateActive({ nodes });
  }, [updateActive]);

  const handleEdgesChange = useCallback((edges: Workflow['edges']) => {
    if (bridgeRef.current) {
      bridgeRef.current.onEdgesChanged(edges);
    }
    pendingStateRef.current = { ...pendingStateRef.current, edges };
    updateActive({ edges });
  }, [updateActive]);

  const handleGroupsChange = useCallback((groups: Workflow['groups']) => {
    if (bridgeRef.current) {
      bridgeRef.current.onGroupsChanged(groups);
    }
    pendingStateRef.current = { ...pendingStateRef.current, groups };
    updateActive({ groups });
  }, [updateActive]);

  const handleRun = useCallback(async () => {
    setIsRunning(true);
    try {
      await validate(activeWorkflow);
      const result = await submitRun(activeWorkflow, { no_cache: !cacheEnabled });
      // Add to local runs so it appears in console immediately
      addRun({
        run_id: result.run_id,
        status: 'pending',
        workflow_name: result.workflow_name || activeWorkflow.name || 'Untitled',
        node_statuses: [],
        node_outputs: {},
        execution_plan: [],
        previews: {},
        artifacts: {},
        start_time: new Date().toISOString(),
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      addLog({
        run_id: 'workflow',
        node_id: 'engine',
        level: 'error',
        message: `Run failed: ${msg}`,
        timestamp: new Date().toISOString(),
      });
      // Auto-open console so the user sees the error
      setConsoleVisible(true);
      setRailTab('console');
    }
    setIsRunning(false);
  }, [activeWorkflow, validate, submitRun, cacheEnabled, addLog, addRun]);

  const handleToggleQueue = useCallback(() => {
    const isVisible = consoleVisible || railTab === 'console';
    if (isVisible) {
      setConsoleVisible(false);
      if (railTab === 'console') setRailTab(null);
    } else {
      setConsoleVisible(true);
      setRailTab('console');
    }
  }, [consoleVisible, railTab]);

  const handleLoadTemplate = useCallback(async (template: TemplateInfo) => {
    console.log('[Template] loading:', template.filename);
    const wf = await fetchTemplateWorkflow(template);
    if (!wf) {
      console.error('Failed to load template:', template.filename);
      return;
    }
    console.log('[Template] loaded, nodes:', wf.nodes.length);
    if (collabEnabled) {
      // Keep a shared room on the same workflow id. Opening a new tab here
      // strands collaborators, presence, and comments in different rooms.
      const sharedWorkflow = withWorkflowId(wf, activeWorkflowId);
      updateWorkflow(activeIndex, sharedWorkflow);
      if (collabDoc) {
        workflowToDoc(sharedWorkflow, collabDoc);
      }
    } else {
      addWorkflow(withWorkflowId(wf));
    }
    // Auto-fit view after nodes render
    requestAnimationFrame(() => {
      requestAnimationFrame(() => canvasRef.current?.fitView());
    });
    // Resolve is auto-triggered by the activeWorkflow useEffect
  }, [activeIndex, activeWorkflowId, addWorkflow, collabDoc, collabEnabled, updateWorkflow]);

  const handleImport = useCallback((wf: Workflow) => {
    addWorkflow(withWorkflowId(wf));
    // Auto-fit view after nodes render
    requestAnimationFrame(() => {
      requestAnimationFrame(() => canvasRef.current?.fitView());
    });
    // Resolve is auto-triggered by the activeWorkflow useEffect
  }, [addWorkflow]);

  const handleRenameTab = useCallback((index: number, name: string) => {
    updateWorkflow(index, { name });
  }, [updateWorkflow]);

  const handleDuplicateTab = useCallback((index: number) => {
    const wf = workflows[index];
    if (!wf) return;
    const dup: Workflow = {
      ...wf,
      id: createWorkflowId(),
      name: `${wf.name || 'Untitled'} (copy)`,
      nodes: wf.nodes.map(n => ({ ...n, id: `${n.type}_${Date.now()}_${Math.random().toString(36).slice(2, 7)}` })),
    };
    addWorkflow(dup);
  }, [workflows, addWorkflow]);

  const handleReorderTabs = useCallback((from: number, to: number) => {
    reorderWorkflows(from, to);
  }, [reorderWorkflows]);

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;

      const key = e.key.toLowerCase();
      const isCtrl = e.ctrlKey || e.metaKey;

      if (isCtrl && key === 'f') { e.preventDefault(); setRailTab('nodes'); }
      else if (isCtrl && key === 'r') { e.preventDefault(); handleRun(); }
      else if (isCtrl && key === 'e') { e.preventDefault(); setShowExport(true); }
      else if (isCtrl && key === 'i') { e.preventDefault(); setShowImport(true); }
      else if (isCtrl && key === ',') { e.preventDefault(); setRailTab(prev => prev === 'settings' ? null : 'settings'); }
      else if (isCtrl && key === '`') { e.preventDefault(); setConsoleVisible(v => !v); }
      else if (isCtrl && key >= '1' && key <= '7') {
        e.preventDefault();
        const tabs: RailTab[] = ['data', 'nodes', 'templates', 'environments', 'hpc', 'help', 'console'];
        const idx = parseInt(key) - 1;
        setRailTab(prev => prev === tabs[idx] ? null : tabs[idx]);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [handleRun]);

  // Auto-validate and resolve on workflow change
  useEffect(() => {
    console.log('[AutoResolve] workflow changed:', activeWorkflow.name, 'nodes:', activeWorkflow.nodes.length);
    const timer = setTimeout(() => {
      console.log('[AutoResolve] running resolve...');
      validate(activeWorkflow);
      resolve(activeWorkflow).then((report) => {
        console.log('[AutoResolve] resolve result:', report?.has_issues, report?.summary);
      });
    }, 300);
    return () => clearTimeout(timer);
  }, [activeWorkflow, validate, resolve]);

  // Reset banners when workflow changes
  useEffect(() => {
    console.log('[BannerReset] activeIndex changed to', activeIndex);
    setDismissedReport(null);
    clearResolveReport();
  }, [activeIndex, clearResolveReport]);

  const tabNames = workflows.map(w => w.name || 'Untitled');
  const missingDependencyNodeIds = useMemo(() => {
    const missingTypes = new Set<string>();
    for (const item of resolveReport?.missing_nodes ?? []) missingTypes.add(item.node_type);
    for (const item of resolveReport?.missing_executables ?? []) item.node_types.forEach(type => missingTypes.add(type));
    for (const item of resolveReport?.missing_packages ?? []) item.node_types.forEach(type => missingTypes.add(type));
    for (const item of resolveReport?.missing_r_packages ?? []) item.node_types.forEach(type => missingTypes.add(type));
    return new Set(activeWorkflow.nodes.filter(node => missingTypes.has(node.type)).map(node => node.id));
  }, [activeWorkflow.nodes, resolveReport]);
  const nodeCommentsMap = useMemo(() => {
    const map = new Map<string, { count: number; unresolved: boolean }>();
    const add = (comment: Comment) => {
      if (!comment.node_id) return;
      const previous = map.get(comment.node_id) ?? { count: 0, unresolved: false };
      map.set(comment.node_id, {
        count: previous.count + 1,
        unresolved: previous.unresolved || !comment.resolved,
      });
      comment.replies?.forEach(add);
    };
    workflowComments.forEach(add);
    return map;
  }, [workflowComments]);
  const knownWorkflowNames = useMemo(() => ({
    ...Object.fromEntries(workflows.filter(workflow => workflow.id).map(workflow => [workflow.id!, workflow.name || 'Untitled'])),
    ...workflowNames,
  }), [workflowNames, workflows]);
  return (
    <div className={[
      'app-shell',
      showAI ? 'ai-open' : '',
      showComments ? 'comments-open' : '',
      (consoleVisible || railTab === 'console') ? 'console-open' : '',
    ].filter(Boolean).join(' ')}>
      <TopBar
        validationValid={validation.valid}
        validationErrors={validation.errors}
        onRun={handleRun}
        onExport={() => setShowExport(true)}
        onImport={() => setShowImport(true)}
        onAI={() => setShowAI(true)}
        hpcStatus={hpcStatus}
        isRunning={isRunning}
        queueCount={queueCount}
        onToggleQueue={handleToggleQueue}
        collabControls={(
          <CollabBadge
            enabled={collabEnabled}
            connected={collabConnected}
            connecting={collabConnecting}
            activeUsers={collabActiveUsers}
            liveUsers={livePresenceUsers}
            currentUserId={currentUser.id}
            currentSessionId={collabSessionId}
            currentWorkflowId={activeWorkflowId}
            workflowNames={knownWorkflowNames}
            followingUserId={followingUserId}
            isShared={collabIsShared}
            onShare={() => setShowShareDialog(true)}
            onFollow={followPresenceUser}
            onOpenComments={() => setShowComments(v => !v)}
            onOpenVersions={() => setShowVersions(v => !v)}
            onOpenAudit={() => setShowAudit(v => !v)}
            onOpenSettings={() => setRailTab('settings')}
            reconnectAttempt={collabReconnectAttempt}
            error={collabError}
            offline={collabOffline || !collabEnabled}
          />
        )}
      />

      <AuthDialog
        isOpen={showAuthDialog}
        onLogin={handleAuthLogin}
        onClose={handleAuthClose}
      />

      <WorkflowTabs
        tabs={tabNames}
        active={activeIndex}
        onChange={setActiveIndex}
        onClose={closeTab}
        onAdd={addTab}
        onRename={handleRenameTab}
        onDuplicate={handleDuplicateTab}
        onReorder={handleReorderTabs}
      />

      <LeftRail active={railTab} onChange={setRailTab} />

      <div
        className="main-canvas"
        onDragOver={(e) => {
          if (e.dataTransfer.types.includes('application/bionodulo-workflow-path')) {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'copy';
          }
        }}
        onDrop={async (e) => {
          e.preventDefault();
          const path = e.dataTransfer.getData('application/bionodulo-workflow-path');
          if (!path) return;
          try {
            const r = await fetch(`/api/workspace/file?path=${encodeURIComponent(path)}`);
            if (!r.ok) return;
            const text = await r.text();
            const wf = JSON.parse(text);
            if (wf && (wf.nodes || Array.isArray(wf))) {
              handleImport(wf);
            }
          } catch { /* ignore */ }
        }}
      >
        {collabEnabled && collabPresenceEnabled && (
          <ForeignCursors
            activeUsers={collabActiveUsers}
            currentUserId={currentUser.id}
          />
        )}
        {hostStatus && !hostStatus.ready && hostStatus !== dismissedHostStatus && (
          <HostPrerequisitesBanner
            status={hostStatus}
            onDismiss={() => setDismissedHostStatus(hostStatus)}
            onOpenConsole={() => { setConsoleVisible(true); setRailTab('console'); }}
            onRecheck={async () => {
              const r = await fetch('/api/host_status');
              if (r.ok) setHostStatus(await r.json() as HostStatus);
            }}
          />
        )}
        {resolveReport && resolveReport.has_issues && resolveReport !== dismissedReport && (
          <MissingDependenciesBanner
            report={resolveReport}
            workflow={activeWorkflow}
            onDismiss={() => setDismissedReport(resolveReport)}
            onOpenConsole={() => { setConsoleVisible(true); setRailTab('console'); }}
            onResolve={() => { resolve(activeWorkflow); }}
          />
        )}
        <LiteGraphCanvas
          ref={canvasRef}
          nodes={activeWorkflow.nodes}
          edges={activeWorkflow.edges}
          groups={activeWorkflow.groups}
          objectInfo={BUILTIN_NODES /* merged with server-provided */}
          onNodesChange={handleNodesChange}
          onEdgesChange={handleEdgesChange}
          onGroupsChange={handleGroupsChange}
          onPushHistory={pushHistory}
          onUndo={undo}
          onRedo={redo}
          snapToGrid={getBool('bionodulo.snapToGrid')}
          showMinimap={getBool('bionodulo.showMinimap')}
          viewportLocked={getBool('bionodulo.viewportLocked')}
          linksHidden={getBool('bionodulo.linksHidden')}
          onToggleMinimap={() => set('bionodulo.showMinimap', !getBool('bionodulo.showMinimap'))}
          onToggleLinksHidden={() => set('bionodulo.linksHidden', !getBool('bionodulo.linksHidden'))}
          nodeStatusMap={new Map(runs.length > 0 ? runs[0].node_statuses.map(ns => [ns.node_id, ns.status]) : [])}
          missingDependencyNodeIds={missingDependencyNodeIds}
          nodeCommentsMap={nodeCommentsMap}
          nodeComments={workflowComments}
          collabWorkflowId={collabEnabled ? activeWorkflowId : undefined}
          currentCollabUser={collabEnabled ? currentUser : undefined}
          onNodeCommentsChange={() => void fetchWorkflowComments()}
          collabUsers={collabActiveUsers}
          nodePreviewsMap={(() => {
            if (runs.length === 0) return undefined;
            const latest = runs[0];
            const map = new Map<string, string>();
            // Map previews to image_preview nodes (show preview on the viewer, not the producer)
            for (const node of activeWorkflow.nodes) {
              if (node.type === 'image_preview') {
                const incoming = activeWorkflow.edges.find(e => e.to.node === node.id);
                if (incoming) {
                  const sourceNodeId = incoming.from.node;
                  const path = latest.previews?.[sourceNodeId];
                  if (path) {
                    map.set(node.id, `/api/previews/${latest.run_id}/${sourceNodeId}?path=${encodeURIComponent(path)}`);
                  }
                }
              }
            }
            return map;
          })()}
          collabBridge={bridgeRef.current ?? undefined}
          onCollabCursor={collabEnabled ? setCollabCursor : undefined}
          onCollabSelection={(nodeIds) => {
            setSelectedNodeId(nodeIds[0] ?? null);
            setCollabSelection({ nodeIds });
          }}
          onCollabDragStart={claimCollabDrag}
          onCollabDragEnd={releaseCollabDrag}
        />

        {/* Rail panels */}
        {railTab === 'settings' && <SettingsPanel onClose={() => setRailTab(null)} />}
        {railTab === 'help' && <HelpWikiPanel onClose={() => setRailTab(null)} />}
        {railTab === 'templates' && <TemplatesPanel onClose={() => setRailTab(null)} onLoadTemplate={handleLoadTemplate} />}
        {railTab === 'environments' && (
          <EnvironmentPanel onClose={() => setRailTab(null)} currentWorkflow={activeWorkflow} />
        )}
        {railTab === 'hpc' && (
          <HPCPanel
            config={hpcConfig}
            onChange={(cfg) => {
              set('bionodulo.hpc.enabled', cfg.enabled);
              set('bionodulo.hpc.backend', cfg.backend);
              set('bionodulo.hpc.partition', cfg.partition || '');
              set('bionodulo.hpc.account', cfg.account || '');
              set('bionodulo.hpc.modules', cfg.modules || []);
              set('bionodulo.hpc.container', cfg.container || '');
              set('bionodulo.hpc.walltime', cfg.walltime || '01:00:00');
              set('bionodulo.hpc.cpus_per_task', cfg.cpus_per_task || 4);
              set('bionodulo.hpc.mem_per_cpu', cfg.mem_per_cpu || '4G');
            }}
            onClose={() => setRailTab(null)}
          />
        )}
        {railTab === 'nodes' && <NodeLibraryPanel objectInfo={BUILTIN_NODES} onAddNode={(meta) => {
          const newNode: WorkflowNode = {
            id: `${meta.id}_${Date.now()}`,
            type: meta.id,
            position: [200 + Math.random() * 40, 200 + Math.random() * 40],
            params: defaultsFor(meta),
            node_info: meta,
            ui: { title: meta.display_name },
          };
          handleNodesChange([...activeWorkflow.nodes, newNode]);
          pushHistory();
        }} onClose={() => setRailTab(null)} />}
        {railTab === 'data' && (
          <WorkspacePanel
            onClose={() => setRailTab(null)}
            onOpenSettings={() => setRailTab('settings')}
            onImportWorkflow={handleImport}
          />
        )}

        <HardwareMonitor />
        {(consoleVisible || railTab === 'console') && (
          <ErrorBoundary>
            <BottomConsole
              logs={logs}
              queue={runs.filter(r => r.status === 'pending' || r.status === 'running')}
              history={runs}
              onClose={() => { setConsoleVisible(false); if (railTab === 'console') setRailTab(null); }}
              onOpenLightbox={openLightbox}
              onClearLogs={clearLogs}
            />
          </ErrorBoundary>
        )}
      </div>

      <ShareDialog
        workflowId={activeWorkflowId}
        isOpen={showShareDialog}
        onClose={() => setShowShareDialog(false)}
      />

      {/* Phase 3 Collaboration Panels */}
      <CommentsPanel
        workflowId={activeWorkflowId}
        selectedNodeId={null}
        currentUser={currentUser}
        isOpen={showComments}
        onClose={() => setShowComments(false)}
        onFocusNode={(nodeId) => {
          setSelectedNodeId(nodeId);
          canvasRef.current?.focusNode(nodeId);
        }}
        onCommentsChange={setWorkflowComments}
        onWorkflowNamesChange={setWorkflowNames}
      />
      <VersionHistory
        workflowId={activeWorkflowId}
        isOpen={showVersions}
        onClose={() => setShowVersions(false)}
        onRestore={(versionJson) => {
          if (versionJson && typeof versionJson === 'object') {
            const v = versionJson as Record<string, unknown>;
            if (v.nodes) updateWorkflow(activeIndex, { nodes: v.nodes as WorkflowNode[] });
            if (v.edges) updateWorkflow(activeIndex, { edges: v.edges as Workflow['edges'] });
            if (v.groups) updateWorkflow(activeIndex, { groups: v.groups as Workflow['groups'] });
          }
        }}
      />
      <AuditLog
        workflowId={activeWorkflowId}
        isOpen={showAudit}
        onClose={() => setShowAudit(false)}
      />

      {/* Modals */}
      {showExport && <ExportModal workflow={activeWorkflow} onClose={() => setShowExport(false)} />}
      {showImport && <ImportModal onImport={handleImport} onClose={() => setShowImport(false)} />}
      {showAI && (
        <AIWorkflowModal
          workflow={activeWorkflow}
          onClose={() => setShowAI(false)}
          onApplyWorkflow={(wf) => setWorkflow(activeIndex, () => withWorkflowId(wf, activeWorkflowId))}
        />
      )}
      {showGettingStarted && (
        <GettingStartedModal
          onClose={() => {
            set('bionodulo.getting_started.dismissed', true);
            setShowGettingStarted(false);
          }}
          onDontShowAgain={(hide) => {
            set('bionodulo.getting_started.show_on_startup', !hide);
          }}
          collabEnabled={collabEnabled}
          onSetCollabEnabled={(enabled) => {
            set('bionodulo.collab.enabled', enabled);
            if (!enabled) {
              setShowAuthDialog(false);
            } else if (!authUser) {
              setShowAuthDialog(true);
            }
          }}
          showOnStartup={getBool('bionodulo.getting_started.show_on_startup')}
        />
      )}
      <ImageLightbox
        images={lightboxImages}
        initialIndex={lightboxIndex}
        isOpen={lightboxOpen}
        onClose={() => setLightboxOpen(false)}
      />

    </div>
  );
}
