#!/usr/bin/env python3
"""Solve one workflow environment and publish its lock to the shared cache.

Cloud workers refuse to solve at run time, so a workflow whose package set has
no committed bundle cannot run — which is every workflow a user edits into a
new shape. This solves that environment ONCE, off the worker, and publishes the
bundle so the run (and every later run of the same package set) just installs it.

Run this where solving is cheap and always-on. Provisioning a VM per solve costs
~207s (measured) before pixi's ~7s solve even starts, so the dispatch host is
roughly 30x better than a one-shot job.

Usage::

    python scripts/solve_env_lock.py --workflow workflow.json
    python scripts/solve_env_lock.py --workflow - < workflow.json
    python scripts/solve_env_lock.py --workflow wf.json --check   # report only

Requires ENV_LOCK_CACHE_BUCKET (plus S3/R2 credentials) to publish. `--check`
needs neither and is safe to run anywhere.

Exit codes: 0 solved//cached, 1 solve or publish failed, 2 bad input.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from bionodulo.environments.manifest import (  # noqa: E402
    DEFAULT_LOCK_PLATFORM,
    _manifest_text_for_plan,
    generate_environment_manifest,
    get_environment_plan_id,
    materialize_committed_environment,
    run_pixi_lock,
    workflow_to_environment_plan,
)
from bionodulo.execution import env_lock_cache  # noqa: E402
from bionodulo.nodes.registry import NodeRegistry  # noqa: E402


def _load_workflow(source: str) -> dict:
    raw = sys.stdin.read() if source == "-" else Path(source).read_text(encoding="utf-8")
    document = json.loads(raw)
    if not isinstance(document, dict):
        raise ValueError("workflow must be a JSON object")
    return document


def solve_and_publish(workflow: dict, platform: str, check_only: bool) -> int:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    plan = workflow_to_environment_plan(workflow, registry)
    env_id = get_environment_plan_id(plan)
    manifest_text = _manifest_text_for_plan(plan)

    if not plan.all_packages:
        print(f"{env_id}: no external packages; nothing to solve")
        return 0

    # Already resolvable? Committed bundle first, then the cache — same order the
    # worker uses, so "already available" here means "the run will not fail".
    with tempfile.TemporaryDirectory() as probe:
        env_lock_cache.install()
        if materialize_committed_environment(probe, plan, platform=platform) is not None:
            print(f"{env_id} ({platform}): already available, no solve needed")
            return 0

    if check_only:
        print(f"{env_id} ({platform}): MISSING — would solve {len(plan.all_packages)} package(s)")
        return 0

    with tempfile.TemporaryDirectory() as workdir:
        env_dir = Path(workdir)
        generate_environment_manifest(env_dir, plan)
        ok, message = asyncio.run(run_pixi_lock(env_dir))
        if not ok:
            # An unsatisfiable package set is a real answer, not a transient
            # failure: report it so the caller can reject the workflow instead
            # of letting a worker discover it.
            print(f"{env_id} ({platform}): solve failed: {message}", file=sys.stderr)
            return 1
        lock_bytes = (env_dir / "pixi.lock").read_bytes()

    if not env_lock_cache.cache_enabled():
        print(f"{env_id} ({platform}): solved but ENV_LOCK_CACHE_BUCKET is unset", file=sys.stderr)
        return 1
    if not env_lock_cache.publish(env_id, platform, manifest_text, lock_bytes):
        print(f"{env_id} ({platform}): publish failed", file=sys.stderr)
        return 1

    print(f"{env_id} ({platform}): solved and published ({len(lock_bytes)} bytes)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workflow", required=True, help="workflow JSON path, or - for stdin")
    parser.add_argument("--platform", default=DEFAULT_LOCK_PLATFORM)
    parser.add_argument(
        "--check",
        action="store_true",
        help="report whether a lock is needed without solving or publishing",
    )
    args = parser.parse_args(argv)

    try:
        workflow = _load_workflow(args.workflow)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"cannot read workflow: {error}", file=sys.stderr)
        return 2

    return solve_and_publish(workflow, args.platform, args.check)


if __name__ == "__main__":
    raise SystemExit(main())
