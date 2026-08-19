"""BioNodulo MCP server.

Exposes the BioNodulo cloud platform (bionodulo.com — the website and cloud
backend) and, optionally, a locally running BioNodulo desktop app as MCP
tools for AI agents.

Covers: user account, teams, credits/billing, workflow runs and their
status, workflows, files, hosted AI, collaboration invites, and the local
desktop execution engine (run queue, node catalog, templates, run logs).
"""

from __future__ import annotations

import functools
import json
from typing import Any

import os

from fastmcp import FastMCP

from .auth import AuthError, build_token_provider
from .client import ApiError, CloudClient, DesktopClient
from .config import load_settings


def _http_auth():
    """Optional bearer-token auth for the HTTP transport.

    When serving over HTTP (e.g. for ChatGPT / Claude.ai connectors or a
    shared team deployment), set BIONODULO_MCP_TOKEN to require
    ``Authorization: Bearer <token>`` on every MCP request. Stdio transport
    never uses this (the parent process owns the pipe).
    """
    token = os.environ.get("BIONODULO_MCP_TOKEN")
    if not token:
        return None
    from fastmcp.server.auth import StaticTokenVerifier

    return StaticTokenVerifier(
        tokens={token: {"client_id": "bionodulo-mcp-user", "scopes": []}}
    )


mcp = FastMCP(
    "BioNodulo",
    auth=_http_auth(),
    instructions=(
        "BioNodulo is a visual bioinformatics workflow platform. Use these tools "
        "to inspect the user's account, credits and billing, list and manage "
        "cloud workflow runs (submit, poll status, fetch events/outputs, cancel), "
        "manage workflows and files, use the hosted AI, manage collaboration "
        "invites and team members, and — when the desktop app is running — "
        "interact with the local execution engine (desktop_* tools)."
    ),
)

_settings = load_settings()
_cloud: CloudClient | None = None
_desktop: DesktopClient | None = None


def _cloud_client() -> CloudClient:
    global _cloud
    if _cloud is None:
        provider = build_token_provider(
            auth_token=_settings.auth_token,
            clerk_secret_key=_settings.clerk_secret_key,
            clerk_user_id=_settings.clerk_user_id,
            clerk_user_email=_settings.clerk_user_email,
        )
        _cloud = CloudClient(
            base_url=_settings.api_url, token_provider=provider, team_id=_settings.team_id
        )
    return _cloud


def _desktop_client() -> DesktopClient:
    global _desktop
    if _desktop is None:
        if not _settings.desktop_enabled:
            raise ApiError(
                "Desktop integration is disabled (BIONODULO_DESKTOP=0). "
                "Enable it or use the cloud tools instead."
            )
        _desktop = DesktopClient(_settings.desktop_url)
    return _desktop


def _guard(func):
    """Convert API/auth errors into structured tool results."""

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except (ApiError, AuthError) as exc:
            return {"ok": False, "error": str(exc)}

    return wrapper


# ---------------------------------------------------------------------------
# Account, health & billing
# ---------------------------------------------------------------------------


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
@_guard
async def get_account_info() -> Any:
    """Get the signed-in BioNodulo user's account info.

    Returns the user's id, name, email and current team (id + name).
    """
    return await _cloud_client().get("/api/me")


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
@_guard
async def get_service_health() -> Any:
    """Check the BioNodulo cloud service health (public endpoint, no auth)."""
    return await _cloud_client().get("/api/health")


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
@_guard
async def get_credit_balance() -> Any:
    """Get the team's credit balance and plan.

    Returns monthlyCredits, usedCredits, remaining, percentUsed, the plan
    name, and the AI paper-analysis quota (aiAnalysisQuota/aiAnalysisUsed).
    """
    return await _cloud_client().get("/api/billing/credits")


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
@_guard
async def get_credit_usage() -> Any:
    """Get the team's detailed credit usage / consumption ledger."""
    return await _cloud_client().get("/api/billing/usage")


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
@_guard
async def get_usage_analytics(days: int = 30) -> Any:
    """Get dashboard usage analytics (credit consumption over time).

    Args:
        days: Lookback window in days; one of 7, 30, 90 or 180.
    """
    if days not in (7, 30, 90, 180):
        return {"ok": False, "error": "days must be one of 7, 30, 90, 180"}
    return await _cloud_client().get("/api/dashboard/usage", params={"days": days})


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
@_guard
async def estimate_run_cost(vcpu: float, ram_gb: float) -> Any:
    """Estimate the credit cost of a cloud run for a given compute size.

    Args:
        vcpu: Number of virtual CPUs.
        ram_gb: Amount of RAM in GB.
    """
    return await _cloud_client().post(
        "/api/billing/estimate", json={"compute": {"vcpu": vcpu, "ramGb": ram_gb}}
    )


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
@_guard
async def list_invoices() -> Any:
    """List the team's billing invoices (Stripe top-ups and subscriptions)."""
    return await _cloud_client().get("/api/billing/invoices")


