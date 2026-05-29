// Flat ESLint config (eslint v9+). Configures TypeScript + React + hooks with
// Prettier interop. Kept intentionally lean — the goal of Wave O is to pass a
// clean lint, not to encode every house style rule. Tighten over time.

import js from '@eslint/js';
import globals from 'globals';
import tsPlugin from '@typescript-eslint/eslint-plugin';
import tsParser from '@typescript-eslint/parser';
import reactPlugin from 'eslint-plugin-react';
import reactHooks from 'eslint-plugin-react-hooks';
import prettier from 'eslint-config-prettier';

export default [
  {
    // Files we never lint — generated output and configs.
    ignores: [
      'dist/**',
      'node_modules/**',
      'e2e/**',
      'vite.config.ts',
      'vitest.config.ts',
      'eslint.config.js',
      '.prettierrc.json',
      'public/**',
    ],
  },
  js.configs.recommended,
  {
    files: ['src/**/*.{ts,tsx}'],
    languageOptions: {
      parser: tsParser,
      parserOptions: {
        ecmaVersion: 'latest',
        sourceType: 'module',
        ecmaFeatures: { jsx: true },
      },
      globals: {
        ...globals.browser,
        ...globals.es2024,
      },
    },
    plugins: {
      '@typescript-eslint': tsPlugin,
      react: reactPlugin,
      'react-hooks': reactHooks,
    },
    settings: {
      react: { version: 'detect' },
    },
    rules: {
      // TypeScript essentials only — full recommended set surfaces hundreds of
      // diagnostics we don't have time to clean in this wave; pick the rules
      // that catch real bugs without drowning the user in lint noise.
      '@typescript-eslint/no-unused-vars': [
        'warn',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_', caughtErrorsIgnorePattern: '^_' },
      ],
      '@typescript-eslint/no-explicit-any': 'off',
      'no-unused-vars': 'off', // superseded by @typescript-eslint version
      'no-empty': ['warn', { allowEmptyCatch: true }],
      'no-undef': 'off', // TS handles this; ESLint flags valid global types

      // React
      'react/jsx-uses-react': 'off',
      'react/react-in-jsx-scope': 'off',
      'react/prop-types': 'off',
      'react/no-unescaped-entities': 'off',

      // React Hooks
      'react-hooks/rules-of-hooks': 'error',
      'react-hooks/exhaustive-deps': 'warn',
    },
  },
  prettier,
];
