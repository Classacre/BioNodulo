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

## Wave M — `d0d3926` — HTML preview in canvas + AI assistant overhaul

- HTML preview node (`bionodulo/nodes/builtin/utils.py`): new `html_preview` built-in node mirrors `image_preview` but accepts `.html`/`.htm` files. `VALIDATE_INPUTS` rejects non-HTML extensions; `run()` registers the file with the run context so it lands in the previews map. Auto-registers via the existing `bionodulo.nodes.builtin.utils` import.
- Canvas HTML overlay (`web/src/components/canvas/LiteGraphCanvas.tsx`): new `nodeHtmlPreviewsMap` prop renders a sandboxed `<iframe>` inside any `html_preview` node, alongside the existing `nodePreviewsMap` image overlay. `sandbox="allow-scripts"` is used **without** `allow-same-origin` so the embedded report lives on an opaque origin — it can run JS for tabs/plots (MultiQC, FastQC, plotly) but cannot reach the parent DOM, cookies, or storage even if a node emits malicious markup. Per-type node-height bumped by +200 px for `html_preview`.
- Gallery HTML cards (`web/src/components/layout/BottomConsole.tsx`): the Previews tab now lists HTML reports as scaled-down iframe thumbnails next to image cards; tab counter shows the combined count. New `onOpenHtmlPreview` prop opens the report full-screen.
- HTML preview modal (`web/src/components/modals/HtmlPreviewModal.tsx`): new component, full-screen sandboxed `<iframe>` with header (filename, Save, Open-in-new-tab, Close). Same sandbox rules as the canvas overlay.
- AI assistant — token efficiency (`bionodulo/ai/assistant.py`): conversation history is now trimmed to the last 12 non-system turns before being sent to the LLM (was: full history every round). Tool-result payloads above 8 kB are truncated with a trailing marker so a single `get_current_workflow` doesn't dwarf the rest of the prompt.
- AI assistant — new tools (`bionodulo/ai/tools.py`): `get_workflow_summary` returns a compact view of the canvas (node count, edge count, type histogram, id/title list) — preferred over `get_current_workflow` when full parameters aren't needed. `explain_last_failure` summarises the most recent failed run: status, error, first failing node, and log tail. System prompt updated to mention the html_preview node and to prefer the summary tool.
- AI assistant — Stop button (`AIWorkflowModal.tsx`): in-flight chat requests use `AbortController`; the Send button morphs into Stop while sending. Aborting appends a `_Stopped by user._` note instead of a fake local response.
- AI assistant — Regenerate (`AIWorkflowModal.tsx`): post-turn chip drops the last assistant turn and re-sends the previous user question, useful when the model picked a bad tool path.
- AI assistant — quick prompt chips (`AIWorkflowModal.tsx`): when the conversation is empty the footer shows four one-click prompts (Summarize my workflow, What went wrong?, Find missing QC, Suggest next step) that pre-fill the input box.
- AI assistant — markdown rendering (`web/src/utils/markdown.ts`, `AIWorkflowModal.tsx`, `index.css`): hand-rolled escape-then-format renderer with inline code, fenced blocks, **bold**, _italics_, headings, lists, and safe http(s) links. Inputs are HTML-escaped before any markdown substitution, so `dangerouslySetInnerHTML` only ever mounts content emitted by the renderer itself. New `.ai-markdown` and `.md-*` CSS.
- AI chat streaming endpoint (`bionodulo/api/ai_routes.py`): the stubbed `/ai/chat/stream` is replaced with a real SSE responder that runs the full tool-aware chat and emits each `ChatStep` as its own SSE event (`tool_call`, `tool_result`, `propose_changes`, `reply`, terminated by `[DONE]`). The internal LangGraph loop stays non-streaming — this is the cheapest step-level streaming we can ship without a graph rewrite, and the frontend can adopt it incrementally.
- Run cluster polish (`TopBar.tsx`, `index.css`): the standalone chevron-up/down batch stepper next to Run is gone — batch count now lives inside the Run dropdown with horizontal `−` value `+` controls under a "Batch count" header (followed by `run`/`runs`). The Run + chevron split-button drops every internal border so the two halves render as one primary-coloured surface; the seam between them is a single inset `box-shadow` `|` separator, with a wrapper-level `:focus-within` ring around the whole control. (Follow-up: dropped `overflow: hidden` from the wrapper, which was clipping the absolutely-positioned menu and made the chevron silent.)
- URL-aware input nodes (`bionodulo/nodes/builtin/inputs.py`): `CopyInputNode._resolve_source` now detects `http(s)/ftp(s)` URLs and downloads them into a workspace-scoped cache at `.bionodulo/url_cache/` on first use; subsequent runs reuse the cached copy. `.gz` URLs are transparently decompressed (matching the existing example-data downloader). Per-format descriptions on every `Input *` node now read "Path or URL to …" so the param surface advertises the new behaviour.
- Getting Started "Example Data" tab removed (`GettingStartedModal.tsx`): the up-front 340 MB bulk download is obsolete now that templates can reference URLs in their input-node params and let the runtime cache them on demand. Removed the tab entry, the `DataStatus` interface, the `handleDownload` / status-polling state, and the entire `tab === 'data'` block. Backend `/api/getting-started/*` endpoints stay in place for older scripts.
- Templates use URLs (`templates/*.json`): the seven URL-backed templates (fastq_qc, assembly, rna_seq, variant_calling, wgs_variant, differential_expression, and the assembly reference reused in wgs_variant) now reference public URLs directly in their input-node params — provenance is visible in the canvas and the runtime cache fetches on first run. The six generator-only templates (chip_seq, metagenomics, single_cell, biopython, phylogenetics, deseq2, r_visualization) keep their `examples/data/<cat>/<file>` paths because there is no real URL; instead `inputs.py` grows a `_resolve_example_data_fallback` that consults `EXAMPLE_DATA_MANIFEST` on a missing path and either downloads or runs the generator into the cache. The `single_cell` template's category-level directory input is materialised by populating every manifest entry for the category.
- Failed-node red highlight (`bionodulo/execution/executor.py`, `web/src/App.tsx`): input-resolution failures used to emit a generic `error` event that never updated per-node status, so the node stuck on green `running`. The executor now emits `node_error` for input failures (matching real execution failures), and the frontend `queue_finish` / `queue_error` handlers also defensively promote any nodes still showing `running` after a failed run to `error` — so even if a future event path is missed, the canvas border switches from green to red.
- Every template now has a canvas visualization (`templates/*.json`, `bionodulo/nodes/builtin/*.py`): added `html_preview` or `image_preview` nodes wired to the most useful report from each pipeline — MultiQC HTML for fastq_qc / chip_seq / metagenomics / rna_seq / variant_calling / wgs_variant / differential_expression; QUAST HTML for assembly; DESeq2 MA-plot + pheatmap PNG for deseq2; CellRanger web_summary.html for single_cell; bp_msa_view alignment view for phylogenetics; bp_seq_stats stats table for biopython_analysis. To make the wiring work the MultiQC and QUAST nodes' `PLAN_OUTPUTS` were corrected to return the actual `.html` paths instead of stale directory / no-extension names; `bp_seq_stats`, `bp_msa_view`, and `cellranger_count` gained extra HTML outputs (`stats_html`, `alignment_html`, `web_summary`) with small self-contained HTML reports that render cleanly inside the sandbox iframe.



