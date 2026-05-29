import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { resolve } from 'path';
import { visualizer } from 'rollup-plugin-visualizer';

// Bundle-size analysis: run `npm run build:analyze` to emit `dist/stats.html`.
// The visualizer plugin only loads when BIONODULO_ANALYZE=1 so regular builds
// stay lean.
const analyze = process.env.BIONODULO_ANALYZE === '1';

export default defineConfig({
  // Colab and notebook-hosted environments can expose the app below a path
  // prefix. Relative asset URLs keep the built SPA loadable in both root and
  // proxied deployments.
  base: './',
  plugins: [
    react(),
    ...(analyze
      ? [
          visualizer({
            filename: 'dist/stats.html',
            template: 'treemap',
            gzipSize: true,
            brotliSize: true,
            open: false,
          }) as never,
        ]
      : []),
  ],
  root: '.',
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    rollupOptions: {
      output: {
        // Pull the big runtime libs out of the main bundle so they cache
        // across releases. The expected effect is a ~300 kB drop in the
        // main chunk (react + scheduler + yjs+ystack + fuse + i18next move
        // to their own files).
        manualChunks(id) {
          // Normalise Windows backslashes so the checks work on every OS.
          const p = id.replace(/\\/g, '/');
          if (!p.includes('/node_modules/')) return undefined;
          if (p.includes('/node_modules/react/') ||
              p.includes('/node_modules/react-dom/') ||
              p.includes('/node_modules/scheduler/')) return 'react';
          if (p.includes('/node_modules/yjs/') ||
              p.includes('/node_modules/y-protocols/') ||
              p.includes('/node_modules/y-websocket/') ||
              p.includes('/node_modules/lib0/')) return 'yjs';
          if (p.includes('/node_modules/fuse.js/')) return 'fuse';
          if (p.includes('/node_modules/i18next/') ||
              p.includes('/node_modules/react-i18next/')) return 'i18n';
          if (p.includes('/node_modules/zod/')) return 'zod';
          return undefined;
        },
      },
    },
  },
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8765',
      '/ws': {
        target: 'ws://127.0.0.1:8765',
        ws: true,
      },
    },
  },
});
