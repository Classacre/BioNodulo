import { defineConfig } from '@playwright/test';

// Exercise the shipped chunks, not Vite's development module graph. No real
// cloud service is called: the parent frame implements the MCP host protocol.
export default defineConfig({
  testDir: '.',
  testMatch: 'mcp-workbench.spec.ts',
  timeout: 45_000,
  workers: 1,
  metadata: { productionMcp: true },
  use: { baseURL: 'http://127.0.0.1:5175', headless: true, viewport: { width: 1280, height: 800 } },
  webServer: [
    { command: 'npm run preview -- --host 127.0.0.1 --port 5175 --strictPort', port: 5175, reuseExistingServer: false, timeout: 30_000 },
    { command: 'node mcp-assets-server.mjs', url: 'http://127.0.0.1:5176/health', reuseExistingServer: false, timeout: 30_000 },
  ],
});
