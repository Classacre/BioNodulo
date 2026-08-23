"""
WorkflowExecutor - the main execution engine for BioNodulo v2.

Executes workflow graphs with support for:
- Topological-sort execution order
- Input resolution from upstream node outputs
- Muted and bypassed node handling
- Cache hit detection and skipping
- Real execution with optional environment isolation
- WebSocket event emission
- Per-node and per-run metadata
- Preview artifact collection
- Provenance embedding
"""

from __future__ import annotations

import asyncio
import copy
import gzip
import hashlib
import json
import logging
import os
import re
import shlex
import tempfile
import traceback
from collections import deque
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Callable

from bionodulo.core.credentials import merge_api_secrets, redact_tree
from bionodulo.environments.manifest import (
    get_env_dir,
    get_environment_plan_id,
    is_env_ready,
    workflow_to_environment_plan,
)
from bionodulo.execution import head_preview as head_preview_mod
from bionodulo.execution.cache import CacheStore
from bionodulo.execution.errors import (
    NodeExitCodeError,
    NodeMemoryError,
    NodeTimeoutError,
)
from bionodulo.execution.subprocess_runner import CommandCancelledError, run_subprocess
from bionodulo.workflow.graph import edge_source, edge_source_port, edge_target, edge_target_port

logger = logging.getLogger(__name__)

PREVIEWABLE_EXTENSIONS = frozenset({
    ".html", ".htm", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".json", ".csv", ".tsv",
})


# ---------------------------------------------------------------------------
# ExecutionContext
# ---------------------------------------------------------------------------

@dataclass
class ExecutionContext:
    """Runtime context passed to each node's ``run()`` method.

    Attributes:
        run_id: Unique identifier for this workflow run.
        node_id: The node's identifier in the workflow graph.
        node_type: The node's type string.
        node_dir: Working directory for this node's execution.
        params: Resolved parameters for the node.
        api_secrets: Dictionary of resolved API secrets.
        emit: Callback for emitting WebSocket events.
        cancel_event: Asyncio event that signals cancellation.
        env_prefix: Optional command prefix for environment isolation
            (e.g. ["pixi", "run", "-e", "qc", "--"]).
        run_metadata: Mutable metadata for the whole workflow run.
        executor: The active workflow executor instance.
        registry: The active node registry for type resolution.
    """

    run_id: str
    node_id: str
    node_type: str
    node_dir: Path
    workspace_dir: Path
    params: dict[str, Any]
    api_secrets: dict[str, str]
    emit: Callable[[str, dict[str, Any]], None]
    cancel_event: asyncio.Event
    env_prefix: list[str] = field(default_factory=list)
    run_metadata: dict[str, Any] = field(default_factory=dict)
    executor: Any | None = None
    registry: Any | None = field(default=None, repr=False)
    hpc_backend: Any | None = field(default=None, repr=False)

    # Mutable state set during execution
    _previews: list[dict[str, Any]] = field(default_factory=list, repr=False)
    _logs: list[dict[str, Any]] = field(default_factory=list, repr=False)

    def planned_outputs(self) -> dict[str, str]:
        """Return a mapping of output port names to planned file paths.

        By default, each output port gets a file inside ``node_dir``
        named after the port.
        """
        return {
            name: str(self.node_dir / f"{name}_output")
            for name in (self.params.get("_output_ports") or ["default"])
        }

    def log(self, level: str, message: str) -> None:
        """Emit a log message via WebSocket and store locally."""
        entry = {"node_id": self.node_id, "level": level, "message": message}
        self._logs.append(entry)
        self.emit("log", entry)

    def resolve_secret(self, key: str) -> str | None:
        """Resolve an API secret by *key*."""
        return self.api_secrets.get(key)

    def register_preview(self, path: str | Path, label: str | None = None) -> None:
        """Register a file as a previewable artifact."""
        preview = {
            "path": str(path),
            "label": label or Path(path).name,
            "node_id": self.node_id,
        }
        self._previews.append(preview)
        self.emit("preview", preview)

    @staticmethod
    def _wrap_with_env_prefix(
        cmd: str | list[str],
        env_prefix: list[str],
    ) -> str | list[str]:
        """Run ``cmd`` under ``env_prefix`` without letting it escape.

        ``env_prefix`` is an argv prefix ending in ``--`` (``pixi run ... --``).
        A SHELL=True node returns its command as a *string* that may contain
        shell operators. Concatenating that string after the prefix lets the
        OUTER shell split on those operators, so only the first segment runs
        inside the environment and everything after ``&&``/``|``/``;`` runs
        outside it — where the tools do not exist. In production that turned

            export FC_PATH=$(command -v featureCounts) && featureCounts ...

        into ``pixi run -- export ...`` (exit 127, no such binary) followed by a
        featureCounts call outside the environment.

        Pass the whole shell command as ONE argument to a shell that itself runs
        inside the prefix, so the operators are interpreted in there.
        """
        if not env_prefix:
            return cmd
        if isinstance(cmd, str):
            return " ".join(shlex.quote(part) for part in [*env_prefix, "bash", "-c", cmd])
        return env_prefix + list(cmd)

    async def run_command(
        self,
        cmd: str | list[str],
        cwd: str | Path | None = None,
        env: dict[str, str] | None = None,
        timeout: float | None = None,
        stdout_path: str | Path | None = None,
        stderr_path: str | Path | None = None,
    ) -> dict[str, Any]:
        """Run a subprocess command within this execution context.

        If ``env_prefix`` is set, commands are wrapped for isolated execution.
        Stream paths default to the node's existing ``stdout.log`` and
        ``stderr.log`` files.
        """
        if stdout_path is None:
            stdout_path = self.node_dir / "stdout.log"
        if stderr_path is None:
            stderr_path = self.node_dir / "stderr.log"

        wrapped_cmd: str | list[str] = self._wrap_with_env_prefix(cmd, self.env_prefix)

        return await run_subprocess(
            cmd=wrapped_cmd,
            cwd=cwd or self.node_dir,
            env=env,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            emit=self.emit,
            node_id=self.node_id,
            timeout=timeout,
            cancel_event=self.cancel_event,
        )


# ---------------------------------------------------------------------------
# WorkflowExecutor
# ---------------------------------------------------------------------------

