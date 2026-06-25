import { expect, test } from '@playwright/test';

const objectInfo = {
  if_condition: {
    name: 'if_condition',
    display_name: 'If Condition',
    category: 'flow_control',
    description: 'Branch workflow execution based on a condition.',
    search_aliases: ['branch', 'condition', 'flow control'],
    input: {
      required: {
        value: { type: 'ANY' },
      },
    },
    output: ['ANY'],
    output_name: ['selected'],
  },
  filter_rows: {
    name: 'filter_rows',
    display_name: 'Filter Rows',
    category: 'data_transform',
    description: 'Filter tabular rows using a simple predicate.',
    search_aliases: ['table filter', 'data transform'],
    input: {
      required: {
        table: { type: 'FILE' },
      },
    },
    output: ['FILE'],
    output_name: ['filtered_table'],
  },
  http_request: {
    name: 'http_request',
    display_name: 'HTTP Request',
    category: 'api',
    description: 'Call a REST API endpoint from a workflow.',
    search_aliases: ['rest', 'webhook', 'api call'],
    input: {
      required: {
        url: { type: 'STRING' },
      },
    },
    output: ['JSON'],
    output_name: ['response_json'],
  },
  alphafold_db: {
    name: 'alphafold_db',
    display_name: 'AlphaFold DB',
    category: 'databases',
    description: 'Fetch AlphaFold structure metadata by UniProt accession.',
    search_aliases: ['protein structure', 'database', 'alphafold'],
    input: {
      required: {
        uniprot_id: { type: 'STRING' },
      },
    },
    output: ['JSON'],
    output_name: ['prediction'],
  },
  colabfold_batch: {
    name: 'colabfold_batch',
    display_name: 'ColabFold Batch',
    category: 'ai',
    description: 'Predict protein structures from FASTA sequences with ColabFold batch.',
    search_aliases: ['colabfold', 'mmseqs2', 'protein folding'],
    input: {
      required: {
        fasta: { type: 'FASTA' },
      },
    },
    output: ['DIRECTORY'],
    output_name: ['prediction_dir'],
  },
  esmfold_predict: {
    name: 'esmfold_predict',
    display_name: 'ESMFold Predict',
    category: 'ai',
    description: 'Predict protein structures from FASTA sequences with ESMFold.',
    search_aliases: ['esmfold', 'single sequence', 'protein folding'],
    input: {
      required: {
        fasta: { type: 'FASTA' },
      },
    },
    output: ['DIRECTORY'],
    output_name: ['pdb_dir'],
  },
  proteinmpnn_design: {
    name: 'proteinmpnn_design',
    display_name: 'ProteinMPNN Design',
    category: 'ai',
    description: 'Design protein sequences from a backbone PDB using ProteinMPNN.',
    search_aliases: ['proteinmpnn', 'inverse folding', 'protein design'],
    input: {
      required: {
        script_path: { type: 'FILE' },
        pdb_path: { type: 'FILE' },
      },
    },
    output: ['DIRECTORY', 'FASTA'],
    output_name: ['design_dir', 'designed_sequences'],
  },
  minigraph_cactus: {
    name: 'minigraph_cactus',
    display_name: 'Minigraph-Cactus',
    category: 'pangenomics',
    description: 'Build pangenome graphs from assemblies using the Cactus Minigraph-Cactus pipeline.',
    search_aliases: ['minigraph-cactus', 'cactus-pangenome', 'HPRC', 'pangenome construction'],
    input: {
      required: {
        seq_file: { type: 'FILE' },
        reference: { type: 'STRING' },
      },
    },
    output: ['GBZ', 'VCF_GZ', 'GFA', 'ODGI'],
    output_name: ['graph_gbz', 'variants_vcf', 'graph_gfa', 'graph_odgi'],
  },
  clair3: {
    name: 'clair3',
    display_name: 'Clair3',
    category: 'variant',
    description: 'Call small variants from long-read BAM files with Clair3 deep-learning models.',
    search_aliases: ['clair3', 'nanopore', 'deep learning', 'long-read variant caller'],
    input: {
      required: {
        bam: { type: 'BAM' },
        reference: { type: 'FASTA' },
        model_path: { type: 'DIRECTORY' },
      },
    },
    output: ['VCF_GZ'],
    output_name: ['vcf'],
  },
  sage_search: {
    name: 'sage_search',
    display_name: 'Sage Search',
    category: 'proteomics',
    description: 'Fast Rust-based peptide-spectrum matching for large-scale proteomics searches.',
    search_aliases: ['sage', 'sage-proteomics', 'proteomics', 'peptide identification'],
    input: {
      required: {
        spectra_files: { type: 'FILE' },
        fasta_db: { type: 'FASTA' },
      },
    },
    output: ['TSV', 'JSON', 'FILE'],
    output_name: ['results_tsv', 'results_json', 'config_json'],
  },
  fragpipe: {
    name: 'fragpipe',
    display_name: 'FragPipe Workflow',
    category: 'proteomics',
    description: 'Run FragPipe headless workflows for end-to-end proteomics processing.',
    search_aliases: ['fragpipe', 'headless', 'msfragger', 'proteomics', 'proteomics workflow'],
    input: {
      required: {
        workflow_file: { type: 'FILE' },
        manifest_file: { type: 'FILE' },
      },
    },
    output: ['DIRECTORY'],
    output_name: ['results_dir'],
  },
  llm_prompt: {
    name: 'llm_prompt',
    display_name: 'LLM Prompt',
    category: 'ai',
    description: 'Run a prompt against a configured LLM provider.',
    search_aliases: ['ai prompt', 'language model'],
    input: {
      required: {
        prompt: { type: 'STRING' },
      },
    },
    output: ['STRING'],
    output_name: ['response'],
  },
  workflow_trigger: {
    name: 'workflow_trigger',
    display_name: 'Workflow Trigger',
    category: 'workflow',
    description: 'Trigger workflows using webhooks, schedules, or file watches.',
    search_aliases: ['schedule', 'webhook', 'file watch'],
    input: {},
    output: ['JSON'],
    output_name: ['trigger'],
  },
  busco: {
    name: 'busco',
    display_name: 'BUSCO',
    category: 'assembly',
    description: 'Assess assembly or annotation completeness using BUSCO lineage orthologs.',
    search_aliases: ['Galaxy', 'busco', 'completeness', 'orthologs'],
    input: {
      required: {
        input: { type: 'FASTA' },
        mode: { type: 'STRING', default: 'genome', options: ['genome', 'transcriptome', 'proteins'] },
        threads: { type: 'INT', default: 4 },
      },
    },
    output: ['STATS_FILE', 'TSV', 'TSV', 'IMAGE'],
    output_name: ['short_summary', 'full_table', 'missing_buscos', 'summary_image'],
    required_executables: ['busco'],
    required_conda_packages: ['busco'],
    documentation_url: 'https://busco.ezlab.org/',
    citation_dois: ['10.1093/bioinformatics/btv351'],
    citation_urls: ['https://doi.org/10.1093/bioinformatics/btv351'],
    citation_text: 'BUSCO completeness citation.',
  },
  diamond_align: {
    name: 'diamond_align',
    display_name: 'DIAMOND Align',
    category: 'alignment',
    description: 'Run DIAMOND blastp or blastx searches against a protein database.',
    search_aliases: ['Galaxy', 'diamond', 'blastp', 'blastx', 'protein alignment'],
    input: {
      required: {
        query: { type: 'FASTA' },
        database: { type: 'FILE' },
        method: { type: 'STRING', default: 'blastp', options: ['blastp', 'blastx'] },
        threads: { type: 'INT', default: 12 },
      },
    },
    output: ['TSV'],
    output_name: ['matches'],
    required_executables: ['diamond'],
    required_conda_packages: ['diamond'],
    documentation_url: 'https://github.com/bbuchfink/diamond/wiki',
    citation_dois: ['10.1038/s41592-021-01101-x'],
    citation_urls: ['https://doi.org/10.1038/s41592-021-01101-x'],
    citation_text: 'Sensitive protein alignments at tree-of-life scale using DIAMOND.',
  },
  htseq_count: {
    name: 'htseq_count',
    display_name: 'HTSeq-count',
    category: 'rna_seq',
    description: 'Count aligned reads that overlap GFF/GTF features.',
    search_aliases: ['Galaxy', 'htseq-count', 'gene counts'],
    input: {
      required: {
        samfile: { type: 'BAM' },
        gfffile: { type: 'GFF_GTF' },
      },
    },
    output: ['COUNTS'],
    output_name: ['counts'],
    citation_dois: ['10.1093/bioinformatics/btu638'],
    citation_urls: ['https://doi.org/10.1093/bioinformatics/btu638'],
  },
  hmmer_hmmscan: {
    name: 'hmmer_hmmscan',
    display_name: 'HMMER hmmscan',
    category: 'annotation',
    description: 'Search protein sequences against a profile HMM database.',
    search_aliases: ['Galaxy', 'hmmer', 'hmmscan', 'pfam'],
    input: {
      required: {
        seqfile: { type: 'FASTA' },
        hmmdb: { type: 'FILE' },
      },
    },
    output: ['STATS_FILE', 'TSV', 'TSV', 'TSV'],
    output_name: ['output', 'tblout', 'domtblout', 'pfamtblout'],
    citation_dois: ['10.1093/nar/gkr367'],
    citation_urls: ['https://doi.org/10.1093/nar/gkr367'],
  },
  mmseqs2_easy_search: {
    name: 'mmseqs2_easy_search',
    display_name: 'MMseqs2 Easy Search',
    category: 'alignment',
    description: 'Run MMseqs2 easy-search for sequence homology searches.',
    search_aliases: ['Galaxy', 'mmseqs2', 'mmseqs', 'easy-search'],
    input: {
      required: {
        query_fasta: { type: 'FASTA' },
        target_fasta: { type: 'FASTA' },
      },
    },
    output: ['TSV'],
    output_name: ['search_results'],
    citation_dois: ['10.1038/nbt.3988'],
    citation_urls: ['https://doi.org/10.1038/nbt.3988'],
  },
  mash_dist: {
    name: 'mash_dist',
    display_name: 'Mash Dist',
    category: 'genomics',
    description: 'Estimate genome or metagenome distances from FASTA/FASTQ files or Mash sketches.',
    search_aliases: ['Galaxy', 'mash', 'mash dist', 'minhash', 'minhash distance', 'genome distance'],
    input: {
      required: {
        reference: { type: 'FASTA' },
        query: { type: 'FASTA' },
      },
    },
    output: ['TSV'],
    output_name: ['distances'],
    citation_dois: ['10.1186/s13059-016-0997-x'],
    citation_urls: ['https://doi.org/10.1186/s13059-016-0997-x'],
  },
  fastani: {
    name: 'fastani',
    display_name: 'FastANI',
    category: 'genomics',
    description: 'Compute alignment-free whole-genome Average Nucleotide Identity for query and reference genomes.',
    search_aliases: ['Galaxy', 'fastani', 'ANI', 'average nucleotide identity', 'genome comparison'],
    input: {
      required: {
        query: { type: 'FASTA_LIST' },
        reference: { type: 'FASTA_LIST' },
      },
    },
    output: ['TSV', 'FILE', 'FILE'],
    output_name: ['ani_table', 'ani_matrix', 'visual_mappings'],
    citation_dois: ['10.1038/s41467-018-07641-9'],
    citation_urls: ['https://doi.org/10.1038/s41467-018-07641-9'],
  },
  lofreq_call: {
    name: 'lofreq_call',
    display_name: 'LoFreq Call',
    category: 'variant',
    description: 'Call sequence-quality-aware SNVs and indels from mapped reads using LoFreq.',
    search_aliases: ['Galaxy', 'lofreq', 'variant caller', 'low frequency variants'],
    input: {
      required: {
        reads: { type: 'BAM' },
        reference: { type: 'FASTA' },
      },
    },
    output: ['VCF'],
    output_name: ['variants'],
    citation_dois: ['10.1093/nar/gks918'],
    citation_urls: ['https://doi.org/10.1093/nar/gks918'],
  },
  ivar_variants: {
    name: 'ivar_variants',
    display_name: 'iVar Variants',
    category: 'variant',
    description: 'Call iSNVs and indels from aligned viral amplicon reads with iVar variants.',
    search_aliases: ['Galaxy', 'ivar', 'viral variants', 'amplicon variants', 'iSNV'],
    input: {
      required: {
        input_bam: { type: 'BAM' },
        ref: { type: 'FASTA' },
      },
    },
    output: ['TSV', 'VCF'],
    output_name: ['variants_tsv', 'variants_vcf'],
    citation_dois: ['10.1186/s13059-018-1618-7'],
    citation_urls: ['https://doi.org/10.1186/s13059-018-1618-7'],
  },
  gtdbtk_classify_wf: {
    name: 'gtdbtk_classify_wf',
    display_name: 'GTDB-Tk Classify',
    category: 'taxonomy',
    description: 'Classify bacterial and archaeal genomes against the GTDB reference taxonomy.',
    search_aliases: ['Galaxy', 'gtdbtk', 'GTDB-Tk', 'classify_wf', 'taxonomy', 'genome taxonomy'],
    input: {
      required: {
        input: { type: 'FASTA_LIST' },
        gtdbtk_data_path: { type: 'DIRECTORY' },
      },
    },
    output: ['DIRECTORY', 'DIRECTORY', 'DIRECTORY', 'DIRECTORY', 'STATS_FILE'],
    output_name: ['align', 'identify', 'classify', 'summary', 'process_log'],
    required_executables: ['gtdbtk'],
    required_conda_packages: ['gtdbtk'],
    documentation_url: 'https://ecogenomics.github.io/GTDBTk/commands/classify_wf.html',
    citation_dois: ['10.1093/bioinformatics/btz848'],
    citation_urls: ['https://doi.org/10.1093/bioinformatics/btz848'],
    citation_text: 'GTDB-Tk: a toolkit to classify genomes with the Genome Taxonomy Database.',
  },
  rseqc_infer_experiment: {
    name: 'rseqc_infer_experiment',
    display_name: 'RSeQC Infer Experiment',
    category: 'rna_seq',
    description: 'Estimate RNA-seq strandedness and library configuration from mapped reads.',
    search_aliases: ['Galaxy', 'rseqc', 'infer_experiment', 'strandedness', 'rna-seq qc'],
    input: {
      required: {
        input: { type: 'BAM' },
        refgene: { type: 'BED' },
      },
    },
    output: ['STATS_FILE'],
    output_name: ['infer_experiment'],
    required_executables: ['infer_experiment.py'],
    required_conda_packages: ['rseqc'],
    documentation_url: 'https://rseqc.sourceforge.net/#infer-experiment-py',
    citation_dois: ['10.1093/bioinformatics/bts356'],
    citation_urls: ['https://doi.org/10.1093/bioinformatics/bts356'],
    citation_text: 'RSeQC: quality control of RNA-seq experiments.',
  },
  bedtools_coveragebed: {
    name: 'bedtools_coveragebed',
    display_name: 'BEDTools Coverage',
    category: 'genomics',
    description: 'Compute interval coverage depth and breadth using bedtools coverage.',
    search_aliases: ['Galaxy', 'bedtools', 'coverage', 'coveragebed', 'depth', 'breadth'],
    input: {
      required: {
        inputA: { type: 'BED' },
        inputB: { type: 'BED_LIST' },
      },
    },
    output: ['BED'],
    output_name: ['coverage'],
    required_executables: ['bedtools'],
    required_conda_packages: ['bedtools'],
    documentation_url: 'https://bedtools.readthedocs.io/en/latest/content/tools/coverage.html',
    citation_dois: ['10.1093/bioinformatics/btq033'],
    citation_urls: ['https://doi.org/10.1093/bioinformatics/btq033'],
    citation_text: 'BEDTools: a flexible suite of utilities for comparing genomic features.',
  },
  bedtools_genomecoveragebed: {
    name: 'bedtools_genomecoveragebed',
    display_name: 'BEDTools Genome Coverage',
    category: 'genomics',
    description: 'Compute genome-wide coverage from BAM or interval files with bedtools genomecov.',
    search_aliases: ['Galaxy', 'bedtools', 'genomecov', 'genome coverage', 'bedgraph'],
    input: {
      required: {
        input_type: { type: 'STRING', default: 'bed', options: ['bed', 'bam'] },
        input: { type: 'FILE' },
        report: { type: 'STRING', default: 'bg', options: ['bg', 'hist'] },
      },
    },
    output: ['BEDGRAPH', 'TSV'],
    output_name: ['genome_coverage_bedgraph', 'genome_coverage_histogram'],
    required_executables: ['bedtools'],
    required_conda_packages: ['bedtools'],
    documentation_url: 'https://bedtools.readthedocs.io/en/latest/content/tools/genomecov.html',
    citation_dois: ['10.1093/bioinformatics/btq033'],
    citation_urls: ['https://doi.org/10.1093/bioinformatics/btq033'],
    citation_text: 'BEDTools: a flexible suite of utilities for comparing genomic features.',
  },
  bedtools_subtractbed: {
    name: 'bedtools_subtractbed',
    display_name: 'BEDTools Subtract',
    category: 'genomics',
    description: 'Remove intervals or overlapping bases from one feature set using bedtools subtract.',
    search_aliases: ['Galaxy', 'bedtools', 'subtract', 'subtractbed', 'interval subtraction', 'blacklist'],
    input: {
      required: {
        inputA: { type: 'BED' },
        inputB: { type: 'BED' },
      },
    },
    output: ['BED'],
    output_name: ['subtracted'],
    required_executables: ['bedtools'],
    required_conda_packages: ['bedtools'],
    documentation_url: 'https://bedtools.readthedocs.io/en/latest/content/tools/subtract.html',
    citation_dois: ['10.1093/bioinformatics/btq033'],
    citation_urls: ['https://doi.org/10.1093/bioinformatics/btq033'],
    citation_text: 'BEDTools: a flexible suite of utilities for comparing genomic features.',
  },
  bedtools_mergebed: {
    name: 'bedtools_mergebed',
    display_name: 'BEDTools Merge',
    category: 'genomics',
    description: 'Combine overlapping or nearby intervals into flattened regions with optional column summaries.',
    search_aliases: ['Galaxy', 'bedtools', 'merge', 'mergebed', 'combine intervals', 'flatten intervals'],
    input: {
      required: {
        input: { type: 'FILE' },
        distance: { type: 'INT', default: 0 },
      },
    },
    output: ['BED'],
    output_name: ['merged'],
    required_executables: ['mergeBed'],
    required_conda_packages: ['bedtools'],
    documentation_url: 'https://bedtools.readthedocs.io/en/latest/content/tools/merge.html',
    citation_dois: ['10.1093/bioinformatics/btq033'],
    citation_urls: ['https://doi.org/10.1093/bioinformatics/btq033'],
    citation_text: 'BEDTools: a flexible suite of utilities for comparing genomic features.',
  },
  bedtools_sortbed: {
    name: 'bedtools_sortbed',
    display_name: 'BEDTools Sort',
    category: 'genomics',
    description: 'Order BED, GFF, VCF, or bedGraph intervals by coordinate, size, score, or a genome file.',
    search_aliases: ['Galaxy', 'bedtools', 'sort', 'sortbed', 'coordinate sort', 'genome order'],
    input: {
      required: {
        input: { type: 'FILE' },
      },
    },
    output: ['BED'],
    output_name: ['sorted_intervals'],
    required_executables: ['sortBed'],
    required_conda_packages: ['bedtools'],
    documentation_url: 'https://bedtools.readthedocs.io/en/latest/content/tools/sort.html',
    citation_dois: ['10.1093/bioinformatics/btq033'],
    citation_urls: ['https://doi.org/10.1093/bioinformatics/btq033'],
    citation_text: 'BEDTools: a flexible suite of utilities for comparing genomic features.',
  },
  bedtools_getfastabed: {
    name: 'bedtools_getfastabed',
    display_name: 'BEDTools getfasta',
    category: 'genomics',
    description: 'Extract sequences from a FASTA file using BED, GFF, VCF, or bedGraph intervals.',
    search_aliases: ['Galaxy', 'bedtools', 'getfasta', 'getfastabed', 'extract sequence', 'fasta intervals'],
    input: {
      required: {
        input: { type: 'BED' },
        fasta: { type: 'FASTA' },
      },
    },
    output: ['FASTA', 'TSV'],
    output_name: ['extracted_fasta', 'extracted_tsv'],
    required_executables: ['bedtools'],
    required_conda_packages: ['bedtools'],
    documentation_url: 'https://bedtools.readthedocs.io/en/latest/content/tools/getfasta.html',
    citation_dois: ['10.1093/bioinformatics/btq033'],
    citation_urls: ['https://doi.org/10.1093/bioinformatics/btq033'],
    citation_text: 'BEDTools: a flexible suite of utilities for comparing genomic features.',
  },
  bedtools_complementbed: {
    name: 'bedtools_complementbed',
    display_name: 'BEDTools Complement',
    category: 'genomics',
    description: 'Extract genome intervals not represented by an interval file using bedtools complement.',
    search_aliases: ['Galaxy', 'bedtools', 'complement', 'complementbed', 'genome gaps', 'uncovered intervals'],
    input: {
      required: {
        input: { type: 'BED' },
        genome: { type: 'TSV' },
      },
    },
    output: ['BED'],
    output_name: ['complement'],
    required_executables: ['complementBed'],
    required_conda_packages: ['bedtools'],
    documentation_url: 'https://bedtools.readthedocs.io/en/latest/content/tools/complement.html',
    citation_dois: ['10.1093/bioinformatics/btq033'],
    citation_urls: ['https://doi.org/10.1093/bioinformatics/btq033'],
    citation_text: 'BEDTools: a flexible suite of utilities for comparing genomic features.',
  },
  bedtools_flankbed: {
    name: 'bedtools_flankbed',
    display_name: 'BEDTools Flank',
    category: 'genomics',
    description: 'Create new intervals from the flanks of existing intervals with bedtools flank.',
    search_aliases: ['Galaxy', 'bedtools', 'flank', 'flankbed', 'upstream', 'downstream'],
    input: {
      required: {
        input: { type: 'BED' },
        genome: { type: 'TSV' },
      },
    },
    output: ['BED'],
    output_name: ['flanks'],
    required_executables: ['flankBed'],
    required_conda_packages: ['bedtools'],
    documentation_url: 'https://bedtools.readthedocs.io/en/latest/content/tools/flank.html',
    citation_dois: ['10.1093/bioinformatics/btq033'],
    citation_urls: ['https://doi.org/10.1093/bioinformatics/btq033'],
    citation_text: 'BEDTools: a flexible suite of utilities for comparing genomic features.',
  },
  bedtools_slopbed: {
    name: 'bedtools_slopbed',
    display_name: 'BEDTools Slop',
    category: 'genomics',
    description: 'Adjust interval sizes with bedtools slop while clipping to chromosome boundaries.',
    search_aliases: ['Galaxy', 'bedtools', 'slop', 'slopbed', 'extend intervals', 'resize intervals'],
    input: {
      required: {
        inputA: { type: 'BED' },
        genome: { type: 'TSV' },
      },
    },
    output: ['BED'],
    output_name: ['slopped'],
    required_executables: ['bedtools'],
    required_conda_packages: ['bedtools'],
    documentation_url: 'https://bedtools.readthedocs.io/en/latest/content/tools/slop.html',
    citation_dois: ['10.1093/bioinformatics/btq033'],
    citation_urls: ['https://doi.org/10.1093/bioinformatics/btq033'],
    citation_text: 'BEDTools: a flexible suite of utilities for comparing genomic features.',
  },
  bedtools_windowbed: {
    name: 'bedtools_windowbed',
    display_name: 'BEDTools Window',
    category: 'genomics',
    description: 'Find intervals in B that overlap a window around each interval in A.',
    search_aliases: ['Galaxy', 'bedtools', 'window', 'windowbed', 'nearby intervals', 'proximal features'],
    input: {
      required: {
        inputA: { type: 'FILE' },
        inputB: { type: 'BED' },
      },
    },
    output: ['BED'],
    output_name: ['window_matches'],
    required_executables: ['bedtools'],
    required_conda_packages: ['bedtools'],
    documentation_url: 'https://bedtools.readthedocs.io/en/latest/content/tools/window.html',
    citation_dois: ['10.1093/bioinformatics/btq033'],
    citation_urls: ['https://doi.org/10.1093/bioinformatics/btq033'],
    citation_text: 'BEDTools: a flexible suite of utilities for comparing genomic features.',
  },
  bedtools_map: {
    name: 'bedtools_map',
    display_name: 'BEDTools Map',
    category: 'genomics',
    description: 'Apply summary operations to columns from B intervals that overlap each A interval.',
    search_aliases: ['Galaxy', 'bedtools', 'map', 'mapbed', 'interval statistics', 'overlap summary'],
    input: {
      required: {
        inputA: { type: 'BED' },
        inputB: { type: 'BED' },
        columns: { type: 'STRING', default: '5' },
        operations: { type: 'STRING', default: 'mean' },
      },
    },
    output: ['BED'],
    output_name: ['mapped'],
    required_executables: ['bedtools'],
    required_conda_packages: ['bedtools'],
    documentation_url: 'https://bedtools.readthedocs.io/en/latest/content/tools/map.html',
    citation_dois: ['10.1093/bioinformatics/btq033'],
    citation_urls: ['https://doi.org/10.1093/bioinformatics/btq033'],
    citation_text: 'BEDTools: a flexible suite of utilities for comparing genomic features.',
  },
  bedtools_multiintersectbed: {
    name: 'bedtools_multiintersectbed',
    display_name: 'BEDTools Multiple Intersect',
    category: 'genomics',
    description: 'Identify common intervals among multiple sorted interval files with bedtools multiinter.',
    search_aliases: ['Galaxy', 'bedtools', 'multiinter', 'multiintersect', 'multiple intersect', 'shared intervals'],
    input: {
      required: {
        inputs: { type: 'BED_LIST' },
      },
    },
    output: ['BED'],
    output_name: ['multiintersect'],
    required_executables: ['bedtools'],
    required_conda_packages: ['bedtools'],
    documentation_url: 'https://bedtools.readthedocs.io/en/latest/content/tools/multiinter.html',
    citation_dois: ['10.1093/bioinformatics/btq033'],
    citation_urls: ['https://doi.org/10.1093/bioinformatics/btq033'],
    citation_text: 'BEDTools: a flexible suite of utilities for comparing genomic features.',
  },
  bedtools_clusterbed: {
    name: 'bedtools_clusterbed',
    display_name: 'BEDTools Cluster',
    category: 'genomics',
    description: 'Cluster overlapping or nearby sorted intervals without flattening them.',
    search_aliases: ['Galaxy', 'bedtools', 'cluster', 'clusterbed', 'overlap clusters', 'nearby intervals'],
    input: {
      required: {
        inputA: { type: 'BED' },
      },
    },
    output: ['BED'],
    output_name: ['clustered'],
    required_executables: ['bedtools'],
    required_conda_packages: ['bedtools'],
    documentation_url: 'https://bedtools.readthedocs.io/en/latest/content/tools/cluster.html',
    citation_dois: ['10.1093/bioinformatics/btq033'],
    citation_urls: ['https://doi.org/10.1093/bioinformatics/btq033'],
    citation_text: 'BEDTools: a flexible suite of utilities for comparing genomic features.',
  },
  bedtools_jaccard: {
    name: 'bedtools_jaccard',
    display_name: 'BEDTools Jaccard',
    category: 'genomics',
    description: 'Calculate intersection, union, Jaccard similarity, and intersection counts for two sorted interval sets.',
    search_aliases: ['Galaxy', 'bedtools', 'jaccard', 'jaccardbed', 'interval similarity', 'set overlap'],
    input: {
      required: {
        inputA: { type: 'BED' },
        inputB: { type: 'BED' },
      },
    },
    output: ['TSV'],
    output_name: ['jaccard'],
    required_executables: ['bedtools'],
    required_conda_packages: ['bedtools'],
    documentation_url: 'https://bedtools.readthedocs.io/en/latest/content/tools/jaccard.html',
    citation_dois: ['10.1093/bioinformatics/btq033'],
    citation_urls: ['https://doi.org/10.1093/bioinformatics/btq033'],
    citation_text: 'BEDTools: a flexible suite of utilities for comparing genomic features.',
  },
  bedtools_fisher: {
    name: 'bedtools_fisher',
    display_name: 'BEDTools Fisher',
    category: 'genomics',
    description: "Calculate Fisher's exact test statistics for overlaps between two feature files.",
    search_aliases: ['Galaxy', 'bedtools', 'fisher', 'fisherbed', 'overlap significance', 'exact test'],
    input: {
      required: {
        inputA: { type: 'BED' },
        inputB: { type: 'BED' },
        genome: { type: 'TSV' },
      },
    },
    output: ['STATS_FILE'],
    output_name: ['fisher'],
    required_executables: ['bedtools'],
    required_conda_packages: ['bedtools'],
    documentation_url: 'https://bedtools.readthedocs.io/en/latest/content/tools/fisher.html',
    citation_dois: ['10.1093/bioinformatics/btq033'],
    citation_urls: ['https://doi.org/10.1093/bioinformatics/btq033'],
    citation_text: 'BEDTools: a flexible suite of utilities for comparing genomic features.',
  },
  bedtools_reldistbed: {
    name: 'bedtools_reldistbed',
    display_name: 'BEDTools Relative Distance',
    category: 'genomics',
    description: 'Calculate the relative distance distribution between intervals in two feature sets.',
    search_aliases: ['Galaxy', 'bedtools', 'reldist', 'reldistbed', 'relative distance', 'spatial correlation'],
    input: {
      required: {
        inputA: { type: 'BED' },
        inputB: { type: 'BED' },
      },
    },
    output: ['TSV'],
    output_name: ['relative_distance'],
    required_executables: ['bedtools'],
    required_conda_packages: ['bedtools'],
    documentation_url: 'https://bedtools.readthedocs.io/en/latest/content/tools/reldist.html',
    citation_dois: ['10.1093/bioinformatics/btq033', '10.1371/journal.pcbi.1002529'],
    citation_urls: ['https://doi.org/10.1093/bioinformatics/btq033', 'https://doi.org/10.1371/journal.pcbi.1002529'],
    citation_text: 'BEDTools: a flexible suite of utilities for comparing genomic features; Exploring Massive, Genome Scale Datasets with the GenometriCorr Package.',
  },
  bedtools_spacingbed: {
    name: 'bedtools_spacingbed',
    display_name: 'BEDTools Spacing',
    category: 'genomics',
    description: 'Report the spacing between adjacent intervals in a sorted interval file.',
    search_aliases: ['Galaxy', 'bedtools', 'spacing', 'spacingbed', 'distance between intervals', 'adjacent intervals'],
    input: {
      required: {
        input: { type: 'BED' },
      },
    },
    output: ['BED'],
    output_name: ['spacing'],
    required_executables: ['bedtools'],
    required_conda_packages: ['bedtools'],
    documentation_url: 'https://bedtools.readthedocs.io/en/latest/content/tools/spacing.html',
    citation_dois: ['10.1093/bioinformatics/btq033'],
    citation_urls: ['https://doi.org/10.1093/bioinformatics/btq033'],
    citation_text: 'BEDTools: a flexible suite of utilities for comparing genomic features.',
  },
  bedtools_groupbybed: {
    name: 'bedtools_groupbybed',
    display_name: 'BEDTools GroupBy',
    category: 'genomics',
    description: 'Group intervals by one or more columns and summarize selected columns with bedtools groupby.',
    search_aliases: ['Galaxy', 'bedtools', 'groupby', 'groupbybed', 'summarize intervals', 'aggregate columns'],
    input: {
      required: {
        inputA: { type: 'BED' },
        columns: { type: 'STRING', default: '4' },
        group: { type: 'STRING', default: '1,2,3' },
        operation: { type: 'STRING', default: 'sum' },
      },
    },
    output: ['BED'],
    output_name: ['grouped'],
    required_executables: ['bedtools'],
    required_conda_packages: ['bedtools'],
    documentation_url: 'https://bedtools.readthedocs.io/en/latest/content/tools/groupby.html',
    citation_dois: ['10.1093/bioinformatics/btq033'],
    citation_urls: ['https://doi.org/10.1093/bioinformatics/btq033'],
    citation_text: 'BEDTools: a flexible suite of utilities for comparing genomic features.',
  },
  samtools_idxstats: {
    name: 'samtools_idxstats',
    display_name: 'Samtools Idxstats',
    category: 'samtools',
    description: 'Report mapped and unmapped read counts per reference sequence from a BAM or CRAM index.',
    search_aliases: ['Galaxy', 'samtools', 'idxstats', 'index stats', 'BAM index', 'MultiQC'],
    input: {
      required: {
        input: { type: 'BAM' },
        threads: { type: 'INT', default: 1 },
      },
    },
    output: ['TSV'],
    output_name: ['idxstats'],
    required_executables: ['samtools'],
    required_conda_packages: ['samtools'],
    documentation_url: 'https://www.htslib.org/doc/samtools-idxstats.html',
    citation_dois: ['10.1093/gigascience/giab008', '10.1093/bioinformatics/btp352'],
    citation_urls: ['https://doi.org/10.1093/gigascience/giab008', 'https://doi.org/10.1093/bioinformatics/btp352'],
    citation_text: 'Twelve years of SAMtools and BCFtools; The Sequence Alignment/Map format and SAMtools.',
  },
  samtools_depth: {
    name: 'samtools_depth',
    display_name: 'Samtools Depth',
    category: 'samtools',
    description: 'Compute per-position alignment depth for one or more BAM files, optionally restricted to regions.',
    search_aliases: ['Galaxy', 'samtools', 'depth', 'coverage depth', 'per-base coverage'],
    input: {
      required: {
        input_bams: { type: 'BAM_LIST' },
      },
    },
    output: ['TSV'],
    output_name: ['depth'],
    required_executables: ['samtools'],
    required_conda_packages: ['samtools'],
    documentation_url: 'https://www.htslib.org/doc/samtools-depth.html',
    citation_dois: ['10.1093/gigascience/giab008', '10.1093/bioinformatics/btp352'],
    citation_urls: ['https://doi.org/10.1093/gigascience/giab008', 'https://doi.org/10.1093/bioinformatics/btp352'],
    citation_text: 'Twelve years of SAMtools and BCFtools; The Sequence Alignment/Map format and SAMtools.',
  },
  samtools_faidx: {
    name: 'samtools_faidx',
    display_name: 'Samtools Faidx',
    category: 'samtools',
    description: 'Create a FASTA/FASTQ fai index, with fallback handling for gzip-compressed inputs.',
    search_aliases: ['Galaxy', 'samtools', 'faidx', 'FASTA index', 'FASTQ index', 'fai'],
    input: {
      required: {
        input: { type: 'FASTA' },
      },
    },
    output: ['TSV'],
    output_name: ['fai_index'],
    required_executables: ['samtools'],
    required_conda_packages: ['samtools'],
    documentation_url: 'https://www.htslib.org/doc/samtools-faidx.html',
    citation_dois: ['10.1093/gigascience/giab008', '10.1093/bioinformatics/btp352'],
    citation_urls: ['https://doi.org/10.1093/gigascience/giab008', 'https://doi.org/10.1093/bioinformatics/btp352'],
    citation_text: 'Twelve years of SAMtools and BCFtools; The Sequence Alignment/Map format and SAMtools.',
  },
  samtools_coverage: {
    name: 'samtools_coverage',
    display_name: 'Samtools Coverage',
    category: 'samtools',
    description: 'Compute tabular or histogram coverage summaries per reference sequence using samtools coverage.',
    search_aliases: ['Galaxy', 'samtools', 'coverage', 'histogram', 'BAM coverage'],
    input: {
      required: {
        input: { type: 'BAM' },
      },
    },
    output: ['TSV'],
    output_name: ['coverage'],
    required_executables: ['samtools'],
    required_conda_packages: ['samtools'],
    documentation_url: 'https://www.htslib.org/doc/samtools-coverage.html',
    citation_dois: ['10.1093/gigascience/giab008', '10.1093/bioinformatics/btp352'],
    citation_urls: ['https://doi.org/10.1093/gigascience/giab008', 'https://doi.org/10.1093/bioinformatics/btp352'],
    citation_text: 'Twelve years of SAMtools and BCFtools; The Sequence Alignment/Map format and SAMtools.',
  },
  samtools_bedcov: {
    name: 'samtools_bedcov',
    display_name: 'Samtools Bedcov',
    category: 'samtools',
    description: 'Calculate read depth totals for BED intervals across one or more BAM files.',
    search_aliases: ['Galaxy', 'samtools', 'bedcov', 'interval coverage', 'BED coverage'],
    input: {
      required: {
        input_bed: { type: 'BED' },
        input_bams: { type: 'BAM_LIST' },
      },
    },
    output: ['TSV'],
    output_name: ['interval_coverage'],
    required_executables: ['samtools'],
    required_conda_packages: ['samtools'],
    documentation_url: 'https://www.htslib.org/doc/samtools-bedcov.html',
    citation_dois: ['10.1093/gigascience/giab008', '10.1093/bioinformatics/btr076'],
    citation_urls: ['https://doi.org/10.1093/gigascience/giab008', 'https://doi.org/10.1093/bioinformatics/btr076'],
    citation_text: 'Twelve years of SAMtools and BCFtools; Improving SNP discovery by Base Alignment Quality.',
  },
  samtools_calmd: {
    name: 'samtools_calmd',
    display_name: 'Samtools Calmd',
    category: 'samtools',
    description: 'Recalculate MD and NM tags against a reference FASTA, optionally adding BAQ-adjusted qualities.',
    search_aliases: ['Galaxy', 'samtools', 'calmd', 'MD tags', 'NM tags', 'BAQ'],
    input: {
      required: {
        input: { type: 'BAM' },
        reference: { type: 'FASTA' },
        threads: { type: 'INT', default: 1 },
      },
    },
    output: ['BAM'],
    output_name: ['calmd_bam'],
    required_executables: ['samtools'],
    required_conda_packages: ['samtools'],
    documentation_url: 'https://www.htslib.org/doc/samtools-calmd.html',
    citation_dois: ['10.1093/gigascience/giab008', '10.1093/bioinformatics/btr076'],
    citation_urls: ['https://doi.org/10.1093/gigascience/giab008', 'https://doi.org/10.1093/bioinformatics/btr076'],
    citation_text: 'Twelve years of SAMtools and BCFtools; Improving SNP discovery by Base Alignment Quality.',
  },
  samtools_ampliconclip: {
    name: 'samtools_ampliconclip',
    display_name: 'Samtools Ampliconclip',
    category: 'samtools',
    description: 'Clip primer bases from amplicon BAM files and re-sort alignments for downstream analysis.',
    search_aliases: ['Galaxy', 'samtools', 'ampliconclip', 'primer trimming', 'amplicon'],
    input: {
      required: {
        input_bed: { type: 'BED' },
        input_bam: { type: 'BAM' },
        threads: { type: 'INT', default: 1 },
      },
    },
    output: ['BAM', 'BEDGRAPH'],
    output_name: ['clipped_bam', 'primer_counts'],
    required_executables: ['samtools'],
    required_conda_packages: ['samtools'],
    documentation_url: 'https://www.htslib.org/doc/samtools-ampliconclip.html',
    citation_dois: ['10.1093/gigascience/giab008', '10.1093/bioinformatics/btr076'],
    citation_urls: ['https://doi.org/10.1093/gigascience/giab008', 'https://doi.org/10.1093/bioinformatics/btr076'],
    citation_text: 'Twelve years of SAMtools and BCFtools; Improving SNP discovery by Base Alignment Quality.',
  },
  samtools_fastx: {
    name: 'samtools_fastx',
    display_name: 'Samtools Fastx',
    category: 'samtools',
    description: 'Extract FASTA or FASTQ reads from alignment files, with optional read-pair and index-read outputs.',
    search_aliases: ['Galaxy', 'samtools', 'fastx', 'bam2fq', 'FASTQ extraction'],
    input: {
      required: {
        input: { type: 'BAM' },
        threads: { type: 'INT', default: 1 },
      },
    },
    output: ['FILE', 'FILE', 'FILE', 'FILE', 'FILE', 'FILE', 'FILE'],
    output_name: ['reads', 'read1', 'read2', 'singletons', 'nonspecific', 'index1', 'index2'],
    required_executables: ['samtools'],
    required_conda_packages: ['samtools'],
    documentation_url: 'https://www.htslib.org/doc/samtools-fasta.html',
    citation_dois: ['10.1093/gigascience/giab008', '10.1093/bioinformatics/btr076'],
    citation_urls: ['https://doi.org/10.1093/gigascience/giab008', 'https://doi.org/10.1093/bioinformatics/btr076'],
    citation_text: 'Twelve years of SAMtools and BCFtools; Improving SNP discovery by Base Alignment Quality.',
  },
  samtools_mpileup: {
    name: 'samtools_mpileup',
    display_name: 'Samtools Mpileup',
    category: 'samtools',
    description: 'Generate pileup format text for one or more BAM files using samtools mpileup.',
    search_aliases: ['Galaxy', 'samtools', 'mpileup', 'pileup', 'BAQ'],
    input: {
      required: {
        input_bams: { type: 'BAM_LIST' },
        reference: { type: 'FASTA' },
      },
    },
    output: ['FILE'],
    output_name: ['pileup'],
    required_executables: ['samtools'],
    required_conda_packages: ['samtools'],
    documentation_url: 'https://www.htslib.org/doc/samtools-mpileup.html',
    citation_dois: ['10.1093/gigascience/giab008', '10.1093/bioinformatics/btr076'],
    citation_urls: ['https://doi.org/10.1093/gigascience/giab008', 'https://doi.org/10.1093/bioinformatics/btr076'],
    citation_text: 'Twelve years of SAMtools and BCFtools; Improving SNP discovery by Base Alignment Quality.',
  },
  samtools_reheader: {
    name: 'samtools_reheader',
    display_name: 'Samtools Reheader',
    category: 'samtools',
    description: 'Replace the header of a BAM file using a SAM or BAM source header.',
    search_aliases: ['Galaxy', 'samtools', 'reheader', 'SAM header', 'BAM header'],
    input: {
      required: {
        input_header: { type: 'BAM' },
        input_file: { type: 'BAM' },
      },
    },
    output: ['BAM'],
    output_name: ['reheadered_bam'],
    required_executables: ['samtools'],
    required_conda_packages: ['samtools'],
    documentation_url: 'https://www.htslib.org/doc/samtools-reheader.html',
    citation_dois: ['10.1093/gigascience/giab008', '10.1093/bioinformatics/btr076'],
    citation_urls: ['https://doi.org/10.1093/gigascience/giab008', 'https://doi.org/10.1093/bioinformatics/btr076'],
    citation_text: 'Twelve years of SAMtools and BCFtools; Improving SNP discovery by Base Alignment Quality.',
  },
  samtools_split: {
    name: 'samtools_split',
    display_name: 'Samtools Split',
    category: 'samtools',
    description: 'Split a BAM file into separate BAM files by read group.',
    search_aliases: ['Galaxy', 'samtools', 'split', 'read groups', 'readgroup'],
    input: {
      required: {
        input_bam: { type: 'BAM' },
        threads: { type: 'INT', default: 1 },
      },
    },
    output: ['DIRECTORY'],
    output_name: ['readgroup_bams'],
    required_executables: ['samtools'],
    required_conda_packages: ['samtools'],
    documentation_url: 'https://www.htslib.org/doc/samtools-split.html',
    citation_dois: ['10.1093/gigascience/giab008', '10.1093/bioinformatics/btr076'],
    citation_urls: ['https://doi.org/10.1093/gigascience/giab008', 'https://doi.org/10.1093/bioinformatics/btr076'],
    citation_text: 'Twelve years of SAMtools and BCFtools; Improving SNP discovery by Base Alignment Quality.',
  },
  samtools_slice_bam: {
    name: 'samtools_slice_bam',
    display_name: 'Samtools Slice BAM',
    category: 'samtools',
    description: 'Slice an indexed BAM to BED intervals, contigs, or manually supplied genomic regions.',
    search_aliases: ['Galaxy', 'samtools', 'slice', 'regions', 'BED slice'],
    input: {
      required: {
        input_bam: { type: 'BAM' },
        slice_method: { type: 'STRING', default: 'bed', options: ['bed', 'chromosomes', 'manual'] },
        threads: { type: 'INT', default: 1 },
      },
    },
    output: ['BAM'],
    output_name: ['sliced_bam'],
    required_executables: ['samtools'],
    required_conda_packages: ['samtools'],
    documentation_url: 'https://www.htslib.org/doc/samtools-view.html',
    citation_dois: ['10.1093/gigascience/giab008', '10.1093/bioinformatics/btr076'],
    citation_urls: ['https://doi.org/10.1093/gigascience/giab008', 'https://doi.org/10.1093/bioinformatics/btr076'],
    citation_text: 'Twelve years of SAMtools and BCFtools; Improving SNP discovery by Base Alignment Quality.',
  },
  samtools_phase: {
    name: 'samtools_phase',
    display_name: 'Samtools Phase',
    category: 'samtools',
    description: 'Call and phase heterozygous SNPs, producing phase-set logs and phased BAM outputs.',
    search_aliases: ['Galaxy', 'samtools', 'phase', 'heterozygous SNPs', 'phasing'],
    input: {
      required: {
        input_bam: { type: 'BAM' },
      },
    },
    output: ['STATS_FILE', 'BAM', 'BAM', 'BAM'],
    output_name: ['phase_sets', 'phase0', 'phase1', 'chimera'],
    required_executables: ['samtools'],
    required_conda_packages: ['samtools'],
    documentation_url: 'https://www.htslib.org/doc/samtools-phase.html',
    citation_dois: ['10.1093/gigascience/giab008', '10.1093/bioinformatics/btr076'],
    citation_urls: ['https://doi.org/10.1093/gigascience/giab008', 'https://doi.org/10.1093/bioinformatics/btr076'],
    citation_text: 'Twelve years of SAMtools and BCFtools; Improving SNP discovery by Base Alignment Quality.',
  },
};

