# BioNodulo Node-Graph Gap Closure: Wave Log

A running ledger of the multi-wave effort to close feature gaps in
BioNodulo's node-graph workflow tools.
Each wave is a coherent ~8-item batch landed as a single commit/push to
`bionodulo-collab`.

For full diffs, see the branch history for `bionodulo-collab`.

---

## App.tsx state ownership prep — `0a8aeb7` — Hooks + modal atoms

- Extracted six App-owned behaviours into focused hooks: auto-save snapshot publishing, panel layout persistence, HPC polling, WebSocket workflow message dispatch, queue-mode effects, and collaboration comments/presence polling.
- Added `web/src/state/uiAtoms.ts` for modal flags plus UI shell atoms, matching the existing flat atom export pattern.
- Moved the 13-modal JSX cluster into `web/src/components/modals/Modals.tsx`; each modal now owns its open flag subscription while App passes only the workflow-coupled context bundle.
- `web/src/App.tsx` dropped the extracted hook bodies and modal render block, shrinking from roughly 3,495 lines to roughly 3,009 before the next state-ownership waves.
- Verification before commit: `npx tsc --noEmit`, `npm run build`, and `npm test` all passed.

## App.tsx state ownership Wave B — `fe41fb8` — Lightbox atoms

- Added `web/src/state/lightboxAtoms.ts` with lightbox open/images/index atoms, HTML-preview state, and a write-only `openLightboxAtom` action that updates the coupled lightbox state together.
- `BottomConsole` now opens image and HTML previews through atoms instead of receiving `onOpenLightbox` / `onOpenHtmlPreview` props from App.
- `Modals` now subscribes directly to lightbox and HTML-preview atoms, removing those fields from the App-provided modal context bundle.
- `web/src/App.tsx` no longer owns lightbox or HTML-preview state and no longer forwards the preview opener callbacks into the console.
- Verification before commit: `npx tsc --noEmit`, `npm run build`, and `npm test` all passed. Local Vite responded at `http://localhost:5173/`; Browser-plugin smoke was blocked by the Windows sandbox spawn failure.

## App.tsx state ownership Wave C — `604bcce` — Run telemetry atoms

- Added `web/src/state/runAtoms.ts` with `isRunningAtom`, `batchCountAtom`, `logsAtom`, `hostStatusAtom`, and Record-backed `nodeRunProgressAtom`.
- App still owns run orchestration, but now writes telemetry atoms instead of owning render state for logs, host status, running state, batch count, and node progress.
- `TopBar` subscribes directly to running state and batch count; `BottomConsole` subscribes directly to logs and batch count.
- `WorkflowCanvas` subscribes to node progress with `selectAtom` and reads the Record by node id instead of receiving a `Map` prop from App.
- Verification before commit: `npx tsc --noEmit`, `npm run build`, and `npm test` all passed.

## App.tsx state ownership Wave D — `11a992f` — UI shell atoms

- Wired `selectedNodeIdAtom` through canvas and `CommentsPanel`; canvas publishes selection into the atom, while comments read it directly.
- App still reads selected node id for Help/Inspector panel composition, but no longer owns the selection setter or forwards selected-node props into `CommentsPanel`.
- Wired `consoleVisibleAtom` into the rail and App shell so the console button reflects atom-backed visibility and toggles the console without extra prop state.
- Replaced App-local focus-mode state with `focusModeAtom`; added a migration-compatible storage adapter that reads the old `bionodulo.focusMode` key and writes the new `bionodulo.focus_mode` key without losing existing sessions.
- Verification before commit: `npx tsc --noEmit`, `npm run build`, and `npm test` all passed.

## App.tsx state ownership Wave E — `b464c5e` — Prop cleanup

- Removed now-redundant modal opener props from `TopBar`, `BottomConsole`, and `CollabBadge`; those components now open their own Jotai-backed modals directly.
- Cleaned App imports/setters made dead by the atom migrations, including collaboration modal openers and output-diff opener wiring.
- Fixed the panel-resize keyboard helper's no-useless-assignment lint error.
- Final `web/src/App.tsx` line count after this refactor wave: 2,833 lines.
- Verification before commit: `npx tsc --noEmit`, `npm run lint` (warnings only), `npm run build`, and `npm test` all passed.

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
- Canvas background pattern per palette (dots / grid / mesh / none); `workflow-canvas-host` paints `--canvas`.
- `apiGetCached`: TTL + in-flight dedup + `clearApiCache(predicate?)`.
- Feature flags system (`state/featureFlags.ts`): `registerFlag`/`useFeatureFlag`/`setFeatureFlag`; localStorage; `?flag=foo` URL bootstrap; Settings panel auto-populates.

## Wave G — `227210a` — Thumbnails, ranking, diffs, dialogs, help, telemetry

- Recents thumbnails: `renderRecentThumbnail` (240×150 JPEG) on import/load; autosave updates in place via `refreshRecentThumbnail`.
- Workflow thumbnail node fallback labels now read from `workflowThumbnail` i18n keys, so exported/recent thumbnails render `Nodo` under Spanish when a node lacks both title and type metadata.
- Client-side template ranking: `state/templateUsage.ts` count+lastUsed; layered into Fuse score; "N× used" pill on cards.
- Link colour modes: `type` / `gradient` / `uniform` setting; gradient highlights type changes through reroutes.
- Output diff modal: `OutputDiffModal` fetches `/runs/{id}` for two runs; amber row highlight on differences; wired into history toolbar.
- Generic `Dialog` primitive in `components/ui/Dialog.tsx`: focus trap + ESC + role=dialog + close button.
- Dialog stacking via `state/dialogStack.ts`: z-index ladder; only the top dialog responds to ESC.
- Dynamic help: when a node is selected, HelpWikiPanel surfaces objectInfo-driven docs (description, ports, requires, experimental/version pills).
- Telemetry: opt-in local-only ring buffer (200 events) with toggle, export-as-text, clear in Settings; `logTelemetry()` hooks at workflow run/import/template-load.

## Wave M — `d0d3926` — HTML preview in canvas + AI assistant overhaul

- HTML preview node (`bionodulo/nodes/builtin/utils.py`): new `html_preview` built-in node mirrors `image_preview` but accepts `.html`/`.htm` files. `VALIDATE_INPUTS` rejects non-HTML extensions; `run()` registers the file with the run context so it lands in the previews map. Auto-registers via the existing `bionodulo.nodes.builtin.utils` import.
- Canvas HTML overlay (`web/src/components/canvas/WorkflowCanvas.tsx`): new `nodeHtmlPreviewsMap` prop renders a sandboxed `<iframe>` inside any `html_preview` node, alongside the existing `nodePreviewsMap` image overlay. `sandbox="allow-scripts"` is used **without** `allow-same-origin` so the embedded report lives on an opaque origin — it can run JS for tabs/plots (MultiQC, FastQC, plotly) but cannot reach the parent DOM, cookies, or storage even if a node emits malicious markup. Per-type node-height bumped by +200 px for `html_preview`.
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



## Wave O bundled — `0a05cf4` — Final §2/§4/§10/§14/§17/§19 closure

