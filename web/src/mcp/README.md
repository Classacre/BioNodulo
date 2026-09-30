# Embedded BioNodulo workbench

This entry renders the existing `WorkflowCanvas`, `BioNode`, widgets, properties,
edges, layout and selection behavior. Catalog metadata is normalized by the same
pure `normalizeObjectInfo` function as the main app. Search and categories reuse
the normal node-search and category helpers. No replacement graph is maintained.

## Host and resource contract

- Pin `@modelcontextprotocol/ext-apps` **1.7.5** (the MCP SDK 1.x line).
- The HTML resource sets `<html data-mcp-app="true">`. Local development also
  accepts `?mcp_app=1`. `main.tsx` loads this branch dynamically without importing
  the normal `App` entry or mounting its Clerk, Yjs, settings API or run sockets.
- One `App` instance connects directly to the parent host. There is no inner
  iframe and no access token, cookie or direct account API transport.
- `open_bionodulo` sends `structuredContent` containing optional `workflow_id`,
  `team_id`, `run_id`, and a full `workflow` record. An opening result arriving
  before initialization completes is retained by the adapter.
- `get_editor_catalog` returns `{ catalog: rawObjectInfo }`. List tools return
  `{ items: [...] }`. Workflow records have `id`, `name`, `description`,
  `definition`, and ISO `updatedAt`.
- All account, workflow, catalog, file metadata, validation, conversion, billing
  and run operations use `App.callServerTool`. The sole direct fetch is a
  credential-free HTTPS PUT to a server-issued presigned upload URL. Its exact
  origin must occur in `<meta name="bionodulo-upload-origins" content="...">`.
  Redirects are rejected; `complete_upload` must succeed before an input is ready.
- Uploaded inputs are bound explicitly through `inputs.artifacts` on submission.
  Team ownership and byte verification remain server responsibilities.
- Resource CSP must allow the deployed build assets; cross-origin module assets
  need CORS headers. PUT origins need resource `connectDomains` and object-store
  CORS that permits the host iframe's origin. No extra font origins are necessary:
  the shared stylesheet's remote font import can fall back to system fonts.

## Editing, consent, and live updates

Manual edits remain in a local draft until Save. Updates send
`expected_updated_at`; creations retain an idempotency UUID until a confirmed
response. An in-flight save cannot discard newer edits. An old poll cannot
regress a newer saved revision. Visible-only workflow polling runs every eight
seconds. A dirty draft encountering a remote edit displays a conflict with
explicit discard/load-latest or save-copy choices. The host model receives a
debounced draft/selection/run context, with secret fields and URL credentials or
query signatures removed. Run output download URLs are not included in context.
The assistant composer sends a user message to the host, not to a private model.

Run review requires a saved conflict-free draft, server validation, a positive
credit balance and an allowed compute estimate. Default CPU compute is custom
1 vCPU / 4 GB RAM; bounds and eligibility come from the server. The dialog shows
the team, workflow, compute, balance and rate, and explains that duration controls
the total. Only its confirmation button sends `confirm_credit_use: true` and
`expected_workflow_updated_at`. One confirmation authorizes one attempt. An
uncertain result is displayed and never automatically retried.

Active runs poll persisted status and paginated events every five seconds while
visible. Terminal event pages are drained. Completed outputs are requested from
`get_run_outputs`, which exposes only server-verified committed artifacts. Cancel
has a separate confirmation. Fullscreen appears only when the host advertises it.

## Verification, 2026-10-01

From `web/` (Node 24.13.0 on the audit host):

```text
npm run build
node node_modules/vitest/vitest.mjs run src/mcp/draft.test.ts src/test/useObjectInfo.test.tsx
node node_modules/@playwright/test/cli.js test --config=e2e/mcp-workbench.config.ts --reporter=line
```

- Production build **0.1.1-alpha.6** passed: 675 modules. Vite reports the
  existing large App/Clerk chunks; those are not mounted in the MCP branch.
- **17 unit tests passed**: 13 new draft/adapter/privacy checks and four existing
  object-info hook regressions.
- **Five browser scenarios passed against production chunks**, with a real
  postMessage MCP host fixture and actual canvas components: editing/layout/save,
  host assistant/fullscreen, external updates and conflict preservation,
  confirmed compute plus fast completion/output monitoring, no automatic retry
  after uncertain submission, verified input selection, export and narrow layout.
  The fixture uses the injected HTML marker without a query flag.
- Desktop and narrow screenshots are generated under `web/test-results/` and were
  visually inspected. Native dropdowns retain their original canvas styling.
- Browser assertions verify no direct account/editor API request or normal App
  entry load. These are transport/UI tests with mocked cloud responses, not a
  real paid-cloud execution or an object-store upload test.
- `git diff --check` passes for changed tracked app sources and dependency files.

The parent host in the browser fixture is test infrastructure; it is not shipped
as a second iframe inside the app. The production preview test server uses port
5175 and stops when Playwright finishes.

## Deliberate boundaries

Local filesystem browsing, local/HPC execution, local environment management,
Yjs invitations, embedded model credentials, GPU execution and account/billing
administration are not presented as supported workbench controls. Cloud file or
workflow deletion remains available through the host's separately authorized
tools. Team selection is supplied by `open_bionodulo`; the selected team is shown
in the UI. The catalog is discoverable metadata, not proof every node has run.

Unsaved drafts are protected during refresh, switching and saves within the
mounted app. They are not a durable cross-session store: save before closing the
host conversation. Event display retains the latest 1,000 events; full persisted
run logs remain visible. A host that cannot update model context can still accept
explicit user messages. Live deployed host rendering, OAuth permissions, storage
CORS and paid execution require the separate website/release verification.