class WorkflowExecutor:
    """Main workflow execution engine.

    Executes a workflow graph node by node in topological order,
    handling caching, muting, bypassing, and error recovery.
    """

    def __init__(
        self,
        cache_dir: str | Path | None = None,
        workspace_dir: str | Path = "./workspace",
        registry: Any | None = None,
        settings: Any | None = None,
        hpc_backend: Any | None = None,
        run_store: Any | None = None,
    ) -> None:
        self.workspace_dir = Path(workspace_dir)
        self.cache = CacheStore(cache_dir or self.workspace_dir / "cache")
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.registry = registry
        self.settings = settings
        self.hpc_backend = hpc_backend
        self.run_store = run_store

    def _record_run_event(self, run_id: str, event_type: str, payload: dict[str, Any]) -> None:
        """Best-effort durable run-event persistence (no-op without a store)."""
        store = getattr(self, "run_store", None)
        if store is None:
            return
        try:
            store.append_event(run_id, event_type, payload)
        except Exception:
            logger.exception("Failed to persist run event %s for run %s", event_type, run_id)

    @staticmethod
    def _tag_subgraph_path(run_metadata: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        """Stamp a nested-execution event payload with its subgraph path."""
        path = run_metadata.get("subgraph_path") if isinstance(run_metadata, dict) else ""
        if not path:
            return payload
        return {**payload, "subgraph_path": path}

    def _api_secrets_for_options(self, options: dict[str, Any]) -> dict[str, str]:
        configured = getattr(self.settings, "api_secrets", {}) if self.settings is not None else {}
        option_secrets = options.get("api_secrets", {})
        return merge_api_secrets(configured, option_secrets if isinstance(option_secrets, dict) else {})

    @staticmethod
    def _detected_vcpus() -> int:
        """Best-effort count of usable vCPUs on this machine.

        In containers/cgroups, os.cpu_count() reports the host's total;
        reading the cgroup quota is the reliable signal there. On a
        full VM, os.cpu_count() is correct.
        """
        try:
            import os

            count = os.cpu_count() or 1
        except Exception:
            count = 1
        # cgroup v2 (most modern containers)
        try:
            quota = int(open("/sys/fs/cgroup/cpu.max").read().split()[0])
            if quota > 0:
                period = int(open("/sys/fs/cgroup/cpu.max").read().split()[1])
                if period > 0:
                    count = min(count, max(1, quota // period))
        except (OSError, ValueError, IndexError):
            pass
        # cgroup v1 (older containers)
        if count > 1:
            try:
                quota = int(open("/sys/fs/cgroup/cpu/cpu.cfs_quota_us").read())
                period = int(open("/sys/fs/cgroup/cpu/cpu.cfs_period_us").read())
                if quota > 0 and period > 0:
                    count = min(count, max(1, quota // period))
            except (OSError, ValueError):
                pass
        return max(1, count)

    def _max_parallel_nodes(self) -> int:
        """Maximum number of nodes to execute concurrently within one run.

        Priority order:
          1. ``BIONODULO_MAX_WORKERS`` env var (explicit override — the
             dispatch/website sets this to match the provisioned VM size)
          2. ``settings.execution.max_workers`` (user configuration)
          3. Auto-detected vCPU count (universal default: use what you pay for)

        Independent branches of the DAG run in parallel up to this bound; set
        to 1 to recover fully serial execution.
        """
        env = os.environ.get("BIONODULO_MAX_WORKERS", "").strip()
        if env:
            try:
                return max(1, int(env))
            except (TypeError, ValueError):
                pass
        execution = getattr(self.settings, "execution", None) if self.settings is not None else None
        raw = getattr(execution, "max_workers", None) if execution is not None else None
        if raw is not None:
            try:
                return max(1, int(raw))
            except (TypeError, ValueError):
                pass
        # Universal default: scale with detected vCPUs so the engine uses
        # what the user is paying for. Cloud VMs report their size correctly;
        # local dev machines get their core count too.
        return self._detected_vcpus()

    def _cache_hash_mode(self) -> str:
        """Input-file fingerprint mode for cache keys: 'fast', 'strong', or 'off'.

        Sourced from ``settings.execution.content_hashing`` (default 'fast').
        """
        execution = getattr(self.settings, "execution", None) if self.settings is not None else None
        mode = getattr(execution, "content_hashing", None) if execution is not None else None
        mode = str(mode).lower() if mode is not None else "fast"
        return mode if mode in {"fast", "strong", "off"} else "fast"

    @staticmethod
    async def _drive_node_scheduler(
        *,
        execution_order: list[str],
        upstream_of: dict[str, list[str]],
        downstream_of: dict[str, list[str]],
        run_node: Callable[[int, str], Any],
        cancel_event: asyncio.Event,
        max_parallel: int,
    ) -> None:
        """Execute nodes with bounded concurrency while honouring the DAG.

        A node is dispatched only once every one of its predecessors has finished
        processing, so the per-node body still sees complete upstream state.
        Independent branches run concurrently up to ``max_parallel``. When
        ``run_node`` returns ``"stop"`` (a blocking failure or cancellation) no
        further nodes are dispatched; already in-flight nodes are awaited to
        completion rather than abandoned.
        """
        idx_of = {node_id: i for i, node_id in enumerate(execution_order)}
        indegree = {
            node_id: len(set(upstream_of.get(node_id, ())))
            for node_id in execution_order
        }
        successors = {
            node_id: list(dict.fromkeys(downstream_of.get(node_id, ())))
            for node_id in execution_order
        }
        ready: deque[str] = deque(
            node_id for node_id in execution_order if indegree.get(node_id, 0) == 0
        )
        sem = asyncio.Semaphore(max(1, max_parallel))
        stop = False

        async def _guarded(node_id: str) -> tuple[str, str]:
            async with sem:
                if stop or cancel_event.is_set():
                    return ("stop", node_id)
                outcome = await run_node(idx_of[node_id], node_id)
                return (outcome, node_id)

        pending: set[asyncio.Task[tuple[str, str]]] = set()
        while True:
            while ready and not stop:
                pending.add(asyncio.create_task(_guarded(ready.popleft())))
            if not pending:
                break
            finished, pending = await asyncio.wait(
                pending, return_when=asyncio.FIRST_COMPLETED
            )
            for task in finished:
                outcome, node_id = task.result()
                if outcome == "stop":
                    stop = True
                    continue
                for succ in successors.get(node_id, ()):  # newly satisfiable nodes
                    indegree[succ] -= 1
                    if indegree[succ] == 0:
                        ready.append(succ)
            if stop:
                if pending:
                    await asyncio.gather(*pending, return_exceptions=True)
                break

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def execute(
        self,
        run_id: str,
        workflow: dict[str, Any],
        record: Any | None = None,
        force: bool = False,
        force_nodes: set[str] | None = None,
        options: dict[str, Any] | None = None,
        cancel_event: asyncio.Event | None = None,
        emit: Callable[[str, dict[str, Any]], None] | None = None,
        input_overrides: dict[str, dict[str, Any]] | None = None,
        *,
        _run_dir: Path | None = None,
        _subgraph_path: str = "",
    ) -> dict[str, Any]:
        """Execute a workflow.

        Args:
            run_id: Unique run identifier.
            workflow: Workflow dict with ``nodes`` and ``edges``.
            record: Optional run record object for progress tracking.
            force: Ignore cache for all nodes.
            force_nodes: Set of node IDs to force re-execution.
            options: Execution options (stop_on_error, etc.).
            cancel_event: Asyncio event for cancellation signaling.
            emit: Callback for WebSocket events.
            input_overrides: Per-node input values applied after edge
                resolution (override wins); used to feed a subgraph's mapped
                parent inputs to its inner nodes.
            _run_dir: Internal — artifact root for this (possibly nested)
                execution; defaults to ``workspace/runs/<run_id>``.
            _subgraph_path: Internal — dot-joined chain of subgraph node IDs
                this execution is nested under ("" at the top level).

        Returns:
            Execution result dict with ``status``, ``outputs``, ``previews``,
            ``metadata``, and ``node_results``.
        """
        options = options or {}
        force_nodes = force_nodes or set()
        cancel_event = cancel_event or asyncio.Event()
        input_overrides = input_overrides or {}
        run_root = Path(_run_dir) if _run_dir is not None else self.workspace_dir / "runs" / run_id

        if emit is None:
            def _noop_emit(event: str, data: dict[str, Any]) -> None:
                pass
            emit = _noop_emit

        try:
            workflow_parameters = self._resolve_workflow_parameters(
                workflow.get("parameters", []),
                options.get("parameters", {}),
            )
        except ValueError as exc:
            msg = str(exc)
            emit("error", {"run_id": run_id, "message": msg})
            return {"status": "failed", "run_id": run_id, "error": msg}

        _VISUAL_ONLY_TYPES = frozenset({"note"})
        raw_nodes_data = workflow.get("nodes", [])
        if isinstance(raw_nodes_data, dict):
            raw_nodes = []
            for node_id, node in raw_nodes_data.items():
                if isinstance(node, dict):
                    node_data = dict(node)
                elif hasattr(node, "model_dump"):
                    node_data = node.model_dump()
                else:
                    node_data = dict(getattr(node, "__dict__", {}))
                node_data.setdefault("id", str(node_id))
                raw_nodes.append(node_data)
        else:
            raw_nodes = list(raw_nodes_data or [])
        nodes: dict[str, dict[str, Any]] = {
            str(n["id"]): n
            for n in raw_nodes
            if isinstance(n, dict) and n.get("id") is not None and n.get("type") not in _VISUAL_ONLY_TYPES
        }
        edges: list[dict[str, Any]] = workflow.get("edges", [])
        target_nodes = self._coerce_node_id_set(options.get("target_nodes"))

        if target_nodes:
            raw_node_ids = {
                str(n["id"])
                for n in raw_nodes
                if isinstance(n, dict) and n.get("id") is not None
            }
            unknown_targets = sorted(target_nodes - raw_node_ids)
            if unknown_targets:
                msg = f"Unknown target node(s): {', '.join(unknown_targets)}"
                emit("error", {"run_id": run_id, "message": msg})
                return {"status": "failed", "error": msg}

            executable_targets = target_nodes & set(nodes)
            if executable_targets:
                required_nodes = self._upstream_closure(executable_targets, nodes, edges)
                nodes = {nid: node for nid, node in nodes.items() if nid in required_nodes}
                edges = [
                    edge
                    for edge in edges
                    if edge_source(edge) in nodes and edge_target(edge) in nodes
                ]
            else:
                nodes = {}
                edges = []

        all_nodes = nodes
        loop_bodies = self._loop_bodies(all_nodes, edges)
        try_catch_regions = self._try_catch_regions(all_nodes, edges)
        loop_body_node_ids = {body_node for body in loop_bodies.values() for body_node in body}
        try_catch_body_node_ids = {
            body_node
            for branches in try_catch_regions.values()
            for body in branches.values()
            for body_node in body
        }
        internal_node_ids = loop_body_node_ids | try_catch_body_node_ids
        nodes = {
            node_id: node
            for node_id, node in all_nodes.items()
            if node_id not in internal_node_ids
        }
        outer_edges = [
            edge
            for edge in edges
            if edge_source(edge) in nodes and edge_target(edge) in nodes
        ]

        # Build adjacency lists
        upstream_of: dict[str, list[str]] = {nid: [] for nid in nodes}
        downstream_of: dict[str, list[str]] = {nid: [] for nid in nodes}
        edge_map: dict[str, list[dict[str, Any]]] = {nid: [] for nid in nodes}

        for edge in outer_edges:
            src = edge_source(edge)
            tgt = edge_target(edge)

            if src in nodes and tgt in nodes:
                upstream_of[tgt].append(src)
                downstream_of[src].append(tgt)
                edge_map[tgt].append(edge)

        # Topological sort
        try:
            execution_order = self._topological_sort(nodes, upstream_of, downstream_of)
        except ValueError as exc:
            emit("error", {"run_id": run_id, "message": f"Cycle detected: {exc}"})
            return {"status": "failed", "error": str(exc)}

        resume_checkpoint = options.get("resume_checkpoint")
        resume_node_id = ""
        resume_outputs: dict[str, Any] = {}
        if resume_checkpoint:
            try:
                if not isinstance(resume_checkpoint, dict):
                    raise ValueError("resume_checkpoint must be an object")
                resume_node_id = str(resume_checkpoint.get("node_id", "") or "")
                resume_outputs = self._resume_checkpoint_outputs(resume_checkpoint)
                resume_graph = self._restrict_graph_for_resume(
                    resume_node_id=resume_node_id,
                    nodes=nodes,
                    outer_edges=outer_edges,
                )
            except ValueError as exc:
                msg = str(exc)
                emit("error", {"run_id": run_id, "message": msg})
                return {"status": "failed", "error": msg}
            nodes = resume_graph["nodes"]
            outer_edges = resume_graph["outer_edges"]
            edge_map = resume_graph["edge_map"]
            upstream_of = resume_graph["upstream_of"]
            downstream_of = resume_graph["downstream_of"]
            execution_order = resume_graph["execution_order"]

        emit("start", {"run_id": run_id, "total_nodes": len(execution_order)})

        # State tracking
        node_results: dict[str, dict[str, Any]] = {}
        node_cache_keys: dict[str, str | None] = {}
        node_outputs: dict[str, dict[str, str]] = {}
        node_inactive_outputs: dict[str, set[str]] = {}
        failed_nodes: set[str] = set()
        skipped_nodes: set[str] = set()
        previews: list[dict[str, Any]] = []
        stop_on_error = options.get("stop_on_error", True)
        run_metadata: dict[str, Any] = {
            "run_id": run_id,
            "forced": force,
            "target_nodes": sorted(target_nodes),
            "workflow_parameters": workflow_parameters,
            "nodes": {},
            # Flags a nested subgraph execution must inherit (its inner
            # execute() call reads these through ctx.run_metadata).
            "execution_options": {
                "force": bool(force),
                "stop_on_error": bool(stop_on_error),
                "embed_provenance": bool(options.get("embed_provenance", True)),
            },
        }
        if _subgraph_path:
            run_metadata["subgraph_path"] = _subgraph_path
        if input_overrides:
            run_metadata["input_overrides"] = input_overrides
        if resume_checkpoint:
            run_metadata["resume_checkpoint"] = resume_checkpoint

        cancelled_holder: dict[str, str | None] = {}

        async def _run_node(idx: int, node_id: str) -> str:
            """Process one node; return 'done' to keep scheduling or
            'stop' to halt (blocking failure or cancellation). The single-pass
            ``for`` loop lets the original body keep its ``continue``/``break``
            control flow unchanged."""
            should_stop = False
            for _scheduler_pass in (0,):
                if cancel_event.is_set():
                    emit("cancelled", {"run_id": run_id, "node_id": node_id})
                    cancelled_holder.setdefault("at", node_id)
                    should_stop = True
                    break

                if node_id in skipped_nodes and node_id in node_results:
                    continue

                node = nodes[node_id]
                node_type = node.get("type", "unknown")
                node_meta = node.get("meta", {})

                if resume_checkpoint and node_id == resume_node_id:
                    emit(
                        "node_resume",
                        {
                            "run_id": run_id,
                            "node_id": node_id,
                            "checkpoint": resume_checkpoint,
                            "outputs": resume_outputs,
                        },
                    )
                    node_results[node_id] = {
                        "status": "resumed",
                        "outputs": resume_outputs,
                        "checkpoint": resume_checkpoint,
                    }
                    node_outputs[node_id] = resume_outputs
                    node_cache_keys[node_id] = None
                    run_metadata["nodes"][node_id] = {
                        "type": node_type,
                        "status": "resumed",
                        "cache_key": None,
                    }
                    continue

                emit(
                    "node_start",
                    {
                        "run_id": run_id,
                        "node_id": node_id,
                        "node_type": node_type,
                        "progress": f"{idx + 1}/{len(execution_order)}",
                    },
                )

                # ---- Muted node: skip execution entirely ----
                if node_meta.get("muted"):
                    emit(
                        "node_skip",
                        {"run_id": run_id, "node_id": node_id, "reason": "muted"},
                    )
                    node_results[node_id] = {"status": "muted"}
                    skipped_nodes.add(node_id)
                    continue

                inactive_upstream = self._inactive_upstream(
                    node_id,
                    edge_map,
                    skipped_nodes,
                    node_inactive_outputs,
                    self._node_class_for(node),
                )
                if inactive_upstream is not None:
                    emit(
                        "node_skip",
                        {
                            "run_id": run_id,
                            "node_id": node_id,
                            "reason": "inactive_branch",
                            "upstream": inactive_upstream,
                        },
                    )
                    node_results[node_id] = {
                        "status": "skipped",
                        "reason": "inactive_branch",
                        "upstream": inactive_upstream,
                    }
                    skipped_nodes.add(node_id)
                    continue

                # ---- Bypassed node: pass inputs through to outputs ----
                if node_meta.get("bypassed"):
                    bypass_outputs = self._bypass_outputs(node_id, node, edge_map)
                    emit(
                        "node_bypass",
                        {
                            "run_id": run_id,
                            "node_id": node_id,
                            "outputs": bypass_outputs,
                        },
                    )
                    node_results[node_id] = {
                        "status": "bypassed",
                        "outputs": bypass_outputs,
                    }
                    node_outputs[node_id] = bypass_outputs
                    continue

                # ---- Resolve inputs from upstream nodes ----
                try:
                    resolved_inputs = self._resolve_inputs(
                        node_id,
                        node,
                        edge_map,
                        node_outputs,
                        workflow_parameters,
                        input_overrides=input_overrides,
                    )
                except Exception as exc:
                    msg = f"Input resolution failed for {node_id}: {exc}"
                    # Emit `node_error` (not the generic `error`) so the frontend
                    # WS handler can flip the node's status to 'error' and the
                    # canvas border switches from green to red. The earlier
                    # `error` event was a queue-level signal and never updated
                    # per-node status.
                    emit("node_error", {"run_id": run_id, "node_id": node_id, "error": msg})
                    node_results[node_id] = {"status": "failed", "error": msg}
                    failed_nodes.add(node_id)
                    if stop_on_error:
                        should_stop = True
                        break
                    continue

                # ---- Fill parameter defaults ----
                _node_class = self._node_class_for(node)
                resolved_params = self._with_defaults(node, resolved_inputs, _node_class, workflow_parameters)
                # Universal optimization: scale thread params to available cores
                resolved_params = self._auto_scale_threads(resolved_params)
                is_subgraph = self._is_subgraph_node(node)
                executes_loop_body = self._executes_loop_body(_node_class)
                executes_try_catch_branches = self._executes_try_catch_branches(_node_class)

                # ---- Build upstream cache key map ----
                upstream_keys: dict[str, str | None] = {}
                for edge in edge_map.get(node_id, []):
                    src = edge_source(edge)
                    src_port = edge_source_port(edge)
                    tgt_port = edge_target_port(edge)
                    upstream_keys[f"{src}:{src_port}->{tgt_port}"] = node_cache_keys.get(src)

                # ---- Compute cache key ----
                # Subgraph nodes have no registry class and always re-run their
                # embedded workflow (unless excluded by a resume restriction);
                # inner nodes keep their own normal caching.
                cache_key = None
                forced_node = (
                    force
                    or node_id in force_nodes
                    or is_subgraph
                    or executes_loop_body
                    or executes_try_catch_branches
                    or self._executor_cache_policy(_node_class) == "always_run"
                )
                if not forced_node:
                    hash_mode = self._cache_hash_mode()
                    input_fingerprints = {
                        **{f"in:{k}": v for k, v in self.cache.fingerprint_inputs(resolved_inputs, hash_mode).items()},
                        **{f"param:{k}": v for k, v in self.cache.fingerprint_inputs(resolved_params, hash_mode).items()},
                    }
                    # Key on content fingerprints instead of absolute paths so a
                    # rerun in a fresh run directory still hits entries from an
                    # earlier run whose inputs are byte-identical.
                    cache_key = self.cache.cache_key_for_node(
                        node_id=node_id,
                        node_type=node_type,
                        params=self.cache.normalize_paths(resolved_params, hash_mode),
                        inputs=self.cache.normalize_paths(resolved_inputs, hash_mode),
                        upstream_keys=upstream_keys,
                        tool_version=getattr(_node_class, "VERSION", None),
                        input_fingerprints=input_fingerprints,
                    )
                node_cache_keys[node_id] = cache_key

                # ---- Prepare node working directory and environment prefix ----
                node_dir = run_root / node_id
                node_dir.mkdir(parents=True, exist_ok=True)

                env_prefix: list[str] = []
                isolation = getattr(self.settings, "execution", None)
                isolation_mode = getattr(isolation, "env_isolation", "auto") if isolation else "auto"
                if isolation_mode in ("auto", "always"):
                    env_prefix = self._env_prefix_for_node(node, workflow)

                # ---- Cache hit check ----
                marker = None
                if cache_key is not None and self.cache.is_hit(cache_key):
                    marker = self.cache.read_marker(cache_key)
                    cached_outputs = marker.get("outputs", {}) if marker else {}
                    # Path-independent keys (content fingerprints) let a rerun hit
                    # entries written by an earlier run — but the marker's outputs
                    # point at THAT run's directory. If it was cleaned up, the
                    # replayed paths dangle; treat the entry as a miss so the node
                    # re-executes and materialises fresh outputs under this run.
                    if cached_outputs and not self.cache.marker_outputs_exist(cached_outputs):
                        marker = None
                        cached_outputs = {}
                if cache_key is not None and marker is not None:
                    ctx = ExecutionContext(
                        run_id=run_id,
                        node_id=node_id,
                        node_type=node_type,
                        node_dir=node_dir,
                        workspace_dir=self.workspace_dir,
                        params=resolved_params,
                        api_secrets=self._api_secrets_for_options(options),
                        emit=emit,
                        cancel_event=cancel_event,
                        env_prefix=env_prefix,
                        run_metadata=run_metadata,
                        executor=self,
                        registry=self.registry,
                        hpc_backend=self.hpc_backend,
                    )
                    cached_outputs = await self._apply_inline_output_validations(
                        ctx=ctx,
                        node=node,
                        outputs=cached_outputs,
                    )
                    inactive_outputs = self._inactive_output_ports(
                        marker or {},
                        cached_outputs,
                        _node_class,
                    )
                    if inactive_outputs:
                        node_inactive_outputs[node_id] = inactive_outputs
                    self._apply_skip_downstream(
                        run_id,
                        node_id,
                        marker or {},
                        _node_class,
                        nodes,
                        node_results,
                        skipped_nodes,
                        emit,
                    )
                    emit(
                        "node_cache_hit",
                        {
                            "run_id": run_id,
                            "node_id": node_id,
                            "cache_key": cache_key,
                            "outputs": cached_outputs,
                        },
                    )
                    node_results[node_id] = {
                        "status": "cached",
                        "cache_key": cache_key,
                        "outputs": cached_outputs,
                    }
                    node_outputs[node_id] = cached_outputs
                    # Some HTML reports are directory bundles whose relative
                    # assets cannot be served by the single-file preview route.
                    if self._automatic_previews_enabled(_node_class):
                        for port, path in cached_outputs.items():
                            paths = path if isinstance(path, (list, tuple)) else [path]
                            for p_str in paths:
                                if not isinstance(p_str, (str, Path)):
                                    continue
                                p = Path(p_str)
                                if p.exists() and p.suffix.lower() in PREVIEWABLE_EXTENSIONS:
                                    previews.append(
                                        {
                                            "path": str(p),
                                            "label": f"{node_id}/{port}",
                                            "node_id": node_id,
                                        }
                                    )
                    continue

                # ---- Build execution context ----
                ctx = ExecutionContext(
                    run_id=run_id,
                    node_id=node_id,
                    node_type=node_type,
                    node_dir=node_dir,
                    workspace_dir=self.workspace_dir,
                    params=resolved_params,
                    api_secrets=self._api_secrets_for_options(options),
                    emit=emit,
                    cancel_event=cancel_event,
                    env_prefix=env_prefix,
                    run_metadata=run_metadata,
                    executor=self,
                    registry=self.registry,
                    hpc_backend=self.hpc_backend,
                )

                # ---- Execute the node ----
                try:
                    if executes_loop_body:
                        result = await self._execute_loop_node(
                            ctx=ctx,
                            node=node,
                            inputs=resolved_inputs,
                            all_nodes=all_nodes,
                            edges=edges,
                            body_node_ids=loop_bodies.get(node_id, set()),
                            node_outputs=node_outputs,
                            options=options,
                            workflow=workflow,
                            emit=emit,
                        )
                    elif executes_try_catch_branches:
                        result = await self._execute_try_catch_node(
                            ctx=ctx,
                            node=node,
                            inputs=resolved_inputs,
                            all_nodes=all_nodes,
                            edges=edges,
                            branch_node_ids=try_catch_regions.get(node_id, {"try": set(), "catch": set()}),
                            node_outputs=node_outputs,
                            options=options,
                            workflow=workflow,
                            emit=emit,
                        )
                    else:
                        result = await self._execute_node_with_retry(
                            ctx=ctx,
                            node=node,
                            inputs=resolved_inputs,
                            upstream_nodes=self._upstream_node_ids(node_id, upstream_of),
                            emit=emit,
                        )
                    outputs = await self._apply_inline_output_validations(
                        ctx=ctx,
                        node=node,
                        outputs=result.get("outputs", {}),
                    )
                    result["outputs"] = outputs
                    inactive_outputs = self._inactive_output_ports(
                        result,
                        outputs,
                        _node_class,
                    )
                    if inactive_outputs:
                        node_inactive_outputs[node_id] = inactive_outputs
                    skip_downstream = self._apply_skip_downstream(
                        run_id,
                        node_id,
                        result,
                        _node_class,
                        nodes,
                        node_results,
                        skipped_nodes,
                        emit,
                    )
                    node_results[node_id] = {
                        "status": "completed",
                        "outputs": outputs,
                        "cache_key": cache_key,
                        "attempts": result.get("attempts", 1),
                    }
                    node_outputs[node_id] = outputs

                    # Cache the result
                    if cache_key is not None:
                        self.cache.write_marker(
                            cache_key=cache_key,
                            outputs=outputs,
                            params=resolved_params,
                            inputs=resolved_inputs,
                            upstream_keys=upstream_keys,
                            inactive_outputs=sorted(inactive_outputs) if inactive_outputs else None,
                            skip_downstream=sorted(skip_downstream) if skip_downstream else None,
                        )

                    # Collect previews
                    node_previews = self._collect_previews(ctx, result, _node_class)
                    previews.extend(node_previews)

                    emit(
                        "node_complete",
                        {
                            "run_id": run_id,
                            "node_id": node_id,
                            "outputs": outputs,
                        },
                    )

                except CommandCancelledError:
                    # Subprocess was killed because the run was cancelled. Mark
                    # the cancel event (idempotent), record the node as cancelled
                    # rather than failed, and stop the scheduler.
                    cancel_event.set()
                    cancelled_holder.setdefault("at", node_id)
                    node_results[node_id] = {"status": "cancelled"}
                    run_metadata["nodes"][node_id] = {
                        "type": node_type,
                        "status": "cancelled",
                        "cache_key": cache_key,
                    }
                    should_stop = True
                    break

                except Exception as exc:
                    tb = traceback.format_exc()
                    msg = f"Execution failed for {node_id}: {exc}"
                    attempts = getattr(exc, "attempts", 1)
                    emit(
                        "node_error",
                        {
                            "run_id": run_id,
                            "node_id": node_id,
                            "error": msg,
                            "traceback": tb,
                        },
                    )
                    self._record_run_event(
                        run_id,
                        "node_error",
                        self._tag_subgraph_path(
                            run_metadata,
                            {
                                "node_id": node_id,
                                "error": msg,
                                "error_code": self._error_code(exc),
                                "attempts": attempts,
                            },
                        ),
                    )
                    error_outputs = self._error_outputs(
                        node=node,
                        error=exc,
                        message=msg,
                        traceback_text=tb,
                        attempts=attempts,
                    )
                    node_results[node_id] = {"status": "failed", "error": msg, "traceback": tb}
                    node_results[node_id]["attempts"] = attempts
                    failed_nodes.add(node_id)
                    if self._continue_on_fail(node):
                        node_results[node_id]["continue_on_fail"] = True
                        node_results[node_id]["outputs"] = error_outputs
                        node_outputs[node_id] = error_outputs
                        continue
                    if stop_on_error:
                        should_stop = True
                        break

                run_metadata["nodes"][node_id] = {
                    "type": node_type,
                    "status": node_results[node_id]["status"],
                    "cache_key": cache_key,
                }

            return "stop" if should_stop else "done"

        await self._drive_node_scheduler(
            execution_order=execution_order,
            upstream_of=upstream_of,
            downstream_of=downstream_of,
            run_node=_run_node,
            cancel_event=cancel_event,
            max_parallel=self._max_parallel_nodes(),
        )

        # No node may be left statusless after a terminal run state: planned
        # nodes the scheduler never dispatched (or dispatched but cancelled
        # before their body started) get an explicit terminal status distinct
        # from the in-flight "cancelled" of nodes that actually ran.
        for unstarted_id in execution_order:
            if unstarted_id in node_results or unstarted_id in run_metadata["nodes"]:
                continue
            node_type = nodes.get(unstarted_id, {}).get("type", "unknown")
            node_results[unstarted_id] = {"status": "skipped_cancelled"}
            run_metadata["nodes"][unstarted_id] = {
                "type": node_type,
                "status": "skipped_cancelled",
                "cache_key": None,
            }
            emit(
                "node_skip",
                {
                    "run_id": run_id,
                    "node_id": unstarted_id,
                    "reason": "skipped_cancelled",
                },
            )
            self._record_run_event(
                run_id,
                "node_skipped_cancelled",
                self._tag_subgraph_path(
                    run_metadata,
                    {"node_id": unstarted_id, "node_type": node_type},
                ),
            )

        if cancel_event.is_set():
            # Persist what ran so logs/report endpoints and crash recovery can
            # see the partial run instead of an empty directory.
            run_metadata["status"] = "cancelled"
            run_metadata["failed_nodes"] = list(failed_nodes)
            run_metadata["skipped_nodes"] = list(skipped_nodes)
            run_metadata["cancelled_at"] = cancelled_holder.get("at")
            cancel_artifacts = self._collect_artifacts(run_id, nodes, node_results)
            run_metadata["artifacts"] = cancel_artifacts
            try:
                self._write_metadata(run_id, run_metadata, meta_dir=run_root)
            except Exception:
                logger.exception("Failed to write metadata for cancelled run %s", run_id)
            emit("complete", {"run_id": run_id, "status": "cancelled"})
            return {
                "status": "cancelled",
                "run_id": run_id,
                "outputs": node_outputs,
                "previews": previews,
                "artifacts": cancel_artifacts,
                "metadata": run_metadata,
                "node_results": node_results,
                "cancelled_at": cancelled_holder.get("at"),
            }

        # ---- Finalize ----
        blocking_failed_nodes = {
            node_id
            for node_id in failed_nodes
            if not self._continue_on_fail(nodes.get(node_id, {}))
        }
        final_status = "completed" if not blocking_failed_nodes else "failed"
        if cancel_event.is_set():
            final_status = "cancelled"

        run_metadata["status"] = final_status
        run_metadata["failed_nodes"] = list(failed_nodes)
        run_metadata["skipped_nodes"] = list(skipped_nodes)

        # Collect all artifacts
        artifacts = self._collect_artifacts(run_id, nodes, node_results)
        run_metadata["artifacts"] = artifacts

        # Write run metadata
        self._write_metadata(run_id, run_metadata, meta_dir=run_root)

        # Embed provenance in outputs
        if options.get("embed_provenance", True):
            try:
                from bionodulo.provenance.workflow_embed import embed_workflow_in_outputs
                embed_workflow_in_outputs(workflow, artifacts)
            except Exception:
                logger.exception("Failed to embed workflow provenance for run %s", run_id)

        emit("complete", {"run_id": run_id, "status": final_status})

        return {
            "status": final_status,
            "run_id": run_id,
            "outputs": node_outputs,
            "previews": previews,
            "artifacts": artifacts,
            "metadata": run_metadata,
            "node_results": node_results,
        }

    async def dry_run(
        self,
        run_id: str,
        workflow: dict[str, Any],
        *,
        force: bool = False,
        force_nodes: set[str] | None = None,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return a no-execute preview of node commands, outputs, cache, and environments."""
        options = options or {}
        force_nodes = force_nodes or set()
        graph = self._prepare_execution_plan_graph(workflow, options)
        if graph.get("status") == "failed":
            return {"status": "failed", "run_id": run_id, "error": graph["error"]}

        execution_order: list[str] = graph["execution_order"]
        nodes: dict[str, dict[str, Any]] = graph["nodes"]
        edge_map: dict[str, list[dict[str, Any]]] = graph["edge_map"]
        workflow_parameters: dict[str, Any] = graph["workflow_parameters"]

        resume_checkpoint = options.get("resume_checkpoint")
        resume_node_id = ""
        resume_outputs: dict[str, Any] = {}
        if resume_checkpoint:
            try:
                if not isinstance(resume_checkpoint, dict):
                    raise ValueError("resume_checkpoint must be an object")
                resume_node_id = str(resume_checkpoint.get("node_id", "") or "")
                resume_outputs = self._resume_checkpoint_outputs(resume_checkpoint)
                resume_graph = self._restrict_graph_for_resume(
                    resume_node_id=resume_node_id,
                    nodes=nodes,
                    outer_edges=graph["outer_edges"],
                )
            except ValueError as exc:
                return {"status": "failed", "run_id": run_id, "error": str(exc)}
            execution_order = resume_graph["execution_order"]
            nodes = resume_graph["nodes"]
            edge_map = resume_graph["edge_map"]

        node_outputs: dict[str, dict[str, Any]] = {}
        node_cache_keys: dict[str, str | None] = {}
        plan_nodes: list[dict[str, Any]] = []
        gpu_nodes: list[str] = []
        executables: set[str] = set()

        for node_id in execution_order:
            node = nodes[node_id]
            node_type = str(node.get("type", "unknown"))
            node_class = self._node_class_for(node)
            is_subgraph = self._is_subgraph_node(node)
            node_executables = list(getattr(node_class, "REQUIRED_EXECUTABLES", []) or []) if node_class else []
            node_requires_gpu = bool(getattr(node_class, "REQUIRES_GPU", False)) if node_class else False
            executables.update(str(item) for item in node_executables)
            if node_requires_gpu:
                gpu_nodes.append(node_id)
            if resume_checkpoint and node_id == resume_node_id:
                node_outputs[node_id] = resume_outputs
                node_cache_keys[node_id] = None
                plan_nodes.append(
                    {
                        "node_id": node_id,
                        "node_type": node_type,
                        "display_name": getattr(node_class, "DISPLAY_NAME", "") if node_class else "",
                        "category": getattr(node_class, "CATEGORY", "") if node_class else "",
                        "inputs": {},
                        "params": {},
                        "command": None,
                        "shell": False,
                        "env_prefix": self._env_prefix_for_node(node, workflow),
                        "requires_gpu": node_requires_gpu,
                        "required_executables": node_executables,
                        "required_conda_packages": list(getattr(node_class, "REQUIRED_CONDA_PACKAGES", []) or []),
                        "planned_outputs": resume_outputs,
                        "cache": {
                            "key": None,
                            "hit": False,
                            "forced": True,
                        },
                        "status": "resumed",
                    }
                )
                continue
            resolved_inputs = self._resolve_inputs(
                node_id,
                node,
                edge_map,
                node_outputs,
                workflow_parameters,
            )
            resolved_params = self._with_defaults(node, resolved_inputs, node_class, workflow_parameters)
            resolved_params = self._auto_scale_threads(resolved_params)
            upstream_keys: dict[str, str | None] = {}
            for edge in edge_map.get(node_id, []):
                src = edge_source(edge)
                src_port = edge_source_port(edge)
                tgt_port = edge_target_port(edge)
                upstream_keys[f"{src}:{src_port}->{tgt_port}"] = node_cache_keys.get(src)

            forced_node = (
                force
                or node_id in force_nodes
                or is_subgraph
                or self._executes_loop_body(node_class)
                or self._executes_try_catch_branches(node_class)
                or self._executor_cache_policy(node_class) == "always_run"
            )
            cache_key = None
            cache_hit = False
            if not forced_node:
                hash_mode = self._cache_hash_mode()
                cache_key = self.cache.cache_key_for_node(
                    node_id=node_id,
                    node_type=node_type,
                    params=self.cache.normalize_paths(resolved_params, hash_mode),
                    inputs=self.cache.normalize_paths(resolved_inputs, hash_mode),
                    upstream_keys=upstream_keys,
                    input_fingerprints={
                        **{f"in:{k}": v for k, v in self.cache.fingerprint_inputs(resolved_inputs, hash_mode).items()},
                        **{f"param:{k}": v for k, v in self.cache.fingerprint_inputs(resolved_params, hash_mode).items()},
                    },
                )
                cache_hit = self.cache.is_hit(cache_key)
            node_cache_keys[node_id] = cache_key

            node_dir = self.workspace_dir / "runs" / run_id / node_id
            planned_paths = self._dry_run_planned_outputs(node_class, resolved_params, node_dir)
            planned_outputs = self._planned_output_map(node_class, planned_paths)
            command = self._dry_run_command(node_class, resolved_params, node_dir)
            node_outputs[node_id] = planned_outputs

            plan_entry = {
                "node_id": node_id,
                "node_type": node_type,
                "display_name": getattr(node_class, "DISPLAY_NAME", "") if node_class else "",
                "category": getattr(node_class, "CATEGORY", "") if node_class else "",
                "inputs": self._public_plan_values(redact_tree(resolved_inputs)),
                "params": self._public_plan_values(redact_tree(resolved_params)),
                "command": self._redact_command(command, resolved_params),
                "shell": bool(getattr(node_class, "SHELL", False)) if node_class else False,
                "env_prefix": self._env_prefix_for_node(node, workflow),
                "requires_gpu": node_requires_gpu,
                "required_executables": node_executables,
                "required_conda_packages": list(getattr(node_class, "REQUIRED_CONDA_PACKAGES", []) or []),
                "planned_outputs": planned_outputs,
                "cache": {
                    "key": cache_key,
                    "hit": cache_hit,
                    "forced": forced_node,
                },
            }
            plan_nodes.append(plan_entry)

            if is_subgraph:
                inner_preview = await self._dry_run_subgraph(
                    node=node,
                    run_id=run_id,
                    force=force,
                    force_nodes=force_nodes,
                    options=options,
                    workflow_parameters=workflow_parameters,
                )
                plan_entry["inner_node_count"] = inner_preview["node_count"]
                if inner_preview["error"]:
                    plan_entry["inner_error"] = inner_preview["error"]
                plan_nodes.extend(inner_preview["nodes"])
                executables.update(inner_preview["executables"])
                gpu_nodes.extend(inner_preview["gpu_nodes"])

        return {
            "status": "dry_run",
            "run_id": run_id,
            "workflow_name": workflow.get("name", ""),
            "target_nodes": sorted(graph["target_nodes"]),
            "workflow_parameters": workflow_parameters,
            "execution_order": execution_order,
            "nodes": plan_nodes,
            "requirements": {
                "gpu": bool(gpu_nodes),
                "gpu_nodes": sorted(gpu_nodes),
                "executables": sorted(executables),
            },
            "will_execute": False,
            **({"resume_checkpoint": resume_checkpoint} if resume_checkpoint else {}),
        }

    async def _dry_run_subgraph(
        self,
        *,
        node: dict[str, Any],
        run_id: str,
        force: bool,
        force_nodes: set[str],
        options: dict[str, Any],
        workflow_parameters: dict[str, Any],
    ) -> dict[str, Any]:
        """Plan a subgraph node's embedded workflow for dry_run.

        Inner plan entries are surfaced with ``<subgraph_id>/<inner_id>`` node
        ids (nested subgraphs compose the prefix), their planned output paths
        are re-rooted under the subgraph's run directory, and the inner
        executables/GPU requirements are aggregated for the caller to merge
        into the workflow-level ``requirements``.
        """
        empty = {"nodes": [], "node_count": 0, "executables": set(), "gpu_nodes": [], "error": ""}
        raw_params = node.get("params")
        params = raw_params if isinstance(raw_params, dict) else {}
        inner_workflow = params.get("workflow")
        if not isinstance(inner_workflow, dict) or not inner_workflow.get("nodes"):
            return {**empty, "error": "subgraph node is missing its embedded workflow"}

        subgraph_id = str(node.get("id", "") or "")
        inner_seed = self._subgraph_seed(workflow_parameters, subgraph_id)
        inner_options = {
            key: value
            for key, value in (options or {}).items()
            if key in ("parameters", "api_secrets")
        }
        inner_parameters = dict(inner_options.get("parameters") or {})
        inner_parameters["subgraph_seed"] = inner_seed
        inner_options["parameters"] = inner_parameters

        preview = await self.dry_run(
            run_id=run_id,
            workflow=copy.deepcopy(inner_workflow),
            force=force,
            force_nodes=force_nodes,
            options=inner_options,
        )
        if preview.get("status") == "failed":
            return {**empty, "error": str(preview.get("error", ""))}

        run_dir_prefix = str(self.workspace_dir / "runs" / run_id)
        planned: list[dict[str, Any]] = []
        for entry in preview.get("nodes", []):
            if not isinstance(entry, dict):
                continue
            prefixed = dict(entry)
            prefixed["node_id"] = f"{subgraph_id}/{entry.get('node_id', '')}"
            prefixed["subgraph_path"] = subgraph_id
            prefixed["planned_outputs"] = self._replan_output_paths(
                entry.get("planned_outputs"), run_dir_prefix, subgraph_id
            )
            planned.append(prefixed)

        requirements = preview.get("requirements", {})
        return {
            "nodes": planned,
            "node_count": len(planned),
            "executables": {str(item) for item in requirements.get("executables", [])},
            "gpu_nodes": [
                f"{subgraph_id}/{node_id}" for node_id in requirements.get("gpu_nodes", [])
            ],
            "error": "",
        }

    @staticmethod
    def _replan_output_paths(value: Any, run_dir_prefix: str, subgraph_id: str) -> Any:
        """Re-root planned inner-workflow paths under the subgraph directory."""
        if isinstance(value, str):
            if not value.startswith(run_dir_prefix):
                return value
            remainder = value[len(run_dir_prefix):].lstrip("/\\")
            if not remainder:
                return value
            return str(Path(run_dir_prefix) / subgraph_id / remainder)
        if isinstance(value, list):
            return [
                WorkflowExecutor._replan_output_paths(item, run_dir_prefix, subgraph_id)
                for item in value
            ]
        if isinstance(value, dict):
            return {
                key: WorkflowExecutor._replan_output_paths(item, run_dir_prefix, subgraph_id)
                for key, item in value.items()
            }
        return value

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _executor_cache_policy(node_class: Any) -> str:
        return str(getattr(node_class, "EXECUTOR_CACHE_POLICY", "cacheable") or "cacheable")

    def _inactive_upstream(
        self,
        node_id: str,
        edge_map: dict[str, list[dict[str, Any]]],
        skipped_nodes: set[str],
        node_inactive_outputs: dict[str, set[str]],
        node_class: Any = None,
    ) -> dict[str, str] | None:
        """Return the first upstream branch edge that should prevent execution."""
        if self._allows_inactive_inputs(node_class):
            return None
        for edge in edge_map.get(node_id, []):
            src = edge_source(edge)
            src_port = edge_source_port(edge)
            if src in skipped_nodes:
                return {"source_node": src, "source_output": src_port}
            if src_port in node_inactive_outputs.get(src, set()):
                return {"source_node": src, "source_output": src_port}
        return None

    def _inactive_output_ports(
        self,
        result: dict[str, Any],
        outputs: dict[str, Any],
        node_class: Any,
    ) -> set[str]:
        """Extract inactive output ports from flow-control node results."""
        if not self._routes_flow(node_class):
            return set()
        raw = result.get("inactive_outputs")
        if raw is not None:
            return {str(port) for port in raw}
        branch_meta = result.get("_branch_meta")
        if isinstance(branch_meta, dict):
            raw = branch_meta.get("inactive_ports")
            if raw is not None:
                return {str(port) for port in raw}
            active_ports = branch_meta.get("active_ports")
            if active_ports is not None:
                return set(outputs) - {str(port) for port in active_ports}
        return {str(port) for port, value in outputs.items() if value is None}

    def _apply_skip_downstream(
        self,
        run_id: str,
        source_node_id: str,
        result: dict[str, Any],
        node_class: Any,
        nodes: dict[str, dict[str, Any]],
        node_results: dict[str, dict[str, Any]],
        skipped_nodes: set[str],
        emit: Callable[[str, dict[str, Any]], None],
    ) -> set[str]:
        """Mark branch-meta skip_downstream nodes as skipped before they run."""
        skipped = self._skip_downstream_node_ids(result, node_class, nodes)
        skipped.discard(source_node_id)
        applied: set[str] = set()
        for node_id in sorted(skipped):
            if node_id in node_results:
                continue
            node_results[node_id] = {
                "status": "skipped",
                "reason": "skip_downstream",
                "upstream": {"source_node": source_node_id},
            }
            skipped_nodes.add(node_id)
            applied.add(node_id)
            emit(
                "node_skip",
                {
                    "run_id": run_id,
                    "node_id": node_id,
                    "reason": "skip_downstream",
                    "upstream": {"source_node": source_node_id},
                },
            )
        return applied

    def _skip_downstream_node_ids(
        self,
        result: dict[str, Any],
        node_class: Any,
        nodes: dict[str, dict[str, Any]],
    ) -> set[str]:
        """Extract known downstream node IDs from flow-control skip metadata."""
        if not self._routes_flow(node_class):
            return set()
        raw = result.get("skip_downstream")
        branch_meta = result.get("_branch_meta")
        if raw is None and isinstance(branch_meta, dict):
            raw = branch_meta.get("skip_downstream")
        if raw is None:
            return set()
        if isinstance(raw, str):
            candidates = [raw]
        else:
            try:
                candidates = list(raw)
            except TypeError:
                candidates = [raw]
        return {str(node_id) for node_id in candidates if str(node_id) in nodes}

    @staticmethod
    def _routes_flow(node_class: Any) -> bool:
        return bool(getattr(node_class, "ROUTES_FLOW", False))

    @staticmethod
    def _allows_inactive_inputs(node_class: Any) -> bool:
        return bool(getattr(node_class, "ALLOW_INACTIVE_INPUTS", False))

    @staticmethod
    def _upstream_node_ids(node_id: str, upstream_of: dict[str, list[str]]) -> set[str]:
        """Return all upstream ancestors for a node in the execution graph."""
        upstream_nodes: set[str] = set()
        queue: deque[str] = deque(upstream_of.get(node_id, []))
        while queue:
            upstream = queue.popleft()
            if upstream in upstream_nodes:
                continue
            upstream_nodes.add(upstream)
            queue.extend(upstream_of.get(upstream, []))
        return upstream_nodes

    @staticmethod
    def _continue_on_fail(node: dict[str, Any]) -> bool:
        meta = node.get("meta", {})
        if not isinstance(meta, dict):
            meta = {}
        return any(
            bool(container.get(key))
            for container in (node, meta)
            for key in ("continueOnFail", "continue_on_fail")
            if isinstance(container, dict)
        )

    @staticmethod
    def _error_outputs(
        *,
        node: dict[str, Any],
        error: Exception,
        message: str,
        traceback_text: str,
        attempts: int,
    ) -> dict[str, Any]:
        declared_outputs = node.get("outputs", {})
        output_ports = list(declared_outputs) if isinstance(declared_outputs, dict) else []
        values: dict[str, Any] = {
            "error": message,
            "error_message": str(error),
            "error_type": type(error).__name__,
            "traceback": traceback_text,
            "attempts": attempts,
        }
        if not output_ports:
            return values
        return {port: values.get(port, None) for port in output_ports}

    @staticmethod
    def _executes_loop_body(node_class: Any) -> bool:
        return bool(getattr(node_class, "EXECUTES_LOOP_BODY", False))

    @staticmethod
    def _executes_try_catch_branches(node_class: Any) -> bool:
        return bool(getattr(node_class, "EXECUTES_TRY_CATCH_BRANCHES", False))

    def _node_class_for(self, node: dict[str, Any]) -> Any:
        node_class = node.get("_node_class")
        if node_class is None and self.registry is not None and hasattr(self.registry, "get"):
            node_class = self.registry.get(str(node.get("type", "unknown")))
        return node_class

    def _prepare_execution_plan_graph(
        self,
        workflow: dict[str, Any],
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Resolve workflow parameters and build the outer execution graph."""
        options = options or {}
        try:
            workflow_parameters = self._resolve_workflow_parameters(
                workflow.get("parameters", []),
                options.get("parameters", {}),
            )
        except ValueError as exc:
            return {"status": "failed", "error": str(exc)}

        visual_only_types = frozenset({"note"})
        raw_nodes_data = workflow.get("nodes", [])
        if isinstance(raw_nodes_data, dict):
            raw_nodes = []
            for node_id, node in raw_nodes_data.items():
                if isinstance(node, dict):
                    node_data = dict(node)
                elif hasattr(node, "model_dump"):
                    node_data = node.model_dump()
                else:
                    node_data = dict(getattr(node, "__dict__", {}))
                node_data.setdefault("id", str(node_id))
                raw_nodes.append(node_data)
        else:
            raw_nodes = list(raw_nodes_data or [])

        nodes: dict[str, dict[str, Any]] = {
            str(n["id"]): n
            for n in raw_nodes
            if isinstance(n, dict) and n.get("id") is not None and n.get("type") not in visual_only_types
        }
        edges: list[dict[str, Any]] = list(workflow.get("edges", []) or [])
        target_nodes = self._coerce_node_id_set(options.get("target_nodes"))

        if target_nodes:
            raw_node_ids = {
                str(n["id"])
                for n in raw_nodes
                if isinstance(n, dict) and n.get("id") is not None
            }
            unknown_targets = sorted(target_nodes - raw_node_ids)
            if unknown_targets:
                return {
                    "status": "failed",
                    "error": f"Unknown target node(s): {', '.join(unknown_targets)}",
                }

            executable_targets = target_nodes & set(nodes)
            if executable_targets:
                required_nodes = self._upstream_closure(executable_targets, nodes, edges)
                nodes = {nid: node for nid, node in nodes.items() if nid in required_nodes}
                edges = [
                    edge
                    for edge in edges
                    if edge_source(edge) in nodes and edge_target(edge) in nodes
                ]
            else:
                nodes = {}
                edges = []

        all_nodes = nodes
        loop_bodies = self._loop_bodies(all_nodes, edges)
        try_catch_regions = self._try_catch_regions(all_nodes, edges)
        loop_body_node_ids = {body_node for body in loop_bodies.values() for body_node in body}
        try_catch_body_node_ids = {
            body_node
            for branches in try_catch_regions.values()
            for body in branches.values()
            for body_node in body
        }
        internal_node_ids = loop_body_node_ids | try_catch_body_node_ids
        nodes = {
            node_id: node
            for node_id, node in all_nodes.items()
            if node_id not in internal_node_ids
        }
        outer_edges = [
            edge
            for edge in edges
            if edge_source(edge) in nodes and edge_target(edge) in nodes
        ]

        upstream_of: dict[str, list[str]] = {nid: [] for nid in nodes}
        downstream_of: dict[str, list[str]] = {nid: [] for nid in nodes}
        edge_map: dict[str, list[dict[str, Any]]] = {nid: [] for nid in nodes}

        for edge in outer_edges:
            src = edge_source(edge)
            tgt = edge_target(edge)
            if src in nodes and tgt in nodes:
                upstream_of[tgt].append(src)
                downstream_of[src].append(tgt)
                edge_map[tgt].append(edge)

        try:
            execution_order = self._topological_sort(nodes, upstream_of, downstream_of)
        except ValueError as exc:
            return {"status": "failed", "error": str(exc)}

        return {
            "status": "ok",
            "workflow_parameters": workflow_parameters,
            "target_nodes": target_nodes,
            "all_nodes": all_nodes,
            "nodes": nodes,
            "edges": edges,
            "outer_edges": outer_edges,
            "edge_map": edge_map,
            "upstream_of": upstream_of,
            "downstream_of": downstream_of,
            "execution_order": execution_order,
            "loop_bodies": loop_bodies,
            "try_catch_regions": try_catch_regions,
        }

    def _dry_run_planned_outputs(
        self,
        node_class: Any,
        resolved_params: dict[str, Any],
        node_dir: Path,
    ) -> list[Path] | dict[str, Any]:
        """Plan node outputs without invoking the node's run method."""
        if node_class is None or not hasattr(node_class, "PLAN_OUTPUTS"):
            return []

        with tempfile.TemporaryDirectory(prefix="bionodulo-dry-run-") as scratch:
            scratch_dir = Path(scratch)
            plan_inputs = dict(resolved_params)
            scratch_output_dir = scratch_dir / str(getattr(node_class, "NODE_ID", "") or "")
            plan_inputs["output"] = str(scratch_output_dir)
            plan_inputs["output_dir"] = str(scratch_output_dir)
            planned = node_class.PLAN_OUTPUTS(plan_inputs, scratch_dir)
            return self._remap_planned_paths(planned, scratch_dir, node_dir)

    def _remap_planned_paths(
        self,
        value: Any,
        scratch_dir: Path,
        node_dir: Path,
    ) -> Any:
        if isinstance(value, Path):
            try:
                return node_dir / value.relative_to(scratch_dir)
            except ValueError:
                return value
        if isinstance(value, str):
            try:
                path = Path(value)
                return str(node_dir / path.relative_to(scratch_dir))
            except ValueError:
                return value
        if isinstance(value, list):
            return [self._remap_planned_paths(item, scratch_dir, node_dir) for item in value]
        if isinstance(value, tuple):
            return tuple(self._remap_planned_paths(item, scratch_dir, node_dir) for item in value)
        if isinstance(value, dict):
            return {
                key: self._remap_planned_paths(item, scratch_dir, node_dir)
                for key, item in value.items()
            }
        return value

    @staticmethod
    def _planned_output_map(
        node_class: Any,
        planned_paths: list[Path] | tuple[Any, ...] | dict[str, Any],
    ) -> dict[str, Any]:
        custom_mapper = getattr(node_class, "MAP_PLANNED_OUTPUTS", None)
        if callable(custom_mapper):
            mapped = custom_mapper(planned_paths)
            if not isinstance(mapped, dict):
                raise TypeError(
                    f"{getattr(node_class, 'NODE_ID', node_class)!r} "
                    "MAP_PLANNED_OUTPUTS must return a mapping"
                )

            def normalize(value: Any) -> Any:
                if isinstance(value, Path):
                    return str(value)
                if isinstance(value, list):
                    return [normalize(item) for item in value]
                if isinstance(value, tuple):
                    return tuple(normalize(item) for item in value)
                if isinstance(value, dict):
                    return {
                        str(name): normalize(item)
                        for name, item in value.items()
                    }
                return value

            return {
                str(name): normalize(value)
                for name, value in mapped.items()
            }

        if isinstance(planned_paths, dict):
            return {
                str(name): str(path) if isinstance(path, Path) else path
                for name, path in planned_paths.items()
            }

        return_names = getattr(node_class, "RETURN_NAMES", ()) or ()
        outputs: dict[str, Any] = {}
        for idx, path in enumerate(planned_paths or []):
            name = return_names[idx] if idx < len(return_names) else f"output_{idx}"
            outputs[str(name)] = str(path) if isinstance(path, Path) else path
        return outputs

    def _dry_run_command(
        self,
        node_class: Any,
        resolved_params: dict[str, Any],
        node_dir: Path,
    ) -> str | list[str] | None:
        """Render the command a command-style node would submit."""
        if node_class is None or not hasattr(node_class, "render_command"):
            return None

        from bionodulo.nodes.command_node import _shell_join

        command_inputs = dict(resolved_params)
        node_output_dir = node_dir / str(getattr(node_class, "NODE_ID", "") or "")
        command_inputs["output"] = str(node_output_dir)
        command_inputs["output_dir"] = str(node_output_dir)
        try:
            command = node_class.render_command(command_inputs)
        except Exception as exc:  # noqa: BLE001 - a preview must not fail the plan
            # Command rendering can legitimately depend on runtime inputs a dry
            # run cannot know yet (e.g. a subgraph port placeholder). Surface the
            # reason on the plan entry instead of failing the whole preview.
            logger.debug("dry-run command render failed for %s: %s", node_class, exc)
            return None
        if getattr(node_class, "SHELL", False) and isinstance(command, list):
            return _shell_join(command)
        return command

    @staticmethod
    def _redact_command(command: str | list[str] | None, resolved_params: dict[str, Any]) -> str | list[str] | None:
        if command is None:
            return None
        redacted_params = redact_tree(resolved_params)
        replacements = {
            str(value): str(redacted_params.get(key))
            for key, value in resolved_params.items()
            if redacted_params.get(key) == "***" and isinstance(value, (str, int, float))
        }

        def _redact_text(text: str) -> str:
            redacted = text
            for raw, replacement in replacements.items():
                if raw:
                    redacted = redacted.replace(raw, replacement)
            return redacted

        if isinstance(command, list):
            return [_redact_text(str(part)) for part in command]
        return _redact_text(command)

    @staticmethod
    def _public_plan_values(value: Any) -> Any:
        """Return a JSON-friendly planning value with private metadata omitted."""
        if isinstance(value, dict):
            return {
                str(key): WorkflowExecutor._public_plan_values(item)
                for key, item in value.items()
                if not str(key).startswith("_")
            }
        if isinstance(value, list):
            return [WorkflowExecutor._public_plan_values(item) for item in value]
        if isinstance(value, tuple):
            return [WorkflowExecutor._public_plan_values(item) for item in value]
        if isinstance(value, set):
            return sorted(WorkflowExecutor._public_plan_values(item) for item in value)
        if isinstance(value, Path):
            return str(value)
        return value

    def _loop_bodies(
        self,
        nodes: dict[str, dict[str, Any]],
        edges: list[dict[str, Any]],
    ) -> dict[str, set[str]]:
        bodies: dict[str, set[str]] = {}
        for node_id, node in nodes.items():
            if self._executes_loop_body(self._node_class_for(node)):
                bodies[node_id] = self._find_loop_body(node_id, edges, nodes)
        return bodies

    def _find_loop_body(
        self,
        loop_node_id: str,
        edges: list[dict[str, Any]],
        nodes: dict[str, dict[str, Any]],
    ) -> set[str]:
        body: set[str] = set()
        queue: deque[str] = deque()
        for edge in edges:
            if edge_source(edge) != loop_node_id:
                continue
            if edge_source_port(edge) != "iteration":
                continue
            target = edge_target(edge)
            if target in nodes and target != loop_node_id:
                body.add(target)
                queue.append(target)

        while queue:
            current = queue.popleft()
            # Nested loop nodes own their own bodies; stop the outer body at
            # the nested node so its feedback edges stay out of this graph.
            if current != loop_node_id and self._executes_loop_body(self._node_class_for(nodes.get(current, {}))):
                continue
            for edge in edges:
                if edge_source(edge) != current:
                    continue
                next_node = edge_target(edge)
                if next_node == loop_node_id or next_node not in nodes or next_node in body:
                    continue
                body.add(next_node)
                queue.append(next_node)
        return body

    def _coerce_node_id_set(self, value: Any) -> set[str]:
        """Normalize an option value into a set of non-empty node IDs."""
        if value is None:
            return set()
        if isinstance(value, str):
            values = [value]
        else:
            try:
                values = list(value)
            except TypeError:
                values = [value]
        return {
            str(node_id).strip()
            for node_id in values
            if node_id is not None and str(node_id).strip()
        }

    def _upstream_closure(
        self,
        target_nodes: set[str],
        nodes: dict[str, dict[str, Any]],
        edges: list[dict[str, Any]],
    ) -> set[str]:
        """Return target nodes plus all executable upstream dependencies."""
        upstream_of: dict[str, list[str]] = {nid: [] for nid in nodes}
        for edge in edges:
            src = edge_source(edge)
            tgt = edge_target(edge)
            if src in nodes and tgt in nodes:
                upstream_of[tgt].append(src)

        required = set(target_nodes)
        queue = deque(target_nodes)
        while queue:
            current = queue.popleft()
            for upstream in upstream_of.get(current, []):
                if upstream in required:
                    continue
                required.add(upstream)
                queue.append(upstream)
        return required

    def _downstream_closure(
        self,
        start_node: str,
        nodes: dict[str, dict[str, Any]],
        edges: list[dict[str, Any]],
    ) -> set[str]:
        """Return start node plus all executable downstream dependents."""
        downstream_of: dict[str, list[str]] = {nid: [] for nid in nodes}
        for edge in edges:
            src = edge_source(edge)
            tgt = edge_target(edge)
            if src in nodes and tgt in nodes:
                downstream_of[src].append(tgt)

        reachable = {start_node}
        queue = deque([start_node])
        while queue:
            current = queue.popleft()
            for downstream in downstream_of.get(current, []):
                if downstream in reachable:
                    continue
                reachable.add(downstream)
                queue.append(downstream)
        return reachable

    def _restrict_graph_for_resume(
        self,
        *,
        resume_node_id: str,
        nodes: dict[str, dict[str, Any]],
        outer_edges: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Build the executable downstream subgraph for checkpoint resume."""
        if resume_node_id not in nodes:
            raise ValueError(f"Resume checkpoint node '{resume_node_id}' is not executable in this workflow")

        resume_nodes = self._downstream_closure(resume_node_id, nodes, outer_edges)
        restricted_nodes = {
            node_id: node
            for node_id, node in nodes.items()
            if node_id in resume_nodes
        }
        restricted_edges = [
            edge
            for edge in outer_edges
            if edge_source(edge) in restricted_nodes
            and edge_target(edge) in restricted_nodes
            and edge_target(edge) != resume_node_id
        ]

        upstream_of: dict[str, list[str]] = {nid: [] for nid in restricted_nodes}
        downstream_of: dict[str, list[str]] = {nid: [] for nid in restricted_nodes}
        edge_map: dict[str, list[dict[str, Any]]] = {nid: [] for nid in restricted_nodes}

        for edge in restricted_edges:
            src = edge_source(edge)
            tgt = edge_target(edge)
            upstream_of[tgt].append(src)
            downstream_of[src].append(tgt)
            edge_map[tgt].append(edge)

        execution_order = self._topological_sort(restricted_nodes, upstream_of, downstream_of)
        return {
            "nodes": restricted_nodes,
            "outer_edges": restricted_edges,
            "edge_map": edge_map,
            "upstream_of": upstream_of,
            "downstream_of": downstream_of,
            "execution_order": execution_order,
        }

    def _load_checkpoint_payload(self, checkpoint_entry: dict[str, Any]) -> dict[str, Any]:
        checkpoint_path = Path(str(checkpoint_entry.get("checkpoint_path", ""))).expanduser()
        if not checkpoint_path.is_file():
            raise ValueError(f"Resume checkpoint artifact was not found: {checkpoint_path}")

        try:
            if checkpoint_path.suffix == ".gz" or bool(checkpoint_entry.get("compressed")):
                raw_text = gzip.decompress(checkpoint_path.read_bytes()).decode("utf-8")
            else:
                raw_text = checkpoint_path.read_text(encoding="utf-8")
            payload = json.loads(raw_text)
        except (OSError, gzip.BadGzipFile, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"Resume checkpoint artifact is unreadable: {checkpoint_path}") from exc
        if not isinstance(payload, dict):
            raise ValueError("Resume checkpoint artifact must contain a JSON object")
        if "data" not in payload:
            raise ValueError("Resume checkpoint artifact is missing data")
        return payload

    def _resume_checkpoint_outputs(self, checkpoint_entry: dict[str, Any]) -> dict[str, Any]:
        payload = self._load_checkpoint_payload(checkpoint_entry)
        normalized_entry = dict(checkpoint_entry)
        normalized_entry["checkpoint_path"] = str(Path(str(normalized_entry.get("checkpoint_path", ""))).expanduser())
        return {
            "passthrough": payload["data"],
            "checkpoint_file": normalized_entry["checkpoint_path"],
            "checkpoint_info": json.dumps(normalized_entry, sort_keys=True, default=str),
        }

    def _try_catch_regions(
        self,
        nodes: dict[str, dict[str, Any]],
        edges: list[dict[str, Any]],
    ) -> dict[str, dict[str, set[str]]]:
        regions: dict[str, dict[str, set[str]]] = {}
        for node_id, node in nodes.items():
            if not self._executes_try_catch_branches(self._node_class_for(node)):
                continue
            regions[node_id] = {
                "try": self._find_try_catch_branch(node_id, "try", "_try_result", edges, nodes),
                "catch": self._find_try_catch_branch(node_id, "catch", "_catch_result", edges, nodes),
            }
        return regions

    def _find_try_catch_branch(
        self,
        control_node_id: str,
        branch_port: str,
        return_port: str,
        edges: list[dict[str, Any]],
        nodes: dict[str, dict[str, Any]],
    ) -> set[str]:
        reachable: set[str] = set()
        queue: deque[str] = deque()
        for edge in edges:
            if edge_source(edge) != control_node_id or edge_source_port(edge) != branch_port:
                continue
            target = edge_target(edge)
            if target in nodes and target != control_node_id:
                reachable.add(target)
                queue.append(target)

        while queue:
            current = queue.popleft()
            for edge in edges:
                if edge_source(edge) != current:
                    continue
                next_node = edge_target(edge)
                if next_node == control_node_id or next_node not in nodes or next_node in reachable:
                    continue
                reachable.add(next_node)
                queue.append(next_node)

        return_sources = {
            edge_source(edge)
            for edge in edges
            if edge_target(edge) == control_node_id
            and edge_target_port(edge) == return_port
            and edge_source(edge) in reachable
        }
        if not return_sources:
            return reachable

        reverse_edges: dict[str, list[str]] = {node_id: [] for node_id in reachable}
        for edge in edges:
            source = edge_source(edge)
            target = edge_target(edge)
            if source in reachable and target in reachable:
                reverse_edges.setdefault(target, []).append(source)

        branch: set[str] = set(return_sources)
        queue = deque(return_sources)
        while queue:
            current = queue.popleft()
            for upstream in reverse_edges.get(current, []):
                if upstream in branch:
                    continue
                branch.add(upstream)
                queue.append(upstream)
        return branch

    # Types that indicate a file or directory path parameter
    _FILE_TYPES: set[str] = {
        "FASTQ_LIST", "FASTA", "FASTQ", "BAM", "SAM", "VCF", "GFF", "GTF",
        "BED", "WIG", "BIGWIG", "FILE", "DIR", "PATH", "INDEX_DIR", "BWA_MEM2_INDEX", "BOWTIE2_INDEX",
        "REFERENCE", "READS", "ASSEMBLY", "CONTIGS", "ALIGNMENT",
        "GFA", "ODGI", "REPORT", "PLOT", "IMAGE", "TABLE", "MATRIX", "TREE",
    }

    def _resolve_file_paths(
        self,
        node_class: Any,
        inputs: dict[str, Any],
    ) -> dict[str, Any]:
        """Resolve relative file paths in inputs against the workspace root."""
        try:
            input_types = node_class.INPUT_TYPES()
        except Exception:
            return inputs

        # Collect parameter names whose type indicates a file path
        file_params: set[str] = set()
        for section in ("required", "optional", "hidden"):
            for name, spec in input_types.get(section, {}).items():
                if isinstance(spec, tuple) and len(spec) > 0:
                    type_name = spec[0]
                    if isinstance(type_name, str) and type_name.upper() in self._FILE_TYPES:
                        file_params.add(name)

        if not file_params:
            return inputs

        resolved = dict(inputs)
        for name in file_params:
            if name not in resolved:
                continue
            val = resolved[name]
            if isinstance(val, str):
                resolved[name] = self._resolve_single_path(val)
            elif isinstance(val, (list, tuple)):
                resolved[name] = [
                    self._resolve_single_path(v) if isinstance(v, str) else v
                    for v in val
                ]
        return resolved

    def _resolve_single_path(self, path_str: str) -> str:
        """Convert a relative path to absolute against the workspace root."""
        if not path_str or path_str.startswith("/") or path_str.startswith("~"):
            return path_str
        # Leave URLs and simple names alone
        if "://" in path_str or "/" not in path_str:
            return path_str
        # Try workspace_dir first
        abs_path = (self.workspace_dir / path_str).resolve()
        if abs_path.exists():
            return str(abs_path)
        # Fallback: resolve relative to cwd (repo root when server starts from repo)
        cwd_path = Path(path_str).resolve()
        if cwd_path.exists():
            return str(cwd_path)
        return path_str

    async def _execute_body_node(
        self,
        *,
        ctx: ExecutionContext,
        node: dict[str, Any],
        inputs: dict[str, Any],
        all_nodes: dict[str, dict[str, Any]],
        edges: list[dict[str, Any]],
        node_outputs: dict[str, dict[str, Any]],
        options: dict[str, Any],
        workflow: dict[str, Any],
        emit: Callable[[str, dict[str, Any]], None],
    ) -> dict[str, Any]:
        """Execute one loop-body node, recursing into nested loop nodes."""
        if self._executes_loop_body(self._node_class_for(node)):
            return await self._execute_loop_node(
                ctx=ctx,
                node=node,
                inputs=inputs,
                all_nodes=all_nodes,
                edges=edges,
                body_node_ids=self._find_loop_body(str(node.get("id", "")), edges, all_nodes),
                node_outputs=node_outputs,
                options=options,
                workflow=workflow,
                emit=emit,
            )
        return await self._execute_node(ctx, node, inputs)

    async def _execute_loop_node(
        self,
        *,
        ctx: ExecutionContext,
        node: dict[str, Any],
        inputs: dict[str, Any],
        all_nodes: dict[str, dict[str, Any]],
        edges: list[dict[str, Any]],
        body_node_ids: set[str],
        node_outputs: dict[str, dict[str, Any]],
        options: dict[str, Any],
        workflow: dict[str, Any],
        emit: Callable[[str, dict[str, Any]], None],
    ) -> dict[str, Any]:
        """Execute a ForEach-style node by re-running its body subgraph."""
        if self._is_while_loop_node(node):
            return await self._execute_while_loop_node(
                ctx=ctx,
                node=node,
                inputs=inputs,
                all_nodes=all_nodes,
                edges=edges,
                body_node_ids=body_node_ids,
                node_outputs=node_outputs,
                options=options,
                workflow=workflow,
                emit=emit,
            )

        if self._is_parallel_for_node(node):
            return await self._execute_parallel_for_node(
                ctx=ctx,
                node=node,
                inputs=inputs,
                all_nodes=all_nodes,
                edges=edges,
                body_node_ids=body_node_ids,
                node_outputs=node_outputs,
                options=options,
                workflow=workflow,
                emit=emit,
            )

        if not body_node_ids:
            return await self._execute_node(ctx, node, inputs)

        items = self._coerce_loop_items(inputs.get("items", []))
        iteration_mode = str(inputs.get("iteration_mode", "single") or "single")
        collect_mode = str(inputs.get("collect_mode", "list") or "list")
        stop_on_error = bool(inputs.get("stop_on_error", True))
        max_iterations = max(1, int(inputs.get("max_iterations", 1000) or 1000))
        batches = self._loop_batches(items, iteration_mode, int(inputs.get("batch_size", 1) or 1))

        if len(batches) > max_iterations:
            raise RuntimeError(f"Loop {ctx.node_id} would exceed max_iterations={max_iterations}")

        body_nodes = {node_id: all_nodes[node_id] for node_id in body_node_ids if node_id in all_nodes}
        body_edge_map = self._loop_body_edge_map(ctx.node_id, body_node_ids, edges)
        body_order = self._loop_body_order(body_nodes, edges)
        collected: list[Any] = []
        processed_count = 0
        all_succeeded = True
        loop_state: dict[str, Any] = {}

        for iteration_index, batch in enumerate(batches):
            if ctx.cancel_event.is_set():
                raise RuntimeError(f"Loop {ctx.node_id} cancelled")
            iteration_value: Any = batch if iteration_mode == "batch" else batch[0]
            local_outputs: dict[str, dict[str, Any]] = {
                ctx.node_id: {"iteration": iteration_value},
            }
            local_inactive_outputs: dict[str, set[str]] = {}
            local_skipped_nodes: set[str] = set()
            loop_signal = "none"

            try:
                for body_node_id in body_order:
                    body_node = body_nodes[body_node_id]
                    body_type = str(body_node.get("type", "unknown"))
                    body_class = self._node_class_for(body_node)
                    visible_iteration = iteration_index + 1
                    emit(
                        "node_start",
                        {
                            "run_id": ctx.run_id,
                            "node_id": body_node_id,
                            "node_type": body_type,
                            "loop_parent": ctx.node_id,
                            "iteration": visible_iteration,
                        },
                    )

                    inactive_upstream = self._inactive_upstream(
                        body_node_id,
                        body_edge_map,
                        local_skipped_nodes,
                        local_inactive_outputs,
                        body_class,
                    )
                    if inactive_upstream is not None:
                        local_skipped_nodes.add(body_node_id)
                        emit(
                            "node_skip",
                            {
                                "run_id": ctx.run_id,
                                "node_id": body_node_id,
                                "reason": "inactive_branch",
                                "upstream": inactive_upstream,
                                "loop_parent": ctx.node_id,
                                "iteration": visible_iteration,
                            },
                        )
                        continue

                    combined_outputs = {**node_outputs, **local_outputs}
                    body_inputs = self._resolve_inputs(
                        body_node_id,
                        body_node,
                        body_edge_map,
                        combined_outputs,
                        ctx.run_metadata.get("workflow_parameters", {}),
                    )
                    body_params = self._with_defaults(
                        body_node,
                        body_inputs,
                        body_class,
                        ctx.run_metadata.get("workflow_parameters", {}),
                    )
                    hidden_inputs = self._declared_hidden_inputs(body_class)
                    if "_loop_state" in hidden_inputs:
                        body_params["_loop_state"] = loop_state
                    if "_iteration" in hidden_inputs:
                        body_params["_iteration"] = iteration_index
                    body_dir = (
                        ctx.node_dir
                        / "iterations"
                        / f"{visible_iteration:04d}"
                        / body_node_id
                    )
                    body_dir.mkdir(parents=True, exist_ok=True)
                    body_ctx = ExecutionContext(
                        run_id=ctx.run_id,
                        node_id=body_node_id,
                        node_type=body_type,
                        node_dir=body_dir,
                        workspace_dir=self.workspace_dir,
                        params=body_params,
                        api_secrets=self._api_secrets_for_options(options),
                        emit=emit,
                        cancel_event=ctx.cancel_event,
                        env_prefix=self._env_prefix_for_node(body_node, workflow),
                        run_metadata=ctx.run_metadata,
                        executor=ctx.executor or self,
                        registry=ctx.registry if ctx.registry is not None else self.registry,
                        hpc_backend=ctx.hpc_backend,
                    )
                    body_result = await self._execute_body_node(
                        ctx=body_ctx,
                        node=body_node,
                        inputs=body_inputs,
                        all_nodes=all_nodes,
                        edges=edges,
                        node_outputs=combined_outputs,
                        options=options,
                        workflow=workflow,
                        emit=emit,
                    )
                    outputs = body_result.get("outputs", {})
                    inactive_outputs = self._inactive_output_ports(
                        body_result,
                        outputs,
                        body_class,
                    )
                    if inactive_outputs:
                        local_inactive_outputs[body_node_id] = inactive_outputs
                    local_outputs[body_node_id] = outputs
                    emit(
                        "node_complete",
                        {
                            "run_id": ctx.run_id,
                            "node_id": body_node_id,
                            "outputs": outputs,
                            "loop_parent": ctx.node_id,
                            "iteration": visible_iteration,
                        },
                    )
                    loop_signal = self._loop_control_signal(body_result)
                    if loop_signal in {"break", "continue"}:
                        break

                if loop_signal == "break":
                    processed_count += len(batch)
                    break
                if loop_signal != "continue":
                    body_value = self._loop_body_result(ctx.node_id, edges, local_outputs, body_order)
                    self._append_loop_result(collected, body_value, collect_mode)
                processed_count += len(batch)
            except Exception as exc:
                all_succeeded = False
                emit(
                    "node_error",
                    {
                        "run_id": ctx.run_id,
                        "node_id": ctx.node_id,
                        "error": f"Loop iteration {iteration_index + 1} failed: {exc}",
                    },
                )
                if stop_on_error:
                    raise
                self._append_loop_result(
                    collected,
                    {"iteration": iteration_index + 1, "error": str(exc)},
                    collect_mode,
                )
                processed_count += len(batch)

            if loop_signal == "break":
                break

        return {
            "outputs": {
                "iteration": None,
                "results": collected,
                "count": processed_count,
                "all_succeeded": all_succeeded,
            },
            "inactive_outputs": ["iteration"],
        }

    async def _execute_while_loop_node(
        self,
        *,
        ctx: ExecutionContext,
        node: dict[str, Any],
        inputs: dict[str, Any],
        all_nodes: dict[str, dict[str, Any]],
        edges: list[dict[str, Any]],
        body_node_ids: set[str],
        node_outputs: dict[str, dict[str, Any]],
        options: dict[str, Any],
        workflow: dict[str, Any],
        emit: Callable[[str, dict[str, Any]], None],
    ) -> dict[str, Any]:
        """Execute a WhileLoop node by re-running its body until complete."""
        if not body_node_ids:
            return await self._execute_node(ctx, node, inputs)

        body_nodes = {node_id: all_nodes[node_id] for node_id in body_node_ids if node_id in all_nodes}
        body_edge_map = self._loop_body_edge_map(ctx.node_id, body_node_ids, edges)
        body_order = self._loop_body_order(body_nodes, edges)
        current_value = inputs.get("value")
        loop_result = await self._execute_node(ctx, node, inputs)
        flow_control = loop_result.get("flow_control", {})
        loop_state = dict(flow_control.get("loop_state", {})) if isinstance(flow_control, dict) else {}

        while isinstance(flow_control, dict) and not bool(flow_control.get("is_complete", True)):
            visible_iteration = int(loop_state.get("iteration", 0) or 0) + 1
            if ctx.cancel_event.is_set():
                raise RuntimeError(f"Loop {ctx.node_id} cancelled")

            local_outputs: dict[str, dict[str, Any]] = {
                ctx.node_id: {"iteration": current_value},
            }
            local_inactive_outputs: dict[str, set[str]] = {}
            local_skipped_nodes: set[str] = set()
            loop_signal = "none"

            for body_node_id in body_order:
                body_node = body_nodes[body_node_id]
                body_type = str(body_node.get("type", "unknown"))
                body_class = self._node_class_for(body_node)
                emit(
                    "node_start",
                    {
                        "run_id": ctx.run_id,
                        "node_id": body_node_id,
                        "node_type": body_type,
                        "loop_parent": ctx.node_id,
                        "iteration": visible_iteration,
                    },
                )

                inactive_upstream = self._inactive_upstream(
                    body_node_id,
                    body_edge_map,
                    local_skipped_nodes,
                    local_inactive_outputs,
                    body_class,
                )
                if inactive_upstream is not None:
                    local_skipped_nodes.add(body_node_id)
                    emit(
                        "node_skip",
                        {
                            "run_id": ctx.run_id,
                            "node_id": body_node_id,
                            "reason": "inactive_branch",
                            "upstream": inactive_upstream,
                            "loop_parent": ctx.node_id,
                            "iteration": visible_iteration,
                        },
                    )
                    continue

                combined_outputs = {**node_outputs, **local_outputs}
                body_inputs = self._resolve_inputs(
                    body_node_id,
                    body_node,
                    body_edge_map,
                    combined_outputs,
                    ctx.run_metadata.get("workflow_parameters", {}),
                )
                body_params = self._with_defaults(
                    body_node,
                    body_inputs,
                    body_class,
                    ctx.run_metadata.get("workflow_parameters", {}),
                )
                hidden_inputs = self._declared_hidden_inputs(body_class)
                if "_loop_state" in hidden_inputs:
                    body_params["_loop_state"] = loop_state
                if "_iteration" in hidden_inputs:
                    body_params["_iteration"] = visible_iteration - 1
                body_dir = (
                    ctx.node_dir
                    / "iterations"
                    / f"{visible_iteration:04d}"
                    / body_node_id
                )
                body_dir.mkdir(parents=True, exist_ok=True)
                body_ctx = ExecutionContext(
                    run_id=ctx.run_id,
                    node_id=body_node_id,
                    node_type=body_type,
                    node_dir=body_dir,
                    workspace_dir=self.workspace_dir,
                    params=body_params,
                    api_secrets=self._api_secrets_for_options(options),
                    emit=emit,
                    cancel_event=ctx.cancel_event,
                    env_prefix=self._env_prefix_for_node(body_node, workflow),
                    run_metadata=ctx.run_metadata,
                    executor=ctx.executor or self,
                    registry=ctx.registry if ctx.registry is not None else self.registry,
                    hpc_backend=ctx.hpc_backend,
                )
                body_result = await self._execute_body_node(
                    ctx=body_ctx,
                    node=body_node,
                    inputs=body_inputs,
                    all_nodes=all_nodes,
                    edges=edges,
                    node_outputs=combined_outputs,
                    options=options,
                    workflow=workflow,
                    emit=emit,
                )
                outputs = body_result.get("outputs", {})
                inactive_outputs = self._inactive_output_ports(body_result, outputs, body_class)
                if inactive_outputs:
                    local_inactive_outputs[body_node_id] = inactive_outputs
                local_outputs[body_node_id] = outputs
                emit(
                    "node_complete",
                    {
                        "run_id": ctx.run_id,
                        "node_id": body_node_id,
                        "outputs": outputs,
                        "loop_parent": ctx.node_id,
                        "iteration": visible_iteration,
                    },
                )
                loop_signal = self._loop_control_signal(body_result)
                if loop_signal in {"break", "continue"}:
                    break

            if loop_signal == "break":
                processed = list(loop_state.get("processed", []))
                loop_state["iteration"] = visible_iteration
                loop_state["processed"] = processed
                loop_state["is_complete"] = True
                return {
                    "outputs": {
                        "results": processed,
                        "iterations": visible_iteration,
                        "converged": False,
                    },
                    "inactive_outputs": [],
                    "flow_control": {
                        "type": "while_loop",
                        "phase": "break",
                        "is_complete": True,
                        "loop_state": dict(loop_state),
                    },
                }

            body_result_value = self._loop_body_result(ctx.node_id, edges, local_outputs, body_order)
            current_value = self._loop_feedback_value(
                ctx.node_id,
                "value",
                edges,
                local_outputs,
                fallback=body_result_value,
            )
            loop_inputs = {
                **inputs,
                "value": current_value,
                "_loop_state": loop_state,
                "_is_loop_iteration": True,
                "_body_result": None if loop_signal == "continue" else self._loop_feedback_value(
                    ctx.node_id,
                    "_body_result",
                    edges,
                    local_outputs,
                    fallback=body_result_value,
                ),
            }
            loop_ctx = replace(ctx, params={**ctx.params, **loop_inputs})
            loop_result = await self._execute_node(loop_ctx, node, loop_inputs)
            flow_control = loop_result.get("flow_control", {})
            loop_state = dict(flow_control.get("loop_state", {})) if isinstance(flow_control, dict) else loop_state

        return loop_result

    @staticmethod
    def _is_while_loop_node(node: dict[str, Any]) -> bool:
        node_class = node.get("_node_class")
        node_id = str(getattr(node_class, "NODE_ID", "") or node.get("type", ""))
        return node_id == "while_loop" or node_id.endswith("/while_loop")

    @staticmethod
    def _is_parallel_for_node(node: dict[str, Any]) -> bool:
        node_class = node.get("_node_class")
        node_id = str(getattr(node_class, "NODE_ID", "") or node.get("type", ""))
        return node_id == "parallel_for" or node_id.endswith("/parallel_for")

    async def _execute_parallel_for_node(
        self,
        *,
        ctx: ExecutionContext,
        node: dict[str, Any],
        inputs: dict[str, Any],
        all_nodes: dict[str, dict[str, Any]],
        edges: list[dict[str, Any]],
        body_node_ids: set[str],
        node_outputs: dict[str, dict[str, Any]],
        options: dict[str, Any],
        workflow: dict[str, Any],
        emit: Callable[[str, dict[str, Any]], None],
    ) -> dict[str, Any]:
        """Execute a ParallelFor body subgraph and gather its body results."""
        if not body_node_ids:
            return await self._execute_node(ctx, node, inputs)

        initial = await self._execute_node(ctx, node, inputs)
        flow_control = initial.get("flow_control", {})
        chunks = flow_control.get("chunks", []) if isinstance(flow_control, dict) else []
        if not isinstance(chunks, list):
            chunks = []
        max_concurrency = 1
        if isinstance(flow_control, dict):
            try:
                max_concurrency = max(1, int(flow_control.get("max_concurrency", 1) or 1))
            except (TypeError, ValueError):
                max_concurrency = 1

        body_nodes = {node_id: all_nodes[node_id] for node_id in body_node_ids if node_id in all_nodes}
        body_edge_map = self._loop_body_edge_map(ctx.node_id, body_node_ids, edges)
        body_order = self._loop_body_order(body_nodes, edges)
        loop_state: dict[str, Any] = {}
        semaphore = asyncio.Semaphore(max_concurrency)

        async def run_chunk(chunk_index: int, chunk: Any) -> tuple[int, Any, bool]:
            async with semaphore:
                if ctx.cancel_event.is_set():
                    raise RuntimeError(f"Parallel loop {ctx.node_id} cancelled")

                visible_iteration = chunk_index + 1
                iteration_value: Any = chunk[0] if isinstance(chunk, list) and len(chunk) == 1 else chunk
                local_outputs: dict[str, dict[str, Any]] = {
                    ctx.node_id: {"iteration": iteration_value},
                }
                local_inactive_outputs: dict[str, set[str]] = {}
                local_skipped_nodes: set[str] = set()

                try:
                    for body_node_id in body_order:
                        body_node = body_nodes[body_node_id]
                        body_type = str(body_node.get("type", "unknown"))
                        body_class = self._node_class_for(body_node)
                        emit(
                            "node_start",
                            {
                                "run_id": ctx.run_id,
                                "node_id": body_node_id,
                                "node_type": body_type,
                                "loop_parent": ctx.node_id,
                                "iteration": visible_iteration,
                            },
                        )

                        inactive_upstream = self._inactive_upstream(
                            body_node_id,
                            body_edge_map,
                            local_skipped_nodes,
                            local_inactive_outputs,
                            body_class,
                        )
                        if inactive_upstream is not None:
                            local_skipped_nodes.add(body_node_id)
                            emit(
                                "node_skip",
                                {
                                    "run_id": ctx.run_id,
                                    "node_id": body_node_id,
                                    "reason": "inactive_branch",
                                    "upstream": inactive_upstream,
                                    "loop_parent": ctx.node_id,
                                    "iteration": visible_iteration,
                                },
                            )
                            continue

                        combined_outputs = {**node_outputs, **local_outputs}
                        body_inputs = self._resolve_inputs(
                            body_node_id,
                            body_node,
                            body_edge_map,
                            combined_outputs,
                            ctx.run_metadata.get("workflow_parameters", {}),
                        )
                        body_params = self._with_defaults(
                            body_node,
                            body_inputs,
                            body_class,
                            ctx.run_metadata.get("workflow_parameters", {}),
                        )
                        hidden_inputs = self._declared_hidden_inputs(body_class)
                        if "_loop_state" in hidden_inputs:
                            body_params["_loop_state"] = loop_state
                        if "_iteration" in hidden_inputs:
                            body_params["_iteration"] = chunk_index
                        body_dir = (
                            self.workspace_dir
                            / "runs"
                            / ctx.run_id
                            / ctx.node_id
                            / "parallel"
                            / f"{visible_iteration:04d}"
                            / body_node_id
                        )
                        body_dir.mkdir(parents=True, exist_ok=True)
                        body_ctx = ExecutionContext(
                            run_id=ctx.run_id,
                            node_id=body_node_id,
                            node_type=body_type,
                            node_dir=body_dir,
                            workspace_dir=self.workspace_dir,
                            params=body_params,
                            api_secrets=self._api_secrets_for_options(options),
                            emit=emit,
                            cancel_event=ctx.cancel_event,
                            env_prefix=self._env_prefix_for_node(body_node, workflow),
                            run_metadata=ctx.run_metadata,
                            executor=ctx.executor or self,
                            registry=ctx.registry if ctx.registry is not None else self.registry,
                            hpc_backend=ctx.hpc_backend,
                        )
                        body_result = await self._execute_node(body_ctx, body_node, body_inputs)
                        outputs = body_result.get("outputs", {})
                        inactive_outputs = self._inactive_output_ports(
                            body_result,
                            outputs,
                            body_class,
                        )
                        if inactive_outputs:
                            local_inactive_outputs[body_node_id] = inactive_outputs
                        local_outputs[body_node_id] = outputs
                        emit(
                            "node_complete",
                            {
                                "run_id": ctx.run_id,
                                "node_id": body_node_id,
                                "outputs": outputs,
                                "loop_parent": ctx.node_id,
                                "iteration": visible_iteration,
                            },
                        )

                    return (
                        chunk_index,
                        self._loop_feedback_value(
                            ctx.node_id,
                            "_parallel_results",
                            edges,
                            local_outputs,
                            fallback=self._loop_body_result(ctx.node_id, edges, local_outputs, body_order),
                        ),
                        True,
                    )
                except Exception as exc:
                    emit(
                        "node_error",
                        {
                            "run_id": ctx.run_id,
                            "node_id": ctx.node_id,
                            "error": f"Parallel loop iteration {visible_iteration} failed: {exc}",
                        },
                    )
                    return chunk_index, None, False

        chunk_results = await asyncio.gather(
            *(run_chunk(chunk_index, chunk) for chunk_index, chunk in enumerate(chunks)),
        )
        chunk_results.sort(key=lambda item: item[0])
        parallel_results = [result for _chunk_index, result, _succeeded in chunk_results]
        all_succeeded = all(succeeded for _chunk_index, _result, succeeded in chunk_results)

        loop_inputs = {**inputs, "_parallel_results": parallel_results}
        loop_ctx = replace(ctx, params={**ctx.params, **loop_inputs})
        gathered = await self._execute_node(loop_ctx, node, loop_inputs)
        if not all_succeeded and isinstance(gathered.get("outputs"), dict):
            gathered["outputs"]["all_succeeded"] = False
        return gathered

    @staticmethod
    def _loop_control_signal(result: dict[str, Any]) -> str:
        flow_control = result.get("flow_control")
        if isinstance(flow_control, dict) and flow_control.get("type") == "break_continue":
            action = str(flow_control.get("action", "none") or "none").lower()
            if flow_control.get("triggered") is True and action in {"break", "continue"}:
                return action
        return "none"

    def _coerce_loop_items(self, value: Any) -> list[Any]:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, (tuple, set)):
            return list(value)
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return []
            if text.startswith("["):
                try:
                    parsed = json.loads(text)
                except json.JSONDecodeError:
                    parsed = None
                if isinstance(parsed, list):
                    return parsed
            path = Path(text)
            if path.exists() and path.is_file():
                return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
            if "\n" in text or "," in text:
                return [item.strip() for item in text.replace("\n", ",").split(",") if item.strip()]
            return [text]
        return [value]

    def _loop_batches(self, items: list[Any], iteration_mode: str, batch_size: int) -> list[list[Any]]:
        if not items:
            return []
        if iteration_mode != "batch":
            return [[item] for item in items]
        size = max(1, batch_size)
        return [items[index:index + size] for index in range(0, len(items), size)]

    def _loop_body_edge_map(
        self,
        loop_node_id: str,
        body_node_ids: set[str],
        edges: list[dict[str, Any]],
    ) -> dict[str, list[dict[str, Any]]]:
        edge_map: dict[str, list[dict[str, Any]]] = {node_id: [] for node_id in body_node_ids}
        for edge in edges:
            target = edge_target(edge)
            if target not in body_node_ids:
                continue
            source = edge_source(edge)
            if source == loop_node_id or source in body_node_ids:
                edge_map[target].append(edge)
        return edge_map

    def _loop_body_order(
        self,
        body_nodes: dict[str, dict[str, Any]],
        edges: list[dict[str, Any]],
    ) -> list[str]:
        upstream_of: dict[str, list[str]] = {node_id: [] for node_id in body_nodes}
        downstream_of: dict[str, list[str]] = {node_id: [] for node_id in body_nodes}
        for edge in edges:
            source = edge_source(edge)
            target = edge_target(edge)
            if source in body_nodes and target in body_nodes:
                upstream_of[target].append(source)
                downstream_of[source].append(target)
        return self._topological_sort(body_nodes, upstream_of, downstream_of)

    def _loop_body_result(
        self,
        loop_node_id: str,
        edges: list[dict[str, Any]],
        local_outputs: dict[str, dict[str, Any]],
        body_order: list[str],
    ) -> Any:
        values: list[Any] = []
        for edge in edges:
            if edge_target(edge) != loop_node_id or edge_target_port(edge) not in {"body_result", "_body_result"}:
                continue
            source = edge_source(edge)
            source_port = edge_source_port(edge)
            outputs = local_outputs.get(source, {})
            if source_port in outputs:
                values.append(outputs[source_port])
            elif "default" in outputs:
                values.append(outputs["default"])
        if len(values) == 1:
            return values[0]
        if values:
            return values
        if not body_order:
            return None
        outputs = local_outputs.get(body_order[-1], {})
        if len(outputs) == 1:
            return next(iter(outputs.values()))
        return outputs

    def _loop_feedback_value(
        self,
        loop_node_id: str,
        target_input: str,
        edges: list[dict[str, Any]],
        local_outputs: dict[str, dict[str, Any]],
        fallback: Any = None,
    ) -> Any:
        values: list[Any] = []
        for edge in edges:
            if edge_target(edge) != loop_node_id or edge_target_port(edge) != target_input:
                continue
            source = edge_source(edge)
            source_port = edge_source_port(edge)
            outputs = local_outputs.get(source, {})
            if source_port in outputs:
                values.append(outputs[source_port])
            elif "default" in outputs:
                values.append(outputs["default"])
        if len(values) == 1:
            return values[0]
        if values:
            return values
        return fallback

    def _append_loop_result(self, collected: list[Any], value: Any, collect_mode: str) -> None:
        if collect_mode == "concat" and isinstance(value, (list, tuple)):
            collected.extend(value)
            return
        if collect_mode == "merge" and isinstance(value, dict):
            if not collected or not isinstance(collected[-1], dict):
                collected.append({})
            collected[-1].update(value)
            return
        collected.append(value)

    async def _execute_try_catch_node(
        self,
        *,
        ctx: ExecutionContext,
        node: dict[str, Any],
        inputs: dict[str, Any],
        all_nodes: dict[str, dict[str, Any]],
        edges: list[dict[str, Any]],
        branch_node_ids: dict[str, set[str]],
        node_outputs: dict[str, dict[str, Any]],
        options: dict[str, Any],
        workflow: dict[str, Any],
        emit: Callable[[str, dict[str, Any]], None],
    ) -> dict[str, Any]:
        """Execute a Try/Catch control node and its internal branch subgraphs."""
        initial = await self._execute_node(ctx, node, inputs)
        try_value = initial.get("outputs", {}).get("try")
        retry_count = 0

        while True:
            try:
                try_result = await self._execute_try_catch_branch(
                    ctx=ctx,
                    control_node=node,
                    branch_name="try",
                    branch_value=try_value,
                    return_port="_try_result",
                    body_node_ids=branch_node_ids.get("try", set()),
                    all_nodes=all_nodes,
                    edges=edges,
                    node_outputs=node_outputs,
                    options=options,
                    workflow=workflow,
                    emit=emit,
                    branch_run_id=f"try-{retry_count + 1}",
                )
                phase = await self._execute_try_catch_phase(
                    ctx,
                    node,
                    inputs,
                    phase="try_result",
                    try_result=try_result,
                    try_error="",
                    retry_count=retry_count,
                )
                return phase
            except Exception as exc:
                try_error = str(exc)
                phase = await self._execute_try_catch_phase(
                    ctx,
                    node,
                    inputs,
                    phase="try_result",
                    try_result=None,
                    try_error=try_error,
                    retry_count=retry_count,
                )
                flow_phase = phase.get("flow_control", {}).get("phase")
                outputs = phase.get("outputs", {})

                if flow_phase == "retrying":
                    retry_count = int(outputs.get("retry_count", retry_count + 1) or 0)
                    try_value = outputs.get("try")
                    continue

                if flow_phase == "catching":
                    catch_result = await self._execute_try_catch_branch(
                        ctx=ctx,
                        control_node=node,
                        branch_name="catch",
                        branch_value=outputs.get("catch"),
                        return_port="_catch_result",
                        body_node_ids=branch_node_ids.get("catch", set()),
                        all_nodes=all_nodes,
                        edges=edges,
                        node_outputs=node_outputs,
                        options=options,
                        workflow=workflow,
                        emit=emit,
                        branch_run_id="catch",
                    )
                    return await self._execute_try_catch_phase(
                        ctx,
                        node,
                        inputs,
                        phase="catch_result",
                        try_result=None,
                        try_error=str(outputs.get("error_info", try_error) or try_error),
                        catch_result=catch_result,
                        retry_count=int(outputs.get("retry_count", retry_count) or 0),
                    )

                raise RuntimeError(str(outputs.get("error_info", try_error) or try_error))

    async def _execute_try_catch_phase(
        self,
        ctx: ExecutionContext,
        node: dict[str, Any],
        inputs: dict[str, Any],
        *,
        phase: str,
        try_result: Any = None,
        try_error: str = "",
        catch_result: Any = None,
        retry_count: int = 0,
    ) -> dict[str, Any]:
        params = {
            **ctx.params,
            "_phase": phase,
            "_try_result": try_result,
            "_try_error": try_error,
            "_catch_result": catch_result,
            "_retry_count": retry_count,
        }
        return await self._execute_node(replace(ctx, params=params), node, inputs)

    async def _execute_try_catch_branch(
        self,
        *,
        ctx: ExecutionContext,
        control_node: dict[str, Any],
        branch_name: str,
        branch_value: Any,
        return_port: str,
        body_node_ids: set[str],
        all_nodes: dict[str, dict[str, Any]],
        edges: list[dict[str, Any]],
        node_outputs: dict[str, dict[str, Any]],
        options: dict[str, Any],
        workflow: dict[str, Any],
        emit: Callable[[str, dict[str, Any]], None],
        branch_run_id: str,
    ) -> Any:
        if not body_node_ids:
            return branch_value

        body_nodes = {node_id: all_nodes[node_id] for node_id in body_node_ids if node_id in all_nodes}
        body_edge_map = self._try_catch_branch_edge_map(ctx.node_id, branch_name, body_node_ids, edges)
        body_order = self._try_catch_branch_order(body_nodes, edges)
        local_outputs: dict[str, dict[str, Any]] = {
            ctx.node_id: {branch_name: branch_value},
        }
        local_inactive_outputs: dict[str, set[str]] = {}
        local_skipped_nodes: set[str] = set()

        for body_node_id in body_order:
            body_node = body_nodes[body_node_id]
            body_type = str(body_node.get("type", "unknown"))
            body_class = self._node_class_for(body_node)
            emit(
                "node_start",
                {
                    "run_id": ctx.run_id,
                    "node_id": body_node_id,
                    "node_type": body_type,
                    "try_catch_parent": ctx.node_id,
                    "branch": branch_name,
                },
            )

            inactive_upstream = self._inactive_upstream(
                body_node_id,
                body_edge_map,
                local_skipped_nodes,
                local_inactive_outputs,
                body_class,
            )
            if inactive_upstream is not None:
                local_skipped_nodes.add(body_node_id)
                emit(
                    "node_skip",
                    {
                        "run_id": ctx.run_id,
                        "node_id": body_node_id,
                        "reason": "inactive_branch",
                        "upstream": inactive_upstream,
                        "try_catch_parent": ctx.node_id,
                        "branch": branch_name,
                    },
                )
                continue

            combined_outputs = {**node_outputs, **local_outputs}
            body_inputs = self._resolve_inputs(
                body_node_id,
                body_node,
                body_edge_map,
                combined_outputs,
                ctx.run_metadata.get("workflow_parameters", {}),
            )
            body_params = self._with_defaults(
                body_node,
                body_inputs,
                body_class,
                ctx.run_metadata.get("workflow_parameters", {}),
            )
            body_dir = (
                self.workspace_dir
                / "runs"
                / ctx.run_id
                / ctx.node_id
                / "try_catch"
                / branch_run_id
                / body_node_id
            )
            body_dir.mkdir(parents=True, exist_ok=True)
            body_ctx = ExecutionContext(
                run_id=ctx.run_id,
                node_id=body_node_id,
                node_type=body_type,
                node_dir=body_dir,
                workspace_dir=self.workspace_dir,
                params=body_params,
                api_secrets=self._api_secrets_for_options(options),
                emit=emit,
                cancel_event=ctx.cancel_event,
                env_prefix=self._env_prefix_for_node(body_node, workflow),
                run_metadata=ctx.run_metadata,
                executor=ctx.executor or self,
                registry=ctx.registry if ctx.registry is not None else self.registry,
                hpc_backend=ctx.hpc_backend,
            )
            body_result = await self._execute_node(body_ctx, body_node, body_inputs)
            outputs = body_result.get("outputs", {})
            inactive_outputs = self._inactive_output_ports(
                body_result,
                outputs,
                body_class,
            )
            if inactive_outputs:
                local_inactive_outputs[body_node_id] = inactive_outputs
            local_outputs[body_node_id] = outputs
            emit(
                "node_complete",
                {
                    "run_id": ctx.run_id,
                    "node_id": body_node_id,
                    "outputs": outputs,
                    "try_catch_parent": ctx.node_id,
                    "branch": branch_name,
                },
            )

        return self._try_catch_branch_result(ctx.node_id, return_port, edges, local_outputs, body_order)

    def _try_catch_branch_edge_map(
        self,
        control_node_id: str,
        branch_port: str,
        body_node_ids: set[str],
        edges: list[dict[str, Any]],
    ) -> dict[str, list[dict[str, Any]]]:
        edge_map: dict[str, list[dict[str, Any]]] = {node_id: [] for node_id in body_node_ids}
        for edge in edges:
            target = edge_target(edge)
            if target not in body_node_ids:
                continue
            source = edge_source(edge)
            if source == control_node_id:
                if edge_source_port(edge) == branch_port:
                    edge_map[target].append(edge)
                continue
            edge_map[target].append(edge)
        return edge_map

    def _try_catch_branch_order(
        self,
        body_nodes: dict[str, dict[str, Any]],
        edges: list[dict[str, Any]],
    ) -> list[str]:
        upstream_of: dict[str, list[str]] = {node_id: [] for node_id in body_nodes}
        downstream_of: dict[str, list[str]] = {node_id: [] for node_id in body_nodes}
        for edge in edges:
            source = edge_source(edge)
            target = edge_target(edge)
            if source in body_nodes and target in body_nodes:
                upstream_of[target].append(source)
                downstream_of[source].append(target)
        return self._topological_sort(body_nodes, upstream_of, downstream_of)

    def _try_catch_branch_result(
        self,
        control_node_id: str,
        return_port: str,
        edges: list[dict[str, Any]],
        local_outputs: dict[str, dict[str, Any]],
        body_order: list[str],
    ) -> Any:
        values: list[Any] = []
        for edge in edges:
            if edge_target(edge) != control_node_id or edge_target_port(edge) != return_port:
                continue
            source = edge_source(edge)
            source_port = edge_source_port(edge)
            outputs = local_outputs.get(source, {})
            if source_port in outputs:
                values.append(outputs[source_port])
            elif "default" in outputs:
                values.append(outputs["default"])
        if len(values) == 1:
            return values[0]
        if values:
            return values
        if not body_order:
            return None
        outputs = local_outputs.get(body_order[-1], {})
        if len(outputs) == 1:
            return next(iter(outputs.values()))
        return outputs

    @staticmethod
    def _is_subgraph_node(node: dict[str, Any]) -> bool:
        return isinstance(node, dict) and str(node.get("type", "")) == "subgraph"

    @staticmethod
    def _subgraph_ports(raw: Any) -> list[dict[str, str]]:
        """Normalize ``params.input_ports``/``output_ports`` entries."""
        ports: list[dict[str, str]] = []
        if not isinstance(raw, (list, tuple)):
            return ports
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            name = str(entry.get("name", "") or "")
            if not name:
                continue
            inner_node_id = str(
                entry.get("innerNodeId", entry.get("inner_node_id", "")) or ""
            )
            inner_slot = str(entry.get("innerSlot", entry.get("inner_slot", "")) or "")
            ports.append(
                {
                    "name": name,
                    "inner_node_id": inner_node_id,
                    "inner_slot": inner_slot,
                }
            )
        return ports

    @staticmethod
    def _subgraph_seed(workflow_parameters: dict[str, Any], subgraph_node_id: str) -> int:
        """Derive a stable per-subgraph seed from the run's master seed."""
        master_seed = workflow_parameters.get("seed") if isinstance(workflow_parameters, dict) else None
        if master_seed is None and isinstance(workflow_parameters, dict):
            master_seed = workflow_parameters.get("master_seed")
        material = "" if master_seed is None else str(master_seed)
        digest = hashlib.sha256(f"{material}:{subgraph_node_id}".encode("utf-8")).hexdigest()
        # Mask to 31 bits: full 8-hex-digit digests exceed the INT max
        # (2147483647) that node input validation enforces on seed inputs.
        return int(digest[:8], 16) & 0x7FFFFFFF

    async def _execute_subgraph_node(
        self,
        ctx: ExecutionContext,
        node: dict[str, Any],
        inputs: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a subgraph node's embedded workflow inside the same run.

        The inner execution reuses this executor (same run_id, cache,
        cancel_event) with a recursion context: its artifacts root at the
        subgraph node's own directory, its events are tagged with the nested
        ``subgraph_path``, and the parent's resolved port inputs are mapped
        onto the inner nodes via ``input_overrides``.
        """
        raw_params = node.get("params")
        params = raw_params if isinstance(raw_params, dict) else {}
        inner_workflow = params.get("workflow")
        if not isinstance(inner_workflow, dict) or not inner_workflow.get("nodes"):
            raise RuntimeError(f"Subgraph node '{ctx.node_id}' is missing its embedded workflow")

        input_ports = self._subgraph_ports(params.get("input_ports"))
        output_ports = self._subgraph_ports(params.get("output_ports"))
        workflow_parameters = ctx.run_metadata.get("workflow_parameters")
        if not isinstance(workflow_parameters, dict):
            workflow_parameters = {}
        inner_seed = self._subgraph_seed(workflow_parameters, ctx.node_id)

        input_overrides: dict[str, dict[str, Any]] = {}
        for port in input_ports:
            if not port["inner_node_id"] or not port["inner_slot"]:
                continue
            if port["name"] in inputs:
                value = inputs[port["name"]]
                if port["name"] == "seed" and (value is None or value == ""):
                    value = inner_seed
            elif port["name"] == "seed":
                value = inner_seed
            else:
                continue
            input_overrides.setdefault(port["inner_node_id"], {})[port["inner_slot"]] = value

        parent_path = str(ctx.run_metadata.get("subgraph_path", "") or "")
        child_path = f"{parent_path}.{ctx.node_id}" if parent_path else ctx.node_id

        parent_options = ctx.run_metadata.get("execution_options")
        parent_options = parent_options if isinstance(parent_options, dict) else {}

        def _inner_emit(event: str, data: dict[str, Any]) -> None:
            # Inner node events flow to the same stream as the parent run's,
            # tagged with the nesting path; the inner run's own start/complete
            # bookkeeping stays internal so consumers tracking run-level state
            # see exactly one of each from the outermost execution. Events
            # already tagged by a deeper subgraph keep their deeper path.
            if event in ("start", "complete"):
                return
            if "subgraph_path" in data:
                ctx.emit(event, data)
            else:
                ctx.emit(event, {**data, "subgraph_path": child_path})

        inner_result = await self.execute(
            run_id=ctx.run_id,
            workflow=copy.deepcopy(inner_workflow),
            force=bool(parent_options.get("force", False)),
            options={
                "api_secrets": dict(ctx.api_secrets),
                "parameters": {"subgraph_seed": inner_seed},
                "stop_on_error": bool(parent_options.get("stop_on_error", True)),
                "embed_provenance": bool(parent_options.get("embed_provenance", True)),
            },
            cancel_event=ctx.cancel_event,
            emit=_inner_emit,
            input_overrides=input_overrides,
            _run_dir=ctx.node_dir,
            _subgraph_path=child_path,
        )

        inner_status = str(inner_result.get("status", ""))
        if inner_status == "cancelled":
            ctx.cancel_event.set()
            raise CommandCancelledError(f"subgraph:{ctx.node_id}")
        inner_node_results = inner_result.get("node_results", {})
        if inner_status != "completed":
            failures = [
                f"{node_id}: {result.get('error', result.get('status'))}"
                for node_id, result in inner_node_results.items()
                if isinstance(result, dict) and result.get("status") == "failed"
            ]
            detail = str(inner_result.get("error") or "; ".join(failures) or inner_status)
            raise RuntimeError(f"Subgraph '{ctx.node_id}' failed: {detail[:500]}")

        outputs: dict[str, Any] = {}
        for port in output_ports:
            node_result = inner_node_results.get(port["inner_node_id"], {})
            port_outputs = node_result.get("outputs", {}) if isinstance(node_result, dict) else {}
            if port["inner_slot"] in port_outputs:
                outputs[port["name"]] = port_outputs[port["inner_slot"]]
            else:
                outputs[port["name"]] = port_outputs.get("default")
        outputs["subgraph_dir"] = str(ctx.node_dir.resolve())

        return {
            "outputs": outputs,
            "subgraph": {
                "status": inner_status,
                "subgraph_path": child_path,
                "seed": inner_seed,
                "node_count": len(inner_node_results),
            },
        }

    async def _execute_node(
        self,
        ctx: ExecutionContext,
        node: dict[str, Any],
        inputs: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a single node via its ``run()`` method."""
        if self._is_subgraph_node(node):
            return await self._execute_subgraph_node(ctx, node, inputs)
        node_class = node.get("_node_class")
        # Fallback: look up in registry if _node_class is not attached
        if node_class is None and self.registry is not None and hasattr(self.registry, "get"):
            node_class = self.registry.get(node.get("type", "unknown"))
        if node_class is not None and hasattr(node_class, "run"):
            kwargs = {**inputs, **ctx.params}
            hidden_inputs = self._declared_hidden_inputs(node_class)
            kwargs = {
                k: v
                for k, v in kwargs.items()
                if not str(k).startswith("_") or k in hidden_inputs
            }
            kwargs = self._resolve_file_paths(node_class, kwargs)
            node_instance = node_class()
            if asyncio.iscoroutinefunction(node_class.run):
                raw = await node_instance.run(context=ctx, **kwargs)
            else:
                # Run synchronous (often CPU- or IO-bound) node bodies off the
                # event loop so a single blocking node cannot stall the server,
                # the queue, or sibling nodes running concurrently.
                raw = await asyncio.to_thread(node_instance.run, context=ctx, **kwargs)
            return self._normalize_result(raw, node_class)

        raise RuntimeError(
            f"Node class not found for '{node.get('type', 'unknown')}'. "
            "Ensure the node is registered in the node registry."
        )

    @staticmethod
    def _declared_hidden_inputs(node_class: Any) -> set[str]:
        if node_class is None or not hasattr(node_class, "INPUT_TYPES"):
            return set()
        try:
            input_types = node_class.INPUT_TYPES()
        except Exception:
            return set()
        hidden = input_types.get("hidden", {})
        return {str(name) for name in hidden}

    async def _execute_node_with_retry(
        self,
        *,
        ctx: ExecutionContext,
        node: dict[str, Any],
        inputs: dict[str, Any],
        upstream_nodes: set[str],
        emit: Callable[[str, dict[str, Any]], None],
    ) -> dict[str, Any]:
        """Execute a node and apply the nearest applicable retry policy."""
        policy = self._retry_policy_for_node(ctx.node_id, upstream_nodes, ctx.run_metadata)
        max_retries = max(0, int(policy.get("max_retries", 0) or 0)) if policy else 0
        max_attempts = max_retries + 1
        attempts = 0
        last_exc: Exception | None = None

        while attempts < max_attempts:
            attempts += 1
            try:
                result = await self._execute_node(ctx, node, inputs)
                result["attempts"] = attempts
                return result
            except Exception as exc:
                last_exc = exc
                if attempts >= max_attempts or not self._retry_matches_exception(policy, exc):
                    setattr(exc, "attempts", attempts)
                    raise
                next_attempt = attempts + 1
                emit(
                    "node_retry",
                    {
                        "run_id": ctx.run_id,
                        "node_id": ctx.node_id,
                        "attempt": next_attempt,
                        "max_attempts": max_attempts,
                    },
                )
                self._record_run_event(
                    ctx.run_id,
                    "node_retry",
                    self._tag_subgraph_path(
                        ctx.run_metadata,
                        {
                            "node_id": ctx.node_id,
                            "attempt": next_attempt,
                            "max_attempts": max_attempts,
                            "error_code": self._error_code(exc),
                        },
                    ),
                )
                if isinstance(exc, NodeMemoryError):
                    self._apply_memory_escalation(ctx, policy, next_attempt, emit)
                delay = self._retry_delay(policy, attempts)
                if delay > 0:
                    await asyncio.sleep(delay)

        if last_exc is not None:
            setattr(last_exc, "attempts", attempts)
            raise last_exc
        raise RuntimeError(f"Retry execution failed for {ctx.node_id}")

    def _apply_memory_escalation(
        self,
        ctx: ExecutionContext,
        policy: dict[str, Any] | None,
        attempt: int,
        emit: Callable[[str, dict[str, Any]], None],
    ) -> None:
        """Record (and where possible apply) a memory escalation on OOM retry.

        The multiplier is only honoured where the engine can actually deliver
        it today: nodes exposing a ``memory`` directive parameter (the
        ``hpc_submit_job`` family feeds it straight into the scheduler's mem
        directive, so the resubmission carries the bumped value). Nodes without
        such a parameter record the escalation intent only — no fake bumps.
        """
        escalate = policy.get("escalate") if isinstance(policy, dict) else None
        multiplier = 1.0
        if isinstance(escalate, dict):
            try:
                multiplier = max(1.0, float(escalate.get("memory_multiplier", 1.0) or 1.0))
            except (TypeError, ValueError):
                multiplier = 1.0
        elif escalate is None:
            return
        applied = False
        bumped = ""
        current = ctx.params.get("memory")
        if multiplier > 1.0 and isinstance(current, str) and current:
            bumped = self._bump_memory_directive(current, multiplier)
            if bumped and bumped != current:
                ctx.params["memory"] = bumped
                applied = True
        record = {
            "node_id": ctx.node_id,
            "attempt": attempt,
            "memory_multiplier": multiplier,
            "applied": applied,
        }
        if applied:
            record["memory"] = bumped
        ctx.run_metadata.setdefault("escalations", []).append(record)
        emit("node_escalate", {"run_id": ctx.run_id, **record})
        self._record_run_event(ctx.run_id, "node_escalate", self._tag_subgraph_path(ctx.run_metadata, record))

    @staticmethod
    def _bump_memory_directive(value: str, multiplier: float) -> str:
        """Scale a scheduler memory directive (``"32G"``, ``"512M"``, ``"16000"``)."""
        match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*([KMGTP]?)(?:i?B)?\s*", value, re.IGNORECASE)
        if match is None:
            return value
        amount = float(match.group(1))
        unit = match.group(2).upper()
        scaled = max(1, int(round(amount * multiplier)))
        return f"{scaled}{unit or ''}"

    @staticmethod
    def _error_code(exc: Exception) -> str:
        return getattr(exc, "code", "") or ""

    def _retry_policy_for_node(
        self,
        node_id: str,
        upstream_nodes: set[str],
        run_metadata: dict[str, Any],
    ) -> dict[str, Any] | None:
        policies = run_metadata.get("retry_policies", [])
        if not isinstance(policies, list):
            return None
        for policy in reversed(policies):
            if not isinstance(policy, dict):
                continue
            policy_node_id = str(policy.get("node_id", ""))
            if policy_node_id not in upstream_nodes:
                continue
            target_nodes = self._coerce_node_id_set(policy.get("target_nodes", []))
            if target_nodes and node_id not in target_nodes:
                continue
            return policy
        return None

    @staticmethod
    def _retry_matches_exception(policy: dict[str, Any] | None, exc: Exception) -> bool:
        if not policy:
            return False
        retry_on = str(policy.get("retry_on", "all") or "all").lower()
        if retry_on == "all":
            return True
        # Typed dispatch first: the taxonomy carries the failure class. Memory
        # is checked before exit code because OOM failures surface as non-zero
        # exits too and the memory diagnosis is the more specific match.
        if isinstance(exc, NodeMemoryError):
            return retry_on == "memory"
        if isinstance(exc, NodeTimeoutError):
            return retry_on == "timeout"
        if isinstance(exc, NodeExitCodeError):
            return retry_on == "exit_code"
        # Fallback for third-party node errors raising generic exceptions.
        message = str(exc).lower()
        if retry_on == "timeout":
            return isinstance(exc, TimeoutError) or "timeout" in message or "timed out" in message
        if retry_on == "memory":
            return "memory" in message or "oom" in message
        if retry_on == "exit_code":
            return "exit code" in message or "returncode" in message or "returned non-zero" in message
        return False

    @staticmethod
    def _retry_delay(policy: dict[str, Any] | None, completed_attempts: int) -> float:
        if not policy:
            return 0.0
        delays = policy.get("delays_seconds")
        if isinstance(delays, list) and completed_attempts - 1 < len(delays):
            return max(0.0, float(delays[completed_attempts - 1] or 0.0))
        delay_seconds = max(0.0, float(policy.get("delay_seconds", 0.0) or 0.0))
        backoff_multiplier = max(1.0, float(policy.get("backoff_multiplier", 1.0) or 1.0))
        max_delay = max(0.0, float(policy.get("max_delay", delay_seconds) or delay_seconds))
        delay = delay_seconds * (backoff_multiplier ** max(0, completed_attempts - 1))
        return min(delay, max_delay) if max_delay > 0 else delay

    def _normalize_result(
        self,
        raw: Any,
        node_class: Any,
    ) -> dict[str, Any]:
        """Normalize node return value to dict format expected by the executor."""
        if isinstance(raw, dict):
            outputs = raw.get("outputs")
            if not isinstance(outputs, dict):
                raise ValueError("Node result dict must return an 'outputs' mapping")
            return raw
        if isinstance(raw, tuple):
            return_names = getattr(node_class, "RETURN_NAMES", ()) or ()
            outputs: dict[str, Any] = {}
            for idx, val in enumerate(raw):
                name = return_names[idx] if idx < len(return_names) else f"output_{idx}"
                outputs[name] = val
            return {"outputs": outputs}
        if raw is None:
            raise ValueError("Node did not return outputs")
        # Single scalar value
        return_names = getattr(node_class, "RETURN_NAMES", ()) or ()
        name = return_names[0] if return_names else "default"
        return {"outputs": {name: raw}}

    @staticmethod
    def _inline_output_validation_rules(node: dict[str, Any]) -> dict[str, dict[str, Any]]:
        ui = node.get("ui")
        if not isinstance(ui, dict):
            return {}
        validation = ui.get("validation")
        if not isinstance(validation, dict):
            return {}
        outputs = validation.get("outputs")
        if not isinstance(outputs, dict):
            return {}
        rules: dict[str, dict[str, Any]] = {}
        for output_name, raw_rule in outputs.items():
            if not isinstance(raw_rule, dict):
                continue
            if raw_rule.get("enabled") is False:
                continue
            rules[str(output_name)] = dict(raw_rule)
        return rules

    async def _apply_inline_output_validations(
        self,
        *,
        ctx: ExecutionContext,
        node: dict[str, Any],
        outputs: dict[str, Any],
    ) -> dict[str, Any]:
        rules = self._inline_output_validation_rules(node)
        if not rules:
            return outputs

        try:
            from bionodulo.nodes.builtin.workflow_enhancement import DataValidatorNode
        except Exception as exc:  # pragma: no cover - import failure is environment-specific
            raise RuntimeError(f"Inline validation could not load Data Validator: {exc}") from exc

        validator = DataValidatorNode()
        validation_records = ctx.run_metadata.setdefault("inline_validations", [])
        for output_name, rule in rules.items():
            if output_name not in outputs:
                raise RuntimeError(f"Inline validation output '{output_name}' not found for node '{ctx.node_id}'")
            validator_kwargs = dict(rule)
            validator_kwargs.pop("enabled", None)
            validator_kwargs["input"] = outputs[output_name]
            validator_kwargs.setdefault("fail_on_error", True)
            _, passed, report, report_file, _ = await validator.run(context=ctx, **validator_kwargs)
            validation_records.append(
                {
                    "node_id": ctx.node_id,
                    "output": output_name,
                    "passed": bool(passed),
                    "report": report,
                    "report_file": report_file,
                }
            )
        return outputs

    def _topological_sort(
        self,
        nodes: dict[str, dict[str, Any]],
        upstream_of: dict[str, list[str]],
        downstream_of: dict[str, list[str]],
    ) -> list[str]:
        """Return node IDs in topological order (Kahn's algorithm)."""
        in_degree = {nid: len(upstream_of[nid]) for nid in nodes}
        queue = deque(nid for nid, deg in in_degree.items() if deg == 0)
        order: list[str] = []

        while queue:
            nid = queue.popleft()
            order.append(nid)
            for downstream in downstream_of.get(nid, []):
                in_degree[downstream] -= 1
                if in_degree[downstream] == 0:
                    queue.append(downstream)

        if len(order) != len(nodes):
            remaining = [nid for nid in nodes if nid not in order]
            raise ValueError(f"Cycle detected involving nodes: {remaining}")

        return order

    def _resolve_inputs(
        self,
        node_id: str,
        node: dict[str, Any],
        edge_map: dict[str, list[dict[str, Any]]],
        node_outputs: dict[str, dict[str, str]],
        workflow_parameters: dict[str, Any] | None = None,
        input_overrides: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Resolve edge connections to actual values from upstream outputs."""
        inputs: dict[str, Any] = {}
        node_def_inputs = node.get("inputs", {})
        workflow_parameters = workflow_parameters or {}

        # Start with literal/default values from node definition
        for inp_name, inp_val in node_def_inputs.items():
            if isinstance(inp_val, dict) and "value" in inp_val:
                inputs[inp_name] = self._bind_workflow_parameters(inp_val["value"], workflow_parameters)
            else:
                inputs[inp_name] = self._bind_workflow_parameters(inp_val, workflow_parameters)

        # Fallback: use params if no inputs defined (frontend/template format)
        if not inputs:
            for pname, pval in node.get("params", {}).items():
                inputs[pname] = self._bind_workflow_parameters(pval, workflow_parameters)

        # Override with upstream connections.
        #
        # Multiple edges may target the SAME input port (fan-in), e.g. several
        # QC nodes feeding MultiQC's `reports`. For a LIST-typed port that
        # receives 2+ edges we ACCUMULATE the upstream values into a flat list;
        # the previous code did `inputs[tgt_port] = value` unconditionally, so
        # the last edge silently overwrote the rest (MultiQC then received only
        # one report and produced "No analysis results found"). A port with a
        # single edge is assigned its value directly — unchanged behaviour, so
        # this only affects genuine fan-in and can't perturb existing runs.
        list_ports = self._list_input_ports(node)
        edge_count: dict[str, int] = {}
        for edge in edge_map.get(node_id, []):
            edge_count[edge_target_port(edge)] = edge_count.get(edge_target_port(edge), 0) + 1
        collected_list: dict[str, list[Any]] = {}
        for edge in edge_map.get(node_id, []):
            src = edge_source(edge)
            src_port = edge_source_port(edge)
            tgt_port = edge_target_port(edge)

            if src in node_outputs:
                upstream_out = node_outputs[src]
                if src_port in upstream_out:
                    value = upstream_out[src_port]
                elif "default" in upstream_out:
                    value = upstream_out["default"]
                else:
                    continue
                if tgt_port in list_ports and edge_count.get(tgt_port, 0) > 1:
                    bucket = collected_list.setdefault(tgt_port, [])
                    if isinstance(value, (list, tuple)):
                        bucket.extend(value)
                    else:
                        bucket.append(value)
                else:
                    inputs[tgt_port] = value

        for port, values in collected_list.items():
            inputs[port] = values

        # Explicit per-node overrides win over everything resolved above
        # (used to map a subgraph's parent inputs onto its inner nodes).
        if input_overrides:
            node_overrides = input_overrides.get(node_id)
            if node_overrides:
                inputs.update(node_overrides)

        return inputs

    def _list_input_ports(self, node: dict[str, Any]) -> set[str]:
        """Names of this node's inputs whose declared type is a LIST type.

        Read from the node class's INPUT_TYPES via the registry; a port counts
        as a list when its type token contains 'LIST' (e.g. FILE_LIST,
        FASTQ_LIST) or its input metadata declares ``multiple=True``. The latter
        keeps the artifact type exact (for example FILE -> FILE) while still
        preserving all fan-in values. Returns an empty set when the
        class/registry is unavailable so behaviour is unchanged for unknown
        nodes.
        """
        node_class = self._node_class_for(node)
        if node_class is None or not hasattr(node_class, "INPUT_TYPES"):
            return set()
        try:
            spec = node_class.INPUT_TYPES()
        except Exception:
            return set()
        ports: set[str] = set()
        for section in ("required", "optional"):
            for name, decl in (spec.get(section, {}) or {}).items():
                type_token = decl[0] if isinstance(decl, (list, tuple)) and decl else decl
                config = (
                    decl[1]
                    if isinstance(decl, (list, tuple))
                    and len(decl) > 1
                    and isinstance(decl[1], dict)
                    else {}
                )
                if (
                    isinstance(type_token, str)
                    and "LIST" in type_token.upper()
                ) or config.get("multiple") is True:
                    ports.add(name)
        return ports

    def _auto_scale_threads(self, params: dict[str, Any]) -> dict[str, Any]:
        """Universal thread auto-scaling: bump node ``threads`` params to use
        available cores when the user hasn't explicitly set a higher value.

        Bioinformatics tools (samtools, bwa, minimap2, seqkit, etc.) expose a
        ``threads`` parameter that defaults to a conservative 1-4. On a
        16-vCPU cloud VM that means 75%+ of paid compute sits idle. This hook
        detects the machine's vCPU count and raises any ``threads`` param that
        is below it — but only when the user hasn't explicitly tuned it up.

        Rules:
          - Only scales up (never reduces a user's explicit higher setting)
          - Respects ``BIONODULO_MAX_THREADS`` env cap (the dispatch sets this
            to the provisioned VM's vCPU count)
          - Leaves ``threads=1`` alone only when the node genuinely requires
            serial execution (detected via ``serial_only`` in the param config)
          - Works on ANY workflow — the presence of a ``threads`` param is the
            trigger; no workflow-specific knowledge required.
        """
        if "threads" not in params:
            return params

        # Respect explicit env override
        max_threads_env = os.environ.get("BIONODULO_MAX_THREADS", "").strip()
        if max_threads_env:
            try:
                cap = max(1, int(max_threads_env))
            except (TypeError, ValueError):
                cap = self._detected_vcpus()
        else:
            cap = self._detected_vcpus()

        try:
            current = int(params.get("threads", 1))
        except (TypeError, ValueError):
            return params

        if current >= cap:
            return params  # already using enough

        # Scale up to the cap
        params["threads"] = cap
        return params

    def _with_defaults(
        self,
        node: dict[str, Any],
        inputs: dict[str, Any],
        node_class: Any = None,
        workflow_parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Fill in default parameter values from node definition."""
        params: dict[str, Any] = {}
        workflow_parameters = workflow_parameters or {}
        # Widget values / parameters
        widgets = node.get("widgets", {})
        params.update(self._bind_workflow_parameters(widgets, workflow_parameters))
        # Fallback: params from frontend/template format
        for pname, pval in node.get("params", {}).items():
            if pname not in params:
                params[pname] = self._bind_workflow_parameters(pval, workflow_parameters)
        # Pull defaults from node class INPUT_TYPES if available
        if node_class is not None and hasattr(node_class, "INPUT_TYPES"):
            try:
                input_types = node_class.INPUT_TYPES()
                for section in ("required", "optional", "hidden"):
                    for name, spec in input_types.get(section, {}).items():
                        if name not in params and isinstance(spec, (list, tuple)) and len(spec) > 1:
                            config = spec[1]
                            if isinstance(config, dict) and "default" in config:
                                params[name] = config["default"]
            except Exception:
                pass
        # Override with resolved inputs
        params.update(inputs)
        # Add metadata
        params["_node_type"] = node.get("type", "unknown")
        params["_output_ports"] = list(node.get("outputs", {}).keys()) or ["default"]
        return params

    @staticmethod
    def _resolve_workflow_parameters(raw_parameters: Any, runtime_values: Any) -> dict[str, Any]:
        """Resolve workflow parameter definitions plus runtime overrides."""
        if raw_parameters in (None, {}):
            raw_parameters = []
        if runtime_values in (None, ""):
            runtime_values = {}
        if not isinstance(raw_parameters, list):
            raise ValueError("Workflow parameters must be a list")
        if not isinstance(runtime_values, dict):
            raise ValueError("Runtime workflow parameters must be an object")

        resolved: dict[str, Any] = {}
        missing_required: list[str] = []
        for index, parameter in enumerate(raw_parameters):
            if hasattr(parameter, "model_dump"):
                parameter = parameter.model_dump()
            if not isinstance(parameter, dict):
                raise ValueError(f"Workflow parameter at index {index} must be an object")
            name = str(parameter.get("name", "") or "").strip()
            if not name:
                raise ValueError(f"Workflow parameter at index {index} must have a non-empty name")

            if name in runtime_values:
                value = runtime_values[name]
            elif parameter.get("value") is not None:
                value = parameter.get("value")
            elif parameter.get("default") is not None:
                value = parameter.get("default")
            else:
                value = None

            if value is None and bool(parameter.get("required", False)):
                missing_required.append(name)
            elif value is not None:
                resolved[name] = value

        for name, value in runtime_values.items():
            key = str(name).strip()
            if key and key not in resolved:
                resolved[key] = value

        if missing_required:
            if len(missing_required) == 1:
                raise ValueError(f"Missing required workflow parameter: {missing_required[0]}")
            raise ValueError(f"Missing required workflow parameters: {', '.join(missing_required)}")
        return resolved

    @classmethod
    def _bind_workflow_parameters(cls, value: Any, parameters: dict[str, Any]) -> Any:
        """Recursively replace ``{{name}}`` workflow parameter placeholders."""
        if not parameters:
            return value
        if isinstance(value, dict):
            return {
                key: cls._bind_workflow_parameters(item, parameters)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [cls._bind_workflow_parameters(item, parameters) for item in value]
        if not isinstance(value, str):
            return value

        exact = re.fullmatch(r"\{\{\s*([A-Za-z_][A-Za-z0-9_.-]*)\s*\}\}", value)
        if exact:
            name = exact.group(1)
            if name not in parameters:
                return value
            return parameters[name]

        def replace(match: re.Match[str]) -> str:
            name = match.group(1)
            if name not in parameters:
                return match.group(0)
            return str(parameters[name])

        return re.sub(r"\{\{\s*([A-Za-z_][A-Za-z0-9_.-]*)\s*\}\}", replace, value)

    def _bypass_outputs(
        self,
        node_id: str,
        node: dict[str, Any],
        edge_map: dict[str, list[dict[str, Any]]],
    ) -> dict[str, str]:
        """Compute bypassed node outputs by passing inputs through."""
        outputs: dict[str, str] = {}
        node_outputs_def = node.get("outputs", {})
        node_inputs = node.get("inputs", {})

        # For simple passthrough, map each output to the first input value
        input_values = [
            v["value"] if isinstance(v, dict) and "value" in v else v
            for v in node_inputs.values()
        ]
        input_values = [v for v in input_values if isinstance(v, str)]

        for out_name in node_outputs_def:
            if input_values:
                outputs[out_name] = input_values[0]
            else:
                outputs[out_name] = ""

        return outputs

    def _collect_previews(
        self,
        ctx: ExecutionContext,
        result: dict[str, Any],
        node_class: type[Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Collect previewable output files (HTML, images, JSON, etc.).

        In addition to natively-previewable outputs and any preview a node
        registered itself, generate a small truncated HEAD preview for the
        node's primary output when it has no visual preview yet — so every
        node (FASTA, VCF, GFF, logs, BAM, …) shows something on the canvas.
        """
        if not self._automatic_previews_enabled(node_class):
            return list(ctx._previews)

        previews: list[dict[str, Any]] = []

        for port, path in result.get("outputs", {}).items():
            paths = path if isinstance(path, (list, tuple)) else [path]
            for p_str in paths:
                if not isinstance(p_str, (str, Path)):
                    continue
                p = Path(p_str)
                if self._path_exists(p) and p.suffix.lower() in PREVIEWABLE_EXTENSIONS:
                    previews.append(
                        {
                            "path": str(p),
                            "label": f"{ctx.node_id}/{port}",
                            "node_id": ctx.node_id,
                        }
                    )

        all_previews = previews + ctx._previews
        head_preview = self._maybe_head_preview(ctx, result, all_previews)
        if head_preview is not None:
            all_previews.append(head_preview)
        return all_previews

    @staticmethod
    def _automatic_previews_enabled(node_class: type[Any] | None) -> bool:
        """Return whether outputs may use automatic single-file previews.

        Nodes with bundle-aware outputs can set ``AUTO_PREVIEW = False``.
        Explicit previews registered through the execution context survive.
        """
        return getattr(node_class, "AUTO_PREVIEW", True) is not False

    def _maybe_head_preview(
        self,
        ctx: ExecutionContext,
        result: dict[str, Any],
        existing_previews: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        """Generate a truncated HEAD preview for the node's primary output.

        Skips when the node already has a visual preview (an HTML/image/SVG
        entry, including ones a node registered itself), or when no suitable
        primary output exists. Never raises.
        """
        try:
            # Already has a visual preview? Don't override charts, reports,
            # images, table/text previews, etc.
            for prev in existing_previews:
                prev_path = Path(str(prev.get("path", "")))
                if prev_path.suffix.lower() not in head_preview_mod.SKIP_EXTENSIONS:
                    continue
                # An HTML/image/svg preview counts as a visual preview.
                if prev_path.suffix.lower() in {
                    ".html", ".htm", ".png", ".jpg", ".jpeg",
                    ".gif", ".svg", ".webp", ".bmp",
                }:
                    return None

            # Pick the primary output deterministically: first existing output
            # file (by output-port order) that isn't already natively previewed.
            primary: Path | None = None
            for _port, path in result.get("outputs", {}).items():
                paths = path if isinstance(path, (list, tuple)) else [path]
                for p_str in paths:
                    if not isinstance(p_str, (str, Path)):
                        continue
                    p = Path(p_str)
                    if not self._path_exists(p) or not p.is_file():
                        continue
                    if head_preview_mod.should_skip_extension(p):
                        continue
                    primary = p
                    break
                if primary is not None:
                    break

            if primary is None:
                return None

            out_dir = primary.parent / "_head_preview"
            html_path = head_preview_mod.write_head_preview(primary, out_dir)
            if html_path is None:
                return None
            return {
                "path": str(html_path),
                "label": f"{ctx.node_id} (head)",
                "node_id": ctx.node_id,
            }
        except Exception:  # noqa: BLE001 — a preview must never fail a run
            logger.exception("auto head preview failed for node %s", ctx.node_id)
            return None

    def _collect_artifacts(
        self,
        run_id: str,
        nodes: dict[str, dict[str, Any]],
        node_results: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Collect all output artifact file paths from the run."""
        artifacts: list[dict[str, Any]] = []
        for node_id, result in node_results.items():
            if result.get("status") not in ("completed", "cached", "bypassed"):
                continue
            outputs = result.get("outputs", {})
            for port, path in outputs.items():
                paths = path if isinstance(path, (list, tuple)) else [path]
                for p_str in paths:
                    if not isinstance(p_str, (str, Path)):
                        continue
                    p = Path(p_str)
                    if self._path_exists(p):
                        artifacts.append(
                            {
                                "node_id": node_id,
                                "node_type": nodes.get(node_id, {}).get("type", "unknown"),
                            "port": port,
                            "path": str(p),
                            "size": p.stat().st_size,
                        }
                    )
        return artifacts

    @staticmethod
    def _path_exists(path: Path) -> bool:
        try:
            return path.exists()
        except OSError:
            return False

    def _write_metadata(
        self,
        run_id: str,
        metadata: dict[str, Any],
        meta_dir: Path | None = None,
    ) -> None:
        """Write run metadata JSON to the workspace.

        ``meta_dir`` relocates the file for nested subgraph executions, whose
        metadata lands beside their artifacts under the subgraph node's run
        directory instead of the top-level run directory.
        """
        target_dir = meta_dir if meta_dir is not None else self.workspace_dir / "runs" / run_id
        target_dir.mkdir(parents=True, exist_ok=True)
        meta_path = target_dir / "run_metadata.json"
        with open(meta_path, "w", encoding="utf-8") as fh:
            json.dump(metadata, fh, indent=2, ensure_ascii=True, default=str)

    def _env_prefix_for_node(self, node: dict[str, Any], workflow: dict[str, Any] | None = None) -> list[str]:
        """Compute the environment command prefix for a node.

        Uses the workflow's content-addressed pixi manifest so that every
        workflow runs in an environment containing exactly the tools it needs.
        """
        node_type = node.get("type", "")
        node_class = node.get("_node_class")

        # If _node_class is not attached, try registry lookup
        if node_class is None and self.registry is not None and hasattr(self.registry, "get"):
            node_class = self.registry.get(node_type)

        # A named Pixi environment is resolved inside the same committed
        # workflow bundle.  Never fall back to ``pixi run -e`` from an ambient
        # cwd: that would permit a fresh solve and could select a different
        # lock than the one provisioned for this run.
        env_spec = getattr(node_class, "ENVIRONMENT", {}) if node_class else {}
        named_environment = None
        if isinstance(env_spec, dict) and env_spec.get("type") == "pixi":
            named_environment = str(env_spec.get("name", "")).strip() or None

        # Default: workflow-scoped manifest. Only use the pixi env when it is
        # actually installed — a failed/partial install leaves a pixi.toml behind,
        # and wrapping commands in `pixi run` against a non-ready env makes every
        # node re-trigger a doomed solve (which hangs or fails the whole run).
        # Falling back to system PATH lets a missing tool fail fast instead.
        if workflow is not None:
            environment_plan = workflow_to_environment_plan(workflow, self.registry)
            env_id = get_environment_plan_id(environment_plan)
            env_dir = get_env_dir(env_id, self.workspace_dir)
            manifest_path = env_dir / "pixi.toml"
            if manifest_path.exists() and is_env_ready(
                env_dir,
                environment_plan.environment_names,
            ):
                return self._command_prefix_list(
                    "pixi",
                    named_environment,
                    manifest_path=manifest_path,
                )

        # Fallback: system PATH
        return []

    def _command_prefix_list(
        self,
        env_type: str | None,
        env_name: str | None,
        manifest_path: Path | None = None,
    ) -> list[str]:
        """Generate environment command prefix as a token list."""
        # Resolve the actual executable path (system or managed)
        exe = env_type or "pixi"
        if exe == "pixi":
            from bionodulo.manager.runtime_installer import get_pixi_path
            pixi_path = get_pixi_path()
            if pixi_path is not None:
                exe = str(pixi_path)
            else:
                exe = "pixi"

        if env_type == "pixi" and manifest_path is not None:
            command = [exe, "run", "--locked", "--manifest-path", str(manifest_path)]
            if env_name:
                command.extend(["-e", env_name])
            command.append("--")
            return command
        if env_type == "pixi" and env_name:
            return [exe, "run", "--locked", "-e", env_name, "--"]
        return []
