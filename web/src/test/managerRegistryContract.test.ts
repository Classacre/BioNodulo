import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import {
  safeValidateManagerRegistry,
  validateManagerRegistry,
} from '../api/validators';

describe('ManagerRegistry contract', () => {
  it('documents the /manager/registry response shape in frontend types', () => {
    const source = readFileSync(resolve(process.cwd(), 'src/types.ts'), 'utf8');

    expect(source).toContain('export interface ManagerRegistryResponse');
    expect(source).toContain('registries: Record<string, string>');
    expect(source).toContain('tool_paths: Record<string, string>');
    expect(source).toContain('custom_node_registries: Record<string, CustomNodeRegistryEntry>');
    expect(source).toContain('installed_packages: CustomNodePackage[]');
    expect(source).toContain('export interface CustomNodeRegistryEntry');
    expect(source).toContain('compatibility: CustomNodeRegistryCompatibility');
    expect(source).toContain('installed_package?: CustomNodePackage | null');
    expect(source).toContain('export interface CustomNodePackage');
    expect(source).toContain('valid: boolean');
    expect(source).toContain('errors: string[]');
  });

  it('validates registry catalog and installed package payloads', () => {
    const payload = validateManagerRegistry({
      registries: { bionodulo: 'https://github.com/bionodulo/community-nodes.git' },
      tool_paths: { git: '/usr/bin/git' },
      custom_node_registries: {
        'bionodulo-community': {
          name: 'bionodulo-community',
          url: 'https://github.com/bionodulo/community-nodes.git',
          description: 'BioNodulo custom node registry: bionodulo-community',
          installed: true,
          install_status: 'installed',
          installed_package: {
            name: 'community-nodes',
            version: '0.1.0',
            repository: 'https://github.com/bionodulo/community-nodes.git',
            entrypoints: ['community_nodes'],
            requirements: ['requests'],
            directory: 'community_nodes',
            manifest_path: '/tmp/custom_nodes/community_nodes/bionodulo.toml',
            manifest_present: true,
            valid: true,
            errors: [],
          },
          verified: true,
          compatibility: {
            manifest_required: true,
            supported_manifest: 'bionodulo.toml',
          },
        },
      },
      installed_packages: [
        {
          name: 'community-nodes',
          version: '0.1.0',
          description: 'Community nodes',
          repository: 'https://github.com/bionodulo/community-nodes.git',
          entrypoints: ['community_nodes'],
          requirements: ['requests'],
          directory: 'community_nodes',
          manifest_path: '/tmp/custom_nodes/community_nodes/bionodulo.toml',
          manifest_present: true,
          valid: true,
          errors: [],
        },
      ],
    });

    expect(payload.custom_node_registries['bionodulo-community'].installed).toBe(true);
    expect(payload.custom_node_registries['bionodulo-community'].installed_package?.name).toBe('community-nodes');
    expect(payload.custom_node_registries['bionodulo-community'].compatibility.supported_manifest).toBe('bionodulo.toml');
    expect(payload.installed_packages[0].entrypoints).toEqual(['community_nodes']);
  });

  it('rejects malformed installed package lists through the safe wrapper', () => {
    const result = safeValidateManagerRegistry({
      registries: {},
      tool_paths: {},
      custom_node_registries: {},
      installed_packages: 'community-nodes',
    });

    expect(result.ok).toBe(false);
  });
});
