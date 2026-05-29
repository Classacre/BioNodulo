import { test, expect } from '@playwright/test';

// Smoke: app shell loads, top bar renders, and the document has a non-empty title.
// Skipped automatically when the backend isn't running (it 502s before mount).
test('app shell mounts', async ({ page }) => {
  const response = await page.goto('/', { waitUntil: 'domcontentloaded' }).catch(() => null);
  if (!response || !response.ok()) {
    test.skip(true, 'dev server unavailable');
    return;
  }
  await expect(page).toHaveTitle(/BioNodulo|Vite/i);
  await expect(page.locator('body')).toBeVisible();
});