Bundles the remaining outstanding sections from the implementation review into one commit so the wave list is fully crossed off.

- §2 Media paste support (`web/src/components/canvas/WorkflowCanvas.tsx`): the `Ctrl+V` handler now reads `navigator.clipboard.read()` for image / audio / video blobs first; each blob is uploaded via `apiPost('/workspace/upload')` and an `input_file` node is spawned at the viewport centre with `file_path` pre-populated. Falls through to the existing text/JSON paste path when no media items are present. Uses the existing `apiPost`, `objectInfo.input_file`, `addNode`, and `toast.success` / `toast.error`.
- §4 Palette token expansion (`web/src/state/palettes.ts`): rewrote the 16-token design system into a 66-token system organised into semantic groups (8 surfaces, 6 text, 5 borders/dividers, 5 accent + 3 soft tints, 4 status base + soft + borders, 5 focus/interaction, 8 canvas/graph, 4 code/mono, 3 backdrop/scrim, 3 shadows/elevation, 4 misc). Added `completePalette()` deep-merge fallback via `deriveTokens()` so palette authors only need ~16 anchors and derived states (`accent-hover`, `accent-soft`, `danger-border`, etc.) are filled in automatically with `color-mix()` / alpha-channel functions. All 4 built-in palettes (BioNodulo, Clinical, Field Station, High Contrast) keep their light + dark anchors; everything else is derived. `applyPalette` continues to set tokens with `!important` so theme defaults can't win the cascade.
- §10 App.tsx breakdown — partial (`web/src/hooks/useAuth.ts`, `web/src/App.tsx`): extracted the auth init flow + login/close handlers into `useAuth({ collabEnabled, settingsReady })`. Returns `{ authUser, authReady, showAuthDialog, setShowAuthDialog, handleAuthLogin, handleAuthClose }`. Drops `initAuth` / `getAuthUser` / `authReadyAtom` / `authUserAtom` / `showAuthDialogAtom` from the App.tsx import surface. App.tsx is 37 lines lighter; full breakdown into the 8 hooks called out in the plan stays as deliberate follow-up because each carries non-trivial regression risk and the gains are mostly architectural.
- §14 Panel resize hardening (`web/src/App.tsx`): the existing custom `mousemove`/`mouseup` resize handler now also accepts touch events (`touchstart` / `touchmove` / `touchend`) and arrow-key keyboard nudges (16 px, `Shift`+arrow = 64 px, `Home` / `End` snap to 280 / 560). The handle is `tabIndex=0` with proper `role="separator"`, `aria-orientation="vertical"`, and `aria-valuenow` / `aria-valuemin` / `aria-valuemax` for assistive tech. Right-docked panels invert the drag direction so the handle behaves intuitively on either side. This delivers the keyboard / touch / a11y wins `react-resizable-panels` would have given us without taking the dependency, since the existing dock+float architecture is per-panel and would have required an end-to-end rewrite to fit the library's `<PanelGroup>` model.
- §17 Inspector panel as a persistent right-dock (`web/src/components/panels/InspectorPanel.tsx`, `web/src/App.tsx`, `web/src/components/layout/LeftRail.tsx`): new `InspectorPanel` component wraps the existing `NodeEditor` with an empty-state for "no node selected", consuming `selectedNodeId` from App and rendering parameter edits through `handleNodesChange`. Synthesises a minimal `GraphNode`-shaped object from the workflow node + `objectInfo` so `NodeEditor` keeps working unchanged. Lazy-loaded as `InspectorPanel` chunk (1.46 kB). New rail button between Nodes and Templates; uses the existing rail-panel docking, floating, resize, and per-panel error-boundary infrastructure for free.
- §19 Template PNG embedding (`web/src/state/templateThumbnails.ts`, `web/src/components/panels/TemplatesPanel.tsx`): new `getOrRenderTemplateThumbnail()` LRU-50 cache. When a template card lacks a server-supplied `thumbnail_url`, the panel fetches the template's workflow JSON via `/api/workflow_templates/{filename}`, runs it through `renderWorkflowThumbnail()`, embeds the JSON via `embedWorkflowInPngDataUrl()`, and serves the resulting PNG (with workflow tEXt chunk) as the card image. Object URLs are revoked on LRU eviction so we don't leak Blob memory across long sessions.
- §10 / §14 follow-up notes: full App.tsx extraction (`useAutoSave` / `usePanelLayout` / `useRunQueue` / `useCollab` / `useHPC` / `wsReducer` / `AppShell`) and `react-resizable-panels` library adoption stay deferred. Each is a self-contained commit when its risk envelope justifies the work.

---



