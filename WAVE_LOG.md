# BioNodulo ↔ ComfyUI Gap Closure: Wave Log

A running ledger of the multi-wave effort to close feature gaps between
BioNodulo and ComfyUI (the industry reference for node-graph workflow tools).
Each wave is a coherent ~8-item batch landed as a single commit/push to
`bionodulo-collab`.

For full diffs, see `git log --grep="ComfyUI gap"`.

---

## Wave A — `74de87c` — Polish, search, auto-queue, focus mode

- Focus mode (`Ctrl+.`): hide chrome to give canvas the full viewport; floating exit pill.
- Tooltip-based keybindings on rail buttons.
- `state/recentWorkflows.ts`: localStorage-backed recents (max 12) surfaced in Getting Started.
- Settings panel sticky search with keywords + group-level visibility.
- Inline indeterminate progress bars on running nodes.
- Connection-aware node search: drop link on empty canvas → palette filtered to compatible inputs + auto-connect.
- Edge color palette: extended from ~20 to 40+ bioinformatics data types; stable hashed fallback hue for unknown types.
- Auto-queue modes (`manual` / `change` / `instant`) with localStorage persistence.
- Command registry grown from ~16 to 40+ commands.
- Dialog-aware shortcuts via `state/overlays.ts` MutationObserver.

## Wave B — `c2510ad` — Chainable reroutes, auto-history, subgraphs