## Wave O.§15 — `__PENDING__` — Connection-aware node search ranking

- `web/src/utils/nodeSearch.ts`: `useNodeSearch` now accepts an optional `compatibleInputType` arg. When set, the hook precomputes which nodes accept that source type (including `*` / `ANY` slots) and applies a `-0.18` boost to their Fuse score so they outrank weaker string matches. With an empty query, compatible nodes are surfaced first so the palette opens directly on useful options.
- `web/src/components/nodes/NodePalette.tsx`: forwards its existing `requireInputType` prop into the ranking hook — both filter mode (only show compatible) and ranked mode (compatible bubble up) now use the same signal.
- `web/src/test/nodeSearch.test.ts`: 4 cases — empty query no-filter returns all nodes, empty query with type boosts all type-compatible nodes to the top three, a strict string match still appears when the typed filter would exclude it, and a weak Fuse match loses to a strong typed match (`"qc"` + FASTQ ranks `fastqc` above `multiqc`).



## Wave O.§1 — `50abf93` — Pluggable history store with transactions

- Rewrote `web/src/hooks/useHistory.ts`. Old hook was 43 lines of `JSON.parse(JSON.stringify(...))` deep clone with no dedup, no viewport, no transactions. New hook offers `push(workflow, viewport?)` (no-op when the signature matches the current tip), `begin()` (returns a `commit()` thunk; sequential pushes inside a transaction collapse into a single snapshot at commit so users undo a whole drag/paste gesture at once), `undo()`/`redo()` returning the popped `HistorySnapshot` (workflow + viewport + sig), and reactive `canUndo`/`canRedo`.
- `structuredClone` replaces `JSON.parse(JSON.stringify(...))` so node params keep `undefined`/Date/Map/Set correctly; a JSON fallback covers older jsdom.
- Default signature reuses the App.tsx pattern (node id/type/position/params/ui + edge endpoints + group geometry). Signature override via `options.signatureFn` for tests / specialised editors.
- App.tsx's inline auto-history is the source of truth right now — it already had sig dedup + viewport + 350 ms debounce + mouseup/keyup eager flush hard-wired in. This commit ships the hook as the reusable export for future consumers (subgraph editors, snippet editors, plugins) without disrupting the inline path. The §10 App.tsx breakdown will fold the inline code through this hook.
- `src/test/useHistory.test.ts` rewritten: 6 cases — initial state, push + undo + redo round trip, signature dedup is a no-op, viewport survives undo/redo, transactions collapse to one snapshot, external mutation of the initial workflow doesn't corrupt the stored history.



