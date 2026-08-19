"""Live end-to-end test of the BioNodulo MCP server.

Uses the FastMCP in-process client to exercise the read-only tools against
the real cloud API. Mutating tools (submit_run, cancel_run, create_*) are
intentionally not called.

Requires: CLERK_SECRET_KEY and BIONODULO_USER_EMAIL in the environment.
"""

import asyncio
import json
import os
import sys

# Ensure settings pick up credentials before server import.
assert os.environ.get("CLERK_SECRET_KEY"), "set CLERK_SECRET_KEY"
assert os.environ.get("BIONODULO_USER_EMAIL"), "set BIONODULO_USER_EMAIL"

from fastmcp import Client  # noqa: E402

from bionodulo_mcp.server import mcp  # noqa: E402

PASS, FAIL = "\033[92mPASS\033[0m", "\033[91mFAIL\033[0m"


def summarize(result) -> str:
    text = result.content[0].text if result.content else ""
    try:
        data = json.loads(text)
        s = json.dumps(data)
    except (ValueError, TypeError):
        s = text
    return s[:220]


async def main() -> int:
    failures = 0

    async with Client(mcp) as client:
        tools = await client.list_tools()
        print(f"\n== {len(tools)} tools registered ==")
        for t in tools:
            print(f"  - {t.name}")

        prompts = await client.list_prompts()
        resources = await client.list_resources()
        print(f"== {len(prompts)} prompts, {len(resources)} resources ==\n")

        async def check(name: str, expect_ok: bool = True, **args):
            nonlocal failures
            result = await client.call_tool(name, args)
            out = summarize(result)
            ok = '"ok": false' not in out
            good = ok if expect_ok else True
            print(f"{PASS if good else FAIL} {name}: {out}")
            if not good:
                failures += 1
            return result

        # --- read-only cloud tools ---
        await check("get_service_health")
        await check("get_account_info")
        await check("get_credit_balance")
        await check("get_credit_usage")
        await check("get_usage_analytics", days=30)
        await check("estimate_run_cost", vcpu=4, ram_gb=16)
        await check("list_invoices")
        runs_result = await check("list_runs")
        await check("list_workflows")
        await check("list_files")
        # get_ai_analysis requires an id/doi; verify input validation works.
        await check("get_ai_analysis", expect_ok=False)

        # Drill into a run if one exists.
        try:
            runs = json.loads(runs_result.content[0].text)
            run_list = runs if isinstance(runs, list) else runs.get("runs", [])
        except (ValueError, AttributeError):
            run_list = []
        if run_list:
            rid = run_list[0].get("id") or run_list[0].get("runId")
            print(f"\n-- drilling into run {rid} --")
            await check("get_run_status", run_id=rid)
            await check("get_run_events", run_id=rid, expect_ok=False)
            await check("get_run_outputs", run_id=rid)
            wid = run_list[0].get("workflowId")
            if wid:
                await check("get_workflow", workflow_id=wid)
                await check("list_collab_invites", workflow_id=wid)
        else:
            print("\n-- no runs found; skipping run drill-down --")

        # --- resources ---
        for uri in ("bionodulo://account", "bionodulo://credits", "bionodulo://runs"):
            res = await client.read_resource(uri)
            body = res[0].text if res else ""
            ok = '"error"' not in body[:60]
            print(f"{PASS if ok else FAIL} resource {uri}: {body[:160]}")
            if not ok:
                failures += 1

        # --- desktop (optional; expected to fail gracefully if not running) ---
        desktop = await client.call_tool("desktop_status", {})
        print(f"info desktop_status: {summarize(desktop)}")

    print(f"\n{'ALL GOOD' if failures == 0 else f'{failures} FAILURES'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
