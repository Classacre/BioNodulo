import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

describe('ManagerStatus contract', () => {
  it('matches the /manager/status response shape exposed by the backend', () => {
    const source = readFileSync(resolve(process.cwd(), 'src/types.ts'), 'utf8');

    expect(source).toContain('export interface ManagerStatus');
    expect(source).toContain('custom_nodes_dir: string');
    expect(source).toContain('installed_nodes: ManagerInstalledNode[]');
    expect(source).toContain('total: number');
    expect(source).not.toContain('installed_packages');
    expect(source).not.toContain('installed_node_modules');
    expect(source).not.toContain('environment_info');
  });
});