## Wave O.§12 — `b77044e` — Structured catch logging

- New `web/src/state/logging.ts` exposes `logError(scope, err)` + a 200-entry ring buffer + a subscribe API. Errors land in `console.error` (visible in DevTools) and in the ring buffer where a future telemetry sink can pick them up; subscribers fire synchronously but listener errors are swallowed so they can't reenter `logError`.
- Tested in `src/test/logging.test.ts` (4 cases): Error normalisation (message/name/stack), non-Error fallbacks (string + object via JSON.stringify), subscriber + unsubscribe, ring-buffer capacity overflow.
- Retrofitted six high-traffic catches in `App.tsx`: `collab.comments.fetch`, `collab.presence.fetch`, `collab.snapshot.publish`, `collab.snapshot.fetch`, `hpc.status.poll` (and the import wiring). These are the network catches where silent failures previously left no trail at all.
- The remaining ~170 silent catches are deliberately untouched in this commit — they're mostly localStorage UI-pref persistence where a failure is genuinely fine to swallow. They can adopt `logError` opportunistically over future work without one big mechanical sweep.



## Wave O.§9 — `358feb6` — TypeScript strictness

- `web/tsconfig.json` adds three flags: `noUnusedParameters: true` (was false), `noImplicitOverride: true`, and `verbatimModuleSyntax: true`. The codebase already used `import type` everywhere `verbatimModuleSyntax` requires, so that flag landed at zero cost. `noImplicitOverride` caught two missing `override` keywords in `ErrorBoundary.tsx`. `noUnusedParameters` caught three intentional-but-unmarked unused params; they're prefixed with `_` now (`useAwareness` `_doc`/`_connected`, `markdown` link replacer `_m`).
- Deferred for a follow-up wave: `exactOptionalPropertyTypes: true` surfaces 291 type errors across run-record types, API validators, and node-status flows; `noUncheckedIndexedAccess: true` typically adds another 50–100 errors. Both are correct-by-default but would consume an entire wave on their own and are tracked separately so the rest of Wave O can move.



