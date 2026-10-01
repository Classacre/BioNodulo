# BioNodulo cloud app MCP adapter

The MCP resource mounts the existing `App.tsx`: the same top bar, navigation,
workflow tabs, canvas, toolbox, templates, settings, cloud workspace, assistant
panel and run history. There is no separate workbench UI, reducer or stylesheet.

## Bootstrap and transport

The resource sets `<html data-mcp-app="true">` (development also accepts
`?mcp_app=1`). `index.tsx` connects the MCP Apps SDK 1.7.5 host, verifies the
account and team, seeds cloud/editor mode, then imports the full App. This skips
local backend sockets, Clerk browser authentication and local room bootstrap.

The existing typed editor and website API clients use `cloud_editor_request`:
`{surface, path, method, body?, team_id?}` returns `{status, body, content_type}`.
The server allowlists cloud operations and enforces OAuth scopes and existing
team/role checks. Browser tokens, cookies and arbitrary URL proxies are absent;
`fetch` is not patched. The resource URI is `ui://bionodulo/cloud-app/v2` and its
assets are pinned to the published editor release. Links and fullscreen use the
host SDK when supported.

## Files, workflows and the host assistant

Workspace shows cloud files. Browser uploads use credential-free HTTPS PUT to a
presigned URL whose exact origin is enabled by the resource. `complete_upload`
must verify the bytes before a key becomes ready. Dragging a verified upload to
the canvas creates the usual input-file node. Cloud runs bind uploaded keys from
the selected team's file listing; local filesystem staging is desktop-only.

The existing workflow hook owns tabs, autosave, undo/redo and creation retries.
Writes carry the saved revision. Eight-second polling adopts host changes in a
clean tab; a changed remote revision preserves a dirty draft and offers explicit
Load latest recovery. A stale read cannot advance a dirty draft's baseline.

The shared AI panel sends messages to the host assistant, together with redacted
workflow context. Failed sends are visible and retryable. It does not create a
second private AI conversation. The host's regular MCP tools can edit the same
saved workflow, and those edits appear in the editor.

## Cloud execution

Each paid submission reads the current credit balance and matching CPU/GPU cost
estimate, then requires explicit confirmation of workflow, team, compute and
rate. Cancellation or a changed team/revision sends no run. One confirmation
allows one attempt; an uncertain response is never automatically retried.
Automatic execution queues are disabled in cloud editor mode.

The existing canvas, console and Runs drawer render cloud status and durable
logs. Completed output manifests must be server-verified. Downloads request a
fresh verified URL and open it through the host. The drawer also shows reported
credits and duration. Local environments and HPC controls remain desktop-only.

## Verification

From `web/`:

```text
npm run build
node node_modules/vitest/vitest.mjs run
node node_modules/@playwright/test/cli.js test --config=e2e/mcp-workbench.config.ts --reporter=line
```

The browser suite mounts production chunks inside a postMessage MCP host fixture,
exercises the actual App and verifies that no direct editor/account API requests
or local WebSockets occur. It covers editing, guarded saves, catalog search,
imports/exports, host assistant, cloud uploads, paid confirmation, run monitoring,
verified outputs and narrow layouts. Mock host tests do not prove native ChatGPT
or Claude rendering, OAuth deployment, or paid provider execution; report those
separately in the release audit. The catalog remains discoverable metadata,
not proof that every bioinformatics tool has executed.