- `web/src/i18n/locales/en.ts` rebuilt as a comprehensive surface-organised dictionary: top-level keys per panel / dialog / domain (`common`, `notifications`, `dialogs`, `commandPalette`, `shortcuts`, `palettes`, `topbar`, `panels`, `nodeLibrary`, `parameters`, `workspace`, `templates`, `runs`, `inspector`, `console`, `hpc`, `settings`, `helpWiki`, `errors`, `validation`, `nodes`, `runStatus`, `a11y`, `toasts`). 582 leaf keys total, 669 lines. Keys are stable identifiers — screen-reader / keyboard-help components read them directly, so renames are user-visible.
- `web/src/i18n/locales/es.ts` mirrors the en structure 1:1 (same keys, same nesting). 171 leaf strings have Spanish translations applied via `web/scripts/es-overlay.ts` — anything not yet translated falls back to English at runtime through i18next's `fallbackLng: 'en'`. To extend Spanish coverage, add entries to `es-overlay.ts` and re-run the small Node generator embedded in this wave's commit (no separate npm script — it's a one-shot used during wave authoring).
- Plurals use i18next's `_plural` suffix convention (`{{count}} node` / `{{count}} nodes`). Interpolation tokens (`{{count}}`, `{{name}}`, `{{action}}`) are preserved verbatim across both locales.
- No production code reads these keys yet — wiring is deferred. The point of this wave is to publish the *contract*: every panel author can now use `t('panels.workspace')` instead of hard-coding strings, knowing the keys exist and an es fallback is in place. The actual `useTranslation()` migration is a per-panel exercise that will happen wave-by-wave alongside cosmetic refactors.

## Wave O.§7 — `082d2f4` — Runtime validation expansion (zod-style, dependency-free)

- The hand-rolled validators in `web/src/api/validators.ts` (added in Wave G.51) are extended to cover the recently-migrated endpoints: `host_status`, `hpc/status`, and a generic `runs_list` shape that tolerates both `{ runs: [...] }` and a top-level array.
- Decision: **don't ship zod**. The existing module already mirrors zod's `safeParse` API (`safeValidateX → { ok, value | error }`), is ~5kB, and a real `zod` dependency would add ~10kB min+gz. Validation coverage at this point is ~7 endpoints — not worth the bundle.
- Wired `safeValidateHostStatus` into the host-status poll and the recheck button in `App.tsx`. Wired `safeValidateHpcStatus` into the HPC status poll. Both treat a validation failure the same way they treat an offline backend — degrade silently, log structured.
- Added `web/src/test/validators.test.ts` (16 cases) covering: missing fields default safely, well-formed payload pass-through, wrong status enum coerced to undefined, top-level array fallback for runs list, and individual bad rows skipped without failing the whole list. Test count 23 → 39.
- If validation coverage doubles or we need cross-field rules, the `safeValidateX` helpers are drop-in replaceable with `zodSchema.safeParse` — the call-site shape is identical.

## Wave O.§11 — `e6b9b69` — Raw fetch() migration to api/client

- All `/api/...` raw `fetch()` calls in the web app are migrated to the centralised `api/client` helpers (`apiGet`, `apiPost`, `apiDelete`, `apiGetText`). The client already runs through `getToken()` and injects `Authorization: Bearer <token>` once in `buildHeaders` — call sites no longer hand-roll the header dictionary, JSON serialisation, or `Content-Type: application/json`.
- Migrated files: `web/src/App.tsx` (16 fetches: workflow templates, collab comments / presence / snapshot publish + fetch, host status x2, run logs, run details, hpc status, queue cancel, run load, run retry, workspace upload, collab templates, cache clear, workspace file), `web/src/components/layout/BottomConsole.tsx` (run report HTML), `web/src/hooks/useSettings.ts` (`/api/settings`), `web/src/collab/ShareDialog.tsx` (4 calls — list, create, refresh, revoke), `web/src/collab/useCollab.ts` (2 calls — share list, share create).
- `getToken()` guards (`if (!token) return;`) are kept where they short-circuit before the request — they're now an authentication-required pre-check, not a header-construction step.
- Behaviour change: 4xx / 5xx responses now throw `ApiError` instead of being silently swallowed by `r.ok ? r.json() : null` patterns. Every migrated site already had a `try/catch` or `.catch(() => …)` for offline / unauthorised states, so the visible behaviour is the same except errors are now log-friendly rather than null-coalesced.
- The one `fetch()` left in the web app on purpose: `GettingStartedModal.tsx`'s call to `https://api.github.com/repos/Classacre/BioNodulo/releases?per_page=10`. That hits an external host, not `/api/...`, and `api/client` is intentionally scoped to first-party endpoints. A comment-block-free rule of thumb: if the path doesn't start with `/api/` or `/ws/`, don't route it through the client.
- BottomConsole's report effect needed a small TS adjustment: hoisting `selectedRunId` into a local `runId` const so the inner `async fetchReport` could use it without TS narrowing complaining about the closure capture of a possibly-null state. Pure refactor — no behaviour change.



## Wave O.§18 — `9dda701` — Validation enforcement on selected runs

- `web/src/App.tsx` `handleRunSelected` previously called `validate()` and discarded the result — selected-node runs would silently submit a known-invalid workflow. Now it mirrors `handleRun`: when `validate()` returns `valid: false`, the selected run is aborted, a `toast.error("Validation failed (N)")` shows the first error string, and a "Jump to node" toast action focuses the offending node when the error message contains a node-id token. `setIsRunning(false)` is reset on the early return so the run button doesn't stick.
- The full-workflow `handleRun` already had this enforcement — this commit closes the gap that selected-run mode was the only escape hatch around the validator. Errors continue to land in TopBar (`validationValid` / `validationErrors`) for at-rest visibility; runtime enforcement is now consistent across both run paths.



## Wave O.§20 — `049389b` — Reroute parentId

- `WorkflowNode` (in `web/src/types.ts`) gains an optional `parentId?: string`. Today only reroutes use it; subgraph and group-membership work can adopt the same field later without a schema bump.
- New helper `groupContainingPoint(groups, x, y)` in `WorkflowCanvas.tsx` — topmost group whose body contains the point, or null.
- Both reroute creation paths (`insertRerouteOnEdge` for split-edge insertion and the canvas-menu "Add Reroute") now set `parentId` to the containing group when one exists. Reroutes dropped onto bare canvas stay parentless. The field is omitted (not set to undefined) when no parent applies, so the workflow JSON stays clean.
- No selection / move / copy semantics depend on the field yet — those flow into §17 (inspector) and a future group-aware drag pass; this commit ships the data plumbing so the rest can land without another schema migration.



## Wave O.§13 — `dc58de9` — Per-panel error boundaries

- `web/src/components/layout/ErrorBoundary.tsx` rewritten. New props: `name` (becomes the `panel.<name>` log scope and labels the fallback so the user sees which surface failed), `variant: 'inline' | 'panel'` (compact vs full fallback), `resetKeys: ReadonlyArray<unknown>` (boundary auto-resets when any key changes — handy when the user navigates away from the broken surface). `componentDidCatch` now routes through `logError` from §12 instead of bare `console.error`.
- `web/src/App.tsx` `renderPanelContent` wraps every panel branch (`settings`, `help`, `templates`, `environments`, `hpc`, `nodes`, `data`, plugin-registered panels, console) in its own `ErrorBoundary` with `name`, `variant="inline"`, and `resetKeys={[tab]}` so switching tabs heals a crashed sibling. The bottom-console boundary now passes `name="console"` plus reset keys, and the App-root boundary that wraps the canvas keeps its existing default fallback.



## Wave O.§16 — `716b7a6` — Shortcut scoping

- `web/src/state/keybindings.ts`: `KeybindingDefinition` gains an optional `scope?: 'global' | 'canvas' | 'modal'`. Independent from the visual `category` grouping. `'global'` is the default and preserves today's behavior exactly. The 10 `canvas.*` bindings (select-all, copy, cut, paste, undo, redo, redo-alternate, group, collapse, delete) are now scoped `'canvas'` so they don't fire while a modal is open.
- `web/src/hooks/useKeybindings.ts`: dispatcher reads the scope and enforces it. `'modal'` bindings only fire while `hasOpenOverlay()` is true; `'canvas'` bindings stay silent while an overlay is open. The legacy `respectOverlays` option still works and is now scope-aware — modal-scoped bindings are exempt from it.
- No UI changes — the shortcut modal will pick up the new `scope` field opportunistically when it's worth adding a scope chip; the field is in the public type so future panels / plugins can read it without breaking changes.



## Wave O.§15 — `de3a9ec` — Connection-aware node search ranking

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

- Added `web/eslint.config.js` (flat config) wiring `@typescript-eslint`, `eslint-plugin-react`, `eslint-plugin-react-hooks`, and `eslint-config-prettier`. Lean rule set focused on real bugs (hooks rules, unused vars warning, useless escape error) so the existing codebase passes without a 100-file reformat. Cleaned 5 genuine lint errors uncovered by the new config: a useless escape `\-` in App.tsx's error-token regex, two `\"` escapes inside single-quoted strings in ImportModal, a `useState` called after an early `return null` in NodeEditor (real hooks-rules violation), and a useless `let wtype = 'text'` initial in WorkflowCanvas where every branch reassigns.
- Added `.prettierrc.json` + `.prettierignore` with house style (single quotes, trailing comma all, 100-col, semis, 2-space). Not running `prettier --write` across the codebase in this commit — the 108-file reformat would dwarf every future Wave O diff. The script is wired so future code follows the rule and a dedicated formatting commit can land it later.
- `web/package.json`: new scripts `lint`, `lint:fix`, `format`, `format:check`.
- `.github/workflows/ci.yml`: frontend job now runs `npm run lint` before `npm run build` so future regressions trip CI.



## Wave N — `6f4305c` — Tool-native viz, post-run cleanup, less node chrome

- Tool-generated viz instead of custom HTML (`bionodulo/nodes/builtin/biopython_nodes.py`, `templates/*.json`): the `bp_seq_stats` and `bp_msa_view` nodes no longer emit hand-rolled HTML reports. `bp_seq_stats` now writes a real `stats.tsv` alongside the existing JSON and the biopython template renders it via the new `table_preview` node. `bp_msa_view` now renders the alignment as a matplotlib PNG (typed `IMAGE`) so it flows naturally into `image_preview` without going through the HTML sandbox at all — the phylogenetics template was switched over to image_preview. Both reverts replace 5-sequence-tall hand-written HTML tables / `<span>`-coloured rows with proper tool output.
- New generic `table_preview` node (`bionodulo/nodes/builtin/utils.py`): visual-sink node that takes a CSV / TSV / TXT path and renders only the head rows (default 25, capped at 500) into a sandbox-rendered HTML table. Streams the file row-by-row so multi-million-row variant tables / count matrices don't blow up memory; reports `… N more rows not shown` when truncated. Delimiter auto-sniffed but overridable. Same `register_preview` hook as `image_preview` / `html_preview`, so it shows up in the canvas overlay and the Previews gallery automatically.
- Post-run highlight cleanup (`web/src/App.tsx`): the `queue_finish` handler used to only flip stuck `running` nodes to `error` on failure — a successful run that lost a `node_complete` event would leave the node frozen on green forever. Now any node still in `running` when the run terminates is promoted based on the final status (`completed` for success, `error` for failure/cancellation, since `NodeStatus` has no cancelled state). The existing failure-only toast logic stays as before.
- Drop per-node version badge (`web/src/components/canvas/WorkflowCanvas.tsx`): the small `vX.Y.Z` chip the canvas drew in every node's title bar (next to `EXP` / port-count) is gone — the metadata still lives in `node.meta.version` for the node-details drawer where it's actually useful. The other badges (`L` for pinned, `EXP` for experimental, collapsed `in→out` port counts) are unchanged. Less chrome at glance density.



## Wave L — `0911439` — UI polish: top bar, overlays, runs, palette, panels

- Top bar overhaul (`TopBar.tsx`, `App.tsx`): HPC badge now only renders when `bionodulo.hpc.enabled` is on; CollabBadge is only mounted when `bionodulo.collab.enabled` is on (instead of being shown in offline state); the "Unsaved changes / Autosave" pill is gone (the per-tab amber dot covers dirty signalling); batch-count stepper collapsed to chevron-up / value / chevron-down with no `-`/`+` duplicates; Run is now a split-button — the connected chevron opens a popover with `Manual` / `On change` / `Instant` queue-mode radios plus `Batch from sheet…`; standalone Sheet button + bare `<select>` queue mode removed; standalone Import button removed (drag-drop covers import); Export icon swapped to read as out-of-app.
- Export modal (`ExportModal.tsx`, `workflowThumbnail.ts`): PNG is now the default format. New options block: transparent-background checkbox (renders the preview on a CSS checkerboard so users see the alpha), resolution slider (50–100 % of base, drives canvas dimensions since PNG is lossless), and a "JSON only (skip PNG wrapper)" checkbox for the case where the user just wants the workflow JSON. Auto-regenerate on option change once a preview is on screen.
- Merged bottom-left overlay (`WorkflowStatsOverlay.tsx`, deleted `HardwareMonitor.tsx`): the system-stats card and workflow-stats card no longer overlap. One overlay polls `/system_stats` every 2 s and renders both sections in a single bordered card; the collapsed pill carries both signals (`5n · 4e · 23% CPU · 48% RAM`). Notes / reroutes already excluded from the node count.
- Backend cancel no-404 (`bionodulo/execution/queue.py` route in `bionodulo/api/routes.py`): if a run has already moved to history when the cancel POST lands, the endpoint returns `200 { status: "already_finished" }` instead of 404. Only an unknown `run_id` is treated as 404. Stops the spurious "Could not cancel run" toast that fired when the user clicked cancel a second too late.
- Failed-run toast (`App.tsx` WebSocket handler): both `queue_finish` (status `failed`) and `queue_error` now fire `toast.error('Run failed', { message: 'WorkflowName — <first error line>' })`. The active queue automatically de-lists the failed run (status filter is pending/running) while keeping it in history.
- Log node UUIDs replaced with names (`BottomConsole.tsx`, `App.tsx`): new `nodeIdToName` map (built from every open workflow's nodes) flows into `BottomConsole`; both the per-node group header and individual log-line `[node]` tags resolve to the friendly title with the raw UUID accessible only via the title attribute.
- Example-data 14+ 404s (`bionodulo/manager/example_data.py`): every dead URL (Zenodo record 1324070 ChIP-seq, Zenodo record 17661262 metagenomics, `minoda-lab/universc` 10x tinygex paths) was replaced with deterministic synthetic FASTQ generators using a single `_write_fastq` helper. The downloader is unchanged because it already catches per-file exceptions, but now there's nothing to catch.
- Auto-arrange measured spacing (`WorkflowCanvas.tsx`): `arrangeNodesLayout` now measures each node's effective height (header + ports + widget rows + padding) and computes per-layer column width / per-layer cumulative row offsets, with 80 px column gaps and 40 px row gaps. Replaces the fixed `colWidth=280, rowHeight=140` which guaranteed overlap on tall widget stacks.
- Notes excluded from auto-run + validate (`App.tsx`): the empty-workflow guards in the `change`-mode auto-queue effect and the auto-validate/resolve effect now filter `node.type !== 'note' && node.type !== 'reroute'` so a notes-only workflow is treated as empty (backend executor already filtered them).
- Drag-over-widget fix (`WorkflowCanvas.tsx`): widget overlays use `pointerEvents: 'none'` while any drag is in flight and the dragged node's own widgets fade to 0.35 opacity with z-index dropped to 1, so dragging a node OVER another no longer has the moved node's widget catch the cursor and stall the drag.
- Selection highlight on plain click (`WorkflowCanvas.tsx`): selection outline now uses `palette.accent` instead of `node.color` — the old code drew a same-colour outline against a same-colour body, so plain clicks looked like nothing happened.
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
- Reroute selection (#73): marquee switched from "wholly inside" containment to intersection so quick drags catch small nodes, especially reroutes.

## Post-Wave H follow-up — Dynamic help node-doc search

- HelpWikiPanel node search now indexes the same registry-backed docs it can render: aliases, required tools, documentation URL, version, input names/types/tooltips/descriptions/defaults, and output names/types.
- Node search hits are actionable buttons; clicking one opens the full node documentation in the Help panel, including inputs, outputs, and required executables, even when the node is not selected on the canvas.
- `InputSpec.description` is typed on the frontend so backend-authored input descriptions from `/api/object_info` are searchable and rendered beside ports.
- Verification: Vitest coverage for searching node input descriptions and opening node docs, plus a Firefox Playwright smoke using live `objectInfo` (`spectral library` -> DIA-NN -> full docs).

## Current gap closure follow-up — API migration + bio format conversion

- API client migration: `EnvironmentPanel` rename/delete/duplicate/package-remove calls and `useWorkflow` validate/resolve/run/export/import calls now route through `api/client` helpers instead of raw `fetch(appPath(...))`. The migration guard covers both files.
- Stage 2 data-transform gap audit: the planned data-transform nodes mostly already exist; the concrete high-value gap was `format_converter`, which only handled CSV/TSV/JSON table records.
- `format_converter` now preserves existing in-process CSV/TSV/JSON conversion while adding bio-format command routing for SAM/BAM/CRAM (`samtools`), VCF/VCF_GZ/BCF (`bcftools`), GFF/GTF (`gffread`), and FASTQ/FASTA (`seqtk`).
- `string_operations` now accepts the planned Stage 2 operation aliases (`concatenate`, `uppercase`, `lowercase`, `replace`, `trim`, `substring`, `regex_match`, `startswith`, `endswith`) while preserving the existing tuple output contract.
- Environment resolution now knows `gffread` and `seqtk` package/version metadata, and tests cover frontend discovery metadata, output planning, command rendering, unsupported conversion validation, and cwd handling for command execution.
- Workflow-control executor integration: node execution contexts now expose the active executor and shared run metadata, and workflow control nodes declare `EXECUTOR_CACHE_POLICY = "always_run"` so their explicit cache/checkpoint/retry/pause semantics are not hidden by the generic executor cache.
- Checkpoints now include a JSON-safe snapshot of shared run metadata alongside local checkpoint context when upstream metadata is requested.
- `cache_control` run-scope cache markers now live under the current run id, so a "run" scoped cache miss in `run-1` does not turn into a hit for `run-2`; explicit custom cache directories and global/user scopes keep their existing shared behavior.
- Retry policies are now consumed by the executor for downstream matching nodes: the executor retries failed nodes according to the recorded policy, emits `node_retry`, records attempt counts, and respects `only_retry_specific_nodes`.
- ForEach loop body subgraphs now honor inactive branch outputs, so conditional routing inside loops skips inactive body branches per iteration.
- `parallel_for` now has an executor-backed body path: workflows can connect from its new `iteration` body port, run the connected body subgraph once per scatter chunk, feed returned body values into `_parallel_results`, and gather through the existing all/any/first/sorted strategies.
- Workflow LLM backend calls now retry transient provider errors and return a normalized `LLMResponse.error` after exhausted attempts; `llm_prompt` includes that provider error in metadata instead of hiding it behind an empty response.
- API-backed nodes now have shared HTTP primitives for retries, 429 `Retry-After`, optional GET/HEAD caching, and token-bucket rate limiting; `http_request` delegates through the shared client while preserving its existing helper interface.
- Manifest-backed custom node packages now load the modules declared in `bionodulo.toml` `entrypoints`, turning the package manifest from registry metadata into an executable node-loading contract while preserving legacy single-file and `__init__.py` custom nodes.
- Frontend object-info normalization now preserves custom-node provenance and dependency metadata (`builtin`, `git_url`, `git_commit`, conda/R packages), so saved `node_info` retains the source details needed for later third-party node resolution.
- App-owned workflow hooks now live under `web/src/hooks/workflow/` with a category barrel for auto-save, queue-mode, and workflow WebSocket message effects; shared UI/settings hooks remain in the top-level hook folder.
- App-owned collaboration hooks now live under `web/src/hooks/collab/` with a category barrel for auth initialization and REST polling effects.
- API client migration: `collab/auth.ts` now uses the central API helpers for `/auth/token` and `/auth/me`; token/user localStorage helpers live in `collab/authStorage.ts` so `api/client.ts` can read bearer tokens without a circular dependency. The migration guard now covers auth, and no first-party raw `/api` fetches remain outside `api/client.ts`.
- TopBar visible run/queue/status controls now read from i18n keys, with Spanish runtime coverage for validation status, queue count, run/export/AI buttons, run options, batch controls, and queue-mode menu labels.
- Manager status now has an explicit backend/frontend contract for the read-only custom-node manager surface: `/manager/status` exposes `custom_nodes_dir`, `installed_nodes`, and `total`, and the frontend `ManagerStatus` type matches that route instead of the stale package/environment shape.
- Workflow-owned `useWorkflow` and `useHistory` now live under `web/src/hooks/workflow/` and export through that category barrel; the workflow message hook imports notifications directly instead of pulling in the full UI barrel during hook-only tests.
- Node Library panel chrome, search summaries, result actions, bookmark affordances, tooltip headings, subgraph actions, and empty states now read from `nodeLibrary` i18n keys, with Spanish unit and browser coverage for the panel surface.
- TopBar run options now support keyboard menu entry and recovery: `ArrowDown` opens the split menu and focuses the first enabled control, while `Escape` closes the menu and restores focus to the run-options toggle.
- TopBar run options now also support open-menu focus movement with `ArrowDown`, `ArrowUp`, `Home`, and `End`, wrapping through enabled controls in DOM order.
- Templates panel dialog chrome, save form, search/sort controls, result summaries, card affordances, counts, and empty/error states now read from `templates` i18n keys, with Spanish unit coverage for the panel surface.
- Left rail built-in panel labels, button titles, and accessible names now read from `panels` i18n keys, with Spanish unit coverage while preserving the existing tab ids and shortcut suffixes.
- Workspace panel chrome, root controls, file-list loading/empty states, selection count, file row tooltips, preview actions, and local error strings now read from `workspace` / `common` i18n keys, with Spanish unit coverage and a Firefox smoke of the persisted Spanish language path.
- Inspector panel is restored as a built-in rail/App panel, and its chrome plus empty-state text now read from `inspector` i18n keys with Spanish unit coverage.
- HPC panel configuration labels, enabled/test-connection status messages, and script preview chrome now read from `hpc` / `common` i18n keys with Spanish unit coverage and a Firefox smoke of the persisted Spanish language path.
- Environment panel manager chrome, loading/empty states, row menus, package counts/actions, confirmation copy, and local fallback status messages now read from `environment` / `common` / `errors` i18n keys with Spanish unit coverage and a Firefox smoke of the persisted Spanish language path.
- Workflow tab-strip default names, dirty-state affordance, new-tab action, scroll controls, and context-menu labels now read from `workflowTabs` / `topbar` / `common` / `dialogs` i18n keys with Spanish unit coverage and a Firefox smoke of the persisted Spanish language path.
- Settings dialog shell, close affordance, section navigation labels, search placeholder/summary, and section headings now read from `settings` / `common` i18n keys with Spanish unit coverage and a Firefox smoke of the persisted Spanish language path.
- Settings Appearance and Canvas rows now read labels, descriptions, actions, and select options from `settings` / `common` i18n keys with Spanish unit coverage and a Firefox smoke of the persisted Spanish language path.
- Settings Collaboration, Cache, Execution, and Files rows now read labels, descriptions, status pills, actions, and cache-clear toast copy from `settings` / `common` i18n keys with Spanish unit coverage and a Firefox smoke of the persisted Spanish language path.
- Settings AI and Telemetry rows now read labels, descriptions, descriptive provider options, telemetry buffer copy, and telemetry toasts from `settings` / `common` i18n keys with Spanish unit coverage and a Firefox smoke of the persisted Spanish language path.
- Settings palette toasts now read from locale keys, and feature flags can opt into localized labels/descriptions with fallback search preserving the original English label/description.
- Bottom console tabs, empty states, queue/history run controls, status chips, report actions, and preview affordances now read from `console` i18n keys with Spanish unit coverage.
- Bottom console history buckets now format older same-year month headings with the active i18n language instead of the browser default locale, so Spanish history groups render `mayo` rather than `May`.
- Bottom console history-card completion timestamps now also use the active i18n language instead of the browser default locale, keeping run metadata formatting consistent with localized bucket headings.
- App-level console queue/history confirmations, fallback run names, retry labels, and toast/error feedback now read from `console.actions` i18n keys with Spanish unit coverage.
- Workflow run submission now uses the active locale's untitled fallback for unnamed `/runs` payloads, so Spanish sessions queue `Sin titulo` instead of the raw English default while keeping stored workflow sentinels unchanged.
- Workflow WebSocket run-failure toast titles, workflow fallback names, and console-detail fallback messages now read from `console.actions` i18n keys with Spanish unit coverage.
- Help wiki panel chrome, search headings/no-results copy, page navigation labels, node-source hints, and generated node documentation labels now read from `helpWiki` i18n keys with Spanish unit coverage; embedded static article HTML remains deferred.
- Output comparison modal title, run pickers, loading/empty states, summary counts, section headings, error labels, and footer action now read from `outputDiff` / `common` i18n keys with Spanish unit coverage.
- Output comparison modal run-start timestamps now format with the active i18n language instead of the browser default locale, so Spanish summaries use day/month ordering and 24-hour time consistently.
- Bulk parameter modal title, shared-parameter header, no-common-parameter states, pluralized apply action, varies placeholder, and reset-field tooltip now read from `paramBulk` / `common` i18n keys with Spanish unit coverage.
- Workflow doctor modal title, severity summaries, healthy/empty states, diagnostic finding titles/details, jump action, and footer close action now read from `doctor` / `common` i18n keys with Spanish unit coverage.
- Batch sample-sheet modal title, helper copy, upload/name controls, sheet summary, column mapping controls, preview heading, validation errors, and queue/submitting actions now read from `batchSampleSheet` / `common` i18n keys with Spanish unit coverage.
- Import modal title, helper text, parse/error alerts, parsing state, and footer actions now read from `importModal` / `common` i18n keys with Spanish unit coverage.
- Export modal title, format tabs, PNG option copy, generation actions, thumbnail alt text, converter fallback copy, and footer actions now read from `exportModal` / `common` i18n keys with Spanish unit coverage.
- HTML preview modal toolbar save/open/close tooltips and accessible action labels now read from `htmlPreview` / `common` i18n keys with Spanish unit coverage.
- Image lightbox close/previous/next/save image tooltips and accessible action labels now read from `imageLightbox` / `common` i18n keys with Spanish unit coverage.
- Missing dependency banner title, fallback summary, env status, install/detail/dismiss controls, job fallback text, and expanded report headings now read from `resolveReport` / `common` i18n keys with Spanish unit coverage.
- Host prerequisite banner title, fallback summary, Pixi install controls/status messages, detail/dismiss controls, host-check heading, and manual/auto-install hints now read from `hostStatus` / `common` / `resolveReport` i18n keys with Spanish unit coverage.
- Node context menu node/canvas actions, shape/preset/subgraph actions, and color-submenu back action now read from `nodeContextMenu` / `common` i18n keys with Spanish unit coverage.
- Node palette chrome, typed-add headings, search summaries, recent controls, category affordances, fallback category labels, and empty states now read from `nodePalette` i18n keys with Spanish unit coverage.
- Node editor and node info panel section headings, advanced controls, file-drop placeholders, documentation links, metadata labels, and parameter detail labels now read from `nodeDetails` i18n keys with Spanish unit coverage.
- Node info panel header metadata now reuses the shared node-category label mapping, so categories such as `Quality Control` render as `Control de calidad` under Spanish instead of leaking registry labels into the read-only panel.
- Share dialog title, offline notice, invite controls, room-link copy/actions, share-list states, role labels, revoke/close actions, and copy-link toasts now read from `collab` / `common` i18n keys with Spanish unit coverage.
- Node comment popover title, close affordance, reply/resolve/post actions, placeholders, fallback errors, and relative-time labels now read from `collab` i18n keys with Spanish unit coverage.
- Comments panel title, close/filter controls, loading/empty states, comment actions, relative-time labels, reply controls, placeholders, and fallback errors now read from `collab` / `common` i18n keys with Spanish unit coverage.
- Collaboration badge status text, tooltip labels, offline/link actions, menu navigation, follow-viewport copy, and workflow fallbacks now read from `collab` i18n keys with Spanish unit coverage.
- Audit log title, export action, summaries, filters, loading/empty states, table headers, pagination labels, and common action/target labels now read from `collab` / `common` i18n keys with Spanish unit coverage.
- Collaboration user list title, close affordance, empty state, role chips, current-user suffix, workflow fallback, access menu, and role-change/remove errors now read from `collab` / `common` i18n keys with Spanish unit coverage.
- Collaboration auth dialog title, helper copy, display-name controls, join/guest actions, secure-session hint, and fallback errors now read from `collab` i18n keys with Spanish unit coverage.
- Collaboration token failures now use structured auth errors and render API/missing-token fallback messages from `collab` i18n keys in the auth dialog with Spanish coverage.
- Follow-user control titles, followed-user copy, active-user heading/empty state, activity labels, and follow/unfollow actions now read from `collab` i18n keys with Spanish unit coverage.
- App-level collaboration create-link, join-link, leave-session, connected-role, invalid-link, and workflow-fallback copy now reads from `collab` i18n keys with Spanish helper coverage and an App wiring guard.
- App-level shared-template save unavailable alert, success toast, and fallback error now read from `collab` i18n keys with Spanish helper coverage and an App wiring guard.
- App-level pasted and dropped workspace file feedback now reads from `workspace` i18n keys with Spanish unit coverage and an App wiring guard.
- Workspace upload-failure feedback now has a Spanish translation for the existing `workspace.uploadFailed` key instead of falling back to the English "Upload failed" toast copy.
- Workspace upload labels, drop hints, progress copy, and success copy now have Spanish translations under the existing `workspace` i18n keys.
- App-level snippet save/insert prompts, default names, command labels, and toasts now read from `snippets` i18n keys with Spanish unit coverage and an App wiring guard.
- App-level workflow duplicate, close-unsaved, import, URL-load, and recent-command fallbacks now read from `workflowTabs`, `workflowImport`, and `commandPalette` i18n keys with Spanish unit coverage and an App wiring guard.
- Comment pins and selection toolbox action tooltips now read from `collab` and `canvas` i18n keys with Spanish component coverage and static wiring guards.
- Group context menu labels, color submenu back action, and rename prompt copy now read from `canvas` i18n keys with Spanish component coverage and a static wiring guard.
- Modal shell lazy-loading labels and bulk-parameter success toasts now read from `outputDiff`, `doctor`, and `paramBulk` i18n keys with Spanish unit coverage and a static wiring guard.
- Workflow canvas node rename, subgraph-library, and parameter-preset prompts/toasts now read from `canvas` i18n keys with Spanish unit coverage and a static wiring guard.
- Workflow canvas hover-card metadata plus canvas/link context-menu labels now read from `canvas` i18n keys with Spanish coverage and a static wiring guard.
- Workflow canvas generated group and reroute fallback names now read from `canvas` i18n keys, so newly created groups and reroute nodes use the active locale instead of embedding raw English defaults.
- Workflow canvas widget-copy hints and node-error popover labels now read from `canvas`/`errors` i18n keys with Spanish coverage and a static wiring guard.
- Workflow stats overlay labels, fallback category, collapse/expand titles, and compact pill units now read from `workflowStats` i18n keys with Spanish render coverage and a static wiring guard.
- Workflow stats overlay category chips now reuse the shared node-category label mapping, so registered categories such as `Input` and `Quality Control` render as `Entrada` and `Control de calidad` under Spanish while unknown categories still use the localized fallback.
- Getting-started modal shell, tabs, welcome intro, footer checkbox, and close button now read from `gettingStarted`/`common` i18n keys with Spanish render coverage and a static wiring guard.
- HPC panel form placeholders and job-script workflow placeholder comments now read from `hpc` i18n keys with Spanish render coverage.
- Getting-started resources tab link titles and descriptions now read from `gettingStarted.resources` i18n keys with Spanish render coverage and a static wiring guard.
- Getting-started quick-start guidance and AI-assistant tip now read from `gettingStarted` i18n keys with Spanish render coverage and a static wiring guard.
- Getting-started recent-workflow controls, row metadata, and release-status chrome now read from `gettingStarted` i18n keys with Spanish render coverage and a static wiring guard.
- Getting-started recent-workflow absolute dates now format with the active i18n language instead of the browser default locale, keeping older recent rows consistent with Spanish metadata.
- AI workflow assistant drawer title, default session/greeting, and session-menu chrome now read from `aiWorkflow` / `common` i18n keys with Spanish render coverage and a static wiring guard.
- AI workflow assistant quick prompts and basic input controls now read from `aiWorkflow` i18n keys with Spanish render coverage and a static wiring guard.
- AI workflow assistant step controls, tool-result labels, and proposed-change actions now read from `aiWorkflow` i18n keys with Spanish render coverage and a static wiring guard.
- AI workflow assistant thinking, stop, and regenerate controls now read from `aiWorkflow` i18n keys with Spanish render coverage and a static wiring guard.
- AI workflow assistant apply-success confirmation now reads from `aiWorkflow` i18n keys with Spanish render coverage and a static wiring guard.
- AI workflow assistant pasted-canvas-node prompt text now reads from `aiWorkflow` i18n keys with Spanish render coverage and a static wiring guard.
- AI workflow assistant stopped-by-user note now reads from `aiWorkflow` i18n keys with Spanish render coverage and a static wiring guard.
- AI workflow assistant local fallback responses now read from `aiWorkflow` i18n keys with Spanish render coverage for RNA-Seq, variant-calling, and default branches plus a static wiring guard for all fallback branches.
- AI workflow proposed changes now preserve the active workflow metadata when the AI response omits workflow-level fields, while still honoring explicit proposed names and metadata.
- Workflow Trigger schedule registrations now validate five-field cron expressions, validate IANA timezones, calculate the next local and UTC run times, and persist that scheduling metadata with the recorded trigger intent.
- Help/Wiki getting-started article content now reads from `helpWiki` i18n keys with Spanish render and search coverage plus a static wiring guard.
- Help/Wiki canvas-features article content now reads from `helpWiki` i18n keys with Spanish render and search coverage plus a static wiring guard.
- Help/Wiki nodes-reference article content now reads from `helpWiki` i18n keys with Spanish render and search coverage plus a static wiring guard.
- Help/Wiki templates-guide article content now reads from `helpWiki` i18n keys with Spanish render and search coverage plus a static wiring guard.
- Help/Wiki custom-nodes article content now reads from `helpWiki` i18n keys with Spanish render and search coverage plus a static wiring guard.
- Help/Wiki hpc-integration article content now reads from `helpWiki` i18n keys with Spanish render and search coverage plus a static wiring guard.
- Help/Wiki workflow-converters article content now reads from `helpWiki` i18n keys with Spanish render and search coverage plus a static wiring guard.
- Help/Wiki keyboard-shortcuts article content now reads from `helpWiki` i18n keys with Spanish render and search coverage plus a static wiring guard.
- Live collaboration authorization and WebSocket fallback errors now read from `collab` i18n keys with Spanish unit coverage and a `useCollab` static wiring guard.
- Canvas zoom/fit/minimap/link/auto-arrange controls now read from `canvas` i18n keys with Spanish unit coverage.
- Template gallery drawer title, save/close/search/tag chrome, loading/empty states, author/time labels, and fork actions now read from `collab` i18n keys with Spanish unit coverage.
- Template gallery load/fork/save fallback errors and save-template prompt dialogs now read from `collab` / `common` i18n keys with Spanish unit coverage.
- Version history drawer title, save/close affordances, loading/empty states, auto/manual labels, fallback version names, metadata, relative-time labels, and row actions now read from `collab` / `common` i18n keys with Spanish unit coverage.
- Version history save prompt, restore/delete confirmations, fallback errors, diff-load errors, and diff auto-save fallback names now read from `collab` / `common` i18n keys with Spanish unit coverage.
- Version diff modal title, close affordance, changed counts, empty state, node/edge/group/meta labels, and footer summaries now read from `collab` / `common` i18n keys with Spanish unit coverage.
- Runtime artifact checkpoint headings, fallback labels, resolved-state labels, and counts now read from translated Spanish `runtimeArtifacts` copy with panel render coverage.
- Runtime artifact workflow-trigger headings, action labels, fallback labels, and due/count summaries now use Spanish `disparador` wording with panel render coverage.
- HPC scheduler backend label now renders as Spanish `Sistema de colas` with panel coverage.
- Console log and preview empty states now use Spanish `flujo de trabajo` wording with BottomConsole coverage.
- Design token documentation now covers the complete 66-token palette contract from `ALL_PALETTE_TOKENS`, derived-token behavior, semantic token groups, current built-in canvas pattern mappings, and custom palette authoring guidance. The palette test suite now guards `docs/DESIGN_TOKENS.md` against missing CSS custom properties or stale built-in pattern rows.
- ForEach executor body runs now inject declared hidden loop runtime inputs (`_loop_state`, `_iteration`) into body nodes while still filtering undeclared internal `_` metadata. `counter_accumulator` can now maintain shared accumulator state across real foreach iterations instead of only in direct node-level calls, with executor coverage for accumulating `["S1", "S2", "S3"]` through the loop body.
- TypeScript strictness now has a config-contract test that guards `strict`, `noUnusedLocals`, `noUnusedParameters`, `noImplicitOverride`, and `verbatimModuleSyntax` in `web/tsconfig.json`, so the strict-flag gap cannot silently regress.
- Settings hooks now live under `web/src/hooks/settings/` with a category barrel; App, SettingsPanel, WorkflowCanvas, and `useTheme` import from the category instead of the old top-level `useSettings` path. The hooks organization test now guards the settings category alongside workflow/collab.
- Data hooks now live under `web/src/hooks/data/` with a category barrel; App imports `useObjectInfo` from the category, and the API-migration guard follows the moved path.
- Shared UI hooks now live under `web/src/hooks/ui/` with a category barrel; App, layout controls, dialogs, keyboard shortcuts, and modal focus traps import command-palette/keybinding/focus-trap hooks from the category.
- Node versioning now has an explicit lifecycle contract for node authors: `BaseNode` exposes previous versions, deprecation metadata, replacement hints, and migration descriptors; `NodeRegistry.object_info()` and saved node manifests preserve those fields, and the frontend object-info hook keeps them available to UI/plugin consumers.
- Workflow validation now emits non-blocking warnings when a saved node's cached `node_info.version` differs from the currently registered node version, giving users upgrade/drift visibility without preventing existing workflows from running.
- Custom node packaging now has a concrete `bionodulo.toml` manifest contract: the manager can parse required package name/version fields, optional repository/entrypoints/requirements metadata, and list manifest-backed plus legacy custom-node installs.
- Workflow parameters now have a passive schema foundation: backend workflow JSON preserves parameter definitions, validation rejects malformed or duplicate parameter names, frontend workflow validation keeps parameter metadata, new workflows initialise `parameters: []`, and history signatures track parameter-only edits.
- Scatter Plot now has an interactive HTML output mode alongside PNG/SVG: it emits a Plotly-backed `scatter_plot.html`, preserves the existing `plot_image` output name for compatibility, registers HTML previews through the existing preview pipeline, and keeps static image formats as the default.
- Line Chart now has a matching interactive HTML output mode: multi-series traces render through Plotly with line style, marker, grid, palette, and axis metadata preserved, while the existing `chart_image` output and PNG/SVG defaults remain compatible.
- Bar Chart now has an interactive HTML output mode as well: grouped vertical and horizontal bars render through Plotly, preserve value labels and group colors, keep the existing `chart_image` output path, and were browser-checked with Playwright against a generated HTML artifact.
- Heatmap now supports interactive HTML output through Plotly while preserving clustering, row/column scaling, labels, colour-scale choices, the existing `heatmap_image` output name, and PNG/SVG defaults. The generated HTML artifact was browser-checked with Playwright.
- Volcano Plot now supports interactive HTML output through Plotly: Up/Down/NS points render as separate traces, threshold lines and top-gene labels are preserved, the existing `volcano_image` output name remains compatible, and the generated HTML artifact was browser-checked with Playwright.
- MA Plot now supports interactive HTML output through Plotly: significant and non-significant genes render as separate traces, fold-change threshold guides and top-gene labels are preserved, the existing `ma_image` output name remains compatible, and the generated HTML artifact was browser-checked with Playwright.
- Manhattan Plot now supports interactive HTML output through Plotly: genome-offset GWAS points render with chromosome ticks, genome-wide/suggestive threshold annotations, top-SNP labels, the existing `manhattan_image` output name, and PNG/SVG defaults preserved. The generated HTML artifact was browser-checked with Playwright.
- Coverage Plot now supports interactive HTML output through Plotly: coverage intervals render as width-aware bars with structured region/depth hover data, the existing `coverage_image` output name remains compatible, and the generated HTML artifact was browser-checked with Playwright.
- VCF Stats Chart now supports interactive HTML output through Plotly: variant-type, quality-distribution, Ti/Tv, and chromosome-count panels render as an interactive dashboard while preserving the `stats_image` plus `stats_json` outputs. The generated HTML artifact was browser-checked with Playwright.
- Forest Plot now supports interactive HTML output through Plotly: study estimates render with confidence intervals, pooled rows use diamond markers, weights are kept in hover data, and the existing `forest_image` output name plus PNG/SVG defaults remain compatible. The generated HTML artifact was browser-checked with Playwright.
- Phylogenetic Tree Viewer now supports interactive HTML output through Plotly: Newick branch geometry, tip labels, and bootstrap annotations render interactively while preserving the existing `tree_image` output name and PNG/SVG defaults. The generated HTML artifact was browser-checked with Playwright.
- Circos Plot now supports interactive HTML output through Plotly: chromosome sectors plus gene, variant, and CNV tracks render as interactive polar traces while preserving the existing `circos_image` output name and PNG/SVG defaults. The generated HTML artifact was browser-checked with Playwright.
- IGV Snapshot now supports interactive HTML output through Plotly: variant and annotation tracks render against a shared genomic coordinate axis while preserving the existing `snapshot_image` output name and PNG/SVG defaults. The generated HTML artifact was browser-checked with Playwright.
- Notification workflow nodes now support real SMTP email delivery when SMTP host/from/to settings are supplied directly or through `BIONODULO_SMTP_*` environment variables, while missing SMTP configuration still skips safely and delivery metadata redacts credentials.

---

## Pending / future waves

Items from the gap analysis that haven't landed yet:

- #6 UI primitives library (Radix UI) — large scope.
- #12 i18n string externalisation — partial: infrastructure/dictionaries exist; migrate remaining hard-coded UI strings surface by surface.
- #15 ESLint + Prettier setup — DONE in Wave O.§5.
- #19 Strict TS checks (`noUnusedLocals`, `verbatimModuleSyntax`) — DONE (compiler flags enabled and guarded by a config-contract test).
- #49 Extension/plugin system — large scope.
- #65 Dynamic help — DONE (selected-node docs plus full node-doc search/open from Help results).
- #66 Telemetry — DONE in Wave G; remote-sink integration deferred.
- #85 Reorganise hooks into category folders — DONE for current hook tree (workflow, collab, settings, data, and UI categories).
- #86 Design tokens documented — DONE (CSS custom property reference guarded by palette tests).
- First-party raw `/api` fetch migration — DONE; the GitHub releases request remains intentionally outside `api/client.ts` because it targets an external host.

---

## Operating notes

- Commits attributed only to `classacre <nieuwenhuyzenmikamartin@gmail.com>`.
- Each wave: implement → build green → commit → push to `bionodulo-collab` on `Classacre/BioNodulo`.
- "Next wave" from the user starts a fresh batch; mid-wave "commit and push" confirms the partial scope.
