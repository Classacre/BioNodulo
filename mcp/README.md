# BioNodulo MCP Server

An [MCP](https://modelcontextprotocol.io) server (built with
[FastMCP](https://gofastmcp.com)) that exposes the **BioNodulo platform** —
the cloud app at [bionodulo.com](https://bionodulo.com) and, optionally, a
locally running BioNodulo desktop app — to AI agents and chat clients
(Claude, Codex/ChatGPT, Cursor, …).

## What it covers

| Area | Tools |
|---|---|
| **Account** | `get_account_info`, `get_service_health` |
| **Billing & credits** | `get_credit_balance`, `get_credit_usage`, `get_usage_analytics`, `estimate_run_cost`, `list_invoices` |
| **Runs (cloud)** | `list_runs`, `get_run_status`, `get_run_events`, `get_run_outputs`, `submit_run`, `cancel_run` |
| **Workflows** | `list_workflows`, `get_workflow`, `create_workflow`, `update_workflow`, `delete_workflow` |
| **Files** | `list_files`, `get_upload_url`, `delete_file` |
| **Hosted AI** | `get_ai_analysis`, `chat_with_bionodulo_ai` |
| **Collab & team** | `list_collab_invites`, `create_collab_invite`, `revoke_collab_invite`, `invite_team_member` |
| **Desktop app** (local) | `desktop_status`, `desktop_list_node_types`, `desktop_get_node_info`, `desktop_list_templates`, `desktop_validate_workflow`, `desktop_submit_run`, `desktop_get_run`, `desktop_get_run_logs`, `desktop_get_queue`, `desktop_get_history`, `desktop_get_system_stats` |

Plus resources (`bionodulo://account`, `bionodulo://credits`,
`bionodulo://runs`) and prompts (`run_status_report`,
`troubleshoot_failed_run`, `plan_cloud_run`).

## Install

```bash
cd mcp
uv sync
```

## Configuration

| Env var | Purpose |
|---|---|
| `BIONODULO_API_URL` | Cloud API base URL (default `https://bionodulo.com`) |
| `BIONODULO_AUTH_TOKEN` | A pre-minted Clerk session JWT (short-lived) |
| `CLERK_SECRET_KEY` | Clerk backend secret — enables **automatic token refresh** |
| `BIONODULO_USER_EMAIL` / `BIONODULO_USER_ID` | Which Clerk user to mint session tokens for |
| `BIONODULO_TEAM_ID` | Optional `X-Team-Id` override (defaults to first team) |
| `BIONODULO_DESKTOP_URL` | Local desktop backend (default `http://127.0.0.1:8765`) |
| `BIONODULO_DESKTOP` | Set to `0` to disable the `desktop_*` tools |
| `BIONODULO_MCP_TOKEN` | Require this bearer token on the HTTP transport |

Authentication: the cloud API accepts a Clerk session JWT as a bearer token.
Because session JWTs are short-lived, the recommended setup is
`CLERK_SECRET_KEY` + `BIONODULO_USER_EMAIL`: the server mints and refreshes
10-minute session tokens from the user's most recently active Clerk session
(preferring sessions with an active organization), entirely server-side.
Alternatively pass a fixed `BIONODULO_AUTH_TOKEN`.

## Connect your client

### One-shot installer (Claude Code, Claude Desktop, Codex)

```bash
uv run bionodulo-mcp install \
  --clerk-secret-key sk_live_... \
  --user-email you@example.com
```

This writes/merges:

- **Codex CLI, Codex IDE extension & ChatGPT desktop app** → `~/.codex/config.toml`
  (`[mcp_servers.bionodulo]`). Verify with `codex mcp list`, and use `/mcp` in
  a Codex session to confirm the tools are visible.
- **Claude Desktop** → `claude_desktop_config.json` (restart Claude Desktop
  afterwards).
- **Claude Code** → registered at user scope via `claude mcp add`
  (verify with `claude mcp list`).

Use `--client claude-code|claude-desktop|codex` to install just one.

### Codex (manual)

```bash
codex mcp add bionodulo \
  --env CLERK_SECRET_KEY=sk_live_... \
  --env BIONODULO_USER_EMAIL=you@example.com \
  -- uv --directory /path/to/BioNodulo/mcp run bionodulo-mcp
```

### Claude Code (manual)

```bash
claude mcp add bionodulo --scope user \
  --env CLERK_SECRET_KEY=sk_live_... \
  --env BIONODULO_USER_EMAIL=you@example.com \
  -- uv --directory /path/to/BioNodulo/mcp run bionodulo-mcp
```

### Claude Desktop (manual)

`%APPDATA%\Claude\claude_desktop_config.json` (Windows),
`~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):

```json
{
  "mcpServers": {
    "bionodulo": {
      "command": "uv",
      "args": ["--directory", "/path/to/BioNodulo/mcp", "run", "bionodulo-mcp"],
      "env": {
        "CLERK_SECRET_KEY": "sk_live_...",
        "BIONODULO_USER_EMAIL": "you@example.com"
      }
    }
  }
}
```

### ChatGPT web & Claude.ai web (remote connectors)

Web chat clients can't spawn local processes — they need the server exposed
over **HTTPS** with the streamable-HTTP transport:

```bash
# 1. Run the server over HTTP (set a token to protect the endpoint)
export BIONODULO_MCP_TOKEN=$(openssl rand -hex 32)
export CLERK_SECRET_KEY=sk_live_...
export BIONODULO_USER_EMAIL=you@example.com
uv run bionodulo-mcp serve --transport http --host 0.0.0.0 --port 8787

# 2. Expose it publicly, e.g. with a Cloudflare tunnel
cloudflared tunnel --url http://localhost:8787
```

Then, using `https://<your-host>/mcp`:

- **ChatGPT**: Settings → Apps → Advanced → enable *Developer Mode* →
  **Create app**, paste the `/mcp` URL, choose authentication (bearer token
  via advanced settings, or none for a local tunnel you control).
- **Claude.ai**: Customize → Connectors → **Add custom connector**, paste the
  `/mcp` URL.

> Keep `BIONODULO_MCP_TOKEN` set whenever the endpoint is reachable from the
> internet — it gates every MCP request with `Authorization: Bearer`.

## Test

```bash
CLERK_SECRET_KEY=sk_live_... BIONODULO_USER_EMAIL=you@example.com \
  uv run python scripts/test_live.py
```