# ---------------------------------------------------------------------------
# Runs (cloud execution)
# ---------------------------------------------------------------------------

_RESOURCE_PROFILES = "micro, small, medium, large, gpu, xlarge, extreme"


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
@_guard
async def list_runs() -> Any:
    """List the team's recent workflow runs (up to 50, newest first).

    Each run includes its id, status (queued | running | completed | failed |
    cancelled | interrupted), workflow id, timestamps and credits used.
    """
    return await _cloud_client().get("/api/runs")


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
@_guard
async def get_run_status(run_id: str) -> Any:
    """Get a run's current status snapshot.

    Returns id, status, recent logs, errorMessage (if failed), outputLocation,
    durationMs, creditsUsed, createdAt and completedAt.

    Args:
        run_id: The run id returned by submit_run or list_runs.
    """
    return await _cloud_client().get(f"/api/runs/{run_id}")


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
@_guard
async def get_run_events(run_id: str) -> Any:
    """Get the durable event ledger for a run (lifecycle and node events).

    Args:
        run_id: The run id.
    """
    return await _cloud_client().get(f"/api/runs/{run_id}/events")


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
@_guard
async def get_run_outputs(run_id: str) -> Any:
    """List the output files produced by a run (with download locations).

    Args:
        run_id: The run id.
    """
    return await _cloud_client().get(f"/api/runs/{run_id}/outputs")


@mcp.tool(annotations={"openWorldHint": True, "idempotentHint": False})
@_guard
async def submit_run(
    workflow_id: str,
    resource_profile: str | None = None,
    vcpu: float | None = None,
    ram_gb: float | None = None,
    parameters: dict[str, Any] | None = None,
    inputs: dict[str, Any] | None = None,
) -> Any:
    """Submit a workflow for cloud execution. Consumes credits.

    Returns {runId, status: "queued"} — poll with get_run_status.

    Args:
        workflow_id: Id of a saved workflow (see list_workflows).
        resource_profile: Preset size, one of RESOURCE_PROFILES. Optional.
        vcpu: Custom vCPU count (use with ram_gb instead of a profile).
        ram_gb: Custom RAM in GB (use with vcpu instead of a profile).
        parameters: Workflow parameter overrides.
        inputs: Workflow input values.
    """
    body: dict[str, Any] = {"workflowId": workflow_id}
    if resource_profile:
        allowed = [p.strip() for p in _RESOURCE_PROFILES.split(",")]
        if resource_profile not in allowed:
            return {
                "ok": False,
                "error": f"resource_profile must be one of: {_RESOURCE_PROFILES}",
            }
        body["resourceProfile"] = resource_profile
    if vcpu is not None or ram_gb is not None:
        if vcpu is None or ram_gb is None:
            return {"ok": False, "error": "vcpu and ram_gb must be provided together"}
        body["compute"] = {"vcpu": vcpu, "ramGb": ram_gb}
    if parameters:
        body["parameters"] = parameters
    if inputs:
        body["inputs"] = inputs
    return await _cloud_client().post("/api/runs", json=body)


@mcp.tool(annotations={"openWorldHint": True, "destructiveHint": True})
@_guard
async def cancel_run(run_id: str) -> Any:
    """Cancel a queued or running cloud run.

    Args:
        run_id: The run id to cancel.
    """
    return await _cloud_client().post(f"/api/runs/{run_id}/cancel")


# ---------------------------------------------------------------------------
# Workflows
# ---------------------------------------------------------------------------


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
@_guard
async def list_workflows() -> Any:
    """List the team's saved workflows (id, name, description, updated time)."""
    return await _cloud_client().get("/api/workflows")


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
@_guard
async def get_workflow(workflow_id: str) -> Any:
    """Get a saved workflow, including its node-graph definition.

    Args:
        workflow_id: The workflow id.
    """
    return await _cloud_client().get(f"/api/workflows/{workflow_id}")


