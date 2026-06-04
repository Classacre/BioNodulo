import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const migratedFiles = [
  'src/components/panels/SettingsPanel.tsx',
  'src/components/panels/WorkspacePanel.tsx',
  'src/components/panels/EnvironmentPanel.tsx',
  'src/collab/AuditLog.tsx',
  'src/collab/CommentsPanel.tsx',
  'src/collab/NodeCommentPopover.tsx',
  'src/collab/TemplateGallery.tsx',
  'src/collab/UserList.tsx',
  'src/collab/VersionHistory.tsx',
  'src/hooks/useObjectInfo.ts',
  'src/hooks/useWorkflow.ts',
];

describe('API client migration', () => {
  it('keeps selected frontend files off raw appPath fetch calls', () => {
    for (const file of migratedFiles) {
      const source = readFileSync(resolve(process.cwd(), file), 'utf8');
      expect(source, file).not.toContain('fetch(appPath');
    }
  });
});