test.beforeEach(async ({ context, page }) => {
  await context.addInitScript(() => {
    window.localStorage.setItem('bionodulo.language', 'en');
    window.localStorage.setItem('bionodulo.settings', JSON.stringify({
      'bionodulo.getting_started.dismissed': true,
      'bionodulo.getting_started.show_on_startup': false,
    }));
  });

  await page.route(url => url.pathname.startsWith('/api/'), async route => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    let payload: unknown = {};

    if (path.endsWith('/api/object_info')) {
      payload = objectInfo;
    } else if (path.endsWith('/api/settings')) {
      payload = {
        'bionodulo.getting_started.dismissed': true,
        'bionodulo.getting_started.show_on_startup': false,
      };
    } else if (path.endsWith('/api/host_status')) {
      payload = {
        ready: true,
        checks: {},
        missing_required: [],
        missing_optional: [],
        message: 'ready',
      };
    } else if (path.endsWith('/api/queue')) {
      payload = { pending: [], running: null };
    } else if (path.endsWith('/api/history')) {
      payload = { history: [] };
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(payload),
    });
  });
});

test('node library exposes advanced gap-analysis node families from object_info', async ({ page }) => {
  await page.goto('/', { waitUntil: 'domcontentloaded' });

  await page.getByRole('button', { name: /^Nodes/ }).click();
  await expect(page.getByText('55 nodes available')).toBeVisible();

  const search = page.getByRole('combobox', { name: 'Search nodes' });
  const expectedNodes = [
    { query: 'flow control', name: 'If Condition', category: 'flow_control' },
    { query: 'data transform', name: 'Filter Rows', category: 'data_transform' },
    { query: 'REST API', name: 'HTTP Request', category: 'api' },
    { query: 'database', name: 'AlphaFold DB', category: 'databases' },
    { query: 'mmseqs2', name: 'ColabFold Batch', category: 'ai' },
    { query: 'single sequence', name: 'ESMFold Predict', category: 'ai' },
    { query: 'inverse folding', name: 'ProteinMPNN Design', category: 'ai' },
    { query: 'HPRC', name: 'Minigraph-Cactus', category: 'pangenomics' },
    { query: 'nanopore', name: 'Clair3', category: 'variant' },
    { query: 'sage-proteomics', name: 'Sage Search', category: 'proteomics' },
    { query: 'proteomics workflow', name: 'FragPipe Workflow', category: 'proteomics' },
    { query: 'language model', name: 'LLM Prompt', category: 'ai' },
    { query: 'schedule', name: 'Workflow Trigger', category: 'workflow' },
    { query: 'busco completeness', name: 'BUSCO', category: 'assembly' },
    { query: 'diamond blastx', name: 'DIAMOND Align', category: 'alignment' },
    { query: 'htseq gene counts', name: 'HTSeq-count', category: 'rna_seq' },
    { query: 'hmmer pfam', name: 'HMMER hmmscan', category: 'annotation' },
    { query: 'mmseqs easy-search', name: 'MMseqs2 Easy Search', category: 'alignment' },
    { query: 'mash dist', name: 'Mash Dist', category: 'genomics' },
    { query: 'average nucleotide identity', name: 'FastANI', category: 'genomics' },
    { query: 'lofreq low frequency variants', name: 'LoFreq Call', category: 'variant' },
    { query: 'ivar viral variants', name: 'iVar Variants', category: 'variant' },
    { query: 'gtdbtk taxonomy', name: 'GTDB-Tk Classify', category: 'taxonomy' },
    { query: 'rseqc strandedness', name: 'RSeQC Infer Experiment', category: 'rna_seq' },
    { query: 'bedtools coverage', name: 'BEDTools Coverage', category: 'genomics' },
    { query: 'genome coverage bedgraph', name: 'BEDTools Genome Coverage', category: 'genomics' },
    { query: 'subtractbed', name: 'BEDTools Subtract', category: 'genomics' },
    { query: 'mergebed', name: 'BEDTools Merge', category: 'genomics' },
    { query: 'sortbed', name: 'BEDTools Sort', category: 'genomics' },
    { query: 'getfasta', name: 'BEDTools getfasta', category: 'genomics' },
    { query: 'complementbed', name: 'BEDTools Complement', category: 'genomics' },
    { query: 'flankbed', name: 'BEDTools Flank', category: 'genomics' },
    { query: 'slopbed', name: 'BEDTools Slop', category: 'genomics' },
    { query: 'windowbed', name: 'BEDTools Window', category: 'genomics' },
    { query: 'mapbed', name: 'BEDTools Map', category: 'genomics' },
    { query: 'multiintersect', name: 'BEDTools Multiple Intersect', category: 'genomics' },
    { query: 'clusterbed', name: 'BEDTools Cluster', category: 'genomics' },
    { query: 'jaccardbed', name: 'BEDTools Jaccard', category: 'genomics' },
    { query: 'fisherbed', name: 'BEDTools Fisher', category: 'genomics' },
    { query: 'reldistbed', name: 'BEDTools Relative Distance', category: 'genomics' },
    { query: 'spacingbed', name: 'BEDTools Spacing', category: 'genomics' },
    { query: 'groupbybed', name: 'BEDTools GroupBy', category: 'genomics' },
    { query: 'samtools idxstats multiqc', name: 'Samtools Idxstats', category: 'samtools' },
    { query: 'samtools depth', name: 'Samtools Depth', category: 'samtools' },
    { query: 'samtools faidx', name: 'Samtools Faidx', category: 'samtools' },
    { query: 'samtools coverage', name: 'Samtools Coverage', category: 'samtools' },
    { query: 'bedcov', name: 'Samtools Bedcov', category: 'samtools' },
    { query: 'calmd', name: 'Samtools Calmd', category: 'samtools' },
    { query: 'ampliconclip', name: 'Samtools Ampliconclip', category: 'samtools' },
    { query: 'fastx', name: 'Samtools Fastx', category: 'samtools' },
    { query: 'mpileup', name: 'Samtools Mpileup', category: 'samtools' },
    { query: 'reheader', name: 'Samtools Reheader', category: 'samtools' },
    { query: 'readgroup', name: 'Samtools Split', category: 'samtools' },
    { query: 'slice', name: 'Samtools Slice BAM', category: 'samtools' },
    { query: 'phase', name: 'Samtools Phase', category: 'samtools' },
  ];

  for (const node of expectedNodes) {
    await search.fill(node.query);
    await expect(page.getByText(/\d+ match(?:es)?/)).toBeVisible();
    await expect(page.getByTitle(`Add ${node.name}`)).toBeVisible();
    await expect(page.getByText(node.category).first()).toBeVisible();
  }

  await search.fill('language model');
  await page.getByTitle('Add LLM Prompt').click();
  await expect(page.getByRole('status')).toContainText('1');
  await expect(page.locator('.workflow-stats-cat', { hasText: 'ai' })).toBeVisible();
});

