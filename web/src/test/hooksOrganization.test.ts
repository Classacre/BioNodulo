import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const workflowHooks = [
  'useAutoSave.ts',
  'useHistory.ts',
  'useQueueMode.ts',
  'useWorkflow.ts',
  'useWorkflowMessages.ts',
];
const collabHooks = ['useAuth.ts', 'useCollabPolling.ts'];
const settingsHooks = ['useSettings.ts'];
const dataHooks = ['useObjectInfo.ts'];
const uiHooks = ['useCommandPalette.ts', 'useFocusTrap.ts', 'useKeybindings.ts'];

describe('hooks organization', () => {
  it('keeps App-owned workflow hooks in the workflow hooks category', () => {
    const appSource = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');

    for (const hookFile of workflowHooks) {
      expect(existsSync(resolve(process.cwd(), 'src/hooks/workflow', hookFile)), hookFile).toBe(true);
      expect(existsSync(resolve(process.cwd(), 'src/hooks', hookFile)), hookFile).toBe(false);
    }
    expect(appSource).toContain("from './hooks/workflow'");
    expect(appSource).not.toContain("from './hooks/useAutoSave'");
    expect(appSource).not.toContain("from './hooks/useWorkflow'");
    expect(appSource).not.toContain("from './hooks/useQueueMode'");
    expect(appSource).not.toContain("from './hooks/useWorkflowMessages'");
  });

  it('keeps App-owned collaboration hooks in the collab hooks category', () => {
    const appSource = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');

    for (const hookFile of collabHooks) {
      expect(existsSync(resolve(process.cwd(), 'src/hooks/collab', hookFile)), hookFile).toBe(true);
      expect(existsSync(resolve(process.cwd(), 'src/hooks', hookFile)), hookFile).toBe(false);
    }
    expect(appSource).toContain("from './hooks/collab'");
    expect(appSource).not.toContain("from './hooks/useAuth'");
    expect(appSource).not.toContain("from './hooks/useCollabPolling'");
  });

  it('keeps settings hooks in the settings hooks category', () => {
    const appSource = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
    const themeSource = readFileSync(resolve(process.cwd(), 'src/hooks/useTheme.ts'), 'utf8');
    const settingsPanelSource = readFileSync(
      resolve(process.cwd(), 'src/components/panels/SettingsPanel.tsx'),
      'utf8',
    );
    const canvasSource = readFileSync(
      resolve(process.cwd(), 'src/components/canvas/WorkflowCanvas.tsx'),
      'utf8',
    );

    for (const hookFile of settingsHooks) {
      expect(existsSync(resolve(process.cwd(), 'src/hooks/settings', hookFile)), hookFile).toBe(true);
      expect(existsSync(resolve(process.cwd(), 'src/hooks', hookFile)), hookFile).toBe(false);
    }
    expect(appSource).toContain("from './hooks/settings'");
    expect(appSource).not.toContain("from './hooks/useSettings'");
    expect(themeSource).toContain("from './settings'");
    expect(settingsPanelSource).toContain("from '../../hooks/settings'");
    expect(canvasSource).toContain("from '../../hooks/settings'");
  });

  it('keeps data hooks in the data hooks category', () => {
    const appSource = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');

    for (const hookFile of dataHooks) {
      expect(existsSync(resolve(process.cwd(), 'src/hooks/data', hookFile)), hookFile).toBe(true);
      expect(existsSync(resolve(process.cwd(), 'src/hooks', hookFile)), hookFile).toBe(false);
    }
    expect(appSource).toContain("from './hooks/data'");
    expect(appSource).not.toContain("from './hooks/useObjectInfo'");
  });

  it('keeps shared UI hooks in the UI hooks category', () => {
    const appSource = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
    const dialogSource = readFileSync(resolve(process.cwd(), 'src/components/ui/Dialog.tsx'), 'utf8');
    const leftRailSource = readFileSync(resolve(process.cwd(), 'src/components/layout/LeftRail.tsx'), 'utf8');
    const topBarSource = readFileSync(resolve(process.cwd(), 'src/components/layout/TopBar.tsx'), 'utf8');

    for (const hookFile of uiHooks) {
      expect(existsSync(resolve(process.cwd(), 'src/hooks/ui', hookFile)), hookFile).toBe(true);
      expect(existsSync(resolve(process.cwd(), 'src/hooks', hookFile)), hookFile).toBe(false);
    }
    expect(appSource).toContain("from './hooks/ui'");
    expect(appSource).not.toContain("from './hooks/useCommandPalette'");
    expect(appSource).not.toContain("from './hooks/useKeybindings'");
    expect(dialogSource).toContain("from '../../hooks/ui'");
    expect(leftRailSource).toContain("from '../../hooks/ui'");
    expect(topBarSource).toContain("from '../../hooks/ui'");
  });
});
