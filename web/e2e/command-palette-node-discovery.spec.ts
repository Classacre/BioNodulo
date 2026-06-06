import { expect, test } from '@playwright/test';

function fillerNode(index: number) {
  return {
    name: `filler_${index}`,
    display_name: `Filler ${index}`,
    category: 'utility',
    description: 'Filler node for command-palette registry ordering.',
    search_aliases: [`filler-${index}`],
    input: {},
    output: ['STRING'],
    output_name: ['value'],
  };
}

const objectInfoWithLateNode = Object.fromEntries([
  ...Array.from({ length: 40 }, (_, index) => [`filler_${index}`, fillerNode(index)]),
  [
    'llm_prompt',
    {
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
  ],
]);

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
      payload = objectInfoWithLateNode;
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

test('command palette can add nodes beyond the first 40 object_info entries', async ({ page }) => {
  await page.goto('/', { waitUntil: 'domcontentloaded' });
  await expect(page.getByRole('button', { name: /Run workflow/ })).toBeVisible();

  await page.keyboard.press('Control+K');
  await expect(page.getByRole('dialog', { name: 'Command palette' })).toBeVisible();

  await page.getByRole('textbox', { name: 'Search commands' }).fill('language model');
  await expect(page.getByRole('option', { name: /Add: LLM Prompt/ })).toBeVisible();

  await page.getByRole('option', { name: /Add: LLM Prompt/ }).click();
  await expect(page.getByRole('status')).toContainText('1');
  await expect(page.locator('.workflow-stats-cat', { hasText: 'ai' })).toBeVisible();
});