## Wave O.§8 — `b1e6bbe` — Vite code splitting

- `web/vite.config.ts`: added `build.rollupOptions.output.manualChunks` that pulls react/scheduler, yjs/y-protocols/y-websocket/lib0, fuse.js, i18next/react-i18next, and zod into their own caching-friendly chunks. Paths are normalised (`\\` → `/`) so the rules work on Windows.
- Main bundle dropped from 850.85 kB → 493.60 kB (-42%); the split-off chunks are react 192.52 kB, yjs 87.82 kB, i18n 48.72 kB, fuse 24.38 kB. These cache across releases.
- Removed stale `web/vite.config.js` + `vite.config.d.ts` that were silently overriding the `.ts` config (Vite picked the `.js` first; that's why the previous attempt didn't split). `tsconfig.node.json` now emits its composite output into `node_modules/.tmp-tsc-node` so future runs don't re-pollute the repo root.
- `web/package.json` gained `build:analyze` (calls `cross-env BIONODULO_ANALYZE=1 npm run build`), which the existing rollup-plugin-visualizer hook turns into a `dist/stats.html` treemap.



## Wave O.§6 — `d1999ab` — Vitest + Playwright test infrastructure

- `web/vitest.config.ts`: jsdom env, `src/test/setup.ts` setup file pulling in `@testing-library/jest-dom/vitest` matchers, test file glob limited to `src/**/*.{test,spec}.{ts,tsx}`.
- `web/playwright.config.ts`: e2e test dir, headless chrome, auto-starts `npm run dev` for runs.
- First test suite (11 tests, all green): `src/test/palettes.test.ts` (completePalette deep-merge + getResolvedPaletteMode), `src/test/client.test.ts` (apiGet/apiPost JSON parsing, ApiError thrown on 4xx, empty body handling, body stringification), `src/test/useHistory.test.ts` (initial state, push + undo + redo round-trip using renderHook).
- Playwright smoke (`web/e2e/smoke.spec.ts`): app-shell mounts, title matches, skips gracefully when dev server is not running.
- `web/package.json` scripts: `test`, `test:watch`, `test:ui`, `test:e2e`.
- `web/tsconfig.json` excludes `src/test/**`, `*.test.ts(x)`, `*.spec.ts(x)`, and `e2e/**` from the production build so test code never ships to the bundle.
- `.github/workflows/ci.yml` frontend job runs `npm test` between lint and build.



## Wave O.§5 — `a1c5db1` — ESLint + Prettier toolchain

- Added `web/eslint.config.js` (flat config) wiring `@typescript-eslint`, `eslint-plugin-react`, `eslint-plugin-react-hooks`, and `eslint-config-prettier`. Lean rule set focused on real bugs (hooks rules, unused vars warning, useless escape error) so the existing codebase passes without a 100-file reformat. Cleaned 5 genuine lint errors uncovered by the new config: a useless escape `\-` in App.tsx's error-token regex, two `\"` escapes inside single-quoted strings in ImportModal, a `useState` called after an early `return null` in NodeEditor (real hooks-rules violation), and a useless `let wtype = 'text'` initial in LiteGraphCanvas where every branch reassigns.
- Added `.prettierrc.json` + `.prettierignore` with house style (single quotes, trailing comma all, 100-col, semis, 2-space). Not running `prettier --write` across the codebase in this commit — the 108-file reformat would dwarf every future Wave O diff. The script is wired so future code follows the rule and a dedicated formatting commit can land it later.
- `web/package.json`: new scripts `lint`, `lint:fix`, `format`, `format:check`.
- `.github/workflows/ci.yml`: frontend job now runs `npm run lint` before `npm run build` so future regressions trip CI.



