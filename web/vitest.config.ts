/// <reference types="vitest" />
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import { readFileSync } from 'fs';

// __APP_VERSION__ is injected by vite.config.ts `define` for real builds; the
// test config must supply it too or every component that renders the version
// throws ReferenceError under vitest.
const appVersion = JSON.parse(
  readFileSync(new URL('./package.json', import.meta.url), 'utf-8'),
).version as string;

export default defineConfig({
  plugins: [react()],
  define: { __APP_VERSION__: JSON.stringify(appVersion) },
  test: {
    environment: 'jsdom',
    // Default 5s is too tight for the first cold test on Windows: the i18n
    // locales are ~260 KB combined, and each async test re-imports them.
    // 15s keeps the full suite green on cold Windows runs without slowing
    // the warm path (most tests still complete in <2s).
    testTimeout: 15_000,
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    exclude: ['node_modules', 'dist', 'e2e'],
  },
});
