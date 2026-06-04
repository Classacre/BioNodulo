import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

describe('TypeScript strictness config', () => {
  it('keeps the strict compiler checks required by the gap-closure plan enabled', () => {
    const tsconfig = JSON.parse(readFileSync(resolve(process.cwd(), 'tsconfig.json'), 'utf8'));
    const compilerOptions = tsconfig.compilerOptions ?? {};

    expect(compilerOptions.strict).toBe(true);
    expect(compilerOptions.noUnusedLocals).toBe(true);
    expect(compilerOptions.noUnusedParameters).toBe(true);
    expect(compilerOptions.noImplicitOverride).toBe(true);
    expect(compilerOptions.verbatimModuleSyntax).toBe(true);
  });
});
