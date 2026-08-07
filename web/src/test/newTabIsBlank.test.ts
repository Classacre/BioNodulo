import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

/**
 * The "+" in the tab bar must make a new, empty workflow.
 *
 * In cloud mode it used to open the "Open workflow" picker instead, so the one
 * control labelled "New workflow" was the only way to open an *old* one, and
 * there was no way to get a blank tab at all. Moving the picker to the command
 * palette keeps it reachable without overloading "+".
 *
 * Asserted against the source because App.tsx needs the whole editor mounted.
 */
const app = readFileSync(resolve(__dirname, '../App.tsx'), 'utf8');

describe('the new-tab button', () => {
  it('creates a workflow rather than opening the picker', () => {
    const onAdd = app.match(/onAdd=\{[^}]*\}/)?.[0] ?? '';

    expect(onAdd, 'onAdd binding not found').not.toBe('');
    expect(onAdd).toContain('newCloudWorkflow');
    expect(onAdd).not.toContain('setShowOpenWorkflow');
  });

  it('creates a cloud-backed workflow in cloud mode', () => {
    // A local `addTab` tab has no id, so it cannot be saved, shared, or
    // restored on the next visit — it looks like a tab but loses the work.
    const onAdd = app.match(/onAdd=\{[^}]*\}/)?.[0] ?? '';

    expect(onAdd).toContain('editorMode');
  });

  it('routes the palette command the same way as the button', () => {
    // Two ways to make a tab that disagree is how the local-only tab survived.
    const command = app.slice(app.indexOf("id: 'workflow.new'"));
    const onSelect = command.slice(0, command.indexOf('},')).match(/onSelect:.*/)?.[0] ?? '';

    expect(onSelect).toContain('newCloudWorkflow');
  });

  it('still offers a way to open an existing workflow', () => {
    // Rewiring "+" removes the picker's only entry point unless this exists.
    expect(app).toContain("id: 'workflow.open'");
    expect(app).toMatch(/id: 'workflow\.open'[\s\S]{0,400}setShowOpenWorkflow\(true\)/);
  });
});