test('Galaxy parity nodes render citation metadata in node info', async ({ page }) => {
  await page.goto('/', { waitUntil: 'domcontentloaded' });

  const canvas = page.locator('canvas').first();
  const canvasBox = await canvas.boundingBox();
  expect(canvasBox).not.toBeNull();
  const nodePoint = {
    x: canvasBox!.x + Math.min(320, canvasBox!.width / 2),
    y: canvasBox!.y + Math.min(220, canvasBox!.height / 2),
  };

  await page.mouse.click(nodePoint.x, nodePoint.y, { button: 'right' });
  await page.getByText('Add Node').click();
  const search = page.getByRole('combobox', { name: 'Search nodes' });
  await search.fill('diamond blastx');
  await page.getByTitle('Add DIAMOND Align').click();

  await expect(page.getByRole('status')).toContainText('1');
  await page.mouse.click(nodePoint.x + 80, nodePoint.y + 30, { button: 'right' });
  await page.getByText('Node Info').click();

  const infoPanel = page.locator('.node-editor').last();
  await expect(infoPanel.getByText('DIAMOND Align')).toBeVisible();
  await expect(infoPanel.getByText('DOI', { exact: true })).toBeVisible();
  await expect(infoPanel.getByText('10.1038/s41592-021-01101-x', { exact: true })).toBeVisible();
  await expect(infoPanel.getByRole('link', { name: 'https://doi.org/10.1038/s41592-021-01101-x' })).toBeVisible();
  await expect(infoPanel.getByText('Sensitive protein alignments at tree-of-life scale using DIAMOND.')).toBeVisible();
});
