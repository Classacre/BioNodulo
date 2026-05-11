import { useState, useCallback, useEffect, useRef } from 'react';
import TopBar from './components/layout/TopBar';
import LeftRail, { type RailTab } from './components/layout/LeftRail';
import WorkflowTabs from './components/layout/WorkflowTabs';
import BottomConsole from './components/layout/BottomConsole';
import LiteGraphCanvas from './components/canvas/LiteGraphCanvas';
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
import { useSettings } from './hooks/useSettings';
import { useWorkflow } from './hooks/useWorkflow';
import { useTheme } from './hooks/useTheme';
import { defaultsFor } from './utils';
import type { Workflow, WorkflowNode, NodeMetadata, HPCConfig, TemplateInfo, LogEntry } from './types';

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
  'note': { id: 'note', display_name: 'Note', category: 'Utility', description: 'Add a text note or description to the workflow', search_aliases: ['note', 'text', 'comment', 'description'], input_types: { required: { text: { type: 'STRING', default: '', multiline: true, label: 'Text' } } } },
  'reroute': { id: 'reroute', display_name: 'Reroute', category: 'Utility', description: 'Pass a connection through a routing point', search_aliases: ['reroute', 'pass', 'junction', 'connection'], input_types: { required: { input: { type: 'STRING', label: 'Input' } } }, return_types: ['STRING'], return_names: ['output'] },
  'view_text': { id: 'view_text', display_name: 'View Text', category: 'Utility', description: 'View text file contents', output_node: true, return_types: ['STRING'], return_names: ['text'], input_types: { required: { file: { type: 'FILE', label: 'File' } } } },
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

async function fetchTemplateWorkflow(template: TemplateInfo): Promise<Workflow | null> {
  try {
    const r = await fetch(`/api/workflow_templates/${template.filename}`);
    if (!r.ok) return null;
    const data = await r.json() as Workflow;
    // Assign fresh unique ids so multiple loads don't collide
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
  } catch {
    return null;
  }
}

export default function App() {
  const { get, getBool, set } = useSettings();
  const {
    workflows, activeIndex, activeWorkflow, validation, runs,
    updateWorkflow, addTab, addWorkflow, closeTab, reorderWorkflows, setActiveIndex,
    validate, submitRun,
  } = useWorkflow();
  useTheme();

  // History stack for undo/redo
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
  const [isRunning, setIsRunning] = useState(false);
  const [logs] = useState<LogEntry[]>([]);

  const queueCount = runs.filter(r => r.status === 'pending' || r.status === 'running').length;

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

  const updateActive = useCallback((partial: Partial<Workflow>) => {
    updateWorkflow(activeIndex, partial);
  }, [activeIndex, updateWorkflow]);

  const handleNodesChange = useCallback((nodes: WorkflowNode[]) => {
    pendingStateRef.current = { ...pendingStateRef.current, nodes };
    updateActive({ nodes });
  }, [updateActive]);

  const handleEdgesChange = useCallback((edges: Workflow['edges']) => {
    pendingStateRef.current = { ...pendingStateRef.current, edges };
    updateActive({ edges });
  }, [updateActive]);

  const handleGroupsChange = useCallback((groups: Workflow['groups']) => {
    pendingStateRef.current = { ...pendingStateRef.current, groups };
    updateActive({ groups });
  }, [updateActive]);

  const handleRun = useCallback(async () => {
    setIsRunning(true);
    try {
      await validate(activeWorkflow);
      await submitRun(activeWorkflow, { hpc: hpcEnabled, hpc_config: hpcConfig });
    } catch { /* ignore */ }
    setIsRunning(false);
  }, [activeWorkflow, validate, submitRun, hpcEnabled, hpcConfig]);

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
    const wf = await fetchTemplateWorkflow(template);
    if (!wf) {
      console.error('Failed to load template:', template.filename);
      return;
    }
    addWorkflow(wf);
  }, [addWorkflow]);

  const handleImport = useCallback((wf: Workflow) => {
    addWorkflow(wf);
  }, [addWorkflow]);

  const handleRenameTab = useCallback((index: number, name: string) => {
    updateWorkflow(index, { name });
  }, [updateWorkflow]);

  const handleDuplicateTab = useCallback((index: number) => {
    const wf = workflows[index];
    if (!wf) return;
    const dup: Workflow = {
      ...wf,
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

  // Auto-validate on workflow change
  useEffect(() => {
    const timer = setTimeout(() => { validate(activeWorkflow); }, 500);
    return () => clearTimeout(timer);
  }, [activeWorkflow, validate]);

  const tabNames = workflows.map(w => w.name || 'Untitled');

  return (
    <div className="app-shell">
      <TopBar
        validationValid={validation.valid}
        validationErrors={validation.errors}
        onRun={handleRun}
        onExport={() => setShowExport(true)}
        onImport={() => setShowImport(true)}

        onAI={() => setShowAI(true)}
        hpcEnabled={hpcEnabled}
        onToggleHPC={() => set('bionodulo.hpc.enabled', !hpcEnabled)}
        isRunning={isRunning}
        queueCount={queueCount}
        onToggleQueue={handleToggleQueue}
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

      <div className="main-canvas">
        <LiteGraphCanvas
          nodes={activeWorkflow.nodes}
          edges={activeWorkflow.edges}
          groups={activeWorkflow.groups}
          objectInfo={{ ...BUILTIN_NODES /* merged with server-provided */ }}
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
          nodeStatusMap={new Map(runs.length > 0 ? runs[runs.length - 1].node_statuses.map(ns => [ns.node_id, ns.status]) : [])}
        />

        {/* Rail panels */}
        {railTab === 'settings' && <SettingsPanel onClose={() => setRailTab(null)} />}
        {railTab === 'help' && <HelpWikiPanel onClose={() => setRailTab(null)} />}
        {railTab === 'templates' && <TemplatesPanel onClose={() => setRailTab(null)} onLoadTemplate={handleLoadTemplate} />}
        {railTab === 'environments' && <EnvironmentPanel onClose={() => setRailTab(null)} />}
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
        {railTab === 'data' && <WorkspacePanel onClose={() => setRailTab(null)} />}

        <HardwareMonitor />
        <BottomConsole
          visible={consoleVisible || railTab === 'console'}
          logs={logs}
          queue={runs.filter(r => r.status === 'pending' || r.status === 'running')}
          history={runs}
          onClose={() => { setConsoleVisible(false); if (railTab === 'console') setRailTab(null); }}
        />
      </div>

      {/* Modals */}
      {showExport && <ExportModal workflow={activeWorkflow} onClose={() => setShowExport(false)} />}
      {showImport && <ImportModal onImport={handleImport} onClose={() => setShowImport(false)} />}
      {showAI && <AIWorkflowModal onClose={() => setShowAI(false)} />}

    </div>
  );
}
