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
import json
import logging
import traceback
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from bionodulo.environments.manifest import get_env_dir, get_env_id, workflow_to_packages
from bionodulo.execution.cache import CacheStore
from bionodulo.execution.subprocess_runner import run_subprocess
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

    async def run_command(
        self,
        cmd: str | list[str],
        cwd: str | Path | None = None,
        env: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Run a subprocess command within this execution context.

        If ``env_prefix`` is set, commands are wrapped for isolated execution.
        """
        stdout_path = self.node_dir / "stdout.log"
        stderr_path = self.node_dir / "stderr.log"

        # Wrap command with environment prefix if isolated execution is configured
        wrapped_cmd: str | list[str] = cmd
        if self.env_prefix:
            if isinstance(cmd, str):
                import shlex

                wrapped_cmd = " ".join(shlex.quote(part) for part in self.env_prefix) + " " + cmd
            else:
                wrapped_cmd = self.env_prefix + list(cmd)

        return await run_subprocess(
            cmd=wrapped_cmd,
            cwd=cwd or self.node_dir,
            env=env,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            emit=self.emit,
            node_id=self.node_id,
            timeout=timeout,
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
    ) -> None:
        self.workspace_dir = Path(workspace_dir)
        self.cache = CacheStore(cache_dir or self.workspace_dir / "cache")
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.registry = registry
        self.settings = settings

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

        Returns:
            Execution result dict with ``status``, ``outputs``, ``previews``,
            ``metadata``, and ``node_results``.
        """
        options = options or {}
        force_nodes = force_nodes or set()
        cancel_event = cancel_event or asyncio.Event()

        if emit is None:
            def _noop_emit(event: str, data: dict[str, Any]) -> None:
                pass
            emit = _noop_emit

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
        loop_body_node_ids = {body_node for body in loop_bodies.values() for body_node in body}
        nodes = {
            node_id: node
            for node_id, node in all_nodes.items()
            if node_id not in loop_body_node_ids
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

        emit("start", {"run_id": run_id, "total_nodes": len(execution_order)})

        # State tracking
        node_results: dict[str, dict[str, Any]] = {}
        node_cache_keys: dict[str, str | None] = {}
        node_outputs: dict[str, dict[str, str]] = {}
        node_inactive_outputs: dict[str, set[str]] = {}
        failed_nodes: set[str] = set()
        skipped_nodes: set[str] = set()
        previews: list[dict[str, Any]] = []
        run_metadata: dict[str, Any] = {
            "run_id": run_id,
            "forced": force,
            "target_nodes": sorted(target_nodes),
            "nodes": {},
        }

        stop_on_error = options.get("stop_on_error", True)

        for idx, node_id in enumerate(execution_order):
            if cancel_event.is_set():
                emit("cancelled", {"run_id": run_id, "node_id": node_id})
                return {
                    "status": "cancelled",
                    "node_results": node_results,
                    "cancelled_at": node_id,
                }

            node = nodes[node_id]
            node_type = node.get("type", "unknown")
            node_meta = node.get("meta", {})

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
                    node_id, node, edge_map, node_outputs
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
                    break
                continue

            # ---- Fill parameter defaults ----
            _node_class = node.get("_node_class")
            if _node_class is None and self.registry is not None and hasattr(self.registry, "get"):
                _node_class = self.registry.get(str(node.get("type", "unknown")))
            resolved_params = self._with_defaults(node, resolved_inputs, _node_class)
            executes_loop_body = self._executes_loop_body(_node_class)

            # ---- Build upstream cache key map ----
            upstream_keys: dict[str, str | None] = {}
            for edge in edge_map.get(node_id, []):
                src = edge_source(edge)
                src_port = edge_source_port(edge)
                tgt_port = edge_target_port(edge)
                upstream_keys[f"{src}:{src_port}->{tgt_port}"] = node_cache_keys.get(src)

            # ---- Compute cache key ----
            cache_key = None
            forced_node = force or node_id in force_nodes or executes_loop_body
            if not forced_node:
                cache_key = self.cache.cache_key_for_node(
                    node_id=node_id,
                    node_type=node_type,
                    params=resolved_params,
                    inputs=resolved_inputs,
                    upstream_keys=upstream_keys,
                )
            node_cache_keys[node_id] = cache_key

            # ---- Cache hit check ----
            if cache_key is not None and self.cache.is_hit(cache_key):
                marker = self.cache.read_marker(cache_key)
                cached_outputs = marker.get("outputs", {}) if marker else {}
                inactive_outputs = self._inactive_output_ports(
                    marker or {},
                    cached_outputs,
                    _node_class,
                )
                if inactive_outputs:
                    node_inactive_outputs[node_id] = inactive_outputs
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
                # Collect previews from cached outputs too
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

            # ---- Prepare node working directory ----
            node_dir = self.workspace_dir / "runs" / run_id / node_id
            node_dir.mkdir(parents=True, exist_ok=True)

            # ---- Determine environment prefix for isolated execution ----
            env_prefix: list[str] = []
            isolation = getattr(self.settings, "execution", None)
            isolation_mode = getattr(isolation, "env_isolation", "auto") if isolation else "auto"
            if isolation_mode in ("auto", "always"):
                env_prefix = self._env_prefix_for_node(node, workflow)

            # ---- Build execution context ----
            ctx = ExecutionContext(
                run_id=run_id,
                node_id=node_id,
                node_type=node_type,
                node_dir=node_dir,
                workspace_dir=self.workspace_dir,
                params=resolved_params,
                api_secrets=options.get("api_secrets", {}),
                emit=emit,
                cancel_event=cancel_event,
                env_prefix=env_prefix,
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
                else:
                    result = await self._execute_node(ctx, node, resolved_inputs)
                outputs = result.get("outputs", {})
                inactive_outputs = self._inactive_output_ports(
                    result,
                    outputs,
                    _node_class,
                )
                if inactive_outputs:
                    node_inactive_outputs[node_id] = inactive_outputs
                node_results[node_id] = {
                    "status": "completed",
                    "outputs": outputs,
                    "cache_key": cache_key,
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
                    )

                # Collect previews
                node_previews = self._collect_previews(ctx, result)
                previews.extend(node_previews)

                emit(
                    "node_complete",
                    {
                        "run_id": run_id,
                        "node_id": node_id,
                        "outputs": outputs,
                    },
                )

            except Exception as exc:
                tb = traceback.format_exc()
                msg = f"Execution failed for {node_id}: {exc}"
                emit(
                    "node_error",
                    {
                        "run_id": run_id,
                        "node_id": node_id,
                        "error": msg,
                        "traceback": tb,
                    },
                )
                node_results[node_id] = {"status": "failed", "error": msg, "traceback": tb}
                failed_nodes.add(node_id)
                if stop_on_error:
                    break

            run_metadata["nodes"][node_id] = {
                "type": node_type,
                "status": node_results[node_id]["status"],
                "cache_key": cache_key,
            }

        # ---- Finalize ----
        final_status = "completed" if not failed_nodes else "failed"
        if cancel_event.is_set():
            final_status = "cancelled"

        run_metadata["status"] = final_status
        run_metadata["failed_nodes"] = list(failed_nodes)
        run_metadata["skipped_nodes"] = list(skipped_nodes)

        # Collect all artifacts
        artifacts = self._collect_artifacts(run_id, nodes, node_results)

        # Write run metadata
        self._write_metadata(run_id, run_metadata)

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

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _inactive_upstream(
        self,
        node_id: str,
        edge_map: dict[str, list[dict[str, Any]]],
        skipped_nodes: set[str],
        node_inactive_outputs: dict[str, set[str]],
    ) -> dict[str, str] | None:
        """Return the first upstream branch edge that should prevent execution."""
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
        return {str(port) for port, value in outputs.items() if value is None}

    @staticmethod
    def _routes_flow(node_class: Any) -> bool:
        return bool(getattr(node_class, "ROUTES_FLOW", False))

    @staticmethod
    def _executes_loop_body(node_class: Any) -> bool:
        return bool(getattr(node_class, "EXECUTES_LOOP_BODY", False))

    def _node_class_for(self, node: dict[str, Any]) -> Any:
        node_class = node.get("_node_class")
        if node_class is None and self.registry is not None and hasattr(self.registry, "get"):
            node_class = self.registry.get(str(node.get("type", "unknown")))
        return node_class

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

    # Types that indicate a file or directory path parameter
    _FILE_TYPES: set[str] = {
        "FASTQ_LIST", "FASTA", "FASTQ", "BAM", "SAM", "VCF", "GFF", "GTF",
        "BED", "WIG", "BIGWIG", "FILE", "DIR", "PATH", "INDEX_DIR",
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

        for iteration_index, batch in enumerate(batches):
            if ctx.cancel_event.is_set():
                raise RuntimeError(f"Loop {ctx.node_id} cancelled")
            iteration_value: Any = batch if iteration_mode == "batch" else batch[0]
            local_outputs: dict[str, dict[str, Any]] = {
                ctx.node_id: {"iteration": iteration_value},
            }
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

                    combined_outputs = {**node_outputs, **local_outputs}
                    body_inputs = self._resolve_inputs(
                        body_node_id,
                        body_node,
                        body_edge_map,
                        combined_outputs,
                    )
                    body_params = self._with_defaults(body_node, body_inputs, body_class)
                    body_dir = (
                        self.workspace_dir
                        / "runs"
                        / ctx.run_id
                        / ctx.node_id
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
                        api_secrets=options.get("api_secrets", {}),
                        emit=emit,
                        cancel_event=ctx.cancel_event,
                        env_prefix=self._env_prefix_for_node(body_node, workflow),
                    )
                    body_result = await self._execute_node(body_ctx, body_node, body_inputs)
                    outputs = body_result.get("outputs", {})
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
            if edge_target(edge) != loop_node_id or edge_target_port(edge) != "body_result":
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

    async def _execute_node(
        self,
        ctx: ExecutionContext,
        node: dict[str, Any],
        inputs: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a single node via its ``run()`` method."""
        node_class = node.get("_node_class")
        # Fallback: look up in registry if _node_class is not attached
        if node_class is None and self.registry is not None and hasattr(self.registry, "get"):
            node_class = self.registry.get(node.get("type", "unknown"))
        if node_class is not None and hasattr(node_class, "run"):
            kwargs = {**inputs, **ctx.params}
            kwargs = {k: v for k, v in kwargs.items() if not k.startswith("_")}
            kwargs = self._resolve_file_paths(node_class, kwargs)
            node_instance = node_class()
            if asyncio.iscoroutinefunction(node_class.run):
                raw = await node_instance.run(context=ctx, **kwargs)
            else:
                raw = node_instance.run(context=ctx, **kwargs)
            return self._normalize_result(raw, node_class)

        raise RuntimeError(
            f"Node class not found for '{node.get('type', 'unknown')}'. "
            "Ensure the node is registered in the node registry."
        )

    def _normalize_result(
        self,
        raw: Any,
        node_class: Any,
    ) -> dict[str, Any]:
        """Normalize node return value to dict format expected by the executor."""
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, tuple):
            return_names = getattr(node_class, "RETURN_NAMES", ()) or ()
            outputs: dict[str, Any] = {}
            for idx, val in enumerate(raw):
                name = return_names[idx] if idx < len(return_names) else f"output_{idx}"
                outputs[name] = val
            return {"outputs": outputs}
        if raw is None:
            return {"outputs": {}}
        # Single scalar value
        return_names = getattr(node_class, "RETURN_NAMES", ()) or ()
        name = return_names[0] if return_names else "default"
        return {"outputs": {name: raw}}

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
    ) -> dict[str, Any]:
        """Resolve edge connections to actual values from upstream outputs."""
        inputs: dict[str, Any] = {}
        node_def_inputs = node.get("inputs", {})

        # Start with literal/default values from node definition
        for inp_name, inp_val in node_def_inputs.items():
            if isinstance(inp_val, dict) and "value" in inp_val:
                inputs[inp_name] = inp_val["value"]
            else:
                inputs[inp_name] = inp_val

        # Fallback: use params if no inputs defined (frontend/template format)
        if not inputs:
            for pname, pval in node.get("params", {}).items():
                inputs[pname] = pval

        # Override with upstream connections
        for edge in edge_map.get(node_id, []):
            src = edge_source(edge)
            src_port = edge_source_port(edge)
            tgt_port = edge_target_port(edge)

            if src in node_outputs:
                upstream_out = node_outputs[src]
                if src_port in upstream_out:
                    inputs[tgt_port] = upstream_out[src_port]
                elif "default" in upstream_out:
                    inputs[tgt_port] = upstream_out["default"]

        return inputs

    def _with_defaults(
        self,
        node: dict[str, Any],
        inputs: dict[str, Any],
        node_class: Any = None,
    ) -> dict[str, Any]:
        """Fill in default parameter values from node definition."""
        params: dict[str, Any] = {}
        # Widget values / parameters
        widgets = node.get("widgets", {})
        params.update(widgets)
        # Fallback: params from frontend/template format
        for pname, pval in node.get("params", {}).items():
            if pname not in params:
                params[pname] = pval
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
    ) -> list[dict[str, Any]]:
        """Collect previewable output files (HTML, images, JSON, etc.)."""
        previews: list[dict[str, Any]] = []

        for port, path in result.get("outputs", {}).items():
            paths = path if isinstance(path, (list, tuple)) else [path]
            for p_str in paths:
                if not isinstance(p_str, (str, Path)):
                    continue
                p = Path(p_str)
                if p.exists() and p.suffix.lower() in PREVIEWABLE_EXTENSIONS:
                    previews.append(
                        {
                            "path": str(p),
                            "label": f"{ctx.node_id}/{port}",
                            "node_id": ctx.node_id,
                        }
                    )

        return previews + ctx._previews

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
                    if p.exists():
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

    def _write_metadata(self, run_id: str, metadata: dict[str, Any]) -> None:
        """Write run metadata JSON to the workspace."""
        meta_dir = self.workspace_dir / "runs" / run_id
        meta_dir.mkdir(parents=True, exist_ok=True)
        meta_path = meta_dir / "run_metadata.json"
        with open(meta_path, "w", encoding="utf-8") as fh:
            json.dump(metadata, fh, indent=2, ensure_ascii=True)

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

        # Use the node's own ENVIRONMENT if explicitly set
        env_spec = getattr(node_class, "ENVIRONMENT", {}) if node_class else {}
        if env_spec and isinstance(env_spec, dict):
            env_type = env_spec.get("type", "pixi")
            env_name = env_spec.get("name", "")
            if env_name:
                return self._command_prefix_list(env_type, env_name)

        # Default: workflow-scoped manifest
        if workflow is not None:
            packages = workflow_to_packages(workflow, self.registry)
            env_id = get_env_id(packages)
            env_dir = get_env_dir(env_id, self.workspace_dir)
            manifest_path = env_dir / "pixi.toml"
            if manifest_path.exists():
                return self._command_prefix_list("pixi", None, manifest_path=manifest_path)

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
            return [exe, "run", "--manifest-path", str(manifest_path), "--"]
        if env_type == "pixi" and env_name:
            return [exe, "run", "-e", env_name, "--"]
        return []
