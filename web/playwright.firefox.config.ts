import { defineConfig, devices } from '@playwright/test';

// Firefox-only end-to-end config that drives the *production build* served by
// the Python backend (`python main.py`) on port 8000, rather than the Vite dev
// server. This mirrors how a real desktop user runs the app: built `web/dist`
// served by FastAPI.
//
// Start the backend yourself before running:
//   .venv/bin/python main.py --host 127.0.0.1 --port 8000
// then:
//   cd web && npx playwright test --config playwright.firefox.config.ts
//
// The base URL can be overridden with BIONODULO_BASE_URL.
const baseURL = process.env.BIONODULO_BASE_URL ?? 'http://127.0.0.1:8000';

export default defineConfig({
  testDir: './e2e-firefox',
  timeout: 90_000,
  expect: { timeout: 30_000 },
  fullyParallel: false,
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL,
    headless: true,
    viewport: { width: 1440, height: 900 },
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
    },
  ],
  // No webServer: the Python backend is started out-of-band so we don't pull in
  // the Vite dev server (the built dist is what we want to test).
});