## Wave N — `6f4305c` — Tool-native viz, post-run cleanup, less node chrome

- Tool-generated viz instead of custom HTML (`bionodulo/nodes/builtin/biopython_nodes.py`, `templates/*.json`): the `bp_seq_stats` and `bp_msa_view` nodes no longer emit hand-rolled HTML reports. `bp_seq_stats` now writes a real `stats.tsv` alongside the existing JSON and the biopython template renders it via the new `table_preview` node. `bp_msa_view` now renders the alignment as a matplotlib PNG (typed `IMAGE`) so it flows naturally into `image_preview` without going through the HTML sandbox at all — the phylogenetics template was switched over to image_preview. Both reverts replace 5-sequence-tall hand-written HTML tables / `<span>`-coloured rows with proper tool output.
- New generic `table_preview` node (`bionodulo/nodes/builtin/utils.py`): visual-sink node that takes a CSV / TSV / TXT path and renders only the head rows (default 25, capped at 500) into a sandbox-rendered HTML table. Streams the file row-by-row so multi-million-row variant tables / count matrices don't blow up memory; reports `… N more rows not shown` when truncated. Delimiter auto-sniffed but overridable. Same `register_preview` hook as `image_preview` / `html_preview`, so it shows up in the canvas overlay and the Previews gallery automatically.
- Post-run highlight cleanup (`web/src/App.tsx`): the `queue_finish` handler used to only flip stuck `running` nodes to `error` on failure — a successful run that lost a `node_complete` event would leave the node frozen on green forever. Now any node still in `running` when the run terminates is promoted based on the final status (`completed` for success, `error` for failure/cancellation, since `NodeStatus` has no cancelled state). The existing failure-only toast logic stays as before.
- Drop per-node version badge (`web/src/components/canvas/LiteGraphCanvas.tsx`): the small `vX.Y.Z` chip the canvas drew in every node's title bar (next to `EXP` / port-count) is gone — the metadata still lives in `node.meta.version` for the node-details drawer where it's actually useful. The other badges (`L` for pinned, `EXP` for experimental, collapsed `in→out` port counts) are unchanged. Less chrome at glance density.



## Wave L — `0911439` — UI polish: top bar, overlays, runs, palette, panels