- Reroutes (gap #1, #4): centre-anchored edges; mirrored bezier control points; upstream-walking link colour; click-point insertion; "Add Reroute Here" canvas context-menu item; Shift+click detach + re-target.
- History (gap #2): structural-signature dedup; 350ms debounced auto-push; mouseup/keyup flush; viewport in every snapshot; `beginTransaction`/`endTransaction` helpers.
- Subgraphs (gap #3): `utils/subgraph.ts` (extractSubgraph + writeSubgraphBack + promoteWidget); convert-in-place with auto-port synthesis; breadcrumb subgraph entry; `state/subgraphLibrary.ts` persisted library; widget promotion DOM overlay.
- Canvas plumbing: `getViewport()` ref accessor; `onEnterSubgraph` + `onPromoteWidgets` props; client-side node_info fallback.

## Wave 4.2-tail — `4df11b7` — Viewport/group/align/paste

- Per-workflow viewport persistence (#36): pan + zoom captured/restored per tab id; localStorage + beforeunload.
- Group mode propagation (#32): Mute All / Unmute All / Bypass All / Enable All / Pin All / Unpin All in group context menu.
- Alignment & distribution (#35): 6 alignment buttons + 2 distribution buttons in SelectionToolbox.
- Media paste (#31): backend `POST /api/workspace/upload`; clipboard file blob → upload → `input_file` node spawn.

## Wave C — `cfdedc4` — Canvas polish, lazy panels, history filter, right dock

- `React.lazy` + `Suspense` for 7 panels — ~60 kB main bundle reduction.
- Canvas honours palette tokens (canvas/accent/surface/border/muted) instead of hard-coded colours.
- Render Quality setting (`auto`/`high`/`low`) + shadow + smooth-link toggles wired through `qualityPrefsRef`.
- Ghost outline of node origin while dragging.
- `useNodeUsageStats`: most-used nodes group in NodeLibraryPanel with badge + star icon.
- Backend `get_run()` returns workflow snapshot; "Load workflow" history-card action.
- History tab toolbar: status chips, name+run-id search, Today/Yesterday/Past Week buckets.
- Right-side panel docking (per-panel toggle persisted).
- `useSettings`: `getBool` accepts fallback.
- `Spinner.tsx`: `ReactElement` return type for React 19 compatibility.

## Wave D — `64a925a` — Focus trap, scoped shortcuts, history mgmt, live releases

- `useFocusTrap` hook applied to Export/Import/BatchSampleSheet/GettingStarted/KeyboardShortcuts modals.
- Canvas keydown handler respects `hasOpenOverlay()` and scope-checks the focused element.
- Settings panel search shows match count + "no matches" hint + Clear.
- TopBar Run/Export/Import/AI buttons render their keybinding in the tooltip.
- Backend `POST /history/clear` + `DELETE /history/{id}`; toolbar "Clear history" + per-row delete.
- Per-node execution progress: `node_start` events → "3/12 · 6s" caption on running nodes.
- Live release notes via GitHub Releases API with 6h localStorage cache; bundled CHANGELOG fallback.

## Wave E — `cf753b2` — API client, canvas polish, settings hooks, log cap

- `web/src/api/client.ts`: centralised `apiGet`/`apiPost`/`apiPut`/`apiDelete` + `ApiError`.
- `rollup-plugin-visualizer` wired via `BIONODULO_ANALYZE=1`.
- `Ctrl/Cmd+click` adds to canvas selection; `Shift` still toggles.
- Group context menu: "Fit to Nodes" action.
- `Ctrl+Shift+V` paste-with-connections: copy records external incoming/outgoing edges; paste re-attaches.
- Visual undo/redo flash chip on `Ctrl+Z`/`Ctrl+Y`.
- `subscribeSetting` + `useSettingChange` for per-key reactive settings.
- Console log render cap (`LOG_RENDER_CAP = 250`, `+1000` expander) — bounded DOM on huge runs.

## Wave F — `4339d2f` — Search polish, error overlay, drop zones, feature flags

- Node Library: hover preview tooltip (350ms delay) with port types + tools; category filter chips with click-to-pin; loading state with Spinner.
- Per-node error overlay: "!" badge → popover with full message; auto-clears on param edit; resurfaces on re-failure.
- Floating panel drag → left/right canvas-edge dock zones with visual feedback.
- Canvas background pattern per palette (dots / grid / mesh / none); `litegraph-host` paints `--canvas`.
- `apiGetCached`: TTL + in-flight dedup + `clearApiCache(predicate?)`.
- Feature flags system (`state/featureFlags.ts`): `registerFlag`/`useFeatureFlag`/`setFeatureFlag`; localStorage; `?flag=foo` URL bootstrap; Settings panel auto-populates.

## Wave G — `227210a` — Thumbnails, ranking, diffs, dialogs, help, telemetry

- Recents thumbnails: `renderRecentThumbnail` (240×150 JPEG) on import/load; autosave updates in place via `refreshRecentThumbnail`.
- Client-side template ranking: `state/templateUsage.ts` count+lastUsed; layered into Fuse score; "N× used" pill on cards.
- Link colour modes: `type` / `gradient` / `uniform` setting; gradient highlights type changes through reroutes.
- Output diff modal: `OutputDiffModal` fetches `/runs/{id}` for two runs; amber row highlight on differences; wired into history toolbar.
- Generic `Dialog` primitive in `components/ui/Dialog.tsx`: focus trap + ESC + role=dialog + close button.
- Dialog stacking via `state/dialogStack.ts`: z-index ladder; only the top dialog responds to ESC.
- Dynamic help: when a node is selected, HelpWikiPanel surfaces objectInfo-driven docs (description, ports, requires, experimental/version pills).
- Telemetry: opt-in local-only ring buffer (200 events) with toggle, export-as-text, clear in Settings; `logTelemetry()` hooks at workflow run/import/template-load.

## Wave I — Search, bookmarks, minimap, validation, tokens

- Node bookmarks: `state/nodeBookmarks.ts` (localStorage Set); star button per row in NodeLibraryPanel; new "Bookmarks" group renders above Most Used / Recently Used.
- Workflow stats overlay: bottom-left floating card with node/edge/group counts + top-4 categories; collapses to a `12n · 8e` pill on click. Hidden in focus mode.
- Minimap improvements: nodes coloured by status (running blue, error red, completed green, cached purple, skipped grey) instead of just their nominal tint. Existing click-to-jump + drag-pan already worked.
- Help cross-search: `HelpWikiPanel` accepts `objectInfo` and surfaces node hits (name / description / category) under a "Nodes" section in the search results, alongside wiki page hits.
- `docs/DESIGN_TOKENS.md`: catalogue of every CSS custom property, canvas pattern dataset values, palette definition shape, and z-index ladder.
- API client migration: `TemplatesPanel`, `ExportModal`, `HPCPanel`, `EnvironmentPanel` moved off raw `fetch('/api/...')` to `apiGet` / `apiPost` (ApiError-aware fallback paths).
- Validation toast: `handleRun` short-circuits when `validate()` returns errors and emits a danger toast; if the first error names a known node id, surfaces a "Jump to node" action that calls `canvasRef.focusNode(id)`.
- Color-by-status toggle: new `bionodulo.canvas.colorByStatus` setting tints the node header with the status colour (completed/error/cached/skipped/running) instead of the user-chosen palette colour.

## Wave H — `481293e` — Tracking log, rename, layout, tags, types, validators

- This `WAVE_LOG.md` itself, plus the items below.
- Inline node title rename: `F2` on single-selected node, or `Alt`+double-click header → absolutely-positioned input overlay scaled to header. Enter/blur commits; Escape aborts; reroutes excluded (no user title).
- Auto-layout: `canvasRef.autoLayout()` runs topological column-rank layout on the selection (or all nodes); columns at 280px / rows at 160px anchored at the working-set top-left. Surfaced as `edit.autoLayout` command.
- Workflow tags: `RecentWorkflow.tags?: string[]` + `setRecentTags()`; Getting Started recents shows tag chips, an `All` / per-tag filter row, and a `#` button per row to edit tags inline.
- `cn()` utility (#84): dependency-free clsx-style class composer in `utils/cn.ts`.
- Command palette typed groups (#60): `COMMAND_GROUPS` const + `CommandGroup` type + `COMMAND_GROUP_ORDER` + `compareCommandGroups`; palette renders groups in canonical order.
- Zod-lite validators (#51): hand-rolled `validateRunRecord` / `validateWorkflow` / `validateObjectInfo` in `api/validators.ts`; wired into `OutputDiffModal` + `useObjectInfo`. Dependency-free.
- Reroute selection (#73): marquee switched from "wholly inside" containment to intersection so quick drags catch small nodes (reroutes especially); matches ComfyUI behaviour.

---

## Pending / future waves

Items from the gap analysis that haven't landed yet:

- #6 UI primitives library (Radix UI) — large scope.
- #12 i18n string externalisation.
- #15 ESLint + Prettier setup.
- #19 Strict TS checks (`noUnusedLocals`, `verbatimModuleSyntax`).
- #49 Extension/plugin system — large scope.
- #65 Dynamic help — partial (selected-node docs landed in Wave G); search across node docs still TODO.
- #66 Telemetry — DONE in Wave G; remote-sink integration deferred.
- #85 Reorganise hooks into category folders.
- #86 Design tokens documented (CSS custom property reference).
- Remaining `fetch('/api/...')` call sites: ~30 files still pre-`api/client.ts`; migrate opportunistically.

---

## Operating notes

- Commits attributed only to `classacre <nieuwenhuyzenmikamartin@gmail.com>`.
- Each wave: implement → build green → commit → push to `bionodulo-collab` on `Classacre/BioNodulo`.
- "Next wave" from the user starts a fresh batch; mid-wave "commit and push" confirms the partial scope.