@mcp.tool(annotations={"openWorldHint": True, "idempotentHint": False})
@_guard
async def create_workflow(
    name: str,
    description: str | None = None,
    definition: dict[str, Any] | None = None,
) -> Any:
    """Create a new workflow in the team's workspace.

    Args:
        name: Workflow name.
        description: Optional description.
        definition: Optional node-graph definition ({nodes: [...], edges: [...]}).
    """
    body: dict[str, Any] = {"name": name}
    if description is not None:
        body["description"] = description
    if definition is not None:
        body["definition"] = definition
    return await _cloud_client().post("/api/workflows", json=body)


@mcp.tool(annotations={"openWorldHint": True, "idempotentHint": True})
@_guard
async def update_workflow(
    workflow_id: str,
    name: str | None = None,
    description: str | None = None,
    definition: dict[str, Any] | None = None,
) -> Any:
    """Update a workflow's name, description and/or node-graph definition.

    Args:
        workflow_id: The workflow id.
        name: New name (optional).
        description: New description (optional).
        definition: New node-graph definition (optional).
    """
    body: dict[str, Any] = {}
    if name is not None:
        body["name"] = name
    if description is not None:
        body["description"] = description
    if definition is not None:
        body["definition"] = definition
    if not body:
        return {"ok": False, "error": "Provide at least one of name, description, definition"}
    return await _cloud_client().put(f"/api/workflows/{workflow_id}", json=body)


@mcp.tool(annotations={"openWorldHint": True, "destructiveHint": True})
@_guard
async def delete_workflow(workflow_id: str) -> Any:
    """Delete a workflow. This cannot be undone.

    Args:
        workflow_id: The workflow id to delete.
    """
    return await _cloud_client().delete(f"/api/workflows/{workflow_id}")


# ---------------------------------------------------------------------------
# Files
# ---------------------------------------------------------------------------


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
@_guard
async def list_files() -> Any:
    """List the team's files: uploads and run outputs, with download URLs.

    Returns up to 2000 files with presigned GET URLs.
    """
    return await _cloud_client().get("/api/files")


@mcp.tool(annotations={"openWorldHint": True, "idempotentHint": False})
@_guard
async def get_upload_url(filename: str, content_type: str = "application/octet-stream") -> Any:
    """Get a presigned URL to upload a file to the team's storage.

    Args:
        filename: Name of the file to upload.
        content_type: MIME type of the file.
    """
    return await _cloud_client().post(
        "/api/files/presign", json={"filename": filename, "contentType": content_type}
    )


@mcp.tool(annotations={"openWorldHint": True, "destructiveHint": True})
@_guard
async def delete_file(file_id: str) -> Any:
    """Delete a file from the team's storage.

    Args:
        file_id: The file id (from list_files).
    """
    return await _cloud_client().post("/api/files/delete", json={"fileId": file_id})


# ---------------------------------------------------------------------------
# Hosted AI
# ---------------------------------------------------------------------------


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
@_guard
async def get_ai_analysis(
    analysis_id: str | None = None, doi: str | None = None
) -> Any:
    """Get the status/result of an AI paper analysis (paper -> workflow).

    Analyses are started from the website's /build DOI flow. Provide exactly
    one of analysis_id or doi.

    Args:
        analysis_id: Id of a previously started analysis.
        doi: DOI of the analyzed paper (looks up your team's analysis).
    """
    if bool(analysis_id) == bool(doi):
        return {"ok": False, "error": "Provide exactly one of analysis_id or doi"}
    params = {"id": analysis_id} if analysis_id else {"doi": doi}
    return await _cloud_client().get("/api/ai/status", params=params)