- Top bar overhaul (`TopBar.tsx`, `App.tsx`): HPC badge now only renders when `bionodulo.hpc.enabled` is on; CollabBadge is only mounted when `bionodulo.collab.enabled` is on (instead of being shown in offline state); the "Unsaved changes / Autosave" pill is gone (the per-tab amber dot covers dirty signalling); batch-count stepper collapsed to chevron-up / value / chevron-down with no `-`/`+` duplicates; Run is now a split-button — the connected chevron opens a popover with `Manual` / `On change` / `Instant` queue-mode radios plus `Batch from sheet…`; standalone Sheet button + bare `<select>` queue mode removed; standalone Import button removed (drag-drop covers import); Export icon swapped to read as out-of-app.
- Export modal (`ExportModal.tsx`, `workflowThumbnail.ts`): PNG is now the default format. New options block: transparent-background checkbox (renders the preview on a CSS checkerboard so users see the alpha), resolution slider (50–100 % of base, drives canvas dimensions since PNG is lossless), and a "JSON only (skip PNG wrapper)" checkbox for the case where the user just wants the workflow JSON. Auto-regenerate on option change once a preview is on screen.
- Merged bottom-left overlay (`WorkflowStatsOverlay.tsx`, deleted `HardwareMonitor.tsx`): the system-stats card and workflow-stats card no longer overlap. One overlay polls `/system_stats` every 2 s and renders both sections in a single bordered card; the collapsed pill carries both signals (`5n · 4e · 23% CPU · 48% RAM`). Notes / reroutes already excluded from the node count.
- Backend cancel no-404 (`bionodulo/execution/queue.py` route in `bionodulo/api/routes.py`): if a run has already moved to history when the cancel POST lands, the endpoint returns `200 { status: "already_finished" }` instead of 404. Only an unknown `run_id` is treated as 404. Stops the spurious "Could not cancel run" toast that fired when the user clicked cancel a second too late.
- Failed-run toast (`App.tsx` WebSocket handler): both `queue_finish` (status `failed`) and `queue_error` now fire `toast.error('Run failed', { message: 'WorkflowName — <first error line>' })`. The active queue automatically de-lists the failed run (status filter is pending/running) while keeping it in history.
- Log node UUIDs replaced with names (`BottomConsole.tsx`, `App.tsx`): new `nodeIdToName` map (built from every open workflow's nodes) flows into `BottomConsole`; both the per-node group header and individual log-line `[node]` tags resolve to the friendly title with the raw UUID accessible only via the title attribute.
- Example-data 14+ 404s (`bionodulo/manager/example_data.py`): every dead URL (Zenodo record 1324070 ChIP-seq, Zenodo record 17661262 metagenomics, `minoda-lab/universc` 10x tinygex paths) was replaced with deterministic synthetic FASTQ generators using a single `_write_fastq` helper. The downloader is unchanged because it already catches per-file exceptions, but now there's nothing to catch.
- Auto-arrange measured spacing (`LiteGraphCanvas.tsx`): `arrangeNodesLayout` now measures each node's effective height (header + ports + widget rows + padding) and computes per-layer column width / per-layer cumulative row offsets, with 80 px column gaps and 40 px row gaps. Replaces the fixed `colWidth=280, rowHeight=140` which guaranteed overlap on tall widget stacks.
- Notes excluded from auto-run + validate (`App.tsx`): the empty-workflow guards in the `change`-mode auto-queue effect and the auto-validate/resolve effect now filter `node.type !== 'note' && node.type !== 'reroute'` so a notes-only workflow is treated as empty (backend executor already filtered them).
- Drag-over-widget fix (`LiteGraphCanvas.tsx`): widget overlays use `pointerEvents: 'none'` while any drag is in flight and the dragged node's own widgets fade to 0.35 opacity with z-index dropped to 1, so dragging a node OVER another no longer has the moved node's widget catch the cursor and stall the drag.
- Selection highlight on plain click (`LiteGraphCanvas.tsx`): selection outline now uses `palette.accent` instead of `node.color` — the old code drew a same-colour outline against a same-colour body, so plain clicks looked like nothing happened.
- Palette in dark mode (`palettes.ts`): `applyPalette` now calls `setProperty(token, value, 'important')` so palette tokens win the cascade against dark-mode default selectors that previously masked the swap.
- Settings panel close button (`SettingsPanel.tsx`): × close button in the header bound to the existing `onClose` prop, matching other rail panels' header layout.
- Minimap + canvas controls follow right-docked panels (`App.tsx`, `index.css`): new `--right-panel-inset` CSS custom property is computed from the total width of right-docked panels and applied to the app shell wrapper; `.minimap` and `.canvas-controls` use `right: calc(8px + var(--right-panel-inset, 0px))` so they shift left to stay visible.
- Float / dock buttons appear with panel content (`App.tsx`): `rail-panel-toolbar` now lives inside the `<Suspense>` boundary, so float + dock-to-side buttons no longer flash on screen for the half-second the lazy panel chunk is loading.



- Workflow doctor: `WorkflowDoctorModal` scans the active workflow for missing required inputs (with default-value fallback check), unused outputs (excluding `output_node` sinks), empty graph / disconnected graph, and dependency hints; each finding has a Jump button that focuses the offending node. Surfaced via the `workflow.doctor` command.
- URL-hash share: `utils/workflowShare.ts` encodes the workflow as base64-url JSON in `#wf=…`. `workflow.copyShareUrl` command builds + copies; mount-time hook decodes any incoming hash, replays through `handleImport`, then strips the hash so refresh doesn't re-import.
- Inline param help tooltips: widget labels read `spec.tooltip` / `spec.description` for their `title` attribute so hover surfaces backend-authored docs alongside the existing copy-to-selection hint.
- Node parameter presets: `state/nodePresets.ts` (per-type, localStorage, max 30 each). Context-menu entries "Save Params as Preset…" and "Apply Preset…" wired through `handleContextAction`; apply only overwrites keys the target node already has so cross-variant presets don't bolt stray params on.
- Per-tab dirty indicator: `WorkflowTabs` gains a `dirtyIndices?: ReadonlySet<number>` prop; renders a small amber dot before the tab label. Active tab only (single-source `dirty` flag — multi-tab dirty tracking is a future polish).
- Close-tab dirty confirm: `onClose` wrapper invokes `confirmDialog({ tone: 'danger' })` when the active tab is dirty so accidentally closing the X doesn't lose work. `beforeunload` already guarded refresh / close-window.
- Workflow auto-naming: `utils/workflowNaming.ts`'s `suggestWorkflowName` builds names like `BWA + samtools alignment` from the dominant tools/categories. `workflow.autoName` command renames the current tab; `TemplatesPanel`'s save dialog now defaults to the auto-name instead of "Untitled workflow".
- API client migration round 3: `HardwareMonitor`, `AIWorkflowModal` moved off raw `fetch('/api/...')` to `apiGet` / `apiPost` with `ApiError`-aware local-fallback path for the AI chat.

## Wave J — `fa93ad1` — Snippets, drag-drop, bulk edit, unified search, strict TS

- Workflow snippets: `state/workflowSnippets.ts` (localStorage, max 100, `instantiateSnippet` remaps ids + anchors at world position). `workflow.saveSnippet` / `workflow.insertSnippet` commands captured a selection or stamps a saved snippet at canvas centre.
- Drag workspace file → canvas: new `application/bionodulo-workspace-file` dataTransfer mime; every file row in `WorkspacePanel` is now draggable; drop on canvas spawns an `input_file` node at the cursor position with the file path pre-filled.
- Bulk parameter editor: `BulkParamModal` shows the intersection of params shared by all selected nodes, with `[varies]` placeholder; touched fields apply to every selected node on Apply.
- Unified search palette: a `'dynamic'` command source registers up to 40 `Add: {Node}` commands (sourced from `objectInfo`) and 12 `Open recent: {Name}` commands so `Ctrl+P` doubles as node-add and workflow-recall.
- Widget right-click copy-to-selection: `copyParamToSelection` on the canvas; every DOM widget label spreads `labelProps` containing `onContextMenu` so right-clicking any widget broadcasts its current value to other selected nodes that expose the same key. Flashes a "Copied X → N nodes" chip.
- Collapsed node port-count badge: when a node is collapsed, the title bar renders an `N→M` badge so the user knows what's hidden underneath.
- API client migration round 2: `WorkspacePanel`, `ImportModal`, `MissingDependenciesBanner`, `HostPrerequisitesBanner` moved off `fetch('/api/...')` to `apiGet` / `apiPost` with `ApiError`-aware fallback paths.
- Strict TS `noUnusedLocals` enabled in `tsconfig.json`; cleaned up 8 unused locals (App.tsx `shareWorkflow`/`beginTransaction`/`endTransaction`, bridge.ts dead handler fields, HostPrerequisitesBanner `missingOptional`, WorkspacePanel `rootPath` value, pngMetadata `writeUint32BE`).

## Wave I — `3beab04` — Search, bookmarks, minimap, validation, tokens

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
