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
  await expect(page.getByText('9 nodes available')).toBeVisible();

  const search = page.getByRole('combobox', { name: 'Search nodes' });
  const expectedNodes = [
    { query: 'flow control', name: 'If Condition', category: 'flow_control' },
    { query: 'data transform', name: 'Filter Rows', category: 'data_transform' },
    { query: 'REST API', name: 'HTTP Request', category: 'api' },
    { query: 'database', name: 'AlphaFold DB', category: 'databases' },
    { query: 'mmseqs2', name: 'ColabFold Batch', category: 'ai' },
    { query: 'single sequence', name: 'ESMFold Predict', category: 'ai' },
    { query: 'inverse folding', name: 'ProteinMPNN Design', category: 'ai' },
    { query: 'language model', name: 'LLM Prompt', category: 'ai' },
    { query: 'schedule', name: 'Workflow Trigger', category: 'workflow' },
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
