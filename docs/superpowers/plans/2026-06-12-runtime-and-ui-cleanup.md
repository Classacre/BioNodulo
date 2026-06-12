# Runtime And UI Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Make workflow runs show real node plans, move queue/history into one right drawer, simplify appearance settings around palettes, add language selection to Getting Started, and remove Inspector from the left rail.

**Architecture:** Reuse the existing run card/progress logic by extracting it from `BottomConsole` into a shared `RunsDrawer` component. Keep the backend queue serializer as the source of run execution plans. Treat Light and Dark as palette entries that also set `data-theme`, while leaving current palette token resolution intact for compatibility.

**Tech Stack:** Python `pytest` backend tests, React + TypeScript frontend, Vitest/Testing Library, existing BioNodulo palette/settings state.

---

### Task 1: Run Plan Serialization

**Files:**
- Modify: `bionodulo/execution/queue.py`
- Test: `tests/test_execution_runtime.py`

- [x] **Step 1: Write the failing test**

Add `test_run_queue_serializes_execution_plan_for_queue_and_history` to assert pending/running/history runs expose `execution_plan` and completed `node_statuses`.

- [x] **Step 2: Run test to verify it fails**

Run: `uv run --isolated --cache-dir /tmp/bionodulo-uv-cache --python 3.12 --with-editable . --with pytest --with pytest-asyncio python -m pytest tests/test_execution_runtime.py::test_run_queue_serializes_execution_plan_for_queue_and_history -q`
Expected: FAIL because `execution_plan` is absent.

- [x] **Step 3: Write minimal implementation**

Update `RunQueue._run_to_dict`, `get_run`, and `list_history` so every run serialization carries `execution_plan`; derive it from result metadata when available or from workflow nodes/edges otherwise.

- [x] **Step 4: Run test to verify it passes**

Run the same targeted pytest command.
Expected: PASS.

### Task 2: Runs Drawer

**Files:**
- Create: `web/src/components/layout/RunsDrawer.tsx`
- Modify: `web/src/components/layout/BottomConsole.tsx`
- Modify: `web/src/App.tsx`
- Modify: `web/src/index.css`
- Test: `web/src/test/RunsDrawer.test.tsx`

- [x] **Step 1: Write failing tests**

Add tests that render `RunsDrawer` with one pending and one completed run, verify both appear in one drawer, verify filtering, and verify close/cancel callbacks.

- [x] **Step 2: Run tests to verify they fail**

Run: `cd web && npm run test -- src/test/RunsDrawer.test.tsx`
Expected: FAIL because `RunsDrawer` does not exist.

- [x] **Step 3: Implement drawer**

Extract run progress/card helpers from `BottomConsole` into `RunsDrawer`, remove queue/history tabs from `BottomConsole`, and wire TopBar queue button to `runsDrawerOpen` state in `App.tsx`.

- [x] **Step 4: Run tests to verify they pass**

Run the same Vitest command.
Expected: PASS.

### Task 3: Rail And Getting Started

**Files:**
- Modify: `web/src/components/layout/LeftRail.tsx`
- Modify: `web/src/App.tsx`
- Modify: `web/src/components/modals/GettingStartedModal.tsx`
- Modify: `web/src/i18n/en.ts`
- Modify: `web/src/i18n/es.ts`

- [x] **Step 1: Write/update tests**

Use existing rail/getting-started tests if present; otherwise add focused assertions that Inspector is absent from the rail and the modal language select calls the language setter.

- [x] **Step 2: Implement**

Remove only the Inspector rail button and command-palette rail item. Keep the inspector panel available to edit-properties flows. Add a compact language selector in the Getting Started header.

- [x] **Step 3: Verify**

Run targeted frontend tests.

### Task 4: Palette Simplification

**Files:**
- Modify: `web/src/state/palettes.ts`
- Modify: `web/src/hooks/useTheme.ts`
- Modify: `web/src/hooks/usePaletteTheme.ts`
- Modify: `web/src/components/panels/SettingsPanel.tsx`
- Modify: `web/src/i18n/en.ts`
- Modify: `web/src/i18n/es.ts`
- Test: `web/src/test/palettes.test.ts` or existing palette/settings tests

- [x] **Step 1: Write tests**

Assert selecting built-in `light` and `dark` palette IDs sets the document theme mode and palette tokens, while normal palettes keep current behavior.

- [x] **Step 2: Implement**

Add Light and Dark palette entries, remove the standalone theme selector from Settings, make `setPalette` force `bionodulo.theme` for those palettes, and add a compact palette maker form that saves/export custom palettes.

- [x] **Step 3: Verify**

Run targeted palette/settings tests.

### Task 5: Input Validation Template Cleanup

**Files:**
- Modify: template JSON/PNG metadata files under `workflow_templates` and/or `web/public/templates`
- Modify tests that assert standalone validation nodes

- [x] **Step 1: Audit validator patterns**

Find `data_validator` nodes with one incoming edge and passthrough-only outgoing edges.

- [x] **Step 2: Migrate safe cases**

Move validator params into upstream node UI validation metadata, rewire passthrough edges, remove now-unused validator nodes, and rerun template relayout/thumbnail metadata generation.

- [x] **Step 3: Verify**

Run template tests and metadata checks.

### Task 6: Final Verification

**Files:**
- All modified files

- [x] **Step 1: Run targeted backend/frontend tests**

Run the queue serializer pytest, RunsDrawer/validator/palette tests, and `npm run build`.

- [x] **Step 2: Run diff hygiene**

Run `git diff --check` and inspect `git status --short`.

- [x] **Step 3: Clean generated temp artifacts**

Remove `/tmp/bionodulo-uv-cache`, `.pytest_cache`, `__pycache__`, and frontend build/cache outputs created by this run.