@mcp.tool(annotations={"openWorldHint": True, "idempotentHint": False})
@_guard
async def chat_with_bionodulo_ai(
    message: str,
    system_prompt: str | None = None,
    model: str = "bionodulo-ai",
) -> Any:
    """Send a chat message to the hosted BioNodulo AI (OpenAI-compatible).

    Free for signed-in users subject to a global daily quota.

    Args:
        message: The user message.
        system_prompt: Optional system prompt.
        model: Model name; the service always reports 'bionodulo-ai'.
    """
    messages: list[dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": message})
    return await _cloud_client().post(
        "/api/ai/proxy/v1/chat/completions",
        json={"model": model, "messages": messages, "stream": False},
    )


# ---------------------------------------------------------------------------
# Collaboration & team
# ---------------------------------------------------------------------------


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
@_guard
async def list_collab_invites(workflow_id: str) -> Any:
    """List share-link invites for a workflow.

    Args:
        workflow_id: The workflow id.
    """
    return await _cloud_client().get(
        "/api/collab/invites", params={"workflowId": workflow_id}
    )


@mcp.tool(annotations={"openWorldHint": True, "idempotentHint": False})
@_guard
async def create_collab_invite(workflow_id: str, role: str = "viewer") -> Any:
    """Create a share link (bni_ token) for a workflow.

    Args:
        workflow_id: The workflow id.
        role: 'viewer' or 'editor'.
    """
    if role not in ("viewer", "editor"):
        return {"ok": False, "error": "role must be 'viewer' or 'editor'"}
    return await _cloud_client().post(
        "/api/collab/invites", json={"workflowId": workflow_id, "role": role}
    )


@mcp.tool(annotations={"openWorldHint": True, "destructiveHint": True})
@_guard
async def revoke_collab_invite(invite_id: str) -> Any:
    """Revoke a workflow share-link invite.

    Args:
        invite_id: The invite id (from list_collab_invites).
    """
    return await _cloud_client().delete("/api/collab/invites", params={"id": invite_id})


@mcp.tool(annotations={"openWorldHint": True, "idempotentHint": False})
@_guard
async def invite_team_member(email: str) -> Any:
    """Invite someone to the team by email (sends a Clerk organization invite).

    Args:
        email: Email address to invite.
    """
    return await _cloud_client().post("/api/team/invite", json={"email": email})


# ---------------------------------------------------------------------------
# Local desktop app (optional — requires the BioNodulo desktop backend)
# ---------------------------------------------------------------------------


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": False})
@_guard
async def desktop_status() -> Any:
    """Check whether a local BioNodulo desktop app is running and reachable."""
    client = _desktop_client()
    if await client.ping():
        return {"ok": True, "url": _settings.desktop_url, "status": "reachable"}
    return {
        "ok": False,
        "error": f"No BioNodulo desktop app reachable at {_settings.desktop_url}",
    }


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": False})
@_guard
async def desktop_list_node_types(search: str | None = None) -> Any:
    """List node types available in the desktop app's registry (~800 nodes).

    Args:
        search: Optional substring filter on node type names (case-insensitive).
    """
    info = await _desktop_client().get("/api/object_info")
    if search and isinstance(info, dict):
        needle = search.lower()
        info = {k: v for k, v in info.items() if needle in k.lower()}
    return info


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": False})
@_guard
async def desktop_get_node_info(node_type: str) -> Any:
    """Get full metadata for one node type (inputs, outputs, parameters).

    Args:
        node_type: Node class name, e.g. 'AlphaFoldDBNode' or 'AIDataExtractionNode'.
    """
    return await _desktop_client().get(f"/api/object_info/{node_type}")


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": False})
@_guard
async def desktop_list_templates() -> Any:
    """List the desktop app's built-in workflow templates (23 templates)."""
    return await _desktop_client().get("/api/workflow_templates")


@mcp.tool(annotations={"openWorldHint": False, "idempotentHint": True})
@_guard
async def desktop_validate_workflow(workflow: dict[str, Any]) -> Any:
    """Validate a workflow definition locally (structure + environment readiness).

    Args:
        workflow: Workflow JSON document ({nodes: [...], edges: [...], ...}).
    """
    return await _desktop_client().post("/api/workflow/validate", json={"workflow": workflow})


@mcp.tool(annotations={"openWorldHint": False, "idempotentHint": False})
@_guard
async def desktop_submit_run(
    workflow: dict[str, Any],
    name: str = "mcp-run",
    dry_run: bool = False,
    no_cache: bool = False,
    parameters: dict[str, Any] | None = None,
) -> Any:
    """Submit a workflow to the local desktop execution engine.

    Returns {run_id, status: "queued"} — poll with desktop_get_run.

    Args:
        workflow: Workflow JSON document ({nodes: [...], edges: [...], ...}).
        name: Human-readable run name (prefix of the generated run_id).
        dry_run: If true, only preview the execution plan without running.
        no_cache: If true, bypass the result cache.
        parameters: Workflow parameter overrides.
    """
    body: dict[str, Any] = {
        "workflow": workflow,
        "name": name,
        "dry_run": dry_run,
        "no_cache": no_cache,
    }
    if parameters:
        body["parameters"] = parameters
    return await _desktop_client().post("/api/runs", json=body)


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": False})
@_guard
async def desktop_get_run(run_id: str) -> Any:
    """Get a local run's status and result.

    Statuses: pending | running | completed | failed | cancelled | interrupted.

    Args:
        run_id: The local run id (from desktop_submit_run).
    """
    return await _desktop_client().get(f"/api/runs/{run_id}")


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": False})
@_guard
async def desktop_get_run_logs(run_id: str, offset: int = 0, limit: int = 200) -> Any:
    """Get per-node stdout/stderr logs for a local run.

    Args:
        run_id: The local run id.
        offset: Log offset for pagination.
        limit: Maximum number of log entries.
    """
    return await _desktop_client().get(
        f"/api/runs/{run_id}/logs", params={"offset": offset, "limit": limit}
    )


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": False})
@_guard
async def desktop_get_queue() -> Any:
    """Get the local run queue state ({pending, running})."""
    return await _desktop_client().get("/api/queue")


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": False})
@_guard
async def desktop_get_history() -> Any:
    """Get the local run history (finished runs)."""
    return await _desktop_client().get("/api/history")


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": False})
@_guard
async def desktop_get_system_stats() -> Any:
    """Get host system stats from the desktop app (CPU, memory, GPU, tools)."""
    return await _desktop_client().get("/api/system_stats")


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------


@mcp.resource("bionodulo://account")
async def account_resource() -> str:
    """Current BioNodulo account snapshot (user + team)."""
    try:
        data = await _cloud_client().get("/api/me")
    except (ApiError, AuthError) as exc:
        data = {"error": str(exc)}
    return json.dumps(data, indent=2)


@mcp.resource("bionodulo://credits")
async def credits_resource() -> str:
    """Current team credit balance and plan."""
    try:
        data = await _cloud_client().get("/api/billing/credits")
    except (ApiError, AuthError) as exc:
        data = {"error": str(exc)}
    return json.dumps(data, indent=2)


@mcp.resource("bionodulo://runs")
async def runs_resource() -> str:
    """Recent cloud workflow runs (up to 50)."""
    try:
        data = await _cloud_client().get("/api/runs")
    except (ApiError, AuthError) as exc:
        data = {"error": str(exc)}
    return json.dumps(data, indent=2)


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------


@mcp.prompt
def run_status_report(run_id: str) -> str:
    """Summarize the status, events and outputs of a cloud run."""
    return (
        f"Use get_run_status, get_run_events and get_run_outputs for run "
        f"'{run_id}', then summarize: overall status, timeline, credits used, "
        "any errors, and the outputs produced."
    )


@mcp.prompt
def troubleshoot_failed_run(run_id: str) -> str:
    """Diagnose why a run failed and suggest fixes."""
    return (
        f"Investigate failed run '{run_id}': call get_run_status for the error "
        "message, get_run_events for the failing node/step, and (if this was a "
        "local run) desktop_get_run_logs for stdout/stderr. Explain the root "
        "cause and suggest a concrete fix or a retry strategy."
    )


@mcp.prompt
def plan_cloud_run(workflow_id: str) -> str:
    """Prepare and cost-check a cloud run before submitting it."""
    return (
        f"Help me run workflow '{workflow_id}' in the cloud: fetch it with "
        "get_workflow, check my balance with get_credit_balance, estimate the "
        "cost for a suitable resource profile with estimate_run_cost, then "
        "confirm the parameters with me before calling submit_run."
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        prog="bionodulo-mcp",
        description="BioNodulo MCP server (stdio for local clients, HTTP for remote).",
    )
    sub = parser.add_subparsers(dest="command")

    serve = sub.add_parser("serve", help="Run the MCP server (default)")
    serve.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default="stdio",
        help="stdio for Claude/Codex desktop clients; http for remote connectors",
    )
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8787)
    serve.add_argument("--path", default="/mcp")

    install = sub.add_parser(
        "install", help="Register this server with Claude Code/Desktop and Codex"
    )
    install.add_argument(
        "--client",
        choices=["claude-code", "claude-desktop", "codex", "all"],
        default="all",
    )
    install.add_argument("--clerk-secret-key", default=os.environ.get("CLERK_SECRET_KEY"))
    install.add_argument(
        "--user-email",
        default=os.environ.get("BIONODULO_USER_EMAIL"),
        help="BioNodulo account email (used to mint Clerk session tokens)",
    )

    args = parser.parse_args()

    if args.command == "install":
        from .install import install_clients

        install_clients(
            client=args.client,
            clerk_secret_key=args.clerk_secret_key,
            user_email=args.user_email,
        )
        return

    transport = getattr(args, "transport", "stdio")
    if transport == "http":
        mcp.run(
            transport="streamable-http",
            host=args.host,
            port=args.port,
            path=args.path,
        )
    else:
        mcp.run()


if __name__ == "__main__":
    main()
