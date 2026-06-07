import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

describe('ManagerStatus contract', () => {
  it('matches the /manager/status response shape exposed by the backend', () => {
    const source = readFileSync(resolve(process.cwd(), 'src/types.ts'), 'utf8');
    const statusInterface = source.slice(
      source.indexOf('export interface ManagerStatus'),
      source.indexOf('export interface ManagerInstalledNode'),
    );

    expect(source).toContain('export interface ManagerStatus');
    expect(statusInterface).toContain('custom_nodes_dir: string');
    expect(statusInterface).toContain('installed_nodes: ManagerInstalledNode[]');
    expect(statusInterface).toContain('total: number');
    expect(statusInterface).not.toContain('installed_packages');
    expect(statusInterface).not.toContain('installed_node_modules');
    expect(statusInterface).not.toContain('environment_info');
  });
});
