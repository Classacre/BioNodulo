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
  await expect(page.getByText('22 nodes available')).toBeVisible();

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
